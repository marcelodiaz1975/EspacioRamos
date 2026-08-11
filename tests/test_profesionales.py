import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.profesionales import pantalla_profesionales


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
    assert pantalla.tabla_widget.rowCount() == 1
    assert pantalla.tabla_widget.item(0, 1).text() == "Gómez"


def test_pantalla_profesionales_muestra_etiqueta_de_categoria(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.commit()
    pantalla = pantalla_profesionales(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.item(0, 0).text() == "R - Regular"


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
        i for i in range(pantalla.tabla_widget.rowCount()) if pantalla.tabla_widget.item(i, 1).text() == "Ruiz"
    )
    assert "Gómez" in pantalla.tabla_widget.item(fila_equipo, 20).text()
