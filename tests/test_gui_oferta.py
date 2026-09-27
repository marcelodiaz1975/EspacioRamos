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


def test_dias_con_domingo_agregado_quedan_4_y_3(qtbot, conn, monkeypatch, profesional_y_consultorio):
    """Confirmación pedida por la clienta: si el día domingo se sumara a
    `_DIAS_BUSQUEDA` (hoy son 6 días fijos, Lunes a Sábado — ver el test
    de arriba), la grilla de 2 filas quedaría con Lunes/Martes/Miércoles/
    Jueves arriba y Viernes/Sábado/Domingo abajo — el mismo algoritmo
    `math.ceil(len(dias)/2)` columnas que ya arma la grilla de 6 días,
    sin necesitar ningún cambio de código. `_DIAS_BUSQUEDA` sigue siendo
    hoy una constante fija de 6 días (no depende de ningún parámetro de
    sistema pese al comentario), este test monkeypatchea la lista para
    dejar la confirmación fijada como regresión."""
    import app.gui.pantallas.oferta as oferta_mod
    from PySide6.QtWidgets import QGridLayout

    monkeypatch.setattr(
        oferta_mod, "_DIAS_BUSQUEDA",
        ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
    )
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)

    grid = pantalla._checks_dia["Lunes"].parentWidget().layout()
    assert isinstance(grid, QGridLayout)
    # 4 columnas (ceil(7/2)): fila 0 = Lunes..Jueves, fila 1 = Viernes/Sábado/Domingo.
    fila_0 = [grid.itemAtPosition(0, c).widget().text() for c in range(4)]
    fila_1 = [grid.itemAtPosition(1, c).widget().text() for c in range(3)]
    assert fila_0 == ["Lunes", "Martes", "Miércoles", "Jueves"]
    assert fila_1 == ["Viernes", "Sábado", "Domingo"]
    assert grid.itemAtPosition(1, 3) is None  # nada más en esa fila


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
    """Pedido explícito de la clienta (mantenido en la ronda que le dio a
    "Franjas agregadas a esta búsqueda" su propia columna, la segunda):
    prefiere que los cuadros/tablas sean escroleables en vez de la
    pantalla entera — la lista crece con `stretch=1` hasta el pie de ESA
    columna (ya no la del formulario), sin perder el scroll propio de
    `QListWidget` para cuando hay más franjas de las que entran."""
    from PySide6.QtCore import Qt as _Qt

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    columna_franjas = pantalla.lista_franjas.parentWidget().layout()
    indice = columna_franjas.indexOf(pantalla.lista_franjas)
    assert columna_franjas.stretch(indice) == 1
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


def test_sin_etiqueta_visualizacion_en_la_grilla(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: el combo "Visualización" (Reservas
    regulares/aisladas, siempre deshabilitado acá — lo maneja "Tipo de
    búsqueda", ver `_al_cambiar_tipo`) se queda solo, sin la etiqueta al
    lado — esa fila era la que fijaba el ancho mínimo de la cuarta
    columna, más ancho que lo que la tabla en sí necesita (que ya
    scrollea sola), forzando scroll horizontal de toda la pantalla."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.grilla._etiqueta_visualizacion.isVisible() is False


def test_formulario_no_escrolea_horizontal_solo_la_grilla(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: "no quiero que sea escroleable en
    horizontal los formularios en general, solo la grilla" — el
    `QScrollArea` externo de la pantalla no debería necesitar scroll
    horizontal (las primeras tres columnas más el ancho mínimo de la
    cuarta tienen que entrar en el ancho disponible), dejando cualquier
    desborde de días de la semana a cargo del scroll propio de la tabla
    (`self.grilla.tabla`, que ya lo tenía de antes)."""
    from PySide6.QtWidgets import QScrollArea

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    pantalla.resize(1260, 850)  # ancho de referencia usado en las capturas (1500 - sidebar)
    qtbot.waitExposed(pantalla)

    scroll = pantalla.findChildren(QScrollArea)[0]
    assert scroll.horizontalScrollBar().maximum() == 0


def test_columna_del_formulario_mas_angosta_que_antes(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta, ronda "cuatro columnas": los
    botones "Agregar franja"/"Quitar franja" pasan a dos líneas de texto,
    angostando la primera columna (el formulario de búsqueda) todavía
    más — antes de esa ronda medía 690px de sizeHint (con los tres
    botones "Generar PDF"/"Generar texto WhatsApp"/"Nueva búsqueda" en
    una fila horizontal, y "Franjas agregadas" en la misma columna);
    ahora esos tres botones y la lista de franjas viven en su propia
    columna (la segunda, ver más abajo), y los dos botones que quedan acá
    ya no fuerzan tanto ancho al ser de dos líneas."""
    from PySide6.QtWidgets import QSplitter

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    splitter = pantalla.findChildren(QSplitter)[0]
    panel_form = splitter.widget(0)
    assert panel_form.sizeHint().width() < 500  # bien por debajo de los 690px originales
    assert pantalla.boton_agregar_franja.text() == "Agregar franja\na la búsqueda"
    assert pantalla.boton_quitar_franja.text() == "Quitar franja\nseleccionada"


def test_filtros_dias_y_referencias_en_una_sola_linea(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta, ronda "cuatro columnas": los
    filtros (días) y las referencias de colores de la grilla embebida
    vuelven a mostrarse en una sola línea cada uno (no de a pares/
    compactado a 2 columnas, como se había probado en la ronda
    anterior) — la columna de Filtros pasa a ser la tercera columna de
    esta pantalla, con la leyenda ajustada en tamaño para llegar al pie."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    grilla = pantalla.grilla
    # Días de la semana en una lista vertical, no de a pares.
    from PySide6.QtWidgets import QVBoxLayout
    assert isinstance(grilla._contenedor_dias.layout(), QVBoxLayout)
    # Referencias de colores en una sola columna (no compactas).
    assert grilla._leyenda_colores._columnas == 1
    assert not grilla._leyenda_colores.isHidden()


def test_filtro_dia_a_pares_con_domingo_configurado(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: si el sistema tiene el domingo
    sumado a "Días de grilla" (`Configuracion.DiasGrilla`, editable
    desde Configuración general), el filtro de "Día de la semana" de la
    grilla embebida (columna 3) pasa a 2 columnas — a diferencia del
    caso normal (6 días, ver el test de arriba, que sigue en una sola
    columna) — con el domingo solo en su propia fila al final, y la
    leyenda de colores se agranda un poco más para seguir llegando al
    pie de la columna con menos alto ocupado por el filtro de días."""
    import json
    from PySide6.QtWidgets import QGridLayout

    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    conn.execute("UPDATE Configuracion SET DiasGrilla = ? WHERE IdConfiguracion = 1", (json.dumps(dias, ensure_ascii=False),))
    conn.commit()

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)

    assert pantalla._domingo_en_filtro_dia is True
    grid = pantalla.grilla._contenedor_dias.layout()
    assert isinstance(grid, QGridLayout)
    assert grid.itemAtPosition(3, 0).widget().text() == "Domingo"
    assert grid.itemAtPosition(3, 1) is None  # solo en su columna, nada al lado


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


def test_botones_de_accion_viven_al_pie_de_la_columna_de_franjas(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta, ronda "cuatro columnas": "Generar
    PDF"/"Generar texto WhatsApp"/"Nueva búsqueda" se reubican al pie de
    la segunda columna (la de "Franjas agregadas a esta búsqueda") —
    dejan de vivir en el panel de Filtros de la grilla, donde los había
    puesto la ronda anterior."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    panel_franjas = pantalla.lista_franjas.parentWidget()
    assert pantalla.boton_pdf.parentWidget() is panel_franjas
    assert pantalla.boton_texto.parentWidget() is panel_franjas
    assert pantalla.boton_nueva.parentWidget() is panel_franjas

    layout = panel_franjas.layout()
    indice_lista = layout.indexOf(pantalla.lista_franjas)
    indice_pdf = layout.indexOf(pantalla.boton_pdf)
    indice_texto = layout.indexOf(pantalla.boton_texto)
    indice_nueva = layout.indexOf(pantalla.boton_nueva)
    assert indice_lista < indice_pdf < indice_texto < indice_nueva

    # Ya no viven en el panel de Filtros de la grilla.
    panel_filtros = pantalla.grilla._panel_filtros
    assert pantalla.boton_pdf.parentWidget() is not panel_filtros


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


def test_grilla_nunca_se_recorta_con_mas_horarios_detalle_cede_espacio(
    qtbot, conn, profesional_y_consultorio,
):
    """Pedido explícito de la clienta: si se agregan más horarios a la
    grilla (una franja horaria más amplia en "Configuración general"),
    siempre tiene que verse completa — el espacio que necesite de más lo
    cede el cuadro "Detalle" (gracias a `dar_stretch_a_detalle`, ver el
    test de arriba: la tabla queda con `stretch=0`, fija a su alto
    natural, y "Detalle" es el único que cede)."""
    conn.execute("UPDATE Configuracion SET HoraInicioGrilla = 0, HoraFinGrilla = 24, FraccionGrilla = 0.5 WHERE IdConfiguracion = 1")
    conn.commit()

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    pantalla.resize(1260, 850)
    qtbot.waitExposed(pantalla)

    assert pantalla.grilla.tabla.rowCount() > 20  # grilla bien más larga que la de siempre (6 días × ~4hs)
    # La tabla se ve completa (a lo sumo un resto ínfimo, artefacto de
    # medición offscreen ya documentado en otras pantallas de este
    # sistema — nunca una tabla realmente recortada).
    assert pantalla.grilla.tabla.verticalScrollBar().maximum() <= 2


def test_grilla_reserva_alto_para_que_el_scroll_horizontal_no_tape_la_ultima_fila(
    qtbot, conn, profesional_y_consultorio,
):
    """Pedido explícito de la clienta: "dale más largo para que el scrol
    horizontal no tape lo último que se tendría que ver de la grilla, en
    este caso el horario de las 21hs con su línea inferior incluída".
    `reservar_alto_scroll_horizontal()` (opt-in, solo Oferta) suma al
    alto mínimo de la tabla el espacio de la barra de scroll horizontal
    — sin esto, el viewport de la tabla mide justo la suma de sus filas
    y la barra, al aparecer, le come ese mismo alto al viewport, tapando
    la última fila."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    pantalla.resize(1260, 850)
    qtbot.waitExposed(pantalla)
    qtbot.wait(50)

    assert pantalla.grilla._reservar_alto_scroll_horizontal is True
    tabla = pantalla.grilla.tabla
    # La grilla necesita scroll horizontal (columna angosta, seis días de
    # la semana) — confirma que el escenario que motivó el pedido está
    # realmente presente en este test, no solo la reserva de alto.
    assert tabla.horizontalScrollBar().maximum() > 0
    suma_filas = sum(tabla.rowHeight(i) for i in range(tabla.rowCount()))
    # El borde inferior de la última fila tiene que caer DENTRO del
    # viewport visible — nunca tapado por la barra de scroll horizontal.
    assert tabla.viewport().height() >= suma_filas


def test_panel_filtros_de_la_grilla_ancho_fijo(qtbot, conn, profesional_y_consultorio):
    """Ronda "cuatro columnas": el panel de Filtros de la grilla (ahora
    la tercera columna de la pantalla) pasa a tener un ancho FIJO
    (mínimo = máximo) en vez de solo un tope — sin esto, sin ningún
    stretch propio en el `QHBoxLayout` interno de la grilla, se quedaba
    en su ancho natural (~190px, mucho menos que el tope) y no le
    quedaba lugar de verdad a "Referencias de colores"."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    panel_filtros = pantalla.grilla._panel_filtros
    assert panel_filtros.minimumWidth() == panel_filtros.maximumWidth()
    assert panel_filtros.minimumWidth() > 200


def test_pantalla_tiene_cuatro_columnas(qtbot, conn, profesional_y_consultorio):
    """Ronda "cuatro columnas", pedido explícito de la clienta: 1)
    formulario de búsqueda, 2) "Franjas agregadas a esta búsqueda" + los
    tres botones de acción al pie, 3) Filtros de la grilla (Localidad/
    Edificio/Unidad/Día/Profesional/Referencias), 4) la grilla
    escroleable + "Detalle". Las columnas 3 y 4 siguen viviendo dentro de
    un solo widget de splitter (`self.grilla`, que ya las divide
    internamente en Filtros | grilla) — separarlas en dos panes de
    `QSplitter` de verdad hubiera significado desarmar `GrillaOperativaWidget`
    sin necesidad, cuando alcanza con que cada mitad interna quede bien
    dimensionada."""
    from PySide6.QtWidgets import QSplitter

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    splitter = pantalla.findChildren(QSplitter)[0]
    assert splitter.count() == 3
    assert splitter.widget(0) is pantalla.combo_profesional.parentWidget()
    assert splitter.widget(1) is pantalla.lista_franjas.parentWidget()
    assert splitter.widget(2) is pantalla.grilla


def test_columna_de_franjas_tiene_titulo_lista_y_tres_botones_al_pie(qtbot, conn, profesional_y_consultorio):
    """La segunda columna, nueva en esta ronda: título arriba, la lista
    de franjas creciendo con `stretch=1` y los tres botones de acción
    justo debajo — al ser lo único con stretch, la lista empuja los
    botones exactamente al pie de la columna."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    panel_franjas = pantalla.lista_franjas.parentWidget()
    etiqueta = next(
        lbl for lbl in panel_franjas.findChildren(QLabel) if lbl.text() == "Franjas agregadas a esta búsqueda"
    )
    layout = panel_franjas.layout()
    assert layout.indexOf(etiqueta) < layout.indexOf(pantalla.lista_franjas) < layout.indexOf(pantalla.boton_pdf)


def test_referencias_de_colores_sin_texto_recortado(qtbot, conn, profesional_y_consultorio):
    """Bug real detectado al armar esta pantalla a cuatro columnas: sin
    `fijar_ancho_etiqueta_leyenda`, la columna de Filtros (angosta,
    ~250px) forzaba varias líneas de wrap en las descripciones más
    largas de "Referencias de colores", pero cada fila se dimensionaba
    con el `sizeHint` de una sola línea SIN wrapear — el texto de más
    quedaba recortado arriba y abajo (`QLabel` centra verticalmente por
    default). Confirma que las etiquetas más largas ya piden más alto
    del que ocuparía una sola línea."""
    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    leyenda = pantalla.grilla._leyenda_colores
    etiquetas = [
        leyenda._layout.itemAtPosition(i, 1).widget()
        for i in range(leyenda._layout.rowCount())
        if leyenda._layout.itemAtPosition(i, 1) is not None
    ]
    una_linea = etiquetas[0].fontMetrics().height()
    assert any(e.minimumHeight() > una_linea * 1.5 for e in etiquetas)


def test_leyenda_se_agranda_mas_en_aislada_que_en_regular(qtbot, conn, profesional_y_consultorio):
    """Pedido explícito de la clienta: "Aislada de manera similar a esta
    pantalla de Regulares" — Aislada tiene 6 referencias contra las 8 de
    Regular, así que con menos filas para repartir el mismo alto total
    necesita una muestra y una letra más grandes todavía para llegar al
    mismo pie de columna. `_ajustar_tamano_leyenda` aplica un juego de
    valores propio por tipo cada vez que cambia "Tipo de búsqueda"."""
    from app.negocio.oferta_busqueda import TIPO_AISLADA, TIPO_REGULAR

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)

    pantalla.combo_tipo.setCurrentIndex(pantalla.combo_tipo.findData(TIPO_REGULAR))
    _, alto_regular = pantalla.grilla.tamano_muestra_leyenda()

    pantalla.combo_tipo.setCurrentIndex(pantalla.combo_tipo.findData(TIPO_AISLADA))
    _, alto_aislada = pantalla.grilla.tamano_muestra_leyenda()

    assert alto_aislada > alto_regular


def test_leyenda_de_aislada_sin_texto_recortado(qtbot, conn, profesional_y_consultorio):
    """Mismo bug que `test_referencias_de_colores_sin_texto_recortado`,
    pero para Aislada — su juego propio de tamaño de letra/muestra
    (agrandado respecto de Regular, ver el test de arriba) también tiene
    que quedar consistente con lo que `QFontMetrics` usa para calcular el
    alto de cada etiqueta (`fijar_tamano_fuente_leyenda`, que usa
    `QLabel.setFont` — no un `setStyleSheet` de CSS, que no lo hubiera
    reflejado)."""
    from app.negocio.oferta_busqueda import TIPO_AISLADA

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_tipo.setCurrentIndex(pantalla.combo_tipo.findData(TIPO_AISLADA))

    leyenda = pantalla.grilla._leyenda_colores
    etiquetas = [
        leyenda._layout.itemAtPosition(i, 1).widget()
        for i in range(leyenda._layout.rowCount())
        if leyenda._layout.itemAtPosition(i, 1) is not None
    ]
    from PySide6.QtCore import QRect as _QRect

    ancho = leyenda._ancho_etiqueta
    for etiqueta in etiquetas:
        rect = etiqueta.fontMetrics().boundingRect(_QRect(0, 0, ancho, 0), Qt.TextFlag.TextWordWrap, etiqueta.text())
        # El alto ya calculado no puede quedar por debajo de lo que la
        # letra REAL (la que Qt termina pintando) necesita.
        assert etiqueta.minimumHeight() >= rect.height()


def test_referencias_de_colores_sin_recorte_al_ancho_real_renderizado(qtbot, conn, profesional_y_consultorio):
    """Bug real detectado al revisar el pedido de la clienta de "letras
    cortadas": los dos tests de arriba comparan `minimumHeight()` contra
    un `boundingRect` calculado con `leyenda._ancho_etiqueta` (el ancho
    que se le PASÓ a `fijar_ancho_etiqueta_leyenda`) — si ese valor está
    mal (como pasaba con 220, cuando el ancho REAL renderizado de la
    etiqueta era 186px), los dos tests siguen pasando igual, porque
    comparan contra su propia asunción equivocada en vez de contra la
    realidad. Este test mide el `QLabel.width()` YA RENDERIZADO (mostrando
    la pantalla de verdad, no solo construyéndola) y confirma que el alto
    ya calculado alcanza para el wrap real a ESE ancho — a 220px
    "Reservado a futuro + aislada confirmada este mes." wrapeaba a 2
    líneas, pero a los 186px reales necesita 3, y la tercera quedaba
    cortada."""
    from PySide6.QtCore import QRect as _QRect
    from app.negocio.oferta_busqueda import TIPO_AISLADA, TIPO_REGULAR

    pantalla = _PanelOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    for tipo in (TIPO_REGULAR, TIPO_AISLADA):
        pantalla.combo_tipo.setCurrentIndex(pantalla.combo_tipo.findData(tipo))
        pantalla._al_cambiar_tipo()
        leyenda = pantalla.grilla._leyenda_colores
        etiquetas = [
            leyenda._layout.itemAtPosition(i, 1).widget()
            for i in range(leyenda._layout.rowCount())
            if leyenda._layout.itemAtPosition(i, 1) is not None
        ]
        for etiqueta in etiquetas:
            ancho_real = etiqueta.width()
            rect = etiqueta.fontMetrics().boundingRect(
                _QRect(0, 0, ancho_real, 0), Qt.TextFlag.TextWordWrap, etiqueta.text(),
            )
            assert etiqueta.height() >= rect.height(), (tipo, etiqueta.text())
