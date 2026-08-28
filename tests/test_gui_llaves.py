import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.crud_generico import _DialogoRegistro
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


def _crear_llave_copia_y_profesional(conn):
    conn.execute("INSERT INTO Llave (Descripcion, ValorDepositoActual) VALUES ('Llave principal', 1000)")
    id_llave = conn.execute("SELECT IdLlave FROM Llave").fetchone()["IdLlave"]
    conn.execute("INSERT INTO LlaveCopia (IdLlave, Identificador) VALUES (?, 'Copia 1')", (id_llave,))
    id_copia = conn.execute("SELECT IdLlaveCopia FROM LlaveCopia").fetchone()["IdLlaveCopia"]
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    conn.commit()
    return id_llave, id_copia, id_profesional


def test_llave_tipo_lee_valores_de_listas_editables(qtbot, conn):
    """El combo Tipo tenía los 3 valores hardcodeados en Python — si el
    admin los editaba desde la pantalla Listas editables, no tenía ningún
    efecto. Ahora tiene que leerlos de ahí (sección 8.2)."""
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.crud_llaves.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    combo_tipo = dialogo._entradas["Tipo"]
    textos = [combo_tipo.itemText(i) for i in range(combo_tipo.count())]
    assert textos == ["Unidad", "Edificio", "No especificada"]


def test_seleccionar_copia_sin_tenencias_deshabilita_devolver(qtbot, conn):
    _, _, _ = _crear_llave_copia_y_profesional(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    pantalla.tabla_copias.selectRow(0)
    assert pantalla.boton_entregar.isEnabled() is True
    assert pantalla.boton_devolver.isEnabled() is False


def test_sin_copia_seleccionada_boton_entregar_deshabilitado(qtbot, conn):
    _crear_llave_copia_y_profesional(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    assert pantalla.boton_entregar.isEnabled() is False


def test_entregar_llave_crea_tenencia_y_cargo_especial(qtbot, conn):
    id_llave, id_copia, id_profesional = _crear_llave_copia_y_profesional(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    pantalla.tabla_copias.selectRow(0)

    from app.negocio.llaves import entregar_llave

    entregar_llave(conn, id_copia=id_copia, id_profesional=id_profesional, cobrar_deposito=True)
    conn.commit()
    pantalla._actualizar_tenencias()

    assert pantalla.tabla_tenencias.rowCount() == 1
    assert pantalla.boton_devolver.isEnabled() is True
    cargo = conn.execute("SELECT * FROM CargoEspecial WHERE IdProfesional = ?", (id_profesional,)).fetchone()
    assert cargo is not None
    assert cargo["Tipo"] == "Débito"
    assert cargo["IdLlave"] == id_llave


def test_devolver_llave_actualiza_tabla_y_deshabilita_boton(qtbot, conn):
    id_llave, id_copia, id_profesional = _crear_llave_copia_y_profesional(conn)
    from app.negocio.llaves import entregar_llave

    entregar_llave(conn, id_copia=id_copia, id_profesional=id_profesional, cobrar_deposito=True)
    conn.commit()

    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    pantalla.tabla_copias.selectRow(0)
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
    assert cargo_credito["IdLlave"] == id_llave


def test_sin_llave_seleccionada_boton_agregar_acceso_deshabilitado(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_agregar_acceso.isEnabled() is False


def _crear_edificio_con_unidad(conn, nombre="Ramos 1", departamento="1ro A"):
    id_edificio = conn.execute("INSERT INTO Edificio (Nombre) VALUES (?)", (nombre,)).lastrowid
    id_unidad = conn.execute(
        "INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, ?)", (id_edificio, departamento)
    ).lastrowid
    conn.commit()
    return id_edificio, id_unidad


def test_sin_llave_seleccionada_boton_agregar_copia_deshabilitado(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_agregar_copia.isEnabled() is False


def test_agregar_copia_sugiere_identificador_y_aparece_sin_entregar(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from app.gui.pantallas.llaves import _DialogoCopia

    conn.execute("INSERT INTO Llave (Descripcion) VALUES ('Llave A')")
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)

    monkeypatch.setattr(_DialogoCopia, "exec", lambda self: QDialog.DialogCode.Accepted)
    pantalla._agregar_copia()

    assert pantalla.tabla_copias.rowCount() == 1
    assert pantalla.tabla_copias.item(0, 0).text() == "Copia 1"
    assert pantalla.tabla_copias.item(0, 1).text() == "Sin entregar"


def test_dos_copias_del_mismo_tipo_muestran_titulares_distintos(qtbot, conn):
    id_llave, id_copia_1, id_profesional_1 = _crear_llave_copia_y_profesional(conn)
    id_copia_2 = conn.execute(
        "INSERT INTO LlaveCopia (IdLlave, Identificador) VALUES (?, 'Copia 2')", (id_llave,)
    ).lastrowid
    id_profesional_2 = conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Otro')"
    ).lastrowid
    conn.commit()

    from app.negocio.llaves import entregar_llave

    entregar_llave(conn, id_copia=id_copia_1, id_profesional=id_profesional_1)
    entregar_llave(conn, id_copia=id_copia_2, id_profesional=id_profesional_2)
    conn.commit()

    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)

    assert pantalla.tabla_copias.rowCount() == 2
    titulares = {pantalla.tabla_copias.item(f, 1).text() for f in range(2)}
    assert len(titulares) == 2
    assert "Sin entregar" not in titulares


def test_eliminar_copia_sin_historial(qtbot, conn):
    conn.execute("INSERT INTO Llave (Descripcion) VALUES ('Llave A')")
    id_llave = conn.execute("SELECT IdLlave FROM Llave").fetchone()["IdLlave"]
    conn.execute("INSERT INTO LlaveCopia (IdLlave, Identificador) VALUES (?, 'Copia 1')", (id_llave,))
    conn.commit()

    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    assert pantalla.tabla_copias.rowCount() == 1

    pantalla.tabla_copias.selectRow(0)
    pantalla._eliminar_copia()

    assert pantalla.tabla_copias.rowCount() == 0


def test_eliminar_copia_con_historial_no_se_puede(qtbot, conn):
    _, id_copia, id_profesional = _crear_llave_copia_y_profesional(conn)
    from app.negocio.llaves import entregar_llave

    entregar_llave(conn, id_copia=id_copia, id_profesional=id_profesional)
    conn.commit()

    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    pantalla.tabla_copias.selectRow(0)
    pantalla._eliminar_copia()

    assert pantalla.tabla_copias.rowCount() == 1


def test_agregar_acceso_edificio_completo(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from app.gui.pantallas.llaves import _DialogoAcceso

    id_llave, _, _ = _crear_llave_copia_y_profesional(conn)
    _crear_edificio_con_unidad(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)

    monkeypatch.setattr(_DialogoAcceso, "exec", lambda self: QDialog.DialogCode.Accepted)
    pantalla._agregar_acceso()

    assert pantalla.tabla_accesos.rowCount() == 1
    assert pantalla.tabla_accesos.item(0, 0).text() == "Ramos 1"
    assert pantalla.tabla_accesos.item(0, 1).text() == "Todas"

    acceso = conn.execute("SELECT * FROM LlaveAcceso WHERE IdLlave = ?", (id_llave,)).fetchone()
    assert acceso["IdEdificio"] is not None
    assert acceso["IdUnidad"] is None


def test_agregar_acceso_unidad_puntual_con_descripcion(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from app.gui.pantallas.llaves import _DialogoAcceso

    _crear_llave_copia_y_profesional(conn)
    _, id_unidad = _crear_edificio_con_unidad(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)

    def _elegir_unidad(self):
        indice = self.combo_unidad.findData(id_unidad)
        self.combo_unidad.setCurrentIndex(indice)
        self.campo_descripcion.setText("Portón lateral")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoAcceso, "exec", _elegir_unidad)
    pantalla._agregar_acceso()

    assert pantalla.tabla_accesos.item(0, 1).text() == "1ro A"
    assert pantalla.tabla_accesos.item(0, 2).text() == "Portón lateral"


def test_eliminar_acceso(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from app.gui.pantallas.llaves import _DialogoAcceso

    _crear_llave_copia_y_profesional(conn)
    _crear_edificio_con_unidad(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    monkeypatch.setattr(_DialogoAcceso, "exec", lambda self: QDialog.DialogCode.Accepted)
    pantalla._agregar_acceso()
    assert pantalla.tabla_accesos.rowCount() == 1

    pantalla.tabla_accesos.selectRow(0)
    pantalla._eliminar_acceso()

    assert pantalla.tabla_accesos.rowCount() == 0


def test_cambiar_de_llave_actualiza_accesos_y_copias_mostrados(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from app.gui.pantallas.llaves import _DialogoAcceso

    conn.execute("INSERT INTO Llave (Descripcion) VALUES ('Llave A')")
    conn.execute("INSERT INTO Llave (Descripcion) VALUES ('Llave B')")
    conn.commit()
    _crear_edificio_con_unidad(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)

    monkeypatch.setattr(_DialogoAcceso, "exec", lambda self: QDialog.DialogCode.Accepted)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    pantalla._agregar_acceso()
    assert pantalla.tabla_accesos.rowCount() == 1

    pantalla.crud_llaves.tabla_widget.selectRow(1)
    assert pantalla.tabla_accesos.rowCount() == 0
    assert pantalla.tabla_copias.rowCount() == 0


def test_flujo_completo_entregar_y_devolver_via_botones(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QDialog

    _, _, id_profesional = _crear_llave_copia_y_profesional(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    pantalla.tabla_copias.selectRow(0)

    def _entrega_aceptada(self, *a, **k):
        indice = self.combo_profesional.findData(id_profesional)
        self.combo_profesional.setCurrentIndex(indice)
        self.casilla_deposito.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.gui.pantallas.llaves._DialogoEntrega.exec", _entrega_aceptada)
    pantalla._entregar()
    assert pantalla.tabla_copias.item(0, 1).text() != "Sin entregar"

    pantalla.tabla_copias.selectRow(0)
    assert pantalla.tabla_tenencias.rowCount() == 1
    assert pantalla.boton_devolver.isEnabled() is True

    def _devolucion_aceptada(self, *a, **k):
        self.casilla_reintegro.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.gui.pantallas.llaves._DialogoDevolucion.exec", _devolucion_aceptada)
    pantalla._devolver()
    assert pantalla.tabla_copias.item(0, 1).text() == "Sin entregar"

    tenencia = conn.execute("SELECT * FROM LlaveProfesional").fetchone()
    assert tenencia["FechaDevolucion"] is not None
    assert tenencia["DepositoReintegrado"] == 1


def test_deshacer_ultimo_revierte_entrega(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QDialog

    _, _, id_profesional = _crear_llave_copia_y_profesional(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_llaves.tabla_widget.selectRow(0)
    pantalla.tabla_copias.selectRow(0)

    def _entrega_aceptada(self, *a, **k):
        indice = self.combo_profesional.findData(id_profesional)
        self.combo_profesional.setCurrentIndex(indice)
        self.casilla_deposito.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.gui.pantallas.llaves._DialogoEntrega.exec", _entrega_aceptada)
    pantalla._entregar()
    assert conn.execute("SELECT COUNT(*) c FROM LlaveProfesional").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1
    assert pantalla.boton_deshacer.isEnabled() is True

    pantalla._deshacer_ultimo()

    assert conn.execute("SELECT COUNT(*) c FROM LlaveProfesional").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 0
    assert pantalla.boton_deshacer.isEnabled() is False


def test_deshacer_sin_movimientos_no_falla(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla._deshacer_ultimo()  # no debe fallar aunque no haya nada para deshacer
