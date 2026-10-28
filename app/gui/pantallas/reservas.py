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

from PySide6.QtCore import QDate, QEvent, QLocale, QObject, QTimer
from PySide6.QtGui import QGuiApplication, QValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.dialogos import confirmar_datos_antes_de_crear, confirmar_si_fecha_es_mes_anterior
from app.gui.widgets.eliminar_tecla import instalar_eliminar_con_tecla
from app.gui.widgets.fecha import aplicar_color_sabado_negro, instalar_flechas_cambian_fecha_completa
from app.gui.widgets.foco import excluir_tabla_del_tab
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.grilla_operativa import (
    GrillaOperativaWidget,
    pares_dia_unidad_con_reserva,
    pares_dia_unidad_con_reserva_vigente,
)
from app.gui.widgets.items_tabla import item_numero
from app.gui.widgets.orden_tabla import OrdenTabla, clave_orden_codigo, clave_orden_profesional
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.pdf.estilos import clave_orden_unidad
from app.negocio.ausencias import crear_ausencia
from app.negocio.dias import DIAS_SEMANA, fecha_a_dia_semana, fecha_actual, periodo_actual, sumar_meses
from app.negocio.estadisticas import regenerar_snapshot_si_corresponde
from app.negocio.formato import formatear_moneda
from app.negocio.lista_espera import GrupoCobertura, marcar_resuelto
from app.negocio.liquidaciones import regenerar_si_corresponde
from app.negocio.llaves import llaves_faltantes_para_reserva
from app.negocio.mensajes import mensaje_detalle_reserva_aislada
from app.negocio.placas import placa_faltante_para_reserva
from app.negocio.resumen_profesional import calcular_resumen_profesional
from app.negocio.reservas import (
    ConflictoBloqueanteError,
    cancelar_reserva_aislada,
    crear_reserva_aislada,
    crear_reserva_regular,
    eliminar_reserva_regular,
    modificar_reserva_aislada,
    modificar_reserva_regular,
)
from app.repositorio.registro import obtener_repositorio

_DIAS_RESERVA = DIAS_SEMANA[:6]
_ANCHO_COMBO_PROFESIONAL = 190
_ANCHO_PANEL_FILTROS_GRILLA = 290
_ANCHO_COL_PROFESIONAL = 180
_FORMATO_FECHA = "dd-MM-yyyy"
_FECHA_SIN_DATO = QDate(2000, 1, 1)  # sentinel de QDateEdit.setSpecialValueText: "sin fecha"
# Punto #9.1.8 (SistemaDF v0.11.2026.10): "Dale un poco más de ancho a
# las columnas de la tabla, hay lugar" — mismo criterio y mismo valor
# que `novedades._ajustar_columnas`/`llaves._ajustar_columnas`
# (duplicado acá, pantallas sin relación entre sí).
_PADDING_COLUMNA = 30


def _ajustar_columnas(tabla: QTableWidget) -> None:
    tabla.resizeColumnsToContents()
    for columna in range(tabla.columnCount()):
        tabla.setColumnWidth(columna, tabla.columnWidth(columna) + _PADDING_COLUMNA)
    tabla.setColumnWidth(0, max(tabla.columnWidth(0), _ANCHO_COL_PROFESIONAL))


class _FiltroCalendarioArrancaHoy(QObject):
    """Hallazgo real de la clienta en Licencias ("el selector de fecha
    hasta... me lleva al año 2000"), mismo patrón en Reservas regulares
    (Vigencia hasta): mientras el campo sigue en el sentinel
    `_FECHA_SIN_DATO`, el popup del calendario arranca en esa página
    (año 2000) en vez del mes en curso — hay que retroceder casi tres
    décadas para llegar a una fecha real. Qt sincroniza la página
    visible del calendario con `date()` al armar el popup, ANTES de
    mostrarlo — instalado sobre el propio `calendarWidget()` y
    disparando en su evento Show (después de esa sincronización),
    `setCurrentPage` solo cambia qué página se VE, sin tocar el valor
    real del campo ni perder el sentinel."""

    def __init__(self, conn: sqlite3.Connection, campo: QDateEdit, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._campo = campo

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (override de Qt)
        if event.type() == QEvent.Type.Show and self._campo.date() == _FECHA_SIN_DATO:
            hoy = fecha_actual(self._conn)
            watched.setCurrentPage(hoy.year, hoy.month)
        return False


def _instalar_calendario_arranca_hoy(conn: sqlite3.Connection, campo: QDateEdit) -> None:
    """Ver `_FiltroCalendarioArrancaHoy` — para cualquier `QDateEdit` con
    `setCalendarPopup(True)` y el sentinel `_FECHA_SIN_DATO` como
    "sin fecha" (Reservas regulares acá mismo, Licencias en
    `novedades.py`, importado cruzado)."""
    filtro = _FiltroCalendarioArrancaHoy(conn, campo, parent=campo)
    campo.calendarWidget().installEventFilter(filtro)


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
# de Reservas AISLADAS (Crear/Modificar/Cancelar): en una ronda anterior
# crecían a propósito (`padding: 11px 16px`, después bajado a `5px` al
# sumar "Período a imputar") para alinear "Horas aisladas mensuales" con
# el borde inferior del cuadro "Detalle" — ver el historial completo en
# versiones anteriores de este comentario.
#
# Punto #9.1.3 (SistemaDF v0.11.2026.10): "Achicá el alto de los tres
# botones un poco más, al mínimo, para que se vean los tres... hoy por
# hoy veo dos nada más" — pasan al mismo mínimo que el resto de la
# columna (`_ESTILO_BOTON_COMPACTO`, 22px), sin ninguna distinción
# propia.
_ESTILO_BOTON_AISLADAS_ALTO = _ESTILO_BOTON_COMPACTO
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
# Rediseño a 4 columnas de Reservas aisladas (pedido explícito de la
# clienta, confirmado con una captura mockup antes de tocar código):
# formulario / filtros de la grilla / referencias de colores+Detalle /
# grilla, las primeras tres del mismo ancho fijo para que queden
# simétricas entre sí.
_ANCHO_COLUMNA_AISLADAS = 260
# Alto (px) de fila de encabezado/dato de la grilla en esa columna 4,
# más chico que el default de `GrillaOperativaWidget` (26px/24px) para
# que las 14 horas (8 a 22hs, configuración de hoy) entren sin necesitar
# scroll vertical — pedido explícito de la clienta, ver `fijar_alto_
# filas`.
_ALTO_FILA_ENCABEZADO_AISLADAS = 18
_ALTO_FILA_DATO_AISLADAS = 16


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


def _confirmar_llave_o_placa_faltante(parent: QWidget, faltantes: list[str]) -> bool:
    """Pedido explícito de la clienta: al cargar una reserva (regular o
    aislada), si al profesional le falta alguna llave de acceso
    (`llaves_faltantes_para_reserva`) y/o una placa en la unidad
    (`placa_faltante_para_reserva`), avisa con un cartel Sí/No en vez de
    bloquear la carga — ninguna de las dos cosas impide atender ahí (una
    llave la puede suplir otro profesional presente; una placa se puede
    encargar después), "pero está bueno que el sistema avise". Los dos
    chequeos se combinan en una sola lista y un solo cartel — si falta
    solo una llave, solo una placa, o ambas, el texto las menciona todas
    juntas; si no falta nada, no se llama a esta función. Devuelve True
    si el operador elige seguir igual (Sí), False si cancela (No) —
    mismo criterio (`QMessageBox.question`, Sí/No) que el resto de los
    carteles de confirmación de esta pantalla (ej.
    `ConflictoBloqueanteError`)."""
    respuesta = QMessageBox.question(
        parent, "Falta llave o placa",
        "Al profesional le falta " + " y ".join(faltantes) + ".\n\n"
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


class _SpinMonto(QDoubleSpinBox):
    """QDoubleSpinBox que se muestra como moneda ("$ 1.234,56") — mismo
    criterio que `_SpinMonto` de Pagos/`_SpinMoneda` de Configuración
    general (duplicado acá, no importado). Pedido de la clienta sobre
    "Monto a cobrar" de Reserva extraordinaria, extendido a "todos los
    cuadros de texto similares del sistema": separador de miles (en vez
    del decimal con coma que arrastra Qt por defecto) y select-all al
    enfocar, para poder tipear en limpio sin borrar a mano."""

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

    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)


_CATEGORIAS_REGULARES = ("R", "B", "E")
# Pedido de la clienta: Aisladas/Extraordinarias se abren a las cuatro
# categorías (A/B/R/E) — B solo para marcar ocupación (nunca imputa,
# sin liquidación propia), E puede imputar igual que R (afecta la
# liquidación de su cabeza de equipo). Ver `_categoria_requiere_
# periodo_editable`/`_resolver_periodo_imputar`.
_CATEGORIAS_AISLADAS = ("A", "B", "R", "E")
_ORDEN_CATEGORIA_REGULAR = {"B": 0, "R": 1, "E": 2}
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
    profesional sin importar su categoría).

    Orden: jerarquía de categorías B, R, A, E, X, C y, dentro de cada
    una, código natural (`clave_orden_profesional`) — pedido explícito
    de la clienta sobre TODOS los selectores de profesional del sistema,
    reemplaza al orden alfabético por Apellido que tenía antes."""
    if categorias is None:
        filas = conn.execute(
            "SELECT IdProfesional, IdCodigo, Tratamiento, Apellido, NombrePila, CategoriaProfesional "
            "FROM Profesional"
        ).fetchall()
    else:
        placeholders = ", ".join("?" for _ in categorias)
        filas = conn.execute(
            f"SELECT IdProfesional, IdCodigo, Tratamiento, Apellido, NombrePila, CategoriaProfesional "
            f"FROM Profesional WHERE CategoriaProfesional IN ({placeholders})",
            categorias,
        ).fetchall()
    filas = sorted(filas, key=lambda f: clave_orden_profesional(f["CategoriaProfesional"], f["IdCodigo"]))
    return [(f["IdProfesional"], _texto_profesional(f)) for f in filas]


def _opciones_profesional_con_categoria(
    conn: sqlite3.Connection, categorias: tuple[str, ...],
) -> list[tuple[int, str, str]]:
    """Mismo orden que `_opciones_profesional` (jerarquía B/R/A/E/X/C +
    código natural) pero devuelve también la categoría de cada uno —
    la necesitan Reservas aisladas/extraordinarias para decidir si
    "Período a imputar" queda editable (R/E) o fijo en "Período
    actual" (A/B, sin liquidación mensual propia).

    Reemplaza a la vieja `_opciones_profesional_extraordinaria` (A antes
    que R, orden propio de esa pantalla cuando solo admitía esas dos
    categorías): al ampliarse a cuatro categorías (pedido de la clienta,
    ver el docstring de `_PanelReservaExtraordinaria`/`_PanelReservas
    Aisladas`), se adopta la jerarquía global en vez de mantener una
    excepción puntual para solo dos de las cuatro."""
    opciones = _opciones_profesional(conn, categorias)
    placeholders = ", ".join("?" for _ in categorias)
    categoria_por_id = {
        f["IdProfesional"]: f["CategoriaProfesional"]
        for f in conn.execute(
            f"SELECT IdProfesional, CategoriaProfesional FROM Profesional "
            f"WHERE CategoriaProfesional IN ({placeholders})",
            categorias,
        )
    }
    return [(id_, etiqueta, categoria_por_id[id_]) for id_, etiqueta in opciones]


def _categoria_requiere_periodo_editable(categoria: str | None) -> bool:
    """R y E pueden imputar al período actual (rehace y marca no enviada
    la liquidación del profesional liquidable) o al próximo (no toca
    nada ahora, entra sola en el cálculo del mes siguiente) — ver
    `_resolver_periodo_imputar`. A y B no tienen liquidación mensual
    propia (`id_profesional_liquidable` da `None` para los dos), así que
    el selector queda fijo en "Período actual" y deshabilitado: elegir
    cualquier valor para ellos es un no-op funcional, la clienta solo
    pidió que el campo se vea parejo en las cuatro categorías."""
    return categoria in ("R", "E")


def _resolver_periodo_imputar(
    conn: sqlite3.Connection, id_profesional: int, periodo_reserva: str, periodo_a_imputar: str,
) -> None:
    """Respuesta de la clienta: "si se imputa al mismo período de la
    liquidación, la rehace y la marca como no enviada. Si la imputa para
    el período siguiente, no toca la liquidación del mes, se contempla
    ese punto para la liquidación del mes siguiente." Compartida por
    Reservas aisladas y Reservas extraordinarias — mismo mecanismo,
    ninguna de las dos pantallas necesita más que esto.

    "Período siguiente" no necesita código: no se toca nada ahora, y el
    mes que viene la recoge sola — `calcular_liquidacion` ya suma tanto
    las aisladas del mes en curso como las del mes anterior. "Período
    actual" reusa `regenerar_si_corresponde` (DC-08 §3.7): resuelve el
    profesional liquidable (el R mismo, o su cabeza de equipo si es E;
    `None` para A/B, en cuyo caso no hace nada) y reemite la liquidación
    de `periodo_reserva` si corresponde — `emitir_liquidacion` ya deja
    sola la marca "Regenerada no enviada" si hacía falta."""
    if periodo_a_imputar != "actual":
        return
    regenerar_si_corresponde(conn, id_profesional=id_profesional, periodo=periodo_reserva)
    conn.commit()


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
    """Orden por piso (PB, EP, después ascendente numérico —
    `clave_orden_unidad`, no expresable en el ORDER BY de SQL), pedido
    explícito de la clienta sobre este selector y "todos los similares
    del sistema": el orden alfabético puro de `Departamento` ponía "EP"
    antes de "PB" y rompía con pisos de dos dígitos (ej. "10mo" antes de
    "9no")."""
    if id_edificio is None:
        return []
    filas = conn.execute(
        "SELECT IdUnidad, Departamento FROM Unidad WHERE IdEdificio = ?", (id_edificio,)
    ).fetchall()
    filas = sorted(filas, key=lambda f: clave_orden_unidad(f["Departamento"]))
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


class _DialogoModificarReservaRegular(QDialog):
    """Punto #9.1.4 (SistemaDF v0.11.2026.10): "Modificar reserva" pasa de
    finalizar la fila vieja y precargar el formulario de alta (que
    parecía solo "cancelarla", sin dejar en claro que había quedado algo
    pendiente de confirmar) a este diálogo propio — edita Horario/
    Vigencia de la fila EXISTENTE, dejándola corriendo con la
    modificación aplicada. "Si quiero la termino desde el cuadro de
    diálogo" — alcanza con poner una Vigencia hasta real en vez de
    dejarla en "(sin fecha)", no hace falta ningún control aparte para
    eso. Profesional/Consultorio/Día no se pueden tocar acá (cambiarlos
    es, en los hechos, dar de alta una reserva distinta) — se muestran
    de solo lectura, arriba de los campos editables."""

    def __init__(self, conn: sqlite3.Connection, reserva: sqlite3.Row, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modificar reserva")
        layout = QVBoxLayout(self)

        profesional = obtener_repositorio(conn, "Profesional").obtener(reserva["IdProfesional"])
        consultorio = conn.execute(
            "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS NombreEdificio, "
            "loc.Localidad AS DomicilioLocalidad "
            "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad "
            "WHERE c.IdConsultorio = ?",
            (reserva["IdConsultorio"],),
        ).fetchone()
        layout.addWidget(QLabel(f"Profesional: {_texto_profesional(profesional) if profesional else '?'}"))
        if consultorio is not None:
            layout.addWidget(QLabel(
                f"Ubicación: {consultorio['DomicilioLocalidad'] or '(Sin localidad)'} - "
                f"{consultorio['NombreEdificio']} - {consultorio['Departamento']} - "
                f"Consultorio {consultorio['NumeroConsultorio']}"
            ))
        layout.addWidget(QLabel(f"Día: {reserva['DiaSemana']}"))

        fila_horario = QHBoxLayout()
        self.spin_desde = _SpinHorario()
        self.spin_desde.setRange(0, 23)
        self.spin_desde.setValue(reserva["HoraInicio"])
        self.spin_hasta = _SpinHorario()
        self.spin_hasta.setRange(1, 24)
        self.spin_hasta.setValue(reserva["HoraFin"])
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_desde)
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hasta)
        layout.addLayout(fila_horario)

        layout.addWidget(QLabel("Vigencia desde"))
        self.campo_vigencia_inicio = QDateEdit()
        self.campo_vigencia_inicio.setDisplayFormat(_FORMATO_FECHA_DIA)
        self.campo_vigencia_inicio.setLocale(_LOCALE_ES)
        self.campo_vigencia_inicio.setCalendarPopup(True)
        aplicar_color_sabado_negro(self.campo_vigencia_inicio)
        instalar_flechas_cambian_fecha_completa(self.campo_vigencia_inicio)
        self.campo_vigencia_inicio.setDate(QDate.fromString(reserva["VigenciaInicio"], "yyyy-MM-dd"))
        layout.addWidget(self.campo_vigencia_inicio)

        layout.addWidget(QLabel("Vigencia hasta (opcional — poné una fecha para terminar la reserva)"))
        self.campo_vigencia_fin = QDateEdit()
        self.campo_vigencia_fin.setDisplayFormat(_FORMATO_FECHA_DIA)
        self.campo_vigencia_fin.setLocale(_LOCALE_ES)
        self.campo_vigencia_fin.setCalendarPopup(True)
        aplicar_color_sabado_negro(self.campo_vigencia_fin)
        instalar_flechas_cambian_fecha_completa(self.campo_vigencia_fin)
        self.campo_vigencia_fin.setMinimumDate(_FECHA_SIN_DATO)
        self.campo_vigencia_fin.setSpecialValueText("(sin fecha)")
        self.campo_vigencia_fin.setDate(
            QDate.fromString(reserva["VigenciaFin"], "yyyy-MM-dd") if reserva["VigenciaFin"] else _FECHA_SIN_DATO
        )
        _instalar_calendario_arranca_hoy(conn, self.campo_vigencia_fin)
        layout.addWidget(self.campo_vigencia_fin)

        fila_botones = QHBoxLayout()
        boton_guardar = QPushButton("Guardar cambios")
        boton_guardar.setObjectName("botonPrimario")
        boton_guardar.clicked.connect(self._confirmar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.setObjectName("botonSecundario")
        boton_cancelar.clicked.connect(self.reject)
        fila_botones.addWidget(boton_guardar)
        fila_botones.addWidget(boton_cancelar)
        layout.addLayout(fila_botones)

        self._foco = instalar_enter_avanza_foco(
            [self.spin_desde, self.spin_hasta, self.campo_vigencia_inicio, self.campo_vigencia_fin,
             boton_guardar, boton_cancelar],
            parent=self,
        )
        self.spin_desde.setFocus()

    def _confirmar(self) -> None:
        if self.spin_hasta.value() <= self.spin_desde.value():
            QMessageBox.warning(self, "Modificar reserva", "\"Hasta\" tiene que ser posterior a \"Desde\".")
            return
        self.hora_inicio = self.spin_desde.value()
        self.hora_fin = self.spin_hasta.value()
        self.vigencia_inicio = self.campo_vigencia_inicio.date().toPython().isoformat()
        self.vigencia_fin = (
            None if self.campo_vigencia_fin.date() == _FECHA_SIN_DATO
            else self.campo_vigencia_fin.date().toPython().isoformat()
        )
        self.accept()


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
        self.panel_extraordinaria = _PanelReservaExtraordinaria(conn)
        self.pestanas.addTab(self.panel_regulares, "Reservas regulares")
        self.pestanas.addTab(self.panel_aisladas, "Reservas aisladas")
        self.pestanas.addTab(self.panel_extraordinaria, "Reservas extraordinarias")
        layout.addWidget(self.pestanas, stretch=1)

    def actualizar(self) -> None:
        self.panel_regulares.actualizar()
        self.panel_aisladas.actualizar()
        self.panel_extraordinaria.actualizar()


class _PanelReservasRegulares(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._reservas: list[sqlite3.Row] = []
        # #22 ("Confirmar reserva" de Lista de espera): cola de partes
        # pendientes de precargar cuando una cobertura necesita más de una
        # ReservaRegular para cubrir todo el pedido — ver `precargar_
        # desde_pedido`. Vacía en el uso manual de siempre.
        self._cola_precarga_pedido: list[GrupoCobertura] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar":
        el QTabWidget contenedor todavía no está mostrado y se termina
        quedando el foco en su tab bar. Al mostrarse la pestaña (al
        abrir la pantalla o volver a esta solapa) se repite el pedido
        de foco en Profesional, que es cuando realmente surte efecto —
        vía `reiniciar()` (punto #1.4), que de paso es lo mismo que
        dispara F3 ("Reiniciar solapa"). De paso, vuelve a fijar el
        alto de `_scroll_superior` (ver `_armar_ui`): el
        `minimumSizeHint()` calculado ANTES de este primer show puede
        quedar unos pixels desincronizado del real."""
        super().showEvent(event)
        self._scroll_superior.setFixedHeight(self._contenido_superior.minimumSizeHint().height())
        self.reiniciar()

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
        aplicar_color_sabado_negro(self.campo_vigencia_inicio)
        instalar_flechas_cambian_fecha_completa(self.campo_vigencia_inicio)
        form.addWidget(QLabel("Vigencia desde"))
        form.addWidget(self.campo_vigencia_inicio)

        self.campo_vigencia_fin = QDateEdit()
        self.campo_vigencia_fin.setDisplayFormat(_FORMATO_FECHA_DIA)
        self.campo_vigencia_fin.setLocale(_LOCALE_ES)
        self.campo_vigencia_fin.setCalendarPopup(True)
        aplicar_color_sabado_negro(self.campo_vigencia_fin)
        instalar_flechas_cambian_fecha_completa(self.campo_vigencia_fin)
        self.campo_vigencia_fin.setMinimumDate(_FECHA_SIN_DATO)
        self.campo_vigencia_fin.setSpecialValueText("(sin fecha)")
        self.campo_vigencia_fin.setDate(_FECHA_SIN_DATO)
        _instalar_calendario_arranca_hoy(self.conn, self.campo_vigencia_fin)
        form.addWidget(QLabel("Vigencia hasta (opcional)"))
        form.addWidget(self.campo_vigencia_fin)

        boton_crear = QPushButton("Crear reserva regular")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.setStyleSheet(_ESTILO_BOTON_COMPACTO)
        boton_crear.clicked.connect(self._crear)
        form.addWidget(boton_crear)
        # Punto #9.1.3 (SistemaDF v0.11.2026.10): deshabilitados sin
        # ninguna fila seleccionada en la tabla — ver `_actualizar_
        # botones`, conectada a `itemSelectionChanged` y llamada también
        # al final de `actualizar()`.
        self.boton_modificar = QPushButton("Modificar reserva")
        self.boton_modificar.setObjectName("botonSecundario")
        self.boton_modificar.setStyleSheet(_ESTILO_BOTON_COMPACTO)
        self.boton_modificar.clicked.connect(self._modificar_seleccionada)
        form.addWidget(self.boton_modificar)
        # Punto #9.1.6: "Finalizar reserva a fin de mes" pasa a "Eliminar
        # reserva" — ya no finaliza la vigencia, borra la fila por
        # completo (alerta mediante) y la saca de la tabla.
        self.boton_eliminar = QPushButton("Eliminar reserva")
        self.boton_eliminar.setObjectName("botonSecundario")
        self.boton_eliminar.setStyleSheet(_ESTILO_BOTON_COMPACTO)
        self.boton_eliminar.clicked.connect(self._eliminar_seleccionada)
        form.addWidget(self.boton_eliminar)

        linea_separadora = QFrame()
        linea_separadora.setFrameShape(QFrame.Shape.HLine)
        linea_separadora.setFrameShadow(QFrame.Shadow.Sunken)
        form.addWidget(linea_separadora)

        # wordWrap (pedido de la clienta, "Cantidad de horas regulares
        # semanales se ve cortado"): sin esto, un QLabel de una sola
        # línea más ancha que la columna no se recorta de forma visible
        # en el layout, pero sí puede quedar tapado por el panel de al
        # lado o cortado contra el borde de la ventana — con wrap pasa a
        # ocupar una segunda línea en vez de desbordar.
        self.etiqueta_horas_semanales = QLabel()
        self.etiqueta_horas_semanales.setWordWrap(True)
        self.etiqueta_descuento = QLabel()
        self.etiqueta_descuento.setWordWrap(True)
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
        # Pedido explícito de la clienta, extendido desde Oferta de
        # consultorios a toda pantalla con esta grilla: Tipo de bloque/
        # Horario y las filas de encabezado quedan siempre visibles al
        # escrolear — solo se escrolea el bloque de datos.
        self.grilla.activar_filas_y_columnas_fijas()
        # Pedido explícito de la clienta, extendido a todo el sistema: sin
        # esto, cuando la grilla necesita scroll horizontal (muchos
        # consultorios), la barra se come alto del viewport sin que el
        # tope mínimo lo contemple — tapaba la última fila y podía
        # disparar un scroll vertical de más, innecesario.
        self.grilla.reservar_alto_scroll_horizontal()
        # Cadena de foco propia del panel de Filtros de la grilla (pedido
        # de la clienta: "el Tab se salta el filtro de Día de la semana
        # entre Unidad y Profesional") — este panel nunca tuvo una cadena
        # explícita, dependía del orden nativo de Tab de Qt, que `agrupar_
        # dias_en_pares()` termina rompiendo. Cadena propia, separada de
        # `self._foco` (el formulario de alta de la izquierda): son dos
        # columnas con propósitos distintos (una carga la reserva, la
        # otra solo filtra la grilla de referencia), sin que la una
        # dependa del orden de Tab de la otra.
        self._foco_filtros_grilla = instalar_enter_avanza_foco(
            self.grilla.widgets_filtro_para_foco(), parent=self.grilla,
        )
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
        excluir_tabla_del_tab(self.tabla)
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
        instalar_eliminar_con_tecla(self.tabla, self._eliminar_seleccionada)
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones)
        layout_tabla.addWidget(self.tabla, stretch=1)
        layout_externo.addWidget(panel_tabla, stretch=1)

        self._cargar_edificios()
        self._foco = instalar_enter_avanza_foco(
            [
                self.combo_profesional, self.combo_localidad, self.combo_edificio, self.combo_unidad,
                self.combo_consultorio, *(self._checks_dia[dia] for dia in _DIAS_RESERVA),
                self.spin_desde, self.spin_hasta,
                self.campo_vigencia_inicio, self.campo_vigencia_fin, boton_crear,
                self.boton_modificar, self.boton_eliminar,
            ],
            parent=self,
        )
        self._actualizar_botones()

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
        _ajustar_columnas(self.tabla)
        self._sincronizar_grilla()
        self._actualizar_botones()

    @staticmethod
    def _clave_orden(columna: int):
        claves = {
            0: lambda t: clave_orden_codigo(_texto_profesional(t[1])) if t[1] else ("", -1, ""),
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
        """Después de crear una reserva, deja el resto del formulario
        listo para cargar otra — PERO sin tocar "Profesional" (punto
        #9.1.9, pedido explícito de la clienta: "queda cargado el
        nombre del profesional en el selector, solo cambia si se
        abandona el foco de la solapa") — ese reset vive aparte, en
        `reiniciar()`, que es lo que corre al reingresar a la solapa."""
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

    def reiniciar(self) -> None:
        """Punto #1.4: reset completo de filtros al reingresar a la
        solapa (incluido "Profesional", a diferencia de `_resetear_
        formulario`) + foco en el primer control — ver el comentario de
        esa función para por qué están separadas. Se llama desde
        `showEvent` y desde F3 ("Reiniciar solapa")."""
        self._orden.reiniciar()
        self.combo_profesional.setCurrentIndex(0)
        self._resetear_formulario()
        self.actualizar()

    def _dias_seleccionados(self) -> list[str]:
        return [dia for dia, check in self._checks_dia.items() if check.isChecked()]

    def precargar_desde_pedido(self, *, id_profesional: int, grupos: list[GrupoCobertura]) -> None:
        """#22: Lista de espera llama esto desde "Confirmar reserva" —
        carga la primera `GrupoCobertura` de `grupos` en el formulario y
        deja el resto en cola. Cada "Crear reserva regular" exitoso avanza
        solo a la parte siguiente (ver `_crear`), sin que el operador
        tenga que volver a Lista de espera entre una parte y la otra."""
        if not grupos:
            return
        self._cola_precarga_pedido = list(grupos[1:])
        self._cargar_grupo_cobertura(id_profesional, grupos[0])

    def _cargar_grupo_cobertura(self, id_profesional: int, grupo: GrupoCobertura) -> None:
        indice_profesional = self.combo_profesional.findData(id_profesional)
        if indice_profesional >= 0:
            self.combo_profesional.setCurrentIndex(indice_profesional)
        self._seleccionar_ubicacion(grupo.id_consultorio)
        for dia, check in self._checks_dia.items():
            check.setChecked(dia in grupo.dias)
        self.spin_desde.setValue(grupo.hora_inicio)
        self.spin_hasta.setValue(grupo.hora_fin)
        hoy = fecha_actual(self.conn)
        self.campo_vigencia_inicio.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.campo_vigencia_fin.setDate(_FECHA_SIN_DATO)
        self._sincronizar_grilla()
        self.combo_profesional.setFocus()

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
        # llave para entrar al lugar de la reserva y/o una placa en la
        # unidad — un solo cartel combinado, ver `_confirmar_llave_o_
        # placa_faltante`.
        faltantes = llaves_faltantes_para_reserva(
            self.conn, id_profesional=id_profesional, id_consultorio=id_consultorio,
        ) + placa_faltante_para_reserva(self.conn, id_profesional=id_profesional, id_consultorio=id_consultorio)
        if faltantes and not _confirmar_llave_o_placa_faltante(self, faltantes):
            return
        # Pedido explícito de la clienta ("EN GENERAL"): antes de crear
        # cualquier reserva, una vista previa de los datos con Confirmar/
        # Cancelar — si cancela, no se toca nada del formulario (ver
        # `confirmar_datos_antes_de_crear`).
        vigencia_fin_texto = (
            "sin fecha de fin" if self.campo_vigencia_fin.date() == _FECHA_SIN_DATO
            else self.campo_vigencia_fin.date().toString("dd-MM-yyyy")
        )
        if not confirmar_datos_antes_de_crear(self, "Crear reserva regular", [
            f"Profesional: {self.combo_profesional.currentText()}",
            f"Ubicación: {self.combo_localidad.currentText()} - {self.combo_edificio.currentText()} - "
            f"{self.combo_unidad.currentText()} - {self.combo_consultorio.currentText()}",
            f"Días: {', '.join(dias)}",
            f"Horario: {_fmt_hora(self.spin_desde.value())} a {_fmt_hora(self.spin_hasta.value())}",
            f"Vigencia: desde {self.campo_vigencia_inicio.date().toString('dd-MM-yyyy')} hasta {vigencia_fin_texto}",
        ]):
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
        else:
            # Punto #9.1.9: alerta final de éxito.
            QMessageBox.information(self, "Reserva creada", "Reserva cargada con éxito.")
        regenerar_si_corresponde(self.conn, id_profesional=id_profesional, periodo=periodo_actual(self.conn))
        self.conn.commit()
        self.actualizar()
        if self._cola_precarga_pedido:
            # #22: todavía falta cubrir otra parte del mismo pedido — se
            # precarga sola, sin volver a Lista de espera. El pedido recién
            # se marca Resuelto (más abajo) cuando no queda ninguna parte
            # pendiente, para no cerrarlo a mitad de camino.
            siguiente = self._cola_precarga_pedido.pop(0)
            self._cargar_grupo_cobertura(id_profesional, siguiente)
            return
        self._resolver_lista_espera_si_corresponde(id_profesional)
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

    def _resolver_lista_espera_si_corresponde(self, id_profesional: int) -> None:
        """DC-10 §2.2 paso 5: confirmar la reserva regular en F16 cierra
        solo, sin preguntar, el pedido de Lista de espera que la originó —
        pedido explícito de la clienta, reemplazando la confirmación Sí/No
        que tenía antes. Con un solo pedido Activo del profesional alcanza
        para resolverlo; con más de uno queda a criterio manual (no hay
        forma de saber cuál de todos se acaba de cubrir)."""
        pedidos = obtener_repositorio(self.conn, "ListaEspera").listar(
            IdProfesional=id_profesional, Estado="Activo",
        )
        if len(pedidos) != 1:
            return
        marcar_resuelto(self.conn, pedidos[0]["IdPedido"])
        self.conn.commit()

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._reservas[filas[0].row()]

    def _actualizar_botones(self) -> None:
        """Punto #9.1.3 (SistemaDF v0.11.2026.10): "Modificar reserva"/
        "Eliminar reserva" quedan deshabilitados (grises, salteados por
        el Tab) sin ninguna fila en foco en la tabla."""
        hay_seleccion = self._fila_seleccionada() is not None
        self.boton_modificar.setEnabled(hay_seleccion)
        self.boton_eliminar.setEnabled(hay_seleccion)

    def _modificar_seleccionada(self) -> None:
        """Punto #9.1.4: "Modificar reserva" abre un cuadro de diálogo
        propio (`_DialogoModificarReservaRegular`) que edita la fila
        EXISTENTE — sin finalizarla ni precargar el formulario de alta
        — "si quiero modifico algo puntual y la reserva sigue corriendo
        con esa modificación". Desde el mismo diálogo se la puede
        "terminar" poniendo una Vigencia hasta real."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            QMessageBox.warning(self, "Modificar reserva", "Elegí una fila de la tabla para modificar.")
            return
        dialogo = _DialogoModificarReservaRegular(self.conn, reserva, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            advertencias = modificar_reserva_regular(
                self.conn, reserva["IdReservaRegular"], hora_inicio=dialogo.hora_inicio,
                hora_fin=dialogo.hora_fin, vigencia_inicio=dialogo.vigencia_inicio,
                vigencia_fin=dialogo.vigencia_fin,
            )
        except ConflictoBloqueanteError as error:
            confirmacion = QMessageBox.question(
                self, "Conflictos detectados", f"{error}\n\n¿Modificar la reserva de todos modos?",
            )
            if confirmacion != QMessageBox.StandardButton.Yes:
                return
            advertencias = modificar_reserva_regular(
                self.conn, reserva["IdReservaRegular"], hora_inicio=dialogo.hora_inicio,
                hora_fin=dialogo.hora_fin, vigencia_inicio=dialogo.vigencia_inicio,
                vigencia_fin=dialogo.vigencia_fin, forzar=True,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Modificar reserva", str(error))
            return
        regenerar_si_corresponde(
            self.conn, id_profesional=reserva["IdProfesional"], periodo=periodo_actual(self.conn),
        )
        self.conn.commit()
        if advertencias:
            QMessageBox.information(
                self, "Reserva modificada", "Reserva modificada con avisos:\n" + "\n".join(advertencias),
            )
        else:
            QMessageBox.information(self, "Modificar reserva", "Reserva modificada con éxito.")
        self.actualizar()

    def _eliminar_seleccionada(self) -> None:
        """Punto #9.1.6: "Finalizar reserva a fin de mes" pasa a
        "Eliminar reserva" — con una fila seleccionada, borra esa
        reserva (alerta mediante) y la saca de la tabla directamente, en
        vez de solo ponerle fecha de fin."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            return
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(reserva["IdProfesional"])
        nombre_profesional = _texto_profesional(profesional) if profesional else "?"
        confirmacion = QMessageBox.question(
            self, "Eliminar reserva",
            f"¿Eliminar la reserva regular de {nombre_profesional} los {reserva['DiaSemana']} de "
            f"{_fmt_horario(reserva['HoraInicio'], reserva['HoraFin'])}?",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        try:
            eliminar_reserva_regular(self.conn, reserva["IdReservaRegular"])
        except ValueError as error:
            QMessageBox.warning(self, "Eliminar reserva", str(error))
            return
        # Punto #9.1.9: cualquiera de los tres botones (Crear/Modificar/
        # Eliminar) que toque el período en curso regenera y marca no
        # enviada la liquidación del profesional afectado.
        regenerar_si_corresponde(
            self.conn, id_profesional=reserva["IdProfesional"], periodo=periodo_actual(self.conn),
        )
        self.conn.commit()
        QMessageBox.information(self, "Eliminar reserva", "Reserva eliminada con éxito.")
        self.actualizar()
        self.combo_profesional.setFocus()


class _DialogoModificarReservaAislada(QDialog):
    """Homólogo de `_DialogoModificarReservaRegular` para Reservas
    aisladas/extraordinarias (pedido explícito de la clienta, "que los
    botones 'Modificar reserva'/'Cancelar reserva' se comporten de la
    misma manera que los homólogos de Regulares, #9.1.4 y #9.1.6"):
    edita la fila EXISTENTE (horario, y recargo o ítem/monto según el
    tipo) en vez de cancelarla y precargar el formulario de alta.
    Profesional/Ubicación/Fecha quedan de solo lectura — cambiarlos es,
    en los hechos, dar de alta una reserva distinta."""

    def __init__(self, conn: sqlite3.Connection, reserva: sqlite3.Row, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modificar reserva")
        self._es_extraordinaria = bool(reserva["EsExtraordinaria"])
        layout = QVBoxLayout(self)

        profesional = obtener_repositorio(conn, "Profesional").obtener(reserva["IdProfesional"])
        consultorio = conn.execute(
            "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS NombreEdificio, "
            "loc.Localidad AS DomicilioLocalidad "
            "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad "
            "WHERE c.IdConsultorio = ?",
            (reserva["IdConsultorio"],),
        ).fetchone()
        layout.addWidget(QLabel(f"Profesional: {_texto_profesional(profesional) if profesional else '?'}"))
        if consultorio is not None:
            layout.addWidget(QLabel(
                f"Ubicación: {consultorio['DomicilioLocalidad'] or '(Sin localidad)'} - "
                f"{consultorio['NombreEdificio']} - {consultorio['Departamento']} - "
                f"Consultorio {consultorio['NumeroConsultorio']}"
            ))
        layout.addWidget(QLabel(f"Fecha: {_fmt_fecha(reserva['Fecha'])}"))

        fila_horario = QHBoxLayout()
        self.spin_desde = _SpinHorario()
        self.spin_desde.setRange(0, 23)
        self.spin_desde.setSingleStep(0.5)
        self.spin_desde.setValue(reserva["HoraInicio"])
        self.spin_hasta = _SpinHorario()
        self.spin_hasta.setRange(0.5, 24)
        self.spin_hasta.setSingleStep(0.5)
        self.spin_hasta.setValue(reserva["HoraFin"])
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_desde)
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hasta)
        layout.addLayout(fila_horario)

        widgets_foco = [self.spin_desde, self.spin_hasta]

        self.casilla_recargo: QCheckBox | None = None
        self.campo_item: QLineEdit | None = None
        self.campo_monto: _SpinMonto | None = None
        if self._es_extraordinaria:
            layout.addWidget(QLabel("Ítem a cargar"))
            self.campo_item = QLineEdit(reserva["ItemExtraordinario"] or "")
            layout.addWidget(self.campo_item)
            layout.addWidget(QLabel("Monto a cobrar"))
            self.campo_monto = _SpinMonto()
            self.campo_monto.setRange(0, 10_000_000)
            self.campo_monto.setValue(reserva["MontoExtraordinario"] or 0.0)
            layout.addWidget(self.campo_monto)
            widgets_foco += [self.campo_item, self.campo_monto]
        else:
            self.casilla_recargo = QCheckBox("Aplica recargo")
            self.casilla_recargo.setChecked(bool(reserva["AplicaRecargo"]))
            layout.addWidget(self.casilla_recargo)
            widgets_foco.append(self.casilla_recargo)

        fila_botones = QHBoxLayout()
        boton_guardar = QPushButton("Guardar cambios")
        boton_guardar.setObjectName("botonPrimario")
        boton_guardar.clicked.connect(self._confirmar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.setObjectName("botonSecundario")
        boton_cancelar.clicked.connect(self.reject)
        fila_botones.addWidget(boton_guardar)
        fila_botones.addWidget(boton_cancelar)
        layout.addLayout(fila_botones)

        widgets_foco += [boton_guardar, boton_cancelar]
        self._foco = instalar_enter_avanza_foco(widgets_foco, parent=self)
        self.spin_desde.setFocus()

    def _confirmar(self) -> None:
        if self.spin_hasta.value() <= self.spin_desde.value():
            QMessageBox.warning(self, "Modificar reserva", "\"Hasta\" tiene que ser posterior a \"Desde\".")
            return
        if self._es_extraordinaria and not self.campo_item.text().strip():
            QMessageBox.warning(self, "Modificar reserva", "Cargá un ítem a cobrar.")
            return
        self.hora_inicio = self.spin_desde.value()
        self.hora_fin = self.spin_hasta.value()
        self.aplica_recargo = self.casilla_recargo.isChecked() if self.casilla_recargo else None
        self.item_extraordinario = self.campo_item.text().strip() if self.campo_item else None
        self.monto_extraordinario = self.campo_monto.value() if self.campo_monto else None
        self.accept()


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
        `_scroll_superior` (ver esa misma solapa).

        A diferencia de Reservas regulares, este `showEvent` NO llama a
        `reiniciar()` — simplemente volver a esta solapa no tiene que
        perder el filtro de Profesional que el operador ya había
        elegido (comportamiento de siempre, sin tocar); `reiniciar()`
        es exclusivamente para F3 ("Reiniciar solapa"), que sí es un
        pedido explícito de empezar de cero."""
        super().showEvent(event)
        self._scroll_superior.setFixedHeight(self._contenido_superior.minimumSizeHint().height())
        self._orden.reiniciar()
        self.actualizar()
        self.combo_profesional.setFocus()

    def reiniciar(self) -> None:
        """F3 ("Reiniciar solapa"): mismo criterio que `_PanelReservas
        Regulares.reiniciar` — a diferencia de esa solapa, acá
        `_resetear_formulario` ya incluye "Profesional" (punto #9.1.9
        no aplica acá), así que alcanza con llamarla directo."""
        self._orden.reiniciar()
        self._resetear_formulario()
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
        # Rediseño a 4 columnas (pedido de la clienta, ver constantes
        # `_ANCHO_COLUMNA_AISLADAS`/`_ALTO_FILA_*_AISLADAS` más arriba en
        # el archivo): reemplaza el `QSplitter` de 2 paneles (formulario +
        # grilla con filtros embebidos) de antes.
        fila_columnas = QHBoxLayout()

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
        self._categoria_por_profesional: dict[int, str] = {}
        for id_, etiqueta, categoria in _opciones_profesional_con_categoria(self.conn, _CATEGORIAS_AISLADAS):
            self.combo_profesional.addItem(etiqueta, id_)
            self._categoria_por_profesional[id_] = categoria
        habilitar_busqueda_profesional(self.combo_profesional)
        self.combo_profesional.currentIndexChanged.connect(self.actualizar)
        self.combo_profesional.currentIndexChanged.connect(self._al_cambiar_profesional)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        # "Período a imputar" (pedido de la clienta): siempre visible,
        # pero fijo en "Período actual" y deshabilitado para A/B (sin
        # liquidación mensual propia) — `_al_cambiar_profesional` lo
        # habilita y lo lleva a "Período siguiente" por defecto para R/E.
        self.etiqueta_periodo_imputar = QLabel("Período a imputar")
        self.combo_periodo_imputar = QComboBox()
        self.combo_periodo_imputar.addItem("Período actual (el de la fecha cargada)", "actual")
        self.combo_periodo_imputar.addItem("Período siguiente", "siguiente")
        # Estado inicial explícito: la primera selección de "Profesional"
        # (índice 0, "Todos los profesionales") dispara `currentIndexChanged`
        # ANTES de que este método termine de conectarlo a `_al_cambiar_
        # profesional` (Qt ya emite ese cambio al agregar el primer ítem al
        # combo, más arriba) — sin este default a mano, el combo quedaba
        # habilitado por default de Qt en vez de arrancar deshabilitado.
        self.combo_periodo_imputar.setEnabled(False)
        form.addWidget(self.etiqueta_periodo_imputar)
        form.addWidget(self.combo_periodo_imputar)

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
        aplicar_color_sabado_negro(self.campo_fecha)
        instalar_flechas_cambian_fecha_completa(self.campo_fecha)
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

        # Punto "la etiqueta del check... cambiala a 'Es reubicación' y
        # ponelos en la misma línea uno al lado del otro" (SistemaDF
        # v0.11.2026.10, Reservas aisladas): la aclaración larga que
        # tenía el check de reubicación se saca del todo (ya no hace
        # falta el salto de línea a mano de la ronda anterior, que
        # existía justamente para compensar ese texto largo) y los dos
        # checks pasan a una sola fila.
        fila_checks = QHBoxLayout()
        self.casilla_recargo = QCheckBox("Aplica recargo")
        fila_checks.addWidget(self.casilla_recargo)
        self.casilla_reubicacion = QCheckBox("Es reubicación")
        self.casilla_reubicacion.stateChanged.connect(self._alternar_reubicacion)
        fila_checks.addWidget(self.casilla_reubicacion)
        form.addLayout(fila_checks)

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
        aplicar_color_sabado_negro(self.campo_fecha_ausencia)
        instalar_flechas_cambian_fecha_completa(self.campo_fecha_ausencia)
        layout_reubicacion.addWidget(self.campo_fecha_ausencia)
        self.contenedor_reubicacion.setVisible(False)
        form.addWidget(self.contenedor_reubicacion)

        boton_crear = QPushButton("Crear reserva aislada")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.setStyleSheet(_ESTILO_BOTON_AISLADAS_ALTO)
        boton_crear.clicked.connect(self._crear)
        form.addWidget(boton_crear)
        # Mismo criterio que Reservas regulares (regla general "EN
        # GENERAL": edición de tabla vía selección + diálogo): deshabilitados
        # sin ninguna fila en foco en la tabla.
        self.boton_modificar = QPushButton("Modificar reserva")
        self.boton_modificar.setObjectName("botonSecundario")
        self.boton_modificar.setStyleSheet(_ESTILO_BOTON_AISLADAS_ALTO)
        self.boton_modificar.clicked.connect(self._modificar_seleccionada)
        form.addWidget(self.boton_modificar)
        self.boton_cancelar = QPushButton("Cancelar reserva")
        self.boton_cancelar.setObjectName("botonSecundario")
        self.boton_cancelar.setStyleSheet(_ESTILO_BOTON_AISLADAS_ALTO)
        self.boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(self.boton_cancelar)

        form.addStretch()
        panel_form.setFixedWidth(_ANCHO_COLUMNA_AISLADAS)
        fila_columnas.addWidget(panel_form)

        # --- Columna 2: solo los filtros de la grilla (Localidad/
        # Edificio/Unidad/Día de la semana/Profesional), mismo ancho que
        # la columna 1, estirados hasta su misma altura. Rediseño de 4
        # columnas pedido por la clienta sobre el formulario anterior (2
        # columnas: formulario + grilla con sus filtros embebidos) —
        # "vamos a agregar una cuarta columna a ver cómo queda".
        self.grilla = GrillaOperativaWidget(self.conn)
        self.grilla.fijar_modo("aislada")
        self.grilla.activar_filtro_exclusivo_profesional(True)
        self.grilla.mostrar_leyenda_colores(compacta=False)
        # Sin título "Filtros" (pedido de la clienta) — cada filtro pasa a
        # nombrarse solo con "Filtro de ...", ver `renombrar_etiquetas_
        # filtro`.
        self.grilla.fijar_titulo_filtros("")
        self.grilla.renombrar_etiquetas_filtro()
        # Celdas más bajas que el default (26px/24px) para que las 14
        # horas (8 a 22hs, configuración de hoy) entren en la columna 4
        # sin necesitar scroll vertical — pedido explícito de la clienta
        # en este rediseño. Hay que fijarlo ANTES de la primera
        # construcción real de la grilla (ver `fijar_alto_filas`).
        self.grilla.fijar_alto_filas(_ALTO_FILA_ENCABEZADO_AISLADAS, _ALTO_FILA_DATO_AISLADAS)

        panel_filtros_aisladas = self.grilla.extraer_panel_filtros()
        panel_filtros_aisladas.setFixedWidth(_ANCHO_COLUMNA_AISLADAS)
        # "Referencias de colores" se separa del panel de Filtros: pasa a
        # su propia columna 3, arriba del cuadro "Detalle" — pedido
        # explícito de la clienta ("arrancás con las referencias de
        # colores... de a una por fila").
        leyenda_colores = self.grilla.extraer_leyenda_colores()
        # Una referencia por fila (no a dos columnas, que es lo que arma
        # `mostrar_leyenda_colores(compacta=True)` para el panel angosto
        # de Filtros embebido de siempre) — fuente y cuadros chicos para
        # ganar lugar, mismo pedido explícito de la clienta.
        leyenda_colores._columnas = 1
        leyenda_colores.fijar_tamano_muestra(24, 14)
        leyenda_colores.fijar_tamano_fuente(9)
        leyenda_colores.actualizar(self.grilla.combo_modo.currentData() or "aislada")
        # La columna de Filtros se estira hasta la misma altura que la
        # columna 1 (ver `fila_columnas` más abajo, que iguala el alto de
        # las cuatro columnas) — pedido explícito de la clienta ("si es
        # necesario... poné los días de la semana de a uno", ya el
        # default de esta grilla, para que llegue simétrico sin hueco en
        # blanco al final).
        # Sin margen propio: el panel ya trae su propio margen nativo de
        # `QGroupBox` (el mismo que, sin título, alineaba "Filtro de
        # localidad" con "Profesional" cuando vivía embebido directo en
        # `self.grilla`) — sumarle acá otro encima de `_ALTO_TITULO_
        # FILTROS` lo corría de más.
        panel_filtros_aisladas.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout_col_filtros = QVBoxLayout()
        layout_col_filtros.setContentsMargins(0, 0, 0, 0)
        layout_col_filtros.addWidget(panel_filtros_aisladas, stretch=1)
        fila_columnas.addLayout(layout_col_filtros)

        # --- Columna 3: referencias de colores arriba, "Detalle" abajo
        # (estirado hasta el final, sin tope de alto), mismo ancho que
        # las columnas 1 y 2.
        panel_col_detalle = QWidget()
        panel_col_detalle.setFixedWidth(_ANCHO_COLUMNA_AISLADAS)
        layout_col_detalle = QVBoxLayout(panel_col_detalle)
        # Sin margen propio, mismo motivo que la columna 2: "Referencias de
        # colores" es un `QGroupBox` (como "Filtros") y ya trae su propio
        # margen nativo para alinearse con "Profesional" — sumarle
        # `_ALTO_TITULO_FILTROS` encima lo corría de más.
        layout_col_detalle.setContentsMargins(0, 0, 0, 0)
        layout_col_detalle.addWidget(leyenda_colores)
        etiqueta_detalle, texto_detalle = self.grilla.extraer_detalle()
        layout_col_detalle.addWidget(etiqueta_detalle)
        # Sin tope de alto (90px por defecto): el cuadro de Detalle se
        # estira hasta el final de la columna en vez de quedar chico con
        # un hueco en blanco debajo — pedido explícito de la clienta
        # ("estiralo hasta abajo donde terminan las otras columnas").
        texto_detalle.setMaximumHeight(16_777_215)
        layout_col_detalle.addWidget(texto_detalle, stretch=1)
        fila_columnas.addWidget(panel_col_detalle)

        # --- Columna 4: la grilla en sí (ya sin el panel de Filtros ni
        # la leyenda, sacados arriba), con el resto del ancho disponible.
        # Pedido explícito de la clienta, extendido desde Oferta de
        # consultorios a toda pantalla con esta grilla: Tipo de bloque/
        # Horario y las filas de encabezado quedan siempre visibles al
        # escrolear — solo se escrolea el bloque de datos.
        self.grilla.activar_filas_y_columnas_fijas()
        # Pedido explícito de la clienta, extendido a todo el sistema: sin
        # esto, cuando la grilla necesita scroll horizontal (muchos
        # consultorios), la barra se come alto del viewport sin que el
        # tope mínimo lo contemple — tapaba la última fila y podía
        # disparar un scroll vertical de más, innecesario.
        self.grilla.reservar_alto_scroll_horizontal()
        # Mismo criterio que Reservas regulares (ver esa solapa): cadena
        # de foco propia para el panel de Filtros de la grilla, separada
        # de `self._foco` (el formulario de alta).
        self._foco_filtros_grilla = instalar_enter_avanza_foco(
            self.grilla.widgets_filtro_para_foco(), parent=self.grilla,
        )
        fila_columnas.addWidget(self.grilla, stretch=1)

        layout.addLayout(fila_columnas)

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
        excluir_tabla_del_tab(self.tabla)
        self.tabla.setColumnCount(12)
        self.tabla.setHorizontalHeaderLabels(
            [
                "Profesional", "Localidad", "Edificio", "Unidad", "Consultorio", "Día", "Fecha", "Horario",
                "Reubicación", "Estado", "Valor", "Período imputado",
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
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones)
        instalar_eliminar_con_tecla(self.tabla, self._cancelar)
        layout_tabla.addWidget(self.tabla, stretch=1)
        layout_externo.addWidget(panel_tabla, stretch=1)

        self._cargar_edificios()
        self._foco = instalar_enter_avanza_foco(
            [
                # Pedido explícito de la clienta: "si elijo un profesional
                # categoría R el foco desde el selector del profesional
                # pasa al 'Período a imputar', no lo saltea" — faltaba de
                # la cadena por completo; al estar deshabilitado para A/B
                # (`_al_cambiar_profesional`), `instalar_enter_avanza_foco`
                # ya lo saltea sola sin necesitar ninguna condición acá.
                self.combo_profesional, self.combo_periodo_imputar,
                self.combo_localidad, self.combo_edificio, self.combo_unidad,
                self.combo_consultorio, self.campo_fecha, self.spin_desde, self.spin_hasta,
                self.casilla_recargo, self.casilla_reubicacion, self.combo_horario_no_usado,
                self.campo_fecha_ausencia, boton_crear, self.boton_modificar, self.boton_cancelar,
            ],
            parent=self,
        )
        self._actualizar_botones()

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
        """Helper interno (y de tests): puebla los cuatro combos de
        ubicación en cascada a partir de un `IdConsultorio`."""
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
        if self.casilla_reubicacion.isChecked():
            self._cargar_horarios_no_usados()

    def _alternar_reubicacion(self) -> None:
        marcado = self.casilla_reubicacion.isChecked()
        self.contenedor_reubicacion.setVisible(marcado)
        if marcado:
            self._cargar_horarios_no_usados()

    def _al_cambiar_profesional(self) -> None:
        """"Período a imputar" queda editable (default "Período
        siguiente") para R/E, fijo en "Período actual" y deshabilitado
        para A/B/sin profesional elegido — ver `_categoria_requiere_
        periodo_editable`."""
        id_profesional = self.combo_profesional.currentData()
        categoria = self._categoria_por_profesional.get(id_profesional) if id_profesional is not None else None
        editable = _categoria_requiere_periodo_editable(categoria)
        self.combo_periodo_imputar.setEnabled(editable)
        self.combo_periodo_imputar.setCurrentIndex(1 if editable else 0)

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
        todavía no corresponde mostrarle un valor de facturación. Una
        reserva extraordinaria muestra el monto manual que se tipeó al
        cargarla (`MontoExtraordinario`), no un cálculo de hora×tarifa —
        esta tabla también lista las extraordinarias (son una
        ReservaAislada más), así que su columna "Valor" tiene que
        reflejar lo que de verdad se cobra."""
        if reserva["Fecha"][:7] > periodo_actual(self.conn):
            return ""
        if reserva["EsExtraordinaria"]:
            return formatear_moneda(reserva["MontoExtraordinario"] or 0.0)
        if reserva["EsReubicacion"]:
            return formatear_moneda(0.0)
        monto = (reserva["HoraFin"] - reserva["HoraInicio"]) * valor_hora_aislada
        if reserva["AplicaRecargo"]:
            monto *= 1 + recargo_pct / 100
        return formatear_moneda(monto)

    def actualizar(self) -> None:
        """Sin profesional elegido ("Todos los profesionales"), muestra
        las reservas aisladas comunes de todos los profesionales —
        pedido explícito de la clienta: las extraordinarias quedan
        afuera (tienen su propia solapa), y el orden por defecto pasa a
        ser fecha, hora de inicio y código de profesional (sin agrupar
        por categoría). Con un profesional elegido, se acota a las de
        ese profesional únicamente (incluidas extraordinarias y su
        historia — canceladas incluidas — para poder revisarla), mismo
        orden por fecha/hora (la categoría/código no distinguen nada
        dentro de un solo profesional). Overridable en los dos casos
        haciendo click en el título de una columna (ver `OrdenTabla`)."""
        id_profesional_filtro = self.combo_profesional.currentData()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        todas = obtener_repositorio(self.conn, "ReservaAislada").listar()
        if id_profesional_filtro is not None:
            filtradas = [r for r in todas if r["IdProfesional"] == id_profesional_filtro]
        else:
            filtradas = [r for r in todas if not r["EsExtraordinaria"]]

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
            t[0]["Fecha"], t[0]["HoraInicio"],
            _numero_codigo(t[1]["IdCodigo"] if t[1] else None),
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
            self.tabla.setItem(fila_idx, 11, QTableWidgetItem(r["PeriodoImputado"] or ""))
        _ajustar_columnas(self.tabla)
        self._sincronizar_grilla()
        self.grilla.actualizar()

    @staticmethod
    def _clave_orden(columna: int):
        claves = {
            0: lambda t: clave_orden_codigo(_texto_profesional(t[1])) if t[1] else ("", -1, ""),
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
            11: lambda t: t[0]["PeriodoImputado"] or "",
        }
        return claves[columna]

    def _crear(self, forzar: bool = False) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Crear reserva aislada", "Elegí un profesional.")
            return
        # Capturado ACÁ, antes de que `_resetear_formulario()` (al final,
        # si todo sale bien) vuelva a pisar este combo.
        periodo_a_imputar = self.combo_periodo_imputar.currentData()
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
            faltantes = llaves_faltantes_para_reserva(
                self.conn, id_profesional=id_profesional, id_consultorio=id_consultorio,
            ) + placa_faltante_para_reserva(self.conn, id_profesional=id_profesional, id_consultorio=id_consultorio)
            if faltantes and not _confirmar_llave_o_placa_faltante(self, faltantes):
                return
            # Pedido explícito de la clienta ("EN GENERAL"): vista previa
            # de los datos con Confirmar/Cancelar antes de crear — mismo
            # criterio que Reservas regulares, sin repetir en el
            # reintento automático con `forzar=True`.
            if not confirmar_datos_antes_de_crear(self, "Crear reserva aislada", [
                f"Profesional: {self.combo_profesional.currentText()}",
                f"Ubicación: {self.combo_localidad.currentText()} - {self.combo_edificio.currentText()} - "
                f"{self.combo_unidad.currentText()} - {self.combo_consultorio.currentText()}",
                f"Fecha: {self.campo_fecha.date().toString('dd-MM-yyyy')}",
                f"Horario: {_fmt_hora(self.spin_desde.value())} a {_fmt_hora(self.spin_hasta.value())}",
                f"Aplica recargo: {'Sí' if self.casilla_recargo.isChecked() else 'No'}",
                f"Es reubicación: {'Sí' if self.casilla_reubicacion.isChecked() else 'No'}",
                f"Período a imputar: {self.combo_periodo_imputar.currentText()}",
            ]):
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
            # "En la tabla agregar el campo 'Período imputado'" — se
            # guarda ya resuelto a "AAAA-MM" (no "actual"/"siguiente" tal
            # cual viene del combo), mismo criterio que `_resolver_
            # periodo_imputar` resuelve el efecto real sobre la
            # liquidación.
            periodo_imputado=(
                fecha[:7] if periodo_a_imputar == "actual" else sumar_meses(fecha[:7], 1)
            ),
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
        regenerar_snapshot_si_corresponde(self.conn, fecha[:7])
        _resolver_periodo_imputar(self.conn, id_profesional, fecha[:7], periodo_a_imputar)
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
        regenerar_snapshot_si_corresponde(self.conn, reserva["Fecha"][:7])
        if requiere_aviso:
            QMessageBox.information(self, titulo, "Cancelada el mismo día: avisar al profesional.")
        self._copiar_mensaje_detalle(reserva["IdProfesional"], reserva["Fecha"])
        self.actualizar()
        return True

    def _actualizar_botones(self) -> None:
        """Mismo criterio que Reservas regulares: "Modificar reserva"/
        "Cancelar reserva" quedan deshabilitados sin ninguna fila en
        foco en la tabla."""
        hay_seleccion = self._fila_seleccionada() is not None
        self.boton_modificar.setEnabled(hay_seleccion)
        self.boton_cancelar.setEnabled(hay_seleccion)

    def _cancelar(self) -> None:
        """Punto #9.1.6 (homólogo de "Eliminar reserva" en Regulares):
        pide confirmación explícita antes de cancelar, con los datos
        completos de la reserva (profesional/día/horario) en vez de
        cancelar directo sin preguntar nada."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            return
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(reserva["IdProfesional"])
        nombre_profesional = _texto_profesional(profesional) if profesional else "?"
        dia_semana = fecha_a_dia_semana(date.fromisoformat(reserva["Fecha"]))
        confirmacion = QMessageBox.question(
            self, "Cancelar reserva",
            f"¿Cancelar la reserva aislada de {nombre_profesional} el {dia_semana} "
            f"{_fmt_fecha(reserva['Fecha'])} de {_fmt_horario(reserva['HoraInicio'], reserva['HoraFin'])}?",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        if self._cancelar_registro(reserva, "Cancelar reserva"):
            self.combo_profesional.setFocus()

    def _modificar_seleccionada(self) -> None:
        """Punto #9.1.4 (homólogo de Reservas regulares): abre
        `_DialogoModificarReservaAislada`, que edita la fila EXISTENTE
        (horario, y recargo o ítem/monto si es extraordinaria) sin
        cancelarla ni precargar el formulario de alta."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            QMessageBox.warning(self, "Modificar reserva", "Elegí una fila de la tabla para modificar.")
            return
        dialogo = _DialogoModificarReservaAislada(self.conn, reserva, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            advertencias = modificar_reserva_aislada(
                self.conn, reserva["IdReservaAislada"], hora_inicio=dialogo.hora_inicio,
                hora_fin=dialogo.hora_fin, aplica_recargo=dialogo.aplica_recargo,
                item_extraordinario=dialogo.item_extraordinario, monto_extraordinario=dialogo.monto_extraordinario,
            )
        except ConflictoBloqueanteError as error:
            confirmacion = QMessageBox.question(
                self, "Conflictos detectados", f"{error}\n\n¿Modificar la reserva de todos modos?",
            )
            if confirmacion != QMessageBox.StandardButton.Yes:
                return
            advertencias = modificar_reserva_aislada(
                self.conn, reserva["IdReservaAislada"], hora_inicio=dialogo.hora_inicio,
                hora_fin=dialogo.hora_fin, aplica_recargo=dialogo.aplica_recargo,
                item_extraordinario=dialogo.item_extraordinario, monto_extraordinario=dialogo.monto_extraordinario,
                forzar=True,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Modificar reserva", str(error))
            return
        self.conn.commit()
        regenerar_snapshot_si_corresponde(self.conn, reserva["Fecha"][:7])
        self._copiar_mensaje_detalle(reserva["IdProfesional"], reserva["Fecha"])
        if advertencias:
            QMessageBox.information(
                self, "Reserva modificada", "Reserva modificada con avisos:\n" + "\n".join(advertencias),
            )
        else:
            QMessageBox.information(self, "Modificar reserva", "Reserva modificada con éxito.")
        self.actualizar()


# `panel_form` usa `_ANCHO_PANEL_FILTROS_GRILLA` como ancho TOTAL fijo,
# pero su `QVBoxLayout` se queda con el margen default de Qt (9px por
# lado) — el ancho de CONTENIDO real es 290 - 9 - 9 = 272 (confirmado
# con `combo_profesional`, que ya se dimensiona bien a ese ancho). Los
# tres botones de acción, en cambio, se fijaban al ancho TOTAL del panel
# (290) en vez de al de contenido — su borde derecho terminaba 9px más
# allá del borde del panel y quedaba cortado contra él. Ancho correcto
# para estos tres botones, medido, no el de `panel_form`.
_ANCHO_BOTON_EXTRAORDINARIA = _ANCHO_PANEL_FILTROS_GRILLA - 18


class _PanelReservaExtraordinaria(QWidget):
    """Reserva extraordinaria (pedido de la clienta): una `ReservaAislada`
    más — mismo modelo de conflictos, ocupación de grilla y cancelación
    que cualquier otra aislada (`crear_reserva_aislada`/
    `cancelar_reserva_aislada`, sin duplicar nada de esa lógica) — pero
    con un ítem a cargar de texto libre y un monto manual en vez de
    hora×tarifa del consultorio. Al confirmar, el mensaje de detalle
    (`mensaje_detalle_reserva_aislada`, el mismo que ya usa Centro de
    mensajería) ya la incluye sola, con el saldo anterior y los demás
    conceptos especiales (llaves, ítems libres) — no hace falta ningún
    mensaje ni cálculo aparte, se copia al portapapeles con el mismo
    mecanismo que cualquier alta de aislada.

    Pedido explícito de la clienta, ampliado en rondas sucesivas: el
    combo de profesional admite las cuatro categorías A/B/R/E (no solo
    A) — B participa solo para marcar ocupación (nunca imputa, sin
    liquidación propia); R y E (vía su cabeza de equipo) sí pueden
    afectar una `LiquidacionEmitida` ya generada, de ahí "Período a
    imputar" — ver `_al_cambiar_profesional`/`_resolver_periodo_imputar`
    (función compartida con Reservas aisladas, mismo mecanismo).

    A diferencia de Reservas regulares/aisladas (con rondas y rondas de
    calibración pixel a pixel documentadas en CLAUDE.md), esta solapa es
    un primer armado deliberadamente simple — sin grilla de referencia
    embebida —, para no arriesgar esa geometría ya afinada de las otras
    dos solapas."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._reservas: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """No llama a `reiniciar()` — mismo motivo que en Reservas
        aisladas: volver a esta solapa no tiene que perder el filtro de
        Profesional elegido."""
        super().showEvent(event)
        self._orden.reiniciar()
        self.actualizar()
        self.combo_profesional.setFocus()

    def reiniciar(self) -> None:
        """F3 ("Reiniciar solapa"): mismo criterio que las otras dos
        solapas de Reservas."""
        self._orden.reiniciar()
        self._resetear_formulario()
        self.actualizar()
        self.combo_profesional.setFocus()

    def _armar_ui(self) -> None:
        layout_externo = QHBoxLayout(self)

        panel_form = QWidget()
        panel_form.setFixedWidth(_ANCHO_PANEL_FILTROS_GRILLA)
        form = QVBoxLayout(panel_form)

        self.combo_profesional = QComboBox()
        self.combo_profesional.addItem("Todos los profesionales", None)
        self._categoria_por_profesional: dict[int, str] = {}
        for id_, etiqueta, categoria in _opciones_profesional_con_categoria(self.conn, _CATEGORIAS_AISLADAS):
            self.combo_profesional.addItem(etiqueta, id_)
            self._categoria_por_profesional[id_] = categoria
        habilitar_busqueda_profesional(self.combo_profesional)
        self.combo_profesional.currentIndexChanged.connect(self._al_cambiar_profesional)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        # "Período a imputar" (pedido de la clienta): siempre visible,
        # pero fijo en "Período actual" y deshabilitado para A/B — ver
        # `_al_cambiar_profesional`.
        self.etiqueta_periodo_imputar = QLabel("Período a imputar")
        self.combo_periodo_imputar = QComboBox()
        self.combo_periodo_imputar.addItem("Período actual (el de la fecha cargada)", "actual")
        self.combo_periodo_imputar.addItem("Período siguiente", "siguiente")
        # Mismo motivo que en Reservas aisladas (ver esa solapa): el
        # primer ítem agregado ya dispara `currentIndexChanged` de
        # `combo_profesional` antes de que termine de conectarse acá.
        self.combo_periodo_imputar.setEnabled(False)
        form.addWidget(self.etiqueta_periodo_imputar)
        form.addWidget(self.combo_periodo_imputar)

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
        form.addWidget(QLabel("Consultorio"))
        form.addWidget(self.combo_consultorio)

        self.campo_fecha = QDateEdit()
        self.campo_fecha.setDisplayFormat(_FORMATO_FECHA_DIA)
        self.campo_fecha.setLocale(_LOCALE_ES)
        self.campo_fecha.setCalendarPopup(True)
        aplicar_color_sabado_negro(self.campo_fecha)
        instalar_flechas_cambian_fecha_completa(self.campo_fecha)
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

        self.campo_item = QLineEdit()
        self.campo_item.setPlaceholderText("Qué se está cobrando")
        form.addWidget(QLabel("Ítem a cargar"))
        form.addWidget(self.campo_item)

        self.spin_monto = _SpinMonto()
        self.spin_monto.setRange(0, 99_999_999)
        self.spin_monto.setDecimals(2)
        self.spin_monto.setSingleStep(100)
        form.addWidget(QLabel("Monto a cobrar"))
        form.addWidget(self.spin_monto)

        boton_crear = QPushButton("Crear reserva extraordinaria")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.setFixedWidth(_ANCHO_BOTON_EXTRAORDINARIA)
        boton_crear.clicked.connect(self._crear)
        form.addWidget(boton_crear)

        self.boton_modificar = QPushButton("Modificar reserva")
        self.boton_modificar.setObjectName("botonSecundario")
        self.boton_modificar.setFixedWidth(_ANCHO_BOTON_EXTRAORDINARIA)
        self.boton_modificar.clicked.connect(self._modificar_seleccionada)
        form.addWidget(self.boton_modificar)

        self.boton_cancelar = QPushButton("Cancelar reserva")
        self.boton_cancelar.setObjectName("botonSecundario")
        self.boton_cancelar.setFixedWidth(_ANCHO_BOTON_EXTRAORDINARIA)
        self.boton_cancelar.clicked.connect(self._cancelar)
        form.addWidget(self.boton_cancelar)

        form.addStretch()
        layout_externo.addWidget(panel_form)

        columnas = [
            "Profesional", "Localidad", "Edificio", "Unidad", "Consultorio",
            "Día", "Fecha", "Horario", "Ítem", "Monto", "Estado", "Período imputado",
        ]
        self.tabla = QTableWidget(0, len(columnas))
        self.tabla.setHorizontalHeaderLabels(columnas)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        excluir_tabla_del_tab(self.tabla)
        self._orden = OrdenTabla(self.tabla, self.actualizar)
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones)
        instalar_eliminar_con_tecla(self.tabla, self._cancelar)
        layout_externo.addWidget(self.tabla, stretch=1)

        self._foco = instalar_enter_avanza_foco(
            [
                self.combo_profesional, self.combo_periodo_imputar, self.combo_localidad, self.combo_edificio,
                self.combo_unidad, self.combo_consultorio, self.campo_fecha, self.spin_desde, self.spin_hasta,
                self.campo_item, self.spin_monto, boton_crear, self.boton_modificar, self.boton_cancelar,
            ],
            parent=self,
        )
        self._actualizar_botones()
        # `_resetear_formulario` (no solo `_cargar_edificios`, que también
        # llama) para que "Fecha" arranque en HOY en vez del default de
        # `QDateEdit` sin fecha puesta (01-01-2000) — mismo motivo por el
        # que Reservas aisladas fija ese campo recién en su primer
        # `_resetear_formulario`, acá adelantado a la construcción porque
        # esta solapa no tiene un `showEvent` que lo haga por otro lado.
        self._resetear_formulario()

    def _al_cambiar_profesional(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        categoria = self._categoria_por_profesional.get(id_profesional) if id_profesional is not None else None
        editable = _categoria_requiere_periodo_editable(categoria)
        self.combo_periodo_imputar.setEnabled(editable)
        self.combo_periodo_imputar.setCurrentIndex(1 if editable else 0)
        self.actualizar()

    def _cargar_edificios(self) -> None:
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

    def _fila_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._reservas[filas[0].row()]

    def _copiar_mensaje_detalle(self, id_profesional: int, fecha: str) -> None:
        """Mismo mecanismo que Reservas aisladas: confirmar o cancelar una
        reserva extraordinaria carga sola el mensaje de detalle
        actualizado al portapapeles."""
        try:
            texto = mensaje_detalle_reserva_aislada(self.conn, id_profesional=id_profesional, periodo=fecha[:7])
        except ValueError:
            return
        QGuiApplication.clipboard().setText(texto)

    def _crear(self, forzar: bool = False) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Crear reserva extraordinaria", "Elegí un profesional.")
            return
        # Capturado ACÁ, antes de que `_resetear_formulario()` (al final,
        # si todo sale bien) vuelva a reiniciar este combo.
        periodo_a_imputar = self.combo_periodo_imputar.currentData()
        id_consultorio = self.combo_consultorio.currentData()
        if id_consultorio is None:
            QMessageBox.warning(
                self, "Crear reserva extraordinaria", "Elegí localidad, edificio, unidad y consultorio.",
            )
            return
        item = self.campo_item.text().strip()
        if not item:
            QMessageBox.warning(self, "Crear reserva extraordinaria", "Cargá el ítem que se está cobrando.")
            return
        monto = self.spin_monto.value()
        if monto <= 0:
            QMessageBox.warning(self, "Crear reserva extraordinaria", "Cargá el monto a cobrar.")
            return
        fecha = self.campo_fecha.date().toPython().isoformat()
        if not forzar and not confirmar_si_fecha_es_mes_anterior(self, self.conn, fecha):
            return
        if not forzar:
            faltantes = llaves_faltantes_para_reserva(
                self.conn, id_profesional=id_profesional, id_consultorio=id_consultorio,
            ) + placa_faltante_para_reserva(self.conn, id_profesional=id_profesional, id_consultorio=id_consultorio)
            if faltantes and not _confirmar_llave_o_placa_faltante(self, faltantes):
                return
            # Pedido explícito de la clienta ("EN GENERAL"): vista previa
            # de los datos con Confirmar/Cancelar antes de crear — mismo
            # criterio que Reservas regulares/aisladas.
            lineas_confirmacion = [
                f"Profesional: {self.combo_profesional.currentText()}",
                f"Ubicación: {self.combo_localidad.currentText()} - {self.combo_edificio.currentText()} - "
                f"{self.combo_unidad.currentText()} - {self.combo_consultorio.currentText()}",
                f"Fecha: {self.campo_fecha.date().toString('dd-MM-yyyy')}",
                f"Horario: {_fmt_hora(self.spin_desde.value())} a {_fmt_hora(self.spin_hasta.value())}",
                f"Ítem a cargar: {item}",
                f"Monto a cobrar: {formatear_moneda(monto)}",
                f"Período a imputar: {self.combo_periodo_imputar.currentText()}",
            ]
            if not confirmar_datos_antes_de_crear(self, "Crear reserva extraordinaria", lineas_confirmacion):
                return
        try:
            _id, advertencias = crear_reserva_aislada(
                self.conn, id_profesional=id_profesional, id_consultorio=id_consultorio, fecha=fecha,
                hora_inicio=self.spin_desde.value(), hora_fin=self.spin_hasta.value(),
                es_extraordinaria=True, item_extraordinario=item, monto_extraordinario=monto, forzar=forzar,
                # Mismo criterio que Reservas aisladas: se guarda ya
                # resuelto a "AAAA-MM" (no "actual"/"siguiente" tal cual
                # viene del combo), para la columna "Período imputado".
                periodo_imputado=(
                    fecha[:7] if periodo_a_imputar == "actual" else sumar_meses(fecha[:7], 1)
                ),
            )
        except ConflictoBloqueanteError as error:
            confirmacion = QMessageBox.question(
                self, "Conflictos detectados", f"{error}\n\n¿Crear la reserva de todos modos?",
            )
            if confirmacion == QMessageBox.StandardButton.Yes:
                self._crear(forzar=True)
            return
        except ValueError as error:
            QMessageBox.warning(self, "Crear reserva extraordinaria", str(error))
            return
        self.conn.commit()
        regenerar_snapshot_si_corresponde(self.conn, fecha[:7])
        _resolver_periodo_imputar(self.conn, id_profesional, fecha[:7], periodo_a_imputar)
        if advertencias:
            QMessageBox.information(self, "Reserva creada", "Reserva creada con avisos:\n" + "\n".join(advertencias))
        self._copiar_mensaje_detalle(id_profesional, fecha)
        self.actualizar()
        self._resetear_formulario()

    def _cancelar_registro(self, reserva: sqlite3.Row, titulo: str) -> bool:
        try:
            requiere_aviso = cancelar_reserva_aislada(self.conn, reserva["IdReservaAislada"])
        except ValueError as error:
            QMessageBox.warning(self, titulo, str(error))
            return False
        self.conn.commit()
        regenerar_snapshot_si_corresponde(self.conn, reserva["Fecha"][:7])
        if requiere_aviso:
            QMessageBox.information(self, titulo, "Cancelada el mismo día: avisar al profesional.")
        self._copiar_mensaje_detalle(reserva["IdProfesional"], reserva["Fecha"])
        self.actualizar()
        return True

    def _actualizar_botones(self) -> None:
        """Mismo criterio que Reservas regulares/aisladas: "Modificar
        reserva"/"Cancelar reserva" quedan deshabilitados sin ninguna
        fila en foco en la tabla."""
        hay_seleccion = self._fila_seleccionada() is not None
        self.boton_modificar.setEnabled(hay_seleccion)
        self.boton_cancelar.setEnabled(hay_seleccion)

    def _cancelar(self) -> None:
        """Punto #9.1.6 (homólogo de Reservas aisladas): pide
        confirmación explícita antes de cancelar, con los datos
        completos de la reserva (profesional/día/horario/ítem) en vez
        de cancelar directo sin preguntar nada."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            return
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(reserva["IdProfesional"])
        nombre_profesional = _texto_profesional(profesional) if profesional else "?"
        dia_semana = fecha_a_dia_semana(date.fromisoformat(reserva["Fecha"]))
        confirmacion = QMessageBox.question(
            self, "Cancelar reserva",
            f"¿Cancelar la reserva extraordinaria de {nombre_profesional} el {dia_semana} "
            f"{_fmt_fecha(reserva['Fecha'])} de {_fmt_horario(reserva['HoraInicio'], reserva['HoraFin'])} "
            f"({reserva['ItemExtraordinario']})?",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        if self._cancelar_registro(reserva, "Cancelar reserva"):
            self.combo_profesional.setFocus()

    def _modificar_seleccionada(self) -> None:
        """Punto #9.1.4 (homólogo de Reservas regulares/aisladas):
        reusa `_DialogoModificarReservaAislada`/`modificar_reserva_
        aislada` (ya armados genéricos sobre `EsExtraordinaria`, ver
        Reservas aisladas) — edita la fila EXISTENTE (horario, ítem y
        monto) sin cancelarla ni precargar el formulario de alta."""
        reserva = self._fila_seleccionada()
        if reserva is None:
            QMessageBox.warning(self, "Modificar reserva", "Elegí una fila de la tabla para modificar.")
            return
        dialogo = _DialogoModificarReservaAislada(self.conn, reserva, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            advertencias = modificar_reserva_aislada(
                self.conn, reserva["IdReservaAislada"], hora_inicio=dialogo.hora_inicio,
                hora_fin=dialogo.hora_fin, item_extraordinario=dialogo.item_extraordinario,
                monto_extraordinario=dialogo.monto_extraordinario,
            )
        except ConflictoBloqueanteError as error:
            confirmacion = QMessageBox.question(
                self, "Conflictos detectados", f"{error}\n\n¿Modificar la reserva de todos modos?",
            )
            if confirmacion != QMessageBox.StandardButton.Yes:
                return
            advertencias = modificar_reserva_aislada(
                self.conn, reserva["IdReservaAislada"], hora_inicio=dialogo.hora_inicio,
                hora_fin=dialogo.hora_fin, item_extraordinario=dialogo.item_extraordinario,
                monto_extraordinario=dialogo.monto_extraordinario, forzar=True,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Modificar reserva", str(error))
            return
        self.conn.commit()
        regenerar_snapshot_si_corresponde(self.conn, reserva["Fecha"][:7])
        self._copiar_mensaje_detalle(reserva["IdProfesional"], reserva["Fecha"])
        if advertencias:
            QMessageBox.information(
                self, "Reserva modificada", "Reserva modificada con avisos:\n" + "\n".join(advertencias),
            )
        else:
            QMessageBox.information(self, "Modificar reserva", "Reserva modificada con éxito.")
        self.actualizar()

    def _resetear_formulario(self) -> None:
        self.combo_profesional.setCurrentIndex(0)
        if self.combo_localidad.count():
            self.combo_localidad.setCurrentIndex(0)
        self._cargar_edificios()
        self.spin_desde.setValue(9)
        self.spin_hasta.setValue(10)
        hoy = fecha_actual(self.conn)
        self.campo_fecha.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.campo_item.clear()
        self.spin_monto.setValue(0)

    def actualizar(self) -> None:
        id_profesional_filtro = self.combo_profesional.currentData()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        todas = [r for r in obtener_repositorio(self.conn, "ReservaAislada").listar() if r["EsExtraordinaria"]]
        if id_profesional_filtro is not None:
            filtradas = [r for r in todas if r["IdProfesional"] == id_profesional_filtro]
        else:
            filtradas = todas

        filas: list[tuple[sqlite3.Row, sqlite3.Row | None, sqlite3.Row | None]] = []
        for r in filtradas:
            profesional = repo_profesional.obtener(r["IdProfesional"])
            consultorio = self.conn.execute(
                "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS NombreEdificio, "
                "loc.Localidad AS DomicilioLocalidad FROM Consultorio c "
                "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
                "LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad WHERE c.IdConsultorio = ?",
                (r["IdConsultorio"],),
            ).fetchone()
            filas.append((r, profesional, consultorio))
        # Orden por defecto ascendente (pedido explícito de la clienta:
        # "las reservas tienen que aparecer por orden de fecha, lo mas
        # próximo arriba") — antes quedaba descendente (la fecha más
        # lejana en el tiempo primero).
        filas.sort(key=lambda t: (t[0]["Fecha"], t[0]["HoraInicio"]))
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
            self.tabla.setItem(fila_idx, 8, QTableWidgetItem(r["ItemExtraordinario"] or ""))
            self.tabla.setItem(fila_idx, 9, item_numero(formatear_moneda(r["MontoExtraordinario"] or 0.0)))
            self.tabla.setItem(fila_idx, 10, QTableWidgetItem(r["Estado"]))
            self.tabla.setItem(fila_idx, 11, QTableWidgetItem(r["PeriodoImputado"] or ""))
        self.tabla.resizeColumnsToContents()
        self._actualizar_botones()

    @staticmethod
    def _clave_orden(columna: int):
        claves = {
            0: lambda t: clave_orden_codigo(_texto_profesional(t[1])) if t[1] else ("", -1, ""),
            1: lambda t: (t[2]["DomicilioLocalidad"] or "") if t[2] else "",
            2: lambda t: (t[2]["NombreEdificio"] or "") if t[2] else "",
            3: lambda t: (t[2]["Departamento"] or "") if t[2] else "",
            4: lambda t: (t[2]["NumeroConsultorio"] if t[2] else 0),
            5: lambda t: date.fromisoformat(t[0]["Fecha"]).weekday(),
            6: lambda t: t[0]["Fecha"],
            7: lambda t: t[0]["HoraInicio"],
            8: lambda t: t[0]["ItemExtraordinario"] or "",
            9: lambda t: t[0]["MontoExtraordinario"] or 0.0,
            10: lambda t: t[0]["Estado"],
            11: lambda t: t[0]["PeriodoImputado"] or "",
        }
        return claves[columna]
