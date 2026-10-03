import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import COLOR_AMARILLO
from app.gui.pantallas.aumentos import (
    _COL_AISLADA_NUEVO,
    _COL_CONSULTORIO,
    _COL_DIF_REGULAR,
    _COL_EDIFICIO,
    _COL_LOCALIDAD,
    _COL_PORCENTAJE_DIFERENCIAL,
    _COL_PORCENTAJE_GENERAL,
    _COL_REGULAR_ACTUAL,
    _COL_REGULAR_NUEVO,
    _COL_RESTABLECER,
    _COL_UNIDAD,
    _GUION,
    _PanelAumentos,
    _PanelEsquemaDescuentos,
)
from app.negocio.aumentos import actualizar_esquema_descuentos, generar_tramos_esquema
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


def _id_localidad(conn, nombre: str) -> int:
    fila = conn.execute("SELECT IdLocalidad FROM Localidad WHERE Localidad = ?", (nombre,)).fetchone()
    return fila["IdLocalidad"] if fila else obtener_repositorio(conn, "Localidad").crear(Localidad=nombre)


def _crear_edificio_con_consultorio(
    conn, valor_regular=1000, valor_aislada=1500, localidad="Ramos Mejía", nombre_edificio="Torre Norte",
):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre=nombre_edificio, IdLocalidad=_id_localidad(conn, localidad)
    )
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1,
        ValorHoraRegularActual=valor_regular, ValorHoraAisladaActual=valor_aislada,
    )


def test_tabla_arranca_poblada_con_todos_los_consultorios(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    _crear_edificio_con_consultorio(conn, nombre_edificio="Torre Sur")
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    assert panel.tabla.rowCount() == 2


def test_columnas_localidad_edificio_unidad_consultorio_separadas(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    tabla = panel.tabla
    assert tabla.item(0, _COL_LOCALIDAD).text() == "Ramos Mejía"
    assert tabla.item(0, _COL_EDIFICIO).text() == "Torre Norte"
    assert tabla.item(0, _COL_UNIDAD).text() == "1A"
    assert tabla.item(0, _COL_CONSULTORIO).text() == "1"
    assert id_consultorio is not None


def test_simular_calcula_regular_nuevo(qtbot, conn):
    _crear_edificio_con_consultorio(conn, valor_regular=1000)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(10)
    panel._simular()
    assert panel.tabla.item(0, _COL_REGULAR_ACTUAL).text() == "$ 1.000,00"
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.100,00"
    assert panel.tabla.item(0, _COL_DIF_REGULAR).text() == "$ 100,00"


def test_porcentaje_general_se_muestra_en_la_columna(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(15)
    panel._simular()
    assert panel.tabla.item(0, _COL_PORCENTAJE_GENERAL).text() == "15,00%"
    assert panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL).text() == _GUION


def test_diferencial_pisa_al_general_y_muestra_rayita_cruzada(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(10)
    panel._diferenciales[id_consultorio] = 50
    panel._simular()

    assert panel.tabla.item(0, _COL_PORCENTAJE_GENERAL).text() == _GUION
    assert panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL).text() == "50,00%"
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.500,00"


def test_boton_editar_tiene_el_texto_pedido(qtbot, conn):
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    assert panel.boton_editar.text() == "Editar porcentaje diferencial"


def test_redondear_valores_activado_por_defecto_en_multiplos_de_1(qtbot, conn):
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    assert panel.check_redondear.isChecked() is True
    assert panel._radios_multiplo[1].isChecked() is True
    assert panel.panel_multiplo.isEnabled() is True


def test_destildar_redondear_deshabilita_selector_de_multiplo(qtbot, conn):
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.check_redondear.setChecked(False)
    assert panel.panel_multiplo.isEnabled() is False
    assert panel._redondear_a() is None


def test_redondear_a_multiplo_de_100_redondea_los_valores_nuevos(qtbot, conn):
    _crear_edificio_con_consultorio(conn, valor_regular=1000)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(13.37)
    panel._radios_multiplo[100].setChecked(True)
    panel._simular()
    valor = panel.tabla.item(0, _COL_REGULAR_NUEVO).text()
    # 1000 * 1.1337 = 1133.70 -> redondeado para arriba a múltiplo de 100 -> 1200
    assert valor == "$ 1.200,00"


def test_sin_redondear_conserva_los_centavos(qtbot, conn):
    _crear_edificio_con_consultorio(conn, valor_regular=1000)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.check_redondear.setChecked(False)
    panel.spin_porcentaje.setValue(13.37)
    panel._simular()
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.133,70"


def test_columna_diferencial_no_editable_sin_tildar_editar(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    from PySide6.QtCore import Qt
    item = panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL)
    assert not bool(item.flags() & Qt.ItemFlag.ItemIsEditable)


def test_boton_editar_habilita_columna_diferencial(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.boton_editar.setChecked(True)
    from PySide6.QtCore import Qt
    item = panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL)
    assert bool(item.flags() & Qt.ItemFlag.ItemIsEditable)


def test_editar_celda_diferencial_actualiza_simulacion(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(10)
    panel._simular()
    panel.boton_editar.setChecked(True)

    panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL).setText("30")
    assert panel._diferenciales[id_consultorio] == 30
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.300,00"

    panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL).setText("")
    assert id_consultorio not in panel._diferenciales
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.100,00"


# ----------------------------------------- DC-10 §1.2: valores a mano, resaltado, Restablecer

def test_boton_editar_valores_tiene_el_texto_pedido(qtbot, conn):
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    assert panel.boton_editar_valores.text() == "Editar valores manuales"


def test_columnas_nuevo_no_editables_sin_tildar_editar_valores(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    from PySide6.QtCore import Qt
    assert not bool(panel.tabla.item(0, _COL_REGULAR_NUEVO).flags() & Qt.ItemFlag.ItemIsEditable)
    assert not bool(panel.tabla.item(0, _COL_AISLADA_NUEVO).flags() & Qt.ItemFlag.ItemIsEditable)


def test_boton_editar_valores_habilita_columnas_nuevo(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.boton_editar_valores.setChecked(True)
    from PySide6.QtCore import Qt
    assert bool(panel.tabla.item(0, _COL_REGULAR_NUEVO).flags() & Qt.ItemFlag.ItemIsEditable)
    assert bool(panel.tabla.item(0, _COL_AISLADA_NUEVO).flags() & Qt.ItemFlag.ItemIsEditable)


def test_editar_celda_regular_nuevo_fija_el_valor_a_mano(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000, valor_aislada=1500)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(10)
    panel._simular()
    panel.boton_editar_valores.setChecked(True)

    panel.tabla.item(0, _COL_REGULAR_NUEVO).setText("$ 1.234,00")
    assert panel._valores_manuales[id_consultorio]["regular"] == pytest.approx(1234.0)
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.234,00"
    # El redondeo/% general no le vuelven a pegar a un valor fijado a mano
    # — Aislada sigue calculada con el % general (10% de 1500, con el
    # redondeo "siempre para arriba" ya existente de _redondear_a_multiplo).
    assert panel.tabla.item(0, _COL_AISLADA_NUEVO).text() == "$ 1.651,00"


def test_editar_celda_vacia_quita_solo_ese_override(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000, valor_aislada=1500)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.boton_editar_valores.setChecked(True)
    panel.tabla.item(0, _COL_REGULAR_NUEVO).setText("1234")
    panel.tabla.item(0, _COL_AISLADA_NUEVO).setText("1900")
    assert panel._valores_manuales[id_consultorio] == {"regular": 1234.0, "aislada": 1900.0}

    panel.tabla.item(0, _COL_REGULAR_NUEVO).setText("")
    assert panel._valores_manuales[id_consultorio] == {"aislada": 1900.0}


def test_valor_manual_invalido_avisa_y_no_rompe(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.boton_editar_valores.setChecked(True)
    panel.tabla.item(0, _COL_REGULAR_NUEVO).setText("no es un número")  # no debe lanzar


def test_valor_manual_resalta_la_celda_calculo_con_porcentaje_no(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000, valor_aislada=1500)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(10)
    panel._simular()
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).background().color().name() != QColor(COLOR_AMARILLO).name()

    panel.boton_editar_valores.setChecked(True)
    panel.tabla.item(0, _COL_REGULAR_NUEVO).setText("1234")
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).background().color().name() == QColor(COLOR_AMARILLO).name()
    # Aislada sigue calculada por %, sin resaltar
    assert panel.tabla.item(0, _COL_AISLADA_NUEVO).background().color().name() != QColor(COLOR_AMARILLO).name()
    assert id_consultorio in panel._valores_manuales


def test_valor_manual_y_porcentaje_diferencial_son_mutuamente_excluyentes(qtbot, conn):
    """Mismo criterio que % general/diferencial: nunca los dos juntos
    para la misma fila — fijar un valor a mano limpia el diferencial y
    viceversa."""
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.boton_editar.setChecked(True)
    panel.boton_editar_valores.setChecked(True)

    panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL).setText("30")
    assert id_consultorio in panel._diferenciales
    panel.tabla.item(0, _COL_REGULAR_NUEVO).setText("1234")
    assert id_consultorio not in panel._diferenciales
    assert panel._valores_manuales[id_consultorio]["regular"] == pytest.approx(1234.0)

    panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL).setText("30")
    assert id_consultorio not in panel._valores_manuales


def test_boton_restablecer_deshabilitado_sin_override(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    boton = panel.tabla.cellWidget(0, _COL_RESTABLECER)
    assert boton.isEnabled() is False


def test_boton_restablecer_limpia_diferencial_y_valor_manual(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(10)
    panel.boton_editar_valores.setChecked(True)
    panel.tabla.item(0, _COL_REGULAR_NUEVO).setText("1234")
    assert id_consultorio in panel._valores_manuales

    boton = panel.tabla.cellWidget(0, _COL_RESTABLECER)
    assert boton.isEnabled() is True
    boton.click()

    assert id_consultorio not in panel._valores_manuales
    assert id_consultorio not in panel._diferenciales
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.100,00"  # vuelve al % general


def test_rerenderizar_la_tabla_no_deja_botones_restablecer_huerfanos(qtbot, conn):
    """Bug real encontrado al armar "Restablecer" (no pedido, destapado
    midiendo geometría contra una captura): `setCellWidget` no borra solo
    el widget que reemplaza, a diferencia de `setItem` — cada re-render
    (un `_simular`/un tildar "Editar...") creaba un botón "Restablecer"
    nuevo y dejaba el anterior huérfano, colgado del viewport sin
    posición asignada por la tabla — Qt lo terminaba pintando superpuesto
    contra las primeras columnas de la primera fila. Se resolvió
    reusando un solo botón por consultorio (`self._botones_restablecer`)
    en vez de crear uno nuevo en cada render."""
    from PySide6.QtWidgets import QPushButton
    _crear_edificio_con_consultorio(conn, valor_regular=1000)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(10)
    panel._simular()  # un render más
    panel.boton_editar.setChecked(True)  # otro render (sin pasar por _simular)
    panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL).setText("30")  # otro render más

    botones = [b for b in panel.findChildren(QPushButton) if b.text() == "Restablecer"]
    assert len(botones) == 1  # uno solo, el que vive en la tabla — nada huérfano colgando


def test_confirmar_avisa_la_cantidad_de_liquidaciones_antes_de_confirmar(qtbot, conn, monkeypatch):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio="2020-01-01",
    )
    from app.negocio.dias import periodo_actual
    from app.negocio.liquidaciones import emitir_liquidacion
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=periodo_actual(conn), fecha_emision="2026-08-01")

    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(10)
    panel._simular()

    textos_pregunta = []

    def _question(*args, **kwargs):
        textos_pregunta.append(args[2])
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_question))
    panel._confirmar()

    assert len(textos_pregunta) == 1
    assert "1 liquidación" in textos_pregunta[0]


def test_confirmar_sin_liquidaciones_emitidas_lo_dice_en_el_aviso(qtbot, conn, monkeypatch):
    _crear_edificio_con_consultorio(conn, valor_regular=1000)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(10)
    panel._simular()

    textos_pregunta = []

    def _question(*args, **kwargs):
        textos_pregunta.append(args[2])
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_question))
    panel._confirmar()

    assert "Todavía no hay ninguna liquidación emitida" in textos_pregunta[0]


def test_confirmar_aplica_el_valor_manual(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.boton_editar_valores.setChecked(True)
    panel.tabla.item(0, _COL_REGULAR_NUEVO).setText("1234")
    panel._confirmar()

    fila = conn.execute(
        "SELECT ValorHoraRegularActual FROM Consultorio WHERE IdConsultorio = ?", (id_consultorio,),
    ).fetchone()
    assert fila["ValorHoraRegularActual"] == pytest.approx(1234.0)


def test_filtro_localidad_solo_oculta_filas_no_cambia_el_conjunto_confirmado(qtbot, conn):
    _crear_edificio_con_consultorio(conn, localidad="Ramos Mejía", nombre_edificio="Torre Norte")
    _crear_edificio_con_consultorio(conn, localidad="Haedo", nombre_edificio="Torre Sur")
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)

    indice = panel.combo_localidad.findText("Haedo")
    panel.combo_localidad.setCurrentIndex(indice)

    assert panel.tabla.rowCount() == 2  # las filas siguen ahí
    ocultas = [panel.tabla.isRowHidden(f) for f in range(panel.tabla.rowCount())]
    assert ocultas.count(True) == 1
    assert len(panel._filas) == 2  # el filtro no recorta lo que se simuló/confirmaría


def test_confirmar_sin_simular_no_falla(qtbot, conn):
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel._confirmar()


def test_confirmar_actualiza_valores_de_consultorio(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000, valor_aislada=1500)
    panel = _PanelAumentos(conn)
    qtbot.addWidget(panel)
    panel.spin_porcentaje.setValue(10)
    panel._simular()
    panel._confirmar()

    fila = conn.execute(
        "SELECT ValorHoraRegularActual FROM Consultorio WHERE IdConsultorio = ?", (id_consultorio,),
    ).fetchone()
    assert fila["ValorHoraRegularActual"] == pytest.approx(1100)


def test_esquema_arranca_con_valores_por_defecto(qtbot, conn):
    panel = _PanelEsquemaDescuentos(conn)
    qtbot.addWidget(panel)
    assert panel.spin_horas.value() == 2.0
    assert panel.spin_porcentaje_descuento.value() == 1.0
    assert panel.spin_porcentaje_tope.value() == 25.0
    assert panel.boton_confirmar.isEnabled() is False


def test_esquema_preview_refleja_los_parametros(qtbot, conn):
    panel = _PanelEsquemaDescuentos(conn)
    qtbot.addWidget(panel)
    assert panel.tabla_preview.item(0, 2).text() == "0,00%"
    assert panel.tabla_preview.item(1, 2).text() == "1,00%"


def test_esquema_cambiar_parametro_habilita_confirmar(qtbot, conn):
    panel = _PanelEsquemaDescuentos(conn)
    qtbot.addWidget(panel)
    panel.spin_horas.setValue(4)
    assert panel.boton_confirmar.isEnabled() is True


def test_esquema_detecta_parametros_no_default_del_vigente(qtbot, conn):
    actualizar_esquema_descuentos(conn, generar_tramos_esquema(cantidad_horas=5, porcentaje_descuento=2, porcentaje_tope=10))
    panel = _PanelEsquemaDescuentos(conn)
    qtbot.addWidget(panel)
    assert panel.spin_horas.value() == 5.0
    assert panel.spin_porcentaje_descuento.value() == 2.0
    assert panel.spin_porcentaje_tope.value() == 10.0
    assert panel.boton_confirmar.isEnabled() is False
    assert panel.etiqueta_aviso.isHidden() is True


def test_esquema_no_reconocido_muestra_aviso_y_tramos_vigentes_en_preview(qtbot, conn):
    actualizar_esquema_descuentos(conn, [(0, 10, 2), (10, 999, 5)])
    panel = _PanelEsquemaDescuentos(conn)
    qtbot.addWidget(panel)

    assert panel.etiqueta_aviso.isHidden() is False
    assert panel.spin_horas.value() == 2.0  # default, no se pudo reconocer
    assert panel.tabla_preview.rowCount() == 2
    assert panel.tabla_preview.item(0, 1).text() == "10hs"
    assert panel.tabla_preview.item(1, 0).text() == "Más de 10hs"  # última fila: fusionada
    assert panel.tabla_preview.item(1, 2).text() == "5,00%"


def test_esquema_editar_un_campo_oculta_el_aviso_y_pasa_a_vista_generada(qtbot, conn):
    actualizar_esquema_descuentos(conn, [(0, 10, 2), (10, 999, 5)])
    panel = _PanelEsquemaDescuentos(conn)
    qtbot.addWidget(panel)

    panel.spin_horas.setValue(3)
    assert panel.etiqueta_aviso.isHidden() is True
    assert panel.tabla_preview.item(0, 1).text() == "3hs"  # ahora es la vista previa generada, no la vigente


def test_esquema_confirmar_cambios_reemplaza_el_vigente(qtbot, conn):
    activos_antes = obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=1)
    assert len(activos_antes) > 0

    panel = _PanelEsquemaDescuentos(conn)
    qtbot.addWidget(panel)
    panel.spin_horas.setValue(5)
    panel.spin_porcentaje_descuento.setValue(2)
    panel.spin_porcentaje_tope.setValue(10)
    panel._confirmar_cambios()

    activos_despues = obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=1)
    assert {a["PorcentajeDescuento"] for a in activos_despues} == {0, 2, 4, 6, 8, 10}
    assert panel.boton_confirmar.isEnabled() is False
    inactivos = obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=0)
    assert len(inactivos) == len(activos_antes)
