"""Historial de búsquedas de Oferta de consultorios (Etapa 9): cada vez que
se genera un PDF o un texto de WhatsApp desde una búsqueda ad-hoc
(`app.negocio.oferta_busqueda`), se guardan los criterios completos que se
usaron para armarla — tipo, alcance, franjas horarias, características
pedidas, exclusiones puntuales — no una foto congelada del resultado. Al
regenerar desde el historial se vuelve a correr `resolver_busqueda` contra
la disponibilidad vigente en ese momento: si mientras tanto se reservó o se
liberó algo, el documento regenerado lo refleja, igual que si se armara la
búsqueda de nuevo desde cero.

Se vacía entero en el avance de mes (Etapa 9, junto con la limpieza de
Archivos varios/Oferta): las búsquedas de meses anteriores ya no tienen
sentido — la propuesta de horarios era para el mes que se está cerrando."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict

from app.negocio.oferta_busqueda import Busqueda, CriteriosGlobales
from app.negocio.oferta_busqueda_texto import nombre_archivo_oferta
from app.negocio.oferta_busqueda_whatsapp import generar_texto_oferta_busqueda
from app.pdf.oferta_busqueda_pdf import generar_pdf_oferta_busqueda
from app.repositorio.registro import obtener_repositorio


def _serializar_criterios(globales: CriteriosGlobales, busquedas: list[Busqueda], excluir: set[tuple[int, int, int]]) -> str:
    return json.dumps({
        "globales": asdict(globales),
        "busquedas": [asdict(b) for b in busquedas],
        "excluir": sorted(excluir) if excluir else [],
    })


def _deserializar_criterios(criterios_json: str) -> tuple[CriteriosGlobales, list[Busqueda], set[tuple[int, int, int]]]:
    data = json.loads(criterios_json)
    globales = CriteriosGlobales(**data["globales"])
    busquedas = [Busqueda(**b) for b in data["busquedas"]]
    excluir = {tuple(t) for t in data.get("excluir", [])}
    return globales, busquedas, excluir


def guardar_busqueda(
    conn: sqlite3.Connection, id_profesional: int, globales: CriteriosGlobales, busquedas: list[Busqueda],
    excluir: set[tuple[int, int, int]], fecha_generacion: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO HistorialOferta (IdProfesional, FechaGeneracion, CriteriosJSON) VALUES (?, ?, ?)",
        (id_profesional, fecha_generacion, _serializar_criterios(globales, busquedas, excluir)),
    )
    conn.commit()
    return cur.lastrowid


def _obtener_historial(conn: sqlite3.Connection, id_historial: int) -> sqlite3.Row:
    fila = obtener_repositorio(conn, "HistorialOferta").obtener(id_historial)
    if fila is None:
        raise ValueError(f"No existe el historial de oferta #{id_historial}")
    return fila


def regenerar_pdf(conn: sqlite3.Connection, id_historial: int, directorio: str) -> str:
    """Vuelve a resolver la búsqueda guardada contra la disponibilidad
    actual y regenera el PDF, devolviendo la ruta completa."""
    fila = _obtener_historial(conn, id_historial)
    globales, busquedas, excluir = _deserializar_criterios(fila["CriteriosJSON"])
    return generar_pdf_oferta_busqueda(conn, directorio, fila["IdProfesional"], globales, busquedas, excluir)


def regenerar_texto(conn: sqlite3.Connection, id_historial: int) -> str:
    """Vuelve a resolver la búsqueda guardada contra la disponibilidad
    actual y devuelve el texto de WhatsApp."""
    fila = _obtener_historial(conn, id_historial)
    globales, busquedas, excluir = _deserializar_criterios(fila["CriteriosJSON"])
    return generar_texto_oferta_busqueda(conn, fila["IdProfesional"], globales, busquedas, excluir)


def nombre_archivo_historial(conn: sqlite3.Connection, id_historial: int) -> str:
    fila = _obtener_historial(conn, id_historial)
    profesional = obtener_repositorio(conn, "Profesional").obtener(fila["IdProfesional"])
    return nombre_archivo_oferta(conn, profesional)


def vaciar_historial(conn: sqlite3.Connection) -> int:
    """Paso del avance de mes: borra todo el historial de búsquedas."""
    cantidad = conn.execute("SELECT COUNT(*) FROM HistorialOferta").fetchone()[0]
    conn.execute("DELETE FROM HistorialOferta")
    conn.commit()
    return cantidad
