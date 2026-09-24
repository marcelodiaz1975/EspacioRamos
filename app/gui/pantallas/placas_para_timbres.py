"""Placas para timbres (reordenamiento de formularios, Excel de la
clienta): agrupa la pantalla operativa "Placas" (antes formulario propio
del menú) con el catálogo "Placas" (el tablero de posiciones/nombre
grabado, distinto de la pantalla operativa aunque comparten nombre) —
caso no contemplado en el Excel de la clienta, resuelto con ella: pasa a
ser la tercera solapa de este formulario.

Tres solapas: "Búsqueda y asignación de placas"/"Impresión de placas en
papel" (las dos de la vieja pantalla operativa, renombradas — ver
`_PanelPlacasOperativas` en `placas.py`) y "Placas" (el catálogo,
anidado vía `catalogos.pantalla_placas`)."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from app.gui.pantallas import catalogos
from app.gui.pantallas.placas import _PanelPlacasOperativas


class PantallaPlacasParaTimbres(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Placas para timbres".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_operativas = _PanelPlacasOperativas(conn)
        self.pestanas.addTab(self.panel_operativas.panel_buscar, "Búsqueda y asignación de placas")
        self.pestanas.addTab(self.panel_operativas.panel_imprimir, "Impresión de placas en papel")
        self.panel_catalogo_placas = catalogos.pantalla_placas(conn, anidado=True)
        self.pestanas.addTab(self.panel_catalogo_placas, "Placas")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
