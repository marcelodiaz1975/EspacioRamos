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


def item_centrado(texto: str) -> QTableWidgetItem:
    """Excepción puntual a la regla de arriba (texto normalmente a la
    izquierda) para columnas que la clienta pidió centradas caso por
    caso — ver convención "Contenido de celda" en CLAUDE.md."""
    item = QTableWidgetItem(texto)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item
