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

from typing import Callable

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
COLOR_NIVEL_4 = colors.HexColor("#8A8A8A")

COLOR_VERDE = colors.HexColor("#4CAF50")
COLOR_AMARILLO = colors.HexColor("#F5D547")
COLOR_NARANJA = colors.HexColor("#E07B39")
COLOR_ROJO = colors.HexColor("#C0392B")

MARGEN = 1.5 * cm

_NIVELES = {
    1: {"color": COLOR_NIVEL_1, "alto": 1.1 * cm, "tamano": 11},
    2: {"color": COLOR_NIVEL_2, "alto": 0.55 * cm, "tamano": 9},
    3: {"color": COLOR_NIVEL_3, "alto": 0.46 * cm, "tamano": 8},
    4: {"color": COLOR_NIVEL_4, "alto": 0.4 * cm, "tamano": 7.5},
}


def crear_documento(
    ruta: str, apaisado: bool = False, altura: float | None = None,
) -> tuple[SimpleDocTemplate, float]:
    """SimpleDocTemplate con los márgenes estándar del sistema. Devuelve
    también el ancho útil (para dimensionar tablas de ancho completo).

    `altura`, si se pasa, reemplaza el alto de página estándar — se usa
    para los PDFs de "página única continua" del modelo real (Etapa 7):
    se estima una altura generosa a partir del volumen de datos. Si la
    estimación se queda corta, usar `construir_sin_saltos` en vez de
    `doc.build` directo — ningún PDF del sistema debe salir paginado."""
    ancho_base, alto_base = (A4[1], A4[0]) if apaisado else A4
    tamano = (ancho_base, altura if altura is not None else alto_base)
    doc = SimpleDocTemplate(
        ruta, pagesize=tamano,
        leftMargin=MARGEN, rightMargin=MARGEN, topMargin=MARGEN, bottomMargin=MARGEN,
    )
    ancho_util = tamano[0] - 2 * MARGEN
    return doc, ancho_util


def ancho_util(apaisado: bool = False) -> float:
    """El mismo ancho útil que devuelve `crear_documento`, sin necesidad
    de crear todavía un `SimpleDocTemplate` — no depende de la altura."""
    ancho_base = A4[1] if apaisado else A4[0]
    return ancho_base - 2 * MARGEN


# Límite real del formato PDF: 14400pt (200 in) de lado máximo de página.
# Por encima de esto Acrobat Reader avisa "Las dimensiones de esta página
# superan los límites" (y puede recortar contenido) al abrir el archivo —
# no todos los lectores lo toleran igual de bien, así que nunca hay que
# pedirle a `crear_documento` una altura mayor a esta, aunque el contenido
# no entre en una sola página. Un par de puntos de margen por debajo del
# límite exacto, para no depender de que el lector lo trate como "<=" o
# como "<" ni de redondeos de punto flotante al construir el pagesize.
_ALTURA_MAXIMA_PAGINA = 14398


def construir_sin_saltos(
    ruta: str, construir_story: Callable[[float], list], altura: float, apaisado: bool = False,
    max_intentos: int = 6, factor: float = 1.35,
) -> None:
    """Arma el PDF reintentando con una página más alta si el contenido no
    entró en una sola con la altura estimada — ningún PDF del sistema debe
    salir paginado (Etapa 7: "página única continua") salvo que el
    contenido sea tan largo que ni siquiera entre en el alto máximo válido
    de una página PDF (`_ALTURA_MAXIMA_PAGINA`): ahí se acepta que el
    documento se reparta en páginas de continuación antes que generar un
    PDF fuera de norma. `construir_story(ancho)` arma el story desde cero
    en cada intento: reusar el mismo `story` entre llamadas a `doc.build`
    rompe el conteo interno de reportlab (los flowables no están pensados
    para pasar por dos documentos), así que no alcanza con guardar el
    story una sola vez afuera. El ancho útil no cambia con la altura
    (`crear_documento`), así que da lo mismo en qué intento se calculen
    los anchos de columna."""
    for _ in range(max_intentos):
        altura = min(altura, _ALTURA_MAXIMA_PAGINA)
        doc, ancho = crear_documento(ruta, apaisado=apaisado, altura=altura)
        doc.build(construir_story(ancho))
        if doc.page <= 1 or altura >= _ALTURA_MAXIMA_PAGINA:
            return
        # Saltar directo a una altura proporcional a cuántas páginas hizo
        # falta (no un factor fijo): con `factor` de más margen para que la
        # próxima pasada no se quede corta por el redondeo del reparto de
        # contenido entre páginas.
        altura *= doc.page * factor


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
