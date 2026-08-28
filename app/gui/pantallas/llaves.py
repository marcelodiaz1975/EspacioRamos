"""Pantalla de Llaves (sección 3.7): administra las llaves con el CRUD
genérico, sus accesos (LlaveAcceso — a qué edificio/unidad abre, sección
3.7) y, para la llave seleccionada, su historial de entregas y
devoluciones — reusa app.negocio.llaves.entregar_llave/devolver_llave en
vez de tocar LlaveProfesional a mano, para no saltarse la validación de
"un titular por vez" ni el cargo especial de depósito que generan.

Es F18 — asignado por nosotros en la revisión uno por uno con la
clienta: es el único número sin usar entre F16 (Reservas regulares) y
F27 (Ausencias), y no había ninguno confirmado para esta pantalla en
ningún documento del proyecto; si la planilla original de la clienta ya
le tenía otro número, hay que corregirlo acá.

"Deshacer último movimiento" (pedido explícito en la revisión): a
diferencia de las demás pantallas, acá cubre CUALQUIER acción hecha en
el formulario, sin importar de cuál se trate — dar de alta/modificar/
eliminar una llave (parte genérica), agregar/quitar un acceso, entregar
o devolver. Se guarda un solo registro de "qué fue lo último" (se pisa
con cada acción nueva) y el botón lo revierte por completo, incluido el
cargo especial de depósito/reintegro si esa acción generó uno."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.crud_generico import Campo, PantallaCRUD
from app.gui.pantallas.reservas import _opciones_profesional, _texto_profesional
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.orden_tabla import OrdenTabla
from app.negocio.listas_editables import opciones_lista
from app.negocio.llaves import agregar_acceso_llave, devolver_llave, entregar_llave
from app.repositorio.registro import obtener_repositorio

_CATEGORIAS_TODAS = ("R", "A", "B", "E", "X", "C")


class PantallaLlaves(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._tenencias: list[sqlite3.Row] = []
        self._accesos_actuales: list[sqlite3.Row] = []
        self._ultimo: dict | None = None
        self._armar_ui()

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar": el
        widget todavía no está mostrado en ese momento."""
        super().showEvent(event)
        self._orden_accesos.reiniciar()
        self._orden_tenencias.reiniciar()
        self._actualizar_tenencias()
        self._actualizar_accesos()
        self.crud_llaves.boton_nuevo.setFocus()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Llaves")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        splitter = QSplitter()
        campos = [
            Campo("Descripcion", "Descripción"),
            Campo("Tipo", "Tipo", tipo="combo", opciones=opciones_lista("TipoLlave")),
            Campo("ValorDepositoActual", "Depósito actual", tipo="numero"),
            Campo("ValorDepositoAnterior", "Depósito anterior", tipo="numero"),
            Campo("Activo", "Activo", tipo="booleano"),
        ]
        self.crud_llaves = PantallaCRUD(
            self.conn, "Llave", "", campos, instalar_foco=False,
            al_crear=self._on_crear_llave, al_actualizar=self._on_modificar_llave,
            al_eliminar=self._on_eliminar_llave,
        )
        self.crud_llaves.tabla_widget.itemSelectionChanged.connect(self._actualizar_tenencias)
        self.crud_llaves.tabla_widget.itemSelectionChanged.connect(self._actualizar_accesos)
        splitter.addWidget(self.crud_llaves)

        panel_tenencias = QWidget()
        layout_tenencias = QVBoxLayout(panel_tenencias)

        layout_tenencias.addWidget(QLabel("Accesos (edificios/unidades que abre)"))
        self.tabla_accesos = QTableWidget()
        self.tabla_accesos.setColumnCount(3)
        self.tabla_accesos.setHorizontalHeaderLabels(["Edificio", "Unidad", "Descripción"])
        self.tabla_accesos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_accesos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_accesos.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_accesos.setMaximumHeight(140)
        self._orden_accesos = OrdenTabla(self.tabla_accesos, self._actualizar_accesos)
        layout_tenencias.addWidget(self.tabla_accesos)

        fila_accesos = QHBoxLayout()
        self.boton_agregar_acceso = QPushButton("Agregar acceso…")
        self.boton_agregar_acceso.clicked.connect(self._agregar_acceso)
        self.boton_eliminar_acceso = QPushButton("Eliminar acceso")
        self.boton_eliminar_acceso.clicked.connect(self._eliminar_acceso)
        fila_accesos.addWidget(self.boton_agregar_acceso)
        fila_accesos.addWidget(self.boton_eliminar_acceso)
        fila_accesos.addStretch()
        layout_tenencias.addLayout(fila_accesos)

        layout_tenencias.addWidget(QLabel("Historial de tenencia"))
        self.tabla_tenencias = QTableWidget()
        self.tabla_tenencias.setColumnCount(5)
        self.tabla_tenencias.setHorizontalHeaderLabels(
            ["Profesional", "Entrega", "Devolución", "Depósito cobrado", "Depósito reintegrado"]
        )
        self.tabla_tenencias.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._orden_tenencias = OrdenTabla(self.tabla_tenencias, self._actualizar_tenencias)
        layout_tenencias.addWidget(self.tabla_tenencias, stretch=1)

        fila_acciones = QHBoxLayout()
        self.boton_entregar = QPushButton("Entregar…")
        self.boton_entregar.setObjectName("botonPrimario")
        self.boton_entregar.clicked.connect(self._entregar)
        self.boton_devolver = QPushButton("Registrar devolución…")
        self.boton_devolver.clicked.connect(self._devolver)
        self.boton_deshacer = QPushButton("Deshacer último movimiento")
        self.boton_deshacer.clicked.connect(self._deshacer_ultimo)
        self.boton_deshacer.setEnabled(False)
        fila_acciones.addWidget(self.boton_entregar)
        fila_acciones.addWidget(self.boton_devolver)
        fila_acciones.addWidget(self.boton_deshacer)
        fila_acciones.addStretch()
        layout_tenencias.addLayout(fila_acciones)
        splitter.addWidget(panel_tenencias)

        layout.addWidget(splitter, stretch=1)
        self._actualizar_tenencias()
        self._actualizar_accesos()

        self._foco = instalar_enter_avanza_foco([
            self.crud_llaves.boton_nuevo, self.crud_llaves.boton_editar, self.crud_llaves.boton_eliminar,
            self.boton_agregar_acceso, self.boton_eliminar_acceso,
            self.boton_entregar, self.boton_devolver, self.boton_deshacer,
        ], parent=self)

    def actualizar(self) -> None:
        self.crud_llaves.actualizar()
        self._actualizar_tenencias()
        self._actualizar_accesos()

    # ------------------------------------------------------------- accesos

    def _accesos(self, id_llave: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT la.*, e.Nombre AS NombreEdificio, u.Departamento
            FROM LlaveAcceso la
            JOIN Edificio e ON e.IdEdificio = la.IdEdificio
            LEFT JOIN Unidad u ON u.IdUnidad = la.IdUnidad
            WHERE la.IdLlave = ? ORDER BY e.Nombre, u.Departamento
            """,
            (id_llave,),
        ).fetchall()

    @staticmethod
    def _clave_orden_accesos(columna: int):
        claves = {
            0: lambda a: a["NombreEdificio"] or "",
            1: lambda a: a["Departamento"] or "",
            2: lambda a: a["DescripcionAcceso"] or "",
        }
        return claves[columna]

    def _actualizar_accesos(self) -> None:
        id_llave = self.crud_llaves.fila_seleccionada_id()
        self.boton_agregar_acceso.setEnabled(id_llave is not None)
        self.boton_eliminar_acceso.setEnabled(False)
        self._accesos_actuales = []
        self.tabla_accesos.setRowCount(0)
        if id_llave is None:
            return
        accesos = self._accesos(id_llave)
        if self._orden_accesos.columna is not None:
            accesos = sorted(
                accesos, key=self._clave_orden_accesos(self._orden_accesos.columna),
                reverse=not self._orden_accesos.ascendente,
            )
        self._accesos_actuales = accesos
        self.tabla_accesos.setRowCount(len(accesos))
        for fila_idx, a in enumerate(accesos):
            self.tabla_accesos.setItem(fila_idx, 0, QTableWidgetItem(a["NombreEdificio"]))
            self.tabla_accesos.setItem(fila_idx, 1, QTableWidgetItem(a["Departamento"] or "Todas"))
            self.tabla_accesos.setItem(fila_idx, 2, QTableWidgetItem(a["DescripcionAcceso"] or ""))
        self.tabla_accesos.resizeColumnsToContents()
        self.boton_eliminar_acceso.setEnabled(bool(self._accesos_actuales))

    def _agregar_acceso(self) -> None:
        id_llave = self.crud_llaves.fila_seleccionada_id()
        if id_llave is None:
            return
        dialogo = _DialogoAcceso(self.conn, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            id_acceso = agregar_acceso_llave(self.conn, id_llave=id_llave, **dialogo.valores())
        except ValueError as error:
            QMessageBox.warning(self, "Agregar acceso", str(error))
            return
        self.conn.commit()
        self._marcar_ultimo({"tipo": "agregar_acceso", "id_acceso": id_acceso})
        self._actualizar_accesos()
        self.crud_llaves.boton_nuevo.setFocus()

    def _eliminar_acceso(self) -> None:
        filas = self.tabla_accesos.selectionModel().selectedRows()
        if not filas:
            QMessageBox.information(self, "Eliminar acceso", "Seleccioná un acceso para eliminar.")
            return
        acceso = self._accesos_actuales[filas[0].row()]
        valores_previos = {k: acceso[k] for k in acceso.keys() if k != "IdLlaveAcceso"}
        obtener_repositorio(self.conn, "LlaveAcceso").eliminar(acceso["IdLlaveAcceso"])
        self.conn.commit()
        self._marcar_ultimo({"tipo": "eliminar_acceso", "valores_previos": valores_previos})
        self._actualizar_accesos()
        self.crud_llaves.boton_nuevo.setFocus()

    # ----------------------------------------------------------- tenencias

    @staticmethod
    def _clave_orden_tenencias(columna: int):
        claves = {
            0: lambda par: _texto_profesional(par[1]) if par[1] else "",
            1: lambda par: par[0]["FechaEntrega"] or "",
            2: lambda par: par[0]["FechaDevolucion"] or "",
            3: lambda par: bool(par[0]["DepositoCobrado"]),
            4: lambda par: bool(par[0]["DepositoReintegrado"]),
        }
        return claves[columna]

    def _actualizar_tenencias(self) -> None:
        id_llave = self.crud_llaves.fila_seleccionada_id()
        self.boton_entregar.setEnabled(id_llave is not None)
        self.boton_devolver.setEnabled(False)
        self._tenencias = []
        self.tabla_tenencias.setRowCount(0)
        if id_llave is None:
            return

        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        tenencias = obtener_repositorio(self.conn, "LlaveProfesional").listar(IdLlave=id_llave)
        filas = [(t, repo_profesional.obtener(t["IdProfesional"])) for t in tenencias]
        if self._orden_tenencias.columna is not None:
            filas.sort(
                key=self._clave_orden_tenencias(self._orden_tenencias.columna),
                reverse=not self._orden_tenencias.ascendente,
            )
        else:
            filas.sort(key=lambda par: par[0]["FechaEntrega"] or "", reverse=True)
        self._tenencias = [t for t, _p in filas]

        self.tabla_tenencias.setRowCount(len(filas))
        hay_titular_activo = False
        for fila_idx, (t, profesional) in enumerate(filas):
            self.tabla_tenencias.setItem(
                fila_idx, 0, QTableWidgetItem(_texto_profesional(profesional) if profesional else "?")
            )
            self.tabla_tenencias.setItem(fila_idx, 1, QTableWidgetItem(t["FechaEntrega"] or ""))
            self.tabla_tenencias.setItem(fila_idx, 2, QTableWidgetItem(t["FechaDevolucion"] or ""))
            self.tabla_tenencias.setItem(fila_idx, 3, QTableWidgetItem("Sí" if t["DepositoCobrado"] else "No"))
            self.tabla_tenencias.setItem(fila_idx, 4, QTableWidgetItem("Sí" if t["DepositoReintegrado"] else "No"))
            if t["FechaDevolucion"] is None:
                hay_titular_activo = True
        self.tabla_tenencias.resizeColumnsToContents()
        self.boton_devolver.setEnabled(hay_titular_activo)

    def _cargo_especial_creado(self, id_llave: int, cargos_antes: set[int]) -> sqlite3.Row | None:
        """El depósito/reintegro genera como mucho un CargoEspecial nuevo
        por acción — se detecta por diferencia de conjunto en vez de
        duplicar acá la condición exacta que usa entregar_llave/
        devolver_llave para decidir si correspondía crear uno."""
        return next(
            (c for c in obtener_repositorio(self.conn, "CargoEspecial").listar(IdLlave=id_llave)
             if c["IdCargo"] not in cargos_antes),
            None,
        )

    def _entregar(self) -> None:
        id_llave = self.crud_llaves.fila_seleccionada_id()
        if id_llave is None:
            return
        dialogo = _DialogoEntrega(self.conn, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        cargos_antes = {c["IdCargo"] for c in obtener_repositorio(self.conn, "CargoEspecial").listar(IdLlave=id_llave)}
        try:
            id_llave_profesional = entregar_llave(self.conn, id_llave=id_llave, **dialogo.valores())
        except ValueError as error:
            QMessageBox.warning(self, "Entregar llave", str(error))
            return
        self.conn.commit()
        cargo_nuevo = self._cargo_especial_creado(id_llave, cargos_antes)
        self._marcar_ultimo({
            "tipo": "entregar", "id_llave_profesional": id_llave_profesional,
            "id_cargo_especial": cargo_nuevo["IdCargo"] if cargo_nuevo else None,
        })
        self._actualizar_tenencias()
        self.crud_llaves.boton_nuevo.setFocus()

    def _devolver(self) -> None:
        activa = next((t for t in self._tenencias if t["FechaDevolucion"] is None), None)
        if activa is None:
            return
        dialogo = _DialogoDevolucion(activa, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        id_llave = activa["IdLlave"]
        cargos_antes = {c["IdCargo"] for c in obtener_repositorio(self.conn, "CargoEspecial").listar(IdLlave=id_llave)}
        try:
            devolver_llave(self.conn, activa["IdLlaveProfesional"], **dialogo.valores())
        except ValueError as error:
            QMessageBox.warning(self, "Registrar devolución", str(error))
            return
        self.conn.commit()
        cargo_nuevo = self._cargo_especial_creado(id_llave, cargos_antes)
        self._marcar_ultimo({
            "tipo": "devolver", "id_llave_profesional": activa["IdLlaveProfesional"],
            "id_cargo_especial": cargo_nuevo["IdCargo"] if cargo_nuevo else None,
        })
        self._actualizar_tenencias()
        self.crud_llaves.boton_nuevo.setFocus()

    # -------------------------------------------------- deshacer (genérico)

    def _on_crear_llave(self, id_nuevo: int, valores: dict) -> None:
        self._marcar_ultimo({"tipo": "crear_llave", "id_llave": id_nuevo})

    def _on_modificar_llave(self, registro_anterior: sqlite3.Row, valores_nuevos: dict) -> None:
        self._marcar_ultimo({
            "tipo": "modificar_llave", "id_llave": registro_anterior["IdLlave"],
            "valores_previos": {k: registro_anterior[k] for k in valores_nuevos},
        })

    def _on_eliminar_llave(self, registro: sqlite3.Row) -> None:
        valores_previos = {k: registro[k] for k in registro.keys() if k != "IdLlave"}
        self._marcar_ultimo({"tipo": "eliminar_llave", "valores_previos": valores_previos})

    def _marcar_ultimo(self, movimiento: dict) -> None:
        self._ultimo = movimiento
        self.boton_deshacer.setEnabled(True)

    def _deshacer_ultimo(self) -> None:
        if self._ultimo is None:
            QMessageBox.warning(self, "Deshacer último movimiento", "No hay ningún movimiento para deshacer.")
            return
        respuesta = QMessageBox.question(
            self, "Deshacer último movimiento",
            "Esto revierte por completo el último movimiento hecho en este formulario (alta/edición/baja de "
            "llave, acceso, entrega o devolución), incluido cualquier cargo especial que haya generado. "
            "¿Confirmás?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        movimiento = self._ultimo
        tipo = movimiento["tipo"]
        if tipo == "crear_llave":
            obtener_repositorio(self.conn, "Llave").eliminar(movimiento["id_llave"])
        elif tipo == "modificar_llave":
            obtener_repositorio(self.conn, "Llave").actualizar(movimiento["id_llave"], **movimiento["valores_previos"])
        elif tipo == "eliminar_llave":
            obtener_repositorio(self.conn, "Llave").crear(**movimiento["valores_previos"])
        elif tipo == "agregar_acceso":
            obtener_repositorio(self.conn, "LlaveAcceso").eliminar(movimiento["id_acceso"])
        elif tipo == "eliminar_acceso":
            obtener_repositorio(self.conn, "LlaveAcceso").crear(**movimiento["valores_previos"])
        elif tipo == "entregar":
            obtener_repositorio(self.conn, "LlaveProfesional").eliminar(movimiento["id_llave_profesional"])
            if movimiento["id_cargo_especial"] is not None:
                obtener_repositorio(self.conn, "CargoEspecial").eliminar(movimiento["id_cargo_especial"])
        elif tipo == "devolver":
            obtener_repositorio(self.conn, "LlaveProfesional").actualizar(
                movimiento["id_llave_profesional"], FechaDevolucion=None, DepositoReintegrado=0,
                MontoReintegrado=None,
            )
            if movimiento["id_cargo_especial"] is not None:
                obtener_repositorio(self.conn, "CargoEspecial").eliminar(movimiento["id_cargo_especial"])

        self._ultimo = None
        self.boton_deshacer.setEnabled(False)
        self.conn.commit()
        self.actualizar()
        self.crud_llaves.boton_nuevo.setFocus()


class _DialogoEntrega(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Entregar llave")
        layout = QFormLayout(self)

        self.combo_profesional = QComboBox()
        for id_, etiqueta in _opciones_profesional(conn, _CATEGORIAS_TODAS):
            self.combo_profesional.addItem(etiqueta, id_)
        layout.addRow("Profesional", self.combo_profesional)

        self.casilla_deposito = QCheckBox("Cobrar depósito")
        layout.addRow(self.casilla_deposito)
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMaximum(10_000_000)
        layout.addRow("Monto cobrado", self.spin_monto)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.combo_profesional, self.casilla_deposito, self.spin_monto, boton_ok, boton_cancelar],
            parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.combo_profesional.setFocus()

    def valores(self) -> dict:
        return {
            "id_profesional": self.combo_profesional.currentData(),
            "cobrar_deposito": self.casilla_deposito.isChecked(),
            "monto_cobrado": self.spin_monto.value() or None,
        }


class _DialogoAcceso(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Agregar acceso")
        layout = QFormLayout(self)

        self.combo_edificio = QComboBox()
        for f in conn.execute("SELECT IdEdificio, Nombre FROM Edificio ORDER BY Nombre"):
            self.combo_edificio.addItem(f["Nombre"], f["IdEdificio"])
        self.combo_edificio.currentIndexChanged.connect(self._cargar_unidades)
        layout.addRow("Edificio", self.combo_edificio)

        self.combo_unidad = QComboBox()
        layout.addRow("Unidad", self.combo_unidad)
        self._cargar_unidades()

        self.campo_descripcion = QLineEdit()
        self.campo_descripcion.setPlaceholderText("Descripción del acceso (opcional)")
        layout.addRow("Descripción", self.campo_descripcion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.combo_edificio, self.combo_unidad, self.campo_descripcion, boton_ok, boton_cancelar],
            parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.combo_edificio.setFocus()

    def _cargar_unidades(self) -> None:
        self.combo_unidad.clear()
        self.combo_unidad.addItem("Todas las unidades del edificio", None)
        id_edificio = self.combo_edificio.currentData()
        if id_edificio is None:
            return
        for f in self.conn.execute(
            "SELECT IdUnidad, Departamento FROM Unidad WHERE IdEdificio = ? ORDER BY Departamento", (id_edificio,)
        ):
            self.combo_unidad.addItem(f["Departamento"], f["IdUnidad"])

    def valores(self) -> dict:
        return {
            "id_edificio": self.combo_edificio.currentData(),
            "id_unidad": self.combo_unidad.currentData(),
            "descripcion_acceso": self.campo_descripcion.text().strip() or None,
        }


class _DialogoDevolucion(QDialog):
    def __init__(self, tenencia: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar devolución")
        layout = QFormLayout(self)

        self.casilla_reintegro = QCheckBox("Reintegrar depósito")
        self.casilla_reintegro.setChecked(bool(tenencia["DepositoCobrado"]))
        layout.addRow(self.casilla_reintegro)
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMaximum(10_000_000)
        self.spin_monto.setValue(tenencia["MontoCobrado"] or 0)
        layout.addRow("Monto a reintegrar", self.spin_monto)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.casilla_reintegro, self.spin_monto, boton_ok, boton_cancelar], parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.casilla_reintegro.setFocus()

    def valores(self) -> dict:
        return {
            "reintegrar_deposito": self.casilla_reintegro.isChecked(),
            "monto_reintegrado": self.spin_monto.value() or None,
        }
