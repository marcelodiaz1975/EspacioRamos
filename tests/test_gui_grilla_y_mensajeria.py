import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QScrollArea, QTabWidget, QWidget

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


def test_grilla_semanal_deja_fijas_columnas_y_encabezado(qtbot, conn):
    """Pedido explícito de la clienta, extendido desde Oferta de
    consultorios a toda pantalla con esta grilla compartida: Tipo de
    bloque/Horario y las filas de encabezado quedan siempre visibles al
    escrolear — el comportamiento del mecanismo en sí queda cubierto en
    `test_gui_grilla_operativa.py`."""
    pantalla = PantallaGrillaYMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_grilla.grilla._filas_columnas_fijas is True


def test_grilla_semanal_tiene_cadena_de_foco_sobre_los_filtros(qtbot, conn):
    """Punto 87 (SistemaDF v0.11.2026.10): Localidad → Edificio → Unidad
    → checks de día → Profesional, con wrap-around de vuelta a
    Localidad."""
    pantalla = PantallaGrillaYMensajeria(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_grilla
    assert panel._foco._orden == panel.grilla.widgets_filtro_para_foco()


def test_grilla_semanal_reiniciar_enfoca_el_primer_filtro(qtbot, conn):
    pantalla = PantallaGrillaYMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    panel = pantalla.panel_grilla

    primer_filtro = panel.grilla.widgets_filtro_para_foco()[0]
    primer_filtro.clearFocus()
    panel.reiniciar()

    qtbot.waitUntil(lambda: primer_filtro.hasFocus())


def test_grilla_semanal_queda_envuelta_en_un_scroll_area(qtbot, conn):
    """Punto 86: si la grilla necesita más alto del que entra en
    pantalla, tiene que poder escrolearse en vertical — toda la solapa
    pasa a estar dentro de un `QScrollArea` propio."""
    pantalla = PantallaGrillaYMensajeria(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_grilla
    assert panel.findChild(QScrollArea) is not None
    assert panel.objectName() == "panelSolapa"
    assert len(panel.findChildren(QWidget, "panelSolapa")) == 1  # "contenido", dentro del scroll
