"""Orden de tablas por click en el título de columna: un click ordena por
esa columna (ascendente), un segundo click en el mismo título invierte el
sentido. El criterio elegido es transitorio — al reconstruirse el panel
(salir de la pantalla/pestaña y volver) se pierde y el panel vuelve a
mostrar su orden por defecto. No usa el sorting nativo de QTableWidget
(que compara texto de celda tal cual se ve) porque columnas como fechas
"dd-mm-aaaa" o montos "$ X.XXX,XX" no ordenan bien como texto — cada panel
sigue reconstruyendo sus filas a mano desde una lista de Python ordenada,
esta clase solo lleva el estado de qué columna/sentido eligió el usuario y
avisa cuándo hay que volver a armar la tabla con ese criterio."""
from __future__ import annotations

import weakref
from typing import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QTableWidget


class OrdenTabla(QObject):
    def __init__(self, tabla: QTableWidget, al_cambiar: Callable[[], None]):
        super().__init__(tabla)
        self._tabla = tabla
        self.columna: int | None = None
        self.ascendente = True
        # Referencia débil: `al_cambiar` casi siempre es un método atado
        # (ej. `self.actualizar`) del panel dueño de `tabla` — guardarlo
        # fuerte crearía un ciclo panel -> OrdenTabla -> panel que solo el
        # recolector cíclico de Python puede romper, y si ese recolector
        # corre mientras Qt ya venía destruyendo el árbol de widgets en su
        # propio orden (ej. al cerrar muchos paneles seguidos, como en los
        # tests), terminaba tocando un wrapper ya muerto del lado C++ y
        # reventando el proceso entero (segfault, no una excepción
        # atrapable). Con referencia débil, este objeto no sostiene la
        # vida del panel — su propia vida ya la garantiza el parentesco Qt
        # con `tabla` pasado arriba.
        self._al_cambiar = weakref.WeakMethod(al_cambiar) if hasattr(al_cambiar, "__self__") else weakref.ref(al_cambiar)
        header = tabla.horizontalHeader()
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._clic)

    def _clic(self, columna: int) -> None:
        if self.columna == columna:
            self.ascendente = not self.ascendente
        else:
            self.columna = columna
            self.ascendente = True
        self._actualizar_indicador()
        al_cambiar = self._al_cambiar()
        if al_cambiar is not None:
            al_cambiar()

    def _actualizar_indicador(self) -> None:
        from PySide6.QtCore import Qt

        header = self._tabla.horizontalHeader()
        orden = Qt.SortOrder.AscendingOrder if self.ascendente else Qt.SortOrder.DescendingOrder
        header.setSortIndicator(self.columna if self.columna is not None else -1, orden)
        header.setSortIndicatorShown(self.columna is not None)

    def reiniciar(self) -> None:
        """Vuelve al orden por defecto del panel — se llama al mostrarse
        el panel (`showEvent`), que es "salir y volver" en términos de
        Qt para una pestaña o una pantalla del stack principal."""
        if self.columna is None:
            return
        self.columna = None
        self.ascendente = True
        self._actualizar_indicador()
