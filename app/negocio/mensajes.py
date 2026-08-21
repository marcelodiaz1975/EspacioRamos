"""Mensajes de WhatsApp para el centro de mensajería (DC-02, DC-03).

DC-03 da la redacción EXACTA de cada mensaje (a diferencia del spec
general, que solo describía la estructura) — el texto de acá es literal
al documento, verificado además contra ejemplos reales que confirmó el
usuario (Mensaje 1 y Mensaje 3 grupal).

Las 5 situaciones (DC-02 §5) ya no se determinan por tolerancia/plan
directamente acá — se arman por color del Centro de mensajería
(`app.negocio.mensajeria.color_profesional`), que es quien resuelve la
máquina de estados completa (violeta, gris con reactivación, etc.). Cada
`mensaje_situacion_N` asume que el llamador (la pantalla) ya construyó el
mensaje correcto para el color/acción según la tabla de asignación de
DC-03 "Resumen de asignaciones" — no vuelven a validar el color acá.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Callable

from app.negocio.dias import DIAS_SEMANA, fecha_a_dia_semana, sumar_meses, ultimo_dia_mes
from app.negocio.feriados import feriados_relevantes_periodo
from app.negocio.formato import fecha_corta, hora_fmt, mes_texto, periodo_mm_aaaa
from app.negocio.lista_espera import calcular_coincidencia
from app.negocio.liquidaciones import CATEGORIAS_CON_LIQUIDACION_MENSUAL
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
    (DC-02 §5)."""
    profesional = _profesional_r(conn, id_profesional)
    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or ""
    dia_semana, fecha, _ = _fecha_y_dia_remanente(conn, hoy)
    saldo = _moneda(profesional["SaldoCuentaAnterior"] or 0.0)
    return (
        "MENSAJE AUTOMATICO\n\n"
        f"Al día de la fecha se registra un saldo de {saldo} correspondiente al período anterior, por ende se "
        f"retiene la liquidación para ser enviada el {dia_semana} {fecha} contemplando las nuevas cancelaciones "
        "que se vayan a realizar desde ahora hasta ese momento con el fin de que en este plazo se regularice la "
        "situación.\n\n"
        "Se recuerda que los descuentos por cantidad de horas semanales reservadas se realizan únicamente cuando "
        "el saldo está al día al momento de comenzar el nuevo mes, y por otro lado los saldos atrasados que "
        "queden al momento de enviar la nueva liquidación se ajustarán para mantener los mismos actualizados.\n\n"
        "Por cualquier consulta o duda acerca de lo expresado en este texto responder este mensaje para con "
        "gusto conversar todas las inquietudes que pudieran existir.\n\n"
        f"Saludos, {nombre_espacio}."
    )


def mensaje_situacion_2(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> str:
    """Amarillo, al activar el check de envío (DC-02 §5)."""
    profesional = _profesional_r(conn, id_profesional)
    anio, mes = periodo.split("-")
    return (
        f"Hola {nombre_para_mensaje(profesional)}, cómo estás..? Te envío la liquidación del mes de "
        f"{mes_texto(int(mes))} en forma manual tal cual te había adelantado que iba a hacer luego del mensaje "
        "que se disparó anteriormente en forma automática. Por cualquier cosa me escribís, saludos..!"
    )


def mensaje_situacion_3(conn: sqlite3.Connection, id_profesional: int, periodo: str, hoy: date) -> str:
    """Marrón, botón "Generar texto" (al generarlo pasa a amarillo — el
    llamador es responsable de avisarle a
    `app.negocio.mensajeria.marcar_mensaje_previo_generado`)."""
    profesional = _profesional_r(conn, id_profesional)
    anio, mes = periodo.split("-")
    dia_semana, fecha, dias = _fecha_y_dia_remanente(conn, hoy)
    cuando = _cuando_remanente(dias, dia_semana, fecha)
    saldo = _moneda(profesional["SaldoCuentaAnterior"] or 0.0)
    return (
        f"Hola {nombre_para_mensaje(profesional)}, cómo estás? {cuando} se van a mandar los archivos con las "
        f"liquidaciones de {mes_texto(int(mes))} a los profesionales que están al día con sus saldos, en tu "
        "caso se va a llegar un mensaje automático en lugar del PDF, esto es porque quedó un saldo pendiente de "
        f"{saldo} correspondiente al período anterior.\n\n"
        "Obviamente la diferencia no es significativa, yo luego de ese mensaje te mando el archivo en forma "
        "manual con los descuentos contemplados como siempre, solo te estoy anticipando esta secuencia para que "
        "no te sorprenda ya que todo se hace de manera automática.\n\n"
        "Luego del mensaje te escribo, saludos..!"
    )


def mensaje_situacion_4(conn: sqlite3.Connection, id_profesional: int) -> str:
    """Rojo con liquidación YA enviada, reactivado desde gris cerca de fin
    de mes (DC-02 §5)."""
    profesional = _profesional_r(conn, id_profesional)
    saldo_mes_en_curso = _moneda(profesional["SaldoCuentaActual"] or 0.0)
    return (
        f"Hola {nombre_para_mensaje(profesional)}, cómo estás..? Te recuerdo que en unos días se va a estar "
        f"cerrando el mes, a este momento el saldo a abonar del mes en curso incluyendo la cuota del plan de "
        f"pago es de {saldo_mes_en_curso}, tendrías alguna cancelación para informar o para realizar antes de "
        "que termine el mes?\n\n"
        "Recordá que no se pueden trasladar importes atrasados al próximo período cuando hay un plan de pagos "
        "vigente tal cual lo conversamos en su momento. Quedo atento a tu comentario, gracias."
    )


def mensaje_situacion_5(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> str:
    """Rojo con liquidación NO enviada (DC-02 §5)."""
    profesional = _profesional_r(conn, id_profesional)
    anio, mes = periodo.split("-")
    saldo = _moneda(profesional["SaldoCuentaAnterior"] or 0.0)
    return (
        f"Hola {nombre_para_mensaje(profesional)}, cómo estás..? El mes de {mes_texto(int(mes))} ya se "
        "encuentra cerrado en base a tu reserva actual, te va a llegar en breve un mensaje automático "
        "informándote que hay saldos para regularizar en lugar del archivo de la liquidación del mes.\n\n"
        "Como te informé hace unos días no se pueden trasladar saldos de un mes a otro cuando hay un plan de "
        f"pagos acordado. El saldo a regularizar es de {saldo}. Quedo atento a tu comentario para estar al "
        "tanto de como tenés pensado manejar la situación, aguardo tu respuesta, gracias."
    )


def mensaje_envio_liquidacion(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> str:
    """Mensaje 4 (DC-03): acompaña el PDF de liquidación. Asignado a
    verde/violeta/gris (botón) y verde/naranja/rojo/violeta/gris (check)."""
    _profesional_r(conn, id_profesional)
    anio, mes = periodo.split("-")
    return (
        "MENSAJE AUTOMATICO\n"
        "(no es necesario responder)\n\n"
        f"* Se adjunta liquidación correspondiente al mes de {mes_texto(int(mes))}\n"
        "* Abrir el archivo enseguida de recibirlo para que les quede en el teléfono\n"
        "* Revisar el contenido, por cualquier duda comunicarse con el administrador"
    )


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
    siguiente" a él, según el flujo de avance de mes)."""
    cfg = conn.execute("SELECT MensajesPlural FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    plural = bool(cfg["MensajesPlural"]) if cfg is None or cfg["MensajesPlural"] is None else bool(cfg["MensajesPlural"])
    nos_o_me = "nos" if plural else "me"

    anio, mes = (int(p) for p in periodo_liquidacion.split("-"))
    ultimo_dia = ultimo_dia_mes(anio, mes)
    mes_siguiente = sumar_meses(periodo_liquidacion, 1)
    mes_siguiente_mas1 = sumar_meses(periodo_liquidacion, 2)
    anio_sig, mes_sig = (int(p) for p in mes_siguiente.split("-"))
    primer_dia_siguiente = date(anio_sig, mes_sig, 1)

    lineas = [
        f"LIQUIDACIONES DE {mes_texto(mes_sig).upper()} - AVISOS VARIOS",
        "",
        "CIERRE DE RESERVA 👇",
        "",
        f"* El {DIAS_SEMANA[ultimo_dia.weekday()].lower()} {fecha_corta(ultimo_dia.isoformat())} cerramos las "
        f"reservas de {mes_texto(mes_sig)}. Por informes de pago, avisos de vacaciones o por cualquier otra "
        "cosa relacionada con las reservas escribir por privado hasta ese día inclusive.",
        "",
        "ENVIO DE LIQUIDACIONES 👇",
        "",
        f"* El {DIAS_SEMANA[primer_dia_siguiente.weekday()].lower()} {fecha_corta(primer_dia_siguiente.isoformat())} "
        "se enviarán a través de un programa en forma automática las liquidaciones sin otro mensaje "
        "complementario solo a los profesionales que estén sin saldos pendientes a la fecha.",
        "* No hace falta responder el mensaje, si se pide abrir en ese momento el archivo para que les quede "
        "en el teléfono.",
        "* Dichas liquidaciones contarán con los habituales descuentos por cantidad de horas semanales "
        "reservadas.",
        f"* El profesional que tenga alguna duda por su saldo actual puede escribir{nos_o_me} por privado para "
        f"consultar{nos_o_me} el estado de cuenta.",
    ]

    feriados = feriados_relevantes_periodo(conn, anio_sig, mes_sig)
    if feriados:
        esos_ese_dias = "esos días" if len(feriados) > 1 else "ese día"
        lineas += [
            "",
            f"FERIADOS MES DE {mes_texto(mes_sig).upper()} 👇",
            "",
            f"* Se descontará del cálculo de la liquidación lo correspondiente {_texto_feriados_grupal(feriados)} "
            f"dando por descontado en principio que el profesional no asiste al espacio en {esos_ese_dias}.",
            f"* El profesional que necesite trabajar en alguno de {esos_ese_dias} {nos_o_me} avisará cerca del "
            "momento los horarios que pudiera llegar a necesitar para ser asignados, los cuales pueden ser "
            "distintos a los que habitualmente se tienen reservados.",
            f"* Las que se coordinen para ser utilizadas en {esos_ese_dias} como siempre se incluirán y "
            f"detallarán en la próxima liquidación, en este caso la de {mes_texto(int(mes_siguiente_mas1.split('-')[1]))}.",
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


def _lineas_reservas_aisladas(
    filas: list[sqlite3.Row], *, incluir_consultorio: bool, incluir_unidad: bool, incluir_edificio: bool,
    combinar_misma_unidad: bool, combinar_distintas_unidades: bool,
    monto_fn: Callable[[sqlite3.Row], float] | None = None,
) -> tuple[list[str], float]:
    """Sección 5.1: sin combinar (default), cada reserva aislada aparece en
    su propia línea — es el comportamiento pedido para no perder el
    detalle reserva por reserva. Con "Combinar misma unidad" se funden en
    una sola línea las reservas del mismo día y consultorio, uniendo las
    franjas horarias con "y de". "Combinar distintas unidades" además
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
            grupos_ordenados = [[f] for f in reservas_dia]

        entradas = []  # (horarios, lugar, monto | None)
        for grupo in grupos_ordenados:
            horarios = " y de ".join(
                f"{hora_fmt(f['HoraInicio'])[:-2]} a {hora_fmt(f['HoraFin'])}" for f in grupo
            )
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
    resuelve mirando las llaves ACTIVAS (sin devolver) del profesional."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    anio, mes = (int(p) for p in periodo.split("-"))

    incluir_edificio = _incluir_edificio_efectivo(conn, incluir_edificio, id_profesional)

    partes_nombre = [p for p in (profesional["Tratamiento"], profesional["NombrePila"], profesional["Apellido"]) if p]
    lineas = [f"DETALLE RESERVA {mes_texto(mes).upper()}", " ".join(partes_nombre).upper(), ""]

    filas = conn.execute(
        """
        SELECT ra.IdReservaAislada, ra.Fecha, ra.HoraInicio, ra.HoraFin, ra.AplicaRecargo, ra.EsReubicacion,
               c.IdConsultorio, c.NumeroConsultorio, c.ValorHoraAisladaActual, u.Departamento,
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
        if f["EsReubicacion"]:
            # compensa una ausencia del mismo profesional en otro horario —
            # no genera cargo (confirmado por el usuario).
            return 0.0
        monto = (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraAisladaActual"]
        return monto * (1 + recargo_pct / 100) if f["AplicaRecargo"] else monto

    # 1. depósitos/reintegros de llaves del período: unidad primero, edificio después.
    llaves = conn.execute(
        """
        SELECT lp.*, l.Tipo AS TipoLlave, u.Departamento, e.Nombre AS NombreEdificio
        FROM LlaveProfesional lp
        JOIN Llave l ON l.IdLlave = lp.IdLlave
        LEFT JOIN LlaveAcceso la ON la.IdLlaveAcceso = (
            SELECT MIN(IdLlaveAcceso) FROM LlaveAcceso WHERE IdLlave = l.IdLlave
        )
        LEFT JOIN Unidad u ON u.IdUnidad = la.IdUnidad
        LEFT JOIN Edificio e ON e.IdEdificio = la.IdEdificio
        WHERE lp.IdProfesional = ? AND (lp.FechaEntrega LIKE ? OR lp.FechaDevolucion LIKE ?)
        ORDER BY CASE l.Tipo WHEN 'Unidad' THEN 0 WHEN 'Edificio' THEN 1 ELSE 2 END, lp.IdLlaveProfesional
        """,
        (id_profesional, prefijo_mes + "%", prefijo_mes + "%"),
    ).fetchall()

    total_llaves = 0.0
    for ll in llaves:
        lugar_llave = _lugar_llave(ll, incluir_edificio)
        if ll["FechaEntrega"] and ll["FechaEntrega"].startswith(prefijo_mes) and ll["DepositoCobrado"]:
            monto = ll["MontoCobrado"] or 0.0
            lineas.append(f"+ Depósito por llave {lugar_llave} {_moneda(monto)}")
            total_llaves += monto
        if ll["FechaDevolucion"] and ll["FechaDevolucion"].startswith(prefijo_mes) and ll["DepositoReintegrado"]:
            monto = ll["MontoReintegrado"] or 0.0
            lineas.append(f"- Reintegro depósito llave {lugar_llave} {_moneda(-monto)}")
            total_llaves -= monto

    # 2. reservas del mes con valor, cronológicas.
    lineas_reservas, total_reservas = _lineas_reservas_aisladas(
        del_mes, incluir_consultorio=incluir_consultorio, incluir_unidad=incluir_unidad,
        incluir_edificio=incluir_edificio, combinar_misma_unidad=combinar_misma_unidad,
        combinar_distintas_unidades=combinar_distintas_unidades, monto_fn=_monto,
    )
    lineas += lineas_reservas

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
        signo = "+" if c["Tipo"] == "Débito" else "-"
        lineas.append(f"{signo} {c['Concepto']} {_moneda(abs(c['Monto']))}")
        total_item_libre += c["Monto"] if c["Tipo"] == "Débito" else -c["Monto"]

    saldo_a_abonar = saldo_anterior + total_reservas + total_llaves + total_item_libre - total_pagos
    lineas += ["", f"SALDO A ABONAR: {_moneda(saldo_a_abonar)}"]

    if posteriores:
        lineas_posteriores, _ = _lineas_reservas_aisladas(
            posteriores, incluir_consultorio=incluir_consultorio, incluir_unidad=incluir_unidad,
            incluir_edificio=incluir_edificio, combinar_misma_unidad=combinar_misma_unidad,
            combinar_distintas_unidades=combinar_distintas_unidades,
        )
        lineas += ["", "RESERVAS POSTERIORES"] + lineas_posteriores

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

    return "\n".join(lineas)


# ------------------------------------------------------ disponibilidad horarios (5.2)

def _mapa_consultorios_basico(conn: sqlite3.Connection, ids_consultorio: set[int]) -> dict[int, sqlite3.Row]:
    if not ids_consultorio:
        return {}
    placeholders = ", ".join("?" for _ in ids_consultorio)
    filas = conn.execute(
        f"""
        SELECT c.IdConsultorio, c.NumeroConsultorio, u.Departamento, e.NombreEdificio
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad
        JOIN (SELECT IdEdificio, Nombre AS NombreEdificio FROM Edificio) e ON e.IdEdificio = u.IdEdificio
        WHERE c.IdConsultorio IN ({placeholders})
        """,
        list(ids_consultorio),
    ).fetchall()
    return {f["IdConsultorio"]: f for f in filas}


def mensaje_disponibilidad_horarios(
    conn: sqlite3.Connection, *, periodo: str, dias: list[str], horario_desde: float, horario_hasta: float,
    tipo_combinacion: str = "O", condiciones_consultorio: dict | None = None,
    incluir_consultorio: bool = True, incluir_unidad: bool = True, incluir_edificio: bool = True,
) -> str:
    """"Disponibilidad período {MM/AAAA}" (sección 5.2): reusa el mismo
    motor de cruce que la lista de espera (`lista_espera.calcular_coincidencia`)
    contra un pedido armado al vuelo, sin necesidad de persistirlo en
    ListaEspera. Cuando un día necesita combinar más de un consultorio
    para cubrir todo el horario pedido, cada tramo se lista aparte con
    guión indentado debajo del día (sección 5.2: "combinación con punto y
    guión indentado")."""
    incluir_edificio = _incluir_edificio_efectivo(conn, incluir_edificio)
    anio, mes = (int(p) for p in periodo.split("-"))
    pedido = {
        "Bloques": [{
            "Dias": json.dumps(dias), "HorarioDesde": horario_desde, "HorarioHasta": horario_hasta,
            "TipoCombinacionDias": tipo_combinacion,
        }],
        "TipoCombinacion": "O",  # un solo bloque: no influye
        "CondicionesConsultorio": json.dumps(condiciones_consultorio or {}),
    }
    coincidencia = calcular_coincidencia(conn, pedido, anio, mes)

    lineas = [
        f"Disponibilidad período {periodo_mm_aaaa(periodo)}",
        "",
        f"Días y horarios de interés: {', '.join(dias)}, de {hora_fmt(horario_desde)[:-2]} a "
        f"{hora_fmt(horario_hasta)}",
    ]
    if condiciones_consultorio:
        partes = [NOMBRES_CONDICION[k] for k, v in condiciones_consultorio.items() if v and k in NOMBRES_CONDICION]
        if condiciones_consultorio.get("tamano"):
            partes.append(f"tamaño {condiciones_consultorio['tamano']}")
        if partes:
            lineas.append(f"Características: {', '.join(partes)}")
    lineas.append("")

    if coincidencia is None:
        lineas.append("Sin disponibilidad para lo solicitado.")
        return "\n".join(lineas)

    ids_consultorio = {t.id_consultorio for tramos in coincidencia.tramos_por_dia.values() for t in tramos}
    consultorios = _mapa_consultorios_basico(conn, ids_consultorio)

    lineas.append("Alternativas disponibles:")
    for dia, tramos in coincidencia.tramos_por_dia.items():
        if len(tramos) == 1:
            t = tramos[0]
            lugar = _lugar_reserva(consultorios[t.id_consultorio], incluir_consultorio, incluir_unidad, incluir_edificio)
            sufijo = f" {lugar}" if lugar else ""
            lineas.append(f"· {dia} de {hora_fmt(t.hora_inicio)[:-2]} a {hora_fmt(t.hora_fin)}{sufijo}")
        else:
            lineas.append(f"· {dia}:")
            for t in tramos:
                lugar = _lugar_reserva(consultorios[t.id_consultorio], incluir_consultorio, incluir_unidad, incluir_edificio)
                sufijo = f" {lugar}" if lugar else ""
                lineas.append(f"  - {hora_fmt(t.hora_inicio)[:-2]} a {hora_fmt(t.hora_fin)}{sufijo}")
    return "\n".join(lineas)


# -------------------------------------------------------- mensajes predefinidos (5.5)

def sustituir_variables(texto: str, variables: dict[str, str]) -> str:
    """Reemplaza "{variable}" en el texto de un MensajePredefinido por su
    valor. Los saltos de línea del texto guardado se respetan tal cual
    (no hace falta hacer nada especial: son parte del `texto`)."""
    resultado = texto
    for clave, valor in variables.items():
        resultado = resultado.replace(f"{{{clave}}}", str(valor))
    return resultado
