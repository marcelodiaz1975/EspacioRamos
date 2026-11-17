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


def test_botones_de_registro_habilitados_segun_estado(qtbot, conn, unidad):
    """Los tres botones que antes vivían al final de cada fila ahora
    viven al final de la columna 1, habilitados con una fila
    seleccionada (ver `_actualizar_botones_seleccion`)."""
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)
    panel.tabla.selectRow(0)

    # Sin datos cargados: Marcar abonado y Archivar registro habilitados.
    assert panel.boton_marcar_abonado.isEnabled()
    assert panel.boton_archivar_registro.isEnabled()

    from app.negocio.control_pagos import actualizar_instancia
    instancia = panel._registros[0]
    actualizar_instancia(conn, instancia["IdInstancia"], importe=1000)
    panel.actualizar()
    panel.tabla.selectRow(0)

    # Con importe cargado: Archivar registro se deshabilita.
    assert not panel.boton_archivar_registro.isEnabled()
    assert panel.boton_marcar_abonado.isEnabled()


def test_marcar_abonada_deshabilita_los_otros_dos_botones(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)
    panel.tabla.selectRow(0)

    panel._marcar_abonada_seleccionada()

    assert panel.tabla.item(0, panel._COL_ESTADO).text() == "Abonado"
    panel.tabla.selectRow(0)
    assert not panel.boton_marcar_abonado.isEnabled()
    assert not panel.boton_archivar_registro.isEnabled()


def test_archivar_instancia_sin_datos_cargados(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)
    panel.tabla.selectRow(0)

    panel._archivar_seleccionada()

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


def test_tabla_carga_control_tiene_columna_periodo_despues_de_medio_de_pago(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)

    assert [
        panel.tabla.horizontalHeaderItem(i).text() for i in range(panel.tabla.columnCount())
    ] == ["Nombre", "Categoría", "Afectación", "Medio de pago", "Período", "Vencimiento", "Importe", "Estado"]
    assert panel.tabla.item(0, panel._COL_PERIODO).text() == periodo_actual(conn)


def test_botones_de_registro_deshabilitados_sin_seleccion(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)

    for boton in (
        panel.boton_editar_concepto, panel.boton_dar_de_baja, panel.boton_duplicar_periodo_proximo,
        panel.boton_eliminar_duplicado, panel.boton_editar_registro, panel.boton_marcar_abonado,
        panel.boton_archivar_registro,
    ):
        assert not boton.isEnabled()

    panel.tabla.selectRow(0)
    assert panel.boton_duplicar_periodo_proximo.isEnabled()
    assert not panel.boton_eliminar_duplicado.isEnabled()


def test_duplicar_para_periodo_proximo_crea_fila_y_habilita_eliminar_duplicado(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)
    panel.tabla.selectRow(0)

    panel._duplicar_para_periodo_proximo()

    assert panel.tabla.rowCount() == 2
    periodos = {panel.tabla.item(f, panel._COL_PERIODO).text() for f in range(panel.tabla.rowCount())}
    from app.negocio.dias import sumar_meses
    assert periodos == {periodo_actual(conn), sumar_meses(periodo_actual(conn), 1)}

    fila_proxima = next(
        f for f in range(panel.tabla.rowCount())
        if panel.tabla.item(f, panel._COL_PERIODO).text() == sumar_meses(periodo_actual(conn), 1)
    )
    panel.tabla.selectRow(fila_proxima)
    assert panel.boton_eliminar_duplicado.isEnabled()
    assert not panel.boton_duplicar_periodo_proximo.isEnabled()

    panel._eliminar_registro_duplicado()

    assert panel.tabla.rowCount() == 1


def test_fila_abonada_o_archivada_queda_gris_y_al_final(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, nombre="Edenor")
    _crear_concepto_unidad(panel, unidad, nombre="AYSA")
    panel.tabla.selectRow(0)
    panel._marcar_abonada_seleccionada()

    # La fila Abonada queda al final (la otra, sin vencimiento/importe,
    # queda arriba) y en gris.
    assert panel.tabla.item(1, panel._COL_ESTADO).text() == "Abonado"
    from app.gui.estilos import COLOR_GRIS
    from PySide6.QtGui import QColor
    assert panel.tabla.item(1, panel._COL_NOMBRE).background().color() == QColor(COLOR_GRIS)


def test_colores_de_fila_segun_proximidad_del_vencimiento(qtbot, conn, unidad):
    from datetime import date, timedelta

    from app.gui.estilos import COLOR_AMARILLO, COLOR_ROJO, COLOR_VERDE, COLOR_VIOLETA
    from app.negocio.control_pagos import actualizar_instancia
    from PySide6.QtGui import QColor

    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    hoy = date.today()
    for nombre, dias in (("Vencida", -1), ("Hoy", 0), ("Mañana", 1), ("Lejos", 5)):
        _crear_concepto_unidad(panel, unidad, nombre=nombre)
        fila = next(f for f in range(panel.tabla.rowCount()) if panel.tabla.item(f, panel._COL_NOMBRE).text() == nombre)
        instancia = panel._registros[fila]
        vencimiento = (hoy + timedelta(days=dias)).isoformat()
        actualizar_instancia(conn, instancia["IdInstancia"], vencimiento=vencimiento, importe=100)
        panel.actualizar()

    colores_por_nombre = {
        panel.tabla.item(f, panel._COL_NOMBRE).text(): panel.tabla.item(f, panel._COL_NOMBRE).background().color()
        for f in range(panel.tabla.rowCount())
    }
    assert colores_por_nombre["Vencida"] == QColor(COLOR_VIOLETA)
    assert colores_por_nombre["Hoy"] == QColor(COLOR_ROJO)
    assert colores_por_nombre["Mañana"] == QColor(COLOR_AMARILLO)
    assert colores_por_nombre["Lejos"] == QColor(COLOR_VERDE)


def test_reiniciar_resetea_formulario_y_actualiza(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    panel = pantalla.panel_carga_control
    panel.campo_nombre.setText("Algo a medio escribir")
    panel.spin_importe.setValue(500)

    panel.reiniciar()

    assert panel.campo_nombre.text() == ""
    assert panel.spin_importe.value() == 0
    qtbot.waitUntil(lambda: panel.campo_nombre.hasFocus())


def test_historial_boton_editar_registro_habilita_con_seleccion_y_edita_estado(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel_carga = pantalla.panel_carga_control
    _crear_concepto_unidad(panel_carga, unidad)

    panel_historial = pantalla.panel_historial
    panel_historial.actualizar()
    assert not panel_historial.boton_editar_registro.isEnabled()

    panel_historial.tabla.selectRow(0)
    assert panel_historial.boton_editar_registro.isEnabled()
    instancia = panel_historial._fila_seleccionada_instancia()
    assert instancia["Estado"] == "Pendiente"

    from app.negocio.control_pagos import actualizar_instancia
    actualizar_instancia(conn, instancia["IdInstancia"], estado="Archivado")
    panel_historial.actualizar()
    assert panel_historial.tabla.item(0, 7).text() == "Archivado"


def test_catalogos_anidados_de_afectacion_funcionan(qtbot, conn):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_inmuebles_personales, pantalla.panel_rodados, pantalla.panel_personas):
        assert panel.objectName() == "panelSolapa"
        assert panel.anidado is True
