"""Grilla completa de disponibilidad hora por hora, agrupada por edificio
(sección 4.2) — reusada tanto en el PDF de Disponibilidad standalone
(Etapa 7, sección 4.4) como en la sección "Disponibilidad" embebida en el
PDF de Liquidación (sección 4.5), siguiendo el modelo real: filas =
Tipo de bloque (Rígido/Flexible, según BloqueRigido) + Horario, columnas
= Día > Unidad. Las celdas "naranja" (un solo consultorio disponible SIN
ventana) se pintan del mismo color que "amarillo" pero con la leyenda
"S/V" superpuesta, para distinguirlas sin agregar un quinto color."""
from __future__ import annotations

import re
import sqlite3

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from app.negocio.dias import DIAS_SEMANA
from app.negocio.formato import hora_fmt
from app.negocio.grilla import calcular_grilla
from app.pdf.estilos import (
    COLOR_AMARILLO,
    COLOR_DIA_GRILLA,
    COLOR_NIVEL_1,
    COLOR_ROJO,
    COLOR_VERDE,
    FUENTE,
    FUENTE_NEGRITA,
    encabezado,
    estilo_texto,
)

DIAS_GRILLA_DEFAULT = DIAS_SEMANA[:6]  # Lunes a Sábado
_COLOR_CELDA = {"verde": COLOR_VERDE, "amarillo": COLOR_AMARILLO, "naranja": COLOR_AMARILLO, "rojo": COLOR_ROJO}
_GROSOR_GRUESO = 1.3  # líneas estructurales (días, rígido/flexible, marcos de encabezado)


def _tipo_bloque_por_hora(conn: sqlite3.Connection, horas: list[int]) -> dict[int, str]:
    """Un BloqueRigido activo cubre esa hora para todos los días (esta
    grilla no distingue rígido/flexible por día, solo por horario)."""
    filas = conn.execute("SELECT HoraInicio, HoraFin FROM BloqueRigido WHERE Activo = 1").fetchall()
    return {h: ("Rígido" if any(f["HoraInicio"] <= h < f["HoraFin"] for f in filas) else "Flexible") for h in horas}


def _unidades_por_edificio(conn: sqlite3.Connection, ids_edificio: list[int] | None) -> list[sqlite3.Row]:
    if ids_edificio:
        placeholders = ", ".join("?" for _ in ids_edificio)
        return conn.execute(
            f"""
            SELECT u.IdUnidad, u.Departamento, e.IdEdificio, e.Nombre AS NombreEdificio
            FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio
            WHERE e.IdEdificio IN ({placeholders})
            ORDER BY e.Nombre, u.Departamento
            """,
            ids_edificio,
        ).fetchall()
    return conn.execute(
        """
        SELECT u.IdUnidad, u.Departamento, e.IdEdificio, e.Nombre AS NombreEdificio
        FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        ORDER BY e.Nombre, u.Departamento
        """
    ).fetchall()


def _etiqueta_unidad(u: sqlite3.Row, anonimizar: bool) -> str:
    """Sección 4.3: el PDF de Propuesta va a profesionales NO activos y
    "muestra IdUnidad en lugar de departamento" — no debe revelar el
    nombre/número real de la unidad a un contacto que todavía no forma
    parte del espacio."""
    return f"Unidad {u['IdUnidad']}" if anonimizar else u["Departamento"]


def _tamano_que_entra(
    textos: list[str], ancho_disponible: float, tamano_max: int = 10, tamano_min: int = 5,
    fuente: str = FUENTE_NEGRITA,
) -> int:
    """El tamaño de fuente más grande (dentro de [tamano_min, tamano_max])
    con el que TODOS los textos entran en una línea sin envolver — se mide
    el ancho real de cada uno en vez de asumir que el más largo por
    cantidad de caracteres es el más ancho (ej. "EP" es más ancho que "15"
    aunque tengan la misma longitud, las letras son más anchas que los
    dígitos en negrita). Envolver "15" en "1"/"5" a mitad de palabra se ve
    peor que dejarlo un poco más chico pero legible en una sola línea.
    `fuente` debe coincidir con la fuente real de renderizado — medir con
    una fuente distinta a la usada al dibujar puede sub o sobre-estimar
    cuánto entra."""
    if not textos:
        return tamano_max
    for tamano in range(tamano_max, tamano_min - 1, -1):
        ancho_maximo = max(stringWidth(t, fuente, tamano) for t in textos)
        if ancho_maximo <= ancho_disponible * 0.85:
            return tamano
    return tamano_min


def _partir_etiqueta_unidad(etiqueta: str) -> tuple[str, str]:
    """'7mo "L"' -> ('7', 'L'); 'EP "K"' -> ('EP', 'K'); '15 "H"' -> ('15', 'H').
    Arriba va solo el número de piso (sin el sufijo ordinal "mo"/"ro"/"no"
    si lo tiene; si el piso no es numérico, ej. "EP"/"PB", se deja tal
    cual). Abajo va la letra del departamento sin comillas. Si la etiqueta
    no sigue este patrón (dato cargado distinto), se deja completa arriba
    y nada abajo, en vez de romper."""
    m = re.match(r'^(\S+)\s+"([^"]+)"$', etiqueta)
    if not m:
        return etiqueta, ""
    prefijo, sufijo = m.groups()
    numero = re.match(r"^(\d+)", prefijo)
    arriba = numero.group(1) if numero else prefijo
    return arriba, sufijo


def _tabla_grilla_edificio(
    conn: sqlite3.Connection, unidades: list[sqlite3.Row], grilla: dict, horas: list[int], ancho: float,
    anonimizar_unidad: bool = False,
) -> Table:
    dias = DIAS_GRILLA_DEFAULT
    tipo_por_hora = _tipo_bloque_por_hora(conn, horas)

    n_unidades = len(unidades)
    ancho_tipo, ancho_horario = ancho * 0.08, ancho * 0.06
    ancho_restante = ancho - ancho_tipo - ancho_horario
    n_cols_datos = max(len(dias) * n_unidades, 1)
    ancho_col = ancho_restante / n_cols_datos

    def _partes_etiqueta(u: sqlite3.Row) -> tuple[str, str]:
        if anonimizar_unidad:
            return _etiqueta_unidad(u, anonimizar_unidad), ""
        return _partir_etiqueta_unidad(u["Departamento"])

    # Con muchas unidades por edificio la columna por consultorio se vuelve
    # angosta (varios edificios reales tienen 4+ unidades) — una celda de
    # texto plano no ajusta el contenido y termina desbordando sobre la
    # celda vecina, así que el piso y la letra van en un Paragraph propio
    # cada uno (una fila para cada uno). El tamaño de fuente se calcula
    # para que el texto más largo entre en una sola línea — más grande
    # cuando hay lugar, sin llegar a partir "15" en "1"/"5".
    partes = [_partes_etiqueta(u) for u in unidades]
    textos_etiqueta = [p for par in partes for p in par if p]
    # -2: LEFTPADDING+RIGHTPADDING de la celda. Sin negrita y en blanco
    # (fondo azul) — la medición usa la misma fuente con la que se dibuja.
    tamano_etiqueta = _tamano_que_entra(textos_etiqueta, ancho_col - 2, fuente=FUENTE)
    style_etiqueta = estilo_texto(tamano_etiqueta, negrita=False, alignment=TA_CENTER, textColor=colors.white)

    # El día de la semana usa la palabra más larga ("MIÉRCOLES") para
    # calcular el tamaño que entra en el ancho de todo su bloque de
    # columnas (mismo ancho para los 6 días, ya que unidades x ancho_col
    # se cancela). La celda "S/V" se auto-ajusta al ancho de una sola
    # columna de unidad, que sí se achica con más unidades por edificio.
    ancho_dia = ancho_restante / len(dias)
    tamano_dia = _tamano_que_entra([d.upper() for d in dias], ancho_dia - 2, tamano_max=14, tamano_min=6)
    tamano_sv = _tamano_que_entra(["S/V"], ancho_col - 2, tamano_max=6, tamano_min=3)

    fila_dias = ["Tipo\nBloque", "Horario"] + [d.upper() for d in dias for _ in unidades]
    fila_unidad_label = ["", ""] + ["Unidad" for _ in dias for _ in unidades]
    fila_piso = ["", ""] + [Paragraph(par[0], style_etiqueta) for _ in dias for par in partes]
    fila_letra = ["", ""] + [Paragraph(par[1], style_etiqueta) for _ in dias for par in partes]
    filas = [fila_dias, fila_unidad_label, fila_piso, fila_letra]

    fondos = []
    spans = []
    limites_grupo: list[int] = []  # última fila de cada grupo rígido/flexible (para línea gruesa + caja)
    inicios_grupo: list[int] = []
    tipo_anterior, inicio_grupo = None, None
    for fila_idx, h in enumerate(horas, start=4):
        fila = ["", hora_fmt(h)]
        tipo = tipo_por_hora[h]
        if tipo != tipo_anterior:
            if tipo_anterior is not None:
                spans.append(("SPAN", (0, inicio_grupo), (0, fila_idx - 1)))
                limites_grupo.append(fila_idx - 1)
                inicios_grupo.append(inicio_grupo)
            inicio_grupo, tipo_anterior = fila_idx, tipo
        for dia in dias:
            for u in unidades:
                color = grilla.get((u["IdUnidad"], dia, h), "rojo")
                fila.append("S/V" if color == "naranja" else "")
                fondos.append((color, fila_idx, len(fila) - 1))
        filas.append(fila)
    spans.append(("SPAN", (0, inicio_grupo), (0, len(horas) + 3)))
    inicios_grupo.append(inicio_grupo)

    for fila_idx, h in enumerate(horas, start=4):
        filas[fila_idx][0] = tipo_por_hora[h]

    col_widths = [ancho_tipo, ancho_horario] + [ancho_col] * n_cols_datos
    tabla = Table(filas, colWidths=col_widths, repeatRows=4)
    ultima_fila = len(horas) + 3

    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), FUENTE_NEGRITA),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.3, "#999999"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # El padding por defecto de reportlab (6pt a cada lado) se come casi
        # toda una columna angosta (edificios con 4+ unidades) — achicarlo
        # le devuelve ese espacio al texto del piso/letra.
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("BACKGROUND", (0, 0), (1, 3), COLOR_NIVEL_1),
        ("TEXTCOLOR", (0, 0), (1, 3), "#FFFFFF"),
        ("BACKGROUND", (2, 0), (-1, 0), COLOR_DIA_GRILLA),
        ("TEXTCOLOR", (2, 0), (-1, 0), "#FFFFFF"),
        ("FONTSIZE", (2, 0), (-1, 0), tamano_dia),
        ("BACKGROUND", (2, 1), (-1, 3), COLOR_NIVEL_1),
        ("TEXTCOLOR", (2, 1), (-1, 3), "#FFFFFF"),
        ("FONTSIZE", (2, 4), (-1, ultima_fila), tamano_sv),
        # El divisor entre la fila de piso y la de letra se pinta del mismo
        # azul que el fondo para que quede invisible (línea de la GRID fina
        # de abajo, dibujada encima).
        ("LINEBELOW", (2, 2), (-1, 2), 0.3, COLOR_NIVEL_1),
        # "Tipo Bloque"/"Horario" combinan las 4 filas de encabezado (mismo
        # alto que Día/Unidad/Piso/Letra) en vez de quedar ancladas arriba.
        ("SPAN", (0, 0), (0, 3)),
        ("SPAN", (1, 0), (1, 3)),
    ]
    idx = 2
    for dia in dias:
        estilo.append(("SPAN", (idx, 0), (idx + n_unidades - 1, 0)))
        estilo.append(("SPAN", (idx, 1), (idx + n_unidades - 1, 1)))
        idx += n_unidades
    estilo.extend(spans)
    for color, fila, col in fondos:
        estilo.append(("BACKGROUND", (col, fila), (col, fila), _COLOR_CELDA[color]))

    # Líneas estructurales más gruesas que la grilla fina: el marco de
    # Tipo Bloque/Horario, el marco de Día/Unidad/Piso/Letra, un divisor
    # por cada día, un divisor entre cada bloque rígido/flexible, una caja
    # por cada grupo Rígido/Flexible con sus horarios (columnas 0-1), y un
    # marco grueso alrededor de toda la grilla (incluye el borde inferior
    # del último bloque flexible, que si no queda sin remarcar).
    estilo.append(("BOX", (0, 0), (1, 3), _GROSOR_GRUESO, "#000000"))
    estilo.append(("BOX", (2, 0), (-1, 3), _GROSOR_GRUESO, "#000000"))
    idx = 2
    for _dia in dias:
        estilo.append(("BOX", (idx, 0), (idx + n_unidades - 1, 0), _GROSOR_GRUESO, "#000000"))
        idx += n_unidades
    idx = 2
    for _dia in dias:
        idx += n_unidades
        col_divisoria = idx - 1
        if col_divisoria < n_cols_datos + 1:
            estilo.append(("LINEAFTER", (col_divisoria, 0), (col_divisoria, ultima_fila), _GROSOR_GRUESO, "#000000"))
    for limite in limites_grupo:
        estilo.append(("LINEBELOW", (0, limite), (-1, limite), _GROSOR_GRUESO, "#000000"))
    for ini, fin in zip(inicios_grupo, limites_grupo + [ultima_fila]):
        estilo.append(("BOX", (0, ini), (1, fin), _GROSOR_GRUESO, "#000000"))
    estilo.append(("BOX", (0, 0), (-1, ultima_fila), _GROSOR_GRUESO, "#000000"))

    tabla.setStyle(TableStyle(estilo))
    return tabla


def secciones_disponibilidad(
    conn: sqlite3.Connection, anio: int, mes: int, ancho: float, fecha_titulo: str,
    ids_edificio: list[int] | None = None, anonimizar_unidad: bool = False,
) -> list:
    """Nivel 2 "Disponibilidad de consultorios al {fecha_titulo}" seguido,
    por cada edificio relevante, de un nivel 3 con su grilla completa +
    leyenda + notas de horarios rígidos/flexibles (sección 4.2)."""
    cfg = conn.execute(
        "SELECT HoraInicioGrilla, HoraFinGrilla FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    hora_ini = int(cfg["HoraInicioGrilla"]) if cfg else 8
    hora_fin = int(cfg["HoraFinGrilla"]) if cfg else 22
    horas = list(range(hora_ini, hora_fin))
    dias = DIAS_GRILLA_DEFAULT

    grilla = calcular_grilla(conn, anio, mes, hora_ini, hora_fin, dias)
    unidades = _unidades_por_edificio(conn, ids_edificio)

    por_edificio: dict[int, list[sqlite3.Row]] = {}
    nombres: dict[int, str] = {}
    for u in unidades:
        por_edificio.setdefault(u["IdEdificio"], []).append(u)
        nombres[u["IdEdificio"]] = u["NombreEdificio"]

    style_nota = estilo_texto(7, negrita=True, italica=True)

    story = [encabezado(2, f"Disponibilidad de consultorios al {fecha_titulo}", ancho), Spacer(1, 6)]
    for id_edificio, unidades_ed in por_edificio.items():
        bloque = [
            encabezado(3, f"Edificio {nombres[id_edificio]}", ancho),
            Spacer(1, 6),
            _tabla_grilla_edificio(conn, unidades_ed, grilla, horas, ancho, anonimizar_unidad),
            Spacer(1, 4),
            _tabla_leyenda(ancho),
            Paragraph(
                "Horarios rígidos: son bloques de horas consecutivas que se deben reservar sí o sí todas "
                "juntas, estos bloques no se fraccionan.", style_nota,
            ),
            Paragraph(
                "Horarios flexibles: las horas comprendidas dentro de estos bloques se pueden reservar sin "
                "restricción y sin mínimo alguno.", style_nota,
            ),
            Spacer(1, 8),
        ]
        story.append(KeepTogether(bloque))
    return story


def _tabla_leyenda(ancho: float) -> Table:
    filas = [
        [" ", "Hay al menos dos consultorios disponibles", "S/V", "Solo un consultorio disponible sin ventana"],
        [" ", "Solo un consultorio disponible con ventana", " ", "Sin consultorios disponibles"],
    ]
    tabla = Table(filas, colWidths=[ancho * 0.04, ancho * 0.46, ancho * 0.04, ancho * 0.46])
    tabla.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BACKGROUND", (0, 0), (0, 0), COLOR_VERDE),
        ("BACKGROUND", (0, 1), (0, 1), COLOR_AMARILLO),
        ("BACKGROUND", (2, 0), (2, 0), COLOR_AMARILLO),
        ("BACKGROUND", (2, 1), (2, 1), COLOR_ROJO),
        ("FONTNAME", (2, 0), (2, 0), FUENTE_NEGRITA),
        ("ALIGN", (2, 0), (2, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (0, 0), _GROSOR_GRUESO, "#000000"),
        ("BOX", (0, 1), (0, 1), _GROSOR_GRUESO, "#000000"),
        ("BOX", (2, 0), (2, 0), _GROSOR_GRUESO, "#000000"),
        ("BOX", (2, 1), (2, 1), _GROSOR_GRUESO, "#000000"),
    ]))
    return tabla
