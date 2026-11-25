import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import COLOR_ROJO
from app.gui.widgets.resumen_saldo import item_monto, partes_resumen, saldo_actual_mostrado, texto_resumen
from app.negocio.dias import periodo_actual
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


def test_saldo_actual_mostrado_combina_anterior_y_el_bucket_del_periodo():
    """Redefinición de "Saldo actual" (pedido explícito de la clienta,
    caso testigo Vanesa Moreno — ver CLAUDE.md): pasa a ser el resultado
    EN VIVO de la cuenta, Saldo anterior + lo propio del período en
    curso, no el bucket solo."""
    conn = init_database(":memory:")
    sembrar_valores_por_defecto(conn)
    profesional = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Moreno", SaldoCuentaActual=207, SaldoCuentaAnterior=-396,
    )
    conn.commit()
    fila = obtener_repositorio(conn, "Profesional").obtener(profesional)

    assert saldo_actual_mostrado(conn, fila) == pytest.approx(-189)
    conn.close()


def test_saldo_actual_mostrado_de_un_a_combina_anterior_con_la_aislada_en_vivo():
    """Para categoría A, lo "propio del período en curso" sigue siendo
    el cálculo en vivo (`movimiento_periodo_aislada`, no hay liquidación
    mensual que acredite `SaldoCuentaActual`) — ahora sumado a Saldo
    anterior igual que para el resto de las categorías."""
    conn = init_database(":memory:")
    sembrar_valores_por_defecto(conn)
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="PB")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraAisladaActual=1000,
    )
    profesional = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="A", Apellido="Diaz", SaldoCuentaAnterior=-300,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=profesional, IdConsultorio=id_consultorio, Fecha=f"{periodo_actual(conn)}-10",
        HoraInicio=10, HoraFin=11, Estado="Confirmada", AplicaRecargo=0,
    )
    conn.commit()
    fila = obtener_repositorio(conn, "Profesional").obtener(profesional)

    assert saldo_actual_mostrado(conn, fila) == pytest.approx(1000 - 300)
    conn.close()
