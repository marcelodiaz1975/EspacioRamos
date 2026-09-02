"""Convención de foco compartida por los formularios de carga rápida: al
presionar Enter en cualquier campo, el foco pasa al siguiente campo del
formulario (salteando los que estén ocultos o deshabilitados) en vez de
disparar la acción por defecto — como Tab, pero con la tecla que se usa
por costumbre al cargar datos fila por fila. En un botón, la Barra
espaciadora lo acciona (comportamiento nativo de Qt, sin tocar) y Enter
sigue la cadena en vez de accionarlo. Si el Enter cae en el último
elemento de la cadena, vuelve al principio (confirmado por la clienta:
mismo criterio en todos los formularios). Arranca en Pagos > Registrar
pago; pensado para reutilizarse en los demás formularios de carga.

Tab/Shift+Tab siguen exactamente la misma cadena que Enter, con el mismo
salto de último a primero (y de primero a último en reversa) — pedido
explícito de la clienta en la revisión de Llaves: no puede haber una
cadena para Enter y otra distinta para Tab. A diferencia de Enter, Tab no
selecciona el contenido del campo al llegar (solo mueve el foco, sin
tocar nada). Se implementa interceptando Tab/Backtab acá mismo en vez de
recablear el focus chain nativo de Qt (`QWidget.setTabOrder`): ese chain
es uno solo por aplicación, así que empalmar ahí el orden de `orden` se
mezcla de forma impredecible con cualquier otro widget enfocable de la
pantalla que haya quedado afuera de la lista (ej. las tablas, que se
navegan con mouse/flechas, no con Tab) — interceptar la tecla acá y
mover el foco a mano con la misma lógica de `orden` es la única forma de
garantizar que la cadena sea exactamente la misma para las tres teclas."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QComboBox, QWidget


class _EnterAvanzaFoco(QObject):
    def __init__(self, orden: list[QWidget], parent=None):
        super().__init__(parent)
        self._orden = orden

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (nombre impuesto por Qt)
        if event.type() != QEvent.Type.KeyPress:
            return False
        tecla = event.key()
        if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._mover(self._resolver_objetivo(watched), retroceder=False, seleccionar_todo=True)
            return True
        if tecla in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            retroceder = tecla == Qt.Key.Key_Backtab or bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._mover(self._resolver_objetivo(watched), retroceder=retroceder, seleccionar_todo=False)
            return True
        return False

    @staticmethod
    def _resolver_objetivo(watched) -> QWidget:
        padre = watched.parentWidget() if isinstance(watched, QWidget) else None
        if isinstance(padre, QComboBox) and padre.isEditable() and padre.lineEdit() is watched:
            return padre
        return watched

    def _mover(self, actual: QWidget, retroceder: bool, seleccionar_todo: bool) -> None:
        try:
            indice = self._orden.index(actual)
        except ValueError:
            return
        if retroceder:
            # lo que precede al actual, en reversa, y si no hay nada más visible/
            # habilitado ahí, se envuelve al final de la cadena.
            candidatos = list(reversed(self._orden[:indice])) + list(reversed(self._orden[indice + 1:]))
        else:
            # lo que sigue después del actual, y si no hay nada más visible/habilitado
            # ahí, se envuelve al principio de la cadena (sin volver a incluir al actual).
            candidatos = self._orden[indice + 1:] + self._orden[:indice]
        for candidato in candidatos:
            if candidato.isVisible() and candidato.isEnabled():
                candidato.setFocus()
                if seleccionar_todo and hasattr(candidato, "selectAll"):
                    candidato.selectAll()
                return


def instalar_enter_avanza_foco(orden: list[QWidget], parent: QObject | None = None) -> QObject:
    """Instala el filtro de Enter/Tab-avanza-foco sobre los widgets de
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
