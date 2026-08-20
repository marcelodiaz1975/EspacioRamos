from PySide6.QtGui import QPalette

from app.gui.estilos import hoja_estilos, paleta


def test_hoja_estilos_claro_y_oscuro_son_distintas():
    assert hoja_estilos(False) != hoja_estilos(True)


def test_hoja_estilos_claro_usa_fondo_claro():
    assert "#F5F5F5" in hoja_estilos(False)


def test_hoja_estilos_oscuro_usa_fondo_oscuro():
    assert "#1E2124" in hoja_estilos(True)


def test_paleta_clara_es_la_paleta_por_defecto_de_qt():
    assert paleta(False) == QPalette()


def test_paleta_oscura_tiene_fondo_oscuro():
    p = paleta(True)
    assert p.color(QPalette.ColorRole.Window).name() == "#1e2124"
    assert p.color(QPalette.ColorRole.WindowText).name() == "#e8e6e3"
