import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QWidget,
)

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import hoja_estilos
from app.gui.main_window import Seccion, VentanaPrincipal
from app.gui.pantallas.configuracion import (
    _CAMPOS_BOOLEANOS,
    _CAMPOS_ESPECIALES,
    _CAMPOS_FECHA,
    _CAMPOS_NUMERICOS,
    _CAMPOS_TEXTO,
    _GRUPOS,
    _CampoRuta,
    ConfiguracionGeneral,
)


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


def test_carga_valores_existentes(qtbot, conn):
    conn.execute("UPDATE Configuracion SET NombreEspacio = 'Mi Espacio', HoraInicioGrilla = 7 WHERE IdConfiguracion = 1")
    conn.commit()
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    assert pantalla._entradas["NombreEspacio"].text() == "Mi Espacio"
    assert pantalla._entradas["HoraInicioGrilla"].value() == 7.0


def test_guardar_persiste_texto_y_numero(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["NombreEspacio"].setText("Espacio Nuevo")
    pantalla._entradas["ToleranciaDeudaDescuento"].setValue(500)
    pantalla._guardar()

    fila = conn.execute("SELECT * FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["NombreEspacio"] == "Espacio Nuevo"
    assert fila["ToleranciaDeudaDescuento"] == 500.0


def test_guardar_persiste_booleano(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["ModoFechaFicticia"].setChecked(True)
    pantalla._guardar()
    fila = conn.execute("SELECT ModoFechaFicticia FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["ModoFechaFicticia"] == 1


def test_guardar_ruta_logo_y_decimales(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["RutaLogo"].setText("/tmp/logo.png")
    pantalla._entradas["CantidadDecimales"].setValue(0)
    pantalla._guardar()

    fila = conn.execute("SELECT RutaLogo, CantidadDecimales FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["RutaLogo"] == "/tmp/logo.png"
    assert fila["CantidadDecimales"] == 0.0


def test_guardar_persiste_modo_oscuro(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["ModoOscuro"].setChecked(True)
    pantalla._guardar()
    fila = conn.execute("SELECT ModoOscuro FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["ModoOscuro"] == 1


def test_guardar_persiste_visualizar_campos_libres(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["VisualizarCamposLibres"].setChecked(False)
    pantalla._guardar()
    fila = conn.execute("SELECT VisualizarCamposLibres FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["VisualizarCamposLibres"] == 0


def test_guardar_modo_oscuro_aplica_el_tema_sin_reiniciar(qtbot, conn):
    """Al guardar desde la pantalla embebida en la ventana principal, el
    cambio se ve enseguida (mismo criterio que la barra de fecha
    ficticia) — no hace falta cambiar de sección para que se note."""
    ventana = VentanaPrincipal(conn, [Seccion("Configuración", lambda c: ConfiguracionGeneral(c), categoria="Principal")])
    qtbot.addWidget(ventana)
    assert ventana.styleSheet() == hoja_estilos(False)

    pantalla = ventana._pila.widget(0)
    pantalla._entradas["ModoOscuro"].setChecked(True)
    pantalla._guardar()

    assert ventana.styleSheet() == hoja_estilos(True)


def test_tolerancia_deuda_es_un_spinbox_y_nunca_queda_en_estado_invalido(qtbot, conn):
    """Antes era un QLineEdit de texto libre que había que parsear a
    mano; ahora es un QDoubleSpinBox, así que ya no existe la posibilidad
    de tipear "no es un número" — Qt ni siquiera lo deja escribir."""
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla._entradas["ToleranciaDeudaDescuento"], QDoubleSpinBox)


def test_spinboxes_de_porcentaje_no_admiten_mas_de_cien_por_ciento(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    campo = pantalla._entradas["PorcentajeDescuentoFeriado"]
    campo.setValue(500)
    assert campo.value() == 100.0


def test_hora_inicio_grilla_se_muestra_como_horario(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    campo = pantalla._entradas["HoraInicioGrilla"]
    campo.setValue(8.5)
    assert campo.textFromValue(campo.value()) == "8:30hs"


def test_cantidad_decimales_es_un_spinbox_entero(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla._entradas["CantidadDecimales"], QSpinBox)


def test_fecha_ficticia_es_un_selector_de_calendario(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    campo = pantalla._entradas["FechaFicticia"]
    assert isinstance(campo, QDateEdit)
    assert campo.calendarPopup()


def test_fecha_ficticia_null_en_la_base_carga_la_fecha_de_hoy(qtbot, conn):
    conn.execute("UPDATE Configuracion SET FechaFicticia = NULL WHERE IdConfiguracion = 1")
    conn.commit()
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    assert pantalla._entradas["FechaFicticia"].date() == QDate.currentDate()


def test_guardar_con_fecha_ficticia_persiste_en_formato_iso(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["FechaFicticia"].setDate(QDate(2026, 9, 15))
    pantalla._guardar()
    fila = conn.execute("SELECT FechaFicticia FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["FechaFicticia"] == "2026-09-15"


def _campo_ruta_de(pantalla: ConfiguracionGeneral, nombre: str) -> _CampoRuta:
    entrada = pantalla._entradas[nombre]
    return next(w for w in pantalla.findChildren(_CampoRuta) if w.campo is entrada)


def test_ruta_logo_tiene_boton_elegir_que_abre_selector_de_archivo(qtbot, conn, monkeypatch, tmp_path):
    archivo = tmp_path / "logo.png"
    archivo.write_bytes(b"")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(archivo), "")))
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)

    campo_ruta = _campo_ruta_de(pantalla, "RutaLogo")
    assert campo_ruta.boton.text() == "Elegir"
    campo_ruta.boton.click()

    assert pantalla._entradas["RutaLogo"].text() == str(archivo)


def test_ruta_logo_cancelar_el_selector_no_borra_lo_que_ya_habia(qtbot, conn, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["RutaLogo"].setText("/ya/cargado/logo.png")

    _campo_ruta_de(pantalla, "RutaLogo").boton.click()

    assert pantalla._entradas["RutaLogo"].text() == "/ya/cargado/logo.png"


def test_carpeta_base_archivos_tiene_boton_elegir_que_abre_selector_de_carpeta(qtbot, conn, monkeypatch, tmp_path):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)

    _campo_ruta_de(pantalla, "CarpetaBaseArchivos").boton.click()

    assert pantalla._entradas["CarpetaBaseArchivos"].text() == str(tmp_path)


def test_guardar_con_json_invalido_no_persiste(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    valor_original = conn.execute(
        "SELECT DiasGrilla FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()["DiasGrilla"]

    pantalla._entradas["DiasGrilla"].setText("{esto no es json}")
    pantalla._guardar()

    fila = conn.execute("SELECT DiasGrilla FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["DiasGrilla"] == valor_original


# --------------------------------------------------------- formato solapa


def test_titulo_de_pantalla_es_jerarquia_1(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "CONFIGURACIÓN GENERAL"


def test_tiene_formato_solapa_con_las_seis_pestanas(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == [titulo for titulo, _campos in _GRUPOS]
    assert len(pantalla.findChildren(QWidget, "panelSolapa")) == len(_GRUPOS)


def test_todos_los_campos_estan_agrupados_una_sola_vez(qtbot, conn):
    """Ningún campo se pierde ni queda duplicado al pasar del formulario
    plano a los grupos temáticos — incluye los "campos especiales"
    (ej. Contraseña maestra), que no se guardan como el resto pero
    también tienen que aparecer agrupados una sola vez."""
    todos = {
        nombre
        for nombre, _ in _CAMPOS_TEXTO + _CAMPOS_NUMERICOS + _CAMPOS_BOOLEANOS + _CAMPOS_FECHA + _CAMPOS_ESPECIALES
    }
    agrupados: list[str] = [nombre for _titulo, campos in _GRUPOS for nombre in campos]
    assert sorted(agrupados) == sorted(todos)
    assert len(agrupados) == len(set(agrupados))


def test_cada_solapa_carga_todos_sus_campos(qtbot, conn):
    """Los campos "ruta" suman un control más a la cadena de foco (el
    botón "Elegir"), así que la comprobación es "está en algún lado de
    `orden`", no una correspondencia 1 a 1 por posición. Los "campos
    especiales" (ej. Contraseña maestra) no están en `_entradas` —
    alcanza con que su botón esté en `orden`."""
    nombres_especiales = {nombre for nombre, _ in _CAMPOS_ESPECIALES}
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    for panel, (_titulo, nombres) in zip(pantalla._paneles, _GRUPOS):
        for nombre in nombres:
            if nombre in nombres_especiales:
                continue
            assert pantalla._entradas[nombre] in panel.orden


def test_foco_inicial_queda_en_el_primer_campo_de_la_primera_solapa(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    primer_campo = pantalla._paneles[0].orden[0]
    qtbot.waitUntil(lambda: primer_campo.hasFocus())


def test_cambiar_de_solapa_enfoca_el_primer_campo_de_la_nueva(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    pantalla.pestanas.setCurrentIndex(1)
    primer_campo_grilla = pantalla._paneles[1].orden[0]
    qtbot.waitUntil(lambda: primer_campo_grilla.hasFocus())


def test_cadena_de_foco_de_una_solapa_termina_en_guardar_y_vuelve_al_principio(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    panel = pantalla._paneles[0]
    assert pantalla._foco._orden == panel.orden + [pantalla.boton_guardar]

    pantalla.boton_guardar.setFocus()
    qtbot.waitUntil(lambda: pantalla.boton_guardar.hasFocus())
    pantalla._foco._mover(pantalla.boton_guardar, retroceder=False, seleccionar_todo=False)
    qtbot.waitUntil(lambda: panel.orden[0].hasFocus())


def test_cadena_de_foco_se_reinstala_al_cambiar_de_solapa(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla.pestanas.setCurrentIndex(2)
    panel = pantalla._paneles[2]
    assert pantalla._foco._orden == panel.orden + [pantalla.boton_guardar]


# --------------------------------------------------------------- Seguridad


def test_minutos_inactividad_persiste(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["MinutosInactividadBloqueo"].setValue(30)
    pantalla._guardar()
    fila = conn.execute("SELECT MinutosInactividadBloqueo FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["MinutosInactividadBloqueo"] == 30


def test_contrasena_maestra_no_tiene_campo_de_texto_en_entradas(qtbot, conn):
    """No debe poder leerse/editarse como un campo de texto común — solo
    se cambia a través de su propio diálogo."""
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    assert "ContrasenaMaestra" not in pantalla._entradas


def test_contrasena_maestra_primera_vez_no_pide_la_anterior_y_persiste(qtbot, conn, monkeypatch):
    from app.gui.pantallas.configuracion import _DialogoContrasenaMaestra
    from app.negocio.seguridad import verificar_contrasena_maestra

    def _fake_exec(self):
        assert not hasattr(self, "campo_actual")  # todavía no hay ninguna, no debería pedirla
        self.campo_nueva.setText("maestra123")
        self.campo_confirmar.setText("maestra123")
        self._validar_y_aceptar()
        return self.result()

    monkeypatch.setattr(_DialogoContrasenaMaestra, "exec", _fake_exec)

    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    panel_seguridad = pantalla._paneles[[titulo for titulo, _ in _GRUPOS].index("Seguridad")]
    boton = next(w for w in panel_seguridad.orden if w.text() == "Establecer/cambiar contraseña maestra")
    boton.click()

    assert verificar_contrasena_maestra(conn, "maestra123") is True


def test_contrasena_maestra_ya_establecida_exige_la_anterior(qtbot, conn, monkeypatch):
    from app.gui.pantallas.configuracion import _DialogoContrasenaMaestra
    from app.negocio.seguridad import establecer_contrasena_maestra, verificar_contrasena_maestra

    establecer_contrasena_maestra(conn, "maestra123")

    def _fake_exec_incorrecta(self):
        assert hasattr(self, "campo_actual")
        self.campo_actual.setText("incorrecta")
        self.campo_nueva.setText("nueva456")
        self.campo_confirmar.setText("nueva456")
        self._validar_y_aceptar()
        return self.result()

    monkeypatch.setattr(_DialogoContrasenaMaestra, "exec", _fake_exec_incorrecta)
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    panel_seguridad = pantalla._paneles[[titulo for titulo, _ in _GRUPOS].index("Seguridad")]
    boton = next(w for w in panel_seguridad.orden if w.text() == "Establecer/cambiar contraseña maestra")
    boton.click()

    assert verificar_contrasena_maestra(conn, "maestra123") is True  # no cambió

    def _fake_exec_correcta(self):
        self.campo_actual.setText("maestra123")
        self.campo_nueva.setText("nueva456")
        self.campo_confirmar.setText("nueva456")
        self._validar_y_aceptar()
        return self.result()

    monkeypatch.setattr(_DialogoContrasenaMaestra, "exec", _fake_exec_correcta)
    boton.click()

    assert verificar_contrasena_maestra(conn, "nueva456") is True


def test_contrasena_maestra_cancelar_no_cambia_nada(qtbot, conn, monkeypatch):
    from app.gui.pantallas.configuracion import _DialogoContrasenaMaestra
    from app.negocio.seguridad import verificar_contrasena_maestra

    monkeypatch.setattr(_DialogoContrasenaMaestra, "exec", lambda self: QDialog.DialogCode.Rejected)

    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    panel_seguridad = pantalla._paneles[[titulo for titulo, _ in _GRUPOS].index("Seguridad")]
    boton = next(w for w in panel_seguridad.orden if w.text() == "Establecer/cambiar contraseña maestra")
    boton.click()

    assert verificar_contrasena_maestra(conn, "cualquiera") is False


def test_dialogo_contrasena_maestra_rechaza_vacia_y_no_coincidente(qtbot, conn):
    from app.gui.pantallas.configuracion import _DialogoContrasenaMaestra
    from app.negocio.seguridad import verificar_contrasena_maestra

    dialogo = _DialogoContrasenaMaestra(conn)
    qtbot.addWidget(dialogo)
    dialogo.campo_nueva.setText("")
    dialogo.campo_confirmar.setText("")
    dialogo._validar_y_aceptar()
    assert dialogo.result() != QDialog.DialogCode.Accepted

    dialogo.campo_nueva.setText("clave1")
    dialogo.campo_confirmar.setText("clave2")
    dialogo._validar_y_aceptar()
    assert dialogo.result() != QDialog.DialogCode.Accepted

    dialogo.campo_nueva.setText("clave1")
    dialogo.campo_confirmar.setText("clave1")
    dialogo._validar_y_aceptar()
    assert dialogo.result() == QDialog.DialogCode.Accepted
    assert verificar_contrasena_maestra(conn, "clave1") is True
