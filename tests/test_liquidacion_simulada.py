import calendar
from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.dias import DIAS_SEMANA
from app.negocio.liquidacion_simulada import BloqueSimulado, calcular_liquidacion_simulada
from app.negocio.valores import obtener_porcentaje_descuento
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def profesional(conn):
    return obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="7mo L")
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )


def _cantidad_dia_semana_en_periodo(anio: int, mes: int, dia_semana: str) -> int:
    indice = DIAS_SEMANA.index(dia_semana)
    return sum(
        1 for dia in range(1, calendar.monthrange(anio, mes)[1] + 1) if date(anio, mes, dia).weekday() == indice
    )


def test_sin_bloques_rechaza(conn, profesional):
    with pytest.raises(ValueError):
        calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[])


def test_consultorio_inexistente_rechaza(conn, profesional):
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=10, id_consultorio=999999)
    with pytest.raises(ValueError):
        calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])


def test_bruto_multiplica_horas_por_valor_por_cantidad_de_dias_del_periodo(conn, profesional, consultorio):
    """Un solo bloque de 2hs los lunes, consultorio a $1000/hora: el bruto
    tiene que ser 2 × 1000 × (cantidad de lunes de noviembre 2026)."""
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])

    cantidad_lunes = _cantidad_dia_semana_en_periodo(2026, 11, "Lunes")
    assert liquidacion.bruto == pytest.approx(2 * 1000 * cantidad_lunes)
    assert liquidacion.horas_semanales == pytest.approx(2)
    assert liquidacion.descuentos_feriados == []


def test_varios_bloques_en_distintos_dias_y_consultorios_se_suman(conn, profesional):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="7mo L")
    id_cons_1 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )
    id_cons_2 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=2, ValorHoraRegularActual=1500,
    )
    bloques = [
        BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=id_cons_1),
        BloqueSimulado(dia_semana="Miércoles", hora_inicio=14, hora_fin=15, id_consultorio=id_cons_2),
    ]
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=bloques)

    cantidad_lunes = _cantidad_dia_semana_en_periodo(2026, 11, "Lunes")
    cantidad_miercoles = _cantidad_dia_semana_en_periodo(2026, 11, "Miércoles")
    esperado = 2 * 1000 * cantidad_lunes + 1 * 1500 * cantidad_miercoles
    assert liquidacion.bruto == pytest.approx(esperado)
    assert liquidacion.horas_semanales == pytest.approx(3)


def test_aplica_el_mismo_descuento_por_volumen_que_el_resto_del_sistema(conn, profesional, consultorio):
    """El % de descuento por volumen tiene que ser exactamente el que ya
    da `obtener_porcentaje_descuento` para el total de horas semanales de
    los bloques — no un cálculo propio distinto."""
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=8, hora_fin=20, id_consultorio=consultorio)  # 12hs
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])

    assert liquidacion.descuento_horas_pct == obtener_porcentaje_descuento(conn, 12)
    if liquidacion.descuento_horas_pct:
        assert liquidacion.neto < liquidacion.bruto


def test_feriado_en_dia_con_bloque_se_descuenta(conn, profesional, consultorio):
    """Confirmado que 2026-11-02 (feriado nacional de ejemplo) cae lunes."""
    fecha_feriado = "2026-11-02"
    assert date.fromisoformat(fecha_feriado).weekday() == 0  # lunes
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha=fecha_feriado, Descripcion="Feriado de prueba", Tipo="Feriado nacional",
    )
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])

    assert len(liquidacion.descuentos_feriados) == 1
    item = liquidacion.descuentos_feriados[0]
    assert item.fecha == fecha_feriado
    assert item.tipo == "Feriado nacional"
    valor_dia_neto = 2 * 1000 * (1 - liquidacion.descuento_horas_pct / 100)
    assert item.monto == pytest.approx(valor_dia_neto)
    assert liquidacion.neto == pytest.approx(
        liquidacion.bruto * (1 - liquidacion.descuento_horas_pct / 100) - item.monto
    )


def test_feriado_en_dia_sin_bloque_no_descuenta_nada(conn, profesional, consultorio):
    """El feriado cae martes, pero el único bloque cargado es de lunes —
    no hay nada reservado ese día, así que no hay nada que descontar."""
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-11-03", Descripcion="Feriado de prueba", Tipo="Feriado nacional",
    )
    assert date.fromisoformat("2026-11-03").weekday() == 1  # martes
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])

    assert liquidacion.descuentos_feriados == []


def test_dia_no_laborable_usa_su_propio_porcentaje(conn, profesional, consultorio):
    conn.execute(
        "UPDATE Configuracion SET PorcentajeDescuentoFeriado = 100, PorcentajeDescuentoNoLaborable = 50 "
        "WHERE IdConfiguracion = 1"
    )
    conn.commit()
    fecha_no_laborable = "2026-11-02"
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha=fecha_no_laborable, Descripcion="Puente turístico", Tipo="Día no laborable",
    )
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])

    item = liquidacion.descuentos_feriados[0]
    valor_dia_neto = 2 * 1000 * (1 - liquidacion.descuento_horas_pct / 100)
    assert item.monto == pytest.approx(valor_dia_neto * 0.5)


def test_feriado_en_domingo_no_se_descuenta(conn, profesional, consultorio):
    """Mismo criterio que la liquidación real (`feriados_relevantes_
    periodo`): los domingos se omiten, no se liquida ese día."""
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-11-01", Descripcion="Feriado en domingo", Tipo="Feriado nacional",
    )
    assert date.fromisoformat("2026-11-01").weekday() == 6  # domingo
    bloque = BloqueSimulado(dia_semana="Domingo", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])

    assert liquidacion.descuentos_feriados == []


def test_subtotal_de_un_solo_bloque_coincide_con_el_total(conn, profesional, consultorio):
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])

    assert len(liquidacion.subtotales_bloques) == 1
    subtotal = liquidacion.subtotales_bloques[0]
    assert subtotal.numero == 1
    assert subtotal.horas_semanales == pytest.approx(2)
    cantidad_lunes = _cantidad_dia_semana_en_periodo(2026, 11, "Lunes")
    assert subtotal.horas_mensuales == pytest.approx(2 * cantidad_lunes)
    assert subtotal.bruto == pytest.approx(liquidacion.bruto)
    assert subtotal.descuento_pct == liquidacion.descuento_horas_pct
    assert subtotal.neto == pytest.approx(liquidacion.neto)


def test_subtotales_de_varios_bloques_suman_bruto_y_neto_totales(conn, profesional):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="7mo L")
    id_cons_1 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )
    id_cons_2 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=2, ValorHoraRegularActual=1500,
    )
    bloques = [
        BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=id_cons_1),
        BloqueSimulado(dia_semana="Miércoles", hora_inicio=14, hora_fin=15, id_consultorio=id_cons_2),
    ]
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=bloques)

    assert [s.numero for s in liquidacion.subtotales_bloques] == [1, 2]
    assert sum(s.bruto for s in liquidacion.subtotales_bloques) == pytest.approx(liquidacion.bruto)
    assert sum(s.neto for s in liquidacion.subtotales_bloques) == pytest.approx(liquidacion.neto)


def test_feriado_se_atribuye_solo_al_subtotal_del_bloque_de_ese_dia(conn, profesional):
    """Un feriado que cae lunes solo tiene que afectar el descuento/neto
    del bloque de los lunes, no el del miércoles."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="7mo L")
    id_cons_1 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )
    id_cons_2 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=2, ValorHoraRegularActual=1500,
    )
    fecha_feriado = "2026-11-02"
    assert date.fromisoformat(fecha_feriado).weekday() == 0  # lunes
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha=fecha_feriado, Descripcion="Feriado de prueba", Tipo="Feriado nacional",
    )
    bloques = [
        BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=id_cons_1),
        BloqueSimulado(dia_semana="Miércoles", hora_inicio=14, hora_fin=15, id_consultorio=id_cons_2),
    ]
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=bloques)

    subtotal_lunes, subtotal_miercoles = liquidacion.subtotales_bloques
    descuento_por_volumen_lunes = subtotal_lunes.bruto * liquidacion.descuento_horas_pct / 100
    assert subtotal_lunes.descuento > descuento_por_volumen_lunes  # volumen + feriado
    descuento_por_volumen_miercoles = subtotal_miercoles.bruto * liquidacion.descuento_horas_pct / 100
    assert subtotal_miercoles.descuento == pytest.approx(descuento_por_volumen_miercoles)  # solo volumen
    assert sum(s.neto for s in liquidacion.subtotales_bloques) == pytest.approx(liquidacion.neto)
