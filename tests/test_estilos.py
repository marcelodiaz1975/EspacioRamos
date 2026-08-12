import pytest
from PIL import Image as ImagenPIL
from reportlab.platypus import Image, Paragraph

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.pdf.estilos import decimales_configurados, encabezado_espacio, formatear_moneda
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


def test_formatear_moneda_respeta_decimales():
    assert formatear_moneda(1234.5, decimales=2) == "$ 1.234,50"
    assert formatear_moneda(1234.7, decimales=0) == "$ 1.235"
    assert formatear_moneda(-1234.7, decimales=0) == "-$ 1.235"


def test_encabezado_espacio_sin_logo_usa_texto(conn):
    story = encabezado_espacio(conn, ancho=500)
    textos = [f for f in story if isinstance(f, Paragraph)]
    assert any("ESPACIO RAMOS" in p.getPlainText() for p in textos)


def test_encabezado_espacio_con_logo_usa_imagen(conn, tmp_path):
    ruta_logo = tmp_path / "logo.png"
    ImagenPIL.new("RGB", (900, 300), color="blue").save(ruta_logo)
    obtener_repositorio(conn, "Configuracion").actualizar(1, RutaLogo=str(ruta_logo))

    story = encabezado_espacio(conn, ancho=500)
    assert any(isinstance(f, Image) for f in story)


def test_encabezado_espacio_logo_ocupa_el_ancho_de_pagina(conn, tmp_path):
    """Un logo bien apaisado (relación de aspecto grande) debe quedar
    limitado por el ancho de la página, no por una fracción chica de él."""
    ruta_logo = tmp_path / "logo.png"
    ImagenPIL.new("RGB", (2000, 200), color="blue").save(ruta_logo)
    obtener_repositorio(conn, "Configuracion").actualizar(1, RutaLogo=str(ruta_logo))

    story = encabezado_espacio(conn, ancho=500)
    logo = next(f for f in story if isinstance(f, Image))
    assert logo.drawWidth == pytest.approx(500)


def test_encabezado_espacio_muestra_localidad_solo_si_se_pide(conn):
    sin_localidad = encabezado_espacio(conn, ancho=500, mostrar_localidad=False, localidad="Ramos Mejía")
    con_localidad = encabezado_espacio(conn, ancho=500, mostrar_localidad=True, localidad="Ramos Mejía")

    def _textos(story):
        return [p.getPlainText() for p in story if isinstance(p, Paragraph)]

    assert not any("Ramos Mejía" in t for t in _textos(sin_localidad))
    assert any("Ramos Mejía" in t for t in _textos(con_localidad))
