"""Centro de mensajería (FA7, sección 5): lista de profesionales con su
situación (categoría R, sección 5.3) o de reserva aislada (categoría A,
sección 5.1) para el período elegido, arma el mensaje correspondiente
reusando app.negocio.mensajes y permite copiarlo al portapapeles. También
expone el mensaje grupal (sección 5.4).

Sección 5.1: para categoría A, los 5 controles (todos marcados por
default) que arman el detalle de reserva aislada — Incluir consultorio /
Incluir unidad / Incluir edificio / Combinar misma unidad / Combinar
distintas unidades.

Filtros y orden según sección 6.2: "Todos / Solo regulares / Solo
aisladas / Solo con plan / Con deuda (default) / Liquidación enviada /
Liquidación sin enviar", ordenado por días desde el último pago
(descendente) y, a igualdad, por monto adeudado (descendente) — a quién
hace falta contactar primero."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.liquidaciones import marcar_estado_envio
from app.negocio.mensajes import (
    determinar_situacion,
    dias_desde_ultimo_pago,
    liquidacion_del_periodo,
    mensaje_detalle_reserva_aislada,
    mensaje_grupal,
    mensaje_situacion,
    nombre_para_mensaje,
    plan_activo,
)
from app.repositorio.registro import obtener_repositorio

_COLUMNA_ENVIADA = 3

_ETIQUETA_SITUACION = {
    "1": "1 — Deuda sobre tolerancia",
    "2": "2 — Liquidación enviada",
    "3": "3 — Pendiente de liquidación",
    "4": "4 — Plan de pagos, enviada",
    "5": "5 — Plan de pagos, pendiente",
}

_FILTROS = [
    ("Todos", "todos"),
    ("Solo regulares", "regulares"),
    ("Solo aisladas", "aisladas"),
    ("Solo con plan", "con_plan"),
    ("Con deuda", "con_deuda"),
    ("Liquidación enviada", "liq_enviada"),
    ("Liquidación sin enviar", "liq_sin_enviar"),
]
_FILTRO_DEFAULT = "con_deuda"


class CentroMensajeria(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._profesionales: list[sqlite3.Row] = []
        self._actualizando_tabla = False
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        titulo = QLabel("Centro de mensajería")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        fila_filtros = QHBoxLayout()
        fila_filtros.addWidget(QLabel("Filtro:"))
        self.combo_filtro = QComboBox()
        for etiqueta, clave in _FILTROS:
            self.combo_filtro.addItem(etiqueta, clave)
        self.combo_filtro.setCurrentIndex([clave for _, clave in _FILTROS].index(_FILTRO_DEFAULT))
        self.combo_filtro.currentIndexChanged.connect(self.actualizar)
        fila_filtros.addWidget(self.combo_filtro)

        fila_filtros.addWidget(QLabel("Período:"))
        self.campo_periodo = QLineEdit()
        self.campo_periodo.editingFinished.connect(self.actualizar)
        fila_filtros.addWidget(self.campo_periodo)

        boton_actualizar = QPushButton("Actualizar")
        boton_actualizar.clicked.connect(self.actualizar)
        fila_filtros.addWidget(boton_actualizar)

        boton_grupal = QPushButton("Mensaje grupal")
        boton_grupal.setObjectName("botonPrimario")
        boton_grupal.clicked.connect(self._mostrar_mensaje_grupal)
        fila_filtros.addWidget(boton_grupal)
        fila_filtros.addStretch()
        layout.addLayout(fila_filtros)

        splitter = QSplitter()
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Profesional", "Saldo anterior", "Situación", "Enviada"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.itemSelectionChanged.connect(self._mostrar_mensaje_seleccionado)
        self.tabla.itemChanged.connect(self._al_cambiar_enviada)
        splitter.addWidget(self.tabla)

        panel_derecho = QWidget()
        layout_derecho = QVBoxLayout(panel_derecho)

        fila_incluir = QHBoxLayout()
        self.check_incluir_consultorio = QCheckBox("Incluir consultorio")
        self.check_incluir_consultorio.setChecked(True)
        self.check_incluir_consultorio.toggled.connect(self._mostrar_mensaje_seleccionado)
        fila_incluir.addWidget(self.check_incluir_consultorio)
        self.check_incluir_unidad = QCheckBox("Incluir unidad")
        self.check_incluir_unidad.setChecked(True)
        self.check_incluir_unidad.toggled.connect(self._mostrar_mensaje_seleccionado)
        fila_incluir.addWidget(self.check_incluir_unidad)
        self.check_incluir_edificio = QCheckBox("Incluir edificio")
        self.check_incluir_edificio.setChecked(True)
        self.check_incluir_edificio.toggled.connect(self._mostrar_mensaje_seleccionado)
        fila_incluir.addWidget(self.check_incluir_edificio)
        fila_incluir.addStretch()
        layout_derecho.addLayout(fila_incluir)

        fila_combinar = QHBoxLayout()
        self.check_combinar_misma_unidad = QCheckBox("Combinar misma unidad")
        self.check_combinar_misma_unidad.toggled.connect(self._mostrar_mensaje_seleccionado)
        fila_combinar.addWidget(self.check_combinar_misma_unidad)
        self.check_combinar_distintas_unidades = QCheckBox("Combinar distintas unidades")
        self.check_combinar_distintas_unidades.toggled.connect(self._mostrar_mensaje_seleccionado)
        fila_combinar.addWidget(self.check_combinar_distintas_unidades)
        fila_combinar.addStretch()
        layout_derecho.addLayout(fila_combinar)

        self.texto_mensaje = QPlainTextEdit()
        layout_derecho.addWidget(self.texto_mensaje, stretch=1)
        fila_acciones = QHBoxLayout()
        boton_copiar = QPushButton("Copiar mensaje")
        boton_copiar.clicked.connect(self._copiar_mensaje)
        fila_acciones.addWidget(boton_copiar)
        fila_acciones.addStretch()
        layout_derecho.addLayout(fila_acciones)
        splitter.addWidget(panel_derecho)
        layout.addWidget(splitter, stretch=1)

        self.campo_periodo.setText(periodo_actual(self.conn))

    def actualizar(self) -> None:
        periodo = self._periodo()
        filtro = self.combo_filtro.currentData()
        self._profesionales = self._listar_filtrados(periodo, filtro)
        self._profesionales.sort(key=lambda p: self._clave_orden(p), reverse=True)

        self._actualizando_tabla = True
        try:
            self.tabla.setRowCount(len(self._profesionales))
            for fila_idx, profesional in enumerate(self._profesionales):
                categoria = profesional["CategoriaProfesional"]
                nombre = f"{nombre_para_mensaje(profesional)} ({profesional['Apellido']})"
                self.tabla.setItem(fila_idx, 0, QTableWidgetItem(nombre))
                self.tabla.setItem(fila_idx, 1, QTableWidgetItem(f"$ {profesional['SaldoCuentaAnterior']:,.2f}"))
                if categoria == "R":
                    situacion = determinar_situacion(self.conn, profesional["IdProfesional"], periodo)
                    texto_situacion = _ETIQUETA_SITUACION.get(situacion, "")
                else:
                    texto_situacion = "Detalle de reserva"
                self.tabla.setItem(fila_idx, 2, QTableWidgetItem(texto_situacion))
                self.tabla.setItem(fila_idx, _COLUMNA_ENVIADA, self._item_enviada(profesional, categoria, periodo))
        finally:
            self._actualizando_tabla = False
        self.tabla.resizeColumnsToContents()
        self.texto_mensaje.clear()

    def _listar_filtrados(self, periodo: str, filtro: str) -> list[sqlite3.Row]:
        """Base = profesionales de categoría R o A (las únicas con
        contenido propio en este centro de mensajería: situaciones 5.3 o
        detalle de reservas 5.1), acotada según el filtro elegido."""
        candidatos = [
            p for p in obtener_repositorio(self.conn, "Profesional").listar()
            if p["CategoriaProfesional"] in ("R", "A")
        ]
        if filtro == "regulares":
            return [p for p in candidatos if p["CategoriaProfesional"] == "R"]
        if filtro == "aisladas":
            return [p for p in candidatos if p["CategoriaProfesional"] == "A"]
        if filtro == "con_plan":
            return [p for p in candidatos if plan_activo(self.conn, p["IdProfesional"]) is not None]
        if filtro == "con_deuda":
            return [p for p in candidatos if (p["SaldoCuentaAnterior"] or 0) > 0]
        if filtro == "liq_enviada":
            return [
                p for p in candidatos
                if p["CategoriaProfesional"] == "R" and self._enviada(p["IdProfesional"], periodo)
            ]
        if filtro == "liq_sin_enviar":
            return [
                p for p in candidatos
                if p["CategoriaProfesional"] == "R" and not self._enviada(p["IdProfesional"], periodo)
            ]
        return candidatos  # "todos"

    def _enviada(self, id_profesional: int, periodo: str) -> bool:
        liquidacion = liquidacion_del_periodo(self.conn, id_profesional, periodo)
        return liquidacion is not None and liquidacion["EstadoEnvio"] == "Enviada"

    def _clave_orden(self, profesional: sqlite3.Row) -> tuple[float, float]:
        """Días desde el último pago (mayor a menor) y, a igualdad, monto
        adeudado (mayor a menor) — sección 6.2. Nunca pagó = infinito, va
        primero."""
        dias = dias_desde_ultimo_pago(self.conn, profesional["IdProfesional"], fecha_actual(self.conn))
        return (float("inf") if dias is None else dias, profesional["SaldoCuentaAnterior"] or 0.0)

    def _item_enviada(self, profesional: sqlite3.Row, categoria: str, periodo: str) -> QTableWidgetItem:
        """Check "enviada" del centro de mensajería (sección 6.2): marcable
        y reversible. Solo tiene sentido para R con una liquidación ya
        emitida en este período — sin eso no hay nada a lo que el check
        pueda referirse, así que queda deshabilitado."""
        item = QTableWidgetItem()
        liquidacion = liquidacion_del_periodo(self.conn, profesional["IdProfesional"], periodo) if categoria == "R" else None
        if liquidacion is None:
            item.setFlags(Qt.ItemFlag.ItemIsSelectable)
            item.setToolTip("Todavía no se emitió una liquidación de este período.")
        else:
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.Checked if liquidacion["EstadoEnvio"] == "Enviada" else Qt.CheckState.Unchecked)
        return item

    def _al_cambiar_enviada(self, item: QTableWidgetItem) -> None:
        if self._actualizando_tabla or item.column() != _COLUMNA_ENVIADA:
            return
        profesional = self._profesionales[item.row()]
        marcar_estado_envio(
            self.conn, id_profesional=profesional["IdProfesional"], periodo=self._periodo(),
            enviada=item.checkState() == Qt.CheckState.Checked,
        )
        self.actualizar()

    def _periodo(self) -> str:
        return self.campo_periodo.text().strip() or periodo_actual(self.conn)

    def _mostrar_mensaje_seleccionado(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return
        profesional = self._profesionales[filas[0].row()]
        categoria = profesional["CategoriaProfesional"]
        try:
            if categoria == "R":
                texto = mensaje_situacion(self.conn, profesional["IdProfesional"], self._periodo())
            else:
                texto = mensaje_detalle_reserva_aislada(
                    self.conn, id_profesional=profesional["IdProfesional"], periodo=self._periodo(),
                    incluir_consultorio=self.check_incluir_consultorio.isChecked(),
                    incluir_unidad=self.check_incluir_unidad.isChecked(),
                    incluir_edificio=self.check_incluir_edificio.isChecked(),
                    combinar_misma_unidad=self.check_combinar_misma_unidad.isChecked(),
                    combinar_distintas_unidades=self.check_combinar_distintas_unidades.isChecked(),
                )
        except ValueError as error:
            texto = str(error)
        self.texto_mensaje.setPlainText(texto)

    def _copiar_mensaje(self) -> None:
        QGuiApplication.clipboard().setText(self.texto_mensaje.toPlainText())

    def _mostrar_mensaje_grupal(self) -> None:
        self.texto_mensaje.setPlainText(mensaje_grupal(self.conn, self._periodo()))
        self.tabla.clearSelection()
