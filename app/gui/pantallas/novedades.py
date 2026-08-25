"""Novedades por profesional (secciones 3.12-3.15): Vacaciones, Licencias,
Ausencias y Cargos especiales en pestañas. Son registros históricos que
alimentan el cálculo de la liquidación (Etapa 4) — el alta reusa siempre
las funciones de negocio (crear_vacacion/crear_licencia/crear_ausencia/
crear_cargo_especial) para no perderse los valores derivados (bonificado,
cupo consumido, etc.) que esas funciones calculan; no se edita ni borra
desde acá, son historial."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.dialogos import confirmar_si_periodo_imputado_es_anterior
from app.gui.widgets.grilla_operativa import GrillaOperativaWidget
from app.negocio.ausencias import cancelar_ausencia, crear_ausencia
from app.negocio.dias import periodo_actual
from app.negocio.licencias import cancelar_licencia, crear_licencia
from app.negocio.liquidaciones import regenerar_si_corresponde
from app.negocio.listas_editables import valores_lista
from app.negocio.pagos import TIPOS_CARGO, crear_cargo_especial
from app.negocio.vacaciones import cancelar_vacacion, crear_vacacion
from app.repositorio.registro import obtener_repositorio


def _combo_profesionales(conn: sqlite3.Connection) -> QComboBox:
    combo = QComboBox()
    for f in conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido"):
        combo.addItem(f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", "), f["IdProfesional"])
    return combo


def _nombre_profesional(cache: dict[int, sqlite3.Row], id_profesional: int) -> str:
    p = cache.get(id_profesional)
    return p["Apellido"] if p else "?"


def _unidades_del_profesional(conn: sqlite3.Connection, id_profesional: int | None) -> list[int]:
    """Unidades donde el profesional ya tiene alguna reserva regular —
    con eso alcanza para acotar la vista previa de la grilla en
    Vacaciones/Licencias/Ausencias, que no reservan un consultorio
    puntual sino que afectan a todo lo que el profesional ya tiene
    reservado."""
    if id_profesional is None:
        return []
    filas = conn.execute(
        "SELECT DISTINCT u.IdUnidad FROM ReservaRegular r "
        "JOIN Consultorio c ON c.IdConsultorio = r.IdConsultorio "
        "JOIN Unidad u ON u.IdUnidad = c.IdUnidad WHERE r.IdProfesional = ?",
        (id_profesional,),
    ).fetchall()
    return [f["IdUnidad"] for f in filas]


class PantallaNovedades(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Novedades")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        pestanas = QTabWidget()
        self.panel_vacaciones = _PanelVacaciones(conn)
        self.panel_licencias = _PanelLicencias(conn)
        self.panel_ausencias = _PanelAusencias(conn)
        self.panel_cargos = _PanelCargosEspeciales(conn)
        pestanas.addTab(self.panel_vacaciones, "Vacaciones")
        pestanas.addTab(self.panel_licencias, "Licencias")
        pestanas.addTab(self.panel_ausencias, "Ausencias")
        pestanas.addTab(self.panel_cargos, "Cargos especiales")
        layout.addWidget(pestanas, stretch=1)

    def actualizar(self) -> None:
        for panel in (self.panel_vacaciones, self.panel_licencias, self.panel_ausencias, self.panel_cargos):
            panel.actualizar()


class _PanelVacaciones(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._registros: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        self.combo_profesional = _combo_profesionales(self.conn)
        self.combo_profesional.currentIndexChanged.connect(self._sincronizar_grilla)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)
        self.campo_desde = QLineEdit()
        self.campo_desde.setPlaceholderText("AAAA-MM-DD")
        form.addWidget(QLabel("Desde"))
        form.addWidget(self.campo_desde)
        self.campo_hasta = QLineEdit()
        self.campo_hasta.setPlaceholderText("AAAA-MM-DD")
        form.addWidget(QLabel("Hasta"))
        form.addWidget(self.campo_hasta)
        boton = QPushButton("Crear vacación")
        boton.setObjectName("botonPrimario")
        boton.clicked.connect(self._crear)
        form.addWidget(boton)
        boton_cancelar = QPushButton("Anular vacación seleccionada")
        boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(boton_cancelar)
        form.addStretch()
        splitter.addWidget(panel_form)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["Profesional", "Desde", "Hasta", "Valor bonificado", "Cupo restante %"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        splitter.addWidget(self.tabla)

        grupo_grilla = QGroupBox("Vista previa: grilla operativa")
        layout_grupo_grilla = QVBoxLayout(grupo_grilla)
        self.grilla = GrillaOperativaWidget(self.conn)
        layout_grupo_grilla.addWidget(self.grilla)
        splitter.addWidget(grupo_grilla)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)
        layout.addWidget(splitter)
        self._sincronizar_grilla()

    def _sincronizar_grilla(self) -> None:
        """La vista previa muestra el horario regular del profesional
        elegido — acotada a las unidades donde ya tiene algo reservado, y
        con su propia reserva pintada de azul."""
        id_profesional = self.combo_profesional.currentData()
        self.grilla.filtrar_por_unidades(_unidades_del_profesional(self.conn, id_profesional))
        self.grilla.filtrar_por_profesional(id_profesional)

    def actualizar(self) -> None:
        self._registros = obtener_repositorio(self.conn, "Vacacion").listar()
        cache = {p["IdProfesional"]: p for p in obtener_repositorio(self.conn, "Profesional").listar()}
        self.tabla.setRowCount(len(self._registros))
        for i, r in enumerate(self._registros):
            self.tabla.setItem(i, 0, QTableWidgetItem(_nombre_profesional(cache, r["IdProfesional"])))
            self.tabla.setItem(i, 1, QTableWidgetItem(r["FechaDesde"]))
            self.tabla.setItem(i, 2, QTableWidgetItem(r["FechaHasta"]))
            valor = r["ValorBonificado"]
            self.tabla.setItem(i, 3, QTableWidgetItem(f"$ {valor:,.2f}" if valor is not None else ""))
            cupo = r["CupoRestantePorcentaje"]
            self.tabla.setItem(i, 4, QTableWidgetItem(f"{cupo:.1f}%" if cupo is not None else ""))
        self.tabla.resizeColumnsToContents()
        self.grilla.actualizar()

    def _crear(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        try:
            _id, advertencias = crear_vacacion(
                self.conn, id_profesional=id_profesional,
                fecha_desde=self.campo_desde.text().strip(), fecha_hasta=self.campo_hasta.text().strip(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Crear vacación", str(error))
            return
        self.conn.commit()
        if advertencias:
            QMessageBox.information(self, "Vacación creada", "\n".join(advertencias))
        regenerar_si_corresponde(self.conn, id_profesional=id_profesional, periodo=periodo_actual(self.conn))
        self.conn.commit()
        self.actualizar()

    def _cancelar(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return
        registro = self._registros[filas[0].row()]
        try:
            cancelar_vacacion(self.conn, registro["IdVacacion"])
        except ValueError as error:
            QMessageBox.warning(self, "Anular vacación", str(error))
            return
        self.conn.commit()
        regenerar_si_corresponde(
            self.conn, id_profesional=registro["IdProfesional"], periodo=periodo_actual(self.conn),
        )
        self.conn.commit()
        self.actualizar()


class _PanelLicencias(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._registros: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        self.combo_profesional = _combo_profesionales(self.conn)
        self.combo_profesional.currentIndexChanged.connect(self._sincronizar_grilla)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_tipo = QComboBox()
        for t in obtener_repositorio(self.conn, "TipoLicencia").listar(Activo=1):
            self.combo_tipo.addItem(t["Nombre"], t["IdTipoLicencia"])
        self.combo_tipo.currentIndexChanged.connect(self._precargar_porcentaje)
        form.addWidget(QLabel("Tipo de licencia"))
        form.addWidget(self.combo_tipo)

        self.spin_porcentaje = QDoubleSpinBox()
        self.spin_porcentaje.setRange(0, 100)
        self.spin_porcentaje.setSuffix(" %")
        form.addWidget(QLabel("% de bonificación (editable caso por caso)"))
        form.addWidget(self.spin_porcentaje)
        self._precargar_porcentaje()

        self.campo_desde = QLineEdit()
        self.campo_desde.setPlaceholderText("AAAA-MM-DD")
        form.addWidget(QLabel("Desde"))
        form.addWidget(self.campo_desde)
        self.campo_hasta = QLineEdit()
        self.campo_hasta.setPlaceholderText("AAAA-MM-DD (vacío si el tipo la calcula sola)")
        form.addWidget(QLabel("Hasta"))
        form.addWidget(self.campo_hasta)
        boton = QPushButton("Crear licencia")
        boton.setObjectName("botonPrimario")
        boton.clicked.connect(self._crear)
        form.addWidget(boton)
        boton_cancelar = QPushButton("Anular licencia seleccionada")
        boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(boton_cancelar)
        form.addStretch()
        splitter.addWidget(panel_form)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["Profesional", "Tipo", "Desde", "Hasta", "Valor bonificado"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        splitter.addWidget(self.tabla)

        grupo_grilla = QGroupBox("Vista previa: grilla operativa")
        layout_grupo_grilla = QVBoxLayout(grupo_grilla)
        self.grilla = GrillaOperativaWidget(self.conn)
        layout_grupo_grilla.addWidget(self.grilla)
        splitter.addWidget(grupo_grilla)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)
        layout.addWidget(splitter)
        self._sincronizar_grilla()

    def _sincronizar_grilla(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        self.grilla.filtrar_por_unidades(_unidades_del_profesional(self.conn, id_profesional))
        self.grilla.filtrar_por_profesional(id_profesional)

    def _precargar_porcentaje(self) -> None:
        id_tipo = self.combo_tipo.currentData()
        tipo = obtener_repositorio(self.conn, "TipoLicencia").obtener(id_tipo) if id_tipo is not None else None
        self.spin_porcentaje.setValue(tipo["PorcentajeBonificacion"] if tipo else 0)

    def actualizar(self) -> None:
        self._registros = obtener_repositorio(self.conn, "Licencia").listar()
        cache_prof = {p["IdProfesional"]: p for p in obtener_repositorio(self.conn, "Profesional").listar()}
        cache_tipo = {t["IdTipoLicencia"]: t for t in obtener_repositorio(self.conn, "TipoLicencia").listar()}
        self.tabla.setRowCount(len(self._registros))
        for i, r in enumerate(self._registros):
            self.tabla.setItem(i, 0, QTableWidgetItem(_nombre_profesional(cache_prof, r["IdProfesional"])))
            tipo = cache_tipo.get(r["IdTipoLicencia"])
            self.tabla.setItem(i, 1, QTableWidgetItem(tipo["Nombre"] if tipo else "?"))
            self.tabla.setItem(i, 2, QTableWidgetItem(r["FechaDesde"]))
            self.tabla.setItem(i, 3, QTableWidgetItem(r["FechaHasta"]))
            valor = r["ValorBonificado"]
            self.tabla.setItem(i, 4, QTableWidgetItem(f"$ {valor:,.2f}" if valor is not None else ""))
        self.tabla.resizeColumnsToContents()
        self.grilla.actualizar()

    def _crear(self) -> None:
        id_tipo = self.combo_tipo.currentData()
        if id_tipo is None:
            QMessageBox.warning(self, "Crear licencia", "Primero hay que cargar un tipo de licencia.")
            return
        try:
            _id, advertencias = crear_licencia(
                self.conn, id_profesional=self.combo_profesional.currentData(), id_tipo_licencia=id_tipo,
                fecha_desde=self.campo_desde.text().strip(), fecha_hasta=self.campo_hasta.text().strip() or None,
                porcentaje_bonificacion=self.spin_porcentaje.value(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Crear licencia", str(error))
            return
        self.conn.commit()
        if advertencias:
            QMessageBox.information(self, "Licencia creada", "\n".join(advertencias))
        self.actualizar()

    def _cancelar(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return
        registro = self._registros[filas[0].row()]
        try:
            cancelar_licencia(self.conn, registro["IdLicencia"])
        except ValueError as error:
            QMessageBox.warning(self, "Anular licencia", str(error))
            return
        self.conn.commit()
        self.actualizar()


class _PanelAusencias(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._registros: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        self.combo_profesional = _combo_profesionales(self.conn)
        self.combo_profesional.currentIndexChanged.connect(self._sincronizar_grilla)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.campo_desde = QLineEdit()
        self.campo_desde.setPlaceholderText("AAAA-MM-DD")
        form.addWidget(QLabel("Desde"))
        form.addWidget(self.campo_desde)
        self.campo_hasta = QLineEdit()
        self.campo_hasta.setPlaceholderText("AAAA-MM-DD")
        form.addWidget(QLabel("Hasta"))
        form.addWidget(self.campo_hasta)
        self.combo_motivo = QComboBox()
        self.combo_motivo.setEditable(True)
        for valor in valores_lista(self.conn, "MotivoAusencia"):
            self.combo_motivo.addItem(valor)
        form.addWidget(QLabel("Motivo"))
        form.addWidget(self.combo_motivo)
        boton = QPushButton("Crear ausencia")
        boton.setObjectName("botonPrimario")
        boton.clicked.connect(self._crear)
        form.addWidget(boton)
        boton_cancelar = QPushButton("Anular ausencia seleccionada")
        boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(boton_cancelar)
        form.addStretch()
        splitter.addWidget(panel_form)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Profesional", "Desde", "Hasta", "Motivo"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        splitter.addWidget(self.tabla)

        grupo_grilla = QGroupBox("Vista previa: grilla operativa")
        layout_grupo_grilla = QVBoxLayout(grupo_grilla)
        self.grilla = GrillaOperativaWidget(self.conn)
        layout_grupo_grilla.addWidget(self.grilla)
        splitter.addWidget(grupo_grilla)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)
        layout.addWidget(splitter)
        self._sincronizar_grilla()

    def _sincronizar_grilla(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        self.grilla.filtrar_por_unidades(_unidades_del_profesional(self.conn, id_profesional))
        self.grilla.filtrar_por_profesional(id_profesional)

    def actualizar(self) -> None:
        self._registros = obtener_repositorio(self.conn, "Ausencia").listar()
        cache = {p["IdProfesional"]: p for p in obtener_repositorio(self.conn, "Profesional").listar()}
        self.tabla.setRowCount(len(self._registros))
        for i, r in enumerate(self._registros):
            self.tabla.setItem(i, 0, QTableWidgetItem(_nombre_profesional(cache, r["IdProfesional"])))
            self.tabla.setItem(i, 1, QTableWidgetItem(r["FechaDesde"]))
            self.tabla.setItem(i, 2, QTableWidgetItem(r["FechaHasta"]))
            self.tabla.setItem(i, 3, QTableWidgetItem(r["Motivo"] or ""))
        self.tabla.resizeColumnsToContents()
        self.grilla.actualizar()

    def _crear(self) -> None:
        try:
            crear_ausencia(
                self.conn, id_profesional=self.combo_profesional.currentData(),
                fecha_desde=self.campo_desde.text().strip(), fecha_hasta=self.campo_hasta.text().strip(),
                motivo=self.combo_motivo.currentText().strip() or None,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Crear ausencia", str(error))
            return
        self.conn.commit()
        self.actualizar()

    def _cancelar(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return
        registro = self._registros[filas[0].row()]
        try:
            cancelar_ausencia(self.conn, registro["IdAusencia"])
        except ValueError as error:
            QMessageBox.warning(self, "Anular ausencia", str(error))
            return
        self.conn.commit()
        self.actualizar()


class _PanelCargosEspeciales(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        self.combo_profesional = _combo_profesionales(self.conn)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_tipo = QComboBox()
        for t in TIPOS_CARGO:
            self.combo_tipo.addItem(t, t)
        form.addWidget(QLabel("Tipo"))
        form.addWidget(self.combo_tipo)

        self.campo_concepto = QLineEdit()
        form.addWidget(QLabel("Concepto"))
        form.addWidget(self.campo_concepto)

        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMaximum(100_000_000)
        form.addWidget(QLabel("Monto"))
        form.addWidget(self.spin_monto)

        self.campo_periodo = QLineEdit()
        self.campo_periodo.setPlaceholderText("AAAA-MM (opcional)")
        form.addWidget(QLabel("Período imputado"))
        form.addWidget(self.campo_periodo)

        boton = QPushButton("Crear cargo especial")
        boton.setObjectName("botonPrimario")
        boton.clicked.connect(self._crear)
        form.addWidget(boton)
        form.addStretch()
        splitter.addWidget(panel_form)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["Profesional", "Tipo", "Concepto", "Monto", "Período"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.tabla)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    def actualizar(self) -> None:
        registros = obtener_repositorio(self.conn, "CargoEspecial").listar()
        cache = {p["IdProfesional"]: p for p in obtener_repositorio(self.conn, "Profesional").listar()}
        self.tabla.setRowCount(len(registros))
        for i, r in enumerate(registros):
            self.tabla.setItem(i, 0, QTableWidgetItem(_nombre_profesional(cache, r["IdProfesional"])))
            self.tabla.setItem(i, 1, QTableWidgetItem(r["Tipo"]))
            self.tabla.setItem(i, 2, QTableWidgetItem(r["Concepto"]))
            self.tabla.setItem(i, 3, QTableWidgetItem(f"$ {r['Monto']:,.2f}"))
            self.tabla.setItem(i, 4, QTableWidgetItem(r["PeriodoImputado"] or ""))
        self.tabla.resizeColumnsToContents()

    def _crear(self) -> None:
        concepto = self.campo_concepto.text().strip()
        if not concepto:
            QMessageBox.warning(self, "Crear cargo especial", "El concepto es obligatorio.")
            return
        periodo_imputado = self.campo_periodo.text().strip() or None
        if not confirmar_si_periodo_imputado_es_anterior(self, self.conn, periodo_imputado):
            return
        try:
            crear_cargo_especial(
                self.conn, id_profesional=self.combo_profesional.currentData(), tipo=self.combo_tipo.currentData(),
                concepto=concepto, monto=self.spin_monto.value(),
                periodo_imputado=periodo_imputado,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Crear cargo especial", str(error))
            return
        self.conn.commit()
        self.actualizar()
