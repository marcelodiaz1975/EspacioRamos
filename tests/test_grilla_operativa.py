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
    claves_con_ausencia,
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


def _celda(conn, id_consultorio, modo="regular", periodo="2026-08", id_profesional_filtro=None):
    grilla = calcular_grilla_operativa(
        conn, [id_consultorio], ["Lunes"], 9, 10, periodo, modo=modo, id_profesional_filtro=id_profesional_filtro,
    )
    return grilla[(id_consultorio, "Lunes", 9)]


# --------------------------------------------------------------- modo regular

def test_regular_celda_libre(conn, consultorio):
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, BLANCO)
    assert celda.codigo is None
    assert celda.detalle == "Horario disponible."


def test_regular_activa_sin_circunstancias_es_blanco(conn, consultorio, virginia):
    """Blanco liso: reserva activa hoy, sin fecha de liberación cargada
    ni ninguna otra circunstancia — CONFIRMADO por la clienta que este
    caso (antes "verde completo") ahora tiene que ser blanco."""
    _regular(conn, virginia, consultorio)
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, BLANCO)
    assert celda.codigo == "R1"


def test_regular_activa_con_fecha_de_liberacion_es_verde(conn, consultorio, virginia):
    """Verde liso: hay fecha de liberación cargada (VigenciaFin), sin
    importar si cae este mismo mes o en uno posterior."""
    _regular(conn, virginia, consultorio, vigencia_fin="2026-08-20")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (VERDE, VERDE)
    assert celda.codigo == "R1"
    assert "Se libera el jueves 20/8." in celda.detalle


def test_regular_activa_con_liberacion_en_mes_posterior_tambien_es_verde(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio, vigencia_fin="2026-12-31")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (VERDE, VERDE)


def test_regular_entrante_sin_titular_actual_es_rojo_liso(conn, consultorio, eugenia):
    """Rojo liso: nadie lo ocupa ahora, pero ya hay una reserva cargada a futuro."""
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)
    assert celda.codigo is None
    assert "Horario reservado por Lic. Eugenia Viegas (R2) a partir del jueves 3/9." in celda.detalle


def test_regular_conflicto_con_profesional_distinto_entrante_es_rojo_liso(conn, consultorio, virginia, eugenia):
    """Rojo liso: hoy lo tiene Virginia (código visible, sigue siendo
    vigente), pero a futuro pasa a Eugenia."""
    _regular(conn, virginia, consultorio)
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)
    assert celda.codigo == "R1"
    assert celda.detalle == (
        "Horario reservado por Lic. Virginia Lo Veci (R1). "
        "Horario reservado por Lic. Eugenia Viegas (R2) a partir del jueves 3/9."
    )


def test_regular_entrante_mas_aislada_en_mes_actual_es_rojo_con_triangulo_amarillo(conn, consultorio, virginia, eugenia):
    _regular(conn, virginia, consultorio)
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (ROJO, AMARILLO)
    assert celda.codigo == "R1"
    assert "Hora aislada reservada por Lic. Eugenia Viegas (R2) para el lunes 17/8." in celda.detalle


def test_regular_entrante_mas_aislada_en_mes_posterior_no_dispara_el_triangulo(conn, consultorio, eugenia):
    """El triángulo de "rojo" solo mira aisladas DENTRO del mes en curso
    — una aislada de un mes posterior no lo dispara (sigue rojo liso)."""
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-10-03")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-09-14", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)


def test_regular_entrante_mas_aislada_pasada_no_dispara_el_triangulo(conn, consultorio, eugenia):
    """Fix confirmado por la clienta: una aislada de una fecha ya pasada
    (2026-08-03, antes del "hoy" ficticio 2026-08-10) no es una
    referencia útil aunque caiga dentro del mes en curso — se omite y la
    celda sigue rojo liso, sin el triángulo amarillo."""
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-03", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)
    assert "aislada" not in celda.detalle.lower()


def test_regular_con_hueco_por_vacacion_es_blanco_con_triangulo_verde(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio)
    obtener_repositorio(conn, "Vacacion").crear(IdProfesional=virginia, FechaDesde="2026-08-15", FechaHasta="2026-08-25")
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, VERDE)
    assert celda.codigo == "R1"
    assert "De vacaciones desde el sábado 15/8 hasta el martes 25/8." in celda.detalle


def test_regular_con_hueco_ya_tomado_es_blanco_con_triangulo_amarillo(conn, consultorio, virginia, eugenia):
    _regular(conn, virginia, consultorio)
    obtener_repositorio(conn, "Vacacion").crear(IdProfesional=virginia, FechaDesde="2026-08-15", FechaHasta="2026-08-25")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, AMARILLO)
    assert celda.codigo == "R1"
    assert "De vacaciones desde el sábado 15/8 hasta el martes 25/8." in celda.detalle
    assert "Hora aislada reservada por Lic. Eugenia Viegas (R2) para el lunes 17/8." in celda.detalle


def test_regular_hueco_con_aislada_pasada_no_dispara_el_triangulo(conn, consultorio, virginia, eugenia):
    _regular(conn, virginia, consultorio)
    obtener_repositorio(conn, "Vacacion").crear(IdProfesional=virginia, FechaDesde="2026-08-01", FechaHasta="2026-08-25")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-03", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (BLANCO, VERDE)
    assert "aislada" not in celda.detalle.lower()


def test_regular_ausencia_con_horario_puntual_no_afecta_otras_horas(conn, consultorio, virginia):
    """La ausencia solo tiene HoraInicio/HoraFin 9-10 — el mismo profesional
    también tiene una reserva regular a las 11 en otro consultorio, y esa
    NO tiene que verse afectada (bug real: antes de este fix, una ausencia
    con horario puntual se aplicaba a todas las horas reservadas del
    profesional ese día, no solo a la suya)."""
    _regular(conn, virginia, consultorio)
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=obtener_repositorio(conn, "Unidad").crear(
            IdEdificio=obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2"), Departamento="2B",
        ),
        NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=virginia, IdConsultorio=otro_consultorio, DiaSemana="Lunes",
        HoraInicio=11, HoraFin=12, VigenciaInicio="2026-01-01",
    )
    obtener_repositorio(conn, "Ausencia").crear(
        IdProfesional=virginia, FechaDesde="2026-08-17", FechaHasta="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    conn.commit()

    celda_con_ausencia = _celda(conn, consultorio)
    assert (celda_con_ausencia.color_aro, celda_con_ausencia.color_centro) == (BLANCO, VERDE)

    grilla_otro_horario = calcular_grilla_operativa(conn, [otro_consultorio], ["Lunes"], 11, 12, "2026-08")
    celda_otro_horario = grilla_otro_horario[(otro_consultorio, "Lunes", 11)]
    assert (celda_otro_horario.color_aro, celda_otro_horario.color_centro) == (BLANCO, BLANCO)


def test_regular_solo_aislada_en_mes_actual_es_amarillo_liso(conn, consultorio, eugenia):
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (AMARILLO, AMARILLO)
    assert celda.codigo is None  # regla del código: nunca por una aislada
    assert celda.detalle == "Hora aislada reservada por Lic. Eugenia Viegas (R2) para el lunes 17/8."


def test_regular_solo_aislada_en_mes_posterior_tambien_es_amarillo_liso(conn, consultorio, eugenia):
    """Amarillo liso admite explícitamente "mes en curso o posteriores"."""
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-09-14", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio)
    assert (celda.color_aro, celda.color_centro) == (AMARILLO, AMARILLO)


def test_regular_filtro_pinta_azul_cuando_es_el_titular_actual(conn, consultorio, virginia):
    _regular(conn, virginia, consultorio)
    celda = _celda(conn, consultorio, id_profesional_filtro=virginia)
    assert (celda.color_aro, celda.color_centro, celda.color_fuente) == (AZUL_OSCURO, AZUL_OSCURO, BLANCA)


def test_regular_filtro_no_pinta_azul_si_solo_es_entrante(conn, consultorio, virginia, eugenia):
    _regular(conn, virginia, consultorio)
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    celda = _celda(conn, consultorio, id_profesional_filtro=eugenia)
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)


def test_regular_filtro_no_pinta_azul_sobre_aislada_sin_codigo(conn, consultorio, eugenia):
    """Confirmado por la clienta: el resalte azul solo aplica donde se
    muestra el código — una celda "amarillo liso" (aislada sin reserva
    regular) no muestra código, así que no se resalta aunque el
    profesional filtrado sea el de la aislada."""
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio, id_profesional_filtro=eugenia)
    assert (celda.color_aro, celda.color_centro) == (AMARILLO, AMARILLO)


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


def test_aislada_con_hueco_y_aislada_pasada_no_cuenta(conn, consultorio, virginia, eugenia):
    """Mismo fix que en modo regular: una aislada de una fecha ya pasada
    no cuenta como "hueco ya tomado" — sigue mostrando el hueco libre."""
    _regular(conn, virginia, consultorio, vigencia_fin="2026-12-31")
    obtener_repositorio(conn, "Vacacion").crear(IdProfesional=virginia, FechaDesde="2026-08-01", FechaHasta="2026-08-25")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-03", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio, modo="aislada")
    assert (celda.color_aro, celda.color_centro) == (ROJO, VERDE)
    assert celda.codigo is None


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


# --------------------------------------------------------- ausente_en (F.Registro de ausencias)

def test_claves_con_ausencia_dia_completo(conn, consultorio, virginia):
    obtener_repositorio(conn, "Ausencia").crear(
        IdProfesional=virginia, FechaDesde="2026-08-17", FechaHasta="2026-08-17",
    )
    claves = claves_con_ausencia(conn, virginia, [consultorio], ["Lunes"], 9, 10, "2026-08-01", "2026-08-31")
    assert claves == {(consultorio, "Lunes", 9)}


def test_claves_con_ausencia_horario_puntual_acota_la_hora(conn, consultorio, virginia):
    obtener_repositorio(conn, "Ausencia").crear(
        IdProfesional=virginia, FechaDesde="2026-08-17", FechaHasta="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    claves = claves_con_ausencia(conn, virginia, [consultorio], ["Lunes"], 9, 11, "2026-08-01", "2026-08-31")
    assert claves == {(consultorio, "Lunes", 9)}  # la hora 10 queda fuera del horario puntual


def test_ausente_en_pinta_verde_con_letra_negra_sobre_celda_azul(conn, consultorio, virginia):
    """El horario propio del profesional filtrado se pinta de azul oscuro
    — si además tiene una ausencia registrada ahí, pasa a verde con letra
    negra en vez de azul (Registro de ausencias)."""
    _regular(conn, virginia, consultorio)
    ausente_en = {(consultorio, "Lunes", 9)}
    grilla = calcular_grilla_operativa(
        conn, [consultorio], ["Lunes"], 9, 10, "2026-08",
        modo="regular", id_profesional_filtro=virginia, ausente_en=ausente_en,
    )
    celda = grilla[(consultorio, "Lunes", 9)]
    assert (celda.color_aro, celda.color_centro, celda.color_fuente) == (VERDE, VERDE, NEGRA)
    assert celda.codigo == "R1"


def test_ausente_en_no_afecta_celdas_que_no_son_del_profesional_filtrado(conn, consultorio, virginia, eugenia):
    """`ausente_en` solo pisa el azul oscuro del profesional filtrado — una
    celda roja (conflicto con otro profesional) no se ve afectada aunque
    su clave esté en el conjunto."""
    _regular(conn, eugenia, consultorio, vigencia_inicio="2026-09-03")
    ausente_en = {(consultorio, "Lunes", 9)}
    grilla = calcular_grilla_operativa(
        conn, [consultorio], ["Lunes"], 9, 10, "2026-08",
        modo="regular", id_profesional_filtro=virginia, ausente_en=ausente_en,
    )
    celda = grilla[(consultorio, "Lunes", 9)]
    assert (celda.color_aro, celda.color_centro) == (ROJO, ROJO)


def test_aislada_dos_reservas_muestra_la_mas_proxima(conn, consultorio, virginia, eugenia):
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=eugenia, IdConsultorio=consultorio, Fecha="2026-08-24", HoraInicio=9, HoraFin=10,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=virginia, IdConsultorio=consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    celda = _celda(conn, consultorio, modo="aislada")
    assert celda.codigo == "R1"  # 17/8 está más cerca del 10/8 (hoy) que el 24/8
