"""Placas (Etapa 9 / sección 3.8, separada de Archivos varios a pedido de
la clienta): buscar y asignar las placas de nombre de los profesionales
en el tablero de cada Unidad, y armar la selección puntual para
imprimir. Ver el docstring de `app.negocio.placas` para el modelo
completo — en particular, que no se lleva ningún historial: una
posición del tablero tiene como mucho una placa a la vez.

Todavía no está decidido si esta pantalla queda como formulario
independiente o como solapa dentro de otra pantalla existente (ej.
Liquidaciones) — por ahora se registra sola en la navegación, como F18
(Llaves) en su momento.

La apariencia de "ficha de papel" de las solapas se probó primero acá
y, aprobada por la clienta, pasó a `app/gui/estilos.py` (jerarquía 2)
para todas las pantallas — no queda nada de eso local en este
archivo."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from reportlab.lib.pagesizes import A4

from app.gui.pantallas.reservas import _opciones_profesional, _texto_profesional
from app.gui.widgets.grilla_operativa import (
    _agregar_item_todos,
    _corregir_seleccion_todos,
    _FiltroColapsable,
    _ids_seleccionados,
    _lista_multiseleccion,
    _seleccionar_todos,
)
from app.gui.widgets.orden_tabla import OrdenTabla
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.archivos_generados import SUBCARPETA_PLACAS, carpeta_archivos_varios
from app.negocio.placas import (
    asignar_placa,
    liberar_posicion,
    listar_placas,
    nombre_grabado,
    posiciones_libres,
    texto_para_imprimir,
)
from app.pdf.estilos import MARGEN
from app.pdf.placas_pdf import (
    ALTO_PLACA,
    ANCHO_PLACA,
    GAP_ENTRE_COLUMNAS,
    GAP_ENTRE_FILAS,
    MARGEN_INTERNO_HORIZONTAL_PLACA,
    MARGEN_INTERNO_PLACA,
    generar_pdf_placas_seleccionadas,
)
from app.repositorio.registro import obtener_repositorio

# Vista previa = una miniatura de la hoja A4 real, todo escalado con el
# MISMO factor (página, márgenes, placas, espacios Y tamaño de fuente) a
# partir de las medidas reales que usa el PDF (app.pdf.placas_pdf) — así
# se mantienen las proporciones de verdad en vez de una conversión cm/px
# aparte (la de antes no escalaba la fuente junto con la caja, así que
# el texto quedaba grande para el recuadro y las cajas se veían más
# "cuadradas" de lo que son en realidad).
_PAGINA_ANCHO_PX = 650
_ESCALA_PREVIA = _PAGINA_ANCHO_PX / A4[0]


def _pt_a_px(valor_puntos: float) -> int:
    return round(valor_puntos * _ESCALA_PREVIA)


_PAGINA_ALTO_PX = _pt_a_px(A4[1])
_PAGINA_MARGEN_PX = _pt_a_px(MARGEN)
_PREVIA_ANCHO_PX = _pt_a_px(ANCHO_PLACA)
_PREVIA_ALTO_PX = _pt_a_px(ALTO_PLACA)
_PREVIA_MARGEN_PX = _pt_a_px(MARGEN_INTERNO_PLACA)  # arriba/abajo
_PREVIA_MARGEN_HORIZONTAL_PX = max(_pt_a_px(MARGEN_INTERNO_HORIZONTAL_PLACA), 1)  # izquierda/derecha
_PREVIA_GAP_COLUMNAS_PX = _pt_a_px(GAP_ENTRE_COLUMNAS)
_PREVIA_GAP_FILAS_PX = _pt_a_px(GAP_ENTRE_FILAS)
# Tamaño de fuente FIJO e igual para todas las placas (no se achica según el
# texto: la clienta lo pidió así, para que no salten diferencias visuales
# entre una placa con un nombre corto y una con uno largo). Calibrado
# independiente del de app.pdf.placas_pdf (18pt): Qt sustituye "Calibri" por
# una fuente propia del sistema, que mide distinto que la Helvetica-
# BoldOblique de reportlab, así que escalar 18pt con _pt_a_px no reproduce el
# mismo corte de línea — se calibró por separado, en píxeles de esta vista
# previa, contra la misma referencia de la clienta: "Lic. Agustina
# Viavattene" (24 caracteres) entra en una sola línea; una letra más la baja
# a dos líneas.
_PREVIA_FUENTE_PX = 16
_PLACAS_POR_PAGINA = 22  # 2 columnas x 11 filas, igual que generar_pdf_placas_seleccionadas


def _fuente_placa_previa() -> QFont:
    fuente = QFont("Calibri")
    fuente.setBold(True)
    fuente.setItalic(True)
    fuente.setPixelSize(_PREVIA_FUENTE_PX)
    return fuente


def _envolver_lineas_previa(texto: str) -> list[str]:
    """Envuelve cada línea de `texto` a mano con QFontMetrics en vez de
    dejar el salto de palabra en manos de QLabel.setWordWrap: esa opción
    arma un QTextDocument interno (aun con texto plano) que suma su
    propio margen no configurable desde QLabel, así que corta antes de
    lo que sugiere QFontMetrics — la misma clase de desajuste que ya se
    había visto con RichText/"<br/>" en una ronda anterior. Envolviendo
    a mano, con la misma métrica que calibró _PREVIA_FUENTE_PX, el corte
    de línea coincide con la ficha real (nunca corta una palabra a la
    mitad, igual que el salto de línea natural de reportlab en el PDF)."""
    metricas = QFontMetrics(_fuente_placa_previa())
    ancho_disponible = _PREVIA_ANCHO_PX - 2 * _PREVIA_MARGEN_HORIZONTAL_PX
    resultado = []
    for linea in texto.split("\n"):
        actual = ""
        for palabra in linea.split(" "):
            candidato = f"{actual} {palabra}".strip()
            if actual and metricas.boundingRect(candidato).width() > ancho_disponible:
                resultado.append(actual)
                actual = palabra
            else:
                actual = candidato
        resultado.append(actual)
    return resultado


_ANCHO_BOTON_IMPRESION = 180  # Agregar a impresión / Quitar de la lista / Generar PDF, los tres iguales
_ANCHO_MINIMO_PANEL_FILTROS = 300
_ANCHO_BOTON_BUSCAR = 290  # Asignar posición placa nueva / Reasignar.../ Liberar posición, los tres iguales


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


class PantallaPlacas(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._placas_actuales: list[sqlite3.Row] = []
        self._cola_impresion: list[dict] = []
        self._armar_ui()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._orden.reiniciar()
        self.combo_profesional_filtro.setCurrentIndex(0)
        self._cargar_localidades()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Placas".upper())
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        solapas = QTabWidget()
        solapas.addTab(self._armar_panel_buscar(), "Buscar y asignar placas")
        solapas.addTab(self._armar_panel_imprimir(), "Imprimir placas")
        layout.addWidget(solapas)

        self._cargar_localidades()

    # --------------------------------------------------- buscar y asignar

    def _armar_panel_buscar(self) -> QWidget:
        panel = QWidget()
        layout_principal = QHBoxLayout(panel)

        panel_filtros = QWidget()
        panel_filtros.setMinimumWidth(_ANCHO_MINIMO_PANEL_FILTROS)
        columna_filtros = QVBoxLayout(panel_filtros)
        columna_filtros.setContentsMargins(0, 0, 0, 0)
        columna_filtros.addWidget(_titulo_campo("Profesional"))
        self.combo_profesional_filtro = QComboBox()
        self.combo_profesional_filtro.addItem("Todos los profesionales", None)
        for id_profesional, etiqueta in _opciones_profesional(self.conn):
            self.combo_profesional_filtro.addItem(etiqueta, id_profesional)
        habilitar_busqueda_profesional(self.combo_profesional_filtro)
        self.combo_profesional_filtro.currentIndexChanged.connect(self._actualizar_tabla)
        columna_filtros.addWidget(self.combo_profesional_filtro)

        columna_filtros.addWidget(_titulo_campo("Localidad"))
        self.lista_localidad = _lista_multiseleccion()
        self.lista_localidad.itemSelectionChanged.connect(self._cargar_edificios)
        self._filtro_localidad = _FiltroColapsable(self.lista_localidad)
        columna_filtros.addWidget(self._filtro_localidad)

        columna_filtros.addWidget(_titulo_campo("Edificio"))
        self.lista_edificio = _lista_multiseleccion()
        self.lista_edificio.itemSelectionChanged.connect(self._cargar_unidades)
        self._filtro_edificio = _FiltroColapsable(self.lista_edificio)
        columna_filtros.addWidget(self._filtro_edificio)

        columna_filtros.addWidget(_titulo_campo("Unidad"))
        self.lista_unidad = _lista_multiseleccion()
        self.lista_unidad.itemSelectionChanged.connect(self._filtro_unidad_cambio)
        self._filtro_unidad = _FiltroColapsable(self.lista_unidad)
        columna_filtros.addWidget(self._filtro_unidad)

        columna_filtros.addStretch()
        layout_principal.addWidget(panel_filtros)

        columna_tabla = QVBoxLayout()
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(7)
        self.tabla.setHorizontalHeaderLabels(
            ["Localidad", "Edificio", "Unidad", "Posición", "Profesional", "Nombre grabado", "Personalizada"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones_tabla)
        # Todas las columnas se reparten el ancho disponible por igual —
        # pedido de la clienta, en vez de ajustarse al contenido.
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._orden = OrdenTabla(self.tabla, self._actualizar_tabla)
        columna_tabla.addWidget(self.tabla, stretch=1)

        fila_botones = QHBoxLayout()
        self.boton_asignar_nueva = QPushButton("Asignar posición placa nueva")
        self.boton_asignar_nueva.setObjectName("botonPrimario")
        self.boton_asignar_nueva.setFixedWidth(_ANCHO_BOTON_BUSCAR)
        self.boton_asignar_nueva.clicked.connect(self._asignar_nueva)
        self.boton_reasignar = QPushButton("Reasignar posición placa existente")
        self.boton_reasignar.setObjectName("botonSecundario")
        self.boton_reasignar.setFixedWidth(_ANCHO_BOTON_BUSCAR)
        self.boton_reasignar.clicked.connect(self._reasignar)
        self.boton_liberar = QPushButton("Liberar posición")
        self.boton_liberar.setObjectName("botonSecundario")
        self.boton_liberar.setFixedWidth(_ANCHO_BOTON_BUSCAR)
        self.boton_liberar.clicked.connect(self._liberar)
        fila_botones.addWidget(self.boton_asignar_nueva)
        fila_botones.addWidget(self.boton_reasignar)
        fila_botones.addWidget(self.boton_liberar)
        fila_botones.addStretch()
        columna_tabla.addLayout(fila_botones)
        layout_principal.addLayout(columna_tabla, stretch=1)

        self._actualizar_botones_tabla()
        return panel

    def _cargar_localidades(self) -> None:
        self.lista_localidad.blockSignals(True)
        self.lista_localidad.clear()
        _agregar_item_todos(self.lista_localidad, "Todas las localidades")
        localidades = self.conn.execute(
            "SELECT DISTINCT DomicilioLocalidad FROM Edificio ORDER BY DomicilioLocalidad"
        ).fetchall()
        for fila in localidades:
            valor = fila["DomicilioLocalidad"]
            item = QListWidgetItem(valor or "(Sin localidad)")
            item.setData(Qt.ItemDataRole.UserRole, valor)
            self.lista_localidad.addItem(item)
        _seleccionar_todos(self.lista_localidad)
        self.lista_localidad.blockSignals(False)
        self._filtro_localidad.actualizar_resumen()
        self._cargar_edificios()

    def _cargar_edificios(self) -> None:
        _corregir_seleccion_todos(self.lista_localidad)
        self._filtro_localidad.actualizar_resumen()
        localidades = _ids_seleccionados(self.lista_localidad)
        self.lista_edificio.blockSignals(True)
        self.lista_edificio.clear()
        _agregar_item_todos(self.lista_edificio, "Todos los edificios")
        sql = "SELECT IdEdificio, Nombre FROM Edificio"
        parametros: list = []
        if localidades:
            marcas = []
            for localidad in localidades:
                if localidad is None:
                    marcas.append("DomicilioLocalidad IS NULL")
                else:
                    marcas.append("DomicilioLocalidad = ?")
                    parametros.append(localidad)
            sql += " WHERE " + " OR ".join(marcas)
        sql += " ORDER BY Nombre"
        for fila in self.conn.execute(sql, parametros).fetchall():
            item = QListWidgetItem(fila["Nombre"])
            item.setData(Qt.ItemDataRole.UserRole, fila["IdEdificio"])
            self.lista_edificio.addItem(item)
        _seleccionar_todos(self.lista_edificio)
        self.lista_edificio.blockSignals(False)
        self._filtro_edificio.actualizar_resumen()
        self._cargar_unidades()

    def _cargar_unidades(self) -> None:
        _corregir_seleccion_todos(self.lista_edificio)
        self._filtro_edificio.actualizar_resumen()
        ids_edificio = _ids_seleccionados(self.lista_edificio)
        self.lista_unidad.blockSignals(True)
        self.lista_unidad.clear()
        _agregar_item_todos(self.lista_unidad, "Todas las unidades")
        sql = (
            "SELECT u.IdUnidad, u.Departamento, e.Nombre AS NombreEdificio FROM Unidad u "
            "JOIN Edificio e ON e.IdEdificio = u.IdEdificio"
        )
        parametros: list = []
        if ids_edificio:
            placeholders = ", ".join("?" for _ in ids_edificio)
            sql += f" WHERE u.IdEdificio IN ({placeholders})"
            parametros = ids_edificio
        filas = sorted(
            self.conn.execute(sql, parametros).fetchall(), key=lambda f: (f["NombreEdificio"], f["Departamento"]),
        )
        for fila in filas:
            item = QListWidgetItem(f"{fila['NombreEdificio']} - {fila['Departamento']}")
            item.setData(Qt.ItemDataRole.UserRole, fila["IdUnidad"])
            self.lista_unidad.addItem(item)
        _seleccionar_todos(self.lista_unidad)
        self.lista_unidad.blockSignals(False)
        self._filtro_unidad.actualizar_resumen()
        self._actualizar_tabla()

    def _filtro_unidad_cambio(self) -> None:
        _corregir_seleccion_todos(self.lista_unidad)
        self._filtro_unidad.actualizar_resumen()
        self._actualizar_tabla()

    @staticmethod
    def _clave_orden(columna: int):
        claves = {
            0: lambda e: e["localidad"],
            1: lambda e: e["edificio"],
            2: lambda e: e["unidad"],
            3: lambda e: e["placa"]["PosicionTablero"] or 0,
            4: lambda e: e["texto_profesional"],
            5: lambda e: e["nombre"],
            6: lambda e: e["placa"]["EsPersonalizada"],
        }
        return claves[columna]

    def _actualizar_tabla(self) -> None:
        placas = listar_placas(
            self.conn,
            ids_localidad=_ids_seleccionados(self.lista_localidad) or None,
            ids_edificio=_ids_seleccionados(self.lista_edificio) or None,
            ids_unidad=_ids_seleccionados(self.lista_unidad) or None,
            id_profesional=self.combo_profesional_filtro.currentData(),
        )
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        enriquecidos = []
        for placa in placas:
            profesional = repo_profesional.obtener(placa["IdProfesional"]) if placa["IdProfesional"] else None
            enriquecidos.append({
                "placa": placa,
                "localidad": placa["DomicilioLocalidad"] or "",
                "edificio": placa["NombreEdificio"],
                "unidad": placa["Departamento"],
                "texto_profesional": _texto_profesional(profesional) if profesional else "",
                "nombre": nombre_grabado(placa, profesional) if profesional else (placa["NombreGrabado"] or ""),
            })

        if self._orden.columna is not None:
            enriquecidos.sort(key=self._clave_orden(self._orden.columna), reverse=not self._orden.ascendente)
        else:
            # Localidad, Edificio, Unidad, Posición (sort estable: se ordena
            # primero por la clave menos significativa, pedido de la clienta).
            enriquecidos.sort(key=lambda e: e["placa"]["PosicionTablero"] or 0)
            enriquecidos.sort(key=lambda e: e["unidad"])
            enriquecidos.sort(key=lambda e: e["edificio"])
            enriquecidos.sort(key=lambda e: e["localidad"])

        self._placas_actuales = [e["placa"] for e in enriquecidos]
        self.tabla.setRowCount(len(enriquecidos))
        for fila_idx, e in enumerate(enriquecidos):
            placa = e["placa"]
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(e["localidad"]))
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(e["edificio"]))
            item_unidad = QTableWidgetItem(e["unidad"])
            item_unidad.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(fila_idx, 2, item_unidad)
            item_posicion = QTableWidgetItem(str(placa["PosicionTablero"]))
            item_posicion.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(fila_idx, 3, item_posicion)
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(e["texto_profesional"]))
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem(e["nombre"]))
            item_personalizada = QTableWidgetItem("Sí" if placa["EsPersonalizada"] else "No")
            item_personalizada.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(fila_idx, 6, item_personalizada)
        self._actualizar_botones_tabla()

    def _fila_seleccionada_placa(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._placas_actuales[filas[0].row()]

    def _actualizar_botones_tabla(self) -> None:
        hay_seleccion = self._fila_seleccionada_placa() is not None
        self.boton_reasignar.setEnabled(hay_seleccion)
        self.boton_liberar.setEnabled(hay_seleccion)

    def _asignar_nueva(self) -> None:
        dialogo = _DialogoPlaca(self.conn, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        valores = dialogo.valores()
        if valores["id_unidad"] is None or valores["posicion"] is None:
            QMessageBox.warning(self, "Asignar placa nueva", "Elegí una unidad con alguna posición libre.")
            return
        try:
            asignar_placa(self.conn, **valores)
        except ValueError as error:
            QMessageBox.warning(self, "Asignar placa nueva", str(error))
            return
        self._actualizar_tabla()

    def _reasignar(self) -> None:
        placa = self._fila_seleccionada_placa()
        if placa is None:
            return
        dialogo = _DialogoPlaca(self.conn, placa_existente=placa, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            asignar_placa(self.conn, **dialogo.valores())
        except ValueError as error:
            QMessageBox.warning(self, "Reasignar", str(error))
            return
        self._actualizar_tabla()

    def _liberar(self) -> None:
        placa = self._fila_seleccionada_placa()
        if placa is None:
            return
        confirmacion = QMessageBox.question(
            self, "Liberar posición", "¿Confirmás dejar esta posición del tablero vacía?",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        liberar_posicion(self.conn, placa["IdPlaca"])
        self._actualizar_tabla()

    # ------------------------------------------------------------ imprimir

    def _armar_panel_imprimir(self) -> QWidget:
        panel = QWidget()
        layout_principal = QHBoxLayout(panel)

        columna_izquierda = QVBoxLayout()
        columna_izquierda.addWidget(_titulo_campo("Buscar profesional"))
        self.combo_profesional_imprimir = QComboBox()
        for id_profesional, etiqueta in _opciones_profesional(self.conn):
            self.combo_profesional_imprimir.addItem(etiqueta, id_profesional)
        habilitar_busqueda_profesional(self.combo_profesional_imprimir)
        columna_izquierda.addWidget(self.combo_profesional_imprimir)

        fila_personalizada = QHBoxLayout()
        self.casilla_personalizar_impresion = QCheckBox("Personalizar texto de la placa")
        self.campo_linea1_impresion = QLineEdit()
        self.campo_linea1_impresion.setPlaceholderText("Línea 1")
        self.campo_linea1_impresion.setEnabled(False)
        self.campo_linea2_impresion = QLineEdit()
        self.campo_linea2_impresion.setPlaceholderText("Línea 2 (opcional)")
        self.campo_linea2_impresion.setEnabled(False)
        self.casilla_personalizar_impresion.toggled.connect(self.campo_linea1_impresion.setEnabled)
        self.casilla_personalizar_impresion.toggled.connect(self.campo_linea2_impresion.setEnabled)
        fila_personalizada.addWidget(self.casilla_personalizar_impresion)
        fila_personalizada.addWidget(self.campo_linea1_impresion)
        fila_personalizada.addWidget(self.campo_linea2_impresion)
        columna_izquierda.addLayout(fila_personalizada)

        fila_agregar = QHBoxLayout()
        self.boton_agregar_impresion = QPushButton("Agregar a impresión")
        self.boton_agregar_impresion.setObjectName("botonSecundario")
        self.boton_agregar_impresion.setFixedWidth(_ANCHO_BOTON_IMPRESION)
        self.boton_agregar_impresion.clicked.connect(self._agregar_a_impresion)
        fila_agregar.addStretch()
        fila_agregar.addWidget(self.boton_agregar_impresion)
        fila_agregar.addStretch()
        columna_izquierda.addLayout(fila_agregar)

        columna_izquierda.addWidget(_titulo_campo("Placas a imprimir"))
        self.lista_impresion = QListWidget()
        columna_izquierda.addWidget(self.lista_impresion, stretch=1)

        fila_botones = QHBoxLayout()
        self.boton_quitar_impresion = QPushButton("Quitar de la lista")
        self.boton_quitar_impresion.setObjectName("botonSecundario")
        self.boton_quitar_impresion.setFixedWidth(_ANCHO_BOTON_IMPRESION)
        self.boton_quitar_impresion.clicked.connect(self._quitar_de_impresion)
        self.boton_generar_pdf = QPushButton("Generar PDF")
        self.boton_generar_pdf.setObjectName("botonPrimario")
        self.boton_generar_pdf.setFixedWidth(_ANCHO_BOTON_IMPRESION)
        self.boton_generar_pdf.clicked.connect(self._generar_pdf_impresion)
        fila_botones.addStretch()
        fila_botones.addWidget(self.boton_quitar_impresion)
        fila_botones.addWidget(self.boton_generar_pdf)
        columna_izquierda.addLayout(fila_botones)
        layout_principal.addLayout(columna_izquierda, stretch=1)

        columna_derecha = QVBoxLayout()
        columna_derecha.addWidget(_titulo_campo("Vista previa"))
        self.area_previa = QScrollArea()
        self.area_previa.setWidgetResizable(True)
        columna_derecha.addWidget(self.area_previa, stretch=1)
        layout_principal.addLayout(columna_derecha, stretch=1)
        self._actualizar_vista_previa()

        return panel

    def _agregar_a_impresion(self) -> None:
        id_profesional = self.combo_profesional_imprimir.currentData()
        if id_profesional is None:
            return
        personalizar = self.casilla_personalizar_impresion.isChecked()
        linea1 = self.campo_linea1_impresion.text().strip() or None
        linea2 = self.campo_linea2_impresion.text().strip() or None
        if personalizar and not linea1:
            QMessageBox.warning(self, "Agregar a impresión", "Cargá al menos la línea 1 para una placa personalizada.")
            return
        if not personalizar:
            linea1 = None
            linea2 = None

        etiqueta_base = self.combo_profesional_imprimir.currentText()
        etiqueta_lista = f"{etiqueta_base} (personalizada)" if personalizar else etiqueta_base
        self._cola_impresion.append({
            "id_profesional": id_profesional, "linea1": linea1, "linea2": linea2, "etiqueta_lista": etiqueta_lista,
        })
        self.lista_impresion.addItem(etiqueta_lista)
        self.casilla_personalizar_impresion.setChecked(False)
        self.campo_linea1_impresion.clear()
        self.campo_linea2_impresion.clear()
        self._actualizar_vista_previa()

    def _quitar_de_impresion(self) -> None:
        fila = self.lista_impresion.currentRow()
        if fila < 0:
            return
        self.lista_impresion.takeItem(fila)
        del self._cola_impresion[fila]
        self._actualizar_vista_previa()

    def _textos_cola_impresion(self) -> list[str]:
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        textos = []
        for entrada in self._cola_impresion:
            profesional = repo_profesional.obtener(entrada["id_profesional"])
            if profesional is None:
                continue
            textos.append(texto_para_imprimir(profesional, linea1=entrada["linea1"], linea2=entrada["linea2"]))
        return textos

    @staticmethod
    def _armar_placa_previa(texto: str) -> QLabel:
        # El salto de línea NO se deja en manos de QLabel.setWordWrap: esa
        # opción arma internamente un QTextDocument (aun con texto plano)
        # que suma su propio margen interno no configurable desde QLabel, y
        # con eso corta antes de lo que sugiere QFontMetrics — la misma
        # clase de desajuste que ya se había visto con RichText/"<br/>". Se
        # envuelve a mano línea por línea con la MISMA QFontMetrics que
        # calibró _PREVIA_FUENTE_PX, para que coincida con la ficha real.
        etiqueta = QLabel("\n".join(_envolver_lineas_previa(texto)))
        etiqueta.setWordWrap(False)
        etiqueta.setFont(_fuente_placa_previa())
        etiqueta.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        etiqueta.setFixedSize(_PREVIA_ANCHO_PX, _PREVIA_ALTO_PX)  # tamaño físico fijo, como la placa real
        etiqueta.setStyleSheet(
            f"border: 1px solid black; padding: {_PREVIA_MARGEN_PX}px {_PREVIA_MARGEN_HORIZONTAL_PX}px;"
        )
        return etiqueta

    @staticmethod
    def _armar_pagina_previa(textos_pagina: list[str]) -> QFrame:
        """Una "hoja" A4 en miniatura (mismas proporciones reales) con
        hasta 22 placas — igual paginado que generar_pdf_placas_
        seleccionadas — para que la vista previa simule de verdad la
        hoja que va a salir impresa, no una lista suelta de recuadros."""
        pagina = QFrame()
        pagina.setFixedWidth(_PAGINA_ANCHO_PX)
        pagina.setMinimumHeight(_PAGINA_ALTO_PX)  # alto real de una A4 a esta escala; crece si hace falta más lugar
        pagina.setStyleSheet("background-color: #FFFFFF; border: 1px solid #999999;")
        grid = QGridLayout(pagina)
        grid.setContentsMargins(_PAGINA_MARGEN_PX, _PAGINA_MARGEN_PX, _PAGINA_MARGEN_PX, _PAGINA_MARGEN_PX)
        grid.setHorizontalSpacing(_PREVIA_GAP_COLUMNAS_PX)
        grid.setVerticalSpacing(_PREVIA_GAP_FILAS_PX)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        for indice, texto in enumerate(textos_pagina):
            fila, columna = divmod(indice, 2)
            grid.addWidget(PantallaPlacas._armar_placa_previa(texto), fila, columna)
        return pagina

    def _actualizar_vista_previa(self) -> None:
        contenedor = QWidget()
        layout_paginas = QVBoxLayout(contenedor)
        layout_paginas.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout_paginas.setSpacing(16)

        textos = self._textos_cola_impresion()
        for inicio in range(0, len(textos), _PLACAS_POR_PAGINA):
            layout_paginas.addWidget(self._armar_pagina_previa(textos[inicio:inicio + _PLACAS_POR_PAGINA]))

        self.area_previa.setWidget(contenedor)

    def _generar_pdf_impresion(self) -> None:
        if not self._cola_impresion:
            QMessageBox.information(self, "Generar PDF", "Todavía no agregaste ninguna placa a la lista.")
            return
        try:
            directorio = str(carpeta_archivos_varios(self.conn, SUBCARPETA_PLACAS))
            entradas = [
                {"id_profesional": e["id_profesional"], "linea1": e["linea1"], "linea2": e["linea2"]}
                for e in self._cola_impresion
            ]
            ruta = generar_pdf_placas_seleccionadas(self.conn, directorio, entradas)
        except ValueError as error:
            QMessageBox.warning(self, "Generar PDF", str(error))
            return
        QMessageBox.information(self, "Generar PDF", f"Se generó el PDF en:\n{ruta}")
        self._cola_impresion.clear()
        self.lista_impresion.clear()
        self._actualizar_vista_previa()


class _DialogoPlaca(QDialog):
    def __init__(self, conn: sqlite3.Connection, *, placa_existente: sqlite3.Row | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.placa_existente = placa_existente
        self.setWindowTitle("Reasignar placa" if placa_existente else "Asignar placa nueva")
        layout = QFormLayout(self)

        if placa_existente is None:
            self.combo_unidad = QComboBox()
            for fila in conn.execute(
                "SELECT u.IdUnidad, u.Departamento, e.Nombre AS NombreEdificio FROM Unidad u "
                "JOIN Edificio e ON e.IdEdificio = u.IdEdificio ORDER BY e.Nombre, u.Departamento"
            ):
                self.combo_unidad.addItem(f"{fila['NombreEdificio']} - {fila['Departamento']}", fila["IdUnidad"])
            self.combo_unidad.currentIndexChanged.connect(self._cargar_posiciones_libres)
            layout.addRow("Unidad", self.combo_unidad)

            self.combo_posicion = QComboBox()
            layout.addRow("Posición libre", self.combo_posicion)
            self._cargar_posiciones_libres()
        else:
            unidad = obtener_repositorio(conn, "Unidad").obtener(placa_existente["IdUnidad"])
            edificio = obtener_repositorio(conn, "Edificio").obtener(unidad["IdEdificio"])
            layout.addRow("Unidad", QLabel(f"{edificio['Nombre']} - {unidad['Departamento']}"))
            layout.addRow("Posición", QLabel(str(placa_existente["PosicionTablero"])))

        self.combo_profesional = QComboBox()
        for id_profesional, etiqueta in _opciones_profesional(conn):
            self.combo_profesional.addItem(etiqueta, id_profesional)
        habilitar_busqueda_profesional(self.combo_profesional)
        if placa_existente is not None and placa_existente["IdProfesional"]:
            indice = self.combo_profesional.findData(placa_existente["IdProfesional"])
            if indice >= 0:
                self.combo_profesional.setCurrentIndex(indice)
        layout.addRow("Profesional", self.combo_profesional)

        self.casilla_personalizada = QCheckBox("Nombre grabado personalizado")
        self.campo_nombre_personalizado = QLineEdit()
        self.campo_nombre_personalizado.setEnabled(False)
        self.casilla_personalizada.toggled.connect(self.campo_nombre_personalizado.setEnabled)
        if placa_existente is not None and placa_existente["EsPersonalizada"]:
            self.casilla_personalizada.setChecked(True)
            self.campo_nombre_personalizado.setText(placa_existente["NombreGrabado"] or "")
        layout.addRow(self.casilla_personalizada)
        layout.addRow("Nombre grabado", self.campo_nombre_personalizado)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

    def _cargar_posiciones_libres(self) -> None:
        id_unidad = self.combo_unidad.currentData()
        self.combo_posicion.clear()
        if id_unidad is None:
            return
        for posicion in posiciones_libres(self.conn, id_unidad):
            self.combo_posicion.addItem(str(posicion), posicion)

    def valores(self) -> dict:
        if self.placa_existente is None:
            id_unidad = self.combo_unidad.currentData()
            posicion = self.combo_posicion.currentData()
        else:
            id_unidad = self.placa_existente["IdUnidad"]
            posicion = self.placa_existente["PosicionTablero"]
        return {
            "id_unidad": id_unidad,
            "posicion": posicion,
            "id_profesional": self.combo_profesional.currentData(),
            "es_personalizada": self.casilla_personalizada.isChecked(),
            "nombre_grabado_personalizado": self.campo_nombre_personalizado.text().strip() or None,
        }
