import pytest
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.usuarios import (
    PantallaUsuarios,
    _DialogoContrasenaNueva,
    _DialogoHistorialContrasenas,
    _DialogoUsuarioEditar,
    _DialogoUsuarioNuevo,
)
from app.negocio.seguridad import asegurar_permisos_pantalla, autenticar, crear_usuario
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


# --------------------------------------------------------------- layout


def test_titulo_de_pantalla_es_jerarquia_1(qtbot, conn):
    pantalla = PantallaUsuarios(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "USUARIOS Y PERMISOS"


def test_tiene_formato_solapa(qtbot, conn):
    pantalla = PantallaUsuarios(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert solapas.tabText(0) == "Usuarios y permisos"


# ------------------------------------------------------------- usuarios


def test_tabla_usuarios_muestra_los_cargados(qtbot, conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    pantalla = PantallaUsuarios(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_usuarios.rowCount() == 1
    assert pantalla.tabla_usuarios.item(0, 0).text() == "ana"
    assert pantalla.tabla_usuarios.item(0, 1).text() == "Operador"
    assert pantalla.tabla_usuarios.item(0, 2).text() == "Sí"


def test_nuevo_usuario_crea_uno(qtbot, conn, monkeypatch):
    def _fake_exec(self):
        self.campo_nombre.setText("ana")
        self.campo_contrasena.setText("clave123")
        self.campo_confirmar.setText("clave123")
        self._validar_y_aceptar()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoUsuarioNuevo, "exec", _fake_exec)

    pantalla = PantallaUsuarios(conn)
    qtbot.addWidget(pantalla)
    pantalla._nuevo()

    assert autenticar(conn, "ana", "clave123") is not None
    assert pantalla.tabla_usuarios.rowCount() == 1


def test_editar_usuario_cambia_nivel_y_activo(qtbot, conn, monkeypatch):
    id_usuario = crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))

    def _fake_exec(self):
        indice = next(i for i in range(self.combo_nivel.count()) if self.combo_nivel.itemText(i) == "Administrador")
        self.combo_nivel.setCurrentIndex(indice)
        self.casilla_activo.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoUsuarioEditar, "exec", _fake_exec)

    pantalla = PantallaUsuarios(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_usuarios.selectRow(0)
    pantalla._editar()

    usuario = obtener_repositorio(conn, "Usuario").obtener(id_usuario)
    assert usuario["IdNivelAcceso"] == _id_nivel(conn, "Administrador")
    assert usuario["Activo"] == 0


def test_no_deja_desactivar_al_unico_administrador_activo(qtbot, conn, monkeypatch):
    id_admin = crear_usuario(conn, "admin", "clave123", _id_nivel(conn, "Administrador"))

    def _fake_exec(self):
        self.casilla_activo.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoUsuarioEditar, "exec", _fake_exec)

    pantalla = PantallaUsuarios(conn, id_usuario_actual=id_admin)
    qtbot.addWidget(pantalla)
    pantalla.tabla_usuarios.selectRow(0)
    pantalla._editar()

    usuario = obtener_repositorio(conn, "Usuario").obtener(id_admin)
    assert usuario["Activo"] == 1  # no se aplicó el cambio


def test_permite_desactivar_administrador_si_hay_otro_activo(qtbot, conn, monkeypatch):
    id_admin_1 = crear_usuario(conn, "admin1", "clave123", _id_nivel(conn, "Administrador"))
    crear_usuario(conn, "admin2", "clave123", _id_nivel(conn, "Administrador"))

    def _fake_exec(self):
        self.casilla_activo.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoUsuarioEditar, "exec", _fake_exec)

    pantalla = PantallaUsuarios(conn, id_usuario_actual=id_admin_1)
    qtbot.addWidget(pantalla)
    fila_admin1 = next(f for f in range(pantalla.tabla_usuarios.rowCount()) if pantalla.tabla_usuarios.item(f, 0).text() == "admin1")
    pantalla.tabla_usuarios.selectRow(fila_admin1)
    pantalla._editar()

    usuario = obtener_repositorio(conn, "Usuario").obtener(id_admin_1)
    assert usuario["Activo"] == 0


def test_resetear_contrasena_registra_quien_lo_hizo(qtbot, conn, monkeypatch):
    id_admin = crear_usuario(conn, "admin", "clave123", _id_nivel(conn, "Administrador"))
    id_usuario = crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))

    def _fake_exec(self):
        self.campo_nueva.setText("nueva123")
        self.campo_confirmar.setText("nueva123")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoContrasenaNueva, "exec", _fake_exec)

    pantalla = PantallaUsuarios(conn, id_usuario_actual=id_admin)
    qtbot.addWidget(pantalla)
    fila_ana = next(f for f in range(pantalla.tabla_usuarios.rowCount()) if pantalla.tabla_usuarios.item(f, 0).text() == "ana")
    pantalla.tabla_usuarios.selectRow(fila_ana)
    pantalla._resetear_contrasena()

    assert autenticar(conn, "ana", "nueva123") is not None
    historial = conn.execute(
        "SELECT * FROM HistorialContrasenas WHERE IdUsuario = ?", (id_usuario,)
    ).fetchone()
    assert historial["IdUsuarioQueRealizoElCambio"] == id_admin
    assert historial["Motivo"] == "Reseteo por administrador"


def test_ver_historial_abre_dialogo_con_las_filas_del_usuario(qtbot, conn, monkeypatch):
    from app.negocio.seguridad import cambiar_contrasena

    id_admin = crear_usuario(conn, "admin", "clave123", _id_nivel(conn, "Administrador"))
    id_usuario = crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    cambiar_contrasena(conn, id_usuario, "nueva123", realizado_por=id_admin, motivo="Reseteo por administrador")

    capturado = {}

    def _fake_init(self, conn_, id_usuario_, nombre_usuario_, parent=None):
        capturado["id_usuario"] = id_usuario_
        capturado["nombre"] = nombre_usuario_
        QDialog.__init__(self, parent)

    monkeypatch.setattr(_DialogoHistorialContrasenas, "__init__", _fake_init)
    monkeypatch.setattr(_DialogoHistorialContrasenas, "exec", lambda self: QDialog.DialogCode.Accepted)

    pantalla = PantallaUsuarios(conn, id_usuario_actual=id_admin)
    qtbot.addWidget(pantalla)
    fila_ana = next(f for f in range(pantalla.tabla_usuarios.rowCount()) if pantalla.tabla_usuarios.item(f, 0).text() == "ana")
    pantalla.tabla_usuarios.selectRow(fila_ana)
    pantalla._ver_historial()

    assert capturado["id_usuario"] == id_usuario
    assert capturado["nombre"] == "ana"


# --------------------------------------------------------- permisos por pantalla


def test_tabla_permisos_lista_las_pantallas_registradas(qtbot, conn):
    asegurar_permisos_pantalla(conn, ["Reservas", "Pagos"])
    pantalla = PantallaUsuarios(conn)
    qtbot.addWidget(pantalla)
    nombres = {pantalla.tabla_permisos.item(f, 0).text() for f in range(pantalla.tabla_permisos.rowCount())}
    assert {"Reservas", "Pagos"} <= nombres


def test_cambiar_combo_de_permiso_actualiza_la_base_de_inmediato(qtbot, conn):
    asegurar_permisos_pantalla(conn, ["Reservas"])
    pantalla = PantallaUsuarios(conn)
    qtbot.addWidget(pantalla)
    fila = next(f for f in range(pantalla.tabla_permisos.rowCount()) if pantalla.tabla_permisos.item(f, 0).text() == "Reservas")
    combo = pantalla.tabla_permisos.cellWidget(fila, 1)
    indice_admin = next(i for i in range(combo.count()) if combo.itemText(i) == "Administrador")

    combo.setCurrentIndex(indice_admin)

    fila_bd = conn.execute("SELECT IdNivelAcceso FROM PermisoPantalla WHERE NombrePantalla = 'Reservas'").fetchone()
    assert fila_bd["IdNivelAcceso"] == _id_nivel(conn, "Administrador")
