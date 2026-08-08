"""Estilos comunes a todos los PDFs del sistema (Etapa 7, sección 4.1).

Fuente Helvetica para todo el documento. Los títulos de sección son barras
de ancho completo ("borde a borde") con fondo de color y texto en negrita
itálica, centrado horizontal y verticalmente — tres niveles de jerarquía,
cada uno con su propio color/alto/tamaño de fuente.
"""
from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

FUENTE = "Helvetica"
FUENTE_NEGRITA = "Helvetica-Bold"
FUENTE_ITALICA = "Helvetica-Oblique"
FUENTE_NEGRITA_ITALICA = "Helvetica-BoldOblique"

COLOR_NIVEL_1 = colors.HexColor("#2E86AB")
COLOR_NIVEL_2 = colors.HexColor("#E07B39")
COLOR_NIVEL_3 = colors.HexColor("#3D3D3D")
COLOR_DIA_GRILLA = colors.HexColor("#6B0000")

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


def crear_documento(ruta: str, apaisado: bool = False) -> tuple[SimpleDocTemplate, float]:
    """SimpleDocTemplate con los márgenes estándar del sistema. Devuelve
    también el ancho útil (para dimensionar tablas de ancho completo)."""
    tamano = (A4[1], A4[0]) if apaisado else A4
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


def formatear_moneda(monto: float) -> str:
    texto = f"{abs(monto):,.2f}"
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-$ {texto}" if monto < 0 else f"$ {texto}"
