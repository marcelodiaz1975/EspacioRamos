import json

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.grilla import DIAS_GRILLA_DEFAULT, calcular_grilla, dias_grilla
from app.negocio.reservas import crear_reserva_regular
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
