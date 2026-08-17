import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.archivos_varios import PantallaArchivosVarios
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


def test_archivos_varios_recibe_la_lista_completa_de_secciones(qtbot, conn):
    secciones = construir_secciones()
    indice_archivos_varios = next(i for i, s in enumerate(secciones) if s.nombre == "Archivos varios")

    pantalla = secciones[indice_archivos_varios].fabrica(conn)
    qtbot.addWidget(pantalla)

    assert isinstance(pantalla, PantallaArchivosVarios)
    assert len(pantalla._secciones) == len(secciones)
