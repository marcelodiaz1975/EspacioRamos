"""Mensajes predefinidos (FA8, sección 5.5): biblioteca editable de
mensajes ad hoc (a diferencia de los mensajes automáticos del Centro de
mensajería, sección 5.3, que viven en su propia tabla `PlantillaTexto` —
ver `app.negocio.plantillas_texto` y la solapa "Textos del sistema" de
"Archivos y listas" — no en `MensajePredefinido`). Formato estándar de
catálogo (solapa "Listado", Buscar a la izquierda) con todo lo propio de
esta pantalla agrupado ARRIBA de Nuevo/Editar/Eliminar
(`panel_extra_superior_izquierda`, pedido de la clienta al revisar esta
pantalla), de arriba abajo: el combo "Categoría" (filtro que solo afecta
la visualización, mismo criterio que el resto del sistema), "Dirigido a"
más los cuatro selectores de contexto Localidad/Edificio/Unidad/
Consultorio (ver más abajo) y el botón "Copiar mensaje" (`botonPrimario`
— es la acción más importante de esta pantalla, por eso "Nuevo" pasa a
`botonSecundario` acá vía `nuevo_secundario=True`). Debajo de toda la
pantalla queda la vista previa (de solo lectura) que sustituye
{edificio}/{unidad}/{consultorio} y {apodo} según el contexto elegido —
"Copiar mensaje" la manda al portapapeles.

Categoría es un catálogo abierto (mismo criterio que Responsable.Rol):
sugiere los valores de Listas editables (TipoLista="CategoriaMensaje")
pero admite tipear uno nuevo ahí mismo sin tener que darlo de alta antes
en ese catálogo.

Localidad/Edificio/Unidad/Consultorio del MENSAJE (en el cuadro de
diálogo) son cuatro campos independientes (no encadenados en cascada):
si los cuatro quedan sin seleccionar, el mensaje se entiende general
(pedido de la clienta) — "En general" es la etiqueta de ese valor en
blanco en los cuatro combos, tanto acá como en los selectores de
contexto de abajo. Por eso, a diferencia de
`catalogos.pantalla_unidades`/`pantalla_consultorios` (donde Edificio/
Unidad son obligatorios), los combos de Edificio/Unidad/Consultorio acá
necesitan su propia versión con esa opción en blanco al principio
(`_opciones_edificio_o_general` y análogas) — las de `catalogos.py` no
la tienen porque ahí esos campos son obligatorios.

Selectores de contexto (Dirigido a + Localidad/Edificio/Unidad/
Consultorio, debajo de "Categoría"): NO son parte del registro
guardado, son solo contexto para la Vista previa del mensaje
seleccionado en la tabla. Todos arrancan en su valor "general" (Nadie en
particular / En general) — cuando quedan así, la vista previa usa el
vínculo propio del mensaje tal cual está guardado; elegir algo puntual
ahí lo pisa campo por campo (ver `_actualizar_vista_previa`), para poder
previsualizar, por ejemplo, un mensaje general como si fuera para un
edificio puntual sin tener que editar el mensaje. Localidad no tiene
ninguna variable propia todavía ({edificio}/{unidad}/{consultorio}/
{apodo} son las únicas) — queda ahí por paridad con el cuadro de
diálogo, listo para el día que haga falta un {localidad}.

Reordenamiento de formularios (Excel de la clienta): dejó de ser una
pantalla propia del menú y pasó a ser la solapa "Mensajes predefinidos"
de "Grilla y mensajería" (`_PanelMensajesPredefinidos`, junto a "Grilla
semanal" y "Centro de mensajería" — ver `grilla_y_mensajeria.py`). El
`PantallaCRUD` interno pasa a `anidado=True` (sin su propio título ni
`QTabWidget` "Listado") y `_PanelMensajesPredefinidos` pone
`objectName="panelSolapa"` en sí misma — la "Vista previa" de abajo,
fuera del `PantallaCRUD`, sigue en el mismo lugar."""
from __future__ import annotations

import sqlite3

from PySide6.QtGui import QFontMetrics, QGuiApplication
from PySide6.QtWidgets import QComboBox, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from app.gui.crud_generico import Campo, PantallaCRUD, campos_libres
from app.gui.pantallas.catalogos import _opciones_consultorio, _opciones_edificio, _opciones_localidad, _opciones_unidad
from app.gui.pantallas.reservas import _opciones_profesional
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.listas_editables import opciones_lista
from app.negocio.mensajes import sustituir_variables
from app.repositorio.registro import obtener_repositorio

_TODAS = "__todas__"


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


_COLCHON_COMBO = 45
"""Margen para la flecha del desplegable y los bordes del combo, sumado
al ancho real del texto más largo cargado (ver `_ancho_necesario_
combo`) — Qt no lo cuenta dentro de `QFontMetrics.horizontalAdvance`."""


def _ancho_necesario_combo(combo: QComboBox) -> int:
    """Ancho mínimo para que NINGÚN ítem de `combo` quede cortado — a
    diferencia de `combo.sizeHint()` (que para un combo EDITABLE, como
    "Dirigido a" en este formulario, sale del `QLineEdit` interno y NO
    crece con el ítem más largo cargado), esto mide el texto real de
    CADA ítem con `QFontMetrics`, así que funciona igual para un combo
    editable o uno normal."""
    metrica = QFontMetrics(combo.font())
    ancho_texto = max((metrica.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())), default=0)
    return ancho_texto + _COLCHON_COMBO


def _nombre_espacio(conn: sqlite3.Connection) -> str:
    """Mismo criterio que `app.negocio.mensajes`/`plantillas_texto`
    (duplicado acá, sin relación de dependencia con esos módulos): el
    nombre del espacio de `Configuracion`, en blanco si no está
    cargado."""
    fila = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    return (fila["NombreEspacio"] if fila else None) or ""


def _nombre_administrador_principal(conn: sqlite3.Connection) -> str:
    """Variable {nombre_administrador_principal}: pedido explícito de la
    clienta sobre de DÓNDE sacarlo — "Base de datos/Responsables, de esa
    solapa el Nombre del responsable que está agendado como
    'Administrador principal' [`Responsable.Rol`, catálogo abierto, ver
    `app.db.seed.RolResponsable`] con campo 'Contacto principal'
    [`Responsable.EsContactoPrincipal`] seteado en 'Sí'." En blanco si no
    hay ningún responsable que cumpla las dos condiciones a la vez (o
    hay más de uno — se toma el primero, no debería pasar en un uso
    normal). Distinto del "{contacto}" que ya usa el PDF de Valores
    vigentes (`app.pdf.valores_pdf._sustituciones_detalles_
    complementarios`): ese filtra por `EsContactoPrincipal`/`AptoPDF`
    sin mirar el `Rol`, y arma "Nombre - Celular - Email"; acá es solo
    el nombre, filtrado además por `Rol`."""
    fila = conn.execute(
        "SELECT Nombre FROM Responsable WHERE Rol = 'Administrador principal' "
        "AND EsContactoPrincipal = 1 AND Activo = 1 LIMIT 1"
    ).fetchone()
    return (fila["Nombre"] if fila else None) or ""


def _opciones_localidad_o_general(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "En general")] + _opciones_localidad(conn)[1:]


def _opciones_edificio_o_general(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "En general")] + _opciones_edificio(conn)


def _opciones_unidad_o_general(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "En general")] + _opciones_unidad(conn)


def _opciones_consultorio_o_general(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "En general")] + _opciones_consultorio(conn)


def _opciones_categoria_mensaje(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Sugerencias del combo editable "Categoría" (diálogo Nuevo/
    Editar). Bug real reportado por la clienta: "ya habiendo una
    cargada si despliego la cascada me tendría que ofrecer como opción
    esa categoría, tengo una pero pincho ahí y no aparece nada" — antes
    usaba directo `opciones_lista("CategoriaMensaje")`, que solo trae lo
    que esté cargado en el catálogo "Listas editables"; pero Categoría
    es un catálogo ABIERTO (ver el docstring del módulo): la clienta
    puede tipear una categoría nueva directo en un mensaje sin pasar por
    ese catálogo, y esa categoría quedaba sin aparecer nunca más en la
    cascada de ningún otro mensaje. Se suman también las categorías que
    YA están en uso en algún `MensajePredefinido` — mismo criterio que
    ya usa `_refrescar_categorias` para el filtro "Categoría" de
    arriba — además de lo que haya en Listas editables, sin duplicar."""
    desde_lista = {v for v, _ in opciones_lista("CategoriaMensaje")(conn)}
    en_uso = {m["Categoria"] for m in obtener_repositorio(conn, "MensajePredefinido").listar() if m["Categoria"]}
    return [(v, v) for v in sorted(desde_lista | en_uso)]


def _campos_mensaje_predefinido(conn: sqlite3.Connection) -> list[Campo]:
    # Pedido explícito de la clienta sobre esta tabla, primera ronda:
    # "Categoría"/"Descripción" +1/3 de ancho; "Consul" (no
    # "Consultorio") y "Activo" al mínimo para que entre la etiqueta sin
    # cortar, centrados. Segunda ronda, sobre la misma tabla ya con
    # datos reales: "Categoría"/"Descripción" quedaban DEMASIADO anchas
    # —se saca el `tercio_extra`, vuelven al ancho natural (contenido +
    # padding, igual que Localidad/Edificio/Unidad) — y "Consul" pasa a
    # ese mismo criterio natural en vez de achicarse al mínimo de su
    # etiqueta ("dejala del mismo ancho que localidad, edificio y
    # unidad"): con contenido numérico corto, de novo queda chica igual,
    # pero por el mismo mecanismo que esas tres, no por un caso especial
    # aparte. "Activo" sigue al mínimo de su etiqueta (sin cambios, no
    # fue parte de este segundo pedido). "Descripción" queda un poco más
    # ancha que "Categoría" sin necesidad de ningún truco extra: su
    # contenido real (una frase) es naturalmente más largo que una
    # categoría (una palabra o dos) — el mismo ancho natural+padding ya
    # lo resuelve solo. La columna "Mensaje" sigue titulada "Texto" y
    # como `columna_flexible` del `PantallaCRUD` (ver `_armar_ui`) — se
    # achica a lo que haga falta para que la tabla entera entre en el
    # ancho de pantalla sin espacio en blanco, con "Activo" como última
    # columna visible.
    return [
        Campo(
            "Categoria", "Categoría", tipo="combo", opciones=_opciones_categoria_mensaje,
            combo_editable=True,
        ),
        Campo("Descripcion", "Descripción"),
        Campo("IdLocalidad", "Localidad", tipo="combo", opciones=_opciones_localidad_o_general),
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=_opciones_edificio_o_general),
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad_o_general),
        Campo(
            "IdConsultorio", "Consul", tipo="combo", opciones=_opciones_consultorio_o_general,
            centrado=True,
        ),
        Campo("Mensaje", "Texto", tipo="texto_largo", variables=_VARIABLES_MENSAJE),
        Campo("Activo", "Activo", tipo="booleano", centrado=True, ancho_minimo_etiqueta=True),
        *campos_libres(conn),
    ]


def _variables_ubicacion(
    conn: sqlite3.Connection,
    id_edificio: int | None,
    id_unidad: int | None,
    id_consultorio: int | None,
    id_localidad: int | None = None,
) -> dict[str, str]:
    """El más específico de los tres (edificio/unidad/consultorio) gana
    — usado tanto con el vínculo propio del mensaje como, en la vista
    previa, con los valores que hayan quedado tras aplicar las
    selecciones de contexto (que pisan al vínculo del mensaje campo por
    campo, ver `_actualizar_vista_previa`). `{localidad}` es
    independiente de esos tres (campo propio del mensaje, sin cascada —
    ver el docstring del módulo) y se resuelve aparte, con el mismo
    criterio de "en blanco si no hay nada elegido" que los otros tres."""
    variables = {"edificio": "", "unidad": "", "consultorio": ""}
    if id_consultorio is not None:
        fila = conn.execute(
            "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS Edificio "
            "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
            "JOIN Edificio e ON e.IdEdificio = u.IdEdificio WHERE c.IdConsultorio = ?",
            (id_consultorio,),
        ).fetchone()
        if fila:
            variables = {"edificio": fila["Edificio"], "unidad": fila["Departamento"], "consultorio": str(fila["NumeroConsultorio"])}
    elif id_unidad is not None:
        fila = conn.execute(
            "SELECT u.Departamento, e.Nombre AS Edificio FROM Unidad u "
            "JOIN Edificio e ON e.IdEdificio = u.IdEdificio WHERE u.IdUnidad = ?",
            (id_unidad,),
        ).fetchone()
        if fila:
            variables = {"edificio": fila["Edificio"], "unidad": fila["Departamento"], "consultorio": ""}
    elif id_edificio is not None:
        fila = conn.execute("SELECT Nombre FROM Edificio WHERE IdEdificio = ?", (id_edificio,)).fetchone()
        if fila:
            variables = {"edificio": fila["Nombre"], "unidad": "", "consultorio": ""}
    variables["localidad"] = ""
    if id_localidad is not None:
        fila_localidad = conn.execute("SELECT Localidad FROM Localidad WHERE IdLocalidad = ?", (id_localidad,)).fetchone()
        if fila_localidad:
            variables["localidad"] = fila_localidad["Localidad"] or ""
    return variables


_VARIABLES_MENSAJE = {
    "apodo": "Apodo del profesional elegido en \"Dirigido a\" (vista previa).",
    "nombre": "Nombre de pila del profesional elegido en \"Dirigido a\".",
    "apellido": "Apellido del profesional elegido en \"Dirigido a\".",
    "tratamiento": "Tratamiento del profesional elegido en \"Dirigido a\" (ej. \"Lic.\", \"Dr.\").",
    "edificio": "Nombre del edificio vinculado al mensaje (o elegido en los selectores de contexto).",
    "unidad": "Departamento de la unidad vinculada al mensaje (o elegida en los selectores de contexto).",
    "consultorio": "Número del consultorio vinculado al mensaje (o elegido en los selectores de contexto).",
    "localidad": "Localidad vinculada al mensaje (o elegida en los selectores de contexto).",
    "nombre_espacio": "Nombre del espacio (Configuración general).",
    "nombre_administrador_principal": (
        "Nombre del responsable agendado como \"Administrador principal\" con \"Contacto principal\" en "
        "Sí (Base de datos del espacio / Responsables)."
    ),
}
"""Catálogo único de variables ofrecidas en el diálogo Nuevo/Editar
(hallazgo #24 de la auditoría) — mismo dict que alimenta la fila de
botones del campo "Mensaje" (ver `_campos_mensaje_predefinido`) y la
leyenda de "Vista previa" más abajo, para no mantener la lista de
variables en dos lugares."""


class _PanelMensajesPredefinidos(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        panel_superior = QWidget()
        layout_superior = QVBoxLayout(panel_superior)
        layout_superior.setContentsMargins(0, 0, 0, 0)

        layout_superior.addWidget(_titulo_campo("Categoría"))
        self.combo_filtro = QComboBox()
        self.combo_filtro.currentIndexChanged.connect(self._aplicar_filtro)
        layout_superior.addWidget(self.combo_filtro)

        layout_superior.addWidget(_titulo_campo("Dirigido a"))
        self.combo_dirigido_a = QComboBox()
        self.combo_dirigido_a.addItem("Nadie en particular", None)
        for id_profesional, etiqueta in _opciones_profesional(self.conn):
            self.combo_dirigido_a.addItem(etiqueta, id_profesional)
        habilitar_busqueda_profesional(self.combo_dirigido_a)
        self.combo_dirigido_a.currentIndexChanged.connect(self._actualizar_vista_previa)
        layout_superior.addWidget(self.combo_dirigido_a)

        layout_superior.addWidget(_titulo_campo("Localidad"))
        self.combo_localidad_contexto = QComboBox()
        for id_localidad, etiqueta in _opciones_localidad_o_general(self.conn):
            self.combo_localidad_contexto.addItem(etiqueta, id_localidad)
        self.combo_localidad_contexto.currentIndexChanged.connect(self._actualizar_vista_previa)
        layout_superior.addWidget(self.combo_localidad_contexto)

        layout_superior.addWidget(_titulo_campo("Edificio"))
        self.combo_edificio_contexto = QComboBox()
        for id_edificio, etiqueta in _opciones_edificio_o_general(self.conn):
            self.combo_edificio_contexto.addItem(etiqueta, id_edificio)
        self.combo_edificio_contexto.currentIndexChanged.connect(self._actualizar_vista_previa)
        layout_superior.addWidget(self.combo_edificio_contexto)

        layout_superior.addWidget(_titulo_campo("Unidad"))
        self.combo_unidad_contexto = QComboBox()
        for id_unidad, etiqueta in _opciones_unidad_o_general(self.conn):
            self.combo_unidad_contexto.addItem(etiqueta, id_unidad)
        self.combo_unidad_contexto.currentIndexChanged.connect(self._actualizar_vista_previa)
        layout_superior.addWidget(self.combo_unidad_contexto)

        layout_superior.addWidget(_titulo_campo("Consultorio"))
        self.combo_consultorio_contexto = QComboBox()
        for id_consultorio, etiqueta in _opciones_consultorio_o_general(self.conn):
            self.combo_consultorio_contexto.addItem(etiqueta, id_consultorio)
        self.combo_consultorio_contexto.currentIndexChanged.connect(self._actualizar_vista_previa)
        layout_superior.addWidget(self.combo_consultorio_contexto)

        self.boton_copiar = QPushButton("Copiar mensaje")
        self.boton_copiar.setObjectName("botonPrimario")
        self.boton_copiar.clicked.connect(self._copiar_mensaje)
        layout_superior.addWidget(self.boton_copiar)

        # Pedido explícito de la clienta: "reducí al mínimo la columna
        # de los filtros para que no quede ninguna etiqueta o elemento
        # cortado". Sin esto, el ancho de `panel_superior` queda librado
        # al `sizeHint()` de Qt de cada combo — que para los combos NO
        # editables (Localidad/Edificio/Unidad/Consultorio de contexto,
        # Categoría) sí refleja el ítem más largo de la lista, pero NO
        # para "Dirigido a" (`habilitar_busqueda_profesional` lo vuelve
        # editable, y el `sizeHint()` de un combo editable sale del
        # `QLineEdit` interno — un valor genérico que NO crece con el
        # nombre de profesional más largo cargado). Si "Dirigido a"
        # termina siendo el más ancho de los seis (puede pasar con
        # nombres/tratamientos largos y edificios/unidades cortos), el
        # resto de los combos no lo salvan y el nombre elegido queda
        # cortado dentro del combo cerrado.
        #
        # `_ancho_necesario_combo` mide el texto real de CADA ítem
        # cargado (vía `QFontMetrics`, no `sizeHint()`) — funciona igual
        # para los combos editables y los que no, porque lee
        # `itemText(i)` directo del modelo, sin pasar por el cálculo
        # interno de Qt que falla para el editable. El máximo de los
        # seis (+ el botón "Copiar mensaje", que puede ser más ancho que
        # cualquier combo si la base está recién instalada, sin
        # edificios/profesionales cargados todavía) fija el ancho real
        # mínimo que hace falta — ni un píxel más.
        ancho_panel_filtros = max(
            _ancho_necesario_combo(self.combo_filtro),
            _ancho_necesario_combo(self.combo_dirigido_a),
            _ancho_necesario_combo(self.combo_localidad_contexto),
            _ancho_necesario_combo(self.combo_edificio_contexto),
            _ancho_necesario_combo(self.combo_unidad_contexto),
            _ancho_necesario_combo(self.combo_consultorio_contexto),
            self.boton_copiar.sizeHint().width(),
        )
        panel_superior.setFixedWidth(ancho_panel_filtros)

        self.crud = PantallaCRUD(
            self.conn, "MensajePredefinido", "Mensajes predefinidos", _campos_mensaje_predefinido(self.conn),
            panel_extra_superior_izquierda=panel_superior,
            nuevo_secundario=True,
            anidado=True,
            # Pedido explícito de la clienta: el diálogo "Nuevo"/"Editar"
            # al doble de ancho que el default, para verse completo al
            # abrir (ver `_DialogoRegistro.__init__`). El alto arrancó
            # también al doble, pero quedaba demasiado alto — pedido
            # posterior, "reducí el alto... un 30%" SIN tocar el ancho:
            # 2.0 * 0.7 = 1.4, multiplicador independiente del de ancho.
            multiplicador_tamano_dialogo=2.0,
            multiplicador_alto_dialogo=1.4,
            # "Texto" (antes "Mensaje") se achica a lo que haga falta
            # para que la tabla entre en el ancho de pantalla sin dejar
            # espacio en blanco, con "Activo" como última columna
            # visible (ver `columna_flexible` en crud_generico.py).
            columna_flexible="Mensaje",
            # Punto 95 (SistemaDF v0.11.2026.10): la cadena de foco de
            # esta pantalla no es solo Buscar/Nuevo/Editar/Eliminar (el
            # default de `PantallaCRUD`) — tiene que incluir también los
            # selectores de contexto de arriba, así que se arma una
            # propia más abajo (mismo criterio que Gastos operativos).
            instalar_foco=False,
            # Pedido explícito de la clienta: "en el hipotético caso de
            # que quiero editar una categoría cargada dentro de un
            # registro... a todos los items que tienen la categoría
            # [vieja] afecta el mismo cambio" — renombrar la Categoría
            # de UN mensaje (Categoría es texto libre por registro, no
            # una referencia a un catálogo) tiene que renombrarla en
            # TODOS los mensajes que todavía tenían la vieja. Ver
            # `_cascada_renombrar_categoria`.
            al_actualizar=self._cascada_renombrar_categoria,
        )
        self.crud.tabla_widget.itemSelectionChanged.connect(self._actualizar_vista_previa)
        layout.addWidget(self.crud, stretch=1)

        actualizar_original = self.crud.actualizar

        def _actualizar_con_filtro():
            actualizar_original()
            self._refrescar_categorias()
            self._aplicar_filtro()

        self.crud.actualizar = _actualizar_con_filtro
        self.crud.actualizar()

        etiqueta_vista_previa = QLabel(
            "Vista previa (sustituye {edificio}/{unidad}/{consultorio}/{localidad} por el vínculo elegido en "
            "el mensaje o en los selectores de contexto, y {apodo}/{nombre}/{apellido}/{tratamiento} por el "
            "profesional elegido en \"Dirigido a\")"
        )
        etiqueta_vista_previa.setWordWrap(True)
        layout.addWidget(etiqueta_vista_previa)
        self.texto_vista_previa = QPlainTextEdit()
        self.texto_vista_previa.setReadOnly(True)
        self.texto_vista_previa.setFixedHeight(100)
        layout.addWidget(self.texto_vista_previa)

        # Punto 95 (SistemaDF v0.11.2026.10): la cadena de foco de esta
        # pantalla no es solo Buscar/Nuevo/Editar/Eliminar (el default
        # de `PantallaCRUD`, desactivado arriba con `instalar_foco=
        # False`) — tiene que incluir también los selectores de contexto
        # de arriba, así que se arma una propia (mismo criterio que
        # Gastos operativos).
        self._foco = instalar_enter_avanza_foco(
            [
                self.crud.campo_buscar, self.combo_filtro, self.combo_dirigido_a,
                self.combo_localidad_contexto, self.combo_edificio_contexto, self.combo_unidad_contexto,
                self.combo_consultorio_contexto, self.boton_copiar,
                self.crud.boton_nuevo, self.crud.boton_editar, self.crud.boton_eliminar,
            ],
            parent=self,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.reiniciar()

    def reiniciar(self) -> None:
        """Punto 1.4: al volver a entrar (o F3), se resetea el filtro de
        Categoría (`combo_filtro`, antes no se tocaba) y la tabla
        (`self.crud.reiniciar()`, limpia Buscar), y el foco vuelve al
        primero de la cadena completa de esta pantalla."""
        self.combo_filtro.setCurrentIndex(0)
        self.crud.reiniciar()
        self.crud.campo_buscar.setFocus()

    def _cascada_renombrar_categoria(self, registro: sqlite3.Row, valores: dict) -> None:
        """`al_actualizar` de `self.crud` (ver `_armar_ui`): corre
        DESPUÉS de que `PantallaCRUD._editar` ya guardó `valores` en el
        registro editado — `registro` es la fila COMO ESTABA ANTES de
        ese guardado. Si la Categoría cambió (y la anterior no estaba
        vacía), el resto de los mensajes que todavía tengan la vieja
        pasan a la nueva — pedido explícito de la clienta: renombrar la
        categoría de un mensaje puntual tiene que renombrarla en TODOS
        los que la compartían, no dejar un registro "aislado" con el
        nombre nuevo mientras el resto sigue con el viejo. Sin tocar la
        categoría nueva en blanco (no es un pedido de "vaciar todas las
        demás", solo de rename) ni el propio registro ya editado (ya
        quedó con el valor nuevo, lo hizo `_editar` antes de llamar
        acá)."""
        categoria_anterior = registro["Categoria"]
        categoria_nueva = valores.get("Categoria")
        if not categoria_anterior or not categoria_nueva or categoria_nueva == categoria_anterior:
            return
        repo = obtener_repositorio(self.conn, "MensajePredefinido")
        for mensaje in repo.listar(Categoria=categoria_anterior):
            if mensaje["IdMensaje"] == registro["IdMensaje"]:
                continue
            repo.actualizar(mensaje["IdMensaje"], Categoria=categoria_nueva)
        self.conn.commit()

    def _refrescar_categorias(self) -> None:
        categoria_actual = self.combo_filtro.currentData()
        self.combo_filtro.blockSignals(True)
        self.combo_filtro.clear()
        self.combo_filtro.addItem("Todas", _TODAS)
        categorias = sorted({m["Categoria"] for m in obtener_repositorio(self.conn, "MensajePredefinido").listar() if m["Categoria"]})
        for categoria in categorias:
            self.combo_filtro.addItem(categoria, categoria)
        indice = self.combo_filtro.findData(categoria_actual) if categoria_actual else 0
        self.combo_filtro.setCurrentIndex(indice if indice >= 0 else 0)
        self.combo_filtro.blockSignals(False)

    def _aplicar_filtro(self) -> None:
        categoria = self.combo_filtro.currentData()
        tabla = self.crud.tabla_widget
        for fila in range(tabla.rowCount()):
            item_categoria = tabla.item(fila, 0)
            texto = item_categoria.text() if item_categoria else ""
            oculta = categoria not in (None, _TODAS) and texto != categoria
            tabla.setRowHidden(fila, oculta)

    def _actualizar_vista_previa(self) -> None:
        id_valor = self.crud.fila_seleccionada_id()
        if id_valor is None:
            self.texto_vista_previa.clear()
            return
        mensaje = self.crud.repositorio.obtener(id_valor)
        if mensaje is None:
            self.texto_vista_previa.clear()
            return
        id_edificio = self.combo_edificio_contexto.currentData()
        if id_edificio is None:
            id_edificio = mensaje["IdEdificio"]
        id_unidad = self.combo_unidad_contexto.currentData()
        if id_unidad is None:
            id_unidad = mensaje["IdUnidad"]
        id_consultorio = self.combo_consultorio_contexto.currentData()
        if id_consultorio is None:
            id_consultorio = mensaje["IdConsultorio"]
        id_localidad = self.combo_localidad_contexto.currentData()
        if id_localidad is None:
            id_localidad = mensaje["IdLocalidad"]
        variables = _variables_ubicacion(self.conn, id_edificio, id_unidad, id_consultorio, id_localidad)
        variables.update(self._variables_profesional_dirigido_a())
        variables["nombre_espacio"] = _nombre_espacio(self.conn)
        variables["nombre_administrador_principal"] = _nombre_administrador_principal(self.conn)
        self.texto_vista_previa.setPlainText(sustituir_variables(mensaje["Mensaje"] or "", variables))

    def _variables_profesional_dirigido_a(self) -> dict[str, str]:
        """{apodo}/{nombre}/{apellido}/{tratamiento} del profesional
        elegido en "Dirigido a" — en blanco los cuatro sin ninguno
        elegido (mismo criterio que el resto de las variables de este
        formulario)."""
        id_profesional = self.combo_dirigido_a.currentData()
        if id_profesional is None:
            return {"apodo": "", "nombre": "", "apellido": "", "tratamiento": ""}
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(id_profesional)
        if profesional is None:
            return {"apodo": "", "nombre": "", "apellido": "", "tratamiento": ""}
        return {
            "apodo": profesional["Apodo"] or "",
            "nombre": profesional["NombrePila"] or "",
            "apellido": profesional["Apellido"] or "",
            "tratamiento": profesional["Tratamiento"] or "",
        }

    def _copiar_mensaje(self) -> None:
        QGuiApplication.clipboard().setText(self.texto_vista_previa.toPlainText())
