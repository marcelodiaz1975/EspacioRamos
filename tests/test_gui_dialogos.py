import pytest
from PySide6.QtWidgets import QMessageBox, QWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.dialogos import (
    confirmar_si_fecha_es_mes_anterior,
    confirmar_si_periodo_imputado_es_anterior,
    preguntar_si_no,
)


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    connection.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    yield connection
    connection.close()


def test_confirmar_fecha_mes_actual_no_pregunta(qtbot, conn, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: (_ for _ in ()).throw(AssertionError)))
    parent = QWidget()
    qtbot.addWidget(parent)
    assert confirmar_si_fecha_es_mes_anterior(parent, conn, "2026-08-20") is True


def test_confirmar_fecha_mes_anterior_pregunta_y_respeta_respuesta(qtbot, conn, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    assert confirmar_si_fecha_es_mes_anterior(parent, conn, "2026-07-20") is True

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    assert confirmar_si_fecha_es_mes_anterior(parent, conn, "2026-07-20") is False


def test_confirmar_fecha_sin_valor_no_pregunta(qtbot, conn, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: (_ for _ in ()).throw(AssertionError)))
    parent = QWidget()
    qtbot.addWidget(parent)
    assert confirmar_si_fecha_es_mes_anterior(parent, conn, None) is True


def test_confirmar_periodo_imputado_mes_anterior_pregunta_y_respeta_respuesta(qtbot, conn, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    assert confirmar_si_periodo_imputado_es_anterior(parent, conn, "2026-07") is False

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    assert confirmar_si_periodo_imputado_es_anterior(parent, conn, "2026-08") is True


def _simular_click(texto_boton: str):
    """Arma los botones a mano (como hace `preguntar_si_no`) y los
    clickea de verdad sin abrir el loop modal de `exec()` — `.click()`
    dispara igual la conexión interna de `QMessageBox` que fija
    `clickedButton()`, confirmado que no hace falta un `exec()` real."""
    def _exec(self):
        for boton in self.buttons():
            if boton.text() == texto_boton:
                boton.click()
                return 0
        raise AssertionError(f"No se encontró el botón {texto_boton!r} entre {[b.text() for b in self.buttons()]}")
    return _exec


def test_preguntar_si_no_botones_en_espanol_sin_depender_de_la_traduccion_de_qt(qtbot, monkeypatch):
    """Pedido explícito de la clienta: seguía viendo "Yes" en inglés en
    la alerta de "Restablecer descuentos" — los botones de `preguntar_si_no`
    tienen el texto "Sí"/"No" fijo, no delegan en la traducción oficial
    de Qt."""
    parent = QWidget()
    qtbot.addWidget(parent)
    monkeypatch.setattr(QMessageBox, "exec", _simular_click("Sí"))
    assert preguntar_si_no(parent, "Título", "Texto") is True


def test_preguntar_si_no_devuelve_false_si_se_clickea_no(qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    monkeypatch.setattr(QMessageBox, "exec", _simular_click("No"))
    assert preguntar_si_no(parent, "Título", "Texto") is False


def test_preguntar_si_no_default_si_por_defecto(qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    capturado = {}

    def _exec(self):
        capturado["default"] = self.defaultButton().text()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    preguntar_si_no(parent, "Título", "Texto")
    assert capturado["default"] == "Sí"


def test_preguntar_si_no_default_no_si_se_pide_explicitamente(qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    capturado = {}

    def _exec(self):
        capturado["default"] = self.defaultButton().text()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    preguntar_si_no(parent, "Título", "Texto", default_si=False)
    assert capturado["default"] == "No"
