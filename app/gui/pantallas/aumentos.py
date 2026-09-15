"""Aumentos y descuentos (FA2, Etapa 5, DC-10 §1): dos solapas.

"Aumentos" simula un % general de aumento sobre los valores de todos los
consultorios (filtrables por Localidad/Edificio/Unidad SOLO para la
visualización — el aumento que se confirma siempre alcanza a todos los
consultorios, se estén viendo o no) y permite, fila por fila, pisar ese %
general con un "porcentaje diferencial" propio (botón "Editar" habilita
esa columna) — nunca se muestran los dos valores juntos en una fila, el
que no aplica queda con una rayita "-". Confirmar reusa
app.negocio.aumentos.confirmar_aumento, que además regenera (dejándolas
"Regenerada no enviada") las liquidaciones ya emitidas del período
afectado. "Deshacer último movimiento" reusa
app.negocio.aumentos.deshacer_ultimo_aumento, que revierte la corrida más
reciente completa (valores de consultorio, esquema de descuentos si lo
había tocado, y liquidaciones regeneradas).

"Esquema de descuentos" es el único lugar desde donde se puede tocar el
esquema de descuentos (DC-10 §1.1: "solo modificable al ejecutar análisis
de aumentos"; la pantalla de catálogo lo muestra en solo lectura). En vez
del editor libre de tramos (Desde/Hasta/%) de la versión anterior, ahora
se arma con 3 parámetros ("Cantidad de horas", "Porcentaje descuento",
"Porcentaje tope descuento" — ver app.negocio.aumentos.generar_tramos_
esquema) que siempre arrancan en sus valores por defecto (2 / 1% / 25%)
al entrar a la pantalla, no en lo que haya vigente — el esquema vigente
puede tener tramos que no vengan de estos 3 parámetros (ej. historial
viejo cargado a mano), así que no hay una forma confiable de "deshacer"
la fórmula para precargar los campos con eso."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
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

from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.items_tabla import item_numero
from app.gui.widgets.resumen_saldo import item_monto
from app.negocio.aumentos import (
    actualizar_esquema_descuentos,
    confirmar_aumento,
    deshacer_ultimo_aumento,
    generar_tramos_esquema,
    simular_aumento,
)
from app.negocio.dias import periodo_actual

_ID_CONSULTORIO = Qt.ItemDataRole.UserRole
_COL_LOCALIDAD = 0
_COL_EDIFICIO = 1
_COL_UNIDAD = 2
_COL_CONSULTORIO = 3
_COL_PORCENTAJE_GENERAL = 4
_COL_PORCENTAJE_DIFERENCIAL = 5
_COL_REGULAR_ACTUAL = 6
_COL_REGULAR_NUEVO = 7
_COL_DIF_REGULAR = 8
_COL_AISLADA_ACTUAL = 9
_COL_AISLADA_NUEVO = 10
_COL_DIF_AISLADA = 11

_ANCHO_CAMPO = 260  # ancho compartido por todo lo que va en el panel izquierdo de "Aumentos"
_GUION = "-"
_TODAS = object()  # sentinel para "Todas/Todos" en los combos de filtro, distinto de una localidad real en None

_HORAS_DEFAULT = 2.0
_PORCENTAJE_DESCUENTO_DEFAULT = 1.0
_PORCENTAJE_TOPE_DEFAULT = 25.0


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _titulo_campo(texto: str) -> QLabel:
    """Jerarquía 3 (subtituloCampo): mismo criterio que el resto de las
    pantallas para los títulos que van arriba de un selector."""
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _fmt_porcentaje(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",") + "%"


def _celda_no_editable(texto: str) -> QTableWidgetItem:
    item = QTableWidgetItem(texto)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _celda_monto_fija(valor: float) -> QTableWidgetItem:
    item = item_monto(valor)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


class PantallaAumentos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Aumentos y descuentos")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        pestanas = QTabWidget()
        self.panel_aumentos = _PanelAumentos(conn)
        self.panel_esquema = _PanelEsquemaDescuentos(conn)
        pestanas.addTab(self.panel_aumentos, "Aumentos")
        pestanas.addTab(self.panel_esquema, "Esquema de descuentos")
        layout.addWidget(pestanas, stretch=1)

    def actualizar(self) -> None:
        self.panel_aumentos.actualizar()
        self.panel_esquema.actualizar()


class _PanelAumentos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._consultorios_info: dict[int, dict] = {}
        self._orden_consultorios: list[int] = []
        self._filas: dict[int, object] = {}
        self._diferenciales: dict[int, float] = {}
        self._editando_diferencial = False
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.campo_periodo.setFocus()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)

        form.addWidget(_titulo_campo("Período"))
        self.campo_periodo = QLineEdit()
        self.campo_periodo.setFixedWidth(_ANCHO_CAMPO)
        form.addWidget(self.campo_periodo)

        form.addWidget(_titulo_campo("Localidad"))
        self.combo_localidad = QComboBox()
        self.combo_localidad.setFixedWidth(_ANCHO_CAMPO)
        self.combo_localidad.currentIndexChanged.connect(self._cargar_combo_edificio)
        form.addWidget(self.combo_localidad)

        form.addWidget(_titulo_campo("Edificio"))
        self.combo_edificio = QComboBox()
        self.combo_edificio.setFixedWidth(_ANCHO_CAMPO)
        self.combo_edificio.currentIndexChanged.connect(self._cargar_combo_unidad)
        form.addWidget(self.combo_edificio)

        form.addWidget(_titulo_campo("Unidad"))
        self.combo_unidad = QComboBox()
        self.combo_unidad.setFixedWidth(_ANCHO_CAMPO)
        self.combo_unidad.currentIndexChanged.connect(self._aplicar_filtro_visual)
        form.addWidget(self.combo_unidad)

        form.addWidget(_linea_divisoria())

        form.addWidget(_titulo_campo("Porcentaje aumento general a aplicar"))
        self.spin_porcentaje = QDoubleSpinBox()
        self.spin_porcentaje.setFixedWidth(_ANCHO_CAMPO)
        self.spin_porcentaje.setRange(-100, 1000)
        self.spin_porcentaje.setDecimals(2)
        self.spin_porcentaje.setSuffix(" %")
        form.addWidget(self.spin_porcentaje)

        self.boton_simular = QPushButton("Simular")
        self.boton_simular.setObjectName("botonSecundario")
        self.boton_simular.setFixedWidth(_ANCHO_CAMPO)
        self.boton_simular.clicked.connect(self._simular)
        form.addWidget(self.boton_simular)

        self.boton_confirmar = QPushButton("Confirmar y aplicar aumentos")
        self.boton_confirmar.setObjectName("botonPrimario")
        self.boton_confirmar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_confirmar.clicked.connect(self._confirmar)
        form.addWidget(self.boton_confirmar)

        self.boton_editar = QPushButton("Editar")
        self.boton_editar.setObjectName("botonSecundario")
        self.boton_editar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_editar.setCheckable(True)
        self.boton_editar.toggled.connect(self._al_tildar_editar)
        form.addWidget(self.boton_editar)

        self.boton_deshacer = QPushButton("Deshacer último movimiento")
        self.boton_deshacer.setObjectName("botonSecundario")
        self.boton_deshacer.setFixedWidth(_ANCHO_CAMPO)
        self.boton_deshacer.clicked.connect(self._deshacer_ultimo)
        form.addWidget(self.boton_deshacer)

        form.addStretch()
        layout.addWidget(panel_form)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(12)
        self.tabla.setHorizontalHeaderLabels([
            "Localidad", "Edificio", "Unidad", "Consultorio", "% general", "% diferencial",
            "Regular actual", "Regular nuevo", "Dif. regular", "Aislada actual", "Aislada nuevo", "Dif. aislada",
        ])
        self.tabla.itemChanged.connect(self._al_cambiar_celda)
        layout.addWidget(self.tabla, stretch=1)

        self._foco = instalar_enter_avanza_foco([
            self.campo_periodo, self.combo_localidad, self.combo_edificio, self.combo_unidad,
            self.spin_porcentaje, self.boton_simular, self.boton_confirmar, self.boton_editar,
            self.boton_deshacer,
        ], parent=self)

    def actualizar(self) -> None:
        self.campo_periodo.setText(periodo_actual(self.conn))
        self._diferenciales.clear()
        self._editando_diferencial = False
        self.boton_editar.setChecked(False)
        self.spin_porcentaje.setValue(0)
        self._cargar_consultorios_info()
        self._cargar_combo_localidad()
        self._simular()

    def _cargar_consultorios_info(self) -> None:
        filas = self.conn.execute(
            "SELECT c.IdConsultorio, c.NumeroConsultorio, u.IdUnidad, u.Departamento, "
            "e.IdEdificio, e.Nombre AS NombreEdificio, e.DomicilioLocalidad "
            "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
            "JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "ORDER BY e.DomicilioLocalidad, e.Nombre, u.Departamento, c.NumeroConsultorio"
        ).fetchall()
        self._consultorios_info = {}
        self._orden_consultorios = []
        for f in filas:
            self._consultorios_info[f["IdConsultorio"]] = {
                "localidad_raw": f["DomicilioLocalidad"],
                "localidad": f["DomicilioLocalidad"] or "(Sin localidad)",
                "id_edificio": f["IdEdificio"],
                "edificio": f["NombreEdificio"],
                "id_unidad": f["IdUnidad"],
                "unidad": f["Departamento"],
                "numero": f["NumeroConsultorio"],
            }
            self._orden_consultorios.append(f["IdConsultorio"])

    def _cargar_combo_localidad(self) -> None:
        self.combo_localidad.blockSignals(True)
        self.combo_localidad.clear()
        self.combo_localidad.addItem("Todas las localidades", _TODAS)
        filas = self.conn.execute(
            "SELECT DISTINCT DomicilioLocalidad FROM Edificio ORDER BY DomicilioLocalidad"
        ).fetchall()
        for f in filas:
            valor = f["DomicilioLocalidad"]
            self.combo_localidad.addItem(valor or "(Sin localidad)", valor)
        self.combo_localidad.setCurrentIndex(0)
        self.combo_localidad.blockSignals(False)
        self._cargar_combo_edificio()

    def _cargar_combo_edificio(self) -> None:
        self.combo_edificio.blockSignals(True)
        self.combo_edificio.clear()
        self.combo_edificio.addItem("Todos los edificios", _TODAS)
        loc = self.combo_localidad.currentData()
        sql = "SELECT IdEdificio, Nombre FROM Edificio"
        parametros: list = []
        if loc is not _TODAS:
            sql += " WHERE DomicilioLocalidad IS NULL" if loc is None else " WHERE DomicilioLocalidad = ?"
            if loc is not None:
                parametros.append(loc)
        sql += " ORDER BY Nombre"
        for f in self.conn.execute(sql, parametros).fetchall():
            self.combo_edificio.addItem(f["Nombre"], f["IdEdificio"])
        self.combo_edificio.setCurrentIndex(0)
        self.combo_edificio.blockSignals(False)
        self._cargar_combo_unidad()

    def _cargar_combo_unidad(self) -> None:
        self.combo_unidad.blockSignals(True)
        self.combo_unidad.clear()
        self.combo_unidad.addItem("Todas las unidades", _TODAS)
        id_edificio = self.combo_edificio.currentData()
        sql = "SELECT IdUnidad, Departamento FROM Unidad"
        parametros: list = []
        if id_edificio is not _TODAS:
            sql += " WHERE IdEdificio = ?"
            parametros.append(id_edificio)
        sql += " ORDER BY Departamento"
        for f in self.conn.execute(sql, parametros).fetchall():
            self.combo_unidad.addItem(f["Departamento"], f["IdUnidad"])
        self.combo_unidad.setCurrentIndex(0)
        self.combo_unidad.blockSignals(False)
        self._aplicar_filtro_visual()

    def _aplicar_filtro_visual(self) -> None:
        """Solo cambia qué filas se ven — nunca lo que se simula/confirma,
        que siempre es el conjunto completo de consultorios (pedido
        explícito de la clienta)."""
        loc = self.combo_localidad.currentData()
        id_edificio = self.combo_edificio.currentData()
        id_unidad = self.combo_unidad.currentData()
        for fila in range(self.tabla.rowCount()):
            item = self.tabla.item(fila, _COL_LOCALIDAD)
            if item is None:
                continue
            info = self._consultorios_info.get(item.data(_ID_CONSULTORIO), {})
            oculto = (
                (loc is not _TODAS and info.get("localidad_raw") != loc)
                or (id_edificio is not _TODAS and info.get("id_edificio") != id_edificio)
                or (id_unidad is not _TODAS and info.get("id_unidad") != id_unidad)
            )
            self.tabla.setRowHidden(fila, oculto)

    def _al_tildar_editar(self, tildado: bool) -> None:
        self._editando_diferencial = tildado
        self._renderizar_tabla()

    def _simular(self) -> None:
        periodo = self.campo_periodo.text().strip() or periodo_actual(self.conn)
        filas = simular_aumento(
            self.conn, porcentaje_general=self.spin_porcentaje.value(),
            porcentajes_override=self._diferenciales, periodo=periodo,
        )
        self._filas = {f.id_consultorio: f for f in filas}
        self._renderizar_tabla()

    def _renderizar_tabla(self) -> None:
        general_pct = self.spin_porcentaje.value()
        self.tabla.blockSignals(True)
        try:
            self.tabla.setRowCount(len(self._orden_consultorios))
            for fila, id_consultorio in enumerate(self._orden_consultorios):
                info = self._consultorios_info[id_consultorio]
                item_localidad = _celda_no_editable(info["localidad"])
                item_localidad.setData(_ID_CONSULTORIO, id_consultorio)
                self.tabla.setItem(fila, _COL_LOCALIDAD, item_localidad)
                self.tabla.setItem(fila, _COL_EDIFICIO, _celda_no_editable(info["edificio"]))
                self.tabla.setItem(fila, _COL_UNIDAD, _celda_no_editable(info["unidad"]))
                self.tabla.setItem(fila, _COL_CONSULTORIO, _celda_no_editable(str(info["numero"])))

                diferencial = self._diferenciales.get(id_consultorio)
                self.tabla.setItem(
                    fila, _COL_PORCENTAJE_GENERAL,
                    self._celda_porcentaje(None if diferencial is not None else general_pct, editable=False),
                )
                self.tabla.setItem(
                    fila, _COL_PORCENTAJE_DIFERENCIAL,
                    self._celda_porcentaje(diferencial, editable=self._editando_diferencial),
                )

                f = self._filas.get(id_consultorio)
                if f is not None:
                    self.tabla.setItem(fila, _COL_REGULAR_ACTUAL, _celda_monto_fija(f.valor_regular_actual))
                    self.tabla.setItem(fila, _COL_REGULAR_NUEVO, _celda_monto_fija(f.valor_regular_nuevo))
                    self.tabla.setItem(fila, _COL_DIF_REGULAR, _celda_monto_fija(f.diferencia_regular))
                    self.tabla.setItem(fila, _COL_AISLADA_ACTUAL, _celda_monto_fija(f.valor_aislada_actual))
                    self.tabla.setItem(fila, _COL_AISLADA_NUEVO, _celda_monto_fija(f.valor_aislada_nuevo))
                    self.tabla.setItem(fila, _COL_DIF_AISLADA, _celda_monto_fija(f.diferencia_aislada))
        finally:
            self.tabla.blockSignals(False)
        self.tabla.resizeColumnsToContents()
        self._aplicar_filtro_visual()

    @staticmethod
    def _celda_porcentaje(valor: float | None, *, editable: bool) -> QTableWidgetItem:
        item = item_numero(_GUION if valor is None else _fmt_porcentaje(valor))
        if editable:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _al_cambiar_celda(self, item: QTableWidgetItem) -> None:
        if item.column() != _COL_PORCENTAJE_DIFERENCIAL or not self._editando_diferencial:
            return
        item_localidad = self.tabla.item(item.row(), _COL_LOCALIDAD)
        id_consultorio = item_localidad.data(_ID_CONSULTORIO)
        texto = item.text().strip()
        if texto in ("", _GUION):
            self._diferenciales.pop(id_consultorio, None)
        else:
            try:
                valor = float(texto.replace(",", ".").replace("%", ""))
            except ValueError:
                QMessageBox.warning(self, "Porcentaje diferencial", "Valor inválido.")
                self._renderizar_tabla()
                return
            self._diferenciales[id_consultorio] = valor
        self._simular()

    def _confirmar(self) -> None:
        if not self._filas:
            QMessageBox.warning(self, "Confirmar aumento", "Primero hay que simular el aumento.")
            return
        periodo = self.campo_periodo.text().strip() or periodo_actual(self.conn)
        confirmacion = QMessageBox.question(
            self, "Confirmar aumento",
            f"¿Confirmás el aumento para el período {periodo}? Al aplicar los aumentos se modifican valores "
            "en el sistema y, si hay liquidaciones ya emitidas para ese período, se marcan como no emitidas.",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return

        resumen = confirmar_aumento(
            self.conn, porcentaje_general=self.spin_porcentaje.value(),
            porcentajes_override=dict(self._diferenciales), periodo=periodo,
        )
        self.conn.commit()
        mensaje = f"Se actualizaron {resumen.consultorios_actualizados} consultorio(s)."
        if resumen.liquidaciones_regeneradas:
            mensaje = (
                f"Se actualizaron {resumen.consultorios_actualizados} consultorio(s) y se regeneraron "
                f"{len(resumen.liquidaciones_regeneradas)} liquidación(es) del período {resumen.periodo}."
            )
        QMessageBox.information(self, "Aumento confirmado", mensaje)
        self.actualizar()

    def _deshacer_ultimo(self) -> None:
        confirmacion = QMessageBox.question(
            self, "Deshacer último movimiento",
            "¿Deshacer el último aumento aplicado en el sistema?\nEsto revierte los valores de consultorio, el "
            "esquema de descuentos (si lo había reemplazado) y las liquidaciones que hubiera regenerado.",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        try:
            resumen = deshacer_ultimo_aumento(self.conn)
        except ValueError as error:
            QMessageBox.warning(self, "Deshacer último movimiento", str(error))
            return
        self.conn.commit()
        QMessageBox.information(
            self, "Deshacer último movimiento",
            f"Se revirtieron {resumen.consultorios_revertidos} consultorio(s) del período {resumen.periodo}.",
        )
        self.actualizar()


class _PanelEsquemaDescuentos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._valores_cargados = (_HORAS_DEFAULT, _PORCENTAJE_DESCUENTO_DEFAULT, _PORCENTAJE_TOPE_DEFAULT)
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.spin_horas.setFocus()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)

        form.addWidget(_titulo_campo("Cantidad de horas"))
        self.spin_horas = QDoubleSpinBox()
        self.spin_horas.setFixedWidth(_ANCHO_CAMPO)
        self.spin_horas.setRange(0.5, 168)
        self.spin_horas.setDecimals(1)
        self.spin_horas.setSuffix(" hs")
        self.spin_horas.valueChanged.connect(self._al_cambiar_parametros)
        form.addWidget(self.spin_horas)

        form.addWidget(_titulo_campo("Porcentaje descuento"))
        self.spin_porcentaje_descuento = QDoubleSpinBox()
        self.spin_porcentaje_descuento.setFixedWidth(_ANCHO_CAMPO)
        self.spin_porcentaje_descuento.setRange(0, 100)
        self.spin_porcentaje_descuento.setDecimals(2)
        self.spin_porcentaje_descuento.setSuffix(" %")
        self.spin_porcentaje_descuento.valueChanged.connect(self._al_cambiar_parametros)
        form.addWidget(self.spin_porcentaje_descuento)

        form.addWidget(_titulo_campo("Porcentaje tope descuento"))
        self.spin_porcentaje_tope = QDoubleSpinBox()
        self.spin_porcentaje_tope.setFixedWidth(_ANCHO_CAMPO)
        self.spin_porcentaje_tope.setRange(0, 100)
        self.spin_porcentaje_tope.setDecimals(2)
        self.spin_porcentaje_tope.setSuffix(" %")
        self.spin_porcentaje_tope.valueChanged.connect(self._al_cambiar_parametros)
        form.addWidget(self.spin_porcentaje_tope)

        self.boton_confirmar = QPushButton("Confirmar cambios")
        self.boton_confirmar.setObjectName("botonPrimario")
        self.boton_confirmar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_confirmar.setEnabled(False)
        self.boton_confirmar.clicked.connect(self._confirmar_cambios)
        form.addWidget(self.boton_confirmar)

        form.addStretch()
        layout.addWidget(panel_form)

        self.tabla_preview = QTableWidget()
        self.tabla_preview.setColumnCount(3)
        self.tabla_preview.setHorizontalHeaderLabels(["Horas desde", "Horas hasta", "% Descuento"])
        self.tabla_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla_preview, stretch=1)

        self._foco = instalar_enter_avanza_foco([
            self.spin_horas, self.spin_porcentaje_descuento, self.spin_porcentaje_tope, self.boton_confirmar,
        ], parent=self)

    def actualizar(self) -> None:
        self.spin_horas.blockSignals(True)
        self.spin_porcentaje_descuento.blockSignals(True)
        self.spin_porcentaje_tope.blockSignals(True)
        self.spin_horas.setValue(_HORAS_DEFAULT)
        self.spin_porcentaje_descuento.setValue(_PORCENTAJE_DESCUENTO_DEFAULT)
        self.spin_porcentaje_tope.setValue(_PORCENTAJE_TOPE_DEFAULT)
        self.spin_horas.blockSignals(False)
        self.spin_porcentaje_descuento.blockSignals(False)
        self.spin_porcentaje_tope.blockSignals(False)
        self._valores_cargados = (_HORAS_DEFAULT, _PORCENTAJE_DESCUENTO_DEFAULT, _PORCENTAJE_TOPE_DEFAULT)
        self.boton_confirmar.setEnabled(False)
        self._actualizar_preview()

    def _valores_actuales(self) -> tuple[float, float, float]:
        return (self.spin_horas.value(), self.spin_porcentaje_descuento.value(), self.spin_porcentaje_tope.value())

    def _al_cambiar_parametros(self, *_args) -> None:
        self.boton_confirmar.setEnabled(self._valores_actuales() != self._valores_cargados)
        self._actualizar_preview()

    def _actualizar_preview(self) -> None:
        horas, porcentaje, tope = self._valores_actuales()
        tramos = generar_tramos_esquema(cantidad_horas=horas, porcentaje_descuento=porcentaje, porcentaje_tope=tope)
        self.tabla_preview.setRowCount(len(tramos))
        for fila, (desde, hasta, pct) in enumerate(tramos):
            self.tabla_preview.setItem(fila, 0, item_numero(str(desde)))
            self.tabla_preview.setItem(fila, 1, item_numero(str(hasta)))
            self.tabla_preview.setItem(fila, 2, item_numero(_fmt_porcentaje(pct)))
        self.tabla_preview.resizeColumnsToContents()

    def _confirmar_cambios(self) -> None:
        horas, porcentaje, tope = self._valores_actuales()
        confirmacion = QMessageBox.question(
            self, "Confirmar cambios",
            "¿Confirmás el nuevo esquema de descuentos? Reemplaza el vigente (que queda como historial).",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        tramos = generar_tramos_esquema(cantidad_horas=horas, porcentaje_descuento=porcentaje, porcentaje_tope=tope)
        actualizar_esquema_descuentos(self.conn, tramos)
        self.conn.commit()
        QMessageBox.information(self, "Esquema de descuentos", "Se actualizó el esquema de descuentos.")
        self._valores_cargados = (horas, porcentaje, tope)
        self.boton_confirmar.setEnabled(False)
