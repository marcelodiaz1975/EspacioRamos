from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.gui.widgets.calculadora import Calculadora


def test_suma_basica(qtbot):
    calc = Calculadora()
    qtbot.addWidget(calc)
    for tecla in ("2", "+", "3", "="):
        calc._al_tocar(tecla)
    assert calc.pantalla.text() == "5"


def test_multiplicacion_y_division(qtbot):
    calc = Calculadora()
    qtbot.addWidget(calc)
    for tecla in ("6", "*", "7", "="):
        calc._al_tocar(tecla)
    assert calc.pantalla.text() == "42"


def test_boton_c_limpia_la_expresion(qtbot):
    calc = Calculadora()
    qtbot.addWidget(calc)
    for tecla in ("1", "2", "C"):
        calc._al_tocar(tecla)
    assert calc.pantalla.text() == ""


def test_borrar_ultimo_caracter(qtbot):
    calc = Calculadora()
    qtbot.addWidget(calc)
    for tecla in ("1", "2", "3"):
        calc._al_tocar(tecla)
    calc._borrar_ultimo()
    assert calc.pantalla.text() == "12"


def test_division_por_cero_muestra_error_sin_romper(qtbot):
    calc = Calculadora()
    qtbot.addWidget(calc)
    for tecla in ("5", "/", "0", "="):
        calc._al_tocar(tecla)
    assert calc.pantalla.text() == "Error"


def test_igual_sin_expresion_cargada_no_rompe(qtbot):
    calc = Calculadora()
    qtbot.addWidget(calc)
    calc._al_tocar("=")
    assert calc.pantalla.text() == "Error"


def test_teclado_suma_basica(qtbot):
    """Pedido de la clienta: números y signos matemáticos del teclado, no
    solo del mouse."""
    calc = Calculadora()
    qtbot.addWidget(calc)
    calc.show()
    qtbot.waitExposed(calc)
    QTest.keyClicks(calc, "2+3")
    QTest.keyClick(calc, Qt.Key.Key_Return)
    assert calc.pantalla.text() == "5"


def test_teclado_coma_se_trata_como_punto_decimal(qtbot):
    calc = Calculadora()
    qtbot.addWidget(calc)
    calc.show()
    qtbot.waitExposed(calc)
    QTest.keyClicks(calc, "1,5+0,5")
    QTest.keyClick(calc, Qt.Key.Key_Equal)
    assert calc.pantalla.text() == "2.0"


def test_teclado_backspace_borra_el_ultimo_caracter(qtbot):
    calc = Calculadora()
    qtbot.addWidget(calc)
    calc.show()
    qtbot.waitExposed(calc)
    QTest.keyClicks(calc, "123")
    QTest.keyClick(calc, Qt.Key.Key_Backspace)
    assert calc.pantalla.text() == "12"


def test_teclado_c_limpia_la_expresion(qtbot):
    calc = Calculadora()
    qtbot.addWidget(calc)
    calc.show()
    qtbot.waitExposed(calc)
    QTest.keyClicks(calc, "34")
    QTest.keyClick(calc, Qt.Key.Key_C)
    assert calc.pantalla.text() == ""


def test_teclado_escape_cierra_la_calculadora(qtbot):
    """Última corrección de la clienta: Escape ya no limpia la
    expresión — cierra la ventana (igual que la cruz), mismo criterio
    que cualquier ventana flotante del sistema operativo."""
    calc = Calculadora()
    qtbot.addWidget(calc)
    calc.show()
    qtbot.waitExposed(calc)
    with qtbot.waitSignal(calc.destroyed, timeout=1000):
        QTest.keyClick(calc, Qt.Key.Key_Escape)


def test_teclado_delete_limpia_la_expresion(qtbot):
    """Corrección de la clienta: la tecla Suprimir/Delete también borra
    todo, mismo comportamiento que Escape/"C" (no solo el último
    carácter, eso lo sigue haciendo Backspace)."""
    calc = Calculadora()
    qtbot.addWidget(calc)
    calc.show()
    qtbot.waitExposed(calc)
    QTest.keyClicks(calc, "123")
    QTest.keyClick(calc, Qt.Key.Key_Delete)
    assert calc.pantalla.text() == ""


def test_ventana_se_puede_cerrar_con_la_cruz(qtbot):
    """Pedido explícito: "que se pueda cerrar con la cruz típica de
    todas las apps" — una ventana de verdad (`Qt.WindowType.Window`), no
    un diálogo modal que bloquee el resto del sistema."""
    calc = Calculadora()
    qtbot.addWidget(calc)
    calc.show()
    qtbot.waitExposed(calc)
    assert calc.close() is True
