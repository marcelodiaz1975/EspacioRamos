"""Placas (Etapa 9 / sección 3.8, separada de Archivos varios a pedido de
la clienta): buscar y asignar las placas de nombre de los profesionales
en el tablero de cada Unidad, y armar la selección puntual para
imprimir. Ver el docstring de `app.negocio.placas` para el modelo
completo — en particular, que no se lleva ningún historial: una
posición del tablero tiene como mucho una placa a la vez.

Todavía no está decidido si esta pantalla queda como formulario
independiente o como solapa dentro de otra pantalla existente (ej.
Liquidaciones) — por ahora se registra sola en la navegación, como F18
(Llaves) en su momento."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
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
from app.gui.widgets.selector_profesional import habilitar_busqueda_profesional
from app.negocio.archivos_generados import SUBCARPETA_PLACAS, carpeta_archivos_varios
from app.negocio.placas import asignar_placa, liberar_posicion, listar_placas, nombre_grabado, posiciones_libres
from app.pdf.placas_pdf import generar_pdf_placas_seleccionadas
from app.repositorio.registro import obtener_repositorio


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


class PantallaPlacas(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._placas_actuales: list[sqlite3.Row] = []
        self._cola_impresion: list[tuple[int, str]] = []
        self._armar_ui()

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
        layout = QVBoxLayout(panel)

        fila_filtros = QHBoxLayout()

        col_localidad = QVBoxLayout()
        col_localidad.addWidget(_titulo_campo("Localidad"))
        self.lista_localidad = _lista_multiseleccion()
        self.lista_localidad.itemSelectionChanged.connect(self._cargar_edificios)
        self._filtro_localidad = _FiltroColapsable(self.lista_localidad)
        col_localidad.addWidget(self._filtro_localidad)
        fila_filtros.addLayout(col_localidad)

        col_edificio = QVBoxLayout()
        col_edificio.addWidget(_titulo_campo("Edificio"))
        self.lista_edificio = _lista_multiseleccion()
        self.lista_edificio.itemSelectionChanged.connect(self._cargar_unidades)
        self._filtro_edificio = _FiltroColapsable(self.lista_edificio)
        col_edificio.addWidget(self._filtro_edificio)
        fila_filtros.addLayout(col_edificio)

        col_unidad = QVBoxLayout()
        col_unidad.addWidget(_titulo_campo("Unidad"))
        self.lista_unidad = _lista_multiseleccion()
        self.lista_unidad.itemSelectionChanged.connect(self._filtro_unidad_cambio)
        self._filtro_unidad = _FiltroColapsable(self.lista_unidad)
        col_unidad.addWidget(self._filtro_unidad)
        fila_filtros.addLayout(col_unidad)

        col_profesional = QVBoxLayout()
        col_profesional.addWidget(_titulo_campo("Profesional"))
        self.combo_profesional_filtro = QComboBox()
        self.combo_profesional_filtro.addItem("Todos los profesionales", None)
        for id_profesional, etiqueta in _opciones_profesional(self.conn):
            self.combo_profesional_filtro.addItem(etiqueta, id_profesional)
        habilitar_busqueda_profesional(self.combo_profesional_filtro)
        self.combo_profesional_filtro.currentIndexChanged.connect(self._actualizar_tabla)
        col_profesional.addWidget(self.combo_profesional_filtro)
        fila_filtros.addLayout(col_profesional)

        layout.addLayout(fila_filtros)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Edificio", "Unidad", "Posición", "Profesional", "Nombre grabado", "Personalizada"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones_tabla)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabla, stretch=1)

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
        layout.addLayout(fila_botones)

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

    def _actualizar_tabla(self) -> None:
        self._placas_actuales = listar_placas(
            self.conn,
            ids_localidad=_ids_seleccionados(self.lista_localidad) or None,
            ids_edificio=_ids_seleccionados(self.lista_edificio) or None,
            ids_unidad=_ids_seleccionados(self.lista_unidad) or None,
            id_profesional=self.combo_profesional_filtro.currentData(),
        )
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        self.tabla.setRowCount(len(self._placas_actuales))
        for fila_idx, placa in enumerate(self._placas_actuales):
            profesional = repo_profesional.obtener(placa["IdProfesional"]) if placa["IdProfesional"] else None
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(placa["NombreEdificio"]))
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(placa["Departamento"]))
            self.tabla.setItem(fila_idx, 2, item_numero(str(placa["PosicionTablero"])))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(_texto_profesional(profesional) if profesional else ""))
            nombre = nombre_grabado(placa, profesional) if profesional else (placa["NombreGrabado"] or "")
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(nombre))
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem("Sí" if placa["EsPersonalizada"] else "No"))
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
        self.boton_agregar_impresion = QPushButton("Agregar a impresión")
        self.boton_agregar_impresion.setObjectName("botonSecundario")
        self.boton_agregar_impresion.clicked.connect(self._agregar_a_impresion)
        fila_busqueda.addWidget(self.boton_agregar_impresion)
        layout.addLayout(fila_busqueda)

        layout.addWidget(_titulo_campo("Placas a imprimir"))
        self.lista_impresion = QListWidget()
        layout.addWidget(self.lista_impresion, stretch=1)

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

        return panel

    def _agregar_a_impresion(self) -> None:
        id_profesional = self.combo_profesional_imprimir.currentData()
        if id_profesional is None:
            return
        if any(id_ == id_profesional for id_, _ in self._cola_impresion):
            return
        etiqueta = self.combo_profesional_imprimir.currentText()
        self._cola_impresion.append((id_profesional, etiqueta))
        self.lista_impresion.addItem(etiqueta)

    def _quitar_de_impresion(self) -> None:
        fila = self.lista_impresion.currentRow()
        if fila < 0:
            return
        self.lista_impresion.takeItem(fila)
        del self._cola_impresion[fila]

    def _generar_pdf_impresion(self) -> None:
        if not self._cola_impresion:
            QMessageBox.information(self, "Generar PDF", "Todavía no agregaste ninguna placa a la lista.")
            return
        try:
            directorio = str(carpeta_archivos_varios(self.conn, SUBCARPETA_PLACAS))
            ruta = generar_pdf_placas_seleccionadas(
                self.conn, directorio, [id_profesional for id_profesional, _ in self._cola_impresion],
            )
        except ValueError as error:
            QMessageBox.warning(self, "Generar PDF", str(error))
            return
        QMessageBox.information(self, "Generar PDF", f"Se generó el PDF en:\n{ruta}")
        self._cola_impresion.clear()
        self.lista_impresion.clear()


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
