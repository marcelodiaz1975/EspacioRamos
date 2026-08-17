import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.listas_editables import opciones_lista, valores_lista
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_valores_lista_devuelve_los_sembrados_en_orden(conn):
    assert valores_lista(conn, "TipoLlave") == ["Unidad", "Edificio", "No especificada"]


def test_valores_lista_respeta_el_campo_orden(conn):
    obtener_repositorio(conn, "ListasEditables").crear(TipoLista="Prueba", Valor="Segundo", Orden=2)
    obtener_repositorio(conn, "ListasEditables").crear(TipoLista="Prueba", Valor="Primero", Orden=1)
    assert valores_lista(conn, "Prueba") == ["Primero", "Segundo"]


def test_valores_lista_omite_inactivos(conn):
    obtener_repositorio(conn, "ListasEditables").crear(TipoLista="Prueba", Valor="Activo", Activo=1, Orden=1)
    obtener_repositorio(conn, "ListasEditables").crear(TipoLista="Prueba", Valor="Inactivo", Activo=0, Orden=2)
    assert valores_lista(conn, "Prueba") == ["Activo"]


def test_valores_lista_tipo_sin_registros_devuelve_vacio(conn):
    assert valores_lista(conn, "NoExiste") == []


def test_condicion_fiscal_tiene_consumidor_final_primero(conn):
    """Sección 8.2: "Condición fiscal (D: Consumidor Final)" — el default
    tiene que ser el primero de la lista, igual que las demás."""
    assert valores_lista(conn, "CondicionFiscal")[0] == "Consumidor Final"


def test_opciones_lista_devuelve_tuplas_valor_valor(conn):
    opciones = opciones_lista("TipoLlave")(conn)
    assert opciones == [("Unidad", "Unidad"), ("Edificio", "Edificio"), ("No especificada", "No especificada")]
