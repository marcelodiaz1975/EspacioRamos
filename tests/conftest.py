"""Config compartida por toda la suite: los tests de GUI (Etapa 8+) corren
con el backend Qt "offscreen" — no hace falta un display real ni Xvfb."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QMessageBox  # noqa: E402 (después de fijar QT_QPA_PLATFORM)


@pytest.fixture(autouse=True)
def _sin_dialogos_modales_por_defecto(monkeypatch):
    """Punto 1.11 (SistemaDF v0.11.2026.10, "alerta final de operación
    completada exitosamente"/"alerta de cancelación") sumó un
    `QMessageBox.information`/`question` nuevo a varias acciones ya
    existentes (crear/editar/eliminar en `PantallaCRUD` y otros paneles
    armados a mano) — en la plataforma Qt "offscreen" que usa esta
    suite, `QMessageBox.exec()` sigue siendo un diálogo MODAL de verdad
    (abre su propio loop de eventos y espera a que lo cierren), así que
    cualquier test que dispare una de esas acciones sin mockear estos
    tres métodos se queda esperando para siempre a un clic que nunca va
    a llegar — confirmado reproduciendo el hang real con `pytest -v`
    contra un test de `test_catalogos.py` que no lo mockeaba.

    Este fixture global da un default sensato y seguro para TODA la
    suite (`information`/`warning` no hacen nada, `question` responde
    "Sí") — cualquier archivo que ya tenga su propia fixture `autouse`
    local haciendo lo mismo (la mayoría, de rondas anteriores) sigue
    funcionando igual; los tests puntuales que necesitan otra respuesta
    de `question`, o capturar el texto de un `information`, siguen
    pisándolo con su propio `monkeypatch.setattr` dentro del test, que
    corre después y gana."""
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
