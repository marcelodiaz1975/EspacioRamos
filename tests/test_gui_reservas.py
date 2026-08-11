import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.reservas import PantallaReservas


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


def _preparar(conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.commit()


def test_crear_reserva_regular_sin_conflicto_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1
    assert pantalla.panel_regulares.tabla.rowCount() == 1


def test_crear_reserva_regular_con_conflicto_pide_confirmacion_y_fuerza(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares._crear()  # primera reserva 9-10 Lunes

    pantalla.panel_regulares._crear()  # misma reserva de nuevo -> conflicto bloqueante
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 2  # forzada por QMessageBox mockeado


def test_finalizar_vigencia_actualiza_vigenciafin(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares._crear()
    pantalla.panel_regulares.tabla.selectRow(0)
    pantalla.panel_regulares._finalizar_vigencia()
    fila = conn.execute("SELECT VigenciaFin FROM ReservaRegular").fetchone()
    assert fila["VigenciaFin"] is not None


def test_crear_reserva_aislada_sin_conflicto_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1
    assert pantalla.panel_aisladas.tabla.item(0, 4).text() == "Confirmada"


def test_cancelar_reserva_aislada_cambia_estado(qtbot, conn):
    # 13-14 cae fuera de los bloques rígidos por defecto (9-11 y 18-21) para
    # que la cancelación el mismo día no choque con esa restricción aparte.
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.spin_desde.setValue(13)
    pantalla.panel_aisladas.spin_hasta.setValue(14)
    pantalla.panel_aisladas._crear()
    pantalla.panel_aisladas.tabla.selectRow(0)
    pantalla.panel_aisladas._cancelar()
    fila = conn.execute("SELECT Estado FROM ReservaAislada").fetchone()
    assert fila["Estado"] == "Cancelada"
