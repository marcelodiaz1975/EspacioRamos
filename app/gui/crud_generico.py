"""Pantalla CRUD genérica: cubre las pantallas de catálogo simples (Edificios,
Unidades, Consultorios, Responsables, Tipos de licencia, Listas editables,
Condiciones y normas, Mensajes predefinidos) sin escribir una clase por tabla.
Se parametriza con una lista de Campo (columna, etiqueta, tipo de control) y
usa el Repositorio genérico (app/repositorio/base.py) para leer y escribir."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.repositorio.registro import obtener_repositorio

_ID_REGISTRO = Qt.ItemDataRole.UserRole


@dataclass
class Campo:
    nombre: str
    etiqueta: str
    tipo: str = "texto"  # "texto" | "texto_largo" | "numero" | "booleano" | "combo"
    opciones: Callable[[sqlite3.Connection], list[tuple]] | None = None
    requerido: bool = False
    combo_editable: bool = False
    """Solo para tipo="combo": si el combo acepta texto libre además de las
    opciones sugeridas — para catálogos abiertos (p. ej. CondicionFiscal)
    a diferencia de los realmente cerrados (p. ej. TipoFechaEspecial, que
    feriados.py compara por string exacto: un valor fuera de catálogo ahí
    rompe en silencio el descuento del 100%)."""


class PantallaCRUD(QWidget):
    def __init__(
        self, conn: sqlite3.Connection, tabla: str, titulo: str, campos: list[Campo], parent=None,
        al_actualizar: Callable[[sqlite3.Row, dict], None] | None = None,
    ):
        super().__init__(parent)
        self.conn = conn
        self.tabla = tabla
        self.campos = campos
        self.repositorio = obtener_repositorio(conn, tabla)
        self.al_actualizar = al_actualizar
        self._armar_ui(titulo)
        self.actualizar()

    def _armar_ui(self, titulo: str) -> None:
        layout = QVBoxLayout(self)

        etiqueta_titulo = QLabel(titulo)
        etiqueta_titulo.setObjectName("tituloPantalla")
        layout.addWidget(etiqueta_titulo)

        fila_botones = QHBoxLayout()
        boton_nuevo = QPushButton("Nuevo")
        boton_nuevo.setObjectName("botonPrimario")
        boton_nuevo.clicked.connect(self._nuevo)
        boton_editar = QPushButton("Editar")
        boton_editar.clicked.connect(self._editar)
        boton_eliminar = QPushButton("Eliminar")
        boton_eliminar.clicked.connect(self._eliminar)
        fila_botones.addWidget(boton_nuevo)
        fila_botones.addWidget(boton_editar)
        fila_botones.addWidget(boton_eliminar)
        fila_botones.addStretch()
        layout.addLayout(fila_botones)

        self.tabla_widget = QTableWidget()
        self.tabla_widget.setColumnCount(len(self.campos))
        self.tabla_widget.setHorizontalHeaderLabels([c.etiqueta for c in self.campos])
        self.tabla_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_widget.doubleClicked.connect(self._editar)
        layout.addWidget(self.tabla_widget, stretch=1)

    def actualizar(self) -> None:
        registros = self.repositorio.listar()
        self.tabla_widget.setRowCount(len(registros))
        for fila_idx, registro in enumerate(registros):
            for col_idx, campo in enumerate(self.campos):
                item = QTableWidgetItem(self._texto_celda(registro, campo))
                if col_idx == 0:
                    item.setData(_ID_REGISTRO, registro[self.repositorio.clave_primaria])
                self.tabla_widget.setItem(fila_idx, col_idx, item)
        self.tabla_widget.resizeColumnsToContents()

    def _texto_celda(self, registro: sqlite3.Row, campo: Campo) -> str:
        valor = registro[campo.nombre]
        if campo.tipo == "booleano":
            return "Sí" if valor else "No"
        if campo.tipo == "combo" and campo.opciones:
            opciones = dict(campo.opciones(self.conn))
            return opciones.get(valor, "" if valor is None else str(valor))
        return "" if valor is None else str(valor)

    def fila_seleccionada_id(self):
        """ID de la fila seleccionada, o None — pantallas compuestas (p. ej.
        Llaves) lo usan para saber sobre qué registro maestro operar."""
        filas = self.tabla_widget.selectionModel().selectedRows()
        if not filas:
            return None
        return self.tabla_widget.item(filas[0].row(), 0).data(_ID_REGISTRO)

    def _nuevo(self) -> None:
        dialogo = _DialogoRegistro(self.conn, self.campos, "Nuevo registro")
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.repositorio.crear(**dialogo.valores())
            self.actualizar()

    def _editar(self) -> None:
        id_valor = self.fila_seleccionada_id()
        if id_valor is None:
            QMessageBox.information(self, "Editar", "Seleccioná un registro para editar.")
            return
        registro = self.repositorio.obtener(id_valor)
        dialogo = _DialogoRegistro(self.conn, self.campos, "Editar registro", registro=registro)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            valores = dialogo.valores()
            self.repositorio.actualizar(id_valor, **valores)
            if self.al_actualizar:
                self.al_actualizar(registro, valores)
            self.actualizar()

    def _eliminar(self) -> None:
        id_valor = self.fila_seleccionada_id()
        if id_valor is None:
            QMessageBox.information(self, "Eliminar", "Seleccioná un registro para eliminar.")
            return
        confirmacion = QMessageBox.question(self, "Eliminar", "¿Confirmás eliminar el registro seleccionado?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        try:
            self.repositorio.eliminar(id_valor)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Eliminar", "No se puede eliminar: hay otros registros que dependen de este.")
            return
        self.actualizar()


class _DialogoRegistro(QDialog):
    def __init__(self, conn: sqlite3.Connection, campos: list[Campo], titulo: str, registro=None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.campos = campos
        self.setWindowTitle(titulo)
        self._entradas: dict[str, QWidget] = {}

        layout_general = QVBoxLayout(self)

        formulario = QWidget()
        layout_formulario = QFormLayout(formulario)
        for campo in campos:
            entrada = self._crear_entrada(campo, registro)
            self._entradas[campo.nombre] = entrada
            layout_formulario.addRow(campo.etiqueta, entrada)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(formulario)
        layout_general.addWidget(scroll)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout_general.addWidget(botones)

        self.resize(480, min(60 + 40 * len(campos), 640))

    def _crear_entrada(self, campo: Campo, registro: sqlite3.Row | None) -> QWidget:
        valor = registro[campo.nombre] if registro is not None else None
        if campo.tipo == "booleano":
            entrada = QCheckBox()
            entrada.setChecked(bool(valor))
            return entrada
        if campo.tipo == "combo":
            entrada = QComboBox()
            entrada.setEditable(campo.combo_editable)
            for valor_opcion, etiqueta_opcion in campo.opciones(self.conn):
                entrada.addItem(etiqueta_opcion, valor_opcion)
            if valor is not None:
                indice = entrada.findData(valor)
                if indice >= 0:
                    entrada.setCurrentIndex(indice)
                elif campo.combo_editable:
                    entrada.setEditText(str(valor))
            return entrada
        if campo.tipo == "texto_largo":
            entrada = QPlainTextEdit()
            entrada.setPlainText("" if valor is None else str(valor))
            entrada.setFixedHeight(80)
            return entrada
        entrada = QLineEdit()
        if valor is not None:
            entrada.setText(str(valor))
        return entrada

    def _validar_y_aceptar(self) -> None:
        for campo in self.campos:
            if not campo.requerido:
                continue
            entrada = self._entradas[campo.nombre]
            vacio = (
                (campo.tipo == "texto" and not entrada.text().strip())
                or (campo.tipo == "texto_largo" and not entrada.toPlainText().strip())
            )
            if vacio:
                QMessageBox.warning(self, "Datos incompletos", f"El campo «{campo.etiqueta}» es obligatorio.")
                return
        self.accept()

    def valores(self) -> dict:
        resultado = {}
        for campo in self.campos:
            entrada = self._entradas[campo.nombre]
            if campo.tipo == "booleano":
                resultado[campo.nombre] = 1 if entrada.isChecked() else 0
            elif campo.tipo == "combo":
                if campo.combo_editable:
                    texto = entrada.currentText().strip()
                    resultado[campo.nombre] = texto or None
                else:
                    resultado[campo.nombre] = entrada.currentData()
            elif campo.tipo == "texto_largo":
                texto = entrada.toPlainText().strip()
                resultado[campo.nombre] = texto or None
            elif campo.tipo == "numero":
                texto = entrada.text().strip()
                resultado[campo.nombre] = float(texto) if texto else None
            else:
                texto = entrada.text().strip()
                resultado[campo.nombre] = texto or None
        return resultado
