import pytest
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.main_window import Seccion
from app.gui.pantallas.imagenes import _PanelGestorArchivos, _DialogoAgregarArchivo
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
    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", lambda self: QDialog.DialogCode.Accepted)


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


def _archivo_txt(tmp_path, nombre="doc.txt", contenido="Contenido de prueba") -> str:
    ruta = tmp_path / nombre
    ruta.write_text(contenido)
    return str(ruta)


def _elegir_consultorio(pantalla, edificio, unidad, consultorio) -> None:
    pantalla.combo_alcance.setCurrentText("Consultorio")
    pantalla.combo_localidad.setCurrentText("Rosario")
    pantalla.combo_edificio.setCurrentIndex(pantalla.combo_edificio.findData(edificio))
    pantalla.combo_unidad.setCurrentIndex(pantalla.combo_unidad.findData(unidad))
    pantalla.combo_consultorio.setCurrentIndex(pantalla.combo_consultorio.findData(consultorio))


def test_es_un_panel_solapa(qtbot, conn):
    """Reordenamiento de formularios: dejó de ser una pantalla propia con
    su propio título/QTabWidget — ahora es la solapa "Gestor de archivos
    del espacio" de "Archivos y listas" (ver catalogos.py)."""
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.objectName() == "panelSolapa"


def test_boton_manual_del_usuario_es_primario_y_va_despues_de_eliminar(qtbot, conn):
    """Reordenamiento de formularios: el botón "Manual del usuario" se
    reubicó acá desde la vieja pantalla "Archivos varios" (ahora
    "Archivos para enviar" de "Disponibilidad") — pedido explícito de la
    clienta: después de "Eliminar", con una línea divisoria propia
    arriba, como botonPrimario."""
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_manual.text() == "Manual del usuario"
    assert pantalla.boton_manual.objectName() == "botonPrimario"

    panel_izquierda = pantalla.boton_eliminar.parentWidget()
    form = panel_izquierda.layout()
    widgets = [form.itemAt(i).widget() for i in range(form.count()) if form.itemAt(i).widget() is not None]
    assert widgets.index(pantalla.boton_manual) > widgets.index(pantalla.boton_eliminar)


def test_regenerar_manual_sin_secciones_avisa_y_no_falla(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)

    pantalla._regenerar_manual()  # no debe lanzar, solo avisar

    carpeta = tmp_path / "Archivos varios" / "Manual"
    assert not carpeta.exists() or list(carpeta.iterdir()) == []


def test_regenerar_manual_genera_archivo(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    secciones = [Seccion("Alguna pantalla", lambda c: None, categoria="Principal", ayuda="Texto de ayuda.")]
    pantalla = _PanelGestorArchivos(conn, secciones)
    qtbot.addWidget(pantalla)

    pantalla._regenerar_manual()

    generados = list((tmp_path / "Archivos varios" / "Manual").iterdir())
    assert len(generados) == 1
    assert generados[0].name == "Manual de usuario.pdf"


def test_alcance_por_defecto_es_todos_los_archivos(qtbot, conn):
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.combo_alcance.currentText() == "Todos los archivos"
    assert not pantalla.combo_localidad.isEnabled()
    assert not pantalla.boton_agregar.isEnabled()
    assert not pantalla.boton_subir.isEnabled()
    assert not pantalla.boton_principal.isEnabled()


def test_alcance_espacio_deshabilita_los_cuatro_filtros(qtbot, conn):
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Espacio")
    assert pantalla.boton_agregar.isEnabled()
    assert not pantalla.combo_localidad.isEnabled()
    assert not pantalla.combo_edificio.isEnabled()
    assert not pantalla.combo_unidad.isEnabled()
    assert not pantalla.combo_consultorio.isEnabled()


def test_alcance_unidad_habilita_localidad_edificio_y_unidad_pero_no_consultorio(qtbot, conn, edificio, unidad):
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Unidad")
    assert pantalla.combo_localidad.isEnabled()
    assert pantalla.combo_edificio.isEnabled()
    assert pantalla.combo_unidad.isEnabled()
    assert not pantalla.combo_consultorio.isEnabled()


def test_alcance_consultorio_habilita_los_cuatro_filtros(qtbot, conn, edificio, unidad, consultorio):
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Consultorio")
    assert pantalla.combo_localidad.isEnabled()
    assert pantalla.combo_edificio.isEnabled()
    assert pantalla.combo_unidad.isEnabled()
    assert pantalla.combo_consultorio.isEnabled()


def test_combo_edificio_se_acota_por_localidad_elegida(qtbot, conn, edificio, unidad, consultorio):
    id_otra_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Buenos Aires")
    obtener_repositorio(conn, "Edificio").crear(Nombre="Otro edificio", IdLocalidad=id_otra_localidad)
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Edificio")
    pantalla.combo_localidad.setCurrentText("Rosario")
    nombres = [pantalla.combo_edificio.itemText(i) for i in range(pantalla.combo_edificio.count())]
    assert nombres == ["Ramos 1"]


def test_agregar_imagen_via_dialogo(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    ruta = _archivo_jpg(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (ruta, "")))

    pantalla = _PanelGestorArchivos(conn)
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

    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", _elegir_ventana)

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()

    assert pantalla.tabla.item(0, 2).text() == "Ventana"


def test_agregar_imagen_de_espacio_no_pide_ningun_filtro(qtbot, conn, tmp_path, monkeypatch):
    ruta = _archivo_jpg(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (ruta, "")))

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Espacio")

    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 1


def test_agregar_sin_elegir_archivo_no_agrega_nada(qtbot, conn, edificio, unidad, consultorio, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)

    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 0


def test_marcar_como_principal_promueve_la_seleccionada(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    rutas = iter([_archivo_jpg(tmp_path, "a.jpg"), _archivo_jpg(tmp_path, "b.jpg")])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (next(rutas), "")))

    pantalla = _PanelGestorArchivos(conn)
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

    pantalla = _PanelGestorArchivos(conn)
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
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()

    pantalla.tabla.selectRow(0)
    pantalla._alternar_activo()

    assert pantalla.tabla.item(0, 4).text() == "No"


def test_eliminar_imagen(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (_archivo_jpg(tmp_path), "")))
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()

    pantalla.tabla.selectRow(0)
    pantalla._eliminar()

    assert pantalla.tabla.rowCount() == 0
    assert obtener_repositorio(conn, "Imagen").listar() == []


def test_descargar_copia_el_archivo_al_destino_elegido(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (_archivo_jpg(tmp_path), "")))
    pantalla = _PanelGestorArchivos(conn)
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

    pantalla = _PanelGestorArchivos(conn)
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


def test_tipo_documento_muestra_categorias_de_documento(qtbot, conn, edificio, unidad, consultorio):
    from app.negocio.imagenes import categorias_por_alcance

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla.combo_tipo.setCurrentText("Documento")

    dialogo = _DialogoAgregarArchivo(categorias_por_alcance("Consultorio", "Documento"))
    opciones = [dialogo.combo_categoria.itemText(i) for i in range(dialogo.combo_categoria.count())]
    assert opciones == ["Otros documentos"]


def test_agregar_documento_pdf_via_dialogo(qtbot, conn, edificio, unidad, tmp_path, monkeypatch):
    ruta = tmp_path / "manual.pdf"
    ruta.write_bytes(b"%PDF-1.4 contenido de prueba")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(ruta), "")))

    def _elegir_manual(self):
        self.combo_categoria.setCurrentText("Manual del usuario")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", _elegir_manual)

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Espacio")
    pantalla.combo_tipo.setCurrentText("Documento")
    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 1).text() == "Espacio - Manual del usuario - 1"


def test_tipo_filtra_la_tabla_por_imagen_o_documento(qtbot, conn, tmp_path, monkeypatch):
    rutas = iter([_archivo_jpg(tmp_path), str(tmp_path / "manual.pdf")])
    (tmp_path / "manual.pdf").write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (next(rutas), "")))

    def _elegir_manual(self):
        self.combo_categoria.setCurrentText("Manual del usuario")
        return QDialog.DialogCode.Accepted

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Espacio")
    pantalla._agregar()  # Imagen (tipo por defecto), categoría por defecto

    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", _elegir_manual)
    pantalla.combo_tipo.setCurrentText("Documento")
    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 2).text() == "Manual del usuario"

    pantalla.combo_tipo.setCurrentText("Imagen")
    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 2).text() == "Logo PDF"


def test_agregar_otros_documentos_sin_detalle_no_agrega(qtbot, conn, monkeypatch, tmp_path):
    ruta = tmp_path / "cualquiera.pdf"
    ruta.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(ruta), "")))

    def _elegir_otros_sin_detalle(self):
        self.combo_categoria.setCurrentText("Otros documentos")
        self.campo_detalle.setText("")
        self._validar_y_aceptar()
        return self.result()

    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", _elegir_otros_sin_detalle)

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Espacio")
    pantalla.combo_tipo.setCurrentText("Documento")
    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 0


def test_agregar_otros_documentos_con_detalle_arma_la_descripcion(qtbot, conn, monkeypatch, tmp_path):
    ruta = tmp_path / "cualquiera.pdf"
    ruta.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(ruta), "")))

    def _elegir_otros_con_detalle(self):
        self.combo_categoria.setCurrentText("Otros documentos")
        self.campo_detalle.setText("Presupuesto de obra")
        self._validar_y_aceptar()
        return self.result()

    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", _elegir_otros_con_detalle)

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Espacio")
    pantalla.combo_tipo.setCurrentText("Documento")
    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 1).text() == "Espacio - Otros documentos - Presupuesto de obra - 1"


def test_previsualizacion_txt_muestra_el_contenido(qtbot, conn, monkeypatch, tmp_path):
    ruta = _archivo_txt(tmp_path, contenido="Primera línea de prueba")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (ruta, "")))

    def _elegir_manual(self):
        self.combo_categoria.setCurrentText("Manual del usuario")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", _elegir_manual)

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Espacio")
    pantalla.combo_tipo.setCurrentText("Documento")
    pantalla._agregar()
    pantalla.tabla.selectRow(0)

    assert "Primera línea de prueba" in pantalla.etiqueta_preview.text()


def test_previsualizacion_sin_soporte_avisa_que_no_hay_vista(qtbot, conn, monkeypatch, tmp_path):
    ruta = tmp_path / "contrato.docx"
    ruta.write_bytes(b"contenido binario cualquiera")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(ruta), "")))

    def _elegir_manual(self):
        self.combo_categoria.setCurrentText("Manual del usuario")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", _elegir_manual)

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_alcance.setCurrentText("Espacio")
    pantalla.combo_tipo.setCurrentText("Documento")
    pantalla._agregar()
    pantalla.tabla.selectRow(0)

    assert pantalla.etiqueta_preview.text() == "No hay vista disponible."
