import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.oferta import _PanelOferta, _DialogoPrevisualizacion
from app.gui.widgets.selector_profesional import _ProxyBusquedaSinAcentos
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


def test_es_un_panel_solapa(qtbot, conn):
    """Reordenamiento de formularios: dejó de ser una pantalla propia con
    su propio título/QTabWidget — ahora es la solapa "Oferta de
    consultorios" de "Disponibilidad" (ver disponibilidad.py)."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.objectName() == "panelSolapa"


def test_combo_profesional_es_buscable_por_codigo_o_nombre(qtbot, conn, profesional_y_consultorio):
    """Confirmado por la clienta: el selector de profesional buscable
    corre en todos los formularios del sistema, Oferta incluida — con el
    mismo formato canónico que el resto (antes mostraba "Apellido, Nombre")."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    completador = pantalla.combo_profesional.completer()
    assert isinstance(completador.model(), _ProxyBusquedaSinAcentos)
    assert pantalla.combo_profesional.itemText(0) == "Lic. Virginia Lo Veci"


def test_fechas_se_muestran_en_formato_dd_mm_aaaa(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.campo_fecha_desde.displayFormat() == "ddd dd-MM-yyyy"
    assert pantalla.campo_fecha_hasta.displayFormat() == "ddd dd-MM-yyyy"


def test_fecha_hasta_solo_habilitada_para_aislada(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    assert not pantalla.campo_fecha_hasta.isEnabled()  # Regular es el tipo por defecto

    indice_aislada = pantalla.combo_tipo.findData("Aislada")
    pantalla.combo_tipo.setCurrentIndex(indice_aislada)
    assert pantalla.campo_fecha_hasta.isEnabled()


def test_fecha_muestra_el_dia_de_la_semana_abreviado(qtbot, conn, profesional_y_consultorio):
    from PySide6.QtCore import QDate

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.campo_fecha_desde.setDate(QDate(2026, 9, 11))  # viernes
    assert pantalla.campo_fecha_desde.text().startswith("vie")

    pantalla.campo_fecha_desde.setDate(QDate(2026, 9, 9))  # miércoles
    assert pantalla.campo_fecha_desde.text().startswith("mié")


def test_fechas_desde_hasta_en_la_misma_fila(qtbot, conn, profesional_y_consultorio):
    """"Desde"/"Hasta" (esta última, antes "Hasta (solo Aislada)") van
    en la misma fila (pedido explícito de la clienta) — confirmado por
    posición vertical, ya que los dos `QDateEdit` quedan a la misma
    altura dentro del mismo `QHBoxLayout`."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    assert pantalla.campo_fecha_desde.y() == pantalla.campo_fecha_hasta.y()
    assert pantalla.campo_fecha_desde.x() < pantalla.campo_fecha_hasta.x()


def test_horario_muestra_formato_hs(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.spin_desde.setValue(9)
    assert pantalla.spin_desde.text() == "9:00hs"

    pantalla.spin_hasta.setValue(12.5)
    assert pantalla.spin_hasta.text() == "12:30hs"


def test_localidad_edificio_unidad_arrancan_en_todas(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla._filtro_localidad._boton.text() == "Todas las localidades"
    assert pantalla._filtro_edificio._boton.text() == "Todos los edificios"
    assert pantalla._filtro_unidad._boton.text() == "Todas las unidades"
    # sin nada tildado a mano, la búsqueda no se restringe (lista completa)
    assert len(pantalla._ids_unidad_seleccionadas()) == 1


def test_elegir_una_localidad_acota_las_opciones_de_edificio(qtbot, conn, profesional_y_consultorio):
    id_prof, id_edificio = profesional_y_consultorio
    id_recoleta = obtener_repositorio(conn, "Localidad").crear(Localidad="Recoleta")
    conn.execute("UPDATE Edificio SET IdLocalidad = ? WHERE IdEdificio = ?", (id_recoleta, id_edificio))
    id_palermo = obtener_repositorio(conn, "Localidad").crear(Localidad="Palermo")
    id_edificio_2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2", IdLocalidad=id_palermo)
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_2, Departamento="2do B")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    conn.commit()

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._cargar_localidades()  # repuebla ya con los dos edificios/localidades de arriba
    assert pantalla.lista_localidad.count() == 3  # "Todas" + Recoleta + Palermo

    indice_recoleta = next(
        i for i in range(pantalla.lista_localidad.count())
        if pantalla.lista_localidad.item(i).text() == "Recoleta"
    )
    pantalla.lista_localidad.clearSelection()
    pantalla.lista_localidad.item(indice_recoleta).setSelected(True)

    assert pantalla.lista_edificio.count() == 2  # "Todos" + solo el de Recoleta


def test_elegir_un_edificio_puntual_acota_las_unidades_de_la_busqueda(qtbot, conn, profesional_y_consultorio):
    id_prof, id_edificio = profesional_y_consultorio
    id_edificio_2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2")
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_2, Departamento="2do B")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    conn.commit()

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._cargar_localidades()
    assert len(pantalla._ids_unidad_seleccionadas()) == 2  # "Todas las unidades": las dos

    pantalla.lista_edificio.clearSelection()
    for i in range(pantalla.lista_edificio.count()):
        if pantalla.lista_edificio.item(i).text() == "Ramos 1":
            pantalla.lista_edificio.item(i).setSelected(True)

    assert pantalla._ids_unidad_seleccionadas() == [
        pantalla.lista_unidad.item(1).data(Qt.ItemDataRole.UserRole)
    ]


def test_tamano_arranca_deshabilitado_y_se_habilita_con_el_check(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    assert not pantalla.combo_tamano.isEnabled()
    assert pantalla.combo_tamano.currentText() == "Cualquier tamaño"

    pantalla.casilla_tamano.setChecked(True)
    assert pantalla.combo_tamano.isEnabled()

    indice_grande = pantalla.combo_tamano.findData("Grande")
    pantalla.combo_tamano.setCurrentIndex(indice_grande)
    busqueda = pantalla._armar_busqueda_actual()
    assert busqueda is None  # sin días marcados

    pantalla._checks_dia["Lunes"].setChecked(True)
    busqueda = pantalla._armar_busqueda_actual()
    assert busqueda.tamano == "Grande"


def test_tamano_desmarcado_no_filtra_por_tamano(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    busqueda = pantalla._armar_busqueda_actual()
    assert busqueda.tamano is None


def test_hay_tres_botones_y_nueva_busqueda_es_la_principal(qtbot, conn, profesional_y_consultorio):
    from PySide6.QtWidgets import QPushButton

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    botones = {b.text(): b for b in pantalla.findChildren(QPushButton) if b.text() in (
        "Generar PDF", "Generar texto WhatsApp", "Nueva búsqueda",
    )}
    assert set(botones) == {"Generar PDF", "Generar texto WhatsApp", "Nueva búsqueda"}
    assert botones["Generar PDF"].objectName() == "botonSecundario"
    assert botones["Generar texto WhatsApp"].objectName() == "botonSecundario"
    assert botones["Nueva búsqueda"].objectName() == "botonPrimario"


def test_nueva_busqueda_resetea_el_formulario_y_enfoca_profesional(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla.casilla_ventana.setChecked(True)
    pantalla.casilla_tamano.setChecked(True)
    pantalla._agregar_franja()  # deja además una franja cargada

    pantalla._nueva_busqueda()

    assert pantalla._dias_seleccionados() == []
    assert not pantalla.casilla_ventana.isChecked()
    assert not pantalla.casilla_tamano.isChecked()
    assert pantalla._franjas == []
    assert pantalla.lista_franjas.count() == 0
    qtbot.waitUntil(lambda: pantalla.combo_profesional.hasFocus())


def test_dias_son_checkboxes_de_lunes_a_sabado_en_grilla_compacta(qtbot, conn, profesional_y_consultorio):
    """De acuerdo a los parámetros del sistema (reservas de lunes a
    sábado, sin domingo — mismo criterio que Reservas y Lista de
    espera), y en checkboxes horizontales en vez de una lista vertical
    larga, para que sean más legibles."""
    from PySide6.QtWidgets import QGridLayout

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    assert list(pantalla._checks_dia.keys()) == ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
    assert all(check.isChecked() is False for check in pantalla._checks_dia.values())

    grid = pantalla._checks_dia["Lunes"].parentWidget().layout()
    assert isinstance(grid, QGridLayout)
    # 3 arriba y 3 abajo (6 días -> ceil(6/2) = 3 columnas)
    assert grid.itemAtPosition(0, 2) is not None
    assert grid.itemAtPosition(1, 0) is not None
    assert grid.itemAtPosition(1, 2) is not None


def test_grilla_embebida_sin_titulo(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: se saca el título "Grilla
    semanal" del panel de Filtros — mismo criterio que Reservas."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.grilla._panel_filtros.title() == ""


def test_foco_inicial_queda_en_profesional(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.combo_profesional.hasFocus())


def test_lista_franjas_crece_hasta_el_pie_y_es_scroleable(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: prefiere que los cuadros/tablas
    sean escroleables en vez de la pantalla entera — "Franjas agregadas
    a esta búsqueda" pasa de un alto máximo fijo (90px) a crecer con
    `stretch=1` hasta el pie de la columna, sin perder el scroll propio
    de `QListWidget` para cuando hay más franjas de las que entran."""
    from PySide6.QtCore import Qt as _Qt

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    form = pantalla.combo_profesional.parentWidget().layout()
    indice = form.indexOf(pantalla.lista_franjas)
    assert form.stretch(indice) == 1
    assert pantalla.lista_franjas.maximumHeight() > 90

    for i in range(20):
        pantalla._checks_dia["Lunes"].setChecked(True)
        pantalla.spin_desde.setValue(9)
        pantalla.spin_hasta.setValue(10 + i % 10 * 0.1 + 1)
        pantalla._agregar_franja()

    assert pantalla.lista_franjas.count() == 20
    assert pantalla.lista_franjas.verticalScrollBarPolicy() != _Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_grilla_operativa_embebida_sigue_el_tipo_de_busqueda(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.grilla.combo_modo.currentData() == "regular"
    assert not pantalla.grilla.combo_modo.isEnabled()

    indice_aislada = pantalla.combo_tipo.findData("Aislada")
    pantalla.combo_tipo.setCurrentIndex(indice_aislada)
    assert pantalla.grilla.combo_modo.currentData() == "aislada"


def test_generar_pdf_guarda_en_archivos_varios_oferta(qtbot, conn, tmp_path, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes

    pantalla._generar_pdf()

    generados = list((tmp_path / "Archivos varios" / "Oferta").iterdir())
    assert len(generados) == 1
    assert generados[0].name.startswith("Oferta de consultorios - Lic. Virginia Lo Veci")


def test_generar_texto_muestra_dialogo_con_el_texto(qtbot, conn, tmp_path, monkeypatch, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes

    capturado = {}

    def _dialogo_falso(texto, parent=None):
        capturado["texto"] = texto
        return _FalsoDialogo()

    monkeypatch.setattr("app.gui.pantallas.oferta._DialogoTexto", _dialogo_falso)

    pantalla._generar_texto()

    assert "Búsqueda requerida por el profesional" in capturado["texto"]


def test_sin_dias_no_genera_archivo(qtbot, conn, tmp_path, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._generar_pdf()
    assert not (tmp_path / "Archivos varios" / "Oferta").exists()


def test_agregar_franja_la_suma_a_la_lista_y_limpia_dias(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes

    pantalla._agregar_franja()

    assert len(pantalla._franjas) == 1
    assert pantalla.lista_franjas.count() == 1
    assert pantalla._dias_seleccionados() == []  # se limpia para cargar la próxima franja


def test_agregar_franja_sin_dias_no_suma_nada(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._agregar_franja()
    assert pantalla._franjas == []
    assert pantalla.lista_franjas.count() == 0


def test_quitar_franja_seleccionada(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes
    pantalla._agregar_franja()
    pantalla.lista_franjas.setCurrentRow(0)

    pantalla._quitar_franja_seleccionada()

    assert pantalla._franjas == []
    assert pantalla.lista_franjas.count() == 0


def test_generar_con_dos_franjas_genera_un_solo_documento(qtbot, conn, tmp_path, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)

    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes
    pantalla._agregar_franja()
    pantalla.spin_desde.setValue(15)
    pantalla.spin_hasta.setValue(17)
    pantalla._checks_dia["Viernes"].setChecked(True)  # Viernes
    pantalla._agregar_franja()
    assert pantalla.lista_franjas.count() == 2

    pantalla._generar_pdf()

    generados = list((tmp_path / "Archivos varios" / "Oferta").iterdir())
    assert len(generados) == 1
    # se limpia la lista de franjas para la próxima búsqueda
    assert pantalla._franjas == []
    assert pantalla.lista_franjas.count() == 0


def test_cancelar_previsualizacion_no_genera_archivo(qtbot, conn, tmp_path, monkeypatch, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    monkeypatch.setattr(_DialogoPrevisualizacion, "exec", lambda self: QDialog.DialogCode.Rejected)
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes

    pantalla._generar_pdf()

    assert not (tmp_path / "Archivos varios" / "Oferta").exists()


def test_previsualizacion_muestra_una_fila_por_opcion(qtbot, conn, monkeypatch, profesional_y_consultorio):
    capturado = {}

    def _exec_capturando(self):
        capturado["filas"] = list(self._filas)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoPrevisualizacion, "exec", _exec_capturando)
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes

    pantalla._generar_pdf()

    assert len(capturado["filas"]) == 1
    assert "consultorio 1" in capturado["filas"][0][3]


def test_destildar_una_opcion_en_la_previsualizacion_la_excluye_del_documento(
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
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes

    capturado = {}

    def _dialogo_falso(texto, parent=None):
        capturado["texto"] = texto
        return _FalsoDialogo()

    monkeypatch.setattr("app.gui.pantallas.oferta._DialogoTexto", _dialogo_falso)

    pantalla._generar_texto()

    assert "Sin disponibilidad para esta búsqueda" in capturado["texto"]


def test_sin_alternativas_la_previsualizacion_permite_generar_igual(qtbot, conn, tmp_path, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes
    pantalla.casilla_camilla.setChecked(True)  # el consultorio de la fixture no es apto camilla: sin cobertura

    pantalla._generar_pdf()

    generados = list((tmp_path / "Archivos varios" / "Oferta").iterdir())
    assert len(generados) == 1


def test_paquete_y_con_franja_sin_cobertura_no_muestra_nada_en_la_previsualizacion(
    qtbot, conn, monkeypatch, profesional_y_consultorio,
):
    capturado = {}

    def _exec_capturando(self):
        capturado["filas"] = list(self._filas)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoPrevisualizacion, "exec", _exec_capturando)
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes: con cobertura
    pantalla.combo_union_franja.setCurrentIndex(1)  # Y con la próxima
    pantalla._agregar_franja()

    pantalla._checks_dia["Martes"].setChecked(True)  # Martes
    pantalla.casilla_camilla.setChecked(True)  # el consultorio de la fixture no es apto camilla: sin cobertura
    pantalla._agregar_franja()

    pantalla._generar_pdf()

    assert capturado["filas"] == []


class _FalsoDialogo:
    def exec(self):
        return None


def test_contenido_dentro_del_scroll_tiene_fondo_claro(qtbot, conn, profesional_y_consultorio):
    """Mismo bug ya documentado en Reservas/Llaves: el widget que se pasa
    a `scroll.setWidget(...)` necesita su propio `objectName="panelSolapa"`
    — sin él, Qt le pinta el gris por defecto al panel del formulario
    aunque el widget de más afuera (`self`) sí lo tenga."""
    from PySide6.QtWidgets import QWidget

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    descendientes_panel_solapa = [
        w for w in pantalla.findChildren(QWidget) if w.objectName() == "panelSolapa"
    ]
    assert len(descendientes_panel_solapa) == 1  # "contenido", el del scroll (self ya tiene el suyo aparte)


def test_columna_del_formulario_mas_angosta_que_antes(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: la primera columna (el formulario
    de búsqueda) tiene que quedar más angosta, y el ancho liberado se
    reparte entre el panel de Filtros y la grilla de la derecha — mismo
    criterio que la columna del formulario en Reservas. Antes de esta
    ronda la columna medía 690px de sizeHint (dominada por la fila
    horizontal de "Generar PDF"/"Generar texto WhatsApp"/"Nueva
    búsqueda", 660px de tres botones de 220px cada uno); esos tres
    botones se mudaron al panel de Filtros de la grilla (ver más abajo),
    así que ya no aportan nada al ancho de esta columna."""
    from PySide6.QtWidgets import QSplitter

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    splitter = pantalla.findChildren(QSplitter)[0]
    panel_form = splitter.widget(0)
    assert panel_form.sizeHint().width() < 500  # bien por debajo de los 690px originales
    assert pantalla.grilla._panel_filtros.maximumWidth() > 260  # más ancho que el default de la grilla


def test_filtros_dias_y_referencias_como_en_reservas(qtbot, conn, profesional_y_consultorio):
    """La grilla embebida (referencia visual "Grilla semanal") pasa a
    manejar filtros/días/referencias con el mismo criterio compacto que
    usa Reservas regulares/aisladas — antes se llamaba `mostrar_leyenda_
    colores()` sin `compacta=True` y nunca se llamaba `agrupar_dias_en_
    pares()`."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    grilla = pantalla.grilla
    # Días de la semana de a pares (2 columnas), no en una lista vertical.
    from PySide6.QtWidgets import QGridLayout
    assert isinstance(grilla._contenedor_dias.layout(), QGridLayout)
    # Referencias de colores compactas (2 columnas, muestra más chica).
    assert grilla._leyenda_colores._columnas == 2
    assert grilla._leyenda_colores._tamano_muestra == (28, 16)
    assert not grilla._leyenda_colores.isHidden()


def test_leyenda_cambia_de_referencias_segun_el_tipo_de_busqueda(qtbot, conn, profesional_y_consultorio):
    """Elegir "Regular"/"Aislada" en "Tipo de búsqueda" tiene que cambiar
    tanto el modo de la grilla como el set de referencias que muestra la
    leyenda (8 para regular, 6 para aislada) — ya funcionaba antes de esta
    ronda vía la señal de `combo_modo`, se deja cubierto con un test."""
    from app.gui.widgets.grilla_operativa import REFERENCIAS_AISLADA, REFERENCIAS_REGULAR
    from app.negocio.oferta_busqueda import TIPO_AISLADA, TIPO_REGULAR

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_tipo.setCurrentIndex(pantalla.combo_tipo.findData(TIPO_REGULAR))
    assert pantalla.grilla._leyenda_colores._layout.count() == len(REFERENCIAS_REGULAR) * 2

    pantalla.combo_tipo.setCurrentIndex(pantalla.combo_tipo.findData(TIPO_AISLADA))
    assert pantalla.grilla._leyenda_colores._layout.count() == len(REFERENCIAS_AISLADA) * 2


def test_agregar_y_quitar_franja_en_la_misma_fila(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: "Agregar franja a la búsqueda" y
    "Quitar franja seleccionada" van a la par, a la misma altura."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    assert pantalla.boton_agregar_franja.y() == pantalla.boton_quitar_franja.y()
    assert pantalla.boton_agregar_franja.x() < pantalla.boton_quitar_franja.x()


def test_etiqueta_franjas_agregadas_sin_texto_explicativo(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: el título de la lista de franjas
    queda solo con "Franjas agregadas a esta búsqueda", sin la aclaración
    entre paréntesis que tenía antes."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    etiquetas = [lbl.text() for lbl in pantalla.findChildren(QLabel)]
    assert "Franjas agregadas a esta búsqueda" in etiquetas
    assert not any("si no agregás ninguna" in texto for texto in etiquetas)


def test_caracteristicas_pedidas_en_grilla_de_pares_con_placard(qtbot, conn, profesional_y_consultorio):
    """"Con ventana"/"Apto camilla" en una fila, "Con sillones"/"Con
    placard" (checkbox nuevo) en la siguiente, y "Tamaño"/"Valor máximo
    por hora regular" cada uno junto a su selector — pedido explícito de
    la clienta sobre el orden exacto de esta sección."""
    from PySide6.QtWidgets import QGridLayout

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla.casilla_placard, QCheckBox)
    assert pantalla.casilla_placard.text() == "Con placard"

    grid = pantalla._grid_caracteristicas
    assert isinstance(grid, QGridLayout)
    assert grid.indexOf(pantalla.casilla_ventana) == grid.indexOf(pantalla.casilla_camilla) - 1
    assert grid.getItemPosition(grid.indexOf(pantalla.casilla_ventana))[:2] == (0, 0)
    assert grid.getItemPosition(grid.indexOf(pantalla.casilla_camilla))[:2] == (0, 1)
    assert grid.getItemPosition(grid.indexOf(pantalla.casilla_sillones))[:2] == (1, 0)
    assert grid.getItemPosition(grid.indexOf(pantalla.casilla_placard))[:2] == (1, 1)
    assert grid.getItemPosition(grid.indexOf(pantalla.casilla_tamano))[:2] == (2, 0)
    assert grid.getItemPosition(grid.indexOf(pantalla.combo_tamano))[:2] == (2, 1)
    assert grid.getItemPosition(grid.indexOf(pantalla.casilla_valor_maximo))[:2] == (3, 0)
    assert grid.getItemPosition(grid.indexOf(pantalla.spin_valor_maximo))[:2] == (3, 1)


def test_placard_se_incluye_en_la_busqueda_armada(qtbot, conn, profesional_y_consultorio):
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla.casilla_placard.setChecked(True)
    busqueda = pantalla._armar_busqueda_actual()
    assert busqueda.placard is True

    pantalla._nueva_busqueda()
    assert pantalla.casilla_placard.isChecked() is False


def test_botones_de_accion_viven_en_el_panel_de_filtros_de_la_grilla(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: "Generar PDF"/"Generar texto
    WhatsApp"/"Nueva búsqueda" se mudan al panel de Filtros de la grilla,
    debajo de "Referencias de colores" — ya no viven al pie del
    formulario de búsqueda."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    panel_filtros = pantalla.grilla._panel_filtros
    assert pantalla.boton_pdf.parentWidget() is panel_filtros
    assert pantalla.boton_texto.parentWidget() is panel_filtros
    assert pantalla.boton_nueva.parentWidget() is panel_filtros

    layout = panel_filtros.layout()
    indice_leyenda = layout.indexOf(pantalla.grilla._leyenda_colores)
    indice_pdf = layout.indexOf(pantalla.boton_pdf)
    indice_texto = layout.indexOf(pantalla.boton_texto)
    indice_nueva = layout.indexOf(pantalla.boton_nueva)
    assert indice_leyenda < indice_pdf < indice_texto < indice_nueva


def test_etiqueta_hasta_sin_aclaracion_de_aislada(qtbot, conn, profesional_y_consultorio):
    """"Hasta (solo Aislada)" pasa a "Hasta" — pedido explícito de la
    clienta, el comportamiento no cambia (sigue deshabilitado en modo
    Regular, ver `_al_cambiar_tipo`)."""
    from app.negocio.oferta_busqueda import TIPO_AISLADA, TIPO_REGULAR

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    etiquetas = [lbl.text() for lbl in pantalla.findChildren(QLabel)]
    assert "Hasta" in etiquetas
    assert "Hasta (solo Aislada)" not in etiquetas

    pantalla.combo_tipo.setCurrentIndex(pantalla.combo_tipo.findData(TIPO_REGULAR))
    assert not pantalla.campo_fecha_hasta.isEnabled()
    pantalla.combo_tipo.setCurrentIndex(pantalla.combo_tipo.findData(TIPO_AISLADA))
    assert pantalla.campo_fecha_hasta.isEnabled()


def test_profesional_alineado_con_localidad_de_la_grilla(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: "Localidad" (primer filtro del
    panel de Filtros de la grilla, sin título desde este cambio) tiene
    que arrancar a la misma altura que "Profesional" (primer campo de
    la columna del formulario)."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    etiqueta_profesional = next(
        lbl for lbl in pantalla.combo_profesional.parentWidget().findChildren(QLabel) if lbl.text() == "Profesional"
    )
    etiqueta_localidad = next(
        lbl for lbl in pantalla.grilla._panel_filtros.findChildren(QLabel) if lbl.text() == "Localidad"
    )
    assert etiqueta_profesional.mapToGlobal(etiqueta_profesional.rect().topLeft()).y() == (
        etiqueta_localidad.mapToGlobal(etiqueta_localidad.rect().topLeft()).y()
    )


def test_detalle_pegado_debajo_de_la_grilla_sin_relleno(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: "Detalle" y su cuadro suben hasta
    donde termina la grilla, en vez de quedar más abajo con relleno
    vacío en la tabla — mismo método opt-in que ya usa Reservas
    regulares (`dar_stretch_a_detalle`, le saca el stretch a la tabla y
    se lo pasa al cuadro "Detalle")."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    layout = pantalla.grilla._layout_grilla
    assert layout.stretch(layout.indexOf(pantalla.grilla.tabla)) == 0
    assert layout.stretch(layout.indexOf(pantalla.grilla.texto_detalle)) == 1


def test_panel_filtros_de_la_grilla_mas_ancho(qtbot, conn, profesional_y_consultorio):
    """Ancho liberado al acortar "Hasta (solo Aislada)" a "Hasta" —
    pedido explícito de la clienta, "dáselo a la segunda columna"."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.grilla._panel_filtros.maximumWidth() == 355
