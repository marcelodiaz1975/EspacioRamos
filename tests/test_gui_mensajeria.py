import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.mensajeria import CentroMensajeria
from app.negocio.dias import periodo_actual


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_centro_mensajeria_lista_profesionales_categoria_r(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, SaldoCuentaAnterior) VALUES ('R', 'Gómez', 0)")
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.rowCount() == 1
    assert "Gómez" in pantalla.tabla.item(0, 0).text()


def test_centro_mensajeria_seleccionar_fila_muestra_mensaje(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, SaldoCuentaAnterior) VALUES ('R', 'Gómez', 0)")
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)
    assert "Gómez" in pantalla.texto_mensaje.toPlainText() or pantalla.texto_mensaje.toPlainText() != ""


def test_centro_mensajeria_cambia_a_categoria_aislada(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('A', 'Pérez')")
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_categoria.setCurrentIndex(1)  # categoría A
    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 2).text() == "Detalle de reserva"


def test_centro_mensajeria_boton_grupal_llena_texto(qtbot, conn):
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla._mostrar_mensaje_grupal()
    assert "AVISOS VARIOS" in pantalla.texto_mensaje.toPlainText()


def test_centro_mensajeria_usa_periodo_actual_por_defecto(qtbot, conn):
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.campo_periodo.text() == periodo_actual(conn)
