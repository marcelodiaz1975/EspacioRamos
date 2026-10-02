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

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.pantallas import catalogos
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.resumen_saldo import item_monto
from app.negocio.balance import resultado_periodo, total_ingresos_periodo
from app.negocio.dias import periodo_actual
from app.negocio.estadisticas import _ids_consultorio_del_alcance, _periodos_para_filtro

_ANCHO_CAMPO = 220
_ANCHO_PANEL_FILTROS = 240

_COLUMNAS_INGRESOS = [
    "Período", "Ingreso por horas regulares", "Ingreso por horas aisladas",
    "Ingreso por feriados\ny días especiales", "Total ingresos",
]
_COLUMNAS_RESULTADO = ["Período", "Total ingresos", "Total gastos", "Balance del período"]


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _armar_tabla(columnas: list[str]) -> QTableWidget:
    """Pocas columnas, todas de importancia pareja — Stretch en las
    columnas (mismo criterio que Placas/Importar planilla) para que se
    reparta todo el ancho disponible del panel en vez de dejar un
    espacio en blanco al final (ver el bug ya documentado en "Valores
    vigentes")."""
    tabla = QTableWidget()
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
        self.campo_periodo = QLineEdit()
        self.campo_periodo.setFixedWidth(_ANCHO_CAMPO)
        self.campo_periodo.setText(periodo_actual(self.conn))
        self.campo_periodo.editingFinished.connect(self.actualizar)
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
                self.campo_periodo, self.combo_localidad, self.combo_edificio,
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
        sql += " ORDER BY Departamento"
        for f in self.conn.execute(sql, parametros).fetchall():
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
        self.campo_periodo.setText(periodo_actual(self.conn))
        self.actualizar()


class _PanelIngresos(_PanelFiltrosMixin, QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._armar_ui()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
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
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(periodo))
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
        periodo = self.campo_periodo.text().strip() or periodo_actual(self.conn)
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
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(periodo))
            self.tabla.setItem(fila_idx, 1, item_monto(ingresos))
            self.tabla.setItem(fila_idx, 2, item_monto(-gastos))
            self.tabla.setItem(fila_idx, 3, item_monto(resultado))

    def actualizar(self) -> None:
        periodo = self.campo_periodo.text().strip() or periodo_actual(self.conn)
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
        self.panel_gastos = catalogos.pantalla_gastos_operativos(conn, anidado=True)
        self.pestanas.addTab(self.panel_gastos, "Gastos")
        self.panel_ingresos = _PanelIngresos(conn)
        self.pestanas.addTab(self.panel_ingresos, "Ingresos")
        self.panel_resultado = _PanelResultado(conn)
        self.pestanas.addTab(self.panel_resultado, "Resultado")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
