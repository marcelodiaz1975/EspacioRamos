"""Planilla flotante (F2, pedido explícito de la clienta): "en vez de la
calculadora, una especie de planilla de Excel flotante, para hacer
anotaciones, cálculos, etc... para anotaciones simples y cálculos simples,
temporales, como para tener a mano cada tanto" — reemplaza por completo a
la vieja `Calculadora`. Pedido sobre el formato de celda: "funciones
básicas de operaciones aritméticas... no fórmulas complejas... poner
negrita[,] el color de la fuente[,] algún color de relleno en las celdas...
formato de números de dos decimales y separador de miles."

Una ventana de verdad (no un diálogo modal, igual que la vieja
calculadora), con una grilla tipo Excel (columnas A, B, C... filas 1, 2,
3...) y una barra de fórmula arriba (como en Excel: "{dirección}" +
cuadro de texto) — las celdas de la grilla en sí NO tienen `ItemIsEditable`
(Qt no abre un editor nativo sobre ellas), toda edición de VERDAD pasa
por la barra de fórmula, así no hace falta un delegate separado para
distinguir "lo que se tipeó" (la fórmula cruda, ej. "=A1+B2") de "lo que
se ve" (el resultado calculado). Pedido explícito de la clienta: "que al
navegar con el cursor se pueda empezar a escribir directamente en la
celda" — tipear estando parado en una celda (sin haber clickeado antes
la barra de fórmula) arranca la edición igual, pisando el contenido
anterior: el `eventFilter` de la tabla intercepta la primera tecla
imprimible y la redirige a la barra de fórmula (`_empezar_a_escribir`),
que a partir de ahí sigue recibiendo el resto nativamente. Ver
`app.negocio.planilla_flotante` para el motor de fórmulas ("+" además de
"=" como prefijo de fórmula, pedido explícito) y la persistencia
(permanente a pedido explícito, "no quiero que se blanquee al cerrar el
sistema").

El formato por celda (negrita/color de texto/color de relleno) se pinta
con un `QStyledItemDelegate` propio (`_DelegadoCelda`) en vez de
`QTableWidgetItem.setFont`/`setForeground`/`setBackground` — primer bug
real de PySide6/shiboken encontrado investigando esta pantalla: guardar
un `QFont`/`QBrush`/`QColor` como rol de MUCHAS celdas (confirmado a
partir de ~300-400 con un script offscreen) y después tocar su texto
abortaba el proceso al cerrar la ventana ("Fatal Python error: none_
dealloc... bug likely caused by a refcount error in a C extension"). El
delegate evita ESE bug: nunca persiste un QFont/QBrush/QColor en el
modelo/ítem, solo calcula el estilo al pintar leyendo `self._celdas` (un
dict Python común).

SEGUNDO bug, más de fondo, encontrado al seguir investigando: el mismo
abort aparece igual con o sin delegate, con o sin estilo, con
`QTableWidget`/`QTableWidgetItem.setText` o incluso con un
`QAbstractTableModel` propio (sin ningún `QTableWidgetItem` de por
medio) — así que NO es un problema de esta pantalla ni de cómo está
armada, es un bug de fondo de este build puntual de PySide6/shiboken
(6.12.0, confirmado con `pip show PySide6`) que aborta el proceso en el
garbage collection FINAL de Python (al cerrar TODO el programa, no
durante el uso — confirmado: el loop de prueba siempre termina e
imprime su mensaje de "listo" antes de que el abort aparezca en el
shutdown) después de que se acumulan, en total, algo así como 700-1000
mutaciones de texto sobre ítems de tabla en el mismo proceso — número
chico y FIJO, no escala con la cantidad de celdas ni con crear/destruir
ventanas: hasta 480 mutaciones (toda la grilla una vez) no rompe nunca;
a partir de ahí cualquier mutación de más, aunque sea sobre una sola
celda repetida, eventualmente sí. El resto del sistema no lo pisa en
el uso diario porque cada pantalla rearma sus `QTableWidgetItem` de
cero en cada refresco en vez de mutar texto repetidas veces sobre el
mismo ítem — y son relativamente pocos refrescos por sesión.

TERCER hallazgo (ronda "columnas hasta la Z, filas hasta la 100", 2600
celdas): el mismo abort también aparece por la sola CANTIDAD de
`QTableWidgetItem` CREADOS de entrada, sin ninguna mutación de texto
después — confirmado con un script offscreen que crea ítems vacíos y
los asigna con `setItem` sin tocar su texto nunca más: 494 ítems
creados no rompe nunca, 1000 sí, mismo rango chico que el umbral de
mutaciones ya documentado arriba. La vieja `_refrescar_grilla` creaba
las 2600 celdas de entrada (una por una, con `QTableWidgetItem()` +
`setItem`) para poder apagarles `ItemIsEditable` — eso solo ya cruzaba
el umbral antes de que el usuario tipeara nada. Se resuelve apagando la
edición nativa a nivel TABLA (`self.tabla.setEditTriggers(QAbstractItem
View.EditTrigger.NoEditTriggers)`, en el constructor) en vez de por
ítem — confirmado offscreen que esto alcanza igual (ningún editor se
abre con doble click ni al tipear, aunque la celda no tenga ítem
propio) — así que un `QTableWidgetItem` ya no hace falta para TODA
celda, solo para la que realmente tiene algo que mostrar: `_recalcular_
textos` pasa a crear el ítem recién la primera vez que esa celda
necesita texto no vacío (`self.tabla.item(fila, columna) is None` y
`texto != ""`), nunca antes. En el uso real ("anotaciones simples...
cada tanto") la enorme mayoría de las 2600 celdas nunca llega a
necesitar un ítem, así que el conteo real de la sesión queda muy por
debajo de los dos umbrales (creación Y mutación) encontrados — mitiga
la ventana más común (uso real, con pocas celdas tocadas), pero NO
elimina el cuarto hallazgo de abajo.

CUARTO hallazgo (más de fondo todavía, sin mitigación posible desde
código de la app): aun con el fix de arriba — CERO `QTableWidgetItem`
creados, instancia recién construida, sin un solo tecleo — el mismo
abort sigue apareciendo al cierre con la grilla en su tamaño pedido
(100×26). Achicado con un script offscreen que solo construye
`QTableWidget(filas, 26)` (sin ningún ítem, sin delegate, sin esta
pantalla) y lo muestra/oculta: con 26 columnas fijas, 65 filas (1690
celdas) nunca rompe, 70 filas (1820 celdas) sí — un umbral FIJO
parecido al de arriba, pero que depende de la estructura interna de
filas×columnas del propio `QTableWidget`/`QHeaderView` (conteo de
secciones de encabezado, índices de modelo, etc.), no de los ítems que
contiene. Con una sola columna, en cambio, 1100 filas (1100 celdas) no
rompe — así que no es un simple total filas×columnas tampoco: la
cuenta real parece acumular contra el mismo "presupuesto" del proceso
que el resto de los hallazgos de este bug, pero por un lado interno de
Qt que el código de esta pantalla no controla ni puede evitar sin
achicar la grilla por debajo de ese umbral (lo que iría en contra del
pedido explícito "columnas hasta la Z, filas hasta la 100"). Mismo
criterio que el resto de los "Fallos conocidos del sandbox/contenedor"
documentados en CLAUDE.md: el abort SOLO aparece en el shutdown final
del proceso (cerrar TODO el sistema, nunca durante el uso — confirmado
de nuevo con este hallazgo: el script de prueba siempre construye,
muestra y oculta la ventana con éxito antes de abortar al cerrar) y
ningún dato se pierde nunca (ya quedó en SQLite en cada edición) — se
deja documentado sin mitigación de código adicional, pendiente de
confirmar si el build de PySide6 del entorno real de la clienta
(Windows) también lo tiene.

Por eso `_recalcular_textos()` (más abajo) solo llama a `item.setText(...)`
cuando el texto realmente CAMBIÓ — en el uso real ("anotaciones
simples... cada tanto", no una grilla que se recalcula entera en cada
tecla) la inmensa mayoría de las celdas quedan vacías/sin ítem siempre,
así que esto evita la case "re-settear toda la grilla en cada edición"
y deja el conteo real muy por debajo del umbral de la mayoría de las
sesiones. Además, por las dudas, esta ventana NO se destruye nunca al cerrarla
(al revés de la vieja calculadora): `VentanaPrincipal` crea una ÚNICA
instancia la primera vez que se aprieta F2 y la reusa el resto de la
sesión, mostrándola/ocultándola (`show()`/`hide()`) — nunca una
`PlanillaFlotante` nueva. `closeEvent` ignora el cierre real y solo la
esconde, para que la cruz de la ventana se comporte igual que F2
(cerrarla de verdad recién pasa al cerrar TODO el sistema)."""
from __future__ import annotations

import sqlite3
from string import ascii_uppercase

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.negocio.planilla_flotante import (
    ErrorFormula, formatear_miles, guardar_celda, leer_celdas, texto_resultado_celda, valor_celda, vaciar_todo,
)

# Pedido explícito de la clienta: "columnas hasta la Z, filas hasta la
# 100" — 26 letras exactas de `ascii_uppercase`, sin necesidad de
# columnas de dos letras (AA, AB...).
_COLUMNAS = 26
_FILAS = 100

_DELTAS_FLECHA = {
    Qt.Key.Key_Up: (-1, 0), Qt.Key.Key_Down: (1, 0), Qt.Key.Key_Left: (0, -1), Qt.Key.Key_Right: (0, 1),
}


def _letra_columna(indice: int) -> str:
    return ascii_uppercase[indice]


def _id_celda(fila: int, columna: int) -> str:
    return f"{_letra_columna(columna)}{fila + 1}"


_ESTILO_VACIO = {
    "contenido": "", "negrita": False, "color_texto": None, "color_fondo": None, "formato_numero": False,
    "alineacion": None,
}

_ALINEACION_QT = {
    "izquierda": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    "centro": Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
    "derecha": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
}


class _DelegadoCelda(QStyledItemDelegate):
    """Pinta negrita/color de texto/color de relleno/alineación leyendo
    `obtener_estilo(fila, columna)` en cada repintado — ver el
    docstring del módulo para por qué no se guarda nada de esto en el
    ítem/modelo. `estilo["alineacion"]` ya viene resuelta (override
    explícito o el default automático — ver `PlanillaFlotante._
    alineacion_efectiva`), nunca `None` acá."""

    def __init__(self, obtener_estilo, parent=None):
        super().__init__(parent)
        self._obtener_estilo = obtener_estilo

    def initStyleOption(self, option, index) -> None:  # noqa: N802 (override de Qt)
        super().initStyleOption(option, index)
        estilo = self._obtener_estilo(index.row(), index.column())
        if estilo["negrita"]:
            option.font.setBold(True)
        if estilo["color_texto"]:
            color = QColor(estilo["color_texto"])
            option.palette.setColor(QPalette.ColorRole.Text, color)
            option.palette.setColor(QPalette.ColorRole.HighlightedText, color)
        if estilo["color_fondo"]:
            option.backgroundBrush = QColor(estilo["color_fondo"])
        option.displayAlignment = _ALINEACION_QT[estilo["alineacion"]]


class PlanillaFlotante(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Planilla")
        self.setWindowFlag(Qt.WindowType.Window)
        self.resize(760, 480)

        self._celdas: dict[str, dict] = leer_celdas(conn)
        self._fila_actual: int | None = None
        self._columna_actual: int | None = None
        self._texto_pendiente: str | None = None
        # Modo "señalar" (como Excel): navegar con el cursor mientras se
        # tipea una fórmula va concatenando referencias de celda en vez
        # de navegar — ver `_mover_puntero_formula`.
        self._punto_fila: int | None = None
        self._punto_columna: int | None = None
        self._puntero_activo = False
        self._texto_antes_del_puntero: str | None = None

        layout = QVBoxLayout(self)

        fila_formula = QHBoxLayout()
        self.etiqueta_celda = QLabel("")
        self.etiqueta_celda.setFixedWidth(40)
        self.barra_formula = QLineEdit()
        self.barra_formula.textEdited.connect(self._marcar_pendiente)
        self.barra_formula.textEdited.connect(self._al_tipear_en_formula)
        self.barra_formula.returnPressed.connect(self._confirmar_y_bajar)
        fila_formula.addWidget(self.etiqueta_celda)
        fila_formula.addWidget(self.barra_formula)
        layout.addLayout(fila_formula)

        fila_estilos = QHBoxLayout()
        self.boton_negrita = QPushButton("Negrita")
        self.boton_negrita.setCheckable(True)
        self.boton_negrita.clicked.connect(self._alternar_negrita)
        self.boton_color_texto = QPushButton("Color texto")
        self.boton_color_texto.clicked.connect(self._elegir_color_texto)
        self.boton_color_fondo = QPushButton("Color fondo")
        self.boton_color_fondo.clicked.connect(self._elegir_color_fondo)
        self.boton_formato_numero = QPushButton("Formato núm.")
        self.boton_formato_numero.setCheckable(True)
        self.boton_formato_numero.clicked.connect(self._alternar_formato_numero)
        self.boton_alinear_izquierda = QPushButton("Izquierda")
        self.boton_alinear_izquierda.clicked.connect(lambda: self._alinear("izquierda"))
        self.boton_alinear_centro = QPushButton("Centro")
        self.boton_alinear_centro.clicked.connect(lambda: self._alinear("centro"))
        self.boton_alinear_derecha = QPushButton("Derecha")
        self.boton_alinear_derecha.clicked.connect(lambda: self._alinear("derecha"))
        self.boton_combinar = QPushButton("Combinar")
        self.boton_combinar.clicked.connect(self._combinar_celdas)
        self.boton_vaciar_todo = QPushButton("Vaciar todo")
        self.boton_vaciar_todo.clicked.connect(self._vaciar_todo)
        botones = (
            self.boton_negrita, self.boton_color_texto, self.boton_color_fondo,
            self.boton_formato_numero, self.boton_alinear_izquierda, self.boton_alinear_centro,
            self.boton_alinear_derecha, self.boton_combinar, self.boton_vaciar_todo,
        )
        # Pedido explícito: "que los botones queden en una sola fila,
        # reducí el ancho de los mismos" — mismo criterio que el resto
        # del sistema (ancho fijo único, calculado para que entre el
        # texto más largo) en vez del ancho automático de cada uno.
        ancho_boton = max(QFontMetrics(self.font()).horizontalAdvance(b.text()) for b in botones) + 16
        for boton in botones:
            boton.setFixedWidth(ancho_boton)
            fila_estilos.addWidget(boton)
        layout.addLayout(fila_estilos)

        self.tabla = QTableWidget(_FILAS, _COLUMNAS)
        self.tabla.setHorizontalHeaderLabels([_letra_columna(c) for c in range(_COLUMNAS)])
        # Apaga la edición nativa a nivel tabla (en vez de por ítem, con
        # ItemIsEditable) — ver el docstring del módulo, "TERCER
        # hallazgo": así no hace falta crear un QTableWidgetItem para
        # las 2600 celdas de entrada solo para poder apagarles esa
        # bandera.
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setItemDelegate(_DelegadoCelda(self._estilo_en, self.tabla))
        self.tabla.currentCellChanged.connect(self._al_cambiar_celda)
        self.tabla.installEventFilter(self)
        self.barra_formula.installEventFilter(self)
        layout.addWidget(self.tabla)

        self._refrescar_grilla()
        self.tabla.setCurrentCell(0, 0)

    def closeEvent(self, event) -> None:  # noqa: N802 (override de Qt)
        """La cruz de la ventana esconde, no destruye — ver el docstring
        del módulo (bug de PySide6 al crear/destruir muchos `QTableWidget`
        repetidas veces). `VentanaPrincipal` reusa esta misma instancia
        durante toda la sesión; solo se destruye de verdad al cerrar TODO
        el sistema (ahí sí corre el `closeEvent` real de Qt, heredado)."""
        event.ignore()
        self.hide()

    # -------------------------------------------------------------------- eventos de teclado

    def eventFilter(self, objeto, evento):  # noqa: N802 (override de Qt)
        """Delete/Backspace en la grilla (no en la barra de fórmula)
        borra el CONTENIDO de la selección, sin tocar el formato — mismo
        criterio que cualquier planilla de cálculo. Cualquier otra tecla
        con texto imprimible arranca una edición nueva directamente en
        la celda (ver `_empezar_a_escribir`) — pedido explícito: "que al
        navegar con el cursor se pueda empezar a escribir directamente
        en la celda", igual que Excel. En la barra de fórmula, una
        flecha mientras se tipea una fórmula arranca/sigue el "modo
        señalar" (ver `_mover_puntero_formula`) en vez de mover el
        cursor de texto."""
        if objeto is self.tabla and evento.type() == QEvent.Type.KeyPress:
            if evento.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self._borrar_contenido_seleccion()
                return True
            texto = evento.text()
            if texto and texto.isprintable():
                self._empezar_a_escribir(texto)
                return True
        if objeto is self.barra_formula and evento.type() == QEvent.Type.KeyPress:
            delta = _DELTAS_FLECHA.get(evento.key())
            # Mismos prefijos de fórmula que `app.negocio.planilla_
            # flotante._es_formula` ("=" y "+", no "-") — se repite
            # acá en vez de importar ese helper privado de otro módulo.
            if delta is not None and self.barra_formula.text().startswith(("=", "+")):
                self._mover_puntero_formula(*delta)
                return True
        return super().eventFilter(objeto, evento)

    def _empezar_a_escribir(self, texto: str) -> None:
        """Tipear estando parado en una celda (sin haber tocado antes la
        barra de fórmula) arranca una edición nueva que PISA el
        contenido anterior de la celda — mismo comportamiento que
        Excel: la primera tecla se captura acá y se manda a la barra de
        fórmula, que a partir de ahí ya tiene el foco y sigue recibiendo
        el resto de lo que se tipee de forma nativa (`textEdited` ya
        está conectado a `_marcar_pendiente`, sin nada más que hacer acá
        tecla por tecla)."""
        self.barra_formula.setText(texto)
        self._marcar_pendiente(texto)
        self.barra_formula.setFocus()
        self.barra_formula.end(False)

    def _mover_puntero_formula(self, delta_fila: int, delta_columna: int) -> None:
        """"Modo señalar" de Excel: con el cursor dentro de una fórmula
        en construcción, cada flecha concatena una referencia de celda
        en vez de mover el cursor de texto o navegar la grilla. Pedido
        explícito con su propio ejemplo: "empiezo a escribir en '+45+'
        en C1, presiono cursor abajo, ahí quedaría '+45+C2'[;] a medida
        que sigo poniendo signos me sigue concatenando celdas".

        `_puntero_activo` distingue dos casos sin tocar nada más:
        - Si la última acción fue OTRA flecha (sin tipear nada en el
          medio), esta flecha MUEVE la referencia ya insertada (la
          reemplaza) — el punto de partida es la última celda
          señalada, no la celda que se edita.
        - Si la última acción fue tipear algo real (`_al_tipear_en_
          formula` ya puso `_puntero_activo` en `False`), esta flecha
          agrega una referencia NUEVA a partir de la última celda
          señalada (o de la celda que se edita, si todavía no se señaló
          ninguna en esta edición)."""
        if self._punto_fila is None:
            base_fila, base_columna = self._fila_actual, self._columna_actual
        else:
            base_fila, base_columna = self._punto_fila, self._punto_columna
        if not self._puntero_activo:
            self._texto_antes_del_puntero = self.barra_formula.text()
        nueva_fila = max(0, min(_FILAS - 1, base_fila + delta_fila))
        nueva_columna = max(0, min(_COLUMNAS - 1, base_columna + delta_columna))
        self._punto_fila, self._punto_columna = nueva_fila, nueva_columna
        self._puntero_activo = True
        nuevo_texto = self._texto_antes_del_puntero + _id_celda(nueva_fila, nueva_columna)
        self.barra_formula.setText(nuevo_texto)
        self._marcar_pendiente(nuevo_texto)

    def _al_tipear_en_formula(self, _texto: str) -> None:
        """`textEdited` solo se dispara con tecleo real del usuario (no
        con los `setText` de `_mover_puntero_formula`) — cualquier
        tecleo real "fija" la referencia señalada hasta ahora: la
        próxima flecha agrega una referencia nueva en vez de mover la
        última (ver `_mover_puntero_formula`). La celda señalada en sí
        (`_punto_fila`/`_punto_columna`) NO se resetea acá a propósito
        — queda como punto de partida de la próxima referencia, para
        poder "caminar" la misma columna/fila de a una celda por vez."""
        self._puntero_activo = False

    # --------------------------------------------------------------------------- estado/dirección

    def _id_actual(self) -> str | None:
        if self._fila_actual is None or self._columna_actual is None:
            return None
        return _id_celda(self._fila_actual, self._columna_actual)

    def _estilo(self, id_celda: str) -> dict:
        return self._celdas.get(id_celda, _ESTILO_VACIO)

    def _estilo_en(self, fila: int, columna: int) -> dict:
        """Usada por `_DelegadoCelda` — misma info que `_estilo`, por
        fila/columna en vez de dirección (lo que trae `index`), con la
        alineación ya resuelta a un valor concreto (nunca `None`)."""
        id_celda = _id_celda(fila, columna)
        estilo = dict(self._estilo(id_celda))
        estilo["alineacion"] = self._alineacion_efectiva(id_celda, estilo["alineacion"])
        return estilo

    def _alineacion_efectiva(self, id_celda: str, alineacion_guardada: str | None) -> str:
        """Pedido explícito de la clienta: "que por defecto lo que es
        texto se justifique a la izquierda y los valores a la derecha"
        — sin un override explícito (botones de alineación), se decide
        mirando si la celda resuelve a un número (fórmula o no) o no."""
        if alineacion_guardada is not None:
            return alineacion_guardada
        contenidos = {id_: datos["contenido"] for id_, datos in self._celdas.items()}
        try:
            es_numerica = valor_celda(contenidos, id_celda) is not None
        except ErrorFormula:
            es_numerica = False
        return "derecha" if es_numerica else "izquierda"

    def _celdas_seleccionadas(self) -> list[str]:
        indices = {(idx.row(), idx.column()) for idx in self.tabla.selectedIndexes()}
        if not indices and self._fila_actual is not None:
            indices = {(self._fila_actual, self._columna_actual)}
        return [_id_celda(f, c) for f, c in indices]

    # ------------------------------------------------------------------------------ barra de fórmula

    def _marcar_pendiente(self, texto: str) -> None:
        self._texto_pendiente = texto

    def _confirmar_pendiente(self, fila: int, columna: int) -> None:
        if self._texto_pendiente is None:
            return
        self._guardar_contenido(fila, columna, self._texto_pendiente)
        self._texto_pendiente = None

    def _confirmar_y_bajar(self) -> None:
        if self._fila_actual is None:
            return
        self._confirmar_pendiente(self._fila_actual, self._columna_actual)
        siguiente = min(self._fila_actual + 1, _FILAS - 1)
        self.tabla.setCurrentCell(siguiente, self._columna_actual)
        self.tabla.setFocus()

    def _al_cambiar_celda(self, fila: int, columna: int, fila_anterior: int, columna_anterior: int) -> None:
        if fila_anterior >= 0 and columna_anterior >= 0:
            self._confirmar_pendiente(fila_anterior, columna_anterior)
        self._fila_actual, self._columna_actual = fila, columna
        self._cargar_barra_formula()

    def _cargar_barra_formula(self) -> None:
        id_celda = self._id_actual()
        self._texto_pendiente = None
        # Cambiar de celda termina cualquier "modo señalar" en curso —
        # la próxima vez que se tipee una fórmula arranca de cero.
        self._punto_fila = None
        self._punto_columna = None
        self._puntero_activo = False
        self._texto_antes_del_puntero = None
        if id_celda is None:
            self.etiqueta_celda.setText("")
            self.barra_formula.setText("")
            return
        estilo = self._estilo(id_celda)
        self.etiqueta_celda.setText(id_celda)
        self.barra_formula.setText(estilo["contenido"])
        # Pedido explícito: "que el texto que esté cargado al pinchar se
        # seleccione todo por si quiero volver a escribir arriba y
        # borrar el contenido con ese acto" — mismo criterio que
        # `instalar_seleccionar_todo_al_enfocar` (app/gui/widgets/
        # foco.py) pero sin su `QTimer.singleShot`: ahí hace falta
        # porque el click que dispara el foco es sobre el MISMO widget
        # que hay que seleccionar (Qt reposiciona el cursor después);
        # acá el click que cambia de celda es sobre la TABLA, un widget
        # distinto, así que no hay nada que pise esta selección después.
        self.barra_formula.selectAll()
        self.boton_negrita.setChecked(estilo["negrita"])
        self.boton_formato_numero.setChecked(estilo["formato_numero"])

    # --------------------------------------------------------------------------------- persistencia

    def _guardar_contenido(self, fila: int, columna: int, texto: str) -> None:
        id_celda = _id_celda(fila, columna)
        estilo = dict(self._estilo(id_celda))
        estilo["contenido"] = texto
        self._aplicar_y_persistir(id_celda, estilo)

    def _aplicar_y_persistir(self, id_celda: str, estilo: dict) -> None:
        self._guardar_sin_recalcular(id_celda, estilo)
        self._recalcular_textos()

    def _guardar_sin_recalcular(self, id_celda: str, estilo: dict) -> None:
        """Mismo guardado que `_aplicar_y_persistir`, sin el `_recalcular_
        textos()` final — lo usan los cambios de formato sobre VARIAS
        celdas a la vez (`_aplicar_a_seleccion`) para recalcular una
        sola vez al terminar, no una vez por celda de la selección."""
        vacia = (
            not estilo["contenido"] and not estilo["negrita"] and estilo["color_texto"] is None
            and estilo["color_fondo"] is None and not estilo["formato_numero"]
            and estilo["alineacion"] is None
        )
        if vacia:
            self._celdas.pop(id_celda, None)
        else:
            self._celdas[id_celda] = estilo
        guardar_celda(
            self.conn, id_celda, contenido=estilo["contenido"], negrita=estilo["negrita"],
            color_texto=estilo["color_texto"], color_fondo=estilo["color_fondo"],
            formato_numero=estilo["formato_numero"], alineacion=estilo["alineacion"],
        )

    def _aplicar_a_seleccion(self, mutador) -> None:
        for id_celda in self._celdas_seleccionadas():
            estilo = dict(self._estilo(id_celda))
            mutador(estilo)
            self._guardar_sin_recalcular(id_celda, estilo)
        self._recalcular_textos()

    # ------------------------------------------------------------------------------------- grilla

    def _refrescar_grilla(self) -> None:
        """NO crea ningún `QTableWidgetItem` de entrada (ver "TERCER
        hallazgo" en el docstring del módulo) — `_recalcular_textos` ya
        crea cada ítem de forma perezosa, recién cuando una celda
        necesita mostrar texto no vacío."""
        self._recalcular_textos()

    def _recalcular_textos(self) -> None:
        """Solo crea un `QTableWidgetItem` para una celda la primera vez
        que necesita mostrar texto no vacío, y solo llama a
        `item.setText(...)` cuando el texto cambió de verdad — ver el
        docstring del módulo: esto mantiene el conteo total de
        creaciones Y mutaciones de ítems de toda la sesión muy por
        debajo de los dos umbrales que disparan el bug de PySide6/
        shiboken (en el uso real, la enorme mayoría de las 2600 celdas
        están vacías siempre y nunca llegan a necesitar un ítem)."""
        contenidos = {id_: datos["contenido"] for id_, datos in self._celdas.items()}
        for fila in range(_FILAS):
            for columna in range(_COLUMNAS):
                id_celda = _id_celda(fila, columna)
                texto = texto_resultado_celda(contenidos, id_celda)
                if self._estilo(id_celda)["formato_numero"] and texto not in ("", "#ERROR"):
                    try:
                        texto = formatear_miles(float(texto))
                    except ValueError:
                        pass
                item = self.tabla.item(fila, columna)
                if item is None:
                    if texto == "":
                        continue
                    item = QTableWidgetItem()
                    self.tabla.setItem(fila, columna, item)
                if item.text() != texto:
                    item.setText(texto)
        # El estilo (negrita/colores) lo decide el delegate leyendo
        # `self._celdas` en cada pintado — no cambia ningún dato del
        # modelo, así que Qt no sabe solo que hay que repintar.
        self.tabla.viewport().update()

    # ------------------------------------------------------------------------------------ formato

    def _alternar_negrita(self) -> None:
        nuevo = self.boton_negrita.isChecked()
        self._aplicar_a_seleccion(lambda estilo: estilo.__setitem__("negrita", nuevo))

    def _elegir_color_texto(self) -> None:
        color = QColorDialog.getColor(parent=self)
        if not color.isValid():
            return
        self._aplicar_a_seleccion(lambda estilo: estilo.__setitem__("color_texto", color.name()))

    def _elegir_color_fondo(self) -> None:
        color = QColorDialog.getColor(parent=self)
        if not color.isValid():
            return
        self._aplicar_a_seleccion(lambda estilo: estilo.__setitem__("color_fondo", color.name()))

    def _alternar_formato_numero(self) -> None:
        nuevo = self.boton_formato_numero.isChecked()
        self._aplicar_a_seleccion(lambda estilo: estilo.__setitem__("formato_numero", nuevo))

    def _alinear(self, alineacion: str) -> None:
        """Pedido explícito: botones de alineación — fijan un override
        explícito ("izquierda"/"centro"/"derecha") que pisa el default
        automático de `_alineacion_efectiva` para la celda/selección."""
        self._aplicar_a_seleccion(lambda estilo: estilo.__setitem__("alineacion", alineacion))

    def _combinar_celdas(self) -> None:
        """Un solo botón que combina o descombina según el estado
        actual de la selección — pedido explícito: "un botón de
        combinar celdas, que es botón también descombine". Sin
        persistencia (se pierde al cerrar TODO el sistema, a diferencia
        del resto de la planilla) — no se pidió explícitamente guardar
        esto, y la ventana de todos modos nunca se destruye durante la
        sesión, así que sobrevive a mostrar/ocultar con F2 igual."""
        indices = {(idx.row(), idx.column()) for idx in self.tabla.selectedIndexes()}
        if not indices:
            return
        fila_min = min(f for f, _ in indices)
        fila_max = max(f for f, _ in indices)
        columna_min = min(c for _, c in indices)
        columna_max = max(c for _, c in indices)
        ya_combinada = (
            self.tabla.rowSpan(fila_min, columna_min) > 1 or self.tabla.columnSpan(fila_min, columna_min) > 1
        )
        if ya_combinada:
            self.tabla.setSpan(fila_min, columna_min, 1, 1)
        else:
            self.tabla.setSpan(fila_min, columna_min, fila_max - fila_min + 1, columna_max - columna_min + 1)

    def _borrar_contenido_seleccion(self) -> None:
        self._aplicar_a_seleccion(lambda estilo: estilo.__setitem__("contenido", ""))
        self._cargar_barra_formula()

    def _vaciar_todo(self) -> None:
        """NO llama a `_refrescar_grilla()` (eso recrearía los ~480
        `QTableWidgetItem` de cero) — reutiliza los ítems que ya existen
        desde que se construyó la ventana y solo les borra el texto/
        estilo, mismo criterio que evita el bug de PySide6/shiboken
        documentado en el docstring del módulo (ahí era por destruir la
        ventana entera; esto confirma que recrear SOLO los ítems, sin
        tocar la ventana, dispara el mismo bug)."""
        respuesta = QMessageBox.question(
            self, "Vaciar planilla",
            "Esto borra todo el contenido y el formato de la planilla, para todas las celdas. ¿Confirmás?",
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        vaciar_todo(self.conn)
        self._celdas = {}
        self._recalcular_textos()
        self._cargar_barra_formula()
