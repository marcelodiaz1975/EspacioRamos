"""Configuración general (F01, sección 3.28): única fila de la tabla
Configuracion — pantalla de formulario simple en vez del CRUD genérico de
lista, porque no tiene sentido crear/eliminar filas de esta tabla."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.repositorio.registro import obtener_repositorio

_CAMPOS_TEXTO = [
    ("NombreEspacio", "Nombre del espacio"),
    ("ContactoCelular", "Celular de contacto"),
    ("ContactoEmail", "Email de contacto"),
    ("DiasGrilla", "Días de grilla (JSON)"),
    ("FrecuenciaActualizacionValores", "Frecuencia de actualización de valores"),
    ("MesesPeriodoActualizacion", "Meses del período de actualización (JSON)"),
    ("RangosEstadisticasOcupacion", "Rangos de estadísticas de ocupación (JSON)"),
    ("FrecuenciaBackupDrive", "Frecuencia de backup a Drive"),
    ("FechaFicticia", "Fecha ficticia (AAAA-MM-DD)"),
]
_CAMPOS_NUMERICOS = [
    ("HoraInicioGrilla", "Hora inicio de grilla"),
    ("HoraFinGrilla", "Hora fin de grilla"),
    ("FraccionGrilla", "Fracción de grilla (minutos)"),
    ("UmbralGiroGrilla", "Umbral de giro de grilla"),
    ("RecargoPorcentajeAisladas", "Recargo % reservas aisladas"),
    ("PorcentajeAjusteSaldoAtrasado", "% ajuste saldo atrasado"),
    ("ToleranciaDeudaDescuento", "Tolerancia deuda para descuento"),
    ("SemanasVacacionesMaximasPorAnio", "Semanas de vacaciones máximas por año"),
    ("DiasEnvioLiquidacionesRemanentes", "Días de margen para envío de liquidaciones"),
    ("DiasAntesFinMesRecordatorioPlan", "Días antes de fin de mes: recordatorio de plan"),
    ("DiasAntesFinMesRecordatorioGeneral", "Días antes de fin de mes: recordatorio general"),
    ("RetencionHistorialListaEsperaAnios", "Retención historial lista de espera (años)"),
    ("TamanoMaximoImagenMB", "Tamaño máximo de imagen (MB)"),
]
_CAMPOS_BOOLEANOS = [
    ("RecargoAisladasActivoPorDefecto", "Recargo de aisladas activo por defecto"),
    ("ModulosExtendidos", "Módulos extendidos"),
    ("ModoFechaFicticia", "Modo fecha ficticia (QA)"),
    ("MensajesPlural", 'Mensajes en plural ("les avisaremos")'),
]


class ConfiguracionGeneral(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.repositorio = obtener_repositorio(conn, "Configuracion")
        self._entradas: dict[str, QWidget] = {}
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Configuración general")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        formulario = QWidget()
        layout_formulario = QFormLayout(formulario)
        for nombre, etiqueta in _CAMPOS_TEXTO + _CAMPOS_NUMERICOS:
            entrada = QLineEdit()
            self._entradas[nombre] = entrada
            layout_formulario.addRow(etiqueta, entrada)
        for nombre, etiqueta in _CAMPOS_BOOLEANOS:
            entrada = QCheckBox()
            self._entradas[nombre] = entrada
            layout_formulario.addRow(etiqueta, entrada)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(formulario)
        layout.addWidget(scroll, stretch=1)

        boton_guardar = QPushButton("Guardar")
        boton_guardar.setObjectName("botonPrimario")
        boton_guardar.clicked.connect(self._guardar)
        layout.addWidget(boton_guardar)

    def actualizar(self) -> None:
        registro = self.repositorio.obtener(1)
        if registro is None:
            return
        for nombre, _ in _CAMPOS_TEXTO + _CAMPOS_NUMERICOS:
            valor = registro[nombre]
            self._entradas[nombre].setText("" if valor is None else str(valor))
        for nombre, _ in _CAMPOS_BOOLEANOS:
            self._entradas[nombre].setChecked(bool(registro[nombre]))

    def _guardar(self) -> None:
        valores = {}
        for nombre, etiqueta in _CAMPOS_NUMERICOS:
            texto = self._entradas[nombre].text().strip()
            if not texto:
                continue
            try:
                valores[nombre] = float(texto)
            except ValueError:
                QMessageBox.warning(self, "Guardar configuración", f"«{etiqueta}» debe ser un número.")
                return
        for nombre, _ in _CAMPOS_TEXTO:
            texto = self._entradas[nombre].text().strip()
            valores[nombre] = texto or None
        for nombre, _ in _CAMPOS_BOOLEANOS:
            valores[nombre] = 1 if self._entradas[nombre].isChecked() else 0

        self.repositorio.actualizar(1, **valores)
        QMessageBox.information(self, "Guardar configuración", "Configuración guardada.")
        self.actualizar()
