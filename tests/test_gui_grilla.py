import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.grilla import GrillaDisponibilidad
from app.negocio.dias import periodo_actual


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_edificio_con_consultorio(conn, nombre_edificio="Torre Norte"):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES (?)", (nombre_edificio,))
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio WHERE Nombre = ?", (nombre_edificio,)).fetchone()[
        "IdEdificio"
    ]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad WHERE IdEdificio = ?", (id_edificio,)).fetchone()[
        "IdUnidad"
    ]
    conn.execute(
        "INSERT INTO Consultorio (IdUnidad, NumeroConsultorio, Ventana) VALUES (?, 1, 1)", (id_unidad,)
    )
    conn.commit()
    return id_edificio, id_unidad


def test_grilla_sin_unidades_muestra_mensaje(qtbot, conn):
    pantalla = GrillaDisponibilidad(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.layout_contenedor.count() == 1


def test_grilla_arma_una_tabla_por_unidad(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    pantalla = GrillaDisponibilidad(conn)
    qtbot.addWidget(pantalla)
    tablas = [pantalla.layout_contenedor.itemAt(i).widget() for i in range(pantalla.layout_contenedor.count())]
    tablas = [w for w in tablas if w is not None]
    assert len(tablas) == 1  # una tarjeta para la única unidad


def test_grilla_filtra_por_edificio(qtbot, conn):
    _crear_edificio_con_consultorio(conn, "Torre Norte")
    _crear_edificio_con_consultorio(conn, "Torre Sur")
    pantalla = GrillaDisponibilidad(conn)
    qtbot.addWidget(pantalla)

    indice_torre_sur = pantalla.combo_edificio.findText("Torre Sur")
    assert indice_torre_sur >= 0
    pantalla.combo_edificio.setCurrentIndex(indice_torre_sur)

    tablas = [pantalla.layout_contenedor.itemAt(i).widget() for i in range(pantalla.layout_contenedor.count())]
    tablas = [w for w in tablas if w is not None]
    assert len(tablas) == 1


def test_grilla_usa_periodo_actual_por_defecto(qtbot, conn):
    pantalla = GrillaDisponibilidad(conn)
    qtbot.addWidget(pantalla)
    anio, mes = (int(p) for p in periodo_actual(conn).split("-"))
    assert pantalla.spin_anio.value() == anio
    assert pantalla.spin_mes.value() == mes
