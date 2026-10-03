"""Textos del sistema (pedido de la clienta, posterior al cierre de la
revisión "uno por uno"): pantalla para editar, sin tocar código, los
mensajes automáticos del Centro de mensajería y la ayuda contextual F1 de
cada pantalla — ver `app.negocio.plantillas_texto` para el mecanismo
(texto de fábrica + override opcional en `PlantillaTexto`, mismo patrón
de sustitución que ya usa `MensajePredefinido`).

Alcance acotado a pedido explícito de la clienta: los 8 mensajes de
`app.negocio.plantillas_texto.MENSAJES_EDITABLES` (`mensaje_detalle_
reserva_aislada` se sumó en una segunda vuelta — su cuerpo, armado con
loops de reservas/llaves/pagos/etc., llega como una sola variable ya
resuelta, `{detalle_items}`; solo su encabezado es texto de plantilla de
verdad) y la ayuda F1 de cada `Seccion` del menú (hallazgo #23 de la
auditoría DC-01/DC-10: "la ayuda F1 funciona y es contextual, pero no es
editable sin tocar código"). Los textos de WhatsApp de Oferta/
Disponibilidad (loops de franjas) siguen fuera de esta funcionalidad.

No usa `PantallaCRUD` (mismo criterio que Usuarios y permisos/Gestor de
archivos): no hay alta/baja, los "slots" son un conjunto fijo que define
el código — solo edición y "Restablecer al original". Formato: lista a
la izquierda agrupada en dos secciones (separadores no seleccionables,
mismo mecanismo que los separadores de categoría del menú lateral),
editor grande a la derecha con la lista de variables disponibles como
ayuda y dos botones.

Las partes condicionales de un mensaje (si hay feriados, si el
profesional queda deudor) no son editables acá — llegan a la plantilla
ya armadas como una variable más (`{bloque_feriados}`, etc.), decisión
explícita de la clienta para no poder dejar un mensaje a medio armar."""
from __future__ import annotations

import re
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.gui.main_window import Seccion
from app.negocio.plantillas_texto import (
    MENSAJES_EDITABLES,
    guardar_texto_personalizado,
    obtener_texto_personalizado,
    resolver_plantilla,
)

_ANCHO_LISTA = 360
_ANCHO_BOTON = 200
_CLAVE = Qt.ItemDataRole.UserRole


def _item_separador(texto: str) -> QListWidgetItem:
    item = QListWidgetItem(f"— {texto} —")
    item.setFlags(Qt.ItemFlag.NoItemFlags)
    return item


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


class _PanelTextosDelSistema(QWidget):
    def __init__(self, conn: sqlite3.Connection, secciones: list[Seccion] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._secciones = secciones or []
        self._clave_actual: str | None = None
        self._default_actual: str = ""
        self._variables_actuales: tuple[str, ...] = ()
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)

        panel_izquierda = QWidget()
        panel_izquierda.setObjectName("panelSolapa")
        columna = QVBoxLayout(panel_izquierda)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.addWidget(_titulo_campo("Textos editables"))
        self.lista = QListWidget()
        self.lista.setFixedWidth(_ANCHO_LISTA)
        self.lista.currentItemChanged.connect(self._al_cambiar_seleccion)
        columna.addWidget(self.lista, stretch=1)
        layout.addWidget(panel_izquierda)

        panel_derecha = QWidget()
        panel_derecha.setObjectName("panelSolapa")
        columna_derecha = QVBoxLayout(panel_derecha)
        self.etiqueta_nombre = QLabel("")
        self.etiqueta_nombre.setObjectName("subtituloSeccion")
        columna_derecha.addWidget(self.etiqueta_nombre)
        self.etiqueta_variables = QLabel("")
        self.etiqueta_variables.setWordWrap(True)
        columna_derecha.addWidget(self.etiqueta_variables)

        self.editor = QPlainTextEdit()
        columna_derecha.addWidget(self.editor, stretch=1)

        fila_botones = QHBoxLayout()
        self.boton_guardar = QPushButton("Guardar")
        self.boton_guardar.setObjectName("botonPrimario")
        self.boton_guardar.clicked.connect(self._guardar)
        self.boton_restablecer = QPushButton("Restablecer al original")
        self.boton_restablecer.setObjectName("botonSecundario")
        self.boton_restablecer.clicked.connect(self._restablecer)
        for boton in (self.boton_guardar, self.boton_restablecer):
            boton.setFixedWidth(_ANCHO_BOTON)
            fila_botones.addWidget(boton)
        fila_botones.addStretch()
        columna_derecha.addLayout(fila_botones)
        layout.addWidget(panel_derecha, stretch=1)

        self._llenar_lista()
        self._mostrar_sin_seleccion()

    # ------------------------------------------------------------------ lista

    def _llenar_lista(self) -> None:
        self.lista.addItem(_item_separador("MENSAJES AUTOMÁTICOS"))
        for plantilla in MENSAJES_EDITABLES:
            item = QListWidgetItem(self._texto_item(plantilla.clave, plantilla.nombre))
            item.setData(_CLAVE, ("mensaje", plantilla.clave, plantilla.nombre, plantilla.default, plantilla.variables))
            self.lista.addItem(item)

        if self._secciones:
            self.lista.addItem(_item_separador("AYUDA CONTEXTUAL (F1)"))
            for seccion in self._secciones:
                clave = f"ayuda:{seccion.nombre}"
                default = seccion.ayuda or "Esta pantalla todavía no tiene ayuda contextual cargada."
                item = QListWidgetItem(self._texto_item(clave, seccion.nombre))
                item.setData(_CLAVE, ("ayuda", clave, seccion.nombre, default, ()))
                self.lista.addItem(item)

    def _texto_item(self, clave: str, nombre: str) -> str:
        personalizado = obtener_texto_personalizado(self.conn, clave) is not None
        return f"{nombre} (personalizado)" if personalizado else nombre

    def _refrescar_item_actual(self) -> None:
        item = self.lista.currentItem()
        if item is None:
            return
        _tipo, clave, nombre, _default, _variables = item.data(_CLAVE)
        item.setText(self._texto_item(clave, nombre))

    # ------------------------------------------------------------------ selección

    def _mostrar_sin_seleccion(self) -> None:
        self.etiqueta_nombre.setText("Elegí un texto de la lista para editarlo")
        self.etiqueta_variables.setText("")
        self.editor.setPlainText("")
        self.editor.setEnabled(False)
        self.boton_guardar.setEnabled(False)
        self.boton_restablecer.setEnabled(False)
        self._clave_actual = None

    def _al_cambiar_seleccion(self, actual: QListWidgetItem | None, _anterior: QListWidgetItem | None) -> None:
        if actual is None or not (actual.flags() & Qt.ItemFlag.ItemIsSelectable):
            self._mostrar_sin_seleccion()
            return
        _tipo, clave, nombre, default, variables = actual.data(_CLAVE)
        self._clave_actual = clave
        self._default_actual = default
        self._variables_actuales = variables
        self.etiqueta_nombre.setText(nombre)
        self.etiqueta_variables.setText(
            f"Variables disponibles: {', '.join('{' + v + '}' for v in variables)}" if variables
            else "Este texto no tiene variables — es fijo, igual para cualquier pantalla."
        )
        self.editor.setPlainText(resolver_plantilla(self.conn, clave, default))
        self.editor.setEnabled(True)
        self.boton_guardar.setEnabled(True)
        self.boton_restablecer.setEnabled(obtener_texto_personalizado(self.conn, clave) is not None)

    # ------------------------------------------------------------------ acciones

    def _variables_desconocidas(self, texto: str) -> list[str]:
        encontradas = set(re.findall(r"\{(\w+)\}", texto))
        return sorted(encontradas - set(self._variables_actuales))

    def _guardar(self) -> None:
        if self._clave_actual is None:
            return
        texto = self.editor.toPlainText()
        desconocidas = self._variables_desconocidas(texto)
        if desconocidas:
            lista = ", ".join("{" + v + "}" for v in desconocidas)
            respuesta = QMessageBox.question(
                self, "Textos del sistema",
                f"El texto tiene {lista}, que no es ninguna de las variables disponibles para este mensaje — "
                "va a aparecer tal cual, sin reemplazar. ¿Guardás igual?",
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                return
        guardar_texto_personalizado(self.conn, self._clave_actual, texto)
        self.boton_restablecer.setEnabled(obtener_texto_personalizado(self.conn, self._clave_actual) is not None)
        self._refrescar_item_actual()

    def _restablecer(self) -> None:
        if self._clave_actual is None:
            return
        respuesta = QMessageBox.question(
            self, "Textos del sistema",
            "¿Restablecer este texto a la redacción original? Se pierde la personalización actual.",
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        guardar_texto_personalizado(self.conn, self._clave_actual, None)
        self.editor.setPlainText(self._default_actual)
        self.boton_restablecer.setEnabled(False)
        self._refrescar_item_actual()
