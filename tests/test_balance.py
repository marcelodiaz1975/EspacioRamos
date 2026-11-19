import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.balance import (
    fuera_de_liquidacion_periodo,
    monto_liquidado_periodo,
    resultado_periodo,
    total_gastos_periodo,
    total_ingresos_periodo,
)
from app.negocio.liquidaciones import emitir_liquidacion
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


def _profesional_con_reserva_lunes(conn, consultorio, horas=2):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=10 + horas, VigenciaInicio="2026-01-01", VigenciaFin=None,
    )
    return id_prof


def test_total_ingresos_periodo_combina_monto_liquidado_y_fuera_de_liquidacion(conn, consultorio):
    """Rediseño completo (pedido explícito de la clienta): "Monto total
    liquidado" ya no se recalcula en vivo desde las reservas (eso vivía
    en `monto_neto_regular_periodo`, de baja en este camino) — es el
    `MontoGenerado` FROZEN de la última emisión de cada profesional
    (`monto_liquidado_periodo`). "Ingresos por fuera de las
    liquidaciones" es lo que generan los profesionales categoría A
    (`fuera_de_liquidacion_periodo`), nunca lo que factura un R fuera de
    la grilla regular — eso ya está dentro de su propia liquidación."""
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-20")
    id_prof_a = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Aislado")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof_a, IdConsultorio=consultorio, Fecha="2026-08-10", HoraInicio=9, HoraFin=11,
    )
    liquidado, fuera = total_ingresos_periodo(conn, PERIODO)
    assert liquidado == pytest.approx(monto_liquidado_periodo(conn, PERIODO))
    assert liquidado == pytest.approx(10000.0)  # 5 lunes de agosto 2026 x 2hs x 1000, liquidación emitida
    assert fuera == pytest.approx(2 * VALOR_HORA_AISLADA)  # 2hs x 500, profesional A, sin liquidación propia


def test_total_ingresos_periodo_no_filtra_por_ubicacion(conn, consultorio):
    """Pedido explícito de la clienta (recomendación elegida): una
    liquidación es por profesional, no se puede partir prolijamente por
    ubicación — `ids_consultorio` queda sin usar para "Monto total
    liquidado"/"Ingresos por fuera de las liquidaciones" (a diferencia
    de Gastos operativos, que sigue prorrateando por ubicación, ver
    `test_total_gastos_periodo_*`)."""
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-20")
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=obtener_repositorio(conn, "Unidad").crear(
            IdEdificio=obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2"), Departamento="1",
        ),
        NumeroConsultorio=1, ValorHoraRegularActual=VALOR_HORA_REGULAR, ValorHoraAisladaActual=VALOR_HORA_AISLADA,
    )
    sin_filtro = total_ingresos_periodo(conn, PERIODO)
    con_otro_consultorio = total_ingresos_periodo(conn, PERIODO, ids_consultorio=[otro_consultorio])
    assert sin_filtro == con_otro_consultorio == (pytest.approx(10000.0), 0.0)


def test_fuera_de_liquidacion_periodo_desglosa_tres_conceptos_y_acota_el_cobrado(conn, consultorio):
    """Profesionales categoría A nunca tienen liquidación propia — todo
    lo que generan en el período queda desglosado en tres conceptos
    separados (pedido explícito de la clienta, tras la pregunta de qué
    incluye cada línea de "Resultado del negocio" en Panel de control):
    aisladas comunes, reservas extraordinarias, y "otros conceptos"
    (llaves + cargos especiales sueltos). `cobrado` queda acotado a no
    superar lo generado por ESE profesional (mismo criterio de tope que
    ya usa `DesgloseLiquidaciones` para los R)."""
    id_prof_a = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Aislado")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof_a, IdConsultorio=consultorio, Fecha="2026-08-05", HoraInicio=9, HoraFin=11,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof_a, IdConsultorio=consultorio, Fecha="2026-08-12", HoraInicio=9, HoraFin=10,
        EsExtraordinaria=1, MontoExtraordinario=3000,
    )
    id_llave = obtener_repositorio(conn, "Llave").crear(Nombre="Llave", Tipo="Unidad", ValorDepositoActual=5000)
    obtener_repositorio(conn, "LlaveMovimiento").crear(
        IdLlave=id_llave, Tipo="Asignación", IdProfesional=id_prof_a, Fecha="2026-08-02",
        DepositoCobrado=1, MontoCobrado=5000,
    )
    # Pago NEGATIVO (reduce lo que debe, ver app.negocio.pagos.registrar_pago):
    # cobra de más y el excedente no puede superar lo generado (1000+3000+5000=9000).
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_prof_a, Monto=-9500, PeriodoImputado=PERIODO,
    )
    fuera = fuera_de_liquidacion_periodo(conn, PERIODO)
    assert fuera.aisladas_normales == pytest.approx(2 * VALOR_HORA_AISLADA)
    assert fuera.reservas_extraordinarias == pytest.approx(3000.0)
    assert fuera.otros_conceptos == pytest.approx(5000.0)
    assert fuera.bruto == pytest.approx(9000.0)
    assert fuera.cobrado == pytest.approx(9000.0)  # acotado, no los 9500 pagados


def test_total_gastos_periodo_incluye_generales_sin_filtro(conn):
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Alquiler", Monto=5000, Alcance="Espacio general",
    )
    assert total_gastos_periodo(conn, PERIODO) == pytest.approx(5000.0)


def _edificio_unidad_consultorio(conn, nombre_edificio, cantidad_consultorios=1, id_localidad=None):
    """Helper de los tests de prorrateo: arma un Edificio con UNA Unidad
    y N Consultorios, devuelve (id_edificio, id_unidad, [ids_consultorio])."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre=nombre_edificio, IdLocalidad=id_localidad)
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1")
    ids_consultorio = [
        obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=n + 1)
        for n in range(cantidad_consultorios)
    ]
    return id_edificio, id_unidad, ids_consultorio


def test_total_gastos_periodo_alcance_consultorio_cuenta_entero_solo_en_ese_consultorio(conn):
    _, _, (cons_a,) = _edificio_unidad_consultorio(conn, "Ramos 1")
    _, _, (cons_b,) = _edificio_unidad_consultorio(conn, "Ramos 2")
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Pintura", Monto=800, Alcance="Consultorio", IdConsultorio=cons_a,
    )
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_a) == pytest.approx(800.0)
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_b) == 0.0


def test_total_gastos_periodo_unidad_se_reparte_en_partes_iguales_entre_sus_consultorios(conn):
    id_edificio, id_unidad, (cons_a, cons_b) = _edificio_unidad_consultorio(conn, "Ramos 1", 2)
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Limpieza", Monto=1000, Alcance="Unidad", IdUnidad=id_unidad,
    )
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_a) == pytest.approx(500.0)
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_b) == pytest.approx(500.0)
    assert total_gastos_periodo(conn, PERIODO, id_edificio=id_edificio) == pytest.approx(1000.0)


def test_total_gastos_periodo_edificio_se_reparte_en_cascada_por_unidad_y_consultorio(conn):
    """Un gasto de Edificio se divide primero por igual entre sus
    Unidades, y lo que le toca a cada Unidad se vuelve a dividir por
    igual entre SUS Consultorios — no es un reparto proporcional al
    total de consultorios del edificio (pedido explícito de la
    clienta)."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad_1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1")
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="2")
    cons_1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_1, NumeroConsultorio=1)
    cons_2a = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1)
    cons_2b = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=2)
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Seguridad", Monto=1200, Alcance="Edificio", IdEdificio=id_edificio,
    )
    # Unidad 1 (1 solo consultorio) se queda con los 600 enteros de su mitad.
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_1) == pytest.approx(600.0)
    assert total_gastos_periodo(conn, PERIODO, id_unidad=id_unidad_1) == pytest.approx(600.0)
    # Unidad 2 (2 consultorios) reparte sus 600 a la mitad entre los dos.
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_2a) == pytest.approx(300.0)
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_2b) == pytest.approx(300.0)
    assert total_gastos_periodo(conn, PERIODO, id_unidad=id_unidad_2) == pytest.approx(600.0)
    assert total_gastos_periodo(conn, PERIODO, id_edificio=id_edificio) == pytest.approx(1200.0)


def test_total_gastos_periodo_espacio_general_se_reparte_en_cascada_completa_por_localidad(conn):
    """Mismo ejemplo que dio la clienta al confirmar el criterio: una
    Localidad con un solo Edificio/Unidad/Consultorio y otra con el
    doble de Edificios terminan absorbiendo la MISMA porción del gasto
    de "Espacio general" por Localidad — aceptado explícitamente como
    desproporcionado frente a la incidencia real de cada una en los
    ingresos."""
    id_loc_chica = obtener_repositorio(conn, "Localidad").crear(Localidad="Chica")
    id_loc_grande = obtener_repositorio(conn, "Localidad").crear(Localidad="Grande")
    _, _, (cons_chica,) = _edificio_unidad_consultorio(conn, "Único", id_localidad=id_loc_chica)
    _, _, (cons_grande_1,) = _edificio_unidad_consultorio(conn, "Grande A", id_localidad=id_loc_grande)
    _, _, (cons_grande_2,) = _edificio_unidad_consultorio(conn, "Grande B", id_localidad=id_loc_grande)
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Publicidad", Monto=4000, Alcance="Espacio general",
    )
    # Cada Localidad se queda con 2000 (4000 / 2 localidades), sin importar
    # que "Grande" tenga el doble de edificios que "Chica".
    assert total_gastos_periodo(conn, PERIODO, id_localidad=id_loc_chica) == pytest.approx(2000.0)
    assert total_gastos_periodo(conn, PERIODO, id_localidad=id_loc_grande) == pytest.approx(2000.0)
    # Dentro de "Chica" el único consultorio se queda con los 2000 enteros.
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_chica) == pytest.approx(2000.0)
    # Dentro de "Grande" los 2000 se reparten a la mitad entre sus dos edificios.
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_grande_1) == pytest.approx(1000.0)
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_grande_2) == pytest.approx(1000.0)
    # Sin ningún filtro, se suma el gasto entero, sin prorratear nada.
    assert total_gastos_periodo(conn, PERIODO) == pytest.approx(4000.0)


def test_total_gastos_periodo_alcance_localidad_se_reparte_en_cascada_acotada_a_esa_localidad(conn):
    """Pedido explícito de la clienta: un gasto de Localidad arranca la
    misma cascada que "Espacio general" (reparto en partes iguales por
    Edificio, Unidad, Consultorio), pero UN ESCALÓN más abajo — nunca
    toca a otra Localidad."""
    id_loc = obtener_repositorio(conn, "Localidad").crear(Localidad="Ramos Mejía")
    otra_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Otra")
    _, _, (cons_a,) = _edificio_unidad_consultorio(conn, "Ramos 1", id_localidad=id_loc)
    _, _, (cons_b,) = _edificio_unidad_consultorio(conn, "Ramos 2", id_localidad=id_loc)
    _, _, (cons_otra,) = _edificio_unidad_consultorio(conn, "Otro edificio", id_localidad=otra_localidad)
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Publicidad", Monto=2000, Alcance="Localidad", IdLocalidad=id_loc,
    )
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_a) == pytest.approx(1000.0)
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_b) == pytest.approx(1000.0)
    assert total_gastos_periodo(conn, PERIODO, id_consultorio=cons_otra) == 0.0
    assert total_gastos_periodo(conn, PERIODO, id_localidad=id_loc) == pytest.approx(2000.0)
    assert total_gastos_periodo(conn, PERIODO, id_localidad=otra_localidad) == 0.0
    # Sin ningún filtro, se suma el gasto entero, sin prorratear nada.
    assert total_gastos_periodo(conn, PERIODO) == pytest.approx(2000.0)


def test_total_gastos_periodo_rama_sin_hijos_no_reparte_nada(conn):
    """Un Edificio cargado sin ninguna Unidad todavía: la porción que le
    tocaría no llega a ningún Consultorio (se pierde) — consistente con
    que esa rama tampoco puede generar ningún Ingreso."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Sin unidades")
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Seguridad", Monto=500, Alcance="Edificio", IdEdificio=id_edificio,
    )
    assert total_gastos_periodo(conn, PERIODO, id_edificio=id_edificio) == 0.0


def test_resultado_periodo_es_ingresos_menos_gastos(conn, consultorio):
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-20")
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Alquiler", Monto=3000, Alcance="Espacio general",
    )
    ingresos, gastos, resultado = resultado_periodo(conn, PERIODO)
    assert ingresos == pytest.approx(10000.0)
    assert gastos == pytest.approx(3000.0)
    assert resultado == pytest.approx(7000.0)


def test_resultado_periodo_con_filtro_puntual_ingresos_no_cambian_pero_gastos_si(conn, consultorio):
    """Los ingresos (liquidado + fuera de liquidación) ya no filtran por
    ubicación (pedido explícito de la clienta) — solo Gastos operativos
    sigue prorrateando por el alcance elegido (acá el consultorio de la
    fixture es el único del sistema, así que se queda con el gasto
    general entero)."""
    id_prof = _profesional_con_reserva_lunes(conn, consultorio, horas=2)
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO, fecha_emision="2026-08-20")
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo=PERIODO, Categoria="Alquiler", Monto=3000, Alcance="Espacio general",
    )
    ingresos, gastos, resultado = resultado_periodo(conn, PERIODO, id_consultorio=consultorio)
    assert ingresos == pytest.approx(10000.0)
    assert gastos == pytest.approx(3000.0)
    assert resultado == pytest.approx(7000.0)
