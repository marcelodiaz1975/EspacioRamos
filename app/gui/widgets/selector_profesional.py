"""Selector de profesional buscable (confirmado por la clienta en la
revisión de Estado de cuenta - Pagos: tiene que correr igual en todos los
selectores de profesional del sistema, actuales y futuros).

`habilitar_busqueda_profesional` toma un QComboBox YA poblado (con el id
de profesional como dato de cada ítem, texto en el formato canónico
"{código} - {tratamiento} {nombre} {apellido}" de
`app.gui.pantallas.reservas._texto_profesional`, en el orden que ya
viene armado por quien pobló el combo — ver `app.gui.widgets.orden_tabla.
clave_orden_profesional` para el criterio de orden por jerarquía de
categoría + código que usan los que arman esas opciones) y le agrega:

- Al enfocar el campo (un click, o llegar con Tab), selecciona todo el
  texto — permite borrarlo con Delete y escribir de cero sin tener que
  seleccionar a mano (pedido explícito de la clienta).
- Tipear filtra las opciones por CUALQUIER PARTE de ese texto canónico
  (código o nombre/apellido, en cualquier posición de la cadena) sin
  distinguir mayúsculas de minúsculas ni vocales acentuadas ("Diaz"
  encuentra "Díaz") — pedido explícito de la clienta: "R11" encuentra a
  "R11 - Lic. Leandro Cervellini" por el código, y "Leandro" también lo
  encuentra, por el nombre, estando en el medio de la cadena.
- El desplegable del completer (ya mostraba varias coincidencias en
  cascada mientras se tipea, comportamiento nativo de `QCompleter` en
  modo popup) resalta en negrita la porción de cada opción que matchea
  lo tipeado — en la posición real donde aparece (código al principio,
  nombre/apellido en el medio), no solo al principio. Bajar con las
  flechas y confirmar con Enter ya lo da gratis el `QCompleter` nativo,
  sin código extra.
- Al perder el foco confirma la única opción que matchea lo tipeado —
  si no matchea ninguna, o matchea más de una, vuelve al texto de la
  selección vigente en vez de dejar un texto suelto que no se
  corresponde con ningún profesional.

El filtrado nativo de `QCompleter` (`setFilterMode`/`setCaseSensitivity`)
solo resuelve mayúsculas/minúsculas, no tildes — por eso el completer usa
acá un `QSortFilterProxyModel` con `filterAcceptsRow` reimplementado a
mano en vez de esos dos métodos."""
from __future__ import annotations

import html
import unicodedata

from PySide6.QtCore import QEvent, QObject, QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication, QComboBox, QCompleter, QStyle, QStyledItemDelegate, QStyleOptionViewItem


def _sin_acentos(texto: str) -> str:
    """Mismo criterio que `app.importacion.importar_excel.
    _normalizar_encabezado` (duplicado acá, no importado: son dominios
    sin relación entre sí) — saca tildes/diéresis descomponiendo cada
    letra en base + diacrítico y quedándose solo con la base."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _normalizar(texto: str) -> str:
    return _sin_acentos(texto).casefold()


class _ProxyBusquedaSinAcentos(QSortFilterProxyModel):
    """Filtra filas por substring (cualquier parte del texto), sin
    distinguir mayúsculas/minúsculas ni acentos — ver el porqué en el
    docstring del módulo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.patron = ""

    def establecer_patron(self, texto: str) -> None:
        self.patron = _normalizar(texto)
        self.invalidateFilter()

    def filterAcceptsRow(self, fila: int, padre) -> bool:  # noqa: N802 (override de Qt)
        if not self.patron:
            return True
        return self.patron in _normalizar(self._texto_fila(fila, padre))

    def _texto_fila(self, fila: int, padre) -> str:
        origen = self.sourceModel()
        indice = origen.index(fila, 0, padre)
        return origen.data(indice, Qt.ItemDataRole.DisplayRole) or ""


def _rango_resaltado(texto: str, patron: str) -> tuple[int, int] | None:
    """Posición (inicio, fin) de `patron` dentro de `texto`, buscando
    sin distinguir mayúsculas ni acentos — `None` si no matchea. Como
    `_normalizar` preserva la longitud carácter a carácter para el
    texto típico de este sistema (saca tildes/casefold, sin colapsar ni
    expandir posiciones), el rango encontrado en el texto normalizado
    aplica tal cual sobre el texto ORIGINAL para resaltarlo."""
    if not patron:
        return None
    inicio = _normalizar(texto).find(patron)
    if inicio < 0:
        return None
    return inicio, inicio + len(patron)


class _DelegadoNegritaCoincidencia(QStyledItemDelegate):
    """Pinta en negrita la porción de cada opción del desplegable que
    matchea lo tipeado, en su posición real (`_rango_resaltado`) — el
    código al principio de la cadena, el nombre/apellido en el medio."""

    def __init__(self, proxy: _ProxyBusquedaSinAcentos, parent=None):
        super().__init__(parent)
        self._proxy = proxy

    def paint(self, painter, option, index) -> None:  # noqa: N802 (override de Qt)
        opcion = QStyleOptionViewItem(option)
        self.initStyleOption(opcion, index)
        texto = opcion.text
        opcion.text = ""
        estilo = opcion.widget.style() if opcion.widget else QApplication.style()
        estilo.drawControl(QStyle.ControlElement.CE_ItemViewItem, opcion, painter, opcion.widget)

        rango = _rango_resaltado(texto, self._proxy.patron)
        documento = QTextDocument()
        documento.setDefaultFont(opcion.font)
        if rango:
            inicio, fin = rango
            documento.setHtml(
                f"{html.escape(texto[:inicio])}<b>{html.escape(texto[inicio:fin])}</b>{html.escape(texto[fin:])}"
            )
        else:
            documento.setHtml(html.escape(texto))

        rect_texto = estilo.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opcion, opcion.widget)
        painter.save()
        painter.translate(rect_texto.topLeft())
        documento.setTextWidth(rect_texto.width())
        documento.drawContents(painter)
        painter.restore()


class _SeleccionarTodoAlEnfocar(QObject):
    """Al enfocar el campo (click o Tab), selecciona todo su contenido —
    con `QTimer.singleShot(0, ...)` porque un `selectAll()` inmediato
    durante el propio evento de foco queda pisado por el manejo nativo
    del click de Qt (que reposiciona el cursor en el punto clickeado
    justo después)."""

    def __init__(self, line_edit):
        super().__init__(line_edit)
        self._line_edit = line_edit
        line_edit.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (override de Qt)
        if event.type() == QEvent.Type.FocusIn:
            QTimer.singleShot(0, self._line_edit.selectAll)
        return False


def habilitar_busqueda_profesional(combo: QComboBox) -> None:
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    proxy = _ProxyBusquedaSinAcentos(combo)
    proxy.setSourceModel(combo.model())
    # Un `QCompleter()` nuevo, no el que ya trae `combo.completer()` por
    # default al volverlo editable: ESE viene con `popup()` en `None`
    # hasta que se muestra por primera vez de verdad (confirmado a mano,
    # no documentado por Qt) — uno construido aparte ya tiene su popup
    # armado desde el principio, así que se le puede poner el delegado
    # de negrita de una, sin esperar a que el usuario tipee algo.
    completador = QCompleter(combo)
    completador.setModel(proxy)
    completador.setCompletionColumn(0)
    completador.popup().setItemDelegate(_DelegadoNegritaCoincidencia(proxy, completador.popup()))
    combo.setCompleter(completador)
    combo.lineEdit().textEdited.connect(proxy.establecer_patron)
    combo.lineEdit().editingFinished.connect(lambda: _confirmar_texto(combo))
    _SeleccionarTodoAlEnfocar(combo.lineEdit())


def _confirmar_texto(combo: QComboBox) -> None:
    texto = combo.currentText().strip()
    indice = combo.findText(texto, Qt.MatchFlag.MatchFixedString)
    if indice < 0 and texto:
        # Coincidencia parcial (ej. tipeó solo "r1" o "lo veci" sin
        # completar con la sugerencia del desplegable): se acepta solo
        # si matchea una única opción — con más de una (ej. "r1" matchea
        # tanto "R1" como "R10") no hay forma de saber cuál quiso decir,
        # así que no se adivina.
        patron = _normalizar(texto)
        coincidencias = [i for i in range(combo.count()) if patron in _normalizar(combo.itemText(i))]
        if len(coincidencias) == 1:
            indice = coincidencias[0]
    if indice >= 0:
        if indice != combo.currentIndex():
            combo.setCurrentIndex(indice)
        return
    indice_actual = combo.currentIndex()
    combo.setEditText(combo.itemText(indice_actual) if indice_actual >= 0 else "")
