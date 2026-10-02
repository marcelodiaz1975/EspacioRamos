"""Centro de mensajería (DC-02): máquina de 10 colores por profesional.

Solo categorías R y A participan. Para R el color se deriva de
SaldoCuentaAnterior, plan de pagos, plazo de pago extendido y estado de
envío de la liquidación del período; para A, de si ya se generó el
mensaje de detalle de aisladas. Las transiciones que no se pueden derivar
de otra tabla (marrón->amarillo, celeste->azul, gris->bordó->gris) se
trackean en EstadoMensajeriaPeriodo, sección por (profesional, período) —
sin fila todavía = arranque de mes, nunca bordó (DC-02 §2.2 / DC-06 §4.2).

Precedencia de colores para R (violeta primero, después gris con posible
recordatorio de fin de mes, después el resto):
    violeta > gris (± bordó) > verde/marrón|amarillo/naranja/rojo

Bordó (pedido de la clienta, posterior a DC-02/DC-03): reemplaza a la
vieja reactivación gris->rojo cerca de fin de mes (que solo miraba plan de
pago + deuda del mes en curso) — la clienta la descartó explícitamente y
pidió en su lugar un recordatorio que aplica a CUALQUIER profesional R con
reserva regular activa, sin importar deuda ni plan: a partir de
`DiasAntesFinMesRecordatorioGeneral` días de fin de mes, un gris con
reserva regular activa pasa a bordó; al generar su mensaje (botón
"Generar texto") vuelve a gris por el resto del período, aunque sigan
dándose las mismas condiciones — se trackea con
`RecordatorioMensajeriaGenerado`, mismo mecanismo que marrón->amarillo
pero a la inversa (de urgente a calmo en vez de al revés)."""
from __future__ import annotations

import sqlite3
from datetime import date

from app.negocio.dias import fecha_actual, parsear_periodo, ultimo_dia_mes
from app.negocio.mensajes import liquidacion_del_periodo, plan_activo
from app.repositorio.registro import obtener_repositorio

COLORES_R = ("marron", "verde", "amarillo", "naranja", "rojo", "violeta", "bordo", "gris")
COLORES_A = ("celeste", "azul")
COLORES_PENDIENTES_ENVIO = ("marron", "verde", "amarillo", "naranja", "rojo", "violeta", "celeste")
COLORES_ENVIADOS = ("azul", "bordo", "gris")


def _estado_periodo(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> sqlite3.Row | None:
    filas = obtener_repositorio(conn, "EstadoMensajeriaPeriodo").listar(IdProfesional=id_profesional, Periodo=periodo)
    return filas[0] if filas else None


def _obtener_o_crear_estado_periodo(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> sqlite3.Row:
    estado = _estado_periodo(conn, id_profesional, periodo)
    if estado is not None:
        return estado
    repo = obtener_repositorio(conn, "EstadoMensajeriaPeriodo")
    id_estado = repo.crear(IdProfesional=id_profesional, Periodo=periodo)
    return repo.obtener(id_estado)


def marcar_mensaje_previo_generado(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> None:
    """Marrón -> amarillo (DC-02 §2.1): se llama al generar el texto de la
    Situación 3 (mensaje previo) para un profesional marrón."""
    estado = _obtener_o_crear_estado_periodo(conn, id_profesional, periodo)
    obtener_repositorio(conn, "EstadoMensajeriaPeriodo").actualizar(
        estado["IdEstadoMensajeria"], MensajePrevioGenerado=1,
    )


def marcar_mensaje_aislada_generado(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> None:
    """Celeste -> azul (DC-02 §2.1): se llama al generar el Mensaje 1 (detalle
    de aisladas) para un profesional celeste. Idempotente para azul."""
    estado = _obtener_o_crear_estado_periodo(conn, id_profesional, periodo)
    obtener_repositorio(conn, "EstadoMensajeriaPeriodo").actualizar(
        estado["IdEstadoMensajeria"], MensajeAisladaGenerado=1,
    )


def marcar_recordatorio_mensajeria_generado(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> None:
    """Bordó -> gris: se llama al generar el texto del recordatorio de fin
    de mes para un profesional bordó. A diferencia de marrón->amarillo/
    celeste->azul (que suben de urgencia), esta transición baja: una vez
    generado, el profesional se queda en gris el resto del período aunque
    sigan dándose las mismas condiciones (reserva regular activa, dentro
    de la ventana de días antes de fin de mes)."""
    estado = _obtener_o_crear_estado_periodo(conn, id_profesional, periodo)
    obtener_repositorio(conn, "EstadoMensajeriaPeriodo").actualizar(
        estado["IdEstadoMensajeria"], RecordatorioMensajeriaGenerado=1,
    )


def _tolerancia(conn: sqlite3.Connection) -> float:
    cfg = conn.execute("SELECT ToleranciaDeudaDescuento FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    return cfg["ToleranciaDeudaDescuento"] if cfg else 0.0


def _dias_recordatorio_mensajeria(conn: sqlite3.Connection) -> int:
    """Días antes de fin de mes para activar el recordatorio bordó — reusa
    `DiasAntesFinMesRecordatorioGeneral` (ya existía en el schema sin
    ningún lector), expuesto en Configuración general / Valores y
    liquidación."""
    cfg = conn.execute(
        "SELECT DiasAntesFinMesRecordatorioGeneral FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    return cfg["DiasAntesFinMesRecordatorioGeneral"] if cfg else 5


def _reserva_regular_activa(conn: sqlite3.Connection, id_profesional: int, hoy: date) -> bool:
    """Mismo criterio que `app.negocio.panel_control._reserva_regular_activa`
    (duplicado acá, módulos sin relación entre sí — incluso siendo los dos
    de negocio, ese helper es privado de su módulo)."""
    hoy_iso = hoy.isoformat()
    return conn.execute(
        "SELECT 1 FROM ReservaRegular WHERE IdProfesional = ? AND VigenciaInicio <= ? "
        "AND (VigenciaFin IS NULL OR VigenciaFin >= ?) LIMIT 1",
        (id_profesional, hoy_iso, hoy_iso),
    ).fetchone() is not None


def _plazo_vigente(profesional: sqlite3.Row, hoy: date) -> bool:
    plazo = profesional["PlazoPagoExtendido"]
    if not plazo:
        return False
    try:
        return date.fromisoformat(plazo) >= hoy
    except ValueError:
        return False


def _limpiar_plazo_extendido(conn: sqlite3.Connection, id_profesional: int) -> None:
    obtener_repositorio(conn, "Profesional").actualizar(
        id_profesional, PlazoPagoExtendido=None, MotivoPlazoExtra=None,
    )


def limpiar_plazos_vencidos_o_regularizados(conn: sqlite3.Connection) -> None:
    """DC-02 §2.4: al vencer el plazo sin marcar enviado, o al regularizarse
    el saldo (confirmado por el usuario: "se pone en cero o entra en
    tolerancia"), el plazo se borra solo y el profesional pasa al color que
    corresponda según su deuda real. Se llama en cada refresco de la
    pantalla — no hace falta un paso de avance de mes para esto."""
    hoy = fecha_actual(conn)
    tolerancia = _tolerancia(conn)
    for p in obtener_repositorio(conn, "Profesional").listar(CategoriaProfesional="R"):
        if not p["PlazoPagoExtendido"]:
            continue
        saldo_anterior = p["SaldoCuentaAnterior"] or 0.0
        vigente = _plazo_vigente(p, hoy)
        dentro_tolerancia = saldo_anterior <= tolerancia
        if not vigente or dentro_tolerancia:
            _limpiar_plazo_extendido(conn, p["IdProfesional"])


def color_profesional(conn: sqlite3.Connection, profesional: sqlite3.Row, periodo: str) -> str | None:
    """Uno de los 10 colores (DC-02 §2.1 + bordó), o None si la categoría no
    participa del Centro de mensajería (ni R ni A). Asume que
    `limpiar_plazos_vencidos_o_regularizados` ya corrió en este refresco —
    no vuelve a limpiar acá para no mezclar lectura con escritura."""
    categoria = profesional["CategoriaProfesional"]
    id_profesional = profesional["IdProfesional"]

    if categoria == "A":
        estado = _estado_periodo(conn, id_profesional, periodo)
        generado = bool(estado["MensajeAisladaGenerado"]) if estado else False
        return "azul" if generado else "celeste"

    if categoria != "R":
        return None

    hoy = fecha_actual(conn)
    tolerancia = _tolerancia(conn)
    saldo_anterior = profesional["SaldoCuentaAnterior"] or 0.0

    if _plazo_vigente(profesional, hoy) and saldo_anterior > tolerancia:
        return "violeta"

    liquidacion = liquidacion_del_periodo(conn, id_profesional, periodo)
    if liquidacion is not None and liquidacion["EstadoEnvio"] == "Enviada":
        if _debe_recordar_fin_de_mes(conn, id_profesional, periodo, hoy):
            return "bordo"
        return "gris"

    if saldo_anterior <= 0:
        return "verde"

    if saldo_anterior <= tolerancia:
        estado = _estado_periodo(conn, id_profesional, periodo)
        generado = bool(estado["MensajePrevioGenerado"]) if estado else False
        return "amarillo" if generado else "marron"

    return "rojo" if plan_activo(conn, id_profesional) is not None else "naranja"


def _debe_recordar_fin_de_mes(conn: sqlite3.Connection, id_profesional: int, periodo: str, hoy: date) -> bool:
    """Gris -> bordó: a N días de fin de mes (parámetro configurable), un
    gris con reserva regular activa que todavía no generó su recordatorio
    este período pasa a bordó. Sin importar deuda ni plan de pago —
    aplica a CUALQUIER profesional R que siga reservando regular, pedido
    explícito de la clienta al descartar la vieja reactivación a rojo."""
    estado = _estado_periodo(conn, id_profesional, periodo)
    if estado is not None and estado["RecordatorioMensajeriaGenerado"]:
        return False
    anio, mes = parsear_periodo(periodo)
    dias_para_fin_de_mes = (ultimo_dia_mes(anio, mes) - hoy).days
    if dias_para_fin_de_mes > _dias_recordatorio_mensajeria(conn):
        return False
    return _reserva_regular_activa(conn, id_profesional, hoy)
