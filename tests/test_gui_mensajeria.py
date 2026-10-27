import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.mensajeria import _PanelCentroMensajeria
from app.negocio.dias import fecha_actual, periodo_actual, ultimo_dia_mes
from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio
from app.negocio.mensajeria import color_profesional, marcar_recordatorio_deuda_x_generado
from app.negocio.pagos import crear_plan_pago_historico
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


def test_es_un_panel_solapa(qtbot, conn):
    """Reordenamiento de formularios: dejó de ser una pantalla propia con
    su propio título/QTabWidget — ahora es la solapa "Centro de
    mensajería" de "Grilla y mensajería" (ver grilla_y_mensajeria.py)."""
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.objectName() == "panelSolapa"


def test_tab_desde_mensaje_grupal_saltea_la_vista_previa_y_vuelve_a_filtro(qtbot, conn):
    """Pedido explícito de la clienta: "Vista previa" (texto_mensaje) es
    solo visual — Tab después de "Mensaje grupal" (último botón real de
    la cadena) tiene que volver directo a "Filtro", sin pasar por ahí (y
    sin que, si cae ahí de todos modos, insertar más Tabs produzca
    tabulaciones dentro del mensaje)."""
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    boton_grupal = pantalla._foco._orden[-1]
    boton_grupal.setFocus()
    qtbot.waitUntil(lambda: boton_grupal.hasFocus())
    qtbot.keyClick(boton_grupal, Qt.Key.Key_Tab)

    assert pantalla.combo_filtro.hasFocus()
    assert not pantalla.texto_mensaje.hasFocus()


def test_centro_mensajeria_lista_profesionales_categoria_r(qtbot, conn):
    _crear_profesional(conn, saldo=500)
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.rowCount() == 1
    assert "Gómez" in pantalla.tabla.item(0, 1).text()


def test_centro_mensajeria_muestra_estado_en_columna_propia(qtbot, conn):
    _crear_profesional(conn, saldo=0)
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.item(0, 2).text() == "Situación regular"


def test_centro_mensajeria_muestra_nombre_y_apellido_sin_apodo(qtbot, conn):
    id_prof = _crear_profesional(conn, apellido="Lo Veci", saldo=0)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, NombrePila="Marcela", Apodo="Male")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.item(0, 1).text() == "Marcela Lo Veci"


def test_centro_mensajeria_saldo_actual_suma_anterior_y_actual(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=1000)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaActual=500)
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.item(0, 3).text() == "$ 1.000,00"
    assert pantalla.tabla.item(0, 4).text() == "$ 1.500,00"


def test_centro_mensajeria_cambia_a_categoria_aislada(qtbot, conn):
    id_prof = _crear_profesional(conn, categoria="A", apellido="Pérez")
    _hacer_visible_aislada(conn, id_prof)
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 2).text() == "Con aisladas para enviar mensaje"


def test_centro_mensajeria_aislada_sin_reservas_vigentes_no_se_muestra(qtbot, conn):
    """DC-02 §2.2: se depura de la lista un A sin ninguna reserva del mes
    en curso en adelante."""
    _crear_profesional(conn, categoria="A", apellido="SinHoras")
    pantalla = _PanelCentroMensajeria(conn)
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
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    assert pantalla.tabla.rowCount() == 0


def test_centro_mensajeria_boton_grupal_llena_texto(qtbot, conn):
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla._mostrar_mensaje_grupal()
    assert "AVISOS VARIOS" in pantalla.texto_mensaje.toPlainText()


def test_centro_mensajeria_usa_periodo_actual_por_defecto(qtbot, conn):
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.campo_periodo.text() == periodo_actual(conn)


# ------------------------------------------------------------------ botón "Generar texto"

def test_generar_texto_amarillo_usa_el_mismo_mensaje_que_verde(qtbot, conn):
    """Corrección de la clienta: R dentro de tolerancia es amarillo desde
    el principio (sin marrón intermedio) y, por ahora, se trata igual
    que verde — mismo mensaje al generar texto, sin ninguna transición
    de color."""
    id_prof = _crear_profesional(conn, saldo=1)  # dentro de tolerancia -> amarillo
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert _color(conn, id_prof) == "amarillo"

    fila = pantalla._profesionales.index(next(p for p in pantalla._profesionales if p["IdProfesional"] == id_prof))
    pantalla.tabla.cellWidget(fila, 6).click()

    assert "Se adjunta liquidación" in pantalla.texto_mensaje.toPlainText()
    assert _color(conn, id_prof) == "amarillo"


def test_refrescar_reusa_el_boton_sin_duplicar_la_conexion(qtbot, conn):
    """Bug real: reemplazar el cellWidget de una fila que ya tenía uno
    (ej. al cambiar de filtro) podía dejar el botón viejo pintado por
    encima del nuevo hasta el próximo refresco de la tabla — se resuelve
    reusando el widget en vez de destruirlo y crear uno nuevo en su
    lugar. Acá se confirma que reusarlo no deja la conexión vieja
    sonando en paralelo (dispararía el mensaje del profesional
    equivocado, o dos veces, al hacer clic)."""
    id_uno = _crear_profesional(conn, apellido="Uno", saldo=1, codigo="R1")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    fila_uno = pantalla._profesionales.index(next(p for p in pantalla._profesionales if p["IdProfesional"] == id_uno))
    boton = pantalla.tabla.cellWidget(fila_uno, 6)

    id_dos = _crear_profesional(conn, apellido="Dos", saldo=1, codigo="R2")
    pantalla.actualizar()
    assert pantalla.tabla.cellWidget(fila_uno, 6) is boton  # se reusa, no se recrea

    llamadas = []
    pantalla._generar_y_mostrar = lambda p: llamadas.append(p["IdProfesional"])
    fila_dos = pantalla._profesionales.index(next(p for p in pantalla._profesionales if p["IdProfesional"] == id_dos))
    pantalla.tabla.cellWidget(fila_dos, 6).click()

    assert llamadas == [id_dos]  # una sola vez, y por el profesional que hoy ocupa esa fila


def test_generar_texto_aislada_pasa_a_azul(qtbot, conn):
    id_prof = _crear_profesional(conn, categoria="A", apellido="Aislada")
    _hacer_visible_aislada(conn, id_prof)
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")

    fila = pantalla._profesionales.index(next(p for p in pantalla._profesionales if p["IdProfesional"] == id_prof))
    pantalla.tabla.cellWidget(fila, 6).click()

    assert "DETALLE RESERVA" in pantalla.texto_mensaje.toPlainText()
    assert _color(conn, id_prof) == "azul"


def test_generar_texto_bordo_pasa_a_gris(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=0)
    id_consultorio = _crear_consultorio(conn)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio="2026-01-01", VigenciaFin=None,
    )
    periodo = periodo_actual(conn)
    emitir_liquidacion(conn, id_profesional=id_prof, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_prof, periodo=periodo, enviada=True)
    anio, mes = (int(p) for p in periodo.split("-"))
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = ? WHERE IdConfiguracion = 1",
        (ultimo_dia_mes(anio, mes).isoformat(),),
    )
    conn.commit()
    assert _color(conn, id_prof) == "bordo"

    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    fila = pantalla._profesionales.index(next(p for p in pantalla._profesionales if p["IdProfesional"] == id_prof))
    pantalla.tabla.cellWidget(fila, 6).click()

    assert "MENSAJE AUTOMATICO" in pantalla.texto_mensaje.toPlainText()
    assert "ESTADO DE CUENTA ACTUAL" in pantalla.texto_mensaje.toPlainText()
    assert _color(conn, id_prof) == "gris"


def test_generar_texto_copia_al_portapapeles(qtbot, conn, monkeypatch):
    _crear_profesional(conn, saldo=0)
    pantalla = _PanelCentroMensajeria(conn)
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

def test_check_enviada_deshabilitado_para_marron_categoria_x(qtbot, conn):
    """Marrón es ahora exclusivo de categoría X con deuda, y esta nunca
    tiene liquidación que marcar como enviada."""
    _crear_profesional(conn, categoria="X", saldo=5000)
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    item = pantalla.tabla.item(0, 5)
    assert not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def test_check_enviada_deshabilitado_para_aislada(qtbot, conn):
    id_prof = _crear_profesional(conn, categoria="A", apellido="Pérez")
    _hacer_visible_aislada(conn, id_prof)
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")

    item = pantalla.tabla.item(0, 5)
    assert not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def test_check_enviada_habilitado_para_verde_sin_liquidacion_emitida(qtbot, conn):
    """A diferencia del modelo anterior, el check ya está disponible para
    verde/naranja/rojo/violeta/gris aunque todavía no se haya emitido
    ninguna liquidación — es el propio check el que la genera (DC-02 §2.3)."""
    _crear_profesional(conn, saldo=0)  # verde
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    item = pantalla.tabla.item(0, 5)
    assert item.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert item.checkState() == Qt.CheckState.Unchecked


def test_marcar_enviada_emite_liquidacion_genera_pdf_y_baja_a_gris(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=0, codigo="R1")  # verde
    pantalla = _PanelCentroMensajeria(conn)
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


def test_marcar_enviada_amarillo_usa_el_mismo_mensaje_que_verde(qtbot, conn):
    """Corrección de la clienta: ya no hay un mensaje propio (la vieja
    Situación 2) para amarillo al marcar "Enviada" — usa el mismo
    mensaje que acompaña el PDF de liquidación, igual que verde."""
    id_prof = _crear_profesional(conn, saldo=1, codigo="R1")  # dentro de tolerancia -> amarillo

    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert _color(conn, id_prof) == "amarillo"

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Checked)
    assert "Se adjunta liquidación" in pantalla.texto_mensaje.toPlainText()


def test_marcar_enviada_violeta_borra_plazo_extendido(qtbot, conn):
    id_prof = _crear_profesional(conn, saldo=10000, codigo="R1")
    obtener_repositorio(conn, "Profesional").actualizar(
        id_prof, PlazoPagoExtendido="2099-01-01", MotivoPlazoExtra="Prometido",
    )
    pantalla = _PanelCentroMensajeria(conn)
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

    pantalla = _PanelCentroMensajeria(conn)
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
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.item(0, 5).setCheckState(Qt.CheckState.Checked)  # no debe lanzar

    assert obtener_repositorio(conn, "LiquidacionEmitida").listar() == []


# ------------------------------------------------------------------------ filtros

def test_filtro_todos_es_el_default(qtbot, conn):
    """Corrección de la clienta: "Todos" pasa a ser el filtro por
    defecto al entrar (reemplaza a "Pendientes de envío")."""
    _crear_profesional(conn, apellido="Gris", saldo=0, codigo="R1")
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=1, Periodo=periodo_actual(conn), EstadoEnvio="Enviada",
    )
    _crear_profesional(conn, apellido="Verde", saldo=0, codigo="R2")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.combo_filtro.currentData() == "todos"
    assert pantalla.tabla.rowCount() == 2


def test_filtro_enviados(qtbot, conn):
    _crear_profesional(conn, apellido="Gris", saldo=0, codigo="R1")
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=1, Periodo=periodo_actual(conn), EstadoEnvio="Enviada",
    )
    _crear_profesional(conn, apellido="Verde", saldo=0, codigo="R2")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "enviados")
    assert pantalla.tabla.rowCount() == 1
    assert "Gris" in pantalla.tabla.item(0, 1).text()


def test_filtro_todos_incluye_regulares_y_aisladas(qtbot, conn):
    _crear_profesional(conn, categoria="R", apellido="Regular")
    id_aislada = _crear_profesional(conn, categoria="A", apellido="Aislada")
    _hacer_visible_aislada(conn, id_aislada)
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.rowCount() == 2


def test_filtro_solo_regulares(qtbot, conn):
    _crear_profesional(conn, categoria="R", apellido="Regular")
    id_aislada = _crear_profesional(conn, categoria="A", apellido="Aislada")
    _hacer_visible_aislada(conn, id_aislada)
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "regulares")
    assert pantalla.tabla.rowCount() == 1
    assert "Regular" in pantalla.tabla.item(0, 1).text()


def test_filtro_solo_aisladas(qtbot, conn):
    _crear_profesional(conn, categoria="R", apellido="Regular")
    id_aislada = _crear_profesional(conn, categoria="A", apellido="Aislada")
    _hacer_visible_aislada(conn, id_aislada)
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    assert pantalla.tabla.rowCount() == 1
    assert "Aislada" in pantalla.tabla.item(0, 1).text()


# ------------------------------------------------------------- selector de profesional

def test_selector_profesional_todos_por_defecto(qtbot, conn):
    _crear_profesional(conn, apellido="Uno", saldo=0, codigo="R1")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.combo_profesional_filtro.currentText() == "Todos los profesionales"
    assert pantalla.combo_profesional_filtro.currentData() is None


def test_selector_profesional_acota_la_tabla_a_uno_puntual(qtbot, conn):
    id_uno = _crear_profesional(conn, apellido="Uno", saldo=0, codigo="R1")
    _crear_profesional(conn, apellido="Dos", saldo=0, codigo="R2")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.rowCount() == 2

    indice = pantalla.combo_profesional_filtro.findData(id_uno)
    pantalla.combo_profesional_filtro.setCurrentIndex(indice)

    assert pantalla.tabla.rowCount() == 1
    assert "Uno" in pantalla.tabla.item(0, 1).text()


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

    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    nombres = [pantalla.tabla.item(i, 1).text() for i in range(pantalla.tabla.rowCount())]
    # verde va antes que rojo (DC-02 §2.1); entre los dos rojos, R1 antes que R2 (código
    # ascendente — corregido a pedido de la clienta, se había probado descendente).
    assert nombres.index("Verde") < nombres.index("RojoUno")
    assert nombres.index("RojoUno") < nombres.index("RojoDos")


def test_orden_codigo_natural_ascendente_r2_antes_de_r10(qtbot, conn):
    _crear_profesional(conn, apellido="Diez", saldo=0, codigo="R10")
    _crear_profesional(conn, apellido="Dos", saldo=0, codigo="R2")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    nombres = [pantalla.tabla.item(i, 1).text() for i in range(pantalla.tabla.rowCount())]
    assert nombres.index("Dos") < nombres.index("Diez")


def test_columna_profesional_incluye_el_tratamiento(qtbot, conn):
    id_prof = _crear_profesional(conn, apellido="Lo Veci", saldo=0)
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, NombrePila="Virginia", Tratamiento="Lic.")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.item(0, 1).text() == "Lic. Virginia Lo Veci"


def test_columna_codigo_va_primero(qtbot, conn):
    _crear_profesional(conn, apellido="Lo Veci", saldo=0, codigo="R1")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.horizontalHeaderItem(0).text() == "Código"
    assert pantalla.tabla.horizontalHeaderItem(1).text() == "Profesional"
    assert pantalla.tabla.item(0, 0).text() == "R1"


def test_click_en_titulo_ordena_por_esa_columna(qtbot, conn):
    _crear_profesional(conn, apellido="Bajo", saldo=100, codigo="R9")
    _crear_profesional(conn, apellido="Alto", saldo=9000, codigo="R1")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.sortByColumn(3, Qt.SortOrder.AscendingOrder)  # Saldo anterior
    saldos = [pantalla.tabla.item(i, 3).text() for i in range(pantalla.tabla.rowCount())]
    assert saldos == ["$ 100,00", "$ 9.000,00"]  # numérico, no alfabético ("100" < "9000")


def test_click_en_titulo_codigo_usa_orden_natural(qtbot, conn):
    _crear_profesional(conn, apellido="Diez", saldo=0, codigo="R10")
    _crear_profesional(conn, apellido="Dos", saldo=0, codigo="R2")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.sortByColumn(0, Qt.SortOrder.AscendingOrder)  # Código
    codigos = [pantalla.tabla.item(i, 0).text() for i in range(pantalla.tabla.rowCount())]
    assert codigos == ["R2", "R10"]  # natural, no alfabético puro ("R10" < "R2" como texto)


def test_actualizar_despues_de_ordenar_vuelve_al_orden_por_color(qtbot, conn):
    _crear_profesional(conn, apellido="Bajo", saldo=100, codigo="R9")
    _crear_profesional(conn, apellido="Alto", saldo=9000, codigo="R1")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    orden_original = [pantalla.tabla.item(i, 1).text() for i in range(pantalla.tabla.rowCount())]

    pantalla.tabla.sortByColumn(3, Qt.SortOrder.AscendingOrder)
    pantalla.actualizar()

    assert [pantalla.tabla.item(i, 1).text() for i in range(pantalla.tabla.rowCount())] == orden_original


def test_tildar_enviada_despues_de_ordenar_afecta_al_profesional_correcto(qtbot, conn):
    """Bug potencial al agregar el orden por clic: `item.row()` ya no
    identifica de forma confiable al profesional si el usuario ordenó la
    tabla — el check tiene que guiarse por el IdProfesional guardado en
    el propio ítem, no por su posición visual."""
    _crear_profesional(conn, apellido="Bajo", saldo=1, codigo="R9")  # marrón
    id_alto = _crear_profesional(conn, apellido="Alto", saldo=0, codigo="R1")  # verde
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    pantalla.tabla.sortByColumn(1, Qt.SortOrder.AscendingOrder)  # Profesional: Alto antes que Bajo
    fila_alto = next(f for f in range(pantalla.tabla.rowCount()) if pantalla.tabla.item(f, 1).text() == "Alto")
    pantalla.tabla.item(fila_alto, 5).setCheckState(Qt.CheckState.Checked)

    assert _color(conn, id_alto) == "gris"


# ------------------------------------------------- combinar reservas aisladas (5.1)

def _crear_consultorio(conn, numero=1, valor=500):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=numero, ValorHoraAisladaActual=valor,
    )


def test_checks_combinar_aparecen_desmarcados_por_defecto(qtbot, conn):
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.check_combinar_misma_unidad.isChecked() is False
    assert pantalla.check_combinar_distintas_unidades.isChecked() is False


def test_no_expone_checks_de_incluir(qtbot, conn):
    """"Incluir consultorio/unidad/edificio" son controles de las
    pantallas de oferta/búsqueda (Disponibilidad, Lista de espera), no
    de este formulario — confirmado por el usuario."""
    pantalla = _PanelCentroMensajeria(conn)
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
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-05' WHERE IdConfiguracion = 1"
    )
    conn.commit()

    pantalla = _PanelCentroMensajeria(conn)
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
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-05' WHERE IdConfiguracion = 1"
    )
    conn.commit()

    pantalla = _PanelCentroMensajeria(conn)
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
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-05' WHERE IdConfiguracion = 1"
    )
    conn.commit()

    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    pantalla.check_combinar_misma_unidad.setChecked(True)
    pantalla.tabla.cellWidget(0, 6).click()

    assert "y de 14 a 16hs" in pantalla.texto_mensaje.toPlainText()



def test_etiqueta_filtro_dice_filtro_de_visualizacion(qtbot, conn):
    """Punto 91 (SistemaDF v0.11.2026.10)."""
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    etiquetas = [w.text() for w in pantalla.findChildren(QLabel)]
    assert "Filtro de visualización" in etiquetas
    assert "Filtro" not in etiquetas


def test_reiniciar_vuelve_el_filtro_y_periodo_a_su_default(qtbot, conn):
    """Punto 1.4: al volver a entrar (o F3) se resetean los filtros
    propios de esta solapa."""
    id_prof = _crear_profesional(conn, saldo=0, codigo="R1")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "aisladas")
    pantalla.combo_profesional_filtro.setCurrentIndex(
        pantalla.combo_profesional_filtro.findData(id_prof)
    )
    pantalla.campo_periodo.setText("2020-01")
    pantalla.check_combinar_misma_unidad.setChecked(True)

    pantalla.reiniciar()

    assert pantalla.combo_filtro.currentData() == "todos"
    assert pantalla.combo_profesional_filtro.currentIndex() == 0
    assert pantalla.campo_periodo.text() != "2020-01"
    assert pantalla.check_combinar_misma_unidad.isChecked() is False


def test_marcar_enviada_vuelve_el_scroll_al_principio(qtbot, conn):
    """Punto 90: el refresco al marcar "Enviada" tiene que dejar la
    parte de arriba de la tabla a la vista."""
    for codigo in ("R1", "R2"):
        obtener_repositorio(conn, "Profesional").crear(
            CategoriaProfesional="R", IdCodigo=codigo, Apellido=f"Prof{codigo}",
        )
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.verticalScrollBar().setValue(pantalla.tabla.verticalScrollBar().maximum())

    item = pantalla.tabla.item(0, 5)
    if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
        item.setCheckState(Qt.CheckState.Checked)

    assert pantalla.tabla.verticalScrollBar().value() == 0


# --------------------------------------------- categoría X con deuda (marrón/gris)

def test_categoria_x_sin_deuda_no_aparece(qtbot, conn):
    _crear_profesional(conn, categoria="X", apellido="SinDeuda", saldo=0)
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.rowCount() == 0


def test_categoria_x_con_deuda_aparece_marron(qtbot, conn):
    _crear_profesional(conn, categoria="X", apellido="ConDeuda", saldo=5000, codigo="X1")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert pantalla.tabla.rowCount() == 1
    assert "dejó el espacio" in pantalla.tabla.item(0, 2).text().lower()


def test_generar_texto_marron_x_copia_mensaje_y_pasa_a_gris(qtbot, conn):
    id_prof = _crear_profesional(conn, categoria="X", apellido="ConDeuda", saldo=5000, codigo="X1")
    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")
    assert _color(conn, id_prof) == "marron"

    pantalla.tabla.cellWidget(0, 6).click()

    assert "MENSAJE AUTOMATICO" in pantalla.texto_mensaje.toPlainText()
    assert "pendiente de cancelación" in pantalla.texto_mensaje.toPlainText()
    assert _color(conn, id_prof) == "gris"


def test_categoria_x_gris_queda_al_final_del_grupo_gris(qtbot, conn):
    """Pedido de la clienta: primero los grises de siempre (R/A), al
    final los grises de categoría X, ordenados por código."""
    id_x = _crear_profesional(conn, categoria="X", apellido="ConDeuda", saldo=5000, codigo="X1")
    marcar_recordatorio_deuda_x_generado(conn, id_x, fecha_actual(conn))

    id_r = _crear_profesional(conn, categoria="R", apellido="Gris", saldo=0, codigo="R9")
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_r, Periodo=periodo_actual(conn), EstadoEnvio="Enviada",
    )

    pantalla = _PanelCentroMensajeria(conn)
    qtbot.addWidget(pantalla)
    _set_filtro(pantalla, "todos")

    assert _color(conn, id_r) == "gris"
    assert _color(conn, id_x) == "gris"
    assert pantalla.tabla.rowCount() == 2
    assert "Gris" in pantalla.tabla.item(0, 1).text()  # gris de R primero
    assert "ConDeuda" in pantalla.tabla.item(1, 1).text()  # gris de X al final
