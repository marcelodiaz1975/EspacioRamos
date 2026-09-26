"""Proceso de liquidación mensual (F22/F26, sección 4.1): calcula la
vista previa de la liquidación de cada profesional categoría R para el
período, permite emitirlas (persistir en LiquidacionEmitida + acreditar
a SaldoCuentaActual, DC-09 §2) y generar el PDF de cada una en
Profesionales/{código} del profesional correspondiente.

Cuatro solapas: "Emisión de archivos" (F22, lo de siempre), "Estado de
cuenta" (F26 — antes vivía en la pantalla separada "Estado de cuenta",
suprimida: sus tres solapas pasaron a vivir cada una en el formulario
que ya arma ese tipo de movimiento — ver también Pagos F21/F25 y
Cargos especiales F28/F25, confirmado por la clienta), "Feriados y
fechas especiales" (reordenamiento de formularios, Excel de la clienta:
el catálogo `FechasEspeciales` de `catalogos.py`, antes pantalla propia
del menú, se suma acá anidado — están relacionados porque los feriados/
no laborables afectan el cálculo de la liquidación) y "Liquidaciones
simuladas" (pedido posterior de la clienta, ver
`app.negocio.liquidacion_simulada` para el detalle completo: un PDF de
ejemplo para que un profesional vea cuánto le saldría un período dado,
sin cargar ninguna reserva real). La pantalla en sí se renombra
"Liquidaciones" (antes "Liquidación mensual" en el menú, "Proceso de
liquidación mensual" como título Nivel 1 — mismo criterio que el resto
de los merges de esta reorganización: el título Nivel 1 pasa a ser el
nombre nuevo del formulario)."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
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

from app.gui.estilos import COLOR_ROJO
from app.gui.pantallas import catalogos
from app.gui.pantallas.llaves import _alto_para_filas
from app.gui.pantallas.reservas import (
    _DIAS_RESERVA,
    _SpinHorario,
    _fmt_hora,
    _numero_codigo,
    _opciones_edificio,
    _opciones_localidad,
    _opciones_profesional,
    _recargar_consultorios,
    _recargar_unidades,
    _texto_profesional,
)
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.items_tabla import item_numero
from app.gui.widgets.resumen_saldo import item_monto
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.archivos_generados import carpeta_base, carpeta_liquidaciones_simuladas, carpeta_profesional
from app.negocio.dias import fecha_a_dia_semana, fecha_actual, periodo_actual, sumar_meses
from app.negocio.formato import formatear_moneda
from app.negocio.liquidacion_simulada import (
    BloqueSimulado,
    LiquidacionSimulada,
    SubtotalBloque,
    calcular_liquidacion_simulada,
)
from app.negocio.liquidaciones import calcular_liquidacion, emitir_liquidacion
from app.negocio.valores import horas_semanales_vigentes
from app.pdf.liquidacion_pdf import generar_pdf_liquidacion
from app.pdf.liquidacion_simulada_pdf import generar_pdf_liquidacion_simulada
from app.repositorio.registro import obtener_repositorio

_ANCHO_PANEL_FILTROS = 300
_ANCHO_PANEL_FILTROS_ESTADO_CUENTA = 340
_ANCHO_BOTON_EMISION = 275  # Calcular / los tres Emitir..., todos iguales
_ANCHO_BOTON_SIMULADA = 240  # Agregar/Quitar bloque, Generar liquidación simulada
_FILAS_VISIBLES_SIMULADAS = 8  # piso de alto de "Bloques cargados"/"Totales por bloques y general", scrolleables
# Mismo naranja suave que `resalte_seleccion` en app.gui.estilos.paleta()
# (la selección de fila de toda la aplicación) — se reusa acá para
# resaltar la fila de totales, pedido explícito de la clienta.
_COLOR_FILA_TOTAL = "#F2C4A0"

_ESTADOS_FILTRO = [
    ("Cualquier estado", None),
    ("Sin emitir", "Sin emitir"),
    ("No enviada", "No enviada"),
    ("Regenerada no enviada", "Regenerada no enviada"),
    ("Enviada", "Enviada"),
]


def _fmt_horas(horas: float) -> str:
    return str(int(horas)) if horas == int(horas) else f"{horas:.1f}"


def _fmt_fecha_hora_generacion(iso: str | None) -> str:
    """"Martes 10/08/2026 14:30hs" — nombre de día en español (ya viene
    capitalizado de `fecha_a_dia_semana`), fecha con barras y sin
    segundos, a diferencia de `_fmt_fecha_hora_larga` de Pagos (que usa
    guiones y sí los muestra: ahí importa el orden real de los sobres
    físicos, acá no)."""
    if not iso:
        return ""
    dt = datetime.fromisoformat(iso)
    dia = fecha_a_dia_semana(dt.date())
    return f"{dia} {dt.day:02d}/{dt.month:02d}/{dt.year} {dt.hour:02d}:{dt.minute:02d}hs"


class ProcesoLiquidacion(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Liquidaciones".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_emision = _PanelEmisionArchivos(conn)
        self.panel_estado_cuenta = _PanelEstadoCuentaLiquidaciones(conn)
        self.pestanas.addTab(self.panel_emision, "Emisión de archivos")
        self.pestanas.addTab(self.panel_estado_cuenta, "Estado de cuenta")
        self.panel_fechas_especiales = catalogos.pantalla_fechas_especiales(conn, anidado=True)
        self.pestanas.addTab(self.panel_fechas_especiales, "Feriados y fechas especiales")
        self.panel_liquidaciones_simuladas = _PanelLiquidacionesSimuladas(conn)
        self.pestanas.addTab(self.panel_liquidaciones_simuladas, "Liquidaciones simuladas")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)

    def actualizar(self) -> None:
        self.panel_emision.actualizar()
        self.panel_estado_cuenta.actualizar()


class _PanelEmisionArchivos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._filas: list[dict] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """Mismo motivo que en Reservas: `setFocus()` durante la
        construcción no alcanza a "pegar" porque el QTabWidget
        contenedor todavía no está mostrado — se repite el pedido de
        foco en Período al mostrarse la solapa."""
        super().showEvent(event)
        self.campo_periodo.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        panel_filtros = QWidget()
        panel_filtros.setMaximumWidth(_ANCHO_PANEL_FILTROS)
        layout_filtros = QVBoxLayout(panel_filtros)

        layout_filtros.addWidget(QLabel("Período:"))
        self.campo_periodo = QLineEdit()
        self.campo_periodo.editingFinished.connect(self.actualizar)
        layout_filtros.addWidget(self.campo_periodo)

        layout_filtros.addWidget(QLabel("Profesional:"))
        self.combo_profesional_filtro = QComboBox()
        self.combo_profesional_filtro.addItem("Todos los profesionales", None)
        for id_, etiqueta in _opciones_profesional(self.conn, ("R",)):
            self.combo_profesional_filtro.addItem(etiqueta, id_)
        habilitar_busqueda_profesional(self.combo_profesional_filtro)
        self.combo_profesional_filtro.currentIndexChanged.connect(self.actualizar)
        layout_filtros.addWidget(self.combo_profesional_filtro)

        layout_filtros.addWidget(QLabel("Estado de la liquidación:"))
        self.combo_estado_filtro = QComboBox()
        for etiqueta, _valor in _ESTADOS_FILTRO:
            self.combo_estado_filtro.addItem(etiqueta)
        self.combo_estado_filtro.currentIndexChanged.connect(self.actualizar)
        layout_filtros.addWidget(self.combo_estado_filtro)

        self.boton_calcular = QPushButton("Calcular")
        self.boton_calcular.setObjectName("botonPrimario")
        self.boton_calcular.clicked.connect(self.actualizar)
        layout_filtros.addWidget(self.boton_calcular)

        boton_emitir_pendientes = QPushButton("Emitir liquidaciones pendientes")
        boton_emitir_pendientes.setObjectName("botonSecundario")
        boton_emitir_pendientes.clicked.connect(self._emitir_pendientes)
        layout_filtros.addWidget(boton_emitir_pendientes)
        boton_emitir_seleccionadas = QPushButton("Emitir liquidaciones seleccionadas")
        boton_emitir_seleccionadas.setObjectName("botonSecundario")
        boton_emitir_seleccionadas.clicked.connect(self._emitir_seleccionadas)
        layout_filtros.addWidget(boton_emitir_seleccionadas)
        boton_emitir_todas = QPushButton("Emitir todas las liquidaciones")
        boton_emitir_todas.setObjectName("botonSecundario")
        boton_emitir_todas.clicked.connect(self._emitir_todas)
        layout_filtros.addWidget(boton_emitir_todas)

        for boton in (
            self.boton_calcular, boton_emitir_pendientes, boton_emitir_seleccionadas, boton_emitir_todas,
        ):
            boton.setFixedWidth(_ANCHO_BOTON_EMISION)

        layout_filtros.addStretch()
        layout_externo.addWidget(panel_filtros)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Incluir", "Profesional", "Horas semanales", "Saldo anterior", "Monto a generar", "Estado"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        # Por defecto queda en el orden de siempre (no enviadas primero,
        # luego por código); un clic en un título la ordena por esa
        # columna hasta el próximo refresco, que la vuelve a dejar así
        # (mismo criterio que Centro de mensajería).
        self.tabla.setSortingEnabled(True)
        layout_externo.addWidget(self.tabla, stretch=1)

        self.campo_periodo.setText(periodo_actual(self.conn))
        self._foco = instalar_enter_avanza_foco(
            [
                self.campo_periodo, self.combo_profesional_filtro, self.combo_estado_filtro, self.boton_calcular,
                boton_emitir_pendientes, boton_emitir_seleccionadas, boton_emitir_todas,
            ],
            parent=self,
        )

    def _periodo(self) -> str:
        return self.campo_periodo.text().strip() or periodo_actual(self.conn)

    def actualizar(self) -> None:
        """Sin selección por defecto (el operador elige a quién emitir a
        propósito) y orden fijo: no enviadas primero, luego por código de
        profesional — confirmado por la clienta."""
        periodo = self._periodo()
        hoy = fecha_actual(self.conn).isoformat()
        id_profesional_filtro = self.combo_profesional_filtro.currentData()
        estado_filtro = _ESTADOS_FILTRO[self.combo_estado_filtro.currentIndex()][1]
        profesionales = obtener_repositorio(self.conn, "Profesional").listar(CategoriaProfesional="R")
        if id_profesional_filtro is not None:
            profesionales = [p for p in profesionales if p["IdProfesional"] == id_profesional_filtro]
        filas: list[dict] = []
        for profesional in profesionales:
            try:
                liquidacion = calcular_liquidacion(
                    self.conn, id_profesional=profesional["IdProfesional"], periodo=periodo
                )
                monto_generado, monto_error = liquidacion.monto_generado, None
            except ValueError as error:
                monto_generado, monto_error = None, str(error)
            ultima = self.conn.execute(
                "SELECT EstadoEnvio FROM LiquidacionEmitida WHERE IdProfesional = ? AND Periodo = ? "
                "ORDER BY IdLiquidacion DESC LIMIT 1",
                (profesional["IdProfesional"], periodo),
            ).fetchone()
            estado = ultima["EstadoEnvio"] if ultima else "Sin emitir"
            if estado_filtro is not None and estado != estado_filtro:
                continue
            horas_semanales = horas_semanales_vigentes(self.conn, [profesional["IdProfesional"]], hoy)
            filas.append({
                "profesional": profesional, "monto_generado": monto_generado, "monto_error": monto_error,
                "estado": estado, "horas_semanales": horas_semanales,
            })
        filas.sort(key=lambda f: _numero_codigo(f["profesional"]["IdCodigo"]))
        filas.sort(key=lambda f: f["estado"] == "Enviada")  # estable: no enviadas arriba
        self._filas = filas

        # Se apaga mientras se repuebla la tabla: si no, un clic previo en
        # un título la reordenaría fila por fila a medida que se cargan
        # las filas nuevas, mezclando el índice de `filas` con la tabla —
        # se reactiva al final, ya en el orden fijo de siempre.
        self.tabla.setSortingEnabled(False)
        self.tabla.setRowCount(len(filas))
        for fila_idx, f in enumerate(filas):
            profesional = f["profesional"]
            self.tabla.setItem(fila_idx, 0, self._item_incluir(profesional["IdProfesional"]))
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(_texto_profesional(profesional)))
            self.tabla.setItem(fila_idx, 2, item_numero(_fmt_horas(f["horas_semanales"])))
            self.tabla.setItem(fila_idx, 3, item_monto(profesional["SaldoCuentaAnterior"]))
            if f["monto_error"] is not None:
                self.tabla.setItem(fila_idx, 4, QTableWidgetItem(f["monto_error"]))
            else:
                self.tabla.setItem(fila_idx, 4, item_monto(f["monto_generado"]))
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem(f["estado"]))
        self.tabla.setSortingEnabled(True)
        self.tabla.resizeColumnsToContents()

    @staticmethod
    def _item_incluir(id_profesional: int) -> QTableWidgetItem:
        """Checkbox nativo del ítem (en vez de un QCheckBox como
        cellWidget): así queda centrado en la celda y, con los títulos
        ordenables, viaja con su fila al reordenar — un cellWidget no lo
        hace, se queda pegado a la posición visual. Guarda el
        IdProfesional para poder identificar la fila al leer la
        selección, igual criterio que el check "Enviada" de Centro de
        mensajería."""
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        item.setCheckState(Qt.CheckState.Unchecked)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setData(Qt.ItemDataRole.UserRole, id_profesional)
        return item

    def _emitir(self, seleccionados: list[sqlite3.Row], mensaje_confirmacion: str) -> None:
        periodo = self._periodo()
        if carpeta_base(self.conn) is None:
            QMessageBox.warning(
                self, "Emitir liquidaciones", "Configurá primero la carpeta base de archivos en Configuración general.",
            )
            return
        if not seleccionados:
            QMessageBox.information(self, "Emitir liquidaciones", "No hay profesionales seleccionados.")
            return
        confirmacion = QMessageBox.question(self, "Emitir liquidaciones", mensaje_confirmacion)
        if confirmacion != QMessageBox.StandardButton.Yes:
            return

        errores = []
        emitidas = 0
        for profesional in seleccionados:
            try:
                id_liquidacion, liquidacion = emitir_liquidacion(
                    self.conn, id_profesional=profesional["IdProfesional"], periodo=periodo,
                    fecha_emision=fecha_actual(self.conn).isoformat(),
                )
                directorio = str(carpeta_profesional(self.conn, profesional["IdCodigo"]))
                ruta = generar_pdf_liquidacion(self.conn, liquidacion, directorio)
                obtener_repositorio(self.conn, "LiquidacionEmitida").actualizar(
                    id_liquidacion, NombreArchivo=os.path.basename(ruta),
                    FechaHoraGeneracion=datetime.now().isoformat(timespec="seconds"),
                )
                emitidas += 1
            except ValueError as error:
                errores.append(f"{profesional['Apellido']}: {error}")
        self.conn.commit()

        mensaje = f"Se emitieron {emitidas} liquidación(es)."
        if errores:
            mensaje += "\n\nErrores:\n" + "\n".join(errores)
        QMessageBox.information(self, "Emitir liquidaciones", mensaje)
        self.actualizar()

    def _emitir_seleccionadas(self) -> None:
        """Emite lo tildado con los checks, sea cual sea su estado actual
        — si alguna ya estaba emitida (o enviada), se reemite: queda una
        liquidación nueva y pasa a "Regenerada no enviada" (o "No
        enviada" si nunca se había enviado)."""
        ids_incluidos = {
            self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
            for fila in range(self.tabla.rowCount())
            if self.tabla.item(fila, 0).checkState() == Qt.CheckState.Checked
        }
        seleccionados = [f["profesional"] for f in self._filas if f["profesional"]["IdProfesional"] in ids_incluidos]
        self._emitir(
            seleccionados,
            f"¿Confirmás emitir la liquidación de {self._periodo()} para {len(seleccionados)} "
            "profesional(es) seleccionado(s) y generar sus PDF?",
        )

    def _emitir_pendientes(self) -> None:
        """Solo las que todavía no se generaron ninguna vez este período
        (estado "Sin emitir") — no toca las que ya están emitidas,
        enviadas o no."""
        seleccionados = [f["profesional"] for f in self._filas if f["estado"] == "Sin emitir"]
        self._emitir(
            seleccionados,
            f"¿Confirmás emitir la liquidación de {self._periodo()} para {len(seleccionados)} "
            "profesional(es) pendientes (sin emitir) y generar sus PDF?",
        )

    def _emitir_todas(self) -> None:
        """Reemite absolutamente a todos, sin importar el estado actual
        — incluidas las ya enviadas, que vuelven a "Regenerada no
        enviada". Acción más drástica que las otras dos, con una
        confirmación bien explícita."""
        seleccionados = [f["profesional"] for f in self._filas]
        self._emitir(
            seleccionados,
            f"Esto vuelve a generar la liquidación de TODOS los profesionales del período {self._periodo()} "
            f"({len(seleccionados)} en total), incluidas las que ya se emitieron o enviaron — todas quedan "
            "marcadas como no enviadas de nuevo.\n\n¿Confirmás continuar?",
        )


class _PanelEstadoCuentaLiquidaciones(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """Mismo motivo que en Emisión de archivos: al mostrarse la
        solapa (recién ahí "pega" el foco) lo manda a Profesional, el
        único control con el que se interactúa en este panel."""
        super().showEvent(event)
        self.combo_profesional.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        panel_filtros = QWidget()
        panel_filtros.setFixedWidth(_ANCHO_PANEL_FILTROS_ESTADO_CUENTA)
        layout_filtros = QVBoxLayout(panel_filtros)

        layout_filtros.addWidget(QLabel("Profesional:"))
        self.combo_profesional = QComboBox()
        habilitar_busqueda_profesional(self.combo_profesional)
        self.combo_profesional.currentIndexChanged.connect(self._actualizar_datos)
        layout_filtros.addWidget(self.combo_profesional)

        linea_separadora = QFrame()
        linea_separadora.setFrameShape(QFrame.Shape.HLine)
        linea_separadora.setFrameShadow(QFrame.Shadow.Sunken)
        layout_filtros.addWidget(linea_separadora)

        self.campo_saldo_actual = QLineEdit()
        self.campo_saldo_actual.setReadOnly(True)
        layout_filtros.addWidget(self.campo_saldo_actual)

        layout_filtros.addStretch()
        layout_externo.addWidget(panel_filtros)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(7)
        self.tabla.setHorizontalHeaderLabels([
            "Período", "Fecha emisión", "Monto generado", "Reemisión", "Estado de envío", "Archivo",
            "Fecha y hora generación del archivo",
        ])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout_externo.addWidget(self.tabla, stretch=1)

    def actualizar(self) -> None:
        # El profesional elegido se conserva aunque se salga y se vuelva
        # a entrar a este formulario: se busca de nuevo por su id
        # después de repoblar el combo, en vez de resetear a "ninguno".
        id_anterior = self.combo_profesional.currentData()
        self.combo_profesional.blockSignals(True)
        self.combo_profesional.clear()
        for id_, etiqueta in _opciones_profesional(self.conn):
            self.combo_profesional.addItem(etiqueta, id_)
        indice = self.combo_profesional.findData(id_anterior)
        self.combo_profesional.setCurrentIndex(indice if indice >= 0 else 0)
        self.combo_profesional.blockSignals(False)
        self._actualizar_datos()

    def _actualizar_datos(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            self.campo_saldo_actual.setStyleSheet("")
            self.campo_saldo_actual.setText("Saldo actual: —")
            self.tabla.setRowCount(0)
            return
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(id_profesional)
        saldo_actual = profesional["SaldoCuentaActual"] or 0.0
        self.campo_saldo_actual.setText(f"Saldo actual: {formatear_moneda(saldo_actual)}")
        self.campo_saldo_actual.setStyleSheet(f"color: {COLOR_ROJO};" if saldo_actual < 0 else "")
        registros = sorted(
            obtener_repositorio(self.conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional),
            key=lambda r: r["Periodo"], reverse=True,
        )
        self.tabla.setRowCount(len(registros))
        for i, r in enumerate(registros):
            self.tabla.setItem(i, 0, QTableWidgetItem(r["Periodo"]))
            self.tabla.setItem(i, 1, QTableWidgetItem(r["FechaEmision"] or ""))
            self.tabla.setItem(i, 2, item_monto(r["MontoGenerado"]))
            self.tabla.setItem(i, 3, QTableWidgetItem("Sí" if r["EsReemision"] else "No"))
            self.tabla.setItem(i, 4, QTableWidgetItem(r["EstadoEnvio"]))
            self.tabla.setItem(i, 5, QTableWidgetItem(r["NombreArchivo"] or ""))
            self.tabla.setItem(i, 6, QTableWidgetItem(_fmt_fecha_hora_generacion(r["FechaHoraGeneracion"])))
        self.tabla.resizeColumnsToContents()


def _ubicacion_bloque(conn: sqlite3.Connection, id_consultorio: int) -> tuple[str, str, str, str]:
    """Localidad/Edificio/Unidad/Consultorio de un bloque simulado, para
    la tabla "Bloques cargados" — mismo criterio "(Sin localidad)" que
    `_opciones_localidad` de `reservas.py` cuando el edificio no tiene
    localidad cargada."""
    fila = conn.execute(
        """
        SELECT loc.Localidad AS Localidad, e.Nombre AS Edificio, u.Departamento AS Unidad, c.NumeroConsultorio AS Consultorio
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad
        WHERE c.IdConsultorio = ?
        """,
        (id_consultorio,),
    ).fetchone()
    if fila is None:
        return ("", "", "", "")
    return (
        fila["Localidad"] or "(Sin localidad)", fila["Edificio"], fila["Unidad"],
        f"Consultorio {fila['Consultorio']}",
    )


def _fila_subtotal_bloque(subtotal: SubtotalBloque) -> list[QTableWidgetItem]:
    return [
        item_numero(str(subtotal.numero)),
        item_numero(_fmt_horas(subtotal.horas_semanales)),
        item_numero(_fmt_horas(subtotal.horas_mensuales)),
        item_monto(subtotal.bruto),
        item_numero(f"{subtotal.descuento_pct:g}%"),
        item_monto(-subtotal.descuento),
        item_monto(subtotal.neto),
    ]


class _PanelLiquidacionesSimuladas(QWidget):
    """Cuarta solapa de "Liquidaciones" (pedido de la clienta, ver
    `app.negocio.liquidacion_simulada` para el detalle completo de qué
    contempla la simulación y qué no): el operador carga a mano, para un
    profesional y un período, los bloques (día/horario/consultorio) que
    ese profesional querría reservar, y genera un PDF de ejemplo que
    muestra cuánto le saldría — sin tocar la grilla ni la disponibilidad
    real, sin persistir nada en la base. Controles y botones a la
    izquierda (mismo criterio de todo el sistema); a la derecha, los
    bloques ya cargados y el resultado de la última simulación generada.
    """

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._bloques: list[BloqueSimulado] = []
        self._armar_ui()

    def showEvent(self, event) -> None:  # noqa: N802
        """Mismo motivo que en el resto de las solapas de esta pantalla:
        el foco recién "pega" cuando la solapa ya se está mostrando de
        verdad, no durante la construcción."""
        super().showEvent(event)
        self.combo_profesional.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        panel_izquierda = QWidget()
        panel_izquierda.setObjectName("panelSolapa")
        panel_izquierda.setMaximumWidth(_ANCHO_PANEL_FILTROS)
        layout_izquierda = QVBoxLayout(panel_izquierda)

        layout_izquierda.addWidget(QLabel("Profesional:"))
        self.combo_profesional = QComboBox()
        for id_, etiqueta in _opciones_profesional(self.conn, ("R",)):
            self.combo_profesional.addItem(etiqueta, id_)
        habilitar_busqueda_profesional(self.combo_profesional)
        layout_izquierda.addWidget(self.combo_profesional)

        layout_izquierda.addWidget(QLabel("Período a simular:"))
        self.campo_periodo = QLineEdit()
        # Por defecto el mes siguiente al actual (pedido explícito de la
        # clienta) — se puede cambiar a mano para simular cualquier otro.
        self.campo_periodo.setText(sumar_meses(periodo_actual(self.conn), 1))
        layout_izquierda.addWidget(self.campo_periodo)

        linea_1 = QFrame()
        linea_1.setFrameShape(QFrame.Shape.HLine)
        linea_1.setFrameShadow(QFrame.Shadow.Sunken)
        layout_izquierda.addWidget(linea_1)

        layout_izquierda.addWidget(QLabel("Localidad:"))
        self.combo_localidad = QComboBox()
        layout_izquierda.addWidget(self.combo_localidad)
        layout_izquierda.addWidget(QLabel("Edificio:"))
        self.combo_edificio = QComboBox()
        layout_izquierda.addWidget(self.combo_edificio)
        layout_izquierda.addWidget(QLabel("Unidad:"))
        self.combo_unidad = QComboBox()
        layout_izquierda.addWidget(self.combo_unidad)
        layout_izquierda.addWidget(QLabel("Consultorio:"))
        self.combo_consultorio = QComboBox()
        layout_izquierda.addWidget(self.combo_consultorio)

        layout_izquierda.addWidget(QLabel("Día:"))
        self.combo_dia = QComboBox()
        for dia in _DIAS_RESERVA:
            self.combo_dia.addItem(dia)
        layout_izquierda.addWidget(self.combo_dia)

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
        layout_izquierda.addLayout(fila_horario)

        self.boton_agregar_bloque = QPushButton("Agregar bloque")
        self.boton_agregar_bloque.setObjectName("botonSecundario")
        self.boton_agregar_bloque.clicked.connect(self._agregar_bloque)
        layout_izquierda.addWidget(self.boton_agregar_bloque)

        self.boton_quitar_bloque = QPushButton("Quitar bloque")
        self.boton_quitar_bloque.setObjectName("botonSecundario")
        self.boton_quitar_bloque.setEnabled(False)
        self.boton_quitar_bloque.clicked.connect(self._quitar_bloque)
        layout_izquierda.addWidget(self.boton_quitar_bloque)

        linea_2 = QFrame()
        linea_2.setFrameShape(QFrame.Shape.HLine)
        linea_2.setFrameShadow(QFrame.Shadow.Sunken)
        layout_izquierda.addWidget(linea_2)

        self.boton_generar = QPushButton("Generar liquidación simulada")
        self.boton_generar.setObjectName("botonPrimario")
        self.boton_generar.clicked.connect(self._generar)
        layout_izquierda.addWidget(self.boton_generar)

        for boton in (self.boton_agregar_bloque, self.boton_quitar_bloque, self.boton_generar):
            boton.setFixedWidth(_ANCHO_BOTON_SIMULADA)

        layout_izquierda.addStretch()
        layout_externo.addWidget(panel_izquierda)

        panel_derecha = QWidget()
        layout_derecha = QVBoxLayout(panel_derecha)

        layout_derecha.addWidget(QLabel("Bloques cargados:"))
        self.tabla_bloques = QTableWidget()
        self.tabla_bloques.setColumnCount(8)
        self.tabla_bloques.setHorizontalHeaderLabels(
            ["N° Bloque", "Día", "Horario desde", "Horario hasta", "Localidad", "Edificio", "Unidad", "Consultorio"]
        )
        self.tabla_bloques.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_bloques.itemSelectionChanged.connect(self._actualizar_boton_quitar_bloque)
        # Las cuatro últimas columnas (ubicación) se reparten el ancho
        # sobrante del panel — pedido explícito de la clienta, "para
        # aprovechar el ancho de la pantalla visible" — en vez de
        # quedarse angostas al ancho justo de su contenido.
        header_bloques = self.tabla_bloques.horizontalHeader()
        for columna in (4, 5, 6, 7):
            header_bloques.setSectionResizeMode(columna, QHeaderView.ResizeMode.Stretch)
        self.tabla_bloques.setMinimumHeight(_alto_para_filas(self.tabla_bloques, _FILAS_VISIBLES_SIMULADAS))
        layout_derecha.addWidget(self.tabla_bloques, stretch=1)

        layout_derecha.addWidget(QLabel("Totales por bloques y general:"))
        self.tabla_subtotales = QTableWidget()
        self.tabla_subtotales.setColumnCount(7)
        self.tabla_subtotales.setHorizontalHeaderLabels([
            "N° Bloque", "Cantidad horas semanales", "Cantidad horas mensuales", "Importe Bruto",
            "% Descuento", "Descuento", "Importe Neto",
        ])
        self.tabla_subtotales.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_subtotales.setMinimumHeight(_alto_para_filas(self.tabla_subtotales, _FILAS_VISIBLES_SIMULADAS))
        layout_derecha.addWidget(self.tabla_subtotales, stretch=1)

        layout_externo.addWidget(panel_derecha, stretch=1)

        self.combo_localidad.currentIndexChanged.connect(self._al_cambiar_localidad)
        self.combo_edificio.currentIndexChanged.connect(self._al_cambiar_edificio)
        self.combo_unidad.currentIndexChanged.connect(self._al_cambiar_unidad)
        self._cargar_localidades()

        self._foco = instalar_enter_avanza_foco([
            self.combo_profesional, self.campo_periodo, self.combo_localidad, self.combo_edificio,
            self.combo_unidad, self.combo_consultorio, self.combo_dia, self.spin_desde, self.spin_hasta,
            self.boton_agregar_bloque, self.boton_quitar_bloque, self.boton_generar,
        ])

    def _cargar_localidades(self) -> None:
        self.combo_localidad.clear()
        for id_, etiqueta in _opciones_localidad(self.conn):
            self.combo_localidad.addItem(etiqueta, id_)
        self._al_cambiar_localidad()

    def _al_cambiar_localidad(self) -> None:
        id_localidad = self.combo_localidad.currentData()
        self.combo_edificio.blockSignals(True)
        self.combo_edificio.clear()
        for id_, etiqueta in _opciones_edificio(self.conn, id_localidad):
            self.combo_edificio.addItem(etiqueta, id_)
        self.combo_edificio.blockSignals(False)
        self._al_cambiar_edificio()

    def _al_cambiar_edificio(self) -> None:
        _recargar_unidades(self.conn, self.combo_edificio, self.combo_unidad)
        self._al_cambiar_unidad()

    def _al_cambiar_unidad(self) -> None:
        _recargar_consultorios(self.conn, self.combo_unidad, self.combo_consultorio)

    def _actualizar_boton_quitar_bloque(self) -> None:
        self.boton_quitar_bloque.setEnabled(bool(self.tabla_bloques.selectedItems()))

    def _agregar_bloque(self) -> None:
        id_consultorio = self.combo_consultorio.currentData()
        if id_consultorio is None:
            QMessageBox.warning(self, "Falta elegir consultorio", "Elegí un consultorio antes de agregar el bloque.")
            return
        hora_inicio, hora_fin = self.spin_desde.value(), self.spin_hasta.value()
        if hora_fin <= hora_inicio:
            QMessageBox.warning(
                self, "Horario inválido", 'El horario "hasta" tiene que ser posterior al "desde".',
            )
            return
        self._bloques.append(BloqueSimulado(
            dia_semana=self.combo_dia.currentText(), hora_inicio=hora_inicio, hora_fin=hora_fin,
            id_consultorio=id_consultorio,
        ))
        self._refrescar_tabla_bloques()

    def _quitar_bloque(self) -> None:
        fila = self.tabla_bloques.currentRow()
        if fila < 0:
            return
        del self._bloques[fila]
        self._refrescar_tabla_bloques()

    def _refrescar_tabla_bloques(self) -> None:
        self.tabla_bloques.setRowCount(len(self._bloques))
        for fila, bloque in enumerate(self._bloques):
            localidad, edificio, unidad, consultorio = _ubicacion_bloque(self.conn, bloque.id_consultorio)
            self.tabla_bloques.setItem(fila, 0, item_numero(str(fila + 1)))
            self.tabla_bloques.setItem(fila, 1, QTableWidgetItem(bloque.dia_semana))
            self.tabla_bloques.setItem(fila, 2, item_numero(f"{_fmt_hora(bloque.hora_inicio)}hs"))
            self.tabla_bloques.setItem(fila, 3, item_numero(f"{_fmt_hora(bloque.hora_fin)}hs"))
            self.tabla_bloques.setItem(fila, 4, QTableWidgetItem(localidad))
            self.tabla_bloques.setItem(fila, 5, QTableWidgetItem(edificio))
            self.tabla_bloques.setItem(fila, 6, QTableWidgetItem(unidad))
            self.tabla_bloques.setItem(fila, 7, QTableWidgetItem(consultorio))
        # Solo las columnas 0-3 se ajustan a su contenido — las últimas
        # cuatro (ubicación) quedan en modo Stretch (ver `_armar_ui`), así
        # que este resize no las toca.
        self.tabla_bloques.resizeColumnsToContents()
        # "Día" (pedido explícito de la clienta: más ancho que el
        # justo — mismo criterio de padding que `_PADDING_COLUMNA` en
        # `novedades.py`/`llaves.py`, duplicado acá para una sola columna.
        self.tabla_bloques.setColumnWidth(1, self.tabla_bloques.columnWidth(1) + 30)
        self._actualizar_boton_quitar_bloque()

    def _generar(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Falta elegir profesional", "Elegí un profesional antes de generar.")
            return
        periodo = self.campo_periodo.text().strip()
        if not periodo:
            QMessageBox.warning(self, "Falta el período", "Ingresá el período a simular (AAAA-MM).")
            return
        if not self._bloques:
            QMessageBox.warning(self, "Sin bloques", "Agregá al menos un bloque antes de generar.")
            return
        try:
            liquidacion = calcular_liquidacion_simulada(
                self.conn, id_profesional=id_profesional, periodo=periodo, bloques=self._bloques,
            )
            carpeta = carpeta_liquidaciones_simuladas(self.conn)
            ruta = generar_pdf_liquidacion_simulada(self.conn, liquidacion, str(carpeta))
        except ValueError as exc:
            QMessageBox.warning(self, "No se pudo generar", str(exc))
            return
        self._mostrar_resultado(liquidacion)
        QMessageBox.information(self, "Liquidación simulada generada", f"Se generó el archivo:\n{ruta}")

    def _mostrar_resultado(self, liquidacion: LiquidacionSimulada) -> None:
        subtotales = liquidacion.subtotales_bloques

        self.tabla_subtotales.setRowCount(len(subtotales) + 1)
        for fila, subtotal in enumerate(subtotales):
            for columna, item in enumerate(_fila_subtotal_bloque(subtotal)):
                self.tabla_subtotales.setItem(fila, columna, item)

        total_horas_semanales = sum(s.horas_semanales for s in subtotales)
        total_horas_mensuales = sum(s.horas_mensuales for s in subtotales)
        total_bruto = sum(s.bruto for s in subtotales)
        total_descuento = sum(s.descuento for s in subtotales)
        total_neto = sum(s.neto for s in subtotales)

        fila_total = [
            QTableWidgetItem("Total"), item_numero(_fmt_horas(total_horas_semanales)),
            item_numero(_fmt_horas(total_horas_mensuales)),
            item_monto(total_bruto), QTableWidgetItem(""), item_monto(-total_descuento), item_monto(total_neto),
        ]
        for columna, item in enumerate(fila_total):
            item.setBackground(QColor(_COLOR_FILA_TOTAL))
            self.tabla_subtotales.setItem(len(subtotales), columna, item)
        self.tabla_subtotales.resizeColumnsToContents()
