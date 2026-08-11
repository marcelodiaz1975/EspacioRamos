import fitz
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.lista_espera import crear_pedido
from app.pdf.oferta_pdf import generar_pdf_oferta
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", DomicilioLocalidad="CABA")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return id_unidad, obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, Ventana=1, ValorHoraRegularActual=1000,
    )


def _crear_pedido_para(conn, consultorio, categoria):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional=categoria, Apellido="Prueba")
    return crear_pedido(
        conn, id_profesional=id_prof, tipo_combinacion="O", dias=["Lunes"],
        horario_desde=10, horario_hasta=12, condiciones_consultorio={"ventana": True},
    )


def test_nombre_archivo_es_siempre_el_mismo(conn, consultorio, tmp_path):
    _, id_consultorio = consultorio
    id_pedido = _crear_pedido_para(conn, consultorio, "C")
    ruta = generar_pdf_oferta(conn, str(tmp_path), id_pedido)
    assert ruta.endswith("Oferta consultorios.pdf")


def test_anonimiza_unidad_para_profesional_no_activo(conn, consultorio, tmp_path):
    id_unidad, _ = consultorio
    id_pedido = _crear_pedido_para(conn, consultorio, "C")
    ruta = generar_pdf_oferta(conn, str(tmp_path), id_pedido)
    texto = fitz.open(ruta)[0].get_text()
    assert f"Unidad {id_unidad}" in texto
    assert '7mo "L"' not in texto


def test_muestra_departamento_real_para_profesional_activo(conn, consultorio, tmp_path):
    id_pedido = _crear_pedido_para(conn, consultorio, "R")
    ruta = generar_pdf_oferta(conn, str(tmp_path), id_pedido)
    texto = fitz.open(ruta)[0].get_text()
    assert '7mo "L"' in texto


def test_sin_pedido_lanza_error(conn, tmp_path):
    with pytest.raises(ValueError):
        generar_pdf_oferta(conn, str(tmp_path), 999)
