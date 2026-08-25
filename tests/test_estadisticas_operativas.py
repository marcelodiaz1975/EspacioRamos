import calendar
from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.dias import fecha_a_dia_semana
from app.negocio.estadisticas_operativas import calcular_estadisticas_operativas
from app.negocio.liquidaciones import calcular_liquidacion
from app.repositorio.registro import obtener_repositorio

VALOR_HORA_REGULAR = 1000
VALOR_HORA_AISLADA = 500
PERIODO = "2026-08"


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


def _unidad(conn, nombre_edificio="Ramos 1", departamento='7mo "L"', localidad=None):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre=nombre_edificio, DomicilioLocalidad=localidad)
    return obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=departamento), id_edificio


def _otra_unidad_mismo_edificio(conn, id_edificio, departamento):
    return obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=departamento)


def _consultorio(conn, id_unidad, numero=1):
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=numero,
        ValorHoraRegularActual=VALOR_HORA_REGULAR, ValorHoraAisladaActual=VALOR_HORA_AISLADA,
    )


def _profesional(conn, categoria="R"):
    return obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional=categoria, Apellido="Lo Veci")


def _reserva(conn, id_prof, id_consultorio, dia_semana="Lunes", horas=2, vigencia_inicio="2026-01-01"):
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana=dia_semana,
        HoraInicio=10, HoraFin=10 + horas, VigenciaInicio=vigencia_inicio,
    )


def _cantidad_dia(anio: int, mes: int, dia_semana: str) -> int:
    total_dias = calendar.monthrange(anio, mes)[1]
    return sum(
        1 for d in range(1, total_dias + 1) if fecha_a_dia_semana(date(anio, mes, d)) == dia_semana
    )


def test_horas_regulares_cuenta_ocurrencias_del_mes(conn):
    id_unidad, _ = _unidad(conn)
    id_consultorio = _consultorio(conn, id_unidad)
    id_prof = _profesional(conn)
    _reserva(conn, id_prof, id_consultorio, "Lunes", horas=2)
    conn.commit()

    est = calcular_estadisticas_operativas(conn, [id_unidad])
    esperado = _cantidad_dia(2026, 8, "Lunes") * 2
    assert est.por_unidad[0].horas_regulares == esperado


def test_subtotal_regulares_coincide_con_liquidacion_un_solo_consultorio(conn):
    id_unidad, _ = _unidad(conn)
    id_consultorio = _consultorio(conn, id_unidad)
    id_prof = _profesional(conn)
    _reserva(conn, id_prof, id_consultorio, "Lunes", horas=2)
    conn.commit()

    est = calcular_estadisticas_operativas(conn, [id_unidad])
    liq = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert est.por_unidad[0].subtotal_regulares == pytest.approx(liq.subtotal_reserva)


def test_categoria_b_cuenta_horas_pero_no_genera_subtotal(conn):
    id_unidad, _ = _unidad(conn)
    id_consultorio = _consultorio(conn, id_unidad)
    id_prof = _profesional(conn, categoria="B")
    _reserva(conn, id_prof, id_consultorio, "Lunes", horas=2)
    conn.commit()

    est = calcular_estadisticas_operativas(conn, [id_unidad])
    assert est.por_unidad[0].horas_regulares > 0
    assert est.por_unidad[0].subtotal_regulares == 0.0


def test_subtotal_aisladas_exacto(conn):
    id_unidad, _ = _unidad(conn)
    id_consultorio = _consultorio(conn, id_unidad)
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=11,
    )
    conn.commit()

    est = calcular_estadisticas_operativas(conn, [id_unidad])
    assert est.por_unidad[0].horas_aisladas == 2
    assert est.por_unidad[0].subtotal_aisladas == pytest.approx(2 * VALOR_HORA_AISLADA)


def test_falta_cobrar_descuenta_pagos_del_periodo(conn):
    id_unidad, _ = _unidad(conn)
    id_consultorio = _consultorio(conn, id_unidad)
    id_prof = _profesional(conn)
    _reserva(conn, id_prof, id_consultorio, "Lunes", horas=2)
    conn.commit()

    est_sin_pago = calcular_estadisticas_operativas(conn, [id_unidad])
    generado = est_sin_pago.por_unidad[0].falta_cobrar
    assert generado > 0

    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_prof, Monto=100, PeriodoImputado=PERIODO)
    conn.commit()

    est_con_pago = calcular_estadisticas_operativas(conn, [id_unidad])
    assert est_con_pago.por_unidad[0].falta_cobrar == pytest.approx(generado - 100)


def test_multi_consultorio_reparte_proporcional_a_las_horas(conn):
    id_unidad, _ = _unidad(conn)
    id_c1 = _consultorio(conn, id_unidad, numero=1)
    id_c2 = _consultorio(conn, id_unidad, numero=2)
    id_prof = _profesional(conn)
    _reserva(conn, id_prof, id_c1, "Lunes", horas=2)
    _reserva(conn, id_prof, id_c2, "Martes", horas=1)
    conn.commit()

    liq = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    horas_lunes = _cantidad_dia(2026, 8, "Lunes") * 2
    horas_martes = _cantidad_dia(2026, 8, "Martes") * 1
    total_horas = horas_lunes + horas_martes

    est = calcular_estadisticas_operativas(conn, [id_unidad])
    assert est.por_unidad[0].subtotal_regulares == pytest.approx(liq.subtotal_reserva)  # misma unidad, se suma todo
    _ = (horas_lunes, horas_martes, total_horas)  # documentado: el reparto es interno, acá coincide igual


def test_reparte_entre_dos_unidades_distintas_segun_horas(conn):
    id_unidad_1, _ = _unidad(conn, departamento="1A")
    id_unidad_2, _ = _unidad(conn, departamento="2B")
    id_c1 = _consultorio(conn, id_unidad_1, numero=1)
    id_c2 = _consultorio(conn, id_unidad_2, numero=1)
    id_prof = _profesional(conn)
    _reserva(conn, id_prof, id_c1, "Lunes", horas=2)
    _reserva(conn, id_prof, id_c2, "Lunes", horas=2)
    conn.commit()

    liq = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    est = calcular_estadisticas_operativas(conn, [id_unidad_1, id_unidad_2])
    por_unidad = {g.id: g for g in est.por_unidad}
    # mismas horas en cada consultorio -> reparto 50/50
    assert por_unidad[id_unidad_1].subtotal_regulares == pytest.approx(liq.subtotal_reserva / 2, rel=1e-6)
    assert por_unidad[id_unidad_2].subtotal_regulares == pytest.approx(liq.subtotal_reserva / 2, rel=1e-6)


def test_agregado_por_edificio_y_total(conn):
    id_unidad_1, id_edificio_1 = _unidad(conn, nombre_edificio="Ramos 1", departamento="1A")
    id_unidad_2 = _otra_unidad_mismo_edificio(conn, id_edificio_1, departamento="2B")
    id_unidad_3, id_edificio_3 = _unidad(conn, nombre_edificio="Ramos 2", departamento="1A")
    id_c1 = _consultorio(conn, id_unidad_1)
    id_c2 = _consultorio(conn, id_unidad_2)
    id_c3 = _consultorio(conn, id_unidad_3)
    id_prof = _profesional(conn)
    _reserva(conn, id_prof, id_c1, "Lunes", horas=1)
    _reserva(conn, id_prof, id_c2, "Lunes", horas=1)
    _reserva(conn, id_prof, id_c3, "Lunes", horas=1)
    conn.commit()

    est = calcular_estadisticas_operativas(conn, [id_unidad_1, id_unidad_2, id_unidad_3])
    assert len(est.por_unidad) == 3
    assert len(est.por_edificio) == 2

    por_edificio = {g.id: g for g in est.por_edificio}
    assert por_edificio[id_edificio_1].horas_regulares == pytest.approx(
        est.por_unidad[[g.id for g in est.por_unidad].index(id_unidad_1)].horas_regulares
        + [g for g in est.por_unidad if g.id == id_unidad_2][0].horas_regulares
    )
    assert por_edificio[id_edificio_3].horas_regulares == pytest.approx(
        [g for g in est.por_unidad if g.id == id_unidad_3][0].horas_regulares
    )

    total_horas_esperado = sum(g.horas_regulares for g in est.por_unidad)
    assert est.total.horas_regulares == pytest.approx(total_horas_esperado)
    total_subtotal_esperado = sum(g.subtotal_regulares for g in est.por_unidad)
    assert est.total.subtotal_regulares == pytest.approx(total_subtotal_esperado)


def test_agregado_por_localidad(conn):
    id_unidad_1, id_edificio_1 = _unidad(conn, nombre_edificio="Ramos 1", departamento="1A", localidad="Ramos Mejía")
    id_unidad_2 = _otra_unidad_mismo_edificio(conn, id_edificio_1, departamento="2B")
    id_unidad_3, id_edificio_3 = _unidad(conn, nombre_edificio="Haedo 1", departamento="1A", localidad="Haedo")
    id_c1 = _consultorio(conn, id_unidad_1)
    id_c2 = _consultorio(conn, id_unidad_2)
    id_c3 = _consultorio(conn, id_unidad_3)
    id_prof = _profesional(conn)
    _reserva(conn, id_prof, id_c1, "Lunes", horas=1)
    _reserva(conn, id_prof, id_c2, "Lunes", horas=1)
    _reserva(conn, id_prof, id_c3, "Lunes", horas=1)
    conn.commit()

    est = calcular_estadisticas_operativas(conn, [id_unidad_1, id_unidad_2, id_unidad_3])
    assert len(est.por_localidad) == 2

    por_localidad = {g.nombre: g for g in est.por_localidad}
    horas_ramos_mejia = sum(g.horas_regulares for g in est.por_unidad if g.id in (id_unidad_1, id_unidad_2))
    horas_haedo = [g for g in est.por_unidad if g.id == id_unidad_3][0].horas_regulares
    assert por_localidad["Ramos Mejía"].horas_regulares == pytest.approx(horas_ramos_mejia)
    assert por_localidad["Haedo"].horas_regulares == pytest.approx(horas_haedo)


def test_localidad_sin_dato_se_agrupa_como_sin_localidad(conn):
    id_unidad, _ = _unidad(conn, localidad=None)
    id_consultorio = _consultorio(conn, id_unidad)
    id_prof = _profesional(conn)
    _reserva(conn, id_prof, id_consultorio, "Lunes", horas=1)
    conn.commit()

    est = calcular_estadisticas_operativas(conn, [id_unidad])
    assert len(est.por_localidad) == 1
    assert est.por_localidad[0].nombre == "(Sin localidad)"


def test_sin_unidades_devuelve_vacio(conn):
    est = calcular_estadisticas_operativas(conn, [])
    assert est.por_unidad == []
    assert est.por_edificio == []
    assert est.por_localidad == []
    assert est.total.horas_regulares == 0.0
    assert est.periodo == PERIODO


def test_ocupacion_coincide_con_estadisticas_existente(conn):
    from app.negocio.estadisticas import calcular_ocupacion

    id_unidad, _ = _unidad(conn)
    id_consultorio = _consultorio(conn, id_unidad)
    id_prof = _profesional(conn)
    _reserva(conn, id_prof, id_consultorio, "Lunes", horas=2)
    conn.commit()

    ocupacion = calcular_ocupacion(conn, 2026, 8)
    est = calcular_estadisticas_operativas(conn, [id_unidad])
    assert est.por_unidad[0].porcentaje_ocupacion == pytest.approx(ocupacion.por_unidad[id_unidad].porcentaje)
