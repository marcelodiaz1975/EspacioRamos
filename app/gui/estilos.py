"""Estilos compartidos por las pantallas de la aplicación — reusa la
misma paleta que los PDFs (app/pdf/estilos.py) para que la app y los
documentos que genera se sientan del mismo sistema.

Modo oscuro (Configuracion.ModoOscuro, default apagado): además de la
hoja de estilos con los nombres de objeto propios de la app
(tituloPantalla, botonPrimario, etc.), se arma una QPalette para que los
widgets estándar sin estilo propio (QLineEdit, QComboBox, QTableWidget,
QCheckBox, diálogos) seas consistentes sin tener que escribir una regla
QSS por cada pantalla."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

COLOR_NIVEL_1 = "#2E86AB"  # azul — encabezados principales, botón primario
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
    "resalte_seleccion": "#D6D6D6",
}

# ------------------------------------------------------------------ oscuro
_OSCURO = {
    "fondo": "#1E2124",
    "superficie": "#2A2E33",
    "texto": "#E8E6E3",
    "borde": "#3F454C",
    "hover_nav": "#3A6EA5",
    "resalte_seleccion": "#5A5F66",
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
    font-size: 18px; font-weight: bold; color: {COLOR_NIVEL_1};
    padding: 6px 0px;
}}
QLabel#subtitulo {{ font-size: 11px; color: {'#AAAAAA' if modo_oscuro else '#555555'}; }}
QLabel#subtituloSeccion {{ font-size: 15px; font-weight: bold; color: {COLOR_NIVEL_1}; padding: 4px 0px; }}
QGroupBox#panelFiltrosGrilla::title {{
    font-size: 15px; font-weight: bold; color: {t['texto']};
    subcontrol-origin: margin; padding: 4px 0px;
}}

QPushButton#botonPrimario {{
    background-color: {COLOR_NIVEL_1}; color: {COLOR_TEXTO_CLARO};
    border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold;
}}
QPushButton#botonPrimario:disabled {{ background-color: #A0AEC0; }}
QPushButton#botonPrimario:hover:!disabled {{ background-color: #256a89; }}

QPushButton#botonAccion {{ padding: 8px 16px; }}

QPushButton#botonSecundario {{
    background-color: #BFE3F5; color: #14324A;
    border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold;
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
    background-color: {COLOR_NIVEL_1}; color: {COLOR_TEXTO_CLARO}; padding: 4px; border: none;
}}
"""



def paleta(modo_oscuro: bool = False) -> QPalette:
    """QPalette aplicada a nivel QApplication: cubre los widgets estándar
    (QLineEdit, QComboBox, QTableWidget, QCheckBox, QMessageBox, etc.) que
    no tienen una regla propia en `hoja_estilos`.

    El color de selección (Highlight) se fuerza a gris en los dos modos
    -no es solo cosa del modo oscuro- porque el celeste/azul por defecto
    del sistema para la fila/ítem seleccionado se confunde con el azul
    de los títulos (COLOR_NIVEL_1); confirmado por la clienta para
    cualquier tabla o lista de toda la aplicación, no solo esta
    pantalla."""
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
