"""Listas editables (F02, sección 3.19): catálogo de valores por tipo que
alimenta los combos de otros formularios en vez de dejarlos como texto
libre (sección 8.2: CondicionFiscal, MedioPago, CuentaReceptora,
TipoFechaEspecial, RolResponsable, TipoLlave, MotivoAusencia). El valor
guardado en la tabla destino es el texto de la opción — no hay un ID
separado, así que el combo usa el mismo texto como dato y como
etiqueta."""
from __future__ import annotations

import sqlite3
from typing import Callable

from app.repositorio.registro import obtener_repositorio


def valores_lista(conn: sqlite3.Connection, tipo_lista: str) -> list[str]:
    """Valores activos de `tipo_lista`, en el orden configurado (campo
    Orden de ListasEditables) — el primero es el default de esa lista."""
    filas = obtener_repositorio(conn, "ListasEditables").listar(TipoLista=tipo_lista, Activo=1)
    return [f["Valor"] for f in sorted(filas, key=lambda f: f["Orden"])]


def opciones_lista(tipo_lista: str) -> Callable[[sqlite3.Connection], list[tuple[str, str]]]:
    """Fábrica de `opciones` para Campo(tipo="combo") del CRUD genérico
    (app.gui.crud_generico)."""
    def _opciones(conn: sqlite3.Connection) -> list[tuple[str, str]]:
        return [(v, v) for v in valores_lista(conn, tipo_lista)]
    return _opciones
