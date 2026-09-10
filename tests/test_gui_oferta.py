import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.oferta import PantallaOferta, _DialogoPrevisualizacion
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


def test_combo_profesional_es_buscable_por_codigo_o_nombre(qtbot, conn, profesional_y_consultorio):
    """Confirmado por la clienta: el selector de profesional buscable
    corre en todos los formularios del sistema, Oferta incluida — con el
    mismo formato canónico que el resto (antes mostraba "Apellido, Nombre")."""
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    completador = pantalla.combo_profesional.completer()
    assert isinstance(completador.model(), _ProxyBusquedaSinAcentos)
    assert pantalla.combo_profesional.itemText(0) == "Lic. Virginia Lo Veci"


def test_fechas_se_muestran_en_formato_dd_mm_aaaa(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.campo_fecha_desde.displayFormat() == "ddd dd-MM-yyyy"
    assert pantalla.campo_fecha_hasta.displayFormat() == "ddd dd-MM-yyyy"


def test_fecha_hasta_solo_habilitada_para_aislada(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    assert not pantalla.campo_fecha_hasta.isEnabled()  # Regular es el tipo por defecto

    indice_aislada = pantalla.combo_tipo.findData("Aislada")
    pantalla.combo_tipo.setCurrentIndex(indice_aislada)
    assert pantalla.campo_fecha_hasta.isEnabled()


def test_fecha_muestra_el_dia_de_la_semana_abreviado(qtbot, conn, profesional_y_consultorio):
    from PySide6.QtCore import QDate

    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.campo_fecha_desde.setDate(QDate(2026, 9, 11))  # viernes
    assert pantalla.campo_fecha_desde.text().startswith("vie")

    pantalla.campo_fecha_desde.setDate(QDate(2026, 9, 9))  # miércoles
    assert pantalla.campo_fecha_desde.text().startswith("mié")


def test_fecha_queda_pegada_a_su_etiqueta_sin_hueco(qtbot, conn, profesional_y_consultorio):
    """Sin un `addStretch()` al final de la fila, QHBoxLayout reparte el
    espacio sobrante entre los 4 widgets por igual — cada etiqueta queda
    mucho más ancha que su propio texto y dejaba un hueco antes del
    selector de fecha correspondiente."""
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    etiquetas = {lbl.text(): lbl for lbl in pantalla.findChildren(QLabel)}
    etiqueta_desde = etiquetas["Desde"]
    etiqueta_hasta = etiquetas["Hasta (solo Aislada)"]
    assert etiqueta_desde.width() <= etiqueta_desde.sizeHint().width() + 2
    assert etiqueta_hasta.width() <= etiqueta_hasta.sizeHint().width() + 2


def test_horario_muestra_formato_hs(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.spin_desde.setValue(9)
    assert pantalla.spin_desde.text() == "9:00hs"

    pantalla.spin_hasta.setValue(12.5)
    assert pantalla.spin_hasta.text() == "12:30hs"


def test_localidad_edificio_unidad_arrancan_en_todas(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla._filtro_localidad._boton.text() == "Todas las localidades"
    assert pantalla._filtro_edificio._boton.text() == "Todos los edificios"
    assert pantalla._filtro_unidad._boton.text() == "Todas las unidades"
    # sin nada tildado a mano, la búsqueda no se restringe (lista completa)
    assert len(pantalla._ids_unidad_seleccionadas()) == 1


def test_elegir_una_localidad_acota_las_opciones_de_edificio(qtbot, conn, profesional_y_consultorio):
    id_prof, id_edificio = profesional_y_consultorio
    conn.execute("UPDATE Edificio SET DomicilioLocalidad = 'Recoleta' WHERE IdEdificio = ?", (id_edificio,))
    id_edificio_2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2", DomicilioLocalidad="Palermo")
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_2, Departamento="2do B")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    conn.commit()

    pantalla = PantallaOferta(conn)
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

    pantalla = PantallaOferta(conn)
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
    pantalla = PantallaOferta(conn)
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
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    busqueda = pantalla._armar_busqueda_actual()
    assert busqueda.tamano is None


def test_hay_tres_botones_y_no_esta_resaltado_ni_pdf_ni_texto(qtbot, conn, profesional_y_consultorio):
    from PySide6.QtWidgets import QPushButton

    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    botones = {b.text(): b for b in pantalla.findChildren(QPushButton) if b.text() in (
        "Generar PDF", "Generar texto WhatsApp", "Nueva búsqueda",
    )}
    assert set(botones) == {"Generar PDF", "Generar texto WhatsApp", "Nueva búsqueda"}
    assert botones["Generar PDF"].objectName() == "botonAccion"
    assert botones["Generar texto WhatsApp"].objectName() == "botonAccion"
    assert botones["Nueva búsqueda"].objectName() == "botonDestacado"


def test_nueva_busqueda_resetea_el_formulario_y_enfoca_profesional(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
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

    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    assert list(pantalla._checks_dia.keys()) == ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
    assert all(check.isChecked() is False for check in pantalla._checks_dia.values())

    grid = pantalla._checks_dia["Lunes"].parentWidget().layout()
    assert isinstance(grid, QGridLayout)
    # 3 arriba y 3 abajo (6 días -> ceil(6/2) = 3 columnas)
    assert grid.itemAtPosition(0, 2) is not None
    assert grid.itemAtPosition(1, 0) is not None
    assert grid.itemAtPosition(1, 2) is not None


def test_grilla_embebida_tiene_titulo_grilla_semanal(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.grilla._panel_filtros.title() == "Grilla semanal"


def test_foco_inicial_queda_en_profesional(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.combo_profesional.hasFocus())


def test_lista_franjas_es_scroleable_con_muchas_franjas(qtbot, conn, profesional_y_consultorio):
    """El campo tiene una altura fija (no crece con el formulario) y
    hereda el scroll propio de QListWidget — si se cargan muchas
    franjas, quedan navegables con la barra en vez de estirar la
    pantalla."""
    from PySide6.QtCore import Qt as _Qt

    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    for i in range(20):
        pantalla._checks_dia["Lunes"].setChecked(True)
        pantalla.spin_desde.setValue(9)
        pantalla.spin_hasta.setValue(10 + i % 10 * 0.1 + 1)
        pantalla._agregar_franja()

    assert pantalla.lista_franjas.count() == 20
    assert pantalla.lista_franjas.maximumHeight() == 90
    assert pantalla.lista_franjas.verticalScrollBarPolicy() != _Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_grilla_operativa_embebida_sigue_el_tipo_de_busqueda(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.grilla.combo_modo.currentData() == "regular"
    assert not pantalla.grilla.combo_modo.isEnabled()

    indice_aislada = pantalla.combo_tipo.findData("Aislada")
    pantalla.combo_tipo.setCurrentIndex(indice_aislada)
    assert pantalla.grilla.combo_modo.currentData() == "aislada"


def test_generar_pdf_guarda_en_archivos_varios_oferta(qtbot, conn, tmp_path, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes

    pantalla._generar_pdf()

    generados = list((tmp_path / "Archivos varios" / "Oferta").iterdir())
    assert len(generados) == 1
    assert generados[0].name.startswith("Oferta de consultorios - Lic. Virginia Lo Veci")


def test_generar_texto_muestra_dialogo_con_el_texto(qtbot, conn, tmp_path, monkeypatch, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaOferta(conn)
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
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._generar_pdf()
    assert not (tmp_path / "Archivos varios" / "Oferta").exists()


def test_agregar_franja_la_suma_a_la_lista_y_limpia_dias(qtbot, conn, profesional_y_consultorio):
    pantalla = PantallaOferta(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes

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
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes
    pantalla._agregar_franja()
    pantalla.lista_franjas.setCurrentRow(0)

    pantalla._quitar_franja_seleccionada()

    assert pantalla._franjas == []
    assert pantalla.lista_franjas.count() == 0


def test_generar_con_dos_franjas_genera_un_solo_documento(qtbot, conn, tmp_path, profesional_y_consultorio):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaOferta(conn)
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
    pantalla = PantallaOferta(conn)
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
    pantalla = PantallaOferta(conn)
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
    pantalla = PantallaOferta(conn)
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
    pantalla = PantallaOferta(conn)
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
    pantalla = PantallaOferta(conn)
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
