"""Balance del negocio (reordenamiento de formularios, Excel de la
clienta): formulario nuevo con tres solapas — "Gastos" (el catálogo
Gastos operativos, antes pantalla propia del menú, anidado como el
resto de los catálogos que se van sumando a un formulario compuesto) e
"Ingresos"/"Resultado", dos solapas de informe 100% en vivo, nuevas
(no existían antes de esta reorganización, pedido explícito de la
clienta al definir este formulario). Toda la lógica de cálculo vive en
`app.negocio.balance` — ver su docstring para el detalle de qué cuenta
como ingreso y cómo se traduce el alcance de ubicación de Ingresos/
Resultado (Localidad/Edificio/Unidad/Consultorio) al Alcance propio de
Gastos operativos (Espacio general/Edificio/Unidad).

Ingresos y Resultado comparten el mismo panel de filtros (Período,
cambiable pero arranca en el actual — mismo criterio que Gastos
operativos — más la cascada Localidad/Edificio/Unidad/Consultorio,
mismo criterio y mismo código que Estadísticas Varias, duplicado acá
como el resto de las pantallas del sistema que arman su propia cadena
de filtros) pero cada uno arma el suyo por separado (`_PanelIngresos`/
`_PanelResultado`), sin una clase base compartida — mismo criterio de
"cada pantalla arma la suya" que el resto del sistema.

Los dos muestran su resultado en una TABLA (no en etiquetas sueltas,
como en la primera versión): una sola fila con el período elegido por
defecto, o todos los períodos con datos (del más nuevo al más viejo,
reusando `app.negocio.estadisticas._periodos_para_filtro`) al apretar
"Ver historial". El viejo botón "Actualizar" (no hacía nada que los
filtros ya conectados no dispararan solos) se reemplaza por ese botón
("Ver historial", `botonPrimario`) y "Ver período actual"
(`botonSecundario`, vuelve a mostrar solo el período en curso) — pedido
explícito de la clienta. Gastos (el catálogo anidado) no se tocó."""
from __future__ import annotations

import sqlite3

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.pantallas.catalogos import _opciones_consultorio, _opciones_edificio, _opciones_localidad, _opciones_unidad
from app.gui.pantallas.pagos import _SpinMonto
from app.gui.widgets.foco import excluir_tabla_del_tab
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.items_tabla import item_centrado
from app.gui.widgets.orden_tabla import OrdenTabla
from app.gui.widgets.resumen_saldo import item_monto
from app.gui.widgets.selector_periodo import SelectorPeriodo
from app.negocio.balance import resultado_periodo, total_ingresos_periodo
from app.negocio.dias import periodo_actual
from app.negocio.estadisticas import _ids_consultorio_del_alcance, _periodos_para_filtro
from app.negocio.formato import formatear_moneda
from app.negocio.gastos_operativos import ALCANCES_GASTO, gasto_en_conflicto, sanear_alcance, texto_afectacion_gasto
from app.negocio.listas_editables import valores_lista
from app.pdf.estilos import clave_orden_unidad
from app.repositorio.registro import obtener_repositorio

_ANCHO_CAMPO = 220
_ANCHO_PANEL_FILTROS = 240

# Mismo colchón de siempre para el padding interno que Qt le suma a la
# celda del encabezado (ver `imagenes._COLCHON_TITULO_COLUMNA`/
# `control_pagos._COLCHON_TITULO_COLUMNA`) — "Período" de "Gastos" al
# ancho mínimo que entra el título sin cortar.
_COLCHON_TITULO_COLUMNA = 12

_COLUMNAS_INGRESOS = [
    "Período", "Ingreso por horas regulares", "Ingreso por horas aisladas",
    "Ingreso por feriados\ny días especiales", "Total ingresos",
]
_COLUMNAS_RESULTADO = ["Período", "Total ingresos", "Total gastos", "Balance del período"]


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _titulo_subtotal_periodo(periodo: str) -> str:
    """"Subtotal gastos período 09-2026": el período se guarda como
    AAAA-MM pero acá se muestra invertido, MM-AAAA (mismo criterio que
    tenía el catálogo genérico que este panel reemplaza)."""
    anio, mes = periodo.split("-")
    return f"Subtotal gastos período {mes}-{anio}"


class _DialogoGasto(QDialog):
    """Nuevo/Editar de "Gastos" (pedido explícito de la clienta,
    reemplaza por completo el diálogo genérico que armaba `crud_
    generico.PantallaCRUD` para `GastoOperativo`): "Nuevo" solo permite
    cargar un concepto extraordinario MANUAL (Origen fijo, no editable
    — lo Importado se sincroniza solo desde "Carga y control" de
    Control de pagos, ver `app.negocio.control_pagos.sincronizar_gasto_
    operativo`, y se edita desde ahí). "Afectación" (antes "Alcance")
    suma el selector de Localidad que faltaba, además de los ya
    existentes de Edificio/Unidad/Consultorio — exactamente uno de los
    cuatro queda habilitado según lo elegido en el combo de Afectación,
    mismo mecanismo de cascada que ya tenía `catalogos._al_abrir_
    dialogo_gasto` (ahora de baja, sin otro consumidor)."""

    def __init__(
        self, conn: sqlite3.Connection, *, gasto: sqlite3.Row | None = None,
        periodo_default: str | None = None, parent=None,
    ):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Nuevo gasto" if gasto is None else "Editar gasto")
        layout = QVBoxLayout(self)

        layout.addWidget(_titulo_campo("Período"))
        self.campo_periodo = SelectorPeriodo(conn)
        if gasto is not None:
            self.campo_periodo.set_periodo(gasto["Periodo"])
        elif periodo_default is not None:
            self.campo_periodo.set_periodo(periodo_default)
        layout.addWidget(self.campo_periodo)

        layout.addWidget(_titulo_campo("Nombre"))
        self.campo_nombre = QLineEdit(gasto["Concepto"] if gasto is not None and gasto["Concepto"] else "")
        layout.addWidget(self.campo_nombre)

        layout.addWidget(_titulo_campo("Categoría"))
        self.combo_categoria = QComboBox()
        self.combo_categoria.setEditable(True)
        for valor in valores_lista(conn, "CategoriaControlPagos"):
            self.combo_categoria.addItem(valor)
        if gasto is not None and gasto["Categoria"]:
            self.combo_categoria.setCurrentText(gasto["Categoria"])
        else:
            self.combo_categoria.setCurrentIndex(-1)
        layout.addWidget(self.combo_categoria)

        layout.addWidget(_titulo_campo("Monto"))
        self.spin_monto = _SpinMonto()
        self.spin_monto.setRange(0, 100_000_000)
        self.spin_monto.setDecimals(2)
        self.spin_monto.setValue(gasto["Monto"] if gasto is not None else 0)
        layout.addWidget(self.spin_monto)

        layout.addWidget(_titulo_campo("Afectación"))
        self.combo_afectacion = QComboBox()
        for alcance in ALCANCES_GASTO:
            self.combo_afectacion.addItem(alcance, alcance)
        layout.addWidget(self.combo_afectacion)

        self.combo_localidad = QComboBox()
        for id_, etiqueta in _opciones_localidad(conn):
            self.combo_localidad.addItem(etiqueta, id_)
        layout.addWidget(self.combo_localidad)

        self.combo_edificio = QComboBox()
        self.combo_edificio.addItem("Sin relación a edificio específico", None)
        for id_, etiqueta in _opciones_edificio(conn):
            self.combo_edificio.addItem(etiqueta, id_)
        layout.addWidget(self.combo_edificio)

        self.combo_unidad = QComboBox()
        self.combo_unidad.addItem("Sin relación a unidad específica", None)
        for id_, etiqueta in _opciones_unidad(conn):
            self.combo_unidad.addItem(etiqueta, id_)
        layout.addWidget(self.combo_unidad)

        self.combo_consultorio = QComboBox()
        self.combo_consultorio.addItem("Sin relación a consultorio específico", None)
        for id_, etiqueta in _opciones_consultorio(conn):
            self.combo_consultorio.addItem(etiqueta, id_)
        layout.addWidget(self.combo_consultorio)

        # Precarga ANTES de conectar la cascada: si se conectara primero,
        # fijar el combo de Afectación de un gasto existente dispararía
        # `_actualizar_combos_afectacion` y resetearía a "Sin relación..."
        # el combo de ubicación que se está a punto de precargar acá
        # abajo (mismo orden que ya usaba `_al_abrir_dialogo_gasto`).
        if gasto is not None:
            indice_alcance = self.combo_afectacion.findData(gasto["Alcance"])
            if indice_alcance >= 0:
                self.combo_afectacion.setCurrentIndex(indice_alcance)
            if gasto["Alcance"] == "Localidad":
                indice = self.combo_localidad.findData(gasto["IdLocalidad"])
                if indice >= 0:
                    self.combo_localidad.setCurrentIndex(indice)
            elif gasto["Alcance"] == "Edificio":
                indice = self.combo_edificio.findData(gasto["IdEdificio"])
                if indice >= 0:
                    self.combo_edificio.setCurrentIndex(indice)
            elif gasto["Alcance"] == "Unidad":
                indice = self.combo_unidad.findData(gasto["IdUnidad"])
                if indice >= 0:
                    self.combo_unidad.setCurrentIndex(indice)
            elif gasto["Alcance"] == "Consultorio":
                indice = self.combo_consultorio.findData(gasto["IdConsultorio"])
                if indice >= 0:
                    self.combo_consultorio.setCurrentIndex(indice)

        self.combo_afectacion.currentIndexChanged.connect(self._actualizar_combos_afectacion)
        self._actualizar_combos_afectacion()

        layout.addWidget(_titulo_campo("Origen"))
        # Pedido explícito de la clienta: siempre "Manual" desde este
        # diálogo, no editable — lo Importado viene solo (sincronizado)
        # desde "Carga y control" de Control de pagos, y se edita desde
        # ahí, no desde "Gastos".
        layout.addWidget(QLabel("Manual"))

        layout.addWidget(_titulo_campo("Observación"))
        self.campo_observacion = QPlainTextEdit(
            gasto["Observacion"] if gasto is not None and gasto["Observacion"] else "",
        )
        layout.addWidget(self.campo_observacion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        self._foco = instalar_enter_avanza_foco(
            [
                self.campo_periodo.spin_anio, self.campo_periodo.combo_mes, self.campo_nombre, self.combo_categoria,
                self.spin_monto, self.combo_afectacion, self.combo_localidad, self.combo_edificio, self.combo_unidad,
                self.combo_consultorio, self.campo_observacion, botones.button(QDialogButtonBox.StandardButton.Ok),
            ],
            parent=self,
        )

    def _actualizar_combos_afectacion(self) -> None:
        alcance = self.combo_afectacion.currentData()
        self.combo_localidad.setEnabled(alcance == "Localidad")
        self.combo_edificio.setEnabled(alcance == "Edificio")
        self.combo_unidad.setEnabled(alcance == "Unidad")
        self.combo_consultorio.setEnabled(alcance == "Consultorio")
        if alcance != "Localidad":
            self.combo_localidad.setCurrentIndex(0)
        if alcance != "Edificio":
            self.combo_edificio.setCurrentIndex(0)
        if alcance != "Unidad":
            self.combo_unidad.setCurrentIndex(0)
        if alcance != "Consultorio":
            self.combo_consultorio.setCurrentIndex(0)

    def valores(self) -> dict:
        return {
            "Periodo": self.campo_periodo.periodo(),
            "Concepto": self.campo_nombre.text().strip() or None,
            "Categoria": self.combo_categoria.currentText().strip() or None,
            "Monto": self.spin_monto.value(),
            "Alcance": self.combo_afectacion.currentData(),
            "IdLocalidad": self.combo_localidad.currentData(),
            "IdEdificio": self.combo_edificio.currentData(),
            "IdUnidad": self.combo_unidad.currentData(),
            "IdConsultorio": self.combo_consultorio.currentData(),
            "Origen": "Manual",
            "Observacion": self.campo_observacion.toPlainText().strip() or None,
        }


class _PanelGastos(QWidget):
    """"Gastos" de Balance del negocio (pedido explícito de la clienta:
    rediseño completo, reemplaza el catálogo genérico `catalogos.
    pantalla_gastos_operativos`, ahora de baja). Columnas de tabla
    Período/Nombre/Categoría/Afectación/Monto/Origen/Observación (en
    ese orden), ordenadas por Período, Afectación, Categoría y Nombre.
    Período con `SelectorPeriodo` (mismo widget que Ingresos/Resultado),
    arranca en el período actual. Filtros de visualización (Nombre/
    Categoría/Afectación/Origen, en cascada mutua con sentinel "Todos/
    Todas") igual mecanismo que la columna 4 de "Carga y control"
    (`app.gui.pantallas.control_pagos._PanelCargaControl`) — nunca
    tocan el subtotal, que siempre es el total real del período
    elegido."""

    _TODOS = object()

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setObjectName("panelSolapa")
        self._registros: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.actualizar()
        self.campo_periodo.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        self.tabla = QTableWidget()
        excluir_tabla_del_tab(self.tabla)
        self.tabla.setColumnCount(7)
        self.tabla.setHorizontalHeaderLabels(
            ["Período", "Nombre", "Categoría", "Afectación", "Monto", "Origen", "Observación"],
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        # Nombre/Categoría/Afectación quedan en Interactive (ancho fijo,
        # +30% calculado en `actualizar()`) en vez de ResizeToContents —
        # pedido explícito de la clienta.
        for columna in (1, 2, 3):
            header.setSectionResizeMode(columna, QHeaderView.ResizeMode.Interactive)
        for columna in (4, 5):
            header.setSectionResizeMode(columna, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones)
        # Tabla ordenable por click en el encabezado — pedido explícito
        # de la clienta, mismo mecanismo que "Carga y control"/
        # "Historial"/"Registrar pagos" (`OrdenTabla`, ver `app/gui/
        # widgets/orden_tabla.py`). El orden por click es un criterio
        # transitorio: F5 lo vuelve al orden por defecto (`reiniciar`).
        self._orden = OrdenTabla(self.tabla, self.actualizar)

        panel_izquierda = QWidget()
        panel_izquierda.setFixedWidth(_ANCHO_PANEL_FILTROS)
        columna = QVBoxLayout(panel_izquierda)

        columna.addWidget(_titulo_campo("Período"))
        self.campo_periodo = SelectorPeriodo(self.conn)
        self.campo_periodo.setFixedWidth(_ANCHO_CAMPO)
        self.campo_periodo.cambiado.connect(self.actualizar)
        columna.addWidget(self.campo_periodo)

        self.boton_nuevo = QPushButton("Nuevo")
        self.boton_nuevo.setObjectName("botonPrimario")
        self.boton_nuevo.setFixedWidth(_ANCHO_CAMPO)
        self.boton_nuevo.clicked.connect(self._nuevo)
        columna.addWidget(self.boton_nuevo)

        self.boton_editar = QPushButton("Editar")
        self.boton_editar.setObjectName("botonSecundario")
        self.boton_editar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_editar.clicked.connect(self._editar)
        columna.addWidget(self.boton_editar)

        self.boton_eliminar = QPushButton("Eliminar")
        self.boton_eliminar.setObjectName("botonSecundario")
        self.boton_eliminar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_eliminar.clicked.connect(self._eliminar)
        columna.addWidget(self.boton_eliminar)

        columna.addWidget(_linea_divisoria())
        # Pedido explícito de la clienta: la etiqueta del subtotal y su
        # importe van en negrita.
        self.etiqueta_titulo_subtotal = QLabel()
        self.etiqueta_titulo_subtotal.setStyleSheet("font-weight: bold;")
        columna.addWidget(self.etiqueta_titulo_subtotal)
        self.etiqueta_subtotal = QLabel()
        self.etiqueta_subtotal.setStyleSheet("font-weight: bold;")
        columna.addWidget(self.etiqueta_subtotal)

        columna.addWidget(_linea_divisoria())
        titulo_filtros = QLabel("Filtros")
        titulo_filtros.setObjectName("subtituloSeccion")
        columna.addWidget(titulo_filtros)

        self.combo_filtro_nombre = QComboBox()
        self.combo_filtro_categoria = QComboBox()
        self.combo_filtro_afectacion = QComboBox()
        self.combo_filtro_origen = QComboBox()
        for etiqueta, combo in (
            ("Nombre", self.combo_filtro_nombre), ("Categoría", self.combo_filtro_categoria),
            ("Afectación", self.combo_filtro_afectacion), ("Origen", self.combo_filtro_origen),
        ):
            columna.addWidget(_titulo_campo(etiqueta))
            combo.setFixedWidth(_ANCHO_CAMPO)
            combo.currentIndexChanged.connect(self.actualizar)
            columna.addWidget(combo)

        self.boton_reiniciar_filtros = QPushButton("Reiniciar filtros")
        self.boton_reiniciar_filtros.setObjectName("botonSecundario")
        self.boton_reiniciar_filtros.setFixedWidth(_ANCHO_CAMPO)
        self.boton_reiniciar_filtros.clicked.connect(self._reiniciar_filtros)
        columna.addWidget(self.boton_reiniciar_filtros)
        columna.addStretch()

        layout_externo.addWidget(panel_izquierda)
        layout_externo.addWidget(self.tabla, stretch=1)

        self._foco = instalar_enter_avanza_foco(
            [
                self.campo_periodo.spin_anio, self.campo_periodo.combo_mes, self.boton_nuevo, self.boton_editar,
                self.boton_eliminar, self.combo_filtro_nombre, self.combo_filtro_categoria,
                self.combo_filtro_afectacion, self.combo_filtro_origen, self.boton_reiniciar_filtros,
            ],
            parent=self,
        )
        self._actualizar_botones()

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._registros[filas[0].row()]

    def _actualizar_botones(self) -> None:
        hay_seleccion = self._fila_seleccionada() is not None
        self.boton_editar.setEnabled(hay_seleccion)
        self.boton_eliminar.setEnabled(hay_seleccion)

    def _valor_filtro(self, fila: tuple, clave: str) -> str:
        gasto, afectacion = fila
        if clave == "nombre":
            return gasto["Concepto"] or "?"
        if clave == "categoria":
            return gasto["Categoria"] or ""
        if clave == "afectacion":
            return afectacion
        return gasto["Origen"] or ""

    def _combos_filtro(self) -> dict:
        return {
            "nombre": self.combo_filtro_nombre, "categoria": self.combo_filtro_categoria,
            "afectacion": self.combo_filtro_afectacion, "origen": self.combo_filtro_origen,
        }

    def _coincide_filtros(self, fila: tuple, *, excepto: str | None = None) -> bool:
        for clave, combo in self._combos_filtro().items():
            if clave == excepto:
                continue
            filtro = combo.currentData()
            if filtro is not None and filtro is not self._TODOS and self._valor_filtro(fila, clave) != filtro:
                return False
        return True

    def _repoblar_filtros_cascada(self, filas_totales: list) -> None:
        etiquetas_todos = {"nombre": "Todos", "categoria": "Todas", "afectacion": "Todas", "origen": "Todos"}
        for clave, combo in self._combos_filtro().items():
            valores = sorted({
                self._valor_filtro(f, clave) for f in filas_totales if self._coincide_filtros(f, excepto=clave)
            })
            actual = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(etiquetas_todos[clave], self._TODOS)
            for valor in valores:
                combo.addItem(valor, valor)
            indice = combo.findData(actual) if actual is not None else 0
            combo.setCurrentIndex(indice if indice >= 0 else 0)
            combo.blockSignals(False)

    def _reiniciar_filtros(self) -> None:
        for combo in self._combos_filtro().values():
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.actualizar()

    def actualizar(self) -> None:
        periodo = self.campo_periodo.periodo()
        gastos = obtener_repositorio(self.conn, "GastoOperativo").listar(Periodo=periodo)
        filas_totales = [(g, texto_afectacion_gasto(self.conn, g)) for g in gastos]
        self._repoblar_filtros_cascada(filas_totales)
        filas = [f for f in filas_totales if self._coincide_filtros(f)]
        # Pedido explícito de la clienta: se ordena por período primero,
        # luego por afectación, luego por categoría, luego por nombre.
        filas.sort(key=lambda f: (f[0]["Periodo"], f[1], f[0]["Categoria"] or "", f[0]["Concepto"] or ""))
        if self._orden.columna is not None:
            filas.sort(key=self._clave_orden_columna(self._orden.columna), reverse=not self._orden.ascendente)
        self._registros = [f[0] for f in filas]

        self.tabla.setRowCount(len(filas))
        for fila_idx, (gasto, afectacion) in enumerate(filas):
            self.tabla.setItem(fila_idx, 0, item_centrado(gasto["Periodo"]))
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(gasto["Concepto"] or ""))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(gasto["Categoria"] or ""))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(afectacion))
            self.tabla.setItem(fila_idx, 4, item_monto(gasto["Monto"]))
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem(gasto["Origen"] or ""))
            self.tabla.setItem(fila_idx, 6, QTableWidgetItem(gasto["Observacion"] or ""))
        # Pedido explícito de la clienta: "Período" al ancho mínimo que
        # entra el título sin cortar (mismo criterio que `control_pagos.
        # _PanelHistorialControlPagos` con "Período"/"Vencimiento") y
        # centrado (`item_centrado` arriba).
        metrica_encabezado = QFontMetrics(self.tabla.horizontalHeader().font())
        ancho_periodo = metrica_encabezado.horizontalAdvance("Período") + _COLCHON_TITULO_COLUMNA
        self.tabla.setColumnWidth(0, ancho_periodo)
        # Pedido explícito de la clienta: "Nombre"/"Categoría"/"Afectación"
        # +30% de su ancho natural (post-carga de filas); ronda
        # siguiente: +25% más sobre ese ancho ya ampliado (total
        # natural×1.3×1.25, mismo criterio en cascada que "Cuenta/Id"/
        # "Importe" de "Carga y control", CLAUDE.md). El ancho que esto
        # le saca a "Observación" sale solo, porque es la única columna
        # en `Stretch` (ver `_armar_ui`).
        for columna in (1, 2, 3):
            self.tabla.resizeColumnToContents(columna)
            ancho_mas_30 = round(self.tabla.columnWidth(columna) * 1.3)
            self.tabla.setColumnWidth(columna, round(ancho_mas_30 * 1.25))
        self._actualizar_subtotal(periodo, gastos)
        self._actualizar_botones()

    @staticmethod
    def _clave_orden_columna(columna: int):
        """Clave de orden para un click de encabezado — mismo criterio
        que `control_pagos._PanelCargaControl._clave_orden_columna`: un
        dict de lambdas, una por columna, sobre la misma tupla
        (gasto, afectación) que ya arma `actualizar`."""
        claves = {
            0: lambda f: f[0]["Periodo"],
            1: lambda f: f[0]["Concepto"] or "",
            2: lambda f: f[0]["Categoria"] or "",
            3: lambda f: f[1],
            4: lambda f: f[0]["Monto"] or 0,
            5: lambda f: f[0]["Origen"] or "",
            6: lambda f: f[0]["Observacion"] or "",
        }
        return claves[columna]

    def _actualizar_subtotal(self, periodo: str, gastos: list) -> None:
        """El subtotal es siempre el total REAL del período elegido —
        los filtros de Nombre/Categoría/Afectación/Origen de más arriba
        solo afectan qué filas se VEN en la tabla (mismo criterio que
        "Filtros que solo afectan la visualización" de CLAUDE.md), nunca
        este número."""
        subtotal = sum(g["Monto"] or 0 for g in gastos)
        self.etiqueta_titulo_subtotal.setText(_titulo_subtotal_periodo(periodo))
        self.etiqueta_subtotal.setText(formatear_moneda(subtotal))

    def _resolver_conflicto(self, valores: dict, registro: sqlite3.Row | None) -> dict | None:
        id_actual = registro["IdGasto"] if registro is not None else None
        conflicto = gasto_en_conflicto(
            self.conn, periodo=valores.get("Periodo"), concepto=valores.get("Concepto"),
            origen=valores.get("Origen"), id_gasto_actual=id_actual,
        )
        if conflicto is None:
            return valores
        respuesta = QMessageBox.question(
            self, "Conflicto de origen",
            f"Ya existe un gasto \"{conflicto['Concepto']}\" del período {conflicto['Periodo']} con origen "
            f"\"{conflicto['Origen']}\" ({formatear_moneda(conflicto['Monto'])}). No pueden convivir un origen "
            f"Manual y uno Importado para el mismo concepto y período.\n\n¿Reemplazarlo por este nuevo valor?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return None
        obtener_repositorio(self.conn, "GastoOperativo").eliminar(conflicto["IdGasto"])
        return valores

    def _nuevo(self) -> None:
        dialogo = _DialogoGasto(self.conn, periodo_default=self.campo_periodo.periodo(), parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        valores = sanear_alcance(dialogo.valores())
        valores = self._resolver_conflicto(valores, registro=None)
        if valores is None:
            return
        obtener_repositorio(self.conn, "GastoOperativo").crear(**valores)
        self.actualizar()
        QMessageBox.information(self, "Nuevo gasto", "Gasto creado con éxito.")

    def _editar(self) -> None:
        gasto = self._fila_seleccionada()
        if gasto is None:
            return
        if gasto["Origen"] == "Importado":
            # Pedido explícito de la clienta: lo Importado (sincronizado
            # desde Control de pagos) se edita desde "Carga y control"
            # de ese formulario, nunca desde acá.
            QMessageBox.warning(
                self, "Editar",
                "Este gasto viene importado desde \"Control de pagos\" — se edita desde la solapa "
                "\"Carga y control\" de ese formulario, no desde \"Gastos\".",
            )
            return
        dialogo = _DialogoGasto(self.conn, gasto=gasto, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        valores = sanear_alcance(dialogo.valores())
        valores = self._resolver_conflicto(valores, registro=gasto)
        if valores is None:
            return
        obtener_repositorio(self.conn, "GastoOperativo").actualizar(gasto["IdGasto"], **valores)
        self.actualizar()
        QMessageBox.information(self, "Editar gasto", "Gasto actualizado con éxito.")

    def _eliminar(self) -> None:
        gasto = self._fila_seleccionada()
        if gasto is None:
            return
        respuesta = QMessageBox.question(
            self, "Eliminar gasto", f"¿Eliminar «{gasto['Concepto'] or '(sin nombre)'}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        obtener_repositorio(self.conn, "GastoOperativo").eliminar(gasto["IdGasto"])
        self.actualizar()
        QMessageBox.information(self, "Eliminar gasto", "Gasto eliminado con éxito.")

    def reiniciar(self) -> None:
        """F5: vuelve todo a su estado inicial (período actual, filtros,
        orden, selección) — mismo criterio que el resto del sistema
        (CLAUDE.md, "F5... reinicia desde cero, distinto de showEvent")."""
        self.campo_periodo.set_periodo(periodo_actual(self.conn))
        self.tabla.clearSelection()
        self._orden.reiniciar()
        self._reiniciar_filtros()
        self.campo_periodo.setFocus()


def _armar_tabla(columnas: list[str]) -> QTableWidget:
    """Pocas columnas, todas de importancia pareja — Stretch en las
    columnas (mismo criterio que Placas/Importar planilla) para que se
    reparta todo el ancho disponible del panel en vez de dejar un
    espacio en blanco al final (ver el bug ya documentado en "Valores
    vigentes")."""
    tabla = QTableWidget()
    excluir_tabla_del_tab(tabla)
    tabla.setColumnCount(len(columnas))
    tabla.setHorizontalHeaderLabels(columnas)
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabla.verticalHeader().setVisible(False)
    tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    header = tabla.horizontalHeader()
    for columna in range(len(columnas)):
        header.setSectionResizeMode(columna, QHeaderView.ResizeMode.Stretch)
    return tabla


class _PanelFiltrosMixin:
    """Arma la columna de filtros (Período + cascada de ubicación) y la
    cadena de foco, compartida palabra por palabra entre `_PanelIngresos`
    y `_PanelResultado` — no una clase base de verdad (cada panel sigue
    siendo su propio `QWidget`), solo el método que arma ese pedazo de
    UI, para no repetir el cableado de la cascada dos veces."""

    def _armar_panel_filtros(self) -> QWidget:
        panel_filtros = QWidget()
        panel_filtros.setFixedWidth(_ANCHO_PANEL_FILTROS)
        columna = QVBoxLayout(panel_filtros)

        columna.addWidget(_titulo_campo("Período"))
        # Punto propio de esta vuelta: selector Año+Mes en línea en vez
        # de texto libre "AAAA-MM" — mismo widget ya introducido en
        # Liquidaciones ("Emisión de archivos").
        self.campo_periodo = SelectorPeriodo(self.conn)
        self.campo_periodo.setFixedWidth(_ANCHO_CAMPO)
        self.campo_periodo.cambiado.connect(self.actualizar)
        columna.addWidget(self.campo_periodo)

        columna.addWidget(_titulo_campo("Localidad"))
        self.combo_localidad = QComboBox()
        self.combo_localidad.setFixedWidth(_ANCHO_CAMPO)
        self.combo_localidad.currentIndexChanged.connect(self._cargar_combo_edificio)
        columna.addWidget(self.combo_localidad)

        columna.addWidget(_titulo_campo("Edificio"))
        self.combo_edificio = QComboBox()
        self.combo_edificio.setFixedWidth(_ANCHO_CAMPO)
        self.combo_edificio.currentIndexChanged.connect(self._cargar_combo_unidad)
        columna.addWidget(self.combo_edificio)

        columna.addWidget(_titulo_campo("Unidad"))
        self.combo_unidad = QComboBox()
        self.combo_unidad.setFixedWidth(_ANCHO_CAMPO)
        self.combo_unidad.currentIndexChanged.connect(self._cargar_combo_consultorio)
        columna.addWidget(self.combo_unidad)

        columna.addWidget(_titulo_campo("Consultorio"))
        self.combo_consultorio = QComboBox()
        self.combo_consultorio.setFixedWidth(_ANCHO_CAMPO)
        self.combo_consultorio.currentIndexChanged.connect(self.actualizar)
        columna.addWidget(self.combo_consultorio)

        self.boton_historial = QPushButton("Ver historial")
        self.boton_historial.setObjectName("botonPrimario")
        self.boton_historial.setFixedWidth(_ANCHO_CAMPO)
        self.boton_historial.clicked.connect(self._ver_historial)
        columna.addWidget(self.boton_historial)

        self.boton_periodo_actual = QPushButton("Ver período actual")
        self.boton_periodo_actual.setObjectName("botonSecundario")
        self.boton_periodo_actual.setFixedWidth(_ANCHO_CAMPO)
        self.boton_periodo_actual.clicked.connect(self._ver_periodo_actual)
        columna.addWidget(self.boton_periodo_actual)

        columna.addStretch()

        self._cargar_combo_localidad()
        self._foco = instalar_enter_avanza_foco(
            [
                self.campo_periodo.spin_anio, self.campo_periodo.combo_mes,
                self.combo_localidad, self.combo_edificio,
                self.combo_unidad, self.combo_consultorio, self.boton_historial, self.boton_periodo_actual,
            ],
            parent=self,
        )
        return panel_filtros

    def _cargar_combo_localidad(self) -> None:
        self.combo_localidad.blockSignals(True)
        self.combo_localidad.clear()
        self.combo_localidad.addItem("Todas", None)
        for f in self.conn.execute("SELECT IdLocalidad, Localidad FROM Localidad ORDER BY Localidad").fetchall():
            self.combo_localidad.addItem(f["Localidad"], f["IdLocalidad"])
        self.combo_localidad.blockSignals(False)
        self._cargar_combo_edificio()

    def _cargar_combo_edificio(self, *_args) -> None:
        self.combo_edificio.blockSignals(True)
        self.combo_edificio.clear()
        self.combo_edificio.addItem("Todos", None)
        id_localidad = self.combo_localidad.currentData()
        sql = "SELECT IdEdificio, Nombre FROM Edificio"
        parametros: list = []
        if id_localidad is not None:
            sql += " WHERE IdLocalidad = ?"
            parametros.append(id_localidad)
        sql += " ORDER BY Nombre"
        for f in self.conn.execute(sql, parametros).fetchall():
            self.combo_edificio.addItem(f["Nombre"], f["IdEdificio"])
        self.combo_edificio.blockSignals(False)
        self._cargar_combo_unidad()

    def _cargar_combo_unidad(self, *_args) -> None:
        self.combo_unidad.blockSignals(True)
        self.combo_unidad.clear()
        self.combo_unidad.addItem("Todas", None)
        id_edificio = self.combo_edificio.currentData()
        sql = "SELECT IdUnidad, Departamento FROM Unidad"
        parametros: list = []
        if id_edificio is not None:
            sql += " WHERE IdEdificio = ?"
            parametros.append(id_edificio)
        filas = self.conn.execute(sql, parametros).fetchall()
        # Orden por piso (PB, EP, después ascendente numérico) + letra a
        # igual piso — pedido general de la clienta, no expresable en el
        # ORDER BY de SQL (ver `clave_orden_unidad`/`reservas._opciones_unidad`).
        filas = sorted(filas, key=lambda f: clave_orden_unidad(f["Departamento"]))
        for f in filas:
            self.combo_unidad.addItem(f["Departamento"], f["IdUnidad"])
        self.combo_unidad.blockSignals(False)
        self._cargar_combo_consultorio()

    def _cargar_combo_consultorio(self, *_args) -> None:
        self.combo_consultorio.blockSignals(True)
        self.combo_consultorio.clear()
        self.combo_consultorio.addItem("Todos", None)
        id_unidad = self.combo_unidad.currentData()
        sql = "SELECT IdConsultorio, NumeroConsultorio FROM Consultorio"
        parametros: list = []
        if id_unidad is not None:
            sql += " WHERE IdUnidad = ?"
            parametros.append(id_unidad)
        sql += " ORDER BY NumeroConsultorio"
        for f in self.conn.execute(sql, parametros).fetchall():
            self.combo_consultorio.addItem(str(f["NumeroConsultorio"]), f["IdConsultorio"])
        self.combo_consultorio.blockSignals(False)
        self.actualizar()

    def _ver_periodo_actual(self) -> None:
        """"Ver período actual" solo toca el campo Período — pedido
        explícito de la clienta, a diferencia del viejo "Actualizar" que
        también reiniciaba la cascada de ubicación (ese reinicio se saca
        por completo, no tenía un pedido real detrás)."""
        self.campo_periodo.set_periodo(periodo_actual(self.conn))
        self.actualizar()

    def _restablecer_filtros(self) -> None:
        """F5 (`reiniciar()` de cada subclase): a diferencia de "Ver
        período actual", acá sí vuelve TODO al estado de apertura —
        Período al actual y la cascada de ubicación a "Todas/Todos".
        Se reconstruye `combo_localidad` desde cero (`_cargar_combo_
        localidad`, que ya encadena hasta `actualizar()`) en vez de
        `setCurrentIndex(0)`: si ya estaba en el índice 0, ese set no
        dispara `currentIndexChanged` y la cascada de abajo (Edificio/
        Unidad/Consultorio) quedaría con una selección vieja."""
        self.campo_periodo.set_periodo(periodo_actual(self.conn))
        self._cargar_combo_localidad()


class _PanelIngresos(_PanelFiltrosMixin, QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._armar_ui()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.campo_periodo.setFocus()

    def reiniciar(self) -> None:
        self._restablecer_filtros()
        self.campo_periodo.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        # La tabla se arma ANTES que el panel de filtros: construir los
        # filtros dispara la cascada de combos, que termina llamando a
        # `actualizar()` — la tabla tiene que existir ya.
        self.tabla = _armar_tabla(_COLUMNAS_INGRESOS)

        layout_externo.addWidget(self._armar_panel_filtros())
        layout_externo.addWidget(self.tabla, stretch=1)

    def _fila(self, periodo: str, ids_consultorio: list[int] | None) -> tuple:
        regulares, aisladas, feriados_trabajados = total_ingresos_periodo(self.conn, periodo, ids_consultorio)
        total = regulares + aisladas + feriados_trabajados
        return periodo, regulares, aisladas, feriados_trabajados, total

    def _llenar_filas(self, filas: list[tuple]) -> None:
        self.tabla.setRowCount(len(filas))
        for fila_idx, (periodo, regulares, aisladas, feriados_trabajados, total) in enumerate(filas):
            self.tabla.setItem(fila_idx, 0, item_centrado(periodo))
            self.tabla.setItem(fila_idx, 1, item_monto(regulares))
            self.tabla.setItem(fila_idx, 2, item_monto(aisladas))
            self.tabla.setItem(fila_idx, 3, item_monto(feriados_trabajados))
            self.tabla.setItem(fila_idx, 4, item_monto(total))

    def _ids_consultorio(self) -> list[int] | None:
        return _ids_consultorio_del_alcance(
            self.conn,
            id_localidad=self.combo_localidad.currentData(), id_edificio=self.combo_edificio.currentData(),
            id_unidad=self.combo_unidad.currentData(), id_consultorio=self.combo_consultorio.currentData(),
        )

    def actualizar(self) -> None:
        periodo = self.campo_periodo.periodo()
        self._llenar_filas([self._fila(periodo, self._ids_consultorio())])

    def _ver_historial(self) -> None:
        """Una fila por cada período con algún dato cargado en el
        sistema, del más nuevo al más viejo (ya es el orden que devuelve
        `_periodos_para_filtro` sin filtro de rango) — respeta el
        alcance de ubicación elegido, igual que la fila única de
        `actualizar()`."""
        ids_consultorio = self._ids_consultorio()
        periodos = _periodos_para_filtro(self.conn, desde=None, hasta=None)
        self._llenar_filas([self._fila(periodo, ids_consultorio) for periodo in periodos])


class _PanelResultado(_PanelFiltrosMixin, QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._armar_ui()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.campo_periodo.setFocus()

    def reiniciar(self) -> None:
        self._restablecer_filtros()
        self.campo_periodo.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        # Mismo motivo que en _PanelIngresos: armar la tabla antes que
        # los filtros, porque construir los filtros ya dispara `actualizar()`.
        self.tabla = _armar_tabla(_COLUMNAS_RESULTADO)

        layout_externo.addWidget(self._armar_panel_filtros())
        layout_externo.addWidget(self.tabla, stretch=1)

    def _fila(self, periodo: str) -> tuple:
        ingresos, gastos, resultado = resultado_periodo(
            self.conn, periodo,
            id_localidad=self.combo_localidad.currentData(), id_edificio=self.combo_edificio.currentData(),
            id_unidad=self.combo_unidad.currentData(), id_consultorio=self.combo_consultorio.currentData(),
        )
        return periodo, ingresos, gastos, resultado

    def _llenar_filas(self, filas: list[tuple]) -> None:
        self.tabla.setRowCount(len(filas))
        for fila_idx, (periodo, ingresos, gastos, resultado) in enumerate(filas):
            self.tabla.setItem(fila_idx, 0, item_centrado(periodo))
            self.tabla.setItem(fila_idx, 1, item_monto(ingresos))
            self.tabla.setItem(fila_idx, 2, item_monto(-gastos))
            self.tabla.setItem(fila_idx, 3, item_monto(resultado))

    def actualizar(self) -> None:
        periodo = self.campo_periodo.periodo()
        self._llenar_filas([self._fila(periodo)])

    def _ver_historial(self) -> None:
        """Mismo criterio que `_PanelIngresos._ver_historial`: una fila
        por cada período con algún dato, del más nuevo al más viejo,
        respetando el alcance de ubicación elegido."""
        periodos = _periodos_para_filtro(self.conn, desde=None, hasta=None)
        self._llenar_filas([self._fila(periodo) for periodo in periodos])


class PantallaBalanceDelNegocio(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Balance del negocio".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_gastos = _PanelGastos(conn)
        self.pestanas.addTab(self.panel_gastos, "Gastos")
        self.panel_ingresos = _PanelIngresos(conn)
        self.pestanas.addTab(self.panel_ingresos, "Ingresos")
        self.panel_resultado = _PanelResultado(conn)
        self.pestanas.addTab(self.panel_resultado, "Resultado")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
