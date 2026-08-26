"""Inicialización del esquema de base de datos."""
import sqlite3
from pathlib import Path

from app.db.connection import DB_PATH_DEFAULT, get_connection
from app.db.migraciones import aplicar_migraciones

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def init_database(db_path: Path | str = DB_PATH_DEFAULT) -> sqlite3.Connection:
    """Crea (si no existen) todas las tablas del modelo de datos, aplica
    las migraciones de columnas pendientes sobre una base ya existente
    y devuelve una conexión abierta a la base."""
    conn = get_connection(db_path)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.commit()
    aplicar_migraciones(conn)
    return conn
