"""Migraciones incrementales: columnas nuevas que se agregan a tablas ya
existentes. `schema.sql` solo crea tablas con `CREATE TABLE IF NOT
EXISTS` — eso no hace nada en una base que ya existe, así que una
columna agregada ahí nunca aparece sola en una base ya en uso. Cada
entrada acá se aplica con `ALTER TABLE ... ADD COLUMN` si la columna
todavía no existe, así una base vieja se pone al día la próxima vez que
esta app la abre. Al agregar una columna nueva a una tabla existente,
sumarla tanto en `schema.sql` (para que una base nueva ya nazca con
ella) como en `_COLUMNAS_NUEVAS` acá (para que una base vieja la
reciba)."""
from __future__ import annotations

import sqlite3

# (tabla, columna, definición SQL de la columna — tipo + constraints)
_COLUMNAS_NUEVAS: list[tuple[str, str, str]] = [
    ("Ausencia", "IdReservaAislada", "INTEGER REFERENCES ReservaAislada(IdReservaAislada)"),
    ("Ausencia", "HoraInicio", "REAL"),
    ("Ausencia", "HoraFin", "REAL"),
    ("HistorialPagos", "SaldoAnterior", "REAL"),
    ("HistorialPagos", "SaldoNuevo", "REAL"),
    ("HistorialPagos", "RegistroModificado", "INTEGER NOT NULL DEFAULT 0"),
]


def aplicar_migraciones(conn: sqlite3.Connection) -> None:
    for tabla, columna, definicion in _COLUMNAS_NUEVAS:
        existe_tabla = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabla,)
        ).fetchone()
        if not existe_tabla:
            continue  # tabla nueva que todavía no existe en esta base — nada que migrarle
        columnas_existentes = {f["name"] for f in conn.execute(f"PRAGMA table_info({tabla})").fetchall()}
        if columna not in columnas_existentes:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
    conn.commit()
