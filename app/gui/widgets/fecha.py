"""Helper compartido para `QDateEdit`: pedido general de la clienta, el
color de la fuente del día sábado en el calendario emergente tiene que
ser negro en todos los selectores de fecha del sistema — por default Qt
lo pinta en un tono distinto (igual que el domingo) para distinguir el
fin de semana, pero la clienta solo pidió corregir el sábado."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat
from PySide6.QtWidgets import QDateEdit


def aplicar_color_sabado_negro(campo: QDateEdit) -> None:
    """Requiere que `campo` ya tenga `setCalendarPopup(True)` — sin
    calendario emergente no hay `calendarWidget()` sobre el que aplicar
    el formato."""
    calendario = campo.calendarWidget()
    if calendario is None:
        return
    formato = QTextCharFormat(calendario.weekdayTextFormat(Qt.DayOfWeek.Saturday))
    formato.setForeground(Qt.GlobalColor.black)
    calendario.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, formato)
