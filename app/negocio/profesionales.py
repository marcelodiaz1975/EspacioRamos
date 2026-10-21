"""Reglas del legajo de Profesional (sección 3.4) que no encajan en el
CRUD genérico: sugerencia de código y pre-completado de tratamiento."""
from __future__ import annotations

import sqlite3

from app.repositorio.registro import obtener_repositorio


def _numeros_usados(conn: sqlite3.Connection, categoria: str) -> set[int]:
    usados = set()
    for fila in obtener_repositorio(conn, "Profesional").listar(CategoriaProfesional=categoria):
        codigo = (fila["IdCodigo"] or "").strip()
        resto = codigo[len(categoria):] if codigo.startswith(categoria) else ""
        if resto.isdigit():
            usados.add(int(resto))
    return usados


def sugerir_codigo(conn: sqlite3.Connection, categoria: str) -> str:
    """Prefijo letra (la categoría) + número más bajo todavía no usado en
    esa categoría (sección 3.4: "prefijo letra + número más bajo
    disponible en la categoría"). Pedido explícito de la clienta (ronda
    de validaciones de categoría): el código deja de ser "un punto de
    partida editable" — ahora es lo que determina el código real del
    profesional, de forma automática y de solo lectura, cada vez que se
    fija o cambia su Categoría (ver `app.gui.pantallas.profesionales.
    _al_abrir_dialogo`)."""
    return sugerir_codigos_multiples(conn, categoria, 1)[0]


def sugerir_codigos_multiples(conn: sqlite3.Connection, categoria: str, cantidad: int) -> list[str]:
    """Varios códigos sugeridos de la misma categoría EN UNA SOLA
    PASADA, sin tocar la base — pensado para el alerta que lista, de una,
    el código X que le tocaría a cada profesional E que hay que
    desvincular antes de poder cambiarle la categoría a su cabeza de
    equipo (ver `app.gui.pantallas.profesionales._al_guardar_profesional`):
    llamar a `sugerir_codigo` una vez por cada uno devolvería el MISMO
    número para todos (ninguno está guardado todavía como para que el
    siguiente cálculo lo vea como "usado"). Devuelve los `cantidad`
    números más bajos libres, en orden, simulando que cada uno ya se
    ocupó antes de buscar el siguiente."""
    usados = _numeros_usados(conn, categoria)
    sugeridos = []
    numero = 1
    while len(sugeridos) < cantidad:
        if numero not in usados:
            sugeridos.append(f"{categoria}{numero}")
            usados.add(numero)
        numero += 1
    return sugeridos


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
