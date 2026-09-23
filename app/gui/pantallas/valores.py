"""Valores (reordenamiento de formularios, Excel de la clienta): formulario
nuevo que agrupa "Valores vigentes" (antes "Valores de los consultorios",
segunda solapa de "Vista rápida" — ver `grilla_operativa.py`) junto con las
dos solapas de la ex pantalla "Aumentos y descuentos" ("Aumentos"/"Esquema
de descuentos" — ver `aumentos.py`), todas relacionadas con el valor hora
de los consultorios.

Mismo patrón que Usuarios y permisos/Archivos y listas: título Nivel 1 fijo
+ `QTabWidget` con las tres solapas, cada una responsable de su propio
`showEvent`/foco."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from app.gui.pantallas.aumentos import _PanelAumentos, _PanelEsquemaDescuentos
from app.gui.pantallas.grilla_operativa import _PanelValoresVigentes


class PantallaValores(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Valores".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_valores_vigentes = _PanelValoresVigentes(conn)
        self.pestanas.addTab(self.panel_valores_vigentes, "Valores vigentes")
        self.panel_aumentos = _PanelAumentos(conn)
        self.pestanas.addTab(self.panel_aumentos, "Aumentos")
        self.panel_esquema = _PanelEsquemaDescuentos(conn)
        self.pestanas.addTab(self.panel_esquema, "Esquema de descuentos")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
