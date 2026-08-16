import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.feriados import feriados_relevantes_periodo
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_feriados_relevantes_excluye_domingos_y_puentes(conn):
    repo = obtener_repositorio(conn, "FechasEspeciales")
    repo.crear(Fecha="2026-08-17", Descripcion="Feriado lunes", Tipo="Feriado nacional")  # lunes
    repo.crear(Fecha="2026-08-16", Descripcion="Feriado domingo", Tipo="Feriado nacional")  # domingo
    repo.crear(Fecha="2026-08-18", Descripcion="Puente", Tipo="Puente turístico")  # no descuenta 100%

    relevantes = feriados_relevantes_periodo(conn, 2026, 8)
    fechas = {f["Fecha"] for f in relevantes}
    assert fechas == {"2026-08-17"}
