# ═══════════════════════════════════════════════════════════════════════
# SISTEMA ESPACIO RAMOS — Generador PDF Propuesta al profesional
# Modelo definitivo v1.0
# Para profesionales NO ACTIVOS — muestra IdUnidad en lugar de departamento
# Nombre: "{NombreEspacio} - Propuesta al profesional [localidad si hay varias].pdf"
# ═══════════════════════════════════════════════════════════════════════
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
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
normal_st = ParagraphStyle("normal", fontName="Helvetica", fontSize=9,
                           leading=13, textColor=NEGRO, alignment=TA_JUSTIFY)
ph_st     = ParagraphStyle("ph", fontName="Helvetica", fontSize=8,
                           textColor=colors.HexColor("#888888"), alignment=TA_CENTER)
cam_st    = ParagraphStyle("cam", fontName="Helvetica-BoldOblique", fontSize=7.5,
                           textColor=VERDE_CAMILLA, alignment=TA_CENTER)
valor_st  = ParagraphStyle("val", fontName="Helvetica-Bold", fontSize=8,
                           textColor=CELESTE, alignment=TA_CENTER)


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
        x  = (self.ancho - tw) / 2
        y  = (self.alto - self.fs * 0.75) / 2
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


# ── Parámetros de grilla ──────────────────────────────────────────────────────
HORA_INI = 8; HORA_FIN = 22
DIAS_SEM = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado"]
BLOQ_RIG = [(9,11),(18,21)]
UMBRAL   = 8


def tipo_b(h):
    for a,b in BLOQ_RIG:
        if a<=h<b: return "Rígido"
    return "Flexible"


def cambio_tipo(h):
    t=tipo_b(h); t2=tipo_b(h-1) if h>HORA_INI else None
    return t2 is not None and t2!=t


def etiq_d(depto, dos=False):
    if not dos: return depto
    p=depto.rsplit(" ",1)
    if len(p)==2:
        piso=_re.sub(r'(mo|to|vo|ro|no|do)$','',p[0],flags=_re.IGNORECASE)
        letra=p[1].replace('"','').strip()
        return f"{piso}\n{letra}"
    return depto


def grilla_propuesta(unidades_info, estados_grilla=None):
    """
    unidades_info: lista de (uid, cant_consultorios, etiqueta_unidad)
    Para propuesta la etiqueta es "Unidad N" (no el departamento real).
    """
    import random; random.seed(55)
    horas=list(range(HORA_INI,HORA_FIN))
    n_u=len(unidades_info); n_d=len(DIAS_SEM)
    LF=0.4; LG=1.8; LM=1.0; dos=n_u>4

    def color_celda(uid,dia_idx,h):
        if estados_grilla and (uid,dia_idx,h) in estados_grilla:
            return estados_grilla[(uid,dia_idx,h)]
        e=random.choice(["libre","libre","libre","solo_ventana","solo_sin_ventana","ocupado"])
        if e=="ocupado": return ROJO_DISP
        if e=="solo_ventana": return AMARILLO_DISP
        if e=="solo_sin_ventana": return NARANJA_DISP
        return VERDE_DISP

    if n_u>UMBRAL:
        aw=1.8*cm; uw=2.0*cm
        cw_=[aw,uw]+[(ANCHO_UTIL-aw-uw)/len(horas)]*len(horas)
        h0=["Tipo de\nbloque →",""]+[tipo_b(h) for h in horas]
        h1=["Día","Unidad"]+[f"{h}hs" for h in horas]
        data=[h0,h1]; cc=[]; ri=2
        for ci_d,dia in enumerate(DIAS_SEM):
            for uid,cant,etiq in unidades_info:
                fila=[dia.upper(),etiq]
                for ci_h,h in enumerate(horas):
                    fila.append("")
                    cc.append((2+ci_h,ri,color_celda(uid,ci_d,h)))
                data.append(fila); ri+=1
        est=[
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
        i=2
        while i<len(h0):
            j=i
            while j<len(h0) and h0[j]==h0[i]: j+=1
            if j-i>1: est.append(("SPAN",(i,0),(j-1,0)))
            i=j
        for ci_d in range(n_d):
            r0=2+ci_d*n_u; r1=r0+n_u-1
            if n_u>1: est.append(("SPAN",(0,r0),(0,r1)))
            if ci_d<n_d-1: est.append(("LINEBELOW",(0,r1),(-1,r1),LM,NEGRO))
        est.append(("SPAN",(0,0),(1,0)))
        for ci_h,h in enumerate(horas[1:],start=1):
            if cambio_tipo(h): est.append(("LINEBEFORE",(2+ci_h,0),(2+ci_h,-1),LM,NEGRO))
        for col,row,c in cc: est.append(("BACKGROUND",(col,row),(col,row),c))
        t=Table(data,colWidths=cw_,repeatRows=2); t.setStyle(TableStyle(est)); return [t]

    tw=1.3*cm; hw=1.1*cm
    cw_=[tw,hw]+[(ANCHO_UTIL-tw-hw)/(n_d*n_u)]*(n_d*n_u)
    h0=["Tipo\nBloque","Horario"]
    for d in DIAS_SEM: h0.append(d.upper()); h0+=[""]*(n_u-1)
    h1=["",""]
    for d in DIAS_SEM: h1.append("Unidad"); h1+=[""]*(n_u-1)
    h2=["",""]
    for d in DIAS_SEM:
        for uid,cant,etiq in unidades_info: h2.append(etiq_d(etiq,dos))
    rows=[]; cc=[]
    for ri,h in enumerate(horas,start=3):
        fila=[tipo_b(h),f"{h}hs"]
        for ci_d in range(n_d):
            for ci_u,(uid,cant,etiq) in enumerate(unidades_info):
                fila.append("")
                col=2+ci_d*n_u+ci_u
                cc.append((col,ri,color_celda(uid,ci_d,h)))
        rows.append(fila)
    data=[h0,h1,h2]+rows
    est=[
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
    for ci_d,d in enumerate(DIAS_SEM):
        c0=2+ci_d*n_u; c1=c0+n_u-1
        if n_u>1:
            est.append(("SPAN",(c0,0),(c1,0)))
            est.append(("SPAN",(c0,1),(c1,1)))
        if ci_d<n_d-1: est.append(("LINEAFTER",(c1,0),(c1,-1),LG,NEGRO))
    i=3
    while i<len(data):
        j=i
        while j<len(data) and data[j][0]==data[i][0]: j+=1
        if j-i>1: est.append(("SPAN",(0,i),(0,j-1)))
        i=j
    for ri,h in enumerate(horas,start=3):
        if cambio_tipo(h): est.append(("LINEABOVE",(0,ri),(-1,ri),LM,NEGRO))
    for col,row,c in cc: est.append(("BACKGROUND",(col,row),(col,row),c))
    t=Table(data,colWidths=cw_,repeatRows=3); t.setStyle(TableStyle(est)); return [t]


def leyenda():
    CW=0.65*cm; TW=ANCHO_UTIL/2-CW-0.15*cm
    items=[
        (VERDE_DISP,    "Hay al menos dos consultorios disponibles"),
        (AMARILLO_DISP, "Solo un consultorio disponible con ventana"),
        (NARANJA_DISP,  "Solo un consultorio disponible sin ventana"),
        (ROJO_DISP,     "Sin consultorios disponibles"),
    ]
    def p(t): return Paragraph(t,ParagraphStyle("l",fontName="Helvetica",fontSize=7.5,leading=10,textColor=NEGRO))
    data=[[" ",p(items[0][1])," ",p(items[1][1])],[" ",p(items[2][1])," ",p(items[3][1])]]
    t=Table(data,colWidths=[CW,TW,CW,TW])
    e=[
        ("ALIGN",(0,0),(0,-1),"CENTER"),("ALIGN",(2,0),(2,-1),"CENTER"),
        ("FONTSIZE",(0,0),(0,-1),6.5),("FONTSIZE",(2,0),(2,-1),6.5),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
        ("BOX",(0,0),(0,0),1.0,NEGRO),("BOX",(2,0),(2,0),1.0,NEGRO),
        ("BOX",(0,1),(0,1),1.0,NEGRO),("BOX",(2,1),(2,1),1.0,NEGRO),
        ("BACKGROUND",(0,0),(0,0),VERDE_DISP),("BACKGROUND",(2,0),(2,0),AMARILLO_DISP),
        ("BACKGROUND",(0,1),(0,1),NARANJA_DISP),("BACKGROUND",(2,1),(2,1),ROJO_DISP),
    ]
    t.setStyle(TableStyle(e))
    ns=ParagraphStyle("ns",fontName="Helvetica-BoldOblique",fontSize=6.2,
                      textColor=GRIS_OSCURO,spaceBefore=3,leading=9)
    c=Table([[t],
             [Paragraph("Horarios rígidos: son bloques de horas consecutivas que se deben reservar sí o sí todas juntas, estos bloques no se fraccionan.",ns)],
             [Paragraph("Horarios flexibles: las horas comprendidas dentro de estos bloques se pueden reservar sin restricción y sin mínimo alguno.",ns)]],
            colWidths=[ANCHO_UTIL])
    c.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),2),
                            ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
    return c


def tabla_valores(consultorios_todos):
    """Tabla horizontal de valores vigentes por unidad."""
    from collections import OrderedDict
    MAX_C=12; grupos=OrderedDict()
    for c in consultorios_todos: grupos.setdefault(c["etiq_unidad"],[]).append(c)
    LF=0.4; LG=1.8; etiq_w=2.5*cm; result=[]
    max_c=max(len(v) for v in grupos.values())
    for bi in range(0,max_c,MAX_C):
        bf=min(bi+MAX_C,max_c); n=bf-bi
        enc=["Unidad"]+[f"Consul. {i+1+bi}" for i in range(n)]
        filas_d=[]
        for etiq,lista in grupos.items():
            fila=[etiq]
            for i in range(bi,bf):
                fila.append(f"${lista[i]['valor_regular']:,}".replace(",",".") if i<len(lista) else "—")
            filas_d.append(fila)
        cw=[etiq_w]+[(ANCHO_UTIL-etiq_w)/n]*n
        data=[enc]+filas_d
        t=Table(data,colWidths=cw,repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),CELESTE),("TEXTCOLOR",(0,0),(-1,0),BLANCO),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),7.5),
            ("BACKGROUND",(0,1),(0,-1),colors.HexColor("#AED6F1")),
            ("FONTNAME",(0,1),(0,-1),"Helvetica"),
            ("FONTNAME",(1,1),(-1,-1),"Helvetica"),("FONTSIZE",(1,1),(-1,-1),7.5),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[BLANCO,GRIS_CLARO]),
            ("GRID",(0,0),(-1,-1),LF,colors.HexColor("#CCCCCC")),
            ("BOX",(0,0),(-1,-1),LG,NEGRO),
            ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ]))
        result.append(t)
        if bf<max_c: result.append(Spacer(1,0.2*cm))
    return result


def tabla_descuentos():
    TOPE=25; BLQ=9
    tramos=[(f"Hasta {h}hs",f"{min(h//2,TOPE)}%") for h in range(2,52,2)]
    while len(tramos)%BLQ!=0:
        s=int(tramos[-1][0].replace("Hasta ","").replace("hs",""))+2
        tramos.append((f"Hasta {s}hs",f"{TOPE}%"))
    ROJO_D=colors.HexColor("#C0392B"); result=[]
    for i in range(0,len(tramos),BLQ):
        blq=tramos[i:i+BLQ]
        enc=["Hs. semanales"]+[t[0] for t in blq]
        fila=["Descuento"]+[t[1] for t in blq]
        ew=2.3*cm; cw=[ew]+[(ANCHO_UTIL-ew)/len(blq)]*len(blq)
        t=Table([enc,fila],colWidths=cw)
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),CELESTE),("TEXTCOLOR",(0,0),(-1,0),BLANCO),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),7),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("BACKGROUND",(0,0),(0,0),ROJO_D),
            ("BACKGROUND",(0,1),(-1,1),BLANCO),("FONTNAME",(0,1),(-1,1),"Helvetica"),
            ("FONTSIZE",(0,1),(-1,1),7),("TEXTCOLOR",(0,1),(-1,1),NEGRO),
            ("BACKGROUND",(0,1),(0,1),ROJO_D),("TEXTCOLOR",(0,1),(0,1),BLANCO),
            ("FONTNAME",(0,1),(0,1),"Helvetica-Bold"),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#CCCCCC")),
            ("BOX",(0,0),(-1,-1),1.0,NEGRO),
            ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ]))
        result.append(t); result.append(Spacer(1,0.2*cm))
    return result


def fotos_propuesta(consultorios):
    """
    consultorios: lista de dicts con n, etiq_unidad, valor_regular, apto_camilla
    Para propuesta la etiqueta de unidad es "Unidad N".
    """
    story=[]
    ancho_foto=ANCHO_UTIL/2-0.2*cm
    for i in range(0,len(consultorios),2):
        grupo=consultorios[i:i+2]; celdas=[]
        for c in grupo:
            ph_tabla=Table(
                [[Paragraph(f"[ Foto consultorio {c['n']} — {c['etiq_unidad']} ]",ph_st)]],
                colWidths=[ancho_foto-0.4*cm],rowHeights=[4.5*cm])
            ph_tabla.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,-1),GRIS_CLARO),
                ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#CCCCCC")),
                ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ]))
            txt_val=f"Consultorio {c['n']} — {c['etiq_unidad']} — Valor hora regular ${c['valor_regular']}"
            lineas=[ph_tabla,Spacer(1,0.15*cm),Paragraph(txt_val,valor_st)]
            if c.get("apto_camilla"):
                lineas.append(Paragraph("✔ Apto camilla",cam_st))
            celdas.append(lineas)
        if len(grupo)==1: celdas.append([Paragraph("",ph_st)])
        t=Table([celdas],colWidths=[ancho_foto,ancho_foto])
        t.setStyle(TableStyle([
            ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"TOP"),
            ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),10),
        ]))
        story.append(t)
    return story


# ── Condiciones (21 puntos) ───────────────────────────────────────────────────
CONDICIONES = [
    ("1) FORMA DE PAGO","Se enviará a cada profesional una liquidación mensual a principios de mes por sus horarios reservados, la cual será abonada por el mismo dentro del mes en curso. El profesional podrá hacer un pago total o realizar también pagos parciales, lo importante es cancelar el total liquidado antes del comienzo del nuevo mes."),
    ("2) DIAS FERIADOS","Los días declarados como feriados nacionales o días no laborables por el ministerio del interior no se contemplan dentro de la liquidación, dando por descontado, en principio, que el profesional no hará uso del espacio reservado en esas fechas. En caso de querer hacerlo, deberá comunicarse previamente con el administrador del espacio para coordinarlo, y abonará únicamente las horas utilizadas en la liquidación del mes siguiente. Aclaraciones y excepciones: el Jueves Santo no es considerado feriado por dicho organismo; por tal motivo, se liquidará normalmente. Las únicas excepciones serán el 24 y el 31 de diciembre, fechas a las que se les dará el mismo tratamiento que a los feriados, aunque legalmente no lo sean. Por cualquier duda consultar la fuente oficial: https://www.argentina.gob.ar/feriados"),
    ("3) VACACIONES","Se reconocerá al profesional un máximo de dos semanas por año calendario en concepto de vacaciones. Dicho período no será abonado y el profesional conservará la reserva del espacio."),
    ("4) ESQUEMA DE DESCUENTOS","Queda a criterio del espacio conservar, ampliar, modificar o eliminar el actual esquema de descuentos a futuro."),
    ("5) ACTUALIZACION DE LOS VALORES","Los valores de las horas se revisarán y, de ser necesario, se ajustarán en forma bimestral durante los meses pares (febrero, abril, junio, agosto, octubre y diciembre) para mantener los mismos actualizados."),
    ("6) COMPROMISO DE RESERVA","El compromiso de reserva se renueva mensualmente. Antes de que comience el nuevo mes el profesional puede cancelar su reserva o bien ajustarla de acuerdo a su necesidad y a la disponibilidad del lugar. Las reducciones de los módulos fijos reservados se pueden hacer únicamente para el mes siguiente, en cambio las extensiones de dichos módulos se pueden coordinar entre el administrador y el profesional en cualquier momento del mes. Las nuevas horas incorporadas a la reserva durante el mes en curso se liquidarán al mes siguiente. Si el profesional no se contacta con el administrador se dará por entendido que continúa con la misma reserva del mes anterior."),
    ("7) RESERVAS AISLADAS","Las horas aisladas para alguna fecha en particular deberán ser coordinadas previamente con el espacio. Las mismas no tienen recargo sobre el valor de la hora regular, pero no se les aplican los descuentos que sí poseen las reservas regulares. Dichas horas pueden cancelarse hasta con 24hs de anticipación sin costo alguno, no se pueden cancelar el mismo día de la reserva. Solo se reservan horarios con este formato de un mes a otro como máximo."),
    ("8) AUSENTES","Las ausencias tanto de los pacientes como de los profesionales no intervienen en el cálculo de la liquidación, por tal motivo son responsabilidad de estos últimos la administración y uso de sus bloques reservados."),
    ("9) JUEGO DE LLAVES","Se entregará al profesional un juego de llaves para que este se maneje con independencia durante su tiempo en el lugar haciéndose desde ese momento responsable de las mismas. Por dicho juego se pedirá un valor en concepto de depósito equivalente al costo de realizar esas llaves. En caso de extraviarlas el profesional deberá abonar la reposición de dichas llaves. Si el profesional en algún momento deja de atender en el lugar, en caso de que haya pagado ese depósito el espacio le reintegrará el valor actualizado de dichas llaves al momento de la devolución. Si es necesario realizar un cambio de combinación en las unidades el espacio reemplazará las llaves de los profesionales sin cargo alguno, pero en el caso de que sea la llave del edificio la que se cambia el profesional abonará el depósito de la nueva llave ya que es una responsabilidad ajena al espacio."),
    ("10) OPTIMIZACION DE LA GRILLA HORARIA","En el caso de haber modificaciones en cuanto a la disponibilidad por bajas de horas de algún profesional, primero se procurará realizar los cambios necesarios para ubicar a algún profesional activo que se encuentre tomando horas no consecutivas o en distintos consultorios, llegado el caso el espacio puede reubicar a otros profesionales en otros consultorios para poder optimizar las estructuras respetándoles los horarios que tenía acordados."),
    ("11) LICENCIA POR MATERNIDAD","Se reconocerá un máximo de 90 días corridos como licencia de maternidad para las profesionales mujeres que no vayan a utilizar los consultorios por ese motivo, período durante el cual abonará el 50% del valor de la reserva y conservará la misma hasta su reincorporación, siempre que desee mantenerla."),
    ("12) LICENCIA POR MATRIMONIO","En el caso de que el profesional contraiga matrimonio y no utilizara los consultorios por algún viaje a modo de luna de miel, se le reconocerá un plazo adicional máximo de dos semanas con el mismo tratamiento que el período de vacaciones."),
    ("13) OTRAS EVENTUALIDADES","El espacio no contempla otras eventualidades además de las descriptas anteriormente. En caso de que el profesional no pueda utilizar el espacio reservado, ya sea por motivos personales o por causas de fuerza mayor, el espacio podrá ofrecer, sujeto a disponibilidad, alternativas para recuperar las horas no utilizadas sin costo adicional."),
    ("14) ENTREGA DE LOS CONSULTORIOS","El profesional debe dejar puntualmente libre el consultorio en los horarios acordados, y a la hora de hacerlo se le solicita al mismo que tenga la seguridad de chequear que el aire acondicionado quede apagado, dejar la puerta del consultorio entreabierta y que la persiana quede baja en caso de que ese consultorio cuente con ella. Los atrasos de los pacientes no son motivo válido para extender el bloque reservado para no perjudicar a los profesionales que toman horas a posterior en ese consultorio."),
    ("15) CONVIVENCIA","El profesional deberá cumplir con las normas de convivencia lógicas de cualquier lugar de este tipo, como ser el cuidado general del espacio, su limpieza, su orden, el hecho de trabajar en silencio y armonía, el respeto a sus colegas, etc., haciéndose responsable por dichas cuestiones tanto de sus actos como también los de sus pacientes, indicándoles a estos las conductas inapropiadas que puedan llegar a tener dentro de su permanencia en el lugar."),
    ("16) AREA DE GUARDADO DE MATERIALES","El espacio ofrece un lugar para que el profesional pueda dejar elementos personales y laborales, pidiéndole a este únicamente que identifique claramente con nombre dichos elementos. El espacio no se hace responsable de cualquier pérdida o daño que estos puedan sufrir."),
    ("17) ACCESO DE TERCEROS","No está permitido el ingreso de terceros relacionados con el profesional a los consultorios para que estos permanezcan ahí esperando a que dicho profesional termine su jornada, esto es para no incomodar al resto de los colegas y conservar la armonía del lugar de trabajo. Se entiende que el uso del espacio y de sus comodidades son exclusivamente para el profesional que contrata el lugar."),
    ("18) CESION DE LA RESERVA","Queda expresamente prohibido al profesional ceder su espacio reservado a otro profesional, sea o no miembro actual del equipo del consultorio, sin haberlo consultado previamente con el administrador del lugar."),
    ("19) AREA DE COCINA","El espacio cuenta con un sector de cocina del cual se ponen a disposición de los profesionales todos sus elementos conjuntamente con una variedad de infusiones para su uso sin cargo alguno. La única condición es que cada cual lave y ordene los elementos que haya utilizado dejando así el área en condiciones para el uso por parte de otro profesional."),
    ("20) VIGENCIA DE CONDICIONES","Las condiciones anteriormente detalladas rigen desde el momento en que son enviadas al profesional conjuntamente con la liquidación mensual, tomando siempre el último envío como modelo de las condiciones vigentes para la reserva del espacio."),
    ("21) CONFORMIDAD Y CUMPLIMIENTO","La reserva de un espacio por parte del profesional implica el conocimiento y la aceptación de todas las condiciones anteriormente detalladas."),
]

# Secciones complementarias editables (21 items — en producción vienen de BD)
SECCIONES_COMPLEMENTARIAS = [
    ("Detalles de acceso al espacio",
     "El espacio se encuentra ubicado en Av. Rivadavia 13876, Ramos Mejía. "
     "Para ingresar se le entregará un juego de llaves al momento de comenzar."),
    ("Medios de contacto",
     "Para cualquier consulta, modificación de reserva o aviso comunicarse por WhatsApp "
     "al número de contacto del administrador."),
    ("Forma de pago habitual",
     "Los pagos se realizan mediante transferencia bancaria o en sobre depositado en el buzón "
     "de la unidad. Los datos bancarios se informan al momento de comenzar."),
]


def seccion_condiciones():
    story=[]
    txt_st=ParagraphStyle("tx",fontName="Helvetica",fontSize=8.5,leading=12,
                          textColor=NEGRO,alignment=TA_JUSTIFY,spaceBefore=5,spaceAfter=2)
    for tit,txt in CONDICIONES:
        story.append(Paragraph(f"<b>{tit}:</b>   {txt}",txt_st))
    return story


def seccion_complementaria(secciones):
    story=[]
    tit_st=ParagraphStyle("tc2",fontName="Helvetica-Bold",fontSize=9,
                          textColor=NEGRO,spaceBefore=8,spaceAfter=2)
    txt_st=ParagraphStyle("tx2",fontName="Helvetica",fontSize=8.5,leading=12,
                          textColor=NEGRO,alignment=TA_JUSTIFY,spaceAfter=4)
    for tit,txt in secciones:
        story.append(Paragraph(tit,tit_st))
        story.append(Paragraph(txt,txt_st))
    return story


# ── GENERADOR PRINCIPAL ───────────────────────────────────────────────────────
def generar_propuesta(
        nombre_espacio,
        unidades_info,        # [(uid, cant_consultorios, "Unidad N"), ...]
        consultorios_fotos,   # [{"n":1,"etiq_unidad":"Unidad 1","valor_regular":4646,"apto_camilla":True}, ...]
        consultorios_valores, # [{"etiq_unidad":"Unidad 1","valor_regular":4646}, ...]
        secciones_complementarias=None,
        estados_grilla=None,
        con_recargo=False,
        localidad=None):
    """
    con_recargo: si True agrega nota sobre recargo en reservas aisladas al final de condiciones
    localidad: str — si hay varias localidades se incluye en nombre y encabezado
    """
    suf_loc = f" - {localidad}" if localidad else ""
    nombre_archivo = f"{nombre_espacio} - Propuesta al profesional{suf_loc}.pdf"
    subtitulo = "Propuesta al profesional"
    if localidad: subtitulo += f" — {localidad}"

    story = []
    story += encabezado(nombre_espacio, subtitulo)
    story += sec("Detalles principales", 1)

    # Fotos (2 por fila)
    story += sec("Fotos de los consultorios disponibles", 2)
    story += fotos_propuesta(consultorios_fotos)
    story.append(Spacer(1, 0.3*cm))

    # Disponibilidad
    story += sec("Disponibilidad de horarios", 2)
    story += grilla_propuesta(unidades_info, estados_grilla)
    story.append(Spacer(1, 0.25*cm))
    story.append(leyenda())
    story.append(Spacer(1, 0.3*cm))

    # Valores vigentes
    story += sec("Valores vigentes por hora regular", 2)
    story += tabla_valores(consultorios_valores)
    story.append(Spacer(1, 0.3*cm))

    # Descuentos
    story += sec("Esquema de descuentos", 2)
    story += tabla_descuentos()

    # Condiciones
    story += sec("Condiciones y normas generales de convivencia relacionadas con la reserva en el espacio", 2)
    story += seccion_condiciones()
    if con_recargo:
        nota_st = ParagraphStyle("nr", fontName="Helvetica-Oblique", fontSize=8.5,
                                 leading=12, textColor=NEGRO, spaceBefore=6)
        story.append(Paragraph(
            "* Las reservas aisladas tienen un recargo adicional sobre el valor de la hora regular.",
            nota_st))
    story.append(Spacer(1, 0.3*cm))

    # Secciones complementarias
    if secciones_complementarias:
        story += sec("Detalles complementarios", 2)
        story += seccion_complementaria(secciones_complementarias)

    altura = max(len(story)*0.55*cm + 60*cm, 100*cm)
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

    # Para propuesta las unidades se muestran como "Unidad N"
    UNIDADES = [
        (1, 7, "Unidad 1"),
        (2, 4, "Unidad 2"),
        (3, 4, "Unidad 3"),
    ]

    CONSUL_FOTOS = [
        {"n":1, "etiq_unidad":"Unidad 1", "valor_regular":"$4.015", "apto_camilla":False},
        {"n":2, "etiq_unidad":"Unidad 1", "valor_regular":"$4.891", "apto_camilla":True},
        {"n":3, "etiq_unidad":"Unidad 1", "valor_regular":"$4.646", "apto_camilla":True},
        {"n":4, "etiq_unidad":"Unidad 1", "valor_regular":"$4.002", "apto_camilla":False},
        {"n":1, "etiq_unidad":"Unidad 2", "valor_regular":"$4.704", "apto_camilla":True},
        {"n":2, "etiq_unidad":"Unidad 2", "valor_regular":"$4.914", "apto_camilla":True},
    ]

    CONSUL_VALORES = [
        {"etiq_unidad":"Unidad 1","consultorio":c,"valor_regular":v}
        for c,v in enumerate([4015,4891,4646,4002,4330,4896,4646],1)
    ] + [
        {"etiq_unidad":"Unidad 2","consultorio":c,"valor_regular":v}
        for c,v in enumerate([4704,4914,4303,3197],1)
    ] + [
        {"etiq_unidad":"Unidad 3","consultorio":c,"valor_regular":v}
        for c,v in enumerate([3800,4100,4200,4200],1)
    ]

    # Adaptar consultorios_valores para tabla_valores (necesita clave "etiq_unidad" como agrupador)
    from collections import OrderedDict
    grupos = OrderedDict()
    for c in CONSUL_VALORES:
        grupos.setdefault(c["etiq_unidad"], []).append(c)

    generar_propuesta(
        NOMBRE_ESPACIO,
        UNIDADES,
        CONSUL_FOTOS,
        CONSUL_VALORES,
        secciones_complementarias=SECCIONES_COMPLEMENTARIAS,
        con_recargo=False,
    )
