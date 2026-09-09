import pytest
from PySide6.QtCore import Qt

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


def test_filtros_de_valores_arrancan_colapsados_con_resumen(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"')
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.filtros_valores
    assert panel.lista_localidad.isHidden() is True
    assert panel.lista_consultorio.isHidden() is True
    assert panel._filtro_localidad._boton.text() == "Todas las localidades"
    assert panel._filtro_edificio._boton.text() == "Todos los edificios"
    assert panel._filtro_unidad._boton.text() == "Todas las unidades"
    assert panel._filtro_consultorio._boton.text() == "Todos los consultorios"


def test_filtro_consultorio_ordena_por_piso_de_la_unidad(qtbot, conn):
    """Bug real: un ORDER BY NumeroConsultorio a secas mezclaba los
    consultorios de distintas unidades ignorando el piso de cada una."""
    id_edificio, id_unidad_7mo, _ = _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"', numero=5)
    id_unidad_pb = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='PB "D"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_pb, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    numeros = [pantalla.filtros_valores.lista_consultorio.item(i).text() for i in range(1, pantalla.filtros_valores.lista_consultorio.count())]
    assert numeros == ["1", "5"]  # PB (consultorio 1) antes que 7mo (consultorio 5), aunque 5 > 1


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


def test_columnas_de_valores_numericas_alineadas_a_la_derecha(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"', valor_regular=1500, valor_aislada=700)
    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)

    alineacion_derecha = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    # Localidad/Edificio/Unidad (texto) siguen a la izquierda; Consultorio/
    # Valor hora regular/Valor hora aislada (numéricas) van a la derecha.
    assert pantalla.tabla_valores.item(0, 0).textAlignment() != alineacion_derecha
    for columna in (3, 4, 5):
        assert pantalla.tabla_valores.item(0, columna).textAlignment() == alineacion_derecha
    assert pantalla.promedios_valores.tabla.item(0, 3).textAlignment() == alineacion_derecha
    assert pantalla.promedios_valores.tabla.item(0, 4).textAlignment() == alineacion_derecha


def test_tabla_de_valores_tiene_titulo_propio(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"')
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    grupo = pantalla.tabla_valores.parentWidget()
    assert grupo.title() == "Valores vigentes por horas regulares y aisladas"


def test_promedios_incluye_hora_regular_y_aislada(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A", valor_regular=1000, valor_aislada=400)
    _unidad_con_consultorio(conn, "Ramos 1", "2B", valor_regular=2000, valor_aislada=800)
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.promedios_valores.tabla
    assert tabla.horizontalHeaderItem(3).text() == "Promedio hora regular"
    assert tabla.horizontalHeaderItem(4).text() == "Promedio hora aislada"
    assert tabla.item(0, 0).text() == "General"
    assert tabla.item(0, 3).text() == formatear_moneda(1500)
    assert tabla.item(0, 4).text() == formatear_moneda(600)


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
    assert pantalla.promedios_valores.tabla.item(0, 3).text() == formatear_moneda(1500)


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
    assert pantalla.promedios_valores.tabla.item(0, 3).text() == formatear_moneda(0)


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


def test_click_en_columna_de_promedios_ordena_localidades_edificios_y_unidades(qtbot, conn):
    """El clic en una columna no debe aplanar la tabla (lo que haría el
    sort nativo de Qt, mezclando niveles): tiene que reordenar las
    localidades entre sí, y dentro de cada una los edificios, y dentro
    de cada edificio las unidades — todo por el mismo valor clickeado."""
    _unidad_con_consultorio(conn, "Haedo 1", "1A", valor_regular=5000, localidad="Haedo")
    _unidad_con_consultorio(conn, "Ramos 1", "2B", valor_regular=1000, localidad="Ramos Mejía")
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.promedios_valores.tabla

    # orden por defecto: alfabético -> Haedo antes que Ramos Mejía
    assert [tabla.item(f, 0).text() for f in (1, 2)] == ["Haedo", "Ramos Mejía"]

    tabla.horizontalHeader().sectionClicked.emit(3)  # Promedio hora regular, ascendente
    assert tabla.item(0, 0).text() == "General"  # el total nunca se reordena
    assert [tabla.item(f, 0).text() for f in (1, 2)] == ["Ramos Mejía", "Haedo"]  # 1000 antes que 5000
    assert [tabla.item(f, 1).text() for f in (3, 4)] == ["Ramos 1", "Haedo 1"]
    assert [tabla.item(f, 2).text() for f in (5, 6)] == ["2B", "1A"]

    tabla.horizontalHeader().sectionClicked.emit(3)  # mismo clic de nuevo -> descendente
    assert [tabla.item(f, 0).text() for f in (1, 2)] == ["Haedo", "Ramos Mejía"]


def test_click_en_columna_de_estadisticas_ordena_localidades_edificios_y_unidades(qtbot, conn):
    _, _, id_consultorio_haedo = _unidad_con_consultorio(conn, "Haedo 1", "1A", localidad="Haedo")
    _, _, id_consultorio_ramos = _unidad_con_consultorio(conn, "Ramos 1", "2B", localidad="Ramos Mejía")
    id_prof_haedo = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Uno")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof_haedo, IdConsultorio=id_consultorio_haedo, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=17, VigenciaInicio="2026-01-01",
    )
    id_prof_ramos = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Dos")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof_ramos, IdConsultorio=id_consultorio_ramos, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    pantalla = PantallaGrillaOperativa(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.tabla_estadisticas

    assert [tabla.item(f, 0).text() for f in (1, 2)] == ["Haedo", "Ramos Mejía"]

    tabla.horizontalHeader().sectionClicked.emit(5)  # Subtotal regulares, ascendente
    assert tabla.item(0, 0).text() == "Total"  # el total nunca se reordena
    # Haedo reservó 8hs, Ramos Mejía 1hs -> Ramos Mejía tiene el subtotal menor.
    assert [tabla.item(f, 0).text() for f in (1, 2)] == ["Ramos Mejía", "Haedo"]
    assert [tabla.item(f, 1).text() for f in (3, 4)] == ["Ramos 1", "Haedo 1"]
    assert [tabla.item(f, 2).text() for f in (5, 6)] == ["2B", "1A"]


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
    assert pantalla.tabla_estadisticas.item(0, 5).text() == formatear_moneda(esperado.subtotal_regulares)
    assert pantalla.tabla_estadisticas.item(0, 7).text() == formatear_moneda(esperado.total_regular_y_aislada)
    assert pantalla.tabla_estadisticas.item(0, 9).text() == formatear_moneda(esperado.falta_cobrar)
