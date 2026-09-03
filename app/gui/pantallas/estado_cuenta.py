"""Estado de cuenta por profesional: vista consolidada de saldo,
liquidaciones emitidas, pagos registrados y cargos especiales — solo
lectura, cada una se sigue dando de alta desde su pantalla propia
(Liquidación mensual, Pagos, Novedades).

F25/F26: F26 es la solapa "Liquidaciones" (historial de liquidaciones);
F25 es el resto de la pantalla — selector de profesional, resumen de
saldo, y las solapas "Pagos" y "Cargos especiales" (confirmado por la
clienta en la revisión uno por uno).

Las solapas "Pagos" y "Cargos especiales" replican exactamente los
campos y formatos de sus tablas propias (Pagos - Registrar pago F21, y
Cargos especiales F28), sacando la columna Profesional porque acá ya
está fija en el selector de arriba (por ahora quedan duplicadas acá,
más adelante puede que esta pantalla se suprima y cada solapa termine
viviendo directamente en su formulario propio, a confirmar). El resumen
de saldo debajo del selector cambia según la solapa activa: en Pagos
muestra pagos imputados al mes actual/anterior, en Cargos especiales
muestra cargos especiales imputados al mes actual/anterior — mismo
signo real y mismo color rojo-si-negativo en los dos casos."""
from __future__ import annotations

import sqlite3

from PySide6.QtGui import QColor
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

from app.gui.estilos import COLOR_ROJO
from app.gui.pantallas.novedades import _fmt_fecha_dia
from app.gui.pantallas.pagos import _fmt_fecha_hora_larga
from app.gui.pantallas.reservas import _opciones_profesional
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.dias import periodo_actual, periodo_anterior
from app.negocio.formato import formatear_moneda
from app.repositorio.registro import obtener_repositorio

_ANCHO_COMBO_PROFESIONAL = 260
_TAB_LIQUIDACIONES, _TAB_PAGOS, _TAB_CARGOS = range(3)


def _item_monto(valor: float | None) -> QTableWidgetItem:
    item = QTableWidgetItem(formatear_moneda(valor or 0.0))
    if (valor or 0.0) < 0:
        item.setForeground(QColor(COLOR_ROJO))
    return item


def _fmt_dato(prefijo: str, valor: float) -> str:
    """Mismo criterio de color que el resto del sistema: negativo en
    rojo (span de texto enriquecido, como ya hace Pagos - Registrar pago
    con Saldo actual/Nuevo saldo)."""
    color = COLOR_ROJO if valor < 0 else "black"
    return f'{prefijo}: <span style="color:{color};">{formatear_moneda(valor)}</span>'


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
        self.combo_profesional.setMinimumWidth(_ANCHO_COMBO_PROFESIONAL)
        habilitar_busqueda_profesional(self.combo_profesional)
        self.combo_profesional.currentIndexChanged.connect(self._actualizar_datos)
        fila_profesional.addWidget(QLabel("Profesional:"))
        fila_profesional.addWidget(self.combo_profesional, stretch=1)
        layout.addLayout(fila_profesional)

        self.etiqueta_datos_profesional = QLabel()
        layout.addWidget(self.etiqueta_datos_profesional)

        self.pestanas = QTabWidget()
        self.tabla_liquidaciones = self._tabla(
            ["Período", "Fecha emisión", "Monto generado", "Reemisión", "Estado de envío", "Archivo"]
        )
        self.tabla_pagos = self._tabla([
            "Fecha de carga", "Período imputado", "Monto", "Medio de pago", "Cuenta receptora",
            "Saldo anterior", "Nuevo saldo", "Registro modificado", "Es ajuste",
        ])
        self.tabla_cargos = self._tabla(["Fecha", "Tipo", "Concepto", "Monto", "Período imputado"])
        self.pestanas.addTab(self.tabla_liquidaciones, "Liquidaciones")
        self.pestanas.addTab(self.tabla_pagos, "Pagos")
        self.pestanas.addTab(self.tabla_cargos, "Cargos especiales")
        self.pestanas.currentChanged.connect(self._actualizar_datos)
        layout.addWidget(self.pestanas, stretch=1)

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
        for id_, etiqueta in _opciones_profesional(self.conn):
            self.combo_profesional.addItem(etiqueta, id_)
        indice = self.combo_profesional.findData(id_anterior)
        self.combo_profesional.setCurrentIndex(indice if indice >= 0 else 0)
        self.combo_profesional.blockSignals(False)
        self._actualizar_datos()

    def _actualizar_datos(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            self.etiqueta_datos_profesional.setText("Saldo actual: — - Saldo anterior: —")
            for tabla in (self.tabla_liquidaciones, self.tabla_pagos, self.tabla_cargos):
                tabla.setRowCount(0)
            return

        profesional = obtener_repositorio(self.conn, "Profesional").obtener(id_profesional)
        partes = [
            _fmt_dato("Saldo actual", profesional["SaldoCuentaActual"] or 0.0),
            _fmt_dato("Saldo anterior", profesional["SaldoCuentaAnterior"] or 0.0),
        ]
        pestana_actual = self.pestanas.currentIndex()
        if pestana_actual == _TAB_PAGOS:
            partes.extend(self._datos_imputados("Pagos", "HistorialPagos", id_profesional))
        elif pestana_actual == _TAB_CARGOS:
            partes.extend(self._datos_imputados("Cargos especiales", "CargoEspecial", id_profesional))
        self.etiqueta_datos_profesional.setText(" - ".join(partes))

        self._actualizar_liquidaciones(id_profesional)
        self._actualizar_pagos(id_profesional)
        self._actualizar_cargos(id_profesional)

    def _datos_imputados(self, etiqueta: str, entidad: str, id_profesional: int) -> list[str]:
        periodo_act = periodo_actual(self.conn)
        periodo_ant = periodo_anterior(periodo_act)
        registros = obtener_repositorio(self.conn, entidad).listar(IdProfesional=id_profesional)
        monto_actual = sum(r["Monto"] for r in registros if r["PeriodoImputado"] == periodo_act)
        monto_anterior = sum(r["Monto"] for r in registros if r["PeriodoImputado"] == periodo_ant)
        return [
            _fmt_dato(f"{etiqueta} imputados al mes actual", monto_actual),
            _fmt_dato(f"{etiqueta} imputados al mes anterior", monto_anterior),
        ]

    def _actualizar_liquidaciones(self, id_profesional: int) -> None:
        registros = sorted(
            obtener_repositorio(self.conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional),
            key=lambda r: r["Periodo"], reverse=True,
        )
        self.tabla_liquidaciones.setRowCount(len(registros))
        for i, r in enumerate(registros):
            self.tabla_liquidaciones.setItem(i, 0, QTableWidgetItem(r["Periodo"]))
            self.tabla_liquidaciones.setItem(i, 1, QTableWidgetItem(r["FechaEmision"] or ""))
            self.tabla_liquidaciones.setItem(i, 2, _item_monto(r["MontoGenerado"]))
            self.tabla_liquidaciones.setItem(i, 3, QTableWidgetItem("Sí" if r["EsReemision"] else "No"))
            self.tabla_liquidaciones.setItem(i, 4, QTableWidgetItem(r["EstadoEnvio"]))
            self.tabla_liquidaciones.setItem(i, 5, QTableWidgetItem(r["NombreArchivo"] or ""))
        self.tabla_liquidaciones.resizeColumnsToContents()

    def _actualizar_pagos(self, id_profesional: int) -> None:
        """Mismos campos y formatos que la tabla de Pagos - Registrar pago
        (F21), sin la columna Profesional (ya fija en el selector de
        arriba). Orden por defecto: IdPago descendente, lo más nuevo
        arriba — equivalente a FechaHoraCarga, igual que en F21."""
        registros = sorted(
            obtener_repositorio(self.conn, "HistorialPagos").listar(IdProfesional=id_profesional),
            key=lambda r: -r["IdPago"],
        )
        self.tabla_pagos.setRowCount(len(registros))
        for i, r in enumerate(registros):
            self.tabla_pagos.setItem(i, 0, QTableWidgetItem(_fmt_fecha_hora_larga(r["FechaHoraCarga"])))
            self.tabla_pagos.setItem(i, 1, QTableWidgetItem(r["PeriodoImputado"] or ""))
            self.tabla_pagos.setItem(i, 2, _item_monto(r["Monto"]))
            self.tabla_pagos.setItem(i, 3, QTableWidgetItem(r["MedioPago"] or ""))
            self.tabla_pagos.setItem(i, 4, QTableWidgetItem(r["CuentaReceptora"] or ""))
            self.tabla_pagos.setItem(i, 5, _item_monto(r["SaldoAnterior"]))
            self.tabla_pagos.setItem(i, 6, _item_monto(r["SaldoNuevo"]))
            self.tabla_pagos.setItem(i, 7, QTableWidgetItem("Sí" if r["RegistroModificado"] else "No"))
            self.tabla_pagos.setItem(i, 8, QTableWidgetItem("Sí" if r["EsAjuste"] else "No"))
        self.tabla_pagos.resizeColumnsToContents()

    def _actualizar_cargos(self, id_profesional: int) -> None:
        """Mismos campos y formatos que la tabla de Cargos especiales
        (F28), sin la columna Profesional (ya fija en el selector de
        arriba). Orden por defecto: fecha descendente, igual que en F28."""
        registros = sorted(
            obtener_repositorio(self.conn, "CargoEspecial").listar(IdProfesional=id_profesional),
            key=lambda r: r["Fecha"] or "", reverse=True,
        )
        self.tabla_cargos.setRowCount(len(registros))
        for i, r in enumerate(registros):
            self.tabla_cargos.setItem(i, 0, QTableWidgetItem(_fmt_fecha_dia(r["Fecha"]) if r["Fecha"] else ""))
            self.tabla_cargos.setItem(i, 1, QTableWidgetItem(r["Tipo"]))
            self.tabla_cargos.setItem(i, 2, QTableWidgetItem(r["Concepto"]))
            self.tabla_cargos.setItem(i, 3, _item_monto(r["Monto"]))
            self.tabla_cargos.setItem(i, 4, QTableWidgetItem(r["PeriodoImputado"] or ""))
        self.tabla_cargos.resizeColumnsToContents()
