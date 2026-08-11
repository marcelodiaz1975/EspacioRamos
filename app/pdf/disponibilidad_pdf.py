"""PDF de Disponibilidad (Etapa 7, sección 4.4). Para profesionales
ACTIVOS: muestra el departamento real (a diferencia de Propuesta, que
anonimiza con "Unidad N" porque va a NO activos). Se sobrescribe al
regenerar — no lleva historial de versiones, así que el nombre de archivo
no incluye más que la fecha.

Secciones: Disponibilidad (grilla + leyenda + notas, sección 4.2) -> Fotos
(con ✔ Apto camilla). La grilla es la misma que se embebe en el PDF de
Liquidación (`app/pdf/grilla_pdf.py`).
"""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib.units import cm
from reportlab.platypus import Spacer

from app.negocio.dias import fecha_actual, parsear_periodo, periodo_actual
from app.pdf.estilos import crear_documento, encabezado
from app.pdf.fotos_pdf import imagenes_de_consultorios, tabla_fotos
from app.pdf.formato import fecha_larga
from app.pdf.grilla_pdf import secciones_disponibilidad


def _edificios_incluidos(conn: sqlite3.Connection, ids_edificio: list[int] | None) -> list[sqlite3.Row]:
    if ids_edificio:
        placeholders = ", ".join("?" for _ in ids_edificio)
        return conn.execute(f"SELECT * FROM Edificio WHERE IdEdificio IN ({placeholders})", ids_edificio).fetchall()
    return conn.execute("SELECT * FROM Edificio").fetchall()


def _ids_consultorio_de_edificios(conn: sqlite3.Connection, ids_edificio: list[int]) -> list[int]:
    if not ids_edificio:
        return []
    placeholders = ", ".join("?" for _ in ids_edificio)
    filas = conn.execute(
        f"SELECT c.IdConsultorio FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
        f"WHERE u.IdEdificio IN ({placeholders})",
        ids_edificio,
    ).fetchall()
    return [f["IdConsultorio"] for f in filas]


def _sufijo_localidad(conn: sqlite3.Connection, edificios: list[sqlite3.Row]) -> str:
    """Sección 4.1: "si hay edificios en más de una localidad" (en TODO el
    sistema, no solo en este PDF) "encabezado muestra la localidad y
    nombre de archivo la incluye al final" — para desambiguar de cuál
    localidad es este PDF en particular."""
    todas = {f["DomicilioLocalidad"] for f in conn.execute("SELECT DomicilioLocalidad FROM Edificio").fetchall()
             if f["DomicilioLocalidad"]}
    if len(todas) <= 1:
        return ""
    localidades_pdf = {e["DomicilioLocalidad"] for e in edificios if e["DomicilioLocalidad"]}
    return f" - {next(iter(localidades_pdf))}" if len(localidades_pdf) == 1 else ""


def generar_pdf_disponibilidad(conn: sqlite3.Connection, directorio: str, ids_edificio: list[int] | None = None) -> str:
    """Genera el PDF de disponibilidad y devuelve la ruta completa. Sin
    `ids_edificio` incluye todos los edificios del sistema."""
    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"

    edificios = _edificios_incluidos(conn, ids_edificio)
    sufijo = _sufijo_localidad(conn, edificios)
    fecha_hoy = fecha_actual(conn)
    fecha_titulo = fecha_larga(fecha_hoy.isoformat()).replace("/", "-")
    nombre_archivo = f"{nombre_espacio} - Disponibilidad al {fecha_titulo}{sufijo}.pdf"

    anio, mes = parsear_periodo(periodo_actual(conn))

    ids_edificio_incluidos = [e["IdEdificio"] for e in edificios]
    ids_consultorio = _ids_consultorio_de_edificios(conn, ids_edificio_incluidos)
    imagenes = imagenes_de_consultorios(conn, ids_consultorio)

    altura = 4 * cm + len(edificios) * (14 * cm) + (len(imagenes) // 2 + 1) * 7 * cm
    ruta = os.path.join(directorio, nombre_archivo)
    doc, ancho = crear_documento(ruta, altura=altura)

    story = [encabezado(1, f"{nombre_espacio} - Disponibilidad al {fecha_titulo}{sufijo}", ancho), Spacer(1, 6)]
    story.extend(secciones_disponibilidad(
        conn, anio, mes, ancho, fecha_titulo, ids_edificio=ids_edificio_incluidos or None,
    ))
    story.append(encabezado(2, "Fotos", ancho))
    story.append(Spacer(1, 4))
    story.extend(tabla_fotos(imagenes, ancho, mostrar_apto_camilla=True))

    doc.build(story)
    return ruta
