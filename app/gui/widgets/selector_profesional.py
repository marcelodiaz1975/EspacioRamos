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

- Al enfocar el campo (un click, llegar con Tab, O que la pantalla le
  dé el foco sola al mostrarse — `showEvent` llamando `.setFocus()`
  sobre el combo, patrón usado en casi todas las pantallas del sistema),
  selecciona todo el texto — permite borrarlo con Delete y escribir de
  cero sin tener que seleccionar a mano (pedido explícito de la
  clienta).
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

### El filtro en vivo: por qué NO alcanza con nuestro propio
`QSortFilterProxyModel`

`QCompleter` tiene su PROPIO motor de filtrado (`completionPrefix`/
`filterMode`/`caseSensitivity`), que decide qué filas de `proxy`
termina mostrando el desplegable — no "confía" en que `proxy` ya haya
filtrado, vuelve a filtrar él mismo encima. Un primer intento (reseteado
`completionPrefix` a vacío en cada `textEdited`, para neutralizar ese
filtro propio y dejar a `proxy` como única fuente de verdad) funcionaba
con un script que SIMULA el tipeo emitiendo la señal a mano
(`lineEdit().textEdited.emit(texto)`), pero NO con tipeo real
(`QTest.keyClicks`/el teclado de verdad): Qt tiene su propia conexión
interna, a nivel C++, entre el `QLineEdit` y su `QCompleter` que
TAMBIÉN fija `completionPrefix` al texto tipeado — y lo hace en un punto
del procesamiento de la tecla que nuestro slot de Python, conectado vía
`textEdited`, no puede garantizar que corra después (confirmado:
`completionPrefix()` terminaba siendo el texto tipeado tal cual, no
vacío, pese al reseteo). Cualquier solución que dependa del ORDEN en
que Qt dispara señales contra nuestro código Python es frágil por
definición — la solución robusta es no pelear contra el filtro propio
de `QCompleter`, sino hacer que haga exactamente lo que necesitamos.

Se logra con dos piezas, ambas en puntos de extensión públicos y
pensados para esto por Qt (nada de pelear con el orden de señales):

1. **Un rol de dato propio, con el texto YA normalizado** (sin acentos,
   en minúsculas) — `_ROL_TEXTO_NORMALIZADO`, que `_ProxyBusquedaSinAcentos.
   data()` calcula al vuelo a partir del texto real. `completador.
   setCompletionRole(_ROL_TEXTO_NORMALIZADO)` + `setFilterMode(
   MatchContains)` + `setCaseSensitivity(CaseInsensitive)` hacen que el
   motor nativo de `QCompleter` compare CONTRA ese texto normalizado, en
   cualquier posición — resuelve "busca sin importar mayúsculas" y
   "busca en cualquier parte de la cadena" de una sola vez, con el
   propio motor de Qt (sin ningún filtro nuestro corriendo en paralelo:
   `_ProxyBusquedaSinAcentos` ya NO filtra filas, solo expone el rol
   normalizado — queda como filtro trivial, deja pasar todo).
2. **Pero falta normalizar lo que el USUARIO tipeó**, no solo los datos:
   sin esto, escribir "díaz" (con tilde) no matchearía el rol
   normalizado "diaz" (sin tilde) — mismo problema, dado vuelta.
   `_CompleterSinAcentos` (subclase de `QCompleter`) resuelve esto
   overrideando `splitPath(path)` (método virtual público, el punto
   donde Qt arma la cadena que de verdad usa para matchear) para
   devolver `[_normalizar(path)]` en vez del texto tal cual — así lo que
   Qt compara contra el rol normalizado YA está normalizado de los dos
   lados, sin depender de ningún timing de señales.
3. Como el rol de matcheo ahora es el texto normalizado, Qt insertaría
   ESE texto (en minúsculas, sin acentos) en el campo si el usuario
   elige una opción del desplegable — `_CompleterSinAcentos` también
   overridea `pathFromIndex(index)` (el otro método virtual que define
   qué texto se inserta al activar una opción) para devolver el texto
   ORIGINAL (`Qt.ItemDataRole.DisplayRole`), no el normalizado."""
from __future__ import annotations

import html
import unicodedata

import shiboken6
from PySide6.QtCore import QEvent, QObject, QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication, QComboBox, QCompleter, QStyle, QStyledItemDelegate, QStyleOptionViewItem

_ROL_TEXTO_NORMALIZADO = Qt.ItemDataRole.UserRole + 1


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
    """Ya NO filtra filas — el filtrado en vivo lo hace el motor nativo
    de `QCompleter` (ver docstring del módulo), contra el texto
    normalizado que expone acá como rol propio (`_ROL_TEXTO_
    NORMALIZADO`). Sigue existiendo por dos motivos: ese rol tiene que
    calcularse en algún lado, y `patron` (actualizado por `establecer_
    patron`, llamado en cada `textEdited`) es lo que usa `_DelegadoNegritaCoincidencia`
    para saber qué resaltar en negrita."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.patron = ""

    def establecer_patron(self, texto: str) -> None:
        self.patron = _normalizar(texto)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802 (override de Qt)
        if role == _ROL_TEXTO_NORMALIZADO:
            return _normalizar(super().data(index, Qt.ItemDataRole.DisplayRole) or "")
        return super().data(index, role)


class _CompleterSinAcentos(QCompleter):
    """`QCompleter` normal, salvo por dos métodos virtuales overrideados
    para que el filtrado nativo (rol `_ROL_TEXTO_NORMALIZADO` +
    `MatchContains` + `CaseInsensitive`) también ignore los acentos que
    tipee el USUARIO, no solo los de los datos — ver el punto 2 del
    docstring del módulo."""

    def splitPath(self, path: str) -> list[str]:  # noqa: N802 (override de Qt)
        return [_normalizar(path)]

    def pathFromIndex(self, index) -> str:  # noqa: N802 (override de Qt)
        # Sin esto, Qt insertaría el texto normalizado (minúsculas, sin
        # acentos) al elegir una opción del desplegable, en vez del
        # texto real — ver el punto 3 del docstring del módulo.
        return index.data(Qt.ItemDataRole.DisplayRole) or ""


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
    """Al enfocar el campo, selecciona todo su contenido — con
    `QTimer.singleShot(0, ...)` porque un `selectAll()` inmediato
    durante el propio evento de foco queda pisado por el manejo nativo
    del click de Qt (que reposiciona el cursor en el punto clickeado
    justo después).

    Escucha `QEvent.Type.FocusIn` en DOS widgets, no solo en el
    `line_edit`: un click del mouse entrega ese evento al `line_edit`
    directo, pero un `showEvent` de pantalla llamando `combo.setFocus()`
    (el patrón que arranca el foco en casi todas las pantallas del
    sistema) se lo entrega al `QComboBox` de afuera, NUNCA a su
    `line_edit` interno (confirmado con un script: cero eventos
    `FocusIn` en el `line_edit` en ese caso, aunque `QApplication.
    focusWidget()` termine siendo el combo) — sin escuchar también ahí,
    el select-all solo funcionaba al llegar por click o por Tab, nunca
    al entrar recién a la pantalla."""

    def __init__(self, line_edit, combo: QComboBox | None = None):
        super().__init__(line_edit)
        self._line_edit = line_edit
        line_edit.installEventFilter(self)
        if combo is not None:
            combo.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (override de Qt)
        if event.type() == QEvent.Type.FocusIn:
            QTimer.singleShot(0, self._seleccionar_si_sigue_vivo)
        return False

    def _seleccionar_si_sigue_vivo(self) -> None:
        # Entre que se agenda el QTimer y que corre (0ms después, en la
        # vuelta siguiente del loop de eventos) la pantalla puede haberse
        # cerrado o reconstruido (confirmado: rompía con "libshiboken:
        # Internal C++ object (QLineEdit) already deleted" en varias
        # pantallas reales al escuchar FocusIn también en el combo, que
        # dispara este camino con más frecuencia que antes) — `shiboken6.
        # isValid` confirma que el objeto C++ todavía existe antes de
        # tocarlo.
        if shiboken6.isValid(self._line_edit):
            self._line_edit.selectAll()


def habilitar_busqueda_profesional(combo: QComboBox) -> None:
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    proxy = _ProxyBusquedaSinAcentos(combo)
    proxy.setSourceModel(combo.model())
    # Un completer nuevo, no el que ya trae `combo.completer()` por
    # default al volverlo editable: ESE viene con `popup()` en `None`
    # hasta que se muestra por primera vez de verdad (confirmado a mano,
    # no documentado por Qt) — uno construido aparte ya tiene su popup
    # armado desde el principio, así que se le puede poner el delegado
    # de negrita de una, sin esperar a que el usuario tipee algo.
    completador = _CompleterSinAcentos(combo)
    completador.setModel(proxy)
    completador.setCompletionRole(_ROL_TEXTO_NORMALIZADO)
    completador.setCompletionColumn(0)
    completador.setFilterMode(Qt.MatchFlag.MatchContains)
    completador.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completador.popup().setItemDelegate(_DelegadoNegritaCoincidencia(proxy, completador.popup()))
    combo.setCompleter(completador)
    combo.lineEdit().textEdited.connect(proxy.establecer_patron)
    combo.lineEdit().editingFinished.connect(lambda: _confirmar_texto(combo))
    _SeleccionarTodoAlEnfocar(combo.lineEdit(), combo)


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
