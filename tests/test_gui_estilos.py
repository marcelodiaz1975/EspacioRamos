from PySide6.QtGui import QPalette

from app.gui.estilos import hoja_estilos, paleta


def test_hoja_estilos_claro_y_oscuro_son_distintas():
    assert hoja_estilos(False) != hoja_estilos(True)


def test_hoja_estilos_claro_usa_fondo_claro():
    assert "#F5F5F5" in hoja_estilos(False)


def test_hoja_estilos_oscuro_usa_fondo_oscuro():
    assert "#1E2124" in hoja_estilos(True)


def test_paleta_clara_fuerza_resalte_naranja_suave_en_vez_del_celeste_por_defecto():
    """Confirmado por la clienta: la fila/ítem seleccionado no puede ser
    celeste/azul (se confunde con el azul de los títulos) en NINGÚN
    modo, no solo en el oscuro — probado primero en gris, después
    cambiado a naranja suave a pedido de la clienta."""
    p = paleta(False)
    predeterminada = QPalette()
    assert p.color(QPalette.ColorRole.Highlight) != predeterminada.color(QPalette.ColorRole.Highlight)
    assert p.color(QPalette.ColorRole.Highlight).name() == "#f2c4a0"
    assert p.color(QPalette.ColorRole.Window) == predeterminada.color(QPalette.ColorRole.Window)


def test_paleta_oscura_tiene_fondo_oscuro():
    p = paleta(True)
    assert p.color(QPalette.ColorRole.Window).name() == "#1e2124"
    assert p.color(QPalette.ColorRole.WindowText).name() == "#e8e6e3"


def test_paleta_oscura_tambien_tiene_resalte_naranja_suave():
    p = paleta(True)
    assert p.color(QPalette.ColorRole.Highlight).name() == "#8a5a32"


def test_hoja_estilos_tiene_boton_secundario_celeste_suave():
    """botonSecundario: mismo padding que botonAccion, pero con un
    celeste suave — para botones que necesitan destacarse un poco sin
    llegar al azul fuerte de botonPrimario."""
    assert "botonSecundario" in hoja_estilos(False)
    assert "botonSecundario" in hoja_estilos(True)


def test_boton_primario_y_secundario_tienen_borde_negro_finito():
    for modo_oscuro in (False, True):
        hoja = hoja_estilos(modo_oscuro)
        assert "border: 1px solid #000000; border-radius: 4px; padding: 8px 16px" in hoja.split(
            "QPushButton#botonPrimario {"
        )[1]
        assert "border: 1px solid #000000; border-radius: 4px; padding: 8px 16px" in hoja.split(
            "QPushButton#botonSecundario {"
        )[1]


def test_titulo_pantalla_es_italica():
    assert "font-style: italic" in hoja_estilos(False).split("QLabel#tituloPantalla {")[1].split("}")[0]


def test_subtitulo_campo_es_negrita():
    assert "font-weight: bold" in hoja_estilos(False).split("QLabel#subtituloCampo {")[1].split("}")[0]


def test_encabezado_de_tabla_usa_azul_mas_oscuro_que_boton_primario():
    from app.gui.estilos import COLOR_NIVEL_1, COLOR_NIVEL_1_OSCURO
    assert COLOR_NIVEL_1_OSCURO != COLOR_NIVEL_1
    hoja = hoja_estilos(False)
    assert COLOR_NIVEL_1_OSCURO in hoja.split("QHeaderView::section {")[1].split("}")[0]


def test_titulo_pantalla_y_subtitulo_seccion_son_negros_no_azules():
    """Jerarquía 1 y 2 probadas primero en azul (COLOR_NIVEL_1), la
    clienta pidió pasarlas a negro (color de texto normal) — es un
    cambio global, no solo de Lista de espera, porque tituloPantalla y
    subtituloSeccion ya las usan todas las pantallas."""
    from app.gui.estilos import COLOR_NIVEL_1

    bloque_titulo = hoja_estilos(False).split("QLabel#tituloPantalla {")[1].split("}")[0]
    bloque_solapa = hoja_estilos(False).split("QLabel#subtituloSeccion {")[1].split("}")[0]
    assert COLOR_NIVEL_1 not in bloque_titulo
    assert COLOR_NIVEL_1 not in bloque_solapa
    assert "#1A1A1A" in bloque_titulo
    assert "#1A1A1A" in bloque_solapa


def test_qtabbar_tab_tiene_el_mismo_formato_de_jerarquia_2():
    """Jerarquía 2 pasó a implementarse como una solapa real de
    QTabWidget (QTabBar::tab) en vez de solo un QLabel simulándola —
    mismo tamaño/negrita/color que subtituloSeccion."""
    bloque = hoja_estilos(False).split("QTabBar::tab {")[1].split("}")[0]
    assert "font-size: 15px" in bloque
    assert "font-weight: bold" in bloque
    assert "#1A1A1A" in bloque


def test_solapa_y_panel_comparten_el_mismo_fondo_que_la_pantalla():
    """Pedido de la clienta: que no se note diferencia de relleno entre
    la pestañita ("Nuevo pedido") y el resto del formulario debajo — por
    defecto Fusion pinta la solapa con el gris de botón, distinto del
    fondo de la pantalla, así que se fuerzan los dos al mismo color."""
    for modo_oscuro, fondo in ((False, "#F5F5F5"), (True, "#1E2124")):
        hoja = hoja_estilos(modo_oscuro)
        bloque_panel = hoja.split("QTabWidget::pane {")[1].split("}")[0]
        bloque_tab = hoja.split("QTabBar::tab {")[1].split("}")[0]
        assert fondo in bloque_panel
        assert fondo in bloque_tab
