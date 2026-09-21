"""Pantalla principal / panel de control (Etapa 6.1, FA1).

Revisión "uno por uno" (ver CLAUDE.md): pasó a formato solapa (una sola
pestaña, "Resumen"), con "Avanzar de mes" y "Generar backup ahora" como
`botonSecundario` los dos (pedido explícito de la clienta — esta
pantalla ya no tiene una acción "más importante" que la otra) en una
columna a la izquierda, cada uno con una leyenda de estado arriba
("Período actual"/"Último backup") y separados por una línea divisoria;
a la derecha, un cuadro de texto fijo que explica qué hace cada botón.
Las alertas siguen debajo, en su propia área con scroll (puede ser una
lista larga)."""
from __future__ import annotations

import sqlite3
from datetime import datetime

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.negocio.avance_mes import avanzar_mes, pedidos_activos_vencidos, porcentaje_aumento_del_periodo
from app.negocio.backup import generar_backup, ultimo_backup
from app.negocio.dias import fecha_a_dia_semana, fecha_actual, periodo_actual
from app.negocio.formato import formatear_moneda, mes_texto, periodo_mm_aaaa
from app.negocio.panel_control import Alertas, calcular_alertas

_ANCHO_PANEL_IZQUIERDA = 240
_ANCHO_BOTON = 220

_TEXTO_EXPLICACION = (
    '"Avanzar de mes" traspasa el saldo de cada profesional, cierra las cuotas de planes de pago que '
    "correspondan y genera el snapshot mensual de ocupación — se puede usar en cualquier momento, no hace "
    "falta esperar a que termine o empiece el mes.\n\n"
    '"Generar backup ahora" copia la base de datos y toda la carpeta de archivos generados a la carpeta de '
    "backup configurada, sin esperar a que se cumpla la frecuencia automática."
)

_TITULOS_ALERTA = {
    "deuda_regulares": "Deuda mes anterior — profesionales regulares",
    "deuda_aisladas": "Deuda mes anterior — profesionales de reserva aislada",
    "liquidaciones_regeneradas_no_enviadas": "Liquidaciones regeneradas sin enviar",
    "planes_con_cuotas_vencidas": "Planes de pago con cuotas vencidas",
    "fechas_especiales_proximas": "Fechas especiales en los próximos 15 días",
    "categoria_x_con_llaves_pendientes": "Profesionales inactivos con llaves sin devolver",
}

_ETIQUETA_FILA = {
    "deuda_regulares": lambda f: f"{f['Apellido']} — saldo anterior {formatear_moneda(f['SaldoCuentaAnterior'])}",
    "deuda_aisladas": lambda f: f"{f['Apellido']} — saldo anterior {formatear_moneda(f['SaldoCuentaAnterior'])}",
    "liquidaciones_regeneradas_no_enviadas": lambda f: f"Liquidación #{f['IdLiquidacion']} — período {f['Periodo']}",
    "planes_con_cuotas_vencidas": lambda f: f"Plan #{f['IdPlan']}",
    "fechas_especiales_proximas": lambda f: f"{f['Fecha']} — {f['Descripcion'] or f['Tipo']}",
    "categoria_x_con_llaves_pendientes": lambda f: f["Apellido"],
}


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _texto_fecha_hora(momento: datetime) -> str:
    """"vie 25-08-2026 14:45hs" — mismo criterio que las fechas de
    Registro de ausencias/Pagos (día de la semana abreviado + dd-MM-yyyy
    + hora), armado a mano porque acá el dato es un `datetime` de Python,
    no un campo de formulario con su propio `QDateEdit`."""
    dia = fecha_a_dia_semana(momento.date())[:3].lower()
    return f"{dia} {momento.day:02d}-{momento.month:02d}-{momento.year} {momento.hour:02d}:{momento.minute:02d}hs"


class PanelControl(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """Mismo motivo que en Estadísticas/Liquidación/Reservas: el foco
        pedido durante la construcción no alcanza a "pegar" porque el
        QTabWidget contenedor todavía no está mostrado en ese momento."""
        super().showEvent(event)
        self.boton_avanzar.setFocus()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.titulo = QLabel()
        self.titulo.setObjectName("tituloPantalla")
        layout.addWidget(self.titulo)

        self.subtitulo = QLabel()
        self.subtitulo.setObjectName("subtitulo")
        layout.addWidget(self.subtitulo)

        solapas = QTabWidget()
        panel_solapa = QWidget()
        panel_solapa.setObjectName("panelSolapa")
        layout_solapa = QVBoxLayout(panel_solapa)

        fila_superior = QHBoxLayout()
        panel_izquierda = QWidget()
        panel_izquierda.setFixedWidth(_ANCHO_PANEL_IZQUIERDA)
        columna = QVBoxLayout(panel_izquierda)
        columna.setContentsMargins(0, 0, 0, 0)

        self.leyenda_periodo = QLabel()
        self.leyenda_periodo.setObjectName("subtitulo")
        columna.addWidget(self.leyenda_periodo)

        self.boton_avanzar = QPushButton("Avanzar de mes")
        self.boton_avanzar.setObjectName("botonSecundario")
        self.boton_avanzar.setFixedWidth(_ANCHO_BOTON)
        self.boton_avanzar.clicked.connect(self._avanzar_mes)
        columna.addWidget(self.boton_avanzar)

        columna.addWidget(_linea_divisoria())

        self.leyenda_backup = QLabel()
        self.leyenda_backup.setObjectName("subtitulo")
        columna.addWidget(self.leyenda_backup)

        self.boton_backup = QPushButton("Generar backup ahora")
        self.boton_backup.setObjectName("botonSecundario")
        self.boton_backup.setFixedWidth(_ANCHO_BOTON)
        self.boton_backup.clicked.connect(self._generar_backup)
        columna.addWidget(self.boton_backup)

        columna.addStretch()
        fila_superior.addWidget(panel_izquierda)

        texto_explicacion = QLabel(_TEXTO_EXPLICACION)
        texto_explicacion.setWordWrap(True)
        texto_explicacion.setStyleSheet("border: 1px solid black; padding: 8px;")
        fila_superior.addWidget(texto_explicacion, stretch=1)
        layout_solapa.addLayout(fila_superior)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.contenedor_alertas = QWidget()
        self.layout_alertas = QVBoxLayout(self.contenedor_alertas)
        self.layout_alertas.addStretch()
        scroll.setWidget(self.contenedor_alertas)
        layout_solapa.addWidget(scroll, stretch=1)

        solapas.addTab(panel_solapa, "Resumen")
        solapas.tabBar().setDrawBase(False)
        layout.addWidget(solapas, stretch=1)

        self._foco = instalar_enter_avanza_foco([self.boton_avanzar, self.boton_backup], parent=self)

    def actualizar(self) -> None:
        cfg = self.conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
        nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"
        periodo = periodo_actual(self.conn)
        anio, mes = (int(p) for p in periodo.split("-"))
        hoy = fecha_actual(self.conn)

        self.titulo.setText(nombre_espacio)
        self.subtitulo.setText(
            f"Período en curso: {mes_texto(mes).capitalize()} de {anio} ({periodo_mm_aaaa(periodo)})  ·  "
            f"Hoy: {hoy.strftime('%d/%m/%Y')}"
        )
        self.leyenda_periodo.setText(f"Período actual {mes:02d}-{anio}")

        momento_backup = ultimo_backup(self.conn)
        self.leyenda_backup.setText(
            f"Último backup {_texto_fecha_hora(momento_backup)}" if momento_backup is not None
            else "Todavía no se generó ningún backup."
        )

        alertas = calcular_alertas(self.conn)
        self._refrescar_alertas(alertas)

    def _refrescar_alertas(self, alertas: Alertas) -> None:
        while self.layout_alertas.count() > 1:
            item = self.layout_alertas.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        hubo_alertas = False
        for campo, titulo in _TITULOS_ALERTA.items():
            filas = getattr(alertas, campo)
            if not filas:
                continue
            hubo_alertas = True
            tarjeta = self._tarjeta_alerta(titulo, filas, _ETIQUETA_FILA[campo])
            self.layout_alertas.insertWidget(self.layout_alertas.count() - 1, tarjeta)

        if alertas.backup_vencido:
            hubo_alertas = True
            tarjeta = self._tarjeta_alerta_simple(
                "Backup vencido según la frecuencia configurada — generá uno nuevo cuando puedas.",
            )
            self.layout_alertas.insertWidget(self.layout_alertas.count() - 1, tarjeta)

        if not hubo_alertas:
            self.layout_alertas.insertWidget(0, QLabel("Sin alertas pendientes."))

    def _tarjeta_alerta_simple(self, mensaje: str) -> QFrame:
        """Alerta binaria (no una lista de registros) — una sola línea."""
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjetaAlerta")
        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(0, 0, 0, 8)
        encabezado = QLabel(mensaje)
        encabezado.setObjectName("encabezadoAlerta")
        layout.addWidget(encabezado)
        return tarjeta

    def _tarjeta_alerta(self, titulo: str, filas: list, etiqueta) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjetaAlerta")
        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(0, 0, 0, 8)

        encabezado = QLabel(f"{titulo} ({len(filas)})")
        encabezado.setObjectName("encabezadoAlerta")
        layout.addWidget(encabezado)

        for fila in filas:
            etiqueta_widget = QLabel(f"•  {etiqueta(fila)}")
            etiqueta_widget.setContentsMargins(8, 2, 8, 2)
            layout.addWidget(etiqueta_widget)
        return tarjeta

    def _avanzar_mes(self) -> None:
        periodo = periodo_actual(self.conn)

        if porcentaje_aumento_del_periodo(self.conn, periodo) is None:
            respuesta_aumento = QMessageBox.question(
                self, "Avanzar de mes",
                f"¿Querés evaluar un aumento de valores para el período {periodo} antes de avanzar de mes?\n\n"
                "Elegí \"No\" para saltear este paso y avanzar directamente.",
            )
            if respuesta_aumento == QMessageBox.StandardButton.Yes:
                QMessageBox.information(
                    self, "Avanzar de mes",
                    "Se canceló el avance. Confirmá el aumento desde \"Aumentos y descuentos\" y volvé "
                    "a \"Avanzar de mes\" cuando termines.",
                )
                return

        confirmacion = QMessageBox.question(
            self, "Avanzar de mes",
            f"¿Confirmás el avance de mes para el período {periodo}? Esta acción traspasa saldos, "
            f"cierra cuotas y genera el snapshot mensual.",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return

        vencidos = pedidos_activos_vencidos(self.conn)
        eliminar_vencidos = False
        if vencidos:
            cantidad = len(vencidos)
            pedido_o_pedidos = "pedido" if cantidad == 1 else "pedidos"
            respuesta_vencidos = QMessageBox.question(
                self, "Lista de espera — pedidos vencidos",
                f"Hay {cantidad} {pedido_o_pedidos} Activo(s) en Lista de espera vencidos: superaron la "
                "retención configurada en Configuración. ¿Confirmás eliminarlos ahora?\n\n"
                "Si elegís \"No\" se conservan un tiempo más: podés eliminarlos a mano cuando quieras "
                "(descartando el pedido) o esperar a que se vuelva a avisar en un próximo avance de mes.",
            )
            eliminar_vencidos = respuesta_vencidos == QMessageBox.StandardButton.Yes

        resumen = avanzar_mes(
            self.conn, periodo_cerrado=periodo, eliminar_activos_vencidos_lista_espera=eliminar_vencidos,
        )
        self.conn.commit()
        mensaje_backup = (
            f"Backup previo generado en:\n{resumen.ruta_backup}\n\n" if resumen.backup_generado
            else "No se generó backup previo (falta configurar la carpeta de backup).\n\n"
        )
        mensaje_plazos = (
            f" Se aplicó el plazo extendido automático a {resumen.plazos_extendidos_automaticos_aplicados} "
            f"profesional(es)."
            if resumen.plazos_extendidos_automaticos_aplicados else ""
        )
        QMessageBox.information(
            self, "Avance de mes completado",
            f"{mensaje_backup}Se traspasó el saldo de {resumen.profesionales_con_traspaso} profesional(es), se cerraron "
            f"{resumen.cuotas_cerradas} cuota(s) y se generó el snapshot #{resumen.id_snapshot}.{mensaje_plazos}",
        )
        self.actualizar()

    def _generar_backup(self) -> None:
        try:
            ruta = generar_backup(self.conn)
        except ValueError as error:
            QMessageBox.warning(self, "Generar backup", str(error))
            return
        QMessageBox.information(self, "Generar backup", f"Backup generado en:\n{ruta}")
        self.actualizar()
