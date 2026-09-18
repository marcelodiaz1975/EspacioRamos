import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.detalles_complementarios import reordenar_al_guardar
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _limpiar(conn) -> None:
    """Los tests arrancan desde cero (sin los ítems sembrados por
    defecto), para no depender de cuántos trae el seed."""
    conn.execute("DELETE FROM DetalleComplementarioPropuesta")
    conn.commit()


def _crear(conn, orden, titulo="Título"):
    return obtener_repositorio(conn, "DetalleComplementarioPropuesta").crear(Orden=orden, Titulo=titulo, Texto="Texto")


def test_reordenar_al_guardar_nuevo_sin_orden_va_al_final(conn):
    _limpiar(conn)
    _crear(conn, 1)
    _crear(conn, 2)
    valores = reordenar_al_guardar(conn, {"Titulo": "Nueva", "Texto": "x", "Orden": None}, None)
    assert valores["Orden"] == 3


def test_reordenar_al_guardar_insertar_en_medio_corre_los_demas(conn):
    _limpiar(conn)
    id_uno = _crear(conn, 1)
    id_dos = _crear(conn, 2)
    id_tres = _crear(conn, 3)

    valores = reordenar_al_guardar(conn, {"Titulo": "Nueva", "Texto": "x", "Orden": 2}, None)

    assert valores["Orden"] == 2
    repo = obtener_repositorio(conn, "DetalleComplementarioPropuesta")
    assert repo.obtener(id_uno)["Orden"] == 1
    assert repo.obtener(id_dos)["Orden"] == 3
    assert repo.obtener(id_tres)["Orden"] == 4


def test_reordenar_al_guardar_orden_fuera_de_rango_se_clampea(conn):
    _limpiar(conn)
    _crear(conn, 1)
    _crear(conn, 2)
    valores = reordenar_al_guardar(conn, {"Titulo": "Nueva", "Texto": "x", "Orden": 99}, None)
    assert valores["Orden"] == 3


def test_reordenar_al_guardar_editar_sin_cambiar_orden_no_toca_hermanos(conn):
    _limpiar(conn)
    id_uno = _crear(conn, 1)
    id_dos = _crear(conn, 2)
    registro = obtener_repositorio(conn, "DetalleComplementarioPropuesta").obtener(id_dos)

    valores = reordenar_al_guardar(conn, {"Titulo": "Dos", "Texto": "x", "Orden": 2}, registro)

    assert valores["Orden"] == 2
    assert obtener_repositorio(conn, "DetalleComplementarioPropuesta").obtener(id_uno)["Orden"] == 1


def test_reordenar_al_guardar_mover_al_principio_corre_a_los_demas(conn):
    _limpiar(conn)
    id_uno = _crear(conn, 1)
    id_dos = _crear(conn, 2)
    id_tres = _crear(conn, 3)
    registro = obtener_repositorio(conn, "DetalleComplementarioPropuesta").obtener(id_tres)

    valores = reordenar_al_guardar(conn, {"Titulo": "Tres", "Texto": "x", "Orden": 1}, registro)

    assert valores["Orden"] == 1
    repo = obtener_repositorio(conn, "DetalleComplementarioPropuesta")
    assert repo.obtener(id_uno)["Orden"] == 2
    assert repo.obtener(id_dos)["Orden"] == 3
