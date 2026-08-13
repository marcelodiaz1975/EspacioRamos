"""PDF de Disponibilidad (Etapa 7, sección 4.4). Para profesionales
ACTIVOS: muestra el departamento real (a diferencia de Propuesta, que
anonimiza con "Unidad N" porque va a NO activos). Se sobrescribe al
regenerar — no lleva historial de versiones, así que el nombre de archivo
no incluye más que la fecha.

Mismo criterio que Propuesta (Etapa 7, sección 4.3) en todo lo que
comparten: logo + localidad debajo (`encabezado_espacio`), un archivo por
localidad cuando el espacio tiene edificios en más de una
(`generar_pdfs_disponibilidad_por_localidad`), y con más de un edificio en
el mismo PDF, un nivel 2 "Edificio {Nombre} - {Dirección}, {Localidad}"
por cada uno.

Estructura (2 secciones de nivel 1, sin el resto de Propuesta —
"Detalle de las unidades/consultorios", "Condiciones y forma de reserva" y
"Valores vigentes" quedan afuera; esto es solo para consultar
disponibilidad, no para pesar la decisión de un profesional nuevo):
"Disponibilidad de consultorios al {fecha}" (grilla, sección 4.2, con
piso/departamento real) -> "Fotos de los consultorios" (agrupadas por
unidad real, con valor de la hora regular, sin ✔ Apto camilla). La grilla
es la misma que se embebe en el PDF de Liquidación
(`app/pdf/grilla_pdf.py`).
"""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.negocio.dias import fecha_actual, parsear_periodo, periodo_actual
from app.negocio.formato import fecha_larga
from app.pdf.edificios_pdf import (
    edificios_incluidos,
    hay_multiples_localidades,
    ids_consultorio_de_edificios,
    sufijo_localidad,
    titulo_edificio,
)
from app.pdf.estilos import clave_orden_unidad, construir_sin_saltos, decimales_configurados, encabezado, encabezado_espacio, estilo_texto
from app.pdf.fotos_pdf import imagenes_de_consultorios, tabla_fotos
from app.pdf.grilla_pdf import altura_estimada_grilla, secciones_disponibilidad


def _bloque_fotos_por_unidad(imagenes_edificio: list[sqlite3.Row], ancho: float, nivel: int, decimales: int) -> list:
    if not imagenes_edificio:
        return [Paragraph("Sin fotos cargadas.", estilo_texto(9))]
    por_unidad: dict[int, list] = {}
    for img in imagenes_edificio:
        por_unidad.setdefault(img["IdUnidadConsultorio"], []).append(img)

    story = []
    # Piso ascendente y letra alfabética a igualdad de piso — mismo
    # criterio de orden que la grilla y "Valores vigentes" sin anonimizar.
    for id_unidad in sorted(por_unidad, key=lambda i: clave_orden_unidad(por_unidad[i][0]["Departamento"])):
        imgs = sorted(por_unidad[id_unidad], key=lambda i: i["NumeroConsultorio"])
        story.append(encabezado(nivel, f"Unidad {imgs[0]['Departamento']}", ancho))
        story.append(Spacer(1, 6))
        story.extend(tabla_fotos(imgs, ancho, mostrar_apto_camilla=False, mostrar_valor=True, decimales=decimales))
    return story


def generar_pdf_disponibilidad(conn: sqlite3.Connection, directorio: str, ids_edificio: list[int] | None = None) -> str:
    """Genera el PDF de disponibilidad y devuelve la ruta completa. Sin
    `ids_edificio` incluye todos los edificios del sistema."""
    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"
    decimales = decimales_configurados(conn)

    edificios = edificios_incluidos(conn, ids_edificio)
    multi = len(edificios) > 1
    sufijo = sufijo_localidad(conn, edificios)
    fecha_hoy = fecha_actual(conn)
    fecha_titulo = fecha_larga(fecha_hoy.isoformat()).replace("/", "-")
    nombre_archivo = f"{nombre_espacio} - Disponibilidad al {fecha_titulo}{sufijo}.pdf"

    anio, mes = parsear_periodo(periodo_actual(conn))

    ids_edificio_incluidos = [e["IdEdificio"] for e in edificios]
    ids_consultorio = ids_consultorio_de_edificios(conn, ids_edificio_incluidos)
    imagenes = imagenes_de_consultorios(conn, ids_consultorio)

    mostrar_localidad = hay_multiples_localidades(conn)
    localidades = sorted({e["DomicilioLocalidad"] for e in edificios if e["DomicilioLocalidad"]})
    localidad_texto = " / ".join(localidades) if mostrar_localidad else ""

    n_ed = len(edificios)
    n_unidades_con_fotos = len({(i["NombreEdificio"], i["IdUnidadConsultorio"]) for i in imagenes})
    altura_disponibilidad = altura_estimada_grilla(conn, ids_edificio_incluidos or None)

    altura = (
        6 * cm  # encabezado_espacio (logo + línea)
        + 1.5 * cm + n_ed * 1 * cm  # nivel1 "Disponibilidad..." + wrapper nivel2 por edificio (si multi)
        + altura_disponibilidad  # grillas (ya suma por edificio)
        + 1.5 * cm + n_ed * 1 * cm  # nivel1 "Fotos de los consultorios" + wrapper por edificio
        + (len(imagenes) // 2 + 1) * 7 * cm + n_unidades_con_fotos * 1 * cm  # fotos + encabezado de unidad
    ) * 1.15

    def _construir_story(ancho: float) -> list:
        story = list(encabezado_espacio(
            conn, ancho, mostrar_localidad=mostrar_localidad, localidad=localidad_texto or None,
        ))

        # -------------------------------------------------------- Disponibilidad
        story.append(encabezado(1, f"Disponibilidad de consultorios al {fecha_titulo}", ancho))
        story.append(Spacer(1, 8))
        if multi:
            for e in edificios:
                story.append(encabezado(2, titulo_edificio(e), ancho))
                story.append(Spacer(1, 6))
                story.extend(secciones_disponibilidad(
                    conn, anio, mes, ancho, fecha_titulo, ids_edificio=[e["IdEdificio"]],
                    mostrar_titulo=False, mostrar_encabezado_edificio=False,
                ))
                story.append(Spacer(1, 10))
        else:
            # Con un solo edificio, repetir "Edificio {Nombre}" arriba de
            # la grilla es redundante (no hay otro del que distinguirlo).
            story.extend(secciones_disponibilidad(
                conn, anio, mes, ancho, fecha_titulo, ids_edificio=ids_edificio_incluidos or None,
                mostrar_titulo=False, mostrar_encabezado_edificio=False,
            ))
        story.append(Spacer(1, 10))

        # ----------------------------------------------------------------- Fotos
        story.append(encabezado(1, "Fotos de los consultorios", ancho))
        story.append(Spacer(1, 8))
        if multi:
            for e in edificios:
                imagenes_ed = [i for i in imagenes if i["NombreEdificio"] == e["Nombre"]]
                if not imagenes_ed:
                    continue
                story.append(encabezado(2, titulo_edificio(e), ancho))
                story.append(Spacer(1, 6))
                story.extend(_bloque_fotos_por_unidad(imagenes_ed, ancho, nivel=3, decimales=decimales))
                story.append(Spacer(1, 10))
        else:
            story.extend(_bloque_fotos_por_unidad(imagenes, ancho, nivel=2, decimales=decimales))
        return story

    ruta = os.path.join(directorio, nombre_archivo)
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta


def generar_pdfs_disponibilidad_por_localidad(conn: sqlite3.Connection, directorio: str) -> list[str]:
    """Un PDF de Disponibilidad por cada localidad con edificios cargados:
    nunca mezcla edificios de distintas localidades en el mismo archivo.
    Los edificios sin localidad cargada quedan agrupados aparte, en un
    único archivo sin sufijo de localidad. Devuelve las rutas generadas."""
    filas = conn.execute("SELECT IdEdificio, DomicilioLocalidad FROM Edificio").fetchall()
    grupos: dict[str | None, list[int]] = {}
    for f in filas:
        grupos.setdefault(f["DomicilioLocalidad"], []).append(f["IdEdificio"])
    return [generar_pdf_disponibilidad(conn, directorio, ids_edificio=ids) for ids in grupos.values()]
