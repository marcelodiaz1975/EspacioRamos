"""Ventana principal: navegación lateral + panel de contenido apilado.

Cada pantalla se registra como (nombre, categoría, fábrica) — la fábrica
recibe la conexión abierta y devuelve el QWidget de esa sección. Las
pantallas se instancian de una sola vez (no al hacer clic) para que
conserven su estado entre visitas dentro de la misma sesión."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget, QWidget

from app.gui.estilos import HOJA_ESTILOS


@dataclass
class Seccion:
    nombre: str
    fabrica: Callable[[sqlite3.Connection], QWidget]
    categoria: str = "General"


_INDICE_PILA = Qt.ItemDataRole.UserRole


class VentanaPrincipal(QMainWindow):
    def __init__(self, conn: sqlite3.Connection, secciones: list[Seccion]):
        super().__init__()
        self.conn = conn
        self.setWindowTitle("Sistema Espacio Ramos")
        self.resize(1200, 800)
        self.setStyleSheet(HOJA_ESTILOS)

        self._navegacion = QListWidget()
        self._navegacion.setObjectName("navegacion")
        self._navegacion.setFixedWidth(240)
        self._pila = QStackedWidget()

        categoria_actual = None
        primer_item_seleccionable = None
        for seccion in secciones:
            if seccion.categoria != categoria_actual:
                separador = QListWidgetItem(f"— {seccion.categoria.upper()} —")
                separador.setFlags(Qt.ItemFlag.NoItemFlags)
                self._navegacion.addItem(separador)
                categoria_actual = seccion.categoria

            indice_pila = self._pila.count()
            widget = seccion.fabrica(conn)
            self._pila.addWidget(widget)

            item = QListWidgetItem(seccion.nombre)
            item.setData(_INDICE_PILA, indice_pila)
            self._navegacion.addItem(item)
            if primer_item_seleccionable is None:
                primer_item_seleccionable = self._navegacion.count() - 1

        self._navegacion.currentRowChanged.connect(self._cambiar_seccion)
        if primer_item_seleccionable is not None:
            self._navegacion.setCurrentRow(primer_item_seleccionable)

        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._navegacion)
        layout.addWidget(self._pila, stretch=1)
        self.setCentralWidget(contenedor)

    def _cambiar_seccion(self, fila: int) -> None:
        if fila < 0:
            return
        item = self._navegacion.item(fila)
        indice_pila = item.data(_INDICE_PILA)
        if indice_pila is None:
            return
        self._pila.setCurrentIndex(indice_pila)
