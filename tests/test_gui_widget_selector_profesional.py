from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional


def _combo_de_prueba() -> QComboBox:
    combo = QComboBox()
    combo.addItem("Sin selección", None)
    combo.addItem("R1 - Lic. Virginia Lo Veci", 1)
    combo.addItem("R3 - Lic. Esteban Quito", 3)
    habilitar_busqueda_profesional(combo)
    return combo


def _confirmar(combo: QComboBox, texto: str) -> None:
    combo.setEditText(texto)
    combo.lineEdit().editingFinished.emit()


def test_completer_es_insensible_a_mayusculas_y_matchea_cualquier_parte(qtbot):
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    completador = combo.completer()
    assert completador.filterMode() == Qt.MatchFlag.MatchContains
    assert completador.caseSensitivity() == Qt.CaseSensitivity.CaseInsensitive


def test_confirmar_con_codigo_en_minuscula_identifica_el_profesional(qtbot):
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    _confirmar(combo, "r1")
    assert combo.currentData() == 1
    assert combo.currentText() == "R1 - Lic. Virginia Lo Veci"


def test_confirmar_con_codigo_mayuscula_identifica_el_profesional(qtbot):
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    _confirmar(combo, "R1")
    assert combo.currentData() == 1


def test_confirmar_con_nombre_en_minuscula_identifica_el_profesional(qtbot):
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    _confirmar(combo, "lo veci")
    assert combo.currentData() == 1
    assert combo.currentText() == "R1 - Lic. Virginia Lo Veci"


def test_confirmar_con_nombre_capitalizado_identifica_el_profesional(qtbot):
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    _confirmar(combo, "Lo Veci")
    assert combo.currentData() == 1


def test_confirmar_texto_ambiguo_no_selecciona_y_revierte(qtbot):
    combo = QComboBox()
    combo.addItem("Sin selección", None)
    combo.addItem("R1 - Lic. Virginia Lo Veci", 1)
    combo.addItem("R10 - Lic. Esteban Quito", 10)
    habilitar_busqueda_profesional(combo)
    qtbot.addWidget(combo)
    combo.setCurrentIndex(1)  # R1

    _confirmar(combo, "r1")  # matchea "R1" y "R10" -> ambiguo, no se adivina
    assert combo.currentData() == 1
    assert combo.currentText() == "R1 - Lic. Virginia Lo Veci"


def test_confirmar_texto_sin_coincidencia_vuelve_a_la_seleccion_vigente(qtbot):
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    combo.setCurrentIndex(1)  # R1

    _confirmar(combo, "texto que no matchea a nadie")
    assert combo.currentData() == 1
    assert combo.currentText() == "R1 - Lic. Virginia Lo Veci"
