"""Centro de mensajería (DC-02): máquina de 9 colores por profesional.

Solo categorías R y A participan. Para R el color se deriva de
SaldoCuentaAnterior, plan de pagos, plazo de pago extendido y estado de
envío de la liquidación del período; para A, de si ya se generó el
mensaje de detalle de aisladas. Las dos transiciones que no se pueden
derivar de otra tabla (marrón->amarillo, celeste->azul) se trackean en
EstadoMensajeriaPeriodo, sección por (profesional, período) — sin fila
todavía = arranque de mes (DC-02 §2.2 / DC-06 §4.2).

Precedencia de colores para R (violeta primero, después gris con
posible reactivación a rojo, después el resto):
    violeta > gris (± reactivación a rojo) > verde/marrón|amarillo/naranja|rojo
"""
from __future__ import annotations

import sqlite3
from datetime import date

from app.negocio.dias import fecha_actual, parsear_periodo, ultimo_dia_mes
from app.negocio.mensajes import liquidacion_del_periodo, plan_activo
from app.repositorio.registro import obtener_repositorio

COLORES_R = ("marron", "verde", "amarillo", "naranja", "rojo", "violeta", "gris")
COLORES_A = ("celeste", "azul")
COLORES_PENDIENTES_ENVIO = ("marron", "verde", "amarillo", "naranja", "rojo", "violeta", "celeste")
COLORES_ENVIADOS = ("azul", "gris")


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


def _tolerancia(conn: sqlite3.Connection) -> float:
    cfg = conn.execute("SELECT ToleranciaDeudaDescuento FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    return cfg["ToleranciaDeudaDescuento"] if cfg else 0.0


def _dias_reactivacion_rojo(conn: sqlite3.Connection) -> int:
    """DC-02 §2.5: reusa DiasAntesFinMesRecordatorioPlan (confirmado por el
    usuario), no un parámetro nuevo."""
    cfg = conn.execute(
        "SELECT DiasAntesFinMesRecordatorioPlan FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    return cfg["DiasAntesFinMesRecordatorioPlan"] if cfg else 5


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
    """Uno de los 9 colores de DC-02 §2.1, o None si la categoría no
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
        if _debe_reactivar_rojo(conn, id_profesional, periodo, hoy, tolerancia):
            return "rojo"
        return "gris"

    if saldo_anterior <= 0:
        return "verde"

    if saldo_anterior <= tolerancia:
        estado = _estado_periodo(conn, id_profesional, periodo)
        generado = bool(estado["MensajePrevioGenerado"]) if estado else False
        return "amarillo" if generado else "marron"

    return "rojo" if plan_activo(conn, id_profesional) is not None else "naranja"


def _debe_reactivar_rojo(
    conn: sqlite3.Connection, id_profesional: int, periodo: str, hoy: date, tolerancia: float,
) -> bool:
    """DC-02 §2.5: a X días de fin de mes, un gris con plan activo cuyo
    saldo del mes EN CURSO (SaldoCuentaActual, neto de pagos ya
    registrados) siga fuera de tolerancia vuelve a subir a rojo."""
    if plan_activo(conn, id_profesional) is None:
        return False
    anio, mes = parsear_periodo(periodo)
    dias_para_fin_de_mes = (ultimo_dia_mes(anio, mes) - hoy).days
    if dias_para_fin_de_mes > _dias_reactivacion_rojo(conn):
        return False
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    saldo_actual = profesional["SaldoCuentaActual"] or 0.0
    return saldo_actual > tolerancia
