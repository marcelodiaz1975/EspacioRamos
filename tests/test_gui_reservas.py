import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.reservas import _FECHA_SIN_DATO, PantallaReservas
from app.negocio.dias import periodo_actual
from app.negocio.lista_espera import crear_pedido
from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def _preparar(conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.commit()


def test_crear_reserva_regular_sin_conflicto_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(1)
    pantalla.panel_regulares._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1
    assert pantalla.panel_regulares.tabla.rowCount() == 1


def test_crear_reserva_regular_con_varios_dias_tildados_crea_una_por_dia(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    panel._checks_dia["Martes"].setChecked(True)
    panel._checks_dia["Jueves"].setChecked(True)
    # Lunes ya viene tildado por defecto -> quedan 3 días en total
    panel._crear()

    dias = {
        f["DiaSemana"] for f in conn.execute("SELECT DiaSemana FROM ReservaRegular").fetchall()
    }
    assert dias == {"Lunes", "Martes", "Jueves"}
    assert panel.tabla.rowCount() == 3


def test_crear_reserva_regular_sin_ningun_dia_tildado_avisa_y_no_crea(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel._checks_dia["Lunes"].setChecked(False)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 0


def test_crear_reserva_regular_con_conflicto_en_un_dia_sigue_con_los_demas(qtbot, conn, monkeypatch):
    """Si uno de los días elegidos choca con OTRO profesional no
    relacionado (conflicto bloqueante) y el operador lo cancela
    (responde "No"), los demás días tildados que sí están libres igual
    se cargan."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=otro_profesional, IdConsultorio=id_consultorio, DiaSemana="Martes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel._checks_dia["Martes"].setChecked(True)  # Lunes ya viene tildado por defecto

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    panel._crear()  # Martes choca con "Otro" (conflicto bloqueante) y se cancela; Lunes es libre

    reservas_del_profesional = conn.execute(
        "SELECT DiaSemana FROM ReservaRegular WHERE IdProfesional = ?", (id_profesional,)
    ).fetchall()
    assert {f["DiaSemana"] for f in reservas_del_profesional} == {"Lunes"}
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 2  # el Lunes propio + el Martes de "Otro"


def test_crear_reserva_regular_resuelve_pedido_unico_de_lista_de_espera(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_pedido = crear_pedido(
        conn, id_profesional=id_profesional,
        bloques=[{"dias": ["Lunes"], "horario_desde": 9, "horario_hasta": 10}],
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(
        pantalla.panel_regulares.combo_profesional.findData(id_profesional)
    )
    pantalla.panel_regulares._crear()  # fixture responde "Yes" a cualquier QMessageBox.question

    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    assert pedido["Estado"] == "Resuelto"


def test_crear_reserva_regular_no_resuelve_pedido_si_operador_dice_que_no(qtbot, conn, monkeypatch):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_pedido = crear_pedido(
        conn, id_profesional=id_profesional,
        bloques=[{"dias": ["Lunes"], "horario_desde": 9, "horario_hasta": 10}],
    )
    conn.commit()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares._crear()

    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    assert pedido["Estado"] == "Activo"


def test_crear_reserva_regular_no_ofrece_resolver_con_mas_de_un_pedido_activo(qtbot, conn, monkeypatch):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    for _ in range(2):
        crear_pedido(
            conn, id_profesional=id_profesional,
            bloques=[{"dias": ["Lunes"], "horario_desde": 9, "horario_hasta": 10}],
        )
    conn.commit()
    preguntas = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: preguntas.append(a) or QMessageBox.StandardButton.Yes),
    )

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares._crear()

    assert preguntas == []  # con más de un pedido activo no se pregunta, queda manual
    estados = {p["Estado"] for p in obtener_repositorio(conn, "ListaEspera").listar(IdProfesional=id_profesional)}
    assert estados == {"Activo"}


def test_crear_reserva_regular_con_conflicto_pide_confirmacion_y_fuerza(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel._crear()  # primera reserva 9-10 Lunes

    # el alta anterior dejó el formulario en blanco -> hay que volver a
    # elegir el profesional para la segunda carga.
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel._crear()  # misma reserva de nuevo -> conflicto bloqueante
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 2  # forzada por QMessageBox mockeado


def test_crear_reserva_regular_regenera_liquidacion_enviada(qtbot, conn):
    """DC-08 §3.7: cargar una reserva regular tiene que regenerar sola la
    liquidación del período en curso si ya estaba Enviada, dejándola
    marcada como pendiente de reenvío."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    periodo = periodo_actual(conn)
    emitir_liquidacion(conn, id_profesional=id_profesional, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_profesional, periodo=periodo, enviada=True)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(
        pantalla.panel_regulares.combo_profesional.findData(id_profesional)
    )
    pantalla.panel_regulares._crear()

    emisiones = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    assert len(emisiones) == 2
    ultima = max(emisiones, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] == "Regenerada no enviada"


def test_finalizar_vigencia_regenera_liquidacion_enviada(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    periodo = periodo_actual(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(
        pantalla.panel_regulares.combo_profesional.findData(id_profesional)
    )
    pantalla.panel_regulares._crear()

    emitir_liquidacion(conn, id_profesional=id_profesional, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_profesional, periodo=periodo, enviada=True)
    conn.commit()

    emitidas_antes = len(
        obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    )
    pantalla.panel_regulares.tabla.selectRow(0)
    pantalla.panel_regulares._finalizar_vigencia()

    emisiones = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    assert len(emisiones) == emitidas_antes + 1
    ultima = max(emisiones, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] == "Regenerada no enviada"


def test_finalizar_vigencia_actualiza_vigenciafin_a_fin_de_mes(qtbot, conn):
    """"Finalizar reserva a fin de mes": el caso clásico — la vigencia
    se cierra el último día del mes en curso, no el día exacto en que se
    hace el trámite."""
    from app.negocio.dias import ultimo_dia_mes

    _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-10' WHERE IdConfiguracion = 1"
    )
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares.combo_profesional.setCurrentIndex(1)
    pantalla.panel_regulares._crear()
    pantalla.panel_regulares.tabla.selectRow(0)
    pantalla.panel_regulares._finalizar_vigencia()
    fila = conn.execute("SELECT VigenciaFin FROM ReservaRegular").fetchone()
    assert fila["VigenciaFin"] == ultimo_dia_mes(2026, 8).isoformat() == "2026-08-31"


def test_modificar_seleccionada_finaliza_la_vieja_y_precarga_el_formulario(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    panel._checks_dia["Martes"].setChecked(True)  # Lunes + Martes
    panel.spin_desde.setValue(14)
    panel.spin_hasta.setValue(16)
    panel._crear()  # crea Lunes 14-16 y Martes 14-16, formulario queda en blanco

    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    fila_lunes = next(
        i for i in range(panel.tabla.rowCount())
        if panel.tabla.item(i, 2).text() == "Lunes"
    )
    panel.tabla.selectRow(fila_lunes)
    panel._modificar_seleccionada()

    # la fila del Lunes quedó finalizada hoy, sin tocar la del Martes
    filas = conn.execute("SELECT DiaSemana, VigenciaFin FROM ReservaRegular").fetchall()
    finalizada = {f["DiaSemana"]: f["VigenciaFin"] for f in filas}
    assert finalizada["Lunes"] is not None
    assert finalizada["Martes"] is None

    # el formulario quedó precargado con esos datos, vigencia desde hoy
    assert panel.combo_profesional.currentData() == id_profesional
    assert panel.combo_consultorio.currentData() == id_consultorio
    assert {d for d, c in panel._checks_dia.items() if c.isChecked()} == {"Lunes"}
    assert panel.spin_desde.value() == 14
    assert panel.spin_hasta.value() == 16
    assert panel.campo_vigencia_fin.date() == _FECHA_SIN_DATO


def test_modificar_seleccionada_sin_fila_no_hace_nada(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel._modificar_seleccionada()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular WHERE VigenciaFin IS NOT NULL").fetchone()["c"] == 0


def test_modificar_seleccionada_permite_cargar_la_nueva_version(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    panel._crear()  # Lunes 9-10

    panel.tabla.selectRow(0)
    panel._modificar_seleccionada()
    panel.spin_hasta.setValue(12)  # el operador ajusta el horario de la nueva versión
    panel._crear()

    vigentes = conn.execute("SELECT HoraInicio, HoraFin FROM ReservaRegular WHERE VigenciaFin IS NULL").fetchall()
    assert len(vigentes) == 1
    assert vigentes[0]["HoraFin"] == 12


def test_crear_reserva_aislada_sin_conflicto_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1
    assert pantalla.panel_aisladas.tabla.item(0, 6).text() == "Confirmada"


def _monkeypatch_clipboard(monkeypatch):
    copiado = []
    monkeypatch.setattr(
        "app.gui.pantallas.reservas.QGuiApplication.clipboard",
        staticmethod(lambda: type("_C", (), {"setText": lambda self, t: copiado.append(t)})()),
    )
    return copiado


def test_crear_reserva_aislada_copia_mensaje_de_detalle_al_portapapeles(qtbot, conn, monkeypatch):
    _preparar(conn)
    copiado = _monkeypatch_clipboard(monkeypatch)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas._crear()
    assert len(copiado) == 1
    assert "DETALLE RESERVA" in copiado[0]


def test_cancelar_reserva_aislada_copia_mensaje_de_detalle_al_portapapeles(qtbot, conn, monkeypatch):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas.spin_desde.setValue(13)
    pantalla.panel_aisladas.spin_hasta.setValue(14)
    pantalla.panel_aisladas._crear()

    copiado = _monkeypatch_clipboard(monkeypatch)
    pantalla.panel_aisladas.tabla.selectRow(0)
    pantalla.panel_aisladas._cancelar()
    assert len(copiado) == 1
    assert "DETALLE RESERVA" in copiado[0]


def test_crear_reserva_aislada_fecha_mes_anterior_pide_confirmacion(qtbot, conn, monkeypatch):
    _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas.campo_fecha.setDate(QDate(2026, 7, 20))

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    pantalla.panel_aisladas._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 0

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    pantalla.panel_aisladas._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1


def test_grilla_preview_profesional_nuevo_no_muestra_nada(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares

    # el único profesional del fixture todavía no tiene nada reservado
    assert panel.grilla.ids_unidad_seleccionadas() == []
    assert panel.grilla.tabla.rowCount() == 0


def test_grilla_preview_acota_tambien_los_dias_a_los_que_tiene_reserva(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    repo_rr = obtener_repositorio(conn, "ReservaRegular")
    repo_rr.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=12, VigenciaInicio="2020-01-01",
    )
    repo_rr.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Jueves",
        HoraInicio=15, HoraFin=16, VigenciaInicio="2020-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))

    dias_tildados = {dia for dia, check in panel.grilla._checks_dia.items() if check.isChecked()}
    assert dias_tildados == {"Lunes", "Jueves"}


def test_formulario_vuelve_en_blanco_despues_de_crear(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_vigencia_fin.setDate(QDate(2026, 12, 31))
    panel._checks_dia["Martes"].setChecked(True)

    panel._crear()

    assert panel.combo_profesional.currentData() is None
    assert panel.combo_profesional.currentIndex() == 0
    assert panel.campo_vigencia_fin.date() == _FECHA_SIN_DATO
    assert {dia for dia, check in panel._checks_dia.items() if check.isChecked()} == {"Lunes"}
    assert panel.grilla.ids_unidad_seleccionadas() == []


def test_datos_complementarios_del_profesional(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=12, VigenciaInicio="2020-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    # el profesional elegido tiene la reserva Lunes 9-12 (3 horas), recién cargada
    assert "3" in panel.etiqueta_horas_semanales.text()
    assert "%" in panel.etiqueta_descuento.text()
    assert "%" in panel.etiqueta_vacaciones.text()

    panel.combo_profesional.setCurrentIndex(0)  # vuelve al placeholder en blanco
    assert panel.etiqueta_horas_semanales.text() == "Horas regulares semanales: —"
    assert panel.etiqueta_descuento.text() == "% Descuento: —"
    assert panel.etiqueta_vacaciones.text() == "% Vacaciones disponible: —"

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    assert panel.etiqueta_horas_semanales.text() == "Horas regulares semanales: 3"


def test_grilla_preview_sigue_al_profesional_no_al_consultorio_elegido(qtbot, conn):
    _preparar(conn)
    id_unidad_1 = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    id_consultorio_1 = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Sur')")
    id_otro_edificio = conn.execute("SELECT IdEdificio FROM Edificio WHERE Nombre = 'Torre Sur'").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '2B')", (id_otro_edificio,))
    id_unidad_2 = conn.execute("SELECT IdUnidad FROM Unidad WHERE Departamento = '2B'").fetchone()["IdUnidad"]
    id_consultorio_2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1)
    id_profesional_1 = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    conn.execute(
        "INSERT INTO ReservaRegular (IdProfesional, IdConsultorio, DiaSemana, HoraInicio, HoraFin, VigenciaInicio) "
        "VALUES (?, ?, 'Lunes', 9, 10, '2020-01-01')",
        (id_profesional_1, id_consultorio_1),
    )
    conn.execute(
        "INSERT INTO ReservaRegular (IdProfesional, IdConsultorio, DiaSemana, HoraInicio, HoraFin, VigenciaInicio) "
        "VALUES (?, ?, 'Martes', 10, 11, '2020-01-01')",
        (id_profesional_2, id_consultorio_2),
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional_1))

    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_1]

    # cambiar el consultorio elegido (edificio/unidad/consultorio en
    # cascada) para la PRÓXIMA alta no debe mover la vista previa: sigue
    # mostrando lo que el profesional 1 ya tiene.
    panel._seleccionar_ubicacion(id_consultorio_2)
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_1]

    # cambiar el PROFESIONAL sí la mueve, a lo que ese otro ya tiene reservado.
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional_2))
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_2]


def test_grilla_preview_pinta_azul_al_profesional_elegido(qtbot, conn):
    _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1'")  # el filtro de la grilla busca por código
    conn.commit()
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(
        next(i for i in range(panel.combo_profesional.count()) if panel.combo_profesional.itemData(i) == id_profesional)
    )
    panel._crear()  # reserva Lunes 9-10 para ese profesional/consultorio

    panel.combo_profesional.setCurrentIndex(
        next(i for i in range(panel.combo_profesional.count()) if panel.combo_profesional.itemData(i) == id_profesional)
    )
    from app.negocio.grilla_operativa import AZUL_OSCURO

    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    clave = (id_consultorio, "Lunes", 9)
    assert panel.grilla._resultado[clave].color_aro == AZUL_OSCURO


def test_grilla_preview_se_refresca_al_crear_una_reserva(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares

    # antes de la primera reserva del profesional, la vista previa está vacía
    assert panel.grilla.ids_unidad_seleccionadas() == []

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel._crear()

    # el formulario queda en blanco después del alta -> hay que volver a
    # elegir el profesional para ver reflejado lo que se acaba de cargar.
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    clave = (id_consultorio, "Lunes", 9)
    assert panel.grilla._resultado[clave].id_profesional_mostrado is not None


def test_cancelar_reserva_aislada_cambia_estado(qtbot, conn):
    # 13-14 cae fuera de los bloques rígidos por defecto (9-11 y 18-21) para
    # que la cancelación el mismo día no choque con esa restricción aparte.
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas.combo_profesional.setCurrentIndex(1)
    pantalla.panel_aisladas.spin_desde.setValue(13)
    pantalla.panel_aisladas.spin_hasta.setValue(14)
    pantalla.panel_aisladas._crear()
    pantalla.panel_aisladas.tabla.selectRow(0)
    pantalla.panel_aisladas._cancelar()
    fila = conn.execute("SELECT Estado FROM ReservaAislada").fetchone()
    assert fila["Estado"] == "Cancelada"


def test_panel_aisladas_grilla_arranca_en_modo_aislada(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_aisladas.grilla.combo_modo.currentData() == "aislada"


def test_panel_aisladas_grilla_preview_sigue_al_profesional(qtbot, conn):
    _preparar(conn)
    id_unidad_1 = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    id_consultorio_1 = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Sur')")
    id_otro_edificio = conn.execute("SELECT IdEdificio FROM Edificio WHERE Nombre = 'Torre Sur'").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '2B')", (id_otro_edificio,))
    id_unidad_2 = conn.execute("SELECT IdUnidad FROM Unidad WHERE Departamento = '2B'").fetchone()["IdUnidad"]
    id_consultorio_2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1)
    id_profesional_1 = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional_1, IdConsultorio=id_consultorio_1, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional_2, IdConsultorio=id_consultorio_2, Fecha="2026-08-18", HoraInicio=9, HoraFin=10,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional_1))
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_1]

    # cambiar el consultorio elegido para la PRÓXIMA alta no debe mover la
    # vista previa: sigue mostrando lo que el profesional 1 ya tiene.
    panel._seleccionar_ubicacion(id_consultorio_2)
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_1]

    # cambiar el PROFESIONAL sí la mueve, a lo que ese otro ya tiene reservado.
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional_2))
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_2]


def test_panel_aisladas_grilla_preview_pinta_azul_al_profesional_elegido(qtbot, conn):
    _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1'")  # el filtro de la grilla busca por código
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-17' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(
        next(i for i in range(panel.combo_profesional.count()) if panel.combo_profesional.itemData(i) == id_profesional)
    )
    panel.campo_fecha.setDate(QDate(2026, 8, 17))
    panel._crear()  # reserva aislada 9-10 ese día

    panel.combo_profesional.setCurrentIndex(
        next(i for i in range(panel.combo_profesional.count()) if panel.combo_profesional.itemData(i) == id_profesional)
    )

    from datetime import date

    from app.negocio.dias import fecha_a_dia_semana
    from app.negocio.grilla_operativa import AZUL_OSCURO

    dia = fecha_a_dia_semana(date(2026, 8, 17))
    clave = (id_consultorio, dia, 9)
    assert panel.grilla._resultado[clave].color_aro == AZUL_OSCURO


def test_panel_aisladas_grilla_preview_se_refresca_al_crear_una_reserva(qtbot, conn):
    _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-17' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.campo_fecha.setDate(QDate(2026, 8, 17))

    # antes de la primera reserva del profesional, la vista previa está vacía
    assert panel.grilla.ids_unidad_seleccionadas() == []

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel._crear()

    # el formulario queda en blanco después del alta -> hay que volver a
    # elegir el profesional para ver reflejado lo que se acaba de cargar.
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    from datetime import date

    from app.negocio.dias import fecha_a_dia_semana

    dia = fecha_a_dia_semana(date(2026, 8, 17))
    clave = (id_consultorio, dia, 9)
    assert panel.grilla._resultado[clave].id_profesional_mostrado is not None


def test_combo_profesional_regulares_solo_categorias_r_b_e(qtbot, conn):
    _preparar(conn)
    id_gomez = conn.execute("SELECT IdProfesional FROM Profesional WHERE Apellido = 'Gómez'").fetchone()["IdProfesional"]
    id_bono = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="B", Apellido="Bono")
    id_equipo = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="E", Apellido="Equipo")
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Ajeno")
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    combo = pantalla.panel_regulares.combo_profesional
    ids = {combo.itemData(i) for i in range(combo.count()) if combo.itemData(i) is not None}
    assert ids == {id_gomez, id_bono, id_equipo}


def test_combo_profesional_aisladas_solo_categorias_r_a(qtbot, conn):
    _preparar(conn)
    id_gomez = conn.execute("SELECT IdProfesional FROM Profesional WHERE Apellido = 'Gómez'").fetchone()["IdProfesional"]
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="B", Apellido="Bono")
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="E", Apellido="Equipo")
    id_ajeno = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Ajeno")
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    combo = pantalla.panel_aisladas.combo_profesional
    ids = {combo.itemData(i) for i in range(combo.count()) if combo.itemData(i) is not None}
    assert ids == {id_gomez, id_ajeno}


def test_combo_profesional_muestra_tratamiento_nombre_apellido(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, Tratamiento="Lic.", NombrePila="Virginia")
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    combo = pantalla.panel_regulares.combo_profesional
    indice = combo.findData(id_profesional)
    assert combo.itemText(indice) == "Lic. Virginia Gómez"


def test_combo_profesional_antepone_el_codigo_cuando_tiene(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    obtener_repositorio(conn, "Profesional").actualizar(
        id_profesional, Tratamiento="Lic.", NombrePila="Virginia", IdCodigo="R1",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    combo = pantalla.panel_regulares.combo_profesional
    indice = combo.findData(id_profesional)
    assert combo.itemText(indice) == "R1 - Lic. Virginia Gómez"


def test_filtros_edificio_unidad_acotan_el_combo_consultorio(qtbot, conn):
    _preparar(conn)
    id_edificio_2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Sur")
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_2, Departamento="2B")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1)
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=2)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares

    indice = panel.combo_edificio.findData(id_edificio_2)
    panel.combo_edificio.setCurrentIndex(indice)
    assert panel.combo_unidad.count() == 1
    assert panel.combo_unidad.currentData() == id_unidad_2
    assert panel.combo_consultorio.count() == 2


def test_spin_horario_aisladas_permite_medias_horas(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(1)
    assert panel.spin_desde.singleStep() == 0.5
    assert panel.spin_hasta.singleStep() == 0.5
    panel.spin_desde.setValue(9.5)
    panel.campo_fecha.setDate(QDate(2026, 8, 17))
    panel.spin_hasta.setValue(10.5)
    panel._crear()
    fila = conn.execute("SELECT HoraInicio, HoraFin FROM ReservaAislada").fetchone()
    assert fila["HoraInicio"] == 9.5
    assert fila["HoraFin"] == 10.5


def test_tabla_aisladas_ordenada_por_fecha_y_hora(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    repo = obtener_repositorio(conn, "ReservaAislada")
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-20", HoraInicio=9, HoraFin=10)
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=14, HoraFin=15)
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=9, HoraFin=10)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    filas = [
        (panel.tabla.item(f, 2).text(), panel.tabla.item(f, 3).text(), panel.tabla.item(f, 4).text())
        for f in range(panel.tabla.rowCount())
    ]
    assert filas == [
        ("Martes", "18-08-2026", "9:00 a 10:00"),
        ("Martes", "18-08-2026", "14:00 a 15:00"),
        ("Jueves", "20-08-2026", "9:00 a 10:00"),
    ]


def test_tabla_aisladas_columna_valor(qtbot, conn):
    _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-10' WHERE IdConfiguracion = 1"
    )
    conn.execute("UPDATE Consultorio SET ValorHoraAisladaActual = 1000")
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    repo = obtener_repositorio(conn, "ReservaAislada")
    # dentro del período actual (2026-08) -> tiene valor
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=11)
    # período posterior al actual -> sin valor
    repo.crear(IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-09-17", HoraInicio=9, HoraFin=10)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    from app.negocio.formato import formatear_moneda

    valores = {panel.tabla.item(f, 3).text(): panel.tabla.item(f, 7).text() for f in range(panel.tabla.rowCount())}
    assert valores["17-08-2026"] == formatear_moneda(2000)
    assert valores["17-09-2026"] == ""


def test_datos_complementarios_aisladas_incluye_horas_aisladas_mensuales(qtbot, conn):
    _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-10' WHERE IdConfiguracion = 1"
    )
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=11,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    assert panel.etiqueta_horas_aisladas.text() == "Horas aisladas mensuales: 2"


def test_spin_horario_se_muestra_como_reloj(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)

    panel_r = pantalla.panel_regulares
    panel_r.spin_desde.setValue(9)
    assert panel_r.spin_desde.textFromValue(9) == "9:00"

    panel_a = pantalla.panel_aisladas
    panel_a.spin_desde.setValue(14.5)
    assert panel_a.spin_desde.textFromValue(14.5) == "14:30"
    assert panel_a.spin_desde.valueFromText("14:30") == 14.5


def test_campos_de_fecha_usan_formato_dd_mm_yyyy(qtbot, conn):
    """El selector de fecha (con calendario) ya deja ver el día de la
    semana por su cuenta, así que no hace falta una aclaración aparte
    debajo — alcanza con que el formato de todos los campos de fecha sea
    consistente en las dos solapas."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)

    panel_r = pantalla.panel_regulares
    assert panel_r.campo_vigencia_inicio.displayFormat() == "dd-MM-yyyy"
    assert panel_r.campo_vigencia_fin.displayFormat() == "dd-MM-yyyy"
    assert panel_r.campo_vigencia_inicio.calendarPopup() is True

    panel_a = pantalla.panel_aisladas
    assert panel_a.campo_fecha.displayFormat() == "dd-MM-yyyy"
    assert panel_a.campo_fecha.calendarPopup() is True
    assert panel_a.campo_fecha_ausencia.displayFormat() == "dd-MM-yyyy"


def test_grilla_preview_no_tiene_scroll_interno_al_elegir_profesional(qtbot, conn):
    """Hallazgo: la grilla se veía cortada con scrollbar interno al elegir
    profesional. El alto mínimo de la tabla, calculado con la suma exacta
    de sus filas, tiene que alcanzar para mostrarla entera."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))

    tabla = panel.grilla.tabla
    assert tabla.rowCount() > 0
    alto_filas = sum(tabla.rowHeight(f) for f in range(tabla.rowCount()))
    assert tabla.minimumHeight() >= alto_filas


def test_tablas_de_abajo_muestran_tratamiento_nombre_apellido_y_columna_ancha(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, Tratamiento="Lic.", NombrePila="Virginia")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)

    tabla_r = pantalla.panel_regulares.tabla
    assert tabla_r.item(0, 0).text() == "Lic. Virginia Gómez"
    assert tabla_r.columnWidth(0) >= 180
    assert tabla_r.item(0, 3).text() == "9:00 a 10:00"

    tabla_a = pantalla.panel_aisladas.tabla
    assert tabla_a.item(0, 0).text() == "Lic. Virginia Gómez"
    assert tabla_a.columnWidth(0) >= 180
    assert tabla_a.item(0, 4).text() == "9:00 a 10:00"


def test_reubicacion_ofrece_horario_regular_y_registra_ausencia(qtbot, conn):
    """Al marcar "Es reubicación" en Aisladas, el formulario tiene que
    ofrecer elegir cuál de los horarios regulares del profesional no va a
    usar esta vez, y al confirmar dejarlo registrado como Ausencia de ese
    consultorio en la fecha indicada (así queda libre para otro
    profesional, sin tocar la reserva regular)."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    otro_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=2)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.combo_consultorio.setCurrentIndex(panel.combo_consultorio.findData(otro_consultorio))
    panel.campo_fecha.setDate(QDate(2026, 8, 22))  # sábado: no choca con el regular del lunes

    panel.casilla_reubicacion.setChecked(True)
    assert panel.contenedor_reubicacion.isHidden() is False
    indice = panel.combo_horario_no_usado.findData(id_consultorio)
    assert indice > 0  # existe una opción con el consultorio de la reserva regular
    panel.combo_horario_no_usado.setCurrentIndex(indice)
    panel.campo_fecha_ausencia.setDate(QDate(2026, 8, 24))  # el lunes siguiente que se va a saltear

    panel._crear()

    ausencia = conn.execute("SELECT * FROM Ausencia WHERE IdProfesional = ?", (id_profesional,)).fetchone()
    assert ausencia is not None
    assert ausencia["IdConsultorio"] == id_consultorio
    assert ausencia["FechaDesde"] == "2026-08-24"
    assert ausencia["FechaHasta"] == "2026-08-24"
    assert ausencia["Motivo"] == "Reubicación"
    reserva_aislada = conn.execute(
        "SELECT IdReservaAislada FROM ReservaAislada WHERE IdConsultorio = ?", (otro_consultorio,)
    ).fetchone()
    assert ausencia["IdReservaAislada"] == reserva_aislada["IdReservaAislada"]

    # el formulario queda en blanco y el cuadro de reubicación oculto de nuevo
    assert panel.casilla_reubicacion.isChecked() is False
    assert panel.contenedor_reubicacion.isHidden() is True


def test_reubicacion_sin_elegir_horario_no_crea_ausencia(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.casilla_reubicacion.setChecked(True)  # "Sin especificar" queda seleccionado por defecto

    panel._crear()

    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 0


def test_regulares_ya_no_tiene_casilla_de_excepcion(qtbot, conn):
    """"Es excepción" se sacó del formulario de Regulares: lo que
    pretendía cubrir ahora se maneja con "Es reubicación" en Aisladas."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert not hasattr(pantalla.panel_regulares, "casilla_excepcion")


def test_dia_de_la_semana_en_tabla_de_aisladas(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=9, HoraFin=10,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    assert panel.tabla.horizontalHeaderItem(2).text() == "Día"
    assert panel.tabla.item(0, 2).text() == "Martes"
    assert panel.tabla.item(0, 3).text() == "18-08-2026"


def test_modificar_reserva_aislada_cancela_la_vieja_y_precarga_el_formulario(qtbot, conn):
    """Para corregir algo de una reserva aislada ya cargada (ej. le
    encargaron una hora más de lo que habían pedido en un principio): se
    cancela la fila vieja (queda su historial, no se borra ni se edita
    in-place) y se precarga el formulario para dar de alta la versión
    corregida."""
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_fecha.setDate(QDate(2026, 8, 18))
    panel.spin_desde.setValue(9)
    panel.spin_hasta.setValue(10)
    panel._crear()

    panel.tabla.selectRow(0)
    panel._modificar_seleccionada()

    fila = conn.execute("SELECT Estado FROM ReservaAislada").fetchone()
    assert fila["Estado"] == "Cancelada"

    assert panel.combo_profesional.currentData() == id_profesional
    assert panel.combo_consultorio.currentData() == id_consultorio
    assert panel.campo_fecha.date() == QDate(2026, 8, 18)
    assert panel.spin_desde.value() == 9
    assert panel.spin_hasta.value() == 10

    panel.spin_hasta.setValue(11)  # el ajuste que pedían: una hora más
    panel._crear()

    vigentes = conn.execute("SELECT HoraInicio, HoraFin FROM ReservaAislada WHERE Estado = 'Confirmada'").fetchall()
    assert len(vigentes) == 1
    assert vigentes[0]["HoraFin"] == 11


def test_modificar_reserva_aislada_sin_fila_avisa(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas._modificar_seleccionada()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 0


def test_modificar_reserva_aislada_al_confirmar_regenera_mensaje_al_portapapeles(qtbot, conn, monkeypatch):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_fecha.setDate(QDate(2026, 8, 18))
    panel._crear()

    copiado = _monkeypatch_clipboard(monkeypatch)
    panel.tabla.selectRow(0)
    panel._modificar_seleccionada()
    panel.spin_hasta.setValue(12)  # el ajuste que pedían
    panel._crear()

    # se copia el mensaje al cancelar la vieja y de nuevo al confirmar la
    # corregida
    assert len(copiado) == 2
    assert "DETALLE RESERVA" in copiado[-1]


def test_columna_reubicacion_en_tabla_de_aisladas(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-18",
        HoraInicio=9, HoraFin=10, EsReubicacion=1,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha="2026-08-19",
        HoraInicio=9, HoraFin=10, EsReubicacion=0,
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    assert panel.tabla.horizontalHeaderItem(5).text() == "Reubicación"
    assert panel.tabla.horizontalHeaderItem(6).text() == "Estado"
    valores = {panel.tabla.item(f, 3).text(): panel.tabla.item(f, 5).text() for f in range(panel.tabla.rowCount())}
    assert valores["18-08-2026"] == "Sí"
    assert valores["19-08-2026"] == "No"
    # el Estado ya no repite la aclaración de reubicación (queda en su propia columna)
    assert panel.tabla.item(0, 6).text() == "Confirmada"


def test_campo_profesional_de_la_grilla_usa_el_mismo_formato(qtbot, conn):
    from app.gui.widgets.grilla_operativa import GrillaOperativaWidget

    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", DomicilioLocalidad="Ramos Mejía")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    id_virginia = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lo Veci", NombrePila="Virginia", Tratamiento="Lic.", IdCodigo="R1",
    )
    conn.commit()

    widget = GrillaOperativaWidget(conn)
    qtbot.addWidget(widget)
    texto = next(t for t, i in widget._profesionales_por_texto.items() if i == id_virginia)
    assert texto == "R1 - Lic. Virginia Lo Veci"


def _preparar_dos_localidades(conn):
    """Dos localidades, cada una con un edificio y un consultorio —
    para probar el filtro de Localidad y el formato "Localidad -
    Edificio - Unidad - Consultorio" de la columna Consultorio."""
    id_edificio_1 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", DomicilioLocalidad="Ramos Mejía")
    id_unidad_1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_1, Departamento='7mo "L"')
    id_consultorio_1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_1, NumeroConsultorio=1)

    id_edificio_2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Haedo Centro", DomicilioLocalidad="Haedo")
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_2, Departamento="PB")
    id_consultorio_2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1)

    id_profesional = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Gómez", IdCodigo="R1",
    )
    conn.commit()
    return id_edificio_1, id_consultorio_1, id_edificio_2, id_consultorio_2, id_profesional


def test_combo_localidad_filtra_el_combo_edificio_en_ambas_solapas(qtbot, conn):
    id_edificio_1, _, id_edificio_2, _, _ = _preparar_dos_localidades(conn)

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    for panel in (pantalla.panel_regulares, pantalla.panel_aisladas):
        assert panel.combo_localidad.count() == 2

        indice = panel.combo_localidad.findData("Haedo")
        panel.combo_localidad.setCurrentIndex(indice)
        assert panel.combo_edificio.count() == 1
        assert panel.combo_edificio.currentData() == id_edificio_2

        indice = panel.combo_localidad.findData("Ramos Mejía")
        panel.combo_localidad.setCurrentIndex(indice)
        assert panel.combo_edificio.count() == 1
        assert panel.combo_edificio.currentData() == id_edificio_1


def test_texto_consultorio_omite_localidad_y_edificio_si_hay_uno_solo(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    # una sola localidad (ninguna, en este fixture) y un solo edificio ("Torre Norte") -> se omiten los dos
    assert pantalla.panel_regulares.tabla.item(0, 1).text() == '1A - 1'


def test_texto_consultorio_incluye_localidad_y_edificio_si_hay_varios(qtbot, conn):
    id_edificio_1, id_consultorio_1, id_edificio_2, id_consultorio_2, id_profesional = _preparar_dos_localidades(conn)
    repo = obtener_repositorio(conn, "ReservaRegular")
    repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio_1, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio_2, DiaSemana="Martes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2026-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.panel_regulares.tabla
    textos = {tabla.item(f, 1).text() for f in range(tabla.rowCount())}
    assert textos == {'Ramos Mejía - Ramos 1 - 7mo "L" - 1', "Haedo - Haedo Centro - PB - 1"}


def test_tabla_regulares_sin_profesional_muestra_solo_vigentes_de_todos(qtbot, conn):
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_vigente = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_finalizado = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ex Profesional")
    repo = obtener_repositorio(conn, "ReservaRegular")
    repo.crear(
        IdProfesional=id_vigente, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    repo.crear(
        IdProfesional=id_finalizado, IdConsultorio=id_consultorio, DiaSemana="Martes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01", VigenciaFin="2020-06-30",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(0)  # placeholder: sin profesional elegido
    dias = {panel.tabla.item(f, 2).text() for f in range(panel.tabla.rowCount())}
    assert dias == {"Lunes"}  # la de Martes ya terminó en 2020 -> no aparece


def test_tabla_regulares_con_profesional_muestra_toda_su_historia(qtbot, conn):
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    repo = obtener_repositorio(conn, "ReservaRegular")
    repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Martes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01", VigenciaFin="2020-06-30",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    dias = {panel.tabla.item(f, 2).text() for f in range(panel.tabla.rowCount())}
    assert dias == {"Lunes", "Martes"}  # incluye la ya finalizada, para poder revisar su historia


def test_tabla_regulares_orden_por_codigo_dia_y_hora(qtbot, conn):
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    conn.execute("UPDATE Profesional SET IdCodigo = 'B1'")  # el de _preparar
    id_a1 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ajeno", IdCodigo="A1")
    repo = obtener_repositorio(conn, "ReservaRegular")
    id_b1 = conn.execute("SELECT IdProfesional FROM Profesional WHERE IdCodigo = 'B1'").fetchone()["IdProfesional"]
    repo.crear(
        IdProfesional=id_b1, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    repo.crear(
        IdProfesional=id_a1, IdConsultorio=id_consultorio, DiaSemana="Martes",
        HoraInicio=9, HoraFin=10, VigenciaInicio="2020-01-01",
    )
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    codigos = [panel.tabla.item(f, 0).text().split(" - ")[0] for f in range(panel.tabla.rowCount())]
    assert codigos == ["A1", "B1"]  # A1 antes que B1, aunque B1 se haya cargado primero


def test_tabla_aisladas_sin_profesional_muestra_todas_de_todos(qtbot, conn):
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional_1 = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    repo = obtener_repositorio(conn, "ReservaAislada")
    repo.crear(IdProfesional=id_profesional_1, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=9, HoraFin=10)
    repo.crear(IdProfesional=id_profesional_2, IdConsultorio=id_consultorio, Fecha="2026-08-19", HoraInicio=9, HoraFin=10)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(0)  # placeholder: sin profesional elegido
    assert panel.tabla.rowCount() == 2


def test_tabla_aisladas_con_profesional_acota_a_sus_reservas(qtbot, conn):
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_profesional_1 = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    repo = obtener_repositorio(conn, "ReservaAislada")
    repo.crear(IdProfesional=id_profesional_1, IdConsultorio=id_consultorio, Fecha="2026-08-18", HoraInicio=9, HoraFin=10)
    repo.crear(IdProfesional=id_profesional_2, IdConsultorio=id_consultorio, Fecha="2026-08-19", HoraInicio=9, HoraFin=10)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional_1))
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 3).text() == "18-08-2026"


def test_tabla_aisladas_orden_por_codigo_fecha_y_hora(qtbot, conn):
    _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    conn.execute("UPDATE Profesional SET IdCodigo = 'B1'")
    id_a1 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ajeno", IdCodigo="A1")
    id_b1 = conn.execute("SELECT IdProfesional FROM Profesional WHERE IdCodigo = 'B1'").fetchone()["IdProfesional"]
    repo = obtener_repositorio(conn, "ReservaAislada")
    repo.crear(IdProfesional=id_b1, IdConsultorio=id_consultorio, Fecha="2026-08-17", HoraInicio=9, HoraFin=10)
    repo.crear(IdProfesional=id_a1, IdConsultorio=id_consultorio, Fecha="2026-08-19", HoraInicio=9, HoraFin=10)
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    codigos = [panel.tabla.item(f, 0).text().split(" - ")[0] for f in range(panel.tabla.rowCount())]
    assert codigos == ["A1", "B1"]


def test_combo_profesional_arranca_en_blanco_en_ambas_solapas(qtbot, conn):
    """El combo de profesional ya no se auto-completa con el primero de
    la lista al abrir la pantalla: tiene que arrancar en el placeholder,
    para que el cuadro de abajo muestre "todos los profesionales" hasta
    que el operador elija uno."""
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_regulares.combo_profesional.currentIndex() == 0
    assert pantalla.panel_regulares.combo_profesional.currentData() is None
    assert pantalla.panel_aisladas.combo_profesional.currentIndex() == 0
    assert pantalla.panel_aisladas.combo_profesional.currentData() is None
