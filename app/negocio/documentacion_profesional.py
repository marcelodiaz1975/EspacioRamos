"""Documentación de profesionales: archivos sueltos (PDF o imagen — DNI,
matrícula, contratos, lo que haga falta) guardados en Profesionales/
{IdCodigo}/Documentación bajo la carpeta base. A diferencia de las fotos
de consultorios (`app.negocio.imagenes`), no tienen fila propia en la
base — es pura gestión de archivos: se listan directamente los que hay
en la carpeta, sin duplicar esa información en una tabla."""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app.negocio.archivos_generados import carpeta_documentacion_profesional, destino_sin_colision

EXTENSIONES_VALIDAS = (".pdf", ".jpg", ".jpeg", ".png")


def listar_documentos(conn: sqlite3.Connection, codigo: str) -> list[Path]:
    carpeta = carpeta_documentacion_profesional(conn, codigo)
    return sorted((f for f in carpeta.iterdir() if f.is_file()), key=lambda f: f.name.lower())


def agregar_documento(conn: sqlite3.Connection, codigo: str, ruta_origen: str) -> Path:
    """Copia `ruta_origen` a Profesionales/{codigo}/Documentación y
    devuelve la ruta final (con sufijo " (2)" etc. si ya había un archivo
    con ese nombre)."""
    origen = Path(ruta_origen)
    if not origen.is_file():
        raise ValueError(f"No se encuentra el archivo: {ruta_origen}")
    if origen.suffix.lower() not in EXTENSIONES_VALIDAS:
        raise ValueError("Formato no soportado: usá PDF, JPG o PNG.")
    destino = destino_sin_colision(carpeta_documentacion_profesional(conn, codigo), origen.name)
    shutil.copy2(origen, destino)
    return destino


def eliminar_documento(conn: sqlite3.Connection, codigo: str, nombre_archivo: str) -> None:
    ruta = carpeta_documentacion_profesional(conn, codigo) / nombre_archivo
    if ruta.is_file():
        ruta.unlink()
