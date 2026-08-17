import pytest
from PySide6.QtCore import Qt

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.mensajeria import CentroMensajeria
from app.negocio.dias import periodo_actual
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _set_filtro(pantalla, clave: str) -> None:
    indice = pantalla.combo_filtro.findData(clave)
    assert indice >= 0, f"filtro desconocido: {clave}"
    pantalla.combo_filtro.setCurrentIndex(indice)


def _crear_profesional(conn, categoria="R", apellido="Gómez", saldo=0.0):
    return conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, SaldoCuentaAnterior) VALUES (?, ?, ?)",
        (categoria, apellido, saldo),
    ).lastrowid


def test_centro_mensajeria_lista_profesionales_categoria_r(qtbot, conn):
    _crear_profesional(conn)
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.rowCount() == 1
    assert "Gómez" in pantalla.tabla.item(0, 0).text()


def test_centro_mensajeria_seleccionar_fila_muestra_mensaje(qtbot, conn):
    _crear_profesional(conn)
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    pantalla.tabla.selectRow(0)
    assert "Gómez" in pantalla.texto_mensaje.toPlainText() or pantalla.texto_mensaje.toPlainText() != ""


def test_centro_mensajeria_cambia_a_categoria_aislada(qtbot, conn):
    _crear_profesional(conn, categoria="A", apellido="Pérez")
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 2).text() == "Detalle de reserva"


def test_centro_mensajeria_boton_grupal_llena_texto(qtbot, conn):
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla._mostrar_mensaje_grupal()
    assert "AVISOS VARIOS" in pantalla.texto_mensaje.toPlainText()


def test_centro_mensajeria_usa_periodo_actual_por_defecto(qtbot, conn):
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.campo_periodo.text() == periodo_actual(conn)


def test_check_enviada_deshabilitado_sin_liquidacion_emitida(qtbot, conn):
    _crear_profesional(conn)
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    item = pantalla.tabla.item(0, 3)
    assert not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def test_check_enviada_habilitado_con_liquidacion_no_enviada(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    periodo = periodo_actual(conn)
    obtener_repositorio(conn, "LiquidacionEmitida").crear(IdProfesional=id_profesional, Periodo=periodo)
    conn.commit()

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    item = pantalla.tabla.item(0, 3)
    assert item.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert item.checkState() == Qt.CheckState.Unchecked


def test_marcar_enviada_actualiza_estado_y_situacion(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    periodo = periodo_actual(conn)
    id_liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").crear(IdProfesional=id_profesional, Periodo=periodo)
    conn.commit()

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.item(0, 3).setCheckState(Qt.CheckState.Checked)

    liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liquidacion)
    assert liquidacion["EstadoEnvio"] == "Enviada"
    assert pantalla.tabla.item(0, 2).text() == _ETIQUETA_SITUACION_2
    assert pantalla.tabla.item(0, 3).checkState() == Qt.CheckState.Checked


def test_marcar_enviada_es_reversible(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    periodo = periodo_actual(conn)
    id_liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_profesional, Periodo=periodo, EstadoEnvio="Enviada",
    )
    conn.commit()

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.item(0, 3).checkState() == Qt.CheckState.Checked

    pantalla.tabla.item(0, 3).setCheckState(Qt.CheckState.Unchecked)

    liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liquidacion)
    assert liquidacion["EstadoEnvio"] == "No enviada"


def test_check_enviada_no_aparece_para_categoria_aislada(qtbot, conn):
    id_profesional = _crear_profesional(conn, categoria="A", apellido="Pérez")
    obtener_repositorio(conn, "LiquidacionEmitida").crear(IdProfesional=id_profesional, Periodo=periodo_actual(conn))
    conn.commit()

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")

    item = pantalla.tabla.item(0, 3)
    assert not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable)


# --------------------------------------------------------------- filtros (6.2)

def test_filtro_con_deuda_es_el_default(qtbot, conn):
    _crear_profesional(conn, apellido="SinDeuda", saldo=0)
    _crear_profesional(conn, apellido="ConDeuda", saldo=500)
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.combo_filtro.currentData() == "con_deuda"
    assert pantalla.tabla.rowCount() == 1
    assert "ConDeuda" in pantalla.tabla.item(0, 0).text()


def test_filtro_todos_incluye_regulares_y_aisladas(qtbot, conn):
    _crear_profesional(conn, categoria="R", apellido="Regular")
    _crear_profesional(conn, categoria="A", apellido="Aislada")
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.rowCount() == 2


def test_filtro_solo_regulares(qtbot, conn):
    _crear_profesional(conn, categoria="R", apellido="Regular")
    _crear_profesional(conn, categoria="A", apellido="Aislada")
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "regulares")
    assert pantalla.tabla.rowCount() == 1
    assert "Regular" in pantalla.tabla.item(0, 0).text()


def test_filtro_solo_aisladas(qtbot, conn):
    _crear_profesional(conn, categoria="R", apellido="Regular")
    _crear_profesional(conn, categoria="A", apellido="Aislada")
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    assert pantalla.tabla.rowCount() == 1
    assert "Aislada" in pantalla.tabla.item(0, 0).text()


def test_filtro_solo_con_plan(qtbot, conn):
    id_con_plan = _crear_profesional(conn, apellido="ConPlan")
    _crear_profesional(conn, apellido="SinPlan")
    obtener_repositorio(conn, "PlanPago").crear(
        IdProfesional=id_con_plan, MontoRefinanciado=1000, MontoTotalAPagar=1000,
        CantidadCuotas=2, ImportePorCuota=500, MesAnoInicio=periodo_actual(conn), Estado="Activo",
    )
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "con_plan")
    assert pantalla.tabla.rowCount() == 1
    assert "ConPlan" in pantalla.tabla.item(0, 0).text()


def test_filtro_liquidacion_enviada(qtbot, conn):
    id_enviada = _crear_profesional(conn, apellido="Enviada")
    _crear_profesional(conn, apellido="SinEnviar")
    periodo = periodo_actual(conn)
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_enviada, Periodo=periodo, EstadoEnvio="Enviada",
    )
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "liq_enviada")
    assert pantalla.tabla.rowCount() == 1
    assert "Enviada" in pantalla.tabla.item(0, 0).text()


def test_filtro_liquidacion_sin_enviar(qtbot, conn):
    id_enviada = _crear_profesional(conn, apellido="Enviada")
    _crear_profesional(conn, apellido="SinEnviar")
    periodo = periodo_actual(conn)
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_enviada, Periodo=periodo, EstadoEnvio="Enviada",
    )
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "liq_sin_enviar")
    assert pantalla.tabla.rowCount() == 1
    assert "SinEnviar" in pantalla.tabla.item(0, 0).text()


# ------------------------------------------------------------------- orden (6.2)

def test_orden_por_dias_desde_ultimo_pago_descendente(qtbot, conn):
    id_reciente = _crear_profesional(conn, apellido="PagoReciente", saldo=100)
    id_antiguo = _crear_profesional(conn, apellido="PagoAntiguo", saldo=100)
    hoy = periodo_actual(conn) + "-15"
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_reciente, Fecha=hoy, Monto=100)
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_antiguo, Fecha="2020-01-01", Monto=100)
    conn.commit()

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "con_deuda")

    nombres = [pantalla.tabla.item(i, 0).text() for i in range(pantalla.tabla.rowCount())]
    assert nombres.index("PagoAntiguo (PagoAntiguo)") < nombres.index("PagoReciente (PagoReciente)")


def test_orden_nunca_pago_va_primero(qtbot, conn):
    _crear_profesional(conn, apellido="NuncaPago", saldo=100)
    id_pago_alguna_vez = _crear_profesional(conn, apellido="PagoAlgunaVez", saldo=100)
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_pago_alguna_vez, Fecha="2020-01-01", Monto=100,
    )
    conn.commit()

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "con_deuda")

    nombres = [pantalla.tabla.item(i, 0).text() for i in range(pantalla.tabla.rowCount())]
    assert nombres.index("NuncaPago (NuncaPago)") < nombres.index("PagoAlgunaVez (PagoAlgunaVez)")


def test_orden_a_igualdad_de_dias_por_monto_adeudado_descendente(qtbot, conn):
    _crear_profesional(conn, apellido="DeudaAlta", saldo=2000)
    _crear_profesional(conn, apellido="DeudaBaja", saldo=100)
    conn.commit()

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "con_deuda")

    nombres = [pantalla.tabla.item(i, 0).text() for i in range(pantalla.tabla.rowCount())]
    assert nombres.index("DeudaAlta (DeudaAlta)") < nombres.index("DeudaBaja (DeudaBaja)")


_ETIQUETA_SITUACION_2 = "2 — Liquidación enviada"
