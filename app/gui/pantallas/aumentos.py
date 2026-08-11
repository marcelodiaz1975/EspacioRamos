"""Análisis de aumentos (FA2, Etapa 5, DC-10 §1): simula un % general de
aumento sobre los valores de todos los consultorios, permite ajustar el
valor de un consultorio puntual editando la celda directamente en la
vista previa, y confirma reusando app.negocio.aumentos.confirmar_aumento
(que además regenera las liquidaciones ya emitidas del período afectado).

Nota: el esquema de descuentos "debería" editarse solo durante este
proceso (DC-10 §1.1), pero la pantalla de catálogo "Esquema de
descuentos" (CRUD genérico) también permite tocarlo directamente — es
una tensión conocida, a resolver en la revisión de la beta si hace
falta un guardarraíl más estricto."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

_ID_CONSULTORIO = Qt.ItemDataRole.UserRole
_COL_REGULAR_NUEVO = 2
_COL_AISLADA_NUEVO = 5


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

            self._celda_fija(i, 1, f"$ {f.valor_regular_actual:,.2f}")
            self._celda_editable(i, _COL_REGULAR_NUEVO, f"{f.valor_regular_nuevo:.2f}")
            self._celda_fija(i, 4, f"$ {f.valor_aislada_actual:,.2f}")
            self._celda_editable(i, _COL_AISLADA_NUEVO, f"{f.valor_aislada_nuevo:.2f}")
        self._recalcular_diferencias()
        self.tabla.resizeColumnsToContents()

    def _celda_fija(self, fila: int, columna: int, texto: str) -> None:
        item = QTableWidgetItem(texto)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
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
                    actual_reg = float(self.tabla.item(i, 1).text().replace("$", "").replace(",", "").strip())
                    nuevo_reg = float(self.tabla.item(i, _COL_REGULAR_NUEVO).text())
                    actual_ais = float(self.tabla.item(i, 4).text().replace("$", "").replace(",", "").strip())
                    nuevo_ais = float(self.tabla.item(i, _COL_AISLADA_NUEVO).text())
                except (ValueError, AttributeError):
                    continue
                self._celda_fija(i, 3, f"{nuevo_reg - actual_reg:+,.2f}")
                self._celda_fija(i, 6, f"{nuevo_ais - actual_ais:+,.2f}")
        finally:
            self.tabla.blockSignals(False)

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

        periodo = self.campo_periodo.text().strip() or periodo_actual(self.conn)
        confirmacion = QMessageBox.question(
            self, "Confirmar aumento",
            f"¿Confirmás el aumento para el período {periodo}? Esto actualiza los valores de "
            f"{len(valores_override)} consultorio(s) y regenera las liquidaciones ya emitidas de ese período.",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return

        resumen = confirmar_aumento(
            self.conn, porcentaje_general=self.spin_porcentaje.value(), valores_override=valores_override,
            periodo=periodo, observacion=self.campo_observacion.text().strip() or None,
        )
        self.conn.commit()
        QMessageBox.information(
            self, "Aumento confirmado",
            f"Se actualizaron {resumen.consultorios_actualizados} consultorio(s) y se regeneraron "
            f"{len(resumen.liquidaciones_regeneradas)} liquidación(es) del período {resumen.periodo}.",
        )
        self.actualizar()
