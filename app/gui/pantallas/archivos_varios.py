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

Formato solapa (revisión uno por uno): columna izquierda de ancho fijo
con cuatro botones. Los primeros tres ("Propuesta", "Disponibilidad",
"Manual del usuario", `botonSecundario` — ninguno es más "definitivo"
que los otros) NO regeneran nada — solo eligen qué documento mirar y
muestran en el cuadro de la derecha la vista previa del archivo que ya
existe en su carpeta (el primero, si hay más de uno —
Propuesta/Disponibilidad arman uno por localidad). El cuarto,
"Regenerar documento" (`botonPrimario`: es la acción más importante de
esta pantalla, la única que efectivamente escribe algo), vuelve a
generar el archivo del tipo elegido con los primeros tres y refresca la
vista previa con el resultado. Separar "elegir/ver" de "regenerar"
evita que mirar qué hay cargado dispare, de paso, una regeneración no
pedida."""
from __future__ import annotations

import sqlite3
from pathlib import Path

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
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.negocio.archivos_generados import (
    SUBCARPETA_DISPONIBILIDAD,
    SUBCARPETA_MANUAL,
    SUBCARPETA_PROPUESTA,
    carpeta_archivos_varios,
)
from app.pdf.disponibilidad_pdf import generar_pdfs_disponibilidad_por_localidad
from app.pdf.manual_pdf import generar_pdf_manual
from app.pdf.propuesta_pdf import generar_pdfs_propuesta_por_localidad

_ANCHO_BOTON = 200  # Propuesta / Disponibilidad / Manual del usuario / Regenerar documento
_ESCALA_PREVIEW = 1.3  # más grande que el 0.6 de Gestor de archivos: acá el cuadro es más ancho

# (etiqueta para mensajes, subcarpeta) por tipo de documento — "manual" arma
# su generador aparte porque necesita self._secciones.
_TIPOS_DOCUMENTO = {
    "propuesta": ("Propuesta", SUBCARPETA_PROPUESTA),
    "disponibilidad": ("Disponibilidad", SUBCARPETA_DISPONIBILIDAD),
    "manual": ("Manual del usuario", SUBCARPETA_MANUAL),
}

_SIN_SELECCION = "Elegí un documento (Propuesta, Disponibilidad o Manual del usuario) para ver su vista previa."


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _primer_archivo_existente(directorio: Path) -> str | None:
    """El primero (orden alfabético, estable) de los archivos ya
    generados en la subcarpeta del documento — sin generar nada nuevo.
    Propuesta/Disponibilidad pueden tener varios (uno por localidad);
    acá alcanza con mostrar cualquiera a modo de muestra."""
    if not directorio.is_dir():
        return None
    archivos = sorted(p for p in directorio.iterdir() if p.is_file())
    return str(archivos[0]) if archivos else None


class PantallaArchivosVarios(QWidget):
    def __init__(self, conn: sqlite3.Connection, secciones: list[Seccion] | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._secciones = secciones or []
        self._tipo_seleccionado: str | None = None
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
            "Elegí un documento para ver su vista previa, y \"Regenerar documento\" para "
            "actualizarlo contra el estado actual del sistema."
        )
        subtitulo.setObjectName("subtitulo")
        subtitulo.setWordWrap(True)
        subtitulo.setFixedWidth(_ANCHO_BOTON)
        columna.addWidget(subtitulo)

        self.boton_propuesta = QPushButton("Propuesta")
        self.boton_propuesta.setObjectName("botonSecundario")
        self.boton_propuesta.clicked.connect(lambda: self._seleccionar("propuesta"))
        columna.addWidget(self.boton_propuesta)

        self.boton_disponibilidad = QPushButton("Disponibilidad")
        self.boton_disponibilidad.setObjectName("botonSecundario")
        self.boton_disponibilidad.clicked.connect(lambda: self._seleccionar("disponibilidad"))
        columna.addWidget(self.boton_disponibilidad)

        self.boton_manual = QPushButton("Manual del usuario")
        self.boton_manual.setObjectName("botonSecundario")
        self.boton_manual.clicked.connect(lambda: self._seleccionar("manual"))
        columna.addWidget(self.boton_manual)

        self.boton_regenerar = QPushButton("Regenerar documento")
        self.boton_regenerar.setObjectName("botonPrimario")
        self.boton_regenerar.clicked.connect(self._regenerar_seleccionado)
        columna.addWidget(self.boton_regenerar)

        for boton in (self.boton_propuesta, self.boton_disponibilidad, self.boton_manual, self.boton_regenerar):
            boton.setFixedWidth(_ANCHO_BOTON)

        columna.addStretch()
        layout_solapa.addWidget(panel_izquierda)

        self._foco = instalar_enter_avanza_foco(
            [self.boton_propuesta, self.boton_disponibilidad, self.boton_manual, self.boton_regenerar],
            parent=self,
        )

        columna_derecha = QVBoxLayout()
        columna_derecha.addWidget(_titulo_campo("Vista previa"))
        self.etiqueta_preview = QLabel(_SIN_SELECCION)
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

    # --------------------------------------------------------- elegir/ver

    def _seleccionar(self, clave: str) -> None:
        self._tipo_seleccionado = clave
        _etiqueta, subcarpeta = _TIPOS_DOCUMENTO[clave]
        directorio = carpeta_archivos_varios(self.conn, subcarpeta)
        self._mostrar_preview(
            _primer_archivo_existente(directorio),
            sin_archivo="Todavía no se generó ningún archivo de este tipo — probá \"Regenerar documento\".",
        )

    # ------------------------------------------------------------ generar

    def _generador(self, clave: str):
        if clave == "propuesta":
            return generar_pdfs_propuesta_por_localidad
        if clave == "disponibilidad":
            return generar_pdfs_disponibilidad_por_localidad
        tuplas = [(s.categoria, s.nombre, s.ayuda) for s in self._secciones]
        return lambda conn, directorio: [generar_pdf_manual(conn, directorio, tuplas)]

    def _regenerar_seleccionado(self) -> None:
        if self._tipo_seleccionado is None:
            QMessageBox.information(self, "Regenerar documento", "Elegí primero qué documento regenerar.")
            return
        clave = self._tipo_seleccionado
        etiqueta, subcarpeta = _TIPOS_DOCUMENTO[clave]
        if clave == "manual" and not self._secciones:
            QMessageBox.warning(
                self, "Regenerar documento", "No hay ayuda contextual disponible para armar el manual.",
            )
            return
        try:
            directorio = str(carpeta_archivos_varios(self.conn, subcarpeta))
            rutas = self._generador(clave)(self.conn, directorio)
        except ValueError as error:
            QMessageBox.warning(self, "Regenerar documento", str(error))
            return
        QMessageBox.information(
            self, "Regenerar documento", f"Se generó {len(rutas)} archivo(s) de {etiqueta} en:\n{directorio}",
        )
        self._mostrar_preview(rutas[0] if rutas else None, sin_archivo="No se generó ningún archivo para previsualizar.")

    # ------------------------------------------------------------ preview

    def _mostrar_preview(self, ruta: str | None, *, sin_archivo: str) -> None:
        if ruta is None:
            self._limpiar_preview(sin_archivo)
            return
        pixmap = _pixmap_primera_pagina_pdf(ruta, escala=_ESCALA_PREVIEW)
        if pixmap is None:
            self._limpiar_preview("No hay vista previa disponible para este archivo.")
            return
        # Se resta más que el margen mínimo: si la imagen ocupa TODO el
        # ancho del viewport y después aparece la barra vertical (porque
        # es más alta que el visible), esa barra le come ancho al
        # viewport y terminaría apareciendo también una horizontal —
        # dejando este margen de entrada no hace falta.
        ancho_disponible = max(self.area_preview.viewport().width() - 24, 200)
        if pixmap.width() > ancho_disponible:
            pixmap = pixmap.scaledToWidth(ancho_disponible, Qt.TransformationMode.SmoothTransformation)
        self.etiqueta_preview.setText("")
        self.etiqueta_preview.setPixmap(pixmap)
        # Sin esto, el QScrollArea (widgetResizable=True) achica la etiqueta
        # al alto del viewport y la imagen queda recortada en vez de poder
        # bajar con la barra vertical — forzando el mínimo al tamaño real
        # de la imagen es lo que habilita el scroll vertical pedido.
        self.etiqueta_preview.setMinimumSize(pixmap.size())

    def _limpiar_preview(self, mensaje: str) -> None:
        self.etiqueta_preview.setMinimumSize(0, 0)
        self.etiqueta_preview.setPixmap(QPixmap())
        self.etiqueta_preview.setText(mensaje)
