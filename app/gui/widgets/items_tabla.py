"""Ítem de tabla para valores numéricos (importes, porcentajes,
cantidades, horas, etc.): alineado a la derecha de la celda — confirmado
por la clienta para todo el sistema, en la revisión uno por uno. Las
celdas de texto (nombre, código, fecha, estado) siguen a la izquierda,
sin usar este helper."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem


def item_numero(texto: str) -> QTableWidgetItem:
    item = QTableWidgetItem(texto)
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item
