"""Pantalla "Vista rápida" (ex "Grilla operativa", punto 21 de la
miscelánea, ago-2026, renombrada y reorganizada en solapas a pedido de la
clienta): tres solapas independientes, cada una con su propio filtro:

- Grilla semanal: la grilla filtrable en sí (el widget compartido
  `GrillaOperativaWidget`, sin modificar — lo siguen usando tal cual el
  resto de los formularios que la embeben) + referencias de colores.
- Valores de los consultorios: valor hora regular/aislada de cada
  consultorio, con su propio filtro en cascada Localidad/Edificio/
  Unidad/Consultorio (`_PanelFiltrosJerarquico`, un nivel más profundo
  que el de la grilla) + un resumen de promedios de valor hora regular.
- Estadísticas: mismo filtro en cascada; total general primero, después
  el desglose por localidad (si el filtro abarca más de una) y por
  edificio (si abarca más de uno), y por último el detalle por unidad —
  ver `app.negocio.estadisticas_operativas`.

Las tres solapas ordenan igual (Localidad/Edificio alfabético, Unidad
por piso — `app.pdf.estilos.clave_orden_unidad`: PB primero, después EP,
después ascendente numérico)."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from app.gui.widgets.grilla_operativa import GrillaOperativaWidget, _CeldaGrilla
from app.negocio.estadisticas_operativas import EstadisticaGrupo, calcular_estadisticas_operativas
from app.negocio.formato import formatear_moneda
from app.negocio.grilla_operativa import AMARILLO, AZUL_OSCURO, BLANCA, BLANCO, NEGRA, ROJO, VERDE, CeldaGrillaOperativa
from app.negocio.valores_operativos import PromediosValorHora, calcular_promedios_valor_hora_regular
from app.pdf.estilos import clave_orden_unidad

_COLUMNAS_VALORES = ["Localidad", "Edificio", "Unidad", "Consultorio", "Valor hora regular", "Valor hora aislada"]
_COLUMNAS_ESTADISTICAS = [
    "Localidad", "Edificio", "Unidad", "% Ocupación", "Horas regulares", "Horas aisladas",
    "Subtotal regulares", "Subtotal aisladas", "Pagos del mes", "Falta cobrar",
]

_COLOR_TOTAL = QColor("#B7C8DC")
_COLOR_LOCALIDAD = QColor("#D2DEEB")
_COLOR_EDIFICIO = QColor("#E9EFF5")

_REFERENCIAS_REGULAR: list[tuple[CeldaGrillaOperativa, str]] = [
    (CeldaGrillaOperativa(BLANCO, BLANCO, NEGRA, None, "", None), "Sin novedades (el código, si lo hay, sigue vigente)."),
    (CeldaGrillaOperativa(VERDE, VERDE, NEGRA, None, "", None), "Se libera en el futuro."),
    (CeldaGrillaOperativa(ROJO, ROJO, NEGRA, None, "", None), "Reservado a futuro (todavía no vigente)."),
    (CeldaGrillaOperativa(AMARILLO, AMARILLO, NEGRA, None, "", None), "Libre de regular, con hora aislada asignada."),
    (CeldaGrillaOperativa(ROJO, AMARILLO, NEGRA, None, "", None), "Reservado a futuro + aislada confirmada este mes."),
    (CeldaGrillaOperativa(BLANCO, VERDE, NEGRA, None, "", None), "Reservado, pero libre por ausencia/vacación/licencia."),
    (CeldaGrillaOperativa(BLANCO, AMARILLO, NEGRA, None, "", None), "Igual, con aislada confirmada en ese hueco."),
    (CeldaGrillaOperativa(AZUL_OSCURO, AZUL_OSCURO, BLANCA, None, "", None), "Profesional filtrado."),
]

_REFERENCIAS_AISLADA: list[tuple[CeldaGrillaOperativa, str]] = [
    (CeldaGrillaOperativa(ROJO, ROJO, NEGRA, None, "", None), "Bloqueado por una reserva regular."),
    (CeldaGrillaOperativa(VERDE, VERDE, NEGRA, None, "", None), "Libre de reserva regular."),
    (CeldaGrillaOperativa(ROJO, VERDE, NEGRA, None, "", None), "Reservado, pero libera un hueco por ausencia/vacación/licencia."),
    (CeldaGrillaOperativa(ROJO, AMARILLO, NEGRA, None, "", None), "Igual, con aislada confirmada en ese hueco."),
    (CeldaGrillaOperativa(AMARILLO, AMARILLO, NEGRA, None, "", None), "Libre + aislada asignada."),
    (CeldaGrillaOperativa(AZUL_OSCURO, AZUL_OSCURO, BLANCA, None, "", None), "Profesional filtrado."),
]


class _LeyendaColores(QGroupBox):
    """Referencia de qué significa cada color/combinación — reusa
    `_CeldaGrilla` (la misma clase que pinta la grilla real) para que la
    muestra sea pixel a pixel igual a lo que se ve arriba, en vez de
    reimplementar el dibujo del triángulo acá aparte."""

    def __init__(self, parent=None):
        super().__init__("Referencias de colores", parent)
        self._layout = QGridLayout(self)
        self.actualizar("regular")

    def actualizar(self, modo: str) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        referencias = _REFERENCIAS_REGULAR if modo == "regular" else _REFERENCIAS_AISLADA
        columnas = 2
        for i, (celda, texto) in enumerate(referencias):
            fila, columna = divmod(i, columnas)
            muestra = _CeldaGrilla(celda, (0, "Lunes", 0), lambda *_: None)
            muestra.setFixedSize(40, 24)
            self._layout.addWidget(muestra, fila, columna * 2)
            etiqueta = QLabel(texto)
            etiqueta.setWordWrap(True)
            self._layout.addWidget(etiqueta, fila, columna * 2 + 1)


def _fmt_horas(horas: float) -> str:
    return str(int(horas)) if horas == int(horas) else f"{horas:.1f}"


def _armar_tabla(columnas: list[str]) -> QTableWidget:
    tabla = QTableWidget()
    tabla.setColumnCount(len(columnas))
    tabla.setHorizontalHeaderLabels(columnas)
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabla.verticalHeader().setVisible(False)
    tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return tabla


def _lista_multiseleccion() -> QListWidget:
    lista = QListWidget()
    lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    lista.setMaximumHeight(90)
    return lista


def _seleccionar_todos(lista: QListWidget) -> None:
    for i in range(lista.count()):
        lista.item(i).setSelected(True)


def _ids_seleccionados(lista: QListWidget) -> list:
    return [item.data(Qt.ItemDataRole.UserRole) for item in lista.selectedItems()]


class _PanelFiltrosJerarquico(QGroupBox):
    """Filtro en cascada Localidad > Edificio > Unidad > Consultorio, para
    las solapas "Valores de los consultorios" y "Estadísticas" — un nivel
    más profundo que el filtro de la grilla (que llega hasta Unidad), por
    eso no se reusa `GrillaOperativaWidget` acá. Cada nivel arranca con
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
        layout.addWidget(self.lista_localidad)

        layout.addWidget(QLabel("Edificio"))
        self.lista_edificio = _lista_multiseleccion()
        self.lista_edificio.itemSelectionChanged.connect(self._cargar_unidades)
        layout.addWidget(self.lista_edificio)

        layout.addWidget(QLabel("Unidad"))
        self.lista_unidad = _lista_multiseleccion()
        self.lista_unidad.itemSelectionChanged.connect(self._cargar_consultorios)
        layout.addWidget(self.lista_unidad)

        layout.addWidget(QLabel("Consultorio"))
        self.lista_consultorio = _lista_multiseleccion()
        self.lista_consultorio.itemSelectionChanged.connect(self._emitir_cambio)
        layout.addWidget(self.lista_consultorio)

        layout.addStretch()
        self._cargar_localidades()

    def _cargar_localidades(self) -> None:
        self.lista_localidad.blockSignals(True)
        self.lista_localidad.clear()
        filas = self.conn.execute("SELECT DISTINCT DomicilioLocalidad FROM Edificio ORDER BY DomicilioLocalidad").fetchall()
        for fila in filas:
            valor = fila["DomicilioLocalidad"]
            item = QListWidgetItem(valor or "(Sin localidad)")
            item.setData(Qt.ItemDataRole.UserRole, valor)
            self.lista_localidad.addItem(item)
        _seleccionar_todos(self.lista_localidad)
        self.lista_localidad.blockSignals(False)
        self._cargar_edificios()

    def _cargar_edificios(self) -> None:
        localidades = _ids_seleccionados(self.lista_localidad)
        self.lista_edificio.blockSignals(True)
        self.lista_edificio.clear()
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
        self._cargar_unidades()

    def _cargar_unidades(self) -> None:
        ids_edificio = _ids_seleccionados(self.lista_edificio)
        self.lista_unidad.blockSignals(True)
        self.lista_unidad.clear()
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
        self._cargar_consultorios()

    def _cargar_consultorios(self) -> None:
        ids_unidad = _ids_seleccionados(self.lista_unidad)
        self.lista_consultorio.blockSignals(True)
        self.lista_consultorio.clear()
        if ids_unidad:
            placeholders = ", ".join("?" for _ in ids_unidad)
            filas = self.conn.execute(
                f"SELECT IdConsultorio, NumeroConsultorio FROM Consultorio WHERE IdUnidad IN ({placeholders}) "
                "ORDER BY NumeroConsultorio",
                ids_unidad,
            ).fetchall()
            for fila in filas:
                item = QListWidgetItem(str(fila["NumeroConsultorio"]))
                item.setData(Qt.ItemDataRole.UserRole, fila["IdConsultorio"])
                self.lista_consultorio.addItem(item)
        _seleccionar_todos(self.lista_consultorio)
        self.lista_consultorio.blockSignals(False)
        self._emitir_cambio()

    def _emitir_cambio(self) -> None:
        if self._on_cambiar:
            self._on_cambiar(self)

    def ids_unidad_seleccionadas(self) -> list[int]:
        return _ids_seleccionados(self.lista_unidad)

    def ids_consultorio_seleccionados(self) -> list[int]:
        return _ids_seleccionados(self.lista_consultorio)


class _PanelPromedios(QGroupBox):
    """Promedio de valor hora regular por localidad/edificio/unidad, para
    la solapa "Valores de los consultorios" — mismo criterio de "mostrar
    el desglose solo si hay más de uno" que usa Estadísticas."""

    def __init__(self, parent=None):
        super().__init__("Promedios de valor hora regular", parent)
        layout = QVBoxLayout(self)
        self.tabla = _armar_tabla(["Nivel", "Promedio"])
        layout.addWidget(self.tabla)

    def actualizar(self, promedios: PromediosValorHora) -> None:
        filas: list[tuple[str, float, QColor | None]] = [("General", promedios.general, _COLOR_TOTAL)]
        if len(promedios.por_localidad) > 1:
            filas += [(g.nombre, g.promedio_valor_hora_regular, _COLOR_LOCALIDAD) for g in promedios.por_localidad]
        if len(promedios.por_edificio) > 1:
            filas += [(g.nombre, g.promedio_valor_hora_regular, _COLOR_EDIFICIO) for g in promedios.por_edificio]
        filas += [(g.nombre, g.promedio_valor_hora_regular, None) for g in promedios.por_unidad]

        self.tabla.setRowCount(len(filas))
        for fila, (nombre, valor, color) in enumerate(filas):
            item_nombre = QTableWidgetItem(nombre)
            item_valor = QTableWidgetItem(formatear_moneda(valor))
            if color is not None:
                for item in (item_nombre, item_valor):
                    fuente = item.font()
                    fuente.setBold(True)
                    item.setFont(fuente)
                    item.setBackground(color)
            self.tabla.setItem(fila, 0, item_nombre)
            self.tabla.setItem(fila, 1, item_valor)


class PantallaGrillaOperativa(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn

        layout = QVBoxLayout(self)

        titulo = QLabel("Vista rápida")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Las tablas se arman antes que los paneles de filtros: el
        # constructor de `_PanelFiltrosJerarquico` ya dispara `on_cambiar`
        # una vez (con todo tildado por defecto), y ese refresco necesita
        # que las tablas ya existan.
        self.tabla_valores = _armar_tabla(_COLUMNAS_VALORES)
        self.tabla_estadisticas = _armar_tabla(_COLUMNAS_ESTADISTICAS)
        self.promedios_valores = _PanelPromedios()

        panel_grilla = QWidget()
        layout_grilla = QVBoxLayout(panel_grilla)
        self.grilla = GrillaOperativaWidget(conn)
        self.grilla.combo_modo.currentIndexChanged.connect(self._actualizar_leyenda)
        layout_grilla.addWidget(self.grilla, stretch=1)
        self._leyenda = _LeyendaColores()
        layout_grilla.addWidget(self._leyenda)
        tabs.addTab(panel_grilla, "Grilla semanal")

        panel_valores = QWidget()
        layout_valores = QHBoxLayout(panel_valores)
        self.filtros_valores = _PanelFiltrosJerarquico(conn, on_cambiar=self._refrescar_valores)
        layout_valores.addWidget(self.filtros_valores)
        columna_valores = QVBoxLayout()
        columna_valores.addWidget(self.promedios_valores)
        columna_valores.addWidget(self.tabla_valores, stretch=1)
        layout_valores.addLayout(columna_valores, stretch=1)
        tabs.addTab(panel_valores, "Valores de los consultorios")

        panel_estadisticas = QWidget()
        layout_estadisticas = QHBoxLayout(panel_estadisticas)
        self.filtros_estadisticas = _PanelFiltrosJerarquico(conn, on_cambiar=self._refrescar_estadisticas)
        layout_estadisticas.addWidget(self.filtros_estadisticas)
        layout_estadisticas.addWidget(self.tabla_estadisticas, stretch=1)
        tabs.addTab(panel_estadisticas, "Estadísticas")

    # -------------------------------------------------------- sincronismo

    def _actualizar_leyenda(self) -> None:
        self._leyenda.actualizar(self.grilla.combo_modo.currentData() or "regular")

    def _refrescar_valores(self, panel: _PanelFiltrosJerarquico) -> None:
        ids_consultorio = panel.ids_consultorio_seleccionados()
        self.tabla_valores.setRowCount(0)
        if not ids_consultorio:
            self.promedios_valores.actualizar(PromediosValorHora())
            return
        placeholders = ", ".join("?" for _ in ids_consultorio)
        filas = self.conn.execute(
            f"""
            SELECT e.DomicilioLocalidad, e.Nombre AS NombreEdificio, u.Departamento, c.NumeroConsultorio,
                   c.ValorHoraRegularActual, c.ValorHoraAisladaActual
            FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
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
            valores = [
                f["DomicilioLocalidad"] or "(Sin localidad)", f["NombreEdificio"], f["Departamento"], str(f["NumeroConsultorio"]),
                formatear_moneda(f["ValorHoraRegularActual"] or 0),
                formatear_moneda(f["ValorHoraAisladaActual"] or 0),
            ]
            for columna, texto in enumerate(valores):
                self.tabla_valores.setItem(fila, columna, QTableWidgetItem(texto))

        self.promedios_valores.actualizar(calcular_promedios_valor_hora_regular(self.conn, ids_consultorio))

    def _refrescar_estadisticas(self, panel: _PanelFiltrosJerarquico) -> None:
        ids_unidad = panel.ids_unidad_seleccionadas()
        ids_consultorio = panel.ids_consultorio_seleccionados()
        self.tabla_estadisticas.setRowCount(0)
        if not ids_unidad or not ids_consultorio:
            return
        estadisticas = calcular_estadisticas_operativas(self.conn, ids_unidad, ids_consultorio_filtro=ids_consultorio)

        filas: list[tuple[EstadisticaGrupo, QColor | None]] = [(estadisticas.total, _COLOR_TOTAL)]
        if len(estadisticas.por_localidad) > 1:
            filas += [(g, _COLOR_LOCALIDAD) for g in estadisticas.por_localidad]
        if len(estadisticas.por_edificio) > 1:
            filas += [(g, _COLOR_EDIFICIO) for g in estadisticas.por_edificio]
        filas += [(g, None) for g in estadisticas.por_unidad]

        self.tabla_estadisticas.setRowCount(len(filas))
        for fila, (grupo, color) in enumerate(filas):
            self._llenar_fila_estadistica(fila, grupo, color)

    def _llenar_fila_estadistica(self, fila: int, grupo: EstadisticaGrupo, color: QColor | None) -> None:
        valores = [
            grupo.localidad if grupo.localidad is not None else grupo.nombre,  # el total no tiene localidad propia
            grupo.edificio or "",
            grupo.unidad or "",
            f"{grupo.porcentaje_ocupacion:.1f} %",
            _fmt_horas(grupo.horas_regulares),
            _fmt_horas(grupo.horas_aisladas),
            formatear_moneda(grupo.subtotal_regulares),
            formatear_moneda(grupo.subtotal_aisladas),
            formatear_moneda(grupo.pagos_atribuidos),
            formatear_moneda(grupo.falta_cobrar),
        ]
        for columna, texto in enumerate(valores):
            item = QTableWidgetItem(texto)
            if color is not None:
                fuente = item.font()
                fuente.setBold(True)
                item.setFont(fuente)
                item.setBackground(color)
            self.tabla_estadisticas.setItem(fila, columna, item)
