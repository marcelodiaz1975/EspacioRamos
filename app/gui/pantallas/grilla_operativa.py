"""Pantalla "Grilla operativa" (punto 21 de la miscelánea, ago-2026): tres
secciones en solapas que comparten el mismo filtro de unidades que el
usuario tildó en la grilla (`GrillaOperativaWidget.ids_unidad_seleccionadas`,
sincronizado vía el callback `on_actualizar`):

- Grilla: la grilla filtrable en sí.
- Valores de los consultorios: valor hora regular/aislada de cada
  consultorio de las unidades filtradas.
- Estadísticas: por cada unidad filtrada (y agregado por edificio y
  total general) el % de ocupación, las horas reservadas y los
  subtotales/falta-cobrar del período actual del sistema — ver
  `app.negocio.estadisticas_operativas`."""
from __future__ import annotations

import sqlite3

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget

from app.gui.widgets.grilla_operativa import GrillaOperativaWidget
from app.negocio.estadisticas_operativas import EstadisticaGrupo, calcular_estadisticas_operativas
from app.negocio.formato import formatear_moneda

_COLUMNAS_VALORES = ["Edificio", "Unidad", "Consultorio", "Valor hora regular", "Valor hora aislada"]
_COLUMNAS_ESTADISTICAS = [
    "Unidad / Edificio", "% Ocupación", "Horas regulares", "Horas aisladas",
    "Subtotal regulares", "Subtotal aisladas", "Pagos del mes", "Falta cobrar",
]

_COLOR_SUBTOTAL_EDIFICIO = QColor("#E3EAF2")
_COLOR_TOTAL_GENERAL = QColor("#C5D3E3")


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

        titulo = QLabel("Grilla operativa")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)

        self.tabla_valores = _armar_tabla(_COLUMNAS_VALORES)
        self._tabs.addTab(self.tabla_valores, "Valores de los consultorios")

        self.tabla_estadisticas = _armar_tabla(_COLUMNAS_ESTADISTICAS)
        self._tabs.addTab(self.tabla_estadisticas, "Estadísticas")

        # Se arma al final: su constructor ya dispara `actualizar()`, que a
        # su vez llama a `_refrescar_secciones` — necesita que las tablas de
        # arriba ya existan.
        self.grilla = GrillaOperativaWidget(conn, on_actualizar=self._refrescar_secciones)
        self._tabs.insertTab(0, self.grilla, "Grilla")
        self._tabs.setCurrentIndex(0)

    # -------------------------------------------------------- sincronismo

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
        filas: list[tuple[EstadisticaGrupo, bool]] = [(g, False) for g in estadisticas.por_unidad]
        filas += [(g, True) for g in estadisticas.por_edificio]
        filas.append((estadisticas.total, True))
        self.tabla_estadisticas.setRowCount(len(filas))
        for fila, (grupo, resaltar) in enumerate(filas):
            self._llenar_fila_estadistica(fila, grupo, resaltar)

    def _llenar_fila_estadistica(self, fila: int, grupo: EstadisticaGrupo, resaltar: bool) -> None:
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
        color = _COLOR_TOTAL_GENERAL if grupo.id is None else (_COLOR_SUBTOTAL_EDIFICIO if resaltar else None)
        for columna, texto in enumerate(valores):
            item = QTableWidgetItem(texto)
            if resaltar:
                fuente = item.font()
                fuente.setBold(True)
                item.setFont(fuente)
            if color is not None:
                item.setBackground(color)
            self.tabla_estadisticas.setItem(fila, columna, item)
