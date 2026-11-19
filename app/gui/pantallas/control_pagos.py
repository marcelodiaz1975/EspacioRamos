"""Módulo extendido ME1 — "Control de pagos" (sección 3.35-3.37): control
mes a mes de todo lo que hay que abonar, sea del espacio o personal/
familiar — ver el docstring de `app.negocio.control_pagos` para el
modelo completo.

Pantalla compuesta con cinco solapas: "Carga y control" e "Historial"
(este archivo) más los tres catálogos livianos que necesita Afectación
("Inmuebles personales"/"Rodados"/"Personas", anidados de `catalogos.py`,
sin código propio). Solo aparece en el menú si `Configuracion.
ModulosExtendidos` está prendido — ver `gui_main.construir_secciones`."""
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.estilos import COLOR_AMARILLO, COLOR_GRIS, COLOR_ROJO, COLOR_TEXTO_CLARO, COLOR_VERDE, COLOR_VIOLETA
from app.gui.pantallas import catalogos
from app.gui.pantallas.novedades import _campo_fecha_opcional, _titulo_campo
from app.gui.pantallas.pagos import _SpinMonto
from app.gui.pantallas.reservas import _FECHA_SIN_DATO
from app.gui.widgets.foco import excluir_tabla_del_tab, instalar_enter_avanza_foco
from app.gui.widgets.items_tabla import item_centrado, item_numero
from app.gui.widgets.orden_tabla import OrdenTabla
from app.gui.widgets.resumen_saldo import item_monto
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.control_pagos import (
    ESTADOS_INSTANCIA,
    TIPOS_AFECTACION,
    actualizar_instancia,
    archivar_instancia,
    crear_concepto,
    dar_de_baja_concepto,
    duplicar_para_periodo_proximo,
    editar_concepto,
    eliminar_instancia_duplicada,
    es_medio_pago_tarjeta,
    generar_instancias_periodo,
    marcar_abonada,
    texto_afectacion,
)
from app.negocio.dias import fecha_actual, periodo_actual, sumar_meses
from app.negocio.listas_editables import opciones_lista
from app.pdf.estilos import clave_orden_unidad
from app.repositorio.registro import obtener_repositorio

_ANCHO_CAMPO = 240
_ANCHO_PANEL_IZQUIERDA = 280

# Pedido explícito de la clienta: rediseño de "Carga y control" en 4
# columnas de igual ancho (ver `_PanelCargaControl._armar_ui`) — todos
# los campos/botones/filtros de las 4 columnas comparten este mismo
# ancho fijo (calculado para que entre el texto más largo sin
# cortarse, el botón "Dar de baja concepto seleccionado": sizeHint
# real medido con QFontMetrics contra la hoja de estilos, 239px).
_ANCHO_CAMPO_CARGA_CONTROL = 240

# "Que el primer elemento de cada una de las 4 columnas arranque en el
# pixel 85" — mismo mecanismo (valor confirmado por medición
# programática contra esta estructura en 4 columnas, sin QScrollArea)
# que Reservas regulares/aisladas y los paneles de Novedades.
_ALTO_TITULO_CARGA_CONTROL = 7

# Colores de fondo de fila según proximidad del vencimiento (pedido
# explícito de la clienta) — mismos valores hex que `app.gui.pantallas.
# mensajeria._COLOR_FONDO`, reusados vía las constantes de `estilos.py`.
_COLOR_FONDO_VENCIMIENTO = {
    "violeta": COLOR_VIOLETA, "rojo": COLOR_ROJO, "amarillo": COLOR_AMARILLO, "verde": COLOR_VERDE,
    "gris": COLOR_GRIS,
}
# Mismo criterio que `mensajeria._COLOR_TEXTO_CLARO`: amarillo (fondo
# claro) usa letra negra, el resto letra blanca.
_COLORES_CON_LETRA_NEGRA = {"amarillo"}

# Tipos de Afectación que necesitan un combo de detalle (el resto,
# "Espacio general"/"Familia", no apuntan a ningún registro puntual).
_TIPOS_CON_DETALLE = ("Edificio", "Unidad", "Inmueble personal", "Rodado", "Persona")

# Pedido explícito de la clienta: Vencimiento en "Carga y control"/
# "Historial" sin el día de la semana (a diferencia de `_campo_fecha`/
# `_campo_fecha_opcional`, usado en el resto del sistema con "ddd
# dd-MM-yyyy") — mismo formato llano que ya usa `reservas._FORMATO_
# FECHA` para otros campos de fecha que tampoco necesitan el día.
_FORMATO_FECHA_SIN_DIA = "dd-MM-yyyy"

# Ancho de columna justo para que entre un importe con este formato y
# esta cantidad de caracteres (pedido explícito de la clienta, "Carga y
# control"/"Historial") — medido con `QFontMetrics` sobre la fuente
# real de la tabla, mismo criterio que `pagos._TEXTO_MONTO_MAXIMO`.
_TEXTO_IMPORTE_MAXIMO = "$ 0.000.000,00"
_PADDING_COLUMNA_IMPORTE = 10

# Colchón para el padding interno que Qt le suma a la celda del
# encabezado — mismo valor/criterio que `imagenes._COLCHON_TITULO_
# COLUMNA` ("Historial", columnas "Período"/"Vencimiento" al mínimo que
# entra el título sin cortar).
_COLCHON_TITULO_COLUMNA = 12


def _fecha_dd_mm_yyyy(fecha_iso: str) -> str:
    """'2026-08-15' -> '15-08-2026' — texto de tabla para Vencimiento,
    mismo formato que `_FORMATO_FECHA_SIN_DIA` en el `QDateEdit`."""
    return date.fromisoformat(fecha_iso).strftime("%d-%m-%Y")


def _linea_divisoria_vertical() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.VLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _campo_vencimiento_sin_dia(conn: sqlite3.Connection):
    """Como `_campo_fecha_opcional`, pero con el formato de Vencimiento
    de esta pantalla (ver `_FORMATO_FECHA_SIN_DIA`)."""
    campo = _campo_fecha_opcional(conn)
    campo.setDisplayFormat(_FORMATO_FECHA_SIN_DIA)
    return campo


class _SpinImporteControlPagos(_SpinMonto):
    """Como `_SpinMonto` (misma presentación "$ 1.234,56"), pero al
    tipear admite el "." como separador decimal — pedido explícito de
    la clienta, puntual de los campos "Importe" de esta pantalla (no
    se tocó `_SpinMonto`, que sigue esperando "," en el resto del
    sistema). También acepta "," (no hace falta reaprender), así que
    no rompe nada tipeado a la vieja usanza."""

    def valueFromText(self, text: str) -> float:  # noqa: N802
        texto = text.strip().replace("$", "").replace(",", ".").strip()
        try:
            return float(texto) if texto else 0.0
        except ValueError:
            return 0.0


def _opciones_edificio(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdEdificio, Nombre FROM Edificio ORDER BY Nombre").fetchall()
    return [(f["IdEdificio"], f["Nombre"]) for f in filas]


def _opciones_unidad(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute(
        "SELECT u.IdUnidad, u.Departamento, e.Nombre AS Edificio FROM Unidad u "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio"
    ).fetchall()
    filas = sorted(filas, key=lambda f: (f["Edificio"], clave_orden_unidad(f["Departamento"])))
    return [(f["IdUnidad"], f"{f['Edificio']} - {f['Departamento']}") for f in filas]


def _opciones_inmueble_personal(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = obtener_repositorio(conn, "InmueblePersonal").listar()
    resultado = []
    for f in filas:
        localidad = obtener_repositorio(conn, "Localidad").obtener(f["IdLocalidad"]) if f["IdLocalidad"] else None
        texto = " ".join(p for p in (f["TipoInmueble"], f["Direccion"]) if p)
        if localidad:
            texto += f", {localidad['Localidad']}"
        resultado.append((f["IdInmueblePersonal"], texto))
    return resultado


def _opciones_rodado(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = obtener_repositorio(conn, "Rodado").listar()
    return [(f["IdRodado"], " ".join(p for p in (f["Marca"], f["Modelo"], f["Dominio"]) if p)) for f in filas]


def _opciones_persona_familia(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = obtener_repositorio(conn, "PersonaFamilia").listar()
    return [(f["IdPersonaFamilia"], f["Nombre"]) for f in filas]


_OPCIONES_POR_TIPO = {
    "Edificio": _opciones_edificio,
    "Unidad": _opciones_unidad,
    "Inmueble personal": _opciones_inmueble_personal,
    "Rodado": _opciones_rodado,
    "Persona": _opciones_persona_familia,
}

_CAMPO_ID_POR_TIPO = {
    "Edificio": "id_edificio",
    "Unidad": "id_unidad",
    "Inmueble personal": "id_inmueble_personal",
    "Rodado": "id_rodado",
    "Persona": "id_persona_familia",
}

_CAMPO_DB_POR_TIPO = {
    "Edificio": "IdEdificio",
    "Unidad": "IdUnidad",
    "Inmueble personal": "IdInmueblePersonal",
    "Rodado": "IdRodado",
    "Persona": "IdPersonaFamilia",
}


def _item_importe(valor: float | None) -> QTableWidgetItem:
    """Como `item_monto`, pero en blanco cuando todavía no se cargó
    ningún importe — "$ 0,00" confundiría "sin cargar" con "cargado en
    cero", dos cosas distintas acá."""
    return QTableWidgetItem("") if valor is None else item_monto(valor)


def _armar_combo_tipo_afectacion() -> QComboBox:
    combo = QComboBox()
    for tipo in TIPOS_AFECTACION:
        combo.addItem(tipo, tipo)
    return combo


def _actualizar_combo_detalle_afectacion(conn: sqlite3.Connection, combo_tipo: QComboBox, combo_detalle: QComboBox) -> None:
    """Repuebla `combo_detalle` según el Tipo elegido — "Espacio
    general"/"Familia" no apuntan a ningún registro puntual, así que
    queda vacío y deshabilitado."""
    tipo = combo_tipo.currentData()
    combo_detalle.blockSignals(True)
    combo_detalle.clear()
    if tipo in _TIPOS_CON_DETALLE:
        combo_detalle.setEnabled(True)
        for id_, etiqueta in _OPCIONES_POR_TIPO[tipo](conn):
            combo_detalle.addItem(etiqueta, id_)
    else:
        combo_detalle.setEnabled(False)
    combo_detalle.blockSignals(False)


def _kwargs_afectacion(combo_tipo: QComboBox, combo_detalle: QComboBox) -> dict:
    tipo = combo_tipo.currentData()
    kwargs = {"tipo_afectacion": tipo}
    if tipo in _TIPOS_CON_DETALLE:
        kwargs[_CAMPO_ID_POR_TIPO[tipo]] = combo_detalle.currentData()
    return kwargs


class _DialogoEditarInstancia(QDialog):
    """Editar vencimiento/monto de UNA instancia puntual — distinto de
    editar los datos del concepto en sí (ver `_DialogoEditarConcepto`).

    `incluir_estado` suma un combo de Estado (Pendiente/Abonado/
    Archivado) — pedido explícito de la clienta para el botón "Editar
    registro" de la solapa "Historial" ("ese botón me tendría que
    permitir editar vencimiento, importe y estado"), para poder
    reabrir algo que el cierre de mes archivó de más sin tener que
    pasar por "Marcar abonado"/"Archivar" por separado. El "Editar
    registro" de "Carga y control" no lo necesita (ahí ya están
    "Marcar abonado"/"Archivar registro" aparte), así que queda en
    `False` por default.

    Pedido explícito de la clienta sobre el Medio de pago del concepto
    (`es_medio_pago_tarjeta`): si es "tarjeta", Vencimiento queda
    deshabilitado (una tarjeta no se controla por vencimiento acá, solo
    por Importe) y no es obligatorio cargar nada; si NO es tarjeta
    (débito manual de una caja de ahorro, "CA Bco X", o "Pago manual"),
    Vencimiento e Importe son obligatorios JUNTOS al aceptar (`accept`,
    ver abajo) — o los dos cargados, o los dos en blanco."""

    def __init__(self, conn: sqlite3.Connection, instancia: sqlite3.Row, parent=None, *, incluir_estado: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Editar vencimiento, monto y estado" if incluir_estado else "Editar vencimiento y monto")
        self._es_tarjeta = es_medio_pago_tarjeta(instancia["MedioPago"])
        layout = QVBoxLayout(self)

        layout.addWidget(_titulo_campo("Vencimiento"))
        self.campo_vencimiento = _campo_vencimiento_sin_dia(conn)
        if instancia["Vencimiento"]:
            from PySide6.QtCore import QDate
            self.campo_vencimiento.setDate(QDate.fromString(instancia["Vencimiento"], "yyyy-MM-dd"))
        elif not self._es_tarjeta:
            # Pedido explícito de la clienta: precargada con la fecha de
            # hoy (en vez de quedar en "(sin fecha)") para que Flecha
            # arriba/abajo (`instalar_flechas_cambian_fecha_completa`,
            # ya instalado por `_campo_fecha`) la mueva de a un día real
            # cerca de hoy, no desde el mínimo sentinel.
            self.campo_vencimiento.setDate(fecha_actual(conn))
        self.campo_vencimiento.setEnabled(not self._es_tarjeta)
        layout.addWidget(self.campo_vencimiento)

        layout.addWidget(_titulo_campo("Importe"))
        self.spin_importe = _SpinImporteControlPagos()
        self.spin_importe.setRange(0, 100_000_000)
        self.spin_importe.setDecimals(2)
        self.spin_importe.setSpecialValueText("(sin cargar)")
        self.spin_importe.setValue(instancia["Importe"] or 0)
        layout.addWidget(self.spin_importe)

        layout.addWidget(_titulo_campo("Cuenta/Id (opcional)"))
        self.campo_cuenta_id = QLineEdit(instancia["CampoLibre1"] or "")
        layout.addWidget(self.campo_cuenta_id)

        self.combo_estado: QComboBox | None = None
        if incluir_estado:
            layout.addWidget(_titulo_campo("Estado"))
            self.combo_estado = QComboBox()
            for valor in ESTADOS_INSTANCIA:
                self.combo_estado.addItem(valor, valor)
            indice = self.combo_estado.findData(instancia["Estado"])
            if indice >= 0:
                self.combo_estado.setCurrentIndex(indice)
            layout.addWidget(self.combo_estado)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)
        # Pedido explícito de la clienta: después de Enter en Importe,
        # el foco pasa al botón OK (así se puede confirmar con la barra
        # espaciadora) en vez de volver al principio de la cadena.
        campos_foco = [self.campo_vencimiento, self.spin_importe, self.campo_cuenta_id]
        if self.combo_estado is not None:
            campos_foco.append(self.combo_estado)
        campos_foco.append(botones.button(QDialogButtonBox.StandardButton.Ok))
        self._foco = instalar_enter_avanza_foco(campos_foco, parent=self)

    def accept(self) -> None:  # noqa: N802
        if not self._es_tarjeta and (self.vencimiento() is None) != (self.importe() is None):
            QMessageBox.warning(
                self, "Editar",
                "Para este medio de pago, el vencimiento y el importe van juntos: "
                "cargá los dos o dejá los dos en blanco.",
            )
            return
        super().accept()

    def vencimiento(self) -> str | None:
        return (
            None if self.campo_vencimiento.date() == _FECHA_SIN_DATO
            else self.campo_vencimiento.date().toPython().isoformat()
        )

    def importe(self) -> float | None:
        return None if self.spin_importe.value() == 0 else self.spin_importe.value()

    def cuenta_id(self) -> str | None:
        return self.campo_cuenta_id.text().strip() or None

    def estado(self) -> str | None:
        return self.combo_estado.currentData() if self.combo_estado is not None else None


class _DialogoEditarConcepto(QDialog):
    """Editar los datos del concepto en sí (Nombre/Categoría/Afectación/
    Medio de pago sugerido) — pedido explícito de la clienta, para
    cuando algo del concepto cambia (ej. se vende una unidad, o se
    corrige un error de carga)."""

    def __init__(self, conn: sqlite3.Connection, concepto: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Editar concepto")
        layout = QVBoxLayout(self)

        layout.addWidget(_titulo_campo("Nombre"))
        self.campo_nombre = QLineEdit(concepto["Nombre"])
        layout.addWidget(self.campo_nombre)

        layout.addWidget(_titulo_campo("Categoría"))
        self.combo_categoria = QComboBox()
        self.combo_categoria.setEditable(True)
        for valor, etiqueta in opciones_lista("CategoriaControlPagos")(conn):
            self.combo_categoria.addItem(etiqueta, valor)
        if concepto["Categoria"]:
            self.combo_categoria.setCurrentText(concepto["Categoria"])
        layout.addWidget(self.combo_categoria)

        layout.addWidget(_titulo_campo("Afectación"))
        self.combo_tipo_afectacion = _armar_combo_tipo_afectacion()
        indice_tipo = self.combo_tipo_afectacion.findData(concepto["TipoAfectacion"])
        if indice_tipo >= 0:
            self.combo_tipo_afectacion.setCurrentIndex(indice_tipo)
        layout.addWidget(self.combo_tipo_afectacion)
        self.combo_detalle_afectacion = QComboBox()
        layout.addWidget(self.combo_detalle_afectacion)
        self.combo_tipo_afectacion.currentIndexChanged.connect(self._actualizar_detalle)
        self._actualizar_detalle()
        tipo = concepto["TipoAfectacion"]
        if tipo in _TIPOS_CON_DETALLE:
            id_actual = concepto[_CAMPO_DB_POR_TIPO[tipo]]
            indice_detalle = self.combo_detalle_afectacion.findData(id_actual)
            if indice_detalle >= 0:
                self.combo_detalle_afectacion.setCurrentIndex(indice_detalle)

        layout.addWidget(_titulo_campo("Medio de pago sugerido"))
        self.combo_medio_pago = QComboBox()
        self.combo_medio_pago.setEditable(True)
        for valor, etiqueta in opciones_lista("MedioPagoControlPagos")(conn):
            self.combo_medio_pago.addItem(etiqueta, valor)
        if concepto["MedioPagoSugerido"]:
            self.combo_medio_pago.setCurrentText(concepto["MedioPagoSugerido"])
        layout.addWidget(self.combo_medio_pago)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _actualizar_detalle(self) -> None:
        _actualizar_combo_detalle_afectacion(self.conn, self.combo_tipo_afectacion, self.combo_detalle_afectacion)

    def valores(self) -> dict:
        valores = {
            "Nombre": self.campo_nombre.text().strip(),
            "Categoria": self.combo_categoria.currentText().strip() or None,
            "MedioPagoSugerido": self.combo_medio_pago.currentText().strip() or None,
            "TipoAfectacion": self.combo_tipo_afectacion.currentData(),
        }
        for campo_db in _CAMPO_DB_POR_TIPO.values():
            valores[campo_db] = None
        tipo = self.combo_tipo_afectacion.currentData()
        if tipo in _TIPOS_CON_DETALLE:
            valores[_CAMPO_DB_POR_TIPO[tipo]] = self.combo_detalle_afectacion.currentData()
        return valores


class _PanelCargaControl(QWidget):
    _COL_NOMBRE, _COL_CATEGORIA, _COL_AFECTACION, _COL_CUENTA_ID = 0, 1, 2, 3
    _COL_MEDIO_PAGO, _COL_PERIODO, _COL_VENCIMIENTO, _COL_IMPORTE, _COL_ESTADO = 4, 5, 6, 7, 8
    _COL_EDITAR, _COL_ABONAR, _COL_ARCHIVAR, _COL_DESHACER = 9, 10, 11, 12

    # Sentinel para "sin filtro" en los 4 combos de la columna 4 — no
    # se usa `None`, que puede ser un valor real (ej. una Categoría sin
    # cargar), mismo criterio que `_PanelHistorialControlPagos._TODAS`.
    _TODOS = object()

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setObjectName("panelSolapa")
        self._registros: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        generar_instancias_periodo(self.conn, periodo_actual(self.conn))
        self.actualizar()
        self.campo_nombre.setFocus()

    @staticmethod
    def _nueva_columna() -> QWidget:
        """Una de las 4 columnas de igual ancho (pedido explícito de la
        clienta) — `objectName="panelSolapa"` (regla general de CLAUDE.
        md: todo contenedor intermedio dentro de la solapa activa tiene
        que quedar del mismo tono claro, nunca el gris default de Qt).
        El margen superior es el mismo mecanismo de "pixel 85" que el
        resto del sistema (ver `_ALTO_TITULO_CARGA_CONTROL`)."""
        columna = QWidget()
        columna.setObjectName("panelSolapa")
        layout = QVBoxLayout(columna)
        layout.setContentsMargins(9, _ALTO_TITULO_CARGA_CONTROL, 9, 0)
        return columna

    @staticmethod
    def _agregar(layout: QVBoxLayout, widget) -> None:
        """Alineado a la izquierda explícito — a diferencia del panel
        único de antes (apenas más ancho que los campos), estas 4
        columnas abarcan todo el ancho de la pantalla, y un campo de
        ancho fijo no tiene que quedar centrado en el espacio sobrante."""
        layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignLeft)

    def _armar_ui(self) -> None:
        # Pedido explícito de la clienta: rediseño completo en 4
        # columnas de igual ancho que abarcan todo el ancho de la
        # pantalla — la tabla va DEBAJO de esas 4 columnas (no al
        # costado, a diferencia del layout de un solo panel+tabla de
        # antes), así que el layout externo pasa a ser vertical.
        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)

        fila_columnas = QWidget()
        fila_columnas.setObjectName("panelSolapa")
        layout_columnas = QHBoxLayout(fila_columnas)
        layout_columnas.setContentsMargins(0, 0, 0, 0)

        columna1 = self._nueva_columna()
        columna2 = self._nueva_columna()
        columna3 = self._nueva_columna()
        columna4 = self._nueva_columna()
        for columna in (columna1, columna2, columna3, columna4):
            layout_columnas.addWidget(columna, stretch=1)
        col1, col2, col3, col4 = columna1.layout(), columna2.layout(), columna3.layout(), columna4.layout()

        # Columna 1: Nombre, Categoría, Afectación (sus dos combos) y
        # Medio de pago.
        self._agregar(col1, _titulo_campo("Nombre"))
        self.campo_nombre = QLineEdit()
        self.campo_nombre.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self._agregar(col1, self.campo_nombre)

        self._agregar(col1, _titulo_campo("Categoría"))
        self.combo_categoria = QComboBox()
        self.combo_categoria.setEditable(True)
        self.combo_categoria.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        for valor, etiqueta in opciones_lista("CategoriaControlPagos")(self.conn):
            self.combo_categoria.addItem(etiqueta, valor)
        self.combo_categoria.setCurrentIndex(-1)
        self._agregar(col1, self.combo_categoria)

        self._agregar(col1, _titulo_campo("Afectación"))
        self.combo_tipo_afectacion = _armar_combo_tipo_afectacion()
        self.combo_tipo_afectacion.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self._agregar(col1, self.combo_tipo_afectacion)
        self.combo_detalle_afectacion = QComboBox()
        self.combo_detalle_afectacion.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self._agregar(col1, self.combo_detalle_afectacion)
        self.combo_tipo_afectacion.currentIndexChanged.connect(self._actualizar_detalle_afectacion)
        self._actualizar_detalle_afectacion()

        # Pedido explícito de la clienta: referencia libre (número de
        # cuenta o de servicio), no obligatoria — reusa `CampoLibre1`
        # de `InstanciaControlPago` (ver `_cuenta_id_heredada`, que la
        # hereda sola en los períodos siguientes sin volver a tipearla).
        self._agregar(col1, _titulo_campo("Cuenta/Id (opcional)"))
        self.campo_cuenta_id = QLineEdit()
        self.campo_cuenta_id.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self._agregar(col1, self.campo_cuenta_id)

        self._agregar(col1, _titulo_campo("Medio de pago"))
        self.combo_medio_pago = QComboBox()
        self.combo_medio_pago.setEditable(True)
        self.combo_medio_pago.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        for valor, etiqueta in opciones_lista("MedioPagoControlPagos")(self.conn):
            self.combo_medio_pago.addItem(etiqueta, valor)
        self.combo_medio_pago.setCurrentIndex(-1)
        self._agregar(col1, self.combo_medio_pago)
        col1.addStretch(1)

        # Columna 2: Vencimiento, Importe y el botón principal "Crear
        # concepto".
        self._agregar(col2, _titulo_campo("Vencimiento (opcional)"))
        self.campo_vencimiento = _campo_vencimiento_sin_dia(self.conn)
        self.campo_vencimiento.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self._agregar(col2, self.campo_vencimiento)

        self._agregar(col2, _titulo_campo("Importe (opcional)"))
        self.spin_importe = _SpinImporteControlPagos()
        self.spin_importe.setRange(0, 100_000_000)
        self.spin_importe.setDecimals(2)
        self.spin_importe.setSpecialValueText("(sin cargar)")
        self.spin_importe.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self._agregar(col2, self.spin_importe)

        self.boton_crear = QPushButton("Crear concepto")
        self.boton_crear.setObjectName("botonPrimario")
        self.boton_crear.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_crear.clicked.connect(self._crear)
        self._agregar(col2, self.boton_crear)

        # Pedido explícito de la clienta: las siete etiquetas de conteo
        # van todas debajo de "Crear concepto", en esta misma columna 2
        # (antes las últimas tres vivían en la columna 3, debajo de
        # "Eliminar registro duplicado") — los mismos buckets de color
        # que ya usa `_color_fila`, sobre lo que está actualmente en
        # pantalla (post-filtro). Se actualizan en cada `actualizar()`.
        self.etiqueta_conteo_por_cargar = QLabel()
        self.etiqueta_conteo_vencimiento_hoy = QLabel()
        self.etiqueta_conteo_vencimiento_mañana = QLabel()
        self.etiqueta_conteo_vencimiento_en_dias = QLabel()
        self.etiqueta_conteo_vencido = QLabel()
        self.etiqueta_conteo_archivados = QLabel()
        self.etiqueta_conteo_total = QLabel()
        for etiqueta in (
            self.etiqueta_conteo_por_cargar, self.etiqueta_conteo_vencimiento_hoy,
            self.etiqueta_conteo_vencimiento_mañana, self.etiqueta_conteo_vencimiento_en_dias,
            self.etiqueta_conteo_vencido, self.etiqueta_conteo_archivados, self.etiqueta_conteo_total,
        ):
            self._agregar(col2, etiqueta)
        col2.addStretch(1)

        # Columna 3: los 4 botones secundarios sobre el CONCEPTO
        # seleccionado (no sobre un registro puntual — esos tres
        # vuelven a vivir al final de cada fila de la tabla, ver
        # `_armar_botones_fila`).
        self.boton_editar_concepto = QPushButton("Editar concepto seleccionado")
        self.boton_editar_concepto.setObjectName("botonSecundario")
        self.boton_editar_concepto.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_editar_concepto.clicked.connect(self._editar_concepto_seleccionado)
        self._agregar(col3, self.boton_editar_concepto)

        # Pedido explícito de la clienta: baja DEFINITIVA de un concepto
        # (distinta de "Archivar", que solo cierra el mes en curso).
        self.boton_dar_de_baja = QPushButton("Dar de baja concepto seleccionado")
        self.boton_dar_de_baja.setObjectName("botonSecundario")
        self.boton_dar_de_baja.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_dar_de_baja.clicked.connect(self._dar_de_baja_seleccionado)
        self._agregar(col3, self.boton_dar_de_baja)

        # Pedido explícito de la clienta: "por si ya tengo la información
        # para adelantar y anotar un importe o vencimiento" de un
        # concepto del período en curso — duplica (en blanco, solo con
        # Medio de pago) la instancia elegida al período próximo. Solo
        # habilitado sobre una fila del período ACTUAL (ver
        # `_actualizar_botones_seleccion`) — "solo se pueden duplicar
        # registros para el período próximo nada más".
        self.boton_duplicar_periodo_proximo = QPushButton("Duplicar para período próximo")
        self.boton_duplicar_periodo_proximo.setObjectName("botonSecundario")
        self.boton_duplicar_periodo_proximo.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_duplicar_periodo_proximo.clicked.connect(self._duplicar_para_periodo_proximo)
        self._agregar(col3, self.boton_duplicar_periodo_proximo)

        self.boton_eliminar_duplicado = QPushButton("Eliminar registro duplicado")
        self.boton_eliminar_duplicado.setObjectName("botonSecundario")
        self.boton_eliminar_duplicado.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_eliminar_duplicado.clicked.connect(self._eliminar_registro_duplicado)
        self._agregar(col3, self.boton_eliminar_duplicado)
        col3.addStretch(1)

        # Línea divisoria vertical entre la columna 3 y la columna 4 —
        # pedido explícito de la clienta, para separar visualmente los
        # botones de acción de los filtros.
        layout_columnas.insertWidget(3, _linea_divisoria_vertical())

        # Columna 4: los filtros, en cascada MUTUA (sin jerarquía entre
        # sí, a diferencia de Localidad->Edificio->Unidad) — las
        # opciones de cada combo se acotan según la selección vigente
        # de los otros tres (nunca la propia, ver
        # `_repoblar_filtros_cascada`). Buscador estilo selector de
        # profesional (`habilitar_busqueda_profesional`, genérico: no
        # depende de que el combo tenga datos de un profesional) — no
        # cambia de ancho al seleccionar ni al tipear, el combo ya
        # queda con `setFixedWidth` como el resto de los campos.
        #
        # Pedido explícito de la clienta: título "Filtros" (Nivel 2,
        # `subtituloSeccion`) arriba de todo, encima de "Nombre".
        self.titulo_filtros = QLabel("Filtros")
        self.titulo_filtros.setObjectName("subtituloSeccion")
        self._agregar(col4, self.titulo_filtros)

        self.combo_filtro_nombre = QComboBox()
        self.combo_filtro_categoria = QComboBox()
        self.combo_filtro_afectacion = QComboBox()
        self.combo_filtro_medio_pago = QComboBox()
        for etiqueta, combo in (
            ("Nombre", self.combo_filtro_nombre), ("Categoría", self.combo_filtro_categoria),
            ("Afectación", self.combo_filtro_afectacion), ("Medio de pago", self.combo_filtro_medio_pago),
        ):
            self._agregar(col4, _titulo_campo(etiqueta))
            combo.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
            habilitar_busqueda_profesional(combo)
            combo.currentIndexChanged.connect(self.actualizar)
            self._agregar(col4, combo)

        self.boton_reiniciar_filtros = QPushButton("Reiniciar filtros")
        self.boton_reiniciar_filtros.setObjectName("botonSecundario")
        self.boton_reiniciar_filtros.setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)
        self.boton_reiniciar_filtros.clicked.connect(self._reiniciar_filtros)
        self._agregar(col4, self.boton_reiniciar_filtros)
        col4.addStretch(1)

        layout_externo.addWidget(fila_columnas)

        # La tabla va abajo de las 4 columnas, a lo ancho de toda la
        # pantalla y escroleable (`QTableWidget` ya scrollea solo si
        # hace falta). Al final de cada fila, los tres botones que
        # vivían ahí antes de pasar (en la ronda anterior) a la
        # columna 1 — "Editar"/"Abonar"/"Archivar", mismas funciones.
        self.tabla = QTableWidget()
        excluir_tabla_del_tab(self.tabla)
        self.tabla.setColumnCount(13)
        self.tabla.setHorizontalHeaderLabels([
            "Nombre", "Categoría", "Afectación", "Cuenta/Id", "Medio de pago", "Período", "Vencimiento",
            "Importe", "Estado", "", "", "", "",
        ])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = self.tabla.horizontalHeader()
        for columna in (self._COL_NOMBRE, self._COL_AFECTACION):
            header.setSectionResizeMode(columna, QHeaderView.ResizeMode.Stretch)
        for columna in (self._COL_CATEGORIA, self._COL_MEDIO_PAGO, self._COL_PERIODO, self._COL_VENCIMIENTO, self._COL_ESTADO):
            header.setSectionResizeMode(columna, QHeaderView.ResizeMode.ResizeToContents)
        # "Cuenta/Id"/"Importe" quedan en ancho manual (`Interactive`,
        # fijado a mano en cada `actualizar()`, ver más abajo) — pedido
        # explícito de la clienta: "Cuenta/Id" al ancho de "Categoría",
        # "Importe" un 20% más ancho que su ancho natural, en los dos
        # casos sacándole el espacio a Nombre/Afectación (los únicos
        # dos en `Stretch`, que lo absorben solos).
        for columna in (self._COL_CUENTA_ID, self._COL_IMPORTE):
            header.setSectionResizeMode(columna, QHeaderView.ResizeMode.Interactive)
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones_seleccion)
        # Pedido explícito de la clienta: tabla ordenable por click en el
        # encabezado — mismo mecanismo que el resto del sistema
        # (`OrdenTabla`, ver `app/gui/widgets/orden_tabla.py`). El orden
        # por defecto (tres grupos, ver `_clave_orden_instancia`) se
        # sigue aplicando primero; un click en una columna se aplica
        # ENCIMA (sort estable), y un segundo click en la misma invierte
        # el sentido.
        self._orden = OrdenTabla(self.tabla, self.actualizar)
        layout_externo.addWidget(self.tabla, stretch=1)

        self._foco = instalar_enter_avanza_foco(
            [
                self.campo_nombre, self.combo_categoria, self.combo_tipo_afectacion, self.combo_detalle_afectacion,
                self.campo_cuenta_id, self.combo_medio_pago, self.campo_vencimiento, self.spin_importe,
                self.boton_crear,
            ],
            parent=self,
        )
        self._actualizar_botones_seleccion()

    def _actualizar_detalle_afectacion(self) -> None:
        _actualizar_combo_detalle_afectacion(self.conn, self.combo_tipo_afectacion, self.combo_detalle_afectacion)

    def _resetear_formulario(self) -> None:
        self.campo_nombre.clear()
        self.combo_categoria.setCurrentIndex(-1)
        self.combo_tipo_afectacion.setCurrentIndex(0)
        self.campo_cuenta_id.clear()
        self.combo_medio_pago.setCurrentIndex(-1)
        self.campo_vencimiento.setDate(_FECHA_SIN_DATO)
        self.spin_importe.setValue(0)

    def _crear(self) -> None:
        nombre = self.campo_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Crear concepto", "El nombre es obligatorio.")
            self.campo_nombre.setFocus()
            return
        kwargs = _kwargs_afectacion(self.combo_tipo_afectacion, self.combo_detalle_afectacion)
        id_concepto = crear_concepto(
            self.conn, nombre=nombre, categoria=self.combo_categoria.currentText().strip() or None,
            medio_pago_sugerido=self.combo_medio_pago.currentText().strip() or None, **kwargs,
        )
        generar_instancias_periodo(self.conn, periodo_actual(self.conn))
        instancias = obtener_repositorio(self.conn, "InstanciaControlPago").listar(
            IdConcepto=id_concepto, Periodo=periodo_actual(self.conn),
        )
        vencimiento = (
            None if self.campo_vencimiento.date() == _FECHA_SIN_DATO
            else self.campo_vencimiento.date().toPython().isoformat()
        )
        importe = None if self.spin_importe.value() == 0 else self.spin_importe.value()
        cuenta_id = self.campo_cuenta_id.text().strip() or None
        id_instancia_nueva = instancias[0]["IdInstancia"] if instancias else None
        if id_instancia_nueva is not None and (vencimiento is not None or importe is not None or cuenta_id is not None):
            actualizar_instancia(
                self.conn, id_instancia_nueva, vencimiento=vencimiento, importe=importe, cuenta_id=cuenta_id,
            )
        self._resetear_formulario()
        self.actualizar()
        if id_instancia_nueva is not None:
            self._seleccionar_instancia(id_instancia_nueva)
        self.campo_nombre.setFocus()
        QMessageBox.information(self, "Crear concepto", "Concepto creado con éxito.")

    def _seleccionar_instancia(self, id_instancia: int) -> None:
        """Pedido explícito de la clienta: después de cargar o editar un
        item, queda seleccionado en la tabla — `actualizar()` repuebla
        la tabla entera (`setRowCount(0)` + de nuevo), así que la
        selección anterior se pierde sola y hay que volver a aplicarla
        después, buscando la fila por `IdInstancia` (el orden puede
        cambiar de una `actualizar()` a la siguiente)."""
        for fila_idx, instancia in enumerate(self._registros):
            if instancia["IdInstancia"] == id_instancia:
                self.tabla.selectRow(fila_idx)
                return

    def _fila_seleccionada_instancia(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._registros[filas[0].row()]

    def _fila_seleccionada_concepto(self) -> sqlite3.Row | None:
        instancia = self._fila_seleccionada_instancia()
        if instancia is None:
            return None
        return obtener_repositorio(self.conn, "ConceptoControlPago").obtener(instancia["IdConcepto"])

    def _valor_filtro(self, fila: tuple, clave: str) -> str:
        instancia, concepto, afectacion = fila
        if clave == "nombre":
            return concepto["Nombre"] if concepto else "?"
        if clave == "categoria":
            return (concepto["Categoria"] if concepto else "") or ""
        if clave == "afectacion":
            return afectacion
        return instancia["MedioPago"] or ""

    def _combos_filtro(self) -> dict:
        return {
            "nombre": self.combo_filtro_nombre, "categoria": self.combo_filtro_categoria,
            "afectacion": self.combo_filtro_afectacion, "medio_pago": self.combo_filtro_medio_pago,
        }

    def _coincide_filtros(self, fila: tuple, *, excepto: str | None = None) -> bool:
        for clave, combo in self._combos_filtro().items():
            if clave == excepto:
                continue
            filtro = combo.currentData()
            if filtro is not None and filtro is not self._TODOS and self._valor_filtro(fila, clave) != filtro:
                return False
        return True

    def _repoblar_filtros_cascada(self, filas_totales: list) -> None:
        """Cascada MUTUA entre los cuatro filtros (Nombre/Categoría/
        Afectación/Medio de pago no tienen jerarquía entre sí, a
        diferencia de Localidad->Edificio->Unidad): las opciones de
        cada combo se acotan por la selección VIGENTE de los otros
        tres, nunca la propia — si acotara también por la propia,
        elegir un valor haría desaparecer las demás opciones de ESE
        mismo combo."""
        etiquetas_todos = {"nombre": "Todos", "categoria": "Todas", "afectacion": "Todas", "medio_pago": "Todos"}
        for clave, combo in self._combos_filtro().items():
            valores = sorted({
                self._valor_filtro(f, clave) for f in filas_totales if self._coincide_filtros(f, excepto=clave)
            })
            actual = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(etiquetas_todos[clave], self._TODOS)
            for valor in valores:
                combo.addItem(valor, valor)
            indice = combo.findData(actual) if actual is not None else 0
            combo.setCurrentIndex(indice if indice >= 0 else 0)
            combo.blockSignals(False)

    def _reiniciar_filtros(self) -> None:
        for combo in self._combos_filtro().values():
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.actualizar()

    def _actualizar_botones_seleccion(self) -> None:
        """Pedido explícito de la clienta: los botones de acción sobre
        el CONCEPTO seleccionado se habilitan solo cuando hay un
        registro seleccionado — Duplicar/Eliminar duplicado además con
        la condición de período que ya tenían como guarda manual."""
        instancia = self._fila_seleccionada_instancia()
        hay_seleccion = instancia is not None
        periodo = periodo_actual(self.conn)
        periodo_proximo = sumar_meses(periodo, 1)
        self.boton_editar_concepto.setEnabled(hay_seleccion)
        self.boton_dar_de_baja.setEnabled(hay_seleccion)
        self.boton_duplicar_periodo_proximo.setEnabled(hay_seleccion and instancia["Periodo"] == periodo)
        self.boton_eliminar_duplicado.setEnabled(hay_seleccion and instancia["Periodo"] == periodo_proximo)

    def _editar_concepto_seleccionado(self) -> None:
        concepto = self._fila_seleccionada_concepto()
        if concepto is None:
            return
        dialogo = _DialogoEditarConcepto(self.conn, concepto, parent=self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            editar_concepto(self.conn, concepto["IdConcepto"], **dialogo.valores())
            self.actualizar()
            QMessageBox.information(self, "Editar concepto", "Concepto actualizado con éxito.")

    def _clave_orden_instancia(self, fila: tuple) -> tuple:
        """Orden pedido explícitamente por la clienta: arriba las filas
        Pendientes sin vencimiento o sin importe cargados (ordenadas por
        Nombre y Afectación); luego las Pendientes con ambos datos
        cargados (por Período más próximo, Vencimiento, Nombre,
        Afectación); al final, en gris, las Abonadas/Archivadas —
        mismo criterio que Centro de mensajería (lo ya resuelto se hunde
        al fondo)."""
        instancia, concepto, afectacion = fila
        nombre = concepto["Nombre"] if concepto else ""
        if instancia["Estado"] in ("Abonado", "Archivado"):
            return (2, "", "", nombre, afectacion)
        if not instancia["Vencimiento"] or instancia["Importe"] is None:
            return (0, "", "", nombre, afectacion)
        return (1, instancia["Periodo"], instancia["Vencimiento"], nombre, afectacion)

    @staticmethod
    def _clave_orden_columna(columna: int):
        """Clave de orden para un click de encabezado — mismo criterio
        que `_PanelPagos._clave_orden` (`app/gui/pantallas/pagos.py`):
        un dict de lambdas, una por columna, sobre la misma tupla
        (instancia, concepto, afectación) que ya arma `actualizar`."""
        claves = {
            0: lambda f: f[1]["Nombre"] if f[1] else "",
            1: lambda f: (f[1]["Categoria"] if f[1] else "") or "",
            2: lambda f: f[2],
            3: lambda f: f[0]["CampoLibre1"] or "",
            4: lambda f: f[0]["MedioPago"] or "",
            5: lambda f: f[0]["Periodo"],
            6: lambda f: f[0]["Vencimiento"] or "",
            7: lambda f: f[0]["Importe"] or 0,
            8: lambda f: f[0]["Estado"],
        }
        return claves[columna]

    def _color_fila(self, instancia: sqlite3.Row, hoy: date) -> str | None:
        """Color de fondo pedido explícitamente por la clienta: gris
        para lo Abonado/Archivado (sin importar el vencimiento); si
        está Pendiente, según cuánto falta para el vencimiento (o
        blanco si no tiene vencimiento cargado)."""
        if instancia["Estado"] in ("Abonado", "Archivado"):
            return "gris"
        vencimiento = instancia["Vencimiento"]
        if not vencimiento:
            return None
        dias = (date.fromisoformat(vencimiento) - hoy).days
        if dias < 0:
            return "violeta"
        if dias == 0:
            return "rojo"
        if dias == 1:
            return "amarillo"
        return "verde"

    def actualizar(self) -> None:
        periodo = periodo_actual(self.conn)
        periodo_proximo = sumar_meses(periodo, 1)
        repo_instancia = obtener_repositorio(self.conn, "InstanciaControlPago")
        # Pedido explícito de la clienta: lo Pendiente de un período
        # viejo que nunca se tocó queda en pantalla indefinidamente (ya
        # no se archiva solo al avanzar de mes, ver `avance_mes.py`) —
        # además de las instancias del período actual/próximo (en
        # cualquier Estado, para seguir viendo lo Abonado/Archivado
        # reciente y los duplicados ya cargados del próximo).
        instancias = [
            i for i in repo_instancia.listar()
            if i["Estado"] == "Pendiente" or i["Periodo"] in (periodo, periodo_proximo)
        ]
        conceptos = {c["IdConcepto"]: c for c in obtener_repositorio(self.conn, "ConceptoControlPago").listar()}
        filas_totales = [
            (i, conceptos.get(i["IdConcepto"]), texto_afectacion(self.conn, conceptos[i["IdConcepto"]]) if i["IdConcepto"] in conceptos else "?")
            for i in instancias
        ]
        self._repoblar_filtros_cascada(filas_totales)
        filas = [f for f in filas_totales if self._coincide_filtros(f)]
        filas.sort(key=self._clave_orden_instancia)
        if self._orden.columna is not None:
            filas.sort(key=self._clave_orden_columna(self._orden.columna), reverse=not self._orden.ascendente)
        self._registros = [f[0] for f in filas]

        hoy = fecha_actual(self.conn)
        # `setRowCount(0)` antes de volver a crecer: como la cantidad
        # de filas y su orden cambian de una `actualizar()` a la
        # siguiente (alta de un concepto, click de encabezado, cambio
        # de filtro), reusar directamente `setRowCount(len(filas))`
        # podía dejar huérfano algún botón de una fila vieja en la
        # posición equivocada (`setCellWidget` reemplazando un botón
        # por otro en una fila que ya tenía uno de ANTES no lo
        # reposiciona limpio) — vaciar la tabla entera primero fuerza a
        # Qt a soltar todos los cell widgets viejos antes de crear los
        # nuevos.
        self.tabla.setRowCount(0)
        self.tabla.setRowCount(len(filas))
        colores_fila: list[str | None] = []
        for fila_idx, (instancia, concepto, afectacion) in enumerate(filas):
            self.tabla.setItem(fila_idx, self._COL_NOMBRE, QTableWidgetItem(concepto["Nombre"] if concepto else "?"))
            self.tabla.setItem(
                fila_idx, self._COL_CATEGORIA, QTableWidgetItem((concepto["Categoria"] if concepto else "") or ""),
            )
            self.tabla.setItem(fila_idx, self._COL_AFECTACION, QTableWidgetItem(afectacion))
            self.tabla.setItem(fila_idx, self._COL_CUENTA_ID, QTableWidgetItem(instancia["CampoLibre1"] or ""))
            self.tabla.setItem(
                fila_idx, self._COL_MEDIO_PAGO, QTableWidgetItem(instancia["MedioPago"] or ""),
            )
            self.tabla.setItem(fila_idx, self._COL_PERIODO, item_centrado(instancia["Periodo"]))
            texto_vencimiento = _fecha_dd_mm_yyyy(instancia["Vencimiento"]) if instancia["Vencimiento"] else ""
            self.tabla.setItem(fila_idx, self._COL_VENCIMIENTO, item_centrado(texto_vencimiento))
            self.tabla.setItem(fila_idx, self._COL_IMPORTE, _item_importe(instancia["Importe"]))
            self.tabla.setItem(fila_idx, self._COL_ESTADO, item_centrado(instancia["Estado"]))
            self._armar_botones_fila(fila_idx, instancia)

            color = self._color_fila(instancia, hoy)
            colores_fila.append(color)
            if color is not None:
                fondo = QColor(_COLOR_FONDO_VENCIMIENTO[color])
                letra = QColor("#000000" if color in _COLORES_CON_LETRA_NEGRA else COLOR_TEXTO_CLARO)
                for columna in (
                    self._COL_NOMBRE, self._COL_CATEGORIA, self._COL_AFECTACION, self._COL_CUENTA_ID,
                    self._COL_MEDIO_PAGO, self._COL_PERIODO, self._COL_VENCIMIENTO, self._COL_IMPORTE,
                    self._COL_ESTADO,
                ):
                    celda = self.tabla.item(fila_idx, columna)
                    celda.setBackground(fondo)
                    celda.setForeground(letra)
        # Las columnas de botones no entran en el Stretch/ResizeToContents
        # de arriba — necesitan su ancho real para no cortar el texto.
        for columna in (self._COL_EDITAR, self._COL_ABONAR, self._COL_ARCHIVAR, self._COL_DESHACER):
            self.tabla.resizeColumnToContents(columna)
        # "Cuenta/Id" al ancho de "Categoría" menos un 25%; "Importe" un
        # 20% más ancho que su ancho natural, menos un 20% — pedido
        # explícito de la clienta (una ronda sobre la otra: antes era
        # "Cuenta/Id" = "Categoría" e "Importe" = natural*1.2, ver
        # CLAUDE.md). El ancho que se libera lo absorben solas Nombre/
        # Afectación (`Stretch`, sin cálculo manual — ver `_armar_ui`).
        self.tabla.setColumnWidth(self._COL_CUENTA_ID, round(self.tabla.columnWidth(self._COL_CATEGORIA) * 0.75))
        self.tabla.resizeColumnToContents(self._COL_IMPORTE)
        ancho_importe = round(self.tabla.columnWidth(self._COL_IMPORTE) * 1.2)
        self.tabla.setColumnWidth(self._COL_IMPORTE, round(ancho_importe * 0.8))
        self._actualizar_botones_seleccion()
        self._actualizar_etiquetas_conteo(colores_fila, filas)

    def _actualizar_etiquetas_conteo(self, colores_fila: list, filas: list) -> None:
        """Siete etiquetas pedidas explícitamente por la clienta, sobre
        lo que está actualmente en pantalla (post-filtro) — mismos
        buckets de color que ya usa `_color_fila`."""
        por_cargar = sum(
            1 for (instancia, _c, _a) in filas
            if instancia["Estado"] == "Pendiente" and (not instancia["Vencimiento"] or instancia["Importe"] is None)
        )
        archivados = sum(1 for (instancia, _c, _a) in filas if instancia["Estado"] == "Archivado")
        self.etiqueta_conteo_por_cargar.setText(f"Conceptos por cargar: {por_cargar}")
        self.etiqueta_conteo_vencimiento_hoy.setText(f"Con vencimiento hoy: {colores_fila.count('rojo')}")
        self.etiqueta_conteo_vencimiento_mañana.setText(f"Con vencimiento mañana: {colores_fila.count('amarillo')}")
        self.etiqueta_conteo_vencimiento_en_dias.setText(f"Con vencimiento en días: {colores_fila.count('verde')}")
        self.etiqueta_conteo_vencido.setText(f"Con vencimiento vencido: {colores_fila.count('violeta')}")
        self.etiqueta_conteo_archivados.setText(f"Conceptos archivados: {archivados}")
        self.etiqueta_conteo_total.setText(f"Total conceptos: {len(filas)}")

    def _armar_botones_fila(self, fila_idx: int, instancia: sqlite3.Row) -> None:
        # Un botón NUEVO por fila en cada `actualizar()` — no se reusa
        # por posición (fila_idx, columna) como se probó primero.
        # `_clave_orden_instancia`/un click de encabezado puede mover
        # qué instancia cae en cada posición entre una llamada y la
        # siguiente, y reconectar un botón viejo con `.clicked.
        # disconnect()` + `.connect(...)` sobre esa posición reciclada
        # corrompía el estado de Qt/shiboken de forma silenciosa — los
        # tests pasaban igual, pero el proceso terminaba con un abort
        # ("bool_dealloc", refcount corrupto) recién al cerrar. Crear un
        # botón nuevo siempre es exactamente lo mismo que ya se hace
        # con el resto de las celdas de la fila (`QTableWidgetItem`
        # nuevo en cada `actualizar()`), así que queda consistente.
        def _boton(columna: int, texto: str, callback) -> QPushButton:
            boton = QPushButton(texto)
            boton.setObjectName("botonSecundario")
            boton.clicked.connect(callback)
            self.tabla.setCellWidget(fila_idx, columna, boton)
            return boton

        _boton(self._COL_EDITAR, "Editar", lambda _c=False, i=instancia: self._editar_instancia(i))
        boton_abonar = _boton(self._COL_ABONAR, "Abonar", lambda _c=False, i=instancia: self._marcar_abonada(i))
        boton_abonar.setEnabled(instancia["Estado"] == "Pendiente")
        boton_archivar = _boton(self._COL_ARCHIVAR, "Archivar", lambda _c=False, i=instancia: self._archivar(i))
        boton_archivar.setEnabled(
            instancia["Estado"] == "Pendiente" and not instancia["Vencimiento"] and instancia["Importe"] is None
        )
        # Pedido explícito de la clienta: botón chico de "deshacer"
        # (flecha típica de deshacer acción), habilitado solo cuando hay
        # algo cargado (vencimiento o importe) — lo vacía todo y deja
        # la instancia Pendiente otra vez, disponible para elegir
        # cualquier acción sobre ella.
        boton_deshacer = _boton(self._COL_DESHACER, "↩", lambda _c=False, i=instancia: self._deshacer(i))
        boton_deshacer.setEnabled(bool(instancia["Vencimiento"]) or instancia["Importe"] is not None)

    def _editar_instancia(self, instancia: sqlite3.Row) -> None:
        dialogo = _DialogoEditarInstancia(self.conn, instancia, parent=self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            importe = dialogo.importe()
            kwargs = {}
            if es_medio_pago_tarjeta(instancia["MedioPago"]) and importe is not None:
                # Pedido explícito de la clienta: una tarjeta no se
                # controla por vencimiento — al cargarle un importe
                # queda abonada directamente, sin pasar por "Abonar".
                kwargs["estado"] = "Abonado"
            elif instancia["Estado"] == "Archivado":
                # Pedido explícito de la clienta: editar un registro
                # archivado lo vuelve a dejar disponible para elegir
                # qué hacer con él (Abonar/Archivar de nuevo).
                kwargs["estado"] = "Pendiente"
            actualizar_instancia(
                self.conn, instancia["IdInstancia"], vencimiento=dialogo.vencimiento(), importe=importe,
                cuenta_id=dialogo.cuenta_id(), **kwargs,
            )
            self.actualizar()
            self._seleccionar_instancia(instancia["IdInstancia"])
            QMessageBox.information(self, "Editar", "Registro actualizado con éxito.")

    def _marcar_abonada(self, instancia: sqlite3.Row) -> None:
        marcar_abonada(self.conn, instancia["IdInstancia"])
        self.actualizar()
        self._seleccionar_instancia(instancia["IdInstancia"])
        QMessageBox.information(self, "Abonar", "Registro marcado como abonado con éxito.")

    def _archivar(self, instancia: sqlite3.Row) -> None:
        try:
            archivar_instancia(self.conn, instancia["IdInstancia"])
        except ValueError as error:
            QMessageBox.warning(self, "Archivar", str(error))
            return
        self.actualizar()
        self._seleccionar_instancia(instancia["IdInstancia"])
        QMessageBox.information(self, "Archivar", "Registro archivado con éxito.")

    def _deshacer(self, instancia: sqlite3.Row) -> None:
        actualizar_instancia(
            self.conn, instancia["IdInstancia"], vencimiento=None, importe=None, estado="Pendiente",
        )
        self.actualizar()
        self._seleccionar_instancia(instancia["IdInstancia"])
        QMessageBox.information(self, "Deshacer", "Registro vuelto a dejar sin vencimiento ni importe.")

    def _duplicar_para_periodo_proximo(self) -> None:
        instancia = self._fila_seleccionada_instancia()
        if instancia is None:
            return
        try:
            id_nuevo = duplicar_para_periodo_proximo(self.conn, instancia["IdInstancia"])
        except ValueError as error:
            QMessageBox.warning(self, "Duplicar para período próximo", str(error))
            return
        self.actualizar()
        self._seleccionar_instancia(id_nuevo)
        QMessageBox.information(
            self, "Duplicar para período próximo", "Registro duplicado con éxito para el período próximo.",
        )

    def _eliminar_registro_duplicado(self) -> None:
        instancia = self._fila_seleccionada_instancia()
        if instancia is None:
            return
        respuesta = QMessageBox.question(
            self, "Eliminar registro duplicado", "¿Eliminar este registro duplicado del período próximo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        eliminar_instancia_duplicada(self.conn, instancia["IdInstancia"])
        self.actualizar()
        QMessageBox.information(self, "Eliminar registro duplicado", "Registro duplicado eliminado con éxito.")

    def _dar_de_baja_seleccionado(self) -> None:
        concepto = self._fila_seleccionada_concepto()
        if concepto is None:
            return
        respuesta = QMessageBox.question(
            self, "Dar de baja concepto",
            f"¿Dar de baja «{concepto['Nombre']}» para siempre? No se va a volver a generar en los próximos "
            "períodos. El historial ya generado no se toca.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        dar_de_baja_concepto(self.conn, concepto["IdConcepto"])
        self.actualizar()
        QMessageBox.information(self, "Dar de baja concepto", "Concepto dado de baja con éxito.")

    def reiniciar(self) -> None:
        """F5: "reinicia la solapa... como recién se entrara en ella" —
        a diferencia de `showEvent` (que no toca un formulario a medio
        completar), acá sí se resetea todo, formulario incluido (ver
        CLAUDE.md, "F5... reinicia desde cero, distinto de showEvent")."""
        self._resetear_formulario()
        self.tabla.clearSelection()
        self._orden.reiniciar()
        self._reiniciar_filtros()
        self.campo_nombre.setFocus()

class _PanelHistorialControlPagos(QWidget):
    _TODAS = object()

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setObjectName("panelSolapa")
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.actualizar()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        panel_filtros = QWidget()
        panel_filtros.setObjectName("panelSolapa")
        panel_filtros.setMinimumWidth(_ANCHO_PANEL_IZQUIERDA)
        panel_filtros.setMaximumWidth(_ANCHO_PANEL_IZQUIERDA)
        filtros = QVBoxLayout(panel_filtros)

        self.combo_categoria = QComboBox()
        self.combo_concepto = QComboBox()
        self.combo_afectacion = QComboBox()
        self.combo_medio_pago = QComboBox()
        for etiqueta, combo in (
            ("Categoría", self.combo_categoria), ("Concepto", self.combo_concepto),
            ("Afectación", self.combo_afectacion), ("Medio de pago", self.combo_medio_pago),
        ):
            filtros.addWidget(_titulo_campo(etiqueta))
            combo.setFixedWidth(_ANCHO_CAMPO)
            combo.currentIndexChanged.connect(self.actualizar)
            filtros.addWidget(combo)

        # Pedido explícito de la clienta: desde acá se puede reabrir un
        # registro que el cierre de mes archivó de más ("Al avanzar de
        # mes... lo que no esté marcado como abonado se archiva y luego
        # desde la solapa 'Historial' se puede marcar como abonado") —
        # el diálogo edita vencimiento, importe Y estado juntos.
        self.boton_editar_registro = QPushButton("Editar registro")
        self.boton_editar_registro.setObjectName("botonSecundario")
        self.boton_editar_registro.setFixedWidth(_ANCHO_CAMPO)
        self.boton_editar_registro.setEnabled(False)
        self.boton_editar_registro.clicked.connect(self._editar_registro)
        filtros.addWidget(self.boton_editar_registro)

        filtros.addStretch(1)
        layout_externo.addWidget(panel_filtros)

        self.tabla = QTableWidget()
        excluir_tabla_del_tab(self.tabla)
        self.tabla.setColumnCount(8)
        self.tabla.setHorizontalHeaderLabels([
            "Período", "Nombre", "Categoría", "Afectación", "Medio de pago", "Vencimiento", "Importe", "Estado",
        ])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = self.tabla.horizontalHeader()
        # Pedido explícito de la clienta: "Nombre"/"Afectación" son las
        # únicas dos columnas que absorben el ancho liberado al achicar
        # "Período"/"Vencimiento"/"Importe" (ver `actualizar`) —
        # "Categoría"/"Medio de pago" salen de `Stretch` y pasan a
        # `ResizeToContents` (no compiten por ese ancho liberado).
        for columna in (1, 3):
            header.setSectionResizeMode(columna, QHeaderView.ResizeMode.Stretch)
        for columna in (2, 4):
            header.setSectionResizeMode(columna, QHeaderView.ResizeMode.ResizeToContents)
        # "Período"/"Vencimiento"/"Importe" quedan en ancho manual
        # (`Interactive`, fijado a mano en cada `actualizar()`).
        for columna in (0, 5, 6):
            header.setSectionResizeMode(columna, QHeaderView.ResizeMode.Interactive)
        self.tabla.itemSelectionChanged.connect(self._actualizar_boton_editar_registro)
        # Pedido explícito de la clienta: tabla ordenable por click en el
        # encabezado — mismo mecanismo que "Carga y control"/"Registrar
        # pagos" (`OrdenTabla`).
        self._orden = OrdenTabla(self.tabla, self.actualizar)
        layout_externo.addWidget(self.tabla, stretch=1)
        self._filas: list[tuple] = []

    def _repoblar_filtros(self) -> None:
        conceptos = obtener_repositorio(self.conn, "ConceptoControlPago").listar()
        categorias = sorted({c["Categoria"] for c in conceptos if c["Categoria"]})
        nombres = sorted({c["Nombre"] for c in conceptos})
        afectaciones = sorted({texto_afectacion(self.conn, c) for c in conceptos})
        medios = sorted({
            i["MedioPago"] for i in obtener_repositorio(self.conn, "InstanciaControlPago").listar() if i["MedioPago"]
        })
        for combo, valores in (
            (self.combo_categoria, categorias), (self.combo_concepto, nombres),
            (self.combo_afectacion, afectaciones), (self.combo_medio_pago, medios),
        ):
            actual = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Todas" if combo is self.combo_categoria else "Todos", self._TODAS)
            for valor in valores:
                combo.addItem(valor, valor)
            indice = combo.findData(actual) if actual is not None else 0
            combo.setCurrentIndex(indice if indice >= 0 else 0)
            combo.blockSignals(False)

    def actualizar(self) -> None:
        self._repoblar_filtros()
        conceptos = {c["IdConcepto"]: c for c in obtener_repositorio(self.conn, "ConceptoControlPago").listar()}
        instancias = obtener_repositorio(self.conn, "InstanciaControlPago").listar()

        filtro_categoria = self.combo_categoria.currentData()
        filtro_concepto = self.combo_concepto.currentData()
        filtro_afectacion = self.combo_afectacion.currentData()
        filtro_medio = self.combo_medio_pago.currentData()

        filas = []
        for i in instancias:
            concepto = conceptos.get(i["IdConcepto"])
            if concepto is None:
                continue
            if filtro_categoria is not self._TODAS and concepto["Categoria"] != filtro_categoria:
                continue
            if filtro_concepto is not self._TODAS and concepto["Nombre"] != filtro_concepto:
                continue
            afectacion = texto_afectacion(self.conn, concepto)
            if filtro_afectacion is not self._TODAS and afectacion != filtro_afectacion:
                continue
            if filtro_medio is not self._TODAS and i["MedioPago"] != filtro_medio:
                continue
            filas.append((i, concepto, afectacion))
        filas.sort(key=lambda t: (t[0]["Periodo"], t[1]["Nombre"]), reverse=True)
        if self._orden.columna is not None:
            filas.sort(key=self._clave_orden_columna(self._orden.columna), reverse=not self._orden.ascendente)
        self._filas = filas

        self.tabla.setRowCount(len(filas))
        for fila_idx, (instancia, concepto, afectacion) in enumerate(filas):
            self.tabla.setItem(fila_idx, 0, item_numero(instancia["Periodo"]))
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(concepto["Nombre"]))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(concepto["Categoria"] or ""))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(afectacion))
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(instancia["MedioPago"] or ""))
            texto_vencimiento = _fecha_dd_mm_yyyy(instancia["Vencimiento"]) if instancia["Vencimiento"] else ""
            self.tabla.setItem(fila_idx, 5, item_centrado(texto_vencimiento))
            self.tabla.setItem(fila_idx, 6, _item_importe(instancia["Importe"]))
            self.tabla.setItem(fila_idx, 7, item_centrado(instancia["Estado"]))
        # Pedido explícito de la clienta: "Período"/"Vencimiento" al
        # ancho mínimo que entra el título sin cortar (mismo criterio
        # que `imagenes._ajustar_columnas`: `QFontMetrics` sobre la
        # fuente real del encabezado + un colchón chico para el padding
        # interno que Qt le suma a la celda); "Importe" ancho para que
        # entre "$ 0.000.000,00" (mismo criterio que `pagos._TEXTO_
        # MONTO_MAXIMO`). El ancho que esto libera lo absorben solas
        # "Nombre"/"Afectación" (`Stretch`, ver `_armar_ui`).
        metrica_encabezado = QFontMetrics(self.tabla.horizontalHeader().font())
        for columna in (0, 5):
            titulo = self.tabla.horizontalHeaderItem(columna).text()
            ancho = metrica_encabezado.horizontalAdvance(titulo) + _COLCHON_TITULO_COLUMNA
            self.tabla.setColumnWidth(columna, ancho)
        ancho_importe = QFontMetrics(self.tabla.font()).horizontalAdvance(_TEXTO_IMPORTE_MAXIMO)
        self.tabla.setColumnWidth(6, ancho_importe + _PADDING_COLUMNA_IMPORTE)
        self._actualizar_boton_editar_registro()

    @staticmethod
    def _clave_orden_columna(columna: int):
        """Clave de orden para un click de encabezado — mismo criterio
        que `_PanelCargaControl._clave_orden_columna`/`_PanelPagos.
        _clave_orden`: un dict de lambdas, una por columna, sobre la
        misma tupla (instancia, concepto, afectación) que ya arma
        `actualizar`."""
        claves = {
            0: lambda f: f[0]["Periodo"],
            1: lambda f: f[1]["Nombre"],
            2: lambda f: f[1]["Categoria"] or "",
            3: lambda f: f[2],
            4: lambda f: f[0]["MedioPago"] or "",
            5: lambda f: f[0]["Vencimiento"] or "",
            6: lambda f: f[0]["Importe"] or 0,
            7: lambda f: f[0]["Estado"],
        }
        return claves[columna]

    def _fila_seleccionada_instancia(self) -> sqlite3.Row | None:
        filas_sel = self.tabla.selectionModel().selectedRows()
        if not filas_sel:
            return None
        return self._filas[filas_sel[0].row()][0]

    def _actualizar_boton_editar_registro(self) -> None:
        self.boton_editar_registro.setEnabled(self._fila_seleccionada_instancia() is not None)

    def _editar_registro(self) -> None:
        instancia = self._fila_seleccionada_instancia()
        if instancia is None:
            return
        # Pedido explícito de la clienta: "Editar registro" de
        # "Historial" es solo para reabrir un registro VIEJO (de un
        # período anterior al actual) que el cierre de mes archivó de
        # más — uno del período actual o de un período posterior
        # (próximo, duplicado por adelantado) se sigue editando desde
        # "Carga y control" (ahí está la lógica de tarjeta, vencimiento+
        # importe juntos, duplicar/eliminar duplicado, etc. que este
        # diálogo no replica).
        if instancia["Periodo"] >= periodo_actual(self.conn):
            QMessageBox.warning(
                self, "Editar registro",
                "Este registro es del período actual o de uno posterior — esos se editan desde la "
                "solapa \"Carga y control\", no desde \"Historial\". Ahí es donde vive el resto de la "
                "lógica de ese período (medio de pago tarjeta, vencimiento e importe juntos, "
                "duplicar/eliminar duplicado para el período próximo), que \"Editar registro\" de "
                "\"Historial\" no replica.",
            )
            return
        dialogo = _DialogoEditarInstancia(self.conn, instancia, parent=self, incluir_estado=True)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            actualizar_instancia(
                self.conn, instancia["IdInstancia"], vencimiento=dialogo.vencimiento(), importe=dialogo.importe(),
                estado=dialogo.estado(), cuenta_id=dialogo.cuenta_id(),
            )
            self.actualizar()
            QMessageBox.information(self, "Editar registro", "Registro actualizado con éxito.")

    def reiniciar(self) -> None:
        """F5: vuelve todo a su estado inicial (filtros, orden y
        selección) — mismo criterio que `_PanelCargaControl.reiniciar`
        (CLAUDE.md, "F5... reinicia desde cero, distinto de showEvent")."""
        self.tabla.clearSelection()
        self._orden.reiniciar()
        for combo in (self.combo_categoria, self.combo_concepto, self.combo_afectacion, self.combo_medio_pago):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.actualizar()


class PantallaControlPagos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Control de pagos".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_carga_control = _PanelCargaControl(conn)
        self.panel_historial = _PanelHistorialControlPagos(conn)
        self.panel_inmuebles_personales = catalogos.pantalla_inmuebles_personales(conn, anidado=True)
        self.panel_rodados = catalogos.pantalla_rodados(conn, anidado=True)
        self.panel_personas = catalogos.pantalla_personas_familia(conn, anidado=True)
        self.pestanas.addTab(self.panel_carga_control, "Carga y control")
        self.pestanas.addTab(self.panel_historial, "Historial")
        self.pestanas.addTab(self.panel_inmuebles_personales, "Inmuebles personales")
        self.pestanas.addTab(self.panel_rodados, "Rodados")
        self.pestanas.addTab(self.panel_personas, "Personas")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
