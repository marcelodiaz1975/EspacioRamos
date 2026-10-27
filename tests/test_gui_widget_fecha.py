"""Tests del mecanismo compartido de Flecha arriba/abajo = fecha completa
(app/gui/widgets/fecha.py) a nivel del widget en sí, en vez de repetirlos en
cada pantalla que lo usa — la garantía es la misma en todos los formularios
porque es el mismo event filter."""
from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDateEdit

from app.gui.widgets.fecha import instalar_flechas_cambian_fecha_completa


def _mostrar(qtbot, campo: QDateEdit) -> None:
    qtbot.addWidget(campo)
    campo.show()
    qtbot.waitExposed(campo)


def test_flecha_arriba_cruza_fin_de_mes(qtbot):
    """Antes de este mecanismo, Qt clampeaba Flecha arriba al día 31
    sin pasar a noviembre — la sección "dd" no cruza de mes sola."""
    campo = QDateEdit()
    campo.setDisplayFormat("dd-MM-yyyy")
    campo.setDate(QDate(2026, 10, 31))
    instalar_flechas_cambian_fecha_completa(campo)
    _mostrar(qtbot, campo)

    QTest.keyClick(campo, Qt.Key.Key_Up)
    assert campo.date() == QDate(2026, 11, 1)


def test_flecha_abajo_cruza_fin_de_anio(qtbot):
    campo = QDateEdit()
    campo.setDisplayFormat("dd-MM-yyyy")
    campo.setDate(QDate(2027, 1, 1))
    instalar_flechas_cambian_fecha_completa(campo)
    _mostrar(qtbot, campo)

    QTest.keyClick(campo, Qt.Key.Key_Down)
    assert campo.date() == QDate(2026, 12, 31)


def test_flecha_arriba_con_formato_dia_de_semana_no_se_traba_ni_retrocede(qtbot):
    """Caso real reportado por la clienta: con el formato "ddd dd-MM-yyyy"
    (Registro de ausencias, Fechas especiales, etc.) el cursor arranca
    sobre la sección de día de la semana — ahí Qt, al llegar al último
    día de la semana, saltaba HACIA ATRÁS al mismo día de la semana
    anterior y se quedaba trabado repitiendo esa fecha."""
    campo = QDateEdit()
    campo.setDisplayFormat("ddd dd-MM-yyyy")
    campo.setLocale(QLocale(QLocale.Language.Spanish))
    campo.setDate(QDate(2026, 10, 27))  # martes
    instalar_flechas_cambian_fecha_completa(campo)
    _mostrar(qtbot, campo)

    for _ in range(8):
        QTest.keyClick(campo, Qt.Key.Key_Up)
    # 8 días después del 27-10 (martes) es el 04-11 (miércoles) — cruza
    # tanto el fin de semana como el fin de mes sin trabarse.
    assert campo.date() == QDate(2026, 11, 4)


def test_flecha_abajo_simetrica_a_la_de_arriba(qtbot):
    campo = QDateEdit()
    campo.setDisplayFormat("dd-MM-yyyy")
    campo.setDate(QDate(2026, 11, 4))
    instalar_flechas_cambian_fecha_completa(campo)
    _mostrar(qtbot, campo)

    for _ in range(8):
        QTest.keyClick(campo, Qt.Key.Key_Down)
    assert campo.date() == QDate(2026, 10, 27)
