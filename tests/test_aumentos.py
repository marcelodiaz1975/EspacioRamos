import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.aumentos import (
    confirmar_aumento,
    deshacer_ultimo_aumento,
    detectar_parametros_esquema,
    generar_tramos_esquema,
    simular_aumento,
)
from app.negocio.liquidaciones import emitir_liquidacion
from app.negocio.valores import obtener_porcentaje_descuento
from app.repositorio.registro import obtener_repositorio

VALOR_REGULAR = 1000
VALOR_AISLADA = 500
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
        ValorHoraRegularActual=VALOR_REGULAR, ValorHoraAisladaActual=VALOR_AISLADA,
    )


def test_simular_aumento_calcula_valor_nuevo(conn, consultorio):
    filas = simular_aumento(conn, porcentaje_general=10)
    assert len(filas) == 1
    fila = filas[0]
    assert fila.valor_regular_actual == VALOR_REGULAR
    assert fila.valor_regular_nuevo == pytest.approx(1100)
    assert fila.valor_aislada_nuevo == pytest.approx(550)
    assert fila.diferencia_regular == pytest.approx(100)


def test_simular_aumento_respeta_override_manual(conn, consultorio):
    filas = simular_aumento(
        conn, porcentaje_general=10, valores_override={consultorio: {"regular": 1234}},
    )
    fila = filas[0]
    assert fila.valor_regular_nuevo == pytest.approx(1234)
    assert fila.valor_aislada_nuevo == pytest.approx(550)  # sin override, sigue el % general


def test_confirmar_aumento_congela_anterior_primera_vez(conn, consultorio):
    resumen = confirmar_aumento(conn, porcentaje_general=10, periodo=PERIODO)
    assert resumen.es_correccion_del_mes is False
    assert resumen.consultorios_actualizados == 1

    c = obtener_repositorio(conn, "Consultorio").obtener(consultorio)
    assert c["ValorHoraRegularAnterior"] == pytest.approx(VALOR_REGULAR)
    assert c["ValorHoraRegularActual"] == pytest.approx(1100)
    assert c["ValorHoraAisladaAnterior"] == pytest.approx(VALOR_AISLADA)
    assert c["ValorHoraAisladaActual"] == pytest.approx(550)


def test_confirmar_aumento_correccion_no_vuelve_a_pisar_anterior(conn, consultorio):
    confirmar_aumento(conn, porcentaje_general=10, periodo=PERIODO)  # 1000 -> 1100, Anterior=1000

    resumen = confirmar_aumento(conn, porcentaje_general=20, periodo=PERIODO)  # corrección, mismo mes
    assert resumen.es_correccion_del_mes is True

    c = obtener_repositorio(conn, "Consultorio").obtener(consultorio)
    assert c["ValorHoraRegularAnterior"] == pytest.approx(VALOR_REGULAR)  # sigue siendo el original
    assert c["ValorHoraRegularActual"] == pytest.approx(1200)  # 1000 * 1.20, no compuesto sobre 1100


def test_confirmar_aumento_actualiza_esquema_descuentos(conn, consultorio):
    activos_antes = obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=1)
    assert len(activos_antes) > 0

    confirmar_aumento(
        conn, porcentaje_general=0, periodo=PERIODO,
        nuevo_esquema_descuentos=[(0, 10, 2), (10, 999, 5)],
    )

    activos_despues = obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=1)
    assert len(activos_despues) == 2
    assert {a["PorcentajeDescuento"] for a in activos_despues} == {2, 5}
    inactivos = obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=0)
    assert len(inactivos) == len(activos_antes)


def test_confirmar_aumento_sin_liquidaciones_emitidas_no_regenera_nada(conn, consultorio):
    resumen = confirmar_aumento(conn, porcentaje_general=10, periodo=PERIODO)
    assert resumen.liquidaciones_regeneradas == []


def test_confirmar_aumento_regenera_liquidaciones_ya_emitidas(conn, consultorio):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio="2026-01-01",
    )
    _, liq_original = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-01")

    resumen = confirmar_aumento(conn, porcentaje_general=10, periodo=PERIODO)
    assert resumen.liquidaciones_regeneradas == [id_prof]

    ultima = max(
        obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_prof, Periodo=PERIODO),
        key=lambda f: f["IdLiquidacion"],
    )
    assert ultima["MontoGenerado"] == pytest.approx(liq_original.monto_generado * 1.10)


def test_confirmar_aumento_liquidacion_enviada_pasa_a_regenerada_no_enviada(conn, consultorio):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio="2026-01-01",
    )
    id_liq, _ = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-01")
    obtener_repositorio(conn, "LiquidacionEmitida").actualizar(id_liq, EstadoEnvio="Enviada")

    confirmar_aumento(conn, porcentaje_general=10, periodo=PERIODO)

    ultima = max(
        obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_prof, Periodo=PERIODO),
        key=lambda f: f["IdLiquidacion"],
    )
    assert ultima["EstadoEnvio"] == "Regenerada no enviada"


def test_simular_aumento_respeta_porcentaje_diferencial_por_consultorio(conn, consultorio):
    filas = simular_aumento(
        conn, porcentaje_general=10, porcentajes_override={consultorio: 50},
    )
    fila = filas[0]
    assert fila.valor_regular_nuevo == pytest.approx(1500)
    assert fila.valor_aislada_nuevo == pytest.approx(750)


def test_simular_aumento_redondea_a_multiplo(conn, consultorio):
    filas = simular_aumento(conn, porcentaje_general=13.37, redondear_a=10)
    fila = filas[0]
    assert fila.valor_regular_nuevo == pytest.approx(1130)  # 1133.7 -> más cercano a 1130 que a 1140
    assert fila.valor_aislada_nuevo % 10 == 0


def test_simular_aumento_sin_redondear_a_conserva_centavos(conn, consultorio):
    filas = simular_aumento(conn, porcentaje_general=13.37)
    assert filas[0].valor_regular_nuevo == pytest.approx(1133.7)


def test_simular_aumento_redondeo_no_afecta_valor_override_absoluto(conn, consultorio):
    filas = simular_aumento(
        conn, porcentaje_general=13.37, valores_override={consultorio: {"regular": 1234.56}}, redondear_a=100,
    )
    assert filas[0].valor_regular_nuevo == pytest.approx(1234.56)


def test_confirmar_aumento_aplica_redondeo(conn, consultorio):
    confirmar_aumento(conn, porcentaje_general=13.37, redondear_a=100, periodo=PERIODO)
    c = obtener_repositorio(conn, "Consultorio").obtener(consultorio)
    assert c["ValorHoraRegularActual"] % 100 == 0


def test_confirmar_aumento_aplica_porcentaje_diferencial(conn, consultorio):
    confirmar_aumento(conn, porcentaje_general=10, porcentajes_override={consultorio: 50}, periodo=PERIODO)
    c = obtener_repositorio(conn, "Consultorio").obtener(consultorio)
    assert c["ValorHoraRegularActual"] == pytest.approx(1500)


def test_generar_tramos_esquema_menos_de_dos_horas_es_cero_por_ciento():
    # Corrección explícita de la clienta: de 0 a 2hs (con los parámetros
    # por defecto) es 0%, no 1% como daba la fórmula vieja.
    tramos = generar_tramos_esquema(cantidad_horas=2, porcentaje_descuento=1, porcentaje_tope=25)
    assert tramos[0] == (0, 2, 0)
    assert tramos[1] == (2, 4, 1)
    assert tramos[2] == (4, 6, 2)
    assert tramos[3] == (6, 8, 3)


def test_generar_tramos_esquema_topa_en_el_porcentaje_tope():
    tramos = generar_tramos_esquema(cantidad_horas=2, porcentaje_descuento=1, porcentaje_tope=25)
    assert tramos[-1][2] == 25
    assert all(t[2] <= 25 for t in tramos)


def test_generar_tramos_esquema_respeta_parametros_no_default():
    tramos = generar_tramos_esquema(cantidad_horas=5, porcentaje_descuento=2, porcentaje_tope=10)
    assert tramos[0] == (0, 5, 0)
    assert tramos[1] == (5, 10, 2)
    assert tramos[-1][2] == 10


def test_generar_tramos_esquema_es_coherente_con_obtener_porcentaje_descuento(conn):
    tramos = generar_tramos_esquema(cantidad_horas=2, porcentaje_descuento=1, porcentaje_tope=25)
    from app.negocio.aumentos import actualizar_esquema_descuentos
    actualizar_esquema_descuentos(conn, tramos)
    assert obtener_porcentaje_descuento(conn, 2) == 0
    assert obtener_porcentaje_descuento(conn, 2.5) == 1
    assert obtener_porcentaje_descuento(conn, 4) == 1
    assert obtener_porcentaje_descuento(conn, 4.5) == 2


def test_detectar_parametros_esquema_reconoce_lo_que_genero_el_mismo_formula():
    tramos = generar_tramos_esquema(cantidad_horas=2, porcentaje_descuento=1, porcentaje_tope=25)
    assert detectar_parametros_esquema(tramos) == (2, 1, 25)


def test_detectar_parametros_esquema_reconoce_parametros_no_default():
    tramos = generar_tramos_esquema(cantidad_horas=5, porcentaje_descuento=2, porcentaje_tope=10)
    assert detectar_parametros_esquema(tramos) == (5, 2, 10)


def test_detectar_parametros_esquema_no_reconoce_tramos_libres():
    # Esquema histórico armado a mano (con el editor libre de tramos que existía antes
    # del rediseño): no corresponde a ningún (cantidad_horas, %descuento, %tope).
    tramos = [(0, 10, 2), (10, 999, 5)]
    assert detectar_parametros_esquema(tramos) is None


def test_detectar_parametros_esquema_vacio_devuelve_none():
    assert detectar_parametros_esquema([]) is None


def test_deshacer_sin_aumentos_lanza_error(conn):
    with pytest.raises(ValueError):
        deshacer_ultimo_aumento(conn)


def test_deshacer_ultimo_aumento_restaura_valores_de_consultorio(conn, consultorio):
    confirmar_aumento(conn, porcentaje_general=10, periodo=PERIODO)
    c = obtener_repositorio(conn, "Consultorio").obtener(consultorio)
    assert c["ValorHoraRegularActual"] == pytest.approx(1100)

    resumen = deshacer_ultimo_aumento(conn)
    assert resumen.consultorios_revertidos == 1

    c = obtener_repositorio(conn, "Consultorio").obtener(consultorio)
    assert c["ValorHoraRegularActual"] == pytest.approx(VALOR_REGULAR)
    assert c["ValorHoraRegularAnterior"] == pytest.approx(0)  # no había ningún aumento previo que la congelara
    assert obtener_repositorio(conn, "AumentoAplicado").listar() == []


def test_deshacer_ultimo_aumento_revierte_esquema_y_preserva_lo_anterior(conn, consultorio):
    activos_antes = {a["IdEsquemaDescuento"] for a in obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=1)}
    ids_antes = {a["IdEsquemaDescuento"] for a in obtener_repositorio(conn, "EsquemaDescuentos").listar()}

    confirmar_aumento(
        conn, porcentaje_general=0, periodo=PERIODO,
        nuevo_esquema_descuentos=[(0, 10, 2), (10, 999, 5)],
    )
    ids_nuevos = {
        a["IdEsquemaDescuento"] for a in obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=1)
    } - activos_antes
    assert len(ids_nuevos) == 2

    deshacer_ultimo_aumento(conn)

    activos_despues = {a["IdEsquemaDescuento"] for a in obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=1)}
    assert activos_despues == activos_antes
    # Los tramos que había creado la corrida deshecha no quedan dando vueltas como historial.
    ids_despues = {a["IdEsquemaDescuento"] for a in obtener_repositorio(conn, "EsquemaDescuentos").listar()}
    assert ids_despues == ids_antes


def test_deshacer_ultimo_aumento_revierte_liquidaciones_regeneradas(conn, consultorio):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio="2026-01-01",
    )
    _, liq_original = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-01")

    confirmar_aumento(conn, porcentaje_general=10, periodo=PERIODO)
    resumen = deshacer_ultimo_aumento(conn)
    assert resumen.liquidaciones_regeneradas == [id_prof]

    ultima = max(
        obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_prof, Periodo=PERIODO),
        key=lambda f: f["IdLiquidacion"],
    )
    assert ultima["MontoGenerado"] == pytest.approx(liq_original.monto_generado)
