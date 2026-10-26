import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.reinicio_prueba import (
    ajustar_saldo_anterior,
    contar_registros_a_depurar,
    depurar_historial_hasta_periodo,
    profesionales_con_saldo,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_consultorio(conn) -> int:
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Norte")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    return obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)


def _crear_profesional(conn, categoria="R", apellido="Lo Veci") -> int:
    return obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional=categoria, Apellido=apellido)


# --- profesionales_con_saldo / ajustar_saldo_anterior -----------------------------------

def test_profesionales_con_saldo_trae_r_a_y_x(conn):
    """Confirmado por la clienta: un X puede venir de haber sido R/A antes
    de liberar sus horarios, y conservar un saldo arrastrado de esa
    época — B/E/C nunca facturan directo, no van acá."""
    id_r = _crear_profesional(conn, "R", "Lo Veci")
    id_a = _crear_profesional(conn, "A", "Pérez")
    id_x = _crear_profesional(conn, "X", "Inactivo")
    _crear_profesional(conn, "B", "Bonificado")
    _crear_profesional(conn, "E", "Equipo")
    _crear_profesional(conn, "C", "Contacto")

    ids = {f["IdProfesional"] for f in profesionales_con_saldo(conn)}
    assert ids == {id_r, id_a, id_x}


def test_ajustar_saldo_anterior_no_toca_el_actual(conn):
    id_r = _crear_profesional(conn)
    obtener_repositorio(conn, "Profesional").actualizar(id_r, SaldoCuentaAnterior=9999, SaldoCuentaActual=500)

    ajustar_saldo_anterior(conn, id_r, 0.0)

    actualizado = obtener_repositorio(conn, "Profesional").obtener(id_r)
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(0.0)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(500)


# --- contar_registros_a_depurar / depurar_historial_hasta_periodo ----------------------

def test_pagos_se_cuentan_y_borran_por_periodo_imputado(conn):
    id_r = _crear_profesional(conn)
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_r, Monto=-100, PeriodoImputado="2026-10", Fecha="2026-10-15",
    )
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_r, Monto=-200, PeriodoImputado="2026-11", Fecha="2026-11-02",
    )

    resumen = contar_registros_a_depurar(conn, "2026-10")
    assert resumen.pagos == 1
    assert resumen.total == 1

    depurar_historial_hasta_periodo(conn, "2026-10")
    restantes = obtener_repositorio(conn, "HistorialPagos").listar()
    assert len(restantes) == 1
    assert restantes[0]["PeriodoImputado"] == "2026-11"


def test_pago_sin_periodo_imputado_cae_por_la_fecha(conn):
    id_r = _crear_profesional(conn)
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_r, Monto=-50, PeriodoImputado=None, Fecha="2026-10-05",
    )

    resumen = contar_registros_a_depurar(conn, "2026-10")
    assert resumen.pagos == 1

    depurar_historial_hasta_periodo(conn, "2026-10")
    assert obtener_repositorio(conn, "HistorialPagos").listar() == []


def test_liquidaciones_se_borran_por_periodo(conn):
    id_r = _crear_profesional(conn)
    obtener_repositorio(conn, "LiquidacionEmitida").crear(IdProfesional=id_r, Periodo="2026-10")
    obtener_repositorio(conn, "LiquidacionEmitida").crear(IdProfesional=id_r, Periodo="2026-11")

    depurar_historial_hasta_periodo(conn, "2026-10")
    periodos = {f["Periodo"] for f in obtener_repositorio(conn, "LiquidacionEmitida").listar()}
    assert periodos == {"2026-11"}


def test_cargos_especiales_se_borran_por_periodo_imputado(conn):
    id_r = _crear_profesional(conn)
    obtener_repositorio(conn, "CargoEspecial").crear(
        IdProfesional=id_r, Tipo="Débito", Concepto="Ajuste", Monto=100, PeriodoImputado="2026-10",
    )
    obtener_repositorio(conn, "CargoEspecial").crear(
        IdProfesional=id_r, Tipo="Débito", Concepto="Ajuste", Monto=100, PeriodoImputado="2026-11",
    )

    depurar_historial_hasta_periodo(conn, "2026-10")
    periodos = {f["PeriodoImputado"] for f in obtener_repositorio(conn, "CargoEspecial").listar()}
    assert periodos == {"2026-11"}


def test_feriados_trabajados_se_borran_por_la_fecha(conn):
    id_r = _crear_profesional(conn)
    id_consultorio = _crear_consultorio(conn)
    obtener_repositorio(conn, "FeriadoTrabajado").crear(
        IdProfesional=id_r, IdConsultorio=id_consultorio, Fecha="2026-10-12",
        HoraInicio=9, HoraFin=10, FechaCarga="2026-10-12",
    )
    obtener_repositorio(conn, "FeriadoTrabajado").crear(
        IdProfesional=id_r, IdConsultorio=id_consultorio, Fecha="2026-11-01",
        HoraInicio=9, HoraFin=10, FechaCarga="2026-11-01",
    )

    depurar_historial_hasta_periodo(conn, "2026-10")
    fechas = {f["Fecha"] for f in obtener_repositorio(conn, "FeriadoTrabajado").listar()}
    assert fechas == {"2026-11-01"}


def test_plan_de_pago_y_sus_cuotas_se_borran_juntos(conn):
    id_r = _crear_profesional(conn)
    id_plan_viejo = obtener_repositorio(conn, "PlanPago").crear(
        IdProfesional=id_r, MontoRefinanciado=1000, MontoTotalAPagar=1000,
        CantidadCuotas=2, ImportePorCuota=500, MesAnoInicio="2026-09",
    )
    obtener_repositorio(conn, "CuotaPlan").crear(IdPlan=id_plan_viejo, NumeroCuota=1, Monto=500)
    obtener_repositorio(conn, "CuotaPlan").crear(IdPlan=id_plan_viejo, NumeroCuota=2, Monto=500)
    id_plan_nuevo = obtener_repositorio(conn, "PlanPago").crear(
        IdProfesional=id_r, MontoRefinanciado=1000, MontoTotalAPagar=1000,
        CantidadCuotas=1, ImportePorCuota=1000, MesAnoInicio="2026-12",
    )

    resumen = contar_registros_a_depurar(conn, "2026-10")
    assert resumen.planes_de_pago == 1
    assert resumen.cuotas == 2

    depurar_historial_hasta_periodo(conn, "2026-10")
    planes = obtener_repositorio(conn, "PlanPago").listar()
    assert [p["IdPlan"] for p in planes] == [id_plan_nuevo]
    assert obtener_repositorio(conn, "CuotaPlan").listar() == []


def test_plan_nuevo_que_refinancia_uno_borrado_no_rompe_por_fk(conn):
    id_r = _crear_profesional(conn)
    id_plan_viejo = obtener_repositorio(conn, "PlanPago").crear(
        IdProfesional=id_r, MontoRefinanciado=1000, MontoTotalAPagar=1000,
        CantidadCuotas=1, ImportePorCuota=1000, MesAnoInicio="2026-09", Estado="Cancelado",
    )
    id_plan_nuevo = obtener_repositorio(conn, "PlanPago").crear(
        IdProfesional=id_r, MontoRefinanciado=1000, MontoTotalAPagar=1000,
        CantidadCuotas=1, ImportePorCuota=1000, MesAnoInicio="2026-12",
        EsRefinanciacion=1, IdPlanAnterior=id_plan_viejo,
    )

    depurar_historial_hasta_periodo(conn, "2026-10")

    restante = obtener_repositorio(conn, "PlanPago").obtener(id_plan_nuevo)
    assert restante is not None
    assert restante["IdPlanAnterior"] is None


def test_reservas_aisladas_se_borran_por_periodo_imputado(conn):
    id_r = _crear_profesional(conn, "A")
    id_consultorio = _crear_consultorio(conn)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_r, IdConsultorio=id_consultorio, Fecha="2026-10-05",
        HoraInicio=9, HoraFin=10, PeriodoImputado="2026-10",
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_r, IdConsultorio=id_consultorio, Fecha="2026-11-05",
        HoraInicio=9, HoraFin=10, PeriodoImputado="2026-11",
    )

    depurar_historial_hasta_periodo(conn, "2026-10")
    fechas = {f["Fecha"] for f in obtener_repositorio(conn, "ReservaAislada").listar()}
    assert fechas == {"2026-11-05"}


def test_reserva_aislada_sin_periodo_imputado_cae_por_la_fecha(conn):
    id_r = _crear_profesional(conn, "A")
    id_consultorio = _crear_consultorio(conn)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_r, IdConsultorio=id_consultorio, Fecha="2026-10-05",
        HoraInicio=9, HoraFin=10, PeriodoImputado=None,
    )

    depurar_historial_hasta_periodo(conn, "2026-10")
    assert obtener_repositorio(conn, "ReservaAislada").listar() == []


def test_ausencia_que_apunta_a_una_aislada_borrada_queda_sin_romper(conn):
    id_r = _crear_profesional(conn, "A")
    id_consultorio = _crear_consultorio(conn)
    id_aislada = obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_r, IdConsultorio=id_consultorio, Fecha="2026-10-05",
        HoraInicio=9, HoraFin=10, PeriodoImputado="2026-10",
    )
    id_ausencia = obtener_repositorio(conn, "Ausencia").crear(
        IdProfesional=id_r, FechaDesde="2026-10-05", FechaHasta="2026-10-05", IdReservaAislada=id_aislada,
    )

    depurar_historial_hasta_periodo(conn, "2026-10")

    assert obtener_repositorio(conn, "ReservaAislada").listar() == []
    ausencia = obtener_repositorio(conn, "Ausencia").obtener(id_ausencia)
    assert ausencia is not None
    assert ausencia["IdReservaAislada"] is None


def test_snapshots_y_estado_mensajeria_se_borran_por_periodo(conn):
    id_r = _crear_profesional(conn)
    obtener_repositorio(conn, "SnapshotMensual").crear(Periodo="2026-10", FechaGeneracion="2026-10-31")
    obtener_repositorio(conn, "SnapshotMensual").crear(Periodo="2026-11", FechaGeneracion="2026-11-30")
    obtener_repositorio(conn, "EstadoMensajeriaPeriodo").crear(IdProfesional=id_r, Periodo="2026-10")
    obtener_repositorio(conn, "EstadoMensajeriaPeriodo").crear(IdProfesional=id_r, Periodo="2026-11")

    depurar_historial_hasta_periodo(conn, "2026-10")

    periodos_snapshot = {f["Periodo"] for f in obtener_repositorio(conn, "SnapshotMensual").listar()}
    periodos_mensajeria = {f["Periodo"] for f in obtener_repositorio(conn, "EstadoMensajeriaPeriodo").listar()}
    assert periodos_snapshot == {"2026-11"}
    assert periodos_mensajeria == {"2026-11"}


def test_no_toca_llaves_placas_ni_reservas_regulares(conn):
    id_r = _crear_profesional(conn)
    id_consultorio = _crear_consultorio(conn)
    id_llave = obtener_repositorio(conn, "Llave").crear(Nombre="Tipo llave E1", Tipo="Edificio")
    obtener_repositorio(conn, "LlaveMovimiento").crear(
        IdLlave=id_llave, Tipo="Ingreso", Fecha="2026-10-01", Cantidad=1,
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_r, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-10-01",
    )

    depurar_historial_hasta_periodo(conn, "2026-12")

    assert len(obtener_repositorio(conn, "LlaveMovimiento").listar()) == 1
    assert len(obtener_repositorio(conn, "ReservaRegular").listar()) == 1


def test_contar_coincide_con_lo_que_se_termina_borrando(conn):
    id_r = _crear_profesional(conn)
    id_consultorio = _crear_consultorio(conn)
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_r, Monto=-1, PeriodoImputado="2026-10")
    obtener_repositorio(conn, "LiquidacionEmitida").crear(IdProfesional=id_r, Periodo="2026-10")
    obtener_repositorio(conn, "CargoEspecial").crear(
        IdProfesional=id_r, Tipo="Débito", Concepto="x", Monto=1, PeriodoImputado="2026-10",
    )
    obtener_repositorio(conn, "FeriadoTrabajado").crear(
        IdProfesional=id_r, IdConsultorio=id_consultorio, Fecha="2026-10-10",
        HoraInicio=9, HoraFin=10, FechaCarga="2026-10-10",
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_r, IdConsultorio=id_consultorio, Fecha="2026-10-10",
        HoraInicio=9, HoraFin=10, PeriodoImputado="2026-10",
    )
    obtener_repositorio(conn, "SnapshotMensual").crear(Periodo="2026-10", FechaGeneracion="2026-10-31")
    obtener_repositorio(conn, "EstadoMensajeriaPeriodo").crear(IdProfesional=id_r, Periodo="2026-10")
    id_plan = obtener_repositorio(conn, "PlanPago").crear(
        IdProfesional=id_r, MontoRefinanciado=100, MontoTotalAPagar=100,
        CantidadCuotas=1, ImportePorCuota=100, MesAnoInicio="2026-10",
    )
    obtener_repositorio(conn, "CuotaPlan").crear(IdPlan=id_plan, NumeroCuota=1, Monto=100)

    resumen = contar_registros_a_depurar(conn, "2026-10")
    assert resumen.total == 9

    resumen_borrado = depurar_historial_hasta_periodo(conn, "2026-10")
    assert resumen_borrado.total == 9
