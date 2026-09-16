import pytest
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.imagenes import PantallaImagenes, _DialogoAgregarImagen
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
    # Por defecto acepta el diálogo de "Agregar imagen" con la primera
    # categoría de la lista y sin marcar principal — los tests que
    # necesiten otra cosa lo pisan explícitamente.
    monkeypatch.setattr(_DialogoAgregarImagen, "exec", lambda self: QDialog.DialogCode.Accepted)


@pytest.fixture
def localidad(conn):
    return obtener_repositorio(conn, "Localidad").crear(Localidad="Rosario")


@pytest.fixture
def edificio(conn, localidad):
    return obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", IdLocalidad=localidad)


@pytest.fixture
def unidad(conn, edificio):
    return obtener_repositorio(conn, "Unidad").crear(IdEdificio=edificio, Departamento='7mo "L"')


@pytest.fixture
def consultorio(conn, unidad):
    return obtener_repositorio(conn, "Consultorio").crear(IdUnidad=unidad, NumeroConsultorio=1)


def _archivo_jpg(tmp_path, nombre="foto.jpg") -> str:
    ruta = tmp_path / nombre
    ruta.write_bytes(b"x" * 50)
    return str(ruta)


def _elegir_consultorio(pantalla, edificio, unidad, consultorio) -> None:
    pantalla.combo_alcance.setCurrentText("Consultorio")
    pantalla.combo_localidad.setCurrentText("Rosario")
    pantalla.combo_edificio.setCurrentIndex(pantalla.combo_edificio.findData(edificio))
    pantalla.combo_unidad.setCurrentIndex(pantalla.combo_unidad.findData(unidad))
    pantalla.combo_consultorio.setCurrentIndex(pantalla.combo_consultorio.findData(consultorio))


def test_alcance_por_defecto_es_todos_los_archivos(qtbot, conn):
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.combo_alcance.currentText() == "Todos los archivos"
    assert not pantalla.combo_localidad.isEnabled()
    assert not pantalla.boton_agregar.isEnabled()
    assert not pantalla.boton_subir.isEnabled()
    assert not pantalla.boton_principal.isEnabled()


def test_alcance_espacio_deshabilita_los_cuatro_filtros(qtbot, conn):
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Espacio")
    assert pantalla.boton_agregar.isEnabled()
    assert not pantalla.combo_localidad.isEnabled()
    assert not pantalla.combo_edificio.isEnabled()
    assert not pantalla.combo_unidad.isEnabled()
    assert not pantalla.combo_consultorio.isEnabled()


def test_alcance_unidad_habilita_localidad_edificio_y_unidad_pero_no_consultorio(qtbot, conn, edificio, unidad):
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Unidad")
    assert pantalla.combo_localidad.isEnabled()
    assert pantalla.combo_edificio.isEnabled()
    assert pantalla.combo_unidad.isEnabled()
    assert not pantalla.combo_consultorio.isEnabled()


def test_alcance_consultorio_habilita_los_cuatro_filtros(qtbot, conn, edificio, unidad, consultorio):
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Consultorio")
    assert pantalla.combo_localidad.isEnabled()
    assert pantalla.combo_edificio.isEnabled()
    assert pantalla.combo_unidad.isEnabled()
    assert pantalla.combo_consultorio.isEnabled()


def test_combo_edificio_se_acota_por_localidad_elegida(qtbot, conn, edificio, unidad, consultorio):
    id_otra_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Buenos Aires")
    obtener_repositorio(conn, "Edificio").crear(Nombre="Otro edificio", IdLocalidad=id_otra_localidad)
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Edificio")
    pantalla.combo_localidad.setCurrentText("Rosario")
    nombres = [pantalla.combo_edificio.itemText(i) for i in range(pantalla.combo_edificio.count())]
    assert nombres == ["Ramos 1"]


def test_agregar_imagen_via_dialogo(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    ruta = _archivo_jpg(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (ruta, "")))

    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)

    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 1
    # Descripción, categoría y "principal" se arman solos
    assert pantalla.tabla.item(0, 1).text() == "Consultorio - Foto general - 1"
    assert pantalla.tabla.item(0, 2).text() == "Foto general"
    assert pantalla.tabla.item(0, 3).text() == "Sí"


def test_agregar_imagen_elige_categoria_del_dialogo(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    ruta = _archivo_jpg(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (ruta, "")))

    def _elegir_ventana(self):
        self.combo_categoria.setCurrentText("Ventana")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoAgregarImagen, "exec", _elegir_ventana)

    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()

    assert pantalla.tabla.item(0, 2).text() == "Ventana"


def test_agregar_imagen_de_espacio_no_pide_ningun_filtro(qtbot, conn, tmp_path, monkeypatch):
    ruta = _archivo_jpg(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (ruta, "")))

    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Espacio")

    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 1


def test_agregar_sin_elegir_archivo_no_agrega_nada(qtbot, conn, edificio, unidad, consultorio, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)

    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 0


def test_marcar_como_principal_promueve_la_seleccionada(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    rutas = iter([_archivo_jpg(tmp_path, "a.jpg"), _archivo_jpg(tmp_path, "b.jpg")])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (next(rutas), "")))

    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()
    pantalla._agregar()

    pantalla.tabla.selectRow(1)
    pantalla._marcar_principal()

    # Al promover la segunda, el orden se reordena: ahora ella es la fila 0
    assert pantalla.tabla.item(0, 1).text() == "Consultorio - Foto general - 1"
    assert pantalla.tabla.item(0, 3).text() == "Sí"
    assert pantalla.tabla.item(1, 3).text() == "No"


def test_reordenar_subir_baja_intercambia_orden(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    rutas = iter([_archivo_jpg(tmp_path, "a.jpg"), _archivo_jpg(tmp_path, "b.jpg")])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (next(rutas), "")))

    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()
    pantalla._agregar()

    pantalla.tabla.selectRow(1)
    pantalla._reordenar(-1)

    assert pantalla.tabla.item(0, 0).text() == "1"  # sigue habiendo un primer y segundo lugar
    assert pantalla.tabla.rowCount() == 2


def test_alternar_activo_actualiza_la_tabla(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (_archivo_jpg(tmp_path), "")))
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()

    pantalla.tabla.selectRow(0)
    pantalla._alternar_activo()

    assert pantalla.tabla.item(0, 4).text() == "No"


def test_eliminar_imagen(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (_archivo_jpg(tmp_path), "")))
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()

    pantalla.tabla.selectRow(0)
    pantalla._eliminar()

    assert pantalla.tabla.rowCount() == 0
    assert obtener_repositorio(conn, "Imagen").listar() == []


def test_descargar_copia_el_archivo_al_destino_elegido(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (_archivo_jpg(tmp_path), "")))
    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()
    pantalla.tabla.selectRow(0)

    destino = tmp_path / "descargas" / "copia.jpg"
    destino.parent.mkdir()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))

    pantalla._descargar()

    assert destino.is_file()


def test_todos_los_archivos_muestra_imagenes_de_todos_los_niveles(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    rutas = iter([_archivo_jpg(tmp_path, "a.jpg"), _archivo_jpg(tmp_path, "b.jpg")])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (next(rutas), "")))

    pantalla = PantallaImagenes(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Espacio")
    pantalla._agregar()
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()

    pantalla.combo_alcance.setCurrentText("Todos los archivos")

    assert pantalla.tabla.rowCount() == 2
    assert pantalla.tabla.item(0, 0).text() == "Espacio"
    assert pantalla.tabla.item(1, 0).text() == "Consultorio"
    assert pantalla.tabla.item(1, 2).text() == "Ramos 1"
