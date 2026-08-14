"""Archivos varios (Etapa 9): regenerar a demanda, contra el estado actual
del sistema, los documentos únicos del espacio en general — Propuesta y
Disponibilidad — que se guardan en Archivos varios/Propuesta y Archivos
varios/Disponibilidad bajo la carpeta base configurada. También se
regeneran solos en el avance de mes (`app.negocio.avance_mes`); esta
pantalla es para cuando hace falta actualizarlos en el medio del mes (p.
ej. después de dar de alta un edificio nuevo)."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app.negocio.archivos_generados import SUBCARPETA_DISPONIBILIDAD, SUBCARPETA_PROPUESTA, carpeta_archivos_varios
from app.pdf.disponibilidad_pdf import generar_pdfs_disponibilidad_por_localidad
from app.pdf.propuesta_pdf import generar_pdfs_propuesta_por_localidad


class PantallaArchivosVarios(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        titulo = QLabel("Archivos varios")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        subtitulo = QLabel(
            "Regenerá acá, contra el estado actual del sistema, los documentos que ya se "
            "vuelven a generar solos en el avance de mes."
        )
        subtitulo.setObjectName("subtitulo")
        subtitulo.setWordWrap(True)
        layout.addWidget(subtitulo)

        fila = QHBoxLayout()
        boton_propuesta = QPushButton("Regenerar Propuesta")
        boton_propuesta.clicked.connect(self._regenerar_propuesta)
        fila.addWidget(boton_propuesta)

        boton_disponibilidad = QPushButton("Regenerar Disponibilidad")
        boton_disponibilidad.clicked.connect(self._regenerar_disponibilidad)
        fila.addWidget(boton_disponibilidad)
        fila.addStretch()
        layout.addLayout(fila)
        layout.addStretch()

    def _regenerar_propuesta(self) -> None:
        self._regenerar(
            "Propuesta", SUBCARPETA_PROPUESTA, generar_pdfs_propuesta_por_localidad,
        )

    def _regenerar_disponibilidad(self) -> None:
        self._regenerar(
            "Disponibilidad", SUBCARPETA_DISPONIBILIDAD, generar_pdfs_disponibilidad_por_localidad,
        )

    def _regenerar(self, etiqueta: str, subcarpeta: str, generador) -> None:
        try:
            directorio = str(carpeta_archivos_varios(self.conn, subcarpeta))
            rutas = generador(self.conn, directorio)
        except ValueError as error:
            QMessageBox.warning(self, f"Regenerar {etiqueta}", str(error))
            return
        QMessageBox.information(
            self, f"Regenerar {etiqueta}", f"Se generó {len(rutas)} archivo(s) en:\n{directorio}",
        )
