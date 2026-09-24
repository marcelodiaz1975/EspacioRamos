"""Balance del negocio (Ingresos/Gastos/Resultado, reordenamiento de
formularios): Ingresos y Resultado son 100% en vivo, con el mismo
alcance de ubicación de 4 niveles (Localidad/Edificio/Unidad/
Consultorio, "el más específico manda") que usa Estadísticas Varias —
ver `app.negocio.estadisticas._ids_consultorio_del_alcance`, reusada
acá. Gastos operativos, en cambio, tiene su propio Alcance de 3 niveles
(Espacio general/Edificio/Unidad, sin Consultorio) — `_alcance_gastos_
del_filtro` traduce uno al otro: confirmado con la clienta, cuando se
elige cualquier filtro puntual (Localidad/Edificio/Unidad/Consultorio)
los gastos "Espacio general" quedan afuera del Resultado de ese lugar,
por no ser atribuibles a un lugar puntual — solo entran cuando los
cuatro filtros están en "Todos" (todo el espacio).

Ingresos, tres componentes:
- Horas regulares / horas aisladas: netos (con descuento por volumen y
  recargo de aisladas ya aplicados), reusando `app.negocio.estadisticas.
  monto_neto_regular_periodo`/`monto_neto_aislada_periodo` — mismo
  criterio "monto real facturado" que Estadísticas.
- "Feriado trabajado" (DC-01 §1.5, DC-11 caso 2): un feriado no se
  cobra (se descuenta de la liquidación, el profesional no usa el
  espacio ese día) salvo que decida usarlo — ahí se carga un cargo
  aparte que puede caer en la liquidación del mes del feriado (si se
  avisa antes de emitirla) o en la del mes siguiente (si se avisa
  después) — confirmado por la clienta: "quiero que se contemple
  dentro de los ingresos en el período en el cual se carga en la
  liquidación, no importa la fecha del feriado". Esa resolución (qué
  período le corresponde a cada feriado trabajado) ya existe en
  `app.negocio.liquidaciones._calcular_feriados_trabajados` — se reusa
  tal cual acá, para todos los profesionales R del sistema, en vez de
  reimplementarla.

Simplificación deliberada, misma que ya tiene `monto_neto_regular_
periodo`: el descuento por volumen de horas semanales se aplica
siempre (no se replica la suspensión por saldo atrasado,
`pierde_descuento`, que es un caso de liquidación puntual por
profesional) — igual que Estadísticas, esto es un informe agregado, no
una liquidación."""
from __future__ import annotations

import sqlite3

from app.negocio.dias import parsear_periodo
from app.negocio.estadisticas import (
    _ids_consultorio_del_alcance,
    monto_neto_aislada_periodo,
    monto_neto_regular_periodo,
)
from app.negocio.liquidaciones import (
    CATEGORIAS_CON_LIQUIDACION_MENSUAL,
    _calcular_feriados_trabajados,
    ids_consolidados,
)
from app.repositorio.registro import obtener_repositorio


def ingresos_feriados_trabajados_periodo(
    conn: sqlite3.Connection, periodo: str, ids_consultorio: list[int] | None = None,
) -> float:
    """Monto de "feriado trabajado" que efectivamente cae en una
    liquidación de `periodo` (ver el docstring del módulo) — recorre
    todos los profesionales R del sistema, reusando la misma resolución
    de período que ya usa el cálculo de liquidación."""
    if ids_consultorio is not None and not ids_consultorio:
        return 0.0
    cfg = conn.execute("SELECT RecargoPorcentajeAisladas FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    recargo_pct = cfg["RecargoPorcentajeAisladas"] if cfg else 0.0
    total = 0.0
    for profesional in obtener_repositorio(conn, "Profesional").listar():
        if profesional["CategoriaProfesional"] not in CATEGORIAS_CON_LIQUIDACION_MENSUAL:
            continue
        ids = ids_consolidados(conn, profesional["IdProfesional"])
        mes_anterior, mes_en_curso = _calcular_feriados_trabajados(
            conn, ids, profesional["IdProfesional"], periodo, False, recargo_pct,
        )
        for item in (*mes_anterior, *mes_en_curso):
            if ids_consultorio is None or item.id_consultorio in ids_consultorio:
                total += item.monto
    return total


def total_ingresos_periodo(
    conn: sqlite3.Connection, periodo: str, ids_consultorio: list[int] | None = None,
) -> tuple[float, float, float]:
    """(regulares, aisladas, feriados trabajados) netos del período,
    para el alcance de `ids_consultorio` (`None` = todo el sistema)."""
    anio, mes = parsear_periodo(periodo)
    return (
        monto_neto_regular_periodo(conn, anio, mes, ids_consultorio),
        monto_neto_aislada_periodo(conn, anio, mes, ids_consultorio),
        ingresos_feriados_trabajados_periodo(conn, periodo, ids_consultorio),
    )


def _alcance_gastos_del_filtro(
    conn: sqlite3.Connection, *,
    id_localidad: int | None = None, id_edificio: int | None = None,
    id_unidad: int | None = None, id_consultorio: int | None = None,
) -> tuple[list[int] | None, list[int] | None, bool]:
    """Traduce el alcance de 4 niveles de Ingresos/Resultado al Alcance
    de 3 niveles de Gastos operativos: devuelve (ids_edificio,
    ids_unidad, incluye_generales). Sin ningún filtro puntual, devuelve
    (None, None, True) — todo el sistema, generales incluidos. Con
    cualquier filtro puntual, los gastos "Espacio general" quedan
    afuera (confirmado por la clienta, ver el docstring del módulo)."""
    if id_consultorio is None and id_unidad is None and id_edificio is None and id_localidad is None:
        return None, None, True
    if id_consultorio is not None:
        fila = conn.execute("SELECT IdUnidad FROM Consultorio WHERE IdConsultorio = ?", (id_consultorio,)).fetchone()
        id_unidad = fila["IdUnidad"] if fila else None
    if id_unidad is not None:
        fila = conn.execute("SELECT IdEdificio FROM Unidad WHERE IdUnidad = ?", (id_unidad,)).fetchone()
        return ([fila["IdEdificio"]] if fila else []), [id_unidad], False
    if id_edificio is not None:
        filas = conn.execute("SELECT IdUnidad FROM Unidad WHERE IdEdificio = ?", (id_edificio,)).fetchall()
        return [id_edificio], [f["IdUnidad"] for f in filas], False
    filas_edificio = conn.execute("SELECT IdEdificio FROM Edificio WHERE IdLocalidad = ?", (id_localidad,)).fetchall()
    filas_unidad = conn.execute(
        "SELECT u.IdUnidad FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio WHERE e.IdLocalidad = ?",
        (id_localidad,),
    ).fetchall()
    return [f["IdEdificio"] for f in filas_edificio], [f["IdUnidad"] for f in filas_unidad], False


def total_gastos_periodo(
    conn: sqlite3.Connection, periodo: str, *,
    id_localidad: int | None = None, id_edificio: int | None = None,
    id_unidad: int | None = None, id_consultorio: int | None = None,
) -> float:
    ids_edificio, ids_unidad, incluye_generales = _alcance_gastos_del_filtro(
        conn, id_localidad=id_localidad, id_edificio=id_edificio, id_unidad=id_unidad, id_consultorio=id_consultorio,
    )
    total = 0.0
    for gasto in obtener_repositorio(conn, "GastoOperativo").listar(Periodo=periodo):
        monto = gasto["Monto"] or 0.0
        if gasto["Alcance"] == "Espacio general":
            if incluye_generales:
                total += monto
        elif gasto["Alcance"] == "Edificio":
            if ids_edificio is None or gasto["IdEdificio"] in ids_edificio:
                total += monto
        elif gasto["Alcance"] == "Unidad":
            if ids_unidad is None or gasto["IdUnidad"] in ids_unidad:
                total += monto
    return total


def resultado_periodo(
    conn: sqlite3.Connection, periodo: str, *,
    id_localidad: int | None = None, id_edificio: int | None = None,
    id_unidad: int | None = None, id_consultorio: int | None = None,
) -> tuple[float, float, float]:
    """(ingresos, gastos, resultado) del período para el alcance de
    ubicación elegido."""
    ids_consultorio = _ids_consultorio_del_alcance(
        conn, id_localidad=id_localidad, id_edificio=id_edificio, id_unidad=id_unidad, id_consultorio=id_consultorio,
    )
    regulares, aisladas, feriados_trabajados = total_ingresos_periodo(conn, periodo, ids_consultorio)
    ingresos = regulares + aisladas + feriados_trabajados
    gastos = total_gastos_periodo(
        conn, periodo, id_localidad=id_localidad, id_edificio=id_edificio,
        id_unidad=id_unidad, id_consultorio=id_consultorio,
    )
    return ingresos, gastos, ingresos - gastos
