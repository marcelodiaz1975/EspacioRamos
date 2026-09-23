"""Pantalla principal / panel de control (Etapa 6.1, FA1).

Segunda vuelta de la revisión "uno por uno" (ver CLAUDE.md): las dos
leyendas de estado que iban arriba de cada botón ("Período actual"/
"Último backup") y el subtítulo del encabezado (período en curso + hoy)
se sacaron — esa información ahora vive, más completa, en los cuadritos
de abajo. La solapa pasa a llamarse "Panel de control" (va a terminar
viviendo dentro de otro formulario más adelante, todavía a definir).
Los botones se invierten ("Generar backup ahora" arriba, "Avanzar de
mes" abajo) y "Avanzar de mes" vuelve a ser `botonPrimario` (el otro
queda `botonSecundario`) — sigue siendo la acción más "definitiva" de
esta pantalla. Debajo de los botones, seis cuadritos informativos del
mismo ancho y alto (reloj en vivo, período actual, estado del backup,
fechas especiales de los próximos dos meses, estadísticas de
profesionales, estadísticas de ocupación/horas) en una grilla 3x2, y
las alertas de siempre debajo de esos seis, ocupando todo el ancho de
la pantalla y con su propio scroll (mismo mecanismo de antes, ahora
como un cuadrito aparte en vez de una lista suelta). Tercera vuelta:
los seis cuadritos principales quedan parejos (mismo ancho y alto,
`_ALTO_MINIMO_TARJETA`), el título de cada cuadrito pasa a itálica y
termina en ":" (`_tarjeta`), y ni el título ni el contenido de abajo
tienen caja propia — un solo borde por cuadrito, el de afuera. Cuarta
vuelta: el borde de `_tarjeta` en realidad SÍ se colaba al título y al
contenido de abajo — `QLabel` hereda de `QFrame` en Qt, así que el
selector de clase `QFrame { border: ... }` de la vuelta anterior
también les pintaba el borde a esos `QLabel` hijos ("cuadritos dentro
de los cuadros", como lo señaló la clienta); se corrigió acotando el
estilo por objectName (`QFrame#cuadritoInfo`). El título de cada
cuadrito pasa además a negrita (ya estaba en itálica), y se suma una
línea divisoria entre los dos botones de la columna izquierda.

Quinta vuelta: el título de la tarjeta de fechas especiales se acorta
("Feriados y fechas especiales próximas") porque era el más largo y
forzaba esa columna de la grilla más ancha que las otras dos; su lógica
cambia de "desde el día 1 del mes en curso" a "desde hoy" (lo que ya
pasó del mes no se muestra) hasta el último día del SEGUNDO mes
siguiente (antes solo llegaba al primero) —
`app.negocio.panel_control.fechas_especiales_proximas_dos_meses`,
renombrada para reflejar el nuevo alcance. Las explicaciones de los
botones dejan de ser un único cuadro de texto y pasan a ser una por
botón, alineada al lado de su botón correspondiente (`fila_backup`/
`fila_avanzar`) — el texto de "Avanzar de mes" además se reescribe con
la redacción exacta pedida por la clienta.

Reordenamiento de formularios (Excel de la clienta): "Panel de control"
pasa a tener dos solapas en vez de una. Todo lo de arriba (botones,
grilla de cuadritos, alertas) se movió tal cual a una clase propia,
`_PanelAvancePeriodo` (mismo patrón `panelSolapa`/`showEvent` que el
resto de las pantallas con solapas de esta revisión), y se le sumó una
segunda solapa, "Importación datos desde Excel", con `_PanelImportacion`
(antes la pantalla propia "Importar planilla" del menú — importado acá,
mismo criterio de import cruzado de un símbolo privado que
`_pixmap_primera_pagina_pdf`/`_opciones_profesional` en otras
pantallas). `PanelControl` queda como el contenedor de afuera: solo el
título Nivel 1 (nombre del espacio) y el `QTabWidget` con las dos
solapas — `actualizar()` sigue siendo el punto de entrada externo
(ej. después de avanzar de mes desde otro lado), y delega en
`self.panel_avance.actualizar()` para todo lo que no sea el título."""
from __future__ import annotations

import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.pantallas.importacion import _PanelImportacion
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.negocio.avance_mes import avanzar_mes, pedidos_activos_vencidos, porcentaje_aumento_del_periodo
from app.negocio.backup import backup_vencido, carpeta_backup, generar_backup, ultimo_backup
from app.negocio.dias import fecha_a_dia_semana, fecha_actual, periodo_actual
from app.negocio.formato import formatear_moneda, mes_texto, periodo_mm_aaaa
from app.negocio.panel_control import (
    Alertas,
    calcular_alertas,
    calcular_estadisticas_ocupacion,
    calcular_estadisticas_profesionales,
    fechas_especiales_proximas_dos_meses,
)

_ANCHO_BOTON = 220
_COLUMNAS_GRILLA = 3
_ALTO_MINIMO_TARJETA = 140  # deja lugar de sobra al cuadrito con más líneas ("Ocupación y horas")

_TEXTO_EXPLICACION_BACKUP = (
    "Generar backup ahora copia la base de datos y toda la carpeta de archivos generados a la carpeta de "
    "backup configurada, sin esperar a que se cumpla la frecuencia automática."
)
_TEXTO_EXPLICACION_AVANZAR = (
    "Avanzar de mes realiza el pase de un mes a otro en el sistema. Este proceso ubica virtualmente al "
    "operador en el nuevo período cualquier sea la fecha real del día."
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


def _texto_explicacion(texto: str) -> QLabel:
    """Cuadro de texto fijo (borde negro) que explica un botón puntual —
    antes había uno solo para los dos botones, ahora hay uno por botón,
    alineado a su lado ("a la par del botón correspondiente")."""
    etiqueta = QLabel(texto)
    etiqueta.setWordWrap(True)
    etiqueta.setStyleSheet("border: 1px solid black; padding: 8px;")
    return etiqueta


def _texto_fecha_hora(momento: datetime, *, con_segundos: bool = False) -> str:
    """"vie 25-08-2026 14:45hs" — mismo criterio que las fechas de
    Registro de ausencias/Pagos (día de la semana abreviado + dd-MM-yyyy
    + hora), armado a mano porque acá el dato es un `datetime` de Python,
    no un campo de formulario con su propio `QDateEdit`."""
    dia = fecha_a_dia_semana(momento.date())[:3].lower()
    hora = f"{momento.hour:02d}:{momento.minute:02d}"
    if con_segundos:
        hora += f":{momento.second:02d}"
    return f"{dia} {momento.day:02d}-{momento.month:02d}-{momento.year} {hora}hs"


def _tarjeta(titulo: str) -> tuple[QFrame, QVBoxLayout]:
    """Cuadrito informativo: UN solo borde negro alrededor de todo el
    cuadrito (mismo criterio que el cuadro de texto de los botones) — el
    título y el contenido de abajo son texto plano sin caja propia,
    nunca cuadritos anidados. El estilo se aplica con un selector por
    objectName (`QFrame#cuadritoInfo`), no por clase (`QFrame` a secas):
    `QLabel` hereda de `QFrame` en Qt, así que un selector de clase sin
    acotar terminaba pintándole el mismo borde a los QLabel de adentro
    (título y contenido) — el bug que la clienta señaló como "cuadritos
    dentro de los cuadros". Título en negrita e itálica y terminado en
    ":", pedido explícito de la clienta; altura mínima pareja para que
    los seis cuadritos principales queden del mismo alto sin importar
    cuánto contenido tenga cada uno."""
    tarjeta = QFrame()
    tarjeta.setObjectName("cuadritoInfo")
    tarjeta.setStyleSheet("QFrame#cuadritoInfo { border: 1px solid black; }")
    tarjeta.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    tarjeta.setMinimumHeight(_ALTO_MINIMO_TARJETA)
    layout = QVBoxLayout(tarjeta)
    encabezado = QLabel(f"{titulo}:")
    encabezado.setStyleSheet("font-style: italic; font-weight: bold;")
    layout.addWidget(encabezado)
    return tarjeta, layout


class PanelControl(QWidget):
    """Contenedor de afuera: título Nivel 1 (nombre del espacio) + las dos
    solapas (`_PanelAvancePeriodo`/`_PanelImportacion`, ver docstring del
    módulo)."""

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

        solapas = QTabWidget()
        self.panel_avance = _PanelAvancePeriodo(self.conn)
        solapas.addTab(self.panel_avance, "Avance de período y backups")
        self.panel_importacion = _PanelImportacion(self.conn)
        solapas.addTab(self.panel_importacion, "Importación datos desde Excel")
        solapas.tabBar().setDrawBase(False)
        layout.addWidget(solapas, stretch=1)

    def actualizar(self) -> None:
        cfg = self.conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
        nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos Consultorios"
        self.titulo.setText(nombre_espacio.upper())
        self.panel_avance.actualizar()


class _PanelAvancePeriodo(QWidget):
    """Solapa "Avance de período y backups": todo lo que antes era el
    contenido único de Panel de control (botones, grilla de cuadritos,
    alertas) — ver docstring del módulo para el detalle de cada vuelta de
    revisión."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """Mismo motivo que en Estadísticas/Liquidación/Reservas: el foco
        pedido durante la construcción no alcanza a "pegar" porque el
        QTabWidget contenedor todavía no está mostrado en ese momento."""
        super().showEvent(event)
        self.boton_backup.setFocus()

    def _armar_ui(self) -> None:
        layout_solapa = QVBoxLayout(self)

        # Orden invertido a pedido de la clienta: "Generar backup ahora"
        # arriba, "Avanzar de mes" abajo — y este último vuelve a ser el
        # botonPrimario de la pantalla (el otro queda botonSecundario).
        # Cada botón va en su propia fila junto con SU explicación (antes
        # era un único cuadro de texto para los dos) — pedido explícito
        # de la clienta: "que queden a la par del botón correspondiente".
        self.boton_backup = QPushButton("Generar backup ahora")
        self.boton_backup.setObjectName("botonSecundario")
        self.boton_backup.setFixedWidth(_ANCHO_BOTON)
        self.boton_backup.clicked.connect(self._generar_backup)
        self.etiqueta_explicacion_backup = _texto_explicacion(_TEXTO_EXPLICACION_BACKUP)
        fila_backup = QHBoxLayout()
        fila_backup.addWidget(self.boton_backup, alignment=Qt.AlignmentFlag.AlignTop)
        fila_backup.addWidget(self.etiqueta_explicacion_backup, stretch=1)

        self.boton_avanzar = QPushButton("Avanzar de mes")
        self.boton_avanzar.setObjectName("botonPrimario")
        self.boton_avanzar.setFixedWidth(_ANCHO_BOTON)
        self.boton_avanzar.clicked.connect(self._avanzar_mes)
        self.etiqueta_explicacion_avanzar = _texto_explicacion(_TEXTO_EXPLICACION_AVANZAR)
        fila_avanzar = QHBoxLayout()
        fila_avanzar.addWidget(self.boton_avanzar, alignment=Qt.AlignmentFlag.AlignTop)
        fila_avanzar.addWidget(self.etiqueta_explicacion_avanzar, stretch=1)

        layout_solapa.addLayout(fila_backup)
        layout_solapa.addWidget(_linea_divisoria())
        layout_solapa.addLayout(fila_avanzar)

        # Seis cuadritos principales, todos del mismo ancho y alto (grilla
        # pareja 3x2 — sin la de Alertas, que va aparte ocupando todo el
        # ancho de la pantalla, ver abajo).
        grilla = QGridLayout()
        tarjetas = [
            self._armar_tarjeta_reloj(),
            self._armar_tarjeta_periodo(),
            self._armar_tarjeta_backup(),
            self._armar_tarjeta_fechas_especiales(),
            self._armar_tarjeta_profesionales(),
            self._armar_tarjeta_ocupacion(),
        ]
        for indice, tarjeta in enumerate(tarjetas):
            grilla.addWidget(tarjeta, indice // _COLUMNAS_GRILLA, indice % _COLUMNAS_GRILLA)
        for columna_grilla in range(_COLUMNAS_GRILLA):
            grilla.setColumnStretch(columna_grilla, 1)
        filas_grilla = -(-len(tarjetas) // _COLUMNAS_GRILLA)  # redondeo hacia arriba sin importar math
        for fila_grilla in range(filas_grilla):
            grilla.setRowStretch(fila_grilla, 1)
        layout_solapa.addLayout(grilla)

        # Alertas ocupa todo el ancho de la pantalla, con scroll propio
        # (puede ser una lista larga) — pedido explícito de la clienta,
        # a diferencia de los seis cuadritos parejos de arriba.
        layout_solapa.addWidget(self._armar_tarjeta_alertas(), stretch=1)

        self._foco = instalar_enter_avanza_foco([self.boton_backup, self.boton_avanzar], parent=self)

        self._timer_reloj = QTimer(self)
        self._timer_reloj.timeout.connect(self._actualizar_reloj)
        self._timer_reloj.start(1000)
        self._actualizar_reloj()

    # ------------------------------------------------------------ tarjetas

    def _armar_tarjeta_reloj(self) -> QFrame:
        tarjeta, layout = _tarjeta("Fecha y hora actual")
        self.etiqueta_reloj = QLabel()
        layout.addWidget(self.etiqueta_reloj)
        layout.addStretch()
        return tarjeta

    def _actualizar_reloj(self) -> None:
        """Hora real del sistema, no la fecha ficticia de QA — un reloj en
        vivo tiene que mostrar la hora real para orientar al operador,
        aunque el resto de la pantalla esté calculando sobre una fecha
        simulada."""
        self.etiqueta_reloj.setText(_texto_fecha_hora(datetime.now(), con_segundos=True))

    def _armar_tarjeta_periodo(self) -> QFrame:
        tarjeta, layout = _tarjeta("Período actual")
        self.etiqueta_periodo = QLabel()
        layout.addWidget(self.etiqueta_periodo)
        layout.addStretch()
        return tarjeta

    def _armar_tarjeta_backup(self) -> QFrame:
        tarjeta, layout = _tarjeta("Último backup")
        self.etiqueta_backup = QLabel()
        self.etiqueta_backup.setWordWrap(True)
        layout.addWidget(self.etiqueta_backup)
        layout.addStretch()
        return tarjeta

    def _armar_tarjeta_fechas_especiales(self) -> QFrame:
        tarjeta, layout = _tarjeta("Feriados y fechas especiales próximas")
        self.etiqueta_fechas_especiales = QLabel()
        self.etiqueta_fechas_especiales.setWordWrap(True)
        layout.addWidget(self.etiqueta_fechas_especiales)
        layout.addStretch()
        return tarjeta

    def _armar_tarjeta_profesionales(self) -> QFrame:
        tarjeta, layout = _tarjeta("Profesionales")
        self.etiqueta_profesionales = QLabel()
        self.etiqueta_profesionales.setWordWrap(True)
        layout.addWidget(self.etiqueta_profesionales)
        layout.addStretch()
        return tarjeta

    def _armar_tarjeta_ocupacion(self) -> QFrame:
        tarjeta, layout = _tarjeta("Ocupación y horas")
        self.etiqueta_ocupacion = QLabel()
        self.etiqueta_ocupacion.setWordWrap(True)
        layout.addWidget(self.etiqueta_ocupacion)
        layout.addStretch()
        return tarjeta

    def _armar_tarjeta_alertas(self) -> QFrame:
        self.tarjeta_alertas, layout = _tarjeta("Alertas")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.contenedor_alertas = QWidget()
        self.layout_alertas = QVBoxLayout(self.contenedor_alertas)
        self.layout_alertas.addStretch()
        scroll.setWidget(self.contenedor_alertas)
        layout.addWidget(scroll)
        return self.tarjeta_alertas

    def actualizar(self) -> None:
        periodo = periodo_actual(self.conn)
        anio, mes = (int(p) for p in periodo.split("-"))
        self.etiqueta_periodo.setText(f"{mes_texto(mes).capitalize()} de {anio} ({periodo_mm_aaaa(periodo)})")

        momento_backup = ultimo_backup(self.conn)
        frecuencia = self.conn.execute(
            "SELECT FrecuenciaBackupDrive FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()["FrecuenciaBackupDrive"]
        lineas_backup = [
            f"Último backup: {_texto_fecha_hora(momento_backup)}" if momento_backup is not None
            else "Todavía no se generó ningún backup.",
            f"Frecuencia configurada: {frecuencia}" if frecuencia else "Frecuencia configurada: sin definir",
        ]
        if carpeta_backup(self.conn) is not None:
            lineas_backup.append("Estado: vencido" if backup_vencido(self.conn, fecha_actual(self.conn)) else "Estado: al día")
        self.etiqueta_backup.setText("\n".join(lineas_backup))

        fechas = fechas_especiales_proximas_dos_meses(self.conn)
        if fechas:
            texto_fechas = "\n".join(f"•  {f['Fecha']} — {f['Descripcion'] or f['Tipo'] or 'Sin descripción'}" for f in fechas)
        else:
            texto_fechas = "Sin fechas especiales cargadas para lo que resta del período."
        self.etiqueta_fechas_especiales.setText(texto_fechas)

        prof = calcular_estadisticas_profesionales(self.conn)
        self.etiqueta_profesionales.setText(
            f"Con plan de pago vigente: {prof.con_plan_pago_vigente}\n"
            f"Con saldo fuera de tolerancia: {prof.con_saldo_fuera_de_tolerancia}\n"
            f"Con reservas regulares activas: {prof.con_reservas_regulares_activas}"
        )

        ocup = calcular_estadisticas_ocupacion(self.conn)
        self.etiqueta_ocupacion.setText(
            f"Ocupación regular general: {ocup.ocupacion_regular_pct:.1f}%\n"
            f"Horas regulares reservadas por semana: {ocup.horas_regulares_semanales:.1f}hs\n"
            f"Horas aisladas reservadas este mes: {ocup.horas_aisladas_mes:.1f}hs\n"
            f"Monto generado por esas horas aisladas: {formatear_moneda(ocup.monto_aisladas_mes)}\n"
            f"Saldo pendiente de cobro este mes: {formatear_moneda(ocup.saldo_pendiente_mes)}"
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
