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
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
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
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()

    emisiones = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    assert len(emisiones) == 2
    ultima = max(emisiones, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] == "Regenerada no enviada"
    assert panel.tabla.rowCount() == 1


def test_crear_licencia_sin_tipo_no_falla(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
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


def test_deshacer_ultimo_movimiento_vacaciones_sin_registros_no_falla(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel._deshacer_ultimo()  # no debe intentar confirmar ni romper: no hay nada que deshacer


def test_deshacer_ultimo_movimiento_vacaciones_anula_la_ultima_sin_importar_filtro(qtbot, conn, monkeypatch):
    id_profesional = _preparar(conn)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Otro")
    conn.commit()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    anio_actual = panel.spin_anio.value()

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(QDate(anio_actual, 9, 1))
    panel.campo_hasta.setDate(QDate(anio_actual, 9, 7))
    panel._crear()
    panel.campo_desde.setDate(QDate(anio_actual, 10, 1))
    panel.campo_hasta.setDate(QDate(anio_actual, 10, 7))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 2

    # El filtro queda en un profesional sin vacaciones cargadas, pero deshacer
    # debe anular la última vacación del sistema igual (la segunda creada arriba).
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(otro_profesional))
    panel._deshacer_ultimo()
    restantes = obtener_repositorio(conn, "Vacacion").listar()
    assert len(restantes) == 1
    assert restantes[0]["FechaDesde"] == f"{anio_actual}-09-01"


def test_deshacer_ultimo_movimiento_vacaciones_cancelado_por_usuario_no_borra(qtbot, conn, monkeypatch):
    id_profesional = _preparar(conn)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()

    panel._deshacer_ultimo()
    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 1


def test_panel_vacaciones_arranca_con_foco_en_profesional(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.panel_vacaciones.combo_profesional.hasFocus())


def test_spin_anio_vacaciones_arranca_en_el_anio_actual(qtbot, conn):
    from app.negocio.dias import fecha_actual

    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    assert panel.spin_anio.value() == fecha_actual(conn).year
    assert panel.boton_crear.isEnabled() is True

    panel.spin_anio.setValue(panel.spin_anio.value() - 1)
    assert panel.boton_crear.isEnabled() is False

    panel.spin_anio.setValue(panel.spin_anio.value() + 2)
    assert panel.boton_crear.isEnabled() is True


def test_crear_vacacion_anio_ya_terminado_no_persiste(qtbot, conn):
    """"Del año anterior solo consulta": ni siquiera llamando _crear a
    mano (esquivando el botón deshabilitado) se puede imputar al año
    pasado."""
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    anio_pasado = panel.spin_anio.value() - 1
    panel.spin_anio.setValue(anio_pasado)
    panel.campo_desde.setDate(QDate(anio_pasado, 9, 1))
    panel.campo_hasta.setDate(QDate(anio_pasado, 9, 7))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 0


def test_tabla_vacaciones_muestra_todos_los_anios_y_filtra_por_profesional(qtbot, conn):
    id_profesional = _preparar(conn)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Otro")
    conn.commit()

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    anio_actual = panel.spin_anio.value()

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(QDate(anio_actual, 9, 1))
    panel.campo_hasta.setDate(QDate(anio_actual, 9, 7))
    panel._crear()
    panel.campo_desde.setDate(QDate(anio_actual + 1, 1, 5))
    panel.campo_hasta.setDate(QDate(anio_actual + 1, 1, 10))
    panel.spin_anio.setValue(anio_actual + 1)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 2

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(otro_profesional))
    assert panel.tabla.rowCount() == 0  # sin nada del otro profesional, en ningún año

    # La lista es el historial completo: sin filtrar por profesional
    # aparecen las vacaciones de ambos años juntas, distinguidas por la
    # columna "Año calendario".
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    assert panel.tabla.rowCount() == 2
    assert panel.tabla.horizontalHeaderItem(1).text() == "Año calendario"
    assert panel.tabla.item(0, 1).text() == str(anio_actual)
    assert panel.tabla.item(0, 2).text() == f"01-09-{anio_actual}"
    assert panel.tabla.item(1, 1).text() == str(anio_actual + 1)
    assert panel.tabla.item(1, 2).text() == f"05-01-{anio_actual + 1}"


def test_tabla_vacaciones_muestra_cupo_utilizado_junto_al_restante(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    anio_actual = panel.spin_anio.value()
    panel.campo_desde.setDate(QDate(anio_actual, 9, 1))
    panel.campo_hasta.setDate(QDate(anio_actual, 9, 7))
    panel._crear()

    assert panel.tabla.horizontalHeaderItem(5).text() == "Cupo utilizado %"
    assert panel.tabla.horizontalHeaderItem(6).text() == "Cupo restante %"
    assert panel.tabla.item(0, 5).text() == "50.0%"
    assert panel.tabla.item(0, 6).text() == "50.0%"


def test_tabla_vacaciones_oculta_valor_bonificado_de_meses_futuros(qtbot, conn):
    """El monto ya está calculado y guardado, pero no se muestra en la
    lista para períodos posteriores al mes en curso: todavía pueden no
    estar definidos los valores de referencia de esos meses."""
    id_profesional = _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-10' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-08-03"))
    panel.campo_hasta.setDate(_fecha("2026-08-09"))
    panel._crear()
    panel.campo_desde.setDate(_fecha("2026-10-05"))
    panel.campo_hasta.setDate(_fecha("2026-10-11"))
    panel._crear()

    assert panel.tabla.rowCount() == 2
    filas = {panel.tabla.item(f, 2).text(): panel.tabla.item(f, 4).text() for f in range(panel.tabla.rowCount())}
    assert filas["03-08-2026"] != ""  # mes en curso: se ve el monto
    assert filas["05-10-2026"] == ""  # mes futuro: en blanco


def test_cupo_vacaciones_se_actualiza_con_profesional_y_anio(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))

    assert "100.0%" in panel.etiqueta_cupo_disponible.text()
    assert "0.0%" in panel.etiqueta_cupo_utilizado.text()

    anio_actual = panel.spin_anio.value()
    panel.campo_desde.setDate(QDate(anio_actual, 9, 1))
    panel.campo_hasta.setDate(QDate(anio_actual, 9, 7))
    panel._crear()
    assert "100.0%" not in panel.etiqueta_cupo_disponible.text()


def test_modificar_vacacion_seleccionada_anula_y_precarga_formulario(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    anio_actual = panel.spin_anio.value()
    panel.campo_desde.setDate(QDate(anio_actual, 9, 1))
    panel.campo_hasta.setDate(QDate(anio_actual, 9, 7))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 1

    panel.tabla.selectRow(0)
    panel._modificar_seleccionada()

    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 0
    assert panel.combo_profesional.currentData() == id_profesional
    assert panel.campo_desde.date() == QDate(anio_actual, 9, 1)
    assert panel.campo_hasta.date() == QDate(anio_actual, 9, 7)

    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Vacacion").fetchone()["c"] == 1


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


def test_deshacer_ultimo_movimiento_licencia_sin_registros_no_falla(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel._deshacer_ultimo()  # no debe intentar confirmar ni romper: no hay nada que deshacer


def test_deshacer_ultimo_movimiento_licencia_anula_la_ultima_sin_importar_filtro(qtbot, conn, monkeypatch):
    id_profesional = _preparar(conn)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Otro")
    conn.commit()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()
    panel.campo_desde.setDate(_fecha("2026-09-14"))
    panel.campo_hasta.setDate(_fecha("2026-09-14"))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 2

    # El filtro queda en un profesional sin licencias cargadas, pero deshacer
    # debe anular la última licencia del sistema igual (la segunda creada arriba).
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(otro_profesional))
    panel._deshacer_ultimo()
    restantes = obtener_repositorio(conn, "Licencia").listar()
    assert len(restantes) == 1
    assert restantes[0]["FechaDesde"] == "2026-09-07"


def test_deshacer_ultimo_movimiento_licencia_cancelado_por_usuario_no_borra(qtbot, conn, monkeypatch):
    id_profesional = _preparar(conn)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()

    panel._deshacer_ultimo()
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 1


def test_panel_licencias_recibe_foco_en_profesional_al_mostrar_la_solapa(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    pantalla.pestanas.setCurrentWidget(pantalla.panel_licencias)
    qtbot.waitUntil(lambda: pantalla.panel_licencias.combo_profesional.hasFocus())


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


def test_licencias_no_tiene_campo_de_anio_a_imputar(qtbot, conn):
    """Los cupos de licencia no son anuales como los de vacaciones — no
    tiene sentido pedir un "año calendario a imputar" acá."""
    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    assert not hasattr(panel, "spin_anio")


def test_crear_licencia_cruza_de_anio_y_persiste(qtbot, conn):
    """A diferencia de vacaciones (cupo anual), una licencia sí puede
    cruzar de un año calendario a otro en un único registro."""
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(QDate(2026, 12, 28))
    panel.campo_hasta.setDate(QDate(2027, 1, 3))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 1


def test_tabla_licencias_muestra_columna_bonificacion(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel._crear()

    assert panel.tabla.horizontalHeaderItem(4).text() == "Bonificación"
    assert panel.tabla.horizontalHeaderItem(5).text() == "Valor bonificado"
    assert panel.tabla.item(0, 4).text() == f"{panel.spin_porcentaje.value():.1f}%"


def test_tabla_licencias_oculta_valor_bonificado_de_meses_futuros(qtbot, conn):
    id_profesional = _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-10' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-08-03"))
    panel.campo_hasta.setDate(_fecha("2026-08-03"))
    panel._crear()
    panel.campo_desde.setDate(_fecha("2026-10-05"))
    panel.campo_hasta.setDate(_fecha("2026-10-05"))
    panel._crear()

    assert panel.tabla.rowCount() == 2
    filas = {panel.tabla.item(f, 2).text(): panel.tabla.item(f, 5).text() for f in range(panel.tabla.rowCount())}
    assert filas["03-08-2026"] != ""  # mes en curso: se ve el monto
    assert filas["05-10-2026"] == ""  # mes futuro: en blanco
    # La columna "Bonificación" (el % elegido) sigue mostrándose siempre,
    # solo se oculta el monto en pesos ya calculado para meses futuros.
    porcentajes = {panel.tabla.item(f, 2).text(): panel.tabla.item(f, 4).text() for f in range(panel.tabla.rowCount())}
    assert porcentajes["05-10-2026"] != ""


def test_crear_licencia_con_porcentaje_default_no_pide_confirmacion(qtbot, conn):
    """Si no se toca el % preestablecido del tipo, no hace falta ninguna
    confirmación extra al crear (y no debe intentar mostrar el diálogo,
    que en este test no está mockeado — colgaría si se llamara)."""
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 1


def test_crear_licencia_con_porcentaje_editado_pide_confirmacion(qtbot, conn, monkeypatch):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel.spin_porcentaje.setValue(50)

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 1
    assert panel.tabla.item(0, 4).text() == "50.0%"


def test_crear_licencia_con_porcentaje_editado_cancelado_no_persiste(qtbot, conn, monkeypatch):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel.spin_porcentaje.setValue(50)

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 0


def test_tabla_licencias_orden_por_defecto_fecha_mas_nueva_primero(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel._crear()
    panel.campo_desde.setDate(_fecha("2026-09-15"))
    panel.campo_hasta.setDate(_fecha("2026-09-15"))
    panel._crear()

    assert panel.tabla.rowCount() == 2
    assert panel.tabla.item(0, 2).text() == "15-09-2026"
    assert panel.tabla.item(1, 2).text() == "01-09-2026"


def test_tabla_licencias_todos_ordena_por_fecha_y_luego_profesional(qtbot, conn):
    id_a = _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1' WHERE IdProfesional = ?", (id_a,))
    id_consultorio = conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]
    id_b = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Aaronson", IdCodigo="A1")
    conn.execute(
        "INSERT INTO ReservaRegular (IdProfesional, IdConsultorio, DiaSemana, HoraInicio, HoraFin, VigenciaInicio) "
        "VALUES (?, ?, 'Martes', 9, 12, '2020-01-01')",
        (id_b, id_consultorio),
    )
    conn.commit()
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_a))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel._crear()
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_b))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel._crear()

    panel.combo_profesional.setCurrentIndex(0)  # Todos los profesionales
    assert panel.tabla.rowCount() == 2
    # Misma fecha en las dos -> desempata por profesional (código A1 antes que R1)
    assert panel.tabla.item(0, 0).text().startswith("A1")
    assert panel.tabla.item(1, 0).text().startswith("R1")


def test_tabla_licencias_click_en_columna_ordena_y_alterna_sentido(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel._crear()
    panel.campo_desde.setDate(_fecha("2026-09-15"))
    panel.campo_hasta.setDate(_fecha("2026-09-15"))
    panel._crear()

    panel.tabla.horizontalHeader().sectionClicked.emit(2)  # "Desde" ascendente
    assert panel.tabla.item(0, 2).text() == "01-09-2026"
    assert panel.tabla.item(1, 2).text() == "15-09-2026"

    panel.tabla.horizontalHeader().sectionClicked.emit(2)  # de nuevo -> descendente
    assert panel.tabla.item(0, 2).text() == "15-09-2026"
    assert panel.tabla.item(1, 2).text() == "01-09-2026"


def test_tabla_licencias_vuelve_al_orden_por_defecto_al_reabrir_la_solapa(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel._crear()
    panel.campo_desde.setDate(_fecha("2026-09-15"))
    panel.campo_hasta.setDate(_fecha("2026-09-15"))
    panel._crear()

    panel.tabla.horizontalHeader().sectionClicked.emit(2)  # "Desde" ascendente
    assert panel.tabla.item(0, 2).text() == "01-09-2026"

    pantalla.pestanas.setCurrentWidget(pantalla.panel_vacaciones)
    pantalla.pestanas.setCurrentWidget(panel)
    assert panel._orden.columna is None
    assert panel.tabla.item(0, 2).text() == "15-09-2026"


def test_licencias_no_tiene_seccion_de_cupo(qtbot, conn):
    """A diferencia de Vacaciones, Licencias no tiene un cupo anual que
    mostrar (no aplica en el modelo de negocio) — no debería quedar ni la
    línea divisoria ni las etiquetas de cupo."""
    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    assert not hasattr(panel, "etiqueta_cupo_utilizado")
    assert not hasattr(panel, "etiqueta_cupo_disponible")


def test_modificar_licencia_seleccionada_anula_y_precarga_formulario(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_licencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    from app.negocio.dias import fecha_actual

    indice_duelo = panel.combo_tipo.findText("Licencia por duelo")
    panel.combo_tipo.setCurrentIndex(indice_duelo)
    anio_actual = fecha_actual(conn).year
    panel.campo_desde.setDate(QDate(anio_actual, 9, 1))
    panel.campo_hasta.setDate(QDate(anio_actual, 9, 3))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 1

    panel.tabla.selectRow(0)
    panel._modificar_seleccionada()

    assert conn.execute("SELECT COUNT(*) c FROM Licencia").fetchone()["c"] == 0
    assert panel.combo_profesional.currentData() == id_profesional
    assert panel.combo_tipo.currentText() == "Licencia por duelo"
    assert panel.campo_desde.date() == QDate(anio_actual, 9, 1)
    assert panel.campo_hasta.date() == QDate(anio_actual, 9, 3)

    panel._crear()
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


def test_deshacer_ultimo_movimiento_ausencia_sin_registros_no_falla(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel._deshacer_ultimo()  # no debe intentar confirmar ni romper: no hay nada que deshacer


def test_deshacer_ultimo_movimiento_ausencia_anula_la_ultima_sin_importar_filtro(qtbot, conn, monkeypatch):
    id_profesional = _preparar(conn)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Otro")
    conn.commit()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()
    panel.campo_desde.setDate(_fecha("2026-09-14"))
    panel.campo_hasta.setDate(_fecha("2026-09-14"))
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 2

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(otro_profesional))
    panel._deshacer_ultimo()
    restantes = obtener_repositorio(conn, "Ausencia").listar()
    assert len(restantes) == 1
    assert restantes[0]["FechaDesde"] == "2026-09-07"


def test_deshacer_ultimo_movimiento_ausencia_cancelado_por_usuario_no_borra(qtbot, conn, monkeypatch):
    id_profesional = _preparar(conn)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-07"))
    panel.campo_hasta.setDate(_fecha("2026-09-07"))
    panel._crear()

    panel._deshacer_ultimo()
    assert conn.execute("SELECT COUNT(*) c FROM Ausencia").fetchone()["c"] == 1


def test_panel_ausencias_recibe_foco_en_profesional_al_mostrar_la_solapa(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    pantalla.pestanas.setCurrentWidget(pantalla.panel_ausencias)
    qtbot.waitUntil(lambda: pantalla.panel_ausencias.combo_profesional.hasFocus())


def test_tabla_ausencias_click_en_columna_ordena_y_alterna_sentido(qtbot, conn):
    id_profesional = _preparar(conn)
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_desde.setDate(_fecha("2026-09-01"))
    panel.campo_hasta.setDate(_fecha("2026-09-01"))
    panel._crear()
    panel.campo_desde.setDate(_fecha("2026-09-15"))
    panel.campo_hasta.setDate(_fecha("2026-09-15"))
    panel._crear()

    panel.tabla.horizontalHeader().sectionClicked.emit(1)  # "Desde" ascendente
    assert panel.tabla.item(0, 1).text() == "01-09-2026"
    assert panel.tabla.item(1, 1).text() == "15-09-2026"

    panel.tabla.horizontalHeader().sectionClicked.emit(1)  # de nuevo -> descendente
    assert panel.tabla.item(0, 1).text() == "15-09-2026"
    assert panel.tabla.item(1, 1).text() == "01-09-2026"


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


def test_panel_vacaciones_grilla_profesional_sin_reservas_queda_vacia(qtbot, conn):
    """Mismo criterio que Ausencias: la grilla se acota a lo que el
    profesional elegido realmente tiene reservado — uno sin ninguna
    reserva regular no tiene nada que mostrar (ya no "todas las
    unidades", que era el criterio viejo)."""
    id_profesional = _preparar(conn)
    id_unidad_1 = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    otro_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Sur")
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=otro_edificio, Departamento="2B")
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Sin Reservas")
    conn.commit()

    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_vacaciones
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    assert panel.grilla.ids_unidad_seleccionadas() == [id_unidad_1]

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(otro_profesional))
    assert panel.grilla.ids_unidad_seleccionadas() == []


def test_combo_profesional_ausencias_usa_formato_de_reservas(qtbot, conn):
    _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1', Tratamiento = 'Lic.'")
    conn.commit()
    pantalla = PantallaRegistroAusencias(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_ausencias
    assert panel.combo_profesional.itemText(0) == "Todos los profesionales"
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
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_concepto.setText("ajuste manual")
    panel.spin_monto.setValue(1500)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1
    assert panel.tabla.item(0, 3).text() == "Ajuste manual"


def test_crear_cargo_especial_periodo_mes_anterior_se_rechaza(qtbot, conn):
    """A diferencia de Pagos (que sí puede corregir hasta un mes atrás), un
    cargo especial nunca se imputa a un período anterior al mes en curso
    — no hay confirmación posible, se rechaza directo."""
    _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_concepto.setText("ajuste manual")
    panel.spin_monto.setValue(1500)
    panel.campo_periodo.setText("2026-07")

    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 0

    panel.campo_periodo.setText("2026-08")
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1


def test_combo_profesional_cargos_especiales_arranca_en_blanco(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    assert panel.combo_profesional.currentIndex() == 0
    assert panel.combo_profesional.currentData() is None


def test_crear_cargo_especial_sin_elegir_profesional_avisa_y_no_crea(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel.campo_concepto.setText("ajuste manual")
    panel.spin_monto.setValue(1500)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 0


def test_tabla_cargos_especiales_usa_formato_canonico_de_profesional(qtbot, conn):
    _preparar(conn)
    conn.execute("UPDATE Profesional SET IdCodigo = 'R1', Tratamiento = 'Lic.', NombrePila = 'Virginia'")
    conn.commit()
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    panel.campo_concepto.setText("ajuste manual")
    panel.spin_monto.setValue(1500)
    panel._crear()
    assert panel.tabla.item(0, 1).text() == "R1 - Lic. Virginia Gómez"


def test_panel_cargos_especiales_recibe_foco_en_profesional_al_mostrarse(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.panel.combo_profesional.hasFocus())


def test_tabla_cargos_especiales_click_en_columna_ordena_y_alterna_sentido(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional))
    for concepto, monto in (("bbb", 100), ("aaa", 200)):
        panel.campo_concepto.setText(concepto)
        panel.spin_monto.setValue(monto)
        panel._crear()
    assert panel.tabla.rowCount() == 2

    panel.tabla.horizontalHeader().sectionClicked.emit(3)  # "Concepto" ascendente
    conceptos_asc = [panel.tabla.item(f, 3).text() for f in range(panel.tabla.rowCount())]
    assert conceptos_asc == ["Aaa", "Bbb"]

    panel.tabla.horizontalHeader().sectionClicked.emit(3)  # de nuevo -> descendente
    conceptos_desc = [panel.tabla.item(f, 3).text() for f in range(panel.tabla.rowCount())]
    assert conceptos_desc == ["Bbb", "Aaa"]


def test_deshacer_ultimo_movimiento_cargo_especial_sin_registros_no_falla(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel._deshacer_ultimo()  # no debe intentar confirmar ni romper


def test_deshacer_ultimo_movimiento_cargo_especial_borra_el_ultimo_cargado(qtbot, conn, monkeypatch):
    _preparar(conn)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_concepto.setText("ajuste manual")
    panel.spin_monto.setValue(1500)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1

    panel._deshacer_ultimo()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 0


def test_deshacer_ultimo_movimiento_cargo_especial_cancelado_por_usuario_no_borra(qtbot, conn, monkeypatch):
    _preparar(conn)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_concepto.setText("ajuste manual")
    panel.spin_monto.setValue(1500)
    panel._crear()

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    panel._deshacer_ultimo()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1


def test_combo_profesional_cargos_especiales_filtra_la_tabla(qtbot, conn):
    from app.negocio.pagos import crear_cargo_especial

    _preparar(conn)
    id_profesional_1 = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_profesional_2 = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    crear_cargo_especial(
        conn, id_profesional=id_profesional_1, tipo="Débito", concepto="propio", monto=100,
        periodo_imputado=periodo_actual(conn),
    )
    crear_cargo_especial(
        conn, id_profesional=id_profesional_2, tipo="Débito", concepto="ajeno", monto=100,
        periodo_imputado=periodo_actual(conn),
    )
    conn.commit()

    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    assert panel.tabla.rowCount() == 2  # "Todos los profesionales" por defecto

    panel.combo_profesional.setCurrentIndex(panel.combo_profesional.findData(id_profesional_1))
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 3).text() == "Propio"


def test_tabla_cargos_especiales_incluye_columna_fecha_con_formato_dia(qtbot, conn):
    _preparar(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-17' WHERE IdConfiguracion = 1"
    )
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_concepto.setText("ajuste manual")
    panel.spin_monto.setValue(1500)
    panel._crear()
    assert panel.tabla.horizontalHeaderItem(0).text() == "Fecha"
    assert panel.tabla.item(0, 0).text() == "Lunes 17-08-2026"


def test_tabla_cargos_especiales_monto_con_signo_y_color(qtbot, conn):
    from app.negocio.pagos import crear_cargo_especial

    from app.gui.estilos import COLOR_ROJO

    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    crear_cargo_especial(
        conn, id_profesional=id_profesional, tipo="Débito", concepto="a favor", monto=100,
        periodo_imputado=periodo_actual(conn),
    )
    crear_cargo_especial(
        conn, id_profesional=id_profesional, tipo="Crédito", concepto="en contra", monto=-50,
        periodo_imputado=periodo_actual(conn),
    )
    conn.commit()

    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    valores = {panel.tabla.item(f, 3).text(): panel.tabla.item(f, 4) for f in range(panel.tabla.rowCount())}
    assert "$" in valores["A favor"].text()
    assert valores["A favor"].foreground().color().name() != COLOR_ROJO.lower()
    assert valores["En contra"].text().startswith("-")
    assert valores["En contra"].foreground().color().name() == COLOR_ROJO.lower()


def test_tabla_cargos_especiales_orden_por_defecto_fecha_categoria_codigo(qtbot, conn):
    from app.negocio.pagos import crear_cargo_especial

    _preparar(conn)
    repo_prof = obtener_repositorio(conn, "Profesional")
    id_b1 = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    repo_prof.actualizar(id_b1, CategoriaProfesional="B", IdCodigo="B1")
    id_r2 = repo_prof.crear(CategoriaProfesional="R", Apellido="Otro", IdCodigo="R2")
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-17' WHERE IdConfiguracion = 1"
    )
    for id_prof in (id_b1, id_r2):
        crear_cargo_especial(
            conn, id_profesional=id_prof, tipo="Débito", concepto="x", monto=100,
            periodo_imputado=periodo_actual(conn),
        )
    conn.commit()

    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    # mismo día -> desempata por categoría (B antes que R)
    codigos = [panel.tabla.item(f, 1).text().split(" - ")[0] for f in range(panel.tabla.rowCount())]
    assert codigos == ["B1", "R2"]


def test_cargo_ligado_a_llave_bloquea_modificar_eliminar_y_deshacer(qtbot, conn, monkeypatch):
    from app.negocio.llaves import crear_llave, entregar_llave

    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    id_llave = crear_llave(conn, valor_deposito_actual=5000)
    entregar_llave(conn, id_llave=id_llave, id_profesional=id_profesional, cobrar_deposito=True)
    conn.commit()

    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    assert panel.tabla.rowCount() == 1  # se ve en la tabla...

    panel.tabla.selectRow(0)
    panel._eliminar()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1  # ...pero no se puede tocar

    panel._modificar_seleccionada()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    panel._deshacer_ultimo()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1


def test_eliminar_cargo_especial_sin_llave_lo_borra(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel.combo_profesional.setCurrentIndex(1)
    panel.campo_concepto.setText("ajuste manual")
    panel.spin_monto.setValue(1500)
    panel._crear()

    panel.tabla.selectRow(0)
    panel._eliminar()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 0


def test_modificar_cargo_especial_sin_llave_lo_precarga_para_recrear(qtbot, conn):
    _preparar(conn)
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    pantalla = PantallaCargosEspeciales(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel
    panel.combo_profesional.setCurrentIndex(1)
    panel.combo_tipo.setCurrentIndex(panel.combo_tipo.findData("Crédito"))
    panel.campo_concepto.setText("bonificación")
    panel.spin_monto.setValue(-300)
    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1

    panel.tabla.selectRow(0)
    panel._modificar_seleccionada()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 0  # se borró la vieja

    assert panel.combo_profesional.currentData() == id_profesional
    assert panel.combo_tipo.currentData() == "Crédito"
    assert panel.campo_concepto.text() == "Bonificación"
    assert panel.spin_monto.value() == -300

    panel._crear()
    assert conn.execute("SELECT COUNT(*) c FROM CargoEspecial").fetchone()["c"] == 1
