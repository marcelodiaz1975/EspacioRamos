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

from openpyxl import Workbook
from openpyxl.styles import Font
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
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
from app.negocio.dias import periodo_actual, periodo_anterior
from app.negocio.estadisticas import (
    FilaEstadistica,
    _periodo_mas_antiguo_con_datos,
    estadisticas_varias,
    historial_general,
)
from app.negocio.formato import formatear_moneda

_ANCHO_PANEL_FILTROS = 240
_ANCHO_CAMPO = 220

# Títulos partidos en dos líneas (pedido de la clienta: más alto, menos
# ancho) donde alcanza con eso para acortar la columna sin recortar la
# palabra a mitad de camino — QHeaderView ya soporta "\n" y agranda solo
# el alto de la fila de encabezados, sin que haga falta nada más.
_COLUMNAS = [
    "Período", "Porcentaje\nOcupación", "Horas regulares\nsemanales", "Variación sobre\nperíodo anterior",
    "Monto por horas\nregulares", "Monto por horas\naisladas", "Monto total",
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


def _opciones_periodo(conn: sqlite3.Connection) -> list[str]:
    """Todos los períodos ("AAAA-MM") con algún dato, del más viejo al
    más nuevo — para poblar los combos "Desde"/"Hasta" de Estadísticas
    varias."""
    hasta = periodo_actual(conn)
    desde = _periodo_mas_antiguo_con_datos(conn)
    periodos = []
    cursor = hasta
    while cursor >= desde:
        periodos.append(cursor)
        cursor = periodo_anterior(cursor)
    periodos.reverse()
    return periodos


def _armar_tabla() -> QTableWidget:
    tabla = QTableWidget()
    tabla.setColumnCount(len(_COLUMNAS))
    tabla.setHorizontalHeaderLabels(_COLUMNAS)
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return tabla


# Mismos títulos que `_COLUMNAS`, sin el "\n" (ahí es para que el
# encabezado de la tabla ocupe menos ancho — en una planilla Excel no
# hace falta ese recurso).
_COLUMNAS_EXCEL = [c.replace("\n", " ") for c in _COLUMNAS]


def _exportar_filas_a_excel(filas: list[FilaEstadistica], ruta: str) -> None:
    """DC-06 §6 (hallazgo de la auditoría DC-01/DC-10): exporta exactamente
    las filas que se le pasan (ya filtradas/ordenadas por el panel que
    llama) con las mismas 11 columnas y el mismo formato de texto que la
    tabla en pantalla — mismos helpers (`_texto_pct`/`_texto_horas`/etc.),
    para que lo que se vea en la planilla coincida con lo que se vio en
    el panel antes de exportar."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Estadísticas"
    hoja.append(_COLUMNAS_EXCEL)
    for celda in hoja[1]:
        celda.font = Font(bold=True)
    for f in filas:
        hoja.append([
            f.periodo, _texto_pct(f.ocupacion_pct), _texto_horas(f.horas_regulares_semanales),
            _texto_variacion(f.variacion_horas), _texto_monto(f.monto_regular), _texto_monto(f.monto_aislada),
            _texto_monto(f.monto_total), f.cant_localidades, f.cant_edificios, f.cant_unidades, f.cant_consultorios,
        ])
    for i, titulo in enumerate(_COLUMNAS_EXCEL, start=1):
        ancho = max(14, len(titulo) + 2)
        hoja.column_dimensions[hoja.cell(row=1, column=i).column_letter].width = ancho
    libro.save(ruta)


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

        boton_exportar = QPushButton("Exportar a Excel")
        boton_exportar.setObjectName("botonSecundario")
        boton_exportar.setFixedWidth(_ANCHO_CAMPO)
        boton_exportar.clicked.connect(self._exportar_a_excel)
        columna.addWidget(boton_exportar)

        columna.addStretch()
        layout_externo.addWidget(panel_filtros)

        self.tabla = _armar_tabla()
        layout_externo.addWidget(self.tabla, stretch=1)

        self._orden = OrdenTabla(self.tabla, self.actualizar)
        self._foco = instalar_enter_avanza_foco(
            [self.check_por_mes, self.check_por_anio, boton_actualizar, boton_exportar], parent=self,
        )

    def _exportar_a_excel(self) -> None:
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar a Excel", "Estadisticas - Historial general.xlsx", "Excel (*.xlsx)",
        )
        if not ruta:
            return
        try:
            _exportar_filas_a_excel(self._filas, ruta)
        except OSError as exc:
            QMessageBox.critical(self, "Exportar a Excel", f"No se pudo generar la planilla: {exc}")
            return
        QMessageBox.information(self, "Exportar a Excel", f"Planilla generada en: {ruta}")

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
        self.combo_desde.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        panel_filtros = QWidget()
        panel_filtros.setFixedWidth(_ANCHO_PANEL_FILTROS)
        columna = QVBoxLayout(panel_filtros)

        opciones_periodo = _opciones_periodo(self.conn)

        columna.addWidget(_titulo_campo("Desde"))
        self.combo_desde = QComboBox()
        self.combo_desde.setFixedWidth(_ANCHO_CAMPO)
        self.combo_desde.addItem("Todo el historial", None)
        for periodo in opciones_periodo:
            self.combo_desde.addItem(periodo, periodo)
        self.combo_desde.currentIndexChanged.connect(self.actualizar)
        columna.addWidget(self.combo_desde)

        columna.addWidget(_titulo_campo("Hasta"))
        self.combo_hasta = QComboBox()
        self.combo_hasta.setFixedWidth(_ANCHO_CAMPO)
        self.combo_hasta.addItem("Todo el historial", None)
        for periodo in opciones_periodo:
            self.combo_hasta.addItem(periodo, periodo)
        self.combo_hasta.currentIndexChanged.connect(self.actualizar)
        columna.addWidget(self.combo_hasta)

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

        boton_exportar = QPushButton("Exportar a Excel")
        boton_exportar.setObjectName("botonSecundario")
        boton_exportar.setFixedWidth(_ANCHO_CAMPO)
        boton_exportar.clicked.connect(self._exportar_a_excel)
        columna.addWidget(boton_exportar)

        columna.addStretch()
        layout_externo.addWidget(panel_filtros)

        self.tabla = _armar_tabla()
        layout_externo.addWidget(self.tabla, stretch=1)

        self._orden = OrdenTabla(self.tabla, self.actualizar)
        self._cargar_combo_localidad()
        self._foco = instalar_enter_avanza_foco(
            [
                self.combo_desde, self.combo_hasta, self.combo_localidad, self.combo_edificio,
                self.combo_unidad, self.combo_consultorio, boton_actualizar, boton_exportar,
            ],
            parent=self,
        )

    def _exportar_a_excel(self) -> None:
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar a Excel", "Estadisticas - Estadisticas varias.xlsx", "Excel (*.xlsx)",
        )
        if not ruta:
            return
        try:
            _exportar_filas_a_excel(self._filas, ruta)
        except OSError as exc:
            QMessageBox.critical(self, "Exportar a Excel", f"No se pudo generar la planilla: {exc}")
            return
        QMessageBox.information(self, "Exportar a Excel", f"Planilla generada en: {ruta}")

    # ------------------------------------------------------- combos

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
        self.combo_desde.blockSignals(True)
        self.combo_desde.setCurrentIndex(0)
        self.combo_desde.blockSignals(False)
        self.combo_hasta.blockSignals(True)
        self.combo_hasta.setCurrentIndex(0)
        self.combo_hasta.blockSignals(False)
        self.combo_localidad.blockSignals(True)
        self.combo_localidad.setCurrentIndex(0)
        self.combo_localidad.blockSignals(False)
        self._cargar_combo_edificio()  # recarga en cascada unidad/consultorio y llama a actualizar() al final

    def actualizar(self) -> None:
        self._filas = estadisticas_varias(
            self.conn,
            desde=self.combo_desde.currentData(),
            hasta=self.combo_hasta.currentData(),
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
