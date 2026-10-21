"""Pantalla de Profesionales (F06/F07, sección 3.4) sobre PantallaCRUD, con
un panel de documentación (archivos sueltos en Profesionales/{código}/
Documentación) para el profesional seleccionado — va debajo de Nuevo/
Editar/Eliminar en el panel izquierdo (`panel_extra_izquierda` de
PantallaCRUD), mismo formato solapa que el resto de los catálogos.

Reordenamiento de formularios (Excel de la clienta): dejó de ser una
pantalla propia del menú y pasó a ser la solapa "Listado de
profesionales" del formulario "Profesionales" (`_PanelProfesionales`,
junto a "Profesiones y tratamientos" — el catálogo `Profesion` de
`catalogos.py`, construido con `anidado=True`). El `PantallaCRUD` interno
(`self.crud_profesionales`) también pasa a `anidado=True` — sin eso,
quedaría un título/QTabWidget "Listado" anidado dentro de la solapa del
formulario de afuera."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.crud_generico import Campo, PantallaCRUD, campos_libres
from app.gui.pantallas import catalogos
from app.gui.pantallas.imagenes import _pixmap_primera_pagina_pdf
from app.gui.pantallas.reservas import _opciones_profesional as _opciones_profesional_canonico
from app.gui.widgets.eliminar_tecla import instalar_eliminar_con_tecla
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.archivos_generados import aplicar_cambio_codigo
from app.negocio.dias import fecha_actual
from app.negocio.documentacion_profesional import (
    CATEGORIAS_DOCUMENTACION_PROFESIONAL,
    agregar_documento,
    eliminar_documento,
    listar_documentos,
)
from app.negocio.imagenes import CATEGORIA_OTRAS_IMAGENES, CATEGORIA_OTROS_DOCUMENTOS
from app.negocio.listas_editables import opciones_lista
from app.negocio.profesionales import (
    normalizar_cuit,
    opciones_tratamiento,
    sugerir_codigo,
    sugerir_codigos_multiples,
    tratamiento_sugerido,
)
from app.negocio.validaciones import (
    FORMATO_CUIT,
    FORMATO_DNI,
    FORMATO_EMAIL,
    FORMATO_FECHA,
    es_cuit_valido,
    es_dni_valido,
    es_email_valido,
    es_fecha_valida,
)
from app.repositorio.registro import obtener_repositorio

_ANCHO_CAMPO = 240  # mismo ancho que el panel izquierdo de PantallaCRUD (ver crud_generico._ANCHO_CAMPO)
# Pedido explícito de la clienta sobre esta pantalla puntual (no una regla
# general de estilos.py): los cinco botones de la columna (los tres del CRUD
# genérico — Nuevo/Editar/Eliminar — más los dos propios de este panel —
# Agregar/Eliminar archivo) bajan a la mitad de su alto default, para hacer
# lugar al cuadro de Vista previa nuevo. Medido con un script de geometría:
# el alto default de un botón (padding "8px 16px" de estilos.py) es 32px;
# "padding: 0px 16px" da exactamente 16px, la mitad exacta.
_ESTILO_BOTON_COMPACTO = "padding: 0px 16px;"
# Alto fijo de `lista_documentos` para mostrar ~5 líneas sin scroll (medido
# con un script de geometría: alto de fila + marco del widget, mismo
# criterio que `_alto_para_filas` de Reservas/Llaves, acá para un
# `QListWidget` en vez de una tabla) — sigue siendo scrolleable (default de
# Qt) para cuando hay más archivos de los que entran.
_ALTO_LISTA_DOCUMENTOS = 76

_CATEGORIAS = [
    ("R", "R - Regular"),
    ("A", "A - Reserva aislada"),
    ("B", "B - Bonificado"),
    ("E", "E - Equipo (consolida en su cabeza de equipo)"),
    ("X", "X - Inactivo"),
    ("C", "C - Contacto / prospecto"),
]
_SEXOS = [("Masculino", "Masculino"), ("Femenino", "Femenino"), ("No binario", "No binario")]


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


class _DialogoCategoriaDocumento(QDialog):
    """Categoría del archivo (lista cerrada, ver
    `documentacion_profesional.CATEGORIAS_DOCUMENTACION_PROFESIONAL`) —
    el archivo se guarda con ese nombre en vez del original. "Otras
    imágenes"/"Otros documentos" no tienen nombre propio: piden además
    un detalle libre para poder identificarlos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar archivo")
        layout = QVBoxLayout(self)

        layout.addWidget(_titulo_campo("Categoría"))
        self.combo_categoria = QComboBox()
        self.combo_categoria.addItems(CATEGORIAS_DOCUMENTACION_PROFESIONAL)
        self.combo_categoria.currentTextChanged.connect(self._actualizar_visibilidad_detalle)
        layout.addWidget(self.combo_categoria)

        self.etiqueta_detalle = _titulo_campo("Detalle (para identificarlo)")
        layout.addWidget(self.etiqueta_detalle)
        self.campo_detalle = QLineEdit()
        layout.addWidget(self.campo_detalle)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        self._actualizar_visibilidad_detalle(self.combo_categoria.currentText())

    def _actualizar_visibilidad_detalle(self, categoria: str) -> None:
        requiere_detalle = categoria in (CATEGORIA_OTRAS_IMAGENES, CATEGORIA_OTROS_DOCUMENTOS)
        self.etiqueta_detalle.setVisible(requiere_detalle)
        self.campo_detalle.setVisible(requiere_detalle)

    def _validar_y_aceptar(self) -> None:
        categoria = self.combo_categoria.currentText()
        if categoria in (CATEGORIA_OTRAS_IMAGENES, CATEGORIA_OTROS_DOCUMENTOS) and not self.campo_detalle.text().strip():
            QMessageBox.warning(self, "Agregar archivo", "Ingresá un detalle para identificar este archivo.")
            self.campo_detalle.setFocus()
            return
        self.accept()

    def categoria(self) -> str:
        return self.combo_categoria.currentText()

    def etiqueta_libre(self) -> str | None:
        return self.campo_detalle.text().strip() or None


def _opciones_categoria(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return _CATEGORIAS


def _opciones_sexo(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return _SEXOS


def _opciones_tratamiento_usados(conn: sqlite3.Connection) -> list[str]:
    """Cualquier `Tratamiento` ya cargado en algún profesional del
    sistema, sin duplicados — ver `_actualizar_tratamiento`."""
    filas = conn.execute(
        "SELECT DISTINCT Tratamiento FROM Profesional WHERE Tratamiento IS NOT NULL AND Tratamiento != '' "
        "ORDER BY Tratamiento"
    ).fetchall()
    return [f["Tratamiento"] for f in filas]


def _opciones_profesion(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdProfesion, Nombre FROM Profesion ORDER BY Nombre").fetchall()
    return [(f["IdProfesion"], f["Nombre"]) for f in filas]


def _campos_profesional(conn: sqlite3.Connection) -> list[Campo]:
    return [
        # Primeras 4 columnas en el mismo orden que el formato canónico
        # "Código - Tratamiento Nombre Apellido" que se usa en los
        # selectores de profesional de todo el sistema (pedido puntual de
        # la clienta para esta pantalla, no una regla general de Campo).
        Campo("IdCodigo", "Código"),
        Campo("Tratamiento", "Tratamiento", tipo="combo", opciones=lambda conn: [], combo_editable=True),
        Campo("NombrePila", "Nombre"),
        Campo("Apellido", "Apellido", requerido=True),
        Campo("CategoriaProfesional", "Categoría", tipo="combo", opciones=_opciones_categoria, requerido=True),
        Campo("NombreCompleto", "Nombre completo"),
        Campo("Apodo", "Apodo"),
        Campo("Sexo", "Sexo", tipo="combo", opciones=_opciones_sexo),
        Campo("DNI", "DNI", validador=es_dni_valido, formato_esperado=FORMATO_DNI),
        Campo("CUIT", "CUIT", normalizar=normalizar_cuit, validador=es_cuit_valido, formato_esperado=FORMATO_CUIT),
        Campo(
            "CondicionFiscal", "Condición fiscal", tipo="combo",
            opciones=opciones_lista("CondicionFiscal"), combo_editable=True,
        ),
        # "DD-MM-YYYY" (sin día de semana, a diferencia de `tipo="fecha"`
        # por default — ver `Campo.formato_fecha`): pedido explícito de
        # la clienta, el día de la semana de un nacimiento no aporta
        # nada (a diferencia de una fecha operativa como Vigencia o
        # Fecha de ausencia).
        Campo("FechaNacimiento", "Fecha de nacimiento", tipo="fecha", formato_fecha="dd-MM-yyyy"),
        Campo("Domicilio", "Domicilio"),
        Campo("DomicilioLocalidad", "Localidad"),
        Campo("TelefonoParticular", "Teléfono particular"),
        Campo("Celular", "Celular"),
        Campo("Email", "Email", validador=es_email_valido, formato_esperado=FORMATO_EMAIL),
        Campo("IdProfesion", "Profesión", tipo="combo", opciones=_opciones_profesion),
        Campo("MatriculaNacional", "Matrícula nacional"),
        Campo("MatriculaProvincial", "Matrícula provincial"),
        Campo(
            "FechaContacto", "Fecha de contacto (AAAA-MM-DD)",
            validador=es_fecha_valida, formato_esperado=FORMATO_FECHA,
        ),
        Campo(
            "ProfesionalCabezaEquipo", "Cabeza de equipo", tipo="combo",
            opciones=_opciones_profesional_canonico,
        ),
        Campo("SaldoCuentaActual", "Saldo cuenta actual", tipo="numero", es_monto=True),
        Campo("SaldoCuentaAnterior", "Saldo cuenta anterior", tipo="numero", es_monto=True),
        Campo("PlazoPagoExtendido", "Plazo de pago extendido"),
        Campo("MotivoPlazoExtra", "Motivo del plazo extra"),
        Campo(
            "DiaPlazoExtendidoAutomatico",
            "Día del mes para plazo extendido automático (1-31, dejar vacío si no aplica)",
            tipo="numero",
        ),
        *campos_libres(conn),
    ]


def _al_abrir_dialogo(dialogo) -> None:
    """Sección 3.4: sugiere el código (según categoría) y pre-completa el
    tratamiento (según profesión y sexo) apenas se abre el formulario, tanto
    al crear un registro nuevo como al editar uno existente — en edición,
    además de sugerir, repuebla el desplegable de Tratamiento con las
    opciones de la profesión/sexo actuales (para Fonoaudiología y
    Psicopedagogía) sin perder el valor ya cargado.

    El código (`campo_codigo`) pasa a ser de SOLO LECTURA (ronda de
    validaciones de categoría, pedido explícito de la clienta: "cualquier
    cambio pase a ser el código mas bajo disponible, que ese campo pase a
    hacer solo lectura") — el operador ya no lo tipea a mano, lo decide
    únicamente la Categoría elegida. `categoria_original`/`codigo_original`
    (el valor con el que se abrió el diálogo: vacío para un alta nueva, el
    código real para una edición) son el ancla: mientras la Categoría se
    quede en la que ya tenía, se conserva el código real tal cual estaba
    (no se lo pisa con una sugerencia); en cuanto cambia a cualquier otra,
    se sugiere el más bajo libre de esa categoría nueva — y si se vuelve a
    la categoría original, se restaura el código real de antes. El
    tratamiento sigue siendo editable, con el mismo criterio de "no pisar
    un valor que sí escribieron" de siempre."""
    conn = dialogo.conn
    combo_categoria = dialogo._entradas["CategoriaProfesional"]
    campo_codigo = dialogo._entradas["IdCodigo"]
    combo_profesion = dialogo._entradas["IdProfesion"]
    combo_sexo = dialogo._entradas["Sexo"]
    combo_tratamiento = dialogo._entradas["Tratamiento"]

    campo_codigo.setReadOnly(True)
    categoria_original = combo_categoria.currentData()
    codigo_original = campo_codigo.text().strip()

    # Mismo selector buscable (código o nombre, con jerarquía de
    # categorías) que el resto del sistema — ya viene poblado en el
    # formato canónico por `_opciones_profesional_canonico`, solo hace
    # falta sumarle el comportamiento de búsqueda.
    habilitar_busqueda_profesional(dialogo._entradas["ProfesionalCabezaEquipo"])

    def _actualizar_codigo() -> None:
        categoria = combo_categoria.currentData()
        if categoria is None:
            return
        if codigo_original and categoria == categoria_original:
            campo_codigo.setText(codigo_original)
        else:
            campo_codigo.setText(sugerir_codigo(conn, categoria))

    ultimo_tratamiento_sugerido = [None]

    def _actualizar_tratamiento() -> None:
        id_profesion = combo_profesion.currentData()
        sexo = combo_sexo.currentData()
        opciones_profesion = opciones_tratamiento(conn, id_profesion, sexo)
        sugerido = tratamiento_sugerido(conn, id_profesion, sexo)
        actual = combo_tratamiento.currentText().strip()

        # `opciones_tratamiento` solo devuelve algo para Fonoaudiología/
        # Psicopedagogía (sección 8.1) — para el resto de las profesiones
        # el desplegable quedaba vacío ("no despliega la lista de
        # tratamientos", bug reportado por la clienta): se suma, siempre,
        # cualquier Tratamiento que ya se haya usado en algún profesional
        # del sistema (mismo criterio "catálogo abierto, sugiere lo ya
        # usado" que `Responsable.Rol`/`CondicionFiscal`), así que el
        # desplegable nunca queda sin nada para elegir una vez que hay al
        # menos un profesional cargado con tratamiento.
        opciones = list(dict.fromkeys([*opciones_profesion, *_opciones_tratamiento_usados(conn)]))

        combo_tratamiento.blockSignals(True)
        combo_tratamiento.clear()
        for opcion in opciones:
            combo_tratamiento.addItem(opcion)
        combo_tratamiento.blockSignals(False)

        if actual in ("", ultimo_tratamiento_sugerido[0]):
            nuevo = sugerido or ""
            combo_tratamiento.setEditText(nuevo)
            ultimo_tratamiento_sugerido[0] = nuevo
        else:
            combo_tratamiento.setEditText(actual)

    combo_categoria.currentIndexChanged.connect(_actualizar_codigo)
    combo_profesion.currentIndexChanged.connect(_actualizar_tratamiento)
    combo_sexo.currentIndexChanged.connect(_actualizar_tratamiento)
    _actualizar_codigo()
    _actualizar_tratamiento()


def _al_guardar_profesional(valores: dict, registro: sqlite3.Row | None, conn: sqlite3.Connection) -> dict | None:
    """Dos guardarraíles de categoría (ronda de validaciones de
    categorías, consultada y confirmada con la clienta), corridos ANTES
    de guardar — nunca después, para no dejar nunca un estado inválido
    aunque sea por un instante:

    - Un profesional categoría E necesita un Cabeza de equipo cargado, Y
      que ese cabeza sea categoría R — sin esto, el E queda "huérfano":
      nunca se liquida (`liquidaciones.id_profesional_liquidable` da
      `None` sin un R válido del otro lado) y nadie se entera, porque
      hasta ahora nada lo impedía al guardar.
    - Cambiarle la categoría a un R que todavía tiene profesionales E
      vinculados (`ProfesionalCabezaEquipo` apuntando a él) se bloquea —
      "antes se debe desvincular a los miembros del equipo", el resto
      ("liberar sus horarios") es consecuencia natural de pasarlos a X,
      no una condición aparte que haga falta chequear acá. El alerta
      lista cada E con el código X que le tocaría si se lo pasa a esa
      categoría — `sugerir_codigos_multiples` en una sola pasada, para no
      sugerirle el mismo número a dos E distintos en el mismo alerta
      (cada `sugerir_codigo` por separado devolvería el más bajo libre
      SIN saber de los demás, ya que ninguno está guardado todavía)."""
    categoria_nueva = valores.get("CategoriaProfesional")

    if categoria_nueva == "E":
        id_cabeza = valores.get("ProfesionalCabezaEquipo")
        cabeza = obtener_repositorio(conn, "Profesional").obtener(id_cabeza) if id_cabeza else None
        if cabeza is None or cabeza["CategoriaProfesional"] != "R":
            QMessageBox.warning(
                None, "Categoría",
                "Un profesional categoría E necesita un Cabeza de equipo cargado, y tiene que "
                "ser un profesional categoría R.",
            )
            return None

    if registro is not None and registro["CategoriaProfesional"] == "R" and categoria_nueva != "R":
        equipo = conn.execute(
            "SELECT * FROM Profesional WHERE ProfesionalCabezaEquipo = ? AND CategoriaProfesional = 'E'",
            (registro["IdProfesional"],),
        ).fetchall()
        if equipo:
            codigos_x = sugerir_codigos_multiples(conn, "X", len(equipo))
            detalle = "\n".join(
                f"- {e['IdCodigo'] or '(sin código)'} {e['Apellido'] or ''} -> pasaría a {codigo_x}"
                for e, codigo_x in zip(equipo, codigos_x)
            )
            QMessageBox.warning(
                None, "Categoría",
                "No se puede cambiar la categoría de este profesional porque todavía tiene "
                "profesionales categoría E vinculados como cabeza de equipo:\n"
                f"{detalle}\n\n"
                "Primero hay que desvincularlos (pasarlos a categoría X, o asignarles otro "
                "Cabeza de equipo) antes de poder cambiar este profesional.",
            )
            return None

    return valores


class _PanelProfesionales(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        panel_doc = QWidget()
        layout_doc = QVBoxLayout(panel_doc)
        layout_doc.setContentsMargins(0, 0, 0, 0)
        layout_doc.addWidget(_linea_divisoria())
        # "Documentación del profesional" (antes "...seleccionado") — pedido
        # explícito de la clienta, así entra en una sola línea sin wrapear.
        titulo_doc = QLabel("Documentación del profesional")
        titulo_doc.setObjectName("subtituloSeccion")
        layout_doc.addWidget(titulo_doc)
        self.lista_documentos = QListWidget()
        self.lista_documentos.setFixedWidth(_ANCHO_CAMPO)
        # Alto fijo (no `stretch=1`) para ~5 líneas — el alto que esto le
        # saca al stretch de siempre se lo lleva el cuadro de Vista previa
        # nuevo, más abajo. Sigue scrolleando sola (default de Qt) si hay
        # más archivos de los que entran.
        self.lista_documentos.setFixedHeight(_ALTO_LISTA_DOCUMENTOS)
        self.lista_documentos.itemSelectionChanged.connect(self._actualizar_vista_previa)
        instalar_eliminar_con_tecla(self.lista_documentos, self._eliminar_documento)
        layout_doc.addWidget(self.lista_documentos)

        boton_agregar = QPushButton("Agregar archivo")
        boton_agregar.setObjectName("botonPrimario")
        boton_agregar.setFixedWidth(_ANCHO_CAMPO)
        boton_agregar.setStyleSheet(_ESTILO_BOTON_COMPACTO)
        boton_agregar.clicked.connect(self._agregar_documento)
        layout_doc.addWidget(boton_agregar)
        boton_eliminar = QPushButton("Eliminar archivo")
        boton_eliminar.setObjectName("botonSecundario")
        boton_eliminar.setFixedWidth(_ANCHO_CAMPO)
        boton_eliminar.setStyleSheet(_ESTILO_BOTON_COMPACTO)
        boton_eliminar.clicked.connect(self._eliminar_documento)
        layout_doc.addWidget(boton_eliminar)

        # Vista previa del archivo seleccionado en `lista_documentos` —
        # pedido explícito de la clienta, mismo mecanismo (imagen con
        # QPixmap directo, PDF con la primera página vía PyMuPDF) que ya
        # usan Gestor de archivos/Archivos para enviar — acá solo hace
        # falta cubrir PDF/JPG/PNG, las únicas extensiones que admite esta
        # documentación (ver `app.negocio.documentacion_profesional.
        # EXTENSIONES_VALIDAS`). Con `stretch=1`, este cuadro es el único
        # elemento que absorbe el alto de sobra del panel izquierdo
        # (mismo mecanismo que ya usaba `lista_documentos` antes de este
        # cambio) — llega hasta el pie del panel, a la par de la tabla de
        # la derecha.
        layout_doc.addWidget(_titulo_campo("Vista previa"))
        self.area_vista_previa = QScrollArea()
        self.area_vista_previa.setWidgetResizable(True)
        self.area_vista_previa.setStyleSheet("QScrollArea { border: 1px solid #000000; }")
        self.etiqueta_vista_previa = QLabel("Seleccioná un archivo para verlo acá.")
        self.etiqueta_vista_previa.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.etiqueta_vista_previa.setWordWrap(True)
        self.area_vista_previa.setWidget(self.etiqueta_vista_previa)
        layout_doc.addWidget(self.area_vista_previa, stretch=1)

        # panel_doc va debajo de Nuevo/Editar/Eliminar en el panel izquierdo
        # de PantallaCRUD (formato solapa, mismo criterio que todo catálogo
        # a partir de ahora) — sus botones referencian self.crud_profesionales
        # por método atado (_agregar_documento/_eliminar_documento), así que
        # alcanza con que exista para cuando se hagan clic, no ya en este punto.
        conn = self.conn
        self.crud_profesionales = PantallaCRUD(
            self.conn, "Profesional", "Profesionales", _campos_profesional(self.conn),
            # `al_guardar` (a diferencia de al_actualizar/al_crear) no se
            # envuelve en referencia débil — se cierra sobre `conn`, la
            # variable local, no sobre `self`, para no armar un ciclo
            # entre el panel y su propio PantallaCRUD.
            al_guardar=lambda valores, registro: _al_guardar_profesional(valores, registro, conn),
            al_actualizar=self._al_actualizar_profesional,
            al_abrir_dialogo=_al_abrir_dialogo,
            panel_extra_izquierda=panel_doc,
            etiqueta_buscar="Buscar profesional",
            anidado=True,
            # Solo en el diálogo Nuevo/Editar — pedido explícito de la
            # clienta: Categoría al principio, arriba de Código. La
            # tabla/listado sigue mostrando las columnas en el orden de
            # siempre ("Código - Tratamiento - Nombre - Apellido...").
            campos_primero_dialogo=["CategoriaProfesional"],
        )
        # Mismo achicado que los dos botones propios de arriba, acá sobre
        # los tres botones genéricos del CRUD (Nuevo/Editar/Eliminar).
        for boton in (
            self.crud_profesionales.boton_nuevo,
            self.crud_profesionales.boton_editar,
            self.crud_profesionales.boton_eliminar,
        ):
            boton.setStyleSheet(_ESTILO_BOTON_COMPACTO)
        self.crud_profesionales.tabla_widget.itemSelectionChanged.connect(self._actualizar_documentacion)
        layout.addWidget(self.crud_profesionales, stretch=1)

    def _al_actualizar_profesional(self, registro_anterior: sqlite3.Row, valores_nuevos: dict) -> None:
        try:
            aplicar_cambio_codigo(self.conn, registro_anterior, valores_nuevos, fecha_actual(self.conn))
        except OSError as error:
            QMessageBox.warning(
                self, "Cambio de código",
                f"Se registró el cambio de código, pero no se pudo renombrar la carpeta en disco: {error}",
            )
        self._actualizar_documentacion()

    def _codigo_seleccionado(self) -> str | None:
        id_valor = self.crud_profesionales.fila_seleccionada_id()
        if id_valor is None:
            return None
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(id_valor)
        return profesional["IdCodigo"] if profesional else None

    def _actualizar_documentacion(self) -> None:
        self.lista_documentos.clear()
        codigo = self._codigo_seleccionado()
        if codigo:
            try:
                for ruta in listar_documentos(self.conn, codigo):
                    item = QListWidgetItem(ruta.name)
                    item.setData(Qt.ItemDataRole.UserRole, str(ruta))
                    self.lista_documentos.addItem(item)
            except ValueError:
                pass  # sin carpeta base configurada todavía: lista vacía
        self._actualizar_vista_previa()

    def _actualizar_vista_previa(self) -> None:
        item = self.lista_documentos.currentItem()
        if item is None:
            self._mostrar_vista_previa_texto("Seleccioná un archivo para verlo acá.")
            return
        ruta = item.data(Qt.ItemDataRole.UserRole)
        ruta_minuscula = (ruta or "").lower()
        if ruta_minuscula.endswith((".jpg", ".jpeg", ".png")):
            pixmap = QPixmap(ruta)
            if not pixmap.isNull():
                self._mostrar_vista_previa_pixmap(pixmap)
                return
        elif ruta_minuscula.endswith(".pdf"):
            pixmap = _pixmap_primera_pagina_pdf(ruta)
            if pixmap is not None:
                self._mostrar_vista_previa_pixmap(pixmap)
                return
        self._mostrar_vista_previa_texto("No hay vista disponible.")

    def _mostrar_vista_previa_texto(self, texto: str) -> None:
        self.etiqueta_vista_previa.setMinimumSize(0, 0)
        self.etiqueta_vista_previa.setPixmap(QPixmap())
        self.etiqueta_vista_previa.setText(texto)

    def _mostrar_vista_previa_pixmap(self, pixmap: QPixmap) -> None:
        ancho_disponible = self.area_vista_previa.viewport().width() - 4
        if ancho_disponible > 0 and pixmap.width() > ancho_disponible:
            pixmap = pixmap.scaledToWidth(ancho_disponible, Qt.TransformationMode.SmoothTransformation)
        self.etiqueta_vista_previa.setText("")
        self.etiqueta_vista_previa.setPixmap(pixmap)
        # Mismo motivo que Archivos para enviar: sin esto, el QScrollArea
        # (widgetResizable=True) achica la etiqueta al alto del viewport y
        # la imagen queda recortada en vez de poder bajarla con la barra.
        self.etiqueta_vista_previa.setMinimumSize(pixmap.size())

    def _agregar_documento(self) -> None:
        codigo = self._codigo_seleccionado()
        if not codigo:
            QMessageBox.information(self, "Documentación", "Seleccioná un profesional con código cargado.")
            return
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegir documentación", "", "PDF e imágenes (*.pdf *.jpg *.jpeg *.png)")
        if not ruta:
            return
        dialogo = _DialogoCategoriaDocumento(parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            agregar_documento(self.conn, codigo, ruta, dialogo.categoria(), dialogo.etiqueta_libre())
        except ValueError as error:
            QMessageBox.warning(self, "Documentación", str(error))
            return
        self._actualizar_documentacion()

    def _eliminar_documento(self) -> None:
        codigo = self._codigo_seleccionado()
        item = self.lista_documentos.currentItem()
        if not codigo or item is None:
            QMessageBox.information(self, "Documentación", "Seleccioná un archivo de la lista.")
            return
        confirmacion = QMessageBox.question(self, "Documentación", f"¿Confirmás eliminar «{item.text()}»?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        eliminar_documento(self.conn, codigo, item.text())
        self._actualizar_documentacion()


class PantallaProfesionales(QWidget):
    """Contenedor de afuera del formulario "Profesionales" (reordenamiento
    de formularios, Excel de la clienta): título Nivel 1 fijo + las dos
    solapas, "Listado de profesionales" (`_PanelProfesionales`, arriba en
    este mismo archivo) y "Profesiones y tratamientos" (el catálogo
    `Profesion` de `catalogos.py`, anidado)."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Profesionales".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        self.pestanas = QTabWidget()
        self.panel_profesionales = _PanelProfesionales(conn)
        self.pestanas.addTab(self.panel_profesionales, "Listado de profesionales")
        self.panel_profesiones = catalogos.pantalla_profesiones(conn, anidado=True)
        self.pestanas.addTab(self.panel_profesiones, "Profesiones y tratamientos")
        self.pestanas.tabBar().setDrawBase(False)
        layout.addWidget(self.pestanas, stretch=1)
