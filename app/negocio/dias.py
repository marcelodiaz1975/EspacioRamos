"""Utilidades de días, meses y períodos ('AAAA-MM')."""
import calendar
import sqlite3
from datetime import date

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def fecha_a_dia_semana(fecha: date) -> str:
    """date.weekday() da 0=lunes..6=domingo, que es justo el orden de DIAS_SEMANA."""
    return DIAS_SEMANA[fecha.weekday()]


def periodo_operativo_actual(conn: sqlite3.Connection) -> str:
    """'AAAA-MM' en el que `app.negocio.avance_mes.avanzar_mes` dejó parado
    al operador la última vez — el ancla de la que recorta `fecha_actual`
    más abajo. Independiente del modo fecha ficticia (QA): esto rige
    siempre, incluso en uso real con ese modo apagado (pedido explícito de
    la clienta, probando el sistema "en forma real, sin el modo QA")."""
    cfg = conn.execute(
        "SELECT PeriodoOperativoActual FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    if cfg and cfg["PeriodoOperativoActual"]:
        return cfg["PeriodoOperativoActual"]
    hoy = date.today()
    return f"{hoy.year:04d}-{hoy.month:02d}"


def fecha_actual(conn: sqlite3.Connection) -> date:
    """Hoy para toda la lógica de negocio del sistema.

    En modo fecha ficticia (sección 2 del documento, Configuracion.
    ModoFechaFicticia/FechaFicticia) devuelve esa fecha fija, para testear
    escenarios de fin/inicio de mes sin depender del reloj real.

    Fuera de ese modo (uso real), devuelve la fecha real de hoy recortada
    para que nunca caiga afuera del mes de `periodo_operativo_actual`
    (confirmado por la clienta): si "Avanzar de mes" ya dejó al operador
    parado en un período que la fecha real todavía no alcanzó, se
    devuelve el día 1 de ese período, fijo, hasta que la realidad llegue
    — ahí "se rompe lo virtual" y se empieza a devolver la fecha real tal
    cual. Simétricamente, si la fecha real ya cruzó a un mes nuevo pero
    todavía no se apretó "Avanzar de mes", se sigue devolviendo el último
    día del período operativo (el que falta cerrar) en vez de la fecha
    real."""
    cfg = conn.execute(
        "SELECT ModoFechaFicticia, FechaFicticia FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    if cfg and cfg["ModoFechaFicticia"] and cfg["FechaFicticia"]:
        return date.fromisoformat(cfg["FechaFicticia"])

    anio, mes = parsear_periodo(periodo_operativo_actual(conn))
    primero, ultimo = primer_dia_mes(anio, mes), ultimo_dia_mes(anio, mes)
    return min(max(date.today(), primero), ultimo)


def periodo_actual(conn: sqlite3.Connection) -> str:
    """'AAAA-MM' de `fecha_actual`."""
    fecha = fecha_actual(conn)
    return f"{fecha.year:04d}-{fecha.month:02d}"


def fecha_real(conn: sqlite3.Connection) -> date:
    """Hoy de VERDAD, sin el recorte al período operativo que hace
    `fecha_actual` (sigue respetando el modo fecha ficticia de QA, que
    es la fecha "real" simulada mientras se prueba el sistema).

    Caso real de la clienta: hizo "Avanzar de mes" con todavía unos días
    de octubre por delante (parado virtualmente en noviembre), y el
    cuadrito de cumpleaños dejó de mostrarle uno que caía el 29/10 (hoy
    real) porque `fecha_actual` ya devolvía el 01/11 (recortada al
    período operativo nuevo) — para un recordatorio ("desde el día en
    curso en adelante") lo que importa es la fecha real del calendario,
    no en qué período quedó posicionado el sistema para la liquidación.
    `periodo_operativo_actual`/`fecha_actual` siguen siendo lo correcto
    para cualquier cálculo de NEGOCIO atado al período (liquidaciones,
    ocupación, etc.) — esta función es solo para esos recordatorios."""
    cfg = conn.execute(
        "SELECT ModoFechaFicticia, FechaFicticia FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    if cfg and cfg["ModoFechaFicticia"] and cfg["FechaFicticia"]:
        return date.fromisoformat(cfg["FechaFicticia"])
    return date.today()


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
