"""Vacaciones (sección 3.12 del documento).

Solo aplican a profesionales categoría R, B o E con reservas regulares
activas. Tienen un cupo anual configurable en semanas (Configuracion.
SemanasVacacionesMaximasPorAnio, default 2) que se resetea en el avance de
mes de enero (eso lo maneja el proceso de avance de mes, no este módulo).

Interpretación del cálculo (el documento no lo detalla en fórmula, solo
nombra los campos "congelados" a guardar):
- FraccionSemanaConsumida = días del período / 7 (puede superar 1 si el
  período dura más de una semana).
- CupoConsumidoPorcentaje / CupoRestantePorcentaje: acumulado del año en
  curso, incluyendo este registro, sobre el cupo máximo configurado.
- ValorBonificado = valor semanal vigente del profesional * fracción de
  semana consumida (la vacación se descuenta al 100%).

Si se pide una vacación que excede el cupo restante, se rechaza salvo que
se fuerce explícitamente; la alternativa sugerida es cargar el excedente
como Ausencia con motivo "Vacaciones fuera de cupo" (no genera descuento).
"""
from __future__ import annotations

import sqlite3
from datetime import date

from app.negocio.valores import calcular_valor_semanal_regular
from app.repositorio.registro import obtener_repositorio

CATEGORIAS_CON_DERECHO_A_VACACIONES = ("R", "B", "E")


class CupoVacacionesExcedidoError(Exception):
    def __init__(self, cupo_restante_porcentaje: float, fraccion_solicitada: float):
        self.cupo_restante_porcentaje = cupo_restante_porcentaje
        self.fraccion_solicitada = fraccion_solicitada
        super().__init__(
            f"La vacación solicitada ({fraccion_solicitada:.2f} semanas) supera el cupo "
            f"disponible ({cupo_restante_porcentaje:.1f}% restante). Se puede forzar, o "
            "cargar el excedente como Ausencia con motivo 'Vacaciones fuera de cupo'."
        )


def _profesional_tiene_derecho(conn: sqlite3.Connection, id_profesional: int) -> bool:
    prof = conn.execute(
        "SELECT CategoriaProfesional FROM Profesional WHERE IdProfesional = ?", (id_profesional,)
    ).fetchone()
    if prof is None or prof["CategoriaProfesional"] not in CATEGORIAS_CON_DERECHO_A_VACACIONES:
        return False
    tiene_reserva = conn.execute(
        "SELECT 1 FROM ReservaRegular WHERE IdProfesional = ? LIMIT 1", (id_profesional,)
    ).fetchone()
    return tiene_reserva is not None


def _cupo_maximo_semanas(conn: sqlite3.Connection) -> float:
    fila = conn.execute(
        "SELECT SemanasVacacionesMaximasPorAnio FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    return float(fila["SemanasVacacionesMaximasPorAnio"]) if fila else 2.0


def _semanas_consumidas_en_anio(conn: sqlite3.Connection, id_profesional: int, anio: int) -> float:
    filas = conn.execute(
        "SELECT FraccionSemanaConsumida FROM Vacacion WHERE IdProfesional = ? "
        "AND substr(FechaDesde, 1, 4) = ?",
        (id_profesional, str(anio)),
    ).fetchall()
    return sum(f["FraccionSemanaConsumida"] or 0 for f in filas)


def crear_vacacion(
    conn: sqlite3.Connection, *, id_profesional: int, fecha_desde: str, fecha_hasta: str,
    forzar: bool = False,
) -> int:
    if not _profesional_tiene_derecho(conn, id_profesional):
        raise ValueError(
            "Las vacaciones solo aplican a profesionales categoría R, B o E "
            "con reservas regulares activas"
        )

    dias = (date.fromisoformat(fecha_hasta) - date.fromisoformat(fecha_desde)).days + 1
    if dias <= 0:
        raise ValueError("FechaHasta debe ser posterior o igual a FechaDesde")

    fraccion = dias / 7
    cupo_maximo = _cupo_maximo_semanas(conn)
    anio = date.fromisoformat(fecha_desde).year
    ya_consumido = _semanas_consumidas_en_anio(conn, id_profesional, anio)
    consumido_total = ya_consumido + fraccion

    if cupo_maximo > 0:
        cupo_consumido_pct = consumido_total / cupo_maximo * 100
        restante_antes_pct = max(0.0, 100 - (ya_consumido / cupo_maximo * 100))
    else:
        cupo_consumido_pct = 100.0
        restante_antes_pct = 0.0
    cupo_restante_pct = max(0.0, 100 - cupo_consumido_pct)

    if consumido_total > cupo_maximo and not forzar:
        raise CupoVacacionesExcedidoError(restante_antes_pct, fraccion)

    valor_semanal = calcular_valor_semanal_regular(conn, id_profesional)
    valor_bonificado = valor_semanal * fraccion

    repo = obtener_repositorio(conn, "Vacacion")
    return repo.crear(
        IdProfesional=id_profesional, FechaDesde=fecha_desde, FechaHasta=fecha_hasta,
        ValorSemanalAlMomentoDelRegistro=valor_semanal, ValorBonificado=valor_bonificado,
        FraccionSemanaConsumida=fraccion, CupoConsumidoPorcentaje=cupo_consumido_pct,
        CupoRestantePorcentaje=cupo_restante_pct,
    )
