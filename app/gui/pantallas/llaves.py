"""Pantalla de Llaves (sección 3.7, replanteada en conversación con la
clienta — segunda vuelta): administra los TIPOS de llave (Tipos de
llaves), sus accesos (Accesos habilitados con la llave) y un libro único
de movimientos de todas las llaves (Movimientos de llaves) — ver el
docstring de app.negocio.llaves para el detalle del modelo.

Las tres tablas no usan PantallaCRUD/Campo (a diferencia de otros
catálogos) porque el Nombre del Tipo se arma solo (no es un campo de
formulario) y el Tipo queda bloqueado al editar — casos puntuales que el
CRUD genérico no cubre. En su lugar, cada sección arma su propia tabla y
sus propios diálogos, siguiendo el mismo patrón que ya usaban Accesos y
Movimientos en la versión anterior de esta pantalla.

Es F18 — asignado por nosotros en la revisión uno por uno con la
clienta: es el único número sin usar entre F16 (Reservas regulares) y
F27 (Ausencias), confirmado con ella.

Formato solapa (revisión uno por uno de esta pantalla): pasó del
`QSplitter` de dos paneles anchos (Tipos+Accesos a la izquierda,
Movimientos a la derecha) a una columna izquierda de ancho fijo con
los diez botones de las tres secciones (sin tablas) y una columna
derecha con las tres tablas apiladas una arriba de la otra — pedido
explícito de la clienta. "Deshacer último movimiento" (que existía
hasta esta revisión, cubría cualquier acción del formulario) se sacó
de la pantalla a pedido de la clienta al reordenar los botones.

Reordenamiento de formularios (Excel de la clienta): esta pantalla deja
de ser un formulario propio del menú y pasa a ser la primera solapa
("Movimientos y tenencias de llaves") de "Llaves y otros conceptos",
junto a las dos solapas de Cargos especiales — mismo criterio ya usado
en el resto de la reorganización: `PantallaLlaves` pasa a `_PanelLlaves`
(solapa desnuda, `objectName="panelSolapa"` en el widget de más afuera,
sin título ni `QTabWidget` propio; conserva su `QScrollArea` interno,
mismo criterio que `_PanelGestorArchivos`/`_PanelCampos` para pantallas
que ya scrolleaban así)."""
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.pantallas.reservas import _opciones_profesional, _SpinMonto, _texto_profesional
from app.gui.widgets.eliminar_tecla import instalar_eliminar_con_tecla
from app.gui.widgets.fecha import aplicar_color_sabado_negro, instalar_flechas_cambian_fecha_completa
from app.gui.widgets.foco import excluir_tabla_del_tab
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.items_tabla import item_numero
from app.gui.widgets.orden_tabla import OrdenTabla, clave_orden_codigo
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.dias import periodo_actual, sumar_meses
from app.negocio.liquidaciones import regenerar_si_corresponde
from app.negocio.listas_editables import opciones_lista
from app.pdf.estilos import clave_orden_unidad
from app.negocio.llaves import (
    agregar_acceso_llave,
    asignar_llave,
    crear_llave,
    devolver_llave,
    ingresar_copias,
    registrar_perdida,
    resumen_stock,
    siguiente_nombre_llave,
    texto_estado_deposito,
)
from app.repositorio.registro import obtener_repositorio

_CATEGORIAS_TODAS = ("R", "A", "B", "E", "X", "C")
# Ronda de validaciones de categoría: "C" no puede tener ningún
# movimiento — se excluye del combo que asigna una llave nueva a un
# profesional (distinto de `_CATEGORIAS_TODAS`, que sigue usando el
# filtro de "Stock de llaves por profesional" sin este descarte: es
# solo un filtro de VISUALIZACIÓN sobre tenencias ya existentes, no una
# acción que pueda crear una nueva).
_CATEGORIAS_CON_LLAVES = ("R", "A", "B", "E", "X")
_DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_ANCHO_BOTON = 280  # "Devolución copia del profesional", el texto más largo de la columna
_FILAS_VISIBLES_TIPOS = 6
_FILAS_VISIBLES_ACCESOS = 3
_PADDING_COLUMNA = 30  # mismo criterio que `novedades._ajustar_columnas`: más aire que el ancho justo
# Orden de "Stock de llaves por profesional" (punto 5 del documento de
# correcciones) — pedido explícito de la clienta, DISTINTO de la
# jerarquía B,R,A,E,X,C que usa `clave_orden_profesional`/`_opciones_
# profesional` para el resto de los selectores del sistema (ahí R va
# antes que A, acá E va antes que A). Categoría C (sin reserva ni llave
# esperable, pero el modelo no lo impide) cae al final, sin entrada
# explícita.
_ORDEN_CATEGORIA_STOCK = {"B": 0, "R": 1, "E": 2, "A": 3, "X": 4}


def _alto_para_filas(tabla: QTableWidget, filas: int) -> int:
    """Alto fijo para que se vean exactamente `filas` filas sin scroll
    (la tabla sigue siendo scrolleable para el resto) — pedido explícito
    de la clienta: Tipos muestra 6, Accesos 3, Movimientos se queda con
    el resto del alto disponible en la pantalla."""
    alto_fila = tabla.verticalHeader().defaultSectionSize()
    alto_header = tabla.horizontalHeader().sizeHint().height()
    return alto_header + alto_fila * filas + 2 * tabla.frameWidth()


def _alto_hasta_primera_fila(titulo: QLabel, tabla: QTableWidget) -> int:
    """Alto desde el techo de la sección (donde arranca su título) hasta
    el comienzo de la primera fila de datos de la tabla, es decir
    salteando el encabezado — pedido explícito de la clienta: el primer
    botón de cada grupo tiene que quedar alineado con el primer
    registro de su tabla, no con el título."""
    return titulo.sizeHint().height() + tabla.horizontalHeader().sizeHint().height() + tabla.frameWidth()


def _alto_hasta_la_tabla(titulo: QLabel) -> int:
    """Alto desde el techo de la sección hasta el borde de ARRIBA de la
    tabla (sin saltear el encabezado) — distinto de `_alto_hasta_
    primera_fila` de arriba. Pedido puntual de la clienta sobre los
    botones de Accesos (punto 5): "que quede a la par del inicio de esa
    tabla", no contra el primer registro como el resto de los grupos de
    esta pantalla."""
    return titulo.sizeHint().height()


def _ajustar_columnas(tabla: QTableWidget, factor: int = 1) -> None:
    """Mismo criterio que `bloques_rigidos._ajustar_columnas`/`novedades.
    _ajustar_columnas`: `resizeColumnsToContents` deja las columnas al
    ancho justo del contenido — se les agrega `_PADDING_COLUMNA` de más a
    cada una. `factor` multiplica ese resultado (Accesos pide el doble,
    pedido explícito de la clienta)."""
    tabla.resizeColumnsToContents()
    for columna in range(tabla.columnCount()):
        tabla.setColumnWidth(columna, (tabla.columnWidth(columna) + _PADDING_COLUMNA) * factor)


def _fecha_larga(iso: str) -> str:
    # Día de la semana ABREVIADO (3 letras) — mismo criterio "ddd dd-MM-
    # yyyy" que ya usa el resto del sistema (Registro de ausencias,
    # Reservas, Configuración general) para cualquier fecha que se
    # muestre en una tabla; acá además angosta la columna "Fecha" de
    # Movimientos (pedido de la clienta de achicar columnas en esa
    # tabla) sin perder el dato del día — antes mostraba el nombre
    # completo ("Lunes"), inconsistente con esa convención.
    d = date.fromisoformat(iso)
    dia = _DIAS_SEMANA[d.weekday()]
    return f"{dia[:3]} {d.strftime('%d-%m-%Y')}"


def _moneda(monto: float) -> str:
    return f"${monto:,.0f}".replace(",", ".")


def _fecha_edit(valor_iso: str | None = None) -> QDateEdit:
    # Punto #1.10: día de la semana abreviado, mismo formato y criterio
    # que el resto del sistema (Registro de ausencias/Reservas/
    # Configuración general) — antes "dd-MM-yyyy" nomás, sin el día.
    campo = QDateEdit()
    campo.setCalendarPopup(True)
    campo.setDisplayFormat("ddd dd-MM-yyyy")
    campo.setLocale(QLocale(QLocale.Language.Spanish))
    aplicar_color_sabado_negro(campo)
    instalar_flechas_cambian_fecha_completa(campo)
    campo.setDate(QDate.fromString(valor_iso, Qt.DateFormat.ISODate) if valor_iso else QDate.currentDate())
    return campo


class _PanelLlaves(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._tipos_actuales: list[sqlite3.Row] = []
        self._accesos_actuales: list[sqlite3.Row] = []
        self._movimientos_actuales: list[sqlite3.Row] = []
        self._armar_ui()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._orden_tipos.reiniciar()
        self._orden_accesos.reiniciar()
        self._orden_movimientos.reiniciar()
        self.actualizar()
        self.boton_nuevo_tipo.setFocus()

    @staticmethod
    def _titulo_seccion(texto: str) -> QLabel:
        """`subtituloCampo` (Nivel 3: mismo tamaño que el texto normal) en
        vez de `subtituloSeccion` (Nivel 2, 15px) — pedido explícito de la
        clienta al revisar esta pantalla: no son solapas reales ni
        necesitan un tamaño distinto del resto del sistema, pero sí
        quedan en negrita (a diferencia del resto de los `subtituloCampo`
        del sistema, que van sin negrita) — pedido puntual de esta
        pantalla, con el `objectName` reutilizado solo por el tamaño."""
        etiqueta = QLabel(texto)
        etiqueta.setObjectName("subtituloCampo")
        etiqueta.setStyleSheet("font-weight: bold;")
        return etiqueta

    @staticmethod
    def _grupo_botones(alto_hasta_primera_fila: int, *botones: QPushButton) -> QWidget:
        """Envuelve un grupo de botones en su propio widget, con ancho fijo
        y sin estirarse — para poder alinearlo por `QGridLayout.addWidget`
        (`Qt.AlignmentFlag.AlignTop`) contra el primer registro de su
        tabla correspondiente (`alto_hasta_primera_fila`, ver
        `_alto_hasta_primera_fila`: salta el título y el encabezado de la
        tabla), en vez de apilar los diez botones de las tres secciones
        seguidos en una sola columna."""
        widget = QWidget()
        columna = QVBoxLayout(widget)
        columna.setContentsMargins(0, 0, 0, 0)
        espaciador = QWidget()
        espaciador.setFixedHeight(alto_hasta_primera_fila)
        columna.addWidget(espaciador)
        for boton in botones:
            boton.setFixedWidth(_ANCHO_BOTON)
            columna.addWidget(boton)
        return widget

    def _armar_ui(self) -> None:
        self.setObjectName("panelSolapa")
        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        contenido = QWidget()
        contenido.setObjectName("panelSolapa")
        grid = QGridLayout(contenido)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(2, 1)  # Movimientos se queda con el resto del alto disponible

        # ------------------------------------------------------- fila 0: Tipos
        panel_tipos = QWidget()
        columna_tipos = QVBoxLayout(panel_tipos)
        columna_tipos.setContentsMargins(0, 0, 0, 0)
        titulo_tipos = self._titulo_seccion("Tipos de llaves")
        columna_tipos.addWidget(titulo_tipos)
        self.tabla_tipos = QTableWidget()
        excluir_tabla_del_tab(self.tabla_tipos)
        self.tabla_tipos.setColumnCount(6)
        self.tabla_tipos.setHorizontalHeaderLabels(
            ["Nombre del tipo de llave", "Tipo", "Depósito actual", "Asignadas", "Disponibles", "Total"]
        )
        self.tabla_tipos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_tipos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_tipos.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_tipos.setColumnWidth(0, 240)
        self.tabla_tipos.setColumnWidth(1, 100)
        self.tabla_tipos.setColumnWidth(2, 150)
        self.tabla_tipos.setColumnWidth(3, 120)
        self.tabla_tipos.setColumnWidth(4, 125)
        self.tabla_tipos.setColumnWidth(5, 95)
        self.tabla_tipos.setFixedHeight(_alto_para_filas(self.tabla_tipos, _FILAS_VISIBLES_TIPOS))
        self.tabla_tipos.itemSelectionChanged.connect(self._actualizar_accesos)
        self.tabla_tipos.itemSelectionChanged.connect(self._actualizar_observacion_tipo)
        self.tabla_tipos.itemSelectionChanged.connect(self._actualizar_botones_movimiento)
        self._orden_tipos = OrdenTabla(self.tabla_tipos, self._actualizar_tipos)
        instalar_eliminar_con_tecla(self.tabla_tipos, self._eliminar_tipo)
        columna_tipos.addWidget(self.tabla_tipos)

        self.campo_observacion_tipo = QLineEdit()
        self.campo_observacion_tipo.editingFinished.connect(self._guardar_observacion_tipo)
        columna_tipos.addWidget(self.campo_observacion_tipo)
        grid.addWidget(panel_tipos, 0, 1)

        self.boton_nuevo_tipo = QPushButton("Nuevo tipo de llave")
        self.boton_nuevo_tipo.setObjectName("botonSecundario")
        self.boton_nuevo_tipo.clicked.connect(self._nuevo_tipo)
        self.boton_editar_tipo = QPushButton("Editar tipo de llave")
        self.boton_editar_tipo.setObjectName("botonSecundario")
        self.boton_editar_tipo.clicked.connect(self._editar_tipo)
        self.boton_eliminar_tipo = QPushButton("Eliminar tipo de llave")
        self.boton_eliminar_tipo.setObjectName("botonSecundario")
        self.boton_eliminar_tipo.clicked.connect(self._eliminar_tipo)
        # Editar/Eliminar arrancan deshabilitados y solo se habilitan con un
        # Tipo seleccionado en la tabla — pedido explícito de la clienta,
        # "ESTO PARA TODO EL SISTEMA".
        self.boton_editar_tipo.setEnabled(False)
        self.boton_eliminar_tipo.setEnabled(False)
        self.tabla_tipos.itemSelectionChanged.connect(self._actualizar_botones_tipo)
        grid.addWidget(
            self._grupo_botones(
                _alto_hasta_primera_fila(titulo_tipos, self.tabla_tipos),
                self.boton_nuevo_tipo, self.boton_editar_tipo, self.boton_eliminar_tipo,
            ),
            0, 0, Qt.AlignmentFlag.AlignTop,
        )

        # ------------------------------------------------------- fila 1: Accesos
        # + "Stock de llaves por profesional" (punto 5 del documento de
        # correcciones, prototipo dentro de esta misma solapa en vez de
        # una solapa nueva): `panel_accesos` pasa de una columna sola a
        # un `QHBoxLayout` con dos mitades — Accesos (achicada hasta el
        # ancho justo de su columna "Nombre", ver `_actualizar_accesos`)
        # a la izquierda, la tabla nueva a la derecha, con `stretch=1`
        # para quedarse con el ancho que Accesos deja libre.
        panel_accesos = QWidget()
        fila_accesos = QHBoxLayout(panel_accesos)
        fila_accesos.setContentsMargins(0, 0, 0, 0)

        # Buscador de profesional (punto 5) y el alto que determina, se
        # construyen ANTES de los dos títulos de esta fila: el combo,
        # editable (`habilitar_busqueda_profesional`), necesita más alto
        # que un `QLabel` solo (20px contra 14px, medido) — fijar ese
        # mismo alto EXPLÍCITO en los dos títulos (`setFixedHeight`, no
        # dejarlo al `sizeHint()` de la fila que lo envuelve) es lo que
        # de verdad alinea el comienzo de las dos tablas: un `QHBoxLayout`
        # agregado con `addLayout` reserva, bajo la plataforma offscreen,
        # un alto mayor al real para la fila que combina label+combo
        # (`sizeHint()` inestable, mismo tipo de hallazgo ya documentado
        # para la leyenda de colores de Reservas/Oferta) — con alto FIJO
        # en los dos títulos, ninguno de los dos depende de ese cálculo.
        self.combo_filtro_stock = QComboBox()
        self.combo_filtro_stock.addItem("Todos los profesionales", None)
        for id_, etiqueta in _opciones_profesional(self.conn, _CATEGORIAS_TODAS):
            self.combo_filtro_stock.addItem(etiqueta, id_)
        habilitar_busqueda_profesional(self.combo_filtro_stock)
        self.combo_filtro_stock.currentIndexChanged.connect(self._actualizar_stock)
        _alto_fila_titulo_stock = self.combo_filtro_stock.sizeHint().height()

        panel_accesos_izq = QWidget()
        columna_accesos = QVBoxLayout(panel_accesos_izq)
        columna_accesos.setContentsMargins(0, 0, 0, 0)
        titulo_accesos = self._titulo_seccion("Accesos habilitados con la llave")
        titulo_accesos.setFixedHeight(_alto_fila_titulo_stock)
        columna_accesos.addWidget(titulo_accesos)
        self.tabla_accesos = QTableWidget()
        excluir_tabla_del_tab(self.tabla_accesos)
        self.tabla_accesos.setColumnCount(4)
        self.tabla_accesos.setHorizontalHeaderLabels(["Localidad", "Edificio", "Unidad", "Nombre"])
        self.tabla_accesos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_accesos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_accesos.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_accesos.setFixedHeight(_alto_para_filas(self.tabla_accesos, _FILAS_VISIBLES_ACCESOS))
        self.tabla_accesos.itemSelectionChanged.connect(self._actualizar_observacion_acceso)
        self.tabla_accesos.itemSelectionChanged.connect(self._actualizar_botones_acceso)
        self._orden_accesos = OrdenTabla(self.tabla_accesos, self._actualizar_accesos)
        instalar_eliminar_con_tecla(self.tabla_accesos, self._eliminar_acceso)
        columna_accesos.addWidget(self.tabla_accesos)

        self.campo_observacion_acceso = QLineEdit()
        self.campo_observacion_acceso.editingFinished.connect(self._guardar_observacion_acceso)
        columna_accesos.addWidget(self.campo_observacion_acceso)
        fila_accesos.addWidget(panel_accesos_izq)

        panel_stock = QWidget()
        columna_stock = QVBoxLayout(panel_stock)
        columna_stock.setContentsMargins(0, 0, 0, 0)
        # El título y el combo van en un `QWidget` propio (no un `QHBoxLayout`
        # agregado directo con `addLayout`) con alto FIJO — mismo motivo
        # que `titulo_accesos.setFixedHeight(...)` más arriba: pedido
        # explícito de la clienta ("ponelo a la par de la etiqueta...
        # apenas termina la misma sin ninguna otra etiqueta adicional").
        fila_titulo_stock = QWidget()
        fila_titulo_stock.setFixedHeight(_alto_fila_titulo_stock)
        layout_titulo_stock = QHBoxLayout(fila_titulo_stock)
        layout_titulo_stock.setContentsMargins(0, 0, 0, 0)
        titulo_stock = self._titulo_seccion("Stock de llaves por profesional")
        layout_titulo_stock.addWidget(titulo_stock)
        layout_titulo_stock.addWidget(self.combo_filtro_stock, stretch=1)
        columna_stock.addWidget(fila_titulo_stock)
        self.tabla_stock = QTableWidget()
        excluir_tabla_del_tab(self.tabla_stock)
        self.tabla_stock.setColumnCount(3)
        self.tabla_stock.setHorizontalHeaderLabels(["Profesional", "Tipo de llave", "Depósito"])
        self.tabla_stock.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_stock.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_stock.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_stock.setFixedHeight(_alto_para_filas(self.tabla_stock, _FILAS_VISIBLES_ACCESOS))
        # Sin `setStretchLastSection`: pedido de la clienta de achicar
        # "Depósito" ("Abonado"/"Bonificado", el texto más largo de la
        # columna) — con el stretch puesto, esta columna se quedaba con
        # TODO el ancho que "Profesional"/"Tipo de llave" dejaban libre
        # en `panel_stock` (confirmado con un script de geometría: hasta
        # 233px para un texto que con el mismo padding que las otras dos
        # columnas — `_ajustar_columnas`, ver `_actualizar_stock` — entra
        # de sobra en ~103px). Sin el stretch, queda al ancho justo como
        # las otras dos, y lo que sobra del panel se queda en blanco a
        # la derecha en vez de hincharla.
        columna_stock.addWidget(self.tabla_stock, stretch=1)
        # `AlignTop` acá es lo que de verdad alinea el comienzo Y el fin
        # de las dos tablas: sin él, `panel_accesos_izq` (más alto, por
        # el campo de observación debajo de su tabla) fuerza a
        # `panel_stock` a estirarse hasta esa misma altura — y, como
        # ningún hijo de `panel_stock` puede crecer de verdad (el título
        # y la tabla tienen alto fijo), Qt reparte ese sobrante como
        # relleno repartido ANTES/ENTRE/DESPUÉS de los dos (medido: título
        # y tabla terminaban bajando parejo, mismo desplazamiento en los
        # dos). Con `AlignTop`, `panel_stock` se queda en su alto natural
        # y el sobrante entero cae DEBAJO suyo, invisible, sin correr
        # nada — confirmado con script de geometría: título y tabla
        # terminan exactos en el mismo píxel que los de "Accesos
        # habilitados con la llave".
        fila_accesos.addWidget(panel_stock, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)

        grid.addWidget(panel_accesos, 1, 1)

        self.boton_agregar_acceso = QPushButton("Agregar acceso de llave")
        self.boton_agregar_acceso.setObjectName("botonSecundario")
        self.boton_agregar_acceso.clicked.connect(self._agregar_acceso)
        self.boton_eliminar_acceso = QPushButton("Eliminar acceso de llave")
        self.boton_eliminar_acceso.setObjectName("botonSecundario")
        self.boton_eliminar_acceso.clicked.connect(self._eliminar_acceso)
        grupo_accesos = self._grupo_botones(
            _alto_hasta_la_tabla(titulo_accesos),
            self.boton_agregar_acceso, self.boton_eliminar_acceso,
        )
        grid.addWidget(grupo_accesos, 1, 0, Qt.AlignmentFlag.AlignTop)

        # ------------------------------------------------------- fila 2: Movimientos
        panel_movimientos = QWidget()
        columna_movimientos = QVBoxLayout(panel_movimientos)
        columna_movimientos.setContentsMargins(0, 0, 0, 0)
        titulo_movimientos = self._titulo_seccion("Movimientos de llaves")
        columna_movimientos.addWidget(titulo_movimientos)
        self.tabla_movimientos = QTableWidget()
        excluir_tabla_del_tab(self.tabla_movimientos)
        self.tabla_movimientos.setColumnCount(8)
        self.tabla_movimientos.setHorizontalHeaderLabels(
            [
                # "Dep. cobrado"/"Dep. reintegrado" (antes "Depósito
                # cobrado"/"Depósito reintegrado"): pedido de la clienta
                # de achicar columnas en esta tabla — mismo significado,
                # abreviado, para que el título deje de ser lo que fija
                # el ancho mínimo de estas dos columnas.
                "Fecha", "Movimiento", "Profesional", "Tipo de llave", "Cantidad",
                "Dep. cobrado", "Dep. reintegrado", "Observación",
            ]
        )
        self.tabla_movimientos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_movimientos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_movimientos.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_movimientos.itemSelectionChanged.connect(self._actualizar_observacion_movimiento)
        self.tabla_movimientos.itemSelectionChanged.connect(self._actualizar_botones_movimiento)
        self._orden_movimientos = OrdenTabla(self.tabla_movimientos, self._actualizar_movimientos)
        columna_movimientos.addWidget(self.tabla_movimientos, stretch=1)

        self.campo_observacion_movimiento = QLineEdit()
        self.campo_observacion_movimiento.editingFinished.connect(self._guardar_observacion_movimiento)
        columna_movimientos.addWidget(self.campo_observacion_movimiento)
        grid.addWidget(panel_movimientos, 2, 1)

        self.boton_ingresar = QPushButton("Ingresar copia al stock")
        self.boton_ingresar.setObjectName("botonSecundario")
        self.boton_ingresar.clicked.connect(self._ingresar_copia)
        self.boton_perdida = QPushButton("Registrar pérdida")
        self.boton_perdida.setObjectName("botonSecundario")
        self.boton_perdida.clicked.connect(self._registrar_perdida)
        self.boton_devolver = QPushButton("Devolución copia del profesional")
        self.boton_devolver.setObjectName("botonSecundario")
        self.boton_devolver.clicked.connect(self._registrar_devolucion)
        self.boton_asignar = QPushButton("Asignar copia a profesional")
        self.boton_asignar.setObjectName("botonPrimario")
        self.boton_asignar.clicked.connect(self._asignar)
        grid.addWidget(
            self._grupo_botones(
                _alto_hasta_primera_fila(titulo_movimientos, self.tabla_movimientos),
                self.boton_ingresar, self.boton_perdida, self.boton_devolver, self.boton_asignar,
            ),
            2, 0, Qt.AlignmentFlag.AlignTop,
        )

        scroll.setWidget(contenido)
        layout_externo.addWidget(scroll)

        self._foco = instalar_enter_avanza_foco([
            self.campo_observacion_tipo, self.boton_nuevo_tipo, self.boton_editar_tipo, self.boton_eliminar_tipo,
            self.campo_observacion_acceso, self.boton_agregar_acceso, self.boton_eliminar_acceso,
            self.combo_filtro_stock,
            self.campo_observacion_movimiento,
            self.boton_ingresar, self.boton_perdida, self.boton_devolver, self.boton_asignar,
        ], parent=self)

        self.actualizar()

    def actualizar(self) -> None:
        self._actualizar_tipos()
        self._actualizar_movimientos()

    # ------------------------------------------------------------- tipos

    def _tipo_seleccionado(self) -> sqlite3.Row | None:
        filas = self.tabla_tipos.selectionModel().selectedRows()
        if not filas:
            return None
        return self._tipos_actuales[filas[0].row()]

    @staticmethod
    def _clave_orden_tipos(columna: int):
        claves = {
            0: lambda par: par[0]["Nombre"] or "",
            1: lambda par: par[0]["Tipo"] or "",
            2: lambda par: par[0]["ValorDepositoActual"] or 0,
            3: lambda par: par[1]["asignadas"],
            4: lambda par: par[1]["disponibles"],
            5: lambda par: par[1]["existentes"],
        }
        return claves[columna]

    def _actualizar_tipos(self) -> None:
        tipo_seleccionado_id = self._tipo_seleccionado()["IdLlave"] if self._tipo_seleccionado() else None
        tipos = obtener_repositorio(self.conn, "Llave").listar()
        filas = [(t, resumen_stock(self.conn, t["IdLlave"])) for t in tipos]
        if self._orden_tipos.columna is not None:
            filas.sort(key=self._clave_orden_tipos(self._orden_tipos.columna), reverse=not self._orden_tipos.ascendente)
        else:
            filas.sort(key=lambda par: par[0]["Nombre"] or "")
        self._tipos_actuales = [t for t, _r in filas]

        self.tabla_tipos.setRowCount(len(filas))
        fila_a_reseleccionar = None
        for fila_idx, (t, resumen) in enumerate(filas):
            self.tabla_tipos.setItem(fila_idx, 0, QTableWidgetItem(t["Nombre"]))
            self.tabla_tipos.setItem(fila_idx, 1, QTableWidgetItem(t["Tipo"]))
            self.tabla_tipos.setItem(fila_idx, 2, item_numero(_moneda(t["ValorDepositoActual"])))
            for col, clave in ((3, "asignadas"), (4, "disponibles"), (5, "existentes")):
                self.tabla_tipos.setItem(fila_idx, col, item_numero(str(resumen[clave])))
            if t["IdLlave"] == tipo_seleccionado_id:
                fila_a_reseleccionar = fila_idx
        if fila_a_reseleccionar is not None:
            self.tabla_tipos.selectRow(fila_a_reseleccionar)
        else:
            self._actualizar_accesos()
            self._actualizar_observacion_tipo()
            self._actualizar_botones_tipo()
            self._actualizar_botones_movimiento()

    def _actualizar_botones_tipo(self) -> None:
        hay_seleccion = self._tipo_seleccionado() is not None
        self.boton_editar_tipo.setEnabled(hay_seleccion)
        self.boton_eliminar_tipo.setEnabled(hay_seleccion)

    def _actualizar_observacion_tipo(self) -> None:
        tipo = self._tipo_seleccionado()
        self.campo_observacion_tipo.setEnabled(tipo is not None)
        self.campo_observacion_tipo.setText(tipo["Observacion"] or "" if tipo else "")

    def _guardar_observacion_tipo(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            return
        texto = self.campo_observacion_tipo.text().strip() or None
        if texto == (tipo["Observacion"] or None):
            return
        obtener_repositorio(self.conn, "Llave").actualizar(tipo["IdLlave"], Observacion=texto)
        self.conn.commit()

    def _nuevo_tipo(self) -> None:
        dialogo = _DialogoTipo(self.conn, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        valores = dialogo.valores()
        id_nuevo = crear_llave(
            self.conn, tipo=valores["tipo"], valor_deposito_actual=valores["valor_deposito_actual"],
            observacion=valores["observacion"], id_edificio=valores["id_edificio"],
        )
        if not valores["activo"]:
            obtener_repositorio(self.conn, "Llave").actualizar(id_nuevo, Activo=0)
        self.conn.commit()
        self._actualizar_tipos()
        self.boton_nuevo_tipo.setFocus()

    def _editar_tipo(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            QMessageBox.information(self, "Editar", "Seleccioná un Tipo de llave para editar.")
            return
        dialogo = _DialogoTipo(self.conn, self, registro=tipo)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        valores = dialogo.valores()
        obtener_repositorio(self.conn, "Llave").actualizar(
            tipo["IdLlave"], ValorDepositoActual=valores["valor_deposito_actual"],
            Observacion=valores["observacion"], Activo=int(valores["activo"]),
        )
        self.conn.commit()
        self._actualizar_tipos()
        self.boton_nuevo_tipo.setFocus()

    def _eliminar_tipo(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            QMessageBox.information(self, "Eliminar", "Seleccioná un Tipo de llave para eliminar.")
            return
        confirmacion = QMessageBox.question(self, "Eliminar", "¿Confirmás eliminar el Tipo de llave seleccionado?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        try:
            obtener_repositorio(self.conn, "Llave").eliminar(tipo["IdLlave"])
        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self, "Eliminar",
                "No se puede eliminar: este Tipo de llave tiene accesos o movimientos registrados.",
            )
            return
        self.conn.commit()
        self._actualizar_tipos()
        self.boton_nuevo_tipo.setFocus()

    # ----------------------------------------------------------- accesos

    def _accesos(self, id_llave: int) -> list[sqlite3.Row]:
        filas = self.conn.execute(
            """
            SELECT la.*, e.Nombre AS NombreEdificio, loc.Localidad AS Localidad, u.Departamento
            FROM LlaveAcceso la
            JOIN Edificio e ON e.IdEdificio = la.IdEdificio
            LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad
            LEFT JOIN Unidad u ON u.IdUnidad = la.IdUnidad
            WHERE la.IdLlave = ? ORDER BY loc.Localidad, e.Nombre
            """,
            (id_llave,),
        ).fetchall()
        # El orden por Unidad (piso + letra) no es expresable en el ORDER
        # BY de SQL — se aplica en Python, mismo criterio que el resto del
        # sistema (`clave_orden_unidad`), sin perder el agrupamiento por
        # Localidad/Edificio que ya trae ordenado la consulta.
        return sorted(
            filas,
            key=lambda a: (a["Localidad"] or "", a["NombreEdificio"] or "", clave_orden_unidad(a["Departamento"] or "")),
        )

    def _acceso_seleccionado(self) -> sqlite3.Row | None:
        filas = self.tabla_accesos.selectionModel().selectedRows()
        if not filas:
            return None
        return self._accesos_actuales[filas[0].row()]

    @staticmethod
    def _clave_orden_accesos(columna: int):
        claves = {
            0: lambda a: a["Localidad"] or "",
            1: lambda a: a["NombreEdificio"] or "",
            # Orden por piso (PB, EP, después ascendente numérico) + letra a
            # igual piso — pedido general de la clienta (`clave_orden_unidad`).
            2: lambda a: clave_orden_unidad(a["Departamento"] or ""),
            3: lambda a: a["Nombre"] or "",
        }
        return claves[columna]

    def _actualizar_accesos(self) -> None:
        tipo = self._tipo_seleccionado()
        self.boton_agregar_acceso.setEnabled(tipo is not None)
        self._accesos_actuales = []
        self.tabla_accesos.setRowCount(0)
        if tipo is not None:
            accesos = self._accesos(tipo["IdLlave"])
            if self._orden_accesos.columna is not None:
                accesos = sorted(
                    accesos, key=self._clave_orden_accesos(self._orden_accesos.columna),
                    reverse=not self._orden_accesos.ascendente,
                )
            self._accesos_actuales = accesos
            self.tabla_accesos.setRowCount(len(accesos))
            for fila_idx, a in enumerate(accesos):
                self.tabla_accesos.setItem(fila_idx, 0, QTableWidgetItem(a["Localidad"] or ""))
                self.tabla_accesos.setItem(fila_idx, 1, QTableWidgetItem(a["NombreEdificio"]))
                self.tabla_accesos.setItem(fila_idx, 2, QTableWidgetItem(a["Departamento"] or "Todas"))
                self.tabla_accesos.setItem(fila_idx, 3, QTableWidgetItem(a["Nombre"] or ""))
        # `_ajustar_columnas` y el ancho fijo corren SIEMPRE (con o sin
        # Tipo seleccionado, con o sin filas) — punto 5: "la tabla del
        # medio la podés acortar hasta el borde donde termina la columna
        # 'Nombre'", para dejarle ese ancho libre a "Stock de llaves por
        # profesional" de al lado. `factor` vuelve a 1 (el doble ancho de
        # una ronda anterior, "Accesos pide directamente el DOBLE de
        # ancho", queda superado por este pedido nuevo y más específico:
        # "acortar", no agrandar).
        _ajustar_columnas(self.tabla_accesos, factor=1)
        ancho = sum(self.tabla_accesos.columnWidth(c) for c in range(4)) + 2 * self.tabla_accesos.frameWidth()
        self.tabla_accesos.setFixedWidth(ancho)
        self._actualizar_observacion_acceso()
        self._actualizar_botones_acceso()

    def _actualizar_botones_acceso(self) -> None:
        # "Eliminar acceso de llave" solo se habilita con un acceso
        # seleccionado en la tabla (pedido explícito de la clienta, "ESTO
        # PARA TODO EL SISTEMA") — antes se habilitaba con solo que
        # hubiera algún acceso cargado, sin importar la selección.
        self.boton_eliminar_acceso.setEnabled(self._acceso_seleccionado() is not None)

    def _actualizar_observacion_acceso(self) -> None:
        acceso = self._acceso_seleccionado()
        self.campo_observacion_acceso.setEnabled(acceso is not None)
        self.campo_observacion_acceso.setText(acceso["Observacion"] or "" if acceso else "")

    def _guardar_observacion_acceso(self) -> None:
        acceso = self._acceso_seleccionado()
        if acceso is None:
            return
        texto = self.campo_observacion_acceso.text().strip() or None
        if texto == (acceso["Observacion"] or None):
            return
        obtener_repositorio(self.conn, "LlaveAcceso").actualizar(acceso["IdLlaveAcceso"], Observacion=texto)
        self.conn.commit()

    def _agregar_acceso(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            return
        dialogo = _DialogoAcceso(self.conn, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            agregar_acceso_llave(self.conn, id_llave=tipo["IdLlave"], **dialogo.valores())
        except ValueError as error:
            QMessageBox.warning(self, "Agregar acceso", str(error))
            return
        self.conn.commit()
        self._actualizar_accesos()
        self.boton_nuevo_tipo.setFocus()

    def _eliminar_acceso(self) -> None:
        acceso = self._acceso_seleccionado()
        if acceso is None:
            QMessageBox.information(self, "Eliminar acceso", "Seleccioná un acceso para eliminar.")
            return
        obtener_repositorio(self.conn, "LlaveAcceso").eliminar(acceso["IdLlaveAcceso"])
        self.conn.commit()
        self._actualizar_accesos()
        self.boton_nuevo_tipo.setFocus()

    # ------------------------------------------------------- movimientos

    def _movimiento_seleccionado(self) -> sqlite3.Row | None:
        filas = self.tabla_movimientos.selectionModel().selectedRows()
        if not filas:
            return None
        return self._movimientos_actuales[filas[0].row()]

    @staticmethod
    def _clave_orden_movimientos(columna: int):
        claves = {
            0: lambda m: m["Fecha"] or "",
            1: lambda m: m["Tipo"] or "",
            2: lambda m: clave_orden_codigo(m["_texto_profesional"]),
            3: lambda m: m["_nombre_llave"],
            4: lambda m: m["Cantidad"],
            5: lambda m: m["MontoCobrado"] or 0,
            6: lambda m: m["MontoReintegrado"] or 0,
            7: lambda m: m["Observacion"] or "",
        }
        return claves[columna]

    def _asignaciones_cerradas(self) -> set[int]:
        cerradas = {
            f["IdAsignacion"] for f in self.conn.execute(
                "SELECT IdAsignacion FROM LlaveMovimiento WHERE IdAsignacion IS NOT NULL"
            ).fetchall()
        }
        return cerradas

    def _actualizar_movimientos(self) -> None:
        repo_prof = obtener_repositorio(self.conn, "Profesional")
        repo_llave = obtener_repositorio(self.conn, "Llave")
        movimientos = obtener_repositorio(self.conn, "LlaveMovimiento").listar()
        enriquecidos = []
        for m in movimientos:
            profesional = repo_prof.obtener(m["IdProfesional"]) if m["IdProfesional"] else None
            llave = repo_llave.obtener(m["IdLlave"])
            enriquecidos.append({
                **dict(m), "_texto_profesional": _texto_profesional(profesional) if profesional else "",
                "_nombre_llave": llave["Nombre"] if llave else "",
                "_categoria_profesional": profesional["CategoriaProfesional"] if profesional else "",
            })
        if self._orden_movimientos.columna is not None:
            enriquecidos.sort(
                key=self._clave_orden_movimientos(self._orden_movimientos.columna),
                reverse=not self._orden_movimientos.ascendente,
            )
        else:
            # Fecha de más nuevo a más viejo, luego Movimiento A-Z, luego Profesional A-Z (sort estable:
            # se ordena primero por la clave menos significativa).
            enriquecidos.sort(key=lambda m: clave_orden_codigo(m["_texto_profesional"]))
            enriquecidos.sort(key=lambda m: m["Tipo"] or "")
            enriquecidos.sort(key=lambda m: m["Fecha"] or "", reverse=True)
        self._movimientos_actuales = enriquecidos

        self.tabla_movimientos.setRowCount(len(enriquecidos))
        for fila_idx, m in enumerate(enriquecidos):
            self.tabla_movimientos.setItem(fila_idx, 0, QTableWidgetItem(_fecha_larga(m["Fecha"])))
            self.tabla_movimientos.setItem(fila_idx, 1, QTableWidgetItem(m["Tipo"]))
            self.tabla_movimientos.setItem(fila_idx, 2, QTableWidgetItem(m["_texto_profesional"]))
            self.tabla_movimientos.setItem(fila_idx, 3, QTableWidgetItem(m["_nombre_llave"]))
            self.tabla_movimientos.setItem(fila_idx, 4, item_numero(str(m["Cantidad"])))
            cobrado = _moneda(m["MontoCobrado"]) if m["Tipo"] == "Asignación" and m["DepositoCobrado"] else ""
            self.tabla_movimientos.setItem(fila_idx, 5, item_numero(cobrado))
            if m["Tipo"] == "Pérdida":
                self.tabla_movimientos.setItem(fila_idx, 6, QTableWidgetItem("No corresponde"))
            else:
                reintegrado = _moneda(m["MontoReintegrado"]) if m["Tipo"] == "Devolución" and m["DepositoReintegrado"] else ""
                self.tabla_movimientos.setItem(fila_idx, 6, item_numero(reintegrado))
            self.tabla_movimientos.setItem(fila_idx, 7, QTableWidgetItem(m["Observacion"] or ""))
        self.tabla_movimientos.resizeColumnsToContents()
        if self.tabla_movimientos.columnWidth(2) < 180:
            self.tabla_movimientos.setColumnWidth(2, 180)
        ancho_deposito = max(self.tabla_movimientos.columnWidth(5), self.tabla_movimientos.columnWidth(6))
        self.tabla_movimientos.setColumnWidth(5, ancho_deposito)
        self.tabla_movimientos.setColumnWidth(6, ancho_deposito)
        self._actualizar_observacion_movimiento()
        self._actualizar_botones_movimiento()
        self._actualizar_stock()

    # --------------------------------------------- stock por profesional

    @staticmethod
    def _clave_orden_stock(m: dict) -> tuple:
        return (
            _ORDEN_CATEGORIA_STOCK.get(m["_categoria_profesional"], len(_ORDEN_CATEGORIA_STOCK)),
            clave_orden_codigo(m["_texto_profesional"]),
        )

    def _actualizar_stock(self) -> None:
        """"Stock de llaves por profesional" (punto 5): una fila por cada
        Asignación todavía ABIERTA (sin Devolución/Pérdida que la
        cierre) — reusa `self._movimientos_actuales`, ya enriquecido por
        `_actualizar_movimientos`, sin repetir la consulta. Filtrable por
        `combo_filtro_stock`; orden fijo (categoría B,R,E,A,X, después
        código natural), no por click de encabezado."""
        id_filtro = self.combo_filtro_stock.currentData()
        cerradas = self._asignaciones_cerradas()
        filas = [
            m for m in self._movimientos_actuales
            if m["Tipo"] == "Asignación" and m["IdMovimiento"] not in cerradas
            and (id_filtro is None or m["IdProfesional"] == id_filtro)
        ]
        filas.sort(key=self._clave_orden_stock)
        self.tabla_stock.setRowCount(len(filas))
        for fila_idx, m in enumerate(filas):
            self.tabla_stock.setItem(fila_idx, 0, QTableWidgetItem(m["_texto_profesional"]))
            self.tabla_stock.setItem(fila_idx, 1, QTableWidgetItem(m["_nombre_llave"]))
            self.tabla_stock.setItem(fila_idx, 2, QTableWidgetItem(texto_estado_deposito(bool(m["DepositoCobrado"]))))
        _ajustar_columnas(self.tabla_stock)

    def _actualizar_observacion_movimiento(self) -> None:
        movimiento = self._movimiento_seleccionado()
        self.campo_observacion_movimiento.setEnabled(movimiento is not None)
        self.campo_observacion_movimiento.setText((movimiento["Observacion"] or "") if movimiento else "")

    def _guardar_observacion_movimiento(self) -> None:
        movimiento = self._movimiento_seleccionado()
        if movimiento is None:
            return
        texto = self.campo_observacion_movimiento.text().strip() or None
        if texto == (movimiento["Observacion"] or None):
            return
        obtener_repositorio(self.conn, "LlaveMovimiento").actualizar(movimiento["IdMovimiento"], Observacion=texto)
        self.conn.commit()

    def _asignacion_abierta_seleccionada(self) -> bool:
        movimiento = self._movimiento_seleccionado()
        return (
            movimiento is not None and movimiento["Tipo"] == "Asignación"
            and movimiento["IdMovimiento"] not in self._asignaciones_cerradas()
        )

    def _actualizar_botones_movimiento(self) -> None:
        tipo = self._tipo_seleccionado()
        # "Ingresar copia al stock"/"Asignar copia a profesional" operan
        # sobre el Tipo de llave seleccionado — sin selección, no hay nada
        # sobre qué actuar (pedido explícito de la clienta, "ESTO PARA TODO
        # EL SISTEMA").
        self.boton_ingresar.setEnabled(tipo is not None)
        self.boton_asignar.setEnabled(tipo is not None)
        es_asignacion_abierta = self._asignacion_abierta_seleccionada()
        self.boton_devolver.setEnabled(es_asignacion_abierta)
        # "Registrar pérdida…" cubre dos casos: cerrar la asignación abierta
        # seleccionada, o (sin ninguna seleccionada) dar de baja stock
        # disponible del Tipo seleccionado que se perdió antes de asignarse.
        disponibles_tipo = resumen_stock(self.conn, tipo["IdLlave"])["disponibles"] if tipo else 0
        self.boton_perdida.setEnabled(es_asignacion_abierta or disponibles_tipo > 0)

    def _ingresar_copia(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            QMessageBox.information(self, "Ingresar copia", "Seleccioná un Tipo de llave.")
            return
        dialogo = _DialogoIngreso(tipo, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        ingresar_copias(self.conn, id_llave=tipo["IdLlave"], **dialogo.valores())
        self.conn.commit()
        self._actualizar_tipos()
        self._actualizar_movimientos()
        self.boton_nuevo_tipo.setFocus()

    def _asignar(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            QMessageBox.information(self, "Asignar", "Seleccioná un Tipo de llave.")
            return
        disponibles = resumen_stock(self.conn, tipo["IdLlave"])["disponibles"]
        if disponibles <= 0:
            QMessageBox.warning(self, "Asignar", f"No hay copias disponibles de {tipo['Nombre']} para asignar.")
            return
        dialogo = _DialogoAsignar(self.conn, tipo, disponibles, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        valores = dialogo.valores()
        try:
            asignar_llave(self.conn, id_llave=tipo["IdLlave"], **valores)
        except ValueError as error:
            QMessageBox.warning(self, "Asignar", str(error))
            return
        self.conn.commit()
        # Punto #1.9: mismo criterio que Cargos especiales — un depósito
        # cobrado, imputado al período en curso, regenera y marca no
        # enviada la liquidación de ese profesional si ya estaba emitida.
        if valores["cobrar_deposito"] and valores["monto_cobrado"] and valores["periodo_imputado"] == periodo_actual(self.conn):
            regenerar_si_corresponde(self.conn, id_profesional=valores["id_profesional"], periodo=valores["periodo_imputado"])
            self.conn.commit()
        self._actualizar_tipos()
        self._actualizar_movimientos()
        self.boton_nuevo_tipo.setFocus()
        QMessageBox.information(self, "Asignar", "Llave asignada con éxito.")

    def _registrar_devolucion(self) -> None:
        movimiento = self._movimiento_seleccionado()
        if movimiento is None:
            return
        dialogo = _DialogoDevolucion(self.conn, movimiento, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        valores = dialogo.valores()
        try:
            devolver_llave(self.conn, movimiento["IdMovimiento"], **valores)
        except ValueError as error:
            QMessageBox.warning(self, "Registrar devolución", str(error))
            return
        self.conn.commit()
        if (
            valores["reintegrar_deposito"] and valores["monto_reintegrado"]
            and valores["periodo_imputado"] == periodo_actual(self.conn)
        ):
            regenerar_si_corresponde(
                self.conn, id_profesional=movimiento["IdProfesional"], periodo=valores["periodo_imputado"],
            )
            self.conn.commit()
        self._actualizar_tipos()
        self._actualizar_movimientos()
        self.boton_nuevo_tipo.setFocus()
        QMessageBox.information(self, "Registrar devolución", "Devolución registrada con éxito.")

    def _registrar_perdida(self) -> None:
        if self._asignacion_abierta_seleccionada():
            movimiento = self._movimiento_seleccionado()
            dialogo = _DialogoPerdida(movimiento, self)
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                registrar_perdida(self.conn, id_asignacion=movimiento["IdMovimiento"], **dialogo.valores())
            except ValueError as error:
                QMessageBox.warning(self, "Registrar pérdida", str(error))
                return
        else:
            tipo = self._tipo_seleccionado()
            if tipo is None:
                QMessageBox.information(
                    self, "Registrar pérdida", "Seleccioná una asignación abierta o un Tipo de llave.",
                )
                return
            disponibles = resumen_stock(self.conn, tipo["IdLlave"])["disponibles"]
            if disponibles <= 0:
                QMessageBox.warning(
                    self, "Registrar pérdida", f"No hay copias disponibles de {tipo['Nombre']} para dar de baja.",
                )
                return
            dialogo = _DialogoPerdidaStock(tipo, disponibles, self)
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                registrar_perdida(self.conn, id_llave=tipo["IdLlave"], **dialogo.valores())
            except ValueError as error:
                QMessageBox.warning(self, "Registrar pérdida", str(error))
                return
        self.conn.commit()
        self._actualizar_tipos()
        self._actualizar_movimientos()
        self.boton_nuevo_tipo.setFocus()
        QMessageBox.information(self, "Registrar pérdida", "Pérdida registrada con éxito.")


class _DialogoTipo(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None, registro: sqlite3.Row | None = None):
        super().__init__(parent)
        self.conn = conn
        self.registro = registro
        self.setWindowTitle("Editar Tipo de llave" if registro else "Nuevo Tipo de llave")
        layout = QFormLayout(self)

        self.combo_tipo = QComboBox()
        for valor, etiqueta in opciones_lista("TipoLlave")(conn):
            self.combo_tipo.addItem(etiqueta, valor)
        # Edificio al que corresponde esta llave, SOLO para Tipo="Edificio"
        # — pedido explícito de la clienta: el nombre pasa a sumar el
        # edificio elegido ("Tipo llave E1 - Ramos 1"). Queda deshabilitado
        # para los demás Tipos y siempre al editar (el Tipo ya está
        # bloqueado, elegir el edificio es solo para el alta).
        self.combo_edificio = QComboBox()
        self.combo_edificio.addItem("(elegí un edificio)", None)
        for f in conn.execute("SELECT IdEdificio, Nombre FROM Edificio ORDER BY Nombre"):
            self.combo_edificio.addItem(f["Nombre"], f["IdEdificio"])
        self.etiqueta_nombre = QLabel()
        if registro is None:
            self.combo_tipo.currentIndexChanged.connect(self._actualizar_previsualizacion)
            self.combo_edificio.currentIndexChanged.connect(self._actualizar_previsualizacion)
        else:
            indice = self.combo_tipo.findData(registro["Tipo"])
            if indice >= 0:
                self.combo_tipo.setCurrentIndex(indice)
            self.combo_tipo.setEnabled(False)
            self.combo_edificio.setEnabled(False)
            self.etiqueta_nombre.setText(registro["Nombre"])
            self.etiqueta_nombre.setStyleSheet("font-weight: bold;")
        layout.addRow("Tipo", self.combo_tipo)
        layout.addRow("Edificio", self.combo_edificio)
        layout.addRow("Nombre del tipo de llave", self.etiqueta_nombre)
        if registro is not None:
            ayuda = QLabel("No se puede cambiar: si cambia, el nombre dejaría de tener sentido.")
            ayuda.setStyleSheet("color: #666; font-size: 11px;")
            layout.addRow("", ayuda)

        self.spin_deposito = _SpinMonto()
        self.spin_deposito.setMaximum(10_000_000)
        self.spin_deposito.setValue(registro["ValorDepositoActual"] if registro else 0)
        layout.addRow("Depósito actual", self.spin_deposito)

        self.campo_observacion = QLineEdit(registro["Observacion"] if registro and registro["Observacion"] else "")
        layout.addRow("Observación", self.campo_observacion)

        self.casilla_activo = QCheckBox("Activo")
        self.casilla_activo.setChecked(bool(registro["Activo"]) if registro else True)
        layout.addRow(self.casilla_activo)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        orden = [
            self.combo_tipo, self.combo_edificio, self.spin_deposito, self.campo_observacion,
            self.casilla_activo, boton_ok, boton_cancelar,
        ]
        self._foco = instalar_enter_avanza_foco(orden, parent=self)
        if registro is None:
            self._actualizar_previsualizacion()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.combo_tipo.setFocus()

    def _actualizar_previsualizacion(self) -> None:
        tipo = self.combo_tipo.currentData()
        es_edificio = tipo == "Edificio"
        self.combo_edificio.setEnabled(es_edificio and self.registro is None)
        id_edificio = self.combo_edificio.currentData() if es_edificio else None
        self.etiqueta_nombre.setText(
            f"Se va a llamar: {siguiente_nombre_llave(self.conn, tipo, id_edificio=id_edificio)}"
        )

    def accept(self) -> None:  # noqa: N802
        if (
            self.registro is None and self.combo_tipo.currentData() == "Edificio"
            and self.combo_edificio.currentData() is None
        ):
            QMessageBox.warning(self, "Nuevo Tipo de llave", "Elegí el edificio para este Tipo de llave.")
            return
        super().accept()

    def valores(self) -> dict:
        tipo = self.combo_tipo.currentData()
        return {
            "tipo": tipo,
            "id_edificio": self.combo_edificio.currentData() if tipo == "Edificio" else None,
            "valor_deposito_actual": self.spin_deposito.value(),
            "observacion": self.campo_observacion.text().strip() or None,
            "activo": self.casilla_activo.isChecked(),
        }


class _DialogoAcceso(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Agregar acceso")
        layout = QFormLayout(self)

        self.combo_edificio = QComboBox()
        for f in conn.execute("SELECT IdEdificio, Nombre FROM Edificio ORDER BY Nombre"):
            self.combo_edificio.addItem(f["Nombre"], f["IdEdificio"])
        self.combo_edificio.currentIndexChanged.connect(self._cargar_unidades)
        layout.addRow("Edificio", self.combo_edificio)

        self.combo_unidad = QComboBox()
        layout.addRow("Unidad", self.combo_unidad)
        self._cargar_unidades()

        self.campo_nombre = QLineEdit()
        self.campo_nombre.setPlaceholderText("Nombre del acceso (opcional)")
        layout.addRow("Nombre", self.campo_nombre)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.combo_edificio, self.combo_unidad, self.campo_nombre, boton_ok, boton_cancelar], parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.combo_edificio.setFocus()

    def _cargar_unidades(self) -> None:
        self.combo_unidad.clear()
        self.combo_unidad.addItem("Todas las unidades del edificio", None)
        id_edificio = self.combo_edificio.currentData()
        if id_edificio is None:
            return
        filas = self.conn.execute(
            "SELECT IdUnidad, Departamento FROM Unidad WHERE IdEdificio = ?", (id_edificio,)
        ).fetchall()
        # Orden PB/EP/piso ascendente (ver CLAUDE.md "Orden de Unidad"), no
        # alfabético — mismo criterio ya usado en reservas.py/catalogos.py.
        for f in sorted(filas, key=lambda f: clave_orden_unidad(f["Departamento"])):
            self.combo_unidad.addItem(f["Departamento"], f["IdUnidad"])

    def valores(self) -> dict:
        return {
            "id_edificio": self.combo_edificio.currentData(),
            "id_unidad": self.combo_unidad.currentData(),
            "nombre": self.campo_nombre.text().strip() or None,
        }


class _DialogoIngreso(QDialog):
    def __init__(self, tipo: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ingresar copia")
        layout = QFormLayout(self)
        layout.addRow(QLabel(tipo["Nombre"]))

        self.campo_fecha = _fecha_edit()
        layout.addRow("Fecha", self.campo_fecha)

        self.spin_cantidad = QSpinBox()
        self.spin_cantidad.setMinimum(1)
        self.spin_cantidad.setMaximum(500)
        self.spin_cantidad.setValue(1)
        layout.addRow("Cantidad", self.spin_cantidad)
        ayuda = QLabel("Se cargan esa cantidad de copias de una sola vez.")
        ayuda.setStyleSheet("color: #666; font-size: 11px;")
        layout.addRow("", ayuda)

        self.campo_observacion = QLineEdit()
        layout.addRow("Comentarios", self.campo_observacion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.campo_fecha, self.spin_cantidad, self.campo_observacion, boton_ok, boton_cancelar], parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.campo_fecha.setFocus()

    def valores(self) -> dict:
        return {
            "cantidad": self.spin_cantidad.value(),
            "fecha": self.campo_fecha.date().toString(Qt.DateFormat.ISODate),
            "observacion": self.campo_observacion.text().strip() or None,
        }


class _DialogoAsignar(QDialog):
    def __init__(self, conn: sqlite3.Connection, tipo: sqlite3.Row, disponibles: int, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Asignar")
        layout = QFormLayout(self)
        copia_o_copias = "copia disponible" if disponibles == 1 else "copias disponibles"
        layout.addRow(QLabel(f"{tipo['Nombre']}  —  {disponibles} {copia_o_copias}"))

        self.combo_profesional = QComboBox()
        for id_, etiqueta in _opciones_profesional(conn, _CATEGORIAS_CON_LLAVES):
            self.combo_profesional.addItem(etiqueta, id_)
        habilitar_busqueda_profesional(self.combo_profesional)
        layout.addRow("Profesional", self.combo_profesional)

        self.campo_fecha = _fecha_edit()
        layout.addRow("Fecha", self.campo_fecha)

        # Selector explícito (en vez de un checkbox "Cobrar depósito",
        # fácil de dejar sin tocar por descuido) — pedido de la clienta:
        # "que me memorice también qué depósito les cobro y qué les
        # bonifico" (punto 4 del documento de correcciones). Arranca en
        # "Bonificado" (mismo default que tenía el checkbox sin tildar).
        self.combo_deposito = QComboBox()
        self.combo_deposito.addItem("Depósito bonificado (no se cobra nada)", "bonificado")
        self.combo_deposito.addItem("Depósito abonado (se cobra el monto)", "abonado")
        layout.addRow("Depósito", self.combo_deposito)
        self.spin_monto = _SpinMonto()
        self.spin_monto.setMaximum(10_000_000)
        self.spin_monto.setValue(tipo["ValorDepositoActual"] or 0)
        self.spin_monto.setEnabled(False)
        layout.addRow("Monto cobrado", self.spin_monto)
        self.combo_deposito.currentIndexChanged.connect(self._al_cambiar_deposito)
        self.combo_profesional.currentIndexChanged.connect(self._al_cambiar_profesional)

        # Punto propio de esta vuelta: `asignar_llave` ya soportaba
        # `periodo_imputado` (default el período actual, sin ningún
        # control para elegir "el siguiente") — mismo combo exacto que
        # ya usa Reservas aisladas/extraordinarias para esta misma
        # decisión, solo tiene efecto si se tilda "Cobrar depósito".
        self.combo_periodo = QComboBox()
        self.combo_periodo.addItem("Período actual", "actual")
        self.combo_periodo.addItem("Período siguiente", "siguiente")
        layout.addRow("Período a imputar", self.combo_periodo)

        self.campo_observacion = QLineEdit()
        layout.addRow("Observación", self.campo_observacion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco([
            self.combo_profesional, self.campo_fecha, self.combo_deposito, self.spin_monto,
            self.combo_periodo, self.campo_observacion, boton_ok, boton_cancelar,
        ], parent=self)
        self._al_cambiar_profesional()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.combo_profesional.setFocus()

    def _al_cambiar_deposito(self) -> None:
        self.spin_monto.setEnabled(self.combo_deposito.currentData() == "abonado")

    def _al_cambiar_profesional(self) -> None:
        """Confirmado por la clienta: un profesional B nunca paga
        depósito — "todo lo que se les carge queda bonificado". En vez
        de dejar que el operador elija "Abonado" y chocar después con el
        error de `crear_cargo_especial` (`resolver_profesional_para_
        cargo`), el combo "Depósito" se fuerza a "Bonificado" y se
        deshabilita mientras el profesional elegido sea un B."""
        id_profesional = self.combo_profesional.currentData()
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(id_profesional) if id_profesional else None
        es_b = profesional is not None and profesional["CategoriaProfesional"] == "B"
        if es_b:
            self.combo_deposito.setCurrentIndex(0)  # "bonificado"
        self.combo_deposito.setEnabled(not es_b)

    def valores(self) -> dict:
        periodo = periodo_actual(self.conn)
        if self.combo_periodo.currentData() == "siguiente":
            periodo = sumar_meses(periodo, 1)
        cobrar_deposito = self.combo_deposito.currentData() == "abonado"
        return {
            "id_profesional": self.combo_profesional.currentData(),
            "fecha": self.campo_fecha.date().toString(Qt.DateFormat.ISODate),
            "cobrar_deposito": cobrar_deposito,
            "monto_cobrado": (self.spin_monto.value() or None) if cobrar_deposito else None,
            "periodo_imputado": periodo,
            "observacion": self.campo_observacion.text().strip() or None,
        }


class _DialogoDevolucion(QDialog):
    def __init__(self, conn: sqlite3.Connection, movimiento: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Registrar devolución")
        layout = QFormLayout(self)
        layout.addRow(QLabel(f"{movimiento['_nombre_llave']}  —  {movimiento['_texto_profesional']}"))

        self.campo_fecha = _fecha_edit()
        layout.addRow("Fecha", self.campo_fecha)

        # Estado del depósito al asignar esta llave, explícito — pedido
        # de la clienta (punto 4): que a la hora de la devolución quede
        # claro si corresponde reintegrar algo o si ya alcanza con la
        # devolución de la llave en sí (bonificado en su momento, nada
        # que devolver). `casilla_reintegro` ya se pre-tildaba según este
        # mismo dato; esta etiqueta solo lo hace visible.
        deposito_cobrado = bool(movimiento["DepositoCobrado"])
        texto_estado = (
            f"Depósito original: Abonado ({_moneda(movimiento['MontoCobrado'] or 0)})" if deposito_cobrado
            else "Depósito original: Bonificado (no se cobró nada — no corresponde reintegrar)"
        )
        layout.addRow(QLabel(texto_estado))

        self.casilla_reintegro = QCheckBox("Reintegrar depósito")
        self.casilla_reintegro.setChecked(deposito_cobrado)
        layout.addRow(self.casilla_reintegro)
        self.spin_monto = _SpinMonto()
        self.spin_monto.setMaximum(10_000_000)
        self.spin_monto.setValue(movimiento["MontoCobrado"] or 0)
        layout.addRow("Monto a reintegrar", self.spin_monto)

        # Mismo combo que `_DialogoAsignar` — `devolver_llave` ya
        # soportaba `periodo_imputado` sin ningún control en la GUI.
        self.combo_periodo = QComboBox()
        self.combo_periodo.addItem("Período actual", "actual")
        self.combo_periodo.addItem("Período siguiente", "siguiente")
        layout.addRow("Período a imputar", self.combo_periodo)

        self.campo_observacion = QLineEdit()
        layout.addRow("Observación", self.campo_observacion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [
                self.campo_fecha, self.casilla_reintegro, self.spin_monto,
                self.combo_periodo, self.campo_observacion, boton_ok, boton_cancelar,
            ],
            parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.campo_fecha.setFocus()

    def valores(self) -> dict:
        periodo = periodo_actual(self.conn)
        if self.combo_periodo.currentData() == "siguiente":
            periodo = sumar_meses(periodo, 1)
        return {
            "fecha": self.campo_fecha.date().toString(Qt.DateFormat.ISODate),
            "reintegrar_deposito": self.casilla_reintegro.isChecked(),
            "monto_reintegrado": self.spin_monto.value() or None,
            "periodo_imputado": periodo,
            "observacion": self.campo_observacion.text().strip() or None,
        }


class _DialogoPerdida(QDialog):
    def __init__(self, movimiento: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar pérdida")
        layout = QFormLayout(self)
        layout.addRow(QLabel(f"{movimiento['_nombre_llave']}  —  {movimiento['_texto_profesional']}"))

        if movimiento["DepositoCobrado"]:
            aviso = QLabel(
                f"El depósito cobrado ({_moneda(movimiento['MontoCobrado'] or 0)}) queda perdido, no se "
                "reintegra.\nSi le da una copia nueva, va a tener que abonar el depósito de nuevo."
            )
        else:
            aviso = QLabel("Esta asignación no tenía depósito cobrado.")
        aviso.setStyleSheet("color: #a33;")
        layout.addRow(aviso)

        self.campo_fecha = _fecha_edit()
        layout.addRow("Fecha", self.campo_fecha)

        self.campo_observacion = QLineEdit()
        layout.addRow("Observación", self.campo_observacion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.campo_fecha, self.campo_observacion, boton_ok, boton_cancelar], parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.campo_fecha.setFocus()

    def valores(self) -> dict:
        return {
            "fecha": self.campo_fecha.date().toString(Qt.DateFormat.ISODate),
            "observacion": self.campo_observacion.text().strip() or None,
        }


class _DialogoPerdidaStock(QDialog):
    """Pérdida de copias que todavía estaban en stock, sin asignar a
    ningún profesional (ej. se traspapelan en el cajón) — a diferencia de
    _DialogoPerdida, acá no hay depósito ni profesional involucrado."""

    def __init__(self, tipo: sqlite3.Row, disponibles: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar pérdida")
        layout = QFormLayout(self)
        copia_o_copias = "copia disponible" if disponibles == 1 else "copias disponibles"
        layout.addRow(QLabel(f"{tipo['Nombre']}  —  {disponibles} {copia_o_copias}, sin asignar"))

        self.campo_fecha = _fecha_edit()
        layout.addRow("Fecha", self.campo_fecha)

        self.spin_cantidad = QSpinBox()
        self.spin_cantidad.setMinimum(1)
        self.spin_cantidad.setMaximum(disponibles)
        self.spin_cantidad.setValue(1)
        layout.addRow("Cantidad", self.spin_cantidad)

        self.campo_observacion = QLineEdit()
        layout.addRow("Observación", self.campo_observacion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.campo_fecha, self.spin_cantidad, self.campo_observacion, boton_ok, boton_cancelar], parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.campo_fecha.setFocus()

    def valores(self) -> dict:
        return {
            "cantidad": self.spin_cantidad.value(),
            "fecha": self.campo_fecha.date().toString(Qt.DateFormat.ISODate),
            "observacion": self.campo_observacion.text().strip() or None,
        }
