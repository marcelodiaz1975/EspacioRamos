"""Lista de espera (F12, sección 3.21 y DC-08 §2 / DC-10 §2): alta de
pedidos y cruce automático contra la disponibilidad real del período en
curso, reusando app.negocio.lista_espera. El mismo formulario de pedido
también arma, sin necesidad de persistirlo, el mensaje "Disponibilidad de
horarios regulares" (sección 5.2, Mensaje 2 de DC-03), con la opción de
regenerar además el PDF de disponibilidad con fotos.

A diferencia del Mensaje 1 (detalle de aisladas, que decide solo si
mencionar el edificio según las llaves del profesional — no hay
checkboxes ahí), el Mensaje 2 no está atado a un profesional en
particular, así que la "regla del edificio" (`mensajes._incluir_edificio_efectivo`)
solo aplica el primer nivel (un solo edificio en el espacio -> se omite
siempre) y para el resto queda a criterio manual del operador: de ahí los
tres checkboxes "Incluir consultorio/unidad/edificio" de acá abajo.

Un pedido puede necesitar varios bloques día(s)+horario a la vez (ej.
"martes o jueves 3hs entre 14 y 18hs" Y "sábado de 9 a 12hs"): los campos
de día/horario/cantidad de horas/combinación de días arman UN bloque por
vez, "Agregar bloque…" lo suma a la tabla de bloques del pedido, y
"Combinación de bloques" define si hace falta que se den todos (Y) o
alcanza con uno (O) — irrelevante con un solo bloque. Al crear el pedido
se toman los bloques ya agregados a la tabla MÁS el que esté cargado en
ese momento en el formulario (si tiene algún día tildado) — así el caso
común de un solo bloque sigue siendo un único paso, sin tener que pasar
por "Agregar bloque…", y agregar uno de más antes de crear tampoco se
pierde."""
from __future__ import annotations

import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from app.negocio.archivos_generados import SUBCARPETA_DISPONIBILIDAD, carpeta_archivos_varios
from app.negocio.dias import DIAS_SEMANA, periodo_actual
from app.negocio.lista_espera import crear_pedido, listar_pedidos_con_coincidencia, marcar_descartado, marcar_resuelto
from app.negocio.mensajes import (
    mensaje_disponibilidad_horarios,
    mensaje_disponibilidad_horarios_fecha,
    nombre_para_mensaje,
)
from app.pdf.disponibilidad_pdf import generar_pdfs_disponibilidad_por_localidad
from app.repositorio.registro import obtener_repositorio

_COLOR_CELDA = {"verde": "#4CAF50", "amarillo": "#F5D547", "naranja": "#E07B39", "rojo": "#C0392B"}
_ETIQUETA_COLOR = {
    "verde": "Un consultorio cubre todo",
    "amarillo": "Combinar, misma unidad",
    "naranja": "Combinar, mismo edificio",
    "rojo": "Combinar, distinto edificio",
}
_DIAS_PEDIDO = DIAS_SEMANA[:6]


class PantallaListaEspera(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._pedidos: list[sqlite3.Row] = []
        self._bloques_pendientes: list[dict] = []
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        titulo = QLabel("Lista de espera")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        form.addWidget(QLabel("Nuevo pedido"))

        self.combo_profesional = QComboBox()
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_tipo = QComboBox()
        self.combo_tipo.addItem("Alcanza con un día (O)", "O")
        self.combo_tipo.addItem("Todos los días (Y)", "Y")
        form.addWidget(QLabel("Combinación de días"))
        form.addWidget(self.combo_tipo)

        form.addWidget(QLabel("Días"))
        self.lista_dias = QListWidget()
        for dia in _DIAS_PEDIDO:
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

        fila_cantidad_horas = QHBoxLayout()
        self.casilla_cantidad_horas = QCheckBox("Cantidad de horas dentro del rango (en vez del rango completo)")
        self.spin_cantidad_horas = QDoubleSpinBox()
        self.spin_cantidad_horas.setRange(0.5, 24)
        self.spin_cantidad_horas.setValue(1)
        self.spin_cantidad_horas.setEnabled(False)
        self.casilla_cantidad_horas.toggled.connect(self.spin_cantidad_horas.setEnabled)
        fila_cantidad_horas.addWidget(self.casilla_cantidad_horas)
        fila_cantidad_horas.addWidget(self.spin_cantidad_horas)
        form.addLayout(fila_cantidad_horas)

        boton_agregar_bloque = QPushButton("Agregar bloque…")
        boton_agregar_bloque.clicked.connect(self._agregar_bloque)
        form.addWidget(boton_agregar_bloque)

        form.addWidget(QLabel("Bloques del pedido (si no se agrega ninguno, se usa el de arriba)"))
        self.tabla_bloques = QTableWidget()
        self.tabla_bloques.setColumnCount(3)
        self.tabla_bloques.setHorizontalHeaderLabels(["Días", "Horario", "Combinación de días"])
        self.tabla_bloques.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_bloques.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_bloques.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_bloques.setMaximumHeight(120)
        form.addWidget(self.tabla_bloques)
        boton_quitar_bloque = QPushButton("Quitar bloque")
        boton_quitar_bloque.clicked.connect(self._quitar_bloque)
        form.addWidget(boton_quitar_bloque)

        self.combo_tipo_bloques = QComboBox()
        self.combo_tipo_bloques.addItem("Alcanza con un bloque (O)", "O")
        self.combo_tipo_bloques.addItem("Todos los bloques (Y)", "Y")
        form.addWidget(QLabel("Combinación de bloques (irrelevante con uno solo)"))
        form.addWidget(self.combo_tipo_bloques)

        form.addWidget(QLabel("Características pedidas"))
        self.casilla_ventana = QCheckBox("Con ventana")
        self.casilla_camilla = QCheckBox("Apto camilla")
        self.casilla_balcon = QCheckBox("Con balcón")
        self.casilla_aire = QCheckBox("Con aire acondicionado")
        self.casilla_sin_combinar = QCheckBox("Sin combinación de consultorios")
        for casilla in (
            self.casilla_ventana, self.casilla_camilla, self.casilla_balcon, self.casilla_aire,
            self.casilla_sin_combinar,
        ):
            form.addWidget(casilla)
        self.campo_tamano = QLineEdit()
        self.campo_tamano.setPlaceholderText("Tamaño (opcional)")
        form.addWidget(self.campo_tamano)

        self.campo_detalle = QPlainTextEdit()
        self.campo_detalle.setFixedHeight(60)
        form.addWidget(QLabel("Detalle"))
        form.addWidget(self.campo_detalle)

        boton_crear = QPushButton("Crear pedido")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.clicked.connect(self._crear_pedido)
        form.addWidget(boton_crear)

        form.addWidget(QLabel("Mensaje de disponibilidad — qué incluir en cada alternativa"))
        self.casilla_incluir_consultorio = QCheckBox("Incluir consultorio")
        self.casilla_incluir_consultorio.setChecked(True)
        self.casilla_incluir_unidad = QCheckBox("Incluir unidad")
        self.casilla_incluir_unidad.setChecked(True)
        self.casilla_incluir_edificio = QCheckBox("Incluir edificio")
        self.casilla_incluir_edificio.setChecked(True)
        for casilla in (self.casilla_incluir_consultorio, self.casilla_incluir_unidad, self.casilla_incluir_edificio):
            form.addWidget(casilla)

        self.casilla_pdf_disponibilidad = QCheckBox("Generar también como PDF con fotos")
        form.addWidget(self.casilla_pdf_disponibilidad)
        boton_mensaje_disponibilidad = QPushButton("Generar mensaje de disponibilidad (por día de semana)")
        boton_mensaje_disponibilidad.clicked.connect(self._generar_mensaje_disponibilidad)
        form.addWidget(boton_mensaje_disponibilidad)

        form.addWidget(QLabel("Variante B: disponibilidad por fecha(s) puntual(es) en vez de día de semana"))
        self.campo_fechas = QLineEdit()
        self.campo_fechas.setPlaceholderText("AAAA-MM-DD, AAAA-MM-DD, … (separadas por coma)")
        form.addWidget(self.campo_fechas)
        self.combo_tipo_fechas = QComboBox()
        self.combo_tipo_fechas.addItem("Alcanza con una fecha (O)", "O")
        self.combo_tipo_fechas.addItem("Todas las fechas (Y)", "Y")
        form.addWidget(self.combo_tipo_fechas)
        boton_mensaje_disponibilidad_fecha = QPushButton("Generar mensaje de disponibilidad (por fecha puntual)")
        boton_mensaje_disponibilidad_fecha.clicked.connect(self._generar_mensaje_disponibilidad_fecha)
        form.addWidget(boton_mensaje_disponibilidad_fecha)

        form.addStretch()
        splitter.addWidget(panel_form)

        panel_tabla = QWidget()
        layout_tabla = QVBoxLayout(panel_tabla)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["Profesional", "Días", "Horario", "Coincidencia", "Detalle"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout_tabla.addWidget(self.tabla, stretch=1)

        fila_acciones = QHBoxLayout()
        boton_resolver = QPushButton("Marcar resuelto")
        boton_resolver.clicked.connect(self._resolver)
        boton_descartar = QPushButton("Descartar")
        boton_descartar.clicked.connect(self._descartar)
        fila_acciones.addWidget(boton_resolver)
        fila_acciones.addWidget(boton_descartar)
        fila_acciones.addStretch()
        layout_tabla.addLayout(fila_acciones)

        layout_tabla.addWidget(QLabel("Mensaje de disponibilidad generado (a partir del formulario de arriba)"))
        self.texto_mensaje_disponibilidad = QPlainTextEdit()
        self.texto_mensaje_disponibilidad.setFixedHeight(120)
        layout_tabla.addWidget(self.texto_mensaje_disponibilidad)
        boton_copiar_disponibilidad = QPushButton("Copiar mensaje")
        boton_copiar_disponibilidad.clicked.connect(self._copiar_mensaje_disponibilidad)
        layout_tabla.addWidget(boton_copiar_disponibilidad)

        splitter.addWidget(panel_tabla)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, stretch=1)
        self._cargar_profesionales()

    def _cargar_profesionales(self) -> None:
        self.combo_profesional.clear()
        for f in self.conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido"):
            nombre = f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", ")
            self.combo_profesional.addItem(nombre, f["IdProfesional"])

    def actualizar(self) -> None:
        periodo = periodo_actual(self.conn)
        anio, mes = (int(p) for p in periodo.split("-"))
        resultado = listar_pedidos_con_coincidencia(self.conn, anio, mes)
        self._pedidos = [p for p, _ in resultado]

        self.tabla.setRowCount(len(resultado))
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        repo_bloque = obtener_repositorio(self.conn, "ListaEsperaBloque")
        for fila_idx, (pedido, coincidencia) in enumerate(resultado):
            profesional = repo_profesional.obtener(pedido["IdProfesional"])
            nombre = nombre_para_mensaje(profesional) if profesional else "?"
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(nombre))

            bloques = repo_bloque.listar(IdPedido=pedido["IdPedido"])
            separador = " Y " if pedido["TipoCombinacion"] == "Y" else " O "
            self.tabla.setItem(
                fila_idx, 1,
                QTableWidgetItem(separador.join(", ".join(json.loads(b["Dias"] or "[]")) for b in bloques)),
            )
            self.tabla.setItem(
                fila_idx, 2,
                QTableWidgetItem(separador.join(f"{b['HorarioDesde']:g} a {b['HorarioHasta']:g}" for b in bloques)),
            )

            color = coincidencia.color if coincidencia else None
            item_color = QTableWidgetItem(_ETIQUETA_COLOR.get(color, "Sin cobertura"))
            if color:
                item_color.setBackground(QColor(_COLOR_CELDA[color]))
            self.tabla.setItem(fila_idx, 3, item_color)
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(pedido["Detalle"] or ""))
        self.tabla.resizeColumnsToContents()

    def _dias_seleccionados(self) -> list[str]:
        return [
            self.lista_dias.item(i).text()
            for i in range(self.lista_dias.count())
            if self.lista_dias.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _condiciones(self) -> dict:
        condiciones = {}
        if self.casilla_ventana.isChecked():
            condiciones["ventana"] = True
        if self.casilla_camilla.isChecked():
            condiciones["aptoCamilla"] = True
        if self.casilla_balcon.isChecked():
            condiciones["balcon"] = True
        if self.casilla_aire.isChecked():
            condiciones["aire"] = True
        if self.casilla_sin_combinar.isChecked():
            condiciones["sinCombinar"] = True
        if self.campo_tamano.text().strip():
            condiciones["tamano"] = self.campo_tamano.text().strip()
        return condiciones

    def _generar_mensaje_disponibilidad(self) -> None:
        """Sección 5.2: arma "Disponibilidad período {MM/AAAA}" con los
        mismos campos del formulario de pedido, sin necesidad de crear un
        pedido en Lista de espera. El checkbox "PDF con fotos" además
        regenera el PDF de disponibilidad general (Archivos varios) para
        adjuntar junto al mensaje."""
        dias = self._dias_seleccionados()
        if not dias:
            QMessageBox.warning(self, "Generar mensaje de disponibilidad", "Elegí al menos un día.")
            return
        try:
            texto = mensaje_disponibilidad_horarios(
                self.conn, periodo=periodo_actual(self.conn), dias=dias,
                horario_desde=self.spin_desde.value(), horario_hasta=self.spin_hasta.value(),
                tipo_combinacion=self.combo_tipo.currentData(), condiciones_consultorio=self._condiciones(),
                incluir_consultorio=self.casilla_incluir_consultorio.isChecked(),
                incluir_unidad=self.casilla_incluir_unidad.isChecked(),
                incluir_edificio=self.casilla_incluir_edificio.isChecked(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Generar mensaje de disponibilidad", str(error))
            return
        self.texto_mensaje_disponibilidad.setPlainText(texto)

        if self.casilla_pdf_disponibilidad.isChecked():
            directorio = str(carpeta_archivos_varios(self.conn, SUBCARPETA_DISPONIBILIDAD))
            rutas = generar_pdfs_disponibilidad_por_localidad(self.conn, directorio)
            QMessageBox.information(
                self, "PDF de disponibilidad",
                f"Se generó {len(rutas)} archivo(s) en:\n{directorio}",
            )

    def _fechas_ingresadas(self) -> list[str]:
        return [f.strip() for f in self.campo_fechas.text().split(",") if f.strip()]

    def _generar_mensaje_disponibilidad_fecha(self) -> None:
        """Variante B del Mensaje 2 (DC-03 sección 5.2): igual que
        `_generar_mensaje_disponibilidad`, pero cruzando fecha(s) puntual(es)
        contra la ocupación real de cada una (respeta ausencias puntuales y
        reservas aisladas ya confirmadas), no el patrón semanal genérico."""
        fechas = self._fechas_ingresadas()
        if not fechas:
            QMessageBox.warning(self, "Generar mensaje de disponibilidad", "Ingresá al menos una fecha (AAAA-MM-DD).")
            return
        try:
            texto = mensaje_disponibilidad_horarios_fecha(
                self.conn, fechas=fechas,
                horario_desde=self.spin_desde.value(), horario_hasta=self.spin_hasta.value(),
                tipo_combinacion=self.combo_tipo_fechas.currentData(), condiciones_consultorio=self._condiciones(),
                incluir_consultorio=self.casilla_incluir_consultorio.isChecked(),
                incluir_unidad=self.casilla_incluir_unidad.isChecked(),
                incluir_edificio=self.casilla_incluir_edificio.isChecked(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Generar mensaje de disponibilidad", str(error))
            return
        self.texto_mensaje_disponibilidad.setPlainText(texto)

        if self.casilla_pdf_disponibilidad.isChecked():
            directorio = str(carpeta_archivos_varios(self.conn, SUBCARPETA_DISPONIBILIDAD))
            rutas = generar_pdfs_disponibilidad_por_localidad(self.conn, directorio)
            QMessageBox.information(
                self, "PDF de disponibilidad",
                f"Se generó {len(rutas)} archivo(s) en:\n{directorio}",
            )

    def _copiar_mensaje_disponibilidad(self) -> None:
        QGuiApplication.clipboard().setText(self.texto_mensaje_disponibilidad.toPlainText())

    def _bloque_del_formulario(self) -> dict:
        return {
            "dias": self._dias_seleccionados(), "horario_desde": self.spin_desde.value(),
            "horario_hasta": self.spin_hasta.value(), "tipo_combinacion_dias": self.combo_tipo.currentData(),
            "cantidad_horas_requeridas": (
                self.spin_cantidad_horas.value() if self.casilla_cantidad_horas.isChecked() else None
            ),
        }

    def _refrescar_tabla_bloques(self) -> None:
        self.tabla_bloques.setRowCount(len(self._bloques_pendientes))
        for fila_idx, bloque in enumerate(self._bloques_pendientes):
            self.tabla_bloques.setItem(fila_idx, 0, QTableWidgetItem(", ".join(bloque["dias"])))
            self.tabla_bloques.setItem(
                fila_idx, 1, QTableWidgetItem(f"{bloque['horario_desde']:g} a {bloque['horario_hasta']:g}"),
            )
            etiqueta_tipo = "Todos los días (Y)" if bloque["tipo_combinacion_dias"] == "Y" else "Alcanza con un día (O)"
            self.tabla_bloques.setItem(fila_idx, 2, QTableWidgetItem(etiqueta_tipo))
        self.tabla_bloques.resizeColumnsToContents()

    def _agregar_bloque(self) -> None:
        bloque = self._bloque_del_formulario()
        if not bloque["dias"]:
            QMessageBox.warning(self, "Agregar bloque", "Elegí al menos un día para el bloque.")
            return
        self._bloques_pendientes.append(bloque)
        self._refrescar_tabla_bloques()
        for i in range(self.lista_dias.count()):
            self.lista_dias.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _quitar_bloque(self) -> None:
        filas = self.tabla_bloques.selectionModel().selectedRows()
        if not filas:
            return
        del self._bloques_pendientes[filas[0].row()]
        self._refrescar_tabla_bloques()

    def _crear_pedido(self) -> None:
        id_profesional = self.combo_profesional.currentData()
        if id_profesional is None:
            QMessageBox.warning(self, "Crear pedido", "No hay profesionales cargados.")
            return
        bloques = list(self._bloques_pendientes)
        if self._dias_seleccionados():
            bloques.append(self._bloque_del_formulario())
        try:
            crear_pedido(
                self.conn, id_profesional=id_profesional,
                tipo_combinacion_bloques=self.combo_tipo_bloques.currentData(), bloques=bloques,
                condiciones_consultorio=self._condiciones(),
                detalle=self.campo_detalle.toPlainText().strip() or None,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Crear pedido", str(error))
            return
        self.conn.commit()
        self._bloques_pendientes = []
        self._refrescar_tabla_bloques()
        self.actualizar()

    def _fila_seleccionada_pedido(self) -> sqlite3.Row | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._pedidos[filas[0].row()]

    def _resolver(self) -> None:
        pedido = self._fila_seleccionada_pedido()
        if pedido is None:
            return
        marcar_resuelto(self.conn, pedido["IdPedido"])
        self.conn.commit()
        self.actualizar()

    def _descartar(self) -> None:
        pedido = self._fila_seleccionada_pedido()
        if pedido is None:
            return
        marcar_descartado(self.conn, pedido["IdPedido"])
        self.conn.commit()
        self.actualizar()
