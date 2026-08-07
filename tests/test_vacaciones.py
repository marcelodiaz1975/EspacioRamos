import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.vacaciones import crear_vacacion
from app.negocio.valores import obtener_porcentaje_descuento
from app.repositorio.registro import obtener_repositorio

VALOR_HORA = 1000


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
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=VALOR_HORA,
    )


def _profesional_con_reserva(conn, consultorio, categoria="R", dias=("Lunes",), horas_por_dia=2):
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional=categoria, Apellido="Lo Veci",
    )
    for dia in dias:
        obtener_repositorio(conn, "ReservaRegular").crear(
            IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana=dia,
            HoraInicio=10, HoraFin=10 + horas_por_dia, VigenciaInicio="2026-01-01",
        )
    return id_prof


def _valor_semanal_esperado(conn, horas_semanales):
    descuento_pct = obtener_porcentaje_descuento(conn, horas_semanales)
    return horas_semanales * VALOR_HORA * (1 - descuento_pct / 100)


def test_categoria_a_no_tiene_derecho_a_vacaciones(conn, consultorio):
    id_prof = _profesional_con_reserva(conn, consultorio, categoria="A")
    with pytest.raises(ValueError):
        crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-08-01", fecha_hasta="2026-08-07")


def test_sin_reserva_regular_no_tiene_derecho(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Sin Reserva")
    with pytest.raises(ValueError):
        crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-08-01", fecha_hasta="2026-08-07")


def test_vacacion_cubre_todos_los_dias_reservados_de_la_semana(conn, consultorio):
    # reserva los 7 días de la semana, 2hs cada uno -> 14hs/semana
    dias = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    id_prof = _profesional_con_reserva(conn, consultorio, dias=dias, horas_por_dia=2)
    valor_semanal = _valor_semanal_esperado(conn, horas_semanales=14)

    # 2026-08-03 (lunes) a 2026-08-09 (domingo): la semana completa
    id_vacacion, advertencias = crear_vacacion(
        conn, id_profesional=id_prof, fecha_desde="2026-08-03", fecha_hasta="2026-08-09",
    )
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)
    assert advertencias == []
    assert vacacion["ValorSemanalAlMomentoDelRegistro"] == pytest.approx(valor_semanal)
    assert vacacion["ValorBonificado"] == pytest.approx(valor_semanal)
    assert vacacion["FraccionSemanaConsumida"] == pytest.approx(1.0)
    assert vacacion["CupoConsumidoPorcentaje"] == pytest.approx(50.0)  # 1 de 2 semanas
    assert vacacion["CupoRestantePorcentaje"] == pytest.approx(50.0)


def test_vacacion_solo_bonifica_dias_efectivamente_reservados(conn, consultorio):
    # solo reserva lunes y miércoles, 2hs cada uno -> 4hs/semana
    id_prof = _profesional_con_reserva(conn, consultorio, dias=("Lunes", "Miércoles"), horas_por_dia=2)
    valor_semanal = _valor_semanal_esperado(conn, horas_semanales=4)
    valor_por_dia_reservado = 2 * VALOR_HORA * (1 - obtener_porcentaje_descuento(conn, 4) / 100)

    # 2026-08-03 (lunes) a 2026-08-05 (miércoles): toca lunes y miércoles, no martes
    id_vacacion, advertencias = crear_vacacion(
        conn, id_profesional=id_prof, fecha_desde="2026-08-03", fecha_hasta="2026-08-05",
    )
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)
    assert advertencias == []
    esperado_bonificado = 2 * valor_por_dia_reservado  # lunes + miércoles
    assert vacacion["ValorBonificado"] == pytest.approx(esperado_bonificado)
    assert vacacion["FraccionSemanaConsumida"] == pytest.approx(esperado_bonificado / valor_semanal)


def test_vacacion_que_excede_cupo_no_bloquea_y_prorratea(conn, consultorio):
    dias = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    id_prof = _profesional_con_reserva(conn, consultorio, dias=dias, horas_por_dia=2)

    # consume el cupo completo (2 semanas) de entrada
    crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-01-05", fecha_hasta="2026-01-18")

    # una semana más, ya sin cupo disponible
    id_vacacion, advertencias = crear_vacacion(
        conn, id_profesional=id_prof, fecha_desde="2026-03-02", fecha_hasta="2026-03-08",
    )
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)
    assert len(advertencias) == 1
    assert "excede el cupo" in advertencias[0]
    assert vacacion["ValorBonificado"] == pytest.approx(0.0, abs=1e-6)
    assert vacacion["FraccionSemanaConsumida"] == pytest.approx(0.0, abs=1e-9)
    assert vacacion["CupoConsumidoPorcentaje"] == pytest.approx(100.0)
    assert vacacion["CupoRestantePorcentaje"] == pytest.approx(0.0, abs=1e-6)


def test_vacacion_parcialmente_dentro_del_cupo_se_prorratea(conn, consultorio):
    dias = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    id_prof = _profesional_con_reserva(conn, consultorio, dias=dias, horas_por_dia=2)

    # consume 10/7 semanas (~1.43) del cupo de 2: reserva los 7 días, la
    # vacación cubre 10 días corridos -> 10 días reservados bonificados
    crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-01-05", fecha_hasta="2026-01-14")

    # pide 1 semana más (quedan 4/7 semanas de cupo, ~0.57)
    id_vacacion, advertencias = crear_vacacion(
        conn, id_profesional=id_prof, fecha_desde="2026-03-02", fecha_hasta="2026-03-08",
    )
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)
    assert len(advertencias) == 1
    assert vacacion["FraccionSemanaConsumida"] == pytest.approx(4 / 7)
    assert vacacion["CupoConsumidoPorcentaje"] == pytest.approx(100.0)
    assert vacacion["ValorBonificado"] > 0
    assert vacacion["ValorBonificado"] < vacacion["ValorSemanalAlMomentoDelRegistro"]


def test_categoria_b_no_genera_descuento_pero_consume_cupo(conn, consultorio):
    dias = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    id_prof = _profesional_con_reserva(conn, consultorio, categoria="B", dias=dias, horas_por_dia=2)

    id_vacacion, advertencias = crear_vacacion(
        conn, id_profesional=id_prof, fecha_desde="2026-08-03", fecha_hasta="2026-08-09",
    )
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)
    assert advertencias == []
    assert vacacion["ValorBonificado"] == 0.0
    assert vacacion["FraccionSemanaConsumida"] == pytest.approx(1.0)
    assert vacacion["CupoConsumidoPorcentaje"] == pytest.approx(50.0)


def test_cupo_por_anio_no_se_mezcla(conn, consultorio):
    dias = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    id_prof = _profesional_con_reserva(conn, consultorio, dias=dias, horas_por_dia=2)
    crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-01-05", fecha_hasta="2026-01-18")  # 2 semanas 2026

    # el cupo de 2027 debería estar entero disponible
    id_vacacion, advertencias = crear_vacacion(
        conn, id_profesional=id_prof, fecha_desde="2027-01-04", fecha_hasta="2027-01-10",
    )
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)
    assert advertencias == []
    assert vacacion["CupoConsumidoPorcentaje"] == pytest.approx(50.0)
