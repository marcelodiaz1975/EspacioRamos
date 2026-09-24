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
"cada pantalla arma la suya" que el resto del sistema."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.pantallas import catalogos
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.resumen_saldo import fmt_dato
from app.negocio.balance import resultado_periodo, total_ingresos_periodo
from app.negocio.dias import periodo_actual
from app.negocio.estadisticas import _ids_consultorio_del_alcance

_ANCHO_CAMPO = 220
_ANCHO_PANEL_FILTROS = 240


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    return linea


def _titulo_periodo(prefijo: str, periodo: str) -> str:
    """Mismo criterio que "Subtotal gastos período" de Gastos
    operativos: el período se guarda AAAA-MM pero se muestra invertido,
    MM-AAAA, pedido de la clienta."""
    partes = periodo.split("-")
    if len(partes) == 2:
        anio, mes = partes
        return f"{prefijo} período {mes}-{anio}"
    return f"{prefijo} período {periodo}"


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

        self.boton_actualizar = QPushButton("Actualizar")
        self.boton_actualizar.setObjectName("botonPrimario")
        self.boton_actualizar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_actualizar.clicked.connect(self._restablecer)
        columna.addWidget(self.boton_actualizar)

        columna.addStretch()

        self._cargar_combo_localidad()
        self._foco = instalar_enter_avanza_foco(
            [
                self.campo_periodo, self.combo_localidad, self.combo_edificio,
                self.combo_unidad, self.combo_consultorio, self.boton_actualizar,
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

    def _restablecer(self) -> None:
        self.campo_periodo.setText(periodo_actual(self.conn))
        self.combo_localidad.blockSignals(True)
        self.combo_localidad.setCurrentIndex(0)
        self.combo_localidad.blockSignals(False)
        self._cargar_combo_edificio()  # recarga en cascada unidad/consultorio y llama a actualizar() al final


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

        # El panel de resumen se arma ANTES que el de filtros: construir
        # los filtros dispara la cascada de combos, que termina llamando
        # a `actualizar()` — las etiquetas de acá tienen que existir ya.
        panel_resumen = QWidget()
        resumen = QVBoxLayout(panel_resumen)
        self.etiqueta_titulo = _titulo_campo("")
        resumen.addWidget(self.etiqueta_titulo)
        resumen.addWidget(_linea_divisoria())
        self.etiqueta_regulares = QLabel()
        self.etiqueta_aisladas = QLabel()
        self.etiqueta_feriados_trabajados = QLabel()
        self.etiqueta_total = QLabel()
        for etiqueta in (
            self.etiqueta_regulares, self.etiqueta_aisladas, self.etiqueta_feriados_trabajados, self.etiqueta_total,
        ):
            resumen.addWidget(etiqueta)
        resumen.addStretch()

        layout_externo.addWidget(self._armar_panel_filtros())
        layout_externo.addWidget(panel_resumen, stretch=1)

    def actualizar(self) -> None:
        periodo = self.campo_periodo.text().strip() or periodo_actual(self.conn)
        ids_consultorio = _ids_consultorio_del_alcance(
            self.conn,
            id_localidad=self.combo_localidad.currentData(), id_edificio=self.combo_edificio.currentData(),
            id_unidad=self.combo_unidad.currentData(), id_consultorio=self.combo_consultorio.currentData(),
        )
        regulares, aisladas, feriados_trabajados = total_ingresos_periodo(self.conn, periodo, ids_consultorio)
        total = regulares + aisladas + feriados_trabajados
        self.etiqueta_titulo.setText(_titulo_periodo("Ingresos", periodo))
        self.etiqueta_regulares.setText(fmt_dato("Ingresos por horas regulares", regulares))
        self.etiqueta_aisladas.setText(fmt_dato("Ingresos por horas aisladas", aisladas))
        self.etiqueta_feriados_trabajados.setText(fmt_dato("Ingresos por feriados trabajados", feriados_trabajados))
        self.etiqueta_total.setText(fmt_dato("Total ingresos", total))


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

        # Mismo motivo que en _PanelIngresos: armar el resumen antes que
        # los filtros, porque construir los filtros ya dispara `actualizar()`.
        panel_resumen = QWidget()
        resumen = QVBoxLayout(panel_resumen)
        self.etiqueta_titulo = _titulo_campo("")
        resumen.addWidget(self.etiqueta_titulo)
        resumen.addWidget(_linea_divisoria())
        self.etiqueta_ingresos = QLabel()
        self.etiqueta_gastos = QLabel()
        self.etiqueta_resultado = QLabel()
        for etiqueta in (self.etiqueta_ingresos, self.etiqueta_gastos, self.etiqueta_resultado):
            resumen.addWidget(etiqueta)
        resumen.addStretch()

        layout_externo.addWidget(self._armar_panel_filtros())
        layout_externo.addWidget(panel_resumen, stretch=1)

    def actualizar(self) -> None:
        periodo = self.campo_periodo.text().strip() or periodo_actual(self.conn)
        ingresos, gastos, resultado = resultado_periodo(
            self.conn, periodo,
            id_localidad=self.combo_localidad.currentData(), id_edificio=self.combo_edificio.currentData(),
            id_unidad=self.combo_unidad.currentData(), id_consultorio=self.combo_consultorio.currentData(),
        )
        self.etiqueta_titulo.setText(_titulo_periodo("Resultado", periodo))
        self.etiqueta_ingresos.setText(fmt_dato("Ingresos totales", ingresos))
        self.etiqueta_gastos.setText(fmt_dato("Gastos totales", -gastos))
        self.etiqueta_resultado.setText(fmt_dato("Resultado", resultado))


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
