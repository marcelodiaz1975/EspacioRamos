"""Lista de espera (F12, sección 3.21 y DC-08 §2 / DC-10 §2): alta de
pedidos y cruce automático contra la disponibilidad real del período en
curso, reusando app.negocio.lista_espera (mismo motor que usa el Centro
de mensajería para "Disponibilidad de horarios")."""
from __future__ import annotations

import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.negocio.dias import DIAS_SEMANA, periodo_actual
from app.negocio.lista_espera import crear_pedido, listar_pedidos_con_coincidencia, marcar_descartado, marcar_resuelto
from app.negocio.mensajes import nombre_para_mensaje
from app.repositorio.registro import obtener_repositorio

_COLOR_CELDA = {"verde": "#4CAF50", "amarillo": "#F5D547", "naranja": "#E07B39", "rojo": "#C0392B"}
_ETIQUETA_COLOR = {
    "verde": "Un consultorio cubre todo",
    "amarillo": "Combinar, misma unidad",
    "naranja": "Combinar, mismo edificio",
    "rojo": "Combinar, distinto edificio",
}
_DIAS_PEDIDO = DIAS_SEMANA[:6]


class PantallaListaEspera(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._pedidos: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Lista de espera")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        form.addWidget(QLabel("Nuevo pedido"))

        self.combo_profesional = QComboBox()
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_tipo = QComboBox()
        self.combo_tipo.addItem("Alcanza con un día (O)", "O")
        self.combo_tipo.addItem("Todos los días (Y)", "Y")
        form.addWidget(QLabel("Combinación de días"))
        form.addWidget(self.combo_tipo)

        form.addWidget(QLabel("Días"))
        self.lista_dias = QListWidget()
        for dia in _DIAS_PEDIDO:
            item = QListWidgetItem(dia)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.lista_dias.addItem(item)
        self.lista_dias.setMaximumHeight(140)
        form.addWidget(self.lista_dias)

        fila_horario = QHBoxLayout()
        self.spin_desde = QDoubleSpinBox()
        self.spin_desde.setRange(0, 23)
        self.spin_desde.setValue(9)
        self.spin_hasta = QDoubleSpinBox()
        self.spin_hasta.setRange(1, 24)
        self.spin_hasta.setValue(12)
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_desde)
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hasta)
        form.addLayout(fila_horario)

        form.addWidget(QLabel("Características pedidas"))
        self.casilla_ventana = QCheckBox("Con ventana")
        self.casilla_camilla = QCheckBox("Apto camilla")
        self.casilla_balcon = QCheckBox("Con balcón")
        self.casilla_aire = QCheckBox("Con aire acondicionado")
        for casilla in (self.casilla_ventana, self.casilla_camilla, self.casilla_balcon, self.casilla_aire):
            form.addWidget(casilla)
        self.campo_tamano = QLineEdit()
        self.campo_tamano.setPlaceholderText("Tamaño (opcional)")
        form.addWidget(self.campo_tamano)

        self.campo_detalle = QPlainTextEdit()
        self.campo_detalle.setFixedHeight(60)
        form.addWidget(QLabel("Detalle"))
        form.addWidget(self.campo_detalle)

        boton_crear = QPushButton("Crear pedido")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.clicked.connect(self._crear_pedido)
        form.addWidget(boton_crear)
        form.addStretch()
        splitter.addWidget(panel_form)

        panel_tabla = QWidget()
        layout_tabla = QVBoxLayout(panel_tabla)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["Profesional", "Días", "Horario", "Coincidencia", "Detalle"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout_tabla.addWidget(self.tabla, stretch=1)

        fila_acciones = QHBoxLayout()
        boton_resolver = QPushButton("Marcar resuelto")
        boton_resolver.clicked.connect(self._resolver)
        boton_descartar = QPushButton("Descartar")
        boton_descartar.clicked.connect(self._descartar)
        fila_acciones.addWidget(boton_resolver)
        fila_acciones.addWidget(boton_descartar)
        fila_acciones.addStretch()
        layout_tabla.addLayout(fila_acciones)
        splitter.addWidget(panel_tabla)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, stretch=1)
        self._cargar_profesionales()

    def _cargar_profesionales(self) -> None:
        self.combo_profesional.clear()
        for f in self.conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido"):
            nombre = f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", ")
            self.combo_profesional.addItem(nombre, f["IdProfesional"])

    def actualizar(self) -> None:
        periodo = periodo_actual(self.conn)
        anio, mes = (int(p) for p in periodo.split("-"))
        resultado = listar_pedidos_con_coincidencia(self.conn, anio, mes)
        self._pedidos = [p for p, _ in resultado]

        self.tabla.setRowCount(len(resultado))
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        for fila_idx, (pedido, coincidencia) in enumerate(resultado):
            profesional = repo_profesional.obtener(pedido["IdProfesional"])
            nombre = nombre_para_mensaje(profesional) if profesional else "?"
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(nombre))

            dias = json.loads(pedido["Dias"]) if pedido["Dias"] else []
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(", ".join(dias)))
            self.tabla.setItem(
                fila_idx, 2, QTableWidgetItem(f"{pedido['HorarioDesde']:g} a {pedido['HorarioHasta']:g}")
            )

            color = coincidencia.color if coincidencia else None
            item_color = QTableWidgetItem(_ETIQUETA_COLOR.get(color, "Sin cobertura"))
            if color:
                item_color.setBackground(QColor(_COLOR_CELDA[color]))
            self.tabla.setItem(fila_idx, 3, item_color)
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(pedido["Detalle"] or ""))
        self.tabla.resizeColumnsToContents()

    def _dias_seleccionados(self) -> list[str]:
        return [
            self.lista_dias.item(i).text()
            for i in range(self.lista_dias.count())
            if self.lista_dias.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _condiciones(self) -> dict:
        condiciones = {}
        if self.casilla_ventana.isChecked():
            condiciones["ventana"] = True
        if self.casilla_camilla.isChecked():
            condiciones["aptoCamilla"] = True
        if self.casilla_balcon.isChecked():
            condiciones["balcon"] = True
        if self.casilla_aire.isChecked():
            condiciones["aire"] = True
        if self.campo_tamano.text().strip():
            condiciones["tamano"] = self.campo_tamano.text().strip()
        return condiciones

    def _crear_pedido(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Crear pedido", "No hay profesionales cargados.")
            return
        try:
            crear_pedido(
                self.conn, id_profesional=id_profesional, tipo_combinacion=self.combo_tipo.currentData(),
                dias=self._dias_seleccionados(), horario_desde=self.spin_desde.value(),
                horario_hasta=self.spin_hasta.value(), condiciones_consultorio=self._condiciones(),
                detalle=self.campo_detalle.toPlainText().strip() or None,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Crear pedido", str(error))
            return
        self.conn.commit()
        self.actualizar()

    def _fila_seleccionada_pedido(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._pedidos[filas[0].row()]

    def _resolver(self) -> None:
        pedido = self._fila_seleccionada_pedido()
        if pedido is None:
            return
        marcar_resuelto(self.conn, pedido["IdPedido"])
        self.conn.commit()
        self.actualizar()

    def _descartar(self) -> None:
        pedido = self._fila_seleccionada_pedido()
        if pedido is None:
            return
        marcar_descartado(self.conn, pedido["IdPedido"])
        self.conn.commit()
        self.actualizar()
