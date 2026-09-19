import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.gastos_operativos import gasto_en_conflicto, sanear_alcance
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_gasto(conn, **kwargs):
    campos = dict(Periodo="2026-08", Concepto="Limpieza", Monto=1000, Origen="Manual")
    campos.update(kwargs)
    return obtener_repositorio(conn, "GastoOperativo").crear(**campos)


def test_sin_gastos_no_hay_conflicto(conn):
    assert gasto_en_conflicto(conn, periodo="2026-08", concepto="Limpieza", origen="Manual") is None


def test_mismo_origen_no_es_conflicto(conn):
    _crear_gasto(conn, Origen="Manual")
    assert gasto_en_conflicto(conn, periodo="2026-08", concepto="Limpieza", origen="Manual") is None


def test_origen_distinto_mismo_periodo_y_concepto_es_conflicto(conn):
    id_gasto = _crear_gasto(conn, Origen="Manual")
    conflicto = gasto_en_conflicto(conn, periodo="2026-08", concepto="Limpieza", origen="Importado")
    assert conflicto is not None
    assert conflicto["IdGasto"] == id_gasto


def test_distinto_periodo_no_es_conflicto(conn):
    _crear_gasto(conn, Periodo="2026-08", Origen="Manual")
    assert gasto_en_conflicto(conn, periodo="2026-09", concepto="Limpieza", origen="Importado") is None


def test_distinto_concepto_no_es_conflicto(conn):
    _crear_gasto(conn, Concepto="Limpieza", Origen="Manual")
    assert gasto_en_conflicto(conn, periodo="2026-08", concepto="Seguridad", origen="Importado") is None


def test_excluye_el_propio_registro_al_editar(conn):
    id_gasto = _crear_gasto(conn, Origen="Manual")
    conflicto = gasto_en_conflicto(
        conn, periodo="2026-08", concepto="Limpieza", origen="Manual", id_gasto_actual=id_gasto,
    )
    assert conflicto is None


def test_sin_origen_no_evalua_conflicto(conn):
    _crear_gasto(conn, Origen="Manual")
    assert gasto_en_conflicto(conn, periodo="2026-08", concepto="Limpieza", origen=None) is None


def test_sanear_alcance_edificio_limpia_unidad():
    valores = sanear_alcance({"Alcance": "Edificio", "IdEdificio": 1, "IdUnidad": 2})
    assert valores["IdEdificio"] == 1
    assert valores["IdUnidad"] is None


def test_sanear_alcance_unidad_limpia_edificio():
    valores = sanear_alcance({"Alcance": "Unidad", "IdEdificio": 1, "IdUnidad": 2})
    assert valores["IdEdificio"] is None
    assert valores["IdUnidad"] == 2


def test_sanear_alcance_espacio_general_limpia_los_dos():
    valores = sanear_alcance({"Alcance": "Espacio general", "IdEdificio": 1, "IdUnidad": 2})
    assert valores["IdEdificio"] is None
    assert valores["IdUnidad"] is None


def test_sanear_alcance_sin_alcance_limpia_los_dos():
    valores = sanear_alcance({"IdEdificio": 1, "IdUnidad": 2})
    assert valores["IdEdificio"] is None
    assert valores["IdUnidad"] is None
