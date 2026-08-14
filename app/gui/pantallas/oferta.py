"""Oferta de consultorios (Etapa 9, motor ad-hoc `app.negocio.oferta_busqueda`):
arma una búsqueda para un profesional puntual y genera el PDF o el texto de
WhatsApp con las alternativas encontradas. Cada búsqueda generada queda en
el historial (`app.negocio.historial_oferta`) con sus criterios completos,
así se puede volver a generar más adelante sin tener que cargarla de
nuevo — la regeneración vuelve a resolver contra la disponibilidad vigente
en ese momento, no repite el resultado congelado del día que se armó.

Esta pantalla arma UNA búsqueda por documento (no encadena varias
franjas con combinación Y/O, aunque el motor lo soporta) — cubre el caso
de uso más habitual; si hace falta combinar varias franjas en un mismo
documento, por ahora se arma por fuera de la pantalla."""
from __future__ import annotations

import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.negocio.archivos_generados import SUBCARPETA_OFERTA, carpeta_archivos_varios
from app.negocio.dias import DIAS_SEMANA, fecha_actual
from app.negocio.historial_oferta import guardar_busqueda, regenerar_pdf, regenerar_texto
from app.negocio.oferta_busqueda import (
    COMBINAR_MISMA_UNIDAD,
    COMBINAR_MISMO_EDIFICIO,
    SIN_COMBINAR,
    TIPO_AISLADA,
    TIPO_REGULAR,
    Busqueda,
    CriteriosGlobales,
    fecha_fin_default,
    fecha_inicio_default,
)
from app.negocio.mensajes import nombre_para_mensaje
from app.repositorio.registro import obtener_repositorio

_COMBINACIONES = [
    ("Sin combinación de consultorios", SIN_COMBINAR),
    ("Combinar, misma unidad", COMBINAR_MISMA_UNIDAD),
    ("Combinar, mismo edificio", COMBINAR_MISMO_EDIFICIO),
]


class _DialogoTexto(QDialog):
    """Muestra el texto de WhatsApp generado, listo para copiar."""

    def __init__(self, texto: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Texto para WhatsApp")
        self.resize(520, 480)
        layout = QVBoxLayout(self)
        campo = QPlainTextEdit()
        campo.setPlainText(texto)
        campo.setReadOnly(True)
        layout.addWidget(campo)
        boton_copiar = QPushButton("Copiar al portapapeles")
        boton_copiar.clicked.connect(lambda: QApplication.clipboard().setText(texto))
        layout.addWidget(boton_copiar)
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.accept)
        layout.addWidget(boton_cerrar)


class PantallaOferta(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._historial: list[sqlite3.Row] = []
        self._armar_ui()
        self._cargar_profesionales()
        self._cargar_edificios()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Oferta de consultorios")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        form.addWidget(QLabel("Nueva búsqueda"))

        self.combo_profesional = QComboBox()
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_tipo = QComboBox()
        self.combo_tipo.addItem("Regular", TIPO_REGULAR)
        self.combo_tipo.addItem("Aislada", TIPO_AISLADA)
        self.combo_tipo.currentIndexChanged.connect(self._al_cambiar_tipo)
        form.addWidget(QLabel("Tipo de búsqueda"))
        form.addWidget(self.combo_tipo)

        fila_fechas = QHBoxLayout()
        self.campo_fecha_desde = QLineEdit()
        self.campo_fecha_hasta = QLineEdit()
        fila_fechas.addWidget(QLabel("Desde (AAAA-MM-DD)"))
        fila_fechas.addWidget(self.campo_fecha_desde)
        fila_fechas.addWidget(QLabel("Hasta (solo Aislada)"))
        fila_fechas.addWidget(self.campo_fecha_hasta)
        form.addLayout(fila_fechas)

        form.addWidget(QLabel("Edificios (ninguno tildado = todos)"))
        self.lista_edificios = QListWidget()
        self.lista_edificios.setMaximumHeight(100)
        form.addWidget(self.lista_edificios)

        form.addWidget(QLabel("Días"))
        self.lista_dias = QListWidget()
        for dia in DIAS_SEMANA:
            item = QListWidgetItem(dia)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.lista_dias.addItem(item)
        self.lista_dias.setMaximumHeight(140)
        form.addWidget(self.lista_dias)

        fila_horario = QHBoxLayout()
        self.spin_desde = QDoubleSpinBox()
        self.spin_desde.setRange(0, 23)
        self.spin_desde.setValue(9)
        self.spin_hasta = QDoubleSpinBox()
        self.spin_hasta.setRange(1, 24)
        self.spin_hasta.setValue(12)
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_desde)
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hasta)
        form.addLayout(fila_horario)

        fila_horas_minimas = QHBoxLayout()
        self.casilla_horas_minimas = QCheckBox("Cantidad de horas dentro del rango (en vez del rango completo)")
        self.spin_horas_minimas = QDoubleSpinBox()
        self.spin_horas_minimas.setRange(0.5, 24)
        self.spin_horas_minimas.setValue(1)
        self.spin_horas_minimas.setEnabled(False)
        self.casilla_horas_minimas.toggled.connect(self.spin_horas_minimas.setEnabled)
        fila_horas_minimas.addWidget(self.casilla_horas_minimas)
        fila_horas_minimas.addWidget(self.spin_horas_minimas)
        form.addLayout(fila_horas_minimas)

        self.combo_combinacion = QComboBox()
        for etiqueta, valor in _COMBINACIONES:
            self.combo_combinacion.addItem(etiqueta, valor)
        self.combo_combinacion.setCurrentIndex(2)
        form.addWidget(QLabel("Combinación de consultorios"))
        form.addWidget(self.combo_combinacion)

        form.addWidget(QLabel("Características pedidas"))
        self.casilla_ventana = QCheckBox("Con ventana")
        self.casilla_camilla = QCheckBox("Apto camilla")
        self.casilla_sillones = QCheckBox("Con sillones")
        for casilla in (self.casilla_ventana, self.casilla_camilla, self.casilla_sillones):
            form.addWidget(casilla)
        self.campo_tamano = QLineEdit()
        self.campo_tamano.setPlaceholderText("Tamaño (opcional)")
        form.addWidget(self.campo_tamano)

        fila_valor_maximo = QHBoxLayout()
        self.casilla_valor_maximo = QCheckBox("Valor máximo por hora regular")
        self.spin_valor_maximo = QDoubleSpinBox()
        self.spin_valor_maximo.setRange(0, 10_000_000)
        self.spin_valor_maximo.setEnabled(False)
        self.casilla_valor_maximo.toggled.connect(self.spin_valor_maximo.setEnabled)
        fila_valor_maximo.addWidget(self.casilla_valor_maximo)
        fila_valor_maximo.addWidget(self.spin_valor_maximo)
        form.addLayout(fila_valor_maximo)

        self.casilla_detalle_reducido = QCheckBox("Detalle reducido (sin identificar el consultorio puntual)")
        form.addWidget(self.casilla_detalle_reducido)

        fila_botones = QHBoxLayout()
        boton_pdf = QPushButton("Generar PDF")
        boton_pdf.setObjectName("botonPrimario")
        boton_pdf.clicked.connect(self._generar_pdf)
        boton_texto = QPushButton("Generar texto WhatsApp")
        boton_texto.clicked.connect(self._generar_texto)
        fila_botones.addWidget(boton_pdf)
        fila_botones.addWidget(boton_texto)
        form.addLayout(fila_botones)
        form.addStretch()
        splitter.addWidget(panel_form)

        panel_historial = QWidget()
        layout_historial = QVBoxLayout(panel_historial)
        layout_historial.addWidget(QLabel("Historial de búsquedas"))
        self.tabla_historial = QTableWidget()
        self.tabla_historial.setColumnCount(3)
        self.tabla_historial.setHorizontalHeaderLabels(["Fecha", "Profesional", "Tipo"])
        self.tabla_historial.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_historial.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_historial.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout_historial.addWidget(self.tabla_historial, stretch=1)

        fila_regenerar = QHBoxLayout()
        boton_regenerar_pdf = QPushButton("Regenerar PDF")
        boton_regenerar_pdf.clicked.connect(self._regenerar_pdf_seleccionado)
        boton_regenerar_texto = QPushButton("Regenerar texto WhatsApp")
        boton_regenerar_texto.clicked.connect(self._regenerar_texto_seleccionado)
        fila_regenerar.addWidget(boton_regenerar_pdf)
        fila_regenerar.addWidget(boton_regenerar_texto)
        fila_regenerar.addStretch()
        layout_historial.addLayout(fila_regenerar)
        splitter.addWidget(panel_historial)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, stretch=1)
        self._al_cambiar_tipo()

    def _cargar_profesionales(self) -> None:
        self.combo_profesional.clear()
        for f in self.conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido"):
            nombre = f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", ")
            self.combo_profesional.addItem(nombre, f["IdProfesional"])

    def _cargar_edificios(self) -> None:
        self.lista_edificios.clear()
        for f in self.conn.execute("SELECT IdEdificio, Nombre FROM Edificio ORDER BY Nombre"):
            item = QListWidgetItem(f["Nombre"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, f["IdEdificio"])
            self.lista_edificios.addItem(item)

    def _al_cambiar_tipo(self) -> None:
        tipo = self.combo_tipo.currentData()
        self.campo_fecha_desde.setText(fecha_inicio_default(self.conn, tipo))
        self.campo_fecha_hasta.setText(fecha_fin_default(tipo, self.campo_fecha_desde.text()) or "")
        self.campo_fecha_hasta.setEnabled(tipo == TIPO_AISLADA)

    def _dias_seleccionados(self) -> list[str]:
        return [
            self.lista_dias.item(i).text()
            for i in range(self.lista_dias.count())
            if self.lista_dias.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _ids_edificio_seleccionados(self) -> list[int]:
        return [
            self.lista_edificios.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.lista_edificios.count())
            if self.lista_edificios.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _armar_criterios(self) -> tuple[int, CriteriosGlobales, list[Busqueda]] | None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Oferta de consultorios", "No hay profesionales cargados.")
            return None
        dias = self._dias_seleccionados()
        if not dias:
            QMessageBox.warning(self, "Oferta de consultorios", "Elegí al menos un día.")
            return None

        tipo = self.combo_tipo.currentData()
        globales = CriteriosGlobales(
            tipo_busqueda=tipo,
            ids_edificio=self._ids_edificio_seleccionados(),
            detalle_reducido=self.casilla_detalle_reducido.isChecked(),
        )
        busqueda = Busqueda(
            fecha_desde=self.campo_fecha_desde.text().strip(),
            fecha_hasta=(self.campo_fecha_hasta.text().strip() or None) if tipo == TIPO_AISLADA else None,
            dias=dias,
            hora_desde=self.spin_desde.value(),
            hora_hasta=self.spin_hasta.value(),
            combinacion=self.combo_combinacion.currentData(),
            apto_camilla=self.casilla_camilla.isChecked(),
            ventana=self.casilla_ventana.isChecked(),
            sillones=self.casilla_sillones.isChecked(),
            tamano=self.campo_tamano.text().strip() or None,
            valor_maximo_hora=self.spin_valor_maximo.value() if self.casilla_valor_maximo.isChecked() else None,
            cantidad_horas_minimas=self.spin_horas_minimas.value() if self.casilla_horas_minimas.isChecked() else None,
        )
        return id_profesional, globales, [busqueda]

    def _guardar_y_generar(self, generador) -> None:
        armado = self._armar_criterios()
        if armado is None:
            return
        id_profesional, globales, busquedas = armado
        try:
            id_historial = guardar_busqueda(
                self.conn, id_profesional, globales, busquedas, set(), fecha_actual(self.conn).isoformat(),
            )
            generador(id_historial)
        except ValueError as error:
            QMessageBox.warning(self, "Oferta de consultorios", str(error))
            return
        self.actualizar()

    def _generar_pdf(self) -> None:
        def hacer(id_historial: int) -> None:
            directorio = str(carpeta_archivos_varios(self.conn, SUBCARPETA_OFERTA))
            ruta = regenerar_pdf(self.conn, id_historial, directorio)
            QMessageBox.information(self, "Oferta de consultorios", f"Se generó:\n{ruta}")
        self._guardar_y_generar(hacer)

    def _generar_texto(self) -> None:
        def hacer(id_historial: int) -> None:
            texto = regenerar_texto(self.conn, id_historial)
            _DialogoTexto(texto, self).exec()
        self._guardar_y_generar(hacer)

    def actualizar(self) -> None:
        self._historial = obtener_repositorio(self.conn, "HistorialOferta").listar()
        self._historial.sort(key=lambda h: h["IdHistorialOferta"], reverse=True)
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        self.tabla_historial.setRowCount(len(self._historial))
        for fila_idx, h in enumerate(self._historial):
            profesional = repo_profesional.obtener(h["IdProfesional"])
            nombre = nombre_para_mensaje(profesional) if profesional else "?"
            self.tabla_historial.setItem(fila_idx, 0, QTableWidgetItem(h["FechaGeneracion"] or ""))
            self.tabla_historial.setItem(fila_idx, 1, QTableWidgetItem(nombre))
            tipo = json.loads(h["CriteriosJSON"])["globales"]["tipo_busqueda"]
            self.tabla_historial.setItem(fila_idx, 2, QTableWidgetItem(tipo))
        self.tabla_historial.resizeColumnsToContents()

    def _historial_seleccionado(self) -> sqlite3.Row | None:
        filas = self.tabla_historial.selectionModel().selectedRows()
        if not filas:
            QMessageBox.information(self, "Oferta de consultorios", "Seleccioná una búsqueda del historial.")
            return None
        return self._historial[filas[0].row()]

    def _regenerar_pdf_seleccionado(self) -> None:
        h = self._historial_seleccionado()
        if h is None:
            return
        try:
            directorio = str(carpeta_archivos_varios(self.conn, SUBCARPETA_OFERTA))
            ruta = regenerar_pdf(self.conn, h["IdHistorialOferta"], directorio)
        except ValueError as error:
            QMessageBox.warning(self, "Oferta de consultorios", str(error))
            return
        QMessageBox.information(self, "Oferta de consultorios", f"Se regeneró:\n{ruta}")

    def _regenerar_texto_seleccionado(self) -> None:
        h = self._historial_seleccionado()
        if h is None:
            return
        try:
            texto = regenerar_texto(self.conn, h["IdHistorialOferta"])
        except ValueError as error:
            QMessageBox.warning(self, "Oferta de consultorios", str(error))
            return
        _DialogoTexto(texto, self).exec()
