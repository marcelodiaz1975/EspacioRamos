import pytest
from PySide6.QtWidgets import QMessageBox, QWidget

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.dialogos import confirmar_si_fecha_es_mes_anterior, confirmar_si_periodo_imputado_es_anterior


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
