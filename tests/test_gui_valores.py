import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.aumentos import _PanelAumentos, _PanelEsquemaDescuentos
from app.gui.pantallas.grilla_operativa import _PanelValoresVigentes
from app.gui.pantallas.valores import PantallaValores


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
    pantalla = PantallaValores(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "VALORES"


def test_tiene_formato_solapa_con_las_tres_pestanas_en_orden(qtbot, conn):
    pantalla = PantallaValores(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == [
        "Valores vigentes", "Aumentos", "Esquema de descuentos",
    ]


def test_las_tres_solapas_son_los_paneles_esperados(qtbot, conn):
    pantalla = PantallaValores(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla.panel_valores_vigentes, _PanelValoresVigentes)
    assert isinstance(pantalla.panel_aumentos, _PanelAumentos)
    assert isinstance(pantalla.panel_esquema, _PanelEsquemaDescuentos)
    for panel in (pantalla.panel_valores_vigentes, pantalla.panel_aumentos, pantalla.panel_esquema):
        assert panel.objectName() == "panelSolapa"
