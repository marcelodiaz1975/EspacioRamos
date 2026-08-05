import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.ausencias import crear_ausencia, esta_ausente
from app.negocio.reservas import crear_reserva_aislada, crear_reserva_regular
from app.repositorio.registro import obtener_repositorio


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
    return obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)


@pytest.fixture
def profesional(conn):
    return obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")


def test_esta_ausente_todos_los_consultorios(conn, profesional):
    crear_ausencia(conn, id_profesional=profesional, fecha_desde="2026-08-10", fecha_hasta="2026-08-14")
    assert esta_ausente(conn, profesional, "2026-08-12", id_consultorio=99) is True
    assert esta_ausente(conn, profesional, "2026-08-20", id_consultorio=99) is False


def test_esta_ausente_consultorio_especifico(conn, profesional, consultorio):
    crear_ausencia(
        conn, id_profesional=profesional, fecha_desde="2026-08-10", fecha_hasta="2026-08-14",
        id_consultorio=consultorio,
    )
    assert esta_ausente(conn, profesional, "2026-08-12", id_consultorio=consultorio) is True
    assert esta_ausente(conn, profesional, "2026-08-12", id_consultorio=consultorio + 1) is False


def test_ausencia_libera_consultorio_para_aislada_de_otro_profesional(conn, profesional, consultorio):
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Gomez")
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    # 2026-08-10 es lunes
    crear_ausencia(conn, id_profesional=profesional, fecha_desde="2026-08-10", fecha_hasta="2026-08-10")

    id_reserva, advertencias = crear_reserva_aislada(
        conn, id_profesional=otro_profesional, id_consultorio=consultorio,
        fecha="2026-08-10", hora_inicio=14, hora_fin=15,
    )
    assert id_reserva is not None
    assert advertencias == []
