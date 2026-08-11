"""Pantalla de Llaves (sección 3.7): administra las llaves con el CRUD
genérico y, para la llave seleccionada, su historial de entregas y
devoluciones — reusa app.negocio.llaves.entregar_llave/devolver_llave en
vez de tocar LlaveProfesional a mano, para no saltarse la validación de
"un titular por vez" ni el cargo especial de depósito que generan."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.crud_generico import Campo, PantallaCRUD
from app.negocio.llaves import devolver_llave, entregar_llave


def _opciones_tipo(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return [("Edificio", "Edificio"), ("Unidad", "Unidad"), ("No especificada", "No especificada")]


class PantallaLlaves(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._tenencias: list[sqlite3.Row] = []
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Llaves")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        splitter = QSplitter()
        campos = [
            Campo("Descripcion", "Descripción"),
            Campo("Tipo", "Tipo", tipo="combo", opciones=_opciones_tipo),
            Campo("ValorDepositoActual", "Depósito actual", tipo="numero"),
            Campo("ValorDepositoAnterior", "Depósito anterior", tipo="numero"),
            Campo("Activo", "Activo", tipo="booleano"),
        ]
        self.crud_llaves = PantallaCRUD(self.conn, "Llave", "", campos)
        self.crud_llaves.tabla_widget.itemSelectionChanged.connect(self._actualizar_tenencias)
        splitter.addWidget(self.crud_llaves)

        panel_tenencias = QWidget()
        layout_tenencias = QVBoxLayout(panel_tenencias)
        layout_tenencias.addWidget(QLabel("Historial de tenencia"))
        self.tabla_tenencias = QTableWidget()
        self.tabla_tenencias.setColumnCount(5)
        self.tabla_tenencias.setHorizontalHeaderLabels(
            ["Profesional", "Entrega", "Devolución", "Depósito cobrado", "Depósito reintegrado"]
        )
        self.tabla_tenencias.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout_tenencias.addWidget(self.tabla_tenencias, stretch=1)

        fila_acciones = QHBoxLayout()
        self.boton_entregar = QPushButton("Entregar…")
        self.boton_entregar.setObjectName("botonPrimario")
        self.boton_entregar.clicked.connect(self._entregar)
        self.boton_devolver = QPushButton("Registrar devolución…")
        self.boton_devolver.clicked.connect(self._devolver)
        fila_acciones.addWidget(self.boton_entregar)
        fila_acciones.addWidget(self.boton_devolver)
        fila_acciones.addStretch()
        layout_tenencias.addLayout(fila_acciones)
        splitter.addWidget(panel_tenencias)

        layout.addWidget(splitter, stretch=1)
        self._actualizar_tenencias()

    def actualizar(self) -> None:
        self.crud_llaves.actualizar()
        self._actualizar_tenencias()

    def _actualizar_tenencias(self) -> None:
        id_llave = self.crud_llaves.fila_seleccionada_id()
        self.boton_entregar.setEnabled(id_llave is not None)
        self.boton_devolver.setEnabled(False)
        self._tenencias = []
        self.tabla_tenencias.setRowCount(0)
        if id_llave is None:
            return

        self._tenencias = self.conn.execute(
            """
            SELECT lp.*, p.Apellido, p.NombrePila FROM LlaveProfesional lp
            JOIN Profesional p ON p.IdProfesional = lp.IdProfesional
            WHERE lp.IdLlave = ? ORDER BY lp.FechaEntrega DESC
            """,
            (id_llave,),
        ).fetchall()
        self.tabla_tenencias.setRowCount(len(self._tenencias))
        hay_titular_activo = False
        for fila_idx, t in enumerate(self._tenencias):
            self.tabla_tenencias.setItem(fila_idx, 0, QTableWidgetItem(f"{t['Apellido']}, {t['NombrePila'] or ''}"))
            self.tabla_tenencias.setItem(fila_idx, 1, QTableWidgetItem(t["FechaEntrega"] or ""))
            self.tabla_tenencias.setItem(fila_idx, 2, QTableWidgetItem(t["FechaDevolucion"] or ""))
            self.tabla_tenencias.setItem(fila_idx, 3, QTableWidgetItem("Sí" if t["DepositoCobrado"] else "No"))
            self.tabla_tenencias.setItem(fila_idx, 4, QTableWidgetItem("Sí" if t["DepositoReintegrado"] else "No"))
            if t["FechaDevolucion"] is None:
                hay_titular_activo = True
        self.tabla_tenencias.resizeColumnsToContents()
        self.boton_devolver.setEnabled(hay_titular_activo)

    def _entregar(self) -> None:
        id_llave = self.crud_llaves.fila_seleccionada_id()
        if id_llave is None:
            return
        dialogo = _DialogoEntrega(self.conn, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            entregar_llave(self.conn, id_llave=id_llave, **dialogo.valores())
        except ValueError as error:
            QMessageBox.warning(self, "Entregar llave", str(error))
            return
        self.conn.commit()
        self._actualizar_tenencias()

    def _devolver(self) -> None:
        activa = next((t for t in self._tenencias if t["FechaDevolucion"] is None), None)
        if activa is None:
            return
        dialogo = _DialogoDevolucion(activa, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            devolver_llave(self.conn, activa["IdLlaveProfesional"], **dialogo.valores())
        except ValueError as error:
            QMessageBox.warning(self, "Registrar devolución", str(error))
            return
        self.conn.commit()
        self._actualizar_tenencias()


class _DialogoEntrega(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Entregar llave")
        layout = QFormLayout(self)

        self.combo_profesional = QComboBox()
        for f in conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido"):
            self.combo_profesional.addItem(f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", "), f["IdProfesional"])
        layout.addRow("Profesional", self.combo_profesional)

        self.casilla_deposito = QCheckBox("Cobrar depósito")
        layout.addRow(self.casilla_deposito)
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMaximum(10_000_000)
        layout.addRow("Monto cobrado", self.spin_monto)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

    def valores(self) -> dict:
        return {
            "id_profesional": self.combo_profesional.currentData(),
            "cobrar_deposito": self.casilla_deposito.isChecked(),
            "monto_cobrado": self.spin_monto.value() or None,
        }


class _DialogoDevolucion(QDialog):
    def __init__(self, tenencia: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar devolución")
        layout = QFormLayout(self)

        self.casilla_reintegro = QCheckBox("Reintegrar depósito")
        self.casilla_reintegro.setChecked(bool(tenencia["DepositoCobrado"]))
        layout.addRow(self.casilla_reintegro)
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMaximum(10_000_000)
        self.spin_monto.setValue(tenencia["MontoCobrado"] or 0)
        layout.addRow("Monto a reintegrar", self.spin_monto)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

    def valores(self) -> dict:
        return {
            "reintegrar_deposito": self.casilla_reintegro.isChecked(),
            "monto_reintegrado": self.spin_monto.value() or None,
        }
