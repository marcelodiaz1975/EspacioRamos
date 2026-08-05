"""Pagos, cargos especiales y planes de pago (secciones 3.6, 3.15 y 3.23).

CargoEspecial es el mecanismo genérico para los ítems manuales que después
aparecen en la liquidación (sección 4.5): ajustes, depósito/reintegro de
llave (IdLlave) e ítems libres. No hace falta un modelo separado para cada
uno, alcanza con Tipo (Débito/Crédito), Concepto y el período que imputan.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from app.repositorio.registro import obtener_repositorio

TIPOS_CARGO = ("Débito", "Crédito")


def _capitalizar(texto: str) -> str:
    texto = texto.strip()
    return texto[:1].upper() + texto[1:] if texto else texto


def _sumar_meses(periodo: str, cantidad: int) -> str:
    anio, mes = (int(p) for p in periodo.split("-"))
    total = (anio * 12 + (mes - 1)) + cantidad
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def registrar_pago(
    conn: sqlite3.Connection, *, id_profesional: int, monto: float, fecha: str | None = None,
    medio_pago: str | None = None, cuenta_receptora: str | None = None,
    periodo_imputado: str | None = None, es_ajuste: bool = False, observacion: str | None = None,
    fecha_transferencia: str | None = None, hora_transferencia: str | None = None,
) -> int:
    """Registra un pago recibido y descuenta el monto de la deuda actual del
    profesional. No modifica SaldoCuentaAnterior: ese campo se congela solo
    al emitir una liquidación (ver `liquidaciones.emitir_liquidacion`)."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")

    repo = obtener_repositorio(conn, "HistorialPagos")
    id_pago = repo.crear(
        IdProfesional=id_profesional, Fecha=fecha, Monto=monto, MedioPago=medio_pago,
        CuentaReceptora=cuenta_receptora, FechaHoraCarga=datetime.now().isoformat(timespec="seconds"),
        FechaTransferencia=fecha_transferencia, HoraTransferencia=hora_transferencia,
        PeriodoImputado=periodo_imputado, EsAjuste=int(es_ajuste), Observacion=observacion,
    )
    nuevo_saldo = profesional["SaldoCuentaActual"] - monto
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, SaldoCuentaActual=nuevo_saldo)
    return id_pago


def crear_cargo_especial(
    conn: sqlite3.Connection, *, id_profesional: int, tipo: str, concepto: str, monto: float,
    periodo_imputado: str | None = None, id_llave: int | None = None, id_unidad: int | None = None,
    observacion: str | None = None,
) -> int:
    if tipo not in TIPOS_CARGO:
        raise ValueError(f"Tipo de cargo inválido: {tipo!r} (debe ser Débito o Crédito)")
    if monto <= 0:
        raise ValueError("El monto del cargo especial debe ser positivo")

    repo = obtener_repositorio(conn, "CargoEspecial")
    return repo.crear(
        IdProfesional=id_profesional, Tipo=tipo, Concepto=_capitalizar(concepto), Monto=monto,
        PeriodoImputado=periodo_imputado, IdLlave=id_llave, IdUnidad=id_unidad, Observacion=observacion,
    )


def crear_plan_pago(
    conn: sqlite3.Connection, *, id_profesional: int, monto_total: float, cantidad_cuotas: int,
    mes_ano_inicio: str, observacion: str | None = None,
) -> int:
    if cantidad_cuotas <= 0:
        raise ValueError("La cantidad de cuotas debe ser mayor a cero")

    monto_por_cuota = round(monto_total / cantidad_cuotas, 2)
    repo_plan = obtener_repositorio(conn, "PlanPago")
    id_plan = repo_plan.crear(
        IdProfesional=id_profesional, MontoTotal=monto_total, CantidadCuotas=cantidad_cuotas,
        MontoPorCuota=monto_por_cuota, MesAnoInicio=mes_ano_inicio, Estado="Activo",
        Observacion=observacion,
    )

    repo_cuota = obtener_repositorio(conn, "CuotaPlan")
    # la última cuota absorbe el resto del redondeo para que la suma cierre exacto
    acumulado = 0.0
    for numero in range(1, cantidad_cuotas + 1):
        if numero < cantidad_cuotas:
            monto_cuota = monto_por_cuota
            acumulado += monto_cuota
        else:
            monto_cuota = round(monto_total - acumulado, 2)
        repo_cuota.crear(
            IdPlan=id_plan, NumeroCuota=numero,
            PeriodoImputado=_sumar_meses(mes_ano_inicio, numero - 1),
            Monto=monto_cuota, Pagado=0,
        )
    return id_plan


def marcar_cuota_pagada(conn: sqlite3.Connection, id_cuota: int) -> None:
    repo_cuota = obtener_repositorio(conn, "CuotaPlan")
    cuota = repo_cuota.obtener(id_cuota)
    if cuota is None:
        raise ValueError(f"No existe la cuota #{id_cuota}")

    repo_cuota.actualizar(id_cuota, Pagado=1)

    pendientes = conn.execute(
        "SELECT COUNT(*) FROM CuotaPlan WHERE IdPlan = ? AND Pagado = 0", (cuota["IdPlan"],)
    ).fetchone()[0]
    if pendientes == 0:
        obtener_repositorio(conn, "PlanPago").actualizar(cuota["IdPlan"], Estado="Finalizado")
