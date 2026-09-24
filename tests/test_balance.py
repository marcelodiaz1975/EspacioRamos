import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.balance import (
    ingresos_feriados_trabajados_periodo,
    resultado_periodo,
    total_gastos_periodo,
    total_ingresos_periodo,
)
from app.negocio.liquidaciones import emitir_liquidacion
from app.repositorio.registro import obtener_repositorio

VALOR_HORA_REGULAR = 1000
VALOR_HORA_AISLADA = 500
PERIODO = "2026-08"
PERIODO_ANTERIOR = "2026-07"


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
        IdUnidad=id_unidad, NumeroConsultorio=1,
        ValorHoraRegularActual=VALOR_HORA_REGULAR, ValorHoraAisladaActual=VALOR_HORA_AISLADA,
    )


def _profesional_con_reserva_lunes(conn, consultorio, horas=2):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=10 + horas, VigenciaInicio="2026-01-01", VigenciaFin=None,
    )
    return id_prof


def test_total_ingresos_periodo_suma_regulares_aisladas_y_feriados_trabajados(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "FeriadoTrabajado").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-08-17",
        HoraInicio=9, HoraFin=11, AplicaRecargo=0, FechaCarga="2026-08-01",
    )
    regulares, aisladas, feriados = total_ingresos_periodo(conn, PERIODO)
    assert regulares == pytest.approx(10000.0)  # 5 lunes de agosto 2026 x 2hs x 1000
    assert aisladas == 0.0
    assert feriados == pytest.approx(2000.0)  # 2hs x 1000, sin descuento ni recargo


def test_ingresos_feriados_trabajados_avisado_despues_de_emitir_se_traslada_al_periodo_siguiente(conn, consultorio):
    """Mismo criterio que `_calcular_feriados_trabajados`: si se avisa
    después de emitida la liquidación del mes del feriado, el cargo
    entra en la liquidación del mes siguiente — confirmado por la
    clienta: "quiero que se contemple dentro de los ingresos en el
    período en el cual se carga en la liquidación, no importa la fecha
    del feriado"."""
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO_ANTERIOR, fecha_emision="2026-07-05")
    obtener_repositorio(conn, "FeriadoTrabajado").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-07-09",
        HoraInicio=9, HoraFin=11, AplicaRecargo=0, FechaCarga="2026-07-20",  # avisó después de emitida julio
    )
    assert ingresos_feriados_trabajados_periodo(conn, PERIODO_ANTERIOR) == 0.0
    assert ingresos_feriados_trabajados_periodo(conn, PERIODO) == pytest.approx(2000.0)


def test_ingresos_filtra_por_consultorio(conn, consultorio):
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=obtener_repositorio(conn, "Unidad").crear(
            IdEdificio=obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2"), Departamento="1",
        ),
        NumeroConsultorio=1, ValorHoraRegularActual=VALOR_HORA_REGULAR, ValorHoraAisladaActual=VALOR_HORA_AISLADA,
    )
    _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    regulares, _, _ = total_ingresos_periodo(conn, PERIODO, ids_consultorio=[otro_consultorio])
    assert regulares == 0.0
    regulares, _, _ = total_ingresos_periodo(conn, PERIODO, ids_consultorio=[consultorio])
    assert regulares == pytest.approx(10000.0)


def test_total_gastos_periodo_incluye_generales_sin_filtro(conn):
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Alquiler", Monto=5000, Alcance="Espacio general",
    )
    assert total_gastos_periodo(conn, PERIODO) == pytest.approx(5000.0)


def test_total_gastos_periodo_excluye_generales_con_filtro_puntual(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Alquiler", Monto=5000, Alcance="Espacio general",
    )
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Limpieza", Monto=1000, Alcance="Edificio", IdEdificio=id_edificio,
    )
    assert total_gastos_periodo(conn, PERIODO, id_edificio=id_edificio) == pytest.approx(1000.0)


def test_total_gastos_periodo_unidad_hereda_de_su_edificio_no_de_otros(conn):
    id_edificio_1 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_edificio_2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2")
    id_unidad_1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_1, Departamento="1")
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Limpieza", Monto=1000, Alcance="Unidad", IdUnidad=id_unidad_1,
    )
    assert total_gastos_periodo(conn, PERIODO, id_edificio=id_edificio_1) == pytest.approx(1000.0)
    assert total_gastos_periodo(conn, PERIODO, id_edificio=id_edificio_2) == 0.0


def test_resultado_periodo_es_ingresos_menos_gastos(conn, consultorio):
    _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Alquiler", Monto=3000, Alcance="Espacio general",
    )
    ingresos, gastos, resultado = resultado_periodo(conn, PERIODO)
    assert ingresos == pytest.approx(10000.0)
    assert gastos == pytest.approx(3000.0)
    assert resultado == pytest.approx(7000.0)


def test_resultado_periodo_con_filtro_puntual_excluye_gastos_generales(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    assert id_prof
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Alquiler", Monto=3000, Alcance="Espacio general",
    )
    ingresos, gastos, resultado = resultado_periodo(conn, PERIODO, id_consultorio=consultorio)
    assert ingresos == pytest.approx(10000.0)
    assert gastos == 0.0
    assert resultado == pytest.approx(10000.0)
