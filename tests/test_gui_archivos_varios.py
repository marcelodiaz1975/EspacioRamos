import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.main_window import Seccion
from app.gui.pantallas.archivos_varios import PantallaArchivosVarios
from app.repositorio.registro import obtener_repositorio


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


def test_regenerar_sin_carpeta_base_no_falla(qtbot, conn):
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    pantalla._regenerar_propuesta()  # no debe lanzar, solo avisar


def test_regenerar_propuesta_genera_archivo(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)

    pantalla._regenerar_propuesta()

    generados = list((tmp_path / "Archivos varios" / "Propuesta").iterdir())
    assert len(generados) == 1
    assert generados[0].name.startswith("Propuesta Espacio Ramos Consultorios")


def test_regenerar_disponibilidad_genera_archivo(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)

    pantalla._regenerar_disponibilidad()

    generados = list((tmp_path / "Archivos varios" / "Disponibilidad").iterdir())
    assert len(generados) == 1
    assert generados[0].name.startswith("Disponibilidad Espacio Ramos Consultorios")


def test_regenerar_placas_genera_archivo(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)

    pantalla._regenerar_placas()

    generados = list((tmp_path / "Archivos varios" / "Placas").iterdir())
    assert len(generados) == 1
    assert generados[0].name.startswith("Placas Espacio Ramos")


def test_regenerar_manual_sin_secciones_avisa_y_no_falla(qtbot, conn):
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    pantalla._regenerar_manual()  # no debe lanzar, solo avisar


def test_regenerar_manual_genera_archivo(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    secciones = [Seccion("Alguna pantalla", lambda c: None, categoria="Principal", ayuda="Texto de ayuda.")]
    pantalla = PantallaArchivosVarios(conn, secciones)
    qtbot.addWidget(pantalla)

    pantalla._regenerar_manual()

    generados = list((tmp_path / "Archivos varios" / "Manual").iterdir())
    assert len(generados) == 1
    assert generados[0].name == "Manual de usuario.pdf"
