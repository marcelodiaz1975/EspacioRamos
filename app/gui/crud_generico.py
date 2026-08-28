"""Pantalla CRUD genérica: cubre las pantallas de catálogo simples (Edificios,
Unidades, Consultorios, Responsables, Tipos de licencia, Listas editables,
Condiciones y normas, Mensajes predefinidos) sin escribir una clase por tabla.
Se parametriza con una lista de Campo (columna, etiqueta, tipo de control) y
usa el Repositorio genérico (app/repositorio/base.py) para leer y escribir."""
from __future__ import annotations

import sqlite3
import weakref
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.orden_tabla import OrdenTabla
from app.repositorio.registro import obtener_repositorio

_ID_REGISTRO = Qt.ItemDataRole.UserRole


def _referencia_debil(funcion):
    """Envuelve un callback en una referencia débil (mismo motivo que
    OrdenTabla, ver app/gui/widgets/orden_tabla.py): `al_crear`/
    `al_actualizar`/`al_eliminar` casi siempre son métodos atados de la
    pantalla compuesta dueña de este PantallaCRUD (ej. Llaves), y
    guardarlos fuertes crearía un ciclo pantalla -> PantallaCRUD ->
    pantalla que reventaba el proceso (segfault) si el recolector cíclico
    de Python corría en mal momento contra la destrucción de widgets de
    Qt. Devuelve un resolver de cero argumentos: llamarlo da el callback
    vivo o None si ya se recolectó."""
    if funcion is None:
        return lambda: None
    if hasattr(funcion, "__self__"):
        return weakref.WeakMethod(funcion)
    return weakref.ref(funcion)


@dataclass
class Campo:
    nombre: str
    etiqueta: str
    tipo: str = "texto"  # "texto" | "texto_largo" | "numero" | "booleano" | "combo"
    opciones: Callable[[sqlite3.Connection], list[tuple]] | None = None
    requerido: bool = False
    combo_editable: bool = False
    """Solo para tipo="combo": si el combo acepta texto libre además de las
    opciones sugeridas — para catálogos abiertos (p. ej. CondicionFiscal)
    a diferencia de los realmente cerrados (p. ej. TipoFechaEspecial, que
    feriados.py compara por string exacto: un valor fuera de catálogo ahí
    rompe en silencio el descuento del 100%)."""
    normalizar: Callable[[str], str] | None = None
    """Solo para tipo="texto": transforma el texto tipeado antes de
    guardarlo (p. ej. CUIT sin guiones — sección 3.4)."""


class PantallaCRUD(QWidget):
    def __init__(
        self, conn: sqlite3.Connection, tabla: str, titulo: str, campos: list[Campo], parent=None,
        al_actualizar: Callable[[sqlite3.Row, dict], None] | None = None,
        al_crear: Callable[[int, dict], None] | None = None,
        al_eliminar: Callable[[sqlite3.Row], None] | None = None,
        al_abrir_dialogo: Callable[[QDialog], None] | None = None,
        al_guardar: Callable[[dict, sqlite3.Row | None], dict | None] | None = None,
        solo_lectura: bool = False,
        instalar_foco: bool = True,
    ):
        super().__init__(parent)
        self.conn = conn
        self.tabla = tabla
        self.campos = campos
        self.repositorio = obtener_repositorio(conn, tabla)
        # al_actualizar/al_crear/al_eliminar: casi siempre son métodos
        # atados de una pantalla compuesta dueña de este PantallaCRUD (ej.
        # Llaves, que los usa para armar su propio "Deshacer último
        # movimiento" sin duplicar acá la lógica de guardado). Guardados
        # como referencia débil (ver `_referencia_debil`) para no crear un
        # ciclo pantalla -> PantallaCRUD -> pantalla.
        self._al_actualizar = _referencia_debil(al_actualizar)
        self._al_crear = _referencia_debil(al_crear)
        self._al_eliminar = _referencia_debil(al_eliminar)
        # solo_lectura: sin botones Nuevo/Editar/Eliminar ni doble clic para
        # editar — para catálogos que se modifican solo desde un proceso de
        # negocio específico (p. ej. Esquema de descuentos, que DC-10 §1.1
        # dice que solo debe tocarse durante el análisis de aumentos) y acá
        # se muestran únicamente como consulta/historial.
        self.solo_lectura = solo_lectura
        # instalar_foco: arma su propia cadena de Enter-avanza-foco (Nuevo /
        # Editar / Eliminar, con foco inicial en Nuevo) — apagalo cuando una
        # pantalla compuesta (p. ej. Llaves) va a armar una cadena propia que
        # combine estos tres botones con los suyos, para no instalar dos
        # filtros de evento distintos sobre los mismos widgets.
        self.instalar_foco = instalar_foco and not solo_lectura
        # al_abrir_dialogo: llamado con el diálogo recién construido, antes de
        # mostrarlo, tanto al crear un registro nuevo como al editar uno
        # existente — para pantallas que necesitan sugerir/reaccionar entre
        # campos del mismo formulario (p. ej. Profesionales: código sugerido
        # según categoría, desplegable de Tratamiento según profesión/sexo)
        # sin acoplar eso al CRUD genérico. Los hooks que solo deben sugerir
        # sobre un campo vacío (y no pisar un valor ya cargado) comparan
        # contra la última sugerencia propia, no contra "vacío".
        self.al_abrir_dialogo = al_abrir_dialogo
        # al_guardar: llamado con (valores, registro_existente_o_None) justo
        # antes de crear/actualizar — devuelve los valores a guardar (puede
        # modificarlos) o None para cancelar el guardado por completo. Para
        # validaciones entre registros que el diálogo por sí solo no puede
        # resolver (p. ej. Gastos operativos: no puede convivir un origen
        # Manual y uno Importado para el mismo concepto y período).
        self.al_guardar = al_guardar
        self.boton_nuevo = self.boton_editar = self.boton_eliminar = None
        self._armar_ui(titulo)
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar":
        el widget todavía no está mostrado en ese momento."""
        super().showEvent(event)
        self._orden.reiniciar()
        self.actualizar()
        if self.instalar_foco:
            self.boton_nuevo.setFocus()

    def _armar_ui(self, titulo: str) -> None:
        layout = QVBoxLayout(self)

        etiqueta_titulo = QLabel(titulo)
        etiqueta_titulo.setObjectName("tituloPantalla")
        layout.addWidget(etiqueta_titulo)

        if not self.solo_lectura:
            fila_botones = QHBoxLayout()
            self.boton_nuevo = QPushButton("Nuevo")
            self.boton_nuevo.setObjectName("botonPrimario")
            self.boton_nuevo.clicked.connect(self._nuevo)
            self.boton_editar = QPushButton("Editar")
            self.boton_editar.clicked.connect(self._editar)
            self.boton_eliminar = QPushButton("Eliminar")
            self.boton_eliminar.clicked.connect(self._eliminar)
            fila_botones.addWidget(self.boton_nuevo)
            fila_botones.addWidget(self.boton_editar)
            fila_botones.addWidget(self.boton_eliminar)
            fila_botones.addStretch()
            layout.addLayout(fila_botones)

        self.tabla_widget = QTableWidget()
        self.tabla_widget.setColumnCount(len(self.campos))
        self.tabla_widget.setHorizontalHeaderLabels([c.etiqueta for c in self.campos])
        self.tabla_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        if not self.solo_lectura:
            self.tabla_widget.doubleClicked.connect(self._editar)
        layout.addWidget(self.tabla_widget, stretch=1)

        if self.instalar_foco:
            self._foco = instalar_enter_avanza_foco(
                [self.boton_nuevo, self.boton_editar, self.boton_eliminar], parent=self,
            )
        self._orden = OrdenTabla(self.tabla_widget, self.actualizar)

    def actualizar(self) -> None:
        registros = self.repositorio.listar()
        if self._orden.columna is not None:
            registros = sorted(
                registros, key=self._clave_orden(self._orden.columna), reverse=not self._orden.ascendente
            )
        self.tabla_widget.setRowCount(len(registros))
        for fila_idx, registro in enumerate(registros):
            for col_idx, campo in enumerate(self.campos):
                item = QTableWidgetItem(self._texto_celda(registro, campo))
                if col_idx == 0:
                    item.setData(_ID_REGISTRO, registro[self.repositorio.clave_primaria])
                self.tabla_widget.setItem(fila_idx, col_idx, item)
        self.tabla_widget.resizeColumnsToContents()

    def _clave_orden(self, columna: int):
        campo = self.campos[columna]

        def clave(registro: sqlite3.Row):
            valor = registro[campo.nombre]
            if campo.tipo == "numero":
                return valor if valor is not None else float("-inf")
            if campo.tipo == "booleano":
                return bool(valor)
            return self._texto_celda(registro, campo)

        return clave

    def _texto_celda(self, registro: sqlite3.Row, campo: Campo) -> str:
        valor = registro[campo.nombre]
        if campo.tipo == "booleano":
            return "Sí" if valor else "No"
        if campo.tipo == "combo" and campo.opciones:
            opciones = dict(campo.opciones(self.conn))
            return opciones.get(valor, "" if valor is None else str(valor))
        return "" if valor is None else str(valor)

    def fila_seleccionada_id(self):
        """ID de la fila seleccionada, o None — pantallas compuestas (p. ej.
        Llaves) lo usan para saber sobre qué registro maestro operar."""
        filas = self.tabla_widget.selectionModel().selectedRows()
        if not filas:
            return None
        return self.tabla_widget.item(filas[0].row(), 0).data(_ID_REGISTRO)

    def _nuevo(self) -> None:
        dialogo = _DialogoRegistro(self.conn, self.campos, "Nuevo registro")
        if self.al_abrir_dialogo:
            self.al_abrir_dialogo(dialogo)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            valores = dialogo.valores()
            if self.al_guardar:
                valores = self.al_guardar(valores, None)
                if valores is None:
                    return
            id_nuevo = self.repositorio.crear(**valores)
            al_crear = self._al_crear()
            if al_crear:
                al_crear(id_nuevo, valores)
            self.actualizar()
            if self.instalar_foco:
                self.boton_nuevo.setFocus()

    def _editar(self) -> None:
        id_valor = self.fila_seleccionada_id()
        if id_valor is None:
            QMessageBox.information(self, "Editar", "Seleccioná un registro para editar.")
            return
        registro = self.repositorio.obtener(id_valor)
        dialogo = _DialogoRegistro(self.conn, self.campos, "Editar registro", registro=registro)
        if self.al_abrir_dialogo:
            self.al_abrir_dialogo(dialogo)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            valores = dialogo.valores()
            if self.al_guardar:
                valores = self.al_guardar(valores, registro)
                if valores is None:
                    return
            self.repositorio.actualizar(id_valor, **valores)
            al_actualizar = self._al_actualizar()
            if al_actualizar:
                al_actualizar(registro, valores)
            self.actualizar()
            if self.instalar_foco:
                self.boton_nuevo.setFocus()

    def _eliminar(self) -> None:
        id_valor = self.fila_seleccionada_id()
        if id_valor is None:
            QMessageBox.information(self, "Eliminar", "Seleccioná un registro para eliminar.")
            return
        confirmacion = QMessageBox.question(self, "Eliminar", "¿Confirmás eliminar el registro seleccionado?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        registro = self.repositorio.obtener(id_valor)
        try:
            self.repositorio.eliminar(id_valor)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Eliminar", "No se puede eliminar: hay otros registros que dependen de este.")
            return
        al_eliminar = self._al_eliminar()
        if al_eliminar:
            al_eliminar(registro)
        self.actualizar()
        if self.instalar_foco:
            self.boton_nuevo.setFocus()


class _DialogoRegistro(QDialog):
    def __init__(self, conn: sqlite3.Connection, campos: list[Campo], titulo: str, registro=None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.campos = campos
        self.setWindowTitle(titulo)
        self._entradas: dict[str, QWidget] = {}

        layout_general = QVBoxLayout(self)

        formulario = QWidget()
        layout_formulario = QFormLayout(formulario)
        for campo in campos:
            entrada = self._crear_entrada(campo, registro)
            self._entradas[campo.nombre] = entrada
            layout_formulario.addRow(campo.etiqueta, entrada)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(formulario)
        layout_general.addWidget(scroll)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout_general.addWidget(botones)

        self.resize(480, min(60 + 40 * len(campos), 640))

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco([*self._entradas.values(), boton_ok, boton_cancelar], parent=self)

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar": el
        diálogo todavía no está mostrado en ese momento."""
        super().showEvent(event)
        if self._entradas:
            next(iter(self._entradas.values())).setFocus()

    def _crear_entrada(self, campo: Campo, registro: sqlite3.Row | None) -> QWidget:
        valor = registro[campo.nombre] if registro is not None else None
        if campo.tipo == "booleano":
            entrada = QCheckBox()
            entrada.setChecked(bool(valor))
            return entrada
        if campo.tipo == "combo":
            entrada = QComboBox()
            entrada.setEditable(campo.combo_editable)
            for valor_opcion, etiqueta_opcion in campo.opciones(self.conn):
                entrada.addItem(etiqueta_opcion, valor_opcion)
            if valor is not None:
                indice = entrada.findData(valor)
                if indice >= 0:
                    entrada.setCurrentIndex(indice)
                elif campo.combo_editable:
                    entrada.setEditText(str(valor))
            return entrada
        if campo.tipo == "texto_largo":
            entrada = QPlainTextEdit()
            entrada.setPlainText("" if valor is None else str(valor))
            entrada.setFixedHeight(80)
            return entrada
        entrada = QLineEdit()
        if valor is not None:
            entrada.setText(str(valor))
        return entrada

    def _validar_y_aceptar(self) -> None:
        for campo in self.campos:
            if not campo.requerido:
                continue
            entrada = self._entradas[campo.nombre]
            vacio = (
                (campo.tipo == "texto" and not entrada.text().strip())
                or (campo.tipo == "texto_largo" and not entrada.toPlainText().strip())
            )
            if vacio:
                QMessageBox.warning(self, "Datos incompletos", f"El campo «{campo.etiqueta}» es obligatorio.")
                return
        self.accept()

    def valores(self) -> dict:
        resultado = {}
        for campo in self.campos:
            entrada = self._entradas[campo.nombre]
            if campo.tipo == "booleano":
                resultado[campo.nombre] = 1 if entrada.isChecked() else 0
            elif campo.tipo == "combo":
                if campo.combo_editable:
                    texto = entrada.currentText().strip()
                    resultado[campo.nombre] = texto or None
                else:
                    resultado[campo.nombre] = entrada.currentData()
            elif campo.tipo == "texto_largo":
                texto = entrada.toPlainText().strip()
                resultado[campo.nombre] = texto or None
            elif campo.tipo == "numero":
                texto = entrada.text().strip()
                resultado[campo.nombre] = float(texto) if texto else None
            else:
                texto = entrada.text().strip()
                if texto and campo.normalizar:
                    texto = campo.normalizar(texto)
                resultado[campo.nombre] = texto or None
        return resultado
