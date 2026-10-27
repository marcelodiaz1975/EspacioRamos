from app.gui.widgets.procesando import Procesando


def test_se_muestra_al_entrar_y_se_cierra_al_salir(qtbot):
    with Procesando() as procesando:
        qtbot.addWidget(procesando._ventana)
        assert procesando._ventana.isVisible() is True
        assert "Procesando..." in procesando._etiqueta.text()

    assert procesando._ventana.isVisible() is False


def test_tick_anima_el_relojito(qtbot):
    with Procesando(texto="Procesando liquidaciones...") as procesando:
        qtbot.addWidget(procesando._ventana)
        texto_inicial = procesando._etiqueta.text()
        procesando.tick()
        assert procesando._etiqueta.text() != texto_inicial
        assert "Procesando liquidaciones..." in procesando._etiqueta.text()


def test_se_centra_sobre_el_parent(qtbot):
    from PySide6.QtWidgets import QWidget

    padre = QWidget()
    padre.resize(400, 300)
    padre.move(100, 100)
    qtbot.addWidget(padre)
    padre.show()

    with Procesando(padre) as procesando:
        qtbot.addWidget(procesando._ventana)
        assert procesando._ventana.isVisible() is True
