import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.dialogos_seguridad import (
    DialogoBaseDesactualizada,
    DialogoDesbloqueo,
    DialogoLogin,
    MonitorInactividad,
)
from app.negocio.seguridad import (
    autenticar,
    crear_usuario,
    establecer_contrasena_maestra,
    hay_usuarios,
)
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


def _id_nivel(conn, nombre):
    return conn.execute("SELECT IdNivelAcceso FROM NivelAcceso WHERE Nombre = ?", (nombre,)).fetchone()["IdNivelAcceso"]


# ------------------------------------------------------------------- login


def test_sin_usuarios_muestra_alta_de_administrador(qtbot, conn):
    dialogo = DialogoLogin(conn)
    qtbot.addWidget(dialogo)
    assert dialogo._alta_inicial is True
    assert hasattr(dialogo, "campo_confirmar")
    assert hasattr(dialogo, "campo_maestra")
    assert hasattr(dialogo, "campo_maestra_confirmar")


def test_con_usuarios_muestra_login_normal(qtbot, conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    dialogo = DialogoLogin(conn)
    qtbot.addWidget(dialogo)
    assert dialogo._alta_inicial is False
    assert not hasattr(dialogo, "campo_confirmar")


def test_alta_inicial_crea_administrador_y_autentica(qtbot, conn):
    dialogo = DialogoLogin(conn)
    qtbot.addWidget(dialogo)
    dialogo.campo_usuario.setText("admin")
    dialogo.campo_contrasena.setText("clave123")
    dialogo.campo_confirmar.setText("clave123")
    dialogo.campo_maestra.setText("maestra999")
    dialogo.campo_maestra_confirmar.setText("maestra999")

    dialogo._confirmar()

    assert dialogo.usuario is not None
    assert dialogo.usuario["NombreUsuario"] == "admin"
    assert dialogo.usuario["IdNivelAcceso"] == _id_nivel(conn, "Administrador")
    assert hay_usuarios(conn) is True
    from app.negocio.seguridad import verificar_contrasena_maestra
    assert verificar_contrasena_maestra(conn, "maestra999") is True


def test_alta_inicial_crea_administrador_aunque_haya_nivel_supervisor_general(qtbot, conn):
    """Test de regresión: con "Supervisor general" sembrado por encima de
    Administrador (ver fixture `conn`), el primer usuario de una base
    nueva tiene que seguir quedando Administrador — si se resolviera por
    `ORDER BY Orden DESC` (el nivel más alto del catálogo) en vez de por
    nombre, este alta pasaría a crear un Supervisor general sin que nadie
    lo haya pedido."""
    dialogo = DialogoLogin(conn)
    qtbot.addWidget(dialogo)
    dialogo.campo_usuario.setText("admin")
    dialogo.campo_contrasena.setText("clave123")
    dialogo.campo_confirmar.setText("clave123")
    dialogo.campo_maestra.setText("maestra999")
    dialogo.campo_maestra_confirmar.setText("maestra999")

    dialogo._confirmar()

    assert dialogo.usuario["IdNivelAcceso"] == _id_nivel(conn, "Administrador")


def test_alta_inicial_rechaza_contrasenas_que_no_coinciden(qtbot, conn):
    dialogo = DialogoLogin(conn)
    qtbot.addWidget(dialogo)
    dialogo.campo_usuario.setText("admin")
    dialogo.campo_contrasena.setText("clave123")
    dialogo.campo_confirmar.setText("otraclave")
    dialogo.campo_maestra.setText("maestra999")
    dialogo.campo_maestra_confirmar.setText("maestra999")

    dialogo._confirmar()

    assert dialogo.usuario is None
    assert hay_usuarios(conn) is False


def test_alta_inicial_rechaza_contrasena_maestra_vacia(qtbot, conn):
    dialogo = DialogoLogin(conn)
    qtbot.addWidget(dialogo)
    dialogo.campo_usuario.setText("admin")
    dialogo.campo_contrasena.setText("clave123")
    dialogo.campo_confirmar.setText("clave123")
    dialogo.campo_maestra.setText("")
    dialogo.campo_maestra_confirmar.setText("")

    dialogo._confirmar()

    assert dialogo.usuario is None
    assert hay_usuarios(conn) is False


def test_alta_inicial_rechaza_contrasenas_maestras_que_no_coinciden(qtbot, conn):
    dialogo = DialogoLogin(conn)
    qtbot.addWidget(dialogo)
    dialogo.campo_usuario.setText("admin")
    dialogo.campo_contrasena.setText("clave123")
    dialogo.campo_confirmar.setText("clave123")
    dialogo.campo_maestra.setText("maestra999")
    dialogo.campo_maestra_confirmar.setText("otramaestra")

    dialogo._confirmar()

    assert dialogo.usuario is None
    assert hay_usuarios(conn) is False


def test_login_normal_con_credenciales_correctas(qtbot, conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    dialogo = DialogoLogin(conn)
    qtbot.addWidget(dialogo)
    dialogo.campo_usuario.setText("ana")
    dialogo.campo_contrasena.setText("clave123")

    dialogo._confirmar()

    assert dialogo.usuario is not None
    assert dialogo.usuario["NombreUsuario"] == "ana"


def test_login_normal_con_credenciales_incorrectas_no_acepta(qtbot, conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    dialogo = DialogoLogin(conn)
    qtbot.addWidget(dialogo)
    dialogo.campo_usuario.setText("ana")
    dialogo.campo_contrasena.setText("incorrecta")

    dialogo._confirmar()

    assert dialogo.usuario is None
    assert dialogo.result() != QDialog.DialogCode.Accepted


# -------------------------------------------------------------- desbloqueo


def test_desbloqueo_con_contrasena_correcta_acepta(qtbot, conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    usuario = autenticar(conn, "ana", "clave123")
    dialogo = DialogoDesbloqueo(conn, usuario)
    qtbot.addWidget(dialogo)
    dialogo.campo_contrasena.setText("clave123")

    dialogo._intentar_desbloquear()

    assert dialogo.result() == QDialog.DialogCode.Accepted


def test_desbloqueo_con_contrasena_incorrecta_no_acepta(qtbot, conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    usuario = autenticar(conn, "ana", "clave123")
    dialogo = DialogoDesbloqueo(conn, usuario)
    qtbot.addWidget(dialogo)
    dialogo.campo_contrasena.setText("incorrecta")

    dialogo._intentar_desbloquear()

    assert dialogo.result() != QDialog.DialogCode.Accepted


def test_desbloqueo_con_contrasena_maestra_tambien_acepta(qtbot, conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    establecer_contrasena_maestra(conn, "maestra999")
    usuario = autenticar(conn, "ana", "clave123")
    dialogo = DialogoDesbloqueo(conn, usuario)
    qtbot.addWidget(dialogo)
    dialogo.campo_contrasena.setText("maestra999")

    dialogo._intentar_desbloquear()

    assert dialogo.result() == QDialog.DialogCode.Accepted


def test_desbloqueo_no_se_puede_cancelar(qtbot, conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    usuario = autenticar(conn, "ana", "clave123")
    dialogo = DialogoDesbloqueo(conn, usuario)
    qtbot.addWidget(dialogo)
    dialogo.show()

    dialogo.reject()

    assert dialogo.isVisible() is True


# ------------------------------------------------------- monitor de inactividad


def test_monitor_reinicia_el_timer_con_actividad(qtbot, conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    usuario = autenticar(conn, "ana", "clave123")
    obtener_repositorio(conn, "Configuracion").actualizar(1, MinutosInactividadBloqueo=1)
    conn.commit()

    monitor = MonitorInactividad(conn, None, usuario)
    tiempo_restante_inicial = monitor._timer.remainingTime()
    assert tiempo_restante_inicial > 0

    evento = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
    monitor.eventFilter(None, evento)

    assert monitor._timer.isActive()


def test_monitor_usa_los_minutos_configurados(qtbot, conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    usuario = autenticar(conn, "ana", "clave123")
    obtener_repositorio(conn, "Configuracion").actualizar(1, MinutosInactividadBloqueo=5)
    conn.commit()

    monitor = MonitorInactividad(conn, None, usuario)

    assert monitor._timer.interval() == 5 * 60_000


# ------------------------------------------------------- base desactualizada


def test_base_desactualizada_restaurar_deja_la_decision_en_accion(qtbot, conn):
    dialogo = DialogoBaseDesactualizada(conn, "Backup 2026-08-20 09h00")
    qtbot.addWidget(dialogo)

    dialogo._elegir_restaurar()

    assert dialogo.accion == "restaurar"
    assert dialogo.result() == QDialog.DialogCode.Accepted


def test_base_desactualizada_sin_contrasena_maestra_no_habilita_la_via_de_escape(qtbot, conn):
    dialogo = DialogoBaseDesactualizada(conn, "Backup 2026-08-20 09h00")
    qtbot.addWidget(dialogo)

    dialogo._elegir_sin_sincronizar()

    assert dialogo.accion is None
    assert dialogo.result() != QDialog.DialogCode.Accepted


def test_base_desactualizada_sin_sincronizar_con_contrasena_correcta_acepta(qtbot, conn, monkeypatch):
    establecer_contrasena_maestra(conn, "maestra999")
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("maestra999", True)))
    dialogo = DialogoBaseDesactualizada(conn, "Backup 2026-08-20 09h00")
    qtbot.addWidget(dialogo)

    dialogo._elegir_sin_sincronizar()

    assert dialogo.accion == "sin_sincronizar"
    assert dialogo.result() == QDialog.DialogCode.Accepted


def test_base_desactualizada_sin_sincronizar_con_contrasena_incorrecta_no_acepta(qtbot, conn, monkeypatch):
    establecer_contrasena_maestra(conn, "maestra999")
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("mala", True)))
    dialogo = DialogoBaseDesactualizada(conn, "Backup 2026-08-20 09h00")
    qtbot.addWidget(dialogo)

    dialogo._elegir_sin_sincronizar()

    assert dialogo.accion is None
    assert dialogo.result() != QDialog.DialogCode.Accepted


def test_base_desactualizada_cancelar_el_pedido_de_contrasena_no_hace_nada(qtbot, conn, monkeypatch):
    establecer_contrasena_maestra(conn, "maestra999")
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
    dialogo = DialogoBaseDesactualizada(conn, "Backup 2026-08-20 09h00")
    qtbot.addWidget(dialogo)

    dialogo._elegir_sin_sincronizar()

    assert dialogo.accion is None
    assert dialogo.result() != QDialog.DialogCode.Accepted


def test_base_desactualizada_salir_del_programa_rechaza(qtbot, conn):
    dialogo = DialogoBaseDesactualizada(conn, "Backup 2026-08-20 09h00")
    qtbot.addWidget(dialogo)

    dialogo.reject()

    assert dialogo.result() != QDialog.DialogCode.Accepted
