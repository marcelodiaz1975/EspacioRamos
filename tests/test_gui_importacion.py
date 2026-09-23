import pytest
from PySide6.QtWidgets import QFileDialog, QHeaderView, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.importacion import _PanelImportacion


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))


def _planilla_minima(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Edificio")
    ws.append(["Nombre", "Domicilio"])
    ws.append(["Torre Norte", "Calle 1"])
    ruta = tmp_path / "planilla.xlsx"
    wb.save(ruta)
    return str(ruta)


def test_boton_importar_deshabilitado_sin_archivo(qtbot, conn):
    panel = _PanelImportacion(conn)
    qtbot.addWidget(panel)
    assert panel.boton_importar.isEnabled() is False


def test_importar_carga_datos_y_llena_tabla_resultados(qtbot, conn, tmp_path):
    panel = _PanelImportacion(conn)
    qtbot.addWidget(panel)
    panel.campo_ruta.setText(_planilla_minima(tmp_path))
    panel._importar()

    assert panel.tabla_resultados.rowCount() == 1
    assert panel.tabla_resultados.item(0, 0).text() == "Edificio"
    assert panel.tabla_resultados.item(0, 1).text() == "1"
    assert conn.execute("SELECT COUNT(*) c FROM Edificio").fetchone()["c"] == 1


def test_importar_sin_problemas_muestra_sin_observaciones(qtbot, conn, tmp_path):
    panel = _PanelImportacion(conn)
    qtbot.addWidget(panel)
    panel.campo_ruta.setText(_planilla_minima(tmp_path))
    panel._importar()
    assert panel.texto_integridad.toPlainText() == "Sin observaciones."


def test_informe_muestra_codigo_duplicado(qtbot, conn, tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Profesional")
    ws.append(["CategoriaProfesional", "IdCodigo", "Apellido"])
    ws.append(["R", "R1", "Perez"])
    ws.append(["R", "R1", "Gomez"])
    ruta = tmp_path / "planilla.xlsx"
    wb.save(ruta)

    panel = _PanelImportacion(conn)
    qtbot.addWidget(panel)
    panel.campo_ruta.setText(str(ruta))
    panel._importar()

    assert "R1" in panel.texto_integridad.toPlainText()
    assert "duplicado" in panel.texto_integridad.toPlainText()


# ---------------------------------------- formato panel de solapa (revisión "uno por uno")
# Desde el reordenamiento de formularios, _PanelImportacion ya no es una
# pantalla propia con su propio QTabWidget: es la solapa "Importación datos
# desde Excel" de Panel de control (ver panel_control.py), así que ya no
# tiene sentido un test de "una sola pestaña" — sigue teniendo su propio
# objectName="panelSolapa", verificado abajo.


def test_es_un_panel_solapa(qtbot, conn):
    panel = _PanelImportacion(conn)
    qtbot.addWidget(panel)
    assert panel.objectName() == "panelSolapa"


def test_importar_es_primario_elegir_y_descargar_son_secundarios(qtbot, conn):
    panel = _PanelImportacion(conn)
    qtbot.addWidget(panel)
    assert panel.boton_importar.objectName() == "botonPrimario"
    assert panel.boton_elegir.objectName() == "botonSecundario"
    assert panel.boton_descargar_plantilla.objectName() == "botonSecundario"


def test_orden_de_los_botones_es_descargar_elegir_importar(qtbot, conn):
    panel = _PanelImportacion(conn)
    qtbot.addWidget(panel)
    assert panel._foco._orden == [
        panel.boton_descargar_plantilla, panel.boton_elegir, panel.boton_importar,
    ]


def test_foco_inicial_queda_en_descargar_planilla(qtbot, conn):
    panel = _PanelImportacion(conn)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitExposed(panel)
    qtbot.waitUntil(lambda: panel.boton_descargar_plantilla.hasFocus())


def test_descargar_plantilla_genera_el_excel_en_el_destino_elegido(qtbot, conn, tmp_path, monkeypatch):
    destino = tmp_path / "plantilla.xlsx"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))
    panel = _PanelImportacion(conn)
    qtbot.addWidget(panel)

    panel._descargar_plantilla()

    assert destino.is_file()


def test_descargar_plantilla_cancelada_no_genera_nada(qtbot, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    panel = _PanelImportacion(conn)
    qtbot.addWidget(panel)

    panel._descargar_plantilla()

    assert list(tmp_path.glob("*.xlsx")) == []


def test_columnas_de_resultado_se_estiran_para_ocupar_todo_el_ancho(qtbot, conn):
    panel = _PanelImportacion(conn)
    qtbot.addWidget(panel)
    header = panel.tabla_resultados.horizontalHeader()
    for columna in range(panel.tabla_resultados.columnCount()):
        assert header.sectionResizeMode(columna) == QHeaderView.ResizeMode.Stretch
