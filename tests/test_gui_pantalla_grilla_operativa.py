import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.grilla_operativa import PantallaGrillaOperativa
from app.negocio.formato import formatear_moneda
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    connection.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-10' WHERE IdConfiguracion = 1"
    )
    connection.commit()
    yield connection
    connection.close()


def _unidad_con_consultorio(
    conn, nombre_edificio, departamento, numero=1, valor_regular=1000, valor_aislada=500, localidad="Ramos Mejía",
):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre=nombre_edificio, DomicilioLocalidad=localidad)
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=departamento)
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=numero,
        ValorHoraRegularActual=valor_regular, ValorHoraAisladaActual=valor_aislada,
    )
    return id_edificio, id_unidad, id_consultorio


def test_valores_se_completan_al_iniciar(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"', valor_regular=1500, valor_aislada=700)
    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.tabla_valores.rowCount() == 1
    assert pantalla.tabla_valores.item(0, 0).text() == "Ramos 1"
    assert pantalla.tabla_valores.item(0, 3).text() == formatear_moneda(1500)
    assert pantalla.tabla_valores.item(0, 4).text() == formatear_moneda(700)


def test_estadisticas_con_un_solo_edificio_omite_el_nivel_edificio(qtbot, conn):
    # con una sola unidad en el filtro, localidad y edificio coinciden con
    # "todo" -> no se muestran esos niveles, solo Total y la unidad.
    id_edificio, id_unidad, id_consultorio = _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"')
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.tabla_estadisticas.rowCount() == 2
    nombres = [pantalla.tabla_estadisticas.item(f, 0).text() for f in range(2)]
    assert nombres[0] == "Total"
    assert nombres[1] == 'Ramos 1 - 7mo "L"'


def test_estadisticas_con_dos_edificios_de_la_misma_localidad_muestra_nivel_edificio(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A")
    _unidad_con_consultorio(conn, "Ramos 2", "2B")
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)

    # misma localidad para ambos (por defecto) -> no se muestra nivel
    # localidad, sí el de edificio: Total, Ramos 1, Ramos 2, 2 unidades.
    assert pantalla.tabla_estadisticas.rowCount() == 5
    nombres = [pantalla.tabla_estadisticas.item(f, 0).text() for f in range(5)]
    assert nombres[0] == "Total"
    assert set(nombres[1:3]) == {"Ramos 1", "Ramos 2"}
    assert set(nombres[3:5]) == {'Ramos 1 - 1A', 'Ramos 2 - 2B'}


def test_estadisticas_con_dos_localidades_muestra_ambos_niveles(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A", localidad="Ramos Mejía")
    _unidad_con_consultorio(conn, "Haedo 1", "2B", localidad="Haedo")
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)

    # Total + 2 localidades + 2 edificios + 2 unidades
    assert pantalla.tabla_estadisticas.rowCount() == 7
    nombres = [pantalla.tabla_estadisticas.item(f, 0).text() for f in range(7)]
    assert nombres[0] == "Total"
    assert set(nombres[1:3]) == {"Ramos Mejía", "Haedo"}
    assert set(nombres[3:5]) == {"Ramos 1", "Haedo 1"}
    assert set(nombres[5:7]) == {'Ramos 1 - 1A', 'Haedo 1 - 2B'}


def test_valores_y_estadisticas_siguen_el_filtro_de_unidad(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A")
    _unidad_con_consultorio(conn, "Ramos 2", "2B")
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_valores.rowCount() == 2

    pantalla.grilla.lista_unidad.clearSelection()
    for i in range(pantalla.grilla.lista_unidad.count()):
        if pantalla.grilla.lista_unidad.item(i).text().startswith("Ramos 1"):
            pantalla.grilla.lista_unidad.item(i).setSelected(True)

    assert pantalla.tabla_valores.rowCount() == 1
    assert pantalla.tabla_valores.item(0, 0).text() == "Ramos 1"
    assert pantalla.tabla_estadisticas.rowCount() == 2  # Total + la unidad (un solo edificio filtrado)


def test_sin_unidades_seleccionadas_vacia_ambas_tablas(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"')
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    pantalla.grilla.lista_unidad.clearSelection()

    assert pantalla.tabla_valores.rowCount() == 0
    assert pantalla.tabla_estadisticas.rowCount() == 0


def test_subtotal_regulares_coincide_con_el_motor_de_estadisticas(qtbot, conn):
    from app.negocio.estadisticas_operativas import calcular_estadisticas_operativas

    id_edificio, id_unidad, id_consultorio = _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"')
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)

    # fila 0 = Total (siempre arriba de todo); con una sola unidad filtrada
    # coincide con esa unidad.
    esperado = calcular_estadisticas_operativas(conn, [id_unidad]).total
    assert pantalla.tabla_estadisticas.item(0, 0).text() == "Total"
    assert pantalla.tabla_estadisticas.item(0, 4).text() == formatear_moneda(esperado.subtotal_regulares)
    assert pantalla.tabla_estadisticas.item(0, 7).text() == formatear_moneda(esperado.falta_cobrar)
