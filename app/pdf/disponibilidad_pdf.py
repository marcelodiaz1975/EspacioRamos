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
from app.pdf.edificios_pdf import edificios_incluidos, ids_consultorio_de_edificios, sufijo_localidad
from app.pdf.estilos import crear_documento, encabezado
from app.pdf.fotos_pdf import imagenes_de_consultorios, tabla_fotos
from app.pdf.formato import fecha_larga
from app.pdf.grilla_pdf import secciones_disponibilidad


def generar_pdf_disponibilidad(conn: sqlite3.Connection, directorio: str, ids_edificio: list[int] | None = None) -> str:
    """Genera el PDF de disponibilidad y devuelve la ruta completa. Sin
    `ids_edificio` incluye todos los edificios del sistema."""
    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"

    edificios = edificios_incluidos(conn, ids_edificio)
    sufijo = sufijo_localidad(conn, edificios)
    fecha_hoy = fecha_actual(conn)
    fecha_titulo = fecha_larga(fecha_hoy.isoformat()).replace("/", "-")
    nombre_archivo = f"{nombre_espacio} - Disponibilidad al {fecha_titulo}{sufijo}.pdf"

    anio, mes = parsear_periodo(periodo_actual(conn))

    ids_edificio_incluidos = [e["IdEdificio"] for e in edificios]
    ids_consultorio = ids_consultorio_de_edificios(conn, ids_edificio_incluidos)
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
