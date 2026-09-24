import pytest
from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtWidgets import QDateEdit, QDialog, QLabel, QMessageBox, QScrollArea, QTabWidget, QWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.crud_generico import Campo, PantallaCRUD, _DialogoRegistro, campos_libres
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    """QMessageBox.exec() bloquea esperando un clic real, que nunca llega en
    los tests — se mockean sus variantes estáticas para que no cuelguen."""
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def _campos_edificio():
    return [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("Domicilio", "Domicilio"),
        Campo("CampoLibre1", "Campo libre 1"),
    ]


def test_campos_libres_visibles_por_defecto(conn):
    nombres = [c.nombre for c in campos_libres(conn)]
    assert nombres == ["CampoLibre1", "CampoLibre2", "CampoLibre3"]


def test_campos_libres_se_ocultan_si_se_apaga_en_configuracion(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, VisualizarCamposLibres=0)
    assert campos_libres(conn) == []


def test_panel_extra_superior_izquierda_queda_entre_buscar_y_nuevo(qtbot, conn):
    from PySide6.QtWidgets import QLabel

    etiqueta = QLabel("Filtro propio")
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio(), panel_extra_superior_izquierda=etiqueta)
    qtbot.addWidget(pantalla)
    assert etiqueta.parent() is not None
    padre = pantalla.campo_buscar.parentWidget()
    layout = padre.layout()
    indices = {layout.itemAt(i).widget(): i for i in range(layout.count()) if layout.itemAt(i).widget() is not None}
    assert indices[pantalla.campo_buscar] < indices[etiqueta] < indices[pantalla.boton_nuevo]


def test_nuevo_secundario_pinta_boton_nuevo_como_secundario(qtbot, conn):
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio(), nuevo_secundario=True)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_nuevo.objectName() == "botonSecundario"


def test_nuevo_es_primario_por_defecto(qtbot, conn):
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)
    assert pantalla.boton_nuevo.objectName() == "botonPrimario"


def test_pantalla_crud_lista_registros_existentes(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre, Domicilio) VALUES ('Torre Norte', 'Calle 1')")
    conn.commit()
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.rowCount() == 1
    assert pantalla.tabla_widget.item(0, 0).text() == "Torre Norte"


def test_pantalla_crud_nuevo_crea_registro_via_dialogo(qtbot, conn, monkeypatch):
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)

    def _dialogo_aceptado_con_nombre(self, *a, **k):
        self._entradas["Nombre"].setText("Torre Sur")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.gui.crud_generico._DialogoRegistro.exec", _dialogo_aceptado_con_nombre)
    pantalla._nuevo()
    assert pantalla.tabla_widget.rowCount() == 1
    assert pantalla.repositorio.listar()[0]["Nombre"] == "Torre Sur"


def test_dialogo_registro_numero_invalido_no_revienta_y_avisa(qtbot, conn, monkeypatch):
    campos = [Campo("SaldoCuentaActual", "Saldo", tipo="numero")]
    dialogo = _DialogoRegistro(conn, campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: avisos.append(a[2])))

    dialogo._entradas["SaldoCuentaActual"].setText("abc")
    dialogo._validar_y_aceptar()

    assert dialogo.result() != QDialog.DialogCode.Accepted
    assert avisos and "número" in avisos[0]


def test_dialogo_registro_numero_valido_se_acepta(qtbot, conn):
    campos = [Campo("SaldoCuentaActual", "Saldo", tipo="numero")]
    dialogo = _DialogoRegistro(conn, campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    dialogo._entradas["SaldoCuentaActual"].setText("123.45")
    dialogo._validar_y_aceptar()
    assert dialogo.valores()["SaldoCuentaActual"] == 123.45


def test_pantalla_crud_eliminar_sin_seleccion_no_falla(qtbot, conn):
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)
    pantalla._eliminar()  # no debe lanzar excepción — solo informa que no hay selección


def test_pantalla_crud_booleano_se_muestra_si_no(qtbot, conn):
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    conn.execute("INSERT INTO Responsable (Nombre, Activo) VALUES ('Ana', 0)")
    conn.commit()
    pantalla = PantallaCRUD(conn, "Responsable", "Responsables", campos)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.item(0, 1).text() == "No"


def test_pantalla_crud_combo_muestra_etiqueta_no_id(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, 'PB')", (id_edificio,))
    conn.commit()

    def opciones_edificio(c):
        filas = c.execute("SELECT IdEdificio, Nombre FROM Edificio").fetchall()
        return [(f["IdEdificio"], f["Nombre"]) for f in filas]

    campos = [
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=opciones_edificio),
        Campo("Departamento", "Departamento"),
    ]
    pantalla = PantallaCRUD(conn, "Unidad", "Unidades", campos)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.item(0, 0).text() == "Torre Norte"


def test_pantalla_crud_eliminar_con_dependientes_no_rompe(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, 'PB')", (id_edificio,))
    conn.commit()

    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)
    pantalla.tabla_widget.selectRow(0)
    item = pantalla.tabla_widget.item(0, 0)
    assert item.data(Qt.ItemDataRole.UserRole) == id_edificio

    pantalla._eliminar()  # FK activa: debe fallar con IntegrityError y no propagarlo
    assert conn.execute("SELECT COUNT(*) c FROM Edificio").fetchone()["c"] == 1


def test_pantalla_crud_editar_campo_numerico_not_null_vacio_no_rompe(qtbot, conn, monkeypatch):
    """CantLimitePlacas es NOT NULL DEFAULT 0 en la base — dejarlo vacío
    al editar mandaría NULL, que antes reventaba con un IntegrityError
    sin atrapar en vez de avisar."""
    campos = [
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=lambda c: [], requerido=True),
        Campo("Departamento", "Departamento", requerido=True),
        Campo("CantLimitePlacas", "Límite de placas", tipo="numero"),
    ]
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="PB", CantLimitePlacas=3)
    conn.commit()

    pantalla = PantallaCRUD(conn, "Unidad", "Unidades", campos)
    qtbot.addWidget(pantalla)
    pantalla.tabla_widget.selectRow(0)

    def _dialogo_con_limite_vacio(self, *a, **k):
        self._entradas["CantLimitePlacas"].setText("")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.gui.crud_generico._DialogoRegistro.exec", _dialogo_con_limite_vacio)
    pantalla._editar()  # no debe lanzar excepción — avisa y no guarda

    assert obtener_repositorio(conn, "Unidad").obtener(id_unidad)["CantLimitePlacas"] == 3


def test_pantalla_crud_campo_numerico_obligatorio_vacio_avisa_y_no_crea(qtbot, conn, monkeypatch):
    """La marca `requerido=True` en un Campo tipo="numero" no se chequeaba
    (el chequeo de "obligatorio" solo miraba tipo texto/texto_largo) —
    dejarlo vacío pasaba la validación y recién reventaba al guardar
    contra una columna NOT NULL sin default."""
    campos = [
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=lambda c: [], requerido=True),
        Campo("Departamento", "Departamento", requerido=True),
        Campo("CantLimitePlacas", "Límite de placas", tipo="numero", requerido=True),
    ]
    pantalla = PantallaCRUD(conn, "Unidad", "Unidades", campos)
    qtbot.addWidget(pantalla)

    def _dialogo_sin_limite(self, *a, **k):
        self._entradas["Departamento"].setText("PB")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.gui.crud_generico._DialogoRegistro.exec", _dialogo_sin_limite)
    pantalla._nuevo()

    assert pantalla.tabla_widget.rowCount() == 0


def test_pantalla_crud_usa_formato_solapa_con_panel_izquierdo(qtbot, conn):
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)
    tabs = pantalla.findChildren(QTabWidget)
    assert len(tabs) == 1
    assert tabs[0].tabText(0) == "Listado"
    scrolls = pantalla.findChildren(QScrollArea)
    assert len(scrolls) == 1
    assert scrolls[0].widget().objectName() == "panelSolapa"


def test_pantalla_crud_panel_izquierdo_tiene_fondo_blanco_no_gris(qtbot, conn):
    """Bug detectado al revisar capturas ("el panel izquierdo tiene un
    relleno mas claro que el contenido"): el panel izquierdo (Buscar +
    Nuevo/Editar/Eliminar) nunca tenía objectName propio, así que
    quedaba con el gris default de Qt para un QWidget genérico en vez
    del blanco de `t['superficie']` que sí pintaba el widget que lo
    contiene — `QWidget#panelSolapa` es un selector por id, no cascada a
    los hijos. Se corrigió sumándole el mismo objectName al panel
    izquierdo en `_armar_panel_izquierda_y_tabla`."""
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)
    paneles = [w for w in pantalla.findChildren(QWidget) if w.objectName() == "panelSolapa"]
    # el contenido de la solapa (dentro del QScrollArea) + el panel
    # izquierdo anidado adentro, los dos con el mismo objectName.
    assert len(paneles) == 2


def test_pantalla_crud_anidado_panel_izquierdo_tiene_fondo_blanco(qtbot, conn):
    """Mismo bug, mismo arreglo, en modo `anidado=True` (formularios
    compuestos del reordenamiento): acá `self` ya tenía el objectName
    (es el widget de más afuera que se pasa a `addTab`), pero adentro
    tanto `contenido` (dentro del QScrollArea) como el panel izquierdo
    seguían sin él."""
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio(), anidado=True)
    qtbot.addWidget(pantalla)
    paneles = [w for w in pantalla.findChildren(QWidget) if w.objectName() == "panelSolapa"]
    # `contenido` + el panel izquierdo anidado adentro (self mismo no
    # cuenta: findChildren busca descendientes, no el propio widget).
    assert len(paneles) == 2


def test_pantalla_crud_botones_tienen_los_estilos_compartidos(qtbot, conn):
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)
    assert pantalla.boton_nuevo.objectName() == "botonPrimario"
    assert pantalla.boton_editar.objectName() == "botonSecundario"
    assert pantalla.boton_eliminar.objectName() == "botonSecundario"


def test_pantalla_crud_buscar_filtra_filas_por_cualquier_columna(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre, CampoLibre1) VALUES ('Torre Norte', 'Ramos Mejía')")
    conn.execute("INSERT INTO Edificio (Nombre, CampoLibre1) VALUES ('Torre Sur', 'Haedo')")
    conn.commit()
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)

    pantalla.campo_buscar.setText("haedo")
    ocultas = [pantalla.tabla_widget.isRowHidden(f) for f in range(pantalla.tabla_widget.rowCount())]
    assert ocultas.count(True) == 1

    pantalla.campo_buscar.setText("")
    assert all(not pantalla.tabla_widget.isRowHidden(f) for f in range(pantalla.tabla_widget.rowCount()))


def test_pantalla_crud_buscar_ignora_mayusculas_y_acentos(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre, CampoLibre1) VALUES ('Torre Norte', 'Ramos Mejía')")
    conn.commit()
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)
    pantalla.campo_buscar.setText("MEJIA")
    assert pantalla.tabla_widget.isRowHidden(0) is False


def test_pantalla_crud_solo_lectura_no_tiene_botones_pero_si_buscar(qtbot, conn):
    pantalla = PantallaCRUD(conn, "EsquemaDescuentos", "Esquema de descuentos", [
        Campo("HorasSemanalesDesde", "Desde", tipo="numero"),
    ], solo_lectura=True)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_nuevo is None
    assert pantalla.campo_buscar is not None


def test_pantalla_crud_compacto_mantiene_el_layout_viejo(qtbot, conn):
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio(), compacto=True)
    qtbot.addWidget(pantalla)
    assert pantalla.findChildren(QTabWidget) == []
    assert pantalla.campo_buscar is None
    assert pantalla.boton_editar.objectName() == "botonSecundario"


def test_pantalla_crud_anidado_no_tiene_titulo_ni_tabwidget_propio(qtbot, conn):
    """anidado=True (reordenamiento de formularios): el catálogo se
    embebe como solapa de un formulario compuesto — sin título Nivel 1
    ni su propio QTabWidget de una sola pestaña "Listado", pero
    conservando Buscar + Nuevo/Editar/Eliminar + tabla de siempre."""
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio(), anidado=True)
    qtbot.addWidget(pantalla)
    assert pantalla.objectName() == "panelSolapa"
    assert pantalla.findChild(QLabel, "tituloPantalla") is None
    assert pantalla.findChildren(QTabWidget) == []
    assert pantalla.campo_buscar is not None
    assert pantalla.boton_nuevo.objectName() == "botonPrimario"


def test_pantalla_crud_anidado_conserva_buscar_y_foco(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre, CampoLibre1) VALUES ('Torre Norte', 'Ramos Mejía')")
    conn.execute("INSERT INTO Edificio (Nombre, CampoLibre1) VALUES ('Torre Sur', 'Haedo')")
    conn.commit()
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio(), anidado=True)
    qtbot.addWidget(pantalla)

    pantalla.campo_buscar.setText("haedo")
    ocultas = [pantalla.tabla_widget.isRowHidden(f) for f in range(pantalla.tabla_widget.rowCount())]
    assert ocultas.count(True) == 1

    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.campo_buscar.hasFocus())


def _campos_fecha_especial():
    return [Campo("Fecha", "Fecha", tipo="fecha"), Campo("Descripcion", "Descripción")]


def test_campo_fecha_widget_es_qdateedit_con_dia_abreviado_en_espanol(qtbot, conn):
    dialogo = _DialogoRegistro(conn, _campos_fecha_especial(), "Nuevo registro")
    qtbot.addWidget(dialogo)
    entrada = dialogo._entradas["Fecha"]
    assert isinstance(entrada, QDateEdit)
    assert entrada.displayFormat() == "ddd dd-MM-yyyy"
    assert entrada.locale().language() == QLocale.Language.Spanish
    assert entrada.calendarPopup() is True


def test_campo_fecha_precarga_el_valor_guardado(qtbot, conn):
    conn.execute("INSERT INTO FechasEspeciales (Fecha, Descripcion) VALUES ('2026-12-25', 'Navidad')")
    conn.commit()
    registro = conn.execute("SELECT * FROM FechasEspeciales").fetchone()
    dialogo = _DialogoRegistro(conn, _campos_fecha_especial(), "Editar registro", registro=registro)
    qtbot.addWidget(dialogo)
    assert dialogo._entradas["Fecha"].date() == QDate(2026, 12, 25)


def test_campo_fecha_guarda_como_aaaa_mm_dd(qtbot, conn):
    dialogo = _DialogoRegistro(conn, _campos_fecha_especial(), "Nuevo registro")
    qtbot.addWidget(dialogo)
    dialogo._entradas["Fecha"].setDate(QDate(2026, 9, 7))
    assert dialogo.valores()["Fecha"] == "2026-09-07"


def test_campo_fecha_se_muestra_en_tabla_con_dia_abreviado(qtbot, conn):
    conn.execute("INSERT INTO FechasEspeciales (Fecha, Descripcion) VALUES ('2026-09-07', 'Feriado de prueba')")
    conn.commit()
    pantalla = PantallaCRUD(conn, "FechasEspeciales", "Fechas especiales", _campos_fecha_especial())
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.item(0, 0).text() == "lun 07-09-2026"


def test_campo_fecha_ordena_cronologicamente_no_por_texto_mostrado(qtbot, conn):
    """"vie 02-01-2026" y "lun 01-06-2026" en orden alfabético de texto
    quedarían "lun..." antes que "vie..." aunque enero es anterior a
    junio — la columna tiene que ordenar por el AAAA-MM-DD real."""
    conn.execute("INSERT INTO FechasEspeciales (Fecha, Descripcion) VALUES ('2026-06-01', 'Junio')")
    conn.execute("INSERT INTO FechasEspeciales (Fecha, Descripcion) VALUES ('2026-01-02', 'Enero')")
    conn.commit()
    pantalla = PantallaCRUD(conn, "FechasEspeciales", "Fechas especiales", _campos_fecha_especial())
    qtbot.addWidget(pantalla)
    pantalla.tabla_widget.horizontalHeader().sectionClicked.emit(0)
    assert pantalla.tabla_widget.item(0, 1).text() == "Enero"
    assert pantalla.tabla_widget.item(1, 1).text() == "Junio"
