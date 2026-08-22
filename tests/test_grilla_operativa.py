import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.grilla_operativa import (
    AMARILLO,
    AZUL_OSCURO,
    BLANCA,
    BLANCO,
    NEGRA,
    ROJO,
    VERDE,
    calcular_grilla_operativa,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    connection.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-10' WHERE IdConfiguracion = 1"
    )
    connection.commit()
    yield connection
    connection.close()


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )


@pytest.fixture
def virginia(conn):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lo Veci", NombrePila="Virginia", Tratamiento="Lic.", IdCodigo="R1",
    )


@pytest.fixture
def eugenia(conn):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Viegas", NombrePila="Eugenia", Tratamiento="Lic.", IdCodigo="R2",
    )


def _regular(conn, id_profesional, id_consultorio, vigencia_inicio="2026-01-01", vigencia_fin=None):
    return obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio=vigencia_inicio, VigenciaFin=vigencia_fin,
    )


def _celda(conn, id_consultorio, id_profesional_filtro=None):
    grilla = calcular_grilla_operativa(
        conn, [id_consultorio], ["Lunes"], 9, 10, "2026-08", id_profesional_filtro=id_profesional_filtro,
    )
    return grilla[(id_consultorio, "Lunes", 9)]


def test_regular_sin_novedad(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio)
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro, celda.color_fuente) == (BLANCO, BLANCO, NEGRA)
    assert celda.codigo == "R1"
    assert celda.detalle == "Horario reservado por Lic. Virginia Lo Veci (R1)."


def test_celda_libre(conn, consultorio):
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, BLANCO)
    assert celda.codigo is None
    assert celda.detalle == "Horario disponible."


def test_regular_con_vacacion_futura(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio)
    obtener_repositorio(conn, "Vacacion").crear(IdProfesional=virginia, FechaDesde="2026-08-15", FechaHasta="2026-08-25")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, VERDE)
    assert "De vacaciones desde el sábado 15/8 hasta el martes 25/8." in celda.detalle


def test_regular_con_licencia_futura(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio)
    id_tipo = obtener_repositorio(conn, "TipoLicencia").crear(Nombre="Maternidad", PorcentajeBonificacion=100)
    obtener_repositorio(conn, "Licencia").crear(
        IdProfesional=virginia, IdTipoLicencia=id_tipo, FechaDesde="2026-08-15", FechaHasta="2026-08-25",
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, VERDE)
    assert "De licencia por maternidad desde el sábado 15/8 hasta el martes 25/8." in celda.detalle


def test_regular_con_ausencia_un_dia(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio)
    obtener_repositorio(conn, "Ausencia").crear(
        IdProfesional=virginia, FechaDesde="2026-08-17", FechaHasta="2026-08-17", Motivo="Motivos personales",
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, VERDE)
    assert "Ausente por motivos personales el lunes 17/8." in celda.detalle


def test_regular_con_baja_propia_futura(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio, vigencia_fin="2026-09-01")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (VERDE, VERDE)
    assert "Horario liberado a partir del miércoles 2/9." in celda.detalle


def test_regular_con_baja_propia_y_aislada(conn, consultorio, virginia, eugenia):
    _regular(conn, virginia, consultorio, vigencia_fin="2026-09-01")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-09-07", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (VERDE, AMARILLO)
    assert "Horario liberado a partir del miércoles 2/9." in celda.detalle
    assert "Hora aislada reservada por Lic. Eugenia Viegas (R2) para el lunes 7/9." in celda.detalle


def test_regular_con_profesional_entrante_distinto(conn, consultorio, virginia, eugenia):
    _regular(conn, virginia, consultorio)
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)
    assert celda.detalle == (
        "Horario reservado por Lic. Virginia Lo Veci (R1). "
        "Horario reservado por Lic. Eugenia Viegas (R2) a partir del jueves 3/9."
    )


def test_libre_con_profesional_entrante_y_vacacion_propia(conn, consultorio, eugenia):
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    obtener_repositorio(conn, "Vacacion").crear(IdProfesional=eugenia, FechaDesde="2026-09-15", FechaHasta="2026-09-22")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (ROJO, VERDE)
    assert "Horario reservado por Lic. Eugenia Viegas (R2) a partir del jueves 3/9." in celda.detalle
    assert "De vacaciones desde el martes 15/9 hasta el martes 22/9." in celda.detalle


def test_libre_con_profesional_entrante_y_aislada(conn, consultorio, virginia, eugenia):
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=virginia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (ROJO, AMARILLO)
    assert "Horario reservado por Lic. Eugenia Viegas (R2) a partir del jueves 3/9." in celda.detalle
    assert "Hora aislada reservada por Lic. Virginia Lo Veci (R1) para el lunes 17/8." in celda.detalle


def test_regular_con_aislada_futura(conn, consultorio, virginia, eugenia):
    _regular(conn, virginia, consultorio)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (AMARILLO, AMARILLO)
    assert celda.detalle == (
        "Horario reservado por Lic. Virginia Lo Veci (R1). "
        "Hora aislada reservada por Lic. Eugenia Viegas (R2) para el lunes 17/8."
    )


def test_solo_aislada_futura(conn, consultorio, virginia):
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=virginia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (AMARILLO, AMARILLO)
    assert celda.codigo is None
    assert celda.detalle == "Hora aislada reservada por Lic. Virginia Lo Veci (R1) para el lunes 17/8."


def test_filtro_profesional_regla_1(conn, consultorio, virginia):
    """Jerarquía 1: si el profesional filtrado tiene la reserva regular
    ESTE MES en la celda, pisa cualquier otro color."""
    _regular(conn, virginia, consultorio)
    obtener_repositorio(conn, "Vacacion").crear(IdProfesional=virginia, FechaDesde="2026-08-15", FechaHasta="2026-08-25")
    celda = _celda(conn, consultorio, id_profesional_filtro=virginia)
    assert (celda.color_aro, celda.color_centro, celda.color_fuente) == (AZUL_OSCURO, AZUL_OSCURO, BLANCA)


def test_filtro_profesional_no_aplica_si_no_es_el_titular_actual(conn, consultorio, virginia, eugenia):
    """El filtro solo pinta de azul las celdas donde el profesional
    filtrado tiene la reserva regular vigente ESTE MES — no alcanza con
    aparecer como entrante futuro."""
    _regular(conn, virginia, consultorio)
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    celda = _celda(conn, consultorio, id_profesional_filtro=eugenia)
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)
