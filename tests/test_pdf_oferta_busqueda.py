import fitz
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.oferta_busqueda import Busqueda, CriteriosGlobales
from app.negocio.oferta_busqueda_texto import COMENTARIO_ALTERNATIVAS_OFRECIDAS, COMENTARIO_RESERVAS_REGULARES
from app.negocio.plantillas_texto import guardar_texto_personalizado
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
    id_caba = obtener_repositorio(conn, "Localidad").crear(Localidad="CABA")
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", IdLocalidad=id_caba)
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, Ventana=1, ValorHoraRegularActual=1000,
    )
    return id_edificio, id_unidad, id_consultorio


def _busqueda_simple(dias=("Lunes",), hora_desde=9, hora_hasta=11):
    return Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=list(dias),
        hora_desde=hora_desde, hora_hasta=hora_hasta,
    )


def test_genera_pdf_valido(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Lo Veci", NombrePila="Virginia", Tratamiento="Lic.")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    assert ruta.endswith("Oferta de consultorios - Espacio Ramos Consultorios.pdf")
    with open(ruta, "rb") as f:
        assert f.read().startswith(b"%PDF")


def test_titulo_es_generico(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Lo Veci", NombrePila="Virginia", Tratamiento="Lic.")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Búsqueda requerida por el profesional" in texto
    assert "Lo Veci" not in texto  # el documento no repite el nombre del profesional


def test_incluye_titulos_principales(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Detalle de la búsqueda" in texto
    assert "Listado de alternativas encontradas" in texto
    assert "Fotos de los consultorios ofrecidos" in texto


def test_detalle_busqueda_muestra_dias_y_horario(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes", "Viernes"], hora_desde=13, hora_hasta=18)
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [busqueda])
    texto = fitz.open(ruta)[0].get_text()
    assert "Lunes, Viernes de 13 a 18" in texto
    # No se detallan fecha inicial/final, combinación, características, etc.
    assert "Combinación de consultorios" not in texto
    assert "Características del consultorio" not in texto


def test_detalle_busqueda_aislada_incluye_rango_de_fechas(conn, tmp_path):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Aislada", ids_edificio=[id_edificio])
    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-03", fecha_hasta=f"{ANIO}-{MES:02d}-03", dias=["Lunes"], hora_desde=9, hora_hasta=11,
    )
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [busqueda])
    texto = fitz.open(ruta)[0].get_text()
    assert "Del" in texto and "al" in texto and "Lunes de 9 a 11" in texto


def test_alternativa_unica_no_se_numera(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    # No confundir con "Alternativas ofrecidas:" del comentario fijo (opt-in,
    # ver test_comentario_incluye_solo_los_tildados_en_orden_fijo, acá no se
    # tildó) — la numeración real diría "Alternativa 1".
    assert "Alternativa 1" not in texto
    assert 'Lunes de 9 a 11hs consultorio 1 del 7mo "L"' in texto


def test_multiples_alternativas_se_numeran(conn, tmp_path):
    """Si más de un consultorio cubre el bloque por sí solo, cada uno es
    una alternativa numerada aparte."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_unidad2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='3ro "B"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad1, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad2, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Alternativa 1" in texto
    assert "Alternativa 2" in texto
    assert 'consultorio 1 del 7mo "L"' in texto
    assert 'consultorio 1 del 3ro "B"' in texto


def test_combinacion_dos_lineas_en_una_sola_alternativa(conn, tmp_path):
    """Una combinación de consultorios es UNA alternativa con varias
    líneas con asterisco, una por tramo — no varias alternativas."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='EP "K"')
    id_c1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_c2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=2, ValorHoraRegularActual=1200)
    id_prof_ocupante = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ocupante")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof_ocupante, IdConsultorio=id_c1, DiaSemana="Lunes", HoraInicio=10, HoraFin=11, VigenciaInicio="2020-01-01",
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof_ocupante, IdConsultorio=id_c2, DiaSemana="Lunes", HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Alternativa 1" not in texto  # una sola alternativa total: no se numera
    assert 'Lunes de 9 a 10hs consultorio 1 del EP "K"' in texto
    assert 'Lunes de 10 a 11hs consultorio 2 del EP "K"' in texto


def test_alternativas_no_muestran_el_valor(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, id_consultorio = edificio_con_consultorio
    obtener_repositorio(conn, "Imagen").crear(
        IdConsultorio=id_consultorio, NumeroOrden=1, Descripcion="Vista", RutaArchivo="/no/existe.jpg", Activo=1,
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    # El valor solo aparece una vez, debajo de la foto — no en el listado de alternativas.
    assert texto.count("Hora regular") == 1


def test_pie_de_foto_edificio_unidad_consultorio_valor_sin_repetir(conn, edificio_con_consultorio, tmp_path):
    id_edificio, id_unidad, id_consultorio = edificio_con_consultorio
    obtener_repositorio(conn, "Imagen").crear(
        IdConsultorio=id_consultorio, NumeroOrden=1, Descripcion="Vista", RutaArchivo="/no/existe.jpg", Activo=1,
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    # Valor redondo (1000, sin centavos): sin decimales.
    assert 'Unidad 7mo "L" - Consultorio 1 - Hora regular $ 1.000' in texto
    assert "Apto camilla" not in texto
    assert "Edificio Ramos 1" not in texto  # un solo edificio: no va en el pie


def test_pie_de_foto_con_centavos_muestra_decimales(conn, tmp_path):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1050.5,
    )
    obtener_repositorio(conn, "Imagen").crear(
        IdConsultorio=id_consultorio, NumeroOrden=1, Descripcion="Vista", RutaArchivo="/no/existe.jpg", Activo=1,
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Hora regular $ 1.050,50" in texto


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


def test_categoria_x_no_se_anonimiza(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="X", Apellido="Prueba")
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


def test_excluir_omite_alternativas_puntuales(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = _busqueda_simple(dias=("Lunes", "Martes"))

    ruta = generar_pdf_oferta_busqueda(
        conn, str(tmp_path), id_prof, globales, [busqueda], excluir={(0, 0, 0)},
    )
    texto = fitz.open(ruta)[0].get_text()
    assert "Lunes de 9 a 11hs" not in texto
    assert "Martes de 9 a 11hs" in texto


def test_detalle_reducido_omite_consultorio_y_fotos(conn, tmp_path):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    obtener_repositorio(conn, "Imagen").crear(
        IdConsultorio=id_consultorio, NumeroOrden=1, Descripcion="Vista", RutaArchivo="/no/existe.jpg", Activo=1,
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")

    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-03", fecha_hasta=f"{ANIO}-{MES:02d}-03", dias=["Lunes"],
        hora_desde=9, hora_hasta=11,
    )
    globales = CriteriosGlobales(
        tipo_busqueda="Aislada", ids_edificio=[id_edificio], salida="Texto", identificar_consultorio=False,
    )
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [busqueda])
    texto = fitz.open(ruta)[0].get_text()
    assert "consultorio 1" not in texto.lower()  # no se identifica el consultorio puntual
    assert 'en la unidad del 7mo "L"' in texto
    assert "Fotos de los consultorios ofrecidos" not in texto


def test_detalle_reducido_tambien_aplica_a_busqueda_regular(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio], identificar_consultorio=False)
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "consultorio 1" not in texto.lower()
    assert "Fotos de los consultorios ofrecidos" not in texto


def test_solo_dias_y_horarios_omite_unidad_edificio_y_fotos(conn, tmp_path):
    """Pedido explícito de la clienta: desmarcar "Identificar unidad"
    (que de una desmarca "Identificar consultorio" también, ver
    `_PanelOferta._al_desmarcar_identificar_unidad`) tiene que mostrar
    solo días y horarios, sin ubicación — ni unidad, ni consultorio, ni
    edificio (a diferencia del detalle reducido de siempre, que sigue
    nombrando la unidad)."""
    id_caba = obtener_repositorio(conn, "Localidad").crear(Localidad="CABA")
    id_edificio_1 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", IdLocalidad=id_caba)
    id_edificio_2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2", IdLocalidad=id_caba)
    id_unidad_1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_1, Departamento='7mo "L"')
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_2, Departamento='3ro "B"')
    id_consultorio_1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_1, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_consultorio_2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    for id_consultorio in (id_consultorio_1, id_consultorio_2):
        obtener_repositorio(conn, "Imagen").crear(
            IdConsultorio=id_consultorio, NumeroOrden=1, Descripcion="Vista", RutaArchivo="/no/existe.jpg", Activo=1,
        )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(
        tipo_busqueda="Regular", ids_edificio=[id_edificio_1, id_edificio_2],
        identificar_unidad=False, identificar_consultorio=False,
    )
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "consultorio 1" not in texto.lower()
    assert "7mo" not in texto and "3ro" not in texto  # sin unidad
    assert "Ramos 1" not in texto and "Ramos 2" not in texto  # sin edificio, aunque haya más de uno
    assert "Fotos de los consultorios ofrecidos" not in texto


def test_detalle_tramo_formato_con_consultorio_un_edificio(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert 'Lunes de 9 a 11hs consultorio 1 del 7mo "L"' in texto
    assert " en Ramos 1" not in texto  # un solo edificio: no se aclara


def test_detalle_tramo_formato_con_consultorio_varios_edificios(conn, tmp_path):
    id_edificio1 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_edificio2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2")
    id_unidad1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio1, Departamento='7mo "L"')
    id_unidad2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio2, Departamento='3ro "B"')
    id_c1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad1, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad2, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof_ocupante = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ocupante")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof_ocupante, IdConsultorio=id_c1, DiaSemana="Martes", HoraInicio=9, HoraFin=11,
        VigenciaInicio="2020-01-01",
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio1, id_edificio2])
    busqueda = _busqueda_simple(dias=("Lunes", "Martes"))
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [busqueda])
    texto = fitz.open(ruta)[0].get_text()
    assert 'consultorio 1 del 7mo "L" en Ramos 1' in texto
    assert 'consultorio 1 del 3ro "B" en Ramos 2' in texto


def test_comentario_ausente_sin_nada_tildado(conn, edificio_con_consultorio, tmp_path):
    """Pedido explícito de la clienta: los tres comentarios fijos pasan
    a ser opt-in (checks "Comentarios a incluír" en la previsualización,
    todos destildados por defecto) — sin ninguno tildado y sin
    ambigüedad de edificio, la sección "Comentarios" desaparece del
    todo (a diferencia de la vuelta anterior, donde los tres textos
    fijos iban siempre)."""
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple(hora_desde=12, hora_hasta=14)])
    texto = fitz.open(ruta)[0].get_text()
    assert "Comentarios" not in texto


def test_comentario_incluye_solo_los_tildados_en_orden_fijo(conn, edificio_con_consultorio, tmp_path):
    """Cada uno de los tres se tilda por separado y el orden en el
    documento es siempre el mismo (regulares / aisladas / alternativas),
    sin importar el orden en que se pasen en `comentarios_incluidos`."""
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(
        conn, str(tmp_path), id_prof, globales, [_busqueda_simple(hora_desde=12, hora_hasta=14)],
        comentarios_incluidos={COMENTARIO_ALTERNATIVAS_OFRECIDAS, COMENTARIO_RESERVAS_REGULARES},
    )
    # El párrafo puede partirse en varias líneas al ajustar el ancho —
    # se normaliza antes de comparar.
    texto = fitz.open(ruta)[0].get_text().replace("\n", " ")
    assert "Comentarios" in texto
    assert "Las horas que van de 9 a 11hs" in texto  # Reservas regulares
    assert "Los horarios ofrecidos pueden ser tomados" in texto  # Alternativas ofrecidas
    assert "No hay limitación alguna" not in texto  # Reservas aisladas: no se tildó
    assert texto.index("Las horas que van de 9 a 11hs") < texto.index("Los horarios ofrecidos pueden ser tomados")


def test_comentario_enumera_edificios_cuando_hay_mas_de_uno(conn, tmp_path):
    id_ramos_mejia = obtener_repositorio(conn, "Localidad").crear(Localidad="Ramos Mejía")
    id_edificio1 = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 1", Domicilio="Av. Rivadavia 13876", IdLocalidad=id_ramos_mejia,
    )
    id_edificio2 = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", Domicilio="Alvear 856", IdLocalidad=id_ramos_mejia,
    )
    id_unidad1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio1, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad1, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_unidad2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio2, Departamento='8vo "M"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad2, NumeroConsultorio=1, ValorHoraRegularActual=1200)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(
        tipo_busqueda="Regular", ids_edificio=[id_edificio1, id_edificio2], localidad="Ramos Mejía",
    )
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Comentario" in texto
    assert "Ramos 1 corresponde a Av. Rivadavia 13876, Ramos Mejía." in texto
    assert "Ramos 2 corresponde a Alvear 856, Ramos Mejía." in texto


def test_comentario_excluye_edificio_sin_resultados(conn, tmp_path):
    """Un edificio incluido en el alcance de la búsqueda (ids_edificio) pero
    sin ninguna coincidencia real no debe figurar en el comentario — acá
    solo Ramos 1 tiene resultados, así que ni siquiera hace falta aclarar
    edificios (un único edificio entre los resultados: no hay ambigüedad).
    Se tilda "Reservas regulares" para que la sección "Comentarios"
    exista y se pueda confirmar que Ramos 2 no aparece en ningún lado."""
    id_ramos_mejia = obtener_repositorio(conn, "Localidad").crear(Localidad="Ramos Mejía")
    id_edificio1 = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 1", Domicilio="Av. Rivadavia 13876", IdLocalidad=id_ramos_mejia,
    )
    id_edificio2 = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", Domicilio="Alvear 856", IdLocalidad=id_ramos_mejia,
    )
    id_unidad1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio1, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad1, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(
        tipo_busqueda="Regular", ids_edificio=[id_edificio1, id_edificio2], localidad="Ramos Mejía",
    )
    ruta = generar_pdf_oferta_busqueda(
        conn, str(tmp_path), id_prof, globales, [_busqueda_simple(hora_desde=12, hora_hasta=14)],
        comentarios_incluidos={COMENTARIO_RESERVAS_REGULARES},
    )
    texto = fitz.open(ruta)[0].get_text()
    assert "Comentarios" in texto
    assert "Ramos 2" not in texto


def test_comentario_no_incluye_aviso_de_hora_aislada(conn, edificio_con_consultorio, tmp_path):
    """Pedido explícito de la clienta: el aviso de hora aislada asignada
    dentro de un horario regular ofrecido deja de imprimirse en el PDF —
    el profesional no tiene por qué verlo. Se le avisa en pantalla al
    operador en su lugar (ver `app.gui.pantallas.oferta`), no en el
    documento."""
    id_edificio, _, id_consultorio = edificio_con_consultorio
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ocupante"),
        IdConsultorio=id_consultorio, Fecha=f"{ANIO}-{MES:02d}-03", HoraInicio=9, HoraFin=10,
    )  # 2026-08-03 es lunes
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "hora aislada asignada" not in texto
    assert f"{ANIO}-{MES:02d}-03" not in texto


def test_comentario_de_reservas_regulares_es_personalizable(conn, edificio_con_consultorio, tmp_path):
    """Cada uno de los tres comentarios fijos sigue siendo editable por
    separado en "Textos del sistema" (clave propia por comentario, ver
    `app.negocio.plantillas_texto`) — solo se ve si además está tildado
    en "Comentarios a incluír"."""
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    guardar_texto_personalizado(
        conn, "oferta_busqueda_comentario_reservas_regulares", "Texto personalizado de comentarios.",
    )
    ruta = generar_pdf_oferta_busqueda(
        conn, str(tmp_path), id_prof, globales, [_busqueda_simple()], comentarios_incluidos={COMENTARIO_RESERVAS_REGULARES},
    )
    texto = fitz.open(ruta)[0].get_text()
    assert "Texto personalizado de comentarios." in texto


def test_comentario_personalizado_no_aparece_si_no_se_tildo(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    guardar_texto_personalizado(
        conn, "oferta_busqueda_comentario_reservas_regulares", "Texto personalizado de comentarios.",
    )
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Texto personalizado de comentarios." not in texto
    assert "Reservas regulares:" not in texto
