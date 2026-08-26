"""Resumen rápido de un profesional para el cuadro de "datos
complementarios" del alta de reserva regular y de reserva aislada (F16,
hallazgo moderado 19): horas regulares semanales, descuento por volumen
vigente, cupo de vacaciones disponible en el año en curso y horas
aisladas confirmadas en el período actual. Reusa los mismos cálculos
que ya usan el esquema de descuentos, las vacaciones y la liquidación,
para que lo que se ve acá coincida con lo que después se factura."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.liquidaciones import ids_consolidados
from app.negocio.vacaciones import cupo_restante_actual
from app.negocio.valores import horas_semanales_vigentes, obtener_porcentaje_descuento


@dataclass
class ResumenProfesional:
    horas_semanales: float
    porcentaje_descuento: float
    porcentaje_vacaciones_disponible: float
    horas_aisladas_mensuales: float = 0.0


def _horas_aisladas_del_periodo(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> float:
    filas = conn.execute(
        "SELECT HoraInicio, HoraFin FROM ReservaAislada "
        "WHERE IdProfesional = ? AND Estado = 'Confirmada' AND Fecha LIKE ?",
        (id_profesional, f"{periodo}-%"),
    ).fetchall()
    return sum(f["HoraFin"] - f["HoraInicio"] for f in filas)


def calcular_resumen_profesional(conn: sqlite3.Connection, id_profesional: int | None) -> ResumenProfesional | None:
    """`None` cuando no hay profesional elegido — no hay nada que resumir."""
    if id_profesional is None:
        return None
    fecha_referencia = fecha_actual(conn).isoformat()
    periodo = periodo_actual(conn)
    horas = horas_semanales_vigentes(conn, ids_consolidados(conn, id_profesional), fecha_referencia)
    return ResumenProfesional(
        horas_semanales=horas,
        porcentaje_descuento=obtener_porcentaje_descuento(conn, horas),
        porcentaje_vacaciones_disponible=cupo_restante_actual(conn, id_profesional, fecha_referencia),
        horas_aisladas_mensuales=_horas_aisladas_del_periodo(conn, id_profesional, periodo),
    )
