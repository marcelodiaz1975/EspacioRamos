"""Oferta de consultorios (Etapa 9, motor ad-hoc `app.negocio.oferta_busqueda`):
arma una búsqueda para un profesional puntual y genera el PDF o el texto de
WhatsApp con las alternativas encontradas, siempre resuelta contra la
disponibilidad vigente en el momento — no se guarda ningún historial de
búsquedas (decisión de la clienta: "búsqueda realizada es búsqueda
terminada", si hace falta se vuelve a generar en el momento).

Un documento puede tener varias franjas (una por cada característica de
búsqueda distinta, p. ej. "lunes y miércoles de mañana" + "viernes de
tarde"): el formulario arma UNA franja por vez y "Agregar franja" la suma
a la lista de la búsqueda actual, con su combinación con la próxima franja
(O: alcanza con que cualquiera tenga cobertura; Y: forman un paquete que
se ofrece entero o no se ofrece nada de él — ver
`app.negocio.oferta_busqueda.resolver_busquedas_documento`). Si no se
agrega ninguna franja explícita, "Generar" usa directo lo cargado en el
formulario como franja única (cubre el caso más común sin pasos de más).

Antes de generar, se muestra una previsualización
(`_DialogoPrevisualizacion`) con todas las alternativas encontradas y un
casillero por opción para destildar puntualmente las que no se quieran
ofrecer (p. ej. porque se prefiere guardar ese consultorio libre para
otro profesional) sin descartar el resto de la búsqueda.

En el lugar donde antes vivía el historial va la grilla operativa
(`GrillaOperativaWidget`) como referencia visual mientras se arma la
búsqueda, con sus propios filtros — el modo (regular/aislada) queda
fijado según el "Tipo de búsqueda" elegido, igual criterio que las
solapas de Reservas. El formulario no se resetea solo: lo cargado queda
tal cual si se sale de la pantalla y se vuelve a entrar (el widget sigue
vivo en memoria), y "Nueva búsqueda" es la única forma de limpiarlo a
propósito."""
from __future__ import annotations

import math
import sqlite3

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.gui.pantallas.reservas import _opciones_profesional
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.grilla_operativa import (
    GrillaOperativaWidget,
    _agregar_item_todos,
    _corregir_seleccion_todos,
    _FiltroColapsable,
    _ids_reales,
    _ids_seleccionados,
    _lista_multiseleccion,
    _seleccionar_todos,
)
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.archivos_generados import SUBCARPETA_OFERTA, carpeta_archivos_varios
from app.negocio.dias import DIAS_SEMANA
from app.negocio.oferta_busqueda import (
    COMBINAR_MISMA_UNIDAD,
    COMBINAR_MISMO_EDIFICIO,
    SIN_COMBINAR,
    TAMANOS_CONSULTORIO,
    TIPO_AISLADA,
    TIPO_REGULAR,
    Busqueda,
    CriteriosGlobales,
    fecha_fin_default,
    fecha_inicio_default,
)
from app.negocio.oferta_busqueda_texto import previsualizar_documento, resumen_busqueda
from app.negocio.oferta_busqueda_whatsapp import generar_texto_oferta_busqueda
from app.pdf.oferta_busqueda_pdf import generar_pdf_oferta_busqueda

_TAMANOS = [("Cualquier tamaño", None)] + [(t, t) for t in TAMANOS_CONSULTORIO]

_DIAS_BUSQUEDA = DIAS_SEMANA[:6]  # de acuerdo a los parámetros del sistema: reservas de lunes a sábado

_COMBINACIONES = [
    ("Sin combinación de consultorios", SIN_COMBINAR),
    ("Combinar, misma unidad", COMBINAR_MISMA_UNIDAD),
    ("Combinar, mismo edificio", COMBINAR_MISMO_EDIFICIO),
]
_UNION_FRANJAS = [
    ("Alcanza con esta franja sola (O)", "O"),
    ("Hace falta también la próxima (Y)", "Y"),
]


class _SpinHora(QDoubleSpinBox):
    """QDoubleSpinBox que se muestra como horario ("12:00hs", "9:30hs")
    en vez del decimal con punto que arrastra Qt por defecto — sigue
    siendo el mismo float por dentro (9.5 = 9:30) que espera
    `app.negocio.oferta_busqueda.Busqueda`, mismo criterio que
    `_SpinMonto` en Pagos."""

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


class _DialogoTexto(QDialog):
    """Muestra el texto de WhatsApp generado, listo para copiar."""

    def __init__(self, texto: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Texto para WhatsApp")
        self.resize(520, 480)
        layout = QVBoxLayout(self)
        campo = QPlainTextEdit()
        campo.setPlainText(texto)
        campo.setReadOnly(True)
        layout.addWidget(campo)
        boton_copiar = QPushButton("Copiar al portapapeles")
        boton_copiar.clicked.connect(lambda: QApplication.clipboard().setText(texto))
        layout.addWidget(boton_copiar)
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.accept)
        layout.addWidget(boton_cerrar)


class _DialogoPrevisualizacion(QDialog):
    """Muestra las alternativas encontradas (ya con la combinación Y/O
    entre franjas aplicada) con un casillero por opción: destildar una la
    deja afuera del documento sin descartar el resto de la búsqueda."""

    def __init__(self, filas: list[tuple[int, int, int, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Previsualización de la oferta")
        self.resize(560, 480)
        self._filas = filas
        layout = QVBoxLayout(self)

        if not filas:
            layout.addWidget(QLabel("No se encontraron alternativas para los criterios cargados."))
            self.lista = None
        else:
            layout.addWidget(QLabel("Destildá las opciones que no querés ofrecer:"))
            self.lista = QListWidget()
            for _, _, _, texto in filas:
                item = QListWidgetItem(texto)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.lista.addItem(item)
            layout.addWidget(self.lista, stretch=1)

        fila_botones = QHBoxLayout()
        boton_confirmar = QPushButton("Confirmar y generar")
        boton_confirmar.setObjectName("botonPrimario")
        boton_confirmar.clicked.connect(self.accept)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        fila_botones.addWidget(boton_confirmar)
        fila_botones.addWidget(boton_cancelar)
        layout.addLayout(fila_botones)

    def excluidas(self) -> set[tuple[int, int, int]]:
        if self.lista is None:
            return set()
        excluidas = set()
        for i in range(self.lista.count()):
            if self.lista.item(i).checkState() != Qt.CheckState.Checked:
                excluidas.add(self._filas[i][:3])
        return excluidas


class PantallaOferta(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._franjas: list[Busqueda] = []
        self._armar_ui()
        self._cargar_profesionales()
        self._cargar_localidades()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Oferta de consultorios")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        titulo_busqueda = QLabel("Nueva búsqueda")
        titulo_busqueda.setObjectName("subtituloSeccion")
        form.addWidget(titulo_busqueda)

        self.combo_profesional = QComboBox()
        habilitar_busqueda_profesional(self.combo_profesional)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_tipo = QComboBox()
        self.combo_tipo.addItem("Regular", TIPO_REGULAR)
        self.combo_tipo.addItem("Aislada", TIPO_AISLADA)
        self.combo_tipo.currentIndexChanged.connect(self._al_cambiar_tipo)
        form.addWidget(QLabel("Tipo de búsqueda"))
        form.addWidget(self.combo_tipo)

        fila_fechas = QHBoxLayout()
        self.campo_fecha_desde = QDateEdit()
        self.campo_fecha_desde.setCalendarPopup(True)
        self.campo_fecha_desde.setLocale(QLocale(QLocale.Language.Spanish))
        self.campo_fecha_desde.setDisplayFormat("ddd dd-MM-yyyy")
        self.campo_fecha_hasta = QDateEdit()
        self.campo_fecha_hasta.setCalendarPopup(True)
        self.campo_fecha_hasta.setLocale(QLocale(QLocale.Language.Spanish))
        self.campo_fecha_hasta.setDisplayFormat("ddd dd-MM-yyyy")
        fila_fechas.addWidget(QLabel("Desde"))
        fila_fechas.addWidget(self.campo_fecha_desde)
        fila_fechas.addWidget(QLabel("Hasta (solo Aislada)"))
        fila_fechas.addWidget(self.campo_fecha_hasta)
        fila_fechas.addStretch()
        form.addLayout(fila_fechas)

        form.addWidget(QLabel("Localidad"))
        self.lista_localidad = _lista_multiseleccion()
        self.lista_localidad.itemSelectionChanged.connect(self._cargar_edificios)
        self._filtro_localidad = _FiltroColapsable(self.lista_localidad)
        form.addWidget(self._filtro_localidad)

        form.addWidget(QLabel("Edificio"))
        self.lista_edificio = _lista_multiseleccion()
        self.lista_edificio.itemSelectionChanged.connect(self._cargar_unidades)
        self._filtro_edificio = _FiltroColapsable(self.lista_edificio)
        form.addWidget(self._filtro_edificio)

        form.addWidget(QLabel("Unidad"))
        self.lista_unidad = _lista_multiseleccion()
        self.lista_unidad.itemSelectionChanged.connect(self._unidad_seleccion_cambio)
        self._filtro_unidad = _FiltroColapsable(self.lista_unidad)
        form.addWidget(self._filtro_unidad)

        form.addWidget(QLabel("Días"))
        contenedor_dias = QWidget()
        grid_dias = QGridLayout(contenedor_dias)
        grid_dias.setContentsMargins(0, 0, 0, 0)
        self._checks_dia: dict[str, QCheckBox] = {}
        # En una sola tanda de filas (mitad arriba, mitad abajo) en vez de
        # una lista vertical larga — más legible. Se arma para la cantidad
        # de días que haya en `_DIAS_BUSQUEDA`, así que si el día domingo
        # se suma más adelante como opción de reserva, esto se adapta solo
        # (7 días -> 4 arriba y 3 abajo) sin tocar el layout a mano.
        columnas = math.ceil(len(_DIAS_BUSQUEDA) / 2)
        for i, dia in enumerate(_DIAS_BUSQUEDA):
            check = QCheckBox(dia)
            self._checks_dia[dia] = check
            grid_dias.addWidget(check, i // columnas, i % columnas)
        form.addWidget(contenedor_dias)

        fila_horario = QHBoxLayout()
        self.spin_desde = _SpinHora()
        self.spin_desde.setRange(0, 23)
        self.spin_desde.setValue(9)
        self.spin_hasta = _SpinHora()
        self.spin_hasta.setRange(1, 24)
        self.spin_hasta.setValue(12)
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_desde)
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hasta)
        fila_horario.addStretch()
        form.addLayout(fila_horario)

        fila_horas_minimas = QHBoxLayout()
        self.casilla_horas_minimas = QCheckBox("Cantidad de horas dentro del rango (en vez del rango completo)")
        self.spin_horas_minimas = QDoubleSpinBox()
        self.spin_horas_minimas.setRange(0.5, 24)
        self.spin_horas_minimas.setValue(1)
        self.spin_horas_minimas.setEnabled(False)
        self.casilla_horas_minimas.toggled.connect(self.spin_horas_minimas.setEnabled)
        fila_horas_minimas.addWidget(self.casilla_horas_minimas)
        fila_horas_minimas.addWidget(self.spin_horas_minimas)
        form.addLayout(fila_horas_minimas)

        self.combo_combinacion = QComboBox()
        for etiqueta, valor in _COMBINACIONES:
            self.combo_combinacion.addItem(etiqueta, valor)
        self.combo_combinacion.setCurrentIndex(2)
        form.addWidget(QLabel("Combinación de consultorios"))
        form.addWidget(self.combo_combinacion)

        form.addWidget(QLabel("Características pedidas"))
        self.casilla_ventana = QCheckBox("Con ventana")
        self.casilla_camilla = QCheckBox("Apto camilla")
        self.casilla_sillones = QCheckBox("Con sillones")
        for casilla in (self.casilla_ventana, self.casilla_camilla, self.casilla_sillones):
            form.addWidget(casilla)

        fila_tamano = QHBoxLayout()
        self.casilla_tamano = QCheckBox("Tamaño")
        self.combo_tamano = QComboBox()
        for etiqueta, valor in _TAMANOS:
            self.combo_tamano.addItem(etiqueta, valor)
        self.combo_tamano.setEnabled(False)
        self.casilla_tamano.toggled.connect(self.combo_tamano.setEnabled)
        fila_tamano.addWidget(self.casilla_tamano)
        fila_tamano.addWidget(self.combo_tamano)
        form.addLayout(fila_tamano)

        fila_valor_maximo = QHBoxLayout()
        self.casilla_valor_maximo = QCheckBox("Valor máximo por hora regular")
        self.spin_valor_maximo = QDoubleSpinBox()
        self.spin_valor_maximo.setRange(0, 10_000_000)
        self.spin_valor_maximo.setEnabled(False)
        self.casilla_valor_maximo.toggled.connect(self.spin_valor_maximo.setEnabled)
        fila_valor_maximo.addWidget(self.casilla_valor_maximo)
        fila_valor_maximo.addWidget(self.spin_valor_maximo)
        form.addLayout(fila_valor_maximo)

        self.combo_union_franja = QComboBox()
        for etiqueta, valor in _UNION_FRANJAS:
            self.combo_union_franja.addItem(etiqueta, valor)
        form.addWidget(QLabel("Combinación con la próxima franja"))
        form.addWidget(self.combo_union_franja)

        fila_franja = QHBoxLayout()
        self.boton_agregar_franja = QPushButton("Agregar franja a la búsqueda")
        self.boton_agregar_franja.clicked.connect(self._agregar_franja)
        self.boton_quitar_franja = QPushButton("Quitar franja seleccionada")
        self.boton_quitar_franja.clicked.connect(self._quitar_franja_seleccionada)
        fila_franja.addWidget(self.boton_agregar_franja)
        fila_franja.addWidget(self.boton_quitar_franja)
        form.addLayout(fila_franja)

        form.addWidget(QLabel(
            "Franjas agregadas a esta búsqueda (si no agregás ninguna, se usa lo cargado arriba como franja única)"
        ))
        self.lista_franjas = QListWidget()
        self.lista_franjas.setMaximumHeight(90)  # ya viene con scroll propio si hay muchas franjas
        form.addWidget(self.lista_franjas)

        self.casilla_detalle_reducido = QCheckBox("Detalle reducido (sin identificar el consultorio puntual)")
        form.addWidget(self.casilla_detalle_reducido)

        fila_botones = QHBoxLayout()
        self.boton_pdf = QPushButton("Generar PDF")
        self.boton_pdf.setObjectName("botonAccion")
        self.boton_pdf.clicked.connect(self._generar_pdf)
        self.boton_texto = QPushButton("Generar texto WhatsApp")
        self.boton_texto.setObjectName("botonAccion")
        self.boton_texto.clicked.connect(self._generar_texto)
        self.boton_nueva = QPushButton("Nueva búsqueda")
        self.boton_nueva.setObjectName("botonDestacado")
        self.boton_nueva.clicked.connect(self._nueva_busqueda)
        fila_botones.addWidget(self.boton_pdf)
        fila_botones.addWidget(self.boton_texto)
        fila_botones.addWidget(self.boton_nueva)
        form.addLayout(fila_botones)
        form.addStretch()
        splitter.addWidget(panel_form)

        self.grilla = GrillaOperativaWidget(self.conn)
        self.grilla.mostrar_leyenda_colores()
        self.grilla.fijar_titulo_filtros("Grilla semanal")
        splitter.addWidget(self.grilla)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, stretch=1)
        self._al_cambiar_tipo()

        self._foco = instalar_enter_avanza_foco(
            [
                self.combo_profesional, self.combo_tipo, self.campo_fecha_desde, self.campo_fecha_hasta,
                self._filtro_localidad.foco_widget(), self._filtro_edificio.foco_widget(),
                self._filtro_unidad.foco_widget(),
                *(self._checks_dia[dia] for dia in _DIAS_BUSQUEDA),
                self.spin_desde, self.spin_hasta, self.casilla_horas_minimas, self.spin_horas_minimas,
                self.combo_combinacion, self.casilla_ventana, self.casilla_camilla, self.casilla_sillones,
                self.casilla_tamano, self.combo_tamano, self.casilla_valor_maximo, self.spin_valor_maximo,
                self.combo_union_franja, self.boton_agregar_franja, self.boton_quitar_franja,
                self.casilla_detalle_reducido, self.boton_pdf, self.boton_texto, self.boton_nueva,
            ],
            parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        """Mismo motivo que Reservas: `setFocus()` durante la
        construcción no alcanza a "pegar" porque la pantalla todavía no
        está mostrada en ese momento."""
        super().showEvent(event)
        self.combo_profesional.setFocus()

    def _cargar_profesionales(self) -> None:
        self.combo_profesional.clear()
        for id_, etiqueta in _opciones_profesional(self.conn):
            self.combo_profesional.addItem(etiqueta, id_)

    def _cargar_localidades(self) -> None:
        """Cascada Localidad -> Edificio -> Unidad, mismo patrón compacto
        (con "Todas las X" tildado por defecto y colapsada hasta que se
        la abre) que ya usa `GrillaOperativaWidget` — reusa sus mismos
        helpers en vez de reimplementar la cascada acá."""
        self.lista_localidad.blockSignals(True)
        self.lista_localidad.clear()
        _agregar_item_todos(self.lista_localidad, "Todas las localidades")
        localidades = self.conn.execute(
            "SELECT DISTINCT DomicilioLocalidad FROM Edificio ORDER BY DomicilioLocalidad"
        ).fetchall()
        for fila in localidades:
            valor = fila["DomicilioLocalidad"]
            item = QListWidgetItem(valor or "(Sin localidad)")
            item.setData(Qt.ItemDataRole.UserRole, valor)
            self.lista_localidad.addItem(item)
        _seleccionar_todos(self.lista_localidad)
        self.lista_localidad.blockSignals(False)
        self._filtro_localidad.actualizar_resumen()
        self._cargar_edificios()

    def _cargar_edificios(self) -> None:
        _corregir_seleccion_todos(self.lista_localidad)
        self._filtro_localidad.actualizar_resumen()
        localidades = _ids_seleccionados(self.lista_localidad)
        self.lista_edificio.blockSignals(True)
        self.lista_edificio.clear()
        _agregar_item_todos(self.lista_edificio, "Todos los edificios")
        sql = "SELECT IdEdificio, Nombre FROM Edificio"
        parametros: list = []
        if localidades:
            marcas = []
            for loc in localidades:
                if loc is None:
                    marcas.append("DomicilioLocalidad IS NULL")
                else:
                    marcas.append("DomicilioLocalidad = ?")
                    parametros.append(loc)
            sql += " WHERE " + " OR ".join(marcas)
        sql += " ORDER BY Nombre"
        for fila in self.conn.execute(sql, parametros).fetchall():
            item = QListWidgetItem(fila["Nombre"])
            item.setData(Qt.ItemDataRole.UserRole, fila["IdEdificio"])
            self.lista_edificio.addItem(item)
        _seleccionar_todos(self.lista_edificio)
        self.lista_edificio.blockSignals(False)
        self._filtro_edificio.actualizar_resumen()
        self._cargar_unidades()

    def _cargar_unidades(self) -> None:
        _corregir_seleccion_todos(self.lista_edificio)
        self._filtro_edificio.actualizar_resumen()
        ids_edificio = _ids_seleccionados(self.lista_edificio)
        self.lista_unidad.blockSignals(True)
        self.lista_unidad.clear()
        _agregar_item_todos(self.lista_unidad, "Todas las unidades")
        sql = (
            "SELECT u.IdUnidad, u.Departamento, e.Nombre AS NombreEdificio FROM Unidad u "
            "JOIN Edificio e ON e.IdEdificio = u.IdEdificio"
        )
        parametros: list = []
        if ids_edificio:
            placeholders = ", ".join("?" for _ in ids_edificio)
            sql += f" WHERE u.IdEdificio IN ({placeholders})"
            parametros = ids_edificio
        filas = sorted(
            self.conn.execute(sql, parametros).fetchall(), key=lambda f: (f["NombreEdificio"], f["Departamento"]),
        )
        for fila in filas:
            item = QListWidgetItem(f"{fila['NombreEdificio']} - {fila['Departamento']}")
            item.setData(Qt.ItemDataRole.UserRole, fila["IdUnidad"])
            self.lista_unidad.addItem(item)
        _seleccionar_todos(self.lista_unidad)
        self.lista_unidad.blockSignals(False)
        self._filtro_unidad.actualizar_resumen()

    def _unidad_seleccion_cambio(self) -> None:
        _corregir_seleccion_todos(self.lista_unidad)
        self._filtro_unidad.actualizar_resumen()

    def _ids_unidad_seleccionadas(self) -> list[int]:
        return _ids_reales(self.lista_unidad)

    def _al_cambiar_tipo(self) -> None:
        tipo = self.combo_tipo.currentData()
        desde_iso = fecha_inicio_default(self.conn, tipo)
        self.campo_fecha_desde.setDate(QDate.fromString(desde_iso, Qt.DateFormat.ISODate))
        hasta_iso = fecha_fin_default(tipo, desde_iso)
        if hasta_iso:
            self.campo_fecha_hasta.setDate(QDate.fromString(hasta_iso, Qt.DateFormat.ISODate))
        self.campo_fecha_hasta.setEnabled(tipo == TIPO_AISLADA)
        self.grilla.fijar_modo("regular" if tipo == TIPO_REGULAR else "aislada")

    def _dias_seleccionados(self) -> list[str]:
        return [dia for dia, check in self._checks_dia.items() if check.isChecked()]

    def _armar_busqueda_actual(self) -> Busqueda | None:
        """Arma la franja a partir de lo cargado en el formulario ahora
        mismo (sin tocar `self._franjas`)."""
        dias = self._dias_seleccionados()
        if not dias:
            QMessageBox.warning(self, "Oferta de consultorios", "Elegí al menos un día.")
            return None
        tipo = self.combo_tipo.currentData()
        fecha_hasta = self.campo_fecha_hasta.date().toString(Qt.DateFormat.ISODate)
        return Busqueda(
            fecha_desde=self.campo_fecha_desde.date().toString(Qt.DateFormat.ISODate),
            fecha_hasta=fecha_hasta if tipo == TIPO_AISLADA else None,
            dias=dias,
            hora_desde=self.spin_desde.value(),
            hora_hasta=self.spin_hasta.value(),
            combinacion=self.combo_combinacion.currentData(),
            apto_camilla=self.casilla_camilla.isChecked(),
            ventana=self.casilla_ventana.isChecked(),
            sillones=self.casilla_sillones.isChecked(),
            tamano=self.combo_tamano.currentData() if self.casilla_tamano.isChecked() else None,
            valor_maximo_hora=self.spin_valor_maximo.value() if self.casilla_valor_maximo.isChecked() else None,
            cantidad_horas_minimas=self.spin_horas_minimas.value() if self.casilla_horas_minimas.isChecked() else None,
        )

    def _agregar_franja(self) -> None:
        busqueda = self._armar_busqueda_actual()
        if busqueda is None:
            return
        busqueda.combinacion_con_siguiente = self.combo_union_franja.currentData()
        self._franjas.append(busqueda)
        resumen = resumen_busqueda(busqueda, self.combo_tipo.currentData())
        if busqueda.combinacion_con_siguiente == "Y":
            resumen += " (Y con la próxima)"
        self.lista_franjas.addItem(resumen)
        for check in self._checks_dia.values():
            check.setChecked(False)

    def _quitar_franja_seleccionada(self) -> None:
        fila = self.lista_franjas.currentRow()
        if fila < 0:
            return
        self.lista_franjas.takeItem(fila)
        del self._franjas[fila]

    def _armar_criterios(self) -> tuple[int, CriteriosGlobales, list[Busqueda]] | None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Oferta de consultorios", "No hay profesionales cargados.")
            return None

        if self._franjas:
            busquedas = list(self._franjas)
        else:
            busqueda = self._armar_busqueda_actual()
            if busqueda is None:
                return None
            busquedas = [busqueda]

        globales = CriteriosGlobales(
            tipo_busqueda=self.combo_tipo.currentData(),
            ids_edificio=[],
            ids_unidad=self._ids_unidad_seleccionadas(),
            detalle_reducido=self.casilla_detalle_reducido.isChecked(),
        )
        return id_profesional, globales, busquedas

    def _limpiar_franjas(self) -> None:
        self._franjas = []
        self.lista_franjas.clear()

    def _generar_y_mostrar(self, generador) -> None:
        armado = self._armar_criterios()
        if armado is None:
            return
        id_profesional, globales, busquedas = armado

        try:
            filas = previsualizar_documento(self.conn, id_profesional, globales, busquedas)
        except ValueError as error:
            QMessageBox.warning(self, "Oferta de consultorios", str(error))
            return

        dialogo = _DialogoPrevisualizacion(filas, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        excluir = dialogo.excluidas()

        try:
            generador(id_profesional, globales, busquedas, excluir)
        except ValueError as error:
            QMessageBox.warning(self, "Oferta de consultorios", str(error))
            return
        self._limpiar_franjas()

    def _generar_pdf(self) -> None:
        def hacer(id_profesional, globales, busquedas, excluir) -> None:
            directorio = str(carpeta_archivos_varios(self.conn, SUBCARPETA_OFERTA))
            ruta = generar_pdf_oferta_busqueda(self.conn, directorio, id_profesional, globales, busquedas, excluir)
            QMessageBox.information(self, "Oferta de consultorios", f"Se generó:\n{ruta}")
        self._generar_y_mostrar(hacer)

    def _generar_texto(self) -> None:
        def hacer(id_profesional, globales, busquedas, excluir) -> None:
            texto = generar_texto_oferta_busqueda(self.conn, id_profesional, globales, busquedas, excluir)
            _DialogoTexto(texto, self).exec()
        self._generar_y_mostrar(hacer)

    def _nueva_busqueda(self) -> None:
        """Único punto que limpia el formulario a propósito — entrar y
        salir de la pantalla NO lo resetea (confirmado por la clienta:
        la última búsqueda queda cargada tal cual se la dejó)."""
        self.combo_profesional.setCurrentIndex(0)
        self.combo_tipo.setCurrentIndex(0)
        self._al_cambiar_tipo()
        self._cargar_localidades()  # vuelve la cascada a "Todas las..." en los tres niveles
        for check in self._checks_dia.values():
            check.setChecked(False)
        self.spin_desde.setValue(9)
        self.spin_hasta.setValue(12)
        self.casilla_horas_minimas.setChecked(False)
        self.spin_horas_minimas.setValue(1)
        self.combo_combinacion.setCurrentIndex(2)
        self.casilla_ventana.setChecked(False)
        self.casilla_camilla.setChecked(False)
        self.casilla_sillones.setChecked(False)
        self.casilla_tamano.setChecked(False)
        self.combo_tamano.setCurrentIndex(0)
        self.casilla_valor_maximo.setChecked(False)
        self.spin_valor_maximo.setValue(0)
        self.casilla_detalle_reducido.setChecked(False)
        self.combo_union_franja.setCurrentIndex(0)
        self._limpiar_franjas()
        self.combo_profesional.setFocus()
