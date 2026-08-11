"""PDF de Propuesta al profesional (Etapa 7, sección 4.3). Para
profesionales NO activos (categoría C/contacto, o cualquiera que todavía
no tenga reservas confirmadas): a diferencia del PDF de Disponibilidad,
anonimiza las unidades como "Unidad {IdUnidad}" en vez de mostrar el
Departamento real, para no revelar información interna del edificio a
alguien que todavía no forma parte del espacio.

Secciones (sección 4.3): Detalles principales -> Fotos (2 por fila, con
✔ Apto camilla) -> Disponibilidad -> Condiciones -> Valores vigentes ->
Esquema de descuentos. El documento no detalla el contenido exacto de
"Detalles principales" (remite a versiones v2/v3 no incluidas) — se arma
con los datos de contacto del espacio y del profesional, a falta de un
modelo de referencia como el que sí hay para el PDF de Liquidación.
"""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.negocio.dias import fecha_actual, parsear_periodo, periodo_actual
from app.negocio.formato import fecha_larga
from app.pdf.edificios_pdf import edificios_incluidos, ids_consultorio_de_edificios, sufijo_localidad
from app.pdf.estilos import crear_documento, encabezado, estilo_texto
from app.pdf.fotos_pdf import imagenes_de_consultorios, tabla_fotos
from app.pdf.grilla_pdf import secciones_disponibilidad
from app.pdf.valores_pdf import bloques_esquema_descuentos, condiciones_normas, matriz_valores_edificio
from app.repositorio.registro import obtener_repositorio


def _detalles_principales(conn: sqlite3.Connection, profesional: sqlite3.Row | None, edificios: list, ancho: float) -> list:
    cfg = conn.execute("SELECT * FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    style = estilo_texto(9)
    story = []
    if cfg and (cfg["ContactoCelular"] or cfg["ContactoEmail"]):
        contacto = " / ".join(c for c in (cfg["ContactoCelular"], cfg["ContactoEmail"]) if c)
        story.append(Paragraph(f"<b>Contacto:</b> {contacto}", style))
    if profesional is not None:
        profesion = obtener_repositorio(conn, "Profesion").obtener(profesional["IdProfesion"]) if profesional["IdProfesion"] else None
        if profesion:
            story.append(Paragraph(f"<b>Profesión de interés:</b> {profesion['Nombre']}", style))
    for e in edificios:
        ubicacion = ", ".join(p for p in (e["Domicilio"], e["DomicilioLocalidad"]) if p)
        story.append(Paragraph(f"<b>Edificio {e['Nombre']}:</b> {ubicacion or 'sin domicilio cargado'}", style))
    if not story:
        story.append(Paragraph("Sin datos de contacto cargados en la configuración.", style))
    return story


def generar_pdf_propuesta(
    conn: sqlite3.Connection, directorio: str, id_profesional: int | None = None,
    ids_edificio: list[int] | None = None,
) -> str:
    """Genera el PDF de propuesta y devuelve la ruta completa.
    `id_profesional` personaliza "Detalles principales" (profesión de
    interés) cuando se conoce al contacto; sin él genera una propuesta
    genérica del espacio."""
    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional) if id_profesional else None
    edificios = edificios_incluidos(conn, ids_edificio)
    sufijo = sufijo_localidad(conn, edificios)
    nombre_archivo = f"{nombre_espacio} - Propuesta al profesional{sufijo}.pdf"

    ids_edificio_incluidos = [e["IdEdificio"] for e in edificios]
    ids_consultorio = ids_consultorio_de_edificios(conn, ids_edificio_incluidos)
    imagenes = imagenes_de_consultorios(conn, ids_consultorio)
    anio, mes = parsear_periodo(periodo_actual(conn))
    fecha_titulo = fecha_larga(fecha_actual(conn).isoformat()).replace("/", "-")

    n_condiciones = conn.execute("SELECT COUNT(*) FROM CondicionNorma WHERE Activo = 1").fetchone()[0]
    n_tramos = conn.execute("SELECT COUNT(*) FROM EsquemaDescuentos WHERE Activo = 1").fetchone()[0]
    altura = (
        6 * cm + len(edificios) * 1 * cm
        + (len(imagenes) // 2 + 1) * 7 * cm
        + len(edificios) * 14 * cm
        + n_condiciones * 1.3 * cm
        + len(edificios) * 3 * cm
        + ((n_tramos // 9) + 1) * 1.4 * cm
    ) * 1.15

    ruta = os.path.join(directorio, nombre_archivo)
    doc, ancho = crear_documento(ruta, altura=altura)

    story = [
        Paragraph(nombre_espacio.upper(), estilo_texto(20, negrita=True)),
        Paragraph("Propuesta al profesional", estilo_texto(11)),
        Spacer(1, 10),
    ]

    story.append(encabezado(2, "Detalles principales", ancho))
    story.append(Spacer(1, 4))
    story.extend(_detalles_principales(conn, profesional, edificios, ancho))
    story.append(Spacer(1, 8))

    story.append(encabezado(2, "Fotos", ancho))
    story.append(Spacer(1, 4))
    story.extend(tabla_fotos(imagenes, ancho, mostrar_apto_camilla=True, anonimizar_unidad=True))
    story.append(Spacer(1, 8))

    story.extend(secciones_disponibilidad(
        conn, anio, mes, ancho, fecha_titulo, ids_edificio=ids_edificio_incluidos or None, anonimizar_unidad=True,
    ))

    condiciones = condiciones_normas(conn)
    if condiciones:
        story.append(encabezado(2, "Condiciones", ancho))
        story.append(Spacer(1, 4))
        story.extend(condiciones)
        story.append(Spacer(1, 8))

    story.append(encabezado(2, "Valores vigentes", ancho))
    for e in edificios:
        story.append(encabezado(3, f"Edificio {e['Nombre']}", ancho))
        story.extend(matriz_valores_edificio(conn, e["IdEdificio"], ancho, anonimizar_unidad=True))
        story.append(Spacer(1, 6))

    story.append(encabezado(2, "Esquema de descuentos", ancho))
    story.extend(bloques_esquema_descuentos(conn, ancho))

    doc.build(story)
    return ruta
