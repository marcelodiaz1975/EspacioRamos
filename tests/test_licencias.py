from datetime import date, timedelta

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.licencias import cancelar_licencia, crear_licencia
from app.negocio.reservas import crear_reserva_aislada
from app.negocio.valores import obtener_porcentaje_descuento
from app.repositorio.registro import obtener_repositorio

VALOR_HORA = 1000
HORAS_SEMANA = 10  # 10 a 20hs los lunes


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
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=VALOR_HORA,
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=10 + HORAS_SEMANA, VigenciaInicio="2026-01-01",
    )
    return id_prof


def _valor_semanal_esperado(conn):
    descuento_pct = obtener_porcentaje_descuento(conn, HORAS_SEMANA)
    return HORAS_SEMANA * VALOR_HORA * (1 - descuento_pct / 100)


def _valor_bonificado_esperado(conn, fecha_desde, fecha_hasta, porcentaje):
    """Día por día del período: solo cuentan los lunes (único día reservado
    en el fixture), con el descuento por horas semanales ya aplicado."""
    descuento_pct = obtener_porcentaje_descuento(conn, HORAS_SEMANA)
    valor_dia = HORAS_SEMANA * VALOR_HORA * (1 - descuento_pct / 100) * (porcentaje / 100)
    dia = date.fromisoformat(fecha_desde)
    fin = date.fromisoformat(fecha_hasta)
    total = 0.0
    while dia <= fin:
        if dia.weekday() == 0:  # lunes
            total += valor_dia
        dia += timedelta(days=1)
    return total


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
    id_licencia, advertencias = crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-01",
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert licencia["FechaHasta"] == "2026-08-05"
    assert advertencias == []


def test_licencia_supera_duracion_maxima_no_bloquea_y_bonifica_solo_hasta_el_tope(conn, profesional_con_reserva):
    id_tipo = _id_tipo(conn, "Licencia por duelo")  # máximo 5 días, 100%
    id_licencia, advertencias = crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-01", fecha_hasta="2026-08-10",
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert len(advertencias) == 1
    assert "supera la duración máxima" in advertencias[0]
    assert licencia["FechaHasta"] == "2026-08-10"  # se guarda el período completo pedido
    # solo se bonifican los primeros 5 días (01 al 05/8): un solo lunes, el 3/8
    esperado = _valor_bonificado_esperado(conn, "2026-08-01", "2026-08-05", 100)
    assert licencia["ValorBonificado"] == pytest.approx(esperado)


def test_licencia_maternidad_bonifica_50_por_ciento(conn, profesional_con_reserva):
    id_tipo = _id_tipo(conn, "Licencia por maternidad")  # 50%, 90 días, no manual
    id_licencia, advertencias = crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-01",
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert advertencias == []
    assert licencia["PorcentajeBonificacionAplicado"] == 50
    valor_semanal = _valor_semanal_esperado(conn)
    assert licencia["ValorSemanalAlMomentoDelRegistro"] == pytest.approx(valor_semanal)
    esperado = _valor_bonificado_esperado(conn, "2026-08-01", licencia["FechaHasta"], 50)
    assert licencia["ValorBonificado"] == pytest.approx(esperado)


def test_licencia_medica_bonifica_100_por_ciento_un_dia_con_reserva(conn, profesional_con_reserva):
    id_tipo = _id_tipo(conn, "Licencia médica")  # 100%, sin límite, manual
    id_licencia, advertencias = crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-03", fecha_hasta="2026-08-03",  # lunes
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert advertencias == []
    descuento_pct = obtener_porcentaje_descuento(conn, HORAS_SEMANA)
    valor_dia = HORAS_SEMANA * VALOR_HORA * (1 - descuento_pct / 100)
    assert licencia["ValorBonificado"] == pytest.approx(valor_dia)


def test_licencia_no_bonifica_dia_sin_reserva(conn, profesional_con_reserva):
    id_tipo = _id_tipo(conn, "Licencia médica")
    id_licencia, _ = crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-04", fecha_hasta="2026-08-04",  # martes, sin reserva
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert licencia["ValorBonificado"] == pytest.approx(0.0)


def test_licencia_rechaza_profesional_sin_categoria_r_b_o_e(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Sin Derecho")
    id_tipo = _id_tipo(conn, "Licencia médica")
    with pytest.raises(ValueError, match="categoría R, B o E"):
        crear_licencia(
            conn, id_profesional=id_prof, id_tipo_licencia=id_tipo,
            fecha_desde="2026-08-03", fecha_hasta="2026-08-03",
        )


def test_licencia_rechaza_profesional_sin_reserva_regular_activa(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Sin Reserva")
    id_tipo = _id_tipo(conn, "Licencia médica")
    with pytest.raises(ValueError, match="categoría R, B o E"):
        crear_licencia(
            conn, id_profesional=id_prof, id_tipo_licencia=id_tipo,
            fecha_desde="2026-08-03", fecha_hasta="2026-08-03",
        )


def test_licencia_porcentaje_bonificacion_editable_caso_por_caso(conn, profesional_con_reserva):
    id_tipo = _id_tipo(conn, "Licencia por maternidad")  # 50% por defecto
    id_licencia, _ = crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-03", fecha_hasta="2026-08-03", porcentaje_bonificacion=75,
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert licencia["PorcentajeBonificacionAplicado"] == 75
    esperado = _valor_bonificado_esperado(conn, "2026-08-03", "2026-08-03", 75)
    assert licencia["ValorBonificado"] == pytest.approx(esperado)


def test_licencia_categoria_b_no_genera_descuento(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=VALOR_HORA,
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="B", Apellido="Bonificada")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=10 + HORAS_SEMANA, VigenciaInicio="2026-01-01",
    )
    id_tipo = _id_tipo(conn, "Licencia médica")
    id_licencia, _ = crear_licencia(
        conn, id_profesional=id_prof, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-03", fecha_hasta="2026-08-03",
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert licencia["ValorBonificado"] == 0.0


def _id_consultorio_de(conn, id_prof):
    return conn.execute(
        "SELECT IdConsultorio FROM ReservaRegular WHERE IdProfesional = ?", (id_prof,)
    ).fetchone()["IdConsultorio"]


def test_licencia_libera_consultorio_para_aislada_de_otro_profesional(conn, profesional_con_reserva):
    """DC-05 §2.1, confirmado por el usuario: una licencia libera el
    consultorio para asignar aisladas a otro profesional, igual que una
    Ausencia."""
    id_consultorio = _id_consultorio_de(conn, profesional_con_reserva)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Gomez")
    id_tipo = _id_tipo(conn, "Licencia médica")
    crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-03", fecha_hasta="2026-08-03",
    )

    id_reserva, advertencias = crear_reserva_aislada(
        conn, id_profesional=otro_profesional, id_consultorio=id_consultorio,
        fecha="2026-08-03", hora_inicio=10, hora_fin=11,
    )
    assert id_reserva is not None
    assert advertencias == []


def test_cancelar_licencia_sin_aisladas_se_elimina(conn, profesional_con_reserva):
    id_tipo = _id_tipo(conn, "Licencia médica")
    id_licencia, _ = crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-03", fecha_hasta="2026-08-03",
    )
    cancelar_licencia(conn, id_licencia)
    assert obtener_repositorio(conn, "Licencia").obtener(id_licencia) is None


def test_cancelar_licencia_bloqueada_por_aislada_ya_asignada(conn, profesional_con_reserva):
    id_consultorio = _id_consultorio_de(conn, profesional_con_reserva)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Gomez")
    id_tipo = _id_tipo(conn, "Licencia médica")
    id_licencia, _ = crear_licencia(
        conn, id_profesional=profesional_con_reserva, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-03", fecha_hasta="2026-08-03",
    )
    crear_reserva_aislada(
        conn, id_profesional=otro_profesional, id_consultorio=id_consultorio,
        fecha="2026-08-03", hora_inicio=10, hora_fin=11,
    )

    with pytest.raises(ValueError):
        cancelar_licencia(conn, id_licencia)
    assert obtener_repositorio(conn, "Licencia").obtener(id_licencia) is not None
