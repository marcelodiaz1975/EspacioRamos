"""Convención de foco compartida por los formularios de carga rápida: al
presionar Enter en cualquier campo, el foco pasa al siguiente campo del
formulario (salteando los que estén ocultos o deshabilitados) en vez de
disparar la acción por defecto — como Tab, pero con la tecla que se usa
por costumbre al cargar datos fila por fila. Arranca en Pagos > Registrar
pago; pensado para reutilizarse en los demás formularios de carga."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QComboBox, QWidget


class _EnterAvanzaFoco(QObject):
    def __init__(self, orden: list[QWidget], parent=None):
        super().__init__(parent)
        self._orden = orden

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (nombre impuesto por Qt)
        if event.type() != QEvent.Type.KeyPress or event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return False
        objetivo = watched
        padre = watched.parentWidget() if isinstance(watched, QWidget) else None
        if isinstance(padre, QComboBox) and padre.isEditable() and padre.lineEdit() is watched:
            objetivo = padre
        self._avanzar(objetivo)
        return True

    def _avanzar(self, actual: QWidget) -> None:
        try:
            indice = self._orden.index(actual)
        except ValueError:
            return
        for candidato in self._orden[indice + 1:]:
            if candidato.isVisible() and candidato.isEnabled():
                candidato.setFocus()
                if hasattr(candidato, "selectAll"):
                    candidato.selectAll()
                return


def instalar_enter_avanza_foco(orden: list[QWidget]) -> QObject:
    """Instala el filtro de Enter-avanza-foco sobre los widgets de
    `orden`, en ese orden. Quien lo llame tiene que guardar la referencia
    devuelta (ej. `self._foco = instalar_enter_avanza_foco(...)`) para que
    no la recolecte el garbage collector de Python mientras el panel
    sigue vivo."""
    filtro = _EnterAvanzaFoco(orden)
    for widget in orden:
        widget.installEventFilter(filtro)
        if isinstance(widget, QComboBox) and widget.isEditable() and widget.lineEdit() is not None:
            widget.lineEdit().installEventFilter(filtro)
    return filtro
