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
    id_reserva_aislada: int | None = None, hora_inicio: float | None = None, hora_fin: float | None = None,
) -> int:
    """`id_reserva_aislada` deja vinculada la ausencia con la reserva
    aislada que la originó (F16, "Es reubicación") — opcional, en blanco
    para las que se cargan directamente desde la pantalla de Ausencias.

    `hora_inicio`/`hora_fin` acotan la ausencia a un horario puntual —
    solo tiene sentido para un único día (FechaDesde == FechaHasta); sin
    ellas (el caso de siempre), la ausencia cubre el día completo."""
    if fecha_hasta < fecha_desde:
        raise ValueError("FechaHasta debe ser posterior o igual a FechaDesde")
    if (hora_inicio is None) != (hora_fin is None):
        raise ValueError("HoraInicio y HoraFin van juntas: las dos o ninguna")
    if hora_inicio is not None:
        if fecha_desde != fecha_hasta:
            raise ValueError("El horario puntual solo se puede usar cuando la ausencia es de un único día")
        if hora_fin <= hora_inicio:
            raise ValueError("HoraFin debe ser posterior a HoraInicio")
    repo = obtener_repositorio(conn, "Ausencia")
    return repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio,
        FechaDesde=fecha_desde, FechaHasta=fecha_hasta, Motivo=motivo, Observacion=observacion,
        IdReservaAislada=id_reserva_aislada, HoraInicio=hora_inicio, HoraFin=hora_fin,
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
    hora: float | None = None,
) -> bool:
    """True si el profesional tiene una ausencia activa esa fecha que cubre
    ese consultorio (o todos, si la ausencia no especifica uno).

    Si se pasa `hora` y la ausencia encontrada tiene horario puntual
    (HoraInicio/HoraFin, solo posible en ausencias de un único día), solo
    cuenta cuando `hora` cae dentro de ese rango. Sin `hora`, o cuando la
    ausencia no tiene horario puntual (cubre el día completo), se
    comporta como siempre."""
    filas = conn.execute(
        "SELECT IdConsultorio, HoraInicio, HoraFin FROM Ausencia WHERE IdProfesional = ? "
        "AND FechaDesde <= ? AND FechaHasta >= ?",
        (id_profesional, fecha, fecha),
    ).fetchall()
    for fila in filas:
        if fila["IdConsultorio"] is not None and fila["IdConsultorio"] != id_consultorio:
            continue
        if hora is not None and fila["HoraInicio"] is not None and fila["HoraFin"] is not None:
            if not (fila["HoraInicio"] <= hora < fila["HoraFin"]):
                continue
        return True
    return False
