import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.lista_espera import PantallaListaEspera
from app.gui.widgets.selector_profesional import _ProxyBusquedaSinAcentos
from app.negocio.lista_espera import crear_pedido


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


def _crear_profesional(conn, apellido="Gómez", codigo=None):
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, IdCodigo) VALUES ('R', ?, ?)", (apellido, codigo),
    )
    conn.commit()
    return conn.execute("SELECT IdProfesional FROM Profesional WHERE Apellido = ?", (apellido,)).fetchone()[
        "IdProfesional"
    ]


def _crear_edificio_con_consultorio(conn, nombre="Torre Norte", departamento="1A"):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES (?)", (nombre,))
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio WHERE Nombre = ?", (nombre,)).fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, ?)", (id_edificio, departamento))
    id_unidad = conn.execute(
        "SELECT IdUnidad FROM Unidad WHERE IdEdificio = ? AND Departamento = ?", (id_edificio, departamento)
    ).fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    conn.commit()


def _bloque_lunes():
    return {"dias": ["Lunes"], "horario_desde": 9, "horario_hasta": 12}


def test_combo_profesional_es_buscable_por_codigo_o_nombre(qtbot, conn):
    """Confirmado por la clienta: el selector de profesional buscable
    corre en todos los formularios del sistema, Lista de espera incluida
    — y con el mismo formato canónico "{código} - {tratamiento} {nombre}
    {apellido}" que el resto (antes mostraba "Apellido, Nombre")."""
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, NombrePila, IdCodigo) "
        "VALUES ('R', 'Lo Veci', 'Virginia', 'R1')"
    )
    conn.commit()
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    completador = pantalla.combo_profesional.completer()
    assert isinstance(completador.model(), _ProxyBusquedaSinAcentos)
    assert pantalla.combo_profesional.itemText(0) == "R1 - Virginia Lo Veci"


def test_combo_profesional_incluye_inactivos_y_contactos(qtbot, conn):
    """Confirmado por la clienta: acá se agenda lo que pide CUALQUIER
    profesional, esté activo en el espacio o no — categoría X (inactivo)
    o C (contacto/prospecto) incluidas, no solo R/A."""
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('X', 'Inactivo')")
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('C', 'Prospecto')")
    conn.commit()
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    textos = {pantalla.combo_profesional.itemText(i) for i in range(pantalla.combo_profesional.count())}
    assert "Inactivo" in textos
    assert "Prospecto" in textos


def test_dias_son_checkboxes_horizontales_no_lista(qtbot, conn):
    """Mismo formato horizontal (checkboxes en grilla) que usa Oferta de
    consultorios, en vez de la lista vertical tildable de antes."""
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert set(pantalla._checks_dia.keys()) == {"Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"}
    assert all(check.isChecked() is False for check in pantalla._checks_dia.values())


def test_caracteristicas_de_los_consultorios_tiene_los_checks_esperados(qtbot, conn):
    """Confirmado por la clienta: "Características de los consultorios"
    tiene ventana, camilla, tamaño mínimo, placard y aire acondicionado
    — "Con balcón" no vuelve, quedó descartado. "Sin/Con combinación de
    consultorios" se mudó a un combo en la segunda columna."""
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert not hasattr(pantalla, "casilla_balcon")
    assert not hasattr(pantalla, "casilla_sin_combinar")
    for atributo in ("casilla_ventana", "casilla_camilla", "casilla_tamano", "casilla_placard", "casilla_aire"):
        assert hasattr(pantalla, atributo)


def test_tamano_minimo_es_la_primera_fila_de_caracteristicas(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    assert _y_absoluta(pantalla.casilla_tamano, pantalla) < _y_absoluta(pantalla.casilla_ventana, pantalla)


def test_combo_sin_combinar_arranca_en_sin_combinacion(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.combo_sin_combinar.currentText() == "Sin combinación de consultorios"
    assert pantalla.combo_sin_combinar.currentData() is True
    textos = [pantalla.combo_sin_combinar.itemText(i) for i in range(pantalla.combo_sin_combinar.count())]
    assert textos == ["Sin combinación de consultorios", "Con combinación de consultorios"]


def test_caracteristicas_quedan_de_a_dos_por_linea(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    assert _y_absoluta(pantalla.casilla_ventana, pantalla) == _y_absoluta(pantalla.casilla_camilla, pantalla)
    assert _y_absoluta(pantalla.casilla_placard, pantalla) == _y_absoluta(pantalla.casilla_aire, pantalla)
    assert pantalla.casilla_ventana.x() < pantalla.casilla_camilla.x()
    assert pantalla.casilla_placard.x() < pantalla.casilla_aire.x()


def test_botones_de_bloques_dicen_agregar_bloque_sin_puntos_suspensivos(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    botones = {b.text(): b for b in pantalla.findChildren(QPushButton)}
    assert "Agregar bloque" in botones
    assert "Agregar bloque…" not in botones


def test_botones_secundarios_usan_el_mismo_tamano_que_crear_pedido(qtbot, conn):
    """"Agregar bloque", "Quitar bloque", "Descartar pedido" y "Editar
    pedido" van en celeste suave (botonSecundario) en vez del azul de
    "Crear pedido" (botonPrimario), pero con el mismo padding para
    quedar del mismo tamaño."""
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    botones = {b.text(): b for b in pantalla.findChildren(QPushButton)}
    for texto in ("Agregar bloque", "Quitar bloque", "Descartar pedido", "Editar pedido"):
        assert botones[texto].objectName() == "botonSecundario"
    assert pantalla.boton_crear.objectName() == "botonPrimario"


def test_agregar_quitar_y_crear_pedido_quedan_a_la_misma_altura(qtbot, conn):
    """"Agregar bloque" (primera columna), "Quitar bloque" (segunda) y
    "Crear pedido" (tercera) tienen que alinearse horizontalmente —
    ajustado agrandando el cuadro de bloques y el de comentarios. La
    tolerancia es más ancha que un ajuste a simple vista porque este
    test no aplica la hoja de estilos de la app (negrita en los
    subtítulos, etc. cambian un poco la métrica de fuente real)."""
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    y_agregar = _y_absoluta(pantalla.boton_agregar_bloque, pantalla)
    y_quitar = _y_absoluta(pantalla.boton_quitar_bloque, pantalla)
    y_crear = _y_absoluta(pantalla.boton_crear, pantalla)
    assert abs(y_agregar - y_quitar) <= 10
    assert abs(y_agregar - y_crear) <= 10


def test_tabla_columna_dias_tiene_ancho_minimo(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    crear_pedido(
        conn, id_profesional=id_profesional,
        bloques=[{"dias": ["Lunes", "Martes", "Miércoles", "Jueves"], "horario_desde": 9, "horario_hasta": 12}],
    )
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.columnWidth(2) >= 180


def test_tabla_bloques_le_da_mas_ancho_a_dias_que_a_las_otras_columnas(qtbot, conn):
    """Confirmado por la clienta: "Días" (columna 0) tiene que quedar
    más ancha que Horario/Comb. días/Horas mínimas por si hay varios
    días en un mismo bloque."""
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    ancho_dias = pantalla.tabla_bloques.columnWidth(0)
    for columna in (1, 2, 3):
        assert ancho_dias > pantalla.tabla_bloques.columnWidth(columna)


def test_columna_coincidencia_de_la_tabla_tiene_delegado_propio(qtbot, conn):
    """La columna Coincidencia (índice 8) usa un delegado que ignora el
    resaltado de selección — su color (verde/amarillo/naranja/rojo)
    tiene que seguir el criterio de cobertura, no el naranja de la fila
    seleccionada."""
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.itemDelegateForColumn(8) is not pantalla.tabla.itemDelegate()


def test_jerarquia_de_titulos_del_formulario(qtbot, conn):
    """Jerarquía 1 (título de pantalla): MAYÚSCULA. Jerarquía 2 (nombre
    de la única solapa, "Nuevo pedido"): solapa real de un QTabWidget,
    visible aunque haya una sola (sin tabBarAutoHide). Jerarquía 3
    (subtítulo de un campo puntual, ej. "Profesional"): objectName
    subtituloCampo — pero "Desde"/"Hasta", al lado del spinbox de
    horario en vez de arriba, no cuentan como jerarquía 3."""
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)

    etiquetas_por_texto = {lbl.text(): lbl for lbl in pantalla.findChildren(QLabel)}
    titulo = etiquetas_por_texto["LISTA DE ESPERA"]
    assert titulo.objectName() == "tituloPantalla"

    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert solapas.count() == 1
    assert solapas.tabText(0) == "Nuevo pedido"
    assert solapas.tabBarAutoHide() is False  # se ve siempre, aunque haya una sola solapa

    for texto in (
        "Profesional", "Localidad", "Edificio", "Unidad", "Bloques del pedido",
        "Combinación de bloques y consultorios", "Características de los consultorios", "Comentarios",
        "Cobertura de la coincidencia seleccionada",
    ):
        assert etiquetas_por_texto[texto].objectName() == "subtituloCampo"

    assert etiquetas_por_texto["Desde"].objectName() != "subtituloCampo"
    assert etiquetas_por_texto["Hasta"].objectName() != "subtituloCampo"


def test_agregar_quitar_y_crear_pedido_no_ocupan_todo_el_ancho_de_su_columna(qtbot, conn):
    """A diferencia de antes (donde estiraban a todo el ancho de la
    columna), ahora tienen un ancho fijo e igual entre los tres, y
    claramente menor que el ancho real de la columna una vez mostrada
    la pantalla en una ventana ancha."""
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1850, 1100)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    assert pantalla.boton_agregar_bloque.width() == pantalla.boton_quitar_bloque.width() == pantalla.boton_crear.width()
    assert pantalla.boton_agregar_bloque.width() < pantalla.combo_profesional.width()


def test_tabla_de_pedidos_tiene_alto_maximo_para_ser_escroleable(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.maximumHeight() <= 260


def test_localidad_edificio_unidad_arrancan_en_todas(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre, DomicilioLocalidad) VALUES ('Torre Norte', 'Palermo')")
    conn.execute("INSERT INTO Edificio (Nombre, DomicilioLocalidad) VALUES ('Torre Sur', 'Belgrano')")
    conn.commit()
    id_norte = conn.execute("SELECT IdEdificio FROM Edificio WHERE Nombre = 'Torre Norte'").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_norte,))
    conn.commit()

    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)

    assert pantalla._filtro_localidad._boton.text() == "Todas las localidades"
    assert pantalla._filtro_edificio._boton.text() == "Todos los edificios"
    assert pantalla._filtro_unidad._boton.text() == "Todas las unidades"
    # "Todas" -> ninguna restricción real, así que ids_unidad_seleccionadas
    # devuelve el universo completo de unidades existentes.
    assert len(pantalla._ids_unidad_seleccionadas()) == 1


def test_elegir_un_edificio_puntual_acota_las_unidades_de_la_busqueda(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Sur')")
    conn.commit()
    id_norte = conn.execute("SELECT IdEdificio FROM Edificio WHERE Nombre = 'Torre Norte'").fetchone()["IdEdificio"]
    id_sur = conn.execute("SELECT IdEdificio FROM Edificio WHERE Nombre = 'Torre Sur'").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_norte,))
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '2A')", (id_sur,))
    conn.commit()
    id_unidad_norte = conn.execute("SELECT IdUnidad FROM Unidad WHERE Departamento = '1A'").fetchone()["IdUnidad"]

    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)

    pantalla.lista_edificio.clearSelection()
    for i in range(pantalla.lista_edificio.count()):
        if pantalla.lista_edificio.item(i).text() == "Torre Norte":
            pantalla.lista_edificio.item(i).setSelected(True)
            break

    assert pantalla._ids_unidad_seleccionadas() == [id_unidad_norte]


def test_horario_muestra_formato_hs(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.spin_desde.setValue(9)
    assert pantalla.spin_desde.text() == "9:00hs"
    pantalla.spin_hasta.setValue(12.5)
    assert pantalla.spin_hasta.text() == "12:30hs"


def _y_absoluta(widget, pantalla) -> int:
    """`.y()` es relativo al padre inmediato — no comparable entre
    widgets anidados en contenedores distintos. Mapear al widget raíz
    de la pantalla da una posición vertical comparable entre todos."""
    return widget.mapTo(pantalla, QPoint(0, 0)).y()


def test_combinacion_de_dias_y_horarios_va_debajo_de_los_checks_de_dias(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    assert _y_absoluta(pantalla._checks_dia["Lunes"], pantalla) < _y_absoluta(pantalla.combo_tipo, pantalla)


def test_checks_de_dias_van_debajo_de_todas_las_unidades_sin_titulo_propio(qtbot, conn):
    """Se saca el título "Combinación de días y horarios" y los checks de
    días pasan a ir directo debajo del filtro de Unidad, seguidos del
    selector "Alcanza con un día (O)", el horario, "Cantidad de horas..."
    y "Agregar bloque…" — todo en la misma columna, un paso abajo del
    otro."""
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    etiquetas = {lbl.text() for lbl in pantalla.findChildren(QLabel)}
    assert "Combinación de días y horarios" not in etiquetas
    assert "Días" not in etiquetas
    assert _y_absoluta(pantalla._filtro_unidad, pantalla) < _y_absoluta(pantalla._checks_dia["Lunes"], pantalla)
    assert _y_absoluta(pantalla._checks_dia["Lunes"], pantalla) < _y_absoluta(pantalla.combo_tipo, pantalla)
    assert _y_absoluta(pantalla.combo_tipo, pantalla) < _y_absoluta(pantalla.spin_desde, pantalla)


def test_comentarios_reemplaza_a_detalle_como_etiqueta(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    etiquetas = {lbl.text() for lbl in pantalla.findChildren(QLabel)}
    assert "Comentarios" in etiquetas
    assert "Detalle" not in etiquetas
    assert pantalla.tabla.horizontalHeaderItem(9).text() == "Comentarios"


def test_tabla_primera_columna_es_la_fecha_en_formato_dd_mm_aaaa(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    crear_pedido(
        conn, id_profesional=id_profesional, bloques=[_bloque_lunes()], fecha_pedido="2026-03-05",
    )
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.horizontalHeaderItem(0).text() == "Fecha pedido"
    assert pantalla.tabla.item(0, 0).text() == "05-03-2026"


def test_tabla_ordena_mas_reciente_arriba_y_por_codigo_a_igual_fecha(qtbot, conn):
    id_temprano = _crear_profesional(conn, apellido="Antiguo", codigo="R5")
    id_r2 = _crear_profesional(conn, apellido="Dos", codigo="R2")
    id_r10 = _crear_profesional(conn, apellido="Diez", codigo="R10")
    crear_pedido(conn, id_profesional=id_temprano, bloques=[_bloque_lunes()], fecha_pedido="2026-01-01")
    crear_pedido(conn, id_profesional=id_r10, bloques=[_bloque_lunes()], fecha_pedido="2026-03-05")
    crear_pedido(conn, id_profesional=id_r2, bloques=[_bloque_lunes()], fecha_pedido="2026-03-05")

    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)

    nombres = [pantalla.tabla.item(fila, 1).text() for fila in range(pantalla.tabla.rowCount())]
    assert nombres == ["R2 - Dos", "R10 - Diez", "R5 - Antiguo"]


def test_profesional_se_muestra_en_formato_codigo_tratamiento_nombre_apellido(qtbot, conn):
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, NombrePila, Tratamiento, IdCodigo) "
        "VALUES ('R', 'Lo Veci', 'Virginia', 'Lic.', 'R1')"
    )
    conn.commit()
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional WHERE IdCodigo = 'R1'").fetchone()[
        "IdProfesional"
    ]
    crear_pedido(conn, id_profesional=id_profesional, bloques=[_bloque_lunes()])

    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.item(0, 1).text() == "R1 - Lic. Virginia Lo Veci"


def test_profesional_sin_tratamiento_ni_nombre_omite_esos_datos(qtbot, conn):
    """Sin Tratamiento ni NombrePila cargados, el nombre no debe quedar
    con espacios de más ni "None" — se omite lo que falte, no solo el
    apellido (obligatorio en la base) del ejemplo de la clienta."""
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, IdCodigo) VALUES ('R', 'Paz', 'R3')")
    conn.commit()
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional WHERE IdCodigo = 'R3'").fetchone()[
        "IdProfesional"
    ]
    crear_pedido(conn, id_profesional=id_profesional, bloques=[_bloque_lunes()])

    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.item(0, 1).text() == "R3 - Paz"


def test_fecha_contacto_no_se_agrega_al_nombre_aunque_este_cargada(qtbot, conn):
    """Confirmado por la clienta: para cargar un pedido el profesional
    obligatoriamente ya tiene código asignado, y con eso alcanza para
    identificarlo — se saca la fecha de contacto de la concatenación."""
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, IdCodigo, FechaContacto) "
        "VALUES ('R', 'Paz', 'R3', '2024-11-20')"
    )
    conn.commit()
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional WHERE IdCodigo = 'R3'").fetchone()[
        "IdProfesional"
    ]
    crear_pedido(conn, id_profesional=id_profesional, bloques=[_bloque_lunes()])

    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.item(0, 1).text() == "R3 - Paz"


def test_horario_de_la_tabla_termina_en_hs(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    crear_pedido(conn, id_profesional=id_profesional, bloques=[_bloque_lunes()])
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.item(0, 3).text() == "9 a 12hs"


def test_cobertura_vacia_sin_seleccion(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    crear_pedido(conn, id_profesional=id_profesional, bloques=[_bloque_lunes()])
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.texto_cobertura.toPlainText() == ""


def test_cobertura_muestra_dia_horario_y_consultorio_al_seleccionar_verde(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    id_profesional = _crear_profesional(conn)
    crear_pedido(conn, id_profesional=id_profesional, bloques=[_bloque_lunes()])

    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)

    texto = pantalla.texto_cobertura.toPlainText()
    assert "Lunes:" in texto
    assert "9 a 12hs" in texto
    assert "Torre Norte - 1A - Consultorio 1" in texto


def test_cobertura_con_varios_dias_los_separa_con_punto_y_coma(qtbot, conn):
    """Confirmado por la clienta: el cuadro de cobertura pasa a ser más
    corto (2 líneas) y el contenido, en vez de un bloque por línea, va
    todo en un renglón separado por ";"."""
    _crear_edificio_con_consultorio(conn)
    id_profesional = _crear_profesional(conn)
    crear_pedido(
        conn, id_profesional=id_profesional,
        bloques=[{"dias": ["Lunes", "Miércoles"], "horario_desde": 9, "horario_hasta": 12}],
    )
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)

    texto = pantalla.texto_cobertura.toPlainText()
    assert texto == (
        "Lunes: 9 a 12hs — Torre Norte - 1A - Consultorio 1; "
        "Miércoles: 9 a 12hs — Torre Norte - 1A - Consultorio 1"
    )
    assert "\n" not in texto


def test_cobertura_indica_sin_cobertura_cuando_no_hay_color(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    crear_pedido(conn, id_profesional=id_profesional, bloques=[_bloque_lunes()])  # sin ningún consultorio cargado
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)
    assert "Sin cobertura" in pantalla.texto_cobertura.toPlainText()


def test_tamano_minimo_es_combo_cerrado_deshabilitado_hasta_tildar_la_casilla(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.casilla_tamano.text() == "Tamaño mínimo"
    assert not pantalla.combo_tamano.isEnabled()
    textos = [pantalla.combo_tamano.itemText(i) for i in range(pantalla.combo_tamano.count())]
    assert textos == ["Chico", "Intermedio", "Grande"]

    pantalla.casilla_tamano.setChecked(True)
    assert pantalla.combo_tamano.isEnabled()


def test_crear_pedido_con_tamano_persiste_la_condicion(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla._agregar_bloque()
    pantalla.casilla_tamano.setChecked(True)
    pantalla.combo_tamano.setCurrentIndex(pantalla.combo_tamano.findData("Grande"))

    pantalla._crear_pedido()

    id_pedido = conn.execute("SELECT IdPedido FROM ListaEspera").fetchone()["IdPedido"]
    condiciones = conn.execute(
        "SELECT CondicionesConsultorio FROM ListaEspera WHERE IdPedido = ?", (id_pedido,)
    ).fetchone()["CondicionesConsultorio"]
    assert '"tamano": "Grande"' in condiciones


def test_crear_pedido_por_defecto_persiste_sin_combinar(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla._agregar_bloque()

    pantalla._crear_pedido()

    id_pedido = conn.execute("SELECT IdPedido FROM ListaEspera").fetchone()["IdPedido"]
    condiciones = conn.execute(
        "SELECT CondicionesConsultorio FROM ListaEspera WHERE IdPedido = ?", (id_pedido,)
    ).fetchone()["CondicionesConsultorio"]
    assert '"sinCombinar": true' in condiciones


def test_elegir_con_combinacion_no_persiste_sincombinar(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla._agregar_bloque()
    pantalla.combo_sin_combinar.setCurrentIndex(pantalla.combo_sin_combinar.findData(False))

    pantalla._crear_pedido()

    id_pedido = conn.execute("SELECT IdPedido FROM ListaEspera").fetchone()["IdPedido"]
    condiciones = conn.execute(
        "SELECT CondicionesConsultorio FROM ListaEspera WHERE IdPedido = ?", (id_pedido,)
    ).fetchone()["CondicionesConsultorio"]
    assert "sinCombinar" not in condiciones


def test_crear_pedido_sin_dias_no_persiste(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._crear_pedido()  # sin días marcados -> ValueError capturado, no debe persistir
    assert conn.execute("SELECT COUNT(*) c FROM ListaEspera").fetchone()["c"] == 0


def test_crear_pedido_con_dias_persiste_y_aparece_en_tabla(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)

    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes
    pantalla._agregar_bloque()
    pantalla._crear_pedido()

    assert conn.execute("SELECT COUNT(*) c FROM ListaEspera").fetchone()["c"] == 1
    assert pantalla.tabla.rowCount() == 1
    assert "Lunes" in pantalla.tabla.item(0, 2).text()


def test_sin_cobertura_muestra_etiqueta_sin_color(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla._agregar_bloque()
    pantalla._crear_pedido()
    assert pantalla.tabla.item(0, 8).text() == "Sin cobertura"


def test_agregar_bloque_lo_suma_a_la_tabla_y_limpia_dias(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # Lunes

    pantalla._agregar_bloque()

    assert len(pantalla._bloques_pendientes) == 1
    assert pantalla.tabla_bloques.rowCount() == 1
    assert pantalla.tabla_bloques.item(0, 0).text() == "Lunes"
    assert pantalla._dias_seleccionados() == []  # se limpia para cargar el próximo bloque


def test_agregar_bloque_sin_dias_no_agrega(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._agregar_bloque()
    assert pantalla._bloques_pendientes == []


def test_crear_pedido_con_dos_bloques_persiste_los_dos(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)

    pantalla._checks_dia["Martes"].setChecked(True)  # Martes
    pantalla._checks_dia["Jueves"].setChecked(True)  # Jueves
    pantalla._agregar_bloque()
    pantalla._checks_dia["Sábado"].setChecked(True)  # Sábado
    pantalla._agregar_bloque()
    pantalla.combo_tipo_bloques.setCurrentIndex(pantalla.combo_tipo_bloques.findData("Y"))
    pantalla._crear_pedido()

    assert conn.execute("SELECT COUNT(*) c FROM ListaEspera").fetchone()["c"] == 1
    id_pedido = conn.execute("SELECT IdPedido FROM ListaEspera").fetchone()["IdPedido"]
    assert conn.execute("SELECT COUNT(*) c FROM ListaEsperaBloque WHERE IdPedido = ?", (id_pedido,)).fetchone()["c"] == 2
    assert conn.execute("SELECT TipoCombinacion FROM ListaEspera").fetchone()["TipoCombinacion"] == "Y"
    assert pantalla._bloques_pendientes == []  # se limpia después de crear


def test_quitar_bloque_lo_saca_de_la_tabla(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla._agregar_bloque()

    pantalla.tabla_bloques.selectRow(0)
    pantalla._quitar_bloque()

    assert pantalla._bloques_pendientes == []
    assert pantalla.tabla_bloques.rowCount() == 0


def test_descartar_saca_el_pedido_de_la_lista(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla._agregar_bloque()
    pantalla._crear_pedido()

    pantalla.tabla.selectRow(0)
    pantalla._descartar()

    assert pantalla.tabla.rowCount() == 0
    estado = conn.execute("SELECT Estado FROM ListaEspera").fetchone()["Estado"]
    assert estado == "Descartado"


def test_editar_pedido_sin_seleccion_avisa_y_no_rompe(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._editar_pedido()  # no debe lanzar excepción
    assert pantalla._id_pedido_en_edicion is None
    assert pantalla.boton_crear.text() == "Crear pedido"


def test_editar_pedido_carga_el_formulario_y_pone_en_modo_edicion(qtbot, conn):
    id_profesional = _crear_profesional(conn, apellido="Paz", codigo="R3")
    crear_pedido(
        conn, id_profesional=id_profesional,
        bloques=[{"dias": ["Martes"], "horario_desde": 10, "horario_hasta": 14}],
        condiciones_consultorio={"ventana": True}, detalle="pedido original",
    )
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)

    pantalla._editar_pedido()

    assert pantalla.combo_profesional.currentData() == id_profesional
    assert pantalla.casilla_ventana.isChecked()
    assert pantalla.combo_sin_combinar.currentData() is False  # no vino "sinCombinar" en la condición original
    assert pantalla._bloques_pendientes == [{
        "dias": ["Martes"], "horario_desde": 10, "horario_hasta": 14,
        "tipo_combinacion_dias": "O", "cantidad_horas_requeridas": None,
    }]
    assert pantalla.campo_detalle.toPlainText() == "pedido original"
    assert pantalla._id_pedido_en_edicion is not None
    assert pantalla.boton_crear.text() == "Guardar cambios"


def test_confirmar_edicion_actualiza_el_pedido_existente_y_lo_manda_arriba(qtbot, conn):
    id_profesional = _crear_profesional(conn, apellido="Paz", codigo="R3")
    id_pedido = crear_pedido(
        conn, id_profesional=id_profesional, bloques=[_bloque_lunes()], fecha_pedido="2020-01-01",
    )
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)
    pantalla._editar_pedido()

    pantalla._checks_dia["Miércoles"].setChecked(True)
    pantalla.campo_detalle.setPlainText("comentario actualizado")
    pantalla._crear_pedido()

    assert conn.execute("SELECT COUNT(*) c FROM ListaEspera").fetchone()["c"] == 1  # no creó uno nuevo
    pedido = conn.execute("SELECT * FROM ListaEspera WHERE IdPedido = ?", (id_pedido,)).fetchone()
    assert pedido["Detalle"] == "comentario actualizado"
    assert pedido["FechaPedido"] != "2020-01-01"
    assert pantalla._id_pedido_en_edicion is None
    assert pantalla.boton_crear.text() == "Crear pedido"


def test_tabla_muestra_columnas_de_combinacion_y_condiciones(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    crear_pedido(
        conn, id_profesional=id_profesional, bloques=[_bloque_lunes()],
        condiciones_consultorio={"ventana": True}, tipo_combinacion_bloques="O",
    )
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)

    encabezados = [pantalla.tabla.horizontalHeaderItem(i).text() for i in range(pantalla.tabla.columnCount())]
    assert encabezados == [
        "Fecha pedido", "Profesional", "Días", "Horario", "Combinación días", "Combinación bloques",
        "Combinación consultorios", "Condiciones", "Coincidencia", "Comentarios",
    ]
    assert pantalla.tabla.item(0, 4).text() == "Alcanza con un día (O)"
    assert pantalla.tabla.item(0, 5).text() == "Alcanza con un bloque (O)"
    assert pantalla.tabla.item(0, 6).text() == "Con combinación de consultorios"
    assert pantalla.tabla.item(0, 7).text() == "Con ventana"


def test_tabla_columna_combinacion_consultorios_refleja_sin_combinar(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    crear_pedido(
        conn, id_profesional=id_profesional, bloques=[_bloque_lunes()],
        condiciones_consultorio={"sinCombinar": True},
    )
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.item(0, 6).text() == "Sin combinación de consultorios"


def test_tabla_tiene_tooltip_con_el_texto_completo_de_cada_celda(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    crear_pedido(conn, id_profesional=id_profesional, bloques=[_bloque_lunes()])
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)

    item = pantalla.tabla.item(0, 1)
    assert item.toolTip() == item.text()


def test_crear_pedido_sin_bloques_agregados_avisa_y_no_persiste(qtbot, conn):
    """Confirmado por la clienta: "Agregar bloque…" es obligatorio, no hay
    fallback que tome lo que esté cargado en el formulario."""
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)  # cargado en el formulario, pero nunca agregado

    pantalla._crear_pedido()

    assert conn.execute("SELECT COUNT(*) c FROM ListaEspera").fetchone()["c"] == 0


def test_combo_tipo_bloques_muestra_bloque_unico_deshabilitado_con_uno_solo(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.combo_tipo_bloques.currentText() == "Bloque único"
    assert not pantalla.combo_tipo_bloques.isEnabled()

    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla._agregar_bloque()
    assert pantalla.combo_tipo_bloques.currentText() == "Bloque único"
    assert not pantalla.combo_tipo_bloques.isEnabled()


def test_combo_tipo_bloques_se_habilita_con_mas_de_un_bloque(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla._agregar_bloque()
    pantalla._checks_dia["Martes"].setChecked(True)
    pantalla._agregar_bloque()

    assert pantalla.combo_tipo_bloques.isEnabled()
    textos = [pantalla.combo_tipo_bloques.itemText(i) for i in range(pantalla.combo_tipo_bloques.count())]
    assert textos == ["Alcanza con un bloque (O)", "Necesarios todos los bloques (Y)"]


def test_boton_quitar_bloque_solo_se_habilita_con_una_fila_seleccionada(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert not pantalla.boton_quitar_bloque.isEnabled()

    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla._agregar_bloque()
    assert not pantalla.boton_quitar_bloque.isEnabled()  # agregado, pero todavía sin seleccionar

    pantalla.tabla_bloques.selectRow(0)
    assert pantalla.boton_quitar_bloque.isEnabled()

    pantalla.tabla_bloques.clearSelection()
    assert not pantalla.boton_quitar_bloque.isEnabled()


def test_crear_pedido_con_profesional_que_ya_tiene_uno_activo_ofrece_editar(qtbot, conn):
    """Confirmado por la clienta: no puede haber dos pedidos activos del
    mismo profesional — si se intenta crear uno nuevo para alguien que ya
    tiene uno, se ofrece editar el existente en su lugar."""
    id_profesional = _crear_profesional(conn, apellido="Paz", codigo="R3")
    id_pedido_existente = crear_pedido(
        conn, id_profesional=id_profesional, bloques=[_bloque_lunes()], detalle="pedido original",
    )
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)

    indice = pantalla.combo_profesional.findData(id_profesional)
    pantalla.combo_profesional.setCurrentIndex(indice)
    pantalla._checks_dia["Martes"].setChecked(True)
    pantalla._agregar_bloque()

    pantalla._crear_pedido()  # _sin_dialogos_modales responde "Yes" a QMessageBox.question

    assert conn.execute("SELECT COUNT(*) c FROM ListaEspera").fetchone()["c"] == 1  # no se creó un segundo
    assert pantalla._id_pedido_en_edicion == id_pedido_existente
    assert pantalla.boton_crear.text() == "Guardar cambios"
    assert pantalla.campo_detalle.toPlainText() == "pedido original"  # el formulario quedó con el existente


def test_crear_pedido_con_profesional_duplicado_y_respuesta_no_no_hace_nada(qtbot, conn, monkeypatch):
    id_profesional = _crear_profesional(conn, apellido="Paz", codigo="R3")
    crear_pedido(conn, id_profesional=id_profesional, bloques=[_bloque_lunes()])
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional.findData(id_profesional)
    pantalla.combo_profesional.setCurrentIndex(indice)
    pantalla._checks_dia["Martes"].setChecked(True)
    pantalla._agregar_bloque()

    pantalla._crear_pedido()

    assert conn.execute("SELECT COUNT(*) c FROM ListaEspera").fetchone()["c"] == 1  # sigue habiendo solo el original
    assert pantalla._id_pedido_en_edicion is None


def test_condiciones_incluye_placard_y_aire(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.casilla_placard.setChecked(True)
    pantalla.casilla_aire.setChecked(True)
    condiciones = pantalla._condiciones()
    assert condiciones["placard"] is True
    assert condiciones["aire"] is True


def test_tabla_bloques_tiene_cuatro_columnas_con_horas_minimas(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    encabezados = [
        pantalla.tabla_bloques.horizontalHeaderItem(i).text() for i in range(pantalla.tabla_bloques.columnCount())
    ]
    assert encabezados == ["Días", "Horario", "Comb. días", "Horas mínimas"]

    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla.casilla_cantidad_horas.setChecked(True)
    pantalla.spin_cantidad_horas.setValue(3)
    pantalla._agregar_bloque()
    assert pantalla.tabla_bloques.item(0, 3).text() == "3hs"

    pantalla._checks_dia["Martes"].setChecked(True)
    pantalla.casilla_cantidad_horas.setChecked(False)
    pantalla._agregar_bloque()
    assert pantalla.tabla_bloques.item(1, 3).text() == "Completo"
