"""Pantalla principal / panel de control (Etapa 6.1 del documento).

Encabezado (nombre del espacio, mes/año en curso, fecha de hoy) + botón
"Avanzar de mes" (disponible en cualquier momento, no solo al principio o
fin de mes — DC-06 §1: el operador puede necesitar adelantarlo unos días,
por ejemplo por vacaciones propias) + 5 alertas. Este módulo calcula los
datos; la pantalla en `app/gui` solo los muestra.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field, fields
from datetime import timedelta

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
    monto_bruto_aislada_periodo,
)
from app.repositorio.registro import obtener_repositorio


@dataclass
class Alertas:
    deuda_regulares: list[sqlite3.Row] = field(default_factory=list)
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
        deuda_regulares=_deuda_regulares(conn),
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
    ese mismo período (`HistorialPagos.Monto`) — interpretación elegida
    a falta de una única forma de calcularlo en el resto del sistema, a
    confirmar con la clienta si no es lo que tenía en mente."""
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
        monto_aisladas_mes=monto_bruto_aislada_periodo(conn, anio, mes),
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
