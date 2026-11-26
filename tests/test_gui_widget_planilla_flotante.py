import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QMessageBox, QTableWidgetSelectionRange

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.widgets.planilla_flotante import _ALINEACION_QT, PlanillaFlotante
from app.negocio.planilla_flotante import leer_celdas


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def _instancia_compartida(qapp):
    """Una sola instancia para TODO este archivo de test — ver el
    docstring de `PlanillaFlotante`: crear y destruir repetidas veces un
    `QTableWidget` de ~480 celdas dentro del mismo proceso dispara un bug
    real de PySide6/shiboken ("Fatal Python error: none_dealloc" — lo
    confirmamos reproduciéndolo con un test por instancia: ~13 ciclos ya
    alcanzan). Los tests de este archivo comparten esta ÚNICA instancia
    y la reconectan a la base propia de cada test (fixture `planilla`,
    abajo) en vez de reconstruir la ventana — mismo criterio que usa la
    app real, que tampoco crea nunca una segunda (ver `main_window.py`,
    `_abrir_calculadora`)."""
    return PlanillaFlotante(init_database(":memory:"))


@pytest.fixture
def planilla(_instancia_compartida, conn):
    """Reconecta la instancia compartida del módulo a la base aislada de
    ESTE test (`conn`, un archivo propio por `tmp_path`), sin reconstruir
    la ventana — ver `_instancia_compartida`."""
    p = _instancia_compartida
    p.conn = conn
    p._celdas = leer_celdas(conn)
    p._texto_pendiente = None
    p._recalcular_textos()
    # `_combinar_celdas` (sin persistencia propia, ver su docstring)
    # puede dejar un span de un test anterior sobre la misma instancia
    # compartida — se vuelve a (0, 0) sin combinar para que los tests
    # de combinar/descombinar no dependan del orden en que corren.
    p.tabla.setSpan(0, 0, 1, 1)
    # `setCurrentCell(0, 0)` no dispara `currentCellChanged` si la celda
    # actual (de un test anterior, sobre la misma instancia compartida)
    # ya era (0, 0) — se fija el estado a mano para no depender de la
    # señal, en vez de poner `_fila_actual`/`_columna_actual` en `None`.
    p._fila_actual, p._columna_actual = 0, 0
    p.tabla.setCurrentCell(0, 0)
    p._cargar_barra_formula()
    return p


def _escribir(planilla, fila, columna, texto):
    """Simula tipear en la barra de fórmula estando parado en esa celda y
    confirmar con Enter (mismo camino que usa la clienta: la grilla no es
    editable directamente, ver el docstring del módulo)."""
    planilla.tabla.setCurrentCell(fila, columna)
    planilla.barra_formula.setText(texto)
    planilla._marcar_pendiente(texto)
    planilla.barra_formula.returnPressed.emit()


def test_arranca_vacia_sin_nada_guardado(planilla):
    # Celda nunca escrita: no tiene `QTableWidgetItem` propio (creación
    # perezosa, ver `_recalcular_textos`) — vacía es "sin ítem", no un
    # ítem con texto vacío.
    assert planilla.tabla.item(0, 0) is None
    assert planilla.etiqueta_celda.text() == "A1"


def test_escribir_en_una_celda_la_muestra_y_la_persiste(planilla, conn):
    _escribir(planilla, 0, 0, "10")
    assert planilla.tabla.item(0, 0).text() == "10"
    assert leer_celdas(conn)["A1"]["contenido"] == "10"


def test_confirmar_con_enter_baja_el_foco_una_fila(planilla):
    _escribir(planilla, 0, 0, "10")
    assert planilla._fila_actual == 1
    assert planilla._columna_actual == 0


def test_formula_con_referencia_a_otra_celda_calcula_el_resultado(planilla):
    _escribir(planilla, 0, 0, "10")  # A1
    _escribir(planilla, 0, 1, "=A1*2")  # B1
    assert planilla.tabla.item(0, 1).text() == "20"


def test_nota_suelta_no_se_calcula_aunque_parezca_una_cuenta(planilla):
    _escribir(planilla, 0, 0, "10+5 (nota)")
    assert planilla.tabla.item(0, 0).text() == "10+5 (nota)"


def test_cambiar_de_celda_sin_enter_tambien_confirma_lo_tipeado(planilla):
    planilla.tabla.setCurrentCell(0, 0)
    planilla.barra_formula.setText("7")
    planilla._marcar_pendiente("7")
    planilla.tabla.setCurrentCell(1, 1)
    assert planilla.tabla.item(0, 0).text() == "7"


def test_negrita_se_aplica_a_la_celda_actual_y_persiste(planilla, conn):
    planilla.tabla.setCurrentCell(0, 0)
    planilla.boton_negrita.setChecked(True)
    planilla._alternar_negrita()
    assert planilla._estilo_en(0, 0)["negrita"] is True
    assert leer_celdas(conn)["A1"]["negrita"] is True


def test_color_de_texto_se_aplica_y_persiste(planilla, conn, monkeypatch):
    planilla.tabla.setCurrentCell(0, 0)
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda parent=None: QColor("#ff0000")))
    planilla._elegir_color_texto()
    assert planilla._estilo_en(0, 0)["color_texto"] == "#ff0000"
    assert leer_celdas(conn)["A1"]["color_texto"] == "#ff0000"


def test_color_invalido_no_aplica_nada(planilla, conn, monkeypatch):
    planilla.tabla.setCurrentCell(0, 0)
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda parent=None: QColor()))
    planilla._elegir_color_fondo()
    assert leer_celdas(conn) == {}


def test_formato_numero_aplica_separador_de_miles_y_dos_decimales(planilla):
    _escribir(planilla, 0, 0, "1234.5")
    planilla.tabla.setCurrentCell(0, 0)
    planilla.boton_formato_numero.setChecked(True)
    planilla._alternar_formato_numero()
    assert planilla.tabla.item(0, 0).text() == "1.234,50"


def test_formato_se_aplica_a_toda_la_seleccion_de_varias_celdas(planilla):
    _escribir(planilla, 0, 0, "1")
    _escribir(planilla, 0, 1, "2")
    planilla.tabla.setRangeSelected(QTableWidgetSelectionRange(0, 0, 0, 1), True)
    planilla.boton_negrita.setChecked(True)
    planilla._alternar_negrita()
    assert planilla._estilo_en(0, 0)["negrita"] is True
    assert planilla._estilo_en(0, 1)["negrita"] is True


def test_delete_borra_el_contenido_sin_tocar_el_formato(planilla):
    _escribir(planilla, 0, 0, "10")
    planilla.tabla.setCurrentCell(0, 0)
    planilla.boton_negrita.setChecked(True)
    planilla._alternar_negrita()
    planilla._borrar_contenido_seleccion()
    assert planilla.tabla.item(0, 0).text() == ""
    assert planilla._estilo_en(0, 0)["negrita"] is True


def test_vaciar_todo_borra_contenido_y_formato_de_toda_la_planilla(planilla, conn):
    """No debe recrear los ítems de la grilla (ver `_vaciar_todo` en el
    widget) — solo confirmamos el resultado visible/persistido, no cómo
    se logra, pero este es justo el caso que reprodujo el bug de
    shiboken durante el desarrollo de esta pantalla."""
    _escribir(planilla, 0, 0, "10")
    _escribir(planilla, 5, 5, "20")
    planilla._vaciar_todo()
    assert planilla.tabla.item(0, 0).text() == ""
    assert planilla.tabla.item(5, 5).text() == ""
    assert leer_celdas(conn) == {}


def test_vaciar_todo_cancelado_no_borra_nada(planilla, monkeypatch):
    _escribir(planilla, 0, 0, "10")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    planilla._vaciar_todo()
    assert planilla.tabla.item(0, 0).text() == "10"


def test_tipear_en_la_tabla_sin_tocar_la_barra_arranca_edicion_en_la_celda(planilla, qtbot):
    """Pedido explícito: "que al navegar con el cursor se pueda empezar
    a escribir directamente en la celda" — tipear con la grilla
    enfocada (no la barra de fórmula) arranca la edición igual. No se
    chequea `hasFocus()` (necesitaría la ventana realmente visible y
    activa, frágil bajo Qt offscreen) — lo que importa es que el texto
    tipeado llegue a la barra de fórmula y de ahí se confirme igual."""
    planilla.tabla.setCurrentCell(0, 0)
    qtbot.keyClick(planilla.tabla, Qt.Key.Key_7)
    assert planilla.barra_formula.text() == "7"
    qtbot.keyClick(planilla.barra_formula, Qt.Key.Key_Return)
    assert planilla.tabla.item(0, 0).text() == "7"


def test_tipear_en_la_celda_pisa_el_contenido_anterior(planilla):
    _escribir(planilla, 0, 0, "10")
    planilla.tabla.setCurrentCell(0, 0)
    planilla._empezar_a_escribir("9")
    assert planilla.barra_formula.text() == "9"


def test_tipear_varias_teclas_seguidas_se_siguen_acumulando_en_la_barra(planilla, qtbot):
    """Solo la PRIMERA tecla la intercepta la grilla — a partir de ahí
    el foco ya está en la barra de fórmula y el resto lo recibe esta de
    forma nativa (sin nada especial que hacer en el `eventFilter`)."""
    planilla.tabla.setCurrentCell(0, 0)
    qtbot.keyClick(planilla.tabla, Qt.Key.Key_7)
    qtbot.keyClick(planilla.barra_formula, Qt.Key.Key_8)
    assert planilla.barra_formula.text() == "78"


def test_cambiar_de_celda_carga_la_barra_de_formula_con_lo_guardado(planilla):
    _escribir(planilla, 0, 0, "=1+1")
    planilla.tabla.setCurrentCell(0, 0)
    assert planilla.etiqueta_celda.text() == "A1"
    assert planilla.barra_formula.text() == "=1+1"


def test_cambiar_de_celda_selecciona_todo_el_contenido_de_la_barra(planilla):
    """Pedido explícito: "que el texto que esté cargado al pinchar se
    seleccione todo por si quiero volver a escribir arriba y borrar el
    contenido con ese acto"."""
    _escribir(planilla, 0, 0, "hola")
    planilla.tabla.setCurrentCell(1, 1)
    planilla.tabla.setCurrentCell(0, 0)
    assert planilla.barra_formula.selectedText() == "hola"


def test_alineacion_por_defecto_texto_izquierda_numero_derecha(planilla):
    """Pedido explícito: "que por defecto lo que es texto se justifique
    a la izquierda y los valores a la derecha"."""
    _escribir(planilla, 0, 0, "una nota")
    _escribir(planilla, 0, 1, "123")
    _escribir(planilla, 0, 2, "=1+1")
    assert planilla._estilo_en(0, 0)["alineacion"] == "izquierda"
    assert planilla._estilo_en(0, 1)["alineacion"] == "derecha"
    assert planilla._estilo_en(0, 2)["alineacion"] == "derecha"


def test_boton_de_alineacion_pisa_el_default_y_persiste(planilla, conn):
    _escribir(planilla, 0, 0, "123")  # numérico, default "derecha"
    planilla.tabla.setCurrentCell(0, 0)
    planilla._alinear("izquierda")
    assert planilla._estilo_en(0, 0)["alineacion"] == "izquierda"
    assert leer_celdas(conn)["A1"]["alineacion"] == "izquierda"


def test_boton_de_alineacion_centro_se_aplica_a_toda_la_seleccion(planilla):
    _escribir(planilla, 0, 0, "1")
    _escribir(planilla, 0, 1, "2")
    planilla.tabla.setRangeSelected(QTableWidgetSelectionRange(0, 0, 0, 1), True)
    planilla._alinear("centro")
    assert planilla._estilo_en(0, 0)["alineacion"] == "centro"
    assert planilla._estilo_en(0, 1)["alineacion"] == "centro"


def test_contenido_cargado_al_construir_desde_lo_ya_guardado(planilla, conn):
    """"Que se conserven" (pedido explícito, persistencia permanente) —
    una instancia nueva arranca leyendo lo que ya había en la base, no en
    blanco. Única excepción en este archivo a "una sola instancia para
    todo el módulo" (ver `_instancia_compartida`): hace falta una
    SEGUNDA de verdad para probar justamente esto — una sola construcción
    extra en toda la suite no alcanza a disparar el bug de shiboken
    (confirmado aparte con un script offscreen: una instancia extra, sin
    ciclos de destrucción, no tiene ningún problema)."""
    _escribir(planilla, 2, 2, "=3*3")
    segunda = PlanillaFlotante(conn)
    assert segunda.tabla.item(2, 2).text() == "9"


def test_cerrar_con_la_cruz_solo_esconde_no_destruye(planilla):
    planilla.show()
    assert planilla.isVisible()
    planilla.close()
    assert not planilla.isVisible()
    # Sigue siendo el mismo objeto Qt vivo, no uno destruido por Qt.
    assert planilla.tabla.rowCount() > 0


# --------------------------------------------------- "modo señalar" (navegación tipo Excel)

def test_flecha_abajo_en_formula_concatena_referencia_de_celda(planilla, qtbot):
    """Pedido explícito, con su propio ejemplo: "empiezo a escribir en
    '+45+' en C1, presiono cursor abajo, ahí quedaría '+45+C2'"."""
    planilla.tabla.setCurrentCell(0, 2)  # C1
    planilla.barra_formula.setText("+45+")
    planilla._marcar_pendiente("+45+")
    qtbot.keyClick(planilla.barra_formula, Qt.Key.Key_Down)
    assert planilla.barra_formula.text() == "+45+C2"


def test_flechas_consecutivas_mueven_la_misma_referencia_en_vez_de_agregar(planilla, qtbot):
    """Sin tipear nada entre una flecha y la siguiente, la referencia ya
    insertada se MUEVE (no se agrega una nueva) — "a medida que sigo
    poniendo signos me sigue concatenando celdas"."""
    planilla.tabla.setCurrentCell(0, 2)  # C1
    planilla.barra_formula.setText("+45+")
    planilla._marcar_pendiente("+45+")
    qtbot.keyClick(planilla.barra_formula, Qt.Key.Key_Down)
    qtbot.keyClick(planilla.barra_formula, Qt.Key.Key_Down)
    assert planilla.barra_formula.text() == "+45+C3"  # no "+45+C2+C3"


def test_tipear_entre_flechas_fija_la_referencia_y_agrega_una_nueva(planilla, qtbot):
    """Tipear algo real entre dos flechas "fija" la referencia anterior
    — la próxima flecha agrega una referencia NUEVA en vez de mover la
    última."""
    planilla.tabla.setCurrentCell(0, 2)  # C1
    planilla.barra_formula.setText("+45+")
    planilla._marcar_pendiente("+45+")
    qtbot.keyClick(planilla.barra_formula, Qt.Key.Key_Down)  # "+45+C2"
    qtbot.keyClick(planilla.barra_formula, Qt.Key.Key_Plus)  # tipeo real: fija C2
    qtbot.keyClick(planilla.barra_formula, Qt.Key.Key_Down)  # nueva referencia desde C2
    assert planilla.barra_formula.text() == "+45+C2+C3"


def test_flecha_sin_prefijo_de_formula_no_dispara_el_modo_senalar(planilla, qtbot):
    """Una flecha en la barra de fórmula solo entra en "modo señalar" si
    el texto ya es una fórmula ("=" o "+") — de lo contrario el cursor
    de texto se mueve de forma nativa, sin tocar el contenido."""
    planilla.tabla.setCurrentCell(0, 0)
    planilla.barra_formula.setText("hola")
    planilla._marcar_pendiente("hola")
    qtbot.keyClick(planilla.barra_formula, Qt.Key.Key_Down)
    assert planilla.barra_formula.text() == "hola"


# ------------------------------------------------------------------- combinar/descombinar

def test_boton_combinar_combina_la_seleccion(planilla):
    planilla.tabla.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 1), True)
    planilla._combinar_celdas()
    assert planilla.tabla.rowSpan(0, 0) == 2
    assert planilla.tabla.columnSpan(0, 0) == 2


def test_boton_combinar_es_el_mismo_boton_para_combinar_y_descombinar(planilla):
    """Pedido explícito: "un botón de combinar celdas, que es botón
    también descombine"."""
    planilla.tabla.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 1), True)
    planilla._combinar_celdas()
    assert planilla.tabla.rowSpan(0, 0) == 2

    planilla.tabla.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 1), True)
    planilla._combinar_celdas()
    assert planilla.tabla.rowSpan(0, 0) == 1
    assert planilla.tabla.columnSpan(0, 0) == 1


def test_sin_seleccion_combinar_no_hace_nada(planilla):
    planilla.tabla.clearSelection()
    planilla._combinar_celdas()  # no debe romper sin ninguna celda seleccionada


# --------------------------------------------------------------------------- copiar/pegar

def test_copiar_y_pegar_una_sola_celda(planilla):
    """Pedido explícito: "los botones de copiar y pegar, para copiar
    celdas o rangos de celdas"."""
    _escribir(planilla, 0, 0, "10")
    planilla.tabla.setCurrentCell(0, 0)
    planilla._copiar()
    planilla.tabla.setCurrentCell(2, 2)
    planilla._pegar()
    assert planilla.tabla.item(2, 2).text() == "10"


def test_copiar_y_pegar_copia_tambien_el_formato(planilla):
    planilla.tabla.setCurrentCell(0, 0)
    planilla.boton_negrita.setChecked(True)
    planilla._alternar_negrita()
    planilla._copiar()
    planilla.tabla.setCurrentCell(1, 1)
    planilla._pegar()
    assert planilla._estilo_en(1, 1)["negrita"] is True


def test_copiar_y_pegar_un_rango_mantiene_la_forma(planilla):
    """Copiar un rango de 2x1 y pegarlo en otro lado reproduce la misma
    forma relativa, anclada en la celda donde se pega."""
    _escribir(planilla, 0, 0, "1")
    _escribir(planilla, 1, 0, "2")
    planilla.tabla.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 0), True)
    planilla._copiar()
    planilla.tabla.setCurrentCell(5, 5)
    planilla._pegar()
    assert planilla.tabla.item(5, 5).text() == "1"
    assert planilla.tabla.item(6, 5).text() == "2"


def test_pegar_cerca_del_borde_descarta_las_celdas_que_quedan_afuera(planilla):
    """Pegar un rango que se saldría de la grilla no rompe nada — las
    celdas fuera de rango se descartan sin más."""
    _escribir(planilla, 0, 0, "1")
    _escribir(planilla, 1, 0, "2")
    planilla.tabla.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 0), True)
    planilla._copiar()
    ultima_fila = planilla.tabla.rowCount() - 1
    planilla.tabla.setCurrentCell(ultima_fila, 0)
    planilla._pegar()  # no debe lanzar ninguna excepción
    assert planilla.tabla.item(ultima_fila, 0).text() == "1"


def test_pegar_sin_copiar_antes_no_hace_nada(planilla):
    """Portapapeles vacío a propósito (en vez de solo confiar en que
    ningún test anterior haya copiado algo sobre la misma instancia
    compartida, ver `_instancia_compartida`) — confirma que pegar sin
    nada copiado no cambia lo que ya hubiera en la celda, sea lo que
    sea."""
    planilla._portapapeles = []
    planilla.tabla.setCurrentCell(0, 0)
    item_antes = planilla.tabla.item(0, 0)
    texto_antes = item_antes.text() if item_antes is not None else None
    planilla._pegar()
    item_despues = planilla.tabla.item(0, 0)
    texto_despues = item_despues.text() if item_despues is not None else None
    assert texto_despues == texto_antes


# ------------------------------------------------------------------------ ancho de botones

def test_todos_los_botones_de_estilo_tienen_el_mismo_ancho(planilla):
    """Pedido explícito: "que los botones queden en una sola fila,
    reducí el ancho de los mismos" — mismo criterio del resto del
    sistema, ancho fijo único para todos."""
    botones = (
        planilla.boton_copiar, planilla.boton_pegar, planilla.boton_negrita, planilla.boton_color_texto,
        planilla.boton_color_fondo, planilla.boton_formato_numero, planilla.boton_alinear_izquierda,
        planilla.boton_alinear_centro, planilla.boton_alinear_derecha, planilla.boton_combinar,
        planilla.boton_vaciar_todo,
    )
    anchos = {b.width() for b in botones}
    assert len(anchos) == 1


# ------------------------------------------------------------------------------- alineación

def test_alineacion_vertical_siempre_centralizada(planilla):
    """Pedido explícito: "la alineación vertical siempre
    centralizada" — sin importar la alineación horizontal elegida."""
    for alineacion in ("izquierda", "centro", "derecha"):
        assert _ALINEACION_QT[alineacion] & Qt.AlignmentFlag.AlignVCenter
