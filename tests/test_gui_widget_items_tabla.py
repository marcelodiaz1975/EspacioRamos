from PySide6.QtCore import Qt

from app.gui.widgets.items_tabla import item_numero

_ALINEACION_DERECHA = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


def test_item_numero_alinea_a_la_derecha():
    item = item_numero("$ 1.234,00")
    assert item.text() == "$ 1.234,00"
    assert item.textAlignment() == _ALINEACION_DERECHA
