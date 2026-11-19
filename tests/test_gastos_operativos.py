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


def test_sanear_alcance_espacio_general_limpia_los_tres():
    valores = sanear_alcance({"Alcance": "Espacio general", "IdEdificio": 1, "IdUnidad": 2, "IdConsultorio": 3})
    assert valores["IdEdificio"] is None
    assert valores["IdUnidad"] is None
    assert valores["IdConsultorio"] is None


def test_sanear_alcance_sin_alcance_limpia_los_tres():
    valores = sanear_alcance({"IdEdificio": 1, "IdUnidad": 2, "IdConsultorio": 3})
    assert valores["IdEdificio"] is None
    assert valores["IdUnidad"] is None
    assert valores["IdConsultorio"] is None


def test_sanear_alcance_consultorio_limpia_edificio_y_unidad():
    valores = sanear_alcance({"Alcance": "Consultorio", "IdEdificio": 1, "IdUnidad": 2, "IdConsultorio": 3})
    assert valores["IdEdificio"] is None
    assert valores["IdUnidad"] is None
    assert valores["IdConsultorio"] == 3


def test_sanear_alcance_edificio_limpia_tambien_consultorio():
    valores = sanear_alcance({"Alcance": "Edificio", "IdEdificio": 1, "IdUnidad": 2, "IdConsultorio": 3})
    assert valores["IdEdificio"] == 1
    assert valores["IdConsultorio"] is None


def test_sanear_alcance_unidad_limpia_tambien_consultorio():
    valores = sanear_alcance({"Alcance": "Unidad", "IdEdificio": 1, "IdUnidad": 2, "IdConsultorio": 3})
    assert valores["IdUnidad"] == 2
    assert valores["IdConsultorio"] is None


def test_sanear_alcance_localidad_limpia_edificio_unidad_y_consultorio():
    valores = sanear_alcance({
        "Alcance": "Localidad", "IdLocalidad": 1, "IdEdificio": 2, "IdUnidad": 3, "IdConsultorio": 4,
    })
    assert valores["IdLocalidad"] == 1
    assert valores["IdEdificio"] is None
    assert valores["IdUnidad"] is None
    assert valores["IdConsultorio"] is None


def test_sanear_alcance_edificio_limpia_tambien_localidad():
    valores = sanear_alcance({"Alcance": "Edificio", "IdLocalidad": 1, "IdEdificio": 2})
    assert valores["IdLocalidad"] is None
    assert valores["IdEdificio"] == 2


def test_sanear_alcance_espacio_general_limpia_tambien_localidad():
    valores = sanear_alcance({"Alcance": "Espacio general", "IdLocalidad": 1})
    assert valores["IdLocalidad"] is None


def test_texto_afectacion_gasto_espacio_general(conn):
    gasto = obtener_repositorio(conn, "GastoOperativo").obtener(_crear_gasto(conn, Alcance="Espacio general"))
    from app.negocio.gastos_operativos import texto_afectacion_gasto
    assert texto_afectacion_gasto(conn, gasto) == "Espacio general"


def test_texto_afectacion_gasto_localidad(conn):
    from app.negocio.gastos_operativos import texto_afectacion_gasto

    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Ramos Mejía")
    gasto = obtener_repositorio(conn, "GastoOperativo").obtener(
        _crear_gasto(conn, Alcance="Localidad", IdLocalidad=id_localidad)
    )
    assert texto_afectacion_gasto(conn, gasto) == "Ramos Mejía"


def test_texto_afectacion_gasto_edificio(conn):
    from app.negocio.gastos_operativos import texto_afectacion_gasto

    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    gasto = obtener_repositorio(conn, "GastoOperativo").obtener(
        _crear_gasto(conn, Alcance="Edificio", IdEdificio=id_edificio)
    )
    assert texto_afectacion_gasto(conn, gasto) == "Ramos 1"


def test_texto_afectacion_gasto_unidad_y_consultorio(conn):
    from app.negocio.gastos_operativos import texto_afectacion_gasto

    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)

    gasto_unidad = obtener_repositorio(conn, "GastoOperativo").obtener(
        _crear_gasto(conn, Alcance="Unidad", IdUnidad=id_unidad)
    )
    assert texto_afectacion_gasto(conn, gasto_unidad) == "Ramos 1 - 1A"

    gasto_consultorio = obtener_repositorio(conn, "GastoOperativo").obtener(
        _crear_gasto(conn, Alcance="Consultorio", IdConsultorio=id_consultorio)
    )
    assert texto_afectacion_gasto(conn, gasto_consultorio) == "Ramos 1 - 1A - Consultorio 1"
