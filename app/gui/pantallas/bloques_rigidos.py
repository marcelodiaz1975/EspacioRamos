"""Bloques rígidos (F06, sección 3.11): franjas horarias que, si se
reservan, tienen que cubrirse enteras (no parcialmente) — la validación
la aplica `app.negocio.reservas.verificar_bloques_rigidos` sobre
DiasLogica; DiasVisualizacion es el conjunto de días en que la grilla
muestra ese horario como bloque rígido (puede ser más amplio que
DiasLogica, como el default de 18-21hs: lógica L-V, visualización L-S)."""
from __future__ import annotations

import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.negocio.dias import DIAS_SEMANA
from app.repositorio.registro import obtener_repositorio


def _resumen_dias(dias: list[str]) -> str:
    if dias == DIAS_SEMANA:
        return "Todos los días"
    return ", ".join(dias) if dias else "(sin días)"


class _ListaDias(QListWidget):
    def __init__(self, seleccionados: list[str] | None = None, parent=None):
        super().__init__(parent)
        seleccionados = seleccionados or []
        for dia in DIAS_SEMANA:
            item = QListWidgetItem(dia)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if dia in seleccionados else Qt.CheckState.Unchecked)
            self.addItem(item)
        self.setMaximumHeight(140)

    def seleccionados(self) -> list[str]:
        return [
            self.item(i).text() for i in range(self.count())
            if self.item(i).checkState() == Qt.CheckState.Checked
        ]


class _DialogoBloque(QDialog):
    def __init__(self, bloque: sqlite3.Row | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bloque rígido")
        layout = QFormLayout(self)

        dias_logica = json.loads(bloque["DiasLogica"]) if bloque and bloque["DiasLogica"] else []
        dias_visualizacion = json.loads(bloque["DiasVisualizacion"]) if bloque and bloque["DiasVisualizacion"] else dias_logica

        self.spin_desde = QDoubleSpinBox()
        self.spin_desde.setRange(0, 23.5)
        self.spin_desde.setSingleStep(0.5)
        self.spin_desde.setValue(bloque["HoraInicio"] if bloque else 9)
        layout.addRow("Hora inicio", self.spin_desde)

        self.spin_hasta = QDoubleSpinBox()
        self.spin_hasta.setRange(0.5, 24)
        self.spin_hasta.setSingleStep(0.5)
        self.spin_hasta.setValue(bloque["HoraFin"] if bloque else 11)
        layout.addRow("Hora fin", self.spin_hasta)

        layout.addRow(QLabel("Días en que aplica la restricción (no se puede reservar parcial)"))
        self.lista_logica = _ListaDias(dias_logica)
        layout.addRow(self.lista_logica)

        layout.addRow(QLabel("Días en que la grilla lo muestra como bloque rígido"))
        self.lista_visualizacion = _ListaDias(dias_visualizacion)
        layout.addRow(self.lista_visualizacion)

        self.casilla_activo = QCheckBox("Activo")
        self.casilla_activo.setChecked(bool(bloque["Activo"]) if bloque else True)
        layout.addRow(self.casilla_activo)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

    def _validar_y_aceptar(self) -> None:
        if self.spin_hasta.value() <= self.spin_desde.value():
            QMessageBox.warning(self, "Bloque rígido", "La hora fin tiene que ser posterior a la hora inicio.")
            return
        if not self.lista_logica.seleccionados():
            QMessageBox.warning(self, "Bloque rígido", "Elegí al menos un día para la restricción.")
            return
        if not self.lista_visualizacion.seleccionados():
            QMessageBox.warning(self, "Bloque rígido", "Elegí al menos un día para la visualización en la grilla.")
            return
        self.accept()

    def valores(self) -> dict:
        return {
            "HoraInicio": self.spin_desde.value(),
            "HoraFin": self.spin_hasta.value(),
            "DiasLogica": json.dumps(self.lista_logica.seleccionados()),
            "DiasVisualizacion": json.dumps(self.lista_visualizacion.seleccionados()),
            "Activo": 1 if self.casilla_activo.isChecked() else 0,
        }


class PantallaBloquesRigidos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.repositorio = obtener_repositorio(conn, "BloqueRigido")
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Bloques rígidos")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        fila_botones = QHBoxLayout()
        boton_nuevo = QPushButton("Nuevo")
        boton_nuevo.setObjectName("botonPrimario")
        boton_nuevo.clicked.connect(self._nuevo)
        boton_editar = QPushButton("Editar")
        boton_editar.clicked.connect(self._editar)
        boton_eliminar = QPushButton("Eliminar")
        boton_eliminar.clicked.connect(self._eliminar)
        fila_botones.addWidget(boton_nuevo)
        fila_botones.addWidget(boton_editar)
        fila_botones.addWidget(boton_eliminar)
        fila_botones.addStretch()
        layout.addLayout(fila_botones)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["Horario", "Días (restricción)", "Días (grilla)", "Activo", ""])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.doubleClicked.connect(self._editar)
        layout.addWidget(self.tabla, stretch=1)

    def actualizar(self) -> None:
        registros = self.repositorio.listar()
        self.tabla.setRowCount(len(registros))
        for fila_idx, r in enumerate(registros):
            item = QTableWidgetItem(f"{r['HoraInicio']:g} a {r['HoraFin']:g}hs")
            item.setData(Qt.ItemDataRole.UserRole, r["IdBloqueRigido"])
            self.tabla.setItem(fila_idx, 0, item)
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(_resumen_dias(json.loads(r["DiasLogica"] or "[]"))))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(_resumen_dias(json.loads(r["DiasVisualizacion"] or "[]"))))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem("Sí" if r["Activo"] else "No"))
        self.tabla.resizeColumnsToContents()

    def _fila_seleccionada_id(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self.tabla.item(filas[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _nuevo(self) -> None:
        dialogo = _DialogoBloque(parent=self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.repositorio.crear(**dialogo.valores())
            self.actualizar()

    def _editar(self) -> None:
        id_valor = self._fila_seleccionada_id()
        if id_valor is None:
            QMessageBox.information(self, "Editar", "Seleccioná un bloque para editar.")
            return
        bloque = self.repositorio.obtener(id_valor)
        dialogo = _DialogoBloque(bloque, parent=self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.repositorio.actualizar(id_valor, **dialogo.valores())
            self.actualizar()

    def _eliminar(self) -> None:
        id_valor = self._fila_seleccionada_id()
        if id_valor is None:
            QMessageBox.information(self, "Eliminar", "Seleccioná un bloque para eliminar.")
            return
        confirmacion = QMessageBox.question(self, "Eliminar", "¿Confirmás eliminar el bloque rígido seleccionado?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        self.repositorio.eliminar(id_valor)
        self.actualizar()
