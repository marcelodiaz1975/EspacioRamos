"""Mensajes predefinidos (FA8, sección 5.5): biblioteca editable de
mensajes ad hoc (a diferencia de las 5 situaciones automáticas del Centro
de mensajería, sección 5.3, que también viven en MensajePredefinido pero
bajo la categoría fija "Situaciones centro de mensajería" — ver
app.negocio.mensajes._DESCRIPCION_SITUACION). Además del alta/baja/edición
genérica (PantallaCRUD), expone lo que pide la spec: un filtro por
categoría y un botón "Copiar" que arma una vista previa sustituyendo
{edificio}/{unidad}/{consultorio} por los nombres reales del vínculo
elegido en el mensaje, antes de copiarlo al portapapeles."""
from __future__ import annotations

import sqlite3

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from app.gui.crud_generico import Campo, PantallaCRUD
from app.gui.pantallas.catalogos import _opciones_consultorio, _opciones_edificio, _opciones_unidad
from app.negocio.mensajes import sustituir_variables
from app.repositorio.registro import obtener_repositorio

_TODAS = "__todas__"


def _campos_mensaje_predefinido() -> list[Campo]:
    return [
        Campo("Categoria", "Categoría"),
        Campo("Descripcion", "Descripción"),
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=_opciones_edificio),
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad),
        Campo("IdConsultorio", "Consultorio", tipo="combo", opciones=_opciones_consultorio),
        Campo("Mensaje", "Mensaje", tipo="texto_largo"),
        Campo("Activo", "Activo", tipo="booleano"),
    ]


def _variables_vinculo(conn: sqlite3.Connection, mensaje: sqlite3.Row) -> dict[str, str]:
    variables = {"edificio": "", "unidad": "", "consultorio": ""}
    if mensaje["IdConsultorio"] is not None:
        fila = conn.execute(
            "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS Edificio "
            "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
            "JOIN Edificio e ON e.IdEdificio = u.IdEdificio WHERE c.IdConsultorio = ?",
            (mensaje["IdConsultorio"],),
        ).fetchone()
        if fila:
            variables = {"edificio": fila["Edificio"], "unidad": fila["Departamento"], "consultorio": str(fila["NumeroConsultorio"])}
    elif mensaje["IdUnidad"] is not None:
        fila = conn.execute(
            "SELECT u.Departamento, e.Nombre AS Edificio FROM Unidad u "
            "JOIN Edificio e ON e.IdEdificio = u.IdEdificio WHERE u.IdUnidad = ?",
            (mensaje["IdUnidad"],),
        ).fetchone()
        if fila:
            variables = {"edificio": fila["Edificio"], "unidad": fila["Departamento"], "consultorio": ""}
    elif mensaje["IdEdificio"] is not None:
        fila = conn.execute("SELECT Nombre FROM Edificio WHERE IdEdificio = ?", (mensaje["IdEdificio"],)).fetchone()
        if fila:
            variables = {"edificio": fila["Nombre"], "unidad": "", "consultorio": ""}
    return variables


class PantallaMensajesPredefinidos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Mensajes predefinidos")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        fila_filtro = QHBoxLayout()
        fila_filtro.addWidget(QLabel("Categoría:"))
        self.combo_filtro = QComboBox()
        self.combo_filtro.currentIndexChanged.connect(self._aplicar_filtro)
        fila_filtro.addWidget(self.combo_filtro)
        fila_filtro.addStretch()
        layout.addLayout(fila_filtro)

        self.crud = PantallaCRUD(
            self.conn, "MensajePredefinido", "Mensajes predefinidos", _campos_mensaje_predefinido(),
        )
        self.crud.tabla_widget.itemSelectionChanged.connect(self._actualizar_vista_previa)
        layout.addWidget(self.crud, stretch=1)

        actualizar_original = self.crud.actualizar

        def _actualizar_con_filtro():
            actualizar_original()
            self._refrescar_categorias()
            self._aplicar_filtro()

        self.crud.actualizar = _actualizar_con_filtro
        self.crud.actualizar()

        layout.addWidget(QLabel("Vista previa (sustituye {edificio}/{unidad}/{consultorio} por el vínculo elegido)"))
        self.texto_vista_previa = QPlainTextEdit()
        self.texto_vista_previa.setReadOnly(True)
        self.texto_vista_previa.setFixedHeight(100)
        layout.addWidget(self.texto_vista_previa)
        boton_copiar = QPushButton("Copiar mensaje")
        boton_copiar.clicked.connect(self._copiar_mensaje)
        layout.addWidget(boton_copiar)

    def _refrescar_categorias(self) -> None:
        categoria_actual = self.combo_filtro.currentData()
        self.combo_filtro.blockSignals(True)
        self.combo_filtro.clear()
        self.combo_filtro.addItem("Todas", _TODAS)
        categorias = sorted({m["Categoria"] for m in obtener_repositorio(self.conn, "MensajePredefinido").listar() if m["Categoria"]})
        for categoria in categorias:
            self.combo_filtro.addItem(categoria, categoria)
        indice = self.combo_filtro.findData(categoria_actual) if categoria_actual else 0
        self.combo_filtro.setCurrentIndex(indice if indice >= 0 else 0)
        self.combo_filtro.blockSignals(False)

    def _aplicar_filtro(self) -> None:
        categoria = self.combo_filtro.currentData()
        tabla = self.crud.tabla_widget
        for fila in range(tabla.rowCount()):
            item_categoria = tabla.item(fila, 0)
            texto = item_categoria.text() if item_categoria else ""
            oculta = categoria not in (None, _TODAS) and texto != categoria
            tabla.setRowHidden(fila, oculta)

    def _actualizar_vista_previa(self) -> None:
        id_valor = self.crud.fila_seleccionada_id()
        if id_valor is None:
            self.texto_vista_previa.clear()
            return
        mensaje = self.crud.repositorio.obtener(id_valor)
        if mensaje is None:
            self.texto_vista_previa.clear()
            return
        variables = _variables_vinculo(self.conn, mensaje)
        self.texto_vista_previa.setPlainText(sustituir_variables(mensaje["Mensaje"] or "", variables))

    def _copiar_mensaje(self) -> None:
        QGuiApplication.clipboard().setText(self.texto_vista_previa.toPlainText())


def pantalla_mensajes_predefinidos(conn: sqlite3.Connection) -> PantallaMensajesPredefinidos:
    return PantallaMensajesPredefinidos(conn)
