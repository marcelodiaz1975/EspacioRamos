"""Pantalla CRUD genérica: cubre las pantallas de catálogo simples (Edificios,
Unidades, Consultorios, Responsables, Tipos de licencia, Listas editables,
Condiciones y normas, Mensajes predefinidos) sin escribir una clase por tabla.
Se parametriza con una lista de Campo (columna, etiqueta, tipo de control) y
usa el Repositorio genérico (app/repositorio/base.py) para leer y escribir.

`anidado=True` (reordenamiento de formularios, Excel de la clienta): en vez
de pantalla de catálogo independiente (título Nivel 1 + su propio
`QTabWidget` de una sola pestaña "Listado"), el catálogo se arma como una
solapa desnuda lista para pasarse directo a `addTab(...)` de un formulario
compuesto (ej. "Archivos y listas", "Base datos del espacio") — mismo
criterio `objectName="panelSolapa"` en el widget de más afuera (`self`) que
`_PanelCampos`/`_PanelGestorArchivos`, con el mismo contenido de siempre
(Buscar + Nuevo/Editar/Eliminar + tabla) adentro de un `QScrollArea`
propio."""
from __future__ import annotations

import sqlite3
import unicodedata
import weakref
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.orden_tabla import OrdenTabla
from app.repositorio.registro import obtener_repositorio

_ID_REGISTRO = Qt.ItemDataRole.UserRole
_ANCHO_CAMPO = 240  # ancho compartido por el panel izquierdo (buscar + botones), mismo criterio que otras pantallas
_LOCALE_ES = QLocale(QLocale.Language.Spanish)
# "lun 07-09-2026" — mismo formato que los campos Desde/Hasta de Registro de
# ausencias (app/gui/pantallas/novedades.py), generalizado acá para
# tipo="fecha" en vez de duplicarlo pantalla por pantalla (pedido de la
# clienta al revisar Fechas especiales).
_FORMATO_FECHA_DIA = "ddd dd-MM-yyyy"


def _titulo_campo(texto: str) -> QLabel:
    """Jerarquía 3 (subtituloCampo): mismo criterio que el resto de las
    pantallas para los títulos que van arriba de un selector."""
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _sin_acentos(texto: str) -> str:
    """Mismo criterio que `selector_profesional._sin_acentos` (duplicado
    acá, no importado: son dominios sin relación) — saca tildes
    descomponiendo cada letra en base + diacrítico y quedándose con la
    base."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _normalizar_busqueda(texto: str) -> str:
    return _sin_acentos(texto).casefold()


def _fmt_fecha_dia(fecha_iso: str | None) -> str:
    """"lun 07-09-2026" a partir del AAAA-MM-DD guardado — ver
    `_FORMATO_FECHA_DIA`. Si el valor no es una fecha válida (no debería
    pasar, viene siempre de un QDateEdit) se muestra tal cual en vez de
    romper."""
    if not fecha_iso:
        return ""
    fecha_qt = QDate.fromString(fecha_iso, "yyyy-MM-dd")
    return _LOCALE_ES.toString(fecha_qt, _FORMATO_FECHA_DIA) if fecha_qt.isValid() else fecha_iso


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
    tipo: str = "texto"  # "texto" | "texto_largo" | "numero" | "booleano" | "combo" | "fecha"
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
    validador: Callable[[str], bool] | None = None
    """Solo para tipo="texto": valida el texto ya normalizado (si hay
    `normalizar`) antes de guardar — si devuelve False, se avisa con
    `formato_esperado` y el diálogo no se cierra. Ver
    `app.negocio.validaciones` para los validadores ya armados (fecha,
    período, email, DNI, CUIT); campos vacíos y no obligatorios no se
    validan (ver `_validar_y_aceptar`)."""
    formato_esperado: str | None = None
    """Descripción corta del formato esperado, para el cartel de aviso
    cuando `validador` rechaza el valor (ej. "AAAA-MM-DD")."""


def campos_libres(conn: sqlite3.Connection) -> list[Campo]:
    """Los tres campos libres (CampoLibre1/2/3) que se suman al final de
    todo catálogo revisado desde Consultorios en adelante (ver CLAUDE.md).
    La clienta los puede ocultar en todos los catálogos a la vez apagando
    "Visualizar campos libres" en Configuración general
    (Configuracion.VisualizarCamposLibres) — no borra los valores ya
    cargados, solo deja de mostrarlos y de pedirlos (tabla y diálogo Nuevo/
    Editar toman esta misma lista, así que alcanza con no incluirlos acá)."""
    fila = conn.execute("SELECT VisualizarCamposLibres FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    if fila is not None and not fila["VisualizarCamposLibres"]:
        return []
    return [
        Campo("CampoLibre1", "Campo libre 1"),
        Campo("CampoLibre2", "Campo libre 2"),
        Campo("CampoLibre3", "Campo libre 3"),
    ]


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
        compacto: bool = False,
        panel_extra_izquierda: QWidget | None = None,
        panel_extra_superior_izquierda: QWidget | None = None,
        etiqueta_buscar: str = "Buscar",
        nuevo_secundario: bool = False,
        anidado: bool = False,
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
        # compacto: layout viejo (título + fila de botones arriba de la
        # tabla, sin solapa/filtro) — para cuando una pantalla compuesta
        # (ej. Mensajes predefinidos) inserta este CRUD como un componente
        # más dentro de su propia composición (con su propio título/
        # filtro/paneles alrededor), en vez de usarlo como pantalla de
        # catálogo independiente. Las pantallas de catálogo comunes usan
        # el layout nuevo (default): solapa "Listado" (ficha, como el resto
        # del sistema), panel de Buscar + botones a la izquierda, tabla a
        # la derecha, todo dentro de un QScrollArea.
        self.compacto = compacto
        # panel_extra_izquierda: widget ya armado (con sus propios botones/
        # conexiones) que se agrega debajo de Nuevo/Editar/Eliminar en el
        # panel izquierdo, antes del stretch final — para catálogos que
        # necesitan una sección extra ahí sin dejar de ser una pantalla de
        # catálogo "de verdad" (ej. Profesionales: panel de documentación
        # del profesional seleccionado). Solo aplica al layout nuevo (se
        # ignora en modo compacto, que no tiene panel izquierdo).
        self.panel_extra_izquierda = panel_extra_izquierda
        # panel_extra_superior_izquierda: widget ya armado que se agrega
        # ENTRE Buscar y Nuevo/Editar/Eliminar — para un filtro propio de
        # visualización que tiene que quedar arriba de los botones en vez
        # de debajo (ej. Mensajes predefinidos: combo de Categoría).
        # Distinto de panel_extra_izquierda (que va debajo de los
        # botones); un catálogo puede usar los dos a la vez. Solo aplica
        # al layout nuevo (se ignora en modo compacto).
        self.panel_extra_superior_izquierda = panel_extra_superior_izquierda
        # etiqueta_buscar: texto del título arriba del campo Buscar — default
        # genérico "Buscar", pero un catálogo puede pedir uno más específico
        # (ej. Profesionales: "Buscar profesional") sin cambiar el criterio
        # de filtrado en sí (sigue siendo substring por cualquier columna).
        self.etiqueta_buscar = etiqueta_buscar
        # nuevo_secundario: pinta "Nuevo" en botonSecundario en vez de
        # botonPrimario — para catálogos donde otra acción del panel es la
        # más importante (ej. Mensajes predefinidos: "Copiar mensaje").
        self.nuevo_secundario = nuevo_secundario
        # anidado: ver docstring del módulo — sin título ni QTabWidget
        # propio, para embeberse como solapa de un formulario compuesto.
        self.anidado = anidado
        self.campo_buscar: QLineEdit | None = None
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
            (self.campo_buscar or self.boton_nuevo).setFocus()

    def _armar_ui(self, titulo: str) -> None:
        if self.anidado:
            self.setObjectName("panelSolapa")
            layout_externo = QVBoxLayout(self)
            layout_externo.setContentsMargins(0, 0, 0, 0)
            scroll = QScrollArea()
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidgetResizable(True)
            contenido = QWidget()
            contenido.setObjectName("panelSolapa")
            layout_solapa = QHBoxLayout(contenido)
            self._armar_panel_izquierda_y_tabla(layout_solapa)
            scroll.setWidget(contenido)
            layout_externo.addWidget(scroll)

            orden_foco = [self.campo_buscar, self.boton_nuevo, self.boton_editar, self.boton_eliminar]
            if self.instalar_foco:
                self._foco = instalar_enter_avanza_foco([w for w in orden_foco if w is not None], parent=self)
        else:
            layout = QVBoxLayout(self)

            etiqueta_titulo = QLabel(titulo)
            etiqueta_titulo.setObjectName("tituloPantalla")
            layout.addWidget(etiqueta_titulo)

            if self.compacto:
                self._armar_botones_y_tabla(layout)
                if self.instalar_foco:
                    self._foco = instalar_enter_avanza_foco(
                        [self.boton_nuevo, self.boton_editar, self.boton_eliminar], parent=self,
                    )
            else:
                solapas = QTabWidget()
                panel_solapa = QWidget()
                panel_solapa.setObjectName("panelSolapa")
                layout_solapa = QHBoxLayout(panel_solapa)
                self._armar_panel_izquierda_y_tabla(layout_solapa)

                scroll = QScrollArea()
                scroll.setFrameShape(QFrame.Shape.NoFrame)
                scroll.setWidgetResizable(True)
                scroll.setWidget(panel_solapa)
                solapas.addTab(scroll, "Listado")
                solapas.tabBar().setDrawBase(False)
                layout.addWidget(solapas, stretch=1)

                orden_foco = [self.campo_buscar, self.boton_nuevo, self.boton_editar, self.boton_eliminar]
                if self.instalar_foco:
                    self._foco = instalar_enter_avanza_foco([w for w in orden_foco if w is not None], parent=self)

        self._orden = OrdenTabla(self.tabla_widget, self.actualizar)

    def _armar_panel_izquierda_y_tabla(self, layout_solapa) -> None:
        panel_izquierda = QWidget()
        panel_izquierda.setObjectName("panelSolapa")
        form = QVBoxLayout(panel_izquierda)
        form.addWidget(_titulo_campo(self.etiqueta_buscar))
        self.campo_buscar = QLineEdit()
        self.campo_buscar.setFixedWidth(_ANCHO_CAMPO)
        self.campo_buscar.textChanged.connect(self._aplicar_filtro_busqueda)
        form.addWidget(self.campo_buscar)
        if self.panel_extra_superior_izquierda is not None:
            form.addWidget(self.panel_extra_superior_izquierda)
        self._armar_botones_y_tabla(form, ancho_botones=_ANCHO_CAMPO)
        if self.panel_extra_izquierda is not None:
            # con stretch para que ocupe el resto del alto disponible (ej.
            # Profesionales: la lista de documentación se estira hasta el
            # pie del panel, a la par de la barra de desplazamiento
            # horizontal de la tabla) — sin esto quedaba pegado arriba,
            # del alto justo de su contenido, con todo el resto en blanco
            # abajo.
            form.addWidget(self.panel_extra_izquierda, stretch=1)
        else:
            form.addStretch()
        layout_solapa.addWidget(panel_izquierda)

        layout_solapa.addWidget(self.tabla_widget, stretch=1)

    def _armar_botones_y_tabla(self, layout, ancho_botones: int | None = None) -> None:
        """Arma los botones Nuevo/Editar/Eliminar (si no es de solo
        lectura) y la tabla, y los agrega a `layout` — compartido entre el
        layout compacto (fila de botones horizontal) y el nuevo (columna
        vertical en el panel izquierdo, con ancho fijo)."""
        if not self.solo_lectura:
            self.boton_nuevo = QPushButton("Nuevo")
            self.boton_nuevo.setObjectName("botonSecundario" if self.nuevo_secundario else "botonPrimario")
            self.boton_nuevo.clicked.connect(self._nuevo)
            self.boton_editar = QPushButton("Editar")
            self.boton_editar.setObjectName("botonSecundario")
            self.boton_editar.clicked.connect(self._editar)
            self.boton_eliminar = QPushButton("Eliminar")
            self.boton_eliminar.setObjectName("botonSecundario")
            self.boton_eliminar.clicked.connect(self._eliminar)
            if ancho_botones is not None:
                self.boton_nuevo.setFixedWidth(ancho_botones)
                self.boton_editar.setFixedWidth(ancho_botones)
                self.boton_eliminar.setFixedWidth(ancho_botones)
                layout.addWidget(self.boton_nuevo)
                layout.addWidget(self.boton_editar)
                layout.addWidget(self.boton_eliminar)
            else:
                fila_botones = QHBoxLayout()
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
        if ancho_botones is None:
            layout.addWidget(self.tabla_widget, stretch=1)

    def _aplicar_filtro_busqueda(self, *_args) -> None:
        """Solo cambia qué filas se ven — mismo criterio que los filtros
        de Vista rápida/Aumentos (ver CLAUDE.md, "Filtros que solo afectan
        la visualización"). Busca por cualquier parte del texto de
        cualquier columna visible, sin distinguir mayúsculas ni acentos
        (mismo criterio que el buscador de profesional)."""
        if self.campo_buscar is None:
            return
        buscado = _normalizar_busqueda(self.campo_buscar.text().strip())
        for fila in range(self.tabla_widget.rowCount()):
            if not buscado:
                self.tabla_widget.setRowHidden(fila, False)
                continue
            texto_fila = " ".join(
                self.tabla_widget.item(fila, col).text()
                for col in range(self.tabla_widget.columnCount())
                if self.tabla_widget.item(fila, col) is not None
            )
            self.tabla_widget.setRowHidden(fila, buscado not in _normalizar_busqueda(texto_fila))

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
        self._aplicar_filtro_busqueda()

    def _clave_orden(self, columna: int):
        campo = self.campos[columna]

        def clave(registro: sqlite3.Row):
            valor = registro[campo.nombre]
            if campo.tipo == "numero":
                return valor if valor is not None else float("-inf")
            if campo.tipo == "booleano":
                return bool(valor)
            if campo.tipo == "fecha":
                # Ordena por el AAAA-MM-DD guardado, no por el texto mostrado
                # ("lun 07-09-2026"): ese orden lexicográfico no coincide con
                # el cronológico (empieza por el día de la semana).
                return valor or ""
            return self._texto_celda(registro, campo)

        return clave

    def _texto_celda(self, registro: sqlite3.Row, campo: Campo) -> str:
        valor = registro[campo.nombre]
        if campo.tipo == "booleano":
            return "Sí" if valor else "No"
        if campo.tipo == "fecha":
            return _fmt_fecha_dia(valor)
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
            try:
                id_nuevo = self.repositorio.crear(**valores)
            except sqlite3.IntegrityError as error:
                QMessageBox.warning(self, "Nuevo registro", f"No se pudo guardar: {error}")
                return
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
            try:
                self.repositorio.actualizar(id_valor, **valores)
            except sqlite3.IntegrityError as error:
                QMessageBox.warning(self, "Editar registro", f"No se pudo guardar: {error}")
                return
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
        if campo.tipo == "fecha":
            entrada = QDateEdit()
            entrada.setDisplayFormat(_FORMATO_FECHA_DIA)
            entrada.setLocale(_LOCALE_ES)
            entrada.setCalendarPopup(True)
            fecha_qt = QDate.fromString(valor, "yyyy-MM-dd") if valor else QDate()
            entrada.setDate(fecha_qt if fecha_qt.isValid() else QDate.currentDate())
            return entrada
        entrada = QLineEdit()
        if valor is not None:
            entrada.setText(str(valor))
        return entrada

    def _validar_y_aceptar(self) -> None:
        for campo in self.campos:
            entrada = self._entradas[campo.nombre]
            if campo.tipo == "numero":
                texto = entrada.text().strip()
                if texto:
                    try:
                        float(texto)
                    except ValueError:
                        QMessageBox.warning(self, "Dato inválido", f"El campo «{campo.etiqueta}» tiene que ser un número.")
                        entrada.setFocus()
                        return
            if campo.tipo == "texto" and campo.validador is not None:
                texto = entrada.text().strip()
                if texto:
                    valor = campo.normalizar(texto) if campo.normalizar else texto
                    if not campo.validador(valor):
                        QMessageBox.warning(
                            self, "Dato inválido",
                            f"El campo «{campo.etiqueta}» no tiene el formato esperado ({campo.formato_esperado}).",
                        )
                        entrada.setFocus()
                        return
            if not campo.requerido:
                continue
            vacio = (
                (campo.tipo in ("texto", "numero") and not entrada.text().strip())
                or (campo.tipo == "texto_largo" and not entrada.toPlainText().strip())
            )
            if vacio:
                QMessageBox.warning(self, "Datos incompletos", f"El campo «{campo.etiqueta}» es obligatorio.")
                entrada.setFocus()
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
            elif campo.tipo == "fecha":
                resultado[campo.nombre] = entrada.date().toString("yyyy-MM-dd")
            else:
                texto = entrada.text().strip()
                if texto and campo.normalizar:
                    texto = campo.normalizar(texto)
                resultado[campo.nombre] = texto or None
        return resultado
