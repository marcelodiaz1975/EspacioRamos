import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio
from app.negocio.mensajeria import (
    color_profesional,
    limpiar_plazos_vencidos_o_regularizados,
    marcar_mensaje_aislada_generado,
    marcar_mensaje_previo_generado,
    marcar_recordatorio_mensajeria_generado,
)
from app.negocio.pagos import crear_plan_pago_historico
from app.repositorio.registro import obtener_repositorio

PERIODO = "2026-08"


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    connection.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = ?, ToleranciaDeudaDescuento = 100 "
        "WHERE IdConfiguracion = 1",
        ("2026-08-15",),
    )
    connection.commit()
    yield connection
    connection.close()


def _fijar_fecha(conn, fecha):
    conn.execute("UPDATE Configuracion SET FechaFicticia = ? WHERE IdConfiguracion = 1", (fecha,))
    conn.commit()


def _crear_r(conn, saldo_anterior=0.0, saldo_actual=0.0):
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Test",
        SaldoCuentaAnterior=saldo_anterior, SaldoCuentaActual=saldo_actual,
    )
    return obtener_repositorio(conn, "Profesional").obtener(id_prof)


def _crear_a(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Aislada")
    return obtener_repositorio(conn, "Profesional").obtener(id_prof)


def _dar_reserva_regular_activa(conn, id_profesional):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio="2026-01-01", VigenciaFin=None,
    )


def test_saldo_cero_es_verde(conn):
    p = _crear_r(conn, saldo_anterior=0)
    assert color_profesional(conn, p, PERIODO) == "verde"


def test_saldo_negativo_es_verde(conn):
    p = _crear_r(conn, saldo_anterior=-500)
    assert color_profesional(conn, p, PERIODO) == "verde"


def test_saldo_dentro_de_tolerancia_sin_mensaje_previo_es_marron(conn):
    p = _crear_r(conn, saldo_anterior=1)
    assert color_profesional(conn, p, PERIODO) == "marron"


def test_saldo_dentro_de_tolerancia_con_mensaje_previo_es_amarillo(conn):
    p = _crear_r(conn, saldo_anterior=1)
    marcar_mensaje_previo_generado(conn, p["IdProfesional"], PERIODO)
    assert color_profesional(conn, p, PERIODO) == "amarillo"


def test_saldo_fuera_de_tolerancia_sin_plan_es_naranja(conn):
    p = _crear_r(conn, saldo_anterior=999999)
    assert color_profesional(conn, p, PERIODO) == "naranja"


def test_saldo_fuera_de_tolerancia_con_plan_es_rojo(conn):
    p = _crear_r(conn, saldo_anterior=10000)
    crear_plan_pago_historico(
        conn, id_profesional=p["IdProfesional"], monto_refinanciado=10000,
        cantidad_cuotas=2, mes_ano_inicio=PERIODO,
    )
    assert color_profesional(conn, p, PERIODO) == "rojo"


def test_liquidacion_enviada_es_gris(conn):
    p = _crear_r(conn, saldo_anterior=0)
    id_liq, _ = emitir_liquidacion(conn, id_profesional=p["IdProfesional"], periodo=PERIODO)
    marcar_estado_envio(conn, id_profesional=p["IdProfesional"], periodo=PERIODO, enviada=True)
    assert color_profesional(conn, p, PERIODO) == "gris"


def test_gris_pasa_a_bordo_cerca_de_fin_de_mes_con_reserva_regular_activa(conn):
    p = _crear_r(conn, saldo_anterior=0)
    _dar_reserva_regular_activa(conn, p["IdProfesional"])
    emitir_liquidacion(conn, id_profesional=p["IdProfesional"], periodo=PERIODO)
    marcar_estado_envio(conn, id_profesional=p["IdProfesional"], periodo=PERIODO, enviada=True)
    _fijar_fecha(conn, "2026-08-28")  # a 3 días de fin de mes, default del parámetro = 5
    assert color_profesional(conn, p, PERIODO) == "bordo"


def test_bordo_no_depende_de_deuda_ni_de_plan(conn):
    """Pedido explícito de la clienta al descartar la vieja reactivación a
    rojo: bordó aplica a CUALQUIER profesional R con reserva regular
    activa, aunque tenga deuda y un plan de pago vigente."""
    p = _crear_r(conn, saldo_anterior=0, saldo_actual=10000)
    _dar_reserva_regular_activa(conn, p["IdProfesional"])
    crear_plan_pago_historico(
        conn, id_profesional=p["IdProfesional"], monto_refinanciado=10000,
        cantidad_cuotas=2, mes_ano_inicio=PERIODO,
    )
    emitir_liquidacion(conn, id_profesional=p["IdProfesional"], periodo=PERIODO)
    marcar_estado_envio(conn, id_profesional=p["IdProfesional"], periodo=PERIODO, enviada=True)
    _fijar_fecha(conn, "2026-08-28")
    p = obtener_repositorio(conn, "Profesional").obtener(p["IdProfesional"])
    assert color_profesional(conn, p, PERIODO) == "bordo"


def test_gris_no_pasa_a_bordo_lejos_de_fin_de_mes(conn):
    p = _crear_r(conn, saldo_anterior=0)
    _dar_reserva_regular_activa(conn, p["IdProfesional"])
    emitir_liquidacion(conn, id_profesional=p["IdProfesional"], periodo=PERIODO)
    marcar_estado_envio(conn, id_profesional=p["IdProfesional"], periodo=PERIODO, enviada=True)
    _fijar_fecha(conn, "2026-08-10")  # lejos de fin de mes
    assert color_profesional(conn, p, PERIODO) == "gris"


def test_gris_no_pasa_a_bordo_sin_reserva_regular_activa(conn):
    p = _crear_r(conn, saldo_anterior=0)
    emitir_liquidacion(conn, id_profesional=p["IdProfesional"], periodo=PERIODO)
    marcar_estado_envio(conn, id_profesional=p["IdProfesional"], periodo=PERIODO, enviada=True)
    _fijar_fecha(conn, "2026-08-28")
    assert color_profesional(conn, p, PERIODO) == "gris"


def test_bordo_vuelve_a_gris_tras_generar_el_recordatorio(conn):
    p = _crear_r(conn, saldo_anterior=0)
    _dar_reserva_regular_activa(conn, p["IdProfesional"])
    emitir_liquidacion(conn, id_profesional=p["IdProfesional"], periodo=PERIODO)
    marcar_estado_envio(conn, id_profesional=p["IdProfesional"], periodo=PERIODO, enviada=True)
    _fijar_fecha(conn, "2026-08-28")
    assert color_profesional(conn, p, PERIODO) == "bordo"
    marcar_recordatorio_mensajeria_generado(conn, p["IdProfesional"], PERIODO)
    assert color_profesional(conn, p, PERIODO) == "gris"


def test_plazo_extendido_vigente_con_deuda_es_violeta(conn):
    p = _crear_r(conn, saldo_anterior=10000)
    obtener_repositorio(conn, "Profesional").actualizar(
        p["IdProfesional"], PlazoPagoExtendido="2026-09-01", MotivoPlazoExtra="Se lo prometí",
    )
    p = obtener_repositorio(conn, "Profesional").obtener(p["IdProfesional"])
    assert color_profesional(conn, p, PERIODO) == "violeta"


def test_plazo_extendido_con_saldo_regularizado_no_es_violeta(conn):
    p = _crear_r(conn, saldo_anterior=0)
    obtener_repositorio(conn, "Profesional").actualizar(
        p["IdProfesional"], PlazoPagoExtendido="2026-09-01", MotivoPlazoExtra="Se lo prometí",
    )
    p = obtener_repositorio(conn, "Profesional").obtener(p["IdProfesional"])
    assert color_profesional(conn, p, PERIODO) == "verde"


def test_limpiar_plazos_borra_el_de_saldo_regularizado(conn):
    p = _crear_r(conn, saldo_anterior=0)
    obtener_repositorio(conn, "Profesional").actualizar(
        p["IdProfesional"], PlazoPagoExtendido="2026-09-01", MotivoPlazoExtra="Se lo prometí",
    )
    limpiar_plazos_vencidos_o_regularizados(conn)
    p = obtener_repositorio(conn, "Profesional").obtener(p["IdProfesional"])
    assert p["PlazoPagoExtendido"] is None
    assert p["MotivoPlazoExtra"] is None


def test_limpiar_plazos_borra_el_vencido_aunque_siga_con_deuda(conn):
    p = _crear_r(conn, saldo_anterior=10000)
    obtener_repositorio(conn, "Profesional").actualizar(
        p["IdProfesional"], PlazoPagoExtendido="2026-08-01", MotivoPlazoExtra="Venció",
    )
    limpiar_plazos_vencidos_o_regularizados(conn)
    p = obtener_repositorio(conn, "Profesional").obtener(p["IdProfesional"])
    assert p["PlazoPagoExtendido"] is None
    assert color_profesional(conn, p, PERIODO) == "naranja"


def test_limpiar_plazos_no_toca_el_vigente_con_deuda(conn):
    p = _crear_r(conn, saldo_anterior=10000)
    obtener_repositorio(conn, "Profesional").actualizar(
        p["IdProfesional"], PlazoPagoExtendido="2026-09-01", MotivoPlazoExtra="Vigente",
    )
    limpiar_plazos_vencidos_o_regularizados(conn)
    p = obtener_repositorio(conn, "Profesional").obtener(p["IdProfesional"])
    assert p["PlazoPagoExtendido"] == "2026-09-01"


def test_categoria_a_sin_mensaje_generado_es_celeste(conn):
    p = _crear_a(conn)
    assert color_profesional(conn, p, PERIODO) == "celeste"


def test_categoria_a_con_mensaje_generado_es_azul(conn):
    p = _crear_a(conn)
    marcar_mensaje_aislada_generado(conn, p["IdProfesional"], PERIODO)
    assert color_profesional(conn, p, PERIODO) == "azul"


def test_categoria_no_r_ni_a_no_tiene_color(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="X", Apellido="Inactivo")
    p = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert color_profesional(conn, p, PERIODO) is None
