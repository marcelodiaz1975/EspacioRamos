"""Archivos varios (Etapa 9): regenerar a demanda, contra el estado actual
del sistema, los documentos únicos del espacio en general — Propuesta y
Disponibilidad — que se guardan en su subcarpeta bajo Archivos varios en
la carpeta base configurada. También se regeneran solos en el avance de
mes (`app.negocio.avance_mes`); esta pantalla es para cuando hace falta
actualizarlos en el medio del mes (p. ej. después de dar de alta un
edificio nuevo).

Placas (Etapa 9 originalmente, sacado de acá a pedido de la clienta):
"Regenerar Placas" dejó de estar en esta pantalla — el armado de placas
va a necesitar su propia pantalla (agenda de qué profesional tiene placa
en qué unidad/posición, selección puntual de cuáles imprimir, etc.), a
definir si queda como formulario independiente o como solapa dentro de
otra pantalla existente. `app.pdf.placas_pdf.generar_pdf_placas` sigue
existiendo tal cual y se sigue regenerando solo en el avance de mes."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app.gui.main_window import Seccion
from app.negocio.archivos_generados import (
    SUBCARPETA_DISPONIBILIDAD,
    SUBCARPETA_MANUAL,
    SUBCARPETA_PROPUESTA,
    carpeta_archivos_varios,
)
from app.pdf.disponibilidad_pdf import generar_pdfs_disponibilidad_por_localidad
from app.pdf.manual_pdf import generar_pdf_manual
from app.pdf.propuesta_pdf import generar_pdfs_propuesta_por_localidad


class PantallaArchivosVarios(QWidget):
    def __init__(self, conn: sqlite3.Connection, secciones: list[Seccion] | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._secciones = secciones or []
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        titulo = QLabel("Archivos varios".upper())
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
        boton_propuesta.setObjectName("botonSecundario")
        boton_propuesta.clicked.connect(self._regenerar_propuesta)
        fila.addWidget(boton_propuesta)

        boton_disponibilidad = QPushButton("Regenerar Disponibilidad")
        boton_disponibilidad.setObjectName("botonSecundario")
        boton_disponibilidad.clicked.connect(self._regenerar_disponibilidad)
        fila.addWidget(boton_disponibilidad)

        boton_manual = QPushButton("Regenerar Manual de usuario")
        boton_manual.setObjectName("botonSecundario")
        boton_manual.clicked.connect(self._regenerar_manual)
        fila.addWidget(boton_manual)
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

    def _regenerar_manual(self) -> None:
        if not self._secciones:
            QMessageBox.warning(
                self, "Regenerar Manual de usuario", "No hay ayuda contextual disponible para armar el manual.",
            )
            return
        tuplas = [(s.categoria, s.nombre, s.ayuda) for s in self._secciones]
        self._regenerar(
            "Manual de usuario", SUBCARPETA_MANUAL,
            lambda conn, directorio: [generar_pdf_manual(conn, directorio, tuplas)],
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
