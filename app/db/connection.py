"""Conexión a la base de datos SQLite del Sistema Espacio Ramos."""
import sqlite3
import sys
from pathlib import Path


def _raiz_proyecto() -> Path:
    """Corriendo desde código fuente: la raíz del repo (tres niveles
    arriba de este archivo). Empaquetado con PyInstaller (`sys.frozen`):
    __file__ apunta adentro de la carpeta temporal de extracción
    (_MEIPASS), que se borra al cerrar el programa — la base de datos
    tiene que vivir al lado del .exe, no ahí, para no perderla en cada
    reinicio."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


DB_PATH_DEFAULT = _raiz_proyecto() / "data" / "espacio_ramos.db"


def get_connection(db_path: Path | str = DB_PATH_DEFAULT) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
