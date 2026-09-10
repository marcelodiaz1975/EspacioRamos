from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.gui.estilos import COLOR_ROJO
from app.gui.widgets.resumen_saldo import item_monto
from app.negocio.formato import formatear_moneda

_ALINEACION_DERECHA = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


def test_item_monto_alinea_a_la_derecha():
    item = item_monto(1500)
    assert item.text() == formatear_moneda(1500)
    assert item.textAlignment() == _ALINEACION_DERECHA


def test_item_monto_negativo_se_colorea_en_rojo_y_alinea_a_la_derecha():
    item = item_monto(-500)
    assert item.text() == formatear_moneda(-500)
    assert item.textAlignment() == _ALINEACION_DERECHA
    assert item.foreground().color() == QColor(COLOR_ROJO)
