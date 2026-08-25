import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.resumen_profesional import calcular_resumen_profesional
from app.negocio.valores import obtener_porcentaje_descuento
from app.repositorio.registro import obtener_repositorio

VALOR_HORA = 1000


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
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=VALOR_HORA,
    )


def test_sin_profesional_devuelve_none(conn):
    assert calcular_resumen_profesional(conn, None) is None


def test_profesional_sin_reservas(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Sin Reserva")
    conn.commit()
    resumen = calcular_resumen_profesional(conn, id_prof)
    assert resumen.horas_semanales == 0.0
    assert resumen.porcentaje_descuento == 0.0
    assert resumen.porcentaje_vacaciones_disponible == pytest.approx(100.0)


def test_horas_semanales_suma_las_reservas_vigentes(conn, consultorio):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2020-01-01",
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Martes",
        HoraInicio=10, HoraFin=13, VigenciaInicio="2020-01-01",
    )
    conn.commit()
    resumen = calcular_resumen_profesional(conn, id_prof)
    assert resumen.horas_semanales == pytest.approx(5.0)
    assert resumen.porcentaje_descuento == pytest.approx(obtener_porcentaje_descuento(conn, 5.0))


def test_no_cuenta_reservas_ya_finalizadas(conn, consultorio):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2020-01-01", VigenciaFin="2026-01-01",
    )
    conn.commit()
    resumen = calcular_resumen_profesional(conn, id_prof)
    assert resumen.horas_semanales == 0.0


def test_consolida_equipo_del_r_cabeza(conn, consultorio):
    id_r = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Cabeza")
    id_e = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="E", Apellido="Equipo", ProfesionalCabezaEquipo=id_r,
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_r, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_e, IdConsultorio=consultorio, DiaSemana="Martes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    conn.commit()
    resumen = calcular_resumen_profesional(conn, id_r)
    assert resumen.horas_semanales == pytest.approx(2.0)  # 1hs propia + 1hs del E consolidado


def test_vacaciones_disponibles_baja_con_una_vacacion_cargada(conn, consultorio):
    from app.negocio.vacaciones import crear_vacacion

    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    dias = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    for dia in dias:
        obtener_repositorio(conn, "ReservaRegular").crear(
            IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana=dia,
            HoraInicio=10, HoraFin=12, VigenciaInicio="2020-01-01",
        )
    conn.commit()
    crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-08-03", fecha_hasta="2026-08-09")

    resumen = calcular_resumen_profesional(conn, id_prof)
    assert resumen.porcentaje_vacaciones_disponible == pytest.approx(50.0)
