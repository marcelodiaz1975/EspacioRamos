"""Condiciones y normas (Etapa 7, sección 4.5): los puntos editables que
`app.pdf.valores_pdf` imprime ordenados por `Numero` — acá vive el hook
de reordenamiento de ese campo (delegado en `app.negocio.posicion`, ver
ahí el criterio general), separado de la GUI."""
from __future__ import annotations

import sqlite3

from app.negocio.posicion import reordenar_posicion_al_guardar


def reordenar_al_guardar(conn: sqlite3.Connection, valores: dict, registro: sqlite3.Row | None) -> dict:
    """Hook `al_guardar` de la pantalla de Condiciones y normas: Numero
    es una posición dentro de toda la lista (1, 2, 3...), no un número
    suelto — ver `app.negocio.posicion.reordenar_posicion_al_guardar`."""
    return reordenar_posicion_al_guardar(conn, "CondicionNorma", "IdCondicion", "Numero", valores, registro, base=1)
