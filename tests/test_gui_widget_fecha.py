from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDateEdit

from app.gui.widgets.fecha import aplicar_color_sabado_negro


def test_aplicar_color_sabado_negro_pinta_el_sabado_negro(qtbot):
    campo = QDateEdit()
    campo.setCalendarPopup(True)
    qtbot.addWidget(campo)

    aplicar_color_sabado_negro(campo)

    formato = campo.calendarWidget().weekdayTextFormat(Qt.DayOfWeek.Saturday)
    assert formato.foreground().color() == Qt.GlobalColor.black


def test_aplicar_color_sabado_negro_sin_calendario_no_rompe(qtbot):
    campo = QDateEdit()  # sin setCalendarPopup(True): calendarWidget() da None
    qtbot.addWidget(campo)

    aplicar_color_sabado_negro(campo)  # no debe lanzar
