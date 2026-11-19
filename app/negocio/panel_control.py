"""Pantalla principal / panel de control (Etapa 6.1 del documento).

Encabezado (nombre del espacio, mes/año en curso, fecha de hoy) + botón
"Avanzar de mes" (disponible en cualquier momento, no solo al principio o
fin de mes — DC-06 §1: el operador puede necesitar adelantarlo unos días,
por ejemplo por vacaciones propias). Este módulo calcula los datos; la
pantalla en `app/gui` solo los muestra. La sección de alertas que vivía
acá (`calcular_alertas`/`Alertas`) se sacó a pedido explícito de la
clienta — ver el comentario grande más abajo, antes de `_deuda_aisladas`.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from app.negocio.balance import DesgloseFueraDeLiquidacion, fuera_de_liquidacion_periodo, total_gastos_periodo
from app.negocio.dias import (
    fecha_actual,
    fecha_real,
    parsear_periodo,
    periodo_actual,
    primer_dia_mes,
    sumar_meses,
    ultimo_dia_mes,
)
from app.negocio.estadisticas import _horas_regulares_semanales_en_fecha, calcular_ocupacion
from app.negocio.liquidaciones import calcular_liquidacion
from app.pdf.estilos import clave_orden_unidad
from app.repositorio.registro import obtener_repositorio


def _deuda_regulares(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Todos los profesionales R con saldo (ANTERIOR, arrastrado de meses
    previos) fuera de tolerancia — alimenta el cuadrito "Profesionales" de
    más abajo (`calcular_estadisticas_profesionales`) y, desde el repaso
    de pendientes abiertos de DC-06 §3, la alerta `deuda_regulares_mes_
    anterior` del panel (mismo criterio exacto que ya usa `_deuda_aisladas`
    para su propia alerta — sin el filtro extra de reserva activa que sí
    tiene `_deuda_regulares_alerta`, que mira el saldo ACTUAL en cambio)."""
    cfg = conn.execute("SELECT ToleranciaDeudaDescuento FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    tolerancia = cfg["ToleranciaDeudaDescuento"] if cfg else 0.0
    return [
        p for p in obtener_repositorio(conn, "Profesional").listar(CategoriaProfesional="R")
        if (p["SaldoCuentaAnterior"] or 0.0) > tolerancia
    ]


def _deuda_aisladas(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Las aisladas no tienen margen de tolerancia: cualquier saldo cuenta."""
    return [
        p for p in obtener_repositorio(conn, "Profesional").listar(CategoriaProfesional="A")
        if (p["SaldoCuentaAnterior"] or 0.0) > 0
    ]


# --------------------------------------------------------------------------
# Cuadritos informativos del Panel de control (revisión "uno por uno", ver
# CLAUDE.md): estadísticas puntuales. La sección de Alertas que vivía acá
# (una tarjeta propia, "Alertas") se sacó a pedido explícito de la clienta
# — `_deuda_regulares`/`_deuda_aisladas` de arriba siguen en pie porque el
# cuadrito "Profesionales" las sigue usando; el resto de las funciones que
# solo alimentaban esa tarjeta (`calcular_alertas`/`Alertas`/
# `_deuda_regulares_alerta`/`_reserva_regular_activa`/`_planes_con_cuotas_
# vencidas`/`_fechas_especiales_proximas`/`_categoria_x_con_llaves_
# pendientes`) se borraron con ella, sin uso en ningún otro lado.
# --------------------------------------------------------------------------


@dataclass
class EstadisticasProfesionales:
    con_plan_pago_vigente: int
    con_saldo_fuera_de_tolerancia: int
    con_reservas_regulares_activas: int
    con_reservas_aisladas_activas: int
    horarios_incorporados_proximo_periodo: float
    horarios_liberados_proximo_periodo: float

    @property
    def diferencia_horarios_proximo_periodo(self) -> float:
        return self.horarios_incorporados_proximo_periodo - self.horarios_liberados_proximo_periodo


def _horas_regulares_por_columna_vigencia(conn: sqlite3.Connection, columna: str, desde: str, hasta: str) -> float:
    """Suma de horas SEMANALES (`HoraFin - HoraInicio`, una vez por fila,
    no multiplicadas por semanas del mes) de `ReservaRegular` cuya
    `columna` (`VigenciaInicio`/`VigenciaFin`) cae dentro de [`desde`,
    `hasta`] — usada para "horarios incorporados/liberados para el mes
    próximo" (ver `calcular_estadisticas_profesionales`): una reserva que
    ARRANCA (`VigenciaInicio`) dentro del mes próximo es un horario que
    se suma a partir de ese mes; una que TERMINA (`VigenciaFin`) dentro
    del mes en curso es un horario que se libera a partir del próximo."""
    filas = conn.execute(
        f"SELECT HoraInicio, HoraFin FROM ReservaRegular WHERE {columna} BETWEEN ? AND ?",  # noqa: S608 (columna fija, no input de usuario)
        (desde, hasta),
    ).fetchall()
    return sum(f["HoraFin"] - f["HoraInicio"] for f in filas)


def calcular_estadisticas_profesionales(conn: sqlite3.Connection) -> EstadisticasProfesionales:
    hoy = fecha_actual(conn).isoformat()
    periodo = periodo_actual(conn)
    anio, mes = parsear_periodo(periodo)
    anio_prox, mes_prox = parsear_periodo(sumar_meses(periodo, 1))

    con_plan = conn.execute(
        "SELECT COUNT(DISTINCT IdProfesional) AS n FROM PlanPago WHERE Estado = 'Activo'"
    ).fetchone()["n"]
    con_reservas_activas = conn.execute(
        "SELECT COUNT(DISTINCT IdProfesional) AS n FROM ReservaRegular "
        "WHERE VigenciaInicio <= ? AND (VigenciaFin IS NULL OR VigenciaFin >= ?)",
        (hoy, hoy),
    ).fetchone()["n"]
    con_aisladas_activas = conn.execute(
        "SELECT COUNT(DISTINCT IdProfesional) AS n FROM ReservaAislada WHERE Estado = 'Confirmada' AND Fecha >= ?",
        (hoy,),
    ).fetchone()["n"]

    incorporados = _horas_regulares_por_columna_vigencia(
        conn, "VigenciaInicio", primer_dia_mes(anio_prox, mes_prox).isoformat(), ultimo_dia_mes(anio_prox, mes_prox).isoformat(),
    )
    liberados = _horas_regulares_por_columna_vigencia(
        conn, "VigenciaFin", primer_dia_mes(anio, mes).isoformat(), ultimo_dia_mes(anio, mes).isoformat(),
    )

    return EstadisticasProfesionales(
        con_plan_pago_vigente=con_plan,
        con_saldo_fuera_de_tolerancia=len(_deuda_regulares(conn)) + len(_deuda_aisladas(conn)),
        con_reservas_regulares_activas=con_reservas_activas,
        con_reservas_aisladas_activas=con_aisladas_activas,
        horarios_incorporados_proximo_periodo=incorporados,
        horarios_liberados_proximo_periodo=liberados,
    )


@dataclass
class EstadisticasOcupacion:
    ocupacion_regular_pct: float
    horas_regulares_semanales: float
    horas_aisladas_mes: float


def _horas_aisladas_periodo(
    conn: sqlite3.Connection, anio: int, mes: int, ids_consultorio: list[int] | None = None,
) -> float:
    if ids_consultorio is not None and not ids_consultorio:
        return 0.0
    sql = "SELECT HoraInicio, HoraFin FROM ReservaAislada WHERE Estado = 'Confirmada' AND Fecha BETWEEN ? AND ?"
    parametros: list = [primer_dia_mes(anio, mes).isoformat(), ultimo_dia_mes(anio, mes).isoformat()]
    if ids_consultorio is not None:
        sql += f" AND IdConsultorio IN ({', '.join('?' for _ in ids_consultorio)})"
        parametros.extend(ids_consultorio)
    filas = conn.execute(sql, parametros).fetchall()
    return sum(f["HoraFin"] - f["HoraInicio"] for f in filas)


def calcular_estadisticas_ocupacion(conn: sqlite3.Connection) -> EstadisticasOcupacion:
    periodo = periodo_actual(conn)
    anio, mes = parsear_periodo(periodo)
    hoy = fecha_actual(conn)
    return EstadisticasOcupacion(
        ocupacion_regular_pct=calcular_ocupacion(conn, anio, mes).general,
        horas_regulares_semanales=_horas_regulares_semanales_en_fecha(conn, hoy.isoformat()),
        horas_aisladas_mes=_horas_aisladas_periodo(conn, anio, mes),
    )


@dataclass
class EstadisticaOcupacionUnidad:
    nombre: str
    ocupacion_pct: float
    horas_regulares_semanales: float
    horas_aisladas_mes: float


def calcular_estadisticas_ocupacion_por_unidad(conn: sqlite3.Connection) -> list[EstadisticaOcupacionUnidad]:
    """Repite los tres conceptos de "Ocupación y horas mes en curso"
    (ocupación %, horas regulares semanales, horas aisladas del mes) por
    cada Unidad del sistema — pedido explícito de la clienta, desglosando
    lo que el cuadrito general ya muestra agregado. Orden: Edificio
    (alfabético) y, dentro de cada uno, la Unidad en el mismo orden
    natural (PB/EP/piso ascendente) que el resto de las pantallas que
    listan unidades (`clave_orden_unidad`)."""
    periodo = periodo_actual(conn)
    anio, mes = parsear_periodo(periodo)
    hoy = fecha_actual(conn).isoformat()
    ocupacion = calcular_ocupacion(conn, anio, mes)

    unidades = conn.execute(
        "SELECT u.IdUnidad, u.Departamento, e.Nombre AS NombreEdificio "
        "FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio"
    ).fetchall()
    ids_por_unidad: dict[int, list[int]] = {}
    for fila in conn.execute("SELECT IdUnidad, IdConsultorio FROM Consultorio"):
        ids_por_unidad.setdefault(fila["IdUnidad"], []).append(fila["IdConsultorio"])

    resultado = []
    for u in sorted(unidades, key=lambda u: (u["NombreEdificio"], clave_orden_unidad(u["Departamento"]))):
        agregado = ocupacion.por_unidad.get(u["IdUnidad"])
        ids_consultorio = ids_por_unidad.get(u["IdUnidad"], [])
        resultado.append(EstadisticaOcupacionUnidad(
            nombre=f"{u['NombreEdificio']} - {u['Departamento']}",
            ocupacion_pct=agregado.porcentaje if agregado else 0.0,
            horas_regulares_semanales=_horas_regulares_semanales_en_fecha(conn, hoy, ids_consultorio),
            horas_aisladas_mes=_horas_aisladas_periodo(conn, anio, mes, ids_consultorio),
        ))
    return resultado


@dataclass
class DesgloseLiquidaciones:
    """Rediseño completo del cuadrito "Estadísticas principales mes en
    curso" (sección "Liquidaciones mes en curso"), pedido explícito de
    la clienta tras preguntar cómo se arma "Total liquidado" — ocho
    conceptos que suman exactamente la liquidación de cada profesional
    (`app.negocio.liquidaciones.Liquidacion.monto_generado`), para que
    el total de este cuadrito cierre SIEMPRE con la suma real de las
    últimas liquidaciones emitidas del período (nunca "si no coincide
    es porque falta algún concepto" — `otros_ajustes` es la bolsa que
    junta todo lo que no tiene una línea propia, para que la cuenta dé
    exacta igual). `descuento_feriados`/`descuento_vacaciones`/
    `descuento_licencias` ya vienen en NEGATIVO (restan); el resto en
    positivo (suman) — `cargos_especiales`/`otros_ajustes` pueden terminar
    en cualquier signo según lo que haya cargado cada profesional.

    `cobrado_r`: NO es una línea mostrada — es lo que de verdad cobraron
    los profesionales R este período, acotado a no superar lo que cada
    uno generó (nunca cuenta el excedente de uno que pagó de más),
    usado por `app.negocio.panel_control.EstadisticasPrincipales` para
    armar la sección "Monto a cobrar en el mes en curso"."""
    monto_neto_reservas_regulares: float
    descuento_feriados: float
    descuento_vacaciones: float
    descuento_licencias: float
    aisladas_en_liquidaciones: float
    feriados_trabajados: float
    cargos_especiales: float
    cuotas_planes_pago: float
    otros_ajustes: float
    cobrado_r: float

    @property
    def total(self) -> float:
        return (
            self.monto_neto_reservas_regulares + self.descuento_feriados + self.descuento_vacaciones
            + self.descuento_licencias + self.aisladas_en_liquidaciones + self.feriados_trabajados
            + self.cargos_especiales + self.cuotas_planes_pago + self.otros_ajustes
        )


def _desglose_liquidaciones_periodo(conn: sqlite3.Connection, periodo: str) -> DesgloseLiquidaciones:
    """Recalcula la liquidación de cada profesional con `calcular_
    liquidacion` (AHORA, con los datos y valores vigentes) para cada
    profesional con una liquidación emitida este período (última
    emisión de cada uno) — puede no coincidir centavo a centavo con el
    `MontoGenerado` ya FROZEN en `LiquidacionEmitida` si algo cambió
    después de emitida (ej. un aumento de tarifas), mismo caso ya
    documentado para "Monto por reservas regulares"/"aisladas" en
    rondas anteriores, pero sirve para explicar de un vistazo de dónde
    sale cada concepto. Categoría E (se consolida en la liquidación de
    su R) y categoría B (nunca se liquida) no tienen una liquidación
    propia — `calcular_liquidacion` las rechaza con `ValueError`, se
    ignoran acá (su aporte ya está contado en la liquidación del R que
    las consolida).

    `otros_ajustes` junta los conceptos más raros de una liquidación,
    sin línea propia en el cuadrito (pedido explícito de la clienta):
    reversión del descuento por saldo atrasado, feriados pendientes de
    un mes anterior agregados tarde, horas regulares agregadas a mitad
    de mes, ajuste por saldo atrasado, ajuste de redondeo."""
    ids = [
        f["IdProfesional"] for f in conn.execute(
            "SELECT IdProfesional FROM LiquidacionEmitida WHERE Periodo = ? GROUP BY IdProfesional", (periodo,),
        ).fetchall()
    ]
    monto_neto_reservas_regulares = 0.0
    descuento_feriados = 0.0
    descuento_vacaciones = 0.0
    descuento_licencias = 0.0
    aisladas_en_liquidaciones = 0.0
    feriados_trabajados = 0.0
    cargos_especiales = 0.0
    cuotas_planes_pago = 0.0
    otros_ajustes = 0.0
    cobrado_r = 0.0
    for id_profesional in ids:
        try:
            liq = calcular_liquidacion(conn, id_profesional=id_profesional, periodo=periodo)
        except ValueError:
            continue
        monto_neto_reservas_regulares += liq.subtotal_reserva
        descuento_feriados -= (liq.total_descuento_feriados + liq.total_descuento_no_laborables)
        descuento_vacaciones -= liq.total_descuento_vacaciones
        descuento_licencias -= liq.total_descuento_licencias
        aisladas_en_liquidaciones += liq.total_aisladas_mes_anterior + liq.total_aisladas_mes_en_curso
        feriados_trabajados += (
            liq.total_feriados_trabajados_mes_anterior + liq.total_feriados_trabajados_mes_en_curso
        )
        cargos_especiales += liq.total_cargos_especiales
        cuotas_planes_pago += liq.total_cuotas_plan
        otros_ajustes += (
            liq.reversion_descuento - liq.total_feriados_pendientes + liq.total_horas_regulares_agregadas
            + liq.ajuste_saldo_atrasado + liq.ajuste_redondeo
        )
        pagado = conn.execute(
            "SELECT COALESCE(SUM(Monto), 0) AS total FROM HistorialPagos WHERE IdProfesional = ? "
            "AND PeriodoImputado = ?",
            (id_profesional, periodo),
        ).fetchone()["total"]
        pendiente = max(liq.monto_generado + pagado, 0)
        cobrado_r += max(liq.monto_generado - pendiente, 0)
    return DesgloseLiquidaciones(
        monto_neto_reservas_regulares=monto_neto_reservas_regulares, descuento_feriados=descuento_feriados,
        descuento_vacaciones=descuento_vacaciones, descuento_licencias=descuento_licencias,
        aisladas_en_liquidaciones=aisladas_en_liquidaciones, feriados_trabajados=feriados_trabajados,
        cargos_especiales=cargos_especiales, cuotas_planes_pago=cuotas_planes_pago,
        otros_ajustes=otros_ajustes, cobrado_r=cobrado_r,
    )


@dataclass
class EstadisticasPrincipales:
    """Las tres secciones del cuadrito "Estadísticas principales mes en
    curso" (rediseño completo, pedido explícito de la clienta): las
    propiedades de acá abajo son justamente las líneas "=" de cada
    sección ("Total liquidado mes en curso", "Balance del negocio",
    "Monto restante del mes a cobrar"), para que la pantalla no tenga
    que rearmar ninguna cuenta por su cuenta."""
    desglose_liquidaciones: DesgloseLiquidaciones
    desglose_fuera_liquidacion: DesgloseFueraDeLiquidacion
    gastos_operativos: float

    @property
    def total_liquidado(self) -> float:
        return self.desglose_liquidaciones.total

    @property
    def monto_a_cobrar_base(self) -> float:
        """"Monto liquidado más horas aisladas": lo liquidado más TODO lo
        que generan los profesionales A por fuera de cualquier
        liquidación (aisladas, extraordinarias, llaves/cargos)."""
        return self.total_liquidado + self.desglose_fuera_liquidacion.bruto

    @property
    def balance_negocio(self) -> float:
        return self.monto_a_cobrar_base - self.gastos_operativos

    @property
    def monto_cobrado(self) -> float:
        return self.desglose_liquidaciones.cobrado_r + self.desglose_fuera_liquidacion.cobrado

    @property
    def monto_restante_a_cobrar(self) -> float:
        return self.monto_a_cobrar_base - self.monto_cobrado


def calcular_estadisticas_principales(conn: sqlite3.Connection) -> EstadisticasPrincipales:
    """Mes en curso, todo el espacio (sin ningún alcance de ubicación —
    pedido explícito de la clienta: una liquidación es por profesional,
    no se puede partir prolijamente por ubicación)."""
    periodo = periodo_actual(conn)
    return EstadisticasPrincipales(
        desglose_liquidaciones=_desglose_liquidaciones_periodo(conn, periodo),
        desglose_fuera_liquidacion=fuera_de_liquidacion_periodo(conn, periodo),
        gastos_operativos=total_gastos_periodo(conn, periodo),
    )


def fechas_especiales_proximas_dos_meses(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Feriados/fechas especiales activas desde HOY (lo que ya pasó del
    mes en curso no se muestra) hasta el último día del segundo mes
    siguiente — "lo que queda de este mes más los dos próximos meses",
    pedido explícito de la clienta. Ventana calendario, distinta de
    `_fechas_especiales_proximas` (15 días corridos, para la alerta).

    `fecha_real`, no `fecha_actual`: caso real de la clienta, un
    "Avanzar de mes" hecho unos días antes de fin de mes recortaba
    `fecha_actual` al primer día del período nuevo y "perdía" fechas
    entre la fecha real de hoy y esa — un recordatorio tiene que mirar
    el calendario real, no en qué período quedó posicionado el sistema."""
    hoy = fecha_real(conn)
    desde = hoy.isoformat()
    anio_limite, mes_limite = parsear_periodo(sumar_meses(f"{hoy.year:04d}-{hoy.month:02d}", 2))
    hasta = ultimo_dia_mes(anio_limite, mes_limite).isoformat()
    filas = obtener_repositorio(conn, "FechasEspeciales").listar(Activo=1)
    return sorted((f for f in filas if desde <= f["Fecha"] <= hasta), key=lambda f: f["Fecha"])


@dataclass
class EventoProximo:
    dias_restantes: int
    fecha_proxima: date  # la próxima ocurrencia futura, con el año que corresponda
    descripcion: str


def _proxima_ocurrencia(hoy: date, mes: int, dia: int) -> date | None:
    """Próxima fecha (hoy inclusive) en que se repite este mes/día, sin
    importar el año — para un 29 de febrero puede no caer el año que
    viene (no es bisiesto), así que se prueba hasta 8 años para adelante
    (siempre hay un bisiesto en ese rango) antes de rendirse."""
    for delta_anio in range(0, 8):
        try:
            candidata = date(hoy.year + delta_anio, mes, dia)
        except ValueError:
            continue
        if candidata >= hoy:
            return candidata
    return None


def cumpleanos_y_dias_profesion_proximos(conn: sqlite3.Connection, meses_ventana: int = 2) -> list[EventoProximo]:
    """Pedido de la clienta ("me podría armar un cuadrito... que me vaya
    indicando por orden de cercanía los cumpleaños de los profesionales
    activos... y los días del psicólogo, del fonoaudiólogo, etc."):

    - Cumpleaños: de `Profesional.FechaNacimiento`, solo profesionales
      "activos en el espacio" — se excluyen categoría X (Inactivo) y C
      (Contacto/prospecto, todavía no es alguien que use el espacio).
    - Días de profesión: de `Profesion.DiaProfesion` (DD-MM, sin año,
      ver su columna en `schema.sql`) — una fecha fija que se repite
      todos los años, a diferencia de FechasEspeciales (fechas puntuales
      de un año concreto). Profesiones sin este dato cargado no aparecen.
      Texto coloquial ("Día del Psicólogo"), armado con `Profesion.
      NombreMasculino` (ya existía en el catálogo, sin agregar ningún
      campo nuevo para esto) — "del" es gramaticalmente correcto para
      cualquier nombre marcado como masculino en el catálogo. Sin
      `NombreMasculino` cargado, cae al genérico "Día de la profesión:
      {Nombre}" en vez de romper.

    Mismo criterio de ventana que `fechas_especiales_proximas_dos_meses`
    (lo que queda del mes en curso más los próximos `meses_ventana`
    meses) — ambos tipos de evento se mezclan en una sola lista, ordenada
    por cercanía (más próximo primero). Mismo motivo que ahí para usar
    `fecha_real` en vez de `fecha_actual`."""
    hoy = fecha_real(conn)
    anio_limite, mes_limite = parsear_periodo(sumar_meses(f"{hoy.year:04d}-{hoy.month:02d}", meses_ventana))
    limite = ultimo_dia_mes(anio_limite, mes_limite)

    eventos: list[EventoProximo] = []

    profesionales = conn.execute(
        "SELECT Apellido, NombrePila, Tratamiento, FechaNacimiento FROM Profesional "
        "WHERE FechaNacimiento IS NOT NULL AND FechaNacimiento != '' "
        "AND CategoriaProfesional NOT IN ('X', 'C')"
    ).fetchall()
    for p in profesionales:
        try:
            nacimiento = date.fromisoformat(p["FechaNacimiento"])
        except ValueError:
            continue
        proxima = _proxima_ocurrencia(hoy, nacimiento.month, nacimiento.day)
        if proxima is None or proxima > limite:
            continue
        partes = [x for x in (p["Tratamiento"], p["NombrePila"], p["Apellido"]) if x]
        nombre = " ".join(partes) if partes else p["Apellido"]
        eventos.append(EventoProximo((proxima - hoy).days, proxima, f"Cumpleaños de {nombre}"))

    profesiones = conn.execute(
        "SELECT Nombre, NombreMasculino, DiaProfesion FROM Profesion "
        "WHERE DiaProfesion IS NOT NULL AND DiaProfesion != ''"
    ).fetchall()
    for prof in profesiones:
        try:
            dia, mes = (int(parte) for parte in prof["DiaProfesion"].split("-"))
        except ValueError:
            continue
        proxima = _proxima_ocurrencia(hoy, mes, dia)
        if proxima is None or proxima > limite:
            continue
        descripcion = (
            f"Día del {prof['NombreMasculino']}"
            if prof["NombreMasculino"]
            else f"Día de la profesión: {prof['Nombre']}"
        )
        eventos.append(EventoProximo((proxima - hoy).days, proxima, descripcion))

    return sorted(eventos, key=lambda e: e.dias_restantes)
