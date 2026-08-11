"""Mensajes de WhatsApp para el centro de mensajería (Etapa 8, sección 5).

El documento describe la ESTRUCTURA de cada mensaje (qué bloques van y en
qué orden) pero no da una redacción exacta como sí pasó con el PDF de
Liquidación (donde hubo un modelo real para copiar) — la redacción de acá
es criterio propio sobre esa estructura, para ajustar en la revisión de
la beta.

Situaciones del centro de mensajería (sección 5.3), solo para categoría
R: se determinan a partir de dos señales — si el profesional arrastra
saldo por encima de la tolerancia (mismo campo que usa
`liquidaciones.calcular_liquidacion` para `pierde_descuento`, así las dos
lecturas de "está atrasado" quedan consistentes) y si ya tiene un plan de
pagos activo, que pisa el circuito normal de deuda/tolerancia. El
documento no cubre el caso "liquidación ya enviada pero con deuda por
encima de la tolerancia" como una situación aparte — se lo trata igual
que la situación 2 (mensaje personal), asumiendo que la liquidación ya
enviada es la fuente de verdad vigente y no hace falta el aviso
automático de la situación 1 encima.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from app.negocio.dias import DIAS_SEMANA, sumar_meses
from app.negocio.feriados import feriados_relevantes_periodo
from app.negocio.formato import fecha_corta, hora_fmt, mes_texto, periodo_mm_aaaa
from app.negocio.liquidaciones import CATEGORIAS_CON_LIQUIDACION_MENSUAL
from app.repositorio.registro import obtener_repositorio


def _moneda(monto: float) -> str:
    texto = f"{abs(monto):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-$ {texto}" if monto < 0 else f"$ {texto}"


def nombre_para_mensaje(profesional: sqlite3.Row) -> str:
    """Sección 5.6: Apodo -> NombrePila -> Tratamiento + Apellido."""
    if profesional["Apodo"]:
        return profesional["Apodo"]
    if profesional["NombrePila"]:
        return profesional["NombrePila"]
    tratamiento = profesional["Tratamiento"] or ""
    return f"{tratamiento} {profesional['Apellido']}".strip()


def _lista_con_y(items: list[str]) -> str:
    """"X" / "X y Z" / "X, Z y W" (sección 5.4)."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} y {items[-1]}"


# --------------------------------------------------------------- situaciones (5.3)

def _plan_activo(conn: sqlite3.Connection, id_profesional: int) -> sqlite3.Row | None:
    filas = obtener_repositorio(conn, "PlanPago").listar(IdProfesional=id_profesional, Estado="Activo")
    return filas[0] if filas else None


def _liquidacion_del_periodo(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> sqlite3.Row | None:
    filas = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    return max(filas, key=lambda f: f["IdLiquidacion"]) if filas else None


def determinar_situacion(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> str | None:
    """"1".."5" (sección 5.3), o None si la categoría no tiene liquidación
    mensual propia (solo R aplica; las aisladas usan el detalle de
    reservas de la sección 5.1, sin situaciones)."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None or profesional["CategoriaProfesional"] not in CATEGORIAS_CON_LIQUIDACION_MENSUAL:
        return None

    plan = _plan_activo(conn, id_profesional)
    liquidacion = _liquidacion_del_periodo(conn, id_profesional, periodo)
    enviada = liquidacion is not None and liquidacion["EstadoEnvio"] == "Enviada"

    if plan is not None:
        return "4" if enviada else "5"

    cfg = conn.execute("SELECT ToleranciaDeudaDescuento FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    tolerancia = cfg["ToleranciaDeudaDescuento"] if cfg else 0.0
    saldo_anterior = profesional["SaldoCuentaAnterior"] or 0.0
    supera_tolerancia = saldo_anterior > tolerancia

    if enviada:
        return "2"
    return "1" if supera_tolerancia else "3"


def mensaje_situacion(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> str:
    situacion = determinar_situacion(conn, id_profesional, periodo)
    if situacion is None:
        raise ValueError("Las situaciones del centro de mensajería solo aplican a profesionales categoría R")

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    nombre = nombre_para_mensaje(profesional)
    saldo_anterior = profesional["SaldoCuentaAnterior"] or 0.0
    cfg = conn.execute(
        "SELECT PorcentajeAjusteSaldoAtrasado, DiasEnvioLiquidacionesRemanentes FROM Configuracion "
        "WHERE IdConfiguracion = 1"
    ).fetchone()
    ajuste_pct = cfg["PorcentajeAjusteSaldoAtrasado"] if cfg else 0.0
    dias_remanentes = cfg["DiasEnvioLiquidacionesRemanentes"] if cfg else 5

    if situacion == "1":
        return (
            f"Hola {nombre}! Te escribimos porque registramos un saldo pendiente de {_moneda(saldo_anterior)}. "
            f"Tenés hasta el fin de mes ({dias_remanentes} días de margen) para regularizarlo y no perder los "
            f"descuentos por horas semanales reservadas del próximo período. Los saldos que se trasladan de un "
            f"mes a otro reciben además un ajuste del {ajuste_pct:g}%."
        )
    if situacion == "2":
        return f"Hola {nombre}! Te enviamos la liquidación del período {periodo_mm_aaaa(periodo)}. Cualquier consulta, quedamos atentos."
    if situacion == "3":
        return (
            f"Hola {nombre}! En los próximos días vas a recibir un mensaje automático con el resumen de tu "
            f"cuenta y, apenas esté lista, te enviamos la liquidación de {periodo_mm_aaaa(periodo)}."
        )
    if situacion == "4":
        plan = _plan_activo(conn, id_profesional)
        cuota = obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=plan["IdPlan"], PeriodoImputado=periodo)
        monto_cuota = cuota[0]["Monto"] if cuota else plan["ImportePorCuota"]
        return (
            f"Hola {nombre}! Te enviamos la liquidación de {periodo_mm_aaaa(periodo)}. Recordá que incluye la "
            f"cuota de tu plan de pagos por {_moneda(monto_cuota)}."
        )
    return (  # situación 5
        f"Hola {nombre}! En los próximos días vas a recibir el mensaje automático con el resumen de tu cuenta. "
        f"Recordá que, al tener un plan de pagos activo, la cuota correspondiente se descuenta igual aunque "
        f"todavía no se haya enviado la liquidación."
    )


# ------------------------------------------------------------------- mensaje grupal (5.4)

def mensaje_grupal(conn: sqlite3.Connection, periodo_liquidacion: str) -> str:
    """"LIQUIDACIONES DE {MES SIGUIENTE} - AVISOS VARIOS" (sección 5.4):
    `periodo_liquidacion` es el mes que se está por cerrar (cuya
    liquidación se arma y envía "el mes siguiente" a él, según el flujo de
    avance de mes)."""
    cfg = conn.execute("SELECT MensajesPlural FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    plural = bool(cfg["MensajesPlural"]) if cfg else True
    pronombre_verbo = "les avisaremos" if plural else "te avisaré"

    mes_siguiente = sumar_meses(periodo_liquidacion, 1)
    mes_siguiente_2 = sumar_meses(periodo_liquidacion, 2)
    anio_sig, mes_sig = (int(p) for p in mes_siguiente.split("-"))

    feriados = feriados_relevantes_periodo(conn, anio_sig, mes_sig)
    lineas = [
        f"LIQUIDACIONES DE {mes_texto(mes_sig).upper()} - AVISOS VARIOS",
        "",
        "CIERRE DE RESERVA",
        "Recordamos que antes de que comience el mes se puede cancelar o ajustar la reserva regular; los "
        "cambios que no se coordinen se mantienen igual que el mes anterior.",
        "",
        "ENVIO DE LIQUIDACIONES",
        f"Las liquidaciones de {mes_texto(mes_sig)} se van a enviar dentro de los primeros días del mes.",
    ]
    if feriados:
        nombres = [f"el {f['Fecha'].split('-')[2].lstrip('0')} de {mes_texto(mes_sig)}" for f in feriados]
        lineas += [
            "",
            f"FERIADOS MES DE {mes_texto(mes_sig).upper()}",
            f"Este mes hay {'feriados' if len(feriados) > 1 else 'un feriado'} {_lista_con_y(nombres)}, que se "
            f"{'descuentan' if len(feriados) > 1 else 'descuenta'} al 100% salvo aviso previo. La próxima "
            f"liquidación, en este caso la de {mes_texto(int(mes_siguiente_2.split('-')[1]))}, {pronombre_verbo} "
            f"si hay novedades.",
        ]
    return "\n".join(lineas)


# --------------------------------------------------------- detalle aisladas (5.1)

def _edificios_de_llaves_activas(conn: sqlite3.Connection, id_profesional: int) -> set[int]:
    filas = conn.execute(
        """
        SELECT DISTINCT la.IdEdificio
        FROM LlaveProfesional lp
        JOIN LlaveAcceso la ON la.IdLlave = lp.IdLlave
        WHERE lp.IdProfesional = ? AND lp.FechaDevolucion IS NULL
        """,
        (id_profesional,),
    ).fetchall()
    return {f["IdEdificio"] for f in filas}


def _lugar_reserva(fila: sqlite3.Row, incluir_consultorio: bool, incluir_unidad: bool, incluir_edificio: bool) -> str:
    """Sección 5.1: los controles están "encadenados" — si no se incluye
    el consultorio tampoco tiene sentido mostrar unidad/edificio solos
    (sin consultorio no queda claro a qué corresponde el importe)."""
    partes = []
    if incluir_consultorio:
        partes.append(f"consul {fila['NumeroConsultorio']}")
        if incluir_unidad:
            partes.append(fila["Departamento"])
        if incluir_edificio:
            partes.append(fila["NombreEdificio"])
    return " - ".join(partes)


def mensaje_detalle_reserva_aislada(
    conn: sqlite3.Connection, *, id_profesional: int, periodo: str,
    incluir_consultorio: bool = True, incluir_unidad: bool = True, incluir_edificio: bool = True,
) -> str:
    """"DETALLE RESERVA {MES}" (sección 5.1, categoría A). No implementa
    todavía "Combinar misma unidad"/"Combinar distintas unidades" (fusionar
    en una sola línea reservas del mismo día que terminan cayendo en el
    mismo consultorio/unidad) — cada reserva aislada aparece en su propia
    línea; a revisar en la beta si hace falta la fusión.

    "Regla edificio" (si tiene llaves de más de un edificio, se agrega el
    edificio a cada línea aunque `incluir_edificio` esté en False) se
    resuelve mirando las llaves ACTIVAS (sin devolver) del profesional."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    nombre = nombre_para_mensaje(profesional)
    anio, mes = (int(p) for p in periodo.split("-"))

    if len(_edificios_de_llaves_activas(conn, id_profesional)) > 1:
        incluir_edificio = True

    filas = conn.execute(
        """
        SELECT ra.IdReservaAislada, ra.Fecha, ra.HoraInicio, ra.HoraFin, ra.AplicaRecargo,
               c.NumeroConsultorio, c.ValorHoraAisladaActual, u.Departamento,
               e.IdEdificio, e.Nombre AS NombreEdificio, e.Domicilio, e.DomicilioLocalidad
        FROM ReservaAislada ra
        JOIN Consultorio c ON c.IdConsultorio = ra.IdConsultorio
        JOIN Unidad u ON u.IdUnidad = c.IdUnidad
        JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE ra.IdProfesional = ? AND ra.Estado = 'Confirmada'
        ORDER BY ra.Fecha, ra.HoraInicio
        """,
        (id_profesional,),
    ).fetchall()

    cfg = conn.execute("SELECT RecargoPorcentajeAisladas FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    recargo_pct = cfg["RecargoPorcentajeAisladas"] if cfg else 0.0

    prefijo_mes = f"{anio:04d}-{mes:02d}-"
    del_mes = [f for f in filas if f["Fecha"].startswith(prefijo_mes)]
    posteriores = [f for f in filas if f["Fecha"] > f"{anio:04d}-{mes:02d}-31"]

    def _monto(f: sqlite3.Row) -> float:
        monto = (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraAisladaActual"]
        return monto * (1 + recargo_pct / 100) if f["AplicaRecargo"] else monto

    lineas = [f"Hola {nombre}!", "", f"DETALLE RESERVA {mes_texto(mes).upper()}:", ""]

    llaves = conn.execute(
        """
        SELECT lp.*, l.ValorDepositoActual FROM LlaveProfesional lp JOIN Llave l ON l.IdLlave = lp.IdLlave
        WHERE lp.IdProfesional = ? AND (lp.FechaEntrega LIKE ? OR lp.FechaDevolucion LIKE ?)
        """,
        (id_profesional, prefijo_mes + "%", prefijo_mes + "%"),
    ).fetchall()
    for ll in llaves:
        if ll["FechaEntrega"] and ll["FechaEntrega"].startswith(prefijo_mes) and ll["DepositoCobrado"]:
            lineas.append(f"Depósito de llave: {_moneda(ll['MontoCobrado'] or ll['ValorDepositoActual'])}")
        if ll["FechaDevolucion"] and ll["FechaDevolucion"].startswith(prefijo_mes) and ll["DepositoReintegrado"]:
            lineas.append(f"Reintegro de llave: -{_moneda(ll['MontoReintegrado'] or ll['ValorDepositoActual'])}")
    if llaves:
        lineas.append("")

    total_reservas = 0.0
    for f in del_mes:
        dia_semana = DIAS_SEMANA[date.fromisoformat(f["Fecha"]).weekday()]
        monto = _monto(f)
        total_reservas += monto
        lugar = _lugar_reserva(f, incluir_consultorio, incluir_unidad, incluir_edificio)
        sufijo_lugar = f" - {lugar}" if lugar else ""
        lineas.append(
            f"{dia_semana} {fecha_corta(f['Fecha'])} de {hora_fmt(f['HoraInicio'])[:-2]} a "
            f"{hora_fmt(f['HoraFin'])}{sufijo_lugar}: {_moneda(monto)}"
        )
    lineas.append("")

    saldo_anterior = profesional["SaldoCuentaAnterior"] or 0.0
    lineas.append(f"Saldo anterior: {_moneda(saldo_anterior)}")

    pagos = conn.execute(
        "SELECT * FROM HistorialPagos WHERE IdProfesional = ? AND Fecha LIKE ? ORDER BY Fecha",
        (id_profesional, prefijo_mes + "%"),
    ).fetchall()
    total_pagos = sum(p["Monto"] for p in pagos if not p["EsAjuste"])
    total_ajustes = sum(p["Monto"] for p in pagos if p["EsAjuste"])
    for p in pagos:
        etiqueta = "Ajuste" if p["EsAjuste"] else "Pago"
        lineas.append(f"{etiqueta} {fecha_corta(p['Fecha'])}: -{_moneda(p['Monto'])}")

    saldo_a_abonar = saldo_anterior + total_reservas - total_pagos - total_ajustes
    lineas += ["", f"SALDO A ABONAR: {_moneda(saldo_a_abonar)}"]

    if posteriores:
        lineas += ["", "RESERVAS POSTERIORES:"]
        for f in posteriores:
            dia_semana = DIAS_SEMANA[date.fromisoformat(f["Fecha"]).weekday()]
            lugar = _lugar_reserva(f, incluir_consultorio, incluir_unidad, incluir_edificio)
            sufijo_lugar = f" - {lugar}" if lugar else ""
            lineas.append(
                f"{dia_semana} {fecha_corta(f['Fecha'])} de {hora_fmt(f['HoraInicio'])[:-2]} a "
                f"{hora_fmt(f['HoraFin'])}{sufijo_lugar}"
            )

    edificios_mencionados: dict[int, sqlite3.Row] = {f["IdEdificio"]: f for f in del_mes + posteriores}
    if incluir_edificio and edificios_mencionados:
        lineas.append("")
        for e in edificios_mencionados.values():
            lineas.append(f"* Edificio {e['NombreEdificio']}: Corresponde a {e['Domicilio']}, {e['DomicilioLocalidad']}")

    lineas += ["", "* Los sobres con el pago en efectivo se dejan en la recepción a nombre del espacio."]
    return "\n".join(lineas)
