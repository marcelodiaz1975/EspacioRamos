import pytest
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.profesionales import pantalla_profesionales
from app.repositorio.registro import obtener_repositorio


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_pantalla_profesionales_lista_existentes(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.commit()
    pantalla = pantalla_profesionales(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.crud_profesionales.tabla_widget.rowCount() == 1
    assert pantalla.crud_profesionales.tabla_widget.item(0, 1).text() == "Gómez"


def test_pantalla_profesionales_muestra_etiqueta_de_categoria(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.commit()
    pantalla = pantalla_profesionales(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.crud_profesionales.tabla_widget.item(0, 0).text() == "R - Regular"


def test_pantalla_profesionales_muestra_cabeza_de_equipo(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    id_cabeza = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, ProfesionalCabezaEquipo) VALUES ('E', 'Ruiz', ?)",
        (id_cabeza,),
    )
    conn.commit()
    pantalla = pantalla_profesionales(conn)
    qtbot.addWidget(pantalla)
    fila_equipo = next(
        i for i in range(pantalla.crud_profesionales.tabla_widget.rowCount()) if pantalla.crud_profesionales.tabla_widget.item(i, 1).text() == "Ruiz"
    )
    assert "Gómez" in pantalla.crud_profesionales.tabla_widget.item(fila_equipo, 20).text()


def test_cambiar_codigo_registra_historial_y_renombra_carpeta(qtbot, conn, tmp_path, monkeypatch):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3",
    )
    (tmp_path / "Profesionales" / "R3").mkdir(parents=True)
    (tmp_path / "Profesionales" / "R3" / "2026-08 - Liquidación Ramos.pdf").write_text("x")
    conn.commit()

    pantalla = pantalla_profesionales(conn)
    qtbot.addWidget(pantalla)
    fila = next(i for i in range(pantalla.crud_profesionales.tabla_widget.rowCount()) if pantalla.crud_profesionales.tabla_widget.item(i, 1).text() == "Ramos")
    pantalla.crud_profesionales.tabla_widget.selectRow(fila)

    def _dialogo_cambia_codigo(self, *a, **k):
        self._entradas["CategoriaProfesional"].setCurrentIndex(self._entradas["CategoriaProfesional"].findData("X"))
        self._entradas["IdCodigo"].setText("X34")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.gui.crud_generico._DialogoRegistro.exec", _dialogo_cambia_codigo)
    pantalla.crud_profesionales._editar()

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["CategoriaProfesional"] == "X"
    assert profesional["IdCodigo"] == "X34"

    historial = conn.execute("SELECT * FROM HistorialCodigo WHERE IdProfesional = ?", (id_prof,)).fetchone()
    assert historial["CodigoAnterior"] == "R3"
    assert historial["CodigoNuevo"] == "X34"

    assert (tmp_path / "Profesionales" / "X34" / "2026-08 - Liquidación Ramos.pdf").exists()
    assert not (tmp_path / "Profesionales" / "R3").exists()


def test_seleccionar_profesional_muestra_su_documentacion(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    (tmp_path / "Profesionales" / "R3" / "Documentación").mkdir(parents=True)
    (tmp_path / "Profesionales" / "R3" / "Documentación" / "dni.pdf").write_text("x")
    conn.commit()

    pantalla = pantalla_profesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)

    assert pantalla.lista_documentos.count() == 1
    assert pantalla.lista_documentos.item(0).text() == "dni.pdf"


def test_profesional_sin_codigo_no_muestra_documentacion(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Sin Codigo")
    conn.commit()

    pantalla = pantalla_profesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)

    assert pantalla.lista_documentos.count() == 0


def test_agregar_documento_lo_copia_y_lo_lista(qtbot, conn, tmp_path, monkeypatch):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path / "base"),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    conn.commit()
    origen = tmp_path / "dni.pdf"
    origen.write_bytes(b"x")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([str(origen)], "")))

    pantalla = pantalla_profesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)

    pantalla._agregar_documento()

    assert pantalla.lista_documentos.count() == 1
    assert pantalla.lista_documentos.item(0).text() == "dni.pdf"
    assert (tmp_path / "base" / "Profesionales" / "R3" / "Documentación" / "dni.pdf").exists()


def test_eliminar_documento(qtbot, conn, tmp_path, monkeypatch):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path / "base"),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    conn.commit()
    origen = tmp_path / "dni.pdf"
    origen.write_bytes(b"x")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([str(origen)], "")))

    pantalla = pantalla_profesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)
    pantalla._agregar_documento()

    pantalla.lista_documentos.setCurrentRow(0)
    pantalla._eliminar_documento()

    assert pantalla.lista_documentos.count() == 0
    assert not (tmp_path / "base" / "Profesionales" / "R3" / "Documentación" / "dni.pdf").exists()
