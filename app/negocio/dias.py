"""Utilidades de días de la semana en español."""
from datetime import date

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def fecha_a_dia_semana(fecha: date) -> str:
    """date.weekday() da 0=lunes..6=domingo, que es justo el orden de DIAS_SEMANA."""
    return DIAS_SEMANA[fecha.weekday()]
