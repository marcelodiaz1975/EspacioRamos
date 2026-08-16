"""Fechas especiales / feriados (sección 3.17 del documento).

Se cargan a mano desde la pantalla de Fechas especiales — sin importación
automática desde ningún sitio externo (decisión explícita: evitar
depender de un formato de página/API que puede cambiar, y poder darle a
una fecha puntual un tratamiento distinto del que traería un sitio
externo)."""
from __future__ import annotations

import sqlite3
from datetime import date

from app.repositorio.registro import obtener_repositorio

TIPOS_QUE_DESCUENTAN_100 = ("Feriado nacional", "Día no laborable")


def feriados_relevantes_periodo(conn: sqlite3.Connection, anio: int, mes: int) -> list[sqlite3.Row]:
    """Feriados que se descuentan al 100% en la liquidación (sección 5.4):
    nacionales y no laborables, de lunes a sábado (domingos se omiten)."""
    prefijo = f"{anio:04d}-{mes:02d}-"
    filas = obtener_repositorio(conn, "FechasEspeciales").listar(Activo=1)
    resultado = []
    for f in filas:
        if not f["Fecha"].startswith(prefijo):
            continue
        if f["Tipo"] not in TIPOS_QUE_DESCUENTAN_100:
            continue
        if date.fromisoformat(f["Fecha"]).weekday() == 6:  # domingo
            continue
        resultado.append(f)
    return resultado
