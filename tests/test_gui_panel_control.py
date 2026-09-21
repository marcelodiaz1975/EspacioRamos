from datetime import datetime

import pytest
from PySide6.QtWidgets import QGridLayout, QLabel, QMessageBox, QTabWidget, QWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.main_window import Seccion, VentanaPrincipal
from app.gui.pantallas.panel_control import PanelControl
from app.negocio.backup import generar_backup
from app.negocio.lista_espera import crear_pedido
from app.repositorio.registro import obtener_repositorio


def _textos_visibles(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


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


def test_panel_control_muestra_nombre_del_espacio(qtbot, conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, NombreEspacio="Mi Espacio")
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.titulo.text() == "Mi Espacio"


def test_panel_control_boton_avanzar_habilitado_a_mitad_de_mes(qtbot, conn):
    # DC-06 §1: el avance de mes tiene que estar disponible en cualquier
    # momento, no solo al principio o fin de mes.
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_avanzar.isEnabled() is True


def test_panel_control_sin_alertas_muestra_mensaje(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert any("Sin alertas pendientes." in t for t in _textos_visibles(pantalla.contenedor_alertas))


def test_panel_control_alerta_de_deuda_se_muestra(qtbot, conn):
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Deudor", SaldoCuentaAnterior=99999,
    )
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert any("Deudor" in t for t in _textos_visibles(pantalla.contenedor_alertas))


def test_panel_control_alerta_de_backup_vencido_se_muestra(qtbot, conn, tmp_path):
    conn.execute(
        "UPDATE Configuracion SET CarpetaBackup = ?, FrecuenciaBackupDrive = 'Diario' WHERE IdConfiguracion = 1",
        (str(tmp_path / "backups"),),
    )
    conn.commit()
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert any("Backup vencido" in t for t in _textos_visibles(pantalla.contenedor_alertas))


def test_generar_backup_sin_carpeta_configurada_no_falla(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla._generar_backup()  # solo debe avisar, no lanzar


def test_generar_backup_con_carpeta_configurada(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBackup=str(tmp_path / "backups"))
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla._generar_backup()
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

    pantalla._avanzar_mes()

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

    pantalla._avanzar_mes()

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

    pantalla._avanzar_mes()

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

    pantalla._avanzar_mes()

    assert len(preguntas) == 1  # solo la confirmación del avance, sin la pregunta de aumentos
    assert "evaluar un aumento" not in preguntas[0]
    snapshots = obtener_repositorio(conn, "SnapshotMensual").listar()
    assert snapshots[0]["PorcentajeAumentoAplicado"] == 5.0


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

    pantalla._avanzar_mes()

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

    pantalla._avanzar_mes()

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
    assert ventana._pila.count() == 2
    ventana._navegacion.setCurrentRow(2)  # fila 0 = separador, 1 = primera, 2 = segunda
    assert ventana._pila.currentIndex() == 1


# --------------------------------------------------------- formato solapa


def test_tiene_formato_solapa_con_una_pestana(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert solapas.tabText(0) == "Panel de control"
    assert pantalla.findChild(QWidget, "panelSolapa") is not None


def test_avanzar_de_mes_es_primario_y_backup_secundario(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_avanzar.objectName() == "botonPrimario"
    assert pantalla.boton_backup.objectName() == "botonSecundario"


def test_los_dos_botones_comparten_el_mismo_ancho_fijo(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_avanzar.width() == pantalla.boton_backup.width()


def test_no_quedan_las_leyendas_ni_el_subtitulo_viejos(qtbot, conn):
    """Se sacaron a pedido de la clienta: esa información ahora vive en
    los cuadritos de abajo."""
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert not hasattr(pantalla, "subtitulo")
    assert not hasattr(pantalla, "leyenda_periodo")
    assert not hasattr(pantalla, "leyenda_backup")


def test_tarjeta_reloj_muestra_fecha_y_hora_real_con_segundos(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.etiqueta_reloj.text()
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
    assert pantalla.etiqueta_reloj.text() == "mar 25-08-2026 14:45:00hs"
    pantalla._actualizar_reloj()
    assert pantalla.etiqueta_reloj.text() == "mar 25-08-2026 14:45:01hs"


def test_tarjeta_periodo_actual(qtbot, conn):
    conn.execute("UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1")
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.etiqueta_periodo.text() == "Agosto de 2026 (08/2026)"


def test_tarjeta_backup_sin_ninguno_generado(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert "Todavía no se generó ningún backup." in pantalla.etiqueta_backup.text()


def test_tarjeta_backup_con_uno_ya_generado(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, CarpetaBackup=str(tmp_path / "backups"), FrecuenciaBackupDrive="Semanal",
    )
    generar_backup(conn, momento=datetime(2026, 8, 25, 14, 45))
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.etiqueta_backup.text()
    assert "Último backup: mar 25-08-2026 14:45hs" in texto
    assert "Frecuencia configurada: Semanal" in texto
    assert "Estado:" in texto


def test_generar_backup_actualiza_la_tarjeta(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBackup=str(tmp_path / "backups"))
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert "Todavía no se generó ningún backup." in pantalla.etiqueta_backup.text()

    pantalla._generar_backup()

    assert "Último backup:" in pantalla.etiqueta_backup.text()


def test_tarjeta_fechas_especiales_sin_datos(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert "Sin fechas especiales cargadas" in pantalla.etiqueta_fechas_especiales.text()


def test_tarjeta_fechas_especiales_lista_mes_actual_y_siguiente(qtbot, conn):
    conn.execute("UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-20", Descripcion="Feriado puente", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-10-05", Descripcion="Fuera de rango", Activo=1)
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.etiqueta_fechas_especiales.text()
    assert "2026-08-20" in texto
    assert "Feriado puente" in texto
    assert "2026-10-05" not in texto


def test_tarjeta_profesionales_muestra_los_tres_conteos(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.etiqueta_profesionales.text()
    assert "Con plan de pago vigente: 0" in texto
    assert "Con saldo fuera de tolerancia: 0" in texto
    assert "Con reservas regulares activas: 0" in texto


def test_tarjeta_ocupacion_muestra_las_cinco_metricas(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    texto = pantalla.etiqueta_ocupacion.text()
    assert "Ocupación regular general:" in texto
    assert "Horas regulares reservadas por semana:" in texto
    assert "Horas aisladas reservadas este mes:" in texto
    assert "Monto generado por esas horas aisladas:" in texto
    assert "Saldo pendiente de cobro este mes:" in texto


def test_tarjeta_alertas_sigue_mostrando_las_alertas_de_siempre(qtbot, conn):
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Deudor", SaldoCuentaAnterior=99999,
    )
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert any("Deudor" in t for t in _textos_visibles(pantalla.contenedor_alertas))


def test_hay_seis_tarjetas_parejas_en_la_grilla_y_alertas_aparte(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1200, 800)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    grilla = pantalla.findChild(QGridLayout)
    assert grilla is not None
    assert grilla.count() == 6

    # Tolerancia de 1px: QGridLayout reparte el resto de una división no
    # exacta (ancho de ventana / 3 columnas) en algún borde, invisible a
    # simple vista pero real en píxeles.
    tarjetas = [grilla.itemAt(i).widget() for i in range(6)]
    anchos = [t.width() for t in tarjetas]
    altos = [t.height() for t in tarjetas]
    assert max(anchos) - min(anchos) <= 1  # las seis del mismo ancho
    assert max(altos) - min(altos) <= 1  # las seis del mismo alto


def test_tarjeta_alertas_no_esta_en_la_grilla(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    grilla = pantalla.findChild(QGridLayout)
    assert all(grilla.itemAt(i).widget() is not pantalla.tarjeta_alertas for i in range(grilla.count()))


def test_tarjeta_alertas_ocupa_mucho_mas_ancho_que_una_tarjeta_de_la_grilla(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1200, 800)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    grilla = pantalla.findChild(QGridLayout)
    ancho_una_tarjeta = grilla.itemAt(0).widget().width()
    assert pantalla.tarjeta_alertas.width() > ancho_una_tarjeta * 2


def test_titulos_de_las_tarjetas_van_en_italica_con_dos_puntos(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    encabezado = pantalla.etiqueta_periodo.parentWidget().findChildren(QLabel)[0]
    assert encabezado.text() == "Período actual:"
    assert "italic" in encabezado.styleSheet()


def test_foco_inicial_queda_en_generar_backup(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.boton_backup.hasFocus())


def test_cadena_de_foco_entre_los_dos_botones_da_la_vuelta(qtbot, conn):
    pantalla = PanelControl(conn)
    qtbot.addWidget(pantalla)
    assert pantalla._foco._orden == [pantalla.boton_backup, pantalla.boton_avanzar]
    pantalla.show()
    qtbot.waitExposed(pantalla)
    pantalla.boton_avanzar.setFocus()
    qtbot.waitUntil(lambda: pantalla.boton_avanzar.hasFocus())
    pantalla._foco._mover(pantalla.boton_avanzar, retroceder=False, seleccionar_todo=False)
    qtbot.waitUntil(lambda: pantalla.boton_backup.hasFocus())
