import pytest
from PySide6.QtCore import Qt

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.grilla_operativa import _PanelGrillaSemanal, _PanelValoresVigentes
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


def _id_localidad(conn, nombre: str) -> int:
    fila = conn.execute("SELECT IdLocalidad FROM Localidad WHERE Localidad = ?", (nombre,)).fetchone()
    return fila["IdLocalidad"] if fila else obtener_repositorio(conn, "Localidad").crear(Localidad=nombre)


def _unidad_con_consultorio(
    conn, nombre_edificio, departamento, numero=1, valor_regular=1000, valor_aislada=500, localidad="Ramos Mejía",
):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre=nombre_edificio, IdLocalidad=_id_localidad(conn, localidad)
    )
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


# ------------------------------------------------------- _PanelGrillaSemanal


def test_grilla_semanal_es_un_panel_solapa(qtbot, conn):
    """Reordenamiento de formularios: dejó de ser una solapa de "Vista
    rápida" (pantalla retirada) — ahora es la solapa "Grilla semanal" de
    "Grilla y mensajería" (ver grilla_y_mensajeria.py)."""
    panel = _PanelGrillaSemanal(conn)
    qtbot.addWidget(panel)
    assert panel.objectName() == "panelSolapa"


def test_cambiar_modo_de_visualizacion_oculta_la_leyenda_anterior(qtbot, conn):
    """Bug real: `deleteLater()` sola no saca el widget de pantalla al
    toque (la destrucción queda diferida al loop de eventos) — al pasar
    de "Reservas regulares" a "Reservas aisladas" la leyenda vieja
    quedaba superpuesta con la nueva, con el texto ilegible."""
    panel = _PanelGrillaSemanal(conn)
    qtbot.addWidget(panel)
    leyenda = panel._leyenda
    widgets_regular = [leyenda._layout.itemAt(i).widget() for i in range(leyenda._layout.count())]
    assert widgets_regular  # la leyenda de "regular" arranca poblada

    panel.grilla.combo_modo.setCurrentIndex(1)  # Reservas aisladas

    assert all(w.isHidden() for w in widgets_regular)


# ----------------------------------------------------- _PanelValoresVigentes


def test_valores_vigentes_es_un_panel_solapa(qtbot, conn):
    """Reordenamiento de formularios: dejó de ser una solapa de "Vista
    rápida" (pantalla retirada) — ahora es la solapa "Valores vigentes"
    de "Valores" (ver valores.py)."""
    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    assert panel.objectName() == "panelSolapa"


def test_filtros_de_valores_arrancan_colapsados_con_resumen(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"')
    conn.commit()

    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    filtros = panel.filtros_valores
    assert filtros.lista_localidad.isHidden() is True
    assert filtros.lista_consultorio.isHidden() is True
    assert filtros._filtro_localidad._boton.text() == "Todas las localidades"
    assert filtros._filtro_edificio._boton.text() == "Todos los edificios"
    assert filtros._filtro_unidad._boton.text() == "Todas las unidades"
    assert filtros._filtro_consultorio._boton.text() == "Todos los consultorios"


def test_filtro_consultorio_ordena_por_piso_de_la_unidad(qtbot, conn):
    """Bug real: un ORDER BY NumeroConsultorio a secas mezclaba los
    consultorios de distintas unidades ignorando el piso de cada una."""
    id_edificio, id_unidad_7mo, _ = _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"', numero=5)
    id_unidad_pb = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='PB "D"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_pb, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    conn.commit()

    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    numeros = [panel.filtros_valores.lista_consultorio.item(i).text() for i in range(1, panel.filtros_valores.lista_consultorio.count())]
    assert numeros == ["1", "5"]  # PB (consultorio 1) antes que 7mo (consultorio 5), aunque 5 > 1


def test_valores_se_completan_al_iniciar(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"', valor_regular=1500, valor_aislada=700)
    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)

    assert panel.tabla_valores.rowCount() == 1
    assert panel.tabla_valores.item(0, 0).text() == "Ramos Mejía"
    assert panel.tabla_valores.item(0, 1).text() == "Ramos 1"
    assert panel.tabla_valores.item(0, 2).text() == '7mo "L"'
    assert panel.tabla_valores.item(0, 4).text() == formatear_moneda(1500)
    assert panel.tabla_valores.item(0, 5).text() == formatear_moneda(700)


def test_columnas_de_valores_numericas_alineadas_a_la_derecha(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"', valor_regular=1500, valor_aislada=700)
    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)

    alineacion_derecha = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    # Localidad/Edificio/Unidad (texto) siguen a la izquierda; Consultorio/
    # Valor hora regular/Valor hora aislada (numéricas) van a la derecha.
    assert panel.tabla_valores.item(0, 0).textAlignment() != alineacion_derecha
    for columna in (3, 4, 5):
        assert panel.tabla_valores.item(0, columna).textAlignment() == alineacion_derecha
    assert panel.promedios_valores.tabla.item(0, 3).textAlignment() == alineacion_derecha
    assert panel.promedios_valores.tabla.item(0, 4).textAlignment() == alineacion_derecha


def test_tabla_de_valores_tiene_titulo_propio(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"')
    conn.commit()

    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    grupo = panel.tabla_valores.parentWidget()
    assert grupo.title() == "Valores vigentes por horas regulares y aisladas"


def test_promedios_incluye_hora_regular_y_aislada(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A", valor_regular=1000, valor_aislada=400)
    _unidad_con_consultorio(conn, "Ramos 1", "2B", valor_regular=2000, valor_aislada=800)
    conn.commit()

    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    tabla = panel.promedios_valores.tabla
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

    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    unidades = [panel.tabla_valores.item(f, 2).text() for f in range(panel.tabla_valores.rowCount())]
    assert unidades == ['PB "D"', '7mo "L"']


def test_promedios_se_completan_al_iniciar(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A", valor_regular=1000)
    _unidad_con_consultorio(conn, "Ramos 1", "2B", valor_regular=2000)
    conn.commit()

    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    assert panel.promedios_valores.tabla.item(0, 0).text() == "General"
    assert panel.promedios_valores.tabla.item(0, 3).text() == formatear_moneda(1500)


def test_valores_siguen_su_propio_filtro_de_unidad(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", "1A")
    _unidad_con_consultorio(conn, "Ramos 2", "2B")
    conn.commit()

    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    assert panel.tabla_valores.rowCount() == 2

    _deseleccionar_todo_menos(panel.filtros_valores.lista_unidad, "Ramos 1")
    assert panel.tabla_valores.rowCount() == 1
    assert panel.tabla_valores.item(0, 1).text() == "Ramos 1"


def test_sin_unidades_en_el_filtro_vacia_valores_y_promedios(qtbot, conn):
    _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"')
    conn.commit()

    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    panel.filtros_valores.lista_unidad.clearSelection()

    assert panel.tabla_valores.rowCount() == 0
    assert panel.promedios_valores.tabla.item(0, 3).text() == formatear_moneda(0)


def test_filtro_por_consultorio_puntual_acota_valores(qtbot, conn):
    id_edificio, id_unidad, _ = _unidad_con_consultorio(conn, "Ramos 1", '7mo "L"', numero=1, valor_regular=1000)
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=2, ValorHoraRegularActual=5000)
    conn.commit()

    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    assert panel.tabla_valores.rowCount() == 2

    _deseleccionar_todo_menos(panel.filtros_valores.lista_consultorio, "1")
    assert panel.tabla_valores.rowCount() == 1
    assert panel.tabla_valores.item(0, 4).text() == formatear_moneda(1000)


def test_click_en_columna_de_promedios_ordena_localidades_edificios_y_unidades(qtbot, conn):
    """El clic en una columna no debe aplanar la tabla (lo que haría el
    sort nativo de Qt, mezclando niveles): tiene que reordenar las
    localidades entre sí, y dentro de cada una los edificios, y dentro
    de cada edificio las unidades — todo por el mismo valor clickeado."""
    _unidad_con_consultorio(conn, "Haedo 1", "1A", valor_regular=5000, localidad="Haedo")
    _unidad_con_consultorio(conn, "Ramos 1", "2B", valor_regular=1000, localidad="Ramos Mejía")
    conn.commit()

    panel = _PanelValoresVigentes(conn)
    qtbot.addWidget(panel)
    tabla = panel.promedios_valores.tabla

    # orden por defecto: alfabético -> Haedo antes que Ramos Mejía
    assert [tabla.item(f, 0).text() for f in (1, 2)] == ["Haedo", "Ramos Mejía"]

    tabla.horizontalHeader().sectionClicked.emit(3)  # Promedio hora regular, ascendente
    assert tabla.item(0, 0).text() == "General"  # el total nunca se reordena
    assert [tabla.item(f, 0).text() for f in (1, 2)] == ["Ramos Mejía", "Haedo"]  # 1000 antes que 5000
    assert [tabla.item(f, 1).text() for f in (3, 4)] == ["Ramos 1", "Haedo 1"]
    assert [tabla.item(f, 2).text() for f in (5, 6)] == ["2B", "1A"]

    tabla.horizontalHeader().sectionClicked.emit(3)  # mismo clic de nuevo -> descendente
    assert [tabla.item(f, 0).text() for f in (1, 2)] == ["Haedo", "Ramos Mejía"]
