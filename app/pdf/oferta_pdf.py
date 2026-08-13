"""PDF de Oferta de consultorios (Etapa 7, sección 4.6). Se genera a partir
de un pedido de lista de espera (`ListaEspera`, sección 3.21) — reusa el
mismo motor de cruce que ya arma las coincidencias para esa pantalla
(`negocio.lista_espera.calcular_coincidencia`) en vez de reimplementar la
búsqueda de alternativas.

Nombre de archivo fijo "Oferta consultorios.pdf": siempre se sobrescribe,
sin historial de versiones (a diferencia de Liquidación/Disponibilidad).

Anonimización (sección 4.6): "Profesional activo (departamento real) / No
activo ('Unidad N')" — a diferencia de Disponibilidad (siempre activos) y
Propuesta (siempre no activos), acá depende del profesional dueño del
pedido en particular.
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
from app.pdf.estilos import construir_sin_saltos, encabezado, estilo_texto, formatear_moneda
from app.pdf.fotos_pdf import imagenes_de_consultorios, tabla_fotos
from app.repositorio.registro import obtener_repositorio

_ES_ACTIVO = ("R", "A", "B", "E")
_COLOR_BADGE_HEX = {VERDE: "#4CAF50", AMARILLO: "#F5D547", NARANJA: "#E07B39", ROJO: "#C0392B"}


def _categoria_es_activa(profesional: sqlite3.Row) -> bool:
    return profesional["CategoriaProfesional"] in _ES_ACTIVO


def _texto_filtros(pedido: sqlite3.Row) -> list:
    condiciones = json.loads(pedido["CondicionesConsultorio"] or "{}")
    dias = json.loads(pedido["Dias"] or "[]")
    style = estilo_texto(9)
    nombres_condicion = {
        "ventana": "con ventana", "aptoCamilla": "apto camilla",
        "balcon": "con balcón", "aire": "con aire acondicionado",
        "sinCombinar": "sin combinación de consultorios",
    }
    partes_condiciones = [nombres_condicion[k] for k, v in condiciones.items() if v and k in nombres_condicion]
    if condiciones.get("tamano"):
        partes_condiciones.append(f"tamaño {condiciones['tamano']}")

    story = [
        Paragraph(f"<b>Días solicitados:</b> {', '.join(dias) or '—'}", style),
        Paragraph(
            f"<b>Horario:</b> {hora_fmt(pedido['HorarioDesde'])[:-2]} a {hora_fmt(pedido['HorarioHasta'])}", style,
        ),
        Paragraph(
            f"<b>Combinación de días:</b> {'todos los días pedidos' if pedido['TipoCombinacion'] == 'Y' else 'alcanza con uno de los días pedidos'}",
            style,
        ),
    ]
    if partes_condiciones:
        story.append(Paragraph(f"<b>Condiciones del consultorio:</b> {', '.join(partes_condiciones)}", style))
    if pedido["Detalle"]:
        story.append(Paragraph(f"<b>Detalle:</b> {pedido['Detalle']}", style))
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


def _alternativas(coincidencia: Coincidencia | None, consultorios: dict, anonimizar: bool, ancho: float) -> list:
    style = estilo_texto(9)
    if coincidencia is None:
        return [Paragraph("Sin alternativas disponibles con los filtros solicitados.", style)]

    badge_hex = _COLOR_BADGE_HEX.get(coincidencia.color, "#000000")
    story = [Paragraph(
        f'<font color="{badge_hex}"><b>&bull;</b></font> Coincidencia: {coincidencia.color}', style,
    )]
    for dia, tramos in coincidencia.tramos_por_dia.items():
        for t in tramos:
            c = consultorios.get(t.id_consultorio)
            if c is None:
                continue
            unidad = f"Unidad {c['IdUnidad']}" if anonimizar else c["Departamento"]
            story.append(Paragraph(
                f"* {dia} de {hora_fmt(t.hora_inicio)[:-2]} a {hora_fmt(t.hora_fin)} — "
                f"Consultorio {c['NumeroConsultorio']} - {unidad} - {c['NombreEdificio']}",
                style,
            ))
    return story


def _bloque_filtros_y_alternativas(
    pedido: sqlite3.Row, coincidencia: Coincidencia | None, consultorios: dict, anonimizar: bool, ancho: float,
) -> list:
    story = [encabezado(2, "Filtros de búsqueda y alternativas disponibles", ancho), Spacer(1, 4)]
    story.extend(_texto_filtros(pedido))
    story.append(Spacer(1, 4))
    story.extend(_alternativas(coincidencia, consultorios, anonimizar, ancho))
    return story


def _bloque_fotos_valores(imagenes: list[sqlite3.Row], consultorios: dict, anonimizar: bool, ancho: float) -> list:
    story = [encabezado(2, "Fotos y valores regulares de los consultorios ofrecidos", ancho), Spacer(1, 4)]
    story.extend(tabla_fotos(imagenes, ancho, mostrar_apto_camilla=True, anonimizar_unidad=anonimizar))
    for c in consultorios.values():
        unidad = f"Unidad {c['IdUnidad']}" if anonimizar else c["Departamento"]
        story.append(Paragraph(
            f"Consultorio {c['NumeroConsultorio']} - {unidad} - {c['NombreEdificio']}: "
            f"{formatear_moneda(c['ValorHoraRegularActual'])}/hora",
            estilo_texto(9),
        ))
    if len({c["IdEdificio"] for c in consultorios.values()}) > 1:
        for id_ed in {c["IdEdificio"] for c in consultorios.values()}:
            nombre_ed = next(c["NombreEdificio"] for c in consultorios.values() if c["IdEdificio"] == id_ed)
            story.append(Paragraph(f"* Edificio {nombre_ed}", estilo_texto(8, italica=True)))
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

    El sistema representa cada pedido con un único horario aplicado a una
    lista de días (`ListaEspera.HorarioDesde/HorarioHasta`) — no admite
    franjas horarias distintas por día dentro de un mismo pedido. Una
    búsqueda con varias franjas (p. ej. "lunes a jueves de 8 a 15hs" +
    "lunes de 8 a 12hs" + "viernes desde las 16hs") se arma como varios
    pedidos, uno por franja, y este PDF muestra las alternativas de todos
    juntos en un solo archivo: un bloque "Filtros de búsqueda y
    alternativas disponibles" por pedido, seguido de una única sección de
    fotos y valores con la unión de los consultorios ofrecidos en
    cualquiera de las franjas."""
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

    anio, mes = parsear_periodo(periodo_actual(conn))
    coincidencias = [calcular_coincidencia(conn, p, anio, mes) for p in pedidos]
    ids_consultorio = sorted({
        t.id_consultorio for c in coincidencias if c is not None for tramos in c.tramos_por_dia.values() for t in tramos
    })
    consultorios = _mapa_consultorios_basico(conn, ids_consultorio)
    imagenes = imagenes_de_consultorios(conn, ids_consultorio)

    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"

    altura = (
        6 * cm + len(pedidos) * 3 * cm + len(ids_consultorio) * 2 * 0.5 * cm
        + (len(imagenes) // 2 + 1) * 7 * cm + 3 * cm
    ) * 1.2

    def _construir_story(ancho: float) -> list:
        story = [
            Paragraph(nombre_espacio.upper(), estilo_texto(20, negrita=True)),
            Paragraph("Oferta de consultorios", estilo_texto(11)),
            Spacer(1, 10),
        ]
        for pedido, coincidencia in zip(pedidos, coincidencias):
            story.extend(_bloque_filtros_y_alternativas(pedido, coincidencia, consultorios, anonimizar, ancho))
            story.append(Spacer(1, 10))
        story.extend(_bloque_fotos_valores(imagenes, consultorios, anonimizar, ancho))
        return story

    ruta = os.path.join(directorio, "Oferta consultorios.pdf")
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta


def generar_pdf_oferta(conn: sqlite3.Connection, directorio: str, id_pedido: int) -> str:
    """Genera "Oferta consultorios.pdf" a partir de un único pedido de
    lista de espera y devuelve la ruta completa (siempre el mismo nombre:
    se sobrescribe en cada regeneración)."""
    return generar_pdf_oferta_multiple(conn, directorio, [id_pedido])
