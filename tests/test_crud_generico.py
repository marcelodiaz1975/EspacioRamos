import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.crud_generico import Campo, PantallaCRUD


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    """QMessageBox.exec() bloquea esperando un clic real, que nunca llega en
    los tests — se mockean sus variantes estáticas para que no cuelguen."""
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def _campos_edificio():
    return [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("Domicilio", "Domicilio"),
        Campo("DomicilioLocalidad", "Localidad"),
    ]


def test_pantalla_crud_lista_registros_existentes(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre, Domicilio) VALUES ('Torre Norte', 'Calle 1')")
    conn.commit()
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.rowCount() == 1
    assert pantalla.tabla_widget.item(0, 0).text() == "Torre Norte"


def test_pantalla_crud_nuevo_crea_registro_via_dialogo(qtbot, conn, monkeypatch):
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)

    def _dialogo_aceptado_con_nombre(self, *a, **k):
        self._entradas["Nombre"].setText("Torre Sur")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.gui.crud_generico._DialogoRegistro.exec", _dialogo_aceptado_con_nombre)
    pantalla._nuevo()
    assert pantalla.tabla_widget.rowCount() == 1
    assert pantalla.repositorio.listar()[0]["Nombre"] == "Torre Sur"


def test_pantalla_crud_eliminar_sin_seleccion_no_falla(qtbot, conn):
    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)
    pantalla._eliminar()  # no debe lanzar excepción — solo informa que no hay selección


def test_pantalla_crud_booleano_se_muestra_si_no(qtbot, conn):
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    conn.execute("INSERT INTO Responsable (Nombre, Activo) VALUES ('Ana', 0)")
    conn.commit()
    pantalla = PantallaCRUD(conn, "Responsable", "Responsables", campos)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.item(0, 1).text() == "No"


def test_pantalla_crud_combo_muestra_etiqueta_no_id(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, 'PB')", (id_edificio,))
    conn.commit()

    def opciones_edificio(c):
        filas = c.execute("SELECT IdEdificio, Nombre FROM Edificio").fetchall()
        return [(f["IdEdificio"], f["Nombre"]) for f in filas]

    campos = [
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=opciones_edificio),
        Campo("Departamento", "Departamento"),
    ]
    pantalla = PantallaCRUD(conn, "Unidad", "Unidades", campos)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.item(0, 0).text() == "Torre Norte"


def test_pantalla_crud_eliminar_con_dependientes_no_rompe(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, 'PB')", (id_edificio,))
    conn.commit()

    pantalla = PantallaCRUD(conn, "Edificio", "Edificios", _campos_edificio())
    qtbot.addWidget(pantalla)
    pantalla.tabla_widget.selectRow(0)
    item = pantalla.tabla_widget.item(0, 0)
    assert item.data(Qt.ItemDataRole.UserRole) == id_edificio

    pantalla._eliminar()  # FK activa: debe fallar con IntegrityError y no propagarlo
    assert conn.execute("SELECT COUNT(*) c FROM Edificio").fetchone()["c"] == 1
