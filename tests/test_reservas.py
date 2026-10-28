from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.dias import fecha_a_dia_semana
from app.negocio.liquidaciones import emitir_liquidacion
from app.negocio.reservas import (
    ConflictoBloqueanteError,
    cancelar_reserva_aislada,
    eliminar_reserva_aislada,
    crear_reserva_aislada,
    crear_reserva_regular,
    eliminar_reserva_regular,
    finalizar_reserva_regular,
    modificar_reserva_aislada,
    modificar_reserva_regular,
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


def test_crear_reserva_regular_media_hora_es_valida(conn, consultorio, profesional_factory):
    """Sección 3.28 (FraccionGrilla, default 30 min): 14.5 = 14:30, cae
    justo en la fracción configurada."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, advertencias = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14.5, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    assert id_reserva is not None
    assert advertencias == []


def test_crear_reserva_regular_fuera_de_fraccion_falla(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    with pytest.raises(ValueError):
        crear_reserva_regular(
            conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=14.25, hora_fin=16, vigencia_inicio="2026-01-01",
        )


def test_crear_reserva_regular_respeta_fraccion_configurada(conn, consultorio, profesional_factory):
    """Con la fracción configurada en 15 min, un cuarto de hora pasa a
    ser válido."""
    obtener_repositorio(conn, "Configuracion").actualizar(1, FraccionGrilla=15)
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14.25, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    assert id_reserva is not None


# ----------------------------------------------- DC-06 §3: período cerrado

def test_crear_reserva_regular_en_periodo_cerrado_bloquea(conn, consultorio, profesional_factory):
    """DC-06 §3: a diferencia de una aislada (ajusta sola el saldo), una
    regular con vigencia en un período que ya tiene una liquidación
    POSTERIOR emitida tocaría la base de cálculo de esa liquidación ya
    cerrada — se bloquea sin excepción, dirigiendo a Cargos especiales."""
    id_prof = profesional_factory("Lo Veci")
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")
    with pytest.raises(ValueError, match="Cargo especial"):
        crear_reserva_regular(
            conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01",
        )


def test_crear_reserva_regular_en_periodo_cerrado_no_se_puede_forzar(conn, consultorio, profesional_factory):
    """A diferencia de los conflictos de superposición, `forzar=True` no
    pisa este bloqueo — no es una advertencia que se pueda confirmar."""
    id_prof = profesional_factory("Lo Veci")
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")
    with pytest.raises(ValueError):
        crear_reserva_regular(
            conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01", forzar=True,
        )


def test_crear_reserva_regular_en_el_mismo_periodo_emitido_no_bloquea(conn, consultorio, profesional_factory):
    """El criterio es `Periodo > periodo`, no `>=`: el período que
    efectivamente tiene la liquidación más nueva todavía está "abierto"
    (nada posterior lo usó como base), mismo criterio exacto de
    `liquidaciones.emitir_liquidacion`."""
    id_prof = profesional_factory("Lo Veci")
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-09-15",
    )
    assert id_reserva is not None


def test_crear_reserva_regular_vigencia_fin_en_periodo_cerrado_bloquea(conn, consultorio, profesional_factory):
    """El mismo chequeo se aplica a `vigencia_fin` cuando se la da de alta
    de entrada con una fecha de cierre ya en un período cerrado (una
    "excepción" puntual, no el alta abierta de siempre)."""
    id_prof = profesional_factory("Lo Veci")
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")
    with pytest.raises(ValueError, match="Cargo especial"):
        crear_reserva_regular(
            conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01", vigencia_fin="2026-08-31",
        )


def test_crear_reserva_regular_consolida_el_bloqueo_del_e_en_su_r(conn, consultorio, profesional_factory):
    """El período cerrado se evalúa sobre el profesional LIQUIDABLE: un E
    consolidado en un R bloquea si el R tiene una liquidación posterior
    emitida, aunque el E en sí nunca tenga liquidaciones propias."""
    id_r = profesional_factory("Cabeza de equipo", categoria="R")
    id_e = profesional_factory("Del equipo", categoria="E", cabeza_equipo=id_r)
    emitir_liquidacion(conn, id_profesional=id_r, periodo="2026-09", fecha_emision="2026-09-01")
    with pytest.raises(ValueError, match="Cargo especial"):
        crear_reserva_regular(
            conn, id_profesional=id_e, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01",
        )


def test_crear_reserva_regular_categoria_b_nunca_bloquea(conn, consultorio, profesional_factory):
    """Un B no tiene profesional liquidable (`id_profesional_liquidable`
    da `None`): no hay ninguna liquidación que una vigencia vieja pudiera
    desalinear, así que nunca bloquea sin importar la fecha."""
    id_b = profesional_factory("Sin liquidación", categoria="B")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_b, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2020-01-01",
    )
    assert id_reserva is not None


# -------------------------------------------- validación de categoría (regular)

def test_crear_reserva_regular_rechaza_categoria_a(conn, consultorio, profesional_factory):
    """Defensa en profundidad (los combos de la GUI ya ni siquiera
    ofrecen A/X/C para Reservas regulares): el guardarraíl de categoría
    vive también en `crear_reserva_regular`, con el código R sugerido en
    el mensaje."""
    id_prof = profesional_factory("Paz", categoria="A")
    with pytest.raises(ValueError, match="código sugerido: R1"):
        crear_reserva_regular(
            conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
        )


def test_crear_reserva_regular_rechaza_categoria_x(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Paz", categoria="X")
    with pytest.raises(ValueError, match="no admite horarios regulares"):
        crear_reserva_regular(
            conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
        )


def test_crear_reserva_regular_rechaza_categoria_c(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Paz", categoria="C")
    with pytest.raises(ValueError, match="no admite horarios regulares"):
        crear_reserva_regular(
            conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
        )


def test_crear_reserva_regular_rechaza_e_sin_cabeza_de_equipo(conn, consultorio, profesional_factory):
    id_e = profesional_factory("Huérfano", categoria="E")
    with pytest.raises(ValueError, match="Cabeza de equipo"):
        crear_reserva_regular(
            conn, id_profesional=id_e, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
        )


def test_crear_reserva_regular_rechaza_e_con_cabeza_que_no_es_r(conn, consultorio, profesional_factory):
    id_b = profesional_factory("Cabeza inválida", categoria="B")
    id_e = profesional_factory("Huérfano", categoria="E", cabeza_equipo=id_b)
    with pytest.raises(ValueError, match="Cabeza de equipo"):
        crear_reserva_regular(
            conn, id_profesional=id_e, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
        )


def test_crear_reserva_regular_acepta_e_con_cabeza_r_valida(conn, consultorio, profesional_factory):
    id_r = profesional_factory("Cabeza de equipo", categoria="R")
    id_e = profesional_factory("Del equipo", categoria="E", cabeza_equipo=id_r)
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_e, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    assert id_reserva is not None


def test_finalizar_reserva_regular_en_periodo_cerrado_bloquea(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")
    with pytest.raises(ValueError, match="Cargo especial"):
        finalizar_reserva_regular(conn, id_reserva, "2026-08-31")


def test_finalizar_reserva_regular_sin_periodo_cerrado_funciona(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    finalizar_reserva_regular(conn, id_reserva, "2026-09-30")
    reserva = obtener_repositorio(conn, "ReservaRegular").obtener(id_reserva)
    assert reserva["VigenciaFin"] == "2026-09-30"


def test_eliminar_reserva_regular_ya_finalizada_en_periodo_cerrado_sigue_bloqueada(
    conn, consultorio, profesional_factory,
):
    """Una reserva puramente histórica (ya finalizada ANTES del borde del
    último período cerrado) sigue sin poder borrarse: no hay ningún
    motivo de negocio real detrás (no hay nada "activo" para reemplazar),
    así que acá sigue el guardarraíl estricto de siempre."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01", vigencia_fin="2026-08-15",
    )
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")
    with pytest.raises(ValueError, match="Cargo especial"):
        eliminar_reserva_regular(conn, id_reserva)
    assert obtener_repositorio(conn, "ReservaRegular").obtener(id_reserva) is not None


def test_eliminar_reserva_regular_activa_en_periodo_cerrado_se_permite(conn, consultorio, profesional_factory):
    """Pedido explícito de la clienta (caso real: reemplazar una reserva
    vieja por otra con más horas en otro consultorio desde el mes en
    curso): si la reserva sigue ACTIVA (sin Vigencia hasta, o con una
    posterior al borde del último período cerrado), se permite borrarla
    igual aunque su Vigencia desde caiga en un período ya cerrado —
    aceptando a sabiendas que se pierde el rastro de que existió durante
    ese período."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01",
    )
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")
    eliminar_reserva_regular(conn, id_reserva)
    assert obtener_repositorio(conn, "ReservaRegular").obtener(id_reserva) is None


def test_eliminar_reserva_regular_sin_periodo_cerrado_borra_la_fila(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    eliminar_reserva_regular(conn, id_reserva)
    assert obtener_repositorio(conn, "ReservaRegular").obtener(id_reserva) is None


def test_eliminar_reserva_regular_inexistente_falla(conn):
    with pytest.raises(ValueError, match="No existe"):
        eliminar_reserva_regular(conn, 99999)


def test_modificar_reserva_regular_edita_la_fila_sin_finalizarla(conn, consultorio, profesional_factory):
    """Punto #9.1.4 (SistemaDF v0.11.2026.10): "Modificar reserva" edita la
    fila existente en vez de finalizarla y precargar el formulario para
    dar de alta una nueva — "la reserva sigue corriendo con esa
    modificación" (sin VigenciaFin)."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    advertencias = modificar_reserva_regular(
        conn, id_reserva, hora_inicio=15, hora_fin=17, vigencia_inicio="2026-01-01", vigencia_fin=None,
    )
    assert advertencias == []
    reserva = obtener_repositorio(conn, "ReservaRegular").obtener(id_reserva)
    assert reserva["HoraInicio"] == 15
    assert reserva["HoraFin"] == 17
    assert reserva["VigenciaFin"] is None


def test_modificar_reserva_regular_puede_terminarla_poniendo_vigencia_fin(conn, consultorio, profesional_factory):
    """"Si quiero la termino desde el cuadro de diálogo" — alcanza con
    pasar una Vigencia hasta real, sin necesitar ningún camino aparte."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    modificar_reserva_regular(
        conn, id_reserva, hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01", vigencia_fin="2026-09-30",
    )
    reserva = obtener_repositorio(conn, "ReservaRegular").obtener(id_reserva)
    assert reserva["VigenciaFin"] == "2026-09-30"


def test_modificar_reserva_regular_en_periodo_cerrado_bloquea(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01",
    )
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")
    with pytest.raises(ValueError, match="Cargo especial"):
        modificar_reserva_regular(
            conn, id_reserva, hora_inicio=15, hora_fin=17, vigencia_inicio="2026-08-01", vigencia_fin=None,
        )


def test_modificar_reserva_regular_finaliza_en_el_borde_del_periodo_cerrado_se_permite(
    conn, consultorio, profesional_factory,
):
    """Pedido explícito de la clienta (caso real: profesional con una
    reserva vieja que necesita reemplazarse por otra con más horas en
    otro consultorio desde el mes en curso): "finalizarla" — mismo
    Horario y Vigencia desde, solo se le pone una Vigencia hasta —
    tiene que permitirse aunque la Vigencia desde de la fila sea de un
    período ya cerrado, siempre que la Vigencia hasta nueva no se meta
    DENTRO de ese período (acá, justo en su borde: el último día de
    agosto, el último período cerrado por la liquidación de
    septiembre)."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01",
    )
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")
    modificar_reserva_regular(
        conn, id_reserva, hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01", vigencia_fin="2026-08-31",
    )
    reserva = obtener_repositorio(conn, "ReservaRegular").obtener(id_reserva)
    assert reserva["VigenciaFin"] == "2026-08-31"


def test_modificar_reserva_regular_finaliza_dentro_del_periodo_cerrado_sigue_bloqueada(
    conn, consultorio, profesional_factory,
):
    """A diferencia del caso anterior, una Vigencia hasta que cae a
    MITAD de un período ya cerrado sí cambiaría lo que esa liquidación
    ya tuvo en cuenta (le quitaría presencia que ya estaba contada) —
    sigue bloqueado."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01",
    )
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")
    with pytest.raises(ValueError, match="período ya cerrado"):
        modificar_reserva_regular(
            conn, id_reserva, hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01", vigencia_fin="2026-08-15",
        )
    reserva = obtener_repositorio(conn, "ReservaRegular").obtener(id_reserva)
    assert reserva["VigenciaFin"] is None


def test_modificar_reserva_regular_cambia_horario_y_finaliza_en_periodo_cerrado_sigue_bloqueada(
    conn, consultorio, profesional_factory,
):
    """La excepción es SOLO para "finalizar" sin tocar nada más — si
    además se cambia el horario, vuelve a aplicar el guardarraíl
    estricto de siempre (la Vigencia desde de la fila sigue cayendo en
    un período cerrado)."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01",
    )
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")
    with pytest.raises(ValueError, match="Cargo especial"):
        modificar_reserva_regular(
            conn, id_reserva, hora_inicio=15, hora_fin=17, vigencia_inicio="2026-08-01", vigencia_fin="2026-08-31",
        )


def test_modificar_reserva_regular_contra_otro_profesional_bloquea(conn, consultorio, profesional_factory):
    """El horario nuevo puede generar un conflicto que la versión vieja
    no tenía — se vuelve a chequear, excluyendo a la propia fila."""
    id_prof_a = profesional_factory("Lo Veci")
    id_prof_b = profesional_factory("Gomez")
    id_reserva, _ = crear_reserva_regular(
        conn, id_profesional=id_prof_a, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    crear_reserva_regular(
        conn, id_profesional=id_prof_b, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=18, hora_fin=20, vigencia_inicio="2026-01-01",
    )
    with pytest.raises(ConflictoBloqueanteError):
        modificar_reserva_regular(
            conn, id_reserva, hora_inicio=19, hora_fin=21, vigencia_inicio="2026-01-01", vigencia_fin=None,
        )


def test_modificar_reserva_regular_inexistente_falla(conn):
    with pytest.raises(ValueError, match="No existe"):
        modificar_reserva_regular(
            conn, 99999, hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01", vigencia_fin=None,
        )


def test_crear_reserva_aislada_fuera_de_fraccion_falla(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    with pytest.raises(ValueError):
        crear_reserva_aislada(
            conn, id_profesional=id_prof, id_consultorio=consultorio, fecha="2026-08-10",
            hora_inicio=14, hora_fin=16.1,
        )


def test_crear_reserva_aislada_que_cruza_medianoche_falla(conn, consultorio, profesional_factory):
    """#45: "Hasta" menor o igual que "Desde" se bloquea con un mensaje
    claro — sin esta validación, se guardaba tal cual (los dos horarios
    son spines independientes en el formulario) y el monto quedaba
    calculado en negativo en silencio."""
    id_prof = profesional_factory("Lo Veci")
    with pytest.raises(ValueError, match="no puede cruzar medianoche"):
        crear_reserva_aislada(
            conn, id_profesional=id_prof, id_consultorio=consultorio, fecha="2026-08-10",
            hora_inicio=23, hora_fin=1,
        )
    assert obtener_repositorio(conn, "ReservaAislada").listar() == []


def test_crear_reserva_aislada_hora_fin_igual_a_hora_inicio_falla(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    with pytest.raises(ValueError, match="no puede cruzar medianoche"):
        crear_reserva_aislada(
            conn, id_profesional=id_prof, id_consultorio=consultorio, fecha="2026-08-10",
            hora_inicio=14, hora_fin=14,
        )


# ------------------------------------------------------------ reserva extraordinaria

def test_crear_reserva_extraordinaria_se_guarda_con_monto_manual(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Paz", categoria="A")
    id_reserva, advertencias = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio, fecha="2026-08-10",
        hora_inicio=14, hora_fin=16, es_extraordinaria=True,
        item_extraordinario="Uso del consultorio para un taller puntual", monto_extraordinario=12000,
    )
    assert advertencias == []
    reserva = obtener_repositorio(conn, "ReservaAislada").obtener(id_reserva)
    assert reserva["EsExtraordinaria"] == 1
    assert reserva["ItemExtraordinario"] == "Uso del consultorio para un taller puntual"
    assert reserva["MontoExtraordinario"] == 12000
    assert reserva["AplicaRecargo"] == 0


def test_crear_reserva_extraordinaria_tambien_admite_categoria_r(conn, consultorio, profesional_factory):
    """Pedido de la clienta, segunda vuelta: los R también pueden tener
    reservas extraordinarias (ya no es exclusivo de A)."""
    id_prof_r = profesional_factory("Lo Veci", categoria="R")
    id_reserva, advertencias = crear_reserva_aislada(
        conn, id_profesional=id_prof_r, id_consultorio=consultorio, fecha="2026-08-10",
        hora_inicio=14, hora_fin=16, es_extraordinaria=True,
        item_extraordinario="Taller puntual", monto_extraordinario=5000,
    )
    assert advertencias == []
    reserva = obtener_repositorio(conn, "ReservaAislada").obtener(id_reserva)
    assert reserva["EsExtraordinaria"] == 1
    assert reserva["MontoExtraordinario"] == 5000


def test_crear_reserva_extraordinaria_admite_categoria_b_y_e(conn, consultorio, profesional_factory):
    """Pedido de la clienta, ampliado de A/R a las cuatro categorías
    imputables: B participa solo para marcar ocupación (nunca afecta
    liquidación), E puede imputar igual que R."""
    for fecha, categoria in (("2026-08-10", "B"), ("2026-08-11", "E")):
        id_prof = profesional_factory(f"Paz{categoria}", categoria=categoria)
        _id, advertencias = crear_reserva_aislada(
            conn, id_profesional=id_prof, id_consultorio=consultorio, fecha=fecha,
            hora_inicio=14, hora_fin=16, es_extraordinaria=True,
            item_extraordinario="Taller puntual", monto_extraordinario=5000,
        )
        assert advertencias == []
        reserva = obtener_repositorio(conn, "ReservaAislada").obtener(_id)
        assert reserva["EsExtraordinaria"] == 1


def test_crear_reserva_extraordinaria_rechaza_categoria_distinta_de_a_b_r_e(conn, consultorio, profesional_factory):
    id_prof_x = profesional_factory("Paz", categoria="X")
    with pytest.raises(ValueError, match="categoría A, B, R o E"):
        crear_reserva_aislada(
            conn, id_profesional=id_prof_x, id_consultorio=consultorio, fecha="2026-08-10",
            hora_inicio=14, hora_fin=16, es_extraordinaria=True,
            item_extraordinario="Taller puntual", monto_extraordinario=5000,
        )


def test_crear_reserva_extraordinaria_sin_item_falla(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Paz", categoria="A")
    with pytest.raises(ValueError, match="ítem a cargar"):
        crear_reserva_aislada(
            conn, id_profesional=id_prof, id_consultorio=consultorio, fecha="2026-08-10",
            hora_inicio=14, hora_fin=16, es_extraordinaria=True,
            item_extraordinario="   ", monto_extraordinario=5000,
        )


def test_crear_reserva_extraordinaria_sin_monto_falla(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Paz", categoria="A")
    with pytest.raises(ValueError, match="monto a cobrar"):
        crear_reserva_aislada(
            conn, id_profesional=id_prof, id_consultorio=consultorio, fecha="2026-08-10",
            hora_inicio=14, hora_fin=16, es_extraordinaria=True,
            item_extraordinario="Taller puntual", monto_extraordinario=None,
        )


def test_reserva_extraordinaria_ocupa_la_grilla_igual_que_una_aislada(conn, consultorio, profesional_factory):
    """"Afecta la grilla visual en la ocupación como reserva aislada"
    (pedido explícito de la clienta): al ser una ReservaAislada más,
    genera el mismo conflicto bloqueante contra otro profesional que
    cualquier aislada común."""
    id_prof_a = profesional_factory("Paz", categoria="A")
    id_prof_b = profesional_factory("Gomez", categoria="A")
    crear_reserva_aislada(
        conn, id_profesional=id_prof_a, id_consultorio=consultorio, fecha="2026-08-10",
        hora_inicio=14, hora_fin=16, es_extraordinaria=True,
        item_extraordinario="Taller puntual", monto_extraordinario=5000,
    )
    with pytest.raises(ConflictoBloqueanteError):
        crear_reserva_aislada(
            conn, id_profesional=id_prof_b, id_consultorio=consultorio, fecha="2026-08-10",
            hora_inicio=15, hora_fin=17,
        )


def test_mensaje_de_conflicto_identifica_al_profesional_por_tratamiento_nombre_y_apellido(
    conn, consultorio, profesional_factory,
):
    """Punto #9.1.5 (SistemaDF v0.11.2026.10): el mensaje de conflicto
    identificaba al profesional solo por su número interno — pedido
    explícito de la clienta, pasa a mostrar "Tratamiento Nombre
    Apellido"."""
    profesionales = obtener_repositorio(conn, "Profesional")
    id_prof_a = profesionales.crear(CategoriaProfesional="R", Tratamiento="Lic.", NombrePila="Virginia", Apellido="Lo Veci")
    id_prof_b = profesional_factory("Gomez")
    crear_reserva_regular(
        conn, id_profesional=id_prof_a, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-01-01",
    )
    with pytest.raises(ConflictoBloqueanteError, match="Lic. Virginia Lo Veci"):
        crear_reserva_regular(
            conn, id_profesional=id_prof_b, id_consultorio=consultorio, dia_semana="Lunes",
            hora_inicio=15, hora_fin=17, vigencia_inicio="2026-01-01",
        )


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


# -------------------------------------------- validación de categoría (aislada)

def test_crear_reserva_aislada_rechaza_categoria_x(conn, consultorio, profesional_factory):
    """Defensa en profundidad (el combo de Reservas aisladas ya no
    ofrece X/C): el guardarraíl de categoría vive también en
    `crear_reserva_aislada`, solo para la aislada COMÚN — la
    extraordinaria ya tiene su propia validación aparte."""
    id_prof = profesional_factory("Paz", categoria="X")
    with pytest.raises(ValueError, match="código sugerido: A1"):
        crear_reserva_aislada(
            conn, id_profesional=id_prof, id_consultorio=consultorio,
            fecha="2026-08-10", hora_inicio=11, hora_fin=12,
        )


def test_crear_reserva_aislada_rechaza_categoria_c(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Paz", categoria="C")
    with pytest.raises(ValueError, match="no admite horarios aislados"):
        crear_reserva_aislada(
            conn, id_profesional=id_prof, id_consultorio=consultorio,
            fecha="2026-08-10", hora_inicio=11, hora_fin=12,
        )


def test_crear_reserva_aislada_rechaza_e_sin_cabeza_de_equipo(conn, consultorio, profesional_factory):
    id_e = profesional_factory("Huérfano", categoria="E")
    with pytest.raises(ValueError, match="Cabeza de equipo"):
        crear_reserva_aislada(
            conn, id_profesional=id_e, id_consultorio=consultorio,
            fecha="2026-08-10", hora_inicio=11, hora_fin=12,
        )


def test_crear_reserva_aislada_acepta_e_con_cabeza_r_valida(conn, consultorio, profesional_factory):
    id_r = profesional_factory("Cabeza de equipo", categoria="R")
    id_e = profesional_factory("Del equipo", categoria="E", cabeza_equipo=id_r)
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_e, id_consultorio=consultorio,
        fecha="2026-08-10", hora_inicio=11, hora_fin=12,
    )
    assert id_reserva is not None


def test_crear_reserva_extraordinaria_no_pasa_por_la_validacion_de_la_comun(conn, consultorio, profesional_factory):
    """Una extraordinaria de categoría X (fuera de A/B/R/E) sigue
    rechazada, pero por SU PROPIA validación — no por la de la aislada
    común (`_validar_categoria_reserva`), que se saltea por completo
    cuando `es_extraordinaria=True`."""
    id_prof = profesional_factory("Paz", categoria="X")
    with pytest.raises(ValueError, match="categoría A, B, R o E"):
        crear_reserva_aislada(
            conn, id_profesional=id_prof, id_consultorio=consultorio, fecha="2026-08-10",
            hora_inicio=14, hora_fin=16, es_extraordinaria=True,
            item_extraordinario="Taller puntual", monto_extraordinario=5000,
        )


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


def test_cancelar_reserva_aislada_mismo_dia_en_bloque_rigido_no_bloquea(conn, consultorio, profesional_factory):
    """DC-04 §4.3, confirmado por el usuario: las aisladas no tienen
    ninguna restricción de bloques rígidos, ni siquiera al cancelar el
    mismo día — solo el aviso normal de "mismo día", nunca bloqueo."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=9, hora_fin=11,
    )
    requiere_aviso = cancelar_reserva_aislada(conn, id_reserva, fecha_actual="2026-08-20")
    assert requiere_aviso is True
    assert obtener_repositorio(conn, "ReservaAislada").obtener(id_reserva)["Estado"] == "Cancelada"


# ------------------------------------------------------------ eliminación (Reservas aisladas)

def test_eliminar_reserva_aislada_otro_dia_no_requiere_aviso_y_borra_la_fila(conn, consultorio, profesional_factory):
    """`eliminar_reserva_aislada` (botón "Eliminar reserva" de Reservas
    aisladas, antes "Cancelar reserva") borra la fila por completo en
    vez de marcarla `Estado="Cancelada"` — pedido explícito de la
    clienta. `cancelar_reserva_aislada` sigue existiendo tal cual, sin
    tocar (todavía la usa Reserva extraordinaria)."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12,
    )
    requiere_aviso = eliminar_reserva_aislada(conn, id_reserva, fecha_actual="2026-08-10")
    assert requiere_aviso is False
    assert obtener_repositorio(conn, "ReservaAislada").obtener(id_reserva) is None


def test_eliminar_reserva_aislada_mismo_dia_requiere_aviso(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12,
    )
    requiere_aviso = eliminar_reserva_aislada(conn, id_reserva, fecha_actual="2026-08-20")
    assert requiere_aviso is True
    assert obtener_repositorio(conn, "ReservaAislada").obtener(id_reserva) is None


def test_eliminar_reserva_aislada_inexistente_lanza_error(conn):
    with pytest.raises(ValueError):
        eliminar_reserva_aislada(conn, 99999)


def test_crear_reserva_aislada_guarda_el_periodo_imputado(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12, periodo_imputado="2026-09",
    )
    assert obtener_repositorio(conn, "ReservaAislada").obtener(id_reserva)["PeriodoImputado"] == "2026-09"


def test_crear_reserva_aislada_sin_periodo_imputado_queda_en_blanco(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12,
    )
    assert obtener_repositorio(conn, "ReservaAislada").obtener(id_reserva)["PeriodoImputado"] is None


def test_modificar_reserva_aislada_edita_horario_y_recargo_sin_cancelarla(conn, consultorio, profesional_factory):
    """#9.1.4 (homólogo de Reservas regulares): edita la fila existente,
    sigue Confirmada."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12, aplica_recargo=False,
    )
    advertencias = modificar_reserva_aislada(conn, id_reserva, hora_inicio=14, hora_fin=16, aplica_recargo=True)
    assert advertencias == []
    fila = obtener_repositorio(conn, "ReservaAislada").obtener(id_reserva)
    assert fila["HoraInicio"] == 14
    assert fila["HoraFin"] == 16
    assert bool(fila["AplicaRecargo"]) is True
    assert fila["Estado"] == "Confirmada"


def test_modificar_reserva_aislada_hora_fin_menor_a_inicio_falla(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12,
    )
    with pytest.raises(ValueError):
        modificar_reserva_aislada(conn, id_reserva, hora_inicio=14, hora_fin=12)


def test_modificar_reserva_aislada_contra_otro_profesional_bloquea(conn, consultorio, profesional_factory):
    id_a = profesional_factory("Lo Veci")
    id_b = profesional_factory("Gómez", categoria="A")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_a, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12,
    )
    crear_reserva_aislada(
        conn, id_profesional=id_b, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=15, hora_fin=17,
    )
    with pytest.raises(ConflictoBloqueanteError):
        modificar_reserva_aislada(conn, id_reserva, hora_inicio=16, hora_fin=18)


def test_modificar_reserva_aislada_no_choca_contra_si_misma(conn, consultorio, profesional_factory):
    """`excluir_id` evita que la propia fila se reporte como conflicto
    contra sí misma al mantener el mismo horario."""
    id_prof = profesional_factory("Lo Veci")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12,
    )
    advertencias = modificar_reserva_aislada(conn, id_reserva, hora_inicio=11, hora_fin=12, aplica_recargo=False)
    assert advertencias == []


def test_modificar_reserva_aislada_extraordinaria_edita_item_y_monto(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci", categoria="A")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12,
        es_extraordinaria=True, item_extraordinario="Taller", monto_extraordinario=1000,
    )
    modificar_reserva_aislada(
        conn, id_reserva, hora_inicio=11, hora_fin=12,
        item_extraordinario="Taller corregido", monto_extraordinario=1500,
    )
    fila = obtener_repositorio(conn, "ReservaAislada").obtener(id_reserva)
    assert fila["ItemExtraordinario"] == "Taller corregido"
    assert fila["MontoExtraordinario"] == 1500


def test_modificar_reserva_aislada_extraordinaria_sin_item_falla(conn, consultorio, profesional_factory):
    id_prof = profesional_factory("Lo Veci", categoria="A")
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-20", hora_inicio=11, hora_fin=12,
        es_extraordinaria=True, item_extraordinario="Taller", monto_extraordinario=1000,
    )
    with pytest.raises(ValueError):
        modificar_reserva_aislada(conn, id_reserva, hora_inicio=11, hora_fin=12, item_extraordinario="")


def test_modificar_reserva_aislada_inexistente_falla(conn):
    with pytest.raises(ValueError):
        modificar_reserva_aislada(conn, 99999, hora_inicio=9, hora_fin=10)


def test_crear_reserva_aislada_en_bloque_rigido_no_advierte(conn, consultorio, profesional_factory):
    """DC-04 §2.2, confirmado por el usuario: crear una aislada dentro de
    un bloque rígido no genera ninguna advertencia (a diferencia de una
    reserva regular parcial en el mismo horario)."""
    id_prof = profesional_factory("Lo Veci")
    _id_reserva, advertencias = crear_reserva_aislada(
        conn, id_profesional=id_prof, id_consultorio=consultorio,
        fecha="2026-08-10", hora_inicio=9, hora_fin=10,  # parcial dentro del bloque 9-11
    )
    assert advertencias == []


# ---------------------------------------------- reserva regular sobre aisladas futuras (DC-04 §1.3)

def test_reserva_regular_sobre_aislada_futura_confirmada_solo_advierte(conn, consultorio, profesional_factory):
    id_aislado = profesional_factory("Aislado", categoria="A")
    assert fecha_a_dia_semana(date(2026, 8, 17)) == "Lunes"
    id_reserva_aislada, _ = crear_reserva_aislada(
        conn, id_profesional=id_aislado, id_consultorio=consultorio,
        fecha="2026-08-17", hora_inicio=14, hora_fin=16,
    )

    id_regular = profesional_factory("Regular nuevo")
    id_reserva, advertencias = crear_reserva_regular(
        conn, id_profesional=id_regular, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01",
    )
    assert id_reserva is not None  # no bloquea, DC-08 §3.4 prevalece sobre DC-04 §1.3
    assert len(advertencias) == 1
    assert str(id_reserva_aislada) in advertencias[0] or "reserva aislada" in advertencias[0]


def test_aislada_anterior_a_vigencia_de_la_regular_no_genera_aviso(conn, consultorio, profesional_factory):
    id_aislado = profesional_factory("Aislado", categoria="A")
    crear_reserva_aislada(
        conn, id_profesional=id_aislado, id_consultorio=consultorio,
        fecha="2026-07-06", hora_inicio=14, hora_fin=16,  # antes de la vigencia de la regular
    )

    id_regular = profesional_factory("Regular nuevo")
    id_reserva, advertencias = crear_reserva_regular(
        conn, id_profesional=id_regular, id_consultorio=consultorio, dia_semana="Lunes",
        hora_inicio=14, hora_fin=16, vigencia_inicio="2026-08-01",
    )
    assert id_reserva is not None
    assert advertencias == []
