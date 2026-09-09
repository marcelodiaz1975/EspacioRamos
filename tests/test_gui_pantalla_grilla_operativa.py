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


def _deseleccionar_todo_menos(lista, texto_prefijo):
    lista.clearSelection()
    for i in range(lista.count()):
        if lista.item(i).text().startswith(texto_prefijo):
            lista.item(i).setSelected(True)


def test_solapas_correctas(qtbot, conn):
    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    tabs = pantalla.layout().itemAt(1).widget()
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "Grilla semanal", "Valores de los consultorios", "Estadísticas",
    ]


def test_valores_se_completan_al_iniciar(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"', valor_regular=1500, valor_aislada=700)
    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.tabla_valores.rowCount() == 1
    assert pantalla.tabla_valores.item(0, 0).text() == "Ramos Mejía"
    assert pantalla.tabla_valores.item(0, 1).text() == "Ramos 1"
    assert pantalla.tabla_valores.item(0, 2).text() == '7mo "L"'
    assert pantalla.tabla_valores.item(0, 4).text() == formatear_moneda(1500)
    assert pantalla.tabla_valores.item(0, 5).text() == formatear_moneda(700)


def test_valores_ordena_unidades_por_piso(qtbot, conn):
    id_edificio, _, _ = _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='PB "D"'),
        NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    unidades = [pantalla.tabla_valores.item(f, 2).text() for f in range(pantalla.tabla_valores.rowCount())]
    assert unidades == ['PB "D"', '7mo "L"']


def test_promedios_se_completan_al_iniciar(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A", valor_regular=1000)
    _unidad_con_consultorio(conn, "Ramos 1", "2B", valor_regular=2000)
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.promedios_valores.tabla.item(0, 0).text() == "General"
    assert pantalla.promedios_valores.tabla.item(0, 1).text() == formatear_moneda(1500)


def test_valores_siguen_su_propio_filtro_de_unidad(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A")
    _unidad_con_consultorio(conn, "Ramos 2", "2B")
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_valores.rowCount() == 2

    _deseleccionar_todo_menos(pantalla.filtros_valores.lista_unidad, "Ramos 1")
    assert pantalla.tabla_valores.rowCount() == 1
    assert pantalla.tabla_valores.item(0, 1).text() == "Ramos 1"


def test_valores_no_sigue_el_filtro_de_la_grilla(qtbot, conn):
    """Las solapas Valores/Estadísticas tienen su propio filtro,
    independiente del de la solapa Grilla semanal."""
    _unidad_con_consultorio(conn, "Ramos 1", "1A")
    _unidad_con_consultorio(conn, "Ramos 2", "2B")
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    pantalla.grilla.lista_unidad.clearSelection()
    assert pantalla.tabla_valores.rowCount() == 2


def test_sin_unidades_en_el_filtro_vacia_valores_y_promedios(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"')
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    pantalla.filtros_valores.lista_unidad.clearSelection()

    assert pantalla.tabla_valores.rowCount() == 0
    assert pantalla.promedios_valores.tabla.item(0, 1).text() == formatear_moneda(0)


def test_filtro_por_consultorio_puntual_acota_valores(qtbot, conn):
    id_edificio, id_unidad, _ = _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"', numero=1, valor_regular=1000)
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=2, ValorHoraRegularActual=5000)
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_valores.rowCount() == 2

    _deseleccionar_todo_menos(pantalla.filtros_valores.lista_consultorio, "1")
    assert pantalla.tabla_valores.rowCount() == 1
    assert pantalla.tabla_valores.item(0, 4).text() == formatear_moneda(1000)


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
    assert pantalla.tabla_estadisticas.item(0, 0).text() == "Total"
    assert pantalla.tabla_estadisticas.item(1, 1).text() == "Ramos 1"
    assert pantalla.tabla_estadisticas.item(1, 2).text() == '7mo "L"'


def test_estadisticas_con_dos_edificios_de_la_misma_localidad_muestra_nivel_edificio(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A")
    _unidad_con_consultorio(conn, "Ramos 2", "2B")
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)

    # misma localidad para ambos (por defecto) -> no se muestra nivel
    # localidad, sí el de edificio: Total, Ramos 1, Ramos 2, 2 unidades.
    assert pantalla.tabla_estadisticas.rowCount() == 5
    assert pantalla.tabla_estadisticas.item(0, 0).text() == "Total"
    edificios_solo = [pantalla.tabla_estadisticas.item(f, 1).text() for f in (1, 2)]
    assert set(edificios_solo) == {"Ramos 1", "Ramos 2"}
    unidades = [pantalla.tabla_estadisticas.item(f, 2).text() for f in (3, 4)]
    assert set(unidades) == {"1A", "2B"}


def test_estadisticas_con_dos_localidades_muestra_ambos_niveles(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A", localidad="Ramos Mejía")
    _unidad_con_consultorio(conn, "Haedo 1", "2B", localidad="Haedo")
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)

    # Total + 2 localidades + 2 edificios + 2 unidades
    assert pantalla.tabla_estadisticas.rowCount() == 7
    assert pantalla.tabla_estadisticas.item(0, 0).text() == "Total"
    localidades = [pantalla.tabla_estadisticas.item(f, 0).text() for f in (1, 2)]
    assert set(localidades) == {"Ramos Mejía", "Haedo"}
    edificios = [pantalla.tabla_estadisticas.item(f, 1).text() for f in (3, 4)]
    assert set(edificios) == {"Ramos 1", "Haedo 1"}
    unidades = [pantalla.tabla_estadisticas.item(f, 2).text() for f in (5, 6)]
    assert set(unidades) == {"1A", "2B"}


def test_estadisticas_sigue_su_propio_filtro(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A")
    _unidad_con_consultorio(conn, "Ramos 2", "2B")
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_estadisticas.rowCount() == 5  # Total + 2 edificios + 2 unidades

    _deseleccionar_todo_menos(pantalla.filtros_estadisticas.lista_unidad, "Ramos 1")
    assert pantalla.tabla_estadisticas.rowCount() == 2  # Total + la unidad (un solo edificio filtrado)


def test_sin_unidades_seleccionadas_vacia_estadisticas(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"')
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    pantalla.filtros_estadisticas.lista_unidad.clearSelection()

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
    assert pantalla.tabla_estadisticas.item(0, 6).text() == formatear_moneda(esperado.subtotal_regulares)
    assert pantalla.tabla_estadisticas.item(0, 9).text() == formatear_moneda(esperado.falta_cobrar)
