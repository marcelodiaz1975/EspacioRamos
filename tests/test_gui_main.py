import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.archivos_y_listas import PantallaArchivosYListas
from gui_main import construir_secciones


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_todas_las_secciones_tienen_ayuda_cargada():
    secciones = construir_secciones()
    sin_ayuda = [s.nombre for s in secciones if not s.ayuda.strip()]
    assert sin_ayuda == []


def test_categorias_son_parametros_del_sistema_y_el_nombre_del_espacio_y_van_contiguas():
    """SistemaDF v0.11.2026.10, puntos 19/20: "Sistema" pasa a llamarse
    "Parámetros del sistema" y "Operativa diaria" pasa a mostrar el
    nombre del espacio configurado (en mayúsculas) — sin `conn`, o con
    `NombreEspacio` todavía sin configurar, cae al nombre default
    "Sistema DF" (pedido explícito de la clienta: una base recién
    instalada no tiene por qué mostrar el nombre de un negocio de
    ejemplo que no es el suyo). `VentanaPrincipal` arma un separador
    cada vez que la categoría cambia respecto de la sección anterior
    (no agrupa por nombre repetido en toda la lista) — así que las de
    una misma categoría tienen que quedar todas juntas, sin
    intercalarse con la otra."""
    secciones = construir_secciones()
    categorias = [s.categoria for s in secciones]
    assert set(categorias) == {"Parámetros del sistema", "SISTEMA DF"}
    cambios = sum(1 for a, b in zip(categorias, categorias[1:]) if a != b)
    assert cambios == 1  # un solo cambio de categoría en toda la lista


def test_categoria_del_espacio_usa_el_nombre_configurado(conn):
    """Con un nombre de espacio real cargado, la categoría lo refleja en
    mayúsculas en vez de caer al fallback default."""
    conn.execute("UPDATE Configuracion SET NombreEspacio = ? WHERE IdConfiguracion = 1", ("Consultorios del Sur",))
    conn.commit()
    secciones = construir_secciones(conn=conn)
    categorias = {s.categoria for s in secciones}
    assert "CONSULTORIOS DEL SUR" in categorias
    assert "SISTEMA DF" not in categorias


def test_panel_de_control_es_la_primera_seccion_de_la_categoria_del_espacio():
    """Punto 74: "Panel de control" pasa a ser el primero de la categoría
    del espacio (no de "Parámetros del sistema"), arriba de "Grilla y
    mensajería"."""
    secciones = construir_secciones()
    nombres_del_espacio = [s.nombre for s in secciones if s.categoria == "SISTEMA DF"]
    assert nombres_del_espacio[0] == "Panel de control"
    assert nombres_del_espacio[1] == "Grilla y mensajería"
    assert "Panel de control" not in [s.nombre for s in secciones if s.categoria == "Parámetros del sistema"]


def test_archivos_y_listas_recibe_la_lista_completa_de_secciones(qtbot, conn):
    """"Manual del usuario" (reubicado en Gestor de archivos del espacio,
    ver imagenes.py) sigue necesitando la lista completa de secciones
    para armar la ayuda contextual del manual."""
    secciones = construir_secciones()
    indice_archivos_y_listas = next(i for i, s in enumerate(secciones) if s.nombre == "Archivos y listas")

    pantalla = secciones[indice_archivos_y_listas].fabrica(conn)
    qtbot.addWidget(pantalla)

    assert isinstance(pantalla, PantallaArchivosYListas)
    assert len(pantalla.panel_gestor_archivos._secciones) == len(secciones)


def test_locale_espanol_tiene_la_semana_empezando_en_lunes(qtbot):
    """Pedido de la clienta: "que todos los selectores de fecha del
    sistema empiecen la semana en lunes, no en domingo". `gui_main.main()`
    fija `QLocale.setDefault(QLocale(QLocale.Language.Spanish))` antes de
    mostrar cualquier pantalla — no testeable invocando `main()` en sí
    (abre una base real y un diálogo de login, mismo criterio ya
    documentado para `showMaximized()`), así que esto confirma la pieza
    real: ese locale tiene `firstDayOfWeek() == Monday`, y un QDateEdit
    construido bajo ese locale por default arranca su calendario ahí."""
    from PySide6.QtCore import QLocale, Qt
    from PySide6.QtWidgets import QDateEdit

    locale_espanol = QLocale(QLocale.Language.Spanish)
    assert locale_espanol.firstDayOfWeek() == Qt.DayOfWeek.Monday

    anterior = QLocale.system()
    try:
        QLocale.setDefault(locale_espanol)
        campo = QDateEdit()
        campo.setCalendarPopup(True)
        qtbot.addWidget(campo)
        assert campo.calendarWidget().firstDayOfWeek() == Qt.DayOfWeek.Monday
    finally:
        QLocale.setDefault(anterior)
