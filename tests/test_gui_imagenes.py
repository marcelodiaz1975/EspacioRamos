import pytest
from PySide6.QtWidgets import QInputDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.imagenes import PantallaImagenes
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    connection.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path / "base"),))
    connection.commit()
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Vista general", True)))


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)


def _archivo_jpg(tmp_path, nombre="foto.jpg") -> str:
    ruta = tmp_path / nombre
    ruta.write_bytes(b"x" * 50)
    return str(ruta)


def test_lista_edificios_por_defecto(qtbot, conn):
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.combo_alcance.currentText() == "Edificio"


def test_cambiar_alcance_a_consultorio_carga_combo(qtbot, conn, consultorio):
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Consultorio")
    assert pantalla.combo_entidad.count() == 1
    assert "Consultorio 1" in pantalla.combo_entidad.currentText()


def test_agregar_imagen_via_dialogo(qtbot, conn, consultorio, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    ruta = _archivo_jpg(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (ruta, "")))

    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Consultorio")

    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 1).text() == "Vista general"


def test_agregar_sin_elegir_archivo_no_agrega_nada(qtbot, conn, consultorio, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Consultorio")

    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 0


def test_reordenar_subir_baja_intercambia_orden(qtbot, conn, consultorio, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    rutas = iter([_archivo_jpg(tmp_path, "a.jpg"), _archivo_jpg(tmp_path, "b.jpg")])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (next(rutas), "")))

    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Consultorio")
    pantalla._agregar()
    pantalla._agregar()

    pantalla.tabla.selectRow(1)
    pantalla._reordenar(-1)

    assert pantalla.tabla.item(0, 0).text() == "1"  # sigue habiendo un primer y segundo lugar
    assert pantalla.tabla.rowCount() == 2


def test_alternar_activo_actualiza_la_tabla(qtbot, conn, consultorio, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (_archivo_jpg(tmp_path), "")))
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Consultorio")
    pantalla._agregar()

    pantalla.tabla.selectRow(0)
    pantalla._alternar_activo()

    assert pantalla.tabla.item(0, 3).text() == "No"


def test_eliminar_imagen(qtbot, conn, consultorio, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (_archivo_jpg(tmp_path), "")))
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Consultorio")
    pantalla._agregar()

    pantalla.tabla.selectRow(0)
    pantalla._eliminar()

    assert pantalla.tabla.rowCount() == 0
    assert obtener_repositorio(conn, "Imagen").listar() == []
