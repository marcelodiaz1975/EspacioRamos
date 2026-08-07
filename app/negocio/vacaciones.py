"""Vacaciones (sección 3.12 del documento).

Solo aplican a profesionales categoría R, B o E con reservas regulares
activas. El cupo máximo es de N semanas por año calendario
(Configuracion.SemanasVacacionesMaximasPorAnio, default 2). El consumo del
cupo no se mide en días corridos sino en peso económico relativo a la
semana del profesional:

1. ValorSemanalAlMomentoDelRegistro: suma de todas sus horas regulares
   semanales × su valor con el descuento por volumen de horas aplicado.
   Se congela al momento del registro.
2. ValorBonificado: suma, para cada día del período de vacaciones que cae
   en un día de la semana en que el profesional tiene reserva regular
   vigente, de las horas de ese día × el valor con descuento. Es el
   importe que se descuenta en la liquidación.
3. FraccionSemanaConsumida = ValorBonificado / ValorSemanalAlMomentoDelRegistro.
4. CupoConsumidoPorcentaje: suma de todas las fracciones del año calendario
   (incluida esta) × 100 / SemanasVacacionesMaximasPorAnio.
5. CupoRestantePorcentaje = 100 - CupoConsumidoPorcentaje.

Si el período solicitado supera el cupo disponible, el sistema avisa pero
no bloquea: se bonifica solo la porción que entra en el cupo restante y el
resto se factura normalmente en la liquidación (no se le resta nada de
ValorBonificado).

El cupo se calcula siempre en vivo sumando las Vacacion del profesional
del año calendario correspondiente, así que no hace falta un paso de
"reseteo" en el avance de mes de enero: el año siguiente arranca en cero
porque todavía no tiene registros propios.

Categoría B (DC-05 §1.1): sin impacto económico — sus bloques ya están
bonificados en la liquidación, así que ValorBonificado se guarda siempre
en 0. El cupo (FraccionSemanaConsumida y derivados) se sigue consumiendo
igual que para R/E: sirve para saber cuándo el consultorio queda libre
para asignar aisladas, no depende de si hay o no descuento económico.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from app.negocio.dias import fecha_actual
from app.negocio.valores import (
    calcular_valor_semanal_regular,
    obtener_porcentaje_descuento,
    valor_regular_por_rango_dias,
)
from app.repositorio.registro import obtener_repositorio

CATEGORIAS_CON_DERECHO_A_VACACIONES = ("R", "B", "E")


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


def _valor_bonificado_bruto(
    conn: sqlite3.Connection, id_profesional: int, fecha_desde: str, fecha_hasta: str, descuento_pct: float,
) -> float:
    """Valor de las horas regulares reservadas en el período, con el
    descuento por volumen ya aplicado (sección 3.12)."""
    bruto = valor_regular_por_rango_dias(conn, id_profesional, fecha_desde, fecha_hasta)
    return bruto * (1 - descuento_pct / 100)


def crear_vacacion(
    conn: sqlite3.Connection, *, id_profesional: int, fecha_desde: str, fecha_hasta: str,
) -> tuple[int, list[str]]:
    if not _profesional_tiene_derecho(conn, id_profesional):
        raise ValueError(
            "Las vacaciones solo aplican a profesionales categoría R, B o E "
            "con reservas regulares activas"
        )
    if fecha_hasta < fecha_desde:
        raise ValueError("FechaHasta debe ser posterior o igual a FechaDesde")

    fecha_hoy = fecha_actual(conn).isoformat()
    horas_semanales = conn.execute(
        "SELECT COALESCE(SUM(HoraFin - HoraInicio), 0) AS total FROM ReservaRegular "
        "WHERE IdProfesional = ? AND VigenciaInicio <= ? AND (VigenciaFin IS NULL OR VigenciaFin >= ?)",
        (id_profesional, fecha_hoy, fecha_hoy),
    ).fetchone()["total"]
    descuento_pct = obtener_porcentaje_descuento(conn, horas_semanales)

    valor_semanal = calcular_valor_semanal_regular(conn, id_profesional, fecha_hoy)
    valor_bonificado_bruto = _valor_bonificado_bruto(conn, id_profesional, fecha_desde, fecha_hasta, descuento_pct)
    fraccion_bruta = (valor_bonificado_bruto / valor_semanal) if valor_semanal > 0 else 0.0

    cupo_maximo = _cupo_maximo_semanas(conn)
    anio = date.fromisoformat(fecha_desde).year
    ya_consumido = _semanas_consumidas_en_anio(conn, id_profesional, anio)
    cupo_restante_antes = max(0.0, cupo_maximo - ya_consumido)
    if cupo_restante_antes < 1e-9:  # residuo de punto flotante: tratarlo como cupo agotado
        cupo_restante_antes = 0.0

    advertencias = []
    if fraccion_bruta > cupo_restante_antes:
        proporcion_cubierta = (cupo_restante_antes / fraccion_bruta) if fraccion_bruta > 0 else 0.0
        valor_bonificado = valor_bonificado_bruto * proporcion_cubierta
        fraccion_consumida = cupo_restante_antes
        valor_excedente = valor_bonificado_bruto - valor_bonificado
        advertencias.append(
            "La vacación excede el cupo disponible: se bonifican "
            f"{fraccion_consumida:.2f} semana(s) (cupo agotado) y ${valor_excedente:,.2f} "
            "del período se facturan normalmente en la liquidación"
        )
    else:
        valor_bonificado = valor_bonificado_bruto
        fraccion_consumida = fraccion_bruta

    consumido_total = ya_consumido + fraccion_consumida
    if cupo_maximo > 0:
        cupo_consumido_pct = consumido_total / cupo_maximo * 100
    else:
        cupo_consumido_pct = 100.0 if consumido_total > 0 else 0.0
    cupo_restante_pct = max(0.0, 100 - cupo_consumido_pct)

    # Categoría B (DC-05 §1.1): sin impacto económico — sus bloques ya están
    # bonificados, así que no hay nada que descontar en ninguna liquidación.
    # El cupo se sigue consumiendo igual (sirve para saber cuándo el
    # consultorio queda libre para aisladas).
    profesional = conn.execute(
        "SELECT CategoriaProfesional FROM Profesional WHERE IdProfesional = ?", (id_profesional,)
    ).fetchone()
    if profesional["CategoriaProfesional"] == "B":
        valor_bonificado = 0.0

    repo = obtener_repositorio(conn, "Vacacion")
    id_vacacion = repo.crear(
        IdProfesional=id_profesional, FechaDesde=fecha_desde, FechaHasta=fecha_hasta,
        ValorSemanalAlMomentoDelRegistro=valor_semanal, ValorBonificado=valor_bonificado,
        FraccionSemanaConsumida=fraccion_consumida, CupoConsumidoPorcentaje=cupo_consumido_pct,
        CupoRestantePorcentaje=cupo_restante_pct,
    )
    return id_vacacion, advertencias
