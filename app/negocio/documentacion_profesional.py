"""Documentación de profesionales: archivos sueltos (PDF o imagen — DNI,
matrícula, contratos, lo que haga falta) guardados en Profesionales/
{IdCodigo}/Documentación bajo la carpeta base. A diferencia de las fotos
de consultorios (`app.negocio.imagenes`), no tienen fila propia en la
base — es pura gestión de archivos: se listan directamente los que hay
en la carpeta, sin duplicar esa información en una tabla.

Categoría (`CATEGORIAS_DOCUMENTACION_PROFESIONAL`): lista cerrada que se
elige al agregar un archivo (cuadro "Agregar archivo" de
`app.gui.pantallas.profesionales`) — el archivo se guarda con el nombre
de la categoría (o "{categoría} - {detalle}" para "Otras imágenes"/
"Otros documentos", que no tienen nombre propio y piden un detalle
libre), no con el nombre original. Reusa las mismas dos categorías
"libres" que `app.negocio.imagenes` (mismo criterio, texto idéntico)."""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app.negocio.archivos_generados import carpeta_documentacion_profesional, destino_sin_colision
from app.negocio.imagenes import CATEGORIA_OTRAS_IMAGENES, CATEGORIA_OTROS_DOCUMENTOS

EXTENSIONES_VALIDAS = (".pdf", ".jpg", ".jpeg", ".png")

CATEGORIAS_DOCUMENTACION_PROFESIONAL = [
    "DNI completo", "DNI frente", "DNI dorso", "Título", "Curso", "Capacitación",
    "Seguro mala praxis", "Matrícula nacional", "Matrícula provincial",
    CATEGORIA_OTRAS_IMAGENES, CATEGORIA_OTROS_DOCUMENTOS,
]


def _nombre_para_categoria(categoria: str, etiqueta_libre: str | None) -> str:
    if categoria in (CATEGORIA_OTRAS_IMAGENES, CATEGORIA_OTROS_DOCUMENTOS) and etiqueta_libre:
        return f"{categoria} - {etiqueta_libre}"
    return categoria


def listar_documentos(conn: sqlite3.Connection, codigo: str) -> list[Path]:
    carpeta = carpeta_documentacion_profesional(conn, codigo)
    return sorted((f for f in carpeta.iterdir() if f.is_file()), key=lambda f: f.name.lower())


def agregar_documento(
    conn: sqlite3.Connection, codigo: str, ruta_origen: str, categoria: str, etiqueta_libre: str | None = None,
) -> Path:
    """Copia `ruta_origen` a Profesionales/{codigo}/Documentación con el
    nombre de la categoría elegida (con sufijo " (2)" etc. si ya había
    un archivo con ese nombre) y devuelve la ruta final."""
    origen = Path(ruta_origen)
    if not origen.is_file():
        raise ValueError(f"No se encuentra el archivo: {ruta_origen}")
    if origen.suffix.lower() not in EXTENSIONES_VALIDAS:
        raise ValueError("Formato no soportado: usá PDF, JPG o PNG.")
    if categoria in (CATEGORIA_OTRAS_IMAGENES, CATEGORIA_OTROS_DOCUMENTOS) and not (etiqueta_libre or "").strip():
        raise ValueError(f"«{categoria}» necesita un detalle propio para poder identificarlo.")
    nombre = f"{_nombre_para_categoria(categoria, etiqueta_libre)}{origen.suffix.lower()}"
    destino = destino_sin_colision(carpeta_documentacion_profesional(conn, codigo), nombre)
    shutil.copy2(origen, destino)
    return destino


def eliminar_documento(conn: sqlite3.Connection, codigo: str, nombre_archivo: str) -> None:
    ruta = carpeta_documentacion_profesional(conn, codigo) / nombre_archivo
    if ruta.is_file():
        ruta.unlink()
