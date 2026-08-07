"""Pagos, cargos especiales y planes de pago (secciones 3.6, 3.15 y 3.23,
planes afinados por DC-09 §3).

CargoEspecial es el mecanismo genérico para los ítems manuales que después
aparecen en la liquidación (sección 4.5): ajustes, depósito/reintegro de
llave (IdLlave), ítems libres y feriados trabajados avisados con horas ya
calculadas manualmente. No hace falta un modelo separado para cada uno,
alcanza con Tipo (Débito/Crédito), Concepto y el período que imputan.

PlanPago admite refinanciación con interés simple (todas las cuotas
tienen el mismo importe): MontoTotalAPagar = MontoRefinanciado × (1 +
PorcentajeInteresMensual/100 × CantidadCuotas). Solo puede haber un plan
Activo por profesional a la vez — para otro hay que cancelar o refinanciar
el existente.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from app.negocio.dias import periodo_actual, sumar_meses
from app.repositorio.registro import obtener_repositorio

TIPOS_CARGO = ("Débito", "Crédito")


def _capitalizar(texto: str) -> str:
    texto = texto.strip()
    return texto[:1].upper() + texto[1:] if texto else texto


def registrar_pago(
    conn: sqlite3.Connection, *, id_profesional: int, monto: float, fecha: str | None = None,
    medio_pago: str | None = None, cuenta_receptora: str | None = None,
    periodo_imputado: str | None = None, es_ajuste: bool = False, observacion: str | None = None,
    fecha_transferencia: str | None = None, hora_transferencia: str | None = None,
) -> int:
    """Registra un pago recibido. Si se imputa a un período anterior al mes
    en curso descuenta de SaldoCuentaAnterior (DC-09 §8); si no, descuenta
    de SaldoCuentaActual. Nunca toca ambos a la vez."""
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

    campo = "SaldoCuentaAnterior" if periodo_imputado and periodo_imputado < periodo_actual(conn) else "SaldoCuentaActual"
    nuevo_saldo = (profesional[campo] or 0.0) - monto
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, **{campo: nuevo_saldo})
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


def _generar_cuotas(conn: sqlite3.Connection, id_plan: int, monto_total_a_pagar: float,
                     importe_por_cuota: float, cantidad_cuotas: int, mes_ano_inicio: str) -> None:
    repo_cuota = obtener_repositorio(conn, "CuotaPlan")
    # la última cuota absorbe el resto del redondeo para que la suma cierre exacto
    acumulado = 0.0
    for numero in range(1, cantidad_cuotas + 1):
        if numero < cantidad_cuotas:
            monto_cuota = importe_por_cuota
            acumulado += monto_cuota
        else:
            monto_cuota = round(monto_total_a_pagar - acumulado, 2)
        repo_cuota.crear(
            IdPlan=id_plan, NumeroCuota=numero,
            PeriodoImputado=sumar_meses(mes_ano_inicio, numero - 1),
            Monto=monto_cuota, Pagado=0, Estado="Pendiente",
        )


def crear_plan_pago(
    conn: sqlite3.Connection, *, id_profesional: int, monto_refinanciado: float, cantidad_cuotas: int,
    mes_ano_inicio: str, porcentaje_interes_mensual: float = 0.0, observacion: str | None = None,
) -> int:
    plan_activo = obtener_repositorio(conn, "PlanPago").listar(IdProfesional=id_profesional, Estado="Activo")
    if plan_activo:
        raise ValueError(
            f"El profesional #{id_profesional} ya tiene un plan de pagos activo "
            f"(#{plan_activo[0]['IdPlan']}); hay que cancelarlo o refinanciarlo, no puede haber dos a la vez"
        )
    return _crear_plan_pago(
        conn, id_profesional=id_profesional, monto_refinanciado=monto_refinanciado,
        cantidad_cuotas=cantidad_cuotas, mes_ano_inicio=mes_ano_inicio,
        porcentaje_interes_mensual=porcentaje_interes_mensual, observacion=observacion,
    )


def _crear_plan_pago(
    conn: sqlite3.Connection, *, id_profesional: int, monto_refinanciado: float, cantidad_cuotas: int,
    mes_ano_inicio: str, porcentaje_interes_mensual: float = 0.0, observacion: str | None = None,
    es_refinanciacion: bool = False, id_plan_anterior: int | None = None,
) -> int:
    """Crea el plan sin verificar el invariante de "un solo plan activo" —
    `refinanciar_plan` ya canceló el plan vigente (o decidió a propósito no
    hacerlo) antes de llamar acá, así que no corresponde repetir el chequeo."""
    if cantidad_cuotas <= 0:
        raise ValueError("La cantidad de cuotas debe ser mayor a cero")

    monto_total_a_pagar = monto_refinanciado * (1 + (porcentaje_interes_mensual / 100) * cantidad_cuotas)
    importe_por_cuota = round(monto_total_a_pagar / cantidad_cuotas, 2)

    repo_plan = obtener_repositorio(conn, "PlanPago")
    id_plan = repo_plan.crear(
        IdProfesional=id_profesional, MontoRefinanciado=monto_refinanciado,
        PorcentajeInteresMensual=porcentaje_interes_mensual, MontoTotalAPagar=monto_total_a_pagar,
        CantidadCuotas=cantidad_cuotas, ImportePorCuota=importe_por_cuota, MesAnoInicio=mes_ano_inicio,
        Estado="Activo", EsRefinanciacion=int(es_refinanciacion), IdPlanAnterior=id_plan_anterior,
        Observacion=observacion,
    )
    _generar_cuotas(conn, id_plan, monto_total_a_pagar, importe_por_cuota, cantidad_cuotas, mes_ano_inicio)
    return id_plan


def cancelar_plan(conn: sqlite3.Connection, id_plan: int) -> None:
    """Cancela un plan activo. Las cuotas pendientes se suman a
    SaldoCuentaActual: el saldo no desaparece, pasa a ser deuda normal
    (DC-09 §3.5)."""
    repo_plan = obtener_repositorio(conn, "PlanPago")
    plan = repo_plan.obtener(id_plan)
    if plan is None:
        raise ValueError(f"No existe el plan #{id_plan}")
    if plan["Estado"] != "Activo":
        raise ValueError(f"El plan #{id_plan} no está activo (Estado={plan['Estado']!r})")

    pendientes = conn.execute(
        "SELECT COALESCE(SUM(Monto), 0) AS total FROM CuotaPlan WHERE IdPlan = ? AND Pagado = 0", (id_plan,)
    ).fetchone()["total"]
    repo_plan.actualizar(id_plan, Estado="Cancelado")
    if pendientes:
        repo_prof = obtener_repositorio(conn, "Profesional")
        profesional = repo_prof.obtener(plan["IdProfesional"])
        repo_prof.actualizar(
            plan["IdProfesional"], SaldoCuentaActual=(profesional["SaldoCuentaActual"] or 0.0) + pendientes
        )


def refinanciar_plan(
    conn: sqlite3.Connection, *, id_profesional: int, monto_a_refinanciar: float, cantidad_cuotas: int,
    mes_ano_inicio: str, porcentaje_interes_mensual: float = 0.0, cancelar_plan_vigente: bool = True,
    observacion: str | None = None,
) -> int:
    """Formulario de refinanciación (DC-09 §3.6): cancela el plan vigente
    (si hay y se pide), descuenta el monto a refinanciar del saldo general
    (pasa a pagarse a través del plan nuevo) y crea el plan nuevo."""
    plan_activo = obtener_repositorio(conn, "PlanPago").listar(IdProfesional=id_profesional, Estado="Activo")
    id_plan_anterior = plan_activo[0]["IdPlan"] if plan_activo else None
    if id_plan_anterior is not None and cancelar_plan_vigente:
        cancelar_plan(conn, id_plan_anterior)

    repo_prof = obtener_repositorio(conn, "Profesional")
    profesional = repo_prof.obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    repo_prof.actualizar(
        id_profesional, SaldoCuentaActual=(profesional["SaldoCuentaActual"] or 0.0) - monto_a_refinanciar
    )

    return _crear_plan_pago(
        conn, id_profesional=id_profesional, monto_refinanciado=monto_a_refinanciar,
        cantidad_cuotas=cantidad_cuotas, mes_ano_inicio=mes_ano_inicio,
        porcentaje_interes_mensual=porcentaje_interes_mensual, observacion=observacion,
        es_refinanciacion=True, id_plan_anterior=id_plan_anterior,
    )


def marcar_cuota_pagada(conn: sqlite3.Connection, id_cuota: int) -> None:
    repo_cuota = obtener_repositorio(conn, "CuotaPlan")
    cuota = repo_cuota.obtener(id_cuota)
    if cuota is None:
        raise ValueError(f"No existe la cuota #{id_cuota}")

    repo_cuota.actualizar(id_cuota, Pagado=1, Estado="Pagada")

    pendientes = conn.execute(
        "SELECT COUNT(*) FROM CuotaPlan WHERE IdPlan = ? AND Pagado = 0", (cuota["IdPlan"],)
    ).fetchone()[0]
    if pendientes == 0:
        obtener_repositorio(conn, "PlanPago").actualizar(cuota["IdPlan"], Estado="Finalizado")
