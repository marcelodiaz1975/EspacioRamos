"""Cálculo de valores compartido por vacaciones y licencias (Etapa 3).

El "valor semanal" de un profesional es lo que paga por semana por sus
reservas regulares vigentes, ya con el descuento por volumen de horas
semanales aplicado (EsquemaDescuentos, sección 3.18).
"""
from __future__ import annotations

import sqlite3
from datetime import date


def obtener_porcentaje_descuento(conn: sqlite3.Connection, horas_semanales: float) -> float:
    """Porcentaje de descuento por volumen de horas semanales (sección 3.18)."""
    if horas_semanales <= 0:
        return 0.0
    fila = conn.execute(
        "SELECT PorcentajeDescuento FROM EsquemaDescuentos WHERE Activo = 1 "
        "AND HorasSemanalesDesde < ? AND HorasSemanalesHasta >= ? "
        "ORDER BY HorasSemanalesDesde LIMIT 1",
        (horas_semanales, horas_semanales),
    ).fetchone()
    if fila:
        return fila["PorcentajeDescuento"]
    # Supera todos los tramos definidos: se aplica el tope del tramo más alto.
    fila = conn.execute(
        "SELECT PorcentajeDescuento FROM EsquemaDescuentos WHERE Activo = 1 "
        "ORDER BY HorasSemanalesHasta DESC LIMIT 1"
    ).fetchone()
    return fila["PorcentajeDescuento"] if fila else 0.0


def _reservas_regulares_vigentes(conn: sqlite3.Connection, id_profesional: int, fecha_referencia: str):
    return conn.execute(
        """
        SELECT rr.DiaSemana, rr.HoraInicio, rr.HoraFin, c.ValorHoraRegularActual
        FROM ReservaRegular rr
        JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio
        WHERE rr.IdProfesional = ?
          AND rr.VigenciaInicio <= ?
          AND (rr.VigenciaFin IS NULL OR rr.VigenciaFin >= ?)
        """,
        (id_profesional, fecha_referencia, fecha_referencia),
    ).fetchall()


def calcular_valor_semanal_regular(
    conn: sqlite3.Connection, id_profesional: int, fecha_referencia: str | None = None,
) -> float:
    """Valor semanal vigente del profesional (lo que paga por semana por
    sus reservas regulares), con el descuento por volumen de horas ya
    aplicado."""
    fecha_referencia = fecha_referencia or date.today().isoformat()
    filas = _reservas_regulares_vigentes(conn, id_profesional, fecha_referencia)
    horas_totales = sum(f["HoraFin"] - f["HoraInicio"] for f in filas)
    descuento_pct = obtener_porcentaje_descuento(conn, horas_totales)
    valor_bruto = sum((f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"] for f in filas)
    return valor_bruto * (1 - descuento_pct / 100)
