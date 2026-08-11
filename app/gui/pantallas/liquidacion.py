"""Proceso de liquidación mensual (F22, sección 4.1): calcula la vista
previa de la liquidación de cada profesional categoría R para el período,
permite emitirlas (persistir en LiquidacionEmitida + acreditar a
SaldoCuentaActual, DC-09 §2) y generar el PDF de cada una en la carpeta
elegida."""
from __future__ import annotations

import os
import sqlite3

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.liquidaciones import calcular_liquidacion, emitir_liquidacion
from app.negocio.mensajes import nombre_para_mensaje
from app.pdf.liquidacion_pdf import generar_pdf_liquidacion
from app.repositorio.registro import obtener_repositorio


class ProcesoLiquidacion(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._profesionales: list[sqlite3.Row] = []
        self._casillas: list[QCheckBox] = []
        self._directorio_pdfs = ""
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        titulo = QLabel("Proceso de liquidación mensual")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        fila_filtros = QHBoxLayout()
        fila_filtros.addWidget(QLabel("Período:"))
        self.campo_periodo = QLineEdit()
        self.campo_periodo.editingFinished.connect(self.actualizar)
        fila_filtros.addWidget(self.campo_periodo)

        boton_calcular = QPushButton("Calcular")
        boton_calcular.clicked.connect(self.actualizar)
        fila_filtros.addWidget(boton_calcular)

        boton_carpeta = QPushButton("Elegir carpeta de destino…")
        boton_carpeta.clicked.connect(self._elegir_carpeta)
        fila_filtros.addWidget(boton_carpeta)
        fila_filtros.addStretch()
        layout.addLayout(fila_filtros)

        self.etiqueta_carpeta = QLabel("Carpeta de destino: (sin elegir)")
        self.etiqueta_carpeta.setObjectName("subtitulo")
        layout.addWidget(self.etiqueta_carpeta)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(
            ["Incluir", "Profesional", "Saldo anterior", "Monto a generar", "Última emisión"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tabla, stretch=1)

        boton_emitir = QPushButton("Emitir liquidaciones seleccionadas y generar PDFs")
        boton_emitir.setObjectName("botonPrimario")
        boton_emitir.clicked.connect(self._emitir_seleccionadas)
        layout.addWidget(boton_emitir)

        self.campo_periodo.setText(periodo_actual(self.conn))

    def _elegir_carpeta(self) -> None:
        carpeta = QFileDialog.getExistingDirectory(self, "Elegir carpeta de destino para los PDF")
        if carpeta:
            self._directorio_pdfs = carpeta
            self.etiqueta_carpeta.setText(f"Carpeta de destino: {carpeta}")

    def _periodo(self) -> str:
        return self.campo_periodo.text().strip() or periodo_actual(self.conn)

    def actualizar(self) -> None:
        periodo = self._periodo()
        self._profesionales = obtener_repositorio(self.conn, "Profesional").listar(CategoriaProfesional="R")
        self._casillas = []
        self.tabla.setRowCount(len(self._profesionales))
        for fila_idx, profesional in enumerate(self._profesionales):
            casilla = QCheckBox()
            casilla.setChecked(True)
            self.tabla.setCellWidget(fila_idx, 0, casilla)
            self._casillas.append(casilla)

            nombre = f"{nombre_para_mensaje(profesional)} ({profesional['Apellido']})"
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(nombre))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(f"$ {profesional['SaldoCuentaAnterior']:,.2f}"))

            try:
                liquidacion = calcular_liquidacion(
                    self.conn, id_profesional=profesional["IdProfesional"], periodo=periodo
                )
                monto_texto = f"$ {liquidacion.monto_generado:,.2f}"
            except ValueError as error:
                monto_texto = str(error)
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(monto_texto))

            ultima = self.conn.execute(
                "SELECT EstadoEnvio FROM LiquidacionEmitida WHERE IdProfesional = ? AND Periodo = ? "
                "ORDER BY IdLiquidacion DESC LIMIT 1",
                (profesional["IdProfesional"], periodo),
            ).fetchone()
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(ultima["EstadoEnvio"] if ultima else "Sin emitir"))
        self.tabla.resizeColumnsToContents()

    def _emitir_seleccionadas(self) -> None:
        periodo = self._periodo()
        if not self._directorio_pdfs:
            QMessageBox.warning(self, "Emitir liquidaciones", "Elegí primero una carpeta de destino para los PDF.")
            return
        seleccionados = [p for p, casilla in zip(self._profesionales, self._casillas) if casilla.isChecked()]
        if not seleccionados:
            QMessageBox.information(self, "Emitir liquidaciones", "No hay profesionales seleccionados.")
            return
        confirmacion = QMessageBox.question(
            self, "Emitir liquidaciones",
            f"¿Confirmás emitir la liquidación de {periodo} para {len(seleccionados)} profesional(es) "
            f"y generar sus PDF?",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return

        errores = []
        emitidas = 0
        for profesional in seleccionados:
            try:
                id_liquidacion, liquidacion = emitir_liquidacion(
                    self.conn, id_profesional=profesional["IdProfesional"], periodo=periodo,
                    fecha_emision=fecha_actual(self.conn).isoformat(),
                )
                ruta = generar_pdf_liquidacion(self.conn, liquidacion, self._directorio_pdfs)
                obtener_repositorio(self.conn, "LiquidacionEmitida").actualizar(
                    id_liquidacion, NombreArchivo=os.path.basename(ruta)
                )
                emitidas += 1
            except ValueError as error:
                errores.append(f"{profesional['Apellido']}: {error}")
        self.conn.commit()

        mensaje = f"Se emitieron {emitidas} liquidación(es)."
        if errores:
            mensaje += "\n\nErrores:\n" + "\n".join(errores)
        QMessageBox.information(self, "Emitir liquidaciones", mensaje)
        self.actualizar()
