import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.reinicio_prueba import (
    PantallaReinicioPrueba,
    _DialogoAjustarSaldo,
    _PanelDepurarHistorial,
    _PanelSaldosIniciales,
)
from app.negocio.dias import periodo_actual, sumar_meses
from app.negocio.seguridad import establecer_contrasena_maestra
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_profesional(conn, categoria="R", apellido="Lo Veci", id_codigo=None):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional=categoria, Apellido=apellido, IdCodigo=id_codigo,
    )


# --- _PanelSaldosIniciales ---------------------------------------------------------------

def test_panel_saldos_lista_r_a_y_x_en_orden_natural(qtbot, conn):
    """Confirmado por la clienta: R, luego A, luego X, cada uno por
    código — `clave_orden_profesional` ya da este orden solo, con la
    jerarquía de categorías de todo el sistema (B, R, A, E, X, C)."""
    _crear_profesional(conn, "R", "Lo Veci", "R14")
    _crear_profesional(conn, "R", "Pérez", "R2")
    _crear_profesional(conn, "A", "Gómez", "A1")
    _crear_profesional(conn, "X", "Inactivo", "X1")
    _crear_profesional(conn, "B", "Bonificado", "B1")

    panel = _PanelSaldosIniciales(conn)
    qtbot.addWidget(panel)

    codigos = [panel.tabla.item(fila, 0).text().split(" - ")[0] for fila in range(panel.tabla.rowCount())]
    assert codigos == ["R2", "R14", "A1", "X1"]


def test_ajustar_saldo_seleccionado_actualiza_la_tabla(qtbot, conn, monkeypatch):
    id_r = _crear_profesional(conn, "R", "Lo Veci", "R1")
    obtener_repositorio(conn, "Profesional").actualizar(id_r, SaldoCuentaAnterior=9999)

    panel = _PanelSaldosIniciales(conn)
    qtbot.addWidget(panel)
    panel.tabla.selectRow(0)
    assert panel.boton_ajustar.isEnabled()

    class _DialogoFalso:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return _DialogoAjustarSaldo.DialogCode.Accepted

        def saldo(self):
            return 0.0

    monkeypatch.setattr("app.gui.pantallas.reinicio_prueba._DialogoAjustarSaldo", _DialogoFalso)
    panel._ajustar_seleccionado()

    actualizado = obtener_repositorio(conn, "Profesional").obtener(id_r)
    assert actualizado["SaldoCuentaAnterior"] == pytest.approx(0.0)


def test_boton_ajustar_deshabilitado_sin_seleccion(qtbot, conn):
    _crear_profesional(conn, "R", "Lo Veci", "R1")
    panel = _PanelSaldosIniciales(conn)
    qtbot.addWidget(panel)
    assert not panel.boton_ajustar.isEnabled()


def test_poner_todos_en_cero(qtbot, conn):
    id_r = _crear_profesional(conn, "R", "Lo Veci", "R1")
    id_a = _crear_profesional(conn, "A", "Gómez", "A1")
    obtener_repositorio(conn, "Profesional").actualizar(id_r, SaldoCuentaAnterior=5000)
    obtener_repositorio(conn, "Profesional").actualizar(id_a, SaldoCuentaAnterior=-200)

    panel = _PanelSaldosIniciales(conn)
    qtbot.addWidget(panel)
    panel._poner_todos_en_cero()

    assert obtener_repositorio(conn, "Profesional").obtener(id_r)["SaldoCuentaAnterior"] == 0.0
    assert obtener_repositorio(conn, "Profesional").obtener(id_a)["SaldoCuentaAnterior"] == 0.0


def test_ajustar_saldo_no_toca_el_actual(qtbot, conn):
    id_r = _crear_profesional(conn, "R", "Lo Veci", "R1")
    obtener_repositorio(conn, "Profesional").actualizar(id_r, SaldoCuentaActual=777, SaldoCuentaAnterior=1)

    panel = _PanelSaldosIniciales(conn)
    qtbot.addWidget(panel)
    panel.tabla.selectRow(0)

    dialogo = _DialogoAjustarSaldo("R1 - Lo Veci", 1.0)
    qtbot.addWidget(dialogo)
    dialogo.spin_saldo.setValue(50.0)
    dialogo.accept()

    assert dialogo.saldo() == pytest.approx(50.0)


def test_dialogo_ajustar_saldo_selecciona_el_importe_al_abrir(qtbot):
    """Pedido explícito de la clienta: el importe prefijado queda
    seleccionado al abrir el diálogo, para empezar a escribir encima y
    borrarlo a la vez."""
    dialogo = _DialogoAjustarSaldo("R1 - Lo Veci", 9999.0)
    qtbot.addWidget(dialogo)
    dialogo.show()
    qtbot.waitExposed(dialogo)
    qtbot.wait(10)  # el select-all corre en un QTimer.singleShot(0, ...)

    linea = dialogo.spin_saldo.lineEdit()
    assert linea.selectedText() == linea.text()


def test_buscar_profesional_filtra_la_tabla(qtbot, conn):
    """Mismo criterio que "Filtros que solo afectan la visualización":
    oculta filas sin distinguir mayúsculas ni acentos, por cualquier
    columna visible."""
    _crear_profesional(conn, "R", "Díaz", "R1")
    _crear_profesional(conn, "A", "Gómez", "A1")

    panel = _PanelSaldosIniciales(conn)
    qtbot.addWidget(panel)

    panel.campo_buscar.setText("diaz")
    assert panel.tabla.isRowHidden(0) is False
    assert panel.tabla.isRowHidden(1) is True

    panel.campo_buscar.clear()
    assert panel.tabla.isRowHidden(0) is False
    assert panel.tabla.isRowHidden(1) is False


def test_reiniciar_limpia_el_buscador(qtbot, conn):
    _crear_profesional(conn, "R", "Lo Veci", "R1")
    panel = _PanelSaldosIniciales(conn)
    qtbot.addWidget(panel)
    panel.campo_buscar.setText("algo")

    panel.reiniciar()

    assert panel.campo_buscar.text() == ""


def test_foco_inicial_queda_en_el_buscador(qtbot, conn):
    panel = _PanelSaldosIniciales(conn)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitExposed(panel)
    qtbot.waitUntil(lambda: panel.campo_buscar.hasFocus())


# --- _PanelDepurarHistorial ---------------------------------------------------------------

def test_panel_depurar_arranca_en_el_mes_anterior_al_actual(qtbot, conn):
    panel = _PanelDepurarHistorial(conn)
    qtbot.addWidget(panel)
    assert panel.selector_periodo.periodo() == sumar_meses(periodo_actual(conn), -1)


def test_boton_depurar_deshabilitado_sin_nada_para_borrar(qtbot, conn):
    panel = _PanelDepurarHistorial(conn)
    qtbot.addWidget(panel)
    panel.selector_periodo.set_periodo("2000-01")
    panel.actualizar()
    assert not panel.boton_depurar.isEnabled()


def test_boton_depurar_habilitado_con_registros_a_borrar(qtbot, conn):
    id_r = _crear_profesional(conn)
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_r, Monto=-1, PeriodoImputado="2026-10")

    panel = _PanelDepurarHistorial(conn)
    qtbot.addWidget(panel)
    panel.selector_periodo.set_periodo("2026-10")
    panel.actualizar()
    assert panel.boton_depurar.isEnabled()


def test_depurar_sin_contrasena_maestra_avisa_y_no_borra_nada(qtbot, conn):
    id_r = _crear_profesional(conn)
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_r, Monto=-1, PeriodoImputado="2026-10")

    panel = _PanelDepurarHistorial(conn)
    qtbot.addWidget(panel)
    panel.selector_periodo.set_periodo("2026-10")
    panel.actualizar()
    panel._depurar()

    assert len(obtener_repositorio(conn, "HistorialPagos").listar()) == 1


def test_depurar_con_contrasena_incorrecta_no_borra_nada(qtbot, conn, monkeypatch):
    id_r = _crear_profesional(conn)
    establecer_contrasena_maestra(conn, "correcta123")
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_r, Monto=-1, PeriodoImputado="2026-10")

    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("incorrecta", True)),
    )

    panel = _PanelDepurarHistorial(conn)
    qtbot.addWidget(panel)
    panel.selector_periodo.set_periodo("2026-10")
    panel.actualizar()
    panel._depurar()

    assert len(obtener_repositorio(conn, "HistorialPagos").listar()) == 1


def test_depurar_con_contrasena_correcta_borra_y_actualiza_la_tabla(qtbot, conn, monkeypatch):
    id_r = _crear_profesional(conn)
    establecer_contrasena_maestra(conn, "correcta123")
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_r, Monto=-1, PeriodoImputado="2026-10")
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_r, Monto=-1, PeriodoImputado="2026-11")

    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("correcta123", True)),
    )

    panel = _PanelDepurarHistorial(conn)
    qtbot.addWidget(panel)
    panel.selector_periodo.set_periodo("2026-10")
    panel.actualizar()
    panel._depurar()

    restantes = obtener_repositorio(conn, "HistorialPagos").listar()
    assert len(restantes) == 1
    assert restantes[0]["PeriodoImputado"] == "2026-11"
    assert not panel.boton_depurar.isEnabled()


def test_cancelar_el_pedido_de_contrasena_no_borra_nada(qtbot, conn, monkeypatch):
    id_r = _crear_profesional(conn)
    establecer_contrasena_maestra(conn, "correcta123")
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_r, Monto=-1, PeriodoImputado="2026-10")

    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)),
    )

    panel = _PanelDepurarHistorial(conn)
    qtbot.addWidget(panel)
    panel.selector_periodo.set_periodo("2026-10")
    panel.actualizar()
    panel._depurar()

    assert len(obtener_repositorio(conn, "HistorialPagos").listar()) == 1


def test_cancelar_el_cartel_de_confirmacion_no_pide_contrasena_ni_borra(qtbot, conn, monkeypatch):
    id_r = _crear_profesional(conn)
    establecer_contrasena_maestra(conn, "correcta123")
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_r, Monto=-1, PeriodoImputado="2026-10")

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    llamados = []
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: (llamados.append(1), ("", False))[1]),
    )

    panel = _PanelDepurarHistorial(conn)
    qtbot.addWidget(panel)
    panel.selector_periodo.set_periodo("2026-10")
    panel.actualizar()
    panel._depurar()

    assert llamados == []
    assert len(obtener_repositorio(conn, "HistorialPagos").listar()) == 1


def test_reiniciar_vuelve_el_periodo_al_mes_anterior(qtbot, conn):
    panel = _PanelDepurarHistorial(conn)
    qtbot.addWidget(panel)
    panel.selector_periodo.set_periodo("2000-01")
    panel.reiniciar()
    assert panel.selector_periodo.periodo() == sumar_meses(periodo_actual(conn), -1)


# --- PantallaReinicioPrueba ---------------------------------------------------------------

def test_pantalla_tiene_las_dos_solapas_en_orden(qtbot, conn):
    pantalla = PantallaReinicioPrueba(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.pestanas.tabText(0) == "Saldos iniciales"
    assert pantalla.pestanas.tabText(1) == "Depurar historial de prueba"
    assert pantalla.panel_saldos.objectName() == "panelSolapa"
    assert pantalla.panel_depurar.objectName() == "panelSolapa"


def test_tablas_excluidas_del_tab(qtbot, conn):
    pantalla = PantallaReinicioPrueba(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_saldos.tabla.focusPolicy() == Qt.FocusPolicy.ClickFocus
    assert pantalla.panel_depurar.tabla.focusPolicy() == Qt.FocusPolicy.ClickFocus
