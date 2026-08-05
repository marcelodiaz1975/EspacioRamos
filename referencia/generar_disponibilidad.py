# ═══════════════════════════════════════════════════════════════════════
# SISTEMA ESPACIO RAMOS — Generador PDF Disponibilidad
# Modelo definitivo v1.0
# Para profesionales ACTIVOS — muestra departamento real
# Nombre archivo: "{NombreEspacio} - Disponibilidad al {dd-mm-aaaa}.pdf"
# Sobrescribe el archivo anterior al regenerar
# ═══════════════════════════════════════════════════════════════════════
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus.flowables import Flowable
from datetime import date as date_cls
import re as _re

# ── Colores ───────────────────────────────────────────────────────────────────
CELESTE      = colors.HexColor("#2E86AB")
NARANJA      = colors.HexColor("#E07B39")
GRIS_OSCURO  = colors.HexColor("#3D3D3D")
BLANCO       = colors.white
GRIS_CLARO   = colors.HexColor("#F5F5F5")
NEGRO        = colors.HexColor("#1A1A1A")
VERDE_DISP   = colors.HexColor("#27AE60")
AMARILLO_DISP= colors.HexColor("#F1C40F")
NARANJA_DISP = colors.HexColor("#E67E22")
ROJO_DISP    = colors.HexColor("#E74C3C")
BORDO        = colors.HexColor("#6B0000")
VERDE_CAMILLA= colors.HexColor("#27AE60")

PAGE_W, PAGE_H = A4
MARGEN     = 1.8 * cm
ANCHO_UTIL = PAGE_W - 2 * MARGEN

# ── Estilos ───────────────────────────────────────────────────────────────────
titulo_st = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=18,
                           textColor=CELESTE, alignment=TA_CENTER, spaceAfter=4)
subtit_st = ParagraphStyle("subtit", fontName="Helvetica", fontSize=10,
                           textColor=GRIS_OSCURO, alignment=TA_CENTER, spaceAfter=10)
ph_st     = ParagraphStyle("ph", fontName="Helvetica", fontSize=8,
                           textColor=colors.HexColor("#888888"), alignment=TA_CENTER)
cam_st    = ParagraphStyle("cam", fontName="Helvetica-BoldOblique", fontSize=7.5,
                           textColor=VERDE_CAMILLA, alignment=TA_CENTER)


# ── Barra de sección ──────────────────────────────────────────────────────────
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
        tw = self.canv.stringWidth(self.texto, "Helvetica-BoldOblique", self.fs)
        x = (self.ancho - tw) / 2
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


# ── Parámetros de grilla (en producción vienen de Configuracion) ──────────────
HORA_INI  = 8
HORA_FIN  = 22
DIAS_SEM  = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
BLOQ_RIG  = [(9, 11), (18, 21)]   # lógica real
UMBRAL    = 8                      # umbral de giro


def tipo_b(h):
    for a, b in BLOQ_RIG:
        if a <= h < b: return "Rígido"
    return "Flexible"


def cambio_tipo(h):
    t = tipo_b(h)
    t2 = tipo_b(h - 1) if h > HORA_INI else None
    return t2 is not None and t2 != t


def etiq_d(depto, dos=False):
    """Etiqueta compacta de departamento para grilla normal con >4 unidades."""
    if not dos: return depto
    p = depto.rsplit(" ", 1)
    if len(p) == 2:
        piso  = _re.sub(r'(mo|to|vo|ro|no|do)$', '', p[0], flags=_re.IGNORECASE)
        letra = p[1].replace('"', '').strip()
        return f"{piso}\n{letra}"
    return depto


def grilla_disponibilidad(unidades_info, estados_grilla=None):
    """
    unidades_info: lista de tuplas (uid, cant_consultorios, departamento)
    estados_grilla: dict opcional {(uid, dia_idx, hora): color_constante}
                    Si None se usan datos de ejemplo aleatorios.
    Colores válidos: VERDE_DISP, AMARILLO_DISP, NARANJA_DISP, ROJO_DISP
    """
    import random; random.seed(42)
    horas   = list(range(HORA_INI, HORA_FIN))
    n_u     = len(unidades_info)
    n_d     = len(DIAS_SEM)
    LF=0.4; LG=1.8; LM=1.0
    dos = n_u > 4

    def color_celda(uid, dia_idx, h):
        if estados_grilla and (uid, dia_idx, h) in estados_grilla:
            return estados_grilla[(uid, dia_idx, h)]
        # Datos de ejemplo
        e = random.choice(["libre","libre","libre","solo_ventana","solo_sin_ventana","ocupado"])
        if e == "ocupado":       return ROJO_DISP
        if e == "solo_ventana":  return AMARILLO_DISP
        if e == "solo_sin_ventana": return NARANJA_DISP
        return VERDE_DISP

    # ── Grilla girada (>UMBRAL unidades) ─────────────────────────────────────
    if n_u > UMBRAL:
        aw = 1.8*cm; uw = 2.0*cm
        cw_ = [aw, uw] + [(ANCHO_UTIL - aw - uw) / len(horas)] * len(horas)
        h0  = ["Tipo de\nbloque →", ""] + [tipo_b(h) for h in horas]
        h1  = ["Día", "Unidad"] + [f"{h}hs" for h in horas]
        data = [h0, h1]; cc = []; ri = 2
        for ci_d, dia in enumerate(DIAS_SEM):
            for uid, cant, dep in unidades_info:
                fila = [dia.upper(), dep]
                for ci_h, h in enumerate(horas):
                    fila.append("")
                    cc.append((2 + ci_h, ri, color_celda(uid, ci_d, h)))
                data.append(fila); ri += 1

        est = [
            ("BACKGROUND",(0,0),(-1,1),CELESTE),("TEXTCOLOR",(0,0),(-1,1),BLANCO),
            ("FONTNAME",(0,0),(-1,1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,1),6),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("FONTNAME",(0,2),(-1,-1),"Helvetica"),("FONTSIZE",(0,2),(-1,-1),6),
            ("BACKGROUND",(0,2),(0,-1),CELESTE),("TEXTCOLOR",(0,2),(0,-1),BLANCO),
            ("FONTNAME",(0,2),(0,-1),"Helvetica-Bold"),
            ("BACKGROUND",(1,2),(1,-1),colors.HexColor("#AED6F1")),
            ("TEXTCOLOR",(1,2),(1,-1),NEGRO),("FONTNAME",(1,2),(1,-1),"Helvetica-Bold"),
            ("BACKGROUND",(2,2),(-1,-1),GRIS_CLARO),
            ("GRID",(0,0),(-1,-1),LF,colors.HexColor("#CCCCCC")),
            ("BOX",(0,0),(-1,-1),LG,NEGRO),
            ("LINEBELOW",(0,0),(-1,0),LG,NEGRO),("LINEBELOW",(0,1),(-1,1),LG,NEGRO),
            ("LINEAFTER",(0,0),(0,-1),LG,NEGRO),("LINEAFTER",(1,0),(1,-1),LG,NEGRO),
            ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ]
        # Span de tipo de bloque en header
        i = 2
        while i < len(h0):
            j = i
            while j < len(h0) and h0[j] == h0[i]: j += 1
            if j - i > 1: est.append(("SPAN",(i,0),(j-1,0)))
            i = j
        # Span de días
        for ci_d in range(n_d):
            r0 = 2 + ci_d * n_u; r1 = r0 + n_u - 1
            if n_u > 1: est.append(("SPAN",(0,r0),(0,r1)))
            if ci_d < n_d - 1: est.append(("LINEBELOW",(0,r1),(-1,r1),LM,NEGRO))
        est.append(("SPAN",(0,0),(1,0)))
        # Líneas de cambio de tipo de bloque
        for ci_h, h in enumerate(horas[1:], start=1):
            if cambio_tipo(h): est.append(("LINEBEFORE",(2+ci_h,0),(2+ci_h,-1),LM,NEGRO))
        for col, row, c in cc: est.append(("BACKGROUND",(col,row),(col,row),c))
        t = Table(data, colWidths=cw_, repeatRows=2)
        t.setStyle(TableStyle(est))
        return [t]

    # ── Grilla normal (≤UMBRAL unidades) ─────────────────────────────────────
    tw = 1.3*cm; hw = 1.1*cm
    cw_ = [tw, hw] + [(ANCHO_UTIL - tw - hw) / (n_d * n_u)] * (n_d * n_u)

    h0 = ["Tipo\nBloque", "Horario"]
    for d in DIAS_SEM:
        h0.append(d.upper())
        h0 += [""] * (n_u - 1)

    h1 = ["", ""]
    for d in DIAS_SEM:
        h1.append("Unidad")
        h1 += [""] * (n_u - 1)

    h2 = ["", ""]
    for d in DIAS_SEM:
        for uid, cant, dep in unidades_info:
            h2.append(etiq_d(dep, dos))

    rows = []; cc = []
    for ri, h in enumerate(horas, start=3):
        fila = [tipo_b(h), f"{h}hs"]
        for ci_d in range(n_d):
            for ci_u, (uid, cant, dep) in enumerate(unidades_info):
                fila.append("")
                col = 2 + ci_d * n_u + ci_u
                cc.append((col, ri, color_celda(uid, ci_d, h)))
        rows.append(fila)

    data = [h0, h1, h2] + rows
    est = [
        ("BACKGROUND",(0,0),(-1,2),CELESTE),("TEXTCOLOR",(0,0),(-1,2),BLANCO),
        ("FONTNAME",(0,0),(-1,2),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,2),6),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("BACKGROUND",(2,0),(-1,0),BORDO),("TEXTCOLOR",(2,0),(-1,0),BLANCO),
        ("FONTNAME",(2,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(2,0),(-1,0),6.5),
        ("FONTNAME",(0,3),(-1,-1),"Helvetica"),("FONTSIZE",(0,3),(-1,-1),6.5),
        ("BACKGROUND",(0,3),(1,-1),GRIS_CLARO),
        ("GRID",(0,0),(-1,-1),LF,colors.HexColor("#CCCCCC")),
        ("BOX",(0,0),(-1,-1),LG,NEGRO),
        ("LINEBELOW",(0,2),(-1,2),LG,NEGRO),
        ("LINEAFTER",(1,0),(1,-1),LG,NEGRO),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
    ]
    est.append(("SPAN",(0,0),(0,2))); est.append(("SPAN",(1,0),(1,2)))
    for ci_d, d in enumerate(DIAS_SEM):
        c0 = 2 + ci_d * n_u; c1 = c0 + n_u - 1
        if n_u > 1:
            est.append(("SPAN",(c0,0),(c1,0)))
            est.append(("SPAN",(c0,1),(c1,1)))
        if ci_d < n_d - 1: est.append(("LINEAFTER",(c1,0),(c1,-1),LG,NEGRO))
    # Span de tipo de bloque en col 0
    i = 3
    while i < len(data):
        j = i
        while j < len(data) and data[j][0] == data[i][0]: j += 1
        if j - i > 1: est.append(("SPAN",(0,i),(0,j-1)))
        i = j
    for ri, h in enumerate(horas, start=3):
        if cambio_tipo(h): est.append(("LINEABOVE",(0,ri),(-1,ri),LM,NEGRO))
    for col, row, c in cc: est.append(("BACKGROUND",(col,row),(col,row),c))
    t = Table(data, colWidths=cw_, repeatRows=3)
    t.setStyle(TableStyle(est))
    return [t]


def leyenda():
    CW = 0.65*cm; TW = ANCHO_UTIL / 2 - CW - 0.15*cm
    items = [
        (VERDE_DISP,    "Hay al menos dos consultorios disponibles"),
        (AMARILLO_DISP, "Solo un consultorio disponible con ventana"),
        (NARANJA_DISP,  "Solo un consultorio disponible sin ventana"),
        (ROJO_DISP,     "Sin consultorios disponibles"),
    ]
    def p(t): return Paragraph(t, ParagraphStyle("l", fontName="Helvetica",
                               fontSize=7.5, leading=10, textColor=NEGRO))
    data = [
        ["", p(items[0][1]), "", p(items[1][1])],
        ["", p(items[2][1]), "", p(items[3][1])],
    ]
    t = Table(data, colWidths=[CW, TW, CW, TW])
    e = [
        ("ALIGN",(0,0),(0,-1),"CENTER"),("ALIGN",(2,0),(2,-1),"CENTER"),
        ("FONTSIZE",(0,0),(0,-1),6.5),("FONTSIZE",(2,0),(2,-1),6.5),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
        ("BOX",(0,0),(0,0),1.0,NEGRO),("BOX",(2,0),(2,0),1.0,NEGRO),
        ("BOX",(0,1),(0,1),1.0,NEGRO),("BOX",(2,1),(2,1),1.0,NEGRO),
        ("BACKGROUND",(0,0),(0,0),VERDE_DISP),
        ("BACKGROUND",(2,0),(2,0),AMARILLO_DISP),
        ("BACKGROUND",(0,1),(0,1),NARANJA_DISP),
        ("BACKGROUND",(2,1),(2,1),ROJO_DISP),
    ]
    t.setStyle(TableStyle(e))
    ns = ParagraphStyle("ns", fontName="Helvetica-BoldOblique", fontSize=6.2,
                        textColor=GRIS_OSCURO, spaceBefore=3, leading=9)
    contenedor = Table(
        [[t],
         [Paragraph("Horarios rígidos: son bloques de horas consecutivas que se deben "
                    "reservar sí o sí todas juntas, estos bloques no se fraccionan.", ns)],
         [Paragraph("Horarios flexibles: las horas comprendidas dentro de estos bloques "
                    "se pueden reservar sin restricción y sin mínimo alguno.", ns)]],
        colWidths=[ANCHO_UTIL])
    contenedor.setStyle(TableStyle([
        ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
    ]))
    return contenedor


def fotos_unidad(consultorios, notas_adicionales=None):
    """
    consultorios: lista de dicts con n, departamento, apto_camilla, ruta_foto (opcional)
    Se muestran en grilla de 2 columnas con ✔ Apto camilla si aplica.
    """
    story = []
    ancho_foto = ANCHO_UTIL / 2 - 0.2*cm
    val_st = ParagraphStyle("vf", fontName="Helvetica-Bold", fontSize=8,
                            textColor=NEGRO, alignment=TA_CENTER)

    for i in range(0, len(consultorios), 2):
        grupo = consultorios[i:i+2]
        celdas = []
        for c in grupo:
            ph_tabla = Table(
                [[Paragraph(f"[ Foto consultorio {c['n']} — {c['departamento']} ]", ph_st)]],
                colWidths=[ancho_foto - 0.4*cm],
                rowHeights=[4.5*cm]
            )
            ph_tabla.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,-1),GRIS_CLARO),
                ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#CCCCCC")),
                ("ALIGN",(0,0),(-1,-1),"CENTER"),
                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ]))
            lineas = [
                ph_tabla,
                Spacer(1, 0.15*cm),
                Paragraph(f"Consultorio {c['n']} — {c['departamento']}", val_st),
            ]
            if c.get("apto_camilla"):
                lineas.append(Paragraph("✔ Apto camilla", cam_st))
            celdas.append(lineas)

        if len(grupo) == 1:
            celdas.append([Paragraph("", ph_st)])

        t = Table([celdas], colWidths=[ancho_foto, ancho_foto])
        t.setStyle(TableStyle([
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("TOPPADDING",(0,0),(-1,-1),4),
            ("BOTTOMPADDING",(0,0),(-1,-1),10),
        ]))
        story.append(t)

    if notas_adicionales:
        nota_st = ParagraphStyle("nota", fontName="Helvetica-Oblique", fontSize=8,
                                 textColor=GRIS_OSCURO, spaceBefore=6)
        for nota in notas_adicionales:
            story.append(Paragraph(f"* {nota}", nota_st))
    return story


def generar_disponibilidad(
        nombre_espacio, unidades_info, consultorios_fotos,
        estados_grilla=None, notas_grilla=None, notas_fotos=None,
        localidad=None):
    """
    nombre_espacio: str
    unidades_info: lista de (uid, cant_consultorios, departamento)
    consultorios_fotos: lista de dicts {n, departamento, apto_camilla}
    estados_grilla: dict {(uid, dia_idx, hora): COLOR} — None = datos de ejemplo
    notas_grilla: lista de strings para mostrar debajo de la leyenda
    notas_fotos: lista de strings para mostrar debajo de las fotos
    localidad: str — si hay varias localidades se incluye en nombre y encabezado
    """
    fecha_hoy = date_cls.today().strftime("%d-%m-%Y")
    suf_loc   = f" - {localidad}" if localidad else ""
    nombre_archivo = f"{nombre_espacio} - Disponibilidad al {fecha_hoy}{suf_loc}.pdf"
    subtitulo = f"Disponibilidad al {fecha_hoy}"
    if localidad:
        subtitulo += f" — {localidad}"

    story = []
    story += encabezado(nombre_espacio, subtitulo)

    # Sección disponibilidad
    story += sec(f"Disponibilidad de consultorios al {fecha_hoy}", 1)
    story += grilla_disponibilidad(unidades_info, estados_grilla)
    story.append(Spacer(1, 0.25*cm))
    story.append(leyenda())

    if notas_grilla:
        nota_st = ParagraphStyle("ng", fontName="Helvetica-Oblique", fontSize=8,
                                 textColor=GRIS_OSCURO, spaceBefore=4, leading=11)
        story.append(Spacer(1, 0.2*cm))
        for nota in notas_grilla:
            story.append(Paragraph(f"* {nota}", nota_st))
    story.append(Spacer(1, 0.4*cm))

    # Sección fotos
    story += sec("Fotos de los consultorios", 1)
    story += fotos_unidad(consultorios_fotos, notas_fotos)

    altura = max(len(story) * 0.6*cm + 40*cm, 60*cm)
    doc = SimpleDocTemplate(
        nombre_archivo,
        pagesize=(PAGE_W, altura),
        leftMargin=MARGEN, rightMargin=MARGEN,
        topMargin=MARGEN, bottomMargin=MARGEN
    )
    doc.build(story)
    print(f"Generado: {nombre_archivo}")
    return nombre_archivo


# ═══════════════════════════════════════════════════════════════════════════════
# EJEMPLO DE USO — borrar o comentar en producción
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    NOMBRE_ESPACIO = "Espacio Ramos Consultorios"

    UNIDADES = [
        (1, 7, '7mo "L"'),
        (2, 4, 'EP "K"'),
        (3, 4, '9no "C"'),
    ]

    CONSULTORIOS = [
        {"n":1, "departamento":'7mo "L"', "apto_camilla": False},
        {"n":2, "departamento":'7mo "L"', "apto_camilla": True},
        {"n":3, "departamento":'7mo "L"', "apto_camilla": True},
        {"n":4, "departamento":'7mo "L"', "apto_camilla": False},
        {"n":5, "departamento":'7mo "L"', "apto_camilla": True},
        {"n":6, "departamento":'7mo "L"', "apto_camilla": False},
        {"n":7, "departamento":'7mo "L"', "apto_camilla": False},
        {"n":1, "departamento":'EP "K"',  "apto_camilla": True},
        {"n":2, "departamento":'EP "K"',  "apto_camilla": True},
        {"n":3, "departamento":'EP "K"',  "apto_camilla": False},
        {"n":4, "departamento":'EP "K"',  "apto_camilla": False},
        {"n":1, "departamento":'9no "C"', "apto_camilla": True},
        {"n":2, "departamento":'9no "C"', "apto_camilla": True},
        {"n":3, "departamento":'9no "C"', "apto_camilla": False},
        {"n":4, "departamento":'9no "C"', "apto_camilla": True},
    ]

    NOTAS_GRILLA = [
        "La disponibilidad mostrada corresponde al mes en curso considerando reservas regulares activas.",
        "Los horarios marcados como disponibles en este mes pero reservados a futuro se muestran como ocupados.",
    ]

    generar_disponibilidad(
        NOMBRE_ESPACIO,
        UNIDADES,
        CONSULTORIOS,
        notas_grilla=NOTAS_GRILLA,
    )
