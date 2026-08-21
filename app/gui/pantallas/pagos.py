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

from app.gui.dialogos import confirmar_si_periodo_imputado_es_anterior
from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.listas_editables import valores_lista
from app.negocio.pagos import cancelar_plan, crear_plan_pago, registrar_pago, suspender_descuento_periodo
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

        self.combo_medio_pago = QComboBox()
        self.combo_medio_pago.setEditable(True)
        for valor in valores_lista(self.conn, "MedioPago"):
            self.combo_medio_pago.addItem(valor)
        self.combo_medio_pago.currentTextChanged.connect(self._actualizar_visibilidad_cuenta_receptora)
        form.addWidget(QLabel("Medio de pago"))
        form.addWidget(self.combo_medio_pago)

        self.etiqueta_cuenta_receptora = QLabel("Cuenta receptora (transferencias)")
        self.combo_cuenta_receptora = QComboBox()
        self.combo_cuenta_receptora.setEditable(True)
        for valor in valores_lista(self.conn, "CuentaReceptora"):
            self.combo_cuenta_receptora.addItem(valor)
        form.addWidget(self.etiqueta_cuenta_receptora)
        form.addWidget(self.combo_cuenta_receptora)
        self._actualizar_visibilidad_cuenta_receptora()

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
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Profesional", "Fecha", "Monto", "Medio de pago", "Cuenta receptora", "Período imputado"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.tabla)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.campo_fecha.setText(fecha_actual(self.conn).isoformat())

    def _actualizar_visibilidad_cuenta_receptora(self, *_args) -> None:
        """Sección 3.6: CuentaReceptora "solo para transferencias" — se
        oculta salvo que el medio de pago elegido sea una transferencia."""
        es_transferencia = "transferencia" in self.combo_medio_pago.currentText().lower()
        self.etiqueta_cuenta_receptora.setVisible(es_transferencia)
        self.combo_cuenta_receptora.setVisible(es_transferencia)

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
            self.tabla.setItem(i, 4, QTableWidgetItem(r["CuentaReceptora"] or ""))
            self.tabla.setItem(i, 5, QTableWidgetItem(r["PeriodoImputado"] or ""))
        self.tabla.resizeColumnsToContents()

    def _registrar(self) -> None:
        monto = self.spin_monto.value()
        if monto <= 0:
            QMessageBox.warning(self, "Registrar pago", "El monto debe ser mayor a cero.")
            return
        periodo_imputado = self.campo_periodo.text().strip() or None
        if not confirmar_si_periodo_imputado_es_anterior(self, self.conn, periodo_imputado):
            return
        id_profesional = self.combo_profesional.currentData()
        es_transferencia = "transferencia" in self.combo_medio_pago.currentText().lower()
        try:
            _id_pago, cruza_tolerancia = registrar_pago(
                self.conn, id_profesional=id_profesional, monto=monto,
                fecha=self.campo_fecha.text().strip() or None,
                medio_pago=self.combo_medio_pago.currentText().strip() or None,
                cuenta_receptora=self.combo_cuenta_receptora.currentText().strip() if es_transferencia else None,
                periodo_imputado=periodo_imputado,
                es_ajuste=self.casilla_ajuste.isChecked(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Registrar pago", str(error))
            return
        if cruza_tolerancia:
            self._preguntar_restablecer_descuento(id_profesional, periodo_imputado)
        self.conn.commit()
        self.actualizar()

    def _preguntar_restablecer_descuento(self, id_profesional: int, periodo_imputado: str) -> None:
        """DC-06 §5.2: el saldo del mes anterior volvió a estar dentro de
        tolerancia con este pago. Por defecto (recomendado) el descuento
        por horas semanales queda perdido igual para esa liquidación
        puntual — los descuentos están pensados para profesionales que
        terminan al día, no para los que se pusieron al día a mitad de
        camino."""
        respuesta = QMessageBox.question(
            self, "Restablecer descuentos",
            f"El saldo del período {periodo_imputado} volvió a estar dentro de la tolerancia con este pago.\n\n"
            "¿Querés restablecerle el descuento por cantidad de horas semanales reservadas "
            "para esa liquidación?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.No:
            suspender_descuento_periodo(self.conn, id_profesional=id_profesional, periodo=periodo_imputado)


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
