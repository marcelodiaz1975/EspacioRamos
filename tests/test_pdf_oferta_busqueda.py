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
    assert "Criterios de búsqueda seleccionados" in texto
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
    assert "Edificios: Ramos 1" in texto  # sin Domicilio cargado, se muestra solo el nombre
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


def test_coincidencias_edificio_solo_si_hay_mas_de_uno(conn, tmp_path):
    id_edificio1 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_edificio2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2")
    id_unidad1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio1, Departamento='7mo "L"')
    id_unidad2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio2, Departamento='3ro "B"')
    id_c1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad1, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad2, NumeroConsultorio=1, ValorHoraRegularActual=1000)

    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    busqueda_un_dia = _busqueda_simple(dias=("Lunes",))
    globales_un_edificio = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio1])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales_un_edificio, [busqueda_un_dia])
    texto = fitz.open(ruta)[0].get_text()
    assert "Edificio Ramos 1" not in texto

    # Ramos 1 ocupado el martes: la búsqueda de lunes+martes solo encuentra
    # cobertura en Ramos 1 el lunes y tiene que caer a Ramos 2 el martes,
    # así que el resultado final SÍ abarca los dos edificios.
    id_prof_ocupante = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ocupante")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof_ocupante, IdConsultorio=id_c1, DiaSemana="Martes", HoraInicio=9, HoraFin=11,
        VigenciaInicio="2020-01-01",
    )
    busqueda_dos_dias = _busqueda_simple(dias=("Lunes", "Martes"))
    globales_dos_edificios = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio1, id_edificio2])
    ruta2 = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales_dos_edificios, [busqueda_dos_dias])
    texto2 = fitz.open(ruta2)[0].get_text()
    assert "Edificio Ramos 1" in texto2
    assert "Edificio Ramos 2" in texto2


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


def test_muestra_aviso_de_hora_aislada_dentro_del_bloque(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, id_consultorio = edificio_con_consultorio
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ocupante"),
        IdConsultorio=id_consultorio, Fecha=f"{ANIO}-{MES:02d}-03", HoraInicio=9, HoraFin=10,
    )  # 2026-08-03 es lunes
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "hora aislada asignada" in texto
    assert f"{ANIO}-{MES:02d}-03" in texto


def test_cobertura_completa_vs_parcial(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])

    ruta_completa = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    assert "Cobertura completa" in fitz.open(ruta_completa)[0].get_text()

    busqueda_parcial = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=13,
        cantidad_horas_minimas=2,
    )
    ruta_parcial = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [busqueda_parcial])
    assert "Cobertura parcial" in fitz.open(ruta_parcial)[0].get_text()


def test_excluir_omite_alternativas_puntuales(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = _busqueda_simple(dias=("Lunes", "Martes"))

    ruta = generar_pdf_oferta_busqueda(
        conn, str(tmp_path), id_prof, globales, [busqueda], excluir={(0, 0, 0)},
    )
    texto = fitz.open(ruta)[0].get_text()
    assert "Lunes: Cobertura" not in texto
    assert "Martes: Cobertura" in texto


def test_categoria_x_no_se_anonimiza(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="X", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert '7mo "L"' in texto


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
        tipo_busqueda="Aislada", ids_edificio=[id_edificio], salida="Texto", detalle_reducido=True,
    )
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [busqueda])
    texto = fitz.open(ruta)[0].get_text()
    assert "consultorio 1" not in texto.lower()  # no se identifica el consultorio puntual
    assert 'De 9 a 11hs en la unidad del 7mo "L"' in texto
    assert "Fotos de los consultorios que intervienen en las búsquedas" not in texto


def test_detalle_reducido_tambien_aplica_a_busqueda_regular(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio], detalle_reducido=True)
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "consultorio 1" not in texto.lower()
    assert "Fotos de los consultorios que intervienen en las búsquedas" not in texto


def test_detalle_tramo_formato_con_consultorio_un_edificio(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert 'De 9 a 11hs consultorio 1 del 7mo "L" - Hora regular $ 1.000' in texto
    assert "del edificio" not in texto  # un solo edificio: no se aclara


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
    assert 'consultorio 1 del 7mo "L" del edificio Ramos 1 - Hora regular' in texto
    assert 'consultorio 1 del 3ro "B" del edificio Ramos 2 - Hora regular' in texto


def test_todas_las_opciones_verdes_se_detallan(conn, tmp_path):
    """Si más de un consultorio cubre el bloque por sí solo, el PDF lista
    todas las opciones bajo el mismo día, no solo la primera."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_unidad2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='3ro "B"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad1, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad2, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert 'consultorio 1 del 7mo "L"' in texto
    assert 'consultorio 1 del 3ro "B"' in texto
    assert texto.count("Cobertura completa") == 1  # una sola línea de tipo de cobertura para el día


def test_tamano_en_minuscula_en_caracteristicas(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11,
        tamano="Grande",
    )
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [busqueda])
    texto = fitz.open(ruta)[0].get_text()
    assert "tamaño grande" in texto
    assert "tamaño Grande" not in texto


def test_cantidad_horas_minimas_arriba_de_combinacion(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Cantidad de horas mínimas dentro del rango solicitado:" in texto
    assert texto.index("Cantidad de horas mínimas dentro del rango solicitado:") < texto.index("Combinación de consultorios:")


def test_edificios_enumera_direccion_cuando_no_cubre_toda_la_localidad(conn, tmp_path):
    id_edificio1 = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 1", Domicilio="Av. Rivadavia 13876", DomicilioLocalidad="Ramos Mejía",
    )
    obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", Domicilio="Alvear 856", DomicilioLocalidad="Ramos Mejía",
    )
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio1, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio1], localidad="Ramos Mejía")
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Edificios: Av. Rivadavia 13876 (Ramos 1)" in texto


def test_edificios_enumera_los_dos_cuando_ambos_tienen_resultados(conn, tmp_path):
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
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Edificios: Av. Rivadavia 13876 (Ramos 1), Alvear 856 (Ramos 2)" in texto


def test_edificios_excluye_los_del_alcance_sin_resultados(conn, tmp_path):
    """Un edificio incluido en el alcance de la búsqueda (ids_edificio) pero
    sin ninguna coincidencia real no debe figurar en la enumeración: lo que
    importa es dónde efectivamente hay algo para ofrecer, no todo lo que se
    consultó."""
    id_edificio1 = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 1", Domicilio="Av. Rivadavia 13876", DomicilioLocalidad="Ramos Mejía",
    )
    id_edificio2 = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", Domicilio="Alvear 856", DomicilioLocalidad="Ramos Mejía",
    )
    id_unidad1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio1, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad1, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    # id_edificio2 está dentro del alcance de la búsqueda pero no tiene
    # ningún consultorio: no debe aparecer en la enumeración final.
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(
        tipo_busqueda="Regular", ids_edificio=[id_edificio1, id_edificio2], localidad="Ramos Mejía",
    )
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [_busqueda_simple()])
    texto = fitz.open(ruta)[0].get_text()
    assert "Edificios: Av. Rivadavia 13876 (Ramos 1)" in texto
    assert "Ramos 2" not in texto


def test_combinacion_misma_unidad_texto(conn, edificio_con_consultorio, tmp_path):
    id_edificio, _, _ = edificio_con_consultorio
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11,
        combinacion="MismaUnidad",
    )
    ruta = generar_pdf_oferta_busqueda(conn, str(tmp_path), id_prof, globales, [busqueda])
    texto = fitz.open(ruta)[0].get_text()
    assert "admite combinar consultorios, sin salir de la misma unidad" in texto
