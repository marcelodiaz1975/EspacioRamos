"""Selector de profesional buscable (confirmado por la clienta en la
revisión de Estado de cuenta - Pagos: tiene que correr igual en todos los
selectores de profesional del sistema, actuales y futuros).

`habilitar_busqueda_profesional` toma un QComboBox YA poblado (con el id
de profesional como dato de cada ítem, texto en el formato canónico
"{código} - {tratamiento} {nombre} {apellido}" de
`app.gui.pantallas.reservas._texto_profesional`) y le agrega: tipear
filtra las opciones por cualquier parte del texto (código o nombre, no
solo desde el principio) sin distinguir mayúsculas de minúsculas NI
vocales acentuadas ("Diaz" encuentra "Díaz"), y al perder el foco
confirma la única opción que matchea lo tipeado — si no matchea
ninguna, o matchea más de una, vuelve al texto de la selección vigente
en vez de dejar un texto suelto que no se corresponde con ningún
profesional.

El filtrado nativo de `QCompleter` (`setFilterMode`/`setCaseSensitivity`)
solo resuelve mayúsculas/minúsculas, no tildes — por eso el completer usa
acá un `QSortFilterProxyModel` con `filterAcceptsRow` reimplementado a
mano en vez de esos dos métodos."""
from __future__ import annotations

import unicodedata

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QComboBox


def _sin_acentos(texto: str) -> str:
    """Mismo criterio que `app.importacion.importar_excel.
    _normalizar_encabezado` (duplicado acá, no importado: son dominios
    sin relación entre sí) — saca tildes/diéresis descomponiendo cada
    letra en base + diacrítico y quedándose solo con la base."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _normalizar(texto: str) -> str:
    return _sin_acentos(texto).casefold()


class _ProxyBusquedaSinAcentos(QSortFilterProxyModel):
    """Filtra filas por substring sin distinguir mayúsculas/minúsculas ni
    acentos — ver el porqué en el docstring del módulo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._patron = ""

    def establecer_patron(self, texto: str) -> None:
        self._patron = _normalizar(texto)
        self.invalidateRowsFilter()

    def filterAcceptsRow(self, fila: int, padre) -> bool:  # noqa: N802 (override de Qt)
        if not self._patron:
            return True
        origen = self.sourceModel()
        indice = origen.index(fila, 0, padre)
        texto = origen.data(indice, Qt.ItemDataRole.DisplayRole) or ""
        return self._patron in _normalizar(texto)


def habilitar_busqueda_profesional(combo: QComboBox) -> None:
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    proxy = _ProxyBusquedaSinAcentos(combo)
    proxy.setSourceModel(combo.model())
    completador = combo.completer()
    completador.setModel(proxy)
    completador.setCompletionColumn(0)
    combo.lineEdit().textEdited.connect(proxy.establecer_patron)
    combo.lineEdit().editingFinished.connect(lambda: _confirmar_texto(combo))


def _confirmar_texto(combo: QComboBox) -> None:
    texto = combo.currentText().strip()
    indice = combo.findText(texto, Qt.MatchFlag.MatchFixedString)
    if indice < 0 and texto:
        # Coincidencia parcial (ej. tipeó solo "r1" o "lo veci", sin
        # completar con la sugerencia del desplegable): se acepta solo si
        # matchea una única opción — con más de una (ej. "r1" matchea
        # tanto "R1" como "R10") no hay forma de saber cuál quiso decir,
        # así que no se adivina.
        patron = _normalizar(texto)
        coincidencias = [i for i in range(combo.count()) if patron in _normalizar(combo.itemText(i))]
        if len(coincidencias) == 1:
            indice = coincidencias[0]
    if indice >= 0:
        if indice != combo.currentIndex():
            combo.setCurrentIndex(indice)
        return
    indice_actual = combo.currentIndex()
    combo.setEditText(combo.itemText(indice_actual) if indice_actual >= 0 else "")
