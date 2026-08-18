import pytest
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.crud_generico import _DialogoRegistro
from app.gui.pantallas.profesionales import _al_abrir_dialogo_nuevo, _campos_profesional, pantalla_profesionales
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
    assert "Gómez" in pantalla.crud_profesionales.tabla_widget.item(fila_equipo, 21).text()


def test_condicion_fiscal_es_combo_editable_con_default_consumidor_final(qtbot, conn):
    pantalla = pantalla_profesionales(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.crud_profesionales.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    combo = dialogo._entradas["CondicionFiscal"]
    assert combo.isEditable() is True
    assert combo.itemText(0) == "Consumidor Final"
    combo.setEditText("Otra condición")
    assert dialogo.valores()["CondicionFiscal"] == "Otra condición"


def _nuevo_dialogo_con_hook(conn, qtbot):
    dialogo = _DialogoRegistro(conn, _campos_profesional(), "Nuevo registro")
    qtbot.addWidget(dialogo)
    _al_abrir_dialogo_nuevo(dialogo)
    return dialogo


def test_nuevo_profesional_sugiere_codigo_de_la_categoria_por_defecto(qtbot, conn):
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    assert dialogo._entradas["IdCodigo"].text() == "R1"


def test_sugerencia_de_codigo_se_actualiza_al_cambiar_categoria(qtbot, conn):
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    combo_categoria = dialogo._entradas["CategoriaProfesional"]
    combo_categoria.setCurrentIndex(combo_categoria.findData("X"))
    assert dialogo._entradas["IdCodigo"].text() == "X1"


def test_sugerencia_de_codigo_no_pisa_una_edicion_manual(qtbot, conn):
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    campo_codigo = dialogo._entradas["IdCodigo"]
    campo_codigo.setText("R99")

    combo_categoria = dialogo._entradas["CategoriaProfesional"]
    combo_categoria.setCurrentIndex(combo_categoria.findData("X"))

    assert campo_codigo.text() == "R99"


def test_nuevo_profesional_pre_completa_tratamiento(qtbot, conn):
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    combo_profesion = dialogo._entradas["IdProfesion"]
    id_psicologia = obtener_repositorio(conn, "Profesion").listar(Nombre="Psicología")[0]["IdProfesion"]
    combo_profesion.setCurrentIndex(combo_profesion.findData(id_psicologia))
    combo_sexo = dialogo._entradas["Sexo"]
    combo_sexo.setCurrentIndex(combo_sexo.findData("Masculino"))
    assert dialogo._entradas["Tratamiento"].currentText() == "Lic."


def test_tratamiento_ofrece_desplegable_para_fonoaudiologia(qtbot, conn):
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    combo_profesion = dialogo._entradas["IdProfesion"]
    id_fono = obtener_repositorio(conn, "Profesion").listar(Nombre="Fonoaudiología")[0]["IdProfesion"]
    combo_profesion.setCurrentIndex(combo_profesion.findData(id_fono))
    combo_sexo = dialogo._entradas["Sexo"]
    combo_sexo.setCurrentIndex(combo_sexo.findData("Femenino"))

    combo_tratamiento = dialogo._entradas["Tratamiento"]
    opciones = [combo_tratamiento.itemText(i) for i in range(combo_tratamiento.count())]
    assert opciones == ["Fga.", "Lic."]
    assert combo_tratamiento.currentText() == "Fga."


def test_cuit_se_normaliza_al_guardar(qtbot, conn):
    dialogo = _DialogoRegistro(conn, _campos_profesional(), "Nuevo registro")
    qtbot.addWidget(dialogo)
    dialogo._entradas["Apellido"].setText("Gómez")
    dialogo._entradas["CUIT"].setText("20-12345678-9")
    assert dialogo.valores()["CUIT"] == "20123456789"


def test_nombre_completo_se_puede_cargar_y_editar_a_mano(qtbot, conn):
    dialogo = _DialogoRegistro(conn, _campos_profesional(), "Nuevo registro")
    qtbot.addWidget(dialogo)
    dialogo._entradas["Apellido"].setText("Gómez")
    dialogo._entradas["NombreCompleto"].setText("Gómez, Juan Carlos")
    assert dialogo.valores()["NombreCompleto"] == "Gómez, Juan Carlos"

    id_prof = obtener_repositorio(conn, "Profesional").crear(**dialogo.valores())
    assert obtener_repositorio(conn, "Profesional").obtener(id_prof)["NombreCompleto"] == "Gómez, Juan Carlos"

    pantalla = pantalla_profesionales(conn)
    qtbot.addWidget(pantalla)
    dialogo_edicion = _DialogoRegistro(conn, pantalla.crud_profesionales.campos, "Editar registro", registro=obtener_repositorio(conn, "Profesional").obtener(id_prof))
    qtbot.addWidget(dialogo_edicion)
    dialogo_edicion._entradas["NombreCompleto"].setText("Gómez, Juan C.")
    assert dialogo_edicion.valores()["NombreCompleto"] == "Gómez, Juan C."


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
