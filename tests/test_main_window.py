import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import hoja_estilos
from app.gui.main_window import Seccion, VentanaPrincipal
from app.negocio.seguridad import asegurar_permisos_pantalla
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _secciones():
    return [
        Seccion("Uno", lambda c: QWidget(), categoria="Principal", ayuda="Ayuda de Uno."),
        Seccion("Dos", lambda c: QWidget(), categoria="Principal"),
    ]


def test_barra_fecha_ficticia_oculta_por_defecto(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._barra_fecha_ficticia.isHidden() is True


def test_barra_fecha_ficticia_visible_cuando_esta_activo(qtbot, conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoFechaFicticia=1, FechaFicticia="2026-03-15")
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._barra_fecha_ficticia.isHidden() is False
    assert "2026-03-15" in ventana._barra_fecha_ficticia.text()


def test_barra_fecha_ficticia_se_actualiza_al_cambiar_de_pantalla(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._barra_fecha_ficticia.isHidden() is True

    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoFechaFicticia=1, FechaFicticia="2026-03-15")
    ventana._navegacion.setCurrentRow(2)  # 0 = separador, 1 = "Uno", 2 = "Dos"

    assert ventana._barra_fecha_ficticia.isHidden() is False


def test_barra_fecha_ficticia_activada_sin_fecha_no_se_muestra(qtbot, conn):
    """ModoFechaFicticia=1 sin FechaFicticia cargada: no hay nada que
    simular, no tiene sentido mostrar la barra."""
    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoFechaFicticia=1, FechaFicticia=None)
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._barra_fecha_ficticia.isHidden() is True


def test_sin_secciones_no_falla(qtbot, conn):
    ventana = VentanaPrincipal(conn, [])
    qtbot.addWidget(ventana)
    assert ventana._barra_fecha_ficticia.isHidden() is True


def test_barra_fecha_ficticia_es_un_qlabel(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert isinstance(ventana._barra_fecha_ficticia, QLabel)


def test_f1_muestra_ayuda_de_la_seccion_actual(qtbot, conn, monkeypatch):
    llamada = {}
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda parent, titulo, texto: llamada.update(titulo=titulo, texto=texto)),
    )
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)

    ventana._mostrar_ayuda()

    assert "Uno" in llamada["titulo"]
    assert llamada["texto"] == "Ayuda de Uno."


def test_f1_sin_ayuda_cargada_muestra_mensaje_generico(qtbot, conn, monkeypatch):
    llamada = {}
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda parent, titulo, texto: llamada.update(titulo=titulo, texto=texto)),
    )
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    ventana._navegacion.setCurrentRow(2)  # "Dos", sin ayuda cargada

    ventana._mostrar_ayuda()

    assert llamada["texto"]


# --------------------------------------------------------------- modo oscuro/claro

def test_tema_claro_por_defecto(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana.styleSheet() == hoja_estilos(False)


def test_tema_oscuro_cuando_esta_activado(qtbot, conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoOscuro=1)
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana.styleSheet() == hoja_estilos(True)


def test_tema_se_actualiza_al_cambiar_de_pantalla(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana.styleSheet() == hoja_estilos(False)

    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoOscuro=1)
    ventana._navegacion.setCurrentRow(2)

    assert ventana.styleSheet() == hoja_estilos(True)


# --------------------------------------------------------- badge de período

def test_badge_periodo_muestra_el_periodo_actual(qtbot, conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoFechaFicticia=1, FechaFicticia="2026-08-10")
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._badge_periodo.text() == "Período 08/2026"


def test_badge_periodo_se_actualiza_al_cambiar_de_pantalla(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoFechaFicticia=1, FechaFicticia="2026-03-15")
    ventana._navegacion.setCurrentRow(2)
    assert ventana._badge_periodo.text() == "Período 03/2026"


def test_f1_sin_secciones_no_falla(qtbot, conn, monkeypatch):
    llamado = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: llamado.append(1)))
    ventana = VentanaPrincipal(conn, [])
    qtbot.addWidget(ventana)

    ventana._mostrar_ayuda()

    assert llamado == []


# --------------------------------------------------- filtrado por nivel de acceso


def _id_nivel(conn, nombre):
    return conn.execute("SELECT IdNivelAcceso FROM NivelAcceso WHERE Nombre = ?", (nombre,)).fetchone()["IdNivelAcceso"]


def test_sin_nivel_de_usuario_no_filtra_nada(qtbot, conn):
    """El default (`id_nivel_usuario=None`, el que usan todos los tests
    que no tienen nada que ver con Seguridad) muestra todas las
    secciones, sin necesitar login."""
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._navegacion.count() == 3  # separador + Uno + Dos


def test_nivel_operador_no_ve_pantalla_restringida_a_administrador(qtbot, conn):
    asegurar_permisos_pantalla(conn, ["Uno", "Dos"])
    conn.execute(
        "UPDATE PermisoPantalla SET IdNivelAcceso = ? WHERE NombrePantalla = 'Dos'", (_id_nivel(conn, "Administrador"),)
    )
    conn.commit()

    ventana = VentanaPrincipal(conn, _secciones(), id_nivel_usuario=_id_nivel(conn, "Operador"))
    qtbot.addWidget(ventana)

    nombres = [ventana._navegacion.item(i).text() for i in range(ventana._navegacion.count())]
    assert "Uno" in nombres
    assert "Dos" not in nombres


def test_nivel_administrador_ve_todas_las_pantallas(qtbot, conn):
    asegurar_permisos_pantalla(conn, ["Uno", "Dos"])
    conn.execute(
        "UPDATE PermisoPantalla SET IdNivelAcceso = ? WHERE NombrePantalla = 'Dos'", (_id_nivel(conn, "Administrador"),)
    )
    conn.commit()

    ventana = VentanaPrincipal(conn, _secciones(), id_nivel_usuario=_id_nivel(conn, "Administrador"))
    qtbot.addWidget(ventana)

    nombres = [ventana._navegacion.item(i).text() for i in range(ventana._navegacion.count())]
    assert "Uno" in nombres
    assert "Dos" in nombres
