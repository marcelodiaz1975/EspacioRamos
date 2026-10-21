from PySide6.QtGui import QColor
from PySide6.QtWidgets import QSplashScreen

from app.gui.widgets.pantalla_carga import _ALTO, _ANCHO, crear_pantalla_carga
from app.version import NOMBRE_Y_VERSION


def test_crear_pantalla_carga_devuelve_un_qsplashscreen(qtbot):
    pantalla = crear_pantalla_carga()
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla, QSplashScreen)


def test_el_pixmap_tiene_el_tamano_esperado(qtbot):
    pantalla = crear_pantalla_carga()
    qtbot.addWidget(pantalla)
    pixmap = pantalla.pixmap()
    assert pixmap.width() == _ANCHO
    assert pixmap.height() == _ALTO


def test_el_icono_se_pinto_en_el_centro_arriba(qtbot):
    pantalla = crear_pantalla_carga()
    qtbot.addWidget(pantalla)
    imagen = pantalla.pixmap().toImage()
    # En el centro horizontal, a la altura donde debería estar el
    # ícono, tiene que haber algún pixel que NO sea blanco puro (el
    # fondo del lienzo) — confirma que el ícono se dibujó ahí y no
    # quedó un lienzo en blanco.
    color = QColor(imagen.pixel(_ANCHO // 2, 100))
    assert (color.red(), color.green(), color.blue()) != (255, 255, 255)


def test_la_leyenda_se_pinto_debajo_del_icono(qtbot):
    pantalla = crear_pantalla_carga()
    qtbot.addWidget(pantalla)
    imagen = pantalla.pixmap().toImage()

    def _fila_tiene_contenido(y):
        return any(
            QColor(imagen.pixel(x, y)).getRgb()[:3] != (255, 255, 255)
            for x in range(0, _ANCHO, 2)
        )

    # Sin asumir una fila exacta de texto (depende de la métrica real
    # de la fuente): barre la mitad inferior del lienzo (debajo de
    # donde termina el ícono, ~232px) buscando alguna fila con
    # contenido — confirma que la leyenda se dibujó en algún lado de
    # esa franja, no que el lienzo quedó en blanco ahí.
    assert any(_fila_tiene_contenido(y) for y in range(240, _ALTO))


def test_version_actual_queda_representada_en_el_nombre_del_modulo(qtbot):
    # No se puede leer texto de un QPixmap sin OCR — se confirma en
    # cambio que `pantalla_carga` arma su leyenda a partir de
    # `NOMBRE_Y_VERSION` (fuente única de versión del programa), no de
    # un string propio hardcodeado, inspeccionando el código fuente.
    import inspect

    from app.gui.widgets import pantalla_carga

    codigo = inspect.getsource(pantalla_carga)
    assert "NOMBRE_Y_VERSION" in codigo
    assert NOMBRE_Y_VERSION  # sanity: la constante existe y no está vacía
