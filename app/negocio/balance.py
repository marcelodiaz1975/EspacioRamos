"""Balance del negocio (Ingresos/Gastos/Resultado, reordenamiento de
formularios): Ingresos y Resultado son 100% en vivo, con el mismo
alcance de ubicación de 4 niveles (Localidad/Edificio/Unidad/
Consultorio, "el más específico manda") que usa Estadísticas Varias —
ver `app.negocio.estadisticas._ids_consultorio_del_alcance`, reusada
acá.

Gastos operativos (desde que sumó su propio nivel Consultorio, ver
`app.negocio.gastos_operativos.ALCANCES_GASTO`) tiene exactamente los
mismos 4 niveles que el alcance de Ingresos/Resultado — pero un gasto se
carga a UN nivel puntual (o a "Espacio general"), nunca a un Consultorio
y a su Edificio a la vez. Pedido explícito de la clienta sobre cómo
repartir un gasto cargado a un nivel superior entre los filtros más
específicos de abajo: se prorratea en PARTES IGUALES, en cascada, nivel
por nivel ("si pago publicidad para todo el espacio... la voy dividiendo
en partes iguales" — un gasto de "Espacio general" se divide por
igual entre todas las Localidades que haya, lo que le toca a cada una se
vuelve a dividir por igual entre sus Edificios, de ahí entre sus
Unidades, y de ahí entre sus Consultorios; un gasto de Edificio arranca
esa misma cascada un escalón más abajo, de Unidad un escalón más abajo
todavía). La clienta aceptó explícitamente que esto quede desproporcionado
frente a la real incidencia de cada rama en los ingresos (una Localidad
con muchos edificios absorbe la misma porción por Localidad que una con
uno solo) — "es muy difícil que todo sea exacto... no termina siendo
relevante" obsesionarse con un reparto proporcional de verdad.

`_distribuir_gasto_por_consultorio` calcula, para un gasto puntual, el
monto que le llega a CADA Consultorio alcanzado por esa cascada —
`total_gastos_periodo` suma esas porciones para los consultorios del
filtro pedido (vía `_ids_consultorio_del_alcance`, el mismo helper que ya
usa Ingresos). Una rama sin hijos en algún escalón (ej. un Edificio
cargado sin ninguna Unidad todavía) no reparte nada de esa porción a
ningún Consultorio — se pierde, mismo criterio de imprecisión aceptada
que el resto del modelo (y consistente con que esa rama tampoco aporta
ningún Ingreso: sin Unidad no hay Consultorio que se pueda reservar).
Sin ningún filtro (alcance "Todos"/todo el espacio) no hace falta
prorratear nada — se usa directo la suma de TODOS los montos del
período, sin el riesgo de perder un centavo por una rama incompleta.

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
from dataclasses import dataclass

from app.negocio.dias import parsear_periodo
from app.negocio.estadisticas import _ids_consultorio_del_alcance
from app.repositorio.registro import obtener_repositorio


def monto_liquidado_periodo(conn: sqlite3.Connection, periodo: str) -> float:
    """Suma `MontoGenerado` de la ÚLTIMA emisión de cada profesional para
    este período (nunca de todas sus filas — `emitir_liquidacion` crea
    una fila NUEVA en cada reemisión, cada una con el monto TOTAL de esa
    emisión, no un delta). Valor FROZEN (lo que de verdad se facturó,
    con los valores vigentes en el momento de emitir cada liquidación),
    a diferencia del desglose en vivo de `app.negocio.panel_control.
    DesgloseLiquidaciones` (que recalcula con los valores de HOY) —
    "Ingresos" muestra históricos de cualquier período, así que necesita
    el valor real que se facturó entonces, no una reconstrucción con
    tarifas de hoy.

    Sin alcance de ubicación: pedido explícito de la clienta — una
    liquidación es por PROFESIONAL, no se puede partir prolijamente por
    Consultorio (los descuentos de feriados/vacaciones no son por
    ubicación) — así que "Monto total liquidado" en Ingresos/Resultado
    ya no filtra por Localidad/Edificio/Unidad/Consultorio, siempre
    refleja el total real de todo el espacio."""
    return conn.execute(
        """
        SELECT COALESCE(SUM(MontoGenerado), 0) AS total FROM LiquidacionEmitida
        WHERE Periodo = ? AND IdLiquidacion IN (
            SELECT MAX(IdLiquidacion) FROM LiquidacionEmitida WHERE Periodo = ? GROUP BY IdProfesional
        )
        """,
        (periodo, periodo),
    ).fetchone()["total"]


@dataclass
class DesgloseFueraDeLiquidacion:
    """Profesionales categoría A: nunca tienen liquidación mensual propia
    (`app.negocio.liquidaciones.CATEGORIAS_CON_LIQUIDACION_MENSUAL`), así
    que todo lo que generan en el período queda "por fuera" de cualquier
    liquidación — pedido explícito de la clienta, desglosado en tres
    conceptos (antes de esta ronda "Ingresos" solo miraba el bruto de
    sus aisladas, sin separar extraordinarias ni llaves/cargos
    especiales, y sin distinguir que un A nunca entra en una
    liquidación). `cobrado` ya viene acotado por profesional (nunca
    cuenta el excedente de uno que pagó de más — mismo criterio que
    `app.negocio.panel_control.DesgloseLiquidaciones`)."""
    aisladas_normales: float
    reservas_extraordinarias: float
    otros_conceptos: float
    cobrado: float

    @property
    def bruto(self) -> float:
        return self.aisladas_normales + self.reservas_extraordinarias + self.otros_conceptos


def fuera_de_liquidacion_periodo(conn: sqlite3.Connection, periodo: str) -> DesgloseFueraDeLiquidacion:
    """Recorre cada profesional categoría A y arma, para `periodo`
    (AAAA-MM, por `Fecha` real de cada movimiento — a diferencia de
    `DesgloseLiquidaciones`, acá no hay liquidación de la que depender,
    así que el parámetro que manda es la fecha real del mes, no si algo
    "entra" en una emisión):

    - `aisladas_normales`: horas aisladas comunes (hora × tarifa
      congelada al tomarla, + recargo si aplica) — mismo criterio que
      `app.negocio.mensajes.movimiento_periodo_aislada`, separado en vez
      de sumado junto con extraordinarias/llaves/cargos.
    - `reservas_extraordinarias`: el monto a mano (`MontoExtraordinario`)
      de las reservas aisladas marcadas `EsExtraordinaria`.
    - `otros_conceptos`: depósitos/reintegros de llaves + ítems libres
      (`CargoEspecial` sin `IdLlave`, para no contarlos dos veces).
    - `cobrado`: lo efectivamente pagado este período por cada A,
      acotado a no superar lo que esa persona generó (mismo criterio de
      tope por profesional que ya usa `DesgloseLiquidaciones`/
      `_saldo_pendiente_periodo` para R)."""
    anio, mes = parsear_periodo(periodo)
    prefijo_mes = f"{anio:04d}-{mes:02d}-"
    cfg = conn.execute("SELECT RecargoPorcentajeAisladas FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    recargo_pct = cfg["RecargoPorcentajeAisladas"] if cfg else 0.0

    aisladas_normales = 0.0
    reservas_extraordinarias = 0.0
    otros_conceptos = 0.0
    cobrado = 0.0
    for profesional in obtener_repositorio(conn, "Profesional").listar(CategoriaProfesional="A"):
        id_profesional = profesional["IdProfesional"]
        filas = conn.execute(
            """
            SELECT ra.HoraInicio, ra.HoraFin, ra.AplicaRecargo, ra.EsReubicacion, ra.EsExtraordinaria,
                   ra.MontoExtraordinario, COALESCE(ra.ValorHoraAlMomentoDeLaReserva, c.ValorHoraAisladaActual)
                       AS ValorHoraAislada
            FROM ReservaAislada ra JOIN Consultorio c ON c.IdConsultorio = ra.IdConsultorio
            WHERE ra.IdProfesional = ? AND ra.Estado = 'Confirmada' AND ra.Fecha LIKE ?
            """,
            (id_profesional, prefijo_mes + "%"),
        ).fetchall()
        normales_prof = 0.0
        extraordinarias_prof = 0.0
        for f in filas:
            if f["EsExtraordinaria"]:
                extraordinarias_prof += f["MontoExtraordinario"] or 0.0
            elif not f["EsReubicacion"]:
                monto = (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraAislada"]
                normales_prof += monto * (1 + recargo_pct / 100) if f["AplicaRecargo"] else monto

        llaves = conn.execute(
            "SELECT Tipo, DepositoCobrado, MontoCobrado, DepositoReintegrado, MontoReintegrado "
            "FROM LlaveMovimiento WHERE IdProfesional = ? AND Tipo IN ('Asignación', 'Devolución') AND Fecha LIKE ?",
            (id_profesional, prefijo_mes + "%"),
        ).fetchall()
        otros_prof = 0.0
        for ll in llaves:
            if ll["Tipo"] == "Asignación" and ll["DepositoCobrado"]:
                otros_prof += ll["MontoCobrado"] or 0.0
            if ll["Tipo"] == "Devolución" and ll["DepositoReintegrado"]:
                otros_prof -= ll["MontoReintegrado"] or 0.0
        otros_prof += sum(
            c["Monto"] for c in obtener_repositorio(conn, "CargoEspecial").listar(
                IdProfesional=id_profesional, PeriodoImputado=periodo,
            )
            if c["IdLlave"] is None
        )

        bruto_prof = normales_prof + extraordinarias_prof + otros_prof
        pagado_prof = conn.execute(
            "SELECT COALESCE(SUM(Monto), 0) AS total FROM HistorialPagos WHERE IdProfesional = ? AND PeriodoImputado = ?",
            (id_profesional, periodo),
        ).fetchone()["total"]
        pendiente_prof = max(bruto_prof + pagado_prof, 0)
        cobrado += max(bruto_prof - pendiente_prof, 0)

        aisladas_normales += normales_prof
        reservas_extraordinarias += extraordinarias_prof
        otros_conceptos += otros_prof

    return DesgloseFueraDeLiquidacion(
        aisladas_normales=aisladas_normales, reservas_extraordinarias=reservas_extraordinarias,
        otros_conceptos=otros_conceptos, cobrado=cobrado,
    )


def total_ingresos_periodo(
    conn: sqlite3.Connection, periodo: str, ids_consultorio: list[int] | None = None,
) -> tuple[float, float]:
    """(monto liquidado, ingresos por fuera de las liquidaciones) del
    período. `ids_consultorio` queda SIN USAR (ver `monto_liquidado_
    periodo`: pedido explícito de la clienta, una liquidación no se
    puede partir por ubicación) — se sigue aceptando el parámetro por
    compatibilidad con `resultado_periodo`, que sigue filtrando Gastos
    operativos por ubicación."""
    return monto_liquidado_periodo(conn, periodo), fuera_de_liquidacion_periodo(conn, periodo).bruto


def _consultorios_de_unidad(conn: sqlite3.Connection, id_unidad: int) -> list[int]:
    filas = conn.execute("SELECT IdConsultorio FROM Consultorio WHERE IdUnidad = ?", (id_unidad,)).fetchall()
    return [f["IdConsultorio"] for f in filas]


def _unidades_de_edificio(conn: sqlite3.Connection, id_edificio: int) -> list[int]:
    filas = conn.execute("SELECT IdUnidad FROM Unidad WHERE IdEdificio = ?", (id_edificio,)).fetchall()
    return [f["IdUnidad"] for f in filas]


def _edificios_de_localidad(conn: sqlite3.Connection, id_localidad: int | None) -> list[int]:
    if id_localidad is None:
        filas = conn.execute("SELECT IdEdificio FROM Edificio WHERE IdLocalidad IS NULL").fetchall()
    else:
        filas = conn.execute("SELECT IdEdificio FROM Edificio WHERE IdLocalidad = ?", (id_localidad,)).fetchall()
    return [f["IdEdificio"] for f in filas]


def _localidades_con_algun_edificio(conn: sqlite3.Connection) -> list[int | None]:
    """Las "localidades que haya" para repartir un gasto de Espacio
    general (ver el docstring del módulo): cada IdLocalidad con al menos
    un Edificio, más el bucket "Sin localidad" (`None`) si hay algún
    Edificio sin localidad asignada. Dividir por una Localidad sin
    ningún Edificio no tendría a qué Consultorio llegar — ese "DISTINCT"
    sobre Edificio.IdLocalidad ya la deja afuera sola, sin hacer falta
    comparar contra el catálogo completo de Localidad."""
    filas = conn.execute("SELECT DISTINCT IdLocalidad FROM Edificio").fetchall()
    return [f["IdLocalidad"] for f in filas]


def _distribuir_gasto_por_consultorio(conn: sqlite3.Connection, gasto: sqlite3.Row) -> dict[int, float]:
    """Reparte el Monto de un gasto operativo entre los Consultorios que
    alcanza su cascada (ver el docstring del módulo) — dividiendo en
    partes iguales en cada escalón, desde su Alcance hacia abajo. Una
    rama sin hijos en algún escalón no reparte nada de esa porción a
    ningún Consultorio (se pierde, imprecisión aceptada)."""
    monto = gasto["Monto"] or 0.0
    alcance = gasto["Alcance"]

    def _por_unidad(id_unidad: int, monto_unidad: float) -> dict[int, float]:
        consultorios = _consultorios_de_unidad(conn, id_unidad)
        if not consultorios:
            return {}
        porcion = monto_unidad / len(consultorios)
        return {c: porcion for c in consultorios}

    def _por_edificio(id_edificio: int, monto_edificio: float) -> dict[int, float]:
        unidades = _unidades_de_edificio(conn, id_edificio)
        if not unidades:
            return {}
        porcion = monto_edificio / len(unidades)
        resultado: dict[int, float] = {}
        for id_unidad in unidades:
            for id_c, m in _por_unidad(id_unidad, porcion).items():
                resultado[id_c] = resultado.get(id_c, 0.0) + m
        return resultado

    def _por_localidad(id_localidad: int | None, monto_localidad: float) -> dict[int, float]:
        edificios = _edificios_de_localidad(conn, id_localidad)
        if not edificios:
            return {}
        porcion_edificio = monto_localidad / len(edificios)
        resultado: dict[int, float] = {}
        for id_edificio in edificios:
            for id_c, m in _por_edificio(id_edificio, porcion_edificio).items():
                resultado[id_c] = resultado.get(id_c, 0.0) + m
        return resultado

    if alcance == "Consultorio":
        return {gasto["IdConsultorio"]: monto}
    if alcance == "Unidad":
        return _por_unidad(gasto["IdUnidad"], monto)
    if alcance == "Edificio":
        return _por_edificio(gasto["IdEdificio"], monto)
    if alcance == "Localidad":
        # Pedido explícito de la clienta: mismo reparto en cascada que
        # "Espacio general", pero acotado a UNA localidad (la cascada
        # arranca un escalón más abajo, en sus Edificios, en vez de
        # repartir primero entre TODAS las localidades que haya).
        return _por_localidad(gasto["IdLocalidad"], monto)

    # "Espacio general"
    localidades = _localidades_con_algun_edificio(conn)
    if not localidades:
        return {}
    porcion_localidad = monto / len(localidades)
    resultado: dict[int, float] = {}
    for id_localidad in localidades:
        for id_c, m in _por_localidad(id_localidad, porcion_localidad).items():
            resultado[id_c] = resultado.get(id_c, 0.0) + m
    return resultado


def total_gastos_periodo(
    conn: sqlite3.Connection, periodo: str, *,
    id_localidad: int | None = None, id_edificio: int | None = None,
    id_unidad: int | None = None, id_consultorio: int | None = None,
) -> float:
    gastos = obtener_repositorio(conn, "GastoOperativo").listar(Periodo=periodo)
    if id_localidad is None and id_edificio is None and id_unidad is None and id_consultorio is None:
        # "Todos"/todo el espacio: suma directa, sin prorratear nada —
        # evita perder parte de un gasto por una rama incompleta (ver el
        # docstring del módulo).
        return sum(g["Monto"] or 0.0 for g in gastos)
    ids_consultorio = set(_ids_consultorio_del_alcance(
        conn, id_localidad=id_localidad, id_edificio=id_edificio, id_unidad=id_unidad, id_consultorio=id_consultorio,
    ) or [])
    total = 0.0
    for gasto in gastos:
        reparto = _distribuir_gasto_por_consultorio(conn, gasto)
        total += sum(m for c, m in reparto.items() if c in ids_consultorio)
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
    liquidado, fuera_de_liquidacion = total_ingresos_periodo(conn, periodo, ids_consultorio)
    ingresos = liquidado + fuera_de_liquidacion
    gastos = total_gastos_periodo(
        conn, periodo, id_localidad=id_localidad, id_edificio=id_edificio,
        id_unidad=id_unidad, id_consultorio=id_consultorio,
    )
    return ingresos, gastos, ingresos - gastos
