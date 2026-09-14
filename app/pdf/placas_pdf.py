"""PDFs de placas (FA6, sección 3.8): dos documentos independientes.

`generar_pdf_placas` — una fila por posición activa del tablero de cada
unidad, con el nombre grabado: referencia de cómo queda el tablero
completo, se regenera solo en el avance de mes y con nombre de archivo
fijo ("Placas {NombreEspacio}[ - Localidad].pdf", siempre se
sobrescribe, sin historial — igual que Propuesta y Disponibilidad).

`generar_pdf_placas_seleccionadas` — a pedido de la clienta: una hoja
para cortar e imprimir con SOLO las placas que se van juntando en el
buscador de la pantalla de Placas (independiente de qué posición del
tablero ocupen, o si todavía no ocupan ninguna). A diferencia del resto
de los PDFs del sistema (Etapa 7: "página única continua"), éste SÍ
pagina de verdad — se imprime tal cual sobre la plancha física, una
hoja A4 por página — así que arma el documento con `crear_documento` +
`doc.build` en vez de `construir_sin_saltos`.

Medidas de cada placa (modelo físico que pasó la clienta): 7,6 cm x 2,2
cm, margen interno 0,3 cm, texto centrado verticalmente, 2 columnas por
hoja con separación en blanco entre placa y placa (para poder cortarlas
sin que se peguen los bordes). Fuente pedida: Calibri 20pt negrita
itálica — Calibri no es una de las 14 fuentes base de PDF y no está
instalada en este entorno (no se puede registrar sin el archivo .ttf),
así que se usa Helvetica-BoldOblique como reemplazo más parecido
disponible; si la clienta consigue el .ttf de Calibri se puede
registrar para usar la fuente exacta."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.negocio.placas import texto_para_imprimir
from app.pdf.edificios_pdf import edificios_incluidos, sufijo_localidad
from app.pdf.estilos import FUENTE, FUENTE_NEGRITA_ITALICA, construir_sin_saltos, crear_documento, encabezado, encabezado_espacio, estilo_texto
from app.repositorio.registro import obtener_repositorio


def _placas_por_unidad(conn: sqlite3.Connection, ids_edificio: list[int]) -> dict[int, list[sqlite3.Row]]:
    if not ids_edificio:
        return {}
    placeholders = ", ".join("?" for _ in ids_edificio)
    filas = conn.execute(
        f"""
        SELECT p.*, u.Departamento, u.IdEdificio, e.Nombre AS NombreEdificio
        FROM Placa p
        JOIN Unidad u ON u.IdUnidad = p.IdUnidad
        JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE p.Activo = 1 AND u.IdEdificio IN ({placeholders})
        ORDER BY e.Nombre, u.Departamento
        """,
        ids_edificio,
    ).fetchall()
    por_unidad: dict[int, list[sqlite3.Row]] = {}
    for f in filas:
        por_unidad.setdefault(f["IdUnidad"], []).append(f)
    for placas in por_unidad.values():
        placas.sort(key=lambda p: (p["PosicionTablero"] is None, p["PosicionTablero"] or 0))
    return por_unidad


def _tabla_placas(placas: list[sqlite3.Row], ancho: float) -> Table:
    encabezados = [Paragraph("<b>Posición</b>", estilo_texto(9)), Paragraph("<b>Nombre grabado</b>", estilo_texto(9))]
    filas = [encabezados]
    for p in placas:
        posicion = str(p["PosicionTablero"]) if p["PosicionTablero"] is not None else "—"
        nombre = p["NombreGrabado"] or "(sin nombre cargado)"
        if p["EsPersonalizada"]:
            nombre += " (personalizada)"
        filas.append([Paragraph(posicion, estilo_texto(9)), Paragraph(nombre, estilo_texto(9))])

    tabla = Table(filas, colWidths=[ancho * 0.2, ancho * 0.8])
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FUENTE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, "#DDDDDD"),
    ]))
    return tabla


def generar_pdf_placas(conn: sqlite3.Connection, directorio: str, ids_edificio: list[int] | None = None) -> str:
    """Genera el PDF de impresión de placas y devuelve la ruta completa.
    Sin `ids_edificio` incluye todos los edificios del sistema. Unidades
    sin ninguna placa activa no aparecen."""
    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"

    edificios = edificios_incluidos(conn, ids_edificio)
    sufijo = sufijo_localidad(conn, edificios)
    nombre_archivo = f"Placas {nombre_espacio}{sufijo}.pdf"

    ids_edificio_incluidos = [e["IdEdificio"] for e in edificios]
    placas_por_unidad = _placas_por_unidad(conn, ids_edificio_incluidos)
    multi_edificio = len({p[0]["IdEdificio"] for p in placas_por_unidad.values() if p}) > 1

    n_placas = sum(len(p) for p in placas_por_unidad.values())
    altura = (6 * cm + 1.5 * cm + len(placas_por_unidad) * 1.3 * cm + n_placas * 0.7 * cm) * 1.2

    def _construir_story(ancho: float) -> list:
        story = list(encabezado_espacio(conn, ancho))
        story.append(encabezado(1, "Impresión de placas", ancho))
        story.append(Spacer(1, 8))

        if not placas_por_unidad:
            story.append(Paragraph("No hay placas activas cargadas.", estilo_texto(9)))
            return story

        for placas in placas_por_unidad.values():
            primera = placas[0]
            titulo = (
                f"{primera['NombreEdificio']} - {primera['Departamento']}" if multi_edificio
                else primera["Departamento"]
            )
            story.append(encabezado(2, titulo, ancho))
            story.append(Spacer(1, 4))
            story.append(_tabla_placas(placas, ancho))
            story.append(Spacer(1, 10))
        return story

    ruta = os.path.join(directorio, nombre_archivo)
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta


ANCHO_PLACA = 7.6 * cm
ALTO_PLACA = 2.2 * cm
MARGEN_INTERNO_PLACA = 0.3 * cm
GAP_ENTRE_COLUMNAS = 0.6 * cm
GAP_ENTRE_FILAS = 0.2 * cm  # ajustado para que 11 filas (22 placas) entren en una hoja A4 con los márgenes estándar
FUENTE_PLACA = FUENTE_NEGRITA_ITALICA  # reemplazo de Calibri, ver docstring del módulo
TAMANO_FUENTE_PLACA = 20

_ESTILO_PLACA = ParagraphStyle(
    "placa", fontName=FUENTE_PLACA, fontSize=TAMANO_FUENTE_PLACA, leading=TAMANO_FUENTE_PLACA * 1.1,
    alignment=TA_LEFT,
)


def _caja_placa(texto: str) -> Paragraph:
    return Paragraph(texto.replace("\n", "<br/>"), _ESTILO_PLACA)


def _altura_necesaria(parrafo: Paragraph) -> float:
    """Alto real que ocupa el texto de la placa al ancho disponible
    (ANCHO_PLACA menos el margen interno a cada lado) — para que una
    placa con más texto del que entra en ALTO_PLACA a TAMANO_FUENTE_PLACA
    (ej. una personalizada de 2 líneas donde alguna se autoparte por ser
    larga) crezca en vez de recortarse silenciosamente contra el borde."""
    ancho_texto = ANCHO_PLACA - 2 * MARGEN_INTERNO_PLACA
    _ancho_usado, alto = parrafo.wrap(ancho_texto, 1000 * cm)
    return alto + 2 * MARGEN_INTERNO_PLACA


def _fila_de_placas(textos: list[str]) -> Table:
    """Una fila de hasta 2 placas lado a lado, con una columna angosta sin
    contenido ni borde en el medio a modo de separación (para que las
    cajas no queden pegadas). Si la fila tiene una sola placa (cantidad
    impar en la última fila), la segunda columna queda vacía."""
    izquierda = _caja_placa(textos[0])
    derecha = _caja_placa(textos[1]) if len(textos) > 1 else None
    alto_fila = max(ALTO_PLACA, _altura_necesaria(izquierda), _altura_necesaria(derecha) if derecha else 0)

    fila = Table(
        [[izquierda, "", derecha or ""]], colWidths=[ANCHO_PLACA, GAP_ENTRE_COLUMNAS, ANCHO_PLACA],
        rowHeights=[alto_fila],
    )
    estilo = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), MARGEN_INTERNO_PLACA), ("RIGHTPADDING", (0, 0), (-1, -1), MARGEN_INTERNO_PLACA),
        ("TOPPADDING", (0, 0), (-1, -1), MARGEN_INTERNO_PLACA), ("BOTTOMPADDING", (0, 0), (-1, -1), MARGEN_INTERNO_PLACA),
        ("BOX", (0, 0), (0, 0), 0.75, colors.black),
    ]
    if derecha:
        estilo.append(("BOX", (2, 0), (2, 0), 0.75, colors.black))
    fila.setStyle(TableStyle(estilo))
    return fila


def generar_pdf_placas_seleccionadas(conn: sqlite3.Connection, directorio: str, entradas: list[dict]) -> str:
    """Hoja para cortar e imprimir con las placas seleccionadas puntualmente
    en la pantalla de Placas, sin importar si el profesional ya tiene o
    no una posición asignada en algún tablero. Cada entrada de
    `entradas` es {"id_profesional": int, "linea1": str | None,
    "linea2": str | None} — ver `app.negocio.placas.texto_para_imprimir`
    para el criterio de qué texto sale en cada placa. El nombre de
    archivo lleva fecha y hora porque, a diferencia de Propuesta/
    Disponibilidad/el PDF de referencia de Placas, cada tanda de
    impresión es un documento distinto que no reemplaza al anterior."""
    if not entradas:
        raise ValueError("No hay ninguna placa seleccionada para imprimir.")
    repo_profesional = obtener_repositorio(conn, "Profesional")
    textos = []
    for entrada in entradas:
        profesional = repo_profesional.obtener(entrada["id_profesional"])
        if profesional is not None:
            textos.append(texto_para_imprimir(profesional, linea1=entrada.get("linea1"), linea2=entrada.get("linea2")))
    if not textos:
        raise ValueError("Ninguno de los profesionales seleccionados existe.")

    nombre_archivo = datetime.now().strftime("Placas para imprimir %Y-%m-%d %Hh%M.pdf")
    ruta = os.path.join(directorio, nombre_archivo)
    doc, _ancho = crear_documento(ruta)
    story = []
    for i in range(0, len(textos), 2):
        if i:
            story.append(Spacer(1, GAP_ENTRE_FILAS))
        story.append(_fila_de_placas(textos[i:i + 2]))
    doc.build(story)
    return ruta
