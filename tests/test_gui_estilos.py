from PySide6.QtGui import QPalette

from app.gui.estilos import hoja_estilos, paleta


def test_hoja_estilos_claro_y_oscuro_son_distintas():
    assert hoja_estilos(False) != hoja_estilos(True)


def test_hoja_estilos_claro_usa_fondo_claro():
    assert "#F5F5F5" in hoja_estilos(False)


def test_hoja_estilos_oscuro_usa_fondo_oscuro():
    assert "#1E2124" in hoja_estilos(True)


def test_paleta_clara_fuerza_resalte_gris_en_vez_del_celeste_por_defecto():
    """Confirmado por la clienta: la fila/ítem seleccionado no puede ser
    celeste/azul (se confunde con el azul de los títulos) en NINGÚN
    modo, no solo en el oscuro."""
    p = paleta(False)
    predeterminada = QPalette()
    assert p.color(QPalette.ColorRole.Highlight) != predeterminada.color(QPalette.ColorRole.Highlight)
    assert p.color(QPalette.ColorRole.Highlight).name() == "#d6d6d6"
    assert p.color(QPalette.ColorRole.Window) == predeterminada.color(QPalette.ColorRole.Window)


def test_paleta_oscura_tiene_fondo_oscuro():
    p = paleta(True)
    assert p.color(QPalette.ColorRole.Window).name() == "#1e2124"
    assert p.color(QPalette.ColorRole.WindowText).name() == "#e8e6e3"


def test_paleta_oscura_tambien_tiene_resalte_gris():
    p = paleta(True)
    assert p.color(QPalette.ColorRole.Highlight).name() == "#5a5f66"


def test_hoja_estilos_tiene_boton_secundario_celeste_suave():
    """botonSecundario: mismo padding que botonAccion, pero con un
    celeste suave — para botones que necesitan destacarse un poco sin
    llegar al azul fuerte de botonPrimario."""
    assert "botonSecundario" in hoja_estilos(False)
    assert "botonSecundario" in hoja_estilos(True)
