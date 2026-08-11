import json

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.estadisticas import calcular_ocupacion, generar_snapshot, rango_horas_por_dia
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def dos_consultorios(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    c1 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )
    c2 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=2, ValorHoraRegularActual=1200,
    )
    return id_edificio, id_unidad, c1, c2


def test_rango_horas_por_dia_default_domingo_no_cuenta(conn):
    rangos = rango_horas_por_dia(conn)
    assert "Domingo" not in rangos
    assert rangos["Lunes"] == (9, 21)
    assert rangos["Sábado"] == (9, 15)


def test_rango_horas_por_dia_usa_configuracion_si_esta_cargada(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, RangosEstadisticasOcupacion=json.dumps({"Lunes": [10, 18]}),
    )
    rangos = rango_horas_por_dia(conn)
    assert rangos == {"Lunes": (10, 18)}


def test_ocupacion_general_sin_reservas_es_cero(conn, dos_consultorios):
    ocupacion = calcular_ocupacion(conn, 2026, 8)
    assert ocupacion.general == 0.0


def test_ocupacion_100_por_ciento_cuando_todo_esta_reservado(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    c1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Test")
    for dia in ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes"):
        obtener_repositorio(conn, "ReservaRegular").crear(
            IdProfesional=id_prof, IdConsultorio=c1, DiaSemana=dia, HoraInicio=9, HoraFin=21, VigenciaInicio="2026-01-01",
        )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=c1, DiaSemana="Sábado", HoraInicio=9, HoraFin=15, VigenciaInicio="2026-01-01",
    )
    ocupacion = calcular_ocupacion(conn, 2026, 8)
    assert ocupacion.general == pytest.approx(100.0)


def test_ocupacion_por_consultorio_desglosa_individualmente(conn, dos_consultorios):
    _, _, c1, c2 = dos_consultorios
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Test")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=c1, DiaSemana="Lunes", HoraInicio=9, HoraFin=21, VigenciaInicio="2026-01-01",
    )
    ocupacion = calcular_ocupacion(conn, 2026, 8)
    assert ocupacion.por_consultorio[c1].porcentaje > 0
    assert ocupacion.por_consultorio[c2].porcentaje == 0.0


def test_generar_snapshot_persiste_valores_y_ocupacion(conn, dos_consultorios):
    _, _, c1, c2 = dos_consultorios
    id_snapshot = generar_snapshot(conn, "2026-08", porcentaje_aumento_aplicado=5.0)
    snapshot = obtener_repositorio(conn, "SnapshotMensual").obtener(id_snapshot)

    assert snapshot["Periodo"] == "2026-08"
    assert snapshot["PorcentajeAumentoAplicado"] == pytest.approx(5.0)
    assert snapshot["PorcentajeOcupacionGeneral"] == pytest.approx(0.0)

    valores = json.loads(snapshot["ValoresConsultorios"])
    assert valores[str(c1)] == pytest.approx(1000)
    assert valores[str(c2)] == pytest.approx(1200)
