"""Grilla y mensajería (reordenamiento de formularios, Excel de la
clienta): formulario nuevo que agrupa tres pantallas antes independientes
del menú, todas relacionadas con la operatoria semanal de la grilla y la
comunicación con los profesionales: "Grilla semanal" (antes primera solapa
de "Vista rápida" — ver `grilla_operativa.py`, cuyas otras dos solapas se
repartieron entre este formulario y "Valores"/se sacaron del sistema),
"Centro de mensajería" y "Mensajes predefinidos" (antes pantallas propias
del menú).

Mismo patrón que Usuarios y permisos/Archivos y listas: título Nivel 1 fijo
+ `QTabWidget` con las tres solapas, cada una responsable de su propio
`showEvent`/foco."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from app.gui.pantallas.grilla_operativa import _PanelGrillaSemanal
from app.gui.pantallas.mensajeria import _PanelCentroMensajeria
from app.gui.pantallas.mensajes_predefinidos import _PanelMensajesPredefinidos


class PantallaGrillaYMensajeria(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Grilla y mensajería".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_grilla = _PanelGrillaSemanal(conn)
        self.pestanas.addTab(self.panel_grilla, "Grilla semanal")
        self.panel_mensajeria = _PanelCentroMensajeria(conn)
        self.pestanas.addTab(self.panel_mensajeria, "Centro de mensajería")
        self.panel_mensajes_predefinidos = _PanelMensajesPredefinidos(conn)
        self.pestanas.addTab(self.panel_mensajes_predefinidos, "Mensajes predefinidos")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
