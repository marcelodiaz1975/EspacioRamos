import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.ausencias import cancelar_ausencia, crear_ausencia, esta_ausente
from app.negocio.reservas import crear_reserva_aislada, crear_reserva_regular
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
    return obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)


@pytest.fixture
def profesional(conn):
    return obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")


def test_esta_ausente_todos_los_consultorios(conn, profesional):
    crear_ausencia(conn, id_profesional=profesional, fecha_desde="2026-08-10", fecha_hasta="2026-08-14")
    assert esta_ausente(conn, profesional, "2026-08-12", id_consultorio=99) is True
    assert esta_ausente(conn, profesional, "2026-08-20", id_consultorio=99) is False


def test_esta_ausente_consultorio_especifico(conn, profesional, consultorio):
    crear_ausencia(
        conn, id_profesional=profesional, fecha_desde="2026-08-10", fecha_hasta="2026-08-14",
        id_consultorio=consultorio,
    )
    assert esta_ausente(conn, profesional, "2026-08-12", id_consultorio=consultorio) is True
    assert esta_ausente(conn, profesional, "2026-08-12", id_consultorio=consultorio + 1) is False


def test_ausencia_libera_consultorio_para_aislada_de_otro_profesional(conn, profesional, consultorio):
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Gomez")
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    # 2026-08-10 es lunes
    crear_ausencia(conn, id_profesional=profesional, fecha_desde="2026-08-10", fecha_hasta="2026-08-10")

    id_reserva, advertencias = crear_reserva_aislada(
        conn, id_profesional=otro_profesional, id_consultorio=consultorio,
        fecha="2026-08-10", hora_inicio=14, hora_fin=15,
    )
    assert id_reserva is not None
    assert advertencias == []


def test_cancelar_ausencia_sin_aisladas_se_elimina(conn, profesional):
    id_ausencia = crear_ausencia(conn, id_profesional=profesional, fecha_desde="2026-08-10", fecha_hasta="2026-08-14")
    cancelar_ausencia(conn, id_ausencia)
    assert obtener_repositorio(conn, "Ausencia").obtener(id_ausencia) is None


def test_crear_ausencia_queda_vinculada_a_la_reserva_aislada_que_la_origino(conn, profesional, consultorio):
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=profesional, id_consultorio=consultorio,
        fecha="2026-08-10", hora_inicio=9, hora_fin=10,
    )
    id_ausencia = crear_ausencia(
        conn, id_profesional=profesional, fecha_desde="2026-08-17", fecha_hasta="2026-08-17",
        id_consultorio=consultorio, motivo="Reubicación", id_reserva_aislada=id_reserva,
    )
    ausencia = obtener_repositorio(conn, "Ausencia").obtener(id_ausencia)
    assert ausencia["IdReservaAislada"] == id_reserva


def test_crear_ausencia_sin_reserva_aislada_queda_sin_vincular(conn, profesional):
    id_ausencia = crear_ausencia(conn, id_profesional=profesional, fecha_desde="2026-08-10", fecha_hasta="2026-08-14")
    ausencia = obtener_repositorio(conn, "Ausencia").obtener(id_ausencia)
    assert ausencia["IdReservaAislada"] is None


def test_cancelar_ausencia_bloqueada_por_aislada_ya_asignada(conn, profesional, consultorio):
    """DC-04 §3.2/§3.3, aclarado en conversación: si ya se asignó una
    aislada a otro profesional aprovechando el consultorio liberado, no
    se puede anular la ausencia — chocaría con la reserva regular que
    vuelve a regir."""
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Gomez")
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    id_ausencia = crear_ausencia(conn, id_profesional=profesional, fecha_desde="2026-08-10", fecha_hasta="2026-08-10")
    crear_reserva_aislada(
        conn, id_profesional=otro_profesional, id_consultorio=consultorio,
        fecha="2026-08-10", hora_inicio=14, hora_fin=15,
    )

    with pytest.raises(ValueError):
        cancelar_ausencia(conn, id_ausencia)
    assert obtener_repositorio(conn, "Ausencia").obtener(id_ausencia) is not None


def test_cancelar_ausencia_no_bloquea_por_aislada_de_otro_horario(conn, profesional, consultorio):
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Gomez")
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    id_ausencia = crear_ausencia(conn, id_profesional=profesional, fecha_desde="2026-08-10", fecha_hasta="2026-08-10")
    # aislada fuera del horario que la ausencia libera -> no debería chocar
    crear_reserva_aislada(
        conn, id_profesional=otro_profesional, id_consultorio=consultorio,
        fecha="2026-08-10", hora_inicio=10, hora_fin=11,
    )

    cancelar_ausencia(conn, id_ausencia)
    assert obtener_repositorio(conn, "Ausencia").obtener(id_ausencia) is None
