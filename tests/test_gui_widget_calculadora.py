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


def test_ventana_se_puede_cerrar_con_la_cruz(qtbot):
    """Pedido explícito: "que se pueda cerrar con la cruz típica de
    todas las apps" — una ventana de verdad (`Qt.WindowType.Window`), no
    un diálogo modal que bloquee el resto del sistema."""
    calc = Calculadora()
    qtbot.addWidget(calc)
    calc.show()
    qtbot.waitExposed(calc)
    assert calc.close() is True
