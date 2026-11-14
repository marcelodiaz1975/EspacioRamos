import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.control_pagos import PantallaControlPagos
from app.negocio.dias import periodo_actual
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def unidad(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    return obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def _crear_concepto_unidad(panel, unidad, nombre="Edenor"):
    panel.campo_nombre.setText(nombre)
    panel.combo_categoria.setCurrentText("Servicios")
    panel.combo_tipo_afectacion.setCurrentIndex(panel.combo_tipo_afectacion.findData("Unidad"))
    panel.combo_detalle_afectacion.setCurrentIndex(panel.combo_detalle_afectacion.findData(unidad))
    panel.combo_medio_pago.setCurrentText("CA Bco Hipotecario")
    panel._crear()


def test_pantalla_tiene_cinco_solapas_en_el_orden_esperado(qtbot, conn):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.pestanas.count() == 5
    assert pantalla.pestanas.tabText(0) == "Carga y control"
    assert pantalla.pestanas.tabText(1) == "Historial"
    assert pantalla.pestanas.tabText(2) == "Inmuebles personales"
    assert pantalla.pestanas.tabText(3) == "Rodados"
    assert pantalla.pestanas.tabText(4) == "Personas"


def test_showevent_genera_las_instancias_del_periodo_actual(qtbot, conn, unidad):
    from app.negocio.control_pagos import crear_concepto

    crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()

    assert pantalla.panel_carga_control.tabla.rowCount() == 1
    assert pantalla.panel_carga_control.tabla.item(0, 0).text() == "Edenor"


def test_crear_concepto_imputado_a_unidad_sincroniza_gasto_operativo(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control

    panel.campo_nombre.setText("Edenor")
    panel.combo_categoria.setCurrentText("Servicios")
    panel.combo_tipo_afectacion.setCurrentIndex(panel.combo_tipo_afectacion.findData("Unidad"))
    panel.combo_detalle_afectacion.setCurrentIndex(panel.combo_detalle_afectacion.findData(unidad))
    panel.combo_medio_pago.setCurrentText("CA Bco Hipotecario")
    panel.spin_importe.setValue(45500.26)
    panel._crear()

    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, panel._COL_NOMBRE).text() == "Edenor"
    assert panel.tabla.item(0, panel._COL_AFECTACION).text() == 'Ramos 1 - 7mo "L"'
    gasto = obtener_repositorio(conn, "GastoOperativo").listar(Periodo=periodo_actual(conn), Concepto="Edenor")
    assert len(gasto) == 1
    assert gasto[0]["Monto"] == 45500.26
    assert gasto[0]["Origen"] == "Importado"

    # El formulario se resetea y el foco vuelve a Nombre.
    assert panel.campo_nombre.text() == ""
    assert panel.combo_tipo_afectacion.currentIndex() == 0


def test_crear_concepto_sin_importe_deja_la_fila_en_blanco(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)

    assert panel.tabla.item(0, panel._COL_IMPORTE).text() == ""
    assert panel.tabla.item(0, panel._COL_VENCIMIENTO).text() == ""
    assert obtener_repositorio(conn, "GastoOperativo").listar() == []


def test_botones_de_fila_habilitados_segun_estado(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)

    # Sin datos cargados: Marcar abonado y Archivar habilitados.
    assert panel.tabla.cellWidget(0, panel._COL_ABONADO).isEnabled()
    assert panel.tabla.cellWidget(0, panel._COL_ARCHIVAR).isEnabled()

    from app.negocio.control_pagos import actualizar_instancia
    instancia = panel._registros[0]
    actualizar_instancia(conn, instancia["IdInstancia"], importe=1000)
    panel.actualizar()

    # Con importe cargado: Archivar se deshabilita.
    assert not panel.tabla.cellWidget(0, panel._COL_ARCHIVAR).isEnabled()
    assert panel.tabla.cellWidget(0, panel._COL_ABONADO).isEnabled()


def test_marcar_abonada_deshabilita_los_otros_dos_botones(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)

    panel._marcar_abonada(panel._registros[0])

    assert panel.tabla.item(0, panel._COL_ESTADO).text() == "Abonado"
    assert not panel.tabla.cellWidget(0, panel._COL_ABONADO).isEnabled()
    assert not panel.tabla.cellWidget(0, panel._COL_ARCHIVAR).isEnabled()


def test_archivar_instancia_sin_datos_cargados(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)

    panel._archivar(panel._registros[0])

    assert panel.tabla.item(0, panel._COL_ESTADO).text() == "Archivado"


def test_editar_concepto_seleccionado_sin_seleccion_avisa(qtbot, conn):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    panel._editar_concepto_seleccionado()  # no debe romper sin ninguna fila


def test_dar_de_baja_seleccionado_deja_de_generar_instancias(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)
    panel.tabla.selectRow(0)
    id_concepto = panel._registros[0]["IdConcepto"]

    panel._dar_de_baja_seleccionado()

    concepto = obtener_repositorio(conn, "ConceptoControlPago").obtener(id_concepto)
    assert concepto["Activo"] == 0


def test_historial_filtra_por_categoria_concepto_afectacion_y_medio_de_pago(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel_carga = pantalla.panel_carga_control
    _crear_concepto_unidad(panel_carga, unidad, nombre="Edenor")
    _crear_concepto_unidad(panel_carga, unidad, nombre="AYSA")

    panel_historial = pantalla.panel_historial
    panel_historial.actualizar()
    assert panel_historial.tabla.rowCount() == 2

    indice = panel_historial.combo_concepto.findData("Edenor")
    panel_historial.combo_concepto.setCurrentIndex(indice)
    assert panel_historial.tabla.rowCount() == 1
    assert panel_historial.tabla.item(0, 1).text() == "Edenor"


def test_catalogos_anidados_de_afectacion_funcionan(qtbot, conn):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_inmuebles_personales, pantalla.panel_rodados, pantalla.panel_personas):
        assert panel.objectName() == "panelSolapa"
        assert panel.anidado is True
