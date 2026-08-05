import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.feriados import feriados_relevantes_periodo, importar_feriados_argentina
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _datos_falsos(anio):
    return [
        {"dia": 1, "mes": 1, "tipo": "inamovible", "motivo": "Año Nuevo"},
        {"dia": 24, "mes": 3, "tipo": "inamovible", "motivo": "Día Nacional de la Memoria"},
        {"dia": 21, "mes": 4, "tipo": "puente", "motivo": "Día no laborable con fines turísticos"},
        {"dia": 20, "mes": 12, "tipo": "no_laborable", "motivo": "Nochebuena (medio día)"},
    ]


def test_importar_feriados_inserta_y_mapea_tipos(conn):
    cantidad = importar_feriados_argentina(conn, 2026, obtener_datos=_datos_falsos)
    assert cantidad == 4
    feriados = obtener_repositorio(conn, "FechasEspeciales").listar()
    por_fecha = {f["Fecha"]: f for f in feriados}
    assert por_fecha["2026-01-01"]["Tipo"] == "Feriado nacional"
    assert por_fecha["2026-04-21"]["Tipo"] == "Puente turístico"
    assert por_fecha["2026-12-20"]["Tipo"] == "Día no laborable"


def test_importar_feriados_es_idempotente(conn):
    importar_feriados_argentina(conn, 2026, obtener_datos=_datos_falsos)
    segunda_vez = importar_feriados_argentina(conn, 2026, obtener_datos=_datos_falsos)
    assert segunda_vez == 0
    assert len(obtener_repositorio(conn, "FechasEspeciales").listar()) == 4


def test_feriados_relevantes_excluye_domingos_y_puentes(conn):
    repo = obtener_repositorio(conn, "FechasEspeciales")
    repo.crear(Fecha="2026-08-17", Descripcion="Feriado lunes", Tipo="Feriado nacional")  # lunes
    repo.crear(Fecha="2026-08-16", Descripcion="Feriado domingo", Tipo="Feriado nacional")  # domingo
    repo.crear(Fecha="2026-08-18", Descripcion="Puente", Tipo="Puente turístico")  # no descuenta 100%

    relevantes = feriados_relevantes_periodo(conn, 2026, 8)
    fechas = {f["Fecha"] for f in relevantes}
    assert fechas == {"2026-08-17"}
