import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.crud_generico import _DialogoRegistro
from app.gui.pantallas.mensajes_predefinidos import PantallaMensajesPredefinidos
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


def test_pantalla_se_arma_con_los_sembrados(qtbot, conn):
    pantalla = PantallaMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.crud.tabla_widget.rowCount() == len(obtener_repositorio(conn, "MensajePredefinido").listar())


def test_pantalla_tiene_tres_campos_libres(qtbot, conn):
    pantalla = PantallaMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.crud.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_pantalla_tiene_campo_localidad_antes_de_edificio(qtbot, conn):
    pantalla = PantallaMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.crud.campos]
    assert nombres.index("IdLocalidad") < nombres.index("IdEdificio")


def test_categoria_es_combo_editable_con_valores_de_listas_editables(qtbot, conn):
    obtener_repositorio(conn, "ListasEditables").crear(TipoLista="CategoriaMensaje", Valor="Recordatorios", Orden=0)
    pantalla = PantallaMensajesPredefinidos(conn)
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
    quedar en blanco."""
    _crear_consultorio(conn)
    pantalla = PantallaMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.crud.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    assert dialogo._entradas["IdEdificio"].itemData(0) is None
    assert dialogo._entradas["IdUnidad"].itemData(0) is None
    assert dialogo._entradas["IdConsultorio"].itemData(0) is None
    assert dialogo.valores()["IdEdificio"] is None
    assert dialogo.valores()["IdUnidad"] is None
    assert dialogo.valores()["IdConsultorio"] is None


def test_dirigido_a_por_defecto_es_nadie_en_particular(qtbot, conn):
    pantalla = PantallaMensajesPredefinidos(conn)
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
    pantalla = PantallaMensajesPredefinidos(conn)
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
    pantalla = PantallaMensajesPredefinidos(conn)
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
    pantalla = PantallaMensajesPredefinidos(conn)
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
    pantalla = PantallaMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.crud.tabla_widget
    assert not any(tabla.isRowHidden(f) for f in range(tabla.rowCount()))


def test_seleccionar_fila_arma_vista_previa_con_variables_sustituidas(qtbot, conn):
    id_consultorio = _crear_consultorio(conn)
    obtener_repositorio(conn, "MensajePredefinido").crear(
        Categoria="Recordatorios", Descripcion="Aviso", IdConsultorio=id_consultorio,
        Mensaje="Te esperamos en {edificio}, {unidad}, consultorio {consultorio}.", Activo=1,
    )
    pantalla = PantallaMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)

    fila = next(
        f for f in range(pantalla.crud.tabla_widget.rowCount())
        if pantalla.crud.tabla_widget.item(f, 1).text() == "Aviso"
    )
    pantalla.crud.tabla_widget.selectRow(fila)

    assert pantalla.texto_vista_previa.toPlainText() == "Te esperamos en Torre Norte, 7mo, consultorio 3."


def test_copiar_mensaje_usa_portapapeles(qtbot, conn, monkeypatch):
    pantalla = PantallaMensajesPredefinidos(conn)
    qtbot.addWidget(pantalla)
    pantalla.texto_vista_previa.setPlainText("texto de prueba")

    copiado = []
    monkeypatch.setattr(
        "app.gui.pantallas.mensajes_predefinidos.QGuiApplication.clipboard",
        staticmethod(lambda: type("_C", (), {"setText": lambda self, t: copiado.append(t)})()),
    )
    pantalla._copiar_mensaje()
    assert copiado == ["texto de prueba"]
