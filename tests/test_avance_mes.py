import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.avance_mes import avanzar_mes, revertir_ajuste_saldo_atrasado
from app.negocio.pagos import crear_plan_pago
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_profesional(conn, categoria="R", saldo_actual=0.0, saldo_anterior=0.0):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional=categoria, Apellido="Lo Veci",
        SaldoCuentaActual=saldo_actual, SaldoCuentaAnterior=saldo_anterior,
    )


def test_traspaso_de_saldo(conn):
    # categoría A: no le aplica el ajuste por saldo atrasado, aísla el paso 2
    id_prof = _crear_profesional(conn, categoria="A", saldo_actual=500, saldo_anterior=999)
    avanzar_mes(conn, periodo_cerrado="2026-08")
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["SaldoCuentaAnterior"] == pytest.approx(500)
    assert profesional["SaldoCuentaActual"] == 0


def test_cierre_de_cuotas_marca_cerrada_pagas_e_impagas(conn):
    id_prof = _crear_profesional(conn)
    id_plan = crear_plan_pago(
        conn, id_profesional=id_prof, monto_refinanciado=300, cantidad_cuotas=3, mes_ano_inicio="2026-08",
    )
    cuotas = sorted(obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan), key=lambda c: c["NumeroCuota"])
    obtener_repositorio(conn, "CuotaPlan").actualizar(cuotas[0]["IdCuota"], Pagado=1, Estado="Pagada")

    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")

    cuota_agosto = obtener_repositorio(conn, "CuotaPlan").obtener(cuotas[0]["IdCuota"])
    assert cuota_agosto["Estado"] == "Cerrada"
    assert cuota_agosto["Pagado"] == 1  # no se pierde que estaba pagada
    assert resumen.cuotas_cerradas == 1  # solo la de agosto, no las de sept/oct


def test_plan_se_finaliza_si_todas_las_cuotas_quedan_cerradas(conn):
    id_prof = _crear_profesional(conn)
    id_plan = crear_plan_pago(
        conn, id_profesional=id_prof, monto_refinanciado=100, cantidad_cuotas=1, mes_ano_inicio="2026-08",
    )
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")
    assert id_plan in resumen.planes_finalizados
    assert obtener_repositorio(conn, "PlanPago").obtener(id_plan)["Estado"] == "Finalizado"


def test_plan_no_se_finaliza_si_quedan_cuotas_futuras(conn):
    id_prof = _crear_profesional(conn)
    id_plan = crear_plan_pago(
        conn, id_profesional=id_prof, monto_refinanciado=300, cantidad_cuotas=3, mes_ano_inicio="2026-08",
    )
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")
    assert id_plan not in resumen.planes_finalizados
    assert obtener_repositorio(conn, "PlanPago").obtener(id_plan)["Estado"] == "Activo"


def test_ajuste_por_saldo_atrasado_por_encima_de_tolerancia(conn):
    id_prof = _crear_profesional(conn, categoria="R", saldo_actual=1000)
    # tolerancia por defecto 0, PorcentajeAjusteSaldoAtrasado por defecto 3%
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")

    assert len(resumen.profesionales_con_ajuste) == 1
    assert resumen.profesionales_con_ajuste[0]["id_profesional"] == id_prof
    assert resumen.profesionales_con_ajuste[0]["ajuste"] == pytest.approx(30)

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["SaldoCuentaAnterior"] == pytest.approx(1030)


def test_ajuste_no_aplica_dentro_de_tolerancia(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=2000)
    id_prof = _crear_profesional(conn, categoria="R", saldo_actual=1000)
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")

    assert resumen.profesionales_con_ajuste == []
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["SaldoCuentaAnterior"] == pytest.approx(1000)


def test_ajuste_no_aplica_a_saldo_a_favor(conn):
    id_prof = _crear_profesional(conn, categoria="R", saldo_actual=-500)
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")
    assert resumen.profesionales_con_ajuste == []
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["SaldoCuentaAnterior"] == pytest.approx(-500)


def test_ajuste_no_aplica_a_categoria_distinta_de_r(conn):
    id_prof = _crear_profesional(conn, categoria="A", saldo_actual=1000)
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")
    assert resumen.profesionales_con_ajuste == []


def test_revertir_ajuste_saldo_atrasado(conn):
    id_prof = _crear_profesional(conn, categoria="R", saldo_actual=1000)
    avanzar_mes(conn, periodo_cerrado="2026-08")
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["SaldoCuentaAnterior"] == pytest.approx(1030)

    revertir_ajuste_saldo_atrasado(conn, id_prof, 30)
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["SaldoCuentaAnterior"] == pytest.approx(1000)
