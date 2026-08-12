"""Valores vigentes de consultorios y esquema de descuentos, compartidos
por el PDF de Liquidación y el de Propuesta (secciones 4.5/4.3)."""
from __future__ import annotations

import json
import sqlite3

from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.pdf.estilos import COLOR_NIVEL_1, FUENTE_NEGRITA, decimales_configurados, estilo_texto, formatear_moneda


def _hasta_por_frecuencia(desde: str, meses_actualizacion: list[int]) -> str:
    """Último mes en que el valor de `desde` sigue vigente: el mes
    anterior al próximo mes de actualización programado (envolviendo al
    año siguiente si hace falta). Ej: actualización bimestral en meses
    pares, `desde`="2026-08" -> próxima actualización en 10, vigente
    hasta "2026-09". Semestral en enero/julio, `desde`="2026-07" ->
    próxima actualización en 01/2027, vigente hasta "2026-12"."""
    anio, mes = (int(p) for p in desde.split("-"))
    meses_ordenados = sorted(set(meses_actualizacion))
    siguientes = [m for m in meses_ordenados if m > mes]
    if siguientes:
        proximo_mes, proximo_anio = siguientes[0], anio
    else:
        proximo_mes, proximo_anio = meses_ordenados[0], anio + 1
    mes_hasta, anio_hasta = proximo_mes - 1, proximo_anio
    if mes_hasta == 0:
        mes_hasta, anio_hasta = 12, anio_hasta - 1
    return f"{anio_hasta:04d}-{mes_hasta:02d}"


def rango_actualizacion(conn: sqlite3.Connection, periodo: str) -> tuple[str, str]:
    """(desde, hasta) — el período del último aumento aplicado hasta
    `periodo` (o `periodo` mismo si nunca hubo uno) como `desde`, y el
    último mes en que ese valor sigue vigente según
    `Configuracion.MesesPeriodoActualizacion` como `hasta`. Si no hay
    frecuencia configurada, `hasta` queda igual a `desde` — mostrar un
    rango inventado sería peor que no mostrar rango."""
    fila = conn.execute(
        "SELECT MAX(Periodo) AS p FROM AumentoAplicado WHERE Periodo <= ?", (periodo,)
    ).fetchone()
    desde = fila["p"] if fila and fila["p"] else periodo

    cfg = conn.execute(
        "SELECT MesesPeriodoActualizacion FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    meses = json.loads(cfg["MesesPeriodoActualizacion"]) if cfg and cfg["MesesPeriodoActualizacion"] else []
    hasta = _hasta_por_frecuencia(desde, meses) if meses else desde
    return desde, hasta


def matriz_valores_edificio(
    conn: sqlite3.Connection, id_edificio: int, ancho: float, anonimizar_unidad: bool = False,
) -> list:
    """Tabla Unidad (filas) x Consultorio N (columnas) -> ValorHoraRegularActual,
    con "—" para los números de consultorio que no existen en esa unidad.
    `anonimizar_unidad` muestra "Unidad {IdUnidad}" en vez del Departamento
    real (sección 4.3, PDF de Propuesta, que va a profesionales NO
    activos)."""
    decimales = decimales_configurados(conn)
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
            [unidad]
            + [formatear_moneda(valores[n], decimales) if n in valores else "—" for n in range(1, max_consultorios + 1)]
        )

    ancho_unidad = ancho * 0.18
    ancho_col = (ancho - ancho_unidad) / max_consultorios
    tabla = Table(filas, colWidths=[ancho_unidad] + [ancho_col] * max_consultorios, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, "#000000"), ("BACKGROUND", (0, 0), (-1, 0), COLOR_NIVEL_1),
        ("TEXTCOLOR", (0, 0), (-1, 0), "#FFFFFF"), ("BACKGROUND", (0, 1), (0, -1), "#F0F0F0"),
    ]))
    return [tabla]


def bloques_esquema_descuentos(conn: sqlite3.Connection, ancho: float) -> list:
    """Bloques horizontales de a 9 tramos ("Hs. semanales" / "Descuento").

    Si la cantidad de tramos no es múltiplo de 9, la última fila queda con
    menos columnas que las anteriores — para que las filas se vean parejas
    se completa con tramos "de relleno" que repiten el % tope (el de más
    horas semanales), incrementando "Hasta Nhs" con el mismo paso que ya
    usan los tramos reales. Así, si en el futuro se agregan o sacan
    tramos, la última fila se sigue completando sola."""
    tramos = conn.execute(
        "SELECT * FROM EsquemaDescuentos WHERE Activo = 1 ORDER BY HorasSemanalesDesde"
    ).fetchall()
    if not tramos:
        return [Paragraph("Sin esquema de descuentos configurado.", estilo_texto(9))]

    por_bloque = 9
    faltan = (-len(tramos)) % por_bloque
    if faltan:
        paso = tramos[-1]["HorasSemanalesHasta"] - tramos[-2]["HorasSemanalesHasta"] if len(tramos) >= 2 else 2
        tope_pct = max(t["PorcentajeDescuento"] for t in tramos)
        ultimo_hasta = tramos[-1]["HorasSemanalesHasta"]
        relleno = []
        for _ in range(faltan):
            ultimo_hasta += paso
            relleno.append({"HorasSemanalesHasta": ultimo_hasta, "PorcentajeDescuento": tope_pct})
        tramos = list(tramos) + relleno

    story = []
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
            ("BACKGROUND", (0, 0), (0, -1), COLOR_NIVEL_1), ("TEXTCOLOR", (0, 0), (0, -1), "#FFFFFF"),
            ("BACKGROUND", (1, 0), (-1, 0), COLOR_NIVEL_1), ("TEXTCOLOR", (1, 0), (-1, 0), "#FFFFFF"),
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
