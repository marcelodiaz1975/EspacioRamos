"""Selector de profesional buscable (confirmado por la clienta en la
revisión de Estado de cuenta - Pagos: tiene que correr igual en todos los
selectores de profesional del sistema, actuales y futuros).

`habilitar_busqueda_profesional` toma un QComboBox YA poblado (con el id
de profesional como dato de cada ítem, texto en el formato canónico
"{código} - {tratamiento} {nombre} {apellido}" de
`app.gui.pantallas.reservas._texto_profesional`) y le agrega: tipear
filtra las opciones por cualquier parte del texto (código o nombre, no
solo desde el principio), y si lo tipeado no matchea ninguna opción al
perder el foco, vuelve al texto de la selección vigente en vez de dejar
un texto suelto que no se corresponde con ningún profesional."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox


def habilitar_busqueda_profesional(combo: QComboBox) -> None:
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
    combo.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    combo.lineEdit().editingFinished.connect(lambda: _confirmar_texto(combo))


def _confirmar_texto(combo: QComboBox) -> None:
    texto = combo.currentText()
    indice = combo.findText(texto, Qt.MatchFlag.MatchFixedString)
    if indice >= 0:
        if indice != combo.currentIndex():
            combo.setCurrentIndex(indice)
        return
    indice_actual = combo.currentIndex()
    combo.setEditText(combo.itemText(indice_actual) if indice_actual >= 0 else "")
