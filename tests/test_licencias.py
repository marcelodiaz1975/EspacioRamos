import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.licencias import crear_licencia
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def profesional_con_reserva(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=20, VigenciaInicio="2026-01-01",  # 10hs/semana -> $10.000/semana
    )
    return id_prof


def _id_tipo(conn, nombre):
    tipos = obtener_repositorio(conn, "TipoLicencia").listar(Nombre=nombre)
    return tipos[0]["IdTipoLicencia"]


def test_licencia_manual_requiere_fecha_hasta(conn, profesional_con_reserva):
    id_tipo = _id_tipo(conn, "Licencia médica")
    with pytest.raises(ValueError):
        crear_licencia(
            conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
            fecha_desde="2026-08-01",
        )


def test_licencia_no_manual_calcula_fecha_hasta_sola(conn, profesional_con_reserva):
    id_tipo = _id_tipo(conn, "Licencia por duelo")  # 5 días, no manual
    id_licencia = crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-01",
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert licencia["FechaHasta"] == "2026-08-05"


def test_licencia_supera_duracion_maxima_se_rechaza(conn, profesional_con_reserva):
    id_tipo = _id_tipo(conn, "Licencia por duelo")  # máximo 5 días
    with pytest.raises(ValueError):
        crear_licencia(
            conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
            fecha_desde="2026-08-01", fecha_hasta="2026-08-10",
        )


def test_licencia_maternidad_bonifica_50_por_ciento(conn, profesional_con_reserva):
    id_tipo = _id_tipo(conn, "Licencia por maternidad")  # 50%, 90 días, no manual
    id_licencia = crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-01",
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert licencia["PorcentajeBonificacionAplicado"] == 50
    assert licencia["ValorSemanalAlMomentoDelRegistro"] == pytest.approx(10000)
    # 90 días * (10000/7) * 50% de bonificación
    esperado = (10000 / 7) * 90 * 0.5
    assert licencia["ValorBonificado"] == pytest.approx(esperado)


def test_licencia_medica_bonifica_100_por_ciento_de_un_dia(conn, profesional_con_reserva):
    id_tipo = _id_tipo(conn, "Licencia médica")  # 100%, sin límite, manual
    id_licencia = crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-01", fecha_hasta="2026-08-01",
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert licencia["ValorBonificado"] == pytest.approx(10000 / 7)
