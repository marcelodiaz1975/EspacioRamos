import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.oferta import PantallaOferta, _DialogoPrevisualizacion
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


@pytest.fixture(autouse=True)
def _confirmar_previsualizacion(monkeypatch):
    """La previsualización ahora se abre siempre antes de generar — para
    los tests que no la ejercitan específicamente, se confirma sola."""
    monkeypatch.setattr(_DialogoPrevisualizacion, "exec", lambda self: QDialog.DialogCode.Accepted)


@pytest.fixture
def profesional_y_consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1ro A")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lo Veci", NombrePila="Virginia", Tratamiento="Lic.",
    )
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (None,))
    conn.commit()
    return id_prof, id_edificio


def test_sin_dias_no_genera_ni_guarda_historial(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._generar_pdf()
    assert obtener_repositorio(conn, "HistorialOferta").listar() == []


def test_generar_texto_guarda_historial_y_muestra_dialogo(qtbot, conn, tmp_path, monkeypatch, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes

    capturado = {}

    def _dialogo_falso(texto, parent=None):
        capturado["texto"] = texto
        return _FalsoDialogo()

    monkeypatch.setattr("app.gui.pantallas.oferta._DialogoTexto", _dialogo_falso)

    pantalla._generar_texto()

    assert obtener_repositorio(conn, "HistorialOferta").listar() != []
    assert "Búsqueda requerida por el profesional" in capturado["texto"]
    assert pantalla.tabla_historial.rowCount() == 1


def test_generar_pdf_guarda_en_archivos_varios_oferta(qtbot, conn, tmp_path, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes

    pantalla._generar_pdf()

    generados = list((tmp_path / "Archivos varios" / "Oferta").iterdir())
    assert len(generados) == 1
    assert generados[0].name.startswith("Oferta de consultorios - Lic. Virginia Lo Veci")


def test_agregar_franja_la_suma_a_la_lista_y_limpia_dias(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes

    pantalla._agregar_franja()

    assert len(pantalla._franjas) == 1
    assert pantalla.lista_franjas.count() == 1
    assert pantalla._dias_seleccionados() == []  # se limpia para cargar la próxima franja


def test_agregar_franja_sin_dias_no_suma_nada(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._agregar_franja()
    assert pantalla._franjas == []
    assert pantalla.lista_franjas.count() == 0


def test_quitar_franja_seleccionada(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes
    pantalla._agregar_franja()
    pantalla.lista_franjas.setCurrentRow(0)

    pantalla._quitar_franja_seleccionada()

    assert pantalla._franjas == []
    assert pantalla.lista_franjas.count() == 0


def test_generar_con_dos_franjas_guarda_ambas_en_el_historial(qtbot, conn, tmp_path, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)

    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes
    pantalla._agregar_franja()
    pantalla.spin_desde.setValue(15)
    pantalla.spin_hasta.setValue(17)
    pantalla.lista_dias.item(4).setCheckState(Qt.CheckState.Checked)  # Viernes
    pantalla._agregar_franja()
    assert pantalla.lista_franjas.count() == 2

    pantalla._generar_pdf()

    fila = obtener_repositorio(conn, "HistorialOferta").listar()[0]
    criterios = json.loads(fila["CriteriosJSON"])
    assert len(criterios["busquedas"]) == 2
    assert criterios["busquedas"][0]["dias"] == ["Lunes"]
    assert criterios["busquedas"][1]["dias"] == ["Viernes"]
    # se limpia la lista de franjas para la próxima búsqueda
    assert pantalla._franjas == []
    assert pantalla.lista_franjas.count() == 0


def test_cancelar_previsualizacion_no_genera_ni_guarda_historial(qtbot, conn, monkeypatch, profesional_y_consultorio):
    monkeypatch.setattr(_DialogoPrevisualizacion, "exec", lambda self: QDialog.DialogCode.Rejected)
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes

    pantalla._generar_pdf()

    assert obtener_repositorio(conn, "HistorialOferta").listar() == []


def test_previsualizacion_muestra_una_fila_por_opcion(qtbot, conn, monkeypatch, profesional_y_consultorio):
    capturado = {}

    def _exec_capturando(self):
        capturado["filas"] = list(self._filas)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoPrevisualizacion, "exec", _exec_capturando)
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes

    pantalla._generar_pdf()

    assert len(capturado["filas"]) == 1
    assert "consultorio 1" in capturado["filas"][0][3]


def test_destildar_una_opcion_en_la_previsualizacion_la_excluye_del_historial(
    qtbot, conn, tmp_path, monkeypatch, profesional_y_consultorio,
):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()

    def _exec_destildando_todo(self):
        if self.lista is not None:
            for i in range(self.lista.count()):
                self.lista.item(i).setCheckState(Qt.CheckState.Unchecked)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoPrevisualizacion, "exec", _exec_destildando_todo)
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes

    pantalla._generar_pdf()

    fila = obtener_repositorio(conn, "HistorialOferta").listar()[0]
    criterios = json.loads(fila["CriteriosJSON"])
    assert criterios["excluir"] == [[0, 0, 0]]


def test_sin_alternativas_la_previsualizacion_permite_generar_igual(qtbot, conn, tmp_path, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes
    pantalla.casilla_camilla.setChecked(True)  # el consultorio de la fixture no es apto camilla: sin cobertura

    pantalla._generar_pdf()

    assert obtener_repositorio(conn, "HistorialOferta").listar() != []


def test_paquete_y_con_franja_sin_cobertura_no_muestra_nada_en_la_previsualizacion(
    qtbot, conn, monkeypatch, profesional_y_consultorio,
):
    capturado = {}

    def _exec_capturando(self):
        capturado["filas"] = list(self._filas)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoPrevisualizacion, "exec", _exec_capturando)
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes: con cobertura
    pantalla.combo_union_franja.setCurrentIndex(1)  # Y con la próxima
    pantalla._agregar_franja()

    pantalla.lista_dias.item(1).setCheckState(Qt.CheckState.Checked)  # Martes
    pantalla.casilla_camilla.setChecked(True)  # el consultorio de la fixture no es apto camilla: sin cobertura
    pantalla._agregar_franja()

    pantalla._generar_pdf()

    assert capturado["filas"] == []


class _FalsoDialogo:
    def exec(self):
        return None
