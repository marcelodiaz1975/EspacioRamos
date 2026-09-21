"""Importar planilla (FA5): carga masiva de datos iniciales desde el Excel
de plantilla (app.importacion.importar_excel) y, al terminar, corre el
informe de integridad (app.importacion.informe_integridad) para juntar en
un solo lugar los casos que conviene revisar a mano — códigos de
profesional duplicados y reservas regulares superpuestas — que la carga
masiva no bloquea a propósito (ver el docstring de ese módulo).

Formato solapa (revisión uno por uno): columna izquierda de ancho fijo
con "Elegir archivo", "Importar" (`botonPrimario` — es la acción que
efectivamente escribe algo) y "Descargar planilla importación"
(`botonSecundario`, primera vez que `app.importacion.plantillas.
generar_plantillas` se cuelga de la GUI — antes solo estaba disponible
por línea de comandos, `main.py generar-plantillas`); a la derecha, los
tres cuadros de resultado (tabla por hoja, errores, informe de
integridad)."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.items_tabla import item_numero
from app.importacion.importar_excel import importar_planilla
from app.importacion.informe_integridad import generar_informe_integridad
from app.importacion.plantillas import generar_plantillas

_ANCHO_BOTON = 260  # "Descargar planilla importación", el texto más largo de la columna


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


class PantallaImportacion(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar": el
        QTabWidget contenedor todavía no está mostrado en ese momento
        (mismo motivo que Reservas/Liquidación/Archivos varios)."""
        super().showEvent(event)
        self.boton_elegir.setFocus()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Importar planilla")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        solapas = QTabWidget()
        panel_solapa = QWidget()
        panel_solapa.setObjectName("panelSolapa")
        layout_solapa = QHBoxLayout(panel_solapa)

        panel_izquierda = QWidget()
        columna = QVBoxLayout(panel_izquierda)
        columna.setContentsMargins(0, 0, 0, 0)

        subtitulo = QLabel(
            "Carga masiva de Edificios, Unidades, Consultorios, Profesiones, Profesionales, "
            "Reservas regulares, Llaves, Placas, Fechas especiales, Responsables y Planes de "
            "pago ya en curso desde la planilla Excel de plantilla."
        )
        subtitulo.setObjectName("subtitulo")
        subtitulo.setWordWrap(True)
        subtitulo.setFixedWidth(_ANCHO_BOTON)
        columna.addWidget(subtitulo)

        self.boton_elegir = QPushButton("Elegir archivo...")
        self.boton_elegir.setObjectName("botonSecundario")
        self.boton_elegir.clicked.connect(self._elegir_archivo)
        columna.addWidget(self.boton_elegir)

        columna.addWidget(_titulo_campo("Archivo elegido"))
        self.campo_ruta = QLineEdit()
        self.campo_ruta.setReadOnly(True)
        columna.addWidget(self.campo_ruta)

        self.boton_importar = QPushButton("Importar")
        self.boton_importar.setObjectName("botonPrimario")
        self.boton_importar.setEnabled(False)
        self.boton_importar.clicked.connect(self._importar)
        columna.addWidget(self.boton_importar)

        self.boton_descargar_plantilla = QPushButton("Descargar planilla importación")
        self.boton_descargar_plantilla.setObjectName("botonSecundario")
        self.boton_descargar_plantilla.clicked.connect(self._descargar_plantilla)
        columna.addWidget(self.boton_descargar_plantilla)

        for widget in (self.boton_elegir, self.campo_ruta, self.boton_importar, self.boton_descargar_plantilla):
            widget.setFixedWidth(_ANCHO_BOTON)

        columna.addStretch()
        layout_solapa.addWidget(panel_izquierda)

        self._foco = instalar_enter_avanza_foco(
            [self.boton_elegir, self.boton_importar, self.boton_descargar_plantilla], parent=self,
        )

        columna_derecha = QVBoxLayout()
        columna_derecha.addWidget(_titulo_campo("Resultado por hoja"))
        self.tabla_resultados = QTableWidget()
        self.tabla_resultados.setColumnCount(3)
        self.tabla_resultados.setHorizontalHeaderLabels(["Hoja", "Filas importadas", "Errores"])
        self.tabla_resultados.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        columna_derecha.addWidget(self.tabla_resultados)

        self.texto_errores = QPlainTextEdit()
        self.texto_errores.setReadOnly(True)
        self.texto_errores.setPlaceholderText("Sin errores de importación todavía.")
        columna_derecha.addWidget(self.texto_errores)

        columna_derecha.addWidget(_titulo_campo("Informe de integridad (no bloquea la importación — para revisar a mano)"))
        self.texto_integridad = QPlainTextEdit()
        self.texto_integridad.setReadOnly(True)
        self.texto_integridad.setPlaceholderText("Se completa después de importar.")
        columna_derecha.addWidget(self.texto_integridad)

        layout_solapa.addLayout(columna_derecha, stretch=1)

        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel_solapa)
        solapas.addTab(scroll, "Importación")
        solapas.tabBar().setDrawBase(False)
        layout.addWidget(solapas, stretch=1)

    def _elegir_archivo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegir planilla", "", "Excel (*.xlsx)")
        if ruta:
            self.campo_ruta.setText(ruta)
            self.boton_importar.setEnabled(True)

    def _descargar_plantilla(self) -> None:
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Descargar planilla de importación", "Plantilla_Importacion_EspacioRamos.xlsx", "Excel (*.xlsx)",
        )
        if not ruta:
            return
        try:
            generar_plantillas(ruta)
        except OSError as exc:
            QMessageBox.critical(self, "Descargar planilla", f"No se pudo generar la planilla: {exc}")
            return
        QMessageBox.information(self, "Descargar planilla", f"Planilla generada en: {ruta}")

    def _importar(self) -> None:
        ruta = self.campo_ruta.text().strip()
        if not ruta:
            return
        try:
            resultados = importar_planilla(self.conn, ruta)
        except Exception as exc:
            QMessageBox.critical(self, "Importar planilla", f"No se pudo leer el archivo: {exc}")
            return
        self.conn.commit()

        self.tabla_resultados.setRowCount(len(resultados))
        lineas_error = []
        for i, r in enumerate(resultados):
            self.tabla_resultados.setItem(i, 0, QTableWidgetItem(r.entidad))
            self.tabla_resultados.setItem(i, 1, item_numero(str(r.filas_importadas)))
            self.tabla_resultados.setItem(i, 2, item_numero(str(len(r.errores))))
            for err in r.errores:
                lineas_error.append(f"[{r.entidad}] {err}")
        self.tabla_resultados.resizeColumnsToContents()
        self.texto_errores.setPlainText("\n".join(lineas_error))

        informe = generar_informe_integridad(self.conn)
        self.texto_integridad.setPlainText(self._texto_informe(informe))

        total_importadas = sum(r.filas_importadas for r in resultados)
        total_errores = len(lineas_error)
        QMessageBox.information(
            self, "Importación terminada",
            f"Se importaron {total_importadas} filas en total, con {total_errores} error(es). "
            f"El informe de integridad encontró {informe.total} caso(s) para revisar.",
        )

    def _texto_informe(self, informe) -> str:
        if informe.total == 0:
            return "Sin observaciones."
        lineas = []
        for dup in informe.codigos_duplicados:
            nombres = ", ".join(f"#{idp} {ap}" for idp, ap in dup.profesionales)
            lineas.append(f"Código de profesional duplicado '{dup.codigo}': {nombres}")
        for sup in informe.reservas_superpuestas:
            lineas.append(
                f"Reservas superpuestas en consultorio #{sup.id_consultorio} los {sup.dia_semana}: "
                f"#{sup.reserva_a['IdReservaRegular']} y #{sup.reserva_b['IdReservaRegular']} "
                f"(profesionales #{sup.reserva_a['IdProfesional']} y #{sup.reserva_b['IdProfesional']})"
            )
        return "\n".join(lineas)
