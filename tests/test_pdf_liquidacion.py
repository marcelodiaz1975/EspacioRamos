import fitz
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.dias import parsear_periodo, primer_dia_mes, ultimo_dia_mes
from app.negocio.liquidaciones import calcular_liquidacion, ids_consolidados
from app.pdf.liquidacion_pdf import (
    _consultorios_y_horas,
    _items_cuenta,
    _mapa_consultorios,
    _nombre_archivo,
    generar_pdf_liquidacion,
)
from app.pdf.numeros_en_letras import en_letras_pesos, monto_en_letras
from app.repositorio.registro import obtener_repositorio

PERIODO = "2026-08"


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 1", Domicilio="Av. Rivadavia 1234", DomicilioLocalidad="CABA"
    )
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, Ventana=1,
        ValorHoraRegularActual=1000, ValorHoraAisladaActual=500,
    )


@pytest.fixture
def profesional(conn, consultorio):
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lo Veci", NombrePila="Marcela", Tratamiento="Lic.",
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=13, VigenciaInicio="2026-01-01",
    )
    return id_prof


def test_nombre_archivo_sigue_el_formato_del_documento(conn, profesional):
    prof = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert _nombre_archivo("2026-08", prof) == "2026-08 - Lic. Marcela Lo Veci - Liquidación mensual.pdf"


def test_items_cuenta_respeta_el_orden_de_dc01(conn, profesional):
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    consultorios = _mapa_consultorios(conn)
    items = _items_cuenta(liquidacion, consultorios, {}, "agosto", "julio")
    conceptos = [c for c, _, _ in items]
    assert conceptos[0].startswith("Importe bruto correspondiente a la reserva regular de agosto")
    assert conceptos[1].startswith("Descuento (")
    assert conceptos[2] == "Subtotal por reserva para el mes de agosto"
    assert conceptos[3] == "Saldo pendiente de la liquidación anterior"
    assert conceptos[-1] == "Liquidación a abonar por el profesional en el mes de agosto"
    assert items[-1][1] == pytest.approx(liquidacion.total)


def test_monto_en_letras_casos_basicos():
    assert monto_en_letras(0) == "Pesos cero con 00/100"
    assert monto_en_letras(21) == "Pesos veintiuno con 00/100"
    assert monto_en_letras(21000) == "Pesos veintiún mil con 00/100"
    assert monto_en_letras(1234.56) == "Pesos mil doscientos treinta y cuatro con 56/100"
    assert monto_en_letras(-50.25) == "Menos pesos cincuenta con 25/100"


def test_en_letras_pesos_formato_recuadro_total():
    assert en_letras_pesos(202544) == "(son pesos Doscientos dos mil quinientos cuarenta y cuatro)"
    assert en_letras_pesos(1234.56) == "(son pesos Mil doscientos treinta y cuatro con 56/100)"
    assert en_letras_pesos(0) == "(son pesos Cero)"


def test_generar_pdf_liquidacion_crea_archivo_valido(conn, profesional, tmp_path):
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))

    assert ruta.endswith(".pdf")
    with open(ruta, "rb") as f:
        contenido = f.read()
    assert contenido.startswith(b"%PDF")
    assert len(contenido) > 1000


def _texto_pdf(ruta: str) -> str:
    doc = fitz.open(ruta)
    return "\n".join(pagina.get_text() for pagina in doc)


def test_titulo_dice_liquidacion_periodo_no_detalle_reserva(conn, profesional, tmp_path):
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))
    texto = _texto_pdf(ruta)
    assert "Liquidación período 08/2026 - Lic. Marcela Lo Veci" in texto
    assert "Detalle reserva" not in texto


def test_nota_de_direccion_del_edificio_aparece(conn, profesional, tmp_path):
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))
    texto = _texto_pdf(ruta)
    assert "Edificio Ramos 1: Corresponde a Av. Rivadavia 1234, CABA." in texto


def test_barra_de_edificio_incluye_domicilio(conn, profesional, tmp_path):
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))
    texto = _texto_pdf(ruta)
    assert "Edificio Ramos 1 - Av. Rivadavia 1234, CABA" in texto


def test_condiciones_y_normas_sembradas_aparecen(conn, profesional, tmp_path):
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))
    texto = _texto_pdf(ruta)
    assert "CONDICIONES Y NORMAS GENERALES" in texto.upper()
    assert "FORMA DE PAGO" in texto.upper()
    assert "CONFORMIDAD Y CUMPLIMIENTO" in texto.upper()


def test_decimales_configurados_en_0_no_muestra_centavos(conn, profesional, tmp_path):
    from app.pdf.estilos import formatear_moneda

    obtener_repositorio(conn, "Configuracion").actualizar(1, CantidadDecimales=0)
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))
    texto = _texto_pdf(ruta)
    assert formatear_moneda(liquidacion.total, decimales=0) in texto
    assert formatear_moneda(liquidacion.total, decimales=2) not in texto


def test_fotos_sin_cargar_muestra_mensaje(conn, profesional, tmp_path):
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))
    texto = _texto_pdf(ruta)
    assert "Sin fotos cargadas." in texto


def test_titulo_de_fotos_menciona_consultorios_reservados(conn, profesional, tmp_path):
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))
    texto = _texto_pdf(ruta)
    assert "Fotos de los consultorios reservados" in texto


def test_titulo_valores_usa_la_frecuencia_de_actualizacion(conn, profesional, tmp_path):
    """Default sembrado: bimestral en meses pares — agosto vigente hasta
    septiembre, no "08/2026 y 08/2026"."""
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))
    texto = _texto_pdf(ruta)
    assert "comprendido entre 08/2026 y 09/2026" in texto


def test_consultorios_y_horas_ordenados_por_edificio_y_numero(conn, profesional, consultorio):
    id_edificio_b = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 0")
    id_unidad_b = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_b, Departamento="PB")
    consultorio_b = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad_b, NumeroConsultorio=9, ValorHoraRegularActual=800,
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=profesional, IdConsultorio=consultorio_b, DiaSemana="Martes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-01-01",
    )

    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    anio, mes = parsear_periodo(PERIODO)
    filas = _consultorios_y_horas(
        conn, ids_consolidados(conn, profesional), primer_dia_mes(anio, mes).isoformat(),
        ultimo_dia_mes(anio, mes).isoformat(), _mapa_consultorios(conn), liquidacion.descuento_horas_pct,
    )
    assert [(f["edificio"], f["consultorio"]) for f in filas] == [("Ramos 0", 9), ("Ramos 1", 1)]


def test_valores_incluye_edificios_de_la_misma_localidad_aunque_no_reserve_ahi(conn, profesional, tmp_path):
    obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", Domicilio="Av. Rivadavia 8050", DomicilioLocalidad="CABA",
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))
    texto = _texto_pdf(ruta)
    assert "Edificio Ramos 2" in texto


def test_valores_no_incluye_edificios_de_otra_localidad(conn, profesional, tmp_path):
    obtener_repositorio(conn, "Edificio").crear(
        Nombre="San Justo Norte", Domicilio="Av. San Martín 100", DomicilioLocalidad="San Justo",
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))
    texto = _texto_pdf(ruta)
    assert "San Justo Norte" not in texto
