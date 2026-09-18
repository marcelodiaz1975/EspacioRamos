"""Condiciones y normas (Etapa 7, sección 4.5): los puntos editables que
`app.pdf.valores_pdf` imprime ordenados por `Numero` — acá vive el hook
de reordenamiento de ese campo, separado de la GUI (mismo criterio que
`app.negocio.listas_editables.reordenar_al_guardar`)."""
from __future__ import annotations

import sqlite3

from app.repositorio.registro import obtener_repositorio


def reordenar_al_guardar(conn: sqlite3.Connection, valores: dict, registro: sqlite3.Row | None) -> dict:
    """Hook `al_guardar` de la pantalla de Condiciones y normas
    (`app.gui.crud_generico.PantallaCRUD`): igual criterio que Orden en
    Listas editables — Numero es una posición dentro de toda la lista
    (1, 2, 3...), no un número suelto. Al guardar, las demás filas se
    corren para dejar libre el Numero elegido (clampeado a un rango
    válido), sin huecos ni empates."""
    repo = obtener_repositorio(conn, "CondicionNorma")
    id_actual = registro["IdCondicion"] if registro is not None else None
    hermanos = sorted(
        (f for f in repo.listar() if f["IdCondicion"] != id_actual),
        key=lambda f: (f["Numero"], f["IdCondicion"]),
    )
    numero_deseado = valores.get("Numero")
    numero_deseado = int(numero_deseado) if numero_deseado is not None else len(hermanos) + 1
    numero_final = max(1, min(numero_deseado, len(hermanos) + 1))
    for indice, hermano in enumerate(hermanos, start=1):
        nuevo_numero = indice if indice < numero_final else indice + 1
        if hermano["Numero"] != nuevo_numero:
            repo.actualizar(hermano["IdCondicion"], Numero=nuevo_numero)
    valores["Numero"] = numero_final
    return valores
