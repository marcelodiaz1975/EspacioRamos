"""Gestor de archivos (FA4, sección 3.26), solapa "Archivos del espacio":
fotos y documentos de edificios, unidades y consultorios
(app.negocio.imagenes) que se muestran en Propuesta, Disponibilidad,
Liquidación y Oferta de consultorios.

Layout en dos filas (pedido explícito de la clienta, reemplaza al
formato "filtros a la izquierda, tabla al medio, vista previa a la
derecha" de antes): arriba, tres columnas de igual alto —
filtros/Alcance (primera), botones de acción (segunda, de "Agregar
archivo" a "Manual del usuario") y Vista previa (tercera, la única con
`stretch=1`); abajo, la tabla ocupando todo el ancho disponible (ver
`_ajustar_columnas` para cómo reparte ese ancho entre sus columnas). No
usa `PantallaCRUD` porque no es un catálogo de registros con un cuadro
de diálogo: es un administrador de archivos por alcance. El combo "Alcance" tiene un primer valor especial "Todos los
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
Documento/Enlace, pedido de la clienta): filtra la tabla y decide qué
lista de categorías se ofrece al agregar (ver `app.negocio.imagenes.
categorias_por_alcance`) y, para Imagen/Documento, con qué extensiones
se abre el selector de archivo.

"Enlace" (pedido de la clienta: guardar links de YouTube con el
recorrido en video de una unidad/consultorio en particular, que después
pega por WhatsApp al interesado) no abre ningún selector de archivo —
`_agregar` le pide la URL directo dentro de `_DialogoAgregarArchivo`
(`pedir_url=True`, un campo de texto adicional arriba de Categoría) y la
guarda con `app.negocio.imagenes.agregar_enlace`. Como un enlace no
tiene archivo que "Descargar" ni vista previa de imagen/PDF/texto, el
botón "Descargar" pasa a "Copiar enlace" (copia la URL al portapapeles,
lista para pegar en WhatsApp — la única acción que la clienta pidió
para esto, sin sumar un "Abrir enlace" aparte) cuando el "Tipo de
archivo" elegido es Enlace, y la Vista previa muestra la URL como
texto en vez de intentar renderizar nada.

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
que no se pudo leer.

Reordenamiento de formularios (Excel de la clienta): dejó de ser una
pantalla propia del menú y pasó a ser la solapa "Gestor de archivos del
espacio" del formulario "Archivos y listas" (`_PanelGestorArchivos`,
junto a Listas editables/Condiciones y normas/Detalles complementarios
de la propuesta — ver `catalogos.py`). Por eso ya no tiene título Nivel
1 propio. Mantiene su `QScrollArea` interno (mismo criterio que
`_PanelCampos` de Configuración general: el `objectName="panelSolapa"`
va en el widget de más afuera — el que se pasa a `addTab(...)` — aunque
el contenido scrollee adentro).

De paso (misma reorganización) suma el botón "Manual del usuario",
reubicado acá desde la vieja pantalla "Archivos varios" (ahora la solapa
"Archivos para enviar" de "Disponibilidad" — ver `archivos_varios.py`):
va después de "Eliminar", con una línea divisoria propia arriba, como
`botonPrimario` (pedido explícito de la clienta) — a diferencia de los
otros botones de este panel, que actúan sobre el archivo SELECCIONADO en
la tabla, este no depende de ninguna selección: siempre regenera el PDF
del manual contra el estado actual del sistema (mismo generador que
usaba "Archivos varios", `app.pdf.manual_pdf.generar_pdf_manual`, que
necesita la lista de `Seccion` del menú para armar la ayuda contextual —
por eso `_PanelGestorArchivos` ahora recibe `secciones` opcional,
reenviado desde `PantallaArchivosYListas`)."""
from __future__ import annotations

import shutil
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
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
    QVBoxLayout,
    QWidget,
)

from app.gui.main_window import Seccion
from app.gui.widgets.eliminar_tecla import instalar_eliminar_con_tecla
from app.gui.widgets.foco import excluir_tabla_del_tab, instalar_enter_avanza_foco
from app.gui.widgets.items_tabla import item_centrado, item_numero
from app.negocio.archivos_generados import SUBCARPETA_MANUAL, carpeta_archivos_varios
from app.negocio.imagenes import (
    CATEGORIAS_CON_ETIQUETA_LIBRE,
    EXTENSIONES_DOCUMENTO,
    EXTENSIONES_IMAGEN,
    TIPOS_ARCHIVO,
    agregar_enlace,
    agregar_imagen,
    alternar_activo,
    categorias_por_alcance,
    eliminar_imagen,
    es_documento,
    es_enlace,
    es_imagen,
    imagenes_del_alcance,
    imagenes_todas,
    marcar_principal,
    reordenar,
)
from app.pdf.estilos import clave_orden_unidad
from app.pdf.manual_pdf import generar_pdf_manual

_ANCHO_CAMPO = 270  # pedido explícito de la clienta: "dale un poco más de ancho" a filtros/botones (antes 240)
_TODOS = "Todos los archivos"
_NIVEL_ALCANCE = {"Espacio": 0, "Localidad": 1, "Edificio": 2, "Unidad": 3, "Consultorio": 4}
_ALCANCES = [_TODOS, *_NIVEL_ALCANCE]
_PADDING_COLUMNA = 30  # mismo criterio que novedades._ajustar_columnas
_COLCHON_TITULO_COLUMNA = 12  # padding interno que Qt le suma a la celda del encabezado, ver _ajustar_columnas
# Piso de la Vista previa (pedido explícito de la clienta: ya no tiene
# tamaño fijo, se estira sola al ancho de su columna y al alto que deje
# libre filtros/botones — ver `_armar_ui`) — evita que quede
# degenerada si esa columna terminara más chica que esto.
_ANCHO_MINIMO_PREVISUALIZACION = 300
_ALTO_MINIMO_PREVISUALIZACION = 220
_LINEAS_PREVIEW_TXT = 12

_COLUMNAS_NORMAL = ["Orden", "Descripción", "Categoría", "Principal", "Activo"]
# "Consul" (no "Consultorio", pedido explícito de la clienta): ancho
# mínimo para que entre la etiqueta, mismo criterio que Categoría/
# Principal/Activo — ver `columnas_minimas` en `_llenar_tabla_todos`.
_COLUMNAS_TODOS = [
    "Alcance", "Localidad", "Edificio", "Unidad", "Consul", "Descripción", "Categoría", "Principal", "Activo",
]

_FILTRO_ARCHIVO = {
    "Imagen": "Imágenes (" + " ".join(f"*{ext}" for ext in EXTENSIONES_IMAGEN) + ")",
    "Documento": "Documentos (" + " ".join(f"*{ext}" for ext in EXTENSIONES_DOCUMENTO) + ")",
}

_COMPROBADOR_TIPO = {"Imagen": es_imagen, "Documento": es_documento, "Enlace": es_enlace}


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


def _ajustar_columnas(
    tabla: QTableWidget, indice_descripcion: int, columnas_minimas: frozenset[int] = frozenset(),
) -> None:
    """Mismo criterio que `novedades._ajustar_columnas`: más aire que el
    ancho justo de `resizeColumnsToContents` — con una excepción.

    `columnas_minimas` (puntos 25/27/30, SistemaDF v0.11.2026.10):
    "Orden"/"Categoría"/"Principal"/"Activo" (vista por alcance) o
    "Consul"/"Categoría"/"Principal"/"Activo" (vista "Todos los
    archivos") se quedan en el ancho justo de `resizeColumnsToContents`
    — sin el padding de las demás.

    `resizeColumnsToContents()` mide el ancho necesario por el CONTENIDO
    de las celdas, no por el título del encabezado — con una columna
    "mínima" cuyo contenido es corto ("Sí"/"No") pero cuyo título es más
    largo ("Categoría", en negrita, más ancho que esa misma palabra sin
    negrita), el título quedaba cortado. Se le suma a cada columna
    mínima un piso calculado a mano con `QFontMetrics` sobre la fuente
    REAL del encabezado (`tabla.horizontalHeader().font()`, ya con el
    peso que le da `estilos.py` vía `QHeaderView` aplicado) más un
    colchón chico (`_COLCHON_TITULO_COLUMNA`) para el padding interno
    que Qt le suma a la celda del encabezado.

    Pedido explícito de la clienta sobre esta ronda: la tabla pasa a
    vivir en su propia fila, ocupando todo el ancho disponible (ya no
    comparte fila con "Vista previa", que ahora vive arriba junto con
    los filtros y los botones) — así que el ancho que sobra después de
    que cada columna mida lo que necesita (`sobrante`, puede ser 0 si
    la ventana es angosta) se reparte en dos mitades: una mitad entera
    para "Descripción" ("la columna que puede tener más ancho"), la
    otra mitad repartida en partes iguales entre el resto de las
    columnas que NO están en `columnas_minimas` (esas se quedan siempre
    en su ancho mínimo, no participan del reparto) — si no queda
    ninguna otra columna así, "Descripción" se lleva el sobrante
    entero. Se vuelve a llamar sola cada vez que la tabla cambia de
    tamaño (`_TablaConAnchoDinamico.resizeEvent`), no solo al cargar
    datos nuevos — para que el reparto se recalcule si se redimensiona
    la ventana."""
    tabla.resizeColumnsToContents()
    metrica_encabezado = QFontMetrics(tabla.horizontalHeader().font())
    for columna in range(tabla.columnCount()):
        if columna in columnas_minimas:
            ancho_titulo = metrica_encabezado.horizontalAdvance(tabla.horizontalHeaderItem(columna).text())
            tabla.setColumnWidth(
                columna, max(tabla.columnWidth(columna), ancho_titulo + _COLCHON_TITULO_COLUMNA),
            )
            continue
        tabla.setColumnWidth(columna, tabla.columnWidth(columna) + _PADDING_COLUMNA)

    disponible = tabla.viewport().width()
    suma_natural = sum(tabla.columnWidth(c) for c in range(tabla.columnCount()))
    sobrante = disponible - suma_natural
    reparto = _repartir_sobrante(sobrante, indice_descripcion, tabla.columnCount(), columnas_minimas)
    for columna, extra in reparto.items():
        tabla.setColumnWidth(columna, tabla.columnWidth(columna) + extra)


def _repartir_sobrante(
    sobrante: int, indice_descripcion: int, cantidad_columnas: int, columnas_minimas: frozenset[int],
) -> dict[int, int]:
    """La mitad entera del `sobrante` (ancho disponible de la tabla menos
    la suma de los anchos naturales ya calculados) va para "Descripción"
    ("la columna que puede tener más ancho", pedido explícito de la
    clienta); la otra mitad se reparte en partes iguales (el residuo de
    la división, si no es exacta, para las primeras columnas) entre el
    resto de las columnas que no están en `columnas_minimas` — esas se
    quedan siempre en su ancho mínimo, no participan del reparto. Sin
    ninguna otra columna así, "Descripción" se lleva el sobrante entero.
    `sobrante <= 0` (la tabla ya no tiene más ancho disponible que el
    que sus columnas necesitan) no reparte nada — sin esto, "Descripción"
    no tendría ningún piso artificial propio, ni éste ni ningún otro.

    Separada de `_ajustar_columnas` (que sí depende de un `QTableWidget`
    real) para poder probar el reparto en sí, con números simples, sin
    necesitar una tabla de Qt."""
    if sobrante <= 0:
        return {}
    otras = [c for c in range(cantidad_columnas) if c not in columnas_minimas and c != indice_descripcion]
    if not otras:
        return {indice_descripcion: sobrante}
    para_descripcion = sobrante // 2
    resto = sobrante - para_descripcion
    reparto = {indice_descripcion: para_descripcion}
    por_columna, residuo = divmod(resto, len(otras))
    for i, columna in enumerate(otras):
        reparto[columna] = por_columna + (1 if i < residuo else 0)
    return reparto


class _TablaConAnchoDinamico(QTableWidget):
    """Notifica a `al_redimensionar` cada vez que cambia de tamaño —
    necesario para repartir el ancho sobrante entre sus columnas apenas
    se conoce el ancho real disponible (en la construcción, y de nuevo
    si la ventana se redimensiona), ver `_ajustar_columnas`. No alcanza
    con un `resizeEvent` del panel contenedor: el ancho final de ESTA
    tabla puede resolverse recién después, al terminar el layout."""

    def __init__(self, al_redimensionar, parent=None):
        super().__init__(parent)
        self._al_redimensionar = al_redimensionar

    def resizeEvent(self, evento) -> None:  # noqa: N802 (nombre impuesto por Qt)
        super().resizeEvent(evento)
        self._al_redimensionar()


class _EtiquetaConAnchoDinamico(QLabel):
    """Mismo motivo que `_TablaConAnchoDinamico`: la Vista previa ya no
    tiene un tamaño fijo (se estira sola, ver `_armar_ui`), así que la
    imagen/PDF que tenga cargada en ese momento hay que volver a
    escalarla cada vez que el label cambia de tamaño — si no, se queda
    con el tamaño de la última vez que se seleccionó un archivo."""

    def __init__(self, al_redimensionar, texto: str = "", parent=None):
        super().__init__(texto, parent)
        self._al_redimensionar = al_redimensionar

    def resizeEvent(self, evento) -> None:  # noqa: N802 (nombre impuesto por Qt)
        super().resizeEvent(evento)
        self._al_redimensionar()


def _pixmap_primera_pagina_pdf(ruta: str, escala: float = 0.6) -> QPixmap | None:
    """Miniatura de la primera página de un PDF con PyMuPDF — es una
    dependencia opcional en tiempo de ejecución: si no está instalada o
    el archivo no se puede abrir, no hay vista previa (no rompe la
    pantalla). `escala` default 0.6 (el tamaño de siempre acá); Archivos
    varios pide una escala mayor para que se vea más grande en su cuadro
    de vista previa, más ancho que el de esta pantalla."""
    try:
        import fitz
    except ImportError:
        return None
    try:
        with fitz.open(ruta) as documento:
            pagina = documento[0]
            mapa_pixeles = pagina.get_pixmap(matrix=fitz.Matrix(escala, escala))
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
    (obligatorio solo para "Otras imágenes"/"Otros documentos"/"Otros
    enlaces" — las únicas categorías sin nombre propio) y "Marcar como
    principal" — la Descripción se arma sola a partir de Alcance +
    Categoría [+ detalle] + Orden, no se pide acá.

    `pedir_url=True` (tipo "Enlace") suma un campo de texto para la URL
    arriba de Categoría — un enlace no pasa por ningún selector de
    archivo, se pide acá directo."""

    def __init__(self, categorias: list[str], *, pedir_url: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar enlace" if pedir_url else "Agregar archivo")
        layout = QVBoxLayout(self)

        self.campo_url: QLineEdit | None = None
        if pedir_url:
            layout.addWidget(_titulo_campo("Enlace (URL)"))
            self.campo_url = QLineEdit()
            layout.addWidget(self.campo_url)

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
        if self.campo_url is not None and not es_enlace(self.campo_url.text()):
            QMessageBox.warning(
                self, "Agregar enlace", "Ingresá un enlace válido (tiene que empezar con http:// o https://).",
            )
            self.campo_url.setFocus()
            return
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

    def url(self) -> str:
        return self.campo_url.text().strip() if self.campo_url is not None else ""


class _PanelGestorArchivos(QWidget):
    def __init__(self, conn: sqlite3.Connection, secciones: list[Seccion] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._secciones = secciones or []
        self._imagenes: list[sqlite3.Row] = []
        self._armar_ui()
        self._cargar_combo_localidad()
        self._al_cambiar_alcance()

    def _armar_ui(self) -> None:
        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        contenido = QWidget()
        contenido.setObjectName("panelSolapa")
        layout_contenido = QVBoxLayout(contenido)

        # Fila de arriba: tres columnas (filtros, botones de acción,
        # vista previa) de igual alto — `QHBoxLayout` ya estira sus
        # widgets hijos directos al alto de la fila (el más alto de los
        # tres) sin necesitar nada extra, así que alcanza con un
        # `addStretch()` propio al final de cada columna para que su
        # contenido quede arriba y no se reparta en el alto de sobra.
        fila_superior = QHBoxLayout()

        panel_filtros = QWidget()
        panel_filtros.setObjectName("panelSolapa")
        form = QVBoxLayout(panel_filtros)

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
        self.combo_tipo.currentIndexChanged.connect(self._al_cambiar_tipo)
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

        form.addStretch()
        fila_superior.addWidget(panel_filtros)

        panel_botones = QWidget()
        panel_botones.setObjectName("panelSolapa")
        columna_botones = QVBoxLayout(panel_botones)

        self.boton_agregar = QPushButton("Agregar archivo")
        self.boton_agregar.setObjectName("botonPrimario")
        self.boton_agregar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_agregar.clicked.connect(self._agregar)
        columna_botones.addWidget(self.boton_agregar)

        self.boton_principal = QPushButton("Marcar como principal")
        self.boton_principal.setObjectName("botonSecundario")
        self.boton_principal.setFixedWidth(_ANCHO_CAMPO)
        self.boton_principal.clicked.connect(self._marcar_principal)
        columna_botones.addWidget(self.boton_principal)

        self.boton_subir = QPushButton("Subir")
        self.boton_subir.setObjectName("botonSecundario")
        self.boton_subir.setFixedWidth(_ANCHO_CAMPO)
        self.boton_subir.clicked.connect(lambda: self._reordenar(-1))
        columna_botones.addWidget(self.boton_subir)

        self.boton_bajar = QPushButton("Bajar")
        self.boton_bajar.setObjectName("botonSecundario")
        self.boton_bajar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_bajar.clicked.connect(lambda: self._reordenar(1))
        columna_botones.addWidget(self.boton_bajar)

        self.boton_activo = QPushButton("Activar/Desactivar")
        self.boton_activo.setObjectName("botonSecundario")
        self.boton_activo.setFixedWidth(_ANCHO_CAMPO)
        self.boton_activo.clicked.connect(self._alternar_activo)
        columna_botones.addWidget(self.boton_activo)

        self.boton_descargar = QPushButton("Descargar")
        self.boton_descargar.setObjectName("botonSecundario")
        self.boton_descargar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_descargar.clicked.connect(self._descargar_o_copiar)
        columna_botones.addWidget(self.boton_descargar)

        self.boton_eliminar = QPushButton("Eliminar")
        self.boton_eliminar.setObjectName("botonSecundario")
        self.boton_eliminar.setFixedWidth(_ANCHO_CAMPO)
        self.boton_eliminar.clicked.connect(self._eliminar)
        columna_botones.addWidget(self.boton_eliminar)

        columna_botones.addWidget(_linea_divisoria())

        self.boton_manual = QPushButton("Manual del usuario")
        self.boton_manual.setObjectName("botonPrimario")
        self.boton_manual.setFixedWidth(_ANCHO_CAMPO)
        self.boton_manual.clicked.connect(self._regenerar_manual)
        columna_botones.addWidget(self.boton_manual)

        columna_botones.addStretch()
        fila_superior.addWidget(panel_botones)

        panel_preview = QWidget()
        layout_preview = QVBoxLayout(panel_preview)
        layout_preview.addWidget(_titulo_campo("Vista previa"))
        self._pixmap_original: QPixmap | None = None
        self.etiqueta_preview = _EtiquetaConAnchoDinamico(self._reescalar_preview, "Seleccioná un archivo para verlo acá.")
        self.etiqueta_preview.setObjectName("previsualizacionImagen")
        self.etiqueta_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.etiqueta_preview.setWordWrap(True)
        # Pedido explícito de la clienta: ya no queda fijo a 400x400 —
        # se estira hasta el borde de la pantalla (ancho) y hasta donde
        # llegue filtros/botones, lo que ocupe más en alto (alto) — ver
        # `_ANCHO_MINIMO_PREVISUALIZACION`/`_ALTO_MINIMO_PREVISUALIZACION`
        # para el piso que evita que quede degenerado.
        self.etiqueta_preview.setMinimumSize(_ANCHO_MINIMO_PREVISUALIZACION, _ALTO_MINIMO_PREVISUALIZACION)
        self.etiqueta_preview.setStyleSheet("border: 1px solid #000000;")
        layout_preview.addWidget(self.etiqueta_preview, stretch=1)
        fila_superior.addWidget(panel_preview, stretch=1)

        # Sin stretch (se queda en su alto natural, el que definen filtros/
        # botones — pedido explícito de la clienta) — el que se lleva
        # cualquier alto de sobra que deje el QScrollArea es `self.tabla`
        # de abajo (`stretch=1`), no esta fila.
        layout_contenido.addLayout(fila_superior)

        self._indice_descripcion = 5
        self._columnas_minimas: frozenset[int] = frozenset({4, 6, 7, 8})
        self.tabla = _TablaConAnchoDinamico(self._reajustar_ancho_tabla)
        excluir_tabla_del_tab(self.tabla)
        self._configurar_columnas(es_todos=True)  # "Todos los archivos" es la primera opción del combo Alcance
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.itemSelectionChanged.connect(self._actualizar_previsualizacion)
        instalar_eliminar_con_tecla(self.tabla, self._eliminar)
        layout_contenido.addWidget(self.tabla, stretch=1)

        scroll.setWidget(contenido)
        layout_externo.addWidget(scroll)

        # Punto 26 (SistemaDF v0.11.2026.10): cadena de foco explícita,
        # de arriba a abajo, con wrap-around de "Manual del usuario" de
        # vuelta a "Alcance" (gratis, ver `instalar_enter_avanza_foco`).
        self._foco = instalar_enter_avanza_foco(
            [
                self.combo_alcance, self.combo_tipo, self.combo_localidad, self.combo_edificio,
                self.combo_unidad, self.combo_consultorio, self.boton_agregar, self.boton_principal,
                self.boton_subir, self.boton_bajar, self.boton_activo, self.boton_descargar,
                self.boton_eliminar, self.boton_manual,
            ],
            parent=self,
        )

    def showEvent(self, evento) -> None:
        """Punto 1.4: al volver a mostrarse la solapa (incluido F3, ver
        `reiniciar`), arranca "como recién se hubiera ingresado"."""
        super().showEvent(evento)
        self.reiniciar()

    def reiniciar(self) -> None:
        self.combo_alcance.setCurrentIndex(0)
        self.combo_tipo.setCurrentIndex(0)
        self.tabla.clearSelection()
        self.combo_alcance.setFocus()

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

    def _al_cambiar_tipo(self, *_args) -> None:
        """El botón "Descargar" no tiene sentido para un enlace (no hay
        archivo que copiar afuera) — pasa a "Copiar enlace" (al
        portapapeles, la acción que pidió la clienta) mientras el Tipo
        de archivo elegido sea Enlace."""
        self.boton_descargar.setText("Copiar enlace" if self.combo_tipo.currentText() == "Enlace" else "Descargar")
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
        filas = self.conn.execute(sql, parametros).fetchall()
        # Orden por piso (PB, EP, después ascendente numérico) + letra a
        # igual piso — pedido general de la clienta (ver `clave_orden_unidad`).
        filas = sorted(filas, key=lambda f: clave_orden_unidad(f["Departamento"]))
        for f in filas:
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
        comprobar = _COMPROBADOR_TIPO[self.combo_tipo.currentText()]
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
            self.tabla.setItem(fila_idx, 3, item_centrado("Sí" if img["NumeroOrden"] == 1 else "No"))
            self.tabla.setItem(fila_idx, 4, item_centrado("Sí" if img["Activo"] else "No"))
        self._indice_descripcion = 1
        self._columnas_minimas = frozenset({0, 2, 3, 4})
        _ajustar_columnas(self.tabla, self._indice_descripcion, self._columnas_minimas)

    def _llenar_tabla_todos(self) -> None:
        self.tabla.setRowCount(len(self._imagenes))
        for fila_idx, img in enumerate(self._imagenes):
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(img["Alcance"]))
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(img["LocalidadTexto"] or ""))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(img["EdificioTexto"] or ""))
            # "Unidad"/"Consul" centrados (pedido explícito de la clienta):
            # excepción puntual a la regla general de "texto a la
            # izquierda" — ver convención "Contenido de celda" en CLAUDE.md.
            self.tabla.setItem(fila_idx, 3, item_centrado(img["UnidadTexto"] or ""))
            self.tabla.setItem(
                fila_idx, 4, item_centrado(str(img["ConsultorioNumero"]) if img["ConsultorioNumero"] else ""),
            )
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem(img["Descripcion"] or ""))
            self.tabla.setItem(fila_idx, 6, QTableWidgetItem(img["Tipo"] or ""))
            self.tabla.setItem(fila_idx, 7, item_centrado("Sí" if img["NumeroOrden"] == 1 else "No"))
            self.tabla.setItem(fila_idx, 8, item_centrado("Sí" if img["Activo"] else "No"))
        self._indice_descripcion = 5
        self._columnas_minimas = frozenset({4, 6, 7, 8})
        _ajustar_columnas(self.tabla, self._indice_descripcion, self._columnas_minimas)

    def _reajustar_ancho_tabla(self) -> None:
        """Se llama sola cada vez que la tabla cambia de tamaño
        (`_TablaConAnchoDinamico`), para recalcular cómo se reparte el
        ancho sobrante entre sus columnas con el ancho real ya
        conocido — en la construcción (todavía huérfana, sin mostrarse)
        el viewport mide 0 o un valor chico cualquiera, así que el
        primer reparto que de verdad importa es este, no el que ya hizo
        `_llenar_tabla_normal`/`_llenar_tabla_todos` al cargar los
        datos."""
        if self.tabla.columnCount() == 0:
            return
        _ajustar_columnas(self.tabla, self._indice_descripcion, self._columnas_minimas)

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
        if es_enlace(ruta):
            self._mostrar_preview_texto(f"Enlace:\n{ruta}")
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
        self._pixmap_original = None
        self.etiqueta_preview.setPixmap(QPixmap())
        self.etiqueta_preview.setText(texto)

    def _mostrar_preview_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap_original = pixmap
        self.etiqueta_preview.setText("")
        self._reescalar_preview()

    def _reescalar_preview(self) -> None:
        """Vuelve a escalar `self._pixmap_original` (siempre la imagen
        original, nunca la ya escalada — si no, achicar y agrandar
        varias veces seguidas iría perdiendo calidad) al tamaño actual
        de la Vista previa. Se llama sola cada vez que el label cambia
        de tamaño (`_EtiquetaConAnchoDinamico`), no solo al elegir un
        archivo — la Vista previa ya no tiene un tamaño fijo."""
        if self._pixmap_original is None:
            return
        self.etiqueta_preview.setPixmap(
            self._pixmap_original.scaled(
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
        ruta = None
        if tipo != "Enlace":
            ruta, _ = QFileDialog.getOpenFileName(self, "Elegir archivo", "", _FILTRO_ARCHIVO[tipo])
            if not ruta:
                return
        dialogo = _DialogoAgregarArchivo(categorias, pedir_url=(tipo == "Enlace"), parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            if tipo == "Enlace":
                agregar_enlace(
                    self.conn, url=dialogo.url(), categoria=dialogo.categoria(), etiqueta_libre=dialogo.etiqueta_libre(),
                    principal=dialogo.principal(), **parametros,
                )
            else:
                agregar_imagen(
                    self.conn, ruta_origen=ruta, categoria=dialogo.categoria(), etiqueta_libre=dialogo.etiqueta_libre(),
                    principal=dialogo.principal(), **parametros,
                )
        except ValueError as error:
            QMessageBox.warning(self, "Gestor de archivos", str(error))
            return
        self.conn.commit()
        self.actualizar()
        QMessageBox.information(self, "Gestor de archivos", "Archivo agregado con éxito.")

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

    def _descargar_o_copiar(self) -> None:
        if self.combo_tipo.currentText() == "Enlace":
            self._copiar_enlace()
        else:
            self._descargar()

    def _copiar_enlace(self) -> None:
        img = self._imagen_seleccionada()
        if img is None:
            return
        if not img["RutaArchivo"]:
            QMessageBox.warning(self, "Gestor de archivos", "Este enlace no tiene una URL asociada.")
            return
        QApplication.clipboard().setText(img["RutaArchivo"])
        # Pedido explícito de la clienta: el cartel de "operación exitosa"
        # tiene que salir para todos los procesos de esta solapa (mismo
        # criterio que "Archivo agregado con éxito"/"Archivo eliminado con
        # éxito") — acá faltaba, tanto para "Copiar enlace" como para
        # "Descargar" (ver `_descargar`, el otro camino de este mismo
        # botón).
        QMessageBox.information(self, "Gestor de archivos", "Enlace copiado con éxito.")

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
            return
        # Pedido explícito de la clienta: mismo cartel de "operación
        # exitosa" que ya tienen "Agregar archivo"/"Eliminar archivo" en
        # esta solapa — acá faltaba.
        QMessageBox.information(self, "Gestor de archivos", "Archivo descargado con éxito.")

    def _eliminar(self) -> None:
        img = self._imagen_seleccionada()
        if img is None:
            return
        confirmacion = QMessageBox.question(self, "Eliminar archivo", "¿Confirmás eliminar el archivo seleccionado?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Gestor de archivos", "Eliminación cancelada.")
            return
        eliminar_imagen(self.conn, img["IdImagen"])
        self.conn.commit()
        self.actualizar()
        QMessageBox.information(self, "Gestor de archivos", "Archivo eliminado con éxito.")

    def _regenerar_manual(self) -> None:
        """A diferencia del resto de los botones de este panel, no
        depende de ninguna fila seleccionada en la tabla — siempre
        regenera el PDF del manual contra el estado actual del sistema
        (mismo generador que usaba la vieja pantalla "Archivos varios")."""
        if not self._secciones:
            QMessageBox.warning(
                self, "Manual del usuario", "No hay ayuda contextual disponible para armar el manual.",
            )
            return
        tuplas = [(s.categoria, s.nombre, s.ayuda) for s in self._secciones]
        directorio = str(carpeta_archivos_varios(self.conn, SUBCARPETA_MANUAL))
        try:
            ruta = generar_pdf_manual(self.conn, directorio, tuplas)
        except ValueError as error:
            QMessageBox.warning(self, "Manual del usuario", str(error))
            return
        QMessageBox.information(self, "Manual del usuario", f"Se generó el manual en:\n{ruta}")
