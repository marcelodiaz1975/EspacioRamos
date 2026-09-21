"""Estadísticas (revisión "uno por uno", ver CLAUDE.md): dos solapas, con
las mismas 11 columnas pero fuentes de datos y filtros distintos —
"Historial general" surge de los SnapshotMensual ya generados más el mes
en curso (calculado en vivo), "Estadísticas varias" es 100% en vivo y se
puede acotar por Localidad/Edificio/Unidad/Consultorio ("el más
específico manda"). Todo el cálculo de las columnas vive en
`app.negocio.estadisticas` — ver su docstring para las decisiones de la
clienta sobre montos brutos, horas ponderadas por día y conteos de
entidades siempre actuales."""
from __future__ import annotations

import sqlite3

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.estilos import COLOR_ROJO
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.items_tabla import item_numero
from app.gui.widgets.orden_tabla import OrdenTabla
from app.negocio.dias import parsear_periodo, periodo_actual
from app.negocio.estadisticas import (
    FilaEstadistica,
    _periodo_mas_antiguo_con_datos,
    estadisticas_varias,
    historial_general,
)
from app.negocio.formato import formatear_moneda, mes_texto

_ANCHO_PANEL_FILTROS = 240
_ANCHO_CAMPO = 220

_COLUMNAS = [
    "Período", "Porcentaje Ocupación", "Horas regulares semanales", "Variación sobre período anterior",
    "Monto por horas regulares", "Monto por horas aisladas", "Monto total",
    "Localidades", "Edificios", "Unidades", "Consultorios",
]


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _texto_pct(valor: float | None) -> str:
    return f"{valor:.1f}%" if valor is not None else ""


def _texto_horas(valor: float | None) -> str:
    return f"{valor:.1f}hs" if valor is not None else ""


def _texto_variacion(valor: float | None) -> str:
    if valor is None:
        return ""
    signo = "+" if valor >= 0 else "-"
    return f"{signo}{abs(valor):.1f}hs"


def _texto_monto(valor: float | None) -> str:
    return formatear_moneda(valor) if valor is not None else ""


def _item_variacion(valor: float | None) -> QTableWidgetItem:
    item = item_numero(_texto_variacion(valor))
    if valor is not None and valor < 0:
        item.setForeground(QColor(COLOR_ROJO))
    return item


def _valor_columna(fila: FilaEstadistica, columna: int):
    return (
        fila.periodo, fila.ocupacion_pct, fila.horas_regulares_semanales, fila.variacion_horas,
        fila.monto_regular, fila.monto_aislada, fila.monto_total,
        fila.cant_localidades, fila.cant_edificios, fila.cant_unidades, fila.cant_consultorios,
    )[columna]


def _clave_orden(columna: int):
    """(es_none, valor): las dos partes de la tupla nunca se comparan
    entre sí (Python compara `es_none` primero y ya alcanza para
    desempatar), así que un valor faltante (None, en columnas que pueden
    no tener dato) nunca termina comparándose directamente contra un
    número — quedan siempre al final."""
    def clave(fila: FilaEstadistica):
        valor = _valor_columna(fila, columna)
        return (valor is None, valor)
    return clave


def _llenar_fila(tabla: QTableWidget, fila_idx: int, f: FilaEstadistica) -> None:
    tabla.setItem(fila_idx, 0, QTableWidgetItem(f.periodo))
    tabla.setItem(fila_idx, 1, item_numero(_texto_pct(f.ocupacion_pct)))
    tabla.setItem(fila_idx, 2, item_numero(_texto_horas(f.horas_regulares_semanales)))
    tabla.setItem(fila_idx, 3, _item_variacion(f.variacion_horas))
    tabla.setItem(fila_idx, 4, item_numero(_texto_monto(f.monto_regular)))
    tabla.setItem(fila_idx, 5, item_numero(_texto_monto(f.monto_aislada)))
    tabla.setItem(fila_idx, 6, item_numero(_texto_monto(f.monto_total)))
    tabla.setItem(fila_idx, 7, item_numero(str(f.cant_localidades)))
    tabla.setItem(fila_idx, 8, item_numero(str(f.cant_edificios)))
    tabla.setItem(fila_idx, 9, item_numero(str(f.cant_unidades)))
    tabla.setItem(fila_idx, 10, item_numero(str(f.cant_consultorios)))


def _armar_tabla() -> QTableWidget:
    tabla = QTableWidget()
    tabla.setColumnCount(len(_COLUMNAS))
    tabla.setHorizontalHeaderLabels(_COLUMNAS)
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return tabla


class PantallaEstadisticas(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)

        titulo = QLabel("Estadísticas".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_historial = _PanelHistorialGeneral(conn)
        self.panel_varias = _PanelEstadisticasVarias(conn)
        self.pestanas.addTab(self.panel_historial, "Historial general")
        self.pestanas.addTab(self.panel_varias, "Estadísticas varias")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)

    def actualizar(self) -> None:
        self.panel_historial.actualizar()
        self.panel_varias.actualizar()


class _PanelHistorialGeneral(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._filas: list[FilaEstadistica] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """Mismo motivo que Reservas/Liquidación: el foco pedido durante
        la construcción no alcanza a "pegar" porque el QTabWidget
        contenedor todavía no está mostrado en ese momento."""
        super().showEvent(event)
        self.check_por_mes.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        panel_filtros = QWidget()
        panel_filtros.setFixedWidth(_ANCHO_PANEL_FILTROS)
        columna = QVBoxLayout(panel_filtros)

        columna.addWidget(_titulo_campo("Agrupar por"))
        self.check_por_mes = QCheckBox("Por mes")
        self.check_por_anio = QCheckBox("Por año")
        self.check_por_mes.setChecked(True)
        # Checks excluyentes (uno de los dos siempre marcado, como un par
        # de radio buttons) — pedido de la clienta, "por defecto por
        # mes". Un QButtonGroup exclusivo ya evita destildar el marcado
        # sin marcar el otro, así que no hace falta lógica propia.
        self._grupo_agrupar = QButtonGroup(self)
        self._grupo_agrupar.setExclusive(True)
        self._grupo_agrupar.addButton(self.check_por_mes)
        self._grupo_agrupar.addButton(self.check_por_anio)
        self.check_por_mes.toggled.connect(lambda _marcado: self.actualizar())
        columna.addWidget(self.check_por_mes)
        columna.addWidget(self.check_por_anio)

        boton_actualizar = QPushButton("Actualizar tabla")
        boton_actualizar.setObjectName("botonPrimario")
        boton_actualizar.setFixedWidth(_ANCHO_CAMPO)
        boton_actualizar.clicked.connect(self._restablecer)
        columna.addWidget(boton_actualizar)

        columna.addStretch()
        layout_externo.addWidget(panel_filtros)

        self.tabla = _armar_tabla()
        layout_externo.addWidget(self.tabla, stretch=1)

        self._orden = OrdenTabla(self.tabla, self.actualizar)
        self._foco = instalar_enter_avanza_foco(
            [self.check_por_mes, self.check_por_anio, boton_actualizar], parent=self,
        )

    def _restablecer(self) -> None:
        self.check_por_mes.blockSignals(True)
        self.check_por_mes.setChecked(True)
        self.check_por_mes.blockSignals(False)
        self._orden.reiniciar()
        self.actualizar()

    def actualizar(self) -> None:
        self._filas = historial_general(self.conn, por_anio=self.check_por_anio.isChecked())
        if self._orden.columna is not None:
            self._filas.sort(key=_clave_orden(self._orden.columna), reverse=not self._orden.ascendente)
        self.tabla.setRowCount(len(self._filas))
        for fila_idx, f in enumerate(self._filas):
            _llenar_fila(self.tabla, fila_idx, f)
        self.tabla.resizeColumnsToContents()


class _PanelEstadisticasVarias(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._filas: list[FilaEstadistica] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.combo_anio.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        panel_filtros = QWidget()
        panel_filtros.setFixedWidth(_ANCHO_PANEL_FILTROS)
        columna = QVBoxLayout(panel_filtros)

        columna.addWidget(_titulo_campo("Año"))
        self.combo_anio = QComboBox()
        self.combo_anio.setFixedWidth(_ANCHO_CAMPO)
        self._cargar_combo_anio()
        self.combo_anio.currentIndexChanged.connect(self.actualizar)
        columna.addWidget(self.combo_anio)

        columna.addWidget(_titulo_campo("Mes"))
        self.combo_mes = QComboBox()
        self.combo_mes.setFixedWidth(_ANCHO_CAMPO)
        self.combo_mes.addItem("Todos", None)
        for mes in range(1, 13):
            self.combo_mes.addItem(mes_texto(mes).capitalize(), mes)
        self.combo_mes.currentIndexChanged.connect(self.actualizar)
        columna.addWidget(self.combo_mes)

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

        boton_actualizar = QPushButton("Actualizar tabla")
        boton_actualizar.setObjectName("botonPrimario")
        boton_actualizar.setFixedWidth(_ANCHO_CAMPO)
        boton_actualizar.clicked.connect(self._restablecer)
        columna.addWidget(boton_actualizar)

        columna.addStretch()
        layout_externo.addWidget(panel_filtros)

        self.tabla = _armar_tabla()
        layout_externo.addWidget(self.tabla, stretch=1)

        self._orden = OrdenTabla(self.tabla, self.actualizar)
        self._cargar_combo_localidad()
        self._foco = instalar_enter_avanza_foco(
            [
                self.combo_anio, self.combo_mes, self.combo_localidad, self.combo_edificio,
                self.combo_unidad, self.combo_consultorio, boton_actualizar,
            ],
            parent=self,
        )

    # ------------------------------------------------------- combos

    def _cargar_combo_anio(self) -> None:
        self.combo_anio.blockSignals(True)
        self.combo_anio.clear()
        self.combo_anio.addItem("Todos", None)
        anio_desde, _mes = parsear_periodo(_periodo_mas_antiguo_con_datos(self.conn))
        anio_actual, _mes_actual = parsear_periodo(periodo_actual(self.conn))
        for anio in range(anio_actual, anio_desde - 1, -1):
            self.combo_anio.addItem(str(anio), anio)
        self.combo_anio.blockSignals(False)

    def _cargar_combo_localidad(self) -> None:
        self.combo_localidad.blockSignals(True)
        self.combo_localidad.clear()
        self.combo_localidad.addItem("Todos", None)
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
        self.combo_unidad.addItem("Todos", None)
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

    # --------------------------------------------------------- acciones

    def _restablecer(self) -> None:
        self._orden.reiniciar()
        self.combo_anio.blockSignals(True)
        self.combo_anio.setCurrentIndex(0)
        self.combo_anio.blockSignals(False)
        self.combo_mes.blockSignals(True)
        self.combo_mes.setCurrentIndex(0)
        self.combo_mes.blockSignals(False)
        self.combo_localidad.blockSignals(True)
        self.combo_localidad.setCurrentIndex(0)
        self.combo_localidad.blockSignals(False)
        self._cargar_combo_edificio()  # recarga en cascada unidad/consultorio y llama a actualizar() al final

    def actualizar(self) -> None:
        self._filas = estadisticas_varias(
            self.conn,
            anio=self.combo_anio.currentData(),
            mes=self.combo_mes.currentData(),
            id_localidad=self.combo_localidad.currentData(),
            id_edificio=self.combo_edificio.currentData(),
            id_unidad=self.combo_unidad.currentData(),
            id_consultorio=self.combo_consultorio.currentData(),
        )
        if self._orden.columna is not None:
            self._filas.sort(key=_clave_orden(self._orden.columna), reverse=not self._orden.ascendente)
        self.tabla.setRowCount(len(self._filas))
        for fila_idx, f in enumerate(self._filas):
            _llenar_fila(self.tabla, fila_idx, f)
        self.tabla.resizeColumnsToContents()
