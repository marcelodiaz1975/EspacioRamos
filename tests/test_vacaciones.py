import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.vacaciones import CupoVacacionesExcedidoError, crear_vacacion
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )


def _profesional_con_reserva(conn, consultorio, categoria="R", horas_semana=10):
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional=categoria, Apellido="Lo Veci",
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=10 + horas_semana, VigenciaInicio="2026-01-01",
    )
    return id_prof


def test_categoria_a_no_tiene_derecho_a_vacaciones(conn, consultorio):
    id_prof = _profesional_con_reserva(conn, consultorio, categoria="A")
    with pytest.raises(ValueError):
        crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-08-01", fecha_hasta="2026-08-07")


def test_sin_reserva_regular_no_tiene_derecho(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Sin Reserva")
    with pytest.raises(ValueError):
        crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-08-01", fecha_hasta="2026-08-07")


def test_vacacion_de_una_semana_completa(conn, consultorio):
    id_prof = _profesional_con_reserva(conn, consultorio, horas_semana=10)  # $10.000/semana
    id_vacacion = crear_vacacion(
        conn, id_profesional=id_prof, fecha_desde="2026-08-03", fecha_hasta="2026-08-09"  # 7 días
    )
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)
    assert vacacion["FraccionSemanaConsumida"] == pytest.approx(1.0)
    assert vacacion["ValorSemanalAlMomentoDelRegistro"] == pytest.approx(10000)
    assert vacacion["ValorBonificado"] == pytest.approx(10000)
    assert vacacion["CupoConsumidoPorcentaje"] == pytest.approx(50.0)  # 1 de 2 semanas
    assert vacacion["CupoRestantePorcentaje"] == pytest.approx(50.0)


def test_vacacion_excede_cupo_se_rechaza(conn, consultorio):
    id_prof = _profesional_con_reserva(conn, consultorio)
    crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-01-05", fecha_hasta="2026-01-11")  # 1 semana
    crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-02-02", fecha_hasta="2026-02-08")  # 1 semana más -> 2/2
    with pytest.raises(CupoVacacionesExcedidoError):
        crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-03-02", fecha_hasta="2026-03-08")


def test_vacacion_excede_cupo_se_puede_forzar(conn, consultorio):
    id_prof = _profesional_con_reserva(conn, consultorio)
    crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-01-05", fecha_hasta="2026-01-18")  # 2 semanas -> cupo lleno
    id_vacacion = crear_vacacion(
        conn, id_profesional=id_prof, fecha_desde="2026-03-02", fecha_hasta="2026-03-08",
        forzar=True,
    )
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)
    assert vacacion["CupoConsumidoPorcentaje"] > 100


def test_cupo_por_anio_no_se_mezcla(conn, consultorio):
    id_prof = _profesional_con_reserva(conn, consultorio)
    crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-01-05", fecha_hasta="2026-01-18")  # 2 semanas 2026
    # el mismo cupo de 2027 debería estar entero disponible
    id_vacacion = crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2027-01-04", fecha_hasta="2027-01-10")
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)
    assert vacacion["CupoConsumidoPorcentaje"] == pytest.approx(50.0)
