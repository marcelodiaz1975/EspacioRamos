import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
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
