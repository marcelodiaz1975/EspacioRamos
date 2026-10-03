import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.main_window import Seccion
from app.gui.pantallas.textos_sistema import _PanelTextosDelSistema
from app.negocio.plantillas_texto import MENSAJES_EDITABLES, guardar_texto_personalizado
from app.repositorio.registro import obtener_repositorio


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


_SECCIONES = [
    Seccion("Panel de control", lambda c: None, categoria="Sistema", ayuda="Ayuda del panel de control."),
    Seccion("Reservas", lambda c: None, categoria="Operativa diaria", ayuda=""),
]


def test_es_un_panel_solapa(qtbot, conn):
    pantalla = _PanelTextosDelSistema(conn, _SECCIONES)
    qtbot.addWidget(pantalla)
    assert pantalla.objectName() == "panelSolapa"


def test_lista_incluye_los_7_mensajes_y_las_secciones(qtbot, conn):
    pantalla = _PanelTextosDelSistema(conn, _SECCIONES)
    qtbot.addWidget(pantalla)
    textos = [pantalla.lista.item(i).text() for i in range(pantalla.lista.count())]
    for mensaje in MENSAJES_EDITABLES:
        assert mensaje.nombre in textos
    assert "Panel de control" in textos
    assert "Reservas" in textos


def test_separadores_no_son_seleccionables(qtbot, conn):
    pantalla = _PanelTextosDelSistema(conn, _SECCIONES)
    qtbot.addWidget(pantalla)
    separador = pantalla.lista.item(0)
    assert "MENSAJES AUTOMÁTICOS" in separador.text()
    assert not (separador.flags() & Qt.ItemFlag.ItemIsSelectable)


def test_sin_seleccion_el_editor_queda_deshabilitado(qtbot, conn):
    pantalla = _PanelTextosDelSistema(conn, _SECCIONES)
    qtbot.addWidget(pantalla)
    assert not pantalla.editor.isEnabled()
    assert not pantalla.boton_guardar.isEnabled()
    assert not pantalla.boton_restablecer.isEnabled()


def _seleccionar_por_nombre(pantalla, nombre):
    for i in range(pantalla.lista.count()):
        item = pantalla.lista.item(i)
        if item.text() == nombre or item.text().startswith(f"{nombre} ("):
            pantalla.lista.setCurrentItem(item)
            return item
    raise AssertionError(f"no se encontró el ítem {nombre!r}")


def test_seleccionar_un_mensaje_carga_el_default_y_las_variables(qtbot, conn):
    pantalla = _PanelTextosDelSistema(conn, _SECCIONES)
    qtbot.addWidget(pantalla)
    _seleccionar_por_nombre(pantalla, "Mensaje que acompaña el PDF de liquidación")
    assert pantalla.editor.toPlainText() == MENSAJES_EDITABLES[4].default
    assert "{mes}" in pantalla.etiqueta_variables.text()
    assert pantalla.editor.isEnabled()
    assert pantalla.boton_guardar.isEnabled()
    assert not pantalla.boton_restablecer.isEnabled()


def test_seleccionar_ayuda_sin_variables(qtbot, conn):
    pantalla = _PanelTextosDelSistema(conn, _SECCIONES)
    qtbot.addWidget(pantalla)
    _seleccionar_por_nombre(pantalla, "Panel de control")
    assert pantalla.editor.toPlainText() == "Ayuda del panel de control."
    assert "no tiene variables" in pantalla.etiqueta_variables.text()


def test_guardar_persiste_el_override_y_marca_el_item(qtbot, conn):
    pantalla = _PanelTextosDelSistema(conn, _SECCIONES)
    qtbot.addWidget(pantalla)
    item = _seleccionar_por_nombre(pantalla, "Mensaje que acompaña el PDF de liquidación")
    pantalla.editor.setPlainText("Texto nuevo con {mes}.")
    pantalla.boton_guardar.click()

    filas = obtener_repositorio(conn, "PlantillaTexto").listar(Clave="mensaje_envio_liquidacion")
    assert filas[0]["TextoPersonalizado"] == "Texto nuevo con {mes}."
    assert "(personalizado)" in item.text()
    assert pantalla.boton_restablecer.isEnabled()


def test_guardar_con_variable_desconocida_pide_confirmacion(qtbot, conn, monkeypatch):
    preguntas = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: preguntas.append(a) or QMessageBox.StandardButton.No),
    )
    pantalla = _PanelTextosDelSistema(conn, _SECCIONES)
    qtbot.addWidget(pantalla)
    _seleccionar_por_nombre(pantalla, "Mensaje que acompaña el PDF de liquidación")
    pantalla.editor.setPlainText("Texto con {variable_inventada}.")
    pantalla.boton_guardar.click()

    assert len(preguntas) == 1
    assert obtener_repositorio(conn, "PlantillaTexto").listar(Clave="mensaje_envio_liquidacion") == []


def test_restablecer_borra_el_override_y_vuelve_al_default(qtbot, conn, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    guardar_texto_personalizado(conn, "mensaje_envio_liquidacion", "Personalizado")
    pantalla = _PanelTextosDelSistema(conn, _SECCIONES)
    qtbot.addWidget(pantalla)
    item = _seleccionar_por_nombre(pantalla, "Mensaje que acompaña el PDF de liquidación")
    assert pantalla.editor.toPlainText() == "Personalizado"

    pantalla.boton_restablecer.click()

    assert pantalla.editor.toPlainText() == MENSAJES_EDITABLES[4].default
    assert "(personalizado)" not in item.text()
    assert not pantalla.boton_restablecer.isEnabled()
    assert obtener_repositorio(conn, "PlantillaTexto").listar(Clave="mensaje_envio_liquidacion") == []
