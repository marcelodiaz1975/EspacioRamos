import pytest
from PySide6.QtWidgets import QLabel, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.main_window import Seccion, VentanaPrincipal
from app.gui.pantallas.panel_control import PanelControl
from app.repositorio.registro import obtener_repositorio


def _textos_visibles(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


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


def test_panel_control_muestra_nombre_del_espacio(qtbot, conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, NombreEspacio="Mi Espacio")
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.titulo.text() == "Mi Espacio"


def test_panel_control_boton_avanzar_deshabilitado_a_mitad_de_mes(qtbot, conn):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_avanzar.isEnabled() is False


def test_panel_control_boton_avanzar_habilitado_ultimo_dia(qtbot, conn):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-31' WHERE IdConfiguracion = 1"
    )
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_avanzar.isEnabled() is True


def test_panel_control_sin_alertas_muestra_mensaje(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert any("Sin alertas pendientes." in t for t in _textos_visibles(pantalla.contenedor_alertas))


def test_panel_control_alerta_de_deuda_se_muestra(qtbot, conn):
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Deudor", SaldoCuentaAnterior=99999,
    )
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert any("Deudor" in t for t in _textos_visibles(pantalla.contenedor_alertas))


def test_generar_backup_sin_carpeta_configurada_no_falla(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla._generar_backup()  # solo debe avisar, no lanzar


def test_generar_backup_con_carpeta_configurada(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBackup=str(tmp_path / "backups"))
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla._generar_backup()
    assert list((tmp_path / "backups").iterdir())


def test_avanzar_mes_genera_backup_cuando_esta_configurado(qtbot, conn, tmp_path):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-31', CarpetaBackup = ? "
        "WHERE IdConfiguracion = 1",
        (str(tmp_path / "backups"),),
    )
    conn.commit()
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)

    pantalla._avanzar_mes()

    assert list((tmp_path / "backups").iterdir())


def test_ventana_principal_navega_entre_secciones(qtbot, conn):
    secciones = [
        Seccion("Panel de control", lambda c: PanelControl(c), categoria="Principal"),
        Seccion("Otra pantalla", lambda c: PanelControl(c), categoria="Principal"),
    ]
    ventana = VentanaPrincipal(conn, secciones)
    qtbot.addWidget(ventana)
    assert ventana._pila.count() == 2
    ventana._navegacion.setCurrentRow(2)  # fila 0 = separador, 1 = primera, 2 = segunda
    assert ventana._pila.currentIndex() == 1
