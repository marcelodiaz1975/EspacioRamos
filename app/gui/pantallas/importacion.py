"""Importar planilla (FA5): carga masiva de datos iniciales desde el Excel
de plantilla (app.importacion.importar_excel) y, al terminar, corre el
informe de integridad (app.importacion.informe_integridad) para juntar en
un solo lugar los casos que conviene revisar a mano — códigos de
profesional duplicados y reservas regulares superpuestas — que la carga
masiva no bloquea a propósito (ver el docstring de ese módulo)."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.importacion.importar_excel import importar_planilla
from app.importacion.informe_integridad import generar_informe_integridad


class PantallaImportacion(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Importar planilla")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        subtitulo = QLabel(
            "Carga masiva de Edificios, Unidades, Consultorios, Profesiones, Profesionales, "
            "Reservas regulares, Llaves, Placas, Fechas especiales, Responsables y Planes de "
            "pago ya en curso desde la planilla Excel de plantilla."
        )
        subtitulo.setObjectName("subtitulo")
        subtitulo.setWordWrap(True)
        layout.addWidget(subtitulo)

        fila_archivo = QHBoxLayout()
        self.campo_ruta = QLineEdit()
        self.campo_ruta.setReadOnly(True)
        fila_archivo.addWidget(self.campo_ruta, stretch=1)
        boton_elegir = QPushButton("Elegir archivo...")
        boton_elegir.clicked.connect(self._elegir_archivo)
        fila_archivo.addWidget(boton_elegir)
        self.boton_importar = QPushButton("Importar")
        self.boton_importar.setObjectName("botonPrimario")
        self.boton_importar.setEnabled(False)
        self.boton_importar.clicked.connect(self._importar)
        fila_archivo.addWidget(self.boton_importar)
        layout.addLayout(fila_archivo)

        layout.addWidget(QLabel("Resultado por hoja"))
        self.tabla_resultados = QTableWidget()
        self.tabla_resultados.setColumnCount(3)
        self.tabla_resultados.setHorizontalHeaderLabels(["Hoja", "Filas importadas", "Errores"])
        self.tabla_resultados.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla_resultados)

        self.texto_errores = QPlainTextEdit()
        self.texto_errores.setReadOnly(True)
        self.texto_errores.setPlaceholderText("Sin errores de importación todavía.")
        layout.addWidget(self.texto_errores)

        layout.addWidget(QLabel("Informe de integridad (no bloquea la importación — para revisar a mano)"))
        self.texto_integridad = QPlainTextEdit()
        self.texto_integridad.setReadOnly(True)
        self.texto_integridad.setPlaceholderText("Se completa después de importar.")
        layout.addWidget(self.texto_integridad)

    def _elegir_archivo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegir planilla", "", "Excel (*.xlsx)")
        if ruta:
            self.campo_ruta.setText(ruta)
            self.boton_importar.setEnabled(True)

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
            self.tabla_resultados.setItem(i, 1, QTableWidgetItem(str(r.filas_importadas)))
            self.tabla_resultados.setItem(i, 2, QTableWidgetItem(str(len(r.errores))))
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
