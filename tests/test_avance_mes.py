import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.avance_mes import avanzar_mes
from app.negocio.lista_espera import crear_pedido, marcar_descartado, marcar_resuelto
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
    id_prof = _crear_profesional(conn, saldo_actual=500, saldo_anterior=999)
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


def _crear_pedido(conn, id_prof, dia="Lunes", fecha_pedido=None):
    return crear_pedido(
        conn, id_profesional=id_prof, tipo_combinacion="O", dias=[dia],
        horario_desde=14, horario_hasta=16, fecha_pedido=fecha_pedido,
    )


def test_lista_espera_elimina_resueltos_y_descartados_siempre(conn):
    id_prof = _crear_profesional(conn, categoria="C")
    id_resuelto = _crear_pedido(conn, id_prof)
    id_descartado = _crear_pedido(conn, id_prof, dia="Martes")
    id_activo = _crear_pedido(conn, id_prof, dia="Miércoles")
    marcar_resuelto(conn, id_resuelto)
    marcar_descartado(conn, id_descartado)

    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")

    assert resumen.pedidos_lista_espera_eliminados == 2
    repo = obtener_repositorio(conn, "ListaEspera")
    assert repo.obtener(id_resuelto) is None
    assert repo.obtener(id_descartado) is None
    assert repo.obtener(id_activo) is not None


def test_lista_espera_conserva_activos_vencidos_por_defecto(conn):
    id_prof = _crear_profesional(conn, categoria="C")
    id_viejo = _crear_pedido(conn, id_prof, fecha_pedido="2015-01-01")

    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")

    assert resumen.pedidos_activos_vencidos_eliminados == 0
    assert obtener_repositorio(conn, "ListaEspera").obtener(id_viejo) is not None


def test_lista_espera_elimina_activos_vencidos_si_se_confirma(conn):
    id_prof = _crear_profesional(conn, categoria="C")
    id_viejo = _crear_pedido(conn, id_prof, fecha_pedido="2015-01-01")
    id_reciente = _crear_pedido(conn, id_prof, dia="Martes", fecha_pedido="2026-01-01")

    resumen = avanzar_mes(conn, periodo_cerrado="2026-08", eliminar_activos_vencidos_lista_espera=True)

    assert resumen.pedidos_activos_vencidos_eliminados == 1
    assert obtener_repositorio(conn, "ListaEspera").obtener(id_viejo) is None
    assert obtener_repositorio(conn, "ListaEspera").obtener(id_reciente) is not None
