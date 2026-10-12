import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import hoja_estilos
from app.gui.pantallas.aumentos import _PanelAumentos, _PanelEsquemaDescuentos
from app.gui.pantallas.grilla_operativa import _PanelValoresVigentes
from app.gui.pantallas.valores import PantallaValores
from app.negocio.formato import formatear_moneda
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


def test_titulo_de_pantalla_es_jerarquia_1(qtbot, conn):
    pantalla = PantallaValores(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "VALORES"


def test_tiene_formato_solapa_con_las_tres_pestanas_en_orden(qtbot, conn):
    pantalla = PantallaValores(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == [
        "Valores vigentes", "Aumentos", "Esquema de descuentos",
    ]


def test_las_tres_solapas_son_los_paneles_esperados(qtbot, conn):
    pantalla = PantallaValores(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla.panel_valores_vigentes, _PanelValoresVigentes)
    assert isinstance(pantalla.panel_aumentos, _PanelAumentos)
    assert isinstance(pantalla.panel_esquema, _PanelEsquemaDescuentos)
    for panel in (pantalla.panel_valores_vigentes, pantalla.panel_aumentos, pantalla.panel_esquema):
        assert panel.objectName() == "panelSolapa"


def _cargar_consultorios(conn):
    id_loc = obtener_repositorio(conn, "Localidad").crear(Localidad="Ramos Mejía")
    id_ed = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", IdLocalidad=id_loc)
    id_un1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_ed, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_un1, NumeroConsultorio=1, ValorHoraRegularActual=1500, ValorHoraAisladaActual=700,
    )
    id_un2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_ed, Departamento='PB "D"')
    obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_un2, NumeroConsultorio=2, ValorHoraRegularActual=1800, ValorHoraAisladaActual=850,
    )
    conn.commit()


def test_promedios_localidad_y_edificio_mas_anchas_que_sin_padding(qtbot, conn):
    _cargar_consultorios(conn)
    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    promedios = panel.promedios_valores
    sin_padding_localidad = promedios.tabla.sizeHintForColumn(0)
    sin_padding_edificio = promedios.tabla.sizeHintForColumn(1)
    assert promedios.tabla.columnWidth(0) == sin_padding_localidad + 20
    assert promedios.tabla.columnWidth(1) == sin_padding_edificio + 20


def test_promedios_sin_espacio_en_blanco_tras_la_ultima_columna(qtbot, conn):
    _cargar_consultorios(conn)
    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    promedios = panel.promedios_valores
    ancho_columnas = sum(promedios.tabla.columnWidth(i) for i in range(promedios.tabla.columnCount()))
    assert promedios.tabla.width() == ancho_columnas + 2 * promedios.tabla.frameWidth() + 2


def test_valores_vigentes_muestra_columna_con_recargo(qtbot, conn):
    """Pedido explícito de la clienta: "si activo un porcentaje de
    recargo en horas aisladas, no me lo cambia en el formulario de
    valores" — se suma una columna nueva al lado de "Valor aislada" en
    vez de pisarla (el recargo es opcional por reserva, `AplicaRecargo`,
    no algo que siempre corresponda al valor de referencia)."""
    _cargar_consultorios(conn)
    conn.execute("UPDATE Configuracion SET RecargoPorcentajeAisladas = 10 WHERE IdConfiguracion = 1")
    conn.commit()
    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    tabla = panel.tabla_valores
    assert tabla.horizontalHeaderItem(6).text() == "Valor aislada\ncon recargo"
    # Consultorios de `_cargar_consultorios`: $700 y $850 de valor base —
    # con 10% de recargo, $770 y $935.
    valores_base = {tabla.item(f, 5).text() for f in range(tabla.rowCount())}
    valores_recargo = {tabla.item(f, 6).text() for f in range(tabla.rowCount())}
    assert valores_base == {formatear_moneda(700), formatear_moneda(850)}
    assert valores_recargo == {formatear_moneda(770), formatear_moneda(935)}


def test_valores_vigentes_sin_recargo_configurado_columna_nueva_igual_a_la_base(qtbot, conn):
    _cargar_consultorios(conn)
    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    tabla = panel.tabla_valores
    for fila in range(tabla.rowCount()):
        assert tabla.item(fila, 6).text() == tabla.item(fila, 5).text()


def test_valores_vigentes_sin_scroll_horizontal_con_estilo_real_aplicado(qtbot, conn):
    # Reproduce el bug real reportado por la clienta: `_PanelValoresVigentes`
    # arma sus tablas durante `__init__`, ANTES de colgar de verdad de
    # `VentanaPrincipal` (que recién ahí le cascadea el `setStyleSheet` que
    # se pone sobre SÍ MISMA, no sobre la `QApplication`) — con la fuente
    # todavía sin estilar, los anchos calculados en la construcción
    # quedaban cortos para el texto bold/14px real de los encabezados, y
    # las dos tablas terminaban con scroll horizontal. `_PanelPromedios.
    # showEvent` lo corrige recalculando una vez más al mostrarse de
    # verdad, ya con el estilo puesto (mismo mecanismo que
    # `pantalla.setStyleSheet(...)` + `qtbot.waitExposed` en Reservas).
    _cargar_consultorios(conn)
    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    panel.setStyleSheet(hoja_estilos(modo_oscuro=False))  # solo este panel, no toda la app
    panel.resize(1500, 400)
    panel.show()
    qtbot.waitExposed(panel)
    assert panel.promedios_valores.tabla.horizontalScrollBar().maximum() == 0
    assert panel.tabla_valores.horizontalScrollBar().maximum() == 0
