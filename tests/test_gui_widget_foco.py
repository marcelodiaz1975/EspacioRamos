"""Tests del mecanismo compartido de Enter-avanza-foco (app/gui/widgets/foco.py)
a nivel del widget en sí, en vez de repetirlos en cada pantalla que lo usa —
la garantía es la misma en todos los formularios porque es la misma clase."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.gui.widgets.foco import instalar_enter_avanza_foco


def _enter(widget: QWidget) -> None:
    evento = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, evento)


def _mostrar(qtbot, contenedor: QWidget) -> None:
    qtbot.addWidget(contenedor)
    contenedor.show()
    qtbot.waitExposed(contenedor)


def test_enter_avanza_al_siguiente_campo(qtbot):
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    campo_1 = QLineEdit()
    campo_2 = QLineEdit()
    boton = QPushButton("Crear")
    for w in (campo_1, campo_2, boton):
        layout.addWidget(w)
    foco = instalar_enter_avanza_foco([campo_1, campo_2, boton])
    contenedor._foco = foco  # mantiene viva la referencia, como en las pantallas reales
    _mostrar(qtbot, contenedor)

    campo_1.setFocus()
    qtbot.waitUntil(lambda: campo_1.hasFocus())
    _enter(campo_1)
    qtbot.waitUntil(lambda: campo_2.hasFocus())


def test_enter_en_el_ultimo_elemento_vuelve_al_principio(qtbot):
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    campo_1 = QLineEdit()
    campo_2 = QLineEdit()
    boton = QPushButton("Crear")
    for w in (campo_1, campo_2, boton):
        layout.addWidget(w)
    foco = instalar_enter_avanza_foco([campo_1, campo_2, boton])
    contenedor._foco = foco
    _mostrar(qtbot, contenedor)

    boton.setFocus()
    qtbot.waitUntil(lambda: boton.hasFocus())
    _enter(boton)
    qtbot.waitUntil(lambda: campo_1.hasFocus())


def test_enter_saltea_deshabilitados_y_ocultos(qtbot):
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    campo_1 = QLineEdit()
    campo_2 = QLineEdit()
    campo_2.setEnabled(False)
    campo_3 = QLineEdit()
    campo_4 = QLineEdit()
    for w in (campo_1, campo_2, campo_3, campo_4):
        layout.addWidget(w)
    campo_3.hide()
    foco = instalar_enter_avanza_foco([campo_1, campo_2, campo_3, campo_4])
    contenedor._foco = foco
    _mostrar(qtbot, contenedor)

    campo_1.setFocus()
    qtbot.waitUntil(lambda: campo_1.hasFocus())
    _enter(campo_1)
    qtbot.waitUntil(lambda: campo_4.hasFocus())


def test_enter_no_rompe_si_nada_mas_esta_habilitado(qtbot):
    """Si el actual es el único campo utilizable de la cadena, el Enter no
    encuentra a dónde ir y no debe romper (se queda sin mover el foco)."""
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    campo_1 = QLineEdit()
    campo_2 = QLineEdit()
    campo_2.setEnabled(False)
    for w in (campo_1, campo_2):
        layout.addWidget(w)
    foco = instalar_enter_avanza_foco([campo_1, campo_2])
    contenedor._foco = foco
    _mostrar(qtbot, contenedor)

    campo_1.setFocus()
    qtbot.waitUntil(lambda: campo_1.hasFocus())
    _enter(campo_1)  # no debe lanzar ninguna excepción
    assert campo_1.hasFocus()


def test_tab_sigue_la_misma_cadena_que_enter(qtbot):
    """Pedido explícito de la clienta en la revisión de Llaves: no puede
    haber una cadena para Enter y otra distinta para Tab. Se simulan
    pulsaciones reales de Tab (no alcanza con mirar nextInFocusChain(): esa
    API de bajo nivel incluye widgets no enfocables como el contenedor,
    que Tab saltea solo, así que sigue el orden real que ve el usuario)."""
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    campo_1 = QLineEdit()
    campo_2 = QLineEdit()
    boton = QPushButton("Crear")
    for w in (campo_1, campo_2, boton):
        layout.addWidget(w)
    foco = instalar_enter_avanza_foco([campo_1, campo_2, boton])
    contenedor._foco = foco
    _mostrar(qtbot, contenedor)

    campo_1.setFocus()
    qtbot.waitUntil(lambda: campo_1.hasFocus())
    QTest.keyClick(campo_1, Qt.Key.Key_Tab)
    qtbot.waitUntil(lambda: campo_2.hasFocus())
    QTest.keyClick(campo_2, Qt.Key.Key_Tab)
    qtbot.waitUntil(lambda: boton.hasFocus())
    QTest.keyClick(boton, Qt.Key.Key_Tab)
    qtbot.waitUntil(lambda: campo_1.hasFocus())  # último -> primero, igual que Enter


def test_shift_tab_retrocede_en_la_misma_cadena(qtbot):
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    campo_1 = QLineEdit()
    campo_2 = QLineEdit()
    boton = QPushButton("Crear")
    for w in (campo_1, campo_2, boton):
        layout.addWidget(w)
    foco = instalar_enter_avanza_foco([campo_1, campo_2, boton])
    contenedor._foco = foco
    _mostrar(qtbot, contenedor)

    campo_1.setFocus()
    qtbot.waitUntil(lambda: campo_1.hasFocus())
    QTest.keyClick(campo_1, Qt.Key.Key_Backtab)
    qtbot.waitUntil(lambda: boton.hasFocus())  # primero -> último, en reversa
    QTest.keyClick(boton, Qt.Key.Key_Backtab)
    qtbot.waitUntil(lambda: campo_2.hasFocus())
    QTest.keyClick(campo_2, Qt.Key.Key_Backtab)
    qtbot.waitUntil(lambda: campo_1.hasFocus())
