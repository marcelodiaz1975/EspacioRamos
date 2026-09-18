"""Pantalla de Profesionales (F06/F07, sección 3.4) sobre PantallaCRUD, con
un panel de documentación (archivos sueltos en Profesionales/{código}/
Documentación) para el profesional seleccionado — va debajo de Nuevo/
Editar/Eliminar en el panel izquierdo (`panel_extra_izquierda` de
PantallaCRUD), mismo formato solapa que el resto de los catálogos."""
from __future__ import annotations

import sqlite3

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
    QVBoxLayout,
    QWidget,
)

from app.gui.crud_generico import Campo, PantallaCRUD, campos_libres
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
from app.negocio.profesionales import normalizar_cuit, opciones_tratamiento, sugerir_codigo, tratamiento_sugerido
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


def _opciones_profesion(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdProfesion, Nombre FROM Profesion ORDER BY Nombre").fetchall()
    return [(f["IdProfesion"], f["Nombre"]) for f in filas]


def _opciones_profesional(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido").fetchall()
    return [(f["IdProfesional"], f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", ")) for f in filas]


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
        Campo(
            "FechaNacimiento", "Fecha de nacimiento (AAAA-MM-DD)",
            validador=es_fecha_valida, formato_esperado=FORMATO_FECHA,
        ),
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
        Campo("ProfesionalCabezaEquipo", "Cabeza de equipo", tipo="combo", opciones=_opciones_profesional),
        Campo("SaldoCuentaActual", "Saldo cuenta actual", tipo="numero"),
        Campo("SaldoCuentaAnterior", "Saldo cuenta anterior", tipo="numero"),
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
    Psicopedagogía) sin perder el valor ya cargado. Cada campo se
    recalcula mientras el operador no haya tocado ese campo a mano (se
    compara contra la última sugerencia, no contra "vacío", para no pisar
    un valor que sí escribieron o que ya traía el registro); ambos quedan
    editables antes de confirmar."""
    conn = dialogo.conn
    combo_categoria = dialogo._entradas["CategoriaProfesional"]
    campo_codigo = dialogo._entradas["IdCodigo"]
    combo_profesion = dialogo._entradas["IdProfesion"]
    combo_sexo = dialogo._entradas["Sexo"]
    combo_tratamiento = dialogo._entradas["Tratamiento"]

    ultimo_codigo_sugerido = [None]

    def _actualizar_codigo() -> None:
        categoria = combo_categoria.currentData()
        if categoria is None:
            return
        sugerido = sugerir_codigo(conn, categoria)
        actual = campo_codigo.text().strip()
        if actual in ("", ultimo_codigo_sugerido[0]):
            campo_codigo.setText(sugerido)
            ultimo_codigo_sugerido[0] = sugerido

    ultimo_tratamiento_sugerido = [None]

    def _actualizar_tratamiento() -> None:
        id_profesion = combo_profesion.currentData()
        sexo = combo_sexo.currentData()
        opciones = opciones_tratamiento(conn, id_profesion, sexo)
        sugerido = tratamiento_sugerido(conn, id_profesion, sexo)
        actual = combo_tratamiento.currentText().strip()

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


class PantallaProfesionales(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        panel_doc = QWidget()
        layout_doc = QVBoxLayout(panel_doc)
        layout_doc.setContentsMargins(0, 0, 0, 0)
        layout_doc.addWidget(_linea_divisoria())
        titulo_doc = QLabel("Documentación del profesional seleccionado")
        titulo_doc.setObjectName("subtituloSeccion")
        titulo_doc.setWordWrap(True)
        layout_doc.addWidget(titulo_doc)
        self.lista_documentos = QListWidget()
        self.lista_documentos.setFixedWidth(_ANCHO_CAMPO)
        self.lista_documentos.setMinimumHeight(150)
        layout_doc.addWidget(self.lista_documentos, stretch=1)

        boton_agregar = QPushButton("Agregar archivo")
        boton_agregar.setObjectName("botonPrimario")
        boton_agregar.setFixedWidth(_ANCHO_CAMPO)
        boton_agregar.clicked.connect(self._agregar_documento)
        layout_doc.addWidget(boton_agregar)
        boton_eliminar = QPushButton("Eliminar archivo")
        boton_eliminar.setObjectName("botonSecundario")
        boton_eliminar.setFixedWidth(_ANCHO_CAMPO)
        boton_eliminar.clicked.connect(self._eliminar_documento)
        layout_doc.addWidget(boton_eliminar)

        # panel_doc va debajo de Nuevo/Editar/Eliminar en el panel izquierdo
        # de PantallaCRUD (formato solapa, mismo criterio que todo catálogo
        # a partir de ahora) — sus botones referencian self.crud_profesionales
        # por método atado (_agregar_documento/_eliminar_documento), así que
        # alcanza con que exista para cuando se hagan clic, no ya en este punto.
        self.crud_profesionales = PantallaCRUD(
            self.conn, "Profesional", "Profesionales", _campos_profesional(self.conn),
            al_actualizar=self._al_actualizar_profesional,
            al_abrir_dialogo=_al_abrir_dialogo,
            panel_extra_izquierda=panel_doc,
            etiqueta_buscar="Buscar profesional",
        )
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
        if not codigo:
            return
        try:
            for ruta in listar_documentos(self.conn, codigo):
                self.lista_documentos.addItem(QListWidgetItem(ruta.name))
        except ValueError:
            pass  # sin carpeta base configurada todavía: lista vacía

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


def pantalla_profesionales(conn: sqlite3.Connection) -> PantallaProfesionales:
    return PantallaProfesionales(conn)
