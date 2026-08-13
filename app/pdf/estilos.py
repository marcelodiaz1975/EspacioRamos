"""Estilos comunes a todos los PDFs del sistema (Etapa 7, sección 4.1).

Fuente Helvetica para todo el documento. Los títulos de sección son barras
de ancho completo ("borde a borde") con fondo de color y texto en negrita
itálica, centrado horizontal y verticalmente — tres niveles de jerarquía,
cada uno con su propio color/alto/tamaño de fuente.
"""
from __future__ import annotations

import os
import re
import sqlite3

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Flowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FUENTE = "Helvetica"
FUENTE_NEGRITA = "Helvetica-Bold"
FUENTE_ITALICA = "Helvetica-Oblique"
FUENTE_NEGRITA_ITALICA = "Helvetica-BoldOblique"

COLOR_NIVEL_1 = colors.HexColor("#2E86AB")
COLOR_NIVEL_2 = colors.HexColor("#E07B39")
COLOR_NIVEL_3 = colors.HexColor("#3D3D3D")

COLOR_VERDE = colors.HexColor("#4CAF50")
COLOR_AMARILLO = colors.HexColor("#F5D547")
COLOR_NARANJA = colors.HexColor("#E07B39")
COLOR_ROJO = colors.HexColor("#C0392B")

MARGEN = 1.5 * cm

_NIVELES = {
    1: {"color": COLOR_NIVEL_1, "alto": 1.1 * cm, "tamano": 11},
    2: {"color": COLOR_NIVEL_2, "alto": 0.55 * cm, "tamano": 9},
    3: {"color": COLOR_NIVEL_3, "alto": 0.46 * cm, "tamano": 8},
}


def crear_documento(
    ruta: str, apaisado: bool = False, altura: float | None = None,
) -> tuple[SimpleDocTemplate, float]:
    """SimpleDocTemplate con los márgenes estándar del sistema. Devuelve
    también el ancho útil (para dimensionar tablas de ancho completo).

    `altura`, si se pasa, reemplaza el alto de página estándar — se usa
    para los PDFs de "página única continua" del modelo real (Etapa 7):
    se estima una altura generosa a partir del volumen de datos y, si la
    estimación se queda corta, SimpleDocTemplate sigue funcionando bien:
    agrega páginas de continuación del mismo tamaño en vez de fallar."""
    ancho_base, alto_base = (A4[1], A4[0]) if apaisado else A4
    tamano = (ancho_base, altura if altura is not None else alto_base)
    doc = SimpleDocTemplate(
        ruta, pagesize=tamano,
        leftMargin=MARGEN, rightMargin=MARGEN, topMargin=MARGEN, bottomMargin=MARGEN,
    )
    ancho_util = tamano[0] - 2 * MARGEN
    return doc, ancho_util


def encabezado(nivel: int, texto: str, ancho: float) -> Table:
    """Barra de título de ancho completo para nivel 1/2/3 (sección 4.1).
    Fondo de color, texto negrita itálica centrado H y V."""
    spec = _NIVELES[nivel]
    tabla = Table([[texto]], colWidths=[ancho], rowHeights=[spec["alto"]])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), spec["color"]),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), FUENTE_NEGRITA_ITALICA),
        ("FONTSIZE", (0, 0), (-1, -1), spec["tamano"]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tabla


def estilo_texto(tamano: int = 9, negrita: bool = False, italica: bool = False, **kwargs) -> ParagraphStyle:
    if negrita and italica:
        fuente = FUENTE_NEGRITA_ITALICA
    elif negrita:
        fuente = FUENTE_NEGRITA
    elif italica:
        fuente = FUENTE_ITALICA
    else:
        fuente = FUENTE
    return ParagraphStyle(name="texto", fontName=fuente, fontSize=tamano, leading=tamano * 1.25, **kwargs)


def decimales_configurados(conn) -> int:
    """`Configuracion.CantidadDecimales` (default 2) — parámetro que el
    usuario puede ajustar desde Configuración general sin tocar código."""
    fila = conn.execute("SELECT CantidadDecimales FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    return int(fila["CantidadDecimales"]) if fila and fila["CantidadDecimales"] is not None else 2


def formatear_moneda(monto: float, decimales: int = 2) -> str:
    texto = f"{abs(monto):,.{decimales}f}"
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-$ {texto}" if monto < 0 else f"$ {texto}"


def partir_etiqueta_unidad(etiqueta: str) -> tuple[str, str]:
    """'7mo "L"' -> ('7', 'L'); 'EP "K"' -> ('EP', 'K'); '15 "H"' -> ('15', 'H').
    Arriba va solo el número de piso (sin el sufijo ordinal "mo"/"ro"/"no"
    si lo tiene; si el piso no es numérico, ej. "EP"/"PB", se deja tal
    cual). Abajo va la letra del departamento sin comillas. Si la etiqueta
    no sigue este patrón (dato cargado distinto), se deja completa arriba
    y nada abajo, en vez de romper. Compartido por la grilla (piso/letra
    en celdas separadas) y "Valores de los consultorios" (orden por piso)."""
    m = re.match(r'^(\S+)\s+"([^"]+)"$', etiqueta)
    if not m:
        return etiqueta, ""
    prefijo, sufijo = m.groups()
    numero = re.match(r"^(\d+)", prefijo)
    arriba = numero.group(1) if numero else prefijo
    return arriba, sufijo


def clave_orden_unidad(etiqueta: str) -> tuple[float, str]:
    """Orden pedido para listar unidades: piso ascendente y, a igualdad de
    piso, la letra del departamento alfabéticamente — los pisos no
    numéricos (ej. "EP"/"PB") valen 0 y quedan primero. Usado tanto en
    "Valores de los consultorios" como en las grillas de disponibilidad
    (girada o no) para que las dos secciones ordenen igual."""
    piso, letra = partir_etiqueta_unidad(etiqueta)
    piso_num = float(piso) if piso.isdigit() else 0.0
    return piso_num, letra


class LineaSeparadora(Flowable):
    """Línea horizontal simple, para separar el encabezado del resto del
    documento (compartida por todos los PDFs del sistema)."""

    def __init__(self, ancho: float, grosor: float = 1.2, color=None):
        super().__init__()
        self.ancho, self.grosor, self.color = ancho, grosor, color or COLOR_NIVEL_1

    def wrap(self, availWidth, availHeight):
        return self.ancho, self.grosor + 4

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.grosor)
        self.canv.line(0, 2, self.ancho, 2)


def encabezado_espacio(
    conn: sqlite3.Connection, ancho: float, *, mostrar_localidad: bool = False, localidad: str | None = None,
) -> list:
    """Encabezado común a los PDFs del sistema: logo centrado (si hay uno
    configurado en `Configuracion.RutaLogo` y el archivo existe — si no,
    se cae al nombre del espacio en texto, igual que con las fotos de
    consultorio que no están cargadas todavía), localidad debajo cuando
    corresponde, y la línea separatoria.

    `mostrar_localidad` lo decide cada PDF: en Liquidación no se muestra
    (un profesional puede tener reservas en edificios de más de una
    localidad, no hay una sola localidad "de este documento"); en
    Disponibilidad/Propuesta sí, porque esos PDFs ya se generan un
    archivo distinto por localidad cuando el espacio abarca más de una."""
    cfg = conn.execute("SELECT NombreEspacio, RutaLogo FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = ((cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos").upper()
    ruta_logo = cfg["RutaLogo"] if cfg else None

    story = []
    if ruta_logo and os.path.isfile(ruta_logo):
        logo = Image(ruta_logo, width=ancho, height=5 * cm, kind="proportional")
        logo.hAlign = "CENTER"
        story.append(logo)
    else:
        story.append(Paragraph(nombre_espacio, estilo_texto(20, negrita=True, alignment=TA_CENTER)))

    if mostrar_localidad and localidad:
        story.append(Paragraph(localidad, estilo_texto(10, alignment=TA_CENTER)))

    story.append(Spacer(1, 4))
    story.append(LineaSeparadora(ancho))
    story.append(Spacer(1, 10))
    return story
