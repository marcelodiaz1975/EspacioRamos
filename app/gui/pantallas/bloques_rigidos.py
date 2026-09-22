"""Bloques rígidos (F06, sección 3.11): franjas horarias que, si se
reservan, tienen que cubrirse enteras (no parcialmente) — la validación
la aplica `app.negocio.reservas.verificar_bloques_rigidos` sobre
DiasLogica; DiasVisualizacion es el conjunto de días en que la grilla
muestra ese horario como bloque rígido (puede ser más amplio que
DiasLogica, como el default de 18-21hs: lógica L-V, visualización L-S).

No usa `PantallaCRUD` (ver CLAUDE.md, "Catálogos"): el diálogo Nuevo/
Editar necesita dos listas de días con checks (lógica y visualización),
un tipo de control que `crud_generico.Campo` no contempla — armar un
tipo nuevo ahí serviría solo a esta pantalla, así que se arma a mano
siguiendo el mismo lenguaje visual que los catálogos genéricos (mismo
criterio que Gestor de archivos): solapa única "Bloques rígidos", Buscar
+ Nuevo/Editar/Eliminar en una columna izquierda de ancho fijo, tabla
ordenable a la derecha. El título de la solapa es fijo (no "Listado"
genérico) porque, igual que Panel de control, a futuro esta pantalla va
a terminar viviendo dentro de otro formulario todavía sin definir — no
se tocó nada de la estructura pensando en eso, es solo un aviso para
cuando se defina."""
from __future__ import annotations

import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.crud_generico import _normalizar_busqueda
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.orden_tabla import OrdenTabla
from app.negocio.dias import DIAS_SEMANA
from app.repositorio.registro import obtener_repositorio

_ID_REGISTRO = Qt.ItemDataRole.UserRole
_ANCHO_CAMPO = 240  # mismo ancho que el panel izquierdo de los catálogos genéricos
_PADDING_COLUMNA = 30  # mismo criterio que `novedades._ajustar_columnas`: más aire que el ancho justo


def _resumen_dias(dias: list[str]) -> str:
    if dias == DIAS_SEMANA:
        return "Todos los días"
    return ", ".join(dias) if dias else "(sin días)"


def _fmt_hora(valor: float) -> str:
    """"18:00hs" — mismo criterio que `_SpinHora`/`_fmt_hora` de
    Configuración general/Reservas/Oferta/Lista de espera."""
    horas = int(valor)
    minutos = round((valor - horas) * 60)
    return f"{horas}:{minutos:02d}hs"


def _fmt_horario(hora_inicio: float, hora_fin: float) -> str:
    return f"{_fmt_hora(hora_inicio)} a {_fmt_hora(hora_fin)}"


def _ajustar_columnas(tabla: QTableWidget) -> None:
    """Mismo criterio que `novedades._ajustar_columnas`: `resizeColumnsToContents`
    deja las columnas al ancho justo del contenido — se les agrega
    `_PADDING_COLUMNA` de más a cada una, sin igualarlas entre sí."""
    tabla.resizeColumnsToContents()
    for columna in range(tabla.columnCount()):
        tabla.setColumnWidth(columna, tabla.columnWidth(columna) + _PADDING_COLUMNA)


class _SpinHora(QDoubleSpinBox):
    """QDoubleSpinBox que se muestra como horario ("18:00hs") en vez del
    decimal con punto que arrastra Qt por defecto — mismo criterio que
    `_SpinHora` de Configuración general/Oferta/Reservas/Lista de espera
    (duplicado acá, no importado: son pantallas sin relación entre sí)."""

    def textFromValue(self, value: float) -> str:  # noqa: N802 (nombre impuesto por Qt)
        return _fmt_hora(value)

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


class _ListaDias(QListWidget):
    def __init__(self, seleccionados: list[str] | None = None, parent=None):
        super().__init__(parent)
        seleccionados = seleccionados or []
        for dia in DIAS_SEMANA:
            item = QListWidgetItem(dia)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if dia in seleccionados else Qt.CheckState.Unchecked)
            self.addItem(item)
        self.setMaximumHeight(140)

    def seleccionados(self) -> list[str]:
        return [
            self.item(i).text() for i in range(self.count())
            if self.item(i).checkState() == Qt.CheckState.Checked
        ]


class _DialogoBloque(QDialog):
    def __init__(self, bloque: sqlite3.Row | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bloque rígido")
        layout = QFormLayout(self)

        dias_logica = json.loads(bloque["DiasLogica"]) if bloque and bloque["DiasLogica"] else []
        dias_visualizacion = json.loads(bloque["DiasVisualizacion"]) if bloque and bloque["DiasVisualizacion"] else dias_logica

        self.spin_desde = _SpinHora()
        self.spin_desde.setRange(0, 23.5)
        self.spin_desde.setSingleStep(0.5)
        self.spin_desde.setValue(bloque["HoraInicio"] if bloque else 9)
        layout.addRow("Hora inicio", self.spin_desde)

        self.spin_hasta = _SpinHora()
        self.spin_hasta.setRange(0.5, 24)
        self.spin_hasta.setSingleStep(0.5)
        self.spin_hasta.setValue(bloque["HoraFin"] if bloque else 11)
        layout.addRow("Hora fin", self.spin_hasta)

        layout.addRow(QLabel("Días en que aplica la restricción (no se puede reservar parcial)"))
        self.lista_logica = _ListaDias(dias_logica)
        layout.addRow(self.lista_logica)

        layout.addRow(QLabel("Días en que la grilla lo muestra como bloque rígido"))
        self.lista_visualizacion = _ListaDias(dias_visualizacion)
        layout.addRow(self.lista_visualizacion)

        self.casilla_activo = QCheckBox("Activo")
        self.casilla_activo.setChecked(bool(bloque["Activo"]) if bloque else True)
        layout.addRow(self.casilla_activo)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

    def _validar_y_aceptar(self) -> None:
        if self.spin_hasta.value() <= self.spin_desde.value():
            QMessageBox.warning(self, "Bloque rígido", "La hora fin tiene que ser posterior a la hora inicio.")
            return
        if not self.lista_logica.seleccionados():
            QMessageBox.warning(self, "Bloque rígido", "Elegí al menos un día para la restricción.")
            return
        if not self.lista_visualizacion.seleccionados():
            QMessageBox.warning(self, "Bloque rígido", "Elegí al menos un día para la visualización en la grilla.")
            return
        self.accept()

    def valores(self) -> dict:
        return {
            "HoraInicio": self.spin_desde.value(),
            "HoraFin": self.spin_hasta.value(),
            "DiasLogica": json.dumps(self.lista_logica.seleccionados()),
            "DiasVisualizacion": json.dumps(self.lista_visualizacion.seleccionados()),
            "Activo": 1 if self.casilla_activo.isChecked() else 0,
        }


class PantallaBloquesRigidos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.repositorio = obtener_repositorio(conn, "BloqueRigido")
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar": el
        widget todavía no está mostrado en ese momento."""
        super().showEvent(event)
        self._orden.reiniciar()
        self.actualizar()
        self.campo_buscar.setFocus()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Bloques rígidos")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        solapas = QTabWidget()
        panel_solapa = QWidget()
        panel_solapa.setObjectName("panelSolapa")
        layout_solapa = QHBoxLayout(panel_solapa)

        panel_izquierda = QWidget()
        columna = QVBoxLayout(panel_izquierda)
        etiqueta_buscar = QLabel("Buscar")
        etiqueta_buscar.setObjectName("subtituloCampo")
        columna.addWidget(etiqueta_buscar)
        self.campo_buscar = QLineEdit()
        self.campo_buscar.setFixedWidth(_ANCHO_CAMPO)
        self.campo_buscar.textChanged.connect(self._aplicar_filtro_busqueda)
        columna.addWidget(self.campo_buscar)

        self.boton_nuevo = QPushButton("Nuevo")
        self.boton_nuevo.setObjectName("botonPrimario")
        self.boton_nuevo.setFixedWidth(_ANCHO_CAMPO)
        self.boton_nuevo.clicked.connect(self._nuevo)
        self.boton_editar = QPushButton("Editar")
        self.boton_editar.setObjectName("botonSecundario")
        self.boton_editar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_editar.clicked.connect(self._editar)
        self.boton_eliminar = QPushButton("Eliminar")
        self.boton_eliminar.setObjectName("botonSecundario")
        self.boton_eliminar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_eliminar.clicked.connect(self._eliminar)
        columna.addWidget(self.boton_nuevo)
        columna.addWidget(self.boton_editar)
        columna.addWidget(self.boton_eliminar)
        columna.addStretch()
        layout_solapa.addWidget(panel_izquierda)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Horario", "Días (restricción)", "Días (grilla)", "Activo"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.doubleClicked.connect(self._editar)
        layout_solapa.addWidget(self.tabla, stretch=1)

        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel_solapa)
        solapas.addTab(scroll, "Bloques rígidos")
        solapas.tabBar().setDrawBase(False)
        layout.addWidget(solapas, stretch=1)

        self._foco = instalar_enter_avanza_foco(
            [self.campo_buscar, self.boton_nuevo, self.boton_editar, self.boton_eliminar], parent=self,
        )
        self._orden = OrdenTabla(self.tabla, self.actualizar)

    def _aplicar_filtro_busqueda(self, *_args) -> None:
        """Mismo criterio que "Filtros que solo afectan la visualización"
        de los catálogos genéricos: solo oculta filas, sin distinguir
        mayúsculas ni acentos, por cualquier columna visible."""
        buscado = _normalizar_busqueda(self.campo_buscar.text().strip())
        for fila in range(self.tabla.rowCount()):
            if not buscado:
                self.tabla.setRowHidden(fila, False)
                continue
            texto_fila = " ".join(
                self.tabla.item(fila, col).text()
                for col in range(self.tabla.columnCount())
                if self.tabla.item(fila, col) is not None
            )
            self.tabla.setRowHidden(fila, buscado not in _normalizar_busqueda(texto_fila))

    def _clave_orden(self, registros: list[sqlite3.Row], columna: int):
        def clave(r: sqlite3.Row):
            if columna == 0:
                return r["HoraInicio"]
            if columna == 1:
                return _resumen_dias(json.loads(r["DiasLogica"] or "[]"))
            if columna == 2:
                return _resumen_dias(json.loads(r["DiasVisualizacion"] or "[]"))
            return bool(r["Activo"])
        return clave

    def actualizar(self) -> None:
        registros = self.repositorio.listar()
        if self._orden.columna is not None:
            registros = sorted(
                registros, key=self._clave_orden(registros, self._orden.columna), reverse=not self._orden.ascendente
            )
        self.tabla.setRowCount(len(registros))
        for fila_idx, r in enumerate(registros):
            item = QTableWidgetItem(_fmt_horario(r["HoraInicio"], r["HoraFin"]))
            item.setData(_ID_REGISTRO, r["IdBloqueRigido"])
            self.tabla.setItem(fila_idx, 0, item)
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(_resumen_dias(json.loads(r["DiasLogica"] or "[]"))))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(_resumen_dias(json.loads(r["DiasVisualizacion"] or "[]"))))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem("Sí" if r["Activo"] else "No"))
        _ajustar_columnas(self.tabla)
        self._aplicar_filtro_busqueda()

    def _fila_seleccionada_id(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self.tabla.item(filas[0].row(), 0).data(_ID_REGISTRO)

    def _nuevo(self) -> None:
        dialogo = _DialogoBloque(parent=self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.repositorio.crear(**dialogo.valores())
            self.actualizar()
            self.boton_nuevo.setFocus()

    def _editar(self) -> None:
        id_valor = self._fila_seleccionada_id()
        if id_valor is None:
            QMessageBox.information(self, "Editar", "Seleccioná un bloque para editar.")
            return
        bloque = self.repositorio.obtener(id_valor)
        dialogo = _DialogoBloque(bloque, parent=self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.repositorio.actualizar(id_valor, **dialogo.valores())
            self.actualizar()
            self.boton_nuevo.setFocus()

    def _eliminar(self) -> None:
        id_valor = self._fila_seleccionada_id()
        if id_valor is None:
            QMessageBox.information(self, "Eliminar", "Seleccioná un bloque para eliminar.")
            return
        confirmacion = QMessageBox.question(self, "Eliminar", "¿Confirmás eliminar el bloque rígido seleccionado?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        self.repositorio.eliminar(id_valor)
        self.actualizar()
        self.boton_nuevo.setFocus()
