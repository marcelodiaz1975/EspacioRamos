"""Centro de mensajería (DC-02, DC-03): lista de profesionales categoría R
y A ordenada por color (marrón, verde, amarillo, naranja, rojo, violeta,
celeste, azul, bordó, gris — DC-02 §2.1 + bordó, pedido posterior de la
clienta) y, dentro de cada color, por código.

Cada fila tiene dos controles independientes (DC-02 §3): el check "Enviada"
(solo habilitado para los colores que lo tienen asignado — DC-03 "Resumen
de asignaciones") y el botón "Generar texto" (siempre disponible, carga al
portapapeles el mensaje que corresponde al color actual). No están
encadenados: el check cambia el estado, el botón solo genera texto.

Sección 5.1: para categoría A, los 5 controles (todos marcados por
default salvo los "combinar") que arman el detalle de reserva aislada —
Incluir consultorio / Incluir unidad / Incluir edificio / Combinar misma
unidad / Combinar distintas unidades.

Filtros exactos de DC-02 §4: Todos / Pendientes de envío / Enviados /
Solo regulares / Solo aisladas.

Reordenamiento de formularios (Excel de la clienta): dejó de ser una
pantalla propia del menú y pasó a ser la solapa "Centro de mensajería"
de "Grilla y mensajería" (`_PanelCentroMensajeria`, junto a "Grilla
semanal" y "Mensajes predefinidos" — ver `grilla_y_mensajeria.py`). Por
eso ya no tiene título Nivel 1 ni su propio `QTabWidget`/`QScrollArea`
externo — mismo criterio que `_PanelImportacion`/`_PanelBloquesRigidos`."""
from __future__ import annotations

import os
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.orden_tabla import clave_orden_codigo
from app.negocio.archivos_generados import carpeta_base, carpeta_profesional
from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.formato import formatear_moneda
from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio
from app.negocio.mensajeria import (
    COLORES_ENVIADOS,
    COLORES_PENDIENTES_ENVIO,
    color_profesional,
    limpiar_plazos_vencidos_o_regularizados,
    marcar_mensaje_aislada_generado,
    marcar_mensaje_previo_generado,
    marcar_recordatorio_mensajeria_generado,
)
from app.negocio.mensajes import (
    liquidacion_del_periodo,
    mensaje_detalle_reserva_aislada,
    mensaje_envio_liquidacion,
    mensaje_grupal,
    mensaje_recordatorio_fin_de_mes,
    mensaje_situacion_1,
    mensaje_situacion_2,
    mensaje_situacion_3,
    mensaje_situacion_5,
)
from app.pdf.liquidacion_pdf import generar_pdf_liquidacion
from app.repositorio.registro import obtener_repositorio

_COLUMNA_ENVIADA = 5
_COLUMNA_BOTON = 6

_ORDEN_COLOR = {
    color: orden for orden, color in enumerate(
        ("marron", "verde", "amarillo", "naranja", "rojo", "violeta", "celeste", "azul", "bordo", "gris")
    )
}

# Texto de la columna "Estado" (confirmado por el usuario) — el color de la
# fila ya identifica visualmente cuál es cuál, esto es la descripción en
# palabras para quien lo lea sin distinguir colores.
_ESTADO_TEXTO = {
    "marron": "Deuda en rango de tolerancia",
    "verde": "Situación regular",
    "amarillo": "Deuda en rango de tolerancia",
    "naranja": "Deuda fuera del rango de tolerancia",
    "rojo": "Plan acordado y con deuda",
    "violeta": "Plazo extendido activo",
    "celeste": "Con aisladas para enviar mensaje",
    "azul": "Con aisladas y mensaje enviado",
    "bordo": "Liquidación enviada, recordatorio de fin de mes",
    "gris": "Liquidación enviada",
}
_COLOR_FONDO = {
    "marron": "#8D6E63", "verde": "#4CAF50", "amarillo": "#F5D547",
    "naranja": "#E07B39", "rojo": "#C0392B", "violeta": "#8E44AD",
    "celeste": "#5DADE2", "azul": "#2E5C8A", "bordo": "#6D1B2A", "gris": "#9E9E9E",
}
_COLOR_TEXTO_CLARO = {"amarillo", "celeste"}  # el resto usa letra blanca

# DC-03 "Resumen de asignaciones": check de envío solo disponible para estos colores.
# Bordó se suma con el mismo criterio que gris (liquidación ya enviada, el
# check sigue sirviendo para desmarcarla a mano si hiciera falta corregir).
_COLORES_CON_CHECK = {"amarillo", "verde", "naranja", "rojo", "violeta", "bordo", "gris"}

_FILTROS = [
    ("Todos", "todos"),
    ("Pendientes de envío", "pendientes"),
    ("Enviados", "enviados"),
    ("Solo regulares", "regulares"),
    ("Solo aisladas", "aisladas"),
]
_FILTRO_DEFAULT = "pendientes"
_ANCHO_CAMPO = 280  # combo Filtro, campo Período y los botones del panel izquierdo


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _nombre_con_tratamiento(profesional: sqlite3.Row) -> str:
    """Columna "Profesional" de la grilla: tratamiento, nombre y apellido
    tal cual (ej. "Lic. Virginia Lo Veci"), para que el operador
    identifique a la persona sin ambigüedad — a diferencia de
    `nombre_para_mensaje` (Apodo/NombrePila/Tratamiento), pensado para el
    texto que recibe el profesional, no para esta lista."""
    partes = [p for p in (profesional["Tratamiento"], profesional["NombrePila"], profesional["Apellido"]) if p]
    return " ".join(partes)


class _ItemCodigo(QTableWidgetItem):
    """Ordena la columna "Código" con el mismo criterio natural que ya
    usa el orden por defecto (`clave_orden_codigo`, compartida con el
    resto del sistema — ver CLAUDE.md "Orden natural de códigos de
    profesional") — comparar como texto pondría "R10" antes que "R2"."""

    def __lt__(self, other: object) -> bool:
        if isinstance(other, _ItemCodigo):
            return clave_orden_codigo(self.text()) < clave_orden_codigo(other.text())
        return super().__lt__(other)


class _ItemMoneda(QTableWidgetItem):
    """Ordena las columnas "Saldo anterior"/"Saldo actual" por el valor
    numérico real, no por el texto ya formateado ("$ 1.234,00"), y va
    alineado a la derecha (confirmado por la clienta para todo el
    sistema)."""

    def __init__(self, texto: str, valor: float):
        super().__init__(texto)
        self._valor = valor
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other: object) -> bool:
        if isinstance(other, _ItemMoneda):
            return self._valor < other._valor
        return super().__lt__(other)


class _PanelCentroMensajeria(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._profesionales: list[sqlite3.Row] = []
        self._actualizando_tabla = False
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar":
        el QTabWidget contenedor todavía no está mostrado y el foco se
        queda en su tab bar. Al mostrarse la solapa se repite el pedido
        de foco en Filtro, que es cuando realmente surte efecto (mismo
        motivo que Reservas/Liquidación)."""
        super().showEvent(event)
        self.combo_filtro.setFocus()

    def _armar_ui(self) -> None:
        layout_solapa = QHBoxLayout(self)

        panel_izquierda = QWidget()
        columna = QVBoxLayout(panel_izquierda)
        columna.setContentsMargins(0, 0, 0, 0)

        columna.addWidget(_titulo_campo("Filtro"))
        self.combo_filtro = QComboBox()
        for etiqueta, clave in _FILTROS:
            self.combo_filtro.addItem(etiqueta, clave)
        self.combo_filtro.setCurrentIndex([clave for _, clave in _FILTROS].index(_FILTRO_DEFAULT))
        self.combo_filtro.currentIndexChanged.connect(self.actualizar)
        self.combo_filtro.setFixedWidth(_ANCHO_CAMPO)
        columna.addWidget(self.combo_filtro)

        columna.addWidget(_titulo_campo("Período"))
        self.campo_periodo = QLineEdit()
        self.campo_periodo.editingFinished.connect(self.actualizar)
        self.campo_periodo.setFixedWidth(_ANCHO_CAMPO)
        columna.addWidget(self.campo_periodo)

        self.check_combinar_misma_unidad = QCheckBox("Combinar misma unidad")
        columna.addWidget(self.check_combinar_misma_unidad)
        self.check_combinar_distintas_unidades = QCheckBox("Combinar distintas unidades")
        columna.addWidget(self.check_combinar_distintas_unidades)

        boton_copiar = QPushButton("Copiar mensaje")
        boton_copiar.setObjectName("botonPrimario")
        boton_copiar.clicked.connect(self._copiar_mensaje)
        columna.addWidget(boton_copiar)

        boton_actualizar = QPushButton("Actualizar")
        boton_actualizar.setObjectName("botonSecundario")
        boton_actualizar.clicked.connect(self.actualizar)
        columna.addWidget(boton_actualizar)

        boton_grupal = QPushButton("Mensaje grupal")
        boton_grupal.setObjectName("botonSecundario")
        boton_grupal.clicked.connect(self._mostrar_mensaje_grupal)
        columna.addWidget(boton_grupal)

        for boton in (boton_copiar, boton_actualizar, boton_grupal):
            boton.setFixedWidth(_ANCHO_CAMPO)

        columna.addWidget(_linea_divisoria())
        columna.addWidget(_titulo_campo("Vista previa"))
        self.texto_mensaje = QPlainTextEdit()
        self.texto_mensaje.setFixedWidth(_ANCHO_CAMPO)
        # Sin alto fijo: se estira con `stretch=1` para llegar hasta el
        # mismo borde inferior que la tabla de la derecha — pedido
        # explícito de la clienta, en vez del alto fijo (220px) + un
        # `addStretch()` final que dejaba un espacio en blanco debajo del
        # cuadro sin usar.
        columna.addWidget(self.texto_mensaje, stretch=1)
        layout_solapa.addWidget(panel_izquierda)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(7)
        self.tabla.setHorizontalHeaderLabels(
            ["Código", "Profesional", "Estado", "Saldo anterior", "Saldo actual", "Enviada", ""]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        # Por defecto queda en el orden de siempre (por color); un clic en
        # un título la ordena por esa columna hasta el próximo refresco
        # (`actualizar()` vuelve a dejarla en el orden por color).
        self.tabla.setSortingEnabled(True)
        self.tabla.itemChanged.connect(self._al_cambiar_enviada)
        layout_solapa.addWidget(self.tabla, stretch=1)

        self.campo_periodo.setText(periodo_actual(self.conn))

    # ------------------------------------------------------------------ listado

    def actualizar(self) -> None:
        periodo = self._periodo()
        limpiar_plazos_vencidos_o_regularizados(self.conn)
        filtro = self.combo_filtro.currentData()
        self._profesionales = self._listar_filtrados(periodo, filtro)
        # Dos pasadas (sort estable): primero código descendente, después
        # color ascendente — así, a igualdad de color, queda ordenado por
        # código descendente (confirmado por el usuario).
        self._profesionales.sort(key=lambda p: clave_orden_codigo(p["IdCodigo"]), reverse=True)
        self._profesionales.sort(key=lambda p: _ORDEN_COLOR.get(color_profesional(self.conn, p, periodo), 99))

        # Desactivada mientras se repuebla: si no, un clic previo en un
        # título reordenaría filas fila por fila a medida que se van
        # cargando, mezclando el índice de `self._profesionales` con la
        # tabla — se vuelve a activar recién al final, ya en el orden por
        # color de siempre.
        self.tabla.setSortingEnabled(False)
        self._actualizando_tabla = True
        try:
            self.tabla.setRowCount(len(self._profesionales))
            for fila_idx, profesional in enumerate(self._profesionales):
                color = color_profesional(self.conn, profesional, periodo)
                saldo_anterior = profesional["SaldoCuentaAnterior"] or 0.0
                saldo_actual = saldo_anterior + (profesional["SaldoCuentaActual"] or 0.0)
                self.tabla.setItem(fila_idx, 0, _ItemCodigo(profesional["IdCodigo"] or ""))
                self.tabla.setItem(fila_idx, 1, QTableWidgetItem(_nombre_con_tratamiento(profesional)))
                self.tabla.setItem(fila_idx, 2, QTableWidgetItem(_ESTADO_TEXTO.get(color, "")))
                self.tabla.setItem(fila_idx, 3, _ItemMoneda(formatear_moneda(saldo_anterior), saldo_anterior))
                self.tabla.setItem(fila_idx, 4, _ItemMoneda(formatear_moneda(saldo_actual), saldo_actual))
                self.tabla.setItem(fila_idx, _COLUMNA_ENVIADA, self._item_enviada(profesional, color, periodo))

                # Reusa el botón si la fila ya tenía uno (ej. al cambiar de
                # filtro) en vez de destruirlo y crear uno nuevo en la misma
                # celda: reemplazar un cellWidget in situ es un bug real de
                # Qt (comprobado con capturas) — el botón viejo puede seguir
                # pintado, superpuesto o angosto, hasta que el próximo
                # refresco de la tabla lo termina de limpiar. Igual criterio
                # que la leyenda de colores de Vista rápida, resuelto acá
                # evitando directamente el reemplazo en vez de ocultarlo.
                boton = self.tabla.cellWidget(fila_idx, _COLUMNA_BOTON)
                if boton is None:
                    boton = QPushButton("Generar texto")
                    self.tabla.setCellWidget(fila_idx, _COLUMNA_BOTON, boton)
                else:
                    boton.clicked.disconnect()
                boton.clicked.connect(lambda _checked=False, p=profesional: self._generar_y_mostrar(p))

                if color in _COLOR_FONDO:
                    fondo = QColor(_COLOR_FONDO[color])
                    letra = QColor("#000000" if color in _COLOR_TEXTO_CLARO else "#FFFFFF")
                    for columna in range(5):
                        celda = self.tabla.item(fila_idx, columna)
                        celda.setBackground(fondo)
                        celda.setForeground(letra)
        finally:
            self._actualizando_tabla = False
        self.tabla.setSortingEnabled(True)
        self.tabla.resizeColumnsToContents()

    def _listar_filtrados(self, periodo: str, filtro: str) -> list[sqlite3.Row]:
        """Base = profesionales de categoría R o A (las únicas con
        contenido propio en este centro de mensajería), acotada según el
        filtro elegido (DC-02 §4). Los A sin ninguna reserva aislada del
        mes en curso en adelante se depuran de la lista (DC-02 §2.2:
        "los profesionales que ya no tienen reservas aisladas activas ni
        pendientes se depuran")."""
        candidatos = [
            p for p in obtener_repositorio(self.conn, "Profesional").listar()
            if p["CategoriaProfesional"] in ("R", "A")
        ]
        candidatos = [
            p for p in candidatos
            if p["CategoriaProfesional"] != "A" or self._tiene_aisladas_vigentes(p["IdProfesional"], periodo)
        ]
        if filtro == "regulares":
            return [p for p in candidatos if p["CategoriaProfesional"] == "R"]
        if filtro == "aisladas":
            return [p for p in candidatos if p["CategoriaProfesional"] == "A"]
        if filtro in ("pendientes", "enviados"):
            grupo = COLORES_PENDIENTES_ENVIO if filtro == "pendientes" else COLORES_ENVIADOS
            return [p for p in candidatos if color_profesional(self.conn, p, periodo) in grupo]
        return candidatos  # "todos"

    def _tiene_aisladas_vigentes(self, id_profesional: int, periodo: str) -> bool:
        anio, mes = (int(p) for p in periodo.split("-"))
        primer_dia_periodo = f"{anio:04d}-{mes:02d}-01"
        fila = self.conn.execute(
            "SELECT 1 FROM ReservaAislada WHERE IdProfesional = ? AND Estado = 'Confirmada' AND Fecha >= ? LIMIT 1",
            (id_profesional, primer_dia_periodo),
        ).fetchone()
        return fila is not None

    def _item_enviada(self, profesional: sqlite3.Row, color: str | None, periodo: str) -> QTableWidgetItem:
        """Check "Enviada" (DC-02 §3, DC-03 "Resumen de asignaciones"):
        marcable y reversible, solo disponible para los colores que lo
        tienen asignado. Guarda el IdProfesional en el propio ítem: con
        los títulos ordenables, la fila que ve el usuario al tildar ya no
        tiene por qué coincidir con su posición en `self._profesionales`."""
        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setData(Qt.ItemDataRole.UserRole, profesional["IdProfesional"])
        if color not in _COLORES_CON_CHECK:
            item.setFlags(Qt.ItemFlag.ItemIsSelectable)
            item.setToolTip("El check de envío no está disponible para este color.")
            return item
        liquidacion = liquidacion_del_periodo(self.conn, profesional["IdProfesional"], periodo)
        enviada = liquidacion is not None and liquidacion["EstadoEnvio"] == "Enviada"
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        item.setCheckState(Qt.CheckState.Checked if enviada else Qt.CheckState.Unchecked)
        return item

    def _periodo(self) -> str:
        return self.campo_periodo.text().strip() or periodo_actual(self.conn)

    # -------------------------------------------------------------- check envío

    def _al_cambiar_enviada(self, item: QTableWidgetItem) -> None:
        if self._actualizando_tabla or item.column() != _COLUMNA_ENVIADA:
            return
        id_profesional = item.data(Qt.ItemDataRole.UserRole)
        profesional = next(p for p in self._profesionales if p["IdProfesional"] == id_profesional)
        periodo = self._periodo()
        marcar = item.checkState() == Qt.CheckState.Checked
        try:
            if marcar:
                self._marcar_como_enviada(profesional, periodo)
            else:
                self._desmarcar_enviada(profesional, periodo)
        except ValueError as error:
            QMessageBox.warning(self, "Centro de mensajería", str(error))
        self.actualizar()

    def _desmarcar_enviada(self, profesional: sqlite3.Row, periodo: str) -> None:
        marcar_estado_envio(
            self.conn, id_profesional=profesional["IdProfesional"], periodo=periodo, enviada=False,
        )

    def _marcar_como_enviada(self, profesional: sqlite3.Row, periodo: str) -> None:
        """DC-02 §2.3: al marcar el check se genera el PDF de la
        liquidación, se carga el texto al portapapeles y el profesional
        baja al grupo gris. Para violeta además se borra el plazo
        extendido (DC-02 §2.4)."""
        id_profesional = profesional["IdProfesional"]
        color = color_profesional(self.conn, profesional, periodo)

        if carpeta_base(self.conn) is None:
            raise ValueError("Configurá primero la carpeta base de archivos en Configuración general.")

        directorio = carpeta_profesional(self.conn, profesional["IdCodigo"])
        id_liquidacion, liquidacion = emitir_liquidacion(
            self.conn, id_profesional=id_profesional, periodo=periodo,
            fecha_emision=fecha_actual(self.conn).isoformat(),
        )
        ruta_generada = generar_pdf_liquidacion(self.conn, liquidacion, str(directorio))
        obtener_repositorio(self.conn, "LiquidacionEmitida").actualizar(
            id_liquidacion, NombreArchivo=os.path.basename(ruta_generada)
        )
        marcar_estado_envio(self.conn, id_profesional=id_profesional, periodo=periodo, enviada=True)
        if color == "violeta":
            obtener_repositorio(self.conn, "Profesional").actualizar(
                id_profesional, PlazoPagoExtendido=None, MotivoPlazoExtra=None,
            )

        texto = (
            mensaje_situacion_2(self.conn, id_profesional, periodo) if color == "amarillo"
            else mensaje_envio_liquidacion(self.conn, id_profesional, periodo)
        )
        self.texto_mensaje.setPlainText(texto)
        QGuiApplication.clipboard().setText(texto)

    # -------------------------------------------------------- botón "Generar texto"

    def _generar_y_mostrar(self, profesional: sqlite3.Row) -> None:
        periodo = self._periodo()
        color = color_profesional(self.conn, profesional, periodo)
        try:
            texto = self._texto_para_boton(profesional, color, periodo)
        except ValueError as error:
            texto = str(error)
        self.texto_mensaje.setPlainText(texto)
        QGuiApplication.clipboard().setText(texto)
        self.actualizar()

    def _texto_para_boton(self, profesional: sqlite3.Row, color: str | None, periodo: str) -> str:
        """DC-03 "Resumen de asignaciones", botón "Generar texto". Marrón
        y celeste disparan una transición de estado (a amarillo y azul
        respectivamente).

        Consultorio y unidad van siempre (los checks "Incluir..." son de
        las pantallas de oferta/búsqueda, no de este mensaje); el
        edificio se agrega solo o no según la regla del edificio
        (`mensaje_detalle_reserva_aislada` ya la aplica sola con el
        default `incluir_edificio=True`, no hace falta pasarlo)."""
        id_profesional = profesional["IdProfesional"]
        if profesional["CategoriaProfesional"] == "A":
            texto = mensaje_detalle_reserva_aislada(
                self.conn, id_profesional=id_profesional, periodo=periodo,
                combinar_misma_unidad=self.check_combinar_misma_unidad.isChecked(),
                combinar_distintas_unidades=self.check_combinar_distintas_unidades.isChecked(),
            )
            marcar_mensaje_aislada_generado(self.conn, id_profesional, periodo)
            return texto

        hoy = fecha_actual(self.conn)
        if color == "marron":
            texto = mensaje_situacion_3(self.conn, id_profesional, periodo, hoy)
            marcar_mensaje_previo_generado(self.conn, id_profesional, periodo)
            return texto
        if color in ("amarillo", "naranja"):
            return mensaje_situacion_1(self.conn, id_profesional, hoy)
        if color == "rojo":
            return mensaje_situacion_5(self.conn, id_profesional, periodo)
        if color == "bordo":
            texto = mensaje_recordatorio_fin_de_mes(self.conn, id_profesional, periodo)
            marcar_recordatorio_mensajeria_generado(self.conn, id_profesional, periodo)
            return texto
        if color in ("verde", "violeta", "gris"):
            return mensaje_envio_liquidacion(self.conn, id_profesional, periodo)
        return ""

    # ------------------------------------------------------------------- varios

    def _copiar_mensaje(self) -> None:
        QGuiApplication.clipboard().setText(self.texto_mensaje.toPlainText())

    def _mostrar_mensaje_grupal(self) -> None:
        texto = mensaje_grupal(self.conn, self._periodo())
        self.texto_mensaje.setPlainText(texto)
        QGuiApplication.clipboard().setText(texto)
        self.tabla.clearSelection()
