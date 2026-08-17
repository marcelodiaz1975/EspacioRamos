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


def buscar_backup_mas_reciente(carpeta: Path) -> Path | None:
    """La más reciente de las subcarpetas "Backup AAAA-MM-DD HHhMM" de
    `carpeta` (orden alfabético == orden cronológico, por el formato de
    fecha usado). None si no hay ninguna."""
    if not carpeta.is_dir():
        return None
    candidatos = sorted(p for p in carpeta.iterdir() if p.is_dir() and p.name.startswith("Backup "))
    return candidatos[-1] if candidatos else None


def restaurar_backup(carpeta_backups: Path, db_path: Path) -> Path:
    """Instalación en máquina nueva (sección 2: "restauración automática
    desde Google Drive"): busca el backup más reciente dentro de
    `carpeta_backups` (la carpeta de Drive que el operador ya tiene
    sincronizada en la máquina nueva) y restaura ahí la base de datos y
    la carpeta de archivos generados. Devuelve la carpeta de backup que
    se usó."""
    origen = buscar_backup_mas_reciente(Path(carpeta_backups))
    if origen is None:
        raise ValueError(f"No se encontró ningún backup en {carpeta_backups}.")
    archivos_db = list(origen.glob("*.db"))
    if not archivos_db:
        raise ValueError(f"El backup en {origen} no tiene ningún archivo de base de datos.")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archivos_db[0], db_path)

    origen_archivos = origen / "Archivos"
    if origen_archivos.is_dir():
        from app.db.connection import get_connection

        conn_restaurada = get_connection(db_path)
        try:
            base_archivos = carpeta_base(conn_restaurada)
        finally:
            conn_restaurada.close()
        if base_archivos is not None:
            shutil.copytree(origen_archivos, base_archivos, dirs_exist_ok=True)

    return origen
