import fitz
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.liquidacion_simulada import BloqueSimulado, calcular_liquidacion_simulada
from app.pdf.liquidacion_simulada_pdf import generar_pdf_liquidacion_simulada, nombre_archivo_liquidacion_simulada
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def profesional(conn):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Tratamiento="Dra.", NombrePila="Virginia", Apellido="Lo Veci", IdCodigo="R9",
    )


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="7mo L")
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )


def test_nombre_archivo_sigue_el_formato_pedido(conn, profesional):
    fila = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert nombre_archivo_liquidacion_simulada("2026-11", fila) == "2026-11 - Liquidación simulada Dra. Virginia Lo Veci.pdf"


def test_genera_pdf_con_los_bloques_y_el_total(conn, profesional, consultorio, tmp_path):
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])

    ruta = generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))
    assert ruta.endswith("2026-11 - Liquidación simulada Dra. Virginia Lo Veci.pdf")

    texto = "".join(pagina.get_text() for pagina in fitz.open(ruta))
    assert "Liquidación simulada" in texto
    assert "Lunes" in texto
    assert "9hs a 11hs" in texto
    assert "consul 1 del 7mo L - Ramos 1" in texto
    from app.negocio.formato import formatear_moneda
    assert formatear_moneda(liquidacion.neto) in texto


def test_pdf_incluye_descuento_de_feriado_cuando_hay(conn, profesional, consultorio, tmp_path):
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-11-02", Descripcion="Feriado de prueba", Tipo="Feriado nacional",
    )
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])
    assert liquidacion.descuentos_feriados

    ruta = generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))
    texto = "".join(pagina.get_text() for pagina in fitz.open(ruta))
    assert "Descuento feriado nacional (2026-11-02)" in texto


def test_profesional_inexistente_rechaza(conn, tmp_path):
    from app.negocio.liquidacion_simulada import LiquidacionSimulada
    liquidacion = LiquidacionSimulada(
        id_profesional=999999, periodo="2026-11", bloques=[], horas_semanales=0, descuento_horas_pct=0, bruto=0,
    )
    with pytest.raises(ValueError):
        generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))
