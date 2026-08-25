"""Pantalla "Grilla operativa" (punto 21 de la miscelánea, ago-2026): tres
secciones apiladas en una sola pantalla con scroll (grilla arriba de todo,
lo primero que se ve al entrar; debajo, valores y estadísticas), todas
sincronizadas con el mismo filtro de unidades que el usuario tildó en la
grilla (`GrillaOperativaWidget.ids_unidad_seleccionadas`, sincronizado vía
el callback `on_actualizar`):

- Grilla: la grilla filtrable en sí.
- Valores de los consultorios: valor hora regular/aislada de cada
  consultorio de las unidades filtradas.
- Estadísticas: total general primero, después el desglose por localidad
  (si el filtro abarca más de una) y por edificio (si abarca más de uno),
  y por último el detalle por unidad — ver `app.negocio.estadisticas_operativas`."""
from __future__ import annotations

import sqlite3

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox, QHeaderView, QLabel, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.gui.widgets.grilla_operativa import GrillaOperativaWidget
from app.negocio.estadisticas_operativas import EstadisticaGrupo, calcular_estadisticas_operativas
from app.negocio.formato import formatear_moneda

_COLUMNAS_VALORES = ["Edificio", "Unidad", "Consultorio", "Valor hora regular", "Valor hora aislada"]
_COLUMNAS_ESTADISTICAS = [
    "Total / Localidad / Edificio / Unidad", "% Ocupación", "Horas regulares", "Horas aisladas",
    "Subtotal regulares", "Subtotal aisladas", "Pagos del mes", "Falta cobrar",
]

_COLOR_TOTAL = QColor("#B7C8DC")
_COLOR_LOCALIDAD = QColor("#D2DEEB")
_COLOR_EDIFICIO = QColor("#E9EFF5")


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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        contenedor = QWidget()
        scroll.setWidget(contenedor)
        layout_pantalla = QVBoxLayout(self)
        layout_pantalla.addWidget(scroll)

        layout = QVBoxLayout(contenedor)

        titulo = QLabel("Grilla operativa")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        grupo_valores = QGroupBox("Valores de los consultorios")
        layout_valores = QVBoxLayout(grupo_valores)
        self.tabla_valores = _armar_tabla(_COLUMNAS_VALORES)
        layout_valores.addWidget(self.tabla_valores)

        grupo_estadisticas = QGroupBox("Estadísticas")
        layout_estadisticas = QVBoxLayout(grupo_estadisticas)
        self.tabla_estadisticas = _armar_tabla(_COLUMNAS_ESTADISTICAS)
        layout_estadisticas.addWidget(self.tabla_estadisticas)

        # La grilla se arma al final: su constructor ya dispara `actualizar()`,
        # que a su vez llama a `_refrescar_secciones` — necesita que las
        # tablas de arriba ya existan.
        grupo_grilla = QGroupBox("Grilla")
        layout_grilla = QVBoxLayout(grupo_grilla)
        self.grilla = GrillaOperativaWidget(conn, on_actualizar=self._refrescar_secciones)
        self.grilla.setMinimumHeight(650)
        layout_grilla.addWidget(self.grilla)

        layout.addWidget(grupo_grilla)
        layout.addWidget(grupo_valores)
        layout.addWidget(grupo_estadisticas)

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
