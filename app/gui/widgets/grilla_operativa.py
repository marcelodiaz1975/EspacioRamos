"""Widget reutilizable de la "Grilla Operativa" (miscelánea, ago-2026):
filtros (localidad/edificio/unidad/día de semana/profesional) + selector
de período (mes en curso por defecto, sin rango Desde/Hasta — la clienta
pidió sacarlo) + modo de visualización + la grilla en sí
(encabezados apilados como en el PDF de Disponibilidad: Día de la
semana > Localidad > Edificio > Unidad > Consultorio, omitiendo
Localidad/Edificio cuando solo hay uno, más las columnas Tipo de
bloque/Horario y las líneas gruesas estructurales, igual que el PDF) +
cuadro de texto de detalle al hacer clic en una celda.

Se monta en la pantalla "Grilla operativa" y, más adelante, en los
formularios de reservas/vacaciones/licencias/ausencias (cada uno la
reutiliza tal cual, según se vaya conectando).

Colores: verde y rojo son versiones bien claras de los que usan los PDF
(para que el código dentro de la celda se siga leyendo con fondo de
color) — no comparten constante con `app/pdf/estilos.py` a propósito,
así un cambio de paleta de un lado no mueve el otro sin querer.
Amarillo y el azul oscuro del filtro de profesional sí quedan iguales
que en el resto de la app."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.gui.estilos import COLOR_AMARILLO, COLOR_AZUL_OSCURO, COLOR_NIVEL_1
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.dias import fecha_a_dia_semana, parsear_periodo, periodo_actual, primer_dia_mes, sumar_meses, ultimo_dia_mes
from app.pdf.estilos import clave_orden_unidad
from app.negocio.grilla import dias_grilla
from app.negocio.grilla_operativa import (
    AMARILLO,
    AZUL_OSCURO,
    BLANCA,
    BLANCO,
    NEGRA,
    ROJO,
    VERDE,
    CeldaGrillaOperativa,
    calcular_grilla_operativa,
    claves_con_ausencia,
)

_COLOR_VERDE_CLARO = "#C8E6C9"
_COLOR_ROJO_CLARO = "#FFCDD2"
_COLOR_HEX = {BLANCO: "#FFFFFF", VERDE: _COLOR_VERDE_CLARO, AMARILLO: COLOR_AMARILLO, ROJO: _COLOR_ROJO_CLARO, AZUL_OSCURO: COLOR_AZUL_OSCURO}
_FUENTE_HEX = {BLANCA: "#FFFFFF"}  # "negra" es el default de _CeldaGrilla, no hace falta mapearla
_ANCHO_CODIGO_CORTO = "A99"  # letra + 2 dígitos
_ANCHO_CODIGO_LARGO = "A999"  # letra + 3 dígitos
_GROSOR_GRUESO = 3  # línea estructural — mismo criterio visual que _GROSOR_GRUESO de grilla_pdf.py

# Columnas fijas de cada fila de datos (igual que "Tipo Bloque"/"Horario" en el PDF).
_COL_TIPO_BLOQUE = 0
_COL_HORARIO = 1
_COL_DATOS_INICIO = 2
_CELDA_VACIA = CeldaGrillaOperativa(
    color_aro=BLANCO, color_centro=BLANCO, color_fuente=NEGRA, codigo=None, detalle="", id_profesional_mostrado=None,
)


def _tipo_bloque_por_hora(conn: sqlite3.Connection, horas: list[int]) -> dict[int, str]:
    filas = conn.execute("SELECT HoraInicio, HoraFin FROM BloqueRigido WHERE Activo = 1").fetchall()
    return {h: ("Rígido" if any(f["HoraInicio"] <= h < f["HoraFin"] for f in filas) else "Flexible") for h in horas}


class _CeldaGrilla(QWidget):
    """Una celda de datos: fondo = color de aro, triángulo derecho
    (1/4 de la celda, dividida con una cruz en diagonal) = color de
    centro (si distinto del aro), código encima. Widget propio (no
    QTableWidgetItem) para poder pintar la división y manejar el clic
    sin un delegate aparte."""

    def __init__(
        self, celda: CeldaGrillaOperativa, clave: tuple[int, str, int], on_click,
        bordes: frozenset[str] = frozenset(), parent=None,
    ):
        super().__init__(parent)
        self.celda = celda
        self._clave = clave
        self._on_click = on_click
        self._bordes = bordes
        self.setMinimumHeight(24)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (nombre impuesto por Qt)
        self._on_click(self._clave)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QColor(_COLOR_HEX[self.celda.color_aro]))
        if self.celda.color_centro != self.celda.color_aro:
            # Celda dividida con una cruz en diagonal (de esquina a
            # esquina) en 4 triángulos — izquierda/arriba/abajo quedan
            # del color de aro (3/4) y el de la derecha pasa al color de
            # centro (1/4).
            centro = rect.center()
            triangulo_derecho = QPolygon([rect.topRight(), QPoint(centro.x(), centro.y()), rect.bottomRight()])
            painter.setBrush(QColor(_COLOR_HEX[self.celda.color_centro]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(triangulo_derecho)
        if self.celda.codigo:
            painter.setPen(QColor(_FUENTE_HEX.get(self.celda.color_fuente, "#000000")))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.celda.codigo)
        _dibujar_bordes_gruesos(painter, rect, self._bordes)
        painter.end()


def _dibujar_bordes_gruesos(painter: QPainter, rect, bordes: frozenset[str]) -> None:
    # Línea fina propia en las 4 caras — reemplaza a la cuadrícula nativa
    # de la tabla (desactivada): con "showGrid" activo, Qt le resta 1px a
    # la altura de columnas angostas como Tipo Bloque/Horario para dejarle
    # lugar a su propia línea, y esas celdas quedan 1px más bajas que las
    # de datos — la línea gruesa de esa fila no se dibuja donde debería.
    # Sin esto, drawRect hereda el brush que haya quedado seteado (el
    # color del triángulo de centro, si esta celda tiene uno) y repinta
    # toda la celda encima del texto ya dibujado.
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("#999999"), 1))
    painter.drawRect(rect.adjusted(0, 0, -1, -1))

    pen = QPen(QColor("#000000"), _GROSOR_GRUESO)
    painter.setPen(pen)
    if "right" in bordes:
        painter.drawLine(rect.topRight(), rect.bottomRight())
    if "bottom" in bordes:
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
    if "left" in bordes:
        painter.drawLine(rect.topLeft(), rect.bottomLeft())
    if "top" in bordes:
        painter.drawLine(rect.topLeft(), rect.topRight())


class _EtiquetaGrilla(QWidget):
    """Celda de texto (encabezado azul o etiqueta de fila) pintada a mano,
    igual que _CeldaGrilla — un QLabel con "border" por CSS achica el
    widget en 1px respecto de sus vecinos pintados con QPainter y las
    líneas gruesas quedan cortadas/desalineadas en el borde; pintando
    todo con el mismo mecanismo se evita ese desfasaje."""

    def __init__(
        self, texto: str, tamano_fuente: int, negrita: bool = True,
        fondo: str | None = None, color_texto: str = "#000000",
        bordes: frozenset[str] = frozenset(), parent=None,
    ):
        super().__init__(parent)
        self._texto = texto
        self._fondo = fondo
        self._color_texto = color_texto
        self._bordes = bordes
        fuente = self.font()
        fuente.setPointSize(tamano_fuente)
        fuente.setBold(negrita)
        self.setFont(fuente)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        rect = self.rect()
        if self._fondo:
            painter.fillRect(rect, QColor(self._fondo))
        painter.setPen(QColor(self._color_texto))
        painter.drawText(rect.adjusted(1, 1, -1, -1), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._texto)
        _dibujar_bordes_gruesos(painter, rect, self._bordes)
        painter.end()


TODOS = object()  # sentinel del ítem "Todas las X" de los filtros en cascada (Localidad/Edificio/Unidad)


def _lista_multiseleccion() -> QListWidget:
    lista = QListWidget()
    lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    lista.setMaximumHeight(90)
    return lista


def _agregar_item_todos(lista: QListWidget, etiqueta: str) -> QListWidgetItem:
    """Ítem "Todas las X" — tildado por defecto (confirmado por la
    clienta), en vez de tildar uno por uno cada valor real de la lista."""
    item = QListWidgetItem(etiqueta)
    fuente = item.font()
    fuente.setBold(True)
    item.setFont(fuente)
    item.setData(Qt.ItemDataRole.UserRole, TODOS)
    lista.addItem(item)
    return item


def _corregir_seleccion_todos(lista: QListWidget) -> None:
    """Mutuamente excluyente con los ítems reales: si al tildar algo real
    queda el ítem "Todas las X" tildado junto con otros (ej. Ctrl+clic),
    se destilda "Todas las X" y quedan los reales — un clic simple ya lo
    resuelve solo (Qt selecciona en exclusiva al clickear sin Ctrl)."""
    seleccionados = lista.selectedItems()
    if len(seleccionados) <= 1:
        return
    item_todos = next((it for it in seleccionados if it.data(Qt.ItemDataRole.UserRole) is TODOS), None)
    if item_todos is not None:
        lista.blockSignals(True)
        item_todos.setSelected(False)
        lista.blockSignals(False)


def _seleccionar_todos(lista: QListWidget) -> None:
    """Vuelve al estado por defecto: solo tildado el ítem "Todas las X"."""
    for i in range(lista.count()):
        item = lista.item(i)
        item.setSelected(item.data(Qt.ItemDataRole.UserRole) is TODOS)


def _ids_seleccionados(lista: QListWidget) -> list[int]:
    """[] si está tildado "Todas las X" (sin filtro) — para usar como
    condición de un WHERE de un nivel intermedio de la cascada (Localidad/
    Edificio), donde "sin filtro" ya significa "no restringir"."""
    return [
        item.data(Qt.ItemDataRole.UserRole) for item in lista.selectedItems()
        if item.data(Qt.ItemDataRole.UserRole) is not TODOS
    ]


def _ids_reales(lista: QListWidget) -> list[int]:
    """Como `_ids_seleccionados`, pero para el nivel hoja del filtro (acá,
    Unidad): con "Todas las X" tildado, devuelve el conjunto real
    COMPLETO de la lista en vez de [] — al contrario que el nivel
    intermedio, acá [] tiene que seguir significando "nada tildado" (el
    caso especial de un profesional nuevo sin nada reservado todavía,
    ver `filtrar_por_unidades`)."""
    seleccionados = lista.selectedItems()
    if any(item.data(Qt.ItemDataRole.UserRole) is TODOS for item in seleccionados):
        return [
            lista.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lista.count())
            if lista.item(i).data(Qt.ItemDataRole.UserRole) is not TODOS
        ]
    return [item.data(Qt.ItemDataRole.UserRole) for item in seleccionados]


class _FiltroColapsable(QWidget):
    """Envuelve una QListWidget de multiselección (Localidad/Edificio/
    Unidad/Consultorio) para que arranque colapsada — mostrando solo un
    botón-resumen de la selección vigente ("Todas las localidades", "2
    seleccionadas") — y recién se despliegue al pincharla, en vez de
    mostrar la lista entera siempre abierta (confirmado por la clienta)."""

    def __init__(self, lista: QListWidget, parent=None):
        super().__init__(parent)
        self._lista = lista
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._boton = QPushButton()
        self._boton.setCheckable(True)
        self._boton.clicked.connect(self._alternar)
        layout.addWidget(self._boton)
        layout.addWidget(lista)
        lista.setVisible(False)
        lista.itemSelectionChanged.connect(self.actualizar_resumen)
        self.actualizar_resumen()

    def _alternar(self) -> None:
        self._lista.setVisible(self._boton.isChecked())

    def actualizar_resumen(self) -> None:
        """Público: hay que llamarlo a mano después de repoblar la lista
        con `blockSignals(True)` (como hacen los `_cargar_*` en cascada),
        porque en ese tramo `itemSelectionChanged` no dispara solo."""
        seleccionados = self._lista.selectedItems()
        if len(seleccionados) == 1:
            self._boton.setText(seleccionados[0].text())
        elif not seleccionados:
            self._boton.setText("(nada seleccionado)")
        else:
            self._boton.setText(f"{len(seleccionados)} seleccionadas")


def unidades_con_reserva_vigente(conn: sqlite3.Connection, id_profesional: int | None) -> list[int]:
    """Unidades donde el profesional ya tiene alguna reserva regular
    cargada — para que quien embeba la grilla como vista previa
    (Reservas, Vacaciones, Licencias, Ausencias) la acote a "lo que el
    profesional ya tiene reservado" sin que el operador tenga que tocar
    el filtro de Unidad a mano. Devuelve `[]` para un profesional nuevo
    sin nada reservado todavía."""
    if id_profesional is None:
        return []
    filas = conn.execute(
        "SELECT DISTINCT u.IdUnidad FROM ReservaRegular r "
        "JOIN Consultorio c ON c.IdConsultorio = r.IdConsultorio "
        "JOIN Unidad u ON u.IdUnidad = c.IdUnidad WHERE r.IdProfesional = ?",
        (id_profesional,),
    ).fetchall()
    return [f["IdUnidad"] for f in filas]


def dias_con_reserva_vigente(conn: sqlite3.Connection, id_profesional: int | None) -> list[str]:
    """Días de la semana en los que el profesional ya tiene alguna
    reserva regular cargada — mismo espíritu que `unidades_con_reserva_
    vigente`, para acotar también el filtro de Día de la semana de la
    vista previa y que no quede tan alargada."""
    if id_profesional is None:
        return []
    filas = conn.execute(
        "SELECT DISTINCT DiaSemana FROM ReservaRegular WHERE IdProfesional = ?", (id_profesional,)
    ).fetchall()
    return [f["DiaSemana"] for f in filas]


def pares_dia_unidad_con_reserva_vigente(conn: sqlite3.Connection, id_profesional: int | None) -> set[tuple[str, int]]:
    """Combinaciones (día, unidad) donde el profesional tiene efectivamente
    alguna reserva regular — más preciso que cruzar `unidades_con_reserva_
    vigente` con `dias_con_reserva_vigente` por separado: ese cruce
    muestra TODAS las unidades del profesional en TODOS sus días, aunque
    en un día puntual solo tenga reservado uno de esos lugares. Se usa
    para acotar la grilla exactamente a lo que el profesional tiene
    reservado (`GrillaOperativaWidget.filtrar_por_pares_unidad_dia`)."""
    if id_profesional is None:
        return set()
    filas = conn.execute(
        "SELECT DISTINCT r.DiaSemana, u.IdUnidad FROM ReservaRegular r "
        "JOIN Consultorio c ON c.IdConsultorio = r.IdConsultorio "
        "JOIN Unidad u ON u.IdUnidad = c.IdUnidad WHERE r.IdProfesional = ?",
        (id_profesional,),
    ).fetchall()
    return {(f["DiaSemana"], f["IdUnidad"]) for f in filas}


def pares_dia_unidad_con_reserva(conn: sqlite3.Connection, id_profesional: int | None) -> set[tuple[str, int]]:
    """Como `pares_dia_unidad_con_reserva_vigente`, pero sumando también
    las reservas aisladas confirmadas (su Fecha, no un patrón recurrente)
    — mismo criterio que `unidades_con_reserva`/`dias_con_reserva`, para
    la vista previa de Reservas aisladas."""
    if id_profesional is None:
        return set()
    pares = set(pares_dia_unidad_con_reserva_vigente(conn, id_profesional))
    filas = conn.execute(
        "SELECT DISTINCT a.Fecha, u.IdUnidad FROM ReservaAislada a "
        "JOIN Consultorio c ON c.IdConsultorio = a.IdConsultorio "
        "JOIN Unidad u ON u.IdUnidad = c.IdUnidad WHERE a.IdProfesional = ? AND a.Estado = 'Confirmada'",
        (id_profesional,),
    ).fetchall()
    for f in filas:
        pares.add((fecha_a_dia_semana(date.fromisoformat(f["Fecha"])), f["IdUnidad"]))
    return pares


def unidades_con_reserva(conn: sqlite3.Connection, id_profesional: int | None) -> list[int]:
    """Como `unidades_con_reserva_vigente`, pero considerando también las
    reservas aisladas confirmadas — para la vista previa de Reservas
    aisladas, donde el profesional puede no tener nunca una reserva
    regular (ej. categoría A)."""
    if id_profesional is None:
        return []
    filas = conn.execute(
        "SELECT DISTINCT u.IdUnidad FROM ReservaRegular r "
        "JOIN Consultorio c ON c.IdConsultorio = r.IdConsultorio "
        "JOIN Unidad u ON u.IdUnidad = c.IdUnidad WHERE r.IdProfesional = ? "
        "UNION "
        "SELECT DISTINCT u.IdUnidad FROM ReservaAislada a "
        "JOIN Consultorio c ON c.IdConsultorio = a.IdConsultorio "
        "JOIN Unidad u ON u.IdUnidad = c.IdUnidad WHERE a.IdProfesional = ? AND a.Estado = 'Confirmada'",
        (id_profesional, id_profesional),
    ).fetchall()
    return [f["IdUnidad"] for f in filas]


def dias_con_reserva(conn: sqlite3.Connection, id_profesional: int | None) -> list[str]:
    """Como `dias_con_reserva_vigente`, pero sumando el día de la semana
    de cada reserva aislada confirmada del profesional (su Fecha, no un
    patrón recurrente) — mismo uso que `unidades_con_reserva`."""
    if id_profesional is None:
        return []
    dias = set(dias_con_reserva_vigente(conn, id_profesional))
    filas = conn.execute(
        "SELECT Fecha FROM ReservaAislada WHERE IdProfesional = ? AND Estado = 'Confirmada'", (id_profesional,)
    ).fetchall()
    for f in filas:
        dias.add(fecha_a_dia_semana(date.fromisoformat(f["Fecha"])))
    return list(dias)


def _opciones_profesional_grilla(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    """Mismo formato canónico "{código} - {tratamiento} {nombre}
    {apellido}" que `reservas._texto_profesional` — duplicado acá (en
    vez de importado) porque `reservas.py` ya importa este módulo y
    crearía un import circular."""
    filas = conn.execute(
        "SELECT IdProfesional, IdCodigo, Tratamiento, Apellido, NombrePila FROM Profesional ORDER BY Apellido"
    ).fetchall()
    opciones = []
    for p in filas:
        partes = [x for x in (p["Tratamiento"], p["NombrePila"], p["Apellido"]) if x]
        nombre = " ".join(partes) if partes else p["Apellido"]
        texto = f"{p['IdCodigo']} - {nombre}" if p["IdCodigo"] else nombre
        opciones.append((p["IdProfesional"], texto))
    return opciones


class GrillaOperativaWidget(QWidget):
    def __init__(
        self, conn: sqlite3.Connection, on_actualizar: Callable[[list[int]], None] | None = None, parent=None,
    ):
        super().__init__(parent)
        self.conn = conn
        self._on_actualizar = on_actualizar
        self._resultado: dict[tuple[int, str, int], CeldaGrillaOperativa] = {}
        self._pares_dia_unidad: set[tuple[str, int]] | None = None
        self._resaltar_ausencias = False
        self._filtro_exclusivo_profesional = False
        self._armar_ui()
        self._cargar_localidades()
        self.actualizar()

    # ------------------------------------------------------------- armado

    def _armar_ui(self) -> None:
        layout_principal = QHBoxLayout(self)

        panel_filtros = QGroupBox("Filtros")
        panel_filtros.setMaximumWidth(260)
        layout_filtros = QVBoxLayout(panel_filtros)

        layout_filtros.addWidget(QLabel("Localidad"))
        self.lista_localidad = _lista_multiseleccion()
        self.lista_localidad.itemSelectionChanged.connect(self._cargar_edificios)
        self._filtro_localidad = _FiltroColapsable(self.lista_localidad)
        layout_filtros.addWidget(self._filtro_localidad)

        layout_filtros.addWidget(QLabel("Edificio"))
        self.lista_edificio = _lista_multiseleccion()
        self.lista_edificio.itemSelectionChanged.connect(self._cargar_unidades)
        self._filtro_edificio = _FiltroColapsable(self.lista_edificio)
        layout_filtros.addWidget(self._filtro_edificio)

        layout_filtros.addWidget(QLabel("Unidad"))
        self.lista_unidad = _lista_multiseleccion()
        self.lista_unidad.itemSelectionChanged.connect(self._unidad_seleccion_cambio)
        self._filtro_unidad = _FiltroColapsable(self.lista_unidad)
        layout_filtros.addWidget(self._filtro_unidad)

        layout_filtros.addWidget(QLabel("Día de la semana"))
        self._checks_dia: dict[str, QCheckBox] = {}
        contenedor_dias = QWidget()
        layout_dias = QVBoxLayout(contenedor_dias)
        layout_dias.setContentsMargins(0, 0, 0, 0)
        for dia in dias_grilla(self.conn):
            check = QCheckBox(dia)
            check.setChecked(True)
            check.stateChanged.connect(self.actualizar)
            self._checks_dia[dia] = check
            layout_dias.addWidget(check)
        layout_filtros.addWidget(contenedor_dias)

        layout_filtros.addWidget(QLabel("Profesional"))
        self.campo_profesional = QComboBox()
        self.campo_profesional.addItem("Sin selección", None)
        for id_, etiqueta in _opciones_profesional_grilla(self.conn):
            self.campo_profesional.addItem(etiqueta, id_)
        habilitar_busqueda_profesional(self.campo_profesional)
        self.campo_profesional.currentIndexChanged.connect(self.actualizar)
        layout_filtros.addWidget(self.campo_profesional)

        layout_filtros.addStretch()
        layout_principal.addWidget(panel_filtros)

        panel_grilla = QWidget()
        layout_grilla = QVBoxLayout(panel_grilla)

        fila_controles = QHBoxLayout()
        fila_controles.addWidget(QLabel("Período:"))
        self.combo_periodo = QComboBox()
        periodo_base = periodo_actual(self.conn)
        for i in range(13):
            periodo = sumar_meses(periodo_base, i)
            self.combo_periodo.addItem(periodo, periodo)
        self.combo_periodo.currentIndexChanged.connect(self._periodo_cambiado)
        fila_controles.addWidget(self.combo_periodo)

        fila_controles.addWidget(QLabel("Visualización:"))
        self.combo_modo = QComboBox()
        self.combo_modo.addItem("Reservas regulares", "regular")
        self.combo_modo.addItem("Reservas aisladas", "aislada")
        self.combo_modo.currentIndexChanged.connect(self.actualizar)
        fila_controles.addWidget(self.combo_modo)
        fila_controles.addStretch()
        layout_grilla.addLayout(fila_controles)

        self.tabla = QTableWidget()
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.horizontalHeader().setVisible(False)
        self.tabla.verticalHeader().setVisible(False)
        # La cuadrícula fina la dibuja cada celda por su cuenta (ver
        # _dibujar_bordes_gruesos) — la nativa de Qt le resta 1px de alto
        # a columnas angostas y desalinea las líneas gruesas.
        self.tabla.setShowGrid(False)
        self.tabla.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout_grilla.addWidget(self.tabla, stretch=1)

        layout_grilla.addWidget(QLabel("Detalle:"))
        self.texto_detalle = QTextEdit()
        self.texto_detalle.setReadOnly(True)
        self.texto_detalle.setMaximumHeight(90)
        layout_grilla.addWidget(self.texto_detalle)

        layout_principal.addWidget(panel_grilla, stretch=1)

    def _periodo_cambiado(self) -> None:
        self.actualizar()

    # ------------------------------------------------------------ filtros

    def _cargar_localidades(self) -> None:
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
        sql = "SELECT u.IdUnidad, u.Departamento, e.Nombre AS NombreEdificio FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio"
        parametros: list = []
        if ids_edificio:
            placeholders = ", ".join("?" for _ in ids_edificio)
            sql += f" WHERE u.IdEdificio IN ({placeholders})"
            parametros = ids_edificio
        filas = self.conn.execute(sql, parametros).fetchall()
        # Orden por edificio (alfabético) y, dentro de cada uno, por piso
        # (PB, después EP, después ascendente numérico) — clave_orden_unidad
        # no se puede expresar en el ORDER BY de SQL.
        filas = sorted(filas, key=lambda f: (f["NombreEdificio"], clave_orden_unidad(f["Departamento"])))
        for fila in filas:
            item = QListWidgetItem(f"{fila['NombreEdificio']} - {fila['Departamento']}")
            item.setData(Qt.ItemDataRole.UserRole, fila["IdUnidad"])
            self.lista_unidad.addItem(item)
        _seleccionar_todos(self.lista_unidad)
        self.lista_unidad.blockSignals(False)
        self._filtro_unidad.actualizar_resumen()
        self.actualizar()

    def _dias_seleccionados(self) -> list[str]:
        return [dia for dia, check in self._checks_dia.items() if check.isChecked()]

    def _id_profesional_filtro(self) -> int | None:
        return self.campo_profesional.currentData()

    def ids_unidad_seleccionadas(self) -> list[int]:
        """Unidades actualmente tildadas en el filtro — la misma lista que
        recibe `on_actualizar` en cada refresco, para que otras secciones
        de la pantalla (valores, estadísticas) se mantengan sincronizadas
        con la selección de la grilla sin necesidad de leerla de vuelta
        (el callback puede dispararse durante `__init__`, antes de que el
        que lo llama termine de guardar la referencia al widget)."""
        return _ids_reales(self.lista_unidad)

    def filtrar_por_unidad(self, id_unidad: int | None) -> None:
        """Acota la selección de unidades a una sola — o la vuelve a
        mostrar todas con `None`. Pensado para cuando otro formulario (ej.
        el alta de una reserva) embebe la grilla como vista previa y
        quiere mostrarla acotada al consultorio que se está por reservar,
        sin que el usuario tenga que tocar el filtro de Unidad a mano."""
        self.filtrar_por_unidades([id_unidad] if id_unidad is not None else None)

    def filtrar_por_unidades(self, ids_unidad: list[int] | None) -> None:
        """Como `filtrar_por_unidad`, pero para un conjunto — para cuando
        el formulario no reserva un consultorio puntual (ej. Vacaciones/
        Licencias/Ausencias) sino que afecta a todas las unidades donde
        el profesional ya tiene algo reservado.

        `None` (sin lista) vuelve a mostrar todas las unidades — filtro
        libre. Una lista se toma tal cual, incluida la vacía: eso deja la
        grilla sin ninguna unidad tildada (grilla vacía), a propósito
        para el caso de un profesional nuevo sin nada reservado todavía.
        Quien la llame decide cuál de las dos quiere pasando `None` o
        `[]` según corresponda."""
        self.lista_unidad.blockSignals(True)
        self.lista_unidad.clearSelection()
        if ids_unidad is None:
            _seleccionar_todos(self.lista_unidad)
        else:
            objetivo = set(ids_unidad)
            for i in range(self.lista_unidad.count()):
                item = self.lista_unidad.item(i)
                if item.data(Qt.ItemDataRole.UserRole) in objetivo:
                    item.setSelected(True)
        self.lista_unidad.blockSignals(False)
        self._filtro_unidad.actualizar_resumen()
        self.actualizar()

    def filtrar_por_dias(self, dias: list[str] | None) -> None:
        """Como `filtrar_por_unidades`, pero para el filtro de Día de la
        semana: `None` tilda todos los días (sin filtro); una lista —
        incluida la vacía — tilda exactamente esos, dejando la grilla sin
        ningún día marcado si viene vacía."""
        objetivo = set(self._checks_dia) if dias is None else set(dias)
        for dia, check in self._checks_dia.items():
            check.blockSignals(True)
            check.setChecked(dia in objetivo)
            check.blockSignals(False)
        self.actualizar()

    def filtrar_por_pares_unidad_dia(self, pares: set[tuple[str, int]] | None) -> None:
        """Restringe las columnas mostradas a los (día, unidad) donde el
        profesional tiene efectivamente algo reservado — más preciso que
        cruzar el filtro de Unidad con el de Día (que muestra TODAS las
        unidades elegidas en TODOS los días elegidos, aunque el
        profesional no tenga nada en esa combinación puntual: ej. no
        mostrar el edificio del miércoles también el lunes si ese lunes
        no tiene nada ahí). `None` saca la restricción — vuelve al cruce
        completo. Los consultorios de cada unidad se siguen mostrando
        todos, aunque tenga reservado solo uno."""
        self._pares_dia_unidad = set(pares) if pares is not None else None
        self.actualizar()

    def activar_resalte_ausencias(self, activar: bool = True) -> None:
        """Enciende el resalte en verde con letra negra de los horarios
        propios del profesional filtrado (celda azul oscuro) donde además
        tiene una ausencia registrada — solo lo usa la pantalla de
        Ausencias, el resto de las que embeben esta grilla queda con el
        comportamiento de siempre."""
        self._resaltar_ausencias = activar
        self.actualizar()

    def activar_filtro_exclusivo_profesional(self, activar: bool = True) -> None:
        """Con un profesional elegido en el filtro, no alcanza con
        pintarlo de azul entre lo demás — hay que mostrar ÚNICAMENTE sus
        propias celdas, dejando en blanco cualquier otra (aunque el
        consultorio esté ocupado por otro profesional a otra hora). Pensado
        para los usos "vista previa" embebidos (Reservas, Vacaciones,
        Licencias, Ausencias): la pantalla de Grilla operativa standalone
        no activa esto, ahí sí importa ver quién más ocupa cada lugar."""
        self._filtro_exclusivo_profesional = activar
        self.actualizar()

    def filtrar_por_profesional(self, id_profesional: int | None) -> None:
        """Fija el filtro de profesional (el que pinta de azul su celda
        actual) a uno puntual, o lo limpia con `None` — mismo uso que
        `filtrar_por_unidad`."""
        indice = self.campo_profesional.findData(id_profesional)
        self.campo_profesional.blockSignals(True)
        self.campo_profesional.setCurrentIndex(indice if indice >= 0 else 0)
        self.campo_profesional.blockSignals(False)
        self.actualizar()

    # ------------------------------------------------------------- grilla

    def _unidad_seleccion_cambio(self) -> None:
        _corregir_seleccion_todos(self.lista_unidad)
        self._filtro_unidad.actualizar_resumen()
        self.actualizar()

    def actualizar(self) -> None:
        self._actualizar_grilla()
        if self._on_actualizar:
            self._on_actualizar(self.ids_unidad_seleccionadas())

    def _actualizar_grilla(self) -> None:
        ids_unidad = _ids_reales(self.lista_unidad)
        dias = self._dias_seleccionados()
        periodo = self.combo_periodo.currentData()
        modo = self.combo_modo.currentData() or "regular"

        if not ids_unidad or not dias or not periodo:
            self.tabla.setRowCount(0)
            self.tabla.setColumnCount(0)
            self.tabla.setMinimumHeight(0)
            self._resultado = {}
            return

        columnas = self._columnas(ids_unidad, dias)
        if not columnas:
            self.tabla.setRowCount(0)
            self.tabla.setColumnCount(0)
            self.tabla.setMinimumHeight(0)
            self._resultado = {}
            return

        cfg = self.conn.execute(
            "SELECT HoraInicioGrilla, HoraFinGrilla FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        hora_ini = int(cfg["HoraInicioGrilla"]) if cfg else 8
        hora_fin = int(cfg["HoraFinGrilla"]) if cfg else 22
        horas = list(range(hora_ini, hora_fin))

        ids_consultorio = sorted({c["id_consultorio"] for c in columnas})
        id_profesional_filtro = self._id_profesional_filtro()
        ausente_en = None
        if self._resaltar_ausencias and id_profesional_filtro is not None:
            anio, mes = parsear_periodo(periodo)
            desde = primer_dia_mes(anio, mes).isoformat()
            hasta = ultimo_dia_mes(anio, mes).isoformat()
            ausente_en = claves_con_ausencia(
                self.conn, id_profesional_filtro, ids_consultorio, dias, hora_ini, hora_fin, desde, hasta,
            )
        self._resultado = calcular_grilla_operativa(
            self.conn, ids_consultorio, dias, hora_ini, hora_fin, periodo,
            modo=modo, id_profesional_filtro=id_profesional_filtro, ausente_en=ausente_en,
        )
        if self._filtro_exclusivo_profesional and id_profesional_filtro is not None:
            self._resultado = {
                clave: celda if celda.id_profesional_mostrado == id_profesional_filtro else _CELDA_VACIA
                for clave, celda in self._resultado.items()
            }
        self._construir_tabla(columnas, horas)

    def _columnas(self, ids_unidad: list[int], dias: list[str]) -> list[dict]:
        placeholders = ", ".join("?" for _ in ids_unidad)
        filas = self.conn.execute(
            f"""
            SELECT c.IdConsultorio, c.NumeroConsultorio, u.IdUnidad, u.Departamento,
                   e.IdEdificio, e.Nombre AS NombreEdificio, e.DomicilioLocalidad
            FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
            WHERE u.IdUnidad IN ({placeholders})
            """,
            ids_unidad,
        ).fetchall()
        base = [
            {
                "id_consultorio": f["IdConsultorio"], "numero_consultorio": f["NumeroConsultorio"],
                "id_unidad": f["IdUnidad"], "departamento": f["Departamento"],
                "id_edificio": f["IdEdificio"], "nombre_edificio": f["NombreEdificio"],
                "localidad": f["DomicilioLocalidad"] or "(Sin localidad)",
            }
            for f in filas
        ]
        # Localidad/Edificio alfabético (ya lo hacía SQL); Unidad por piso
        # (PB, EP, ascendente numérico — clave_orden_unidad, no expresable
        # en SQL) y Consultorio numérico ascendente.
        base.sort(key=lambda c: (c["localidad"], c["nombre_edificio"], clave_orden_unidad(c["departamento"]), c["numero_consultorio"]))
        columnas = []
        for dia in dias:
            for base_col in base:
                if self._pares_dia_unidad is not None and (dia, base_col["id_unidad"]) not in self._pares_dia_unidad:
                    continue
                columnas.append({**base_col, "dia": dia})
        return columnas

    def _construir_tabla(self, columnas: list[dict], horas: list[int]) -> None:
        n_localidades = len({c["localidad"] for c in columnas})
        n_edificios = len({c["id_edificio"] for c in columnas})
        mostrar_localidad = n_localidades > 1
        mostrar_edificio = n_edificios > 1

        filas_encabezado = 3 + int(mostrar_localidad) + int(mostrar_edificio)  # Día [+Localidad][+Edificio] + Unidad + Consultorio
        n_filas = filas_encabezado + len(horas)
        n_columnas = _COL_DATOS_INICIO + len(columnas)

        # setRowCount(0)/setColumnCount(0) primero: QTableWidget.clear() no
        # garantiza liberar los cellWidget de la grilla anterior, y sin esto
        # quedan widgets huérfanos superpuestos al reconstruir con otros
        # filtros.
        self.tabla.setRowCount(0)
        self.tabla.setColumnCount(0)
        self.tabla.setRowCount(n_filas)
        self.tabla.setColumnCount(n_columnas)

        ancho_columna = self._ancho_columna(columnas, horas)
        self.tabla.setColumnWidth(_COL_TIPO_BLOQUE, 45)
        self.tabla.setColumnWidth(_COL_HORARIO, 50)
        for col in range(_COL_DATOS_INICIO, n_columnas):
            self.tabla.setColumnWidth(col, ancho_columna)
        for fila in range(filas_encabezado):
            self.tabla.setRowHeight(fila, 26)
        for fila in range(filas_encabezado, n_filas):
            self.tabla.setRowHeight(fila, 24)

        limites_dia = self._limites_dia(columnas)
        es_primera_fila_encabezado = 0  # la fila "Día de la semana" siempre es la fila 0
        es_ultima_fila_encabezado = filas_encabezado - 1  # la fila "Consultorio"

        fila_actual = 0
        self._agregar_encabezado_agrupado(
            fila_actual, columnas, lambda c: c["dia"], "Día de la semana", limites_dia,
            es_primera_fila_encabezado, es_ultima_fila_encabezado, mayusculas=True,
        )
        fila_actual += 1
        if mostrar_localidad:
            self._agregar_encabezado_agrupado(
                fila_actual, columnas, lambda c: (c["dia"], c["localidad"]), "Localidad", limites_dia,
                es_primera_fila_encabezado, es_ultima_fila_encabezado,
            )
            fila_actual += 1
        if mostrar_edificio:
            self._agregar_encabezado_agrupado(
                fila_actual, columnas, lambda c: (c["dia"], c["localidad"], c["nombre_edificio"]), "Edificio",
                limites_dia, es_primera_fila_encabezado, es_ultima_fila_encabezado,
            )
            fila_actual += 1
        self._agregar_encabezado_agrupado(
            fila_actual, columnas, lambda c: (c["dia"], c["localidad"], c["nombre_edificio"], c["id_unidad"]),
            "Unidad", limites_dia, es_primera_fila_encabezado, es_ultima_fila_encabezado, texto=lambda c: c["departamento"],
        )
        fila_actual += 1
        self._agregar_encabezado_consultorio(fila_actual, columnas, limites_dia, es_ultima_fila_encabezado)
        fila_actual += 1

        tipo_por_hora = _tipo_bloque_por_hora(self.conn, horas)
        limites_bloque = {
            i for i, h in enumerate(horas)
            if i == len(horas) - 1 or tipo_por_hora[h] != tipo_por_hora[horas[i + 1]]
        }
        self._agregar_columna_tipo_bloque(filas_encabezado, horas, tipo_por_hora)

        for i, hora in enumerate(horas):
            fila = filas_encabezado + i
            borde_inferior = i in limites_bloque
            bordes_horario: set[str] = {"right"}
            if borde_inferior:
                bordes_horario.add("bottom")
            self._poner_texto_dato_fila(fila, _COL_HORARIO, f"{hora}:00", bordes=frozenset(bordes_horario))
            for j, columna in enumerate(columnas):
                col = _COL_DATOS_INICIO + j
                clave = (columna["id_consultorio"], columna["dia"], hora)
                celda = self._resultado.get(clave)
                if celda is None:
                    continue
                bordes_dato: set[str] = set()
                if j in limites_dia:
                    bordes_dato.add("right")
                if borde_inferior:
                    bordes_dato.add("bottom")
                widget = _CeldaGrilla(celda, clave, self._mostrar_detalle, bordes=frozenset(bordes_dato))
                self.tabla.setCellWidget(fila, col, widget)

        # Alto mínimo = suma exacta de las filas que se acaban de armar, para
        # que la grilla se vea siempre entera (sin scrollbar interno) y sea
        # el contenedor que la embebe (splitter/quien la use) el que crezca
        # para darle lugar, en vez de recortarla a un alto fijo arbitrario.
        alto_filas_encabezado = sum(self.tabla.rowHeight(f) for f in range(filas_encabezado))
        alto_filas_datos = sum(self.tabla.rowHeight(f) for f in range(filas_encabezado, n_filas))
        self.tabla.setMinimumHeight(alto_filas_encabezado + alto_filas_datos + 4)

    def _limites_dia(self, columnas: list[dict]) -> set[int]:
        return {i for i in range(len(columnas)) if i == len(columnas) - 1 or columnas[i]["dia"] != columnas[i + 1]["dia"]}

    def _agregar_columna_tipo_bloque(self, filas_encabezado: int, horas: list[int], tipo_por_hora: dict[int, str]) -> None:
        inicio = 0
        for i in range(1, len(horas) + 1):
            if i == len(horas) or tipo_por_hora[horas[i]] != tipo_por_hora[horas[inicio]]:
                self._poner_texto_dato_fila(
                    filas_encabezado + inicio, _COL_TIPO_BLOQUE, tipo_por_hora[horas[inicio]],
                    span_filas=i - inicio, bordes=frozenset({"left", "bottom"}),
                )
                inicio = i

    def _ancho_columna(self, columnas: list[dict], horas: list[int]) -> int:
        codigos_largos = any(
            celda.codigo and len(celda.codigo) > 3
            for c in columnas
            for h in horas
            if (celda := self._resultado.get((c["id_consultorio"], c["dia"], h))) is not None
        )
        metrica = self.fontMetrics()
        texto = _ANCHO_CODIGO_LARGO if codigos_largos else _ANCHO_CODIGO_CORTO
        return metrica.horizontalAdvance(texto) + 14

    def _agregar_encabezado_agrupado(
        self, fila: int, columnas: list[dict], clave_grupo, etiqueta_columna_0: str, limites_dia: set[int],
        primera_fila: int, ultima_fila: int, texto=None, mayusculas: bool = False,
    ) -> None:
        # Columna de etiqueta (Tipo Bloque/Horario fusionadas): además del
        # recuadro de "todo lo azul junto" (arriba en la primera fila,
        # abajo en la última), siempre lleva el borde izquierdo/derecho
        # que la separa del resto — es el mismo recuadro que envuelve
        # Tipo Bloque + Horario de punta a punta (encabezado y datos).
        bordes_etiqueta = {"left", "right"}
        if fila == primera_fila:
            bordes_etiqueta.add("top")
        if fila == ultima_fila:
            bordes_etiqueta.add("bottom")
        self._poner_texto_encabezado(fila, _COL_TIPO_BLOQUE, etiqueta_columna_0, span=2, bordes=frozenset(bordes_etiqueta))

        inicio = 0
        actual = clave_grupo(columnas[0])
        for i in range(1, len(columnas) + 1):
            clave = clave_grupo(columnas[i]) if i < len(columnas) else None
            if clave != actual:
                texto_grupo = texto(columnas[inicio]) if texto else str(actual[-1] if isinstance(actual, tuple) else actual)
                if mayusculas:
                    texto_grupo = texto_grupo.upper()
                bordes: set[str] = set()
                if (i - 1) in limites_dia:
                    bordes.add("right")
                if fila == primera_fila:
                    bordes.add("top")
                if fila == ultima_fila:
                    bordes.add("bottom")
                self._poner_texto_encabezado(
                    fila, _COL_DATOS_INICIO + inicio, texto_grupo, span=i - inicio, bordes=frozenset(bordes),
                )
                inicio = i
                actual = clave

    def _agregar_encabezado_consultorio(
        self, fila: int, columnas: list[dict], limites_dia: set[int], ultima_fila: int,
    ) -> None:
        bordes_etiqueta = {"left", "right", "bottom"} if fila == ultima_fila else {"left", "right"}
        self._poner_texto_encabezado(fila, _COL_TIPO_BLOQUE, "Consultorio", span=2, bordes=frozenset(bordes_etiqueta))
        for i, columna in enumerate(columnas):
            bordes: set[str] = set()
            if i in limites_dia:
                bordes.add("right")
            if fila == ultima_fila:
                bordes.add("bottom")
            self._poner_texto_encabezado(
                fila, _COL_DATOS_INICIO + i, str(columna["numero_consultorio"]), bordes=frozenset(bordes),
            )

    def _poner_texto_encabezado(
        self, fila: int, col: int, texto: str, span: int = 1, bordes: frozenset[str] = frozenset(),
    ) -> None:
        # Las columnas de etiqueta (Tipo Bloque/Horario fusionadas) tienen
        # textos largos ("Día de la semana") — letra más chica ahí para
        # que entren en 2-3 líneas en vez de desbordar la celda.
        tamano = 7 if col == _COL_TIPO_BLOQUE else 8
        etiqueta = _EtiquetaGrilla(texto, tamano, fondo=COLOR_NIVEL_1, color_texto="#FFFFFF", bordes=bordes)
        if span > 1:
            self.tabla.setSpan(fila, col, 1, span)
        self.tabla.setCellWidget(fila, col, etiqueta)

    def _poner_texto_dato_fila(
        self, fila: int, col: int, texto: str, span_filas: int = 1, bordes: frozenset[str] = frozenset(),
    ) -> None:
        etiqueta = _EtiquetaGrilla(texto, 7, bordes=bordes)
        if span_filas > 1:
            self.tabla.setSpan(fila, col, span_filas, 1)
        self.tabla.setCellWidget(fila, col, etiqueta)

    def _mostrar_detalle(self, clave: tuple[int, str, int]) -> None:
        celda = self._resultado.get(clave)
        self.texto_detalle.setPlainText(celda.detalle if celda else "")
