import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QScrollArea, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.placas import PantallaPlacas, _DialogoPlaca
from app.negocio.placas import asignar_placa
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


def _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A", localidad=None, limite_placas=10):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre=nombre_edificio, DomicilioLocalidad=localidad)
    id_unidad = obtener_repositorio(conn, "Unidad").crear(
        IdEdificio=id_edificio, Departamento=departamento, CantLimitePlacas=limite_placas,
    )
    return id_edificio, id_unidad


def _crear_profesional(conn, apellido="Lo Veci", nombre_pila="Virginia", tratamiento="Lic.", codigo=None):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido=apellido, NombrePila=nombre_pila, Tratamiento=tratamiento, IdCodigo=codigo,
    )


def test_titulo_de_pantalla_es_jerarquia_1(qtbot, conn):
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "PLACAS"


def test_tiene_dos_solapas(qtbot, conn):
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas.count() == 2
    assert solapas.tabText(0) == "Buscar y asignar placas"
    assert solapas.tabText(1) == "Imprimir placas"


def test_columnas_de_la_tabla_arrancan_con_localidad(qtbot, conn):
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    encabezados = [pantalla.tabla.horizontalHeaderItem(i).text() for i in range(pantalla.tabla.columnCount())]
    assert encabezados == [
        "Localidad", "Edificio", "Unidad", "Posición", "Profesional", "Nombre grabado", "Personalizada",
    ]


def test_columnas_de_la_tabla_se_reparten_el_ancho_por_igual(qtbot, conn):
    """Pedido de la clienta: en vez de ajustar cada columna a su
    contenido, las 7 se reparten el ancho disponible por igual."""
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1400, 700)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    anchos = [pantalla.tabla.columnWidth(i) for i in range(pantalla.tabla.columnCount())]
    assert max(anchos) - min(anchos) <= 2  # redondeo de Qt al repartir


def test_posicion_queda_centrada(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    alineacion = pantalla.tabla.item(0, 3).textAlignment()
    assert alineacion & Qt.AlignmentFlag.AlignHCenter


def test_panel_de_filtros_queda_a_la_izquierda_de_la_tabla(qtbot, conn):
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1200, 700)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    assert pantalla.combo_profesional_filtro.x() < pantalla.tabla.x()
    assert pantalla.combo_profesional_filtro.parentWidget().width() >= 300


def test_botones_de_impresion_son_del_mismo_tamano_y_agregar_queda_centrado(qtbot, conn):
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1400, 700)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    pantalla.findChild(QTabWidget).setCurrentIndex(1)
    assert pantalla.boton_agregar_impresion.width() == pantalla.boton_quitar_impresion.width()
    assert pantalla.boton_agregar_impresion.width() == pantalla.boton_generar_pdf.width()

    centro_boton = pantalla.boton_agregar_impresion.x() + pantalla.boton_agregar_impresion.width() / 2
    mitad_izquierda = pantalla.lista_impresion.x() + pantalla.lista_impresion.width() / 2
    assert abs(centro_boton - mitad_izquierda) <= 2


def test_botones_quitar_y_generar_quedan_a_la_derecha(qtbot, conn):
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1400, 700)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    pantalla.findChild(QTabWidget).setCurrentIndex(1)
    fin_lista = pantalla.lista_impresion.x() + pantalla.lista_impresion.width()
    fin_generar = pantalla.boton_generar_pdf.x() + pantalla.boton_generar_pdf.width()
    assert abs(fin_generar - fin_lista) <= 2
    assert pantalla.boton_quitar_impresion.x() < pantalla.boton_generar_pdf.x()


def test_orden_por_defecto_es_localidad_edificio_unidad_posicion(qtbot, conn):
    _, id_unidad_z = _crear_unidad(conn, nombre_edificio="Z Torre", departamento="1A", localidad="Ramos Mejía")
    _, id_unidad_a = _crear_unidad(conn, nombre_edificio="A Torre", departamento="1A", localidad="Ramos Mejía")
    _, id_unidad_haedo = _crear_unidad(conn, nombre_edificio="Torre", departamento="1A", localidad="Haedo")
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad_z, posicion=1, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad_a, posicion=1, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad_haedo, posicion=1, id_profesional=id_profesional)

    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)

    localidades = [pantalla.tabla.item(f, 0).text() for f in range(pantalla.tabla.rowCount())]
    edificios = [pantalla.tabla.item(f, 1).text() for f in range(pantalla.tabla.rowCount())]
    assert localidades == ["Haedo", "Ramos Mejía", "Ramos Mejía"]
    assert edificios[1:] == ["A Torre", "Z Torre"]


def test_orden_por_defecto_desempata_por_posicion(qtbot, conn):
    """La última clave del orden por defecto es Posición, no Profesional
    (pedido de la clienta): dos placas en la misma localidad/edificio/
    unidad quedan ordenadas por su número de posición."""
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=3, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_profesional)

    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)

    posiciones = [pantalla.tabla.item(f, 3).text() for f in range(pantalla.tabla.rowCount())]
    assert posiciones == ["1", "2", "3"]


def test_click_en_encabezado_ordena_por_esa_columna(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_z = _crear_profesional(conn, apellido="Zeta")
    id_a = _crear_profesional(conn, apellido="Alfa")
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_z)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_a)

    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)

    pantalla.tabla.horizontalHeader().sectionClicked.emit(4)  # columna Profesional
    assert "Alfa" in pantalla.tabla.item(0, 4).text()

    pantalla.tabla.horizontalHeader().sectionClicked.emit(4)  # segundo click: invierte
    assert "Zeta" in pantalla.tabla.item(0, 4).text()


def test_reingresar_a_la_pantalla_resetea_filtros(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_1 = _crear_profesional(conn, apellido="Uno")
    id_2 = _crear_profesional(conn, apellido="Dos")
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_1)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_2)

    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_filtro.findData(id_1)
    pantalla.combo_profesional_filtro.setCurrentIndex(indice)
    assert pantalla.tabla.rowCount() == 1

    pantalla.show()
    qtbot.waitExposed(pantalla)

    assert pantalla.combo_profesional_filtro.currentIndex() == 0
    assert pantalla.tabla.rowCount() == 2


def test_tabla_arranca_con_todas_las_placas(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)

    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 4).text() == "Lic. Virginia Lo Veci"


def test_filtro_por_unidad_reduce_la_tabla(qtbot, conn):
    _, id_unidad_1 = _crear_unidad(conn, nombre_edificio="Torre A", departamento="1A")
    _, id_unidad_2 = _crear_unidad(conn, nombre_edificio="Torre B", departamento="1B")
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad_1, posicion=1, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad_2, posicion=1, id_profesional=id_profesional)

    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.rowCount() == 2

    pantalla.lista_unidad.clearSelection()
    for i in range(pantalla.lista_unidad.count()):
        if pantalla.lista_unidad.item(i).text() == "Torre A - 1A":
            pantalla.lista_unidad.item(i).setSelected(True)
            break

    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 1).text() == "Torre A"


def test_filtro_por_profesional_reduce_la_tabla(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_1 = _crear_profesional(conn, apellido="Uno")
    id_2 = _crear_profesional(conn, apellido="Dos")
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_1)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_2)

    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.rowCount() == 2

    indice = pantalla.combo_profesional_filtro.findData(id_1)
    pantalla.combo_profesional_filtro.setCurrentIndex(indice)

    assert pantalla.tabla.rowCount() == 1


def test_etiquetas_y_tamano_de_los_botones_de_buscar_y_asignar(qtbot, conn):
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_asignar_nueva.text() == "Asignar posición placa nueva"
    assert pantalla.boton_reasignar.text() == "Reasignar posición placa existente"
    assert pantalla.boton_liberar.text() == "Liberar posición"
    assert pantalla.boton_asignar_nueva.width() == pantalla.boton_reasignar.width()
    assert pantalla.boton_asignar_nueva.width() == pantalla.boton_liberar.width()


def test_columnas_unidad_y_personalizada_quedan_centradas(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla.item(0, 2).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    assert pantalla.tabla.item(0, 6).textAlignment() & Qt.AlignmentFlag.AlignHCenter


def test_botones_reasignar_y_liberar_arrancan_deshabilitados(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_reasignar.isEnabled() is False
    assert pantalla.boton_liberar.isEnabled() is False

    pantalla.tabla.selectRow(0)
    assert pantalla.boton_reasignar.isEnabled() is True
    assert pantalla.boton_liberar.isEnabled() is True


def test_asignar_placa_nueva_crea_registro(qtbot, conn, monkeypatch):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)

    def _aceptar(self, *a, **k):
        indice_unidad = self.combo_unidad.findData(id_unidad)
        self.combo_unidad.setCurrentIndex(indice_unidad)
        indice_profesional = self.combo_profesional.findData(id_profesional)
        self.combo_profesional.setCurrentIndex(indice_profesional)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoPlaca, "exec", _aceptar)
    pantalla._asignar_nueva()

    assert pantalla.tabla.rowCount() == 1
    assert obtener_repositorio(conn, "Placa").listar(IdUnidad=id_unidad)[0]["IdProfesional"] == id_profesional


def test_reasignar_pisa_el_mismo_registro(qtbot, conn, monkeypatch):
    _, id_unidad = _crear_unidad(conn)
    id_viejo = _crear_profesional(conn, apellido="Viejo")
    id_nuevo = _crear_profesional(conn, apellido="Nuevo")
    id_placa = asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_viejo)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)

    def _aceptar(self, *a, **k):
        indice = self.combo_profesional.findData(id_nuevo)
        self.combo_profesional.setCurrentIndex(indice)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoPlaca, "exec", _aceptar)
    pantalla._reasignar()

    assert pantalla.tabla.rowCount() == 1
    placa = obtener_repositorio(conn, "Placa").obtener(id_placa)
    assert placa["IdProfesional"] == id_nuevo


def test_liberar_posicion_borra_el_registro(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla.selectRow(0)

    pantalla._liberar()

    assert pantalla.tabla.rowCount() == 0
    assert obtener_repositorio(conn, "Placa").listar(IdUnidad=id_unidad) == []


def test_dialogo_nueva_ofrece_solo_posiciones_libres(qtbot, conn):
    _, id_unidad = _crear_unidad(conn, limite_placas=3)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_profesional)

    dialogo = _DialogoPlaca(conn)
    qtbot.addWidget(dialogo)
    indice = dialogo.combo_unidad.findData(id_unidad)
    dialogo.combo_unidad.setCurrentIndex(indice)

    posiciones = [dialogo.combo_posicion.itemData(i) for i in range(dialogo.combo_posicion.count())]
    assert posiciones == [1, 3]


def test_dialogo_reasignar_precarga_datos_existentes(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    id_placa = asignar_placa(
        conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional,
        es_personalizada=True, nombre_grabado_personalizado="Apodo",
    )
    placa = obtener_repositorio(conn, "Placa").obtener(id_placa)

    dialogo = _DialogoPlaca(conn, placa_existente=placa)
    qtbot.addWidget(dialogo)

    assert dialogo.combo_profesional.currentData() == id_profesional
    assert dialogo.casilla_personalizada.isChecked() is True
    assert dialogo.campo_nombre_personalizado.text() == "Apodo"
    valores = dialogo.valores()
    assert valores["id_unidad"] == id_unidad
    assert valores["posicion"] == 1


def test_previa_fuente_se_achica_si_el_texto_no_entra_a_tamano_maximo(qtbot):
    """Mismo criterio que el PDF: la placa tiene tamaño físico fijo, así
    que ante texto largo se achica la fuente en vez de partir una línea
    en dos o recortarla contra el borde."""
    from app.gui.pantallas.placas import _PREVIA_FUENTE_MAXIMA_PX, _PREVIA_FUENTE_MINIMA_PX, _tamano_fuente_previa

    corta = _tamano_fuente_previa(["Lic. Lucía Franco"])
    larga = _tamano_fuente_previa(
        ["Lic. Silvina Pugliese", 'Equipo "Sol terapias" con un texto bien largo para forzar el ajuste']
    )
    assert corta == _PREVIA_FUENTE_MAXIMA_PX
    assert larga < _PREVIA_FUENTE_MAXIMA_PX
    assert larga >= _PREVIA_FUENTE_MINIMA_PX


def test_vista_previa_es_proporcional_a_la_placa_real():
    """Pedido de la clienta: la vista previa tiene que ser proporcional a
    lo que se va a imprimir — se calcula desde las mismas constantes que
    usa el PDF (app.pdf.placas_pdf), no valores propios duplicados."""
    from app.gui.pantallas.placas import _PREVIA_ALTO_PX, _PREVIA_ANCHO_PX
    from app.pdf.placas_pdf import ALTO_PLACA, ANCHO_PLACA

    proporcion_pdf = ANCHO_PLACA / ALTO_PLACA
    proporcion_previa = _PREVIA_ANCHO_PX / _PREVIA_ALTO_PX
    assert proporcion_previa == pytest.approx(proporcion_pdf, rel=0.02)


def test_vista_previa_pagina_es_proporcional_a_una_hoja_a4():
    """La "hoja" de la vista previa tiene que tener las proporciones
    reales de una A4, para simular de verdad la hoja que se imprime."""
    from reportlab.lib.pagesizes import A4

    from app.gui.pantallas.placas import _PAGINA_ALTO_PX, _PAGINA_ANCHO_PX

    proporcion_a4 = A4[0] / A4[1]
    proporcion_previa = _PAGINA_ANCHO_PX / _PAGINA_ALTO_PX
    assert proporcion_previa == pytest.approx(proporcion_a4, rel=0.02)


def test_vista_previa_arma_una_pagina_por_cada_22_placas(qtbot, conn):
    from app.gui.pantallas.placas import _PLACAS_POR_PAGINA

    assert _PLACAS_POR_PAGINA == 22
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)
    for _ in range(25):
        pantalla._agregar_a_impresion()

    # QLabel también hereda de QFrame en Qt, así que se cuentan los hijos
    # directos del layout de páginas en vez de findChildren(QFrame).
    assert pantalla.area_previa.widget().layout().count() == 2


def test_vista_previa_es_escroleable(qtbot, conn):
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    assert isinstance(pantalla.area_previa, QScrollArea)
    assert pantalla.area_previa.widgetResizable() is True


def test_vista_previa_queda_a_la_derecha_de_la_busqueda(qtbot, conn):
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1400, 700)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    pantalla.findChild(QTabWidget).setCurrentIndex(1)
    assert pantalla.lista_impresion.x() < pantalla.area_previa.x()


def test_agregar_y_quitar_de_la_cola_de_impresion(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)

    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)
    pantalla._agregar_a_impresion()
    assert pantalla.lista_impresion.count() == 1

    # A diferencia de v1, permite agregar el mismo profesional más de una
    # vez (ej. dos copias, o una estándar y otra personalizada más tarde).
    pantalla._agregar_a_impresion()
    assert pantalla.lista_impresion.count() == 2

    pantalla.lista_impresion.setCurrentRow(0)
    pantalla._quitar_de_impresion()
    assert pantalla.lista_impresion.count() == 1
    assert len(pantalla._cola_impresion) == 1

    pantalla.lista_impresion.setCurrentRow(0)
    pantalla._quitar_de_impresion()
    assert pantalla.lista_impresion.count() == 0
    assert pantalla._cola_impresion == []


def test_personalizar_impresion_requiere_linea1(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)
    pantalla.casilla_personalizar_impresion.setChecked(True)

    pantalla._agregar_a_impresion()

    assert pantalla.lista_impresion.count() == 0


def test_personalizar_impresion_guarda_las_dos_lineas(qtbot, conn):
    id_profesional = _crear_profesional(conn, apellido="Pugliese", nombre_pila="Silvina")
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)
    pantalla.casilla_personalizar_impresion.setChecked(True)
    pantalla.campo_linea1_impresion.setText("Lic. Silvina Pugliese")
    pantalla.campo_linea2_impresion.setText('Equipo "Sol terapias"')

    pantalla._agregar_a_impresion()

    assert pantalla.lista_impresion.count() == 1
    assert "(personalizada)" in pantalla.lista_impresion.item(0).text()
    entrada = pantalla._cola_impresion[0]
    assert entrada["linea1"] == "Lic. Silvina Pugliese"
    assert entrada["linea2"] == 'Equipo "Sol terapias"'
    # se limpian los campos y se destilda el check después de agregar
    assert pantalla.casilla_personalizar_impresion.isChecked() is False
    assert pantalla.campo_linea1_impresion.text() == ""


def test_generar_pdf_sin_carpeta_base_no_falla(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)
    pantalla._agregar_a_impresion()

    pantalla._generar_pdf_impresion()  # solo debe avisar, no lanzar


def test_generar_pdf_genera_archivo_y_vacia_la_cola(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    conn.commit()
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)
    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)
    pantalla._agregar_a_impresion()

    pantalla._generar_pdf_impresion()

    generados = list((tmp_path / "Archivos varios" / "Placas").iterdir())
    assert len(generados) == 1
    assert generados[0].name.startswith("Placas para imprimir")
    assert pantalla.lista_impresion.count() == 0
    assert pantalla._cola_impresion == []
