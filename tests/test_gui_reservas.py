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
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_regulares._crear()  # primera reserva 9-10 Lunes

    pantalla.panel_regulares._crear()  # misma reserva de nuevo -> conflicto bloqueante
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


def test_crear_reserva_aislada_sin_conflicto_persiste(qtbot, conn):
    _preparar(conn)
    pantalla = PantallaReservas(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_aisladas._crear()
    assert conn.execute("SELECT COUNT(*) c FROM ReservaAislada").fetchone()["c"] == 1
    assert pantalla.panel_aisladas.tabla.item(0, 4).text() == "Confirmada"


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
