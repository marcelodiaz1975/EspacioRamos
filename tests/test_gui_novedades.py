import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.novedades import PantallaNovedades


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


def _preparar(conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute(
        "INSERT INTO Consultorio (IdUnidad, NumeroConsultorio, ValorHoraRegularActual) VALUES (?, 1, 1000)",
        (id_unidad,),
    )
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    conn.execute(
        "INSERT INTO ReservaRegular (IdProfesional, IdConsultorio, DiaSemana, HoraInicio, HoraFin, VigenciaInicio) "
        "VALUES (?, ?, 'Lunes', 9, 12, '2020-01-01')",
        (id_profesional, id_consultorio),
    )
    conn.commit()
    return id_profesional


def test_crear_vacacion_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaNovedades(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.campo_desde.setText("2026-09-01")
    panel.campo_hasta.setText("2026-09-07")
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 1
    assert panel.tabla.rowCount() == 1


def test_crear_licencia_sin_tipo_no_falla(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaNovedades(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.campo_desde.setText("2026-09-01")
    panel.campo_hasta.setText("2026-09-03")
    panel._crear()  # hay tipos de licencia sembrados por defecto
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 1


def test_crear_ausencia_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaNovedades(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.campo_desde.setText("2026-09-01")
    panel.campo_hasta.setText("2026-09-03")
    panel.campo_motivo.setText("Congreso")
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 1
    assert panel.tabla.item(0, 3).text() == "Congreso"


def test_crear_cargo_especial_sin_concepto_no_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaNovedades(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_cargos
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 0


def test_crear_cargo_especial_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaNovedades(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_cargos
    panel.campo_concepto.setText("ajuste manual")
    panel.spin_monto.setValue(1500)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1
    assert panel.tabla.item(0, 2).text() == "Ajuste manual"
