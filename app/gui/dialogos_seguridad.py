"""Diálogos de Seguridad (login al arrancar y bloqueo por inactividad —
ver CLAUDE.md, sección "Seguridad"). Viven aparte de `app/gui/pantallas/`
porque no son una sección del menú: los arma `gui_main.main()` antes de
mostrar `VentanaPrincipal`, y el bloqueo se dispara solo, sin que el
operador lo pida desde ningún lado."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.negocio.seguridad import (
    autenticar,
    crear_usuario,
    establecer_contrasena_maestra,
    hay_contrasena_maestra,
    hay_usuarios,
    verificar_contrasena_maestra,
)

_MINUTOS_INACTIVIDAD_DEFECTO = 15


class DialogoLogin(QDialog):
    """Login al arrancar la GUI. Si todavía no hay ningún usuario cargado
    (primer arranque de esta base), muestra un alta de Administrador en
    vez de un login que nadie podría pasar — `crear_usuario` con el
    nivel de mayor Orden disponible. Tras un login (o alta) exitoso, el
    usuario autenticado queda en `self.usuario`.

    El alta inicial pide también una contraseña maestra (pedido
    explícito de la clienta): sin esto, si alguna vez se pierde el
    acceso del único Administrador antes de que a alguien se le ocurra
    configurar una maestra desde la solapa Seguridad, no habría ninguna
    forma de recuperar el sistema — así queda esa red de seguridad
    puesta desde el primer momento, no como un paso opcional posterior."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.usuario: sqlite3.Row | None = None
        self._alta_inicial = not hay_usuarios(conn)
        self.setWindowTitle("Sistema Espacio Ramos — Ingresar" if not self._alta_inicial else "Crear administrador")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        if self._alta_inicial:
            aviso = QLabel(
                "Todavía no hay ningún usuario cargado.\n"
                "Creá el primer usuario, con nivel Administrador, para empezar a usar el sistema."
            )
            aviso.setWordWrap(True)
            layout.addWidget(aviso)

        formulario = QFormLayout()
        self.campo_usuario = QLineEdit()
        formulario.addRow("Usuario", self.campo_usuario)
        self.campo_contrasena = QLineEdit()
        self.campo_contrasena.setEchoMode(QLineEdit.EchoMode.Password)
        formulario.addRow("Contraseña", self.campo_contrasena)
        if self._alta_inicial:
            self.campo_confirmar = QLineEdit()
            self.campo_confirmar.setEchoMode(QLineEdit.EchoMode.Password)
            formulario.addRow("Confirmar contraseña", self.campo_confirmar)
            self.campo_maestra = QLineEdit()
            self.campo_maestra.setEchoMode(QLineEdit.EchoMode.Password)
            formulario.addRow("Contraseña maestra (recuperación)", self.campo_maestra)
            self.campo_maestra_confirmar = QLineEdit()
            self.campo_maestra_confirmar.setEchoMode(QLineEdit.EchoMode.Password)
            formulario.addRow("Confirmar contraseña maestra", self.campo_maestra_confirmar)
        layout.addLayout(formulario)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Crear administrador" if self._alta_inicial else "Ingresar"
        )
        botones.accepted.connect(self._confirmar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        self.campo_usuario.setFocus()

    def _confirmar(self) -> None:
        if self._alta_inicial:
            self._crear_administrador()
        else:
            self._intentar_login()

    def _intentar_login(self) -> None:
        usuario = autenticar(self.conn, self.campo_usuario.text().strip(), self.campo_contrasena.text())
        if usuario is None:
            QMessageBox.warning(self, "Ingresar", "Usuario o contraseña incorrectos.")
            self.campo_contrasena.clear()
            self.campo_contrasena.setFocus()
            return
        self.usuario = usuario
        self.accept()

    def _crear_administrador(self) -> None:
        nombre = self.campo_usuario.text().strip()
        contrasena = self.campo_contrasena.text()
        if contrasena != self.campo_confirmar.text():
            QMessageBox.warning(self, "Crear administrador", "Las dos contraseñas no coinciden.")
            return
        if not self.campo_maestra.text():
            QMessageBox.warning(self, "Crear administrador", "La contraseña maestra no puede estar vacía.")
            return
        if self.campo_maestra.text() != self.campo_maestra_confirmar.text():
            QMessageBox.warning(self, "Crear administrador", "Las dos contraseñas maestras no coinciden.")
            return
        # Por NOMBRE ("Administrador"), no por el nivel más alto del catálogo
        # (`ORDER BY Orden DESC`): el primer usuario de una base nueva tiene
        # que quedar Administrador, ni más ni menos, sin importar si más
        # adelante se suma un nivel por encima (ej. "Supervisor general") —
        # promoverlo a ese nivel es una decisión aparte, no algo que deba
        # pasar solo porque este método arrancó antes de que existiera.
        nivel = self.conn.execute(
            "SELECT IdNivelAcceso FROM NivelAcceso WHERE Nombre = 'Administrador'"
        ).fetchone() or self.conn.execute(
            "SELECT IdNivelAcceso FROM NivelAcceso ORDER BY Orden DESC LIMIT 1"
        ).fetchone()
        try:
            crear_usuario(self.conn, nombre, contrasena, nivel["IdNivelAcceso"])
        except ValueError as error:
            QMessageBox.warning(self, "Crear administrador", str(error))
            return
        establecer_contrasena_maestra(self.conn, self.campo_maestra.text())
        self.usuario = autenticar(self.conn, nombre, contrasena)
        self.accept()


class DialogoBaseDesactualizada(QDialog):
    """Cartel bloqueante al arrancar (`gui_main.main`): se dispara cuando
    `app.negocio.backup.hay_backup_mas_reciente_sin_sincronizar` detecta
    que la base local de esta máquina quedó atrás de un backup generado
    por otra instalación y ya sincronizado por Drive acá (ver CLAUDE.md,
    sección "Backup y sincronización"). Pedido explícito de la clienta:
    "casi que me obligue a levantar y a usar lo sincronizado" — por eso
    no hay ningún botón de "seguir igual" a la vista; la única vía de
    escape ("Continuar sin sincronizar") pide la contraseña maestra.

    No actúa sobre la base directamente — deja la decisión en
    `self.accion` ("restaurar"/"sin_sincronizar") para que `gui_main.
    main()` la ejecute, con la conexión vieja ya cerrada antes de tocar
    el archivo (reescribirlo con una conexión todavía abierta encima
    puede fallar, sobre todo en Windows)."""

    def __init__(self, conn: sqlite3.Connection, nombre_backup: str, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.accion: str | None = None
        self.setWindowTitle("Base de datos desactualizada")
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self._armar_ui(nombre_backup)

    def _armar_ui(self, nombre_backup: str) -> None:
        layout = QVBoxLayout(self)

        etiqueta = QLabel(
            "Se encontró un backup más nuevo que esta base, sincronizado desde otra instalación "
            f"({nombre_backup}).\n\n"
            "Por seguridad, hay que restaurarlo antes de continuar — así se evita que la información "
            "de esta máquina pise a la más actualizada."
        )
        etiqueta.setWordWrap(True)
        layout.addWidget(etiqueta)

        boton_restaurar = QPushButton("Restaurar y continuar")
        boton_restaurar.setObjectName("botonPrimario")
        boton_restaurar.clicked.connect(self._elegir_restaurar)
        layout.addWidget(boton_restaurar)

        boton_sin_sincronizar = QPushButton("Continuar sin sincronizar")
        boton_sin_sincronizar.setObjectName("botonSecundario")
        boton_sin_sincronizar.clicked.connect(self._elegir_sin_sincronizar)
        layout.addWidget(boton_sin_sincronizar)

        boton_salir = QPushButton("Salir del programa")
        boton_salir.setObjectName("botonSecundario")
        boton_salir.clicked.connect(self.reject)
        layout.addWidget(boton_salir)

        boton_restaurar.setFocus()

    def _elegir_restaurar(self) -> None:
        self.accion = "restaurar"
        self.accept()

    def _elegir_sin_sincronizar(self) -> None:
        if not hay_contrasena_maestra(self.conn):
            QMessageBox.warning(
                self, "Continuar sin sincronizar",
                "No hay una contraseña maestra configurada todavía en esta base — no se puede habilitar "
                "esta vía de escape.",
            )
            return
        contrasena, confirmado = QInputDialog.getText(
            self, "Continuar sin sincronizar", "Contraseña maestra:", QLineEdit.EchoMode.Password,
        )
        if not confirmado:
            return
        if not verificar_contrasena_maestra(self.conn, contrasena):
            QMessageBox.warning(self, "Continuar sin sincronizar", "Contraseña incorrecta.")
            return
        self.accion = "sin_sincronizar"
        self.accept()


class DialogoDesbloqueo(QDialog):
    """Se dispara solo tras el tiempo de inactividad configurado
    (`Configuracion.MinutosInactividadBloqueo`). No cierra sesión: lo que
    estaba cargado en cada pantalla sigue ahí, solo hay que volver a
    tipear la contraseña (la del usuario logueado, o la contraseña
    maestra) para seguir. No se puede cancelar ni cerrar con la X — la
    única salida es desbloquear."""

    def __init__(self, conn: sqlite3.Connection, usuario: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.usuario = usuario
        self.setWindowTitle("Sistema bloqueado")
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Sesión bloqueada por inactividad — Usuario: {self.usuario['NombreUsuario']}"))

        formulario = QFormLayout()
        self.campo_contrasena = QLineEdit()
        self.campo_contrasena.setEchoMode(QLineEdit.EchoMode.Password)
        formulario.addRow("Contraseña", self.campo_contrasena)
        layout.addLayout(formulario)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Desbloquear")
        botones.accepted.connect(self._intentar_desbloquear)
        layout.addWidget(botones)

        self.campo_contrasena.setFocus()

    def _intentar_desbloquear(self) -> None:
        contrasena = self.campo_contrasena.text()
        if autenticar(self.conn, self.usuario["NombreUsuario"], contrasena) is not None:
            self.accept()
            return
        if verificar_contrasena_maestra(self.conn, contrasena):
            self.accept()
            return
        QMessageBox.warning(self, "Sistema bloqueado", "Contraseña incorrecta.")
        self.campo_contrasena.clear()
        self.campo_contrasena.setFocus()

    def reject(self) -> None:  # noqa: N802 — no hay forma de cancelar un bloqueo
        pass


_EVENTOS_ACTIVIDAD = frozenset({
    QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress, QEvent.Type.Wheel,
})


class MonitorInactividad(QObject):
    """Instalado como event filter de la `QApplication` (ver
    `gui_main.main`): cualquier click/tecla/movimiento de mouse reinicia
    el cronómetro; al vencer sin actividad, dispara `DialogoDesbloqueo`
    de forma modal (bloquea toda interacción con `VentanaPrincipal` hasta
    desbloquear) y vuelve a arrancar el cronómetro."""

    def __init__(self, conn: sqlite3.Connection, ventana, usuario: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.ventana = ventana
        self.usuario = usuario
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._bloquear)
        self.reiniciar()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 — nombre impuesto por Qt
        if event.type() in _EVENTOS_ACTIVIDAD:
            self.reiniciar()
        return False

    def reiniciar(self) -> None:
        cfg = self.conn.execute(
            "SELECT MinutosInactividadBloqueo FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        minutos = (cfg["MinutosInactividadBloqueo"] if cfg else None) or _MINUTOS_INACTIVIDAD_DEFECTO
        self._timer.start(int(minutos * 60_000))

    def _bloquear(self) -> None:
        DialogoDesbloqueo(self.conn, self.usuario, self.ventana).exec()
        self.reiniciar()
