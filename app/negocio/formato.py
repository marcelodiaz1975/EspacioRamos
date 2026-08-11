"""Formateo de fechas/horas/períodos compartido por los PDFs y los
mensajes del sistema: fechas cortas "D/M" sin ceros a la izquierda dentro
de texto corrido, fechas largas "DD/MM/AAAA" en tablas, y "Xhs"/"X:MMhs"
para horarios."""
from __future__ import annotations

from datetime import date

MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def mes_texto(mes: int) -> str:
    return MESES[mes]


def periodo_mm_aaaa(periodo: str) -> str:
    """'2026-07' -> '07/2026'."""
    anio, mes = periodo.split("-")
    return f"{mes}/{anio}"


def fecha_corta(fecha_iso: str) -> str:
    """'2026-07-08' -> '8/7' (sin ceros a la izquierda)."""
    d = date.fromisoformat(fecha_iso)
    return f"{d.day}/{d.month}"


def fecha_larga(fecha_iso: str | None) -> str:
    """'2026-07-08' -> '08/07/2026'."""
    if not fecha_iso:
        return "—"
    d = date.fromisoformat(fecha_iso)
    return d.strftime("%d/%m/%Y")


def hora_fmt(hora: float) -> str:
    """14 -> '14hs'; 14.5 -> '14:30hs'."""
    if hora == int(hora):
        return f"{int(hora)}hs"
    horas = int(hora)
    minutos = round((hora - horas) * 60)
    return f"{horas}:{minutos:02d}hs"
