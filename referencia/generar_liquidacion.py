# ═══════════════════════════════════════════════════════════════════════
# SISTEMA ESPACIO RAMOS — Generador PDF Liquidación Mensual
# Modelo definitivo v1.0
# ═══════════════════════════════════════════════════════════════════════
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, KeepTogether)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus.flowables import Flowable
from datetime import date as date_cls
import re as _re

# ── Colores ──────────────────────────────────────────────────────────────────
CELESTE      = colors.HexColor("#2E86AB")
NARANJA      = colors.HexColor("#E07B39")
GRIS_OSCURO  = colors.HexColor("#3D3D3D")
BLANCO       = colors.white
GRIS_CLARO   = colors.HexColor("#F5F5F5")
NEGRO        = colors.HexColor("#1A1A1A")
ROJO         = colors.HexColor("#C0392B")
VERDE_DISP   = colors.HexColor("#27AE60")
AMARILLO_DISP= colors.HexColor("#F1C40F")
NARANJA_DISP = colors.HexColor("#E67E22")
ROJO_DISP    = colors.HexColor("#E74C3C")
BORDO        = colors.HexColor("#6B0000")

PAGE_W, PAGE_H = A4
MARGEN     = 1.8 * cm
ANCHO_UTIL = PAGE_W - 2 * MARGEN

# ── Estilos base ─────────────────────────────────────────────────────────────
normal_st  = ParagraphStyle("normal", fontName="Helvetica", fontSize=9,
                            leading=13, textColor=NEGRO, alignment=TA_JUSTIFY)
titulo_st  = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=18,
                            textColor=CELESTE, alignment=TA_CENTER, spaceAfter=4)
subtit_st  = ParagraphStyle("subtit", fontName="Helvetica", fontSize=10,
                            textColor=GRIS_OSCURO, alignment=TA_CENTER, spaceAfter=10)

# ── Barra de sección ─────────────────────────────────────────────────────────
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

# ── Encabezado ────────────────────────────────────────────────────────────────
def encabezado(nombre_espacio, subtitulo):
    return [
        Spacer(1, 0.3*cm),
        Paragraph(nombre_espacio.upper(), titulo_st),
        Paragraph(subtitulo, subtit_st),
        HRFlowable(width=ANCHO_UTIL, thickness=1.5, color=CELESTE),
        Spacer(1, 0.4*cm),
    ]

# ── Tabla genérica ────────────────────────────────────────────────────────────
def mk_tabla(enc, filas, cw=None, fs=8.5):
    data = [enc] + filas
    if not cw: cw = [ANCHO_UTIL/len(enc)]*len(enc)
    t = Table(data, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), CELESTE),
        ("TEXTCOLOR",     (0,0),(-1,0), BLANCO),
        ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,0), fs),
        ("ALIGN",         (0,0),(-1,-1),"CENTER"),
        ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
        ("FONTNAME",      (0,1),(-1,-1),"Helvetica"),
        ("FONTSIZE",      (0,1),(-1,-1),fs),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[BLANCO, GRIS_CLARO]),
        ("GRID",          (0,0),(-1,-1),0.4,colors.HexColor("#CCCCCC")),
        ("BOX",           (0,0),(-1,-1),1.2,NEGRO),
        ("TOPPADDING",    (0,0),(-1,-1),4),
        ("BOTTOMPADDING", (0,0),(-1,-1),4),
        ("LEFTPADDING",   (0,0),(-1,-1),5),
        ("RIGHTPADDING",  (0,0),(-1,-1),5),
    ]))
    return t

# ── Utilidades moneda ─────────────────────────────────────────────────────────
def fmtM(v): return f"{abs(int(v)):,}".replace(",",".")
def fmtMS(v):
    s = f"${fmtM(v)}"
    return f"-{s}" if v < 0 else s

def numero_a_letras(n):
    uni=["","uno","dos","tres","cuatro","cinco","seis","siete","ocho","nueve",
         "diez","once","doce","trece","catorce","quince","dieciséis","diecisiete",
         "dieciocho","diecinueve"]
    dec=["","","veinte","treinta","cuarenta","cincuenta","sesenta","setenta","ochenta","noventa"]
    cen=["","cien","doscientos","trescientos","cuatrocientos","quinientos",
         "seiscientos","setecientos","ochocientos","novecientos"]
    def _c(n):
        if n<20: return uni[n]
        if n<100:
            d,u=divmod(n,10); return dec[d]+(" y "+uni[u] if u else "")
        c,r=divmod(n,100)
        if n==100: return "cien"
        return cen[c]+(" "+_c(r) if r else "")
    def _m(n):
        if n<1000: return _c(n)
        m,r=divmod(n,1000)
        p="un" if m==1 else _c(m)
        return p+" mil"+(" "+_c(r) if r else "")
    def _mm(n):
        if n<1_000_000: return _m(n)
        m,r=divmod(n,1_000_000)
        p="un millón" if m==1 else _m(m)+" millones"
        return p+(" "+_m(r) if r else "")
    return _mm(abs(int(n))).capitalize()

# ── Tabla bloques horarios ────────────────────────────────────────────────────
ORDEN_DIAS = {"Lunes":1,"Martes":2,"Miércoles":3,"Jueves":4,"Viernes":5,"Sábado":6,"Domingo":7}

def tabla_bloques(bloques, edificios_info=None):
    """
    bloques: lista de dicts con edificio, departamento, consultorio, dia_semana,
             hora_inicio, hora_fin, vigencia_desde, vigencia_hasta
    edificios_info: lista de dicts con nombre, domicilio, localidad (para aclaración al pie)
    """
    ord_ = sorted(bloques, key=lambda b:(b["edificio"],ORDEN_DIAS.get(b["dia_semana"],9),b["hora_inicio"]))
    enc = ["Edificio","Día","Hora inicio","Hora liberación","Unidad","Consultorio","Vigencia desde","Vigencia hasta"]
    filas = [[b["edificio"],b["dia_semana"],f"{b['hora_inicio']}hs",f"{b['hora_fin']}hs",
              b["departamento"],b["consultorio"],b["vigencia_desde"],b["vigencia_hasta"]]
             for b in ord_]
    cw = [x*cm for x in [2.2,1.8,1.9,2.1,1.8,2.0,2.2,2.1]]
    result = [mk_tabla(enc, filas, cw)]

    # Aclaración de edificios al pie
    if edificios_info:
        acl_st = ParagraphStyle("acl_ed", fontName="Helvetica", fontSize=8.5,
                                leading=12, textColor=NEGRO, spaceBefore=4)
        result.append(Spacer(1, 0.2*cm))
        for ed in edificios_info:
            result.append(Paragraph(
                f"* Edificio {ed['nombre']}: Corresponde a {ed['domicilio']}, {ed['localidad']}.",
                acl_st))
    return result

# ── Tabla liquidación ─────────────────────────────────────────────────────────
def tabla_liquidacion(items_cuenta):
    LG = 1.5
    cw = [ANCHO_UTIL - 3.5*cm, 3.5*cm]
    data=[]; estilos_extra=[]; llamadas_activas=[]; nro=1; ri=0; total_val=0
    for item in items_cuenta:
        if item["tipo"]=="total": total_val=item["importe"]
    letras = numero_a_letras(abs(int(total_val)))
    txt_letras = f"(son pesos {letras})" if total_val>=0 else f"(saldo a favor: pesos {letras})"

    for item in items_cuenta:
        imp = item["importe"]
        if imp==0 and not item.get("visible_cero",False): continue
        suf=""
        if item.get("tiene_llamada") and imp!=0:
            suf=f" ({nro})"; llamadas_activas.append((nro,item)); nro+=1
        concepto = item["concepto"]+suf
        imp_txt  = fmtMS(imp)
        es_resta = imp<0
        es_sub   = item["tipo"]=="subtotal"
        es_tot   = item["tipo"]=="total"
        negrita  = es_sub or es_tot
        color_imp= ROJO if (es_resta and not es_sub and not es_tot) else NEGRO
        fn = "Helvetica-Bold" if negrita else "Helvetica"
        c_st = ParagraphStyle("fc",fontName=fn,fontSize=9,textColor=NEGRO)
        i_st = ParagraphStyle("fi",fontName=fn,fontSize=9,textColor=color_imp,alignment=TA_RIGHT)
        if es_tot:
            let_st = ParagraphStyle("fl",fontName="Helvetica",fontSize=8.0,
                                    textColor=NEGRO,alignment=TA_RIGHT,leading=11)
            data.append([Paragraph(concepto,c_st),[Paragraph(imp_txt,i_st),Paragraph(txt_letras,let_st)]])
            estilos_extra.append(("BACKGROUND",(0,ri),(-1,ri),GRIS_CLARO))
            estilos_extra.append(("BOX",(0,ri),(-1,ri),LG,NEGRO))
            estilos_extra.append(("VALIGN",(0,ri),(0,ri),"MIDDLE"))
        else:
            data.append([Paragraph(concepto,c_st),Paragraph(imp_txt,i_st)])
            if es_sub:
                estilos_extra.append(("BACKGROUND",(0,ri),(-1,ri),GRIS_CLARO))
                estilos_extra.append(("BOX",(0,ri),(-1,ri),LG,NEGRO))
        ri+=1
    t = Table(data,colWidths=cw)
    base=[("ALIGN",(0,0),(0,-1),"LEFT"),("ALIGN",(1,0),(1,-1),"RIGHT"),
          ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
          ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
          ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
          ("LINEBELOW",(0,0),(-1,-1),0.3,BLANCO)]
    t.setStyle(TableStyle(base+estilos_extra))
    return t, llamadas_activas, total_val

def seccion_aclaraciones(llamadas, feriados_desc=None):
    story=[]; story.append(Spacer(1,0.4*cm))
    if not llamadas and not feriados_desc: return story
    tit_st=ParagraphStyle("ta",fontName="Helvetica",fontSize=9,textColor=NEGRO,spaceAfter=6)
    acl_st=ParagraphStyle("ac",fontName="Helvetica",fontSize=8.5,leading=12,textColor=NEGRO,spaceBefore=4)
    story.append(Paragraph("Detalle de los conceptos:",tit_st))
    story.append(Spacer(1,0.2*cm))
    if feriados_desc: story.append(Paragraph(feriados_desc,acl_st)); story.append(Spacer(1,0.15*cm))
    for nro,item in llamadas:
        story.append(Paragraph(f"({nro}) {item.get('detalle','')}",acl_st))
        story.append(Spacer(1,0.15*cm))
    return story

# ── Tabla consultorios utilizados ─────────────────────────────────────────────
def tabla_consultorios_utilizados(consultorios_prof):
    enc=["Edificio","Unidad","Consul.","Valor\nregular","Desc.","Valor c/\ndescuento","Horas\nmensuales"]
    filas=[]
    for c in consultorios_prof:
        filas.append([c["edificio"],c["departamento"],c["consultorio"],
                      f"${c['valor_regular']:,}".replace(",","."),
                      f"{c['porc_descuento']}%",
                      f"${round(c['valor_con_descuento']):,}".replace(",","."),
                      c["horas_mensuales"]])
    cw=[x*cm for x in [2.2,1.8,1.6,2.2,1.2,2.4,2.0]]
    t = mk_tabla(enc,filas,cw)
    total_hs = sum(c["horas_mensuales"] for c in consultorios_prof)
    subtotal  = round(sum(c["valor_con_descuento"]*c["horas_mensuales"] for c in consultorios_prof))
    pie_st=ParagraphStyle("pie",fontName="Helvetica-Bold",fontSize=8.5,textColor=NEGRO,alignment=TA_RIGHT)
    nota=Paragraph(
        f"Total horas mensuales: <b>{total_hs}hs</b>   -   "
        f"Subtotal liquidación: <b>${subtotal:,}</b>".replace(",","."),pie_st)
    return [t,Spacer(1,0.2*cm),nota]

# ── Tabla valores vigentes ────────────────────────────────────────────────────
def tabla_valores_vigentes(consultorios_todos):
    from collections import OrderedDict
    MAX_C=12; grupos=OrderedDict()
    for c in consultorios_todos: grupos.setdefault(c["unidad_id"],[]).append(c)
    LF=0.4; LG=1.8; etiq_w=2.5*cm; result=[]
    max_c=max(len(v) for v in grupos.values())
    for bi in range(0,max_c,MAX_C):
        bf=min(bi+MAX_C,max_c); n=bf-bi
        enc=["Unidad"]+[f"Consul. {i+1+bi}" for i in range(n)]
        filas_d=[]
        for uid,lista in grupos.items():
            fila=[lista[0]["departamento"]]
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

# ── Tabla descuentos ──────────────────────────────────────────────────────────
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

# ── Grilla disponibilidad ─────────────────────────────────────────────────────
HORA_INI=8; HORA_FIN=22
BLOQ_RIG=[(9,11),(18,21)]
DIAS_SEM=["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado"]
UMBRAL=8

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

def grilla_disp(unidades_info):
    import random; random.seed(77)
    est_=["libre","libre","libre","solo_uno","ocupado","ocupado"]
    horas=list(range(HORA_INI,HORA_FIN))
    n_u=len(unidades_info); n_d=len(DIAS_SEM)
    LF=0.4; LG=1.8; LM=1.0; dos=n_u>4

    if n_u>UMBRAL:
        aw=1.8*cm; uw=2.0*cm; cw_=[aw,uw]+[(ANCHO_UTIL-aw-uw)/len(horas)]*len(horas)
        h0=["Tipo de\nbloque →",""]+[tipo_b(h) for h in horas]
        h1=["Día","Unidad"]+[f"{h}hs" for h in horas]
        data=[h0,h1]; cc=[]; ri=2
        for ci_d,dia in enumerate(DIAS_SEM):
            for ci_u,(uid,cant,dep) in enumerate(unidades_info):
                fila=[dia.upper(),dep]
                for h in horas:
                    e=random.choice(est_); sv=e=="solo_uno" and random.random()>0.5
                    fila.append("S/V" if (e=="solo_uno" and sv) else "")
                    col=2+horas.index(h)
                    c=ROJO_DISP if e=="ocupado" else (NARANJA_DISP if (e=="solo_uno" and sv) else (AMARILLO_DISP if e=="solo_uno" else VERDE_DISP))
                    cc.append((col,ri,c))
                data.append(fila); ri+=1
        est=[("BACKGROUND",(0,0),(-1,1),CELESTE),("TEXTCOLOR",(0,0),(-1,1),BLANCO),
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
             ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]
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
        for ci,h in enumerate(horas[1:],start=1):
            if cambio_tipo(h): est.append(("LINEBEFORE",(2+ci,0),(2+ci,-1),LM,NEGRO))
        for col,row,c in cc: est.append(("BACKGROUND",(col,row),(col,row),c))
        t=Table(data,colWidths=cw_,repeatRows=2); t.setStyle(TableStyle(est)); return [t]

    tw=1.3*cm; hw=1.1*cm; cw_=[tw,hw]+[(ANCHO_UTIL-tw-hw)/(n_d*n_u)]*(n_d*n_u)
    h0=["Tipo\nBloque","Horario"]
    for d in DIAS_SEM: h0.append(d.upper()); h0+=[""]*(n_u-1)
    h1=["",""]
    for d in DIAS_SEM: h1.append("Unidad"); h1+=[""]*(n_u-1)
    h2=["",""]
    for d in DIAS_SEM:
        for uid,cant,dep in unidades_info: h2.append(etiq_d(dep,dos))
    rows=[]; cc=[]
    for ri,h in enumerate(horas,start=3):
        fila=[tipo_b(h),f"{h}hs"]
        for ci_d in range(n_d):
            for ci_u,(uid,cant,dep) in enumerate(unidades_info):
                e=random.choice(est_); sv=e=="solo_uno" and random.random()>0.5
                fila.append("")
                col=2+ci_d*n_u+ci_u
                c=ROJO_DISP if e=="ocupado" else (NARANJA_DISP if (e=="solo_uno" and sv) else (AMARILLO_DISP if e=="solo_uno" else VERDE_DISP))
                cc.append((col,ri,c))
        rows.append(fila)
    data=[h0,h1,h2]+rows
    est=[("BACKGROUND",(0,0),(-1,2),CELESTE),("TEXTCOLOR",(0,0),(-1,2),BLANCO),
         ("FONTNAME",(0,0),(-1,2),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,2),6),
         ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
         ("BACKGROUND",(2,0),(-1,0),BORDO),("TEXTCOLOR",(2,0),(-1,0),BLANCO),
         ("FONTNAME",(2,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(2,0),(-1,0),6.5),
         ("FONTNAME",(0,3),(-1,-1),"Helvetica"),("FONTSIZE",(0,3),(-1,-1),6.5),
         ("BACKGROUND",(0,3),(1,-1),GRIS_CLARO),
         ("GRID",(0,0),(-1,-1),LF,colors.HexColor("#CCCCCC")),
         ("BOX",(0,0),(-1,-1),LG,NEGRO),("LINEBELOW",(0,2),(-1,2),LG,NEGRO),
         ("LINEAFTER",(1,0),(1,-1),LG,NEGRO),
         ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]
    est.append(("SPAN",(0,0),(0,2))); est.append(("SPAN",(1,0),(1,2)))
    for ci_d,d in enumerate(DIAS_SEM):
        c0=2+ci_d*n_u; c1=c0+n_u-1
        if n_u>1: est.append(("SPAN",(c0,0),(c1,0))); est.append(("SPAN",(c0,1),(c1,1)))
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

def leyenda_disp():
    CW=0.65*cm; TW=ANCHO_UTIL/2-CW-0.15*cm
    items=[(VERDE_DISP,"","Hay al menos dos consultorios disponibles"),
           (AMARILLO_DISP,"","Solo un consultorio disponible con ventana"),
           (NARANJA_DISP,"","Solo un consultorio disponible sin ventana"),
           (ROJO_DISP,"","Sin consultorios disponibles")]
    def p(d): return Paragraph(d,ParagraphStyle("l",fontName="Helvetica",fontSize=7.5,leading=10,textColor=NEGRO))
    data=[[items[0][1],p(items[0][2]),items[1][1],p(items[1][2])],
          [items[2][1],p(items[2][2]),items[3][1],p(items[3][2])]]
    t=Table(data,colWidths=[CW,TW,CW,TW])
    e=[("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"),
       ("FONTSIZE",(0,0),(0,-1),6.5),("FONTSIZE",(2,0),(2,-1),6.5),
       ("ALIGN",(0,0),(0,-1),"CENTER"),("ALIGN",(2,0),(2,-1),"CENTER"),
       ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
       ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
       ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
       ("BOX",(0,0),(0,0),1.0,NEGRO),("BOX",(2,0),(2,0),1.0,NEGRO),
       ("BOX",(0,1),(0,1),1.0,NEGRO),("BOX",(2,1),(2,1),1.0,NEGRO),
       ("BACKGROUND",(0,0),(0,0),VERDE_DISP),("BACKGROUND",(2,0),(2,0),AMARILLO_DISP),
       ("BACKGROUND",(0,1),(0,1),NARANJA_DISP),("BACKGROUND",(2,1),(2,1),ROJO_DISP)]
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

# ── Condiciones y normas ──────────────────────────────────────────────────────
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

def seccion_condiciones():
    story=[]
    txt_st=ParagraphStyle("tx",fontName="Helvetica",fontSize=8.5,leading=12,
                          textColor=NEGRO,alignment=TA_JUSTIFY,spaceBefore=5,spaceAfter=2)
    for tit,txt in CONDICIONES:
        story.append(Paragraph(f"<b>{tit}:</b>   {txt}",txt_st))
    return story

# ── Config actualización ──────────────────────────────────────────────────────
def etiqueta_periodo(config):
    meses=config.get("MesesDelPeriodo",[])
    if len(meses)<=2:
        p=" y ".join(f"{m:02d}/2026" for m in meses)
    else:
        p=f"{meses[0]:02d}/2026 al {meses[-1]:02d}/2026"
    return f"Valores de los consultorios para el período comprendido entre {p}"

# ── GENERADOR PRINCIPAL ───────────────────────────────────────────────────────
def generar_liquidacion(
        nombre_archivo, nombre_espacio, periodo,
        profesional, bloques, items_cuenta,
        consultorios_prof, consultorios_todos, unidades_grilla,
        placas, recordatorios_extra,
        edificios_info=None,
        config_actualizacion=None,
        hay_varios_edificios=False,
        feriados_desc=None):

    story=[]
    np_=(f"{profesional['tratamiento']} {profesional['nombre_pila']} {profesional['apellido']}")
    story += encabezado(nombre_espacio, f"Liquidación mensual - {np_}")
    story += sec(f"Detalle reserva {periodo} - {np_}", 1)

    story += sec("Bloques de horarios regulares reservados", 2)
    story += tabla_bloques(bloques, edificios_info)
    story.append(Spacer(1,0.4*cm))

    story += sec("Liquidación mensual mes en curso", 2)
    t_liq, llamadas, total = tabla_liquidacion(items_cuenta)
    story.append(t_liq)
    story += seccion_aclaraciones(llamadas, feriados_desc)
    story.append(Spacer(1,0.3*cm))

    cfg = config_actualizacion or {"MesesDelPeriodo":[6,7]}
    story += sec("Consultorios y cantidad de horas utilizadas por el profesional en el mes liquidado", 2)
    story += tabla_consultorios_utilizados(consultorios_prof)
    story.append(Spacer(1,0.3*cm))
    story += sec(etiqueta_periodo(cfg), 2)
    if isinstance(consultorios_todos, dict):
        for nombre_ed, lista_c in consultorios_todos.items():
            story += sec(nombre_ed, 3)
            story += tabla_valores_vigentes(lista_c)
            story.append(Spacer(1,0.2*cm))
    else:
        story += tabla_valores_vigentes(consultorios_todos)
    story.append(Spacer(1,0.3*cm))

    story += sec("Esquema de descuentos", 2)
    story += tabla_descuentos()

    story += sec("Recordatorios varios para el profesional", 2)
    rec_st=ParagraphStyle("r",fontName="Helvetica",fontSize=9,leading=13,textColor=NEGRO,spaceBefore=3)
    for p_ in placas:
        if hay_varios_edificios:
            txt=f"* Placa para los timbres en la unidad del {p_['depto']} del edificio {p_['edificio']} en la posición {p_['posicion']} del tablero"
        else:
            txt=f"* Placa para los timbres en la unidad del {p_['depto']} en la posición {p_['posicion']} del tablero"
        story.append(Paragraph(txt,rec_st))
    for r_ in recordatorios_extra:
        story.append(Paragraph(f"* {r_}",rec_st))
    story.append(Paragraph(
        "* Abonar el total liquidado dentro del mes en curso para mantener los descuentos en el próximo período.",rec_st))
    story.append(Paragraph(
        "* Los saldos pendientes que se trasladan de un mes a otro reciben un ajuste del 3% para mantener los mismos actualizados.",rec_st))
    story.append(Spacer(1,0.3*cm))

    fecha_hoy=date_cls.today().strftime("%d-%m-%Y")
    story += sec(f"Disponibilidad de consultorios al {fecha_hoy}", 2)
    if isinstance(unidades_grilla, dict):
        for nombre_ed, ulist in unidades_grilla.items():
            story += sec(nombre_ed, 3)
            story += grilla_disp(ulist)
            story.append(Spacer(1,0.25*cm))
            story.append(leyenda_disp())
            story.append(Spacer(1,0.3*cm))
    else:
        story += grilla_disp(unidades_grilla)
        story.append(Spacer(1,0.25*cm))
        story.append(leyenda_disp())
        story.append(Spacer(1,0.3*cm))

    story += sec("Condiciones y normas generales de convivencia relacionadas con la reserva en el espacio", 2)
    story += seccion_condiciones()

    altura=max(len(story)*0.55*cm+80*cm,150*cm)
    doc=SimpleDocTemplate(nombre_archivo,pagesize=(PAGE_W,altura),
                          leftMargin=MARGEN,rightMargin=MARGEN,
                          topMargin=MARGEN,bottomMargin=MARGEN)
    doc.build(story)
    print(f"Generado: {nombre_archivo}")


# ═══════════════════════════════════════════════════════════════════════════════
# EJEMPLO DE USO — borrar o comentar en producción
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    PROF={"tratamiento":"Lic.","nombre_pila":"Virginia","apellido":"Lo Veci"}
    BLOQUES=[
        {"edificio":"Ramos 1","departamento":'7mo "L"',"consultorio":3,
         "dia_semana":"Lunes","hora_inicio":14,"hora_fin":18,
         "vigencia_desde":"01/07/2026","vigencia_hasta":"31/07/2026"},
        {"edificio":"Ramos 1","departamento":'7mo "L"',"consultorio":3,
         "dia_semana":"Miércoles","hora_inicio":14,"hora_fin":18,
         "vigencia_desde":"01/07/2026","vigencia_hasta":"31/07/2026"},
    ]
    ITEMS=[
        {"tipo":"item","concepto":"Importe bruto correspondiente a la reserva regular de julio",
         "importe":148736,"visible_cero":True,"tiene_llamada":False},
        {"tipo":"item","concepto":"Descuento (6%) por cantidad de horas semanales reservadas (8hs)",
         "importe":-8924,"visible_cero":True,"tiene_llamada":False},
        {"tipo":"subtotal","concepto":"Subtotal por reserva para el mes de julio",
         "importe":139812,"visible_cero":True,"tiene_llamada":False},
        {"tipo":"item","concepto":"Saldo a favor de la liquidación anterior",
         "importe":-1500,"visible_cero":True,"tiene_llamada":False},
        {"tipo":"total","concepto":"Liquidación a abonar por el profesional en el mes de julio",
         "importe":138312,"visible_cero":True,"tiene_llamada":False},
    ]
    CP=[{"edificio":"Ramos 1","departamento":'7mo "L"',"consultorio":3,
         "valor_regular":4646,"porc_descuento":6,"valor_con_descuento":4646*0.94,
         "horas_mensuales":32,"unidad_id":1}]
    CT=[{"unidad_id":1,"departamento":'7mo "L"',"consultorio":c,"valor_regular":v}
        for c,v in enumerate([4015,4891,4646,4002,4330,4896,4646],1)]
    UG=[(1,7,'7mo "L"')]
    PL=[{"depto":'7mo "L"',"posicion":42,"edificio":"Ramos 1"}]
    ED=[{"nombre":"Ramos 1","domicilio":"Av. Rivadavia 13876","localidad":"Ramos Mejía"}]

    generar_liquidacion(
        "2026-07 - Lic. Virginia Lo Veci - Liquidacion mensual.pdf",
        "Espacio Ramos Consultorios","07/2026",
        PROF,BLOQUES,ITEMS,CP,CT,UG,PL,[],
        edificios_info=ED,
        config_actualizacion={"MesesDelPeriodo":[6,7]},
        hay_varios_edificios=False
    )
