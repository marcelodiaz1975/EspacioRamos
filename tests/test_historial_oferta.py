import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.historial_oferta import guardar_busqueda, regenerar_pdf, regenerar_texto, vaciar_historial
from app.negocio.oferta_busqueda import Busqueda, CriteriosGlobales
from app.repositorio.registro import obtener_repositorio

ANIO, MES = 2026, 8


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def busqueda_guardada(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lo Veci", NombrePila="Virginia", Tratamiento="Lic.",
    )
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11)
    id_historial = guardar_busqueda(conn, id_prof, globales, [busqueda], set(), f"{ANIO}-{MES:02d}-01")
    return id_historial


def test_guardar_busqueda_persiste_criterios(conn, busqueda_guardada):
    fila = obtener_repositorio(conn, "HistorialOferta").obtener(busqueda_guardada)
    assert fila is not None
    assert "Regular" in fila["CriteriosJSON"]


def test_regenerar_pdf_usa_los_criterios_guardados(conn, busqueda_guardada, tmp_path):
    ruta = regenerar_pdf(conn, busqueda_guardada, str(tmp_path))
    assert ruta.endswith("Oferta de consultorios - Lic. Virginia Lo Veci.pdf")
    with open(ruta, "rb") as f:
        assert f.read().startswith(b"%PDF")


def test_regenerar_texto_usa_los_criterios_guardados(conn, busqueda_guardada):
    texto = regenerar_texto(conn, busqueda_guardada)
    assert "Búsqueda requerida por el profesional" in texto


def test_regenerar_refleja_cambios_posteriores_en_la_disponibilidad(conn, busqueda_guardada, tmp_path):
    """La regeneración vuelve a resolver contra el estado actual: si se
    ocupa el único consultorio después de guardar la búsqueda, el PDF
    regenerado ya no debe ofrecerlo."""
    ocupante = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ocupante")
    id_consultorio = obtener_repositorio(conn, "Consultorio").listar()[0]["IdConsultorio"]
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=ocupante, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2020-01-01",
    )
    texto = regenerar_texto(conn, busqueda_guardada)
    assert "Sin disponibilidad" in texto


def test_regenerar_id_inexistente_lanza_error(conn):
    with pytest.raises(ValueError):
        regenerar_texto(conn, 999)


def test_vaciar_historial_borra_todo(conn, busqueda_guardada):
    borrados = vaciar_historial(conn)
    assert borrados == 1
    assert obtener_repositorio(conn, "HistorialOferta").listar() == []
