"""Config compartida por toda la suite: los tests de GUI (Etapa 8+) corren
con el backend Qt "offscreen" — no hace falta un display real ni Xvfb."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QMessageBox  # noqa: E402 (después de fijar QT_QPA_PLATFORM)

import app.gui.widgets.planilla_flotante as _planilla_flotante  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _planilla_flotante_grilla_chica_para_tests():
    """Bug real de PySide6/shiboken (6.12.0, este sandbox — ver el
    docstring de `PlanillaFlotante`, "CUARTO hallazgo"): construir/usar
    la grilla al tamaño pedido por la clienta (columnas A-Z, filas hasta
    la 100 — 2600 celdas) consume, por sí solo, la mayor parte de un
    presupuesto FIJO y chico de "churn" de objetos de Qt/shiboken por
    proceso — confirmado con scripts offscreen aislados, no depende de
    cuántos ítems se crean/mutan en esta pantalla. Una vez agotado ese
    presupuesto, CUALQUIER recolección de basura cíclica posterior
    (automática de Python, no solo la del cierre final del proceso)
    aborta TODO el intérprete ("Fatal Python error: none_dealloc") — en
    una corrida de pytest, con sus propios fixtures/widgets/qtbot sumando
    al mismo presupuesto compartido, esto se reproducía de forma
    DETERMINÍSTICA a los pocos tests de `test_gui_widget_planilla_
    flotante.py` (confirmado: siempre en el mismo test, no al azar).

    No es un bug de esta pantalla ni se puede arreglar desde su código
    (ver el docstring del módulo) — la aplicación real sigue usando el
    tamaño completo pedido (`_FILAS`/`_COLUMNAS` sin tocar fuera de
    tests). Acá, para que la SUITE no aborte, se achica la grilla a algo
    muy por debajo de cualquier umbral encontrado (15×15 = 225 celdas,
    de sobra para cualquier test — ninguno usa una fila/columna más allá
    de la 5) durante toda la sesión de tests; ningún test referencia
    `_FILAS`/`_COLUMNAS` directo esperando el valor de producción."""
    _planilla_flotante._FILAS = 15
    _planilla_flotante._COLUMNAS = 15


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
