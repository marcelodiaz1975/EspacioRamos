import pytest
from PySide6.QtWidgets import QDialog, QMessageBox, QPushButton

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
    catalogos.pantalla_esquema_descuentos,
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


def test_esquema_descuentos_es_solo_lectura(qtbot, conn):
    """Sección 3.18: "solo modificable al ejecutar análisis de aumentos" —
    el catálogo genérico no debe ofrecer Nuevo/Editar/Eliminar ni edición
    por doble clic, para no romper el historial que garantiza
    aumentos.actualizar_esquema_descuentos."""
    pantalla = catalogos.pantalla_esquema_descuentos(conn)
    qtbot.addWidget(pantalla)
    assert pantalla.solo_lectura is True
    textos_botones = [boton.text() for boton in pantalla.findChildren(QPushButton)]
    assert not any(texto in ("Nuevo", "Editar", "Eliminar") for texto in textos_botones)


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
