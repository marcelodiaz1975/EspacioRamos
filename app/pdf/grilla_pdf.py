"""Grilla completa de disponibilidad hora por hora, agrupada por edificio
(sección 4.2) — reusada tanto en el PDF de Disponibilidad standalone
(Etapa 7, sección 4.4) como en la sección "Disponibilidad" embebida en el
PDF de Liquidación (sección 4.5), siguiendo el modelo real: filas =
Tipo de bloque (Rígido/Flexible, según BloqueRigido) + Horario, columnas
= Día > Unidad. Las celdas "naranja" (un solo consultorio disponible SIN
ventana) se pintan del mismo color que "amarillo" pero con la leyenda
"S/V" superpuesta, para distinguirlas sin agregar un quinto color."""
from __future__ import annotations

import sqlite3

from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from app.negocio.dias import DIAS_SEMANA
from app.negocio.formato import hora_fmt
from app.negocio.grilla import calcular_grilla
from app.pdf.estilos import (
    COLOR_AMARILLO,
    COLOR_NIVEL_3,
    COLOR_ROJO,
    COLOR_VERDE,
    FUENTE_NEGRITA,
    encabezado,
    estilo_texto,
)

DIAS_GRILLA_DEFAULT = DIAS_SEMANA[:6]  # Lunes a Sábado
_COLOR_CELDA = {"verde": COLOR_VERDE, "amarillo": COLOR_AMARILLO, "naranja": COLOR_AMARILLO, "rojo": COLOR_ROJO}


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

    # Con muchas unidades por edificio la columna por consultorio se vuelve
    # angosta (varios edificios reales tienen 4+ unidades) — una celda de
    # texto plano no ajusta el contenido y termina desbordando sobre la
    # celda vecina, así que la etiqueta de unidad va en un Paragraph que
    # puede partirse en dos líneas, con una fuente que se achica si la
    # columna es angosta en vez de desbordar.
    tamano_etiqueta = 6 if ancho_col >= 40 else 5 if ancho_col >= 28 else 4
    style_etiqueta = estilo_texto(tamano_etiqueta, negrita=True, alignment=TA_CENTER)

    fila_dias = ["Tipo\nBloque", "Horario"] + [d.upper() for d in dias for _ in unidades]
    fila_unidad_label = ["", ""] + ["Unidad" for _ in dias for _ in unidades]
    fila_unidades = ["", ""] + [
        Paragraph(_etiqueta_unidad(u, anonimizar_unidad), style_etiqueta) for _ in dias for u in unidades
    ]
    filas = [fila_dias, fila_unidad_label, fila_unidades]

    fondos = []
    spans = []
    tipo_anterior, inicio_grupo = None, None
    for fila_idx, h in enumerate(horas, start=3):
        fila = ["", hora_fmt(h)]
        tipo = tipo_por_hora[h]
        if tipo != tipo_anterior:
            if tipo_anterior is not None:
                spans.append(("SPAN", (0, inicio_grupo), (0, fila_idx - 1)))
            inicio_grupo, tipo_anterior = fila_idx, tipo
        for dia in dias:
            for u in unidades:
                color = grilla.get((u["IdUnidad"], dia, h), "rojo")
                fila.append("S/V" if color == "naranja" else "")
                fondos.append((color, fila_idx, len(fila) - 1))
        filas.append(fila)
    spans.append(("SPAN", (0, inicio_grupo), (0, len(horas) + 2)))

    for fila_idx, h in enumerate(horas, start=3):
        filas[fila_idx][0] = tipo_por_hora[h]

    col_widths = [ancho_tipo, ancho_horario] + [ancho_col] * n_cols_datos
    tabla = Table(filas, colWidths=col_widths, repeatRows=3)

    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), FUENTE_NEGRITA),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.3, "#999999"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (1, 2), COLOR_NIVEL_3),
        ("TEXTCOLOR", (0, 0), (1, 2), "#FFFFFF"),
        ("BACKGROUND", (2, 0), (-1, 1), "#6B0000"),
        ("TEXTCOLOR", (2, 0), (-1, 1), "#FFFFFF"),
        ("BACKGROUND", (2, 2), (-1, 2), "#2E86AB"),
        ("TEXTCOLOR", (2, 2), (-1, 2), "#FFFFFF"),
    ]
    idx = 2
    for dia in dias:
        estilo.append(("SPAN", (idx, 0), (idx + n_unidades - 1, 0)))
        estilo.append(("SPAN", (idx, 1), (idx + n_unidades - 1, 1)))
        idx += n_unidades
    estilo.extend(spans)
    for color, fila, col in fondos:
        estilo.append(("BACKGROUND", (col, fila), (col, fila), _COLOR_CELDA[color]))
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

    story = [encabezado(2, f"Disponibilidad de consultorios al {fecha_titulo}", ancho)]
    for id_edificio, unidades_ed in por_edificio.items():
        bloque = [
            encabezado(3, f"Edificio {nombres[id_edificio]}", ancho),
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
    ]))
    return tabla
