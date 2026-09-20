import pytest
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QTabWidget, QWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.main_window import Seccion
from app.gui.pantallas.archivos_varios import PantallaArchivosVarios, _SIN_SELECCION
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


def test_titulo_de_pantalla_es_jerarquia_1(qtbot, conn):
    """Preview de la jerarquía de títulos definida en Lista de espera."""
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "ARCHIVOS VARIOS"


def test_hay_cuatro_botones_y_regenerar_es_el_principal(qtbot, conn):
    """Elegir un documento (los primeros tres) solo cambia la vista
    previa, ninguno más "definitivo" que el otro; "Regenerar documento"
    es la única acción que escribe algo, así que es la principal."""
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    botones = pantalla.findChildren(QPushButton)
    assert len(botones) == 4
    assert pantalla.boton_propuesta.objectName() == "botonSecundario"
    assert pantalla.boton_disponibilidad.objectName() == "botonSecundario"
    assert pantalla.boton_manual.objectName() == "botonSecundario"
    assert pantalla.boton_regenerar.objectName() == "botonPrimario"


def test_textos_de_los_botones(qtbot, conn):
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    textos = [b.text() for b in pantalla.findChildren(QPushButton)]
    assert textos == ["Propuesta", "Disponibilidad", "Manual del usuario", "Regenerar documento"]


def test_tiene_formato_solapa(qtbot, conn):
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert solapas.tabText(0) == "Documentos"
    assert pantalla.findChild(QWidget, "panelSolapa") is not None


def test_botones_comparten_el_mismo_ancho_fijo(qtbot, conn):
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    anchos = {
        b.width() for b in
        (pantalla.boton_propuesta, pantalla.boton_disponibilidad, pantalla.boton_manual, pantalla.boton_regenerar)
    }
    assert len(anchos) == 1


def test_foco_inicial_queda_en_boton_propuesta(qtbot, conn):
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    qtbot.waitUntil(lambda: pantalla.boton_propuesta.hasFocus())


def test_cadena_de_foco_baja_de_arriba_a_abajo_y_da_la_vuelta(qtbot, conn):
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    assert pantalla._foco._orden == [
        pantalla.boton_propuesta, pantalla.boton_disponibilidad, pantalla.boton_manual, pantalla.boton_regenerar,
    ]
    pantalla.show()
    qtbot.waitExposed(pantalla)
    pantalla.boton_regenerar.setFocus()
    qtbot.waitUntil(lambda: pantalla.boton_regenerar.hasFocus())
    pantalla._foco._mover(pantalla.boton_regenerar, retroceder=False, seleccionar_todo=False)
    qtbot.waitUntil(lambda: pantalla.boton_propuesta.hasFocus())


def test_elegir_documento_sin_archivos_muestra_aviso_y_no_genera_nada(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)

    pantalla._seleccionar("propuesta")

    carpeta = tmp_path / "Archivos varios" / "Propuesta"
    assert not carpeta.exists() or list(carpeta.iterdir()) == []
    assert "Regenerar documento" in pantalla.etiqueta_preview.text()


def test_regenerar_sin_elegir_documento_avisa_y_no_genera_nada(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)

    pantalla._regenerar_seleccionado()  # no debe lanzar, solo avisar

    assert not (tmp_path / "Archivos varios").exists()


def test_regenerar_propuesta_genera_archivo_y_actualiza_la_vista_previa(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)

    pantalla._seleccionar("propuesta")
    pantalla._regenerar_seleccionado()

    generados = list((tmp_path / "Archivos varios" / "Propuesta").iterdir())
    assert len(generados) == 1
    assert generados[0].name.startswith("Propuesta Espacio Ramos Consultorios")
    assert pantalla.etiqueta_preview.text() != _SIN_SELECCION


def test_regenerar_disponibilidad_genera_archivo(qtbot, conn, tmp_path):
    obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)

    pantalla._seleccionar("disponibilidad")
    pantalla._regenerar_seleccionado()

    generados = list((tmp_path / "Archivos varios" / "Disponibilidad").iterdir())
    assert len(generados) == 1
    assert generados[0].name.startswith("Disponibilidad Espacio Ramos Consultorios")


def test_regenerar_manual_sin_secciones_avisa_y_no_falla(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)

    pantalla._seleccionar("manual")
    pantalla._regenerar_seleccionado()  # no debe lanzar, solo avisar

    carpeta = tmp_path / "Archivos varios" / "Manual"
    assert not carpeta.exists() or list(carpeta.iterdir()) == []


def test_regenerar_manual_genera_archivo(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    secciones = [Seccion("Alguna pantalla", lambda c: None, categoria="Principal", ayuda="Texto de ayuda.")]
    pantalla = PantallaArchivosVarios(conn, secciones)
    qtbot.addWidget(pantalla)

    pantalla._seleccionar("manual")
    pantalla._regenerar_seleccionado()

    generados = list((tmp_path / "Archivos varios" / "Manual").iterdir())
    assert len(generados) == 1
    assert generados[0].name == "Manual de usuario.pdf"


def test_seleccionar_despues_de_regenerar_muestra_el_archivo_ya_generado(qtbot, conn, tmp_path):
    """`_seleccionar` no genera nada, pero sí tiene que encontrar y
    previsualizar un archivo que ya se había generado en una vuelta
    anterior (no solo el resultado recién salido de regenerar)."""
    obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    pantalla._seleccionar("propuesta")
    pantalla._regenerar_seleccionado()
    texto_recien_generado = pantalla.etiqueta_preview.text()

    pantalla._seleccionar("disponibilidad")  # cambia de documento
    pantalla._seleccionar("propuesta")  # vuelve al que ya tenía un archivo

    assert pantalla.etiqueta_preview.text() == texto_recien_generado


def test_preview_muestra_texto_de_ayuda_antes_de_elegir_nada(qtbot, conn):
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.etiqueta_preview.text() == _SIN_SELECCION
    assert pantalla.etiqueta_preview.pixmap().isNull()


def test_regenerar_sin_archivos_generados_no_rompe_la_vista_previa(qtbot, conn, monkeypatch, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    pantalla = PantallaArchivosVarios(conn)
    qtbot.addWidget(pantalla)
    pantalla._seleccionar("propuesta")
    monkeypatch.setattr(
        "app.gui.pantallas.archivos_varios.generar_pdfs_propuesta_por_localidad", lambda conn, directorio: [],
    )
    pantalla._regenerar_seleccionado()
    assert pantalla.etiqueta_preview.text() == "No se generó ningún archivo para previsualizar."
