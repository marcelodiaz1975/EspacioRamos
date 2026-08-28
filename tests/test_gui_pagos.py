import pytest
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.pagos import PantallaPagos
from app.negocio.formato import formatear_moneda
from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


def _crear_profesional(conn, saldo=10000):
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, SaldoCuentaActual) VALUES ('R', 'Gómez', ?)",
        (saldo,),
    )
    conn.commit()
    return conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]


def _seleccionar_profesional(panel, id_profesional):
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))


def test_registrar_pago_sin_monto_no_persiste(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    _seleccionar_profesional(pantalla.panel_pagos, id_profesional)
    pantalla.panel_pagos._registrar()
    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 0


def test_registrar_pago_sin_profesional_no_persiste(qtbot, conn):
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_pagos.spin_monto.setValue(-1000)
    pantalla.panel_pagos._registrar()
    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 0


def test_registrar_pago_negativo_descuenta_saldo_actual(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=10000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-3000)
    panel._registrar()

    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 1
    saldo = conn.execute(
        "SELECT SaldoCuentaActual FROM Profesional WHERE IdProfesional = ?", (id_profesional,)
    ).fetchone()["SaldoCuentaActual"]
    assert saldo == 7000
    assert panel.tabla.rowCount() == 1


def test_registrar_pago_positivo_suma_saldo_actual(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=1000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(500)
    panel._registrar()

    saldo = conn.execute(
        "SELECT SaldoCuentaActual FROM Profesional WHERE IdProfesional = ?", (id_profesional,)
    ).fetchone()["SaldoCuentaActual"]
    assert saldo == 1500


def test_registrar_pago_formulario_se_resetea_y_vuelve_foco_a_profesional(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-500)
    panel._registrar()

    assert panel.combo_profesional.currentData() is None
    assert panel.spin_monto.value() == 0


def test_registrar_pago_medio_no_transferencia_no_guarda_cuenta_receptora(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.combo_medio_pago.setCurrentText("Sobre en buzón")
    panel.spin_monto.setValue(-1000)

    panel._registrar()

    fila = conn.execute("SELECT MedioPago, CuentaReceptora FROM HistorialPagos").fetchone()
    assert fila["MedioPago"] == "Sobre en buzón"
    assert fila["CuentaReceptora"] is None


def test_registrar_pago_transferencia_guarda_cuenta_receptora(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.combo_medio_pago.setCurrentText("Transferencia a cta Celeste")
    panel.combo_cuenta_receptora.setCurrentText("CA Banco Macro - Celeste")
    panel.spin_monto.setValue(-1000)

    panel._registrar()

    fila = conn.execute("SELECT MedioPago, CuentaReceptora FROM HistorialPagos").fetchone()
    assert fila["MedioPago"] == "Transferencia a cta Celeste"
    assert fila["CuentaReceptora"] == "CA Banco Macro - Celeste"


def test_registrar_pago_transferencia_sin_cuenta_receptora_no_persiste(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.combo_medio_pago.setCurrentText("Transferencia a cta Celeste")
    panel.spin_monto.setValue(-1000)

    panel._registrar()

    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 0


def test_registrar_pago_periodo_imputado_mes_anterior_pide_confirmacion(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn, saldo=10000)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-1000)
    panel.campo_periodo.setText("2026-07")

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    panel._registrar()
    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 0

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-1000)
    panel.campo_periodo.setText("2026-07")
    panel._registrar()
    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 1


def test_registrar_pago_mes_anterior_regenera_liquidacion_del_mes_en_curso(qtbot, conn, monkeypatch):
    """La liquidación del mes anterior ya emitida no se reabre — el pago
    corrige el saldo anterior, y es la liquidación del mes EN CURSO la que
    arrastra ese saldo corregido y se regenera/marca como no enviada
    (confirmado por la clienta: no se corrigen liquidaciones ya emitidas)."""
    id_profesional = _crear_profesional(conn, saldo=10000)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    emitir_liquidacion(conn, id_profesional=id_profesional, periodo="2026-07")
    marcar_estado_envio(conn, id_profesional=id_profesional, periodo="2026-07", enviada=True)
    conn.commit()

    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-1000)
    panel.campo_periodo.setText("2026-07")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    panel._registrar()

    emisiones_julio = obtener_repositorio(conn, "LiquidacionEmitida").listar(
        IdProfesional=id_profesional, Periodo="2026-07",
    )
    assert len(emisiones_julio) == 1  # la de julio no se toca
    assert emisiones_julio[0]["EstadoEnvio"] == "Enviada"

    emisiones_agosto = obtener_repositorio(conn, "LiquidacionEmitida").listar(
        IdProfesional=id_profesional, Periodo="2026-08",
    )
    assert len(emisiones_agosto) == 1
    assert emisiones_agosto[0]["EstadoEnvio"] == "No enviada"


def test_registrar_pago_mes_en_curso_no_regenera_liquidacion_de_mes_anterior(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn, saldo=10000)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    emitir_liquidacion(conn, id_profesional=id_profesional, periodo="2026-07")
    marcar_estado_envio(conn, id_profesional=id_profesional, periodo="2026-07", enviada=True)
    conn.commit()

    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-1000)  # período imputado por defecto -> mes en curso
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    panel._registrar()

    emisiones = obtener_repositorio(conn, "LiquidacionEmitida").listar(
        IdProfesional=id_profesional, Periodo="2026-07",
    )
    assert len(emisiones) == 1  # no se tocó la liquidación de julio


def _preparar_pago_que_cruza_tolerancia(conn):
    id_profesional = _crear_profesional(conn, saldo=10000)
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=100)
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, SaldoCuentaAnterior=1000)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    return id_profesional


def _responder_segun_titulo(respuesta_restablecer):
    def _responder(_parent, titulo, *a, **k):
        if titulo == "Restablecer descuentos":
            return respuesta_restablecer
        return QMessageBox.StandardButton.Yes  # confirma que la fecha del mes anterior es correcta

    return staticmethod(_responder)


def test_registrar_pago_que_cruza_tolerancia_pregunta_restablecer_descuento(qtbot, conn, monkeypatch):
    id_profesional = _preparar_pago_que_cruza_tolerancia(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-950)  # 1000 -> 50: cruza la tolerancia de 100
    panel.campo_periodo.setText("2026-07")

    monkeypatch.setattr(QMessageBox, "question", _responder_segun_titulo(QMessageBox.StandardButton.No))
    panel._registrar()

    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 1
    actualizado = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    assert actualizado["DescuentoSuspendidoPeriodo"] == "2026-07"


def test_registrar_pago_que_cruza_tolerancia_restablece_si_responde_si(qtbot, conn, monkeypatch):
    id_profesional = _preparar_pago_que_cruza_tolerancia(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-950)
    panel.campo_periodo.setText("2026-07")

    monkeypatch.setattr(QMessageBox, "question", _responder_segun_titulo(QMessageBox.StandardButton.Yes))
    panel._registrar()

    actualizado = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    assert actualizado["DescuentoSuspendidoPeriodo"] is None


def test_cuenta_receptora_se_deshabilita_salvo_transferencia(qtbot, conn):
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos

    panel.combo_medio_pago.setCurrentText("Sobre en buzón")
    assert panel.combo_cuenta_receptora.isEnabled() is False
    assert panel.combo_cuenta_receptora.isHidden() is False  # ya no se oculta, solo se deshabilita

    panel.combo_medio_pago.setCurrentText("Transferencia a cta Marcelo")
    assert panel.combo_cuenta_receptora.isEnabled() is True


def test_recogida_sobres_se_precarga_desde_configuracion_y_se_actualiza(qtbot, conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, FechaHoraRecogidaSobres="2026-08-01T10:00:00")
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    assert panel.campo_recogida_sobres.dateTime() == QDateTime.fromString("2026-08-01T10:00:00", Qt.DateFormat.ISODate)

    _seleccionar_profesional(panel, id_profesional)
    panel.combo_medio_pago.setCurrentText("Sobre en buzón")
    panel.spin_monto.setValue(-500)
    panel.campo_recogida_sobres.setDateTime(QDateTime.fromString("2026-08-15T09:30:00", Qt.DateFormat.ISODate))
    panel._registrar()

    pago = conn.execute("SELECT FechaHoraRecogidaSobres FROM HistorialPagos").fetchone()
    assert pago["FechaHoraRecogidaSobres"] == "2026-08-15T09:30:00"
    cfg = obtener_repositorio(conn, "Configuracion").obtener(1)
    assert cfg["FechaHoraRecogidaSobres"] == "2026-08-15T09:30:00"


def test_iniciar_y_cerrar_tanda_de_sobres(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    assert panel.etiqueta_estado_tanda.text() == "Sin tanda abierta"

    panel._iniciar_tanda()
    assert panel.etiqueta_estado_tanda.text() == "Con tanda abierta"

    _seleccionar_profesional(panel, id_profesional)
    panel.combo_medio_pago.setCurrentText("Sobre en buzón")
    panel.spin_monto.setValue(-700)
    panel._registrar()
    assert "700" in panel.etiqueta_total_tanda.text()

    panel._cerrar_tanda()
    assert panel.etiqueta_estado_tanda.text() == "Sin tanda abierta"


def test_iniciar_tanda_de_otro_dia_pregunta_mantener_o_nueva(qtbot, conn, monkeypatch):
    _crear_profesional(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15', "
        "TandaSobresAbierta = 1, TandaSobresApertura = '2026-08-14T18:00:00' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel._iniciar_tanda()  # mantiene la vieja
    cfg = obtener_repositorio(conn, "Configuracion").obtener(1)
    assert cfg["TandaSobresApertura"] == "2026-08-14T18:00:00"

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    panel._iniciar_tanda()  # arranca una nueva
    cfg = obtener_repositorio(conn, "Configuracion").obtener(1)
    assert cfg["TandaSobresApertura"] != "2026-08-14T18:00:00"


# ------------------------------------------------------- modificar / deshacer

def test_seleccionar_fila_precarga_formulario(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    periodo = panel.campo_periodo.text()  # queda en el período actual por defecto
    _seleccionar_profesional(panel, id_profesional)
    panel.combo_medio_pago.setCurrentText("Transferencia a cta Celeste")
    panel.combo_cuenta_receptora.setCurrentText("CA Banco Macro - Celeste")
    panel.spin_monto.setValue(-500)
    panel._registrar()

    panel.tabla.selectRow(0)

    assert panel.combo_profesional.currentData() == id_profesional
    assert panel.spin_monto.value() == -500
    assert panel.campo_periodo.text() == periodo
    assert panel.combo_medio_pago.currentText() == "Transferencia a cta Celeste"
    assert panel.combo_cuenta_receptora.currentText() == "CA Banco Macro - Celeste"


def test_modificar_pago_seleccionado_ajusta_saldo_y_marca_modificado(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=1000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-400)
    panel._registrar()  # saldo: 600

    panel.tabla.selectRow(0)
    panel.spin_monto.setValue(-600)  # se corrige el monto cargado
    panel._modificar()

    saldo = obtener_repositorio(conn, "Profesional").obtener(id_profesional)["SaldoCuentaActual"]
    assert saldo == 400
    fila = conn.execute("SELECT Monto, RegistroModificado FROM HistorialPagos").fetchone()
    assert fila["Monto"] == -600
    assert fila["RegistroModificado"] == 1


def test_modificar_pago_sin_seleccion_no_falla(qtbot, conn):
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_pagos._modificar()  # nada seleccionado -> no debe romper


def test_modificar_pago_a_mes_anterior_regenera_liquidacion_del_mes_en_curso(qtbot, conn):
    """Igual que al registrar un pago nuevo: si la modificación hace que el
    pago pase a afectar el saldo anterior (imputado al mes anterior), la
    liquidación del mes EN CURSO (no la de ese período) se regenera y
    queda marcada como no enviada."""
    id_profesional = _crear_profesional(conn, saldo=10000)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    emitir_liquidacion(conn, id_profesional=id_profesional, periodo="2026-08")
    marcar_estado_envio(conn, id_profesional=id_profesional, periodo="2026-08", enviada=True)
    conn.commit()

    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-1000)
    panel._registrar()  # imputado al mes en curso, todavía no toca julio

    panel.tabla.selectRow(0)
    panel.campo_periodo.setText("2026-07")  # se corrige: era del mes anterior
    panel._modificar()

    emisiones_agosto = obtener_repositorio(conn, "LiquidacionEmitida").listar(
        IdProfesional=id_profesional, Periodo="2026-08",
    )
    assert len(emisiones_agosto) == 2
    ultima = max(emisiones_agosto, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] == "Regenerada no enviada"


def test_deshacer_ultimo_movimiento_revierte_y_borra(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn, saldo=1000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-400)
    panel._registrar()

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel._deshacer_ultimo()

    saldo = obtener_repositorio(conn, "Profesional").obtener(id_profesional)["SaldoCuentaActual"]
    assert saldo == 1000
    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 0


def test_deshacer_ultimo_movimiento_sin_confirmar_no_hace_nada(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn, saldo=1000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-400)
    panel._registrar()

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    panel._deshacer_ultimo()

    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 1


def test_deshacer_ultimo_movimiento_sin_pagos_no_falla(qtbot, conn):
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    panel._deshacer_ultimo()  # sin QMessageBox.question mockeado a Yes -> ni siquiera llega a preguntar mal


def test_tabla_pagos_columnas_y_orden(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=1000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    assert [panel.tabla.horizontalHeaderItem(i).text() for i in range(panel.tabla.columnCount())] == [
        "Fecha de carga", "Profesional", "Período imputado", "Monto", "Medio de pago", "Cuenta receptora",
        "Saldo anterior", "Nuevo saldo", "Registro modificado", "Es ajuste",
    ]

    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-100)
    panel._registrar()
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-200)
    panel._registrar()

    # más nuevo arriba
    assert panel.tabla.item(0, 3).text() == "-$ 200,00"
    assert panel.tabla.item(1, 3).text() == "-$ 100,00"


def test_crear_plan_de_pagos_persiste_y_genera_cuotas(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(6000)
    panel.spin_cuotas.setValue(3)
    panel._guardar()

    assert conn.execute("SELECT COUNT(*) c FROM PlanPago").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM CuotaPlan").fetchone()["c"] == 3
    assert panel.tabla.item(0, 5).text() == "Activo"


def test_guardar_con_plan_activo_y_mes_actual_refinancia_de_una(qtbot, conn):
    """DC-09 §3.6: un profesional no puede tener dos planes activos — con
    uno ya vigente, guardar de nuevo para el mes en curso refinancia
    (cancela el viejo, crea uno nuevo) en vez de fallar."""
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(6000)
    panel._guardar()

    panel.spin_monto.setValue(3000)
    panel._guardar()

    planes = conn.execute("SELECT Estado FROM PlanPago ORDER BY IdPlan").fetchall()
    assert [p["Estado"] for p in planes] == ["Cancelado", "Activo"]


def test_guardar_con_plan_activo_y_mes_futuro_programa_la_refinanciacion(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(6000)
    panel._guardar()  # plan activo del mes en curso

    panel.spin_monto.setValue(3000)
    panel.campo_mes_inicio.setText("2099-01")  # bien a futuro
    panel._guardar()

    assert conn.execute("SELECT Estado FROM PlanPago").fetchone()["Estado"] == "Activo"  # el viejo, sin tocar
    assert conn.execute("SELECT COUNT(*) c FROM RefinanciacionProgramada").fetchone()["c"] == 1


def test_cancelar_plan_devuelve_saldo_pendiente(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=0)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(6000)
    panel.spin_cuotas.setValue(3)
    panel._guardar()

    panel.tabla.selectRow(0)
    panel._cancelar()

    estado = conn.execute("SELECT Estado FROM PlanPago").fetchone()["Estado"]
    assert estado == "Cancelado"
    saldo = conn.execute(
        "SELECT SaldoCuentaActual FROM Profesional WHERE IdProfesional = ?", (id_profesional,)
    ).fetchone()["SaldoCuentaActual"]
    assert saldo == 6000


def test_combo_profesional_registrar_pago_filtra_la_tabla(qtbot, conn):
    id_profesional_1 = _crear_profesional(conn)
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional_1)
    panel.spin_monto.setValue(-100)
    panel._registrar()

    _seleccionar_profesional(panel, id_profesional_2)
    panel.spin_monto.setValue(-200)
    panel._registrar()

    assert panel.tabla.rowCount() == 2  # "Todos los profesionales" tras resetear el formulario

    _seleccionar_profesional(panel, id_profesional_1)
    assert panel.tabla.rowCount() == 1


def test_tabla_registrar_pago_click_en_columna_ordena_y_alterna_sentido(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    for medio in ("Efectivo", "Cheque"):
        panel.combo_medio_pago.setCurrentText(medio)
        panel.spin_monto.setValue(-100)
        _seleccionar_profesional(panel, id_profesional)
        panel._registrar()
    assert panel.tabla.rowCount() == 2

    panel.tabla.horizontalHeader().sectionClicked.emit(4)  # "Medio de pago" ascendente
    medios_asc = [panel.tabla.item(f, 4).text() for f in range(panel.tabla.rowCount())]
    assert medios_asc == ["Cheque", "Efectivo"]

    panel.tabla.horizontalHeader().sectionClicked.emit(4)  # de nuevo -> descendente
    medios_desc = [panel.tabla.item(f, 4).text() for f in range(panel.tabla.rowCount())]
    assert medios_desc == ["Efectivo", "Cheque"]


def test_panel_registrar_pago_recibe_foco_en_profesional_al_mostrarse(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.panel_pagos.combo_profesional.hasFocus())


def test_combo_profesional_planes_pago_arranca_en_blanco(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    assert panel.combo_profesional.currentIndex() == 0
    assert panel.combo_profesional.currentData() is None


def test_guardar_plan_sin_elegir_profesional_avisa_y_no_crea(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    panel.spin_monto.setValue(6000)
    panel._guardar()
    assert conn.execute("SELECT COUNT(*) c FROM PlanPago").fetchone()["c"] == 0


def test_tabla_planes_pago_usa_formato_canonico_de_profesional(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, NombrePila, Tratamiento, IdCodigo) "
                 "VALUES ('R', 'Lo Veci', 'Virginia', 'Lic.', 'R1')")
    conn.commit()
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(6000)
    panel._guardar()
    assert panel.tabla.item(0, 0).text() == "R1 - Lic. Virginia Lo Veci"


def test_tabla_planes_pago_mezcla_planes_y_programadas_y_ordena_por_columna(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(6000)
    panel._guardar()  # plan activo

    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(3000)
    panel.campo_mes_inicio.setText("2099-01")
    panel._guardar()  # ya tiene uno activo y el inicio es a futuro -> queda programada, sin tocar el activo

    assert panel.tabla.rowCount() == 2
    assert {panel.tabla.item(f, 5).text() for f in range(panel.tabla.rowCount())} == {
        "Activo", "Refinanciación programada",
    }

    panel.tabla.horizontalHeader().sectionClicked.emit(1)  # "Monto refinanciado" ascendente
    montos_asc = [panel.tabla.item(f, 1).text() for f in range(panel.tabla.rowCount())]
    assert montos_asc == [formatear_moneda(3000), formatear_moneda(6000)]

    panel.tabla.horizontalHeader().sectionClicked.emit(1)  # de nuevo -> descendente
    montos_desc = [panel.tabla.item(f, 1).text() for f in range(panel.tabla.rowCount())]
    assert montos_desc == [formatear_moneda(6000), formatear_moneda(3000)]


def test_fecha_de_carga_muestra_segundos(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-500)
    panel._registrar()

    fecha_carga = conn.execute("SELECT FechaHoraCarga FROM HistorialPagos").fetchone()["FechaHoraCarga"]
    segundos = fecha_carga.split(":")[-1]
    assert f":{segundos}hs" in panel.tabla.item(0, 0).text()


def test_saldo_anterior_y_nuevo_saldo_no_se_colorean_en_negativo(qtbot, conn):
    from PySide6.QtGui import QColor

    id_profesional = _crear_profesional(conn, saldo=100)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-500)  # deja el saldo en negativo
    panel._registrar()

    assert panel.tabla.item(0, 6).foreground().color() != QColor("red")
    assert panel.tabla.item(0, 7).foreground().color() != QColor("red")
    assert panel.tabla.item(0, 3).foreground().color() == QColor("red")  # el Monto sí


def test_eliminar_pago_seleccionado_revierte_saldo(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn, saldo=1000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-400)
    panel._registrar()  # saldo: 600

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel.tabla.selectRow(0)
    panel._eliminar()

    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 0
    saldo = conn.execute(
        "SELECT SaldoCuentaActual FROM Profesional WHERE IdProfesional = ?", (id_profesional,)
    ).fetchone()["SaldoCuentaActual"]
    assert saldo == 1000


def test_eliminar_pago_sin_seleccion_no_falla(qtbot, conn):
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_pagos._eliminar()  # nada seleccionado -> no debe romper


def test_eliminar_pago_mes_anterior_regenera_liquidacion_del_mes_en_curso(qtbot, conn, monkeypatch):
    """Mismo criterio que Modificar: si se elimina un pago que afectaba el
    saldo anterior, hay que regenerar y marcar como no enviada la
    liquidación del mes en curso, que es la que arrastra ese saldo."""
    id_profesional = _crear_profesional(conn, saldo=10000)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    emitir_liquidacion(conn, id_profesional=id_profesional, periodo="2026-08")
    marcar_estado_envio(conn, id_profesional=id_profesional, periodo="2026-08", enviada=True)
    conn.commit()

    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-1000)
    panel.campo_periodo.setText("2026-07")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel._registrar()

    panel.tabla.selectRow(0)
    panel._eliminar()

    emisiones = obtener_repositorio(conn, "LiquidacionEmitida").listar(
        IdProfesional=id_profesional, Periodo="2026-08",
    )
    # 1) la original, 2) la que ya regeneró el propio _registrar al imputar
    # al mes anterior, 3) la que regenera _eliminar al revertir ese efecto
    # (ya no es "Regenerada no enviada" porque lo que reemplaza no estaba
    # "Enviada" — pero tiene que seguir sin quedar marcada como enviada).
    assert len(emisiones) == 3
    ultima = max(emisiones, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] != "Enviada"


def test_deshacer_ultimo_mes_anterior_regenera_liquidacion_del_mes_en_curso(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn, saldo=10000)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    emitir_liquidacion(conn, id_profesional=id_profesional, periodo="2026-08")
    marcar_estado_envio(conn, id_profesional=id_profesional, periodo="2026-08", enviada=True)
    conn.commit()

    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-1000)
    panel.campo_periodo.setText("2026-07")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel._registrar()

    panel._deshacer_ultimo()

    emisiones = obtener_repositorio(conn, "LiquidacionEmitida").listar(
        IdProfesional=id_profesional, Periodo="2026-08",
    )
    assert len(emisiones) == 3
    ultima = max(emisiones, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] != "Enviada"
