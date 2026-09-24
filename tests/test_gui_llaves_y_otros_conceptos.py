import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.llaves import _PanelLlaves
from app.gui.pantallas.llaves_y_otros_conceptos import PantallaLlavesYOtrosConceptos
from app.gui.pantallas.novedades import _PanelCargosEspeciales, _PanelEstadoCuentaCargos


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
    pantalla = PantallaLlavesYOtrosConceptos(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "LLAVES Y OTROS CONCEPTOS"


def test_tiene_formato_solapa_con_las_tres_pestanas_en_orden(qtbot, conn):
    pantalla = PantallaLlavesYOtrosConceptos(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == [
        "Movimientos y tenencias de llaves", "Registro de cargos especiales", "Estado de cuenta",
    ]


def test_las_tres_solapas_son_los_paneles_esperados_con_fondo_claro(qtbot, conn):
    pantalla = PantallaLlavesYOtrosConceptos(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla.panel_llaves, _PanelLlaves)
    assert isinstance(pantalla.panel_cargos_especiales, _PanelCargosEspeciales)
    assert isinstance(pantalla.panel_estado_cuenta, _PanelEstadoCuentaCargos)
    for panel in (pantalla.panel_llaves, pantalla.panel_cargos_especiales, pantalla.panel_estado_cuenta):
        assert panel.objectName() == "panelSolapa"
        assert panel.findChild(QLabel, "tituloPantalla") is None
