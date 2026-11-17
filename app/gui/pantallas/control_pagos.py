"""Módulo extendido ME1 — "Control de pagos" (sección 3.35-3.37): control
mes a mes de todo lo que hay que abonar, sea del espacio o personal/
familiar — ver el docstring de `app.negocio.control_pagos` para el
modelo completo.

Pantalla compuesta con cinco solapas: "Carga y control" e "Historial"
(este archivo) más los tres catálogos livianos que necesita Afectación
("Inmuebles personales"/"Rodados"/"Personas", anidados de `catalogos.py`,
sin código propio). Solo aparece en el menú si `Configuracion.
ModulosExtendidos` está prendido — ver `gui_main.construir_secciones`."""
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.estilos import COLOR_AMARILLO, COLOR_GRIS, COLOR_ROJO, COLOR_TEXTO_CLARO, COLOR_VERDE, COLOR_VIOLETA
from app.gui.pantallas import catalogos
from app.gui.pantallas.novedades import _campo_fecha_opcional, _titulo_campo
from app.gui.pantallas.pagos import _SpinMonto
from app.gui.pantallas.reservas import _FECHA_SIN_DATO
from app.gui.widgets.foco import excluir_tabla_del_tab, instalar_enter_avanza_foco
from app.gui.widgets.items_tabla import item_centrado, item_numero
from app.gui.widgets.resumen_saldo import item_monto
from app.negocio.control_pagos import (
    ESTADOS_INSTANCIA,
    TIPOS_AFECTACION,
    actualizar_instancia,
    archivar_instancia,
    crear_concepto,
    dar_de_baja_concepto,
    duplicar_para_periodo_proximo,
    editar_concepto,
    eliminar_instancia_duplicada,
    generar_instancias_periodo,
    marcar_abonada,
    texto_afectacion,
)
from app.negocio.dias import fecha_actual, periodo_actual, sumar_meses
from app.negocio.listas_editables import opciones_lista
from app.pdf.estilos import clave_orden_unidad
from app.repositorio.registro import obtener_repositorio

_ANCHO_CAMPO = 240
_ANCHO_PANEL_IZQUIERDA = 280

# Pedido explícito de la clienta: la primer columna (el formulario de
# "Carga y control", NO el panel de filtros de "Historial" — mismo
# criterio que el resto de las constantes de acá, cada panel se mide
# por separado) se achica un 15%, y ese ancho liberado pasa a la tabla.
# Los campos/botones del formulario se escalan en la misma proporción
# para no desbordar el panel ya angosto.
_ANCHO_PANEL_CARGA_CONTROL = round(_ANCHO_PANEL_IZQUIERDA * 0.85)
_ANCHO_CAMPO_CARGA_CONTROL = round(_ANCHO_CAMPO * 0.85)

# "Que el primer elemento de la columna arranque en el pixel 85" —
# mismo mecanismo (y mismo valor medido) que Reservas regulares/
# aisladas y los paneles de Novedades (`_ALTO_TITULO_COLUMNAS_
# REGULARES`/`_ALTO_TITULO_COLUMNAS_NOVEDADES`): acá no hay una segunda
# columna con la que coordinar (la clienta aclaró que la idea de
# "tres columnas" no corría), así que es solo el margen de arriba de
# `form`.
_ALTO_TITULO_CARGA_CONTROL = 7

# Colores de fondo de fila según proximidad del vencimiento (pedido
# explícito de la clienta) — mismos valores hex que `app.gui.pantallas.
# mensajeria._COLOR_FONDO`, reusados vía las constantes de `estilos.py`.
_COLOR_FONDO_VENCIMIENTO = {
    "violeta": COLOR_VIOLETA, "rojo": COLOR_ROJO, "amarillo": COLOR_AMARILLO, "verde": COLOR_VERDE,
    "gris": COLOR_GRIS,
}
# Mismo criterio que `mensajeria._COLOR_TEXTO_CLARO`: amarillo (fondo
# claro) usa letra negra, el resto letra blanca.
_COLORES_CON_LETRA_NEGRA = {"amarillo"}

# Tipos de Afectación que necesitan un combo de detalle (el resto,
# "Espacio general"/"Familia", no apuntan a ningún registro puntual).
_TIPOS_CON_DETALLE = ("Edificio", "Unidad", "Inmueble personal", "Rodado", "Persona")


def _opciones_edificio(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdEdificio, Nombre FROM Edificio ORDER BY Nombre").fetchall()
    return [(f["IdEdificio"], f["Nombre"]) for f in filas]


def _opciones_unidad(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute(
        "SELECT u.IdUnidad, u.Departamento, e.Nombre AS Edificio FROM Unidad u "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio"
    ).fetchall()
    filas = sorted(filas, key=lambda f: (f["Edificio"], clave_orden_unidad(f["Departamento"])))
    return [(f["IdUnidad"], f"{f['Edificio']} - {f['Departamento']}") for f in filas]


def _opciones_inmueble_personal(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = obtener_repositorio(conn, "InmueblePersonal").listar()
    resultado = []
    for f in filas:
        localidad = obtener_repositorio(conn, "Localidad").obtener(f["IdLocalidad"]) if f["IdLocalidad"] else None
        texto = " ".join(p for p in (f["TipoInmueble"], f["Direccion"]) if p)
        if localidad:
            texto += f", {localidad['Localidad']}"
        resultado.append((f["IdInmueblePersonal"], texto))
    return resultado


def _opciones_rodado(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = obtener_repositorio(conn, "Rodado").listar()
    return [(f["IdRodado"], " ".join(p for p in (f["Marca"], f["Modelo"], f["Dominio"]) if p)) for f in filas]


def _opciones_persona_familia(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = obtener_repositorio(conn, "PersonaFamilia").listar()
    return [(f["IdPersonaFamilia"], f["Nombre"]) for f in filas]


_OPCIONES_POR_TIPO = {
    "Edificio": _opciones_edificio,
    "Unidad": _opciones_unidad,
    "Inmueble personal": _opciones_inmueble_personal,
    "Rodado": _opciones_rodado,
    "Persona": _opciones_persona_familia,
}

_CAMPO_ID_POR_TIPO = {
    "Edificio": "id_edificio",
    "Unidad": "id_unidad",
    "Inmueble personal": "id_inmueble_personal",
    "Rodado": "id_rodado",
    "Persona": "id_persona_familia",
}

_CAMPO_DB_POR_TIPO = {
    "Edificio": "IdEdificio",
    "Unidad": "IdUnidad",
    "Inmueble personal": "IdInmueblePersonal",
    "Rodado": "IdRodado",
    "Persona": "IdPersonaFamilia",
}


def _item_importe(valor: float | None) -> QTableWidgetItem:
    """Como `item_monto`, pero en blanco cuando todavía no se cargó
    ningún importe — "$ 0,00" confundiría "sin cargar" con "cargado en
    cero", dos cosas distintas acá."""
    return QTableWidgetItem("") if valor is None else item_monto(valor)


def _armar_combo_tipo_afectacion() -> QComboBox:
    combo = QComboBox()
    for tipo in TIPOS_AFECTACION:
        combo.addItem(tipo, tipo)
    return combo


def _actualizar_combo_detalle_afectacion(conn: sqlite3.Connection, combo_tipo: QComboBox, combo_detalle: QComboBox) -> None:
    """Repuebla `combo_detalle` según el Tipo elegido — "Espacio
    general"/"Familia" no apuntan a ningún registro puntual, así que
    queda vacío y deshabilitado."""
    tipo = combo_tipo.currentData()
    combo_detalle.blockSignals(True)
    combo_detalle.clear()
    if tipo in _TIPOS_CON_DETALLE:
        combo_detalle.setEnabled(True)
        for id_, etiqueta in _OPCIONES_POR_TIPO[tipo](conn):
            combo_detalle.addItem(etiqueta, id_)
    else:
        combo_detalle.setEnabled(False)
    combo_detalle.blockSignals(False)


def _kwargs_afectacion(combo_tipo: QComboBox, combo_detalle: QComboBox) -> dict:
    tipo = combo_tipo.currentData()
    kwargs = {"tipo_afectacion": tipo}
    if tipo in _TIPOS_CON_DETALLE:
        kwargs[_CAMPO_ID_POR_TIPO[tipo]] = combo_detalle.currentData()
    return kwargs


class _DialogoEditarInstancia(QDialog):
    """Editar vencimiento/monto de UNA instancia puntual — distinto de
    editar los datos del concepto en sí (ver `_DialogoEditarConcepto`).

    `incluir_estado` suma un combo de Estado (Pendiente/Abonado/
    Archivado) — pedido explícito de la clienta para el botón "Editar
    registro" de la solapa "Historial" ("ese botón me tendría que
    permitir editar vencimiento, importe y estado"), para poder
    reabrir algo que el cierre de mes archivó de más sin tener que
    pasar por "Marcar abonado"/"Archivar" por separado. El "Editar
    registro" de "Carga y control" no lo necesita (ahí ya están
    "Marcar abonado"/"Archivar registro" aparte), así que queda en
    `False` por default."""

    def __init__(self, conn: sqlite3.Connection, instancia: sqlite3.Row, parent=None, *, incluir_estado: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Editar vencimiento, monto y estado" if incluir_estado else "Editar vencimiento y monto")
        layout = QVBoxLayout(self)

        layout.addWidget(_titulo_campo("Vencimiento"))
        self.campo_vencimiento = _campo_fecha_opcional(conn)
        if instancia["Vencimiento"]:
            from PySide6.QtCore import QDate
            self.campo_vencimiento.setDate(QDate.fromString(instancia["Vencimiento"], "yyyy-MM-dd"))
        layout.addWidget(self.campo_vencimiento)

        layout.addWidget(_titulo_campo("Importe"))
        self.spin_importe = _SpinMonto()
        self.spin_importe.setRange(0, 100_000_000)
        self.spin_importe.setDecimals(2)
        self.spin_importe.setSpecialValueText("(sin cargar)")
        self.spin_importe.setValue(instancia["Importe"] or 0)
        layout.addWidget(self.spin_importe)

        self.combo_estado: QComboBox | None = None
        if incluir_estado:
            layout.addWidget(_titulo_campo("Estado"))
            self.combo_estado = QComboBox()
            for valor in ESTADOS_INSTANCIA:
                self.combo_estado.addItem(valor, valor)
            indice = self.combo_estado.findData(instancia["Estado"])
            if indice >= 0:
                self.combo_estado.setCurrentIndex(indice)
            layout.addWidget(self.combo_estado)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)
        campos_foco = [self.campo_vencimiento, self.spin_importe]
        if self.combo_estado is not None:
            campos_foco.append(self.combo_estado)
        self._foco = instalar_enter_avanza_foco(campos_foco, parent=self)

    def vencimiento(self) -> str | None:
        return (
            None if self.campo_vencimiento.date() == _FECHA_SIN_DATO
            else self.campo_vencimiento.date().toPython().isoformat()
        )

    def importe(self) -> float | None:
        return None if self.spin_importe.value() == 0 else self.spin_importe.value()

    def estado(self) -> str | None:
        return self.combo_estado.currentData() if self.combo_estado is not None else None


class _DialogoEditarConcepto(QDialog):
    """Editar los datos del concepto en sí (Nombre/Categoría/Afectación/
    Medio de pago sugerido) — pedido explícito de la clienta, para
    cuando algo del concepto cambia (ej. se vende una unidad, o se
    corrige un error de carga)."""

    def __init__(self, conn: sqlite3.Connection, concepto: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Editar concepto")
        layout = QVBoxLayout(self)

        layout.addWidget(_titulo_campo("Nombre"))
        self.campo_nombre = QLineEdit(concepto["Nombre"])
        layout.addWidget(self.campo_nombre)

        layout.addWidget(_titulo_campo("Categoría"))
        self.combo_categoria = QComboBox()
        self.combo_categoria.setEditable(True)
        for valor, etiqueta in opciones_lista("CategoriaControlPagos")(conn):
            self.combo_categoria.addItem(etiqueta, valor)
        if concepto["Categoria"]:
            self.combo_categoria.setCurrentText(concepto["Categoria"])
        layout.addWidget(self.combo_categoria)

        layout.addWidget(_titulo_campo("Afectación"))
        self.combo_tipo_afectacion = _armar_combo_tipo_afectacion()
        indice_tipo = self.combo_tipo_afectacion.findData(concepto["TipoAfectacion"])
        if indice_tipo >= 0:
            self.combo_tipo_afectacion.setCurrentIndex(indice_tipo)
        layout.addWidget(self.combo_tipo_afectacion)
        self.combo_detalle_afectacion = QComboBox()
        layout.addWidget(self.combo_detalle_afectacion)
        self.combo_tipo_afectacion.currentIndexChanged.connect(self._actualizar_detalle)
        self._actualizar_detalle()
        tipo = concepto["TipoAfectacion"]
        if tipo in _TIPOS_CON_DETALLE:
            id_actual = concepto[_CAMPO_DB_POR_TIPO[tipo]]
            indice_detalle = self.combo_detalle_afectacion.findData(id_actual)
            if indice_detalle >= 0:
                self.combo_detalle_afectacion.setCurrentIndex(indice_detalle)

        layout.addWidget(_titulo_campo("Medio de pago sugerido"))
        self.combo_medio_pago = QComboBox()
        self.combo_medio_pago.setEditable(True)
        for valor, etiqueta in opciones_lista("MedioPagoControlPagos")(conn):
            self.combo_medio_pago.addItem(etiqueta, valor)
        if concepto["MedioPagoSugerido"]:
            self.combo_medio_pago.setCurrentText(concepto["MedioPagoSugerido"])
        layout.addWidget(self.combo_medio_pago)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _actualizar_detalle(self) -> None:
        _actualizar_combo_detalle_afectacion(self.conn, self.combo_tipo_afectacion, self.combo_detalle_afectacion)

    def valores(self) -> dict:
        valores = {
            "Nombre": self.campo_nombre.text().strip(),
            "Categoria": self.combo_categoria.currentText().strip() or None,
            "MedioPagoSugerido": self.combo_medio_pago.currentText().strip() or None,
            "TipoAfectacion": self.combo_tipo_afectacion.currentData(),
        }
        for campo_db in _CAMPO_DB_POR_TIPO.values():
            valores[campo_db] = None
        tipo = self.combo_tipo_afectacion.currentData()
        if tipo in _TIPOS_CON_DETALLE:
            valores[_CAMPO_DB_POR_TIPO[tipo]] = self.combo_detalle_afectacion.currentData()
        return valores


class _PanelCargaControl(QWidget):
    _COL_NOMBRE, _COL_CATEGORIA, _COL_AFECTACION, _COL_MEDIO_PAGO = 0, 1, 2, 3
    _COL_PERIODO, _COL_VENCIMIENTO, _COL_IMPORTE, _COL_ESTADO = 4, 5, 6, 7

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setObjectName("panelSolapa")
        self._registros: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        generar_instancias_periodo(self.conn, periodo_actual(self.conn))
        self.actualizar()
        self.campo_nombre.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)

        panel_form = QWidget()
        panel_form.setObjectName("panelSolapa")
        panel_form.setMinimumWidth(_ANCHO_PANEL_CARGA_CONTROL)
        panel_form.setMaximumWidth(_ANCHO_PANEL_CARGA_CONTROL)
        scroll_form = QScrollArea()
        scroll_form.setWidgetResizable(True)
        scroll_form.setWidget(panel_form)
        scroll_form.setMinimumWidth(_ANCHO_PANEL_CARGA_CONTROL + 20)
        scroll_form.setMaximumWidth(_ANCHO_PANEL_CARGA_CONTROL + 20)
        form = QVBoxLayout(panel_form)
        # "Que el primer elemento arranque en el pixel 85" — ver
        # `_ALTO_TITULO_CARGA_CONTROL` más arriba.
        form.setContentsMargins(9, _ALTO_TITULO_CARGA_CONTROL, 9, 0)

        form.addWidget(_titulo_campo("Período actual"))
        self.etiqueta_periodo = QLabel(periodo_actual(self.conn))
        form.addWidget(self.etiqueta_periodo)

        form.addWidget(_titulo_campo("Nombre"))
        self.campo_nombre = QLineEdit()
        self.campo_nombre.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        form.addWidget(self.campo_nombre)

        form.addWidget(_titulo_campo("Categoría"))
        self.combo_categoria = QComboBox()
        self.combo_categoria.setEditable(True)
        self.combo_categoria.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        for valor, etiqueta in opciones_lista("CategoriaControlPagos")(self.conn):
            self.combo_categoria.addItem(etiqueta, valor)
        self.combo_categoria.setCurrentIndex(-1)
        form.addWidget(self.combo_categoria)

        form.addWidget(_titulo_campo("Afectación"))
        self.combo_tipo_afectacion = _armar_combo_tipo_afectacion()
        self.combo_tipo_afectacion.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        form.addWidget(self.combo_tipo_afectacion)
        self.combo_detalle_afectacion = QComboBox()
        self.combo_detalle_afectacion.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        form.addWidget(self.combo_detalle_afectacion)
        self.combo_tipo_afectacion.currentIndexChanged.connect(self._actualizar_detalle_afectacion)
        self._actualizar_detalle_afectacion()

        form.addWidget(_titulo_campo("Medio de pago"))
        self.combo_medio_pago = QComboBox()
        self.combo_medio_pago.setEditable(True)
        self.combo_medio_pago.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        for valor, etiqueta in opciones_lista("MedioPagoControlPagos")(self.conn):
            self.combo_medio_pago.addItem(etiqueta, valor)
        self.combo_medio_pago.setCurrentIndex(-1)
        form.addWidget(self.combo_medio_pago)

        form.addWidget(_titulo_campo("Vencimiento (opcional)"))
        self.campo_vencimiento = _campo_fecha_opcional(self.conn)
        self.campo_vencimiento.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        form.addWidget(self.campo_vencimiento)

        form.addWidget(_titulo_campo("Importe (opcional)"))
        self.spin_importe = _SpinMonto()
        self.spin_importe.setRange(0, 100_000_000)
        self.spin_importe.setDecimals(2)
        self.spin_importe.setSpecialValueText("(sin cargar)")
        self.spin_importe.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        form.addWidget(self.spin_importe)

        # Pedido explícito de la clienta: el botón "Crear concepto" sube
        # a ocupar el lugar que dejaron los tres campos libres (sacados
        # de esta pantalla — quedan en la BD pero sin uso por ahora) y
        # la línea divisoria que había antes de "Editar concepto
        # seleccionado" se saca.
        self.boton_crear = QPushButton("Crear concepto")
        self.boton_crear.setObjectName("botonPrimario")
        self.boton_crear.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_crear.clicked.connect(self._crear)
        form.addWidget(self.boton_crear)

        self.boton_editar_concepto = QPushButton("Editar concepto seleccionado")
        self.boton_editar_concepto.setObjectName("botonSecundario")
        self.boton_editar_concepto.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_editar_concepto.clicked.connect(self._editar_concepto_seleccionado)
        form.addWidget(self.boton_editar_concepto)

        # Pedido explícito de la clienta: baja DEFINITIVA de un concepto
        # (distinta de "Archivar", que solo cierra el mes en curso).
        self.boton_dar_de_baja = QPushButton("Dar de baja concepto seleccionado")
        self.boton_dar_de_baja.setObjectName("botonSecundario")
        self.boton_dar_de_baja.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_dar_de_baja.clicked.connect(self._dar_de_baja_seleccionado)
        form.addWidget(self.boton_dar_de_baja)

        # Pedido explícito de la clienta: "por si ya tengo la información
        # para adelantar y anotar un importe o vencimiento" de un
        # concepto del período en curso — duplica (en blanco, solo con
        # Medio de pago) la instancia elegida al período próximo. Solo
        # habilitado sobre una fila del período ACTUAL (ver
        # `_actualizar_botones_seleccion`) — "solo se pueden duplicar
        # registros para el período próximo nada más".
        self.boton_duplicar_periodo_proximo = QPushButton("Duplicar para período próximo")
        self.boton_duplicar_periodo_proximo.setObjectName("botonSecundario")
        self.boton_duplicar_periodo_proximo.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_duplicar_periodo_proximo.clicked.connect(self._duplicar_para_periodo_proximo)
        form.addWidget(self.boton_duplicar_periodo_proximo)

        self.boton_eliminar_duplicado = QPushButton("Eliminar registro duplicado")
        self.boton_eliminar_duplicado.setObjectName("botonSecundario")
        self.boton_eliminar_duplicado.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_eliminar_duplicado.clicked.connect(self._eliminar_registro_duplicado)
        form.addWidget(self.boton_eliminar_duplicado)

        linea = QFrame()
        linea.setFrameShape(QFrame.Shape.HLine)
        linea.setFrameShadow(QFrame.Shadow.Sunken)
        form.addWidget(linea)

        # Pedido explícito de la clienta: los tres botones que antes
        # vivían al final de cada fila de la tabla pasan a vivir acá,
        # al final de esta columna — se habilitan con una fila
        # seleccionada (ver `_actualizar_botones_seleccion`).
        self.boton_editar_registro = QPushButton("Editar registro")
        self.boton_editar_registro.setObjectName("botonSecundario")
        self.boton_editar_registro.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_editar_registro.clicked.connect(self._editar_registro_seleccionado)
        form.addWidget(self.boton_editar_registro)

        self.boton_marcar_abonado = QPushButton("Marcar abonado")
        self.boton_marcar_abonado.setObjectName("botonSecundario")
        self.boton_marcar_abonado.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_marcar_abonado.clicked.connect(self._marcar_abonada_seleccionada)
        form.addWidget(self.boton_marcar_abonado)

        self.boton_archivar_registro = QPushButton("Archivar registro")
        self.boton_archivar_registro.setObjectName("botonSecundario")
        self.boton_archivar_registro.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_archivar_registro.clicked.connect(self._archivar_seleccionada)
        form.addWidget(self.boton_archivar_registro)

        form.addStretch(1)
        layout_externo.addWidget(scroll_form)

        self.tabla = QTableWidget()
        excluir_tabla_del_tab(self.tabla)
        self.tabla.setColumnCount(8)
        self.tabla.setHorizontalHeaderLabels([
            "Nombre", "Categoría", "Afectación", "Medio de pago", "Período", "Vencimiento", "Importe", "Estado",
        ])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = self.tabla.horizontalHeader()
        for columna in (self._COL_NOMBRE, self._COL_CATEGORIA, self._COL_AFECTACION, self._COL_MEDIO_PAGO):
            header.setSectionResizeMode(columna, QHeaderView.ResizeMode.Stretch)
        for columna in (self._COL_PERIODO, self._COL_VENCIMIENTO, self._COL_IMPORTE, self._COL_ESTADO):
            header.setSectionResizeMode(columna, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones_seleccion)
        layout_externo.addWidget(self.tabla, stretch=1)

        self._foco = instalar_enter_avanza_foco(
            [
                self.campo_nombre, self.combo_categoria, self.combo_tipo_afectacion, self.combo_detalle_afectacion,
                self.combo_medio_pago, self.campo_vencimiento, self.spin_importe, self.boton_crear,
            ],
            parent=self,
        )
        self._actualizar_botones_seleccion()

    def _actualizar_detalle_afectacion(self) -> None:
        _actualizar_combo_detalle_afectacion(self.conn, self.combo_tipo_afectacion, self.combo_detalle_afectacion)

    def _resetear_formulario(self) -> None:
        self.campo_nombre.clear()
        self.combo_categoria.setCurrentIndex(-1)
        self.combo_tipo_afectacion.setCurrentIndex(0)
        self.combo_medio_pago.setCurrentIndex(-1)
        self.campo_vencimiento.setDate(_FECHA_SIN_DATO)
        self.spin_importe.setValue(0)

    def _crear(self) -> None:
        nombre = self.campo_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Crear concepto", "El nombre es obligatorio.")
            self.campo_nombre.setFocus()
            return
        kwargs = _kwargs_afectacion(self.combo_tipo_afectacion, self.combo_detalle_afectacion)
        id_concepto = crear_concepto(
            self.conn, nombre=nombre, categoria=self.combo_categoria.currentText().strip() or None,
            medio_pago_sugerido=self.combo_medio_pago.currentText().strip() or None, **kwargs,
        )
        generar_instancias_periodo(self.conn, periodo_actual(self.conn))
        instancias = obtener_repositorio(self.conn, "InstanciaControlPago").listar(
            IdConcepto=id_concepto, Periodo=periodo_actual(self.conn),
        )
        vencimiento = (
            None if self.campo_vencimiento.date() == _FECHA_SIN_DATO
            else self.campo_vencimiento.date().toPython().isoformat()
        )
        importe = None if self.spin_importe.value() == 0 else self.spin_importe.value()
        if instancias and (vencimiento is not None or importe is not None):
            actualizar_instancia(self.conn, instancias[0]["IdInstancia"], vencimiento=vencimiento, importe=importe)
        self._resetear_formulario()
        self.actualizar()
        self.campo_nombre.setFocus()
        QMessageBox.information(self, "Crear concepto", "Concepto creado con éxito.")

    def _fila_seleccionada_instancia(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._registros[filas[0].row()]

    def _fila_seleccionada_concepto(self) -> sqlite3.Row | None:
        instancia = self._fila_seleccionada_instancia()
        if instancia is None:
            return None
        return obtener_repositorio(self.conn, "ConceptoControlPago").obtener(instancia["IdConcepto"])

    def _actualizar_botones_seleccion(self) -> None:
        """Pedido explícito de la clienta: los botones de acción sobre
        una fila (todos menos "Crear concepto") se habilitan solo
        cuando hay un registro seleccionado — algunos además con una
        condición propia (estado/período) que ya tenían como guarda
        manual antes de este rediseño."""
        instancia = self._fila_seleccionada_instancia()
        hay_seleccion = instancia is not None
        periodo = periodo_actual(self.conn)
        periodo_proximo = sumar_meses(periodo, 1)
        self.boton_editar_concepto.setEnabled(hay_seleccion)
        self.boton_dar_de_baja.setEnabled(hay_seleccion)
        self.boton_duplicar_periodo_proximo.setEnabled(hay_seleccion and instancia["Periodo"] == periodo)
        self.boton_eliminar_duplicado.setEnabled(hay_seleccion and instancia["Periodo"] == periodo_proximo)
        self.boton_editar_registro.setEnabled(hay_seleccion)
        self.boton_marcar_abonado.setEnabled(hay_seleccion and instancia["Estado"] == "Pendiente")
        self.boton_archivar_registro.setEnabled(
            hay_seleccion and instancia["Estado"] == "Pendiente"
            and not instancia["Vencimiento"] and instancia["Importe"] is None
        )

    def _editar_concepto_seleccionado(self) -> None:
        concepto = self._fila_seleccionada_concepto()
        if concepto is None:
            return
        dialogo = _DialogoEditarConcepto(self.conn, concepto, parent=self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            editar_concepto(self.conn, concepto["IdConcepto"], **dialogo.valores())
            self.actualizar()
            QMessageBox.information(self, "Editar concepto", "Concepto actualizado con éxito.")

    def _clave_orden_instancia(self, fila: tuple) -> tuple:
        """Orden pedido explícitamente por la clienta: arriba las filas
        Pendientes sin vencimiento o sin importe cargados (ordenadas por
        Nombre y Afectación); luego las Pendientes con ambos datos
        cargados (por Período más próximo, Vencimiento, Nombre,
        Afectación); al final, en gris, las Abonadas/Archivadas —
        mismo criterio que Centro de mensajería (lo ya resuelto se hunde
        al fondo)."""
        instancia, concepto, afectacion = fila
        nombre = concepto["Nombre"] if concepto else ""
        if instancia["Estado"] in ("Abonado", "Archivado"):
            return (2, "", "", nombre, afectacion)
        if not instancia["Vencimiento"] or instancia["Importe"] is None:
            return (0, "", "", nombre, afectacion)
        return (1, instancia["Periodo"], instancia["Vencimiento"], nombre, afectacion)

    def _color_fila(self, instancia: sqlite3.Row, hoy: date) -> str | None:
        """Color de fondo pedido explícitamente por la clienta: gris
        para lo Abonado/Archivado (sin importar el vencimiento); si
        está Pendiente, según cuánto falta para el vencimiento (o
        blanco si no tiene vencimiento cargado)."""
        if instancia["Estado"] in ("Abonado", "Archivado"):
            return "gris"
        vencimiento = instancia["Vencimiento"]
        if not vencimiento:
            return None
        dias = (date.fromisoformat(vencimiento) - hoy).days
        if dias < 0:
            return "violeta"
        if dias == 0:
            return "rojo"
        if dias == 1:
            return "amarillo"
        return "verde"

    def actualizar(self) -> None:
        self.etiqueta_periodo.setText(periodo_actual(self.conn))
        periodo = periodo_actual(self.conn)
        periodo_proximo = sumar_meses(periodo, 1)
        repo_instancia = obtener_repositorio(self.conn, "InstanciaControlPago")
        instancias = repo_instancia.listar(Periodo=periodo) + repo_instancia.listar(Periodo=periodo_proximo)
        conceptos = {c["IdConcepto"]: c for c in obtener_repositorio(self.conn, "ConceptoControlPago").listar()}
        filas = [
            (i, conceptos.get(i["IdConcepto"]), texto_afectacion(self.conn, conceptos[i["IdConcepto"]]) if i["IdConcepto"] in conceptos else "?")
            for i in instancias
        ]
        filas.sort(key=self._clave_orden_instancia)
        self._registros = [f[0] for f in filas]

        hoy = fecha_actual(self.conn)
        self.tabla.setRowCount(len(filas))
        for fila_idx, (instancia, concepto, afectacion) in enumerate(filas):
            self.tabla.setItem(fila_idx, self._COL_NOMBRE, QTableWidgetItem(concepto["Nombre"] if concepto else "?"))
            self.tabla.setItem(
                fila_idx, self._COL_CATEGORIA, QTableWidgetItem((concepto["Categoria"] if concepto else "") or ""),
            )
            self.tabla.setItem(fila_idx, self._COL_AFECTACION, QTableWidgetItem(afectacion))
            self.tabla.setItem(
                fila_idx, self._COL_MEDIO_PAGO, QTableWidgetItem(instancia["MedioPago"] or ""),
            )
            self.tabla.setItem(fila_idx, self._COL_PERIODO, item_centrado(instancia["Periodo"]))
            self.tabla.setItem(
                fila_idx, self._COL_VENCIMIENTO, item_centrado(instancia["Vencimiento"] or ""),
            )
            self.tabla.setItem(fila_idx, self._COL_IMPORTE, _item_importe(instancia["Importe"]))
            self.tabla.setItem(fila_idx, self._COL_ESTADO, item_centrado(instancia["Estado"]))

            color = self._color_fila(instancia, hoy)
            if color is not None:
                fondo = QColor(_COLOR_FONDO_VENCIMIENTO[color])
                letra = QColor("#000000" if color in _COLORES_CON_LETRA_NEGRA else COLOR_TEXTO_CLARO)
                for columna in range(self.tabla.columnCount()):
                    celda = self.tabla.item(fila_idx, columna)
                    celda.setBackground(fondo)
                    celda.setForeground(letra)
        self._actualizar_botones_seleccion()

    def _editar_registro_seleccionado(self) -> None:
        instancia = self._fila_seleccionada_instancia()
        if instancia is None:
            return
        dialogo = _DialogoEditarInstancia(self.conn, instancia, parent=self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            actualizar_instancia(
                self.conn, instancia["IdInstancia"], vencimiento=dialogo.vencimiento(), importe=dialogo.importe(),
            )
            self.actualizar()
            QMessageBox.information(self, "Editar registro", "Registro actualizado con éxito.")

    def _marcar_abonada_seleccionada(self) -> None:
        instancia = self._fila_seleccionada_instancia()
        if instancia is None:
            return
        marcar_abonada(self.conn, instancia["IdInstancia"])
        self.actualizar()
        QMessageBox.information(self, "Marcar abonado", "Registro marcado como abonado con éxito.")

    def _archivar_seleccionada(self) -> None:
        instancia = self._fila_seleccionada_instancia()
        if instancia is None:
            return
        try:
            archivar_instancia(self.conn, instancia["IdInstancia"])
        except ValueError as error:
            QMessageBox.warning(self, "Archivar registro", str(error))
            return
        self.actualizar()
        QMessageBox.information(self, "Archivar registro", "Registro archivado con éxito.")

    def _duplicar_para_periodo_proximo(self) -> None:
        instancia = self._fila_seleccionada_instancia()
        if instancia is None:
            return
        try:
            duplicar_para_periodo_proximo(self.conn, instancia["IdInstancia"])
        except ValueError as error:
            QMessageBox.warning(self, "Duplicar para período próximo", str(error))
            return
        self.actualizar()
        QMessageBox.information(
            self, "Duplicar para período próximo", "Registro duplicado con éxito para el período próximo.",
        )

    def _eliminar_registro_duplicado(self) -> None:
        instancia = self._fila_seleccionada_instancia()
        if instancia is None:
            return
        respuesta = QMessageBox.question(
            self, "Eliminar registro duplicado", "¿Eliminar este registro duplicado del período próximo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        eliminar_instancia_duplicada(self.conn, instancia["IdInstancia"])
        self.actualizar()
        QMessageBox.information(self, "Eliminar registro duplicado", "Registro duplicado eliminado con éxito.")

    def _dar_de_baja_seleccionado(self) -> None:
        concepto = self._fila_seleccionada_concepto()
        if concepto is None:
            return
        respuesta = QMessageBox.question(
            self, "Dar de baja concepto",
            f"¿Dar de baja «{concepto['Nombre']}» para siempre? No se va a volver a generar en los próximos "
            "períodos. El historial ya generado no se toca.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        dar_de_baja_concepto(self.conn, concepto["IdConcepto"])
        self.actualizar()
        QMessageBox.information(self, "Dar de baja concepto", "Concepto dado de baja con éxito.")

    def reiniciar(self) -> None:
        """F5: "reinicia la solapa... como recién se entrara en ella" —
        a diferencia de `showEvent` (que no toca un formulario a medio
        completar), acá sí se resetea todo, formulario incluido (ver
        CLAUDE.md, "F5... reinicia desde cero, distinto de showEvent")."""
        self._resetear_formulario()
        self.tabla.clearSelection()
        self.actualizar()
        self.campo_nombre.setFocus()


class _PanelHistorialControlPagos(QWidget):
    _TODAS = object()

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setObjectName("panelSolapa")
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.actualizar()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        panel_filtros = QWidget()
        panel_filtros.setObjectName("panelSolapa")
        panel_filtros.setMinimumWidth(_ANCHO_PANEL_IZQUIERDA)
        panel_filtros.setMaximumWidth(_ANCHO_PANEL_IZQUIERDA)
        filtros = QVBoxLayout(panel_filtros)

        self.combo_categoria = QComboBox()
        self.combo_concepto = QComboBox()
        self.combo_afectacion = QComboBox()
        self.combo_medio_pago = QComboBox()
        for etiqueta, combo in (
            ("Categoría", self.combo_categoria), ("Concepto", self.combo_concepto),
            ("Afectación", self.combo_afectacion), ("Medio de pago", self.combo_medio_pago),
        ):
            filtros.addWidget(_titulo_campo(etiqueta))
            combo.setFixedWidth(_ANCHO_CAMPO)
            combo.currentIndexChanged.connect(self.actualizar)
            filtros.addWidget(combo)

        # Pedido explícito de la clienta: desde acá se puede reabrir un
        # registro que el cierre de mes archivó de más ("Al avanzar de
        # mes... lo que no esté marcado como abonado se archiva y luego
        # desde la solapa 'Historial' se puede marcar como abonado") —
        # el diálogo edita vencimiento, importe Y estado juntos.
        self.boton_editar_registro = QPushButton("Editar registro")
        self.boton_editar_registro.setObjectName("botonSecundario")
        self.boton_editar_registro.setFixedWidth(_ANCHO_CAMPO)
        self.boton_editar_registro.setEnabled(False)
        self.boton_editar_registro.clicked.connect(self._editar_registro)
        filtros.addWidget(self.boton_editar_registro)

        filtros.addStretch(1)
        layout_externo.addWidget(panel_filtros)

        self.tabla = QTableWidget()
        excluir_tabla_del_tab(self.tabla)
        self.tabla.setColumnCount(8)
        self.tabla.setHorizontalHeaderLabels([
            "Período", "Nombre", "Categoría", "Afectación", "Medio de pago", "Vencimiento", "Importe", "Estado",
        ])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = self.tabla.horizontalHeader()
        for columna in (1, 2, 3, 4):
            header.setSectionResizeMode(columna, QHeaderView.ResizeMode.Stretch)
        self.tabla.itemSelectionChanged.connect(self._actualizar_boton_editar_registro)
        layout_externo.addWidget(self.tabla, stretch=1)
        self._filas: list[tuple] = []

    def _repoblar_filtros(self) -> None:
        conceptos = obtener_repositorio(self.conn, "ConceptoControlPago").listar()
        categorias = sorted({c["Categoria"] for c in conceptos if c["Categoria"]})
        nombres = sorted({c["Nombre"] for c in conceptos})
        afectaciones = sorted({texto_afectacion(self.conn, c) for c in conceptos})
        medios = sorted({
            i["MedioPago"] for i in obtener_repositorio(self.conn, "InstanciaControlPago").listar() if i["MedioPago"]
        })
        for combo, valores in (
            (self.combo_categoria, categorias), (self.combo_concepto, nombres),
            (self.combo_afectacion, afectaciones), (self.combo_medio_pago, medios),
        ):
            actual = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Todas" if combo is self.combo_categoria else "Todos", self._TODAS)
            for valor in valores:
                combo.addItem(valor, valor)
            indice = combo.findData(actual) if actual is not None else 0
            combo.setCurrentIndex(indice if indice >= 0 else 0)
            combo.blockSignals(False)

    def actualizar(self) -> None:
        self._repoblar_filtros()
        conceptos = {c["IdConcepto"]: c for c in obtener_repositorio(self.conn, "ConceptoControlPago").listar()}
        instancias = obtener_repositorio(self.conn, "InstanciaControlPago").listar()

        filtro_categoria = self.combo_categoria.currentData()
        filtro_concepto = self.combo_concepto.currentData()
        filtro_afectacion = self.combo_afectacion.currentData()
        filtro_medio = self.combo_medio_pago.currentData()

        filas = []
        for i in instancias:
            concepto = conceptos.get(i["IdConcepto"])
            if concepto is None:
                continue
            if filtro_categoria is not self._TODAS and concepto["Categoria"] != filtro_categoria:
                continue
            if filtro_concepto is not self._TODAS and concepto["Nombre"] != filtro_concepto:
                continue
            afectacion = texto_afectacion(self.conn, concepto)
            if filtro_afectacion is not self._TODAS and afectacion != filtro_afectacion:
                continue
            if filtro_medio is not self._TODAS and i["MedioPago"] != filtro_medio:
                continue
            filas.append((i, concepto, afectacion))
        filas.sort(key=lambda t: (t[0]["Periodo"], t[1]["Nombre"]), reverse=True)
        self._filas = filas

        self.tabla.setRowCount(len(filas))
        for fila_idx, (instancia, concepto, afectacion) in enumerate(filas):
            self.tabla.setItem(fila_idx, 0, item_numero(instancia["Periodo"]))
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(concepto["Nombre"]))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(concepto["Categoria"] or ""))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(afectacion))
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(instancia["MedioPago"] or ""))
            self.tabla.setItem(fila_idx, 5, item_centrado(instancia["Vencimiento"] or ""))
            self.tabla.setItem(fila_idx, 6, _item_importe(instancia["Importe"]))
            self.tabla.setItem(fila_idx, 7, item_centrado(instancia["Estado"]))
        self._actualizar_boton_editar_registro()

    def _fila_seleccionada_instancia(self) -> sqlite3.Row | None:
        filas_sel = self.tabla.selectionModel().selectedRows()
        if not filas_sel:
            return None
        return self._filas[filas_sel[0].row()][0]

    def _actualizar_boton_editar_registro(self) -> None:
        self.boton_editar_registro.setEnabled(self._fila_seleccionada_instancia() is not None)

    def _editar_registro(self) -> None:
        instancia = self._fila_seleccionada_instancia()
        if instancia is None:
            return
        dialogo = _DialogoEditarInstancia(self.conn, instancia, parent=self, incluir_estado=True)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            actualizar_instancia(
                self.conn, instancia["IdInstancia"], vencimiento=dialogo.vencimiento(), importe=dialogo.importe(),
                estado=dialogo.estado(),
            )
            self.actualizar()
            QMessageBox.information(self, "Editar registro", "Registro actualizado con éxito.")


class PantallaControlPagos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Control de pagos".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_carga_control = _PanelCargaControl(conn)
        self.panel_historial = _PanelHistorialControlPagos(conn)
        self.panel_inmuebles_personales = catalogos.pantalla_inmuebles_personales(conn, anidado=True)
        self.panel_rodados = catalogos.pantalla_rodados(conn, anidado=True)
        self.panel_personas = catalogos.pantalla_personas_familia(conn, anidado=True)
        self.pestanas.addTab(self.panel_carga_control, "Carga y control")
        self.pestanas.addTab(self.panel_historial, "Historial")
        self.pestanas.addTab(self.panel_inmuebles_personales, "Inmuebles personales")
        self.pestanas.addTab(self.panel_rodados, "Rodados")
        self.pestanas.addTab(self.panel_personas, "Personas")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
