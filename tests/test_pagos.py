import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.dias import periodo_actual, sumar_meses
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
    resolver_profesional_para_cargo,
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
    _fijar_periodo_actual(conn, "2026-08")  # "hoy" fijo, para que "2026-07" sea el mes inmediato anterior
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
    _fijar_periodo_actual(conn, "2026-08")  # "hoy" fijo, para que "2026-07" sea el mes inmediato anterior
    # paga 950: saldo pasa de 1000 (por encima de 100) a 50 (dentro de tolerancia) -> cruza
    _id, cruza = registrar_pago(conn, id_profesional=profesional, monto=-950, periodo_imputado="2026-07")
    assert cruza is True


def test_registrar_pago_no_cruza_tolerancia_si_ya_estaba_dentro(conn, profesional):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=100)
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=50)
    _fijar_periodo_actual(conn, "2026-08")  # "hoy" fijo, para que "2026-07" sea el mes inmediato anterior
    _id, cruza = registrar_pago(conn, id_profesional=profesional, monto=-10, periodo_imputado="2026-07")
    assert cruza is False


def test_registrar_pago_no_cruza_tolerancia_si_sigue_endeudado(conn, profesional):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=100)
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=1000)
    _fijar_periodo_actual(conn, "2026-08")  # "hoy" fijo, para que "2026-07" sea el mes inmediato anterior
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


def test_registrar_pago_saldo_antes_y_despues_combina_los_dos_periodos(conn, profesional):
    """Pedido explícito de la clienta ("Saldo antes del pago"/"Saldo
    después del pago"): acá "SaldoAnterior"/"SaldoNuevo" de HistorialPagos
    pasan a representar el COMBINADO de SaldoCuentaAnterior +
    SaldoCuentaActual, no un solo campo según a qué período se imputa el
    pago — reproduce el caso real de Lic. Gabriela Icutza que trajo la
    clienta: $81.236 de saldo anterior + $277.292 que le acreditó la
    liquidación del mes, pagó $70.000 imputados al mes en curso."""
    obtener_repositorio(conn, "Profesional").actualizar(
        profesional, SaldoCuentaAnterior=81236, SaldoCuentaActual=277292,
    )
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-70000)
    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["SaldoAnterior"] == pytest.approx(81236 + 277292)
    assert pago["SaldoNuevo"] == pytest.approx(81236 + 277292 - 70000)


def test_registrar_pago_de_un_a_usa_el_calculo_en_vivo_no_el_bucket_crudo(conn):
    """Bug real reportado por la clienta (caso A19 Marcela La Regina, ver
    CLAUDE.md): para categoría A nada acredita nunca el bucket crudo
    `SaldoCuentaActual` (no hay liquidación mensual propia) — el snapshot
    "Saldo antes del pago" que guarda HistorialPagos sumaba ese bucket
    crudo (obsoleto, normalmente $0) en vez del cálculo en vivo
    (`movimiento_periodo_aislada`, el mismo que usa Centro de
    mensajería)."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="PB")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraAisladaActual=163540,
    )
    id_a = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="A", Apellido="La Regina", SaldoCuentaActual=0, SaldoCuentaAnterior=0,
    )
    periodo = periodo_actual(conn)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_a, IdConsultorio=id_consultorio, Fecha=f"{periodo}-10",
        HoraInicio=10, HoraFin=11, Estado="Confirmada", AplicaRecargo=0,
    )

    id_pago, _ = registrar_pago(conn, id_profesional=id_a, monto=-163540, periodo_imputado=periodo)

    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["SaldoAnterior"] == pytest.approx(163540)
    assert pago["SaldoNuevo"] == pytest.approx(0)


def test_modificar_pago_de_un_a_usa_el_calculo_en_vivo_no_el_bucket_crudo(conn):
    """Mismo bug que el anterior, al MODIFICAR un pago: revertir el
    impacto en los campos crudos (antes de recalcular) no alcanza para
    que "Saldo antes de este pago" excluya la versión VIEJA de este
    mismo pago, porque para un A el combinado se recalcula en vivo desde
    HistorialPagos — esa fila sigue en la tabla con su Monto viejo hasta
    el final de `modificar_pago`."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="PB")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraAisladaActual=163540,
    )
    id_a = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="A", Apellido="La Regina", SaldoCuentaActual=0, SaldoCuentaAnterior=0,
    )
    periodo = periodo_actual(conn)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_a, IdConsultorio=id_consultorio, Fecha=f"{periodo}-10",
        HoraInicio=10, HoraFin=11, Estado="Confirmada", AplicaRecargo=0,
    )
    id_pago, _ = registrar_pago(conn, id_profesional=id_a, monto=-100000, periodo_imputado=periodo)

    modificar_pago(conn, id_pago, monto=-163540)

    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["SaldoAnterior"] == pytest.approx(163540)
    assert pago["SaldoNuevo"] == pytest.approx(0)


def test_registrar_pago_saldo_antes_del_pago_encadena_con_el_despues_del_pago_anterior(conn, profesional):
    """"Si en el mes se realiza un nuevo pago, 'Saldo antes del pago' va a
    mostrar el último 'Saldo después del pago' de ese mes" — sale solo de
    leer los dos campos en vivo en cada registro, sin encadenar a mano."""
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=500, SaldoCuentaActual=1000)
    id_pago_1, _ = registrar_pago(conn, id_profesional=profesional, monto=-300)
    id_pago_2, _ = registrar_pago(conn, id_profesional=profesional, monto=-200)

    repo_pagos = obtener_repositorio(conn, "HistorialPagos")
    pago_1 = repo_pagos.obtener(id_pago_1)
    pago_2 = repo_pagos.obtener(id_pago_2)
    assert pago_1["SaldoNuevo"] == pytest.approx(pago_2["SaldoAnterior"])
    assert pago_2["SaldoAnterior"] == pytest.approx(1500 - 300)
    assert pago_2["SaldoNuevo"] == pytest.approx(1500 - 300 - 200)


def test_registrar_pago_que_cubre_de_mas_el_periodo_imputado_tambien_combina_correctamente(conn, profesional):
    """El combinado tiene que cambiar en exactamente `monto`, incluso
    cuando el pago deja en crédito el campo al que se imputa — no hace
    falta ningún caso especial, ni repartir nada con el otro período
    (ver `_aplicar_pago`): el crédito en el campo imputado ya se refleja
    en "Saldo actual" (combinado) sin tocar "Saldo anterior"."""
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=1000, SaldoCuentaActual=2000)
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-3500)  # cubre el actual, sobran 500
    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["SaldoAnterior"] == pytest.approx(3000)
    assert pago["SaldoNuevo"] == pytest.approx(-500)


# --------------------------------------------------------------- un solo campo por pago (sin cascada)
#
# La cascada que repartía un pago entre los dos períodos cuando cubría
# de más el campo imputado (ver una ronda anterior) se retiró: "Saldo
# actual" pasa a MOSTRARSE siempre combinado (`saldo_actual_mostrado`),
# así que mezclar los dos campos guardados ya no hace falta y, peor,
# terminaba destruyendo la separación real entre "lo que se arrastra de
# antes" y "lo que pasó este período" — bug real reportado por la
# clienta con el caso de Vanesa Moreno (ver CLAUDE.md). Un pago/cargo
# siempre toca UN SOLO campo, el que decide `_campo_saldo` según
# `periodo_imputado`, sin importar cuánto sobre o falte.

def test_registrar_pago_que_supera_el_saldo_actual_no_toca_el_anterior(conn, profesional):
    """Escenario real reportado: un profesional debe 1000 del período
    anterior y 2000 del actual; paga 3500 (cubre el actual y le quedan
    500 de más) imputando el pago al período actual (el default del
    formulario) — el sobrante queda como crédito en SaldoCuentaActual,
    SaldoCuentaAnterior no se toca (el combinado, "Saldo actual" en
    pantalla, ya refleja ese crédito sumado a la deuda anterior)."""
    obtener_repositorio(conn, "Profesional").actualizar(
        profesional, SaldoCuentaAnterior=1000, SaldoCuentaActual=2000,
    )
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-3500)

    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(1000)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(-1500)

    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["ImpactoSaldoAnterior"] == pytest.approx(0)
    assert pago["ImpactoSaldoActual"] == pytest.approx(-3500)


def test_registrar_pago_que_no_supera_el_saldo_actual_no_toca_el_anterior(conn, profesional):
    """Un pago normal, que no se pasa del saldo al que se imputa, tampoco
    toca el otro período."""
    obtener_repositorio(conn, "Profesional").actualizar(
        profesional, SaldoCuentaAnterior=1000, SaldoCuentaActual=2000,
    )
    registrar_pago(conn, id_profesional=profesional, monto=-500)

    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(1000)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(1500)


def test_registrar_pago_que_supera_el_saldo_anterior_no_toca_el_actual(conn, profesional):
    """Simétrico: un pago imputado al período anterior que alcanza a
    cubrir por completo esa deuda deja el crédito en SaldoCuentaAnterior
    sin tocar SaldoCuentaActual."""
    obtener_repositorio(conn, "Profesional").actualizar(
        profesional, SaldoCuentaAnterior=500, SaldoCuentaActual=300,
    )
    _fijar_periodo_actual(conn, "2026-08")
    registrar_pago(conn, id_profesional=profesional, monto=-900, periodo_imputado="2026-07")

    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(-400)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(300)


def test_cargo_positivo_no_toca_el_otro_campo_aunque_este_en_credito(conn, profesional):
    """Un cargo (monto positivo) nunca toca el otro campo, ni siquiera si
    ya está en crédito."""
    obtener_repositorio(conn, "Profesional").actualizar(
        profesional, SaldoCuentaAnterior=-300, SaldoCuentaActual=100,
    )
    registrar_pago(conn, id_profesional=profesional, monto=250, es_ajuste=True)

    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(-300)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(350)


def test_eliminar_pago_revierte_el_unico_campo_tocado(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(
        profesional, SaldoCuentaAnterior=1000, SaldoCuentaActual=2000,
    )
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-3500)  # anterior: 1000, actual: -1500

    eliminado = eliminar_pago(conn, id_pago)

    assert eliminado["IdPago"] == id_pago
    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(1000)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(2000)


def test_modificar_pago_revierte_el_viejo_y_aplica_el_nuevo_sobre_el_mismo_campo(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(
        profesional, SaldoCuentaAnterior=1000, SaldoCuentaActual=2000,
    )
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-3500)  # anterior: 1000, actual: -1500

    modificar_pago(conn, id_pago, monto=-3000)  # revierte el -3500 y aplica -3000, siempre sobre el actual

    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(1000)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(-1000)
    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["ImpactoSaldoAnterior"] == pytest.approx(0)
    assert pago["ImpactoSaldoActual"] == pytest.approx(-3000)


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


def test_modificar_pago_saldo_antes_y_despues_combina_los_dos_periodos(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=500, SaldoCuentaActual=1000)
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-400)  # combinado: 1500 -> 1100

    modificar_pago(conn, id_pago, monto=-600)  # combinado antes de este pago sigue siendo 1500 (se revierte el viejo)

    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["SaldoAnterior"] == pytest.approx(1500)
    assert pago["SaldoNuevo"] == pytest.approx(900)


def test_modificar_pago_mantiene_fecha_de_carga_original(conn, profesional):
    id_pago, _ = registrar_pago(conn, id_profesional=profesional, monto=-100)
    fecha_carga_original = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)["FechaHoraCarga"]

    modificar_pago(conn, id_pago, monto=-150)

    pago = obtener_repositorio(conn, "HistorialPagos").obtener(id_pago)
    assert pago["FechaHoraCarga"] == fecha_carga_original


def test_modificar_pago_reimputa_a_otro_periodo(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaActual=1000, SaldoCuentaAnterior=500)
    _fijar_periodo_actual(conn, "2026-08")  # "hoy" fijo, para que "2026-07" sea el mes inmediato anterior
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


def test_crear_cargo_especial_acepta_el_mes_que_viene(conn, profesional):
    """Pedido explícito de la clienta: "solo se puede agendar para el mes
    en curso o el que viene"."""
    id_cargo = crear_cargo_especial(
        conn, id_profesional=profesional, tipo="Débito", concepto="x", monto=100,
        periodo_imputado=sumar_meses(periodo_actual(conn), 1),
    )
    cargo = obtener_repositorio(conn, "CargoEspecial").obtener(id_cargo)
    assert cargo["PeriodoImputado"] == sumar_meses(periodo_actual(conn), 1)


def test_crear_cargo_especial_rechaza_mas_de_un_mes_adelante(conn, profesional):
    with pytest.raises(ValueError):
        crear_cargo_especial(
            conn, id_profesional=profesional, tipo="Débito", concepto="x", monto=100,
            periodo_imputado=sumar_meses(periodo_actual(conn), 2),
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


def test_crear_cargo_especial_sin_subtipo_cae_a_item_libre(conn, profesional):
    """#42: mismo default que la columna en la base — ningún llamador de
    antes de este pedido necesitó actualizarse."""
    id_cargo = crear_cargo_especial(
        conn, id_profesional=profesional, tipo="Débito", concepto="x", monto=100,
        periodo_imputado=periodo_actual(conn),
    )
    cargo = obtener_repositorio(conn, "CargoEspecial").obtener(id_cargo)
    assert cargo["Subtipo"] == "Ítem libre"


def test_crear_cargo_especial_acepta_ajuste_y_bonificacion(conn, profesional):
    id_ajuste = crear_cargo_especial(
        conn, id_profesional=profesional, tipo="Débito", concepto="x", monto=100,
        periodo_imputado=periodo_actual(conn), subtipo="Ajuste",
    )
    id_bonificacion = crear_cargo_especial(
        conn, id_profesional=profesional, tipo="Crédito", concepto="y", monto=-50,
        periodo_imputado=periodo_actual(conn), subtipo="Bonificación",
    )
    repo = obtener_repositorio(conn, "CargoEspecial")
    assert repo.obtener(id_ajuste)["Subtipo"] == "Ajuste"
    assert repo.obtener(id_bonificacion)["Subtipo"] == "Bonificación"


def test_crear_cargo_especial_rechaza_subtipo_invalido(conn, profesional):
    with pytest.raises(ValueError):
        crear_cargo_especial(
            conn, id_profesional=profesional, tipo="Débito", concepto="x", monto=100,
            periodo_imputado=periodo_actual(conn), subtipo="Otro",
        )


def test_crear_cargo_especial_rechaza_deposito_de_llave_sin_id_llave(conn, profesional):
    """"Depósito de llave" es estructural — solo se deriva de `id_llave`,
    nunca una elección directa del operador."""
    with pytest.raises(ValueError):
        crear_cargo_especial(
            conn, id_profesional=profesional, tipo="Débito", concepto="x", monto=100,
            periodo_imputado=periodo_actual(conn), subtipo="Depósito de llave",
        )


def test_crear_cargo_especial_con_id_llave_fuerza_deposito_de_llave_sin_importar_subtipo(conn, profesional):
    """Si viene `id_llave`, el Subtipo es "Depósito de llave" siempre,
    aunque se pase otro valor (o ninguno) — no es una elección del
    operador, se deriva solo."""
    id_llave = obtener_repositorio(conn, "Llave").crear(ValorDepositoActual=5000)
    id_cargo = crear_cargo_especial(
        conn, id_profesional=profesional, tipo="Débito", concepto="depósito", monto=100,
        periodo_imputado=periodo_actual(conn), subtipo="Ajuste", id_llave=id_llave,
    )
    cargo = obtener_repositorio(conn, "CargoEspecial").obtener(id_cargo)
    assert cargo["Subtipo"] == "Depósito de llave"


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


# --- resolver_profesional_para_cargo / categorías B, E, C (confirmado por la clienta) ---

def _crear_profesional(conn, **kwargs):
    kwargs.setdefault("Apellido", "Lo Veci")
    return obtener_repositorio(conn, "Profesional").crear(**kwargs)


def test_resolver_profesional_para_cargo_r_a_x_a_si_mismos(conn):
    for categoria in ("R", "A", "X"):
        id_prof = _crear_profesional(conn, CategoriaProfesional=categoria)
        assert resolver_profesional_para_cargo(conn, id_prof) == id_prof


def test_resolver_profesional_para_cargo_e_redirige_al_cabeza_de_equipo(conn):
    id_r = _crear_profesional(conn, CategoriaProfesional="R")
    id_e = _crear_profesional(conn, CategoriaProfesional="E", ProfesionalCabezaEquipo=id_r)
    assert resolver_profesional_para_cargo(conn, id_e) == id_r


def test_resolver_profesional_para_cargo_e_sin_cabeza_rechaza(conn):
    id_e = _crear_profesional(conn, CategoriaProfesional="E")
    with pytest.raises(ValueError):
        resolver_profesional_para_cargo(conn, id_e)


def test_resolver_profesional_para_cargo_e_con_cabeza_que_no_es_r_rechaza(conn):
    id_a = _crear_profesional(conn, CategoriaProfesional="A")
    id_e = _crear_profesional(conn, CategoriaProfesional="E", ProfesionalCabezaEquipo=id_a)
    with pytest.raises(ValueError):
        resolver_profesional_para_cargo(conn, id_e)


def test_resolver_profesional_para_cargo_b_rechaza(conn):
    id_b = _crear_profesional(conn, CategoriaProfesional="B")
    with pytest.raises(ValueError):
        resolver_profesional_para_cargo(conn, id_b)


def test_resolver_profesional_para_cargo_c_rechaza(conn):
    id_c = _crear_profesional(conn, CategoriaProfesional="C")
    with pytest.raises(ValueError):
        resolver_profesional_para_cargo(conn, id_c)


def test_resolver_profesional_para_cargo_inexistente_rechaza(conn):
    with pytest.raises(ValueError):
        resolver_profesional_para_cargo(conn, 9999)


def test_registrar_pago_a_un_e_se_imputa_al_cabeza_de_equipo(conn):
    id_r = _crear_profesional(conn, CategoriaProfesional="R", SaldoCuentaActual=0)
    id_e = _crear_profesional(conn, CategoriaProfesional="E", ProfesionalCabezaEquipo=id_r)

    registrar_pago(conn, id_profesional=id_e, monto=500)

    repo = obtener_repositorio(conn, "Profesional")
    assert repo.obtener(id_r)["SaldoCuentaActual"] == pytest.approx(500)
    assert repo.obtener(id_e)["SaldoCuentaActual"] == pytest.approx(0)
    assert obtener_repositorio(conn, "HistorialPagos").listar()[0]["IdProfesional"] == id_r


def test_registrar_pago_a_un_b_rechaza(conn):
    id_b = _crear_profesional(conn, CategoriaProfesional="B")
    with pytest.raises(ValueError):
        registrar_pago(conn, id_profesional=id_b, monto=500)


def test_crear_cargo_especial_a_un_e_se_imputa_al_cabeza_de_equipo(conn):
    id_r = _crear_profesional(conn, CategoriaProfesional="R")
    id_e = _crear_profesional(conn, CategoriaProfesional="E", ProfesionalCabezaEquipo=id_r)

    id_cargo = crear_cargo_especial(
        conn, id_profesional=id_e, tipo="Débito", concepto="x", monto=100, periodo_imputado=periodo_actual(conn),
    )

    assert obtener_repositorio(conn, "CargoEspecial").obtener(id_cargo)["IdProfesional"] == id_r


def test_crear_cargo_especial_a_un_b_rechaza(conn):
    id_b = _crear_profesional(conn, CategoriaProfesional="B")
    with pytest.raises(ValueError):
        crear_cargo_especial(
            conn, id_profesional=id_b, tipo="Débito", concepto="x", monto=100,
            periodo_imputado=periodo_actual(conn),
        )


def test_crear_cargo_especial_a_un_c_rechaza(conn):
    id_c = _crear_profesional(conn, CategoriaProfesional="C")
    with pytest.raises(ValueError):
        crear_cargo_especial(
            conn, id_profesional=id_c, tipo="Débito", concepto="x", monto=100,
            periodo_imputado=periodo_actual(conn),
        )


