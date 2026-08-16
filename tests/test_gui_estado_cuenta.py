import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.estado_cuenta import PantallaEstadoCuenta
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_profesional(conn, apellido="Gómez", saldo_actual=100.0, saldo_anterior=50.0):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido=apellido, SaldoCuentaActual=saldo_actual, SaldoCuentaAnterior=saldo_anterior,
    )


def test_sin_profesionales_no_falla(qtbot, conn):
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.etiqueta_saldo_actual.text() == "Saldo actual: —"


def test_muestra_saldos_del_profesional_seleccionado(qtbot, conn):
    _crear_profesional(conn, saldo_actual=1234.5, saldo_anterior=678.9)
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.etiqueta_saldo_actual.text() == "Saldo actual: $ 1,234.50"
    assert pantalla.etiqueta_saldo_anterior.text() == "Saldo anterior: $ 678.90"


def test_lista_liquidaciones_del_profesional(qtbot, conn):
    id_prof = _crear_profesional(conn)
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_prof, Periodo="2026-07", FechaEmision="2026-07-05", MontoGenerado=1000,
        EstadoEnvio="Enviada", NombreArchivo="julio.pdf",
    )
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_prof, Periodo="2026-08", FechaEmision="2026-08-05", MontoGenerado=1100,
        EstadoEnvio="No enviada", NombreArchivo="agosto.pdf",
    )
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.tabla_liquidaciones.rowCount() == 2
    assert pantalla.tabla_liquidaciones.item(0, 0).text() == "2026-08"  # más reciente primero
    assert pantalla.tabla_liquidaciones.item(1, 0).text() == "2026-07"


def test_lista_pagos_del_profesional(qtbot, conn):
    id_prof = _crear_profesional(conn)
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_prof, Fecha="2026-08-01", Monto=500, MedioPago="Transferencia a cta Celeste",
    )
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.tabla_pagos.rowCount() == 1
    assert pantalla.tabla_pagos.item(0, 1).text() == "$ 500.00"


def test_lista_cargos_especiales_del_profesional(qtbot, conn):
    id_prof = _crear_profesional(conn)
    obtener_repositorio(conn, "CargoEspecial").crear(
        IdProfesional=id_prof, Tipo="Débito", Concepto="Depósito llave", Monto=2000,
    )
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.tabla_cargos.rowCount() == 1
    assert pantalla.tabla_cargos.item(0, 1).text() == "Depósito llave"


def test_no_mezcla_datos_de_otros_profesionales(qtbot, conn):
    id_prof1 = _crear_profesional(conn, apellido="Gómez")
    id_prof2 = _crear_profesional(conn, apellido="Pérez")
    obtener_repositorio(conn, "CargoEspecial").crear(IdProfesional=id_prof2, Tipo="Débito", Concepto="Ajeno", Monto=1)
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)

    indice_gomez = pantalla.combo_profesional.findData(id_prof1)
    pantalla.combo_profesional.setCurrentIndex(indice_gomez)
    assert pantalla.tabla_cargos.rowCount() == 0


def test_cambiar_de_profesional_actualiza_las_tablas(qtbot, conn):
    id_prof1 = _crear_profesional(conn, apellido="Gómez")
    id_prof2 = _crear_profesional(conn, apellido="Pérez")
    obtener_repositorio(conn, "CargoEspecial").crear(IdProfesional=id_prof2, Tipo="Débito", Concepto="De Pérez", Monto=1)
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)

    indice_perez = pantalla.combo_profesional.findData(id_prof2)
    pantalla.combo_profesional.setCurrentIndex(indice_perez)
    assert pantalla.tabla_cargos.rowCount() == 1

    indice_gomez = pantalla.combo_profesional.findData(id_prof1)
    pantalla.combo_profesional.setCurrentIndex(indice_gomez)
    assert pantalla.tabla_cargos.rowCount() == 0


def test_actualizar_conserva_la_seleccion(qtbot, conn):
    id_prof1 = _crear_profesional(conn, apellido="Gómez")
    _crear_profesional(conn, apellido="Pérez")
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)

    indice_gomez = pantalla.combo_profesional.findData(id_prof1)
    pantalla.combo_profesional.setCurrentIndex(indice_gomez)

    pantalla.actualizar()

    assert pantalla.combo_profesional.currentData() == id_prof1
