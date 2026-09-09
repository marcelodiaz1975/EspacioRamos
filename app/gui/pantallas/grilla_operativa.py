"""Pantalla "Vista rápida" (ex "Grilla operativa", punto 21 de la
miscelánea, ago-2026, renombrada y reorganizada en solapas a pedido de la
clienta): tres solapas, cada una sincronizada con el mismo filtro de
unidades que el usuario tildó en la grilla
(`GrillaOperativaWidget.ids_unidad_seleccionadas`, sincronizado vía el
callback `on_actualizar`):

- Grilla: la grilla filtrable en sí (el widget compartido
  `GrillaOperativaWidget`, sin modificar — lo siguen usando tal cual el
  resto de los formularios que la embeben) + referencias de colores.
- Valores de los consultorios: valor hora regular/aislada de cada
  consultorio de las unidades filtradas.
- Estadísticas: total general primero, después el desglose por localidad
  (si el filtro abarca más de una) y por edificio (si abarca más de uno),
  y por último el detalle por unidad — ver `app.negocio.estadisticas_operativas`."""
from __future__ import annotations

import sqlite3

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGridLayout, QGroupBox, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from app.gui.widgets.grilla_operativa import GrillaOperativaWidget, _CeldaGrilla
from app.negocio.estadisticas_operativas import EstadisticaGrupo, calcular_estadisticas_operativas
from app.negocio.formato import formatear_moneda
from app.negocio.grilla_operativa import AMARILLO, AZUL_OSCURO, BLANCA, BLANCO, NEGRA, ROJO, VERDE, CeldaGrillaOperativa

_COLUMNAS_VALORES = ["Edificio", "Unidad", "Consultorio", "Valor hora regular", "Valor hora aislada"]
_COLUMNAS_ESTADISTICAS = [
    "Total / Localidad / Edificio / Unidad", "% Ocupación", "Horas regulares", "Horas aisladas",
    "Subtotal regulares", "Subtotal aisladas", "Pagos del mes", "Falta cobrar",
]

_COLOR_TOTAL = QColor("#B7C8DC")
_COLOR_LOCALIDAD = QColor("#D2DEEB")
_COLOR_EDIFICIO = QColor("#E9EFF5")

_REFERENCIAS_REGULAR: list[tuple[CeldaGrillaOperativa, str]] = [
    (CeldaGrillaOperativa(BLANCO, BLANCO, NEGRA, None, "", None), "Sin novedades (el código, si lo hay, sigue vigente)."),
    (CeldaGrillaOperativa(VERDE, VERDE, NEGRA, None, "", None), "Se libera en el futuro."),
    (CeldaGrillaOperativa(ROJO, ROJO, NEGRA, None, "", None), "Reservado a futuro (todavía no vigente)."),
    (CeldaGrillaOperativa(AMARILLO, AMARILLO, NEGRA, None, "", None), "Libre de regular, con hora aislada asignada."),
    (CeldaGrillaOperativa(ROJO, AMARILLO, NEGRA, None, "", None), "Reservado a futuro + aislada confirmada este mes."),
    (CeldaGrillaOperativa(BLANCO, VERDE, NEGRA, None, "", None), "Reservado, pero libre por ausencia/vacación/licencia."),
    (CeldaGrillaOperativa(BLANCO, AMARILLO, NEGRA, None, "", None), "Igual, con aislada confirmada en ese hueco."),
    (CeldaGrillaOperativa(AZUL_OSCURO, AZUL_OSCURO, BLANCA, None, "", None), "Profesional filtrado."),
]

_REFERENCIAS_AISLADA: list[tuple[CeldaGrillaOperativa, str]] = [
    (CeldaGrillaOperativa(ROJO, ROJO, NEGRA, None, "", None), "Bloqueado por una reserva regular."),
    (CeldaGrillaOperativa(VERDE, VERDE, NEGRA, None, "", None), "Libre de reserva regular."),
    (CeldaGrillaOperativa(ROJO, VERDE, NEGRA, None, "", None), "Reservado, pero libera un hueco por ausencia/vacación/licencia."),
    (CeldaGrillaOperativa(ROJO, AMARILLO, NEGRA, None, "", None), "Igual, con aislada confirmada en ese hueco."),
    (CeldaGrillaOperativa(AMARILLO, AMARILLO, NEGRA, None, "", None), "Libre + aislada asignada."),
    (CeldaGrillaOperativa(AZUL_OSCURO, AZUL_OSCURO, BLANCA, None, "", None), "Profesional filtrado."),
]


class _LeyendaColores(QGroupBox):
    """Referencia de qué significa cada color/combinación — reusa
    `_CeldaGrilla` (la misma clase que pinta la grilla real) para que la
    muestra sea pixel a pixel igual a lo que se ve arriba, en vez de
    reimplementar el dibujo del triángulo acá aparte."""

    def __init__(self, parent=None):
        super().__init__("Referencias de colores", parent)
        self._layout = QGridLayout(self)
        self.actualizar("regular")

    def actualizar(self, modo: str) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        referencias = _REFERENCIAS_REGULAR if modo == "regular" else _REFERENCIAS_AISLADA
        columnas = 2
        for i, (celda, texto) in enumerate(referencias):
            fila, columna = divmod(i, columnas)
            muestra = _CeldaGrilla(celda, (0, "Lunes", 0), lambda *_: None)
            muestra.setFixedSize(40, 24)
            self._layout.addWidget(muestra, fila, columna * 2)
            etiqueta = QLabel(texto)
            etiqueta.setWordWrap(True)
            self._layout.addWidget(etiqueta, fila, columna * 2 + 1)


def _fmt_horas(horas: float) -> str:
    return str(int(horas)) if horas == int(horas) else f"{horas:.1f}"


def _armar_tabla(columnas: list[str]) -> QTableWidget:
    tabla = QTableWidget()
    tabla.setColumnCount(len(columnas))
    tabla.setHorizontalHeaderLabels(columnas)
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabla.verticalHeader().setVisible(False)
    tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return tabla


class PantallaGrillaOperativa(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn

        layout = QVBoxLayout(self)

        titulo = QLabel("Vista rápida")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # La grilla se arma primero: su constructor ya dispara
        # `actualizar()`, que a su vez llama a `_refrescar_secciones` —
        # necesita que las tablas de las otras solapas ya existan.
        self.tabla_valores = _armar_tabla(_COLUMNAS_VALORES)
        self.tabla_estadisticas = _armar_tabla(_COLUMNAS_ESTADISTICAS)

        panel_grilla = QWidget()
        layout_grilla = QVBoxLayout(panel_grilla)
        self.grilla = GrillaOperativaWidget(conn, on_actualizar=self._refrescar_secciones)
        self.grilla.combo_modo.currentIndexChanged.connect(self._actualizar_leyenda)
        layout_grilla.addWidget(self.grilla, stretch=1)
        self._leyenda = _LeyendaColores()
        layout_grilla.addWidget(self._leyenda)
        tabs.addTab(panel_grilla, "Grilla")

        panel_valores = QWidget()
        layout_valores = QVBoxLayout(panel_valores)
        layout_valores.addWidget(self.tabla_valores)
        tabs.addTab(panel_valores, "Valores de los consultorios")

        panel_estadisticas = QWidget()
        layout_estadisticas = QVBoxLayout(panel_estadisticas)
        layout_estadisticas.addWidget(self.tabla_estadisticas)
        tabs.addTab(panel_estadisticas, "Estadísticas")

    # -------------------------------------------------------- sincronismo

    def _actualizar_leyenda(self) -> None:
        self._leyenda.actualizar(self.grilla.combo_modo.currentData() or "regular")

    def _refrescar_secciones(self, ids_unidad: list[int]) -> None:
        self._refrescar_valores(ids_unidad)
        self._refrescar_estadisticas(ids_unidad)

    def _refrescar_valores(self, ids_unidad: list[int]) -> None:
        self.tabla_valores.setRowCount(0)
        if not ids_unidad:
            return
        placeholders = ", ".join("?" for _ in ids_unidad)
        filas = self.conn.execute(
            f"""
            SELECT e.Nombre AS NombreEdificio, u.Departamento, c.NumeroConsultorio,
                   c.ValorHoraRegularActual, c.ValorHoraAisladaActual
            FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
            WHERE u.IdUnidad IN ({placeholders})
            ORDER BY e.Nombre, u.Departamento, c.NumeroConsultorio
            """,
            ids_unidad,
        ).fetchall()
        self.tabla_valores.setRowCount(len(filas))
        for fila, f in enumerate(filas):
            valores = [
                f["NombreEdificio"], f["Departamento"], str(f["NumeroConsultorio"]),
                formatear_moneda(f["ValorHoraRegularActual"] or 0),
                formatear_moneda(f["ValorHoraAisladaActual"] or 0),
            ]
            for columna, texto in enumerate(valores):
                self.tabla_valores.setItem(fila, columna, QTableWidgetItem(texto))

    def _refrescar_estadisticas(self, ids_unidad: list[int]) -> None:
        self.tabla_estadisticas.setRowCount(0)
        if not ids_unidad:
            return
        estadisticas = calcular_estadisticas_operativas(self.conn, ids_unidad)

        filas: list[tuple[EstadisticaGrupo, QColor | None]] = [(estadisticas.total, _COLOR_TOTAL)]
        if len(estadisticas.por_localidad) > 1:
            filas += [(g, _COLOR_LOCALIDAD) for g in estadisticas.por_localidad]
        if len(estadisticas.por_edificio) > 1:
            filas += [(g, _COLOR_EDIFICIO) for g in estadisticas.por_edificio]
        filas += [(g, None) for g in estadisticas.por_unidad]

        self.tabla_estadisticas.setRowCount(len(filas))
        for fila, (grupo, color) in enumerate(filas):
            self._llenar_fila_estadistica(fila, grupo, color)

    def _llenar_fila_estadistica(self, fila: int, grupo: EstadisticaGrupo, color: QColor | None) -> None:
        valores = [
            grupo.nombre,
            f"{grupo.porcentaje_ocupacion:.1f} %",
            _fmt_horas(grupo.horas_regulares),
            _fmt_horas(grupo.horas_aisladas),
            formatear_moneda(grupo.subtotal_regulares),
            formatear_moneda(grupo.subtotal_aisladas),
            formatear_moneda(grupo.pagos_atribuidos),
            formatear_moneda(grupo.falta_cobrar),
        ]
        for columna, texto in enumerate(valores):
            item = QTableWidgetItem(texto)
            if color is not None:
                fuente = item.font()
                fuente.setBold(True)
                item.setFont(fuente)
                item.setBackground(color)
            self.tabla_estadisticas.setItem(fila, columna, item)
