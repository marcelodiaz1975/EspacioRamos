import calendar
from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.dias import fecha_a_dia_semana
from app.negocio.liquidaciones import calcular_liquidacion, emitir_liquidacion, marcar_estado_envio
from app.negocio.pagos import crear_cargo_especial, crear_plan_pago, marcar_cuota_pagada, registrar_pago
from app.negocio.valores import obtener_porcentaje_descuento
from app.repositorio.registro import obtener_repositorio

VALOR_HORA_REGULAR = 1000
VALOR_HORA_AISLADA = 500
PERIODO = "2026-08"
PERIODO_ANTERIOR = "2026-07"


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
        IdUnidad=id_unidad, NumeroConsultorio=1,
        ValorHoraRegularActual=VALOR_HORA_REGULAR, ValorHoraAisladaActual=VALOR_HORA_AISLADA,
    )


def _crear_profesional(conn, categoria="R", cabeza_equipo=None):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional=categoria, Apellido="Lo Veci", ProfesionalCabezaEquipo=cabeza_equipo,
    )


def _crear_reserva(conn, id_prof, consultorio, dia_semana="Lunes", horas=2, vigencia_inicio="2026-01-01",
                    vigencia_fin=None):
    return obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana=dia_semana,
        HoraInicio=10, HoraFin=10 + horas, VigenciaInicio=vigencia_inicio, VigenciaFin=vigencia_fin,
    )


def _profesional_con_reserva_lunes(conn, consultorio, categoria="R", horas=2):
    id_prof = _crear_profesional(conn, categoria=categoria)
    _crear_reserva(conn, id_prof, consultorio, "Lunes", horas)
    return id_prof


def _cantidad_dia(anio: int, mes: int, dia_semana: str) -> int:
    total_dias = calendar.monthrange(anio, mes)[1]
    return sum(
        1 for d in range(1, total_dias + 1)
        if fecha_a_dia_semana(date(anio, mes, d)) == dia_semana
    )


def test_categorias_sin_liquidacion_propia_lanzan_error(conn, consultorio):
    for categoria in ("A", "B", "E", "X", "C"):
        id_prof = _profesional_con_reserva_lunes(conn, consultorio, categoria=categoria)
        with pytest.raises(ValueError):
            calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)


def test_bruto_y_subtotal_reserva(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    lunes_en_agosto = _cantidad_dia(2026, 8, "Lunes")
    bruto_esperado = lunes_en_agosto * 2 * VALOR_HORA_REGULAR
    descuento_pct = obtener_porcentaje_descuento(conn, 2)

    assert liquidacion.bruto == pytest.approx(bruto_esperado)
    assert liquidacion.subtotal_reserva == pytest.approx(bruto_esperado * (1 - descuento_pct / 100))
    assert liquidacion.saldo_anterior == 0
    assert len(liquidacion.tramos) == 1
    assert liquidacion.total == pytest.approx(liquidacion.subtotal_reserva)


def test_categoria_e_se_consolida_en_liquidacion_del_r(conn, consultorio):
    id_r = _crear_profesional(conn, categoria="R")
    _crear_reserva(conn, id_r, consultorio, "Lunes", horas=2)
    id_e = _crear_profesional(conn, categoria="E", cabeza_equipo=id_r)
    _crear_reserva(conn, id_e, consultorio, "Martes", horas=3)

    liquidacion = calcular_liquidacion(conn, id_profesional=id_r, periodo=PERIODO)

    lunes = _cantidad_dia(2026, 8, "Lunes")
    martes = _cantidad_dia(2026, 8, "Martes")
    bruto_esperado = lunes * 2 * VALOR_HORA_REGULAR + martes * 3 * VALOR_HORA_REGULAR
    descuento_pct = obtener_porcentaje_descuento(conn, 5)  # 2hs (R) + 3hs (E) = 5hs consolidadas

    assert liquidacion.bruto == pytest.approx(bruto_esperado)
    assert liquidacion.subtotal_reserva == pytest.approx(bruto_esperado * (1 - descuento_pct / 100))

    # el E no tiene liquidación propia
    with pytest.raises(ValueError):
        calcular_liquidacion(conn, id_profesional=id_e, periodo=PERIODO)


def test_tramos_se_desglosan_si_cambian_horas_semanales_a_mitad_de_mes(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    # 15/8 es sábado: agrega una reserva nueva desde ese día (sin emisión previa, se cobra completa)
    _crear_reserva(conn, id_prof, consultorio, "Martes", horas=3, vigencia_inicio="2026-08-15")

    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    assert len(liquidacion.tramos) == 2
    assert liquidacion.tramos[0].fecha_desde == "2026-08-01"
    assert liquidacion.tramos[0].fecha_hasta == "2026-08-14"
    assert liquidacion.tramos[0].horas_semanales == pytest.approx(2)
    assert liquidacion.tramos[1].fecha_desde == "2026-08-15"
    assert liquidacion.tramos[1].fecha_hasta == "2026-08-31"
    assert liquidacion.tramos[1].horas_semanales == pytest.approx(5)
    assert liquidacion.tramos[0].descuento_pct == pytest.approx(obtener_porcentaje_descuento(conn, 2))
    assert liquidacion.tramos[1].descuento_pct == pytest.approx(obtener_porcentaje_descuento(conn, 5))
    assert liquidacion.subtotal_reserva == pytest.approx(sum(t.subtotal for t in liquidacion.tramos))


def test_pierde_descuento_horas_si_saldo_anterior_supera_tolerancia(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=100)
    # tolerancia por defecto es 0 -> cualquier saldo positivo hace perder el descuento

    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    descuento_pct = obtener_porcentaje_descuento(conn, 2)
    assert liquidacion.pierde_descuento_horas is True
    # el % real se sigue aplicando y mostrando (subtotal < bruto)...
    assert liquidacion.tramos[0].descuento_pct == pytest.approx(descuento_pct)
    assert liquidacion.subtotal_reserva == pytest.approx(liquidacion.bruto * (1 - descuento_pct / 100))
    # ...pero se revierte por completo, así que el total final no cambia
    # (el % de descuento aplicado y su reversión se cancelan entre sí)
    assert liquidacion.reversion_descuento == pytest.approx(liquidacion.bruto - liquidacion.subtotal_reserva)
    assert liquidacion.total == pytest.approx(
        liquidacion.bruto + liquidacion.saldo_anterior + liquidacion.ajuste_saldo_atrasado
    )


def test_reversion_descuento_es_cero_si_las_horas_no_alcanzan_ningun_tramo(conn, consultorio):
    """Si no hay ningún tramo de descuento que aplique (0% real), no hay
    nada que revertir aunque se pierda el descuento por saldo atrasado."""
    conn.execute("DELETE FROM EsquemaDescuentos")
    conn.commit()
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=100)
    assert obtener_porcentaje_descuento(conn, 2) == 0

    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    assert liquidacion.pierde_descuento_horas is True
    assert liquidacion.reversion_descuento == 0


def test_no_pierde_descuento_si_saldo_anterior_dentro_de_tolerancia(conn, consultorio):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=500)
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=100)

    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    assert liquidacion.pierde_descuento_horas is False
    assert liquidacion.tramos[0].descuento_pct == pytest.approx(obtener_porcentaje_descuento(conn, 2))


def test_suspender_descuento_periodo_mantiene_perdido_el_descuento_de_horas(conn, consultorio):
    """DC-06 §5.2: aunque el saldo ya volvió a estar dentro de tolerancia,
    si el operador eligió NO restablecer el descuento, sigue perdido para
    esa liquidación puntual — pero el ajuste por saldo atrasado (mecanismo
    aparte) no se ve afectado, porque depende solo del saldo real."""
    from app.negocio.pagos import suspender_descuento_periodo

    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=500)
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=100)  # ya dentro de tolerancia
    suspender_descuento_periodo(conn, id_profesional=id_prof, periodo=PERIODO)

    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.pierde_descuento_horas is True
    assert liquidacion.ajuste_saldo_atrasado == 0  # no se reactiva por la suspensión manual


def test_suspender_descuento_periodo_no_afecta_otros_periodos(conn, consultorio):
    """La decisión es por período puntual: no arrastra a los meses
    siguientes, que se evalúan de forma independiente."""
    from app.negocio.pagos import suspender_descuento_periodo

    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=500)
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=100)
    suspender_descuento_periodo(conn, id_profesional=id_prof, periodo=PERIODO_ANTERIOR)

    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.pierde_descuento_horas is False


def test_ajuste_saldo_atrasado_por_encima_de_tolerancia(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=1000)
    # tolerancia por defecto 0, PorcentajeAjusteSaldoAtrasado por defecto 3%

    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.ajuste_saldo_atrasado == pytest.approx(30)


def test_ajuste_no_aplica_dentro_de_tolerancia(conn, consultorio):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=2000)
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=1000)

    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.ajuste_saldo_atrasado == 0


def test_pago_imputado_a_mes_anterior_regulariza_antes_de_calcular_y_evita_ajuste(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=1000)

    liquidacion_antes = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion_antes.ajuste_saldo_atrasado > 0
    assert liquidacion_antes.pierde_descuento_horas is True

    # paga el saldo del mes anterior (2026-07) antes de que se calcule/emita la liquidación
    registrar_pago(conn, id_profesional=id_prof, monto=1000, periodo_imputado=PERIODO_ANTERIOR)

    liquidacion_despues = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion_despues.saldo_anterior == 0
    assert liquidacion_despues.ajuste_saldo_atrasado == 0
    assert liquidacion_despues.pierde_descuento_horas is False


def test_descuento_feriado_nacional_se_lista_por_dia(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    assert fecha_a_dia_semana(date(2026, 8, 17)) == "Lunes"
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-08-17", Descripcion="Feriado de prueba", Tipo="Feriado nacional",
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    descuento_pct = obtener_porcentaje_descuento(conn, 2)
    monto_esperado = 2 * VALOR_HORA_REGULAR * (1 - descuento_pct / 100)

    assert len(liquidacion.descuentos_feriados) == 1
    assert liquidacion.descuentos_feriados[0].fecha == "2026-08-17"
    assert liquidacion.descuentos_feriados[0].monto == pytest.approx(monto_esperado)
    assert liquidacion.descuentos_no_laborables == []
    assert liquidacion.total == pytest.approx(liquidacion.subtotal_reserva - monto_esperado)


def test_porcentaje_de_feriado_es_independiente_del_no_laborable(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    conn.execute(
        "UPDATE Configuracion SET PorcentajeDescuentoFeriado = 50, PorcentajeDescuentoNoLaborable = 100 "
        "WHERE IdConfiguracion = 1"
    )
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-08-17", Descripcion="Feriado de prueba", Tipo="Feriado nacional",
    )
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-08-24", Descripcion="No laborable de prueba", Tipo="Día no laborable",
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    descuento_pct = obtener_porcentaje_descuento(conn, 2)
    monto_completo = 2 * VALOR_HORA_REGULAR * (1 - descuento_pct / 100)

    assert liquidacion.descuentos_feriados[0].monto == pytest.approx(monto_completo * 0.5)
    assert liquidacion.descuentos_no_laborables[0].monto == pytest.approx(monto_completo)


def test_descuento_dia_no_laborable_va_en_lista_separada(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-08-24", Descripcion="No laborable de prueba", Tipo="Día no laborable",
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    assert liquidacion.descuentos_feriados == []
    assert len(liquidacion.descuentos_no_laborables) == 1
    assert liquidacion.descuentos_no_laborables[0].fecha == "2026-08-24"


def test_feriado_pendiente_agregado_despues_de_emitida_la_liquidacion_del_mes_anterior(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO_ANTERIOR, fecha_emision="2026-07-01")

    # el 20/7 (lunes) se agrega como feriado extraordinario DESPUÉS de emitida julio
    assert fecha_a_dia_semana(date(2026, 7, 20)) == "Lunes"
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-07-20", Descripcion="Feriado extraordinario", Tipo="Feriado nacional",
    )

    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert len(liquidacion.feriados_pendientes) == 1
    assert liquidacion.feriados_pendientes[0].fecha == "2026-07-20"
    descuento_pct = obtener_porcentaje_descuento(conn, 2)
    assert liquidacion.feriados_pendientes[0].monto == pytest.approx(2 * VALOR_HORA_REGULAR * (1 - descuento_pct / 100))


def test_feriado_conocido_antes_de_emitir_no_queda_pendiente(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-07-06", Descripcion="Feriado conocido", Tipo="Feriado nacional",
    )
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO_ANTERIOR, fecha_emision="2026-07-10")

    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.feriados_pendientes == []


def test_aisladas_mes_en_curso_y_mes_anterior(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    conn.execute("UPDATE Configuracion SET RecargoPorcentajeAisladas = 10 WHERE IdConfiguracion = 1")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-08-05",
        HoraInicio=9, HoraFin=11, Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-07-06",
        HoraInicio=9, HoraFin=11, Estado="Confirmada", AplicaRecargo=1,
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    assert liquidacion.total_aisladas_mes_en_curso == pytest.approx(2 * VALOR_HORA_AISLADA)
    assert liquidacion.total_aisladas_mes_anterior == pytest.approx(2 * VALOR_HORA_AISLADA * 1.10)


def test_reserva_aislada_cancelada_no_se_factura(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-08-05",
        HoraInicio=9, HoraFin=11, Estado="Cancelada", AplicaRecargo=0,
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.total_aisladas_mes_en_curso == 0


def test_reserva_aislada_de_reubicacion_no_genera_cargo(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-08-05",
        HoraInicio=9, HoraFin=11, Estado="Confirmada", AplicaRecargo=1, EsReubicacion=1,
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.total_aisladas_mes_en_curso == 0


def test_descuento_vacaciones_no_se_duplica_al_cruzar_fin_de_mes(conn, consultorio):
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    id_prof = _crear_profesional(conn)
    for dia in dias:
        _crear_reserva(conn, id_prof, consultorio, dia, horas=2)
    from app.negocio.vacaciones import crear_vacacion
    id_vacacion, _ = crear_vacacion(
        conn, id_profesional=id_prof, fecha_desde="2026-08-28", fecha_hasta="2026-09-03",
    )
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)

    liq_agosto = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-08")
    liq_septiembre = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-09")

    assert liq_agosto.total_descuento_vacaciones > 0
    assert liq_septiembre.total_descuento_vacaciones > 0
    suma = liq_agosto.total_descuento_vacaciones + liq_septiembre.total_descuento_vacaciones
    assert suma == pytest.approx(vacacion["ValorBonificado"])


def test_descuento_licencias_dia_por_dia(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    from app.negocio.licencias import crear_licencia
    id_tipo = obtener_repositorio(conn, "TipoLicencia").listar(Nombre="Licencia médica")[0]["IdTipoLicencia"]
    id_licencia, _ = crear_licencia(
        conn, id_profesional=id_prof, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-29", fecha_hasta="2026-09-04",
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert licencia["ValorBonificado"] > 0

    liq_agosto = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-08")
    liq_septiembre = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-09")
    suma = liq_agosto.total_descuento_licencias + liq_septiembre.total_descuento_licencias
    assert suma == pytest.approx(licencia["ValorBonificado"])


def test_descuento_vacaciones_respeta_tope_de_cupo_sin_duplicar(conn, consultorio):
    # cupo chico a propósito para forzar que la vacación exceda y se prorratee
    obtener_repositorio(conn, "Configuracion").actualizar(1, SemanasVacacionesMaximasPorAnio=0.5)
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    id_prof = _crear_profesional(conn)
    for dia in dias:
        _crear_reserva(conn, id_prof, consultorio, dia, horas=2)
    from app.negocio.vacaciones import crear_vacacion
    id_vacacion, advertencias = crear_vacacion(
        conn, id_profesional=id_prof, fecha_desde="2026-08-28", fecha_hasta="2026-09-03",  # 1 semana pedida
    )
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)
    assert len(advertencias) == 1  # excede el cupo de 0.5 semanas
    assert 0 < vacacion["ValorBonificado"] < 14 * VALOR_HORA_REGULAR  # capeado, no el bruto semanal completo

    liq_agosto = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-08")
    liq_septiembre = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-09")
    suma = liq_agosto.total_descuento_vacaciones + liq_septiembre.total_descuento_vacaciones
    # la suma entre los dos meses tiene que dar EXACTO el ValorBonificado ya
    # capeado, nunca más (antes del fix se recalculaba sobre el rango
    # completo pedido y se perdía el recorte por cupo agotado)
    assert suma == pytest.approx(vacacion["ValorBonificado"])


def test_descuento_licencias_respeta_tope_de_duracion_maxima_sin_duplicar(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    from app.negocio.licencias import crear_licencia
    id_tipo = obtener_repositorio(conn, "TipoLicencia").listar(Nombre="Licencia por duelo")[0]["IdTipoLicencia"]  # 5 días, 100%
    # pide 12 días (30/8 al 10/9); el tope de 5 días solo llega a cubrir hasta el 3/9,
    # así que el lunes 7/9 (dentro del rango pedido pero fuera del bonificable) es excedente
    assert fecha_a_dia_semana(date(2026, 9, 7)) == "Lunes"
    id_licencia, advertencias = crear_licencia(
        conn, id_profesional=id_prof, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-30", fecha_hasta="2026-09-10",
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)
    assert len(advertencias) == 1

    liq_agosto = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-08")
    liq_septiembre = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-09")
    suma = liq_agosto.total_descuento_licencias + liq_septiembre.total_descuento_licencias
    # si se contara el lunes 7/9 (excedente) la suma daría de más
    assert suma == pytest.approx(licencia["ValorBonificado"])


def test_emitir_liquidacion_rechaza_reemitir_periodo_anterior_a_uno_ya_emitido(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-08", fecha_emision="2026-08-01")
    emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-09", fecha_emision="2026-09-01")

    with pytest.raises(ValueError):
        emitir_liquidacion(conn, id_profesional=id_prof, periodo="2026-08", fecha_emision="2026-09-15")


def test_marcar_estado_envio_falla_sin_liquidacion_emitida(conn):
    id_prof = _crear_profesional(conn)
    with pytest.raises(ValueError):
        marcar_estado_envio(conn, id_profesional=id_prof, periodo=PERIODO, enviada=True)


def test_marcar_estado_envio_marca_y_revierte(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-01")

    marcar_estado_envio(conn, id_profesional=id_prof, periodo=PERIODO, enviada=True)
    ultima = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_prof, Periodo=PERIODO)[0]
    assert ultima["EstadoEnvio"] == "Enviada"

    marcar_estado_envio(conn, id_profesional=id_prof, periodo=PERIODO, enviada=False)
    ultima = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_prof, Periodo=PERIODO)[0]
    assert ultima["EstadoEnvio"] == "No enviada"


def test_marcar_estado_envio_actua_sobre_la_ultima_emision(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    id_liq_1, _ = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-01")
    id_liq_2, _ = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-05")

    marcar_estado_envio(conn, id_profesional=id_prof, periodo=PERIODO, enviada=True)

    repo = obtener_repositorio(conn, "LiquidacionEmitida")
    assert repo.obtener(id_liq_2)["EstadoEnvio"] == "Enviada"
    assert repo.obtener(id_liq_1)["EstadoEnvio"] == "No enviada"


def test_reserva_agregada_sin_emision_previa_se_cobra_completa(conn, consultorio):
    id_prof = _crear_profesional(conn)
    id_reserva = _crear_reserva(conn, id_prof, consultorio, "Martes", horas=2, vigencia_inicio="2026-08-15")
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    # martes de agosto 2026 desde el 15 en adelante: 18 y 25
    assert liquidacion.bruto == pytest.approx(2 * 2 * VALOR_HORA_REGULAR)
    assert liquidacion.horas_regulares_agregadas == []
    assert id_reserva is not None


def test_reserva_agregada_luego_de_emitida_se_traslada_al_mes_siguiente(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-01")

    id_reserva_nueva = _crear_reserva(conn, id_prof, consultorio, "Martes", horas=2, vigencia_inicio="2026-08-15")

    liq_agosto = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    lunes_en_agosto = _cantidad_dia(2026, 8, "Lunes")
    assert liq_agosto.bruto == pytest.approx(lunes_en_agosto * 2 * VALOR_HORA_REGULAR)
    assert liq_agosto.horas_regulares_agregadas == []

    liq_septiembre = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-09")
    assert len(liq_septiembre.horas_regulares_agregadas) == 1
    item = liq_septiembre.horas_regulares_agregadas[0]
    assert item.id_reserva_regular == id_reserva_nueva
    assert liq_septiembre.total_horas_regulares_agregadas > 0


def test_feriado_trabajado_mes_en_curso_avisado_antes_de_emitir(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "FeriadoTrabajado").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-08-17",
        HoraInicio=9, HoraFin=11, AplicaRecargo=0, FechaCarga="2026-08-01",
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    assert len(liquidacion.feriados_trabajados_mes_en_curso) == 1
    descuento_pct = obtener_porcentaje_descuento(conn, 2)
    esperado = 2 * VALOR_HORA_REGULAR * (1 - descuento_pct / 100)
    assert liquidacion.feriados_trabajados_mes_en_curso[0].monto == pytest.approx(esperado)
    assert liquidacion.feriados_trabajados_mes_anterior == []


def test_feriado_trabajado_mes_anterior_avisado_despues_de_emitir(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO_ANTERIOR, fecha_emision="2026-07-05")

    obtener_repositorio(conn, "FeriadoTrabajado").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-07-09",
        HoraInicio=9, HoraFin=11, AplicaRecargo=0, FechaCarga="2026-07-20",  # avisó después de emitida julio
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert len(liquidacion.feriados_trabajados_mes_anterior) == 1
    assert liquidacion.feriados_trabajados_mes_en_curso == []


def test_feriado_trabajado_avisado_a_tiempo_no_se_duplica_al_mes_siguiente(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "FeriadoTrabajado").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-07-09",
        HoraInicio=9, HoraFin=11, AplicaRecargo=0, FechaCarga="2026-07-01",  # antes de emitir julio
    )
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO_ANTERIOR, fecha_emision="2026-07-05")

    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.feriados_trabajados_mes_anterior == []


def test_cargos_especiales_suman_con_signo(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    crear_cargo_especial(
        conn, id_profesional=id_prof, tipo="Débito", concepto="reintegro llave",
        monto=500, periodo_imputado=PERIODO,
    )
    crear_cargo_especial(
        conn, id_profesional=id_prof, tipo="Crédito", concepto="ajuste manual",
        monto=200, periodo_imputado=PERIODO,
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.total_cargos_especiales == pytest.approx(300)


def test_cuotas_de_plan_pendientes_del_periodo_se_incluyen(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    id_plan = crear_plan_pago(
        conn, id_profesional=id_prof, monto_refinanciado=300, cantidad_cuotas=3, mes_ano_inicio="2026-08",
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.total_cuotas_plan == pytest.approx(100)

    cuota = obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan, PeriodoImputado=PERIODO)[0]
    marcar_cuota_pagada(conn, cuota["IdCuota"])
    liquidacion_luego_de_pagar = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion_luego_de_pagar.total_cuotas_plan == 0


def test_emitir_liquidacion_no_toca_saldo_anterior_y_acredita_lo_generado(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=1000, SaldoCuentaActual=0)

    id_liquidacion, liquidacion = emitir_liquidacion(
        conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-01",
    )
    registro = obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liquidacion)
    assert registro["Periodo"] == PERIODO
    assert registro["EstadoEnvio"] == "No enviada"
    assert registro["MontoGenerado"] == pytest.approx(liquidacion.monto_generado)

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["SaldoCuentaAnterior"] == pytest.approx(1000)  # sin tocar
    assert profesional["SaldoCuentaActual"] == pytest.approx(liquidacion.monto_generado)
    assert liquidacion.total == pytest.approx(1000 + liquidacion.monto_generado)


def test_estado_envio_y_reemision_se_derivan_solos(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)

    id_liq_1, _ = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-01")
    liq_1 = obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liq_1)
    assert liq_1["EstadoEnvio"] == "No enviada"
    assert liq_1["EsReemision"] == 0

    # regenerar sin haberla marcado como enviada: sigue "No enviada"
    id_liq_2, _ = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-02")
    liq_2 = obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liq_2)
    assert liq_2["EstadoEnvio"] == "No enviada"
    assert liq_2["EsReemision"] == 1

    # el operador la marca como enviada; una regeneración posterior pasa a "Regenerada no enviada"
    obtener_repositorio(conn, "LiquidacionEmitida").actualizar(id_liq_2, EstadoEnvio="Enviada")
    id_liq_3, _ = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-15")
    liq_3 = obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liq_3)
    assert liq_3["EstadoEnvio"] == "Regenerada no enviada"
    assert liq_3["EsReemision"] == 1


def test_reemision_no_pisa_pagos_ya_registrados_contra_el_mes_en_curso(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=0, SaldoCuentaActual=0)

    _, liq_1 = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-01")
    registrar_pago(conn, id_profesional=id_prof, monto=500)  # pago contra el mes en curso

    saldo_tras_pago = obtener_repositorio(conn, "Profesional").obtener(id_prof)["SaldoCuentaActual"]
    assert saldo_tras_pago == pytest.approx(liq_1.monto_generado - 500)

    crear_cargo_especial(
        conn, id_profesional=id_prof, tipo="Débito", concepto="depósito llave", monto=300, periodo_imputado=PERIODO,
    )
    _, liq_2 = emitir_liquidacion(
        conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-10",
    )
    assert liq_2.monto_generado == pytest.approx(liq_1.monto_generado + 300)

    saldo_final = obtener_repositorio(conn, "Profesional").obtener(id_prof)["SaldoCuentaActual"]
    # el pago de 500 sigue descontado; el cargo de 300 se suma encima, sin repetir lo ya emitido
    assert saldo_final == pytest.approx(liq_1.monto_generado - 500 + 300)
