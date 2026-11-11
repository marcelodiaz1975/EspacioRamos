import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QPushButton

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.crud_generico import _DialogoRegistro
from app.gui.pantallas.mensajes_predefinidos import _opciones_categoria_mensaje, _PanelMensajesPredefinidos
from app.repositorio.registro import obtener_repositorio


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


def _crear_consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Norte")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="7mo")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=3)
    return id_consultorio


def test_es_un_panel_solapa_con_crud_anidado(qtbot, conn):
    """Reordenamiento de formularios: dejó de ser una pantalla propia con
    su propio título/QTabWidget — ahora es la solapa "Mensajes
    predefinidos" de "Grilla y mensajería" (ver grilla_y_mensajeria.py),
    y el PantallaCRUD interno va en modo anidado (sin título ni
    QTabWidget "Listado" propios)."""
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.objectName() == "panelSolapa"
    assert pantalla.crud.anidado is True
    assert pantalla.crud.objectName() == "panelSolapa"


def test_pantalla_se_arma_con_los_sembrados(qtbot, conn):
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.crud.tabla_widget.rowCount() == len(obtener_repositorio(conn, "MensajePredefinido").listar())


def test_pantalla_tiene_tres_campos_libres(qtbot, conn):
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.crud.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_orden_del_panel_izquierdo_categoria_dirigido_a_copiar_nuevo(qtbot, conn):
    """Pedido de la clienta: "Copiar mensaje" arriba de "Nuevo" (como
    acción principal de la pantalla), y "Dirigido a" (+ los cuatro
    selectores de contexto) arriba de "Copiar mensaje"."""
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    boton_copiar = next(
        w for w in pantalla.findChildren(type(pantalla.crud.boton_nuevo)) if w.text() == "Copiar mensaje"
    )
    padre = pantalla.combo_filtro.parentWidget()
    layout = padre.layout()
    indices = {layout.itemAt(i).widget(): i for i in range(layout.count()) if layout.itemAt(i).widget() is not None}
    assert indices[pantalla.combo_filtro] < indices[pantalla.combo_dirigido_a]
    assert indices[pantalla.combo_dirigido_a] < indices[pantalla.combo_localidad_contexto]
    assert indices[pantalla.combo_localidad_contexto] < indices[pantalla.combo_edificio_contexto]
    assert indices[pantalla.combo_edificio_contexto] < indices[pantalla.combo_unidad_contexto]
    assert indices[pantalla.combo_unidad_contexto] < indices[pantalla.combo_consultorio_contexto]
    assert indices[pantalla.combo_consultorio_contexto] < indices[boton_copiar]
    assert boton_copiar.objectName() == "botonPrimario"
    assert pantalla.crud.boton_nuevo.objectName() == "botonSecundario"


def test_sin_linea_divisoria_entre_categoria_y_dirigido_a(qtbot, conn):
    from PySide6.QtWidgets import QFrame

    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    padre = pantalla.combo_filtro.parentWidget()
    lineas = [w for w in padre.findChildren(QFrame) if w.frameShape() == QFrame.Shape.HLine]
    assert lineas == []


def test_pantalla_tiene_campo_localidad_antes_de_edificio(qtbot, conn):
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.crud.campos]
    assert nombres.index("IdLocalidad") < nombres.index("IdEdificio")


def test_categoria_es_combo_editable_con_valores_de_listas_editables(qtbot, conn):
    obtener_repositorio(conn, "ListasEditables").crear(TipoLista="CategoriaMensaje", Valor="Recordatorios", Orden=0)
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.crud.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    combo_categoria = dialogo._entradas["Categoria"]
    assert combo_categoria.isEditable() is True
    opciones = [combo_categoria.itemText(i) for i in range(combo_categoria.count())]
    assert opciones == ["Recordatorios"]
    combo_categoria.setEditText("Categoría inventada")
    assert dialogo.valores()["Categoria"] == "Categoría inventada"


def test_edificio_unidad_consultorio_admiten_dejarlos_sin_seleccionar(qtbot, conn):
    """Si Localidad/Edificio/Unidad/Consultorio quedan todos sin
    seleccionar, el mensaje es general (pedido de la clienta) — para eso
    estos combos, a diferencia de los de catalogos.py, tienen que poder
    quedar en blanco. La etiqueta de ese valor en blanco es "En general"
    en los cuatro, tanto acá como en los selectores de contexto."""
    _crear_consultorio(conn)
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.crud.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    for campo in ("IdLocalidad", "IdEdificio", "IdUnidad", "IdConsultorio"):
        combo = dialogo._entradas[campo]
        assert combo.itemData(0) is None
        assert combo.itemText(0) == "En general"
    assert dialogo.valores()["IdEdificio"] is None
    assert dialogo.valores()["IdUnidad"] is None
    assert dialogo.valores()["IdConsultorio"] is None


def test_selectores_de_contexto_arrancan_en_general(qtbot, conn):
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    for combo in (
        pantalla.combo_localidad_contexto, pantalla.combo_edificio_contexto,
        pantalla.combo_unidad_contexto, pantalla.combo_consultorio_contexto,
    ):
        assert combo.currentText() == "En general"
        assert combo.currentData() is None


def test_contexto_edificio_pisa_al_vinculo_del_mensaje_general(qtbot, conn):
    """Un mensaje general (sin edificio propio) se puede previsualizar
    como si fuera para un edificio puntual, eligiéndolo en el selector de
    contexto — sin tener que editar el mensaje."""
    obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Norte")
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Sur")
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Avisos", Descripcion="Corte de luz", Mensaje="Se corta la luz en {edificio}.", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)

    fila = next(
        f for f in range(pantalla.crud.tabla_widget.rowCount())
        if pantalla.crud.tabla_widget.item(f, 1).text() == "Corte de luz"
    )
    pantalla.crud.tabla_widget.selectRow(fila)
    assert pantalla.texto_vista_previa.toPlainText() == "Se corta la luz en ."

    indice = pantalla.combo_edificio_contexto.findData(id_edificio)
    pantalla.combo_edificio_contexto.setCurrentIndex(indice)
    assert pantalla.texto_vista_previa.toPlainText() == "Se corta la luz en Torre Sur."


def test_contexto_en_general_no_pisa_el_vinculo_propio_del_mensaje(qtbot, conn):
    id_consultorio = _crear_consultorio(conn)
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Avisos", Descripcion="Aviso puntual", IdConsultorio=id_consultorio,
        Mensaje="Te esperamos en {edificio}.", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    fila = next(
        f for f in range(pantalla.crud.tabla_widget.rowCount())
        if pantalla.crud.tabla_widget.item(f, 1).text() == "Aviso puntual"
    )
    pantalla.crud.tabla_widget.selectRow(fila)
    assert pantalla.texto_vista_previa.toPlainText() == "Te esperamos en Torre Norte."


def test_dirigido_a_por_defecto_es_nadie_en_particular(qtbot, conn):
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.combo_dirigido_a.currentText() == "Nadie en particular"
    assert pantalla.combo_dirigido_a.currentData() is None


def test_dirigido_a_sustituye_apodo_en_la_vista_previa(qtbot, conn):
    id_profesional = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Gómez", Apodo="Daniela",
    )
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Avisos", Descripcion="Corte de agua", Mensaje="Hola {apodo}, mañana no hay agua.", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)

    fila = next(
        f for f in range(pantalla.crud.tabla_widget.rowCount())
        if pantalla.crud.tabla_widget.item(f, 1).text() == "Corte de agua"
    )
    pantalla.crud.tabla_widget.selectRow(fila)
    assert pantalla.texto_vista_previa.toPlainText() == "Hola , mañana no hay agua."

    indice = pantalla.combo_dirigido_a.findData(id_profesional)
    pantalla.combo_dirigido_a.setCurrentIndex(indice)
    assert pantalla.texto_vista_previa.toPlainText() == "Hola Daniela, mañana no hay agua."


def test_combo_filtro_incluye_todas_y_las_categorias_sembradas(qtbot, conn):
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Recordatorios", Descripcion="Aviso", Mensaje="Hola {edificio}", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    categorias = [pantalla.combo_filtro.itemText(i) for i in range(pantalla.combo_filtro.count())]
    assert categorias[0] == "Todas"
    assert "Recordatorios" in categorias


def test_filtrar_por_categoria_oculta_las_demas_filas(qtbot, conn):
    id_consultorio = _crear_consultorio(conn)
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Recordatorios", Descripcion="Aviso", IdConsultorio=id_consultorio,
        Mensaje="Hola {edificio}", Activo=1,
    )
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Bienvenida", Descripcion="Saludo", Mensaje="Hola!", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)

    indice = pantalla.combo_filtro.findData("Recordatorios")
    pantalla.combo_filtro.setCurrentIndex(indice)

    tabla = pantalla.crud.tabla_widget
    ocultas = [tabla.isRowHidden(f) for f in range(tabla.rowCount())]
    categorias_filas = [tabla.item(f, 0).text() for f in range(tabla.rowCount())]
    for oculta, categoria in zip(ocultas, categorias_filas):
        assert oculta == (categoria != "Recordatorios")


def test_filtro_todas_no_oculta_ninguna_fila(qtbot, conn):
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Recordatorios", Descripcion="Aviso", Mensaje="Hola {edificio}", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.crud.tabla_widget
    assert not any(tabla.isRowHidden(f) for f in range(tabla.rowCount()))


def test_seleccionar_fila_arma_vista_previa_con_variables_sustituidas(qtbot, conn):
    id_consultorio = _crear_consultorio(conn)
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Recordatorios", Descripcion="Aviso", IdConsultorio=id_consultorio,
        Mensaje="Te esperamos en {edificio}, {unidad}, consultorio {consultorio}.", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)

    fila = next(
        f for f in range(pantalla.crud.tabla_widget.rowCount())
        if pantalla.crud.tabla_widget.item(f, 1).text() == "Aviso"
    )
    pantalla.crud.tabla_widget.selectRow(fila)

    assert pantalla.texto_vista_previa.toPlainText() == "Te esperamos en Torre Norte, 7mo, consultorio 3."


def test_copiar_mensaje_usa_portapapeles(qtbot, conn, monkeypatch):
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    pantalla.texto_vista_previa.setPlainText("texto de prueba")

    copiado = []
    monkeypatch.setattr(
        "app.gui.pantallas.mensajes_predefinidos.QGuiApplication.clipboard",
        staticmethod(lambda: type("_C", (), {"setText": lambda self, t: copiado.append(t)})()),
    )
    pantalla._copiar_mensaje()
    assert copiado == ["texto de prueba"]


def test_campo_mensaje_suma_variables_al_diccionario_de_campo(qtbot, conn):
    """Hallazgo #24 de la auditoría: el campo Mensaje tiene que ofrecer
    la lista de variables disponibles, no solo el texto suelto de la
    leyenda de Vista previa."""
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    campo_mensaje = next(c for c in pantalla.crud.campos if c.nombre == "Mensaje")
    assert campo_mensaje.variables is not None
    assert set(campo_mensaje.variables) == {
        "apodo", "nombre", "apellido", "tratamiento", "edificio", "unidad", "consultorio", "localidad",
        "nombre_espacio", "nombre_administrador_principal",
    }


def test_dialogo_suma_un_boton_por_variable_que_inserta_en_el_cursor(qtbot, conn):
    """"Cómo selecciono variables": un botón por variable en el diálogo
    Nuevo/Editar, debajo del campo Mensaje, que inserta "{variable}" en
    el cursor del texto al hacer clic."""
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.crud.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    entrada = dialogo._entradas["Mensaje"]
    entrada.setPlainText("Hola, ")
    cursor = entrada.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    entrada.setTextCursor(cursor)

    botones = dialogo.findChildren(QPushButton)
    boton_apodo = next(b for b in botones if b.text() == "{apodo}")
    assert "Apodo del profesional" in boton_apodo.toolTip()
    boton_apodo.click()
    assert entrada.toPlainText() == "Hola, {apodo}"

    boton_localidad = next(b for b in botones if b.text() == "{localidad}")
    boton_localidad.click()
    assert entrada.toPlainText() == "Hola, {apodo}{localidad}"


def test_dialogo_nuevo_tiene_10_variables_en_grilla_de_2x5(qtbot, conn):
    """Pedido explícito de la clienta al sumar {nombre_administrador_
    principal}: "ahora que son [10] variables ponelas en dos filas de 5
    botones" (antes 3x3 con 9)."""
    from PySide6.QtWidgets import QGridLayout

    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.crud.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)

    botones_variable = [b for b in dialogo.findChildren(QPushButton) if b.text().startswith("{")]
    assert len(botones_variable) == 10
    grilla = next(g for g in dialogo.findChildren(QGridLayout) if g.count() == 10)
    assert grilla.rowCount() == 2
    assert grilla.columnCount() == 5


def test_vista_previa_sustituye_nombre_espacio(qtbot, conn):
    """Pedido explícito de la clienta: nueva variable {nombre_espacio},
    resuelta contra Configuracion.NombreEspacio."""
    obtener_repositorio(conn, "Configuracion").actualizar(1, NombreEspacio="Espacio Ramos")
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Prueba", Mensaje="Hola desde {nombre_espacio}.", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud.tabla_widget.selectRow(0)
    assert pantalla.texto_vista_previa.toPlainText() == "Hola desde Espacio Ramos."


def test_vista_previa_sustituye_nombre_administrador_principal(qtbot, conn):
    """Pedido explícito de la clienta: nueva variable {nombre_
    administrador_principal}, resuelta contra el Responsable con
    Rol="Administrador principal" y EsContactoPrincipal=1."""
    obtener_repositorio(conn, "Responsable").crear(
        Nombre="Marcela Díaz", Rol="Administrador principal", EsContactoPrincipal=1,
    )
    # Responsable NO elegible (otro rol) — no tiene que interferir.
    obtener_repositorio(conn, "Responsable").crear(Nombre="Otro", Rol="Mantenimiento general", EsContactoPrincipal=1)
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Prueba", Mensaje="Hola de parte de {nombre_administrador_principal}.", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud.tabla_widget.selectRow(0)
    assert pantalla.texto_vista_previa.toPlainText() == "Hola de parte de Marcela Díaz."


def test_vista_previa_sin_administrador_principal_configurado_queda_en_blanco(qtbot, conn):
    """Sin ningún Responsable que cumpla las dos condiciones a la vez
    (Rol="Administrador principal" Y Contacto principal), la variable
    queda en blanco — no rompe la vista previa."""
    obtener_repositorio(conn, "Responsable").crear(
        Nombre="Marcela Díaz", Rol="Administrador principal", EsContactoPrincipal=0,
    )
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Prueba", Mensaje="Hola de parte de {nombre_administrador_principal}.", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud.tabla_widget.selectRow(0)
    assert pantalla.texto_vista_previa.toPlainText() == "Hola de parte de ."


def test_dialogo_nuevo_queda_al_doble_de_ancho_y_un_40_porciento_mas_alto_centrado_arriba(qtbot, conn):
    """Pedido explícito de la clienta, en dos rondas: primero "el doble
    de ancho y de alto que el que se abre ahora, que arranque mas
    arriba en pantalla, centralizado, para que se vea completo al
    abrir"; después, sobre ese mismo diálogo, "reducí el alto... un 30%"
    SIN tocar el ancho — 2.0 (ancho) se mantiene, el alto pasa a 2.0 *
    0.7 = 1.4 (un multiplicador independiente del de ancho, ver
    `PantallaCRUD.__init__`/`_DialogoRegistro.__init__`)."""
    from app.gui.crud_generico import Campo

    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)

    campos = pantalla.crud.campos
    dialogo_normal = _DialogoRegistro(conn, campos, "Nuevo registro")
    qtbot.addWidget(dialogo_normal)
    dialogo_ajustado = _DialogoRegistro(
        conn, campos, "Nuevo registro", multiplicador_ancho=2.0, multiplicador_alto=1.4,
    )
    qtbot.addWidget(dialogo_ajustado)

    assert dialogo_ajustado.width() == dialogo_normal.width() * 2
    assert dialogo_ajustado.height() == int(dialogo_normal.height() * 1.4)

    sin_multiplicador = _DialogoRegistro(conn, [Campo("X", "X")], "Nuevo registro")
    qtbot.addWidget(sin_multiplicador)
    pos_default = sin_multiplicador.pos()
    con_multiplicador = _DialogoRegistro(
        conn, [Campo("X", "X")], "Nuevo registro", multiplicador_ancho=2.0, multiplicador_alto=1.4,
    )
    qtbot.addWidget(con_multiplicador)
    assert con_multiplicador.pos() != pos_default  # se reposiciona a mano (centrado, arriba), no el default de Qt


def test_pantalla_mensajes_predefinidos_usa_el_mismo_ancho_y_el_alto_reducido(qtbot, conn):
    """Confirma que `_PanelMensajesPredefinidos` arma su `PantallaCRUD`
    con los multiplicadores reales (2.0 de ancho, 1.4 de alto) — no solo
    que `_DialogoRegistro` SOPORTA valores independientes (el test de
    arriba), sino que esta pantalla puntual los está usando."""
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.crud._multiplicador_tamano_dialogo == 2.0
    assert pantalla.crud._multiplicador_alto_dialogo == 1.4


def test_tabla_categoria_y_descripcion_al_ancho_natural_consul_como_localidad(qtbot, conn):
    """Segunda ronda sobre esta tabla (la primera, +1/3 para Categoría/
    Descripción y Consul al mínimo de su etiqueta, queda en el test de
    abajo con datos reales desestimada): "Reducí el ancho de las
    columnas 'Categoría' y 'Descripción'... que quede un poco mas ancha
    [Descripción]" y "'Consul' dejala del mismo ancho que localidad,
    edificio y unidad" — ninguna de las tres usa ya `tercio_extra`/
    `ancho_minimo_etiqueta`, vuelven al ancho natural (contenido +
    padding) que ya usan Localidad/Edificio/Unidad."""
    obtener_repositorio(conn, "Configuracion").actualizar(1, VisualizarCamposLibres=0)
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Pagos", Descripcion="Aviso de pago pendiente con un texto largo", Mensaje="x" * 300, Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    pantalla.resize(1600, 850)
    qtbot.waitExposed(pantalla)

    tabla = pantalla.crud.tabla_widget
    campos = pantalla.crud.campos
    indice = {c.nombre: i for i, c in enumerate(campos)}

    from app.gui.crud_generico import _PADDING_COLUMNA

    ancho_categoria_ajustado = tabla.columnWidth(indice["Categoria"])
    ancho_descripcion_ajustado = tabla.columnWidth(indice["Descripcion"])
    ancho_consul_ajustado = tabla.columnWidth(indice["IdConsultorio"])
    tabla.resizeColumnsToContents()
    ancho_categoria_natural = tabla.columnWidth(indice["Categoria"]) + _PADDING_COLUMNA
    ancho_descripcion_natural = tabla.columnWidth(indice["Descripcion"]) + _PADDING_COLUMNA
    ancho_consul_natural = tabla.columnWidth(indice["IdConsultorio"]) + _PADDING_COLUMNA
    # Ancho natural (contenido + padding), sin ningún +1/3 ni recorte al
    # mínimo de la etiqueta — mismo mecanismo que Localidad/Edificio/
    # Unidad, no un caso especial aparte.
    assert ancho_categoria_ajustado == ancho_categoria_natural
    assert ancho_descripcion_ajustado == ancho_descripcion_natural
    assert ancho_consul_ajustado == ancho_consul_natural
    # "Descripción" (una frase) naturalmente más ancha que "Categoría"
    # (una palabra), sin ningún truco de más.
    assert ancho_descripcion_ajustado > ancho_categoria_ajustado

    pantalla.crud.actualizar()
    disponible = tabla.viewport().width()
    suma_columnas = sum(tabla.columnWidth(c) for c in range(tabla.columnCount()))
    assert suma_columnas <= disponible + 1  # la tabla entera entra sin espacio en blanco

    from PySide6.QtCore import Qt
    assert tabla.item(0, indice["IdConsultorio"]).textAlignment() == Qt.AlignmentFlag.AlignCenter
    assert tabla.item(0, indice["Activo"]).textAlignment() == Qt.AlignmentFlag.AlignCenter


def test_campos_sin_variables_no_suman_ningun_boton_extra(qtbot, conn):
    """Un campo "texto_largo" sin `variables` (el caso general de
    cualquier otro catálogo) no se ve afectado por este mecanismo."""
    from app.gui.crud_generico import Campo

    campos = [Campo("Descripcion", "Descripción", tipo="texto_largo")]
    dialogo = _DialogoRegistro(conn, campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    # Ningún botón extra de inserción de variables — solo quedan los de
    # siempre (Aceptar/Cancelar, del QDialogButtonBox).
    assert not any(b.text().startswith("{") for b in dialogo.findChildren(QPushButton))


def test_localidad_del_mensaje_sustituye_en_la_vista_previa(qtbot, conn):
    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Vicente López")
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Avisos", Descripcion="Aviso localidad", IdLocalidad=id_localidad,
        Mensaje="Estamos en {localidad}.", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    fila = next(
        f for f in range(pantalla.crud.tabla_widget.rowCount())
        if pantalla.crud.tabla_widget.item(f, 1).text() == "Aviso localidad"
    )
    pantalla.crud.tabla_widget.selectRow(fila)
    assert pantalla.texto_vista_previa.toPlainText() == "Estamos en Vicente López."


def test_contexto_localidad_pisa_al_vinculo_del_mensaje_general(qtbot, conn):
    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Olivos")
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Avisos", Descripcion="Aviso general", Mensaje="Estamos en {localidad}.", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    fila = next(
        f for f in range(pantalla.crud.tabla_widget.rowCount())
        if pantalla.crud.tabla_widget.item(f, 1).text() == "Aviso general"
    )
    pantalla.crud.tabla_widget.selectRow(fila)
    assert pantalla.texto_vista_previa.toPlainText() == "Estamos en ."

    indice = pantalla.combo_localidad_contexto.findData(id_localidad)
    pantalla.combo_localidad_contexto.setCurrentIndex(indice)
    assert pantalla.texto_vista_previa.toPlainText() == "Estamos en Olivos."


def test_dirigido_a_sustituye_nombre_apellido_y_tratamiento(qtbot, conn):
    id_profesional = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Pérez", NombrePila="Marta", Tratamiento="Lic.", Apodo="Marti",
    )
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Avisos", Descripcion="Saludo", Mensaje="Hola {tratamiento} {nombre} {apellido} ({apodo}).", Activo=1,
    )
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    fila = next(
        f for f in range(pantalla.crud.tabla_widget.rowCount())
        if pantalla.crud.tabla_widget.item(f, 1).text() == "Saludo"
    )
    pantalla.crud.tabla_widget.selectRow(fila)
    assert pantalla.texto_vista_previa.toPlainText() == "Hola    ()."

    indice = pantalla.combo_dirigido_a.findData(id_profesional)
    pantalla.combo_dirigido_a.setCurrentIndex(indice)
    assert pantalla.texto_vista_previa.toPlainText() == "Hola Lic. Marta Pérez (Marti)."


def test_cadena_de_foco_completa_buscar_a_eliminar(qtbot, conn):
    """Punto 95 (SistemaDF v0.11.2026.10): Buscar → Categoría → Dirigido
    a → Localidad → Edificio → Unidad → Consultorio → Copiar mensaje →
    Nuevo → Editar → Eliminar."""
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla._foco._orden == [
        pantalla.crud.campo_buscar, pantalla.combo_filtro, pantalla.combo_dirigido_a,
        pantalla.combo_localidad_contexto, pantalla.combo_edificio_contexto, pantalla.combo_unidad_contexto,
        pantalla.combo_consultorio_contexto, pantalla.boton_copiar,
        pantalla.crud.boton_nuevo, pantalla.crud.boton_editar, pantalla.crud.boton_eliminar,
    ]


def test_reiniciar_limpia_buscar_y_enfoca_el_primero(qtbot, conn):
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud.campo_buscar.setText("algo")

    pantalla.reiniciar()

    assert pantalla.crud.campo_buscar.text() == ""


def test_opciones_categoria_incluye_categorias_en_uso_no_registradas_en_listas_editables(conn):
    """Bug real reportado por la clienta: "ya habiendo una [categoría]
    cargada si despliego la cascada me tendría que ofrecer como opción
    esa categoría, tengo una pero pincho ahí y no aparece nada" — una
    categoría tipeada directo en un mensaje (Categoría es catálogo
    abierto, no pasa por "Listas editables") tiene que aparecer igual
    en la cascada de cualquier otro mensaje."""
    obtener_repositorio(conn, "MensajePredefinido").crear(Categoria="Saludo", Mensaje="Hola.", Activo=1)
    opciones = _opciones_categoria_mensaje(conn)
    assert ("Saludo", "Saludo") in opciones


def test_dialogo_nuevo_ofrece_en_la_cascada_una_categoria_ya_en_uso(qtbot, conn):
    obtener_repositorio(conn, "MensajePredefinido").crear(Categoria="Saludo", Mensaje="Hola.", Activo=1)
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.crud.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    combo_categoria = dialogo._entradas["Categoria"]
    assert combo_categoria.findText("Saludo") >= 0


def test_editar_categoria_de_un_mensaje_renombra_todos_los_que_la_compartian(qtbot, conn, monkeypatch):
    """Pedido explícito de la clienta: "en el hipotético caso de que
    quiero editar una categoría cargada dentro de un registro, por
    ejemplo algo que tenía como 'Saludo' ponerlo como 'Saludo inicial',
    a todos los items que tienen la categoría 'Saludo' afecta el mismo
    cambio"."""
    repo = obtener_repositorio(conn, "MensajePredefinido")
    repo.crear(Categoria="Saludo", Descripcion="Uno", Mensaje="Hola 1.", Activo=1)
    repo.crear(Categoria="Saludo", Descripcion="Dos", Mensaje="Hola 2.", Activo=1)
    repo.crear(Categoria="Despedida", Descripcion="Otra", Mensaje="Chau.", Activo=1)  # no tiene que tocarse

    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    id_uno = next(m["IdMensaje"] for m in repo.listar() if m["Descripcion"] == "Uno")
    fila = next(f for f in range(pantalla.crud.tabla_widget.rowCount())
                if pantalla.crud.tabla_widget.item(f, 0).data(Qt.ItemDataRole.UserRole) == id_uno)
    pantalla.crud.tabla_widget.selectRow(fila)

    def _dialogo_con_categoria_renombrada(self, *a, **k):
        self._entradas["Categoria"].setEditText("Saludo inicial")
        return _DialogoRegistro.DialogCode.Accepted

    monkeypatch.setattr("app.gui.crud_generico._DialogoRegistro.exec", _dialogo_con_categoria_renombrada)
    pantalla.crud._editar()

    categorias = {m["Descripcion"]: m["Categoria"] for m in repo.listar()}
    assert categorias["Uno"] == "Saludo inicial"
    assert categorias["Dos"] == "Saludo inicial"
    assert categorias["Otra"] == "Despedida"


def test_editar_categoria_sin_cambiarla_no_toca_a_nadie_mas(qtbot, conn, monkeypatch):
    repo = obtener_repositorio(conn, "MensajePredefinido")
    repo.crear(Categoria="Saludo", Descripcion="Uno", Mensaje="Hola 1.", Activo=1)
    repo.crear(Categoria="Saludo", Descripcion="Dos", Mensaje="Hola 2.", Activo=1)

    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud.tabla_widget.selectRow(0)

    def _dialogo_sin_cambios(self, *a, **k):
        return _DialogoRegistro.DialogCode.Accepted

    monkeypatch.setattr("app.gui.crud_generico._DialogoRegistro.exec", _dialogo_sin_cambios)
    pantalla.crud._editar()

    categorias = {m["Descripcion"]: m["Categoria"] for m in repo.listar()}
    assert categorias["Uno"] == "Saludo"
    assert categorias["Dos"] == "Saludo"


def test_columna_de_filtros_queda_fija_al_minimo_sin_cortar_dirigido_a(qtbot, conn):
    """Pedido explícito de la clienta: "reducí al mínimo la columna de
    los filtros para que no quede ninguna etiqueta o elemnto cortado".
    Caso real que puede cortarse sin este ajuste: "Dirigido a" es un
    combo EDITABLE (`habilitar_busqueda_profesional`) cuyo `sizeHint()`
    no crece con el nombre más largo cargado — si ningún otro combo de
    este panel necesita más ancho que ese nombre, el panel quedaría más
    angosto de lo que ese nombre necesita para mostrarse completo."""
    from app.gui.pantallas.mensajes_predefinidos import _ancho_necesario_combo

    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, NombrePila, Tratamiento) "
        "VALUES ('R', 'Viavattenee Rodriguez', 'Agustina Del Valle', 'Lic.')"
    )
    conn.commit()
    pantalla = _PanelMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)

    panel_filtros = pantalla.combo_filtro.parentWidget()
    assert panel_filtros.minimumWidth() == panel_filtros.maximumWidth()  # ancho fijo
    ancho_necesario_dirigido_a = _ancho_necesario_combo(pantalla.combo_dirigido_a)
    assert panel_filtros.width() >= ancho_necesario_dirigido_a
