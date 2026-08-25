"""Widget reutilizable de la "Grilla Operativa" (miscelánea, ago-2026):
filtros (localidad/edificio/unidad/día de semana/profesional) + selector
de período/rango de fechas/modo de visualización + la grilla en sí
(encabezados apilados como en el PDF de Disponibilidad: Día de la
semana > Localidad > Edificio > Unidad > Consultorio, omitiendo
Localidad/Edificio cuando solo hay uno) + cuadro de texto de detalle al
hacer clic en una celda.

Se monta en la pantalla "Grilla operativa" y, más adelante, en los
formularios de reservas/vacaciones/licencias/ausencias (cada uno la
reutiliza tal cual, según se vaya conectando)."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.gui.estilos import COLOR_AMARILLO, COLOR_AZUL_OSCURO, COLOR_NIVEL_1, COLOR_ROJO, COLOR_VERDE
from app.negocio.dias import parsear_periodo, periodo_actual, sumar_meses, ultimo_dia_mes
from app.negocio.grilla import dias_grilla
from app.negocio.grilla_operativa import (
    AMARILLO,
    AZUL_OSCURO,
    BLANCA,
    BLANCO,
    ROJO,
    VERDE,
    CeldaGrillaOperativa,
    calcular_grilla_operativa,
)

_COLOR_HEX = {BLANCO: "#FFFFFF", VERDE: COLOR_VERDE, AMARILLO: COLOR_AMARILLO, ROJO: COLOR_ROJO, AZUL_OSCURO: COLOR_AZUL_OSCURO}
_FUENTE_HEX = {BLANCA: "#FFFFFF"}  # "negra" es el default de _CeldaGrilla, no hace falta mapearla
_ANCHO_CODIGO_CORTO = "A99"  # letra + 2 dígitos
_ANCHO_CODIGO_LARGO = "A999"  # letra + 3 dígitos


class _CeldaGrilla(QWidget):
    """Una celda de datos: fondo = color de aro, círculo centrado = color
    de centro (si distinto del aro), código encima. Widget propio (no
    QTableWidgetItem) para poder pintar el círculo y manejar el clic sin
    un delegate aparte."""

    def __init__(self, celda: CeldaGrillaOperativa, clave: tuple[int, str, int], on_click, parent=None):
        super().__init__(parent)
        self.celda = celda
        self._clave = clave
        self._on_click = on_click
        self.setMinimumHeight(24)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (nombre impuesto por Qt)
        self._on_click(self._clave)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QColor(_COLOR_HEX[self.celda.color_aro]))
        if self.celda.color_centro != self.celda.color_aro:
            lado = min(rect.width(), rect.height()) * 0.55
            x = rect.center().x() - lado / 2
            y = rect.center().y() - lado / 2
            painter.setBrush(QColor(_COLOR_HEX[self.celda.color_centro]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(x), int(y), int(lado), int(lado))
        if self.celda.codigo:
            painter.setPen(QColor(_FUENTE_HEX.get(self.celda.color_fuente, "#000000")))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.celda.codigo)
        painter.end()


def _lista_multiseleccion() -> QListWidget:
    lista = QListWidget()
    lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    lista.setMaximumHeight(90)
    return lista


def _seleccionar_todos(lista: QListWidget) -> None:
    for i in range(lista.count()):
        lista.item(i).setSelected(True)


def _ids_seleccionados(lista: QListWidget) -> list[int]:
    return [item.data(Qt.ItemDataRole.UserRole) for item in lista.selectedItems()]


class GrillaOperativaWidget(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._resultado: dict[tuple[int, str, int], CeldaGrillaOperativa] = {}
        self._armar_ui()
        self._cargar_localidades()
        self.actualizar()

    # ------------------------------------------------------------- armado

    def _armar_ui(self) -> None:
        layout_principal = QHBoxLayout(self)

        panel_filtros = QGroupBox("Filtros")
        panel_filtros.setMaximumWidth(260)
        layout_filtros = QVBoxLayout(panel_filtros)

        layout_filtros.addWidget(QLabel("Localidad"))
        self.lista_localidad = _lista_multiseleccion()
        self.lista_localidad.itemSelectionChanged.connect(self._cargar_edificios)
        layout_filtros.addWidget(self.lista_localidad)

        layout_filtros.addWidget(QLabel("Edificio"))
        self.lista_edificio = _lista_multiseleccion()
        self.lista_edificio.itemSelectionChanged.connect(self._cargar_unidades)
        layout_filtros.addWidget(self.lista_edificio)

        layout_filtros.addWidget(QLabel("Unidad"))
        self.lista_unidad = _lista_multiseleccion()
        self.lista_unidad.itemSelectionChanged.connect(self.actualizar)
        layout_filtros.addWidget(self.lista_unidad)

        layout_filtros.addWidget(QLabel("Día de la semana"))
        self._checks_dia: dict[str, QCheckBox] = {}
        contenedor_dias = QWidget()
        layout_dias = QVBoxLayout(contenedor_dias)
        layout_dias.setContentsMargins(0, 0, 0, 0)
        for dia in dias_grilla(self.conn):
            check = QCheckBox(dia)
            check.setChecked(True)
            check.stateChanged.connect(self.actualizar)
            self._checks_dia[dia] = check
            layout_dias.addWidget(check)
        layout_filtros.addWidget(contenedor_dias)

        layout_filtros.addWidget(QLabel("Profesional (código o nombre)"))
        self.campo_profesional = QLineEdit()
        self.campo_profesional.setPlaceholderText("Sin selección")
        self.campo_profesional.editingFinished.connect(self.actualizar)
        layout_filtros.addWidget(self.campo_profesional)
        self._profesionales_por_texto: dict[str, int] = {}
        self._cargar_completador_profesionales()

        layout_filtros.addStretch()
        layout_principal.addWidget(panel_filtros)

        panel_grilla = QWidget()
        layout_grilla = QVBoxLayout(panel_grilla)

        fila_controles = QHBoxLayout()
        fila_controles.addWidget(QLabel("Período:"))
        self.combo_periodo = QComboBox()
        periodo_base = periodo_actual(self.conn)
        for i in range(13):
            periodo = sumar_meses(periodo_base, i)
            self.combo_periodo.addItem(periodo, periodo)
        self.combo_periodo.currentIndexChanged.connect(self._periodo_cambiado)
        fila_controles.addWidget(self.combo_periodo)

        fila_controles.addWidget(QLabel("Desde:"))
        self.campo_desde = QLineEdit()
        self.campo_desde.editingFinished.connect(self.actualizar)
        fila_controles.addWidget(self.campo_desde)

        fila_controles.addWidget(QLabel("Hasta:"))
        self.campo_hasta = QLineEdit()
        self.campo_hasta.editingFinished.connect(self.actualizar)
        fila_controles.addWidget(self.campo_hasta)

        fila_controles.addWidget(QLabel("Visualización:"))
        self.combo_modo = QComboBox()
        self.combo_modo.addItem("Reservas regulares", "regular")
        self.combo_modo.addItem("Reservas aisladas", "aislada")
        self.combo_modo.currentIndexChanged.connect(self.actualizar)
        fila_controles.addWidget(self.combo_modo)
        fila_controles.addStretch()
        layout_grilla.addLayout(fila_controles)

        self._establecer_rango_por_defecto(periodo_base)

        self.tabla = QTableWidget()
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.horizontalHeader().setVisible(False)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout_grilla.addWidget(self.tabla, stretch=1)

        layout_grilla.addWidget(QLabel("Detalle:"))
        self.texto_detalle = QTextEdit()
        self.texto_detalle.setReadOnly(True)
        self.texto_detalle.setMaximumHeight(90)
        layout_grilla.addWidget(self.texto_detalle)

        layout_principal.addWidget(panel_grilla, stretch=1)

    def _establecer_rango_por_defecto(self, periodo: str) -> None:
        anio, mes = parsear_periodo(periodo)
        self.campo_desde.setText(f"{anio:04d}-{mes:02d}-01")
        self.campo_hasta.setText(ultimo_dia_mes(anio, mes).isoformat())

    def _periodo_cambiado(self) -> None:
        periodo = self.combo_periodo.currentData()
        if periodo:
            self._establecer_rango_por_defecto(periodo)
        self.actualizar()

    def _cargar_completador_profesionales(self) -> None:
        textos = []
        for p in self.conn.execute(
            "SELECT IdProfesional, IdCodigo, Apellido, NombrePila FROM Profesional WHERE IdCodigo IS NOT NULL "
            "ORDER BY IdCodigo"
        ).fetchall():
            texto = f"{p['IdCodigo']} - {p['Apellido']}, {p['NombrePila'] or ''}".rstrip(", ")
            self._profesionales_por_texto[texto] = p["IdProfesional"]
            textos.append(texto)
        completador = QCompleter(textos)
        completador.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.campo_profesional.setCompleter(completador)

    # ------------------------------------------------------------ filtros

    def _cargar_localidades(self) -> None:
        self.lista_localidad.blockSignals(True)
        self.lista_localidad.clear()
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
        self._cargar_edificios()

    def _cargar_edificios(self) -> None:
        localidades = _ids_seleccionados(self.lista_localidad)
        self.lista_edificio.blockSignals(True)
        self.lista_edificio.clear()
        sql = "SELECT IdEdificio, Nombre FROM Edificio"
        parametros: list = []
        if localidades:
            marcas = []
            for loc in localidades:
                if loc is None:
                    marcas.append("DomicilioLocalidad IS NULL")
                else:
                    marcas.append("DomicilioLocalidad = ?")
                    parametros.append(loc)
            sql += " WHERE " + " OR ".join(marcas)
        sql += " ORDER BY Nombre"
        for fila in self.conn.execute(sql, parametros).fetchall():
            item = QListWidgetItem(fila["Nombre"])
            item.setData(Qt.ItemDataRole.UserRole, fila["IdEdificio"])
            self.lista_edificio.addItem(item)
        _seleccionar_todos(self.lista_edificio)
        self.lista_edificio.blockSignals(False)
        self._cargar_unidades()

    def _cargar_unidades(self) -> None:
        ids_edificio = _ids_seleccionados(self.lista_edificio)
        self.lista_unidad.blockSignals(True)
        self.lista_unidad.clear()
        sql = "SELECT u.IdUnidad, u.Departamento, e.Nombre AS NombreEdificio FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio"
        parametros: list = []
        if ids_edificio:
            placeholders = ", ".join("?" for _ in ids_edificio)
            sql += f" WHERE u.IdEdificio IN ({placeholders})"
            parametros = ids_edificio
        sql += " ORDER BY e.Nombre, u.Departamento"
        for fila in self.conn.execute(sql, parametros).fetchall():
            item = QListWidgetItem(f"{fila['NombreEdificio']} - {fila['Departamento']}")
            item.setData(Qt.ItemDataRole.UserRole, fila["IdUnidad"])
            self.lista_unidad.addItem(item)
        _seleccionar_todos(self.lista_unidad)
        self.lista_unidad.blockSignals(False)
        self.actualizar()

    def _dias_seleccionados(self) -> list[str]:
        return [dia for dia, check in self._checks_dia.items() if check.isChecked()]

    def _id_profesional_filtro(self) -> int | None:
        return self._profesionales_por_texto.get(self.campo_profesional.text().strip())

    # ------------------------------------------------------------- grilla

    def actualizar(self) -> None:
        ids_unidad = _ids_seleccionados(self.lista_unidad)
        dias = self._dias_seleccionados()
        desde = self.campo_desde.text().strip()
        hasta = self.campo_hasta.text().strip()
        modo = self.combo_modo.currentData() or "regular"

        if not ids_unidad or not dias or not desde or not hasta:
            self.tabla.setRowCount(0)
            self.tabla.setColumnCount(0)
            self._resultado = {}
            return

        columnas = self._columnas(ids_unidad, dias)
        if not columnas:
            self.tabla.setRowCount(0)
            self.tabla.setColumnCount(0)
            self._resultado = {}
            return

        cfg = self.conn.execute(
            "SELECT HoraInicioGrilla, HoraFinGrilla FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        hora_ini = int(cfg["HoraInicioGrilla"]) if cfg else 8
        hora_fin = int(cfg["HoraFinGrilla"]) if cfg else 22
        horas = list(range(hora_ini, hora_fin))

        ids_consultorio = sorted({c["id_consultorio"] for c in columnas})
        self._resultado = calcular_grilla_operativa(
            self.conn, ids_consultorio, dias, hora_ini, hora_fin, desde, hasta,
            modo=modo, id_profesional_filtro=self._id_profesional_filtro(),
        )
        self._construir_tabla(columnas, horas)

    def _columnas(self, ids_unidad: list[int], dias: list[str]) -> list[dict]:
        placeholders = ", ".join("?" for _ in ids_unidad)
        filas = self.conn.execute(
            f"""
            SELECT c.IdConsultorio, c.NumeroConsultorio, u.IdUnidad, u.Departamento,
                   e.IdEdificio, e.Nombre AS NombreEdificio, e.DomicilioLocalidad
            FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
            WHERE u.IdUnidad IN ({placeholders})
            ORDER BY e.DomicilioLocalidad, e.Nombre, u.Departamento, c.NumeroConsultorio
            """,
            ids_unidad,
        ).fetchall()
        base = [
            {
                "id_consultorio": f["IdConsultorio"], "numero_consultorio": f["NumeroConsultorio"],
                "id_unidad": f["IdUnidad"], "departamento": f["Departamento"],
                "id_edificio": f["IdEdificio"], "nombre_edificio": f["NombreEdificio"],
                "localidad": f["DomicilioLocalidad"] or "(Sin localidad)",
            }
            for f in filas
        ]
        columnas = []
        for dia in dias:
            for base_col in base:
                columnas.append({**base_col, "dia": dia})
        return columnas

    def _construir_tabla(self, columnas: list[dict], horas: list[int]) -> None:
        n_localidades = len({c["localidad"] for c in columnas})
        n_edificios = len({c["id_edificio"] for c in columnas})
        mostrar_localidad = n_localidades > 1
        mostrar_edificio = n_edificios > 1

        filas_encabezado = 3 + int(mostrar_localidad) + int(mostrar_edificio)  # Día [+Localidad][+Edificio] + Unidad + Consultorio
        n_filas = filas_encabezado + len(horas)
        n_columnas = 1 + len(columnas)  # +1 columna de horario

        # setRowCount(0)/setColumnCount(0) primero: QTableWidget.clear() no
        # garantiza liberar los cellWidget de la grilla anterior, y sin esto
        # quedan widgets huérfanos superpuestos al reconstruir con otros
        # filtros.
        self.tabla.setRowCount(0)
        self.tabla.setColumnCount(0)
        self.tabla.setRowCount(n_filas)
        self.tabla.setColumnCount(n_columnas)

        ancho_columna = self._ancho_columna(columnas, horas)
        self.tabla.setColumnWidth(0, 55)
        for col in range(1, n_columnas):
            self.tabla.setColumnWidth(col, ancho_columna)
        for fila in range(filas_encabezado):
            self.tabla.setRowHeight(fila, 22)
        for fila in range(filas_encabezado, n_filas):
            self.tabla.setRowHeight(fila, 24)

        fila_actual = 0
        self._agregar_encabezado_agrupado(fila_actual, columnas, lambda c: c["dia"], "Día de la semana", mayusculas=True)
        fila_actual += 1
        if mostrar_localidad:
            self._agregar_encabezado_agrupado(fila_actual, columnas, lambda c: (c["dia"], c["localidad"]), "Localidad")
            fila_actual += 1
        if mostrar_edificio:
            self._agregar_encabezado_agrupado(
                fila_actual, columnas, lambda c: (c["dia"], c["localidad"], c["nombre_edificio"]), "Edificio",
            )
            fila_actual += 1
        self._agregar_encabezado_agrupado(
            fila_actual, columnas, lambda c: (c["dia"], c["localidad"], c["nombre_edificio"], c["id_unidad"]),
            "Unidad", texto=lambda c: c["departamento"],
        )
        fila_actual += 1
        self._agregar_encabezado_consultorio(fila_actual, columnas)
        fila_actual += 1

        for i, hora in enumerate(horas):
            fila = filas_encabezado + i
            self._poner_texto_encabezado(fila, 0, f"{hora}:00")
            for j, columna in enumerate(columnas):
                col = j + 1
                clave = (columna["id_consultorio"], columna["dia"], hora)
                celda = self._resultado.get(clave)
                if celda is None:
                    continue
                widget = _CeldaGrilla(celda, clave, self._mostrar_detalle)
                self.tabla.setCellWidget(fila, col, widget)

    def _ancho_columna(self, columnas: list[dict], horas: list[int]) -> int:
        codigos_largos = any(
            celda.codigo and len(celda.codigo) > 3
            for c in columnas
            for h in horas
            if (celda := self._resultado.get((c["id_consultorio"], c["dia"], h))) is not None
        )
        metrica = self.fontMetrics()
        texto = _ANCHO_CODIGO_LARGO if codigos_largos else _ANCHO_CODIGO_CORTO
        return metrica.horizontalAdvance(texto) + 14

    def _agregar_encabezado_agrupado(self, fila: int, columnas: list[dict], clave_grupo, etiqueta_columna_0, texto=None, mayusculas: bool = False) -> None:
        self._poner_texto_encabezado(fila, 0, etiqueta_columna_0)
        inicio = 0
        actual = clave_grupo(columnas[0])
        for i in range(1, len(columnas) + 1):
            clave = clave_grupo(columnas[i]) if i < len(columnas) else None
            if clave != actual:
                texto_grupo = texto(columnas[inicio]) if texto else str(actual[-1] if isinstance(actual, tuple) else actual)
                if mayusculas:
                    texto_grupo = texto_grupo.upper()
                self._poner_texto_encabezado(fila, inicio + 1, texto_grupo, span=i - inicio)
                inicio = i
                actual = clave

    def _agregar_encabezado_consultorio(self, fila: int, columnas: list[dict]) -> None:
        self._poner_texto_encabezado(fila, 0, "Consultorio")
        for i, columna in enumerate(columnas):
            self._poner_texto_encabezado(fila, i + 1, str(columna["numero_consultorio"]))

    def _poner_texto_encabezado(self, fila: int, col: int, texto: str, span: int = 1) -> None:
        etiqueta = QLabel(texto)
        etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        etiqueta.setStyleSheet(f"background-color: {COLOR_NIVEL_1}; color: white; font-weight: bold;")
        etiqueta.setWordWrap(True)
        if span > 1:
            self.tabla.setSpan(fila, col, 1, span)
        self.tabla.setCellWidget(fila, col, etiqueta)

    def _mostrar_detalle(self, clave: tuple[int, str, int]) -> None:
        celda = self._resultado.get(clave)
        self.texto_detalle.setPlainText(celda.detalle if celda else "")
