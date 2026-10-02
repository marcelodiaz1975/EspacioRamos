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


def test_solapa_gastos_es_el_catalogo_anidado_sin_titulo_propio(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_gastos
    assert panel.objectName() == "panelSolapa"
    assert panel.anidado is True
    assert panel.findChild(QLabel, "tituloPantalla") is None
    assert panel.campo_buscar is not None


def test_solapas_ingresos_y_resultado_usan_el_fondo_claro(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_ingresos.objectName() == "panelSolapa"
    assert pantalla.panel_resultado.objectName() == "panelSolapa"


def test_ingresos_arranca_en_el_periodo_actual_con_una_sola_fila(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ingresos
    assert panel.campo_periodo.text() == periodo_actual(conn)
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)
    assert [panel.tabla.horizontalHeaderItem(i).text() for i in range(panel.tabla.columnCount())] == [
        "Período", "Ingreso por horas regulares", "Ingreso por horas aisladas",
        "Ingreso por feriados\ny días especiales", "Total ingresos",
    ]


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
    panel.campo_periodo.setText("2026-08")
    panel.campo_periodo.editingFinished.emit()
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 0).text() == "2026-08"
    assert "$ 10.000,00" in panel.tabla.item(0, 1).text()


def test_resultado_arranca_en_el_periodo_actual_con_una_sola_fila(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_resultado
    assert panel.campo_periodo.text() == periodo_actual(conn)
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)
    assert [panel.tabla.horizontalHeaderItem(i).text() for i in range(panel.tabla.columnCount())] == [
        "Período", "Total ingresos", "Total gastos", "Balance del período",
    ]


def test_resultado_excluye_gastos_generales_al_filtrar_por_consultorio(qtbot, conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000, ValorHoraAisladaActual=500,
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

    panel.combo_edificio.setCurrentIndex(panel.combo_edificio.findData(id_edificio))
    panel.combo_consultorio.setCurrentIndex(panel.combo_consultorio.findData(id_consultorio))
    assert "$ 0,00" in panel.tabla.item(0, 2).text()


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
    panel.campo_periodo.setText("2020-01")
    panel.boton_historial.click()
    assert panel.tabla.rowCount() >= 1

    panel.boton_periodo_actual.click()
    assert panel.campo_periodo.text() == periodo_actual(conn)
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)


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
    panel.campo_periodo.setText("2020-01")
    panel.boton_historial.click()
    assert panel.tabla.rowCount() >= 1

    panel.boton_periodo_actual.click()
    assert panel.campo_periodo.text() == periodo_actual(conn)
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)
