import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QLabel, QMessageBox

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


def test_caracteristicas_pedidas_ya_no_tiene_balcon_ni_aire(qtbot, conn):
    """Confirmado por la clienta: de "Características pedidas" solo quedan
    Con ventana, Apto camilla, Tamaño mínimo y Sin combinación —
    balcón y aire acondicionado se sacan de este formulario."""
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert not hasattr(pantalla, "casilla_balcon")
    assert not hasattr(pantalla, "casilla_aire")


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


def test_titulo_combinacion_de_dias_y_horarios_encabeza_su_columna(qtbot, conn):
    """El título de la sección encabeza la columna "Cuándo" (por encima
    de los checks de días), y el selector "Alcanza con un día (O)" en sí
    se queda donde estaba, debajo de los checks — separado de su propio
    título, que ahora es el encabezado de toda la columna."""
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    titulo = next(lbl for lbl in pantalla.findChildren(QLabel) if lbl.text() == "Combinación de días y horarios")
    assert _y_absoluta(titulo, pantalla) < _y_absoluta(pantalla._checks_dia["Lunes"], pantalla)
    assert "Días" not in {lbl.text() for lbl in pantalla.findChildren(QLabel)}


def test_comentarios_reemplaza_a_detalle_como_etiqueta(qtbot, conn):
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    etiquetas = {lbl.text() for lbl in pantalla.findChildren(QLabel)}
    assert "Comentarios" in etiquetas
    assert "Detalle" not in etiquetas
    assert pantalla.tabla.horizontalHeaderItem(8).text() == "Comentarios"


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


def test_fecha_contacto_se_agrega_despues_del_nombre_si_esta_cargada(qtbot, conn):
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
    assert pantalla.tabla.item(0, 1).text() == "R3 - Paz — 20-11-2024"


def test_fecha_contacto_se_omite_si_no_esta_cargada(qtbot, conn):
    id_profesional = _crear_profesional(conn, codigo="R3")
    crear_pedido(conn, id_profesional=id_profesional, bloques=[_bloque_lunes()])

    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    assert "—" not in pantalla.tabla.item(0, 1).text()


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
    pantalla.casilla_tamano.setChecked(True)
    pantalla.combo_tamano.setCurrentIndex(pantalla.combo_tamano.findData("Grande"))

    pantalla._crear_pedido()

    id_pedido = conn.execute("SELECT IdPedido FROM ListaEspera").fetchone()["IdPedido"]
    condiciones = conn.execute(
        "SELECT CondicionesConsultorio FROM ListaEspera WHERE IdPedido = ?", (id_pedido,)
    ).fetchone()["CondicionesConsultorio"]
    assert '"tamano": "Grande"' in condiciones


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
    pantalla._crear_pedido()

    assert conn.execute("SELECT COUNT(*) c FROM ListaEspera").fetchone()["c"] == 1
    assert pantalla.tabla.rowCount() == 1
    assert "Lunes" in pantalla.tabla.item(0, 2).text()


def test_sin_cobertura_muestra_etiqueta_sin_color(qtbot, conn):
    _crear_profesional(conn)
    pantalla = PantallaListaEspera(conn)
    qtbot.addWidget(pantalla)
    pantalla._checks_dia["Lunes"].setChecked(True)
    pantalla._crear_pedido()
    assert pantalla.tabla.item(0, 7).text() == "Sin cobertura"


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
    pantalla.combo_tipo_bloques.setCurrentIndex(1)  # Y
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
        "Condiciones", "Coincidencia", "Comentarios",
    ]
    assert pantalla.tabla.item(0, 4).text() == "O"
    assert pantalla.tabla.item(0, 5).text() == "Alcanza con un bloque (O)"
    assert pantalla.tabla.item(0, 6).text() == "Con ventana"
