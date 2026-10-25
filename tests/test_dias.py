from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio import dias
from app.negocio.dias import fecha_actual, periodo_actual, periodo_operativo_actual


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _fijar_periodo_operativo(conn, periodo):
    conn.execute("UPDATE Configuracion SET PeriodoOperativoActual = ? WHERE IdConfiguracion = 1", (periodo,))


def _congelar_hoy_real(monkeypatch, anio, mes, dia):
    class _FechaFija(date):
        @classmethod
        def today(cls):
            return date(anio, mes, dia)

    monkeypatch.setattr(dias, "date", _FechaFija)


def test_periodo_operativo_actual_arranca_en_el_periodo_real_al_sembrar(conn):
    hoy = date.today()
    assert periodo_operativo_actual(conn) == f"{hoy.year:04d}-{hoy.month:02d}"


def test_fecha_actual_sin_avance_pendiente_devuelve_la_fecha_real(conn, monkeypatch):
    _fijar_periodo_operativo(conn, "2026-10")
    _congelar_hoy_real(monkeypatch, 2026, 10, 25)

    assert fecha_actual(conn) == date(2026, 10, 25)
    assert periodo_actual(conn) == "2026-10"


def test_fecha_actual_recorta_al_dia_1_si_se_avanzo_por_delante_de_la_realidad(conn, monkeypatch):
    """"Avanzar de mes" dejó el ancla en noviembre, pero la fecha real
    sigue en octubre: "se ubica virtualmente [...] el día 1 [...]
    mientras sigue en el mes anterior se toma ese paso virtual y se
    mantiene en ese día" (confirmado por la clienta)."""
    _fijar_periodo_operativo(conn, "2026-11")
    _congelar_hoy_real(monkeypatch, 2026, 10, 25)

    assert fecha_actual(conn) == date(2026, 11, 1)
    assert periodo_actual(conn) == "2026-11"


def test_fecha_actual_se_rompe_lo_virtual_cuando_la_realidad_alcanza_el_periodo(conn, monkeypatch):
    _fijar_periodo_operativo(conn, "2026-11")
    _congelar_hoy_real(monkeypatch, 2026, 11, 15)

    assert fecha_actual(conn) == date(2026, 11, 15)


def test_fecha_actual_se_mantiene_en_el_ultimo_dia_si_la_realidad_ya_paso_de_mes_sin_avanzar(conn, monkeypatch):
    """Caso simétrico (confirmado por la clienta): la realidad ya cruzó a
    diciembre pero nunca se apretó "Avanzar de mes" desde octubre —
    seguimos parados en el último día de octubre hasta que se haga el
    avance."""
    _fijar_periodo_operativo(conn, "2026-10")
    _congelar_hoy_real(monkeypatch, 2026, 12, 5)

    assert fecha_actual(conn) == date(2026, 10, 31)
    assert periodo_actual(conn) == "2026-10"


def test_modo_fecha_ficticia_tiene_prioridad_sobre_el_recorte(conn):
    """El modo QA (testing) sigue siendo un override puro, sin relación
    con `periodo_operativo_actual`."""
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = ?, PeriodoOperativoActual = ? "
        "WHERE IdConfiguracion = 1",
        ("2030-05-15", "2026-10"),
    )

    assert fecha_actual(conn) == date(2030, 5, 15)
