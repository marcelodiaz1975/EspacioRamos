"""Reinicio de prueba (pedido explícito de la clienta): pantalla nueva,
propia de "Parámetros del sistema" — no una solapa de "Base de datos del
espacio" (estructura física, sin relación con dinero), mismo criterio que
"Usuarios y permisos" (herramienta administrativa de uso puntual, no un
catálogo de registros). Ver `app.negocio.reinicio_prueba` para el
contrato completo de qué toca y qué no.

Dos solapas:
- "Saldos iniciales": tabla de profesionales R/A/X (ver `app.negocio.
  reinicio_prueba.CATEGORIAS_CON_SALDO`) con su `SaldoCuentaAnterior`
  editable por selección + diálogo (regla general "EN GENERAL" de todo
  el sistema), más "Poner todos en $0" para el caso común de arrancar
  de cero. "Buscar profesional" arriba de los botones filtra la tabla,
  mismo criterio que "Filtros que solo afectan la visualización".
- "Depurar historial de prueba": elegís un período de corte
  (`SelectorPeriodo`, default el mes anterior al actual — el que
  recién se cerró de prueba), se muestra cuánto hay para borrar de cada
  concepto (`contar_registros_a_depurar`) y un botón que ejecuta el
  borrado real (`depurar_historial_hasta_periodo`) — pide la contraseña
  maestra antes de confirmar (pedido explícito de la clienta: "que la
  limpieza pida la contraseña maestra", mismo mecanismo ya usado para
  "Continuar sin sincronizar" en `DialogoBaseDesactualizada`), porque es
  irreversible."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.crud_generico import _normalizar_busqueda
from app.gui.pantallas.reservas import _texto_profesional
from app.gui.widgets.foco import (
    excluir_tabla_del_tab,
    instalar_enter_avanza_foco,
    instalar_seleccionar_todo_al_enfocar,
)
from app.gui.widgets.orden_tabla import clave_orden_profesional
from app.gui.widgets.resumen_saldo import item_monto
from app.gui.widgets.selector_periodo import SelectorPeriodo
from app.negocio.dias import periodo_actual, sumar_meses
from app.negocio.reinicio_prueba import (
    ajustar_saldo_anterior,
    contar_registros_a_depurar,
    depurar_historial_hasta_periodo,
    profesionales_con_saldo,
)
from app.negocio.seguridad import hay_contrasena_maestra, verificar_contrasena_maestra

_ID_REGISTRO = Qt.ItemDataRole.UserRole
_ANCHO_BOTON = 260


def _item_cantidad(valor: int) -> QTableWidgetItem:
    item = QTableWidgetItem(str(valor))
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


_CONCEPTOS_RESUMEN = [
    ("pagos", "Pagos registrados"),
    ("liquidaciones", "Liquidaciones emitidas"),
    ("cargos_especiales", "Cargos especiales"),
    ("feriados_trabajados", "Feriados trabajados"),
    ("planes_de_pago", "Planes de pago"),
    ("cuotas", "Cuotas de plan"),
    ("reservas_aisladas", "Reservas aisladas y extraordinarias"),
    ("snapshots", "Snapshots mensuales"),
    ("estados_mensajeria", "Estado de mensajería por período"),
]


class _DialogoAjustarSaldo(QDialog):
    def __init__(self, nombre_profesional: str, saldo_actual: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustar saldo anterior")
        layout = QFormLayout(self)
        layout.addRow(QLabel(nombre_profesional))
        self.spin_saldo = QDoubleSpinBox()
        self.spin_saldo.setRange(-999999999, 999999999)
        self.spin_saldo.setDecimals(2)
        self.spin_saldo.setValue(saldo_actual)
        layout.addRow("Saldo anterior", self.spin_saldo)
        # Pedido explícito de la clienta: el importe prefijado queda
        # seleccionado al enfocar, para empezar a escribir encima y
        # borrarlo a la vez — acá cubre el foco automático que Qt le da
        # a `spin_saldo` al abrirse el diálogo (único campo editable).
        self._foco_saldo = instalar_seleccionar_todo_al_enfocar(self.spin_saldo, parent=self)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.spin_saldo.setFocus()

    def saldo(self) -> float:
        return self.spin_saldo.value()


class _PanelSaldosIniciales(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.reiniciar()

    def reiniciar(self) -> None:
        self.campo_buscar.clear()
        self.actualizar()
        self.campo_buscar.setFocus()

    def _armar_ui(self) -> None:
        layout_solapa = QHBoxLayout(self)

        columna_widget = QWidget()
        columna = QVBoxLayout(columna_widget)
        etiqueta_buscar = QLabel("Buscar profesional")
        etiqueta_buscar.setObjectName("subtituloCampo")
        columna.addWidget(etiqueta_buscar)
        self.campo_buscar = QLineEdit()
        self.campo_buscar.setFixedWidth(_ANCHO_BOTON)
        self.campo_buscar.textChanged.connect(self._aplicar_filtro_busqueda)
        columna.addWidget(self.campo_buscar)

        self.boton_ajustar = QPushButton("Ajustar saldo anterior")
        self.boton_ajustar.setObjectName("botonPrimario")
        self.boton_ajustar.setFixedWidth(_ANCHO_BOTON)
        self.boton_ajustar.clicked.connect(self._ajustar_seleccionado)
        self.boton_ajustar.setEnabled(False)
        self.boton_todos_cero = QPushButton("Poner todos en $0")
        self.boton_todos_cero.setObjectName("botonSecundario")
        self.boton_todos_cero.setFixedWidth(_ANCHO_BOTON)
        self.boton_todos_cero.clicked.connect(self._poner_todos_en_cero)
        columna.addWidget(self.boton_ajustar)
        columna.addWidget(self.boton_todos_cero)
        columna.addStretch()
        layout_solapa.addWidget(columna_widget)

        self.tabla = QTableWidget()
        excluir_tabla_del_tab(self.tabla)
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Profesional", "Categoría", "Saldo actual", "Saldo anterior"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.itemSelectionChanged.connect(self._actualizar_boton)
        self.tabla.doubleClicked.connect(self._ajustar_seleccionado)
        layout_solapa.addWidget(self.tabla, stretch=1)

        self._foco = instalar_enter_avanza_foco(
            [self.campo_buscar, self.boton_ajustar, self.boton_todos_cero], parent=self,
        )

    def _aplicar_filtro_busqueda(self, *_args) -> None:
        """Mismo criterio que "Filtros que solo afectan la visualización":
        solo oculta filas, sin distinguir mayúsculas ni acentos, por
        cualquier columna visible (código, nombre, categoría)."""
        buscado = _normalizar_busqueda(self.campo_buscar.text().strip())
        for fila in range(self.tabla.rowCount()):
            if not buscado:
                self.tabla.setRowHidden(fila, False)
                continue
            texto_fila = " ".join(
                self.tabla.item(fila, col).text()
                for col in range(self.tabla.columnCount())
                if self.tabla.item(fila, col) is not None
            )
            self.tabla.setRowHidden(fila, buscado not in _normalizar_busqueda(texto_fila))

    def actualizar(self) -> None:
        filas = sorted(
            profesionales_con_saldo(self.conn),
            key=lambda f: clave_orden_profesional(f["CategoriaProfesional"], f["IdCodigo"]),
        )
        self.tabla.setRowCount(len(filas))
        for fila_idx, f in enumerate(filas):
            item = QTableWidgetItem(_texto_profesional(f))
            item.setData(_ID_REGISTRO, f["IdProfesional"])
            self.tabla.setItem(fila_idx, 0, item)
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(f["CategoriaProfesional"]))
            self.tabla.setItem(fila_idx, 2, item_monto(f["SaldoCuentaActual"]))
            self.tabla.setItem(fila_idx, 3, item_monto(f["SaldoCuentaAnterior"]))
        self.tabla.resizeColumnsToContents()
        self._aplicar_filtro_busqueda()
        self._actualizar_boton()

    def _fila_seleccionada(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self.tabla.item(filas[0].row(), 0).data(_ID_REGISTRO)

    def _actualizar_boton(self) -> None:
        self.boton_ajustar.setEnabled(self._fila_seleccionada() is not None)

    def _ajustar_seleccionado(self) -> None:
        id_profesional = self._fila_seleccionada()
        if id_profesional is None:
            QMessageBox.warning(self, "Ajustar saldo anterior", "Elegí un profesional de la tabla.")
            return
        filas = profesionales_con_saldo(self.conn)
        fila = next(f for f in filas if f["IdProfesional"] == id_profesional)
        dialogo = _DialogoAjustarSaldo(_texto_profesional(fila), fila["SaldoCuentaAnterior"] or 0.0, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        ajustar_saldo_anterior(self.conn, id_profesional, dialogo.saldo())
        self.actualizar()
        QMessageBox.information(self, "Ajustar saldo anterior", "Saldo anterior actualizado con éxito.")

    def _poner_todos_en_cero(self) -> None:
        respuesta = QMessageBox.question(
            self, "Poner todos en $0",
            "¿Confirmás poner el saldo anterior de TODOS los profesionales R, A y X en $0?",
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        for fila in profesionales_con_saldo(self.conn):
            ajustar_saldo_anterior(self.conn, fila["IdProfesional"], 0.0)
        self.actualizar()
        QMessageBox.information(self, "Poner todos en $0", "Saldos anteriores puestos en $0 con éxito.")


class _PanelDepurarHistorial(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.reiniciar()

    def reiniciar(self) -> None:
        self.selector_periodo.set_periodo(sumar_meses(periodo_actual(self.conn), -1))
        self.actualizar()
        self.selector_periodo.spin_anio.setFocus()

    def _armar_ui(self) -> None:
        layout_solapa = QHBoxLayout(self)

        columna_widget = QWidget()
        columna = QVBoxLayout(columna_widget)
        columna.addWidget(QLabel("Borrar todo lo generado hasta este período (inclusive):"))
        self.selector_periodo = SelectorPeriodo(self.conn)
        # Default: el mes anterior al actual — el que recién se cerró
        # de prueba al avanzar de mes, el caso de uso real de esta
        # pantalla (distinto del default de `SelectorPeriodo`, que es
        # el mes EN CURSO).
        self.selector_periodo.set_periodo(sumar_meses(periodo_actual(self.conn), -1))
        self.selector_periodo.cambiado.connect(self.actualizar)
        columna.addWidget(self.selector_periodo)
        self.etiqueta_aviso = QLabel(
            "No toca estructura física, profesionales, reservas regulares ni archivos subidos — "
            "solo pagos, liquidaciones, cargos especiales, feriados trabajados, planes de pago, "
            "reservas aisladas/extraordinarias, snapshots y estado de mensajería del período elegido "
            "o anterior."
        )
        self.etiqueta_aviso.setWordWrap(True)
        columna.addWidget(self.etiqueta_aviso)

        self.boton_depurar = QPushButton("Depurar historial de prueba")
        self.boton_depurar.setObjectName("botonPrimario")
        self.boton_depurar.setFixedWidth(_ANCHO_BOTON)
        self.boton_depurar.clicked.connect(self._depurar)
        columna.addWidget(self.boton_depurar)
        columna.addStretch()
        layout_solapa.addWidget(columna_widget)

        self.tabla = QTableWidget()
        excluir_tabla_del_tab(self.tabla)
        self.tabla.setColumnCount(2)
        self.tabla.setHorizontalHeaderLabels(["Concepto", "Cantidad a borrar"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        layout_solapa.addWidget(self.tabla, stretch=1)

        self._foco = instalar_enter_avanza_foco(
            [self.selector_periodo.spin_anio, self.selector_periodo.combo_mes, self.boton_depurar], parent=self,
        )

    def actualizar(self) -> None:
        resumen = contar_registros_a_depurar(self.conn, self.selector_periodo.periodo())
        self.tabla.setRowCount(len(_CONCEPTOS_RESUMEN) + 1)
        for fila_idx, (campo, etiqueta) in enumerate(_CONCEPTOS_RESUMEN):
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(etiqueta))
            self.tabla.setItem(fila_idx, 1, _item_cantidad(getattr(resumen, campo)))
        self.tabla.setItem(len(_CONCEPTOS_RESUMEN), 0, QTableWidgetItem("Total"))
        self.tabla.setItem(len(_CONCEPTOS_RESUMEN), 1, _item_cantidad(resumen.total))
        self.tabla.resizeColumnsToContents()
        self.boton_depurar.setEnabled(resumen.total > 0)

    def _depurar(self) -> None:
        periodo_corte = self.selector_periodo.periodo()
        resumen = contar_registros_a_depurar(self.conn, periodo_corte)
        if resumen.total == 0:
            QMessageBox.information(self, "Depurar historial de prueba", "No hay nada para borrar en ese período.")
            return
        if not hay_contrasena_maestra(self.conn):
            QMessageBox.warning(
                self, "Depurar historial de prueba",
                "No hay una contraseña maestra configurada todavía — configurá una desde "
                "Configuración general > Seguridad antes de poder usar esta acción.",
            )
            return
        respuesta = QMessageBox.question(
            self, "Depurar historial de prueba",
            f"Esta acción NO se puede deshacer. Se van a borrar {resumen.total} registro(s) "
            f"hasta el período {periodo_corte} (inclusive). ¿Confirmás?",
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        contrasena, confirmado = QInputDialog.getText(
            self, "Depurar historial de prueba", "Contraseña maestra:", QLineEdit.EchoMode.Password,
        )
        if not confirmado:
            return
        if not verificar_contrasena_maestra(self.conn, contrasena):
            QMessageBox.warning(self, "Depurar historial de prueba", "Contraseña incorrecta.")
            return
        depurar_historial_hasta_periodo(self.conn, periodo_corte)
        self.actualizar()
        QMessageBox.information(self, "Depurar historial de prueba", "Historial depurado con éxito.")


class PantallaReinicioPrueba(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Reinicio de prueba".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_saldos = _PanelSaldosIniciales(conn)
        self.pestanas.addTab(self.panel_saldos, "Saldos iniciales")
        self.panel_depurar = _PanelDepurarHistorial(conn)
        self.pestanas.addTab(self.panel_depurar, "Depurar historial de prueba")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
