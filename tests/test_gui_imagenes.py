import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.main_window import Seccion
from app.gui.pantallas.imagenes import _PanelGestorArchivos, _DialogoAgregarArchivo, _repartir_sobrante
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


def test_panel_izquierdo_tiene_fondo_blanco_no_gris(qtbot, conn):
    """Bug detectado al revisar capturas ("el panel izquierdo tiene un
    relleno mas claro que el contenido"): igual que en `crud_generico.py`,
    el panel izquierdo (filtros + botones) y el contenido interno del
    QScrollArea nunca tenían objectName propio, así que quedaban con el
    gris default de Qt en vez del blanco de `t['superficie']` que sí
    pintaba `self` — `QWidget#panelSolapa` es un selector por id, no
    cascada a los hijos. Se corrigió sumándoles el mismo objectName.

    Pedido explícito de la clienta sobre una ronda posterior: filtros y
    botones pasan a ser DOS columnas separadas (antes una sola) — ahora
    son tres los `panelSolapa` anidados (filtros + botones + `contenido`
    del scroll)."""
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    paneles = [w for w in pantalla.findChildren(QWidget) if w.objectName() == "panelSolapa"]
    # `contenido` (dentro del scroll) + panel de filtros + panel de
    # botones (self mismo no cuenta: findChildren busca descendientes,
    # no el propio widget).
    assert len(paneles) == 3


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


def test_columnas_categoria_principal_activo_no_cortan_el_titulo(
    qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch,
):
    """Pedido explícito de la clienta: "Categoría", "Principal" y
    "Activo" al mínimo de ancho, pero sin cortar el título de la
    columna — el contenido de esas celdas ("Sí"/"No"/una categoría
    corta) es más angosto que el propio título en negrita, así que
    `resizeColumnsToContents` (que solo mide contenido, no encabezado)
    no alcanza sola."""
    from PySide6.QtGui import QFontMetrics

    ruta = _archivo_jpg(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (ruta, "")))
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()

    metrica = QFontMetrics(pantalla.tabla.horizontalHeader().font())
    for columna, titulo in ((2, "Categoría"), (3, "Principal"), (4, "Activo")):
        ancho_titulo = metrica.horizontalAdvance(titulo)
        assert pantalla.tabla.columnWidth(columna) >= ancho_titulo, (
            f"la columna {titulo!r} quedó más angosta que su propio título"
        )


def test_principal_y_activo_quedan_centrados(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    ruta = _archivo_jpg(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (ruta, "")))
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()

    assert pantalla.tabla.item(0, 3).textAlignment() == (Qt.AlignmentFlag.AlignCenter)
    assert pantalla.tabla.item(0, 4).textAlignment() == (Qt.AlignmentFlag.AlignCenter)


def test_descripcion_sin_piso_minimo_artificial_sin_sobrante_que_repartir(qtbot):
    """Pedido explícito de la clienta, ronda original: "achicá la columna
    Descripción lo necesario" — el piso propio de 300px que tenía antes
    (más generoso que el resto de las columnas) se saca. Confirmado acá
    con `_repartir_sobrante` directo (sin sobrante, no hay ningún piso
    artificial para "Descripción" ni para nada) — la tabla puede SÍ
    terminar más ancha que eso cuando hay ancho de sobra para repartir
    (ver los tests de `_repartir_sobrante` más abajo), pero eso ya no es
    un piso fijo, depende del ancho real disponible."""
    assert _repartir_sobrante(0, indice_descripcion=1, cantidad_columnas=5, columnas_minimas=frozenset({0, 2, 3, 4})) == {}


def test_repartir_sobrante_mitad_a_descripcion_resto_parejo_entre_las_otras():
    reparto = _repartir_sobrante(100, indice_descripcion=1, cantidad_columnas=4, columnas_minimas=frozenset({2, 3}))
    assert reparto == {1: 50, 0: 50}


def test_repartir_sobrante_reparte_el_residuo_entre_las_primeras_columnas():
    # sobrante=103 -> 51 para "Descripción" (índice 0), resto=52 entre 3
    # columnas (1, 2, 3): 17 + 17 + 18, el residuo de la división (1) va
    # a la primera.
    reparto = _repartir_sobrante(103, indice_descripcion=0, cantidad_columnas=4, columnas_minimas=frozenset())
    assert reparto[0] == 51
    assert reparto[1] == 18
    assert reparto[2] == 17
    assert reparto[3] == 17


def test_repartir_sobrante_sin_otras_columnas_descripcion_se_lleva_todo():
    reparto = _repartir_sobrante(100, indice_descripcion=1, cantidad_columnas=2, columnas_minimas=frozenset({0}))
    assert reparto == {1: 100}


def test_repartir_sobrante_columnas_minimas_no_participan_del_reparto():
    reparto = _repartir_sobrante(100, indice_descripcion=1, cantidad_columnas=5, columnas_minimas=frozenset({2, 3, 4}))
    assert 2 not in reparto and 3 not in reparto and 4 not in reparto


def test_repartir_sobrante_cero_o_negativo_no_reparte_nada():
    assert _repartir_sobrante(0, indice_descripcion=1, cantidad_columnas=3, columnas_minimas=frozenset()) == {}
    assert _repartir_sobrante(-10, indice_descripcion=1, cantidad_columnas=3, columnas_minimas=frozenset()) == {}


def test_tabla_crece_para_ocupar_todo_el_ancho_disponible(qtbot, conn):
    """Pedido explícito de la clienta sobre esta ronda: la tabla pasa a
    ocupar todo el ancho de la pantalla (antes quedaba fija al ancho
    justo de sus columnas, y la Vista previa se llevaba el resto) —
    confirmado mostrando la pantalla real a un ancho generoso y viendo
    que "Descripción" terminó más ancha que su ancho natural."""
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    pantalla.resize(1600, 800)
    qtbot.waitExposed(pantalla)

    assert pantalla.tabla.columnWidth(pantalla._indice_descripcion) > 300


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


def test_descargar_con_exito_muestra_cartel_de_operacion_exitosa(
    qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch,
):
    """Pedido explícito de la clienta: mismo cartel de "operación exitosa"
    que ya tienen "Agregar archivo"/"Eliminar archivo" en esta solapa —
    antes "Descargar" quedaba silencioso."""
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (_archivo_jpg(tmp_path), "")))
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()
    pantalla.tabla.selectRow(0)

    destino = tmp_path / "descargas" / "copia.jpg"
    destino.parent.mkdir()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))
    mostrados = []
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: mostrados.append(a[2] if len(a) > 2 else k.get("text"))),
    )

    pantalla._descargar()

    assert mostrados == ["Archivo descargado con éxito."]


def test_descargar_sin_destino_elegido_no_muestra_cartel(qtbot, conn, edificio, unidad, consultorio, tmp_path, monkeypatch):
    """Cancelar el diálogo "Guardar como" no es una descarga exitosa — no
    tiene que mostrar el cartel."""
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (_archivo_jpg(tmp_path), "")))
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla._agregar()
    pantalla.tabla.selectRow(0)

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    mostrados = []
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: mostrados.append(a[2] if len(a) > 2 else k.get("text"))),
    )

    pantalla._descargar()

    assert mostrados == []


def _monkeypatch_clipboard(monkeypatch):
    """Mismo criterio que `test_gui_reservas._monkeypatch_clipboard`."""
    copiado = []
    monkeypatch.setattr(
        "app.gui.pantallas.imagenes.QApplication.clipboard",
        staticmethod(lambda: type("_C", (), {"setText": lambda self, t: copiado.append(t)})()),
    )
    return copiado


def test_agregar_enlace_via_dialogo_no_abre_ningun_selector_de_archivo(
    qtbot, conn, edificio, unidad, consultorio, monkeypatch,
):
    """Un enlace no tiene archivo que elegir — `_agregar` no debería
    llamar nunca a `QFileDialog.getOpenFileName` para el tipo Enlace."""
    def _reventar(*a, **k):
        raise AssertionError("no debería abrirse el selector de archivo para un enlace")

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(_reventar))

    def _cargar_url(self):
        self.campo_url.setText("https://youtu.be/abc123")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", _cargar_url)

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla.combo_tipo.setCurrentText("Enlace")

    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 1).text() == "Consultorio - Recorrido del consultorio - 1"
    assert pantalla.tabla.item(0, 2).text() == "Recorrido del consultorio"


def test_agregar_enlace_sin_url_valida_avisa_y_no_agrega(qtbot, conn, edificio, unidad, consultorio, monkeypatch):
    def _sin_url(self):
        return QDialog.DialogCode.Accepted  # campo_url queda vacío

    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", _sin_url)

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla.combo_tipo.setCurrentText("Enlace")

    pantalla._agregar()

    assert pantalla.tabla.rowCount() == 0


def test_boton_descargar_pasa_a_copiar_enlace_con_tipo_enlace(qtbot, conn):
    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_descargar.text() == "Descargar"

    pantalla.combo_tipo.setCurrentText("Enlace")
    assert pantalla.boton_descargar.text() == "Copiar enlace"

    pantalla.combo_tipo.setCurrentText("Documento")
    assert pantalla.boton_descargar.text() == "Descargar"


def test_copiar_enlace_copia_la_url_al_portapapeles(qtbot, conn, edificio, unidad, consultorio, monkeypatch):
    def _cargar_url(self):
        self.campo_url.setText("https://youtu.be/abc123")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", _cargar_url)

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla.combo_tipo.setCurrentText("Enlace")
    pantalla._agregar()
    pantalla.tabla.selectRow(0)

    copiado = _monkeypatch_clipboard(monkeypatch)
    mostrados = []
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: mostrados.append(a[2] if len(a) > 2 else k.get("text"))),
    )
    pantalla._descargar_o_copiar()

    assert copiado == ["https://youtu.be/abc123"]
    # Pedido explícito de la clienta: mismo cartel de "operación exitosa"
    # para los dos caminos del botón "Descargar"/"Copiar enlace".
    assert mostrados == ["Enlace copiado con éxito."]


def test_previsualizacion_de_enlace_muestra_la_url_como_texto(qtbot, conn, edificio, unidad, consultorio, monkeypatch):
    def _cargar_url(self):
        self.campo_url.setText("https://youtu.be/abc123")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoAgregarArchivo, "exec", _cargar_url)

    pantalla = _PanelGestorArchivos(conn)
    qtbot.addWidget(pantalla)
    _elegir_consultorio(pantalla, edificio, unidad, consultorio)
    pantalla.combo_tipo.setCurrentText("Enlace")
    pantalla._agregar()

    pantalla.tabla.selectRow(0)

    assert "https://youtu.be/abc123" in pantalla.etiqueta_preview.text()


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
