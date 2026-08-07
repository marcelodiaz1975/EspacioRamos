"""Utilidades de días, meses y períodos ('AAAA-MM')."""
import calendar
import sqlite3
from datetime import date

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def fecha_a_dia_semana(fecha: date) -> str:
    """date.weekday() da 0=lunes..6=domingo, que es justo el orden de DIAS_SEMANA."""
    return DIAS_SEMANA[fecha.weekday()]


def fecha_actual(conn: sqlite3.Connection) -> date:
    """Hoy, respetando el modo de fecha ficticia (sección 2 del documento,
    Configuracion.ModoFechaFicticia/FechaFicticia) para poder testear
    escenarios de fin/inicio de mes sin depender del reloj real."""
    cfg = conn.execute(
        "SELECT ModoFechaFicticia, FechaFicticia FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    if cfg and cfg["ModoFechaFicticia"] and cfg["FechaFicticia"]:
        return date.fromisoformat(cfg["FechaFicticia"])
    return date.today()


def periodo_actual(conn: sqlite3.Connection) -> str:
    """'AAAA-MM' de hoy (o de la fecha ficticia si está activa)."""
    fecha = fecha_actual(conn)
    return f"{fecha.year:04d}-{fecha.month:02d}"


def primer_dia_mes(anio: int, mes: int) -> date:
    return date(anio, mes, 1)


def ultimo_dia_mes(anio: int, mes: int) -> date:
    return date(anio, mes, calendar.monthrange(anio, mes)[1])


def parsear_periodo(periodo: str) -> tuple[int, int]:
    anio, mes = (int(p) for p in periodo.split("-"))
    if not 1 <= mes <= 12:
        raise ValueError(f"Período inválido: {periodo!r}")
    return anio, mes


def sumar_meses(periodo: str, cantidad: int) -> str:
    """'AAAA-MM' desplazado `cantidad` meses (puede ser negativo)."""
    anio, mes = parsear_periodo(periodo)
    total = (anio * 12 + (mes - 1)) + cantidad
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def periodo_anterior(periodo: str) -> str:
    return sumar_meses(periodo, -1)
