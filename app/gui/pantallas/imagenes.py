"""Gestión de imágenes (FA4, sección 3.26): fotos de edificios, unidades y
consultorios (app.negocio.imagenes) que se muestran en Propuesta,
Disponibilidad, Liquidación y Oferta de consultorios."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.negocio.imagenes import (
    agregar_imagen,
    alternar_activo,
    eliminar_imagen,
    imagenes_del_alcance,
    reordenar,
)

_ALCANCES = ["Edificio", "Unidad", "Consultorio"]


class PantallaImagenes(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._imagenes: list[sqlite3.Row] = []
        self._armar_ui()
        self._cargar_entidades()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Imágenes de edificios, unidades y consultorios")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        fila_alcance = QHBoxLayout()
        self.combo_alcance = QComboBox()
        self.combo_alcance.addItems(_ALCANCES)
        self.combo_alcance.currentIndexChanged.connect(self._cargar_entidades)
        fila_alcance.addWidget(QLabel("Alcance:"))
        fila_alcance.addWidget(self.combo_alcance)

        self.combo_entidad = QComboBox()
        self.combo_entidad.currentIndexChanged.connect(self.actualizar)
        fila_alcance.addWidget(self.combo_entidad, stretch=1)
        layout.addLayout(fila_alcance)

        splitter = QSplitter()

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Orden", "Descripción", "Tipo", "Activo"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        splitter.addWidget(self.tabla)
        layout.addWidget(splitter, stretch=1)

        fila_botones = QHBoxLayout()
        boton_agregar = QPushButton("Agregar imagen…")
        boton_agregar.setObjectName("botonPrimario")
        boton_agregar.clicked.connect(self._agregar)
        boton_subir = QPushButton("Subir")
        boton_subir.clicked.connect(lambda: self._reordenar(-1))
        boton_bajar = QPushButton("Bajar")
        boton_bajar.clicked.connect(lambda: self._reordenar(1))
        boton_activo = QPushButton("Activar/Desactivar")
        boton_activo.clicked.connect(self._alternar_activo)
        boton_eliminar = QPushButton("Eliminar")
        boton_eliminar.clicked.connect(self._eliminar)
        for boton in (boton_agregar, boton_subir, boton_bajar, boton_activo, boton_eliminar):
            fila_botones.addWidget(boton)
        fila_botones.addStretch()
        layout.addLayout(fila_botones)

    def _cargar_entidades(self) -> None:
        alcance = self.combo_alcance.currentText()
        self.combo_entidad.blockSignals(True)
        self.combo_entidad.clear()
        if alcance == "Edificio":
            filas = self.conn.execute("SELECT IdEdificio AS id, Nombre AS etiqueta FROM Edificio ORDER BY Nombre")
        elif alcance == "Unidad":
            filas = self.conn.execute(
                "SELECT u.IdUnidad AS id, e.Nombre || ' - ' || u.Departamento AS etiqueta "
                "FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio ORDER BY e.Nombre, u.Departamento"
            )
        else:
            filas = self.conn.execute(
                "SELECT c.IdConsultorio AS id, "
                "e.Nombre || ' - ' || u.Departamento || ' - Consultorio ' || c.NumeroConsultorio AS etiqueta "
                "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
                "ORDER BY e.Nombre, u.Departamento, c.NumeroConsultorio"
            )
        for f in filas:
            self.combo_entidad.addItem(f["etiqueta"], f["id"])
        self.combo_entidad.blockSignals(False)
        self.actualizar()

    def _ids_alcance(self) -> tuple[int | None, int | None, int | None]:
        id_valor = self.combo_entidad.currentData()
        alcance = self.combo_alcance.currentText()
        return (
            id_valor if alcance == "Edificio" else None,
            id_valor if alcance == "Unidad" else None,
            id_valor if alcance == "Consultorio" else None,
        )

    def actualizar(self) -> None:
        if self.combo_entidad.currentData() is None:
            self._imagenes = []
        else:
            self._imagenes = imagenes_del_alcance(self.conn, *self._ids_alcance())
        self.tabla.setRowCount(len(self._imagenes))
        for fila_idx, img in enumerate(self._imagenes):
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(str(img["NumeroOrden"])))
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
        if self.combo_entidad.currentData() is None:
            QMessageBox.warning(self, "Imágenes", "No hay ningún registro cargado para este alcance.")
            return
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegir imagen", "", "Imágenes (*.jpg *.jpeg *.png)")
        if not ruta:
            return
        descripcion, _ = QInputDialog.getText(self, "Agregar imagen", "Descripción (opcional):")
        id_edificio, id_unidad, id_consultorio = self._ids_alcance()
        try:
            agregar_imagen(
                self.conn, ruta_origen=ruta, descripcion=descripcion or None,
                id_edificio=id_edificio, id_unidad=id_unidad, id_consultorio=id_consultorio,
            )
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
