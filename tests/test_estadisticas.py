import json
from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.estadisticas import (
    calcular_ocupacion,
    generar_snapshot,
    generar_snapshot_operacion_importante,
    historial_general,
    limpiar_snapshots_operacion_importante_antiguos,
    rango_horas_por_dia,
    regenerar_snapshot_si_corresponde,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def dos_consultorios(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    c1 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )
    c2 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=2, ValorHoraRegularActual=1200,
    )
    return id_edificio, id_unidad, c1, c2


def test_rango_horas_por_dia_default_domingo_no_cuenta(conn):
    rangos = rango_horas_por_dia(conn)
    assert "Domingo" not in rangos
    assert rangos["Lunes"] == (9, 21)
    assert rangos["Sábado"] == (9, 15)


def test_rango_horas_por_dia_usa_configuracion_si_esta_cargada(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, RangosEstadisticasOcupacion=json.dumps({"Lunes": [10, 18]}),
    )
    rangos = rango_horas_por_dia(conn)
    assert rangos == {"Lunes": (10, 18)}


def test_ocupacion_general_sin_reservas_es_cero(conn, dos_consultorios):
    ocupacion = calcular_ocupacion(conn, 2026, 8)
    assert ocupacion.general == 0.0


def test_ocupacion_100_por_ciento_cuando_todo_esta_reservado(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    c1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Test")
    for dia in ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes"):
        obtener_repositorio(conn, "ReservaRegular").crear(
            IdProfesional=id_prof, IdConsultorio=c1, DiaSemana=dia, HoraInicio=9, HoraFin=21, VigenciaInicio="2026-01-01",
        )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=c1, DiaSemana="Sábado", HoraInicio=9, HoraFin=15, VigenciaInicio="2026-01-01",
    )
    ocupacion = calcular_ocupacion(conn, 2026, 8)
    assert ocupacion.general == pytest.approx(100.0)


def test_ocupacion_por_consultorio_desglosa_individualmente(conn, dos_consultorios):
    _, _, c1, c2 = dos_consultorios
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Test")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=c1, DiaSemana="Lunes", HoraInicio=9, HoraFin=21, VigenciaInicio="2026-01-01",
    )
    ocupacion = calcular_ocupacion(conn, 2026, 8)
    assert ocupacion.por_consultorio[c1].porcentaje > 0
    assert ocupacion.por_consultorio[c2].porcentaje == 0.0


def test_generar_snapshot_persiste_valores_y_ocupacion(conn, dos_consultorios):
    _, _, c1, c2 = dos_consultorios
    id_snapshot = generar_snapshot(conn, "2026-08", porcentaje_aumento_aplicado=5.0)
    snapshot = obtener_repositorio(conn, "SnapshotMensual").obtener(id_snapshot)

    assert snapshot["Periodo"] == "2026-08"
    assert snapshot["PorcentajeAumentoAplicado"] == pytest.approx(5.0)
    assert snapshot["PorcentajeOcupacionGeneral"] == pytest.approx(0.0)

    valores = json.loads(snapshot["ValoresConsultorios"])
    assert valores[str(c1)] == pytest.approx(1000)
    assert valores[str(c2)] == pytest.approx(1200)


# ----------------------------------------------- DC-06 §3: ajuste retroactivo

def test_regenerar_snapshot_sin_snapshot_previo_no_hace_nada(conn, dos_consultorios):
    """El período todavía no cerró (nunca se avanzó de mes sobre él) — no
    hay nada desalineado, así que no se crea ningún snapshot de la nada."""
    regenerar_snapshot_si_corresponde(conn, "2026-08")
    assert obtener_repositorio(conn, "SnapshotMensual").listar(Periodo="2026-08") == []


def test_regenerar_snapshot_recalcula_montos_con_una_aislada_tardia(conn, dos_consultorios):
    """Una reserva aislada confirmada DESPUÉS de que el snapshot de su mes
    ya se generó (el caso típico: se carga en un período ya cerrado) deja
    el snapshot viejo con `MontoHorasAisladas` en 0 hasta que se llama a
    esta función — mismo criterio exacto que `generar_snapshot`."""
    _, _, c1, _ = dos_consultorios
    obtener_repositorio(conn, "Consultorio").actualizar(c1, ValorHoraAisladaActual=1000)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Tardía")
    id_snapshot = generar_snapshot(conn, "2026-08", porcentaje_aumento_aplicado=7.0)
    snapshot_antes = obtener_repositorio(conn, "SnapshotMensual").obtener(id_snapshot)
    assert snapshot_antes["MontoHorasAisladas"] == pytest.approx(0.0)

    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-10",
        HoraInicio=9, HoraFin=11, Estado="Confirmada",
    )
    regenerar_snapshot_si_corresponde(conn, "2026-08")

    snapshots = obtener_repositorio(conn, "SnapshotMensual").listar(Periodo="2026-08")
    assert len(snapshots) == 1  # actualiza la fila existente, no crea una nueva
    snapshot_despues = snapshots[0]
    assert snapshot_despues["IdSnapshot"] == id_snapshot
    assert snapshot_despues["MontoHorasAisladas"] == pytest.approx(2000.0)  # 2hs * 1000


def test_regenerar_snapshot_conserva_fecha_generacion_y_aumento_aplicado(conn, dos_consultorios):
    """Esos dos campos no son recalculables a partir del estado actual —
    siguen reflejando el momento y el contexto del cierre original."""
    id_snapshot = generar_snapshot(conn, "2026-08", porcentaje_aumento_aplicado=12.5)
    snapshot_antes = obtener_repositorio(conn, "SnapshotMensual").obtener(id_snapshot)

    regenerar_snapshot_si_corresponde(conn, "2026-08")

    snapshot_despues = obtener_repositorio(conn, "SnapshotMensual").obtener(id_snapshot)
    assert snapshot_despues["FechaGeneracion"] == snapshot_antes["FechaGeneracion"]
    assert snapshot_despues["PorcentajeAumentoAplicado"] == pytest.approx(12.5)


def test_regenerar_snapshot_de_otro_periodo_no_lo_toca(conn, dos_consultorios):
    id_snapshot_julio = generar_snapshot(conn, "2026-07")
    regenerar_snapshot_si_corresponde(conn, "2026-08")
    assert obtener_repositorio(conn, "SnapshotMensual").obtener(id_snapshot_julio) is not None
    assert obtener_repositorio(conn, "SnapshotMensual").listar(Periodo="2026-08") == []


# -------------------------------------------- DC-06 §6: snapshot de operación importante

def test_generar_snapshot_operacion_importante_queda_marcado_con_ese_tipo(conn, dos_consultorios):
    id_snapshot = generar_snapshot_operacion_importante(conn, "2026-08", observacion="Antes de un aumento")
    snapshot = obtener_repositorio(conn, "SnapshotMensual").obtener(id_snapshot)
    assert snapshot["Tipo"] == "OperacionImportante"
    assert snapshot["Observacion"] == "Antes de un aumento"
    assert snapshot["Periodo"] == "2026-08"


def test_generar_snapshot_mensual_queda_marcado_con_tipo_mensual(conn, dos_consultorios):
    id_snapshot = generar_snapshot(conn, "2026-08")
    snapshot = obtener_repositorio(conn, "SnapshotMensual").obtener(id_snapshot)
    assert snapshot["Tipo"] == "Mensual"
    assert snapshot["Observacion"] is None


def test_puede_haber_varios_snapshots_de_operacion_importante_en_el_mismo_periodo(conn, dos_consultorios):
    """A diferencia del mensual (uno por período), este tipo se acumula —
    cada operación importante genera el suyo."""
    generar_snapshot_operacion_importante(conn, "2026-08", observacion="Primer aumento del mes")
    generar_snapshot_operacion_importante(conn, "2026-08", observacion="Corrección del mismo mes")
    filas = obtener_repositorio(conn, "SnapshotMensual").listar(Tipo="OperacionImportante")
    assert len(filas) == 2


def test_historial_general_ignora_los_snapshots_de_operacion_importante(conn, dos_consultorios):
    """Si no filtrara por Tipo, un snapshot "de operación importante" del
    mismo período pisaría (o duplicaría, según el orden de iteración) al
    mensual en `datos_por_mes` — `historial_general` tiene que seguir
    mostrando una sola fila por período, la del mensual."""
    generar_snapshot(conn, "2026-08", porcentaje_aumento_aplicado=10.0)
    generar_snapshot_operacion_importante(conn, "2026-08", observacion="Antes de un aumento")

    filas = historial_general(conn, por_anio=False)
    filas_agosto = [f for f in filas if f.periodo == "2026-08"]
    assert len(filas_agosto) == 1


def test_regenerar_snapshot_si_corresponde_no_toca_una_fila_de_operacion_importante(conn, dos_consultorios):
    """Si en el mismo período solo existe un snapshot "de operación
    importante" (sin ningún mensual todavía), DC-06 §3 no tiene nada que
    actualizar — ese período, a los efectos del cierre de mes, sigue sin
    cerrar."""
    generar_snapshot_operacion_importante(conn, "2026-08", observacion="Antes de un aumento")
    regenerar_snapshot_si_corresponde(conn, "2026-08")
    filas = obtener_repositorio(conn, "SnapshotMensual").listar(Periodo="2026-08")
    assert len(filas) == 1
    assert filas[0]["Tipo"] == "OperacionImportante"  # sigue intacta, no se convirtió en mensual


def test_limpiar_snapshots_operacion_importante_antiguos_borra_los_de_mas_de_12_meses(conn, dos_consultorios):
    generar_snapshot_operacion_importante(conn, "2025-06")  # más de 12 meses antes de 2026-10
    generar_snapshot_operacion_importante(conn, "2026-09")  # dentro de la retención
    borrados = limpiar_snapshots_operacion_importante_antiguos(conn, date(2026, 10, 4))
    assert borrados == 1
    restantes = obtener_repositorio(conn, "SnapshotMensual").listar(Tipo="OperacionImportante")
    assert [f["Periodo"] for f in restantes] == ["2026-09"]


def test_limpiar_snapshots_operacion_importante_antiguos_no_toca_los_mensuales(conn, dos_consultorios):
    """Los snapshots mensuales se conservan para siempre, sin importar su
    antigüedad — esta limpieza es exclusiva de los de operación
    importante."""
    generar_snapshot(conn, "2020-01")
    borrados = limpiar_snapshots_operacion_importante_antiguos(conn, date(2026, 10, 4))
    assert borrados == 0
    assert obtener_repositorio(conn, "SnapshotMensual").listar(Periodo="2020-01") != []
