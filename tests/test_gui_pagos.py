import pytest
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import COLOR_ROJO
from app.gui.pantallas import pagos as pagos_modulo
from app.gui.pantallas.pagos import PantallaPagos
from app.gui.widgets.selector_profesional import _ProxyBusquedaSinAcentos
from app.negocio.dias import periodo_actual
from app.negocio.formato import formatear_moneda
from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio
from app.negocio.pagos import registrar_pago
from app.repositorio.registro import obtener_repositorio


class _DialogoFalso:
    """Reemplaza, en los tests, a los `QDialog` reales de esta pantalla
    (`_DialogoModificarPago`/`_DialogoRefinanciarPlan`): no abre ninguna
    ventana ni bloquea esperando al operador — `exec()` devuelve
    directamente el resultado ya decidido por el test, y los atributos
    que el panel lee de él después de `exec()` (los mismos que arma cada
    diálogo real al confirmar) vienen precargados de antemano."""

    def __init__(self, aceptar=True, **atributos):
        self._aceptar = aceptar
        for nombre, valor in atributos.items():
            setattr(self, nombre, valor)

    def exec(self):
        return QDialog.DialogCode.Accepted if self._aceptar else QDialog.DialogCode.Rejected


def _mockear_dialogo_modificar(monkeypatch, *, aceptar=True, **atributos):
    monkeypatch.setattr(
        pagos_modulo, "_DialogoModificarPago",
        lambda conn, registro, profesional, parent=None: _DialogoFalso(aceptar, **atributos),
    )


def _mockear_dialogo_refinanciar(monkeypatch, *, aceptar=True, **atributos):
    monkeypatch.setattr(
        pagos_modulo, "_DialogoRefinanciarPlan",
        lambda conn, plan, profesional, parent=None: _DialogoFalso(aceptar, **atributos),
    )


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
    # `confirmar_datos_antes_de_crear` (Registrar pago/Guardar plan de pagos)
    # pasa a preguntar con `QMessageBox.question` en el camino feliz, antes
    # sin mockear acá (solo lo necesitaban los pocos tests de "¿período
    # anterior?"/"¿eliminar?", que lo mockean ellos mismos) — default a
    # "Yes" para no bloquear ningún test existente que no se ocupe de esto
    # en particular; los que sí quieren probar "cancelar" lo vuelven a
    # mockear en su propio cuerpo, pisando este default.
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def _crear_profesional(conn, saldo=10000):
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, SaldoCuentaActual) VALUES ('R', 'Gómez', ?)",
        (saldo,),
    )
    conn.commit()
    return conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]


def _seleccionar_profesional(panel, id_profesional):
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))


def test_combo_registrar_pago_no_ofrece_categoria_b(qtbot, conn):
    """Confirmado por la clienta: "no reciben ningún cargo ni tienen que
    abonar nada, todo lo que se les carge queda bonificado" —
    `registrar_pago` ya lo bloquea a nivel de negocio, sacarlo del combo
    evita que el operador llegue a chocar con ese error."""
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="B", Apellido="Bonificado")
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos

    categorias = {
        obtener_repositorio(conn, "Profesional").obtener(panel.combo_profesional.itemData(i))[
            "CategoriaProfesional"
        ]
        for i in range(panel.combo_profesional.count())
        if panel.combo_profesional.itemData(i) is not None
    }
    assert "B" not in categorias


def test_registrar_pagos_reiniciar_vuelve_filtro_y_formulario_al_default(qtbot, conn):
    """Punto #1.4: `reiniciar()` (disparado también desde `showEvent` y
    desde F3) vuelve "Profesional" (el mismo combo que filtra la tabla)
    a "Todos los profesionales", Período al actual y Monto a cero."""
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.campo_periodo.setText("2020-01")
    panel.spin_monto.setValue(500)

    panel.reiniciar()

    assert panel.combo_profesional.currentData() is None
    assert panel.campo_periodo.text() == periodo_actual(conn)
    assert panel.spin_monto.value() == 0


def test_planes_de_pago_reiniciar_vuelve_combo_y_spins_al_default(qtbot, conn):
    """Punto #1.4: mismo criterio que "Registrar pagos" — vuelve
    "Profesional" a "Seleccionar profesional…" y cuotas/interés a su
    default."""
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_cuotas.setValue(12)
    panel.spin_interes.setValue(5)

    panel.reiniciar()

    assert panel.combo_profesional.currentData() is None
    assert panel.spin_cuotas.value() == 3
    assert panel.spin_interes.value() == 0


def test_registrar_pago_sin_monto_no_persiste(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    _seleccionar_profesional(pantalla.panel_pagos, id_profesional)
    pantalla.panel_pagos._registrar()
    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 0


def test_registrar_pago_periodo_invalido_no_persiste(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    _seleccionar_profesional(pantalla.panel_pagos, id_profesional)
    pantalla.panel_pagos.spin_monto.setValue(-1000)
    pantalla.panel_pagos.campo_periodo.setText("no es un período")
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


def test_registrar_pago_mes_anterior_regenera_tambien_el_pdf(qtbot, conn, monkeypatch, tmp_path):
    """Bug real reportado por la clienta: la grilla de mensajería ya
    mostraba bien el estado ("no enviada"), pero el PDF en disco de la
    liquidación del mes en curso quedaba con los números de ANTES del
    pago — nunca se regeneraba de verdad."""
    id_profesional = _crear_profesional(conn, saldo=10000)
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, IdCodigo="R1")
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15', "
        "CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1",
        (str(tmp_path),),
    )
    emitir_liquidacion(conn, id_profesional=id_profesional, periodo="2026-08")
    conn.commit()

    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-1000)
    panel.campo_periodo.setText("2026-07")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    panel._registrar()

    emisiones = obtener_repositorio(conn, "LiquidacionEmitida").listar(
        IdProfesional=id_profesional, Periodo="2026-08",
    )
    emision = max(emisiones, key=lambda f: f["IdLiquidacion"])  # la regenerada, no la original
    assert emision["NombreArchivo"] is not None
    assert (tmp_path / "Profesionales" / "R1 - Gómez" / emision["NombreArchivo"]).exists()


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

def test_seleccionar_fila_habilita_modificar_y_eliminar_sin_tocar_el_formulario(qtbot, conn):
    """Pedido explícito de la clienta: "Modificar pago" pasa a un cuadro
    de diálogo propio — seleccionar una fila ya no precarga el
    formulario de alta (que ahora es exclusivo de "Registrar pago"
    nuevo), solo habilita los botones "Modificar pago"/"Eliminar pago"."""
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    periodo = panel.campo_periodo.text()
    _seleccionar_profesional(panel, id_profesional)
    panel.combo_medio_pago.setCurrentText("Transferencia a cta Celeste")
    panel.combo_cuenta_receptora.setCurrentText("CA Banco Macro - Celeste")
    panel.spin_monto.setValue(-500)
    panel._registrar()  # resetea el formulario al confirmar

    assert not panel.boton_modificar.isEnabled()
    assert not panel.boton_eliminar.isEnabled()

    panel.tabla.selectRow(0)
    assert panel.boton_modificar.isEnabled()
    assert panel.boton_eliminar.isEnabled()
    # el formulario de alta sigue en su estado reseteado, sin tocar
    assert panel.combo_profesional.currentData() is None
    assert panel.spin_monto.value() == 0
    assert panel.campo_periodo.text() == periodo


def test_modificar_pago_seleccionado_ajusta_saldo_y_marca_modificado(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn, saldo=1000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-400)
    panel._registrar()  # saldo: 600

    panel.tabla.selectRow(0)
    _mockear_dialogo_modificar(
        monkeypatch, periodo_imputado=periodo_actual(conn), monto=-600, medio_pago="Efectivo",
        cuenta_receptora=None,
    )
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


def test_modificar_pago_cancelando_el_dialogo_no_cambia_nada(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn, saldo=1000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-400)
    panel._registrar()

    panel.tabla.selectRow(0)
    _mockear_dialogo_modificar(monkeypatch, aceptar=False, monto=-999)
    panel._modificar()

    fila = conn.execute("SELECT Monto, RegistroModificado FROM HistorialPagos").fetchone()
    assert fila["Monto"] == -400
    assert fila["RegistroModificado"] == 0


def test_modificar_pago_a_mes_anterior_regenera_liquidacion_del_mes_en_curso(qtbot, conn, monkeypatch):
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
    _mockear_dialogo_modificar(
        monkeypatch, periodo_imputado="2026-07", monto=-1000, medio_pago="Efectivo", cuenta_receptora=None,
    )  # se corrige: era del mes anterior
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
    panel.spin_interes.setValue(5)
    panel._guardar()

    assert conn.execute("SELECT COUNT(*) c FROM PlanPago").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM CuotaPlan").fetchone()["c"] == 3
    assert panel.tabla.item(0, 8).text() == "Activo"
    assert panel.tabla.item(0, 4).text() == "5.0%"  # interés mensual
    assert panel.tabla.item(0, 6).text() == "3"  # cuotas restantes
    assert panel.tabla.item(0, 7).text() == formatear_moneda(6900)  # saldo restante (con interés)
    alineacion_derecha = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    for columna in (2, 3, 4, 5, 6, 7):  # monto, cuotas, interés, importe, cuotas restantes, saldo
        assert panel.tabla.item(0, columna).textAlignment() == alineacion_derecha


def test_botones_planes_pago_segun_si_hay_plan_activo(qtbot, conn):
    """"Guardar nuevo plan de pagos" se bloquea (no solo falla después del
    clic) si el profesional elegido ya tiene un plan vigente. "Refinanciar"/
    "Cancelar" (pedido explícito de la clienta) ya NO dependen del
    profesional del combo — recién se habilitan al elegir, en la TABLA,
    la fila de un plan todavía Activo."""
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    assert panel.boton_guardar.isEnabled()
    assert not panel.boton_refinanciar.isEnabled()
    assert not panel.boton_cancelar.isEnabled()

    panel.spin_monto.setValue(6000)
    panel._guardar()

    assert not panel.boton_guardar.isEnabled()
    assert not panel.boton_refinanciar.isEnabled()  # todavía sin fila elegida en la tabla
    assert not panel.boton_cancelar.isEnabled()

    panel.tabla.selectRow(0)
    assert panel.boton_refinanciar.isEnabled()
    assert panel.boton_cancelar.isEnabled()


def test_botones_secundarios_de_pagos_son_celestes(qtbot, conn):
    """Mismo criterio que Registro de ausencias/Cargos especiales: los
    botones "aparte" del principal de cada solapa usan "botonSecundario"
    (celeste, mismo alto que el botón principal)."""
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    from PySide6.QtWidgets import QPushButton

    textos_secundarios_registrar = {"Modificar pago", "Eliminar pago", "Deshacer último movimiento"}
    encontrados = {
        b.text() for b in pantalla.panel_pagos.findChildren(QPushButton)
        if b.objectName() == "botonSecundario" and b.text() in textos_secundarios_registrar
    }
    assert encontrados == textos_secundarios_registrar

    assert pantalla.panel_planes.boton_refinanciar.objectName() == "botonSecundario"
    assert pantalla.panel_planes.boton_cancelar.objectName() == "botonSecundario"
    assert pantalla.panel_planes.boton_guardar.objectName() == "botonPrimario"


def test_paneles_de_pagos_usan_el_fondo_claro_de_la_solapa(qtbot, conn):
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_pagos.objectName() == "panelSolapa"
    assert pantalla.panel_planes.objectName() == "panelSolapa"
    assert pantalla.panel_estado_cuenta.objectName() == "panelSolapa"


def test_guardar_con_plan_activo_no_crea_un_segundo(qtbot, conn):
    """DC-09 §3.6: un profesional no puede tener dos planes activos. El
    botón ya viene bloqueado (test de arriba); esto cubre que la
    validación de negocio también sostiene el bloqueo si se llama igual."""
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(6000)
    panel._guardar()

    panel._guardar()  # el profesional ya tiene un plan activo

    planes = conn.execute("SELECT Estado FROM PlanPago").fetchall()
    assert [p["Estado"] for p in planes] == ["Activo"]


def test_refinanciar_plan_cancela_el_vigente_y_crea_uno_nuevo(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(6000)
    panel._guardar()

    panel.tabla.selectRow(0)
    _mockear_dialogo_refinanciar(monkeypatch, monto=3000, cantidad_cuotas=3, porcentaje_interes=0)
    panel._refinanciar()

    planes = conn.execute("SELECT Estado FROM PlanPago ORDER BY IdPlan").fetchall()
    assert [p["Estado"] for p in planes] == ["Cancelado", "Activo"]


def test_refinanciar_sin_seleccion_avisa_y_no_crea(qtbot, conn):
    """Pedido explícito de la clienta: "Refinanciar plan seleccionado"
    opera sobre la fila elegida en la TABLA, no sobre el profesional del
    combo — sin ninguna fila seleccionada, avisa y no hace nada."""
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel._refinanciar()
    assert conn.execute("SELECT COUNT(*) c FROM PlanPago").fetchone()["c"] == 0


def test_cancelar_plan_suma_pendientes_al_saldo_anterior(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=0)
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, SaldoCuentaAnterior=6000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_cuotas.setValue(3)
    panel._guardar()  # descuenta 6000 de SaldoCuentaAnterior -> queda en 0

    panel.tabla.selectRow(0)
    panel._cancelar()  # QMessageBox.question mockeado a "Yes" por el fixture autouse

    estado = conn.execute("SELECT Estado FROM PlanPago").fetchone()["Estado"]
    assert estado == "Cancelado"
    saldo = conn.execute(
        "SELECT SaldoCuentaAnterior FROM Profesional WHERE IdProfesional = ?", (id_profesional,)
    ).fetchone()["SaldoCuentaAnterior"]
    assert saldo == pytest.approx(6000)  # las 3 cuotas pendientes vuelven a ser saldo atrasado


def test_cancelar_plan_responde_no_al_cartel_no_cambia_nada(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn, saldo=0)
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, SaldoCuentaAnterior=6000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_cuotas.setValue(3)
    panel._guardar()

    panel.tabla.selectRow(0)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    panel._cancelar()

    estado = conn.execute("SELECT Estado FROM PlanPago").fetchone()["Estado"]
    assert estado == "Activo"


def test_cancelar_sin_seleccion_avisa_y_no_falla(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel._cancelar()  # no debe fallar aunque no haya nada seleccionado en la tabla


def test_dialogo_refinanciar_sugiere_saldo_atrasado_mas_cuotas_del_plan_a_reemplazar(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=0)
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, SaldoCuentaAnterior=6000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_cuotas.setValue(3)
    panel._guardar()  # deja SaldoCuentaAnterior en 0, con 6000 en cuotas pendientes del plan nuevo

    plan = obtener_repositorio(conn, "PlanPago").listar(IdProfesional=id_profesional)[0]
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    dialogo = pagos_modulo._DialogoRefinanciarPlan(conn, plan, profesional)
    qtbot.addWidget(dialogo)
    # 0 de saldo (ya consumido por "Guardar nuevo plan de pagos") + 6000
    # de las cuotas pendientes del plan que este diálogo va a reemplazar.
    assert dialogo.spin_monto.value() == pytest.approx(6000)


def test_combos_profesional_son_buscables_por_codigo_o_nombre(qtbot, conn):
    """Confirmado por la clienta: el selector de profesional buscable
    corre en todos los formularios del sistema, este incluido — tanto en
    Registrar pago como en Planes de pago."""
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_pagos, pantalla.panel_planes):
        completador = panel.combo_profesional.completer()
        assert isinstance(completador.model(), _ProxyBusquedaSinAcentos)


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


def test_tabla_planes_pago_muestra_todos_los_r_y_ordena_por_columna(qtbot, conn):
    id_profesional_1 = _crear_profesional(conn)
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional_1)
    panel.spin_monto.setValue(6000)
    panel._guardar()

    _seleccionar_profesional(panel, id_profesional_2)
    panel.spin_monto.setValue(3000)
    panel._guardar()

    panel.combo_profesional.setCurrentIndex(0)  # "Seleccionar profesional…": ve la tabla completa
    assert panel.tabla.rowCount() == 2

    panel.tabla.horizontalHeader().sectionClicked.emit(2)  # "Monto refinanciado" ascendente
    montos_asc = [panel.tabla.item(f, 2).text() for f in range(panel.tabla.rowCount())]
    assert montos_asc == [formatear_moneda(3000), formatear_moneda(6000)]

    panel.tabla.horizontalHeader().sectionClicked.emit(2)  # de nuevo -> descendente
    montos_desc = [panel.tabla.item(f, 2).text() for f in range(panel.tabla.rowCount())]
    assert montos_desc == [formatear_moneda(6000), formatear_moneda(3000)]


def test_combo_profesional_planes_pago_filtra_la_tabla(qtbot, conn):
    id_profesional_1 = _crear_profesional(conn)
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_planes
    _seleccionar_profesional(panel, id_profesional_1)
    panel.spin_monto.setValue(6000)
    panel._guardar()

    _seleccionar_profesional(panel, id_profesional_2)
    panel.spin_monto.setValue(3000)
    panel._guardar()

    assert panel.tabla.rowCount() == 1  # sigue filtrado al profesional 2, recién guardado

    _seleccionar_profesional(panel, id_profesional_1)
    assert panel.tabla.rowCount() == 1


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


def test_fecha_de_carga_usa_dia_de_la_semana_abreviado(qtbot, conn):
    """Antes iba con el nombre completo del día ("martes"), la clienta
    pidió abreviarlo ("mar") al revisar esta pantalla."""
    from datetime import datetime

    from app.negocio.dias import fecha_a_dia_semana

    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-500)
    panel._registrar()

    fecha_carga = conn.execute("SELECT FechaHoraCarga FROM HistorialPagos").fetchone()["FechaHoraCarga"]
    dia_completo = fecha_a_dia_semana(datetime.fromisoformat(fecha_carga).date())
    texto = panel.tabla.item(0, 0).text()
    assert texto.startswith(dia_completo[:3].lower() + " ")
    assert dia_completo.lower() not in texto


def test_saldo_anterior_y_nuevo_saldo_se_colorean_en_negativo(qtbot, conn):
    """Confirmado por la clienta: Saldo anterior y Nuevo saldo respetan el
    mismo color rojo-si-negativo que Monto, igual que en todo el sistema
    (COLOR_ROJO, no el "red" puro que usaba antes esta tabla)."""
    from PySide6.QtGui import QColor

    from app.gui.estilos import COLOR_ROJO

    id_profesional = _crear_profesional(conn, saldo=100)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-500)  # deja el saldo en negativo
    panel._registrar()

    assert panel.tabla.item(0, 6).foreground().color() != QColor(COLOR_ROJO)  # saldo anterior: 100, positivo
    assert panel.tabla.item(0, 7).foreground().color() == QColor(COLOR_ROJO)  # nuevo saldo: -400, negativo
    assert panel.tabla.item(0, 3).foreground().color() == QColor(COLOR_ROJO)  # el Monto también


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


def test_tecla_delete_elimina_el_pago_igual_que_el_boton(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn, saldo=1000)
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_pagos
    _seleccionar_profesional(panel, id_profesional)
    panel.spin_monto.setValue(-400)
    panel._registrar()

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel.tabla.selectRow(0)
    qtbot.keyClick(panel.tabla, Qt.Key.Key_Delete)

    assert conn.execute("SELECT COUNT(*) c FROM HistorialPagos").fetchone()["c"] == 0


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


def test_solapa_estado_cuenta_es_tercera_solapa(qtbot, conn):
    """Antes vivía en la pantalla separada "Estado de cuenta" (F25),
    suprimida — ahora es la tercera solapa de Pagos."""
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_estado_cuenta is not None


def test_solapa_estado_cuenta_muestra_saldos_y_tabla_igual_a_registrar_pago(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=1234.5)
    conn.execute(
        "UPDATE Profesional SET SaldoCuentaAnterior = -678.9 WHERE IdProfesional = ?", (id_profesional,)
    )
    conn.commit()
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_estado_cuenta
    _seleccionar_profesional(panel, id_profesional)

    assert panel.etiquetas_resumen[0].text() == (
        f'Saldo actual: <span style="color:black;">{formatear_moneda(1234.5)}</span>'
    )
    assert panel.etiquetas_resumen[1].text() == (
        f'Saldo anterior: <span style="color:{COLOR_ROJO};">{formatear_moneda(-678.9)}</span>'
    )

    assert [panel.tabla.horizontalHeaderItem(i).text() for i in range(panel.tabla.columnCount())] == [
        "Fecha de carga", "Período imputado", "Monto", "Medio de pago", "Cuenta receptora",
        "Saldo anterior", "Nuevo saldo", "Registro modificado", "Es ajuste",
    ]

    registrar_pago(
        conn, id_profesional=id_profesional, monto=-500, medio_pago="Transferencia",
        periodo_imputado=periodo_actual(conn),
    )
    panel.actualizar()
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 2).text() == "-$ 500,00"
    assert panel.tabla.item(0, 2).foreground().color() == QColor(COLOR_ROJO)


def test_solapa_estado_cuenta_combo_es_buscable_por_codigo_o_nombre(qtbot, conn):
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    completador = pantalla.panel_estado_cuenta.combo_profesional.completer()
    assert isinstance(completador.model(), _ProxyBusquedaSinAcentos)


def test_estado_cuenta_pagos_tiene_filtro_a_la_izquierda_y_datos_uno_por_linea(qtbot, conn):
    """A pedido de la clienta: mismo rediseño que Estado de cuenta de
    Cargos especiales — el filtro de profesional a la izquierda y cada
    dato del resumen en su propia línea."""
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    assert len(pantalla.panel_estado_cuenta.etiquetas_resumen) == 4


def test_spin_monto_selecciona_todo_el_texto_al_recibir_foco(qtbot):
    """Pedido de la clienta ("en todos los cuadros de texto similares
    del sistema"): al enfocar el campo de monto, se selecciona todo el
    contenido para poder escribir en limpio sin borrar a mano. Se
    instancia `_SpinMonto` aparte (no dentro de `_PanelRegistrarPago`,
    que vive en un `QScrollArea` cuya visibilidad real no depende solo
    de `show()`) — el comportamiento es del widget en sí, no de la
    pantalla que lo contiene."""
    from app.gui.pantallas.pagos import _SpinMonto

    spin = _SpinMonto()
    spin.setValue(1234.5)
    qtbot.addWidget(spin)
    spin.show()
    qtbot.waitExposed(spin)
    spin.setFocus()
    qtbot.waitUntil(lambda: spin.hasFocus())
    qtbot.wait(10)  # deja correr el QTimer.singleShot(0, ...)
    assert spin.lineEdit().selectedText() == spin.lineEdit().text()
    assert spin.lineEdit().selectedText() != ""


def test_estado_cuenta_pagos_reiniciar_no_rompe(qtbot, conn):
    """F3 ("Reiniciar solapa") acá no tiene ningún filtro que resetear
    (Profesional se conserva a propósito) — antes esta pestaña no tenía
    reiniciar() en absoluto; confirma que ahora existe y no rompe."""
    pantalla = PantallaPagos(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_estado_cuenta.reiniciar()
