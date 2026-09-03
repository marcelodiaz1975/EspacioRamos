import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

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
)
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


def test_combo_profesional_asignar_es_buscable_por_codigo_o_nombre(qtbot, conn):
    """Confirmado por la clienta: el selector de profesional buscable
    corre en todos los formularios del sistema, Llaves incluido."""
    id_llave = _crear_tipo_con_copia(conn)
    tipo = obtener_repositorio(conn, "Llave").obtener(id_llave)
    dialogo = _DialogoAsignar(conn, tipo, 1)
    qtbot.addWidget(dialogo)
    completador = dialogo.combo_profesional.completer()
    assert completador.filterMode() == Qt.MatchFlag.MatchContains


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
    conn.execute(
        "INSERT INTO Edificio (Nombre, DomicilioLocalidad) VALUES ('Ramos 1', 'CABA')"
    )
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


def test_deshacer_ultimo_revierte_asignacion(qtbot, conn, monkeypatch):
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
    assert pantalla.boton_deshacer.isEnabled() is True

    pantalla._deshacer_ultimo()

    movimientos_restantes = obtener_repositorio(conn, "LlaveMovimiento").listar()
    assert len(movimientos_restantes) == 1  # queda el Ingreso original, se deshizo solo la Asignación
    assert movimientos_restantes[0]["Tipo"] == "Ingreso"
    assert obtener_repositorio(conn, "CargoEspecial").listar() == []
    assert pantalla.boton_deshacer.isEnabled() is False


def test_deshacer_sin_movimientos_no_falla(qtbot, conn):
    pantalla = PantallaLlaves(conn)
    qtbot.addWidget(pantalla)
    pantalla._deshacer_ultimo()
