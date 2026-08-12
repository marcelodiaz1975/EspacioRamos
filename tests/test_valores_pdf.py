import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.pdf.estilos import COLOR_NIVEL_1
from app.pdf.valores_pdf import bloques_esquema_descuentos
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _limpiar_esquema(conn):
    conn.execute("DELETE FROM EsquemaDescuentos")
    conn.commit()


def _cargar_tramos(conn, tramos):
    repo = obtener_repositorio(conn, "EsquemaDescuentos")
    for desde, hasta, pct in tramos:
        repo.crear(HorasSemanalesDesde=desde, HorasSemanalesHasta=hasta, PorcentajeDescuento=pct, Activo=1)


def test_completa_la_ultima_fila_repitiendo_el_tope(conn):
    """26 tramos (el default sembrado) -> filas de 9+9+8; la última fila
    tiene que completarse con un tramo de relleno (Hasta 54hs, mismo tope
    25%) para llegar a 9 columnas también."""
    _limpiar_esquema(conn)
    tramos = [(h - 2, h, min(h // 2, 25)) for h in range(2, 53, 2)]  # 26 tramos, tope en 25%
    _cargar_tramos(conn, tramos)

    tablas = bloques_esquema_descuentos(conn, ancho=500)
    ultima_tabla = tablas[-2]  # las tablas van intercaladas con Spacer(1,4)
    fila_horas, fila_desc = ultima_tabla._cellvalues
    assert len(fila_horas) == 10  # "Hs. semanales" + 9 columnas
    assert fila_horas[-1] == "Hasta 54hs"
    assert fila_desc[-1] == "25%"


def test_no_agrega_relleno_si_ya_es_multiplo_de_9(conn):
    _limpiar_esquema(conn)
    tramos = [(h - 2, h, 5) for h in range(2, 20, 2)]  # 9 tramos exactos
    _cargar_tramos(conn, tramos)

    tablas = bloques_esquema_descuentos(conn, ancho=500)
    fila_horas, _ = tablas[0]._cellvalues
    assert len(fila_horas) == 10
    assert fila_horas[-1] == "Hasta 18hs"


def test_relleno_respeta_el_paso_de_los_tramos_reales(conn):
    _limpiar_esquema(conn)
    tramos = [(0, 3, 10), (3, 6, 20)]  # paso de 3hs, 2 tramos
    _cargar_tramos(conn, tramos)

    tablas = bloques_esquema_descuentos(conn, ancho=500)
    fila_horas, fila_desc = tablas[0]._cellvalues
    assert fila_horas == ["Hs. semanales"] + [f"Hasta {h}hs" for h in (3, 6, 9, 12, 15, 18, 21, 24, 27)]
    assert fila_desc[1:] == ["10%", "20%"] + ["20%"] * 7


def test_fondo_azul_en_vez_de_bordo(conn):
    tablas = bloques_esquema_descuentos(conn, ancho=500)
    colores_fondo = {cmd[3] for cmd in tablas[0]._bkgrndcmds}
    assert colores_fondo == {COLOR_NIVEL_1}


def test_sin_tramos_muestra_mensaje(conn):
    _limpiar_esquema(conn)
    resultado = bloques_esquema_descuentos(conn, ancho=500)
    assert len(resultado) == 1
