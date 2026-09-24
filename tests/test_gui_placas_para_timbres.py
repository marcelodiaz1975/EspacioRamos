import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.placas_para_timbres import PantallaPlacasParaTimbres


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
    pantalla = PantallaPlacasParaTimbres(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "PLACAS PARA TIMBRES"


def test_tiene_formato_solapa_con_las_tres_pestanas_en_orden(qtbot, conn):
    pantalla = PantallaPlacasParaTimbres(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == [
        "Búsqueda y asignación de placas", "Impresión de placas en papel", "Placas",
    ]


def test_las_dos_primeras_solapas_son_los_paneles_operativos_con_fondo_claro(qtbot, conn):
    pantalla = PantallaPlacasParaTimbres(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_operativas.panel_buscar.objectName() == "panelSolapa"
    assert pantalla.panel_operativas.panel_imprimir.objectName() == "panelSolapa"


def test_la_tercera_solapa_es_el_catalogo_placas_anidado_sin_titulo_propio(qtbot, conn):
    pantalla = PantallaPlacasParaTimbres(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_catalogo_placas
    assert panel.objectName() == "panelSolapa"
    assert panel.anidado is True
    assert panel.findChild(QLabel, "tituloPantalla") is None
    assert panel.campo_buscar is not None
