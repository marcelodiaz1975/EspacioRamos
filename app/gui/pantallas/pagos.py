"""Pagos y planes de pago (secciones 3.6 y 3.23, DC-09 §3 y §8): registrar
pagos y administrar planes de pago reusando app.negocio.pagos, para que
los descuentos de saldo (SaldoCuentaActual/SaldoCuentaAnterior según el
período imputado) y la generación de cuotas se calculen siempre igual que
por código."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.pagos import cancelar_plan, crear_plan_pago, registrar_pago
from app.repositorio.registro import obtener_repositorio


def _combo_profesionales(conn: sqlite3.Connection) -> QComboBox:
    combo = QComboBox()
    for f in conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido"):
        combo.addItem(f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", "), f["IdProfesional"])
    return combo


def _nombre_profesional(cache: dict[int, sqlite3.Row], id_profesional: int) -> str:
    p = cache.get(id_profesional)
    return p["Apellido"] if p else "?"


class PantallaPagos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Pagos")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        pestanas = QTabWidget()
        self.panel_pagos = _PanelRegistrarPago(conn)
        self.panel_planes = _PanelPlanesPago(conn)
        pestanas.addTab(self.panel_pagos, "Registrar pago")
        pestanas.addTab(self.panel_planes, "Planes de pago")
        layout.addWidget(pestanas, stretch=1)

    def actualizar(self) -> None:
        self.panel_pagos.actualizar()
        self.panel_planes.actualizar()


class _PanelRegistrarPago(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        self.combo_profesional = _combo_profesionales(self.conn)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMaximum(100_000_000)
        form.addWidget(QLabel("Monto"))
        form.addWidget(self.spin_monto)

        self.campo_fecha = QLineEdit()
        self.campo_fecha.setPlaceholderText("AAAA-MM-DD")
        form.addWidget(QLabel("Fecha"))
        form.addWidget(self.campo_fecha)

        self.campo_medio_pago = QLineEdit()
        form.addWidget(QLabel("Medio de pago"))
        form.addWidget(self.campo_medio_pago)

        self.campo_periodo = QLineEdit()
        self.campo_periodo.setPlaceholderText("AAAA-MM (a qué período se imputa)")
        form.addWidget(QLabel("Período imputado"))
        form.addWidget(self.campo_periodo)

        self.casilla_ajuste = QCheckBox("Es ajuste")
        form.addWidget(self.casilla_ajuste)

        boton = QPushButton("Registrar pago")
        boton.setObjectName("botonPrimario")
        boton.clicked.connect(self._registrar)
        form.addWidget(boton)
        form.addStretch()
        splitter.addWidget(panel_form)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["Profesional", "Fecha", "Monto", "Medio de pago", "Período imputado"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.tabla)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.campo_fecha.setText(fecha_actual(self.conn).isoformat())

    def actualizar(self) -> None:
        registros = obtener_repositorio(self.conn, "HistorialPagos").listar()
        cache = {p["IdProfesional"]: p for p in obtener_repositorio(self.conn, "Profesional").listar()}
        self.tabla.setRowCount(len(registros))
        for i, r in enumerate(registros):
            self.tabla.setItem(i, 0, QTableWidgetItem(_nombre_profesional(cache, r["IdProfesional"])))
            self.tabla.setItem(i, 1, QTableWidgetItem(r["Fecha"] or ""))
            etiqueta_monto = f"$ {r['Monto']:,.2f}" + (" (ajuste)" if r["EsAjuste"] else "")
            self.tabla.setItem(i, 2, QTableWidgetItem(etiqueta_monto))
            self.tabla.setItem(i, 3, QTableWidgetItem(r["MedioPago"] or ""))
            self.tabla.setItem(i, 4, QTableWidgetItem(r["PeriodoImputado"] or ""))
        self.tabla.resizeColumnsToContents()

    def _registrar(self) -> None:
        monto = self.spin_monto.value()
        if monto <= 0:
            QMessageBox.warning(self, "Registrar pago", "El monto debe ser mayor a cero.")
            return
        try:
            registrar_pago(
                self.conn, id_profesional=self.combo_profesional.currentData(), monto=monto,
                fecha=self.campo_fecha.text().strip() or None,
                medio_pago=self.campo_medio_pago.text().strip() or None,
                periodo_imputado=self.campo_periodo.text().strip() or None,
                es_ajuste=self.casilla_ajuste.isChecked(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Registrar pago", str(error))
            return
        self.conn.commit()
        self.actualizar()


class _PanelPlanesPago(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._planes: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        self.combo_profesional = _combo_profesionales(self.conn)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMaximum(100_000_000)
        form.addWidget(QLabel("Monto a refinanciar"))
        form.addWidget(self.spin_monto)

        self.spin_cuotas = QSpinBox()
        self.spin_cuotas.setRange(1, 60)
        self.spin_cuotas.setValue(3)
        form.addWidget(QLabel("Cantidad de cuotas"))
        form.addWidget(self.spin_cuotas)

        self.spin_interes = QDoubleSpinBox()
        self.spin_interes.setRange(0, 100)
        form.addWidget(QLabel("% Interés mensual"))
        form.addWidget(self.spin_interes)

        self.campo_mes_inicio = QLineEdit()
        self.campo_mes_inicio.setPlaceholderText("AAAA-MM")
        form.addWidget(QLabel("Mes de inicio"))
        form.addWidget(self.campo_mes_inicio)

        boton_crear = QPushButton("Crear plan de pagos")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.clicked.connect(self._crear)
        form.addWidget(boton_crear)

        boton_cancelar = QPushButton("Cancelar plan seleccionado")
        boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(boton_cancelar)
        form.addStretch()
        splitter.addWidget(panel_form)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Profesional", "Monto refinanciado", "Cuotas", "Importe por cuota", "Inicio", "Estado"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        splitter.addWidget(self.tabla)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.campo_mes_inicio.setText(periodo_actual(self.conn))

    def actualizar(self) -> None:
        self._planes = obtener_repositorio(self.conn, "PlanPago").listar()
        cache = {p["IdProfesional"]: p for p in obtener_repositorio(self.conn, "Profesional").listar()}
        self.tabla.setRowCount(len(self._planes))
        for i, p in enumerate(self._planes):
            self.tabla.setItem(i, 0, QTableWidgetItem(_nombre_profesional(cache, p["IdProfesional"])))
            self.tabla.setItem(i, 1, QTableWidgetItem(f"$ {p['MontoRefinanciado']:,.2f}"))
            self.tabla.setItem(i, 2, QTableWidgetItem(str(p["CantidadCuotas"])))
            self.tabla.setItem(i, 3, QTableWidgetItem(f"$ {p['ImportePorCuota']:,.2f}"))
            self.tabla.setItem(i, 4, QTableWidgetItem(p["MesAnoInicio"]))
            self.tabla.setItem(i, 5, QTableWidgetItem(p["Estado"]))
        self.tabla.resizeColumnsToContents()

    def _crear(self) -> None:
        monto = self.spin_monto.value()
        if monto <= 0:
            QMessageBox.warning(self, "Crear plan de pagos", "El monto a refinanciar debe ser mayor a cero.")
            return
        try:
            crear_plan_pago(
                self.conn, id_profesional=self.combo_profesional.currentData(), monto_refinanciado=monto,
                cantidad_cuotas=self.spin_cuotas.value(), mes_ano_inicio=self.campo_mes_inicio.text().strip(),
                porcentaje_interes_mensual=self.spin_interes.value(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Crear plan de pagos", str(error))
            return
        self.conn.commit()
        self.actualizar()

    def _cancelar(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return
        plan = self._planes[filas[0].row()]
        try:
            cancelar_plan(self.conn, plan["IdPlan"])
        except ValueError as error:
            QMessageBox.warning(self, "Cancelar plan", str(error))
            return
        self.conn.commit()
        self.actualizar()
