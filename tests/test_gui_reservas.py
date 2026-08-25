import pytest
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.reservas import PantallaReservas
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
    pantalla.panel_regulares._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaRegular").fetchone()["c"] == 1
    assert pantalla.panel_regulares.tabla.rowCount() == 1


def test_crear_reserva_regular_con_varios_dias_tildados_crea_una_por_dia(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
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


def test_finalizar_vigencia_actualiza_vigenciafin(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares._crear()
    pantalla.panel_regulares.tabla.selectRow(0)
    pantalla.panel_regulares._finalizar_vigencia()
    fila = conn.execute("SELECT VigenciaFin FROM ReservaRegular").fetchone()
    assert fila["VigenciaFin"] is not None


def test_modificar_seleccionada_finaliza_la_vieja_y_precarga_el_formulario(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel._checks_dia["Martes"].setChecked(True)  # Lunes + Martes
    panel.spin_desde.setValue(14)
    panel.spin_hasta.setValue(16)
    panel.casilla_excepcion.setChecked(True)
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
    assert panel.casilla_excepcion.isChecked() is True
    assert panel.campo_vigencia_fin.text() == ""


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
    pantalla.panel_aisladas._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1
    assert pantalla.panel_aisladas.tabla.item(0, 4).text() == "Confirmada"


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
    pantalla.panel_aisladas._crear()
    assert len(copiado) == 1
    assert "DETALLE RESERVA" in copiado[0]


def test_cancelar_reserva_aislada_copia_mensaje_de_detalle_al_portapapeles(qtbot, conn, monkeypatch):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
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
    pantalla.panel_aisladas.campo_fecha.setText("2026-07-20")

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

    dias_tildados = {dia for dia, check in panel.grilla._checks_dia.items() if check.isChecked()}
    assert dias_tildados == {"Lunes", "Jueves"}


def test_formulario_vuelve_en_blanco_despues_de_crear(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_regulares
    panel.campo_vigencia_fin.setText("2026-12-31")
    panel.casilla_excepcion.setChecked(True)
    panel._checks_dia["Martes"].setChecked(True)

    panel._crear()

    assert panel.combo_profesional.currentData() is None
    assert panel.combo_profesional.currentIndex() == 0
    assert panel.campo_vigencia_fin.text() == ""
    assert panel.casilla_excepcion.isChecked() is False
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
    # el único profesional (con la reserva Lunes 9-12, 3 horas, recién
    # cargada) arranca seleccionado por defecto.
    assert "3" in panel.etiqueta_horas_semanales.text()
    assert "%" in panel.etiqueta_descuento.text()
    assert "%" in panel.etiqueta_vacaciones.text()

    panel.combo_profesional.setCurrentIndex(0)  # vuelve al placeholder en blanco
    assert panel.etiqueta_horas_semanales.text() == "Horas semanales: —"
    assert panel.etiqueta_descuento.text() == "% Descuento: —"
    assert panel.etiqueta_vacaciones.text() == "% Vacaciones disponible: —"

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    assert panel.etiqueta_horas_semanales.text() == "Horas semanales: 3"


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

    # cambiar el consultorio elegido para la PRÓXIMA alta no debe mover la
    # vista previa: sigue mostrando lo que el profesional 1 ya tiene.
    panel.combo_consultorio.setCurrentIndex(
        next(i for i in range(panel.combo_consultorio.count()) if panel.combo_consultorio.itemData(i) == id_consultorio_2)
    )
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


def test_panel_aisladas_grilla_preview_se_acota_al_consultorio_elegido(qtbot, conn):
    _preparar(conn)
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Sur')")
    id_otro_edificio = conn.execute("SELECT IdEdificio FROM Edificio WHERE Nombre = 'Torre Sur'").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '2B')", (id_otro_edificio,))
    id_otra_unidad = conn.execute("SELECT IdUnidad FROM Unidad WHERE Departamento = '2B'").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_otra_unidad,))
    conn.commit()

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad]

    indice_otro_consultorio = next(
        i for i in range(panel.combo_consultorio.count())
        if panel.combo_consultorio.itemData(i) != panel.combo_consultorio.currentData()
    )
    panel.combo_consultorio.setCurrentIndex(indice_otro_consultorio)
    assert panel.grilla.ids_unidad_seleccionadas() == [id_otra_unidad]


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
    panel.campo_fecha.setText("2026-08-17")
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
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]

    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_aisladas
    panel.campo_fecha.setText("2026-08-17")

    from datetime import date

    from app.negocio.dias import fecha_a_dia_semana

    dia = fecha_a_dia_semana(date(2026, 8, 17))
    clave = (id_consultorio, dia, 9)
    assert panel.grilla._resultado[clave].id_profesional_mostrado is None

    panel._crear()

    assert panel.grilla._resultado[clave].id_profesional_mostrado is not None
