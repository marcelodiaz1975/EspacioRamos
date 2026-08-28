"""Convención de foco compartida por los formularios de carga rápida: al
presionar Enter en cualquier campo, el foco pasa al siguiente campo del
formulario (salteando los que estén ocultos o deshabilitados) en vez de
disparar la acción por defecto — como Tab, pero con la tecla que se usa
por costumbre al cargar datos fila por fila. En un botón, la Barra
espaciadora lo acciona (comportamiento nativo de Qt, sin tocar) y Enter
sigue la cadena en vez de accionarlo. Si el Enter cae en el último
elemento de la cadena, vuelve al principio (confirmado por la clienta:
mismo criterio en todos los formularios). Arranca en Pagos > Registrar
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
        # lo que sigue después del actual, y si no hay nada más visible/habilitado
        # ahí, se envuelve al principio de la cadena (sin volver a incluir al actual).
        candidatos = self._orden[indice + 1:] + self._orden[:indice]
        for candidato in candidatos:
            if candidato.isVisible() and candidato.isEnabled():
                candidato.setFocus()
                if hasattr(candidato, "selectAll"):
                    candidato.selectAll()
                return


def instalar_enter_avanza_foco(orden: list[QWidget], parent: QObject | None = None) -> QObject:
    """Instala el filtro de Enter-avanza-foco sobre los widgets de
    `orden`, en ese orden. Quien lo llame tiene que guardar la referencia
    devuelta (ej. `self._foco = instalar_enter_avanza_foco(...)`) para que
    no la recolecte el garbage collector de Python mientras el panel
    sigue vivo.

    `parent` debería ser siempre el panel/diálogo dueño de los widgets de
    `orden` (normalmente `self`, quien llama): sin un padre Qt, el filtro
    queda a merced del orden en que el garbage collector de Python decide
    recolectarlo — en pantallas creadas y destruidas muy seguido (ej. los
    tests de PantallaCRUD, una instancia nueva por catálogo) eso podía
    cerrar con Qt llamando a un filtro cuyo lado Python ya se liberó y
    reventar el proceso entero (segfault, no una excepción atrapable).
    Parentarlo al panel entero hace que Qt lo destruya en el momento
    correcto, junto con el resto de su árbol de widgets — parentarlo a
    uno de los widgets de `orden` en particular no alcanza, porque ese
    widget puede destruirse antes que los demás que el filtro todavía
    está observando."""
    filtro = _EnterAvanzaFoco(orden, parent=parent)
    for widget in orden:
        widget.installEventFilter(filtro)
        if isinstance(widget, QComboBox) and widget.isEditable() and widget.lineEdit() is not None:
            widget.lineEdit().installEventFilter(filtro)
    return filtro
