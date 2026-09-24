import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.profesionales import PantallaProfesionales, _PanelProfesionales


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
    pantalla = PantallaProfesionales(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "PROFESIONALES"


def test_tiene_formato_solapa_con_las_dos_pestanas_en_orden(qtbot, conn):
    pantalla = PantallaProfesionales(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == [
        "Listado de profesionales", "Profesiones y tratamientos",
    ]


def test_las_dos_solapas_son_los_paneles_esperados(qtbot, conn):
    pantalla = PantallaProfesionales(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla.panel_profesionales, _PanelProfesionales)
    assert pantalla.panel_profesionales.objectName() == "panelSolapa"
    assert pantalla.panel_profesiones.objectName() == "panelSolapa"
    assert pantalla.panel_profesiones.anidado is True
    assert pantalla.panel_profesiones.findChild(QLabel, "tituloPantalla") is None
