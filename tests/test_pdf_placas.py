import fitz
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.pdf.placas_pdf import generar_pdf_placas
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A", localidad=None):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre=nombre_edificio, DomicilioLocalidad=localidad)
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=departamento)
    return id_edificio, id_unidad


def test_sin_placas_avisa_y_genera_pdf_valido(conn, tmp_path):
    ruta = generar_pdf_placas(conn, str(tmp_path))
    assert ruta.endswith("Placas Espacio Ramos.pdf")
    texto = fitz.open(ruta)[0].get_text()
    assert "No hay placas activas cargadas." in texto


def test_lista_placas_activas_ordenadas_por_posicion(conn, tmp_path):
    _, id_unidad = _crear_unidad(conn)
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad, PosicionTablero=2, NombreGrabado="Lic. Pérez")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad, PosicionTablero=1, NombreGrabado="Dr. Gómez")

    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()

    assert texto.index("Dr. Gómez") < texto.index("Lic. Pérez")


def test_placa_inactiva_no_aparece(conn, tmp_path):
    _, id_unidad = _crear_unidad(conn)
    obtener_repositorio(conn, "Placa").crear(
        IdUnidad=id_unidad, PosicionTablero=1, NombreGrabado="Dado de baja", Activo=0,
    )
    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "Dado de baja" not in texto


def test_placa_sin_nombre_muestra_placeholder(conn, tmp_path):
    _, id_unidad = _crear_unidad(conn)
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad, PosicionTablero=1)
    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "(sin nombre cargado)" in texto


def test_placa_personalizada_se_marca(conn, tmp_path):
    _, id_unidad = _crear_unidad(conn)
    obtener_repositorio(conn, "Placa").crear(
        IdUnidad=id_unidad, PosicionTablero=1, NombreGrabado="Dr. Gómez", EsPersonalizada=1,
    )
    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "Dr. Gómez (personalizada)" in texto


def test_unidad_sin_placas_no_aparece(conn, tmp_path):
    id_edificio, id_unidad_con = _crear_unidad(conn, departamento="1ro A")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad_con, PosicionTablero=1, NombreGrabado="Con placa")
    obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="Vacía")  # sin placas

    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "Vacía" not in texto


def test_muestra_edificio_cuando_hay_mas_de_uno(conn, tmp_path):
    _, id_unidad1 = _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A")
    _, id_unidad2 = _crear_unidad(conn, nombre_edificio="Ramos 2", departamento="2do B")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad1, PosicionTablero=1, NombreGrabado="Uno")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad2, PosicionTablero=1, NombreGrabado="Dos")

    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "Ramos 1 - 1ro A" in texto
    assert "Ramos 2 - 2do B" in texto


def test_un_solo_edificio_no_repite_nombre(conn, tmp_path):
    _, id_unidad = _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad, PosicionTablero=1, NombreGrabado="Único")

    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "Ramos 1 - 1ro A" not in texto
    assert "1ro A" in texto


def test_filtra_por_ids_edificio(conn, tmp_path):
    id_edificio1, id_unidad1 = _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A")
    _, id_unidad2 = _crear_unidad(conn, nombre_edificio="Ramos 2", departamento="2do B")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad1, PosicionTablero=1, NombreGrabado="Uno")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad2, PosicionTablero=1, NombreGrabado="Dos")

    ruta = generar_pdf_placas(conn, str(tmp_path), ids_edificio=[id_edificio1])
    texto = fitz.open(ruta)[0].get_text()
    assert "Uno" in texto
    assert "Dos" not in texto
