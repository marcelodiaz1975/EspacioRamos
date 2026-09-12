"""Lista de espera (F12, sección 3.21 y DC-08 §2 / DC-10 §2): agenda lo
que piden los profesionales (activos en el espacio o no, de cualquier
categoría — incluidos X/inactivos y C/contacto-prospecto) y cruza cada
pedido automáticamente contra la disponibilidad real del período en
curso, reusando app.negocio.lista_espera. El texto o PDF de oferta para
mandarle a un profesional se arma aparte, en Oferta de consultorios
(`app.gui.pantallas.oferta`) — que funciona igual tenga o no el
profesional algo cargado acá.

Un pedido puede necesitar varios bloques día(s)+horario a la vez (ej.
"martes o jueves 3hs entre 14 y 18hs" Y "sábado de 9 a 12hs"): los campos
de día/horario/cantidad de horas/combinación de días arman UN bloque por
vez, "Agregar bloque" lo suma a la tabla de bloques del pedido —
confirmado por la clienta: es obligatorio pasar por ese botón, no hay
fallback que tome lo cargado en el formulario si no se agregó ningún
bloque. Con un solo bloque, "Combinación de bloques" muestra "Bloque
único" fijo (sin sentido elegir O/Y con uno solo); recién con más de uno
se habilita para elegir si hace falta que se den TODOS (Y) o alcanza con
uno (O).

Localidad/Edificio/Unidad es la misma cascada compacta y colapsable de
Oferta de consultorios (reusa sus mismos helpers privados en
`app.gui.widgets.grilla_operativa`) para el caso de un profesional que
pide expresamente una unidad puntual — o localidad/edificio, si el
sistema llega a tener más de uno — en vez de "cualquiera"; por defecto
arranca en "Todas/Todos" en los tres niveles.

Un profesional no puede tener dos pedidos Activos a la vez (confirmado
por la clienta): al intentar crear uno para alguien que ya tiene uno, se
ofrece editar el existente en su lugar en vez de bloquear sin más — ver
`_crear_pedido`. Esto se resuelve en la pantalla (para poder ofrecer la
alternativa de editar); `crear_pedido` en `app.negocio.lista_espera` no
lo valida a nivel de datos porque `avance_mes` necesita poder dejar más
de un pedido Activo del mismo profesional en escenarios de limpieza de
fin de mes (ver sus tests) — si se quiere blindar también a nivel de
datos, hay que revisar antes esos casos."""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.pantallas.reservas import _opciones_profesional, _texto_profesional
from app.gui.widgets.grilla_operativa import (
    _agregar_item_todos,
    _corregir_seleccion_todos,
    _FiltroColapsable,
    _ids_reales,
    _ids_seleccionados,
    _lista_multiseleccion,
    _seleccionar_todos,
)
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.dias import DIAS_SEMANA, periodo_actual
from app.negocio.formato import hora_fmt
from app.negocio.lista_espera import crear_pedido, editar_pedido, listar_pedidos_con_coincidencia, marcar_descartado
from app.negocio.oferta_busqueda import TAMANOS_CONSULTORIO
from app.repositorio.registro import obtener_repositorio

_COLOR_CELDA = {"verde": "#4CAF50", "amarillo": "#F5D547", "naranja": "#E07B39", "rojo": "#C0392B"}
_ETIQUETA_COLOR = {
    "verde": "Un consultorio cubre todo",
    "amarillo": "Combinar, misma unidad",
    "naranja": "Combinar, mismo edificio",
    "rojo": "Combinar, distinto edificio",
}
_DIAS_PEDIDO = DIAS_SEMANA[:6]
# De menor a mayor porque acá el combo elige un MÍNIMO (ver
# `app.negocio.lista_espera._JERARQUIA_TAMANO`) — al revés que en Oferta
# de consultorios, donde el combo elige un tamaño exacto.
_TAMANOS_MINIMOS = [(t, t) for t in reversed(TAMANOS_CONSULTORIO)]


def _titulo_campo(texto: str) -> QLabel:
    """Subtítulo de jerarquía 3 (ver docstring de `app.gui.estilos`):
    mismo tamaño/color que el texto normal, solo que en negrita — para
    el nombre de un campo/selector/cuadro puntual del formulario (ej.
    "Profesional" arriba de su combo)."""
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _horario_texto(desde: float, hasta: float) -> str:
    """"9 a 12hs" / "9:30 a 12hs" — un solo "hs" al final en vez de uno
    por número, mismo criterio que ya usa `_alertas_aisladas` en
    `app.negocio.lista_espera`."""
    return f"{hora_fmt(desde)[:-2]} a {hora_fmt(hasta)}"


def _texto_condiciones(conn: sqlite3.Connection, condiciones: dict) -> str:
    """Resumen legible de las condiciones/filtros marcados en la
    búsqueda del pedido — ventana/camilla/placard/aire/tamaño mínimo y,
    si se restringió a un subconjunto de unidades, cuántas. La
    combinación de consultorios tiene su propia columna en la tabla
    (ver "Combinación consultorios"), así que no se repite acá."""
    partes = []
    if condiciones.get("ventana"):
        partes.append("Con ventana")
    if condiciones.get("aptoCamilla"):
        partes.append("Apto camilla")
    if condiciones.get("placard"):
        partes.append("Con placard")
    if condiciones.get("aire"):
        partes.append("Con aire acondicionado")
    tamano = condiciones.get("tamano")
    if tamano:
        partes.append(f"Tamaño mínimo: {tamano}")
    ids_unidad = condiciones.get("idsUnidad") or []
    total_unidades = conn.execute("SELECT COUNT(*) c FROM Unidad").fetchone()["c"]
    if ids_unidad and len(ids_unidad) < total_unidades:
        palabra = "unidad" if len(ids_unidad) == 1 else "unidades"
        partes.append(f"Restringido a {len(ids_unidad)} {palabra}")
    return "; ".join(partes) if partes else "Sin condiciones"


def _item_con_tooltip(texto: str) -> QTableWidgetItem:
    """Mismo texto como tooltip: al pasar el mouse por una celda con
    contenido recortado (columna angosta, texto largo) se puede leer
    completo sin tener que agrandar la columna a mano."""
    item = QTableWidgetItem(texto)
    item.setToolTip(texto)
    return item


class _SpinHora(QDoubleSpinBox):
    """QDoubleSpinBox que se muestra como horario ("12:00hs", "9:30hs")
    en vez del decimal con punto que arrastra Qt por defecto — sigue
    siendo el mismo float por dentro (9.5 = 9:30) que espera
    `app.negocio.lista_espera`, mismo criterio que `_SpinMonto` en Pagos
    y `_SpinHora` en Oferta de consultorios."""

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


class _DelegadoSinResaltarSeleccion(QStyledItemDelegate):
    """Pinta la columna Coincidencia ignorando el estado de selección
    de la fila — confirmado por la clienta: el color de esa celda
    (verde/amarillo/naranja/rojo/blanco) tiene que seguir mostrando el
    criterio de cobertura tal cual, esté la fila seleccionada o no, en
    vez de taparse con el naranja de selección."""

    def paint(self, painter, option, index) -> None:  # noqa: N802
        opcion = QStyleOptionViewItem(option)
        opcion.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, opcion, index)


class PantallaListaEspera(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._pedidos: list[sqlite3.Row] = []
        self._coincidencias: list = []
        self._bloques_pendientes: list[dict] = []
        self._id_pedido_en_edicion: int | None = None
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Lista de espera".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        subtitulo_solapa = QLabel("Nuevo pedido")
        subtitulo_solapa.setObjectName("subtituloSeccion")
        layout.addWidget(subtitulo_solapa)
        fila_columnas = QHBoxLayout()

        col_quien = QVBoxLayout()
        self.combo_profesional = QComboBox()
        habilitar_busqueda_profesional(self.combo_profesional)
        col_quien.addWidget(_titulo_campo("Profesional"))
        col_quien.addWidget(self.combo_profesional)

        col_quien.addWidget(_titulo_campo("Localidad"))
        self.lista_localidad = _lista_multiseleccion()
        self.lista_localidad.itemSelectionChanged.connect(self._cargar_edificios)
        self._filtro_localidad = _FiltroColapsable(self.lista_localidad)
        col_quien.addWidget(self._filtro_localidad)

        col_quien.addWidget(_titulo_campo("Edificio"))
        self.lista_edificio = _lista_multiseleccion()
        self.lista_edificio.itemSelectionChanged.connect(self._cargar_unidades)
        self._filtro_edificio = _FiltroColapsable(self.lista_edificio)
        col_quien.addWidget(self._filtro_edificio)

        col_quien.addWidget(_titulo_campo("Unidad"))
        self.lista_unidad = _lista_multiseleccion()
        self.lista_unidad.itemSelectionChanged.connect(self._unidad_seleccion_cambio)
        self._filtro_unidad = _FiltroColapsable(self.lista_unidad)
        col_quien.addWidget(self._filtro_unidad)

        contenedor_dias = QWidget()
        grid_dias = QGridLayout(contenedor_dias)
        grid_dias.setContentsMargins(0, 0, 0, 0)
        self._checks_dia: dict[str, QCheckBox] = {}
        columnas = math.ceil(len(_DIAS_PEDIDO) / 2)
        for i, dia in enumerate(_DIAS_PEDIDO):
            check = QCheckBox(dia)
            self._checks_dia[dia] = check
            grid_dias.addWidget(check, i // columnas, i % columnas)
        col_quien.addWidget(contenedor_dias)

        self.combo_tipo = QComboBox()
        self.combo_tipo.addItem("Alcanza con un día (O)", "O")
        self.combo_tipo.addItem("Todos los días (Y)", "Y")
        col_quien.addWidget(self.combo_tipo)

        fila_horario = QHBoxLayout()
        self.spin_desde = _SpinHora()
        self.spin_desde.setRange(0, 23)
        self.spin_desde.setValue(9)
        self.spin_hasta = _SpinHora()
        self.spin_hasta.setRange(1, 24)
        self.spin_hasta.setValue(12)
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_desde)
        fila_horario.addStretch()
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hasta)
        fila_horario.addStretch()
        col_quien.addLayout(fila_horario)

        fila_cantidad_horas = QHBoxLayout()
        self.casilla_cantidad_horas = QCheckBox("Cantidad de horas dentro del rango (en vez del rango completo)")
        self.spin_cantidad_horas = QDoubleSpinBox()
        self.spin_cantidad_horas.setRange(0.5, 24)
        self.spin_cantidad_horas.setValue(1)
        self.spin_cantidad_horas.setEnabled(False)
        self.casilla_cantidad_horas.toggled.connect(self.spin_cantidad_horas.setEnabled)
        fila_cantidad_horas.addWidget(self.casilla_cantidad_horas)
        fila_cantidad_horas.addWidget(self.spin_cantidad_horas)
        col_quien.addLayout(fila_cantidad_horas)

        self.boton_agregar_bloque = QPushButton("Agregar bloque")
        self.boton_agregar_bloque.setObjectName("botonSecundario")
        self.boton_agregar_bloque.clicked.connect(self._agregar_bloque)
        col_quien.addWidget(self.boton_agregar_bloque)
        col_quien.addStretch()

        col_cuando = QVBoxLayout()
        col_cuando.addWidget(_titulo_campo("Bloques del pedido"))
        self.tabla_bloques = QTableWidget()
        self.tabla_bloques.setColumnCount(4)
        self.tabla_bloques.setHorizontalHeaderLabels(["Días", "Horario", "Comb. días", "Horas mínimas"])
        self.tabla_bloques.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_bloques.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_bloques.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_bloques.setMinimumHeight(218)
        encabezado_bloques = self.tabla_bloques.horizontalHeader()
        encabezado_bloques.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Días — para que quepan varios
        for columna in (1, 2, 3):
            encabezado_bloques.setSectionResizeMode(columna, QHeaderView.ResizeMode.Fixed)
        self.tabla_bloques.setColumnWidth(1, 90)
        self.tabla_bloques.setColumnWidth(2, 95)
        self.tabla_bloques.setColumnWidth(3, 115)
        self.tabla_bloques.itemSelectionChanged.connect(self._actualizar_boton_quitar_bloque)
        col_cuando.addWidget(self.tabla_bloques)

        col_cuando.addWidget(_titulo_campo("Combinación de bloques y consultorios"))
        self.combo_tipo_bloques = QComboBox()
        col_cuando.addWidget(self.combo_tipo_bloques)

        self.combo_sin_combinar = QComboBox()
        self.combo_sin_combinar.addItem("Sin combinación de consultorios", True)
        self.combo_sin_combinar.addItem("Con combinación de consultorios", False)
        col_cuando.addWidget(self.combo_sin_combinar)

        self.boton_quitar_bloque = QPushButton("Quitar bloque")
        self.boton_quitar_bloque.setObjectName("botonSecundario")
        self.boton_quitar_bloque.setEnabled(False)
        self.boton_quitar_bloque.clicked.connect(self._quitar_bloque)
        col_cuando.addWidget(self.boton_quitar_bloque)
        col_cuando.addStretch()

        col_condiciones = QVBoxLayout()
        col_condiciones.addWidget(_titulo_campo("Características de los consultorios"))
        grid_caracteristicas = QGridLayout()

        contenedor_tamano = QWidget()
        fila_tamano = QHBoxLayout(contenedor_tamano)
        fila_tamano.setContentsMargins(0, 0, 0, 0)
        self.casilla_tamano = QCheckBox("Tamaño mínimo")
        self.combo_tamano = QComboBox()
        for etiqueta, valor in _TAMANOS_MINIMOS:
            self.combo_tamano.addItem(etiqueta, valor)
        self.combo_tamano.setEnabled(False)
        self.casilla_tamano.toggled.connect(self.combo_tamano.setEnabled)
        fila_tamano.addWidget(self.casilla_tamano)
        fila_tamano.addWidget(self.combo_tamano)

        self.casilla_ventana = QCheckBox("Con ventana")
        self.casilla_camilla = QCheckBox("Apto camilla")
        self.casilla_placard = QCheckBox("Con placard")
        self.casilla_aire = QCheckBox("Con aire acondicionado")

        grid_caracteristicas.addWidget(contenedor_tamano, 0, 0, 1, 2)
        grid_caracteristicas.addWidget(self.casilla_ventana, 1, 0)
        grid_caracteristicas.addWidget(self.casilla_camilla, 1, 1)
        grid_caracteristicas.addWidget(self.casilla_placard, 2, 0)
        grid_caracteristicas.addWidget(self.casilla_aire, 2, 1)
        col_condiciones.addLayout(grid_caracteristicas)

        self.campo_detalle = QPlainTextEdit()
        self.campo_detalle.setFixedHeight(196)
        col_condiciones.addWidget(_titulo_campo("Comentarios"))
        col_condiciones.addWidget(self.campo_detalle)

        self.boton_crear = QPushButton("Crear pedido")
        self.boton_crear.setObjectName("botonPrimario")
        self.boton_crear.clicked.connect(self._crear_pedido)
        col_condiciones.addWidget(self.boton_crear)
        col_condiciones.addStretch()

        fila_columnas.addLayout(col_quien, 1)
        fila_columnas.addLayout(col_cuando, 1)
        fila_columnas.addLayout(col_condiciones, 1)
        layout.addLayout(fila_columnas)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(10)
        self.tabla.setHorizontalHeaderLabels([
            "Fecha pedido", "Profesional", "Días", "Horario", "Combinación días", "Combinación bloques",
            "Combinación consultorios", "Condiciones", "Coincidencia", "Comentarios",
        ])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.itemSelectionChanged.connect(self._mostrar_cobertura)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setItemDelegateForColumn(8, _DelegadoSinResaltarSeleccion(self.tabla))
        layout.addWidget(self.tabla, stretch=1)

        fila_botones = QHBoxLayout()
        self.boton_descartar = QPushButton("Descartar pedido")
        self.boton_descartar.setObjectName("botonSecundario")
        self.boton_descartar.clicked.connect(self._descartar)
        self.boton_editar = QPushButton("Editar pedido")
        self.boton_editar.setObjectName("botonSecundario")
        self.boton_editar.clicked.connect(self._editar_pedido)
        fila_botones.addStretch()
        fila_botones.addWidget(self.boton_descartar)
        fila_botones.addWidget(self.boton_editar)
        layout.addLayout(fila_botones)

        layout.addWidget(_titulo_campo("Cobertura de la coincidencia seleccionada"))
        self.texto_cobertura = QPlainTextEdit()
        self.texto_cobertura.setReadOnly(True)
        self.texto_cobertura.setFixedHeight(110)
        layout.addWidget(self.texto_cobertura)

        self._actualizar_combo_tipo_bloques()
        self._cargar_profesionales()
        self._cargar_localidades()

    def _cargar_profesionales(self) -> None:
        self.combo_profesional.clear()
        for id_, etiqueta in _opciones_profesional(self.conn):
            self.combo_profesional.addItem(etiqueta, id_)

    def _cargar_localidades(self) -> None:
        """Cascada Localidad -> Edificio -> Unidad, mismo patrón compacto
        (con "Todas las X" tildado por defecto y colapsada hasta que se
        la abre) que usa Oferta de consultorios — reusa sus mismos
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

    def actualizar(self) -> None:
        periodo = periodo_actual(self.conn)
        anio, mes = (int(p) for p in periodo.split("-"))
        resultado = listar_pedidos_con_coincidencia(self.conn, anio, mes)
        self._pedidos = [p for p, _ in resultado]
        self._coincidencias = [c for _, c in resultado]
        self.texto_cobertura.clear()

        self.tabla.setRowCount(len(resultado))
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        repo_bloque = obtener_repositorio(self.conn, "ListaEsperaBloque")
        for fila_idx, (pedido, coincidencia) in enumerate(resultado):
            fecha = date.fromisoformat(pedido["FechaPedido"]).strftime("%d-%m-%Y")
            self.tabla.setItem(fila_idx, 0, _item_con_tooltip(fecha))

            profesional = repo_profesional.obtener(pedido["IdProfesional"])
            nombre = _texto_profesional(profesional) if profesional else "?"
            self.tabla.setItem(fila_idx, 1, _item_con_tooltip(nombre))

            bloques = repo_bloque.listar(IdPedido=pedido["IdPedido"])
            separador = " Y " if pedido["TipoCombinacion"] == "Y" else " O "
            self.tabla.setItem(
                fila_idx, 2,
                _item_con_tooltip(separador.join(", ".join(json.loads(b["Dias"] or "[]")) for b in bloques)),
            )
            self.tabla.setItem(
                fila_idx, 3,
                _item_con_tooltip(
                    separador.join(_horario_texto(b["HorarioDesde"], b["HorarioHasta"]) for b in bloques)
                ),
            )
            self.tabla.setItem(
                fila_idx, 4,
                _item_con_tooltip(
                    separador.join(
                        ("Todos los días (Y)" if b["TipoCombinacionDias"] == "Y" else "Alcanza con un día (O)")
                        for b in bloques
                    )
                ),
            )
            etiqueta_bloques = "Todos los bloques (Y)" if pedido["TipoCombinacion"] == "Y" else "Alcanza con un bloque (O)"
            self.tabla.setItem(fila_idx, 5, _item_con_tooltip(etiqueta_bloques))

            condiciones = json.loads(pedido["CondicionesConsultorio"] or "{}")
            etiqueta_combinacion_consultorios = (
                "Sin combinación de consultorios" if condiciones.get("sinCombinar")
                else "Con combinación de consultorios"
            )
            self.tabla.setItem(fila_idx, 6, _item_con_tooltip(etiqueta_combinacion_consultorios))
            self.tabla.setItem(fila_idx, 7, _item_con_tooltip(_texto_condiciones(self.conn, condiciones)))

            color = coincidencia.color if coincidencia else None
            item_color = _item_con_tooltip(_ETIQUETA_COLOR.get(color, "Sin cobertura"))
            if color:
                item_color.setBackground(QColor(_COLOR_CELDA[color]))
            self.tabla.setItem(fila_idx, 8, item_color)
            self.tabla.setItem(fila_idx, 9, _item_con_tooltip(pedido["Detalle"] or ""))
        self.tabla.resizeColumnsToContents()
        if self.tabla.columnWidth(2) < 180:  # "Días" — que entren varios días sin recortar
            self.tabla.setColumnWidth(2, 180)

    def _mostrar_cobertura(self) -> None:
        """Al seleccionar un pedido con coincidencia, qué bloques/días y
        qué consultorio(s) puntuales la cubren — antes esto solo se podía
        inferir indirectamente desde el color."""
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            self.texto_cobertura.clear()
            return
        coincidencia = self._coincidencias[filas[0].row()]
        if coincidencia is None:
            self.texto_cobertura.setPlainText("Sin cobertura: no hay forma de cubrir todo el horario pedido.")
            return

        lineas = []
        for dia in DIAS_SEMANA:
            tramos = coincidencia.tramos_por_dia.get(dia)
            if not tramos:
                continue
            lineas.append(f"{dia}:")
            for tramo in sorted(tramos, key=lambda t: t.hora_inicio):
                fila_consultorio = self.conn.execute(
                    "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS NombreEdificio FROM Consultorio c "
                    "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
                    "WHERE c.IdConsultorio = ?", (tramo.id_consultorio,),
                ).fetchone()
                etiqueta = (
                    f"{fila_consultorio['NombreEdificio']} - {fila_consultorio['Departamento']} - "
                    f"Consultorio {fila_consultorio['NumeroConsultorio']}"
                    if fila_consultorio else f"Consultorio #{tramo.id_consultorio}"
                )
                lineas.append(f"    {_horario_texto(tramo.hora_inicio, tramo.hora_fin)} — {etiqueta}")
        self.texto_cobertura.setPlainText("\n".join(lineas))

    def _dias_seleccionados(self) -> list[str]:
        return [dia for dia, check in self._checks_dia.items() if check.isChecked()]

    def _condiciones(self) -> dict:
        condiciones = {}
        if self.casilla_ventana.isChecked():
            condiciones["ventana"] = True
        if self.casilla_camilla.isChecked():
            condiciones["aptoCamilla"] = True
        if self.casilla_placard.isChecked():
            condiciones["placard"] = True
        if self.casilla_aire.isChecked():
            condiciones["aire"] = True
        if self.combo_sin_combinar.currentData():
            condiciones["sinCombinar"] = True
        if self.casilla_tamano.isChecked():
            condiciones["tamano"] = self.combo_tamano.currentData()
        condiciones["idsUnidad"] = self._ids_unidad_seleccionadas()
        return condiciones

    def _bloque_del_formulario(self) -> dict:
        return {
            "dias": self._dias_seleccionados(), "horario_desde": self.spin_desde.value(),
            "horario_hasta": self.spin_hasta.value(), "tipo_combinacion_dias": self.combo_tipo.currentData(),
            "cantidad_horas_requeridas": (
                self.spin_cantidad_horas.value() if self.casilla_cantidad_horas.isChecked() else None
            ),
        }

    def _refrescar_tabla_bloques(self) -> None:
        self.tabla_bloques.setRowCount(len(self._bloques_pendientes))
        for fila_idx, bloque in enumerate(self._bloques_pendientes):
            self.tabla_bloques.setItem(fila_idx, 0, QTableWidgetItem(", ".join(bloque["dias"])))
            self.tabla_bloques.setItem(
                fila_idx, 1, QTableWidgetItem(_horario_texto(bloque["horario_desde"], bloque["horario_hasta"])),
            )
            etiqueta_tipo = "Y" if bloque["tipo_combinacion_dias"] == "Y" else "O"
            self.tabla_bloques.setItem(fila_idx, 2, QTableWidgetItem(etiqueta_tipo))
            cantidad_horas = bloque.get("cantidad_horas_requeridas")
            texto_horas = hora_fmt(cantidad_horas) if cantidad_horas else "Completo"
            self.tabla_bloques.setItem(fila_idx, 3, QTableWidgetItem(texto_horas))
        self._actualizar_combo_tipo_bloques()
        self._actualizar_boton_quitar_bloque()

    def _actualizar_combo_tipo_bloques(self) -> None:
        """Con un solo bloque (o ninguno) la combinación entre bloques no
        tiene sentido — el combo se deshabilita mostrando "Bloque único"
        en gris. Recién con más de uno se habilita para elegir entre
        "Alcanza con un bloque (O)" y "Necesarios todos los bloques (Y)"."""
        valor_actual = self.combo_tipo_bloques.currentData()
        self.combo_tipo_bloques.blockSignals(True)
        self.combo_tipo_bloques.clear()
        if len(self._bloques_pendientes) <= 1:
            self.combo_tipo_bloques.addItem("Bloque único", "O")
            self.combo_tipo_bloques.setEnabled(False)
        else:
            self.combo_tipo_bloques.addItem("Alcanza con un bloque (O)", "O")
            self.combo_tipo_bloques.addItem("Necesarios todos los bloques (Y)", "Y")
            indice = self.combo_tipo_bloques.findData(valor_actual)
            self.combo_tipo_bloques.setCurrentIndex(indice if indice >= 0 else 0)
            self.combo_tipo_bloques.setEnabled(True)
        self.combo_tipo_bloques.blockSignals(False)

    def _actualizar_boton_quitar_bloque(self) -> None:
        filas = self.tabla_bloques.selectionModel().selectedRows()
        self.boton_quitar_bloque.setEnabled(bool(filas))

    def _agregar_bloque(self) -> None:
        bloque = self._bloque_del_formulario()
        if not bloque["dias"]:
            QMessageBox.warning(self, "Agregar bloque", "Elegí al menos un día para el bloque.")
            return
        self._bloques_pendientes.append(bloque)
        self._refrescar_tabla_bloques()
        for check in self._checks_dia.values():
            check.setChecked(False)

    def _quitar_bloque(self) -> None:
        filas = self.tabla_bloques.selectionModel().selectedRows()
        if not filas:
            return
        del self._bloques_pendientes[filas[0].row()]
        self._refrescar_tabla_bloques()

    def _crear_pedido(self) -> None:
        en_edicion = self._id_pedido_en_edicion is not None
        titulo = "Guardar cambios" if en_edicion else "Crear pedido"
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, titulo, "No hay profesionales cargados.")
            return
        if not self._bloques_pendientes:
            QMessageBox.warning(self, titulo, 'Agregá al menos un bloque con "Agregar bloque" antes de continuar.')
            return

        if not en_edicion:
            pedidos_activos = obtener_repositorio(self.conn, "ListaEspera").listar(
                IdProfesional=id_profesional, Estado="Activo",
            )
            if pedidos_activos:
                respuesta = QMessageBox.question(
                    self, titulo,
                    "Este profesional ya tiene un pedido activo — no puede haber dos al mismo tiempo. "
                    "¿Querés editarlo en su lugar?",
                )
                if respuesta == QMessageBox.StandardButton.Yes:
                    self._cargar_pedido_en_formulario(pedidos_activos[0])
                return

        bloques = list(self._bloques_pendientes)
        try:
            if en_edicion:
                editar_pedido(
                    self.conn, self._id_pedido_en_edicion,
                    tipo_combinacion_bloques=self.combo_tipo_bloques.currentData(), bloques=bloques,
                    condiciones_consultorio=self._condiciones(),
                    detalle=self.campo_detalle.toPlainText().strip() or None,
                )
            else:
                crear_pedido(
                    self.conn, id_profesional=id_profesional,
                    tipo_combinacion_bloques=self.combo_tipo_bloques.currentData(), bloques=bloques,
                    condiciones_consultorio=self._condiciones(),
                    detalle=self.campo_detalle.toPlainText().strip() or None,
                )
        except ValueError as error:
            QMessageBox.warning(self, titulo, str(error))
            return
        self.conn.commit()
        self._id_pedido_en_edicion = None
        self.boton_crear.setText("Crear pedido")
        self._bloques_pendientes = []
        self._refrescar_tabla_bloques()
        self.actualizar()

    def _fila_seleccionada_pedido(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._pedidos[filas[0].row()]

    def _editar_pedido(self) -> None:
        """Carga el pedido seleccionado en el formulario de arriba para
        modificarlo — "Crear pedido" pasa a decir "Guardar cambios" y, al
        confirmar, reemplaza los bloques/condiciones del pedido existente
        y le actualiza la fecha a hoy (ver `editar_pedido` en
        `app.negocio.lista_espera`), en vez de crear uno nuevo."""
        pedido = self._fila_seleccionada_pedido()
        if pedido is None:
            QMessageBox.warning(self, "Editar pedido", "Elegí un pedido de la tabla para editar.")
            return
        self._cargar_pedido_en_formulario(pedido)

    def _cargar_pedido_en_formulario(self, pedido: sqlite3.Row) -> None:
        """Comparte la carga entre "Editar pedido" y el aviso de "Crear
        pedido" cuando el profesional ya tiene uno activo (ver
        `_crear_pedido`) — en los dos casos hay que dejar el formulario
        listo para editar el mismo pedido existente."""
        indice_profesional = self.combo_profesional.findData(pedido["IdProfesional"])
        if indice_profesional >= 0:
            self.combo_profesional.setCurrentIndex(indice_profesional)

        condiciones = json.loads(pedido["CondicionesConsultorio"] or "{}")
        self.casilla_ventana.setChecked(bool(condiciones.get("ventana")))
        self.casilla_camilla.setChecked(bool(condiciones.get("aptoCamilla")))
        self.casilla_placard.setChecked(bool(condiciones.get("placard")))
        self.casilla_aire.setChecked(bool(condiciones.get("aire")))
        indice_sin_combinar = self.combo_sin_combinar.findData(bool(condiciones.get("sinCombinar")))
        if indice_sin_combinar >= 0:
            self.combo_sin_combinar.setCurrentIndex(indice_sin_combinar)
        tamano = condiciones.get("tamano")
        self.casilla_tamano.setChecked(bool(tamano))
        if tamano:
            indice_tamano = self.combo_tamano.findData(tamano)
            if indice_tamano >= 0:
                self.combo_tamano.setCurrentIndex(indice_tamano)

        self._cargar_localidades()  # cascada a "Todas/Todos" primero, para que la unidad pedida esté disponible
        ids_unidad = condiciones.get("idsUnidad") or []
        if ids_unidad:
            self.lista_unidad.clearSelection()
            for i in range(self.lista_unidad.count()):
                item = self.lista_unidad.item(i)
                if item.data(Qt.ItemDataRole.UserRole) in ids_unidad:
                    item.setSelected(True)

        repo_bloque = obtener_repositorio(self.conn, "ListaEsperaBloque")
        self._bloques_pendientes = [
            {
                "dias": json.loads(b["Dias"] or "[]"), "horario_desde": b["HorarioDesde"],
                "horario_hasta": b["HorarioHasta"], "tipo_combinacion_dias": b["TipoCombinacionDias"],
                "cantidad_horas_requeridas": b["CantidadHorasRequeridas"],
            }
            for b in repo_bloque.listar(IdPedido=pedido["IdPedido"])
        ]
        self._refrescar_tabla_bloques()
        for check in self._checks_dia.values():
            check.setChecked(False)

        indice_tipo_bloques = self.combo_tipo_bloques.findData(pedido["TipoCombinacion"])
        if indice_tipo_bloques >= 0:
            self.combo_tipo_bloques.setCurrentIndex(indice_tipo_bloques)

        self.campo_detalle.setPlainText(pedido["Detalle"] or "")

        self._id_pedido_en_edicion = pedido["IdPedido"]
        self.boton_crear.setText("Guardar cambios")

    def _descartar(self) -> None:
        pedido = self._fila_seleccionada_pedido()
        if pedido is None:
            return
        marcar_descartado(self.conn, pedido["IdPedido"])
        self.conn.commit()
        self.actualizar()
