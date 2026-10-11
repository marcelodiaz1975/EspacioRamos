from PySide6.QtCore import QEvent
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QApplication, QComboBox

from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional


def _combo_de_prueba() -> QComboBox:
    combo = QComboBox()
    combo.addItem("Sin selección", None)
    combo.addItem("R1 - Lic. Virginia Lo Veci", 1)
    combo.addItem("R3 - Lic. Esteban Quito", 3)
    combo.addItem("R4 - Dr. Roberto Díaz", 4)
    habilitar_busqueda_profesional(combo)
    return combo


def _confirmar(combo: QComboBox, texto: str) -> None:
    combo.setEditText(texto)
    combo.lineEdit().editingFinished.emit()


def test_completer_filtra_por_prefijo_del_codigo(qtbot):
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    proxy = combo.completer().model()

    proxy.establecer_patron("R1")
    assert [proxy.data(proxy.index(f, 0)) for f in range(proxy.rowCount())] == ["R1 - Lic. Virginia Lo Veci"]


def test_completer_no_filtra_por_nombre_en_medio_de_la_cadena(qtbot):
    """Pedido explícito de la clienta: tipear "Leandro"/"Veci" (un
    nombre o apellido, en el medio de la cadena canónica) no tiene que
    encontrar nada — solo busca desde el comienzo de la cadena."""
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    proxy = combo.completer().model()

    proxy.establecer_patron("VECI")
    assert proxy.rowCount() == 0


def test_completer_filtra_por_prefijo_sin_distinguir_acentos(qtbot):
    """"diaz" (sin tilde) tiene que encontrar "R4 - Dr. Roberto Díaz" —
    pero solo porque "R4" es el prefijo real, no "Díaz"."""
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    proxy = combo.completer().model()

    proxy.establecer_patron("r4")
    assert [proxy.data(proxy.index(f, 0)) for f in range(proxy.rowCount())] == ["R4 - Dr. Roberto Díaz"]


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


def test_confirmar_con_nombre_no_identifica_a_nadie_y_revierte(qtbot):
    """Mismo pedido que el completer: tipear un nombre (no el principio
    de la cadena) no tiene que resolver a ningún profesional."""
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    combo.setCurrentIndex(1)  # R1

    _confirmar(combo, "lo veci")
    assert combo.currentData() == 1
    assert combo.currentText() == "R1 - Lic. Virginia Lo Veci"


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


def test_al_enfocar_el_campo_selecciona_todo_el_contenido(qtbot):
    """Pedido explícito de la clienta: "apenas se pinche se seleccione
    todo el contenido" — simula el foco real (no alcanza con
    `setFocus()`, el seteo es diferido con `QTimer.singleShot`)."""
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    combo.show()
    linea = combo.lineEdit()
    linea.deselect()
    linea.setCursorPosition(0)

    evento = QFocusEvent(QEvent.Type.FocusIn)
    QApplication.sendEvent(linea, evento)
    qtbot.wait(10)

    assert linea.selectedText() == linea.text()


def test_popup_del_completer_tiene_delegado_de_negrita(qtbot):
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    popup = combo.completer().popup()
    assert popup.itemDelegate() is not None
    assert type(popup.itemDelegate()).__name__ == "_DelegadoNegritaPrefijo"
