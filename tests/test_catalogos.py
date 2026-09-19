import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.crud_generico import _DialogoRegistro
from app.gui.pantallas import catalogos
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


_FABRICAS = [
    catalogos.pantalla_localidades,
    catalogos.pantalla_edificios,
    catalogos.pantalla_unidades,
    catalogos.pantalla_consultorios,
    catalogos.pantalla_responsables,
    catalogos.pantalla_tipos_licencia,
    catalogos.pantalla_listas_editables,
    catalogos.pantalla_condiciones_normas,
    catalogos.pantalla_detalles_complementarios_propuesta,
    catalogos.pantalla_profesiones,
    catalogos.pantalla_gastos_operativos,
    catalogos.pantalla_placas,
    catalogos.pantalla_fechas_especiales,
]


@pytest.mark.parametrize("fabrica", _FABRICAS)
def test_pantalla_catalogo_se_arma_sin_error(qtbot, conn, fabrica):
    pantalla = fabrica(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.rowCount() == len(pantalla.repositorio.listar())


def test_pantalla_unidades_muestra_nombre_de_edificio(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    conn.commit()

    pantalla = catalogos.pantalla_unidades(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.item(0, 0).text() == "Torre Norte"
    assert pantalla.tabla_widget.item(0, 1).text() == "1A"


def test_pantalla_unidades_banos_es_cantidad_no_booleano(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento, Banos) VALUES (?, '1A', 2)", (id_edificio,))
    conn.commit()

    pantalla = catalogos.pantalla_unidades(conn)
    qtbot.addWidget(pantalla)
    columna_banos = next(i for i, c in enumerate(pantalla.campos) if c.nombre == "Banos")
    assert pantalla.campos[columna_banos].tipo == "numero"
    assert pantalla.tabla_widget.item(0, columna_banos).text() == "2"


def test_pantalla_unidades_tiene_tres_campos_libres(qtbot, conn):
    pantalla = catalogos.pantalla_unidades(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_pantalla_localidades_tiene_tres_campos_libres(qtbot, conn):
    pantalla = catalogos.pantalla_localidades(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_pantalla_localidades_localidad_es_requerida(qtbot, conn):
    pantalla = catalogos.pantalla_localidades(conn)
    qtbot.addWidget(pantalla)
    campo = next(c for c in pantalla.campos if c.nombre == "Localidad")
    assert campo.requerido is True


def test_pantalla_edificios_usa_combo_de_localidad(qtbot, conn):
    conn.execute(
        "INSERT INTO Localidad (Localidad, Partido, Provincia, Pais) VALUES (?, ?, ?, ?)",
        ("Ramos Mejía", "La Matanza", "Buenos Aires", "Argentina"),
    )
    conn.commit()
    pantalla = catalogos.pantalla_edificios(conn)
    qtbot.addWidget(pantalla)
    campo = next(c for c in pantalla.campos if c.nombre == "IdLocalidad")
    assert campo.tipo == "combo"
    assert "Ramos Mejía" in dict(campo.opciones(conn)).values()


def test_pantalla_edificios_tiene_tres_campos_libres(qtbot, conn):
    pantalla = catalogos.pantalla_edificios(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_pantalla_edificios_campo_libre_se_guarda_y_se_ve_en_la_tabla(qtbot, conn):
    pantalla = catalogos.pantalla_edificios(conn)
    qtbot.addWidget(pantalla)

    def _dialogo_con_nombre_y_campo_libre(self, *a, **k):
        self._entradas["Nombre"].setText("Torre Norte")
        self._entradas["CampoLibre1"].setText("Dato extra")
        return QDialog.DialogCode.Accepted

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("app.gui.crud_generico._DialogoRegistro.exec", _dialogo_con_nombre_y_campo_libre)
    pantalla._nuevo()
    monkeypatch.undo()

    columna_campo_libre = next(i for i, c in enumerate(pantalla.campos) if c.nombre == "CampoLibre1")
    assert pantalla.tabla_widget.item(0, columna_campo_libre).text() == "Dato extra"


def test_pantalla_consultorios_muestra_edificio_y_unidad(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 3)", (id_unidad,))
    conn.commit()

    pantalla = catalogos.pantalla_consultorios(conn)
    qtbot.addWidget(pantalla)
    assert "Torre Norte" in pantalla.tabla_widget.item(0, 0).text()
    assert pantalla.tabla_widget.item(0, 1).text() == "3"


def test_pantalla_consultorios_numero_no_numerico_no_persiste(qtbot, conn, monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    conn.commit()

    pantalla = catalogos.pantalla_consultorios(conn)
    qtbot.addWidget(pantalla)

    dialogo = _DialogoRegistro(conn, pantalla.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    dialogo._entradas["IdUnidad"].setCurrentIndex(0)
    dialogo._entradas["NumeroConsultorio"].setText("uno")
    dialogo._validar_y_aceptar()

    assert dialogo.result() != QDialog.DialogCode.Accepted
    assert conn.execute("SELECT COUNT(*) c FROM Consultorio").fetchone()["c"] == 0


def test_pantalla_consultorios_tiene_tres_campos_libres(qtbot, conn):
    pantalla = catalogos.pantalla_consultorios(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_pantalla_placas_muestra_unidad_y_profesional(qtbot, conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Profesional (CategoriaProfesional, Apellido) VALUES ('R', 'Gómez')")
    id_profesional = conn.execute("SELECT IdProfesional FROM Profesional").fetchone()["IdProfesional"]
    conn.execute(
        "INSERT INTO Placa (IdUnidad, IdProfesional, NombreGrabado) VALUES (?, ?, 'Dr. Gómez')",
        (id_unidad, id_profesional),
    )
    conn.commit()

    pantalla = catalogos.pantalla_placas(conn)
    qtbot.addWidget(pantalla)
    assert "1A" in pantalla.tabla_widget.item(0, 0).text()
    assert "Gómez" in pantalla.tabla_widget.item(0, 2).text()


def test_pantalla_gastos_operativos_muestra_alcance(qtbot, conn):
    conn.execute(
        "INSERT INTO GastoOperativo (Periodo, Concepto, Monto, Alcance) VALUES ('2026-08', 'Limpieza', 5000, 'Espacio general')"
    )
    conn.commit()
    pantalla = catalogos.pantalla_gastos_operativos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.tabla_widget.item(0, 4).text() == "Espacio general"


def test_fechas_especiales_tipo_es_combo_cerrado(qtbot, conn):
    """Sección 3.17 + 8.2: el Tipo tiene que salir de ListasEditables, no
    ser texto libre — feriados.py compara por string exacto, un typo acá
    rompe en silencio el descuento del 100% (hallazgo de la auditoría)."""
    pantalla = catalogos.pantalla_fechas_especiales(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    combo_tipo = dialogo._entradas["Tipo"]
    assert combo_tipo.isEditable() is False
    textos = [combo_tipo.itemText(i) for i in range(combo_tipo.count())]
    assert "Feriado nacional" in textos
    assert textos[0] == "Feriado nacional"


def test_consultorios_tamano_es_combo_cerrado_con_los_tres_predefinidos(qtbot, conn):
    """Antes era texto libre: el filtro de tamaño de Oferta de
    consultorios compara por igualdad exacta, un valor fuera de catálogo
    ahí (ej. "Pequeño" en vez de "Chico") rompe la coincidencia en
    silencio, mismo motivo que Tipo de fecha especial."""
    pantalla = catalogos.pantalla_consultorios(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    combo_tamano = dialogo._entradas["TamanoClasificacion"]
    assert combo_tamano.isEditable() is False
    textos = [combo_tamano.itemText(i) for i in range(combo_tamano.count())]
    assert textos == ["Sin clasificar", "Grande", "Intermedio", "Chico"]

    combo_tamano.setCurrentIndex(combo_tamano.findData("Grande"))
    assert dialogo.valores()["TamanoClasificacion"] == "Grande"


def test_listas_editables_tipo_lista_es_combo_cerrado_a_los_existentes(qtbot, conn):
    """No se pueden inventar tipos de lista nuevos acá — solo sumar
    valores a un tipo ya usado por algún combo del sistema (pedido de la
    clienta al revisar este catálogo)."""
    pantalla = catalogos.pantalla_listas_editables(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    combo_tipo = dialogo._entradas["TipoLista"]
    assert combo_tipo.isEditable() is False
    tipos = {combo_tipo.itemText(i) for i in range(combo_tipo.count())}
    assert "CondicionFiscal" in tipos
    assert "MedioPago" in tipos


def test_campos_libres_apagados_los_saca_de_todos_los_catalogos(qtbot, conn):
    """Un solo parámetro (Configuracion.VisualizarCamposLibres) controla
    los tres campos libres en todos los catálogos a la vez, porque todos
    arman su lista de Campo con `crud_generico.campos_libres(conn)`."""
    obtener_repositorio(conn, "Configuracion").actualizar(1, VisualizarCamposLibres=0)
    for fabrica in [
        catalogos.pantalla_localidades, catalogos.pantalla_edificios, catalogos.pantalla_unidades,
        catalogos.pantalla_consultorios, catalogos.pantalla_responsables, catalogos.pantalla_tipos_licencia,
        catalogos.pantalla_condiciones_normas, catalogos.pantalla_detalles_complementarios_propuesta,
        catalogos.pantalla_profesiones, catalogos.pantalla_gastos_operativos,
    ]:
        pantalla = fabrica(conn)
        qtbot.addWidget(pantalla)
        nombres = [c.nombre for c in pantalla.campos]
        assert "CampoLibre1" not in nombres
        assert "CampoLibre2" not in nombres
        assert "CampoLibre3" not in nombres


def test_pantalla_condiciones_normas_tiene_tres_campos_libres(qtbot, conn):
    pantalla = catalogos.pantalla_condiciones_normas(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_pantalla_detalles_complementarios_tiene_tres_campos_libres(qtbot, conn):
    pantalla = catalogos.pantalla_detalles_complementarios_propuesta(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_pantalla_profesiones_tiene_tres_campos_libres(qtbot, conn):
    pantalla = catalogos.pantalla_profesiones(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_pantalla_gastos_operativos_tiene_tres_campos_libres(qtbot, conn):
    pantalla = catalogos.pantalla_gastos_operativos(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_gasto_categoria_es_combo_editable_con_valores_de_listas_editables(qtbot, conn):
    obtener_repositorio(conn, "ListasEditables").crear(TipoLista="CategoriaGasto", Valor="Servicios", Orden=0)
    pantalla = catalogos.pantalla_gastos_operativos(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    combo_categoria = dialogo._entradas["Categoria"]
    assert combo_categoria.isEditable() is True
    opciones = [combo_categoria.itemText(i) for i in range(combo_categoria.count())]
    assert opciones == ["Servicios"]
    combo_categoria.setEditText("Categoría inventada")
    assert dialogo.valores()["Categoria"] == "Categoría inventada"


def test_gasto_alcance_edificio_habilita_solo_edificio(qtbot, conn):
    obtener_repositorio(conn, "Edificio").crear(Nombre="Torre Norte")
    pantalla = catalogos.pantalla_gastos_operativos(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    catalogos._al_abrir_dialogo_gasto(dialogo)

    combo_alcance = dialogo._entradas["Alcance"]
    combo_edificio = dialogo._entradas["IdEdificio"]
    combo_unidad = dialogo._entradas["IdUnidad"]

    combo_alcance.setCurrentIndex(combo_alcance.findData("Edificio"))
    assert combo_edificio.isEnabled() is True
    assert combo_unidad.isEnabled() is False
    assert combo_unidad.currentData() is None

    combo_alcance.setCurrentIndex(combo_alcance.findData("Espacio general"))
    assert combo_edificio.isEnabled() is False
    assert combo_edificio.currentData() is None


def test_pantalla_responsables_tiene_tres_campos_libres(qtbot, conn):
    pantalla = catalogos.pantalla_responsables(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_pantalla_tipos_licencia_tiene_tres_campos_libres(qtbot, conn):
    pantalla = catalogos.pantalla_tipos_licencia(conn)
    qtbot.addWidget(pantalla)
    nombres = [c.nombre for c in pantalla.campos]
    assert nombres.count("CampoLibre1") == 1
    assert nombres.count("CampoLibre2") == 1
    assert nombres.count("CampoLibre3") == 1


def test_responsables_rol_es_combo_editable(qtbot, conn):
    """Rol es un catálogo abierto (sección 8.2): sugiere los valores
    sembrados pero admite texto libre, a diferencia de Tipo de fecha
    especial."""
    pantalla = catalogos.pantalla_responsables(conn)
    qtbot.addWidget(pantalla)
    dialogo = _DialogoRegistro(conn, pantalla.campos, "Nuevo registro")
    qtbot.addWidget(dialogo)
    combo_rol = dialogo._entradas["Rol"]
    assert combo_rol.isEditable() is True
    combo_rol.setEditText("Rol inventado")
    assert dialogo.valores()["Rol"] == "Rol inventado"


def _completar_gasto(periodo="2026-08", concepto="Limpieza", monto="1000", origen=None):
    def _completar(self, *a, **k):
        self._entradas["Periodo"].setText(periodo)
        self._entradas["Concepto"].setText(concepto)
        self._entradas["Monto"].setText(monto)
        if origen is not None:
            self._entradas["Origen"].setCurrentIndex(self._entradas["Origen"].findData(origen))
        return QDialog.DialogCode.Accepted
    return _completar


def test_gasto_operativo_sin_conflicto_se_guarda(qtbot, conn, monkeypatch):
    pantalla = catalogos.pantalla_gastos_operativos(conn)
    qtbot.addWidget(pantalla)
    monkeypatch.setattr("app.gui.crud_generico._DialogoRegistro.exec", _completar_gasto())

    pantalla._nuevo()

    gastos = obtener_repositorio(conn, "GastoOperativo").listar()
    assert len(gastos) == 1
    assert gastos[0]["Origen"] == "Manual"


def test_gasto_operativo_conflicto_confirmado_reemplaza(qtbot, conn, monkeypatch):
    """Sección 3.25: "Si existe valor para mismo concepto y período de
    otro origen: obliga a elegir entre uno u otro" — confirmar reemplaza
    el existente."""
    id_anterior = obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo="2026-08", Concepto="Limpieza", Monto=500, Origen="Manual",
    )
    pantalla = catalogos.pantalla_gastos_operativos(conn)
    qtbot.addWidget(pantalla)
    monkeypatch.setattr(
        "app.gui.crud_generico._DialogoRegistro.exec", _completar_gasto(monto="800", origen="Importado"),
    )
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    pantalla._nuevo()

    gastos = obtener_repositorio(conn, "GastoOperativo").listar()
    assert len(gastos) == 1
    assert gastos[0]["Origen"] == "Importado"
    assert gastos[0]["Monto"] == 800
    assert obtener_repositorio(conn, "GastoOperativo").obtener(id_anterior) is None


def test_gasto_operativo_conflicto_cancelado_no_guarda(qtbot, conn, monkeypatch):
    id_anterior = obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo="2026-08", Concepto="Limpieza", Monto=500, Origen="Manual",
    )
    pantalla = catalogos.pantalla_gastos_operativos(conn)
    qtbot.addWidget(pantalla)
    monkeypatch.setattr(
        "app.gui.crud_generico._DialogoRegistro.exec", _completar_gasto(monto="800", origen="Importado"),
    )
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    pantalla._nuevo()

    gastos = obtener_repositorio(conn, "GastoOperativo").listar()
    assert len(gastos) == 1
    assert gastos[0]["IdGasto"] == id_anterior
    assert gastos[0]["Monto"] == 500


def test_gasto_operativo_mismo_origen_no_pregunta(qtbot, conn, monkeypatch):
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo="2026-08", Concepto="Limpieza", Monto=500, Origen="Manual",
    )
    pantalla = catalogos.pantalla_gastos_operativos(conn)
    qtbot.addWidget(pantalla)
    monkeypatch.setattr(
        "app.gui.crud_generico._DialogoRegistro.exec", _completar_gasto(monto="800", origen="Manual"),
    )
    preguntas = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: (preguntas.append(1), QMessageBox.StandardButton.Yes)[1]),
    )

    pantalla._nuevo()

    assert preguntas == []
    assert len(obtener_repositorio(conn, "GastoOperativo").listar()) == 2
