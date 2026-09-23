"""Ex pantalla "Vista rápida" (ex "Grilla operativa", punto 21 de la
miscelánea, ago-2026). Reordenamiento de formularios (Excel de la
clienta): la pantalla en sí se retira — sus tres solapas se repartieron
así:

- Grilla semanal: pasa a `_PanelGrillaSemanal`, solapa de "Grilla y
  mensajería" (`grilla_y_mensajeria.py`, import cruzado, mismo criterio
  que el resto de los merges de esta reorganización).
- Valores de los consultorios: pasa a `_PanelValoresVigentes`, solapa
  "Valores vigentes" de "Valores" (`valores.py`).
- Estadísticas: SE SACA DEL SISTEMA por decisión explícita de la
  clienta (`AskUserQuestion` durante el análisis del Excel de
  reubicación: esta tabla en vivo, filtrable, quedaba redundante contra
  la pantalla completa "Estadísticas") — se borró todo el código
  exclusivo de esa solapa, incluido el módulo `app.negocio.
  estadisticas_operativas` (sin otro consumidor).

Quedan en este módulo los helpers y widgets que siguen usando las dos
solapas que sobreviven: `_PanelFiltrosJerarquico` (filtro en cascada
Localidad/Edificio/Unidad/Consultorio, un nivel más profundo que el de
la grilla, por eso no se reusa `GrillaOperativaWidget` acá) y
`_PanelPromedios` (resumen de promedios de valor hora regular/aislada) —
ambos exclusivos de "Valores de los consultorios". Las dos solapas
ordenan igual (Localidad/Edificio alfabético, Unidad por piso —
`app.pdf.estilos.clave_orden_unidad`: PB primero, después EP, después
ascendente numérico)."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.gui.widgets.grilla_operativa import GrillaOperativaWidget, LeyendaColores, _FiltroColapsable
from app.negocio.formato import formatear_moneda
from app.negocio.valores_operativos import PromediosValorHora, calcular_promedios_valor_hora
from app.pdf.estilos import clave_orden_unidad

_COLUMNAS_VALORES = ["Localidad", "Edificio", "Unidad", "Consultorio", "Valor hora regular", "Valor hora aislada"]

_COLOR_TOTAL = QColor("#B7C8DC")
_COLOR_LOCALIDAD = QColor("#D2DEEB")
_COLOR_EDIFICIO = QColor("#E9EFF5")


class _ItemNumerico(QTableWidgetItem):
    """QTableWidgetItem que ordena por un valor numérico propio en vez de
    comparar el texto formateado ("$ 1.234,00", "67,8 %") como si fuera
    texto — para que el clic en el título de una columna numérica de
    verdad ordene de mayor a menor y viceversa."""

    def __init__(self, texto: str, valor: float):
        super().__init__(texto)
        self._valor = valor
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other: object) -> bool:
        if isinstance(other, _ItemNumerico):
            return self._valor < other._valor
        return super().__lt__(other)


def _armar_tabla(columnas: list[str], *, ordenable_nativo: bool = True) -> QTableWidget:
    """Filas seleccionables completas y sombreadas, con scroll cuando no
    entra todo, y columnas pinchables para ordenar ascendente/descendente
    (confirmado por la clienta).

    `ordenable_nativo=True` (Valores: tabla plana, sin jerarquía) deja que
    Qt ordene solo (`setSortingEnabled` hay que desactivarlo mientras se
    repuebla, si no reordena fila por fila a medida que se van cargando).
    `ordenable_nativo=False` (Promedios/Estadísticas: filas Total/
    Localidad/Edificio/Unidad con jerarquía) solo deja el clic disponible
    y la flechita de orden — quien arma la tabla escucha `sectionClicked`
    y reconstruye las filas a mano con `_ordenar_grupos_jerarquico`, para
    no perder el agrupamiento al ordenar."""
    tabla = QTableWidget()
    tabla.setColumnCount(len(columnas))
    tabla.setHorizontalHeaderLabels(columnas)
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabla.verticalHeader().setVisible(False)
    tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    tabla.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    if ordenable_nativo:
        tabla.setSortingEnabled(True)
    else:
        tabla.horizontalHeader().setSectionsClickable(True)
        tabla.horizontalHeader().setSortIndicatorShown(True)
    return tabla


def _ordenar_grupos_jerarquico(por_localidad, por_edificio, por_unidad, valor_fn, ascendente: bool):
    """Ordena las 3 listas (localidad/edificio/unidad de `EstadisticaGrupo`
    o `PromedioGrupo`, da igual — alcanza con que tengan `.localidad`/
    `.edificio`) por el valor que da `valor_fn` para cada renglón, sin
    perder el agrupamiento jerárquico: primero se ordenan las localidades
    entre sí; los edificios se ordenan por ese mismo valor DENTRO de cada
    localidad (no todos mezclados); las unidades, dentro de cada
    edificio. Doble sort estable en vez de una clave compuesta: ordena
    por valor primero y por el rango del grupo padre después — el
    segundo sort (estable) no pierde el orden por valor ya establecido
    entre elementos del mismo grupo."""
    localidades = sorted(por_localidad, key=valor_fn, reverse=not ascendente)
    rango_localidad = {g.localidad: i for i, g in enumerate(localidades)}

    edificios = sorted(
        sorted(por_edificio, key=valor_fn, reverse=not ascendente),
        key=lambda g: rango_localidad.get(g.localidad, len(rango_localidad)),
    )
    rango_edificio = {(g.localidad, g.edificio): i for i, g in enumerate(edificios)}

    unidades = sorted(
        sorted(por_unidad, key=valor_fn, reverse=not ascendente),
        key=lambda g: rango_edificio.get((g.localidad, g.edificio), len(rango_edificio)),
    )
    return localidades, edificios, unidades


_TODOS = object()  # sentinel del ítem "Todas las X" — mismo criterio que app.gui.widgets.grilla_operativa.TODOS


def _lista_multiseleccion() -> QListWidget:
    lista = QListWidget()
    lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    lista.setMaximumHeight(90)
    return lista


def _agregar_item_todos(lista: QListWidget, etiqueta: str) -> None:
    item = QListWidgetItem(etiqueta)
    fuente = item.font()
    fuente.setBold(True)
    item.setFont(fuente)
    item.setData(Qt.ItemDataRole.UserRole, _TODOS)
    lista.addItem(item)


def _corregir_seleccion_todos(lista: QListWidget) -> None:
    """Mutuamente excluyente con los ítems reales — ver la misma función
    en app.gui.widgets.grilla_operativa (duplicada acá, no importada, con
    su propio sentinel: son dos módulos que no necesitan compartir más
    que el criterio)."""
    seleccionados = lista.selectedItems()
    if len(seleccionados) <= 1:
        return
    item_todos = next((it for it in seleccionados if it.data(Qt.ItemDataRole.UserRole) is _TODOS), None)
    if item_todos is not None:
        lista.blockSignals(True)
        item_todos.setSelected(False)
        lista.blockSignals(False)


def _seleccionar_todos(lista: QListWidget) -> None:
    for i in range(lista.count()):
        item = lista.item(i)
        item.setSelected(item.data(Qt.ItemDataRole.UserRole) is _TODOS)


def _ids_seleccionados(lista: QListWidget) -> list:
    """[] con "Todas las X" tildado — para un nivel intermedio de la
    cascada, donde "sin filtro" ya significa "no restringir"."""
    return [
        item.data(Qt.ItemDataRole.UserRole) for item in lista.selectedItems()
        if item.data(Qt.ItemDataRole.UserRole) is not _TODOS
    ]


def _ids_reales(lista: QListWidget) -> list:
    """Como `_ids_seleccionados`, pero resolviendo "Todas las X" al
    conjunto real completo de la lista — para los métodos públicos
    `ids_unidad_seleccionadas`/`ids_consultorio_seleccionados`, que
    alimentan consultas donde una lista vacía significa "nada", no "todo"."""
    seleccionados = lista.selectedItems()
    if any(item.data(Qt.ItemDataRole.UserRole) is _TODOS for item in seleccionados):
        return [
            lista.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lista.count())
            if lista.item(i).data(Qt.ItemDataRole.UserRole) is not _TODOS
        ]
    return [item.data(Qt.ItemDataRole.UserRole) for item in seleccionados]


class _PanelFiltrosJerarquico(QGroupBox):
    """Filtro en cascada Localidad > Edificio > Unidad > Consultorio, para
    la solapa "Valores de los consultorios" — un nivel más profundo que
    el filtro de la grilla (que llega hasta Unidad), por eso no se reusa
    `GrillaOperativaWidget` acá. Cada nivel arranca con
    todo tildado, mismo criterio que la grilla. `on_cambiar(self)` se
    dispara con el panel mismo (no con `self.filtros_valores` del lado de
    la pantalla, que todavía no existiría como atributo la primera vez
    que se dispara, en medio del propio constructor)."""

    def __init__(self, conn: sqlite3.Connection, on_cambiar, parent=None):
        super().__init__("Filtros", parent)
        self.conn = conn
        self._on_cambiar = on_cambiar
        self.setMaximumWidth(260)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Localidad"))
        self.lista_localidad = _lista_multiseleccion()
        self.lista_localidad.itemSelectionChanged.connect(self._cargar_edificios)
        self._filtro_localidad = _FiltroColapsable(self.lista_localidad)
        layout.addWidget(self._filtro_localidad)

        layout.addWidget(QLabel("Edificio"))
        self.lista_edificio = _lista_multiseleccion()
        self.lista_edificio.itemSelectionChanged.connect(self._cargar_unidades)
        self._filtro_edificio = _FiltroColapsable(self.lista_edificio)
        layout.addWidget(self._filtro_edificio)

        layout.addWidget(QLabel("Unidad"))
        self.lista_unidad = _lista_multiseleccion()
        self.lista_unidad.itemSelectionChanged.connect(self._cargar_consultorios)
        self._filtro_unidad = _FiltroColapsable(self.lista_unidad)
        layout.addWidget(self._filtro_unidad)

        layout.addWidget(QLabel("Consultorio"))
        self.lista_consultorio = _lista_multiseleccion()
        self.lista_consultorio.itemSelectionChanged.connect(self._emitir_cambio)
        self._filtro_consultorio = _FiltroColapsable(self.lista_consultorio)
        layout.addWidget(self._filtro_consultorio)

        layout.addStretch()
        self._cargar_localidades()

    def _cargar_localidades(self) -> None:
        self.lista_localidad.blockSignals(True)
        self.lista_localidad.clear()
        _agregar_item_todos(self.lista_localidad, "Todas las localidades")
        filas = self.conn.execute(
            "SELECT DISTINCT e.IdLocalidad, loc.Localidad FROM Edificio e "
            "LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad ORDER BY loc.Localidad"
        ).fetchall()
        for fila in filas:
            item = QListWidgetItem(fila["Localidad"] or "(Sin localidad)")
            item.setData(Qt.ItemDataRole.UserRole, fila["IdLocalidad"])
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
                    marcas.append("IdLocalidad IS NULL")
                else:
                    marcas.append("IdLocalidad = ?")
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
        filas = sorted(filas, key=lambda f: (f["NombreEdificio"], clave_orden_unidad(f["Departamento"])))
        for fila in filas:
            item = QListWidgetItem(f"{fila['NombreEdificio']} - {fila['Departamento']}")
            item.setData(Qt.ItemDataRole.UserRole, fila["IdUnidad"])
            self.lista_unidad.addItem(item)
        _seleccionar_todos(self.lista_unidad)
        self.lista_unidad.blockSignals(False)
        self._filtro_unidad.actualizar_resumen()
        self._cargar_consultorios()

    def _cargar_consultorios(self) -> None:
        _corregir_seleccion_todos(self.lista_unidad)
        self._filtro_unidad.actualizar_resumen()
        ids_unidad = _ids_reales(self.lista_unidad)
        self.lista_consultorio.blockSignals(True)
        self.lista_consultorio.clear()
        _agregar_item_todos(self.lista_consultorio, "Todos los consultorios")
        if ids_unidad:
            placeholders = ", ".join("?" for _ in ids_unidad)
            filas = self.conn.execute(
                f"SELECT c.IdConsultorio, c.NumeroConsultorio, u.Departamento FROM Consultorio c "
                f"JOIN Unidad u ON u.IdUnidad = c.IdUnidad WHERE c.IdUnidad IN ({placeholders})",
                ids_unidad,
            ).fetchall()
            # Por piso de la unidad (mismo criterio que el resto de los
            # filtros) y, dentro de cada una, por número de consultorio —
            # un ORDER BY NumeroConsultorio a secas (como antes) mezclaba
            # los consultorios de distintas unidades ignorando el piso.
            filas = sorted(filas, key=lambda f: (clave_orden_unidad(f["Departamento"]), f["NumeroConsultorio"]))
            for fila in filas:
                item = QListWidgetItem(str(fila["NumeroConsultorio"]))
                item.setData(Qt.ItemDataRole.UserRole, fila["IdConsultorio"])
                self.lista_consultorio.addItem(item)
        _seleccionar_todos(self.lista_consultorio)
        self.lista_consultorio.blockSignals(False)
        self._filtro_consultorio.actualizar_resumen()
        self._emitir_cambio()

    def _emitir_cambio(self) -> None:
        _corregir_seleccion_todos(self.lista_consultorio)
        self._filtro_consultorio.actualizar_resumen()
        if self._on_cambiar:
            self._on_cambiar(self)

    def ids_unidad_seleccionadas(self) -> list[int]:
        return _ids_reales(self.lista_unidad)

    def ids_consultorio_seleccionados(self) -> list[int]:
        return _ids_reales(self.lista_consultorio)


_COLUMNAS_PROMEDIOS = ["Localidad", "Edificio", "Unidad", "Promedio hora regular", "Promedio hora aislada"]

_VALOR_PROMEDIO_POR_COLUMNA = [
    lambda g: g.localidad or "",
    lambda g: g.edificio or "",
    lambda g: g.unidad or "",
    lambda g: g.promedio_valor_hora_regular,
    lambda g: g.promedio_valor_hora_aislada,
]


class _PanelPromedios(QGroupBox):
    """Promedio de valor hora regular Y hora aislada por localidad/
    edificio/unidad, para la solapa "Valores de los consultorios" —
    mismas 3 columnas separadas y mismo criterio de "mostrar el desglose
    solo si hay más de uno" y de orden que usa Estadísticas.

    El renglón "General" queda siempre primero, sin ordenar — el clic en
    una columna reordena las localidades/edificios/unidades entre sí de
    forma jerárquica (ver `_ordenar_grupos_jerarquico`), sin usar el
    `setSortingEnabled` nativo de Qt (que aplanaría todo, mezclando
    niveles)."""

    def __init__(self, parent=None):
        super().__init__("Promedios de valor hora regular y aislada", parent)
        self.setMinimumWidth(720)
        self.setMaximumWidth(780)
        layout = QVBoxLayout(self)
        self.tabla = _armar_tabla(_COLUMNAS_PROMEDIOS, ordenable_nativo=False)
        self.tabla.horizontalHeader().sectionClicked.connect(self._ordenar_por_columna)
        layout.addWidget(self.tabla)
        self._promedios = PromediosValorHora()
        self._columna_orden: int | None = None
        self._orden_ascendente = True

    def actualizar(self, promedios: PromediosValorHora) -> None:
        self._promedios = promedios
        self._columna_orden = None
        self.tabla.horizontalHeader().setSortIndicatorShown(False)
        self._reconstruir_filas(promedios.por_localidad, promedios.por_edificio, promedios.por_unidad)

    def _ordenar_por_columna(self, columna: int) -> None:
        if columna == self._columna_orden:
            self._orden_ascendente = not self._orden_ascendente
        else:
            self._columna_orden = columna
            self._orden_ascendente = True
        localidades, edificios, unidades = _ordenar_grupos_jerarquico(
            self._promedios.por_localidad, self._promedios.por_edificio, self._promedios.por_unidad,
            _VALOR_PROMEDIO_POR_COLUMNA[columna], self._orden_ascendente,
        )
        orden = Qt.SortOrder.AscendingOrder if self._orden_ascendente else Qt.SortOrder.DescendingOrder
        self.tabla.horizontalHeader().setSortIndicatorShown(True)
        self.tabla.horizontalHeader().setSortIndicator(columna, orden)
        self._reconstruir_filas(localidades, edificios, unidades)

    def _reconstruir_filas(self, por_localidad, por_edificio, por_unidad) -> None:
        promedios = self._promedios
        filas: list[tuple[str, str, str, float, float, QColor | None]] = [
            ("General", "", "", promedios.general_regular, promedios.general_aislada, _COLOR_TOTAL),
        ]
        if len(por_localidad) > 1:
            filas += [
                (g.localidad, "", "", g.promedio_valor_hora_regular, g.promedio_valor_hora_aislada, _COLOR_LOCALIDAD)
                for g in por_localidad
            ]
        if len(por_edificio) > 1:
            filas += [
                (g.localidad, g.edificio, "", g.promedio_valor_hora_regular, g.promedio_valor_hora_aislada, _COLOR_EDIFICIO)
                for g in por_edificio
            ]
        filas += [
            (g.localidad, g.edificio, g.unidad, g.promedio_valor_hora_regular, g.promedio_valor_hora_aislada, None)
            for g in por_unidad
        ]

        self.tabla.setRowCount(len(filas))
        for fila, (localidad, edificio, unidad, valor_regular, valor_aislada, color) in enumerate(filas):
            columnas = [
                QTableWidgetItem(localidad), QTableWidgetItem(edificio), QTableWidgetItem(unidad),
                _ItemNumerico(formatear_moneda(valor_regular), valor_regular),
                _ItemNumerico(formatear_moneda(valor_aislada), valor_aislada),
            ]
            if color is not None:
                for item in columnas:
                    fuente = item.font()
                    fuente.setBold(True)
                    item.setFont(fuente)
                    item.setBackground(color)
            for indice, item in enumerate(columnas):
                self.tabla.setItem(fila, indice, item)


class _PanelGrillaSemanal(QWidget):
    """Solapa "Grilla semanal" de "Grilla y mensajería" — antes la
    primera solapa de "Vista rápida". Sin filtro propio: reusa
    `GrillaOperativaWidget` tal cual (el mismo widget compartido que usan
    otros formularios), con su leyenda de colores debajo."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        layout = QVBoxLayout(self)
        self.grilla = GrillaOperativaWidget(conn)
        self.grilla.combo_modo.currentIndexChanged.connect(self._actualizar_leyenda)
        layout.addWidget(self.grilla)
        self._leyenda = LeyendaColores()
        layout.addWidget(self._leyenda)

    def _actualizar_leyenda(self) -> None:
        self._leyenda.actualizar(self.grilla.combo_modo.currentData() or "regular")


class _PanelValoresVigentes(QWidget):
    """Solapa "Valores vigentes" de "Valores" — antes la solapa "Valores
    de los consultorios" de "Vista rápida". Filtro en cascada
    (`_PanelFiltrosJerarquico`) + tabla de valor hora regular/aislada por
    consultorio + resumen de promedios (`_PanelPromedios`)."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        layout = QHBoxLayout(self)

        # La tabla y los promedios se arman antes que el filtro: el
        # constructor de `_PanelFiltrosJerarquico` ya dispara `on_cambiar`
        # una vez (con todo tildado por defecto), y ese refresco necesita
        # que ya existan.
        self.tabla_valores = _armar_tabla(_COLUMNAS_VALORES)
        self.promedios_valores = _PanelPromedios()

        self.filtros_valores = _PanelFiltrosJerarquico(conn, on_cambiar=self._refrescar_valores)
        layout.addWidget(self.filtros_valores)
        layout.addWidget(self.promedios_valores)
        grupo_valores = QGroupBox("Valores vigentes por horas regulares y aisladas")
        layout_grupo_valores = QVBoxLayout(grupo_valores)
        layout_grupo_valores.addWidget(self.tabla_valores)
        layout.addWidget(grupo_valores, stretch=1)

    def _refrescar_valores(self, panel: _PanelFiltrosJerarquico) -> None:
        ids_consultorio = panel.ids_consultorio_seleccionados()
        self.tabla_valores.setSortingEnabled(False)
        self.tabla_valores.setRowCount(0)
        if not ids_consultorio:
            self.tabla_valores.setSortingEnabled(True)
            self.promedios_valores.actualizar(PromediosValorHora())
            return
        placeholders = ", ".join("?" for _ in ids_consultorio)
        filas = self.conn.execute(
            f"""
            SELECT loc.Localidad AS DomicilioLocalidad, e.Nombre AS NombreEdificio, u.Departamento,
                   c.NumeroConsultorio, c.ValorHoraRegularActual, c.ValorHoraAisladaActual
            FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
            LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad
            WHERE c.IdConsultorio IN ({placeholders})
            """,
            ids_consultorio,
        ).fetchall()
        filas = sorted(filas, key=lambda f: (
            f["DomicilioLocalidad"] or "(Sin localidad)", f["NombreEdificio"],
            clave_orden_unidad(f["Departamento"]), f["NumeroConsultorio"],
        ))
        self.tabla_valores.setRowCount(len(filas))
        for fila, f in enumerate(filas):
            valor_regular = f["ValorHoraRegularActual"] or 0
            valor_aislada = f["ValorHoraAisladaActual"] or 0
            self.tabla_valores.setItem(fila, 0, QTableWidgetItem(f["DomicilioLocalidad"] or "(Sin localidad)"))
            self.tabla_valores.setItem(fila, 1, QTableWidgetItem(f["NombreEdificio"]))
            self.tabla_valores.setItem(fila, 2, QTableWidgetItem(f["Departamento"]))
            self.tabla_valores.setItem(fila, 3, _ItemNumerico(str(f["NumeroConsultorio"]), f["NumeroConsultorio"]))
            self.tabla_valores.setItem(fila, 4, _ItemNumerico(formatear_moneda(valor_regular), valor_regular))
            self.tabla_valores.setItem(fila, 5, _ItemNumerico(formatear_moneda(valor_aislada), valor_aislada))
        self.tabla_valores.setSortingEnabled(True)

        self.promedios_valores.actualizar(calcular_promedios_valor_hora(self.conn, ids_consultorio))
