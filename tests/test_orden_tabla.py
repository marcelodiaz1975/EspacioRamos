import gc
import weakref

from PySide6.QtWidgets import QTableWidget

from app.gui.widgets.orden_tabla import OrdenTabla, clave_orden_codigo


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
    # OrdenTabla guarda una referencia débil a al_cambiar (evita el ciclo
    # panel -> OrdenTabla -> panel) — el caller tiene que sostenerla como
    # sostendría cualquier método atado a un panel que sigue vivo.
    al_cambiar = lambda: llamadas.append(1)  # noqa: E731
    orden = OrdenTabla(tabla, al_cambiar)
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


def test_no_sostiene_vivo_al_dueno_del_metodo_atado(qtbot):
    """El caso real de uso: `al_cambiar` es un método atado del panel
    dueño de la tabla (`OrdenTabla(self.tabla, self.actualizar)`). Guardar
    esa referencia fuerte crearía un ciclo panel -> OrdenTabla -> panel
    que solo el recolector cíclico de Python puede romper — y si ese
    recolector corre mientras Qt ya viene destruyendo el árbol de widgets
    (como pasa al cerrar muchos paneles seguidos), terminaba tocando un
    wrapper ya muerto del lado C++ y reventando el proceso (segfault).
    Esto confirma que OrdenTabla no extiende la vida del panel más allá
    de lo que ya haga cualquier otra referencia."""

    class _Panel:
        def actualizar(self) -> None:
            pass

    tabla = _tabla()
    panel = _Panel()
    referencia_debil = weakref.ref(panel)
    OrdenTabla(tabla, panel.actualizar)

    del panel
    gc.collect()
    assert referencia_debil() is None


def test_clave_orden_codigo_ordena_por_numero_completo_no_por_digito():
    """Pedido explícito de la clienta: "X1, X10, X11, X2..." (alfabético
    puro) NO va; "X1, X2, X3... X10, X11... X234" (número completo) sí."""
    codigos = ["X10", "X2", "X1", "X29", "X234", "X3", "X35", "X11", "X25", "X4"]
    ordenados = sorted(codigos, key=clave_orden_codigo)
    assert ordenados == ["X1", "X2", "X3", "X4", "X10", "X11", "X25", "X29", "X35", "X234"]


def test_clave_orden_codigo_agrupa_primero_por_prefijo_alfabetico():
    codigos = ["A10", "R2", "A2", "R10"]
    ordenados = sorted(codigos, key=clave_orden_codigo)
    assert ordenados == ["A2", "A10", "R2", "R10"]


def test_clave_orden_codigo_funciona_con_texto_despues_del_codigo():
    """Varias pantallas muestran "R1 - Lic. Juan Pérez" en la misma
    celda (código + nombre) — el orden natural tiene que mirar solo el
    código del principio, no romperse por el texto que sigue."""
    textos = ["R10 - Lic. Ana Gómez", "R2 - Dr. Juan Pérez"]
    ordenados = sorted(textos, key=clave_orden_codigo)
    assert ordenados == ["R2 - Dr. Juan Pérez", "R10 - Lic. Ana Gómez"]


def test_clave_orden_codigo_sin_numero_ordena_por_texto():
    assert clave_orden_codigo("ABC") == ("ABC", -1, "ABC")


def test_clave_orden_codigo_vacio_o_none_no_rompe():
    assert clave_orden_codigo(None) == ("", -1, "")
    assert clave_orden_codigo("") == ("", -1, "")
