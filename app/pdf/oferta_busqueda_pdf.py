"""PDF de Oferta de consultorios armado a partir de una búsqueda ad-hoc
(`app.negocio.oferta_busqueda`) — distinto del PDF de Oferta atado a un
pedido de Lista de espera (`app.pdf.oferta_pdf`). Este es el que se arma
cuando un profesional pide opciones de consultorios (para reservar en
forma regular o por horas aisladas) y el resultado puede salir como este
PDF o como mensaje de WhatsApp (el mensaje se resuelve más adelante, con
el mismo motor de búsqueda).

Nombre de archivo fijo "Oferta consultorios.pdf": siempre se sobrescribe,
sin historial de versiones.

Anonimización: depende de si el profesional que pide la búsqueda está
activo en el espacio (departamento real) o no (anonimizado como
"Unidad N"), igual criterio que el resto de los PDFs con esta lógica.

Estructura: nivel 1 "Búsqueda solicitada por {profesional}" -> nivel 2
"Criterios de búsqueda generales" (los criterios comunes a todas las
búsquedas del documento: tipo, localidad, edificios/unidades/consultorios
alcanzados) -> por cada búsqueda, nivel 2 "Búsqueda {N}" con nivel 3
"Criterios de búsqueda específicos" (los filtros particulares de esa
búsqueda) y nivel 3 "Coincidencias de la búsqueda" (las alternativas
encontradas, con una explicación en texto del tipo de cobertura) -> nivel
2 "Fotos de los consultorios que intervienen en las búsquedas" (unión de
todos los consultorios ofrecidos en cualquiera de las búsquedas,
agrupados por edificio cuando hay más de uno administrado, ordenados por
unidad real o posición anonimizada y consultorio; el pie de cada foto es
Edificio (si hay más de uno) - Unidad - Consultorio: Valor/hora, sin
repetir el valor en ningún otro lado)."""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.negocio.formato import fecha_larga, hora_fmt
from app.negocio.oferta_busqueda import (
    AMARILLO,
    NARANJA,
    TIPO_REGULAR,
    VERDE,
    Busqueda,
    CriteriosGlobales,
    ResultadoBusqueda,
    resolver_busqueda,
)
from app.pdf.edificios_pdf import numero_unidad_en_edificio
from app.pdf.estilos import (
    clave_orden_unidad,
    construir_sin_saltos,
    decimales_configurados,
    encabezado,
    encabezado_espacio,
    estilo_texto,
    formatear_moneda,
)
from app.pdf.fotos_pdf import imagenes_de_consultorios, tabla_fotos
from app.repositorio.registro import obtener_repositorio

_ES_ACTIVO = ("R", "A", "B", "E")

_DESCRIPCION_COLOR = {
    VERDE: "Cobertura directa: un solo consultorio cubre todo el bloque pedido.",
    AMARILLO: "Requiere combinar más de un consultorio, todos dentro de la misma unidad.",
    NARANJA: "Requiere combinar consultorios de distintas unidades, dentro del mismo edificio.",
}

_NOMBRES_CARACTERISTICA = {"apto_camilla": "apto camilla", "ventana": "con ventana", "sillones": "con sillones"}


def _categoria_es_activa(profesional: sqlite3.Row) -> bool:
    return profesional["CategoriaProfesional"] in _ES_ACTIVO


def _nombre_completo(profesional: sqlite3.Row) -> str:
    tratamiento = profesional["Tratamiento"] or ""
    nombre = profesional["NombrePila"] or ""
    apellido = profesional["Apellido"]
    return " ".join(p for p in (tratamiento, nombre, apellido) if p)


def _nombres_edificio(conn: sqlite3.Connection, ids_edificio: list[int]) -> list[str]:
    if not ids_edificio:
        return []
    placeholders = ", ".join("?" for _ in ids_edificio)
    filas = conn.execute(f"SELECT Nombre FROM Edificio WHERE IdEdificio IN ({placeholders})", ids_edificio).fetchall()
    return [f["Nombre"] for f in filas]


def _nombres_unidad(conn: sqlite3.Connection, ids_unidad: list[int]) -> list[str]:
    if not ids_unidad:
        return []
    placeholders = ", ".join("?" for _ in ids_unidad)
    filas = conn.execute(f"SELECT Departamento FROM Unidad WHERE IdUnidad IN ({placeholders})", ids_unidad).fetchall()
    return [f["Departamento"] for f in filas]


def _texto_criterios_globales(conn: sqlite3.Connection, globales: CriteriosGlobales) -> list:
    style = estilo_texto(9)
    tipo_texto = "Horarios regulares" if globales.tipo_busqueda == TIPO_REGULAR else "Horas aisladas"
    nombres_ed = _nombres_edificio(conn, globales.ids_edificio)
    nombres_un = _nombres_unidad(conn, globales.ids_unidad) if globales.ids_unidad else []
    return [
        Paragraph(f"<b>Tipo de búsqueda:</b> {tipo_texto}", style),
        Paragraph(f"<b>Localidad:</b> {globales.localidad or '—'}", style),
        Paragraph(f"<b>Edificios:</b> {', '.join(nombres_ed) or 'todos'}", style),
        Paragraph(f"<b>Unidades:</b> {', '.join(nombres_un) or 'todas'}", style),
        Paragraph(
            f"<b>Consultorios:</b> {len(globales.ids_consultorio) if globales.ids_consultorio else 'todos'}"
            + (" seleccionados" if globales.ids_consultorio else ""),
            style,
        ),
    ]


def _texto_criterios_busqueda(busqueda: Busqueda) -> list:
    style = estilo_texto(9)
    story = [
        Paragraph(f"<b>Fecha inicial:</b> {fecha_larga(busqueda.fecha_desde)}", style),
        Paragraph(f"<b>Fecha final:</b> {fecha_larga(busqueda.fecha_hasta) if busqueda.fecha_hasta else 'indefinida'}", style),
        Paragraph(f"<b>Días solicitados:</b> {', '.join(busqueda.dias)}", style),
    ]
    desde, hasta = hora_fmt(busqueda.hora_desde)[:-2], hora_fmt(busqueda.hora_hasta)
    if busqueda.cantidad_horas_minimas:
        texto_horario = f"{busqueda.cantidad_horas_minimas:g}hs dentro del rango de {desde} a {hasta} (no hace falta que sea el rango completo)"
    else:
        texto_horario = f"{desde} a {hasta}"
    story.append(Paragraph(f"<b>Horario:</b> {texto_horario}", style))
    texto_combinar = "admite combinar consultorios (siempre dentro del mismo edificio)" if busqueda.combinar_consultorios else "un solo consultorio, sin combinar"
    story.append(Paragraph(f"<b>Combinación de consultorios:</b> {texto_combinar}", style))

    caracteristicas = [
        etiqueta for clave, etiqueta in _NOMBRES_CARACTERISTICA.items() if getattr(busqueda, clave)
    ]
    if busqueda.tamano:
        caracteristicas.append(f"tamaño {busqueda.tamano}")
    if caracteristicas:
        story.append(Paragraph(f"<b>Características del consultorio:</b> {', '.join(caracteristicas)}", style))
    if busqueda.valor_maximo_hora is not None:
        story.append(Paragraph(f"<b>Valor máximo por hora regular:</b> {formatear_moneda(busqueda.valor_maximo_hora)}", style))
    if busqueda.combinacion_con_siguiente:
        texto = (
            "tienen que darse las dos búsquedas juntas" if busqueda.combinacion_con_siguiente == "Y"
            else "alcanza con que se dé alguna de las dos búsquedas"
        )
        story.append(Paragraph(f"<b>Combinación con la búsqueda siguiente:</b> {texto}", style))
    return story


def _etiqueta_dia(dia_semana: str, fecha: str | None) -> str:
    return f"{dia_semana} {fecha_larga(fecha)}" if fecha else dia_semana


def _texto_coincidencias(resultado: ResultadoBusqueda, consultorios: dict, anonimizar: bool) -> list:
    style = estilo_texto(9)
    if not resultado.alternativas:
        return [Paragraph("Sin disponibilidad para esta búsqueda con los filtros solicitados.", style)]

    story = []
    for indice, alt in enumerate(resultado.alternativas):
        if indice > 0:
            story.append(Spacer(1, 6))
        story.append(Paragraph(f"<i>{_etiqueta_dia(alt.dia_semana, alt.fecha)}: {_DESCRIPCION_COLOR.get(alt.color, '')}</i>", style))
        if len(alt.tramos) == 1:
            t = alt.tramos[0]
            c = consultorios.get(t.id_consultorio)
            if c is None:
                continue
            unidad = f"Unidad {c['IdUnidad']}" if anonimizar else c["Departamento"]
            story.append(Paragraph(
                f"* de {hora_fmt(t.hora_inicio)[:-2]} a {hora_fmt(t.hora_fin)} — "
                f"Consultorio {c['NumeroConsultorio']} - {unidad} - {c['NombreEdificio']}",
                style,
            ))
        else:
            story.append(Paragraph("* Combinación de consultorios:", style))
            for t in alt.tramos:
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


def _consultorios_ordenados(conn: sqlite3.Connection, consultorios: dict, anonimizar: bool) -> list[sqlite3.Row]:
    numeros_por_edificio: dict[int, dict[int, int]] = {}
    if anonimizar:
        for id_edificio in {c["IdEdificio"] for c in consultorios.values()}:
            numeros_por_edificio[id_edificio] = numero_unidad_en_edificio(conn, id_edificio)

    def clave(c: sqlite3.Row):
        if anonimizar:
            return (c["IdEdificio"], numeros_por_edificio[c["IdEdificio"]].get(c["IdUnidad"], 0), c["NumeroConsultorio"])
        return (c["IdEdificio"], clave_orden_unidad(c["Departamento"]), c["NumeroConsultorio"])

    return sorted(consultorios.values(), key=clave)


def _pie_foto(imagen: sqlite3.Row, mostrar_edificio: bool, anonimizar: bool, decimales: int) -> str:
    """Edificio (si hay más de uno) - Unidad - Consultorio: Valor/hora — ni
    apto camilla ni el valor se repiten en ningún otro lado, ese detalle
    ya se desprende de "Criterios de búsqueda específicos"."""
    unidad = f"Unidad {imagen['IdUnidadConsultorio']}" if anonimizar else imagen["Departamento"]
    partes = ([imagen["NombreEdificio"]] if mostrar_edificio else []) + [unidad, f"Consultorio {imagen['NumeroConsultorio']}"]
    valor = formatear_moneda(imagen["ValorHoraRegularActual"], decimales)
    return f"{' - '.join(partes)}: {valor}/hora"


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
            story.append(encabezado(3, f"Edificio {del_edificio[0]['NombreEdificio']}", ancho))
            story.append(Spacer(1, 6))
        imagenes_ed = [img for c in del_edificio for img in imagenes_por_consultorio.get(c["IdConsultorio"], [])]
        story.extend(tabla_fotos(
            imagenes_ed, ancho, pie_personalizado=lambda img: _pie_foto(img, multi, anonimizar, decimales),
        ))
        story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Los valores detallados corresponden a los vigentes a este mes en curso, y a los mismos luego se le "
        "aplican los descuentos en base a la cantidad de horas regulares que se tenga reservadas.",
        estilo_texto(8, italica=True),
    ))
    return story


def generar_pdf_oferta_busqueda(
    conn: sqlite3.Connection, directorio: str, id_profesional: int, globales: CriteriosGlobales,
    busquedas: list[Busqueda],
) -> str:
    """Genera "Oferta consultorios.pdf" a partir de una búsqueda ad-hoc (no
    se persiste nada — a diferencia de Lista de espera) y devuelve la ruta
    completa. `busquedas` es la lista de franjas de la búsqueda global,
    todas del mismo `globales.tipo_busqueda`."""
    if not busquedas:
        raise ValueError("La búsqueda necesita al menos una franja")

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    anonimizar = not _categoria_es_activa(profesional)
    decimales = decimales_configurados(conn)

    resultados = [resolver_busqueda(conn, globales, b) for b in busquedas]
    ids_consultorio = sorted({
        t.id_consultorio for r in resultados for alt in r.alternativas for t in alt.tramos
    })
    consultorios = _mapa_consultorios_basico(conn, ids_consultorio)
    imagenes = imagenes_de_consultorios(conn, ids_consultorio)

    altura = (
        6 * cm + 3 * cm + len(busquedas) * 6 * cm + len(ids_consultorio) * 2 * 0.5 * cm
        + (len(imagenes) // 2 + 1) * 7 * cm + 3 * cm
    ) * 1.2

    def _construir_story(ancho: float) -> list:
        story = list(encabezado_espacio(conn, ancho))

        story.append(encabezado(1, f"Búsqueda solicitada por {_nombre_completo(profesional)}", ancho))
        story.append(Spacer(1, 8))
        story.append(encabezado(2, "Criterios de búsqueda generales", ancho))
        story.append(Spacer(1, 6))
        story.extend(_texto_criterios_globales(conn, globales))
        story.append(Spacer(1, 10))

        for i, (busqueda, resultado) in enumerate(zip(busquedas, resultados)):
            story.append(encabezado(2, f"Búsqueda {i + 1}", ancho))
            story.append(Spacer(1, 6))
            story.append(encabezado(3, "Criterios de búsqueda específicos", ancho))
            story.append(Spacer(1, 4))
            story.extend(_texto_criterios_busqueda(busqueda))
            story.append(Spacer(1, 6))
            story.append(encabezado(3, "Coincidencias de la búsqueda", ancho))
            story.append(Spacer(1, 4))
            story.extend(_texto_coincidencias(resultado, consultorios, anonimizar))
            story.append(Spacer(1, 10))

        story.append(encabezado(2, "Fotos de los consultorios que intervienen en las búsquedas", ancho))
        story.append(Spacer(1, 8))
        story.extend(_bloque_consultorios_intervinientes(conn, consultorios, imagenes, anonimizar, ancho, decimales))
        return story

    ruta = os.path.join(directorio, "Oferta consultorios.pdf")
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta
