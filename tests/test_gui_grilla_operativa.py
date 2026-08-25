import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.widgets.grilla_operativa import GrillaOperativaWidget
from app.negocio.grilla_operativa import AZUL_OSCURO, ROJO, VERDE
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


def _preparar(conn, codigo_virginia="R1"):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", DomicilioLocalidad="Ramos Mejía")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )
    id_virginia = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lo Veci", NombrePila="Virginia", Tratamiento="Lic.", IdCodigo=codigo_virginia,
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_virginia, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    conn.commit()
    return id_edificio, id_unidad, id_consultorio, id_virginia


def test_filtros_por_defecto_incluyen_todo(qtbot, conn):
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    assert widget.lista_localidad.count() == 1
    assert len(widget.lista_localidad.selectedItems()) == 1
    assert widget.lista_edificio.count() == 1
    assert len(widget.lista_edificio.selectedItems()) == 1
    assert widget.lista_unidad.count() == 1
    assert len(widget.lista_unidad.selectedItems()) == 1
    assert all(check.isChecked() for check in widget._checks_dia.values())
    assert widget.campo_profesional.text() == ""
    assert widget.combo_modo.currentData() == "regular"


def test_rango_por_defecto_es_el_mes_completo(qtbot, conn):
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget.campo_desde.date().toPython().isoformat() == "2026-08-01"
    assert widget.campo_hasta.date().toPython().isoformat() == "2026-08-31"
    assert widget.campo_desde.displayFormat() == "dd-MM-yyyy"


def test_grilla_muestra_codigo_de_reserva_regular(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    clave = (id_consultorio, "Lunes", 9)
    assert clave in widget._resultado
    assert widget._resultado[clave].codigo == "R1"
    assert widget._resultado[clave].color_aro == VERDE


def test_clic_en_celda_muestra_detalle(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    clave = (id_consultorio, "Lunes", 9)
    widget._mostrar_detalle(clave)
    assert widget.texto_detalle.toPlainText() == widget._resultado[clave].detalle
    assert "Lic. Virginia Lo Veci (R1)" in widget.texto_detalle.toPlainText()


def test_cambiar_modo_a_aisladas_recalcula(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    indice_aislada = widget.combo_modo.findData("aislada")
    widget.combo_modo.setCurrentIndex(indice_aislada)

    clave = (id_consultorio, "Lunes", 9)
    assert widget._resultado[clave].color_aro == ROJO  # bloqueado por la reserva regular


def test_filtro_profesional_pinta_azul(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    texto = next(t for t, i in widget._profesionales_por_texto.items() if i == id_virginia)
    widget.campo_profesional.setText(texto)
    widget.actualizar()

    clave = (id_consultorio, "Lunes", 9)
    assert widget._resultado[clave].color_aro == AZUL_OSCURO


def test_columna_se_ensancha_con_codigo_de_4_caracteres(qtbot, conn):
    _preparar(conn, codigo_virginia="R123")
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    ancho_corto = widget.fontMetrics().horizontalAdvance("A99") + 14
    assert widget.tabla.columnWidth(2) > ancho_corto  # columna 0=Tipo Bloque, 1=Horario, 2+=datos


def test_cascada_edificio_a_unidad(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    otro_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2", DomicilioLocalidad="Ramos Mejía")
    otra_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=otro_edificio, Departamento="2do B")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=otra_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    conn.commit()

    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget.lista_edificio.count() == 2
    assert widget.lista_unidad.count() == 2

    widget.lista_edificio.clearSelection()
    for i in range(widget.lista_edificio.count()):
        if widget.lista_edificio.item(i).text() == "Ramos 1":
            widget.lista_edificio.item(i).setSelected(True)

    assert widget.lista_unidad.count() == 1
    assert widget.lista_unidad.item(0).text() == 'Ramos 1 - 7mo "L"'


def test_sin_unidades_seleccionadas_deja_grilla_vacia(qtbot, conn):
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    widget.lista_unidad.clearSelection()
    assert widget.tabla.rowCount() == 0
    assert widget._resultado == {}


def test_filtrar_por_unidad_acota_la_seleccion(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    otro_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2", DomicilioLocalidad="Ramos Mejía")
    otra_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=otro_edificio, Departamento="2do B")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=otra_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    conn.commit()

    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert set(widget.ids_unidad_seleccionadas()) == {id_unidad, otra_unidad}

    widget.filtrar_por_unidad(id_unidad)
    assert widget.ids_unidad_seleccionadas() == [id_unidad]

    widget.filtrar_por_unidad(None)
    assert set(widget.ids_unidad_seleccionadas()) == {id_unidad, otra_unidad}


def test_filtrar_por_profesional_fija_y_limpia_el_campo(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    clave = (id_consultorio, "Lunes", 9)
    widget.filtrar_por_profesional(id_virginia)
    assert widget._resultado[clave].color_aro == AZUL_OSCURO

    widget.filtrar_por_profesional(None)
    assert widget.campo_profesional.text() == ""
    assert widget._resultado[clave].color_aro == VERDE


def test_filtrar_por_dias_acota_la_seleccion(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert all(check.isChecked() for check in widget._checks_dia.values())

    widget.filtrar_por_dias(["Lunes", "Martes"])
    assert {dia for dia, check in widget._checks_dia.items() if check.isChecked()} == {"Lunes", "Martes"}

    widget.filtrar_por_dias([])
    assert all(not check.isChecked() for check in widget._checks_dia.values())

    widget.filtrar_por_dias(None)
    assert all(check.isChecked() for check in widget._checks_dia.values())


def test_dias_con_reserva_vigente(qtbot, conn):
    from app.gui.widgets.grilla_operativa import dias_con_reserva_vigente

    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    assert dias_con_reserva_vigente(conn, id_virginia) == ["Lunes"]
    assert dias_con_reserva_vigente(conn, None) == []

    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Sin Reserva")
    conn.commit()
    assert dias_con_reserva_vigente(conn, otro_profesional) == []
