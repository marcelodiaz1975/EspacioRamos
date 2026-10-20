"""Herramienta de "nuevo inicio" para la transición de prueba a uso real
(pedido explícito de la clienta): mientras prueba el sistema a fondo
durante un mes (ej. octubre), antes de arrancar a usarlo de verdad (ej.
noviembre), necesita poder:

- Ajustar a mano el `SaldoCuentaAnterior` de cada profesional R/A (los
  dos únicos que llevan saldo de cuenta propio — B/E/X/C no facturan
  directo, E consolida en su cabeza de equipo R) a su valor real, sin
  que importe lo que haya quedado acumulado probando. NUNCA toca
  `SaldoCuentaActual` — `avance_mes.avanzar_mes` (`_traspasar_saldos`)
  ya lo resetea a 0 al cerrar el mes de prueba, antes de que esta
  pantalla entre en juego.
- Borrar los historiales de movimientos generados durante la prueba,
  hasta un período de corte elegido, SIN tocar la estructura física
  (Localidad/Edificio/Unidad/Consultorio/Profesional), las reservas
  regulares ("controlar que todas las reservas estén correctas" queda
  en manos de la clienta, revisándolas a mano, no de un borrado
  automático) ni ningún archivo subido — un reinicio de los NÚMEROS
  acumulados, no de la base ya cargada.

Alcance de la limpieza, confirmado con la clienta (`AskUserQuestion`):
Pagos y liquidaciones (`HistorialPagos`/`LiquidacionEmitida`/
`CargoEspecial`/`FeriadoTrabajado`/`PlanPago`+`CuotaPlan`), Reservas
aisladas y extraordinarias (`ReservaAislada` — las dos conviven en la
misma tabla, ver `app.negocio.reservas`) y Snapshots/estado de
mensajería (`SnapshotMensual`/`EstadoMensajeriaPeriodo`). Deliberadamente
AFUERA del alcance: movimientos de llaves/placas (`LlaveMovimiento`/
`Placa` — stock y asignaciones reales, riesgoso borrarlas si durante el
mes de prueba ya hubo movimientos de verdad) y Aumentos/Esquema de
descuentos (`AumentoAplicado`/`EsquemaDescuentos` — no son "historial de
movimientos", son configuración de valores vigentes).

"Período de corte": cualquier fila con período (imputado o, a falta de
eso, el mes de su fecha) MENOR O IGUAL al elegido se borra — pensado
para usarse con el mes recién cerrado de prueba (ej. avanza a noviembre,
corta en "2026-10"), pero sin ninguna restricción que lo ate a ese caso
puntual."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.repositorio.registro import obtener_repositorio

# Categorías que llevan saldo de cuenta propio — las únicas que esta
# pantalla ofrece para ajustar `SaldoCuentaAnterior` a mano.
CATEGORIAS_CON_SALDO = ("R", "A")


def profesionales_con_saldo(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Profesionales R/A con su saldo actual (solo lectura, referencia —
    recién reseteado a 0 por `avance_mes.avanzar_mes`) y anterior
    (editable desde esta pantalla)."""
    placeholders = ", ".join("?" for _ in CATEGORIAS_CON_SALDO)
    return conn.execute(
        f"SELECT IdProfesional, IdCodigo, Tratamiento, Apellido, NombrePila, "
        f"CategoriaProfesional, SaldoCuentaAnterior, SaldoCuentaActual "
        f"FROM Profesional WHERE CategoriaProfesional IN ({placeholders})",
        CATEGORIAS_CON_SALDO,
    ).fetchall()


def ajustar_saldo_anterior(conn: sqlite3.Connection, id_profesional: int, nuevo_saldo: float) -> None:
    """Pisa `SaldoCuentaAnterior` directo — a diferencia de `pagos.
    registrar_pago` (que arma un `HistorialPagos` y suma/resta sobre el
    saldo existente), acá el valor nuevo ES el punto de partida, no un
    movimiento más a sumar encima de lo que haya quedado de la prueba."""
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, SaldoCuentaAnterior=nuevo_saldo)


@dataclass
class ResumenDepuracion:
    pagos: int = 0
    liquidaciones: int = 0
    cargos_especiales: int = 0
    feriados_trabajados: int = 0
    planes_de_pago: int = 0
    cuotas: int = 0
    reservas_aisladas: int = 0
    snapshots: int = 0
    estados_mensajeria: int = 0

    @property
    def total(self) -> int:
        return (
            self.pagos + self.liquidaciones + self.cargos_especiales + self.feriados_trabajados
            + self.planes_de_pago + self.cuotas + self.reservas_aisladas + self.snapshots
            + self.estados_mensajeria
        )


def _ids_planes_a_borrar(conn: sqlite3.Connection, periodo_corte: str) -> list[int]:
    return [
        f["IdPlan"]
        for f in conn.execute(
            "SELECT IdPlan FROM PlanPago WHERE MesAnoInicio <= ?", (periodo_corte,)
        ).fetchall()
    ]


def _ids_reservas_aisladas_a_borrar(conn: sqlite3.Connection, periodo_corte: str) -> list[int]:
    return [
        f["IdReservaAislada"]
        for f in conn.execute(
            "SELECT IdReservaAislada FROM ReservaAislada "
            "WHERE COALESCE(PeriodoImputado, substr(Fecha, 1, 7)) <= ?",
            (periodo_corte,),
        ).fetchall()
    ]


def contar_registros_a_depurar(conn: sqlite3.Connection, periodo_corte: str) -> ResumenDepuracion:
    """Cuenta, sin borrar nada todavía, cuántas filas de cada tabla caen
    dentro del período de corte — para mostrarlo en el cartel de
    confirmación antes de ejecutar `depurar_historial_hasta_periodo`
    (mismo criterio que `app.negocio.aumentos.
    cantidad_liquidaciones_a_regenerar`: el número real, no una
    advertencia genérica)."""
    def _contar(sql: str, params: tuple = ()) -> int:
        return conn.execute(sql, params).fetchone()[0]

    ids_planes = _ids_planes_a_borrar(conn, periodo_corte)
    cuotas = 0
    if ids_planes:
        placeholders = ", ".join("?" for _ in ids_planes)
        cuotas = _contar(f"SELECT COUNT(*) FROM CuotaPlan WHERE IdPlan IN ({placeholders})", ids_planes)

    return ResumenDepuracion(
        pagos=_contar(
            "SELECT COUNT(*) FROM HistorialPagos WHERE COALESCE(PeriodoImputado, substr(Fecha, 1, 7)) <= ?",
            (periodo_corte,),
        ),
        liquidaciones=_contar("SELECT COUNT(*) FROM LiquidacionEmitida WHERE Periodo <= ?", (periodo_corte,)),
        cargos_especiales=_contar(
            "SELECT COUNT(*) FROM CargoEspecial WHERE COALESCE(PeriodoImputado, substr(Fecha, 1, 7)) <= ?",
            (periodo_corte,),
        ),
        feriados_trabajados=_contar(
            "SELECT COUNT(*) FROM FeriadoTrabajado WHERE substr(Fecha, 1, 7) <= ?", (periodo_corte,)
        ),
        planes_de_pago=len(ids_planes),
        cuotas=cuotas,
        reservas_aisladas=_contar(
            "SELECT COUNT(*) FROM ReservaAislada WHERE COALESCE(PeriodoImputado, substr(Fecha, 1, 7)) <= ?",
            (periodo_corte,),
        ),
        snapshots=_contar("SELECT COUNT(*) FROM SnapshotMensual WHERE Periodo <= ?", (periodo_corte,)),
        estados_mensajeria=_contar(
            "SELECT COUNT(*) FROM EstadoMensajeriaPeriodo WHERE Periodo <= ?", (periodo_corte,)
        ),
    )


def depurar_historial_hasta_periodo(conn: sqlite3.Connection, periodo_corte: str) -> ResumenDepuracion:
    """Borra, de punta a punta, todo lo que `contar_registros_a_depurar`
    ya contó para ese mismo `periodo_corte` — una sola transacción
    (commit al final, rollback si algo revienta a mitad de camino, para
    no dejar la base a medio borrar).

    Respeta las dos referencias que apuntan HACIA las tablas que se
    borran (con `PRAGMA foreign_keys = ON`, ver `app.db.connection`,
    borrar sin esto rompería con un `IntegrityError`):
    - `Ausencia.IdReservaAislada` (el vínculo "esta ausencia surgió de
      esta reubicación") se limpia a NULL antes de borrar la reserva —
      la Ausencia en sí no se toca, solo deja de señalar a una fila que
      ya no existe.
    - `PlanPago.IdPlanAnterior` (la cadena de refinanciaciones) se
      limpia a NULL en cualquier plan que sobreviva y apunte a uno que
      se va a borrar."""
    resumen = contar_registros_a_depurar(conn, periodo_corte)
    ids_planes = _ids_planes_a_borrar(conn, periodo_corte)
    ids_aisladas = _ids_reservas_aisladas_a_borrar(conn, periodo_corte)

    try:
        if ids_planes:
            placeholders = ", ".join("?" for _ in ids_planes)
            conn.execute(
                f"UPDATE PlanPago SET IdPlanAnterior = NULL WHERE IdPlanAnterior IN ({placeholders})",
                ids_planes,
            )
            conn.execute(f"DELETE FROM CuotaPlan WHERE IdPlan IN ({placeholders})", ids_planes)
            conn.execute(f"DELETE FROM PlanPago WHERE IdPlan IN ({placeholders})", ids_planes)
        if ids_aisladas:
            placeholders = ", ".join("?" for _ in ids_aisladas)
            conn.execute(
                f"UPDATE Ausencia SET IdReservaAislada = NULL WHERE IdReservaAislada IN ({placeholders})",
                ids_aisladas,
            )
            conn.execute(f"DELETE FROM ReservaAislada WHERE IdReservaAislada IN ({placeholders})", ids_aisladas)
        conn.execute(
            "DELETE FROM HistorialPagos WHERE COALESCE(PeriodoImputado, substr(Fecha, 1, 7)) <= ?",
            (periodo_corte,),
        )
        conn.execute("DELETE FROM LiquidacionEmitida WHERE Periodo <= ?", (periodo_corte,))
        conn.execute(
            "DELETE FROM CargoEspecial WHERE COALESCE(PeriodoImputado, substr(Fecha, 1, 7)) <= ?",
            (periodo_corte,),
        )
        conn.execute("DELETE FROM FeriadoTrabajado WHERE substr(Fecha, 1, 7) <= ?", (periodo_corte,))
        conn.execute("DELETE FROM SnapshotMensual WHERE Periodo <= ?", (periodo_corte,))
        conn.execute("DELETE FROM EstadoMensajeriaPeriodo WHERE Periodo <= ?", (periodo_corte,))
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return resumen
