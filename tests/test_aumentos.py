import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.aumentos import confirmar_aumento, simular_aumento
from app.negocio.liquidaciones import emitir_liquidacion
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
