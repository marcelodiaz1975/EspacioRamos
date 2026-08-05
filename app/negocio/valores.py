"""Cálculo de valores compartido por vacaciones y licencias (Etapa 3).

El "valor semanal" de un profesional es lo que paga por semana por sus
reservas regulares vigentes, tomando el valor actual de cada consultorio.
"""
from __future__ import annotations

import sqlite3
from datetime import date


def calcular_valor_semanal_regular(
    conn: sqlite3.Connection, id_profesional: int, fecha_referencia: str | None = None,
) -> float:
    fecha_referencia = fecha_referencia or date.today().isoformat()
    filas = conn.execute(
        """
        SELECT rr.HoraInicio, rr.HoraFin, c.ValorHoraRegularActual
        FROM ReservaRegular rr
        JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio
        WHERE rr.IdProfesional = ?
          AND rr.VigenciaInicio <= ?
          AND (rr.VigenciaFin IS NULL OR rr.VigenciaFin >= ?)
        """,
        (id_profesional, fecha_referencia, fecha_referencia),
    ).fetchall()
    return sum((f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"] for f in filas)
