"""Sección de fotos compartida por los PDFs de Propuesta, Disponibilidad y
Oferta de consultorios (secciones 4.3/4.4/4.6): 2 fotos por fila, con
✔ Apto camilla debajo de cada una cuando corresponde. Si `RutaArchivo` no
existe en disco (fotos no cargadas todavía), se muestra un recuadro con la
descripción en vez de fallar — el documento se sigue generando igual."""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from app.pdf.estilos import FUENTE, estilo_texto

ALTO_FOTO = 6 * cm


def imagenes_de_consultorios(conn: sqlite3.Connection, ids_consultorio: list[int]) -> list[sqlite3.Row]:
    if not ids_consultorio:
        return []
    placeholders = ", ".join("?" for _ in ids_consultorio)
    return conn.execute(
        f"""
        SELECT i.*, c.NumeroConsultorio, c.AptoCamilla, u.IdUnidad AS IdUnidadConsultorio,
               u.Departamento, e.Nombre AS NombreEdificio
        FROM Imagen i
        JOIN Consultorio c ON c.IdConsultorio = i.IdConsultorio
        JOIN Unidad u ON u.IdUnidad = c.IdUnidad
        JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE i.IdConsultorio IN ({placeholders}) AND i.Activo = 1
        ORDER BY i.IdConsultorio, i.NumeroOrden
        """,
        ids_consultorio,
    ).fetchall()


def _celda_foto(imagen: sqlite3.Row, ancho_celda: float, mostrar_apto_camilla: bool, anonimizar_unidad: bool) -> list:
    contenido = []
    ruta = imagen["RutaArchivo"]
    if ruta and os.path.isfile(ruta):
        try:
            img = Image(ruta, width=ancho_celda, height=ALTO_FOTO, kind="proportional")
            contenido.append(img)
        except Exception:
            contenido.append(Paragraph(f"(no se pudo leer la imagen: {imagen['Descripcion'] or ruta})", estilo_texto(8)))
    else:
        contenido.append(Paragraph(
            f"[Foto no disponible — {imagen['Descripcion'] or 'consultorio ' + str(imagen['NumeroConsultorio'])}]",
            estilo_texto(8),
        ))
    unidad = f"Unidad {imagen['IdUnidadConsultorio']}" if anonimizar_unidad else imagen["Departamento"]
    pie = f"Consultorio {imagen['NumeroConsultorio']} - {unidad} - {imagen['NombreEdificio']}"
    if mostrar_apto_camilla and imagen["AptoCamilla"]:
        pie += " ✔ Apto camilla"
    contenido.append(Paragraph(pie, estilo_texto(8, negrita=True)))
    return contenido


def tabla_fotos(
    imagenes: list[sqlite3.Row], ancho: float, mostrar_apto_camilla: bool = True, anonimizar_unidad: bool = False,
) -> list:
    """2 fotos por fila (sección 4.3/4.4/4.6)."""
    if not imagenes:
        return [Paragraph("Sin fotos cargadas.", estilo_texto(9))]

    ancho_celda = ancho / 2 - 0.3 * cm
    filas = []
    for i in range(0, len(imagenes), 2):
        par = imagenes[i:i + 2]
        fila = [_celda_foto(par[0], ancho_celda, mostrar_apto_camilla, anonimizar_unidad)]
        fila.append(_celda_foto(par[1], ancho_celda, mostrar_apto_camilla, anonimizar_unidad) if len(par) > 1 else "")
        filas.append(fila)

    tabla = Table(filas, colWidths=[ancho / 2, ancho / 2])
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FUENTE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return [tabla, Spacer(1, 4)]
