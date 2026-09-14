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

Estilo de las solapas EXPERIMENTAL, solo en esta pantalla (a pedido de
la clienta: "probemos primero acá, si queda bien lo aplicamos al
resto"): contorno negro en la solapa y fondo del panel más claro que la
solapa en sí, con un tamaño de letra un poco menor que el resto de las
pantallas — aplicado con un `setStyleSheet` en la instancia del
QTabWidget de acá, NO en `app/gui/estilos.py`, así que no afecta a
ninguna otra pantalla todavía."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
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

from app.gui.pantallas.reservas import _opciones_profesional, _texto_profesional
from app.gui.widgets.grilla_operativa import (
    _agregar_item_todos,
    _corregir_seleccion_todos,
    _FiltroColapsable,
    _ids_seleccionados,
    _lista_multiseleccion,
    _seleccionar_todos,
)
from app.gui.widgets.items_tabla import item_numero
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
from app.pdf.placas_pdf import generar_pdf_placas_seleccionadas
from app.repositorio.registro import obtener_repositorio

# Vista previa de impresión: escala real a ~96dpi (1cm = 37.8px) para que
# las proporciones se acerquen a las del PDF — no pretende ser exacta
# (Qt y reportlab miden texto distinto), solo una referencia visual.
_PX_POR_CM = 37.8
_PREVIA_ANCHO_PX = round(7.6 * _PX_POR_CM)
_PREVIA_ALTO_PX = round(2.2 * _PX_POR_CM)
_PREVIA_MARGEN_PX = round(0.3 * _PX_POR_CM)
_PREVIA_GAP_COLUMNAS_PX = round(0.6 * _PX_POR_CM)
_PREVIA_GAP_FILAS_PX = round(0.3 * _PX_POR_CM)

_ESTILO_SOLAPAS_PREVIA = """
QTabBar::tab {
    font-size: 14px; font-weight: bold; color: #1A1A1A;
    background-color: #F5F5F5;
    border: 1px solid #000000;
    padding: 6px 14px;
}
QTabBar::tab:selected { background-color: #F5F5F5; }
QTabWidget::pane { background-color: #FFFFFF; }
"""


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
        solapas.setStyleSheet(_ESTILO_SOLAPAS_PREVIA)
        solapas.addTab(self._armar_panel_buscar(), "Buscar y asignar placas")
        solapas.addTab(self._armar_panel_imprimir(), "Imprimir placas")
        layout.addWidget(solapas)

        self._cargar_localidades()

    # --------------------------------------------------- buscar y asignar

    def _armar_panel_buscar(self) -> QWidget:
        panel = QWidget()
        layout_principal = QHBoxLayout(panel)

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
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self._orden = OrdenTabla(self.tabla, self._actualizar_tabla)
        columna_tabla.addWidget(self.tabla, stretch=1)

        fila_botones = QHBoxLayout()
        self.boton_asignar_nueva = QPushButton("Asignar placa nueva…")
        self.boton_asignar_nueva.setObjectName("botonPrimario")
        self.boton_asignar_nueva.clicked.connect(self._asignar_nueva)
        self.boton_reasignar = QPushButton("Reasignar…")
        self.boton_reasignar.setObjectName("botonSecundario")
        self.boton_reasignar.clicked.connect(self._reasignar)
        self.boton_liberar = QPushButton("Liberar posición")
        self.boton_liberar.setObjectName("botonSecundario")
        self.boton_liberar.clicked.connect(self._liberar)
        fila_botones.addWidget(self.boton_asignar_nueva)
        fila_botones.addWidget(self.boton_reasignar)
        fila_botones.addWidget(self.boton_liberar)
        fila_botones.addStretch()
        columna_tabla.addLayout(fila_botones)
        layout_principal.addLayout(columna_tabla, stretch=1)

        columna_filtros = QVBoxLayout()
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
        layout_principal.addLayout(columna_filtros)

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
            # Localidad, Edificio, Unidad, Profesional (sort estable: se ordena
            # primero por la clave menos significativa, pedido de la clienta).
            enriquecidos.sort(key=lambda e: e["texto_profesional"])
            enriquecidos.sort(key=lambda e: e["unidad"])
            enriquecidos.sort(key=lambda e: e["edificio"])
            enriquecidos.sort(key=lambda e: e["localidad"])

        self._placas_actuales = [e["placa"] for e in enriquecidos]
        self.tabla.setRowCount(len(enriquecidos))
        for fila_idx, e in enumerate(enriquecidos):
            placa = e["placa"]
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(e["localidad"]))
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(e["edificio"]))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(e["unidad"]))
            self.tabla.setItem(fila_idx, 3, item_numero(str(placa["PosicionTablero"])))
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(e["texto_profesional"]))
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem(e["nombre"]))
            self.tabla.setItem(fila_idx, 6, QTableWidgetItem("Sí" if placa["EsPersonalizada"] else "No"))
        self.tabla.resizeColumnsToContents()
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
        layout = QVBoxLayout(panel)

        layout.addWidget(_titulo_campo("Buscar profesional"))
        fila_busqueda = QHBoxLayout()
        self.combo_profesional_imprimir = QComboBox()
        for id_profesional, etiqueta in _opciones_profesional(self.conn):
            self.combo_profesional_imprimir.addItem(etiqueta, id_profesional)
        habilitar_busqueda_profesional(self.combo_profesional_imprimir)
        fila_busqueda.addWidget(self.combo_profesional_imprimir, stretch=1)
        layout.addLayout(fila_busqueda)

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
        layout.addLayout(fila_personalizada)

        self.boton_agregar_impresion = QPushButton("Agregar a impresión")
        self.boton_agregar_impresion.setObjectName("botonSecundario")
        self.boton_agregar_impresion.clicked.connect(self._agregar_a_impresion)
        layout.addWidget(self.boton_agregar_impresion)

        layout.addWidget(_titulo_campo("Placas a imprimir"))
        self.lista_impresion = QListWidget()
        layout.addWidget(self.lista_impresion)

        fila_botones = QHBoxLayout()
        self.boton_quitar_impresion = QPushButton("Quitar de la lista")
        self.boton_quitar_impresion.setObjectName("botonSecundario")
        self.boton_quitar_impresion.clicked.connect(self._quitar_de_impresion)
        self.boton_generar_pdf = QPushButton("Generar PDF")
        self.boton_generar_pdf.setObjectName("botonPrimario")
        self.boton_generar_pdf.clicked.connect(self._generar_pdf_impresion)
        fila_botones.addWidget(self.boton_quitar_impresion)
        fila_botones.addStretch()
        fila_botones.addWidget(self.boton_generar_pdf)
        layout.addLayout(fila_botones)

        layout.addWidget(_titulo_campo("Vista previa"))
        self.area_previa = QScrollArea()
        self.area_previa.setWidgetResizable(True)
        layout.addWidget(self.area_previa, stretch=1)
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

    def _actualizar_vista_previa(self) -> None:
        contenedor = QWidget()
        grid = QGridLayout(contenedor)
        grid.setHorizontalSpacing(_PREVIA_GAP_COLUMNAS_PX)
        grid.setVerticalSpacing(_PREVIA_GAP_FILAS_PX)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        for indice, entrada in enumerate(self._cola_impresion):
            profesional = repo_profesional.obtener(entrada["id_profesional"])
            if profesional is None:
                continue
            texto = texto_para_imprimir(profesional, linea1=entrada["linea1"], linea2=entrada["linea2"])
            etiqueta = QLabel(texto.replace("\n", "<br/>"))
            etiqueta.setTextFormat(Qt.TextFormat.RichText)
            etiqueta.setWordWrap(True)
            etiqueta.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            etiqueta.setMinimumSize(_PREVIA_ANCHO_PX, _PREVIA_ALTO_PX)
            etiqueta.setMaximumWidth(_PREVIA_ANCHO_PX)
            etiqueta.setStyleSheet(
                "border: 1px solid black; font-family: 'Calibri', sans-serif; font-size: 20pt; "
                f"font-weight: bold; font-style: italic; padding: {_PREVIA_MARGEN_PX}px;"
            )
            fila, columna = divmod(indice, 2)
            grid.addWidget(etiqueta, fila, columna)
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
