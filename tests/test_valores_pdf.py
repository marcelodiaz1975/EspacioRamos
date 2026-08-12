import json

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.pdf.estilos import COLOR_NIVEL_1
from app.pdf.valores_pdf import _hasta_por_frecuencia, bloques_esquema_descuentos, rango_actualizacion
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_hasta_por_frecuencia_bimestral_meses_pares():
    # actualización en agosto (un mes par); vigente hasta septiembre (mes
    # antes de la próxima actualización, octubre)
    assert _hasta_por_frecuencia("2026-08", [2, 4, 6, 8, 10, 12]) == "2026-09"


def test_hasta_por_frecuencia_envuelve_al_anio_siguiente():
    # actualización en julio (semestral enero/julio); vigente hasta
    # diciembre — la próxima actualización es en enero del año siguiente
    assert _hasta_por_frecuencia("2026-07", [1, 7]) == "2026-12"


def test_hasta_por_frecuencia_ultimo_mes_configurado():
    assert _hasta_por_frecuencia("2026-12", [2, 4, 6, 8, 10, 12]) == "2027-01"


def test_rango_actualizacion_usa_la_frecuencia_configurada(conn):
    desde, hasta = rango_actualizacion(conn, "2026-08")
    assert desde == "2026-08"
    assert hasta == "2026-09"  # default sembrado: bimestral, meses pares


def test_rango_actualizacion_sin_frecuencia_configurada_no_inventa_rango(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, MesesPeriodoActualizacion=None)
    desde, hasta = rango_actualizacion(conn, "2026-08")
    assert desde == hasta == "2026-08"


def test_rango_actualizacion_semestral_configurable(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, MesesPeriodoActualizacion=json.dumps([1, 7]),
    )
    conn.execute(
        "INSERT INTO AumentoAplicado (Periodo, PorcentajeGeneral, FechaAplicacion) VALUES ('2026-07', 5, '2026-07-01')"
    )
    conn.commit()
    desde, hasta = rango_actualizacion(conn, "2026-08")
    assert desde == "2026-07"
    assert hasta == "2026-12"


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
