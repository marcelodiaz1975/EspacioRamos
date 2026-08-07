"""Avance de mes (DC-06), subconjunto de Etapa 4.

Solo cubre lo que le compete a liquidaciones y pagos: traspaso de saldo y
cierre de cuotas del mes cerrado. El resto del proceso de 9 pasos del
documento (backup previo, oferta de análisis de valores, archivo de
aisladas, limpieza de lista de espera, reset del centro de mensajería,
snapshot definitivo) pertenece a otras etapas (snapshots: Etapa 9; lista
de espera: Etapa 6; centro de mensajería: Etapa 8; análisis de valores:
Etapa 5) y se integra acá cuando corresponda.

El reset de cupo de vacaciones en enero (DC-06 Paso 7) no necesita código:
el cupo se calcula siempre en vivo filtrando por año calendario (ver
`vacaciones.py`), así que el año nuevo arranca en cero solo, sin ningún
campo que resetear.

El ajuste por saldo atrasado (DC-06 Paso 4) NO es un paso de este proceso
(corregido en conversación): se evalúa en vivo cada vez que se calcula una
liquidación, no una sola vez acá. Si el operador espera a generar la
liquidación remanente y en el medio el profesional paga algo imputado al
mes anterior que regulariza la situación, el ajuste directamente no se
llega a aplicar — no hace falta revertir nada. Ver
`liquidaciones.calcular_liquidacion` (usa el SaldoCuentaAnterior vigente
en ese momento, después de traspasado acá).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from app.repositorio.registro import obtener_repositorio


@dataclass
class ResumenAvanceMes:
    periodo_cerrado: str
    profesionales_con_traspaso: int = 0
    cuotas_cerradas: int = 0
    planes_finalizados: list[int] = field(default_factory=list)


def _traspasar_saldos(conn: sqlite3.Connection) -> int:
    """Paso 2: SaldoCuentaAnterior = SaldoCuentaActual; SaldoCuentaActual
    arranca en cero para el mes nuevo (se va cargando con las liquidaciones
    y pagos que se registren)."""
    repo = obtener_repositorio(conn, "Profesional")
    profesionales = repo.listar()
    for p in profesionales:
        repo.actualizar(
            p["IdProfesional"], SaldoCuentaAnterior=p["SaldoCuentaActual"] or 0.0, SaldoCuentaActual=0.0,
        )
    return len(profesionales)


def _cerrar_cuotas(conn: sqlite3.Connection, periodo_cerrado: str) -> tuple[int, list[int]]:
    """Paso 3: las cuotas del mes cerrado pasan a Cerrada, pagas o no. Si
    con eso un plan no tiene ninguna cuota fuera de Cerrada, se finaliza."""
    repo_cuota = obtener_repositorio(conn, "CuotaPlan")
    cuotas = repo_cuota.listar(PeriodoImputado=periodo_cerrado)
    planes_afectados = {c["IdPlan"] for c in cuotas}
    for c in cuotas:
        if c["Estado"] != "Cerrada":
            repo_cuota.actualizar(c["IdCuota"], Estado="Cerrada")

    repo_plan = obtener_repositorio(conn, "PlanPago")
    finalizados = []
    for id_plan in planes_afectados:
        plan = repo_plan.obtener(id_plan)
        if plan is None or plan["Estado"] != "Activo":
            continue
        total_no_cerradas = conn.execute(
            "SELECT COUNT(*) FROM CuotaPlan WHERE IdPlan = ? AND Estado != 'Cerrada'", (id_plan,)
        ).fetchone()[0]
        if total_no_cerradas == 0:
            repo_plan.actualizar(id_plan, Estado="Finalizado")
            finalizados.append(id_plan)
    return len(cuotas), finalizados


def avanzar_mes(conn: sqlite3.Connection, *, periodo_cerrado: str) -> ResumenAvanceMes:
    """Ejecuta el subconjunto de Etapa 4 del avance de mes para el período
    que se está cerrando (formato 'AAAA-MM')."""
    resumen = ResumenAvanceMes(periodo_cerrado=periodo_cerrado)
    resumen.profesionales_con_traspaso = _traspasar_saldos(conn)
    resumen.cuotas_cerradas, resumen.planes_finalizados = _cerrar_cuotas(conn, periodo_cerrado)
    return resumen
