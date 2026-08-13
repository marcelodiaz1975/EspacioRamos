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
    catalogos.pantalla_detalles_complementarios_propuesta,
    catalogos.pantalla_mensajes_predefinidos,
    catalogos.pantalla_profesiones,
    catalogos.pantalla_gastos_operativos,
    catalogos.pantalla_placas,
    catalogos.pantalla_fechas_especiales,
    catalogos.pantalla_esquema_descuentos,
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


def test_pantalla_placas_muestra_unidad_y_profesional(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    conn.execute(
        "INSERT INTO Placa (IdUnidad, IdProfesional, NombreGrabado) VALUES (?, ?, 'Dr. Gómez')",
        (id_unidad, id_profesional),
    )
    conn.commit()

    pantalla = catalogos.pantalla_placas(conn)
    qtbot.addWidget(pantalla)
    assert "1A" in pantalla.tabla_widget.item(0, 0).text()
    assert "Gómez" in pantalla.tabla_widget.item(0, 2).text()


def test_pantalla_gastos_operativos_muestra_alcance(qtbot, conn):
    conn.execute(
        "INSERT INTO GastoOperativo (Periodo, Concepto, Monto, Alcance) VALUES ('2026-08', 'Limpieza', 5000, 'Espacio general')"
    )
    conn.commit()
    pantalla = catalogos.pantalla_gastos_operativos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.item(0, 4).text() == "Espacio general"
