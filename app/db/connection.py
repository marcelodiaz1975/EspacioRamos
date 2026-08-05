"""Conexión a la base de datos SQLite del Sistema Espacio Ramos."""
import sqlite3
from pathlib import Path

DB_PATH_DEFAULT = Path(__file__).resolve().parent.parent.parent / "data" / "espacio_ramos.db"


def get_connection(db_path: Path | str = DB_PATH_DEFAULT) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
