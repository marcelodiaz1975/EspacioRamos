import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.listas_editables import opciones_lista, reordenar_al_guardar, valores_lista
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


def _crear_prueba(conn, valor, orden):
    return obtener_repositorio(conn, "ListasEditables").crear(TipoLista="Prueba", Valor=valor, Orden=orden)


def test_reordenar_al_guardar_nuevo_sin_orden_va_al_final(conn):
    _crear_prueba(conn, "Uno", 0)
    _crear_prueba(conn, "Dos", 1)
    valores = reordenar_al_guardar(conn, {"TipoLista": "Prueba", "Valor": "Tres", "Orden": None}, None)
    assert valores["Orden"] == 2
    assert valores_lista(conn, "Prueba") == ["Uno", "Dos"]  # todavía no se creó la fila nueva


def test_reordenar_al_guardar_insertar_en_medio_corre_los_demas(conn):
    id_uno = _crear_prueba(conn, "Uno", 0)
    id_dos = _crear_prueba(conn, "Dos", 1)
    id_tres = _crear_prueba(conn, "Tres", 2)

    valores = reordenar_al_guardar(conn, {"TipoLista": "Prueba", "Valor": "Nuevo", "Orden": 1}, None)

    assert valores["Orden"] == 1
    repo = obtener_repositorio(conn, "ListasEditables")
    assert repo.obtener(id_uno)["Orden"] == 0
    assert repo.obtener(id_dos)["Orden"] == 2
    assert repo.obtener(id_tres)["Orden"] == 3


def test_reordenar_al_guardar_orden_fuera_de_rango_se_clampea(conn):
    _crear_prueba(conn, "Uno", 0)
    _crear_prueba(conn, "Dos", 1)
    valores = reordenar_al_guardar(conn, {"TipoLista": "Prueba", "Valor": "Tres", "Orden": 99}, None)
    assert valores["Orden"] == 2


def test_reordenar_al_guardar_editar_sin_cambiar_orden_no_toca_hermanos(conn):
    id_uno = _crear_prueba(conn, "Uno", 0)
    id_dos = _crear_prueba(conn, "Dos", 1)
    registro = obtener_repositorio(conn, "ListasEditables").obtener(id_dos)

    valores = reordenar_al_guardar(conn, {"TipoLista": "Prueba", "Valor": "Dos", "Orden": 1}, registro)

    assert valores["Orden"] == 1
    assert obtener_repositorio(conn, "ListasEditables").obtener(id_uno)["Orden"] == 0


def test_reordenar_al_guardar_mover_a_principio_corre_a_los_demas(conn):
    id_uno = _crear_prueba(conn, "Uno", 0)
    id_dos = _crear_prueba(conn, "Dos", 1)
    id_tres = _crear_prueba(conn, "Tres", 2)
    registro = obtener_repositorio(conn, "ListasEditables").obtener(id_tres)

    valores = reordenar_al_guardar(conn, {"TipoLista": "Prueba", "Valor": "Tres", "Orden": 0}, registro)

    assert valores["Orden"] == 0
    repo = obtener_repositorio(conn, "ListasEditables")
    assert repo.obtener(id_uno)["Orden"] == 1
    assert repo.obtener(id_dos)["Orden"] == 2


def test_reordenar_al_guardar_cambiar_tipo_lista_cierra_el_hueco_anterior(conn):
    id_uno = _crear_prueba(conn, "Uno", 0)
    id_dos = _crear_prueba(conn, "Dos", 1)
    id_tres = _crear_prueba(conn, "Tres", 2)
    registro = obtener_repositorio(conn, "ListasEditables").obtener(id_dos)

    valores = reordenar_al_guardar(conn, {"TipoLista": "OtraLista", "Valor": "Dos", "Orden": None}, registro)

    assert valores["Orden"] == 0  # primer ítem de OtraLista
    repo = obtener_repositorio(conn, "ListasEditables")
    assert repo.obtener(id_uno)["Orden"] == 0
    assert repo.obtener(id_tres)["Orden"] == 1  # se corrió para cerrar el hueco que dejó "Dos"
