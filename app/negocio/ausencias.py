"""Ausencias (sección 3.14 del documento).

Solo tienen efecto sobre reservas regulares: liberan el consultorio para
que otro profesional pueda tomar una reserva aislada durante el período,
sin afectar la liquidación ni la grilla visual de disponibilidad.
IdConsultorio nulo significa "todos los consultorios del profesional".
"""
from __future__ import annotations

import sqlite3

from app.repositorio.registro import obtener_repositorio


def crear_ausencia(
    conn: sqlite3.Connection, *, id_profesional: int, fecha_desde: str, fecha_hasta: str,
    id_consultorio: int | None = None, motivo: str | None = None, observacion: str | None = None,
) -> int:
    if fecha_hasta < fecha_desde:
        raise ValueError("FechaHasta debe ser posterior o igual a FechaDesde")
    repo = obtener_repositorio(conn, "Ausencia")
    return repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio,
        FechaDesde=fecha_desde, FechaHasta=fecha_hasta, Motivo=motivo, Observacion=observacion,
    )


def esta_ausente(
    conn: sqlite3.Connection, id_profesional: int, fecha: str, id_consultorio: int | None = None,
) -> bool:
    """True si el profesional tiene una ausencia activa esa fecha que cubre
    ese consultorio (o todos, si la ausencia no especifica uno)."""
    filas = conn.execute(
        "SELECT IdConsultorio FROM Ausencia WHERE IdProfesional = ? "
        "AND FechaDesde <= ? AND FechaHasta >= ?",
        (id_profesional, fecha, fecha),
    ).fetchall()
    for fila in filas:
        if fila["IdConsultorio"] is None or fila["IdConsultorio"] == id_consultorio:
            return True
    return False
