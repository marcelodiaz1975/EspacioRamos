"""Pantalla de disponibilidad operativa (F24, sección 4.2 del documento):
visualiza app.negocio.grilla.calcular_grilla como una tabla de color por
unidad, coherente con la grilla del PDF de Disponibilidad (mismo criterio de
colores y la marca "S/V" para el caso "1 libre sin ventana")."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.negocio.dias import periodo_actual
from app.negocio.grilla import DIAS_GRILLA_DEFAULT, calcular_grilla

_COLOR_CELDA = {
    "verde": "#4CAF50",
    "amarillo": "#F5D547",
    "naranja": "#F5D547",
    "rojo": "#C0392B",
}
_TEXTO_CELDA = {"naranja": "S/V"}


class GrillaDisponibilidad(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        titulo = QLabel("Disponibilidad operativa")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        fila_filtros = QHBoxLayout()
        fila_filtros.addWidget(QLabel("Edificio:"))
        self.combo_edificio = QComboBox()
        self.combo_edificio.currentIndexChanged.connect(self.actualizar)
        fila_filtros.addWidget(self.combo_edificio)

        fila_filtros.addWidget(QLabel("Año:"))
        self.spin_anio = QSpinBox()
        self.spin_anio.setRange(2000, 2100)
        fila_filtros.addWidget(self.spin_anio)

        fila_filtros.addWidget(QLabel("Mes:"))
        self.spin_mes = QSpinBox()
        self.spin_mes.setRange(1, 12)
        fila_filtros.addWidget(self.spin_mes)

        boton_actualizar = QPushButton("Actualizar")
        boton_actualizar.setObjectName("botonPrimario")
        boton_actualizar.clicked.connect(self.actualizar)
        fila_filtros.addWidget(boton_actualizar)
        fila_filtros.addStretch()
        layout.addLayout(fila_filtros)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.contenedor = QWidget()
        self.layout_contenedor = QVBoxLayout(self.contenedor)
        scroll.setWidget(self.contenedor)
        layout.addWidget(scroll, stretch=1)

        periodo = periodo_actual(self.conn)
        anio, mes = (int(p) for p in periodo.split("-"))
        self.spin_anio.setValue(anio)
        self.spin_mes.setValue(mes)
        self._cargar_edificios()

    def _cargar_edificios(self) -> None:
        self.combo_edificio.blockSignals(True)
        self.combo_edificio.clear()
        self.combo_edificio.addItem("Todos los edificios", None)
        for fila in self.conn.execute("SELECT IdEdificio, Nombre FROM Edificio ORDER BY Nombre").fetchall():
            self.combo_edificio.addItem(fila["Nombre"], fila["IdEdificio"])
        self.combo_edificio.blockSignals(False)

    def actualizar(self) -> None:
        while self.layout_contenedor.count():
            item = self.layout_contenedor.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        anio = self.spin_anio.value()
        mes = self.spin_mes.value()
        id_edificio = self.combo_edificio.currentData()

        grilla = calcular_grilla(self.conn, anio, mes)
        unidades = self._unidades(id_edificio)
        if not unidades:
            self.layout_contenedor.addWidget(QLabel("No hay unidades para mostrar."))
            return

        for unidad in unidades:
            self.layout_contenedor.addWidget(self._tarjeta_unidad(unidad, grilla))
        self.layout_contenedor.addStretch()

    def _unidades(self, id_edificio: int | None) -> list[sqlite3.Row]:
        sql = (
            "SELECT u.IdUnidad, u.Departamento, e.Nombre AS Edificio FROM Unidad u "
            "JOIN Edificio e ON e.IdEdificio = u.IdEdificio"
        )
        parametros: tuple = ()
        if id_edificio is not None:
            sql += " WHERE u.IdEdificio = ?"
            parametros = (id_edificio,)
        sql += " ORDER BY e.Nombre, u.Departamento"
        return self.conn.execute(sql, parametros).fetchall()

    def _tarjeta_unidad(self, unidad: sqlite3.Row, grilla: dict) -> QWidget:
        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 12)

        subtitulo = QLabel(f"{unidad['Edificio']} — {unidad['Departamento']}")
        subtitulo.setObjectName("subtitulo")
        layout.addWidget(subtitulo)

        cfg = self.conn.execute(
            "SELECT HoraInicioGrilla, HoraFinGrilla FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        hora_ini = cfg["HoraInicioGrilla"] if cfg else 8
        hora_fin = cfg["HoraFinGrilla"] if cfg else 22
        horas = list(range(int(hora_ini), int(hora_fin)))

        tabla = QTableWidget(len(horas), len(DIAS_GRILLA_DEFAULT))
        tabla.setHorizontalHeaderLabels(DIAS_GRILLA_DEFAULT)
        tabla.setVerticalHeaderLabels([f"{h}:00" for h in horas])
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for fila_idx, hora in enumerate(horas):
            for col_idx, dia in enumerate(DIAS_GRILLA_DEFAULT):
                color_nombre = grilla.get((unidad["IdUnidad"], dia, hora), "rojo")
                item = QTableWidgetItem(_TEXTO_CELDA.get(color_nombre, ""))
                item.setBackground(QColor(_COLOR_CELDA[color_nombre]))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tabla.setItem(fila_idx, col_idx, item)
        tabla.resizeColumnsToContents()
        tabla.setFixedHeight(min(28 * (len(horas) + 1) + 4, 500))
        layout.addWidget(tabla)
        return contenedor
