import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas import catalogos


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


_FABRICAS = [
    catalogos.pantalla_edificios,
    catalogos.pantalla_unidades,
    catalogos.pantalla_consultorios,
    catalogos.pantalla_responsables,
    catalogos.pantalla_tipos_licencia,
    catalogos.pantalla_listas_editables,
    catalogos.pantalla_condiciones_normas,
    catalogos.pantalla_mensajes_predefinidos,
]


@pytest.mark.parametrize("fabrica", _FABRICAS)
def test_pantalla_catalogo_se_arma_sin_error(qtbot, conn, fabrica):
    pantalla = fabrica(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.rowCount() == len(pantalla.repositorio.listar())


def test_pantalla_unidades_muestra_nombre_de_edificio(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    conn.commit()

    pantalla = catalogos.pantalla_unidades(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.item(0, 0).text() == "Torre Norte"
    assert pantalla.tabla_widget.item(0, 1).text() == "1A"


def test_pantalla_consultorios_muestra_edificio_y_unidad(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 3)", (id_unidad,))
    conn.commit()

    pantalla = catalogos.pantalla_consultorios(conn)
    qtbot.addWidget(pantalla)
    assert "Torre Norte" in pantalla.tabla_widget.item(0, 0).text()
    assert pantalla.tabla_widget.item(0, 1).text() == "3"
