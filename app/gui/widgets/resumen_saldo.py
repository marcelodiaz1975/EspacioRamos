"""Resumen de saldo compartido por las solapas "Estado de cuenta" de
Liquidación mensual (F22/F26), Pagos (F21/F25) y Cargos especiales
(F28/F25): "Saldo actual"/"Saldo anterior" siempre, más opcionalmente
"<algo> imputados al mes actual/anterior" — mismo signo real (nunca
valor absoluto) y mismo color rojo-si-negativo (COLOR_ROJO) en todos
los casos, confirmado por la clienta en la revisión uno por uno."""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidgetItem

from app.gui.estilos import COLOR_ROJO
from app.negocio.dias import periodo_actual, periodo_anterior
from app.negocio.formato import formatear_moneda
from app.negocio.mensajes import movimiento_periodo_aislada
from app.repositorio.registro import obtener_repositorio

TEXTO_SIN_PROFESIONAL = "Saldo actual: — - Saldo anterior: —"


def item_monto(valor: float | None) -> QTableWidgetItem:
    """Confirmado por la clienta en la revisión uno por uno: cualquier
    importe/número de una tabla va alineado a la derecha de su celda,
    en todo el sistema — acá queda resuelto para todos los que ya pasan
    por este helper compartido."""
    item = QTableWidgetItem(formatear_moneda(valor or 0.0))
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if (valor or 0.0) < 0:
        item.setForeground(QColor(COLOR_ROJO))
    return item


def fmt_dato(prefijo: str, valor: float) -> str:
    color = COLOR_ROJO if valor < 0 else "black"
    return f'{prefijo}: <span style="color:{color};">{formatear_moneda(valor)}</span>'


def saldo_actual_mostrado(conn: sqlite3.Connection, profesional: sqlite3.Row) -> float:
    """"Saldo actual" que corresponde mostrar para un profesional. Bug
    real reportado por la clienta: para categoría A no hay liquidación
    mensual propia (ver `app.negocio.liquidaciones.CATEGORIAS_CON_
    LIQUIDACION_MENSUAL`), así que nada acredita nunca `Profesional.
    SaldoCuentaActual` — quedaba siempre en $0 aunque el profesional
    tuviera una reserva aislada ya ocurrida y sin pagar. Para un A se
    calcula en vivo (`movimiento_periodo_aislada`, mismo criterio EXACTO
    que usa Centro de mensajería para su columna "Saldo actual"); para
    el resto, el campo persistido ya es correcto (se acredita al emitir
    la liquidación, para R, o al registrar un pago/cargo)."""
    if profesional["CategoriaProfesional"] == "A":
        return movimiento_periodo_aislada(conn, profesional["IdProfesional"], periodo_actual(conn))
    return profesional["SaldoCuentaActual"] or 0.0


def partes_resumen(
    conn: sqlite3.Connection, id_profesional: int, *,
    entidad_imputado: str | None = None, etiqueta_imputado: str | None = None,
) -> list[str]:
    """Las mismas partes que arma `texto_resumen`, sueltas en una lista
    en vez de ya unidas en un único string — para pantallas que
    prefieren mostrar cada dato en su propia línea (ej. Cargos
    especiales) en vez de todo corrido en un renglón."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    partes = [
        fmt_dato("Saldo actual", saldo_actual_mostrado(conn, profesional)),
        fmt_dato("Saldo anterior", profesional["SaldoCuentaAnterior"] or 0.0),
    ]
    if entidad_imputado is not None:
        periodo_act = periodo_actual(conn)
        periodo_ant = periodo_anterior(periodo_act)
        registros = obtener_repositorio(conn, entidad_imputado).listar(IdProfesional=id_profesional)
        monto_actual = sum(r["Monto"] for r in registros if r["PeriodoImputado"] == periodo_act)
        monto_anterior = sum(r["Monto"] for r in registros if r["PeriodoImputado"] == periodo_ant)
        partes.append(fmt_dato(f"{etiqueta_imputado} imputados al mes actual", monto_actual))
        partes.append(fmt_dato(f"{etiqueta_imputado} imputados al mes anterior", monto_anterior))
    return partes


def texto_resumen(
    conn: sqlite3.Connection, id_profesional: int, *,
    entidad_imputado: str | None = None, etiqueta_imputado: str | None = None,
) -> str:
    """`entidad_imputado` es el nombre de repositorio a sumar por
    período (HistorialPagos o CargoEspecial, ambos con columnas
    IdProfesional/Monto/PeriodoImputado) — si se pasa, agrega la
    cuarta y quinta parte "<etiqueta_imputado> imputados al mes
    actual/anterior"."""
    return " - ".join(partes_resumen(
        conn, id_profesional, entidad_imputado=entidad_imputado, etiqueta_imputado=etiqueta_imputado,
    ))
