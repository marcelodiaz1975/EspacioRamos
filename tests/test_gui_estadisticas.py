import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.estadisticas import PantallaEstadisticas
from app.negocio.dias import periodo_actual
from app.negocio.estadisticas import generar_snapshot


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_edificio_con_consultorio(conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    conn.commit()


def test_calcula_ocupacion_general_sin_datos(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    assert "Ocupación general: 0.0%" in pantalla.etiqueta_general.text()


def test_muestra_edificios_y_consultorios(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_edificios.rowCount() == 1
    assert pantalla.tabla_edificios.item(0, 0).text() == "Torre Norte"
    assert pantalla.tabla_consultorios.rowCount() == 1


def test_historial_de_snapshots_se_lista(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    generar_snapshot(conn, periodo_actual(conn))
    conn.commit()

    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_snapshots.rowCount() == 1
    assert pantalla.tabla_snapshots.item(0, 0).text() == periodo_actual(conn)


def test_cambiar_periodo_y_recalcular(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    pantalla.spin_mes.setValue(1)
    pantalla.spin_anio.setValue(2020)
    pantalla._calcular()
    assert "Ocupación general" in pantalla.etiqueta_general.text()
