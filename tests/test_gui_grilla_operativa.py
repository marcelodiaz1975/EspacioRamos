import pytest
from PySide6.QtWidgets import QCheckBox, QGridLayout, QLabel

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.widgets.grilla_operativa import GrillaOperativaWidget
from app.gui.widgets.selector_profesional import _ProxyBusquedaSinAcentos
from app.negocio.grilla_operativa import AZUL_OSCURO, BLANCO, ROJO
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


def _preparar(conn, codigo_virginia="R1"):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 1", IdLocalidad=_id_localidad(conn, "Ramos Mejía")
    )
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


def test_filtros_arrancan_colapsados_con_el_resumen_correcto(qtbot, conn):
    """Confirmado por la clienta: la lista no se ve desplegada, solo un
    botón-resumen ("Todas las X") que la abre al pincharlo. Bug real
    encontrado al implementar esto: la población inicial corre con
    `blockSignals(True)`, así que el resumen no se actualizaba solo con
    la señal — hace falta refrescarlo a mano."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    assert widget.lista_localidad.isHidden() is True
    assert widget.lista_edificio.isHidden() is True
    assert widget.lista_unidad.isHidden() is True
    assert widget._filtro_localidad._boton.text() == "Todas las localidades"
    assert widget._filtro_edificio._boton.text() == "Todos los edificios"
    assert widget._filtro_unidad._boton.text() == "Todas las unidades"

    widget._filtro_unidad._boton.setChecked(True)
    widget._filtro_unidad._alternar()
    assert widget.lista_unidad.isHidden() is False


def test_filtros_por_defecto_incluyen_todo(qtbot, conn):
    """Confirmado por la clienta: por defecto solo queda tildado el ítem
    "Todas las X" de cada lista, no cada valor real uno por uno."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    assert widget.lista_localidad.count() == 2  # "Todas las localidades" + 1 real
    assert [i.text() for i in widget.lista_localidad.selectedItems()] == ["Todas las localidades"]
    assert widget.lista_edificio.count() == 2  # "Todos los edificios" + 1 real
    assert [i.text() for i in widget.lista_edificio.selectedItems()] == ["Todos los edificios"]
    assert widget.lista_unidad.count() == 2  # "Todas las unidades" + 1 real
    assert [i.text() for i in widget.lista_unidad.selectedItems()] == ["Todas las unidades"]
    assert all(check.isChecked() for check in widget._checks_dia.values())
    assert widget.campo_profesional.currentData() is None
    assert widget.combo_modo.currentData() == "regular"


def test_periodo_por_defecto_es_el_mes_en_curso(qtbot, conn):
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget.combo_periodo.currentData() == "2026-08"
    assert not hasattr(widget, "campo_desde")
    assert not hasattr(widget, "campo_hasta")


def test_grilla_muestra_codigo_de_reserva_regular(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    clave = (id_consultorio, "Lunes", 9)
    assert clave in widget._resultado
    assert widget._resultado[clave].codigo == "R1"
    assert widget._resultado[clave].color_aro == BLANCO  # sin fecha de liberación cargada: blanco liso


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


def test_campo_profesional_es_buscable_por_codigo_o_nombre(qtbot, conn):
    """Confirmado por la clienta: el selector de profesional buscable
    corre en todos los formularios del sistema, Grilla operativa
    incluida."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    completador = widget.campo_profesional.completer()
    assert isinstance(completador.model(), _ProxyBusquedaSinAcentos)


def test_filtro_profesional_pinta_azul(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    indice = widget.campo_profesional.findData(id_virginia)
    widget.campo_profesional.setCurrentIndex(indice)

    clave = (id_consultorio, "Lunes", 9)
    assert widget._resultado[clave].color_aro == AZUL_OSCURO


def test_filtro_exclusivo_profesional_oculta_a_los_demas(qtbot, conn):
    """Sin activar el filtro exclusivo, la celda de otro profesional en
    otro horario del mismo consultorio se sigue viendo normal. Al
    activarlo con un profesional elegido, esa celda ajena queda en
    blanco — solo se ve lo del profesional filtrado."""
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    id_otro = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Otro", IdCodigo="R9",
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_otro, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=14, HoraFin=15, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    indice = widget.campo_profesional.findData(id_virginia)
    widget.campo_profesional.setCurrentIndex(indice)

    clave_propia = (id_consultorio, "Lunes", 9)
    clave_ajena = (id_consultorio, "Lunes", 14)
    assert widget._resultado[clave_ajena].codigo == "R9"  # sin filtro exclusivo, se ve

    widget.activar_filtro_exclusivo_profesional(True)
    assert widget._resultado[clave_propia].codigo == "R1"
    assert widget._resultado[clave_ajena].codigo is None  # con el filtro exclusivo, desaparece


def test_columna_se_ensancha_con_codigo_de_4_caracteres(qtbot, conn):
    _preparar(conn, codigo_virginia="R123")
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    ancho_corto = widget.fontMetrics().horizontalAdvance("A99") + 14
    assert widget.tabla.columnWidth(2) > ancho_corto  # columna 0=Tipo Bloque, 1=Horario, 2+=datos


def test_lista_unidad_ordena_por_piso_pb_ep_numerico(qtbot, conn):
    """Confirmado por la clienta: PB primero, después EP, después los
    pisos numéricos ascendentes (acá, alfabético dentro del mismo edificio
    ya que las unidades no comparten piso)."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    for departamento in ['7mo "L"', 'EP "K"', 'PB "D"', '1ro "A"']:
        obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=departamento)
    conn.commit()

    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    nombres = [widget.lista_unidad.item(i).text() for i in range(widget.lista_unidad.count())]
    assert nombres == [
        "Todas las unidades", 'Ramos 1 - PB "D"', 'Ramos 1 - EP "K"', 'Ramos 1 - 1ro "A"', 'Ramos 1 - 7mo "L"',
    ]


def test_grilla_ordena_columnas_por_piso_pb_ep_numerico(qtbot, conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    ids_unidad = []
    for departamento in ['7mo "L"', 'PB "D"', 'EP "K"']:
        id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=departamento)
        obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
        ids_unidad.append(id_unidad)
    conn.commit()

    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    columnas = widget._columnas(ids_unidad, ["Lunes"])
    assert [c["departamento"] for c in columnas] == ['PB "D"', 'EP "K"', '7mo "L"']


def test_cascada_edificio_a_unidad(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    otro_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", IdLocalidad=_id_localidad(conn, "Ramos Mejía")
    )
    otra_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=otro_edificio, Departamento="2do B")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=otra_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    conn.commit()

    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget.lista_edificio.count() == 3  # "Todos los edificios" + 2 reales
    assert widget.lista_unidad.count() == 3  # "Todas las unidades" + 2 reales

    widget.lista_edificio.clearSelection()
    for i in range(widget.lista_edificio.count()):
        if widget.lista_edificio.item(i).text() == "Ramos 1":
            widget.lista_edificio.item(i).setSelected(True)

    assert widget.lista_unidad.count() == 2  # "Todas las unidades" + 1 real
    assert widget.lista_unidad.item(1).text() == 'Ramos 1 - 7mo "L"'


def test_sin_unidades_seleccionadas_deja_grilla_vacia(qtbot, conn):
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    widget.lista_unidad.clearSelection()
    assert widget.tabla.rowCount() == 0
    assert widget._resultado == {}


def test_filtrar_por_unidad_acota_la_seleccion(qtbot, conn):
    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    otro_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", IdLocalidad=_id_localidad(conn, "Ramos Mejía")
    )
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
    assert widget.campo_profesional.currentData() is None
    assert widget._resultado[clave].color_aro == BLANCO


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


def test_unidades_con_reserva_incluye_aisladas(qtbot, conn):
    from app.gui.widgets.grilla_operativa import unidades_con_reserva

    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    # id_virginia ya tiene una reserva regular en id_unidad (armada por _preparar)
    assert unidades_con_reserva(conn, id_virginia) == [id_unidad]
    assert unidades_con_reserva(conn, None) == []

    # un profesional sin ninguna reserva regular, solo una aislada, igual aparece
    otro_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", IdLocalidad=_id_localidad(conn, "Ramos Mejía")
    )
    otra_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=otro_edificio, Departamento="2do B")
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=otra_unidad, NumeroConsultorio=1)
    solo_aislada = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Ajeno")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=solo_aislada, IdConsultorio=otro_consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    conn.commit()
    assert unidades_con_reserva(conn, solo_aislada) == [otra_unidad]


def test_dias_con_reserva_incluye_aisladas(qtbot, conn):
    from app.gui.widgets.grilla_operativa import dias_con_reserva

    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    assert dias_con_reserva(conn, id_virginia) == ["Lunes"]
    assert dias_con_reserva(conn, None) == []

    solo_aislada = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Ajeno")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=solo_aislada, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=9, HoraFin=10,
    )
    conn.commit()
    from app.negocio.dias import fecha_a_dia_semana
    from datetime import date

    assert dias_con_reserva(conn, solo_aislada) == [fecha_a_dia_semana(date(2026, 8, 18))]


def test_pares_dia_unidad_con_reserva_vigente(qtbot, conn):
    from app.gui.widgets.grilla_operativa import pares_dia_unidad_con_reserva_vigente

    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    otro_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", IdLocalidad=_id_localidad(conn, "Ramos Mejía")
    )
    otra_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=otro_edificio, Departamento="2do B")
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=otra_unidad, NumeroConsultorio=1)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_virginia, IdConsultorio=otro_consultorio, DiaSemana="Miércoles",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    # _preparar ya cargó Lunes en id_unidad; sumamos Miércoles en otra_unidad
    assert pares_dia_unidad_con_reserva_vigente(conn, id_virginia) == {
        ("Lunes", id_unidad), ("Miércoles", otra_unidad),
    }
    assert pares_dia_unidad_con_reserva_vigente(conn, None) == set()


def test_pares_dia_unidad_con_reserva_incluye_aisladas(qtbot, conn):
    from app.gui.widgets.grilla_operativa import pares_dia_unidad_con_reserva

    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    otro_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", IdLocalidad=_id_localidad(conn, "Ramos Mejía")
    )
    otra_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=otro_edificio, Departamento="2do B")
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=otra_unidad, NumeroConsultorio=1)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_virginia, IdConsultorio=otro_consultorio, Fecha="2026-08-18", HoraInicio=9, HoraFin=10,
    )
    conn.commit()

    from app.negocio.dias import fecha_a_dia_semana
    from datetime import date

    dia_aislada = fecha_a_dia_semana(date(2026, 8, 18))
    assert pares_dia_unidad_con_reserva(conn, id_virginia) == {
        ("Lunes", id_unidad), (dia_aislada, otra_unidad),
    }
    assert pares_dia_unidad_con_reserva(conn, None) == set()


def test_filtrar_por_pares_unidad_dia_evita_combinaciones_fantasma(qtbot, conn):
    """Sin la restricción por pares, cruzar el filtro de Unidad (ambas)
    con el de Día (ambos) mostraría también la unidad del miércoles bajo
    la columna del lunes (y viceversa), aunque el profesional no tenga
    nada ahí ese día — la restricción por pares evita esas columnas
    fantasma."""
    from app.negocio.dias import DIAS_SEMANA
    from app.gui.widgets.grilla_operativa import pares_dia_unidad_con_reserva_vigente

    id_edificio, id_unidad, id_consultorio, id_virginia = _preparar(conn)
    otro_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre="Ramos 2", IdLocalidad=_id_localidad(conn, "Ramos Mejía")
    )
    otra_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=otro_edificio, Departamento="2do B")
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=otra_unidad, NumeroConsultorio=1)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_virginia, IdConsultorio=otro_consultorio, DiaSemana="Miércoles",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    pares = pares_dia_unidad_con_reserva_vigente(conn, id_virginia)
    ids_unidad = sorted({u for _, u in pares})
    dias = sorted({d for d, _ in pares}, key=DIAS_SEMANA.index)
    widget.filtrar_por_unidades(ids_unidad)
    widget.filtrar_por_dias(dias)

    # sin restricción por pares: cruce completo, 2 unidades x 2 días = 4 columnas de datos
    assert widget.tabla.columnCount() - 2 == 4

    widget.filtrar_por_pares_unidad_dia(pares)
    # con la restricción: solo las 2 combinaciones reales
    assert widget.tabla.columnCount() - 2 == 2

    widget.filtrar_por_pares_unidad_dia(None)
    assert widget.tabla.columnCount() - 2 == 4


def test_fijar_titulo_filtros_cambia_el_titulo_del_panel(qtbot, conn):
    """Pensado para Oferta de consultorios, donde el panel funciona como
    referencia visual completa de la semana, no solo como filtros."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget._panel_filtros.title() == "Filtros"

    widget.fijar_titulo_filtros("Grilla semanal")

    assert widget._panel_filtros.title() == "Grilla semanal"


def test_filtro_colapsable_foco_widget_es_el_boton_resumen(qtbot, conn):
    """La lista de multiselección arranca oculta (colapsada) — un
    widget invisible se saltea siempre en una cadena de Enter-avanza-
    foco, así que el que tiene que recibirlo es el botón-resumen,
    siempre visible."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget._filtro_localidad.foco_widget() is widget._filtro_localidad._boton


def test_fijar_modo_deja_el_modo_y_bloquea_el_combo(qtbot, conn):
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    widget.fijar_modo("aislada")

    assert widget.combo_modo.currentData() == "aislada"
    assert widget.combo_modo.isEnabled() is False


# ----------------------------------------------------------- leyenda de colores

def test_leyenda_colores_oculta_por_defecto(qtbot, conn):
    """"Vista rápida" ya trae su propia leyenda debajo de la grilla
    completa — la que va embebida en el panel de Filtros del widget
    compartido arranca oculta, la revela quien la necesite (Reservas)."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget._leyenda_colores.isHidden() is True


def _textos_leyenda_visibles(leyenda) -> list[str]:
    """`takeAt()` + `hide()` + `deleteLater()` (ver `LeyendaColores.
    actualizar`) saca los QLabel viejos de pantalla al toque, pero siguen
    siendo hijos de Qt hasta que el loop de eventos procesa el
    `deleteLater` — así que `findChildren` los sigue devolviendo. Filtrar
    por `isHidden()` es lo que realmente ve el usuario."""
    return [lbl.text() for lbl in leyenda.findChildren(QLabel) if not lbl.isHidden()]


def test_mostrar_leyenda_colores_la_revela_con_las_referencias_de_regular(qtbot, conn):
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    widget.mostrar_leyenda_colores()
    assert widget._leyenda_colores.isHidden() is False
    textos = _textos_leyenda_visibles(widget._leyenda_colores)
    assert "Profesional filtrado." in textos
    assert "Se libera en el futuro." in textos  # propia de "regular"
    assert "Libre de reserva regular." not in textos  # propia de "aislada"


def test_leyenda_colores_sigue_al_cambio_de_modo(qtbot, conn):
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    widget.mostrar_leyenda_colores()

    widget.combo_modo.setCurrentIndex(widget.combo_modo.findData("aislada"))

    textos = _textos_leyenda_visibles(widget._leyenda_colores)
    assert "Libre de reserva regular." in textos
    assert "Se libera en el futuro." not in textos


def test_mostrar_leyenda_colores_compacta_pasa_a_dos_columnas_y_muestra_mas_chica(qtbot, conn):
    """Pedido de la clienta al revisar Reservas: con `compacta=True` la
    leyenda entra a 2 columnas (en vez de 1) y la muestra de color se
    achica — para caber en el panel angosto de Filtros embebido ahí."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    widget.mostrar_leyenda_colores(compacta=True)

    assert widget._leyenda_colores._columnas == 2
    assert widget._leyenda_colores._tamano_muestra == (28, 16)
    textos = _textos_leyenda_visibles(widget._leyenda_colores)
    assert "Profesional filtrado." in textos  # sigue mostrando todas las referencias


def test_mostrar_leyenda_colores_sin_compacta_mantiene_una_columna(qtbot, conn):
    """El resto de los usos (Oferta de consultorios) no pide `compacta` y
    tiene que seguir viéndose igual que siempre."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    widget.mostrar_leyenda_colores()

    assert widget._leyenda_colores._columnas == 1
    assert widget._leyenda_colores._tamano_muestra == (40, 24)


def test_agrandar_panel_filtros_cambia_el_ancho_maximo(qtbot, conn):
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget._panel_filtros.maximumWidth() == 260

    widget.agrandar_panel_filtros(290)

    assert widget._panel_filtros.maximumWidth() == 290


def test_agrupar_dias_en_pares_arma_una_grilla_de_2_columnas(qtbot, conn):
    """Pedido de la clienta: el filtro "Día de la semana" pasa de una
    lista vertical a una grilla de 2 columnas, sin perder ninguno de los
    checks ya construidos (siguen siendo los mismos objetos, solo
    cambian de contenedor)."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    checks_antes = dict(widget._checks_dia)

    widget.agrupar_dias_en_pares()

    assert widget._checks_dia == checks_antes
    grid = widget._contenedor_dias.layout()
    assert isinstance(grid, QGridLayout)
    dias = list(widget._checks_dia)
    for i, dia in enumerate(dias):
        check = widget._checks_dia[dia]
        assert isinstance(check, QCheckBox)
        indice = grid.indexOf(check)
        fila, columna, _, _ = grid.getItemPosition(indice)
        assert (fila, columna) == (i // 2, i % 2)


def test_fijar_titulo_filtros_vacio_saca_el_titulo(qtbot, conn):
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget._panel_filtros.title() == "Filtros"

    widget.fijar_titulo_filtros("")

    assert widget._panel_filtros.title() == ""


def test_renombrar_etiquetas_filtro_deja_profesional_como_estaba(qtbot, conn):
    """Pedido de la clienta al revisar Reservas: sin el título "Filtros",
    cada filtro individual pasa a nombrarse "Filtro de ..."; Profesional
    no lo pidió y se queda igual."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)

    widget.renombrar_etiquetas_filtro()

    assert widget._etiqueta_localidad.text() == "Filtro de localidad"
    assert widget._etiqueta_edificio.text() == "Filtro de edificio"
    assert widget._etiqueta_unidad.text() == "Filtro de unidad"
    assert widget._etiqueta_dia.text() == "Filtro de día de la semana"


def test_dar_stretch_a_detalle_pasa_el_estirado_de_la_grilla_al_cuadro_detalle(qtbot, conn):
    """Pedido de la clienta al revisar Reservas regulares ("que quede
    parejo" con la columna del formulario, más alta): en vez de que la
    grilla absorba cualquier alto de sobra (quedando con relleno en
    blanco debajo de la última hora), ese estirado pasa al cuadro
    "Detalle", que además deja de tener un alto máximo."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget._layout_grilla.stretch(widget._layout_grilla.indexOf(widget.tabla)) == 1
    assert widget.texto_detalle.maximumHeight() == 90

    widget.dar_stretch_a_detalle()

    assert widget._layout_grilla.stretch(widget._layout_grilla.indexOf(widget.tabla)) == 0
    assert widget._layout_grilla.stretch(widget._layout_grilla.indexOf(widget.texto_detalle)) == 1
    assert widget.texto_detalle.maximumHeight() > 90


def test_achicar_detalle_baja_el_alto_maximo(qtbot, conn):
    """Pedido de la clienta al revisar Reservas aisladas: acá es la
    columna de la grilla (no la del formulario) la que sobra en alto, así
    que se achica el cuadro "Detalle" para recuperar lugar."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget.texto_detalle.maximumHeight() == 90

    widget.achicar_detalle(40)

    assert widget.texto_detalle.maximumHeight() == 40


def test_extraer_detalle_saca_la_etiqueta_y_el_texto_de_la_grilla(qtbot, conn):
    """Pedido de la clienta al revisar Reservas aisladas: "Detalle" pasa a
    ocupar todo el ancho de la grilla (Filtros + grid), en vez de la
    columna angosta de la grilla nomás — para eso, primero hay que
    sacarlo del layout donde vive por default."""
    _preparar(conn)
    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    assert widget._layout_grilla.indexOf(widget._etiqueta_detalle) != -1
    assert widget._layout_grilla.indexOf(widget.texto_detalle) != -1

    etiqueta, texto = widget.extraer_detalle()

    assert etiqueta is widget._etiqueta_detalle
    assert texto is widget.texto_detalle
    assert widget._layout_grilla.indexOf(widget._etiqueta_detalle) == -1
    assert widget._layout_grilla.indexOf(widget.texto_detalle) == -1
