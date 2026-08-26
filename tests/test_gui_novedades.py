import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.novedades import PantallaCargosEspeciales, PantallaRegistroAusencias
from app.negocio.ausencias import crear_ausencia
from app.negocio.dias import periodo_actual
from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio
from app.negocio.reservas import crear_reserva_aislada
from app.repositorio.registro import obtener_repositorio


def _fecha(iso: str) -> QDate:
    return QDate.fromString(iso, "yyyy-MM-dd")


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


def _preparar(conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute(
        "INSERT INTO Consultorio (IdUnidad, NumeroConsultorio, ValorHoraRegularActual) VALUES (?, 1, 1000)",
        (id_unidad,),
    )
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    conn.execute(
        "INSERT INTO ReservaRegular (IdProfesional, IdConsultorio, DiaSemana, HoraInicio, HoraFin, VigenciaInicio) "
        "VALUES (?, ?, 'Lunes', 9, 12, '2020-01-01')",
        (id_profesional, id_consultorio),
    )
    conn.commit()
    return id_profesional


def test_crear_vacacion_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 1


def test_crear_vacacion_regenera_liquidacion_enviada(qtbot, conn):
    """DC-08 §4.6: registrar una vacación tiene que regenerar sola la
    liquidación del período en curso si ya estaba Enviada."""
    id_profesional = _preparar(conn)
    periodo = periodo_actual(conn)
    emitir_liquidacion(conn, id_profesional=id_profesional, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_profesional, periodo=periodo, enviada=True)
    conn.commit()

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()

    emisiones = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    assert len(emisiones) == 2
    ultima = max(emisiones, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] == "Regenerada no enviada"
    assert panel.tabla.rowCount() == 1


def test_crear_licencia_sin_tipo_no_falla(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-03"))
    panel._crear()  # hay tipos de licencia sembrados por defecto
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 1


def test_crear_ausencia_persiste(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-03"))
    panel.combo_motivo.setEditText("Congreso")
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 1
    assert panel.tabla.item(0, 3).text() == "Todo el día"
    assert panel.tabla.item(0, 4).text() == "Congreso"


def test_cancelar_vacacion_seleccionada_elimina(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 1

    panel.tabla.selectRow(0)
    panel._cancelar()
    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 0


def test_cancelar_vacacion_bloqueada_por_aislada_muestra_advertencia(qtbot, conn, monkeypatch):
    """DC-04 §3.2/§3.3: si ya hay una aislada de otro profesional asignada
    en el consultorio que la vacación liberó, anularla tiene que avisar y
    no borrar el registro."""
    id_profesional = _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Otro")
    conn.commit()

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()
    crear_reserva_aislada(
        conn, id_profesional=otro_profesional, id_consultorio=id_consultorio,
        fecha="2026-09-07", hora_inicio=9, hora_fin=10,
    )
    conn.commit()

    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda self, titulo, texto: avisos.append(texto)))
    panel.tabla.selectRow(0)
    panel._cancelar()
    assert len(avisos) == 1
    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 1


def test_cancelar_licencia_seleccionada_elimina(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 1

    panel.tabla.selectRow(0)
    panel._cancelar()
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 0


def test_cancelar_licencia_bloqueada_por_aislada_muestra_advertencia(qtbot, conn, monkeypatch):
    id_profesional = _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Otro")
    conn.commit()

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()
    crear_reserva_aislada(
        conn, id_profesional=otro_profesional, id_consultorio=id_consultorio,
        fecha="2026-09-07", hora_inicio=9, hora_fin=10,
    )
    conn.commit()

    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda self, titulo, texto: avisos.append(texto)))
    panel.tabla.selectRow(0)
    panel._cancelar()
    assert len(avisos) == 1
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 1


def test_cancelar_ausencia_seleccionada_elimina(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel.combo_motivo.setEditText("Congreso")
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 1

    panel.tabla.selectRow(0)
    panel._cancelar()
    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 0


def test_modificar_ausencia_sin_seleccion_no_falla(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel._modificar_seleccionada()  # nada seleccionado -> no debe romper


def test_modificar_ausencia_seleccionada_anula_y_precarga_formulario(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel.combo_motivo.setEditText("Congreso")
    panel.grupo_horario.setChecked(True)
    panel.spin_hora_desde.setValue(9)
    panel.spin_hora_hasta.setValue(10)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 1

    # deselecciona el profesional para confirmar que la precarga lo vuelve a fijar
    panel.combo_profesional.setCurrentIndex(0)
    panel.tabla.selectRow(0)
    panel._modificar_seleccionada()

    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 0  # anulada, no editada in-place
    assert panel.combo_profesional.currentData() == id_profesional
    assert panel.combo_motivo.currentText() == "Congreso"
    assert panel.campo_desde.date() == _fecha("2026-09-07")
    assert panel.campo_hasta.date() == _fecha("2026-09-07")
    assert panel.grupo_horario.isChecked() is True
    assert (panel.spin_hora_desde.value(), panel.spin_hora_hasta.value()) == (9, 10)

    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 1


def test_modificar_ausencia_bloqueada_por_aislada_muestra_advertencia(qtbot, conn, monkeypatch):
    id_profesional = _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Otro")
    conn.commit()

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel.combo_motivo.setEditText("Congreso")
    panel._crear()
    crear_reserva_aislada(
        conn, id_profesional=otro_profesional, id_consultorio=id_consultorio,
        fecha="2026-09-07", hora_inicio=9, hora_fin=10,
    )
    conn.commit()

    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda self, titulo, texto: avisos.append(texto)))
    panel.tabla.selectRow(0)
    panel._modificar_seleccionada()
    assert len(avisos) == 1
    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 1


def test_tabla_ausencias_muestra_origen_de_reubicacion(qtbot, conn):
    id_profesional = _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_reserva, _ = crear_reserva_aislada(
        conn, id_profesional=id_profesional, id_consultorio=id_consultorio,
        fecha="2026-08-10", hora_inicio=9, hora_fin=10,
    )
    crear_ausencia(
        conn, id_profesional=id_profesional, fecha_desde="2026-08-17", fecha_hasta="2026-08-17",
        id_consultorio=id_consultorio, motivo="Reubicación", id_reserva_aislada=id_reserva,
    )
    crear_ausencia(conn, id_profesional=id_profesional, fecha_desde="2026-09-01", fecha_hasta="2026-09-05")
    conn.commit()

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    assert panel.tabla.horizontalHeaderItem(5).text() == "Origen"
    origenes = {panel.tabla.item(f, 1).text(): panel.tabla.item(f, 5).text() for f in range(panel.tabla.rowCount())}
    assert origenes["17-08-2026"] == "Reubicación (aislada del 2026-08-10)"
    assert origenes["01-09-2026"] == ""


def test_cancelar_ausencia_bloqueada_por_aislada_muestra_advertencia(qtbot, conn, monkeypatch):
    id_profesional = _preparar(conn)
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Otro")
    conn.commit()

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel.combo_motivo.setEditText("Congreso")
    panel._crear()
    crear_reserva_aislada(
        conn, id_profesional=otro_profesional, id_consultorio=id_consultorio,
        fecha="2026-09-07", hora_inicio=9, hora_fin=10,
    )
    conn.commit()

    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda self, titulo, texto: avisos.append(texto)))
    panel.tabla.selectRow(0)
    panel._cancelar()
    assert len(avisos) == 1
    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 1


def test_panel_vacaciones_grilla_preview_acota_y_pinta_azul(qtbot, conn):
    id_profesional = _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1'")  # el filtro de la grilla busca por código
    conn.commit()
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))

    from app.negocio.grilla_operativa import AZUL_OSCURO

    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad]
    assert panel.grilla._resultado[(id_consultorio, "Lunes", 9)].color_aro == AZUL_OSCURO


def test_panel_licencias_grilla_preview_acota_y_pinta_azul(qtbot, conn):
    id_profesional = _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1'")  # el filtro de la grilla busca por código
    conn.commit()
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))

    from app.negocio.grilla_operativa import AZUL_OSCURO

    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad]
    assert panel.grilla._resultado[(id_consultorio, "Lunes", 9)].color_aro == AZUL_OSCURO


def test_panel_ausencias_grilla_preview_acota_y_pinta_azul(qtbot, conn):
    id_profesional = _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1'")  # el filtro de la grilla busca por código
    conn.commit()
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))

    from app.negocio.grilla_operativa import AZUL_OSCURO

    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad]
    assert panel.grilla._resultado[(id_consultorio, "Lunes", 9)].color_aro == AZUL_OSCURO


def test_panel_vacaciones_grilla_sin_profesional_con_reservas_muestra_todo(qtbot, conn):
    """Un profesional sin ninguna reserva regular todavía no tiene
    unidades para acotar -> la vista previa vuelve a mostrar todas."""
    _preparar(conn)
    id_unidad_1 = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    otro_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Sur")
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=otro_edificio, Departamento="2B")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Sin Reservas")
    conn.commit()

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(otro_profesional))

    assert set(panel.grilla.ids_unidad_seleccionadas()) == {id_unidad_1, id_unidad_2}


def test_combo_profesional_ausencias_usa_formato_de_reservas(qtbot, conn):
    _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1', Tratamiento = 'Lic.'")
    conn.commit()
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    assert panel.combo_profesional.itemText(0) == "Seleccionar profesional…"
    assert panel.combo_profesional.itemData(0) is None
    assert panel.combo_profesional.itemText(1) == "R1 - Lic. Gómez"


def test_horario_puntual_se_habilita_solo_con_un_unico_dia(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))

    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-05"))
    panel._actualizar_disponibilidad_horario()
    assert panel.grupo_horario.isEnabled() is False

    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel._actualizar_disponibilidad_horario()
    assert panel.grupo_horario.isEnabled() is True


def test_crear_ausencia_con_horario_puntual_persiste_y_se_ve_en_la_tabla(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel._actualizar_disponibilidad_horario()
    panel.grupo_horario.setChecked(True)
    panel.spin_hora_desde.setValue(9)
    panel.spin_hora_hasta.setValue(10)
    panel._crear()

    ausencia = conn.execute("SELECT HoraInicio, HoraFin FROM Ausencia").fetchone()
    assert (ausencia["HoraInicio"], ausencia["HoraFin"]) == (9, 10)
    assert panel.tabla.item(0, 3).text() == "9:00 a 10:00"


def test_tabla_ausencias_filtra_por_profesional_seleccionado(qtbot, conn):
    id_profesional = _preparar(conn)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Otro")
    conn.commit()
    crear_ausencia(conn, id_profesional=id_profesional, fecha_desde="2026-09-01", fecha_hasta="2026-09-01")
    crear_ausencia(conn, id_profesional=otro_profesional, fecha_desde="2026-09-02", fecha_hasta="2026-09-02")
    conn.commit()

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    assert panel.tabla.rowCount() == 2

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 1).text() == "01-09-2026"


def test_panel_ausencias_grilla_resalta_verde_donde_hay_ausencia(qtbot, conn):
    id_profesional = _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1'")  # el filtro de la grilla busca por código
    # fija "hoy" dentro de agosto/2026 para que la ausencia quede en el
    # rango por defecto de la grilla (el mes del período activo).
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-10' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    crear_ausencia(conn, id_profesional=id_profesional, fecha_desde="2026-08-17", fecha_hasta="2026-08-17")  # lunes
    conn.commit()

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))

    from app.negocio.grilla_operativa import NEGRA, VERDE

    celda = panel.grilla._resultado[(id_consultorio, "Lunes", 9)]
    assert (celda.color_aro, celda.color_centro, celda.color_fuente) == (VERDE, VERDE, NEGRA)


def test_crear_cargo_especial_sin_concepto_no_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 0


def test_crear_cargo_especial_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel.campo_concepto.setText("ajuste manual")
    panel.spin_monto.setValue(1500)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1
    assert panel.tabla.item(0, 2).text() == "Ajuste manual"


def test_crear_cargo_especial_periodo_mes_anterior_pide_confirmacion(qtbot, conn, monkeypatch):
    _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel.campo_concepto.setText("ajuste manual")
    panel.spin_monto.setValue(1500)
    panel.campo_periodo.setText("2026-07")

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 0

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1
