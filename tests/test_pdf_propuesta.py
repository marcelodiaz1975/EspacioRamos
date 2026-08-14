import fitz
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.pdf.propuesta_pdf import generar_pdf_propuesta, generar_pdfs_propuesta_por_localidad
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
    assert ruta.endswith("Propuesta Espacio Ramos Consultorios.pdf")
    with open(ruta, "rb") as f:
        assert f.read().startswith(b"%PDF")


def test_anonimiza_unidad_en_pie_de_foto_y_grilla(conn, edificio_con_consultorio_y_foto, tmp_path):
    _, id_unidad, _ = edificio_con_consultorio_y_foto
    ruta = generar_pdf_propuesta(conn, str(tmp_path))

    texto = fitz.open(ruta)[0].get_text()
    assert f"Unidad {id_unidad}" in texto
    assert '7mo "L"' not in texto  # el departamento real no debe aparecer


def test_incluye_las_cuatro_secciones_de_nivel_1(conn, edificio_con_consultorio_y_foto, tmp_path):
    ruta = generar_pdf_propuesta(conn, str(tmp_path))

    texto = fitz.open(ruta)[0].get_text()
    assert "Detalles principales de la propuesta" in texto
    assert "Fotos de los consultorios" in texto
    assert "Disponibilidad de consultorios al" in texto
    assert "Detalles complementarios de la propuesta" in texto


def test_por_localidad_genera_un_archivo_separado_por_cada_una(conn, edificio_con_consultorio_y_foto, tmp_path):
    """Nunca mezcla edificios de distintas localidades en el mismo PDF: un
    edificio en San Justo no debe terminar en el mismo archivo que uno en
    CABA (el de la fixture)."""
    id_ed2 = obtener_repositorio(conn, "Edificio").crear(Nombre="San Justo 1", DomicilioLocalidad="San Justo")
    id_unidad2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_ed2, Departamento="1ro A")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad2, NumeroConsultorio=1, ValorHoraRegularActual=500)

    rutas = generar_pdfs_propuesta_por_localidad(conn, str(tmp_path))

    assert len(rutas) == 2
    assert any("CABA" in r for r in rutas)
    assert any("San Justo" in r for r in rutas)
    for ruta in rutas:
        with open(ruta, "rb") as f:
            assert f.read().startswith(b"%PDF")
