"""Ausencias (sección 3.14 del documento).

Solo tienen efecto sobre reservas regulares: liberan el consultorio para
que otro profesional pueda tomar una reserva aislada durante el período,
sin afectar la liquidación ni la grilla visual de disponibilidad.
IdConsultorio nulo significa "todos los consultorios del profesional".
"""
from __future__ import annotations

import sqlite3

from app.negocio.conflictos_aisladas import aisladas_bloqueadas_por_anulacion, mensaje_conflicto_aislada
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


def cancelar_ausencia(conn: sqlite3.Connection, id_ausencia: int) -> None:
    """Anula una ausencia (DC-04 §3.2/§3.3, aclarado en conversación):
    bloquea si ya se asignó una reserva aislada a otro profesional
    aprovechando el consultorio que esta ausencia liberaba, porque
    anularla haría chocar esa aislada con la reserva regular que vuelve a
    regir."""
    repo = obtener_repositorio(conn, "Ausencia")
    ausencia = repo.obtener(id_ausencia)
    if ausencia is None:
        raise ValueError(f"No existe la ausencia #{id_ausencia}")
    conflictos = aisladas_bloqueadas_por_anulacion(
        conn, id_profesional=ausencia["IdProfesional"], fecha_desde=ausencia["FechaDesde"],
        fecha_hasta=ausencia["FechaHasta"], id_consultorio=ausencia["IdConsultorio"],
    )
    if conflictos:
        raise ValueError(mensaje_conflicto_aislada(conflictos))
    repo.eliminar(id_ausencia)


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
