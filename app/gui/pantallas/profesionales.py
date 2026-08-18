"""Pantalla de Profesionales (F06/F07, sección 3.4) sobre PantallaCRUD, con
un panel de documentación (archivos sueltos en Profesionales/{código}/
Documentación) para el profesional seleccionado."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.gui.crud_generico import Campo, PantallaCRUD
from app.negocio.archivos_generados import aplicar_cambio_codigo
from app.negocio.dias import fecha_actual
from app.negocio.documentacion_profesional import agregar_documento, eliminar_documento, listar_documentos
from app.negocio.listas_editables import opciones_lista
from app.negocio.profesionales import normalizar_cuit, opciones_tratamiento, sugerir_codigo, tratamiento_sugerido
from app.repositorio.registro import obtener_repositorio

_CATEGORIAS = [
    ("R", "R - Regular"),
    ("A", "A - Reserva aislada"),
    ("B", "B - Bonificado"),
    ("E", "E - Equipo (consolida en su cabeza de equipo)"),
    ("X", "X - Inactivo"),
    ("C", "C - Contacto / prospecto"),
]
_SEXOS = [("Masculino", "Masculino"), ("Femenino", "Femenino"), ("No binario", "No binario")]


def _opciones_categoria(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return _CATEGORIAS


def _opciones_sexo(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return _SEXOS


def _opciones_profesion(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdProfesion, Nombre FROM Profesion ORDER BY Nombre").fetchall()
    return [(f["IdProfesion"], f["Nombre"]) for f in filas]


def _opciones_profesional(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido").fetchall()
    return [(f["IdProfesional"], f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", ")) for f in filas]


def _campos_profesional() -> list[Campo]:
    return [
        Campo("CategoriaProfesional", "Categoría", tipo="combo", opciones=_opciones_categoria, requerido=True),
        Campo("Apellido", "Apellido", requerido=True),
        Campo("NombreCompleto", "Nombre completo"),
        Campo("NombrePila", "Nombre"),
        Campo("Apodo", "Apodo"),
        Campo("Tratamiento", "Tratamiento", tipo="combo", opciones=lambda conn: [], combo_editable=True),
        Campo("Sexo", "Sexo", tipo="combo", opciones=_opciones_sexo),
        Campo("IdCodigo", "Código"),
        Campo("DNI", "DNI"),
        Campo("CUIT", "CUIT", normalizar=normalizar_cuit),
        Campo(
            "CondicionFiscal", "Condición fiscal", tipo="combo",
            opciones=opciones_lista("CondicionFiscal"), combo_editable=True,
        ),
        Campo("FechaNacimiento", "Fecha de nacimiento (AAAA-MM-DD)"),
        Campo("Domicilio", "Domicilio"),
        Campo("DomicilioLocalidad", "Localidad"),
        Campo("TelefonoParticular", "Teléfono particular"),
        Campo("Celular", "Celular"),
        Campo("Email", "Email"),
        Campo("IdProfesion", "Profesión", tipo="combo", opciones=_opciones_profesion),
        Campo("MatriculaNacional", "Matrícula nacional"),
        Campo("MatriculaProvincial", "Matrícula provincial"),
        Campo("FechaContacto", "Fecha de contacto (AAAA-MM-DD)"),
        Campo("ProfesionalCabezaEquipo", "Cabeza de equipo", tipo="combo", opciones=_opciones_profesional),
        Campo("SaldoCuentaActual", "Saldo cuenta actual", tipo="numero"),
        Campo("SaldoCuentaAnterior", "Saldo cuenta anterior", tipo="numero"),
        Campo("PlazoPagoExtendido", "Plazo de pago extendido"),
        Campo("MotivoPlazoExtra", "Motivo del plazo extra"),
        Campo("CampoLibre1", "Campo libre 1"),
        Campo("CampoLibre2", "Campo libre 2"),
        Campo("CampoLibre3", "Campo libre 3"),
    ]


def _al_abrir_dialogo(dialogo) -> None:
    """Sección 3.4: sugiere el código (según categoría) y pre-completa el
    tratamiento (según profesión y sexo) apenas se abre el formulario, tanto
    al crear un registro nuevo como al editar uno existente — en edición,
    además de sugerir, repuebla el desplegable de Tratamiento con las
    opciones de la profesión/sexo actuales (para Fonoaudiología y
    Psicopedagogía) sin perder el valor ya cargado. Cada campo se
    recalcula mientras el operador no haya tocado ese campo a mano (se
    compara contra la última sugerencia, no contra "vacío", para no pisar
    un valor que sí escribieron o que ya traía el registro); ambos quedan
    editables antes de confirmar."""
    conn = dialogo.conn
    combo_categoria = dialogo._entradas["CategoriaProfesional"]
    campo_codigo = dialogo._entradas["IdCodigo"]
    combo_profesion = dialogo._entradas["IdProfesion"]
    combo_sexo = dialogo._entradas["Sexo"]
    combo_tratamiento = dialogo._entradas["Tratamiento"]

    ultimo_codigo_sugerido = [None]

    def _actualizar_codigo() -> None:
        categoria = combo_categoria.currentData()
        if categoria is None:
            return
        sugerido = sugerir_codigo(conn, categoria)
        actual = campo_codigo.text().strip()
        if actual in ("", ultimo_codigo_sugerido[0]):
            campo_codigo.setText(sugerido)
            ultimo_codigo_sugerido[0] = sugerido

    ultimo_tratamiento_sugerido = [None]

    def _actualizar_tratamiento() -> None:
        id_profesion = combo_profesion.currentData()
        sexo = combo_sexo.currentData()
        opciones = opciones_tratamiento(conn, id_profesion, sexo)
        sugerido = tratamiento_sugerido(conn, id_profesion, sexo)
        actual = combo_tratamiento.currentText().strip()

        combo_tratamiento.blockSignals(True)
        combo_tratamiento.clear()
        for opcion in opciones:
            combo_tratamiento.addItem(opcion)
        combo_tratamiento.blockSignals(False)

        if actual in ("", ultimo_tratamiento_sugerido[0]):
            nuevo = sugerido or ""
            combo_tratamiento.setEditText(nuevo)
            ultimo_tratamiento_sugerido[0] = nuevo
        else:
            combo_tratamiento.setEditText(actual)

    combo_categoria.currentIndexChanged.connect(_actualizar_codigo)
    combo_profesion.currentIndexChanged.connect(_actualizar_tratamiento)
    combo_sexo.currentIndexChanged.connect(_actualizar_tratamiento)
    _actualizar_codigo()
    _actualizar_tratamiento()


class PantallaProfesionales(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)
        splitter = QSplitter()

        self.crud_profesionales = PantallaCRUD(
            self.conn, "Profesional", "Profesionales", _campos_profesional(),
            al_actualizar=self._al_actualizar_profesional,
            al_abrir_dialogo=_al_abrir_dialogo,
        )
        self.crud_profesionales.tabla_widget.itemSelectionChanged.connect(self._actualizar_documentacion)
        splitter.addWidget(self.crud_profesionales)

        panel_doc = QWidget()
        layout_doc = QVBoxLayout(panel_doc)
        layout_doc.addWidget(QLabel("Documentación del profesional seleccionado"))
        self.lista_documentos = QListWidget()
        layout_doc.addWidget(self.lista_documentos, stretch=1)

        fila_botones = QHBoxLayout()
        boton_agregar = QPushButton("Agregar archivo…")
        boton_agregar.setObjectName("botonPrimario")
        boton_agregar.clicked.connect(self._agregar_documento)
        boton_eliminar = QPushButton("Eliminar")
        boton_eliminar.clicked.connect(self._eliminar_documento)
        fila_botones.addWidget(boton_agregar)
        fila_botones.addWidget(boton_eliminar)
        fila_botones.addStretch()
        layout_doc.addLayout(fila_botones)
        splitter.addWidget(panel_doc)

        layout.addWidget(splitter, stretch=1)

    def _al_actualizar_profesional(self, registro_anterior: sqlite3.Row, valores_nuevos: dict) -> None:
        try:
            aplicar_cambio_codigo(self.conn, registro_anterior, valores_nuevos, fecha_actual(self.conn))
        except OSError as error:
            QMessageBox.warning(
                self, "Cambio de código",
                f"Se registró el cambio de código, pero no se pudo renombrar la carpeta en disco: {error}",
            )
        self._actualizar_documentacion()

    def _codigo_seleccionado(self) -> str | None:
        id_valor = self.crud_profesionales.fila_seleccionada_id()
        if id_valor is None:
            return None
        profesional = obtener_repositorio(self.conn, "Profesional").obtener(id_valor)
        return profesional["IdCodigo"] if profesional else None

    def _actualizar_documentacion(self) -> None:
        self.lista_documentos.clear()
        codigo = self._codigo_seleccionado()
        if not codigo:
            return
        try:
            for ruta in listar_documentos(self.conn, codigo):
                self.lista_documentos.addItem(QListWidgetItem(ruta.name))
        except ValueError:
            pass  # sin carpeta base configurada todavía: lista vacía

    def _agregar_documento(self) -> None:
        codigo = self._codigo_seleccionado()
        if not codigo:
            QMessageBox.information(self, "Documentación", "Seleccioná un profesional con código cargado.")
            return
        rutas, _ = QFileDialog.getOpenFileNames(self, "Elegir documentación", "", "PDF e imágenes (*.pdf *.jpg *.jpeg *.png)")
        if not rutas:
            return
        errores = []
        for ruta in rutas:
            try:
                agregar_documento(self.conn, codigo, ruta)
            except ValueError as error:
                errores.append(str(error))
        if errores:
            QMessageBox.warning(self, "Documentación", "\n".join(errores))
        self._actualizar_documentacion()

    def _eliminar_documento(self) -> None:
        codigo = self._codigo_seleccionado()
        item = self.lista_documentos.currentItem()
        if not codigo or item is None:
            QMessageBox.information(self, "Documentación", "Seleccioná un archivo de la lista.")
            return
        confirmacion = QMessageBox.question(self, "Documentación", f"¿Confirmás eliminar «{item.text()}»?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        eliminar_documento(self.conn, codigo, item.text())
        self._actualizar_documentacion()


def pantalla_profesionales(conn: sqlite3.Connection) -> PantallaProfesionales:
    return PantallaProfesionales(conn)
