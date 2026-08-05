import calendar
from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.dias import fecha_a_dia_semana
from app.negocio.liquidaciones import calcular_liquidacion, emitir_liquidacion
from app.negocio.pagos import crear_cargo_especial, crear_plan_pago, marcar_cuota_pagada
from app.negocio.valores import obtener_porcentaje_descuento
from app.repositorio.registro import obtener_repositorio

VALOR_HORA_REGULAR = 1000
VALOR_HORA_AISLADA = 500
PERIODO = "2026-08"


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


def _profesional_con_reserva_lunes(conn, consultorio, categoria="R", horas=2):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional=categoria, Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=10 + horas, VigenciaInicio="2026-01-01",
    )
    return id_prof


def _cantidad_lunes(anio: int, mes: int) -> int:
    total_dias = calendar.monthrange(anio, mes)[1]
    return sum(1 for d in range(1, total_dias + 1) if date(anio, mes, d).weekday() == 0)


def test_categoria_sin_liquidacion_mensual_lanza_error(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, categoria="A")
    with pytest.raises(ValueError):
        calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)


def test_bruto_y_subtotal_reserva(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    lunes_en_agosto = _cantidad_lunes(2026, 8)
    bruto_esperado = lunes_en_agosto * 2 * VALOR_HORA_REGULAR
    descuento_pct = obtener_porcentaje_descuento(conn, 2)

    assert liquidacion.bruto == pytest.approx(bruto_esperado)
    assert liquidacion.subtotal_reserva == pytest.approx(bruto_esperado * (1 - descuento_pct / 100))
    assert liquidacion.saldo_anterior == 0
    assert liquidacion.total == pytest.approx(liquidacion.subtotal_reserva)


def test_categoria_b_tiene_100_por_ciento_de_bonificacion(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, categoria="B", horas=2)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-08-05",
        HoraInicio=9, HoraFin=11, Estado="Confirmada", AplicaRecargo=0,
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    assert liquidacion.descuento_bonificacion == pytest.approx(liquidacion.subtotal_reserva)
    # la bonificación cubre la reserva regular, pero las aisladas se siguen cobrando
    assert liquidacion.total == pytest.approx(liquidacion.aisladas_mes_en_curso)
    assert liquidacion.total > 0


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


def test_descuento_dia_no_laborable_va_en_lista_separada(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-08-24", Descripcion="No laborable de prueba", Tipo="Día no laborable",
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    assert liquidacion.descuentos_feriados == []
    assert len(liquidacion.descuentos_no_laborables) == 1
    assert liquidacion.descuentos_no_laborables[0].fecha == "2026-08-24"


def test_aisladas_mes_en_curso_y_mes_anterior(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-08-05",
        HoraInicio=9, HoraFin=11, Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-07-06",
        HoraInicio=9, HoraFin=11, Estado="Confirmada", AplicaRecargo=1,
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)

    assert liquidacion.aisladas_mes_en_curso == pytest.approx(2 * VALOR_HORA_AISLADA)
    assert liquidacion.aisladas_mes_anterior == pytest.approx(2 * VALOR_HORA_AISLADA * 1.10)


def test_reserva_aislada_cancelada_no_se_factura(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, Fecha="2026-08-05",
        HoraInicio=9, HoraFin=11, Estado="Cancelada", AplicaRecargo=0,
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.aisladas_mes_en_curso == 0


def test_descuento_vacaciones_no_se_duplica_al_cruzar_fin_de_mes(conn, consultorio):
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    for dia in dias:
        obtener_repositorio(conn, "ReservaRegular").crear(
            IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana=dia,
            HoraInicio=10, HoraFin=12, VigenciaInicio="2026-01-01",
        )
    from app.negocio.vacaciones import crear_vacacion
    id_vacacion, _ = crear_vacacion(
        conn, id_profesional=id_prof, fecha_desde="2026-08-28", fecha_hasta="2026-09-03",
    )
    vacacion = obtener_repositorio(conn, "Vacacion").obtener(id_vacacion)

    liq_agosto = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-08")
    liq_septiembre = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-09")

    assert liq_agosto.descuento_vacaciones > 0
    assert liq_septiembre.descuento_vacaciones > 0
    suma = liq_agosto.descuento_vacaciones + liq_septiembre.descuento_vacaciones
    assert suma == pytest.approx(vacacion["ValorBonificado"])


def test_descuento_licencias_prorratea_por_mes(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    from app.negocio.licencias import crear_licencia
    id_tipo = obtener_repositorio(conn, "TipoLicencia").listar(Nombre="Licencia médica")[0]["IdTipoLicencia"]
    id_licencia = crear_licencia(
        conn, id_profesional=id_prof, id_tipo_licencia=id_tipo,
        fecha_desde="2026-08-29", fecha_hasta="2026-09-04",
    )
    licencia = obtener_repositorio(conn, "Licencia").obtener(id_licencia)

    liq_agosto = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-08")
    liq_septiembre = calcular_liquidacion(conn, id_profesional=id_prof, periodo="2026-09")

    # 3 días en agosto (29,30,31) + 4 en septiembre (1,2,3,4) = 7 días totales
    valor_dia = licencia["ValorSemanalAlMomentoDelRegistro"] / 7 * (licencia["PorcentajeBonificacionAplicado"] / 100)
    assert liq_agosto.descuento_licencias == pytest.approx(valor_dia * 3)
    assert liq_septiembre.descuento_licencias == pytest.approx(valor_dia * 4)


def test_ajuste_saldo_atrasado_solo_si_hay_deuda(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaActual=1000)
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.saldo_anterior == 1000
    assert liquidacion.ajuste_saldo_atrasado == pytest.approx(1000 * 3 / 100)  # default 3%

    id_prof2 = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof2, SaldoCuentaActual=-500)  # a favor
    liquidacion2 = calcular_liquidacion(conn, id_profesional=id_prof2, periodo=PERIODO)
    assert liquidacion2.ajuste_saldo_atrasado == 0


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
        conn, id_profesional=id_prof, monto_total=300, cantidad_cuotas=3, mes_ano_inicio="2026-08",
    )
    liquidacion = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion.total_cuotas_plan == pytest.approx(100)

    cuota = obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan, PeriodoImputado=PERIODO)[0]
    marcar_cuota_pagada(conn, cuota["IdCuota"])
    liquidacion_luego_de_pagar = calcular_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    assert liquidacion_luego_de_pagar.total_cuotas_plan == 0


def test_emitir_liquidacion_persiste_y_actualiza_saldo(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaActual=1000)

    id_liquidacion, liquidacion = emitir_liquidacion(
        conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-01",
    )
    registro = obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liquidacion)
    assert registro["Periodo"] == PERIODO
    assert registro["EstadoEnvio"] == "No enviada"

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["SaldoCuentaAnterior"] == pytest.approx(1000)
    assert profesional["SaldoCuentaActual"] == pytest.approx(liquidacion.total)
