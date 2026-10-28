import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication, QDialog, QGridLayout, QGroupBox, QLabel, QMessageBox, QPushButton, QScrollArea, QStyle,
    QVBoxLayout, QWidget,
)

import app.gui.pantallas.reservas as reservas_modulo
from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import hoja_estilos
from app.gui.pantallas.reservas import (
    _FECHA_SIN_DATO, PantallaReservas, _alto_para_filas,
)
from app.gui.widgets.selector_profesional import _ProxyBusquedaSinAcentos
from app.negocio.dias import periodo_actual
from app.negocio.formato import mes_texto
from app.negocio.lista_espera import GrupoCobertura, crear_pedido
from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio
from app.negocio.llaves import agregar_acceso_llave, asignar_llave, crear_llave, ingresar_copias
from app.negocio.placas import asignar_placa
from app.repositorio.registro import obtener_repositorio


class _DialogoRegularFalso:
    """Reemplaza, en los tests, a `_DialogoModificarReservaRegular` —
    mismo criterio que `_DialogoFalso` de Pagos: no abre ninguna ventana
    real ni bloquea esperando al operador, `exec()` devuelve el
    resultado ya decidido y los atributos que el panel lee después de
    `exec()` vienen precargados de antemano."""

    def __init__(self, aceptar=True, **atributos):
        self._aceptar = aceptar
        for nombre, valor in atributos.items():
            setattr(self, nombre, valor)

    def exec(self):
        return QDialog.DialogCode.Accepted if self._aceptar else QDialog.DialogCode.Rejected


def _mockear_dialogo_modificar_regular(monkeypatch, *, aceptar=True, **atributos):
    monkeypatch.setattr(
        reservas_modulo, "_DialogoModificarReservaRegular",
        lambda conn, reserva, parent=None: _DialogoRegularFalso(aceptar, **atributos),
    )


def _mockear_dialogo_modificar_aislada(monkeypatch, *, aceptar=True, **atributos):
    """Mismo criterio que `_mockear_dialogo_modificar_regular`, para
    `_DialogoModificarReservaAislada` (Aisladas y Extraordinarias)."""
    atributos.setdefault("aplica_recargo", None)
    atributos.setdefault("item_extraordinario", None)
    atributos.setdefault("monto_extraordinario", None)
    monkeypatch.setattr(
        reservas_modulo, "_DialogoModificarReservaAislada",
        lambda conn, reserva, parent=None: _DialogoRegularFalso(aceptar, **atributos),
    )


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def _preparar(conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.commit()


def test_combos_profesional_son_buscables_por_codigo_o_nombre(qtbot, conn):
    """Confirmado por la clienta: el selector de profesional buscable
    corre en todos los formularios del sistema, Reservas incluido."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_regulares, pantalla.panel_aisladas):
        completador = panel.combo_profesional.completer()
        assert isinstance(completador.model(), _ProxyBusquedaSinAcentos)


def test_paneles_de_reservas_usan_el_fondo_claro_de_la_solapa(qtbot, conn):
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_regulares.objectName() == "panelSolapa"
    assert pantalla.panel_aisladas.objectName() == "panelSolapa"


def test_contenido_dentro_del_scroll_tiene_fondo_claro(qtbot, conn):
    """Bug detectado al revisar capturas: cada panel (self) tenía
    `panelSolapa` pero `contenido` (el widget que se pasa a
    `scroll.setWidget(...)`) no — el panel de filtros de la izquierda
    quedaba con el gris default de Qt en vez del blanco del resto de la
    solapa. Confirmado por muestreo de píxeles antes/después del
    arreglo.

    Dos descendientes desde que "Horarios reservados"/"Reservas
    aisladas" quedó fuera del `QScrollArea` de la grilla (pedido de la
    clienta, para que se vea sin scrollear todo el panel): `contenido`
    (dentro del scroll) y el propio `panel_tabla` (fuera de él, con su
    propio `panelSolapa` para no perder el fondo blanco al salir de
    `contenido`)."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_regulares, pantalla.panel_aisladas):
        descendientes = [w for w in panel.findChildren(QWidget) if w.objectName() == "panelSolapa"]
        assert len(descendientes) == 2  # `contenido` y `panel_tabla` (self no cuenta)


def test_sin_titulo_vista_previa_grilla_y_tabla_de_abajo_fuera_del_scroll(qtbot, conn):
    """Pedido de la clienta: se saca el título "Vista previa: grilla
    operativa" (el `QGroupBox` de la grilla queda sin título) y la tabla
    de abajo (antes "Horarios reservados"/"Reservas aisladas", esos dos
    títulos también se sacaron en una ronda posterior para que la tabla
    pudiera subir un poco más) queda fuera del `QScrollArea` de la
    grilla — para que se vea siempre, sin tener que scrollear el panel
    entero."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_regulares, pantalla.panel_aisladas):
        titulos = {gb.title() for gb in panel.findChildren(QGroupBox)}
        assert "Vista previa: grilla operativa" not in titulos

        scroll = panel.findChild(QScrollArea)
        panel_tabla = panel.tabla.parentWidget()
        assert isinstance(panel_tabla, QGroupBox)
        assert panel_tabla.title() == ""
        assert scroll.isAncestorOf(panel_tabla) is False


def test_tabla_de_abajo_se_expande_con_el_sobrante_de_la_ventana(qtbot, conn):
    """Pedido explícito de la clienta, ronda posterior ("ampliá el
    tamaño de la tabla... subiéndola arriba al límite de cuando termina
    el cuadro de Detalle... y que llegue lo más abajo posible dentro de
    la pantalla que se visualiza — solo tocá la tabla, nada del resto"):
    hasta la ronda anterior `layout_externo` le daba TODO el alto
    sobrante de la ventana al `QScrollArea` de arriba (`stretch=1`) y la
    tabla se quedaba con un alto fijo — cualquier alto que la tabla
    dejara de necesitar (sacar el título, un margen) había que
    compensarlo con un espaciador fijo al final para que el scroll no se
    lo llevara de vuelta. Se invirtió el reparto: `scroll` pasa a un
    alto FIJO igual al mínimo real de su contenido
    (`contenido.minimumSizeHint()`, sin dejarle nada de más — así el
    contenido de arriba no se mueve, "nada del resto") y es `panel_
    tabla` el que pasa a `stretch=1`, llevándose todo el sobrante. Sin
    nada que compensar, ya no queda ningún espaciador después de la
    tabla."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    # Aisladas mide contra `sizeHint()`, no `minimumSizeHint()` como
    # Regulares — ver `_PanelReservasAisladas.showEvent` para el motivo
    # (la columna 2, con `QSizePolicy.Expanding`, hace que el mínimo
    # quede por debajo de lo que el contenido necesita de verdad).
    for panel, alto_esperado in (
        (pantalla.panel_regulares, lambda w: w.minimumSizeHint().height()),
        (pantalla.panel_aisladas, lambda w: w.sizeHint().height()),
    ):
        layout = panel.layout()
        scroll = panel.findChild(QScrollArea)
        panel_tabla = panel.tabla.parentWidget()
        indice_scroll = layout.indexOf(scroll)
        indice_tabla = layout.indexOf(panel_tabla)

        assert layout.stretch(indice_scroll) == 0
        assert layout.stretch(indice_tabla) == 1
        assert scroll.minimumHeight() == scroll.maximumHeight() == scroll.height()
        assert scroll.height() == alto_esperado(scroll.widget())
        # Nada después de `panel_tabla`: ni espaciador ni ningún otro ítem.
        assert layout.itemAt(indice_tabla + 1) is None


def test_tabla_de_abajo_sin_margen_superior(qtbot, conn):
    """Pedido explícito de la clienta ("las tablas tienen un espacio en
    blanco arriba... más pegado al contenido que está arriba"): sin
    margen superior en el layout de la tabla de abajo, el encabezado
    arranca pegado al borde de arriba del cuadro en vez de dejar el
    margen default de Qt (9px) como hueco en blanco — el margen
    izquierdo/derecho/inferior se queda igual."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_regulares, pantalla.panel_aisladas):
        margenes = panel.tabla.parentWidget().layout().contentsMargins()
        assert margenes.top() == 0
        assert margenes.left() == 9
        assert margenes.right() == 9
        assert margenes.bottom() == 9


def test_layout_externo_sin_espaciado_en_las_dos_solapas(qtbot, conn):
    """`layout_externo` no deja espaciado default de Qt entre `scroll` y
    la tabla de abajo, en ninguna de las dos solapas — pedido explícito
    de la clienta sobre Regulares en una ronda ("subí un poco más la
    tabla para pegarlo a lo de arriba"), extendido a Aisladas en la
    ronda siguiente ("el título detalle... subilo un poco para que haya
    una separación mínima con la grilla")."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_regulares.layout().spacing() == 0
    assert pantalla.panel_aisladas.layout().spacing() == 0


def test_panel_de_filtros_de_la_grilla_queda_compacto(qtbot, conn):
    """Pedido de la clienta al revisar Reservas: en Reservas regulares, la
    columna del formulario (Profesional/Localidad/.../botones) se angosta
    un poco y ese ancho se lo lleva el panel de Filtros de la grilla
    (Localidad/Edificio/Unidad/Día de la semana/Profesional/Referencias de
    colores), que además muestra sus días de a pares y la leyenda de
    colores a 2 columnas con muestra más chica que el tamaño normal
    (40, 24) -- "hay lugar", ver `test_leyenda_de_regulares_se_agranda_un_
    poco`.

    Reservas aisladas tiene su propio criterio desde el rediseño a 4
    columnas (ver `test_aisladas_filtros_y_leyenda_separados_en_columnas_
    propias`): el panel de Filtros ya no comparte ancho con la grilla
    (columna propia, ancho fijo) y la leyenda se separa a su propia
    columna con una referencia por fila."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    assert panel.combo_profesional.minimumWidth() == 190
    assert panel.grilla._panel_filtros.maximumWidth() == 290
    assert panel.grilla._leyenda_colores._columnas == 2
    assert panel.grilla._leyenda_colores._tamano_muestra[0] == 28
    grid = panel.grilla._contenedor_dias.layout()
    assert isinstance(grid, QGridLayout)


def test_aisladas_filtros_y_leyenda_separados_en_columnas_propias(qtbot, conn):
    """Rediseño a 4 columnas de Reservas aisladas (pedido explícito de la
    clienta, confirmado con una captura mockup antes de tocar código):
    columna 1 (formulario, con los tres botones al final) / columna 2
    (solo los filtros de la grilla, mismo ancho fijo que la 1, días de la
    semana de a uno -- no agrupados en pares, para que la columna llegue
    simétrica sin hueco en blanco) / columna 3 (Referencias de colores,
    una por fila, sin marco, al triple de alto y con letra más grande
    -- ronda siguiente sobre la pantalla ya en uso -- + Detalle estirado
    hasta abajo) / columna 4 (la grilla sola, celdas más bajas para que
    entren las 14 horas sin scroll)."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas

    # Columnas 2 y 3 achicadas a dos tercios del ancho de la columna 1 —
    # pedido explícito de la clienta, ronda siguiente sobre la pantalla ya
    # en uso ("Reduci en un tercio el ancho de la columna"): ya no van al
    # mismo ancho que la columna 1, el ancho que pierden lo gana la
    # columna 4 (la grilla).
    assert panel.grilla._panel_filtros.width() == reservas_modulo._ANCHO_COLUMNA_ANGOSTA_AISLADAS
    assert panel.grilla._panel_filtros.layout().indexOf(panel.grilla._leyenda_colores) == -1
    assert isinstance(panel.grilla._contenedor_dias.layout(), QVBoxLayout)
    assert not isinstance(panel.grilla._contenedor_dias.layout(), QGridLayout)

    leyenda = panel.grilla._leyenda_colores
    assert leyenda._columnas == 1
    # Al triple del alto original (14 -> 42) — pedido explícito de la
    # clienta sobre la pantalla ya en uso.
    assert leyenda._tamano_muestra == (24, 42)
    assert leyenda._tamano_fuente == 12
    assert leyenda._alinear_izquierda is True
    assert "border: none" in leyenda.styleSheet()
    assert panel.grilla.texto_detalle.maximumHeight() == 16_777_215



def test_leyenda_de_regulares_se_agranda_un_poco(qtbot, conn):
    """Pedido explícito de la clienta: "hace un poquito mas grande el
    cuadrito de las referencias a lo alto, hay lugar para hacerlo" — acá
    "Referencias de colores" ocupa un lugar fijo dentro del panel de
    Filtros (no cambia de alto según su propio contenido), así que hay
    margen de sobra para agrandar la muestra sin comprimir nada más."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_regulares.grilla.tamano_muestra_leyenda() == (28, 26)


def test_panel_de_filtros_sin_titulo_y_con_etiquetas_renombradas(qtbot, conn):
    """Pedido de la clienta: se saca el título "Filtros" y cada filtro
    pasa a nombrarse "Filtro de ..." (Profesional queda igual)."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_regulares, pantalla.panel_aisladas):
        assert panel.grilla._panel_filtros.title() == ""
        assert panel.grilla._etiqueta_localidad.text() == "Filtro de localidad"
        assert panel.grilla._etiqueta_edificio.text() == "Filtro de edificio"
        assert panel.grilla._etiqueta_unidad.text() == "Filtro de unidad"
        assert panel.grilla._etiqueta_dia.text() == "Filtro de día de la semana"


def test_tabla_de_abajo_tiene_un_piso_de_filas_visibles(qtbot, conn):
    """Pedido de la clienta: "Horarios reservados"/"Reservas aisladas"
    muestra AL MENOS una cantidad fija de filas (con su propio scroll si
    hay más) — para dejarle más alto disponible al panel de arriba, cuyo
    "Detalle" antes quedaba fuera de la vista. Aisladas parte de más
    filas que Regulares (4 contra 3) porque a esa solapa le sobraba lugar
    debajo de "Detalle"/"% Descuento" incluso con las 3 de antes.

    Desde la ronda de "ampliá el tamaño de la tabla... que llegue lo más
    abajo posible", este número ya no es el alto EXACTO de la tabla (que
    ahora crece con `stretch=1` para usar el sobrante de la ventana) sino
    su PISO — `setMinimumHeight` en vez de `setFixedHeight` — así que acá
    se compara con `>=`, no con `==`."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_regulares.tabla.height() >= _alto_para_filas(pantalla.panel_regulares.tabla, 3)
    assert pantalla.panel_aisladas.tabla.height() >= _alto_para_filas(pantalla.panel_aisladas.tabla, 4)


def test_tabla_horarios_reservados_escrolea_con_mas_filas_de_las_que_entran(qtbot, conn):
    """Pedido de la clienta: las tablas de abajo tienen que ser
    scrolleables verticalmente — ya lo eran por default de Qt (mismo
    criterio que Llaves: `verticalScrollBar().maximum() > 0` cuando hay
    más filas de las que entran), este test lo deja cubierto de acá en
    adelante. Desde que la tabla creció con `stretch=1` para usar el
    sobrante de la ventana (ronda "ampliá el tamaño de la tabla..."),
    hacen falta bastantes más filas que antes para forzar el desborde —
    una por día de la semana (6) ya no alcanza con la tabla agrandada."""
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
    repo = obtener_repositorio(conn, "ReservaRegular")
    repo_prof = obtener_repositorio(conn, "Profesional")
    cantidad_filas = 0
    for i in range(6):
        id_profesional = repo_prof.crear(CategoriaProfesional="R", Apellido=f"Prof{i}")
        for dia in dias:
            repo.crear(
                IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana=dia,
                HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
            )
            cantidad_filas += 1
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1300, 900)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    assert pantalla.panel_regulares.tabla.rowCount() == cantidad_filas
    assert pantalla.panel_regulares.tabla.verticalScrollBar().maximum() > 0


def test_tabla_reservas_aisladas_escrolea_con_mas_filas_de_las_que_entran(qtbot, conn):
    """Ver `test_tabla_horarios_reservados_escrolea_con_mas_filas_de_las_
    que_entran`: desde que la tabla creció con `stretch=1`, hacen falta
    bastantes más filas que antes para forzar el desborde."""
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Pérez")
    repo = obtener_repositorio(conn, "ReservaAislada")
    cantidad_filas = 30
    for dia in range(1, cantidad_filas + 1):
        repo.crear(
            IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha=f"2026-{1 + dia // 28:02d}-{1 + dia % 28:02d}",
            HoraInicio=9, HoraFin=10, Estado="Confirmada", AplicaRecargo=0,
        )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1300, 900)
    pantalla.show()
    pantalla.pestanas.setCurrentIndex(1)  # Reservas aisladas — no es la solapa por default
    qtbot.waitExposed(pantalla)

    assert pantalla.panel_aisladas.tabla.rowCount() == cantidad_filas
    assert pantalla.panel_aisladas.tabla.verticalScrollBar().maximum() > 0


def test_tabla_aisladas_columnas_angostadas_sin_scroll_horizontal(qtbot, conn):
    """Pedido explícito de la clienta, cierre de esta solapa: "El objetivo
    es que se vea todo sin escrolear en horizontal" — ajuste puntual de
    ancho por columna sobre la tabla de abajo (`_ajustar_columnas_
    aisladas`, no el `_ajustar_columnas` genérico que usan Regulares/
    Extraordinaria). "Consultorio" pasa a llamarse "Consul" solo en esta
    tabla, y la columna queda al ancho natural que necesita ese título
    (sin el 60% pedido literalmente: un primer intento con ese
    porcentaje recortaba la propia etiqueta "Consul" a la mitad,
    confirmado con una captura — ver `_ajustar_columnas_aisladas`)."""
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Pérez")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-11-09",
        HoraInicio=9, HoraFin=10, Estado="Confirmada", AplicaRecargo=0,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1500, 900)
    pantalla.show()
    pantalla.pestanas.setCurrentIndex(1)
    qtbot.waitExposed(pantalla)

    tabla = pantalla.panel_aisladas.tabla
    assert tabla.horizontalHeaderItem(reservas_modulo._COL_AISLADAS_CONSULTORIO).text() == "Consul"
    assert tabla.horizontalScrollBar().maximum() == 0

    # Ninguna columna "al mínimo" quedó más angosta que su propio título
    # (serían clipeados, mismo bug ya corregido para "Consul")
    for columna in (
        reservas_modulo._COL_AISLADAS_CONSULTORIO,
        reservas_modulo._COL_AISLADAS_REUBICACION,
        reservas_modulo._COL_AISLADAS_PERIODO_IMPUTADO,
    ):
        texto = tabla.horizontalHeaderItem(columna).text()
        ancho_minimo_titulo = QFontMetrics(tabla.font()).horizontalAdvance(texto)
        assert tabla.columnWidth(columna) >= ancho_minimo_titulo


def test_tabla_aisladas_formato_fecha_horario_y_columnas_centradas(qtbot, conn):
    """Pedido explícito de la clienta, cierre de esta solapa:
    - "Horario": sufijo "hs" al final ("9:00 a 10:00hs"), alineado a la
      derecha.
    - "Fecha": formato "ddd dd-mm-yyyy" (ej. "mar 15-10-2026", mismo
      criterio que Registro de ausencias — `_fmt_fecha_dia_abrev`),
      alineado a la derecha, con ancho ajustado para que entre justo.
    - "Consul"/"Reubicación"/"Período imputado": contenido centrado."""
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Pérez")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-10-15",
        HoraInicio=9, HoraFin=10, Estado="Confirmada", AplicaRecargo=0, EsReubicacion=1,
        PeriodoImputado="2026-10",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1500, 900)
    pantalla.show()
    pantalla.pestanas.setCurrentIndex(1)
    qtbot.waitExposed(pantalla)

    tabla = pantalla.panel_aisladas.tabla
    alineacion_derecha = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    alineacion_centro = Qt.AlignmentFlag.AlignCenter

    item_fecha = tabla.item(0, reservas_modulo._COL_AISLADAS_FECHA)
    assert item_fecha.text() == "jue 15-10-2026"
    assert Qt.AlignmentFlag(item_fecha.textAlignment()) == alineacion_derecha

    item_horario = tabla.item(0, reservas_modulo._COL_AISLADAS_HORARIO)
    assert item_horario.text() == "9:00 a 10:00hs"
    assert Qt.AlignmentFlag(item_horario.textAlignment()) == alineacion_derecha

    assert Qt.AlignmentFlag(
        tabla.item(0, reservas_modulo._COL_AISLADAS_CONSULTORIO).textAlignment()
    ) == alineacion_centro
    assert Qt.AlignmentFlag(
        tabla.item(0, reservas_modulo._COL_AISLADAS_REUBICACION).textAlignment()
    ) == alineacion_centro
    assert Qt.AlignmentFlag(
        tabla.item(0, reservas_modulo._COL_AISLADAS_PERIODO_IMPUTADO).textAlignment()
    ) == alineacion_centro


def test_tabla_aisladas_profesional_se_lleva_el_ancho_sobrante(qtbot, conn):
    """Pedido explícito de la clienta, cierre de esta solapa: "ese ancho
    dáselo a la columna 'Profesional'... sin espacios en blanco al final
    y sin necesidad de que se vea la barra de desplazamiento horizontal"
    — `_distribuir_ancho_sobrante_aisladas` le da a "Profesional" lo que
    sobra del ancho total de la tabla, contemplando que la barra de
    desplazamiento vertical se reserva siempre (se vea o no en este
    momento)."""
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Pérez")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-10-15",
        HoraInicio=9, HoraFin=10, Estado="Confirmada", AplicaRecargo=0,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1500, 900)
    pantalla.show()
    pantalla.pestanas.setCurrentIndex(1)
    qtbot.waitExposed(pantalla)
    # El reparto final corre en un `QTimer.singleShot(0, ...)` disparado
    # desde `showEvent` (el ancho real de `tabla` recién está resuelto
    # después de que Qt termina de acomodar el layout de toda la
    # ventana) — hace falta una vuelta más del loop de eventos.
    qtbot.wait(50)

    tabla = pantalla.panel_aisladas.tabla
    assert tabla.horizontalScrollBar().maximum() == 0
    ancho_vertical_header = tabla.verticalHeader().width()
    ancho_scrollbar_vertical = tabla.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
    suma_columnas = sum(tabla.columnWidth(c) for c in range(tabla.columnCount()))
    ancho_total_esperado = suma_columnas + ancho_vertical_header + ancho_scrollbar_vertical + reservas_modulo._ANCHO_BORDE_TABLA
    assert abs(tabla.width() - ancho_total_esperado) <= 2
    assert tabla.columnWidth(reservas_modulo._COL_AISLADAS_PROFESIONAL) > reservas_modulo._ANCHO_COL_PROFESIONAL


def test_cuadro_detalle_escrolea_con_mas_texto_del_que_entra(qtbot, conn):
    """Pedido de la clienta, repetido: el cuadro "Detalle" (no solo las
    tablas de abajo) tiene que ser scrolleable cuando el contenido no
    entra en el alto visible — ya lo era por default de Qt (`QTextEdit`
    scrollea sola), en las dos solapas."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1500, 800)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    texto_largo = "línea de detalle\n" * 30
    for indice, panel in enumerate((pantalla.panel_regulares, pantalla.panel_aisladas)):
        pantalla.pestanas.setCurrentIndex(indice)  # solo la solapa activa tiene geometría real
        qtbot.waitExposed(pantalla)
        panel.grilla.texto_detalle.setPlainText(texto_largo)
        assert panel.grilla.texto_detalle.verticalScrollBar().maximum() > 0


def test_cuadro_detalle_queda_parejo_con_la_columna_del_formulario(qtbot, conn):
    """Pedido explícito de la clienta ("que quede parejo"): en Reservas
    regulares (columna del formulario más alta, por los campos "Días" y
    "Vigencia") el cuadro "Detalle" pasa a estirarse en vez de la grilla.

    En Reservas aisladas, desde el rediseño a 4 columnas, "Detalle" vive
    en su propia columna (la 3, junto a "Referencias de colores") y
    siempre se estira sin tope de alto hasta el pie de la columna 1 (ver
    `test_aisladas_filtros_y_leyenda_separados_en_columnas_propias`), sin
    importar si la grilla de al lado queda más alta o más baja."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    grilla_regulares = pantalla.panel_regulares.grilla
    assert grilla_regulares._layout_grilla.stretch(grilla_regulares._layout_grilla.indexOf(grilla_regulares.tabla)) == 0
    assert grilla_regulares.texto_detalle.maximumHeight() > 90


def test_detalle_de_aisladas_en_su_propia_columna(qtbot, conn):
    """Rediseño a 4 columnas de Reservas aisladas: "Detalle" ya no vive
    adentro de la grilla (columna 4) ni ocupa su ancho — pasa a su propia
    columna 3, junto a "Referencias de colores". Desde que esa columna se
    achicó a dos tercios del ancho de las columnas 1/2 (pedido explícito
    de la clienta, ronda siguiente sobre la pantalla ya en uso), ya no
    comparte su ancho con ellas. En Reservas regulares no cambió nada:
    sigue dentro de la columna de la grilla, más angosto que ella."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1500, 800)
    pantalla.show()
    pantalla.pestanas.setCurrentIndex(1)
    qtbot.waitExposed(pantalla)

    panel_a = pantalla.panel_aisladas
    assert panel_a.grilla._layout_grilla.indexOf(panel_a.grilla.texto_detalle) == -1
    assert panel_a.grilla.texto_detalle.parentWidget() is not panel_a.grilla
    assert panel_a.grilla.texto_detalle.width() == reservas_modulo._ANCHO_COLUMNA_ANGOSTA_AISLADAS

    panel_r = pantalla.panel_regulares
    assert panel_r.grilla._layout_grilla.indexOf(panel_r.grilla.texto_detalle) != -1
    assert panel_r.grilla.texto_detalle.width() < panel_r.grilla.width()


def test_botones_de_accion_quedan_compactos_con_su_color(qtbot, conn):
    """Pedido explícito de la clienta: los tres botones de acción de cada
    solapa mantienen los colores de siempre (primario/secundario). Punto
    #9.1.3 (SistemaDF v0.11.2026.10): los de Aisladas (Crear/Modificar/
    Cancelar) ya no crecen aparte para alinear "Horas aisladas
    mensuales" (criterio de una ronda anterior) — pasan al mismo mínimo
    que el resto de la columna (`_ESTILO_BOTON_COMPACTO`, 22px), igual
    que los de Regulares."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.setStyleSheet(hoja_estilos(modo_oscuro=False))  # solo esta ventana, no toda la app
    pantalla.resize(1500, 800)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    botones_primarios = ["Crear reserva regular", "Crear reserva aislada"]
    botones_secundarios = [
        "Modificar reserva", "Eliminar reserva",
    ]
    alturas_esperadas = {
        "Crear reserva regular": 22, "Eliminar reserva": 22,
        "Crear reserva aislada": 22, "Modificar reserva": 22,
    }
    for indice, panel in enumerate((pantalla.panel_regulares, pantalla.panel_aisladas)):
        pantalla.pestanas.setCurrentIndex(indice)  # solo la solapa activa tiene geometría real
        qtbot.waitExposed(pantalla)
        for boton in panel.findChildren(QPushButton):
            if boton.text() in botones_primarios:
                assert boton.objectName() == "botonPrimario"
            elif boton.text() in botones_secundarios:
                assert boton.objectName() == "botonSecundario"
            else:
                continue
            if boton.text() in alturas_esperadas:
                assert boton.height() == alturas_esperadas[boton.text()]


def test_botones_de_aisladas_quedan_igual_de_compactos_que_los_de_regulares(qtbot, conn):
    """Punto #9.1.3: "achicá el alto de los tres botones... al mínimo,
    para que se vean los tres — hoy por hoy veo dos nada más". Ya no son
    más altos que los de Regulares (criterio viejo, ver el historial en
    `_ESTILO_BOTON_AISLADAS_ALTO`)."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.setStyleSheet(hoja_estilos(modo_oscuro=False))
    pantalla.resize(1500, 800)
    pantalla.show()
    pantalla.pestanas.setCurrentIndex(1)
    qtbot.waitExposed(pantalla)

    panel_a = pantalla.panel_aisladas
    for texto in ("Crear reserva aislada", "Modificar reserva", "Eliminar reserva"):
        boton = next(b for b in panel_a.findChildren(QPushButton) if b.text() == texto)
        assert boton.height() == 22
        assert boton.isVisible()


def test_grilla_de_regulares_mantiene_el_tope_identidad_sin_achicarse(qtbot, conn):
    """Pedido explícito de la clienta: la grilla de Reservas regulares
    queda scrolleable a futuro (por si algún día hace falta mostrar más
    horarios) pero SIN cambiar nada visible hoy — `limitar_alto_grilla`
    se llama con `alto_natural_grilla()` (el propio alto natural de la
    columna), no con un valor más chico, así que el tope no debe recortar
    nada de lo que ya se ve."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel_r = pantalla.panel_regulares

    assert panel_r.grilla.maximumHeight() == panel_r.grilla.alto_natural_grilla()


def test_detalle_de_aisladas_llega_al_pie_de_su_columna(qtbot, conn):
    """Desde la ronda siguiente sobre la pantalla ya en uso, la columna 3
    (leyenda + Detalle) tiene un tope de alto explícito, igual al de la
    columna 1 (`panel_col_detalle.setMaximumHeight(self._alto_referencia_
    aisladas)` — ver `_armar_ui`), así que ya no puede terminar más alta
    que ella. Lo que este test verifica sigue valiendo igual: "Detalle",
    al tener `stretch=1` sin nada después, llega siempre hasta el pie de
    SU PROPIA columna (ahora ese pie coincide con el de la columna 1, no
    por casualidad sino por el tope explícito)."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.setStyleSheet(hoja_estilos(modo_oscuro=False))
    pantalla.resize(1500, 800)
    pantalla.show()
    pantalla.pestanas.setCurrentIndex(1)
    qtbot.waitExposed(pantalla)

    panel_a = pantalla.panel_aisladas
    panel_col_detalle = panel_a.grilla._leyenda_colores.parentWidget()
    fondo_columna = panel_col_detalle.mapToGlobal(panel_col_detalle.rect().bottomLeft()).y()
    fondo_detalle = panel_a.grilla.texto_detalle.mapToGlobal(
        panel_a.grilla.texto_detalle.rect().bottomLeft()
    ).y()
    assert abs(fondo_columna - fondo_detalle) <= 5


def test_titulo_profesional_alineado_con_filtro_de_localidad(qtbot, conn):
    """Pedido explícito de la clienta: "Profesional" (primer título de la
    columna del formulario) tiene que arrancar a la misma altura que
    "Filtro de localidad" (primer título del panel de Filtros de al
    lado) — en las dos solapas. El margen superior de `form` en
    `_ALTO_TITULO_FILTROS` es lo que lo logra (`QGroupBox` le suma su
    propio margen nativo a "Filtro de localidad", que un margen en 0 del
    lado del formulario no podía igualar)."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1500, 800)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    for panel in (pantalla.panel_regulares, pantalla.panel_aisladas):
        etiqueta_profesional = next(
            hijo for hijo in panel.combo_profesional.parentWidget().findChildren(QLabel)
            if hijo.text() == "Profesional"
        )
        top_profesional = etiqueta_profesional.mapToGlobal(etiqueta_profesional.rect().topLeft()).y()
        top_filtro = panel.grilla._etiqueta_localidad.mapToGlobal(
            panel.grilla._etiqueta_localidad.rect().topLeft()
        ).y()
        assert top_profesional == top_filtro


def test_aisladas_columnas_2_3_4_terminan_a_la_altura_de_cancelar_reserva(qtbot, conn):
    """Pedido explícito de la clienta, ronda siguiente sobre la pantalla
    ya en uso: "que el cuadro de detalle"/"el contenedor de la grilla
    termine[n] a la misma altura que el botón 'Cancelar reserva'" —
    columna 1 (formulario + botones) pasa a ser la referencia de alto
    (`_alto_referencia_aisladas`, ver `_armar_ui`) para las columnas 2, 3
    y 4, que ahora llevan un tope de alto explícito en vez de poder
    quedar más altas o más bajas que ella."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1500, 800)
    pantalla.show()
    pantalla.pestanas.setCurrentIndex(1)
    qtbot.waitExposed(pantalla)

    panel = pantalla.panel_aisladas

    def pie(widget):
        return widget.mapToGlobal(widget.rect().bottomLeft()).y()

    pie_cancelar = pie(panel.boton_cancelar)
    assert abs(pie(panel._panel_filtros_aisladas) - pie_cancelar) <= 5
    assert abs(pie(panel._panel_col_detalle_aisladas) - pie_cancelar) <= 5
    assert abs(pie(panel.grilla) - pie_cancelar) <= 5


def test_aisladas_profesional_y_filtro_localidad_suben_16px(qtbot, conn):
    """Pedido explícito de la clienta, ronda siguiente sobre la pantalla
    ya en uso: "Profesional" (columna 1) y "Filtro de localidad" (columna
    2) suben 16px para arrancar en el mismo píxel que "Referencias de
    colores" (columna 3, que no se movió esta ronda) — confirmado contra
    una captura real, ver CLAUDE.md. No se compara acá contra el título
    nativo de "Referencias de colores" (un `QGroupBox` sin marco): medir
    su posición exacta depende del cálculo de `QStyle` para el título, que
    ya dio una discrepancia real entre el render offscreen de los tests y
    la pantalla real de la clienta en una ronda anterior (ver
    `docs/historial/reservas.md`) — las dos etiquetas (Profesional/Filtro
    de localidad) siguen a la misma altura entre sí, y la diferencia de
    16px contra el margen de la columna 3 queda fijada por constante
    (`_ALTO_TITULO_COLUMNA_AISLADAS - _ALTO_ETIQUETA_COLUMNAS_1_2_
    AISLADAS`), no por una medición de pixels frágil."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1500, 800)
    pantalla.show()
    pantalla.pestanas.setCurrentIndex(1)
    qtbot.waitExposed(pantalla)

    panel = pantalla.panel_aisladas
    etiqueta_profesional = next(
        hijo for hijo in panel.combo_profesional.parentWidget().findChildren(QLabel)
        if hijo.text() == "Profesional"
    )
    top_profesional = etiqueta_profesional.mapToGlobal(etiqueta_profesional.rect().topLeft()).y()
    top_filtro = panel.grilla._etiqueta_localidad.mapToGlobal(
        panel.grilla._etiqueta_localidad.rect().topLeft()
    ).y()
    assert top_profesional == top_filtro
    assert (
        reservas_modulo._ALTO_TITULO_COLUMNA_AISLADAS
        - reservas_modulo._ALTO_ETIQUETA_COLUMNAS_1_2_AISLADAS
    ) == 16


def test_campo_fecha_aisladas_muestra_dia_de_la_semana(qtbot, conn):
    """Pedido explícito de la clienta: el campo "Fecha" de Reservas
    aisladas pasa al mismo formato "día de la semana abreviado" que
    Registro de ausencias/Fechas especiales."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.campo_fecha.setDate(QDate(2026, 9, 25))  # viernes
    assert panel.campo_fecha.text() == "vie 25-09-2026"


def test_checkbox_de_reubicacion_etiqueta_corta_en_la_misma_fila_que_recargo(qtbot, conn):
    """Pedido explícito de la clienta sobre Reservas aisladas: la
    aclaración larga de "Es reubicación (compensa una ausencia...)" se
    saca — queda solo "Es reubicación" — y pasa a compartir fila con
    "Aplica recargo" en vez de ir cada uno en su propia línea."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    assert panel.casilla_reubicacion.text() == "Es reubicación"
    assert "\n" not in panel.casilla_reubicacion.text()
    # Misma fila: comparados dentro del mismo padre, quedan a la misma
    # altura en vez de uno debajo del otro.
    assert panel.casilla_recargo.y() == panel.casilla_reubicacion.y()


def test_crear_reserva_regular_sin_conflicto_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(1)
    pantalla.panel_regulares._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1
    assert pantalla.panel_regulares.tabla.rowCount() == 1


def test_crear_reserva_regular_sin_avisos_muestra_alerta_de_exito(qtbot, conn, monkeypatch):
    """Punto #9.1.9: "Alerta final indicando 'Reserva cargada con
    éxito'" — solo cuando no hubo ningún aviso que mostrar en su lugar.
    El horario default (9-10hs) cae parcialmente dentro del bloque
    rígido sembrado por defecto (9-11hs) y SÍ genera un aviso — se usa
    un horario fuera de los dos bloques rígidos de fábrica (9-11/18-21)
    para probar el camino sin avisos."""
    _preparar(conn)
    textos: list[tuple] = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: textos.append(a)))
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    panel.spin_desde.setValue(12)
    panel.spin_hasta.setValue(13)
    panel._crear()
    assert any("Reserva cargada con éxito" in t[2] for t in textos)


def test_crear_reserva_regular_avisa_si_falta_llave_y_confirma(qtbot, conn):
    """Pedido explícito de la clienta: al cargar una reserva regular, si
    al profesional le falta la llave del edificio y/o de la unidad, avisa
    con Confirmar/Cancelar en vez de bloquear — la fixture responde "Yes"
    por default, así que la reserva se crea igual."""
    _preparar(conn)
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    id_llave = crear_llave(conn, tipo="Edificio")
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(1)
    pantalla.panel_regulares._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1


def test_crear_reserva_regular_no_crea_si_cancela_por_llave_faltante(qtbot, conn, monkeypatch):
    _preparar(conn)
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    id_llave = crear_llave(conn, tipo="Edificio")
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio)
    conn.commit()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(1)
    pantalla.panel_regulares._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 0


def test_crear_reserva_regular_con_llave_asignada_no_avisa(qtbot, conn, monkeypatch):
    """Con la llave del edificio ya asignada al profesional Y una placa
    ya asignada en la unidad, no hay nada que avisar sobre eso puntual —
    el cartel nuevo de "EN GENERAL" (confirmar datos antes de crear) sí
    se dispara igual (es independiente de llaves/placas), así que el
    stub tiene que contestar "Sí" ahí para que la reserva se cree, pero
    registra los TÍTULOS vistos para confirmar que "Falta llave o placa"
    nunca apareció."""
    _preparar(conn)
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_llave = crear_llave(conn, tipo="Edificio")
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    asignar_llave(conn, id_llave=id_llave, id_profesional=id_profesional)
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad, PosicionTablero=1, IdProfesional=id_profesional, Activo=1)
    conn.commit()
    titulos: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (titulos.append(a[1]), QMessageBox.StandardButton.Yes)[1]),
    )

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(
        pantalla.panel_regulares.combo_profesional.findData(id_profesional)
    )
    pantalla.panel_regulares._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1
    assert "Falta llave o placa" not in titulos


def test_crear_reserva_regular_avisa_solo_por_placa_si_no_hay_llaves_configuradas(qtbot, conn, monkeypatch):
    """Sin ninguna Llave cargada en el sistema no hay nada que chequear
    de acceso (ver `llaves_faltantes_para_reserva`), pero la placa sigue
    faltando — el cartel combinado se dispara igual, solo por placa.
    `avisos` guarda (título, texto) de TODOS los `question()` — ahora
    también pasa por acá el cartel nuevo de "EN GENERAL" ("Crear reserva
    regular"), así que se filtra por título en vez de asumir una sola
    llamada en total."""
    _preparar(conn)
    avisos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (avisos.append((a[1], a[2])), QMessageBox.StandardButton.Yes)[1]),
    )

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(1)
    pantalla.panel_regulares._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1
    avisos_llave_placa = [texto for titulo, texto in avisos if titulo == "Falta llave o placa"]
    assert len(avisos_llave_placa) == 1
    assert "placa de la unidad" in avisos_llave_placa[0]
    assert "llave" not in avisos_llave_placa[0]


def test_crear_reserva_regular_avisa_con_llave_y_placa_juntas_en_un_mismo_cartel(qtbot, conn, monkeypatch):
    """Pedido explícito de la clienta: si faltan las dos cosas, un solo
    cartel las menciona a ambas — no dos avisos seguidos."""
    _preparar(conn)
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    id_llave = crear_llave(conn, tipo="Edificio")
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio)
    conn.commit()
    avisos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (avisos.append((a[1], a[2])), QMessageBox.StandardButton.Yes)[1]),
    )

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(1)
    pantalla.panel_regulares._crear()

    avisos_llave_placa = [texto for titulo, texto in avisos if titulo == "Falta llave o placa"]
    assert len(avisos_llave_placa) == 1
    assert "llave del edificio" in avisos_llave_placa[0]
    assert "placa de la unidad" in avisos_llave_placa[0]


def test_crear_reserva_regular_con_varios_dias_tildados_crea_una_por_dia(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    panel._checks_dia["Martes"].setChecked(True)
    panel._checks_dia["Jueves"].setChecked(True)
    # Lunes ya viene tildado por defecto -> quedan 3 días en total
    panel._crear()

    dias = {
        f["DiaSemana"] for f in conn.execute("SELECT DiaSemana FROM ReservaRegular").fetchall()
    }
    assert dias == {"Lunes", "Martes", "Jueves"}
    assert panel.tabla.rowCount() == 3


def test_crear_reserva_regular_muestra_vista_previa_y_cancelar_no_borra_el_formulario(qtbot, conn, monkeypatch):
    """Pedido explícito de la clienta ("EN GENERAL"): antes de crear
    cualquier reserva, un cartel con los datos a guardar, Confirmar/
    Cancelar — si cancela, el formulario sigue cargado tal cual para
    poder editar y reintentar, no se borra nada."""
    _preparar(conn)
    textos: list[str] = []

    def _responder(*args, **kwargs):
        titulo, texto = args[1], args[2]
        textos.append(texto)
        # Confirma el llave/placa si apareciera (no es lo que se prueba
        # acá) pero cancela puntualmente la vista previa nueva.
        return QMessageBox.StandardButton.No if titulo == "Crear reserva regular" else QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_responder))
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)

    panel._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 0
    assert any("Profesional:" in t and "Días: Lunes" in t for t in textos)
    # El formulario sigue cargado, no se reseteó.
    assert panel.combo_profesional.currentIndex() == 1
    assert panel._checks_dia["Lunes"].isChecked()


def test_crear_reserva_regular_confirma_vista_previa_y_crea(qtbot, conn, monkeypatch):
    _preparar(conn)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)

    panel._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1


def test_crear_reserva_regular_sin_ningun_dia_tildado_avisa_y_no_crea(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel._checks_dia["Lunes"].setChecked(False)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 0


def _crear_segundo_consultorio(conn, numero=2):
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, ?)", (id_unidad, numero))
    conn.commit()
    return conn.execute(
        "SELECT IdConsultorio FROM Consultorio WHERE NumeroConsultorio = ?", (numero,)
    ).fetchone()["IdConsultorio"]


def test_precargar_desde_pedido_carga_el_primer_grupo_y_deja_el_resto_en_cola(qtbot, conn):
    """#22: "Confirmar reserva" de Lista de espera precarga Reservas con
    la primera `GrupoCobertura` y guarda el resto para cuando haga falta
    más de una ReservaRegular para cubrir todo el pedido."""
    _preparar(conn)
    id_consultorio_1 = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_consultorio_2 = _crear_segundo_consultorio(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    grupos = [
        GrupoCobertura(id_consultorio=id_consultorio_1, hora_inicio=9, hora_fin=12, dias=["Lunes"]),
        GrupoCobertura(id_consultorio=id_consultorio_2, hora_inicio=14, hora_fin=17, dias=["Jueves"]),
    ]
    panel.precargar_desde_pedido(id_profesional=id_profesional, grupos=grupos)

    assert panel.combo_profesional.currentData() == id_profesional
    assert panel.combo_consultorio.currentData() == id_consultorio_1
    assert panel.spin_desde.value() == 9 and panel.spin_hasta.value() == 12
    assert panel._dias_seleccionados() == ["Lunes"]
    assert len(panel._cola_precarga_pedido) == 1


def test_precargar_desde_pedido_avanza_de_parte_en_parte_y_recien_resuelve_el_pedido_al_final(qtbot, conn):
    """La cobertura necesita 2 ReservaRegular distintas (consultorios/
    horarios distintos) para cubrir todo el pedido — el pedido tiene que
    seguir Activo después de confirmar solo la primera parte, y pasar a
    Resuelto recién al confirmar la última."""
    _preparar(conn)
    id_consultorio_1 = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_consultorio_2 = _crear_segundo_consultorio(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_pedido = crear_pedido(
        conn, id_profesional=id_profesional,
        bloques=[{"dias": ["Lunes", "Jueves"], "horario_desde": 9, "horario_hasta": 12}],
    )

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    grupos = [
        GrupoCobertura(id_consultorio=id_consultorio_1, hora_inicio=9, hora_fin=12, dias=["Lunes"]),
        GrupoCobertura(id_consultorio=id_consultorio_2, hora_inicio=14, hora_fin=17, dias=["Jueves"]),
    ]
    panel.precargar_desde_pedido(id_profesional=id_profesional, grupos=grupos)

    panel._crear()  # confirma la parte 1/2

    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1
    assert obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)["Estado"] == "Activo"
    assert panel.combo_consultorio.currentData() == id_consultorio_2
    assert panel._dias_seleccionados() == ["Jueves"]
    assert panel.spin_desde.value() == 14 and panel.spin_hasta.value() == 17

    panel._crear()  # confirma la parte 2/2

    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 2
    assert obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)["Estado"] == "Resuelto"


def test_precargar_desde_pedido_con_un_solo_grupo_resuelve_de_una(qtbot, conn):
    """El caso más común (Verde, un solo bloque): una sola ReservaRegular
    alcanza, así que el pedido queda Resuelto apenas se confirma esa
    única parte — sin ninguna cola pendiente."""
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_pedido = crear_pedido(
        conn, id_profesional=id_profesional, bloques=[{"dias": ["Lunes"], "horario_desde": 9, "horario_hasta": 12}],
    )

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.precargar_desde_pedido(
        id_profesional=id_profesional,
        grupos=[GrupoCobertura(id_consultorio=id_consultorio, hora_inicio=9, hora_fin=12, dias=["Lunes"])],
    )
    panel._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1
    assert obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)["Estado"] == "Resuelto"
    assert panel._cola_precarga_pedido == []


def test_crear_reserva_regular_con_conflicto_en_un_dia_sigue_con_los_demas(qtbot, conn, monkeypatch):
    """Si uno de los días elegidos choca con OTRO profesional no
    relacionado (conflicto bloqueante) y el operador lo cancela
    (responde "No"), los demás días tildados que sí están libres igual
    se cargan."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=otro_profesional, IdConsultorio=id_consultorio, DiaSemana="Martes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    # Con placa asignada, el único cartel "No" que dispara este test es el
    # del conflicto bloqueante de Martes — si le faltara la placa, el
    # monkeypatch global de "No" cancelaría la carga entera antes de
    # llegar al conflicto (ver el aviso combinado llave/placa).
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad, PosicionTablero=1, IdProfesional=id_profesional, Activo=1)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel._checks_dia["Martes"].setChecked(True)  # Lunes ya viene tildado por defecto

    # El cartel nuevo de "EN GENERAL" (confirmar datos antes de crear)
    # se contesta "Sí" — es el único "No" que importa acá es el del
    # conflicto bloqueante de Martes.
    def _responder(*args, **kwargs):
        titulo = args[1]
        if titulo == "Conflictos detectados":
            return QMessageBox.StandardButton.No
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_responder))
    panel._crear()  # Martes choca con "Otro" (conflicto bloqueante) y se cancela; Lunes es libre

    reservas_del_profesional = conn.execute(
        "SELECT DiaSemana FROM ReservaRegular WHERE IdProfesional = ?", (id_profesional,)
    ).fetchall()
    assert {f["DiaSemana"] for f in reservas_del_profesional} == {"Lunes"}
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 2  # el Lunes propio + el Martes de "Otro"


def test_crear_reserva_regular_resuelve_pedido_unico_de_lista_de_espera_automaticamente(qtbot, conn):
    """DC-10 §2.2 paso 5 (pedido explícito de la clienta): con un solo
    pedido Activo del profesional, se resuelve solo, sin preguntar nada."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_pedido = crear_pedido(
        conn, id_profesional=id_profesional,
        bloques=[{"dias": ["Lunes"], "horario_desde": 9, "horario_hasta": 10}],
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(
        pantalla.panel_regulares.combo_profesional.findData(id_profesional)
    )
    pantalla.panel_regulares._crear()

    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    assert pedido["Estado"] == "Resuelto"


def test_crear_reserva_regular_no_resuelve_con_mas_de_un_pedido_activo(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    for _ in range(2):
        crear_pedido(
            conn, id_profesional=id_profesional,
            bloques=[{"dias": ["Lunes"], "horario_desde": 9, "horario_hasta": 10}],
        )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares._crear()

    estados = {p["Estado"] for p in obtener_repositorio(conn, "ListaEspera").listar(IdProfesional=id_profesional)}
    assert estados == {"Activo"}  # con más de un pedido activo no se resuelve nada, queda manual


def test_crear_reserva_regular_con_conflicto_pide_confirmacion_y_fuerza(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel._crear()  # primera reserva 9-10 Lunes

    # el alta anterior dejó el formulario en blanco -> hay que volver a
    # elegir el profesional para la segunda carga.
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel._crear()  # misma reserva de nuevo -> conflicto bloqueante
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 2  # forzada por QMessageBox mockeado


def test_crear_reserva_regular_regenera_liquidacion_enviada(qtbot, conn):
    """DC-08 §3.7: cargar una reserva regular tiene que regenerar sola la
    liquidación del período en curso si ya estaba Enviada, dejándola
    marcada como pendiente de reenvío."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    periodo = periodo_actual(conn)
    emitir_liquidacion(conn, id_profesional=id_profesional, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_profesional, periodo=periodo, enviada=True)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(
        pantalla.panel_regulares.combo_profesional.findData(id_profesional)
    )
    pantalla.panel_regulares._crear()

    emisiones = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    assert len(emisiones) == 2
    ultima = max(emisiones, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] == "Regenerada no enviada"


def test_modificar_reserva_regular_regenera_liquidacion_enviada(qtbot, conn, monkeypatch):
    """Punto #9.1.9: cualquiera de los tres botones que afecte el
    período en curso regenera y marca no enviada la liquidación del
    profesional — acá vía "Modificar reserva"."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    periodo = periodo_actual(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(
        pantalla.panel_regulares.combo_profesional.findData(id_profesional)
    )
    pantalla.panel_regulares._crear()

    emitir_liquidacion(conn, id_profesional=id_profesional, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_profesional, periodo=periodo, enviada=True)
    conn.commit()

    emitidas_antes = len(
        obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    )
    pantalla.panel_regulares.tabla.selectRow(0)
    reserva = pantalla.panel_regulares._fila_seleccionada()
    _mockear_dialogo_modificar_regular(
        monkeypatch, hora_inicio=reserva["HoraInicio"], hora_fin=14,
        vigencia_inicio=reserva["VigenciaInicio"], vigencia_fin=None,
    )
    pantalla.panel_regulares._modificar_seleccionada()

    emisiones = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    assert len(emisiones) == emitidas_antes + 1
    ultima = max(emisiones, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] == "Regenerada no enviada"


def test_eliminar_reserva_regular_borra_la_fila_con_confirmacion(qtbot, conn):
    """Punto #9.1.6: "Finalizar reserva a fin de mes" pasa a "Eliminar
    reserva" — borra la fila de la base y la saca de la tabla, en vez de
    solo ponerle fecha de fin."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(1)
    pantalla.panel_regulares._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1

    pantalla.panel_regulares.tabla.selectRow(0)
    pantalla.panel_regulares._eliminar_seleccionada()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 0
    assert pantalla.panel_regulares.tabla.rowCount() == 0


def test_eliminar_reserva_regular_cancelada_por_el_usuario_no_borra_nada(qtbot, conn, monkeypatch):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(1)
    pantalla.panel_regulares._crear()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    pantalla.panel_regulares.tabla.selectRow(0)
    pantalla.panel_regulares._eliminar_seleccionada()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1


def test_eliminar_reserva_regular_regenera_liquidacion_enviada(qtbot, conn):
    """Punto #9.1.9 aplicado a "Eliminar reserva"."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    periodo = periodo_actual(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(
        pantalla.panel_regulares.combo_profesional.findData(id_profesional)
    )
    pantalla.panel_regulares._crear()

    emitir_liquidacion(conn, id_profesional=id_profesional, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_profesional, periodo=periodo, enviada=True)
    conn.commit()

    pantalla.panel_regulares.tabla.selectRow(0)
    pantalla.panel_regulares._eliminar_seleccionada()

    emisiones = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    ultima = max(emisiones, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] == "Regenerada no enviada"


def test_tecla_delete_en_regulares_elimina_la_reserva(qtbot, conn):
    """Pedido explícito de la clienta, "todo el sistema": Delete sobre
    la fila de la tabla hace lo mismo que "Eliminar reserva"."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(1)
    pantalla.panel_regulares._crear()
    pantalla.panel_regulares.tabla.selectRow(0)
    qtbot.keyClick(pantalla.panel_regulares.tabla, Qt.Key.Key_Delete)
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 0


def test_panel_regulares_recibe_foco_en_profesional_al_mostrarse(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.panel_regulares.combo_profesional.hasFocus())


def test_tabla_regulares_click_en_columna_ordena_y_alterna_sentido(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    panel._checks_dia["Miércoles"].setChecked(True)  # Lunes + Miércoles
    panel._crear()
    assert panel.tabla.rowCount() == 2

    panel.tabla.horizontalHeader().sectionClicked.emit(5)  # "Día" ascendente
    dias_asc = [panel.tabla.item(f, 5).text() for f in range(panel.tabla.rowCount())]
    assert dias_asc == ["Lunes", "Miércoles"]

    panel.tabla.horizontalHeader().sectionClicked.emit(5)  # de nuevo -> descendente
    dias_desc = [panel.tabla.item(f, 5).text() for f in range(panel.tabla.rowCount())]
    assert dias_desc == ["Miércoles", "Lunes"]


def test_modificar_seleccionada_edita_la_fila_existente_sin_precargar_el_formulario(qtbot, conn, monkeypatch):
    """Punto #9.1.4: "Modificar reserva" edita la fila EXISTENTE a
    través de un cuadro de diálogo, sin finalizarla ni precargar el
    formulario de alta — "si quiero modifico algo puntual y la reserva
    sigue corriendo con esa modificación"."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    panel._checks_dia["Martes"].setChecked(True)  # Lunes + Martes
    panel.spin_desde.setValue(14)
    panel.spin_hasta.setValue(16)
    panel._crear()  # crea Lunes 14-16 y Martes 14-16

    fila_lunes = next(
        i for i in range(panel.tabla.rowCount())
        if panel.tabla.item(i, 5).text() == "Lunes"
    )
    panel.tabla.selectRow(fila_lunes)
    reserva = panel._fila_seleccionada()
    _mockear_dialogo_modificar_regular(
        monkeypatch, hora_inicio=reserva["HoraInicio"], hora_fin=18,
        vigencia_inicio=reserva["VigenciaInicio"], vigencia_fin=None,
    )
    panel._modificar_seleccionada()

    # la fila del Lunes quedó editada (sigue vigente), sin tocar el Martes
    filas = conn.execute("SELECT DiaSemana, HoraFin, VigenciaFin FROM ReservaRegular").fetchall()
    por_dia = {f["DiaSemana"]: f for f in filas}
    assert por_dia["Lunes"]["HoraFin"] == 18
    assert por_dia["Lunes"]["VigenciaFin"] is None
    assert por_dia["Martes"]["HoraFin"] == 16

    # el formulario de alta no se tocó (`_crear()` ya lo había dejado en
    # su default de 9-10 al cargar la segunda reserva).
    assert panel.spin_desde.value() == 9
    assert panel.spin_hasta.value() == 10


def test_modificar_seleccionada_puede_terminar_la_reserva_desde_el_dialogo(qtbot, conn, monkeypatch):
    """"Desde el cuadro de diálogo... si quiero la termino" — poniendo
    una Vigencia hasta real queda igual de terminada que antes, pero sin
    pasar por "crear de nuevo"."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    panel._crear()  # Lunes 9-10

    panel.tabla.selectRow(0)
    reserva = panel._fila_seleccionada()
    _mockear_dialogo_modificar_regular(
        monkeypatch, hora_inicio=reserva["HoraInicio"], hora_fin=reserva["HoraFin"],
        vigencia_inicio=reserva["VigenciaInicio"], vigencia_fin="2026-12-31",
    )
    panel._modificar_seleccionada()

    fila = conn.execute("SELECT VigenciaFin FROM ReservaRegular").fetchone()
    assert fila["VigenciaFin"] == "2026-12-31"


def test_modificar_seleccionada_sin_fila_avisa(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel._modificar_seleccionada()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular WHERE VigenciaFin IS NOT NULL").fetchone()["c"] == 0


def test_modificar_seleccionada_cancelada_por_el_usuario_no_cambia_nada(qtbot, conn, monkeypatch):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    panel._crear()  # Lunes 9-10

    panel.tabla.selectRow(0)
    _mockear_dialogo_modificar_regular(monkeypatch, aceptar=False)
    panel._modificar_seleccionada()

    fila = conn.execute("SELECT HoraFin FROM ReservaRegular").fetchone()
    assert fila["HoraFin"] == 10


def test_crear_reserva_aislada_sin_conflicto_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1
    assert pantalla.panel_aisladas.tabla.rowCount() == 1


def test_crear_reserva_aislada_avisa_si_falta_llave_y_confirma(qtbot, conn):
    """Mismo pedido que en Reservas regulares (ver esa solapa), acá sobre
    una reserva aislada: la fixture responde "Yes" por default, así que
    la reserva se crea igual pese a la llave faltante."""
    _preparar(conn)
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    id_llave = crear_llave(conn, tipo="Edificio")
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1


def test_crear_reserva_aislada_no_crea_si_cancela_por_llave_faltante(qtbot, conn, monkeypatch):
    _preparar(conn)
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    id_llave = crear_llave(conn, tipo="Edificio")
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio)
    conn.commit()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 0


def test_crear_reserva_aislada_con_llave_asignada_no_avisa(qtbot, conn, monkeypatch):
    """Con la llave del edificio ya asignada al profesional Y una placa
    ya asignada en la unidad, no hay nada que avisar sobre eso puntual —
    el cartel nuevo de "EN GENERAL" sí se dispara igual, contestado
    "Sí"; se registran los títulos para confirmar que "Falta llave o
    placa" nunca apareció."""
    _preparar(conn)
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_llave = crear_llave(conn, tipo="Edificio")
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    asignar_llave(conn, id_llave=id_llave, id_profesional=id_profesional)
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad, PosicionTablero=1, IdProfesional=id_profesional, Activo=1)
    conn.commit()
    titulos: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (titulos.append(a[1]), QMessageBox.StandardButton.Yes)[1]),
    )

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(
        pantalla.panel_aisladas.combo_profesional.findData(id_profesional)
    )
    pantalla.panel_aisladas._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1
    assert "Falta llave o placa" not in titulos


def test_crear_reserva_aislada_avisa_solo_por_placa_si_no_hay_llaves_configuradas(qtbot, conn, monkeypatch):
    _preparar(conn)
    avisos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (avisos.append((a[1], a[2])), QMessageBox.StandardButton.Yes)[1]),
    )

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1
    avisos_llave_placa = [texto for titulo, texto in avisos if titulo == "Falta llave o placa"]
    assert len(avisos_llave_placa) == 1
    assert "placa de la unidad" in avisos_llave_placa[0]
    assert "llave" not in avisos_llave_placa[0]


def test_crear_reserva_aislada_avisa_con_llave_y_placa_juntas_en_un_mismo_cartel(qtbot, conn, monkeypatch):
    _preparar(conn)
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    id_llave = crear_llave(conn, tipo="Edificio")
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio)
    conn.commit()
    avisos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (avisos.append((a[1], a[2])), QMessageBox.StandardButton.Yes)[1]),
    )

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas._crear()

    avisos_llave_placa = [texto for titulo, texto in avisos if titulo == "Falta llave o placa"]
    assert len(avisos_llave_placa) == 1
    assert "llave del edificio" in avisos_llave_placa[0]
    assert "placa de la unidad" in avisos_llave_placa[0]


def _monkeypatch_clipboard(monkeypatch):
    copiado = []
    monkeypatch.setattr(
        "app.gui.pantallas.reservas.QGuiApplication.clipboard",
        staticmethod(lambda: type("_C", (), {"setText": lambda self, t: copiado.append(t)})()),
    )
    return copiado


def test_crear_reserva_aislada_copia_mensaje_de_detalle_al_portapapeles(qtbot, conn, monkeypatch):
    _preparar(conn)
    copiado = _monkeypatch_clipboard(monkeypatch)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas._crear()
    assert len(copiado) == 1
    assert "DETALLE RESERVA" in copiado[0]


def test_crear_reserva_aislada_de_un_mes_posterior_no_pierde_el_detalle_del_mes_en_curso(qtbot, conn, monkeypatch):
    """Bug real reportado por la clienta: parada en el período actual,
    con una hora aislada del profesional ya confirmada ese mes, agendarle
    otra para el mes siguiente copiaba al portapapeles un mensaje que
    mostraba SOLO la reserva nueva (del mes siguiente) — el detalle del
    mes en curso desaparecía por completo, a diferencia de generar el
    mismo mensaje a mano desde el Centro de mensajería, que sí mostraba
    las dos (la del mes en curso arriba, la del mes siguiente bajo
    "RESERVAS POSTERIORES", sin importe).

    Causa: `_copiar_mensaje_detalle` llamaba a `mensaje_detalle_reserva_
    aislada` con `periodo=fecha[:7]` (el mes DE LA RESERVA que se acaba
    de cargar) en vez de `periodo_actual(self.conn)` (el mes de HOY,
    mismo criterio que ya usaba el Centro de mensajería) — esa función
    solo arma "del mes" (el período consultado) y "posteriores"
    (estrictamente posterior), así que la reserva del mes en curso no
    encajaba en ninguna de las dos listas si se consultaba con el
    período de la reserva nueva, más adelante en el tiempo."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas

    # Una reserva confirmada hoy, dentro del período actual.
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel._crear()

    # Otra para el mes siguiente, mismo profesional — esta es la que
    # reproducía el bug.
    copiado = _monkeypatch_clipboard(monkeypatch)
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_fecha.setDate(panel.campo_fecha.date().addMonths(1))
    panel._crear()

    assert len(copiado) == 1
    texto = copiado[0]
    mes_actual = int(periodo_actual(conn).split("-")[1])
    assert texto.startswith(f"DETALLE RESERVA {mes_texto(mes_actual).upper()}")
    assert "RESERVAS POSTERIORES" in texto
    assert texto.index("RESERVAS POSTERIORES") > texto.index("SALDO A ABONAR")


def test_eliminar_reserva_aislada_copia_mensaje_de_detalle_al_portapapeles(qtbot, conn, monkeypatch):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas.spin_desde.setValue(13)
    pantalla.panel_aisladas.spin_hasta.setValue(14)
    pantalla.panel_aisladas._crear()

    copiado = _monkeypatch_clipboard(monkeypatch)
    pantalla.panel_aisladas.tabla.selectRow(0)
    pantalla.panel_aisladas._eliminar()
    assert len(copiado) == 1
    assert "DETALLE RESERVA" in copiado[0]


def test_crear_reserva_aislada_con_placa_asignada_copia_placas_para_los_timbres(qtbot, conn, monkeypatch):
    """Pedido explícito de la clienta: el mensaje que se copia al
    confirmar una reserva aislada tiene que incluir "PLACAS PARA LOS
    TIMBRES" cuando el profesional ya tiene una placa asignada en la
    unidad reservada — mismo mecanismo que usa Centro de mensajería
    (`mensaje_detalle_reserva_aislada`), acá solo se verifica que el
    flujo de "Reservas aisladas" quede conectado end-to-end."""
    _preparar(conn)
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    obtener_repositorio(conn, "Unidad").actualizar(id_unidad, CantLimitePlacas=200)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    asignar_placa(conn, id_unidad=id_unidad, posicion=12, id_profesional=id_profesional)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    copiado = _monkeypatch_clipboard(monkeypatch)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(
        pantalla.panel_aisladas.combo_profesional.findData(id_profesional),
    )
    pantalla.panel_aisladas._crear()

    assert len(copiado) == 1
    assert "PLACAS PARA LOS TIMBRES" in copiado[0]
    assert "Posición 12" in copiado[0]


def test_crear_reserva_aislada_regenera_el_snapshot_de_su_periodo_si_ya_existe(qtbot, conn):
    """DC-06 §3: cargar una aislada en un período que ya tiene su
    `SnapshotMensual` (ya cerró) lo deja desactualizado — ver
    `app.negocio.estadisticas.regenerar_snapshot_si_corresponde`."""
    _preparar(conn)
    periodo = periodo_actual(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "Consultorio").actualizar(id_consultorio, ValorHoraAisladaActual=1000)
    from app.negocio.estadisticas import generar_snapshot
    id_snapshot = generar_snapshot(conn, periodo)
    assert obtener_repositorio(conn, "SnapshotMensual").obtener(id_snapshot)["MontoHorasAisladas"] == 0.0

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas._crear()

    snapshots = obtener_repositorio(conn, "SnapshotMensual").listar(Periodo=periodo)
    assert len(snapshots) == 1  # se actualizó la fila, no se creó una nueva
    assert snapshots[0]["MontoHorasAisladas"] > 0


def test_eliminar_reserva_aislada_tambien_regenera_el_snapshot(qtbot, conn):
    _preparar(conn)
    periodo = periodo_actual(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "Consultorio").actualizar(id_consultorio, ValorHoraAisladaActual=1000)

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas._crear()

    from app.negocio.estadisticas import generar_snapshot
    id_snapshot = generar_snapshot(conn, periodo)
    assert obtener_repositorio(conn, "SnapshotMensual").obtener(id_snapshot)["MontoHorasAisladas"] > 0

    pantalla.panel_aisladas.tabla.selectRow(0)
    pantalla.panel_aisladas._eliminar()

    snapshot = obtener_repositorio(conn, "SnapshotMensual").obtener(id_snapshot)
    assert snapshot["MontoHorasAisladas"] == 0.0  # eliminada: ya no cuenta


def test_crear_reserva_aislada_fecha_mes_anterior_pide_confirmacion(qtbot, conn, monkeypatch):
    _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas.campo_fecha.setDate(QDate(2026, 7, 20))

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    pantalla.panel_aisladas._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 0

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    pantalla.panel_aisladas._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1


def _textos_leyenda_visibles(leyenda) -> list[str]:
    """`takeAt()` + `hide()` + `deleteLater()` (ver `LeyendaColores.
    actualizar`) saca los QLabel viejos de pantalla al toque, pero siguen
    siendo hijos de Qt hasta que el loop de eventos procesa el
    `deleteLater` — así que `findChildren` los sigue devolviendo. Filtrar
    por `isHidden()` es lo que realmente ve el usuario."""
    return [lbl.text() for lbl in leyenda.findChildren(QLabel) if not lbl.isHidden()]


def test_grilla_preview_regulares_bloquea_la_visualizacion_en_regular(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares

    assert panel.grilla.combo_modo.currentData() == "regular"
    assert panel.grilla.combo_modo.isEnabled() is False


def test_grilla_preview_aisladas_bloquea_la_visualizacion_en_aislada(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas

    assert panel.grilla.combo_modo.currentData() == "aislada"
    assert panel.grilla.combo_modo.isEnabled() is False


def test_grilla_preview_regulares_muestra_leyenda_de_colores_de_regular(qtbot, conn):
    """Pedido de la clienta: en Reservas, la leyenda de colores va debajo
    del selector de Profesional del panel de Filtros de la vista previa
    (no debajo de toda la grilla, como en Vista rápida) — y tiene que
    coincidir con el modo de la solapa."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares

    assert panel.grilla._leyenda_colores.isHidden() is False
    textos = _textos_leyenda_visibles(panel.grilla._leyenda_colores)
    assert "Se libera en el futuro." in textos  # propia de "regular"
    assert "Libre de reserva regular." not in textos  # propia de "aislada"


def test_grilla_preview_aisladas_muestra_leyenda_de_colores_de_aislada(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas

    assert panel.grilla._leyenda_colores.isHidden() is False
    textos = _textos_leyenda_visibles(panel.grilla._leyenda_colores)
    assert "Libre de reserva regular." in textos  # propia de "aislada"
    assert "Se libera en el futuro." not in textos  # propia de "regular"


def test_grilla_preview_profesional_nuevo_no_muestra_nada(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares

    # el único profesional del fixture todavía no tiene nada reservado
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    assert panel.grilla.ids_unidad_seleccionadas() == []
    assert panel.grilla.tabla.rowCount() == 0


def test_grilla_preview_todos_los_profesionales_muestra_la_grilla_completa(qtbot, conn):
    """Sin ningún profesional elegido ("Todos los profesionales"), la
    vista previa no se queda vacía: muestra todas las localidades,
    edificios, unidades y consultorios, sin ningún filtro."""
    _preparar(conn)
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares

    assert panel.combo_profesional.currentData() is None  # "Todos los profesionales" por defecto
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad]


def test_grilla_preview_acota_tambien_los_dias_a_los_que_tiene_reserva(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    repo_rr = obtener_repositorio(conn, "ReservaRegular")
    repo_rr.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=12, VigenciaInicio="2020-01-01",
    )
    repo_rr.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Jueves",
        HoraInicio=15, HoraFin=16, VigenciaInicio="2020-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))

    dias_tildados = {dia for dia, check in panel.grilla._checks_dia.items() if check.isChecked()}
    assert dias_tildados == {"Lunes", "Jueves"}


def test_formulario_vuelve_en_blanco_despues_de_crear(qtbot, conn):
    """Punto #9.1.9: "Queda cargado el nombre del profesional en el
    selector, solo cambia si se abandona el foco de la solapa" — el
    resto del formulario sí vuelve en blanco."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    id_profesional = panel.combo_profesional.currentData()
    panel.campo_vigencia_fin.setDate(QDate(2026, 12, 31))
    panel._checks_dia["Martes"].setChecked(True)

    panel._crear()

    assert panel.combo_profesional.currentData() == id_profesional
    assert panel.campo_vigencia_fin.date() == _FECHA_SIN_DATO
    assert {dia for dia, check in panel._checks_dia.items() if check.isChecked()} == {"Lunes"}


def test_reiniciar_vuelve_profesional_a_todos_los_profesionales(qtbot, conn):
    """`reiniciar()` (F3/`showEvent`) sí resetea "Profesional" — a
    diferencia de `_resetear_formulario()`, que se queda con lo cargado
    después de crear una reserva (ver el test de arriba)."""
    _preparar(conn)
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)

    panel.reiniciar()

    assert panel.combo_profesional.currentData() is None
    assert panel.combo_profesional.currentIndex() == 0
    # vuelve a "Todos los profesionales" -> la vista previa muestra la
    # grilla completa (todo lo que haya), no queda vacía
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad]


def test_datos_complementarios_del_profesional(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=12, VigenciaInicio="2020-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    # el profesional elegido tiene la reserva Lunes 9-12 (3 horas), recién cargada
    assert "3" in panel.etiqueta_horas_semanales.text()
    assert "%" in panel.etiqueta_descuento.text()

    panel.combo_profesional.setCurrentIndex(0)  # vuelve al placeholder en blanco
    assert panel.etiqueta_horas_semanales.text() == "Cant. horas regulares semanales: —"
    assert panel.etiqueta_descuento.text() == "% Descuento: —"

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    assert panel.etiqueta_horas_semanales.text() == "Cant. horas regulares semanales: 3"


def test_regulares_con_horas_semanales_y_descuento_aisladas_sin_ninguno(qtbot, conn):
    """Pedido explícito de la clienta, en varias vueltas: primero se sacó
    "Horas aisladas mensuales" de Reservas regulares (solo importan
    "Horas regulares semanales" y "% Descuento" ahí); después se sacó
    "Horas regulares semanales" y "% Descuento" de Reservas aisladas; en
    el rediseño a 4 columnas se terminó sacando también "Horas aisladas
    mensuales" de Aisladas — esa solapa queda sin ningún título
    informativo de este tipo, Regulares se queda con los dos de siempre
    ("Horas regulares semanales" y "% Descuento")."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert not hasattr(pantalla.panel_regulares, "etiqueta_horas_aisladas")
    assert hasattr(pantalla.panel_regulares, "etiqueta_horas_semanales")
    assert hasattr(pantalla.panel_regulares, "etiqueta_descuento")
    assert not hasattr(pantalla.panel_aisladas, "etiqueta_horas_aisladas")
    assert not hasattr(pantalla.panel_aisladas, "etiqueta_horas_semanales")
    assert not hasattr(pantalla.panel_aisladas, "etiqueta_descuento")


def test_grilla_preview_sigue_al_profesional_no_al_consultorio_elegido(qtbot, conn):
    _preparar(conn)
    id_unidad_1 = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    id_consultorio_1 = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Sur')")
    id_otro_edificio = conn.execute("SELECT IdEdificio FROM Edificio WHERE Nombre = 'Torre Sur'").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '2B')", (id_otro_edificio,))
    id_unidad_2 = conn.execute("SELECT IdUnidad FROM Unidad WHERE Departamento = '2B'").fetchone()["IdUnidad"]
    id_consultorio_2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1)
    id_profesional_1 = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    conn.execute(
        "INSERT INTO ReservaRegular (IdProfesional, IdConsultorio, DiaSemana, HoraInicio, HoraFin, VigenciaInicio) "
        "VALUES (?, ?, 'Lunes', 9, 10, '2020-01-01')",
        (id_profesional_1, id_consultorio_1),
    )
    conn.execute(
        "INSERT INTO ReservaRegular (IdProfesional, IdConsultorio, DiaSemana, HoraInicio, HoraFin, VigenciaInicio) "
        "VALUES (?, ?, 'Martes', 10, 11, '2020-01-01')",
        (id_profesional_2, id_consultorio_2),
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional_1))

    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_1]

    # cambiar el consultorio elegido (edificio/unidad/consultorio en
    # cascada) para la PRÓXIMA alta no debe mover la vista previa: sigue
    # mostrando lo que el profesional 1 ya tiene.
    panel._seleccionar_ubicacion(id_consultorio_2)
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_1]

    # cambiar el PROFESIONAL sí la mueve, a lo que ese otro ya tiene reservado.
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional_2))
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_2]


def test_grilla_preview_pinta_azul_al_profesional_elegido(qtbot, conn):
    _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1'")  # el filtro de la grilla busca por código
    conn.commit()
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(
        next(i for i in range(panel.combo_profesional.count()) if panel.combo_profesional.itemData(i) == id_profesional)
    )
    panel._crear()  # reserva Lunes 9-10 para ese profesional/consultorio

    panel.combo_profesional.setCurrentIndex(
        next(i for i in range(panel.combo_profesional.count()) if panel.combo_profesional.itemData(i) == id_profesional)
    )
    from app.negocio.grilla_operativa import AZUL_OSCURO

    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    clave = (id_consultorio, "Lunes", 9)
    assert panel.grilla._resultado[clave].color_aro == AZUL_OSCURO


def test_grilla_preview_se_refresca_al_crear_una_reserva(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel._crear()

    # el formulario queda en blanco después del alta -> hay que volver a
    # elegir el profesional para ver reflejado lo que se acaba de cargar.
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    clave = (id_consultorio, "Lunes", 9)
    assert panel.grilla._resultado[clave].id_profesional_mostrado is not None


def test_eliminar_reserva_aislada_borra_la_fila(qtbot, conn):
    # 13-14 cae fuera de los bloques rígidos por defecto (9-11 y 18-21) para
    # que la eliminación el mismo día no choque con esa restricción aparte.
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas.spin_desde.setValue(13)
    pantalla.panel_aisladas.spin_hasta.setValue(14)
    pantalla.panel_aisladas._crear()
    pantalla.panel_aisladas.tabla.selectRow(0)
    pantalla.panel_aisladas._eliminar()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 0


def test_eliminar_reserva_aislada_pide_confirmacion_explicita(qtbot, conn, monkeypatch):
    """Punto #9.1.6 (homólogo de "Eliminar reserva" en Regulares):
    "Eliminar reserva" (antes "Cancelar reserva") pide confirmación
    antes de borrar, en vez de hacerlo directo sin preguntar nada."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(1)
    panel._crear()

    textos: list[tuple] = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (textos.append(a), QMessageBox.StandardButton.Yes)[1]),
    )
    panel.tabla.selectRow(0)
    panel._eliminar()
    assert any("Eliminar reserva" in t[1] for t in textos)
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 0


def test_eliminar_reserva_aislada_declinada_no_cambia_nada(qtbot, conn, monkeypatch):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(1)
    panel._crear()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    panel.tabla.selectRow(0)
    panel._eliminar()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1


def test_tecla_delete_en_aisladas_elimina_la_reserva(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas.spin_desde.setValue(13)
    pantalla.panel_aisladas.spin_hasta.setValue(14)
    pantalla.panel_aisladas._crear()
    pantalla.panel_aisladas.tabla.selectRow(0)
    qtbot.keyClick(pantalla.panel_aisladas.tabla, Qt.Key.Key_Delete)
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 0


def test_panel_aisladas_grilla_arranca_en_modo_aislada(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_aisladas.grilla.combo_modo.currentData() == "aislada"


def test_panel_aisladas_grilla_preview_sigue_al_profesional(qtbot, conn):
    _preparar(conn)
    id_unidad_1 = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    id_consultorio_1 = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Sur')")
    id_otro_edificio = conn.execute("SELECT IdEdificio FROM Edificio WHERE Nombre = 'Torre Sur'").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '2B')", (id_otro_edificio,))
    id_unidad_2 = conn.execute("SELECT IdUnidad FROM Unidad WHERE Departamento = '2B'").fetchone()["IdUnidad"]
    id_consultorio_2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1)
    id_profesional_1 = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional_1, IdConsultorio=id_consultorio_1, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional_2, IdConsultorio=id_consultorio_2, Fecha="2026-08-18", HoraInicio=9, HoraFin=10,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional_1))
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_1]

    # cambiar el consultorio elegido para la PRÓXIMA alta no debe mover la
    # vista previa: sigue mostrando lo que el profesional 1 ya tiene.
    panel._seleccionar_ubicacion(id_consultorio_2)
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_1]

    # cambiar el PROFESIONAL sí la mueve, a lo que ese otro ya tiene reservado.
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional_2))
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_2]


def test_panel_aisladas_grilla_preview_pinta_azul_al_profesional_elegido(qtbot, conn):
    _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1'")  # el filtro de la grilla busca por código
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-17' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(
        next(i for i in range(panel.combo_profesional.count()) if panel.combo_profesional.itemData(i) == id_profesional)
    )
    panel.campo_fecha.setDate(QDate(2026, 8, 17))
    panel._crear()  # reserva aislada 9-10 ese día

    panel.combo_profesional.setCurrentIndex(
        next(i for i in range(panel.combo_profesional.count()) if panel.combo_profesional.itemData(i) == id_profesional)
    )

    from datetime import date

    from app.negocio.dias import fecha_a_dia_semana
    from app.negocio.grilla_operativa import AZUL_OSCURO

    dia = fecha_a_dia_semana(date(2026, 8, 17))
    clave = (id_consultorio, dia, 9)
    assert panel.grilla._resultado[clave].color_aro == AZUL_OSCURO


def test_panel_aisladas_grilla_preview_se_refresca_al_crear_una_reserva(qtbot, conn):
    _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-17' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.campo_fecha.setDate(QDate(2026, 8, 17))

    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    # con "Todos los profesionales" (el default), la vista previa muestra
    # la grilla completa, no una acotada al profesional que se va a elegir
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad]

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel._crear()

    # el formulario queda en blanco después del alta -> hay que volver a
    # elegir el profesional para ver reflejado lo que se acaba de cargar.
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    from datetime import date

    from app.negocio.dias import fecha_a_dia_semana

    dia = fecha_a_dia_semana(date(2026, 8, 17))
    clave = (id_consultorio, dia, 9)
    assert panel.grilla._resultado[clave].id_profesional_mostrado is not None


def test_combo_profesional_regulares_solo_categorias_r_b_e(qtbot, conn):
    _preparar(conn)
    id_gomez = conn.execute("SELECT IdProfesional FROM Profesional WHERE Apellido = 'Gómez'").fetchone()["IdProfesional"]
    id_bono = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="B", Apellido="Bono")
    id_equipo = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="E", Apellido="Equipo")
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Ajeno")
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    combo = pantalla.panel_regulares.combo_profesional
    ids = {combo.itemData(i) for i in range(combo.count()) if combo.itemData(i) is not None}
    assert ids == {id_gomez, id_bono, id_equipo}


def test_combo_profesional_aisladas_admite_a_b_r_e(qtbot, conn):
    """Pedido de la clienta: Aisladas se abre a las cuatro categorías
    imputables (A/B/R/E) — B para marcar ocupación, E porque puede
    imputar igual que R. X/C quedan afuera, sin relación con reservas."""
    _preparar(conn)
    id_gomez = conn.execute("SELECT IdProfesional FROM Profesional WHERE Apellido = 'Gómez'").fetchone()["IdProfesional"]
    id_bono = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="B", Apellido="Bono")
    id_equipo = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="E", Apellido="Equipo")
    id_ajeno = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Ajeno")
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="X", Apellido="Inactivo")
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Contacto")
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    combo = pantalla.panel_aisladas.combo_profesional
    ids = {combo.itemData(i) for i in range(combo.count()) if combo.itemData(i) is not None}
    assert ids == {id_gomez, id_bono, id_equipo, id_ajeno}


def test_combo_profesional_muestra_tratamiento_nombre_apellido(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, Tratamiento="Lic.", NombrePila="Virginia")
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    combo = pantalla.panel_regulares.combo_profesional
    indice = combo.findData(id_profesional)
    assert combo.itemText(indice) == "Lic. Virginia Gómez"


def test_combo_profesional_antepone_el_codigo_cuando_tiene(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    obtener_repositorio(conn, "Profesional").actualizar(
        id_profesional, Tratamiento="Lic.", NombrePila="Virginia", IdCodigo="R1",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    combo = pantalla.panel_regulares.combo_profesional
    indice = combo.findData(id_profesional)
    assert combo.itemText(indice) == "R1 - Lic. Virginia Gómez"


def test_filtros_edificio_unidad_acotan_el_combo_consultorio(qtbot, conn):
    _preparar(conn)
    id_edificio_2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Sur")
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_2, Departamento="2B")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1)
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=2)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares

    indice = panel.combo_edificio.findData(id_edificio_2)
    panel.combo_edificio.setCurrentIndex(indice)
    assert panel.combo_unidad.count() == 1
    assert panel.combo_unidad.currentData() == id_unidad_2
    assert panel.combo_consultorio.count() == 2


def test_combo_localidad_y_edificio_deshabilitados_con_una_sola_opcion(qtbot, conn):
    """Con una sola localidad (o ninguna, como acá) y un solo edificio, no
    hay nada para elegir — el combo queda deshabilitado y el Enter del
    campo anterior salta directo al siguiente."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    assert panel.combo_localidad.isEnabled() is False
    assert panel.combo_edificio.isEnabled() is False


def test_combo_localidad_habilitado_con_varias_localidades(qtbot, conn):
    _preparar_dos_localidades(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_regulares.combo_localidad.isEnabled() is True


def test_combo_edificio_habilitado_con_varios_edificios_en_la_misma_localidad(qtbot, conn):
    _preparar(conn)
    obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Sur")  # misma localidad (ninguna) que "Torre Norte"
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    assert panel.combo_localidad.isEnabled() is False  # sigue habiendo una sola localidad
    assert panel.combo_edificio.isEnabled() is True


def test_combo_localidad_con_una_sola_opcion_la_completa_sola(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    assert panel.combo_localidad.currentText() == "(Sin localidad)"
    assert panel.combo_edificio.currentText() == "Torre Norte"


def test_combo_localidad_con_varias_opciones_arranca_en_seleccionar(qtbot, conn):
    """Con más de una localidad, el campo no se queda pegado a la primera
    en orden alfabético: arranca en "Seleccionar…", habilitado, obligando
    a elegir. Edificio (y en cascada Unidad/Consultorio) quedan vacíos
    hasta que se elija una localidad real."""
    _preparar_dos_localidades(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    assert panel.combo_localidad.currentText() == "Seleccionar…"
    assert panel.combo_localidad.currentData() is not None
    assert panel.combo_edificio.count() == 0
    assert panel.combo_edificio.isEnabled() is False
    assert panel.combo_unidad.count() == 0
    assert panel.combo_consultorio.count() == 0


def test_combo_edificio_con_varias_opciones_arranca_en_seleccionar(qtbot, conn):
    _preparar(conn)
    obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Sur")
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    assert panel.combo_edificio.currentText() == "Seleccionar…"
    assert panel.combo_edificio.currentData() is None
    assert panel.combo_unidad.count() == 0
    assert panel.combo_consultorio.count() == 0


def test_crear_reserva_regular_sin_elegir_consultorio_avisa_y_no_crea(qtbot, conn):
    """Con más de una localidad y ninguna elegida todavía, "Crear reserva
    regular" no puede completar el alta sin explotar — avisa y no hace
    nada, en vez de intentar guardar con IdConsultorio en blanco."""
    _preparar_dos_localidades(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 0


def test_crear_reserva_regular_eligiendo_localidad_y_edificio_persiste(qtbot, conn):
    id_edificio_1, id_consultorio_1, _, _, id_profesional = _preparar_dos_localidades(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.combo_localidad.setCurrentIndex(panel.combo_localidad.findData(_id_localidad(conn, "Ramos Mejía")))
    panel.combo_edificio.setCurrentIndex(panel.combo_edificio.findData(id_edificio_1))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1
    assert conn.execute("SELECT IdConsultorio FROM ReservaRegular").fetchone()["IdConsultorio"] == id_consultorio_1


def test_grilla_preview_filtro_exclusivo_no_muestra_otros_profesionales(qtbot, conn):
    """Con R2 elegido, la vista previa solo muestra sus propias celdas —
    aunque otro profesional (B1) tenga algo reservado en el mismo día y
    unidad, a otra hora."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Norte")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    repo_prof = obtener_repositorio(conn, "Profesional")
    id_r2 = repo_prof.crear(CategoriaProfesional="R", Apellido="Lo Veci", IdCodigo="R2")
    id_b1 = repo_prof.crear(CategoriaProfesional="B", Apellido="Bono", IdCodigo="B1")
    repo = obtener_repositorio(conn, "ReservaRegular")
    repo.crear(
        IdProfesional=id_r2, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    repo.crear(
        IdProfesional=id_b1, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=14, HoraFin=15, VigenciaInicio="2020-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_r2))

    codigos = {c.codigo for c in panel.grilla._resultado.values() if c.codigo}
    assert codigos == {"R2"}


def test_spin_horario_aisladas_permite_medias_horas(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(1)
    assert panel.spin_desde.singleStep() == 0.5
    assert panel.spin_hasta.singleStep() == 0.5
    panel.spin_desde.setValue(9.5)
    panel.campo_fecha.setDate(QDate(2026, 8, 17))
    panel.spin_hasta.setValue(10.5)
    panel._crear()
    fila = conn.execute("SELECT HoraInicio, HoraFin FROM ReservaAislada").fetchone()
    assert fila["HoraInicio"] == 9.5
    assert fila["HoraFin"] == 10.5


def test_tabla_aisladas_ordenada_por_fecha_y_hora(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    repo = obtener_repositorio(conn, "ReservaAislada")
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-20", HoraInicio=9, HoraFin=10)
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=14, HoraFin=15)
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=9, HoraFin=10)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    filas = [
        (panel.tabla.item(f, 5).text(), panel.tabla.item(f, 6).text(), panel.tabla.item(f, 7).text())
        for f in range(panel.tabla.rowCount())
    ]
    assert filas == [
        ("Martes", "mar 18-08-2026", "9:00 a 10:00hs"),
        ("Martes", "mar 18-08-2026", "14:00 a 15:00hs"),
        ("Jueves", "jue 20-08-2026", "9:00 a 10:00hs"),
    ]


def test_tabla_aisladas_columna_valor(qtbot, conn):
    _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-10' WHERE IdConfiguracion = 1"
    )
    conn.execute("UPDATE Consultorio SET ValorHoraAisladaActual = 1000")
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    repo = obtener_repositorio(conn, "ReservaAislada")
    # dentro del período actual (2026-08) -> tiene valor
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=11)
    # período posterior al actual -> sin valor
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-09-17", HoraInicio=9, HoraFin=10)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    from app.negocio.formato import formatear_moneda

    valores = {panel.tabla.item(f, 6).text(): panel.tabla.item(f, 9).text() for f in range(panel.tabla.rowCount())}
    assert valores["lun 17-08-2026"] == formatear_moneda(2000)
    assert valores["jue 17-09-2026"] == ""



def test_spin_horario_se_muestra_como_reloj(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)

    panel_r = pantalla.panel_regulares
    panel_r.spin_desde.setValue(9)
    assert panel_r.spin_desde.textFromValue(9) == "9:00"

    panel_a = pantalla.panel_aisladas
    panel_a.spin_desde.setValue(14.5)
    assert panel_a.spin_desde.textFromValue(14.5) == "14:30"
    assert panel_a.spin_desde.valueFromText("14:30") == 14.5


def test_campos_de_fecha_usan_formato_dd_mm_yyyy(qtbot, conn):
    """"Vigencia desde"/"Vigencia hasta" (Regulares) pasan al mismo
    formato con día de la semana abreviado que ya tenía "Fecha" en
    Reservas aisladas — pedido explícito de la clienta ("que se
    comporte igual"). "Fecha que falta" (`campo_fecha_ausencia`, del
    bloque de reubicación en Aisladas) no fue parte de este pedido y
    sigue con el formato de siempre."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)

    panel_r = pantalla.panel_regulares
    assert panel_r.campo_vigencia_inicio.displayFormat() == "ddd dd-MM-yyyy"
    assert panel_r.campo_vigencia_fin.displayFormat() == "ddd dd-MM-yyyy"
    assert panel_r.campo_vigencia_inicio.calendarPopup() is True

    panel_a = pantalla.panel_aisladas
    assert panel_a.campo_fecha.displayFormat() == "ddd dd-MM-yyyy"
    assert panel_a.campo_fecha.calendarPopup() is True
    assert panel_a.campo_fecha_ausencia.displayFormat() == "dd-MM-yyyy"


def test_grilla_preview_no_tiene_scroll_interno_al_elegir_profesional(qtbot, conn):
    """Hallazgo: la grilla se veía cortada con scrollbar interno al elegir
    profesional. El alto mínimo de la tabla, calculado con la suma exacta
    de sus filas, tiene que alcanzar para mostrarla entera."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))

    tabla = panel.grilla.tabla
    assert tabla.rowCount() > 0
    alto_filas = sum(tabla.rowHeight(f) for f in range(tabla.rowCount()))
    assert tabla.minimumHeight() >= alto_filas


def test_tablas_de_abajo_muestran_tratamiento_nombre_apellido_y_columna_ancha(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, Tratamiento="Lic.", NombrePila="Virginia")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)

    tabla_r = pantalla.panel_regulares.tabla
    assert tabla_r.item(0, 0).text() == "Lic. Virginia Gómez"
    assert tabla_r.columnWidth(0) >= 180
    assert tabla_r.item(0, 6).text() == "9:00 a 10:00"

    tabla_a = pantalla.panel_aisladas.tabla
    assert tabla_a.item(0, 0).text() == "Lic. Virginia Gómez"
    assert tabla_a.columnWidth(0) >= 180
    # "hs" al final — pedido puntual de esta tabla, cierre de esta solapa.
    assert tabla_a.item(0, 7).text() == "9:00 a 10:00hs"


def test_reubicacion_ofrece_horario_regular_y_registra_ausencia(qtbot, conn):
    """Al marcar "Es reubicación" en Aisladas, el formulario tiene que
    ofrecer elegir cuál de los horarios regulares del profesional no va a
    usar esta vez, y al confirmar dejarlo registrado como Ausencia de ese
    consultorio en la fecha indicada (así queda libre para otro
    profesional, sin tocar la reserva regular)."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=2)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.combo_consultorio.setCurrentIndex(panel.combo_consultorio.findData(otro_consultorio))
    panel.campo_fecha.setDate(QDate(2026, 8, 22))  # sábado: no choca con el regular del lunes

    panel.casilla_reubicacion.setChecked(True)
    assert panel.contenedor_reubicacion.isHidden() is False
    indice = panel.combo_horario_no_usado.findData(id_consultorio)
    assert indice > 0  # existe una opción con el consultorio de la reserva regular
    panel.combo_horario_no_usado.setCurrentIndex(indice)
    panel.campo_fecha_ausencia.setDate(QDate(2026, 8, 24))  # el lunes siguiente que se va a saltear

    panel._crear()

    ausencia = conn.execute("SELECT * FROM Ausencia WHERE IdProfesional = ?", (id_profesional,)).fetchone()
    assert ausencia is not None
    assert ausencia["IdConsultorio"] == id_consultorio
    assert ausencia["FechaDesde"] == "2026-08-24"
    assert ausencia["FechaHasta"] == "2026-08-24"
    assert ausencia["Motivo"] == "Reubicación"
    reserva_aislada = conn.execute(
        "SELECT IdReservaAislada FROM ReservaAislada WHERE IdConsultorio = ?", (otro_consultorio,)
    ).fetchone()
    assert ausencia["IdReservaAislada"] == reserva_aislada["IdReservaAislada"]

    # el formulario queda en blanco y el cuadro de reubicación oculto de nuevo
    assert panel.casilla_reubicacion.isChecked() is False
    assert panel.contenedor_reubicacion.isHidden() is True


def test_reubicacion_sin_elegir_horario_no_crea_ausencia(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.casilla_reubicacion.setChecked(True)  # "Sin especificar" queda seleccionado por defecto

    panel._crear()

    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 0


def test_regulares_ya_no_tiene_casilla_de_excepcion(qtbot, conn):
    """"Es excepción" se sacó del formulario de Regulares: lo que
    pretendía cubrir ahora se maneja con "Es reubicación" en Aisladas."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert not hasattr(pantalla.panel_regulares, "casilla_excepcion")


def test_dia_de_la_semana_en_tabla_de_aisladas(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=9, HoraFin=10,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    assert panel.tabla.horizontalHeaderItem(5).text() == "Día"
    assert panel.tabla.item(0, 5).text() == "Martes"
    # "ddd dd-MM-yyyy" (ej. "mar 18-08-2026") — pedido puntual de esta
    # tabla, cierre de esta solapa (ver `_fmt_fecha_dia_abrev`).
    assert panel.tabla.item(0, 6).text() == "mar 18-08-2026"


def test_modificar_reserva_aislada_edita_la_fila_existente_sin_cancelarla(qtbot, conn, monkeypatch):
    """Punto #9.1.4 (homólogo de Reservas regulares): "Modificar
    reserva" edita la fila EXISTENTE a través de un cuadro de diálogo —
    sigue Confirmada, no pasa por cancelar+precargar el formulario."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_fecha.setDate(QDate(2026, 8, 18))
    panel.spin_desde.setValue(9)
    panel.spin_hasta.setValue(10)
    panel._crear()

    panel.tabla.selectRow(0)
    _mockear_dialogo_modificar_aislada(monkeypatch, hora_inicio=9, hora_fin=11, aplica_recargo=True)
    panel._modificar_seleccionada()

    fila = conn.execute("SELECT Estado, HoraFin, AplicaRecargo FROM ReservaAislada").fetchone()
    assert fila["Estado"] == "Confirmada"
    assert fila["HoraFin"] == 11
    assert bool(fila["AplicaRecargo"]) is True
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1


def test_modificar_reserva_aislada_sin_fila_avisa(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas._modificar_seleccionada()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 0


def test_modificar_reserva_aislada_cancelada_por_el_usuario_no_cambia_nada(qtbot, conn, monkeypatch):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(1)
    panel._crear()

    panel.tabla.selectRow(0)
    _mockear_dialogo_modificar_aislada(monkeypatch, aceptar=False)
    panel._modificar_seleccionada()

    fila = conn.execute("SELECT HoraFin, Estado FROM ReservaAislada").fetchone()
    assert fila["HoraFin"] == 10
    assert fila["Estado"] == "Confirmada"


def test_modificar_reserva_aislada_al_confirmar_regenera_mensaje_al_portapapeles(qtbot, conn, monkeypatch):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_fecha.setDate(QDate(2026, 8, 18))
    panel._crear()

    copiado = _monkeypatch_clipboard(monkeypatch)
    panel.tabla.selectRow(0)
    _mockear_dialogo_modificar_aislada(monkeypatch, hora_inicio=9, hora_fin=12, aplica_recargo=False)
    panel._modificar_seleccionada()

    assert len(copiado) == 1
    assert "DETALLE RESERVA" in copiado[-1]


def test_columna_reubicacion_en_tabla_de_aisladas(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-18",
        HoraInicio=9, HoraFin=10, EsReubicacion=1,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-19",
        HoraInicio=9, HoraFin=10, EsReubicacion=0,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    assert panel.tabla.horizontalHeaderItem(8).text() == "Reubicación"
    assert panel.tabla.horizontalHeaderItem(9).text() == "Valor"
    valores = {panel.tabla.item(f, 6).text(): panel.tabla.item(f, 8).text() for f in range(panel.tabla.rowCount())}
    assert valores["mar 18-08-2026"] == "Sí"
    assert valores["mié 19-08-2026"] == "No"


def test_columna_periodo_imputado_en_tabla_de_aisladas(qtbot, conn):
    """"En la tabla agregar el campo 'Período imputado'"."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    assert panel.tabla.horizontalHeaderItem(10).text() == "Período imputado"
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_fecha.setDate(QDate(2026, 8, 18))
    # Categoría R arranca en "Período siguiente" por default
    # (`_al_cambiar_profesional`) — se fuerza a "actual" para que el
    # valor esperado sea el mismo mes de la fecha, sin ambigüedad.
    panel.combo_periodo_imputar.setCurrentIndex(panel.combo_periodo_imputar.findData("actual"))
    panel._crear()
    assert panel.tabla.item(0, 10).text() == "2026-08"


def test_botones_modificar_y_cancelar_aislada_deshabilitados_sin_seleccion(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    assert panel.boton_modificar.isEnabled() is False
    assert panel.boton_cancelar.isEnabled() is False

    panel.combo_profesional.setCurrentIndex(1)
    panel._crear()
    panel.tabla.selectRow(0)
    assert panel.boton_modificar.isEnabled() is True
    assert panel.boton_cancelar.isEnabled() is True


def test_foco_de_aisladas_no_saltea_periodo_a_imputar_para_categoria_r(qtbot, conn):
    """Pedido explícito de la clienta: "si elijo un profesional
    categoría R el foco desde el selector del profesional pasa al
    'Período a imputar', no lo saltea"."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(1)  # el único profesional, categoría R
    assert panel.combo_periodo_imputar.isEnabled() is True
    orden = panel._foco._orden
    assert panel.combo_profesional in orden
    assert panel.combo_periodo_imputar in orden
    indice_profesional = orden.index(panel.combo_profesional)
    assert orden[indice_profesional + 1] is panel.combo_periodo_imputar


def _id_localidad(conn, nombre: str) -> int:
    fila = conn.execute("SELECT IdLocalidad FROM Localidad WHERE Localidad = ?", (nombre,)).fetchone()
    return fila["IdLocalidad"] if fila else obtener_repositorio(conn, "Localidad").crear(Localidad=nombre)


def test_campo_profesional_de_la_grilla_usa_el_mismo_formato(qtbot, conn):
    from app.gui.widgets.grilla_operativa import GrillaOperativaWidget

    id_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 1", IdLocalidad=_id_localidad(conn, "Ramos Mejía")
    )
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    id_virginia = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lo Veci", NombrePila="Virginia", Tratamiento="Lic.", IdCodigo="R1",
    )
    conn.commit()

    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    indice = widget.campo_profesional.findData(id_virginia)
    assert widget.campo_profesional.itemText(indice) == "R1 - Lic. Virginia Lo Veci"


def _preparar_dos_localidades(conn):
    """Dos localidades, cada una con un edificio y un consultorio —
    para probar el filtro de Localidad y el formato "Localidad -
    Edificio - Unidad - Consultorio" de la columna Consultorio."""
    id_edificio_1 = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 1", IdLocalidad=_id_localidad(conn, "Ramos Mejía")
    )
    id_unidad_1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_1, Departamento='7mo "L"')
    id_consultorio_1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_1, NumeroConsultorio=1)

    id_edificio_2 = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Haedo Centro", IdLocalidad=_id_localidad(conn, "Haedo")
    )
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_2, Departamento="PB")
    id_consultorio_2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1)

    id_profesional = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Gómez", IdCodigo="R1",
    )
    conn.commit()
    return id_edificio_1, id_consultorio_1, id_edificio_2, id_consultorio_2, id_profesional


def test_combo_localidad_filtra_el_combo_edificio_en_ambas_solapas(qtbot, conn):
    id_edificio_1, _, id_edificio_2, _, _ = _preparar_dos_localidades(conn)

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    # Ambas solapas agregan un placeholder "Seleccionar…" cuando hay más
    # de una localidad (fuerza la elección).
    assert pantalla.panel_regulares.combo_localidad.count() == 3
    assert pantalla.panel_aisladas.combo_localidad.count() == 3

    for panel in (pantalla.panel_regulares, pantalla.panel_aisladas):
        indice = panel.combo_localidad.findData(_id_localidad(conn, "Haedo"))
        panel.combo_localidad.setCurrentIndex(indice)
        assert panel.combo_edificio.count() == 1
        assert panel.combo_edificio.currentData() == id_edificio_2

        indice = panel.combo_localidad.findData(_id_localidad(conn, "Ramos Mejía"))
        panel.combo_localidad.setCurrentIndex(indice)
        assert panel.combo_edificio.count() == 1
        assert panel.combo_edificio.currentData() == id_edificio_1


def test_tabla_regulares_desglosa_localidad_edificio_unidad_consultorio(qtbot, conn):
    """A diferencia de Aisladas (que sigue usando `_texto_consultorio` y
    omite Localidad/Edificio cuando hay uno solo), la tabla de Regulares
    siempre muestra las 4 columnas por separado, sin omitir nada aunque
    solo haya una localidad y un edificio."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.panel_regulares.tabla
    assert [tabla.horizontalHeaderItem(i).text() for i in range(1, 5)] == [
        "Localidad", "Edificio", "Unidad", "Consultorio",
    ]
    assert tabla.item(0, 1).text() == "(Sin localidad)"
    assert tabla.item(0, 2).text() == "Torre Norte"
    assert tabla.item(0, 3).text() == "1A"
    assert tabla.item(0, 4).text() == "1"


def test_tabla_regulares_desglosa_con_varias_localidades(qtbot, conn):
    id_edificio_1, id_consultorio_1, id_edificio_2, id_consultorio_2, id_profesional = _preparar_dos_localidades(conn)
    repo = obtener_repositorio(conn, "ReservaRegular")
    repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio_1, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio_2, DiaSemana="Martes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.panel_regulares.tabla
    filas = {
        (tabla.item(f, 1).text(), tabla.item(f, 2).text(), tabla.item(f, 3).text(), tabla.item(f, 4).text())
        for f in range(tabla.rowCount())
    }
    assert filas == {
        ("Ramos Mejía", "Ramos 1", '7mo "L"', "1"),
        ("Haedo", "Haedo Centro", "PB", "1"),
    }


def test_tabla_regulares_sin_profesional_muestra_solo_vigentes_de_todos(qtbot, conn):
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_vigente = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_finalizado = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ex Profesional")
    repo = obtener_repositorio(conn, "ReservaRegular")
    repo.crear(
        IdProfesional=id_vigente, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    repo.crear(
        IdProfesional=id_finalizado, IdConsultorio=id_consultorio, DiaSemana="Martes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01", VigenciaFin="2020-06-30",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(0)  # placeholder: sin profesional elegido
    dias = {panel.tabla.item(f, 5).text() for f in range(panel.tabla.rowCount())}
    assert dias == {"Lunes"}  # la de Martes ya terminó en 2020 -> no aparece


def test_tabla_regulares_con_profesional_muestra_toda_su_historia(qtbot, conn):
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    repo = obtener_repositorio(conn, "ReservaRegular")
    repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Martes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01", VigenciaFin="2020-06-30",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    dias = {panel.tabla.item(f, 5).text() for f in range(panel.tabla.rowCount())}
    assert dias == {"Lunes", "Martes"}  # incluye la ya finalizada, para poder revisar su historia


def test_tabla_regulares_orden_por_defecto_categoria_numero_dia_hora(qtbot, conn):
    """Orden por defecto: categoría en el orden fijo B, R, E (no
    alfabético); dentro de la misma categoría, por número de profesional
    (numérico: "R2" antes que "R10", no alfabético); luego día de la
    semana y hora de inicio del bloque."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Norte")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    repo_prof = obtener_repositorio(conn, "Profesional")
    id_e1 = repo_prof.crear(CategoriaProfesional="E", Apellido="Equipo", IdCodigo="E1")
    id_r10 = repo_prof.crear(CategoriaProfesional="R", Apellido="Regular Diez", IdCodigo="R10")
    id_r2 = repo_prof.crear(CategoriaProfesional="R", Apellido="Regular Dos", IdCodigo="R2")
    id_b1 = repo_prof.crear(CategoriaProfesional="B", Apellido="Bono", IdCodigo="B1")
    repo = obtener_repositorio(conn, "ReservaRegular")
    for id_prof in (id_e1, id_r10, id_r2, id_b1):
        repo.crear(
            IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
            HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
        )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    codigos = [panel.tabla.item(f, 0).text().split(" - ")[0] for f in range(panel.tabla.rowCount())]
    assert codigos == ["B1", "R2", "R10", "E1"]


def test_tabla_aisladas_sin_profesional_muestra_todas_de_todos(qtbot, conn):
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional_1 = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    repo = obtener_repositorio(conn, "ReservaAislada")
    repo.crear(IdProfesional=id_profesional_1, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=9, HoraFin=10)
    repo.crear(IdProfesional=id_profesional_2, IdConsultorio=id_consultorio, Fecha="2026-08-19", HoraInicio=9, HoraFin=10)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(0)  # placeholder: sin profesional elegido
    assert panel.tabla.rowCount() == 2


def test_tabla_aisladas_con_profesional_acota_a_sus_reservas(qtbot, conn):
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional_1 = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    repo = obtener_repositorio(conn, "ReservaAislada")
    repo.crear(IdProfesional=id_profesional_1, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=9, HoraFin=10)
    repo.crear(IdProfesional=id_profesional_2, IdConsultorio=id_consultorio, Fecha="2026-08-19", HoraInicio=9, HoraFin=10)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional_1))
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 6).text() == "mar 18-08-2026"


def test_tabla_aisladas_todos_los_profesionales_excluye_extraordinarias_y_ordena_por_fecha_hora_codigo(qtbot, conn):
    """Pedido explícito de la clienta: con "Todos los profesionales"
    elegido, la tabla de abajo muestra solo aisladas comunes (las
    extraordinarias quedan afuera, tienen su propia solapa) y ordena
    primero por fecha, luego por hora de inicio, y recién después por
    código de profesional — sin agrupar por categoría."""
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    repo_prof = obtener_repositorio(conn, "Profesional")
    id_a1 = repo_prof.crear(CategoriaProfesional="A", Apellido="Ajeno", IdCodigo="A1")
    id_r10 = repo_prof.crear(CategoriaProfesional="R", Apellido="Regular Diez", IdCodigo="R10")
    id_r2 = repo_prof.crear(CategoriaProfesional="R", Apellido="Regular Dos", IdCodigo="R2")
    repo = obtener_repositorio(conn, "ReservaAislada")
    # Mismo día y hora para R10/A1 — desempata por código (número natural,
    # ignorando la letra: A1 < R10); R2 un día después, siempre al final.
    repo.crear(IdProfesional=id_a1, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10)
    repo.crear(IdProfesional=id_r10, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=14, HoraFin=15)
    repo.crear(IdProfesional=id_r2, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=9, HoraFin=10)
    # Una extraordinaria del mismo profesional/fecha más temprana que
    # todas — si se coló acá, aparecería primera.
    repo.crear(
        IdProfesional=id_a1, IdConsultorio=id_consultorio, Fecha="2026-08-10", HoraInicio=9, HoraFin=10,
        EsExtraordinaria=1, ItemExtraordinario="Taller", MontoExtraordinario=1000,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    assert panel.tabla.rowCount() == 3
    codigos = [panel.tabla.item(f, 0).text().split(" - ")[0] for f in range(panel.tabla.rowCount())]
    assert codigos == ["A1", "R10", "R2"]


def test_combo_profesional_arranca_en_blanco_en_ambas_solapas(qtbot, conn):
    """El combo de profesional ya no se auto-completa con el primero de
    la lista al abrir la pantalla: tiene que arrancar en el placeholder,
    para que el cuadro de abajo muestre "todos los profesionales" hasta
    que el operador elija uno."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_regulares.combo_profesional.currentIndex() == 0
    assert pantalla.panel_regulares.combo_profesional.currentData() is None
    assert pantalla.panel_aisladas.combo_profesional.currentIndex() == 0
    assert pantalla.panel_aisladas.combo_profesional.currentData() is None


def test_panel_aisladas_recibe_foco_en_profesional_al_mostrarse(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    pantalla.pestanas.setCurrentWidget(pantalla.panel_aisladas)
    qtbot.waitUntil(lambda: pantalla.panel_aisladas.combo_profesional.hasFocus())


def test_tabla_aisladas_click_en_columna_ordena_y_alterna_sentido(qtbot, conn):
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    repo = obtener_repositorio(conn, "ReservaAislada")
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-20", HoraInicio=9, HoraFin=10)
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    assert panel.tabla.rowCount() == 2

    panel.tabla.horizontalHeader().sectionClicked.emit(6)  # "Fecha" ascendente
    fechas_asc = [panel.tabla.item(f, 6).text() for f in range(panel.tabla.rowCount())]
    assert fechas_asc == ["lun 17-08-2026", "jue 20-08-2026"]

    panel.tabla.horizontalHeader().sectionClicked.emit(6)  # de nuevo -> descendente
    fechas_desc = [panel.tabla.item(f, 6).text() for f in range(panel.tabla.rowCount())]
    assert fechas_desc == ["jue 20-08-2026", "lun 17-08-2026"]


def test_crear_reserva_aislada_muestra_vista_previa_y_cancelar_no_borra_el_formulario(qtbot, conn, monkeypatch):
    """Pedido explícito de la clienta ("EN GENERAL"), mismo criterio que
    Reservas regulares."""
    _preparar(conn)
    textos: list[str] = []

    def _responder(*args, **kwargs):
        titulo, texto = args[1], args[2]
        textos.append(texto)
        return QMessageBox.StandardButton.No if titulo == "Crear reserva aislada" else QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_responder))
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(1)

    panel._crear()

    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 0
    assert any("Profesional:" in t and "Fecha:" in t for t in textos)
    assert panel.combo_profesional.currentIndex() == 1


def test_crear_reserva_aislada_sin_elegir_consultorio_avisa_y_no_crea(qtbot, conn):
    """Con más de una localidad y ninguna elegida todavía, "Crear reserva
    aislada" no puede completar el alta sin explotar — avisa y no hace
    nada, en vez de intentar guardar con IdConsultorio en blanco."""
    _preparar_dos_localidades(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(1)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 0


def test_crear_reserva_aislada_eligiendo_localidad_y_edificio_persiste(qtbot, conn):
    id_edificio_1, id_consultorio_1, _, _, id_profesional = _preparar_dos_localidades(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.combo_localidad.setCurrentIndex(panel.combo_localidad.findData(_id_localidad(conn, "Ramos Mejía")))
    panel.combo_edificio.setCurrentIndex(panel.combo_edificio.findData(id_edificio_1))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1
    assert conn.execute("SELECT IdConsultorio FROM ReservaAislada").fetchone()["IdConsultorio"] == id_consultorio_1


def test_grilla_preview_aisladas_filtro_exclusivo_no_muestra_otros_profesionales(qtbot, conn):
    """Con R2 elegido, la vista previa solo muestra sus propias celdas —
    aunque otro profesional (A1) tenga algo reservado el mismo día en la
    misma unidad, a otra hora."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Norte")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    repo_prof = obtener_repositorio(conn, "Profesional")
    id_r2 = repo_prof.crear(CategoriaProfesional="R", Apellido="Lo Veci", IdCodigo="R2")
    id_a1 = repo_prof.crear(CategoriaProfesional="A", Apellido="Ajeno", IdCodigo="A1")
    repo = obtener_repositorio(conn, "ReservaAislada")
    repo.crear(IdProfesional=id_r2, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10)
    repo.crear(IdProfesional=id_a1, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=14, HoraFin=15)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-17' WHERE IdConfiguracion = 1"
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_r2))

    codigos = {c.codigo for c in panel.grilla._resultado.values() if c.codigo}
    assert codigos == {"R2"}


def test_grillas_de_reservas_dejan_fijas_columnas_y_encabezado(qtbot, conn):
    """Pedido explícito de la clienta, extendido desde Oferta de
    consultorios a toda pantalla con esta grilla compartida: Tipo de
    bloque/Horario y las filas de encabezado quedan siempre visibles al
    escrolear, en las dos solapas — el comportamiento del mecanismo en
    sí (contenido duplicado, sincronización de scroll, geometría) queda
    cubierto en `test_gui_grilla_operativa.py`."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_regulares, pantalla.panel_aisladas):
        assert panel.grilla._filas_columnas_fijas is True


def test_grillas_de_reservas_reservan_alto_para_el_scroll_horizontal(qtbot, conn):
    """Pedido explícito de la clienta ("que solo aparezca la barra que
    se necesite, sin que tape nada"), extendido a todo el sistema: sin
    `reservar_alto_scroll_horizontal()`, la barra de scroll horizontal
    — cuando la grilla la necesita, por muchos consultorios — se come
    alto del viewport sin que el tope mínimo lo contemple, tapando la
    última fila y pudiendo disparar un scroll vertical de más,
    innecesario. El comportamiento del mecanismo en sí (cuánto alto
    suma, cómo se mide la barra) ya está cubierto en
    `test_gui_grilla_operativa.py` — acá solo se confirma que las dos
    solapas de Reservas lo prenden, mismo criterio que el test de
    arriba para `activar_filas_y_columnas_fijas()`."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_regulares, pantalla.panel_aisladas):
        assert panel.grilla._reservar_alto_scroll_horizontal is True


def test_tab_en_filtro_de_unidad_de_la_grilla_no_salta_el_filtro_de_dia(qtbot, conn):
    """Bug reportado por la clienta: Tab desde "Filtro de unidad" caía
    directo en "Profesional", salteando los checks de "Filtro de día de
    la semana" — causado por `agrupar_dias_en_pares()`, que reparenta
    los checks después de construido el resto del panel y los deja al
    final de la cadena nativa de Qt. Se corrige con una cadena de foco
    propia para este panel (`GrillaOperativaWidget.widgets_filtro_para_
    foco`), separada del formulario de alta."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    for indice, panel in enumerate((pantalla.panel_regulares, pantalla.panel_aisladas)):
        pantalla.pestanas.setCurrentIndex(indice)  # solo la solapa activa tiene widgets visibles
        boton_filtro_unidad = panel.grilla._filtro_unidad.foco_widget()
        boton_filtro_unidad.setFocus()
        qtbot.waitUntil(lambda: boton_filtro_unidad.hasFocus())
        qtbot.keyClick(boton_filtro_unidad, Qt.Key.Key_Tab)
        siguiente = QApplication.focusWidget()
        assert siguiente in panel.grilla._checks_dia.values()


def test_etiquetas_horas_regulares_y_aisladas_tienen_wordwrap(qtbot, conn):
    """Pedido de la clienta: "Cantidad de horas regulares semanales" se
    veía cortado — con wordWrap pasa a una segunda línea en vez de
    desbordar la columna."""
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_regulares.etiqueta_horas_semanales.wordWrap() is True
    assert pantalla.panel_regulares.etiqueta_descuento.wordWrap() is True


# ------------------------------------------------------------ reserva extraordinaria

def _preparar_categoria_a(conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('A', 'Paz')")
    conn.commit()


def test_solapa_reserva_extraordinaria_existe_con_combo_a_b_r_e(qtbot, conn):
    """Ampliado a las cuatro categorías imputables (A/B/R/E) — pedido de
    la clienta: B participa solo para marcar ocupación, E puede imputar
    igual que R. Orden: jerarquía global B/R/A/E/X/C (mismo criterio
    `_opciones_profesional_con_categoria`, ya no la excepción "A antes
    que R" que regía cuando el combo solo admitía esas dos)."""
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, IdCodigo, Apellido) VALUES ('R', 'R5', 'Lo Veci')"
    )
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, IdCodigo, Apellido) VALUES ('A', 'A20', 'Paz')"
    )
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, IdCodigo, Apellido) VALUES ('A', 'A3', 'Gómez')"
    )
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, IdCodigo, Apellido) VALUES ('B', 'B1', 'Bono')"
    )
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, IdCodigo, Apellido) VALUES ('E', 'E1', 'Equipo')"
    )
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('X', 'Inactivo')")
    conn.commit()
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.pestanas.tabText(2) == "Reservas extraordinarias"
    panel = pantalla.panel_extraordinaria
    assert panel.objectName() == "panelSolapa"
    # "Todos los profesionales" + B1, R5, A3, A20, E1 (jerarquía B/R/A/E) — el X queda afuera.
    assert panel.combo_profesional.count() == 6
    assert panel.combo_profesional.itemText(1) == "B1 - Bono"
    assert panel.combo_profesional.itemText(2) == "R5 - Lo Veci"
    assert panel.combo_profesional.itemText(3) == "A3 - Gómez"
    assert panel.combo_profesional.itemText(4) == "A20 - Paz"
    assert panel.combo_profesional.itemText(5) == "E1 - Equipo"


def test_reserva_extraordinaria_etiqueta_profesional_sin_mencionar_categoria(qtbot, conn):
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    etiquetas = [
        w.text() for w in panel.findChildren(QLabel) if hasattr(w, "text")
    ]
    assert "Profesional" in etiquetas
    assert "Profesional (categoría A)" not in etiquetas


def test_periodo_a_imputar_editable_solo_para_r_y_e(qtbot, conn):
    """"Período a imputar" queda siempre VISIBLE (pedido de la clienta:
    "para los profesionales categoría A y B el período es el actual y
    no se puede editar, para los R y E por defecto es el período
    próximo pero se puede editar") — lo que cambia es si está
    habilitado y cuál es el default."""
    _preparar_categoria_a(conn)
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, IdCodigo, Apellido) VALUES ('R', 'R1', 'Lo Veci')"
    )
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, IdCodigo, Apellido) VALUES ('E', 'E1', 'Equipo')"
    )
    conn.commit()
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria

    # Sin selección (arranca en "Todos los profesionales"): deshabilitado, "actual".
    assert panel.combo_periodo_imputar.isEnabled() is False
    assert panel.combo_periodo_imputar.currentData() == "actual"

    # Categoría A: deshabilitado, "actual".
    indice_a = panel.combo_profesional.findText("Paz")
    panel.combo_profesional.setCurrentIndex(indice_a)
    assert panel.combo_periodo_imputar.isEnabled() is False
    assert panel.combo_periodo_imputar.currentData() == "actual"

    # Categoría R: habilitado, default "siguiente".
    indice_r = panel.combo_profesional.findText("R1 - Lo Veci")
    panel.combo_profesional.setCurrentIndex(indice_r)
    assert panel.combo_periodo_imputar.isEnabled() is True
    assert panel.combo_periodo_imputar.currentData() == "siguiente"

    # Categoría E: habilitado, default "siguiente" — igual que R.
    indice_e = panel.combo_profesional.findText("E1 - Equipo")
    panel.combo_profesional.setCurrentIndex(indice_e)
    assert panel.combo_periodo_imputar.isEnabled() is True
    assert panel.combo_periodo_imputar.currentData() == "siguiente"


def test_crear_reserva_extraordinaria_de_un_r_con_periodo_actual_regenera_liquidacion(qtbot, conn):
    """Respuesta de la clienta: "si se imputa al mismo período de la
    liquidación, la rehace y la marca como no enviada"."""
    from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio
    from app.negocio.dias import periodo_actual

    _preparar_categoria_a(conn)
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, IdCodigo, Apellido, SaldoCuentaActual) "
        "VALUES ('R', 'R1', 'Lo Veci', 0)"
    )
    conn.commit()
    id_r = conn.execute("SELECT IdProfesional FROM Profesional WHERE IdCodigo = 'R1'").fetchone()["IdProfesional"]
    periodo = periodo_actual(conn)
    emitir_liquidacion(conn, id_profesional=id_r, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_r, periodo=periodo, enviada=True)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    indice_r = panel.combo_profesional.findText("R1 - Lo Veci")
    panel.combo_profesional.setCurrentIndex(indice_r)
    indice_actual = panel.combo_periodo_imputar.findData("actual")
    panel.combo_periodo_imputar.setCurrentIndex(indice_actual)
    panel.campo_item.setText("Ajuste puntual")
    panel.spin_monto.setValue(3000)
    panel._crear()

    from app.repositorio.registro import obtener_repositorio as repo
    emisiones = repo(conn, "LiquidacionEmitida").listar(IdProfesional=id_r, Periodo=periodo)
    assert len(emisiones) == 2
    ultima = max(emisiones, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] == "Regenerada no enviada"


def test_crear_reserva_extraordinaria_de_un_r_con_periodo_siguiente_no_toca_liquidacion(qtbot, conn):
    """Respuesta de la clienta: "si la imputa para el período siguiente,
    no toca la liquidación del mes"."""
    from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio
    from app.negocio.dias import periodo_actual
    from app.repositorio.registro import obtener_repositorio as repo

    _preparar_categoria_a(conn)
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, IdCodigo, Apellido, SaldoCuentaActual) "
        "VALUES ('R', 'R1', 'Lo Veci', 0)"
    )
    conn.commit()
    id_r = conn.execute("SELECT IdProfesional FROM Profesional WHERE IdCodigo = 'R1'").fetchone()["IdProfesional"]
    periodo = periodo_actual(conn)
    emitir_liquidacion(conn, id_profesional=id_r, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_r, periodo=periodo, enviada=True)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    indice_r = panel.combo_profesional.findText("R1 - Lo Veci")
    panel.combo_profesional.setCurrentIndex(indice_r)
    indice_siguiente = panel.combo_periodo_imputar.findData("siguiente")
    panel.combo_periodo_imputar.setCurrentIndex(indice_siguiente)
    panel.campo_item.setText("Ajuste puntual")
    panel.spin_monto.setValue(3000)
    panel._crear()

    emisiones = repo(conn, "LiquidacionEmitida").listar(IdProfesional=id_r, Periodo=periodo)
    assert len(emisiones) == 1
    assert emisiones[0]["EstadoEnvio"] == "Enviada"


def test_crear_reserva_extraordinaria_se_guarda_y_copia_mensaje_al_portapapeles(qtbot, conn, monkeypatch):
    _preparar_categoria_a(conn)
    copiado = _monkeypatch_clipboard(monkeypatch)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Uso del consultorio para un taller puntual")
    panel.spin_monto.setValue(12000)
    panel._crear()

    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 8).text() == "Uso del consultorio para un taller puntual"
    assert "12.000" in panel.tabla.item(0, 9).text()
    reserva = obtener_repositorio(conn, "ReservaAislada").listar()[0]
    assert reserva["EsExtraordinaria"] == 1
    assert len(copiado) == 1
    assert "DETALLE RESERVA" in copiado[0]
    assert "Uso del consultorio para un taller puntual" in copiado[0]


def test_crear_reserva_extraordinaria_muestra_vista_previa_y_cancelar_no_borra_el_formulario(
    qtbot, conn, monkeypatch,
):
    """Pedido explícito de la clienta ("EN GENERAL"), mismo criterio que
    las otras dos solapas — acá además confirma que el ítem/monto
    cargados aparecen en la vista previa."""
    _preparar_categoria_a(conn)
    textos: list[str] = []

    def _responder(*args, **kwargs):
        titulo, texto = args[1], args[2]
        textos.append(texto)
        return (
            QMessageBox.StandardButton.No if titulo == "Crear reserva extraordinaria"
            else QMessageBox.StandardButton.Yes
        )

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_responder))
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller puntual")
    panel.spin_monto.setValue(5000)

    panel._crear()

    assert obtener_repositorio(conn, "ReservaAislada").listar() == []
    assert any("Taller puntual" in t and "5.000" in t for t in textos)
    # El formulario sigue cargado, no se reseteó.
    assert panel.combo_profesional.currentIndex() == 1
    assert panel.campo_item.text() == "Taller puntual"
    assert panel.spin_monto.value() == 5000


def test_crear_reserva_extraordinaria_sin_item_no_crea_nada(qtbot, conn):
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel.combo_profesional.setCurrentIndex(1)
    panel.spin_monto.setValue(12000)
    panel._crear()
    assert obtener_repositorio(conn, "ReservaAislada").listar() == []


def test_crear_reserva_extraordinaria_sin_monto_no_crea_nada(qtbot, conn):
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller puntual")
    panel._crear()
    assert obtener_repositorio(conn, "ReservaAislada").listar() == []


def test_cancelar_reserva_extraordinaria(qtbot, conn):
    """Punto #9.1.6 (homólogo de Reservas aisladas): pide confirmación
    explícita antes de cancelar — este test confía en el default global
    de `_sin_dialogos_modales` (`question` responde "Sí")."""
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller puntual")
    panel.spin_monto.setValue(5000)
    panel._crear()
    assert panel.tabla.rowCount() == 1

    panel.tabla.selectRow(0)
    panel._cancelar()
    assert obtener_repositorio(conn, "ReservaAislada").listar()[0]["Estado"] == "Cancelada"


def test_cancelar_reserva_extraordinaria_declinada_no_cambia_nada(qtbot, conn, monkeypatch):
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller puntual")
    panel.spin_monto.setValue(5000)
    panel._crear()

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    panel.tabla.selectRow(0)
    panel._cancelar()
    assert obtener_repositorio(conn, "ReservaAislada").listar()[0]["Estado"] == "Confirmada"


def test_tecla_delete_en_extraordinaria_cancela_la_reserva(qtbot, conn):
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller puntual")
    panel.spin_monto.setValue(5000)
    panel._crear()
    panel.tabla.selectRow(0)
    qtbot.keyClick(panel.tabla, Qt.Key.Key_Delete)
    assert obtener_repositorio(conn, "ReservaAislada").listar()[0]["Estado"] == "Cancelada"


def test_modificar_reserva_extraordinaria_edita_la_fila_existente_sin_cancelarla(qtbot, conn, monkeypatch):
    """Punto #9.1.4 (homólogo de Reservas regulares/aisladas): ya no
    cancela la fila vieja y precarga el formulario — abre
    `_DialogoModificarReservaAislada` (reusado, ya sabe mostrar ítem/
    monto en vez de recargo cuando `EsExtraordinaria`) y edita la fila
    EXISTENTE, sin tocar su `Estado`."""
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller puntual")
    panel.spin_monto.setValue(5000)
    panel._crear()
    assert panel.tabla.rowCount() == 1

    _mockear_dialogo_modificar_aislada(
        monkeypatch, hora_inicio=9, hora_fin=11, item_extraordinario="Taller corregido", monto_extraordinario=6000,
    )
    panel.tabla.selectRow(0)
    panel._modificar_seleccionada()

    reservas = obtener_repositorio(conn, "ReservaAislada").listar()
    assert len(reservas) == 1
    assert reservas[0]["Estado"] == "Confirmada"
    assert reservas[0]["ItemExtraordinario"] == "Taller corregido"
    assert reservas[0]["MontoExtraordinario"] == 6000
    assert reservas[0]["HoraFin"] == 11


def test_modificar_reserva_extraordinaria_sin_seleccion_avisa(qtbot, conn):
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel._modificar_seleccionada()
    assert obtener_repositorio(conn, "ReservaAislada").listar() == []


def test_modificar_reserva_extraordinaria_cancelada_por_el_usuario_no_cambia_nada(qtbot, conn, monkeypatch):
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller puntual")
    panel.spin_monto.setValue(5000)
    panel._crear()

    _mockear_dialogo_modificar_aislada(monkeypatch, aceptar=False)
    panel.tabla.selectRow(0)
    panel._modificar_seleccionada()

    reservas = obtener_repositorio(conn, "ReservaAislada").listar()
    assert reservas[0]["ItemExtraordinario"] == "Taller puntual"
    assert reservas[0]["MontoExtraordinario"] == 5000


def test_modificar_reserva_extraordinaria_copia_mensaje_de_detalle_al_portapapeles(qtbot, conn, monkeypatch):
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller puntual")
    panel.spin_monto.setValue(5000)
    panel._crear()

    _mockear_dialogo_modificar_aislada(
        monkeypatch, hora_inicio=9, hora_fin=11, item_extraordinario="Taller puntual", monto_extraordinario=5000,
    )
    copiado = _monkeypatch_clipboard(monkeypatch)
    panel.tabla.selectRow(0)
    panel._modificar_seleccionada()
    assert len(copiado) == 1
    assert "DETALLE RESERVA" in copiado[0]


def test_reserva_extraordinaria_se_ve_en_la_tabla_de_reservas_aisladas_con_el_monto_manual(qtbot, conn):
    """Una extraordinaria es una ReservaAislada más — la tabla de
    "Reservas aisladas" la lista cuando se filtra por SU profesional
    puntual (columna "Valor" con el monto manual, no un cálculo de
    hora×tarifa que daría un número distinto al que de verdad se
    cobra). Con "Todos los profesionales" elegido queda afuera — pedido
    explícito de la clienta, ver `test_tabla_aisladas_todos_los_
    profesionales_excluye_extraordinarias_y_ordena_por_fecha_hora_
    codigo`."""
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel_extra = pantalla.panel_extraordinaria
    panel_extra.combo_profesional.setCurrentIndex(1)
    id_profesional = panel_extra.combo_profesional.currentData()
    panel_extra.campo_item.setText("Taller puntual")
    panel_extra.spin_monto.setValue(7500)
    panel_extra._crear()

    panel_aisladas = pantalla.panel_aisladas
    indice = panel_aisladas.combo_profesional.findData(id_profesional)
    panel_aisladas.combo_profesional.setCurrentIndex(indice)
    assert panel_aisladas.tabla.rowCount() == 1
    assert "7.500" in panel_aisladas.tabla.item(0, 9).text()


def test_tabla_extraordinaria_ordena_por_fecha_ascendente_por_defecto(qtbot, conn):
    """Pedido explícito de la clienta: "las reservas tienen que aparecer
    por orden de fecha, lo mas próximo arriba" — antes quedaba al revés
    (la fecha más lejana en el tiempo primero)."""
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    hoy = panel.campo_fecha.date()
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller lejano")
    panel.spin_monto.setValue(1000)
    panel.campo_fecha.setDate(hoy.addDays(20))
    panel._crear()

    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller cercano")
    panel.spin_monto.setValue(2000)
    panel.campo_fecha.setDate(hoy.addDays(5))
    panel._crear()

    assert panel.tabla.rowCount() == 2
    assert panel.tabla.item(0, 8).text() == "Taller cercano"
    assert panel.tabla.item(1, 8).text() == "Taller lejano"


def test_columna_periodo_imputado_en_tabla_de_extraordinaria(qtbot, conn):
    """Mismo criterio que Reservas aisladas: columna "Período imputado"
    (AAAA-MM), al final de la tabla."""
    from app.negocio.dias import periodo_actual, sumar_meses

    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller puntual")
    panel.spin_monto.setValue(5000)
    panel._crear()

    assert panel.tabla.columnCount() == 12
    assert panel.tabla.horizontalHeaderItem(11).text() == "Período imputado"
    assert panel.tabla.item(0, 11).text() == periodo_actual(conn)
    assert panel.tabla.item(0, 11).text() != sumar_meses(periodo_actual(conn), 1)


def test_botones_modificar_y_cancelar_extraordinaria_deshabilitados_sin_seleccion(qtbot, conn):
    _preparar_categoria_a(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_extraordinaria
    assert not panel.boton_modificar.isEnabled()
    assert not panel.boton_cancelar.isEnabled()

    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_item.setText("Taller puntual")
    panel.spin_monto.setValue(5000)
    panel._crear()
    panel.tabla.selectRow(0)
    assert panel.boton_modificar.isEnabled()
    assert panel.boton_cancelar.isEnabled()

    panel.tabla.clearSelection()
    assert not panel.boton_modificar.isEnabled()
    assert not panel.boton_cancelar.isEnabled()


def test_spin_monto_de_reserva_extraordinaria_selecciona_todo_al_enfocar(qtbot):
    """Pedido de la clienta sobre "Monto a cobrar" de Reserva
    extraordinaria, extendido a "todos los cuadros de texto similares
    del sistema": select-all al enfocar, mismo mecanismo que `_SpinMonto`
    de Pagos/`_SpinMoneda` de Configuración general."""
    from app.gui.pantallas.reservas import _SpinMonto

    spin = _SpinMonto()
    spin.setRange(0, 99_999_999)
    spin.setValue(5000)
    qtbot.addWidget(spin)
    spin.show()
    qtbot.waitExposed(spin)
    spin.setFocus()
    qtbot.waitUntil(lambda: spin.hasFocus())
    qtbot.wait(10)
    assert spin.lineEdit().selectedText() == spin.lineEdit().text()
    assert spin.lineEdit().selectedText() != ""


def test_spin_monto_de_reserva_extraordinaria_muestra_formato_moneda(qtbot):
    from app.gui.pantallas.reservas import _SpinMonto

    spin = _SpinMonto()
    spin.setRange(0, 99_999_999)
    spin.setValue(1234.5)
    qtbot.addWidget(spin)
    assert "$" in spin.text()
    assert "1.234" in spin.text()


def test_vigencia_fin_calendario_arranca_hoy_mientras_este_en_sin_fecha(qtbot, conn):
    """Hallazgo real de la clienta (en Licencias, ver `test_gui_novedades.py`
    — mismo mecanismo acá, en Reservas regulares): con "Vigencia hasta" en
    el sentinel "(sin fecha)", el popup del calendario arrancaba en el año
    2000 en vez del mes en curso. `_instalar_calendario_arranca_hoy`
    re-paginea el calendario (sin tocar el valor real del campo) cada vez
    que se muestra, mientras siga en el sentinel. Dispara el evento Show a
    mano (`QApplication.sendEvent`) porque un `.show()` directo sobre el
    `QCalendarWidget` de un `QDateTimeEdit` (pensado para mostrarse solo
    como popup, no así) no siempre llega a entregar el evento nativo."""
    from PySide6.QtGui import QShowEvent

    from app.negocio.dias import fecha_actual

    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    assert panel.campo_vigencia_fin.date() == _FECHA_SIN_DATO

    calendario = panel.campo_vigencia_fin.calendarWidget()
    calendario.setCurrentPage(2000, 1)  # simula que había quedado en la página del sentinel
    QApplication.sendEvent(calendario, QShowEvent())

    hoy = fecha_actual(conn)
    assert calendario.yearShown() == hoy.year
    assert calendario.monthShown() == hoy.month


def test_vigencia_fin_calendario_no_se_repaginea_con_una_fecha_real(qtbot, conn):
    """Con una fecha real cargada (no el sentinel), el filtro no toca la
    página del calendario — solo actúa mientras el campo sigue en
    "(sin fecha)"."""
    from PySide6.QtGui import QShowEvent

    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.campo_vigencia_fin.setDate(QDate(2030, 6, 15))

    calendario = panel.campo_vigencia_fin.calendarWidget()
    calendario.setCurrentPage(2015, 3)
    QApplication.sendEvent(calendario, QShowEvent())

    # el filtro no hace nada (no es el sentinel) — la página queda tal
    # cual estaba antes de mostrar el calendario.
    assert calendario.yearShown() == 2015
    assert calendario.monthShown() == 3
