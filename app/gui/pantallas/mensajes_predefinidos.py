"""Mensajes predefinidos (FA8, sección 5.5): biblioteca editable de
mensajes ad hoc (a diferencia de las 5 situaciones automáticas del Centro
de mensajería, sección 5.3, que también viven en MensajePredefinido pero
bajo la categoría fija "Situaciones centro de mensajería" — ver
app.negocio.mensajes._DESCRIPCION_SITUACION). Formato estándar de
catálogo (solapa "Listado", Buscar a la izquierda) con todo lo propio de
esta pantalla agrupado ARRIBA de Nuevo/Editar/Eliminar
(`panel_extra_superior_izquierda`, pedido de la clienta al revisar esta
pantalla), de arriba abajo: el combo "Categoría" (filtro que solo afecta
la visualización, mismo criterio que el resto del sistema), "Dirigido a"
(selector de profesional para la vista previa, ver más abajo) y el botón
"Copiar mensaje" (`botonPrimario` — es la acción más importante de esta
pantalla, por eso "Nuevo" pasa a `botonSecundario` acá vía
`nuevo_secundario=True`). Debajo de toda la pantalla queda la vista
previa (de solo lectura) que sustituye {edificio}/{unidad}/{consultorio}
por el vínculo elegido en el mensaje y {apodo} por el profesional
elegido en "Dirigido a" — "Copiar mensaje" la manda al portapapeles.

Categoría es un catálogo abierto (mismo criterio que Responsable.Rol):
sugiere los valores de Listas editables (TipoLista="CategoriaMensaje")
pero admite tipear uno nuevo ahí mismo sin tener que darlo de alta antes
en ese catálogo.

Localidad/Edificio/Unidad/Consultorio son cuatro campos independientes
(no encadenados en cascada): si los cuatro quedan sin seleccionar, el
mensaje se entiende general (pedido de la clienta) — por eso acá, a
diferencia de `catalogos.pantalla_unidades`/`pantalla_consultorios`
(donde Edificio/Unidad son obligatorios), los combos de Edificio/Unidad/
Consultorio necesitan su propia versión con una opción en blanco al
principio (`_opciones_edificio_o_ninguno` y análogas) — las de
`catalogos.py` no la tienen porque ahí esos campos son obligatorios."""
from __future__ import annotations

import sqlite3

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from app.gui.crud_generico import Campo, PantallaCRUD, campos_libres
from app.gui.pantallas.catalogos import _opciones_consultorio, _opciones_edificio, _opciones_localidad, _opciones_unidad
from app.gui.pantallas.reservas import _opciones_profesional
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.listas_editables import opciones_lista
from app.negocio.mensajes import sustituir_variables
from app.repositorio.registro import obtener_repositorio

_TODAS = "__todas__"


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _opciones_edificio_o_ninguno(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "Sin edificio")] + _opciones_edificio(conn)


def _opciones_unidad_o_ninguna(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "Sin unidad")] + _opciones_unidad(conn)


def _opciones_consultorio_o_ninguno(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "Sin consultorio")] + _opciones_consultorio(conn)


def _campos_mensaje_predefinido(conn: sqlite3.Connection) -> list[Campo]:
    return [
        Campo("Categoria", "Categoría", tipo="combo", opciones=opciones_lista("CategoriaMensaje"), combo_editable=True),
        Campo("Descripcion", "Descripción"),
        Campo("IdLocalidad", "Localidad", tipo="combo", opciones=_opciones_localidad),
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=_opciones_edificio_o_ninguno),
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad_o_ninguna),
        Campo("IdConsultorio", "Consultorio", tipo="combo", opciones=_opciones_consultorio_o_ninguno),
        Campo("Mensaje", "Mensaje", tipo="texto_largo"),
        Campo("Activo", "Activo", tipo="booleano"),
        *campos_libres(conn),
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

        panel_superior = QWidget()
        layout_superior = QVBoxLayout(panel_superior)
        layout_superior.setContentsMargins(0, 0, 0, 0)

        layout_superior.addWidget(_titulo_campo("Categoría"))
        self.combo_filtro = QComboBox()
        self.combo_filtro.currentIndexChanged.connect(self._aplicar_filtro)
        layout_superior.addWidget(self.combo_filtro)

        layout_superior.addWidget(_linea_divisoria())
        layout_superior.addWidget(_titulo_campo("Dirigido a"))
        self.combo_dirigido_a = QComboBox()
        self.combo_dirigido_a.addItem("Nadie en particular", None)
        for id_profesional, etiqueta in _opciones_profesional(self.conn):
            self.combo_dirigido_a.addItem(etiqueta, id_profesional)
        habilitar_busqueda_profesional(self.combo_dirigido_a)
        self.combo_dirigido_a.currentIndexChanged.connect(self._actualizar_vista_previa)
        layout_superior.addWidget(self.combo_dirigido_a)

        boton_copiar = QPushButton("Copiar mensaje")
        boton_copiar.setObjectName("botonPrimario")
        boton_copiar.clicked.connect(self._copiar_mensaje)
        layout_superior.addWidget(boton_copiar)

        self.crud = PantallaCRUD(
            self.conn, "MensajePredefinido", "Mensajes predefinidos", _campos_mensaje_predefinido(self.conn),
            panel_extra_superior_izquierda=panel_superior,
            nuevo_secundario=True,
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

        layout.addWidget(QLabel(
            "Vista previa (sustituye {edificio}/{unidad}/{consultorio} por el vínculo elegido en el mensaje, "
            "y {apodo} por el profesional elegido en \"Dirigido a\")"
        ))
        self.texto_vista_previa = QPlainTextEdit()
        self.texto_vista_previa.setReadOnly(True)
        self.texto_vista_previa.setFixedHeight(100)
        layout.addWidget(self.texto_vista_previa)

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
        variables["apodo"] = self._apodo_dirigido_a()
        self.texto_vista_previa.setPlainText(sustituir_variables(mensaje["Mensaje"] or "", variables))

    def _apodo_dirigido_a(self) -> str:
        id_profesional = self.combo_dirigido_a.currentData()
        if id_profesional is None:
            return ""
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(id_profesional)
        return (profesional["Apodo"] or "") if profesional else ""

    def _copiar_mensaje(self) -> None:
        QGuiApplication.clipboard().setText(self.texto_vista_previa.toPlainText())


def pantalla_mensajes_predefinidos(conn: sqlite3.Connection) -> PantallaMensajesPredefinidos:
    return PantallaMensajesPredefinidos(conn)
