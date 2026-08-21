"""Chequeo compartido por Ausencia/Vacacion/Licencia (DC-04 §3.2/§3.3,
aclarado en conversación).

Asignar una hora aislada en un consultorio libre por una ausencia,
vacación o licencia nunca hace falta validarlo: para poder cargar esa
aislada, la ausencia/vacación/licencia ya tenía que existir antes. La
situación real a cuidar es la inversa — anular o acortar una
ausencia/vacación/licencia después de que ya se asignó una aislada a otro
profesional en el consultorio que quedó libre: eso sí puede generar un
choque real entre la reserva regular (que vuelve a regir) y la aislada ya
confirmada. Por eso el chequeo va del lado de cancelar/anular, no del
lado de crear la aislada.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from app.negocio.dias import fecha_a_dia_semana


def _solapan(inicio_a: float, fin_a: float, inicio_b: float, fin_b: float) -> bool:
    return inicio_a < fin_b and inicio_b < fin_a


def aisladas_bloqueadas_por_anulacion(
    conn: sqlite3.Connection, *, id_profesional: int, fecha_desde: str, fecha_hasta: str,
    id_consultorio: int | None = None,
) -> list[sqlite3.Row]:
    """Reservas aisladas Confirmadas de OTRO profesional que caen dentro
    de [fecha_desde, fecha_hasta] en un horario y consultorio que
    `id_profesional` volvería a ocupar con su reserva regular si se anula
    la ausencia/vacación/licencia. `id_consultorio` acota la búsqueda al
    consultorio de la Ausencia puntual (None = todos los suyos, como
    Vacacion/Licencia o una Ausencia sin consultorio específico)."""
    sql = "SELECT * FROM ReservaRegular WHERE IdProfesional = ?"
    parametros: list = [id_profesional]
    if id_consultorio is not None:
        sql += " AND IdConsultorio = ?"
        parametros.append(id_consultorio)
    regulares = conn.execute(sql, parametros).fetchall()

    conflictos: list[sqlite3.Row] = []
    for regular in regulares:
        aisladas = conn.execute(
            "SELECT * FROM ReservaAislada WHERE IdConsultorio = ? AND Estado = 'Confirmada' "
            "AND Fecha BETWEEN ? AND ? AND IdProfesional != ?",
            (regular["IdConsultorio"], fecha_desde, fecha_hasta, id_profesional),
        ).fetchall()
        for aislada in aisladas:
            if fecha_a_dia_semana(date.fromisoformat(aislada["Fecha"])) != regular["DiaSemana"]:
                continue
            if not _solapan(regular["HoraInicio"], regular["HoraFin"], aislada["HoraInicio"], aislada["HoraFin"]):
                continue
            conflictos.append(aislada)
    return conflictos


def mensaje_conflicto_aislada(conflictos: list[sqlite3.Row]) -> str:
    detalles = "; ".join(
        f"{a['Fecha']} {a['HoraInicio']}-{a['HoraFin']}hs (consultorio #{a['IdConsultorio']})" for a in conflictos
    )
    return (
        "No se puede anular: ya hay reserva(s) aislada(s) de otro profesional asignada(s) en ese "
        f"período aprovechando el consultorio liberado — {detalles}"
    )
