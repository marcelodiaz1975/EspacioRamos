import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.archivos_y_listas import PantallaArchivosYListas
from app.gui.pantallas.imagenes import _PanelGestorArchivos


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    connection.execute(
        "UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path / "base"),)
    )
    connection.commit()
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


def test_titulo_de_pantalla_es_jerarquia_1(qtbot, conn):
    pantalla = PantallaArchivosYListas(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "ARCHIVOS Y LISTAS"


def test_tiene_formato_solapa_con_las_cuatro_pestanas(qtbot, conn):
    pantalla = PantallaArchivosYListas(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == [
        "Gestor de archivos del espacio",
        "Listas editables",
        "Condiciones y normas",
        "Detalles complementarios de la propuesta",
    ]


def test_solapa_gestor_de_archivos_es_un_panel_funcional(qtbot, conn):
    pantalla = PantallaArchivosYListas(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla.panel_gestor_archivos, _PanelGestorArchivos)
    assert pantalla.panel_gestor_archivos.objectName() == "panelSolapa"
    assert pantalla.panel_gestor_archivos.combo_alcance.currentText() == "Todos los archivos"


def test_las_tres_solapas_de_catalogo_son_pantallascrud_anidadas(qtbot, conn):
    pantalla = PantallaArchivosYListas(conn)
    qtbot.addWidget(pantalla)
    for panel in (
        pantalla.panel_listas_editables, pantalla.panel_condiciones_normas, pantalla.panel_detalles_complementarios,
    ):
        assert panel.objectName() == "panelSolapa"
        assert panel.anidado is True
        assert panel.findChild(QLabel, "tituloPantalla") is None
        assert panel.campo_buscar is not None


def test_listas_editables_carga_los_valores_sembrados(qtbot, conn):
    pantalla = PantallaArchivosYListas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_listas_editables.tabla_widget.rowCount() > 0
