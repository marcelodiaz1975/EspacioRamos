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
        pantallas): el FONDO usa dos tonos de gris — la solapa ACTIVA
        usa el tono CLARO (`t['superficie']`), que es el mismo fondo que
        el panel de contenido (QTabWidget::pane, también
        `t['superficie']`) — pierde el borde de abajo
        (`border-bottom-color` igual al fondo del panel) para que el
        borde la envuelva arriba/izquierda/derecha nada más, como si el
        panel fuera la continuación de la solapa. La solapa INACTIVA usa
        el tono OSCURO (`t['fondo']`, el mismo fondo que el resto de la
        ventana — "el exterior") de fondo, con su borde completo incluida
        la línea de abajo, y baja 2px (`margin-top`) para quedar
        visualmente "detrás" de la activa, como una ficha de fichero de
        papel. El BORDE (pane y las dos solapas) es negro
        (`#000000`) — se probó en un gris oscuro a tono con el fondo de
        la solapa inactiva al revisar Registro de ausencias, pero la
        clienta pidió volver al negro al revisar Vista rápida/
        Estadísticas, para todas las pantallas ("como está en Lista de
        espera"). `QTabWidget::pane` sube 1px (`top: -1px`) para que su
        borde superior quede tapado exactamente donde se apoya la solapa
        activa, sin una línea doble ahí.

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
        Se probó en negrita, pero la clienta pidió sacarla al revisar
        Registro de ausencias — queda con el mismo peso que el texto
        normal, sin nada que la distinga visualmente; el objectName se
        mantiene igual como gancho por si hace falta diferenciarla más
        adelante.

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
COLOR_FOCO = "#FFC107"  # ámbar — anillo de foco de teclado (Tab), ver "Indicador de foco" más abajo

# Se probó fijar la fuente de toda la app a "Segoe UI" (para que el
# ancho real del texto no dependiera de la fuente default de cada
# instalación de Windows) pero se revirtió a pedido explícito de la
# clienta: esa fuente resolvía un tamaño de punto más grande que el
# default que ya traía su Windows, y contra los anchos/altos fijos
# calibrados pixel a pixel en todo el sistema eso apelmazaba el
# contenido — ver `gui_main.main()`, que ya no fija ninguna fuente.

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
QListWidget#navegacion::item:selected {{
    background-color: {COLOR_DIA_GRILLA}; color: {COLOR_TEXTO_CLARO}; font-weight: bold;
}}
QListWidget#navegacion::item:hover {{ background-color: {t['hover_nav']}; }}
QListWidget#navegacion::item:disabled {{
    background-color: {COLOR_NIVEL_1_OSCURO}; font-weight: bold;
}}

QLabel#tituloPantalla {{
    font-size: 18px; font-weight: bold; font-style: italic; color: {t['texto']};
    padding: 6px 0px;
}}
QLabel#subtitulo {{ font-size: 11px; color: {'#AAAAAA' if modo_oscuro else '#555555'}; }}
QLabel#subtituloSeccion {{ font-size: 15px; font-weight: bold; color: {t['texto']}; padding: 4px 0px; }}
QLabel#subtituloCampo {{ }}
QTabWidget::pane {{
    background-color: {t['superficie']};
    border: 1px solid #000000;
    top: -1px;
}}
QTabBar::tab {{
    font-size: 14px; font-weight: bold; color: {t['texto']};
    background-color: {t['fondo']};
    border: 1px solid #000000;
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

QPushButton#botonSecundario {{
    background-color: #BFE3F5; color: #14324A;
    border: 1px solid #000000; border-radius: 4px; padding: 8px 16px; font-weight: bold;
}}
QPushButton#botonSecundario:hover:!disabled {{ background-color: #A6D6EF; }}
QPushButton#botonSecundario:disabled {{ background-color: #DDDDDD; color: #9A9A9A; }}

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

/* Punto 23 (SistemaDF v0.11.2026.10): a la tabla de Gestor de archivos
le faltaba el mismo recuadro negro fino que ya tienen los filtros
(QLineEdit/QComboBox, ver más abajo) — se confundía contra el fondo.
`QTableView` es la clase base de `QTableWidget`, así que cubre de una a
cualquier tabla del sistema. */
QTableView {{ gridline-color: {t['borde']}; border: 1px solid #000000; }}
QHeaderView::section {{
    background-color: {COLOR_NIVEL_1_OSCURO}; color: {COLOR_TEXTO_CLARO};
    font-weight: bold; padding: 4px; border: none;
}}
QHeaderView:vertical {{ qproperty-defaultAlignment: AlignCenter; }}

/* Indicador de foco en botones (pedido explícito de la clienta): "toco
Tab, pasa de botón en botón, pero no veo dónde estoy parado" — el estilo
propio de botonPrimario/botonSecundario (fondo + borde negro) le ganaba
al rectángulo de foco nativo que dibuja el estilo base de Qt, así que
quedaba invisible. `outline` (no `border`) porque no ocupa espacio de
layout — a diferencia de agrandar el borde en :focus, que correría el
contenido un par de píxeles cada vez que el botón gana o pierde el foco.

Comprobado con capturas reales (`outline` no es parejo entre tipos de
widget en Qt): funciona bien acá (QPushButton) y QLineEdit/QDateEdit/
QSpinBox/QDoubleSpinBox ya traían su propio foco nativo visible (borde
celeste, por el QLineEdit interno que usan esos últimos tres) sin
necesitar nada de esto, pero `outline` NO llegó a pintarse en absoluto
en QComboBox/QCheckBox/QPlainTextEdit/QTextEdit/QTabBar.

Pedido explícito de la clienta sobre Reservas ("no veo en los cheks ni
en los botones"): para QComboBox/QCheckBox hace falta `border` en vez
de `outline` — a diferencia de los botones, cambiar el tamaño en :focus
hubiera corrido el contenido de alrededor cada vez que el control gana o
pierde el foco, así que se reserva el mismo espacio siempre
(`border: 2px solid transparent` en reposo, color real solo en :focus)
en vez de agregarlo recién al enfocar.

Mismo hueco encontrado al revisar Aumentos (pedido explícito: "revisá
si falta el foco visible en esta pantalla"): los `QRadioButton` de
"Múltiplos de..." (los únicos de todo el sistema que pasan por
`instalar_enter_avanza_foco`) tampoco tenían ninguna regla propia —
mismo criterio `border` que QComboBox/QCheckBox. */
QPushButton:focus {{
    outline: 2px solid {COLOR_FOCO};
    outline-offset: 1px;
}}
QComboBox {{ border: 2px solid #000000; border-radius: 2px; }}
QComboBox:focus {{ border: 2px solid {COLOR_FOCO}; }}
QCheckBox {{ border: 2px solid transparent; border-radius: 2px; padding: 1px; }}
QCheckBox:focus {{ border: 2px solid {COLOR_FOCO}; }}
QRadioButton {{ border: 2px solid transparent; border-radius: 2px; padding: 1px; }}
QRadioButton:focus {{ border: 2px solid {COLOR_FOCO}; }}

/* Pedido general de la clienta ("recuadro alrededor del filtro
seleccionable"): a varios cuadros de texto/filtro les faltaba la línea
negra finita que los delimita visualmente — `QComboBox` ya tenía un
borde (ver arriba), pero transparente en reposo (solo se veía al
enfocar); `QLineEdit` dependía por completo del estilo nativo de cada
plataforma, que en algunos casos lo deja prácticamente invisible. Mismo
criterio "borde negro fino" que el resto de la app (botones, solapas,
tabla). `QComboBox` sube de `transparent` a `#000000` en reposo (mismo
ancho de 2px que ya tenía, así el foco no corre nada al ganar/perder
color). */
QLineEdit {{ border: 1px solid #000000; border-radius: 2px; padding: 1px 2px; }}

/* Scrollbars con contraste explícito, parejo en toda la app — pedido de
la clienta al revisar Grilla semanal ("no aparece el scroll
horizontal"): sin esta regla, el thumb queda pintado con el tema nativo
de cada instalación, que en algunos casos (ciertos temas claros de
Windows) lo deja en un gris muy parecido al fondo — ahí sigue
funcionando (se puede arrastrar, aparece cuando hace falta), pero se
percibe como "ausente" a simple vista. Mismo criterio de "borde negro
fino" que el resto de la app en el thumb, para que se note sin
depender de qué tan buen contraste traiga el estilo nativo de turno. */
QScrollBar:horizontal {{
    background: {t['fondo']}; height: 14px; border: 1px solid {t['borde']}; margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: #8A8A8A; min-width: 24px; border: 1px solid #000000; border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{ background: #6E6E6E; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
QScrollBar:vertical {{
    background: {t['fondo']}; width: 14px; border: 1px solid {t['borde']}; margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: #8A8A8A; min-height: 24px; border: 1px solid #000000; border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{ background: #6E6E6E; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ width: 0px; }}
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
