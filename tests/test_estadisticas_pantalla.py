"""Funciones de app.negocio.estadisticas que arman las dos solapas de la
pantalla Estadísticas (Historial general / Estadísticas varias) — ver el
docstring del módulo para el detalle de cada decisión de la clienta."""
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.estadisticas import (
    FilaEstadistica,
    _ids_consultorio_del_alcance,
    _periodo_mas_antiguo_con_datos,
    _periodos_para_filtro,
    conteo_entidades,
    estadisticas_varias,
    generar_snapshot,
    historial_general,
    horas_regulares_semanales_promedio,
    monto_bruto_aislada_periodo,
    monto_bruto_regular_periodo,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def fecha_actual_agosto_2026(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, ModoFechaFicticia=1, FechaFicticia="2026-08-15",
    )
    conn.commit()


@pytest.fixture
def localidad_edificio_unidad_consultorio(conn):
    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Vicente López")
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", IdLocalidad=id_localidad)
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000, ValorHoraAisladaActual=1500,
    )
    conn.commit()
    return id_localidad, id_edificio, id_unidad, id_consultorio


def _profesional(conn):
    return obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Test")


# ------------------------------------------------------ horas semanales


def test_horas_regulares_semanales_promedio_sin_reservas_es_cero(conn):
    assert horas_regulares_semanales_promedio(conn, 2026, 8) == 0.0


def test_horas_regulares_semanales_promedio_pondera_por_dias_segun_vigencia(conn, localidad_edificio_unidad_consultorio):
    """Ejemplo textual de la clienta: 30hs reservadas la primera quincena
    de un mes de 30 días, se liberan 10hs y quedan 20 la segunda
    quincena -> promedio del mes = 25hs. Se arma con 3 reservas de 10hs
    cada una, dos de ellas vigentes todo el mes y una tercera que se da
    de baja (VigenciaFin) justo a mitad de mes."""
    _, _, _, id_consultorio = localidad_edificio_unidad_consultorio
    id_prof = _profesional(conn)
    repo = obtener_repositorio(conn, "ReservaRegular")
    for _ in range(2):
        repo.crear(
            IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
            HoraInicio=9, HoraFin=19, VigenciaInicio="2026-01-01",
        )
    repo.crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Martes",
        HoraInicio=9, HoraFin=19, VigenciaInicio="2026-01-01", VigenciaFin="2026-08-15",
    )
    conn.commit()

    promedio = horas_regulares_semanales_promedio(conn, 2026, 8)
    # Agosto 2026 tiene 31 días: 15 días con 30hs (hasta el 15 inclusive) +
    # 16 días con 20hs.
    esperado = (15 * 30 + 16 * 20) / 31
    assert promedio == pytest.approx(esperado)


def test_horas_regulares_semanales_promedio_filtra_por_consultorio(conn, localidad_edificio_unidad_consultorio):
    _, id_edificio, id_unidad, id_consultorio = localidad_edificio_unidad_consultorio
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=2)
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=otro_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=19, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    assert horas_regulares_semanales_promedio(conn, 2026, 8, [id_consultorio]) == 0.0
    assert horas_regulares_semanales_promedio(conn, 2026, 8, [otro_consultorio]) == pytest.approx(10.0)


def test_horas_regulares_semanales_promedio_lista_vacia_es_cero(conn, localidad_edificio_unidad_consultorio):
    assert horas_regulares_semanales_promedio(conn, 2026, 8, []) == 0.0


# ---------------------------------------------------------------- montos


def test_monto_bruto_regular_periodo_a_valores_vigentes(conn, localidad_edificio_unidad_consultorio):
    _, _, _, id_consultorio = localidad_edificio_unidad_consultorio
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    # Agosto 2026: lunes 3, 10, 17, 24, 31 -> 5 lunes.
    monto = monto_bruto_regular_periodo(conn, 2026, 8)
    assert monto == pytest.approx(5 * 2 * 1000)


def test_monto_bruto_aislada_periodo_solo_confirmadas(conn, localidad_edificio_unidad_consultorio):
    _, _, _, id_consultorio = localidad_edificio_unidad_consultorio
    id_prof = _profesional(conn)
    repo = obtener_repositorio(conn, "ReservaAislada")
    repo.crear(IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-10", HoraInicio=9, HoraFin=11)
    repo.crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-11", HoraInicio=9, HoraFin=11,
        Estado="Cancelada",
    )
    conn.commit()

    assert monto_bruto_aislada_periodo(conn, 2026, 8) == pytest.approx(2 * 1500)


def test_montos_lista_vacia_de_consultorios_es_cero(conn, localidad_edificio_unidad_consultorio):
    assert monto_bruto_regular_periodo(conn, 2026, 8, []) == 0.0
    assert monto_bruto_aislada_periodo(conn, 2026, 8, []) == 0.0


# --------------------------------------------------------------- alcance


def test_ids_consultorio_del_alcance_ninguno_es_todo_el_sistema(conn):
    assert _ids_consultorio_del_alcance(conn) is None


def test_ids_consultorio_del_alcance_consultorio_manda_sobre_el_resto(conn, localidad_edificio_unidad_consultorio):
    id_localidad, id_edificio, id_unidad, id_consultorio = localidad_edificio_unidad_consultorio
    ids = _ids_consultorio_del_alcance(
        conn, id_localidad=id_localidad, id_edificio=id_edificio, id_unidad=id_unidad, id_consultorio=id_consultorio,
    )
    assert ids == [id_consultorio]


def test_ids_consultorio_del_alcance_por_unidad(conn, localidad_edificio_unidad_consultorio):
    _, _, id_unidad, id_consultorio = localidad_edificio_unidad_consultorio
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=2)
    ids = _ids_consultorio_del_alcance(conn, id_unidad=id_unidad)
    assert sorted(ids) == sorted([id_consultorio, otro_consultorio])


def test_ids_consultorio_del_alcance_por_edificio_y_por_localidad(conn, localidad_edificio_unidad_consultorio):
    id_localidad, id_edificio, _, id_consultorio = localidad_edificio_unidad_consultorio
    assert _ids_consultorio_del_alcance(conn, id_edificio=id_edificio) == [id_consultorio]
    assert _ids_consultorio_del_alcance(conn, id_localidad=id_localidad) == [id_consultorio]


def test_conteo_entidades_sin_alcance_es_todo_el_sistema(conn, localidad_edificio_unidad_consultorio):
    assert conteo_entidades(conn) == (1, 1, 1, 1)


def test_conteo_entidades_por_cada_nivel_de_alcance(conn, localidad_edificio_unidad_consultorio):
    id_localidad, id_edificio, id_unidad, id_consultorio = localidad_edificio_unidad_consultorio
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=2)

    assert conteo_entidades(conn, id_consultorio=id_consultorio) == (1, 1, 1, 1)
    assert conteo_entidades(conn, id_unidad=id_unidad) == (1, 1, 1, 2)
    assert conteo_entidades(conn, id_edificio=id_edificio) == (1, 1, 1, 2)
    assert conteo_entidades(conn, id_localidad=id_localidad) == (1, 1, 1, 2)


# --------------------------------------------------------------- períodos


def test_periodo_mas_antiguo_sin_datos_es_el_actual(conn, fecha_actual_agosto_2026):
    assert _periodo_mas_antiguo_con_datos(conn) == "2026-08"


def test_periodo_mas_antiguo_con_datos_toma_el_minimo_entre_regulares_y_aisladas(
    conn, localidad_edificio_unidad_consultorio,
):
    _, _, _, id_consultorio = localidad_edificio_unidad_consultorio
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-03-01",
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-01-10", HoraInicio=9, HoraFin=11,
    )
    conn.commit()
    assert _periodo_mas_antiguo_con_datos(conn) == "2026-01"


def test_periodos_para_filtro_anio_y_mes_puntual(conn, fecha_actual_agosto_2026):
    assert _periodos_para_filtro(conn, anio=2026, mes=3) == ["2026-03"]
    assert _periodos_para_filtro(conn, anio=2030, mes=3) == []  # futuro: nada que mostrar


def test_periodos_para_filtro_solo_anio_no_pasa_del_mes_actual(conn, fecha_actual_agosto_2026):
    periodos = _periodos_para_filtro(conn, anio=2026, mes=None)
    assert periodos == [f"2026-{m:02d}" for m in range(8, 0, -1)]


def test_periodos_para_filtro_anio_pasado_trae_los_doce_meses(conn, fecha_actual_agosto_2026):
    periodos = _periodos_para_filtro(conn, anio=2025, mes=None)
    assert periodos == [f"2025-{m:02d}" for m in range(12, 0, -1)]


def test_periodos_para_filtro_sin_nada_va_desde_el_primer_dato_hasta_hoy(
    conn, fecha_actual_agosto_2026, localidad_edificio_unidad_consultorio,
):
    _, _, _, id_consultorio = localidad_edificio_unidad_consultorio
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-06-01",
    )
    conn.commit()
    assert _periodos_para_filtro(conn, anio=None, mes=None) == ["2026-08", "2026-07", "2026-06"]


# ------------------------------------------------------- historial general


def test_historial_general_por_mes_incluye_el_mes_en_curso_en_vivo(conn, fecha_actual_agosto_2026):
    filas = historial_general(conn, por_anio=False)
    assert len(filas) == 1
    assert filas[0].periodo == "2026-08"
    assert filas[0].ocupacion_pct == 0.0


def test_historial_general_por_mes_ordena_del_mas_nuevo_al_mas_viejo(conn, fecha_actual_agosto_2026):
    generar_snapshot(conn, "2026-06")
    generar_snapshot(conn, "2026-07")
    conn.commit()
    filas = historial_general(conn, por_anio=False)
    assert [f.periodo for f in filas] == ["2026-08", "2026-07", "2026-06"]


def test_historial_general_snapshot_viejo_sin_horas_ni_montos_queda_en_blanco(conn, fecha_actual_agosto_2026):
    """Un snapshot generado antes de esta revisión no tiene las columnas
    nuevas cargadas -- se documenta como límite aceptado, no se
    recalcula por fuera de lo guardado."""
    obtener_repositorio(conn, "SnapshotMensual").crear(
        Periodo="2026-07", FechaGeneracion="2026-08-01T00:00:00", PorcentajeOcupacionGeneral=50.0,
    )
    conn.commit()
    filas = historial_general(conn, por_anio=False)
    fila_julio = next(f for f in filas if f.periodo == "2026-07")
    assert fila_julio.horas_regulares_semanales is None
    assert fila_julio.monto_total is None


def test_historial_general_variacion_horas_contra_periodo_anterior(conn, fecha_actual_agosto_2026, localidad_edificio_unidad_consultorio):
    _, _, _, id_consultorio = localidad_edificio_unidad_consultorio
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=19, VigenciaInicio="2026-01-01",
    )
    conn.commit()
    generar_snapshot(conn, "2026-07")
    conn.commit()

    filas = historial_general(conn, por_anio=False)
    fila_agosto = next(f for f in filas if f.periodo == "2026-08")
    fila_julio = next(f for f in filas if f.periodo == "2026-07")
    assert fila_agosto.variacion_horas == pytest.approx(fila_agosto.horas_regulares_semanales - fila_julio.horas_regulares_semanales)
    assert fila_agosto.variacion_horas == pytest.approx(0.0)


def test_historial_general_por_anio_promedia_ocupacion_y_suma_montos(conn, fecha_actual_agosto_2026, localidad_edificio_unidad_consultorio):
    generar_snapshot(conn, "2026-06", porcentaje_aumento_aplicado=None)
    conn.commit()
    obtener_repositorio(conn, "SnapshotMensual").actualizar(
        obtener_repositorio(conn, "SnapshotMensual").listar()[0]["IdSnapshot"],
        PorcentajeOcupacionGeneral=20.0, MontoHorasRegulares=1000.0, MontoHorasAisladas=100.0,
    )
    generar_snapshot(conn, "2026-07")
    conn.commit()
    obtener_repositorio(conn, "SnapshotMensual").actualizar(
        obtener_repositorio(conn, "SnapshotMensual").listar()[1]["IdSnapshot"],
        PorcentajeOcupacionGeneral=40.0, MontoHorasRegulares=2000.0, MontoHorasAisladas=200.0,
    )
    conn.commit()

    filas = historial_general(conn, por_anio=True)
    assert len(filas) == 1
    fila_2026 = filas[0]
    assert fila_2026.periodo == "2026"
    # Promedio de ocupación entre junio (20%), julio (40%) y agosto (en
    # vivo, sin reservas, 0%).
    assert fila_2026.ocupacion_pct == pytest.approx((20.0 + 40.0 + 0.0) / 3)
    assert fila_2026.monto_regular == pytest.approx(1000.0 + 2000.0 + 0.0)


# ----------------------------------------------------- estadísticas varias


def test_estadisticas_varias_sin_filtros_trae_todos_los_periodos_con_datos(
    conn, fecha_actual_agosto_2026, localidad_edificio_unidad_consultorio,
):
    _, _, _, id_consultorio = localidad_edificio_unidad_consultorio
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-07-01",
    )
    conn.commit()
    filas = estadisticas_varias(conn)
    assert [f.periodo for f in filas] == ["2026-08", "2026-07"]


def test_estadisticas_varias_filtra_por_anio_y_mes(conn, fecha_actual_agosto_2026):
    filas = estadisticas_varias(conn, anio=2026, mes=3)
    assert [f.periodo for f in filas] == ["2026-03"]


def test_estadisticas_varias_refresca_segun_el_alcance_elegido(
    conn, fecha_actual_agosto_2026, localidad_edificio_unidad_consultorio,
):
    _, id_edificio, id_unidad, id_consultorio = localidad_edificio_unidad_consultorio
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=2)
    id_prof = _profesional(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=otro_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=19, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    fila_consultorio_1 = estadisticas_varias(conn, anio=2026, mes=8, id_consultorio=id_consultorio)[0]
    fila_consultorio_2 = estadisticas_varias(conn, anio=2026, mes=8, id_consultorio=otro_consultorio)[0]
    fila_edificio = estadisticas_varias(conn, anio=2026, mes=8, id_edificio=id_edificio)[0]

    assert fila_consultorio_1.horas_regulares_semanales == 0.0
    assert fila_consultorio_2.horas_regulares_semanales == pytest.approx(10.0)
    assert fila_edificio.horas_regulares_semanales == pytest.approx(10.0)
    assert fila_edificio.cant_consultorios == 2


def test_fila_estadistica_monto_total_es_la_suma_de_regular_y_aislada():
    fila = FilaEstadistica(
        periodo="2026-08", ocupacion_pct=10.0, horas_regulares_semanales=5.0, variacion_horas=None,
        monto_regular=1000.0, monto_aislada=500.0,
        cant_localidades=1, cant_edificios=1, cant_unidades=1, cant_consultorios=1,
    )
    assert fila.monto_total == pytest.approx(1500.0)


def test_fila_estadistica_monto_total_none_si_los_dos_faltan():
    fila = FilaEstadistica(
        periodo="2026-08", ocupacion_pct=None, horas_regulares_semanales=None, variacion_horas=None,
        monto_regular=None, monto_aislada=None,
        cant_localidades=1, cant_edificios=1, cant_unidades=1, cant_consultorios=1,
    )
    assert fila.monto_total is None
