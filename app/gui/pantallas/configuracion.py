"""Configuración general (F01, sección 3.28): única fila de la tabla
Configuracion — pantalla de formulario simple en vez del CRUD genérico de
lista, porque no tiene sentido crear/eliminar filas de esta tabla.

Revisión "uno por uno" (ver CLAUDE.md): pasó de un `QFormLayout` plano
con los 30 campos seguidos, uno abajo del otro, a formato solapa con 5
pestañas temáticas (agrupamiento a criterio propio, aprobado por la
clienta — "cualquier cosa se reevalúa más adelante"). El botón "Guardar"
queda FUERA del `QTabWidget`, compartido por las cinco solapas (guarda
todos los campos juntos, no solo los de la pestaña visible — sigue
siendo una única fila de configuración)."""
from __future__ import annotations

import json
import sqlite3

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.negocio.validaciones import FORMATO_FECHA, es_fecha_valida
from app.repositorio.registro import obtener_repositorio

FORMATO_JSON = "JSON válido"


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
    "FechaFicticia": (es_fecha_valida, FORMATO_FECHA),
}

_CAMPOS_TEXTO = [
    ("NombreEspacio", "Nombre del espacio"),
    ("DiasGrilla", "Días de grilla (JSON)"),
    ("FrecuenciaActualizacionValores", "Frecuencia de actualización de valores"),
    ("MesesPeriodoActualizacion", "Meses del período de actualización (JSON)"),
    ("RangosEstadisticasOcupacion", "Rangos de estadísticas de ocupación (JSON)"),
    ("FrecuenciaBackupDrive", "Frecuencia de backup a Drive"),
    ("FechaFicticia", "Fecha ficticia (AAAA-MM-DD)"),
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
]
_CAMPOS_BOOLEANOS = [
    ("RecargoAisladasActivoPorDefecto", "Recargo de aisladas activo por defecto"),
    ("ModulosExtendidos", "Módulos extendidos"),
    ("ModoFechaFicticia", "Modo fecha ficticia (QA)"),
    ("MensajesPlural", 'Mensajes en plural ("les avisaremos")'),
    ("ModoOscuro", "Modo oscuro"),
    ("VisualizarCamposLibres", "Visualizar campos libres (en todos los catálogos)"),
]

_ETIQUETAS: dict[str, str] = dict(_CAMPOS_TEXTO + _CAMPOS_NUMERICOS + _CAMPOS_BOOLEANOS)
_NOMBRES_BOOLEANOS = {nombre for nombre, _ in _CAMPOS_BOOLEANOS}

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
]


class _PanelCampos(QWidget):
    """Una solapa: formulario (`QFormLayout`) con los campos de un grupo,
    envuelto en un `QScrollArea` interno (mismo patrón que `_PanelReservasRegulares`
    en Reservas — el propio `panelSolapa` es el widget que se pasa a
    `addTab`, con su `showEvent` propio, y el scroll queda adentro)."""

    def __init__(self, nombres: list[str], entradas: dict[str, QWidget], parent=None):
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
            entrada = QCheckBox() if nombre in _NOMBRES_BOOLEANOS else QLineEdit()
            entradas[nombre] = entrada
            formulario.addRow(_ETIQUETAS[nombre], entrada)
            self.orden.append(entrada)

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
        self._paneles: list[_PanelCampos] = []
        for titulo_solapa, nombres in _GRUPOS:
            panel = _PanelCampos(nombres, self._entradas)
            self.pestanas.addTab(panel, titulo_solapa)
            self._paneles.append(panel)
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
        self._foco = instalar_enter_avanza_foco(panel.orden + [self.boton_guardar], parent=self)

    def actualizar(self) -> None:
        registro = self.repositorio.obtener(1)
        if registro is None:
            return
        for nombre, _ in _CAMPOS_TEXTO + _CAMPOS_NUMERICOS:
            valor = registro[nombre]
            self._entradas[nombre].setText("" if valor is None else str(valor))
        for nombre, _ in _CAMPOS_BOOLEANOS:
            self._entradas[nombre].setChecked(bool(registro[nombre]))

    def _guardar(self) -> None:
        valores = {}
        for nombre, etiqueta in _CAMPOS_NUMERICOS:
            texto = self._entradas[nombre].text().strip()
            if not texto:
                continue
            try:
                valores[nombre] = float(texto)
            except ValueError:
                QMessageBox.warning(self, "Guardar configuración", f"«{etiqueta}» debe ser un número.")
                return
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

        self.repositorio.actualizar(1, **valores)
        aplicar_tema = getattr(self.window(), "_aplicar_tema", None)
        if aplicar_tema is not None:
            aplicar_tema()
        QMessageBox.information(self, "Guardar configuración", "Configuración guardada.")
        self.actualizar()
