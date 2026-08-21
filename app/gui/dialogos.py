"""Diálogos de confirmación reusados entre varias pantallas."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QMessageBox, QWidget

from app.negocio.dias import periodo_actual
from app.negocio.formato import mes_texto


def _confirmar_periodo_anterior(parent: QWidget, periodo: str, detalle: str) -> bool:
    anio, mes = (int(p) for p in periodo.split("-"))
    respuesta = QMessageBox.question(
        parent, "Fecha de un mes anterior",
        f"{detalle} corresponde a {mes_texto(mes)} de {anio}, un mes anterior al que está en curso.\n\n"
        "¿Confirmás que es correcta?",
    )
    return respuesta == QMessageBox.StandardButton.Yes


def confirmar_si_fecha_es_mes_anterior(parent: QWidget, conn: sqlite3.Connection, fecha_iso: str | None) -> bool:
    """DC-06 §3: cualquier movimiento cargado con una fecha de un mes
    anterior al mes en curso (algo que puede pasar mucho tiempo después de
    haber avanzado de mes, no solo en los primeros días) pide confirmación
    antes de guardarse, para atajar errores de tipeo en la fecha. Devuelve
    True si corresponde continuar: la fecha no es de un mes anterior, o el
    operador confirmó que es correcta."""
    if not fecha_iso:
        return True
    periodo_fecha = fecha_iso[:7]
    if periodo_fecha >= periodo_actual(conn):
        return True
    return _confirmar_periodo_anterior(parent, periodo_fecha, f"La fecha ingresada ({fecha_iso})")


def confirmar_si_periodo_imputado_es_anterior(parent: QWidget, conn: sqlite3.Connection, periodo: str | None) -> bool:
    """Misma confirmación que `confirmar_si_fecha_es_mes_anterior`, para
    formularios que imputan directo a un período ('AAAA-MM') en vez de a
    una fecha puntual (pagos, cargos especiales)."""
    if not periodo or periodo >= periodo_actual(conn):
        return True
    return _confirmar_periodo_anterior(parent, periodo, f"El período imputado ({periodo})")
