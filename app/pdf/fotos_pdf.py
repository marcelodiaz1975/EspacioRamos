"""Sección de fotos compartida por los PDFs de Liquidación, Propuesta,
Disponibilidad y Oferta de consultorios (secciones 4.3/4.4/4.5/4.6): 2
fotos por fila, con ✔ Apto camilla debajo de cada una cuando corresponde.
Si `RutaArchivo` no existe en disco (fotos no cargadas todavía), se
muestra un recuadro con la descripción en vez de fallar — el documento se
sigue generando igual.

Las fotos que carga el usuario no siempre vienen en la misma relación de
aspecto (fotos de celular, de cámara, recortadas a mano) — para que la
grilla de 2 columnas quede pareja se recortan al centro a 4:3 (RELACION_FOTO)
antes de insertarlas: de los costados si la foto es más ancha que 4:3, de
arriba/abajo si es más alta. El formato definitivo recomendado para sacar
fotos nuevas ya en el tamaño final es 1200x900px (4:3)."""
from __future__ import annotations

import io
import os
import sqlite3

from PIL import Image as ImagenPIL
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from app.pdf.estilos import FUENTE, estilo_texto

ALTO_FOTO = 6 * cm
RELACION_FOTO = 4 / 3


def _recortar_al_centro(ruta: str, relacion: float = RELACION_FOTO) -> io.BytesIO:
    """Recorta al centro para que la imagen quede en `relacion` (ancho/alto)
    sin deformarla. Si la foto ya viene en esa relación (el formato
    definitivo), el recorte no cambia nada."""
    imagen = ImagenPIL.open(ruta).convert("RGB")
    ancho, alto = imagen.size
    relacion_actual = ancho / alto
    if relacion_actual > relacion:
        nuevo_ancho = round(alto * relacion)
        x0 = (ancho - nuevo_ancho) // 2
        imagen = imagen.crop((x0, 0, x0 + nuevo_ancho, alto))
    elif relacion_actual < relacion:
        nuevo_alto = round(ancho / relacion)
        y0 = (alto - nuevo_alto) // 2
        imagen = imagen.crop((0, y0, ancho, y0 + nuevo_alto))
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=88)
    buffer.seek(0)
    return buffer


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
            recorte = _recortar_al_centro(ruta)
            img = Image(recorte, width=ancho_celda, height=ALTO_FOTO, kind="proportional")
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
