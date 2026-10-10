"""Tecla Delete sobre una fila de tabla (o ítem de lista) dispara la
misma acción que el botón "Eliminar"/"Anular"/"Cancelar"/"Liberar"/
"Descartar" de esa pantalla (pedido explícito de la clienta, "todo el
sistema"): instala un filtro de eventos sobre el widget que, al recibir
Key_Delete, llama directo al mismo método que ya usa el botón — no
duplica ninguna validación (fila/ítem seleccionado, avisos de
confirmación, guardarraíles) porque es, literalmente, la misma llamada
que un click en el botón ya hacía. Sirve tanto para `QTableWidget` como
para `QListWidget` (ej. la lista de documentos de Profesionales) — el
filtro de eventos no depende de ningún método propio de tabla."""
from __future__ import annotations

import weakref
from typing import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget


class _EliminarConTecla(QObject):
    def __init__(self, tabla: QWidget, accion: Callable[[], None]):
        super().__init__(tabla)
        # Referencia débil, mismo motivo documentado en OrdenTabla
        # (app/gui/widgets/orden_tabla.py): `accion` casi siempre es un
        # método atado del panel dueño de `tabla` — guardarlo fuerte
        # crearía un ciclo panel -> este objeto -> panel que confunde al
        # recolector cíclico de Qt/PySide al destruir muchos paneles
        # seguidos (ej. en los tests).
        self._accion = weakref.WeakMethod(accion) if hasattr(accion, "__self__") else weakref.ref(accion)
        tabla.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (nombre impuesto por Qt)
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Delete:
            accion = self._accion()
            if accion is not None:
                accion()
            return True
        return False


def instalar_eliminar_con_tecla(tabla: QWidget, accion: Callable[[], None]) -> QObject:
    """Instala el filtro y devuelve el objeto — el caller no necesita
    guardar la referencia (queda parentada a `tabla`), pero conviene
    igual asignarla a un atributo de la pantalla por si hiciera falta
    desinstalarla más adelante."""
    return _EliminarConTecla(tabla, accion)
