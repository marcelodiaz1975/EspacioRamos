"""Disponibilidad (reordenamiento de formularios, Excel de la clienta):
formulario nuevo que agrupa tres pantallas antes independientes del menú,
todas relacionadas con ofrecer/coordinar horarios libres a profesionales
interesados: "Oferta de consultorios" (búsqueda ad hoc + PDF/texto de
oferta), "Lista de espera" (pedidos agendados, cruzados automáticamente
contra la disponibilidad real) y "Archivos para enviar" (antes "Archivos
varios": regenerar Propuesta/Disponibilidad a demanda).

Mismo patrón que Usuarios y permisos/Archivos y listas: título Nivel 1 fijo
+ `QTabWidget` con las tres solapas, cada una responsable de su propio
`showEvent`/foco."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from app.gui.pantallas.archivos_varios import _PanelArchivosVarios
from app.gui.pantallas.lista_espera import _PanelListaEspera
from app.gui.pantallas.oferta import _PanelOferta


class PantallaDisponibilidad(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Disponibilidad".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_oferta = _PanelOferta(conn)
        self.pestanas.addTab(self.panel_oferta, "Oferta de consultorios")
        self.panel_lista_espera = _PanelListaEspera(conn)
        self.pestanas.addTab(self.panel_lista_espera, "Lista de espera")
        self.panel_archivos_varios = _PanelArchivosVarios(conn)
        self.pestanas.addTab(self.panel_archivos_varios, "Archivos para enviar")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
