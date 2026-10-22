import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.formato import (
    decimales_configurados,
    decimales_total_liquidacion,
    formatear_moneda,
    formatear_valor,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_decimales_por_defecto_es_2(conn):
    assert decimales_configurados(conn) == 2


def test_decimales_configurable(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, CantidadDecimales=0)
    assert decimales_configurados(conn) == 0


def test_decimales_total_liquidacion_por_defecto_es_2(conn):
    assert decimales_total_liquidacion(conn) == 2


def test_decimales_total_liquidacion_configurable_independiente_de_cantidad_decimales(conn):
    """Son dos parámetros distintos: cambiar uno no toca el otro."""
    obtener_repositorio(conn, "Configuracion").actualizar(1, DecimalesTotalLiquidacion=0)
    assert decimales_total_liquidacion(conn) == 0
    assert decimales_configurados(conn) == 2


def test_formatear_moneda_respeta_decimales():
    assert formatear_moneda(1234.5, decimales=2) == "$ 1.234,50"
    assert formatear_moneda(1234.7, decimales=0) == "$ 1.235"
    assert formatear_moneda(-1234.7, decimales=0) == "-$ 1.235"


def test_formatear_valor_omite_decimales_cuando_es_redondo():
    assert formatear_valor(1000, decimales=2) == "$ 1.000"
    assert formatear_valor(1050.5, decimales=2) == "$ 1.050,50"
