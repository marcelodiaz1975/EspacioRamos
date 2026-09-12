import pytest
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QTabWidget

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


def test_tabla_arranca_con_todas_las_placas(qtbot, conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)

    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)

    assert pantalla.tabla.rowCount() == 1
    assert pantalla.tabla.item(0, 3).text() == "Lic. Virginia Lo Veci"


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
    assert pantalla.tabla.item(0, 0).text() == "Torre A"


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


def test_agregar_y_quitar_de_la_cola_de_impresion(qtbot, conn):
    id_profesional = _crear_profesional(conn)
    pantalla = PantallaPlacas(conn)
    qtbot.addWidget(pantalla)

    indice = pantalla.combo_profesional_imprimir.findData(id_profesional)
    pantalla.combo_profesional_imprimir.setCurrentIndex(indice)
    pantalla._agregar_a_impresion()
    assert pantalla.lista_impresion.count() == 1

    pantalla._agregar_a_impresion()  # no duplica
    assert pantalla.lista_impresion.count() == 1

    pantalla.lista_impresion.setCurrentRow(0)
    pantalla._quitar_de_impresion()
    assert pantalla.lista_impresion.count() == 0
    assert pantalla._cola_impresion == []


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
