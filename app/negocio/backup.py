"""Backup previo (Paso 1 del avance de mes, DC-06): copia de la base de
datos y de toda la carpeta base de archivos (fotos, documentación de
profesionales, PDFs generados) antes de avanzar el mes, para poder volver
atrás si algo sale mal en el proceso.

No sube nada a Google Drive por API — no hay credenciales ni librería de
Drive en el proyecto (sección 2: "Backup automático a Google Drive").
Configuracion.CarpetaBackup se espera que sea una carpeta ya sincronizada
por el cliente de escritorio de Google Drive que el operador instala en
su máquina: el backup en sí es copiar los archivos ahí adentro, la
sincronización a la nube la hace ese cliente, no esta aplicación."""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from app.negocio.archivos_generados import carpeta_base


def carpeta_backup(conn: sqlite3.Connection) -> Path | None:
    fila = conn.execute("SELECT CarpetaBackup FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    ruta = fila["CarpetaBackup"] if fila else None
    return Path(ruta) if ruta else None


def _ruta_base_datos(conn: sqlite3.Connection) -> Path | None:
    """Ruta del archivo de la base "main" de esta conexión (vía PRAGMA
    database_list) — vacía para bases en memoria, que no hay qué copiar."""
    fila = conn.execute("PRAGMA database_list").fetchone()
    archivo = fila["file"] if fila else None
    return Path(archivo) if archivo else None


def generar_backup(conn: sqlite3.Connection, momento: datetime | None = None) -> Path:
    """Copia la base de datos (con `sqlite3.Connection.backup`, seguro
    aunque haya escrituras en curso — no es una copia cruda del archivo)
    y toda la carpeta base de archivos generados a una subcarpeta con
    fecha y hora dentro de la carpeta de backup configurada. Devuelve la
    carpeta creada."""
    destino_base = carpeta_backup(conn)
    if destino_base is None:
        raise ValueError("Configurá primero la carpeta de backup en Configuración general.")

    momento = momento or datetime.now()
    destino = destino_base / momento.strftime("Backup %Y-%m-%d %Hh%M")
    destino.mkdir(parents=True, exist_ok=True)

    ruta_db = _ruta_base_datos(conn)
    if ruta_db is not None and ruta_db.is_file():
        destino_conn = sqlite3.connect(destino / ruta_db.name)
        try:
            conn.backup(destino_conn)
        finally:
            destino_conn.close()

    base_archivos = carpeta_base(conn)
    if base_archivos is not None and base_archivos.is_dir():
        shutil.copytree(base_archivos, destino / "Archivos", dirs_exist_ok=True)

    return destino
