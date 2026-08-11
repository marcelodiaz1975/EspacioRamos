import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.liquidaciones import emitir_liquidacion
from app.negocio.mensajes import (
    _lista_con_y,
    determinar_situacion,
    mensaje_grupal,
    mensaje_situacion,
    nombre_para_mensaje,
)
from app.negocio.pagos import crear_plan_pago
from app.repositorio.registro import obtener_repositorio

PERIODO = "2026-08"


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )


def _crear_regular(conn, consultorio, **kwargs):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Test", **kwargs)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio="2026-01-01",
    )
    return id_prof


def test_nombre_para_mensaje_prioriza_apodo(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, Apodo="Male", NombrePila="Marcela", Tratamiento="Lic.")
    prof = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert nombre_para_mensaje(prof) == "Male"


def test_nombre_para_mensaje_usa_nombre_pila_sin_apodo(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, NombrePila="Marcela", Tratamiento="Lic.")
    prof = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert nombre_para_mensaje(prof) == "Marcela"


def test_nombre_para_mensaje_usa_tratamiento_y_apellido_como_ultimo_recurso(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, Tratamiento="Lic.")
    prof = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert nombre_para_mensaje(prof) == "Lic. Test"


def test_situacion_1_deuda_alta_liquidacion_no_enviada(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, SaldoCuentaAnterior=50000)
    assert determinar_situacion(conn, id_prof, PERIODO) == "1"


def test_situacion_3_deuda_baja_liquidacion_no_enviada(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    assert determinar_situacion(conn, id_prof, PERIODO) == "3"


def test_situacion_2_liquidacion_enviada_sin_plan(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    id_liq, _ = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    obtener_repositorio(conn, "LiquidacionEmitida").actualizar(id_liq, EstadoEnvio="Enviada")
    assert determinar_situacion(conn, id_prof, PERIODO) == "2"


def test_situacion_5_con_plan_liquidacion_no_enviada(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    crear_plan_pago(conn, id_profesional=id_prof, monto_refinanciado=3000, cantidad_cuotas=3, mes_ano_inicio=PERIODO)
    assert determinar_situacion(conn, id_prof, PERIODO) == "5"


def test_situacion_4_con_plan_liquidacion_enviada(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    crear_plan_pago(conn, id_profesional=id_prof, monto_refinanciado=3000, cantidad_cuotas=3, mes_ano_inicio=PERIODO)
    id_liq, _ = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    obtener_repositorio(conn, "LiquidacionEmitida").actualizar(id_liq, EstadoEnvio="Enviada")
    assert determinar_situacion(conn, id_prof, PERIODO) == "4"


def test_situacion_none_para_categoria_sin_liquidacion_propia(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Aislada")
    assert determinar_situacion(conn, id_prof, PERIODO) is None


def test_mensaje_situacion_incluye_nombre_y_saldo(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, Apodo="Male", SaldoCuentaAnterior=50000)
    texto = mensaje_situacion(conn, id_prof, PERIODO)
    assert "Male" in texto
    assert "50.000" in texto


def test_mensaje_situacion_rechaza_categoria_no_r(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Aislada")
    with pytest.raises(ValueError):
        mensaje_situacion(conn, id_prof, PERIODO)


def test_lista_con_y_gramatica():
    assert _lista_con_y([]) == ""
    assert _lista_con_y(["X"]) == "X"
    assert _lista_con_y(["X", "Z"]) == "X y Z"
    assert _lista_con_y(["X", "Z", "W"]) == "X, Z y W"


def test_mensaje_grupal_sin_feriados(conn):
    texto = mensaje_grupal(conn, PERIODO)
    assert "LIQUIDACIONES DE SEPTIEMBRE" in texto
    assert "FERIADOS" not in texto


def test_mensaje_grupal_con_un_feriado_concuerda_en_singular(conn):
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-07", Tipo="Feriado nacional")
    texto = mensaje_grupal(conn, PERIODO)
    assert "hay un feriado" in texto
    assert "se descuenta al 100%" in texto
    assert "la de octubre" in texto


def test_mensaje_grupal_con_varios_feriados_concuerda_en_plural(conn):
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-07", Tipo="Feriado nacional")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-21", Tipo="Día no laborable")
    texto = mensaje_grupal(conn, PERIODO)
    assert "hay feriados" in texto
    assert "se descuentan al 100%" in texto
    assert " y " in texto
