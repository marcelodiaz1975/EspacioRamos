import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.grilla_operativa import (
    AMARILLO,
    AZUL_OSCURO,
    BLANCA,
    BLANCO,
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


def _celda(conn, id_consultorio, modo="regular", desde="2026-08-01", hasta="2026-08-31", id_profesional_filtro=None):
    grilla = calcular_grilla_operativa(
        conn, [id_consultorio], ["Lunes"], 9, 10, desde, hasta, modo=modo, id_profesional_filtro=id_profesional_filtro,
    )
    return grilla[(id_consultorio, "Lunes", 9)]


# --------------------------------------------------------------- modo regular

def test_regular_celda_libre(conn, consultorio):
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, BLANCO)
    assert celda.codigo is None
    assert celda.detalle == "Horario disponible."


def test_regular_activa_sin_liberarse_dentro_del_rango(conn, consultorio, virginia):
    """Verde completo: reserva activa hoy que no se libera dentro del rango."""
    _regular(conn, virginia, consultorio, vigencia_fin="2026-12-31")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (VERDE, VERDE)
    assert celda.codigo == "R1"


def test_regular_activa_sin_vigencia_fin(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio)
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (VERDE, VERDE)


def test_regular_activa_que_se_libera_dentro_del_rango(conn, consultorio, virginia):
    """Blanco completo: se libera DENTRO del rango consultado, sin nadie más tomando el lugar."""
    _regular(conn, virginia, consultorio, vigencia_fin="2026-08-20")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, BLANCO)
    assert celda.codigo == "R1"


def test_regular_entrante_sin_titular_actual(conn, consultorio, eugenia):
    """Rojo completo: nadie lo ocupa ahora, pero ya hay una reserva cargada a futuro."""
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)
    assert celda.codigo is None
    assert "Horario reservado por Lic. Eugenia Viegas (R2) a partir del jueves 3/9." in celda.detalle


def test_regular_entrante_arranca_dentro_del_rango_tambien_es_rojo(conn, consultorio, eugenia):
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-08-18")
    celda = _celda(conn, consultorio, desde="2026-08-01", hasta="2026-08-31")
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)


def test_regular_conflicto_con_profesional_distinto_entrante(conn, consultorio, virginia, eugenia):
    """Rojo completo: hoy lo tiene Virginia, pero después del rango pasa a Eugenia."""
    _regular(conn, virginia, consultorio)
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)
    assert celda.codigo == "R1"
    assert celda.detalle == (
        "Horario reservado por Lic. Virginia Lo Veci (R1). "
        "Horario reservado por Lic. Eugenia Viegas (R2) a partir del jueves 3/9."
    )


def test_regular_conflicto_mas_aislada_en_rango(conn, consultorio, virginia, eugenia):
    _regular(conn, virginia, consultorio)
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (ROJO, AMARILLO)
    assert "Hora aislada reservada por Lic. Eugenia Viegas (R2) para el lunes 17/8." in celda.detalle


def test_regular_con_hueco_por_vacacion(conn, consultorio, virginia):
    """Blanco con centro verde: reservado en el rango, pero libera un día suelto por vacaciones."""
    _regular(conn, virginia, consultorio, vigencia_fin="2026-12-31")
    obtener_repositorio(conn, "Vacacion").crear(IdProfesional=virginia, FechaDesde="2026-08-15", FechaHasta="2026-08-25")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, VERDE)
    assert celda.codigo == "R1"
    assert "De vacaciones desde el sábado 15/8 hasta el martes 25/8." in celda.detalle


def test_regular_con_hueco_ya_tomado_por_aislada(conn, consultorio, virginia, eugenia):
    """Blanco con centro amarillo: el hueco de la vacación ya tiene una aislada adentro."""
    _regular(conn, virginia, consultorio, vigencia_fin="2026-12-31")
    obtener_repositorio(conn, "Vacacion").crear(IdProfesional=virginia, FechaDesde="2026-08-15", FechaHasta="2026-08-25")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, AMARILLO)
    assert "De vacaciones desde el sábado 15/8 hasta el martes 25/8." in celda.detalle
    assert "Hora aislada reservada por Lic. Eugenia Viegas (R2) para el lunes 17/8." in celda.detalle


def test_regular_solo_aislada_en_rango(conn, consultorio, eugenia):
    """Amarillo completo: libre de regular en todo el rango, pero hay una aislada."""
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (AMARILLO, AMARILLO)
    assert celda.codigo == "R2"
    assert celda.detalle == "Hora aislada reservada por Lic. Eugenia Viegas (R2) para el lunes 17/8."


def test_regular_filtro_pinta_azul_cuando_es_el_titular_actual(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio, vigencia_fin="2026-12-31")
    celda = _celda(conn, consultorio, id_profesional_filtro=virginia)
    assert (celda.color_aro, celda.color_centro, celda.color_fuente) == (AZUL_OSCURO, AZUL_OSCURO, BLANCA)


def test_regular_filtro_no_pinta_azul_si_solo_es_entrante(conn, consultorio, virginia, eugenia):
    _regular(conn, virginia, consultorio)
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    celda = _celda(conn, consultorio, id_profesional_filtro=eugenia)
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)


def test_regular_filtro_pinta_azul_sobre_aislada_mostrada(conn, consultorio, eugenia):
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio, id_profesional_filtro=eugenia)
    assert (celda.color_aro, celda.color_centro, celda.color_fuente) == (AZUL_OSCURO, AZUL_OSCURO, BLANCA)


# -------------------------------------------------------------- modo aislada

def test_aislada_libre_de_regular(conn, consultorio):
    celda = _celda(conn, consultorio, modo="aislada")
    assert (celda.color_aro, celda.color_centro) == (VERDE, VERDE)
    assert celda.codigo is None


def test_aislada_bloqueada_por_regular_sin_hueco(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio, vigencia_fin="2026-12-31")
    celda = _celda(conn, consultorio, modo="aislada")
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)
    assert celda.codigo is None


def test_aislada_con_hueco_disponible_por_vacacion(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio, vigencia_fin="2026-12-31")
    obtener_repositorio(conn, "Vacacion").crear(IdProfesional=virginia, FechaDesde="2026-08-15", FechaHasta="2026-08-25")
    celda = _celda(conn, consultorio, modo="aislada")
    assert (celda.color_aro, celda.color_centro) == (ROJO, VERDE)
    assert "De vacaciones desde el sábado 15/8 hasta el martes 25/8." in celda.detalle


def test_aislada_con_hueco_ya_tomado(conn, consultorio, virginia, eugenia):
    _regular(conn, virginia, consultorio, vigencia_fin="2026-12-31")
    obtener_repositorio(conn, "Vacacion").crear(IdProfesional=virginia, FechaDesde="2026-08-15", FechaHasta="2026-08-25")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio, modo="aislada")
    assert (celda.color_aro, celda.color_centro) == (ROJO, AMARILLO)
    assert celda.codigo == "R2"


def test_aislada_libre_con_aislada_asignada(conn, consultorio, eugenia):
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio, modo="aislada")
    assert (celda.color_aro, celda.color_centro) == (AMARILLO, AMARILLO)
    assert celda.codigo == "R2"


def test_aislada_ignora_entrante_futuro(conn, consultorio, eugenia):
    """Modo aislada no le da bola a reservas regulares que todavía no arrancaron."""
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    celda = _celda(conn, consultorio, modo="aislada")
    assert (celda.color_aro, celda.color_centro) == (VERDE, VERDE)


def test_aislada_filtro_pinta_azul(conn, consultorio, eugenia):
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio, modo="aislada", id_profesional_filtro=eugenia)
    assert (celda.color_aro, celda.color_centro, celda.color_fuente) == (AZUL_OSCURO, AZUL_OSCURO, BLANCA)


def test_aislada_dos_reservas_muestra_la_mas_proxima(conn, consultorio, virginia, eugenia):
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-24", HoraInicio=9, HoraFin=10,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=virginia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio, modo="aislada")
    assert celda.codigo == "R1"  # 17/8 está más cerca del 10/8 (hoy) que el 24/8
