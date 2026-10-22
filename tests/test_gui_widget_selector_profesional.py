from PySide6.QtCore import QEvent
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox

from app.gui.widgets.selector_profesional import _rango_resaltado, habilitar_busqueda_profesional


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


def _filas_visibles_en_el_desplegable(combo: QComboBox) -> list[str]:
    """Lee lo que de verdad termina mostrando `QCompleter` — ya no tiene
    sentido mirar el `proxy` por separado (`proxy.establecer_patron(...)`
    + `proxy.rowCount()`/`data()`): desde el rediseño con `splitPath`/
    `pathFromIndex` (ver docstring del módulo), `proxy` dejó de filtrar
    filas — el filtrado en vivo lo hace el motor nativo de `QCompleter`,
    así que el único lugar donde se puede verificar de verdad qué queda
    visible es su `completionModel()`."""
    cm = combo.completer().completionModel()
    return [cm.data(cm.index(f, 0)) for f in range(cm.rowCount())]


def _tipear(combo: QComboBox, texto: str) -> None:
    """Tipeo REAL con `QTest.keyClicks`, no `textEdited.emit(...)` a
    mano: un primer intento de arreglo pasaba un test que emitía la
    señal a mano, pero la clienta lo probó en la pantalla real y seguía
    roto — la conexión interna de Qt entre `QLineEdit` y `QCompleter` (a
    nivel C++) hace cosas que emitir la señal a mano no reproduce. Ver
    docstring del módulo, sección "El filtro en vivo"."""
    combo.show()
    QTest.qWaitForWindowExposed(combo)
    combo.lineEdit().setFocus()
    QApplication.processEvents()
    QTest.keyClicks(combo.lineEdit(), texto)


def test_completer_filtra_por_codigo(qtbot):
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)

    _tipear(combo, "R1")
    assert _filas_visibles_en_el_desplegable(combo) == ["R1 - Lic. Virginia Lo Veci"]


def test_completer_filtra_por_nombre_en_el_medio_de_la_cadena(qtbot):
    """Pedido explícito de la clienta: buscar también por nombre/apellido,
    no solo por código — "VECI" está en el medio de la cadena, no al
    principio, y tiene que encontrarla igual."""
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)

    _tipear(combo, "VECI")
    assert _filas_visibles_en_el_desplegable(combo) == ["R1 - Lic. Virginia Lo Veci"]


def test_desplegable_real_no_distingue_mayusculas_de_minusculas(qtbot):
    """Bug real: `QCompleter` filtra con `CaseSensitive` por default, por
    encima de nuestro `proxy` (que sí es case-insensitive) — escribir en
    minúscula un código que existe en mayúscula no mostraba nada.

    Tipeo REAL con `QTest.keyClicks` (no `textEdited.emit(...)` a mano):
    un primer arreglo (resetear `completionPrefix` a mano en cada
    `textEdited`) pasaba este mismo test con señal emitida a mano, pero
    la clienta lo probó en la pantalla real y seguía roto — la conexión
    interna de Qt entre `QLineEdit` y `QCompleter` (a nivel C++) también
    fija `completionPrefix`, y lo hace en un punto que nuestro slot de
    Python no puede garantizar que corra después. Solo tipeo real
    reproduce esa carrera; emitir la señal a mano no la ejercita y deja
    pasar un bug como este dando falso positivo."""
    combo = _combo_de_prueba()
    combo.addItem("X1 - Carlos Pérez", 99)
    qtbot.addWidget(combo)

    _tipear(combo, "x1")
    assert _filas_visibles_en_el_desplegable(combo) == ["X1 - Carlos Pérez"]


def test_desplegable_real_filtra_por_substring_en_el_medio(qtbot):
    """Mismo bug de fondo que el anterior (`QCompleter` filtra con
    `MatchStartsWith` por default, por encima de nuestro `proxy`), mismo
    motivo para usar tipeo real en vez de `textEdited.emit(...)` a mano."""
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)

    _tipear(combo, "lo ve")
    assert _filas_visibles_en_el_desplegable(combo) == ["R1 - Lic. Virginia Lo Veci"]


def test_al_elegir_una_opcion_del_desplegable_inserta_el_texto_original(qtbot):
    """El rol que usa el `QCompleter` para matchear (`_ROL_TEXTO_
    NORMALIZADO`) es el texto en minúsculas y sin acentos — sin el
    override de `pathFromIndex`, elegir una opción insertaría ESE texto
    normalizado en el campo en vez del texto real con mayúsculas y
    tildes."""
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    completador = combo.completer()
    modelo = completador.completionModel()
    fila = next(f for f in range(modelo.rowCount()) if "Díaz" in modelo.data(modelo.index(f, 0)))

    assert completador.pathFromIndex(modelo.index(fila, 0)) == "R4 - Dr. Roberto Díaz"


def test_setfocus_directo_en_el_combo_selecciona_todo_el_contenido(qtbot):
    """Patrón usado por el `showEvent` de casi todas las pantallas del
    sistema para arrancar la cadena de foco: NO es un click del mouse
    directo en el campo de texto, es `combo.setFocus()` llamado desde
    código. Bug real: ese `FocusIn` lo recibe el `QComboBox` de afuera,
    nunca su `line_edit` interno — sin escuchar también en el combo, el
    select-all funcionaba al llegar por click o por Tab, pero NO al
    entrar recién a la pantalla."""
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    combo.show()
    qtbot.waitExposed(combo)
    linea = combo.lineEdit()
    linea.deselect()
    linea.setCursorPosition(0)

    combo.setFocus()
    qtbot.wait(10)

    assert linea.selectedText() == linea.text()


def test_completer_filtra_sin_distinguir_acentos(qtbot):
    """"diaz" (sin tilde) tiene que encontrar "Díaz"."""
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)

    _tipear(combo, "diaz")
    assert _filas_visibles_en_el_desplegable(combo) == ["R4 - Dr. Roberto Díaz"]


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


def test_confirmar_con_nombre_sin_acento_identifica_el_profesional_con_tilde(qtbot):
    combo = _combo_de_prueba()
    qtbot.addWidget(combo)
    _confirmar(combo, "diaz")
    assert combo.currentData() == 4
    assert combo.currentText() == "R4 - Dr. Roberto Díaz"


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
    assert type(popup.itemDelegate()).__name__ == "_DelegadoNegritaCoincidencia"


def test_rango_resaltado_encuentra_la_posicion_real_del_substring():
    inicio, fin = _rango_resaltado("R1 - Lic. Virginia Lo Veci", "veci")
    assert "R1 - Lic. Virginia Lo Veci"[inicio:fin].lower() == "veci"


def test_rango_resaltado_sin_distinguir_acentos():
    inicio, fin = _rango_resaltado("R4 - Dr. Roberto Díaz", "diaz")
    assert "R4 - Dr. Roberto Díaz"[inicio:fin] == "Díaz"


def test_rango_resaltado_sin_coincidencia_devuelve_none():
    assert _rango_resaltado("R1 - Lic. Virginia Lo Veci", "nada que ver") is None


def test_rango_resaltado_sin_patron_devuelve_none():
    assert _rango_resaltado("R1 - Lic. Virginia Lo Veci", "") is None
