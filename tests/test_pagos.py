import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.pagos import (
    crear_cargo_especial,
    crear_plan_pago,
    marcar_cuota_pagada,
    registrar_pago,
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


def test_registrar_pago_descuenta_saldo_actual_sin_tocar_el_anterior(conn, profesional):
    obtener_repositorio(conn, "Profesional").actualizar(profesional, SaldoCuentaAnterior=1000)
    id_pago = registrar_pago(conn, id_profesional=profesional, monto=400, medio_pago="Sobre en buzón")
    assert id_pago is not None

    actualizado = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert actualizado["SaldoCuentaActual"] == pytest.approx(600)
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(1000)


def test_registrar_pago_profesional_inexistente(conn):
    with pytest.raises(ValueError):
        registrar_pago(conn, id_profesional=9999, monto=100)


def test_crear_cargo_especial_capitaliza_concepto(conn, profesional):
    id_cargo = crear_cargo_especial(
        conn, id_profesional=profesional, tipo="Débito", concepto="reintegro de llave", monto=500,
    )
    cargo = obtener_repositorio(conn, "CargoEspecial").obtener(id_cargo)
    assert cargo["Concepto"] == "Reintegro de llave"


def test_crear_cargo_especial_rechaza_tipo_invalido(conn, profesional):
    with pytest.raises(ValueError):
        crear_cargo_especial(conn, id_profesional=profesional, tipo="Otro", concepto="x", monto=100)


def test_crear_cargo_especial_rechaza_monto_no_positivo(conn, profesional):
    with pytest.raises(ValueError):
        crear_cargo_especial(conn, id_profesional=profesional, tipo="Débito", concepto="x", monto=0)


def test_crear_plan_pago_genera_cuotas_consecutivas(conn, profesional):
    id_plan = crear_plan_pago(
        conn, id_profesional=profesional, monto_total=1000, cantidad_cuotas=3, mes_ano_inicio="2026-08",
    )
    cuotas = obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan)
    cuotas = sorted(cuotas, key=lambda c: c["NumeroCuota"])
    assert [c["PeriodoImputado"] for c in cuotas] == ["2026-08", "2026-09", "2026-10"]
    assert sum(c["Monto"] for c in cuotas) == pytest.approx(1000)  # la última absorbe el redondeo


def test_crear_plan_pago_cruza_fin_de_anio(conn, profesional):
    id_plan = crear_plan_pago(
        conn, id_profesional=profesional, monto_total=300, cantidad_cuotas=3, mes_ano_inicio="2026-11",
    )
    cuotas = obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan)
    periodos = sorted(c["PeriodoImputado"] for c in cuotas)
    assert periodos == ["2026-11", "2026-12", "2027-01"]


def test_marcar_cuota_pagada_finaliza_plan_al_pagar_la_ultima(conn, profesional):
    id_plan = crear_plan_pago(
        conn, id_profesional=profesional, monto_total=300, cantidad_cuotas=3, mes_ano_inicio="2026-08",
    )
    cuotas = sorted(
        obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan), key=lambda c: c["NumeroCuota"],
    )

    marcar_cuota_pagada(conn, cuotas[0]["IdCuota"])
    assert obtener_repositorio(conn, "PlanPago").obtener(id_plan)["Estado"] == "Activo"

    marcar_cuota_pagada(conn, cuotas[1]["IdCuota"])
    marcar_cuota_pagada(conn, cuotas[2]["IdCuota"])
    assert obtener_repositorio(conn, "PlanPago").obtener(id_plan)["Estado"] == "Finalizado"
