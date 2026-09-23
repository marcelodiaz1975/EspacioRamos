"""Archivos y listas (reordenamiento de formularios, Excel de la clienta):
formulario nuevo que agrupa cuatro pantallas antes independientes del menú,
todas relacionadas con contenido "de referencia" del espacio — archivos y
listas cerradas/semiabiertas que se leen desde otras pantallas y PDFs — que
no tenían relación de navegación entre sí hasta esta reorganización:

- "Gestor de archivos del espacio" (`_PanelGestorArchivos`, antes la
  pantalla propia "Gestor de archivos" — ver `imagenes.py`).
- "Listas editables", "Condiciones y normas" y "Detalles complementarios
  de la propuesta" (los tres, catálogos genéricos de `catalogos.py`,
  construidos acá con `anidado=True` — ver `crud_generico.py` — en vez de
  como pantallas de catálogo independientes).

Mismo patrón que Usuarios y permisos/Estadísticas: título Nivel 1 fijo +
`QTabWidget` con las cuatro solapas, cada una responsable de su propio
`showEvent`/foco (los tres catálogos genéricos ya lo traen incorporado por
`PantallaCRUD`; Gestor de archivos nunca tuvo cadena de foco propia — no
formó parte de la revisión "uno por uno" — y no se le agregó acá, fuera del
alcance de esta reorganización).

Recibe `secciones` (la lista de `Seccion` del menú, mismo dato que ya
recibía la vieja pantalla "Archivos varios") y se la reenvía a
`_PanelGestorArchivos`, que la necesita para el botón "Manual del
usuario" reubicado ahí (ver `imagenes.py`)."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from app.gui.main_window import Seccion
from app.gui.pantallas.catalogos import (
    pantalla_condiciones_normas,
    pantalla_detalles_complementarios_propuesta,
    pantalla_listas_editables,
)
from app.gui.pantallas.imagenes import _PanelGestorArchivos


class PantallaArchivosYListas(QWidget):
    def __init__(self, conn: sqlite3.Connection, secciones: list[Seccion] | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Archivos y listas".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_gestor_archivos = _PanelGestorArchivos(conn, secciones)
        self.pestanas.addTab(self.panel_gestor_archivos, "Gestor de archivos del espacio")
        self.panel_listas_editables = pantalla_listas_editables(conn, anidado=True)
        self.pestanas.addTab(self.panel_listas_editables, "Listas editables")
        self.panel_condiciones_normas = pantalla_condiciones_normas(conn, anidado=True)
        self.pestanas.addTab(self.panel_condiciones_normas, "Condiciones y normas")
        self.panel_detalles_complementarios = pantalla_detalles_complementarios_propuesta(conn, anidado=True)
        self.pestanas.addTab(self.panel_detalles_complementarios, "Detalles complementarios de la propuesta")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
