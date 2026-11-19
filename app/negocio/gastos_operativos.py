"""Gastos operativos (sección 3.25)."""
from __future__ import annotations

import sqlite3

from app.repositorio.registro import obtener_repositorio


ALCANCES_GASTO = ("Espacio general", "Localidad", "Edificio", "Unidad", "Consultorio")


def sanear_alcance(valores: dict) -> dict:
    """Un gasto solo puede estar asociado a UN nivel (Espacio general,
    Localidad, Edificio, Unidad o Consultorio — Consultorio y Localidad
    sumados a pedido de la clienta en rondas separadas) — fuerza a None
    el/los campo(s) que no corresponden al Alcance elegido, para que
    nunca quede un IdLocalidad/IdEdificio/IdUnidad/IdConsultorio
    "colgado" de un gasto que en realidad es de otro nivel (o general).
    Se llama tanto desde el diálogo de carga manual (`balance.
    _DialogoGasto`) como, en un futuro módulo extendido, desde la
    importación automática — cualquier vía de carga tiene que pasar por
    acá antes de guardar."""
    alcance = valores.get("Alcance")
    if alcance == "Localidad":
        valores["IdEdificio"] = None
        valores["IdUnidad"] = None
        valores["IdConsultorio"] = None
    elif alcance == "Edificio":
        valores["IdLocalidad"] = None
        valores["IdUnidad"] = None
        valores["IdConsultorio"] = None
    elif alcance == "Unidad":
        valores["IdLocalidad"] = None
        valores["IdEdificio"] = None
        valores["IdConsultorio"] = None
    elif alcance == "Consultorio":
        valores["IdLocalidad"] = None
        valores["IdEdificio"] = None
        valores["IdUnidad"] = None
    else:
        valores["IdLocalidad"] = None
        valores["IdEdificio"] = None
        valores["IdUnidad"] = None
        valores["IdConsultorio"] = None
    return valores


def texto_afectacion_gasto(conn: sqlite3.Connection, gasto: sqlite3.Row) -> str:
    """Texto legible de la Afectación de un gasto, para la tabla/
    filtros del panel de "Gastos" (`app.gui.pantallas.balance`) — mismo
    criterio que `app.negocio.control_pagos.texto_afectacion`, pero
    sobre los 5 niveles propios de `ALCANCES_GASTO`."""
    alcance = gasto["Alcance"]
    if alcance == "Localidad":
        if gasto["IdLocalidad"] is None:
            return "Sin localidad"
        fila = obtener_repositorio(conn, "Localidad").obtener(gasto["IdLocalidad"])
        return fila["Localidad"] if fila else "Localidad (eliminada)"
    if alcance == "Edificio":
        fila = obtener_repositorio(conn, "Edificio").obtener(gasto["IdEdificio"])
        return fila["Nombre"] if fila else "Edificio (eliminado)"
    if alcance == "Unidad":
        fila = conn.execute(
            "SELECT u.Departamento, e.Nombre AS NombreEdificio FROM Unidad u "
            "JOIN Edificio e ON e.IdEdificio = u.IdEdificio WHERE u.IdUnidad = ?",
            (gasto["IdUnidad"],),
        ).fetchone()
        return f"{fila['NombreEdificio']} - {fila['Departamento']}" if fila else "Unidad (eliminada)"
    if alcance == "Consultorio":
        fila = conn.execute(
            "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS NombreEdificio FROM Consultorio c "
            "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "WHERE c.IdConsultorio = ?",
            (gasto["IdConsultorio"],),
        ).fetchone()
        return (
            f"{fila['NombreEdificio']} - {fila['Departamento']} - Consultorio {fila['NumeroConsultorio']}"
            if fila else "Consultorio (eliminado)"
        )
    return "Espacio general"


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
