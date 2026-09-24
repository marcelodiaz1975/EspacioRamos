import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.balance import PantallaBalanceDelNegocio
from app.negocio.dias import periodo_actual
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


def test_ingresos_arranca_en_el_periodo_actual_y_muestra_las_tres_partes(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ingresos
    assert panel.campo_periodo.text() == periodo_actual(conn)
    assert "Ingresos por horas regulares" in panel.etiqueta_regulares.text()
    assert "Ingresos por horas aisladas" in panel.etiqueta_aisladas.text()
    assert "Ingresos por feriados trabajados" in panel.etiqueta_feriados_trabajados.text()
    assert "Total ingresos" in panel.etiqueta_total.text()


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
    assert "$ 10.000,00" in panel.etiqueta_regulares.text()


def test_resultado_muestra_ingresos_gastos_y_resultado(qtbot, conn):
    pantalla = PantallaBalanceDelNegocio(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_resultado
    assert "Ingresos totales" in panel.etiqueta_ingresos.text()
    assert "Gastos totales" in panel.etiqueta_gastos.text()
    assert "Resultado" in panel.etiqueta_resultado.text()


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
    assert "$ 3.000,00" in panel.etiqueta_gastos.text()

    panel.combo_edificio.setCurrentIndex(panel.combo_edificio.findData(id_edificio))
    panel.combo_consultorio.setCurrentIndex(panel.combo_consultorio.findData(id_consultorio))
    assert "$ 0,00" in panel.etiqueta_gastos.text()
