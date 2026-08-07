"""Avance de mes (DC-06), subconjunto de Etapa 4.

Solo cubre lo que le compete a liquidaciones y pagos: traspaso de saldo,
cierre de cuotas del mes cerrado y ajuste por saldo atrasado. El resto del
proceso de 9 pasos del documento (backup previo, oferta de análisis de
valores, archivo de aisladas, limpieza de lista de espera, reset del
centro de mensajería, snapshot definitivo) pertenece a otras etapas
(snapshots: Etapa 9; lista de espera: Etapa 6; centro de mensajería:
Etapa 8; análisis de valores: Etapa 5) y se integra acá cuando corresponda.

El reset de cupo de vacaciones en enero (DC-06 Paso 7) no necesita código:
el cupo se calcula siempre en vivo filtrando por año calendario (ver
`vacaciones.py`), así que el año nuevo arranca en cero solo, sin ningún
campo que resetear.

Orden (DC-11 caso 3): traspaso de saldo -> cierre de cuotas -> ajuste por
saldo atrasado. El ajuste se calcula sobre el saldo YA trasladado; las
cuotas impagas del mes cerrado ya están reflejadas en ese saldo porque su
importe entró a SaldoCuentaActual cuando se emitió la liquidación que las
incluía — este paso solo actualiza el Estado de las cuotas para dejar
registro, no mueve plata.
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
    profesionales_con_ajuste: list[dict] = field(default_factory=list)


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


def _aplicar_ajuste_saldo_atrasado(conn: sqlite3.Connection) -> list[dict]:
    """Paso 4: solo profesionales R con SaldoCuentaAnterior por encima de
    la tolerancia (naranjas y rojos, DC-06 §5.2)."""
    cfg = conn.execute(
        "SELECT ToleranciaDeudaDescuento, PorcentajeAjusteSaldoAtrasado FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    tolerancia = cfg["ToleranciaDeudaDescuento"] if cfg else 0.0
    ajuste_pct = cfg["PorcentajeAjusteSaldoAtrasado"] if cfg else 0.0

    repo = obtener_repositorio(conn, "Profesional")
    afectados = []
    for p in repo.listar(CategoriaProfesional="R"):
        saldo = p["SaldoCuentaAnterior"] or 0.0
        if saldo > tolerancia:
            ajuste = saldo * ajuste_pct / 100
            repo.actualizar(p["IdProfesional"], SaldoCuentaAnterior=saldo + ajuste)
            afectados.append({"id_profesional": p["IdProfesional"], "ajuste": ajuste})
    return afectados


def avanzar_mes(conn: sqlite3.Connection, *, periodo_cerrado: str) -> ResumenAvanceMes:
    """Ejecuta el subconjunto de Etapa 4 del avance de mes para el período
    que se está cerrando (formato 'AAAA-MM')."""
    resumen = ResumenAvanceMes(periodo_cerrado=periodo_cerrado)
    resumen.profesionales_con_traspaso = _traspasar_saldos(conn)
    resumen.cuotas_cerradas, resumen.planes_finalizados = _cerrar_cuotas(conn, periodo_cerrado)
    resumen.profesionales_con_ajuste = _aplicar_ajuste_saldo_atrasado(conn)
    return resumen


def revertir_ajuste_saldo_atrasado(conn: sqlite3.Connection, id_profesional: int, monto_ajuste: float) -> None:
    """Reversión manual (DC-06 §5.2): si un pago imputado al mes anterior
    regulariza la situación de un profesional antes de enviarle la
    liquidación remanente, el operador puede decidir reestablecerle el
    descuento. El monto a revertir lo determina quien llama (Etapa 8)."""
    repo = obtener_repositorio(conn, "Profesional")
    profesional = repo.obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    repo.actualizar(id_profesional, SaldoCuentaAnterior=(profesional["SaldoCuentaAnterior"] or 0.0) - monto_ajuste)
