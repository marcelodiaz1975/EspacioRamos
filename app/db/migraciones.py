"""Migraciones incrementales: columnas nuevas que se agregan a tablas ya
existentes, y tablas viejas que se dan de baja. `schema.sql` solo crea
tablas con `CREATE TABLE IF NOT EXISTS` — eso no hace nada en una base
que ya existe, así que una columna agregada ahí nunca aparece sola en
una base ya en uso, ni una tabla sacada de `schema.sql` desaparece
sola. Cada entrada de `_COLUMNAS_NUEVAS` se aplica con `ALTER TABLE ...
ADD COLUMN` si la columna todavía no existe, y cada entrada de
`_TABLAS_ELIMINADAS` se borra con `DROP TABLE` si la tabla todavía
está — así una base vieja se pone al día la próxima vez que esta app la
abre. Al agregar una columna nueva a una tabla existente, sumarla tanto
en `schema.sql` (para que una base nueva ya nazca con ella) como en
`_COLUMNAS_NUEVAS` acá (para que una base vieja la reciba); al sacar
una tabla entera de `schema.sql`, sumarla en `_TABLAS_ELIMINADAS`."""
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
    ("CargoEspecial", "Fecha", "TEXT"),
    ("LiquidacionEmitida", "FechaHoraGeneracion", "TEXT"),
]

# Tablas que existían en versiones anteriores y se dieron de baja del todo
# (decisión de la clienta sobre HistorialOferta: "búsqueda realizada es
# búsqueda terminada", no se guarda ningún historial de Oferta de
# consultorios).
_TABLAS_ELIMINADAS: list[str] = [
    "HistorialOferta",
]

# Consultorio.TamanoClasificacion pasó de texto libre a catálogo cerrado
# (mismos 3 valores que app.negocio.oferta_busqueda.TAMANOS_CONSULTORIO,
# duplicados acá en vez de importados para no hacer que la capa de base
# de datos dependa de la de negocio). Normaliza mayúsculas/espacios de lo
# que ya coincide y vacía cualquier otro valor viejo (ej. "Pequeño") que
# haya quedado cargado de cuando el campo era libre — así el filtro de
# tamaño de Oferta de consultorios, que compara por igualdad exacta,
# encuentra coincidencia con cualquier consultorio ya cargado.
_TAMANOS_CONSULTORIO = ["Grande", "Intermedio", "Chico"]


def _normalizar_tamanos_consultorio(conn: sqlite3.Connection) -> None:
    existe_tabla = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'Consultorio'"
    ).fetchone()
    if not existe_tabla:
        return
    for valor in _TAMANOS_CONSULTORIO:
        conn.execute(
            "UPDATE Consultorio SET TamanoClasificacion = ? "
            "WHERE TamanoClasificacion IS NOT NULL AND LOWER(TRIM(TamanoClasificacion)) = ?",
            (valor, valor.lower()),
        )
    placeholders = ", ".join("?" for _ in _TAMANOS_CONSULTORIO)
    conn.execute(
        "UPDATE Consultorio SET TamanoClasificacion = NULL "
        f"WHERE TamanoClasificacion IS NOT NULL AND TamanoClasificacion NOT IN ({placeholders})",
        _TAMANOS_CONSULTORIO,
    )


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
    for tabla in _TABLAS_ELIMINADAS:
        conn.execute(f"DROP TABLE IF EXISTS {tabla}")
    _normalizar_tamanos_consultorio(conn)
    conn.commit()
