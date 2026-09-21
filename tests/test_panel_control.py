import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.panel_control import (
    calcular_alertas,
    calcular_estadisticas_ocupacion,
    calcular_estadisticas_profesionales,
    fechas_especiales_proximas_dos_meses,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _fijar_fecha(conn, fecha_iso):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = ? WHERE IdConfiguracion = 1", (fecha_iso,)
    )


def test_alertas_vacias_sin_datos(conn):
    alertas = calcular_alertas(conn)
    assert alertas.total == 0


def test_alerta_deuda_regular_respeta_tolerancia(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=1000)
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Bajo saldo", SaldoCuentaAnterior=500,
    )
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Alto saldo", SaldoCuentaAnterior=5000,
    )
    alertas = calcular_alertas(conn)
    assert len(alertas.deuda_regulares) == 1
    assert alertas.deuda_regulares[0]["Apellido"] == "Alto saldo"


def test_alerta_deuda_aislada_no_tiene_tolerancia(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=1000)
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="A", Apellido="Debe poco", SaldoCuentaAnterior=1,
    )
    alertas = calcular_alertas(conn)
    assert len(alertas.deuda_aisladas) == 1


def test_alerta_fechas_especiales_proximas_respeta_ventana(conn):
    _fijar_fecha(conn, "2026-08-01")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-10", Tipo="Feriado nacional", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-30", Tipo="Feriado nacional", Activo=1)
    alertas = calcular_alertas(conn)
    assert len(alertas.fechas_especiales_proximas) == 1


def test_alerta_categoria_x_con_llaves_pendientes(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="X", Apellido="Inactivo")
    id_llave = obtener_repositorio(conn, "Llave").crear(Nombre="Llave")
    obtener_repositorio(conn, "LlaveMovimiento").crear(
        IdLlave=id_llave, Tipo="Asignación", IdProfesional=id_prof, Fecha="2026-01-01",
    )
    alertas = calcular_alertas(conn)
    assert len(alertas.categoria_x_con_llaves_pendientes) == 1


def test_alerta_backup_vencido_sin_configurar_no_prende(conn):
    alertas = calcular_alertas(conn)
    assert alertas.backup_vencido is False


def test_alerta_backup_vencido_prende_con_backup_desactualizado(conn, tmp_path):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, CarpetaBackup=str(tmp_path / "backups"), FrecuenciaBackupDrive="Diario",
    )
    alertas = calcular_alertas(conn)
    assert alertas.backup_vencido is True


def test_alertas_total_cuenta_el_backup_vencido_como_uno(conn, tmp_path):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, CarpetaBackup=str(tmp_path / "backups"), FrecuenciaBackupDrive="Diario",
    )
    alertas = calcular_alertas(conn)
    assert alertas.total == 1


# ---------------------------------------- cuadritos informativos (Panel de control)


def _profesional(conn, **kwargs):
    kwargs.setdefault("CategoriaProfesional", "R")
    kwargs.setdefault("Apellido", "Test")
    return obtener_repositorio(conn, "Profesional").crear(**kwargs)


def test_estadisticas_profesionales_sin_datos(conn):
    est = calcular_estadisticas_profesionales(conn)
    assert est.con_plan_pago_vigente == 0
    assert est.con_saldo_fuera_de_tolerancia == 0
    assert est.con_reservas_regulares_activas == 0


def test_estadisticas_profesionales_cuenta_planes_activos_no_finalizados(conn):
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "PlanPago").crear(
        IdProfesional=id_prof, MontoRefinanciado=1000, MontoTotalAPagar=1000, CantidadCuotas=1,
        ImportePorCuota=1000, MesAnoInicio="2026-08", Estado="Activo",
    )
    otro_prof = _profesional(conn)
    obtener_repositorio(conn, "PlanPago").crear(
        IdProfesional=otro_prof, MontoRefinanciado=1000, MontoTotalAPagar=1000, CantidadCuotas=1,
        ImportePorCuota=1000, MesAnoInicio="2026-08", Estado="Finalizado",
    )
    assert calcular_estadisticas_profesionales(conn).con_plan_pago_vigente == 1


def test_estadisticas_profesionales_cuenta_saldo_fuera_de_tolerancia(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=1000)
    _profesional(conn, CategoriaProfesional="R", SaldoCuentaAnterior=5000)
    _profesional(conn, CategoriaProfesional="A", SaldoCuentaAnterior=1)
    assert calcular_estadisticas_profesionales(conn).con_saldo_fuera_de_tolerancia == 2


def test_estadisticas_profesionales_cuenta_reservas_regulares_activas(conn):
    _fijar_fecha(conn, "2026-08-15")
    id_prof = _profesional(conn)
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-01-01",
    )
    otro_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=otro_prof, IdConsultorio=id_consultorio, DiaSemana="Martes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-01-01", VigenciaFin="2026-06-30",
    )
    assert calcular_estadisticas_profesionales(conn).con_reservas_regulares_activas == 1


def test_estadisticas_ocupacion_sin_datos(conn):
    est = calcular_estadisticas_ocupacion(conn)
    assert est.ocupacion_regular_pct == 0.0
    assert est.horas_regulares_semanales == 0.0
    assert est.horas_aisladas_mes == 0.0
    assert est.monto_aisladas_mes == 0.0
    assert est.saldo_pendiente_mes == 0.0


def test_estadisticas_ocupacion_horas_aisladas_solo_cuenta_confirmadas(conn):
    _fijar_fecha(conn, "2026-08-15")
    id_prof = _profesional(conn)
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraAisladaActual=1000,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-10", HoraInicio=9, HoraFin=11,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-11", HoraInicio=9, HoraFin=11,
        Estado="Cancelada",
    )
    est = calcular_estadisticas_ocupacion(conn)
    assert est.horas_aisladas_mes == pytest.approx(2.0)
    assert est.monto_aisladas_mes == pytest.approx(2000.0)


def test_estadisticas_ocupacion_saldo_pendiente_es_facturado_menos_cobrado(conn):
    _fijar_fecha(conn, "2026-08-15")
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_prof, Periodo="2026-08", MontoGenerado=10000,
    )
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_prof, Monto=4000, PeriodoImputado="2026-08",
    )
    # Pago de otro período no debe afectar el saldo pendiente de agosto.
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_prof, Monto=1000, PeriodoImputado="2026-07",
    )
    assert calcular_estadisticas_ocupacion(conn).saldo_pendiente_mes == pytest.approx(6000.0)


def test_fechas_especiales_proximas_dos_meses_excluye_las_que_ya_pasaron_este_mes(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-01", Tipo="Feriado nacional", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-14", Tipo="Feriado nacional", Activo=1)
    assert fechas_especiales_proximas_dos_meses(conn) == []


def test_fechas_especiales_proximas_dos_meses_incluye_hoy_y_lo_que_falta_del_mes(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-15", Tipo="Feriado nacional", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-31", Tipo="Feriado nacional", Activo=1)
    fechas = fechas_especiales_proximas_dos_meses(conn)
    assert [f["Fecha"] for f in fechas] == ["2026-08-15", "2026-08-31"]


def test_fechas_especiales_proximas_dos_meses_incluye_los_dos_meses_siguientes(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-30", Tipo="Feriado nacional", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-10-31", Tipo="Feriado nacional", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-11-01", Tipo="Feriado nacional", Activo=1)
    fechas = fechas_especiales_proximas_dos_meses(conn)
    assert [f["Fecha"] for f in fechas] == ["2026-09-30", "2026-10-31"]


def test_fechas_especiales_proximas_dos_meses_ignora_inactivas(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-20", Tipo="Feriado nacional", Activo=0)
    assert fechas_especiales_proximas_dos_meses(conn) == []
