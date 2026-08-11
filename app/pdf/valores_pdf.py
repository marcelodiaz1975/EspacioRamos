"""Valores vigentes de consultorios y esquema de descuentos, compartidos
por el PDF de Liquidación y el de Propuesta (secciones 4.5/4.3)."""
from __future__ import annotations

import sqlite3

from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.pdf.estilos import COLOR_NIVEL_1, FUENTE_NEGRITA, estilo_texto, formatear_moneda


def rango_actualizacion(conn: sqlite3.Connection, periodo: str) -> tuple[str, str]:
    """(desde, hasta) — el período del último aumento aplicado hasta
    `periodo` (o `periodo` mismo si nunca hubo uno), para el título
    "Valores... para el período comprendido entre X y Y"."""
    fila = conn.execute(
        "SELECT MAX(Periodo) AS p FROM AumentoAplicado WHERE Periodo <= ?", (periodo,)
    ).fetchone()
    desde = fila["p"] if fila and fila["p"] else periodo
    return desde, periodo


def matriz_valores_edificio(
    conn: sqlite3.Connection, id_edificio: int, ancho: float, anonimizar_unidad: bool = False,
) -> list:
    """Tabla Unidad (filas) x Consultorio N (columnas) -> ValorHoraRegularActual,
    con "—" para los números de consultorio que no existen en esa unidad.
    `anonimizar_unidad` muestra "Unidad {IdUnidad}" en vez del Departamento
    real (sección 4.3, PDF de Propuesta, que va a profesionales NO
    activos)."""
    filas_bd = conn.execute(
        """
        SELECT u.IdUnidad, u.Departamento, c.NumeroConsultorio, c.ValorHoraRegularActual
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad
        WHERE u.IdEdificio = ? ORDER BY u.Departamento, c.NumeroConsultorio
        """,
        (id_edificio,),
    ).fetchall()
    por_unidad: dict[str, dict[int, float]] = {}
    for f in filas_bd:
        etiqueta = f"Unidad {f['IdUnidad']}" if anonimizar_unidad else f["Departamento"]
        por_unidad.setdefault(etiqueta, {})[f["NumeroConsultorio"]] = f["ValorHoraRegularActual"]
    max_consultorios = max((max(v.keys()) for v in por_unidad.values()), default=0)
    if max_consultorios == 0:
        return [Paragraph("Sin consultorios cargados.", estilo_texto(9))]

    encabezado_fila = ["Unidad"] + [f"Consul. {n}" for n in range(1, max_consultorios + 1)]
    filas = [encabezado_fila]
    for unidad, valores in por_unidad.items():
        filas.append(
            [unidad] + [formatear_moneda(valores[n]) if n in valores else "—" for n in range(1, max_consultorios + 1)]
        )

    ancho_unidad = ancho * 0.18
    ancho_col = (ancho - ancho_unidad) / max_consultorios
    tabla = Table(filas, colWidths=[ancho_unidad] + [ancho_col] * max_consultorios, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA), ("FONTNAME", (0, 1), (0, -1), FUENTE_NEGRITA),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, "#000000"), ("BACKGROUND", (0, 0), (-1, 0), COLOR_NIVEL_1),
        ("TEXTCOLOR", (0, 0), (-1, 0), "#FFFFFF"), ("BACKGROUND", (0, 1), (0, -1), "#F0F0F0"),
    ]))
    return [tabla]


def bloques_esquema_descuentos(conn: sqlite3.Connection, ancho: float) -> list:
    """Bloques horizontales de a 9 tramos ("Hs. semanales" / "Descuento")."""
    tramos = conn.execute(
        "SELECT * FROM EsquemaDescuentos WHERE Activo = 1 ORDER BY HorasSemanalesDesde"
    ).fetchall()
    if not tramos:
        return [Paragraph("Sin esquema de descuentos configurado.", estilo_texto(9))]

    story = []
    por_bloque = 9
    for inicio in range(0, len(tramos), por_bloque):
        grupo = tramos[inicio:inicio + por_bloque]
        fila_horas = ["Hs. semanales"] + [f"Hasta {t['HorasSemanalesHasta']:g}hs" for t in grupo]
        fila_desc = ["Descuento"] + [f"{t['PorcentajeDescuento']:g}%" for t in grupo]
        n = len(grupo)
        ancho_col = ancho / (n + 1)
        tabla = Table([fila_horas, fila_desc], colWidths=[ancho_col] * (n + 1))
        tabla.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), FUENTE_NEGRITA), ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, "#000000"),
            ("BACKGROUND", (0, 0), (0, -1), "#6B0000"), ("TEXTCOLOR", (0, 0), (0, -1), "#FFFFFF"),
            ("BACKGROUND", (1, 0), (-1, 0), "#6B0000"), ("TEXTCOLOR", (1, 0), (-1, 0), "#FFFFFF"),
        ]))
        story.append(tabla)
        story.append(Spacer(1, 4))
    return story


def condiciones_normas(conn: sqlite3.Connection) -> list:
    """Los 21 puntos editables de "Condiciones y normas" (CondicionNorma),
    numerados "N) TÍTULO:" en mayúsculas — mismo formato en Liquidación y
    Propuesta."""
    condiciones = conn.execute("SELECT * FROM CondicionNorma WHERE Activo = 1 ORDER BY Numero").fetchall()
    style = estilo_texto(9)
    return [Paragraph(f"<b>{c['Numero']}) {c['Titulo'].upper()}:</b> {c['Texto']}", style) for c in condiciones]
