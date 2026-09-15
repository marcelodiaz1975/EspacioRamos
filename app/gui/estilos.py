"""Estilos compartidos por las pantallas de la aplicación — reusa la
misma paleta que los PDFs (app/pdf/estilos.py) para que la app y los
documentos que genera se sientan del mismo sistema.

Modo oscuro (Configuracion.ModoOscuro, default apagado): además de la
hoja de estilos con los nombres de objeto propios de la app
(tituloPantalla, botonPrimario, etc.), se arma una QPalette para que los
widgets estándar sin estilo propio (QLineEdit, QComboBox, QTableWidget,
QCheckBox, diálogos) seas consistentes sin tener que escribir una regla
QSS por cada pantalla.

Jerarquía de títulos dentro de una pantalla (definida y probada primero
en Lista de espera, a replicar en el resto de a poco):
    Jerarquía 1 — título de la pantalla entera (ej. "Lista de espera"):
        objectName "tituloPantalla". Mismo tamaño de siempre (18px),
        negrita, MAYÚSCULA e itálica, en color de texto normal (negro
        en modo claro) en vez de azul — probado primero en azul, la
        clienta pidió pasarlo a negro. La mayúscula hay que escribirla
        en el texto (`.upper()` al armar el QLabel): Qt Style Sheets no
        soporta la propiedad CSS text-transform.
    Jerarquía 2 — nombre de la solapa/sección dentro del formulario
        (ej. "Nuevo pedido"): es una solapa real de un QTabWidget, no
        una etiqueta simulándola — Qt muestra la barra de solapas
        aunque haya una sola mientras no se active `tabBarAutoHide`
        (que acá no se usa a propósito, así se ve siempre — inclusive
        con una sola solapa se quiere la misma apariencia de "ficha" de
        abajo, y como esa única solapa siempre está seleccionada, el
        CSS de `:selected` ya le da ese aspecto sin hacer nada especial).
        El texto de la solapa (QTabBar::tab) usa el mismo criterio: más
        grande que el texto normal pero menor que jerarquía 1 (14px),
        negrita, sin itálica, mismo color de texto normal que jerarquía
        1 (no azul).

        Apariencia de "ficha de papel" (probada primero en Placas,
        aprobada por la clienta y llevada acá para todas las
        pantallas), en dos tonos de gris (ya no negro, a pedido de la
        clienta al revisar Registro de ausencias): la solapa ACTIVA usa
        el tono CLARO (`t['superficie']`) tanto de fondo como de borde,
        y ese mismo fondo claro es el que también funde con el panel de
        contenido (QTabWidget::pane, mismo `t['superficie']`) — pierde
        el borde de abajo (`border-bottom-color` igual al fondo del
        panel) para que el borde la envuelva arriba/izquierda/derecha
        nada más, como si el panel fuera la continuación de la solapa.
        La solapa INACTIVA usa el tono OSCURO (`t['fondo']`) de fondo Y
        de borde, con su borde completo incluida la línea de abajo, y
        baja 2px (`margin-top`) para quedar visualmente "detrás" de la
        activa, como una ficha de fichero de papel; el borde de
        `QTabWidget::pane` (lo que enmarca el contenido) usa ese mismo
        tono oscuro, en vez de negro. `QTabWidget::pane` sube 1px
        (`top: -1px`) para que su borde superior quede tapado
        exactamente donde se apoya la solapa activa, sin una línea
        doble ahí.

        El fondo claro de la solapa activa NO llega solo por estar
        dentro del `QTabWidget::pane`: el widget que se agrega con
        `addTab(...)` pinta encima con su propio fondo (transparente
        por defecto, así que en la práctica termina mostrando el fondo
        de la ventana, más oscuro, no el de la solapa) — hay que
        pedírselo explícitamente con objectName "panelSolapa" en el
        widget de más afuera de cada pestaña (el que se le pasa a
        `addTab`, o el widget interno que ocupa todo un QScrollArea si
        la pestaña scrollea) para que la regla de acá (`QWidget#
        panelSolapa`) lo pinte del mismo `t['superficie']` que la
        solapa activa y el pane.

        Como referencia visual suelta (ej. un título de sección que no
        amerita ser una solapa real), objectName "subtituloSeccion" da
        el mismo formato en un QLabel.
    Jerarquía 3 — subtítulo de un campo/selector/cuadro puntual (ej.
        "Profesional" arriba de su combo): objectName "subtituloCampo".
        Mismo tamaño/color que el texto normal, solo que en negrita.

Jerarquía de botones: "botonPrimario" (azul fuerte, ej. "Crear pedido")
para la acción más importante/definitiva del formulario; "botonSecundario"
(celeste suave) para el resto de las acciones, no tan definitivas (ej.
"Agregar bloque", "Descartar pedido"). Los encabezados de columna de
cualquier tabla (QHeaderView::section) usan un azul más oscuro que
botonPrimario para no confundirse con un botón, y van en negrita.

Números de fila (encabezado vertical de cualquier tabla): centrados,
global vía `QHeaderView:vertical { qproperty-defaultAlignment: ... }`
en vez de tocar cada pantalla — Qt Style Sheets no soporta `text-align`
para QHeaderView::section (probado y descartado), pero sí permite
setear cualquier Q_PROPERTY del widget con `qproperty-<nombre>`, y acá
`:vertical` alcanza a distinguir el encabezado de filas del de
columnas (que sigue con su alineación normal, sin tocar)."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

COLOR_NIVEL_1 = "#2E86AB"  # azul — encabezados principales, botón primario
COLOR_NIVEL_1_OSCURO = "#1F5F7A"  # azul más oscuro — encabezados de tabla, para diferenciarse del botón primario
COLOR_NIVEL_2 = "#E07B39"  # naranja — sub-encabezados
COLOR_DIA_GRILLA = "#6B0000"  # bordó — encabezados de grilla
COLOR_VERDE = "#4CAF50"
COLOR_AMARILLO = "#F5D547"
COLOR_ROJO = "#C0392B"
COLOR_AZUL_OSCURO = "#0B2942"  # grilla operativa — celdas del profesional filtrado
COLOR_TEXTO_CLARO = "#FFFFFF"

# ------------------------------------------------------------------- claro
_CLARO = {
    "fondo": "#F5F5F5",
    "superficie": "#FFFFFF",
    "texto": "#1A1A1A",
    "borde": "#DDDDDD",
    "hover_nav": "#3A6EA5",
    "resalte_seleccion": "#F2C4A0",
}

# ------------------------------------------------------------------ oscuro
_OSCURO = {
    "fondo": "#1E2124",
    "superficie": "#2A2E33",
    "texto": "#E8E6E3",
    "borde": "#3F454C",
    "hover_nav": "#3A6EA5",
    "resalte_seleccion": "#8A5A32",
}


def hoja_estilos(modo_oscuro: bool = False) -> str:
    t = _OSCURO if modo_oscuro else _CLARO
    return f"""
QMainWindow {{ background-color: {t['fondo']}; }}

QListWidget#navegacion {{
    background-color: {COLOR_NIVEL_1};
    color: {COLOR_TEXTO_CLARO};
    border: none;
    font-size: 13px;
    outline: none;
}}
QListWidget#navegacion::item {{ padding: 10px 14px; }}
QListWidget#navegacion::item:selected {{ background-color: {COLOR_DIA_GRILLA}; }}
QListWidget#navegacion::item:hover {{ background-color: {t['hover_nav']}; }}

QLabel#tituloPantalla {{
    font-size: 18px; font-weight: bold; font-style: italic; color: {t['texto']};
    padding: 6px 0px;
}}
QLabel#subtitulo {{ font-size: 11px; color: {'#AAAAAA' if modo_oscuro else '#555555'}; }}
QLabel#subtituloSeccion {{ font-size: 15px; font-weight: bold; color: {t['texto']}; padding: 4px 0px; }}
QLabel#subtituloCampo {{ font-weight: bold; }}
QTabWidget::pane {{
    background-color: {t['superficie']};
    border: 1px solid {t['fondo']};
    top: -1px;
}}
QTabBar::tab {{
    font-size: 14px; font-weight: bold; color: {t['texto']};
    background-color: {t['fondo']};
    border: 1px solid {t['fondo']};
    padding: 6px 14px;
}}
QTabBar::tab:selected {{
    background-color: {t['superficie']};
    border-bottom-color: {t['superficie']};
}}
QTabBar::tab:!selected {{
    margin-top: 2px;
}}
QWidget#panelSolapa {{ background-color: {t['superficie']}; }}
QGroupBox#panelFiltrosGrilla::title {{
    font-size: 15px; font-weight: bold; color: {t['texto']};
    subcontrol-origin: margin; padding: 4px 0px;
}}

QPushButton#botonPrimario {{
    background-color: {COLOR_NIVEL_1}; color: {COLOR_TEXTO_CLARO};
    border: 1px solid #000000; border-radius: 4px; padding: 8px 16px; font-weight: bold;
}}
QPushButton#botonPrimario:disabled {{ background-color: #A0AEC0; }}
QPushButton#botonPrimario:hover:!disabled {{ background-color: #256a89; }}

QPushButton#botonAccion {{ padding: 8px 16px; }}

QPushButton#botonSecundario {{
    background-color: #BFE3F5; color: #14324A;
    border: 1px solid #000000; border-radius: 4px; padding: 8px 16px; font-weight: bold;
}}
QPushButton#botonSecundario:hover:!disabled {{ background-color: #A6D6EF; }}
QPushButton#botonSecundario:disabled {{ background-color: #DDDDDD; color: #9A9A9A; }}

QPushButton#botonDestacado {{
    background-color: {COLOR_NIVEL_1}; color: {COLOR_TEXTO_CLARO};
    border: none; border-radius: 4px; padding: 10px 18px; font-weight: bold; font-size: 14px;
}}
QPushButton#botonDestacado:hover {{ background-color: #256a89; }}

QFrame#tarjetaAlerta {{
    background-color: {t['superficie']}; border: 1px solid {t['borde']}; border-radius: 4px;
}}
QLabel#encabezadoAlerta {{
    background-color: {COLOR_NIVEL_2}; color: {COLOR_TEXTO_CLARO};
    font-weight: bold; padding: 4px 8px;
}}

QLabel#barraFechaFicticia {{
    background-color: {COLOR_ROJO}; color: {COLOR_TEXTO_CLARO};
    font-weight: bold; font-size: 12px; padding: 6px 12px;
}}

QTableView {{ gridline-color: {t['borde']}; }}
QHeaderView::section {{
    background-color: {COLOR_NIVEL_1_OSCURO}; color: {COLOR_TEXTO_CLARO};
    font-weight: bold; padding: 4px; border: none;
}}
QHeaderView:vertical {{ qproperty-defaultAlignment: AlignCenter; }}
"""



def paleta(modo_oscuro: bool = False) -> QPalette:
    """QPalette aplicada a nivel QApplication: cubre los widgets estándar
    (QLineEdit, QComboBox, QTableWidget, QCheckBox, QMessageBox, etc.) que
    no tienen una regla propia en `hoja_estilos`.

    El color de selección (Highlight) se fuerza a un naranja suave en
    los dos modos -no es solo cosa del modo oscuro- porque el celeste/
    azul por defecto del sistema para la fila/ítem seleccionado se
    confunde con el azul de los títulos (COLOR_NIVEL_1); confirmado por
    la clienta para cualquier tabla o lista de toda la aplicación, no
    solo una pantalla puntual (probado primero en gris, después
    cambiado a este naranja suave a pedido de la clienta)."""
    t = _OSCURO if modo_oscuro else _CLARO
    p = QPalette()
    p.setColor(QPalette.ColorRole.Highlight, QColor(t["resalte_seleccion"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(t["texto"]))
    if not modo_oscuro:
        return p

    fondo = QColor(_OSCURO["fondo"])
    superficie = QColor(_OSCURO["superficie"])
    texto = QColor(_OSCURO["texto"])
    texto_apagado = QColor("#8A8F98")
    azul = QColor(COLOR_NIVEL_1)

    p.setColor(QPalette.ColorRole.Window, fondo)
    p.setColor(QPalette.ColorRole.WindowText, texto)
    p.setColor(QPalette.ColorRole.Base, superficie)
    p.setColor(QPalette.ColorRole.AlternateBase, fondo)
    p.setColor(QPalette.ColorRole.Text, texto)
    p.setColor(QPalette.ColorRole.Button, superficie)
    p.setColor(QPalette.ColorRole.ButtonText, texto)
    p.setColor(QPalette.ColorRole.BrightText, QColor("#FF6B6B"))
    p.setColor(QPalette.ColorRole.ToolTipBase, superficie)
    p.setColor(QPalette.ColorRole.ToolTipText, texto)
    p.setColor(QPalette.ColorRole.PlaceholderText, texto_apagado)
    p.setColor(QPalette.ColorRole.Link, azul)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, texto_apagado)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, texto_apagado)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, texto_apagado)
    return p
