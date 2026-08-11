import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.aumentos import PantallaAumentos


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


def _crear_edificio_con_consultorio(conn, valor_regular=1000, valor_aislada=1500):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute(
        "INSERT INTO Consultorio (IdUnidad, NumeroConsultorio, ValorHoraRegularActual, ValorHoraAisladaActual) "
        "VALUES (?, 1, ?, ?)",
        (id_unidad, valor_regular, valor_aislada),
    )
    conn.commit()
    return conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]


def test_simular_llena_la_tabla_sin_recursion_infinita(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    pantalla.spin_porcentaje.setValue(10)
    pantalla._simular()  # antes del fix esto podía entrar en recursión infinita vía itemChanged
    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 2).text() == "1100.00"


def test_diferencia_se_calcula_automaticamente(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    pantalla.spin_porcentaje.setValue(10)
    pantalla._simular()
    assert pantalla.tabla.item(0, 3).text() == "+100.00"


def test_editar_celda_recalcula_diferencia(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    pantalla.spin_porcentaje.setValue(10)
    pantalla._simular()

    pantalla.tabla.item(0, 2).setText("1200.00")  # override manual del valor regular nuevo
    assert pantalla.tabla.item(0, 3).text() == "+200.00"


def test_confirmar_sin_simular_no_falla(qtbot, conn):
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    pantalla._confirmar()  # tabla vacía -> solo advierte, no debe lanzar excepción


def test_confirmar_actualiza_valores_de_consultorio(qtbot, conn):
    id_consultorio = _crear_edificio_con_consultorio(conn, valor_regular=1000, valor_aislada=1500)
    pantalla = PantallaAumentos(conn)
    qtbot.addWidget(pantalla)
    pantalla.spin_porcentaje.setValue(10)
    pantalla._simular()
    pantalla._confirmar()

    fila = conn.execute(
        "SELECT ValorHoraRegularActual, ValorHoraRegularAnterior FROM Consultorio WHERE IdConsultorio = ?",
        (id_consultorio,),
    ).fetchone()
    assert fila["ValorHoraRegularActual"] == 1100.0
    assert fila["ValorHoraRegularAnterior"] == 1000.0
    assert conn.execute("SELECT COUNT(*) c FROM AumentoAplicado").fetchone()["c"] == 1
