"""Pantalla principal / panel de control (Etapa 6.1, FA1)."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.negocio.avance_mes import avanzar_mes
from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.formato import mes_texto, periodo_mm_aaaa
from app.negocio.panel_control import Alertas, calcular_alertas, puede_avanzar_mes

_TITULOS_ALERTA = {
    "deuda_regulares": "Deuda mes anterior — profesionales regulares",
    "deuda_aisladas": "Deuda mes anterior — profesionales de reserva aislada",
    "liquidaciones_regeneradas_no_enviadas": "Liquidaciones regeneradas sin enviar",
    "planes_con_cuotas_vencidas": "Planes de pago con cuotas vencidas",
    "fechas_especiales_proximas": "Fechas especiales en los próximos 15 días",
    "categoria_x_con_llaves_pendientes": "Profesionales inactivos con llaves sin devolver",
}

_ETIQUETA_FILA = {
    "deuda_regulares": lambda f: f"{f['Apellido']} — saldo anterior $ {f['SaldoCuentaAnterior']:,.2f}",
    "deuda_aisladas": lambda f: f"{f['Apellido']} — saldo anterior $ {f['SaldoCuentaAnterior']:,.2f}",
    "liquidaciones_regeneradas_no_enviadas": lambda f: f"Liquidación #{f['IdLiquidacion']} — período {f['Periodo']}",
    "planes_con_cuotas_vencidas": lambda f: f"Plan #{f['IdPlan']}",
    "fechas_especiales_proximas": lambda f: f"{f['Fecha']} — {f['Descripcion'] or f['Tipo']}",
    "categoria_x_con_llaves_pendientes": lambda f: f["Apellido"],
}


class PanelControl(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.titulo = QLabel()
        self.titulo.setObjectName("tituloPantalla")
        layout.addWidget(self.titulo)

        self.subtitulo = QLabel()
        self.subtitulo.setObjectName("subtitulo")
        layout.addWidget(self.subtitulo)

        fila_boton = QHBoxLayout()
        self.boton_avanzar = QPushButton("Avanzar de mes")
        self.boton_avanzar.setObjectName("botonPrimario")
        self.boton_avanzar.clicked.connect(self._avanzar_mes)
        fila_boton.addWidget(self.boton_avanzar)
        fila_boton.addStretch()
        layout.addLayout(fila_boton)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.contenedor_alertas = QWidget()
        self.layout_alertas = QVBoxLayout(self.contenedor_alertas)
        self.layout_alertas.addStretch()
        scroll.setWidget(self.contenedor_alertas)
        layout.addWidget(scroll, stretch=1)

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
        self.boton_avanzar.setEnabled(puede_avanzar_mes(self.conn))

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

        if not hubo_alertas:
            self.layout_alertas.insertWidget(0, QLabel("Sin alertas pendientes."))

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
        confirmacion = QMessageBox.question(
            self, "Avanzar de mes",
            f"¿Confirmás el avance de mes para el período {periodo}? Esta acción traspasa saldos, "
            f"cierra cuotas y genera el snapshot mensual.",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        resumen = avanzar_mes(self.conn, periodo_cerrado=periodo)
        self.conn.commit()
        QMessageBox.information(
            self, "Avance de mes completado",
            f"Se traspasó el saldo de {resumen.profesionales_con_traspaso} profesional(es), se cerraron "
            f"{resumen.cuotas_cerradas} cuota(s) y se generó el snapshot #{resumen.id_snapshot}.",
        )
        self.actualizar()
