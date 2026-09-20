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
existiendo tal cual y se sigue regenerando solo en el avance de mes.

Formato solapa (revisión uno por uno): los tres botones quedan en una
columna izquierda de ancho fijo, todos `botonSecundario` (son acciones
independientes, ninguna más "definitiva" que las otras). A la derecha,
un cuadro de previsualización muestra la primera página del archivo que
acaba de regenerarse (reusa `_pixmap_primera_pagina_pdf` de
`imagenes.py`, la misma vista previa de PDF que usa Gestor de
archivos) — Propuesta/Disponibilidad generan un archivo por localidad,
así que se previsualiza el primero de la lista devuelta."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.main_window import Seccion
from app.gui.pantallas.imagenes import _pixmap_primera_pagina_pdf
from app.negocio.archivos_generados import (
    SUBCARPETA_DISPONIBILIDAD,
    SUBCARPETA_MANUAL,
    SUBCARPETA_PROPUESTA,
    carpeta_archivos_varios,
)
from app.pdf.disponibilidad_pdf import generar_pdfs_disponibilidad_por_localidad
from app.pdf.manual_pdf import generar_pdf_manual
from app.pdf.propuesta_pdf import generar_pdfs_propuesta_por_localidad

_ANCHO_BOTON = 240  # los tres botones de regenerar (el más largo es "Regenerar Manual de usuario")


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


class PantallaArchivosVarios(QWidget):
    def __init__(self, conn: sqlite3.Connection, secciones: list[Seccion] | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._secciones = secciones or []
        self._armar_ui()

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar":
        el QTabWidget contenedor todavía no está mostrado en ese
        momento (mismo motivo que Reservas/Liquidación/Oferta)."""
        super().showEvent(event)
        self.boton_propuesta.setFocus()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        titulo = QLabel("Archivos varios".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        solapas = QTabWidget()
        panel_solapa = QWidget()
        panel_solapa.setObjectName("panelSolapa")
        layout_solapa = QHBoxLayout(panel_solapa)

        panel_izquierda = QWidget()
        columna = QVBoxLayout(panel_izquierda)
        columna.setContentsMargins(0, 0, 0, 0)

        subtitulo = QLabel(
            "Regenerá acá, contra el estado actual del sistema, los documentos que ya se "
            "vuelven a generar solos en el avance de mes."
        )
        subtitulo.setObjectName("subtitulo")
        subtitulo.setWordWrap(True)
        subtitulo.setFixedWidth(_ANCHO_BOTON)
        columna.addWidget(subtitulo)

        self.boton_propuesta = QPushButton("Regenerar Propuesta")
        self.boton_propuesta.setObjectName("botonSecundario")
        self.boton_propuesta.clicked.connect(self._regenerar_propuesta)
        columna.addWidget(self.boton_propuesta)

        self.boton_disponibilidad = QPushButton("Regenerar Disponibilidad")
        self.boton_disponibilidad.setObjectName("botonSecundario")
        self.boton_disponibilidad.clicked.connect(self._regenerar_disponibilidad)
        columna.addWidget(self.boton_disponibilidad)

        self.boton_manual = QPushButton("Regenerar Manual de usuario")
        self.boton_manual.setObjectName("botonSecundario")
        self.boton_manual.clicked.connect(self._regenerar_manual)
        columna.addWidget(self.boton_manual)

        for boton in (self.boton_propuesta, self.boton_disponibilidad, self.boton_manual):
            boton.setFixedWidth(_ANCHO_BOTON)

        columna.addStretch()
        layout_solapa.addWidget(panel_izquierda)

        columna_derecha = QVBoxLayout()
        columna_derecha.addWidget(_titulo_campo("Vista previa"))
        self.etiqueta_preview = QLabel("Regenerá un documento para ver acá su primera página.")
        self.etiqueta_preview.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.etiqueta_preview.setWordWrap(True)
        self.area_preview = QScrollArea()
        self.area_preview.setWidgetResizable(True)
        self.area_preview.setWidget(self.etiqueta_preview)
        columna_derecha.addWidget(self.area_preview, stretch=1)
        layout_solapa.addLayout(columna_derecha, stretch=1)

        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel_solapa)
        solapas.addTab(scroll, "Documentos")
        solapas.tabBar().setDrawBase(False)
        layout.addWidget(solapas, stretch=1)

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
        self._mostrar_preview(rutas[0] if rutas else None)

    def _mostrar_preview(self, ruta: str | None) -> None:
        if ruta is None:
            self.etiqueta_preview.setPixmap(QPixmap())
            self.etiqueta_preview.setText("No se generó ningún archivo para previsualizar.")
            return
        pixmap = _pixmap_primera_pagina_pdf(ruta)
        if pixmap is None:
            self.etiqueta_preview.setPixmap(QPixmap())
            self.etiqueta_preview.setText("No hay vista previa disponible para este archivo.")
        else:
            self.etiqueta_preview.setText("")
            self.etiqueta_preview.setPixmap(pixmap)
