import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.mensajeria import CentroMensajeria
from app.negocio.archivos_generados import carpeta_profesional
from app.negocio.dias import periodo_actual
from app.negocio.mensajeria import color_profesional, marcar_mensaje_previo_generado
from app.negocio.pagos import crear_plan_pago_historico
from app.pdf.liquidacion_pdf import nombre_archivo_liquidacion
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    connection.execute(
        "UPDATE Configuracion SET CarpetaBaseArchivos = ?, ToleranciaDeudaDescuento = 100 WHERE IdConfiguracion = 1",
        (str(tmp_path / "archivos"),),
    )
    connection.commit()
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))


def _set_filtro(pantalla, clave: str) -> None:
    indice = pantalla.combo_filtro.findData(clave)
    assert indice >= 0, f"filtro desconocido: {clave}"
    pantalla.combo_filtro.setCurrentIndex(indice)


def _crear_profesional(conn, categoria="R", apellido="Gómez", saldo=0.0, codigo=None):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional=categoria, Apellido=apellido, SaldoCuentaAnterior=saldo, IdCodigo=codigo,
    )


def _color(conn, id_profesional):
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    return color_profesional(conn, profesional, periodo_actual(conn))


def _hacer_visible_aislada(conn, id_profesional):
    """Una categoría A sin ninguna reserva aislada del mes en curso en
    adelante se depura de la lista (DC-02 §2.2) — los tests que necesitan
    que aparezca le cargan una reserva del período actual."""
    id_consultorio = _crear_consultorio(conn)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha=f"{periodo_actual(conn)}-05",
        HoraInicio=10, HoraFin=11, Estado="Confirmada", AplicaRecargo=0,
    )


def test_centro_mensajeria_lista_profesionales_categoria_r(qtbot, conn):
    _crear_profesional(conn, saldo=500)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.rowCount() == 1
    assert "Gómez" in pantalla.tabla.item(0, 0).text()


def test_centro_mensajeria_muestra_estado_en_columna_propia(qtbot, conn):
    _crear_profesional(conn, saldo=0)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.item(0, 2).text() == "Situación regular"


def test_centro_mensajeria_muestra_nombre_y_apellido_sin_apodo(qtbot, conn):
    id_prof = _crear_profesional(conn, apellido="Lo Veci", saldo=0)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, NombrePila="Marcela", Apodo="Male")
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.item(0, 0).text() == "Marcela Lo Veci"


def test_centro_mensajeria_saldo_actual_suma_anterior_y_actual(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=1000)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaActual=500)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.item(0, 3).text() == "$ 1.000,00"
    assert pantalla.tabla.item(0, 4).text() == "$ 1.500,00"


def test_centro_mensajeria_cambia_a_categoria_aislada(qtbot, conn):
    id_prof = _crear_profesional(conn, categoria="A", apellido="Pérez")
    _hacer_visible_aislada(conn, id_prof)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 2).text() == "Con aisladas para enviar mensaje"


def test_centro_mensajeria_aislada_sin_reservas_vigentes_no_se_muestra(qtbot, conn):
    """DC-02 §2.2: se depura de la lista un A sin ninguna reserva del mes
    en curso en adelante."""
    _crear_profesional(conn, categoria="A", apellido="SinHoras")
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    assert pantalla.tabla.rowCount() == 0


def test_centro_mensajeria_aislada_con_reserva_pasada_no_se_muestra(qtbot, conn):
    id_prof = _crear_profesional(conn, categoria="A", apellido="YaPaso")
    id_consultorio = _crear_consultorio(conn)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2020-01-05",
        HoraInicio=10, HoraFin=11, Estado="Confirmada", AplicaRecargo=0,
    )
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    assert pantalla.tabla.rowCount() == 0


def test_centro_mensajeria_boton_grupal_llena_texto(qtbot, conn):
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla._mostrar_mensaje_grupal()
    assert "AVISOS VARIOS" in pantalla.texto_mensaje.toPlainText()


def test_centro_mensajeria_usa_periodo_actual_por_defecto(qtbot, conn):
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.campo_periodo.text() == periodo_actual(conn)


# ------------------------------------------------------------------ botón "Generar texto"

def test_generar_texto_marron_pasa_a_amarillo(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=1)  # dentro de tolerancia -> marrón
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    fila = pantalla._profesionales.index(next(p for p in pantalla._profesionales if p["IdProfesional"] == id_prof))
    pantalla.tabla.cellWidget(fila, 6).click()

    assert "se van a mandar los archivos" in pantalla.texto_mensaje.toPlainText()
    assert _color(conn, id_prof) == "amarillo"


def test_generar_texto_aislada_pasa_a_azul(qtbot, conn):
    id_prof = _crear_profesional(conn, categoria="A", apellido="Aislada")
    _hacer_visible_aislada(conn, id_prof)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")

    fila = pantalla._profesionales.index(next(p for p in pantalla._profesionales if p["IdProfesional"] == id_prof))
    pantalla.tabla.cellWidget(fila, 6).click()

    assert "DETALLE RESERVA" in pantalla.texto_mensaje.toPlainText()
    assert _color(conn, id_prof) == "azul"


def test_generar_texto_copia_al_portapapeles(qtbot, conn, monkeypatch):
    _crear_profesional(conn, saldo=0)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    copiado = []
    monkeypatch.setattr(
        "app.gui.pantallas.mensajeria.QGuiApplication.clipboard",
        staticmethod(lambda: type("_C", (), {"setText": lambda self, t: copiado.append(t)})()),
    )
    pantalla.tabla.cellWidget(0, 6).click()
    assert copiado and copiado[0] == pantalla.texto_mensaje.toPlainText()


# --------------------------------------------------------------------- check "Enviada"

def test_check_enviada_deshabilitado_para_marron(qtbot, conn):
    _crear_profesional(conn, saldo=1)  # dentro de tolerancia -> marrón
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    item = pantalla.tabla.item(0, 5)
    assert not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def test_check_enviada_deshabilitado_para_aislada(qtbot, conn):
    id_prof = _crear_profesional(conn, categoria="A", apellido="Pérez")
    _hacer_visible_aislada(conn, id_prof)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")

    item = pantalla.tabla.item(0, 5)
    assert not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def test_check_enviada_habilitado_para_verde_sin_liquidacion_emitida(qtbot, conn):
    """A diferencia del modelo anterior, el check ya está disponible para
    verde/naranja/rojo/violeta/gris aunque todavía no se haya emitido
    ninguna liquidación — es el propio check el que la genera (DC-02 §2.3)."""
    _crear_profesional(conn, saldo=0)  # verde
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    item = pantalla.tabla.item(0, 5)
    assert item.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert item.checkState() == Qt.CheckState.Unchecked


def test_marcar_enviada_emite_liquidacion_genera_pdf_y_baja_a_gris(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=0, codigo="R1")  # verde
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Checked)

    liquidaciones = obtener_repositorio(conn, "LiquidacionEmitida").listar()
    assert len(liquidaciones) == 1
    assert liquidaciones[0]["EstadoEnvio"] == "Enviada"
    assert liquidaciones[0]["NombreArchivo"]
    assert "MENSAJE AUTOMATICO" in pantalla.texto_mensaje.toPlainText()

    _set_filtro(pantalla, "todos")
    assert _color(conn, id_prof) == "gris"
    assert pantalla.tabla.item(0, 5).checkState() == Qt.CheckState.Checked


def test_marcar_enviada_amarillo_usa_situacion_2(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=1, codigo="R1")  # marrón -> lo subimos a mano a amarillo
    marcar_mensaje_previo_generado(conn, id_prof, periodo_actual(conn))

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert _color(conn, id_prof) == "amarillo"

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Checked)
    assert "en forma manual" in pantalla.texto_mensaje.toPlainText()


def test_marcar_enviada_violeta_borra_plazo_extendido(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=10000, codigo="R1")
    obtener_repositorio(conn, "Profesional").actualizar(
        id_prof, PlazoPagoExtendido="2099-01-01", MotivoPlazoExtra="Prometido",
    )
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert _color(conn, id_prof) == "violeta"

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Checked)

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["PlazoPagoExtendido"] is None
    assert profesional["MotivoPlazoExtra"] is None


def test_marcar_enviada_es_reversible(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=0, codigo="R1")
    periodo = periodo_actual(conn)
    id_liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_profesional, Periodo=periodo, EstadoEnvio="Enviada",
    )

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.item(0, 5).checkState() == Qt.CheckState.Checked

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Unchecked)

    liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liquidacion)
    assert liquidacion["EstadoEnvio"] == "No enviada"


def test_marcar_enviada_sin_carpeta_base_avisa_y_no_rompe(qtbot, conn):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = NULL WHERE IdConfiguracion = 1")
    conn.commit()
    _crear_profesional(conn, saldo=0, codigo="R1")
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Checked)  # no debe lanzar

    assert obtener_repositorio(conn, "LiquidacionEmitida").listar() == []


# ------------------------------------------------------------------------ filtros

def test_filtro_pendientes_es_el_default(qtbot, conn):
    _crear_profesional(conn, apellido="Gris", saldo=0, codigo="R1")
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=1, Periodo=periodo_actual(conn), EstadoEnvio="Enviada",
    )
    _crear_profesional(conn, apellido="Verde", saldo=0, codigo="R2")
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.combo_filtro.currentData() == "pendientes"
    assert pantalla.tabla.rowCount() == 1
    assert "Verde" in pantalla.tabla.item(0, 0).text()


def test_filtro_enviados(qtbot, conn):
    _crear_profesional(conn, apellido="Gris", saldo=0, codigo="R1")
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=1, Periodo=periodo_actual(conn), EstadoEnvio="Enviada",
    )
    _crear_profesional(conn, apellido="Verde", saldo=0, codigo="R2")
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "enviados")
    assert pantalla.tabla.rowCount() == 1
    assert "Gris" in pantalla.tabla.item(0, 0).text()


def test_filtro_todos_incluye_regulares_y_aisladas(qtbot, conn):
    _crear_profesional(conn, categoria="R", apellido="Regular")
    id_aislada = _crear_profesional(conn, categoria="A", apellido="Aislada")
    _hacer_visible_aislada(conn, id_aislada)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.rowCount() == 2


def test_filtro_solo_regulares(qtbot, conn):
    _crear_profesional(conn, categoria="R", apellido="Regular")
    id_aislada = _crear_profesional(conn, categoria="A", apellido="Aislada")
    _hacer_visible_aislada(conn, id_aislada)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "regulares")
    assert pantalla.tabla.rowCount() == 1
    assert "Regular" in pantalla.tabla.item(0, 0).text()


def test_filtro_solo_aisladas(qtbot, conn):
    _crear_profesional(conn, categoria="R", apellido="Regular")
    id_aislada = _crear_profesional(conn, categoria="A", apellido="Aislada")
    _hacer_visible_aislada(conn, id_aislada)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    assert pantalla.tabla.rowCount() == 1
    assert "Aislada" in pantalla.tabla.item(0, 0).text()


# ---------------------------------------------------------------------------- orden

def test_orden_por_color_y_dentro_de_cada_color_por_codigo(qtbot, conn):
    _crear_profesional(conn, apellido="RojoDos", saldo=10000, codigo="R2")
    id_rojo1 = _crear_profesional(conn, apellido="RojoUno", saldo=10000, codigo="R1")
    crear_plan_pago_historico(
        conn, id_profesional=id_rojo1, monto_refinanciado=10000, cantidad_cuotas=2,
        mes_ano_inicio=periodo_actual(conn),
    )
    id_rojo2 = obtener_repositorio(conn, "Profesional").listar(Apellido="RojoDos")[0]["IdProfesional"]
    crear_plan_pago_historico(
        conn, id_profesional=id_rojo2, monto_refinanciado=10000, cantidad_cuotas=2,
        mes_ano_inicio=periodo_actual(conn),
    )
    _crear_profesional(conn, apellido="Verde", saldo=0, codigo="R3")

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    nombres = [pantalla.tabla.item(i, 0).text() for i in range(pantalla.tabla.rowCount())]
    # verde va antes que rojo (DC-02 §2.1); entre los dos rojos, R2 antes que R1 (código descendente).
    assert nombres.index("Verde") < nombres.index("RojoDos")
    assert nombres.index("RojoDos") < nombres.index("RojoUno")


def test_orden_codigo_natural_descendente_r10_antes_de_r2(qtbot, conn):
    _crear_profesional(conn, apellido="Diez", saldo=0, codigo="R10")
    _crear_profesional(conn, apellido="Dos", saldo=0, codigo="R2")
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    nombres = [pantalla.tabla.item(i, 0).text() for i in range(pantalla.tabla.rowCount())]
    assert nombres.index("Diez") < nombres.index("Dos")


# ------------------------------------------------- combinar reservas aisladas (5.1)

def _crear_consultorio(conn, numero=1, valor=500):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=numero, ValorHoraAisladaActual=valor,
    )


def test_checks_combinar_aparecen_desmarcados_por_defecto(qtbot, conn):
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.check_combinar_misma_unidad.isChecked() is False
    assert pantalla.check_combinar_distintas_unidades.isChecked() is False


def test_no_expone_checks_de_incluir(qtbot, conn):
    """"Incluir consultorio/unidad/edificio" son controles de las
    pantallas de oferta/búsqueda (Disponibilidad, Lista de espera), no
    de este formulario — confirmado por el usuario."""
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert not hasattr(pantalla, "check_incluir_consultorio")
    assert not hasattr(pantalla, "check_incluir_unidad")
    assert not hasattr(pantalla, "check_incluir_edificio")


def test_mensaje_aislada_siempre_incluye_consultorio_y_unidad(qtbot, conn):
    id_consultorio = _crear_consultorio(conn, numero=7)
    id_prof = _crear_profesional(conn, categoria="A", apellido="Aislada")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    pantalla.tabla.cellWidget(0, 6).click()

    assert "consul 7" in pantalla.texto_mensaje.toPlainText()
    assert '7mo "L"' in pantalla.texto_mensaje.toPlainText()


def test_mensaje_aislada_por_defecto_no_combina(qtbot, conn):
    id_consultorio = _crear_consultorio(conn)
    id_prof = _crear_profesional(conn, categoria="A", apellido="Aislada")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-05", HoraInicio=14, HoraFin=16,
        Estado="Confirmada", AplicaRecargo=0,
    )

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    pantalla.tabla.cellWidget(0, 6).click()

    assert "y de" not in pantalla.texto_mensaje.toPlainText()


def test_tildar_combinar_misma_unidad_actualiza_el_mensaje(qtbot, conn):
    id_consultorio = _crear_consultorio(conn)
    id_prof = _crear_profesional(conn, categoria="A", apellido="Aislada")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha="2026-08-05", HoraInicio=14, HoraFin=16,
        Estado="Confirmada", AplicaRecargo=0,
    )

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    pantalla.check_combinar_misma_unidad.setChecked(True)
    pantalla.tabla.cellWidget(0, 6).click()

    assert "y de 14 a 16hs" in pantalla.texto_mensaje.toPlainText()


# ------------------------------------------------------ deshacer última acción

def test_deshacer_sin_acciones_no_rompe(qtbot, conn):
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla._deshacer_ultima_accion()  # no debe lanzar


def test_deshacer_marcar_enviada_sin_pdf_previo_borra_el_generado(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=0, codigo="R1")  # verde
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Checked)
    liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").listar()[0]
    ruta = carpeta_profesional(conn, "R1") / liquidacion["NombreArchivo"]
    assert ruta.exists()

    pantalla._deshacer_ultima_accion()

    assert obtener_repositorio(conn, "LiquidacionEmitida").listar() == []
    assert not ruta.exists()
    _set_filtro(pantalla, "todos")
    assert _color(conn, id_prof) == "verde"
    assert pantalla.tabla.item(0, 5).checkState() == Qt.CheckState.Unchecked


def test_deshacer_marcar_enviada_restaura_el_pdf_previo(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=0, codigo="R1")
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    periodo = periodo_actual(conn)
    ruta = carpeta_profesional(conn, "R1") / nombre_archivo_liquidacion(periodo, profesional)
    ruta.write_bytes(b"PDF-VIEJO")

    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Checked)
    assert ruta.read_bytes() != b"PDF-VIEJO"

    pantalla._deshacer_ultima_accion()

    assert ruta.read_bytes() == b"PDF-VIEJO"
    assert obtener_repositorio(conn, "LiquidacionEmitida").listar() == []


def test_deshacer_marcar_enviada_restaura_saldo_actual(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=0, codigo="R1")
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaActual=1234)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Checked)
    pantalla._deshacer_ultima_accion()

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["SaldoCuentaActual"] == 1234


def test_deshacer_marcar_enviada_violeta_restaura_plazo_extendido(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=10000, codigo="R1")
    obtener_repositorio(conn, "Profesional").actualizar(
        id_prof, PlazoPagoExtendido="2099-01-01", MotivoPlazoExtra="Prometido",
    )
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Checked)
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["PlazoPagoExtendido"] is None

    pantalla._deshacer_ultima_accion()

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["PlazoPagoExtendido"] == "2099-01-01"
    assert profesional["MotivoPlazoExtra"] == "Prometido"


def test_deshacer_desmarcar_enviada_la_vuelve_a_marcar(qtbot, conn):
    id_profesional = _crear_profesional(conn, saldo=0, codigo="R1")
    periodo = periodo_actual(conn)
    id_liquidacion = obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_profesional, Periodo=periodo, EstadoEnvio="Enviada",
    )
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Unchecked)
    assert obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liquidacion)["EstadoEnvio"] == "No enviada"

    pantalla._deshacer_ultima_accion()

    assert obtener_repositorio(conn, "LiquidacionEmitida").obtener(id_liquidacion)["EstadoEnvio"] == "Enviada"


def test_deshacer_generar_texto_marron_vuelve_a_marron(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=1, codigo="R1")  # dentro de tolerancia -> marrón
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.cellWidget(0, 6).click()
    assert _color(conn, id_prof) == "amarillo"

    pantalla._deshacer_ultima_accion()

    assert _color(conn, id_prof) == "marron"


def test_deshacer_generar_texto_aislada_vuelve_a_celeste(qtbot, conn):
    id_prof = _crear_profesional(conn, categoria="A", apellido="Aislada", codigo="A1")
    _hacer_visible_aislada(conn, id_prof)
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")

    pantalla.tabla.cellWidget(0, 6).click()
    assert _color(conn, id_prof) == "azul"

    pantalla._deshacer_ultima_accion()

    assert _color(conn, id_prof) == "celeste"


def test_generar_texto_sin_mutacion_no_deja_nada_para_deshacer(qtbot, conn):
    """Generar el texto de un color que no dispara ninguna transición de
    estado (verde) no debe dejar disponible una acción anterior más
    vieja para deshacer -> "última acción" es literal, la más reciente."""
    _crear_profesional(conn, saldo=0, codigo="R1")  # verde
    pantalla = CentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Checked)  # acción mutante
    assert pantalla._ultima_accion is not None

    _set_filtro(pantalla, "todos")
    pantalla.tabla.cellWidget(0, 6).click()  # generar texto de gris: no muta nada
    assert pantalla._ultima_accion is None

    pantalla._deshacer_ultima_accion()  # no debe revertir la marca como enviada
    assert obtener_repositorio(conn, "LiquidacionEmitida").listar()[0]["EstadoEnvio"] == "Enviada"
