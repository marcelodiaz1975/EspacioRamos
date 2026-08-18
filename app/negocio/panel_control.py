"""Pantalla principal / panel de control (Etapa 6.1 del documento).

Encabezado (nombre del espacio, mes/año en curso, fecha de hoy) + botón
"Avanzar de mes" (solo habilitado el último día del mes o el primero del
siguiente) + 5 alertas. Este módulo calcula los datos; la pantalla en
`app/gui` solo los muestra.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field, fields
from datetime import timedelta

from app.negocio.backup import backup_vencido as _backup_vencido
from app.negocio.dias import fecha_actual, periodo_actual, ultimo_dia_mes
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


def puede_avanzar_mes(conn: sqlite3.Connection) -> bool:
    """"Solo habilitado el último día del mes o el primero del siguiente"."""
    hoy = fecha_actual(conn)
    if hoy.day == 1:
        return True
    return hoy == ultimo_dia_mes(hoy.year, hoy.month)


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
        SELECT DISTINCT p.* FROM Profesional p JOIN LlaveProfesional lp ON lp.IdProfesional = p.IdProfesional
        WHERE p.CategoriaProfesional = 'X' AND lp.FechaDevolucion IS NULL
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
