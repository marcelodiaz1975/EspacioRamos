import json

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.ausencias import crear_ausencia
from app.negocio.grilla import (
    DIAS_GRILLA_DEFAULT,
    aisladas_confirmadas_fecha,
    calcular_grilla,
    calcular_ocupacion_fecha,
    dias_grilla,
)
from app.negocio.reservas import crear_reserva_aislada, crear_reserva_regular
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def unidad_con_dos_consultorios(conn):
    edificios = obtener_repositorio(conn, "Edificio")
    unidades = obtener_repositorio(conn, "Unidad")
    consultorios = obtener_repositorio(conn, "Consultorio")

    id_edificio = edificios.crear(Nombre="Ramos 1")
    id_unidad = unidades.crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_c1 = consultorios.crear(IdUnidad=id_unidad, NumeroConsultorio=1, Ventana=1)
    id_c2 = consultorios.crear(IdUnidad=id_unidad, NumeroConsultorio=2, Ventana=0)
    return id_unidad, id_c1, id_c2


@pytest.fixture
def profesional(conn):
    return obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")


def test_ambos_consultorios_libres_da_verde(conn, unidad_con_dos_consultorios):
    id_unidad, _, _ = unidad_con_dos_consultorios
    grilla = calcular_grilla(conn, 2026, 8)
    assert grilla[(id_unidad, "Lunes", 15)] == "verde"


def test_un_consultorio_ocupado_con_ventana_libre_da_amarillo(conn, unidad_con_dos_consultorios, profesional):
    id_unidad, id_c1, id_c2 = unidad_con_dos_consultorios
    # ocupamos el consultorio SIN ventana (c2) -> queda libre el que tiene ventana (c1) -> amarillo
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=id_c2, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    grilla = calcular_grilla(conn, 2026, 8)
    assert grilla[(id_unidad, "Lunes", 15)] == "amarillo"


def test_un_consultorio_ocupado_con_ventana_ocupada_da_naranja(conn, unidad_con_dos_consultorios, profesional):
    id_unidad, id_c1, id_c2 = unidad_con_dos_consultorios
    # ocupamos el consultorio CON ventana (c1) -> queda libre el que no tiene ventana (c2) -> naranja
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=id_c1, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    grilla = calcular_grilla(conn, 2026, 8)
    assert grilla[(id_unidad, "Lunes", 15)] == "naranja"


def test_los_dos_consultorios_ocupados_da_rojo(conn, unidad_con_dos_consultorios, profesional):
    id_unidad, id_c1, id_c2 = unidad_con_dos_consultorios
    for id_consultorio in (id_c1, id_c2):
        crear_reserva_regular(
            conn, id_profesional=profesional, id_consultorio=id_consultorio, dia_semana="Lunes",
            hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
        )
    grilla = calcular_grilla(conn, 2026, 8)
    assert grilla[(id_unidad, "Lunes", 15)] == "rojo"


def test_fuera_del_horario_reservado_sigue_libre(conn, unidad_con_dos_consultorios, profesional):
    id_unidad, id_c1, id_c2 = unidad_con_dos_consultorios
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=id_c1, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    grilla = calcular_grilla(conn, 2026, 8)
    assert grilla[(id_unidad, "Lunes", 10)] == "verde"


def test_reserva_confirmada_a_futuro_marca_ocupado(conn, unidad_con_dos_consultorios, profesional):
    """Una reserva regular que arranca en un mes posterior al activo ya
    marca el slot como ocupado (está comprometido, sección 4.2)."""
    id_unidad, id_c1, id_c2 = unidad_con_dos_consultorios
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=id_c1, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-10-01",  # empieza en octubre
    )
    grilla = calcular_grilla(conn, 2026, 8)  # mes activo: agosto
    # c1 (con ventana) ya está comprometido a futuro -> ocupado ya desde ahora;
    # queda libre solo c2, que no tiene ventana -> naranja
    assert grilla[(id_unidad, "Lunes", 15)] == "naranja"


def test_reserva_que_termina_el_mes_que_viene_ya_figura_disponible(conn, unidad_con_dos_consultorios, profesional):
    """Una reserva cuya VigenciaFin cae en el mes siguiente al activo se
    considera 'a liberarse pronto' y el slot se muestra disponible."""
    id_unidad, id_c1, id_c2 = unidad_con_dos_consultorios
    # c1 (con ventana) termina en septiembre -> se considera disponible ya en agosto
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=id_c1, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01", vigencia_fin="2026-09-15",
    )
    grilla = calcular_grilla(conn, 2026, 8)  # mes activo: agosto; termina en septiembre (mes siguiente)
    assert grilla[(id_unidad, "Lunes", 15)] == "verde"


# --------------------------------------------------------------- dias_grilla (3.28)

def test_dias_grilla_usa_el_default_sin_configurar(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, DiasGrilla=None)
    assert dias_grilla(conn) == DIAS_GRILLA_DEFAULT


def test_dias_grilla_lee_la_configuracion(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, DiasGrilla=json.dumps(["Lunes", "Miércoles"]))
    assert dias_grilla(conn) == ["Lunes", "Miércoles"]


def test_dias_grilla_ignora_json_invalido(conn):
    conn.execute("UPDATE Configuracion SET DiasGrilla = ? WHERE IdConfiguracion = 1", ("no es json",))
    conn.commit()
    assert dias_grilla(conn) == DIAS_GRILLA_DEFAULT


def test_dias_grilla_ignora_lista_vacia(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, DiasGrilla=json.dumps([]))
    assert dias_grilla(conn) == DIAS_GRILLA_DEFAULT


def test_calcular_grilla_respeta_dias_configurados(conn, unidad_con_dos_consultorios, profesional):
    """Con la grilla acotada a Lunes/Martes, una reserva en Miércoles no
    debería figurar en absoluto (día fuera de la grilla configurada)."""
    id_unidad, id_c1, _ = unidad_con_dos_consultorios
    obtener_repositorio(conn, "Configuracion").actualizar(1, DiasGrilla=json.dumps(["Lunes", "Martes"]))
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=id_c1, dia_semana="Miércoles",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    grilla = calcular_grilla(conn, 2026, 8)
    assert (id_unidad, "Miércoles", 15) not in grilla
    assert (id_unidad, "Lunes", 15) in grilla


def test_ocupacion_fecha_marca_reserva_regular_vigente_esa_fecha(conn, unidad_con_dos_consultorios, profesional):
    _, id_c1, _ = unidad_con_dos_consultorios
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=id_c1, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    ocupado = calcular_ocupacion_fecha(conn, "2026-08-03")  # lunes
    assert ocupado[(id_c1, 14)] is True
    assert (id_c1, 16) not in ocupado


def test_ocupacion_fecha_libera_por_ausencia_puntual(conn, unidad_con_dos_consultorios, profesional):
    """A diferencia de la grilla mensual, la ocupación por fecha puntual sí
    tiene en cuenta las ausencias de ese día concreto."""
    _, id_c1, _ = unidad_con_dos_consultorios
    crear_reserva_regular(
        conn, id_profesional=profesional, id_consultorio=id_c1, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    crear_ausencia(conn, id_profesional=profesional, fecha_desde="2026-08-03", fecha_hasta="2026-08-03")
    ocupado = calcular_ocupacion_fecha(conn, "2026-08-03")
    assert (id_c1, 14) not in ocupado

    # otro lunes cualquiera, sin ausencia, sigue ocupado
    ocupado_otro_lunes = calcular_ocupacion_fecha(conn, "2026-08-10")
    assert ocupado_otro_lunes[(id_c1, 14)] is True


def test_ocupacion_fecha_no_bloquea_por_reserva_aislada_confirmada(conn, unidad_con_dos_consultorios):
    """Una aislada es un compromiso puntual reubicable, no ocupación real:
    no debe bloquear la búsqueda de horarios regulares (a diferencia de
    una reserva regular vigente o una versión anterior de esta función)."""
    _, id_c1, _ = unidad_con_dos_consultorios
    id_prof_aislada = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Puntual")
    crear_reserva_aislada(
        conn, id_profesional=id_prof_aislada, id_consultorio=id_c1, fecha="2026-08-03",
        hora_inicio=10, hora_fin=11,
    )
    ocupado = calcular_ocupacion_fecha(conn, "2026-08-03")
    assert (id_c1, 10) not in ocupado


def test_aisladas_confirmadas_fecha(conn, unidad_con_dos_consultorios):
    _, id_c1, _ = unidad_con_dos_consultorios
    id_prof_aislada = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Puntual")
    crear_reserva_aislada(
        conn, id_profesional=id_prof_aislada, id_consultorio=id_c1, fecha="2026-08-03",
        hora_inicio=10, hora_fin=11,
    )
    aisladas = aisladas_confirmadas_fecha(conn, "2026-08-03")
    assert len(aisladas) == 1
    assert aisladas[0]["IdConsultorio"] == id_c1
    assert aisladas_confirmadas_fecha(conn, "2026-08-10") == []
