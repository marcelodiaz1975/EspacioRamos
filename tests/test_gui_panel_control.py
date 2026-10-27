from datetime import date, datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QInputDialog,
    QLabel,
    QMessageBox,
    QScrollArea,
    QTabWidget,
)

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import COLOR_ROJO
from app.gui.main_window import Seccion, VentanaPrincipal
from app.gui.pantallas.panel_control import PanelControl
from app.negocio.backup import activar_modo_sin_sincronizar, generar_backup
from app.negocio.lista_espera import crear_pedido


def _tarjeta_de(widget):
    """Sube por `parentWidget()` hasta el `QFrame#cuadritoInfo` (punto 78,
    SistemaDF v0.11.2026.10: cada cuadrito envuelve su contenido en un
    `QScrollArea` propio, así que la etiqueta de contenido ya no es hija
    directa del cuadrito — hay que atravesar el viewport del scroll)."""
    actual = widget
    while actual is not None and actual.objectName() != "cuadritoInfo":
        actual = actual.parentWidget()
    assert actual is not None, "no se encontró ningún ancestro cuadritoInfo"
    return actual
from app.repositorio.registro import obtener_repositorio


def _textos_visibles(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def _crear_profesional_regular_con_deuda(conn, apellido: str, saldo: float) -> int:
    """La alerta de deuda regular (ver `panel_control._deuda_regulares_
    alerta`) exige, además del saldo del mes EN CURSO (`SaldoCuentaActual`
    — no el arrastrado de meses anteriores), una `ReservaRegular` vigente
    hoy."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)
    id_profesional = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido=apellido, SaldoCuentaActual=saldo,
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=11, VigenciaInicio="2020-01-01", VigenciaFin=None,
    )
    return id_profesional


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


def test_panel_control_muestra_su_propio_nombre_en_mayuscula(qtbot, conn):
    """Nivel 1 (ver CLAUDE.md): mismo formato MAYÚSCULA que el resto de
    los títulos de pantalla del sistema. Título fijo desde el
    reordenamiento de formularios — antes mostraba el nombre del
    espacio (pedido puntual de cuando esta pantalla era la portada del
    sistema), ahora coherente con el resto de las pantallas, que
    muestran su propio nombre. Este título vive en el contenedor de
    afuera (`PanelControl`), no en ninguna de las dos solapas."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.titulo.text() == "PANEL DE CONTROL"


def test_panel_control_boton_avanzar_habilitado_a_mitad_de_mes(qtbot, conn):
    # DC-06 §1: el avance de mes tiene que estar disponible en cualquier
    # momento, no solo al principio o fin de mes.
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_avance.boton_avanzar.isEnabled() is True


def test_panel_control_sin_alertas_muestra_mensaje(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert any("Sin alertas pendientes." in t for t in _textos_visibles(pantalla.panel_avance.contenedor_alertas))


def test_panel_control_alerta_de_deuda_se_muestra(qtbot, conn):
    _crear_profesional_regular_con_deuda(conn, "Deudor", 99999)
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert any("Deudor" in t for t in _textos_visibles(pantalla.panel_avance.contenedor_alertas))


def test_panel_control_alerta_de_backup_vencido_se_muestra(qtbot, conn, tmp_path):
    conn.execute(
        "UPDATE Configuracion SET CarpetaBackup = ?, FrecuenciaBackupDrive = 'Diario' WHERE IdConfiguracion = 1",
        (str(tmp_path / "backups"),),
    )
    conn.commit()
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert any("Backup vencido" in t for t in _textos_visibles(pantalla.panel_avance.contenedor_alertas))


def test_generar_backup_sin_carpeta_configurada_no_falla(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_avance._generar_backup()  # solo debe avisar, no lanzar


def test_generar_backup_con_carpeta_configurada(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBackup=str(tmp_path / "backups"))
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_avance._generar_backup()
    assert list((tmp_path / "backups").iterdir())


def test_avanzar_mes_genera_backup_cuando_esta_configurado(qtbot, conn, tmp_path, monkeypatch):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-31', CarpetaBackup = ? "
        "WHERE IdConfiguracion = 1",
        (str(tmp_path / "backups"),),
    )
    conn.commit()
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    _saltear_aumento_y_confirmar(monkeypatch)

    pantalla.panel_avance._avanzar_mes()

    assert list((tmp_path / "backups").iterdir())


def _saltear_aumento_y_confirmar(monkeypatch) -> None:
    """"No" a evaluar aumentos (saltear), "Sí" a confirmar el avance — la
    secuencia que sigue `_avanzar_mes` cuando no hay un aumento confirmado
    todavía este período."""
    respuestas = iter([QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes])
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: next(respuestas)))


def test_avanzar_mes_ofrece_evaluar_aumentos_si_no_se_confirmo_ninguno(qtbot, conn, monkeypatch):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-31' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)

    preguntas = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda self, titulo, texto, *a, **k: (preguntas.append(texto), QMessageBox.StandardButton.Yes)[1]),
    )

    pantalla.panel_avance._avanzar_mes()

    assert len(preguntas) == 1
    assert "evaluar un aumento" in preguntas[0]
    snapshots = obtener_repositorio(conn, "SnapshotMensual").listar()
    assert snapshots == []  # se canceló el avance, no llegó a ejecutarlo


def test_avanzar_mes_saltea_aumentos_y_avanza(qtbot, conn, monkeypatch):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-31' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    _saltear_aumento_y_confirmar(monkeypatch)

    pantalla.panel_avance._avanzar_mes()

    snapshots = obtener_repositorio(conn, "SnapshotMensual").listar()
    assert len(snapshots) == 1
    assert snapshots[0]["PorcentajeAumentoAplicado"] is None


def test_avanzar_mes_no_pregunta_por_aumento_si_ya_se_confirmo_uno(qtbot, conn, monkeypatch):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-31' WHERE IdConfiguracion = 1"
    )
    obtener_repositorio(conn, "AumentoAplicado").crear(Periodo="2026-08", PorcentajeGeneral=5.0)
    conn.commit()
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)

    preguntas = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda self, titulo, texto, *a, **k: (preguntas.append(texto), QMessageBox.StandardButton.Yes)[1]),
    )

    pantalla.panel_avance._avanzar_mes()

    assert len(preguntas) == 1  # solo la confirmación del avance, sin la pregunta de aumentos
    assert "evaluar un aumento" not in preguntas[0]
    snapshots = obtener_repositorio(conn, "SnapshotMensual").listar()
    assert snapshots[0]["PorcentajeAumentoAplicado"] == 5.0


def test_avanzar_mes_bloqueado_si_ya_esta_un_periodo_por_delante_de_la_fecha_real(qtbot, conn, monkeypatch):
    """Confirmado por la clienta: "si estoy realmente en octubre, que me
    permita avanzar a noviembre y no más de eso" — un segundo click sobre
    "Avanzar de mes" sin que la fecha real haya alcanzado ese período
    tiene que avisar y NO ejecutar nada (sin backup, cuotas, snapshot,
    etc.). Usa la fecha REAL del sistema operativo (no el modo QA de
    fecha ficticia, que esta regla ignora a propósito)."""
    from app.negocio import avance_mes as avance_mes_modulo
    from app.negocio import dias as dias_modulo

    class _FechaFija(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 25)

    monkeypatch.setattr(dias_modulo, "date", _FechaFija)
    monkeypatch.setattr(avance_mes_modulo, "date", _FechaFija)
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    _saltear_aumento_y_confirmar(monkeypatch)
    pantalla.panel_avance._avanzar_mes()  # avance válido: cierra 2026-10, queda parado en 2026-11
    snapshots_tras_el_avance = len(obtener_repositorio(conn, "SnapshotMensual").listar())

    avisos = []
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda self, titulo, texto, *a, **k: avisos.append(texto)),
    )
    pantalla.panel_avance._avanzar_mes()  # 2do intento, sin que la fecha real haya llegado a noviembre

    assert len(avisos) == 1
    assert "no se puede avanzar" in avisos[0].lower()
    assert len(obtener_repositorio(conn, "SnapshotMensual").listar()) == snapshots_tras_el_avance


def _crear_pedido_vencido(conn) -> int:
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Vencido")
    return crear_pedido(
        conn, id_profesional=id_prof,
        bloques=[{"dias": ["Lunes"], "horario_desde": 14, "horario_hasta": 16}], fecha_pedido="2015-01-01",
    )


def test_avanzar_mes_avisa_de_vencidos_y_los_elimina_si_se_confirma(qtbot, conn, monkeypatch):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-31' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    id_pedido = _crear_pedido_vencido(conn)
    conn.commit()
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)

    # "No" a evaluar aumentos (saltear), "Sí" a confirmar el avance, "Sí" a eliminar los vencidos.
    preguntas = []
    respuestas = iter([
        QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Yes,
    ])
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda self, titulo, texto, *a, **k: (preguntas.append(texto), next(respuestas))[1]),
    )

    pantalla.panel_avance._avanzar_mes()

    assert any("vencidos" in p.lower() for p in preguntas)
    assert obtener_repositorio(conn, "ListaEspera").obtener(id_pedido) is None


def test_avanzar_mes_conserva_vencidos_si_no_se_confirma(qtbot, conn, monkeypatch):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-31' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    id_pedido = _crear_pedido_vencido(conn)
    conn.commit()
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)

    # "Sí" a saltear aumentos y confirmar el avance, "No" a eliminar los vencidos.
    respuestas = iter([
        QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No,
    ])
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: next(respuestas)))

    pantalla.panel_avance._avanzar_mes()

    assert obtener_repositorio(conn, "ListaEspera").obtener(id_pedido) is not None
    snapshots = obtener_repositorio(conn, "SnapshotMensual").listar()
    assert len(snapshots) == 1  # el avance de mes se ejecutó igual


def test_ventana_principal_navega_entre_secciones(qtbot, conn):
    secciones = [
        Seccion("Panel de control", lambda c: PanelControl(c), categoria="Principal"),
        Seccion("Otra pantalla", lambda c: PanelControl(c), categoria="Principal"),
    ]
    ventana = VentanaPrincipal(conn, secciones)
    qtbot.addWidget(ventana)
    assert ventana._pila.count() == 3  # pantalla inicial + las dos secciones
    ventana._navegacion.setCurrentRow(2)  # fila 0 = separador, 1 = primera, 2 = segunda
    assert ventana._pila.currentIndex() == 2


# --------------------------------------------------------- formato solapa


def test_tiene_dos_solapas_avance_de_periodo_e_importacion(qtbot, conn):
    """Reordenamiento de formularios (Excel de la clienta): "Panel de
    control" absorbió a la vieja pantalla "Importar planilla" como
    segunda solapa."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert solapas.count() == 2
    assert solapas.tabText(0) == "Avance de período, backup, y vista rápida"
    assert solapas.tabText(1) == "Importación datos desde Excel"
    assert pantalla.panel_avance.objectName() == "panelSolapa"
    assert pantalla.panel_importacion.objectName() == "panelSolapa"


def test_solapa_importacion_es_un_panel_importacion_funcional(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_importacion.boton_importar.objectName() == "botonPrimario"
    assert pantalla.panel_importacion.boton_importar.isEnabled() is False


def test_avanzar_de_mes_es_primario_y_backup_secundario(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_avance.boton_avanzar.objectName() == "botonPrimario"
    assert pantalla.panel_avance.boton_backup.objectName() == "botonSecundario"


def test_los_dos_botones_comparten_el_mismo_ancho_fijo(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_avance.boton_avanzar.width() == pantalla.panel_avance.boton_backup.width()


def test_no_quedan_las_leyendas_ni_el_subtitulo_viejos(qtbot, conn):
    """Se sacaron a pedido de la clienta: esa información ahora vive en
    los cuadritos de abajo."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert not hasattr(pantalla.panel_avance, "subtitulo")
    assert not hasattr(pantalla.panel_avance, "leyenda_periodo")
    assert not hasattr(pantalla.panel_avance, "leyenda_backup")


def test_tarjeta_reloj_muestra_fecha_y_hora_real_con_segundos(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.panel_avance.etiqueta_reloj.text()
    assert texto.count(":") == 2  # HH:MM:SS
    assert texto.endswith("hs")


def test_tarjeta_reloj_se_actualiza_con_el_timer(qtbot, conn, monkeypatch):
    momentos = iter([datetime(2026, 8, 25, 14, 45, 0), datetime(2026, 8, 25, 14, 45, 1)])
    monkeypatch.setattr(
        "app.gui.pantallas.panel_control.datetime",
        type("_FakeDatetime", (), {"now": staticmethod(lambda: next(momentos))}),
    )
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_avance.etiqueta_reloj.text() == "mar 25-08-2026 14:45:00hs"
    pantalla.panel_avance._actualizar_reloj()
    assert pantalla.panel_avance.etiqueta_reloj.text() == "mar 25-08-2026 14:45:01hs"


def test_tarjeta_periodo_actual(qtbot, conn):
    conn.execute("UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1")
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_avance.etiqueta_periodo.text() == "Agosto de 2026 (08/2026)"


def test_tarjeta_backup_sin_ninguno_generado(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert "Todavía no se generó ningún backup." in pantalla.panel_avance.etiqueta_backup.text()


def test_tarjeta_backup_con_uno_ya_generado(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, CarpetaBackup=str(tmp_path / "backups"), FrecuenciaBackupDrive="Semanal",
    )
    generar_backup(conn, momento=datetime(2026, 8, 25, 14, 45))
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.panel_avance.etiqueta_backup.text()
    assert "Último backup: mar 25-08-2026 14:45hs" in texto
    assert "Frecuencia configurada: Semanal" in texto
    assert "estado" in pantalla.panel_avance.etiqueta_estado_backup.text().lower()


def test_tarjeta_backup_vencido_queda_en_mayuscula_rojo_y_negrita(qtbot, conn, tmp_path):
    """Pedido explícito de la clienta: cuando el backup está vencido, la
    línea entera pasa a "ESTADO: VENCIDO", en rojo y negrita — separada
    de `etiqueta_backup` (que sigue mostrando Último backup/Frecuencia
    sin ningún estilo especial)."""
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, CarpetaBackup=str(tmp_path / "backups"), FrecuenciaBackupDrive="Diario",
        ModoFechaFicticia=1, FechaFicticia="2026-08-30",
    )
    generar_backup(conn, momento=datetime(2026, 8, 25, 14, 45))
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    etiqueta = pantalla.panel_avance.etiqueta_estado_backup
    assert etiqueta.text() == "ESTADO: VENCIDO"
    assert COLOR_ROJO in etiqueta.styleSheet()
    assert "bold" in etiqueta.styleSheet()
    assert "Estado" not in pantalla.panel_avance.etiqueta_backup.text()


def test_tarjeta_backup_al_dia_sin_estilo_especial(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, CarpetaBackup=str(tmp_path / "backups"), FrecuenciaBackupDrive="Mensual",
    )
    generar_backup(conn, momento=datetime.now())
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    etiqueta = pantalla.panel_avance.etiqueta_estado_backup
    assert etiqueta.text() == "Estado: al día"
    assert etiqueta.styleSheet() == ""


def test_generar_backup_actualiza_la_tarjeta(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBackup=str(tmp_path / "backups"))
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert "Todavía no se generó ningún backup." in pantalla.panel_avance.etiqueta_backup.text()

    pantalla.panel_avance._generar_backup()

    assert "Último backup:" in pantalla.panel_avance.etiqueta_backup.text()


def test_tarjeta_fechas_especiales_sin_datos(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert "Sin fechas especiales cargadas" in pantalla.panel_avance.etiqueta_fechas_especiales.text()


def test_tarjeta_fechas_especiales_lista_lo_que_falta_del_mes_y_los_dos_siguientes(qtbot, conn):
    conn.execute("UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-01", Descripcion="Ya pasó", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-20", Descripcion="Feriado puente", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-10-05", Descripcion="Dentro de rango", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-11-01", Descripcion="Fuera de rango", Activo=1)
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.panel_avance.etiqueta_fechas_especiales.text()
    assert "01-08-2026" not in texto
    assert "jue 20-08-2026" in texto  # punto 82: formato "ddd dd-mm-yyyy"
    assert "Feriado puente" in texto
    assert "lun 05-10-2026" in texto
    assert "01-11-2026" not in texto


def test_tarjeta_profesionales_muestra_los_tres_conteos(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.panel_avance.etiqueta_profesionales.text()
    assert "Con plan de pago vigente: 0" in texto
    assert "Con saldo fuera de tolerancia: 0" in texto
    assert "Con reservas regulares activas: 0" in texto


def test_tarjeta_ocupacion_muestra_los_tres_conceptos_generales(qtbot, conn):
    """El monto de aisladas y el saldo pendiente se mudaron a
    "Estadísticas principales mes en curso" (sin duplicarse acá)."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.panel_avance.etiqueta_ocupacion.text()
    assert "Ocupación regular general:" in texto
    assert "Cantidad horas regulares semanales mes en curso:" in texto
    assert "Cantidad horas aisladas mensuales:" in texto
    assert "Monto generado" not in texto
    assert "Saldo pendiente" not in texto


def test_tarjeta_ocupacion_repite_los_tres_conceptos_por_unidad(qtbot, conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.panel_avance.etiqueta_ocupacion.text()
    assert "Ramos 1 - 1A:" in texto
    assert texto.count("Ocupación regular general:") == 2  # general + la de esa unidad


def test_tarjeta_estadisticas_principales_muestra_los_siete_conceptos(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.panel_avance.etiqueta_estadisticas_principales.text()
    for etiqueta in (
        "Monto por reservas regulares:", "Monto por reservas aisladas:", "Total ingresos:",
        "Total liquidado:", "Saldo pendiente de cobro (de lo liquidado):",
        "Gastos operativos:", "Balance de negocio:",
    ):
        assert etiqueta in texto


def test_tarjeta_profesionales_muestra_los_cuatro_conceptos_nuevos(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.panel_avance.etiqueta_profesionales.text()
    assert "Con reservas aisladas activas:" in texto
    assert "Horarios incorporados para el mes próximo:" in texto
    assert "Horarios liberados para el mes próximo:" in texto
    assert "Diferencia:" in texto


def test_tarjeta_cumpleanos_sin_datos(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert "Sin cumpleaños ni días de profesión" in pantalla.panel_avance.etiqueta_cumpleanos.text()


def test_tarjeta_cumpleanos_lista_profesionales_y_dias_de_profesion(qtbot, conn):
    conn.execute("UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1")
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Lo Veci", NombrePila="Virginia", FechaNacimiento="1990-08-20",
    )
    obtener_repositorio(conn, "Profesion").crear(
        Nombre="Psicología", NombreMasculino="Psicólogo", DiaProfesion="08-25",
    )
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.panel_avance.etiqueta_cumpleanos.text()
    # Punto 80: día de la semana abreviado ("ddd dd-mm") — jue 20-08-2026,
    # mar 25-08-2026.
    assert "jue 20-08 — Cumpleaños de Virginia Lo Veci" in texto
    assert "mar 25-08 — Día del Psicólogo" in texto


def test_cada_cuadrito_principal_tiene_su_propio_scroll_area(qtbot, conn):
    """Punto 78: cada uno de los seis cuadritos (período, backup,
    ocupación, profesionales, fechas especiales, cumpleaños) tiene que
    poder escrolear en vertical de forma individual — un `QScrollArea`
    propio dentro de cada uno, sin afectar el alto parejo de la grilla."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    for etiqueta in (
        pantalla.panel_avance.etiqueta_periodo, pantalla.panel_avance.etiqueta_backup,
        pantalla.panel_avance.etiqueta_ocupacion, pantalla.panel_avance.etiqueta_profesionales,
        pantalla.panel_avance.etiqueta_fechas_especiales, pantalla.panel_avance.etiqueta_cumpleanos,
    ):
        tarjeta = _tarjeta_de(etiqueta)
        assert tarjeta.findChild(QScrollArea) is not None


def test_tarjeta_periodo_muestra_periodo_y_reloj_en_el_mismo_cuadrito(qtbot, conn):
    """Punto 76: "Fecha y hora actual" se funde dentro de "Período
    actual" — las dos etiquetas quedan en el mismo cuadrito."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert _tarjeta_de(pantalla.panel_avance.etiqueta_periodo) is _tarjeta_de(pantalla.panel_avance.etiqueta_reloj)


def test_tarjeta_alertas_sigue_mostrando_las_alertas_de_siempre(qtbot, conn):
    _crear_profesional_regular_con_deuda(conn, "Deudor", 99999)
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert any("Deudor" in t for t in _textos_visibles(pantalla.panel_avance.contenedor_alertas))


def test_refrescar_alertas_dos_veces_no_deja_la_tarjeta_vieja_visible(qtbot, conn):
    """Bug detectado al revisar capturas: `_refrescar_alertas` sacaba la
    tarjeta vieja del layout y la mandaba a `deleteLater()`, pero sin
    ocultarla de una seguía pintada en su posición vieja hasta que el
    event loop procesara el borrado — se veía como una tarjeta
    "fantasma" duplicada debajo de la real."""
    _crear_profesional_regular_con_deuda(conn, "Deudor", 99999)
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_avance
    tarjeta_vieja = panel.layout_alertas.itemAt(0).widget()

    panel.actualizar()  # mismos datos: fuerza sacar y recrear la tarjeta

    assert tarjeta_vieja.isHidden()


def _seis_tarjetas(panel) -> list:
    return [
        _tarjeta_de(panel.etiqueta_periodo),
        _tarjeta_de(panel.etiqueta_estadisticas_principales),
        _tarjeta_de(panel.etiqueta_ocupacion),
        _tarjeta_de(panel.etiqueta_profesionales),
        _tarjeta_de(panel.etiqueta_fechas_especiales),
        _tarjeta_de(panel.etiqueta_cumpleanos),
    ]


def test_hay_seis_tarjetas_parejas_en_dos_filas_y_alertas_aparte(qtbot, conn):
    """Punto 76 (SistemaDF v0.11.2026.10): "Fecha y hora actual" se funde
    dentro de "Período actual" — de 7 cuadritos (3+3+1 suelto) vuelve a
    6 (3+3 parejo, sin ninguno sobrando en una fila propia). Punto 82:
    las dos filas de tres ya NO viven en un único `QGridLayout` — cada
    una es su propio `QHBoxLayout`, hermano del de Alertas en
    `layout_solapa` (ver el comentario grande en `_armar_ui`)."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1200, 800)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    tarjetas = _seis_tarjetas(pantalla.panel_avance)
    assert all(t is not None for t in tarjetas)

    # Tolerancia chica: el reparto de una división no exacta (ancho/alto
    # de ventana entre columnas/filas) cae en algún borde — invisible a
    # simple vista pero real en píxeles.
    anchos = [t.width() for t in tarjetas]
    altos = [t.height() for t in tarjetas]
    assert max(anchos) - min(anchos) <= 8  # las seis del mismo ancho
    assert max(altos) - min(altos) <= 8  # las seis del mismo alto


def test_tarjeta_alertas_no_es_ninguna_de_las_seis_tarjetas(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    tarjetas = _seis_tarjetas(pantalla.panel_avance)
    assert pantalla.panel_avance.tarjeta_alertas not in tarjetas


def test_tarjeta_alertas_ocupa_mucho_mas_ancho_que_una_tarjeta_de_las_filas(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1200, 800)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    ancho_una_tarjeta = _seis_tarjetas(pantalla.panel_avance)[0].width()
    assert pantalla.panel_avance.tarjeta_alertas.width() > ancho_una_tarjeta * 2


def test_titulos_de_las_tarjetas_van_en_negrita_e_italica_con_dos_puntos(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    tarjeta = _tarjeta_de(pantalla.panel_avance.etiqueta_periodo)
    encabezado = tarjeta.findChildren(QLabel)[0]
    assert encabezado.text() == "Período actual y último backup:"
    assert "italic" in encabezado.styleSheet()
    assert "bold" in encabezado.styleSheet()


def test_el_borde_del_cuadrito_no_se_cuela_al_titulo_ni_al_contenido(qtbot, conn):
    """`QLabel` hereda de `QFrame` en Qt: un selector de clase sin acotar
    ("QFrame { border: ... }") le pintaba el mismo borde a los QLabel de
    adentro (título y contenido) — bug señalado por la clienta como
    "cuadritos dentro de los cuadros". El estilo tiene que quedar
    acotado por objectName, no por clase."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    tarjeta = _tarjeta_de(pantalla.panel_avance.etiqueta_periodo)
    assert tarjeta.objectName() == "cuadritoInfo"
    assert "QFrame#cuadritoInfo" in tarjeta.styleSheet()
    encabezado = tarjeta.findChildren(QLabel)[0]
    assert "border" not in encabezado.styleSheet()
    assert "border" not in pantalla.panel_avance.etiqueta_periodo.styleSheet()


def test_hay_una_linea_divisoria_entre_los_dos_botones(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    panel_izquierda = pantalla.panel_avance.boton_backup.parentWidget()
    lineas = [
        w for w in panel_izquierda.findChildren(QFrame)
        if w.frameShape() == QFrame.Shape.HLine
    ]
    assert len(lineas) == 1


def test_cada_boton_tiene_su_propia_explicacion_al_lado(qtbot, conn):
    """Antes había un único cuadro de texto para los dos botones; ahora
    cada uno tiene el suyo, en la misma fila que su botón — pedido
    explícito de la clienta ("a la par del botón correspondiente")."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    panel_avance = pantalla.panel_avance

    assert "Generar backup ahora copia la base de datos" in panel_avance.etiqueta_explicacion_backup.text()
    assert panel_avance.etiqueta_explicacion_avanzar.text() == (
        "Avanzar de mes realiza el pase de un mes a otro en el sistema. Este proceso ubica virtualmente al "
        "operador en el nuevo período cualquier sea la fecha real del día."
    )
    # Misma fila que su botón: ambos comparten padre directo (el QHBoxLayout
    # de esa fila reparenta sus widgets al mismo widget dueño del layout).
    assert panel_avance.etiqueta_explicacion_backup.parentWidget() is panel_avance.boton_backup.parentWidget()
    assert panel_avance.etiqueta_explicacion_avanzar.parentWidget() is panel_avance.boton_avanzar.parentWidget()


def test_titulo_de_fechas_especiales_es_corto(qtbot, conn):
    """Título largo anterior forzaba esa columna de la grilla más ancha
    que las otras dos — se acortó, pedido explícito de la clienta."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    tarjeta = _tarjeta_de(pantalla.panel_avance.etiqueta_fechas_especiales)
    encabezado = tarjeta.findChildren(QLabel)[0]
    assert encabezado.text() == "Feriados y fechas especiales próximas:"


def test_foco_inicial_queda_en_generar_backup(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.panel_avance.boton_backup.hasFocus())


def test_cadena_de_foco_entre_los_tres_botones_da_la_vuelta(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    panel_avance = pantalla.panel_avance
    assert panel_avance._foco._orden == [
        panel_avance.boton_backup, panel_avance.boton_restaurar, panel_avance.boton_avanzar,
    ]
    pantalla.show()
    qtbot.waitExposed(pantalla)
    panel_avance.boton_avanzar.setFocus()
    qtbot.waitUntil(lambda: panel_avance.boton_avanzar.hasFocus())
    panel_avance._foco._mover(panel_avance.boton_avanzar, retroceder=False, seleccionar_todo=False)
    qtbot.waitUntil(lambda: panel_avance.boton_backup.hasFocus())


def test_boton_restaurar_backup_es_secundario_y_mismo_ancho_que_generar(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    panel_avance = pantalla.panel_avance
    assert panel_avance.boton_restaurar.objectName() == "botonSecundario"
    assert panel_avance.boton_restaurar.width() == panel_avance.boton_backup.width()


def test_restaurar_backup_sin_elegir_carpeta_no_hace_nada(qtbot, conn, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_avance._restaurar_backup()  # no debe romper ni tocar la conexión
    conn.execute("SELECT 1")  # sigue abierta


def test_restaurar_backup_carpeta_sin_backups_avisa_y_no_rompe(qtbot, conn, tmp_path, monkeypatch):
    carpeta_vacia = tmp_path / "sin_backups"
    carpeta_vacia.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(carpeta_vacia)))
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_avance._restaurar_backup()
    conn.execute("SELECT 1")  # sigue abierta, no se tocó nada


def test_restaurar_backup_cancelado_en_la_eleccion_no_hace_nada(qtbot, conn, tmp_path, monkeypatch):
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBackup=str(tmp_path))
    conn.commit()
    generar_backup(conn, momento=datetime(2026, 1, 1, 10, 0))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_avance._restaurar_backup()
    conn.execute("SELECT 1")  # sigue abierta


def test_restaurar_backup_confirmado_restaura_la_base_y_cierra_el_programa(qtbot, conn, tmp_path, monkeypatch):
    """Caso real de punta a punta: genera un backup con un dato puntual,
    cambia ese dato SIN volver a respaldar, restaura por el botón, y
    confirma (con una conexión nueva, ya que la vieja se cierra) que el
    archivo en disco volvió al estado del backup — y que el programa
    pidió cerrarse, no que sigue funcionando con la conexión vieja."""
    carpeta_backups = tmp_path / "Drive"
    repo_cfg = obtener_repositorio(conn, "Configuracion")
    repo_cfg.actualizar(1, CarpetaBackup=str(carpeta_backups), NombreEspacio="Antes del backup")
    conn.commit()
    ruta_backup = generar_backup(conn, momento=datetime(2026, 1, 1, 10, 0))
    repo_cfg.actualizar(1, NombreEspacio="Cargado después, sin respaldar")
    conn.commit()
    db_path = conn.execute("PRAGMA database_list").fetchone()["file"]

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(carpeta_backups)))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: (ruta_backup.name, True)))
    llamadas_quit = []
    monkeypatch.setattr(QApplication, "quit", lambda *a, **k: llamadas_quit.append(1))

    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_avance._restaurar_backup()

    assert llamadas_quit == [1]
    conn_nueva = init_database(db_path)
    fila = conn_nueva.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["NombreEspacio"] == "Antes del backup"
    conn_nueva.close()


def test_banner_sin_sincronizar_oculto_por_defecto(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_avance.etiqueta_modo_sin_sincronizar.isHidden() is True


def test_banner_sin_sincronizar_visible_cuando_el_modo_esta_activo(qtbot, conn):
    db_path = conn.execute("PRAGMA database_list").fetchone()["file"]
    activar_modo_sin_sincronizar(db_path)

    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_avance.etiqueta_modo_sin_sincronizar.isHidden() is False


def test_scroll_de_cada_cuadrito_principal_tiene_fondo_transparente(qtbot, conn):
    """Punto 81: sin esto, el viewport del `QScrollArea` pintaba con el
    color de la paleta (`autoFillBackground` + `Base`) — un recuadro de
    color distinto al resto del cuadrito ("un cuadrito adentro del
    cuadrito"). `autoFillBackground(False)`, no un `setStyleSheet(...)`:
    ver `test_el_fondo_transparente_de_alertas_no_le_pisa_el_color_a_los_
    titulos` para el motivo (un stylesheet ahí rompía el color de los
    títulos de alerta, que están mucho más anidados)."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    for etiqueta in (
        pantalla.panel_avance.etiqueta_periodo, pantalla.panel_avance.etiqueta_estadisticas_principales,
        pantalla.panel_avance.etiqueta_ocupacion, pantalla.panel_avance.etiqueta_profesionales,
        pantalla.panel_avance.etiqueta_fechas_especiales, pantalla.panel_avance.etiqueta_cumpleanos,
    ):
        tarjeta = _tarjeta_de(etiqueta)
        scroll = tarjeta.findChild(QScrollArea)
        assert scroll.viewport().autoFillBackground() is False


def test_scroll_de_alertas_tambien_tiene_fondo_transparente(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    scroll = pantalla.panel_avance.tarjeta_alertas.findChild(QScrollArea)
    assert scroll.viewport().autoFillBackground() is False


def test_el_fondo_transparente_de_alertas_no_le_pisa_el_color_a_los_titulos(qtbot, conn):
    """Bug real, detectado por la clienta probando la pantalla: un
    `setStyleSheet("background: transparent;")` puesto en el `QScrollArea`
    de Alertas (un ancestro de cada `QFrame#tarjetaAlerta`/`QLabel#
    encabezadoAlerta`) le cambiaba el motor de pintado a TODOS los
    descendientes y terminaba pisándole el fondo naranja/letra blanca al
    título de cada alerta, pese a que esa regla tiene su propio selector
    por objectName en `estilos.py`. No debe quedar ningún `styleSheet`
    puesto en el `QScrollArea` ni en su viewport — el arreglo tiene que
    ser por `autoFillBackground`, que no pasa por ese motor."""
    _crear_profesional_regular_con_deuda(conn, "Deudor", 99999)
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    scroll = pantalla.panel_avance.tarjeta_alertas.findChild(QScrollArea)
    assert scroll.styleSheet() == ""
    assert scroll.viewport().styleSheet() == ""
    encabezado = next(
        lbl for lbl in pantalla.panel_avance.contenedor_alertas.findChildren(QLabel)
        if lbl.objectName() == "encabezadoAlerta"
    )
    assert "border" not in encabezado.styleSheet()  # sin estilo local que pueda competir con estilos.py


def test_contenido_de_un_solo_label_se_alinea_arriba_no_al_centro(qtbot, conn):
    """Sin `setAlignment(AlignTop)`, `setWidgetResizable(True)` estira el
    `QLabel` al alto del viewport y la alineación vertical default
    (`AlignVCenter`) lo deja centrado en vez de arriba."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    for etiqueta in (
        pantalla.panel_avance.etiqueta_estadisticas_principales, pantalla.panel_avance.etiqueta_ocupacion,
        pantalla.panel_avance.etiqueta_profesionales, pantalla.panel_avance.etiqueta_fechas_especiales,
        pantalla.panel_avance.etiqueta_cumpleanos,
    ):
        assert etiqueta.alignment() & Qt.AlignmentFlag.AlignTop


def test_alto_minimo_de_tarjeta_bajo_a_dos_tercios(qtbot, conn):
    """Revertido tras el feedback de la clienta: el primer intento sumaba
    `setFixedHeight` + un piso explícito para Alertas, pero probó la
    captura y confirmó que el mínimo solo (como se pidió desde el
    principio) ya daba el resultado que quería — se volvió a esa versión
    más simple, sin tocar nada del mecanismo de alto."""
    from app.gui.pantallas.panel_control import _ALTO_MINIMO_TARJETA
    assert _ALTO_MINIMO_TARJETA == 93  # round(140 * 2 / 3)


def test_fila1_fila2_y_alertas_quedan_del_mismo_alto(qtbot, conn):
    """Punto 82 (SistemaDF v0.11.2026.10), pedido explícito de la
    clienta: todo el alto que queda debajo de "Avanzar de mes" se reparte
    en tres franjas IGUALES — primera fila de tres cuadritos, segunda
    fila, y Alertas — no que Alertas se quede con lo que sobra después de
    que las filas tomen lo que piden. Antes la grilla y Alertas competían
    con stretch 0 vs 1 (Alertas terminaba mucho más chica o mucho más
    grande según la ventana, nunca igual); ahora las tres son hermanas de
    `layout_solapa` con el mismo `stretch=1`."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1200, 900)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    alto_fila1 = _tarjeta_de(pantalla.panel_avance.etiqueta_periodo).height()
    alto_fila2 = _tarjeta_de(pantalla.panel_avance.etiqueta_profesionales).height()
    alto_alertas = pantalla.panel_avance.tarjeta_alertas.height()
    # Tolerancia chica: redondeo de QBoxLayout al repartir píxeles entre
    # tres ítems, invisible a simple vista.
    assert max(alto_fila1, alto_fila2, alto_alertas) - min(alto_fila1, alto_fila2, alto_alertas) <= 8
