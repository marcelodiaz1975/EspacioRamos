"""Llaves y otros conceptos (reordenamiento de formularios, Excel de la
clienta): formulario nuevo que agrupa "Llaves" (antes pantalla propia del
menú, como solapa "Movimientos y tenencias de llaves") con las dos solapas
que ya tenía "Cargos especiales" (antes también pantalla propia del menú):
"Registro de cargos especiales" y "Estado de cuenta" — ambas sin ningún
cambio, se importan cruzadas tal cual estaban en `novedades.py`.

Mismo patrón que el resto de los formularios compuestos: título Nivel 1
fijo + `QTabWidget` con las tres solapas."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from app.gui.pantallas.llaves import _PanelLlaves
from app.gui.pantallas.novedades import _PanelCargosEspeciales, _PanelEstadoCuentaCargos


class PantallaLlavesYOtrosConceptos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Llaves y otros conceptos".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_llaves = _PanelLlaves(conn)
        self.panel_cargos_especiales = _PanelCargosEspeciales(conn)
        self.panel_estado_cuenta = _PanelEstadoCuentaCargos(conn)
        self.pestanas.addTab(self.panel_llaves, "Movimientos y tenencias de llaves")
        self.pestanas.addTab(self.panel_cargos_especiales, "Registro de cargos especiales")
        self.pestanas.addTab(self.panel_estado_cuenta, "Estado de cuenta")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)

    def actualizar(self) -> None:
        self.panel_cargos_especiales.actualizar()
        self.panel_estado_cuenta.actualizar()
