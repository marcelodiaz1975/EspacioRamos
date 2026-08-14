import fitz
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.oferta_busqueda import Busqueda, CriteriosGlobales
from app.pdf.oferta_busqueda_pdf import generar_pdf_oferta_busqueda
from app.repositorio.registro import obtener_repositorio

ANIO, MES = 2026, 8


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def edificio_con_consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", DomicilioLocalidad="CABA")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, Ventana=1, ValorHoraRegularActual=1000,
    )
    return id_edificio, id_unidad, id_consultorio


def _busqueda_simple(dias=("Lunes",)):
    return Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=list(dias), hora_desde=9, hora_hasta=11,
    )


def test_genera_pdf_valido(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Lo Veci", NombrePila="Virginia", Tratamiento="Lic.")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    assert ruta.endswith("Oferta consultorios.pdf")
    with open(ruta, "rb") as f:
        assert f.read().startswith(b"%PDF")


def test_titulo_usa_nombre_completo_del_profesional(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Lo Veci", NombrePila="Virginia", Tratamiento="Lic.")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Búsqueda solicitada por Lic. Virginia Lo Veci" in texto


def test_incluye_todos_los_titulos_por_busqueda(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Criterios de búsqueda generales" in texto
    assert "Búsqueda 1" in texto
    assert "Criterios de búsqueda específicos" in texto
    assert "Coincidencias de la búsqueda" in texto
    assert "Fotos de los consultorios que intervienen en las búsquedas" in texto


def test_criterios_generales_muestra_las_5_lineas_con_defaults(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Tipo de búsqueda:" in texto
    assert "Localidad:" in texto
    assert "Edificios:" in texto
    assert "Unidades: todas" in texto
    assert "Consultorios: todos" in texto


def test_pie_de_foto_edificio_unidad_consultorio_valor_sin_repetir(conn, edificio_con_consultorio, tmp_path):
    id_edificio, id_unidad, id_consultorio = edificio_con_consultorio
    obtener_repositorio(conn, "Imagen").crear(
        IdConsultorio=id_consultorio, NumeroOrden=1, Descripcion="Vista", RutaArchivo="/no/existe.jpg", Activo=1,
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert '7mo "L" - Consultorio 1: $ 1.000,00/hora' in texto
    assert texto.count("$ 1.000,00/hora") == 1  # no se repite en ningún otro lado
    assert "Apto camilla" not in texto
    assert "Ramos 1 -" not in texto  # un solo edificio: no va en el pie


def test_anonimiza_para_profesional_no_activo(conn, edificio_con_consultorio, tmp_path):
    id_edificio, id_unidad, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert f"Unidad {id_unidad}" in texto
    assert '7mo "L"' not in texto


def test_muestra_departamento_real_para_profesional_activo(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert '7mo "L"' in texto


def test_sin_busquedas_lanza_error(conn, tmp_path):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[])
    with pytest.raises(ValueError):
        generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [])


def test_sin_profesional_lanza_error(conn, tmp_path):
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[])
    with pytest.raises(ValueError):
        generar_pdf_oferta_busqueda(conn, str(tmp_path), 999, globales, [_busqueda_simple()])
