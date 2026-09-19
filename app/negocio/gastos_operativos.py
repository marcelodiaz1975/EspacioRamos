"""Gastos operativos (sección 3.25)."""
from __future__ import annotations

import sqlite3

from app.repositorio.registro import obtener_repositorio


ALCANCES_GASTO = ("Espacio general", "Edificio", "Unidad")


def sanear_alcance(valores: dict) -> dict:
    """Un gasto solo puede estar asociado a UN nivel (Espacio general,
    Edificio o Unidad, sección 3.25) — fuerza a None el/los campo(s) que
    no corresponden al Alcance elegido, para que nunca quede un
    IdEdificio o IdUnidad "colgado" de un gasto que en realidad es de
    otro nivel (o general). Se llama tanto desde el diálogo de carga
    manual (`catalogos._resolver_conflicto_gasto`) como, en un futuro
    módulo extendido, desde la importación automática — cualquier vía de
    carga tiene que pasar por acá antes de guardar."""
    alcance = valores.get("Alcance")
    if alcance == "Edificio":
        valores["IdUnidad"] = None
    elif alcance == "Unidad":
        valores["IdEdificio"] = None
    else:
        valores["IdEdificio"] = None
        valores["IdUnidad"] = None
    return valores


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
