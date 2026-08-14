"""Avance de mes (DC-06), subconjunto de las Etapas 4, 6 y 9.

Cubre lo que le compete a liquidaciones, pagos, lista de espera y
estadísticas: snapshot del mes que se cierra, traspaso de saldo, cierre
de cuotas del mes cerrado y limpieza de la lista de espera. El resto del
proceso de 9 pasos del documento (backup previo, oferta de análisis de
valores, archivo de aisladas, reset del centro de mensajería) pertenece a
otras etapas (centro de mensajería: Etapa 8; análisis de valores: Etapa
5) y se integra acá cuando corresponda. El archivo de aisladas del mes
cerrado tampoco necesita código: "desaparecer de la vista operativa" es
un filtro de pantalla (Etapa 8), no una migración de datos — los
registros siguen enteros, solo se dejan de mostrar como "del mes en
curso".

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

from app.negocio.archivos_generados import (
    SUBCARPETA_DISPONIBILIDAD,
    SUBCARPETA_OFERTA,
    SUBCARPETA_PROPUESTA,
    carpeta_archivos_varios,
    carpeta_base,
    carpeta_profesional,
    limpiar_liquidaciones_antiguas,
    vaciar_carpeta,
)
from app.negocio.dias import fecha_actual
from app.negocio.estadisticas import generar_snapshot
from app.negocio.historial_oferta import vaciar_historial
from app.repositorio.registro import obtener_repositorio


@dataclass
class ResumenAvanceMes:
    periodo_cerrado: str
    id_snapshot: int = 0
    profesionales_con_traspaso: int = 0
    cuotas_cerradas: int = 0
    planes_finalizados: list[int] = field(default_factory=list)
    pedidos_lista_espera_eliminados: int = 0
    pedidos_activos_vencidos_eliminados: int = 0
    archivos_varios_regenerados: bool = False
    liquidaciones_antiguas_eliminadas: int = 0
    ofertas_eliminadas: int = 0
    historial_oferta_eliminado: int = 0


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


def _limpiar_lista_espera(conn: sqlite3.Connection, *, eliminar_activos_vencidos: bool) -> tuple[int, int]:
    """Paso 6 (DC-06, DC-08 §2.6): Resueltos y Descartados se eliminan
    siempre. Los Activos con más de RetencionHistorialListaEsperaAnios de
    antigüedad solo se eliminan si el operador ya confirmó la limpieza
    (`eliminar_activos_vencidos=True`); por defecto se conservan (equivale
    a la opción "conservar por un mes más" del documento)."""
    repo = obtener_repositorio(conn, "ListaEspera")
    cerrados = repo.listar(Estado="Resuelto") + repo.listar(Estado="Descartado")
    for c in cerrados:
        repo.eliminar(c["IdPedido"])

    vencidos_eliminados = 0
    if eliminar_activos_vencidos:
        cfg = conn.execute(
            "SELECT RetencionHistorialListaEsperaAnios FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        anios_retencion = cfg["RetencionHistorialListaEsperaAnios"] if cfg else 5
        hoy = fecha_actual(conn)
        try:
            limite = hoy.replace(year=hoy.year - anios_retencion).isoformat()
        except ValueError:  # 29 de febrero sin año bisiesto equivalente
            limite = hoy.replace(year=hoy.year - anios_retencion, day=28).isoformat()
        vencidos = [p for p in repo.listar(Estado="Activo") if p["FechaPedido"] < limite]
        for p in vencidos:
            repo.eliminar(p["IdPedido"])
        vencidos_eliminados = len(vencidos)

    return len(cerrados), vencidos_eliminados


def _regenerar_archivos_varios(conn: sqlite3.Connection) -> bool:
    """Paso 9 (Etapa 9): Propuesta y Disponibilidad se regeneran contra el
    estado del mes que arranca y quedan listas en Archivos varios; la
    carpeta de Oferta se vacía entera (esas búsquedas ya no aplican al mes
    nuevo). Si todavía no se configuró la carpeta base, se salta sin
    romper el resto del avance de mes — el operador la configura cuando
    quiera empezar a usar esta parte."""
    if carpeta_base(conn) is None:
        return False
    from app.pdf.disponibilidad_pdf import generar_pdfs_disponibilidad_por_localidad
    from app.pdf.propuesta_pdf import generar_pdfs_propuesta_por_localidad

    generar_pdfs_propuesta_por_localidad(conn, str(carpeta_archivos_varios(conn, SUBCARPETA_PROPUESTA)))
    generar_pdfs_disponibilidad_por_localidad(conn, str(carpeta_archivos_varios(conn, SUBCARPETA_DISPONIBILIDAD)))
    return True


def _limpiar_liquidaciones_antiguas_todos(conn: sqlite3.Connection, hoy) -> int:
    if carpeta_base(conn) is None:
        return 0
    repo = obtener_repositorio(conn, "Profesional")
    total = 0
    for p in repo.listar():
        if not p["IdCodigo"]:
            continue
        total += limpiar_liquidaciones_antiguas(carpeta_profesional(conn, p["IdCodigo"]), hoy)
    return total


def avanzar_mes(
    conn: sqlite3.Connection, *, periodo_cerrado: str, eliminar_activos_vencidos_lista_espera: bool = False,
    porcentaje_aumento_aplicado: float | None = None,
) -> ResumenAvanceMes:
    """Ejecuta el subconjunto de Etapas 4, 6 y 9 del avance de mes para el
    período que se está cerrando (formato 'AAAA-MM'). `porcentaje_aumento_aplicado`
    queda en el snapshot si ese mes se confirmó un aumento (sección 6.1:
    "ofrece evaluar aumentos o saltear" — `aumentos.confirmar_aumento` no
    llama a esta función, así que el llamador es quien conecta ambos)."""
    resumen = ResumenAvanceMes(periodo_cerrado=periodo_cerrado)
    resumen.id_snapshot = generar_snapshot(
        conn, periodo_cerrado, porcentaje_aumento_aplicado=porcentaje_aumento_aplicado,
    )
    resumen.profesionales_con_traspaso = _traspasar_saldos(conn)
    resumen.cuotas_cerradas, resumen.planes_finalizados = _cerrar_cuotas(conn, periodo_cerrado)
    resumen.pedidos_lista_espera_eliminados, resumen.pedidos_activos_vencidos_eliminados = _limpiar_lista_espera(
        conn, eliminar_activos_vencidos=eliminar_activos_vencidos_lista_espera,
    )

    resumen.archivos_varios_regenerados = _regenerar_archivos_varios(conn)
    resumen.liquidaciones_antiguas_eliminadas = _limpiar_liquidaciones_antiguas_todos(conn, fecha_actual(conn))
    if carpeta_base(conn) is not None:
        resumen.ofertas_eliminadas = vaciar_carpeta(carpeta_archivos_varios(conn, SUBCARPETA_OFERTA))
    resumen.historial_oferta_eliminado = vaciar_historial(conn)
    return resumen
