"""Resumen rápido de un profesional para el cuadro de "datos
complementarios" del alta de reserva regular (F16, hallazgo moderado
19): horas semanales reservadas, descuento por volumen vigente y cupo
de vacaciones disponible en el año en curso. Reusa los mismos cálculos
que ya usan el esquema de descuentos y las vacaciones, para que lo que
se ve acá coincida con lo que después se factura."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.negocio.dias import fecha_actual
from app.negocio.liquidaciones import ids_consolidados
from app.negocio.vacaciones import cupo_restante_actual
from app.negocio.valores import horas_semanales_vigentes, obtener_porcentaje_descuento


@dataclass
class ResumenProfesional:
    horas_semanales: float
    porcentaje_descuento: float
    porcentaje_vacaciones_disponible: float


def calcular_resumen_profesional(conn: sqlite3.Connection, id_profesional: int | None) -> ResumenProfesional | None:
    """`None` cuando no hay profesional elegido — no hay nada que resumir."""
    if id_profesional is None:
        return None
    fecha_referencia = fecha_actual(conn).isoformat()
    horas = horas_semanales_vigentes(conn, ids_consolidados(conn, id_profesional), fecha_referencia)
    return ResumenProfesional(
        horas_semanales=horas,
        porcentaje_descuento=obtener_porcentaje_descuento(conn, horas),
        porcentaje_vacaciones_disponible=cupo_restante_actual(conn, id_profesional, fecha_referencia),
    )
