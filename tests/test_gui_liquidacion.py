import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import COLOR_ROJO
from app.gui.pantallas.liquidacion import ProcesoLiquidacion
from app.gui.widgets.selector_profesional import _ProxyBusquedaSinAcentos
from app.negocio.dias import periodo_actual
from app.negocio.formato import formatear_moneda
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


def _crear_profesional(conn, apellido="Gómez", id_codigo=None, saldo_anterior=0.0):
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, IdCodigo, SaldoCuentaAnterior) "
        "VALUES ('R', ?, ?, ?)",
        (apellido, id_codigo, saldo_anterior),
    )
    conn.commit()
    return conn.execute("SELECT IdProfesional FROM Profesional WHERE Apellido = ?", (apellido,)).fetchone()[
        "IdProfesional"
    ]


def test_periodo_por_defecto_es_el_actual(qtbot, conn):
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_emision.campo_periodo.text() == periodo_actual(conn)


def test_lista_solo_profesionales_categoria_r(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('A', 'Pérez')")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_emision.tabla.rowCount() == 1
    assert "Gómez" in pantalla.panel_emision.tabla.item(0, 1).text()


def test_nombre_profesional_usa_formato_canonico(qtbot, conn):
    _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_emision.tabla.item(0, 1).text() == "R1 - Lo Veci"


def test_calcula_monto_a_generar_sin_reservas(qtbot, conn):
    _crear_profesional(conn)
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_emision.tabla.item(0, 4).text() == "$ 0,00"
    assert pantalla.panel_emision.tabla.item(0, 5).text() == "Sin emitir"
    assert [
        pantalla.panel_emision.tabla.horizontalHeaderItem(i).text()
        for i in range(pantalla.panel_emision.tabla.columnCount())
    ] == ["Incluir", "Profesional", "Horas semanales", "Saldo anterior", "Monto a generar", "Estado"]


def test_columna_horas_semanales_suma_las_reservas_regulares_vigentes(qtbot, conn):
    id_prof = _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1A")
    id_consultorio = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana="Lunes",
        HoraInicio=9, HoraFin=11, VigenciaInicio="2026-01-01",
    )
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    item = pantalla.panel_emision.tabla.item(0, 2)
    assert item.text() == "2"
    assert item.textAlignment() == int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


def test_saldo_anterior_negativo_se_colorea_en_rojo(qtbot, conn):
    _crear_profesional(conn, saldo_anterior=-500)
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    item = pantalla.panel_emision.tabla.item(0, 3)
    assert item.text() == formatear_moneda(-500)
    assert item.foreground().color() == QColor(COLOR_ROJO)


def test_hay_tres_botones_de_emision(qtbot, conn):
    from PySide6.QtWidgets import QPushButton

    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    textos = {b.text() for b in pantalla.panel_emision.findChildren(QPushButton)}
    assert "Emitir liquidaciones seleccionadas" in textos
    assert "Emitir liquidaciones pendientes" in textos
    assert "Emitir todas las liquidaciones" in textos


def test_ningun_boton_de_emision_queda_resaltado_y_son_del_mismo_tamano(qtbot, conn):
    from PySide6.QtWidgets import QPushButton

    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    botones = [
        b for b in pantalla.panel_emision.findChildren(QPushButton)
        if b.text().startswith("Emitir ")
    ]
    assert len(botones) == 3
    assert all(b.objectName() == "botonAccion" for b in botones)


def test_orden_de_los_botones_es_pendientes_seleccionadas_todas(qtbot, conn):
    from PySide6.QtWidgets import QPushButton

    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    botones = [
        b for b in pantalla.panel_emision.findChildren(QPushButton)
        if b.text().startswith("Emitir ")
    ]
    assert [b.text() for b in botones] == [
        "Emitir liquidaciones pendientes", "Emitir liquidaciones seleccionadas", "Emitir todas las liquidaciones",
    ]


def test_check_incluir_queda_centrado_en_la_celda(qtbot, conn):
    _crear_profesional(conn)
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    item = pantalla.panel_emision.tabla.item(0, 0)
    assert item.textAlignment() == int(Qt.AlignmentFlag.AlignCenter)


def test_tabla_se_puede_ordenar_haciendo_clic_en_los_titulos(qtbot, conn):
    _crear_profesional(conn, apellido="Zeta", id_codigo="R9")
    _crear_profesional(conn, apellido="Alfa", id_codigo="R1")
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.panel_emision.tabla

    assert tabla.isSortingEnabled()
    tabla.sortItems(1, Qt.SortOrder.AscendingOrder)  # clic en "Profesional"

    assert tabla.item(0, 1).text() == "R1 - Alfa"
    assert tabla.item(1, 1).text() == "R9 - Zeta"


def test_ningun_profesional_seleccionado_por_defecto(qtbot, conn):
    _crear_profesional(conn)
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.panel_emision.tabla
    assert all(tabla.item(fila, 0).checkState() == Qt.CheckState.Unchecked for fila in range(tabla.rowCount()))


def test_orden_no_enviadas_arriba_y_luego_por_codigo(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    _crear_profesional(conn, apellido="Diez", id_codigo="R10")
    _crear_profesional(conn, apellido="Dos", id_codigo="R2")
    id_r5 = _crear_profesional(conn, apellido="Cinco", id_codigo="R5")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)

    # emite y marca como enviada la de R5 -> tiene que quedar al final pese al código
    from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio

    periodo = pantalla.panel_emision._periodo()
    emitir_liquidacion(conn, id_profesional=id_r5, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_r5, periodo=periodo, enviada=True)
    conn.commit()
    pantalla.panel_emision.actualizar()

    codigos = [pantalla.panel_emision.tabla.item(i, 1).text().split(" - ")[0] for i in range(3)]
    assert codigos == ["R2", "R10", "R5"]


def test_filtro_profesional_por_defecto_muestra_todos(qtbot, conn):
    _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    _crear_profesional(conn, apellido="Quito", id_codigo="R3")
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_emision

    assert panel.combo_profesional_filtro.currentText() == "Todos los profesionales"
    assert panel.tabla.rowCount() == 2


def test_filtro_profesional_deja_solo_el_seleccionado(qtbot, conn):
    _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    id_r3 = _crear_profesional(conn, apellido="Quito", id_codigo="R3")
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_emision

    indice = panel.combo_profesional_filtro.findData(id_r3)
    panel.combo_profesional_filtro.setCurrentIndex(indice)

    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 1).text() == "R3 - Quito"


def test_filtro_profesional_es_buscable_por_codigo_o_nombre(qtbot, conn):
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    completador = pantalla.panel_emision.combo_profesional_filtro.completer()
    assert isinstance(completador.model(), _ProxyBusquedaSinAcentos)


def test_filtro_estado_por_defecto_es_cualquier_estado(qtbot, conn):
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.panel_emision.combo_estado_filtro.currentText() == "Cualquier estado"


def test_filtro_estado_deja_solo_las_del_estado_elegido(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    id_r1 = _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    _crear_profesional(conn, apellido="Quito", id_codigo="R3")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_emision

    from app.negocio.liquidaciones import emitir_liquidacion

    emitir_liquidacion(conn, id_profesional=id_r1, periodo=panel._periodo())  # queda "No enviada"
    conn.commit()
    panel.actualizar()

    indice = panel.combo_estado_filtro.findText("Sin emitir")
    panel.combo_estado_filtro.setCurrentIndex(indice)

    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 1).text() == "R3 - Quito"


def test_foco_inicial_queda_en_periodo(qtbot, conn):
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.panel_emision.campo_periodo.hasFocus())


def test_emitir_sin_carpeta_base_no_falla_ni_emite(qtbot, conn):
    _crear_profesional(conn, id_codigo="R1")
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_emision._emitir_seleccionadas()
    assert conn.execute("SELECT COUNT(*) c FROM LiquidacionEmitida").fetchone()["c"] == 0


def test_emitir_seleccionadas_persiste_liquidacion_y_genera_pdf(qtbot, conn, tmp_path):
    _crear_profesional(conn, id_codigo="R1")
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    pantalla.panel_emision.tabla.item(0, 0).setCheckState(Qt.CheckState.Checked)

    pantalla.panel_emision._emitir_seleccionadas()

    fila = conn.execute("SELECT * FROM LiquidacionEmitida").fetchone()
    assert fila is not None
    assert fila["Periodo"] == periodo_actual(conn)
    assert fila["NombreArchivo"] is not None
    assert (tmp_path / "Profesionales" / "R1" / fila["NombreArchivo"]).exists()


def test_emitir_sin_seleccionados_no_emite(qtbot, conn, tmp_path):
    _crear_profesional(conn, id_codigo="R1")
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)

    pantalla.panel_emision._emitir_seleccionadas()
    assert conn.execute("SELECT COUNT(*) c FROM LiquidacionEmitida").fetchone()["c"] == 0


def test_emitir_pendientes_no_reemite_las_que_ya_estaban_emitidas(qtbot, conn, tmp_path):
    """"Emitir liquidaciones pendientes" es solo para las "Sin emitir" —
    a diferencia del viejo botón único, no debe tocar una que ya se
    generó (aunque todavía no se haya enviado)."""
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    id_r1 = _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    id_r3 = _crear_profesional(conn, apellido="Quito", id_codigo="R3")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_emision

    from app.negocio.liquidaciones import emitir_liquidacion

    periodo = panel._periodo()
    emitir_liquidacion(conn, id_profesional=id_r1, periodo=periodo)  # queda "No enviada"
    conn.commit()
    panel.actualizar()

    panel._emitir_pendientes()

    repo_liq = obtener_repositorio(conn, "LiquidacionEmitida")
    assert len(repo_liq.listar(IdProfesional=id_r1)) == 1  # no se reemitió: ya no está "Sin emitir"
    assert len(repo_liq.listar(IdProfesional=id_r3)) == 1  # esta sí, estaba pendiente


def test_emitir_todas_reemite_incluso_las_ya_enviadas(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    id_r1 = _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_emision

    from app.negocio.liquidaciones import emitir_liquidacion, marcar_estado_envio

    periodo = panel._periodo()
    emitir_liquidacion(conn, id_profesional=id_r1, periodo=periodo)
    marcar_estado_envio(conn, id_profesional=id_r1, periodo=periodo, enviada=True)
    conn.commit()
    panel.actualizar()

    panel._emitir_todas()

    filas = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_r1)
    assert len(filas) == 2  # se reemitió aunque ya estaba enviada
    ultima = max(filas, key=lambda f: f["IdLiquidacion"])
    assert ultima["EstadoEnvio"] == "Regenerada no enviada"


def test_solapa_estado_cuenta_lista_liquidaciones_del_profesional(qtbot, conn):
    id_prof = _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_prof, Periodo="2026-07", FechaEmision="2026-07-05", MontoGenerado=1000,
        EstadoEnvio="Enviada", NombreArchivo="julio.pdf",
    )
    obtener_repositorio(conn, "LiquidacionEmitida").crear(
        IdProfesional=id_prof, Periodo="2026-08", FechaEmision="2026-08-05", MontoGenerado=1100,
        EstadoEnvio="No enviada", NombreArchivo="agosto.pdf",
    )
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_estado_cuenta

    assert panel.tabla.rowCount() == 2
    assert panel.tabla.item(0, 0).text() == "2026-08"  # más reciente primero
    assert panel.tabla.item(0, 2).text() == formatear_moneda(1100)


def test_solapa_estado_cuenta_combo_es_buscable_por_codigo_o_nombre(qtbot, conn):
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    completador = pantalla.panel_estado_cuenta.combo_profesional.completer()
    assert isinstance(completador.model(), _ProxyBusquedaSinAcentos)


def test_solapa_estado_cuenta_tiene_columna_de_fecha_y_hora_de_generacion(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    id_prof = _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    conn.commit()
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel_emision = pantalla.panel_emision

    panel_emision.tabla.item(0, 0).setCheckState(Qt.CheckState.Checked)
    panel_emision._emitir_seleccionadas()

    panel = pantalla.panel_estado_cuenta
    panel.actualizar()
    indice = panel.combo_profesional.findData(id_prof)
    panel.combo_profesional.setCurrentIndex(indice)

    assert panel.tabla.horizontalHeaderItem(6).text() == "Fecha y hora generación del archivo"
    texto = panel.tabla.item(0, 6).text()
    assert texto != ""
    assert texto.endswith("hs")
    assert "/" in texto


def test_solapa_estado_cuenta_muestra_solo_saldo_actual_en_un_cuadro_de_solo_lectura(qtbot, conn):
    id_prof = _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    obtener_repositorio(conn, "Profesional").actualizar(
        id_prof, SaldoCuentaActual=1500, SaldoCuentaAnterior=-300,
    )
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_estado_cuenta
    indice = panel.combo_profesional.findData(id_prof)
    panel.combo_profesional.setCurrentIndex(indice)

    assert panel.campo_saldo_actual.isReadOnly()
    assert panel.campo_saldo_actual.text() == f"Saldo actual: {formatear_moneda(1500)}"
    assert not hasattr(panel, "campo_saldo_anterior")


def test_solapa_estado_cuenta_saldo_actual_negativo_se_colorea_en_rojo(qtbot, conn):
    id_prof = _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaActual=-500)
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_estado_cuenta
    indice = panel.combo_profesional.findData(id_prof)
    panel.combo_profesional.setCurrentIndex(indice)

    assert COLOR_ROJO in panel.campo_saldo_actual.styleSheet()


def test_solapa_estado_cuenta_conserva_el_profesional_elegido_al_refrescar(qtbot, conn):
    """Simula salir y volver a entrar al formulario: `actualizar()` es lo
    que se dispara al reconstruir/repoblar la pantalla, y no debe
    resetear la selección hecha por el operador."""
    id_prof = _crear_profesional(conn, apellido="Lo Veci", id_codigo="R1")
    _crear_profesional(conn, apellido="Quito", id_codigo="R3")
    pantalla = ProcesoLiquidacion(conn)
    qtbot.addWidget(pantalla)
    panel = pantalla.panel_estado_cuenta
    indice = panel.combo_profesional.findData(id_prof)
    panel.combo_profesional.setCurrentIndex(indice)

    panel.actualizar()

    assert panel.combo_profesional.currentData() == id_prof
