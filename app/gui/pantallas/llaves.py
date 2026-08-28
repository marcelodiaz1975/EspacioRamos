"""Pantalla de Llaves (sección 3.7): administra las llaves con el CRUD
genérico, sus accesos (LlaveAcceso — a qué edificio/unidad abre, sección
3.7) y, para la llave seleccionada, su historial de entregas y
devoluciones — reusa app.negocio.llaves.entregar_llave/devolver_llave en
vez de tocar LlaveProfesional a mano, para no saltarse la validación de
"un titular por vez" ni el cargo especial de depósito que generan.

Es F18 — asignado por nosotros en la revisión uno por uno con la
clienta: es el único número sin usar entre F16 (Reservas regulares) y
F27 (Ausencias), y no había ninguno confirmado para esta pantalla en
ningún documento del proyecto; si la planilla original de la clienta ya
le tenía otro número, hay que corregirlo acá."""
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
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.crud_generico import Campo, PantallaCRUD
from app.negocio.listas_editables import opciones_lista
from app.negocio.llaves import agregar_acceso_llave, devolver_llave, entregar_llave
from app.repositorio.registro import obtener_repositorio


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
            Campo("Tipo", "Tipo", tipo="combo", opciones=opciones_lista("TipoLlave")),
            Campo("ValorDepositoActual", "Depósito actual", tipo="numero"),
            Campo("ValorDepositoAnterior", "Depósito anterior", tipo="numero"),
            Campo("Activo", "Activo", tipo="booleano"),
        ]
        self.crud_llaves = PantallaCRUD(self.conn, "Llave", "", campos)
        self.crud_llaves.tabla_widget.itemSelectionChanged.connect(self._actualizar_tenencias)
        self.crud_llaves.tabla_widget.itemSelectionChanged.connect(self._actualizar_accesos)
        splitter.addWidget(self.crud_llaves)

        panel_tenencias = QWidget()
        layout_tenencias = QVBoxLayout(panel_tenencias)

        layout_tenencias.addWidget(QLabel("Accesos (edificios/unidades que abre)"))
        self.tabla_accesos = QTableWidget()
        self.tabla_accesos.setColumnCount(3)
        self.tabla_accesos.setHorizontalHeaderLabels(["Edificio", "Unidad", "Descripción"])
        self.tabla_accesos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_accesos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_accesos.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_accesos.setMaximumHeight(140)
        layout_tenencias.addWidget(self.tabla_accesos)

        fila_accesos = QHBoxLayout()
        self.boton_agregar_acceso = QPushButton("Agregar acceso…")
        self.boton_agregar_acceso.clicked.connect(self._agregar_acceso)
        self.boton_eliminar_acceso = QPushButton("Eliminar acceso")
        self.boton_eliminar_acceso.clicked.connect(self._eliminar_acceso)
        fila_accesos.addWidget(self.boton_agregar_acceso)
        fila_accesos.addWidget(self.boton_eliminar_acceso)
        fila_accesos.addStretch()
        layout_tenencias.addLayout(fila_accesos)

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
        self._actualizar_accesos()

    def actualizar(self) -> None:
        self.crud_llaves.actualizar()
        self._actualizar_tenencias()
        self._actualizar_accesos()

    def _accesos(self, id_llave: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT la.*, e.Nombre AS NombreEdificio, u.Departamento
            FROM LlaveAcceso la
            JOIN Edificio e ON e.IdEdificio = la.IdEdificio
            LEFT JOIN Unidad u ON u.IdUnidad = la.IdUnidad
            WHERE la.IdLlave = ? ORDER BY e.Nombre, u.Departamento
            """,
            (id_llave,),
        ).fetchall()

    def _actualizar_accesos(self) -> None:
        id_llave = self.crud_llaves.fila_seleccionada_id()
        self.boton_agregar_acceso.setEnabled(id_llave is not None)
        self.boton_eliminar_acceso.setEnabled(False)
        self._accesos_actuales: list[sqlite3.Row] = []
        self.tabla_accesos.setRowCount(0)
        if id_llave is None:
            return
        self._accesos_actuales = self._accesos(id_llave)
        self.tabla_accesos.setRowCount(len(self._accesos_actuales))
        for fila_idx, a in enumerate(self._accesos_actuales):
            self.tabla_accesos.setItem(fila_idx, 0, QTableWidgetItem(a["NombreEdificio"]))
            self.tabla_accesos.setItem(fila_idx, 1, QTableWidgetItem(a["Departamento"] or "Todas"))
            self.tabla_accesos.setItem(fila_idx, 2, QTableWidgetItem(a["DescripcionAcceso"] or ""))
        self.tabla_accesos.resizeColumnsToContents()
        self.boton_eliminar_acceso.setEnabled(bool(self._accesos_actuales))

    def _agregar_acceso(self) -> None:
        id_llave = self.crud_llaves.fila_seleccionada_id()
        if id_llave is None:
            return
        dialogo = _DialogoAcceso(self.conn, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            agregar_acceso_llave(self.conn, id_llave=id_llave, **dialogo.valores())
        except ValueError as error:
            QMessageBox.warning(self, "Agregar acceso", str(error))
            return
        self.conn.commit()
        self._actualizar_accesos()

    def _eliminar_acceso(self) -> None:
        filas = self.tabla_accesos.selectionModel().selectedRows()
        if not filas:
            QMessageBox.information(self, "Eliminar acceso", "Seleccioná un acceso para eliminar.")
            return
        acceso = self._accesos_actuales[filas[0].row()]
        obtener_repositorio(self.conn, "LlaveAcceso").eliminar(acceso["IdLlaveAcceso"])
        self.conn.commit()
        self._actualizar_accesos()

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


class _DialogoAcceso(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Agregar acceso")
        layout = QFormLayout(self)

        self.combo_edificio = QComboBox()
        for f in conn.execute("SELECT IdEdificio, Nombre FROM Edificio ORDER BY Nombre"):
            self.combo_edificio.addItem(f["Nombre"], f["IdEdificio"])
        self.combo_edificio.currentIndexChanged.connect(self._cargar_unidades)
        layout.addRow("Edificio", self.combo_edificio)

        self.combo_unidad = QComboBox()
        layout.addRow("Unidad", self.combo_unidad)
        self._cargar_unidades()

        self.campo_descripcion = QLineEdit()
        self.campo_descripcion.setPlaceholderText("Descripción del acceso (opcional)")
        layout.addRow("Descripción", self.campo_descripcion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

    def _cargar_unidades(self) -> None:
        self.combo_unidad.clear()
        self.combo_unidad.addItem("Todas las unidades del edificio", None)
        id_edificio = self.combo_edificio.currentData()
        if id_edificio is None:
            return
        for f in self.conn.execute(
            "SELECT IdUnidad, Departamento FROM Unidad WHERE IdEdificio = ? ORDER BY Departamento", (id_edificio,)
        ):
            self.combo_unidad.addItem(f["Departamento"], f["IdUnidad"])

    def valores(self) -> dict:
        return {
            "id_edificio": self.combo_edificio.currentData(),
            "id_unidad": self.combo_unidad.currentData(),
            "descripcion_acceso": self.campo_descripcion.text().strip() or None,
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
