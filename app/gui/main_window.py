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
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

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

        self._barra_fecha_ficticia = QLabel()
        self._barra_fecha_ficticia.setObjectName("barraFechaFicticia")
        self._barra_fecha_ficticia.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._barra_fecha_ficticia.hide()

        self._navegacion.currentRowChanged.connect(self._cambiar_seccion)
        if primer_item_seleccionable is not None:
            self._navegacion.setCurrentRow(primer_item_seleccionable)
        else:
            self._actualizar_barra_fecha_ficticia()

        fila_principal = QWidget()
        layout_fila = QHBoxLayout(fila_principal)
        layout_fila.setContentsMargins(0, 0, 0, 0)
        layout_fila.setSpacing(0)
        layout_fila.addWidget(self._navegacion)
        layout_fila.addWidget(self._pila, stretch=1)

        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._barra_fecha_ficticia)
        layout.addWidget(fila_principal, stretch=1)
        self.setCentralWidget(contenedor)

    def _actualizar_barra_fecha_ficticia(self) -> None:
        """Modo de fecha ficticia para testing (sección 2): barra bien
        visible mientras está activo, para no confundir datos de prueba
        con reales — se revisa en cada cambio de pantalla, ya que
        Configuración general puede activarlo/desactivarlo en cualquier
        momento durante la sesión."""
        cfg = self.conn.execute(
            "SELECT ModoFechaFicticia, FechaFicticia FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        activo = bool(cfg and cfg["ModoFechaFicticia"] and cfg["FechaFicticia"])
        if activo:
            self._barra_fecha_ficticia.setText(
                f"⚠ MODO FECHA FICTICIA ACTIVO — Hoy simulado: {cfg['FechaFicticia']} ⚠"
            )
        self._barra_fecha_ficticia.setVisible(activo)

    def _cambiar_seccion(self, fila: int) -> None:
        if fila < 0:
            return
        item = self._navegacion.item(fila)
        indice_pila = item.data(_INDICE_PILA)
        if indice_pila is None:
            return
        self._pila.setCurrentIndex(indice_pila)
        self._actualizar_barra_fecha_ficticia()
