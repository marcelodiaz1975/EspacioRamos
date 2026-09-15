from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import COLOR_ROJO
from app.gui.widgets.resumen_saldo import item_monto, partes_resumen, texto_resumen
from app.negocio.formato import formatear_moneda
from app.repositorio.registro import obtener_repositorio

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


def test_partes_resumen_devuelve_las_mismas_partes_que_texto_resumen_junta():
    """`texto_resumen` (un solo renglón, usado en Pagos) y
    `partes_resumen` (una lista, usada en Cargos especiales para
    mostrar cada dato en su propia línea) tienen que devolver
    exactamente lo mismo, solo que sin/con unir con " - "."""
    conn = init_database(":memory:")
    sembrar_valores_por_defecto(conn)
    id_profesional = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lo Veci", SaldoCuentaActual=1000, SaldoCuentaAnterior=-200,
    )
    conn.commit()

    partes = partes_resumen(
        conn, id_profesional, entidad_imputado="CargoEspecial", etiqueta_imputado="Cargos especiales",
    )
    assert len(partes) == 4
    assert partes[0].startswith("Saldo actual:")
    assert partes[1].startswith("Saldo anterior:")
    assert partes[2].startswith("Cargos especiales imputados al mes actual:")
    assert partes[3].startswith("Cargos especiales imputados al mes anterior:")
    assert " - ".join(partes) == texto_resumen(
        conn, id_profesional, entidad_imputado="CargoEspecial", etiqueta_imputado="Cargos especiales",
    )
    conn.close()
