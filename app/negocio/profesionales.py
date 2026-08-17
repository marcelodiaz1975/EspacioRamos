"""Reglas del legajo de Profesional (sección 3.4) que no encajan en el
CRUD genérico: sugerencia de código y pre-completado de tratamiento."""
from __future__ import annotations

import sqlite3

from app.repositorio.registro import obtener_repositorio


def sugerir_codigo(conn: sqlite3.Connection, categoria: str) -> str:
    """Prefijo letra (la categoría) + número más bajo todavía no usado en
    esa categoría (sección 3.4: "prefijo letra + número más bajo
    disponible en la categoría, editable antes de confirmar") — es solo
    un punto de partida, el operador lo puede pisar antes de guardar."""
    usados = set()
    for fila in obtener_repositorio(conn, "Profesional").listar(CategoriaProfesional=categoria):
        codigo = (fila["IdCodigo"] or "").strip()
        resto = codigo[len(categoria):] if codigo.startswith(categoria) else ""
        if resto.isdigit():
            usados.add(int(resto))
    numero = 1
    while numero in usados:
        numero += 1
    return f"{categoria}{numero}"


def tratamiento_sugerido(conn: sqlite3.Connection, id_profesion: int | None, sexo: str | None) -> str | None:
    """Sección 3.4: "Tratamiento (pre-completado según profesión y sexo,
    editable)". Sin profesión, o con un sexo sin default propio en la
    sección 8.1 (No binario), no hay nada que sugerir.

    Si la profesión tiene desplegable (Fonoaudiología/Psicopedagogía),
    sugiere la primera opción en vez del texto combinado de
    TratamientoDefault* ("Fgo. o Lic."), que no es ninguna de las
    opciones seleccionables."""
    if id_profesion is None:
        return None
    profesion = obtener_repositorio(conn, "Profesion").obtener(id_profesion)
    if profesion is None:
        return None
    if profesion["TieneMultiplesTratamientos"]:
        opciones = opciones_tratamiento(conn, id_profesion, sexo)
        if opciones:
            return opciones[0]
    if sexo == "Femenino":
        return profesion["TratamientoDefaultFemenino"]
    if sexo == "Masculino":
        return profesion["TratamientoDefaultMasculino"]
    return None


def opciones_tratamiento(conn: sqlite3.Connection, id_profesion: int | None, sexo: str | None) -> list[str]:
    """Sección 8.1: Fonoaudiología y Psicopedagogía tienen desplegable de
    tratamiento (ej. "Fgo. o Lic." / "Fga. o Lic.") en vez de un único
    default fijo — separadas por coma en OpcionesTratamientoMasculino/
    Femenino, marcado por Profesion.TieneMultiplesTratamientos. Lista
    vacía para el resto de las profesiones (default único, sin opciones
    entre las que elegir)."""
    if id_profesion is None:
        return []
    profesion = obtener_repositorio(conn, "Profesion").obtener(id_profesion)
    if profesion is None or not profesion["TieneMultiplesTratamientos"]:
        return []
    columna = "OpcionesTratamientoFemenino" if sexo == "Femenino" else "OpcionesTratamientoMasculino"
    texto = profesion[columna] or ""
    return [o.strip() for o in texto.split(",") if o.strip()]


def normalizar_cuit(texto: str) -> str:
    """Sección 3.4: "CUIT (formato XX-XXXXXXXX-X, almacenado sin
    guiones)" — se tipea con el formato habitual y se guarda limpio."""
    return texto.replace("-", "").replace(" ", "")
