"""Centro de mensajería (DC-02, DC-03): lista de profesionales categoría R
y A ordenada por color (marrón, verde, amarillo, naranja, rojo, violeta,
celeste, azul, gris — DC-02 §2.1) y, dentro de cada color, por código.

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
Solo regulares / Solo aisladas."""
from __future__ import annotations

import os
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.negocio.archivos_generados import carpeta_base, carpeta_profesional
from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio
from app.negocio.mensajeria import (
    COLORES_ENVIADOS,
    COLORES_PENDIENTES_ENVIO,
    color_profesional,
    limpiar_plazos_vencidos_o_regularizados,
    marcar_mensaje_aislada_generado,
    marcar_mensaje_previo_generado,
)
from app.negocio.mensajes import (
    liquidacion_del_periodo,
    mensaje_detalle_reserva_aislada,
    mensaje_envio_liquidacion,
    mensaje_grupal,
    mensaje_situacion_1,
    mensaje_situacion_2,
    mensaje_situacion_3,
    mensaje_situacion_4,
    mensaje_situacion_5,
    nombre_para_mensaje,
)
from app.pdf.liquidacion_pdf import generar_pdf_liquidacion
from app.repositorio.registro import obtener_repositorio

_COLUMNA_ENVIADA = 4
_COLUMNA_BOTON = 5

_ORDEN_COLOR = {
    color: orden for orden, color in enumerate(
        ("marron", "verde", "amarillo", "naranja", "rojo", "violeta", "celeste", "azul", "gris")
    )
}

_ETIQUETA_COLOR = {
    "marron": "🟤 Marrón", "verde": "🟢 Verde", "amarillo": "🟡 Amarillo",
    "naranja": "🟠 Naranja", "rojo": "🔴 Rojo", "violeta": "🟣 Violeta",
    "celeste": "🔵 Celeste", "azul": "🔵 Azul", "gris": "⚫ Gris",
}
_COLOR_FONDO = {
    "marron": "#8D6E63", "verde": "#4CAF50", "amarillo": "#F5D547",
    "naranja": "#E07B39", "rojo": "#C0392B", "violeta": "#8E44AD",
    "celeste": "#5DADE2", "azul": "#2E5C8A", "gris": "#9E9E9E",
}
_COLOR_TEXTO_CLARO = {"amarillo", "celeste"}  # el resto usa letra blanca

# DC-03 "Resumen de asignaciones": check de envío solo disponible para estos colores.
_COLORES_CON_CHECK = {"amarillo", "verde", "naranja", "rojo", "violeta", "gris"}

_FILTROS = [
    ("Todos", "todos"),
    ("Pendientes de envío", "pendientes"),
    ("Enviados", "enviados"),
    ("Solo regulares", "regulares"),
    ("Solo aisladas", "aisladas"),
]
_FILTRO_DEFAULT = "pendientes"


def _clave_codigo(codigo: str | None) -> tuple[str, int, str]:
    """Orden natural para IdCodigo tipo "R1".."R10" (sin ceros a la
    izquierda): prefijo alfabético + número, no orden de texto puro."""
    codigo = (codigo or "").strip()
    i = 0
    while i < len(codigo) and not codigo[i].isdigit():
        i += 1
    numero = codigo[i:]
    return (codigo[:i], int(numero) if numero.isdigit() else 0, codigo)


class CentroMensajeria(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._profesionales: list[sqlite3.Row] = []
        self._actualizando_tabla = False
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        titulo = QLabel("Centro de mensajería")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        fila_filtros = QHBoxLayout()
        fila_filtros.addWidget(QLabel("Filtro:"))
        self.combo_filtro = QComboBox()
        for etiqueta, clave in _FILTROS:
            self.combo_filtro.addItem(etiqueta, clave)
        self.combo_filtro.setCurrentIndex([clave for _, clave in _FILTROS].index(_FILTRO_DEFAULT))
        self.combo_filtro.currentIndexChanged.connect(self.actualizar)
        fila_filtros.addWidget(self.combo_filtro)

        fila_filtros.addWidget(QLabel("Período:"))
        self.campo_periodo = QLineEdit()
        self.campo_periodo.editingFinished.connect(self.actualizar)
        fila_filtros.addWidget(self.campo_periodo)

        boton_actualizar = QPushButton("Actualizar")
        boton_actualizar.clicked.connect(self.actualizar)
        fila_filtros.addWidget(boton_actualizar)

        boton_grupal = QPushButton("Mensaje grupal")
        boton_grupal.setObjectName("botonPrimario")
        boton_grupal.clicked.connect(self._mostrar_mensaje_grupal)
        fila_filtros.addWidget(boton_grupal)
        fila_filtros.addStretch()
        layout.addLayout(fila_filtros)

        splitter = QSplitter()
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Profesional", "Código", "Color", "Saldo anterior", "Enviada", ""]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.itemChanged.connect(self._al_cambiar_enviada)
        splitter.addWidget(self.tabla)

        panel_derecho = QWidget()
        layout_derecho = QVBoxLayout(panel_derecho)

        fila_incluir = QHBoxLayout()
        self.check_incluir_consultorio = QCheckBox("Incluir consultorio")
        self.check_incluir_consultorio.setChecked(True)
        fila_incluir.addWidget(self.check_incluir_consultorio)
        self.check_incluir_unidad = QCheckBox("Incluir unidad")
        self.check_incluir_unidad.setChecked(True)
        fila_incluir.addWidget(self.check_incluir_unidad)
        self.check_incluir_edificio = QCheckBox("Incluir edificio")
        self.check_incluir_edificio.setChecked(True)
        fila_incluir.addWidget(self.check_incluir_edificio)
        fila_incluir.addStretch()
        layout_derecho.addLayout(fila_incluir)

        fila_combinar = QHBoxLayout()
        self.check_combinar_misma_unidad = QCheckBox("Combinar misma unidad")
        fila_combinar.addWidget(self.check_combinar_misma_unidad)
        self.check_combinar_distintas_unidades = QCheckBox("Combinar distintas unidades")
        fila_combinar.addWidget(self.check_combinar_distintas_unidades)
        fila_combinar.addStretch()
        layout_derecho.addLayout(fila_combinar)

        self.texto_mensaje = QPlainTextEdit()
        layout_derecho.addWidget(self.texto_mensaje, stretch=1)
        fila_acciones = QHBoxLayout()
        boton_copiar = QPushButton("Copiar mensaje")
        boton_copiar.clicked.connect(self._copiar_mensaje)
        fila_acciones.addWidget(boton_copiar)
        fila_acciones.addStretch()
        layout_derecho.addLayout(fila_acciones)
        splitter.addWidget(panel_derecho)
        layout.addWidget(splitter, stretch=1)

        self.campo_periodo.setText(periodo_actual(self.conn))

    # ------------------------------------------------------------------ listado

    def actualizar(self) -> None:
        periodo = self._periodo()
        limpiar_plazos_vencidos_o_regularizados(self.conn)
        filtro = self.combo_filtro.currentData()
        self._profesionales = self._listar_filtrados(periodo, filtro)
        self._profesionales.sort(key=lambda p: self._clave_orden(p, periodo))

        self._actualizando_tabla = True
        try:
            self.tabla.setRowCount(len(self._profesionales))
            for fila_idx, profesional in enumerate(self._profesionales):
                color = color_profesional(self.conn, profesional, periodo)
                nombre = f"{nombre_para_mensaje(profesional)} ({profesional['Apellido']})"
                self.tabla.setItem(fila_idx, 0, QTableWidgetItem(nombre))
                self.tabla.setItem(fila_idx, 1, QTableWidgetItem(profesional["IdCodigo"] or ""))
                self.tabla.setItem(fila_idx, 2, QTableWidgetItem(_ETIQUETA_COLOR.get(color, "")))
                self.tabla.setItem(fila_idx, 3, QTableWidgetItem(f"$ {profesional['SaldoCuentaAnterior']:,.2f}"))
                self.tabla.setItem(fila_idx, _COLUMNA_ENVIADA, self._item_enviada(profesional, color, periodo))

                boton = QPushButton("Generar texto")
                boton.clicked.connect(lambda _checked=False, p=profesional: self._generar_y_mostrar(p))
                self.tabla.setCellWidget(fila_idx, _COLUMNA_BOTON, boton)

                if color in _COLOR_FONDO:
                    fondo = QColor(_COLOR_FONDO[color])
                    letra = QColor("#000000" if color in _COLOR_TEXTO_CLARO else "#FFFFFF")
                    for columna in range(4):
                        celda = self.tabla.item(fila_idx, columna)
                        celda.setBackground(fondo)
                        celda.setForeground(letra)
        finally:
            self._actualizando_tabla = False
        self.tabla.resizeColumnsToContents()

    def _listar_filtrados(self, periodo: str, filtro: str) -> list[sqlite3.Row]:
        """Base = profesionales de categoría R o A (las únicas con
        contenido propio en este centro de mensajería), acotada según el
        filtro elegido (DC-02 §4)."""
        candidatos = [
            p for p in obtener_repositorio(self.conn, "Profesional").listar()
            if p["CategoriaProfesional"] in ("R", "A")
        ]
        if filtro == "regulares":
            return [p for p in candidatos if p["CategoriaProfesional"] == "R"]
        if filtro == "aisladas":
            return [p for p in candidatos if p["CategoriaProfesional"] == "A"]
        if filtro in ("pendientes", "enviados"):
            grupo = COLORES_PENDIENTES_ENVIO if filtro == "pendientes" else COLORES_ENVIADOS
            return [p for p in candidatos if color_profesional(self.conn, p, periodo) in grupo]
        return candidatos  # "todos"

    def _clave_orden(self, profesional: sqlite3.Row, periodo: str) -> tuple[int, tuple[str, int, str]]:
        """Orden por color (DC-02 §2.1) y, dentro de cada color, por
        código (confirmado por el usuario para toda la lista, no solo
        para gris)."""
        color = color_profesional(self.conn, profesional, periodo)
        return (_ORDEN_COLOR.get(color, 99), _clave_codigo(profesional["IdCodigo"]))

    def _item_enviada(self, profesional: sqlite3.Row, color: str | None, periodo: str) -> QTableWidgetItem:
        """Check "Enviada" (DC-02 §3, DC-03 "Resumen de asignaciones"):
        marcable y reversible, solo disponible para los colores que lo
        tienen asignado."""
        item = QTableWidgetItem()
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
        profesional = self._profesionales[item.row()]
        periodo = self._periodo()
        marcar = item.checkState() == Qt.CheckState.Checked
        try:
            if marcar:
                self._marcar_como_enviada(profesional, periodo)
            else:
                marcar_estado_envio(
                    self.conn, id_profesional=profesional["IdProfesional"], periodo=periodo, enviada=False,
                )
        except ValueError as error:
            QMessageBox.warning(self, "Centro de mensajería", str(error))
        self.actualizar()

    def _marcar_como_enviada(self, profesional: sqlite3.Row, periodo: str) -> None:
        """DC-02 §2.3: al marcar el check se genera el PDF de la
        liquidación, se carga el texto al portapapeles y el profesional
        baja al grupo gris. Para violeta además se borra el plazo
        extendido (DC-02 §2.4)."""
        id_profesional = profesional["IdProfesional"]
        color = color_profesional(self.conn, profesional, periodo)

        if carpeta_base(self.conn) is None:
            raise ValueError("Configurá primero la carpeta base de archivos en Configuración general.")

        id_liquidacion, liquidacion = emitir_liquidacion(
            self.conn, id_profesional=id_profesional, periodo=periodo,
            fecha_emision=fecha_actual(self.conn).isoformat(),
        )
        directorio = str(carpeta_profesional(self.conn, profesional["IdCodigo"]))
        ruta = generar_pdf_liquidacion(self.conn, liquidacion, directorio)
        obtener_repositorio(self.conn, "LiquidacionEmitida").actualizar(
            id_liquidacion, NombreArchivo=os.path.basename(ruta)
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
        """DC-03 "Resumen de asignaciones", botón "Generar texto"."""
        id_profesional = profesional["IdProfesional"]
        if profesional["CategoriaProfesional"] == "A":
            texto = mensaje_detalle_reserva_aislada(
                self.conn, id_profesional=id_profesional, periodo=periodo,
                incluir_consultorio=self.check_incluir_consultorio.isChecked(),
                incluir_unidad=self.check_incluir_unidad.isChecked(),
                incluir_edificio=self.check_incluir_edificio.isChecked(),
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
            liquidacion = liquidacion_del_periodo(self.conn, id_profesional, periodo)
            if liquidacion is not None and liquidacion["EstadoEnvio"] == "Enviada":
                return mensaje_situacion_4(self.conn, id_profesional)
            return mensaje_situacion_5(self.conn, id_profesional, periodo)
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
