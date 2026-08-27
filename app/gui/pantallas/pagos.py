"""Pagos y planes de pago (secciones 3.6 y 3.23, DC-09 §3 y §8): registrar
pagos y administrar planes de pago reusando app.negocio.pagos, para que
los descuentos de saldo (SaldoCuentaActual/SaldoCuentaAnterior según el
período imputado) y la generación de cuotas se calculen siempre igual que
por código."""
from __future__ import annotations

import sqlite3
from datetime import datetime

from PySide6.QtCore import QDateTime, QLocale, Qt
from PySide6.QtGui import QColor, QValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.dialogos import confirmar_si_periodo_imputado_es_anterior
from app.gui.pantallas.reservas import _opciones_profesional, _texto_profesional
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.negocio.dias import fecha_a_dia_semana, periodo_actual
from app.negocio.formato import formatear_moneda
from app.negocio.liquidaciones import regenerar_si_corresponde
from app.negocio.listas_editables import valores_lista
from app.negocio.pagos import (
    abrir_tanda_sobres,
    cancelar_plan,
    cerrar_tanda_sobres,
    crear_plan_pago,
    deshacer_ultimo_pago,
    modificar_pago,
    programar_refinanciacion,
    refinanciar_plan,
    registrar_pago,
    subtotal_tanda_sobres,
    suspender_descuento_periodo,
    tanda_sobres_abierta,
    tanda_sobres_es_de_otro_dia,
)
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


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _fmt_fecha_hora_larga(iso: str | None) -> str:
    """"lunes 10-08-2026 14:30hs" — mismo criterio de nombre de día en
    español que usa el resto de la app (no depende del locale del SO)."""
    if not iso:
        return ""
    dt = datetime.fromisoformat(iso)
    dia = fecha_a_dia_semana(dt.date()).lower()
    return f"{dia} {dt.day:02d}-{dt.month:02d}-{dt.year} {dt.hour:02d}:{dt.minute:02d}hs"


class _SpinMonto(QDoubleSpinBox):
    """QDoubleSpinBox que se muestra como moneda ("$ 1.234,56", negativo
    con "-$ ..." y en rojo) en vez del formato con coma como separador de
    miles que arrastra Qt por defecto — internamente sigue siendo el
    mismo float con signo que espera `app.negocio.pagos.registrar_pago`
    (negativo resta de la cuenta del profesional, positivo suma)."""

    def textFromValue(self, value: float) -> str:  # noqa: N802 (nombre impuesto por Qt)
        return formatear_moneda(value)

    def valueFromText(self, text: str) -> float:  # noqa: N802
        texto = text.strip().replace("$", "").replace(".", "").replace(",", ".").strip()
        try:
            return float(texto) if texto else 0.0
        except ValueError:
            return 0.0

    def validate(self, text: str, pos: int):  # noqa: N802
        return (QValidator.State.Acceptable, text, pos)


class PantallaPagos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Pagos")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        pestanas = QTabWidget()
        self.panel_pagos = _PanelRegistrarPago(conn)
        self.panel_planes = _PanelPlanesPago(conn)
        pestanas.addTab(self.panel_pagos, "Registrar pago")
        pestanas.addTab(self.panel_planes, "Planes de pago")
        layout.addWidget(pestanas, stretch=1)

    def actualizar(self) -> None:
        self.panel_pagos.actualizar()
        self.panel_planes.actualizar()


class _PanelRegistrarPago(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._registros: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()
        self.combo_profesional.setFocus()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)

        self.campo_periodo = QLineEdit()
        self.campo_periodo.setPlaceholderText("aaaa-mm")
        self.campo_periodo.setText(periodo_actual(self.conn))
        form.addWidget(QLabel("Período imputado"))
        form.addWidget(self.campo_periodo)

        self.combo_profesional = QComboBox()
        self.combo_profesional.setMinimumWidth(_ANCHO_COMBO_PROFESIONAL)
        self.combo_profesional.addItem("Seleccionar profesional…", None)
        for id_, etiqueta in _opciones_profesional(self.conn, _CATEGORIAS_TODAS):
            self.combo_profesional.addItem(etiqueta, id_)
        self.combo_profesional.currentIndexChanged.connect(self._actualizar_saldos)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.spin_monto = _SpinMonto()
        self.spin_monto.setRange(-100_000_000, 100_000_000)
        self.spin_monto.setDecimals(2)
        self.spin_monto.valueChanged.connect(self._actualizar_color_monto)
        self.spin_monto.valueChanged.connect(self._actualizar_saldos)
        form.addWidget(QLabel("Monto"))
        form.addWidget(self.spin_monto)

        self.combo_medio_pago = QComboBox()
        self.combo_medio_pago.setEditable(True)
        for valor in valores_lista(self.conn, "MedioPago"):
            self.combo_medio_pago.addItem(valor)
        if self.combo_medio_pago.findText("Sobre en buzón") >= 0:
            self.combo_medio_pago.setCurrentText("Sobre en buzón")
        self.combo_medio_pago.currentTextChanged.connect(self._actualizar_visibilidad_segun_medio_pago)
        form.addWidget(QLabel("Medio de pago"))
        form.addWidget(self.combo_medio_pago)

        self.combo_cuenta_receptora = QComboBox()
        self.combo_cuenta_receptora.setEditable(True)
        for valor in valores_lista(self.conn, "CuentaReceptora"):
            self.combo_cuenta_receptora.addItem(valor)
        form.addWidget(QLabel("Cuenta receptora"))
        form.addWidget(self.combo_cuenta_receptora)

        self.boton_registrar = QPushButton("Registrar pago")
        self.boton_registrar.setObjectName("botonPrimario")
        self.boton_registrar.clicked.connect(self._registrar)
        form.addWidget(self.boton_registrar)
        boton_modificar = QPushButton("Modificar pago")
        boton_modificar.clicked.connect(self._modificar)
        form.addWidget(boton_modificar)
        boton_deshacer = QPushButton("Deshacer último movimiento")
        boton_deshacer.clicked.connect(self._deshacer_ultimo)
        form.addWidget(boton_deshacer)

        form.addWidget(_linea_divisoria())
        self.etiqueta_saldo_actual = QLabel()
        self.etiqueta_nuevo_saldo = QLabel()
        form.addWidget(self.etiqueta_saldo_actual)
        form.addWidget(self.etiqueta_nuevo_saldo)

        form.addWidget(_linea_divisoria())
        form.addWidget(QLabel("Tanda de sobres"))
        self.etiqueta_estado_tanda = QLabel()
        self.etiqueta_total_tanda = QLabel()
        form.addWidget(self.etiqueta_estado_tanda)
        form.addWidget(self.etiqueta_total_tanda)
        fila_tanda = QHBoxLayout()
        boton_iniciar_tanda = QPushButton("Iniciar tanda")
        boton_iniciar_tanda.clicked.connect(self._iniciar_tanda)
        boton_cerrar_tanda = QPushButton("Cerrar tanda")
        boton_cerrar_tanda.clicked.connect(self._cerrar_tanda)
        fila_tanda.addWidget(boton_iniciar_tanda)
        fila_tanda.addWidget(boton_cerrar_tanda)
        form.addLayout(fila_tanda)

        form.addWidget(_linea_divisoria())
        self.campo_recogida_sobres = QDateTimeEdit()
        self.campo_recogida_sobres.setCalendarPopup(True)
        self.campo_recogida_sobres.setLocale(QLocale(QLocale.Language.Spanish))
        self.campo_recogida_sobres.setDisplayFormat("dddd dd-MM-yyyy HH:mm'hs'")
        form.addWidget(QLabel("Fecha y hora de recogida de sobres"))
        form.addWidget(self.campo_recogida_sobres)
        self._precargar_recogida_sobres()

        form.addStretch()
        splitter.addWidget(panel_form)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(10)
        self.tabla.setHorizontalHeaderLabels([
            "Fecha de carga", "Profesional", "Período imputado", "Monto", "Medio de pago", "Cuenta receptora",
            "Saldo anterior", "Nuevo saldo", "Registro modificado", "Es ajuste",
        ])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.itemSelectionChanged.connect(self._precargar_seleccion)
        splitter.addWidget(self.tabla)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self._actualizar_visibilidad_segun_medio_pago()
        self._actualizar_color_monto()
        self._actualizar_saldos()
        self._foco = instalar_enter_avanza_foco([
            self.campo_periodo, self.combo_profesional, self.spin_monto, self.combo_medio_pago,
            self.combo_cuenta_receptora, self.boton_registrar,
        ])

    def _es_sobre(self) -> bool:
        return "sobre" in self.combo_medio_pago.currentText().lower()

    def _actualizar_visibilidad_segun_medio_pago(self, *_args) -> None:
        """Sección 3.6: CuentaReceptora solo se puede completar para
        transferencias — para cualquier otro medio queda deshabilitada
        (en gris) y sin nada seleccionado, y el Enter/Tab la saltea sola
        (la salteamos también programáticamente si tenía foco)."""
        es_transferencia = "transferencia" in self.combo_medio_pago.currentText().lower()
        tenia_foco = self.combo_cuenta_receptora.hasFocus() or (
            self.combo_cuenta_receptora.lineEdit() is not None and self.combo_cuenta_receptora.lineEdit().hasFocus()
        )
        self.combo_cuenta_receptora.setEnabled(es_transferencia)
        if not es_transferencia:
            self.combo_cuenta_receptora.setCurrentIndex(-1)
            if tenia_foco:
                self.campo_recogida_sobres.setFocus()

    def _actualizar_color_monto(self) -> None:
        self.spin_monto.setStyleSheet("color: red;" if self.spin_monto.value() < 0 else "")

    def _fmt_saldo_label(self, prefijo: str, valor: float) -> str:
        color = "red" if valor < 0 else "black"
        return f'{prefijo}: <span style="color:{color};">{formatear_moneda(valor)}</span>'

    def _actualizar_saldos(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            self.etiqueta_saldo_actual.setText("Saldo actual: —")
            self.etiqueta_nuevo_saldo.setText("Nuevo saldo: —")
            return
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(id_profesional)
        saldo_actual = (profesional["SaldoCuentaActual"] or 0.0) if profesional else 0.0
        nuevo_saldo = saldo_actual + self.spin_monto.value()
        self.etiqueta_saldo_actual.setText(self._fmt_saldo_label("Saldo actual", saldo_actual))
        self.etiqueta_nuevo_saldo.setText(self._fmt_saldo_label("Nuevo saldo", nuevo_saldo))

    def _precargar_recogida_sobres(self) -> None:
        cfg = self.conn.execute(
            "SELECT FechaHoraRecogidaSobres FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        valor = cfg["FechaHoraRecogidaSobres"] if cfg else None
        dt = QDateTime.fromString(valor, Qt.DateFormat.ISODate) if valor else QDateTime()
        self.campo_recogida_sobres.setDateTime(dt if dt.isValid() else QDateTime.currentDateTime())

    def _actualizar_tanda(self) -> None:
        apertura = tanda_sobres_abierta(self.conn)
        if apertura is None:
            self.etiqueta_estado_tanda.setText("Sin tanda abierta")
            self.etiqueta_total_tanda.setText(f"Total tanda: {formatear_moneda(0)}")
            return
        self.etiqueta_estado_tanda.setText("Con tanda abierta")
        subtotal = subtotal_tanda_sobres(self.conn, apertura)
        self.etiqueta_total_tanda.setText(f"Total tanda: {formatear_moneda(subtotal)}")

    def _poner_item_monto(self, fila: int, col: int, valor: float | None) -> None:
        item = QTableWidgetItem(formatear_moneda(valor or 0.0))
        if (valor or 0.0) < 0:
            item.setForeground(QColor("red"))
        self.tabla.setItem(fila, col, item)

    def actualizar(self) -> None:
        """Orden: fecha y hora de carga, lo más nuevo arriba (y, dentro
        de un mismo instante, por profesional) — IdPago ya es un orden
        total equivalente a FechaHoraCarga, así que alcanza con eso."""
        todos = obtener_repositorio(self.conn, "HistorialPagos").listar()
        cache = {p["IdProfesional"]: p for p in obtener_repositorio(self.conn, "Profesional").listar()}
        filas = sorted(
            todos,
            key=lambda r: (-r["IdPago"], _texto_profesional(cache[r["IdProfesional"]]) if r["IdProfesional"] in cache else ""),
        )
        self._registros = filas

        self.tabla.setRowCount(len(filas))
        for i, r in enumerate(filas):
            profesional = cache.get(r["IdProfesional"])
            self.tabla.setItem(i, 0, QTableWidgetItem(_fmt_fecha_hora_larga(r["FechaHoraCarga"])))
            self.tabla.setItem(i, 1, QTableWidgetItem(_texto_profesional(profesional) if profesional else "?"))
            self.tabla.setItem(i, 2, QTableWidgetItem(r["PeriodoImputado"] or ""))
            self._poner_item_monto(i, 3, r["Monto"])
            self.tabla.setItem(i, 4, QTableWidgetItem(r["MedioPago"] or ""))
            self.tabla.setItem(i, 5, QTableWidgetItem(r["CuentaReceptora"] or ""))
            self._poner_item_monto(i, 6, r["SaldoAnterior"])
            self._poner_item_monto(i, 7, r["SaldoNuevo"])
            self.tabla.setItem(i, 8, QTableWidgetItem("Sí" if r["RegistroModificado"] else "No"))
            self.tabla.setItem(i, 9, QTableWidgetItem("Sí" if r["EsAjuste"] else "No"))
        self.tabla.resizeColumnsToContents()
        self.tabla.setColumnWidth(1, max(self.tabla.columnWidth(1), _ANCHO_COL_PROFESIONAL))
        self._actualizar_tanda()
        self._actualizar_saldos()

    def _resetear_formulario(self) -> None:
        self.combo_profesional.setCurrentIndex(0)
        self.campo_periodo.setText(periodo_actual(self.conn))
        self.spin_monto.setValue(0)
        if self.combo_medio_pago.findText("Sobre en buzón") >= 0:
            self.combo_medio_pago.setCurrentText("Sobre en buzón")
        self.combo_profesional.setFocus()

    def _registrar(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        periodo_imputado = self.campo_periodo.text().strip()
        monto = self.spin_monto.value()
        medio_pago = self.combo_medio_pago.currentText().strip()
        if id_profesional is None or not periodo_imputado or monto == 0 or not medio_pago:
            QMessageBox.warning(self, "Registrar pago", "Completá profesional, período, monto y medio de pago.")
            return
        es_transferencia = "transferencia" in medio_pago.lower()
        if es_transferencia and not self.combo_cuenta_receptora.currentText().strip():
            QMessageBox.warning(self, "Registrar pago", "Elegí una cuenta receptora para la transferencia.")
            return
        if not confirmar_si_periodo_imputado_es_anterior(self, self.conn, periodo_imputado):
            return
        es_sobre = self._es_sobre()
        recogida_sobres = (
            self.campo_recogida_sobres.dateTime().toString(Qt.DateFormat.ISODate) if es_sobre else None
        )
        apertura_buzon = tanda_sobres_abierta(self.conn) if es_sobre else None
        try:
            _id_pago, cruza_tolerancia = registrar_pago(
                self.conn, id_profesional=id_profesional, monto=monto, medio_pago=medio_pago,
                cuenta_receptora=self.combo_cuenta_receptora.currentText().strip() if es_transferencia else None,
                periodo_imputado=periodo_imputado,
                fecha_hora_recogida_sobres=recogida_sobres, fecha_hora_apertura_buzon=apertura_buzon,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Registrar pago", str(error))
            return
        if cruza_tolerancia:
            self._preguntar_restablecer_descuento(id_profesional, periodo_imputado)
        if periodo_imputado < periodo_actual(self.conn):
            regenerar_si_corresponde(self.conn, id_profesional=id_profesional, periodo=periodo_imputado)
        if es_sobre and recogida_sobres:
            obtener_repositorio(self.conn, "Configuracion").actualizar(1, FechaHoraRecogidaSobres=recogida_sobres)
        self.conn.commit()
        self.actualizar()
        self._resetear_formulario()

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._registros[filas[0].row()]

    def _precargar_seleccion(self) -> None:
        registro = self._fila_seleccionada()
        if registro is None:
            return
        indice = self.combo_profesional.findData(registro["IdProfesional"])
        if indice >= 0:
            self.combo_profesional.setCurrentIndex(indice)
        self.campo_periodo.setText(registro["PeriodoImputado"] or "")
        self.spin_monto.setValue(registro["Monto"])
        if registro["MedioPago"] and self.combo_medio_pago.findText(registro["MedioPago"]) >= 0:
            self.combo_medio_pago.setCurrentText(registro["MedioPago"])
        else:
            self.combo_medio_pago.setCurrentText(registro["MedioPago"] or "")
        self._actualizar_visibilidad_segun_medio_pago()
        self.combo_cuenta_receptora.setCurrentText(registro["CuentaReceptora"] or "")

    def _modificar(self) -> None:
        registro = self._fila_seleccionada()
        if registro is None:
            QMessageBox.warning(self, "Modificar pago", "Elegí una fila de la tabla para modificar.")
            return
        periodo_imputado = self.campo_periodo.text().strip()
        monto = self.spin_monto.value()
        medio_pago = self.combo_medio_pago.currentText().strip()
        if not periodo_imputado or monto == 0 or not medio_pago:
            QMessageBox.warning(self, "Modificar pago", "Completá período, monto y medio de pago.")
            return
        es_transferencia = "transferencia" in medio_pago.lower()
        if es_transferencia and not self.combo_cuenta_receptora.currentText().strip():
            QMessageBox.warning(self, "Modificar pago", "Elegí una cuenta receptora para la transferencia.")
            return
        es_sobre = self._es_sobre()
        recogida_sobres = (
            self.campo_recogida_sobres.dateTime().toString(Qt.DateFormat.ISODate) if es_sobre else None
        )
        try:
            modificar_pago(
                self.conn, registro["IdPago"], monto=monto, medio_pago=medio_pago,
                cuenta_receptora=self.combo_cuenta_receptora.currentText().strip() if es_transferencia else None,
                periodo_imputado=periodo_imputado, fecha_hora_recogida_sobres=recogida_sobres,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Modificar pago", str(error))
            return
        self.conn.commit()
        self.actualizar()
        self._resetear_formulario()

    def _deshacer_ultimo(self) -> None:
        if not self._registros:
            QMessageBox.warning(self, "Deshacer último movimiento", "No hay ningún movimiento para deshacer.")
            return
        respuesta = QMessageBox.question(
            self, "Deshacer último movimiento",
            "Esto revierte por completo el efecto del último movimiento registrado (le devuelve el saldo "
            "al profesional y borra el registro, sin importar quién sea). ¿Confirmás?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        try:
            deshacer_ultimo_pago(self.conn)
        except ValueError as error:
            QMessageBox.warning(self, "Deshacer último movimiento", str(error))
            return
        self.conn.commit()
        self.actualizar()

    def _iniciar_tanda(self) -> None:
        if tanda_sobres_es_de_otro_dia(self.conn):
            respuesta = QMessageBox.question(
                self, "Tanda de sobres",
                "Hay una tanda abierta de otro día. ¿Querés mantenerla en vez de empezar una nueva?",
            )
            if respuesta == QMessageBox.StandardButton.Yes:
                return
        elif tanda_sobres_abierta(self.conn) is not None:
            QMessageBox.information(self, "Tanda de sobres", "Ya hay una tanda abierta hoy.")
            return
        abrir_tanda_sobres(self.conn)
        self.conn.commit()
        self._actualizar_tanda()

    def _cerrar_tanda(self) -> None:
        if tanda_sobres_abierta(self.conn) is None:
            return
        cerrar_tanda_sobres(self.conn)
        self.conn.commit()
        self._actualizar_tanda()

    def _preguntar_restablecer_descuento(self, id_profesional: int, periodo_imputado: str) -> None:
        """DC-06 §5.2: el saldo del mes anterior volvió a estar dentro de
        tolerancia con este pago. Por defecto (recomendado) el descuento
        por horas semanales queda perdido igual para esa liquidación
        puntual — los descuentos están pensados para profesionales que
        terminan al día, no para los que se pusieron al día a mitad de
        camino."""
        respuesta = QMessageBox.question(
            self, "Restablecer descuentos",
            f"El saldo del período {periodo_imputado} volvió a estar dentro de la tolerancia con este pago.\n\n"
            "¿Querés restablecerle el descuento por cantidad de horas semanales reservadas "
            "para esa liquidación?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.No:
            suspender_descuento_periodo(self.conn, id_profesional=id_profesional, periodo=periodo_imputado)


class _PanelPlanesPago(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._planes: list[sqlite3.Row] = []
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

        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setMaximum(100_000_000)
        form.addWidget(QLabel("Monto a refinanciar"))
        form.addWidget(self.spin_monto)

        self.spin_cuotas = QSpinBox()
        self.spin_cuotas.setRange(1, 60)
        self.spin_cuotas.setValue(3)
        form.addWidget(QLabel("Cantidad de cuotas"))
        form.addWidget(self.spin_cuotas)

        self.spin_interes = QDoubleSpinBox()
        self.spin_interes.setRange(0, 100)
        form.addWidget(QLabel("% Interés mensual"))
        form.addWidget(self.spin_interes)

        self.campo_mes_inicio = QLineEdit()
        self.campo_mes_inicio.setPlaceholderText("AAAA-MM")
        form.addWidget(QLabel("Mes de inicio"))
        form.addWidget(self.campo_mes_inicio)

        boton_crear = QPushButton("Guardar plan de pagos (crea, o refinancia si ya tiene uno activo)")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.clicked.connect(self._guardar)
        form.addWidget(boton_crear)

        boton_cancelar = QPushButton("Cancelar plan seleccionado")
        boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(boton_cancelar)
        form.addStretch()
        splitter.addWidget(panel_form)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Profesional", "Monto refinanciado", "Cuotas", "Importe por cuota", "Inicio", "Estado"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        splitter.addWidget(self.tabla)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.campo_mes_inicio.setText(periodo_actual(self.conn))

    def actualizar(self) -> None:
        self._planes = obtener_repositorio(self.conn, "PlanPago").listar()
        cache = {p["IdProfesional"]: p for p in obtener_repositorio(self.conn, "Profesional").listar()}
        programadas = obtener_repositorio(self.conn, "RefinanciacionProgramada").listar()
        self.tabla.setRowCount(len(self._planes) + len(programadas))
        for i, p in enumerate(self._planes):
            self.tabla.setItem(i, 0, QTableWidgetItem(_nombre_profesional(cache, p["IdProfesional"])))
            self.tabla.setItem(i, 1, QTableWidgetItem(f"$ {p['MontoRefinanciado']:,.2f}"))
            self.tabla.setItem(i, 2, QTableWidgetItem(str(p["CantidadCuotas"])))
            self.tabla.setItem(i, 3, QTableWidgetItem(f"$ {p['ImportePorCuota']:,.2f}"))
            self.tabla.setItem(i, 4, QTableWidgetItem(p["MesAnoInicio"]))
            self.tabla.setItem(i, 5, QTableWidgetItem(p["Estado"]))
        for j, r in enumerate(programadas, start=len(self._planes)):
            self.tabla.setItem(j, 0, QTableWidgetItem(_nombre_profesional(cache, r["IdProfesional"])))
            self.tabla.setItem(j, 1, QTableWidgetItem(f"$ {r['MontoARefinanciar']:,.2f}"))
            self.tabla.setItem(j, 2, QTableWidgetItem(str(r["CantidadCuotas"])))
            self.tabla.setItem(j, 3, QTableWidgetItem(""))
            self.tabla.setItem(j, 4, QTableWidgetItem(r["MesAnoInicio"]))
            self.tabla.setItem(j, 5, QTableWidgetItem("Refinanciación programada"))
        self.tabla.resizeColumnsToContents()

    def _guardar(self) -> None:
        """Un profesional no puede tener más de un plan activo a la vez
        (DC-09 §3.6): si ya tiene uno, este mismo formulario refinancia en
        vez de crear. Si el mes de inicio pedido es el actual, refinancia
        ya mismo y regenera la liquidación si correspondía; si es un mes
        futuro, la refinanciación queda agendada para que el propio avance
        de mes la aplique sola (cancelar el plan vigente ahora inflaría el
        saldo del mes en curso antes de tiempo)."""
        monto = self.spin_monto.value()
        if monto <= 0:
            QMessageBox.warning(self, "Guardar plan de pagos", "El monto debe ser mayor a cero.")
            return
        id_profesional = self.combo_profesional.currentData()
        mes_inicio = self.campo_mes_inicio.text().strip()
        plan_activo = obtener_repositorio(self.conn, "PlanPago").listar(
            IdProfesional=id_profesional, Estado="Activo",
        )
        try:
            if not plan_activo:
                crear_plan_pago(
                    self.conn, id_profesional=id_profesional, monto_refinanciado=monto,
                    cantidad_cuotas=self.spin_cuotas.value(), mes_ano_inicio=mes_inicio,
                    porcentaje_interes_mensual=self.spin_interes.value(),
                )
            elif mes_inicio <= periodo_actual(self.conn):
                refinanciar_plan(
                    self.conn, id_profesional=id_profesional, monto_a_refinanciar=monto,
                    cantidad_cuotas=self.spin_cuotas.value(), mes_ano_inicio=mes_inicio,
                    porcentaje_interes_mensual=self.spin_interes.value(),
                )
                regenerar_si_corresponde(self.conn, id_profesional=id_profesional, periodo=periodo_actual(self.conn))
            else:
                programar_refinanciacion(
                    self.conn, id_profesional=id_profesional, monto_a_refinanciar=monto,
                    cantidad_cuotas=self.spin_cuotas.value(), mes_ano_inicio=mes_inicio,
                    porcentaje_interes_mensual=self.spin_interes.value(),
                )
                QMessageBox.information(
                    self, "Refinanciación programada",
                    f"Se agendó la refinanciación para {mes_inicio}: el plan vigente sigue activo hasta "
                    "entonces, y el cambio se aplica solo al avanzar de mes.",
                )
        except ValueError as error:
            QMessageBox.warning(self, "Guardar plan de pagos", str(error))
            return
        self.conn.commit()
        self.actualizar()

    def _cancelar(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return
        fila = filas[0].row()
        if fila >= len(self._planes):
            QMessageBox.warning(
                self, "Cancelar plan",
                "Esa fila es una refinanciación programada, todavía no un plan — esperá a que se aplique "
                "sola en el próximo avance de mes.",
            )
            return
        plan = self._planes[fila]
        try:
            cancelar_plan(self.conn, plan["IdPlan"])
        except ValueError as error:
            QMessageBox.warning(self, "Cancelar plan", str(error))
            return
        self.conn.commit()
        self.actualizar()
