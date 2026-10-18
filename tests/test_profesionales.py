import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFileDialog, QLabel, QMessageBox, QPushButton, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.crud_generico import _DialogoRegistro
from app.gui.estilos import hoja_estilos
from app.gui.pantallas.profesionales import (
    _al_abrir_dialogo,
    _campos_profesional,
    _DialogoCategoriaDocumento,
    _PanelProfesionales,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    # Por defecto acepta el diálogo de "Agregar archivo" con la primera
    # categoría de la lista — los tests que necesiten otra la pisan.
    monkeypatch.setattr(_DialogoCategoriaDocumento, "exec", lambda self: QDialog.DialogCode.Accepted)


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_pantalla_profesionales_lista_existentes(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.commit()
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.crud_profesionales.tabla_widget.rowCount() == 1
    assert pantalla.crud_profesionales.tabla_widget.item(0, 3).text() == "Gómez"


def test_columna_codigo_ordena_natural_no_alfabetico(qtbot, conn):
    """Pedido explícito de la clienta: click en "Código" tiene que
    ordenar "R1, R2, R3... R10, R11" (número completo) en vez de
    "R1, R10, R11, R2..." (alfabético dígito a dígito)."""
    for codigo in ("R10", "R2", "R1"):
        conn.execute(
            "INSERT INTO Profesional (CategoriaProfesional, Apellido, IdCodigo) VALUES ('R', 'Lo Veci', ?)",
            (codigo,),
        )
    conn.commit()
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    tabla = pantalla.crud_profesionales.tabla_widget
    tabla.horizontalHeader().sectionClicked.emit(0)
    assert [tabla.item(fila, 0).text() for fila in range(3)] == ["R1", "R2", "R10"]


def test_pantalla_profesionales_muestra_etiqueta_de_categoria(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    conn.commit()
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.crud_profesionales.tabla_widget.item(0, 4).text() == "R - Regular"


def test_pantalla_profesionales_muestra_cabeza_de_equipo(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    id_cabeza = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, ProfesionalCabezaEquipo) VALUES ('E', 'Ruiz', ?)",
        (id_cabeza,),
    )
    conn.commit()
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    fila_equipo = next(
        i for i in range(pantalla.crud_profesionales.tabla_widget.rowCount()) if pantalla.crud_profesionales.tabla_widget.item(i, 3).text() == "Ruiz"
    )
    assert "Gómez" in pantalla.crud_profesionales.tabla_widget.item(fila_equipo, 21).text()


def test_campos_libres_apagados_los_saca_de_profesionales(qtbot, conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, VisualizarCamposLibres=0)
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.crud_profesionales.campos]
    assert "CampoLibre1" not in nombres


def test_condicion_fiscal_es_combo_editable_con_default_consumidor_final(qtbot, conn):
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.crud_profesionales.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    combo = dialogo._entradas["CondicionFiscal"]
    assert combo.isEditable() is True
    assert combo.itemText(0) == "Consumidor Final"
    combo.setEditText("Otra condición")
    assert dialogo.valores()["CondicionFiscal"] == "Otra condición"


def _nuevo_dialogo_con_hook(conn, qtbot):
    dialogo = _DialogoRegistro(conn, _campos_profesional(conn), "Nuevo registro")
    qtbot.addWidget(dialogo)
    _al_abrir_dialogo(dialogo)
    return dialogo


def test_nuevo_profesional_sugiere_codigo_de_la_categoria_por_defecto(qtbot, conn):
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    assert dialogo._entradas["IdCodigo"].text() == "R1"


def test_tratamiento_ofrece_los_ya_usados_aunque_la_profesion_no_tenga_desplegable(qtbot, conn):
    """Bug reportado por la clienta ("no despliega el menú de los
    tratamientos"): `opciones_tratamiento` solo devuelve algo para
    Fonoaudiología/Psicopedagogía — para el resto de las profesiones el
    desplegable quedaba vacío. Ahora siempre suma, además, cualquier
    Tratamiento ya usado en algún profesional del sistema."""
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, Tratamiento) VALUES ('R', 'Pérez', 'Dr.')")
    conn.commit()
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    combo = dialogo._entradas["Tratamiento"]
    opciones = [combo.itemText(i) for i in range(combo.count())]
    assert "Dr." in opciones


def test_cabeza_de_equipo_tiene_busqueda_habilitada_y_formato_canonico(qtbot, conn):
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido, IdCodigo) VALUES ('R', 'Gómez', 'R1')")
    conn.commit()
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    combo = dialogo._entradas["ProfesionalCabezaEquipo"]
    assert combo.isEditable() is True
    assert combo.completer() is not None
    assert combo.itemText(0) == "R1 - Gómez"


def test_sugerencia_de_codigo_se_actualiza_al_cambiar_categoria(qtbot, conn):
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    combo_categoria = dialogo._entradas["CategoriaProfesional"]
    combo_categoria.setCurrentIndex(combo_categoria.findData("X"))
    assert dialogo._entradas["IdCodigo"].text() == "X1"


def test_sugerencia_de_codigo_no_pisa_una_edicion_manual(qtbot, conn):
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    campo_codigo = dialogo._entradas["IdCodigo"]
    campo_codigo.setText("R99")

    combo_categoria = dialogo._entradas["CategoriaProfesional"]
    combo_categoria.setCurrentIndex(combo_categoria.findData("X"))

    assert campo_codigo.text() == "R99"


def test_nuevo_profesional_pre_completa_tratamiento(qtbot, conn):
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    combo_profesion = dialogo._entradas["IdProfesion"]
    id_psicologia = obtener_repositorio(conn, "Profesion").listar(Nombre="Psicología")[0]["IdProfesion"]
    combo_profesion.setCurrentIndex(combo_profesion.findData(id_psicologia))
    combo_sexo = dialogo._entradas["Sexo"]
    combo_sexo.setCurrentIndex(combo_sexo.findData("Masculino"))
    assert dialogo._entradas["Tratamiento"].currentText() == "Lic."


def test_tratamiento_ofrece_desplegable_para_fonoaudiologia(qtbot, conn):
    dialogo = _nuevo_dialogo_con_hook(conn, qtbot)
    combo_profesion = dialogo._entradas["IdProfesion"]
    id_fono = obtener_repositorio(conn, "Profesion").listar(Nombre="Fonoaudiología")[0]["IdProfesion"]
    combo_profesion.setCurrentIndex(combo_profesion.findData(id_fono))
    combo_sexo = dialogo._entradas["Sexo"]
    combo_sexo.setCurrentIndex(combo_sexo.findData("Femenino"))

    combo_tratamiento = dialogo._entradas["Tratamiento"]
    opciones = [combo_tratamiento.itemText(i) for i in range(combo_tratamiento.count())]
    assert opciones == ["Fga.", "Lic."]
    assert combo_tratamiento.currentText() == "Fga."


def test_editar_profesional_repuebla_desplegable_tratamiento_sin_perder_valor(qtbot, conn):
    id_fono = obtener_repositorio(conn, "Profesion").listar(Nombre="Fonoaudiología")[0]["IdProfesion"]
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Pérez", IdProfesion=id_fono, Sexo="Femenino", Tratamiento="Lic.",
    )
    registro = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    dialogo = _DialogoRegistro(conn, _campos_profesional(conn), "Editar registro", registro=registro)
    qtbot.addWidget(dialogo)
    _al_abrir_dialogo(dialogo)

    combo_tratamiento = dialogo._entradas["Tratamiento"]
    opciones = [combo_tratamiento.itemText(i) for i in range(combo_tratamiento.count())]
    assert opciones == ["Fga.", "Lic."]
    assert combo_tratamiento.currentText() == "Lic."


def test_editar_desde_pantalla_invoca_al_abrir_dialogo(qtbot, conn, monkeypatch):
    """El hook de Profesionales debe engancharse también al editar (no
    solo al crear), para repoblar el desplegable de Tratamiento."""
    id_fono = obtener_repositorio(conn, "Profesion").listar(Nombre="Fonoaudiología")[0]["IdProfesion"]
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Pérez", IdProfesion=id_fono, Sexo="Femenino", Tratamiento="Lic.",
    )
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)

    opciones_vistas = []

    def _exec_falso(self, *a, **k):
        opciones_vistas.extend(
            self._entradas["Tratamiento"].itemText(i) for i in range(self._entradas["Tratamiento"].count())
        )
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr("app.gui.crud_generico._DialogoRegistro.exec", _exec_falso)
    pantalla.crud_profesionales._editar()

    assert opciones_vistas == ["Fga.", "Lic."]


def test_cuit_se_normaliza_al_guardar(qtbot, conn):
    dialogo = _DialogoRegistro(conn, _campos_profesional(conn), "Nuevo registro")
    qtbot.addWidget(dialogo)
    dialogo._entradas["Apellido"].setText("Gómez")
    dialogo._entradas["CUIT"].setText("20-12345678-9")
    assert dialogo.valores()["CUIT"] == "20123456789"


def test_nombre_completo_se_puede_cargar_y_editar_a_mano(qtbot, conn):
    dialogo = _DialogoRegistro(conn, _campos_profesional(conn), "Nuevo registro")
    qtbot.addWidget(dialogo)
    dialogo._entradas["Apellido"].setText("Gómez")
    dialogo._entradas["NombreCompleto"].setText("Gómez, Juan Carlos")
    assert dialogo.valores()["NombreCompleto"] == "Gómez, Juan Carlos"

    id_prof = obtener_repositorio(conn, "Profesional").crear(**dialogo.valores())
    assert obtener_repositorio(conn, "Profesional").obtener(id_prof)["NombreCompleto"] == "Gómez, Juan Carlos"

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    dialogo_edicion = _DialogoRegistro(conn, pantalla.crud_profesionales.campos, "Editar registro", registro=obtener_repositorio(conn, "Profesional").obtener(id_prof))
    qtbot.addWidget(dialogo_edicion)
    dialogo_edicion._entradas["NombreCompleto"].setText("Gómez, Juan C.")
    assert dialogo_edicion.valores()["NombreCompleto"] == "Gómez, Juan C."


def test_cambiar_codigo_registra_historial_y_renombra_carpeta(qtbot, conn, tmp_path, monkeypatch):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3",
    )
    # Carpeta "{código} - {apellido}" (sin Tratamiento/NombrePila cargados
    # en este profesional de prueba) — ver `nombre_carpeta_profesional`.
    (tmp_path / "Profesionales" / "R3 - Ramos").mkdir(parents=True)
    (tmp_path / "Profesionales" / "R3 - Ramos" / "2026-08 - Liquidación Ramos.pdf").write_text("x")
    conn.commit()

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    fila = next(i for i in range(pantalla.crud_profesionales.tabla_widget.rowCount()) if pantalla.crud_profesionales.tabla_widget.item(i, 3).text() == "Ramos")
    pantalla.crud_profesionales.tabla_widget.selectRow(fila)

    def _dialogo_cambia_codigo(self, *a, **k):
        self._entradas["CategoriaProfesional"].setCurrentIndex(self._entradas["CategoriaProfesional"].findData("X"))
        self._entradas["IdCodigo"].setText("X34")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.gui.crud_generico._DialogoRegistro.exec", _dialogo_cambia_codigo)
    pantalla.crud_profesionales._editar()

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert profesional["CategoriaProfesional"] == "X"
    assert profesional["IdCodigo"] == "X34"

    historial = conn.execute("SELECT * FROM HistorialCodigo WHERE IdProfesional = ?", (id_prof,)).fetchone()
    assert historial["CodigoAnterior"] == "R3"
    assert historial["CodigoNuevo"] == "X34"

    # El diálogo de edición resuelve "Tratamiento" con el combo completo
    # (`_entradas["Tratamiento"]`, no tocado por este mock) — al guardar
    # vuelve a escribir su valor actual ("Coach", el que ya resolvía el
    # combo para este profesional sin tratamiento cargado antes), así que
    # la carpeta nueva lo incorpora aunque el mock no haya tocado ese
    # campo. La carpeta vieja ("R3 - Ramos") seguía sin Tratamiento porque
    # se armó a mano en el setup de este test, antes de pasar por ningún
    # diálogo real.
    assert (tmp_path / "Profesionales" / "X34 - Coach Ramos" / "2026-08 - Liquidación Ramos.pdf").exists()
    assert not (tmp_path / "Profesionales" / "R3 - Ramos").exists()


def test_seleccionar_profesional_muestra_su_documentacion(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    (tmp_path / "Profesionales" / "R3 - Ramos" / "Documentación").mkdir(parents=True)
    (tmp_path / "Profesionales" / "R3 - Ramos" / "Documentación" / "dni.pdf").write_text("x")
    conn.commit()

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)

    assert pantalla.lista_documentos.count() == 1
    assert pantalla.lista_documentos.item(0).text() == "dni.pdf"


def test_profesional_sin_codigo_no_muestra_documentacion(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Sin Codigo")
    conn.commit()

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)

    assert pantalla.lista_documentos.count() == 0


def test_agregar_documento_lo_copia_y_lo_lista(qtbot, conn, tmp_path, monkeypatch):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path / "base"),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    conn.commit()
    origen = tmp_path / "dni.pdf"
    origen.write_bytes(b"x")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(origen), "")))

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)

    pantalla._agregar_documento()

    assert pantalla.lista_documentos.count() == 1
    # El archivo se guarda con el nombre de la categoría elegida (la
    # primera de la lista, "DNI completo" — mockeada por defecto), no
    # con el nombre original.
    assert pantalla.lista_documentos.item(0).text() == "DNI completo.pdf"
    assert (tmp_path / "base" / "Profesionales" / "R3 - Ramos" / "Documentación" / "DNI completo.pdf").exists()


def test_eliminar_documento(qtbot, conn, tmp_path, monkeypatch):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path / "base"),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    conn.commit()
    origen = tmp_path / "dni.pdf"
    origen.write_bytes(b"x")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(origen), "")))

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)
    pantalla._agregar_documento()

    pantalla.lista_documentos.setCurrentRow(0)
    pantalla._eliminar_documento()

    assert pantalla.lista_documentos.count() == 0
    assert not (tmp_path / "base" / "Profesionales" / "R3 - Ramos" / "Documentación" / "DNI completo.pdf").exists()


def test_agregar_documento_elige_categoria_del_dialogo(qtbot, conn, tmp_path, monkeypatch):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path / "base"),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    conn.commit()
    origen = tmp_path / "titulo.pdf"
    origen.write_bytes(b"x")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(origen), "")))

    def _elegir_titulo(self):
        self.combo_categoria.setCurrentText("Título")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoCategoriaDocumento, "exec", _elegir_titulo)

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)
    pantalla._agregar_documento()

    assert pantalla.lista_documentos.item(0).text() == "Título.pdf"


def test_agregar_otras_imagenes_sin_detalle_no_agrega(qtbot, conn, tmp_path, monkeypatch):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path / "base"),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    conn.commit()
    origen = tmp_path / "otra.jpg"
    origen.write_bytes(b"x")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(origen), "")))

    def _elegir_otras_sin_detalle(self):
        self.combo_categoria.setCurrentText("Otras imágenes")
        self.campo_detalle.setText("")
        self._validar_y_aceptar()
        return self.result()

    monkeypatch.setattr(_DialogoCategoriaDocumento, "exec", _elegir_otras_sin_detalle)

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)
    pantalla._agregar_documento()

    assert pantalla.lista_documentos.count() == 0


def test_agregar_otras_imagenes_con_detalle_nombra_el_archivo(qtbot, conn, tmp_path, monkeypatch):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path / "base"),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    conn.commit()
    origen = tmp_path / "otra.jpg"
    origen.write_bytes(b"x")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(origen), "")))

    def _elegir_otras_con_detalle(self):
        self.combo_categoria.setCurrentText("Otras imágenes")
        self.campo_detalle.setText("Foto del consultorio alquilado")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoCategoriaDocumento, "exec", _elegir_otras_con_detalle)

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)
    pantalla._agregar_documento()

    assert pantalla.lista_documentos.item(0).text() == "Otras imágenes - Foto del consultorio alquilado.jpg"


def test_pantalla_profesionales_usa_formato_solapa(qtbot, conn):
    """Reordenamiento de formularios: `_PanelProfesionales` es ahora la
    solapa "Listado de profesionales" de "Profesionales" — el
    `PantallaCRUD` interno va en modo `anidado=True`, sin su propio
    título ni `QTabWidget` "Listado" (ver `PantallaProfesionales`,
    contenedor de afuera, para el `QTabWidget` real)."""
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.findChildren(QTabWidget) == []
    assert pantalla.crud_profesionales.anidado is True
    assert pantalla.crud_profesionales.objectName() == "panelSolapa"


def test_pantalla_profesionales_documentacion_va_bajo_los_botones_del_crud(qtbot, conn):
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    crud = pantalla.crud_profesionales
    assert crud.campo_buscar is not None
    assert crud.boton_nuevo.objectName() == "botonPrimario"
    assert crud.boton_editar.objectName() == "botonSecundario"
    # el panel de documentación queda dentro del mismo panel izquierdo del CRUD, no en un splitter aparte
    assert crud.panel_extra_izquierda is not None
    assert crud.panel_extra_izquierda.isAncestorOf(pantalla.lista_documentos)


def test_pantalla_profesionales_lista_documentos_alto_fijo_y_vista_previa_se_estira(qtbot, conn):
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1300, 700)
    pantalla.show()
    qtbot.wait(50)
    # `lista_documentos` queda a un alto fijo (~5 líneas), sin crecer con la
    # ventana — el alto de sobra se lo lleva "Vista previa" (cuadro nuevo),
    # que tiene que llegar al pie del panel, a la par de la tabla de la
    # derecha.
    assert pantalla.lista_documentos.height() == pantalla.lista_documentos.minimumHeight() == pantalla.lista_documentos.maximumHeight()
    assert pantalla.area_vista_previa.height() > 150


def test_pantalla_profesionales_botones_quedan_a_la_mitad_del_alto_default(qtbot, conn):
    """Pedido explícito de la clienta: los cinco botones de la columna
    (los tres del CRUD + "Agregar archivo"/"Eliminar archivo") bajan a
    la mitad del alto default de botonPrimario/botonSecundario, para
    ganar espacio vertical en el panel izquierdo."""
    referencia = QPushButton("Agregar archivo")
    referencia.setObjectName("botonPrimario")
    referencia.setStyleSheet(hoja_estilos(modo_oscuro=False))
    qtbot.addWidget(referencia)
    alto_default = referencia.sizeHint().height()

    pantalla = _PanelProfesionales(conn)
    pantalla.setStyleSheet(hoja_estilos(modo_oscuro=False))
    qtbot.addWidget(pantalla)
    botones = pantalla.findChildren(QPushButton)
    nombres = {"Agregar archivo", "Eliminar archivo", "Nuevo", "Editar", "Eliminar"}
    botones_relevantes = [b for b in botones if b.text() in nombres]
    assert len(botones_relevantes) == 5
    for boton in botones_relevantes:
        assert boton.sizeHint().height() == alto_default // 2


def test_pantalla_profesionales_titulo_documentacion_sin_seleccionado(qtbot, conn):
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    etiquetas = [e.text() for e in pantalla.findChildren(QLabel)]
    assert "Documentación del profesional" in etiquetas
    assert "Documentación del profesional seleccionado" not in etiquetas


def test_vista_previa_arranca_con_el_texto_de_ayuda_y_sin_seleccion_vuelve_a_el(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    (tmp_path / "Profesionales" / "R3 - Ramos" / "Documentación").mkdir(parents=True)
    (tmp_path / "Profesionales" / "R3 - Ramos" / "Documentación" / "notas.txt").write_text("x")
    conn.commit()

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.etiqueta_vista_previa.text() == "Seleccioná un archivo para verlo acá."

    pantalla.crud_profesionales.tabla_widget.selectRow(0)
    pantalla.lista_documentos.setCurrentRow(0)
    # ".txt" no está entre las extensiones que esta vista previa sabe
    # renderizar (solo PDF/JPG/PNG) — cae al mensaje de "sin vista".
    assert pantalla.etiqueta_vista_previa.text() == "No hay vista disponible."

    pantalla.lista_documentos.setCurrentItem(None)
    assert pantalla.etiqueta_vista_previa.text() == "Seleccioná un archivo para verlo acá."


def test_vista_previa_de_imagen_muestra_el_pixmap(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    carpeta = tmp_path / "Profesionales" / "R3 - Ramos" / "Documentación"
    carpeta.mkdir(parents=True)
    ruta_imagen = carpeta / "foto.png"
    QPixmap(20, 20).save(str(ruta_imagen))
    conn.commit()

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)
    pantalla.lista_documentos.setCurrentRow(0)

    assert pantalla.etiqueta_vista_previa.text() == ""
    assert not pantalla.etiqueta_vista_previa.pixmap().isNull()


def test_cambiar_de_profesional_actualiza_la_vista_previa(qtbot, conn, tmp_path):
    conn.execute("UPDATE Configuracion SET CarpetaBaseArchivos = ? WHERE IdConfiguracion = 1", (str(tmp_path),))
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci", IdCodigo="R4")
    carpeta = tmp_path / "Profesionales" / "R3 - Ramos" / "Documentación"
    carpeta.mkdir(parents=True)
    QPixmap(20, 20).save(str(carpeta / "foto.png"))
    conn.commit()

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    pantalla.crud_profesionales.tabla_widget.selectRow(0)
    pantalla.lista_documentos.setCurrentRow(0)
    assert not pantalla.etiqueta_vista_previa.pixmap().isNull()

    # Lo Veci (R4) no tiene ningún documento cargado — al seleccionarla,
    # la vista previa vuelve al mensaje default, sin dejar la imagen del
    # profesional anterior pegada en pantalla.
    pantalla.crud_profesionales.tabla_widget.selectRow(1)
    assert pantalla.lista_documentos.count() == 0
    assert pantalla.etiqueta_vista_previa.text() == "Seleccioná un archivo para verlo acá."


def test_pantalla_profesionales_buscar_dice_buscar_profesional(qtbot, conn):
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.crud_profesionales.etiqueta_buscar == "Buscar profesional"


def test_pantalla_profesionales_botones_de_documentacion_dicen_agregar_y_eliminar_archivo(qtbot, conn):
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    textos = [b.text() for b in pantalla.findChildren(QPushButton)]
    assert "Agregar archivo" in textos
    assert "Eliminar archivo" in textos


def test_pantalla_profesionales_tiene_linea_divisoria_arriba_de_documentacion(qtbot, conn):
    from PySide6.QtWidgets import QFrame

    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    lineas = [w for w in pantalla.crud_profesionales.panel_extra_izquierda.findChildren(QFrame)]
    assert any(w.frameShape() == QFrame.Shape.HLine for w in lineas)


def test_pantalla_profesionales_columnas_en_orden_codigo_tratamiento_nombre_apellido(qtbot, conn):
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    etiquetas = [c.etiqueta for c in pantalla.crud_profesionales.campos[:4]]
    assert etiquetas == ["Código", "Tratamiento", "Nombre", "Apellido"]


def test_categoria_queda_primero_en_el_dialogo_pero_la_tabla_no_cambia(qtbot, conn):
    """Pedido explícito de la clienta: Categoría al principio, arriba de
    Código, SOLO en el cuadro de diálogo — el listado sigue mostrando
    las columnas en el orden canónico de siempre."""
    pantalla = _PanelProfesionales(conn)
    qtbot.addWidget(pantalla)
    crud = pantalla.crud_profesionales
    assert crud.campos[0].nombre == "IdCodigo"  # tabla: sin cambios
    campos_dialogo = crud._campos_dialogo()
    assert campos_dialogo[0].nombre == "CategoriaProfesional"
    assert [c.nombre for c in campos_dialogo[1:]] == [c.nombre for c in crud.campos if c.nombre != "CategoriaProfesional"]


def test_dialogo_se_ensancha_para_que_entren_etiquetas_largas(qtbot, conn):
    dialogo = _DialogoRegistro(conn, _campos_profesional(conn), "Nuevo registro")
    qtbot.addWidget(dialogo)
    assert dialogo.width() > 480  # el campo de "Día del mes para plazo extendido..." no entraba en el ancho fijo viejo


def test_fecha_nacimiento_sin_cargar_no_guarda_hoy_por_defecto(qtbot, conn):
    """Bug real: un `QDateEdit` siempre tiene algún valor concreto — sin
    el sentinel "(sin fecha)", un alta nueva sin tocar el campo hubiera
    guardado la fecha de hoy como si fuera el nacimiento real."""
    dialogo = _DialogoRegistro(conn, _campos_profesional(conn), "Nuevo registro")
    qtbot.addWidget(dialogo)
    assert dialogo._entradas["FechaNacimiento"].text() == "(sin fecha)"
    dialogo._entradas["Apellido"].setText("Gómez")
    assert dialogo.valores()["FechaNacimiento"] is None


def test_fecha_nacimiento_formato_sin_dia_de_semana(qtbot, conn):
    dialogo = _DialogoRegistro(conn, _campos_profesional(conn), "Nuevo registro")
    qtbot.addWidget(dialogo)
    from PySide6.QtCore import QDate
    dialogo._entradas["FechaNacimiento"].setDate(QDate(1990, 5, 20))
    assert dialogo._entradas["FechaNacimiento"].text() == "20-05-1990"
    dialogo._entradas["Apellido"].setText("Gómez")
    assert dialogo.valores()["FechaNacimiento"] == "1990-05-20"


def test_fecha_nacimiento_ya_cargada_se_precarga_y_se_puede_guardar_igual(qtbot, conn):
    id_prof = conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, Apellido, FechaNacimiento) VALUES ('R', 'Gómez', '1990-05-20')"
    ).lastrowid
    conn.commit()
    registro = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    dialogo = _DialogoRegistro(conn, _campos_profesional(conn), "Editar registro", registro=registro)
    qtbot.addWidget(dialogo)
    assert dialogo._entradas["FechaNacimiento"].text() == "20-05-1990"
    assert dialogo.valores()["FechaNacimiento"] == "1990-05-20"
