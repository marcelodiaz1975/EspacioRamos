"""Pantalla principal / panel de control (Etapa 6.1 del documento).

Encabezado (nombre del espacio, mes/año en curso, fecha de hoy) + botón
"Avanzar de mes" (disponible en cualquier momento, no solo al principio o
fin de mes — DC-06 §1: el operador puede necesitar adelantarlo unos días,
por ejemplo por vacaciones propias) + 6 alertas (una nueva, `deuda_
regulares_mes_anterior`, sumada en el repaso de DC-06 §3 — ver abajo).
Este módulo calcula los datos; la pantalla en `app/gui` solo los muestra.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field, fields
from datetime import date, timedelta

from app.negocio.backup import backup_vencido as _backup_vencido
from app.negocio.dias import (
    fecha_actual,
    parsear_periodo,
    periodo_actual,
    primer_dia_mes,
    sumar_meses,
    ultimo_dia_mes,
)
from app.negocio.estadisticas import (
    _horas_regulares_semanales_en_fecha,
    calcular_ocupacion,
    monto_neto_aislada_periodo,
)
from app.repositorio.registro import obtener_repositorio


@dataclass
class Alertas:
    deuda_regulares: list[sqlite3.Row] = field(default_factory=list)
    deuda_regulares_mes_anterior: list[sqlite3.Row] = field(default_factory=list)
    deuda_aisladas: list[sqlite3.Row] = field(default_factory=list)
    liquidaciones_regeneradas_no_enviadas: list[sqlite3.Row] = field(default_factory=list)
    planes_con_cuotas_vencidas: list[sqlite3.Row] = field(default_factory=list)
    fechas_especiales_proximas: list[sqlite3.Row] = field(default_factory=list)
    categoria_x_con_llaves_pendientes: list[sqlite3.Row] = field(default_factory=list)
    backup_vencido: bool = False

    @property
    def total(self) -> int:
        """`backup_vencido` es un bool (una alerta binaria, no una lista de
        registros como el resto) — cuenta como 1 cuando está prendida."""
        total = 0
        for f in fields(self):
            valor = getattr(self, f.name)
            total += len(valor) if isinstance(valor, list) else int(bool(valor))
        return total


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


def _reserva_regular_activa(conn: sqlite3.Connection, id_profesional: int, hoy: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM ReservaRegular WHERE IdProfesional = ? AND VigenciaInicio <= ? "
        "AND (VigenciaFin IS NULL OR VigenciaFin >= ?) LIMIT 1",
        (id_profesional, hoy, hoy),
    ).fetchone() is not None


def _deuda_regulares_alerta(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Primer alerta del panel (pedido de la clienta, dos rondas de
    ajuste sobre esta misma alerta). A diferencia de `_deuda_regulares`
    (saldo ANTERIOR — arrastrado de meses previos —, que sigue
    alimentando el cuadrito "Profesionales" sin cambios), esta alerta
    puntual mira `SaldoCuentaActual`: lo que se va liquidando durante EL
    MES EN CURSO (`avance_mes.avanzar_mes` lo resetea a 0 al arrancar un
    mes nuevo; `liquidaciones.emitir_liquidacion` le suma lo generado;
    `pagos.registrar_pago` le resta lo cobrado imputado a este período)
    — no el saldo arrastrado de meses anteriores, aclarado explícitamente
    por la clienta para esta sección. Además exige que el profesional
    reserve regular a este momento, y queda ordenada por código."""
    cfg = conn.execute("SELECT ToleranciaDeudaDescuento FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    tolerancia = cfg["ToleranciaDeudaDescuento"] if cfg else 0.0
    hoy = fecha_actual(conn).isoformat()
    filas = [
        p for p in obtener_repositorio(conn, "Profesional").listar(CategoriaProfesional="R")
        if (p["SaldoCuentaActual"] or 0.0) > tolerancia and _reserva_regular_activa(conn, p["IdProfesional"], hoy)
    ]
    filas.sort(key=lambda p: p["IdCodigo"] or "")
    return filas


def _deuda_aisladas(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Las aisladas no tienen margen de tolerancia: cualquier saldo cuenta."""
    return [
        p for p in obtener_repositorio(conn, "Profesional").listar(CategoriaProfesional="A")
        if (p["SaldoCuentaAnterior"] or 0.0) > 0
    ]


def _planes_con_cuotas_vencidas(conn: sqlite3.Connection, periodo: str) -> list[sqlite3.Row]:
    filas = conn.execute(
        """
        SELECT DISTINCT pp.* FROM PlanPago pp JOIN CuotaPlan cp ON cp.IdPlan = pp.IdPlan
        WHERE pp.Estado = 'Activo' AND cp.Estado = 'Pendiente' AND cp.PeriodoImputado < ?
        """,
        (periodo,),
    ).fetchall()
    return filas


def _fechas_especiales_proximas(conn: sqlite3.Connection, dias_ventana: int = 15) -> list[sqlite3.Row]:
    hoy = fecha_actual(conn)
    limite = (hoy + timedelta(days=dias_ventana)).isoformat()
    filas = obtener_repositorio(conn, "FechasEspeciales").listar(Activo=1)
    return [f for f in filas if hoy.isoformat() <= f["Fecha"] <= limite]


def _categoria_x_con_llaves_pendientes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    filas = conn.execute(
        """
        SELECT DISTINCT p.* FROM Profesional p
        JOIN LlaveMovimiento asig ON asig.IdProfesional = p.IdProfesional AND asig.Tipo = 'Asignación'
        WHERE p.CategoriaProfesional = 'X'
          AND NOT EXISTS (SELECT 1 FROM LlaveMovimiento cierre WHERE cierre.IdAsignacion = asig.IdMovimiento)
        """
    ).fetchall()
    return filas


def calcular_alertas(conn: sqlite3.Connection) -> Alertas:
    periodo = periodo_actual(conn)
    return Alertas(
        deuda_regulares=_deuda_regulares_alerta(conn),
        deuda_regulares_mes_anterior=_deuda_regulares(conn),
        deuda_aisladas=_deuda_aisladas(conn),
        liquidaciones_regeneradas_no_enviadas=obtener_repositorio(conn, "LiquidacionEmitida").listar(
            EstadoEnvio="Regenerada no enviada",
        ),
        planes_con_cuotas_vencidas=_planes_con_cuotas_vencidas(conn, periodo),
        fechas_especiales_proximas=_fechas_especiales_proximas(conn),
        categoria_x_con_llaves_pendientes=_categoria_x_con_llaves_pendientes(conn),
        backup_vencido=_backup_vencido(conn, fecha_actual(conn)),
    )


# --------------------------------------------------------------------------
# Cuadritos informativos del Panel de control (revisión "uno por uno", ver
# CLAUDE.md): estadísticas puntuales, independientes de las alertas de
# arriba (que ahora viven en su propio cuadrito, "Alertas").
# --------------------------------------------------------------------------


@dataclass
class EstadisticasProfesionales:
    con_plan_pago_vigente: int
    con_saldo_fuera_de_tolerancia: int
    con_reservas_regulares_activas: int


def calcular_estadisticas_profesionales(conn: sqlite3.Connection) -> EstadisticasProfesionales:
    hoy = fecha_actual(conn).isoformat()
    con_plan = conn.execute(
        "SELECT COUNT(DISTINCT IdProfesional) AS n FROM PlanPago WHERE Estado = 'Activo'"
    ).fetchone()["n"]
    con_reservas_activas = conn.execute(
        "SELECT COUNT(DISTINCT IdProfesional) AS n FROM ReservaRegular "
        "WHERE VigenciaInicio <= ? AND (VigenciaFin IS NULL OR VigenciaFin >= ?)",
        (hoy, hoy),
    ).fetchone()["n"]
    return EstadisticasProfesionales(
        con_plan_pago_vigente=con_plan,
        con_saldo_fuera_de_tolerancia=len(_deuda_regulares(conn)) + len(_deuda_aisladas(conn)),
        con_reservas_regulares_activas=con_reservas_activas,
    )


@dataclass
class EstadisticasOcupacion:
    ocupacion_regular_pct: float
    horas_regulares_semanales: float
    horas_aisladas_mes: float
    monto_aisladas_mes: float
    saldo_pendiente_mes: float


def _horas_aisladas_periodo(conn: sqlite3.Connection, anio: int, mes: int) -> float:
    filas = conn.execute(
        "SELECT HoraInicio, HoraFin FROM ReservaAislada WHERE Estado = 'Confirmada' AND Fecha BETWEEN ? AND ?",
        (primer_dia_mes(anio, mes).isoformat(), ultimo_dia_mes(anio, mes).isoformat()),
    ).fetchall()
    return sum(f["HoraFin"] - f["HoraInicio"] for f in filas)


def _saldo_pendiente_periodo(conn: sqlite3.Connection, periodo: str) -> float:
    """"Cuánto queda por cobrar de este mes": lo facturado en el período
    (`LiquidacionEmitida.MontoGenerado`) menos lo ya cobrado imputado a
    ese mismo período (`HistorialPagos.Monto`) — confirmado con la
    clienta en la revisión "uno por uno" de Panel de control, es el
    cálculo que tenía en mente."""
    facturado = conn.execute(
        "SELECT COALESCE(SUM(MontoGenerado), 0) AS total FROM LiquidacionEmitida WHERE Periodo = ?", (periodo,),
    ).fetchone()["total"]
    cobrado = conn.execute(
        "SELECT COALESCE(SUM(Monto), 0) AS total FROM HistorialPagos WHERE PeriodoImputado = ?", (periodo,),
    ).fetchone()["total"]
    return facturado - cobrado


def calcular_estadisticas_ocupacion(conn: sqlite3.Connection) -> EstadisticasOcupacion:
    periodo = periodo_actual(conn)
    anio, mes = parsear_periodo(periodo)
    hoy = fecha_actual(conn)
    return EstadisticasOcupacion(
        ocupacion_regular_pct=calcular_ocupacion(conn, anio, mes).general,
        horas_regulares_semanales=_horas_regulares_semanales_en_fecha(conn, hoy.isoformat()),
        horas_aisladas_mes=_horas_aisladas_periodo(conn, anio, mes),
        monto_aisladas_mes=monto_neto_aislada_periodo(conn, anio, mes),
        saldo_pendiente_mes=_saldo_pendiente_periodo(conn, periodo),
    )


def fechas_especiales_proximas_dos_meses(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Feriados/fechas especiales activas desde HOY (lo que ya pasó del
    mes en curso no se muestra) hasta el último día del segundo mes
    siguiente — "lo que queda de este mes más los dos próximos meses",
    pedido explícito de la clienta. Ventana calendario, distinta de
    `_fechas_especiales_proximas` (15 días corridos, para la alerta)."""
    hoy = fecha_actual(conn)
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
    - Días de profesión: de `Profesion.DiaProfesion` (MM-DD, sin año,
      ver su columna en `schema.sql`) — una fecha fija que se repite
      todos los años, a diferencia de FechasEspeciales (fechas puntuales
      de un año concreto). Profesiones sin este dato cargado no aparecen.

    Mismo criterio de ventana que `fechas_especiales_proximas_dos_meses`
    (lo que queda del mes en curso más los próximos `meses_ventana`
    meses) — ambos tipos de evento se mezclan en una sola lista, ordenada
    por cercanía (más próximo primero)."""
    hoy = fecha_actual(conn)
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
        "SELECT Nombre, DiaProfesion FROM Profesion WHERE DiaProfesion IS NOT NULL AND DiaProfesion != ''"
    ).fetchall()
    for prof in profesiones:
        try:
            mes, dia = (int(parte) for parte in prof["DiaProfesion"].split("-"))
        except ValueError:
            continue
        proxima = _proxima_ocurrencia(hoy, mes, dia)
        if proxima is None or proxima > limite:
            continue
        eventos.append(EventoProximo((proxima - hoy).days, proxima, f"Día de la profesión: {prof['Nombre']}"))

    return sorted(eventos, key=lambda e: e.dias_restantes)
