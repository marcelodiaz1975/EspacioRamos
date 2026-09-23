import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.archivos_varios import _PanelArchivosVarios
from app.gui.pantallas.disponibilidad import PantallaDisponibilidad
from app.gui.pantallas.lista_espera import _PanelListaEspera
from app.gui.pantallas.oferta import _PanelOferta


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def test_titulo_de_pantalla_es_jerarquia_1(qtbot, conn):
    pantalla = PantallaDisponibilidad(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "DISPONIBILIDAD"


def test_tiene_formato_solapa_con_las_tres_pestanas_en_orden(qtbot, conn):
    pantalla = PantallaDisponibilidad(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == [
        "Oferta de consultorios", "Lista de espera", "Archivos para enviar",
    ]


def test_las_tres_solapas_son_los_paneles_esperados(qtbot, conn):
    pantalla = PantallaDisponibilidad(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla.panel_oferta, _PanelOferta)
    assert isinstance(pantalla.panel_lista_espera, _PanelListaEspera)
    assert isinstance(pantalla.panel_archivos_varios, _PanelArchivosVarios)
    assert pantalla.panel_oferta.objectName() == "panelSolapa"
    assert pantalla.panel_archivos_varios.objectName() == "panelSolapa"
