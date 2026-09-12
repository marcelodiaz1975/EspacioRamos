"""PDFs de placas (FA6, sección 3.8): dos documentos independientes.

`generar_pdf_placas` — una fila por posición activa del tablero de cada
unidad, con el nombre grabado: referencia de cómo queda el tablero
completo, se regenera solo en el avance de mes y con nombre de archivo
fijo ("Placas {NombreEspacio}[ - Localidad].pdf", siempre se
sobrescribe, sin historial — igual que Propuesta y Disponibilidad).

`generar_pdf_placas_seleccionadas` — a pedido de la clienta: una hoja
para cortar e imprimir con SOLO las placas que se van juntando en el
buscador de la pantalla de Placas (independiente de qué posición del
tablero ocupen, o si todavía no ocupan ninguna). A diferencia del resto
de los PDFs del sistema (Etapa 7: "página única continua"), éste SÍ
pagina de verdad — se imprime tal cual sobre la plancha física, una
hoja A4 por página — así que arma el documento con `crear_documento` +
`doc.build` en vez de `construir_sin_saltos`."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.negocio.placas import nombre_estandar
from app.pdf.edificios_pdf import edificios_incluidos, sufijo_localidad
from app.pdf.estilos import FUENTE, FUENTE_NEGRITA, construir_sin_saltos, crear_documento, encabezado, encabezado_espacio, estilo_texto
from app.repositorio.registro import obtener_repositorio


def _placas_por_unidad(conn: sqlite3.Connection, ids_edificio: list[int]) -> dict[int, list[sqlite3.Row]]:
    if not ids_edificio:
        return {}
    placeholders = ", ".join("?" for _ in ids_edificio)
    filas = conn.execute(
        f"""
        SELECT p.*, u.Departamento, u.IdEdificio, e.Nombre AS NombreEdificio
        FROM Placa p
        JOIN Unidad u ON u.IdUnidad = p.IdUnidad
        JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE p.Activo = 1 AND u.IdEdificio IN ({placeholders})
        ORDER BY e.Nombre, u.Departamento
        """,
        ids_edificio,
    ).fetchall()
    por_unidad: dict[int, list[sqlite3.Row]] = {}
    for f in filas:
        por_unidad.setdefault(f["IdUnidad"], []).append(f)
    for placas in por_unidad.values():
        placas.sort(key=lambda p: (p["PosicionTablero"] is None, p["PosicionTablero"] or 0))
    return por_unidad


def _tabla_placas(placas: list[sqlite3.Row], ancho: float) -> Table:
    encabezados = [Paragraph("<b>Posición</b>", estilo_texto(9)), Paragraph("<b>Nombre grabado</b>", estilo_texto(9))]
    filas = [encabezados]
    for p in placas:
        posicion = str(p["PosicionTablero"]) if p["PosicionTablero"] is not None else "—"
        nombre = p["NombreGrabado"] or "(sin nombre cargado)"
        if p["EsPersonalizada"]:
            nombre += " (personalizada)"
        filas.append([Paragraph(posicion, estilo_texto(9)), Paragraph(nombre, estilo_texto(9))])

    tabla = Table(filas, colWidths=[ancho * 0.2, ancho * 0.8])
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FUENTE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, "#DDDDDD"),
    ]))
    return tabla


def generar_pdf_placas(conn: sqlite3.Connection, directorio: str, ids_edificio: list[int] | None = None) -> str:
    """Genera el PDF de impresión de placas y devuelve la ruta completa.
    Sin `ids_edificio` incluye todos los edificios del sistema. Unidades
    sin ninguna placa activa no aparecen."""
    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"

    edificios = edificios_incluidos(conn, ids_edificio)
    sufijo = sufijo_localidad(conn, edificios)
    nombre_archivo = f"Placas {nombre_espacio}{sufijo}.pdf"

    ids_edificio_incluidos = [e["IdEdificio"] for e in edificios]
    placas_por_unidad = _placas_por_unidad(conn, ids_edificio_incluidos)
    multi_edificio = len({p[0]["IdEdificio"] for p in placas_por_unidad.values() if p}) > 1

    n_placas = sum(len(p) for p in placas_por_unidad.values())
    altura = (6 * cm + 1.5 * cm + len(placas_por_unidad) * 1.3 * cm + n_placas * 0.7 * cm) * 1.2

    def _construir_story(ancho: float) -> list:
        story = list(encabezado_espacio(conn, ancho))
        story.append(encabezado(1, "Impresión de placas", ancho))
        story.append(Spacer(1, 8))

        if not placas_por_unidad:
            story.append(Paragraph("No hay placas activas cargadas.", estilo_texto(9)))
            return story

        for placas in placas_por_unidad.values():
            primera = placas[0]
            titulo = (
                f"{primera['NombreEdificio']} - {primera['Departamento']}" if multi_edificio
                else primera["Departamento"]
            )
            story.append(encabezado(2, titulo, ancho))
            story.append(Spacer(1, 4))
            story.append(_tabla_placas(placas, ancho))
            story.append(Spacer(1, 10))
        return story

    ruta = os.path.join(directorio, nombre_archivo)
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta


_COLUMNAS_GRILLA = 2
_ALTO_CELDA = 2.3 * cm  # 2 columnas x 11 filas = 22 por hoja A4, como la plantilla de Excel que usaba la clienta antes


def _tabla_grilla_placas(nombres: list[str], ancho: float) -> Table:
    estilo_celda = ParagraphStyle(
        "placa", fontName=FUENTE_NEGRITA, fontSize=13, alignment=TA_CENTER, leading=16,
    )
    celdas = [Paragraph(nombre, estilo_celda) for nombre in nombres]
    faltantes = (-len(celdas)) % _COLUMNAS_GRILLA
    celdas.extend([Paragraph("", estilo_celda)] * faltantes)

    filas = [celdas[i:i + _COLUMNAS_GRILLA] for i in range(0, len(celdas), _COLUMNAS_GRILLA)]
    ancho_columna = ancho / _COLUMNAS_GRILLA
    tabla = Table(filas, colWidths=[ancho_columna] * _COLUMNAS_GRILLA, rowHeights=[_ALTO_CELDA] * len(filas))
    tabla.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return tabla


def generar_pdf_placas_seleccionadas(conn: sqlite3.Connection, directorio: str, ids_profesional: list[int]) -> str:
    """Hoja para cortar e imprimir con las placas seleccionadas puntualmente
    (buscador de profesional en la pantalla de Placas) — 2 columnas x 11
    filas por hoja A4, sin importar si el profesional ya tiene o no una
    posición asignada en algún tablero. El nombre de archivo lleva fecha
    y hora porque, a diferencia de Propuesta/Disponibilidad/el PDF de
    referencia de Placas, cada tanda de impresión es un documento
    distinto que no reemplaza al anterior."""
    if not ids_profesional:
        raise ValueError("No hay ninguna placa seleccionada para imprimir.")
    repo_profesional = obtener_repositorio(conn, "Profesional")
    nombres = []
    for id_profesional in ids_profesional:
        profesional = repo_profesional.obtener(id_profesional)
        if profesional is not None:
            nombres.append(nombre_estandar(profesional))
    if not nombres:
        raise ValueError("Ninguno de los profesionales seleccionados existe.")

    nombre_archivo = datetime.now().strftime("Placas para imprimir %Y-%m-%d %Hh%M.pdf")
    ruta = os.path.join(directorio, nombre_archivo)
    doc, ancho = crear_documento(ruta)
    doc.build([_tabla_grilla_placas(nombres, ancho)])
    return ruta
