import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import hoja_estilos
from app.gui.main_window import Seccion, VentanaPrincipal
from app.negocio.seguridad import asegurar_permisos_pantalla
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _secciones():
    return [
        Seccion("Uno", lambda c: QWidget(), categoria="Principal", ayuda="Ayuda de Uno."),
        Seccion("Dos", lambda c: QWidget(), categoria="Principal"),
    ]


def test_barra_fecha_ficticia_oculta_por_defecto(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._barra_fecha_ficticia.isHidden() is True


def test_barra_fecha_ficticia_visible_cuando_esta_activo(qtbot, conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoFechaFicticia=1, FechaFicticia="2026-03-15")
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._barra_fecha_ficticia.isHidden() is False
    assert "2026-03-15" in ventana._barra_fecha_ficticia.text()


def test_barra_fecha_ficticia_se_actualiza_al_cambiar_de_pantalla(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._barra_fecha_ficticia.isHidden() is True

    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoFechaFicticia=1, FechaFicticia="2026-03-15")
    ventana._navegacion.setCurrentRow(2)  # 0 = separador, 1 = "Uno", 2 = "Dos"

    assert ventana._barra_fecha_ficticia.isHidden() is False


def test_barra_fecha_ficticia_activada_sin_fecha_no_se_muestra(qtbot, conn):
    """ModoFechaFicticia=1 sin FechaFicticia cargada: no hay nada que
    simular, no tiene sentido mostrar la barra."""
    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoFechaFicticia=1, FechaFicticia=None)
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._barra_fecha_ficticia.isHidden() is True


def test_sin_secciones_no_falla(qtbot, conn):
    ventana = VentanaPrincipal(conn, [])
    qtbot.addWidget(ventana)
    assert ventana._barra_fecha_ficticia.isHidden() is True


def test_barra_fecha_ficticia_es_un_qlabel(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert isinstance(ventana._barra_fecha_ficticia, QLabel)


def test_f1_muestra_ayuda_de_la_seccion_actual(qtbot, conn, monkeypatch):
    llamada = {}
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda parent, titulo, texto: llamada.update(titulo=titulo, texto=texto)),
    )
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)

    ventana._mostrar_ayuda()

    assert "Uno" in llamada["titulo"]
    assert llamada["texto"] == "Ayuda de Uno."


def test_f1_sin_ayuda_cargada_muestra_mensaje_generico(qtbot, conn, monkeypatch):
    llamada = {}
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda parent, titulo, texto: llamada.update(titulo=titulo, texto=texto)),
    )
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    ventana._navegacion.setCurrentRow(2)  # "Dos", sin ayuda cargada

    ventana._mostrar_ayuda()

    assert llamada["texto"]


# --------------------------------------------------------------- modo oscuro/claro

def test_tema_claro_por_defecto(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana.styleSheet() == hoja_estilos(False)


def test_tema_oscuro_cuando_esta_activado(qtbot, conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoOscuro=1)
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana.styleSheet() == hoja_estilos(True)


def test_tema_se_actualiza_al_cambiar_de_pantalla(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana.styleSheet() == hoja_estilos(False)

    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoOscuro=1)
    ventana._navegacion.setCurrentRow(2)

    assert ventana.styleSheet() == hoja_estilos(True)


# --------------------------------------------------------- badge de período

def test_badge_periodo_muestra_el_periodo_actual(qtbot, conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoFechaFicticia=1, FechaFicticia="2026-08-10")
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._badge_periodo.text() == "Período 08/2026"


def test_badge_periodo_se_actualiza_al_cambiar_de_pantalla(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    obtener_repositorio(conn, "Configuracion").actualizar(1, ModoFechaFicticia=1, FechaFicticia="2026-03-15")
    ventana._navegacion.setCurrentRow(2)
    assert ventana._badge_periodo.text() == "Período 03/2026"


def test_f1_sin_secciones_no_falla(qtbot, conn, monkeypatch):
    llamado = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: llamado.append(1)))
    ventana = VentanaPrincipal(conn, [])
    qtbot.addWidget(ventana)

    ventana._mostrar_ayuda()

    assert llamado == []


# --------------------------------------------------- filtrado por nivel de acceso


def _id_nivel(conn, nombre):
    return conn.execute("SELECT IdNivelAcceso FROM NivelAcceso WHERE Nombre = ?", (nombre,)).fetchone()["IdNivelAcceso"]


def test_sin_nivel_de_usuario_no_filtra_nada(qtbot, conn):
    """El default (`id_nivel_usuario=None`, el que usan todos los tests
    que no tienen nada que ver con Seguridad) muestra todas las
    secciones, sin necesitar login."""
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._navegacion.count() == 3  # separador + Uno + Dos


def test_nivel_operador_no_ve_pantalla_restringida_a_administrador(qtbot, conn):
    asegurar_permisos_pantalla(conn, ["Uno", "Dos"])
    conn.execute(
        "UPDATE PermisoPantalla SET IdNivelAcceso = ? WHERE NombrePantalla = 'Dos'", (_id_nivel(conn, "Administrador"),)
    )
    conn.commit()

    ventana = VentanaPrincipal(conn, _secciones(), id_nivel_usuario=_id_nivel(conn, "Operador"))
    qtbot.addWidget(ventana)

    nombres = [ventana._navegacion.item(i).text() for i in range(ventana._navegacion.count())]
    assert "Uno" in nombres
    assert "Dos" not in nombres


def test_nivel_administrador_ve_todas_las_pantallas(qtbot, conn):
    asegurar_permisos_pantalla(conn, ["Uno", "Dos"])
    conn.execute(
        "UPDATE PermisoPantalla SET IdNivelAcceso = ? WHERE NombrePantalla = 'Dos'", (_id_nivel(conn, "Administrador"),)
    )
    conn.commit()

    ventana = VentanaPrincipal(conn, _secciones(), id_nivel_usuario=_id_nivel(conn, "Administrador"))
    qtbot.addWidget(ventana)

    nombres = [ventana._navegacion.item(i).text() for i in range(ventana._navegacion.count())]
    assert "Uno" in nombres
    assert "Dos" in nombres


def test_ir_a_seccion_selecciona_la_fila_y_devuelve_el_widget(qtbot, conn):
    """#22: mecanismo genérico para que una pantalla salte a otra (ej.
    "Confirmar reserva" de Lista de espera -> Reservas)."""
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    ventana._navegacion.setCurrentRow(1)  # arranca en "Uno"

    widget = ventana.ir_a_seccion("Dos")

    assert isinstance(widget, QWidget)
    assert ventana._pila.currentWidget() is widget
    assert ventana._navegacion.currentItem().text() == "Dos"


def test_ir_a_seccion_inexistente_devuelve_none_sin_romper(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    ventana._navegacion.setCurrentRow(1)

    assert ventana.ir_a_seccion("No existe") is None
    assert ventana._navegacion.currentItem().text() == "Uno"  # no se movió


def test_al_abrir_arranca_en_panel_de_control_por_nombre_no_por_posicion(qtbot, conn):
    """#1.1 (GENERAL, "Correcciones para próxima versión"): tiene que
    arrancar en "Panel de control" aunque esa Seccion NO sea la primera
    de la lista (lo que pasaría, por ejemplo, tras el reordenamiento de
    menú que pide mover Panel de control de categoría)."""
    secciones = [
        Seccion("Otra pantalla", lambda c: QWidget(), categoria="X"),
        Seccion("Panel de control", lambda c: QWidget(), categoria="Y"),
        Seccion("Y otra más", lambda c: QWidget(), categoria="Y"),
    ]
    ventana = VentanaPrincipal(conn, secciones)
    qtbot.addWidget(ventana)
    assert ventana._navegacion.currentItem().text() == "Panel de control"


def test_categorias_arrancan_colapsadas_salvo_panel_de_control(qtbot, conn):
    """Punto 20: las dos categorías arrancan COLAPSADAS, "Panel de
    control" queda siempre visible sin importar el estado de la suya."""
    secciones = [
        Seccion("Panel de control", lambda c: QWidget(), categoria="Y"),
        Seccion("Y otra más", lambda c: QWidget(), categoria="Y"),
    ]
    ventana = VentanaPrincipal(conn, secciones)
    qtbot.addWidget(ventana)

    item_panel = next(
        ventana._navegacion.item(i) for i in range(ventana._navegacion.count()) if ventana._navegacion.item(i).text() == "Panel de control"
    )
    item_otra = next(
        ventana._navegacion.item(i) for i in range(ventana._navegacion.count()) if ventana._navegacion.item(i).text() == "Y otra más"
    )
    assert item_panel.isHidden() is False
    assert item_otra.isHidden() is True


def test_click_en_separador_despliega_y_vuelve_a_colapsar(qtbot, conn):
    """Punto 20: clickear el separador de una categoría la despliega; un
    segundo click la vuelve a colapsar."""
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    separador = ventana._navegacion.item(0)
    item_uno = ventana._navegacion.item(1)
    assert item_uno.isHidden() is True

    ventana._al_click_item_navegacion(separador)
    assert item_uno.isHidden() is False
    assert ventana._navegacion.item(0).text().startswith("▾")

    ventana._al_click_item_navegacion(separador)
    assert item_uno.isHidden() is True
    assert ventana._navegacion.item(0).text().startswith("▸")


def test_click_en_item_normal_no_toca_el_colapso(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    item_uno = ventana._navegacion.item(1)

    ventana._al_click_item_navegacion(item_uno)  # no es un separador

    assert item_uno.isHidden() is True  # sigue colapsado, no rompió nada


def test_ir_a_seccion_expande_la_categoria_si_estaba_colapsada(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    item_dos = next(ventana._navegacion.item(i) for i in range(ventana._navegacion.count()) if ventana._navegacion.item(i).text() == "Dos")
    assert item_dos.isHidden() is True

    widget = ventana.ir_a_seccion("Dos")

    assert widget is not None
    assert item_dos.isHidden() is False


def test_etiqueta_de_funciones_f1_f2_f3(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._etiqueta_funciones.text() == "F1 – Ayuda / F2 – Calculadora / F3 – Reiniciar solapa"


def test_f2_abre_una_sola_calculadora_y_f2_de_nuevo_no_abre_otra(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())
    qtbot.addWidget(ventana)
    assert ventana._calculadora is None

    ventana._abrir_calculadora()
    primera = ventana._calculadora
    assert primera is not None

    ventana._abrir_calculadora()
    assert ventana._calculadora is primera  # no abrió una segunda

    primera.close()
    qtbot.wait(50)  # WA_DeleteOnClose agenda un deleteLater, no es sincrónico
    assert ventana._calculadora is None  # se liberó al cerrarla con la cruz


def test_panel_mas_interno_baja_por_tabwidgets_anidados(qtbot, conn):
    from PySide6.QtWidgets import QTabWidget

    hoja_interna = QWidget()
    tab_interno = QTabWidget()
    tab_interno.addTab(hoja_interna, "Interna")

    tab_externo = QTabWidget()
    tab_externo.addTab(tab_interno, "Externa")

    secciones = [Seccion("Compuesta", lambda c: tab_externo, categoria="X")]
    ventana = VentanaPrincipal(conn, secciones)
    qtbot.addWidget(ventana)

    assert ventana._panel_mas_interno() is hoja_interna


def test_f3_llama_reiniciar_del_panel_activo_si_lo_tiene(qtbot, conn):
    llamadas = []

    class _PanelConReset(QWidget):
        def reiniciar(self):
            llamadas.append(True)

    panel = _PanelConReset()
    secciones = [Seccion("Con reset", lambda c: panel, categoria="X")]
    ventana = VentanaPrincipal(conn, secciones)
    qtbot.addWidget(ventana)

    ventana._reiniciar_solapa_activa()

    assert llamadas == [True]


def test_f3_sin_metodo_reiniciar_no_rompe(qtbot, conn):
    ventana = VentanaPrincipal(conn, _secciones())  # QWidget liso, sin reiniciar()
    qtbot.addWidget(ventana)
    ventana._reiniciar_solapa_activa()  # no debe lanzar
