"""Gastos operativos (sección 3.25)."""
from __future__ import annotations

import sqlite3

from app.repositorio.registro import obtener_repositorio


def gasto_en_conflicto(
    conn: sqlite3.Connection, *, periodo: str | None, concepto: str | None, origen: str | None,
    id_gasto_actual: int | None = None,
) -> sqlite3.Row | None:
    """Sección 3.25: "Si existe valor para mismo concepto y período de
    otro origen: obliga a elegir entre uno u otro." Devuelve el registro
    existente en conflicto (mismo Periodo+Concepto, Origen distinto), o
    None si no hay ninguno. `id_gasto_actual` excluye el propio registro
    al editar, para no marcarlo en conflicto consigo mismo."""
    if not periodo or not concepto or not origen:
        return None
    candidatos = obtener_repositorio(conn, "GastoOperativo").listar(Periodo=periodo, Concepto=concepto)
    for g in candidatos:
        if g["Origen"] and g["Origen"] != origen and g["IdGasto"] != id_gasto_actual:
            return g
    return None
