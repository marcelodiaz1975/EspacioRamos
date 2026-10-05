"""Mensajes de WhatsApp para el centro de mensajería (DC-02, DC-03).

DC-03 da la redacción EXACTA de cada mensaje (a diferencia del spec
general, que solo describía la estructura) — el texto de acá es literal
al documento, verificado además contra ejemplos reales que confirmó el
usuario (Mensaje 1 y Mensaje 3 grupal).

Las 5 situaciones (DC-02 §5) ya no se determinan por tolerancia/plan
directamente acá — se arman por color del Centro de mensajería
(`app.negocio.mensajeria.color_profesional`), que es quien resuelve la
máquina de estados completa (violeta, gris con posible recordatorio
bordó, etc.). Cada `mensaje_situacion_N` asume que el llamador (la
pantalla) ya construyó el mensaje correcto para el color/acción según la
tabla de asignación de DC-03 "Resumen de asignaciones" — no vuelven a
validar el color acá. `mensaje_recordatorio_fin_de_mes` (bordó) es
posterior a DC-02/DC-03, pedido directo de la clienta — no tiene
numeración de "situación" del documento original.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Callable

from app.negocio.dias import DIAS_SEMANA, fecha_a_dia_semana, sumar_meses, ultimo_dia_mes
from app.negocio.feriados import feriados_relevantes_periodo
from app.negocio.formato import fecha_corta, hora_fmt, mes_texto
from app.negocio.liquidaciones import CATEGORIAS_CON_LIQUIDACION_MENSUAL
from app.negocio.plantillas_texto import (  # noqa: F401 (sustituir_variables se reexporta)
    DEFAULT_DETALLE_RESERVA_AISLADA,
    DEFAULT_ENVIO_LIQUIDACION,
    DEFAULT_GRUPAL,
    DEFAULT_RECORDATORIO_FIN_DE_MES,
    DEFAULT_SITUACION_1,
    DEFAULT_SITUACION_2,
    DEFAULT_SITUACION_3,
    DEFAULT_SITUACION_5,
    resolver_plantilla,
    sustituir_variables,
)
from app.repositorio.registro import obtener_repositorio

NOMBRES_CONDICION = {
    "ventana": "con ventana", "aptoCamilla": "apto camilla",
    "balcon": "con balcón", "aire": "con aire acondicionado",
}


def _moneda(monto: float) -> str:
    """DC-03 reglas generales: punto como separador de miles, SIN
    decimales, sin espacio entre "$" y el número (ej. "$4.330")."""
    texto = f"{abs(monto):,.0f}".replace(",", ".")
    return f"-${texto}" if monto < 0 else f"${texto}"


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

def plan_activo(conn: sqlite3.Connection, id_profesional: int) -> sqlite3.Row | None:
    filas = obtener_repositorio(conn, "PlanPago").listar(IdProfesional=id_profesional, Estado="Activo")
    return filas[0] if filas else None


def liquidacion_del_periodo(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> sqlite3.Row | None:
    """Última emisión de LiquidacionEmitida para (profesional, período), o
    None si todavía no se emitió ninguna — la misma noción de "última" que
    usa `liquidaciones.emitir_liquidacion`/`marcar_estado_envio`."""
    filas = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    return max(filas, key=lambda f: f["IdLiquidacion"]) if filas else None


def dias_desde_ultimo_pago(conn: sqlite3.Connection, id_profesional: int, hoy: date) -> int | None:
    """Días entre `hoy` y el último pago real (no ajuste) registrado —
    orden del centro de mensajería (sección 6.2). None si nunca pagó (se
    ordena antes que cualquier profesional con pagos, es a quien más
    tiempo hace falta contactar)."""
    fila = conn.execute(
        "SELECT MAX(Fecha) AS ultima FROM HistorialPagos WHERE IdProfesional = ? AND EsAjuste = 0",
        (id_profesional,),
    ).fetchone()
    ultima = fila["ultima"] if fila else None
    if not ultima:
        return None
    return (hoy - date.fromisoformat(ultima)).days


def _profesional_r(conn: sqlite3.Connection, id_profesional: int) -> sqlite3.Row:
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None or profesional["CategoriaProfesional"] not in CATEGORIAS_CON_LIQUIDACION_MENSUAL:
        raise ValueError("Las situaciones del centro de mensajería solo aplican a profesionales categoría R")
    return profesional


def _dias_remanentes(conn: sqlite3.Connection) -> int:
    cfg = conn.execute(
        "SELECT DiasEnvioLiquidacionesRemanentes FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    return cfg["DiasEnvioLiquidacionesRemanentes"] if cfg and cfg["DiasEnvioLiquidacionesRemanentes"] is not None else 5


def _fecha_y_dia_remanente(conn: sqlite3.Connection, hoy: date) -> tuple[str, str, int]:
    """DC-02 Situación 1: "{FechaRemanente} — fecha calculada: día actual +
    DiasEnvioLiquidacionesRemanentes"."""
    dias = _dias_remanentes(conn)
    fecha_remanente = hoy + timedelta(days=dias)
    dia_semana = DIAS_SEMANA[fecha_remanente.weekday()].lower()
    return dia_semana, fecha_corta(fecha_remanente.isoformat()), dias


def _cuando_remanente(dias: int, dia_semana: str, fecha: str) -> str:
    """DC-02 Situación 3: "Hoy"/"Mañana"/"Pasado mañana" según días
    restantes; el documento no cubre más de 2 días, así que para el resto
    se usa la misma forma "{día} {fecha}" que ya usa Situación 1."""
    if dias <= 0:
        return "Hoy"
    if dias == 1:
        return "Mañana"
    if dias == 2:
        return "Pasado mañana"
    return f"El {dia_semana} {fecha}"


def mensaje_situacion_1(conn: sqlite3.Connection, id_profesional: int, hoy: date) -> str:
    """Amarillo/Naranja con liquidación NO enviada, botón "Generar texto"
    (DC-02 §5). Editable desde "Textos del sistema" (clave
    `mensaje_situacion_1`) — ver `app.negocio.plantillas_texto`."""
    profesional = _profesional_r(conn, id_profesional)
    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or ""
    dia_semana, fecha, _ = _fecha_y_dia_remanente(conn, hoy)
    saldo = _moneda(profesional["SaldoCuentaAnterior"] or 0.0)
    plantilla = resolver_plantilla(conn, "mensaje_situacion_1", DEFAULT_SITUACION_1)
    return sustituir_variables(plantilla, {
        "saldo": saldo, "dia_semana": dia_semana, "fecha": fecha, "nombre_espacio": nombre_espacio,
    })


def mensaje_situacion_2(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> str:
    """Amarillo, al activar el check de envío (DC-02 §5). Editable (clave
    `mensaje_situacion_2`)."""
    profesional = _profesional_r(conn, id_profesional)
    anio, mes = periodo.split("-")
    plantilla = resolver_plantilla(conn, "mensaje_situacion_2", DEFAULT_SITUACION_2)
    return sustituir_variables(plantilla, {
        "nombre": nombre_para_mensaje(profesional), "mes": mes_texto(int(mes)),
    })


def mensaje_situacion_3(conn: sqlite3.Connection, id_profesional: int, periodo: str, hoy: date) -> str:
    """Marrón, botón "Generar texto" (al generarlo pasa a amarillo — el
    llamador es responsable de avisarle a
    `app.negocio.mensajeria.marcar_mensaje_previo_generado`). Editable
    (clave `mensaje_situacion_3`)."""
    profesional = _profesional_r(conn, id_profesional)
    anio, mes = periodo.split("-")
    dia_semana, fecha, dias = _fecha_y_dia_remanente(conn, hoy)
    cuando = _cuando_remanente(dias, dia_semana, fecha)
    saldo = _moneda(profesional["SaldoCuentaAnterior"] or 0.0)
    plantilla = resolver_plantilla(conn, "mensaje_situacion_3", DEFAULT_SITUACION_3)
    return sustituir_variables(plantilla, {
        "nombre": nombre_para_mensaje(profesional), "cuando": cuando, "mes": mes_texto(int(mes)), "saldo": saldo,
    })


def mensaje_recordatorio_fin_de_mes(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> str:
    """Bordó, botón "Generar texto" (al generarlo vuelve a gris — el
    llamador es responsable de avisarle a
    `app.negocio.mensajeria.marcar_recordatorio_mensajeria_generado`).

    Modelo acordado con la clienta: empieza igual que los demás mensajes
    automáticos ("MENSAJE AUTOMATICO") y repite, casi textual, las
    secciones de "Mensaje grupal" (cierre de reservas / envío de
    liquidaciones / feriados del mes próximo) — pero agrega arriba de
    todo el estado de cuenta actual del profesional (a su favor / pendiente
    a favor del espacio / en cero), y si queda deudor, la fecha y hora de
    la última recogida de sobres (Configuracion.FechaHoraRecogidaSobres,
    el mismo valor que ya precarga el campo de Pagos) como corte de lo
    ya contemplado en ese saldo.

    Editable (clave `mensaje_recordatorio_fin_de_mes`) — "ESTADO DE CUENTA
    ACTUAL" y el bloque de feriados llegan a la plantilla ya armados como
    variables (`{estado_cuenta}`/`{bloque_feriados}`), el sistema sigue
    decidiendo cuándo y qué contienen (pedido explícito de la clienta)."""
    profesional = _profesional_r(conn, id_profesional)
    saldo = profesional["SaldoCuentaActual"] or 0.0

    anio, mes = (int(p) for p in periodo.split("-"))
    ultimo_dia = ultimo_dia_mes(anio, mes)
    mes_siguiente = sumar_meses(periodo, 1)
    anio_sig, mes_sig = (int(p) for p in mes_siguiente.split("-"))
    primer_dia_siguiente = date(anio_sig, mes_sig, 1)

    if saldo == 0:
        estado_cuenta = "* Saldo en cero, sin deuda."
    elif saldo < 0:
        estado_cuenta = f"* A favor del profesional {_moneda(abs(saldo))}."
    else:
        estado_cuenta = f"* Pendiente de cancelación {_moneda(saldo)}."
        cfg = conn.execute(
            "SELECT FechaHoraRecogidaSobres FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        if cfg and cfg["FechaHoraRecogidaSobres"]:
            dt = datetime.fromisoformat(cfg["FechaHoraRecogidaSobres"])
            dia_semana = DIAS_SEMANA[dt.weekday()].lower()
            hora = hora_fmt(dt.hour + dt.minute / 60)
            estado_cuenta += (
                f"\n* Para el cálculo del saldo se contemplaron los sobres recogidos hasta las {hora} del "
                f"{dia_semana} {fecha_corta(dt.date().isoformat())}."
            )

    bloque_feriados = ""
    feriados = feriados_relevantes_periodo(conn, anio_sig, mes_sig)
    if feriados:
        lineas_feriados = ["", "", "PROXIMOS FERIADOS 👇", ""]
        for f in feriados:
            d = date.fromisoformat(f["Fecha"])
            lineas_feriados.append(f"* {DIAS_SEMANA[d.weekday()]} {fecha_corta(f['Fecha'])}")
        bloque_feriados = "\n".join(lineas_feriados)

    plantilla = resolver_plantilla(
        conn, "mensaje_recordatorio_fin_de_mes", DEFAULT_RECORDATORIO_FIN_DE_MES,
    )
    return sustituir_variables(plantilla, {
        "estado_cuenta": estado_cuenta,
        "fecha_cierre_reservas": f"{DIAS_SEMANA[ultimo_dia.weekday()]} {fecha_corta(ultimo_dia.isoformat())}",
        "fecha_envio_liquidaciones": (
            f"{DIAS_SEMANA[primer_dia_siguiente.weekday()]} {fecha_corta(primer_dia_siguiente.isoformat())}"
        ),
        "bloque_feriados": bloque_feriados,
    })


def mensaje_situacion_5(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> str:
    """Rojo con liquidación NO enviada (DC-02 §5). Editable (clave
    `mensaje_situacion_5`)."""
    profesional = _profesional_r(conn, id_profesional)
    anio, mes = periodo.split("-")
    saldo = _moneda(profesional["SaldoCuentaAnterior"] or 0.0)
    plantilla = resolver_plantilla(conn, "mensaje_situacion_5", DEFAULT_SITUACION_5)
    return sustituir_variables(plantilla, {
        "nombre": nombre_para_mensaje(profesional), "mes": mes_texto(int(mes)), "saldo": saldo,
    })


def mensaje_envio_liquidacion(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> str:
    """Mensaje 4 (DC-03): acompaña el PDF de liquidación. Asignado a
    verde/violeta/gris (botón) y verde/naranja/rojo/violeta/gris (check).
    Editable (clave `mensaje_envio_liquidacion`)."""
    _profesional_r(conn, id_profesional)
    anio, mes = periodo.split("-")
    plantilla = resolver_plantilla(conn, "mensaje_envio_liquidacion", DEFAULT_ENVIO_LIQUIDACION)
    return sustituir_variables(plantilla, {"mes": mes_texto(int(mes))})


# ------------------------------------------------------------------- mensaje grupal (Mensaje 3, DC-03)

def _texto_feriados_grupal(feriados: list[sqlite3.Row]) -> str:
    """"lo correspondiente al {día1} DD/M por ser {tipo1}[, el {día2}...] y
    el {díaN} DD/M por ser {tipoN}" (DC-03, construcción de la lista de
    feriados)."""
    piezas = []
    for i, f in enumerate(feriados):
        d = date.fromisoformat(f["Fecha"])
        prefijo = "al" if i == 0 else "el"
        piezas.append(f"{prefijo} {DIAS_SEMANA[d.weekday()].lower()} {fecha_corta(f['Fecha'])} por ser {f['Tipo'].lower()}")
    if len(piezas) == 1:
        return piezas[0]
    return f"{', '.join(piezas[:-1])} y {piezas[-1]}"


def mensaje_grupal(conn: sqlite3.Connection, periodo_liquidacion: str) -> str:
    """Mensaje 3 (DC-03): "LIQUIDACIONES DE {MesSiguienteMAYUS} - AVISOS
    VARIOS", para el grupo de WhatsApp. `periodo_liquidacion` es el mes que
    se está por cerrar (cuya liquidación se arma y envía "el mes
    siguiente" a él, según el flujo de avance de mes). Editable (clave
    `mensaje_grupal`) — el bloque de feriados llega como `{bloque_feriados}`
    ya armado, no es editable por separado en esta primera vuelta."""
    cfg = conn.execute("SELECT MensajesPlural FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    plural = bool(cfg["MensajesPlural"]) if cfg is None or cfg["MensajesPlural"] is None else bool(cfg["MensajesPlural"])
    nos_o_me = "nos" if plural else "me"

    anio, mes = (int(p) for p in periodo_liquidacion.split("-"))
    ultimo_dia = ultimo_dia_mes(anio, mes)
    mes_siguiente = sumar_meses(periodo_liquidacion, 1)
    mes_siguiente_mas1 = sumar_meses(periodo_liquidacion, 2)
    anio_sig, mes_sig = (int(p) for p in mes_siguiente.split("-"))
    primer_dia_siguiente = date(anio_sig, mes_sig, 1)

    bloque_feriados = ""
    feriados = feriados_relevantes_periodo(conn, anio_sig, mes_sig)
    if feriados:
        esos_ese_dias = "esos días" if len(feriados) > 1 else "ese día"
        bloque_feriados = "\n".join([
            "",
            "",
            f"FERIADOS MES DE {mes_texto(mes_sig).upper()} 👇",
            "",
            f"* Se descontará del cálculo de la liquidación lo correspondiente {_texto_feriados_grupal(feriados)} "
            f"dando por descontado en principio que el profesional no asiste al espacio en {esos_ese_dias}.",
            f"* El profesional que necesite trabajar en alguno de {esos_ese_dias} {nos_o_me} avisará cerca del "
            "momento los horarios que pudiera llegar a necesitar para ser asignados, los cuales pueden ser "
            "distintos a los que habitualmente se tienen reservados.",
            f"* Las que se coordinen para ser utilizadas en {esos_ese_dias} como siempre se incluirán y "
            f"detallarán en la próxima liquidación, en este caso la de "
            f"{mes_texto(int(mes_siguiente_mas1.split('-')[1]))}.",
        ])

    plantilla = resolver_plantilla(conn, "mensaje_grupal", DEFAULT_GRUPAL)
    return sustituir_variables(plantilla, {
        "mes_mayus": mes_texto(mes_sig).upper(),
        "dia_cierre": DIAS_SEMANA[ultimo_dia.weekday()].lower(),
        "fecha_cierre": fecha_corta(ultimo_dia.isoformat()),
        "mes": mes_texto(mes_sig),
        "dia_envio": DIAS_SEMANA[primer_dia_siguiente.weekday()].lower(),
        "fecha_envio": fecha_corta(primer_dia_siguiente.isoformat()),
        "nos_o_me": nos_o_me,
        "bloque_feriados": bloque_feriados,
    })


# --------------------------------------------------------- detalle aisladas (5.1)

def _edificios_de_llaves_activas(conn: sqlite3.Connection, id_profesional: int) -> set[int]:
    filas = conn.execute(
        """
        SELECT DISTINCT la.IdEdificio
        FROM LlaveMovimiento asig
        JOIN LlaveAcceso la ON la.IdLlave = asig.IdLlave
        WHERE asig.IdProfesional = ? AND asig.Tipo = 'Asignación'
          AND NOT EXISTS (SELECT 1 FROM LlaveMovimiento cierre WHERE cierre.IdAsignacion = asig.IdMovimiento)
        """,
        (id_profesional,),
    ).fetchall()
    return {f["IdEdificio"] for f in filas}


def _incluir_edificio_efectivo(
    conn: sqlite3.Connection, incluir_edificio: bool, id_profesional: int | None = None,
) -> bool:
    """"Regla del edificio" (DC-03, reglas generales — aplica a todos los
    mensajes): si el espacio tiene un solo edificio se omite SIEMPRE la
    mención, aunque el control esté tildado; si el profesional tiene
    llaves de un solo edificio también se omite; si tiene llaves de más
    de un edificio se fuerza a incluir aunque el control esté destildado.
    Sin llaves todavía (recién empieza, alguien le abre la puerta la
    primera vez) y con más de un edificio en el espacio, se incluye —
    confirmado por el usuario, por eso `incluir_edificio` default True en
    los llamadores de Mensaje 1 en vez de tratar "sin llaves" como
    "omitir". Sin profesional asociado (Mensaje 2, que no está atado a
    uno en particular) solo aplica el primer nivel."""
    if conn.execute("SELECT COUNT(*) AS n FROM Edificio").fetchone()["n"] <= 1:
        return False
    if id_profesional is not None:
        edificios = _edificios_de_llaves_activas(conn, id_profesional)
        if len(edificios) == 1:
            return False
        if len(edificios) > 1:
            return True
    return incluir_edificio


def _lugar_reserva(fila: sqlite3.Row, incluir_consultorio: bool, incluir_unidad: bool, incluir_edificio: bool) -> str:
    """DC-03: "consul N del {Depto} [- Edificio {nombre}]" — el consultorio
    y la unidad se unen con la palabra "del"; el edificio, si corresponde,
    se agrega aparte con " - Edificio {nombre}". Los controles están
    "encadenados": si no se incluye el consultorio tampoco tiene sentido
    mostrar unidad/edificio solos (sin consultorio no queda claro a qué
    corresponde el importe)."""
    if not incluir_consultorio:
        return ""
    texto = f"consul {fila['NumeroConsultorio']}"
    if incluir_unidad:
        texto += f" del {fila['Departamento']}"
    if incluir_edificio:
        texto += f" - Edificio {fila['NombreEdificio']}"
    return texto


def _agrupar_bloques_continuos(reservas_dia: list[sqlite3.Row]) -> list[list[sqlite3.Row]]:
    """#44: agrupa, por consultorio, las reservas de un mismo día cuyos
    horarios son continuos (el HoraFin de una coincide con el HoraInicio
    de la siguiente, sin huecos) — "una línea por bloque continuo de
    horas", pedido explícito de la clienta para el default SIN combinar.
    Dos reservas del mismo consultorio con un hueco entre medio (ej. 10 a
    12 y 14 a 16) quedan en grupos separados, igual que antes de este
    pedido."""
    por_consultorio: dict[int, list[sqlite3.Row]] = {}
    for f in reservas_dia:
        por_consultorio.setdefault(f["IdConsultorio"], []).append(f)

    grupos: list[list[sqlite3.Row]] = []
    for filas_consultorio in por_consultorio.values():
        ordenadas = sorted(filas_consultorio, key=lambda f: f["HoraInicio"])
        bloque_actual: list[sqlite3.Row] = []
        for f in ordenadas:
            if bloque_actual and f["HoraInicio"] == bloque_actual[-1]["HoraFin"]:
                bloque_actual.append(f)
            else:
                if bloque_actual:
                    grupos.append(bloque_actual)
                bloque_actual = [f]
        if bloque_actual:
            grupos.append(bloque_actual)
    return grupos


def _lineas_reservas_aisladas(
    filas: list[sqlite3.Row], *, incluir_consultorio: bool, incluir_unidad: bool, incluir_edificio: bool,
    combinar_misma_unidad: bool, combinar_distintas_unidades: bool,
    monto_fn: Callable[[sqlite3.Row], float] | None = None,
) -> tuple[list[str], float]:
    """Sección 5.1: sin combinar (default), cada BLOQUE CONTINUO de horas
    (mismo consultorio, sin huecos entre una reserva y la siguiente)
    aparece en su propia línea, como un único rango — #44, pedido
    explícito de la clienta. Dos reservas con un hueco entre medio siguen
    en líneas separadas. Con "Combinar misma unidad" se funden en una
    sola línea TODAS las reservas del mismo día y consultorio (continuas
    o no), uniendo las franjas horarias con "y de" — sin cambios, este
    pedido no tocó ese checkbox. "Combinar distintas unidades" además
    agrupa bajo una sola fecha (con el total del día) las reservas de
    consultorios distintos ese mismo día — implica combinar misma unidad
    (no tendría sentido agrupar entre consultorios sin haber fundido antes
    los repetidos). `monto_fn` es None para "RESERVAS POSTERIORES" (sección
    5.1: esa lista va sin importe)."""
    combinar_misma_unidad = combinar_misma_unidad or combinar_distintas_unidades

    por_fecha: dict[str, list[sqlite3.Row]] = {}
    for f in filas:
        por_fecha.setdefault(f["Fecha"], []).append(f)

    lineas: list[str] = []
    total = 0.0
    for fecha, reservas_dia in por_fecha.items():
        dia_semana = DIAS_SEMANA[date.fromisoformat(fecha).weekday()]

        if combinar_misma_unidad:
            grupos: dict[int, list[sqlite3.Row]] = {}
            for f in reservas_dia:
                grupos.setdefault(f["IdConsultorio"], []).append(f)
            grupos_ordenados = list(grupos.values())
        else:
            grupos_ordenados = _agrupar_bloques_continuos(reservas_dia)

        entradas = []  # (horarios, lugar, monto | None)
        for grupo in grupos_ordenados:
            if combinar_misma_unidad:
                horarios = " y de ".join(
                    f"{hora_fmt(f['HoraInicio'])[:-2]} a {hora_fmt(f['HoraFin'])}" for f in grupo
                )
            else:
                # Bloque continuo: un único rango de punta a punta, no
                # un "y de" por cada reserva que lo compone.
                horarios = f"{hora_fmt(grupo[0]['HoraInicio'])[:-2]} a {hora_fmt(grupo[-1]['HoraFin'])}"
            lugar = _lugar_reserva(grupo[0], incluir_consultorio, incluir_unidad, incluir_edificio)
            monto = sum(monto_fn(f) for f in grupo) if monto_fn else None
            entradas.append((horarios, lugar, monto))

        if combinar_distintas_unidades and len(entradas) > 1 and monto_fn:
            total_dia = sum(monto for _, _, monto in entradas)
            lineas.append(f"+ {dia_semana} {fecha_corta(fecha)}: {_moneda(total_dia)}")
            for horarios, lugar, monto in entradas:
                sufijo_lugar = f" {lugar}" if lugar else ""
                lineas.append(f"  de {horarios}{sufijo_lugar}: {_moneda(monto)}")
            total += total_dia
        else:
            for horarios, lugar, monto in entradas:
                sufijo_lugar = f" {lugar}" if lugar else ""
                sufijo_monto = f" {_moneda(monto)}" if monto is not None else ""
                lineas.append(f"+ {dia_semana} {fecha_corta(fecha)} de {horarios}{sufijo_lugar}{sufijo_monto}")
                total += monto or 0.0

    return lineas, total


def _lineas_reservas_extraordinarias(filas: list[sqlite3.Row]) -> tuple[list[str], float]:
    """Reserva extraordinaria (categoría A, pedido de la clienta): el
    monto es el que tipeó el operador a mano (`MontoExtraordinario`), no
    uno calculado por hora×tarifa — y lo que se cobra es la descripción
    de texto libre (`ItemExtraordinario`), no un horario/lugar armado
    solo. A diferencia de `_lineas_reservas_aisladas`, nunca se agrupa ni
    se combina entre sí (cada una describe un cobro distinto, fundir dos
    ítems distintos en una sola línea les haría perder sentido) — una
    línea por cada una, ordenadas por fecha."""
    lineas: list[str] = []
    total = 0.0
    for f in sorted(filas, key=lambda f: (f["Fecha"], f["HoraInicio"])):
        dia_semana = DIAS_SEMANA[date.fromisoformat(f["Fecha"]).weekday()]
        monto = f["MontoExtraordinario"] or 0.0
        lineas.append(f"+ {dia_semana} {fecha_corta(f['Fecha'])} - {f['ItemExtraordinario']} {_moneda(monto)}")
        total += monto
    return lineas, total


def _lugar_llave(fila: sqlite3.Row, incluir_edificio: bool) -> str:
    """DC-03: línea de depósito/reintegro de llave — "unidad {Depto} [-
    Edificio {nombre}]" para llaves tipo Unidad; "edificio {nombre}" para
    llaves tipo Edificio, que ya identifican el edificio sin sufijo aparte."""
    if fila["TipoLlave"] == "Edificio":
        return f"edificio {fila['NombreEdificio']}"
    texto = f"unidad {fila['Departamento']}" if fila["Departamento"] else "unidad"
    if incluir_edificio and fila["NombreEdificio"]:
        texto += f" - Edificio {fila['NombreEdificio']}"
    return texto


def mensaje_detalle_reserva_aislada(
    conn: sqlite3.Connection, *, id_profesional: int, periodo: str,
    incluir_consultorio: bool = True, incluir_unidad: bool = True, incluir_edificio: bool = True,
    combinar_misma_unidad: bool = False, combinar_distintas_unidades: bool = False,
) -> str:
    """"DETALLE RESERVA {MES}" (DC-03, Mensaje 1, categoría A). Por defecto
    (los dos combinar en False) cada reserva aislada aparece en su propia
    línea — es el comportamiento pedido, reserva por reserva. Ver
    `_lineas_reservas_aisladas` para el detalle de qué hace cada combinar.

    "Regla del edificio" (si tiene llaves de más de un edificio, se agrega
    el edificio a cada línea aunque `incluir_edificio` esté en False) se
    resuelve mirando las llaves ACTIVAS (sin devolver) del profesional.

    Editable desde "Textos del sistema" (clave
    `mensaje_detalle_reserva_aislada`) — ver `app.negocio.plantillas_
    texto`: solo el encabezado (título + nombre) es texto de plantilla de
    verdad, el resto del cuerpo (armado con loops de reservas/llaves/
    pagos/etc.) se le entrega ya resuelto como la variable
    `{detalle_items}`, nunca editable línea por línea."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    anio, mes = (int(p) for p in periodo.split("-"))

    incluir_edificio = _incluir_edificio_efectivo(conn, incluir_edificio, id_profesional)

    partes_nombre = [p for p in (profesional["Tratamiento"], profesional["NombrePila"], profesional["Apellido"]) if p]
    lineas: list[str] = []

    filas = conn.execute(
        """
        SELECT ra.IdReservaAislada, ra.Fecha, ra.HoraInicio, ra.HoraFin, ra.AplicaRecargo, ra.EsReubicacion,
               ra.EsExtraordinaria, ra.ItemExtraordinario, ra.MontoExtraordinario,
               c.IdConsultorio, c.NumeroConsultorio, c.ValorHoraAisladaActual, u.Departamento,
               e.IdEdificio, e.Nombre AS NombreEdificio, e.Domicilio, loc.Localidad AS DomicilioLocalidad
        FROM ReservaAislada ra
        JOIN Consultorio c ON c.IdConsultorio = ra.IdConsultorio
        JOIN Unidad u ON u.IdUnidad = c.IdUnidad
        JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad
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
    # Las extraordinarias se cobran con el ítem de texto libre que tipeó
    # el operador, no con el cálculo hora×tarifa de las demás — se
    # separan ANTES de pasar por `_lineas_reservas_aisladas` (que asume
    # ese cálculo) y se formatean aparte con `_lineas_reservas_
    # extraordinarias`, pero siguen contando para "Regla del edificio"
    # más abajo (quedan en `del_mes`/`posteriores`, sin sacarlas de ahí).
    del_mes_normales = [f for f in del_mes if not f["EsExtraordinaria"]]
    del_mes_extraordinarias = [f for f in del_mes if f["EsExtraordinaria"]]
    posteriores_normales = [f for f in posteriores if not f["EsExtraordinaria"]]
    posteriores_extraordinarias = [f for f in posteriores if f["EsExtraordinaria"]]

    def _monto(f: sqlite3.Row) -> float:
        if f["EsReubicacion"]:
            # compensa una ausencia del mismo profesional en otro horario —
            # no genera cargo (confirmado por el usuario).
            return 0.0
        monto = (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraAisladaActual"]
        return monto * (1 + recargo_pct / 100) if f["AplicaRecargo"] else monto

    # 1. depósitos/reintegros de llaves del período: unidad primero, edificio después.
    llaves = conn.execute(
        """
        SELECT m.*, l.Tipo AS TipoLlave, u.Departamento, e.Nombre AS NombreEdificio
        FROM LlaveMovimiento m
        JOIN Llave l ON l.IdLlave = m.IdLlave
        LEFT JOIN LlaveAcceso la ON la.IdLlaveAcceso = (
            SELECT MIN(IdLlaveAcceso) FROM LlaveAcceso WHERE IdLlave = l.IdLlave
        )
        LEFT JOIN Unidad u ON u.IdUnidad = la.IdUnidad
        LEFT JOIN Edificio e ON e.IdEdificio = la.IdEdificio
        WHERE m.IdProfesional = ? AND m.Tipo IN ('Asignación', 'Devolución') AND m.Fecha LIKE ?
        ORDER BY CASE l.Tipo WHEN 'Unidad' THEN 0 WHEN 'Edificio' THEN 1 ELSE 2 END, m.IdMovimiento
        """,
        (id_profesional, prefijo_mes + "%"),
    ).fetchall()

    total_llaves = 0.0
    for ll in llaves:
        lugar_llave = _lugar_llave(ll, incluir_edificio)
        if ll["Tipo"] == "Asignación" and ll["DepositoCobrado"]:
            monto = ll["MontoCobrado"] or 0.0
            lineas.append(f"+ Depósito por llave {lugar_llave} {_moneda(monto)}")
            total_llaves += monto
        if ll["Tipo"] == "Devolución" and ll["DepositoReintegrado"]:
            monto = ll["MontoReintegrado"] or 0.0
            lineas.append(f"- Reintegro depósito llave {lugar_llave} {_moneda(-monto)}")
            total_llaves -= monto

    # 2. reservas del mes con valor, cronológicas.
    lineas_reservas, total_reservas = _lineas_reservas_aisladas(
        del_mes_normales, incluir_consultorio=incluir_consultorio, incluir_unidad=incluir_unidad,
        incluir_edificio=incluir_edificio, combinar_misma_unidad=combinar_misma_unidad,
        combinar_distintas_unidades=combinar_distintas_unidades, monto_fn=_monto,
    )
    lineas += lineas_reservas
    lineas_extraordinarias, total_extraordinarias = _lineas_reservas_extraordinarias(del_mes_extraordinarias)
    lineas += lineas_extraordinarias
    total_reservas += total_extraordinarias

    # 3. saldo pendiente/a favor del mes anterior — se omite si es cero.
    saldo_anterior = profesional["SaldoCuentaAnterior"] or 0.0
    if saldo_anterior > 0:
        lineas.append(f"+ Saldo pendiente mes anterior {_moneda(saldo_anterior)}")
    elif saldo_anterior < 0:
        lineas.append(f"- Saldo a favor mes anterior {_moneda(-saldo_anterior)}")

    # 4. pagos registrados en el mes en curso: una sola línea con los ajustes ya incluidos
    # (confirmado por el usuario — sin detalle pago por pago).
    pagos = conn.execute(
        "SELECT * FROM HistorialPagos WHERE IdProfesional = ? AND Fecha LIKE ? ORDER BY Fecha",
        (id_profesional, prefijo_mes + "%"),
    ).fetchall()
    total_pagos = sum(p["Monto"] for p in pagos)
    if pagos:
        lineas.append(f"- Pagos registrados en mes en curso {_moneda(abs(total_pagos))}")

    # 5. ítem libre opcional: CargoEspecial sin llave asociada (ajustes y bonificación
    # unificados, decisión confirmada durante la auditoría).
    items_libres = [
        c for c in obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=id_profesional, PeriodoImputado=periodo)
        if c["IdLlave"] is None
    ]
    total_item_libre = 0.0
    for c in items_libres:
        signo = "+" if c["Monto"] >= 0 else "-"
        lineas.append(f"{signo} {c['Concepto']} {_moneda(abs(c['Monto']))}")
        total_item_libre += c["Monto"]

    saldo_a_abonar = saldo_anterior + total_reservas + total_llaves + total_item_libre - total_pagos
    lineas += ["", f"SALDO A ABONAR: {_moneda(saldo_a_abonar)}"]

    if posteriores:
        lineas_posteriores, _ = _lineas_reservas_aisladas(
            posteriores_normales, incluir_consultorio=incluir_consultorio, incluir_unidad=incluir_unidad,
            incluir_edificio=incluir_edificio, combinar_misma_unidad=combinar_misma_unidad,
            combinar_distintas_unidades=combinar_distintas_unidades,
        )
        lineas_posteriores_extraordinarias, _ = _lineas_reservas_extraordinarias(posteriores_extraordinarias)
        lineas += ["", "RESERVAS POSTERIORES"] + lineas_posteriores + lineas_posteriores_extraordinarias

    edificios_mencionados: dict[int, sqlite3.Row] = {f["IdEdificio"]: f for f in del_mes + posteriores}
    if incluir_edificio and len(edificios_mencionados) > 1:
        lineas.append("")
        for e in edificios_mencionados.values():
            lineas.append(f"* Edificio {e['NombreEdificio']}: Corresponde a {e['Domicilio']}, {e['DomicilioLocalidad']}")

    pagos_sobre = [p for p in pagos if p["MedioPago"] == "Sobre en buzón" and p["FechaHoraRecogidaSobres"]]
    if pagos_sobre:
        ultimo = max(pagos_sobre, key=lambda p: p["FechaHoraRecogidaSobres"])
        dt = datetime.fromisoformat(ultimo["FechaHoraRecogidaSobres"])
        dia_semana = fecha_a_dia_semana(dt.date()).lower()
        hora = hora_fmt(dt.hour + dt.minute / 60)
        lineas += [
            "",
            f"* Nota: Se imputaron los pagos de los sobres recogidos en las unidades hasta el "
            f"{dia_semana} {dt.day}/{dt.month} a las {hora}.",
        ]

    plantilla = resolver_plantilla(
        conn, "mensaje_detalle_reserva_aislada", DEFAULT_DETALLE_RESERVA_AISLADA,
    )
    return sustituir_variables(plantilla, {
        "mes_mayus": mes_texto(mes).upper(),
        "nombre_profesional": " ".join(partes_nombre).upper(),
        "detalle_items": "\n".join(lineas),
    })


# -------------------------------------------------------- mensajes predefinidos (5.5)
# `sustituir_variables` se mudó a `app.negocio.plantillas_texto` (mismo
# mecanismo, ahora compartido también por los mensajes automáticos
# editables) — se reexporta arriba para no romper a quien ya la
# importaba de acá.
