"""PDF de liquidación mensual (Etapa 7, sección 4.5).

Se construye sobre `negocio.liquidaciones.Liquidacion`: no recalcula nada,
solo formatea lo que `calcular_liquidacion`/`emitir_liquidacion` ya
produjeron. El orden de los ítems de la cuenta es el de DC-01 §1.10 (el
mismo que usa `liquidaciones.calcular_liquidacion`) — reemplaza al orden de
la sección 4.5 del documento v1.0 original, que los documentos
complementarios dejaron desactualizado (ya no existe "descuento
bonificación": la categoría B nunca se liquida).

Las secciones "Bloques horarios regulares reservados", "Consultorios y
horas utilizadas", "Valores vigentes por edificio", "Esquema de
descuentos" y "Disponibilidad" no tienen un layout detallado en la versión
del documento disponible (remite a versiones v2/v3 no incluidas acá) — se
implementaron con un criterio razonable a partir de los datos existentes,
para ajustar una vez que se puedan revisar contra un ejemplo real.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta

from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from app.negocio.dias import fecha_a_dia_semana, parsear_periodo, primer_dia_mes, ultimo_dia_mes
from app.negocio.grilla import calcular_grilla
from app.negocio.liquidaciones import Liquidacion, ids_consolidados
from app.pdf.estilos import (
    COLOR_AMARILLO,
    COLOR_NARANJA,
    COLOR_ROJO,
    COLOR_VERDE,
    FUENTE,
    FUENTE_NEGRITA,
    FUENTE_NEGRITA_ITALICA,
    crear_documento,
    encabezado,
    estilo_texto,
    formatear_moneda,
)
from app.pdf.numeros_en_letras import monto_en_letras
from app.repositorio.registro import obtener_repositorio

DIAS_SEMANA_ORDEN = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
_COLOR_CELDA = {"verde": COLOR_VERDE, "amarillo": COLOR_AMARILLO, "naranja": COLOR_NARANJA, "rojo": COLOR_ROJO}


def _nombre_archivo(periodo: str, profesional: sqlite3.Row) -> str:
    tratamiento = profesional["Tratamiento"] or ""
    nombre = profesional["NombrePila"] or ""
    apellido = profesional["Apellido"]
    partes = " ".join(p for p in (tratamiento, nombre, apellido) if p)
    return f"{periodo} - {partes} - Liquidación mensual.pdf"


def _edificios_de_bloques(bloques: list[sqlite3.Row]) -> list[sqlite3.Row]:
    vistos: dict[int, sqlite3.Row] = {}
    for b in bloques:
        vistos.setdefault(b["IdEdificio"], b)
    return list(vistos.values())


def _bloques_horarios(conn: sqlite3.Connection, ids: list[int], fecha_referencia: str) -> list[sqlite3.Row]:
    placeholders = ", ".join("?" for _ in ids)
    filas = conn.execute(
        f"""
        SELECT rr.DiaSemana, rr.HoraInicio, rr.HoraFin, c.NumeroConsultorio,
               u.Departamento, e.Nombre AS NombreEdificio, e.Domicilio, e.DomicilioLocalidad,
               e.IdEdificio
        FROM ReservaRegular rr
        JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio
        JOIN Unidad u ON u.IdUnidad = c.IdUnidad
        JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE rr.IdProfesional IN ({placeholders})
          AND rr.VigenciaInicio <= ? AND (rr.VigenciaFin IS NULL OR rr.VigenciaFin >= ?)
        """,
        (*ids, fecha_referencia, fecha_referencia),
    ).fetchall()
    return sorted(filas, key=lambda f: (DIAS_SEMANA_ORDEN.index(f["DiaSemana"]), f["HoraInicio"]))


def _consultorios_y_horas(
    conn: sqlite3.Connection, ids: list[int], primer_dia: str, ultimo_dia: str,
) -> list[tuple[str, float, float]]:
    """Horas y bruto del período agrupados por consultorio (misma lógica
    día-por-día que `liquidaciones._bruto_y_tramos`, pero desglosada por
    consultorio en vez de por día: la suma de esta tabla da `bruto`)."""
    placeholders = ", ".join("?" for _ in ids)
    acumulado: dict[int, list] = {}
    dia = date.fromisoformat(primer_dia)
    fin = date.fromisoformat(ultimo_dia)
    while dia <= fin:
        fecha_iso = dia.isoformat()
        filas = conn.execute(
            f"""
            SELECT rr.IdConsultorio, rr.HoraInicio, rr.HoraFin, c.ValorHoraRegularActual,
                   c.NumeroConsultorio, u.Departamento, e.Nombre AS NombreEdificio
            FROM ReservaRegular rr
            JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio
            JOIN Unidad u ON u.IdUnidad = c.IdUnidad
            JOIN Edificio e ON e.IdEdificio = u.IdEdificio
            WHERE rr.IdProfesional IN ({placeholders}) AND rr.DiaSemana = ?
              AND rr.VigenciaInicio <= ? AND (rr.VigenciaFin IS NULL OR rr.VigenciaFin >= ?)
            """,
            (*ids, fecha_a_dia_semana(dia), fecha_iso, fecha_iso),
        ).fetchall()
        for f in filas:
            horas = f["HoraFin"] - f["HoraInicio"]
            monto = horas * f["ValorHoraRegularActual"]
            clave = f["IdConsultorio"]
            if clave not in acumulado:
                nombre = f"{f['NombreEdificio']} - {f['Departamento']} - Consultorio {f['NumeroConsultorio']}"
                acumulado[clave] = [nombre, 0.0, 0.0]
            acumulado[clave][1] += horas
            acumulado[clave][2] += monto
        dia += timedelta(days=1)
    return [tuple(v) for v in acumulado.values()]


def _valores_vigentes_por_edificio(conn: sqlite3.Connection, edificios: list[sqlite3.Row]) -> list[tuple]:
    resultado = []
    for ed in edificios:
        consultorios = conn.execute(
            """
            SELECT c.NumeroConsultorio, u.Departamento, c.ValorHoraRegularActual, c.ValorHoraAisladaActual
            FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad
            WHERE u.IdEdificio = ? ORDER BY u.Departamento, c.NumeroConsultorio
            """,
            (ed["IdEdificio"],),
        ).fetchall()
        resultado.append((ed["NombreEdificio"], consultorios))
    return resultado


def _esquema_descuentos_vigente(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM EsquemaDescuentos WHERE Activo = 1 ORDER BY HorasSemanalesDesde"
    ).fetchall()


def _condiciones_normas(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM CondicionNorma WHERE Activo = 1 ORDER BY Numero"
    ).fetchall()


def _items_cuenta(liquidacion: Liquidacion) -> list[tuple[str, float | None, bool]]:
    """(concepto, importe, es_subtotal) en el orden de DC-01 §1.10. Los
    ítems compuestos por varias líneas (feriados, cargos especiales, etc.)
    se listan uno por uno; `importe=None` marca una línea de sub-encabezado
    sin importe propio."""
    items: list[tuple[str, float | None, bool]] = []
    items.append(("Bruto", liquidacion.bruto, False))
    items.append((
        f"Descuento por horas semanales ({liquidacion.horas_semanales:g} hs, "
        f"{'0% — pierde descuento' if liquidacion.pierde_descuento_horas else f'{liquidacion.descuento_horas_pct:g}%'})",
        -(liquidacion.bruto - liquidacion.subtotal_reserva), False,
    ))
    items.append(("Subtotal reserva", liquidacion.subtotal_reserva, True))
    items.append(("Saldo anterior", liquidacion.saldo_anterior, False))
    for f in liquidacion.descuentos_feriados:
        items.append((f"Descuento feriado {f.fecha}", -f.monto, False))
    for f in liquidacion.descuentos_no_laborables:
        items.append((f"Descuento no laborable {f.fecha}", -f.monto, False))
    for f in liquidacion.feriados_pendientes:
        items.append((f"Feriado pendiente mes anterior {f.fecha}", -f.monto, False))
    if liquidacion.descuento_vacaciones:
        items.append(("Descuento vacaciones", -liquidacion.descuento_vacaciones, False))
    if liquidacion.descuento_licencias:
        items.append(("Descuento licencias", -liquidacion.descuento_licencias, False))
    for h in liquidacion.horas_regulares_agregadas:
        items.append((f"Horas regulares agregadas ({h.dia_semana} desde {h.vigencia_inicio})", h.monto, False))
    for f in liquidacion.feriados_trabajados_mes_anterior:
        items.append((f"Feriado trabajado mes anterior {f.fecha}", f.monto, False))
    for f in liquidacion.feriados_trabajados_mes_en_curso:
        items.append((f"Feriado trabajado {f.fecha}", f.monto, False))
    if liquidacion.aisladas_mes_anterior:
        items.append(("Aisladas mes anterior", liquidacion.aisladas_mes_anterior, False))
    if liquidacion.aisladas_mes_en_curso:
        items.append(("Aisladas mes en curso", liquidacion.aisladas_mes_en_curso, False))
    if liquidacion.ajuste_saldo_atrasado:
        items.append(("Ajuste por saldo atrasado", liquidacion.ajuste_saldo_atrasado, False))
    for c in liquidacion.cargos_especiales:
        signo = 1 if c["Tipo"] == "Débito" else -1
        etiqueta = "Depósito/Reintegro llave" if c["IdLlave"] else "Ítem libre"
        items.append((f"{etiqueta}: {c['Concepto']}", signo * c["Monto"], False))
    for c in liquidacion.cuotas_plan:
        items.append((f"Cuota plan de pagos #{c['NumeroCuota']}", c["Monto"], False))
    items.append(("TOTAL", liquidacion.total, True))
    return items


def _tabla_items(liquidacion: Liquidacion, ancho: float) -> Table:
    filas = [["Concepto", "Importe"]]
    estilo = [
        ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA),
        ("FONTNAME", (0, 1), (-1, -1), FUENTE),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, "#999999"),
        ("BACKGROUND", (0, 0), (-1, 0), "#DDDDDD"),
    ]
    for i, (concepto, importe, es_subtotal) in enumerate(_items_cuenta(liquidacion), start=1):
        filas.append([concepto, formatear_moneda(importe)])
        if es_subtotal:
            estilo.append(("FONTNAME", (0, i), (-1, i), FUENTE_NEGRITA))
    tabla = Table(filas, colWidths=[ancho * 0.75, ancho * 0.25], repeatRows=1)
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _total_recuadro(liquidacion: Liquidacion, ancho: float) -> Table:
    tabla = Table(
        [
            ["Total", formatear_moneda(liquidacion.total)],
            [monto_en_letras(liquidacion.total), ""],
        ],
        colWidths=[ancho * 0.75, ancho * 0.25],
    )
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA_ITALICA),
        ("FONTNAME", (0, 1), (0, 1), FUENTE),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("SPAN", (0, 1), (1, 1)),
        ("BOX", (0, 0), (-1, -1), 1, "#000000"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, "#000000"),
    ]))
    return tabla


def generar_pdf_liquidacion(conn: sqlite3.Connection, liquidacion: Liquidacion, directorio: str) -> str:
    """Genera el PDF de liquidación mensual y devuelve la ruta completa del
    archivo creado (`directorio` debe existir)."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(liquidacion.id_profesional)
    cfg = conn.execute("SELECT * FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"

    ids = ids_consolidados(conn, liquidacion.id_profesional)
    anio, mes = parsear_periodo(liquidacion.periodo)
    primer_dia = primer_dia_mes(anio, mes).isoformat()
    ultimo_dia = ultimo_dia_mes(anio, mes).isoformat()

    ruta = os.path.join(directorio, _nombre_archivo(liquidacion.periodo, profesional))
    doc, ancho = crear_documento(ruta)
    style_texto = estilo_texto(9)
    style_nota = estilo_texto(7, italica=True)
    story = []

    story.append(encabezado(1, f"{nombre_espacio} - Liquidación mensual", ancho))
    story.append(Spacer(1, 6))

    bloques = _bloques_horarios(conn, ids, ultimo_dia)
    story.append(encabezado(2, "Bloques horarios regulares reservados", ancho))
    if bloques:
        filas = [["Día", "Horario", "Consultorio"]]
        for b in bloques:
            filas.append([
                b["DiaSemana"], f"{b['HoraInicio']:g} a {b['HoraFin']:g} hs",
                f"{b['NombreEdificio']} - {b['Departamento']} - Consultorio {b['NumeroConsultorio']}",
            ])
        tabla = Table(filas, colWidths=[ancho * 0.2, ancho * 0.25, ancho * 0.55], repeatRows=1)
        tabla.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA), ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, "#999999"), ("BACKGROUND", (0, 0), (-1, 0), "#DDDDDD"),
        ]))
        story.append(tabla)
    else:
        story.append(Paragraph("Sin bloques horarios regulares vigentes.", style_texto))
    for ed in _edificios_de_bloques(bloques):
        story.append(Paragraph(
            f"* Edificio {ed['NombreEdificio']}: Corresponde a {ed['Domicilio']}, {ed['DomicilioLocalidad']}",
            style_nota,
        ))
    story.append(Spacer(1, 8))

    story.append(encabezado(1, f"Liquidación mensual {liquidacion.periodo}", ancho))
    story.append(Spacer(1, 4))
    story.append(_tabla_items(liquidacion, ancho))
    story.append(Spacer(1, 4))
    story.append(_total_recuadro(liquidacion, ancho))
    story.append(Spacer(1, 8))

    story.append(encabezado(2, "Consultorios y horas utilizadas", ancho))
    filas_ch = [["Consultorio", "Horas del período", "Bruto del período"]]
    for nombre, horas, monto in _consultorios_y_horas(conn, ids, primer_dia, ultimo_dia):
        filas_ch.append([nombre, f"{horas:g}", formatear_moneda(monto)])
    tabla_ch = Table(filas_ch, colWidths=[ancho * 0.55, ancho * 0.2, ancho * 0.25], repeatRows=1)
    tabla_ch.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), 0.4, "#999999"),
        ("BACKGROUND", (0, 0), (-1, 0), "#DDDDDD"),
    ]))
    story.append(tabla_ch)
    story.append(Spacer(1, 8))

    for nombre_ed, consultorios in _valores_vigentes_por_edificio(conn, _edificios_de_bloques(bloques)):
        story.append(encabezado(3, f"Valores vigentes — Edificio {nombre_ed}", ancho))
        filas_v = [["Unidad", "Consultorio", "Valor hora regular", "Valor hora aislada"]]
        for c in consultorios:
            filas_v.append([
                c["Departamento"], str(c["NumeroConsultorio"]),
                formatear_moneda(c["ValorHoraRegularActual"]), formatear_moneda(c["ValorHoraAisladaActual"]),
            ])
        tabla_v = Table(filas_v, colWidths=[ancho * 0.25, ancho * 0.25, ancho * 0.25, ancho * 0.25], repeatRows=1)
        tabla_v.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA), ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), 0.3, "#999999"),
        ]))
        story.append(tabla_v)
        story.append(Spacer(1, 4))

    story.append(encabezado(2, "Esquema de descuentos", ancho))
    filas_e = [["Desde (hs)", "Hasta (hs)", "% descuento"]]
    for e in _esquema_descuentos_vigente(conn):
        filas_e.append([f"{e['HorasSemanalesDesde']:g}", f"{e['HorasSemanalesHasta']:g}", f"{e['PorcentajeDescuento']:g}%"])
    tabla_e = Table(filas_e, colWidths=[ancho / 3] * 3, repeatRows=1)
    tabla_e.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("GRID", (0, 0), (-1, -1), 0.4, "#999999"),
        ("BACKGROUND", (0, 0), (-1, 0), "#DDDDDD"),
    ]))
    story.append(tabla_e)
    story.append(Spacer(1, 8))

    story.append(encabezado(2, "Recordatorios", ancho))
    ajuste_pct = cfg["PorcentajeAjusteSaldoAtrasado"] if cfg else 0
    story.append(Paragraph(
        "* Abonar el total liquidado dentro del mes en curso para mantener los descuentos "
        "en el próximo período.", style_nota,
    ))
    story.append(Paragraph(
        f"* Los saldos pendientes que se trasladan de un mes a otro reciben un ajuste del "
        f"{ajuste_pct:g}% para mantener los mismos actualizados.", style_nota,
    ))
    story.append(Spacer(1, 8))

    story.append(encabezado(2, "Disponibilidad", ancho))
    story.append(_grilla_disponibilidad(conn, anio, mes, ancho))
    story.append(Spacer(1, 8))

    condiciones = _condiciones_normas(conn)
    if condiciones:
        story.append(encabezado(2, "Condiciones y normas", ancho))
        for c in condiciones:
            story.append(Paragraph(f"<b>{c['Numero']}. {c['Titulo']}:</b> {c['Texto']}", style_texto))

    doc.build(story)
    return ruta


_ORDEN_COLOR = {"rojo": 0, "naranja": 1, "amarillo": 2, "verde": 3}


def _grilla_disponibilidad(conn: sqlite3.Connection, anio: int, mes: int, ancho: float) -> KeepTogether:
    """Resumen diario (no hora por hora: no entra en el ancho de una hoja
    A4 junto con el resto del PDF) — cada celda es el PEOR color de
    disponibilidad de esa unidad en ese día, sección 4.2. Filas = días,
    columnas = unidades, como indica la grilla normal del documento."""
    cfg = conn.execute(
        "SELECT HoraInicioGrilla, HoraFinGrilla FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    hora_ini = int(cfg["HoraInicioGrilla"]) if cfg else 8
    hora_fin = int(cfg["HoraFinGrilla"]) if cfg else 22
    dias = DIAS_SEMANA_ORDEN[:6]  # Lunes a Sábado

    grilla = calcular_grilla(conn, anio, mes, hora_ini, hora_fin, dias)
    unidades = conn.execute(
        """
        SELECT u.IdUnidad, u.Departamento, e.Nombre AS NombreEdificio
        FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        ORDER BY e.Nombre, u.Departamento
        """
    ).fetchall()

    encabezados = ["Día"] + [f"{u['NombreEdificio']} - {u['Departamento']}" for u in unidades]
    filas = [encabezados]
    fondos = []
    for fila_idx, dia in enumerate(dias, start=1):
        fila = [dia]
        for col_idx, u in enumerate(unidades, start=1):
            colores_dia = [grilla.get((u["IdUnidad"], dia, h), "rojo") for h in range(hora_ini, hora_fin)]
            peor = min(colores_dia, key=lambda c: _ORDEN_COLOR[c]) if colores_dia else "rojo"
            fila.append("")
            fondos.append((peor, fila_idx, col_idx))
        filas.append(fila)

    ancho_dia = ancho * 0.15
    ancho_unidad = (ancho - ancho_dia) / max(len(unidades), 1)
    tabla = Table(filas, colWidths=[ancho_dia] + [ancho_unidad] * len(unidades), repeatRows=1)
    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), FUENTE_NEGRITA), ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.3, "#999999"), ("BACKGROUND", (0, 0), (0, -1), "#6B0000"),
        ("TEXTCOLOR", (0, 0), (0, -1), "#FFFFFF"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for color, fila, col in fondos:
        estilo.append(("BACKGROUND", (col, fila), (col, fila), _COLOR_CELDA[color]))
    tabla.setStyle(TableStyle(estilo))

    leyenda = Paragraph(
        "Verde: 2 o más consultorios disponibles &nbsp;·&nbsp; Amarillo: 1 disponible con ventana "
        "&nbsp;·&nbsp; Naranja: 1 disponible sin ventana &nbsp;·&nbsp; Rojo: sin disponibilidad. "
        "Cada celda muestra el peor color del día (resumen; no hora por hora).",
        estilo_texto(6, italica=True),
    )
    return KeepTogether([tabla, Spacer(1, 3), leyenda])
