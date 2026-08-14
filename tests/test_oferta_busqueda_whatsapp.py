import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.oferta_busqueda import Busqueda, CriteriosGlobales
from app.negocio.oferta_busqueda_whatsapp import generar_texto_oferta_busqueda
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
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    return id_edificio, id_unidad, id_consultorio


def _busqueda_simple(dias=("Lunes",)):
    return Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=list(dias), hora_desde=9, hora_hasta=11,
    )


def test_estructura_basica_con_una_sola_alternativa(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    texto = generar_texto_oferta_busqueda(conn, id_prof, globales, [_busqueda_simple()])

    assert "*Búsqueda requerida por el profesional*" in texto
    assert "*Detalle de la búsqueda*" in texto
    assert "- Lunes de 9 a 11hs" in texto
    assert "*Listado de alternativas encontradas*" in texto
    assert "_Alternativa" not in texto  # una sola alternativa: no se numera
    assert '- Lunes de 9 a 11hs consultorio 1 del 7mo "L"' in texto
    assert "*Comentario*" not in texto  # un solo edificio, sin avisos
    assert "Hora regular" not in texto  # sin fotos en el texto, no hace falta el valor


def test_numera_alternativas_con_guion_bajo(conn, tmp_path):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_unidad2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='3ro "B"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad1, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad2, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    texto = generar_texto_oferta_busqueda(conn, id_prof, globales, [_busqueda_simple()])

    assert "_Alternativa 1_" in texto
    assert "_Alternativa 2_" in texto


def test_viñetas_usan_guion_no_asterisco(conn, edificio_con_consultorio, tmp_path):
    """Un "*" sin cerrar rompería la negrita de WhatsApp para el resto del
    mensaje — las viñetas tienen que ser "-", no "*"."""
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    texto = generar_texto_oferta_busqueda(conn, id_prof, globales, [_busqueda_simple()])
    for linea in texto.splitlines():
        if linea.startswith("*"):
            assert linea.endswith("*")  # todo asterisco de apertura tiene su cierre


def test_comentario_enumera_edificios_cuando_hay_mas_de_uno(conn, tmp_path):
    id_edificio1 = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 1", Domicilio="Av. Rivadavia 13876", DomicilioLocalidad="Ramos Mejía",
    )
    id_edificio2 = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", Domicilio="Alvear 856", DomicilioLocalidad="Ramos Mejía",
    )
    id_unidad1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio1, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad1, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_unidad2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio2, Departamento='8vo "M"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad2, NumeroConsultorio=1, ValorHoraRegularActual=1200)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(
        tipo_busqueda="Regular", ids_edificio=[id_edificio1, id_edificio2], localidad="Ramos Mejía",
    )
    texto = generar_texto_oferta_busqueda(conn, id_prof, globales, [_busqueda_simple()])

    assert "*Comentario*" in texto
    assert "- Ramos 1 corresponde a Av. Rivadavia 13876, Ramos Mejía." in texto
    assert "- Ramos 2 corresponde a Alvear 856, Ramos Mejía." in texto


def test_aislada_incluye_rango_de_fechas(conn, tmp_path):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Aislada", ids_edificio=[id_edificio])
    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-03", fecha_hasta=f"{ANIO}-{MES:02d}-03", dias=["Lunes"], hora_desde=9, hora_hasta=11,
    )
    texto = generar_texto_oferta_busqueda(conn, id_prof, globales, [busqueda])
    assert "Del" in texto and "al" in texto and "Lunes de 9 a 11" in texto


def test_sin_alternativas_avisa(conn, tmp_path):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    texto = generar_texto_oferta_busqueda(conn, id_prof, globales, [_busqueda_simple()])
    assert "Sin disponibilidad" in texto


def test_anonimiza_para_profesional_no_activo(conn, edificio_con_consultorio, tmp_path):
    id_edificio, id_unidad, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    texto = generar_texto_oferta_busqueda(conn, id_prof, globales, [_busqueda_simple()])
    assert f"Unidad {id_unidad}" in texto
    assert '7mo "L"' not in texto


def test_detalle_reducido_omite_consultorio(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio], detalle_reducido=True)
    texto = generar_texto_oferta_busqueda(conn, id_prof, globales, [_busqueda_simple()])
    assert "consultorio 1" not in texto.lower()
    assert 'en la unidad del 7mo "L"' in texto


def test_sin_busquedas_lanza_error(conn, tmp_path):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[])
    with pytest.raises(ValueError):
        generar_texto_oferta_busqueda(conn, id_prof, globales, [])


def test_sin_profesional_lanza_error(conn, tmp_path):
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[])
    with pytest.raises(ValueError):
        generar_texto_oferta_busqueda(conn, 999, globales, [_busqueda_simple()])
