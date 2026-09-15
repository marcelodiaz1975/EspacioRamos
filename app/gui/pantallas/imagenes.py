"""Gestión de imágenes (FA4, sección 3.26): fotos de edificios, unidades y
consultorios (app.negocio.imagenes) que se muestran en Propuesta,
Disponibilidad, Liquidación y Oferta de consultorios.

Mismo formato que los catálogos (solapa "Listado", filtros a la izquierda,
tabla escroleable a la derecha, botones debajo de los filtros) aunque no
usa `PantallaCRUD` porque no es un catálogo de registros con un cuadro de
diálogo: es un administrador de archivos por alcance. El combo "Alcance"
(Espacio/Localidad/Edificio/Unidad/Consultorio — ver
`app.negocio.imagenes.ALCANCES`) define hasta qué nivel de la cadena
Localidad → Edificio → Unidad → Consultorio hace falta elegir un valor
concreto: los combos de nivel superior al elegido quedan deshabilitados
(`_al_cambiar_alcance`) — el que efectivamente determina qué imágenes se
listan/agregan es el del nivel exacto del alcance elegido; los de
niveles inferiores solo acotan en cascada sus opciones (mismo criterio
de cascada que Aumentos y descuentos). No lleva campos libres: no es un
registro de catálogo, es una carpeta de archivos."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.items_tabla import item_numero
from app.negocio.imagenes import (
    agregar_imagen,
    alternar_activo,
    eliminar_imagen,
    imagenes_del_alcance,
    reordenar,
)

_ANCHO_CAMPO = 240
_NIVEL_ALCANCE = {"Espacio": 0, "Localidad": 1, "Edificio": 2, "Unidad": 3, "Consultorio": 4}
_ALCANCES = list(_NIVEL_ALCANCE)


def _titulo_campo(texto: str) -> QLabel:
    """Jerarquía 3 (subtituloCampo): mismo criterio que el resto de las
    pantallas para los títulos que van arriba de un selector."""
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


class PantallaImagenes(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._imagenes: list[sqlite3.Row] = []
        self._armar_ui()
        self._cargar_combo_localidad()
        self._al_cambiar_alcance()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Imágenes de edificios, unidades y consultorios")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        solapas = QTabWidget()
        panel_solapa = QWidget()
        panel_solapa.setObjectName("panelSolapa")
        layout_solapa = QHBoxLayout(panel_solapa)

        panel_izquierda = QWidget()
        form = QVBoxLayout(panel_izquierda)

        form.addWidget(_titulo_campo("Alcance"))
        self.combo_alcance = QComboBox()
        self.combo_alcance.addItems(_ALCANCES)
        self.combo_alcance.setFixedWidth(_ANCHO_CAMPO)
        self.combo_alcance.currentIndexChanged.connect(self._al_cambiar_alcance)
        form.addWidget(self.combo_alcance)

        form.addWidget(_titulo_campo("Localidad"))
        self.combo_localidad = QComboBox()
        self.combo_localidad.setFixedWidth(_ANCHO_CAMPO)
        self.combo_localidad.currentIndexChanged.connect(self._cargar_combo_edificio)
        form.addWidget(self.combo_localidad)

        form.addWidget(_titulo_campo("Edificio"))
        self.combo_edificio = QComboBox()
        self.combo_edificio.setFixedWidth(_ANCHO_CAMPO)
        self.combo_edificio.currentIndexChanged.connect(self._cargar_combo_unidad)
        form.addWidget(self.combo_edificio)

        form.addWidget(_titulo_campo("Unidad"))
        self.combo_unidad = QComboBox()
        self.combo_unidad.setFixedWidth(_ANCHO_CAMPO)
        self.combo_unidad.currentIndexChanged.connect(self._cargar_combo_consultorio)
        form.addWidget(self.combo_unidad)

        form.addWidget(_titulo_campo("Consultorio"))
        self.combo_consultorio = QComboBox()
        self.combo_consultorio.setFixedWidth(_ANCHO_CAMPO)
        self.combo_consultorio.currentIndexChanged.connect(self.actualizar)
        form.addWidget(self.combo_consultorio)

        form.addWidget(_linea_divisoria())

        self.boton_agregar = QPushButton("Agregar imagen")
        self.boton_agregar.setObjectName("botonPrimario")
        self.boton_agregar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_agregar.clicked.connect(self._agregar)
        form.addWidget(self.boton_agregar)

        self.boton_subir = QPushButton("Subir")
        self.boton_subir.setObjectName("botonSecundario")
        self.boton_subir.setFixedWidth(_ANCHO_CAMPO)
        self.boton_subir.clicked.connect(lambda: self._reordenar(-1))
        form.addWidget(self.boton_subir)

        self.boton_bajar = QPushButton("Bajar")
        self.boton_bajar.setObjectName("botonSecundario")
        self.boton_bajar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_bajar.clicked.connect(lambda: self._reordenar(1))
        form.addWidget(self.boton_bajar)

        self.boton_activo = QPushButton("Activar/Desactivar")
        self.boton_activo.setObjectName("botonSecundario")
        self.boton_activo.setFixedWidth(_ANCHO_CAMPO)
        self.boton_activo.clicked.connect(self._alternar_activo)
        form.addWidget(self.boton_activo)

        self.boton_eliminar = QPushButton("Eliminar")
        self.boton_eliminar.setObjectName("botonSecundario")
        self.boton_eliminar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_eliminar.clicked.connect(self._eliminar)
        form.addWidget(self.boton_eliminar)

        form.addStretch()
        layout_solapa.addWidget(panel_izquierda)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Orden", "Descripción", "Tipo", "Activo"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout_solapa.addWidget(self.tabla, stretch=1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel_solapa)
        solapas.addTab(scroll, "Listado")
        layout.addWidget(solapas, stretch=1)

    def _al_cambiar_alcance(self, *_args) -> None:
        nivel = _NIVEL_ALCANCE[self.combo_alcance.currentText()]
        self.combo_localidad.setEnabled(nivel >= 1)
        self.combo_edificio.setEnabled(nivel >= 2)
        self.combo_unidad.setEnabled(nivel >= 3)
        self.combo_consultorio.setEnabled(nivel >= 4)
        self.actualizar()

    def _cargar_combo_localidad(self) -> None:
        self.combo_localidad.blockSignals(True)
        self.combo_localidad.clear()
        filas = self.conn.execute(
            "SELECT DISTINCT DomicilioLocalidad FROM Edificio "
            "WHERE DomicilioLocalidad IS NOT NULL AND TRIM(DomicilioLocalidad) != '' "
            "ORDER BY DomicilioLocalidad"
        ).fetchall()
        for f in filas:
            self.combo_localidad.addItem(f["DomicilioLocalidad"], f["DomicilioLocalidad"])
        self.combo_localidad.blockSignals(False)
        self._cargar_combo_edificio()

    def _cargar_combo_edificio(self) -> None:
        self.combo_edificio.blockSignals(True)
        self.combo_edificio.clear()
        localidad = self.combo_localidad.currentData()
        sql = "SELECT IdEdificio, Nombre FROM Edificio"
        parametros: list = []
        if localidad is not None:
            sql += " WHERE DomicilioLocalidad = ?"
            parametros.append(localidad)
        sql += " ORDER BY Nombre"
        for f in self.conn.execute(sql, parametros).fetchall():
            self.combo_edificio.addItem(f["Nombre"], f["IdEdificio"])
        self.combo_edificio.blockSignals(False)
        self._cargar_combo_unidad()

    def _cargar_combo_unidad(self) -> None:
        self.combo_unidad.blockSignals(True)
        self.combo_unidad.clear()
        id_edificio = self.combo_edificio.currentData()
        sql = "SELECT IdUnidad, Departamento FROM Unidad"
        parametros: list = []
        if id_edificio is not None:
            sql += " WHERE IdEdificio = ?"
            parametros.append(id_edificio)
        sql += " ORDER BY Departamento"
        for f in self.conn.execute(sql, parametros).fetchall():
            self.combo_unidad.addItem(f["Departamento"], f["IdUnidad"])
        self.combo_unidad.blockSignals(False)
        self._cargar_combo_consultorio()

    def _cargar_combo_consultorio(self) -> None:
        self.combo_consultorio.blockSignals(True)
        self.combo_consultorio.clear()
        id_unidad = self.combo_unidad.currentData()
        sql = "SELECT IdConsultorio, NumeroConsultorio FROM Consultorio"
        parametros: list = []
        if id_unidad is not None:
            sql += " WHERE IdUnidad = ?"
            parametros.append(id_unidad)
        sql += " ORDER BY NumeroConsultorio"
        for f in self.conn.execute(sql, parametros).fetchall():
            self.combo_consultorio.addItem(str(f["NumeroConsultorio"]), f["IdConsultorio"])
        self.combo_consultorio.blockSignals(False)
        self.actualizar()

    def _parametros_alcance(self) -> dict:
        """El valor efectivo de alcance para consultar/guardar es el del
        combo en el nivel exacto elegido — los combos de niveles
        inferiores solo sirven para acotar en cascada las opciones de
        ese combo, no se pasan además."""
        alcance = self.combo_alcance.currentText()
        if alcance == "Espacio":
            return {}
        if alcance == "Localidad":
            return {"localidad": self.combo_localidad.currentData()}
        if alcance == "Edificio":
            return {"id_edificio": self.combo_edificio.currentData()}
        if alcance == "Unidad":
            return {"id_unidad": self.combo_unidad.currentData()}
        return {"id_consultorio": self.combo_consultorio.currentData()}

    def actualizar(self, *_args) -> None:
        parametros = self._parametros_alcance()
        if any(valor is None for valor in parametros.values()):
            self._imagenes = []
        else:
            self._imagenes = imagenes_del_alcance(self.conn, **parametros)
        self.tabla.setRowCount(len(self._imagenes))
        for fila_idx, img in enumerate(self._imagenes):
            self.tabla.setItem(fila_idx, 0, item_numero(str(img["NumeroOrden"])))
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(img["Descripcion"] or ""))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(img["Tipo"] or ""))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem("Sí" if img["Activo"] else "No"))
        self.tabla.resizeColumnsToContents()

    def _imagen_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            QMessageBox.information(self, "Imágenes", "Seleccioná una imagen de la lista.")
            return None
        return self._imagenes[filas[0].row()]

    def _agregar(self) -> None:
        parametros = self._parametros_alcance()
        if any(valor is None for valor in parametros.values()):
            QMessageBox.warning(self, "Imágenes", "No hay ningún registro cargado para este alcance.")
            return
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegir imagen", "", "Imágenes (*.jpg *.jpeg *.png)")
        if not ruta:
            return
        descripcion, _ = QInputDialog.getText(self, "Agregar imagen", "Descripción (opcional):")
        try:
            agregar_imagen(self.conn, ruta_origen=ruta, descripcion=descripcion or None, **parametros)
        except ValueError as error:
            QMessageBox.warning(self, "Imágenes", str(error))
            return
        self.conn.commit()
        self.actualizar()

    def _reordenar(self, delta: int) -> None:
        img = self._imagen_seleccionada()
        if img is None:
            return
        reordenar(self.conn, img["IdImagen"], delta)
        self.conn.commit()
        self.actualizar()

    def _alternar_activo(self) -> None:
        img = self._imagen_seleccionada()
        if img is None:
            return
        alternar_activo(self.conn, img["IdImagen"])
        self.conn.commit()
        self.actualizar()

    def _eliminar(self) -> None:
        img = self._imagen_seleccionada()
        if img is None:
            return
        confirmacion = QMessageBox.question(self, "Eliminar imagen", "¿Confirmás eliminar la imagen seleccionada?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        eliminar_imagen(self.conn, img["IdImagen"])
        self.conn.commit()
        self.actualizar()
