"""Reservas regulares y aisladas (F16/F17, secciones 3.9-3.10): reusa
app.negocio.reservas para el alta (con toda la validación de conflictos,
bloques rígidos y ausencias) y la cancelación de aisladas, en vez de
escribir directamente en las tablas."""
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtGui import QGuiApplication, QValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.dialogos import confirmar_si_fecha_es_mes_anterior
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.grilla_operativa import (
    GrillaOperativaWidget,
    pares_dia_unidad_con_reserva,
    pares_dia_unidad_con_reserva_vigente,
)
from app.gui.widgets.orden_tabla import OrdenTabla
from app.negocio.ausencias import crear_ausencia
from app.negocio.dias import DIAS_SEMANA, fecha_a_dia_semana, fecha_actual, periodo_actual, ultimo_dia_mes
from app.negocio.formato import formatear_moneda
from app.negocio.lista_espera import marcar_resuelto
from app.negocio.liquidaciones import regenerar_si_corresponde
from app.negocio.mensajes import mensaje_detalle_reserva_aislada
from app.negocio.resumen_profesional import calcular_resumen_profesional
from app.negocio.reservas import (
    ConflictoBloqueanteError,
    cancelar_reserva_aislada,
    crear_reserva_aislada,
    crear_reserva_regular,
)
from app.repositorio.registro import obtener_repositorio

_DIAS_RESERVA = DIAS_SEMANA[:6]
_ANCHO_COMBO_PROFESIONAL = 220
_ANCHO_COL_PROFESIONAL = 180
_FORMATO_FECHA = "dd-MM-yyyy"
_FECHA_SIN_DATO = QDate(2000, 1, 1)  # sentinel de QDateEdit.setSpecialValueText: "sin fecha"


def _fmt_horas(horas: float) -> str:
    return str(int(horas)) if horas == int(horas) else f"{horas:.1f}"


def _fmt_fecha(fecha_iso: str | None) -> str:
    if not fecha_iso:
        return ""
    return QDate.fromString(fecha_iso, "yyyy-MM-dd").toString(_FORMATO_FECHA)


def _fmt_hora(valor: float) -> str:
    """"9:00", "14:30" — mismo criterio que `_SpinHorario`, para las
    columnas de horario de las tablas (que no son spinboxes) y los
    combos que arman su propia etiqueta con un horario adentro."""
    horas = int(valor)
    minutos = round((valor - horas) * 60)
    return f"{horas}:{minutos:02d}"


def _fmt_horario(hora_inicio: float, hora_fin: float) -> str:
    return f"{_fmt_hora(hora_inicio)} a {_fmt_hora(hora_fin)}"


class _SpinHorario(QDoubleSpinBox):
    """QDoubleSpinBox que se muestra como horario ("9:00", "14:30") en vez
    del decimal ("9,00", "14,5") que arrastra el separador de la
    configuración regional — internamente sigue siendo el mismo float en
    horas que espera `app.negocio.reservas` (9.0, 14.5, ...)."""

    def textFromValue(self, value: float) -> str:  # noqa: N802 (nombre impuesto por Qt)
        return _fmt_hora(value)

    def valueFromText(self, text: str) -> float:  # noqa: N802
        texto = text.strip()
        if ":" in texto:
            horas_str, minutos_str = texto.split(":", 1)
            return int(horas_str or 0) + int(minutos_str or 0) / 60
        return float(texto.replace(",", ".") or 0)

    def validate(self, text: str, pos: int):  # noqa: N802
        return (QValidator.State.Acceptable, text, pos)


_CATEGORIAS_REGULARES = ("R", "B", "E")
_CATEGORIAS_AISLADAS = ("R", "A")


def _texto_profesional(fila: sqlite3.Row) -> str:
    """"R1 - Lic. Virginia Lo Veci": código (si tiene) + Tratamiento +
    NombrePila + Apellido, estos últimos tres opcionales si el
    profesional no los tiene cargados."""
    partes = [p for p in (fila["Tratamiento"], fila["NombrePila"], fila["Apellido"]) if p]
    nombre = " ".join(partes) if partes else fila["Apellido"]
    codigo = fila["IdCodigo"]
    return f"{codigo} - {nombre}" if codigo else nombre


def _texto_consultorio(consultorio: sqlite3.Row, mostrar_localidad: bool, mostrar_edificio: bool) -> str:
    """"Ramos Mejía - Ramos 1 - 7mo 'L' - 1": Localidad y Edificio se
    omiten cuando el conjunto que se está mostrando en la tabla tiene
    uno solo (no hace falta aclarar lo que ya es igual en todas las
    filas) — mismo criterio que usa GrillaOperativaWidget para sus
    encabezados agrupados."""
    partes = []
    if mostrar_localidad:
        partes.append(consultorio["DomicilioLocalidad"] or "(Sin localidad)")
    if mostrar_edificio:
        partes.append(consultorio["NombreEdificio"])
    partes.append(consultorio["Departamento"])
    partes.append(str(consultorio["NumeroConsultorio"]))
    return " - ".join(partes)


def _opciones_profesional(conn: sqlite3.Connection, categorias: tuple[str, ...]) -> list[tuple[int, str]]:
    placeholders = ", ".join("?" for _ in categorias)
    filas = conn.execute(
        f"SELECT IdProfesional, IdCodigo, Tratamiento, Apellido, NombrePila FROM Profesional "
        f"WHERE CategoriaProfesional IN ({placeholders}) ORDER BY Apellido",
        categorias,
    ).fetchall()
    return [(f["IdProfesional"], _texto_profesional(f)) for f in filas]


def _opciones_horario_regular(conn: sqlite3.Connection, id_profesional: int | None) -> list[tuple[int, str]]:
    """Horarios regulares vigentes del profesional — para que, al marcar
    "Es reubicación" en el alta de una reserva aislada, el operador pueda
    elegir cuál de ellos no va a usar esta vez."""
    if id_profesional is None:
        return []
    filas = conn.execute(
        "SELECT r.IdConsultorio, r.DiaSemana, r.HoraInicio, r.HoraFin, u.Departamento, c.NumeroConsultorio "
        "FROM ReservaRegular r JOIN Consultorio c ON c.IdConsultorio = r.IdConsultorio "
        "JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
        "WHERE r.IdProfesional = ? AND (r.VigenciaFin IS NULL OR r.VigenciaFin >= ?) "
        "ORDER BY r.DiaSemana, r.HoraInicio",
        (id_profesional, fecha_actual(conn).isoformat()),
    ).fetchall()
    return [
        (
            f["IdConsultorio"],
            f"{f['DiaSemana']} {_fmt_horario(f['HoraInicio'], f['HoraFin'])} - {f['Departamento']} - {f['NumeroConsultorio']}",
        )
        for f in filas
    ]


def _opciones_localidad(conn: sqlite3.Connection) -> list[tuple[str | None, str]]:
    filas = conn.execute("SELECT DISTINCT DomicilioLocalidad FROM Edificio ORDER BY DomicilioLocalidad").fetchall()
    return [(f["DomicilioLocalidad"], f["DomicilioLocalidad"] or "(Sin localidad)") for f in filas]


def _opciones_edificio(conn: sqlite3.Connection, localidad: str | None) -> list[tuple[int, str]]:
    if localidad is None:
        filas = conn.execute(
            "SELECT IdEdificio, Nombre FROM Edificio WHERE DomicilioLocalidad IS NULL ORDER BY Nombre"
        ).fetchall()
    else:
        filas = conn.execute(
            "SELECT IdEdificio, Nombre FROM Edificio WHERE DomicilioLocalidad = ? ORDER BY Nombre", (localidad,)
        ).fetchall()
    return [(f["IdEdificio"], f["Nombre"]) for f in filas]


def _opciones_unidad(conn: sqlite3.Connection, id_edificio: int | None) -> list[tuple[int, str]]:
    if id_edificio is None:
        return []
    filas = conn.execute(
        "SELECT IdUnidad, Departamento FROM Unidad WHERE IdEdificio = ? ORDER BY Departamento", (id_edificio,)
    ).fetchall()
    return [(f["IdUnidad"], f["Departamento"]) for f in filas]


def _opciones_consultorio_de_unidad(conn: sqlite3.Connection, id_unidad: int | None) -> list[tuple[int, str]]:
    if id_unidad is None:
        return []
    filas = conn.execute(
        "SELECT IdConsultorio, NumeroConsultorio FROM Consultorio WHERE IdUnidad = ? ORDER BY NumeroConsultorio",
        (id_unidad,),
    ).fetchall()
    return [(f["IdConsultorio"], f"Consultorio {f['NumeroConsultorio']}") for f in filas]


def _recargar_edificios(conn: sqlite3.Connection, combo_localidad: QComboBox, combo_edificio: QComboBox) -> None:
    localidad = combo_localidad.currentData()
    combo_edificio.blockSignals(True)
    combo_edificio.clear()
    for id_, nombre in _opciones_edificio(conn, localidad):
        combo_edificio.addItem(nombre, id_)
    combo_edificio.blockSignals(False)


def _recargar_unidades(conn: sqlite3.Connection, combo_edificio: QComboBox, combo_unidad: QComboBox) -> None:
    id_edificio = combo_edificio.currentData()
    combo_unidad.blockSignals(True)
    combo_unidad.clear()
    for id_, depto in _opciones_unidad(conn, id_edificio):
        combo_unidad.addItem(depto, id_)
    combo_unidad.blockSignals(False)


def _recargar_consultorios(conn: sqlite3.Connection, combo_unidad: QComboBox, combo_consultorio: QComboBox) -> None:
    id_unidad = combo_unidad.currentData()
    combo_consultorio.blockSignals(True)
    combo_consultorio.clear()
    for id_, etiqueta in _opciones_consultorio_de_unidad(conn, id_unidad):
        combo_consultorio.addItem(etiqueta, id_)
    combo_consultorio.blockSignals(False)


class PantallaReservas(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Reservas")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        pestanas = QTabWidget()
        self.panel_regulares = _PanelReservasRegulares(conn)
        self.panel_aisladas = _PanelReservasAisladas(conn)
        pestanas.addTab(self.panel_regulares, "Regulares")
        pestanas.addTab(self.panel_aisladas, "Aisladas")
        layout.addWidget(pestanas, stretch=1)

    def actualizar(self) -> None:
        self.panel_regulares.actualizar()
        self.panel_aisladas.actualizar()


class _PanelReservasRegulares(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._reservas: list[sqlite3.Row] = []
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
        for id_, etiqueta in _opciones_profesional(self.conn, _CATEGORIAS_REGULARES):
            self.combo_profesional.addItem(etiqueta, id_)
        self.combo_profesional.currentIndexChanged.connect(self.actualizar)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_localidad = QComboBox()
        for valor, etiqueta in _opciones_localidad(self.conn):
            self.combo_localidad.addItem(etiqueta, valor)
        self.combo_localidad.currentIndexChanged.connect(self._cargar_edificios)
        form.addWidget(QLabel("Localidad"))
        form.addWidget(self.combo_localidad)

        self.combo_edificio = QComboBox()
        self.combo_edificio.currentIndexChanged.connect(self._cargar_unidades)
        form.addWidget(QLabel("Edificio"))
        form.addWidget(self.combo_edificio)

        self.combo_unidad = QComboBox()
        self.combo_unidad.currentIndexChanged.connect(self._cargar_consultorios)
        form.addWidget(QLabel("Unidad"))
        form.addWidget(self.combo_unidad)

        self.combo_consultorio = QComboBox()
        self.combo_consultorio.currentIndexChanged.connect(self._sincronizar_grilla)
        form.addWidget(QLabel("Consultorio"))
        form.addWidget(self.combo_consultorio)

        form.addWidget(QLabel("Días"))
        self._checks_dia: dict[str, QCheckBox] = {}
        contenedor_dias = QWidget()
        layout_dias = QVBoxLayout(contenedor_dias)
        layout_dias.setContentsMargins(0, 0, 0, 0)
        for dia in _DIAS_RESERVA:
            check = QCheckBox(dia)
            check.setChecked(dia == "Lunes")
            self._checks_dia[dia] = check
            layout_dias.addWidget(check)
        form.addWidget(contenedor_dias)

        fila_horario = QHBoxLayout()
        self.spin_desde = _SpinHorario()
        self.spin_desde.setRange(0, 23)
        self.spin_desde.setValue(9)
        self.spin_hasta = _SpinHorario()
        self.spin_hasta.setRange(1, 24)
        self.spin_hasta.setValue(10)
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_desde)
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hasta)
        form.addLayout(fila_horario)

        self.campo_vigencia_inicio = QDateEdit()
        self.campo_vigencia_inicio.setDisplayFormat(_FORMATO_FECHA)
        self.campo_vigencia_inicio.setCalendarPopup(True)
        form.addWidget(QLabel("Vigencia desde"))
        form.addWidget(self.campo_vigencia_inicio)

        self.campo_vigencia_fin = QDateEdit()
        self.campo_vigencia_fin.setDisplayFormat(_FORMATO_FECHA)
        self.campo_vigencia_fin.setCalendarPopup(True)
        self.campo_vigencia_fin.setMinimumDate(_FECHA_SIN_DATO)
        self.campo_vigencia_fin.setSpecialValueText("(sin fecha)")
        self.campo_vigencia_fin.setDate(_FECHA_SIN_DATO)
        form.addWidget(QLabel("Vigencia hasta (opcional)"))
        form.addWidget(self.campo_vigencia_fin)

        boton_crear = QPushButton("Crear reserva regular")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.clicked.connect(self._crear)
        form.addWidget(boton_crear)

        linea_separadora = QFrame()
        linea_separadora.setFrameShape(QFrame.Shape.HLine)
        linea_separadora.setFrameShadow(QFrame.Shadow.Sunken)
        form.addWidget(linea_separadora)

        form.addWidget(QLabel("Datos complementarios del profesional"))
        self.etiqueta_horas_semanales = QLabel()
        self.etiqueta_horas_aisladas = QLabel()
        self.etiqueta_descuento = QLabel()
        self.etiqueta_vacaciones = QLabel()
        form.addWidget(self.etiqueta_horas_semanales)
        form.addWidget(self.etiqueta_horas_aisladas)
        form.addWidget(self.etiqueta_descuento)
        form.addWidget(self.etiqueta_vacaciones)

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

        panel_tabla = QGroupBox("Horarios reservados")
        layout_tabla = QVBoxLayout(panel_tabla)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Profesional", "Consultorio", "Día", "Horario", "Vigencia desde", "Vigencia hasta"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._orden = OrdenTabla(self.tabla, self.actualizar)
        layout_tabla.addWidget(self.tabla, stretch=1)

        fila_acciones = QHBoxLayout()
        boton_modificar = QPushButton("Modificar seleccionada")
        boton_modificar.clicked.connect(self._modificar_seleccionada)
        fila_acciones.addWidget(boton_modificar)
        boton_finalizar = QPushButton("Finalizar reserva a fin de mes")
        boton_finalizar.clicked.connect(self._finalizar_vigencia)
        fila_acciones.addWidget(boton_finalizar)
        boton_deshacer = QPushButton("Deshacer último movimiento")
        boton_deshacer.clicked.connect(self._deshacer_ultimo)
        fila_acciones.addWidget(boton_deshacer)
        fila_acciones.addStretch()
        layout_tabla.addLayout(fila_acciones)
        layout.addWidget(panel_tabla, stretch=1)

        hoy = fecha_actual(self.conn)
        self.campo_vigencia_inicio.setDate(QDate(hoy.year, hoy.month, hoy.day))

        scroll.setWidget(contenido)
        layout_externo.addWidget(scroll)
        self._cargar_edificios()
        self._foco = instalar_enter_avanza_foco(
            [
                self.combo_profesional, self.combo_localidad, self.combo_edificio, self.combo_unidad,
                self.combo_consultorio, self.spin_desde, self.spin_hasta,
                self.campo_vigencia_inicio, self.campo_vigencia_fin, boton_crear,
            ]
        )

    def actualizar(self) -> None:
        """Sin profesional elegido, muestra todas las reservas regulares
        VIGENTES de todos los profesionales (no tiene sentido alargar la
        lista con lo que ya terminó); con uno elegido, se acota a las de
        ese profesional únicamente (incluida su historia, para poder
        revisarla). Orden: código del profesional, día de la semana,
        hora inicial, localidad, edificio, unidad y consultorio."""
        id_profesional_filtro = self.combo_profesional.currentData()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        todas = obtener_repositorio(self.conn, "ReservaRegular").listar()
        if id_profesional_filtro is not None:
            filtradas = [r for r in todas if r["IdProfesional"] == id_profesional_filtro]
        else:
            hoy = fecha_actual(self.conn).isoformat()
            filtradas = [r for r in todas if not r["VigenciaFin"] or r["VigenciaFin"] >= hoy]

        filas: list[tuple[sqlite3.Row, sqlite3.Row | None, sqlite3.Row | None]] = []
        for r in filtradas:
            profesional = repo_profesional.obtener(r["IdProfesional"])
            consultorio = self.conn.execute(
                "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS NombreEdificio, e.DomicilioLocalidad "
                "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
                "WHERE c.IdConsultorio = ?",
                (r["IdConsultorio"],),
            ).fetchone()
            filas.append((r, profesional, consultorio))
        filas.sort(key=lambda t: (
            t[1]["IdCodigo"] or "" if t[1] else "",
            DIAS_SEMANA.index(t[0]["DiaSemana"]),
            t[0]["HoraInicio"],
            (t[2]["DomicilioLocalidad"] or "") if t[2] else "",
            (t[2]["NombreEdificio"] or "") if t[2] else "",
            (t[2]["Departamento"] or "") if t[2] else "",
            t[2]["NumeroConsultorio"] if t[2] else 0,
        ))
        if self._orden.columna is not None:
            filas.sort(key=self._clave_orden(self._orden.columna), reverse=not self._orden.ascendente)
        self._reservas = [t[0] for t in filas]

        mostrar_localidad = len({t[2]["DomicilioLocalidad"] for t in filas if t[2]}) > 1
        mostrar_edificio = len({t[2]["NombreEdificio"] for t in filas if t[2]}) > 1

        self.tabla.setRowCount(len(filas))
        for fila_idx, (r, profesional, consultorio) in enumerate(filas):
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(_texto_profesional(profesional) if profesional else "?"))
            texto_consultorio = (
                _texto_consultorio(consultorio, mostrar_localidad, mostrar_edificio) if consultorio else "?"
            )
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(texto_consultorio))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(r["DiaSemana"]))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(_fmt_horario(r["HoraInicio"], r["HoraFin"])))
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(_fmt_fecha(r["VigenciaInicio"])))
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem(_fmt_fecha(r["VigenciaFin"])))
        self.tabla.resizeColumnsToContents()
        self.tabla.setColumnWidth(0, max(self.tabla.columnWidth(0), _ANCHO_COL_PROFESIONAL))
        self._sincronizar_grilla()

    @staticmethod
    def _clave_orden(columna: int):
        claves = {
            0: lambda t: _texto_profesional(t[1]) if t[1] else "",
            1: lambda t: (t[2]["NumeroConsultorio"] if t[2] else 0),
            2: lambda t: DIAS_SEMANA.index(t[0]["DiaSemana"]),
            3: lambda t: t[0]["HoraInicio"],
            4: lambda t: t[0]["VigenciaInicio"] or "",
            5: lambda t: t[0]["VigenciaFin"] or "",
        }
        return claves[columna]

    def _cargar_edificios(self) -> None:
        _recargar_edificios(self.conn, self.combo_localidad, self.combo_edificio)
        self._cargar_unidades()

    def _cargar_unidades(self) -> None:
        _recargar_unidades(self.conn, self.combo_edificio, self.combo_unidad)
        self._cargar_consultorios()

    def _cargar_consultorios(self) -> None:
        _recargar_consultorios(self.conn, self.combo_unidad, self.combo_consultorio)
        self._sincronizar_grilla()

    def _seleccionar_ubicacion(self, id_consultorio: int) -> None:
        fila = self.conn.execute(
            "SELECT e.DomicilioLocalidad, u.IdEdificio, c.IdUnidad FROM Consultorio c "
            "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "WHERE c.IdConsultorio = ?", (id_consultorio,),
        ).fetchone()
        if fila is None:
            return
        indice_localidad = self.combo_localidad.findData(fila["DomicilioLocalidad"])
        if indice_localidad >= 0:
            self.combo_localidad.setCurrentIndex(indice_localidad)
        indice_edificio = self.combo_edificio.findData(fila["IdEdificio"])
        if indice_edificio >= 0:
            self.combo_edificio.setCurrentIndex(indice_edificio)
        indice_unidad = self.combo_unidad.findData(fila["IdUnidad"])
        if indice_unidad >= 0:
            self.combo_unidad.setCurrentIndex(indice_unidad)
        indice_consultorio = self.combo_consultorio.findData(id_consultorio)
        if indice_consultorio >= 0:
            self.combo_consultorio.setCurrentIndex(indice_consultorio)

    def _sincronizar_grilla(self) -> None:
        """La vista previa muestra el horario regular del profesional
        elegido — acotada a las unidades (con todos sus consultorios) y a
        los días en los que ya tiene algo reservado (vacía para un
        profesional nuevo, sin nada reservado todavía, o cuando no hay
        ninguno elegido), y con su propia reserva pintada de azul. Se
        vuelve a calcular también en cada refresco de la tabla (después
        de cada alta/baja), así queda siempre al día de lo que el
        profesional ya tiene reservado antes de seguir cargando."""
        id_profesional = self.combo_profesional.currentData()
        pares = pares_dia_unidad_con_reserva_vigente(self.conn, id_profesional)
        ids_unidad = sorted({u for _, u in pares})
        dias = sorted({d for d, _ in pares}, key=DIAS_SEMANA.index)
        self.grilla.filtrar_por_unidades(ids_unidad)
        self.grilla.filtrar_por_dias(dias)
        self.grilla.filtrar_por_pares_unidad_dia(pares)
        self.grilla.filtrar_por_profesional(id_profesional)
        self._actualizar_resumen_profesional(id_profesional)

    def _actualizar_resumen_profesional(self, id_profesional: int | None) -> None:
        resumen = calcular_resumen_profesional(self.conn, id_profesional)
        if resumen is None:
            self.etiqueta_horas_semanales.setText("Horas regulares semanales: —")
            self.etiqueta_horas_aisladas.setText("Horas aisladas mensuales: —")
            self.etiqueta_descuento.setText("% Descuento: —")
            self.etiqueta_vacaciones.setText("% Vacaciones disponible: —")
            return
        self.etiqueta_horas_semanales.setText(f"Horas regulares semanales: {_fmt_horas(resumen.horas_semanales)}")
        self.etiqueta_horas_aisladas.setText(f"Horas aisladas mensuales: {_fmt_horas(resumen.horas_aisladas_mensuales)}")
        self.etiqueta_descuento.setText(f"% Descuento: {resumen.porcentaje_descuento:.1f}%")
        self.etiqueta_vacaciones.setText(f"% Vacaciones disponible: {resumen.porcentaje_vacaciones_disponible:.1f}%")

    def _resetear_formulario(self) -> None:
        """Después de aplicar un cambio, deja el formulario listo y en
        blanco para cargar otro registro — aunque sea de otro
        profesional (el combo vuelve al placeholder en blanco, no queda
        pegado al que se acababa de cargar)."""
        self.combo_profesional.setCurrentIndex(0)
        if self.combo_localidad.count():
            self.combo_localidad.setCurrentIndex(0)
        self._cargar_edificios()
        for dia, check in self._checks_dia.items():
            check.setChecked(dia == "Lunes")
        self.spin_desde.setValue(9)
        self.spin_hasta.setValue(10)
        hoy = fecha_actual(self.conn)
        self.campo_vigencia_inicio.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.campo_vigencia_fin.setDate(_FECHA_SIN_DATO)
        self.combo_profesional.setFocus()

    def _dias_seleccionados(self) -> list[str]:
        return [dia for dia, check in self._checks_dia.items() if check.isChecked()]

    def _crear(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Crear reserva regular", "Elegí un profesional.")
            return
        dias = self._dias_seleccionados()
        if not dias:
            QMessageBox.warning(self, "Crear reserva regular", "Elegí al menos un día.")
            return
        advertencias_totales: list[str] = []
        algun_dia_creado = False
        for dia in dias:
            creado, advertencias = self._crear_un_dia(dia)
            if creado:
                algun_dia_creado = True
                advertencias_totales.extend(f"{dia}: {a}" for a in advertencias)
        if not algun_dia_creado:
            return
        if advertencias_totales:
            QMessageBox.information(self, "Reserva creada", "Reserva creada con avisos:\n" + "\n".join(advertencias_totales))
        self._ofrecer_resolver_lista_espera(id_profesional)
        regenerar_si_corresponde(self.conn, id_profesional=id_profesional, periodo=periodo_actual(self.conn))
        self.conn.commit()
        self.actualizar()
        self._resetear_formulario()
        self._sincronizar_grilla()

    def _crear_un_dia(self, dia_semana: str, forzar: bool = False) -> tuple[bool, list[str]]:
        datos = dict(
            id_profesional=self.combo_profesional.currentData(),
            id_consultorio=self.combo_consultorio.currentData(),
            dia_semana=dia_semana,
            hora_inicio=self.spin_desde.value(),
            hora_fin=self.spin_hasta.value(),
            vigencia_inicio=self.campo_vigencia_inicio.date().toPython().isoformat(),
            vigencia_fin=(
                None if self.campo_vigencia_fin.date() == _FECHA_SIN_DATO
                else self.campo_vigencia_fin.date().toPython().isoformat()
            ),
            forzar=forzar,
        )
        try:
            _id, advertencias = crear_reserva_regular(self.conn, **datos)
        except ConflictoBloqueanteError as error:
            confirmacion = QMessageBox.question(
                self, "Conflictos detectados",
                f"{dia_semana}: {error}\n\n¿Crear la reserva de todos modos?",
            )
            if confirmacion == QMessageBox.StandardButton.Yes:
                return self._crear_un_dia(dia_semana, forzar=True)
            return False, []
        except ValueError as error:
            QMessageBox.warning(self, "Crear reserva regular", f"{dia_semana}: {error}")
            return False, []
        self.conn.commit()
        return True, advertencias

    def _ofrecer_resolver_lista_espera(self, id_profesional: int) -> None:
        """DC-10 §2.2 paso 5: confirmar la reserva regular en F16 tiene que
        poder cerrar el pedido de Lista de espera que la originó. Con un
        solo pedido Activo del profesional alcanza con preguntar; con más
        de uno queda a criterio manual (no hay forma de saber cuál de
        todos se acaba de cubrir)."""
        pedidos = obtener_repositorio(self.conn, "ListaEspera").listar(
            IdProfesional=id_profesional, Estado="Activo",
        )
        if len(pedidos) != 1:
            return
        respuesta = QMessageBox.question(
            self, "Lista de espera",
            "Este profesional tiene un pedido activo en Lista de espera. "
            "¿Lo marcás como resuelto?",
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            marcar_resuelto(self.conn, pedidos[0]["IdPedido"])
            self.conn.commit()

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._reservas[filas[0].row()]

    def _finalizar_registro(self, reserva: sqlite3.Row, fecha_fin: str) -> None:
        obtener_repositorio(self.conn, "ReservaRegular").actualizar(
            reserva["IdReservaRegular"], VigenciaFin=fecha_fin
        )
        regenerar_si_corresponde(
            self.conn, id_profesional=reserva["IdProfesional"], periodo=periodo_actual(self.conn),
        )
        self.conn.commit()

    def _finalizar_vigencia(self) -> None:
        """"Finalizar reserva a fin de mes": el caso clásico (95% de las
        bajas se cierran a fin de mes), no el día exacto en que se
        gestiona la baja."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            return
        hoy = fecha_actual(self.conn)
        fin_de_mes = ultimo_dia_mes(hoy.year, hoy.month)
        self._finalizar_registro(reserva, fin_de_mes.isoformat())
        self.actualizar()
        self.combo_profesional.setFocus()

    def _deshacer_ultimo(self) -> None:
        """A diferencia de Vacaciones/Licencias/Ausencias, acá nunca se
        borra una reserva (podría desalinear una liquidación que ya la
        usó) — solo se le cierra la vigencia. "Deshacer" entonces solo
        cubre el caso seguro: si la última reserva regular cargada en el
        sistema (mayor IdReservaRegular) todavía nunca tuvo su vigencia
        cerrada, se puede borrar sin más porque es imposible que ya haya
        sido usada en una liquidación. Si ya tiene VigenciaFin (un
        Finalizar o Modificar posterior a su alta), ese tipo de cambio no
        se puede deshacer automáticamente — hay que corregirlo a mano."""
        todas = obtener_repositorio(self.conn, "ReservaRegular").listar()
        if not todas:
            QMessageBox.warning(self, "Deshacer último movimiento", "No hay reservas regulares cargadas para deshacer.")
            return
        ultima = max(todas, key=lambda r: r["IdReservaRegular"])
        if ultima["VigenciaFin"]:
            QMessageBox.warning(
                self, "Deshacer último movimiento",
                "La última reserva regular cargada ya tiene la vigencia cerrada (por un \"Finalizar\" o "
                "\"Modificar\" posterior) y ese tipo de cambio no se puede deshacer automáticamente. "
                "Corregilo a mano desde la tabla.",
            )
            return
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(ultima["IdProfesional"])
        respuesta = QMessageBox.question(
            self, "Deshacer último movimiento",
            "¿Deshacer el alta de la última reserva regular cargada en el sistema?\n"
            f"{_texto_profesional(profesional) if profesional else '?'}: "
            f"{ultima['DiaSemana']} {_fmt_horario(ultima['HoraInicio'], ultima['HoraFin'])} "
            f"desde {_fmt_fecha(ultima['VigenciaInicio'])}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        obtener_repositorio(self.conn, "ReservaRegular").eliminar(ultima["IdReservaRegular"])
        regenerar_si_corresponde(
            self.conn, id_profesional=ultima["IdProfesional"], periodo=periodo_actual(self.conn),
        )
        self.conn.commit()
        self.actualizar()
        self.combo_profesional.setFocus()

    def _modificar_seleccionada(self) -> None:
        """No se edita la fila histórica in-place (podría desalinear una
        liquidación ya emitida que la haya usado): finaliza su vigencia
        hoy (no a fin de mes — acá la versión nueva arranca hoy mismo, y
        dejarla superpuesta con la vieja hasta fin de mes rompería la
        validación de solapamiento) y precarga el formulario con sus
        datos para dar de alta la versión nueva. El operador ajusta lo
        que haga falta y confirma con "Crear reserva regular", como
        cualquier alta."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            QMessageBox.warning(self, "Modificar reserva", "Elegí una fila de la tabla para modificar.")
            return
        self._finalizar_registro(reserva, fecha_actual(self.conn).isoformat())
        self.actualizar()

        indice_profesional = self.combo_profesional.findData(reserva["IdProfesional"])
        if indice_profesional >= 0:
            self.combo_profesional.setCurrentIndex(indice_profesional)
        self._seleccionar_ubicacion(reserva["IdConsultorio"])
        for dia, check in self._checks_dia.items():
            check.setChecked(dia == reserva["DiaSemana"])
        self.spin_desde.setValue(reserva["HoraInicio"])
        self.spin_hasta.setValue(reserva["HoraFin"])
        hoy = fecha_actual(self.conn)
        self.campo_vigencia_inicio.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.campo_vigencia_fin.setDate(_FECHA_SIN_DATO)
        self._sincronizar_grilla()


class _PanelReservasAisladas(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._reservas: list[sqlite3.Row] = []
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
        for id_, etiqueta in _opciones_profesional(self.conn, _CATEGORIAS_AISLADAS):
            self.combo_profesional.addItem(etiqueta, id_)
        self.combo_profesional.currentIndexChanged.connect(self.actualizar)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_localidad = QComboBox()
        for valor, etiqueta in _opciones_localidad(self.conn):
            self.combo_localidad.addItem(etiqueta, valor)
        self.combo_localidad.currentIndexChanged.connect(self._cargar_edificios)
        form.addWidget(QLabel("Localidad"))
        form.addWidget(self.combo_localidad)

        self.combo_edificio = QComboBox()
        self.combo_edificio.currentIndexChanged.connect(self._cargar_unidades)
        form.addWidget(QLabel("Edificio"))
        form.addWidget(self.combo_edificio)

        self.combo_unidad = QComboBox()
        self.combo_unidad.currentIndexChanged.connect(self._cargar_consultorios)
        form.addWidget(QLabel("Unidad"))
        form.addWidget(self.combo_unidad)

        self.combo_consultorio = QComboBox()
        self.combo_consultorio.currentIndexChanged.connect(self._sincronizar_grilla)
        form.addWidget(QLabel("Consultorio"))
        form.addWidget(self.combo_consultorio)

        self.campo_fecha = QDateEdit()
        self.campo_fecha.setDisplayFormat(_FORMATO_FECHA)
        self.campo_fecha.setCalendarPopup(True)
        form.addWidget(QLabel("Fecha"))
        form.addWidget(self.campo_fecha)

        fila_horario = QHBoxLayout()
        self.spin_desde = _SpinHorario()
        self.spin_desde.setRange(0, 23)
        self.spin_desde.setSingleStep(0.5)
        self.spin_desde.setValue(9)
        self.spin_hasta = _SpinHorario()
        self.spin_hasta.setRange(0.5, 24)
        self.spin_hasta.setSingleStep(0.5)
        self.spin_hasta.setValue(10)
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_desde)
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hasta)
        form.addLayout(fila_horario)

        self.casilla_recargo = QCheckBox("Aplica recargo")
        form.addWidget(self.casilla_recargo)

        self.casilla_reubicacion = QCheckBox("Es reubicación (compensa una ausencia del profesional, no genera cargo)")
        self.casilla_reubicacion.stateChanged.connect(self._alternar_reubicacion)
        form.addWidget(self.casilla_reubicacion)

        self.contenedor_reubicacion = QWidget()
        layout_reubicacion = QVBoxLayout(self.contenedor_reubicacion)
        layout_reubicacion.setContentsMargins(0, 0, 0, 0)
        layout_reubicacion.addWidget(QLabel("Horario que no va a usar"))
        self.combo_horario_no_usado = QComboBox()
        layout_reubicacion.addWidget(self.combo_horario_no_usado)
        layout_reubicacion.addWidget(QLabel("Fecha que falta"))
        self.campo_fecha_ausencia = QDateEdit()
        self.campo_fecha_ausencia.setDisplayFormat(_FORMATO_FECHA)
        self.campo_fecha_ausencia.setCalendarPopup(True)
        layout_reubicacion.addWidget(self.campo_fecha_ausencia)
        self.contenedor_reubicacion.setVisible(False)
        form.addWidget(self.contenedor_reubicacion)

        boton_crear = QPushButton("Crear reserva aislada")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.clicked.connect(self._crear)
        form.addWidget(boton_crear)

        linea_separadora = QFrame()
        linea_separadora.setFrameShape(QFrame.Shape.HLine)
        linea_separadora.setFrameShadow(QFrame.Shadow.Sunken)
        form.addWidget(linea_separadora)

        form.addWidget(QLabel("Datos complementarios del profesional"))
        self.etiqueta_horas_semanales = QLabel()
        self.etiqueta_horas_aisladas = QLabel()
        self.etiqueta_descuento = QLabel()
        self.etiqueta_vacaciones = QLabel()
        form.addWidget(self.etiqueta_horas_semanales)
        form.addWidget(self.etiqueta_horas_aisladas)
        form.addWidget(self.etiqueta_descuento)
        form.addWidget(self.etiqueta_vacaciones)

        form.addStretch()
        splitter_superior.addWidget(panel_form)

        grupo_grilla = QGroupBox("Vista previa: grilla operativa")
        layout_grupo_grilla = QVBoxLayout(grupo_grilla)
        self.grilla = GrillaOperativaWidget(self.conn)
        self.grilla.combo_modo.setCurrentIndex(self.grilla.combo_modo.findData("aislada"))
        layout_grupo_grilla.addWidget(self.grilla)
        splitter_superior.addWidget(grupo_grilla)

        splitter_superior.setStretchFactor(0, 0)
        splitter_superior.setStretchFactor(1, 1)
        layout.addWidget(splitter_superior, stretch=2)

        panel_tabla = QGroupBox("Reservas aisladas")
        layout_tabla = QVBoxLayout(panel_tabla)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(8)
        self.tabla.setHorizontalHeaderLabels(
            ["Profesional", "Consultorio", "Día", "Fecha", "Horario", "Reubicación", "Estado", "Valor"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout_tabla.addWidget(self.tabla, stretch=1)

        fila_acciones = QHBoxLayout()
        boton_modificar = QPushButton("Modificar reserva")
        boton_modificar.clicked.connect(self._modificar_seleccionada)
        fila_acciones.addWidget(boton_modificar)
        boton_cancelar = QPushButton("Cancelar reserva")
        boton_cancelar.clicked.connect(self._cancelar)
        fila_acciones.addWidget(boton_cancelar)
        fila_acciones.addStretch()
        layout_tabla.addLayout(fila_acciones)
        layout.addWidget(panel_tabla, stretch=1)

        hoy = fecha_actual(self.conn)
        self.campo_fecha.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.campo_fecha_ausencia.setDate(QDate(hoy.year, hoy.month, hoy.day))

        scroll.setWidget(contenido)
        layout_externo.addWidget(scroll)
        self._cargar_edificios()

    def _cargar_edificios(self) -> None:
        _recargar_edificios(self.conn, self.combo_localidad, self.combo_edificio)
        self._cargar_unidades()

    def _cargar_unidades(self) -> None:
        _recargar_unidades(self.conn, self.combo_edificio, self.combo_unidad)
        self._cargar_consultorios()

    def _cargar_consultorios(self) -> None:
        _recargar_consultorios(self.conn, self.combo_unidad, self.combo_consultorio)
        self._sincronizar_grilla()

    def _seleccionar_ubicacion(self, id_consultorio: int) -> None:
        fila = self.conn.execute(
            "SELECT e.DomicilioLocalidad, u.IdEdificio, c.IdUnidad FROM Consultorio c "
            "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "WHERE c.IdConsultorio = ?", (id_consultorio,),
        ).fetchone()
        if fila is None:
            return
        indice_localidad = self.combo_localidad.findData(fila["DomicilioLocalidad"])
        if indice_localidad >= 0:
            self.combo_localidad.setCurrentIndex(indice_localidad)
        indice_edificio = self.combo_edificio.findData(fila["IdEdificio"])
        if indice_edificio >= 0:
            self.combo_edificio.setCurrentIndex(indice_edificio)
        indice_unidad = self.combo_unidad.findData(fila["IdUnidad"])
        if indice_unidad >= 0:
            self.combo_unidad.setCurrentIndex(indice_unidad)
        indice_consultorio = self.combo_consultorio.findData(id_consultorio)
        if indice_consultorio >= 0:
            self.combo_consultorio.setCurrentIndex(indice_consultorio)

    def _sincronizar_grilla(self) -> None:
        """Mismo criterio que en Reservas regulares, pero considerando
        también las aisladas del profesional (puede no tener nunca una
        reserva regular, ej. categoría A): acotada a las unidades y días
        en los que ya tiene algo reservado, con su propia reserva
        pintada de azul — en modo "Reservas aisladas" porque acá
        interesa ver qué está libre AHORA, no los conflictos futuros."""
        id_profesional = self.combo_profesional.currentData()
        pares = pares_dia_unidad_con_reserva(self.conn, id_profesional)
        ids_unidad = sorted({u for _, u in pares})
        dias = sorted({d for d, _ in pares}, key=DIAS_SEMANA.index)
        self.grilla.filtrar_por_unidades(ids_unidad)
        self.grilla.filtrar_por_dias(dias)
        self.grilla.filtrar_por_pares_unidad_dia(pares)
        self.grilla.filtrar_por_profesional(id_profesional)
        self._actualizar_resumen_profesional(id_profesional)
        if self.casilla_reubicacion.isChecked():
            self._cargar_horarios_no_usados()

    def _actualizar_resumen_profesional(self, id_profesional: int | None) -> None:
        resumen = calcular_resumen_profesional(self.conn, id_profesional)
        if resumen is None:
            self.etiqueta_horas_semanales.setText("Horas regulares semanales: —")
            self.etiqueta_horas_aisladas.setText("Horas aisladas mensuales: —")
            self.etiqueta_descuento.setText("% Descuento: —")
            self.etiqueta_vacaciones.setText("% Vacaciones disponible: —")
            return
        self.etiqueta_horas_semanales.setText(f"Horas regulares semanales: {_fmt_horas(resumen.horas_semanales)}")
        self.etiqueta_horas_aisladas.setText(f"Horas aisladas mensuales: {_fmt_horas(resumen.horas_aisladas_mensuales)}")
        self.etiqueta_descuento.setText(f"% Descuento: {resumen.porcentaje_descuento:.1f}%")
        self.etiqueta_vacaciones.setText(f"% Vacaciones disponible: {resumen.porcentaje_vacaciones_disponible:.1f}%")

    def _alternar_reubicacion(self) -> None:
        marcado = self.casilla_reubicacion.isChecked()
        self.contenedor_reubicacion.setVisible(marcado)
        if marcado:
            self._cargar_horarios_no_usados()

    def _cargar_horarios_no_usados(self) -> None:
        """Al marcar "Es reubicación", ofrece elegir cuál de los horarios
        regulares vigentes del profesional no va a usar esta vez — para
        dejarlo registrado como Ausencia de ese consultorio en esa fecha
        puntual (así queda libre para que otro profesional lo tome como
        aislada), sin afectar la reserva regular ni la grilla visual."""
        id_profesional = self.combo_profesional.currentData()
        self.combo_horario_no_usado.clear()
        self.combo_horario_no_usado.addItem("Sin especificar", None)
        for id_consultorio, etiqueta in _opciones_horario_regular(self.conn, id_profesional):
            self.combo_horario_no_usado.addItem(etiqueta, id_consultorio)

    def _resetear_formulario(self) -> None:
        """Igual que en Reservas regulares: después de aplicar un cambio,
        deja el formulario listo y en blanco para cargar otro registro,
        aunque sea de otro profesional."""
        self.combo_profesional.setCurrentIndex(0)
        if self.combo_localidad.count():
            self.combo_localidad.setCurrentIndex(0)
        self._cargar_edificios()
        self.spin_desde.setValue(9)
        self.spin_hasta.setValue(10)
        hoy = fecha_actual(self.conn)
        self.campo_fecha.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.campo_fecha_ausencia.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.casilla_recargo.setChecked(False)
        self.casilla_reubicacion.setChecked(False)

    def _valor_reserva(self, reserva: sqlite3.Row, valor_hora_aislada: float, recargo_pct: float) -> str:
        """Vacío si la reserva cae en un período posterior al actual —
        todavía no corresponde mostrarle un valor de facturación."""
        if reserva["Fecha"][:7] > periodo_actual(self.conn):
            return ""
        if reserva["EsReubicacion"]:
            return formatear_moneda(0.0)
        monto = (reserva["HoraFin"] - reserva["HoraInicio"]) * valor_hora_aislada
        if reserva["AplicaRecargo"]:
            monto *= 1 + recargo_pct / 100
        return formatear_moneda(monto)

    def actualizar(self) -> None:
        """Sin profesional elegido, muestra todas las reservas aisladas de
        todos los profesionales; con uno elegido, se acota a las de ese
        profesional únicamente (incluida su historia — canceladas
        incluidas — para poder revisarla). Orden: código del profesional,
        fecha y hora inicial."""
        id_profesional_filtro = self.combo_profesional.currentData()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        todas = obtener_repositorio(self.conn, "ReservaAislada").listar()
        if id_profesional_filtro is not None:
            filtradas = [r for r in todas if r["IdProfesional"] == id_profesional_filtro]
        else:
            filtradas = todas

        cfg = self.conn.execute(
            "SELECT RecargoPorcentajeAisladas FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        recargo_pct = cfg["RecargoPorcentajeAisladas"] if cfg else 0.0

        filas: list[tuple[sqlite3.Row, sqlite3.Row | None, sqlite3.Row | None]] = []
        for r in filtradas:
            profesional = repo_profesional.obtener(r["IdProfesional"])
            consultorio = self.conn.execute(
                "SELECT c.NumeroConsultorio, c.ValorHoraAisladaActual, u.Departamento, "
                "e.Nombre AS NombreEdificio, e.DomicilioLocalidad FROM Consultorio c "
                "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
                "WHERE c.IdConsultorio = ?",
                (r["IdConsultorio"],),
            ).fetchone()
            filas.append((r, profesional, consultorio))
        filas.sort(key=lambda t: (
            t[1]["IdCodigo"] or "" if t[1] else "",
            t[0]["Fecha"],
            t[0]["HoraInicio"],
        ))
        self._reservas = [t[0] for t in filas]

        mostrar_localidad = len({t[2]["DomicilioLocalidad"] for t in filas if t[2]}) > 1
        mostrar_edificio = len({t[2]["NombreEdificio"] for t in filas if t[2]}) > 1

        self.tabla.setRowCount(len(filas))
        for fila_idx, (r, profesional, consultorio) in enumerate(filas):
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(_texto_profesional(profesional) if profesional else "?"))
            texto_consultorio = (
                _texto_consultorio(consultorio, mostrar_localidad, mostrar_edificio) if consultorio else "?"
            )
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(texto_consultorio))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(fecha_a_dia_semana(date.fromisoformat(r["Fecha"]))))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(_fmt_fecha(r["Fecha"])))
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(_fmt_horario(r["HoraInicio"], r["HoraFin"])))
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem("Sí" if r["EsReubicacion"] else "No"))
            self.tabla.setItem(fila_idx, 6, QTableWidgetItem(r["Estado"]))
            valor_hora = consultorio["ValorHoraAisladaActual"] if consultorio else 0.0
            self.tabla.setItem(fila_idx, 7, QTableWidgetItem(self._valor_reserva(r, valor_hora, recargo_pct)))
        self.tabla.resizeColumnsToContents()
        self.tabla.setColumnWidth(0, max(self.tabla.columnWidth(0), _ANCHO_COL_PROFESIONAL))
        self._sincronizar_grilla()
        self.grilla.actualizar()

    def _crear(self, forzar: bool = False) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Crear reserva aislada", "Elegí un profesional.")
            return
        fecha = self.campo_fecha.date().toPython().isoformat()
        if not forzar and not confirmar_si_fecha_es_mes_anterior(self, self.conn, fecha):
            return
        datos = dict(
            id_profesional=id_profesional,
            id_consultorio=self.combo_consultorio.currentData(),
            fecha=fecha,
            hora_inicio=self.spin_desde.value(),
            hora_fin=self.spin_hasta.value(),
            aplica_recargo=self.casilla_recargo.isChecked(),
            es_reubicacion=self.casilla_reubicacion.isChecked(),
            forzar=forzar,
        )
        try:
            _id, advertencias = crear_reserva_aislada(self.conn, **datos)
        except ConflictoBloqueanteError as error:
            confirmacion = QMessageBox.question(
                self, "Conflictos detectados",
                f"{error}\n\n¿Crear la reserva de todos modos?",
            )
            if confirmacion == QMessageBox.StandardButton.Yes:
                self._crear(forzar=True)
            return
        except ValueError as error:
            QMessageBox.warning(self, "Crear reserva aislada", str(error))
            return
        self.conn.commit()
        if datos["es_reubicacion"]:
            self._registrar_ausencia_por_reubicacion(id_profesional, fecha, _id)
        if advertencias:
            QMessageBox.information(self, "Reserva creada", "Reserva creada con avisos:\n" + "\n".join(advertencias))
        self._copiar_mensaje_detalle(datos["id_profesional"], fecha)
        self.actualizar()
        self._resetear_formulario()
        self._sincronizar_grilla()

    def _registrar_ausencia_por_reubicacion(self, id_profesional: int, fecha_aislada: str, id_reserva_aislada: int) -> None:
        """Si al marcar "Es reubicación" el operador indicó cuál de los
        horarios regulares del profesional no va a usar, deja registrada
        la Ausencia de ese consultorio en la fecha indicada — vinculada a
        la reserva aislada que la originó, así queda libre para que otro
        profesional lo tome como aislada, sin afectar la reserva regular
        ni la grilla visual (mismo criterio que ya usa la pantalla de
        Ausencias)."""
        id_consultorio_no_usado = self.combo_horario_no_usado.currentData()
        if id_consultorio_no_usado is None:
            return
        fecha_ausencia = self.campo_fecha_ausencia.date().toPython().isoformat()
        crear_ausencia(
            self.conn, id_profesional=id_profesional, fecha_desde=fecha_ausencia, fecha_hasta=fecha_ausencia,
            id_consultorio=id_consultorio_no_usado, motivo="Reubicación",
            observacion=f"Compensada por la reserva aislada del {fecha_aislada}",
            id_reserva_aislada=id_reserva_aislada,
        )
        self.conn.commit()

    def _copiar_mensaje_detalle(self, id_profesional: int, fecha: str) -> None:
        """DC-02/DC-03/DC-04: confirmar, cancelar o modificar una reserva
        aislada carga sola el mensaje de detalle al portapapeles — sin
        reemplazar la posibilidad de volver a generarlo a mano desde el
        Centro de mensajería."""
        try:
            texto = mensaje_detalle_reserva_aislada(self.conn, id_profesional=id_profesional, periodo=fecha[:7])
        except ValueError:
            return
        QGuiApplication.clipboard().setText(texto)

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._reservas[filas[0].row()]

    def _cancelar_registro(self, reserva: sqlite3.Row, titulo: str) -> bool:
        try:
            requiere_aviso = cancelar_reserva_aislada(self.conn, reserva["IdReservaAislada"])
        except ValueError as error:
            QMessageBox.warning(self, titulo, str(error))
            return False
        self.conn.commit()
        if requiere_aviso:
            QMessageBox.information(self, titulo, "Cancelada el mismo día: avisar al profesional.")
        self._copiar_mensaje_detalle(reserva["IdProfesional"], reserva["Fecha"])
        self.actualizar()
        return True

    def _cancelar(self) -> None:
        reserva = self._fila_seleccionada()
        if reserva is None:
            return
        self._cancelar_registro(reserva, "Cancelar reserva")

    def _modificar_seleccionada(self) -> None:
        """Mismo criterio que en Reservas regulares: no se edita la fila
        histórica in-place (podría desalinear una liquidación ya
        emitida que la haya usado) — se cancela la reserva aislada
        seleccionada (queda su historial, no se borra) y se precarga el
        formulario con sus datos para dar de alta la versión corregida.
        El operador ajusta lo que haga falta (ej. una hora más de las
        que le habían encargado en un principio) y confirma con "Crear
        reserva aislada", como cualquier alta."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            QMessageBox.warning(self, "Modificar reserva", "Elegí una fila de la tabla para modificar.")
            return
        if not self._cancelar_registro(reserva, "Modificar reserva"):
            return

        indice_profesional = self.combo_profesional.findData(reserva["IdProfesional"])
        if indice_profesional >= 0:
            self.combo_profesional.setCurrentIndex(indice_profesional)
        self._seleccionar_ubicacion(reserva["IdConsultorio"])
        self.campo_fecha.setDate(QDate.fromString(reserva["Fecha"], "yyyy-MM-dd"))
        self.spin_desde.setValue(reserva["HoraInicio"])
        self.spin_hasta.setValue(reserva["HoraFin"])
        self.casilla_recargo.setChecked(bool(reserva["AplicaRecargo"]))
        self.casilla_reubicacion.setChecked(bool(reserva["EsReubicacion"]))
        self._sincronizar_grilla()
