"""Pantalla "Grilla operativa" (punto 21 de la miscelánea, ago-2026):
por ahora solo la grilla filtrable en sí (`GrillaOperativaWidget`). Las
secciones de "valores de los consultorios" y "estadísticas" que pidió
el usuario para esta pantalla se agregan en un paso siguiente."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.gui.widgets.grilla_operativa import GrillaOperativaWidget


class PantallaGrillaOperativa(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)

        titulo = QLabel("Grilla operativa")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.grilla = GrillaOperativaWidget(conn)
        layout.addWidget(self.grilla, stretch=1)
