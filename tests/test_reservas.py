from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.dias import fecha_a_dia_semana
from app.negocio.reservas import (
    ConflictoBloqueanteError,
    cancelar_reserva_aislada,
    crear_reserva_aislada,
    crear_reserva_regular,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def consultorio(conn):
    edificios = obtener_repositorio(conn, "Edificio")
    unidades = obtener_repositorio(conn, "Unidad")
    consultorios = obtener_repositorio(conn, "Consultorio")

    id_edificio = edificios.crear(Nombre="Ramos 1")
    id_unidad = unidades.crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return consultorios.crear(IdUnidad=id_unidad, NumeroConsultorio=1, Ventana=1)


@pytest.fixture
def profesional_factory(conn):
    profesionales = obtener_repositorio(conn, "Profesional")

    def crear(apellido, categoria="R", cabeza_equipo=None):
        return profesionales.crear(
            CategoriaProfesional=categoria, Apellido=apellido,
            ProfesionalCabezaEquipo=cabeza_equipo,
        )
    return crear


# ---------------------------------------------------------- reserva regular

def test_crear_reserva_regular_sin_conflictos(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, advertencias = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    assert id_reserva is not None
    assert advertencias == []


def test_superposicion_entre_profesionales_distintos_bloquea(conn, consultorio, profesional_factory):
    id_prof_a = profesional_factory("Lo Veci")
    id_prof_b = profesional_factory("Gomez")
    crear_reserva_regular(
        conn, id_profesional=id_prof_a, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    with pytest.raises(ConflictoBloqueanteError):
        crear_reserva_regular(
            conn, id_profesional=id_prof_b, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=15, hora_fin=17, vigencia_inicio="2026-01-01",
        )


def test_superposicion_equipo_e_con_su_r_solo_advierte(conn, consultorio, profesional_factory):
    id_r = profesional_factory("Cabeza de equipo", categoria="R")
    id_e = profesional_factory("Empleada", categoria="E", cabeza_equipo=id_r)

    crear_reserva_regular(
        conn, id_profesional=id_r, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=18, vigencia_inicio="2026-01-01",
    )
    id_reserva, advertencias = crear_reserva_regular(
        conn, id_profesional=id_e, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=15, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    assert id_reserva is not None
    assert len(advertencias) == 1
    assert "reserva regular" in advertencias[0]


def test_forzar_ignora_conflicto_bloqueante(conn, consultorio, profesional_factory):
    id_prof_a = profesional_factory("Lo Veci")
    id_prof_b = profesional_factory("Gomez")
    crear_reserva_regular(
        conn, id_profesional=id_prof_a, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    id_reserva, advertencias = crear_reserva_regular(
        conn, id_profesional=id_prof_b, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=15, hora_fin=17, vigencia_inicio="2026-01-01", forzar=True,
    )
    assert id_reserva is not None
    assert advertencias


def test_no_superposicion_si_no_hay_solapamiento_horario(conn, consultorio, profesional_factory):
    id_prof_a = profesional_factory("Lo Veci")
    id_prof_b = profesional_factory("Gomez")
    crear_reserva_regular(
        conn, id_profesional=id_prof_a, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    id_reserva, advertencias = crear_reserva_regular(
        conn, id_profesional=id_prof_b, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=16, hora_fin=18, vigencia_inicio="2026-01-01",
    )
    assert id_reserva is not None
    assert advertencias == []


# ---------------------------------------------------------------- bloque rígido

def test_reserva_parcial_de_bloque_rigido_solo_advierte(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, advertencias = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=9, hora_fin=10, vigencia_inicio="2026-01-01",
    )
    assert id_reserva is not None
    assert len(advertencias) == 1
    assert "bloque rígido" in advertencias[0]


def test_reserva_que_cubre_bloque_rigido_completo_no_bloquea(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, advertencias = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=9, hora_fin=11, vigencia_inicio="2026-01-01",
    )
    assert id_reserva is not None
    assert advertencias == []


# ---------------------------------------------------------------- reserva aislada

def test_reserva_aislada_choca_con_regular_vigente(conn, consultorio, profesional_factory):
    id_prof_a = profesional_factory("Lo Veci")
    id_prof_b = profesional_factory("Gomez")
    proxima_fecha = date(2026, 8, 10)  # se ajusta el día de semana de la regular a esta fecha
    dia_semana = fecha_a_dia_semana(proxima_fecha)

    crear_reserva_regular(
        conn, id_profesional=id_prof_a, id_consultorio=consultorio, dia_semana=dia_semana,
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    with pytest.raises(ConflictoBloqueanteError):
        crear_reserva_aislada(
            conn, id_profesional=id_prof_b, id_consultorio=consultorio,
            fecha=proxima_fecha.isoformat(), hora_inicio=15, hora_fin=16,
        )


def test_reserva_aislada_sin_conflicto_toma_recargo_por_defecto(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, advertencias = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-10", hora_inicio=11, hora_fin=12,
    )
    reserva = obtener_repositorio(conn, "ReservaAislada").obtener(id_reserva)
    assert reserva["AplicaRecargo"] == 0  # RecargoAisladasActivoPorDefecto = 0 por defecto
    assert advertencias == []


# ---------------------------------------------------------------- cancelación

def test_cancelar_reserva_aislada_otro_dia_no_requiere_aviso(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12,
    )
    requiere_aviso = cancelar_reserva_aislada(conn, id_reserva, fecha_actual="2026-08-10")
    assert requiere_aviso is False
    assert obtener_repositorio(conn, "ReservaAislada").obtener(id_reserva)["Estado"] == "Cancelada"


def test_cancelar_reserva_aislada_mismo_dia_requiere_aviso(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12,
    )
    requiere_aviso = cancelar_reserva_aislada(conn, id_reserva, fecha_actual="2026-08-20")
    assert requiere_aviso is True


def test_cancelar_reserva_aislada_mismo_dia_en_bloque_rigido_falla(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=9, hora_fin=11,
    )
    with pytest.raises(ValueError):
        cancelar_reserva_aislada(conn, id_reserva, fecha_actual="2026-08-20")
