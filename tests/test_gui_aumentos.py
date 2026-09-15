import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.aumentos import (
    _COL_CONSULTORIO,
    _COL_DIF_REGULAR,
    _COL_EDIFICIO,
    _COL_LOCALIDAD,
    _COL_PORCENTAJE_DIFERENCIAL,
    _COL_PORCENTAJE_GENERAL,
    _COL_REGULAR_ACTUAL,
    _COL_REGULAR_NUEVO,
    _COL_UNIDAD,
    _GUION,
    PantallaAumentos,
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


def _crear_edificio_con_consultorio(
    conn, valor_regular=1000, valor_aislada=1500, localidad="Ramos Mejía", nombre_edificio="Torre Norte",
):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre=nombre_edificio, DomicilioLocalidad=localidad)
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1,
        ValorHoraRegularActual=valor_regular, ValorHoraAisladaActual=valor_aislada,
    )


def test_pestanas(qtbot, conn):
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_aumentos is not None
    assert pantalla.panel_esquema is not None


def test_tabla_arranca_poblada_con_todos_los_consultorios(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    _crear_edificio_con_consultorio(conn, nombre_edificio="Torre Sur")
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_aumentos.tabla.rowCount() == 2


def test_columnas_localidad_edificio_unidad_consultorio_separadas(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.panel_aumentos.tabla
    assert tabla.item(0, _COL_LOCALIDAD).text() == "Ramos Mejía"
    assert tabla.item(0, _COL_EDIFICIO).text() == "Torre Norte"
    assert tabla.item(0, _COL_UNIDAD).text() == "1A"
    assert tabla.item(0, _COL_CONSULTORIO).text() == "1"
    assert id_consultorio is not None


def test_simular_calcula_regular_nuevo(qtbot, conn):
    _crear_edificio_con_consultorio(conn, valor_regular=1000)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    panel.spin_porcentaje.setValue(10)
    panel._simular()
    assert panel.tabla.item(0, _COL_REGULAR_ACTUAL).text() == "$ 1.000,00"
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.100,00"
    assert panel.tabla.item(0, _COL_DIF_REGULAR).text() == "$ 100,00"


def test_porcentaje_general_se_muestra_en_la_columna(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    panel.spin_porcentaje.setValue(15)
    panel._simular()
    assert panel.tabla.item(0, _COL_PORCENTAJE_GENERAL).text() == "15,00%"
    assert panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL).text() == _GUION


def test_diferencial_pisa_al_general_y_muestra_rayita_cruzada(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    panel.spin_porcentaje.setValue(10)
    panel._diferenciales[id_consultorio] = 50
    panel._simular()

    assert panel.tabla.item(0, _COL_PORCENTAJE_GENERAL).text() == _GUION
    assert panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL).text() == "50,00%"
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.500,00"


def test_boton_editar_tiene_el_texto_pedido(qtbot, conn):
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_aumentos.boton_editar.text() == "Editar porcentaje diferencial"


def test_redondear_valores_activado_por_defecto_en_multiplos_de_1(qtbot, conn):
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    assert panel.check_redondear.isChecked() is True
    assert panel._radios_multiplo[1].isChecked() is True
    assert panel.panel_multiplo.isEnabled() is True


def test_destildar_redondear_deshabilita_selector_de_multiplo(qtbot, conn):
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    panel.check_redondear.setChecked(False)
    assert panel.panel_multiplo.isEnabled() is False
    assert panel._redondear_a() is None


def test_redondear_a_multiplo_de_100_redondea_los_valores_nuevos(qtbot, conn):
    _crear_edificio_con_consultorio(conn, valor_regular=1000)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    panel.spin_porcentaje.setValue(13.37)
    panel._radios_multiplo[100].setChecked(True)
    panel._simular()
    valor = panel.tabla.item(0, _COL_REGULAR_NUEVO).text()
    # 1000 * 1.1337 = 1133.70 -> redondeado para arriba a múltiplo de 100 -> 1200
    assert valor == "$ 1.200,00"


def test_sin_redondear_conserva_los_centavos(qtbot, conn):
    _crear_edificio_con_consultorio(conn, valor_regular=1000)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    panel.check_redondear.setChecked(False)
    panel.spin_porcentaje.setValue(13.37)
    panel._simular()
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.133,70"


def test_columna_diferencial_no_editable_sin_tildar_editar(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    from PySide6.QtCore import Qt
    item = panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL)
    assert not bool(item.flags() & Qt.ItemFlag.ItemIsEditable)


def test_boton_editar_habilita_columna_diferencial(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    panel.boton_editar.setChecked(True)
    from PySide6.QtCore import Qt
    item = panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL)
    assert bool(item.flags() & Qt.ItemFlag.ItemIsEditable)


def test_editar_celda_diferencial_actualiza_simulacion(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    panel.spin_porcentaje.setValue(10)
    panel._simular()
    panel.boton_editar.setChecked(True)

    panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL).setText("30")
    assert panel._diferenciales[id_consultorio] == 30
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.300,00"

    panel.tabla.item(0, _COL_PORCENTAJE_DIFERENCIAL).setText("")
    assert id_consultorio not in panel._diferenciales
    assert panel.tabla.item(0, _COL_REGULAR_NUEVO).text() == "$ 1.100,00"


def test_filtro_localidad_solo_oculta_filas_no_cambia_el_conjunto_confirmado(qtbot, conn):
    _crear_edificio_con_consultorio(conn, localidad="Ramos Mejía", nombre_edificio="Torre Norte")
    _crear_edificio_con_consultorio(conn, localidad="Haedo", nombre_edificio="Torre Sur")
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos

    indice = panel.combo_localidad.findText("Haedo")
    panel.combo_localidad.setCurrentIndex(indice)

    assert panel.tabla.rowCount() == 2  # las filas siguen ahí
    ocultas = [panel.tabla.isRowHidden(f) for f in range(panel.tabla.rowCount())]
    assert ocultas.count(True) == 1
    assert len(panel._filas) == 2  # el filtro no recorta lo que se simuló/confirmaría


def test_confirmar_sin_simular_no_falla(qtbot, conn):
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aumentos._confirmar()


def test_confirmar_actualiza_valores_de_consultorio(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000, valor_aislada=1500)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    panel.spin_porcentaje.setValue(10)
    panel._simular()
    panel._confirmar()

    fila = conn.execute(
        "SELECT ValorHoraRegularActual FROM Consultorio WHERE IdConsultorio = ?", (id_consultorio,),
    ).fetchone()
    assert fila["ValorHoraRegularActual"] == pytest.approx(1100)


def test_deshacer_ultimo_movimiento_revierte(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aumentos
    panel.spin_porcentaje.setValue(10)
    panel._simular()
    panel._confirmar()

    panel._deshacer_ultimo()

    fila = conn.execute(
        "SELECT ValorHoraRegularActual FROM Consultorio WHERE IdConsultorio = ?", (id_consultorio,),
    ).fetchone()
    assert fila["ValorHoraRegularActual"] == pytest.approx(1000)


def test_deshacer_sin_movimientos_no_falla(qtbot, conn):
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aumentos._deshacer_ultimo()


def test_esquema_arranca_con_valores_por_defecto(qtbot, conn):
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_esquema
    assert panel.spin_horas.value() == 2.0
    assert panel.spin_porcentaje_descuento.value() == 1.0
    assert panel.spin_porcentaje_tope.value() == 25.0
    assert panel.boton_confirmar.isEnabled() is False


def test_esquema_preview_refleja_los_parametros(qtbot, conn):
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_esquema
    assert panel.tabla_preview.item(0, 2).text() == "0,00%"
    assert panel.tabla_preview.item(1, 2).text() == "1,00%"


def test_esquema_cambiar_parametro_habilita_confirmar(qtbot, conn):
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_esquema
    panel.spin_horas.setValue(4)
    assert panel.boton_confirmar.isEnabled() is True


def test_esquema_detecta_parametros_no_default_del_vigente(qtbot, conn):
    actualizar_esquema_descuentos(conn, generar_tramos_esquema(cantidad_horas=5, porcentaje_descuento=2, porcentaje_tope=10))
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_esquema
    assert panel.spin_horas.value() == 5.0
    assert panel.spin_porcentaje_descuento.value() == 2.0
    assert panel.spin_porcentaje_tope.value() == 10.0
    assert panel.boton_confirmar.isEnabled() is False
    assert panel.etiqueta_aviso.isHidden() is True


def test_esquema_no_reconocido_muestra_aviso_y_tramos_vigentes_en_preview(qtbot, conn):
    actualizar_esquema_descuentos(conn, [(0, 10, 2), (10, 999, 5)])
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_esquema

    assert panel.etiqueta_aviso.isHidden() is False
    assert panel.spin_horas.value() == 2.0  # default, no se pudo reconocer
    assert panel.tabla_preview.rowCount() == 2
    assert panel.tabla_preview.item(0, 1).text() == "10hs"
    assert panel.tabla_preview.item(1, 0).text() == "Más de 10hs"  # última fila: fusionada
    assert panel.tabla_preview.item(1, 2).text() == "5,00%"


def test_esquema_editar_un_campo_oculta_el_aviso_y_pasa_a_vista_generada(qtbot, conn):
    actualizar_esquema_descuentos(conn, [(0, 10, 2), (10, 999, 5)])
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_esquema

    panel.spin_horas.setValue(3)
    assert panel.etiqueta_aviso.isHidden() is True
    assert panel.tabla_preview.item(0, 1).text() == "3hs"  # ahora es la vista previa generada, no la vigente


def test_esquema_confirmar_cambios_reemplaza_el_vigente(qtbot, conn):
    activos_antes = obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=1)
    assert len(activos_antes) > 0

    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_esquema
    panel.spin_horas.setValue(5)
    panel.spin_porcentaje_descuento.setValue(2)
    panel.spin_porcentaje_tope.setValue(10)
    panel._confirmar_cambios()

    activos_despues = obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=1)
    assert {a["PorcentajeDescuento"] for a in activos_despues} == {0, 2, 4, 6, 8, 10}
    assert panel.boton_confirmar.isEnabled() is False
    inactivos = obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=0)
    assert len(inactivos) == len(activos_antes)
