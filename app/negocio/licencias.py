"""Licencias (sección 3.13 del documento).

Cada TipoLicencia define un % de bonificación, una duración máxima opcional
y si es "manual" (el usuario tiene que indicar la fecha de fin a mano) o no
(la fecha de fin se calcula sola a partir de la duración máxima, como pasa
con duelo, matrimonio o maternidad).

Interpretación del cálculo de ValorBonificado (el documento no da la
fórmula, solo los campos "congelados" a guardar): se prorratea el valor
semanal vigente del profesional por los días de la licencia, aplicando el
% de bonificación del tipo.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from app.negocio.valores import calcular_valor_semanal_regular
from app.repositorio.registro import obtener_repositorio


def crear_licencia(
    conn: sqlite3.Connection, *, id_profesional: int, id_tipo_licencia: int,
    fecha_desde: str, fecha_hasta: str | None = None,
) -> int:
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
    if tipo["DuracionMaximaDias"] and dias > tipo["DuracionMaximaDias"]:
        raise ValueError(
            f"El tipo de licencia '{tipo['Nombre']}' tiene un máximo de "
            f"{tipo['DuracionMaximaDias']} días (se pidieron {dias})"
        )

    valor_semanal = calcular_valor_semanal_regular(conn, id_profesional)
    porcentaje = tipo["PorcentajeBonificacion"]
    valor_bonificado = (valor_semanal / 7) * dias * (porcentaje / 100)

    repo = obtener_repositorio(conn, "Licencia")
    return repo.crear(
        IdProfesional=id_profesional, IdTipoLicencia=id_tipo_licencia,
        FechaDesde=fecha_desde, FechaHasta=fecha_hasta,
        PorcentajeBonificacionAplicado=porcentaje,
        ValorSemanalAlMomentoDelRegistro=valor_semanal, ValorBonificado=valor_bonificado,
    )
