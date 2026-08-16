import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.bloques_rigidos import PantallaBloquesRigidos, _DialogoBloque
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
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def test_lista_los_dos_bloques_sembrados(qtbot, conn):
    pantalla = PantallaBloquesRigidos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.rowCount() == 2


def test_resumen_de_dias_todos_los_dias(qtbot, conn):
    pantalla = PantallaBloquesRigidos(conn)
    qtbot.addWidget(pantalla)
    fila_9_11 = next(
        i for i in range(pantalla.tabla.rowCount()) if pantalla.tabla.item(i, 0).text().startswith("9 a 11")
    )
    assert pantalla.tabla.item(fila_9_11, 1).text() == "Lunes, Martes, Miércoles, Jueves, Viernes, Sábado"


def test_nuevo_bloque_se_agrega(qtbot, conn, monkeypatch):
    pantalla = PantallaBloquesRigidos(conn)
    qtbot.addWidget(pantalla)

    def _dialogo_aceptado(self, *a, **k):
        self.spin_desde.setValue(13)
        self.spin_hasta.setValue(14)
        self.lista_logica.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes
        self.lista_visualizacion.item(0).setCheckState(Qt.CheckState.Checked)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoBloque, "exec", _dialogo_aceptado)
    pantalla._nuevo()

    assert pantalla.tabla.rowCount() == 3
    nuevo = obtener_repositorio(conn, "BloqueRigido").listar(HoraInicio=13)
    assert len(nuevo) == 1
    assert json.loads(nuevo[0]["DiasLogica"]) == ["Lunes"]


def test_dialogo_rechaza_hora_fin_anterior_a_inicio(qtbot, conn):
    dialogo = _DialogoBloque(parent=None)
    dialogo.spin_desde.setValue(15)
    dialogo.spin_hasta.setValue(10)
    dialogo.lista_logica.item(0).setCheckState(Qt.CheckState.Checked)
    dialogo.lista_visualizacion.item(0).setCheckState(Qt.CheckState.Checked)
    dialogo._validar_y_aceptar()
    assert dialogo.result() == 0  # no se aceptó


def test_dialogo_rechaza_sin_dias_de_logica(qtbot, conn):
    dialogo = _DialogoBloque(parent=None)
    dialogo._validar_y_aceptar()
    assert dialogo.result() == 0


def test_editar_bloque_existente_precarga_valores(qtbot, conn):
    id_bloque = obtener_repositorio(conn, "BloqueRigido").listar(HoraInicio=9)[0]["IdBloqueRigido"]
    bloque = obtener_repositorio(conn, "BloqueRigido").obtener(id_bloque)
    dialogo = _DialogoBloque(bloque, parent=None)
    assert dialogo.spin_desde.value() == 9
    assert dialogo.spin_hasta.value() == 11
    assert "Lunes" in dialogo.lista_logica.seleccionados()


def test_editar_bloque_guarda_cambios(qtbot, conn, monkeypatch):
    pantalla = PantallaBloquesRigidos(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)

    def _dialogo_desactiva(self, *a, **k):
        self.casilla_activo.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoBloque, "exec", _dialogo_desactiva)
    pantalla._editar()

    assert pantalla.tabla.item(0, 3).text() == "No"


def test_eliminar_bloque(qtbot, conn):
    pantalla = PantallaBloquesRigidos(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)

    pantalla._eliminar()

    assert pantalla.tabla.rowCount() == 1
