import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.llaves import PantallaLlaves


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


def _crear_llave_y_profesional(conn):
    conn.execute("INSERT INTO Llave (Descripcion, ValorDepositoActual) VALUES ('Llave principal', 1000)")
    id_llave = conn.execute("SELECT IdLlave FROM Llave").fetchone()["IdLlave"]
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    conn.commit()
    return id_llave, id_profesional


def test_seleccionar_llave_sin_tenencias_deshabilita_devolver(qtbot, conn):
    _crear_llave_y_profesional(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    assert pantalla.boton_entregar.isEnabled() is True
    assert pantalla.boton_devolver.isEnabled() is False


def test_entregar_llave_crea_tenencia_y_cargo_especial(qtbot, conn):
    id_llave, id_profesional = _crear_llave_y_profesional(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)

    from app.negocio.llaves import entregar_llave

    entregar_llave(conn, id_llave=id_llave, id_profesional=id_profesional, cobrar_deposito=True)
    conn.commit()
    pantalla._actualizar_tenencias()

    assert pantalla.tabla_tenencias.rowCount() == 1
    assert pantalla.boton_devolver.isEnabled() is True
    cargo = conn.execute("SELECT * FROM CargoEspecial WHERE IdProfesional = ?", (id_profesional,)).fetchone()
    assert cargo is not None
    assert cargo["Tipo"] == "Débito"


def test_devolver_llave_actualiza_tabla_y_deshabilita_boton(qtbot, conn):
    id_llave, id_profesional = _crear_llave_y_profesional(conn)
    from app.negocio.llaves import entregar_llave

    entregar_llave(conn, id_llave=id_llave, id_profesional=id_profesional, cobrar_deposito=True)
    conn.commit()

    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    assert pantalla.boton_devolver.isEnabled() is True

    activa = pantalla._tenencias[0]
    from app.negocio.llaves import devolver_llave

    devolver_llave(conn, activa["IdLlaveProfesional"], reintegrar_deposito=True)
    conn.commit()
    pantalla._actualizar_tenencias()

    assert pantalla.boton_devolver.isEnabled() is False
    cargo_credito = conn.execute(
        "SELECT * FROM CargoEspecial WHERE IdProfesional = ? AND Tipo = 'Crédito'", (id_profesional,)
    ).fetchone()
    assert cargo_credito is not None


def test_sin_llave_seleccionada_boton_entregar_deshabilitado(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_entregar.isEnabled() is False


def test_flujo_completo_entregar_y_devolver_via_botones(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QDialog

    id_llave, id_profesional = _crear_llave_y_profesional(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)

    def _entrega_aceptada(self, *a, **k):
        indice = self.combo_profesional.findData(id_profesional)
        self.combo_profesional.setCurrentIndex(indice)
        self.casilla_deposito.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.gui.pantallas.llaves._DialogoEntrega.exec", _entrega_aceptada)
    pantalla._entregar()
    assert pantalla.tabla_tenencias.rowCount() == 1
    assert pantalla.boton_devolver.isEnabled() is True

    def _devolucion_aceptada(self, *a, **k):
        self.casilla_reintegro.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.gui.pantallas.llaves._DialogoDevolucion.exec", _devolucion_aceptada)
    pantalla._devolver()
    assert pantalla.boton_devolver.isEnabled() is False

    tenencia = conn.execute("SELECT * FROM LlaveProfesional WHERE IdLlave = ?", (id_llave,)).fetchone()
    assert tenencia["FechaDevolucion"] is not None
    assert tenencia["DepositoReintegrado"] == 1
