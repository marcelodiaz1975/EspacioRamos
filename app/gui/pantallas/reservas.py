"""Reservas regulares y aisladas (F16/F17, secciones 3.9-3.10): reusa
app.negocio.reservas para el alta (con toda la validación de conflictos,
bloques rígidos y ausencias) y la cancelación de aisladas, en vez de
escribir directamente en las tablas.

Reordenamiento de formularios (Excel de la clienta): las dos solapas se
renombran "Reservas regulares"/"Reservas aisladas" (antes "Regulares"/
"Aisladas") — la pantalla en sí sigue siendo la misma, sin ningún otro
cambio estructural."""
from __future__ import annotations

import re
import sqlite3
from datetime import date

from PySide6.QtCore import QDate, QLocale
from PySide6.QtGui import QGuiApplication, QValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.dialogos import confirmar_si_fecha_es_mes_anterior
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.grilla_operativa import (
    GrillaOperativaWidget,
    pares_dia_unidad_con_reserva,
    pares_dia_unidad_con_reserva_vigente,
)
from app.gui.widgets.items_tabla import item_numero
from app.gui.widgets.orden_tabla import OrdenTabla
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.ausencias import crear_ausencia
from app.negocio.dias import DIAS_SEMANA, fecha_a_dia_semana, fecha_actual, periodo_actual, ultimo_dia_mes
from app.negocio.formato import formatear_moneda
from app.negocio.lista_espera import marcar_resuelto
from app.negocio.liquidaciones import regenerar_si_corresponde
from app.negocio.llaves import llaves_faltantes_para_reserva
from app.negocio.mensajes import mensaje_detalle_reserva_aislada
from app.negocio.resumen_profesional import calcular_resumen_profesional
from app.negocio.reservas import (
    ConflictoBloqueanteError,
    cancelar_reserva_aislada,
    crear_reserva_aislada,
    crear_reserva_regular,
)
from app.repositorio.registro import obtener_repositorio

_DIAS_RESERVA = DIAS_SEMANA[:6]
_ANCHO_COMBO_PROFESIONAL = 190
_ANCHO_PANEL_FILTROS_GRILLA = 290
_ANCHO_COL_PROFESIONAL = 180
_FORMATO_FECHA = "dd-MM-yyyy"
_FECHA_SIN_DATO = QDate(2000, 1, 1)  # sentinel de QDateEdit.setSpecialValueText: "sin fecha"
# Pedido de la clienta: el campo "Fecha" de Reservas aisladas pasa al
# mismo formato "día de la semana abreviado" que Registro de ausencias/
# Fechas especiales (ej. "lun 07-09-2026") — mismo criterio, duplicado
# acá porque son pantallas sin relación entre sí.
_FORMATO_FECHA_DIA = "ddd dd-MM-yyyy"
_LOCALE_ES = QLocale(QLocale.Language.Spanish)
# Pedido de la clienta: "Profesional" (primer título de la columna del
# formulario) tiene que arrancar a la misma altura que "Filtro de
# localidad" (primer título del panel de Filtros de al lado, dentro de
# un QGroupBox con su propio margen superior nativo) — 21px medido
# programáticamente (geometría real de la ventana), no a ojo.
_ALTO_TITULO_FILTROS = 21
# Espaciado entre campos de la columna del formulario (6px por defecto
# en Qt) — se achica un poco en Reservas regulares para compensar el
# alto que le suma `_ALTO_TITULO_FILTROS` de arriba, ver el comentario
# en `_PanelReservasRegulares._armar_ui`.
_ESPACIADO_FORM = 4
# Pedido explícito de la clienta, solo para esta pantalla (no se toca
# `estilos.py`): los tres botones de acción (Crear/Modificar/Finalizar-
# Cancelar) quedaban más altos que el resto de los controles de esta
# columna (los botones-resumen de los filtros colapsables, ~22px) por el
# padding vertical default de `botonPrimario`/`botonSecundario` (8px,
# ~32px de alto total) — se lo pisa acá nomás, por widget, para bajarlo a
# 22px sin perder el color/borde que ya les da el objectName.
_ESTILO_BOTON_COMPACTO = "padding: 3px 16px;"
# Pedido explícito de la clienta, puntual de los tres botones de acción
# de Reservas AISLADAS (Crear/Modificar/Cancelar): en vez de quedar
# compactos como el resto de la columna (`_ESTILO_BOTON_COMPACTO`, 22px),
# crecen lo necesario para que "Horas aisladas mensuales" (el título que
# sigue después del separador, al final de esta columna) quede alineado
# con el borde inferior del cuadro "Detalle" de la grilla de al lado —
# valor medido (`padding: 11px 16px` ≈ 38px de alto por botón, sube el
# título ~48px en total entre los tres), no un número a ojo.
_ESTILO_BOTON_AISLADAS_ALTO = "padding: 11px 16px;"
# Pedido de la clienta: la tabla de abajo (Horarios reservados/Reservas
# aisladas) tiene que verse, título y un par de filas, sin scrollear el
# panel entero — ver el rearmado de `_armar_ui` en las dos clases de
# abajo, que la saca del QScrollArea de la grilla para que quede siempre
# visible en su propio espacio fijo. Muestra exactamente esta cantidad de
# filas (ver `_alto_para_filas`) y no una altura mínima aproximada: cuanto
# menos alto se lleve, más le queda disponible al panel de arriba
# (formulario + grilla, con su "Detalle" que antes quedaba fuera de la
# vista). Aisladas muestra más filas que Regulares porque a esta pantalla
# le sobraba lugar debajo de "Detalle"/"% Descuento" incluso con las 3 de
# antes (pedido explícito de la clienta al revisar la captura).
_FILAS_VISIBLES_TABLA_INFERIOR_REGULARES = 3
_FILAS_VISIBLES_TABLA_INFERIOR_AISLADAS = 4
# Alto máximo del cuadro "Detalle" en Reservas aisladas, ya sacado de la
# grilla y ocupando todo el ancho de "Filtros + grid" (90px por defecto
# en el resto de los usos) — ver `GrillaOperativaWidget.extraer_detalle`.
# Sube de 54 a 64 (medido, no a ojo) en la ronda que junta el gap grilla-
# Detalle: sacar el espaciado default de Qt ahí corrió a "Detalle" 6-10px
# hacia arriba, rompiendo la alineación de su borde inferior contra el
# pie de "Cant. horas aisladas mensuales" (pedido de una ronda anterior,
# "que se vea todo parejo") — el cuadro un poco más alto la recupera.
_ALTO_DETALLE_AISLADAS = 64
# Hasta la ronda anterior, `layout_externo` (form+grilla scrolleable,
# `stretch=1`, seguido de la tabla de abajo, sin stretch) le daba TODO el
# alto sobrante de la ventana a `scroll` — cualquier alto que `panel_
# tabla` dejara de necesitar (sacar un título, un margen) había que
# compensarlo con un espaciador fijo al final para que no se lo llevara
# de vuelta el scroll, empujando la tabla hacia abajo en la misma medida.
# Pedido explícito de la clienta, ronda posterior ("ampliá el tamaño de
# la tabla... que llegue lo más abajo posible... solo tocá la tabla"):
# se invirtió el reparto — `scroll` pasa a un alto FIJO igual a su propio
# mínimo (`contenido.minimumSizeHint()`, ver `_armar_ui` de las dos
# clases) y es `panel_tabla` el que se queda con `stretch=1`, así la
# tabla crece con TODO el sobrante en vez de que quede invisible dentro
# del scroll. Sin nada que compensar (el sobrante ahora es tabla de
# verdad, no hueco muerto), `_ALTO_TITULO_PANEL_TABLA`/`_ALTO_TITULO_
# PANEL_TABLA_REGULARES` — los espaciadores fijos de las dos rondas
# anteriores — dejaron de usarse y se sacaron.
# Cantidad de filas de "Referencias de colores" en Reservas aisladas (6
# referencias / 2 columnas, ver `LeyendaColores.hacer_compacta`) — usado
# para repartir en partes iguales, entre los "cuadraditos" de esa
# leyenda, el alto de sobra que gana el panel de Filtros al alinearse
# contra una grilla que ahora se muestra completa (pedido explícito de
# la clienta, ver `_PanelReservasAisladas._armar_ui`).
_FILAS_LEYENDA_AISLADA = 3
# Ajuste fino sobre el tope "identidad" de la grilla de Aisladas (pedido
# explícito de la clienta, ronda posterior: "ajustá un pelín la grilla
# para que se vea el borde de abajo y que no aparezca el escrolleable").
# Medido con un script de geometría: `alto_natural_grilla()` (el
# `sizeHint()` de la columna) quedaba 2px por debajo de lo que la tabla
# realmente necesita (`sum(rowHeight) + 2 × frameWidth`, con el
# encabezado horizontal oculto) — un desfasaje entre el `sizeHint` y el
# alto real de renderizado, no algo que dependa de los datos cargados,
# así que alcanza con sumarle un puñado de pixels fijo al tope antes de
# aplicarlo. Confirmado que sube a `tabla.verticalScrollBar().maximum()
# == 0` (antes daba 1) sin recortar el borde inferior de la grilla.
_AJUSTE_ALTO_GRILLA_AISLADAS = 2


def _alto_para_filas(tabla: QTableWidget, filas: int) -> int:
    """Alto fijo para que se vean exactamente `filas` filas sin scroll (la
    tabla sigue siendo scrolleable para el resto) — mismo criterio que
    `app.gui.pantallas.llaves._alto_para_filas`, duplicado acá porque son
    pantallas sin relación entre sí."""
    alto_fila = tabla.verticalHeader().defaultSectionSize()
    alto_header = tabla.horizontalHeader().sizeHint().height()
    return alto_header + alto_fila * filas + 2 * tabla.frameWidth()


def _fmt_horas(horas: float) -> str:
    return str(int(horas)) if horas == int(horas) else f"{horas:.1f}"


def _fmt_fecha(fecha_iso: str | None) -> str:
    if not fecha_iso:
        return ""
    return QDate.fromString(fecha_iso, "yyyy-MM-dd").toString(_FORMATO_FECHA)


def _fmt_hora(valor: float) -> str:
    """"9:00", "14:30" — mismo criterio que `_SpinHorario`, para las
    columnas de horario de las tablas (que no son spinboxes) y los
    combos que arman su propia etiqueta con un horario adentro."""
    horas = int(valor)
    minutos = round((valor - horas) * 60)
    return f"{horas}:{minutos:02d}"


def _fmt_horario(hora_inicio: float, hora_fin: float) -> str:
    return f"{_fmt_hora(hora_inicio)} a {_fmt_hora(hora_fin)}"


def _confirmar_llaves_faltantes(parent: QWidget, faltantes: list[str]) -> bool:
    """Pedido explícito de la clienta: al cargar una reserva (regular o
    aislada), si `llaves_faltantes_para_reserva` encuentra que el
    profesional no tiene alguna llave de acceso necesaria, avisa con un
    cartel Sí/No en vez de bloquear la carga — puede igual atender ahí
    haciéndose abrir por otro profesional presente en ese momento, "pero
    está bueno que el sistema avise para ver cómo se maneja el acceso".
    Devuelve True si el operador elige seguir igual (Sí), False si
    cancela (No) — mismo criterio (`QMessageBox.question`, Sí/No) que el
    resto de los carteles de confirmación de esta pantalla (ej.
    `ConflictoBloqueanteError`)."""
    respuesta = QMessageBox.question(
        parent, "Falta acceso al lugar",
        "Al profesional le falta " + " y ".join(faltantes) + ".\n\n"
        "Puede atender igual si otro profesional presente le abre.\n"
        "¿Confirmás la reserva de todos modos?",
    )
    return respuesta == QMessageBox.StandardButton.Yes


class _SpinHorario(QDoubleSpinBox):
    """QDoubleSpinBox que se muestra como horario ("9:00", "14:30") en vez
    del decimal ("9,00", "14,5") que arrastra el separador de la
    configuración regional — internamente sigue siendo el mismo float en
    horas que espera `app.negocio.reservas` (9.0, 14.5, ...)."""

    def textFromValue(self, value: float) -> str:  # noqa: N802 (nombre impuesto por Qt)
        return _fmt_hora(value)

    def valueFromText(self, text: str) -> float:  # noqa: N802
        texto = text.strip()
        if ":" in texto:
            horas_str, minutos_str = texto.split(":", 1)
            return int(horas_str or 0) + int(minutos_str or 0) / 60
        return float(texto.replace(",", ".") or 0)

    def validate(self, text: str, pos: int):  # noqa: N802
        return (QValidator.State.Acceptable, text, pos)


_CATEGORIAS_REGULARES = ("R", "B", "E")
_CATEGORIAS_AISLADAS = ("R", "A")
_ORDEN_CATEGORIA_REGULAR = {"B": 0, "R": 1, "E": 2}
_ORDEN_CATEGORIA_AISLADA = {cat: i for i, cat in enumerate(_CATEGORIAS_AISLADAS)}
_SIN_ELEGIR = object()  # sentinel del placeholder "Seleccionar…" de Localidad (None ya es un valor real: "sin localidad")


def _numero_codigo(codigo: str | None) -> int:
    """El número de "R12" -> 12, para ordenar numéricamente en vez de
    alfabéticamente (que pondría "R10" antes que "R2"). Sin código, o sin
    ningún dígito en él, se manda al final."""
    if not codigo:
        return 10**9
    coincidencia = re.search(r"\d+", codigo)
    return int(coincidencia.group()) if coincidencia else 10**9


def _texto_profesional(fila: sqlite3.Row) -> str:
    """"R1 - Lic. Virginia Lo Veci": código (si tiene) + Tratamiento +
    NombrePila + Apellido, estos últimos tres opcionales si el
    profesional no los tiene cargados."""
    partes = [p for p in (fila["Tratamiento"], fila["NombrePila"], fila["Apellido"]) if p]
    nombre = " ".join(partes) if partes else fila["Apellido"]
    codigo = fila["IdCodigo"]
    return f"{codigo} - {nombre}" if codigo else nombre


def _opciones_profesional(
    conn: sqlite3.Connection, categorias: tuple[str, ...] | None = None
) -> list[tuple[int, str]]:
    """`categorias=None` trae todos los profesionales sin filtrar por
    categoría (por ejemplo, para pantallas donde puede aparecer cualquier
    profesional sin importar su categoría)."""
    if categorias is None:
        filas = conn.execute(
            "SELECT IdProfesional, IdCodigo, Tratamiento, Apellido, NombrePila FROM Profesional ORDER BY Apellido"
        ).fetchall()
    else:
        placeholders = ", ".join("?" for _ in categorias)
        filas = conn.execute(
            f"SELECT IdProfesional, IdCodigo, Tratamiento, Apellido, NombrePila FROM Profesional "
            f"WHERE CategoriaProfesional IN ({placeholders}) ORDER BY Apellido",
            categorias,
        ).fetchall()
    return [(f["IdProfesional"], _texto_profesional(f)) for f in filas]


def _opciones_horario_regular(conn: sqlite3.Connection, id_profesional: int | None) -> list[tuple[int, str]]:
    """Horarios regulares vigentes del profesional — para que, al marcar
    "Es reubicación" en el alta de una reserva aislada, el operador pueda
    elegir cuál de ellos no va a usar esta vez."""
    if id_profesional is None:
        return []
    filas = conn.execute(
        "SELECT r.IdConsultorio, r.DiaSemana, r.HoraInicio, r.HoraFin, u.Departamento, c.NumeroConsultorio "
        "FROM ReservaRegular r JOIN Consultorio c ON c.IdConsultorio = r.IdConsultorio "
        "JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
        "WHERE r.IdProfesional = ? AND (r.VigenciaFin IS NULL OR r.VigenciaFin >= ?) "
        "ORDER BY r.DiaSemana, r.HoraInicio",
        (id_profesional, fecha_actual(conn).isoformat()),
    ).fetchall()
    return [
        (
            f["IdConsultorio"],
            f"{f['DiaSemana']} {_fmt_horario(f['HoraInicio'], f['HoraFin'])} - {f['Departamento']} - {f['NumeroConsultorio']}",
        )
        for f in filas
    ]


def _opciones_localidad(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    filas = conn.execute(
        "SELECT DISTINCT e.IdLocalidad, loc.Localidad FROM Edificio e "
        "LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad ORDER BY loc.Localidad"
    ).fetchall()
    return [(f["IdLocalidad"], f["Localidad"] or "(Sin localidad)") for f in filas]


def _opciones_edificio(conn: sqlite3.Connection, id_localidad: int | None) -> list[tuple[int, str]]:
    if id_localidad is None:
        filas = conn.execute(
            "SELECT IdEdificio, Nombre FROM Edificio WHERE IdLocalidad IS NULL ORDER BY Nombre"
        ).fetchall()
    else:
        filas = conn.execute(
            "SELECT IdEdificio, Nombre FROM Edificio WHERE IdLocalidad = ? ORDER BY Nombre", (id_localidad,)
        ).fetchall()
    return [(f["IdEdificio"], f["Nombre"]) for f in filas]


def _opciones_unidad(conn: sqlite3.Connection, id_edificio: int | None) -> list[tuple[int, str]]:
    if id_edificio is None:
        return []
    filas = conn.execute(
        "SELECT IdUnidad, Departamento FROM Unidad WHERE IdEdificio = ? ORDER BY Departamento", (id_edificio,)
    ).fetchall()
    return [(f["IdUnidad"], f["Departamento"]) for f in filas]


def _opciones_consultorio_de_unidad(conn: sqlite3.Connection, id_unidad: int | None) -> list[tuple[int, str]]:
    if id_unidad is None:
        return []
    filas = conn.execute(
        "SELECT IdConsultorio, NumeroConsultorio FROM Consultorio WHERE IdUnidad = ? ORDER BY NumeroConsultorio",
        (id_unidad,),
    ).fetchall()
    return [(f["IdConsultorio"], f"Consultorio {f['NumeroConsultorio']}") for f in filas]


def _recargar_unidades(conn: sqlite3.Connection, combo_edificio: QComboBox, combo_unidad: QComboBox) -> None:
    id_edificio = combo_edificio.currentData()
    combo_unidad.blockSignals(True)
    combo_unidad.clear()
    for id_, depto in _opciones_unidad(conn, id_edificio):
        combo_unidad.addItem(depto, id_)
    combo_unidad.blockSignals(False)


def _recargar_consultorios(conn: sqlite3.Connection, combo_unidad: QComboBox, combo_consultorio: QComboBox) -> None:
    id_unidad = combo_unidad.currentData()
    combo_consultorio.blockSignals(True)
    combo_consultorio.clear()
    for id_, etiqueta in _opciones_consultorio_de_unidad(conn, id_unidad):
        combo_consultorio.addItem(etiqueta, id_)
    combo_consultorio.blockSignals(False)


class PantallaReservas(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Reservas")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_regulares = _PanelReservasRegulares(conn)
        self.panel_aisladas = _PanelReservasAisladas(conn)
        self.pestanas.addTab(self.panel_regulares, "Reservas regulares")
        self.pestanas.addTab(self.panel_aisladas, "Reservas aisladas")
        layout.addWidget(self.pestanas, stretch=1)

    def actualizar(self) -> None:
        self.panel_regulares.actualizar()
        self.panel_aisladas.actualizar()


class _PanelReservasRegulares(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._reservas: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar":
        el QTabWidget contenedor todavía no está mostrado y se termina
        quedando el foco en su tab bar. Al mostrarse la pestaña (al
        abrir la pantalla o volver a esta solapa) se repite el pedido
        de foco en Profesional, que es cuando realmente surte efecto.
        De paso, vuelve a fijar el alto de `_scroll_superior` (ver
        `_armar_ui`): el `minimumSizeHint()` calculado ANTES de este
        primer show puede quedar unos pixels desincronizado del real."""
        super().showEvent(event)
        self._scroll_superior.setFixedHeight(self._contenido_superior.minimumSizeHint().height())
        self._orden.reiniciar()
        self.actualizar()
        self.combo_profesional.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        # Sin espaciado default de Qt entre los ítems (pedido de la
        # clienta: separación mínima entre lo de arriba y la tabla) — ver
        # más abajo cómo se reparte el alto entre `scroll` y `panel_
        # tabla`.
        layout_externo.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        contenido = QWidget()
        contenido.setObjectName("panelSolapa")
        layout = QVBoxLayout(contenido)
        # Sin margen propio (pedido de la clienta: que "% Descuento" se vea
        # sin scrollear) — panel_form/grupo_grilla ya traen su propio
        # respiro interno, este margen extra solo le restaba alto
        # disponible a la columna del formulario, que es la más alta de
        # las dos y la que termina fijando cuánto hay que scrollear.
        layout.setContentsMargins(0, 0, 0, 0)
        splitter_superior = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        # Sin margen abajo (mismo motivo que el de `contenido` más arriba:
        # esta columna es la más alta de las dos y cualquier margen de
        # sobra le resta a lo que necesitamos recuperar para que "%
        # Descuento" se vea sin scrollear). El margen de arriba, en
        # cambio, no se saca del todo: queda en `_ALTO_TITULO_FILTROS`
        # (21px, medido) para que "Profesional" arranque a la misma
        # altura que "Filtro de localidad" (el título del panel de al
        # lado, dentro de un `QGroupBox` con su propio margen superior
        # nativo que un margen en 0 acá no puede igualar) — pedido
        # explícito de la clienta. Ese margen nuevo hay que recuperarlo de
        # algún lado para que "% Descuento" se siga viendo sin scrollear:
        # `_ESPACIADO_FORM` (4px, menos que el 6px default de Qt) achica
        # un poco el espacio entre cada campo de esta columna (son
        # muchos: 5 combos, "Días", horario, dos vigencias, 3 botones,
        # separador, 2 títulos informativos), alcanza para compensarlo.
        form.setContentsMargins(9, _ALTO_TITULO_FILTROS, 9, 0)
        form.setSpacing(_ESPACIADO_FORM)
        self.combo_profesional = QComboBox()
        self.combo_profesional.setMinimumWidth(_ANCHO_COMBO_PROFESIONAL)
        self.combo_profesional.addItem("Todos los profesionales", None)
        for id_, etiqueta in _opciones_profesional(self.conn, _CATEGORIAS_REGULARES):
            self.combo_profesional.addItem(etiqueta, id_)
        habilitar_busqueda_profesional(self.combo_profesional)
        self.combo_profesional.currentIndexChanged.connect(self.actualizar)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_localidad = QComboBox()
        opciones_localidad = _opciones_localidad(self.conn)
        if len(opciones_localidad) > 1:
            self.combo_localidad.addItem("Seleccionar…", _SIN_ELEGIR)
        for valor, etiqueta in opciones_localidad:
            self.combo_localidad.addItem(etiqueta, valor)
        self.combo_localidad.setEnabled(len(opciones_localidad) > 1)
        self.combo_localidad.currentIndexChanged.connect(self._cargar_edificios)
        form.addWidget(QLabel("Localidad"))
        form.addWidget(self.combo_localidad)

        self.combo_edificio = QComboBox()
        self.combo_edificio.currentIndexChanged.connect(self._cargar_unidades)
        form.addWidget(QLabel("Edificio"))
        form.addWidget(self.combo_edificio)

        self.combo_unidad = QComboBox()
        self.combo_unidad.currentIndexChanged.connect(self._cargar_consultorios)
        form.addWidget(QLabel("Unidad"))
        form.addWidget(self.combo_unidad)

        self.combo_consultorio = QComboBox()
        self.combo_consultorio.currentIndexChanged.connect(self._sincronizar_grilla)
        form.addWidget(QLabel("Consultorio"))
        form.addWidget(self.combo_consultorio)

        form.addWidget(QLabel("Días"))
        self._checks_dia: dict[str, QCheckBox] = {}
        contenedor_dias = QWidget()
        grid_dias = QGridLayout(contenedor_dias)
        grid_dias.setContentsMargins(0, 0, 0, 0)
        # Dos por línea (Lunes/Martes, Miércoles/Jueves, Viernes/Sábado),
        # pedido explícito de la clienta — a diferencia de la grilla de
        # Oferta de consultorios (mitad arriba/mitad abajo), acá son
        # siempre 2 columnas fijas: si se suma Domingo a `_DIAS_RESERVA`
        # más adelante, cae solo en una fila nueva debajo de Viernes/
        # Sábado, sin acompañante en la segunda columna.
        for i, dia in enumerate(_DIAS_RESERVA):
            check = QCheckBox(dia)
            check.setChecked(dia == "Lunes")
            self._checks_dia[dia] = check
            grid_dias.addWidget(check, i // 2, i % 2)
        form.addWidget(contenedor_dias)

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
        form.addLayout(fila_horario)

        # Mismo formato "día de la semana abreviado" que "Fecha" en
        # Reservas aisladas (pedido explícito de la clienta, "que se
        # comporte igual") — duplicado acá, sin relación entre las dos
        # solapas más que este formato compartido.
        self.campo_vigencia_inicio = QDateEdit()
        self.campo_vigencia_inicio.setDisplayFormat(_FORMATO_FECHA_DIA)
        self.campo_vigencia_inicio.setLocale(_LOCALE_ES)
        self.campo_vigencia_inicio.setCalendarPopup(True)
        form.addWidget(QLabel("Vigencia desde"))
        form.addWidget(self.campo_vigencia_inicio)

        self.campo_vigencia_fin = QDateEdit()
        self.campo_vigencia_fin.setDisplayFormat(_FORMATO_FECHA_DIA)
        self.campo_vigencia_fin.setLocale(_LOCALE_ES)
        self.campo_vigencia_fin.setCalendarPopup(True)
        self.campo_vigencia_fin.setMinimumDate(_FECHA_SIN_DATO)
        self.campo_vigencia_fin.setSpecialValueText("(sin fecha)")
        self.campo_vigencia_fin.setDate(_FECHA_SIN_DATO)
        form.addWidget(QLabel("Vigencia hasta (opcional)"))
        form.addWidget(self.campo_vigencia_fin)

        boton_crear = QPushButton("Crear reserva regular")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.setStyleSheet(_ESTILO_BOTON_COMPACTO)
        boton_crear.clicked.connect(self._crear)
        form.addWidget(boton_crear)
        boton_modificar = QPushButton("Modificar seleccionada")
        boton_modificar.setObjectName("botonSecundario")
        boton_modificar.setStyleSheet(_ESTILO_BOTON_COMPACTO)
        boton_modificar.clicked.connect(self._modificar_seleccionada)
        form.addWidget(boton_modificar)
        boton_finalizar = QPushButton("Finalizar reserva a fin de mes")
        boton_finalizar.setObjectName("botonSecundario")
        boton_finalizar.setStyleSheet(_ESTILO_BOTON_COMPACTO)
        boton_finalizar.clicked.connect(self._finalizar_vigencia)
        form.addWidget(boton_finalizar)

        linea_separadora = QFrame()
        linea_separadora.setFrameShape(QFrame.Shape.HLine)
        linea_separadora.setFrameShadow(QFrame.Shadow.Sunken)
        form.addWidget(linea_separadora)

        self.etiqueta_horas_semanales = QLabel()
        self.etiqueta_descuento = QLabel()
        form.addWidget(self.etiqueta_horas_semanales)
        form.addWidget(self.etiqueta_descuento)

        form.addStretch()
        splitter_superior.addWidget(panel_form)

        # Sin título (pedido de la clienta) — antes decía "Vista previa:
        # grilla operativa".
        grupo_grilla = QGroupBox()
        layout_grupo_grilla = QVBoxLayout(grupo_grilla)
        layout_grupo_grilla.setContentsMargins(0, 0, 0, 0)
        self.grilla = GrillaOperativaWidget(self.conn)
        self.grilla.fijar_modo("regular")
        self.grilla.activar_filtro_exclusivo_profesional(True)
        self.grilla.agrandar_panel_filtros(_ANCHO_PANEL_FILTROS_GRILLA)
        self.grilla.agrupar_dias_en_pares()
        self.grilla.mostrar_leyenda_colores(compacta=True)
        # Pedido explícito de la clienta ("hace un poquito mas grande el
        # cuadrito de las referencias a lo alto, hay lugar para
        # hacerlo"): "Referencias de colores" ya ocupa un lugar fijo
        # dentro del panel de Filtros (no crece ni se achica según su
        # propio contenido — lo determina el resto de los filtros de
        # arriba, con el sobrante yendo a un `addStretch()` interno), así
        # que agrandar la muestra no cambia el alto del panel: solo
        # reduce el hueco en blanco que quedaba entre el contenido y el
        # borde inferior del cuadro. Medido: con las 8 referencias de
        # Regulares (2 columnas, 4 filas) ese lugar fijo alcanza sin
        # comprimir nada hasta muestras de ~50px de alto — 26px se queda
        # con margen de sobra, "un poquito" más grande, no al límite.
        self.grilla.agrandar_muestras_leyenda(28, 26)
        # Sin título "Filtros" (pedido de la clienta) — cada filtro pasa a
        # nombrarse solo con "Filtro de ...", ver `renombrar_etiquetas_
        # filtro`.
        self.grilla.fijar_titulo_filtros("")
        self.grilla.renombrar_etiquetas_filtro()
        # El panel_form de al lado (con Días/Vigencia/3 botones) es más
        # alto que esta columna — sin esto, ese sobrante lo absorbía la
        # grilla (relleno en blanco debajo de la última hora); pasa el
        # estirado al cuadro "Detalle" para que la columna termine a la
        # misma altura que el formulario ("que quede parejo", pedido
        # explícito de la clienta), ver `dar_stretch_a_detalle`.
        self.grilla.dar_stretch_a_detalle()
        # Tope de alto IGUAL al que ya tiene hoy (sin cambiar nada visible
        # ahora): pedido explícito de la clienta para dejar la grilla
        # scrolleable de acá en adelante, por si el día de mañana hace
        # falta mostrar más horarios sin agrandar el panel — ver
        # `limitar_alto_grilla`/`alto_natural_grilla`.
        self.grilla.limitar_alto_grilla(self.grilla.alto_natural_grilla())
        layout_grupo_grilla.addWidget(self.grilla)
        # `limitar_alto_grilla` le pone un tope de alto a `self.grilla` —
        # sin este spacer, cuando el splitter le da a `grupo_grilla` más
        # alto del que ese tope permite usar, Qt centra `self.grilla`
        # dentro del sobrante en vez de dejarlo pegado arriba (mismo
        # mecanismo que el `addStretch()` de `GrillaOperativaWidget.
        # _armar_ui`, acá un nivel más afuera).
        layout_grupo_grilla.addStretch()
        splitter_superior.addWidget(grupo_grilla)

        splitter_superior.setStretchFactor(0, 0)
        splitter_superior.setStretchFactor(1, 1)
        layout.addWidget(splitter_superior)

        hoy = fecha_actual(self.conn)
        self.campo_vigencia_inicio.setDate(QDate(hoy.year, hoy.month, hoy.day))

        scroll.setWidget(contenido)
        # Pedido explícito de la clienta ("ampliá el tamaño de la tabla,
        # subiéndola arriba al límite de cuando termina el cuadro de
        # Detalle... y que llegue lo más abajo posible dentro de la
        # pantalla que se visualiza — solo tocá la tabla, nada del
        # resto"): antes `scroll` tenía `stretch=1` (se llevaba TODO el
        # alto sobrante de la ventana, quedando más alto que lo que su
        # propio contenido necesita — 585px contra un mínimo real de
        # 569px, medido con `contenido.minimumSizeHint()`) mientras la
        # tabla de abajo quedaba con un alto fijo de 3 filas nomás, sin
        # importar cuánta ventana sobrara debajo. Se invierte quién se
        # queda con el sobrante: `scroll` pasa a un alto FIJO, igual a lo
        # que su contenido realmente necesita (sin dejarle nada de más,
        # así el contenido de arriba — formulario, grilla, botones,
        # Detalle — no se mueve ni un pixel, "nada del resto"), y el
        # sobrante que eso libera se lo lleva la tabla de abajo (`stretch
        # =1` en `panel_tabla`, ver más abajo) — la tabla crece hasta
        # pegarse contra el borde de Detalle arriba y contra el borde de
        # la ventana abajo. Ya no hace falta ningún espaciador que
        # compense nada (`_ALTO_TITULO_PANEL_TABLA_REGULARES` deja de
        # usarse acá): no hay más hueco muerto que esconder, todo el
        # sobrante pasa a ser tabla de verdad.
        scroll.setFixedHeight(contenido.minimumSizeHint().height())
        # Guardados aparte: el `sizeHint()` calculado ACÁ (antes de que la
        # pantalla se muestre de verdad) no siempre coincide con el que
        # da el mismo widget una vez mostrado (mismo tipo de imprecisión
        # ya documentado en Aisladas para `alto_natural_grilla()` — el
        # offscreen platform de Qt no soporta `propagateSizeHints`) —
        # `showEvent` vuelve a fijar el alto con el valor ya asentado.
        self._scroll_superior = scroll
        self._contenido_superior = contenido
        layout_externo.addWidget(scroll)

        # Sin título (pedido de la clienta: "eliminá el título 'Horarios
        # reservados' así la tabla puede situarse un poco más arriba") —
        # el `QGroupBox` sigue existiendo (borde propio, `panelSolapa`),
        # solo pierde el título, mismo criterio que `grupo_grilla` de
        # arriba, que ya no tiene título desde una ronda anterior.
        panel_tabla = QGroupBox()
        panel_tabla.setObjectName("panelSolapa")
        layout_tabla = QVBoxLayout(panel_tabla)
        # Pedido explícito de la clienta ("las tablas tienen un espacio en
        # blanco arriba... más pegado al contenido que está arriba"): sin
        # margen superior, la tabla arranca pegada al borde de arriba del
        # cuadro en vez de dejar el margen default de Qt (9px) como hueco
        # en blanco antes del encabezado — el margen izquierdo/derecho/
        # inferior se queda igual, para no pegar el resto del contenido a
        # los otros tres bordes.
        layout_tabla.setContentsMargins(9, 0, 9, 9)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(9)
        self.tabla.setHorizontalHeaderLabels(
            [
                "Profesional", "Localidad", "Edificio", "Unidad", "Consultorio", "Día", "Horario",
                "Vigencia desde", "Vigencia hasta",
            ]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        # Antes `setFixedHeight` a 3 filas justas — pasa a `setMinimumHeight`
        # (mismo cálculo de `_alto_para_filas`, ahora como piso en vez de
        # techo) para que la tabla pueda crecer con `panel_tabla` sin dejar
        # de mostrar al menos esas 3 filas en una ventana chica. Sigue
        # siendo scrolleable sola si hay más filas de las que entran en el
        # alto que le toque, sea cual sea ese alto.
        self.tabla.setMinimumHeight(_alto_para_filas(self.tabla, _FILAS_VISIBLES_TABLA_INFERIOR_REGULARES))
        self._orden = OrdenTabla(self.tabla, self.actualizar)
        layout_tabla.addWidget(self.tabla, stretch=1)
        layout_externo.addWidget(panel_tabla, stretch=1)

        self._cargar_edificios()
        self._foco = instalar_enter_avanza_foco(
            [
                self.combo_profesional, self.combo_localidad, self.combo_edificio, self.combo_unidad,
                self.combo_consultorio, *(self._checks_dia[dia] for dia in _DIAS_RESERVA),
                self.spin_desde, self.spin_hasta,
                self.campo_vigencia_inicio, self.campo_vigencia_fin, boton_crear,
            ],
            parent=self,
        )

    def actualizar(self) -> None:
        """Sin profesional elegido, muestra todas las reservas regulares
        VIGENTES de todos los profesionales (no tiene sentido alargar la
        lista con lo que ya terminó); con uno elegido, se acota a las de
        ese profesional únicamente (incluida su historia, para poder
        revisarla). Orden por defecto: categoría del profesional (B, R,
        E, en ese orden fijo — no alfabético), número de profesional,
        día de la semana y hora de inicio del bloque — overridable
        haciendo click en el título de una columna (ver `OrdenTabla`)."""
        id_profesional_filtro = self.combo_profesional.currentData()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        todas = obtener_repositorio(self.conn, "ReservaRegular").listar()
        if id_profesional_filtro is not None:
            filtradas = [r for r in todas if r["IdProfesional"] == id_profesional_filtro]
        else:
            hoy = fecha_actual(self.conn).isoformat()
            filtradas = [r for r in todas if not r["VigenciaFin"] or r["VigenciaFin"] >= hoy]

        filas: list[tuple[sqlite3.Row, sqlite3.Row | None, sqlite3.Row | None]] = []
        for r in filtradas:
            profesional = repo_profesional.obtener(r["IdProfesional"])
            consultorio = self.conn.execute(
                "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS NombreEdificio, "
                "loc.Localidad AS DomicilioLocalidad "
                "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
                "LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad "
                "WHERE c.IdConsultorio = ?",
                (r["IdConsultorio"],),
            ).fetchone()
            filas.append((r, profesional, consultorio))
        filas.sort(key=lambda t: (
            _ORDEN_CATEGORIA_REGULAR.get(t[1]["CategoriaProfesional"], 99) if t[1] else 99,
            _numero_codigo(t[1]["IdCodigo"] if t[1] else None),
            DIAS_SEMANA.index(t[0]["DiaSemana"]),
            t[0]["HoraInicio"],
        ))
        if self._orden.columna is not None:
            filas.sort(key=self._clave_orden(self._orden.columna), reverse=not self._orden.ascendente)
        self._reservas = [t[0] for t in filas]

        self.tabla.setRowCount(len(filas))
        for fila_idx, (r, profesional, consultorio) in enumerate(filas):
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(_texto_profesional(profesional) if profesional else "?"))
            self.tabla.setItem(
                fila_idx, 1,
                QTableWidgetItem((consultorio["DomicilioLocalidad"] or "(Sin localidad)") if consultorio else "?"),
            )
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(consultorio["NombreEdificio"] if consultorio else "?"))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(consultorio["Departamento"] if consultorio else "?"))
            self.tabla.setItem(
                fila_idx, 4, item_numero(str(consultorio["NumeroConsultorio"]) if consultorio else "?"),
            )
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem(r["DiaSemana"]))
            self.tabla.setItem(fila_idx, 6, QTableWidgetItem(_fmt_horario(r["HoraInicio"], r["HoraFin"])))
            self.tabla.setItem(fila_idx, 7, QTableWidgetItem(_fmt_fecha(r["VigenciaInicio"])))
            self.tabla.setItem(fila_idx, 8, QTableWidgetItem(_fmt_fecha(r["VigenciaFin"])))
        self.tabla.resizeColumnsToContents()
        self.tabla.setColumnWidth(0, max(self.tabla.columnWidth(0), _ANCHO_COL_PROFESIONAL))
        self._sincronizar_grilla()

    @staticmethod
    def _clave_orden(columna: int):
        claves = {
            0: lambda t: _texto_profesional(t[1]) if t[1] else "",
            1: lambda t: (t[2]["DomicilioLocalidad"] or "") if t[2] else "",
            2: lambda t: (t[2]["NombreEdificio"] or "") if t[2] else "",
            3: lambda t: (t[2]["Departamento"] or "") if t[2] else "",
            4: lambda t: (t[2]["NumeroConsultorio"] if t[2] else 0),
            5: lambda t: DIAS_SEMANA.index(t[0]["DiaSemana"]),
            6: lambda t: t[0]["HoraInicio"],
            7: lambda t: t[0]["VigenciaInicio"] or "",
            8: lambda t: t[0]["VigenciaFin"] or "",
        }
        return claves[columna]

    def _cargar_edificios(self) -> None:
        """Localidad/Edificio fuerzan una elección explícita cuando hay
        más de una opción — "Seleccionar…" habilitado, en vez de quedarse
        en la primera opción sin que el operador la haya elegido a
        propósito."""
        localidad = self.combo_localidad.currentData()
        self.combo_edificio.blockSignals(True)
        self.combo_edificio.clear()
        if localidad is _SIN_ELEGIR:
            self.combo_edificio.blockSignals(False)
            self.combo_edificio.setEnabled(False)
            self._cargar_unidades()
            return
        opciones_edificio = _opciones_edificio(self.conn, localidad)
        if len(opciones_edificio) > 1:
            self.combo_edificio.addItem("Seleccionar…", None)
        for id_, nombre in opciones_edificio:
            self.combo_edificio.addItem(nombre, id_)
        self.combo_edificio.blockSignals(False)
        self.combo_edificio.setEnabled(len(opciones_edificio) > 1)
        self._cargar_unidades()

    def _cargar_unidades(self) -> None:
        _recargar_unidades(self.conn, self.combo_edificio, self.combo_unidad)
        self._cargar_consultorios()

    def _cargar_consultorios(self) -> None:
        _recargar_consultorios(self.conn, self.combo_unidad, self.combo_consultorio)
        self._sincronizar_grilla()

    def _seleccionar_ubicacion(self, id_consultorio: int) -> None:
        fila = self.conn.execute(
            "SELECT e.IdLocalidad, u.IdEdificio, c.IdUnidad FROM Consultorio c "
            "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "WHERE c.IdConsultorio = ?", (id_consultorio,),
        ).fetchone()
        if fila is None:
            return
        indice_localidad = self.combo_localidad.findData(fila["IdLocalidad"])
        if indice_localidad >= 0:
            self.combo_localidad.setCurrentIndex(indice_localidad)
        indice_edificio = self.combo_edificio.findData(fila["IdEdificio"])
        if indice_edificio >= 0:
            self.combo_edificio.setCurrentIndex(indice_edificio)
        indice_unidad = self.combo_unidad.findData(fila["IdUnidad"])
        if indice_unidad >= 0:
            self.combo_unidad.setCurrentIndex(indice_unidad)
        indice_consultorio = self.combo_consultorio.findData(id_consultorio)
        if indice_consultorio >= 0:
            self.combo_consultorio.setCurrentIndex(indice_consultorio)

    def _sincronizar_grilla(self) -> None:
        """Con un profesional elegido, la vista previa muestra su horario
        regular — acotada a las unidades (con todos sus consultorios) y a
        los días en los que ya tiene algo reservado (vacía para uno nuevo,
        sin nada reservado todavía), con su propia reserva pintada de
        azul. Con "Todos los profesionales" no tiene sentido acotar a
        nada — se saca cualquier filtro y queda la grilla completa (todas
        las localidades/edificios/unidades/consultorios), con los mismos
        criterios de colores que la pantalla de Grilla operativa. Se
        vuelve a calcular también en cada refresco de la tabla (después
        de cada alta/baja), así queda siempre al día de lo que el
        profesional ya tiene reservado antes de seguir cargando."""
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            self.grilla.filtrar_por_unidades(None)
            self.grilla.filtrar_por_dias(None)
            self.grilla.filtrar_por_pares_unidad_dia(None)
            self.grilla.filtrar_por_profesional(None)
        else:
            pares = pares_dia_unidad_con_reserva_vigente(self.conn, id_profesional)
            ids_unidad = sorted({u for _, u in pares})
            dias = sorted({d for d, _ in pares}, key=DIAS_SEMANA.index)
            self.grilla.filtrar_por_unidades(ids_unidad)
            self.grilla.filtrar_por_dias(dias)
            self.grilla.filtrar_por_pares_unidad_dia(pares)
            self.grilla.filtrar_por_profesional(id_profesional)
        self._actualizar_resumen_profesional(id_profesional)

    def _actualizar_resumen_profesional(self, id_profesional: int | None) -> None:
        # Sin "Horas aisladas mensuales" (pedido explícito de la clienta): en
        # Reservas regulares solo importan las horas regulares y el
        # descuento — ver `_PanelReservasAisladas._actualizar_resumen_
        # profesional` para la versión completa de esta pantalla hermana.
        resumen = calcular_resumen_profesional(self.conn, id_profesional)
        if resumen is None:
            self.etiqueta_horas_semanales.setText("Cant. horas regulares semanales: —")
            self.etiqueta_descuento.setText("% Descuento: —")
            return
        self.etiqueta_horas_semanales.setText(
            f"Cant. horas regulares semanales: {_fmt_horas(resumen.horas_semanales)}"
        )
        self.etiqueta_descuento.setText(f"% Descuento: {resumen.porcentaje_descuento:.1f}%")

    def _resetear_formulario(self) -> None:
        """Después de aplicar un cambio, deja el formulario listo y en
        blanco para cargar otro registro — aunque sea de otro
        profesional (el combo vuelve al placeholder en blanco, no queda
        pegado al que se acababa de cargar)."""
        self.combo_profesional.setCurrentIndex(0)
        if self.combo_localidad.count():
            self.combo_localidad.setCurrentIndex(0)
        self._cargar_edificios()
        for dia, check in self._checks_dia.items():
            check.setChecked(dia == "Lunes")
        self.spin_desde.setValue(9)
        self.spin_hasta.setValue(10)
        hoy = fecha_actual(self.conn)
        self.campo_vigencia_inicio.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.campo_vigencia_fin.setDate(_FECHA_SIN_DATO)
        self.combo_profesional.setFocus()

    def _dias_seleccionados(self) -> list[str]:
        return [dia for dia, check in self._checks_dia.items() if check.isChecked()]

    def _crear(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Crear reserva regular", "Elegí un profesional.")
            return
        id_consultorio = self.combo_consultorio.currentData()
        if id_consultorio is None:
            QMessageBox.warning(self, "Crear reserva regular", "Elegí localidad, edificio, unidad y consultorio.")
            return
        dias = self._dias_seleccionados()
        if not dias:
            QMessageBox.warning(self, "Crear reserva regular", "Elegí al menos un día.")
            return
        # Pedido explícito de la clienta: chequear una sola vez por carga
        # (no una vez por día elegido) si al profesional le falta alguna
        # llave para entrar al lugar de la reserva — ver `_confirmar_
        # llaves_faltantes`.
        faltantes = llaves_faltantes_para_reserva(self.conn, id_profesional=id_profesional, id_consultorio=id_consultorio)
        if faltantes and not _confirmar_llaves_faltantes(self, faltantes):
            return
        advertencias_totales: list[str] = []
        algun_dia_creado = False
        for dia in dias:
            creado, advertencias = self._crear_un_dia(dia)
            if creado:
                algun_dia_creado = True
                advertencias_totales.extend(f"{dia}: {a}" for a in advertencias)
        if not algun_dia_creado:
            return
        if advertencias_totales:
            QMessageBox.information(self, "Reserva creada", "Reserva creada con avisos:\n" + "\n".join(advertencias_totales))
        self._ofrecer_resolver_lista_espera(id_profesional)
        regenerar_si_corresponde(self.conn, id_profesional=id_profesional, periodo=periodo_actual(self.conn))
        self.conn.commit()
        self.actualizar()
        self._resetear_formulario()
        self._sincronizar_grilla()

    def _crear_un_dia(self, dia_semana: str, forzar: bool = False) -> tuple[bool, list[str]]:
        datos = dict(
            id_profesional=self.combo_profesional.currentData(),
            id_consultorio=self.combo_consultorio.currentData(),
            dia_semana=dia_semana,
            hora_inicio=self.spin_desde.value(),
            hora_fin=self.spin_hasta.value(),
            vigencia_inicio=self.campo_vigencia_inicio.date().toPython().isoformat(),
            vigencia_fin=(
                None if self.campo_vigencia_fin.date() == _FECHA_SIN_DATO
                else self.campo_vigencia_fin.date().toPython().isoformat()
            ),
            forzar=forzar,
        )
        try:
            _id, advertencias = crear_reserva_regular(self.conn, **datos)
        except ConflictoBloqueanteError as error:
            confirmacion = QMessageBox.question(
                self, "Conflictos detectados",
                f"{dia_semana}: {error}\n\n¿Crear la reserva de todos modos?",
            )
            if confirmacion == QMessageBox.StandardButton.Yes:
                return self._crear_un_dia(dia_semana, forzar=True)
            return False, []
        except ValueError as error:
            QMessageBox.warning(self, "Crear reserva regular", f"{dia_semana}: {error}")
            return False, []
        self.conn.commit()
        return True, advertencias

    def _ofrecer_resolver_lista_espera(self, id_profesional: int) -> None:
        """DC-10 §2.2 paso 5: confirmar la reserva regular en F16 tiene que
        poder cerrar el pedido de Lista de espera que la originó. Con un
        solo pedido Activo del profesional alcanza con preguntar; con más
        de uno queda a criterio manual (no hay forma de saber cuál de
        todos se acaba de cubrir)."""
        pedidos = obtener_repositorio(self.conn, "ListaEspera").listar(
            IdProfesional=id_profesional, Estado="Activo",
        )
        if len(pedidos) != 1:
            return
        respuesta = QMessageBox.question(
            self, "Lista de espera",
            "Este profesional tiene un pedido activo en Lista de espera. "
            "¿Lo marcás como resuelto?",
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            marcar_resuelto(self.conn, pedidos[0]["IdPedido"])
            self.conn.commit()

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._reservas[filas[0].row()]

    def _finalizar_registro(self, reserva: sqlite3.Row, fecha_fin: str) -> None:
        obtener_repositorio(self.conn, "ReservaRegular").actualizar(
            reserva["IdReservaRegular"], VigenciaFin=fecha_fin
        )
        regenerar_si_corresponde(
            self.conn, id_profesional=reserva["IdProfesional"], periodo=periodo_actual(self.conn),
        )
        self.conn.commit()

    def _finalizar_vigencia(self) -> None:
        """"Finalizar reserva a fin de mes": el caso clásico (95% de las
        bajas se cierran a fin de mes), no el día exacto en que se
        gestiona la baja."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            return
        hoy = fecha_actual(self.conn)
        fin_de_mes = ultimo_dia_mes(hoy.year, hoy.month)
        self._finalizar_registro(reserva, fin_de_mes.isoformat())
        self.actualizar()
        self.combo_profesional.setFocus()

    def _modificar_seleccionada(self) -> None:
        """No se edita la fila histórica in-place (podría desalinear una
        liquidación ya emitida que la haya usado): finaliza su vigencia
        hoy (no a fin de mes — acá la versión nueva arranca hoy mismo, y
        dejarla superpuesta con la vieja hasta fin de mes rompería la
        validación de solapamiento) y precarga el formulario con sus
        datos para dar de alta la versión nueva. El operador ajusta lo
        que haga falta y confirma con "Crear reserva regular", como
        cualquier alta."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            QMessageBox.warning(self, "Modificar reserva", "Elegí una fila de la tabla para modificar.")
            return
        self._finalizar_registro(reserva, fecha_actual(self.conn).isoformat())
        self.actualizar()

        indice_profesional = self.combo_profesional.findData(reserva["IdProfesional"])
        if indice_profesional >= 0:
            self.combo_profesional.setCurrentIndex(indice_profesional)
        self._seleccionar_ubicacion(reserva["IdConsultorio"])
        for dia, check in self._checks_dia.items():
            check.setChecked(dia == reserva["DiaSemana"])
        self.spin_desde.setValue(reserva["HoraInicio"])
        self.spin_hasta.setValue(reserva["HoraFin"])
        hoy = fecha_actual(self.conn)
        self.campo_vigencia_inicio.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.campo_vigencia_fin.setDate(_FECHA_SIN_DATO)
        self._sincronizar_grilla()


class _PanelReservasAisladas(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._reservas: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """Mismo motivo que en Reservas regulares: `setFocus()` durante la
        construcción no alcanza a "pegar" porque el QTabWidget contenedor
        todavía no está mostrado. De paso, vuelve a fijar el alto de
        `_scroll_superior` (ver esa misma solapa)."""
        super().showEvent(event)
        self._scroll_superior.setFixedHeight(self._contenido_superior.minimumSizeHint().height())
        self._orden.reiniciar()
        self.actualizar()
        self.combo_profesional.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        # Mismo motivo que Regulares: sin espaciado default de Qt entre
        # `scroll` y la tabla de abajo, para una separación mínima.
        layout_externo.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        contenido = QWidget()
        contenido.setObjectName("panelSolapa")
        layout = QVBoxLayout(contenido)
        # Sin margen propio (mismo motivo que en Reservas regulares): le
        # deja más alto disponible a esta columna antes de tener que
        # scrollear, espacio que acá se usa para mostrar más filas en la
        # tabla de abajo sin perder de vista "Detalle"/"% Descuento".
        layout.setContentsMargins(0, 0, 0, 0)
        splitter_superior = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        # Margen de arriba en `_ALTO_TITULO_FILTROS` (no en 0): mismo
        # motivo que en Reservas regulares — "Profesional" arranca a la
        # misma altura que "Filtro de localidad", pedido explícito de la
        # clienta.
        form.setContentsMargins(9, _ALTO_TITULO_FILTROS, 9, 0)
        self.combo_profesional = QComboBox()
        self.combo_profesional.setMinimumWidth(_ANCHO_COMBO_PROFESIONAL)
        self.combo_profesional.addItem("Todos los profesionales", None)
        for id_, etiqueta in _opciones_profesional(self.conn, _CATEGORIAS_AISLADAS):
            self.combo_profesional.addItem(etiqueta, id_)
        habilitar_busqueda_profesional(self.combo_profesional)
        self.combo_profesional.currentIndexChanged.connect(self.actualizar)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_localidad = QComboBox()
        opciones_localidad = _opciones_localidad(self.conn)
        if len(opciones_localidad) > 1:
            self.combo_localidad.addItem("Seleccionar…", _SIN_ELEGIR)
        for valor, etiqueta in opciones_localidad:
            self.combo_localidad.addItem(etiqueta, valor)
        self.combo_localidad.setEnabled(len(opciones_localidad) > 1)
        self.combo_localidad.currentIndexChanged.connect(self._cargar_edificios)
        form.addWidget(QLabel("Localidad"))
        form.addWidget(self.combo_localidad)

        self.combo_edificio = QComboBox()
        self.combo_edificio.currentIndexChanged.connect(self._cargar_unidades)
        form.addWidget(QLabel("Edificio"))
        form.addWidget(self.combo_edificio)

        self.combo_unidad = QComboBox()
        self.combo_unidad.currentIndexChanged.connect(self._cargar_consultorios)
        form.addWidget(QLabel("Unidad"))
        form.addWidget(self.combo_unidad)

        self.combo_consultorio = QComboBox()
        self.combo_consultorio.currentIndexChanged.connect(self._sincronizar_grilla)
        form.addWidget(QLabel("Consultorio"))
        form.addWidget(self.combo_consultorio)

        self.campo_fecha = QDateEdit()
        self.campo_fecha.setDisplayFormat(_FORMATO_FECHA_DIA)
        self.campo_fecha.setLocale(_LOCALE_ES)
        self.campo_fecha.setCalendarPopup(True)
        form.addWidget(QLabel("Fecha"))
        form.addWidget(self.campo_fecha)

        fila_horario = QHBoxLayout()
        self.spin_desde = _SpinHorario()
        self.spin_desde.setRange(0, 23)
        self.spin_desde.setSingleStep(0.5)
        self.spin_desde.setValue(9)
        self.spin_hasta = _SpinHorario()
        self.spin_hasta.setRange(0.5, 24)
        self.spin_hasta.setSingleStep(0.5)
        self.spin_hasta.setValue(10)
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_desde)
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hasta)
        form.addLayout(fila_horario)

        self.casilla_recargo = QCheckBox("Aplica recargo")
        form.addWidget(self.casilla_recargo)

        # Salto de línea a mano (QCheckBox no ajusta el texto solo, a
        # diferencia de un QLabel): pedido de la clienta, la columna del
        # formulario quedaba mucho más ancha que la del panel de Filtros
        # de al lado por culpa de este texto largo en una sola línea.
        self.casilla_reubicacion = QCheckBox(
            "Es reubicación (compensa una ausencia\ndel profesional, no genera cargo)"
        )
        self.casilla_reubicacion.stateChanged.connect(self._alternar_reubicacion)
        form.addWidget(self.casilla_reubicacion)

        self.contenedor_reubicacion = QWidget()
        layout_reubicacion = QVBoxLayout(self.contenedor_reubicacion)
        layout_reubicacion.setContentsMargins(0, 0, 0, 0)
        layout_reubicacion.addWidget(QLabel("Horario que no va a usar"))
        self.combo_horario_no_usado = QComboBox()
        layout_reubicacion.addWidget(self.combo_horario_no_usado)
        layout_reubicacion.addWidget(QLabel("Fecha que falta"))
        self.campo_fecha_ausencia = QDateEdit()
        self.campo_fecha_ausencia.setDisplayFormat(_FORMATO_FECHA)
        self.campo_fecha_ausencia.setCalendarPopup(True)
        layout_reubicacion.addWidget(self.campo_fecha_ausencia)
        self.contenedor_reubicacion.setVisible(False)
        form.addWidget(self.contenedor_reubicacion)

        boton_crear = QPushButton("Crear reserva aislada")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.setStyleSheet(_ESTILO_BOTON_AISLADAS_ALTO)
        boton_crear.clicked.connect(self._crear)
        form.addWidget(boton_crear)
        boton_modificar = QPushButton("Modificar reserva")
        boton_modificar.setObjectName("botonSecundario")
        boton_modificar.setStyleSheet(_ESTILO_BOTON_AISLADAS_ALTO)
        boton_modificar.clicked.connect(self._modificar_seleccionada)
        form.addWidget(boton_modificar)
        boton_cancelar = QPushButton("Cancelar reserva")
        boton_cancelar.setObjectName("botonSecundario")
        boton_cancelar.setStyleSheet(_ESTILO_BOTON_AISLADAS_ALTO)
        boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(boton_cancelar)

        linea_separadora = QFrame()
        linea_separadora.setFrameShape(QFrame.Shape.HLine)
        linea_separadora.setFrameShadow(QFrame.Shadow.Sunken)
        form.addWidget(linea_separadora)

        self.etiqueta_horas_aisladas = QLabel()
        form.addWidget(self.etiqueta_horas_aisladas)

        form.addStretch()
        splitter_superior.addWidget(panel_form)

        # Sin título (pedido de la clienta) — antes decía "Vista previa:
        # grilla operativa".
        grupo_grilla = QGroupBox()
        layout_grupo_grilla = QVBoxLayout(grupo_grilla)
        layout_grupo_grilla.setContentsMargins(0, 0, 0, 0)
        # Sin espaciado default de Qt (6px) entre la grilla y "Detalle:"
        # (pedido explícito de la clienta: "el título detalle... subilo
        # un poco para que haya una separación mínima con la grilla") —
        # el hueco que queda ahora (borde de `self.grilla` nomás) es el
        # mínimo posible, no hace falta compensar nada más abajo porque
        # acá no hay ningún mecanismo de "scroll que se lleva lo
        # sobrante" de por medio, a diferencia de `layout_externo` más
        # abajo.
        layout_grupo_grilla.setSpacing(0)
        self.grilla = GrillaOperativaWidget(self.conn)
        self.grilla.fijar_modo("aislada")
        self.grilla.activar_filtro_exclusivo_profesional(True)
        self.grilla.agrandar_panel_filtros(_ANCHO_PANEL_FILTROS_GRILLA)
        self.grilla.agrupar_dias_en_pares()
        self.grilla.mostrar_leyenda_colores(compacta=True)
        # Sin título "Filtros" (pedido de la clienta) — cada filtro pasa a
        # nombrarse solo con "Filtro de ...", ver `renombrar_etiquetas_
        # filtro`.
        self.grilla.fijar_titulo_filtros("")
        self.grilla.renombrar_etiquetas_filtro()
        # "Detalle" pasa a ocupar todo el ancho de esta grilla (Filtros +
        # grid juntos), debajo de todo, en vez de la columna angosta de
        # la grilla nomás — pedido explícito de la clienta ("en regulares
        # no porque no entra", así que esto es puntual de Aisladas). Sale
        # de `self.grilla` con `extraer_detalle` ANTES de medir el alto
        # natural de la columna (ver justo abajo): si se sacara después,
        # ese alto natural todavía arrastraría el de "Detalle", que de
        # todos modos se saca a continuación.
        etiqueta_detalle, texto_detalle = self.grilla.extraer_detalle()
        # La grilla se muestra COMPLETA, sin recortar (pedido explícito
        # de la clienta: "se ve cortada... dale mas alta de manera que se
        # visualice completa") — el tope que se le pone es IGUAL a su
        # propio alto natural (mismo criterio "identidad" que Reservas
        # regulares, ver `_PanelReservasRegulares`), así que no recorta
        # nada hoy; de paso queda scrolleable, por si el día de mañana
        # hace falta mostrar más horarios sin agrandar el panel.
        alto_grilla = self.grilla.alto_natural_grilla() + _AJUSTE_ALTO_GRILLA_AISLADAS
        # Guardado aparte (no solo pasado a `limitar_alto_grilla`): el
        # `sizeHint()` detrás de `alto_natural_grilla()` deja de ser
        # estable una vez aplicado el tope y agrandada la leyenda más
        # abajo — volver a llamarlo después de construir la pantalla (ej.
        # desde un test) puede devolver otro valor. Este atributo es el
        # que realmente se usó.
        self._alto_grilla_aplicado = alto_grilla
        self.grilla.limitar_alto_grilla(alto_grilla)
        # El panel de Filtros de al lado (con "Referencias de colores")
        # queda más bajo que la grilla ahora que esta se ve completa —
        # pedido explícito de la clienta: ese sobrante no se deja como
        # hueco en blanco al final (lo que haría solo el `addStretch()`
        # de `layout_filtros`), se reparte entre los "cuadraditos" de la
        # leyenda para que crezcan y el panel termine exactamente a la
        # misma altura que el borde inferior de la grilla.
        alto_filtros = self.grilla.alto_natural_filtros()
        diferencia = alto_grilla - alto_filtros
        # Si la grilla no queda más alta que Filtros (ej. una base con
        # pocos consultorios cargados), no hay nada que repartir — se
        # deja el tamaño compacto de siempre en vez de achicar las
        # muestras con una diferencia negativa.
        if diferencia > 0:
            ancho_muestra, alto_muestra = self.grilla.tamano_muestra_leyenda()
            alto_muestra += diferencia // _FILAS_LEYENDA_AISLADA
            self.grilla.agrandar_muestras_leyenda(ancho_muestra, alto_muestra)
        layout_grupo_grilla.addWidget(self.grilla)
        layout_grupo_grilla.addWidget(etiqueta_detalle)
        layout_grupo_grilla.addWidget(texto_detalle)
        texto_detalle.setMaximumHeight(_ALTO_DETALLE_AISLADAS)
        # Sin esto, el sobrante de alto que el splitter le da a
        # `grupo_grilla` (para igualar el alto de `panel_form`, más alto
        # que el contenido real de acá) lo repartía Qt en `etiqueta_
        # detalle` — el único item de este layout sin un tope propio,
        # ya que `self.grilla` y `texto_detalle` sí lo tienen — inflando
        # el label "Detalle:" a un alto absurdo y empujando el cuadro de
        # texto hacia abajo, en vez de pegarlo justo debajo de la grilla
        # como pidió la clienta. Mismo mecanismo/mismo arreglo que el
        # `addStretch()` de `GrillaOperativaWidget._armar_ui`.
        layout_grupo_grilla.addStretch()
        splitter_superior.addWidget(grupo_grilla)

        splitter_superior.setStretchFactor(0, 0)
        splitter_superior.setStretchFactor(1, 1)
        layout.addWidget(splitter_superior)

        hoy = fecha_actual(self.conn)
        self.campo_fecha.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.campo_fecha_ausencia.setDate(QDate(hoy.year, hoy.month, hoy.day))

        scroll.setWidget(contenido)
        # Mismo mecanismo que Reservas regulares (ver esa solapa para el
        # detalle completo): `scroll` pasa de `stretch=1` a un alto FIJO
        # igual a lo que su contenido realmente necesita
        # (`contenido.minimumSizeHint()`, sin dejarle nada de más), así
        # el sobrante de la ventana se lo lleva la tabla de abajo en vez
        # de quedar invisible dentro del scroll — "Reservas aisladas"
        # sigue quedando FUERA de este `QScrollArea` para que su título y
        # un par de filas siempre se vean sin scrollear todo el panel.
        scroll.setFixedHeight(contenido.minimumSizeHint().height())
        # Guardados aparte para volver a fijar el alto en `showEvent` (ver
        # esa solapa en Regulares) — el `minimumSizeHint()` de acá puede
        # quedar unos pixels desincronizado hasta el primer show real.
        self._scroll_superior = scroll
        self._contenido_superior = contenido
        layout_externo.addWidget(scroll)

        # Sin título (mismo pedido y mismo criterio que Regulares, ver
        # esa solapa) — la tabla sube lo más posible sin tocar nada de
        # lo que está arriba (form + grilla + Detalle).
        panel_tabla = QGroupBox()
        panel_tabla.setObjectName("panelSolapa")
        layout_tabla = QVBoxLayout(panel_tabla)
        # Pedido explícito de la clienta ("las tablas tienen un espacio en
        # blanco arriba... más pegado al contenido que está arriba"): sin
        # margen superior, la tabla arranca pegada al borde de arriba del
        # cuadro en vez de dejar el margen default de Qt (9px) como hueco
        # en blanco antes del encabezado — el margen izquierdo/derecho/
        # inferior se queda igual, para no pegar el resto del contenido a
        # los otros tres bordes.
        layout_tabla.setContentsMargins(9, 0, 9, 9)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(11)
        self.tabla.setHorizontalHeaderLabels(
            [
                "Profesional", "Localidad", "Edificio", "Unidad", "Consultorio", "Día", "Fecha", "Horario",
                "Reubicación", "Estado", "Valor",
            ]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        # Antes `setFixedHeight` a 4 filas justas — mismo cambio que
        # Regulares, pasa a `setMinimumHeight` (piso, no techo) para que
        # la tabla crezca con `panel_tabla` y use el sobrante que antes
        # se quedaba invisible dentro de `scroll`.
        self.tabla.setMinimumHeight(_alto_para_filas(self.tabla, _FILAS_VISIBLES_TABLA_INFERIOR_AISLADAS))
        self._orden = OrdenTabla(self.tabla, self.actualizar)
        layout_tabla.addWidget(self.tabla, stretch=1)
        layout_externo.addWidget(panel_tabla, stretch=1)

        self._cargar_edificios()
        self._foco = instalar_enter_avanza_foco(
            [
                self.combo_profesional, self.combo_localidad, self.combo_edificio, self.combo_unidad,
                self.combo_consultorio, self.campo_fecha, self.spin_desde, self.spin_hasta,
                self.casilla_recargo, self.casilla_reubicacion, self.combo_horario_no_usado,
                self.campo_fecha_ausencia, boton_crear,
            ],
            parent=self,
        )

    def _cargar_edificios(self) -> None:
        """Mismo criterio que en Reservas regulares: Localidad/Edificio
        fuerzan una elección explícita cuando hay más de una opción —
        "Seleccionar…" habilitado, en vez de quedarse en la primera
        opción sin que el operador la haya elegido a propósito."""
        localidad = self.combo_localidad.currentData()
        self.combo_edificio.blockSignals(True)
        self.combo_edificio.clear()
        if localidad is _SIN_ELEGIR:
            self.combo_edificio.blockSignals(False)
            self.combo_edificio.setEnabled(False)
            self._cargar_unidades()
            return
        opciones_edificio = _opciones_edificio(self.conn, localidad)
        if len(opciones_edificio) > 1:
            self.combo_edificio.addItem("Seleccionar…", None)
        for id_, nombre in opciones_edificio:
            self.combo_edificio.addItem(nombre, id_)
        self.combo_edificio.blockSignals(False)
        self.combo_edificio.setEnabled(len(opciones_edificio) > 1)
        self._cargar_unidades()

    def _cargar_unidades(self) -> None:
        _recargar_unidades(self.conn, self.combo_edificio, self.combo_unidad)
        self._cargar_consultorios()

    def _cargar_consultorios(self) -> None:
        _recargar_consultorios(self.conn, self.combo_unidad, self.combo_consultorio)
        self._sincronizar_grilla()

    def _seleccionar_ubicacion(self, id_consultorio: int) -> None:
        fila = self.conn.execute(
            "SELECT e.IdLocalidad, u.IdEdificio, c.IdUnidad FROM Consultorio c "
            "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "WHERE c.IdConsultorio = ?", (id_consultorio,),
        ).fetchone()
        if fila is None:
            return
        indice_localidad = self.combo_localidad.findData(fila["IdLocalidad"])
        if indice_localidad >= 0:
            self.combo_localidad.setCurrentIndex(indice_localidad)
        indice_edificio = self.combo_edificio.findData(fila["IdEdificio"])
        if indice_edificio >= 0:
            self.combo_edificio.setCurrentIndex(indice_edificio)
        indice_unidad = self.combo_unidad.findData(fila["IdUnidad"])
        if indice_unidad >= 0:
            self.combo_unidad.setCurrentIndex(indice_unidad)
        indice_consultorio = self.combo_consultorio.findData(id_consultorio)
        if indice_consultorio >= 0:
            self.combo_consultorio.setCurrentIndex(indice_consultorio)

    def _sincronizar_grilla(self) -> None:
        """Mismo criterio que en Reservas regulares, pero considerando
        también las aisladas del profesional (puede no tener nunca una
        reserva regular, ej. categoría A): acotada a las unidades y días
        en los que ya tiene algo reservado, con su propia reserva
        pintada de azul — en modo "Reservas aisladas" porque acá
        interesa ver qué está libre AHORA, no los conflictos futuros. Con
        "Todos los profesionales" no tiene sentido acotar a nada — se
        saca cualquier filtro y queda la grilla completa."""
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            self.grilla.filtrar_por_unidades(None)
            self.grilla.filtrar_por_dias(None)
            self.grilla.filtrar_por_pares_unidad_dia(None)
            self.grilla.filtrar_por_profesional(None)
        else:
            pares = pares_dia_unidad_con_reserva(self.conn, id_profesional)
            ids_unidad = sorted({u for _, u in pares})
            dias = sorted({d for d, _ in pares}, key=DIAS_SEMANA.index)
            self.grilla.filtrar_por_unidades(ids_unidad)
            self.grilla.filtrar_por_dias(dias)
            self.grilla.filtrar_por_pares_unidad_dia(pares)
            self.grilla.filtrar_por_profesional(id_profesional)
        self._actualizar_resumen_profesional(id_profesional)
        if self.casilla_reubicacion.isChecked():
            self._cargar_horarios_no_usados()

    def _actualizar_resumen_profesional(self, id_profesional: int | None) -> None:
        # Sin "Horas regulares semanales" ni "% Descuento" (pedido
        # explícito de la clienta, en dos vueltas): en Reservas aisladas
        # solo importa "Horas aisladas mensuales" — ver
        # `_PanelReservasRegulares._actualizar_resumen_profesional` para
        # la versión de la pantalla hermana (horas regulares + %
        # descuento, sin horas aisladas).
        resumen = calcular_resumen_profesional(self.conn, id_profesional)
        if resumen is None:
            self.etiqueta_horas_aisladas.setText("Cant. horas aisladas mensuales: —")
            return
        self.etiqueta_horas_aisladas.setText(
            f"Cant. horas aisladas mensuales: {_fmt_horas(resumen.horas_aisladas_mensuales)}"
        )

    def _alternar_reubicacion(self) -> None:
        marcado = self.casilla_reubicacion.isChecked()
        self.contenedor_reubicacion.setVisible(marcado)
        if marcado:
            self._cargar_horarios_no_usados()

    def _cargar_horarios_no_usados(self) -> None:
        """Al marcar "Es reubicación", ofrece elegir cuál de los horarios
        regulares vigentes del profesional no va a usar esta vez — para
        dejarlo registrado como Ausencia de ese consultorio en esa fecha
        puntual (así queda libre para que otro profesional lo tome como
        aislada), sin afectar la reserva regular ni la grilla visual."""
        id_profesional = self.combo_profesional.currentData()
        self.combo_horario_no_usado.clear()
        self.combo_horario_no_usado.addItem("Sin especificar", None)
        for id_consultorio, etiqueta in _opciones_horario_regular(self.conn, id_profesional):
            self.combo_horario_no_usado.addItem(etiqueta, id_consultorio)

    def _resetear_formulario(self) -> None:
        """Igual que en Reservas regulares: después de aplicar un cambio,
        deja el formulario listo y en blanco para cargar otro registro,
        aunque sea de otro profesional."""
        self.combo_profesional.setCurrentIndex(0)
        if self.combo_localidad.count():
            self.combo_localidad.setCurrentIndex(0)
        self._cargar_edificios()
        self.spin_desde.setValue(9)
        self.spin_hasta.setValue(10)
        hoy = fecha_actual(self.conn)
        self.campo_fecha.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.campo_fecha_ausencia.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.casilla_recargo.setChecked(False)
        self.casilla_reubicacion.setChecked(False)

    def _valor_reserva(self, reserva: sqlite3.Row, valor_hora_aislada: float, recargo_pct: float) -> str:
        """Vacío si la reserva cae en un período posterior al actual —
        todavía no corresponde mostrarle un valor de facturación."""
        if reserva["Fecha"][:7] > periodo_actual(self.conn):
            return ""
        if reserva["EsReubicacion"]:
            return formatear_moneda(0.0)
        monto = (reserva["HoraFin"] - reserva["HoraInicio"]) * valor_hora_aislada
        if reserva["AplicaRecargo"]:
            monto *= 1 + recargo_pct / 100
        return formatear_moneda(monto)

    def actualizar(self) -> None:
        """Sin profesional elegido, muestra todas las reservas aisladas de
        todos los profesionales; con uno elegido, se acota a las de ese
        profesional únicamente (incluida su historia — canceladas
        incluidas — para poder revisarla). Orden por defecto: categoría
        del profesional (R, A, en ese orden fijo — no alfabético), número
        de profesional, fecha y hora de inicio — overridable haciendo
        click en el título de una columna (ver `OrdenTabla`)."""
        id_profesional_filtro = self.combo_profesional.currentData()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        todas = obtener_repositorio(self.conn, "ReservaAislada").listar()
        if id_profesional_filtro is not None:
            filtradas = [r for r in todas if r["IdProfesional"] == id_profesional_filtro]
        else:
            filtradas = todas

        cfg = self.conn.execute(
            "SELECT RecargoPorcentajeAisladas FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        recargo_pct = cfg["RecargoPorcentajeAisladas"] if cfg else 0.0

        filas: list[tuple[sqlite3.Row, sqlite3.Row | None, sqlite3.Row | None]] = []
        for r in filtradas:
            profesional = repo_profesional.obtener(r["IdProfesional"])
            consultorio = self.conn.execute(
                "SELECT c.NumeroConsultorio, c.ValorHoraAisladaActual, u.Departamento, "
                "e.Nombre AS NombreEdificio, loc.Localidad AS DomicilioLocalidad FROM Consultorio c "
                "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
                "LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad "
                "WHERE c.IdConsultorio = ?",
                (r["IdConsultorio"],),
            ).fetchone()
            filas.append((r, profesional, consultorio))
        filas.sort(key=lambda t: (
            _ORDEN_CATEGORIA_AISLADA.get(t[1]["CategoriaProfesional"], 99) if t[1] else 99,
            _numero_codigo(t[1]["IdCodigo"] if t[1] else None),
            t[0]["Fecha"],
            t[0]["HoraInicio"],
        ))
        if self._orden.columna is not None:
            filas.sort(key=self._clave_orden(self._orden.columna), reverse=not self._orden.ascendente)
        self._reservas = [t[0] for t in filas]

        self.tabla.setRowCount(len(filas))
        for fila_idx, (r, profesional, consultorio) in enumerate(filas):
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(_texto_profesional(profesional) if profesional else "?"))
            self.tabla.setItem(
                fila_idx, 1,
                QTableWidgetItem((consultorio["DomicilioLocalidad"] or "(Sin localidad)") if consultorio else "?"),
            )
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(consultorio["NombreEdificio"] if consultorio else "?"))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(consultorio["Departamento"] if consultorio else "?"))
            self.tabla.setItem(
                fila_idx, 4, item_numero(str(consultorio["NumeroConsultorio"]) if consultorio else "?"),
            )
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem(fecha_a_dia_semana(date.fromisoformat(r["Fecha"]))))
            self.tabla.setItem(fila_idx, 6, QTableWidgetItem(_fmt_fecha(r["Fecha"])))
            self.tabla.setItem(fila_idx, 7, QTableWidgetItem(_fmt_horario(r["HoraInicio"], r["HoraFin"])))
            self.tabla.setItem(fila_idx, 8, QTableWidgetItem("Sí" if r["EsReubicacion"] else "No"))
            self.tabla.setItem(fila_idx, 9, QTableWidgetItem(r["Estado"]))
            valor_hora = consultorio["ValorHoraAisladaActual"] if consultorio else 0.0
            self.tabla.setItem(fila_idx, 10, item_numero(self._valor_reserva(r, valor_hora, recargo_pct)))
        self.tabla.resizeColumnsToContents()
        self.tabla.setColumnWidth(0, max(self.tabla.columnWidth(0), _ANCHO_COL_PROFESIONAL))
        self._sincronizar_grilla()
        self.grilla.actualizar()

    @staticmethod
    def _clave_orden(columna: int):
        claves = {
            0: lambda t: _texto_profesional(t[1]) if t[1] else "",
            1: lambda t: (t[2]["DomicilioLocalidad"] or "") if t[2] else "",
            2: lambda t: (t[2]["NombreEdificio"] or "") if t[2] else "",
            3: lambda t: (t[2]["Departamento"] or "") if t[2] else "",
            4: lambda t: (t[2]["NumeroConsultorio"] if t[2] else 0),
            5: lambda t: date.fromisoformat(t[0]["Fecha"]).weekday(),
            6: lambda t: t[0]["Fecha"],
            7: lambda t: t[0]["HoraInicio"],
            8: lambda t: bool(t[0]["EsReubicacion"]),
            9: lambda t: t[0]["Estado"],
            10: lambda t: t[0]["HoraFin"] - t[0]["HoraInicio"],
        }
        return claves[columna]

    def _crear(self, forzar: bool = False) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Crear reserva aislada", "Elegí un profesional.")
            return
        id_consultorio = self.combo_consultorio.currentData()
        if id_consultorio is None:
            QMessageBox.warning(self, "Crear reserva aislada", "Elegí localidad, edificio, unidad y consultorio.")
            return
        fecha = self.campo_fecha.date().toPython().isoformat()
        if not forzar and not confirmar_si_fecha_es_mes_anterior(self, self.conn, fecha):
            return
        # Mismo criterio que Reservas regulares (ver esa solapa): se
        # chequea una sola vez, no en cada reintento con `forzar=True`
        # (ya se confirmó, o no hacía falta, la primera vez).
        if not forzar:
            faltantes = llaves_faltantes_para_reserva(self.conn, id_profesional=id_profesional, id_consultorio=id_consultorio)
            if faltantes and not _confirmar_llaves_faltantes(self, faltantes):
                return
        datos = dict(
            id_profesional=id_profesional,
            id_consultorio=id_consultorio,
            fecha=fecha,
            hora_inicio=self.spin_desde.value(),
            hora_fin=self.spin_hasta.value(),
            aplica_recargo=self.casilla_recargo.isChecked(),
            es_reubicacion=self.casilla_reubicacion.isChecked(),
            forzar=forzar,
        )
        try:
            _id, advertencias = crear_reserva_aislada(self.conn, **datos)
        except ConflictoBloqueanteError as error:
            confirmacion = QMessageBox.question(
                self, "Conflictos detectados",
                f"{error}\n\n¿Crear la reserva de todos modos?",
            )
            if confirmacion == QMessageBox.StandardButton.Yes:
                self._crear(forzar=True)
            return
        except ValueError as error:
            QMessageBox.warning(self, "Crear reserva aislada", str(error))
            return
        self.conn.commit()
        if datos["es_reubicacion"]:
            self._registrar_ausencia_por_reubicacion(id_profesional, fecha, _id)
        if advertencias:
            QMessageBox.information(self, "Reserva creada", "Reserva creada con avisos:\n" + "\n".join(advertencias))
        self._copiar_mensaje_detalle(datos["id_profesional"], fecha)
        self.actualizar()
        self._resetear_formulario()
        self._sincronizar_grilla()

    def _registrar_ausencia_por_reubicacion(self, id_profesional: int, fecha_aislada: str, id_reserva_aislada: int) -> None:
        """Si al marcar "Es reubicación" el operador indicó cuál de los
        horarios regulares del profesional no va a usar, deja registrada
        la Ausencia de ese consultorio en la fecha indicada — vinculada a
        la reserva aislada que la originó, así queda libre para que otro
        profesional lo tome como aislada, sin afectar la reserva regular
        ni la grilla visual (mismo criterio que ya usa la pantalla de
        Ausencias)."""
        id_consultorio_no_usado = self.combo_horario_no_usado.currentData()
        if id_consultorio_no_usado is None:
            return
        fecha_ausencia = self.campo_fecha_ausencia.date().toPython().isoformat()
        crear_ausencia(
            self.conn, id_profesional=id_profesional, fecha_desde=fecha_ausencia, fecha_hasta=fecha_ausencia,
            id_consultorio=id_consultorio_no_usado, motivo="Reubicación",
            observacion=f"Compensada por la reserva aislada del {fecha_aislada}",
            id_reserva_aislada=id_reserva_aislada,
        )
        self.conn.commit()

    def _copiar_mensaje_detalle(self, id_profesional: int, fecha: str) -> None:
        """DC-02/DC-03/DC-04: confirmar, cancelar o modificar una reserva
        aislada carga sola el mensaje de detalle al portapapeles — sin
        reemplazar la posibilidad de volver a generarlo a mano desde el
        Centro de mensajería."""
        try:
            texto = mensaje_detalle_reserva_aislada(self.conn, id_profesional=id_profesional, periodo=fecha[:7])
        except ValueError:
            return
        QGuiApplication.clipboard().setText(texto)

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._reservas[filas[0].row()]

    def _cancelar_registro(self, reserva: sqlite3.Row, titulo: str) -> bool:
        try:
            requiere_aviso = cancelar_reserva_aislada(self.conn, reserva["IdReservaAislada"])
        except ValueError as error:
            QMessageBox.warning(self, titulo, str(error))
            return False
        self.conn.commit()
        if requiere_aviso:
            QMessageBox.information(self, titulo, "Cancelada el mismo día: avisar al profesional.")
        self._copiar_mensaje_detalle(reserva["IdProfesional"], reserva["Fecha"])
        self.actualizar()
        return True

    def _cancelar(self) -> None:
        reserva = self._fila_seleccionada()
        if reserva is None:
            return
        if self._cancelar_registro(reserva, "Cancelar reserva"):
            self.combo_profesional.setFocus()

    def _modificar_seleccionada(self) -> None:
        """Mismo criterio que en Reservas regulares: no se edita la fila
        histórica in-place (podría desalinear una liquidación ya
        emitida que la haya usado) — se cancela la reserva aislada
        seleccionada (queda su historial, no se borra) y se precarga el
        formulario con sus datos para dar de alta la versión corregida.
        El operador ajusta lo que haga falta (ej. una hora más de las
        que le habían encargado en un principio) y confirma con "Crear
        reserva aislada", como cualquier alta."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            QMessageBox.warning(self, "Modificar reserva", "Elegí una fila de la tabla para modificar.")
            return
        if not self._cancelar_registro(reserva, "Modificar reserva"):
            return

        indice_profesional = self.combo_profesional.findData(reserva["IdProfesional"])
        if indice_profesional >= 0:
            self.combo_profesional.setCurrentIndex(indice_profesional)
        self._seleccionar_ubicacion(reserva["IdConsultorio"])
        self.campo_fecha.setDate(QDate.fromString(reserva["Fecha"], "yyyy-MM-dd"))
        self.spin_desde.setValue(reserva["HoraInicio"])
        self.spin_hasta.setValue(reserva["HoraFin"])
        self.casilla_recargo.setChecked(bool(reserva["AplicaRecargo"]))
        self.casilla_reubicacion.setChecked(bool(reserva["EsReubicacion"]))
        self._sincronizar_grilla()
