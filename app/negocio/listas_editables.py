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


def _renumerar(repo, tipo_lista: str, excluir_id: int | None) -> None:
    """Deja el Orden de `tipo_lista` contiguo y sin empates (0, 1, 2...),
    salteando `excluir_id` — se usa tanto para cerrar el hueco que deja un
    ítem que cambió de tipo de lista como, con `excluir_id=None`, para
    normalizar una lista completa."""
    filas = sorted(
        (f for f in repo.listar(TipoLista=tipo_lista) if f["IdOpcion"] != excluir_id),
        key=lambda f: (f["Orden"], f["IdOpcion"]),
    )
    for indice, fila in enumerate(filas):
        if fila["Orden"] != indice:
            repo.actualizar(fila["IdOpcion"], Orden=indice)


def reordenar_al_guardar(conn: sqlite3.Connection, valores: dict, registro: sqlite3.Row | None) -> dict:
    """Hook `al_guardar` de la pantalla de Listas editables
    (`app.gui.crud_generico.PantallaCRUD`): pedido de la clienta al
    revisar este catálogo — el Orden no es un número suelto, es una
    posición dentro de su TipoLista. Al guardar, las demás filas de ese
    mismo tipo se corren para dejar libre el lugar elegido (como
    arrastrar y soltar), en vez de convivir con huecos o con dos filas
    empatadas en el mismo Orden. Si además la edición cambia el
    TipoLista de una fila existente, primero cierra el hueco que deja en
    su lista anterior."""
    repo = obtener_repositorio(conn, "ListasEditables")
    id_actual = registro["IdOpcion"] if registro is not None else None
    tipo_lista = valores.get("TipoLista")

    if registro is not None and registro["TipoLista"] != tipo_lista:
        _renumerar(repo, registro["TipoLista"], excluir_id=id_actual)

    hermanos = sorted(
        (f for f in repo.listar(TipoLista=tipo_lista) if f["IdOpcion"] != id_actual),
        key=lambda f: (f["Orden"], f["IdOpcion"]),
    )
    orden_deseado = valores.get("Orden")
    orden_deseado = int(orden_deseado) if orden_deseado is not None else len(hermanos)
    orden_final = max(0, min(orden_deseado, len(hermanos)))
    for indice, hermano in enumerate(hermanos):
        nuevo_orden = indice if indice < orden_final else indice + 1
        if hermano["Orden"] != nuevo_orden:
            repo.actualizar(hermano["IdOpcion"], Orden=nuevo_orden)
    valores["Orden"] = orden_final
    return valores
