"""Licencias (sección 3.13 del documento, afinado por DC-05).

Cada TipoLicencia define un % de bonificación, una duración máxima opcional
y si es "manual" (el usuario tiene que indicar la fecha de fin a mano) o no
(la fecha de fin se calcula sola a partir de la duración máxima, como pasa
con duelo, matrimonio o maternidad).

Cálculo de ValorBonificado (DC-05 §2.4) — mismo criterio que vacaciones:
1. ValorHoraConDescuento = valor regular del consultorio × (1 - descuento
   por horas semanales vigente al registrar).
2. ValorBonificado = suma, para cada día del período que cae en un día de
   la semana con reserva regular activa, de horas × ValorHoraConDescuento
   × (PorcentajeBonificacion / 100).
A diferencia de vacaciones no hay cupo anual: el tope es la duración
máxima del tipo de licencia. Si el período pedido la supera, se avisa pero
no bloquea — solo se bonifican los primeros DuracionMaximaDias días desde
FechaDesde; el resto se cobra normalmente en la liquidación (queda fuera
de ValorBonificado).

Categoría B (DC-05 §2.1): sin impacto económico — ValorBonificado se
guarda en 0 aunque el registro sea válido (sirve solo para saber cuándo
el consultorio queda libre).

Igual que vacaciones (DC-05 §2.1), solo aplican a profesionales categoría
R, B o E con reserva regular activa. El % de bonificación del tipo de
licencia es el valor por defecto, pero se puede editar caso por caso al
registrarla (DC-05 §2.2).
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from app.negocio.dias import fecha_actual
from app.negocio.vacaciones import CATEGORIAS_CON_DERECHO_A_VACACIONES
from app.negocio.valores import (
    calcular_valor_semanal_regular,
    horas_semanales_vigentes,
    obtener_porcentaje_descuento,
    valor_regular_por_rango_dias,
)
from app.repositorio.registro import obtener_repositorio


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


def crear_licencia(
    conn: sqlite3.Connection, *, id_profesional: int, id_tipo_licencia: int,
    fecha_desde: str, fecha_hasta: str | None = None, porcentaje_bonificacion: float | None = None,
) -> tuple[int, list[str]]:
    if not _profesional_tiene_derecho(conn, id_profesional):
        raise ValueError(
            "Las licencias solo aplican a profesionales categoría R, B o E "
            "con reservas regulares activas"
        )
    tipo = obtener_repositorio(conn, "TipoLicencia").obtener(id_tipo_licencia)
    if tipo is None:
        raise ValueError(f"No existe el tipo de licencia #{id_tipo_licencia}")

    if fecha_hasta is None:
        if tipo["EsManual"] or not tipo["DuracionMaximaDias"]:
            raise ValueError(
                f"El tipo de licencia '{tipo['Nombre']}' requiere que se indique FechaHasta"
            )
        fecha_hasta = (
            date.fromisoformat(fecha_desde) + timedelta(days=tipo["DuracionMaximaDias"] - 1)
        ).isoformat()

    dias = (date.fromisoformat(fecha_hasta) - date.fromisoformat(fecha_desde)).days + 1
    if dias <= 0:
        raise ValueError("FechaHasta debe ser posterior o igual a FechaDesde")

    advertencias: list[str] = []
    fecha_hasta_bonificable = fecha_hasta
    if tipo["DuracionMaximaDias"] and dias > tipo["DuracionMaximaDias"]:
        fecha_hasta_bonificable = (
            date.fromisoformat(fecha_desde) + timedelta(days=tipo["DuracionMaximaDias"] - 1)
        ).isoformat()
        dias_excedentes = dias - tipo["DuracionMaximaDias"]
        advertencias.append(
            f"El período supera la duración máxima de '{tipo['Nombre']}' "
            f"({tipo['DuracionMaximaDias']} días): {dias_excedentes} día(s) excedente(s) "
            "se cobran normalmente en la liquidación"
        )

    fecha_hoy = fecha_actual(conn).isoformat()
    horas_semanales = horas_semanales_vigentes(conn, [id_profesional], fecha_hoy)
    descuento_pct = obtener_porcentaje_descuento(conn, horas_semanales)
    valor_semanal = calcular_valor_semanal_regular(conn, id_profesional, fecha_hoy)

    porcentaje = porcentaje_bonificacion if porcentaje_bonificacion is not None else tipo["PorcentajeBonificacion"]
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is not None and profesional["CategoriaProfesional"] == "B":
        valor_bonificado = 0.0
    else:
        bruto = valor_regular_por_rango_dias(conn, id_profesional, fecha_desde, fecha_hasta_bonificable)
        valor_bonificado = bruto * (1 - descuento_pct / 100) * (porcentaje / 100)

    repo = obtener_repositorio(conn, "Licencia")
    id_licencia = repo.crear(
        IdProfesional=id_profesional, IdTipoLicencia=id_tipo_licencia,
        FechaDesde=fecha_desde, FechaHasta=fecha_hasta,
        PorcentajeBonificacionAplicado=porcentaje,
        ValorSemanalAlMomentoDelRegistro=valor_semanal, ValorBonificado=valor_bonificado,
    )
    return id_licencia, advertencias
