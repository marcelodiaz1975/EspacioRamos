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


def test_centro_mensajeria_lista_profesionales_categoria_r(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, SaldoCuentaAnterior) VALUES ('R', 'Gómez', 0)")
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.rowCount() == 1
    assert "Gómez" in pantalla.tabla.item(0, 0).text()


def test_centro_mensajeria_seleccionar_fila_muestra_mensaje(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, SaldoCuentaAnterior) VALUES ('R', 'Gómez', 0)")
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)
    assert "Gómez" in pantalla.texto_mensaje.toPlainText() or pantalla.texto_mensaje.toPlainText() != ""


def test_centro_mensajeria_cambia_a_categoria_aislada(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('A', 'Pérez')")
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_categoria.setCurrentIndex(1)  # categoría A
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
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, SaldoCuentaAnterior) VALUES ('R', 'Gómez', 0)")
    conn.commit()
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)

    item = pantalla.tabla.item(0, 3)
    assert not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def test_check_enviada_habilitado_con_liquidacion_no_enviada(qtbot, conn):
    id_profesional = conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, SaldoCuentaAnterior) VALUES ('R', 'Gómez', 0)"
    ).lastrowid
    periodo = periodo_actual(conn)
    obtener_repositorio(conn, "LiquidacionEmitida").crear(IdProfesional=id_profesional, Periodo=periodo)
    conn.commit()

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)

    item = pantalla.tabla.item(0, 3)
    assert item.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert item.checkState() == Qt.CheckState.Unchecked


def test_marcar_enviada_actualiza_estado_y_situacion(qtbot, conn):
    id_profesional = conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, SaldoCuentaAnterior) VALUES ('R', 'Gómez', 0)"
    ).lastrowid
    periodo = periodo_actual(conn)
    id_liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").crear(IdProfesional=id_profesional, Periodo=periodo)
    conn.commit()

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)

    pantalla.tabla.item(0, 3).setCheckState(Qt.CheckState.Checked)

    liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liquidacion)
    assert liquidacion["EstadoEnvio"] == "Enviada"
    assert pantalla.tabla.item(0, 2).text() == _ETIQUETA_SITUACION_2
    assert pantalla.tabla.item(0, 3).checkState() == Qt.CheckState.Checked


def test_marcar_enviada_es_reversible(qtbot, conn):
    id_profesional = conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, SaldoCuentaAnterior) VALUES ('R', 'Gómez', 0)"
    ).lastrowid
    periodo = periodo_actual(conn)
    id_liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_profesional, Periodo=periodo, EstadoEnvio="Enviada",
    )
    conn.commit()

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.item(0, 3).checkState() == Qt.CheckState.Checked

    pantalla.tabla.item(0, 3).setCheckState(Qt.CheckState.Unchecked)

    liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liquidacion)
    assert liquidacion["EstadoEnvio"] == "No enviada"


def test_check_enviada_no_aparece_para_categoria_aislada(qtbot, conn):
    id_profesional = conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('A', 'Pérez')"
    ).lastrowid
    obtener_repositorio(conn, "LiquidacionEmitida").crear(IdProfesional=id_profesional, Periodo=periodo_actual(conn))
    conn.commit()

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_categoria.setCurrentIndex(1)  # categoría A

    item = pantalla.tabla.item(0, 3)
    assert not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable)


_ETIQUETA_SITUACION_2 = "2 — Liquidación enviada"
