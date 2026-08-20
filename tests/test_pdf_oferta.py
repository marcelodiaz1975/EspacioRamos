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


def _bloque(dias, horario_desde=10, horario_hasta=12, **extra):
    return {"dias": dias, "horario_desde": horario_desde, "horario_hasta": horario_hasta, **extra}


def _crear_pedido_para(conn, consultorio, categoria):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional=categoria, Apellido="Prueba")
    return crear_pedido(
        conn, id_profesional=id_prof, bloques=[_bloque(["Lunes"])], condiciones_consultorio={"ventana": True},
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


def test_coincidencia_verde_explica_cobertura_directa(conn, consultorio, tmp_path):
    id_pedido = _crear_pedido_para(conn, consultorio, "R")
    ruta = generar_pdf_oferta(conn, str(tmp_path), id_pedido)
    texto = fitz.open(ruta)[0].get_text()
    assert "Cobertura directa: un solo consultorio cubre todo el horario pedido." in texto


def test_cantidad_horas_se_describe_en_criterios(conn, consultorio, tmp_path):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    id_pedido = crear_pedido(
        conn, id_profesional=id_prof, bloques=[_bloque(["Lunes"], 9, 13, cantidad_horas_requeridas=2)],
    )
    ruta = generar_pdf_oferta(conn, str(tmp_path), id_pedido)
    texto = fitz.open(ruta)[0].get_text()
    assert "2hs dentro del rango de 9 a 13hs (no hace falta que sea el rango completo)" in texto


def test_orden_consultorios_activo_por_piso_y_departamento(conn, tmp_path):
    """Profesional activo (departamento real): dentro de un edificio, el
    orden tiene que ser por piso ascendente — PB antes que 1ro — no por
    IdUnidad ni por orden alfabético de Departamento."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad_1ro = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='1ro "A"')
    id_unidad_pb = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='PB "B"')
    id_c_1ro = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_1ro, NumeroConsultorio=1, ValorHoraRegularActual=100)
    id_c_pb = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_pb, NumeroConsultorio=1, ValorHoraRegularActual=100)
    # Cada pedido ocupa el consultorio del OTRO piso en su propio día, para
    # forzar que cada uno termine matcheando con una unidad distinta (si no,
    # el barrido siempre elige el primer consultorio libre y el otro nunca
    # aparecería en la sección final).
    id_prof_ocupante = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ocupante")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof_ocupante, IdConsultorio=id_c_1ro, DiaSemana="Lunes", HoraInicio=10, HoraFin=11,
        VigenciaInicio="2020-01-01",
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof_ocupante, IdConsultorio=id_c_pb, DiaSemana="Martes", HoraInicio=10, HoraFin=11,
        VigenciaInicio="2020-01-01",
    )

    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    id_pedido1 = crear_pedido(conn, id_profesional=id_prof, bloques=[_bloque(["Lunes"], 10, 11)])
    id_pedido2 = crear_pedido(conn, id_profesional=id_prof, bloques=[_bloque(["Martes"], 10, 11)])
    ruta = generar_pdf_oferta_multiple(conn, str(tmp_path), [id_pedido1, id_pedido2])
    texto = fitz.open(ruta)[0].get_text()
    seccion = texto.split("Consultorios que intervienen en las ofertas")[1]
    assert seccion.index('PB "B"') < seccion.index('1ro "A"')


def test_multiple_combina_varios_pedidos_del_mismo_profesional_en_un_pdf(conn, consultorio, tmp_path):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    id_pedido1 = crear_pedido(conn, id_profesional=id_prof, bloques=[_bloque(["Lunes"], 8, 12)])
    id_pedido2 = crear_pedido(conn, id_profesional=id_prof, bloques=[_bloque(["Viernes"], 16, 20)])
    ruta = generar_pdf_oferta_multiple(conn, str(tmp_path), [id_pedido1, id_pedido2])
    texto = fitz.open(ruta)[0].get_text()
    assert texto.count("Criterios de búsqueda") == 1
    assert texto.count("Coincidencias") == 1
    assert texto.count("Consultorios que intervienen en las ofertas") == 1
    # Una franja por pedido, en cada una de las dos secciones que las repiten.
    assert texto.count("Franja horaria 1") == 2
    assert texto.count("Franja horaria 2") == 2


def test_multiple_con_profesionales_distintos_lanza_error(conn, consultorio, tmp_path):
    id_prof1 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Uno")
    id_prof2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Dos")
    id_pedido1 = crear_pedido(conn, id_profesional=id_prof1, bloques=[_bloque(["Lunes"], 8, 12)])
    id_pedido2 = crear_pedido(conn, id_profesional=id_prof2, bloques=[_bloque(["Lunes"], 8, 12)])
    with pytest.raises(ValueError):
        generar_pdf_oferta_multiple(conn, str(tmp_path), [id_pedido1, id_pedido2])


def test_pedido_con_dos_bloques_muestra_ambos_y_como_se_combinan(conn, consultorio, tmp_path):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    id_pedido = crear_pedido(
        conn, id_profesional=id_prof, tipo_combinacion_bloques="Y",
        bloques=[_bloque(["Martes", "Jueves"], 14, 18, tipo_combinacion_dias="O"), _bloque(["Sábado"], 9, 12)],
    )
    ruta = generar_pdf_oferta(conn, str(tmp_path), id_pedido)
    texto = fitz.open(ruta)[0].get_text()
    assert "Bloque 1" in texto and "Bloque 2" in texto
    assert "Sábado" in texto
    assert "se necesitan todos los bloques" in texto


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
        conn, id_profesional=id_prof, bloques=[_bloque(["Lunes"], 9, 11)],
        condiciones_consultorio={"sinCombinar": True},
    )
    ruta = generar_pdf_oferta(conn, str(tmp_path), id_pedido)
    texto = fitz.open(ruta)[0].get_text()
    assert "sin combinación de consultorios" in texto
    assert "Sin disponibilidad para este bloque con los filtros solicitados." in texto
