import pytest
from openpyxl import load_workbook

from app.db.init_db import init_database
from app.importacion.importar_excel import importar_planilla
from app.importacion.plantillas import generar_plantillas
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    yield connection
    connection.close()


def test_generar_plantilla_crea_una_hoja_por_entidad(tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    assert ruta.exists()

    wb = load_workbook(ruta)
    assert "Edificio" in wb.sheetnames
    assert "Unidad" in wb.sheetnames
    assert "Consultorio" in wb.sheetnames
    assert wb["Edificio"][1][0].value == "Nombre"


def test_importar_edificio_unidad_consultorio(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)

    wb["Edificio"].append(["Ramos 1", "Av. Rivadavia 13876", "Ramos Mejía"])

    wb["Unidad"].append(
        ["Ramos 1", '7mo "L"', "SI", "SI", 2, "NO", "NO", "NO", "NO", "NO", "NO", "SI", 60]
    )

    wb["Consultorio"].append(
        ["Ramos 1", '7mo "L"', 3, 4.2, 3.5, "intermedio", "SI", "NO", "SI", "NO", "SI", "SI", "NO", 4646, 4646]
    )

    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}

    assert resultados["Edificio"].filas_importadas == 1
    assert resultados["Unidad"].filas_importadas == 1
    assert resultados["Consultorio"].filas_importadas == 1
    assert not resultados["Unidad"].errores
    assert not resultados["Consultorio"].errores

    edificio = obtener_repositorio(conn, "Edificio").listar()[0]
    unidad = obtener_repositorio(conn, "Unidad").listar()[0]
    consultorio = obtener_repositorio(conn, "Consultorio").listar()[0]

    assert unidad["IdEdificio"] == edificio["IdEdificio"]
    assert unidad["WiFi"] == 1
    assert consultorio["IdUnidad"] == unidad["IdUnidad"]
    assert consultorio["NumeroConsultorio"] == 3


def test_importar_referencia_inexistente_reporta_error(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)

    wb["Unidad"].append(
        ["Edificio Que No Existe", "PB", "NO", "NO", 1, "NO", "NO", "NO", "NO", "NO", "NO", "NO", 10]
    )
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}

    assert resultados["Unidad"].filas_importadas == 0
    assert len(resultados["Unidad"].errores) == 1
    assert "Edificio Que No Existe" in resultados["Unidad"].errores[0]
