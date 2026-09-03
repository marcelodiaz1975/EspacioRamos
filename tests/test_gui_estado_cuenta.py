import pytest
from PySide6.QtCore import Qt

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import COLOR_ROJO
from app.gui.pantallas.estado_cuenta import PantallaEstadoCuenta
from app.negocio.formato import formatear_moneda
from app.negocio.pagos import registrar_pago
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    connection.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-09-05' WHERE IdConfiguracion = 1"
    )
    yield connection
    connection.close()


def _crear_profesional(conn, apellido="Gómez", saldo_actual=100.0, saldo_anterior=50.0, id_codigo=None):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido=apellido, SaldoCuentaActual=saldo_actual,
        SaldoCuentaAnterior=saldo_anterior, IdCodigo=id_codigo,
    )


def _seleccionar_profesional(pantalla, id_profesional):
    pantalla.combo_profesional.setCurrentIndex(pantalla.combo_profesional.findData(id_profesional))


def test_sin_profesionales_no_falla(qtbot, conn):
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.etiqueta_datos_profesional.text() == "Saldo actual: — - Saldo anterior: —"


def test_muestra_saldos_del_profesional_seleccionado(qtbot, conn):
    """Por defecto (solapa Liquidaciones activa) el resumen solo trae
    saldo actual/anterior, con signo real y rojo si es negativo."""
    _crear_profesional(conn, saldo_actual=1234.5, saldo_anterior=-678.9)
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.etiqueta_datos_profesional.text() == (
        'Saldo actual: <span style="color:black;">$ 1.234,50</span> - '
        f'Saldo anterior: <span style="color:{COLOR_ROJO};">-$ 678,90</span>'
    )


def test_pagos_imputados_al_mes_actual_y_anterior_solo_en_solapa_pagos(qtbot, conn):
    """Confirmado por la clienta: los pagos (con signo negativo, tal como
    se guardan) se muestran con su signo real y en rojo si son negativos —
    no en valor absoluto — y solo aparecen en el resumen cuando la solapa
    Pagos está activa."""
    id_prof = _crear_profesional(conn)
    registrar_pago(conn, id_profesional=id_prof, monto=-12000, medio_pago="Transferencia", periodo_imputado="2026-09")
    registrar_pago(conn, id_profesional=id_prof, monto=-5000, medio_pago="Transferencia", periodo_imputado="2026-08")
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)
    assert "Pagos imputados" not in pantalla.etiqueta_datos_profesional.text()

    pantalla.pestanas.setCurrentWidget(pantalla.tabla_pagos)
    texto = pantalla.etiqueta_datos_profesional.text()
    assert f'Pagos imputados al mes actual: <span style="color:{COLOR_ROJO};">-$ 12.000,00</span>' in texto
    assert f'Pagos imputados al mes anterior: <span style="color:{COLOR_ROJO};">-$ 5.000,00</span>' in texto


def test_cargos_especiales_imputados_al_mes_actual_y_anterior_solo_en_esa_solapa(qtbot, conn):
    """Misma lógica que Pagos, ahora para Cargos especiales: signo real,
    rojo si es negativo, y solo aparece con esa solapa activa."""
    id_prof = _crear_profesional(conn)
    obtener_repositorio(conn, "CargoEspecial").crear(
        IdProfesional=id_prof, Tipo="Débito", Concepto="Ajuste", Monto=8000,
        Fecha="2026-09-01", PeriodoImputado="2026-09",
    )
    obtener_repositorio(conn, "CargoEspecial").crear(
        IdProfesional=id_prof, Tipo="Crédito", Concepto="Bonificación", Monto=-3000,
        Fecha="2026-08-01", PeriodoImputado="2026-08",
    )
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)
    assert "Cargos especiales imputados" not in pantalla.etiqueta_datos_profesional.text()

    pantalla.pestanas.setCurrentWidget(pantalla.tabla_cargos)
    texto = pantalla.etiqueta_datos_profesional.text()
    assert 'Cargos especiales imputados al mes actual: <span style="color:black;">$ 8.000,00</span>' in texto
    assert (
        f'Cargos especiales imputados al mes anterior: <span style="color:{COLOR_ROJO};">-$ 3.000,00</span>'
        in texto
    )


def test_combo_profesional_usa_formato_canonico(qtbot, conn):
    _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.combo_profesional.currentText() == "R1 - Lo Veci"


def test_combo_profesional_busca_por_codigo_o_nombre(qtbot, conn):
    """Además del formato canónico, el filtro del completer tiene que matchear
    en cualquier parte del texto (no solo desde el principio) para que buscar
    por nombre encuentre resultados aunque el código vaya primero."""
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)
    completador = pantalla.combo_profesional.completer()
    assert completador.filterMode() == Qt.MatchFlag.MatchContains
    assert completador.caseSensitivity() == Qt.CaseSensitivity.CaseInsensitive


def test_texto_invalido_vuelve_al_formato_de_la_seleccion_vigente(qtbot, conn):
    _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)
    pantalla.combo_profesional.setEditText("texto suelto que no matchea")
    pantalla.combo_profesional.lineEdit().editingFinished.emit()
    assert pantalla.combo_profesional.currentText() == "R1 - Lo Veci"


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
    assert pantalla.tabla_liquidaciones.item(0, 2).text() == formatear_moneda(1100)


def test_tabla_pagos_columnas_y_formato_igual_a_registrar_pago(qtbot, conn):
    id_prof = _crear_profesional(conn)
    registrar_pago(conn, id_profesional=id_prof, monto=-500, medio_pago="Transferencia a cta Celeste", periodo_imputado="2026-09")
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)

    assert [pantalla.tabla_pagos.horizontalHeaderItem(i).text() for i in range(pantalla.tabla_pagos.columnCount())] == [
        "Fecha de carga", "Período imputado", "Monto", "Medio de pago", "Cuenta receptora",
        "Saldo anterior", "Nuevo saldo", "Registro modificado", "Es ajuste",
    ]
    assert pantalla.tabla_pagos.rowCount() == 1
    assert pantalla.tabla_pagos.item(0, 2).text() == "-$ 500,00"
    assert pantalla.tabla_pagos.item(0, 3).text() == "Transferencia a cta Celeste"
    assert pantalla.tabla_pagos.item(0, 7).text() == "No"
    assert pantalla.tabla_pagos.item(0, 8).text() == "No"


def test_tabla_cargos_columnas_y_formato_igual_a_cargos_especiales(qtbot, conn):
    id_prof = _crear_profesional(conn)
    obtener_repositorio(conn, "CargoEspecial").crear(
        IdProfesional=id_prof, Tipo="Débito", Concepto="Depósito llave", Monto=2000,
        Fecha="2026-09-02", PeriodoImputado="2026-09",
    )
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)

    assert [pantalla.tabla_cargos.horizontalHeaderItem(i).text() for i in range(pantalla.tabla_cargos.columnCount())] == [
        "Fecha", "Tipo", "Concepto", "Monto", "Período imputado",
    ]
    assert pantalla.tabla_cargos.rowCount() == 1
    assert pantalla.tabla_cargos.item(0, 1).text() == "Débito"
    assert pantalla.tabla_cargos.item(0, 2).text() == "Depósito llave"
    assert pantalla.tabla_cargos.item(0, 3).text() == formatear_moneda(2000)
    assert pantalla.tabla_cargos.item(0, 4).text() == "2026-09"


def test_no_mezcla_datos_de_otros_profesionales(qtbot, conn):
    id_prof1 = _crear_profesional(conn, apellido="Gómez")
    id_prof2 = _crear_profesional(conn, apellido="Pérez")
    obtener_repositorio(conn, "CargoEspecial").crear(IdProfesional=id_prof2, Tipo="Débito", Concepto="Ajeno", Monto=1)
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)

    _seleccionar_profesional(pantalla, id_prof1)
    assert pantalla.tabla_cargos.rowCount() == 0


def test_cambiar_de_profesional_actualiza_las_tablas(qtbot, conn):
    id_prof1 = _crear_profesional(conn, apellido="Gómez")
    id_prof2 = _crear_profesional(conn, apellido="Pérez")
    obtener_repositorio(conn, "CargoEspecial").crear(IdProfesional=id_prof2, Tipo="Débito", Concepto="De Pérez", Monto=1)
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)

    _seleccionar_profesional(pantalla, id_prof2)
    assert pantalla.tabla_cargos.rowCount() == 1

    _seleccionar_profesional(pantalla, id_prof1)
    assert pantalla.tabla_cargos.rowCount() == 0


def test_actualizar_conserva_la_seleccion(qtbot, conn):
    id_prof1 = _crear_profesional(conn, apellido="Gómez")
    _crear_profesional(conn, apellido="Pérez")
    pantalla = PantallaEstadoCuenta(conn)
    qtbot.addWidget(pantalla)

    _seleccionar_profesional(pantalla, id_prof1)
    pantalla.actualizar()

    assert pantalla.combo_profesional.currentData() == id_prof1
