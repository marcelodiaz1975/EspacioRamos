"""Reacomodo automático de un campo de posición (N°, Orden, etc.) al
guardar un alta o edición en una tabla plana, sin agrupación — mismo
criterio en Condiciones y normas y Detalles complementarios (Propuesta):
la posición elegida se respeta, las demás filas se corren para dejarle
lugar, sin huecos ni empates (pedido de la clienta, mismo mecanismo que
`app.negocio.listas_editables.reordenar_al_guardar`, que tiene su propia
versión porque además agrupa por TipoLista)."""
from __future__ import annotations

import sqlite3

from app.repositorio.registro import obtener_repositorio


def reordenar_posicion_al_guardar(
    conn: sqlite3.Connection, tabla: str, columna_pk: str, columna_posicion: str,
    valores: dict, registro: sqlite3.Row | None, base: int = 1,
) -> dict:
    """Hook `al_guardar` de `app.gui.crud_generico.PantallaCRUD` para
    `tabla`: corre a las demás filas para dejar libre `columna_posicion`
    en el valor pedido (clampeado entre `base` y "última posición + 1").
    Dejar la posición vacía en un alta manda el registro al final."""
    repo = obtener_repositorio(conn, tabla)
    id_actual = registro[columna_pk] if registro is not None else None
    hermanos = sorted(
        (f for f in repo.listar() if f[columna_pk] != id_actual),
        key=lambda f: (f[columna_posicion], f[columna_pk]),
    )
    deseada = valores.get(columna_posicion)
    deseada = int(deseada) if deseada is not None else len(hermanos) + base
    final = max(base, min(deseada, len(hermanos) + base))
    for indice, hermano in enumerate(hermanos, start=base):
        nueva = indice if indice < final else indice + 1
        if hermano[columna_posicion] != nueva:
            repo.actualizar(hermano[columna_pk], **{columna_posicion: nueva})
    valores[columna_posicion] = final
    return valores
