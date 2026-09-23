import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.grilla_operativa import _PanelGrillaSemanal
from app.gui.pantallas.grilla_y_mensajeria import PantallaGrillaYMensajeria
from app.gui.pantallas.mensajeria import _PanelCentroMensajeria
from app.gui.pantallas.mensajes_predefinidos import _PanelMensajesPredefinidos


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


def test_titulo_de_pantalla_es_jerarquia_1(qtbot, conn):
    pantalla = PantallaGrillaYMensajeria(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "GRILLA Y MENSAJERÍA"


def test_tiene_formato_solapa_con_las_tres_pestanas_en_orden(qtbot, conn):
    pantalla = PantallaGrillaYMensajeria(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == [
        "Grilla semanal", "Centro de mensajería", "Mensajes predefinidos",
    ]


def test_las_tres_solapas_son_los_paneles_esperados(qtbot, conn):
    pantalla = PantallaGrillaYMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla.panel_grilla, _PanelGrillaSemanal)
    assert isinstance(pantalla.panel_mensajeria, _PanelCentroMensajeria)
    assert isinstance(pantalla.panel_mensajes_predefinidos, _PanelMensajesPredefinidos)
    for panel in (pantalla.panel_grilla, pantalla.panel_mensajeria, pantalla.panel_mensajes_predefinidos):
        assert panel.objectName() == "panelSolapa"
