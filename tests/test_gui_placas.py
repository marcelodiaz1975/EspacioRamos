import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QMessageBox, QScrollArea

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.placas import _PanelPlacasOperativas, _DialogoPlaca
from app.negocio.placas import asignar_placa
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


def _id_localidad(conn, nombre: str | None) -> int | None:
    if nombre is None:
        return None
    fila = conn.execute("SELECT IdLocalidad FROM Localidad WHERE Localidad = ?", (nombre,)).fetchone()
    return fila["IdLocalidad"] if fila else obtener_repositorio(conn, "Localidad").crear(Localidad=nombre)


def _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A", localidad=None, limite_placas=10):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre=nombre_edificio, IdLocalidad=_id_localidad(conn, localidad)
    )
    id_unidad = obtener_repositorio(conn, "Unidad").crear(
        IdEdificio=id_edificio, Departamento=departamento, CantLimitePlacas=limite_placas,
    )
    return id_edificio, id_unidad


def _crear_profesional(conn, apellido="Lo Veci", nombre_pila="Virginia", tratamiento="Lic.", codigo=None):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido=apellido, NombrePila=nombre_pila, Tratamiento=tratamiento, IdCodigo=codigo,
    )


def test_paneles_de_placas_usan_el_fondo_claro_de_la_solapa(qtbot, conn):
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_buscar.objectName() == "panelSolapa"
    assert pantalla.panel_imprimir.objectName() == "panelSolapa"


def test_columnas_de_la_tabla_arrancan_con_localidad(qtbot, conn):
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    encabezados = [pantalla.tabla.horizontalHeaderItem(i).text() for i in range(pantalla.tabla.columnCount())]
    assert encabezados == [
        "Localidad", "Edificio", "Unidad", "Posición", "Profesional", "Nombre grabado", "Personalizada",
    ]


def test_nombre_grabado_es_la_unica_columna_que_se_estira(qtbot, conn):
    """Pedido explícito de la clienta: reducir las seis columnas cortas
    (Localidad/Edificio/Unidad/Posición/Profesional/Personalizada) y
    dárselo a "Nombre grabado" — es la única en modo Stretch, las otras
    seis se ajustan a su contenido."""
    from PySide6.QtWidgets import QHeaderView

    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    header = pantalla.tabla.horizontalHeader()
    for columna in (0, 1, 2, 3, 4, 6):
        assert header.sectionResizeMode(columna) == QHeaderView.ResizeMode.Interactive
    assert header.sectionResizeMode(5) == QHeaderView.ResizeMode.Stretch


def test_nombre_grabado_entra_al_menos_51_caracteres(qtbot, conn):
    """51 = dos líneas completas de 24 caracteres (el límite calibrado
    contra "Lic. Agustina Viavattene") más " / " en el medio."""
    from PySide6.QtGui import QFontMetrics

    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(
        conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional,
        es_personalizada=True, nombre_grabado_personalizado="Lic. Agustina Viavattene\nEquipo Nutri Oeste 24c",
    )
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_buscar.resize(1400, 700)
    pantalla.panel_buscar.show()
    qtbot.waitExposed(pantalla.panel_buscar)

    referencia = "Lic. Agustina Viavattene / Lic. Agustina Viavattene"  # 51 caracteres
    ancho_necesario = QFontMetrics(pantalla.tabla.font()).boundingRect(referencia).width()
    assert pantalla.tabla.columnWidth(5) >= ancho_necesario


def test_columnas_cortas_quedan_mas_angostas_que_nombre_grabado(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_buscar.resize(1400, 700)
    pantalla.panel_buscar.show()
    qtbot.waitExposed(pantalla.panel_buscar)

    for columna in (0, 1, 2, 3, 4, 6):
        assert pantalla.tabla.columnWidth(columna) < pantalla.tabla.columnWidth(5)


def test_nombre_grabado_en_la_tabla_muestra_barra_en_vez_de_salto_de_linea(qtbot, conn):
    """Pedido explícito de la clienta: "la barra solo es visual en el
    campo para que sepa a simple vista que se hizo en dos líneas" — el
    dato guardado sigue con el salto real (ver test_placas.py), esto es
    puramente de esta columna de la tabla."""
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(
        conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional,
        es_personalizada=True, nombre_grabado_personalizado="Lic. Agustina Viavattene\nEquipo Nutri Oeste",
    )
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.tabla.item(0, 5).text() == "Lic. Agustina Viavattene / Equipo Nutri Oeste"


def test_nombre_grabado_de_una_linea_en_la_tabla_queda_de_corrido(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(
        conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional,
        es_personalizada=True, nombre_grabado_personalizado="Equipo Nutri Oeste",
    )
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.tabla.item(0, 5).text() == "Equipo Nutri Oeste"


def test_posicion_queda_centrada(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    alineacion = pantalla.tabla.item(0, 3).textAlignment()
    assert alineacion & Qt.AlignmentFlag.AlignHCenter


def test_panel_de_filtros_queda_a_la_izquierda_de_la_tabla(qtbot, conn):
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_buscar.resize(1200, 700)
    pantalla.panel_buscar.show()
    qtbot.waitExposed(pantalla.panel_buscar)
    assert pantalla.combo_profesional_filtro.x() < pantalla.tabla.x()
    assert pantalla.combo_profesional_filtro.parentWidget().width() >= 300


def test_botones_de_impresion_son_del_mismo_tamano_y_agregar_queda_centrado(qtbot, conn):
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_imprimir.resize(1400, 700)
    pantalla.panel_imprimir.show()
    qtbot.waitExposed(pantalla.panel_imprimir)
    assert pantalla.boton_agregar_impresion.width() == pantalla.boton_quitar_impresion.width()
    assert pantalla.boton_agregar_impresion.width() == pantalla.boton_generar_pdf.width()

    centro_boton = pantalla.boton_agregar_impresion.x() + pantalla.boton_agregar_impresion.width() / 2
    mitad_izquierda = pantalla.lista_impresion.x() + pantalla.lista_impresion.width() / 2
    assert abs(centro_boton - mitad_izquierda) <= 2


def test_botones_quitar_y_generar_quedan_a_la_derecha(qtbot, conn):
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_imprimir.resize(1400, 700)
    pantalla.panel_imprimir.show()
    qtbot.waitExposed(pantalla.panel_imprimir)
    fin_lista = pantalla.lista_impresion.x() + pantalla.lista_impresion.width()
    fin_generar = pantalla.boton_generar_pdf.x() + pantalla.boton_generar_pdf.width()
    assert abs(fin_generar - fin_lista) <= 2
    assert pantalla.boton_quitar_impresion.x() < pantalla.boton_generar_pdf.x()


def test_orden_por_defecto_es_localidad_edificio_unidad_posicion(qtbot, conn):
    _, id_unidad_z = _crear_unidad(conn, nombre_edificio="Z Torre", departamento="1A", localidad="Ramos Mejía")
    _, id_unidad_a = _crear_unidad(conn, nombre_edificio="A Torre", departamento="1A", localidad="Ramos Mejía")
    _, id_unidad_haedo = _crear_unidad(conn, nombre_edificio="Torre", departamento="1A", localidad="Haedo")
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad_z, posicion=1, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad_a, posicion=1, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad_haedo, posicion=1, id_profesional=id_profesional)

    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)

    localidades = [pantalla.tabla.item(f, 0).text() for f in range(pantalla.tabla.rowCount())]
    edificios = [pantalla.tabla.item(f, 1).text() for f in range(pantalla.tabla.rowCount())]
    assert localidades == ["Haedo", "Ramos Mejía", "Ramos Mejía"]
    assert edificios[1:] == ["A Torre", "Z Torre"]


def test_orden_por_defecto_desempata_por_posicion(qtbot, conn):
    """La última clave del orden por defecto es Posición, no Profesional
    (pedido de la clienta): dos placas en la misma localidad/edificio/
    unidad quedan ordenadas por su número de posición."""
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=3, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_profesional)

    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)

    posiciones = [pantalla.tabla.item(f, 3).text() for f in range(pantalla.tabla.rowCount())]
    assert posiciones == ["1", "2", "3"]


def test_click_en_encabezado_ordena_por_esa_columna(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_z = _crear_profesional(conn, apellido="Zeta")
    id_a = _crear_profesional(conn, apellido="Alfa")
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_z)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_a)

    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)

    pantalla.tabla.horizontalHeader().sectionClicked.emit(4)  # columna Profesional
    assert "Alfa" in pantalla.tabla.item(0, 4).text()

    pantalla.tabla.horizontalHeader().sectionClicked.emit(4)  # segundo click: invierte
    assert "Zeta" in pantalla.tabla.item(0, 4).text()


def test_reingresar_a_la_pantalla_resetea_filtros(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_1 = _crear_profesional(conn, apellido="Uno")
    id_2 = _crear_profesional(conn, apellido="Dos")
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_1)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_2)

    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_filtro.findData(id_1)
    pantalla.combo_profesional_filtro.setCurrentIndex(indice)
    assert pantalla.tabla.rowCount() == 1

    pantalla.panel_buscar.show()
    qtbot.waitExposed(pantalla.panel_buscar)

    assert pantalla.combo_profesional_filtro.currentIndex() == 0
    assert pantalla.tabla.rowCount() == 2


def test_tabla_arranca_con_todas_las_placas(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)

    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 4).text() == "Lic. Virginia Lo Veci"


def test_filtro_por_unidad_reduce_la_tabla(qtbot, conn):
    _, id_unidad_1 = _crear_unidad(conn, nombre_edificio="Torre A", departamento="1A")
    _, id_unidad_2 = _crear_unidad(conn, nombre_edificio="Torre B", departamento="1B")
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad_1, posicion=1, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad_2, posicion=1, id_profesional=id_profesional)

    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.rowCount() == 2

    pantalla.lista_unidad.clearSelection()
    for i in range(pantalla.lista_unidad.count()):
        if pantalla.lista_unidad.item(i).text() == "Torre A - 1A":
            pantalla.lista_unidad.item(i).setSelected(True)
            break

    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 1).text() == "Torre A"


def test_filtro_por_profesional_reduce_la_tabla(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_1 = _crear_profesional(conn, apellido="Uno")
    id_2 = _crear_profesional(conn, apellido="Dos")
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_1)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_2)

    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.rowCount() == 2

    indice = pantalla.combo_profesional_filtro.findData(id_1)
    pantalla.combo_profesional_filtro.setCurrentIndex(indice)

    assert pantalla.tabla.rowCount() == 1


def test_etiquetas_y_tamano_de_los_botones_de_buscar_y_asignar(qtbot, conn):
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_asignar_nueva.text() == "Asignar posición de placa\na profesional"
    assert pantalla.boton_reasignar.text() == "Reasignar posición de placa\na otro profesional"
    assert pantalla.boton_liberar.text() == "Liberar posición de placa"
    assert pantalla.boton_asignar_nueva.width() == pantalla.boton_reasignar.width()
    assert pantalla.boton_asignar_nueva.width() == pantalla.boton_liberar.width()


def test_columnas_unidad_y_personalizada_quedan_centradas(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.item(0, 2).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    assert pantalla.tabla.item(0, 6).textAlignment() & Qt.AlignmentFlag.AlignHCenter


def test_botones_reasignar_y_liberar_arrancan_deshabilitados(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_reasignar.isEnabled() is False
    assert pantalla.boton_liberar.isEnabled() is False

    pantalla.tabla.selectRow(0)
    assert pantalla.boton_reasignar.isEnabled() is True
    assert pantalla.boton_liberar.isEnabled() is True


def test_asignar_placa_nueva_crea_registro(qtbot, conn, monkeypatch):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)

    def _aceptar(self, *a, **k):
        indice_unidad = self.combo_unidad.findData(id_unidad)
        self.combo_unidad.setCurrentIndex(indice_unidad)
        indice_profesional = self.combo_profesional.findData(id_profesional)
        self.combo_profesional.setCurrentIndex(indice_profesional)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoPlaca, "exec", _aceptar)
    pantalla._asignar_nueva()

    assert pantalla.tabla.rowCount() == 1
    assert obtener_repositorio(conn, "Placa").listar(IdUnidad=id_unidad)[0]["IdProfesional"] == id_profesional


def test_reasignar_pisa_el_mismo_registro(qtbot, conn, monkeypatch):
    _, id_unidad = _crear_unidad(conn)
    id_viejo = _crear_profesional(conn, apellido="Viejo")
    id_nuevo = _crear_profesional(conn, apellido="Nuevo")
    id_placa = asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_viejo)
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)

    def _aceptar(self, *a, **k):
        indice = self.combo_profesional.findData(id_nuevo)
        self.combo_profesional.setCurrentIndex(indice)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoPlaca, "exec", _aceptar)
    pantalla._reasignar()

    assert pantalla.tabla.rowCount() == 1
    placa = obtener_repositorio(conn, "Placa").obtener(id_placa)
    assert placa["IdProfesional"] == id_nuevo


def test_liberar_posicion_borra_el_registro(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)

    pantalla._liberar()

    assert pantalla.tabla.rowCount() == 0
    assert obtener_repositorio(conn, "Placa").listar(IdUnidad=id_unidad) == []


def test_dialogo_nueva_ofrece_solo_posiciones_libres(qtbot, conn):
    _, id_unidad = _crear_unidad(conn, limite_placas=3)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_profesional)

    dialogo = _DialogoPlaca(conn)
    qtbot.addWidget(dialogo)
    indice = dialogo.combo_unidad.findData(id_unidad)
    dialogo.combo_unidad.setCurrentIndex(indice)

    posiciones = [dialogo.combo_posicion.itemData(i) for i in range(dialogo.combo_posicion.count())]
    assert posiciones == [1, 3]


def test_dialogo_nueva_localidad_y_edificio_unicos_quedan_preseleccionados_y_deshabilitados(qtbot, conn):
    """Pedido explícito de la clienta: si solo hay una Localidad (o un
    solo Edificio dentro de ella), ese combo se preselecciona solo y
    queda deshabilitado — un combo deshabilitado ya queda afuera de la
    cadena de foco de Qt, así que el foco pasa solo al siguiente
    selector sin código extra."""
    _, id_unidad = _crear_unidad(conn, localidad="Ramos Mejía")

    dialogo = _DialogoPlaca(conn)
    qtbot.addWidget(dialogo)

    assert dialogo.combo_localidad.count() == 1
    assert dialogo.combo_localidad.isEnabled() is False
    assert dialogo.combo_edificio.count() == 1
    assert dialogo.combo_edificio.isEnabled() is False
    assert dialogo.combo_unidad.findData(id_unidad) == 0


def test_dialogo_nueva_con_varias_localidades_el_combo_queda_habilitado(qtbot, conn):
    _crear_unidad(conn, nombre_edificio="Torre A", localidad="Ramos Mejía")
    _crear_unidad(conn, nombre_edificio="Torre B", localidad="Haedo")

    dialogo = _DialogoPlaca(conn)
    qtbot.addWidget(dialogo)

    assert dialogo.combo_localidad.count() == 2
    assert dialogo.combo_localidad.isEnabled() is True


def test_dialogo_nueva_elegir_localidad_acota_edificio_y_unidad(qtbot, conn):
    _, id_unidad_ramos = _crear_unidad(conn, nombre_edificio="Torre A", departamento="1A", localidad="Ramos Mejía")
    _crear_unidad(conn, nombre_edificio="Torre B", departamento="1B", localidad="Haedo")

    dialogo = _DialogoPlaca(conn)
    qtbot.addWidget(dialogo)

    indice_haedo = dialogo.combo_localidad.findText("Haedo")
    dialogo.combo_localidad.setCurrentIndex(indice_haedo)

    assert dialogo.combo_edificio.count() == 1
    assert dialogo.combo_edificio.currentText() == "Torre B"
    ids_unidad = [dialogo.combo_unidad.itemData(i) for i in range(dialogo.combo_unidad.count())]
    assert ids_unidad == [dialogo.combo_unidad.itemData(0)]
    assert id_unidad_ramos not in ids_unidad


def test_dialogo_reasignar_muestra_localidad_edificio_y_unidad_por_separado(qtbot, conn):
    """Pedido explícito de la clienta: ya no un solo campo combinado
    "Edificio - Unidad" — Localidad/Edificio/Unidad quedan cada uno en
    su propia fila (de solo lectura acá: reasignar no cambia de unidad,
    solo de profesional)."""
    _, id_unidad = _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A", localidad="Ramos Mejía")
    id_profesional = _crear_profesional(conn)
    id_placa = asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    placa = obtener_repositorio(conn, "Placa").obtener(id_placa)

    dialogo = _DialogoPlaca(conn, placa_existente=placa)
    qtbot.addWidget(dialogo)

    layout = dialogo.layout()
    etiquetas = {}
    for fila in range(layout.rowCount()):
        item_etiqueta = layout.itemAt(fila, QFormLayout.ItemRole.LabelRole)
        item_campo = layout.itemAt(fila, QFormLayout.ItemRole.FieldRole)
        if item_etiqueta is None or item_campo is None or not isinstance(item_campo.widget(), QLabel):
            continue
        etiquetas[item_etiqueta.widget().text()] = item_campo.widget().text()

    assert etiquetas["Localidad"] == "Ramos Mejía"
    assert etiquetas["Edificio"] == "Ramos 1"
    assert etiquetas["Unidad"] == "1ro A"


def test_dialogo_reasignar_precarga_datos_existentes(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    id_placa = asignar_placa(
        conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional,
        es_personalizada=True, nombre_grabado_personalizado="Apodo",
    )
    placa = obtener_repositorio(conn, "Placa").obtener(id_placa)

    dialogo = _DialogoPlaca(conn, placa_existente=placa)
    qtbot.addWidget(dialogo)

    assert dialogo.combo_profesional.currentData() == id_profesional
    assert dialogo.casilla_personalizada.isChecked() is True
    assert dialogo.campo_linea1_personalizada.text() == "Apodo"
    assert dialogo.campo_linea2_personalizada.text() == ""
    valores = dialogo.valores()
    assert valores["id_unidad"] == id_unidad
    assert valores["posicion"] == 1


def test_dialogo_reasignar_precarga_las_dos_lineas_por_separado(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    id_placa = asignar_placa(
        conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional,
        es_personalizada=True, nombre_grabado_personalizado="Lic. Agustina Viavattene\nEquipo Nutri Oeste",
    )
    placa = obtener_repositorio(conn, "Placa").obtener(id_placa)

    dialogo = _DialogoPlaca(conn, placa_existente=placa)
    qtbot.addWidget(dialogo)

    assert dialogo.campo_linea1_personalizada.text() == "Lic. Agustina Viavattene"
    assert dialogo.campo_linea2_personalizada.text() == "Equipo Nutri Oeste"


def test_dialogo_lineas_personalizadas_limitan_a_24_caracteres(qtbot, conn):
    """Pedido explícito de la clienta: el límite es el mismo que calibró
    la placa física, "Lic. Agustina Viavattene" (24 caracteres, contando
    puntos y espacios)."""
    from app.gui.pantallas.placas import _MAX_CARACTERES_LINEA_PLACA

    dialogo = _DialogoPlaca(conn)
    qtbot.addWidget(dialogo)

    assert _MAX_CARACTERES_LINEA_PLACA == 24
    assert dialogo.campo_linea1_personalizada.maxLength() == 24
    assert dialogo.campo_linea2_personalizada.maxLength() == 24


def test_valores_arma_nombre_de_una_sola_linea(qtbot, conn):
    dialogo = _DialogoPlaca(conn)
    qtbot.addWidget(dialogo)
    dialogo.casilla_personalizada.setChecked(True)
    dialogo.campo_linea1_personalizada.setText("Equipo Nutri Oeste")

    assert dialogo.valores()["nombre_grabado_personalizado"] == "Equipo Nutri Oeste"


def test_valores_arma_nombre_de_dos_lineas_con_salto_real(qtbot, conn):
    dialogo = _DialogoPlaca(conn)
    qtbot.addWidget(dialogo)
    dialogo.casilla_personalizada.setChecked(True)
    dialogo.campo_linea1_personalizada.setText("Lic. Agustina Viavattene")
    dialogo.campo_linea2_personalizada.setText("Equipo Nutri Oeste")

    assert dialogo.valores()["nombre_grabado_personalizado"] == "Lic. Agustina Viavattene\nEquipo Nutri Oeste"


def test_previa_usa_la_misma_fuente_fija_para_texto_corto_y_largo(qtbot):
    """La clienta rechazó el achique automático por placa ("está muy
    grande Lucía Franco. La fuente tendría que ser igual en tamaño, ya
    sea en una linea o en dos lineas"): ahora el tamaño de fuente de la
    vista previa es FIJO, no depende del largo del texto."""
    from app.gui.pantallas.placas import _PanelPlacasOperativas, _PREVIA_FUENTE_PX

    corta = _PanelPlacasOperativas._armar_placa_previa("Lic. Lucía Franco")
    larga = _PanelPlacasOperativas._armar_placa_previa('Lic. Silvina Pugliese\nEquipo "Sol terapias"')
    qtbot.addWidget(corta)
    qtbot.addWidget(larga)
    assert corta.font().pixelSize() == _PREVIA_FUENTE_PX
    assert larga.font().pixelSize() == _PREVIA_FUENTE_PX


def test_previa_calibracion_replica_el_corte_de_linea_del_sistema_fisico_de_la_clienta(qtbot):
    """Referencia exacta que dio la clienta de su sistema físico actual:
    "Lic. Agustina Viavattene" (24 caracteres) entra en una sola línea;
    una letra más la baja a dos líneas. El tamaño fijo de la vista
    previa (_PREVIA_FUENTE_PX) se calibró aparte del de reportlab
    porque Qt sustituye "Calibri" por una fuente propia del sistema que
    mide distinto que Helvetica-BoldOblique."""
    from PySide6.QtGui import QFont, QFontMetrics

    from app.gui.pantallas.placas import _PREVIA_ANCHO_PX, _PREVIA_FUENTE_PX, _PREVIA_MARGEN_HORIZONTAL_PX

    ancho_disponible = _PREVIA_ANCHO_PX - 2 * _PREVIA_MARGEN_HORIZONTAL_PX
    fuente = QFont("Calibri")
    fuente.setBold(True)
    fuente.setItalic(True)
    fuente.setPixelSize(_PREVIA_FUENTE_PX)
    metricas = QFontMetrics(fuente)
    entra = metricas.boundingRect("Lic. Agustina Viavattene").width()
    no_entra = metricas.boundingRect("Lic. Agustina Viavattenee").width()
    assert entra <= ancho_disponible
    assert no_entra > ancho_disponible


def test_previa_placa_replica_el_corte_de_linea_del_sistema_fisico_de_la_clienta(qtbot):
    """Regresión: QLabel.setWordWrap(True) arma un QTextDocument interno
    con un margen propio no configurable, así que cortaba antes de lo
    que sugería QFontMetrics (la misma clase de desajuste que ya se
    había visto con RichText/"<br/>") — "Lic. Agustina Viavattene"
    terminaba en dos líneas en la placa real aunque la calibración de
    _PREVIA_FUENTE_PX decía que entraba en una. Ahora `_armar_placa_previa`
    envuelve el texto a mano (`_envolver_lineas_previa`) con la misma
    métrica que calibró el tamaño de fuente, así que la placa se
    comporta igual que la calibración."""
    from app.gui.pantallas.placas import _PanelPlacasOperativas

    entra = _PanelPlacasOperativas._armar_placa_previa("Lic. Agustina Viavattene")
    no_entra = _PanelPlacasOperativas._armar_placa_previa("Lic. Agustina Viavattenee")
    qtbot.addWidget(entra)
    qtbot.addWidget(no_entra)
    assert "\n" not in entra.text()
    assert "\n" in no_entra.text()


def test_vista_previa_es_proporcional_a_la_placa_real():
    """Pedido de la clienta: la vista previa tiene que ser proporcional a
    lo que se va a imprimir — se calcula desde las mismas constantes que
    usa el PDF (app.pdf.placas_pdf), no valores propios duplicados."""
    from app.gui.pantallas.placas import _PREVIA_ALTO_PX, _PREVIA_ANCHO_PX
    from app.pdf.placas_pdf import ALTO_PLACA, ANCHO_PLACA

    proporcion_pdf = ANCHO_PLACA / ALTO_PLACA
    proporcion_previa = _PREVIA_ANCHO_PX / _PREVIA_ALTO_PX
    assert proporcion_previa == pytest.approx(proporcion_pdf, rel=0.02)


def test_vista_previa_pagina_es_proporcional_a_una_hoja_a4():
    """La "hoja" de la vista previa tiene que tener las proporciones
    reales de una A4, para simular de verdad la hoja que se imprime."""
    from reportlab.lib.pagesizes import A4

    from app.gui.pantallas.placas import _PAGINA_ALTO_PX, _PAGINA_ANCHO_PX

    proporcion_a4 = A4[0] / A4[1]
    proporcion_previa = _PAGINA_ANCHO_PX / _PAGINA_ALTO_PX
    assert proporcion_previa == pytest.approx(proporcion_a4, rel=0.02)


def test_vista_previa_arma_una_pagina_por_cada_22_placas(qtbot, conn):
    from app.gui.pantallas.placas import _PLACAS_POR_PAGINA

    assert _PLACAS_POR_PAGINA == 22
    id_profesional = _crear_profesional(conn)
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)
    for _ in range(25):
        pantalla._agregar_a_impresion()

    # QLabel también hereda de QFrame en Qt, así que se cuentan los hijos
    # directos del layout de páginas en vez de findChildren(QFrame).
    assert pantalla.area_previa.widget().layout().count() == 2


def test_vista_previa_es_escroleable(qtbot, conn):
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla.area_previa, QScrollArea)
    assert pantalla.area_previa.widgetResizable() is True


def test_vista_previa_queda_a_la_derecha_de_la_busqueda(qtbot, conn):
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_imprimir.resize(1400, 700)
    pantalla.panel_imprimir.show()
    qtbot.waitExposed(pantalla.panel_imprimir)
    assert pantalla.lista_impresion.x() < pantalla.area_previa.x()


def test_agregar_y_quitar_de_la_cola_de_impresion(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)

    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)
    pantalla._agregar_a_impresion()
    assert pantalla.lista_impresion.count() == 1

    # A diferencia de v1, permite agregar el mismo profesional más de una
    # vez (ej. dos copias, o una estándar y otra personalizada más tarde).
    pantalla._agregar_a_impresion()
    assert pantalla.lista_impresion.count() == 2

    pantalla.lista_impresion.setCurrentRow(0)
    pantalla._quitar_de_impresion()
    assert pantalla.lista_impresion.count() == 1
    assert len(pantalla._cola_impresion) == 1

    pantalla.lista_impresion.setCurrentRow(0)
    pantalla._quitar_de_impresion()
    assert pantalla.lista_impresion.count() == 0
    assert pantalla._cola_impresion == []


def test_panel_imprimir_no_tiene_controles_de_personalizar(qtbot, conn):
    """Pedido explícito de la clienta: esta solapa ya no pide nada de
    personalización — se maneja íntegramente en la primera solapa."""
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    assert not hasattr(pantalla, "casilla_personalizar_impresion")
    assert not hasattr(pantalla, "campo_linea1_impresion")
    assert not hasattr(pantalla, "campo_linea2_impresion")


def test_agregar_a_impresion_levanta_la_personalizacion_de_la_placa(qtbot, conn):
    """"Agregar a impresión" ya no pide nada — levanta lo que ya se cargó
    en la primera solapa para ese profesional (si tiene alguna placa
    personalizada)."""
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn, apellido="Pugliese", nombre_pila="Silvina")
    asignar_placa(
        conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional,
        es_personalizada=True, nombre_grabado_personalizado='Lic. Silvina Pugliese\nEquipo "Sol terapias"',
    )
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)

    pantalla._agregar_a_impresion()

    assert pantalla.lista_impresion.count() == 1
    assert "(personalizada)" in pantalla.lista_impresion.item(0).text()
    entrada = pantalla._cola_impresion[0]
    assert entrada["linea1"] == "Lic. Silvina Pugliese"
    assert entrada["linea2"] == 'Equipo "Sol terapias"'


def test_agregar_a_impresion_sin_placa_personalizada_usa_el_nombre_estandar(qtbot, conn):
    id_profesional = _crear_profesional(conn, apellido="Difalco", nombre_pila="Sol")
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)

    pantalla._agregar_a_impresion()

    assert pantalla.lista_impresion.count() == 1
    assert "(personalizada)" not in pantalla.lista_impresion.item(0).text()
    entrada = pantalla._cola_impresion[0]
    assert entrada["linea1"] is None
    assert entrada["linea2"] is None


def test_generar_pdf_sin_carpeta_base_no_falla(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)
    pantalla._agregar_a_impresion()

    pantalla._generar_pdf_impresion()  # solo debe avisar, no lanzar


def test_generar_pdf_genera_archivo_y_vacia_la_cola(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    id_profesional = _crear_profesional(conn)
    pantalla = _PanelPlacasOperativas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)
    pantalla._agregar_a_impresion()

    pantalla._generar_pdf_impresion()

    generados = list((tmp_path / "Archivos varios" / "Placas").iterdir())
    assert len(generados) == 1
    assert generados[0].name.startswith("Placas para imprimir")
    assert pantalla.lista_impresion.count() == 0
    assert pantalla._cola_impresion == []
