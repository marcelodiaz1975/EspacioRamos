"""Gestor de archivos (FA4, sección 3.26), solapa "Archivos del espacio":
fotos y documentos de edificios, unidades y consultorios
(app.negocio.imagenes) que se muestran en Propuesta, Disponibilidad,
Liquidación y Oferta de consultorios.

Mismo formato que los catálogos (solapa "Archivos del espacio", filtros
a la izquierda, tabla escroleable a la derecha, botones debajo de los
filtros) aunque no usa `PantallaCRUD` porque no es un catálogo de
registros con un cuadro de diálogo: es un administrador de archivos por
alcance. El combo "Alcance" tiene un primer valor especial "Todos los
archivos" (lista completa, sin filtros, ordenada por nivel y
Descripción — ver `_TODOS`) y después los 5 niveles reales (Espacio/
Localidad/Edificio/Unidad/Consultorio — ver `app.negocio.imagenes.
ALCANCES`), que definen hasta qué nivel de la cadena Localidad →
Edificio → Unidad → Consultorio hace falta elegir un valor concreto:
los combos de nivel superior al elegido quedan deshabilitados
(`_al_cambiar_alcance`) — el que efectivamente determina qué archivos
se listan/agregan es el del nivel exacto del alcance elegido; los de
niveles inferiores solo acotan en cascada sus opciones (mismo criterio
de cascada que Aumentos y descuentos). No lleva campos libres: no es un
registro de catálogo, es una carpeta de archivos.

Justo debajo de Alcance va el combo "Tipo de archivo" (Imagen/
Documento, pedido de la clienta): filtra la tabla y decide qué lista de
categorías se ofrece al agregar (ver `app.negocio.imagenes.
categorias_por_alcance`) y con qué extensiones se abre el selector de
archivo.

El combo Localidad lista el catálogo `Localidad` (`catalogos.
pantalla_localidades`) completo, no solo las que ya tienen algún
Edificio cargado — se puede guardar un archivo de alcance Localidad
(ej. el logo de esa localidad) antes de cargar ningún edificio ahí.

Categoría, principal y descripción automática: ver el docstring de
`app.negocio.imagenes`. El cuadro "Agregar archivo" (`_DialogoAgregarArchivo`)
pide la categoría (combo cerrado, según alcance + tipo elegidos), un
campo de detalle libre — obligatorio solo para "Otras imágenes"/"Otros
documentos", únicas categorías sin nombre propio — y un check "Marcar
como principal". "Marcar como principal" también existe como botón
aparte en la lista, para promover un archivo ya cargado sin tener que
recargarlo.

Vista previa: imágenes con QPixmap directo; PDF renderizando la primera
página con PyMuPDF (opcional en tiempo de ejecución — si no está
instalado, cae al mensaje de "sin vista"); TXT mostrando las primeras
líneas como texto. Word (.doc/.docx) no tiene vista previa disponible
todavía — mismo mensaje "No hay vista disponible" que cualquier archivo
que no se pudo leer."""
from __future__ import annotations

import shutil
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.items_tabla import item_numero
from app.negocio.imagenes import (
    CATEGORIAS_CON_ETIQUETA_LIBRE,
    EXTENSIONES_DOCUMENTO,
    EXTENSIONES_IMAGEN,
    TIPOS_ARCHIVO,
    agregar_imagen,
    alternar_activo,
    categorias_por_alcance,
    eliminar_imagen,
    es_documento,
    es_imagen,
    imagenes_del_alcance,
    imagenes_todas,
    marcar_principal,
    reordenar,
)

_ANCHO_CAMPO = 240
_TODOS = "Todos los archivos"
_NIVEL_ALCANCE = {"Espacio": 0, "Localidad": 1, "Edificio": 2, "Unidad": 3, "Consultorio": 4}
_ALCANCES = [_TODOS, *_NIVEL_ALCANCE]
_PADDING_COLUMNA = 30  # mismo criterio que novedades._ajustar_columnas
_ANCHO_MINIMO_DESCRIPCION = 300  # la clienta pidió más aire acá en particular
_ANCHO_PREVISUALIZACION = 400
_LINEAS_PREVIEW_TXT = 12

_COLUMNAS_NORMAL = ["Orden", "Descripción", "Categoría", "Principal", "Activo"]
_COLUMNAS_TODOS = [
    "Alcance", "Localidad", "Edificio", "Unidad", "Consultorio", "Descripción", "Categoría", "Principal", "Activo",
]

_FILTRO_ARCHIVO = {
    "Imagen": "Imágenes (" + " ".join(f"*{ext}" for ext in EXTENSIONES_IMAGEN) + ")",
    "Documento": "Documentos (" + " ".join(f"*{ext}" for ext in EXTENSIONES_DOCUMENTO) + ")",
}


def _titulo_campo(texto: str) -> QLabel:
    """Jerarquía 3 (subtituloCampo): mismo criterio que el resto de las
    pantallas para los títulos que van arriba de un selector."""
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _ajustar_columnas(tabla: QTableWidget, indice_descripcion: int) -> None:
    """Mismo criterio que `novedades._ajustar_columnas`: más aire que el
    ancho justo de `resizeColumnsToContents`, con Descripción todavía
    más generosa — pedido puntual de la clienta al revisar esta pantalla.
    El ancho final de la tabla queda fijo a la suma de sus columnas (sin
    stretch) para que no quede un espacio en blanco antes del panel de
    vista previa, que es el que se estira y ocupa el resto del ancho."""
    tabla.resizeColumnsToContents()
    for columna in range(tabla.columnCount()):
        tabla.setColumnWidth(columna, tabla.columnWidth(columna) + _PADDING_COLUMNA)
    tabla.setColumnWidth(indice_descripcion, max(tabla.columnWidth(indice_descripcion), _ANCHO_MINIMO_DESCRIPCION))
    ancho_total = tabla.verticalHeader().width() + tabla.horizontalHeader().length() + 2 * tabla.frameWidth() + 4
    tabla.setFixedWidth(ancho_total)


def _pixmap_primera_pagina_pdf(ruta: str) -> QPixmap | None:
    """Miniatura de la primera página de un PDF con PyMuPDF — es una
    dependencia opcional en tiempo de ejecución: si no está instalada o
    el archivo no se puede abrir, no hay vista previa (no rompe la
    pantalla)."""
    try:
        import fitz
    except ImportError:
        return None
    try:
        with fitz.open(ruta) as documento:
            pagina = documento[0]
            mapa_pixeles = pagina.get_pixmap(matrix=fitz.Matrix(0.6, 0.6))
        formato = QImage.Format.Format_RGBA8888 if mapa_pixeles.alpha else QImage.Format.Format_RGB888
        imagen = QImage(mapa_pixeles.samples, mapa_pixeles.width, mapa_pixeles.height, mapa_pixeles.stride, formato)
        return QPixmap.fromImage(imagen.copy())
    except Exception:
        return None


def _texto_primeras_lineas(ruta: str) -> str | None:
    try:
        with open(ruta, encoding="utf-8", errors="replace") as archivo:
            lineas = [next(archivo) for _ in range(_LINEAS_PREVIEW_TXT)]
    except StopIteration:
        pass
    except OSError:
        return None
    else:
        return "".join(lineas)
    try:
        with open(ruta, encoding="utf-8", errors="replace") as archivo:
            return archivo.read()
    except OSError:
        return None


class _DialogoAgregarArchivo(QDialog):
    """Categoría (según alcance + tipo elegidos), un detalle libre
    (obligatorio solo para "Otras imágenes"/"Otros documentos" — las
    únicas categorías sin nombre propio) y "Marcar como principal" — la
    Descripción se arma sola a partir de Alcance + Categoría [+ detalle]
    + Orden, no se pide acá."""

    def __init__(self, categorias: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar archivo")
        layout = QVBoxLayout(self)

        layout.addWidget(_titulo_campo("Categoría"))
        self.combo_categoria = QComboBox()
        self.combo_categoria.addItems(categorias)
        self.combo_categoria.currentTextChanged.connect(self._actualizar_visibilidad_detalle)
        layout.addWidget(self.combo_categoria)

        self.etiqueta_detalle = _titulo_campo("Detalle (para identificarlo)")
        layout.addWidget(self.etiqueta_detalle)
        self.campo_detalle = QLineEdit()
        layout.addWidget(self.campo_detalle)

        self.check_principal = QCheckBox("Marcar como principal")
        layout.addWidget(self.check_principal)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        self._actualizar_visibilidad_detalle(self.combo_categoria.currentText())

    def _actualizar_visibilidad_detalle(self, categoria: str) -> None:
        requiere_detalle = categoria in CATEGORIAS_CON_ETIQUETA_LIBRE
        self.etiqueta_detalle.setVisible(requiere_detalle)
        self.campo_detalle.setVisible(requiere_detalle)

    def _validar_y_aceptar(self) -> None:
        if self.combo_categoria.currentText() in CATEGORIAS_CON_ETIQUETA_LIBRE and not self.campo_detalle.text().strip():
            QMessageBox.warning(self, "Agregar archivo", "Ingresá un detalle para identificar este archivo.")
            self.campo_detalle.setFocus()
            return
        self.accept()

    def categoria(self) -> str:
        return self.combo_categoria.currentText()

    def etiqueta_libre(self) -> str | None:
        return self.campo_detalle.text().strip() or None

    def principal(self) -> bool:
        return self.check_principal.isChecked()


class PantallaImagenes(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._imagenes: list[sqlite3.Row] = []
        self._armar_ui()
        self._cargar_combo_localidad()
        self._al_cambiar_alcance()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Gestor de archivos")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        solapas = QTabWidget()
        panel_solapa = QWidget()
        panel_solapa.setObjectName("panelSolapa")
        layout_solapa = QHBoxLayout(panel_solapa)

        panel_izquierda = QWidget()
        form = QVBoxLayout(panel_izquierda)

        form.addWidget(_titulo_campo("Alcance"))
        self.combo_alcance = QComboBox()
        self.combo_alcance.addItems(_ALCANCES)
        self.combo_alcance.setFixedWidth(_ANCHO_CAMPO)
        self.combo_alcance.currentIndexChanged.connect(self._al_cambiar_alcance)
        form.addWidget(self.combo_alcance)

        form.addWidget(_titulo_campo("Tipo de archivo"))
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(TIPOS_ARCHIVO)
        self.combo_tipo.setFixedWidth(_ANCHO_CAMPO)
        self.combo_tipo.currentIndexChanged.connect(self.actualizar)
        form.addWidget(self.combo_tipo)

        form.addWidget(_titulo_campo("Localidad"))
        self.combo_localidad = QComboBox()
        self.combo_localidad.setFixedWidth(_ANCHO_CAMPO)
        self.combo_localidad.currentIndexChanged.connect(self._cargar_combo_edificio)
        form.addWidget(self.combo_localidad)

        form.addWidget(_titulo_campo("Edificio"))
        self.combo_edificio = QComboBox()
        self.combo_edificio.setFixedWidth(_ANCHO_CAMPO)
        self.combo_edificio.currentIndexChanged.connect(self._cargar_combo_unidad)
        form.addWidget(self.combo_edificio)

        form.addWidget(_titulo_campo("Unidad"))
        self.combo_unidad = QComboBox()
        self.combo_unidad.setFixedWidth(_ANCHO_CAMPO)
        self.combo_unidad.currentIndexChanged.connect(self._cargar_combo_consultorio)
        form.addWidget(self.combo_unidad)

        form.addWidget(_titulo_campo("Consultorio"))
        self.combo_consultorio = QComboBox()
        self.combo_consultorio.setFixedWidth(_ANCHO_CAMPO)
        self.combo_consultorio.currentIndexChanged.connect(self.actualizar)
        form.addWidget(self.combo_consultorio)

        form.addWidget(_linea_divisoria())

        self.boton_agregar = QPushButton("Agregar archivo")
        self.boton_agregar.setObjectName("botonPrimario")
        self.boton_agregar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_agregar.clicked.connect(self._agregar)
        form.addWidget(self.boton_agregar)

        self.boton_principal = QPushButton("Marcar como principal")
        self.boton_principal.setObjectName("botonSecundario")
        self.boton_principal.setFixedWidth(_ANCHO_CAMPO)
        self.boton_principal.clicked.connect(self._marcar_principal)
        form.addWidget(self.boton_principal)

        self.boton_subir = QPushButton("Subir")
        self.boton_subir.setObjectName("botonSecundario")
        self.boton_subir.setFixedWidth(_ANCHO_CAMPO)
        self.boton_subir.clicked.connect(lambda: self._reordenar(-1))
        form.addWidget(self.boton_subir)

        self.boton_bajar = QPushButton("Bajar")
        self.boton_bajar.setObjectName("botonSecundario")
        self.boton_bajar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_bajar.clicked.connect(lambda: self._reordenar(1))
        form.addWidget(self.boton_bajar)

        self.boton_activo = QPushButton("Activar/Desactivar")
        self.boton_activo.setObjectName("botonSecundario")
        self.boton_activo.setFixedWidth(_ANCHO_CAMPO)
        self.boton_activo.clicked.connect(self._alternar_activo)
        form.addWidget(self.boton_activo)

        self.boton_descargar = QPushButton("Descargar")
        self.boton_descargar.setObjectName("botonSecundario")
        self.boton_descargar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_descargar.clicked.connect(self._descargar)
        form.addWidget(self.boton_descargar)

        self.boton_eliminar = QPushButton("Eliminar")
        self.boton_eliminar.setObjectName("botonSecundario")
        self.boton_eliminar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_eliminar.clicked.connect(self._eliminar)
        form.addWidget(self.boton_eliminar)

        form.addStretch()
        layout_solapa.addWidget(panel_izquierda)

        self.tabla = QTableWidget()
        self._configurar_columnas(es_todos=True)  # "Todos los archivos" es la primera opción del combo Alcance
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.itemSelectionChanged.connect(self._actualizar_previsualizacion)
        layout_solapa.addWidget(self.tabla)

        panel_preview = QWidget()
        layout_preview = QVBoxLayout(panel_preview)
        layout_preview.addWidget(_titulo_campo("Vista previa"))
        self.etiqueta_preview = QLabel("Seleccioná un archivo para verlo acá.")
        self.etiqueta_preview.setObjectName("previsualizacionImagen")
        self.etiqueta_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.etiqueta_preview.setWordWrap(True)
        self.etiqueta_preview.setFixedSize(_ANCHO_PREVISUALIZACION, _ANCHO_PREVISUALIZACION)
        self.etiqueta_preview.setStyleSheet("border: 1px solid #000000;")
        layout_preview.addWidget(self.etiqueta_preview)
        layout_preview.addStretch()
        layout_solapa.addWidget(panel_preview, stretch=1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel_solapa)
        solapas.addTab(scroll, "Archivos del espacio")
        layout.addWidget(solapas, stretch=1)

    def _al_cambiar_alcance(self, *_args) -> None:
        alcance = self.combo_alcance.currentText()
        es_todos = alcance == _TODOS
        nivel = _NIVEL_ALCANCE.get(alcance, -1)
        self.combo_localidad.setEnabled(not es_todos and nivel >= 1)
        self.combo_edificio.setEnabled(not es_todos and nivel >= 2)
        self.combo_unidad.setEnabled(not es_todos and nivel >= 3)
        self.combo_consultorio.setEnabled(not es_todos and nivel >= 4)
        self.boton_agregar.setEnabled(not es_todos)
        self.boton_principal.setEnabled(not es_todos)
        self.boton_subir.setEnabled(not es_todos)
        self.boton_bajar.setEnabled(not es_todos)
        self._configurar_columnas(es_todos)
        self.actualizar()

    def _configurar_columnas(self, es_todos: bool) -> None:
        columnas = _COLUMNAS_TODOS if es_todos else _COLUMNAS_NORMAL
        self.tabla.setColumnCount(len(columnas))
        self.tabla.setHorizontalHeaderLabels(columnas)

    def _cargar_combo_localidad(self) -> None:
        self.combo_localidad.blockSignals(True)
        self.combo_localidad.clear()
        filas = self.conn.execute("SELECT IdLocalidad, Localidad FROM Localidad ORDER BY Localidad").fetchall()
        for f in filas:
            self.combo_localidad.addItem(f["Localidad"], f["IdLocalidad"])
        self.combo_localidad.blockSignals(False)
        self._cargar_combo_edificio()

    def _cargar_combo_edificio(self) -> None:
        self.combo_edificio.blockSignals(True)
        self.combo_edificio.clear()
        id_localidad = self.combo_localidad.currentData()
        sql = "SELECT IdEdificio, Nombre FROM Edificio"
        parametros: list = []
        if id_localidad is not None:
            sql += " WHERE IdLocalidad = ?"
            parametros.append(id_localidad)
        sql += " ORDER BY Nombre"
        for f in self.conn.execute(sql, parametros).fetchall():
            self.combo_edificio.addItem(f["Nombre"], f["IdEdificio"])
        self.combo_edificio.blockSignals(False)
        self._cargar_combo_unidad()

    def _cargar_combo_unidad(self) -> None:
        self.combo_unidad.blockSignals(True)
        self.combo_unidad.clear()
        id_edificio = self.combo_edificio.currentData()
        sql = "SELECT IdUnidad, Departamento FROM Unidad"
        parametros: list = []
        if id_edificio is not None:
            sql += " WHERE IdEdificio = ?"
            parametros.append(id_edificio)
        sql += " ORDER BY Departamento"
        for f in self.conn.execute(sql, parametros).fetchall():
            self.combo_unidad.addItem(f["Departamento"], f["IdUnidad"])
        self.combo_unidad.blockSignals(False)
        self._cargar_combo_consultorio()

    def _cargar_combo_consultorio(self) -> None:
        self.combo_consultorio.blockSignals(True)
        self.combo_consultorio.clear()
        id_unidad = self.combo_unidad.currentData()
        sql = "SELECT IdConsultorio, NumeroConsultorio FROM Consultorio"
        parametros: list = []
        if id_unidad is not None:
            sql += " WHERE IdUnidad = ?"
            parametros.append(id_unidad)
        sql += " ORDER BY NumeroConsultorio"
        for f in self.conn.execute(sql, parametros).fetchall():
            self.combo_consultorio.addItem(str(f["NumeroConsultorio"]), f["IdConsultorio"])
        self.combo_consultorio.blockSignals(False)
        self.actualizar()

    def _parametros_alcance(self) -> dict:
        """El valor efectivo de alcance para consultar/guardar es el del
        combo en el nivel exacto elegido — los combos de niveles
        inferiores solo sirven para acotar en cascada las opciones de
        ese combo, no se pasan además."""
        alcance = self.combo_alcance.currentText()
        if alcance == "Espacio":
            return {}
        if alcance == "Localidad":
            return {"id_localidad": self.combo_localidad.currentData()}
        if alcance == "Edificio":
            return {"id_edificio": self.combo_edificio.currentData()}
        if alcance == "Unidad":
            return {"id_unidad": self.combo_unidad.currentData()}
        return {"id_consultorio": self.combo_consultorio.currentData()}

    def _filtrar_por_tipo(self, filas: list[sqlite3.Row]) -> list[sqlite3.Row]:
        comprobar = es_imagen if self.combo_tipo.currentText() == "Imagen" else es_documento
        return [f for f in filas if f["RutaArchivo"] and comprobar(f["RutaArchivo"])]

    def actualizar(self, *_args) -> None:
        alcance = self.combo_alcance.currentText()
        if alcance == _TODOS:
            self._imagenes = self._filtrar_por_tipo(imagenes_todas(self.conn))
            self._llenar_tabla_todos()
        else:
            parametros = self._parametros_alcance()
            if any(valor is None for valor in parametros.values()):
                self._imagenes = []
            else:
                self._imagenes = self._filtrar_por_tipo(imagenes_del_alcance(self.conn, **parametros))
            self._llenar_tabla_normal()
        self._actualizar_previsualizacion()

    def _llenar_tabla_normal(self) -> None:
        self.tabla.setRowCount(len(self._imagenes))
        for fila_idx, img in enumerate(self._imagenes):
            self.tabla.setItem(fila_idx, 0, item_numero(str(img["NumeroOrden"])))
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(img["Descripcion"] or ""))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(img["Tipo"] or ""))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem("Sí" if img["NumeroOrden"] == 1 else "No"))
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem("Sí" if img["Activo"] else "No"))
        _ajustar_columnas(self.tabla, indice_descripcion=1)

    def _llenar_tabla_todos(self) -> None:
        self.tabla.setRowCount(len(self._imagenes))
        for fila_idx, img in enumerate(self._imagenes):
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(img["Alcance"]))
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(img["LocalidadTexto"] or ""))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(img["EdificioTexto"] or ""))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(img["UnidadTexto"] or ""))
            self.tabla.setItem(
                fila_idx, 4, item_numero(str(img["ConsultorioNumero"])) if img["ConsultorioNumero"] else QTableWidgetItem(""),
            )
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem(img["Descripcion"] or ""))
            self.tabla.setItem(fila_idx, 6, QTableWidgetItem(img["Tipo"] or ""))
            self.tabla.setItem(fila_idx, 7, QTableWidgetItem("Sí" if img["NumeroOrden"] == 1 else "No"))
            self.tabla.setItem(fila_idx, 8, QTableWidgetItem("Sí" if img["Activo"] else "No"))
        _ajustar_columnas(self.tabla, indice_descripcion=5)

    def _actualizar_previsualizacion(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            self._mostrar_preview_texto("Seleccioná un archivo para verlo acá.")
            return
        img = self._imagenes[filas[0].row()]
        ruta = img["RutaArchivo"]
        if not ruta:
            self._mostrar_preview_texto("No hay vista disponible.")
            return
        if es_imagen(ruta):
            pixmap = QPixmap(ruta)
            if pixmap.isNull():
                self._mostrar_preview_texto("No hay vista disponible.")
                return
            self._mostrar_preview_pixmap(pixmap)
            return
        if ruta.lower().endswith(".pdf"):
            pixmap = _pixmap_primera_pagina_pdf(ruta)
            if pixmap is not None:
                self._mostrar_preview_pixmap(pixmap)
                return
            self._mostrar_preview_texto("No hay vista disponible.")
            return
        if ruta.lower().endswith(".txt"):
            texto = _texto_primeras_lineas(ruta)
            self._mostrar_preview_texto(texto if texto else "No hay vista disponible.")
            return
        self._mostrar_preview_texto("No hay vista disponible.")

    def _mostrar_preview_texto(self, texto: str) -> None:
        self.etiqueta_preview.setPixmap(QPixmap())
        self.etiqueta_preview.setText(texto)

    def _mostrar_preview_pixmap(self, pixmap: QPixmap) -> None:
        self.etiqueta_preview.setText("")
        self.etiqueta_preview.setPixmap(
            pixmap.scaled(
                self.etiqueta_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _imagen_seleccionada(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            QMessageBox.information(self, "Gestor de archivos", "Seleccioná un archivo de la lista.")
            return None
        return self._imagenes[filas[0].row()]

    def _agregar(self) -> None:
        parametros = self._parametros_alcance()
        if any(valor is None for valor in parametros.values()):
            QMessageBox.warning(self, "Gestor de archivos", "No hay ningún registro cargado para este alcance.")
            return
        tipo = self.combo_tipo.currentText()
        categorias = categorias_por_alcance(self.combo_alcance.currentText(), tipo)
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegir archivo", "", _FILTRO_ARCHIVO[tipo])
        if not ruta:
            return
        dialogo = _DialogoAgregarArchivo(categorias, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            agregar_imagen(
                self.conn, ruta_origen=ruta, categoria=dialogo.categoria(), etiqueta_libre=dialogo.etiqueta_libre(),
                principal=dialogo.principal(), **parametros,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Gestor de archivos", str(error))
            return
        self.conn.commit()
        self.actualizar()

    def _marcar_principal(self) -> None:
        img = self._imagen_seleccionada()
        if img is None:
            return
        marcar_principal(self.conn, img["IdImagen"])
        self.conn.commit()
        self.actualizar()

    def _reordenar(self, delta: int) -> None:
        img = self._imagen_seleccionada()
        if img is None:
            return
        reordenar(self.conn, img["IdImagen"], delta)
        self.conn.commit()
        self.actualizar()

    def _alternar_activo(self) -> None:
        img = self._imagen_seleccionada()
        if img is None:
            return
        alternar_activo(self.conn, img["IdImagen"])
        self.conn.commit()
        self.actualizar()

    def _descargar(self) -> None:
        img = self._imagen_seleccionada()
        if img is None:
            return
        if not img["RutaArchivo"]:
            QMessageBox.warning(self, "Gestor de archivos", "Este archivo no tiene un archivo asociado.")
            return
        nombre_sugerido = img["Descripcion"] or "archivo"
        extension = "." + img["RutaArchivo"].rsplit(".", 1)[-1] if "." in img["RutaArchivo"] else ""
        destino, _ = QFileDialog.getSaveFileName(self, "Descargar archivo", f"{nombre_sugerido}{extension}")
        if not destino:
            return
        try:
            shutil.copy2(img["RutaArchivo"], destino)
        except OSError as error:
            QMessageBox.warning(self, "Gestor de archivos", f"No se pudo descargar el archivo: {error}")

    def _eliminar(self) -> None:
        img = self._imagen_seleccionada()
        if img is None:
            return
        confirmacion = QMessageBox.question(self, "Eliminar archivo", "¿Confirmás eliminar el archivo seleccionado?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        eliminar_imagen(self.conn, img["IdImagen"])
        self.conn.commit()
        self.actualizar()
