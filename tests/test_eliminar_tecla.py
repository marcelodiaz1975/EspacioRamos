import gc
import weakref

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget

from app.gui.widgets.eliminar_tecla import instalar_eliminar_con_tecla


def _tabla(qtbot) -> QTableWidget:
    tabla = QTableWidget()
    tabla.setColumnCount(2)
    tabla.setRowCount(1)
    qtbot.addWidget(tabla)
    return tabla


def test_tecla_delete_dispara_la_accion(qtbot):
    tabla = _tabla(qtbot)
    llamadas = []
    # Referencia débil (mismo motivo que OrdenTabla): el caller tiene que
    # sostener `accion`, igual que sostendría un método atado de un panel
    # que sigue vivo — un lambda anónimo sin esta variable se recolecta
    # casi enseguida y la tecla dejaría de disparar nada.
    accion = lambda: llamadas.append(1)  # noqa: E731
    instalar_eliminar_con_tecla(tabla, accion)
    qtbot.keyClick(tabla, Qt.Key.Key_Delete)
    assert llamadas == [1]


def test_otra_tecla_no_dispara_la_accion(qtbot):
    tabla = _tabla(qtbot)
    llamadas = []
    accion = lambda: llamadas.append(1)  # noqa: E731
    instalar_eliminar_con_tecla(tabla, accion)
    qtbot.keyClick(tabla, Qt.Key.Key_Backspace)
    assert llamadas == []


def test_no_sostiene_vivo_al_dueno_del_metodo_atado(qtbot):
    """Mismo criterio que OrdenTabla (app/gui/widgets/orden_tabla.py):
    `accion` suele ser un método atado del panel dueño de la tabla —
    guardarlo fuerte crearía un ciclo panel -> este objeto -> panel."""

    class _Panel:
        def _eliminar(self) -> None:
            pass

    tabla = _tabla(qtbot)
    panel = _Panel()
    referencia_debil = weakref.ref(panel)
    instalar_eliminar_con_tecla(tabla, panel._eliminar)

    del panel
    gc.collect()
    assert referencia_debil() is None


def test_delete_sin_accion_viva_no_rompe(qtbot):
    class _Panel:
        def _eliminar(self) -> None:
            pass

    tabla = _tabla(qtbot)
    panel = _Panel()
    instalar_eliminar_con_tecla(tabla, panel._eliminar)
    del panel
    gc.collect()
    qtbot.keyClick(tabla, Qt.Key.Key_Delete)  # no debe lanzar ninguna excepción
