import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import COLOR_ROJO
from app.gui.pantallas.liquidacion import ProcesoLiquidacion
from app.negocio.dias import periodo_actual
from app.negocio.formato import formatear_moneda
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
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def _crear_profesional(conn, apellido="Gómez", id_codigo=None, saldo_anterior=0.0):
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, IdCodigo, SaldoCuentaAnterior) "
        "VALUES ('R', ?, ?, ?)",
        (apellido, id_codigo, saldo_anterior),
    )
    conn.commit()
    return conn.execute("SELECT IdProfesional FROM Profesional WHERE Apellido = ?", (apellido,)).fetchone()[
        "IdProfesional"
    ]


def test_periodo_por_defecto_es_el_actual(qtbot, conn):
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_emision.campo_periodo.text() == periodo_actual(conn)


def test_lista_solo_profesionales_categoria_r(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('A', 'Pérez')")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_emision.tabla.rowCount() == 1
    assert "Gómez" in pantalla.panel_emision.tabla.item(0, 1).text()


def test_nombre_profesional_usa_formato_canonico(qtbot, conn):
    _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_emision.tabla.item(0, 1).text() == "R1 - Lo Veci"


def test_calcula_monto_a_generar_sin_reservas(qtbot, conn):
    _crear_profesional(conn)
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_emision.tabla.item(0, 3).text() == "$ 0,00"
    assert pantalla.panel_emision.tabla.item(0, 4).text() == "Sin emitir"
    assert [
        pantalla.panel_emision.tabla.horizontalHeaderItem(i).text()
        for i in range(pantalla.panel_emision.tabla.columnCount())
    ] == ["Incluir", "Profesional", "Saldo anterior", "Monto a generar", "Estado"]


def test_saldo_anterior_negativo_se_colorea_en_rojo(qtbot, conn):
    _crear_profesional(conn, saldo_anterior=-500)
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    item = pantalla.panel_emision.tabla.item(0, 2)
    assert item.text() == formatear_moneda(-500)
    assert item.foreground().color() == QColor(COLOR_ROJO)


def test_ningun_profesional_seleccionado_por_defecto(qtbot, conn):
    _crear_profesional(conn)
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert all(not casilla.isChecked() for casilla in pantalla.panel_emision._casillas)


def test_orden_no_enviadas_arriba_y_luego_por_codigo(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    _crear_profesional(conn, apellido="Diez", id_codigo="R10")
    _crear_profesional(conn, apellido="Dos", id_codigo="R2")
    id_r5 = _crear_profesional(conn, apellido="Cinco", id_codigo="R5")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)

    # emite y marca como enviada la de R5 -> tiene que quedar al final pese al código
    from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio

    periodo = pantalla.panel_emision._periodo()
    emitir_liquidacion(conn, id_profesional=id_r5, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_r5, periodo=periodo, enviada=True)
    conn.commit()
    pantalla.panel_emision.actualizar()

    codigos = [pantalla.panel_emision.tabla.item(i, 1).text().split(" - ")[0] for i in range(3)]
    assert codigos == ["R2", "R10", "R5"]


def test_buscar_profesional_resalta_fila_sin_filtrar(qtbot, conn):
    _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    _crear_profesional(conn, apellido="Quito", id_codigo="R3")
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_emision

    assert panel.tabla.rowCount() == 2
    indice = panel.combo_buscar.findData(panel._filas[1]["profesional"]["IdProfesional"])
    panel.combo_buscar.setCurrentIndex(indice)

    assert panel.tabla.rowCount() == 2  # no filtra
    from app.gui.pantallas.liquidacion import _COLOR_RESALTADO

    assert panel.tabla.item(1, 1).background().color() == _COLOR_RESALTADO
    assert panel.tabla.item(0, 1).background().color() != _COLOR_RESALTADO


def test_emitir_sin_carpeta_base_no_falla_ni_emite(qtbot, conn):
    _crear_profesional(conn, id_codigo="R1")
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_emision._emitir_seleccionadas()
    assert conn.execute("SELECT COUNT(*) c FROM LiquidacionEmitida").fetchone()["c"] == 0


def test_emitir_seleccionadas_persiste_liquidacion_y_genera_pdf(qtbot, conn, tmp_path):
    _crear_profesional(conn, id_codigo="R1")
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_emision._casillas[0].setChecked(True)

    pantalla.panel_emision._emitir_seleccionadas()

    fila = conn.execute("SELECT * FROM LiquidacionEmitida").fetchone()
    assert fila is not None
    assert fila["Periodo"] == periodo_actual(conn)
    assert fila["NombreArchivo"] is not None
    assert (tmp_path / "Profesionales" / "R1" / fila["NombreArchivo"]).exists()


def test_emitir_sin_seleccionados_no_emite(qtbot, conn, tmp_path):
    _crear_profesional(conn, id_codigo="R1")
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)

    pantalla.panel_emision._emitir_seleccionadas()
    assert conn.execute("SELECT COUNT(*) c FROM LiquidacionEmitida").fetchone()["c"] == 0


def test_emitir_no_enviadas_emite_las_sin_emitir_y_las_no_enviadas(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    id_r1 = _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    id_r3 = _crear_profesional(conn, apellido="Quito", id_codigo="R3")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_emision

    from app.negocio.liquidaciones import emitir_liquidacion

    periodo = panel._periodo()
    emitir_liquidacion(conn, id_profesional=id_r1, periodo=periodo)  # queda "No enviada"
    conn.commit()
    panel.actualizar()

    panel._emitir_no_enviadas()

    filas = obtener_repositorio(conn, "LiquidacionEmitida").listar()
    profesionales_emitidos = {f["IdProfesional"] for f in filas}
    assert id_r1 in profesionales_emitidos
    assert id_r3 in profesionales_emitidos


def test_solapa_estado_cuenta_lista_liquidaciones_del_profesional(qtbot, conn):
    id_prof = _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_prof, Periodo="2026-07", FechaEmision="2026-07-05", MontoGenerado=1000,
        EstadoEnvio="Enviada", NombreArchivo="julio.pdf",
    )
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_prof, Periodo="2026-08", FechaEmision="2026-08-05", MontoGenerado=1100,
        EstadoEnvio="No enviada", NombreArchivo="agosto.pdf",
    )
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_estado_cuenta

    assert panel.tabla.rowCount() == 2
    assert panel.tabla.item(0, 0).text() == "2026-08"  # más reciente primero
    assert panel.tabla.item(0, 2).text() == formatear_moneda(1100)


def test_solapa_estado_cuenta_combo_es_buscable_por_codigo_o_nombre(qtbot, conn):
    from PySide6.QtCore import Qt

    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    completador = pantalla.panel_estado_cuenta.combo_profesional.completer()
    assert completador.filterMode() == Qt.MatchFlag.MatchContains
