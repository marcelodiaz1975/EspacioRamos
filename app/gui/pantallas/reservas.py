"""Reservas regulares y aisladas (F16/F17, secciones 3.9-3.10): reusa
app.negocio.reservas para el alta (con toda la validación de conflictos,
bloques rígidos y ausencias) y la cancelación de aisladas, en vez de
escribir directamente en las tablas."""
from __future__ import annotations

import sqlite3

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.dialogos import confirmar_si_fecha_es_mes_anterior
from app.gui.widgets.grilla_operativa import GrillaOperativaWidget
from app.negocio.dias import DIAS_SEMANA, fecha_actual, periodo_actual
from app.negocio.lista_espera import marcar_resuelto
from app.negocio.liquidaciones import regenerar_si_corresponde
from app.negocio.mensajes import mensaje_detalle_reserva_aislada
from app.negocio.reservas import (
    ConflictoBloqueanteError,
    cancelar_reserva_aislada,
    crear_reserva_aislada,
    crear_reserva_regular,
)
from app.repositorio.registro import obtener_repositorio

_DIAS_RESERVA = DIAS_SEMANA[:6]


def _opciones_profesional(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido").fetchall()
    return [(f["IdProfesional"], f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", ")) for f in filas]


def _opciones_consultorio(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute(
        "SELECT c.IdConsultorio, c.NumeroConsultorio, u.Departamento, e.Nombre AS Edificio "
        "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio ORDER BY e.Nombre, u.Departamento, c.NumeroConsultorio"
    ).fetchall()
    return [
        (f["IdConsultorio"], f"{f['Edificio']} — {f['Departamento']} — Consultorio {f['NumeroConsultorio']}")
        for f in filas
    ]


class PantallaReservas(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        layout = QVBoxLayout(self)
        titulo = QLabel("Reservas")
        titulo.setObjectName("tituloPantalla")
        layout.addWidget(titulo)

        pestanas = QTabWidget()
        self.panel_regulares = _PanelReservasRegulares(conn)
        self.panel_aisladas = _PanelReservasAisladas(conn)
        pestanas.addTab(self.panel_regulares, "Regulares")
        pestanas.addTab(self.panel_aisladas, "Aisladas")
        layout.addWidget(pestanas, stretch=1)

    def actualizar(self) -> None:
        self.panel_regulares.actualizar()
        self.panel_aisladas.actualizar()


class _PanelReservasRegulares(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._reservas: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        self.combo_profesional = QComboBox()
        for id_, etiqueta in _opciones_profesional(self.conn):
            self.combo_profesional.addItem(etiqueta, id_)
        self.combo_profesional.currentIndexChanged.connect(self._sincronizar_grilla)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_consultorio = QComboBox()
        for id_, etiqueta in _opciones_consultorio(self.conn):
            self.combo_consultorio.addItem(etiqueta, id_)
        self.combo_consultorio.currentIndexChanged.connect(self._sincronizar_grilla)
        form.addWidget(QLabel("Consultorio"))
        form.addWidget(self.combo_consultorio)

        self.combo_dia = QComboBox()
        self.combo_dia.addItems(_DIAS_RESERVA)
        form.addWidget(QLabel("Día"))
        form.addWidget(self.combo_dia)

        fila_horario = QHBoxLayout()
        self.spin_desde = QDoubleSpinBox()
        self.spin_desde.setRange(0, 23)
        self.spin_desde.setValue(9)
        self.spin_hasta = QDoubleSpinBox()
        self.spin_hasta.setRange(1, 24)
        self.spin_hasta.setValue(10)
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_desde)
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hasta)
        form.addLayout(fila_horario)

        self.campo_vigencia_inicio = QLineEdit()
        self.campo_vigencia_inicio.setPlaceholderText("AAAA-MM-DD")
        form.addWidget(QLabel("Vigencia desde"))
        form.addWidget(self.campo_vigencia_inicio)

        self.campo_vigencia_fin = QLineEdit()
        self.campo_vigencia_fin.setPlaceholderText("AAAA-MM-DD (opcional)")
        form.addWidget(QLabel("Vigencia hasta"))
        form.addWidget(self.campo_vigencia_fin)

        self.casilla_excepcion = QCheckBox("Es excepción")
        form.addWidget(self.casilla_excepcion)

        boton_crear = QPushButton("Crear reserva regular")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.clicked.connect(self._crear)
        form.addWidget(boton_crear)
        form.addStretch()
        splitter.addWidget(panel_form)

        panel_tabla = QWidget()
        layout_tabla = QVBoxLayout(panel_tabla)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Profesional", "Consultorio", "Día", "Horario", "Vigencia desde", "Vigencia hasta"]
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout_tabla.addWidget(self.tabla, stretch=1)

        fila_acciones = QHBoxLayout()
        boton_finalizar = QPushButton("Finalizar vigencia hoy")
        boton_finalizar.clicked.connect(self._finalizar_vigencia)
        fila_acciones.addWidget(boton_finalizar)
        fila_acciones.addStretch()
        layout_tabla.addLayout(fila_acciones)
        splitter.addWidget(panel_tabla)

        grupo_grilla = QGroupBox("Vista previa: grilla operativa")
        layout_grupo_grilla = QVBoxLayout(grupo_grilla)
        self.grilla = GrillaOperativaWidget(self.conn)
        layout_grupo_grilla.addWidget(self.grilla)
        splitter.addWidget(grupo_grilla)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)

        layout.addWidget(splitter)
        self.campo_vigencia_inicio.setText(fecha_actual(self.conn).isoformat())
        self._sincronizar_grilla()

    def actualizar(self) -> None:
        self._reservas = obtener_repositorio(self.conn, "ReservaRegular").listar()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        self.tabla.setRowCount(len(self._reservas))
        for fila_idx, r in enumerate(self._reservas):
            profesional = repo_profesional.obtener(r["IdProfesional"])
            consultorio = self.conn.execute(
                "SELECT c.NumeroConsultorio, u.Departamento FROM Consultorio c "
                "JOIN Unidad u ON u.IdUnidad = c.IdUnidad WHERE c.IdConsultorio = ?",
                (r["IdConsultorio"],),
            ).fetchone()
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(profesional["Apellido"] if profesional else "?"))
            texto_consultorio = f"{consultorio['Departamento']} - {consultorio['NumeroConsultorio']}" if consultorio else "?"
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(texto_consultorio))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(r["DiaSemana"]))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(f"{r['HoraInicio']:g} a {r['HoraFin']:g}"))
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(r["VigenciaInicio"] or ""))
            self.tabla.setItem(fila_idx, 5, QTableWidgetItem(r["VigenciaFin"] or ""))
        self.tabla.resizeColumnsToContents()
        self.grilla.actualizar()

    def _sincronizar_grilla(self) -> None:
        """La vista previa acompaña lo que se está por reservar: acotada
        al consultorio elegido, y con el profesional elegido pintado de
        azul si ya tiene algo reservado en el mes actual."""
        id_consultorio = self.combo_consultorio.currentData()
        id_unidad = None
        if id_consultorio is not None:
            fila = self.conn.execute(
                "SELECT IdUnidad FROM Consultorio WHERE IdConsultorio = ?", (id_consultorio,)
            ).fetchone()
            id_unidad = fila["IdUnidad"] if fila else None
        self.grilla.filtrar_por_unidad(id_unidad)
        self.grilla.filtrar_por_profesional(self.combo_profesional.currentData())

    def _crear(self, forzar: bool = False) -> None:
        datos = dict(
            id_profesional=self.combo_profesional.currentData(),
            id_consultorio=self.combo_consultorio.currentData(),
            dia_semana=self.combo_dia.currentText(),
            hora_inicio=self.spin_desde.value(),
            hora_fin=self.spin_hasta.value(),
            vigencia_inicio=self.campo_vigencia_inicio.text().strip() or fecha_actual(self.conn).isoformat(),
            vigencia_fin=self.campo_vigencia_fin.text().strip() or None,
            es_excepcion=self.casilla_excepcion.isChecked(),
            forzar=forzar,
        )
        try:
            _id, advertencias = crear_reserva_regular(self.conn, **datos)
        except ConflictoBloqueanteError as error:
            confirmacion = QMessageBox.question(
                self, "Conflictos detectados",
                f"{error}\n\n¿Crear la reserva de todos modos?",
            )
            if confirmacion == QMessageBox.StandardButton.Yes:
                self._crear(forzar=True)
            return
        except ValueError as error:
            QMessageBox.warning(self, "Crear reserva regular", str(error))
            return
        self.conn.commit()
        if advertencias:
            QMessageBox.information(self, "Reserva creada", "Reserva creada con avisos:\n" + "\n".join(advertencias))
        self._ofrecer_resolver_lista_espera(datos["id_profesional"])
        regenerar_si_corresponde(self.conn, id_profesional=datos["id_profesional"], periodo=periodo_actual(self.conn))
        self.conn.commit()
        self.actualizar()

    def _ofrecer_resolver_lista_espera(self, id_profesional: int) -> None:
        """DC-10 §2.2 paso 5: confirmar la reserva regular en F16 tiene que
        poder cerrar el pedido de Lista de espera que la originó. Con un
        solo pedido Activo del profesional alcanza con preguntar; con más
        de uno queda a criterio manual (no hay forma de saber cuál de
        todos se acaba de cubrir)."""
        pedidos = obtener_repositorio(self.conn, "ListaEspera").listar(
            IdProfesional=id_profesional, Estado="Activo",
        )
        if len(pedidos) != 1:
            return
        respuesta = QMessageBox.question(
            self, "Lista de espera",
            "Este profesional tiene un pedido activo en Lista de espera. "
            "¿Lo marcás como resuelto?",
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            marcar_resuelto(self.conn, pedidos[0]["IdPedido"])
            self.conn.commit()

    def _finalizar_vigencia(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return
        reserva = self._reservas[filas[0].row()]
        obtener_repositorio(self.conn, "ReservaRegular").actualizar(
            reserva["IdReservaRegular"], VigenciaFin=fecha_actual(self.conn).isoformat()
        )
        regenerar_si_corresponde(
            self.conn, id_profesional=reserva["IdProfesional"], periodo=periodo_actual(self.conn),
        )
        self.conn.commit()
        self.actualizar()


class _PanelReservasAisladas(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._reservas: list[sqlite3.Row] = []
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()

        panel_form = QWidget()
        form = QVBoxLayout(panel_form)
        self.combo_profesional = QComboBox()
        for id_, etiqueta in _opciones_profesional(self.conn):
            self.combo_profesional.addItem(etiqueta, id_)
        self.combo_profesional.currentIndexChanged.connect(self._sincronizar_grilla)
        form.addWidget(QLabel("Profesional"))
        form.addWidget(self.combo_profesional)

        self.combo_consultorio = QComboBox()
        for id_, etiqueta in _opciones_consultorio(self.conn):
            self.combo_consultorio.addItem(etiqueta, id_)
        self.combo_consultorio.currentIndexChanged.connect(self._sincronizar_grilla)
        form.addWidget(QLabel("Consultorio"))
        form.addWidget(self.combo_consultorio)

        self.campo_fecha = QLineEdit()
        self.campo_fecha.setPlaceholderText("AAAA-MM-DD")
        form.addWidget(QLabel("Fecha"))
        form.addWidget(self.campo_fecha)

        fila_horario = QHBoxLayout()
        self.spin_desde = QDoubleSpinBox()
        self.spin_desde.setRange(0, 23)
        self.spin_desde.setValue(9)
        self.spin_hasta = QDoubleSpinBox()
        self.spin_hasta.setRange(1, 24)
        self.spin_hasta.setValue(10)
        fila_horario.addWidget(QLabel("Desde"))
        fila_horario.addWidget(self.spin_desde)
        fila_horario.addWidget(QLabel("Hasta"))
        fila_horario.addWidget(self.spin_hasta)
        form.addLayout(fila_horario)

        self.casilla_recargo = QCheckBox("Aplica recargo")
        form.addWidget(self.casilla_recargo)

        self.casilla_reubicacion = QCheckBox("Es reubicación (compensa una ausencia del profesional, no genera cargo)")
        form.addWidget(self.casilla_reubicacion)

        boton_crear = QPushButton("Crear reserva aislada")
        boton_crear.setObjectName("botonPrimario")
        boton_crear.clicked.connect(self._crear)
        form.addWidget(boton_crear)
        form.addStretch()
        splitter.addWidget(panel_form)

        panel_tabla = QWidget()
        layout_tabla = QVBoxLayout(panel_tabla)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["Profesional", "Consultorio", "Fecha", "Horario", "Estado"])
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout_tabla.addWidget(self.tabla, stretch=1)

        fila_acciones = QHBoxLayout()
        boton_cancelar = QPushButton("Cancelar reserva")
        boton_cancelar.clicked.connect(self._cancelar)
        fila_acciones.addWidget(boton_cancelar)
        fila_acciones.addStretch()
        layout_tabla.addLayout(fila_acciones)
        splitter.addWidget(panel_tabla)

        grupo_grilla = QGroupBox("Vista previa: grilla operativa")
        layout_grupo_grilla = QVBoxLayout(grupo_grilla)
        self.grilla = GrillaOperativaWidget(self.conn)
        self.grilla.combo_modo.setCurrentIndex(self.grilla.combo_modo.findData("aislada"))
        layout_grupo_grilla.addWidget(self.grilla)
        splitter.addWidget(grupo_grilla)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)

        layout.addWidget(splitter)
        self.campo_fecha.setText(fecha_actual(self.conn).isoformat())
        self._sincronizar_grilla()

    def _sincronizar_grilla(self) -> None:
        """Igual que en Reservas regulares: la vista previa acompaña lo
        que se está por reservar, acotada al consultorio elegido y con el
        profesional elegido pintado de azul si ya tiene algo reservado en
        el mes en curso — en modo "Reservas aisladas" porque acá interesa
        ver qué está libre AHORA, no los conflictos futuros."""
        id_consultorio = self.combo_consultorio.currentData()
        id_unidad = None
        if id_consultorio is not None:
            fila = self.conn.execute(
                "SELECT IdUnidad FROM Consultorio WHERE IdConsultorio = ?", (id_consultorio,)
            ).fetchone()
            id_unidad = fila["IdUnidad"] if fila else None
        self.grilla.filtrar_por_unidad(id_unidad)
        self.grilla.filtrar_por_profesional(self.combo_profesional.currentData())

    def actualizar(self) -> None:
        self._reservas = obtener_repositorio(self.conn, "ReservaAislada").listar()
        repo_profesional = obtener_repositorio(self.conn, "Profesional")
        self.tabla.setRowCount(len(self._reservas))
        for fila_idx, r in enumerate(self._reservas):
            profesional = repo_profesional.obtener(r["IdProfesional"])
            consultorio = self.conn.execute(
                "SELECT c.NumeroConsultorio, u.Departamento FROM Consultorio c "
                "JOIN Unidad u ON u.IdUnidad = c.IdUnidad WHERE c.IdConsultorio = ?",
                (r["IdConsultorio"],),
            ).fetchone()
            self.tabla.setItem(fila_idx, 0, QTableWidgetItem(profesional["Apellido"] if profesional else "?"))
            texto_consultorio = f"{consultorio['Departamento']} - {consultorio['NumeroConsultorio']}" if consultorio else "?"
            self.tabla.setItem(fila_idx, 1, QTableWidgetItem(texto_consultorio))
            self.tabla.setItem(fila_idx, 2, QTableWidgetItem(r["Fecha"]))
            self.tabla.setItem(fila_idx, 3, QTableWidgetItem(f"{r['HoraInicio']:g} a {r['HoraFin']:g}"))
            estado = f"{r['Estado']} (reubicación)" if r["EsReubicacion"] else r["Estado"]
            self.tabla.setItem(fila_idx, 4, QTableWidgetItem(estado))
        self.tabla.resizeColumnsToContents()
        self.grilla.actualizar()

    def _crear(self, forzar: bool = False) -> None:
        fecha = self.campo_fecha.text().strip() or fecha_actual(self.conn).isoformat()
        if not forzar and not confirmar_si_fecha_es_mes_anterior(self, self.conn, fecha):
            return
        datos = dict(
            id_profesional=self.combo_profesional.currentData(),
            id_consultorio=self.combo_consultorio.currentData(),
            fecha=fecha,
            hora_inicio=self.spin_desde.value(),
            hora_fin=self.spin_hasta.value(),
            aplica_recargo=self.casilla_recargo.isChecked(),
            es_reubicacion=self.casilla_reubicacion.isChecked(),
            forzar=forzar,
        )
        try:
            _id, advertencias = crear_reserva_aislada(self.conn, **datos)
        except ConflictoBloqueanteError as error:
            confirmacion = QMessageBox.question(
                self, "Conflictos detectados",
                f"{error}\n\n¿Crear la reserva de todos modos?",
            )
            if confirmacion == QMessageBox.StandardButton.Yes:
                self._crear(forzar=True)
            return
        except ValueError as error:
            QMessageBox.warning(self, "Crear reserva aislada", str(error))
            return
        self.conn.commit()
        if advertencias:
            QMessageBox.information(self, "Reserva creada", "Reserva creada con avisos:\n" + "\n".join(advertencias))
        self._copiar_mensaje_detalle(datos["id_profesional"], fecha)
        self.actualizar()

    def _copiar_mensaje_detalle(self, id_profesional: int, fecha: str) -> None:
        """DC-02/DC-03/DC-04: confirmar, cancelar o modificar una reserva
        aislada carga sola el mensaje de detalle al portapapeles — sin
        reemplazar la posibilidad de volver a generarlo a mano desde el
        Centro de mensajería."""
        try:
            texto = mensaje_detalle_reserva_aislada(self.conn, id_profesional=id_profesional, periodo=fecha[:7])
        except ValueError:
            return
        QGuiApplication.clipboard().setText(texto)

    def _cancelar(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return
        reserva = self._reservas[filas[0].row()]
        try:
            requiere_aviso = cancelar_reserva_aislada(self.conn, reserva["IdReservaAislada"])
        except ValueError as error:
            QMessageBox.warning(self, "Cancelar reserva", str(error))
            return
        self.conn.commit()
        if requiere_aviso:
            QMessageBox.information(self, "Cancelar reserva", "Cancelada el mismo día: avisar al profesional.")
        self._copiar_mensaje_detalle(reserva["IdProfesional"], reserva["Fecha"])
        self.actualizar()
