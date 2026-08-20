import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.lista_espera import PantallaListaEspera


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


def _crear_profesional(conn, apellido="Gómez"):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', ?)", (apellido,))
    conn.commit()
    return conn.execute("SELECT IdProfesional FROM Profesional WHERE Apellido = ?", (apellido,)).fetchone()[
        "IdProfesional"
    ]


def test_crear_pedido_sin_dias_no_persiste(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._crear_pedido()  # sin días marcados -> ValueError capturado, no debe persistir
    assert conn.execute("SELECT COUNT(*) c FROM ListaEspera").fetchone()["c"] == 0


def test_crear_pedido_con_dias_persiste_y_aparece_en_tabla(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)

    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes
    pantalla._crear_pedido()

    assert conn.execute("SELECT COUNT(*) c FROM ListaEspera").fetchone()["c"] == 1
    assert pantalla.tabla.rowCount() == 1
    assert "Lunes" in pantalla.tabla.item(0, 1).text()


def test_sin_cobertura_muestra_etiqueta_sin_color(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)
    pantalla._crear_pedido()
    assert pantalla.tabla.item(0, 3).text() == "Sin cobertura"


def test_marcar_resuelto_saca_el_pedido_de_la_lista(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)
    pantalla._crear_pedido()

    pantalla.tabla.selectRow(0)
    pantalla._resolver()

    assert pantalla.tabla.rowCount() == 0
    estado = conn.execute("SELECT Estado FROM ListaEspera").fetchone()["Estado"]
    assert estado == "Resuelto"


def _crear_edificio_con_consultorio(conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute(
        "INSERT INTO Consultorio (IdUnidad, NumeroConsultorio, ValorHoraRegularActual, ValorHoraAisladaActual) "
        "VALUES (?, 1, 1000, 1500)",
        (id_unidad,),
    )
    conn.commit()


def test_generar_mensaje_disponibilidad_sin_dias_no_completa_texto(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._generar_mensaje_disponibilidad()
    assert pantalla.texto_mensaje_disponibilidad.toPlainText() == ""


def test_generar_mensaje_disponibilidad_completa_texto(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes

    pantalla._generar_mensaje_disponibilidad()

    texto = pantalla.texto_mensaje_disponibilidad.toPlainText()
    assert texto.startswith("Disponibilidad período")
    assert "Lunes" in texto


def test_generar_mensaje_disponibilidad_con_pdf_tildado_genera_archivo(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    _crear_edificio_con_consultorio(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)
    pantalla.casilla_pdf_disponibilidad.setChecked(True)

    pantalla._generar_mensaje_disponibilidad()

    carpeta_disponibilidad = tmp_path / "Archivos varios" / "Disponibilidad"
    assert list(carpeta_disponibilidad.glob("*.pdf"))


def test_generar_mensaje_disponibilidad_respeta_checkbox_de_edificio(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Sur')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio WHERE Nombre = 'Torre Norte'").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute(
        "INSERT INTO Consultorio (IdUnidad, NumeroConsultorio, ValorHoraRegularActual, ValorHoraAisladaActual) "
        "VALUES (?, 1, 1000, 1500)",
        (id_unidad,),
    )
    conn.commit()

    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes
    pantalla.casilla_incluir_edificio.setChecked(False)

    pantalla._generar_mensaje_disponibilidad()

    assert "Torre Norte" not in pantalla.texto_mensaje_disponibilidad.toPlainText()


def test_copiar_mensaje_disponibilidad_usa_portapapeles(qtbot, conn, monkeypatch):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.texto_mensaje_disponibilidad.setPlainText("texto de prueba")

    copiado = []
    monkeypatch.setattr(
        "app.gui.pantallas.lista_espera.QGuiApplication.clipboard",
        staticmethod(lambda: type("_C", (), {"setText": lambda self, t: copiado.append(t)})()),
    )
    pantalla._copiar_mensaje_disponibilidad()
    assert copiado == ["texto de prueba"]


def test_agregar_bloque_lo_suma_a_la_tabla_y_limpia_dias(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes

    pantalla._agregar_bloque()

    assert len(pantalla._bloques_pendientes) == 1
    assert pantalla.tabla_bloques.rowCount() == 1
    assert pantalla.tabla_bloques.item(0, 0).text() == "Lunes"
    assert pantalla._dias_seleccionados() == []  # se limpia para cargar el próximo bloque


def test_agregar_bloque_sin_dias_no_agrega(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._agregar_bloque()
    assert pantalla._bloques_pendientes == []


def test_crear_pedido_con_dos_bloques_persiste_los_dos(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)

    pantalla.lista_dias.item(1).setCheckState(Qt.CheckState.Checked)  # Martes
    pantalla.lista_dias.item(3).setCheckState(Qt.CheckState.Checked)  # Jueves
    pantalla._agregar_bloque()
    pantalla.lista_dias.item(5).setCheckState(Qt.CheckState.Checked)  # Sábado
    pantalla.combo_tipo_bloques.setCurrentIndex(1)  # Y
    pantalla._crear_pedido()

    assert conn.execute("SELECT COUNT(*) c FROM ListaEspera").fetchone()["c"] == 1
    id_pedido = conn.execute("SELECT IdPedido FROM ListaEspera").fetchone()["IdPedido"]
    assert conn.execute("SELECT COUNT(*) c FROM ListaEsperaBloque WHERE IdPedido = ?", (id_pedido,)).fetchone()["c"] == 2
    assert conn.execute("SELECT TipoCombinacion FROM ListaEspera").fetchone()["TipoCombinacion"] == "Y"
    assert pantalla._bloques_pendientes == []  # se limpia después de crear


def test_quitar_bloque_lo_saca_de_la_tabla(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)
    pantalla._agregar_bloque()

    pantalla.tabla_bloques.selectRow(0)
    pantalla._quitar_bloque()

    assert pantalla._bloques_pendientes == []
    assert pantalla.tabla_bloques.rowCount() == 0


def test_descartar_saca_el_pedido_de_la_lista(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)
    pantalla._crear_pedido()

    pantalla.tabla.selectRow(0)
    pantalla._descartar()

    assert pantalla.tabla.rowCount() == 0
    estado = conn.execute("SELECT Estado FROM ListaEspera").fetchone()["Estado"]
    assert estado == "Descartado"
