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


def _crear_concepto_unidad(panel, unidad, nombre="Edenor", *, categoria="Servicios", medio_pago="CA Bco Hipotecario"):
    panel.campo_nombre.setText(nombre)
    panel.combo_categoria.setCurrentText(categoria)
    panel.combo_tipo_afectacion.setCurrentIndex(panel.combo_tipo_afectacion.findData("Unidad"))
    panel.combo_detalle_afectacion.setCurrentIndex(panel.combo_detalle_afectacion.findData(unidad))
    panel.combo_medio_pago.setCurrentText(medio_pago)
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
    """Pedido explícito de la clienta: los tres botones vuelven a vivir
    al final de cada fila de la tabla (`_armar_botones_fila`) — ya no
    dependen de que haya una fila seleccionada, solo del estado/datos
    de ESA fila."""
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)

    # Sin datos cargados: Abonar y Archivar habilitados.
    assert panel.tabla.cellWidget(0, panel._COL_ABONAR).isEnabled()
    assert panel.tabla.cellWidget(0, panel._COL_ARCHIVAR).isEnabled()

    from app.negocio.control_pagos import actualizar_instancia
    instancia = panel._registros[0]
    actualizar_instancia(conn, instancia["IdInstancia"], importe=1000)
    panel.actualizar()

    # Con importe cargado: Archivar se deshabilita.
    assert not panel.tabla.cellWidget(0, panel._COL_ARCHIVAR).isEnabled()
    assert panel.tabla.cellWidget(0, panel._COL_ABONAR).isEnabled()


def test_marcar_abonada_deshabilita_los_otros_dos_botones(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)

    panel.tabla.cellWidget(0, panel._COL_ABONAR).click()

    assert panel.tabla.item(0, panel._COL_ESTADO).text() == "Abonado"
    assert not panel.tabla.cellWidget(0, panel._COL_ABONAR).isEnabled()
    assert not panel.tabla.cellWidget(0, panel._COL_ARCHIVAR).isEnabled()


def test_archivar_instancia_sin_datos_cargados(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)

    panel.tabla.cellWidget(0, panel._COL_ARCHIVAR).click()

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
    ] == [
        "Nombre", "Categoría", "Afectación", "Cuenta/Id", "Medio de pago", "Período", "Vencimiento", "Importe",
        "Estado", "", "", "", "",
    ]
    assert panel.tabla.item(0, panel._COL_PERIODO).text() == periodo_actual(conn)


def test_botones_de_registro_deshabilitados_sin_seleccion(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)
    # Pedido explícito de la clienta: crear un concepto deja la
    # instancia nueva seleccionada — para probar "sin selección" hay
    # que sacarla a mano.
    panel.tabla.clearSelection()

    for boton in (
        panel.boton_editar_concepto, panel.boton_dar_de_baja, panel.boton_duplicar_periodo_proximo,
        panel.boton_eliminar_duplicado,
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
    fila = next(f for f in range(panel.tabla.rowCount()) if panel.tabla.item(f, panel._COL_NOMBRE).text() == "Edenor")
    panel.tabla.cellWidget(fila, panel._COL_ABONAR).click()

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


def test_las_cuatro_columnas_arrancan_a_la_misma_altura_y_con_igual_ancho(qtbot, conn):
    """Pedido explícito de la clienta: "cuatro columnas de igual ancho
    que abarquen todo el ancho de la pantalla, el primer elemento de
    cada columna que arranque en el pixel 85 de altura" — mismo
    criterio de medición relativa que Vacaciones (`test_gui_novedades.
    test_vacaciones_profesional_y_filtro_de_localidad_arrancan_a_la_
    misma_altura`): no se compara contra un valor absoluto, se compara
    que las 4 columnas coincidan entre sí."""
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    panel = pantalla.panel_carga_control

    primeros_widgets = [
        panel.campo_nombre, panel.campo_vencimiento, panel.boton_editar_concepto, panel.combo_filtro_nombre,
    ]
    columnas = [widget.parentWidget() for widget in primeros_widgets]
    primeros_elementos = [columna.layout().itemAt(0).widget() for columna in columnas]

    alturas = {w.mapTo(panel, w.rect().topLeft()).y() for w in primeros_elementos}
    assert len(alturas) == 1

    anchos = {columna.width() for columna in columnas}
    assert len(anchos) == 1


def test_boton_dar_de_baja_entra_en_el_ancho_fijo_compartido_sin_cortar(qtbot, conn):
    from app.gui.pantallas.control_pagos import _ANCHO_CAMPO_CARGA_CONTROL

    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control

    assert panel.boton_dar_de_baja.sizeHint().width() <= _ANCHO_CAMPO_CARGA_CONTROL


def test_click_en_encabezado_ordena_por_esa_columna_y_el_segundo_click_invierte(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, nombre="Zeta")
    _crear_concepto_unidad(panel, unidad, nombre="Alfa")

    panel.tabla.horizontalHeader().sectionClicked.emit(panel._COL_NOMBRE)
    nombres = [panel.tabla.item(f, panel._COL_NOMBRE).text() for f in range(panel.tabla.rowCount())]
    assert nombres == ["Alfa", "Zeta"]

    panel.tabla.horizontalHeader().sectionClicked.emit(panel._COL_NOMBRE)
    nombres = [panel.tabla.item(f, panel._COL_NOMBRE).text() for f in range(panel.tabla.rowCount())]
    assert nombres == ["Zeta", "Alfa"]


def test_f5_reiniciar_vuelve_al_orden_por_defecto(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, nombre="Zeta")
    _crear_concepto_unidad(panel, unidad, nombre="Alfa")
    panel.tabla.horizontalHeader().sectionClicked.emit(panel._COL_NOMBRE)

    panel.reiniciar()

    assert panel._orden.columna is None


def test_filtro_categoria_acota_la_tabla_por_la_seleccion(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, nombre="Edenor", categoria="Servicios", medio_pago="CA Bco Hipotecario")
    _crear_concepto_unidad(panel, unidad, nombre="Expensas", categoria="Expensas", medio_pago="Transferencia")

    indice = panel.combo_filtro_categoria.findData("Expensas")
    panel.combo_filtro_categoria.setCurrentIndex(indice)

    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, panel._COL_NOMBRE).text() == "Expensas"


def test_filtros_cascada_se_acotan_mutuamente_sin_acotar_la_propia_seleccion(qtbot, conn, unidad):
    """Pedido explícito de la clienta: filtros "en cascada, para elegir
    dentro de los valores que tiene las columnas" — a diferencia de una
    cascada jerárquica (Localidad->Edificio->Unidad), estos 4 filtros no
    tienen jerarquía entre sí: cada combo se acota por la selección de
    los OTROS tres, nunca por la propia (si se acotara a sí mismo,
    elegir un valor haría desaparecer las demás opciones de ese mismo
    combo, imposibilitando cambiar de selección)."""
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, nombre="Edenor", categoria="Servicios", medio_pago="CA Bco Hipotecario")
    _crear_concepto_unidad(panel, unidad, nombre="Expensas", categoria="Expensas", medio_pago="Transferencia")

    indice = panel.combo_filtro_categoria.findData("Expensas")
    panel.combo_filtro_categoria.setCurrentIndex(indice)

    # El combo de Medio de pago se acota por la Categoría elegida: solo
    # queda "Transferencia" (más el "Todos" de siempre).
    valores_medio = {panel.combo_filtro_medio_pago.itemData(i) for i in range(panel.combo_filtro_medio_pago.count())}
    assert valores_medio == {panel._TODOS, "Transferencia"}

    # El propio combo de Categoría, en cambio, sigue mostrando TODAS sus
    # opciones — nunca se acota a sí mismo.
    valores_categoria = {panel.combo_filtro_categoria.itemData(i) for i in range(panel.combo_filtro_categoria.count())}
    assert valores_categoria == {panel._TODOS, "Servicios", "Expensas"}


def test_boton_reiniciar_filtros_vuelve_todos_los_combos_a_todos(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, nombre="Edenor")
    _crear_concepto_unidad(panel, unidad, nombre="AYSA")
    panel.combo_filtro_nombre.setCurrentIndex(panel.combo_filtro_nombre.findData("Edenor"))
    assert panel.tabla.rowCount() == 1

    panel.boton_reiniciar_filtros.click()

    assert panel.tabla.rowCount() == 2
    assert all(combo.currentData() is panel._TODOS for combo in panel._combos_filtro().values())


def test_f5_reiniciar_tambien_reinicia_los_filtros_cascada(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, nombre="Edenor")
    _crear_concepto_unidad(panel, unidad, nombre="AYSA")
    panel.combo_filtro_nombre.setCurrentIndex(panel.combo_filtro_nombre.findData("Edenor"))

    panel.reiniciar()

    assert panel.tabla.rowCount() == 2
    assert all(combo.currentData() is panel._TODOS for combo in panel._combos_filtro().values())


def test_catalogos_anidados_de_afectacion_funcionan(qtbot, conn):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_inmuebles_personales, pantalla.panel_rodados, pantalla.panel_personas):
        assert panel.objectName() == "panelSolapa"
        assert panel.anidado is True


def _instancia_actual(conn, panel, nombre="Edenor"):
    concepto = next(
        c for c in obtener_repositorio(conn, "ConceptoControlPago").listar() if c["Nombre"] == nombre
    )
    return obtener_repositorio(conn, "InstanciaControlPago").listar(
        IdConcepto=concepto["IdConcepto"], Periodo=periodo_actual(conn),
    )[0]


def test_dialogo_editar_instancia_sin_vencimiento_precarga_hoy(qtbot, conn, unidad):
    """Pedido explícito de la clienta: en vez de quedar en "(sin
    fecha)", se precarga con la fecha de hoy — así Flecha arriba/abajo
    (ya instalado por `_campo_fecha`) la mueve cerca de hoy."""
    from app.gui.pantallas.control_pagos import _DialogoEditarInstancia
    from app.negocio.dias import fecha_actual

    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, medio_pago="CA Bco Hipotecario")
    instancia = _instancia_actual(conn, panel)

    dialogo = _DialogoEditarInstancia(conn, instancia, parent=panel)

    hoy = fecha_actual(conn)
    assert dialogo.campo_vencimiento.date().toPython() == hoy
    assert dialogo.campo_vencimiento.isEnabled()


def test_dialogo_editar_instancia_tarjeta_deshabilita_vencimiento(qtbot, conn, unidad):
    from app.gui.pantallas.control_pagos import _DialogoEditarInstancia

    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, medio_pago="Tarjeta Bco Macro")
    instancia = _instancia_actual(conn, panel)

    dialogo = _DialogoEditarInstancia(conn, instancia, parent=panel)

    assert not dialogo.campo_vencimiento.isEnabled()


def test_editar_item_tarjeta_al_cargar_importe_queda_abonado_directo(qtbot, conn, unidad, monkeypatch):
    """Pedido explícito de la clienta: una tarjeta solo admite Importe
    — al cargarlo, la instancia queda Abonada sin pasar por el botón
    "Abonar"."""
    from PySide6.QtWidgets import QDialog

    import app.gui.pantallas.control_pagos as control_pagos_modulo

    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, medio_pago="Tarjeta Bco Macro")
    instancia = _instancia_actual(conn, panel)
    panel.tabla.selectRow(0)

    class _DialogoFalso:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def vencimiento(self):
            return None

        def importe(self):
            return 1500.0

        def cuenta_id(self):
            return None

    monkeypatch.setattr(control_pagos_modulo, "_DialogoEditarInstancia", lambda *a, **k: _DialogoFalso())
    panel._editar_instancia(instancia)

    repo = obtener_repositorio(conn, "InstanciaControlPago")
    assert repo.obtener(instancia["IdInstancia"])["Estado"] == "Abonado"


def test_dialogo_editar_instancia_manual_exige_vencimiento_e_importe_juntos(qtbot, conn, unidad, monkeypatch):
    """Pedido explícito de la clienta: para un medio de pago NO tarjeta
    (débito manual de una caja de ahorro), vencimiento e importe van
    juntos — no se puede aceptar con uno solo cargado."""
    from PySide6.QtWidgets import QMessageBox

    from app.gui.pantallas.control_pagos import _DialogoEditarInstancia

    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, medio_pago="CA Bco Hipotecario")
    instancia = _instancia_actual(conn, panel)

    dialogo = _DialogoEditarInstancia(conn, instancia, parent=panel)
    dialogo.spin_importe.setValue(0)  # vencimiento queda precargado con hoy, importe en blanco
    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: avisos.append(a)))

    dialogo.accept()

    assert len(avisos) == 1
    assert dialogo.result() != dialogo.DialogCode.Accepted


def test_dialogo_editar_instancia_manual_acepta_los_dos_en_blanco(qtbot, conn, unidad):
    from PySide6.QtWidgets import QDialog

    from app.gui.pantallas.control_pagos import _DialogoEditarInstancia

    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, medio_pago="CA Bco Hipotecario")
    instancia = _instancia_actual(conn, panel)

    dialogo = _DialogoEditarInstancia(conn, instancia, parent=panel)
    dialogo.campo_vencimiento.setDate(dialogo.campo_vencimiento.minimumDate())
    dialogo.spin_importe.setValue(0)

    dialogo.accept()

    assert dialogo.result() == QDialog.DialogCode.Accepted


def test_tabla_carga_control_cuenta_id_despues_de_afectacion_y_ancho_igual_a_categoria(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    panel.campo_cuenta_id.setText("12345-6")
    _crear_concepto_unidad(panel, unidad)

    assert panel.tabla.item(0, panel._COL_CUENTA_ID).text() == "12345-6"
    assert panel.tabla.columnWidth(panel._COL_CUENTA_ID) == panel.tabla.columnWidth(panel._COL_CATEGORIA)


def test_tabla_carga_control_importe_un_20_por_ciento_mas_ancho(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)
    ancho_achicado = panel.tabla.columnWidth(panel._COL_IMPORTE)

    panel.tabla.resizeColumnToContents(panel._COL_IMPORTE)

    assert abs(ancho_achicado - round(panel.tabla.columnWidth(panel._COL_IMPORTE) * 1.2)) <= 1


def test_boton_deshacer_deshabilitado_sin_datos_habilitado_con_datos(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, medio_pago="CA Bco Hipotecario")
    boton_deshacer = panel.tabla.cellWidget(0, panel._COL_DESHACER)
    assert not boton_deshacer.isEnabled()

    instancia = _instancia_actual(conn, panel)
    from app.negocio.control_pagos import actualizar_instancia
    actualizar_instancia(conn, instancia["IdInstancia"], vencimiento="2026-12-01", importe=500)
    panel.actualizar()

    boton_deshacer = panel.tabla.cellWidget(0, panel._COL_DESHACER)
    assert boton_deshacer.isEnabled()


def test_deshacer_vacia_vencimiento_e_importe_y_vuelve_a_pendiente(qtbot, conn, unidad):
    from app.negocio.control_pagos import actualizar_instancia

    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, medio_pago="CA Bco Hipotecario")
    instancia = _instancia_actual(conn, panel)
    actualizar_instancia(conn, instancia["IdInstancia"], vencimiento="2026-12-01", importe=500)
    panel.actualizar()

    panel._deshacer(obtener_repositorio(conn, "InstanciaControlPago").obtener(instancia["IdInstancia"]))

    actualizada = obtener_repositorio(conn, "InstanciaControlPago").obtener(instancia["IdInstancia"])
    assert actualizada["Vencimiento"] is None
    assert actualizada["Importe"] is None
    assert actualizada["Estado"] == "Pendiente"


def test_editar_item_archivado_lo_vuelve_a_pendiente(qtbot, conn, unidad, monkeypatch):
    from PySide6.QtWidgets import QDialog

    import app.gui.pantallas.control_pagos as control_pagos_modulo
    from app.negocio.control_pagos import archivar_instancia

    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, medio_pago="CA Bco Hipotecario")
    instancia = _instancia_actual(conn, panel)
    archivar_instancia(conn, instancia["IdInstancia"])
    panel.actualizar()
    instancia_archivada = obtener_repositorio(conn, "InstanciaControlPago").obtener(instancia["IdInstancia"])
    assert instancia_archivada["Estado"] == "Archivado"

    class _DialogoFalso:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def vencimiento(self):
            return "2026-12-05"

        def importe(self):
            return 700.0

        def cuenta_id(self):
            return None

    monkeypatch.setattr(control_pagos_modulo, "_DialogoEditarInstancia", lambda *a, **k: _DialogoFalso())
    panel._editar_instancia(instancia_archivada)

    resultado = obtener_repositorio(conn, "InstanciaControlPago").obtener(instancia["IdInstancia"])
    assert resultado["Estado"] == "Pendiente"


def test_crear_concepto_deja_la_instancia_nueva_seleccionada(qtbot, conn, unidad):
    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad)

    filas = panel.tabla.selectionModel().selectedRows()
    assert len(filas) == 1
    assert panel._registros[filas[0].row()]["IdInstancia"] == _instancia_actual(conn, panel)["IdInstancia"]


def test_etiquetas_de_conteo_reflejan_lo_que_esta_en_pantalla(qtbot, conn, unidad):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-11-15' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    from app.negocio.control_pagos import actualizar_instancia

    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, nombre="Sin datos")
    _crear_concepto_unidad(panel, unidad, nombre="Vence hoy")
    instancia_hoy = _instancia_actual(conn, panel, nombre="Vence hoy")
    actualizar_instancia(conn, instancia_hoy["IdInstancia"], vencimiento="2026-11-15", importe=1000)
    panel.actualizar()

    assert panel.etiqueta_conteo_por_cargar.text() == "Conceptos por cargar: 1"
    assert panel.etiqueta_conteo_vencimiento_hoy.text() == "Con vencimiento hoy: 1"
    assert panel.etiqueta_conteo_total.text() == "Total conceptos: 2"


def test_dialogo_editar_instancia_foco_despues_de_importe_va_al_boton_ok(qtbot, conn, unidad):
    from PySide6.QtWidgets import QDialogButtonBox

    from app.gui.pantallas.control_pagos import _DialogoEditarInstancia

    pantalla = PantallaControlPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_carga_control
    _crear_concepto_unidad(panel, unidad, medio_pago="CA Bco Hipotecario")
    instancia = _instancia_actual(conn, panel)

    dialogo = _DialogoEditarInstancia(conn, instancia, parent=panel)
    boton_ok = None
    for boton in dialogo.findChildren(QDialogButtonBox):
        boton_ok = boton.button(QDialogButtonBox.StandardButton.Ok)
    assert boton_ok in dialogo._foco._orden


def test_spin_importe_control_pagos_acepta_punto_como_decimal(qtbot, conn):
    from app.gui.pantallas.control_pagos import _SpinImporteControlPagos

    spin = _SpinImporteControlPagos()
    qtbot.addWidget(spin)
    spin.setRange(0, 100_000_000)
    spin.setDecimals(2)

    assert spin.valueFromText("1500.50") == 1500.50
    assert spin.valueFromText("1500,50") == 1500.50
