"""Registro de ausencias por profesional (secciones 3.12-3.14): Vacaciones,
Licencias y Ausencias en pestañas — plazos por inactividad únicamente. Los
Cargos especiales (sección 3.15) viven en su propia pantalla
(`PantallaCargosEspeciales`, más abajo), porque no son un plazo de
inactividad. Son registros históricos que alimentan el cálculo de la
liquidación (Etapa 4) — el alta reusa siempre las funciones de negocio
(crear_vacacion/crear_licencia/crear_ausencia/crear_cargo_especial) para no
perderse los valores derivados (bonificado, cupo consumido, etc.) que esas
funciones calculan; no se edita ni borra desde acá, son historial."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.dialogos import confirmar_si_periodo_imputado_es_anterior
from app.gui.pantallas.reservas import _SpinHorario, _fmt_horario, _opciones_profesional, _texto_profesional
from app.gui.widgets.grilla_operativa import (
    GrillaOperativaWidget,
    pares_dia_unidad_con_reserva_vigente,
    unidades_con_reserva_vigente,
)
from app.negocio.ausencias import cancelar_ausencia, crear_ausencia
from app.negocio.dias import DIAS_SEMANA, periodo_actual
from app.negocio.licencias import cancelar_licencia, crear_licencia
from app.negocio.liquidaciones import regenerar_si_corresponde
from app.negocio.listas_editables import valores_lista
from app.negocio.pagos import TIPOS_CARGO, crear_cargo_especial
from app.negocio.vacaciones import cancelar_vacacion, crear_vacacion
from app.repositorio.registro import obtener_repositorio

_CATEGORIAS_TODAS = ("R", "A", "B", "E", "X", "C")
_ANCHO_COMBO_PROFESIONAL = 220
_ANCHO_COL_PROFESIONAL = 180


def _combo_profesionales(conn: sqlite3.Connection) -> QComboBox:
    combo = QComboBox()
    for f in conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido"):
        combo.addItem(f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", "), f["IdProfesional"])
    return combo


def _nombre_profesional(cache: dict[int, sqlite3.Row], id_profesional: int) -> str:
    p = cache.get(id_profesional)
    return p["Apellido"] if p else "?"


class PantallaRegistroAusencias(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Registro de ausencias")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        pestanas = QTabWidget()
        self.panel_vacaciones = _PanelVacaciones(conn)
        self.panel_licencias = _PanelLicencias(conn)
        self.panel_ausencias = _PanelAusencias(conn)
        pestanas.addTab(self.panel_vacaciones, "Vacaciones")
        pestanas.addTab(self.panel_licencias, "Licencias")
        pestanas.addTab(self.panel_ausencias, "Ausencias")
        layout.addWidget(pestanas, stretch=1)

    def actualizar(self) -> None:
        for panel in (self.panel_vacaciones, self.panel_licencias, self.panel_ausencias):
            panel.actualizar()


class PantallaCargosEspeciales(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Cargos especiales")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)
        self.panel = _PanelCargosEspeciales(conn)
        layout.addWidget(self.panel, stretch=1)

    def actualizar(self) -> None:
        self.panel.actualizar()


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
        ids_unidad = unidades_con_reserva_vigente(self.conn, id_profesional)
        self.grilla.filtrar_por_unidades(ids_unidad or None)  # sin reservas -> mostrar todas
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
        ids_unidad = unidades_con_reserva_vigente(self.conn, id_profesional)
        self.grilla.filtrar_por_unidades(ids_unidad or None)  # sin reservas -> mostrar todas
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


def _fmt_horario_ausencia(registro: sqlite3.Row) -> str:
    if registro["HoraInicio"] is None or registro["HoraFin"] is None:
        return "Todo el día"
    return _fmt_horario(registro["HoraInicio"], registro["HoraFin"])


class _PanelAusencias(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._registros: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        contenido = QWidget()
        layout = QVBoxLayout(contenido)
        splitter_superior = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        self.combo_profesional = QComboBox()
        self.combo_profesional.setMinimumWidth(_ANCHO_COMBO_PROFESIONAL)
        self.combo_profesional.addItem("Seleccionar profesional…", None)
        for id_, etiqueta in _opciones_profesional(self.conn, _CATEGORIAS_TODAS):
            self.combo_profesional.addItem(etiqueta, id_)
        self.combo_profesional.currentIndexChanged.connect(self._profesional_cambio)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_motivo = QComboBox()
        self.combo_motivo.setEditable(True)
        for valor in valores_lista(self.conn, "MotivoAusencia"):
            self.combo_motivo.addItem(valor)
        form.addWidget(QLabel("Motivo"))
        form.addWidget(self.combo_motivo)

        self.campo_desde = QLineEdit()
        self.campo_desde.setPlaceholderText("AAAA-MM-DD")
        self.campo_desde.editingFinished.connect(self._actualizar_disponibilidad_horario)
        form.addWidget(QLabel("Desde"))
        form.addWidget(self.campo_desde)
        self.campo_hasta = QLineEdit()
        self.campo_hasta.setPlaceholderText("AAAA-MM-DD")
        self.campo_hasta.editingFinished.connect(self._actualizar_disponibilidad_horario)
        form.addWidget(QLabel("Hasta"))
        form.addWidget(self.campo_hasta)

        self.grupo_horario = QGroupBox("Horario puntual (solo si la ausencia es de un único día)")
        self.grupo_horario.setCheckable(True)
        self.grupo_horario.setChecked(False)
        self.grupo_horario.setEnabled(False)
        fila_horario = QHBoxLayout(self.grupo_horario)
        self.spin_hora_desde = _SpinHorario()
        self.spin_hora_desde.setRange(0, 23)
        self.spin_hora_desde.setValue(9)
        self.spin_hora_hasta = _SpinHorario()
        self.spin_hora_hasta.setRange(1, 24)
        self.spin_hora_hasta.setValue(10)
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_hora_desde)
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hora_hasta)
        form.addWidget(self.grupo_horario)

        boton = QPushButton("Crear ausencia")
        boton.setObjectName("botonPrimario")
        boton.clicked.connect(self._crear)
        form.addWidget(boton)
        boton_cancelar = QPushButton("Anular ausencia seleccionada")
        boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(boton_cancelar)
        form.addStretch()
        splitter_superior.addWidget(panel_form)

        grupo_grilla = QGroupBox("Vista previa: grilla operativa")
        layout_grupo_grilla = QVBoxLayout(grupo_grilla)
        self.grilla = GrillaOperativaWidget(self.conn)
        self.grilla.activar_resalte_ausencias(True)
        layout_grupo_grilla.addWidget(self.grilla)
        splitter_superior.addWidget(grupo_grilla)

        splitter_superior.setStretchFactor(0, 0)
        splitter_superior.setStretchFactor(1, 1)
        layout.addWidget(splitter_superior, stretch=2)

        panel_tabla = QGroupBox("Ausencias registradas")
        layout_tabla = QVBoxLayout(panel_tabla)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(["Profesional", "Desde", "Hasta", "Horario", "Motivo", "Origen"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout_tabla.addWidget(self.tabla, stretch=1)
        layout.addWidget(panel_tabla, stretch=1)

        scroll.setWidget(contenido)
        layout_externo.addWidget(scroll)
        self._sincronizar_grilla()

    def _profesional_cambio(self) -> None:
        self._sincronizar_grilla()
        self.actualizar()

    def _actualizar_disponibilidad_horario(self) -> None:
        """El horario puntual solo tiene sentido para una ausencia de un
        único día — se habilita apenas Desde y Hasta coinciden, y se
        vuelve a deshabilitar (destildando) apenas dejan de coincidir."""
        un_solo_dia = bool(self.campo_desde.text().strip()) and self.campo_desde.text().strip() == self.campo_hasta.text().strip()
        self.grupo_horario.setEnabled(un_solo_dia)
        if not un_solo_dia:
            self.grupo_horario.setChecked(False)

    def _sincronizar_grilla(self) -> None:
        """Mismo criterio que la vista previa de Reservas regulares:
        acotada a las unidades (con todos sus consultorios) y a los días
        en los que el profesional ya tiene una reserva regular, con su
        propio horario pintado de azul — y, adicionalmente acá, en verde
        con letra negra donde además tiene una ausencia registrada."""
        id_profesional = self.combo_profesional.currentData()
        pares = pares_dia_unidad_con_reserva_vigente(self.conn, id_profesional)
        ids_unidad = sorted({u for _, u in pares})
        dias = sorted({d for d, _ in pares}, key=DIAS_SEMANA.index)
        self.grilla.filtrar_por_unidades(ids_unidad)
        self.grilla.filtrar_por_dias(dias)
        self.grilla.filtrar_por_pares_unidad_dia(pares)
        self.grilla.filtrar_por_profesional(id_profesional)

    def _origen(self, registro: sqlite3.Row) -> str:
        """En blanco para las que se cargan directamente acá; si vienen
        de "Es reubicación" en Reservas aisladas, queda a la vista de
        cuál reserva puntual surgieron (F16)."""
        if not registro["IdReservaAislada"]:
            return ""
        aislada = obtener_repositorio(self.conn, "ReservaAislada").obtener(registro["IdReservaAislada"])
        if aislada is None:
            return "Reubicación (reserva aislada eliminada)"
        return f"Reubicación (aislada del {aislada['Fecha']})"

    def actualizar(self) -> None:
        """Sin profesional elegido, muestra las ausencias de todos los
        profesionales; con uno elegido, se acota a las de ese profesional
        únicamente. Orden: código del profesional y luego fecha desde."""
        id_profesional_filtro = self.combo_profesional.currentData()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        todas = obtener_repositorio(self.conn, "Ausencia").listar()
        if id_profesional_filtro is not None:
            filtradas = [r for r in todas if r["IdProfesional"] == id_profesional_filtro]
        else:
            filtradas = todas

        filas: list[tuple[sqlite3.Row, sqlite3.Row | None]] = [
            (r, repo_profesional.obtener(r["IdProfesional"])) for r in filtradas
        ]
        filas.sort(key=lambda t: (t[1]["IdCodigo"] or "" if t[1] else "", t[0]["FechaDesde"]))
        self._registros = [t[0] for t in filas]

        self.tabla.setRowCount(len(filas))
        for i, (r, profesional) in enumerate(filas):
            self.tabla.setItem(i, 0, QTableWidgetItem(_texto_profesional(profesional) if profesional else "?"))
            self.tabla.setItem(i, 1, QTableWidgetItem(r["FechaDesde"]))
            self.tabla.setItem(i, 2, QTableWidgetItem(r["FechaHasta"]))
            self.tabla.setItem(i, 3, QTableWidgetItem(_fmt_horario_ausencia(r)))
            self.tabla.setItem(i, 4, QTableWidgetItem(r["Motivo"] or ""))
            self.tabla.setItem(i, 5, QTableWidgetItem(self._origen(r)))
        self.tabla.resizeColumnsToContents()
        self.tabla.setColumnWidth(0, max(self.tabla.columnWidth(0), _ANCHO_COL_PROFESIONAL))
        self.grilla.actualizar()

    def _crear(self) -> None:
        hora_inicio = hora_fin = None
        if self.grupo_horario.isEnabled() and self.grupo_horario.isChecked():
            hora_inicio = self.spin_hora_desde.value()
            hora_fin = self.spin_hora_hasta.value()
        try:
            crear_ausencia(
                self.conn, id_profesional=self.combo_profesional.currentData(),
                fecha_desde=self.campo_desde.text().strip(), fecha_hasta=self.campo_hasta.text().strip(),
                motivo=self.combo_motivo.currentText().strip() or None,
                hora_inicio=hora_inicio, hora_fin=hora_fin,
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
