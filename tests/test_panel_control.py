from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.balance import resultado_periodo
from app.negocio.panel_control import (
    _proxima_ocurrencia,
    calcular_estadisticas_ocupacion,
    calcular_estadisticas_ocupacion_por_unidad,
    calcular_estadisticas_principales,
    calcular_estadisticas_profesionales,
    cumpleanos_y_dias_profesion_proximos,
    fechas_especiales_proximas_dos_meses,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _fijar_fecha(conn, fecha_iso):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = ? WHERE IdConfiguracion = 1", (fecha_iso,)
    )


# ---------------------------------------- cuadritos informativos (Panel de control)


def _profesional(conn, **kwargs):
    kwargs.setdefault("CategoriaProfesional", "R")
    kwargs.setdefault("Apellido", "Test")
    return obtener_repositorio(conn, "Profesional").crear(**kwargs)


def test_estadisticas_profesionales_sin_datos(conn):
    est = calcular_estadisticas_profesionales(conn)
    assert est.con_plan_pago_vigente == 0
    assert est.con_saldo_fuera_de_tolerancia == 0
    assert est.con_reservas_regulares_activas == 0


def test_estadisticas_profesionales_cuenta_planes_activos_no_finalizados(conn):
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "PlanPago").crear(
        IdProfesional=id_prof, MontoRefinanciado=1000, MontoTotalAPagar=1000, CantidadCuotas=1,
        ImportePorCuota=1000, MesAnoInicio="2026-08", Estado="Activo",
    )
    otro_prof = _profesional(conn)
    obtener_repositorio(conn, "PlanPago").crear(
        IdProfesional=otro_prof, MontoRefinanciado=1000, MontoTotalAPagar=1000, CantidadCuotas=1,
        ImportePorCuota=1000, MesAnoInicio="2026-08", Estado="Finalizado",
    )
    assert calcular_estadisticas_profesionales(conn).con_plan_pago_vigente == 1


def test_estadisticas_profesionales_cuenta_saldo_fuera_de_tolerancia(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=1000)
    _profesional(conn, CategoriaProfesional="R", SaldoCuentaAnterior=5000)
    _profesional(conn, CategoriaProfesional="A", SaldoCuentaAnterior=1)
    assert calcular_estadisticas_profesionales(conn).con_saldo_fuera_de_tolerancia == 2


def test_estadisticas_profesionales_cuenta_reservas_regulares_activas(conn):
    _fijar_fecha(conn, "2026-08-15")
    id_prof = _profesional(conn)
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-01-01",
    )
    otro_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=otro_prof, IdConsultorio=id_consultorio, DiaSemana="Martes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-01-01", VigenciaFin="2026-06-30",
    )
    assert calcular_estadisticas_profesionales(conn).con_reservas_regulares_activas == 1


def test_estadisticas_profesionales_cuenta_aisladas_activas_desde_hoy(conn):
    """"Activas" = confirmadas desde hoy en adelante (inclusive) — una
    aislada ya pasada no cuenta, una futura o de hoy sí."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    _fijar_fecha(conn, "2026-08-15")
    con_futura = _profesional(conn, CategoriaProfesional="A")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=con_futura, IdConsultorio=id_consultorio, Fecha="2026-08-20", HoraInicio=9, HoraFin=11,
    )
    con_pasada = _profesional(conn, CategoriaProfesional="A")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=con_pasada, IdConsultorio=id_consultorio, Fecha="2026-08-10", HoraInicio=9, HoraFin=11,
    )
    assert calcular_estadisticas_profesionales(conn).con_reservas_aisladas_activas == 1


def test_estadisticas_profesionales_horarios_incorporados_proximo_periodo(conn):
    """Una `ReservaRegular` que arranca (`VigenciaInicio`) dentro del mes
    PRÓXIMO es un horario "incorporado" — todavía no pesa en la ocupación
    de este mes, pero sí en la del que viene."""
    _fijar_fecha(conn, "2026-08-15")
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-09-01",
    )
    est = calcular_estadisticas_profesionales(conn)
    assert est.horarios_incorporados_proximo_periodo == pytest.approx(2.0)
    assert est.horarios_liberados_proximo_periodo == pytest.approx(0.0)
    assert est.diferencia_horarios_proximo_periodo == pytest.approx(2.0)


def test_estadisticas_profesionales_horarios_liberados_proximo_periodo(conn):
    """Una `ReservaRegular` que termina (`VigenciaFin`) dentro del mes EN
    CURSO libera ese horario a partir del mes próximo."""
    _fijar_fecha(conn, "2026-08-15")
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=12, VigenciaInicio="2020-01-01", VigenciaFin="2026-08-31",
    )
    est = calcular_estadisticas_profesionales(conn)
    assert est.horarios_incorporados_proximo_periodo == pytest.approx(0.0)
    assert est.horarios_liberados_proximo_periodo == pytest.approx(3.0)
    assert est.diferencia_horarios_proximo_periodo == pytest.approx(-3.0)


def test_estadisticas_ocupacion_sin_datos(conn):
    est = calcular_estadisticas_ocupacion(conn)
    assert est.ocupacion_regular_pct == 0.0
    assert est.horas_regulares_semanales == 0.0
    assert est.horas_aisladas_mes == 0.0


def test_estadisticas_ocupacion_horas_aisladas_solo_cuenta_confirmadas(conn):
    _fijar_fecha(conn, "2026-08-15")
    id_prof = _profesional(conn)
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraAisladaActual=1000,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-10", HoraInicio=9, HoraFin=11,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-11", HoraInicio=9, HoraFin=11,
        Estado="Cancelada",
    )
    est = calcular_estadisticas_ocupacion(conn)
    assert est.horas_aisladas_mes == pytest.approx(2.0)


def test_estadisticas_ocupacion_por_unidad_desglosa_horas_regulares_y_aisladas(conn):
    """Repite los tres conceptos generales por cada Unidad del sistema
    (pedido explícito de la clienta) — una reserva cargada en una Unidad
    no debe aparecer en las estadísticas de la otra."""
    _fijar_fecha(conn, "2026-08-15")
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad_1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="PB")
    id_consultorio_1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_1, NumeroConsultorio=1)
    id_consultorio_2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=2)
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio_1, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2020-01-01",
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio_2, Fecha="2026-08-10", HoraInicio=9, HoraFin=11,
    )
    por_unidad = {u.nombre: u for u in calcular_estadisticas_ocupacion_por_unidad(conn)}
    assert por_unidad["Ramos 1 - 1A"].horas_regulares_semanales == pytest.approx(2.0)
    assert por_unidad["Ramos 1 - 1A"].horas_aisladas_mes == pytest.approx(0.0)
    assert por_unidad["Ramos 1 - PB"].horas_regulares_semanales == pytest.approx(0.0)
    assert por_unidad["Ramos 1 - PB"].horas_aisladas_mes == pytest.approx(2.0)


def test_estadisticas_ocupacion_por_unidad_ordena_pb_antes_que_pisos(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="PB")
    nombres = [u.nombre for u in calcular_estadisticas_ocupacion_por_unidad(conn)]
    assert nombres == ["Ramos 1 - PB", "Ramos 1 - 1A"]


def test_estadisticas_principales_monto_aisladas_y_saldo_pendiente(conn):
    """El monto generado por aisladas (antes vivía en `EstadisticasOcupacion.
    monto_aisladas_mes`) y el saldo pendiente (antes `saldo_pendiente_mes`)
    se mudaron acá, al cuadrito "Estadísticas principales mes en curso" —
    pedido explícito de la clienta, sin duplicarse en "Ocupación y horas"."""
    _fijar_fecha(conn, "2026-08-15")
    id_prof = _profesional(conn)
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraAisladaActual=1000,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-10", HoraInicio=9, HoraFin=11,
    )
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_prof, Periodo="2026-08", MontoGenerado=10000,
    )
    # Monto NEGATIVO: un pago real se guarda así (reduce lo que debe,
    # ver `app.negocio.pagos.registrar_pago`), nunca en positivo.
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_prof, Monto=-4000, PeriodoImputado="2026-08",
    )
    # Pago de otro período no debe afectar el saldo pendiente de agosto.
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_prof, Monto=-1000, PeriodoImputado="2026-07",
    )
    principales = calcular_estadisticas_principales(conn)
    assert principales.monto_aisladas == pytest.approx(2000.0)
    assert principales.total_liquidado == pytest.approx(10000.0)
    assert principales.saldo_pendiente == pytest.approx(6000.0)


def test_estadisticas_principales_total_liquidado_no_duplica_reemisiones(conn):
    """Caso real de la clienta: "estuve haciendo un par de pruebas con las
    emisiones de liquidaciones" dejó varias filas de `LiquidacionEmitida`
    para el mismo profesional/período (cada reemisión crea una fila
    nueva, con el monto TOTAL de esa emisión — ver `emitir_liquidacion`),
    y "Total liquidado" las sumaba todas en vez de quedarse solo con la
    última de cada profesional."""
    _fijar_fecha(conn, "2026-08-15")
    id_prof1 = _profesional(conn)
    id_prof2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    repo_liq = obtener_repositorio(conn, "LiquidacionEmitida")
    repo_liq.crear(IdProfesional=id_prof1, Periodo="2026-08", MontoGenerado=100000, EsReemision=0)
    repo_liq.crear(IdProfesional=id_prof1, Periodo="2026-08", MontoGenerado=150000, EsReemision=1)
    repo_liq.crear(IdProfesional=id_prof1, Periodo="2026-08", MontoGenerado=120000, EsReemision=1)
    repo_liq.crear(IdProfesional=id_prof2, Periodo="2026-08", MontoGenerado=50000, EsReemision=0)
    principales = calcular_estadisticas_principales(conn)
    assert principales.total_liquidado == pytest.approx(170000.0)  # última de prof1 (120000) + prof2 (50000)


def test_desglose_liquidaciones_feriados_vacaciones_aisladas_y_cuotas(conn):
    """Pedido explícito de la clienta: después de preguntar por qué
    "Monto por reservas regulares" + "Monto por reservas aisladas" no
    coincide con "Total liquidado", se agregan estas cuatro líneas de
    desglose (caso real de su propia base: el principal era el
    descuento por feriados). Escenario con los cuatro conceptos a la
    vez, montos verificados contra las mismas fórmulas de `app.negocio.
    liquidaciones.calcular_liquidacion`."""
    from app.negocio.liquidaciones import emitir_liquidacion
    from app.negocio.pagos import crear_plan_pago_historico
    from app.negocio.valores import obtener_porcentaje_descuento
    from app.negocio.vacaciones import crear_vacacion

    _fijar_fecha(conn, "2026-08-15")
    periodo = "2026-08"
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000, ValorHoraAisladaActual=500,
    )
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio="2026-01-01",
    )
    # 17-08-2026 es lunes — feriado nacional ese día.
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-08-17", Descripcion="Feriado de prueba", Tipo="Feriado nacional",
    )
    crear_vacacion(conn, id_profesional=id_prof, fecha_desde="2026-08-03", fecha_hasta="2026-08-09")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-05",
        HoraInicio=9, HoraFin=11, Estado="Confirmada", AplicaRecargo=0,
    )
    crear_plan_pago_historico(
        conn, id_profesional=id_prof, monto_refinanciado=300, cantidad_cuotas=3, mes_ano_inicio=periodo,
    )
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=periodo, fecha_emision="2026-08-20")

    desglose = calcular_estadisticas_principales(conn).desglose_liquidaciones

    descuento_pct = obtener_porcentaje_descuento(conn, 2)
    monto_feriado_esperado = 2 * 1000 * (1 - descuento_pct / 100)
    assert desglose.descuento_feriados == pytest.approx(-monto_feriado_esperado)
    assert desglose.descuento_vacaciones_licencias < 0
    assert desglose.aisladas_en_liquidaciones == pytest.approx(2 * 500)
    assert desglose.cuotas_planes_pago == pytest.approx(100)


def test_desglose_liquidaciones_ignora_profesionales_sin_liquidacion_mensual_propia(conn):
    """Categoría E (se consolida en la liquidación de su R) y categoría B
    (nunca se liquida) no tienen una liquidación propia — `calcular_
    liquidacion` las rechaza con `ValueError`. Una fila de
    `LiquidacionEmitida` con MontoGenerado=0 para una de ellas (como
    deja el sistema real, ver CLAUDE.md "Panel de control: segundo bug
    real...") no puede romper el desglose."""
    _fijar_fecha(conn, "2026-08-15")
    id_prof_e = _profesional(conn, CategoriaProfesional="E")
    obtener_repositorio(conn, "LiquidacionEmitida").crear(IdProfesional=id_prof_e, Periodo="2026-08", MontoGenerado=0)

    desglose = calcular_estadisticas_principales(conn).desglose_liquidaciones

    assert desglose.descuento_feriados == 0.0
    assert desglose.descuento_vacaciones_licencias == 0.0
    assert desglose.aisladas_en_liquidaciones == 0.0
    assert desglose.cuotas_planes_pago == 0.0


def test_estadisticas_principales_saldo_pendiente_no_resta_el_sobrepago_de_un_profesional(conn):
    """Bug real encontrado y arreglado (pedido explícito de la clienta,
    ejemplo dado): total liquidado $10.000 — un profesional debía $500
    y pagó $600 (deja $100 a favor del próximo mes), el otro debía
    $9.500 y no pagó nada. El saldo pendiente tiene que ser $9500, no
    $9400: el sobrepago de uno no puede reducir el saldo pendiente del
    otro, tiene que quedar acotado profesional por profesional."""
    _fijar_fecha(conn, "2026-08-15")
    id_prof_sobrepaga = _profesional(conn, Apellido="Sobrepaga")
    id_prof_debe = _profesional(conn, Apellido="Debe")
    repo_liq = obtener_repositorio(conn, "LiquidacionEmitida")
    repo_liq.crear(IdProfesional=id_prof_sobrepaga, Periodo="2026-08", MontoGenerado=500)
    repo_liq.crear(IdProfesional=id_prof_debe, Periodo="2026-08", MontoGenerado=9500)
    # Monto NEGATIVO: un pago real se guarda así (reduce lo que debe,
    # ver `app.negocio.pagos.registrar_pago`), nunca en positivo.
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_prof_sobrepaga, Monto=-600, PeriodoImputado="2026-08",
    )
    principales = calcular_estadisticas_principales(conn)
    assert principales.total_liquidado == pytest.approx(10000.0)
    assert principales.saldo_pendiente == pytest.approx(9500.0)


def test_estadisticas_principales_saldo_pendiente_un_ajuste_positivo_suma_deuda_del_periodo(conn):
    """Caso real encontrado con la base de datos de la clienta: un
    "ajuste" (`HistorialPagos.EsAjuste`) imputado al período puede ir en
    POSITIVO (un cargo que aumenta lo que debe, ver `app.negocio.pagos.
    registrar_pago`) — a diferencia de un pago real (siempre negativo),
    este sí tiene que SUMAR al saldo pendiente del período, nunca
    restarle."""
    _fijar_fecha(conn, "2026-08-15")
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_prof, Periodo="2026-08", MontoGenerado=1000,
    )
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_prof, Monto=200, PeriodoImputado="2026-08", EsAjuste=1,
    )
    principales = calcular_estadisticas_principales(conn)
    assert principales.saldo_pendiente == pytest.approx(1200.0)


def test_estadisticas_principales_total_ingresos_y_balance_reusan_balance_del_negocio(conn):
    """"Total ingresos"/"Gastos operativos"/"Balance de negocio" son los
    mismos tres valores que ya calcula `app.negocio.balance.resultado_
    periodo` para todo el espacio, sin ningún alcance de ubicación."""
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo="2026-08", Monto=500, Alcance="Espacio general", Concepto="Limpieza",
    )
    principales = calcular_estadisticas_principales(conn)
    ingresos, gastos, balance = resultado_periodo(conn, "2026-08")
    assert principales.total_ingresos == pytest.approx(ingresos)
    assert principales.gastos_operativos == pytest.approx(gastos)
    assert principales.balance_negocio == pytest.approx(balance)


def test_fechas_especiales_proximas_dos_meses_excluye_las_que_ya_pasaron_este_mes(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-01", Tipo="Feriado nacional", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-14", Tipo="Feriado nacional", Activo=1)
    assert fechas_especiales_proximas_dos_meses(conn) == []


def test_fechas_especiales_proximas_dos_meses_incluye_hoy_y_lo_que_falta_del_mes(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-15", Tipo="Feriado nacional", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-31", Tipo="Feriado nacional", Activo=1)
    fechas = fechas_especiales_proximas_dos_meses(conn)
    assert [f["Fecha"] for f in fechas] == ["2026-08-15", "2026-08-31"]


def test_fechas_especiales_proximas_dos_meses_incluye_los_dos_meses_siguientes(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-30", Tipo="Feriado nacional", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-10-31", Tipo="Feriado nacional", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-11-01", Tipo="Feriado nacional", Activo=1)
    fechas = fechas_especiales_proximas_dos_meses(conn)
    assert [f["Fecha"] for f in fechas] == ["2026-09-30", "2026-10-31"]


def test_fechas_especiales_proximas_dos_meses_ignora_inactivas(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-20", Tipo="Feriado nacional", Activo=0)
    assert fechas_especiales_proximas_dos_meses(conn) == []


def test_fechas_especiales_proximas_dos_meses_usa_fecha_real_no_la_del_periodo_operativo(conn):
    """Caso real de la clienta: "Avanzar de mes" hecho con días de
    octubre todavía por delante la deja parada virtualmente en
    noviembre (`PeriodoOperativoActual`) aunque la fecha real de hoy
    (`FechaFicticia` en este test, simulando el reloj real) siga en
    octubre — una fecha especial del 29/10 no tiene que desaparecer
    del cuadrito solo porque el sistema ya está posicionado en el mes
    siguiente para la liquidación."""
    _fijar_fecha(conn, "2026-10-27")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-10-29", Tipo="Feriado nacional", Activo=1)
    conn.execute("UPDATE Configuracion SET PeriodoOperativoActual = '2026-11' WHERE IdConfiguracion = 1")
    fechas = fechas_especiales_proximas_dos_meses(conn)
    assert [f["Fecha"] for f in fechas] == ["2026-10-29"]


# -------------------------------------------------------------------------
# cumpleanos_y_dias_profesion_proximos (pedido explícito de la clienta)
# -------------------------------------------------------------------------


def test_proxima_ocurrencia_dentro_del_mismo_anio(conn):
    assert _proxima_ocurrencia(date(2026, 8, 15), 8, 20) == date(2026, 8, 20)


def test_proxima_ocurrencia_hoy_cuenta_como_proxima(conn):
    assert _proxima_ocurrencia(date(2026, 8, 20), 8, 20) == date(2026, 8, 20)


def test_proxima_ocurrencia_ya_paso_este_anio_salta_al_que_viene(conn):
    assert _proxima_ocurrencia(date(2026, 8, 15), 1, 10) == date(2027, 1, 10)


def test_proxima_ocurrencia_29_de_febrero_salta_al_proximo_bisiesto(conn):
    """2026 y 2027 no son bisiestos — el próximo 29 de febrero recién cae
    en 2028."""
    assert _proxima_ocurrencia(date(2026, 3, 1), 2, 29) == date(2028, 2, 29)


def test_cumpleanos_proximo_de_profesional_activo_aparece(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lo Veci", NombrePila="Virginia", FechaNacimiento="1990-08-20",
    )
    eventos = cumpleanos_y_dias_profesion_proximos(conn)
    assert len(eventos) == 1
    assert eventos[0].descripcion == "Cumpleaños de Virginia Lo Veci"
    assert eventos[0].fecha_proxima == date(2026, 8, 20)
    assert eventos[0].dias_restantes == 5


def test_cumpleanos_de_categoria_x_o_c_no_aparece(conn):
    """"Profesionales activos en el espacio": X (Inactivo) y C (Contacto/
    prospecto) quedan afuera."""
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="X", Apellido="Inactivo", FechaNacimiento="1990-08-20",
    )
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="C", Apellido="Prospecto", FechaNacimiento="1990-08-21",
    )
    assert cumpleanos_y_dias_profesion_proximos(conn) == []


def test_cumpleanos_usa_fecha_real_no_la_del_periodo_operativo(conn):
    """Mismo caso real que en `fechas_especiales_proximas_dos_meses`: un
    "Avanzar de mes" hecho antes de que la fecha real llegara a fin de
    mes no tiene que hacer desaparecer un cumpleaños que todavía no
    pasó en el calendario real."""
    _fijar_fecha(conn, "2026-10-27")
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Test", NombrePila="Ana", FechaNacimiento="1990-10-29",
    )
    conn.execute("UPDATE Configuracion SET PeriodoOperativoActual = '2026-11' WHERE IdConfiguracion = 1")
    eventos = cumpleanos_y_dias_profesion_proximos(conn)
    assert len(eventos) == 1
    assert eventos[0].fecha_proxima == date(2026, 10, 29)


def test_cumpleanos_fuera_de_la_ventana_de_dos_meses_no_aparece(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lejano", FechaNacimiento="1990-12-01",
    )
    assert cumpleanos_y_dias_profesion_proximos(conn) == []


def test_dia_de_profesion_cargado_aparece_con_texto_coloquial(conn):
    """Pedido explícito de la clienta: "prefiero algo más coloquial" —
    usa Profesion.NombreMasculino (ya existente en el catálogo) para
    armar "Día del {NombreMasculino}" en vez del genérico."""
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "Profesion").crear(
        Nombre="Psicología", NombreMasculino="Psicólogo", DiaProfesion="25-08",
    )
    eventos = cumpleanos_y_dias_profesion_proximos(conn)
    assert len(eventos) == 1
    assert eventos[0].descripcion == "Día del Psicólogo"
    assert eventos[0].fecha_proxima == date(2026, 8, 25)


def test_dia_de_profesion_sin_nombre_masculino_usa_el_generico(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "Profesion").crear(Nombre="Psicología", DiaProfesion="25-08")
    eventos = cumpleanos_y_dias_profesion_proximos(conn)
    assert len(eventos) == 1
    assert eventos[0].descripcion == "Día de la profesión: Psicología"


def test_profesion_sin_dia_cargado_no_aparece(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "Profesion").crear(Nombre="Psicología", NombreMasculino="Psicólogo")
    assert cumpleanos_y_dias_profesion_proximos(conn) == []


def test_cumpleanos_y_dias_de_profesion_se_mezclan_ordenados_por_cercania(conn):
    _fijar_fecha(conn, "2026-08-15")
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lejos", FechaNacimiento="1990-09-20",
    )
    obtener_repositorio(conn, "Profesion").crear(
        Nombre="Psicología", NombreMasculino="Psicólogo", DiaProfesion="18-08",
    )
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Cerca", FechaNacimiento="1990-08-16",
    )
    eventos = cumpleanos_y_dias_profesion_proximos(conn)
    assert [e.descripcion for e in eventos] == [
        "Cumpleaños de Cerca",
        "Día del Psicólogo",
        "Cumpleaños de Lejos",
    ]
