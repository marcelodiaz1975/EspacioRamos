"""Proceso de liquidación mensual (F22/F26, sección 4.1): calcula la
vista previa de la liquidación de cada profesional categoría R para el
período, permite emitirlas (persistir en LiquidacionEmitida + acreditar
a SaldoCuentaActual, DC-09 §2) y generar el PDF de cada una en
Profesionales/{código} del profesional correspondiente.

Dos solapas: "Emisión de archivos" (F22, lo de siempre) y "Estado de
cuenta" (F26 — antes vivía en la pantalla separada "Estado de cuenta",
suprimida: sus tres solapas pasaron a vivir cada una en el formulario
que ya arma ese tipo de movimiento — ver también Pagos F21/F25 y
Cargos especiales F28/F25, confirmado por la clienta)."""
from __future__ import annotations

import os
import sqlite3

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.pantallas.reservas import _numero_codigo, _opciones_profesional, _texto_profesional
from app.gui.widgets.resumen_saldo import TEXTO_SIN_PROFESIONAL, item_monto, texto_resumen
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.archivos_generados import carpeta_base, carpeta_profesional
from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.liquidaciones import calcular_liquidacion, emitir_liquidacion
from app.pdf.liquidacion_pdf import generar_pdf_liquidacion
from app.repositorio.registro import obtener_repositorio

_COLOR_RESALTADO = QColor("#D9D9D9")
_ANCHO_COMBO_PROFESIONAL = 260


class ProcesoLiquidacion(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Proceso de liquidación mensual")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_emision = _PanelEmisionArchivos(conn)
        self.panel_estado_cuenta = _PanelEstadoCuentaLiquidaciones(conn)
        self.pestanas.addTab(self.panel_emision, "Emisión de archivos")
        self.pestanas.addTab(self.panel_estado_cuenta, "Estado de cuenta")
        layout.addWidget(self.pestanas, stretch=1)

    def actualizar(self) -> None:
        self.panel_emision.actualizar()
        self.panel_estado_cuenta.actualizar()


class _PanelEmisionArchivos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._filas: list[dict] = []
        self._casillas: list[QCheckBox] = []
        self._id_resaltado: int | None = None
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        fila_filtros = QHBoxLayout()
        fila_filtros.addWidget(QLabel("Período:"))
        self.campo_periodo = QLineEdit()
        self.campo_periodo.editingFinished.connect(self.actualizar)
        fila_filtros.addWidget(self.campo_periodo)

        boton_calcular = QPushButton("Calcular")
        boton_calcular.clicked.connect(self.actualizar)
        fila_filtros.addWidget(boton_calcular)

        fila_filtros.addWidget(QLabel("Buscar profesional:"))
        self.combo_buscar = QComboBox()
        self.combo_buscar.addItem("", None)
        for id_, etiqueta in _opciones_profesional(self.conn, ("R",)):
            self.combo_buscar.addItem(etiqueta, id_)
        habilitar_busqueda_profesional(self.combo_buscar)
        self.combo_buscar.currentIndexChanged.connect(self._resaltar_buscado)
        fila_filtros.addWidget(self.combo_buscar)

        fila_filtros.addStretch()
        layout.addLayout(fila_filtros)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(
            ["Incluir", "Profesional", "Saldo anterior", "Monto a generar", "Estado"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tabla, stretch=1)

        fila_botones = QHBoxLayout()
        boton_emitir = QPushButton("Emitir liquidaciones seleccionadas y generar PDFs")
        boton_emitir.setObjectName("botonPrimario")
        boton_emitir.clicked.connect(self._emitir_seleccionadas)
        fila_botones.addWidget(boton_emitir)
        boton_emitir_no_enviadas = QPushButton("Emitir todas las liquidaciones que no se hayan enviado")
        boton_emitir_no_enviadas.clicked.connect(self._emitir_no_enviadas)
        fila_botones.addWidget(boton_emitir_no_enviadas)
        layout.addLayout(fila_botones)

        self.campo_periodo.setText(periodo_actual(self.conn))

    def _periodo(self) -> str:
        return self.campo_periodo.text().strip() or periodo_actual(self.conn)

    def actualizar(self) -> None:
        """Sin selección por defecto (el operador elige a quién emitir a
        propósito) y orden fijo: no enviadas primero, luego por código de
        profesional — confirmado por la clienta."""
        periodo = self._periodo()
        profesionales = obtener_repositorio(self.conn, "Profesional").listar(CategoriaProfesional="R")
        filas: list[dict] = []
        for profesional in profesionales:
            try:
                liquidacion = calcular_liquidacion(
                    self.conn, id_profesional=profesional["IdProfesional"], periodo=periodo
                )
                monto_generado, monto_error = liquidacion.monto_generado, None
            except ValueError as error:
                monto_generado, monto_error = None, str(error)
            ultima = self.conn.execute(
                "SELECT EstadoEnvio FROM LiquidacionEmitida WHERE IdProfesional = ? AND Periodo = ? "
                "ORDER BY IdLiquidacion DESC LIMIT 1",
                (profesional["IdProfesional"], periodo),
            ).fetchone()
            estado = ultima["EstadoEnvio"] if ultima else "Sin emitir"
            filas.append({
                "profesional": profesional, "monto_generado": monto_generado, "monto_error": monto_error,
                "estado": estado,
            })
        filas.sort(key=lambda f: _numero_codigo(f["profesional"]["IdCodigo"]))
        filas.sort(key=lambda f: f["estado"] == "Enviada")  # estable: no enviadas arriba
        self._filas = filas

        self._casillas = []
        self.tabla.setRowCount(len(filas))
        for fila_idx, f in enumerate(filas):
            profesional = f["profesional"]
            casilla = QCheckBox()
            casilla.setChecked(False)
            self.tabla.setCellWidget(fila_idx, 0, casilla)
            self._casillas.append(casilla)

            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(_texto_profesional(profesional)))
            self.tabla.setItem(fila_idx, 2, item_monto(profesional["SaldoCuentaAnterior"]))
            if f["monto_error"] is not None:
                self.tabla.setItem(fila_idx, 3, QTableWidgetItem(f["monto_error"]))
            else:
                self.tabla.setItem(fila_idx, 3, item_monto(f["monto_generado"]))
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(f["estado"]))
        self.tabla.resizeColumnsToContents()
        self._aplicar_resaltado()

    def _resaltar_buscado(self) -> None:
        self._id_resaltado = self.combo_buscar.currentData()
        self._aplicar_resaltado()

    def _aplicar_resaltado(self) -> None:
        """El buscador de profesional es solo para ubicarlo de un
        vistazo (una fila gris) — nunca filtra ni cambia la selección de
        checkboxes, confirmado por la clienta."""
        for fila_idx, f in enumerate(self._filas):
            resaltar = (
                self._id_resaltado is not None and f["profesional"]["IdProfesional"] == self._id_resaltado
            )
            for col in range(1, 5):
                item = self.tabla.item(fila_idx, col)
                if item is not None:
                    item.setBackground(_COLOR_RESALTADO if resaltar else QBrush())

    def _emitir(self, seleccionados: list[sqlite3.Row]) -> None:
        periodo = self._periodo()
        if carpeta_base(self.conn) is None:
            QMessageBox.warning(
                self, "Emitir liquidaciones", "Configurá primero la carpeta base de archivos en Configuración general.",
            )
            return
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
                directorio = str(carpeta_profesional(self.conn, profesional["IdCodigo"]))
                ruta = generar_pdf_liquidacion(self.conn, liquidacion, directorio)
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

    def _emitir_seleccionadas(self) -> None:
        seleccionados = [f["profesional"] for f, casilla in zip(self._filas, self._casillas) if casilla.isChecked()]
        self._emitir(seleccionados)

    def _emitir_no_enviadas(self) -> None:
        seleccionados = [f["profesional"] for f in self._filas if f["estado"] != "Enviada"]
        self._emitir(seleccionados)


class _PanelEstadoCuentaLiquidaciones(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        fila_profesional = QHBoxLayout()
        self.combo_profesional = QComboBox()
        self.combo_profesional.setMinimumWidth(_ANCHO_COMBO_PROFESIONAL)
        habilitar_busqueda_profesional(self.combo_profesional)
        self.combo_profesional.currentIndexChanged.connect(self._actualizar_datos)
        fila_profesional.addWidget(QLabel("Profesional:"))
        fila_profesional.addWidget(self.combo_profesional, stretch=1)
        layout.addLayout(fila_profesional)

        self.etiqueta_resumen = QLabel()
        layout.addWidget(self.etiqueta_resumen)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Período", "Fecha emisión", "Monto generado", "Reemisión", "Estado de envío", "Archivo"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla, stretch=1)

    def actualizar(self) -> None:
        id_anterior = self.combo_profesional.currentData()
        self.combo_profesional.blockSignals(True)
        self.combo_profesional.clear()
        for id_, etiqueta in _opciones_profesional(self.conn):
            self.combo_profesional.addItem(etiqueta, id_)
        indice = self.combo_profesional.findData(id_anterior)
        self.combo_profesional.setCurrentIndex(indice if indice >= 0 else 0)
        self.combo_profesional.blockSignals(False)
        self._actualizar_datos()

    def _actualizar_datos(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            self.etiqueta_resumen.setText(TEXTO_SIN_PROFESIONAL)
            self.tabla.setRowCount(0)
            return
        self.etiqueta_resumen.setText(texto_resumen(self.conn, id_profesional))
        registros = sorted(
            obtener_repositorio(self.conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional),
            key=lambda r: r["Periodo"], reverse=True,
        )
        self.tabla.setRowCount(len(registros))
        for i, r in enumerate(registros):
            self.tabla.setItem(i, 0, QTableWidgetItem(r["Periodo"]))
            self.tabla.setItem(i, 1, QTableWidgetItem(r["FechaEmision"] or ""))
            self.tabla.setItem(i, 2, item_monto(r["MontoGenerado"]))
            self.tabla.setItem(i, 3, QTableWidgetItem("Sí" if r["EsReemision"] else "No"))
            self.tabla.setItem(i, 4, QTableWidgetItem(r["EstadoEnvio"]))
            self.tabla.setItem(i, 5, QTableWidgetItem(r["NombreArchivo"] or ""))
        self.tabla.resizeColumnsToContents()
