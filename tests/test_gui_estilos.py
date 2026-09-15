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


def test_boton_secundario_usa_el_mismo_gris_de_fuera_del_panel():
    """botonSecundario: mismo padding que botonAccion. Probado primero
    en celeste suave, pasa al mismo gris que queda por fuera del panel
    del formulario (`t['fondo']`, texto `t['texto']`) al revisar
    Registro de ausencias — se lee como "el gris de afuera metido acá"
    en vez de un color propio."""
    for modo_oscuro, fondo, texto in ((False, "#F5F5F5", "#1A1A1A"), (True, "#1E2124", "#E8E6E3")):
        bloque = hoja_estilos(modo_oscuro).split("QPushButton#botonSecundario {")[1].split("}")[0]
        assert f"background-color: {fondo}" in bloque
        assert f"color: {texto}" in bloque


def test_boton_primario_usa_gris_oscuro_fijo_con_texto_blanco():
    """Probado primero en azul fuerte (COLOR_NIVEL_1), la clienta pidió
    pasarlo a un gris oscuro fijo (no depende del modo claro/oscuro,
    igual que antes con el azul) manteniendo el texto blanco."""
    from app.gui.estilos import COLOR_BOTON_PRIMARIO, COLOR_TEXTO_CLARO

    for modo_oscuro in (False, True):
        bloque = hoja_estilos(modo_oscuro).split("QPushButton#botonPrimario {")[1].split("}")[0]
        assert f"background-color: {COLOR_BOTON_PRIMARIO}" in bloque
        assert f"color: {COLOR_TEXTO_CLARO}" in bloque


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


def test_subtitulo_campo_no_es_negrita():
    """Se probó en negrita, pero la clienta pidió sacarla al revisar
    Registro de ausencias: jerarquía 3 queda con el mismo peso que el
    texto normal."""
    assert "font-weight: bold" not in hoja_estilos(False).split("QLabel#subtituloCampo {")[1].split("}")[0]


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
    QTabWidget (QTabBar::tab) en vez de solo un QLabel simulándola.
    Tamaño (14px) probado primero en Placas y aprobado por la clienta:
    más chico que antes (15px), sigue más grande que el texto normal."""
    bloque = hoja_estilos(False).split("QTabBar::tab {")[1].split("}")[0]
    assert "font-size: 14px" in bloque
    assert "font-weight: bold" in bloque
    assert "#1A1A1A" in bloque


def test_encabezado_de_columna_esta_en_negrita():
    bloque = hoja_estilos(False).split("QHeaderView::section {")[1].split("}")[0]
    assert "font-weight: bold" in bloque


def test_numeros_de_fila_quedan_centrados_globalmente():
    """Pedido de la clienta al revisar Llaves: los números de fila
    (encabezado vertical) centrados en cualquier tabla que se toque —
    QSS no soporta text-align para QHeaderView::section, así que se usa
    qproperty-defaultAlignment sobre QHeaderView:vertical."""
    hoja = hoja_estilos(False)
    bloque = hoja.split("QHeaderView:vertical {")[1].split("}")[0]
    assert "qproperty-defaultAlignment: AlignCenter" in bloque


def test_solapas_tienen_apariencia_de_ficha_de_papel():
    """Probado primero en Placas y aprobado por la clienta para todas
    las pantallas: la solapa activa funde su fondo con el panel de
    contenido y pierde la línea de abajo (border-bottom-color igual al
    fondo del panel) — el borde la envuelve arriba/izquierda/derecha
    nada más. La inactiva conserva su fondo y su borde de abajo, y baja
    unos px para quedar "detrás" de la activa, como una ficha. El borde
    (pane y solapas) usa el tono oscuro (`fondo`), no negro — corregido
    a pedido de la clienta al revisar Registro de ausencias, que pidió
    dos tonos de gris (claro para la activa/el contenido, oscuro para
    la inactiva y el borde) en vez de un borde negro."""
    for modo_oscuro, superficie, fondo in (
        (False, "#FFFFFF", "#F5F5F5"), (True, "#2A2E33", "#1E2124"),
    ):
        hoja = hoja_estilos(modo_oscuro)
        bloque_panel = hoja.split("QTabWidget::pane {")[1].split("}")[0]
        bloque_tab = hoja.split("QTabBar::tab {")[1].split("}")[0]
        bloque_seleccionada = hoja.split("QTabBar::tab:selected {")[1].split("}")[0]
        bloque_inactiva = hoja.split("QTabBar::tab:!selected {")[1].split("}")[0]
        assert superficie in bloque_panel
        assert f"border: 1px solid {fondo}" in bloque_panel
        assert "top: -1px" in bloque_panel
        assert f"border: 1px solid {fondo}" in bloque_tab
        assert superficie in bloque_seleccionada
        assert f"border-bottom-color: {superficie}" in bloque_seleccionada
        assert "margin-top: 2px" in bloque_inactiva


def test_panel_dentro_de_una_solapa_hereda_el_mismo_fondo_claro():
    """El widget que se agrega con addTab() no hereda el fondo del
    QTabWidget::pane solo (Qt lo pinta transparente por defecto, así
    que en la práctica se ve el fondo de la ventana) — necesita el
    objectName "panelSolapa" para que esta regla lo pinte del mismo
    tono claro que la solapa activa y el pane."""
    for modo_oscuro, superficie in ((False, "#FFFFFF"), (True, "#2A2E33")):
        hoja = hoja_estilos(modo_oscuro)
        bloque = hoja.split("QWidget#panelSolapa {")[1].split("}")[0]
        assert superficie in bloque
