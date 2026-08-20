"""PDF de Oferta de consultorios (Etapa 7, sección 4.6, alineado a DC-03/
DC-07/DC-08 §F24). Se genera a partir de uno o más pedidos de lista de
espera (`ListaEspera`, sección 3.21) — reusa el mismo motor de cruce que
ya arma las coincidencias para esa pantalla
(`negocio.lista_espera.calcular_coincidencia`) en vez de reimplementar la
búsqueda de alternativas.

Nombre de archivo fijo "Oferta consultorios.pdf": siempre se sobrescribe,
sin historial de versiones (a diferencia de Liquidación/Disponibilidad).

Anonimización (sección 4.6): "Profesional activo (departamento real) / No
activo ('Unidad N')" — a diferencia de Disponibilidad (siempre activos) y
Propuesta (siempre no activos), acá depende del profesional dueño del
pedido en particular.

Estructura (3 secciones de nivel 1): "Criterios de búsqueda" (un bloque
por franja horaria pedida) -> "Coincidencias" (una explicación en texto
del tipo de cobertura encontrada por franja — cobertura directa,
combinación dentro de la misma unidad/edificio/entre edificios, o sin
disponibilidad — más el detalle día por día) -> "Consultorios que
intervienen en las ofertas" (fotos + valores, unión de todos los
consultorios ofrecidos en cualquiera de las franjas, agrupados por
edificio cuando hay más de uno).
"""
from __future__ import annotations

import json
import os
import sqlite3

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.negocio.dias import parsear_periodo, periodo_actual
from app.negocio.formato import hora_fmt
from app.negocio.lista_espera import AMARILLO, NARANJA, ROJO, VERDE, Coincidencia, calcular_coincidencia
from app.pdf.edificios_pdf import numero_unidad_en_edificio
from app.negocio.formato import decimales_configurados, formatear_moneda
from app.pdf.estilos import clave_orden_unidad, construir_sin_saltos, encabezado, estilo_texto
from app.pdf.fotos_pdf import imagenes_de_consultorios, tabla_fotos
from app.repositorio.registro import obtener_repositorio

_ES_ACTIVO = ("R", "A", "B", "E")

_DESCRIPCION_COINCIDENCIA = {
    VERDE: "Cobertura directa: un solo consultorio cubre todo el horario pedido.",
    AMARILLO: "Requiere combinar más de un consultorio, todos dentro de la misma unidad.",
    NARANJA: "Requiere combinar consultorios de distintas unidades, dentro del mismo edificio.",
    ROJO: "Requiere combinar consultorios de distintos edificios.",
}

_NOMBRES_CONDICION = {
    "ventana": "con ventana", "aptoCamilla": "apto camilla",
    "balcon": "con balcón", "aire": "con aire acondicionado",
    "sinCombinar": "sin combinación de consultorios",
}


def _categoria_es_activa(profesional: sqlite3.Row) -> bool:
    return profesional["CategoriaProfesional"] in _ES_ACTIVO


def _etiqueta_franja(pedido: sqlite3.Row, indice: int) -> str:
    return pedido["Detalle"] or f"Franja horaria {indice + 1}"


def _texto_criterios(conn: sqlite3.Connection, pedido: sqlite3.Row) -> list:
    """Un pedido puede tener varios bloques día(s)+horario (ej. "martes o
    jueves de 14 a 18hs" Y "sábado de 9 a 12hs") — cada uno se detalla por
    separado, y si hay más de uno se agrega al final cómo se combinan
    entre sí (`pedido['TipoCombinacion']`, entre bloques)."""
    condiciones = json.loads(pedido["CondicionesConsultorio"] or "{}")
    bloques = obtener_repositorio(conn, "ListaEsperaBloque").listar(IdPedido=pedido["IdPedido"])
    style = estilo_texto(9)
    partes_condiciones = [_NOMBRES_CONDICION[k] for k, v in condiciones.items() if v and k in _NOMBRES_CONDICION]
    if condiciones.get("tamano"):
        partes_condiciones.append(f"tamaño {condiciones['tamano']}")

    story = []
    for indice, bloque in enumerate(bloques):
        dias = json.loads(bloque["Dias"] or "[]")
        desde, hasta = hora_fmt(bloque["HorarioDesde"])[:-2], hora_fmt(bloque["HorarioHasta"])
        cantidad_horas = bloque["CantidadHorasRequeridas"]
        if cantidad_horas:
            texto_horario = f"{cantidad_horas:g}hs dentro del rango de {desde} a {hasta} (no hace falta que sea el rango completo)"
        else:
            texto_horario = f"{desde} a {hasta}"
        prefijo = f"Bloque {indice + 1} — " if len(bloques) > 1 else ""
        story.append(Paragraph(f"<b>{prefijo}Días solicitados:</b> {', '.join(dias) or '—'}", style))
        story.append(Paragraph(f"<b>Horario:</b> {texto_horario}", style))
        story.append(Paragraph(
            f"<b>Combinación de días:</b> "
            f"{'todos los días pedidos' if bloque['TipoCombinacionDias'] == 'Y' else 'alcanza con uno de los días pedidos'}",
            style,
        ))
    if len(bloques) > 1:
        story.append(Paragraph(
            f"<b>Combinación de bloques:</b> "
            f"{'se necesitan todos los bloques' if pedido['TipoCombinacion'] == 'Y' else 'alcanza con uno de los bloques'}",
            style,
        ))
    if partes_condiciones:
        story.append(Paragraph(f"<b>Condiciones del consultorio:</b> {', '.join(partes_condiciones)}", style))
    return story


def _mapa_consultorios_basico(conn: sqlite3.Connection, ids_consultorio: list[int]) -> dict[int, sqlite3.Row]:
    if not ids_consultorio:
        return {}
    placeholders = ", ".join("?" for _ in ids_consultorio)
    filas = conn.execute(
        f"""
        SELECT c.IdConsultorio, c.NumeroConsultorio, c.ValorHoraRegularActual,
               u.IdUnidad, u.Departamento, e.IdEdificio, e.Nombre AS NombreEdificio
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE c.IdConsultorio IN ({placeholders})
        """,
        ids_consultorio,
    ).fetchall()
    return {f["IdConsultorio"]: f for f in filas}


def _texto_coincidencia(coincidencia: Coincidencia | None, consultorios: dict, anonimizar: bool) -> list:
    """Explica el tipo de cobertura encontrada y, día por día, el detalle:
    una línea simple para un consultorio único, o "combinación de
    consultorios:" con un renglón indentado por tramo cuando hace falta
    más de uno — mismo criterio que el mensaje de texto para WhatsApp, así
    el PDF no queda con una redacción distinta para lo mismo."""
    style = estilo_texto(9)
    if coincidencia is None:
        return [Paragraph("Sin disponibilidad para este bloque con los filtros solicitados.", style)]

    story = [Paragraph(f"<i>{_DESCRIPCION_COINCIDENCIA.get(coincidencia.color, '')}</i>", style)]
    for dia, tramos in coincidencia.tramos_por_dia.items():
        if len(tramos) == 1:
            t = tramos[0]
            c = consultorios.get(t.id_consultorio)
            if c is None:
                continue
            unidad = f"Unidad {c['IdUnidad']}" if anonimizar else c["Departamento"]
            story.append(Paragraph(
                f"* {dia} de {hora_fmt(t.hora_inicio)[:-2]} a {hora_fmt(t.hora_fin)} — "
                f"Consultorio {c['NumeroConsultorio']} - {unidad} - {c['NombreEdificio']}",
                style,
            ))
        else:
            story.append(Paragraph(f"* {dia}, combinación de consultorios:", style))
            for t in tramos:
                c = consultorios.get(t.id_consultorio)
                if c is None:
                    continue
                unidad = f"Unidad {c['IdUnidad']}" if anonimizar else c["Departamento"]
                story.append(Paragraph(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;· de {hora_fmt(t.hora_inicio)[:-2]} a {hora_fmt(t.hora_fin)} — "
                    f"Consultorio {c['NumeroConsultorio']} - {unidad} - {c['NombreEdificio']}",
                    style,
                ))
    return story


def _consultorios_ordenados(conn: sqlite3.Connection, consultorios: dict, anonimizar: bool) -> list[sqlite3.Row]:
    """Sin activar (anonimizado): edificio, unidad (posición dentro del
    edificio) y consultorio. Profesional activo (departamento real):
    edificio, piso y departamento (`clave_orden_unidad`, el mismo criterio
    que el resto del sistema) y consultorio."""
    numeros_por_edificio: dict[int, dict[int, int]] = {}
    if anonimizar:
        for id_edificio in {c["IdEdificio"] for c in consultorios.values()}:
            numeros_por_edificio[id_edificio] = numero_unidad_en_edificio(conn, id_edificio)

    def clave(c: sqlite3.Row):
        if anonimizar:
            return (c["IdEdificio"], numeros_por_edificio[c["IdEdificio"]].get(c["IdUnidad"], 0), c["NumeroConsultorio"])
        return (c["IdEdificio"], clave_orden_unidad(c["Departamento"]), c["NumeroConsultorio"])

    return sorted(consultorios.values(), key=clave)


def _bloque_consultorios_intervinientes(
    conn: sqlite3.Connection, consultorios: dict, imagenes: list[sqlite3.Row], anonimizar: bool, ancho: float,
    decimales: int,
) -> list:
    if not consultorios:
        return [Paragraph("No hay consultorios involucrados en las alternativas encontradas.", estilo_texto(9))]

    consultorios_ordenados = _consultorios_ordenados(conn, consultorios, anonimizar)
    imagenes_por_consultorio: dict[int, list] = {}
    for img in imagenes:
        imagenes_por_consultorio.setdefault(img["IdConsultorio"], []).append(img)

    ids_edificio_orden = list(dict.fromkeys(c["IdEdificio"] for c in consultorios_ordenados))
    multi = len(ids_edificio_orden) > 1

    story = []
    for id_edificio in ids_edificio_orden:
        del_edificio = [c for c in consultorios_ordenados if c["IdEdificio"] == id_edificio]
        if multi:
            story.append(encabezado(2, f"Edificio {del_edificio[0]['NombreEdificio']}", ancho))
            story.append(Spacer(1, 6))
        imagenes_ed = [img for c in del_edificio for img in imagenes_por_consultorio.get(c["IdConsultorio"], [])]
        story.extend(tabla_fotos(
            imagenes_ed, ancho, mostrar_apto_camilla=True, anonimizar_unidad=anonimizar, decimales=decimales,
        ))
        for c in del_edificio:
            unidad = f"Unidad {c['IdUnidad']}" if anonimizar else c["Departamento"]
            story.append(Paragraph(
                f"Consultorio {c['NumeroConsultorio']} - {unidad} - {c['NombreEdificio']}: "
                f"{formatear_moneda(c['ValorHoraRegularActual'], decimales)}/hora",
                estilo_texto(9),
            ))
        story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Los valores detallados corresponden a los vigentes a este mes en curso, y a los mismos luego se le "
        "aplican los descuentos en base a la cantidad de horas regulares que se tenga reservadas.",
        estilo_texto(8, italica=True),
    ))
    return story


def generar_pdf_oferta_multiple(conn: sqlite3.Connection, directorio: str, ids_pedido: list[int]) -> str:
    """Genera "Oferta consultorios.pdf" combinando varios pedidos de lista
    de espera del MISMO profesional en un solo documento.

    Un mismo pedido ya admite varios bloques día(s)+horario combinados
    entre sí con Y/O (ListaEsperaBloque) — esta función combina, además,
    varios PEDIDOS del mismo profesional en un solo documento (para
    búsquedas que conviene rastrear como filas separadas en la pantalla
    de Lista de espera en vez de como bloques de un mismo pedido). Este
    PDF muestra "Criterios de búsqueda" y "Coincidencias" de todos los
    pedidos juntos, con una única sección final de "Consultorios que
    intervienen en las ofertas" (unión de los consultorios ofrecidos en
    cualquiera de ellos)."""
    repo_pedido = obtener_repositorio(conn, "ListaEspera")
    pedidos = [repo_pedido.obtener(id_pedido) for id_pedido in ids_pedido]
    faltante = next((id_pedido for id_pedido, p in zip(ids_pedido, pedidos) if p is None), None)
    if faltante is not None:
        raise ValueError(f"No existe el pedido de lista de espera #{faltante}")
    ids_profesional = {p["IdProfesional"] for p in pedidos}
    if len(ids_profesional) > 1:
        raise ValueError("Los pedidos deben pertenecer al mismo profesional para combinarlos en un solo PDF")

    profesional = obtener_repositorio(conn, "Profesional").obtener(pedidos[0]["IdProfesional"])
    anonimizar = not (profesional is not None and _categoria_es_activa(profesional))
    decimales = decimales_configurados(conn)

    anio, mes = parsear_periodo(periodo_actual(conn))
    coincidencias = [calcular_coincidencia(conn, p, anio, mes) for p in pedidos]
    ids_consultorio = sorted({
        t.id_consultorio for c in coincidencias if c is not None for tramos in c.tramos_por_dia.values() for t in tramos
    })
    consultorios = _mapa_consultorios_basico(conn, ids_consultorio)
    imagenes = imagenes_de_consultorios(conn, ids_consultorio)

    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"

    multi_franjas = len(pedidos) > 1
    altura = (
        6 * cm + len(pedidos) * 3 * cm * 2 + len(ids_consultorio) * 2 * 0.5 * cm
        + (len(imagenes) // 2 + 1) * 7 * cm + 3 * cm
    ) * 1.2

    def _construir_story(ancho: float) -> list:
        story = [
            Paragraph(nombre_espacio.upper(), estilo_texto(20, negrita=True)),
            Paragraph("Oferta de consultorios", estilo_texto(11)),
            Spacer(1, 10),
        ]

        story.append(encabezado(1, "Criterios de búsqueda", ancho))
        story.append(Spacer(1, 8))
        for i, pedido in enumerate(pedidos):
            if multi_franjas:
                story.append(encabezado(2, _etiqueta_franja(pedido, i), ancho))
                story.append(Spacer(1, 4))
            story.extend(_texto_criterios(conn, pedido))
            story.append(Spacer(1, 8))

        story.append(encabezado(1, "Coincidencias", ancho))
        story.append(Spacer(1, 8))
        for i, (pedido, coincidencia) in enumerate(zip(pedidos, coincidencias)):
            if multi_franjas:
                story.append(encabezado(2, _etiqueta_franja(pedido, i), ancho))
                story.append(Spacer(1, 4))
            story.extend(_texto_coincidencia(coincidencia, consultorios, anonimizar))
            story.append(Spacer(1, 8))

        story.append(encabezado(1, "Consultorios que intervienen en las ofertas", ancho))
        story.append(Spacer(1, 8))
        story.extend(_bloque_consultorios_intervinientes(conn, consultorios, imagenes, anonimizar, ancho, decimales))
        return story

    ruta = os.path.join(directorio, "Oferta consultorios.pdf")
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta


def generar_pdf_oferta(conn: sqlite3.Connection, directorio: str, id_pedido: int) -> str:
    """Genera "Oferta consultorios.pdf" a partir de un único pedido de
    lista de espera y devuelve la ruta completa (siempre el mismo nombre:
    se sobrescribe en cada regeneración)."""
    return generar_pdf_oferta_multiple(conn, directorio, [id_pedido])
