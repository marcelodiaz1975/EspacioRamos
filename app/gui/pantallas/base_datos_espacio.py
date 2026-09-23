"""Base datos del espacio (reordenamiento de formularios, Excel de la
clienta): formulario nuevo que agrupa los cinco catálogos de la estructura
física/de contacto del espacio — antes cinco pantallas propias e
independientes del menú, sin relación de navegación entre sí — en el orden
de la cadena de referencias que ya usan entre sí (Localidad → Edificio →
Unidad → Consultorio, más Responsables): "Localidades", "Edificios",
"Unidades", "Consultorios", "Responsables".

Mismo patrón que Usuarios y permisos/Archivos y listas: título Nivel 1 fijo
+ `QTabWidget` con las cinco solapas, cada `PantallaCRUD` construida con
`anidado=True` (ver `crud_generico.py`)."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from app.gui.pantallas import catalogos


class PantallaBaseDatosEspacio(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Base datos del espacio".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_localidades = catalogos.pantalla_localidades(conn, anidado=True)
        self.pestanas.addTab(self.panel_localidades, "Localidades")
        self.panel_edificios = catalogos.pantalla_edificios(conn, anidado=True)
        self.pestanas.addTab(self.panel_edificios, "Edificios")
        self.panel_unidades = catalogos.pantalla_unidades(conn, anidado=True)
        self.pestanas.addTab(self.panel_unidades, "Unidades")
        self.panel_consultorios = catalogos.pantalla_consultorios(conn, anidado=True)
        self.pestanas.addTab(self.panel_consultorios, "Consultorios")
        self.panel_responsables = catalogos.pantalla_responsables(conn, anidado=True)
        self.pestanas.addTab(self.panel_responsables, "Responsables")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
