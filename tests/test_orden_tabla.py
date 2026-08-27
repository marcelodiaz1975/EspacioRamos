from PySide6.QtWidgets import QTableWidget

from app.gui.widgets.orden_tabla import OrdenTabla


def _tabla(columnas=3):
    tabla = QTableWidget()
    tabla.setColumnCount(columnas)
    tabla.setHorizontalHeaderLabels([f"Col{i}" for i in range(columnas)])
    return tabla


def test_orden_tabla_arranca_sin_columna_elegida(qtbot):
    tabla = _tabla()
    llamadas = []
    orden = OrdenTabla(tabla, lambda: llamadas.append(1))
    assert orden.columna is None
    assert orden.ascendente is True
    assert llamadas == []


def test_click_en_columna_ordena_ascendente_y_avisa(qtbot):
    tabla = _tabla()
    llamadas = []
    orden = OrdenTabla(tabla, lambda: llamadas.append(1))
    tabla.horizontalHeader().sectionClicked.emit(1)
    assert orden.columna == 1
    assert orden.ascendente is True
    assert len(llamadas) == 1


def test_click_de_nuevo_en_la_misma_columna_invierte_el_sentido(qtbot):
    tabla = _tabla()
    orden = OrdenTabla(tabla, lambda: None)
    tabla.horizontalHeader().sectionClicked.emit(1)
    assert orden.ascendente is True
    tabla.horizontalHeader().sectionClicked.emit(1)
    assert orden.columna == 1
    assert orden.ascendente is False
    tabla.horizontalHeader().sectionClicked.emit(1)
    assert orden.ascendente is True


def test_click_en_otra_columna_reinicia_a_ascendente(qtbot):
    tabla = _tabla()
    orden = OrdenTabla(tabla, lambda: None)
    tabla.horizontalHeader().sectionClicked.emit(1)
    tabla.horizontalHeader().sectionClicked.emit(1)  # descendente
    assert orden.ascendente is False
    tabla.horizontalHeader().sectionClicked.emit(2)
    assert orden.columna == 2
    assert orden.ascendente is True


def test_reiniciar_vuelve_al_orden_por_defecto(qtbot):
    tabla = _tabla()
    orden = OrdenTabla(tabla, lambda: None)
    tabla.horizontalHeader().sectionClicked.emit(1)
    assert orden.columna == 1
    orden.reiniciar()
    assert orden.columna is None
    assert orden.ascendente is True


def test_reiniciar_sin_click_previo_no_falla(qtbot):
    tabla = _tabla()
    orden = OrdenTabla(tabla, lambda: None)
    orden.reiniciar()  # no hay nada que reiniciar, no debe romper
    assert orden.columna is None
