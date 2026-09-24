"""Usuarios y permisos (Seguridad — ver CLAUDE.md, sección "Seguridad").

No usa `PantallaCRUD` (mismo criterio que Bloques rígidos/Gestor de
archivos): el alta de un usuario necesita contraseña + confirmación, la
edición no debería exponer ni pisar la contraseña sin querer, y la
segunda tabla (permisos por pantalla) no es un catálogo de registros
propios.

Formato solapa con DOS pestañas (pedido explícito de la clienta al
revisar la primera versión, que las apilaba las dos en una sola solapa):
mismo patrón que `_PanelHistorialGeneral`/`_PanelEstadisticasVarias` de
Estadísticas — cada solapa es su propia clase con
`objectName="panelSolapa"` y su propio `showEvent` (necesario para que
cada una enfoque su propio primer control al mostrarse), pasada
directamente a `addTab(...)` sin envolver en un `QScrollArea` externo
(rompería la propagación del evento):

- **"Usuarios"**: alta, nivel de acceso, activo/inactivo, resetear
  contraseña (sin conocer la actual — pedido de la clienta, una de las
  dos formas de recuperar un acceso perdido) y ver el historial de
  cambios de contraseña de cada uno.
- **"Permisos por pantalla"**: un combo de nivel por fila, uno por cada
  pantalla ya registrada en `PermisoPantalla` (`asegurar_permisos_
  pantalla`, llamado al arrancar la GUI) — cambiar el combo escribe
  directo a la base, sin un botón "Guardar" aparte (mismo criterio
  inmediato que "Marcar como principal" en Gestor de archivos): pedido
  explícito de la clienta, que la asignación de nivel de cada pantalla
  se pueda cambiar desde el sistema en cualquier momento.

No se permite desactivar ni degradar (bajarle el nivel) al único
usuario Administrador activo que quede — dejaría el sistema sin nadie
que pueda administrarlo (`app.negocio.seguridad.
hay_otro_usuario_activo_de_nivel`)."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.orden_tabla import OrdenTabla
from app.negocio.seguridad import cambiar_contrasena, crear_usuario, hay_otro_usuario_activo_de_nivel
from app.repositorio.registro import obtener_repositorio

_ID_REGISTRO = Qt.ItemDataRole.UserRole
_ANCHO_BOTON = 260  # calculado para "Ver historial de contraseñas"
_PADDING_COLUMNA = 30  # mismo criterio que novedades._ajustar_columnas/bloques_rigidos


def _ajustar_columnas(tabla: QTableWidget) -> None:
    tabla.resizeColumnsToContents()
    for columna in range(tabla.columnCount()):
        tabla.setColumnWidth(columna, tabla.columnWidth(columna) + _PADDING_COLUMNA)


class _DialogoUsuarioNuevo(QDialog):
    def __init__(self, conn: sqlite3.Connection, niveles: list[sqlite3.Row], parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Nuevo usuario")
        layout = QFormLayout(self)

        self.campo_nombre = QLineEdit()
        layout.addRow("Nombre de usuario", self.campo_nombre)
        self.campo_contrasena = QLineEdit()
        self.campo_contrasena.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Contraseña", self.campo_contrasena)
        self.campo_confirmar = QLineEdit()
        self.campo_confirmar.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Confirmar contraseña", self.campo_confirmar)
        self.combo_nivel = QComboBox()
        for nivel in niveles:
            self.combo_nivel.addItem(nivel["Nombre"], nivel["IdNivelAcceso"])
        layout.addRow("Nivel de acceso", self.combo_nivel)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

    def _validar_y_aceptar(self) -> None:
        if self.campo_contrasena.text() != self.campo_confirmar.text():
            QMessageBox.warning(self, "Nuevo usuario", "Las dos contraseñas no coinciden.")
            return
        try:
            crear_usuario(
                self.conn, self.campo_nombre.text().strip(), self.campo_contrasena.text(), self.combo_nivel.currentData(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Nuevo usuario", str(error))
            return
        self.accept()


class _DialogoUsuarioEditar(QDialog):
    def __init__(self, usuario: sqlite3.Row, niveles: list[sqlite3.Row], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar usuario")
        layout = QFormLayout(self)

        self.campo_nombre = QLineEdit(usuario["NombreUsuario"])
        layout.addRow("Nombre de usuario", self.campo_nombre)
        self.combo_nivel = QComboBox()
        for nivel in niveles:
            self.combo_nivel.addItem(nivel["Nombre"], nivel["IdNivelAcceso"])
        indice = next((i for i, n in enumerate(niveles) if n["IdNivelAcceso"] == usuario["IdNivelAcceso"]), 0)
        self.combo_nivel.setCurrentIndex(indice)
        layout.addRow("Nivel de acceso", self.combo_nivel)
        self.casilla_activo = QCheckBox("Activo")
        self.casilla_activo.setChecked(bool(usuario["Activo"]))
        layout.addRow(self.casilla_activo)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

    def _validar_y_aceptar(self) -> None:
        if not self.campo_nombre.text().strip():
            QMessageBox.warning(self, "Editar usuario", "El nombre de usuario no puede estar vacío.")
            return
        self.accept()

    def valores(self) -> dict:
        return {
            "NombreUsuario": self.campo_nombre.text().strip(),
            "IdNivelAcceso": self.combo_nivel.currentData(),
            "Activo": 1 if self.casilla_activo.isChecked() else 0,
        }


class _DialogoContrasenaNueva(QDialog):
    def __init__(self, titulo: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        layout = QFormLayout(self)

        self.campo_nueva = QLineEdit()
        self.campo_nueva.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Contraseña nueva", self.campo_nueva)
        self.campo_confirmar = QLineEdit()
        self.campo_confirmar.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Confirmar", self.campo_confirmar)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

    def _validar_y_aceptar(self) -> None:
        if not self.campo_nueva.text():
            QMessageBox.warning(self, self.windowTitle(), "La contraseña no puede estar vacía.")
            return
        if self.campo_nueva.text() != self.campo_confirmar.text():
            QMessageBox.warning(self, self.windowTitle(), "Las dos contraseñas no coinciden.")
            return
        self.accept()

    def contrasena(self) -> str:
        return self.campo_nueva.text()


class _DialogoHistorialContrasenas(QDialog):
    def __init__(self, conn: sqlite3.Connection, id_usuario: int, nombre_usuario: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Historial de contraseñas — {nombre_usuario}")
        layout = QVBoxLayout(self)

        tabla = QTableWidget()
        tabla.setColumnCount(3)
        tabla.setHorizontalHeaderLabels(["Fecha y hora", "Motivo", "Realizado por"])
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        filas = conn.execute(
            "SELECT h.FechaHora, h.Motivo, u.NombreUsuario AS RealizadoPor "
            "FROM HistorialContrasenas h LEFT JOIN Usuario u ON u.IdUsuario = h.IdUsuarioQueRealizoElCambio "
            "WHERE h.IdUsuario = ? ORDER BY h.FechaHora DESC",
            (id_usuario,),
        ).fetchall()
        tabla.setRowCount(len(filas))
        for fila_idx, f in enumerate(filas):
            tabla.setItem(fila_idx, 0, QTableWidgetItem(f["FechaHora"]))
            tabla.setItem(fila_idx, 1, QTableWidgetItem(f["Motivo"]))
            tabla.setItem(fila_idx, 2, QTableWidgetItem(f["RealizadoPor"] or "-"))
        _ajustar_columnas(tabla)
        layout.addWidget(tabla)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        botones.accepted.connect(self.accept)
        layout.addWidget(botones)


class _PanelUsuarios(QWidget):
    """Solapa "Usuarios": columna de botones a la izquierda, tabla a la
    derecha — mismo lenguaje que los catálogos genéricos."""

    def __init__(self, conn: sqlite3.Connection, id_usuario_actual: int | None, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self.id_usuario_actual = id_usuario_actual
        self.repositorio = obtener_repositorio(conn, "Usuario")
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._orden_usuarios.reiniciar()
        self.actualizar()
        self.boton_nuevo.setFocus()

    def _armar_ui(self) -> None:
        layout_solapa = QHBoxLayout(self)

        columna_widget = QWidget()
        columna = QVBoxLayout(columna_widget)
        self.boton_nuevo = QPushButton("Nuevo usuario")
        self.boton_nuevo.setObjectName("botonPrimario")
        self.boton_nuevo.setFixedWidth(_ANCHO_BOTON)
        self.boton_nuevo.clicked.connect(self._nuevo)
        self.boton_editar = QPushButton("Editar usuario")
        self.boton_editar.setObjectName("botonSecundario")
        self.boton_editar.setFixedWidth(_ANCHO_BOTON)
        self.boton_editar.clicked.connect(self._editar)
        self.boton_resetear = QPushButton("Resetear contraseña")
        self.boton_resetear.setObjectName("botonSecundario")
        self.boton_resetear.setFixedWidth(_ANCHO_BOTON)
        self.boton_resetear.clicked.connect(self._resetear_contrasena)
        self.boton_historial = QPushButton("Ver historial de contraseñas")
        self.boton_historial.setObjectName("botonSecundario")
        self.boton_historial.setFixedWidth(_ANCHO_BOTON)
        self.boton_historial.clicked.connect(self._ver_historial)
        columna.addWidget(self.boton_nuevo)
        columna.addWidget(self.boton_editar)
        columna.addWidget(self.boton_resetear)
        columna.addWidget(self.boton_historial)
        columna.addStretch()
        layout_solapa.addWidget(columna_widget)

        self.tabla_usuarios = QTableWidget()
        self.tabla_usuarios.setColumnCount(4)
        self.tabla_usuarios.setHorizontalHeaderLabels(["Usuario", "Nivel de acceso", "Activo", "Último ingreso"])
        self.tabla_usuarios.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_usuarios.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_usuarios.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_usuarios.doubleClicked.connect(self._editar)
        layout_solapa.addWidget(self.tabla_usuarios, stretch=1)

        self._foco = instalar_enter_avanza_foco(
            [self.boton_nuevo, self.boton_editar, self.boton_resetear, self.boton_historial], parent=self,
        )
        self._orden_usuarios = OrdenTabla(self.tabla_usuarios, self.actualizar)

    def _clave_orden(self, registros: list[sqlite3.Row], columna: int, niveles: dict[int, str]):
        def clave(r: sqlite3.Row):
            if columna == 0:
                return r["NombreUsuario"]
            if columna == 1:
                return niveles.get(r["IdNivelAcceso"], "")
            if columna == 2:
                return bool(r["Activo"])
            return r["UltimoIngreso"] or ""
        return clave

    def actualizar(self) -> None:
        registros = self.repositorio.listar()
        niveles = {n["IdNivelAcceso"]: n["Nombre"] for n in obtener_repositorio(self.conn, "NivelAcceso").listar()}
        if self._orden_usuarios.columna is not None:
            registros = sorted(
                registros, key=self._clave_orden(registros, self._orden_usuarios.columna, niveles),
                reverse=not self._orden_usuarios.ascendente,
            )
        self.tabla_usuarios.setRowCount(len(registros))
        for fila_idx, r in enumerate(registros):
            item = QTableWidgetItem(r["NombreUsuario"])
            item.setData(_ID_REGISTRO, r["IdUsuario"])
            self.tabla_usuarios.setItem(fila_idx, 0, item)
            self.tabla_usuarios.setItem(fila_idx, 1, QTableWidgetItem(niveles.get(r["IdNivelAcceso"], "")))
            self.tabla_usuarios.setItem(fila_idx, 2, QTableWidgetItem("Sí" if r["Activo"] else "No"))
            self.tabla_usuarios.setItem(fila_idx, 3, QTableWidgetItem(r["UltimoIngreso"] or "-"))
        _ajustar_columnas(self.tabla_usuarios)

    def _fila_seleccionada_usuario(self):
        filas = self.tabla_usuarios.selectionModel().selectedRows()
        if not filas:
            return None
        return self.tabla_usuarios.item(filas[0].row(), 0).data(_ID_REGISTRO)

    def _nuevo(self) -> None:
        niveles = obtener_repositorio(self.conn, "NivelAcceso").listar()
        dialogo = _DialogoUsuarioNuevo(self.conn, niveles, parent=self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.actualizar()

    def _editar(self) -> None:
        id_usuario = self._fila_seleccionada_usuario()
        if id_usuario is None:
            QMessageBox.warning(self, "Editar usuario", "Elegí un usuario de la tabla.")
            return
        usuario = self.repositorio.obtener(id_usuario)
        niveles = obtener_repositorio(self.conn, "NivelAcceso").listar()
        dialogo = _DialogoUsuarioEditar(usuario, niveles, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        valores = dialogo.valores()

        # Se resuelve por NOMBRE ("Administrador"), no por `max(..., key=Orden)`:
        # si se resolviera por el nivel más alto del catálogo, sumar un nivel
        # todavía superior (ej. "Supervisor general") haría que esta variable
        # deje de apuntar a Administrador, y el guardarraíl de abajo dejaría
        # de dispararse para el último Administrador activo del sistema.
        nivel_admin = next(n for n in niveles if n["Nombre"] == "Administrador")
        orden_por_id = {n["IdNivelAcceso"]: n["Orden"] for n in niveles}

        def _alcanza_admin(id_nivel: int) -> bool:
            return orden_por_id.get(id_nivel, -1) >= nivel_admin["Orden"]

        deja_de_ser_admin_activo = (
            _alcanza_admin(usuario["IdNivelAcceso"])
            and (not _alcanza_admin(valores["IdNivelAcceso"]) or not valores["Activo"])
        )
        if deja_de_ser_admin_activo and not hay_otro_usuario_activo_de_nivel(
            self.conn, nivel_admin["IdNivelAcceso"], excluir_id=id_usuario,
        ):
            QMessageBox.warning(
                self, "Editar usuario",
                "No se puede: es el único usuario Administrador activo. "
                "Creá o activá otro Administrador antes de hacer este cambio.",
            )
            return

        try:
            self.repositorio.actualizar(id_usuario, **valores)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Editar usuario", f"Ya existe un usuario '{valores['NombreUsuario']}'.")
            return
        self.conn.commit()
        self.actualizar()

    def _resetear_contrasena(self) -> None:
        id_usuario = self._fila_seleccionada_usuario()
        if id_usuario is None:
            QMessageBox.warning(self, "Resetear contraseña", "Elegí un usuario de la tabla.")
            return
        dialogo = _DialogoContrasenaNueva("Resetear contraseña", parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        cambiar_contrasena(
            self.conn, id_usuario, dialogo.contrasena(),
            realizado_por=self.id_usuario_actual, motivo="Reseteo por administrador",
        )
        QMessageBox.information(self, "Resetear contraseña", "Contraseña actualizada.")

    def _ver_historial(self) -> None:
        id_usuario = self._fila_seleccionada_usuario()
        if id_usuario is None:
            QMessageBox.warning(self, "Historial de contraseñas", "Elegí un usuario de la tabla.")
            return
        usuario = self.repositorio.obtener(id_usuario)
        _DialogoHistorialContrasenas(self.conn, id_usuario, usuario["NombreUsuario"], parent=self).exec()


class _PanelPermisosPantalla(QWidget):
    """Solapa "Permisos por pantalla": una tabla con un combo de nivel
    por fila, sin botones — cambiar el combo escribe directo a la base."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(2)
        self.tabla.setHorizontalHeaderLabels(["Pantalla", "Nivel mínimo requerido"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla, stretch=1)

    def actualizar(self) -> None:
        filas = self.conn.execute(
            "SELECT NombrePantalla, IdNivelAcceso FROM PermisoPantalla ORDER BY NombrePantalla"
        ).fetchall()
        niveles = obtener_repositorio(self.conn, "NivelAcceso").listar()
        self.tabla.setRowCount(len(filas))
        for fila_idx, f in enumerate(filas):
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(f["NombrePantalla"]))
            combo = QComboBox()
            for nivel in niveles:
                combo.addItem(nivel["Nombre"], nivel["IdNivelAcceso"])
            indice = next((i for i, n in enumerate(niveles) if n["IdNivelAcceso"] == f["IdNivelAcceso"]), 0)
            combo.setCurrentIndex(indice)
            combo.currentIndexChanged.connect(
                lambda _indice, pantalla=f["NombrePantalla"], c=combo: self._cambiar_nivel(pantalla, c.currentData())
            )
            self.tabla.setCellWidget(fila_idx, 1, combo)
        _ajustar_columnas(self.tabla)

    def _cambiar_nivel(self, nombre_pantalla: str, id_nivel: int) -> None:
        self.conn.execute(
            "UPDATE PermisoPantalla SET IdNivelAcceso = ? WHERE NombrePantalla = ?", (id_nivel, nombre_pantalla)
        )
        self.conn.commit()


class PantallaUsuarios(QWidget):
    def __init__(self, conn: sqlite3.Connection, id_usuario_actual: int | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Usuarios y permisos".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_usuarios = _PanelUsuarios(conn, id_usuario_actual)
        self.pestanas.addTab(self.panel_usuarios, "Usuarios")
        self.panel_permisos = _PanelPermisosPantalla(conn)
        self.pestanas.addTab(self.panel_permisos, "Permisos por pantalla")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
