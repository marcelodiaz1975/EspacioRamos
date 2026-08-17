"""Estilos compartidos por las pantallas de la aplicación — reusa la
misma paleta que los PDFs (app/pdf/estilos.py) para que la app y los
documentos que genera se sientan del mismo sistema."""
from __future__ import annotations

COLOR_NIVEL_1 = "#2E86AB"  # azul — encabezados principales, botón primario
COLOR_NIVEL_2 = "#E07B39"  # naranja — sub-encabezados
COLOR_DIA_GRILLA = "#6B0000"  # bordó — encabezados de grilla
COLOR_VERDE = "#4CAF50"
COLOR_AMARILLO = "#F5D547"
COLOR_ROJO = "#C0392B"
COLOR_FONDO = "#F5F5F5"
COLOR_TEXTO_CLARO = "#FFFFFF"

HOJA_ESTILOS = f"""
QMainWindow {{ background-color: {COLOR_FONDO}; }}

QListWidget#navegacion {{
    background-color: {COLOR_NIVEL_1};
    color: {COLOR_TEXTO_CLARO};
    border: none;
    font-size: 13px;
    outline: none;
}}
QListWidget#navegacion::item {{ padding: 10px 14px; }}
QListWidget#navegacion::item:selected {{ background-color: {COLOR_DIA_GRILLA}; }}
QListWidget#navegacion::item:hover {{ background-color: #3A6EA5; }}

QLabel#tituloPantalla {{
    font-size: 18px; font-weight: bold; color: {COLOR_NIVEL_1};
    padding: 6px 0px;
}}
QLabel#subtitulo {{ font-size: 11px; color: #555555; }}

QPushButton#botonPrimario {{
    background-color: {COLOR_NIVEL_1}; color: {COLOR_TEXTO_CLARO};
    border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold;
}}
QPushButton#botonPrimario:disabled {{ background-color: #A0AEC0; }}
QPushButton#botonPrimario:hover:!disabled {{ background-color: #256a89; }}

QFrame#tarjetaAlerta {{
    background-color: white; border: 1px solid #DDDDDD; border-radius: 4px;
}}
QLabel#encabezadoAlerta {{
    background-color: {COLOR_NIVEL_2}; color: {COLOR_TEXTO_CLARO};
    font-weight: bold; padding: 4px 8px;
}}

QLabel#barraFechaFicticia {{
    background-color: {COLOR_ROJO}; color: {COLOR_TEXTO_CLARO};
    font-weight: bold; font-size: 12px; padding: 6px 12px;
}}

QTableView {{ gridline-color: #DDDDDD; }}
QHeaderView::section {{
    background-color: {COLOR_NIVEL_1}; color: {COLOR_TEXTO_CLARO}; padding: 4px; border: none;
}}
"""
