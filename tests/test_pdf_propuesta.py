import fitz
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.pdf.propuesta_pdf import generar_pdf_propuesta
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def edificio_con_consultorio_y_foto(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 1", Domicilio="Av. Rivadavia 1234", DomicilioLocalidad="CABA"
    )
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, Ventana=1, AptoCamilla=1, ValorHoraRegularActual=1000,
    )
    obtener_repositorio(conn, "Imagen").crear(
        IdConsultorio=id_consultorio, NumeroOrden=1, Descripcion="Vista", RutaArchivo="/no/existe.jpg", Activo=1,
    )
    return id_edificio, id_unidad, id_consultorio


def test_genera_pdf_valido(conn, edificio_con_consultorio_y_foto, tmp_path):
    ruta = generar_pdf_propuesta(conn, str(tmp_path))
    assert ruta.endswith("Propuesta al profesional.pdf")
    with open(ruta, "rb") as f:
        assert f.read().startswith(b"%PDF")


def test_anonimiza_unidad_en_pie_de_foto_y_grilla(conn, edificio_con_consultorio_y_foto, tmp_path):
    _, id_unidad, _ = edificio_con_consultorio_y_foto
    ruta = generar_pdf_propuesta(conn, str(tmp_path))

    texto = fitz.open(ruta)[0].get_text()
    assert f"Unidad {id_unidad}" in texto
    assert '7mo "L"' not in texto  # el departamento real no debe aparecer


def test_personaliza_con_profesion_del_contacto(conn, edificio_con_consultorio_y_foto, tmp_path):
    id_profesion = obtener_repositorio(conn, "Profesion").listar()[0]["IdProfesion"]
    nombre_profesion = obtener_repositorio(conn, "Profesion").obtener(id_profesion)["Nombre"]
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="C", Apellido="Prospecto", IdProfesion=id_profesion,
    )
    ruta = generar_pdf_propuesta(conn, str(tmp_path), id_profesional=id_prof)

    texto = fitz.open(ruta)[0].get_text()
    assert nombre_profesion in texto
