"""Estado de cuenta por profesional (F25/F26): vista consolidada de
saldo, liquidaciones emitidas, pagos registrados y cargos especiales —
solo lectura, cada una se sigue dando de alta desde su pantalla propia
(Liquidación mensual, Pagos, Novedades)."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.negocio.formato import formatear_moneda
from app.repositorio.registro import obtener_repositorio


class PantallaEstadoCuenta(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Estado de cuenta")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        fila_profesional = QHBoxLayout()
        self.combo_profesional = QComboBox()
        self.combo_profesional.currentIndexChanged.connect(self._actualizar_datos)
        fila_profesional.addWidget(QLabel("Profesional:"))
        fila_profesional.addWidget(self.combo_profesional, stretch=1)
        layout.addLayout(fila_profesional)

        fila_saldos = QHBoxLayout()
        self.etiqueta_saldo_actual = QLabel("Saldo actual: —")
        self.etiqueta_saldo_anterior = QLabel("Saldo anterior: —")
        fila_saldos.addWidget(self.etiqueta_saldo_actual)
        fila_saldos.addWidget(self.etiqueta_saldo_anterior)
        fila_saldos.addStretch()
        layout.addLayout(fila_saldos)

        pestanas = QTabWidget()
        self.tabla_liquidaciones = self._tabla(
            ["Período", "Fecha emisión", "Monto generado", "Reemisión", "Estado de envío", "Archivo"]
        )
        self.tabla_pagos = self._tabla(
            ["Fecha", "Monto", "Medio de pago", "Cuenta receptora", "Período imputado", "Ajuste", "Observación"]
        )
        self.tabla_cargos = self._tabla(["Tipo", "Concepto", "Monto", "Período imputado", "Observación"])
        pestanas.addTab(self.tabla_liquidaciones, "Liquidaciones")
        pestanas.addTab(self.tabla_pagos, "Pagos")
        pestanas.addTab(self.tabla_cargos, "Cargos especiales")
        layout.addWidget(pestanas, stretch=1)

    def _tabla(self, encabezados: list[str]) -> QTableWidget:
        tabla = QTableWidget()
        tabla.setColumnCount(len(encabezados))
        tabla.setHorizontalHeaderLabels(encabezados)
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        return tabla

    def actualizar(self) -> None:
        """Repuebla el combo de profesionales (por si se cargó alguno
        nuevo desde otra pantalla) conservando la selección actual, y
        refresca los datos del profesional que quede seleccionado."""
        id_anterior = self.combo_profesional.currentData()
        self.combo_profesional.blockSignals(True)
        self.combo_profesional.clear()
        for f in self.conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido"):
            self.combo_profesional.addItem(f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", "), f["IdProfesional"])
        indice = self.combo_profesional.findData(id_anterior)
        self.combo_profesional.setCurrentIndex(indice if indice >= 0 else 0)
        self.combo_profesional.blockSignals(False)
        self._actualizar_datos()

    def _actualizar_datos(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            self.etiqueta_saldo_actual.setText("Saldo actual: —")
            self.etiqueta_saldo_anterior.setText("Saldo anterior: —")
            for tabla in (self.tabla_liquidaciones, self.tabla_pagos, self.tabla_cargos):
                tabla.setRowCount(0)
            return

        profesional = obtener_repositorio(self.conn, "Profesional").obtener(id_profesional)
        self.etiqueta_saldo_actual.setText(f"Saldo actual: $ {profesional['SaldoCuentaActual']:,.2f}")
        self.etiqueta_saldo_anterior.setText(f"Saldo anterior: $ {profesional['SaldoCuentaAnterior']:,.2f}")

        self._actualizar_liquidaciones(id_profesional)
        self._actualizar_pagos(id_profesional)
        self._actualizar_cargos(id_profesional)

    def _actualizar_liquidaciones(self, id_profesional: int) -> None:
        registros = sorted(
            obtener_repositorio(self.conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional),
            key=lambda r: r["Periodo"], reverse=True,
        )
        self.tabla_liquidaciones.setRowCount(len(registros))
        for i, r in enumerate(registros):
            self.tabla_liquidaciones.setItem(i, 0, QTableWidgetItem(r["Periodo"]))
            self.tabla_liquidaciones.setItem(i, 1, QTableWidgetItem(r["FechaEmision"] or ""))
            self.tabla_liquidaciones.setItem(i, 2, QTableWidgetItem(f"$ {r['MontoGenerado']:,.2f}"))
            self.tabla_liquidaciones.setItem(i, 3, QTableWidgetItem("Sí" if r["EsReemision"] else "No"))
            self.tabla_liquidaciones.setItem(i, 4, QTableWidgetItem(r["EstadoEnvio"]))
            self.tabla_liquidaciones.setItem(i, 5, QTableWidgetItem(r["NombreArchivo"] or ""))
        self.tabla_liquidaciones.resizeColumnsToContents()

    def _actualizar_pagos(self, id_profesional: int) -> None:
        registros = sorted(
            obtener_repositorio(self.conn, "HistorialPagos").listar(IdProfesional=id_profesional),
            key=lambda r: r["Fecha"] or "", reverse=True,
        )
        self.tabla_pagos.setRowCount(len(registros))
        for i, r in enumerate(registros):
            self.tabla_pagos.setItem(i, 0, QTableWidgetItem(r["Fecha"] or ""))
            self.tabla_pagos.setItem(i, 1, QTableWidgetItem(f"$ {r['Monto']:,.2f}"))
            self.tabla_pagos.setItem(i, 2, QTableWidgetItem(r["MedioPago"] or ""))
            self.tabla_pagos.setItem(i, 3, QTableWidgetItem(r["CuentaReceptora"] or ""))
            self.tabla_pagos.setItem(i, 4, QTableWidgetItem(r["PeriodoImputado"] or ""))
            self.tabla_pagos.setItem(i, 5, QTableWidgetItem("Sí" if r["EsAjuste"] else "No"))
            self.tabla_pagos.setItem(i, 6, QTableWidgetItem(r["Observacion"] or ""))
        self.tabla_pagos.resizeColumnsToContents()

    def _actualizar_cargos(self, id_profesional: int) -> None:
        registros = obtener_repositorio(self.conn, "CargoEspecial").listar(IdProfesional=id_profesional)
        self.tabla_cargos.setRowCount(len(registros))
        for i, r in enumerate(registros):
            self.tabla_cargos.setItem(i, 0, QTableWidgetItem(r["Tipo"]))
            self.tabla_cargos.setItem(i, 1, QTableWidgetItem(r["Concepto"]))
            self.tabla_cargos.setItem(i, 2, QTableWidgetItem(formatear_moneda(r["Monto"])))
            self.tabla_cargos.setItem(i, 3, QTableWidgetItem(r["PeriodoImputado"] or ""))
            self.tabla_cargos.setItem(i, 4, QTableWidgetItem(r["Observacion"] or ""))
        self.tabla_cargos.resizeColumnsToContents()
