import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.lista_espera import PantallaListaEspera
from app.gui.widgets.selector_profesional import _ProxyBusquedaSinAcentos


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


def test_combo_profesional_es_buscable_por_codigo_o_nombre(qtbot, conn):
    """Confirmado por la clienta: el selector de profesional buscable
    corre en todos los formularios del sistema, Lista de espera incluida
    — y con el mismo formato canónico "{código} - {tratamiento} {nombre}
    {apellido}" que el resto (antes mostraba "Apellido, Nombre")."""
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, NombrePila, IdCodigo) "
        "VALUES ('R', 'Lo Veci', 'Virginia', 'R1')"
    )
    conn.commit()
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    completador = pantalla.combo_profesional.completer()
    assert isinstance(completador.model(), _ProxyBusquedaSinAcentos)
    assert pantalla.combo_profesional.itemText(0) == "R1 - Virginia Lo Veci"


def test_combo_profesional_incluye_inactivos_y_contactos(qtbot, conn):
    """Confirmado por la clienta: acá se agenda lo que pide CUALQUIER
    profesional, esté activo en el espacio o no — categoría X (inactivo)
    o C (contacto/prospecto) incluidas, no solo R/A."""
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('X', 'Inactivo')")
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('C', 'Prospecto')")
    conn.commit()
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    textos = {pantalla.combo_profesional.itemText(i) for i in range(pantalla.combo_profesional.count())}
    assert "Inactivo" in textos
    assert "Prospecto" in textos


def test_horario_muestra_formato_hs(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.spin_desde.setValue(9)
    assert pantalla.spin_desde.text() == "9:00hs"
    pantalla.spin_hasta.setValue(12.5)
    assert pantalla.spin_hasta.text() == "12:30hs"


def test_tamano_es_combo_cerrado_deshabilitado_hasta_tildar_la_casilla(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert not pantalla.combo_tamano.isEnabled()
    textos = [pantalla.combo_tamano.itemText(i) for i in range(pantalla.combo_tamano.count())]
    assert textos == ["Cualquier tamaño", "Grande", "Intermedio", "Chico"]

    pantalla.casilla_tamano.setChecked(True)
    assert pantalla.combo_tamano.isEnabled()


def test_crear_pedido_con_tamano_persiste_la_condicion(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.lista_dias.item(0).setCheckState(Qt.CheckState.Checked)  # Lunes
    pantalla.casilla_tamano.setChecked(True)
    pantalla.combo_tamano.setCurrentIndex(pantalla.combo_tamano.findData("Grande"))

    pantalla._crear_pedido()

    id_pedido = conn.execute("SELECT IdPedido FROM ListaEspera").fetchone()["IdPedido"]
    condiciones = conn.execute(
        "SELECT CondicionesConsultorio FROM ListaEspera WHERE IdPedido = ?", (id_pedido,)
    ).fetchone()["CondicionesConsultorio"]
    assert '"tamano": "Grande"' in condiciones


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
