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

from app.negocio.dias import fecha_actual, periodo_actual, sumar_meses
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
    fecha_hora_recogida_sobres: str | None = None, fecha_hora_apertura_buzon: str | None = None,
) -> tuple[int, bool]:
    """Registra un movimiento de cuenta (pago o ajuste). `monto` es un
    valor con signo: negativo se resta de la cuenta del profesional (un
    pago recibido, que reduce lo que debe), positivo se suma (un cargo,
    que aumenta lo que debe) — `nuevo_saldo = saldo_previo + monto`. Si
    se imputa a un período anterior al mes en curso afecta
    SaldoCuentaAnterior (DC-09 §8); si no, SaldoCuentaActual. Nunca toca
    ambos a la vez.

    `fecha`, si no se pasa, toma la fecha de hoy (antes era un campo que
    cargaba el operador a mano; con el rediseño del formulario de Pagos
    ese dato pasó a ser siempre "ahora", igual que FechaHoraCarga).

    El segundo valor devuelto (`cruza_tolerancia`) es True cuando el pago
    imputado al mes anterior hace que ese saldo pase de estar por encima de
    ToleranciaDeudaDescuento a estar dentro — el caso en que corresponde
    preguntarle al operador si restablece el descuento por horas semanales
    para la liquidación remanente de ese período puntual (DC-06 §5.2)."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    if periodo_imputado and periodo_imputado < sumar_meses(periodo_actual(conn), -1):
        raise ValueError("Un pago no se puede imputar a más de un mes anterior al mes en curso")

    es_mes_anterior = bool(periodo_imputado) and periodo_imputado < periodo_actual(conn)
    campo = "SaldoCuentaAnterior" if es_mes_anterior else "SaldoCuentaActual"
    saldo_previo = profesional[campo] or 0.0
    nuevo_saldo = saldo_previo + monto
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, **{campo: nuevo_saldo})

    repo = obtener_repositorio(conn, "HistorialPagos")
    id_pago = repo.crear(
        IdProfesional=id_profesional, Fecha=fecha or fecha_actual(conn).isoformat(), Monto=monto,
        MedioPago=medio_pago, CuentaReceptora=cuenta_receptora,
        FechaHoraCarga=datetime.now().isoformat(timespec="seconds"),
        FechaTransferencia=fecha_transferencia, HoraTransferencia=hora_transferencia,
        PeriodoImputado=periodo_imputado, EsAjuste=int(es_ajuste), Observacion=observacion,
        FechaHoraRecogidaSobres=fecha_hora_recogida_sobres, FechaHoraAperturaBuzon=fecha_hora_apertura_buzon,
        SaldoAnterior=saldo_previo, SaldoNuevo=nuevo_saldo, RegistroModificado=0,
    )

    cruza_tolerancia = False
    if es_mes_anterior:
        cfg = conn.execute(
            "SELECT ToleranciaDeudaDescuento FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        tolerancia = cfg["ToleranciaDeudaDescuento"] if cfg else 0.0
        cruza_tolerancia = saldo_previo > tolerancia >= nuevo_saldo
    return id_pago, cruza_tolerancia


def _campo_saldo(conn: sqlite3.Connection, periodo_imputado: str | None) -> str:
    es_mes_anterior = bool(periodo_imputado) and periodo_imputado < periodo_actual(conn)
    return "SaldoCuentaAnterior" if es_mes_anterior else "SaldoCuentaActual"


def modificar_pago(
    conn: sqlite3.Connection, id_pago: int, *, monto: float | None = None, medio_pago: str | None = None,
    cuenta_receptora: str | None = None, periodo_imputado: str | None = None,
    fecha_hora_recogida_sobres: str | None = None,
) -> None:
    """Edita un pago ya cargado in-place (a diferencia de Vacaciones/
    Licencias/Ausencias, acá no se anula y se recrea): revierte el efecto
    que tenía sobre el saldo del profesional y aplica el nuevo, conserva
    FechaHoraCarga tal cual quedó la primera vez, y marca
    RegistroModificado. Los parámetros en None dejan ese campo como
    estaba — pasar explícitamente el valor actual si se quiere "no
    cambiarlo" pero de todos modos tocar otro campo."""
    repo = obtener_repositorio(conn, "HistorialPagos")
    pago = repo.obtener(id_pago)
    if pago is None:
        raise ValueError(f"No existe el pago #{id_pago}")
    repo_prof = obtener_repositorio(conn, "Profesional")
    profesional = repo_prof.obtener(pago["IdProfesional"])
    if profesional is None:
        raise ValueError(f"No existe el profesional #{pago['IdProfesional']}")
    if periodo_imputado and periodo_imputado < sumar_meses(periodo_actual(conn), -1):
        raise ValueError("Un pago no se puede imputar a más de un mes anterior al mes en curso")

    campo_viejo = _campo_saldo(conn, pago["PeriodoImputado"])
    repo_prof.actualizar(pago["IdProfesional"], **{campo_viejo: (profesional[campo_viejo] or 0.0) - pago["Monto"]})

    nuevo_monto = monto if monto is not None else pago["Monto"]
    nuevo_periodo = periodo_imputado if periodo_imputado is not None else pago["PeriodoImputado"]
    campo_nuevo = _campo_saldo(conn, nuevo_periodo)
    profesional = repo_prof.obtener(pago["IdProfesional"])
    saldo_previo = profesional[campo_nuevo] or 0.0
    nuevo_saldo = saldo_previo + nuevo_monto
    repo_prof.actualizar(pago["IdProfesional"], **{campo_nuevo: nuevo_saldo})

    repo.actualizar(
        id_pago, Monto=nuevo_monto,
        MedioPago=medio_pago if medio_pago is not None else pago["MedioPago"],
        CuentaReceptora=cuenta_receptora if cuenta_receptora is not None else pago["CuentaReceptora"],
        PeriodoImputado=nuevo_periodo,
        FechaHoraRecogidaSobres=(
            fecha_hora_recogida_sobres if fecha_hora_recogida_sobres is not None else pago["FechaHoraRecogidaSobres"]
        ),
        SaldoAnterior=saldo_previo, SaldoNuevo=nuevo_saldo, RegistroModificado=1,
    )


def eliminar_pago(conn: sqlite3.Connection, id_pago: int) -> sqlite3.Row:
    """Revierte por completo un movimiento de HistorialPagos: le devuelve
    al profesional el saldo que tenía antes de ese movimiento y borra el
    registro. Devuelve la fila borrada, para que quien la llame pueda
    avisar qué se eliminó (y, si corresponde, regenerar la liquidación del
    mes en curso — eso queda a cargo de quien llama, igual que ya hace
    `modificar_pago` vía la pantalla)."""
    repo = obtener_repositorio(conn, "HistorialPagos")
    pago = repo.obtener(id_pago)
    if pago is None:
        raise ValueError(f"No existe el pago #{id_pago}")

    repo_prof = obtener_repositorio(conn, "Profesional")
    profesional = repo_prof.obtener(pago["IdProfesional"])
    if profesional is not None:
        campo = _campo_saldo(conn, pago["PeriodoImputado"])
        repo_prof.actualizar(pago["IdProfesional"], **{campo: (profesional[campo] or 0.0) - pago["Monto"]})

    repo.eliminar(id_pago)
    return pago


def deshacer_ultimo_pago(conn: sqlite3.Connection) -> sqlite3.Row:
    """Como `eliminar_pago`, pero sobre el último movimiento registrado en
    HistorialPagos (el de IdPago más alto), sin necesidad de elegirlo a
    mano."""
    todos = obtener_repositorio(conn, "HistorialPagos").listar()
    if not todos:
        raise ValueError("No hay ningún movimiento para deshacer")
    ultimo = max(todos, key=lambda p: p["IdPago"])
    return eliminar_pago(conn, ultimo["IdPago"])


# --------------------------------------------------------------- tanda de sobres (DC-08 §5.3)
#
# Una "tanda" no tiene tabla propia: se identifica por su FechaHoraApertura
# (el momento en que se abrió), guardada en Configuracion mientras está
# abierta. Cada pago por sobre registrado durante esa tanda guarda el mismo
# valor en HistorialPagos.FechaHoraAperturaBuzon, que es lo que permite
# sumar el subtotal en vivo sin necesitar una tabla aparte ni un ID: dos
# pagos "pertenecen a la misma tanda" si comparten esa marca de tiempo.

def tanda_sobres_abierta(conn: sqlite3.Connection) -> str | None:
    """Fecha y hora de apertura de la tanda actual, o None si no hay
    ninguna abierta."""
    cfg = conn.execute(
        "SELECT TandaSobresAbierta, TandaSobresApertura FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    if cfg and cfg["TandaSobresAbierta"]:
        return cfg["TandaSobresApertura"]
    return None


def abrir_tanda_sobres(conn: sqlite3.Connection) -> str:
    """Abre una tanda nueva (o reemplaza la que estuviera abierta: el
    operador ya decidió no mantenerla, ver `tanda_sobres_es_de_otro_dia`).
    Devuelve la marca de tiempo de apertura."""
    apertura = datetime.now().isoformat(timespec="seconds")
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, TandaSobresAbierta=1, TandaSobresApertura=apertura,
    )
    return apertura


def cerrar_tanda_sobres(conn: sqlite3.Connection) -> None:
    obtener_repositorio(conn, "Configuracion").actualizar(1, TandaSobresAbierta=0)


def tanda_sobres_es_de_otro_dia(conn: sqlite3.Connection) -> bool:
    """True si hay una tanda abierta pero de un día calendario distinto al
    de hoy — el caso en que corresponde preguntarle al operador si la
    mantiene o arranca una nueva (DC-08 §5.3)."""
    apertura = tanda_sobres_abierta(conn)
    if apertura is None:
        return False
    return apertura[:10] != fecha_actual(conn).isoformat()


def subtotal_tanda_sobres(conn: sqlite3.Connection, apertura: str) -> float:
    """Suma de los pagos por sobre registrados durante la tanda que abrió
    en `apertura` — el subtotal en vivo para cuadrar contra el efectivo
    físico al ir abriendo los sobres."""
    fila = conn.execute(
        "SELECT COALESCE(SUM(Monto), 0) AS total FROM HistorialPagos "
        "WHERE MedioPago = 'Sobre en buzón' AND FechaHoraAperturaBuzon = ?",
        (apertura,),
    ).fetchone()
    return fila["total"]


def suspender_descuento_periodo(conn: sqlite3.Connection, *, id_profesional: int, periodo: str) -> None:
    """DC-06 §5.2, rama "No" (la recomendada por defecto): aunque el saldo
    anterior ya volvió a estar dentro de tolerancia, el descuento por horas
    semanales queda perdido igual para la liquidación remanente de ese
    período puntual — los meses siguientes se evalúan de forma
    independiente, sin arrastrar esta decisión."""
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, DescuentoSuspendidoPeriodo=periodo)


def crear_cargo_especial(
    conn: sqlite3.Connection, *, id_profesional: int, tipo: str, concepto: str, monto: float,
    periodo_imputado: str, id_llave: int | None = None, id_unidad: int | None = None,
    observacion: str | None = None,
) -> int:
    """A diferencia de Pagos (que sí puede corregir hasta un mes atrás), un
    cargo especial nunca se imputa a un período ya cerrado — ajustes,
    bonificaciones y depósitos/reintegros de llave se cargan siempre al mes
    en curso o a uno posterior, para no tener que reabrir una liquidación
    ya emitida (confirmado por la clienta). El monto lleva directo el
    signo que le corresponde al Tipo (Débito positivo, Crédito negativo)
    — Tipo queda como una validación cruzada de ese signo, no hace falta
    derivarlo aparte en ningún lado que sume estos montos."""
    if tipo not in TIPOS_CARGO:
        raise ValueError(f"Tipo de cargo inválido: {tipo!r} (debe ser Débito o Crédito)")
    if not periodo_imputado:
        raise ValueError("El período imputado es obligatorio")
    if periodo_imputado < periodo_actual(conn):
        raise ValueError("No se puede imputar un cargo especial a un período anterior al mes en curso")
    if tipo == "Débito" and monto <= 0:
        raise ValueError("Un cargo especial Débito debe cargarse con un monto positivo")
    if tipo == "Crédito" and monto >= 0:
        raise ValueError("Un cargo especial Crédito debe cargarse con un monto negativo")

    repo = obtener_repositorio(conn, "CargoEspecial")
    return repo.crear(
        IdProfesional=id_profesional, Tipo=tipo, Concepto=_capitalizar(concepto), Monto=monto,
        Fecha=fecha_actual(conn).isoformat(), PeriodoImputado=periodo_imputado,
        IdLlave=id_llave, IdUnidad=id_unidad, Observacion=observacion,
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


def _validar_sin_plan_activo(conn: sqlite3.Connection, id_profesional: int) -> None:
    plan_activo = obtener_repositorio(conn, "PlanPago").listar(IdProfesional=id_profesional, Estado="Activo")
    if plan_activo:
        raise ValueError(
            f"El profesional #{id_profesional} ya tiene un plan de pagos activo "
            f"(#{plan_activo[0]['IdPlan']}); hay que cancelarlo o refinanciarlo, no puede haber dos a la vez"
        )


def crear_plan_pago(
    conn: sqlite3.Connection, *, id_profesional: int, monto_refinanciado: float, cantidad_cuotas: int,
    porcentaje_interes_mensual: float = 0.0, observacion: str | None = None,
) -> int:
    """Formulario de "Guardar nuevo plan de pagos" (DC-09 §3.6, aclarado en
    conversación): se arma siempre a principio del mes en curso.
    `monto_refinanciado` sale del saldo atrasado (SaldoCuentaAnterior), que
    se descuenta acá — deja de ser deuda suelta y pasa a pagarse en cuotas.
    La primera cuota queda imputada al período actual y se cobra sola en
    la próxima liquidación de este mes, junto con lo demás
    (`calcular_liquidacion` ya suma las CuotaPlan pendientes del período)."""
    _validar_sin_plan_activo(conn, id_profesional)
    repo_prof = obtener_repositorio(conn, "Profesional")
    profesional = repo_prof.obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    repo_prof.actualizar(
        id_profesional, SaldoCuentaAnterior=(profesional["SaldoCuentaAnterior"] or 0.0) - monto_refinanciado
    )
    return _crear_plan_pago(
        conn, id_profesional=id_profesional, monto_refinanciado=monto_refinanciado,
        cantidad_cuotas=cantidad_cuotas, mes_ano_inicio=periodo_actual(conn),
        porcentaje_interes_mensual=porcentaje_interes_mensual, observacion=observacion,
    )


def crear_plan_pago_historico(
    conn: sqlite3.Connection, *, id_profesional: int, monto_refinanciado: float, cantidad_cuotas: int,
    mes_ano_inicio: str, porcentaje_interes_mensual: float = 0.0, observacion: str | None = None,
) -> int:
    """Para reconstruir un plan que ya venía en curso antes de empezar a
    usar el sistema (importación de Excel, `importar_excel.
    _crear_plan_pago_importado`): a diferencia de `crear_plan_pago`, no
    toca SaldoCuentaAnterior — ese estado ya viene reflejado aparte en el
    saldo importado del profesional — y admite cualquier MesAnoInicio,
    no solo el período actual."""
    _validar_sin_plan_activo(conn, id_profesional)
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


def plan_activo_de(conn: sqlite3.Connection, id_profesional: int) -> sqlite3.Row | None:
    """El plan de pagos Activo del profesional, si tiene uno (nunca puede
    haber más de uno a la vez)."""
    activos = obtener_repositorio(conn, "PlanPago").listar(IdProfesional=id_profesional, Estado="Activo")
    return activos[0] if activos else None


def cuotas_restantes_plan(conn: sqlite3.Connection, id_plan: int) -> tuple[int, float]:
    """Cantidad y monto de las cuotas del plan que todavía no cerró el
    avance de mes (`avance_mes._cerrar_cuotas` las pasa a Estado="Cerrada"
    al cerrar el período al que estaban imputadas, cobradas o no vía la
    liquidación de ese mes) — son las que de verdad quedan sin abonar,
    incluida la del período en curso si todavía no se cerró."""
    fila = conn.execute(
        "SELECT COUNT(*) AS cantidad, COALESCE(SUM(Monto), 0) AS total FROM CuotaPlan "
        "WHERE IdPlan = ? AND Estado != 'Cerrada'",
        (id_plan,),
    ).fetchone()
    return fila["cantidad"], fila["total"]


def cuotas_pendientes_plan(conn: sqlite3.Connection, id_plan: int) -> float:
    """Ver `cuotas_restantes_plan` — esto es solo el monto."""
    return cuotas_restantes_plan(conn, id_plan)[1]


def cancelar_plan(conn: sqlite3.Connection, id_plan: int) -> None:
    """Cancela un plan activo. Las cuotas que todavía quedaban sin abonar
    (incluida la del mes en curso si no se cerró) se suman a
    SaldoCuentaAnterior: vuelven a ser saldo atrasado, tal como estaban
    antes de armar el plan (DC-09 §3.5, aclarado en conversación)."""
    repo_plan = obtener_repositorio(conn, "PlanPago")
    plan = repo_plan.obtener(id_plan)
    if plan is None:
        raise ValueError(f"No existe el plan #{id_plan}")
    if plan["Estado"] != "Activo":
        raise ValueError(f"El plan #{id_plan} no está activo (Estado={plan['Estado']!r})")

    pendientes = cuotas_pendientes_plan(conn, id_plan)
    repo_plan.actualizar(id_plan, Estado="Cancelado")
    if pendientes:
        repo_prof = obtener_repositorio(conn, "Profesional")
        profesional = repo_prof.obtener(plan["IdProfesional"])
        repo_prof.actualizar(
            plan["IdProfesional"], SaldoCuentaAnterior=(profesional["SaldoCuentaAnterior"] or 0.0) + pendientes
        )


def refinanciar_plan(
    conn: sqlite3.Connection, *, id_profesional: int, monto_a_refinanciar: float, cantidad_cuotas: int,
    porcentaje_interes_mensual: float = 0.0, observacion: str | None = None,
) -> int:
    """Formulario de refinanciación (DC-09 §3.6, aclarado en conversación):
    se arma siempre a principio del mes en curso. Cancela el plan vigente
    (las cuotas que le quedaban, incluida la de este mes, se suman a
    SaldoCuentaAnterior — ver `cancelar_plan`), descuenta de ahí
    `monto_a_refinanciar` (que en la pantalla ya viene sugerido como ese
    mismo saldo atrasado, con las cuotas del plan viejo incluidas) y arma
    el plan nuevo con eso."""
    plan_activo = obtener_repositorio(conn, "PlanPago").listar(IdProfesional=id_profesional, Estado="Activo")
    if not plan_activo:
        raise ValueError(f"El profesional #{id_profesional} no tiene un plan de pagos activo para refinanciar")
    id_plan_anterior = plan_activo[0]["IdPlan"]
    cancelar_plan(conn, id_plan_anterior)

    repo_prof = obtener_repositorio(conn, "Profesional")
    profesional = repo_prof.obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    repo_prof.actualizar(
        id_profesional, SaldoCuentaAnterior=(profesional["SaldoCuentaAnterior"] or 0.0) - monto_a_refinanciar
    )

    return _crear_plan_pago(
        conn, id_profesional=id_profesional, monto_refinanciado=monto_a_refinanciar,
        cantidad_cuotas=cantidad_cuotas, mes_ano_inicio=periodo_actual(conn),
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
