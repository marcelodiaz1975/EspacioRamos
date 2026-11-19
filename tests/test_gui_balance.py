import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.balance import PantallaBalanceDelNegocio
from app.negocio.dias import periodo_actual, periodo_anterior
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


def test_titulo_de_pantalla_es_jerarquia_1(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "BALANCE DEL NEGOCIO"


def test_tiene_formato_solapa_con_las_tres_pestanas_en_orden(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == ["Gastos", "Ingresos", "Resultado"]


def test_solapa_gastos_es_un_panel_bespoke_sin_titulo_propio(qtbot, conn):
    """Pedido explícito de la clienta: rediseño completo de "Gastos",
    ya no es el catálogo genérico `PantallaCRUD` (`catalogos.pantalla_
    gastos_operativos`, ahora de baja)."""
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos
    assert panel.objectName() == "panelSolapa"
    assert panel.findChild(QLabel, "tituloPantalla") is None
    assert panel.boton_nuevo is not None
    assert panel.campo_periodo is not None


def test_solapas_ingresos_y_resultado_usan_el_fondo_claro(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_ingresos.objectName() == "panelSolapa"
    assert pantalla.panel_resultado.objectName() == "panelSolapa"


def test_ingresos_arranca_en_el_periodo_actual_con_una_sola_fila(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ingresos
    assert panel.campo_periodo.periodo() == periodo_actual(conn)
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)
    assert [panel.tabla.horizontalHeaderItem(i).text() for i in range(panel.tabla.columnCount())] == [
        "Período", "Ingreso por horas regulares", "Ingreso por horas aisladas",
        "Ingreso por feriados\ny días especiales", "Total ingresos",
    ]


def test_ingresos_y_resultado_columna_periodo_centrada(qtbot, conn):
    """Pedido explícito de la clienta."""
    from PySide6.QtCore import Qt

    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_ingresos, pantalla.panel_resultado):
        assert panel.tabla.item(0, 0).textAlignment() == Qt.AlignmentFlag.AlignCenter


def test_periodo_es_selector_anio_y_mes_en_linea_en_las_dos_solapas(qtbot, conn):
    """Punto propio de esta vuelta: selector Año+Mes en línea (mismo
    widget que Liquidaciones), no texto libre "AAAA-MM"."""
    from app.gui.widgets.selector_periodo import SelectorPeriodo

    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_ingresos, pantalla.panel_resultado):
        assert isinstance(panel.campo_periodo, SelectorPeriodo)
        assert panel._foco._orden[0] is panel.campo_periodo.spin_anio
        assert panel._foco._orden[1] is panel.campo_periodo.combo_mes


def test_ingresos_filtros_de_ubicacion_arrancan_en_todas_todos(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ingresos
    assert panel.combo_localidad.currentText() == "Todas"
    assert panel.combo_edificio.currentText() == "Todos"
    assert panel.combo_unidad.currentText() == "Todas"
    assert panel.combo_consultorio.currentText() == "Todos"


def test_ingresos_recalcula_al_cambiar_periodo(qtbot, conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000, ValorHoraAisladaActual=500,
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio="2026-01-01", VigenciaFin=None,
    )
    conn.commit()

    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ingresos
    panel.campo_periodo.set_periodo("2026-08")
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 0).text() == "2026-08"
    assert "$ 10.000,00" in panel.tabla.item(0, 1).text()


def test_resultado_arranca_en_el_periodo_actual_con_una_sola_fila(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_resultado
    assert panel.campo_periodo.periodo() == periodo_actual(conn)
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)
    assert [panel.tabla.horizontalHeaderItem(i).text() for i in range(panel.tabla.columnCount())] == [
        "Período", "Total ingresos", "Total gastos", "Balance del período",
    ]


def test_resultado_prorratea_gastos_generales_al_filtrar_por_consultorio(qtbot, conn):
    """Desde que Gastos reparte en cascada (ver `app.negocio.balance`),
    filtrar por un consultorio puntual ya no excluye los gastos
    "Espacio general" — le llega la porción prorateada que le
    corresponde en la cascada. Acá hay dos edificios, así que cada uno
    (y cada consultorio) se queda con la mitad."""
    id_edificio_1 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad_1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_1, Departamento="1")
    id_consultorio_1 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad_1, NumeroConsultorio=1, ValorHoraRegularActual=1000, ValorHoraAisladaActual=500,
    )
    id_edificio_2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2")
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_2, Departamento="1")
    obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad_2, NumeroConsultorio=1, ValorHoraRegularActual=1000, ValorHoraAisladaActual=500,
    )
    periodo = periodo_actual(conn)
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=periodo, Categoria="Alquiler", Monto=3000, Alcance="Espacio general",
    )
    conn.commit()

    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_resultado
    assert "-$ 3.000,00" in panel.tabla.item(0, 2).text()

    panel.combo_edificio.setCurrentIndex(panel.combo_edificio.findData(id_edificio_1))
    panel.combo_consultorio.setCurrentIndex(panel.combo_consultorio.findData(id_consultorio_1))
    assert "-$ 1.500,00" in panel.tabla.item(0, 2).text()


def test_botones_historial_y_periodo_actual_tienen_los_estilos_correctos(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_ingresos, pantalla.panel_resultado):
        assert panel.boton_historial.text() == "Ver historial"
        assert panel.boton_historial.objectName() == "botonPrimario"
        assert panel.boton_periodo_actual.text() == "Ver período actual"
        assert panel.boton_periodo_actual.objectName() == "botonSecundario"
        assert panel.boton_historial.width() == panel.boton_periodo_actual.width() == panel.campo_periodo.width()


def test_ingresos_ver_historial_muestra_todos_los_periodos_mas_nuevo_arriba(qtbot, conn):
    actual = periodo_actual(conn)
    anterior = periodo_anterior(actual)
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000, ValorHoraAisladaActual=500,
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio=f"{anterior}-01", VigenciaFin=None,
    )
    conn.commit()

    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ingresos
    panel.boton_historial.click()
    assert panel.tabla.rowCount() == 2
    assert panel.tabla.item(0, 0).text() == actual
    assert panel.tabla.item(1, 0).text() == anterior


def test_ingresos_ver_periodo_actual_vuelve_a_una_sola_fila(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ingresos
    panel.campo_periodo.set_periodo("2020-01")
    panel.boton_historial.click()
    assert panel.tabla.rowCount() >= 1

    panel.boton_periodo_actual.click()
    assert panel.campo_periodo.periodo() == periodo_actual(conn)
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)


def test_ingresos_reiniciar_vuelve_periodo_y_localidad_al_inicial(qtbot, conn):
    """F5: `_PanelIngresos` no tenía ningún `reiniciar()` propio — a
    diferencia de "Ver período actual", esto también vuelve la cascada
    de ubicación a "Todas/Todos"."""
    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Ramos 1")
    conn.commit()
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ingresos
    panel.campo_periodo.set_periodo("2020-01")
    panel.combo_localidad.setCurrentIndex(panel.combo_localidad.findData(id_localidad))
    assert panel.combo_localidad.currentData() == id_localidad

    panel.reiniciar()

    assert panel.campo_periodo.periodo() == periodo_actual(conn)
    assert panel.combo_localidad.currentText() == "Todas"


def test_resultado_ver_historial_muestra_todos_los_periodos_mas_nuevo_arriba(qtbot, conn):
    actual = periodo_actual(conn)
    anterior = periodo_anterior(actual)
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000, ValorHoraAisladaActual=500,
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio=f"{anterior}-01", VigenciaFin=None,
    )
    conn.commit()

    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_resultado
    panel.boton_historial.click()
    assert panel.tabla.rowCount() == 2
    assert panel.tabla.item(0, 0).text() == actual
    assert panel.tabla.item(1, 0).text() == anterior


def test_resultado_ver_periodo_actual_vuelve_a_una_sola_fila(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_resultado
    panel.campo_periodo.set_periodo("2020-01")
    panel.boton_historial.click()
    assert panel.tabla.rowCount() >= 1

    panel.boton_periodo_actual.click()
    assert panel.campo_periodo.periodo() == periodo_actual(conn)
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)


def test_resultado_reiniciar_vuelve_periodo_y_localidad_al_inicial(qtbot, conn):
    """F5: `_PanelResultado` no tenía ningún `reiniciar()` propio."""
    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Ramos 1")
    conn.commit()
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_resultado
    panel.campo_periodo.set_periodo("2020-01")
    panel.combo_localidad.setCurrentIndex(panel.combo_localidad.findData(id_localidad))
    assert panel.combo_localidad.currentData() == id_localidad

    panel.reiniciar()

    assert panel.campo_periodo.periodo() == periodo_actual(conn)
    assert panel.combo_localidad.currentText() == "Todas"


def _completar_dialogo_gasto(dialogo, *, nombre="Limpieza", monto=1000, categoria=None, alcance=None, id_destino=None):
    dialogo.campo_nombre.setText(nombre)
    dialogo.spin_monto.setValue(monto)
    if categoria is not None:
        dialogo.combo_categoria.setCurrentText(categoria)
    if alcance is not None:
        dialogo.combo_afectacion.setCurrentIndex(dialogo.combo_afectacion.findData(alcance))
    if alcance == "Localidad":
        dialogo.combo_localidad.setCurrentIndex(dialogo.combo_localidad.findData(id_destino))
    elif alcance == "Edificio":
        dialogo.combo_edificio.setCurrentIndex(dialogo.combo_edificio.findData(id_destino))
    elif alcance == "Unidad":
        dialogo.combo_unidad.setCurrentIndex(dialogo.combo_unidad.findData(id_destino))
    elif alcance == "Consultorio":
        dialogo.combo_consultorio.setCurrentIndex(dialogo.combo_consultorio.findData(id_destino))


def test_gastos_tabla_columnas_en_el_orden_pedido(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos
    assert [panel.tabla.horizontalHeaderItem(i).text() for i in range(panel.tabla.columnCount())] == [
        "Período", "Nombre", "Categoría", "Afectación", "Monto", "Origen", "Observación",
    ]


def test_gastos_columna_periodo_al_minimo_y_centrada(qtbot, conn):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFontMetrics

    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=periodo_actual(conn), Concepto="Limpieza", Monto=1000, Alcance="Espacio general", Origen="Manual",
    )
    panel.actualizar()

    ancho_esperado = QFontMetrics(panel.tabla.horizontalHeader().font()).horizontalAdvance("Período") + 12
    assert panel.tabla.columnWidth(0) == ancho_esperado
    assert panel.tabla.item(0, 0).textAlignment() == Qt.AlignmentFlag.AlignCenter


def test_gastos_se_ordena_por_periodo_afectacion_categoria_y_nombre(qtbot, conn):
    periodo = periodo_actual(conn)
    repo = obtener_repositorio(conn, "GastoOperativo")
    repo.crear(Periodo=periodo, Concepto="Zeta", Categoria="B", Monto=1, Alcance="Espacio general", Origen="Manual")
    repo.crear(Periodo=periodo, Concepto="Alfa", Categoria="B", Monto=1, Alcance="Espacio general", Origen="Manual")
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    repo.crear(
        Periodo=periodo, Concepto="Beta", Categoria="A", Monto=1, Alcance="Edificio", IdEdificio=id_edificio,
        Origen="Manual",
    )

    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos

    nombres = [panel.tabla.item(f, 1).text() for f in range(panel.tabla.rowCount())]
    # "Espacio general" ordena antes que "Ramos 1" (afectación), y dentro
    # de "Espacio general" (misma categoría "B") Alfa antes que Zeta.
    assert nombres == ["Alfa", "Zeta", "Beta"]


def test_gastos_nuevo_crea_concepto_manual_con_afectacion_localidad(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from app.gui.pantallas.balance import _DialogoGasto

    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Ramos Mejía")
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos

    def _exec(self):
        _completar_dialogo_gasto(self, nombre="Publicidad", monto=2000, alcance="Localidad", id_destino=id_localidad)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoGasto, "exec", _exec)
    panel._nuevo()

    gastos = obtener_repositorio(conn, "GastoOperativo").listar()
    assert len(gastos) == 1
    assert gastos[0]["Concepto"] == "Publicidad"
    assert gastos[0]["Monto"] == 2000
    assert gastos[0]["Alcance"] == "Localidad"
    assert gastos[0]["IdLocalidad"] == id_localidad
    assert gastos[0]["Origen"] == "Manual"
    assert panel.tabla.item(0, 3).text() == "Ramos Mejía"


def test_gastos_editar_bloqueado_para_origen_importado_con_alerta(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    periodo = periodo_actual(conn)
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=periodo, Concepto="Edenor", Monto=500, Alcance="Espacio general", Origen="Importado",
    )
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos
    panel.tabla.selectRow(0)

    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: avisos.append(a)))
    panel._editar()

    assert len(avisos) == 1
    assert "Carga y control" in avisos[0][2]
    gasto = obtener_repositorio(conn, "GastoOperativo").listar()[0]
    assert gasto["Monto"] == 500  # no cambió


def test_gastos_editar_permite_origen_manual(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from app.gui.pantallas.balance import _DialogoGasto

    periodo = periodo_actual(conn)
    id_gasto = obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=periodo, Concepto="Limpieza", Monto=500, Alcance="Espacio general", Origen="Manual",
    )
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos
    panel.tabla.selectRow(0)

    def _exec(self):
        self.spin_monto.setValue(900)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoGasto, "exec", _exec)
    panel._editar()

    gasto = obtener_repositorio(conn, "GastoOperativo").obtener(id_gasto)
    assert gasto["Monto"] == 900


def test_gastos_eliminar_pide_confirmacion_y_borra(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    periodo = periodo_actual(conn)
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=periodo, Concepto="Limpieza", Monto=500, Alcance="Espacio general", Origen="Manual",
    )
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos
    panel.tabla.selectRow(0)

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel._eliminar()

    assert obtener_repositorio(conn, "GastoOperativo").listar() == []


def test_gastos_conflicto_de_origen_reemplaza_si_se_confirma(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QDialog, QMessageBox

    from app.gui.pantallas.balance import _DialogoGasto

    periodo = periodo_actual(conn)
    id_anterior = obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=periodo, Concepto="Limpieza", Monto=500, Alcance="Espacio general", Origen="Importado",
    )
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos

    def _exec(self):
        _completar_dialogo_gasto(self, nombre="Limpieza", monto=800)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoGasto, "exec", _exec)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel._nuevo()

    gastos = obtener_repositorio(conn, "GastoOperativo").listar()
    assert len(gastos) == 1
    assert gastos[0]["Origen"] == "Manual"
    assert gastos[0]["Monto"] == 800
    assert obtener_repositorio(conn, "GastoOperativo").obtener(id_anterior) is None


def test_gastos_subtotal_en_negrita_y_no_lo_tocan_los_filtros(qtbot, conn):
    from app.negocio.formato import formatear_moneda

    periodo = periodo_actual(conn)
    repo = obtener_repositorio(conn, "GastoOperativo")
    repo.crear(Periodo=periodo, Concepto="Luz", Monto=1000, Alcance="Espacio general", Origen="Manual")
    repo.crear(Periodo=periodo, Concepto="Agua", Monto=500, Alcance="Espacio general", Origen="Manual")

    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos

    assert panel.etiqueta_titulo_subtotal.styleSheet() == "font-weight: bold;"
    assert panel.etiqueta_subtotal.styleSheet() == "font-weight: bold;"
    assert panel.etiqueta_subtotal.text() == formatear_moneda(1500)

    indice = panel.combo_filtro_nombre.findData("Luz")
    panel.combo_filtro_nombre.setCurrentIndex(indice)
    assert panel.tabla.rowCount() == 1  # la tabla sí se filtra...
    assert panel.etiqueta_subtotal.text() == formatear_moneda(1500)  # ...el subtotal no


def test_gastos_filtros_cuarta_columna_cascada_y_reiniciar(qtbot, conn):
    periodo = periodo_actual(conn)
    repo = obtener_repositorio(conn, "GastoOperativo")
    repo.crear(
        Periodo=periodo, Concepto="Luz", Categoria="Servicios", Monto=1000, Alcance="Espacio general",
        Origen="Manual",
    )
    repo.crear(
        Periodo=periodo, Concepto="Sueldo", Categoria="Personal", Monto=2000, Alcance="Espacio general",
        Origen="Manual",
    )

    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos
    assert panel.tabla.rowCount() == 2

    indice = panel.combo_filtro_categoria.findData("Servicios")
    panel.combo_filtro_categoria.setCurrentIndex(indice)
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 1).text() == "Luz"
    # cascada mutua: el filtro de Nombre ya no ofrece "Sueldo".
    opciones_nombre = [panel.combo_filtro_nombre.itemText(i) for i in range(panel.combo_filtro_nombre.count())]
    assert "Sueldo" not in opciones_nombre

    panel.boton_reiniciar_filtros.click()
    assert panel.combo_filtro_categoria.currentText() == "Todas"
    assert panel.tabla.rowCount() == 2


def test_gastos_f5_reinicia_periodo_filtros_y_seleccion(qtbot, conn):
    periodo = periodo_actual(conn)
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=periodo, Concepto="Limpieza", Monto=500, Alcance="Espacio general", Origen="Manual",
    )
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos
    panel.campo_periodo.set_periodo("2020-01")
    panel.tabla.selectRow(0) if panel.tabla.rowCount() else None

    panel.reiniciar()

    assert panel.campo_periodo.periodo() == periodo_actual(conn)
    assert not panel.tabla.selectionModel().selectedRows()


def test_dialogo_gasto_categoria_ofrece_las_de_control_de_pagos(qtbot, conn):
    from app.gui.pantallas.balance import _DialogoGasto
    from app.negocio.listas_editables import valores_lista

    obtener_repositorio(conn, "ListasEditables").crear(TipoLista="CategoriaControlPagos", Valor="Servicios", Orden=0)
    dialogo = _DialogoGasto(conn)
    qtbot.addWidget(dialogo)
    opciones = [dialogo.combo_categoria.itemText(i) for i in range(dialogo.combo_categoria.count())]
    assert opciones == valores_lista(conn, "CategoriaControlPagos")
    assert dialogo.combo_categoria.isEditable() is True


def test_dialogo_gasto_afectacion_habilita_solo_el_combo_correspondiente(qtbot, conn):
    from app.gui.pantallas.balance import _DialogoGasto

    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Ramos Mejía")
    dialogo = _DialogoGasto(conn)
    qtbot.addWidget(dialogo)

    dialogo.combo_afectacion.setCurrentIndex(dialogo.combo_afectacion.findData("Localidad"))
    assert dialogo.combo_localidad.isEnabled() is True
    assert dialogo.combo_edificio.isEnabled() is False
    assert dialogo.combo_edificio.currentData() is None
    assert dialogo.combo_unidad.isEnabled() is False
    assert dialogo.combo_consultorio.isEnabled() is False
    dialogo.combo_localidad.setCurrentIndex(dialogo.combo_localidad.findData(id_localidad))

    dialogo.combo_afectacion.setCurrentIndex(dialogo.combo_afectacion.findData("Espacio general"))
    assert dialogo.combo_localidad.isEnabled() is False
    assert dialogo.combo_localidad.currentData() is None


def test_dialogo_gasto_origen_es_siempre_manual_y_no_editable(qtbot, conn):
    """Pedido explícito de la clienta: el diálogo no tiene ningún combo
    de Origen — siempre guarda "Manual", sin forma de elegir otra cosa."""
    from app.gui.pantallas.balance import _DialogoGasto

    dialogo = _DialogoGasto(conn)
    qtbot.addWidget(dialogo)
    assert not hasattr(dialogo, "combo_origen")
    assert dialogo.valores()["Origen"] == "Manual"


def test_dialogo_gasto_editar_precarga_valores_existentes(qtbot, conn):
    from app.gui.pantallas.balance import _DialogoGasto

    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_gasto = obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo="2026-08", Concepto="Seguridad", Categoria="Servicios", Monto=1200, Alcance="Edificio",
        IdEdificio=id_edificio, Origen="Manual", Observacion="Guardia nocturna",
    )
    gasto = obtener_repositorio(conn, "GastoOperativo").obtener(id_gasto)
    dialogo = _DialogoGasto(conn, gasto=gasto)
    qtbot.addWidget(dialogo)

    assert dialogo.campo_periodo.periodo() == "2026-08"
    assert dialogo.campo_nombre.text() == "Seguridad"
    assert dialogo.combo_categoria.currentText() == "Servicios"
    assert dialogo.spin_monto.value() == 1200
    assert dialogo.combo_afectacion.currentData() == "Edificio"
    assert dialogo.combo_edificio.currentData() == id_edificio
    assert dialogo.combo_edificio.isEnabled() is True
    assert dialogo.campo_observacion.toPlainText() == "Guardia nocturna"


def test_las_tres_solapas_tienen_reiniciar_para_f5(qtbot, conn):
    """Chequeo pedido explícitamente por la clienta: F5 tiene que poder
    devolver cada solapa de "Balance del negocio" a su estado inicial."""
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_gastos, pantalla.panel_ingresos, pantalla.panel_resultado):
        assert hasattr(panel, "reiniciar")
        panel.reiniciar()  # no debe tirar ningún error


def test_gastos_nuevo_editar_y_eliminar_muestran_alerta_de_exito(qtbot, conn, monkeypatch):
    """Chequeo pedido explícitamente por la clienta: los tres botones de
    acción de "Gastos" (la única solapa de este formulario con botones
    que modifican datos — Ingresos/Resultado son 100% de lectura, sin
    ninguna acción que alertar) muestran su alerta de proceso completado."""
    from PySide6.QtWidgets import QDialog

    from app.gui.pantallas.balance import _DialogoGasto

    avisos = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: avisos.append(a[2])))

    periodo = periodo_actual(conn)
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=periodo, Concepto="Limpieza", Monto=500, Alcance="Espacio general", Origen="Manual",
    )
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos

    def _exec(self):
        _completar_dialogo_gasto(self, nombre="Agua", monto=300)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoGasto, "exec", _exec)
    panel._nuevo()
    assert avisos and "éxito" in avisos[-1]
    assert len(obtener_repositorio(conn, "GastoOperativo").listar()) == 2

    panel.tabla.selectRow(0)
    monkeypatch.setattr(_DialogoGasto, "exec", lambda self: QDialog.DialogCode.Accepted)
    panel._editar()
    assert "éxito" in avisos[-1]

    panel.tabla.selectRow(0)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel._eliminar()
    assert "éxito" in avisos[-1]
    assert len(obtener_repositorio(conn, "GastoOperativo").listar()) == 1
