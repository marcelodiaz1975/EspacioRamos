from pathlib import Path

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.avance_mes import avanzar_mes, porcentaje_aumento_del_periodo
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


def test_plazo_extendido_automatico_se_aplica_al_avanzar_de_mes(conn):
    id_prof = _crear_profesional(conn)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, DiaPlazoExtendidoAutomatico=15)

    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["PlazoPagoExtendido"] == "2026-09-15"
    assert profesional["MotivoPlazoExtra"]
    assert resumen.plazos_extendidos_automaticos_aplicados == 1


def test_plazo_extendido_automatico_recorta_al_ultimo_dia_del_mes(conn):
    id_prof = _crear_profesional(conn)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, DiaPlazoExtendidoAutomatico=31)

    avanzar_mes(conn, periodo_cerrado="2026-01")  # pasa a febrero, que no tiene 31

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["PlazoPagoExtendido"] == "2026-02-28"


def test_plazo_extendido_automatico_no_aplica_sin_configurar(conn):
    id_prof = _crear_profesional(conn)

    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["PlazoPagoExtendido"] is None
    assert resumen.plazos_extendidos_automaticos_aplicados == 0


def test_plazo_extendido_automatico_no_aplica_a_categoria_a(conn):
    id_prof = _crear_profesional(conn, categoria="A")
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, DiaPlazoExtendidoAutomatico=15)

    avanzar_mes(conn, periodo_cerrado="2026-08")

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["PlazoPagoExtendido"] is None


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


def test_avanzar_mes_genera_snapshot(conn):
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")
    snapshot = obtener_repositorio(conn, "SnapshotMensual").obtener(resumen.id_snapshot)
    assert snapshot is not None
    assert snapshot["Periodo"] == "2026-08"


def test_avanzar_mes_pasa_porcentaje_aumento_al_snapshot(conn):
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08", porcentaje_aumento_aplicado=12.5)
    snapshot = obtener_repositorio(conn, "SnapshotMensual").obtener(resumen.id_snapshot)
    assert snapshot["PorcentajeAumentoAplicado"] == pytest.approx(12.5)


def test_avanzar_mes_sin_pasar_porcentaje_lo_busca_en_aumento_aplicado(conn):
    obtener_repositorio(conn, "AumentoAplicado").crear(Periodo="2026-08", PorcentajeGeneral=7.0)
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")
    snapshot = obtener_repositorio(conn, "SnapshotMensual").obtener(resumen.id_snapshot)
    assert snapshot["PorcentajeAumentoAplicado"] == pytest.approx(7.0)


def test_avanzar_mes_sin_aumento_confirmado_snapshot_queda_sin_porcentaje(conn):
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")
    snapshot = obtener_repositorio(conn, "SnapshotMensual").obtener(resumen.id_snapshot)
    assert snapshot["PorcentajeAumentoAplicado"] is None


def test_avanzar_mes_toma_la_ultima_correccion_del_periodo(conn):
    obtener_repositorio(conn, "AumentoAplicado").crear(Periodo="2026-08", PorcentajeGeneral=5.0)
    obtener_repositorio(conn, "AumentoAplicado").crear(Periodo="2026-08", PorcentajeGeneral=8.0)
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")
    snapshot = obtener_repositorio(conn, "SnapshotMensual").obtener(resumen.id_snapshot)
    assert snapshot["PorcentajeAumentoAplicado"] == pytest.approx(8.0)


def test_avanzar_mes_ignora_aumento_de_otro_periodo(conn):
    obtener_repositorio(conn, "AumentoAplicado").crear(Periodo="2026-07", PorcentajeGeneral=5.0)
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")
    snapshot = obtener_repositorio(conn, "SnapshotMensual").obtener(resumen.id_snapshot)
    assert snapshot["PorcentajeAumentoAplicado"] is None


def test_porcentaje_aumento_del_periodo_sin_registros(conn):
    assert porcentaje_aumento_del_periodo(conn, "2026-08") is None


def test_porcentaje_aumento_del_periodo_devuelve_el_ultimo(conn):
    obtener_repositorio(conn, "AumentoAplicado").crear(Periodo="2026-08", PorcentajeGeneral=5.0)
    obtener_repositorio(conn, "AumentoAplicado").crear(Periodo="2026-08", PorcentajeGeneral=8.0)
    assert porcentaje_aumento_del_periodo(conn, "2026-08") == pytest.approx(8.0)


def test_avanzar_mes_sin_carpeta_base_no_regenera_archivos(conn):
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")
    assert resumen.archivos_varios_regenerados is False
    assert resumen.liquidaciones_antiguas_eliminadas == 0


def test_avanzar_mes_regenera_archivos_varios_y_limpia_liquidaciones_antiguas(conn, tmp_path):
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBaseArchivos=str(tmp_path))
    obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_prof = _crear_profesional(conn)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, IdCodigo="R1")

    from app.negocio.archivos_generados import carpeta_archivos_varios, carpeta_profesional
    (carpeta_profesional(conn, "R1") / "2020-01 - Liquidación Vieja.pdf").write_text("x")
    (carpeta_archivos_varios(conn, "Oferta") / "Oferta de consultorios - Vieja.pdf").write_text("x")

    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")

    assert resumen.archivos_varios_regenerados is True
    assert resumen.liquidaciones_antiguas_eliminadas == 1
    assert not (carpeta_profesional(conn, "R1") / "2020-01 - Liquidación Vieja.pdf").exists()
    assert list(carpeta_archivos_varios(conn, "Oferta").iterdir()) == []
    assert any((tmp_path / "Archivos varios" / "Propuesta").iterdir())
    assert any((tmp_path / "Archivos varios" / "Disponibilidad").iterdir())
    assert any((tmp_path / "Archivos varios" / "Placas").iterdir())


def test_avanzar_mes_vacia_historial_de_oferta(conn):
    from app.negocio.oferta_busqueda import Busqueda, CriteriosGlobales
    from app.negocio.historial_oferta import guardar_busqueda

    id_prof = _crear_profesional(conn)
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[])
    busqueda = Busqueda(fecha_desde="2026-09-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11)
    guardar_busqueda(conn, id_prof, globales, [busqueda], set(), "2026-08-01")

    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")

    assert resumen.historial_oferta_eliminado == 1
    assert obtener_repositorio(conn, "HistorialOferta").listar() == []


def test_avanzar_mes_sin_carpeta_backup_no_falla(conn):
    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")
    assert resumen.backup_generado is False
    assert resumen.ruta_backup is None


def test_avanzar_mes_genera_backup_previo(conn, tmp_path):
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBackup=str(tmp_path / "backups"))

    resumen = avanzar_mes(conn, periodo_cerrado="2026-08")

    assert resumen.backup_generado is True
    assert resumen.ruta_backup is not None
    assert list(Path(resumen.ruta_backup).glob("*.db"))
