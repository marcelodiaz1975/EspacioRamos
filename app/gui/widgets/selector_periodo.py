"""Selector de período (Año + Mes) para reemplazar el campo de texto libre
"AAAA-MM" — pedido de la clienta: "poder elegir un período más fácil, con
un desplegable de año y otro de mes, en vez de tener que tipearlo a mano".
Arranca en Liquidaciones > "Emisión de archivos" (el caso puntual que
pidió primero); pensado para reusarse en cualquier otro campo de período
del sistema que hoy sea un `QLineEdit` con formato "AAAA-MM" libre, sin
tener que repetir este armado.

No reemplaza `app.negocio.validaciones.es_periodo_valido`/`FORMATO_PERIODO`
en ningún lado — como los dos combos solo ofrecen valores ya válidos, no
hace falta validar nada al leer `periodo()`."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QSpinBox, QWidget

from app.negocio.dias import fecha_actual
from app.negocio.formato import MESES

_ANIO_MINIMO = 2000
_ANIO_MAXIMO = 2100


class SelectorPeriodo(QWidget):
    """Año (`QSpinBox`) + Mes (`QComboBox`, "Enero".."Diciembre") — arranca
    en el período actual (`periodo_actual`, respeta la fecha ficticia de
    QA). `cambiado` se emite al tocar cualquiera de los dos, mismo
    criterio que `currentIndexChanged` de cualquier combo del sistema."""

    cambiado = Signal()

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.spin_anio = QSpinBox()
        self.spin_anio.setRange(_ANIO_MINIMO, _ANIO_MAXIMO)
        self.spin_anio.valueChanged.connect(self._emitir_cambiado)
        layout.addWidget(self.spin_anio)

        self.combo_mes = QComboBox()
        for mes in MESES[1:]:
            self.combo_mes.addItem(mes.capitalize())
        self.combo_mes.currentIndexChanged.connect(self._emitir_cambiado)
        layout.addWidget(self.combo_mes, stretch=1)

        hoy = fecha_actual(conn)
        self.spin_anio.setValue(hoy.year)
        self.combo_mes.setCurrentIndex(hoy.month - 1)

    def _emitir_cambiado(self, *_args) -> None:
        self.cambiado.emit()

    def periodo(self) -> str:
        return f"{self.spin_anio.value():04d}-{self.combo_mes.currentIndex() + 1:02d}"

    def set_periodo(self, periodo: str) -> None:
        anio, mes = periodo.split("-")
        self.spin_anio.setValue(int(anio))
        self.combo_mes.setCurrentIndex(int(mes) - 1)

    def setFocus(self, *args, **kwargs) -> None:  # noqa: N802 (override de Qt)
        self.spin_anio.setFocus(*args, **kwargs)
