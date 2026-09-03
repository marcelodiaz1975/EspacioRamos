import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.liquidacion import ProcesoLiquidacion
from app.negocio.dias import periodo_actual


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


def test_lista_solo_profesionales_categoria_r(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('A', 'Pérez')")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.rowCount() == 1
    assert "Gómez" in pantalla.tabla.item(0, 1).text()


def test_calcula_monto_a_generar_sin_reservas(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.item(0, 3).text() == "$ 0,00"
    assert pantalla.tabla.item(0, 4).text() == "Sin emitir"


def test_emitir_sin_carpeta_base_no_falla_ni_emite(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, IdCodigo) VALUES ('R', 'Gómez', 'R1')")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    pantalla._emitir_seleccionadas()
    assert conn.execute("SELECT COUNT(*) c FROM LiquidacionEmitida").fetchone()["c"] == 0


def test_emitir_seleccionadas_persiste_liquidacion_y_genera_pdf(qtbot, conn, tmp_path):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, IdCodigo) VALUES ('R', 'Gómez', 'R1')")
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)

    pantalla._emitir_seleccionadas()

    fila = conn.execute("SELECT * FROM LiquidacionEmitida").fetchone()
    assert fila is not None
    assert fila["Periodo"] == periodo_actual(conn)
    assert fila["NombreArchivo"] is not None
    assert (tmp_path / "Profesionales" / "R1" / fila["NombreArchivo"]).exists()


def test_emitir_sin_seleccionados_no_emite(qtbot, conn, tmp_path):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, IdCodigo) VALUES ('R', 'Gómez', 'R1')")
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    pantalla._casillas[0].setChecked(False)

    pantalla._emitir_seleccionadas()
    assert conn.execute("SELECT COUNT(*) c FROM LiquidacionEmitida").fetchone()["c"] == 0
