"""Pantalla de carga mostrada entre el login y la ventana principal.

Pedido explícito de la clienta: "Cuando esté cargando la base de datos
luego de poner el usuario y contraseña que se ponga una pantalla con
el ícono... grande en el centro de la pantalla... y abajo la leyenda
'SistemaDF {versión}'". `VentanaPrincipal.__init__` arma las ~18
pantallas del sistema de una sola vez, no de forma perezosa al hacer
clic (`seccion.fabrica(conn)` corre para cada una dentro del loop de
construcción) — ese armado es lo que puede tardar un momento
perceptible, no la apertura de la conexión SQLite en sí (ya resuelta
mucho antes, en el login). Por eso esta pantalla se muestra justo
después de un login exitoso y se cierra recién cuando `VentanaPrincipal`
ya está lista para mostrarse — cubre ese tramo, no el de antes del
login (que no tiene ninguna carga pesada propia).

Se arma sobre `QSplashScreen` (la clase estándar de Qt para esto, con
`finish(ventana)` ya resuelto para cerrarse sola apenas la ventana de
destino se muestra) en vez de un diálogo propio — no hace falta ningún
mecanismo de cierre manual."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen

from app.gui.estilos import COLOR_NIVEL_1_OSCURO
from app.gui.recursos import RUTA_ICONO
from app.version import NOMBRE_Y_VERSION

_ANCHO = 420
_ALTO = 340
_TAMANO_ICONO = 200


def crear_pantalla_carga() -> QSplashScreen:
    """Arma el `QPixmap` (ícono grande centrado + leyenda debajo) y lo
    envuelve en un `QSplashScreen` listo para `.show()`."""
    lienzo = QPixmap(_ANCHO, _ALTO)
    lienzo.fill(Qt.GlobalColor.white)

    pintor = QPainter(lienzo)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    icono = QPixmap(str(RUTA_ICONO)).scaled(
        _TAMANO_ICONO, _TAMANO_ICONO,
        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )
    x_icono = (_ANCHO - icono.width()) // 2
    y_icono = 40
    pintor.drawPixmap(x_icono, y_icono, icono)

    pintor.setPen(COLOR_NIVEL_1_OSCURO)
    fuente = QFont()
    fuente.setPointSize(14)
    fuente.setBold(True)
    pintor.setFont(fuente)
    y_texto = y_icono + icono.height() + 30
    pintor.drawText(
        0, y_texto, _ANCHO, 40,
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        NOMBRE_Y_VERSION,
    )
    pintor.end()

    pantalla = QSplashScreen(lienzo)
    pantalla.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    return pantalla
