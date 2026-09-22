import pytest
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QMessageBox, QTabWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.pantallas.llaves import (
    PantallaLlaves,
    _DialogoAcceso,
    _DialogoAsignar,
    _DialogoDevolucion,
    _DialogoIngreso,
    _DialogoPerdida,
    _DialogoPerdidaStock,
    _DialogoTipo,
    _FILAS_VISIBLES_ACCESOS,
    _PADDING_COLUMNA,
)
from app.gui.widgets.selector_profesional import _ProxyBusquedaSinAcentos
from app.negocio.llaves import crear_llave, ingresar_copias
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


def _crear_tipo_con_copia(conn, tipo="Unidad", valor_deposito_actual=3000):
    id_llave = crear_llave(conn, tipo=tipo, valor_deposito_actual=valor_deposito_actual)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    conn.commit()
    return id_llave


def test_titulo_de_pantalla_es_jerarquia_1(qtbot, conn):
    """Preview de la jerarquía de títulos definida en Lista de espera,
    aplicada acá antes de la revisión uno por uno de esta pantalla."""
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    titulo = pantalla.findChild(QLabel, "tituloPantalla")
    assert titulo is not None
    assert titulo.text() == "LLAVES"


def test_solo_asignar_es_primario_resto_secundarios(qtbot, conn):
    """"Asignar copia a profesional" es la única acción más definitiva
    de la pantalla (jerarquía 1); el resto, incluido "Nuevo tipo de
    llave", pasa a botonSecundario — pedido explícito de la clienta al
    revisar esta pantalla."""
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_asignar.objectName() == "botonPrimario"
    for boton in (
        pantalla.boton_nuevo_tipo, pantalla.boton_editar_tipo, pantalla.boton_eliminar_tipo,
        pantalla.boton_agregar_acceso, pantalla.boton_eliminar_acceso,
        pantalla.boton_ingresar, pantalla.boton_devolver, pantalla.boton_perdida,
    ):
        assert boton.objectName() == "botonSecundario"


def test_columna_profesional_de_movimientos_tiene_ancho_minimo(qtbot, conn):
    _crear_tipo_con_copia(conn)
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)
    assert pantalla.tabla_movimientos.columnWidth(2) >= 180


def test_columnas_de_tipos_son_mas_anchas_que_antes(qtbot, conn):
    """Pedido explícito de la clienta: más ancho para las columnas de
    las dos primeras tablas (Tipos y Accesos)."""
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    anchos_anteriores = [200, 70, 120, 90, 95, 65]
    for columna, ancho_anterior in enumerate(anchos_anteriores):
        assert pantalla.tabla_tipos.columnWidth(columna) > ancho_anterior


def test_columnas_de_accesos_tienen_el_doble_del_ancho_con_padding(qtbot, conn, monkeypatch):
    """Pedido explícito de la clienta: el doble de ancho para todas las
    columnas de Accesos, sobre el ancho justo + el padding de siempre."""
    crear_llave(conn)
    _crear_edificio_con_unidad(conn)
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)
    monkeypatch.setattr(_DialogoAcceso, "exec", lambda self: QDialog.DialogCode.Accepted)
    pantalla._agregar_acceso()

    tabla = pantalla.tabla_accesos
    anchos_actuales = [tabla.columnWidth(c) for c in range(tabla.columnCount())]
    tabla.resizeColumnsToContents()
    anchos_justos = [tabla.columnWidth(c) for c in range(tabla.columnCount())]

    assert anchos_actuales == [(justo + _PADDING_COLUMNA) * 2 for justo in anchos_justos]


def test_columnas_de_deposito_cobrado_y_reintegrado_tienen_el_mismo_ancho(qtbot, conn):
    """Pedido de la clienta: mismo ancho para las dos, el necesario para
    ver completo el título más largo ("Depósito reintegrado")."""
    _crear_tipo_con_copia(conn)
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)
    ancho_cobrado = pantalla.tabla_movimientos.columnWidth(5)
    ancho_reintegrado = pantalla.tabla_movimientos.columnWidth(6)
    assert ancho_cobrado == ancho_reintegrado
    header = pantalla.tabla_movimientos.horizontalHeader()
    ancho_minimo_titulo = header.fontMetrics().horizontalAdvance("Depósito reintegrado")
    assert ancho_cobrado >= ancho_minimo_titulo


def test_combo_profesional_asignar_es_buscable_por_codigo_o_nombre(qtbot, conn):
    """Confirmado por la clienta: el selector de profesional buscable
    corre en todos los formularios del sistema, Llaves incluido."""
    id_llave = _crear_tipo_con_copia(conn)
    tipo = obtener_repositorio(conn, "Llave").obtener(id_llave)
    dialogo = _DialogoAsignar(conn, tipo, 1)
    qtbot.addWidget(dialogo)
    completador = dialogo.combo_profesional.completer()
    assert isinstance(completador.model(), _ProxyBusquedaSinAcentos)


def _crear_edificio_con_unidad(conn, nombre="Ramos 1", departamento="1ro A"):
    id_edificio = conn.execute("INSERT INTO Edificio (Nombre) VALUES (?)", (nombre,)).lastrowid
    id_unidad = conn.execute(
        "INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, ?)", (id_edificio, departamento)
    ).lastrowid
    conn.commit()
    return id_edificio, id_unidad


def test_tipo_combo_lee_valores_de_listas_editables(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoTipo(conn, pantalla)
    qtbot.addWidget(dialogo)
    textos = [dialogo.combo_tipo.itemText(i) for i in range(dialogo.combo_tipo.count())]
    assert textos == ["Unidad", "Edificio", "No especificada"]


def test_nuevo_tipo_arma_nombre_automatico(qtbot, conn, monkeypatch):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)

    def _crear_edificio(self, *a, **k):
        indice = self.combo_tipo.findData("Edificio")
        self.combo_tipo.setCurrentIndex(indice)
        self.spin_deposito.setValue(5000)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoTipo, "exec", _crear_edificio)
    pantalla._nuevo_tipo()

    assert pantalla.tabla_tipos.rowCount() == 1
    assert pantalla.tabla_tipos.item(0, 0).text() == "Tipo llave E1"
    assert pantalla.tabla_tipos.item(0, 1).text() == "Edificio"


def test_tipos_ordenados_alfabeticamente_por_defecto(qtbot, conn):
    crear_llave(conn, tipo="Unidad")
    crear_llave(conn, tipo="Edificio")
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)

    nombres = [pantalla.tabla_tipos.item(f, 0).text() for f in range(pantalla.tabla_tipos.rowCount())]
    assert nombres == sorted(nombres)


def test_seleccionar_tipo_muestra_asignadas_disponibles_y_total(qtbot, conn):
    id_llave = _crear_tipo_con_copia(conn)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)

    assert pantalla.tabla_tipos.item(0, 3).text() == "0"  # Asignadas
    assert pantalla.tabla_tipos.item(0, 4).text() == "2"  # Disponibles
    assert pantalla.tabla_tipos.item(0, 5).text() == "2"  # Total


def test_editar_tipo_bloquea_combo_y_no_cambia_nombre(qtbot, conn, monkeypatch):
    id_llave = _crear_tipo_con_copia(conn, tipo="Unidad")
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)

    def _editar(self, *a, **k):
        assert self.combo_tipo.isEnabled() is False
        self.spin_deposito.setValue(4000)
        self.campo_observacion.setText("nota")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoTipo, "exec", _editar)
    pantalla._editar_tipo()

    llave = obtener_repositorio(conn, "Llave").obtener(id_llave)
    assert llave["Nombre"] == "Tipo llave U1"
    assert llave["ValorDepositoActual"] == pytest.approx(4000)
    assert llave["Observacion"] == "nota"


def test_eliminar_tipo_sin_dependientes(qtbot, conn):
    crear_llave(conn)
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)
    pantalla._eliminar_tipo()
    assert pantalla.tabla_tipos.rowCount() == 0


def test_eliminar_tipo_con_copias_no_se_puede(qtbot, conn):
    _crear_tipo_con_copia(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)
    pantalla._eliminar_tipo()
    assert pantalla.tabla_tipos.rowCount() == 1


def test_observacion_tipo_se_guarda_al_perder_foco(qtbot, conn):
    id_llave = crear_llave(conn)
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)

    pantalla.campo_observacion_tipo.setText("una nota")
    pantalla.campo_observacion_tipo.editingFinished.emit()

    llave = obtener_repositorio(conn, "Llave").obtener(id_llave)
    assert llave["Observacion"] == "una nota"


def test_agregar_acceso_completa_localidad_desde_edificio(qtbot, conn, monkeypatch):
    crear_llave(conn)
    conn.execute("INSERT INTO Localidad (Localidad) VALUES ('CABA')")
    id_caba = conn.execute("SELECT IdLocalidad FROM Localidad WHERE Localidad = 'CABA'").fetchone()["IdLocalidad"]
    conn.execute("INSERT INTO Edificio (Nombre, IdLocalidad) VALUES ('Ramos 1', ?)", (id_caba,))
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)

    monkeypatch.setattr(_DialogoAcceso, "exec", lambda self: QDialog.DialogCode.Accepted)
    pantalla._agregar_acceso()

    assert pantalla.tabla_accesos.rowCount() == 1
    assert pantalla.tabla_accesos.item(0, 0).text() == "CABA"
    assert pantalla.tabla_accesos.item(0, 1).text() == "Ramos 1"
    assert pantalla.tabla_accesos.item(0, 2).text() == "Todas"


def test_eliminar_acceso(qtbot, conn, monkeypatch):
    crear_llave(conn)
    conn.commit()
    _crear_edificio_con_unidad(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)
    monkeypatch.setattr(_DialogoAcceso, "exec", lambda self: QDialog.DialogCode.Accepted)
    pantalla._agregar_acceso()
    assert pantalla.tabla_accesos.rowCount() == 1

    pantalla.tabla_accesos.selectRow(0)
    pantalla._eliminar_acceso()
    assert pantalla.tabla_accesos.rowCount() == 0


def test_ingresar_copia_actualiza_total_y_disponibles(qtbot, conn, monkeypatch):
    crear_llave(conn)
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)

    def _cargar_tres(self, *a, **k):
        self.spin_cantidad.setValue(3)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoIngreso, "exec", _cargar_tres)
    pantalla._ingresar_copia()

    assert pantalla.tabla_tipos.item(0, 4).text() == "3"
    assert pantalla.tabla_tipos.item(0, 5).text() == "3"


def test_asignar_sin_disponibles_avisa_y_no_hace_nada(qtbot, conn):
    crear_llave(conn)
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)
    pantalla._asignar()  # no debe lanzar excepción
    assert obtener_repositorio(conn, "LlaveMovimiento").listar() == []


def test_asignar_crea_movimiento_y_cargo_especial(qtbot, conn, monkeypatch):
    id_llave = _crear_tipo_con_copia(conn, valor_deposito_actual=3000)
    id_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Gómez")
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)

    def _asignar_con_deposito(self, *a, **k):
        indice = self.combo_profesional.findData(id_profesional)
        self.combo_profesional.setCurrentIndex(indice)
        self.casilla_deposito.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoAsignar, "exec", _asignar_con_deposito)
    pantalla._asignar()

    assert pantalla.tabla_tipos.item(0, 3).text() == "1"  # Asignadas
    assert pantalla.tabla_movimientos.rowCount() == 2  # el Ingreso original + esta Asignación
    cargo = conn.execute("SELECT * FROM CargoEspecial WHERE IdProfesional = ?", (id_profesional,)).fetchone()
    assert cargo is not None
    assert cargo["IdLlave"] == id_llave


def test_registrar_devolucion_deshabilitado_sin_asignacion_abierta(qtbot, conn):
    _crear_tipo_con_copia(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)
    assert pantalla.tabla_movimientos.rowCount() == 1  # el Ingreso, sin ninguna Asignación todavía
    assert pantalla.boton_devolver.isEnabled() is False
    pantalla._registrar_devolucion()  # nada seleccionado, no debe fallar


def test_perdida_habilitado_con_stock_disponible_sin_asignacion(qtbot, conn):
    """Con un Tipo seleccionado que tiene copias disponibles (pero
    ninguna asignación abierta), Registrar pérdida se habilita para dar
    de baja stock sin asignar — Registrar devolución no tiene sentido en
    ese caso y sigue deshabilitado."""
    _crear_tipo_con_copia(conn)
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)

    assert pantalla.boton_perdida.isEnabled() is True
    assert pantalla.boton_devolver.isEnabled() is False


def test_perdida_deshabilitado_sin_seleccion(qtbot, conn):
    crear_llave(conn)  # sin stock ingresado
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)
    assert pantalla.boton_perdida.isEnabled() is False
    pantalla._registrar_perdida()  # nada que hacer, no debe fallar


def test_registrar_perdida_de_stock_sin_asignar_via_boton(qtbot, conn, monkeypatch):
    id_llave = _crear_tipo_con_copia(conn)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)
    assert pantalla.tabla_tipos.item(0, 4).text() == "2"  # Disponibles

    def _perder_una(self, *a, **k):
        self.spin_cantidad.setValue(1)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoPerdidaStock, "exec", _perder_una)
    pantalla._registrar_perdida()

    assert pantalla.tabla_tipos.item(0, 4).text() == "1"  # Disponibles bajó
    assert pantalla.tabla_tipos.item(0, 3).text() == "0"  # Asignadas sin cambios
    assert obtener_repositorio(conn, "CargoEspecial").listar() == []


def test_flujo_completo_asignar_y_devolver(qtbot, conn, monkeypatch):
    _crear_tipo_con_copia(conn, valor_deposito_actual=3000)
    id_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Gómez")
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)

    def _asignar_con_deposito(self, *a, **k):
        indice = self.combo_profesional.findData(id_profesional)
        self.combo_profesional.setCurrentIndex(indice)
        self.casilla_deposito.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoAsignar, "exec", _asignar_con_deposito)
    pantalla._asignar()
    assert pantalla.tabla_tipos.item(0, 3).text() == "1"

    pantalla.tabla_movimientos.selectRow(0)
    assert pantalla.boton_devolver.isEnabled() is True
    assert pantalla.boton_perdida.isEnabled() is True

    monkeypatch.setattr(_DialogoDevolucion, "exec", lambda self: QDialog.DialogCode.Accepted)
    pantalla._registrar_devolucion()

    assert pantalla.tabla_tipos.item(0, 3).text() == "0"
    assert pantalla.tabla_tipos.item(0, 4).text() == "1"
    assert pantalla.tabla_movimientos.rowCount() == 3  # Ingreso + Asignación + Devolución


def test_flujo_perdida_no_reintegra(qtbot, conn, monkeypatch):
    _crear_tipo_con_copia(conn, valor_deposito_actual=3000)
    id_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Gómez")
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.tabla_tipos.selectRow(0)

    def _asignar_con_deposito(self, *a, **k):
        indice = self.combo_profesional.findData(id_profesional)
        self.combo_profesional.setCurrentIndex(indice)
        self.casilla_deposito.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DialogoAsignar, "exec", _asignar_con_deposito)
    pantalla._asignar()

    pantalla.tabla_movimientos.selectRow(0)
    monkeypatch.setattr(_DialogoPerdida, "exec", lambda self: QDialog.DialogCode.Accepted)
    pantalla._registrar_perdida()

    assert pantalla.tabla_tipos.item(0, 3).text() == "0"  # Asignadas
    assert pantalla.tabla_tipos.item(0, 4).text() == "0"  # Disponibles: no vuelve al stock
    assert pantalla.tabla_tipos.item(0, 5).text() == "0"  # Total baja
    cargos = conn.execute("SELECT * FROM CargoEspecial WHERE IdProfesional = ?", (id_profesional,)).fetchall()
    assert len(cargos) == 1
    assert cargos[0]["Tipo"] == "Débito"




# ---------------------------------------- formato solapa (revisión "uno por uno")


def test_tiene_formato_solapa_con_una_pestana_llaves(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    solapas = pantalla.findChild(QTabWidget)
    assert solapas is not None
    assert solapas.count() == 1
    assert solapas.tabText(0) == "Llaves"


def test_no_queda_boton_deshacer(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    assert not hasattr(pantalla, "boton_deshacer")


def test_etiquetas_de_los_botones(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.boton_nuevo_tipo.text() == "Nuevo tipo de llave"
    assert pantalla.boton_editar_tipo.text() == "Editar tipo de llave"
    assert pantalla.boton_eliminar_tipo.text() == "Eliminar tipo de llave"
    assert pantalla.boton_agregar_acceso.text() == "Agregar acceso de llave"
    assert pantalla.boton_eliminar_acceso.text() == "Eliminar acceso de llave"
    assert pantalla.boton_ingresar.text() == "Ingresar copia al stock"
    assert pantalla.boton_perdida.text() == "Registrar pérdida"
    assert pantalla.boton_devolver.text() == "Devolución copia del profesional"
    assert pantalla.boton_asignar.text() == "Asignar copia a profesional"


def test_orden_de_foco_sigue_el_orden_visual_de_los_botones(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    assert pantalla._foco._orden == [
        pantalla.campo_observacion_tipo, pantalla.boton_nuevo_tipo, pantalla.boton_editar_tipo,
        pantalla.boton_eliminar_tipo, pantalla.campo_observacion_acceso, pantalla.boton_agregar_acceso,
        pantalla.boton_eliminar_acceso, pantalla.campo_observacion_movimiento,
        pantalla.boton_ingresar, pantalla.boton_perdida, pantalla.boton_devolver, pantalla.boton_asignar,
    ]


def test_todos_los_botones_comparten_el_mismo_ancho_fijo(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    anchos = {
        pantalla.boton_nuevo_tipo.width(), pantalla.boton_editar_tipo.width(), pantalla.boton_eliminar_tipo.width(),
        pantalla.boton_agregar_acceso.width(), pantalla.boton_eliminar_acceso.width(),
        pantalla.boton_ingresar.width(), pantalla.boton_perdida.width(), pantalla.boton_devolver.width(),
        pantalla.boton_asignar.width(),
    }
    assert len(anchos) == 1


def test_tabla_tipos_y_accesos_tienen_alto_fijo_movimientos_no(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_tipos.maximumHeight() == pantalla.tabla_tipos.minimumHeight()
    assert pantalla.tabla_accesos.maximumHeight() == pantalla.tabla_accesos.minimumHeight()
    assert pantalla.tabla_movimientos.maximumHeight() > pantalla.tabla_movimientos.minimumHeight()


# ---------------------------------------- ronda 2: títulos normales, alineación, sin divisorias


def test_titulos_de_seccion_mismo_tamano_normal_pero_en_negrita(qtbot, conn):
    """Pedido explícito de la clienta: "Tipos de llaves"/"Accesos
    habilitados con la llave"/"Movimientos de llaves" no son solapas
    reales, van con el mismo tamaño que el texto normal (subtituloCampo,
    no subtituloSeccion) pero en negrita — a diferencia del resto de los
    `subtituloCampo` del sistema, que van sin negrita."""
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    textos = {"Tipos de llaves", "Accesos habilitados con la llave", "Movimientos de llaves"}
    etiquetas = [
        etiqueta for etiqueta in pantalla.findChildren(QLabel, "subtituloCampo")
        if etiqueta.text() in textos
    ]
    assert {e.text() for e in etiquetas} == textos
    assert pantalla.findChildren(QLabel, "subtituloSeccion") == []
    assert all(e.font().bold() for e in etiquetas)


def test_no_quedan_lineas_divisorias_entre_grupos_de_botones(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    lineas = [f for f in pantalla.findChildren(QFrame) if f.frameShape() == QFrame.Shape.HLine]
    assert lineas == []


def test_cada_grupo_de_botones_arranca_a_la_altura_del_primer_registro(qtbot, conn):
    """"Los botones que queden alineados al primer registro de cada
    tabla": el primer botón de cada grupo tiene que empezar (en Y) a la
    misma altura que el comienzo de la primera fila de datos de su
    tabla correspondiente (después del encabezado), no a la altura del
    título."""
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1300, 900)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    def _y_global(widget):
        return widget.mapToGlobal(widget.rect().topLeft()).y()

    def _y_primera_fila(tabla):
        header = tabla.horizontalHeader()
        return header.mapToGlobal(header.rect().bottomLeft()).y()

    assert abs(_y_global(pantalla.boton_nuevo_tipo) - _y_primera_fila(pantalla.tabla_tipos)) <= 2
    assert abs(_y_global(pantalla.boton_agregar_acceso) - _y_primera_fila(pantalla.tabla_accesos)) <= 2
    assert abs(_y_global(pantalla.boton_ingresar) - _y_primera_fila(pantalla.tabla_movimientos)) <= 2


def test_tabla_tipos_escrolea_internamente_con_mas_filas_de_las_que_entran(qtbot, conn):
    for _ in range(10):
        crear_llave(conn, tipo="Unidad")
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1300, 900)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    assert pantalla.tabla_tipos.rowCount() == 10
    assert pantalla.tabla_tipos.verticalScrollBar().maximum() > 0


def test_tabla_accesos_escrolea_internamente_con_mas_filas_de_las_que_entran(qtbot, conn):
    crear_llave(conn)
    id_edificio, _ = _crear_edificio_con_unidad(conn)
    for i in range(6):
        conn.execute(
            "INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, ?)", (id_edificio, f"Depto {i}")
        )
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1300, 900)
    pantalla.show()
    qtbot.waitExposed(pantalla)
    pantalla.tabla_tipos.selectRow(0)

    for id_unidad in [row["IdUnidad"] for row in conn.execute("SELECT IdUnidad FROM Unidad")]:
        obtener_repositorio(conn, "LlaveAcceso").crear(
            IdLlave=obtener_repositorio(conn, "Llave").listar()[0]["IdLlave"],
            IdEdificio=id_edificio, IdUnidad=id_unidad,
        )
    pantalla._actualizar_accesos()
    qtbot.wait(10)

    assert pantalla.tabla_accesos.rowCount() > _FILAS_VISIBLES_ACCESOS
    assert pantalla.tabla_accesos.verticalScrollBar().maximum() > 0


def test_tabla_movimientos_escrolea_internamente_con_mas_filas_de_las_que_entran(qtbot, conn):
    id_llave = crear_llave(conn)
    for _ in range(20):
        ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    conn.commit()
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla.resize(1300, 700)
    pantalla.show()
    qtbot.waitExposed(pantalla)

    assert pantalla.tabla_movimientos.rowCount() == 20
    assert pantalla.tabla_movimientos.verticalScrollBar().maximum() > 0
