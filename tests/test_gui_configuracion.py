import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.configuracion import ConfiguracionGeneral


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


def test_carga_valores_existentes(qtbot, conn):
    conn.execute("UPDATE Configuracion SET NombreEspacio = 'Mi Espacio', HoraInicioGrilla = 7 WHERE IdConfiguracion = 1")
    conn.commit()
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    assert pantalla._entradas["NombreEspacio"].text() == "Mi Espacio"
    assert pantalla._entradas["HoraInicioGrilla"].text() == "7.0"


def test_guardar_persiste_texto_y_numero(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["NombreEspacio"].setText("Espacio Nuevo")
    pantalla._entradas["ToleranciaDeudaDescuento"].setText("500")
    pantalla._guardar()

    fila = conn.execute("SELECT * FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["NombreEspacio"] == "Espacio Nuevo"
    assert fila["ToleranciaDeudaDescuento"] == 500.0


def test_guardar_persiste_booleano(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["ModoFechaFicticia"].setChecked(True)
    pantalla._guardar()
    fila = conn.execute("SELECT ModoFechaFicticia FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["ModoFechaFicticia"] == 1


def test_guardar_con_numero_invalido_no_persiste(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    valor_original = conn.execute(
        "SELECT ToleranciaDeudaDescuento FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()["ToleranciaDeudaDescuento"]

    pantalla._entradas["ToleranciaDeudaDescuento"].setText("no es un número")
    pantalla._guardar()

    fila = conn.execute("SELECT ToleranciaDeudaDescuento FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["ToleranciaDeudaDescuento"] == valor_original
