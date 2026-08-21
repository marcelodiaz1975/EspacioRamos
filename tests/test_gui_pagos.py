import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.pagos import PantallaPagos
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


def test_registrar_pago_sin_monto_no_persiste(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_pagos._registrar()
    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 0


def test_registrar_pago_descuenta_saldo_actual(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=10000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_pagos.spin_monto.setValue(3000)
    pantalla.panel_pagos._registrar()

    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 1
    saldo = conn.execute(
        "SELECT SaldoCuentaActual FROM Profesional WHERE IdProfesional = ?", (id_profesional,)
    ).fetchone()["SaldoCuentaActual"]
    assert saldo == 7000
    assert pantalla.panel_pagos.tabla.rowCount() == 1


def test_registrar_pago_medio_no_transferencia_no_guarda_cuenta_receptora(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    panel.combo_medio_pago.setCurrentText("Sobre en buzón")
    panel.spin_monto.setValue(1000)

    panel._registrar()

    fila = conn.execute("SELECT MedioPago, CuentaReceptora FROM HistorialPagos").fetchone()
    assert fila["MedioPago"] == "Sobre en buzón"
    assert fila["CuentaReceptora"] is None


def test_registrar_pago_transferencia_guarda_cuenta_receptora(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    panel.combo_medio_pago.setCurrentText("Transferencia a cta Celeste")
    panel.combo_cuenta_receptora.setCurrentText("CA Banco Macro - Celeste")
    panel.spin_monto.setValue(1000)

    panel._registrar()

    fila = conn.execute("SELECT MedioPago, CuentaReceptora FROM HistorialPagos").fetchone()
    assert fila["MedioPago"] == "Transferencia a cta Celeste"
    assert fila["CuentaReceptora"] == "CA Banco Macro - Celeste"


def test_registrar_pago_periodo_imputado_mes_anterior_pide_confirmacion(qtbot, conn, monkeypatch):
    _crear_profesional(conn, saldo=10000)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    panel.spin_monto.setValue(1000)
    panel.campo_periodo.setText("2026-07")

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    panel._registrar()
    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 0

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel._registrar()
    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 1


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
    panel.spin_monto.setValue(950)  # 1000 -> 50: cruza la tolerancia de 100
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
    panel.spin_monto.setValue(950)
    panel.campo_periodo.setText("2026-07")

    monkeypatch.setattr(QMessageBox, "question", _responder_segun_titulo(QMessageBox.StandardButton.Yes))
    panel._registrar()

    actualizado = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    assert actualizado["DescuentoSuspendidoPeriodo"] is None


def test_cuenta_receptora_se_oculta_salvo_transferencia(qtbot, conn):
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos

    panel.combo_medio_pago.setCurrentText("Sobre en buzón")
    assert panel.combo_cuenta_receptora.isHidden() is True

    panel.combo_medio_pago.setCurrentText("Transferencia a cta Marcelo")
    assert panel.combo_cuenta_receptora.isHidden() is False


def test_crear_plan_de_pagos_persiste_y_genera_cuotas(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    panel.spin_monto.setValue(6000)
    panel.spin_cuotas.setValue(3)
    panel._crear()

    assert conn.execute("SELECT COUNT(*) c FROM PlanPago").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM CuotaPlan").fetchone()["c"] == 3
    assert panel.tabla.item(0, 5).text() == "Activo"


def test_crear_segundo_plan_activo_falla(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    panel.spin_monto.setValue(6000)
    panel._crear()
    panel._crear()  # ya hay un plan activo -> ValueError capturado, no debe crear otro
    assert conn.execute("SELECT COUNT(*) c FROM PlanPago").fetchone()["c"] == 1


def test_cancelar_plan_devuelve_saldo_pendiente(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=0)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    panel.spin_monto.setValue(6000)
    panel.spin_cuotas.setValue(3)
    panel._crear()

    panel.tabla.selectRow(0)
    panel._cancelar()

    estado = conn.execute("SELECT Estado FROM PlanPago").fetchone()["Estado"]
    assert estado == "Cancelado"
    saldo = conn.execute(
        "SELECT SaldoCuentaActual FROM Profesional WHERE IdProfesional = ?", (id_profesional,)
    ).fetchone()["SaldoCuentaActual"]
    assert saldo == 6000
