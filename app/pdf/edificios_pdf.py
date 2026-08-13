"""Helpers de alcance por edificio, compartidos por los PDFs de
Disponibilidad, Propuesta y Oferta de consultorios."""
from __future__ import annotations

import sqlite3


def edificios_incluidos(conn: sqlite3.Connection, ids_edificio: list[int] | None) -> list[sqlite3.Row]:
    if ids_edificio:
        placeholders = ", ".join("?" for _ in ids_edificio)
        return conn.execute(f"SELECT * FROM Edificio WHERE IdEdificio IN ({placeholders})", ids_edificio).fetchall()
    return conn.execute("SELECT * FROM Edificio").fetchall()


def ids_consultorio_de_edificios(conn: sqlite3.Connection, ids_edificio: list[int]) -> list[int]:
    if not ids_edificio:
        return []
    placeholders = ", ".join("?" for _ in ids_edificio)
    filas = conn.execute(
        f"SELECT c.IdConsultorio FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
        f"WHERE u.IdEdificio IN ({placeholders})",
        ids_edificio,
    ).fetchall()
    return [f["IdConsultorio"] for f in filas]


def numero_unidad_en_edificio(conn: sqlite3.Connection, id_edificio: int) -> dict[int, int]:
    """Posición 1-based de cada unidad dentro de SU edificio, ordenada por
    IdUnidad ascendente: {IdUnidad real -> 1, 2, 3...}. La etiqueta
    anonimizada "Unidad N" de Propuesta (sección 4.3) usa este número
    relativo al edificio, no el IdUnidad real — que es un autoincremental
    global a todo el sistema, así que sin este ajuste el segundo edificio
    de una Propuesta con más de uno arrancaba en "Unidad 5" en vez de
    "Unidad 1"."""
    filas = conn.execute("SELECT IdUnidad FROM Unidad WHERE IdEdificio = ? ORDER BY IdUnidad", (id_edificio,)).fetchall()
    return {f["IdUnidad"]: i + 1 for i, f in enumerate(filas)}


def titulo_edificio(e: sqlite3.Row) -> str:
    """"Edificio {Nombre} - {Domicilio}, {Localidad}" — encabezado nivel 2
    por edificio, compartido por Propuesta y Disponibilidad cuando el PDF
    incluye más de uno."""
    direccion = ", ".join(p for p in (e["Domicilio"], e["DomicilioLocalidad"]) if p)
    return f"Edificio {e['Nombre']} - {direccion}" if direccion else f"Edificio {e['Nombre']}"


def hay_multiples_localidades(conn: sqlite3.Connection) -> bool:
    """Sección 4.1: la localidad debajo del logo y el sufijo de localidad
    en el nombre del archivo solo se muestran "si el espacio tiene
    edificios en más de una localidad" (en TODO el sistema, no solo en
    los edificios de este PDF puntual) — con una sola, aclararla es
    redundante."""
    todas = {f["DomicilioLocalidad"] for f in conn.execute("SELECT DomicilioLocalidad FROM Edificio").fetchall()
             if f["DomicilioLocalidad"]}
    return len(todas) > 1


def sufijo_localidad(conn: sqlite3.Connection, edificios: list[sqlite3.Row]) -> str:
    """" - {Localidad}" para desambiguar de cuál localidad es este PDF en
    particular, cuando corresponde mostrarla (`hay_multiples_localidades`)
    y los edificios de este PDF caen todos en una sola."""
    if not hay_multiples_localidades(conn):
        return ""
    localidades_pdf = {e["DomicilioLocalidad"] for e in edificios if e["DomicilioLocalidad"]}
    return f" - {next(iter(localidades_pdf))}" if len(localidades_pdf) == 1 else ""
