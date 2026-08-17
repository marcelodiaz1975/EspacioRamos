"""PDF de impresión de placas (FA6, sección 3.8): una fila por posición
activa del tablero de cada unidad, con el nombre grabado — para mandar a
fabricar o tener una referencia impresa de cómo queda el tablero.

Nombre de archivo fijo ("Placas {NombreEspacio}[ - Localidad].pdf"):
siempre se sobrescribe, sin historial de versiones — igual que Propuesta
y Disponibilidad, es un documento de trabajo del estado actual, no un
archivo por versión."""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.pdf.edificios_pdf import edificios_incluidos, sufijo_localidad
from app.pdf.estilos import FUENTE, construir_sin_saltos, encabezado, encabezado_espacio, estilo_texto


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
