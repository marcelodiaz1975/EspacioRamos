"""Análisis de aumentos (FA2, Etapa 5, DC-10 §1): simula un % general de
aumento sobre los valores de todos los consultorios, permite ajustar el
valor de un consultorio puntual editando la celda directamente en la
vista previa, y confirma reusando app.negocio.aumentos.confirmar_aumento
(que además regenera las liquidaciones ya emitidas del período afectado).

También es el único lugar desde donde se puede tocar el esquema de
descuentos (DC-10 §1.1: "solo modificable al ejecutar análisis de
aumentos"; la pantalla de catálogo lo muestra en solo lectura) — un
checkbox opcional habilita una tabla de tramos (Desde/Hasta/%) que, si
se confirma marcada, reemplaza el esquema vigente vía
app.negocio.aumentos.actualizar_esquema_descuentos (que preserva el
esquema anterior como historial, Activo=0)."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.negocio.aumentos import confirmar_aumento, simular_aumento
from app.negocio.dias import periodo_actual
from app.negocio.formato import formatear_moneda
from app.repositorio.registro import obtener_repositorio

_ID_CONSULTORIO = Qt.ItemDataRole.UserRole
_COL_REGULAR_NUEVO = 2
_COL_AISLADA_NUEVO = 5


def _fmt_diferencia(valor: float) -> str:
    """Signo "+"/"-" explícito (a diferencia de `formatear_moneda`, que
    nunca antepone "+") y sin símbolo "$" — es un delta, no un monto."""
    texto = f"{abs(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{'-' if valor < 0 else '+'}{texto}"


class PantallaAumentos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Análisis de aumentos")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        fila_filtros = QHBoxLayout()
        fila_filtros.addWidget(QLabel("Período"))
        self.campo_periodo = QLineEdit()
        fila_filtros.addWidget(self.campo_periodo)

        fila_filtros.addWidget(QLabel("% general"))
        self.spin_porcentaje = QDoubleSpinBox()
        self.spin_porcentaje.setRange(-100, 1000)
        self.spin_porcentaje.setDecimals(2)
        fila_filtros.addWidget(self.spin_porcentaje)

        boton_simular = QPushButton("Simular")
        boton_simular.clicked.connect(self._simular)
        fila_filtros.addWidget(boton_simular)
        fila_filtros.addStretch()
        layout.addLayout(fila_filtros)

        self.campo_observacion = QLineEdit()
        self.campo_observacion.setPlaceholderText("Observación (opcional)")
        layout.addWidget(self.campo_observacion)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(7)
        self.tabla.setHorizontalHeaderLabels(
            ["Consultorio", "Regular actual", "Regular nuevo", "Dif. regular",
             "Aislada actual", "Aislada nuevo", "Dif. aislada"]
        )
        self.tabla.itemChanged.connect(self._recalcular_diferencias)
        layout.addWidget(self.tabla, stretch=1)

        self.check_actualizar_esquema = QCheckBox("Actualizar esquema de descuentos (reemplaza el vigente)")
        self.check_actualizar_esquema.toggled.connect(self._al_tildar_actualizar_esquema)
        layout.addWidget(self.check_actualizar_esquema)

        self.tabla_esquema = QTableWidget()
        self.tabla_esquema.setColumnCount(3)
        self.tabla_esquema.setHorizontalHeaderLabels(["Horas desde", "Horas hasta", "% Descuento"])
        self.tabla_esquema.setVisible(False)
        layout.addWidget(self.tabla_esquema)

        fila_botones_esquema = QHBoxLayout()
        self.boton_agregar_tramo = QPushButton("Agregar tramo")
        self.boton_agregar_tramo.clicked.connect(self._agregar_tramo)
        self.boton_agregar_tramo.setVisible(False)
        self.boton_quitar_tramo = QPushButton("Quitar tramo seleccionado")
        self.boton_quitar_tramo.clicked.connect(self._quitar_tramo)
        self.boton_quitar_tramo.setVisible(False)
        fila_botones_esquema.addWidget(self.boton_agregar_tramo)
        fila_botones_esquema.addWidget(self.boton_quitar_tramo)
        fila_botones_esquema.addStretch()
        layout.addLayout(fila_botones_esquema)

        boton_confirmar = QPushButton("Confirmar aumento")
        boton_confirmar.setObjectName("botonPrimario")
        boton_confirmar.clicked.connect(self._confirmar)
        layout.addWidget(boton_confirmar)

        self.campo_periodo.setText(periodo_actual(self.conn))

    def actualizar(self) -> None:
        self.campo_periodo.setText(periodo_actual(self.conn))
        self.tabla.setRowCount(0)

    def _etiqueta_consultorio(self, id_consultorio: int) -> str:
        fila = self.conn.execute(
            "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS Edificio FROM Consultorio c "
            "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "WHERE c.IdConsultorio = ?",
            (id_consultorio,),
        ).fetchone()
        if fila is None:
            return f"Consultorio #{id_consultorio}"
        return f"{fila['Edificio']} - {fila['Departamento']} - Consultorio {fila['NumeroConsultorio']}"

    def _simular(self) -> None:
        periodo = self.campo_periodo.text().strip() or periodo_actual(self.conn)
        filas = simular_aumento(self.conn, porcentaje_general=self.spin_porcentaje.value(), periodo=periodo)
        self.tabla.setRowCount(len(filas))
        for i, f in enumerate(filas):
            item_consultorio = QTableWidgetItem(self._etiqueta_consultorio(f.id_consultorio))
            item_consultorio.setFlags(item_consultorio.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_consultorio.setData(_ID_CONSULTORIO, f.id_consultorio)
            self.tabla.setItem(i, 0, item_consultorio)

            self._celda_fija(i, 1, formatear_moneda(f.valor_regular_actual), valor=f.valor_regular_actual)
            self._celda_editable(i, _COL_REGULAR_NUEVO, f"{f.valor_regular_nuevo:.2f}")
            self._celda_fija(i, 4, formatear_moneda(f.valor_aislada_actual), valor=f.valor_aislada_actual)
            self._celda_editable(i, _COL_AISLADA_NUEVO, f"{f.valor_aislada_nuevo:.2f}")
        self._recalcular_diferencias()
        self.tabla.resizeColumnsToContents()

    def _celda_fija(self, fila: int, columna: int, texto: str, valor: float | None = None) -> None:
        """`valor`, si se pasa, guarda el número crudo detrás del texto ya
        formateado (separadores "." de miles y "," de decimales) — así
        `_recalcular_diferencias` no tiene que volver a parsear el texto
        mostrado, cosa que además ya no sería ambigua (el "." dejó de
        significar siempre decimal)."""
        item = QTableWidgetItem(texto)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if valor is not None:
            item.setData(Qt.ItemDataRole.UserRole, valor)
        self.tabla.setItem(fila, columna, item)

    def _celda_editable(self, fila: int, columna: int, texto: str) -> None:
        item = QTableWidgetItem(texto)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.tabla.setItem(fila, columna, item)

    def _recalcular_diferencias(self, *_args) -> None:
        # Este método escribe en la misma tabla que escucha (itemChanged) —
        # bloquear señales mientras escribe evita que sus propias celdas de
        # diferencia disparen una recursión infinita sobre sí mismas.
        self.tabla.blockSignals(True)
        try:
            for i in range(self.tabla.rowCount()):
                try:
                    actual_reg = self.tabla.item(i, 1).data(Qt.ItemDataRole.UserRole)
                    nuevo_reg = float(self.tabla.item(i, _COL_REGULAR_NUEVO).text())
                    actual_ais = self.tabla.item(i, 4).data(Qt.ItemDataRole.UserRole)
                    nuevo_ais = float(self.tabla.item(i, _COL_AISLADA_NUEVO).text())
                except (ValueError, AttributeError):
                    continue
                if actual_reg is None or actual_ais is None:
                    continue
                self._celda_fija(i, 3, _fmt_diferencia(nuevo_reg - actual_reg))
                self._celda_fija(i, 6, _fmt_diferencia(nuevo_ais - actual_ais))
        finally:
            self.tabla.blockSignals(False)

    def _al_tildar_actualizar_esquema(self, tildado: bool) -> None:
        self.tabla_esquema.setVisible(tildado)
        self.boton_agregar_tramo.setVisible(tildado)
        self.boton_quitar_tramo.setVisible(tildado)
        if tildado and self.tabla_esquema.rowCount() == 0:
            for tramo in obtener_repositorio(self.conn, "EsquemaDescuentos").listar(Activo=1):
                self._agregar_fila_tramo(
                    tramo["HorasSemanalesDesde"], tramo["HorasSemanalesHasta"], tramo["PorcentajeDescuento"],
                )

    def _agregar_fila_tramo(self, desde: float = 0, hasta: float = 0, porcentaje: float = 0) -> None:
        fila = self.tabla_esquema.rowCount()
        self.tabla_esquema.insertRow(fila)
        self.tabla_esquema.setItem(fila, 0, QTableWidgetItem(str(desde)))
        self.tabla_esquema.setItem(fila, 1, QTableWidgetItem(str(hasta)))
        self.tabla_esquema.setItem(fila, 2, QTableWidgetItem(str(porcentaje)))

    def _agregar_tramo(self) -> None:
        self._agregar_fila_tramo()

    def _quitar_tramo(self) -> None:
        filas = self.tabla_esquema.selectionModel().selectedRows()
        if not filas:
            return
        self.tabla_esquema.removeRow(filas[0].row())

    def _tramos_esquema(self) -> list[tuple[float, float, float]]:
        tramos = []
        for i in range(self.tabla_esquema.rowCount()):
            desde = float(self.tabla_esquema.item(i, 0).text())
            hasta = float(self.tabla_esquema.item(i, 1).text())
            porcentaje = float(self.tabla_esquema.item(i, 2).text())
            tramos.append((desde, hasta, porcentaje))
        return tramos

    def _confirmar(self) -> None:
        if self.tabla.rowCount() == 0:
            QMessageBox.warning(self, "Confirmar aumento", "Primero hay que simular el aumento.")
            return

        valores_override: dict[int, dict] = {}
        for i in range(self.tabla.rowCount()):
            id_consultorio = self.tabla.item(i, 0).data(_ID_CONSULTORIO)
            try:
                valores_override[id_consultorio] = {
                    "regular": float(self.tabla.item(i, _COL_REGULAR_NUEVO).text()),
                    "aislada": float(self.tabla.item(i, _COL_AISLADA_NUEVO).text()),
                }
            except ValueError:
                QMessageBox.warning(self, "Confirmar aumento", f"Valor inválido en la fila {i + 1}.")
                return

        nuevo_esquema_descuentos = None
        if self.check_actualizar_esquema.isChecked():
            try:
                nuevo_esquema_descuentos = self._tramos_esquema()
            except ValueError:
                QMessageBox.warning(self, "Confirmar aumento", "Hay un valor inválido en el esquema de descuentos.")
                return

        periodo = self.campo_periodo.text().strip() or periodo_actual(self.conn)
        mensaje_esquema = " y se reemplaza el esquema de descuentos" if nuevo_esquema_descuentos is not None else ""
        confirmacion = QMessageBox.question(
            self, "Confirmar aumento",
            f"¿Confirmás el aumento para el período {periodo}? Esto actualiza los valores de "
            f"{len(valores_override)} consultorio(s){mensaje_esquema} y regenera las liquidaciones ya "
            f"emitidas de ese período.",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return

        resumen = confirmar_aumento(
            self.conn, porcentaje_general=self.spin_porcentaje.value(), valores_override=valores_override,
            nuevo_esquema_descuentos=nuevo_esquema_descuentos,
            periodo=periodo, observacion=self.campo_observacion.text().strip() or None,
        )
        self.conn.commit()
        QMessageBox.information(
            self, "Aumento confirmado",
            f"Se actualizaron {resumen.consultorios_actualizados} consultorio(s) y se regeneraron "
            f"{len(resumen.liquidaciones_regeneradas)} liquidación(es) del período {resumen.periodo}.",
        )
        self.actualizar()
