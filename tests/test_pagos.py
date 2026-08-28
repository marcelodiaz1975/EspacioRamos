import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.dias import periodo_actual
from app.negocio.pagos import (
    abrir_tanda_sobres,
    cancelar_plan,
    cerrar_tanda_sobres,
    crear_cargo_especial,
    crear_plan_pago,
    cuotas_pendientes_plan,
    deshacer_ultimo_pago,
    eliminar_pago,
    marcar_cuota_pagada,
    modificar_pago,
    plan_activo_de,
    refinanciar_plan,
    registrar_pago,
    subtotal_tanda_sobres,
    tanda_sobres_abierta,
    tanda_sobres_es_de_otro_dia,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def profesional(conn):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lo Veci", SaldoCuentaActual=1000,
    )


def test_registrar_pago_sin_periodo_descuenta_saldo_actual(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=1000)
    id_pago, cruza_tolerancia = registrar_pago(conn, id_profesional=profesional, monto=-400, medio_pago="Sobre en buzón")
    assert id_pago is not None
    assert cruza_tolerancia is False

    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(600)
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(1000)


def test_registrar_pago_imputado_a_mes_anterior_descuenta_saldo_anterior(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=1000)
    # hoy (fecha real de sistema) cae en 2026-08 en este entorno de test
    registrar_pago(conn, id_profesional=profesional, monto=-400, periodo_imputado="2026-07")

    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(600)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(1000)  # sin tocar


def test_registrar_pago_rechaza_mas_de_un_mes_atras(conn, profesional):
    """Un pago puede corregir a lo sumo el mes inmediatamente anterior —
    más atrás que eso obligaría a reabrir más de una liquidación ya
    cerrada (confirmado por la clienta)."""
    with pytest.raises(ValueError):
        registrar_pago(conn, id_profesional=profesional, monto=-400, periodo_imputado="2026-06")


def test_registrar_pago_cruza_tolerancia_al_regularizar_mes_anterior(conn, profesional):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=100)
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=1000)
    # paga 950: saldo pasa de 1000 (por encima de 100) a 50 (dentro de tolerancia) -> cruza
    _id, cruza = registrar_pago(conn, id_profesional=profesional, monto=-950, periodo_imputado="2026-07")
    assert cruza is True


def test_registrar_pago_no_cruza_tolerancia_si_ya_estaba_dentro(conn, profesional):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=100)
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=50)
    _id, cruza = registrar_pago(conn, id_profesional=profesional, monto=-10, periodo_imputado="2026-07")
    assert cruza is False


def test_registrar_pago_no_cruza_tolerancia_si_sigue_endeudado(conn, profesional):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=100)
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=1000)
    _id, cruza = registrar_pago(conn, id_profesional=profesional, monto=-200, periodo_imputado="2026-07")
    assert cruza is False


def test_registrar_pago_no_cruza_tolerancia_si_imputa_a_mes_en_curso(conn, profesional):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=100)
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=1000)
    _id, cruza = registrar_pago(conn, id_profesional=profesional, monto=-950)  # sin periodo_imputado
    assert cruza is False


def test_registrar_pago_positivo_suma_al_saldo(conn, profesional):
    """Un monto positivo es un cargo (aumenta lo que debe), no un pago."""
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaActual=100)
    registrar_pago(conn, id_profesional=profesional, monto=250)
    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(350)


def test_registrar_pago_default_fecha_a_hoy(conn, profesional):
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-100)
    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["Fecha"] is not None


def test_registrar_pago_guarda_saldo_anterior_y_nuevo(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaActual=1000)
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-400)
    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["SaldoAnterior"] == pytest.approx(1000)
    assert pago["SaldoNuevo"] == pytest.approx(600)
    assert pago["RegistroModificado"] == 0


# --------------------------------------------------------------- modificar / deshacer

def test_modificar_pago_ajusta_monto_y_marca_modificado(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaActual=1000)
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-400)  # saldo: 600

    modificar_pago(conn, id_pago, monto=-600)  # se corrige a -600: saldo debería quedar en 400

    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(400)
    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["Monto"] == pytest.approx(-600)
    assert pago["RegistroModificado"] == 1
    assert pago["SaldoAnterior"] == pytest.approx(1000)
    assert pago["SaldoNuevo"] == pytest.approx(400)


def test_modificar_pago_mantiene_fecha_de_carga_original(conn, profesional):
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-100)
    fecha_carga_original = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)["FechaHoraCarga"]

    modificar_pago(conn, id_pago, monto=-150)

    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["FechaHoraCarga"] == fecha_carga_original


def test_modificar_pago_reimputa_a_otro_periodo(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaActual=1000, SaldoCuentaAnterior=500)
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-100)  # contra el mes en curso

    modificar_pago(conn, id_pago, periodo_imputado="2026-07")  # se corrige: era del mes anterior

    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(1000)  # revertido
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(400)  # aplicado ahí


def test_modificar_pago_inexistente_rechaza(conn):
    with pytest.raises(ValueError):
        modificar_pago(conn, 9999, monto=-100)


def test_deshacer_ultimo_pago_revierte_saldo_y_borra(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaActual=1000)
    registrar_pago(conn, id_profesional=profesional, monto=-300)
    id_pago_2, _ = registrar_pago(conn, id_profesional=profesional, monto=-200)  # saldo: 500

    deshecho = deshacer_ultimo_pago(conn)

    assert deshecho["IdPago"] == id_pago_2
    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(700)  # el segundo pago revertido, el primero queda
    assert obtener_repositorio(conn, "HistorialPagos").obtener(id_pago_2) is None


def test_deshacer_ultimo_pago_sin_movimientos_rechaza(conn):
    with pytest.raises(ValueError):
        deshacer_ultimo_pago(conn)


def test_eliminar_pago_arbitrario_revierte_saldo_y_borra(conn, profesional):
    """A diferencia de `deshacer_ultimo_pago` (siempre el de IdPago más
    alto), `eliminar_pago` puede revertir cualquiera de los pagos
    cargados, no solo el último."""
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaActual=1000)
    id_pago_1, _ = registrar_pago(conn, id_profesional=profesional, monto=-300)
    registrar_pago(conn, id_profesional=profesional, monto=-200)  # saldo: 500

    eliminado = eliminar_pago(conn, id_pago_1)

    assert eliminado["IdPago"] == id_pago_1
    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(800)  # el primer pago revertido, el segundo queda
    assert obtener_repositorio(conn, "HistorialPagos").obtener(id_pago_1) is None


def test_eliminar_pago_inexistente_rechaza(conn):
    with pytest.raises(ValueError):
        eliminar_pago(conn, 9999)


def test_registrar_pago_profesional_inexistente(conn):
    with pytest.raises(ValueError):
        registrar_pago(conn, id_profesional=9999, monto=100)


def test_crear_cargo_especial_capitaliza_concepto(conn, profesional):
    id_cargo = crear_cargo_especial(
        conn, id_profesional=profesional, tipo="Débito", concepto="reintegro de llave", monto=500,
        periodo_imputado=periodo_actual(conn),
    )
    cargo = obtener_repositorio(conn, "CargoEspecial").obtener(id_cargo)
    assert cargo["Concepto"] == "Reintegro de llave"


def test_crear_cargo_especial_completa_la_fecha_sola(conn, profesional):
    id_cargo = crear_cargo_especial(
        conn, id_profesional=profesional, tipo="Débito", concepto="x", monto=100,
        periodo_imputado=periodo_actual(conn),
    )
    cargo = obtener_repositorio(conn, "CargoEspecial").obtener(id_cargo)
    assert cargo["Fecha"] is not None


def test_crear_cargo_especial_rechaza_tipo_invalido(conn, profesional):
    with pytest.raises(ValueError):
        crear_cargo_especial(
            conn, id_profesional=profesional, tipo="Otro", concepto="x", monto=100,
            periodo_imputado=periodo_actual(conn),
        )


def test_crear_cargo_especial_rechaza_periodo_en_blanco(conn, profesional):
    with pytest.raises(ValueError):
        crear_cargo_especial(conn, id_profesional=profesional, tipo="Débito", concepto="x", monto=100, periodo_imputado="")


def test_crear_cargo_especial_rechaza_periodo_anterior(conn, profesional):
    with pytest.raises(ValueError):
        crear_cargo_especial(
            conn, id_profesional=profesional, tipo="Débito", concepto="x", monto=100,
            periodo_imputado="2000-01",
        )


def test_crear_cargo_especial_debito_rechaza_monto_no_positivo(conn, profesional):
    with pytest.raises(ValueError):
        crear_cargo_especial(
            conn, id_profesional=profesional, tipo="Débito", concepto="x", monto=0,
            periodo_imputado=periodo_actual(conn),
        )


def test_crear_cargo_especial_credito_rechaza_monto_positivo(conn, profesional):
    """El monto de un Crédito tiene que cargarse en negativo — Tipo queda
    como una validación cruzada de ese signo (confirmado por la clienta)."""
    with pytest.raises(ValueError):
        crear_cargo_especial(
            conn, id_profesional=profesional, tipo="Crédito", concepto="x", monto=100,
            periodo_imputado=periodo_actual(conn),
        )


def test_crear_cargo_especial_credito_acepta_monto_negativo(conn, profesional):
    id_cargo = crear_cargo_especial(
        conn, id_profesional=profesional, tipo="Crédito", concepto="x", monto=-100,
        periodo_imputado=periodo_actual(conn),
    )
    cargo = obtener_repositorio(conn, "CargoEspecial").obtener(id_cargo)
    assert cargo["Monto"] == -100


def _fijar_periodo_actual(conn, periodo):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = ? WHERE IdConfiguracion = 1",
        (f"{periodo}-15",),
    )


def test_crear_plan_pago_sin_interes_genera_cuotas_iguales(conn, profesional):
    _fijar_periodo_actual(conn, "2026-08")
    id_plan = crear_plan_pago(conn, id_profesional=profesional, monto_refinanciado=1000, cantidad_cuotas=3)
    plan = obtener_repositorio(conn, "PlanPago").obtener(id_plan)
    assert plan["MontoTotalAPagar"] == pytest.approx(1000)
    assert plan["ImportePorCuota"] == pytest.approx(333.33)
    assert plan["MesAnoInicio"] == "2026-08"

    cuotas = sorted(obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan), key=lambda c: c["NumeroCuota"])
    assert [c["PeriodoImputado"] for c in cuotas] == ["2026-08", "2026-09", "2026-10"]
    assert [c["Estado"] for c in cuotas] == ["Pendiente", "Pendiente", "Pendiente"]
    assert sum(c["Monto"] for c in cuotas) == pytest.approx(1000)  # la última absorbe el redondeo


def test_crear_plan_pago_descuenta_saldo_anterior(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=1500)
    crear_plan_pago(conn, id_profesional=profesional, monto_refinanciado=1000, cantidad_cuotas=3)
    profesional_actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert profesional_actualizado["SaldoCuentaAnterior"] == pytest.approx(500)


def test_crear_plan_pago_con_interes_simple(conn, profesional):
    # 1000 refinanciado, 5% mensual, 4 cuotas -> total = 1000*(1+0.05*4) = 1200
    id_plan = crear_plan_pago(
        conn, id_profesional=profesional, monto_refinanciado=1000, cantidad_cuotas=4,
        porcentaje_interes_mensual=5,
    )
    plan = obtener_repositorio(conn, "PlanPago").obtener(id_plan)
    assert plan["MontoTotalAPagar"] == pytest.approx(1200)
    assert plan["ImportePorCuota"] == pytest.approx(300)


def test_crear_plan_pago_cruza_fin_de_anio(conn, profesional):
    _fijar_periodo_actual(conn, "2026-11")
    id_plan = crear_plan_pago(conn, id_profesional=profesional, monto_refinanciado=300, cantidad_cuotas=3)
    cuotas = obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan)
    periodos = sorted(c["PeriodoImputado"] for c in cuotas)
    assert periodos == ["2026-11", "2026-12", "2027-01"]


def test_crear_plan_pago_rechaza_dos_activos_a_la_vez(conn, profesional):
    crear_plan_pago(conn, id_profesional=profesional, monto_refinanciado=300, cantidad_cuotas=3)
    with pytest.raises(ValueError):
        crear_plan_pago(conn, id_profesional=profesional, monto_refinanciado=100, cantidad_cuotas=2)


def test_marcar_cuota_pagada_finaliza_plan_al_pagar_la_ultima(conn, profesional):
    id_plan = crear_plan_pago(conn, id_profesional=profesional, monto_refinanciado=300, cantidad_cuotas=3)
    cuotas = sorted(
        obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan), key=lambda c: c["NumeroCuota"],
    )

    marcar_cuota_pagada(conn, cuotas[0]["IdCuota"])
    assert obtener_repositorio(conn, "PlanPago").obtener(id_plan)["Estado"] == "Activo"
    assert obtener_repositorio(conn, "CuotaPlan").obtener(cuotas[0]["IdCuota"])["Estado"] == "Pagada"

    marcar_cuota_pagada(conn, cuotas[1]["IdCuota"])
    marcar_cuota_pagada(conn, cuotas[2]["IdCuota"])
    assert obtener_repositorio(conn, "PlanPago").obtener(id_plan)["Estado"] == "Finalizado"


def test_cuotas_pendientes_plan_excluye_las_ya_cerradas(conn, profesional):
    """`avance_mes._cerrar_cuotas` es lo único que marca una cuota como
    definitivamente cobrada (Estado="Cerrada", al cerrar el mes al que
    estaba imputada) — `marcar_cuota_pagada` es un dato aparte (Pagado)
    que no usa este cálculo, porque hoy nada de la pantalla lo dispara."""
    id_plan = crear_plan_pago(conn, id_profesional=profesional, monto_refinanciado=300, cantidad_cuotas=3)
    cuotas = sorted(obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan), key=lambda c: c["NumeroCuota"])
    assert cuotas_pendientes_plan(conn, id_plan) == pytest.approx(300)

    obtener_repositorio(conn, "CuotaPlan").actualizar(cuotas[0]["IdCuota"], Estado="Cerrada")
    assert cuotas_pendientes_plan(conn, id_plan) == pytest.approx(200)


def test_cancelar_plan_suma_cuotas_pendientes_al_saldo_anterior(conn, profesional):
    # arranca en 300 (el saldo atrasado que se usa para armar el plan de abajo);
    # crear_plan_pago ya lo descuenta a 0, así que "vuelve a ser atrasado" se ve directo
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=300)
    id_plan = crear_plan_pago(conn, id_profesional=profesional, monto_refinanciado=300, cantidad_cuotas=3)
    cuotas = sorted(obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan), key=lambda c: c["NumeroCuota"])
    obtener_repositorio(conn, "CuotaPlan").actualizar(cuotas[0]["IdCuota"], Estado="Cerrada")  # 100 ya cerrados

    cancelar_plan(conn, id_plan)

    assert obtener_repositorio(conn, "PlanPago").obtener(id_plan)["Estado"] == "Cancelado"
    profesional_actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert profesional_actualizado["SaldoCuentaAnterior"] == pytest.approx(200)


def test_refinanciar_plan_cancela_el_vigente_y_descuenta_del_saldo_anterior(conn, profesional):
    # arranca en 300 (el saldo atrasado que se usa para armar el plan viejo);
    # crear_plan_pago ya lo descuenta a 0, que es el punto de partida del comentario de abajo
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=300)
    id_plan_viejo = crear_plan_pago(conn, id_profesional=profesional, monto_refinanciado=300, cantidad_cuotas=3)

    id_plan_nuevo = refinanciar_plan(
        conn, id_profesional=profesional, monto_a_refinanciar=250, cantidad_cuotas=5,
    )

    assert obtener_repositorio(conn, "PlanPago").obtener(id_plan_viejo)["Estado"] == "Cancelado"
    plan_nuevo = obtener_repositorio(conn, "PlanPago").obtener(id_plan_nuevo)
    assert plan_nuevo["EsRefinanciacion"] == 1
    assert plan_nuevo["IdPlanAnterior"] == id_plan_viejo
    assert plan_nuevo["MontoRefinanciado"] == pytest.approx(250)

    # saldo atrasado: 0 (viejo cancelado, +300 de cuotas pendientes) - 250 (al plan nuevo) = 50
    profesional_actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert profesional_actualizado["SaldoCuentaAnterior"] == pytest.approx(50)


def test_refinanciar_plan_sin_plan_activo_rechaza(conn, profesional):
    with pytest.raises(ValueError):
        refinanciar_plan(conn, id_profesional=profesional, monto_a_refinanciar=250, cantidad_cuotas=5)


def test_plan_activo_de(conn, profesional):
    assert plan_activo_de(conn, profesional) is None
    id_plan = crear_plan_pago(conn, id_profesional=profesional, monto_refinanciado=300, cantidad_cuotas=3)
    assert plan_activo_de(conn, profesional)["IdPlan"] == id_plan
    cancelar_plan(conn, id_plan)
    assert plan_activo_de(conn, profesional) is None


# --------------------------------------------------------------- tanda de sobres

def test_no_hay_tanda_abierta_por_defecto(conn):
    assert tanda_sobres_abierta(conn) is None


def test_abrir_y_cerrar_tanda(conn):
    apertura = abrir_tanda_sobres(conn)
    assert tanda_sobres_abierta(conn) == apertura
    cerrar_tanda_sobres(conn)
    assert tanda_sobres_abierta(conn) is None


def test_subtotal_tanda_suma_solo_pagos_por_sobre_de_esa_tanda(conn, profesional):
    apertura = abrir_tanda_sobres(conn)
    registrar_pago(
        conn, id_profesional=profesional, monto=1000, medio_pago="Sobre en buzón",
        fecha_hora_apertura_buzon=apertura,
    )
    registrar_pago(
        conn, id_profesional=profesional, monto=500, medio_pago="Sobre en buzón",
        fecha_hora_apertura_buzon=apertura,
    )
    # pago por otro medio, y pago por sobre de una tanda anterior: no deben sumar
    registrar_pago(conn, id_profesional=profesional, monto=999, medio_pago="Transferencia")
    registrar_pago(
        conn, id_profesional=profesional, monto=999, medio_pago="Sobre en buzón",
        fecha_hora_apertura_buzon="2020-01-01T00:00:00",
    )

    assert subtotal_tanda_sobres(conn, apertura) == pytest.approx(1500)


def test_tanda_sobres_es_de_otro_dia(conn):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    assert tanda_sobres_es_de_otro_dia(conn) is False  # sin tanda abierta

    obtener_repositorio(conn, "Configuracion").actualizar(
        1, TandaSobresAbierta=1, TandaSobresApertura="2026-08-14T18:00:00",
    )
    assert tanda_sobres_es_de_otro_dia(conn) is True

    obtener_repositorio(conn, "Configuracion").actualizar(1, TandaSobresApertura="2026-08-15T09:00:00")
    assert tanda_sobres_es_de_otro_dia(conn) is False
