"""Configuración general (F01, sección 3.28): única fila de la tabla
Configuracion — pantalla de formulario simple en vez del CRUD genérico de
lista, porque no tiene sentido crear/eliminar filas de esta tabla.

Revisión "uno por uno" (ver CLAUDE.md): pasó de un `QFormLayout` plano
con los 30 campos seguidos, uno abajo del otro, a formato solapa con 5
pestañas temáticas (agrupamiento a criterio propio, aprobado por la
clienta — "cualquier cosa se reevalúa más adelante"). El botón "Guardar"
queda FUERA del `QTabWidget`, compartido por las cinco solapas (guarda
todos los campos juntos, no solo los de la pestaña visible — sigue
siendo una única fila de configuración).

Segunda vuelta sobre esta misma pantalla: los campos numéricos pasaron
de `QLineEdit` con parseo manual a `float` a `QSpinBox`/`QDoubleSpinBox`
(no hay forma de dejarlos en un estado inválido); "Fecha ficticia" pasó
al mismo selector de calendario que el resto del sistema
("Selectores y fecha"); "Ruta del logo"/"Carpeta base de archivos"/
"Carpeta de backup" suman un botón "Elegir" que abre el selector nativo
de archivo/carpeta en vez de tipear la ruta a mano.

Reordenamiento de formularios (Excel de la clienta): se suma una solapa
más, "Bloques rígidos" (`_PanelBloquesRigidos`, importado desde
`bloques_rigidos.py` — antes una pantalla propia del menú), insertada
entre "Grilla y ocupación" y "Valores y liquidación". A diferencia de
las demás solapas (todas `_PanelCampos` sobre campos simples de
`Configuracion`), esta es un catálogo completo con su propia cadena de
foco Enter/Tab (Buscar → Nuevo → Editar → Eliminar) que no tiene nada
que ver con el botón "Guardar" compartido — `_actualizar_cadena_foco`
salta esa solapa (un `None` en `self._paneles` en esa posición marca
"esta solapa arma la suya propia", mismo criterio que Gastos operativos
con `instalar_foco=False`)."""
from __future__ import annotations

import json
import sqlite3

from PySide6.QtCore import QDate, QLocale
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.pantallas.bloques_rigidos import _PanelBloquesRigidos
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.negocio.formato import formatear_moneda
from app.negocio.seguridad import cambiar_contrasena_maestra, hay_contrasena_maestra
from app.repositorio.registro import obtener_repositorio

FORMATO_JSON = "JSON válido"
_FORMATO_FECHA_DIA = "ddd dd-MM-yyyy"  # mismo criterio que crud_generico.py (tipo="fecha")


def _es_json_valido(texto: str) -> bool:
    try:
        json.loads(texto)
        return True
    except json.JSONDecodeError:
        return False


# (nombre, validador, descripción del formato esperado para el cartel de aviso)
_VALIDADORES_TEXTO: dict[str, tuple[callable, str]] = {
    "DiasGrilla": (_es_json_valido, FORMATO_JSON),
    "MesesPeriodoActualizacion": (_es_json_valido, FORMATO_JSON),
    "RangosEstadisticasOcupacion": (_es_json_valido, FORMATO_JSON),
}

_CAMPOS_TEXTO = [
    ("NombreEspacio", "Nombre del espacio"),
    ("DiasGrilla", "Días de grilla (JSON)"),
    ("FrecuenciaActualizacionValores", "Frecuencia de actualización de valores"),
    ("MesesPeriodoActualizacion", "Meses del período de actualización (JSON)"),
    ("RangosEstadisticasOcupacion", "Rangos de estadísticas de ocupación (JSON)"),
    ("FrecuenciaBackupDrive", "Frecuencia de backup a Drive"),
    ("RutaLogo", "Ruta del archivo de logo (PNG/JPG)"),
    ("CarpetaBaseArchivos", "Carpeta base de archivos generados"),
    ("CarpetaBackup", "Carpeta de backup (sincronizada con Google Drive)"),
]
_CAMPOS_NUMERICOS = [
    ("HoraInicioGrilla", "Hora inicio de grilla"),
    ("HoraFinGrilla", "Hora fin de grilla"),
    ("FraccionGrilla", "Fracción de grilla (minutos)"),
    ("UmbralGiroGrilla", "Umbral de giro de grilla"),
    ("RecargoPorcentajeAisladas", "Recargo % reservas aisladas"),
    ("PorcentajeAjusteSaldoAtrasado", "% ajuste saldo atrasado"),
    ("ToleranciaDeudaDescuento", "Tolerancia deuda para descuento"),
    ("PorcentajeDescuentoFeriado", "% descuento por feriado nacional"),
    ("PorcentajeDescuentoNoLaborable", "% descuento por día no laborable"),
    ("SemanasVacacionesMaximasPorAnio", "Semanas de vacaciones máximas por año"),
    ("DiasEnvioLiquidacionesRemanentes", "Días de margen para envío de liquidaciones"),
    ("RetencionHistorialListaEsperaAnios", "Retención historial lista de espera (años)"),
    ("TamanoMaximoImagenMB", "Tamaño máximo de imagen (MB)"),
    ("CantidadDecimales", "Cantidad de decimales en los montos"),
    ("MinutosInactividadBloqueo", "Minutos de inactividad para bloqueo automático"),
]
_CAMPOS_BOOLEANOS = [
    ("RecargoAisladasActivoPorDefecto", "Recargo de aisladas activo por defecto"),
    ("ModulosExtendidos", "Módulos extendidos"),
    ("ModoFechaFicticia", "Modo fecha ficticia (QA)"),
    ("MensajesPlural", 'Mensajes en plural ("les avisaremos")'),
    ("ModoOscuro", "Modo oscuro"),
    ("VisualizarCamposLibres", "Visualizar campos libres (en todos los catálogos)"),
]
_CAMPOS_FECHA = [
    ("FechaFicticia", "Fecha ficticia"),
]
# "Campo" especial (Seguridad): no es un valor de Configuracion que se
# edite y guarde con el resto — es un botón que abre su propio diálogo y
# escribe directo a la base (ver _CampoContrasenaMaestra). Solo aparece
# en _GRUPOS/_ETIQUETAS, nunca en actualizar()/_guardar().
_CAMPOS_ESPECIALES = [
    ("ContrasenaMaestra", "Contraseña maestra"),
]

_ETIQUETAS: dict[str, str] = dict(
    _CAMPOS_TEXTO + _CAMPOS_NUMERICOS + _CAMPOS_BOOLEANOS + _CAMPOS_FECHA + _CAMPOS_ESPECIALES
)
_NOMBRES_BOOLEANOS = {nombre for nombre, _ in _CAMPOS_BOOLEANOS}
_NOMBRES_NUMERICOS = {nombre for nombre, _ in _CAMPOS_NUMERICOS}
_NOMBRES_FECHA = {nombre for nombre, _ in _CAMPOS_FECHA}

# Campos de texto que en vez de tipearse a mano eligen archivo/carpeta con
# un botón "Elegir" (QFileDialog) — la clave es el filtro de archivo para
# los de tipo archivo, `None` para los de carpeta.
_CAMPOS_RUTA_ARCHIVO: dict[str, str] = {"RutaLogo": "Imágenes (*.png *.jpg *.jpeg)"}
_CAMPOS_RUTA_CARPETA = {"CarpetaBaseArchivos", "CarpetaBackup"}

# (mínimo, máximo) por campo numérico — generosos a propósito: nunca deben
# recortar un valor ya guardado en la base (setValue() clampea en
# silencio), así que se prefiere de más a arriesgar perder precisión de
# un valor cargado antes de esta revisión.
_RANGOS_NUMERICOS: dict[str, tuple[float, float]] = {
    "HoraInicioGrilla": (0, 24),
    "HoraFinGrilla": (0, 24),
    "FraccionGrilla": (1, 120),
    "UmbralGiroGrilla": (1, 50),
    "RecargoPorcentajeAisladas": (0, 1000),
    "PorcentajeAjusteSaldoAtrasado": (0, 1000),
    "ToleranciaDeudaDescuento": (0, 100_000_000),
    "PorcentajeDescuentoFeriado": (0, 100),
    "PorcentajeDescuentoNoLaborable": (0, 100),
    "SemanasVacacionesMaximasPorAnio": (0, 52),
    "DiasEnvioLiquidacionesRemanentes": (0, 60),
    "RetencionHistorialListaEsperaAnios": (0, 50),
    "TamanoMaximoImagenMB": (0.1, 500),
    "CantidadDecimales": (0, 4),
    "MinutosInactividadBloqueo": (1, 240),
}
_CAMPOS_HORA = {"HoraInicioGrilla", "HoraFinGrilla"}
_CAMPOS_PORCENTAJE = {
    "RecargoPorcentajeAisladas", "PorcentajeAjusteSaldoAtrasado",
    "PorcentajeDescuentoFeriado", "PorcentajeDescuentoNoLaborable",
}
_CAMPOS_MONEDA = {"ToleranciaDeudaDescuento"}
_CAMPOS_MB = {"TamanoMaximoImagenMB"}

# Agrupamiento en solapas (a criterio propio, aprobado por la clienta —
# "cualquier cosa se reevalúa más adelante"). Cada nombre de campo
# aparece en un único grupo; el orden acá define el orden visual dentro
# de cada solapa (de arriba abajo) y, por lo tanto, el de la cadena de
# foco Enter/Tab de esa pestaña.
_GRUPOS: list[tuple[str, list[str]]] = [
    ("General", [
        "NombreEspacio", "RutaLogo", "ModoOscuro", "MensajesPlural",
        "ModulosExtendidos", "VisualizarCamposLibres", "CantidadDecimales",
    ]),
    ("Grilla y ocupación", [
        "DiasGrilla", "HoraInicioGrilla", "HoraFinGrilla", "FraccionGrilla",
        "UmbralGiroGrilla", "RangosEstadisticasOcupacion",
    ]),
    ("Valores y liquidación", [
        "FrecuenciaActualizacionValores", "MesesPeriodoActualizacion",
        "RecargoPorcentajeAisladas", "RecargoAisladasActivoPorDefecto",
        "PorcentajeAjusteSaldoAtrasado", "ToleranciaDeudaDescuento",
        "PorcentajeDescuentoFeriado", "PorcentajeDescuentoNoLaborable",
        "SemanasVacacionesMaximasPorAnio", "DiasEnvioLiquidacionesRemanentes",
        "RetencionHistorialListaEsperaAnios",
    ]),
    ("Archivos y backup", [
        "FrecuenciaBackupDrive", "CarpetaBaseArchivos", "CarpetaBackup", "TamanoMaximoImagenMB",
    ]),
    ("Modo QA", ["FechaFicticia", "ModoFechaFicticia"]),
    ("Seguridad", ["MinutosInactividadBloqueo", "ContrasenaMaestra"]),
]


class _SpinHora(QDoubleSpinBox):
    """QDoubleSpinBox que se muestra como horario ("8:00hs") en vez del
    decimal con punto que arrastra Qt por defecto — mismo criterio que
    `_SpinHora`/`_SpinHorario` de Oferta/Reservas/Lista de espera
    (duplicado acá, no importado: son pantallas sin relación entre sí)."""

    def textFromValue(self, value: float) -> str:  # noqa: N802 (nombre impuesto por Qt)
        horas = int(value)
        minutos = round((value - horas) * 60)
        return f"{horas}:{minutos:02d}hs"

    def valueFromText(self, text: str) -> float:  # noqa: N802
        texto = text.strip().lower().replace("hs", "").strip()
        if ":" in texto:
            horas_str, minutos_str = texto.split(":", 1)
            try:
                return float(horas_str or 0) + float(minutos_str or 0) / 60
            except ValueError:
                return 0.0
        try:
            return float(texto) if texto else 0.0
        except ValueError:
            return 0.0

    def validate(self, text: str, pos: int):  # noqa: N802
        return (QValidator.State.Acceptable, text, pos)


class _SpinMoneda(QDoubleSpinBox):
    """QDoubleSpinBox que se muestra como moneda ("$ 1.234,56") — mismo
    criterio que `_SpinMonto` de Pagos/Novedades/Llaves (duplicado acá,
    no importado)."""

    def textFromValue(self, value: float) -> str:  # noqa: N802
        return formatear_moneda(value)

    def valueFromText(self, text: str) -> float:  # noqa: N802
        texto = text.strip().replace("$", "").replace(".", "").replace(",", ".").strip()
        try:
            return float(texto) if texto else 0.0
        except ValueError:
            return 0.0

    def validate(self, text: str, pos: int):  # noqa: N802
        return (QValidator.State.Acceptable, text, pos)


def _crear_spin_numerico(nombre: str) -> QWidget:
    minimo, maximo = _RANGOS_NUMERICOS[nombre]
    if nombre in _CAMPOS_HORA:
        spin = _SpinHora()
        spin.setSingleStep(0.5)
    elif nombre in _CAMPOS_PORCENTAJE:
        spin = QDoubleSpinBox()
        spin.setDecimals(1)
        spin.setSuffix("%")
    elif nombre in _CAMPOS_MONEDA:
        spin = _SpinMoneda()
        spin.setDecimals(2)
    elif nombre in _CAMPOS_MB:
        spin = QDoubleSpinBox()
        spin.setDecimals(1)
        spin.setSuffix(" MB")
    else:
        spin = QSpinBox()
    spin.setRange(minimo, maximo)
    return spin


class _CampoRuta(QWidget):
    """Campo de ruta de archivo/carpeta con un botón "Elegir" al lado
    (`QFileDialog` nativo) en vez de tipear la ruta a mano. `self.campo`
    es un `QLineEdit` común — el resto de la pantalla (`actualizar`/
    `_guardar`) lo trata exactamente igual que cualquier otro campo de
    texto, sin necesidad de distinguirlo."""

    def __init__(self, *, es_carpeta: bool, filtro: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.campo = QLineEdit()
        layout.addWidget(self.campo, stretch=1)

        self.boton = QPushButton("Elegir")
        self.boton.setObjectName("botonSecundario")
        layout.addWidget(self.boton)

        self._filtro = filtro
        self.boton.clicked.connect(self._elegir_carpeta if es_carpeta else self._elegir_archivo)

    def _elegir_carpeta(self) -> None:
        carpeta = QFileDialog.getExistingDirectory(self, "Elegir carpeta", self.campo.text())
        if carpeta:
            self.campo.setText(carpeta)

    def _elegir_archivo(self) -> None:
        archivo, _filtro = QFileDialog.getOpenFileName(self, "Elegir archivo", self.campo.text(), self._filtro)
        if archivo:
            self.campo.setText(archivo)


class _DialogoContrasenaMaestra(QDialog):
    """Pide la contraseña maestra ANTERIOR (salvo la primera vez que se
    establece, que todavía no hay ninguna que pedir) más la nueva dos
    veces (confirmación), y escribe directo a la base
    (`cambiar_contrasena_maestra`) apenas se confirma — pedido explícito
    de la clienta: evita que cualquiera que abra esta pantalla pueda
    pisarla sin demostrar que ya la conocía."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._pide_actual = hay_contrasena_maestra(conn)
        self.setWindowTitle("Contraseña maestra")
        layout = QVBoxLayout(self)

        formulario = QFormLayout()
        if self._pide_actual:
            self.campo_actual = QLineEdit()
            self.campo_actual.setEchoMode(QLineEdit.EchoMode.Password)
            formulario.addRow("Contraseña maestra actual", self.campo_actual)
        self.campo_nueva = QLineEdit()
        self.campo_nueva.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_confirmar = QLineEdit()
        self.campo_confirmar.setEchoMode(QLineEdit.EchoMode.Password)
        formulario.addRow("Contraseña maestra nueva", self.campo_nueva)
        formulario.addRow("Confirmar", self.campo_confirmar)
        layout.addLayout(formulario)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _validar_y_aceptar(self) -> None:
        if not self.campo_nueva.text():
            QMessageBox.warning(self, "Contraseña maestra", "La contraseña no puede estar vacía.")
            return
        if self.campo_nueva.text() != self.campo_confirmar.text():
            QMessageBox.warning(self, "Contraseña maestra", "Las dos contraseñas no coinciden.")
            return
        contrasena_actual = self.campo_actual.text() if self._pide_actual else ""
        try:
            cambiar_contrasena_maestra(self.conn, contrasena_actual, self.campo_nueva.text())
        except ValueError as error:
            QMessageBox.warning(self, "Contraseña maestra", str(error))
            return
        self.accept()


class _CampoContrasenaMaestra(QWidget):
    """Botón que abre `_DialogoContrasenaMaestra` — el diálogo mismo
    escribe a la base apenas se confirma, sin pasar por "Guardar": nunca
    queda una contraseña pendiente de guardar en memoria más tiempo del
    necesario."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.boton = QPushButton("Establecer/cambiar contraseña maestra")
        self.boton.setObjectName("botonSecundario")
        self.boton.clicked.connect(self._abrir_dialogo)
        layout.addWidget(self.boton)
        layout.addStretch(1)

    def _abrir_dialogo(self) -> None:
        dialogo = _DialogoContrasenaMaestra(self.conn, self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Contraseña maestra", "Contraseña maestra actualizada.")


def _crear_campo_fecha() -> QDateEdit:
    entrada = QDateEdit()
    entrada.setCalendarPopup(True)
    entrada.setDisplayFormat(_FORMATO_FECHA_DIA)
    entrada.setLocale(QLocale(QLocale.Language.Spanish))
    return entrada


def _construir_campo(
    nombre: str, entradas: dict[str, QWidget], conn: sqlite3.Connection,
) -> tuple[QWidget, list[QWidget]]:
    """Arma el widget (o los widgets) de un campo y registra en
    `entradas` el que expone la interfaz que `actualizar`/`_guardar`
    esperan (`.text()`, `.value()`, `.isChecked()` o `.date()`). Devuelve
    (widget para la fila del formulario, widgets para la cadena de foco
    — más de uno cuando hay un botón al lado, ej. "Elegir"). Los campos
    de `_CAMPOS_ESPECIALES` (ej. "ContrasenaMaestra") no se registran en
    `entradas`: no pasan por `actualizar()`/`_guardar()`, escriben solos."""
    if nombre == "ContrasenaMaestra":
        campo = _CampoContrasenaMaestra(conn)
        return campo, [campo.boton]

    if nombre in _NOMBRES_BOOLEANOS:
        entrada = QCheckBox()
        entradas[nombre] = entrada
        return entrada, [entrada]

    if nombre in _NOMBRES_NUMERICOS:
        entrada = _crear_spin_numerico(nombre)
        entradas[nombre] = entrada
        return entrada, [entrada]

    if nombre in _NOMBRES_FECHA:
        entrada = _crear_campo_fecha()
        entradas[nombre] = entrada
        return entrada, [entrada]

    if nombre in _CAMPOS_RUTA_CARPETA:
        campo_ruta = _CampoRuta(es_carpeta=True)
        entradas[nombre] = campo_ruta.campo
        return campo_ruta, [campo_ruta.campo, campo_ruta.boton]

    if nombre in _CAMPOS_RUTA_ARCHIVO:
        campo_ruta = _CampoRuta(es_carpeta=False, filtro=_CAMPOS_RUTA_ARCHIVO[nombre])
        entradas[nombre] = campo_ruta.campo
        return campo_ruta, [campo_ruta.campo, campo_ruta.boton]

    entrada = QLineEdit()
    entradas[nombre] = entrada
    return entrada, [entrada]


class _PanelCampos(QWidget):
    """Una solapa: formulario (`QFormLayout`) con los campos de un grupo,
    envuelto en un `QScrollArea` interno (mismo patrón que `_PanelReservasRegulares`
    en Reservas — el propio `panelSolapa` es el widget que se pasa a
    `addTab`, con su `showEvent` propio, y el scroll queda adentro)."""

    def __init__(self, nombres: list[str], entradas: dict[str, QWidget], conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.orden: list[QWidget] = []

        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        contenido = QWidget()
        formulario = QFormLayout(contenido)
        for nombre in nombres:
            fila_widget, controles = _construir_campo(nombre, entradas, conn)
            formulario.addRow(_ETIQUETAS[nombre], fila_widget)
            self.orden.extend(controles)

        scroll.setWidget(contenido)
        layout_externo.addWidget(scroll)

    def showEvent(self, event) -> None:  # noqa: N802
        """Mismo motivo que en Reservas/Liquidación/Estadísticas: el foco
        pedido durante la construcción no alcanza a "pegar" porque el
        QTabWidget contenedor todavía no está mostrado en ese momento."""
        super().showEvent(event)
        if self.orden:
            self.orden[0].setFocus()


class ConfiguracionGeneral(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.repositorio = obtener_repositorio(conn, "Configuracion")
        self._entradas: dict[str, QWidget] = {}
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Configuración general".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self._paneles: list[_PanelCampos | None] = []
        for titulo_solapa, nombres in _GRUPOS:
            panel = _PanelCampos(nombres, self._entradas, self.conn)
            self.pestanas.addTab(panel, titulo_solapa)
            self._paneles.append(panel)
            if titulo_solapa == "Grilla y ocupación":
                self.panel_bloques_rigidos = _PanelBloquesRigidos(self.conn)
                self.pestanas.addTab(self.panel_bloques_rigidos, "Bloques rígidos")
                self._paneles.append(None)  # arma su propia cadena de foco, ver docstring del módulo
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)

        self.boton_guardar = QPushButton("Guardar")
        self.boton_guardar.setObjectName("botonPrimario")
        self.boton_guardar.clicked.connect(self._guardar)
        layout.addWidget(self.boton_guardar)

        # "Guardar" es compartido por las cinco solapas (guarda todo, no
        # solo la pestaña visible), así que la cadena de foco de cada una
        # se arma con SUS campos + ese botón al final — se reinstala cada
        # vez que se cambia de pestaña para que Enter/Tab en "Guardar"
        # vuelva siempre al primer campo de la solapa realmente visible.
        self.pestanas.currentChanged.connect(self._actualizar_cadena_foco)
        self._actualizar_cadena_foco(self.pestanas.currentIndex())

    def _actualizar_cadena_foco(self, indice: int) -> None:
        panel = self._paneles[indice]
        if panel is None:
            return  # esta solapa (Bloques rígidos) arma su propia cadena de foco
        self._foco = instalar_enter_avanza_foco(panel.orden + [self.boton_guardar], parent=self)

    def actualizar(self) -> None:
        registro = self.repositorio.obtener(1)
        if registro is None:
            return
        for nombre, _ in _CAMPOS_TEXTO:
            valor = registro[nombre]
            self._entradas[nombre].setText("" if valor is None else str(valor))
        for nombre, _ in _CAMPOS_NUMERICOS:
            valor = registro[nombre]
            self._entradas[nombre].setValue(valor if valor is not None else 0)
        for nombre, _ in _CAMPOS_BOOLEANOS:
            self._entradas[nombre].setChecked(bool(registro[nombre]))

        valor_fecha = registro["FechaFicticia"]
        fecha = QDate.fromString(valor_fecha, "yyyy-MM-dd") if valor_fecha else QDate()
        if not fecha.isValid():
            fecha = QDate.currentDate()
        self._entradas["FechaFicticia"].setDate(fecha)

    def _guardar(self) -> None:
        valores = {}
        for nombre, _ in _CAMPOS_NUMERICOS:
            valores[nombre] = self._entradas[nombre].value()
        for nombre, etiqueta in _CAMPOS_TEXTO:
            texto = self._entradas[nombre].text().strip()
            if texto and nombre in _VALIDADORES_TEXTO:
                validador, formato_esperado = _VALIDADORES_TEXTO[nombre]
                if not validador(texto):
                    QMessageBox.warning(
                        self, "Guardar configuración",
                        f"«{etiqueta}» no tiene el formato esperado ({formato_esperado}).",
                    )
                    return
            valores[nombre] = texto or None
        for nombre, _ in _CAMPOS_BOOLEANOS:
            valores[nombre] = 1 if self._entradas[nombre].isChecked() else 0
        valores["FechaFicticia"] = self._entradas["FechaFicticia"].date().toString("yyyy-MM-dd")

        self.repositorio.actualizar(1, **valores)
        aplicar_tema = getattr(self.window(), "_aplicar_tema", None)
        if aplicar_tema is not None:
            aplicar_tema()
        QMessageBox.information(self, "Guardar configuración", "Configuración guardada.")
        self.actualizar()
