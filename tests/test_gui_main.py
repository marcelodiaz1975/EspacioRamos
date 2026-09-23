import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.archivos_y_listas import PantallaArchivosYListas
from gui_main import construir_secciones


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_todas_las_secciones_tienen_ayuda_cargada():
    secciones = construir_secciones()
    sin_ayuda = [s.nombre for s in secciones if not s.ayuda.strip()]
    assert sin_ayuda == []


def test_archivos_y_listas_recibe_la_lista_completa_de_secciones(qtbot, conn):
    """"Manual del usuario" (reubicado en Gestor de archivos del espacio,
    ver imagenes.py) sigue necesitando la lista completa de secciones
    para armar la ayuda contextual del manual."""
    secciones = construir_secciones()
    indice_archivos_y_listas = next(i for i, s in enumerate(secciones) if s.nombre == "Archivos y listas")

    pantalla = secciones[indice_archivos_y_listas].fabrica(conn)
    qtbot.addWidget(pantalla)

    assert isinstance(pantalla, PantallaArchivosYListas)
    assert len(pantalla.panel_gestor_archivos._secciones) == len(secciones)
