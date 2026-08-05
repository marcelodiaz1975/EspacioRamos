# ═══════════════════════════════════════════════════════════════════════
# SISTEMA ESPACIO RAMOS — Generador PDF Oferta de Consultorios
# Modelo definitivo v1.0
# ═══════════════════════════════════════════════════════════════════════
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus.flowables import Flowable

CELESTE     = colors.HexColor("#2E86AB")
NARANJA     = colors.HexColor("#E07B39")
GRIS_OSCURO = colors.HexColor("#3D3D3D")
BLANCO      = colors.white
GRIS_CLARO  = colors.HexColor("#F5F5F5")
NEGRO       = colors.HexColor("#1A1A1A")
VERDE       = colors.HexColor("#27AE60")

PAGE_W, PAGE_H = A4
MARGEN     = 1.8 * cm
ANCHO_UTIL = PAGE_W - 2 * MARGEN

titulo_st  = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=18,
                            textColor=CELESTE, alignment=TA_CENTER, spaceAfter=4)
subtit_st  = ParagraphStyle("subtit", fontName="Helvetica", fontSize=10,
                            textColor=GRIS_OSCURO, alignment=TA_CENTER, spaceAfter=10)
normal_st  = ParagraphStyle("normal", fontName="Helvetica", fontSize=9,
                            leading=13, textColor=NEGRO)
bold_st    = ParagraphStyle("bold", fontName="Helvetica-Bold", fontSize=9,
                            leading=13, textColor=NEGRO)
valor_st   = ParagraphStyle("valor", fontName="Helvetica-Bold", fontSize=8,
                            textColor=CELESTE, alignment=TA_CENTER)
ph_st      = ParagraphStyle("ph", fontName="Helvetica", fontSize=8,
                            textColor=colors.HexColor("#888888"), alignment=TA_CENTER)


class BarraSeccion(Flowable):
    def __init__(self, texto, nivel=1, ancho=ANCHO_UTIL):
        super().__init__()
        self.texto = texto; self.nivel = nivel; self.ancho = ancho
        if nivel == 1:
            self.alto = 1.1*cm; self.color = CELESTE;     self.fs = 11
        elif nivel == 2:
            self.alto = 0.55*cm; self.color = NARANJA;    self.fs = 9
        else:
            self.alto = 0.46*cm; self.color = GRIS_OSCURO; self.fs = 8

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.rect(0, 0, self.ancho, self.alto, fill=1, stroke=0)
        self.canv.setFillColor(BLANCO)
        self.canv.setFont("Helvetica-BoldOblique", self.fs)
        text_w = self.canv.stringWidth(self.texto, "Helvetica-BoldOblique", self.fs)
        x = (self.ancho - text_w) / 2
        y = (self.alto - self.fs * 0.75) / 2
        self.canv.drawString(x, y, self.texto)

    def wrap(self, aW, aH): return self.ancho, self.alto


def sec(texto, nivel=1):
    return [BarraSeccion(texto, nivel), Spacer(1, 0.25*cm)]


def encabezado(nombre_espacio, subtitulo):
    return [
        Spacer(1, 0.3*cm),
        Paragraph(nombre_espacio.upper(), titulo_st),
        Paragraph(subtitulo, subtit_st),
        HRFlowable(width=ANCHO_UTIL, thickness=1.5, color=CELESTE),
        Spacer(1, 0.4*cm),
    ]


def bloque_consulta(periodo, dias_horarios, caracteristicas):
    story = []
    story += sec(f"Disponibilidad período {periodo}", 1)
    story += sec("Filtros de búsqueda y alternativas disponibles", 2)
    story.append(Paragraph("Días y horarios de interés:", bold_st))
    story.append(Spacer(1, 0.1*cm))
    for dh in dias_horarios:
        story.append(Paragraph(f"* {dh}", normal_st))
    story.append(Spacer(1, 0.2*cm))
    if caracteristicas:
        story.append(Paragraph("Características de consultorio:", bold_st))
        story.append(Spacer(1, 0.1*cm))
        for c in caracteristicas:
            story.append(Paragraph(f"* {c}", normal_st))
        story.append(Spacer(1, 0.2*cm))
    return story


def bloque_alternativas(alternativas):
    story = []
    story.append(Paragraph("Alternativas disponibles:", bold_st))
    story.append(Spacer(1, 0.1*cm))
    for alt in alternativas:
        story.append(Paragraph(f"* {alt}", normal_st))
    story.append(Spacer(1, 0.3*cm))
    return story


def fotos_consultorios(consultorios):
    """
    consultorios: lista de dicts con:
      n, depto, id_unidad, edificio, valor
      es_activo (True=muestra depto real, False=muestra "Unidad N")
      mostrar_edificio (True si hay más de un edificio)
    """
    story = []
    story += sec("Fotos y valores regulares de los consultorios ofrecidos", 2)
    ancho_foto = ANCHO_UTIL/2 - 0.2*cm

    for i in range(0, len(consultorios), 2):
        grupo = consultorios[i:i+2]
        celdas = []
        for c in grupo:
            # Referencia de unidad según tipo de destinatario
            if c.get("es_activo", True):
                ref_unidad = c['depto']
            else:
                ref_unidad = f"Unidad {c['id_unidad']}"

            # Texto de valor con edificio si corresponde
            if c.get("mostrar_edificio"):
                txt_valor = (f"Consultorio {c['n']} del {ref_unidad} - "
                             f"{c['edificio']} — Valor hora regular ${c['valor']}")
            else:
                txt_valor = f"Consultorio {c['n']} del {ref_unidad} — Valor hora regular ${c['valor']}"

            ph_tabla = Table(
                [[Paragraph(f"[ Foto consultorio {c['n']} — {ref_unidad} ]", ph_st)]],
                colWidths=[ancho_foto - 0.4*cm],
                rowHeights=[4.5*cm]
            )
            ph_tabla.setStyle(TableStyle([
                ("BACKGROUND",   (0,0),(-1,-1), GRIS_CLARO),
                ("BOX",          (0,0),(-1,-1), 0.5, colors.HexColor("#CCCCCC")),
                ("ALIGN",        (0,0),(-1,-1), "CENTER"),
                ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
            ]))
            celdas.append([
                ph_tabla,
                Spacer(1, 0.15*cm),
                Paragraph(txt_valor, valor_st),
            ])

        if len(grupo) == 1:
            celdas.append([Paragraph("", ph_st)])

        t = Table([celdas], colWidths=[ancho_foto, ancho_foto])
        t.setStyle(TableStyle([
            ("ALIGN",        (0,0),(-1,-1), "CENTER"),
            ("VALIGN",       (0,0),(-1,-1), "TOP"),
            ("TOPPADDING",   (0,0),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ]))
        story.append(t)

    # Aclaración final
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width=ANCHO_UTIL, thickness=0.5,
                            color=colors.HexColor("#CCCCCC")))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "Aclaración: los valores detallados corresponden a los vigentes a este mes en curso, "
        "y a los mismos luego se le aplican los descuentos en base a la cantidad de horas "
        "regulares que se tenga reservadas.",
        ParagraphStyle("acl_fin", fontName="Helvetica-Oblique", fontSize=8,
                       textColor=GRIS_OSCURO)))
    return story


def generar_oferta(nombre_archivo, nombre_espacio, periodo,
                   dias_horarios, caracteristicas, alternativas,
                   consultorios):
    """
    nombre_archivo: siempre "Oferta consultorios.pdf" — se sobrescribe
    consultorios: lista con es_activo y mostrar_edificio seteados
    """
    story = []
    story += encabezado(nombre_espacio, f"Oferta de consultorios — período {periodo}")
    story += bloque_consulta(periodo, dias_horarios, caracteristicas)
    story += bloque_alternativas(alternativas)
    story += fotos_consultorios(consultorios)

    altura = max(len(story)*0.6*cm + 60*cm, 80*cm)
    doc = SimpleDocTemplate(
        nombre_archivo,
        pagesize=(PAGE_W, altura),
        leftMargin=MARGEN, rightMargin=MARGEN,
        topMargin=MARGEN, bottomMargin=MARGEN
    )
    doc.build(story)
    print(f"Generado: {nombre_archivo}")


# ═══════════════════════════════════════════════════════════════════════════════
# EJEMPLO DE USO — borrar o comentar en producción
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    PERIODO        = "08/2026"
    NOMBRE_ESPACIO = "Espacio Ramos Consultorios"

    DIAS_HORARIOS = [
        "De lunes a viernes entre 8 y 12hs",
        "Jueves entre 16 y 18hs",
        "Viernes a partir de las 18hs",
        "Sábado de 15 a 18hs",
    ]
    CARACTERISTICAS = ["Apto camilla", "Con ventana"]
    ALTERNATIVAS = [
        'Lunes de 9 a 12hs consul 4 del 7mo "L" - Edificio Ramos 1',
        'Miércoles de 8 a 11hs consul 1 del EP "K"',
        'Jueves entre 16 y 18hs: sin disponibilidad',
        'Sábado de 15 a 18hs - combinación de consultorios:',
        '  · de 15 a 17hs consul 6 del 9no "C"',
        '  · de 17 a 18hs consul 2 del 9no "C"',
    ]
    CONSULTORIOS = [
        {"n":4, "depto":'7mo "L"', "id_unidad":1, "edificio":"Ramos 1",
         "valor":"4.646", "es_activo":True, "mostrar_edificio":True},
        {"n":1, "depto":'EP "K"',  "id_unidad":2, "edificio":"Ramos 1",
         "valor":"4.015", "es_activo":True, "mostrar_edificio":True},
        {"n":6, "depto":'9no "C"', "id_unidad":3, "edificio":"Ramos 1",
         "valor":"4.896", "es_activo":True, "mostrar_edificio":True},
    ]

    generar_oferta("Oferta consultorios.pdf", NOMBRE_ESPACIO, PERIODO,
                   DIAS_HORARIOS, CARACTERISTICAS, ALTERNATIVAS, CONSULTORIOS)
