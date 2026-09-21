import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QTabWidget, QWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.estilos import hoja_estilos
from app.gui.main_window import Seccion, VentanaPrincipal
from app.gui.pantallas.configuracion import (
    _CAMPOS_BOOLEANOS,
    _CAMPOS_NUMERICOS,
    _CAMPOS_TEXTO,
    _GRUPOS,
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
    assert pantalla._entradas["HoraInicioGrilla"].text() == "7.0"


def test_guardar_persiste_texto_y_numero(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["NombreEspacio"].setText("Espacio Nuevo")
    pantalla._entradas["ToleranciaDeudaDescuento"].setText("500")
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
    pantalla._entradas["CantidadDecimales"].setText("0")
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


def test_guardar_con_numero_invalido_no_persiste(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    valor_original = conn.execute(
        "SELECT ToleranciaDeudaDescuento FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()["ToleranciaDeudaDescuento"]

    pantalla._entradas["ToleranciaDeudaDescuento"].setText("no es un número")
    pantalla._guardar()

    fila = conn.execute("SELECT ToleranciaDeudaDescuento FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["ToleranciaDeudaDescuento"] == valor_original


def test_guardar_con_fecha_ficticia_invalida_no_persiste(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    valor_original = conn.execute(
        "SELECT FechaFicticia FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()["FechaFicticia"]

    pantalla._entradas["FechaFicticia"].setText("31-13-2026")
    pantalla._guardar()

    fila = conn.execute("SELECT FechaFicticia FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["FechaFicticia"] == valor_original


def test_guardar_con_fecha_ficticia_valida_persiste(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    pantalla._entradas["FechaFicticia"].setText("2026-09-15")
    pantalla._guardar()
    fila = conn.execute("SELECT FechaFicticia FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    assert fila["FechaFicticia"] == "2026-09-15"


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


def test_tiene_formato_solapa_con_las_cinco_pestanas(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert [solapas.tabText(i) for i in range(solapas.count())] == [titulo for titulo, _campos in _GRUPOS]
    assert len(pantalla.findChildren(QWidget, "panelSolapa")) == len(_GRUPOS)


def test_todos_los_campos_estan_agrupados_una_sola_vez(qtbot, conn):
    """Ningún campo se pierde ni queda duplicado al pasar del formulario
    plano a los cinco grupos temáticos."""
    todos = {nombre for nombre, _ in _CAMPOS_TEXTO + _CAMPOS_NUMERICOS + _CAMPOS_BOOLEANOS}
    agrupados: list[str] = [nombre for _titulo, campos in _GRUPOS for nombre in campos]
    assert sorted(agrupados) == sorted(todos)
    assert len(agrupados) == len(set(agrupados))


def test_cada_solapa_carga_todos_sus_campos(qtbot, conn):
    pantalla = ConfiguracionGeneral(conn)
    qtbot.addWidget(pantalla)
    for panel, (_titulo, nombres) in zip(pantalla._paneles, _GRUPOS):
        assert len(panel.orden) == len(nombres)
        for nombre, entrada in zip(nombres, panel.orden):
            assert pantalla._entradas[nombre] is entrada


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
