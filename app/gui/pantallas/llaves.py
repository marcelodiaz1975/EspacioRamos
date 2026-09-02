"""Pantalla de Llaves (sección 3.7, replanteada en conversación con la
clienta — segunda vuelta): administra los TIPOS de llave (Tipos de
llaves), sus accesos (Accesos habilitados con la llave) y un libro único
de movimientos de todas las llaves (Movimientos de llaves) — ver el
docstring de app.negocio.llaves para el detalle del modelo.

Las tres tablas no usan PantallaCRUD/Campo (a diferencia de otros
catálogos) porque el Nombre del Tipo se arma solo (no es un campo de
formulario) y el Tipo queda bloqueado al editar — casos puntuales que el
CRUD genérico no cubre. En su lugar, cada sección arma su propia tabla y
sus propios diálogos, siguiendo el mismo patrón que ya usaban Accesos y
Movimientos en la versión anterior de esta pantalla.

Es F18 — asignado por nosotros en la revisión uno por uno con la
clienta: es el único número sin usar entre F16 (Reservas regulares) y
F27 (Ausencias), confirmado con ella.

"Deshacer último movimiento" (pedido explícito en la revisión): cubre
CUALQUIER acción hecha en el formulario, sin importar de cuál se trate —
dar de alta/modificar/eliminar un Tipo de llave, agregar/quitar un
acceso, ingresar copias, asignar, devolver o registrar una pérdida. Se
guarda un solo registro de "qué fue lo último" (se pisa con cada acción
nueva) y el botón lo revierte por completo, incluido el cargo especial
de depósito/reintegro si esa acción generó uno."""
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.pantallas.reservas import _opciones_profesional, _texto_profesional
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.orden_tabla import OrdenTabla
from app.negocio.listas_editables import opciones_lista
from app.negocio.llaves import (
    agregar_acceso_llave,
    asignar_llave,
    crear_llave,
    devolver_llave,
    ingresar_copias,
    registrar_perdida,
    resumen_stock,
    siguiente_nombre_llave,
)
from app.repositorio.registro import obtener_repositorio

_CATEGORIAS_TODAS = ("R", "A", "B", "E", "X", "C")
_DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _fecha_larga(iso: str) -> str:
    d = date.fromisoformat(iso)
    dia = _DIAS_SEMANA[d.weekday()]
    return f"{dia[0].upper()}{dia[1:]} {d.strftime('%d-%m-%Y')}"


def _moneda(monto: float) -> str:
    return f"${monto:,.0f}".replace(",", ".")


def _fecha_edit(valor_iso: str | None = None) -> QDateEdit:
    campo = QDateEdit()
    campo.setCalendarPopup(True)
    campo.setDisplayFormat("dd-MM-yyyy")
    campo.setLocale(QLocale(QLocale.Language.Spanish))
    campo.setDate(QDate.fromString(valor_iso, Qt.DateFormat.ISODate) if valor_iso else QDate.currentDate())
    return campo


class PantallaLlaves(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._tipos_actuales: list[sqlite3.Row] = []
        self._accesos_actuales: list[sqlite3.Row] = []
        self._movimientos_actuales: list[sqlite3.Row] = []
        self._ultimo: dict | None = None
        self._armar_ui()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._orden_tipos.reiniciar()
        self._orden_accesos.reiniciar()
        self._orden_movimientos.reiniciar()
        self.actualizar()
        self.boton_nuevo_tipo.setFocus()

    @staticmethod
    def _titulo_seccion(texto: str) -> QLabel:
        etiqueta = QLabel(texto)
        etiqueta.setStyleSheet("font-size: 13px; font-weight: bold;")
        return etiqueta

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        # ------------------------------------------------------- izquierda
        panel_izq = QWidget()
        layout_izq = QVBoxLayout(panel_izq)

        layout_izq.addWidget(self._titulo_seccion("Tipos de llaves"))
        self.tabla_tipos = QTableWidget()
        self.tabla_tipos.setColumnCount(6)
        self.tabla_tipos.setHorizontalHeaderLabels(
            ["Nombre del tipo de llave", "Tipo", "Depósito actual", "Asignadas", "Disponibles", "Total"]
        )
        self.tabla_tipos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_tipos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_tipos.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_tipos.setColumnWidth(0, 200)
        self.tabla_tipos.setColumnWidth(1, 70)
        self.tabla_tipos.setColumnWidth(2, 120)
        self.tabla_tipos.setColumnWidth(3, 90)
        self.tabla_tipos.setColumnWidth(4, 95)
        self.tabla_tipos.setColumnWidth(5, 65)
        self.tabla_tipos.itemSelectionChanged.connect(self._actualizar_accesos)
        self.tabla_tipos.itemSelectionChanged.connect(self._actualizar_observacion_tipo)
        self.tabla_tipos.itemSelectionChanged.connect(self._actualizar_botones_movimiento)
        self._orden_tipos = OrdenTabla(self.tabla_tipos, self._actualizar_tipos)
        layout_izq.addWidget(self.tabla_tipos, stretch=1)

        self.campo_observacion_tipo = QLineEdit()
        self.campo_observacion_tipo.editingFinished.connect(self._guardar_observacion_tipo)
        layout_izq.addWidget(self.campo_observacion_tipo)

        fila_botones_tipo = QHBoxLayout()
        self.boton_nuevo_tipo = QPushButton("Nuevo")
        self.boton_nuevo_tipo.setObjectName("botonPrimario")
        self.boton_nuevo_tipo.clicked.connect(self._nuevo_tipo)
        self.boton_editar_tipo = QPushButton("Editar")
        self.boton_editar_tipo.clicked.connect(self._editar_tipo)
        self.boton_eliminar_tipo = QPushButton("Eliminar")
        self.boton_eliminar_tipo.clicked.connect(self._eliminar_tipo)
        fila_botones_tipo.addWidget(self.boton_nuevo_tipo)
        fila_botones_tipo.addWidget(self.boton_editar_tipo)
        fila_botones_tipo.addWidget(self.boton_eliminar_tipo)
        fila_botones_tipo.addStretch()
        layout_izq.addLayout(fila_botones_tipo)

        layout_izq.addWidget(self._titulo_seccion("Accesos habilitados con la llave"))
        self.tabla_accesos = QTableWidget()
        self.tabla_accesos.setColumnCount(4)
        self.tabla_accesos.setHorizontalHeaderLabels(["Localidad", "Edificio", "Unidad", "Nombre"])
        self.tabla_accesos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_accesos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_accesos.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_accesos.itemSelectionChanged.connect(self._actualizar_observacion_acceso)
        self._orden_accesos = OrdenTabla(self.tabla_accesos, self._actualizar_accesos)
        layout_izq.addWidget(self.tabla_accesos, stretch=1)

        self.campo_observacion_acceso = QLineEdit()
        self.campo_observacion_acceso.editingFinished.connect(self._guardar_observacion_acceso)
        layout_izq.addWidget(self.campo_observacion_acceso)

        fila_accesos = QHBoxLayout()
        self.boton_agregar_acceso = QPushButton("Agregar acceso…")
        self.boton_agregar_acceso.clicked.connect(self._agregar_acceso)
        self.boton_eliminar_acceso = QPushButton("Eliminar acceso")
        self.boton_eliminar_acceso.clicked.connect(self._eliminar_acceso)
        fila_accesos.addWidget(self.boton_agregar_acceso)
        fila_accesos.addWidget(self.boton_eliminar_acceso)
        fila_accesos.addStretch()
        layout_izq.addLayout(fila_accesos)

        panel_izq.setMaximumWidth(720)
        panel_izq.setMinimumWidth(700)
        splitter.addWidget(panel_izq)

        # ------------------------------------------------------- derecha
        panel_der = QWidget()
        layout_der = QVBoxLayout(panel_der)

        layout_der.addWidget(self._titulo_seccion("Movimientos de llaves"))
        self.tabla_movimientos = QTableWidget()
        self.tabla_movimientos.setColumnCount(7)
        self.tabla_movimientos.setHorizontalHeaderLabels(
            ["Fecha", "Movimiento", "Profesional", "Tipo de llave", "Cantidad", "Depósito cobrado", "Depósito reintegrado"]
        )
        self.tabla_movimientos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_movimientos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_movimientos.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_movimientos.itemSelectionChanged.connect(self._actualizar_observacion_movimiento)
        self.tabla_movimientos.itemSelectionChanged.connect(self._actualizar_botones_movimiento)
        self._orden_movimientos = OrdenTabla(self.tabla_movimientos, self._actualizar_movimientos)
        layout_der.addWidget(self.tabla_movimientos, stretch=1)

        self.campo_observacion_movimiento = QLineEdit()
        self.campo_observacion_movimiento.editingFinished.connect(self._guardar_observacion_movimiento)
        layout_der.addWidget(self.campo_observacion_movimiento)

        fila_acciones = QHBoxLayout()
        self.boton_ingresar = QPushButton("Ingresar copia…")
        self.boton_ingresar.clicked.connect(self._ingresar_copia)
        self.boton_asignar = QPushButton("Asignar…")
        self.boton_asignar.setObjectName("botonPrimario")
        self.boton_asignar.clicked.connect(self._asignar)
        self.boton_devolver = QPushButton("Registrar devolución…")
        self.boton_devolver.clicked.connect(self._registrar_devolucion)
        self.boton_perdida = QPushButton("Registrar pérdida…")
        self.boton_perdida.clicked.connect(self._registrar_perdida)
        self.boton_deshacer = QPushButton("Deshacer último movimiento")
        self.boton_deshacer.clicked.connect(self._deshacer_ultimo)
        self.boton_deshacer.setEnabled(False)
        fila_acciones.addWidget(self.boton_ingresar)
        fila_acciones.addWidget(self.boton_asignar)
        fila_acciones.addWidget(self.boton_devolver)
        fila_acciones.addWidget(self.boton_perdida)
        fila_acciones.addWidget(self.boton_deshacer)
        fila_acciones.addStretch()
        layout_der.addLayout(fila_acciones)

        splitter.addWidget(panel_der)
        layout.addWidget(splitter)

        self._foco = instalar_enter_avanza_foco([
            self.campo_observacion_tipo, self.boton_nuevo_tipo, self.boton_editar_tipo, self.boton_eliminar_tipo,
            self.campo_observacion_acceso, self.boton_agregar_acceso, self.boton_eliminar_acceso,
            self.campo_observacion_movimiento,
            self.boton_ingresar, self.boton_asignar, self.boton_devolver, self.boton_perdida, self.boton_deshacer,
        ], parent=self)

        self.actualizar()

    def actualizar(self) -> None:
        self._actualizar_tipos()
        self._actualizar_movimientos()

    # ------------------------------------------------------------- tipos

    def _tipo_seleccionado(self) -> sqlite3.Row | None:
        filas = self.tabla_tipos.selectionModel().selectedRows()
        if not filas:
            return None
        return self._tipos_actuales[filas[0].row()]

    @staticmethod
    def _clave_orden_tipos(columna: int):
        claves = {
            0: lambda par: par[0]["Nombre"] or "",
            1: lambda par: par[0]["Tipo"] or "",
            2: lambda par: par[0]["ValorDepositoActual"] or 0,
            3: lambda par: par[1]["asignadas"],
            4: lambda par: par[1]["disponibles"],
            5: lambda par: par[1]["existentes"],
        }
        return claves[columna]

    def _actualizar_tipos(self) -> None:
        tipo_seleccionado_id = self._tipo_seleccionado()["IdLlave"] if self._tipo_seleccionado() else None
        tipos = obtener_repositorio(self.conn, "Llave").listar()
        filas = [(t, resumen_stock(self.conn, t["IdLlave"])) for t in tipos]
        if self._orden_tipos.columna is not None:
            filas.sort(key=self._clave_orden_tipos(self._orden_tipos.columna), reverse=not self._orden_tipos.ascendente)
        else:
            filas.sort(key=lambda par: par[0]["Nombre"] or "")
        self._tipos_actuales = [t for t, _r in filas]

        self.tabla_tipos.setRowCount(len(filas))
        fila_a_reseleccionar = None
        for fila_idx, (t, resumen) in enumerate(filas):
            self.tabla_tipos.setItem(fila_idx, 0, QTableWidgetItem(t["Nombre"]))
            self.tabla_tipos.setItem(fila_idx, 1, QTableWidgetItem(t["Tipo"]))
            self.tabla_tipos.setItem(fila_idx, 2, QTableWidgetItem(_moneda(t["ValorDepositoActual"])))
            for col, clave in ((3, "asignadas"), (4, "disponibles"), (5, "existentes")):
                item = QTableWidgetItem(str(resumen[clave]))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla_tipos.setItem(fila_idx, col, item)
            if t["IdLlave"] == tipo_seleccionado_id:
                fila_a_reseleccionar = fila_idx
        if fila_a_reseleccionar is not None:
            self.tabla_tipos.selectRow(fila_a_reseleccionar)
        else:
            self._actualizar_accesos()
            self._actualizar_observacion_tipo()

    def _actualizar_observacion_tipo(self) -> None:
        tipo = self._tipo_seleccionado()
        self.campo_observacion_tipo.setEnabled(tipo is not None)
        self.campo_observacion_tipo.setText(tipo["Observacion"] or "" if tipo else "")

    def _guardar_observacion_tipo(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            return
        texto = self.campo_observacion_tipo.text().strip() or None
        if texto == (tipo["Observacion"] or None):
            return
        obtener_repositorio(self.conn, "Llave").actualizar(tipo["IdLlave"], Observacion=texto)
        self.conn.commit()

    def _nuevo_tipo(self) -> None:
        dialogo = _DialogoTipo(self.conn, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        valores = dialogo.valores()
        id_nuevo = crear_llave(
            self.conn, tipo=valores["tipo"], valor_deposito_actual=valores["valor_deposito_actual"],
            observacion=valores["observacion"],
        )
        if not valores["activo"]:
            obtener_repositorio(self.conn, "Llave").actualizar(id_nuevo, Activo=0)
        self.conn.commit()
        self._marcar_ultimo({"tipo": "crear_tipo", "id_llave": id_nuevo})
        self._actualizar_tipos()
        self.boton_nuevo_tipo.setFocus()

    def _editar_tipo(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            QMessageBox.information(self, "Editar", "Seleccioná un Tipo de llave para editar.")
            return
        dialogo = _DialogoTipo(self.conn, self, registro=tipo)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        valores = dialogo.valores()
        valores_previos = {
            "ValorDepositoActual": tipo["ValorDepositoActual"], "Observacion": tipo["Observacion"],
            "Activo": tipo["Activo"],
        }
        obtener_repositorio(self.conn, "Llave").actualizar(
            tipo["IdLlave"], ValorDepositoActual=valores["valor_deposito_actual"],
            Observacion=valores["observacion"], Activo=int(valores["activo"]),
        )
        self.conn.commit()
        self._marcar_ultimo({"tipo": "editar_tipo", "id_llave": tipo["IdLlave"], "valores_previos": valores_previos})
        self._actualizar_tipos()
        self.boton_nuevo_tipo.setFocus()

    def _eliminar_tipo(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            QMessageBox.information(self, "Eliminar", "Seleccioná un Tipo de llave para eliminar.")
            return
        confirmacion = QMessageBox.question(self, "Eliminar", "¿Confirmás eliminar el Tipo de llave seleccionado?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        valores_previos = {k: tipo[k] for k in tipo.keys() if k != "IdLlave"}
        try:
            obtener_repositorio(self.conn, "Llave").eliminar(tipo["IdLlave"])
        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self, "Eliminar",
                "No se puede eliminar: este Tipo de llave tiene accesos o movimientos registrados.",
            )
            return
        self.conn.commit()
        self._marcar_ultimo({"tipo": "eliminar_tipo", "valores_previos": valores_previos})
        self._actualizar_tipos()
        self.boton_nuevo_tipo.setFocus()

    # ----------------------------------------------------------- accesos

    def _accesos(self, id_llave: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT la.*, e.Nombre AS NombreEdificio, e.DomicilioLocalidad AS Localidad, u.Departamento
            FROM LlaveAcceso la
            JOIN Edificio e ON e.IdEdificio = la.IdEdificio
            LEFT JOIN Unidad u ON u.IdUnidad = la.IdUnidad
            WHERE la.IdLlave = ? ORDER BY e.DomicilioLocalidad, e.Nombre, u.Departamento
            """,
            (id_llave,),
        ).fetchall()

    def _acceso_seleccionado(self) -> sqlite3.Row | None:
        filas = self.tabla_accesos.selectionModel().selectedRows()
        if not filas:
            return None
        return self._accesos_actuales[filas[0].row()]

    @staticmethod
    def _clave_orden_accesos(columna: int):
        claves = {
            0: lambda a: a["Localidad"] or "",
            1: lambda a: a["NombreEdificio"] or "",
            2: lambda a: a["Departamento"] or "",
            3: lambda a: a["Nombre"] or "",
        }
        return claves[columna]

    def _actualizar_accesos(self) -> None:
        tipo = self._tipo_seleccionado()
        self.boton_agregar_acceso.setEnabled(tipo is not None)
        self.boton_eliminar_acceso.setEnabled(False)
        self._accesos_actuales = []
        self.tabla_accesos.setRowCount(0)
        if tipo is None:
            self._actualizar_observacion_acceso()
            return
        accesos = self._accesos(tipo["IdLlave"])
        if self._orden_accesos.columna is not None:
            accesos = sorted(
                accesos, key=self._clave_orden_accesos(self._orden_accesos.columna),
                reverse=not self._orden_accesos.ascendente,
            )
        self._accesos_actuales = accesos
        self.tabla_accesos.setRowCount(len(accesos))
        for fila_idx, a in enumerate(accesos):
            self.tabla_accesos.setItem(fila_idx, 0, QTableWidgetItem(a["Localidad"] or ""))
            self.tabla_accesos.setItem(fila_idx, 1, QTableWidgetItem(a["NombreEdificio"]))
            self.tabla_accesos.setItem(fila_idx, 2, QTableWidgetItem(a["Departamento"] or "Todas"))
            self.tabla_accesos.setItem(fila_idx, 3, QTableWidgetItem(a["Nombre"] or ""))
        self.tabla_accesos.resizeColumnsToContents()
        self.boton_eliminar_acceso.setEnabled(bool(self._accesos_actuales))
        self._actualizar_observacion_acceso()

    def _actualizar_observacion_acceso(self) -> None:
        acceso = self._acceso_seleccionado()
        self.campo_observacion_acceso.setEnabled(acceso is not None)
        self.campo_observacion_acceso.setText(acceso["Observacion"] or "" if acceso else "")

    def _guardar_observacion_acceso(self) -> None:
        acceso = self._acceso_seleccionado()
        if acceso is None:
            return
        texto = self.campo_observacion_acceso.text().strip() or None
        if texto == (acceso["Observacion"] or None):
            return
        obtener_repositorio(self.conn, "LlaveAcceso").actualizar(acceso["IdLlaveAcceso"], Observacion=texto)
        self.conn.commit()

    def _agregar_acceso(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            return
        dialogo = _DialogoAcceso(self.conn, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            id_acceso = agregar_acceso_llave(self.conn, id_llave=tipo["IdLlave"], **dialogo.valores())
        except ValueError as error:
            QMessageBox.warning(self, "Agregar acceso", str(error))
            return
        self.conn.commit()
        self._marcar_ultimo({"tipo": "agregar_acceso", "id_acceso": id_acceso})
        self._actualizar_accesos()
        self.boton_nuevo_tipo.setFocus()

    def _eliminar_acceso(self) -> None:
        acceso = self._acceso_seleccionado()
        if acceso is None:
            QMessageBox.information(self, "Eliminar acceso", "Seleccioná un acceso para eliminar.")
            return
        valores_previos = {k: acceso[k] for k in ("IdLlave", "IdEdificio", "IdUnidad", "Nombre", "Observacion")}
        obtener_repositorio(self.conn, "LlaveAcceso").eliminar(acceso["IdLlaveAcceso"])
        self.conn.commit()
        self._marcar_ultimo({"tipo": "eliminar_acceso", "valores_previos": valores_previos})
        self._actualizar_accesos()
        self.boton_nuevo_tipo.setFocus()

    # ------------------------------------------------------- movimientos

    def _movimiento_seleccionado(self) -> sqlite3.Row | None:
        filas = self.tabla_movimientos.selectionModel().selectedRows()
        if not filas:
            return None
        return self._movimientos_actuales[filas[0].row()]

    @staticmethod
    def _clave_orden_movimientos(columna: int):
        claves = {
            0: lambda m: m["Fecha"] or "",
            1: lambda m: m["Tipo"] or "",
            2: lambda m: m["_texto_profesional"],
            3: lambda m: m["_nombre_llave"],
            4: lambda m: m["Cantidad"],
            5: lambda m: m["MontoCobrado"] or 0,
            6: lambda m: m["MontoReintegrado"] or 0,
        }
        return claves[columna]

    def _asignaciones_cerradas(self) -> set[int]:
        cerradas = {
            f["IdAsignacion"] for f in self.conn.execute(
                "SELECT IdAsignacion FROM LlaveMovimiento WHERE IdAsignacion IS NOT NULL"
            ).fetchall()
        }
        return cerradas

    def _actualizar_movimientos(self) -> None:
        repo_prof = obtener_repositorio(self.conn, "Profesional")
        repo_llave = obtener_repositorio(self.conn, "Llave")
        movimientos = obtener_repositorio(self.conn, "LlaveMovimiento").listar()
        enriquecidos = []
        for m in movimientos:
            profesional = repo_prof.obtener(m["IdProfesional"]) if m["IdProfesional"] else None
            llave = repo_llave.obtener(m["IdLlave"])
            enriquecidos.append({
                **dict(m), "_texto_profesional": _texto_profesional(profesional) if profesional else "",
                "_nombre_llave": llave["Nombre"] if llave else "",
            })
        if self._orden_movimientos.columna is not None:
            enriquecidos.sort(
                key=self._clave_orden_movimientos(self._orden_movimientos.columna),
                reverse=not self._orden_movimientos.ascendente,
            )
        else:
            # Fecha de más nuevo a más viejo, luego Movimiento A-Z, luego Profesional A-Z (sort estable:
            # se ordena primero por la clave menos significativa).
            enriquecidos.sort(key=lambda m: m["_texto_profesional"])
            enriquecidos.sort(key=lambda m: m["Tipo"] or "")
            enriquecidos.sort(key=lambda m: m["Fecha"] or "", reverse=True)
        self._movimientos_actuales = enriquecidos

        self.tabla_movimientos.setRowCount(len(enriquecidos))
        for fila_idx, m in enumerate(enriquecidos):
            self.tabla_movimientos.setItem(fila_idx, 0, QTableWidgetItem(_fecha_larga(m["Fecha"])))
            self.tabla_movimientos.setItem(fila_idx, 1, QTableWidgetItem(m["Tipo"]))
            self.tabla_movimientos.setItem(fila_idx, 2, QTableWidgetItem(m["_texto_profesional"]))
            self.tabla_movimientos.setItem(fila_idx, 3, QTableWidgetItem(m["_nombre_llave"]))
            item_cant = QTableWidgetItem(str(m["Cantidad"]))
            item_cant.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla_movimientos.setItem(fila_idx, 4, item_cant)
            cobrado = _moneda(m["MontoCobrado"]) if m["Tipo"] == "Asignación" and m["DepositoCobrado"] else ""
            self.tabla_movimientos.setItem(fila_idx, 5, QTableWidgetItem(cobrado))
            if m["Tipo"] == "Pérdida":
                reintegrado = "No corresponde"
            elif m["Tipo"] == "Devolución" and m["DepositoReintegrado"]:
                reintegrado = _moneda(m["MontoReintegrado"])
            else:
                reintegrado = ""
            self.tabla_movimientos.setItem(fila_idx, 6, QTableWidgetItem(reintegrado))
        self.tabla_movimientos.resizeColumnsToContents()
        self._actualizar_observacion_movimiento()
        self._actualizar_botones_movimiento()

    def _actualizar_observacion_movimiento(self) -> None:
        movimiento = self._movimiento_seleccionado()
        self.campo_observacion_movimiento.setEnabled(movimiento is not None)
        self.campo_observacion_movimiento.setText((movimiento["Observacion"] or "") if movimiento else "")

    def _guardar_observacion_movimiento(self) -> None:
        movimiento = self._movimiento_seleccionado()
        if movimiento is None:
            return
        texto = self.campo_observacion_movimiento.text().strip() or None
        if texto == (movimiento["Observacion"] or None):
            return
        obtener_repositorio(self.conn, "LlaveMovimiento").actualizar(movimiento["IdMovimiento"], Observacion=texto)
        self.conn.commit()

    def _asignacion_abierta_seleccionada(self) -> bool:
        movimiento = self._movimiento_seleccionado()
        return (
            movimiento is not None and movimiento["Tipo"] == "Asignación"
            and movimiento["IdMovimiento"] not in self._asignaciones_cerradas()
        )

    def _actualizar_botones_movimiento(self) -> None:
        es_asignacion_abierta = self._asignacion_abierta_seleccionada()
        self.boton_devolver.setEnabled(es_asignacion_abierta)
        tipo = self._tipo_seleccionado()
        # "Registrar pérdida…" cubre dos casos: cerrar la asignación abierta
        # seleccionada, o (sin ninguna seleccionada) dar de baja stock
        # disponible del Tipo seleccionado que se perdió antes de asignarse.
        disponibles_tipo = resumen_stock(self.conn, tipo["IdLlave"])["disponibles"] if tipo else 0
        self.boton_perdida.setEnabled(es_asignacion_abierta or disponibles_tipo > 0)

    def _cargo_especial_creado(self, id_llave: int, cargos_antes: set[int]) -> sqlite3.Row | None:
        """El depósito/reintegro genera como mucho un CargoEspecial nuevo
        por acción — se detecta por diferencia de conjunto en vez de
        duplicar acá la condición exacta que usa asignar_llave/
        devolver_llave para decidir si correspondía crear uno."""
        return next(
            (c for c in obtener_repositorio(self.conn, "CargoEspecial").listar(IdLlave=id_llave)
             if c["IdCargo"] not in cargos_antes),
            None,
        )

    def _ingresar_copia(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            QMessageBox.information(self, "Ingresar copia", "Seleccioná un Tipo de llave.")
            return
        dialogo = _DialogoIngreso(tipo, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        id_movimiento = ingresar_copias(self.conn, id_llave=tipo["IdLlave"], **dialogo.valores())
        self.conn.commit()
        self._marcar_ultimo({"tipo": "ingreso", "id_movimiento": id_movimiento})
        self._actualizar_tipos()
        self._actualizar_movimientos()
        self.boton_nuevo_tipo.setFocus()

    def _asignar(self) -> None:
        tipo = self._tipo_seleccionado()
        if tipo is None:
            QMessageBox.information(self, "Asignar", "Seleccioná un Tipo de llave.")
            return
        disponibles = resumen_stock(self.conn, tipo["IdLlave"])["disponibles"]
        if disponibles <= 0:
            QMessageBox.warning(self, "Asignar", f"No hay copias disponibles de {tipo['Nombre']} para asignar.")
            return
        dialogo = _DialogoAsignar(self.conn, tipo, disponibles, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        cargos_antes = {c["IdCargo"] for c in obtener_repositorio(self.conn, "CargoEspecial").listar(IdLlave=tipo["IdLlave"])}
        try:
            id_movimiento = asignar_llave(self.conn, id_llave=tipo["IdLlave"], **dialogo.valores())
        except ValueError as error:
            QMessageBox.warning(self, "Asignar", str(error))
            return
        self.conn.commit()
        cargo_nuevo = self._cargo_especial_creado(tipo["IdLlave"], cargos_antes)
        self._marcar_ultimo({
            "tipo": "asignacion", "id_movimiento": id_movimiento,
            "id_cargo_especial": cargo_nuevo["IdCargo"] if cargo_nuevo else None,
        })
        self._actualizar_tipos()
        self._actualizar_movimientos()
        self.boton_nuevo_tipo.setFocus()

    def _registrar_devolucion(self) -> None:
        movimiento = self._movimiento_seleccionado()
        if movimiento is None:
            return
        dialogo = _DialogoDevolucion(movimiento, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        cargos_antes = {c["IdCargo"] for c in obtener_repositorio(self.conn, "CargoEspecial").listar(IdLlave=movimiento["IdLlave"])}
        try:
            id_devolucion = devolver_llave(self.conn, movimiento["IdMovimiento"], **dialogo.valores())
        except ValueError as error:
            QMessageBox.warning(self, "Registrar devolución", str(error))
            return
        self.conn.commit()
        cargo_nuevo = self._cargo_especial_creado(movimiento["IdLlave"], cargos_antes)
        self._marcar_ultimo({
            "tipo": "devolucion", "id_movimiento": id_devolucion,
            "id_cargo_especial": cargo_nuevo["IdCargo"] if cargo_nuevo else None,
        })
        self._actualizar_tipos()
        self._actualizar_movimientos()
        self.boton_nuevo_tipo.setFocus()

    def _registrar_perdida(self) -> None:
        if self._asignacion_abierta_seleccionada():
            movimiento = self._movimiento_seleccionado()
            dialogo = _DialogoPerdida(movimiento, self)
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                id_perdida = registrar_perdida(
                    self.conn, id_asignacion=movimiento["IdMovimiento"], **dialogo.valores(),
                )
            except ValueError as error:
                QMessageBox.warning(self, "Registrar pérdida", str(error))
                return
        else:
            tipo = self._tipo_seleccionado()
            if tipo is None:
                QMessageBox.information(
                    self, "Registrar pérdida", "Seleccioná una asignación abierta o un Tipo de llave.",
                )
                return
            disponibles = resumen_stock(self.conn, tipo["IdLlave"])["disponibles"]
            if disponibles <= 0:
                QMessageBox.warning(
                    self, "Registrar pérdida", f"No hay copias disponibles de {tipo['Nombre']} para dar de baja.",
                )
                return
            dialogo = _DialogoPerdidaStock(tipo, disponibles, self)
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                id_perdida = registrar_perdida(self.conn, id_llave=tipo["IdLlave"], **dialogo.valores())
            except ValueError as error:
                QMessageBox.warning(self, "Registrar pérdida", str(error))
                return
        self.conn.commit()
        self._marcar_ultimo({"tipo": "perdida", "id_movimiento": id_perdida})
        self._actualizar_tipos()
        self._actualizar_movimientos()
        self.boton_nuevo_tipo.setFocus()

    # -------------------------------------------------- deshacer (genérico)

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
            "Tipo de llave, acceso, ingreso, asignación, devolución o pérdida), incluido cualquier cargo "
            "especial que haya generado. ¿Confirmás?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        movimiento = self._ultimo
        tipo = movimiento["tipo"]
        if tipo == "crear_tipo":
            obtener_repositorio(self.conn, "Llave").eliminar(movimiento["id_llave"])
        elif tipo == "editar_tipo":
            obtener_repositorio(self.conn, "Llave").actualizar(movimiento["id_llave"], **movimiento["valores_previos"])
        elif tipo == "eliminar_tipo":
            obtener_repositorio(self.conn, "Llave").crear(**movimiento["valores_previos"])
        elif tipo == "agregar_acceso":
            obtener_repositorio(self.conn, "LlaveAcceso").eliminar(movimiento["id_acceso"])
        elif tipo == "eliminar_acceso":
            obtener_repositorio(self.conn, "LlaveAcceso").crear(**movimiento["valores_previos"])
        elif tipo in ("ingreso", "perdida"):
            obtener_repositorio(self.conn, "LlaveMovimiento").eliminar(movimiento["id_movimiento"])
        elif tipo in ("asignacion", "devolucion"):
            obtener_repositorio(self.conn, "LlaveMovimiento").eliminar(movimiento["id_movimiento"])
            if movimiento["id_cargo_especial"] is not None:
                obtener_repositorio(self.conn, "CargoEspecial").eliminar(movimiento["id_cargo_especial"])

        self._ultimo = None
        self.boton_deshacer.setEnabled(False)
        self.conn.commit()
        self.actualizar()
        self.boton_nuevo_tipo.setFocus()


class _DialogoTipo(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None, registro: sqlite3.Row | None = None):
        super().__init__(parent)
        self.conn = conn
        self.registro = registro
        self.setWindowTitle("Editar Tipo de llave" if registro else "Nuevo Tipo de llave")
        layout = QFormLayout(self)

        self.combo_tipo = QComboBox()
        for valor, etiqueta in opciones_lista("TipoLlave")(conn):
            self.combo_tipo.addItem(etiqueta, valor)
        self.etiqueta_nombre = QLabel()
        if registro is None:
            self.combo_tipo.currentIndexChanged.connect(self._actualizar_previsualizacion)
        else:
            indice = self.combo_tipo.findData(registro["Tipo"])
            if indice >= 0:
                self.combo_tipo.setCurrentIndex(indice)
            self.combo_tipo.setEnabled(False)
            self.etiqueta_nombre.setText(registro["Nombre"])
            self.etiqueta_nombre.setStyleSheet("font-weight: bold;")
        layout.addRow("Tipo", self.combo_tipo)
        layout.addRow("Nombre del tipo de llave", self.etiqueta_nombre)
        if registro is not None:
            ayuda = QLabel("No se puede cambiar: si cambia, el nombre dejaría de tener sentido.")
            ayuda.setStyleSheet("color: #666; font-size: 11px;")
            layout.addRow("", ayuda)

        self.spin_deposito = QDoubleSpinBox()
        self.spin_deposito.setMaximum(10_000_000)
        self.spin_deposito.setValue(registro["ValorDepositoActual"] if registro else 0)
        layout.addRow("Depósito actual", self.spin_deposito)

        self.campo_observacion = QLineEdit(registro["Observacion"] if registro and registro["Observacion"] else "")
        layout.addRow("Observación", self.campo_observacion)

        self.casilla_activo = QCheckBox("Activo")
        self.casilla_activo.setChecked(bool(registro["Activo"]) if registro else True)
        layout.addRow(self.casilla_activo)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        orden = [self.combo_tipo, self.spin_deposito, self.campo_observacion, self.casilla_activo, boton_ok, boton_cancelar]
        self._foco = instalar_enter_avanza_foco(orden, parent=self)
        if registro is None:
            self._actualizar_previsualizacion()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.combo_tipo.setFocus()

    def _actualizar_previsualizacion(self) -> None:
        tipo = self.combo_tipo.currentData()
        self.etiqueta_nombre.setText(f"Se va a llamar: {siguiente_nombre_llave(self.conn, tipo)}")

    def valores(self) -> dict:
        return {
            "tipo": self.combo_tipo.currentData(),
            "valor_deposito_actual": self.spin_deposito.value(),
            "observacion": self.campo_observacion.text().strip() or None,
            "activo": self.casilla_activo.isChecked(),
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

        self.campo_nombre = QLineEdit()
        self.campo_nombre.setPlaceholderText("Nombre del acceso (opcional)")
        layout.addRow("Nombre", self.campo_nombre)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.combo_edificio, self.combo_unidad, self.campo_nombre, boton_ok, boton_cancelar], parent=self,
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
            "nombre": self.campo_nombre.text().strip() or None,
        }


class _DialogoIngreso(QDialog):
    def __init__(self, tipo: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ingresar copia")
        layout = QFormLayout(self)
        layout.addRow(QLabel(tipo["Nombre"]))

        self.campo_fecha = _fecha_edit()
        layout.addRow("Fecha", self.campo_fecha)

        self.spin_cantidad = QSpinBox()
        self.spin_cantidad.setMinimum(1)
        self.spin_cantidad.setMaximum(500)
        self.spin_cantidad.setValue(1)
        layout.addRow("Cantidad", self.spin_cantidad)
        ayuda = QLabel("Se cargan esa cantidad de copias de una sola vez.")
        ayuda.setStyleSheet("color: #666; font-size: 11px;")
        layout.addRow("", ayuda)

        self.campo_observacion = QLineEdit()
        layout.addRow("Comentarios", self.campo_observacion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.campo_fecha, self.spin_cantidad, self.campo_observacion, boton_ok, boton_cancelar], parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.campo_fecha.setFocus()

    def valores(self) -> dict:
        return {
            "cantidad": self.spin_cantidad.value(),
            "fecha": self.campo_fecha.date().toString(Qt.DateFormat.ISODate),
            "observacion": self.campo_observacion.text().strip() or None,
        }


class _DialogoAsignar(QDialog):
    def __init__(self, conn: sqlite3.Connection, tipo: sqlite3.Row, disponibles: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Asignar")
        layout = QFormLayout(self)
        copia_o_copias = "copia disponible" if disponibles == 1 else "copias disponibles"
        layout.addRow(QLabel(f"{tipo['Nombre']}  —  {disponibles} {copia_o_copias}"))

        self.combo_profesional = QComboBox()
        for id_, etiqueta in _opciones_profesional(conn, _CATEGORIAS_TODAS):
            self.combo_profesional.addItem(etiqueta, id_)
        layout.addRow("Profesional", self.combo_profesional)

        self.campo_fecha = _fecha_edit()
        layout.addRow("Fecha", self.campo_fecha)

        self.casilla_deposito = QCheckBox("Cobrar depósito")
        layout.addRow(self.casilla_deposito)
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMaximum(10_000_000)
        self.spin_monto.setValue(tipo["ValorDepositoActual"] or 0)
        layout.addRow("Monto cobrado", self.spin_monto)

        self.campo_observacion = QLineEdit()
        layout.addRow("Observación", self.campo_observacion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco([
            self.combo_profesional, self.campo_fecha, self.casilla_deposito, self.spin_monto,
            self.campo_observacion, boton_ok, boton_cancelar,
        ], parent=self)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.combo_profesional.setFocus()

    def valores(self) -> dict:
        return {
            "id_profesional": self.combo_profesional.currentData(),
            "fecha": self.campo_fecha.date().toString(Qt.DateFormat.ISODate),
            "cobrar_deposito": self.casilla_deposito.isChecked(),
            "monto_cobrado": self.spin_monto.value() or None,
            "observacion": self.campo_observacion.text().strip() or None,
        }


class _DialogoDevolucion(QDialog):
    def __init__(self, movimiento: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar devolución")
        layout = QFormLayout(self)
        layout.addRow(QLabel(f"{movimiento['_nombre_llave']}  —  {movimiento['_texto_profesional']}"))

        self.campo_fecha = _fecha_edit()
        layout.addRow("Fecha", self.campo_fecha)

        self.casilla_reintegro = QCheckBox("Reintegrar depósito")
        self.casilla_reintegro.setChecked(bool(movimiento["DepositoCobrado"]))
        layout.addRow(self.casilla_reintegro)
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMaximum(10_000_000)
        self.spin_monto.setValue(movimiento["MontoCobrado"] or 0)
        layout.addRow("Monto a reintegrar", self.spin_monto)

        self.campo_observacion = QLineEdit()
        layout.addRow("Observación", self.campo_observacion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.campo_fecha, self.casilla_reintegro, self.spin_monto, self.campo_observacion, boton_ok, boton_cancelar],
            parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.campo_fecha.setFocus()

    def valores(self) -> dict:
        return {
            "fecha": self.campo_fecha.date().toString(Qt.DateFormat.ISODate),
            "reintegrar_deposito": self.casilla_reintegro.isChecked(),
            "monto_reintegrado": self.spin_monto.value() or None,
            "observacion": self.campo_observacion.text().strip() or None,
        }


class _DialogoPerdida(QDialog):
    def __init__(self, movimiento: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar pérdida")
        layout = QFormLayout(self)
        layout.addRow(QLabel(f"{movimiento['_nombre_llave']}  —  {movimiento['_texto_profesional']}"))

        if movimiento["DepositoCobrado"]:
            aviso = QLabel(
                f"El depósito cobrado ({_moneda(movimiento['MontoCobrado'] or 0)}) queda perdido, no se "
                "reintegra.\nSi le da una copia nueva, va a tener que abonar el depósito de nuevo."
            )
        else:
            aviso = QLabel("Esta asignación no tenía depósito cobrado.")
        aviso.setStyleSheet("color: #a33;")
        layout.addRow(aviso)

        self.campo_fecha = _fecha_edit()
        layout.addRow("Fecha", self.campo_fecha)

        self.campo_observacion = QLineEdit()
        layout.addRow("Observación", self.campo_observacion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.campo_fecha, self.campo_observacion, boton_ok, boton_cancelar], parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.campo_fecha.setFocus()

    def valores(self) -> dict:
        return {
            "fecha": self.campo_fecha.date().toString(Qt.DateFormat.ISODate),
            "observacion": self.campo_observacion.text().strip() or None,
        }


class _DialogoPerdidaStock(QDialog):
    """Pérdida de copias que todavía estaban en stock, sin asignar a
    ningún profesional (ej. se traspapelan en el cajón) — a diferencia de
    _DialogoPerdida, acá no hay depósito ni profesional involucrado."""

    def __init__(self, tipo: sqlite3.Row, disponibles: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar pérdida")
        layout = QFormLayout(self)
        copia_o_copias = "copia disponible" if disponibles == 1 else "copias disponibles"
        layout.addRow(QLabel(f"{tipo['Nombre']}  —  {disponibles} {copia_o_copias}, sin asignar"))

        self.campo_fecha = _fecha_edit()
        layout.addRow("Fecha", self.campo_fecha)

        self.spin_cantidad = QSpinBox()
        self.spin_cantidad.setMinimum(1)
        self.spin_cantidad.setMaximum(disponibles)
        self.spin_cantidad.setValue(1)
        layout.addRow("Cantidad", self.spin_cantidad)

        self.campo_observacion = QLineEdit()
        layout.addRow("Observación", self.campo_observacion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco(
            [self.campo_fecha, self.spin_cantidad, self.campo_observacion, boton_ok, boton_cancelar], parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.campo_fecha.setFocus()

    def valores(self) -> dict:
        return {
            "cantidad": self.spin_cantidad.value(),
            "fecha": self.campo_fecha.date().toString(Qt.DateFormat.ISODate),
            "observacion": self.campo_observacion.text().strip() or None,
        }
