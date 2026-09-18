import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.condiciones_normas import reordenar_al_guardar
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _limpiar(conn) -> None:
    """Los tests arrancan desde cero (sin las condiciones sembradas por
    defecto), para no depender de cuántas trae el seed."""
    conn.execute("DELETE FROM CondicionNorma")
    conn.commit()


def _crear(conn, numero, titulo="Título"):
    return obtener_repositorio(conn, "CondicionNorma").crear(Numero=numero, Titulo=titulo, Texto="Texto")


def test_reordenar_al_guardar_nuevo_sin_numero_va_al_final(conn):
    _limpiar(conn)
    _crear(conn, 1)
    _crear(conn, 2)
    valores = reordenar_al_guardar(conn, {"Titulo": "Nueva", "Texto": "x", "Numero": None}, None)
    assert valores["Numero"] == 3


def test_reordenar_al_guardar_insertar_en_medio_corre_los_demas(conn):
    _limpiar(conn)
    id_uno = _crear(conn, 1)
    id_dos = _crear(conn, 2)
    id_tres = _crear(conn, 3)

    valores = reordenar_al_guardar(conn, {"Titulo": "Nueva", "Texto": "x", "Numero": 2}, None)

    assert valores["Numero"] == 2
    repo = obtener_repositorio(conn, "CondicionNorma")
    assert repo.obtener(id_uno)["Numero"] == 1
    assert repo.obtener(id_dos)["Numero"] == 3
    assert repo.obtener(id_tres)["Numero"] == 4


def test_reordenar_al_guardar_numero_fuera_de_rango_se_clampea(conn):
    _limpiar(conn)
    _crear(conn, 1)
    _crear(conn, 2)
    valores = reordenar_al_guardar(conn, {"Titulo": "Nueva", "Texto": "x", "Numero": 99}, None)
    assert valores["Numero"] == 3


def test_reordenar_al_guardar_numero_menor_a_uno_se_clampea(conn):
    _limpiar(conn)
    _crear(conn, 1)
    valores = reordenar_al_guardar(conn, {"Titulo": "Nueva", "Texto": "x", "Numero": 0}, None)
    assert valores["Numero"] == 1


def test_reordenar_al_guardar_editar_sin_cambiar_numero_no_toca_hermanos(conn):
    _limpiar(conn)
    id_uno = _crear(conn, 1)
    id_dos = _crear(conn, 2)
    registro = obtener_repositorio(conn, "CondicionNorma").obtener(id_dos)

    valores = reordenar_al_guardar(conn, {"Titulo": "Dos", "Texto": "x", "Numero": 2}, registro)

    assert valores["Numero"] == 2
    assert obtener_repositorio(conn, "CondicionNorma").obtener(id_uno)["Numero"] == 1


def test_reordenar_al_guardar_mover_al_principio_corre_a_los_demas(conn):
    _limpiar(conn)
    id_uno = _crear(conn, 1)
    id_dos = _crear(conn, 2)
    id_tres = _crear(conn, 3)
    registro = obtener_repositorio(conn, "CondicionNorma").obtener(id_tres)

    valores = reordenar_al_guardar(conn, {"Titulo": "Tres", "Texto": "x", "Numero": 1}, registro)

    assert valores["Numero"] == 1
    repo = obtener_repositorio(conn, "CondicionNorma")
    assert repo.obtener(id_uno)["Numero"] == 2
    assert repo.obtener(id_dos)["Numero"] == 3
