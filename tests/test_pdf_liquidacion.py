import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.liquidaciones import calcular_liquidacion
from app.pdf.liquidacion_pdf import _items_cuenta, _nombre_archivo, generar_pdf_liquidacion
from app.pdf.numeros_en_letras import monto_en_letras
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
    items = _items_cuenta(liquidacion)
    conceptos = [c for c, _, _ in items]
    assert conceptos[0] == "Bruto"
    assert conceptos[1].startswith("Descuento por horas semanales")
    assert conceptos[2] == "Subtotal reserva"
    assert conceptos[3] == "Saldo anterior"
    assert conceptos[-1] == "TOTAL"
    assert items[-1][1] == pytest.approx(liquidacion.total)


def test_monto_en_letras_casos_basicos():
    assert monto_en_letras(0) == "Pesos cero con 00/100"
    assert monto_en_letras(21) == "Pesos veintiuno con 00/100"
    assert monto_en_letras(21000) == "Pesos veintiún mil con 00/100"
    assert monto_en_letras(1234.56) == "Pesos mil doscientos treinta y cuatro con 56/100"
    assert monto_en_letras(-50.25) == "Menos pesos cincuenta con 25/100"


def test_generar_pdf_liquidacion_crea_archivo_valido(conn, profesional, tmp_path):
    liquidacion = calcular_liquidacion(conn, id_profesional=profesional, periodo=PERIODO)
    ruta = generar_pdf_liquidacion(conn, liquidacion, str(tmp_path))

    assert ruta.endswith(".pdf")
    with open(ruta, "rb") as f:
        contenido = f.read()
    assert contenido.startswith(b"%PDF")
    assert len(contenido) > 1000
