"""Calculadora flotante (F2, pedido general de la clienta: "que se
emerja una calculadora de pantalla flotante como para hacer cálculos
random, que se pueda cerrar con la cruz típica de todas las apps") — una
ventana de verdad (no un diálogo modal: no tiene que bloquear el resto
del sistema mientras está abierta), con las cuatro operaciones básicas.
No guarda ningún estado de negocio ni toca la base — es una herramienta
suelta, igual que la calculadora de cualquier sistema operativo."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QGridLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

_TECLAS_VALIDAS = set("0123456789.+-*/")

_BOTONES = [
    ["7", "8", "9", "/"],
    ["4", "5", "6", "*"],
    ["1", "2", "3", "-"],
    ["C", "0", "=", "+"],
]


class Calculadora(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculadora")
        self.setWindowFlag(Qt.WindowType.Window)
        self.setFixedSize(220, 280)
        # Sin esto, cerrarla con la cruz solo la ESCONDE (comportamiento
        # default de `QWidget.close()`) — la ventana en sí sigue viva, y
        # quien la abrió (F2 en `VentanaPrincipal`) nunca se entera de que
        # "se cerró" para poder abrir una nueva la próxima vez.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._expresion = ""

        # Pedido de la clienta: números y signos matemáticos del teclado,
        # no solo del mouse — la ventana entera (no "pantalla", de solo
        # lectura y sin motivo para quedarse con el foco) es la que recibe
        # las teclas, ver `keyPressEvent`.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        self.pantalla = QLineEdit()
        self.pantalla.setReadOnly(True)
        self.pantalla.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pantalla.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pantalla.setFixedHeight(40)
        layout.addWidget(self.pantalla)

        grilla = QGridLayout()
        for fila, teclas in enumerate(_BOTONES):
            for columna, tecla in enumerate(teclas):
                boton = QPushButton(tecla)
                boton.setFixedSize(45, 45)
                boton.clicked.connect(lambda _checked=False, t=tecla: self._al_tocar(t))
                grilla.addWidget(boton, fila, columna)
        layout.addLayout(grilla)

        boton_punto = QPushButton(".")
        boton_punto.setFixedSize(45, 45)
        boton_punto.clicked.connect(lambda: self._al_tocar("."))
        grilla.addWidget(boton_punto, len(_BOTONES), 0)

        boton_borrar = QPushButton("←")
        boton_borrar.setFixedSize(45, 45)
        boton_borrar.clicked.connect(self._borrar_ultimo)
        grilla.addWidget(boton_borrar, len(_BOTONES), 1)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (override de Qt)
        """Números y signos matemáticos del teclado, no solo del mouse —
        mismos botones de siempre, solo que disparados por tecla en vez
        de click. La coma (teclado numérico en configuraciones que la
        usan como separador decimal) se trata igual que el punto."""
        tecla = event.key()
        if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Equal):
            self._al_tocar("=")
        elif tecla == Qt.Key.Key_Backspace:
            self._borrar_ultimo()
        elif tecla in (Qt.Key.Key_Escape, Qt.Key.Key_C):
            self._al_tocar("C")
        elif tecla == Qt.Key.Key_Comma:
            self._al_tocar(".")
        elif event.text() in _TECLAS_VALIDAS:
            self._al_tocar(event.text())
        else:
            super().keyPressEvent(event)

    def _al_tocar(self, tecla: str) -> None:
        if tecla == "C":
            self._expresion = ""
        elif tecla == "=":
            self._calcular()
            return
        else:
            self._expresion += tecla
        self.pantalla.setText(self._expresion)

    def _borrar_ultimo(self) -> None:
        self._expresion = self._expresion[:-1]
        self.pantalla.setText(self._expresion)

    def _calcular(self) -> None:
        # Solo dígitos/./+-*/ y paréntesis — nunca texto arbitrario, así
        # `eval` acá no abre ninguna puerta a código ejecutable externo
        # (los botones solo agregan uno de estos caracteres, y
        # `keyPressEvent` filtra el teclado contra el mismo conjunto).
        if not self._expresion or any(c not in "0123456789.+-*/() " for c in self._expresion):
            self.pantalla.setText("Error")
            self._expresion = ""
            return
        try:
            resultado = eval(self._expresion, {"__builtins__": {}}, {})  # noqa: S307
        except (SyntaxError, ZeroDivisionError, ArithmeticError):
            self.pantalla.setText("Error")
            self._expresion = ""
            return
        self._expresion = str(resultado)
        self.pantalla.setText(self._expresion)
