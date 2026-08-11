"""Estadísticas (FA3, Etapa 9): ocupación en vivo para un período elegido
y el historial de snapshots mensuales ya generados (uno se crea
automáticamente en cada avance de mes). El documento no detalla más
contenido para esta pantalla que el modelo de SnapshotMensual — ver el
docstring de app.negocio.estadisticas."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.negocio.dias import periodo_actual
from app.negocio.estadisticas import calcular_ocupacion
from app.repositorio.registro import obtener_repositorio


class PantallaEstadisticas(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Estadísticas de ocupación")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        fila_filtros = QHBoxLayout()
        fila_filtros.addWidget(QLabel("Año"))
        self.spin_anio = QSpinBox()
        self.spin_anio.setRange(2000, 2100)
        fila_filtros.addWidget(self.spin_anio)
        fila_filtros.addWidget(QLabel("Mes"))
        self.spin_mes = QSpinBox()
        self.spin_mes.setRange(1, 12)
        fila_filtros.addWidget(self.spin_mes)
        boton_calcular = QPushButton("Calcular ocupación")
        boton_calcular.setObjectName("botonPrimario")
        boton_calcular.clicked.connect(self._calcular)
        fila_filtros.addWidget(boton_calcular)
        fila_filtros.addStretch()
        layout.addLayout(fila_filtros)

        self.etiqueta_general = QLabel()
        self.etiqueta_general.setObjectName("subtitulo")
        layout.addWidget(self.etiqueta_general)

        splitter = QSplitter()
        self.tabla_edificios = QTableWidget()
        self.tabla_edificios.setColumnCount(2)
        self.tabla_edificios.setHorizontalHeaderLabels(["Edificio", "% Ocupación"])
        self.tabla_edificios.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.tabla_edificios)

        self.tabla_unidades = QTableWidget()
        self.tabla_unidades.setColumnCount(2)
        self.tabla_unidades.setHorizontalHeaderLabels(["Unidad", "% Ocupación"])
        self.tabla_unidades.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.tabla_unidades)

        self.tabla_consultorios = QTableWidget()
        self.tabla_consultorios.setColumnCount(2)
        self.tabla_consultorios.setHorizontalHeaderLabels(["Consultorio", "% Ocupación"])
        self.tabla_consultorios.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.tabla_consultorios)
        layout.addWidget(splitter, stretch=1)

        layout.addWidget(QLabel("Historial de snapshots mensuales"))
        self.tabla_snapshots = QTableWidget()
        self.tabla_snapshots.setColumnCount(4)
        self.tabla_snapshots.setHorizontalHeaderLabels(
            ["Período", "Fecha de generación", "% Ocupación general", "% Aumento aplicado"]
        )
        self.tabla_snapshots.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla_snapshots, stretch=1)

        periodo = periodo_actual(self.conn)
        anio, mes = (int(p) for p in periodo.split("-"))
        self.spin_anio.setValue(anio)
        self.spin_mes.setValue(mes)

    def actualizar(self) -> None:
        self._calcular()
        self._actualizar_snapshots()

    def _calcular(self) -> None:
        ocupacion = calcular_ocupacion(self.conn, self.spin_anio.value(), self.spin_mes.value())
        self.etiqueta_general.setText(f"Ocupación general: {ocupacion.general:.1f}%")

        self.tabla_edificios.setRowCount(len(ocupacion.por_edificio))
        for i, agregado in enumerate(ocupacion.por_edificio.values()):
            self.tabla_edificios.setItem(i, 0, QTableWidgetItem(agregado.nombre))
            self.tabla_edificios.setItem(i, 1, QTableWidgetItem(f"{agregado.porcentaje:.1f}%"))
        self.tabla_edificios.resizeColumnsToContents()

        self.tabla_unidades.setRowCount(len(ocupacion.por_unidad))
        for i, agregado in enumerate(ocupacion.por_unidad.values()):
            self.tabla_unidades.setItem(i, 0, QTableWidgetItem(agregado.nombre))
            self.tabla_unidades.setItem(i, 1, QTableWidgetItem(f"{agregado.porcentaje:.1f}%"))
        self.tabla_unidades.resizeColumnsToContents()

        self.tabla_consultorios.setRowCount(len(ocupacion.por_consultorio))
        for i, c in enumerate(ocupacion.por_consultorio.values()):
            etiqueta = f"{c.edificio} - {c.unidad} - Consultorio {c.numero}"
            self.tabla_consultorios.setItem(i, 0, QTableWidgetItem(etiqueta))
            self.tabla_consultorios.setItem(i, 1, QTableWidgetItem(f"{c.porcentaje:.1f}%"))
        self.tabla_consultorios.resizeColumnsToContents()

    def _actualizar_snapshots(self) -> None:
        snapshots = obtener_repositorio(self.conn, "SnapshotMensual").listar()
        snapshots = sorted(snapshots, key=lambda s: s["Periodo"], reverse=True)
        self.tabla_snapshots.setRowCount(len(snapshots))
        for i, s in enumerate(snapshots):
            self.tabla_snapshots.setItem(i, 0, QTableWidgetItem(s["Periodo"]))
            self.tabla_snapshots.setItem(i, 1, QTableWidgetItem(s["FechaGeneracion"] or ""))
            general = s["PorcentajeOcupacionGeneral"]
            self.tabla_snapshots.setItem(i, 2, QTableWidgetItem(f"{general:.1f}%" if general is not None else ""))
            aumento = s["PorcentajeAumentoAplicado"]
            self.tabla_snapshots.setItem(i, 3, QTableWidgetItem(f"{aumento:.1f}%" if aumento is not None else ""))
        self.tabla_snapshots.resizeColumnsToContents()
