import pytest

from app.db.init_db import init_database
from app.repositorio.registro import TABLAS, obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    yield connection
    connection.close()


def test_todas_las_tablas_se_crean(conn):
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tablas_creadas = {fila["name"] for fila in cur.fetchall()}
    for tabla in TABLAS:
        assert tabla in tablas_creadas


def test_crud_edificio(conn):
    repo = obtener_repositorio(conn, "Edificio")
    id_edificio = repo.crear(
        Nombre="Ramos 1", Domicilio="Av. Rivadavia 13876", DomicilioLocalidad="Ramos Mejía"
    )

    edificio = repo.obtener(id_edificio)
    assert edificio["Nombre"] == "Ramos 1"

    repo.actualizar(id_edificio, Domicilio="Av. Rivadavia 13900")
    assert repo.obtener(id_edificio)["Domicilio"] == "Av. Rivadavia 13900"

    assert len(repo.listar()) == 1

    repo.eliminar(id_edificio)
    assert repo.obtener(id_edificio) is None


def test_crud_con_relacion_edificio_unidad(conn):
    edificios = obtener_repositorio(conn, "Edificio")
    unidades = obtener_repositorio(conn, "Unidad")

    id_edificio = edificios.crear(Nombre="Ramos 1")
    id_unidad = unidades.crear(IdEdificio=id_edificio, Departamento='7mo "L"', WiFi=1)

    unidad = unidades.obtener(id_unidad)
    assert unidad["IdEdificio"] == id_edificio
    assert unidad["WiFi"] == 1


def test_categoria_profesional_invalida_falla(conn):
    profesionales = obtener_repositorio(conn, "Profesional")
    with pytest.raises(Exception):
        profesionales.crear(CategoriaProfesional="Z", Apellido="Lo Veci")


def test_listar_con_filtro(conn):
    edificios = obtener_repositorio(conn, "Edificio")
    edificios.crear(Nombre="Ramos 1")
    edificios.crear(Nombre="Ramos 2")

    resultado = edificios.listar(Nombre="Ramos 2")
    assert len(resultado) == 1
    assert resultado[0]["Nombre"] == "Ramos 2"
