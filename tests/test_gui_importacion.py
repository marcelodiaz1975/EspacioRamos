import pytest
from PySide6.QtWidgets import QFileDialog, QHeaderView, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.importacion import PantallaImportacion


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
    pantalla = PantallaImportacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_importar.isEnabled() is False


def test_importar_carga_datos_y_llena_tabla_resultados(qtbot, conn, tmp_path):
    pantalla = PantallaImportacion(conn)
    qtbot.addWidget(pantalla)
    pantalla.campo_ruta.setText(_planilla_minima(tmp_path))
    pantalla._importar()

    assert pantalla.tabla_resultados.rowCount() == 1
    assert pantalla.tabla_resultados.item(0, 0).text() == "Edificio"
    assert pantalla.tabla_resultados.item(0, 1).text() == "1"
    assert conn.execute("SELECT COUNT(*) c FROM Edificio").fetchone()["c"] == 1


def test_importar_sin_problemas_muestra_sin_observaciones(qtbot, conn, tmp_path):
    pantalla = PantallaImportacion(conn)
    qtbot.addWidget(pantalla)
    pantalla.campo_ruta.setText(_planilla_minima(tmp_path))
    pantalla._importar()
    assert pantalla.texto_integridad.toPlainText() == "Sin observaciones."


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

    pantalla = PantallaImportacion(conn)
    qtbot.addWidget(pantalla)
    pantalla.campo_ruta.setText(str(ruta))
    pantalla._importar()

    assert "R1" in pantalla.texto_integridad.toPlainText()
    assert "duplicado" in pantalla.texto_integridad.toPlainText()


# ---------------------------------------- formato solapa (revisión "uno por uno")


def test_tiene_formato_solapa_con_una_pestana(qtbot, conn):
    pantalla = PantallaImportacion(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert solapas.count() == 1
    assert solapas.tabText(0) == "Importación"


def test_importar_es_primario_elegir_y_descargar_son_secundarios(qtbot, conn):
    pantalla = PantallaImportacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_importar.objectName() == "botonPrimario"
    assert pantalla.boton_elegir.objectName() == "botonSecundario"
    assert pantalla.boton_descargar_plantilla.objectName() == "botonSecundario"


def test_orden_de_los_botones_es_descargar_elegir_importar(qtbot, conn):
    pantalla = PantallaImportacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla._foco._orden == [
        pantalla.boton_descargar_plantilla, pantalla.boton_elegir, pantalla.boton_importar,
    ]


def test_foco_inicial_queda_en_descargar_planilla(qtbot, conn):
    pantalla = PantallaImportacion(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.boton_descargar_plantilla.hasFocus())


def test_descargar_plantilla_genera_el_excel_en_el_destino_elegido(qtbot, conn, tmp_path, monkeypatch):
    destino = tmp_path / "plantilla.xlsx"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))
    pantalla = PantallaImportacion(conn)
    qtbot.addWidget(pantalla)

    pantalla._descargar_plantilla()

    assert destino.is_file()


def test_descargar_plantilla_cancelada_no_genera_nada(qtbot, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    pantalla = PantallaImportacion(conn)
    qtbot.addWidget(pantalla)

    pantalla._descargar_plantilla()

    assert list(tmp_path.glob("*.xlsx")) == []


def test_columnas_de_resultado_se_estiran_para_ocupar_todo_el_ancho(qtbot, conn):
    pantalla = PantallaImportacion(conn)
    qtbot.addWidget(pantalla)
    header = pantalla.tabla_resultados.horizontalHeader()
    for columna in range(pantalla.tabla_resultados.columnCount()):
        assert header.sectionResizeMode(columna) == QHeaderView.ResizeMode.Stretch
