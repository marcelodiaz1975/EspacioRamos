"""Helpers compartidos para `QDateEdit`, pedidos de alcance general de
la clienta aplicados a todos los selectores de fecha del sistema."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QTextCharFormat
from PySide6.QtWidgets import QDateEdit


def aplicar_color_sabado_negro(campo: QDateEdit) -> None:
    """El color de la fuente del día sábado en el calendario emergente
    tiene que ser negro — por default Qt lo pinta en un tono distinto
    (igual que el domingo) para distinguir el fin de semana, pero la
    clienta solo pidió corregir el sábado.

    Requiere que `campo` ya tenga `setCalendarPopup(True)` — sin
    calendario emergente no hay `calendarWidget()` sobre el que aplicar
    el formato."""
    calendario = campo.calendarWidget()
    if calendario is None:
        return
    formato = QTextCharFormat(calendario.weekdayTextFormat(Qt.DayOfWeek.Saturday))
    formato.setForeground(Qt.GlobalColor.black)
    calendario.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, formato)


class _FlechasCambianFechaCompleta(QObject):
    """Ver `instalar_flechas_cambian_fecha_completa`."""

    def __init__(self, campo: QDateEdit, parent=None) -> None:
        super().__init__(parent)
        self._campo = campo

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (override de Qt)
        if event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Up, Qt.Key.Key_Down,
        ):
            dias = 1 if event.key() == Qt.Key.Key_Up else -1
            self._campo.setDate(self._campo.date().addDays(dias))
            return True
        return False


def instalar_flechas_cambian_fecha_completa(campo: QDateEdit) -> None:
    """Pedido de la clienta: Flecha arriba/abajo tiene que mover la
    fecha de a un día real, sin quedar atado al mes ni a la semana en
    curso.

    Por default, Qt mueve el VALOR DE LA SECCIÓN donde está el cursor
    (día, mes, año, o -si el formato tiene "ddd"- día de la semana), no
    la fecha completa. Confirmado con un script de prueba, dos bugs
    reales por eso:
    - Con el cursor sobre "dd" (día de mes): al llegar al último día
      del mes, Flecha arriba se queda clavado ahí — nunca pasa al mes
      siguiente.
    - Con el cursor sobre "ddd" (día de semana — la sección que arranca
      enfocada en los campos con ese formato, ej. Registro de
      ausencias): al llegar al último día de la semana, Flecha arriba
      salta HACIA ATRÁS al mismo día de la semana anterior y se queda
      trabado repitiendo esa misma fecha.

    Se intercepta Flecha arriba/abajo con un event filter sobre el
    propio campo y se avanza/retrocede la FECHA completa
    (`QDate.addDays`) en vez de dejar que Qt mueva la sección — sin
    importar dónde esté el cursor. El límite real de negocio (no
    permitir elegir una fecha de un período ya cerrado, etc.) no se
    valida acá: lo sigue poniendo, como siempre, quien procesa el valor
    al guardar (`crear_reserva_regular`/`modificar_reserva_regular`,
    etc.), igual que si la fecha se hubiera tipeado o elegido del
    calendario."""
    filtro = _FlechasCambianFechaCompleta(campo, parent=campo)
    campo.installEventFilter(filtro)
