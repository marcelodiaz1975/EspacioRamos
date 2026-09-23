import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.base_datos_espacio import PantallaBaseDatosEspacio


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
    pantalla = PantallaBaseDatosEspacio(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "BASE DATOS DEL ESPACIO"


def test_tiene_formato_solapa_con_las_cinco_pestanas_en_orden(qtbot, conn):
    """El orden sigue la cadena de referencias real entre las tablas
    (Localidad → Edificio → Unidad → Consultorio), más Responsables al
    final — mismo orden del Excel de la clienta."""
    pantalla = PantallaBaseDatosEspacio(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == [
        "Localidades", "Edificios", "Unidades", "Consultorios", "Responsables",
    ]


def test_las_cinco_solapas_son_pantallascrud_anidadas_con_datos(qtbot, conn):
    pantalla = PantallaBaseDatosEspacio(conn)
    qtbot.addWidget(pantalla)
    for panel in (
        pantalla.panel_localidades, pantalla.panel_edificios, pantalla.panel_unidades,
        pantalla.panel_consultorios, pantalla.panel_responsables,
    ):
        assert panel.objectName() == "panelSolapa"
        assert panel.anidado is True
        assert panel.findChild(QLabel, "tituloPantalla") is None
        assert panel.campo_buscar is not None


def test_edificios_lista_los_edificios_ya_cargados(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    conn.commit()
    pantalla = PantallaBaseDatosEspacio(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_edificios.tabla_widget.rowCount() == 1
