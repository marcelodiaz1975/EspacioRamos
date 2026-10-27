"""Indicador "Procesando..." para operaciones sincrónicas largas (pedido
de la clienta, ej. "emitir todas las liquidaciones": "que muestre algo
chico en el centro de la pantalla como un relojito de arena junto a la
palabra 'Procesando...' para que no quede la sensación de que se colgó").

Qt es de un solo hilo: un loop largo sin pausas deja la ventana sin
repintarse ni responder hasta que termina, aunque el trabajo en sí sea
rápido por vuelta (ej. generar un PDF por profesional, de a varios
segundos en total). Mover ese trabajo a otro hilo traería más riesgo que
beneficio acá (la conexión sqlite no está pensada para compartirse entre
hilos) — en vez de eso, el propio loop que hace el trabajo llama a
`tick()` en cada vuelta, que fuerza a Qt a procesar los eventos de
pintado pendientes (incluido el propio cartel) antes de seguir."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

_CUADROS = ("⏳", "⌛")


class Procesando:
    """Uso:

        with Procesando(self, "Procesando liquidaciones..."):
            for item in lista:
                ... trabajo real ...
                procesando.tick()

    `parent`, si se pasa, centra el cartel sobre esa ventana — sin
    `parent` queda centrado en la pantalla."""

    def __init__(self, parent: QWidget | None = None, texto: str = "Procesando...") -> None:
        self._texto = texto
        self._cuadro = 0
        self._ventana = QWidget(
            parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint,
        )
        self._ventana.setObjectName("cartelProcesando")
        self._ventana.setStyleSheet(
            "#cartelProcesando { background-color: white; border: 1px solid black; border-radius: 6px; }"
        )
        layout = QVBoxLayout(self._ventana)
        self._etiqueta = QLabel(f"{_CUADROS[0]}  {texto}")
        self._etiqueta.setStyleSheet("font-size: 14px; padding: 6px;")
        layout.addWidget(self._etiqueta)

    def __enter__(self) -> "Procesando":
        self._ventana.adjustSize()
        padre = self._ventana.parentWidget()
        if padre is not None:
            centro = padre.mapToGlobal(padre.rect().center())
            self._ventana.move(centro - self._ventana.rect().center())
        self._ventana.show()
        QApplication.processEvents()
        return self

    def tick(self) -> None:
        """Llamar una vez por vuelta del loop que hace el trabajo real —
        anima el relojito y le da lugar a Qt para procesar lo pendiente
        (pintado de este cartel, eventos del sistema, etc.)."""
        self._cuadro = 1 - self._cuadro
        self._etiqueta.setText(f"{_CUADROS[self._cuadro]}  {self._texto}")
        QApplication.processEvents()

    def __exit__(self, *exc: object) -> None:
        self._ventana.close()
