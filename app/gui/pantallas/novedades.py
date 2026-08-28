"""Registro de ausencias por profesional (secciones 3.12-3.14): Vacaciones,
Licencias y Ausencias en pestañas — plazos por inactividad únicamente. Los
Cargos especiales (sección 3.15) viven en su propia pantalla
(`PantallaCargosEspeciales`, más abajo), porque no son un plazo de
inactividad. Son registros históricos que alimentan el cálculo de la
liquidación (Etapa 4) — el alta reusa siempre las funciones de negocio
(crear_vacacion/crear_licencia/crear_ausencia/crear_cargo_especial) para no
perderse los valores derivados (bonificado, cupo consumido, etc.) que esas
funciones calculan; no se edita ni borra desde acá, son historial.

Números de formulario (revisión uno por uno con la clienta): Vacaciones es
F19 (confirmado). Licencias es F20 — asignado por nosotros en esa revisión,
entre F19 (Vacaciones) y F21 (Pagos), porque no había un número confirmado
para esta pestaña en ningún documento del proyecto; si la planilla original
de la clienta ya le tenía otro número, hay que corregirlo acá. Ausencias
es F27 — también asignado por nosotros (la clienta confirmó que no hace
falta que sea correlativo con Vacaciones/Licencias), lógica y diseño ya
aprobados."""
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.estilos import COLOR_ROJO
from app.gui.pantallas.reservas import (
    _FECHA_SIN_DATO,
    _FORMATO_FECHA,
    _SpinHorario,
    _fmt_fecha,
    _fmt_horario,
    _numero_codigo,
    _opciones_profesional,
    _texto_profesional,
)
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.grilla_operativa import GrillaOperativaWidget, pares_dia_unidad_con_reserva_vigente
from app.gui.widgets.orden_tabla import OrdenTabla
from app.negocio.ausencias import cancelar_ausencia, crear_ausencia
from app.negocio.dias import DIAS_SEMANA, fecha_a_dia_semana, fecha_actual, periodo_actual
from app.negocio.formato import formatear_moneda
from app.negocio.licencias import cancelar_licencia, crear_licencia
from app.negocio.liquidaciones import regenerar_si_corresponde
from app.negocio.listas_editables import valores_lista
from app.negocio.pagos import TIPOS_CARGO, crear_cargo_especial
from app.negocio.vacaciones import cancelar_vacacion, crear_vacacion, cupo_restante_actual
from app.repositorio.registro import obtener_repositorio

_CATEGORIAS_TODAS = ("R", "A", "B", "E", "X", "C")
_ORDEN_CATEGORIA_CARGOS = {"B": 0, "R": 1, "A": 2, "E": 3}
_ANCHO_COMBO_PROFESIONAL = 220
_ANCHO_COL_PROFESIONAL = 180


def _campo_fecha(conn: sqlite3.Connection) -> QDateEdit:
    """QDateEdit con el mismo formato "dd-mm-aaaa" que Reservas, precargado
    con la fecha de hoy."""
    campo = QDateEdit()
    campo.setDisplayFormat(_FORMATO_FECHA)
    campo.setCalendarPopup(True)
    hoy = fecha_actual(conn)
    campo.setDate(QDate(hoy.year, hoy.month, hoy.day))
    return campo


def _campo_fecha_opcional(conn: sqlite3.Connection) -> QDateEdit:
    """Como `_campo_fecha`, pero admite quedar en blanco ("(sin fecha)") —
    mismo sentinel `_FECHA_SIN_DATO` que usa Reservas para Vigencia hasta."""
    campo = _campo_fecha(conn)
    campo.setMinimumDate(_FECHA_SIN_DATO)
    campo.setSpecialValueText("(sin fecha)")
    campo.setDate(_FECHA_SIN_DATO)
    return campo


def _spin_anio(conn: sqlite3.Connection) -> QSpinBox:
    """"Año calendario a imputar": arranca en el año actual, pero se puede
    cambiar libremente a cualquier otro (para consultar años anteriores o
    cargar por adelantado el que viene)."""
    spin = QSpinBox()
    spin.setRange(2000, 2100)
    spin.setValue(fecha_actual(conn).year)
    return spin


def _texto_valor_bonificado(valor: float | None, fecha_desde: str, periodo_en_curso: str) -> str:
    """En blanco para los períodos futuros (posteriores al mes en curso):
    el monto ya está calculado y congelado en la base (así funciona el
    prorrateo mensual de liquidaciones, DC-05 §1.3), pero mostrarlo en la
    lista antes de tiempo podría ser engañoso — los valores de referencia
    de esos meses (aumentos, etc.) todavía pueden no estar definidos."""
    if fecha_desde[:7] > periodo_en_curso:
        return ""
    return f"$ {valor:,.2f}" if valor is not None else ""


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _fmt_fecha_dia(fecha_iso: str) -> str:
    """"Lunes 27-08-2026": día de la semana + fecha, para columnas de
    tablas donde interesa ver de un vistazo qué día se cargó el registro."""
    dia = fecha_a_dia_semana(date.fromisoformat(fecha_iso))
    return f"{dia} {_fmt_fecha(fecha_iso)}"


def _item_monto(valor: float) -> QTableWidgetItem:
    """Importes negativos en rojo, positivos en negro (criterio confirmado
    por la clienta para Cargos especiales; se va a ir extendiendo al resto
    de las pantallas a medida que las revisemos)."""
    item = QTableWidgetItem(formatear_moneda(valor))
    if valor < 0:
        item.setForeground(QColor(COLOR_ROJO))
    return item


class PantallaRegistroAusencias(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Registro de ausencias")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_vacaciones = _PanelVacaciones(conn)
        self.panel_licencias = _PanelLicencias(conn)
        self.panel_ausencias = _PanelAusencias(conn)
        self.pestanas.addTab(self.panel_vacaciones, "Vacaciones")
        self.pestanas.addTab(self.panel_licencias, "Licencias")
        self.pestanas.addTab(self.panel_ausencias, "Ausencias")
        layout.addWidget(self.pestanas, stretch=1)

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

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar":
        el QTabWidget contenedor todavía no está mostrado y se termina
        quedando el foco en su tab bar. Al mostrarse la pestaña (al
        abrir la pantalla o volver a esta solapa) se repite el pedido
        de foco en Profesional, que es cuando realmente surte efecto."""
        super().showEvent(event)
        self._orden.reiniciar()
        self.actualizar()
        self.combo_profesional.setFocus()

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
        self.combo_profesional.addItem("Todos los profesionales", None)
        for id_, etiqueta in _opciones_profesional(self.conn, _CATEGORIAS_TODAS):
            self.combo_profesional.addItem(etiqueta, id_)
        self.combo_profesional.currentIndexChanged.connect(self._profesional_cambio)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.spin_anio = _spin_anio(self.conn)
        self.spin_anio.valueChanged.connect(self._anio_cambio)
        form.addWidget(QLabel("Año calendario a imputar"))
        form.addWidget(self.spin_anio)

        self.campo_desde = _campo_fecha(self.conn)
        form.addWidget(QLabel("Desde"))
        form.addWidget(self.campo_desde)
        self.campo_hasta = _campo_fecha(self.conn)
        form.addWidget(QLabel("Hasta"))
        form.addWidget(self.campo_hasta)

        self.boton_crear = QPushButton("Crear vacaciones")
        self.boton_crear.setObjectName("botonPrimario")
        self.boton_crear.clicked.connect(self._crear)
        form.addWidget(self.boton_crear)
        boton_modificar = QPushButton("Modificar vacaciones")
        boton_modificar.clicked.connect(self._modificar_seleccionada)
        form.addWidget(boton_modificar)
        boton_cancelar = QPushButton("Anular vacaciones")
        boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(boton_cancelar)
        boton_deshacer = QPushButton("Deshacer último movimiento")
        boton_deshacer.clicked.connect(self._deshacer_ultimo)
        form.addWidget(boton_deshacer)

        form.addWidget(_linea_divisoria())
        self.etiqueta_cupo_utilizado = QLabel()
        self.etiqueta_cupo_disponible = QLabel()
        form.addWidget(self.etiqueta_cupo_utilizado)
        form.addWidget(self.etiqueta_cupo_disponible)

        form.addStretch()
        splitter_superior.addWidget(panel_form)

        grupo_grilla = QGroupBox("Vista previa: grilla operativa")
        layout_grupo_grilla = QVBoxLayout(grupo_grilla)
        self.grilla = GrillaOperativaWidget(self.conn)
        layout_grupo_grilla.addWidget(self.grilla)
        splitter_superior.addWidget(grupo_grilla)

        splitter_superior.setStretchFactor(0, 0)
        splitter_superior.setStretchFactor(1, 1)
        layout.addWidget(splitter_superior, stretch=2)

        panel_tabla = QGroupBox("Vacaciones tomadas")
        layout_tabla = QVBoxLayout(panel_tabla)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(7)
        self.tabla.setHorizontalHeaderLabels(
            ["Profesional", "Año calendario", "Desde", "Hasta", "Valor bonificado", "Cupo utilizado %", "Cupo restante %"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._orden = OrdenTabla(self.tabla, self.actualizar)
        layout_tabla.addWidget(self.tabla, stretch=1)
        layout.addWidget(panel_tabla, stretch=1)

        scroll.setWidget(contenido)
        layout_externo.addWidget(scroll)
        self._actualizar_disponibilidad_crear()
        self._sincronizar_grilla()
        self._foco = instalar_enter_avanza_foco(
            [self.combo_profesional, self.spin_anio, self.campo_desde, self.campo_hasta, self.boton_crear]
        )

    def _profesional_cambio(self) -> None:
        self._sincronizar_grilla()
        self.actualizar()

    def _anio_cambio(self) -> None:
        self._actualizar_disponibilidad_crear()
        self.actualizar()

    def _actualizar_disponibilidad_crear(self) -> None:
        """"Del año anterior solo consulta": el año elegido para imputar
        ya terminado deja "Crear vacaciones" deshabilitado — se puede
        seguir viendo la tabla y el cupo de ese año, pero no cargar nada
        nuevo ahí."""
        anio_actual = fecha_actual(self.conn).year
        self.boton_crear.setEnabled(self.spin_anio.value() >= anio_actual)

    def _sincronizar_grilla(self) -> None:
        """Mismo criterio que Ausencias: acotada a las unidades (con
        todos sus consultorios) y a los días en los que el profesional ya
        tiene una reserva regular, con su propio horario pintado de azul."""
        id_profesional = self.combo_profesional.currentData()
        pares = pares_dia_unidad_con_reserva_vigente(self.conn, id_profesional)
        ids_unidad = sorted({u for _, u in pares})
        dias = sorted({d for d, _ in pares}, key=DIAS_SEMANA.index)
        self.grilla.filtrar_por_unidades(ids_unidad)
        self.grilla.filtrar_por_dias(dias)
        self.grilla.filtrar_por_pares_unidad_dia(pares)
        self.grilla.filtrar_por_profesional(id_profesional)

    def _actualizar_cupo(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            self.etiqueta_cupo_utilizado.setText("Porcentaje cupo utilizado: —")
            self.etiqueta_cupo_disponible.setText("Porcentaje cupo disponible: —")
            return
        disponible = cupo_restante_actual(self.conn, id_profesional, fecha_referencia=f"{self.spin_anio.value()}-01-01")
        self.etiqueta_cupo_utilizado.setText(f"Porcentaje cupo utilizado: {100 - disponible:.1f}%")
        self.etiqueta_cupo_disponible.setText(f"Porcentaje cupo disponible: {disponible:.1f}%")

    def actualizar(self) -> None:
        """La lista de abajo es el historial completo de vacaciones
        registradas (todos los años) — sin profesional elegido muestra
        las de todos, con uno elegido se acota a las suyas. El año de
        "Año calendario a imputar" solo controla qué se va a crear y el
        cupo mostrado más abajo, por eso la lista lleva su propia
        columna "Año calendario" para distinguir a qué período
        corresponde cada fila (Orden: código del profesional y luego
        fecha desde, que ya trae el año)."""
        id_profesional_filtro = self.combo_profesional.currentData()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        todas = obtener_repositorio(self.conn, "Vacacion").listar()
        filtradas = todas
        if id_profesional_filtro is not None:
            filtradas = [r for r in filtradas if r["IdProfesional"] == id_profesional_filtro]

        filas: list[tuple[sqlite3.Row, sqlite3.Row | None]] = [
            (r, repo_profesional.obtener(r["IdProfesional"])) for r in filtradas
        ]
        filas.sort(key=lambda t: (t[1]["IdCodigo"] or "" if t[1] else "", t[0]["FechaDesde"]))
        if self._orden.columna is not None:
            filas.sort(key=self._clave_orden(self._orden.columna), reverse=not self._orden.ascendente)
        self._registros = [t[0] for t in filas]

        periodo_en_curso = periodo_actual(self.conn)
        self.tabla.setRowCount(len(filas))
        for i, (r, profesional) in enumerate(filas):
            self.tabla.setItem(i, 0, QTableWidgetItem(_texto_profesional(profesional) if profesional else "?"))
            self.tabla.setItem(i, 1, QTableWidgetItem(r["FechaDesde"][:4]))
            self.tabla.setItem(i, 2, QTableWidgetItem(_fmt_fecha(r["FechaDesde"])))
            self.tabla.setItem(i, 3, QTableWidgetItem(_fmt_fecha(r["FechaHasta"])))
            texto_valor = _texto_valor_bonificado(r["ValorBonificado"], r["FechaDesde"], periodo_en_curso)
            self.tabla.setItem(i, 4, QTableWidgetItem(texto_valor))
            cupo_utilizado = r["CupoConsumidoPorcentaje"]
            self.tabla.setItem(i, 5, QTableWidgetItem(f"{cupo_utilizado:.1f}%" if cupo_utilizado is not None else ""))
            cupo_restante = r["CupoRestantePorcentaje"]
            self.tabla.setItem(i, 6, QTableWidgetItem(f"{cupo_restante:.1f}%" if cupo_restante is not None else ""))
        self.tabla.resizeColumnsToContents()
        self.tabla.setColumnWidth(0, max(self.tabla.columnWidth(0), _ANCHO_COL_PROFESIONAL))
        self._actualizar_cupo()
        self.grilla.actualizar()

    @staticmethod
    def _clave_orden(columna: int):
        claves = {
            0: lambda t: _texto_profesional(t[1]) if t[1] else "",
            1: lambda t: t[0]["FechaDesde"][:4],
            2: lambda t: t[0]["FechaDesde"],
            3: lambda t: t[0]["FechaHasta"],
            4: lambda t: t[0]["ValorBonificado"] or 0,
            5: lambda t: t[0]["CupoConsumidoPorcentaje"] or 0,
            6: lambda t: t[0]["CupoRestantePorcentaje"] or 0,
        }
        return claves[columna]

    def _crear(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        anio_actual = fecha_actual(self.conn).year
        if self.spin_anio.value() < anio_actual:
            QMessageBox.warning(
                self, "Crear vacaciones", "No se puede imputar una vacación a un año calendario que ya terminó.",
            )
            return
        try:
            _id, advertencias = crear_vacacion(
                self.conn, id_profesional=id_profesional,
                fecha_desde=self.campo_desde.date().toPython().isoformat(),
                fecha_hasta=self.campo_hasta.date().toPython().isoformat(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Crear vacaciones", str(error))
            return
        self.conn.commit()
        if advertencias:
            QMessageBox.information(self, "Vacación creada", "\n".join(advertencias))
        regenerar_si_corresponde(self.conn, id_profesional=id_profesional, periodo=periodo_actual(self.conn))
        self.conn.commit()
        self.actualizar()
        self.combo_profesional.setFocus()

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._registros[filas[0].row()]

    def _cancelar_registro(self, registro: sqlite3.Row, titulo: str) -> bool:
        try:
            cancelar_vacacion(self.conn, registro["IdVacacion"])
        except ValueError as error:
            QMessageBox.warning(self, titulo, str(error))
            return False
        self.conn.commit()
        regenerar_si_corresponde(
            self.conn, id_profesional=registro["IdProfesional"], periodo=periodo_actual(self.conn),
        )
        self.conn.commit()
        self.actualizar()
        return True

    def _cancelar(self) -> None:
        registro = self._fila_seleccionada()
        if registro is None:
            return
        if self._cancelar_registro(registro, "Anular vacaciones"):
            self.combo_profesional.setFocus()

    def _deshacer_ultimo(self) -> None:
        """Anula la última vacación cargada en el sistema (la de mayor
        IdVacacion), sin importar de qué profesional sea ni cuál esté
        elegido en el filtro."""
        todas = obtener_repositorio(self.conn, "Vacacion").listar()
        if not todas:
            QMessageBox.warning(self, "Deshacer último movimiento", "No hay vacaciones cargadas para deshacer.")
            return
        ultima = max(todas, key=lambda v: v["IdVacacion"])
        respuesta = QMessageBox.question(
            self, "Deshacer último movimiento",
            "¿Deshacer la última vacación cargada en el sistema?\n"
            f"{_texto_profesional(obtener_repositorio(self.conn, 'Profesional').obtener(ultima['IdProfesional']))}: "
            f"{_fmt_fecha(ultima['FechaDesde'])} a {_fmt_fecha(ultima['FechaHasta'])}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        if self._cancelar_registro(ultima, "Deshacer último movimiento"):
            self.combo_profesional.setFocus()

    def _modificar_seleccionada(self) -> None:
        """Mismo criterio que Ausencias: anula la vacación seleccionada
        (bloquea si ya hay una aislada de otro profesional asignada
        aprovechando el consultorio liberado) y precarga el formulario
        con sus datos para dar de alta la versión corregida."""
        registro = self._fila_seleccionada()
        if registro is None:
            QMessageBox.warning(self, "Modificar vacaciones", "Elegí una fila de la tabla para modificar.")
            return
        if not self._cancelar_registro(registro, "Modificar vacaciones"):
            return

        indice_profesional = self.combo_profesional.findData(registro["IdProfesional"])
        if indice_profesional >= 0:
            self.combo_profesional.setCurrentIndex(indice_profesional)
        self.campo_desde.setDate(QDate.fromString(registro["FechaDesde"], "yyyy-MM-dd"))
        self.campo_hasta.setDate(QDate.fromString(registro["FechaHasta"], "yyyy-MM-dd"))
        self.spin_anio.setValue(int(registro["FechaDesde"][:4]))
        self._sincronizar_grilla()


class _PanelLicencias(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._registros: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar":
        el QTabWidget contenedor todavía no está mostrado y se termina
        quedando el foco en su tab bar. Al mostrarse la pestaña (al
        abrir la pantalla o volver a esta solapa) se repite el pedido
        de foco en Profesional, que es cuando realmente surte efecto."""
        super().showEvent(event)
        self._orden.reiniciar()
        self.actualizar()
        self.combo_profesional.setFocus()

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
        self.combo_profesional.addItem("Todos los profesionales", None)
        for id_, etiqueta in _opciones_profesional(self.conn, _CATEGORIAS_TODAS):
            self.combo_profesional.addItem(etiqueta, id_)
        self.combo_profesional.currentIndexChanged.connect(self._profesional_cambio)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_tipo = QComboBox()
        for t in obtener_repositorio(self.conn, "TipoLicencia").listar(Activo=1):
            self.combo_tipo.addItem(t["Nombre"], t["IdTipoLicencia"])
        self.combo_tipo.currentIndexChanged.connect(self._tipo_cambio)
        form.addWidget(QLabel("Tipo de licencia"))
        form.addWidget(self.combo_tipo)

        self.spin_porcentaje = QDoubleSpinBox()
        self.spin_porcentaje.setRange(0, 100)
        self.spin_porcentaje.setSuffix(" %")
        form.addWidget(QLabel("% de bonificación (editable caso por caso)"))
        form.addWidget(self.spin_porcentaje)
        self._precargar_porcentaje()

        self.campo_desde = _campo_fecha(self.conn)
        form.addWidget(QLabel("Desde"))
        form.addWidget(self.campo_desde)
        self.campo_hasta = _campo_fecha_opcional(self.conn)
        form.addWidget(QLabel("Hasta (vacío si el tipo la calcula sola)"))
        form.addWidget(self.campo_hasta)

        self.boton_crear = QPushButton("Crear licencia")
        self.boton_crear.setObjectName("botonPrimario")
        self.boton_crear.clicked.connect(self._crear)
        form.addWidget(self.boton_crear)
        boton_modificar = QPushButton("Modificar licencia")
        boton_modificar.clicked.connect(self._modificar_seleccionada)
        form.addWidget(boton_modificar)
        boton_cancelar = QPushButton("Anular licencia")
        boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(boton_cancelar)
        boton_deshacer = QPushButton("Deshacer último movimiento")
        boton_deshacer.clicked.connect(self._deshacer_ultimo)
        form.addWidget(boton_deshacer)

        form.addStretch()
        splitter_superior.addWidget(panel_form)

        grupo_grilla = QGroupBox("Vista previa: grilla operativa")
        layout_grupo_grilla = QVBoxLayout(grupo_grilla)
        self.grilla = GrillaOperativaWidget(self.conn)
        layout_grupo_grilla.addWidget(self.grilla)
        splitter_superior.addWidget(grupo_grilla)

        splitter_superior.setStretchFactor(0, 0)
        splitter_superior.setStretchFactor(1, 1)
        layout.addWidget(splitter_superior, stretch=2)

        panel_tabla = QGroupBox("Licencias tomadas")
        layout_tabla = QVBoxLayout(panel_tabla)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Profesional", "Tipo", "Desde", "Hasta", "Bonificación", "Valor bonificado"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._orden = OrdenTabla(self.tabla, self.actualizar)
        layout_tabla.addWidget(self.tabla, stretch=1)
        layout.addWidget(panel_tabla, stretch=1)

        scroll.setWidget(contenido)
        layout_externo.addWidget(scroll)
        self._sincronizar_grilla()
        self._foco = instalar_enter_avanza_foco(
            [
                self.combo_profesional, self.combo_tipo, self.spin_porcentaje,
                self.campo_desde, self.campo_hasta, self.boton_crear,
            ]
        )

    def _profesional_cambio(self) -> None:
        self._sincronizar_grilla()
        self.actualizar()

    def _tipo_cambio(self) -> None:
        self._precargar_porcentaje()
        self.actualizar()

    def _sincronizar_grilla(self) -> None:
        """Mismo criterio que Ausencias: acotada a las unidades (con
        todos sus consultorios) y a los días en los que el profesional ya
        tiene una reserva regular, con su propio horario pintado de azul."""
        id_profesional = self.combo_profesional.currentData()
        pares = pares_dia_unidad_con_reserva_vigente(self.conn, id_profesional)
        ids_unidad = sorted({u for _, u in pares})
        dias = sorted({d for d, _ in pares}, key=DIAS_SEMANA.index)
        self.grilla.filtrar_por_unidades(ids_unidad)
        self.grilla.filtrar_por_dias(dias)
        self.grilla.filtrar_por_pares_unidad_dia(pares)
        self.grilla.filtrar_por_profesional(id_profesional)

    def _precargar_porcentaje(self) -> None:
        id_tipo = self.combo_tipo.currentData()
        tipo = obtener_repositorio(self.conn, "TipoLicencia").obtener(id_tipo) if id_tipo is not None else None
        self.spin_porcentaje.setValue(tipo["PorcentajeBonificacion"] if tipo else 0)

    def actualizar(self) -> None:
        """Sin profesional elegido ("Todos los profesionales") muestra
        las licencias de todos; con uno elegido, todas las de ese
        profesional (no hay filtro de año: los cupos de licencia no son
        anuales). Orden por defecto: más nueva primero y, a igualdad de
        fecha, por profesional — overridable haciendo click en el
        título de una columna (ver `OrdenTabla`)."""
        id_profesional_filtro = self.combo_profesional.currentData()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        cache_tipo = {t["IdTipoLicencia"]: t for t in obtener_repositorio(self.conn, "TipoLicencia").listar()}
        todas = obtener_repositorio(self.conn, "Licencia").listar()
        filtradas = todas
        if id_profesional_filtro is not None:
            filtradas = [r for r in filtradas if r["IdProfesional"] == id_profesional_filtro]

        filas: list[tuple[sqlite3.Row, sqlite3.Row | None]] = [
            (r, repo_profesional.obtener(r["IdProfesional"])) for r in filtradas
        ]
        filas.sort(key=lambda t: (t[1]["IdCodigo"] or "" if t[1] else ""))
        filas.sort(key=lambda t: t[0]["FechaDesde"], reverse=True)
        if self._orden.columna is not None:
            clave = self._clave_orden(self._orden.columna, cache_tipo)
            filas.sort(key=clave, reverse=not self._orden.ascendente)
        self._registros = [t[0] for t in filas]

        periodo_en_curso = periodo_actual(self.conn)
        self.tabla.setRowCount(len(filas))
        for i, (r, profesional) in enumerate(filas):
            self.tabla.setItem(i, 0, QTableWidgetItem(_texto_profesional(profesional) if profesional else "?"))
            tipo = cache_tipo.get(r["IdTipoLicencia"])
            self.tabla.setItem(i, 1, QTableWidgetItem(tipo["Nombre"] if tipo else "?"))
            self.tabla.setItem(i, 2, QTableWidgetItem(_fmt_fecha(r["FechaDesde"])))
            self.tabla.setItem(i, 3, QTableWidgetItem(_fmt_fecha(r["FechaHasta"])))
            porcentaje = r["PorcentajeBonificacionAplicado"]
            self.tabla.setItem(i, 4, QTableWidgetItem(f"{porcentaje:.1f}%" if porcentaje is not None else ""))
            texto_valor = _texto_valor_bonificado(r["ValorBonificado"], r["FechaDesde"], periodo_en_curso)
            self.tabla.setItem(i, 5, QTableWidgetItem(texto_valor))
        self.tabla.resizeColumnsToContents()
        self.tabla.setColumnWidth(0, max(self.tabla.columnWidth(0), _ANCHO_COL_PROFESIONAL))
        self.grilla.actualizar()

    @staticmethod
    def _clave_orden(columna: int, cache_tipo: dict):
        claves = {
            0: lambda t: _texto_profesional(t[1]) if t[1] else "",
            1: lambda t: (cache_tipo.get(t[0]["IdTipoLicencia"]) or {}).get("Nombre", ""),
            2: lambda t: t[0]["FechaDesde"],
            3: lambda t: t[0]["FechaHasta"],
            4: lambda t: t[0]["PorcentajeBonificacionAplicado"] or 0,
            5: lambda t: t[0]["ValorBonificado"] or 0,
        }
        return claves[columna]

    def _crear(self) -> None:
        id_tipo = self.combo_tipo.currentData()
        if id_tipo is None:
            QMessageBox.warning(self, "Crear licencia", "Primero hay que cargar un tipo de licencia.")
            return
        tipo = obtener_repositorio(self.conn, "TipoLicencia").obtener(id_tipo)
        porcentaje_tipo = tipo["PorcentajeBonificacion"] if tipo else 0
        if self.spin_porcentaje.value() != porcentaje_tipo:
            respuesta = QMessageBox.question(
                self, "Crear licencia",
                f"El porcentaje de bonificación de '{tipo['Nombre']}' es {porcentaje_tipo:.1f}% en realidad, "
                f"pero se va a cargar con {self.spin_porcentaje.value():.1f}%. ¿Confirmar de todas formas?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                return
        try:
            _id, advertencias = crear_licencia(
                self.conn, id_profesional=self.combo_profesional.currentData(), id_tipo_licencia=id_tipo,
                fecha_desde=self.campo_desde.date().toPython().isoformat(),
                fecha_hasta=(
                    None if self.campo_hasta.date() == _FECHA_SIN_DATO
                    else self.campo_hasta.date().toPython().isoformat()
                ),
                porcentaje_bonificacion=self.spin_porcentaje.value(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Crear licencia", str(error))
            return
        self.conn.commit()
        if advertencias:
            QMessageBox.information(self, "Licencia creada", "\n".join(advertencias))
        self.actualizar()
        self.combo_profesional.setFocus()

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._registros[filas[0].row()]

    def _cancelar_registro(self, registro: sqlite3.Row, titulo: str) -> bool:
        try:
            cancelar_licencia(self.conn, registro["IdLicencia"])
        except ValueError as error:
            QMessageBox.warning(self, titulo, str(error))
            return False
        self.conn.commit()
        self.actualizar()
        return True

    def _cancelar(self) -> None:
        registro = self._fila_seleccionada()
        if registro is None:
            return
        if self._cancelar_registro(registro, "Anular licencia"):
            self.combo_profesional.setFocus()

    def _deshacer_ultimo(self) -> None:
        """Anula la última licencia cargada en el sistema (la de mayor
        IdLicencia), sin importar de qué profesional sea ni cuál esté
        elegido en el filtro."""
        todas = obtener_repositorio(self.conn, "Licencia").listar()
        if not todas:
            QMessageBox.warning(self, "Deshacer último movimiento", "No hay licencias cargadas para deshacer.")
            return
        ultima = max(todas, key=lambda v: v["IdLicencia"])
        respuesta = QMessageBox.question(
            self, "Deshacer último movimiento",
            "¿Deshacer la última licencia cargada en el sistema?\n"
            f"{_texto_profesional(obtener_repositorio(self.conn, 'Profesional').obtener(ultima['IdProfesional']))}: "
            f"{_fmt_fecha(ultima['FechaDesde'])} a {_fmt_fecha(ultima['FechaHasta'])}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        if self._cancelar_registro(ultima, "Deshacer último movimiento"):
            self.combo_profesional.setFocus()

    def _modificar_seleccionada(self) -> None:
        registro = self._fila_seleccionada()
        if registro is None:
            QMessageBox.warning(self, "Modificar licencia", "Elegí una fila de la tabla para modificar.")
            return
        if not self._cancelar_registro(registro, "Modificar licencia"):
            return

        indice_profesional = self.combo_profesional.findData(registro["IdProfesional"])
        if indice_profesional >= 0:
            self.combo_profesional.setCurrentIndex(indice_profesional)
        indice_tipo = self.combo_tipo.findData(registro["IdTipoLicencia"])
        if indice_tipo >= 0:
            self.combo_tipo.setCurrentIndex(indice_tipo)
        self.spin_porcentaje.setValue(registro["PorcentajeBonificacionAplicado"] or 0)
        self.campo_desde.setDate(QDate.fromString(registro["FechaDesde"], "yyyy-MM-dd"))
        self.campo_hasta.setDate(QDate.fromString(registro["FechaHasta"], "yyyy-MM-dd"))
        self._sincronizar_grilla()


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

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar":
        el QTabWidget contenedor todavía no está mostrado y se termina
        quedando el foco en su tab bar. Al mostrarse la pestaña (al
        abrir la pantalla o volver a esta solapa) se repite el pedido
        de foco en Profesional, que es cuando realmente surte efecto."""
        super().showEvent(event)
        self._orden.reiniciar()
        self.actualizar()
        self.combo_profesional.setFocus()

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
        self.combo_profesional.addItem("Todos los profesionales", None)
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

        self.campo_desde = _campo_fecha(self.conn)
        self.campo_desde.dateChanged.connect(self._actualizar_disponibilidad_horario)
        form.addWidget(QLabel("Desde"))
        form.addWidget(self.campo_desde)
        self.campo_hasta = _campo_fecha(self.conn)
        self.campo_hasta.dateChanged.connect(self._actualizar_disponibilidad_horario)
        form.addWidget(QLabel("Hasta"))
        form.addWidget(self.campo_hasta)

        self.grupo_horario = QGroupBox("Horario puntual (solo si la ausencia es de un único día)")
        self.grupo_horario.setCheckable(True)
        self.grupo_horario.setChecked(False)
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
        self._actualizar_disponibilidad_horario()

        boton = QPushButton("Crear ausencia")
        boton.setObjectName("botonPrimario")
        boton.clicked.connect(self._crear)
        form.addWidget(boton)
        boton_modificar = QPushButton("Modificar ausencia seleccionada")
        boton_modificar.clicked.connect(self._modificar_seleccionada)
        form.addWidget(boton_modificar)
        boton_cancelar = QPushButton("Anular ausencia seleccionada")
        boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(boton_cancelar)
        boton_deshacer = QPushButton("Deshacer último movimiento")
        boton_deshacer.clicked.connect(self._deshacer_ultimo)
        form.addWidget(boton_deshacer)
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
        self._orden = OrdenTabla(self.tabla, self.actualizar)
        layout_tabla.addWidget(self.tabla, stretch=1)
        layout.addWidget(panel_tabla, stretch=1)

        scroll.setWidget(contenido)
        layout_externo.addWidget(scroll)
        self._sincronizar_grilla()
        self._foco = instalar_enter_avanza_foco(
            [self.combo_profesional, self.combo_motivo, self.campo_desde, self.campo_hasta, boton]
        )

    def _profesional_cambio(self) -> None:
        self._sincronizar_grilla()
        self.actualizar()

    def _actualizar_disponibilidad_horario(self) -> None:
        """El horario puntual solo tiene sentido para una ausencia de un
        único día — se habilita apenas Desde y Hasta coinciden, y se
        vuelve a deshabilitar (destildando) apenas dejan de coincidir."""
        un_solo_dia = self.campo_desde.date() == self.campo_hasta.date()
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
        if self._orden.columna is not None:
            filas.sort(key=self._clave_orden(self._orden.columna), reverse=not self._orden.ascendente)
        self._registros = [t[0] for t in filas]

        self.tabla.setRowCount(len(filas))
        for i, (r, profesional) in enumerate(filas):
            self.tabla.setItem(i, 0, QTableWidgetItem(_texto_profesional(profesional) if profesional else "?"))
            self.tabla.setItem(i, 1, QTableWidgetItem(_fmt_fecha(r["FechaDesde"])))
            self.tabla.setItem(i, 2, QTableWidgetItem(_fmt_fecha(r["FechaHasta"])))
            self.tabla.setItem(i, 3, QTableWidgetItem(_fmt_horario_ausencia(r)))
            self.tabla.setItem(i, 4, QTableWidgetItem(r["Motivo"] or ""))
            self.tabla.setItem(i, 5, QTableWidgetItem(self._origen(r)))
        self.tabla.resizeColumnsToContents()
        self.tabla.setColumnWidth(0, max(self.tabla.columnWidth(0), _ANCHO_COL_PROFESIONAL))
        self.grilla.actualizar()

    def _clave_orden(self, columna: int):
        claves = {
            0: lambda t: _texto_profesional(t[1]) if t[1] else "",
            1: lambda t: t[0]["FechaDesde"],
            2: lambda t: t[0]["FechaHasta"],
            3: lambda t: _fmt_horario_ausencia(t[0]),
            4: lambda t: t[0]["Motivo"] or "",
            5: lambda t: self._origen(t[0]),
        }
        return claves[columna]

    def _crear(self) -> None:
        hora_inicio = hora_fin = None
        if self.grupo_horario.isEnabled() and self.grupo_horario.isChecked():
            hora_inicio = self.spin_hora_desde.value()
            hora_fin = self.spin_hora_hasta.value()
        try:
            crear_ausencia(
                self.conn, id_profesional=self.combo_profesional.currentData(),
                fecha_desde=self.campo_desde.date().toPython().isoformat(),
                fecha_hasta=self.campo_hasta.date().toPython().isoformat(),
                motivo=self.combo_motivo.currentText().strip() or None,
                hora_inicio=hora_inicio, hora_fin=hora_fin,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Crear ausencia", str(error))
            return
        self.conn.commit()
        self.actualizar()
        self.combo_profesional.setFocus()

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._registros[filas[0].row()]

    def _cancelar_registro(self, registro: sqlite3.Row, titulo: str) -> bool:
        try:
            cancelar_ausencia(self.conn, registro["IdAusencia"])
        except ValueError as error:
            QMessageBox.warning(self, titulo, str(error))
            return False
        self.conn.commit()
        self.actualizar()
        return True

    def _cancelar(self) -> None:
        registro = self._fila_seleccionada()
        if registro is None:
            return
        if self._cancelar_registro(registro, "Anular ausencia"):
            self.combo_profesional.setFocus()

    def _deshacer_ultimo(self) -> None:
        """Anula la última ausencia cargada en el sistema (la de mayor
        IdAusencia), sin importar de qué profesional sea ni cuál esté
        elegido en el filtro."""
        todas = obtener_repositorio(self.conn, "Ausencia").listar()
        if not todas:
            QMessageBox.warning(self, "Deshacer último movimiento", "No hay ausencias cargadas para deshacer.")
            return
        ultima = max(todas, key=lambda v: v["IdAusencia"])
        respuesta = QMessageBox.question(
            self, "Deshacer último movimiento",
            "¿Deshacer la última ausencia cargada en el sistema?\n"
            f"{_texto_profesional(obtener_repositorio(self.conn, 'Profesional').obtener(ultima['IdProfesional']))}: "
            f"{_fmt_fecha(ultima['FechaDesde'])} a {_fmt_fecha(ultima['FechaHasta'])}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        if self._cancelar_registro(ultima, "Deshacer último movimiento"):
            self.combo_profesional.setFocus()

    def _modificar_seleccionada(self) -> None:
        """Mismo criterio que Reservas aisladas: no se edita la fila
        histórica in-place — se anula la ausencia seleccionada (bloquea
        si ya hay una aislada de otro profesional asignada aprovechando
        el consultorio liberado) y se precarga el formulario con sus
        datos para dar de alta la versión corregida. El operador ajusta
        lo que haga falta y confirma con "Crear ausencia", como
        cualquier alta."""
        registro = self._fila_seleccionada()
        if registro is None:
            QMessageBox.warning(self, "Modificar ausencia", "Elegí una fila de la tabla para modificar.")
            return
        if not self._cancelar_registro(registro, "Modificar ausencia"):
            return

        indice_profesional = self.combo_profesional.findData(registro["IdProfesional"])
        if indice_profesional >= 0:
            self.combo_profesional.setCurrentIndex(indice_profesional)
        self.combo_motivo.setCurrentText(registro["Motivo"] or "")
        self.campo_desde.setDate(QDate.fromString(registro["FechaDesde"], "yyyy-MM-dd"))
        self.campo_hasta.setDate(QDate.fromString(registro["FechaHasta"], "yyyy-MM-dd"))
        tiene_horario = registro["HoraInicio"] is not None and registro["HoraFin"] is not None
        self.grupo_horario.setChecked(tiene_horario)
        if tiene_horario:
            self.spin_hora_desde.setValue(registro["HoraInicio"])
            self.spin_hora_hasta.setValue(registro["HoraFin"])
        self._sincronizar_grilla()


class _PanelCargosEspeciales(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._registros: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """Mismo motivo que en las demás pestañas de esta pantalla:
        `setFocus()` durante la construcción no alcanza a "pegar"."""
        super().showEvent(event)
        self._orden.reiniciar()
        self.actualizar()
        self.combo_profesional.setFocus()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        self.combo_profesional = QComboBox()
        self.combo_profesional.setMinimumWidth(_ANCHO_COMBO_PROFESIONAL)
        self.combo_profesional.addItem("Todos los profesionales", None)
        for id_, etiqueta in _opciones_profesional(self.conn, _CATEGORIAS_TODAS):
            self.combo_profesional.addItem(etiqueta, id_)
        self.combo_profesional.currentIndexChanged.connect(self.actualizar)
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
        self.spin_monto.setRange(-100_000_000, 100_000_000)
        self.spin_monto.valueChanged.connect(self._actualizar_color_monto)
        form.addWidget(QLabel("Monto (Débito positivo, Crédito negativo)"))
        form.addWidget(self.spin_monto)

        self.campo_periodo = QLineEdit()
        self.campo_periodo.setText(periodo_actual(self.conn))
        form.addWidget(QLabel("Período imputado"))
        form.addWidget(self.campo_periodo)

        boton = QPushButton("Crear cargo especial")
        boton.setObjectName("botonPrimario")
        boton.clicked.connect(self._crear)
        form.addWidget(boton)
        boton_modificar = QPushButton("Modificar cargo especial")
        boton_modificar.clicked.connect(self._modificar_seleccionada)
        form.addWidget(boton_modificar)
        boton_eliminar = QPushButton("Eliminar cargo especial")
        boton_eliminar.clicked.connect(self._eliminar)
        form.addWidget(boton_eliminar)
        boton_deshacer = QPushButton("Deshacer último movimiento")
        boton_deshacer.clicked.connect(self._deshacer_ultimo)
        form.addWidget(boton_deshacer)
        form.addStretch()
        splitter.addWidget(panel_form)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Fecha", "Profesional", "Tipo", "Concepto", "Monto", "Período imputado"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._orden = OrdenTabla(self.tabla, self.actualizar)
        splitter.addWidget(self.tabla)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        self._foco = instalar_enter_avanza_foco(
            [
                self.combo_profesional, self.combo_tipo, self.campo_concepto, self.spin_monto, self.campo_periodo,
                boton, boton_modificar, boton_eliminar, boton_deshacer,
            ]
        )

    def _actualizar_color_monto(self) -> None:
        """Mismo criterio que la tabla: negativo en rojo, positivo en
        negro, ya mientras se está cargando el monto (no recién después de
        confirmar)."""
        self.spin_monto.setStyleSheet(f"color: {COLOR_ROJO};" if self.spin_monto.value() < 0 else "")

    def actualizar(self) -> None:
        """Sin profesional elegido, muestra los cargos especiales de todos
        los profesionales; con uno elegido, se acota a los suyos. Orden
        por defecto: fecha de carga (lo más nuevo arriba), categoría del
        profesional (B, R, A, E — orden fijo específico de esta pantalla,
        no el mismo que usa Reservas regulares) y número de profesional."""
        id_profesional_filtro = self.combo_profesional.currentData()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        todos = obtener_repositorio(self.conn, "CargoEspecial").listar()
        if id_profesional_filtro is not None:
            registros = [r for r in todos if r["IdProfesional"] == id_profesional_filtro]
        else:
            registros = todos

        filas: list[tuple[sqlite3.Row, sqlite3.Row | None]] = [
            (r, repo_profesional.obtener(r["IdProfesional"])) for r in registros
        ]
        filas.sort(key=lambda t: (
            _ORDEN_CATEGORIA_CARGOS.get(t[1]["CategoriaProfesional"], 99) if t[1] else 99,
            _numero_codigo(t[1]["IdCodigo"] if t[1] else None),
        ))
        filas.sort(key=lambda t: t[0]["Fecha"] or "", reverse=True)  # más nuevo arriba, estable sobre lo anterior
        if self._orden.columna is not None:
            filas.sort(key=self._clave_orden(self._orden.columna), reverse=not self._orden.ascendente)
        self._registros = [t[0] for t in filas]

        self.tabla.setRowCount(len(filas))
        for i, (r, profesional) in enumerate(filas):
            self.tabla.setItem(i, 0, QTableWidgetItem(_fmt_fecha_dia(r["Fecha"]) if r["Fecha"] else ""))
            self.tabla.setItem(i, 1, QTableWidgetItem(_texto_profesional(profesional) if profesional else "?"))
            self.tabla.setItem(i, 2, QTableWidgetItem(r["Tipo"]))
            self.tabla.setItem(i, 3, QTableWidgetItem(r["Concepto"]))
            self.tabla.setItem(i, 4, _item_monto(r["Monto"]))
            self.tabla.setItem(i, 5, QTableWidgetItem(r["PeriodoImputado"] or ""))
        self.tabla.resizeColumnsToContents()
        self.tabla.setColumnWidth(1, max(self.tabla.columnWidth(1), _ANCHO_COL_PROFESIONAL))

    @staticmethod
    def _clave_orden(columna: int):
        claves = {
            0: lambda t: t[0]["Fecha"] or "",
            1: lambda t: _texto_profesional(t[1]) if t[1] else "",
            2: lambda t: t[0]["Tipo"],
            3: lambda t: t[0]["Concepto"],
            4: lambda t: t[0]["Monto"],
            5: lambda t: t[0]["PeriodoImputado"] or "",
        }
        return claves[columna]

    def _crear(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Crear cargo especial", "Elegí un profesional.")
            return
        concepto = self.campo_concepto.text().strip()
        if not concepto:
            QMessageBox.warning(self, "Crear cargo especial", "El concepto es obligatorio.")
            return
        periodo_imputado = self.campo_periodo.text().strip()
        try:
            crear_cargo_especial(
                self.conn, id_profesional=id_profesional, tipo=self.combo_tipo.currentData(),
                concepto=concepto, monto=self.spin_monto.value(), periodo_imputado=periodo_imputado,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Crear cargo especial", str(error))
            return
        self.conn.commit()
        self.actualizar()
        self.combo_profesional.setFocus()

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._registros[filas[0].row()]

    def _bloqueado_por_llave(self, registro: sqlite3.Row, titulo: str) -> bool:
        """Un cargo especial ligado a una llave (IdLlave) se generó solo
        desde la pantalla de Llaves al entregarla o devolverla — tocarlo
        acá (modificarlo, eliminarlo o deshacerlo) desincronizaría la
        tenencia registrada en LlaveProfesional, así que se bloquea y se
        indica corregirlo desde la pantalla de Llaves."""
        if registro["IdLlave"] is None:
            return False
        QMessageBox.warning(
            self, titulo,
            "Este cargo especial viene de un depósito o reintegro de llave — corregilo desde la pantalla de Llaves.",
        )
        return True

    def _eliminar(self) -> None:
        registro = self._fila_seleccionada()
        if registro is None:
            QMessageBox.warning(self, "Eliminar cargo especial", "Elegí una fila de la tabla para eliminar.")
            return
        if self._bloqueado_por_llave(registro, "Eliminar cargo especial"):
            return
        obtener_repositorio(self.conn, "CargoEspecial").eliminar(registro["IdCargo"])
        self.conn.commit()
        self.actualizar()
        self.combo_profesional.setFocus()

    def _modificar_seleccionada(self) -> None:
        """No se edita la fila in-place: se elimina la seleccionada y se
        precarga el formulario con sus datos para dar de alta la versión
        corregida, como en Vacaciones/Licencias/Ausencias."""
        registro = self._fila_seleccionada()
        if registro is None:
            QMessageBox.warning(self, "Modificar cargo especial", "Elegí una fila de la tabla para modificar.")
            return
        if self._bloqueado_por_llave(registro, "Modificar cargo especial"):
            return
        obtener_repositorio(self.conn, "CargoEspecial").eliminar(registro["IdCargo"])
        self.conn.commit()
        self.actualizar()

        indice_profesional = self.combo_profesional.findData(registro["IdProfesional"])
        if indice_profesional >= 0:
            self.combo_profesional.setCurrentIndex(indice_profesional)
        self.combo_tipo.setCurrentIndex(self.combo_tipo.findData(registro["Tipo"]))
        self.campo_concepto.setText(registro["Concepto"])
        self.spin_monto.setValue(registro["Monto"])
        self.campo_periodo.setText(registro["PeriodoImputado"] or periodo_actual(self.conn))

    def _deshacer_ultimo(self) -> None:
        """Como no hay forma de anular un cargo especial (se elimina
        directo, sin dejar estado): "Deshacer" borra el último cargo
        especial cargado en el sistema (el de mayor IdCargo), sin importar
        de qué profesional sea."""
        todos = obtener_repositorio(self.conn, "CargoEspecial").listar()
        if not todos:
            QMessageBox.warning(self, "Deshacer último movimiento", "No hay cargos especiales cargados para deshacer.")
            return
        ultimo = max(todos, key=lambda c: c["IdCargo"])
        if self._bloqueado_por_llave(ultimo, "Deshacer último movimiento"):
            return
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(ultimo["IdProfesional"])
        respuesta = QMessageBox.question(
            self, "Deshacer último movimiento",
            "¿Deshacer el último cargo especial cargado en el sistema?\n"
            f"{_texto_profesional(profesional) if profesional else '?'}: "
            f"{ultimo['Tipo']} - {ultimo['Concepto']} - {formatear_moneda(ultimo['Monto'])}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        obtener_repositorio(self.conn, "CargoEspecial").eliminar(ultimo["IdCargo"])
        self.conn.commit()
        self.actualizar()
        self.combo_profesional.setFocus()
        self.combo_profesional.setFocus()
