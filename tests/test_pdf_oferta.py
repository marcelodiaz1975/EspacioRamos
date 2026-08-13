import fitz
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.lista_espera import crear_pedido
from app.pdf.oferta_pdf import generar_pdf_oferta, generar_pdf_oferta_multiple
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


def test_multiple_combina_varios_pedidos_del_mismo_profesional_en_un_pdf(conn, consultorio, tmp_path):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    id_pedido1 = crear_pedido(
        conn, id_profesional=id_prof, tipo_combinacion="O", dias=["Lunes"], horario_desde=8, horario_hasta=12,
    )
    id_pedido2 = crear_pedido(
        conn, id_profesional=id_prof, tipo_combinacion="O", dias=["Viernes"], horario_desde=16, horario_hasta=20,
    )
    ruta = generar_pdf_oferta_multiple(conn, str(tmp_path), [id_pedido1, id_pedido2])
    texto = fitz.open(ruta)[0].get_text()
    assert texto.count("Filtros de búsqueda y alternativas disponibles") == 2
    assert texto.count("Fotos y valores regulares de los consultorios ofrecidos") == 1


def test_multiple_con_profesionales_distintos_lanza_error(conn, consultorio, tmp_path):
    id_prof1 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Uno")
    id_prof2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Dos")
    id_pedido1 = crear_pedido(
        conn, id_profesional=id_prof1, tipo_combinacion="O", dias=["Lunes"], horario_desde=8, horario_hasta=12,
    )
    id_pedido2 = crear_pedido(
        conn, id_profesional=id_prof2, tipo_combinacion="O", dias=["Lunes"], horario_desde=8, horario_hasta=12,
    )
    with pytest.raises(ValueError):
        generar_pdf_oferta_multiple(conn, str(tmp_path), [id_pedido1, id_pedido2])


def test_sin_combinar_rechaza_coincidencias_que_no_sean_verde(conn, tmp_path):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1ro A")
    # Dos consultorios angostos: ninguno solo cubre las 2 horas pedidas sin
    # que el otro esté ocupado justo una de ellas, así que la única
    # cobertura posible combina ambos (no puede dar verde).
    id_c1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=100)
    id_c2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=2, ValorHoraRegularActual=100)
    id_prof_ocupante = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ocupante")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof_ocupante, IdConsultorio=id_c1, DiaSemana="Lunes", HoraInicio=10, HoraFin=11,
        VigenciaInicio="2020-01-01",
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof_ocupante, IdConsultorio=id_c2, DiaSemana="Lunes", HoraInicio=9, HoraFin=10,
        VigenciaInicio="2020-01-01",
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Interesado")
    id_pedido = crear_pedido(
        conn, id_profesional=id_prof, tipo_combinacion="O", dias=["Lunes"], horario_desde=9, horario_hasta=11,
        condiciones_consultorio={"sinCombinar": True},
    )
    ruta = generar_pdf_oferta(conn, str(tmp_path), id_pedido)
    texto = fitz.open(ruta)[0].get_text()
    assert "sin combinación de consultorios" in texto
    assert "Sin alternativas disponibles con los filtros solicitados." in texto
