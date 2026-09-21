"""GUI de Estadísticas (revisión "uno por uno"): dos solapas, "Historial
general" y "Estadísticas varias" — ver CLAUDE.md y el docstring de
app/gui/pantallas/estadisticas.py."""
import pytest
from PySide6.QtWidgets import QLabel, QTabWidget, QWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.estadisticas import PantallaEstadisticas
from app.negocio.dias import periodo_actual
from app.negocio.estadisticas import generar_snapshot
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_edificio_con_consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Norte")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    conn.commit()
    return id_edificio, id_unidad


def test_titulo_de_pantalla_es_jerarquia_1(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "ESTADÍSTICAS"


def test_tiene_formato_solapa_con_las_dos_pestanas(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert solapas.tabText(0) == "Historial general"
    assert solapas.tabText(1) == "Estadísticas varias"
    assert len(pantalla.findChildren(QWidget, "panelSolapa")) == 2


def test_las_dos_tablas_tienen_las_once_columnas(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    columnas = [
        "Período", "Porcentaje Ocupación", "Horas regulares semanales", "Variación sobre período anterior",
        "Monto por horas regulares", "Monto por horas aisladas", "Monto total",
        "Localidades", "Edificios", "Unidades", "Consultorios",
    ]
    for tabla in (pantalla.panel_historial.tabla, pantalla.panel_varias.tabla):
        assert tabla.columnCount() == len(columnas)
        etiquetas = [tabla.horizontalHeaderItem(i).text() for i in range(tabla.columnCount())]
        assert etiquetas == columnas


# ------------------------------------------------------- Historial general


def test_historial_general_arranca_por_mes_e_incluye_el_mes_en_curso(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_historial
    assert panel.check_por_mes.isChecked()
    assert not panel.check_por_anio.isChecked()
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)


def test_historial_general_lista_los_snapshots_ya_generados(qtbot, conn):
    _crear_edificio_con_consultorio(conn)
    generar_snapshot(conn, "2026-06")
    conn.commit()
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    periodos = [pantalla.panel_historial.tabla.item(fila, 0).text() for fila in range(pantalla.panel_historial.tabla.rowCount())]
    assert "2026-06" in periodos
    assert periodo_actual(conn) in periodos


def test_historial_general_checks_por_mes_y_por_anio_son_excluyentes(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_historial

    panel.check_por_anio.click()
    assert panel.check_por_anio.isChecked()
    assert not panel.check_por_mes.isChecked()
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)[:4]

    # Un grupo exclusivo no deja destildar el que está marcado haciendo
    # clic en él mismo: hace falta marcar el otro.
    panel.check_por_anio.click()
    assert panel.check_por_anio.isChecked()

    panel.check_por_mes.click()
    assert panel.check_por_mes.isChecked()
    assert not panel.check_por_anio.isChecked()


def test_historial_general_boton_actualizar_vuelve_a_por_mes(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_historial
    panel.check_por_anio.click()
    assert panel.check_por_anio.isChecked()

    from PySide6.QtWidgets import QPushButton
    boton_actualizar = next(b for b in panel.findChildren(QPushButton) if b.text() == "Actualizar tabla")
    boton_actualizar.click()
    assert panel.check_por_mes.isChecked()


def test_historial_general_se_puede_ordenar_por_columna(qtbot, conn):
    generar_snapshot(conn, "2026-06")
    generar_snapshot(conn, "2026-07")
    conn.commit()
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_historial
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)  # por defecto, lo más nuevo arriba

    panel.tabla.horizontalHeader().sectionClicked.emit(0)  # clic en "Período" -> ascendente
    assert panel.tabla.item(0, 0).text() == "2026-06"

    panel.tabla.horizontalHeader().sectionClicked.emit(0)  # segundo clic -> desciende
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn)


def test_historial_general_variacion_negativa_se_pinta_de_rojo(qtbot, conn, monkeypatch):
    from PySide6.QtGui import QColor

    from app.gui.estilos import COLOR_ROJO
    import app.gui.pantallas.estadisticas as mod

    def _historial_falso(conn, *, por_anio):
        return [
            mod.FilaEstadistica(
                periodo="2026-08", ocupacion_pct=10.0, horas_regulares_semanales=5.0, variacion_horas=-3.0,
                monto_regular=100.0, monto_aislada=50.0,
                cant_localidades=1, cant_edificios=1, cant_unidades=1, cant_consultorios=1,
            ),
        ]

    monkeypatch.setattr(mod, "historial_general", _historial_falso)
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    item = pantalla.panel_historial.tabla.item(0, 3)
    assert item.text() == "-3.0hs"
    assert item.foreground().color() == QColor(COLOR_ROJO)


def test_foco_inicial_de_historial_general(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.panel_historial.check_por_mes.hasFocus())


def test_cadena_de_foco_de_historial_general(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_historial
    assert panel._foco._orden[0] is panel.check_por_mes
    assert panel._foco._orden[1] is panel.check_por_anio


# ----------------------------------------------------- Estadísticas varias


def test_estadisticas_varias_arranca_con_todos_los_filtros_en_todos(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_varias
    for combo in (
        panel.combo_anio, panel.combo_mes, panel.combo_localidad,
        panel.combo_edificio, panel.combo_unidad, panel.combo_consultorio,
    ):
        assert combo.currentText() == "Todos"
        assert combo.currentData() is None


def test_estadisticas_varias_filtro_localidad_acota_edificio_en_cascada(qtbot, conn):
    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Vicente López")
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", IdLocalidad=id_localidad)
    obtener_repositorio(conn, "Edificio").crear(Nombre="Otro Edificio")
    conn.commit()

    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_varias
    indice = panel.combo_localidad.findData(id_localidad)
    panel.combo_localidad.setCurrentIndex(indice)

    nombres_edificio = [panel.combo_edificio.itemText(i) for i in range(panel.combo_edificio.count())]
    assert nombres_edificio == ["Todos", "Ramos 1"]
    assert panel.combo_edificio.findData(id_edificio) == 1


def test_estadisticas_varias_recalcula_al_elegir_un_filtro(qtbot, conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Test")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=19, VigenciaInicio="2026-01-01",
    )
    otro_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Otro")
    conn.commit()

    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_varias
    panel.combo_anio.setCurrentIndex(panel.combo_anio.findData(2026))
    panel.combo_mes.setCurrentIndex(panel.combo_mes.findData(8))
    assert panel.tabla.rowCount() == 1
    fila_sin_filtro = panel.tabla.item(0, 2).text()

    panel.combo_edificio.setCurrentIndex(panel.combo_edificio.findData(otro_edificio))
    fila_filtrada = panel.tabla.item(0, 2).text()
    assert fila_filtrada != fila_sin_filtro
    assert fila_filtrada == "0.0hs"


def test_estadisticas_varias_boton_actualizar_restablece_todos_los_filtros(qtbot, conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    conn.commit()
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_varias
    panel.combo_edificio.setCurrentIndex(panel.combo_edificio.findData(id_edificio))
    assert panel.combo_edificio.currentData() == id_edificio

    from PySide6.QtWidgets import QPushButton
    boton_actualizar = next(b for b in panel.findChildren(QPushButton) if b.text() == "Actualizar tabla")
    boton_actualizar.click()

    assert panel.combo_edificio.currentData() is None
    assert panel.combo_localidad.currentData() is None
    assert panel.combo_anio.currentData() is None


def test_estadisticas_varias_se_puede_ordenar_por_columna(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_varias
    panel.combo_anio.setCurrentIndex(panel.combo_anio.findData(2026))
    assert panel.tabla.item(0, 0).text() == periodo_actual(conn) and panel.tabla.rowCount() >= 2

    panel.tabla.horizontalHeader().sectionClicked.emit(0)  # clic en "Período" -> ascendente
    assert panel.tabla.item(0, 0).text() == "2026-01"

    panel.tabla.horizontalHeader().sectionClicked.emit(0)  # segundo clic -> desciende
    assert panel.tabla.item(0, 0).text() != "2026-01"


def test_foco_inicial_de_estadisticas_varias(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    pantalla.pestanas.setCurrentIndex(1)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.panel_varias.combo_anio.hasFocus())


def test_cadena_de_foco_de_estadisticas_varias(qtbot, conn):
    pantalla = PantallaEstadisticas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_varias
    from PySide6.QtWidgets import QPushButton
    boton_actualizar = next(b for b in panel.findChildren(QPushButton) if b.text() == "Actualizar tabla")
    assert panel._foco._orden == [
        panel.combo_anio, panel.combo_mes, panel.combo_localidad, panel.combo_edificio,
        panel.combo_unidad, panel.combo_consultorio, boton_actualizar,
    ]
