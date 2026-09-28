"""Placas para timbres (reordenamiento de formularios, Excel de la
clienta): agrupa la pantalla operativa "Placas" (antes formulario propio
del menú), con sus dos solapas ("Búsqueda y asignación de placas"/
"Impresión de placas en papel", renombradas — ver `_PanelPlacasOperativas`
en `placas.py`).

Tenía una tercera solapa, el catálogo "Placas" (el tablero de posiciones/
nombre grabado, `catalogos.pantalla_placas`) — caso no contemplado en el
Excel de la clienta, sumado en su momento porque compartía nombre con
esta pantalla operativa. Se sacó a pedido explícito de la clienta al
revisar esta pantalla: esa solapa repetía la misma función que ya cubre
"Búsqueda y asignación de placas" (dar de alta/reasignar/liberar una
posición del tablero), solo que sin las validaciones ni la vista
integrada con la tabla — `catalogos.pantalla_placas` se borró de
`catalogos.py` al quedar sin ningún otro consumidor."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

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
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
