"""Validadores de formato para campos de texto libre — reusados por
`app.gui.crud_generico.Campo.validador` (catálogos y Profesionales) y por
pantallas con sus propios campos de fecha/período/email en texto libre en
vez de un widget dedicado (`QDateEdit`, `QDoubleSpinBox`). Cada uno valida
el TEXTO tal como lo tipea el operador, no le importa a qué tabla/columna
va a parar."""
from __future__ import annotations

import re
from datetime import date

from app.negocio.dias import parsear_periodo

_REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

FORMATO_FECHA = "AAAA-MM-DD"
FORMATO_PERIODO = "AAAA-MM"
FORMATO_EMAIL = "ejemplo@dominio.com"
FORMATO_DNI = "solo números (6 a 9 dígitos)"
FORMATO_CUIT = "11 dígitos (XX-XXXXXXXX-X, con o sin guiones)"


def es_fecha_valida(texto: str) -> bool:
    """AAAA-MM-DD, y que sea una fecha real (rechaza "2026-02-30")."""
    try:
        date.fromisoformat(texto)
        return True
    except ValueError:
        return False


def es_periodo_valido(texto: str) -> bool:
    """AAAA-MM, con el mes dentro de 1-12 (reusa `dias.parsear_periodo`,
    la misma validación que ya usan `sumar_meses`/`periodo_anterior`)."""
    try:
        parsear_periodo(texto)
        return True
    except ValueError:
        return False


def es_email_valido(texto: str) -> bool:
    return bool(_REGEX_EMAIL.fullmatch(texto))


def es_dni_valido(texto: str) -> bool:
    return texto.isdigit() and 6 <= len(texto) <= 9


def es_cuit_valido(texto: str) -> bool:
    return texto.isdigit() and len(texto) == 11
