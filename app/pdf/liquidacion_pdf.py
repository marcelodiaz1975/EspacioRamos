"""PDF de liquidación mensual (Etapa 7, sección 4.5), reconstruido sobre un
modelo real ya generado por el sistema previo (no sobre la redacción
original de la sección 4.5 del documento, que quedó desactualizada).

Estructura, de arriba a abajo:
    Título + subtítulo + línea
    Nivel 1: "Detalle reserva {MM/AAAA} - {Tratamiento} {Nombre} {Apellido}"
      Nivel 2: Bloques de horarios regulares reservados
      Nivel 2: Liquidación mensual mes en curso (ítems + subtotal + total)
      Nivel 2: Consultorios y cantidad de horas utilizadas
    Nivel 2: Valores de los consultorios para el período X-Y (por edificio)
    Nivel 2: Esquema de descuentos
    Nivel 2: Recordatorios varios para el profesional
    Nivel 2: Disponibilidad de consultorios al {fecha} (por edificio)
    Nivel 2: Condiciones y normas generales de convivencia...

Es una página única continua (no A4 paginado): se estima una altura
generosa a partir del volumen de datos de este profesional en particular
y, si la estimación se queda corta, simplemente se agrega una página de
continuación del mismo ancho — no es un error, es el mismo comportamiento
que tiene el documento modelo (que también deja margen de sobra al final).

El orden y el cálculo de los montos de la cuenta siguen siendo los de
DC-01 §1.10 (los que ya usa `negocio.liquidaciones`) — categoría B nunca
se liquida, categoría E se consolida en la de su R.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from math import ceil

from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.negocio.dias import DIAS_SEMANA, fecha_actual, parsear_periodo, primer_dia_mes, ultimo_dia_mes
from app.negocio.feriados import feriados_relevantes_periodo
from app.negocio.formato import fecha_corta, fecha_larga, hora_fmt, mes_texto, periodo_mm_aaaa
from app.negocio.liquidaciones import Liquidacion, ids_consolidados
from app.negocio.formato import decimales_configurados, formatear_moneda
from app.pdf.estilos import (
    COLOR_NIVEL_1,
    COLOR_ROJO,
    FUENTE,
    FUENTE_NEGRITA,
    FUENTE_NEGRITA_ITALICA,
    construir_sin_saltos,
    encabezado,
    encabezado_espacio,
    estilo_texto,
)
from app.pdf.fotos_pdf import imagenes_de_consultorios, tabla_fotos
from app.pdf.grilla_pdf import altura_estimada_grilla, secciones_disponibilidad
from app.pdf.numeros_en_letras import en_letras_pesos
from app.pdf.valores_pdf import (
    bloques_esquema_descuentos,
    condiciones_normas,
    matriz_valores_edificio,
    rango_actualizacion,
)
from app.repositorio.registro import obtener_repositorio


def _nombre_archivo(periodo: str, profesional: sqlite3.Row) -> str:
    tratamiento = profesional["Tratamiento"] or ""
    nombre = profesional["NombrePila"] or ""
    apellido = profesional["Apellido"]
    partes = " ".join(p for p in (tratamiento, nombre, apellido) if p)
    return f"{periodo} - Liquidación {partes}.pdf"


def _nombre_completo(profesional: sqlite3.Row) -> str:
    tratamiento = profesional["Tratamiento"] or ""
    nombre = profesional["NombrePila"] or ""
    apellido = profesional["Apellido"]
    return " ".join(p for p in (tratamiento, nombre, apellido) if p)


def _mapa_consultorios(conn: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    filas = conn.execute(
        """
        SELECT c.IdConsultorio, c.NumeroConsultorio, c.Ventana,
               c.ValorHoraRegularActual, c.ValorHoraAisladaActual,
               u.IdUnidad, u.Departamento, e.IdEdificio, e.Nombre AS NombreEdificio,
               e.Domicilio, e.DomicilioLocalidad
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad
        JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        """
    ).fetchall()
    return {f["IdConsultorio"]: f for f in filas}


def _lugar(consultorios: dict, id_consultorio: int) -> str:
    c = consultorios[id_consultorio]
    return f"consul {c['NumeroConsultorio']} del {c['Departamento']} - {c['NombreEdificio']}"


def _ids_consultorio_reservados(conn: sqlite3.Connection, ids: list[int]) -> list[int]:
    placeholders = ", ".join("?" for _ in ids)
    filas = conn.execute(
        f"SELECT DISTINCT IdConsultorio FROM ReservaRegular WHERE IdProfesional IN ({placeholders})", ids,
    ).fetchall()
    return [f["IdConsultorio"] for f in filas]


def _dia_y_fecha(fecha_iso: str) -> tuple[str, str]:
    dia_semana = DIAS_SEMANA[date.fromisoformat(fecha_iso).weekday()]
    return dia_semana, fecha_corta(fecha_iso)


# ------------------------------------------------------------------- bloques horarios

def _bloques_horarios(conn: sqlite3.Connection, ids: list[int]) -> list[sqlite3.Row]:
    placeholders = ", ".join("?" for _ in ids)
    filas = conn.execute(
        f"""
        SELECT rr.DiaSemana, rr.HoraInicio, rr.HoraFin, rr.VigenciaInicio, rr.VigenciaFin,
               c.NumeroConsultorio, u.Departamento, e.Nombre AS NombreEdificio, e.IdEdificio,
               e.Domicilio, e.DomicilioLocalidad
        FROM ReservaRegular rr
        JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio
        JOIN Unidad u ON u.IdUnidad = c.IdUnidad
        JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE rr.IdProfesional IN ({placeholders})
        """,
        ids,
    ).fetchall()
    return sorted(
        filas,
        key=lambda f: (f["NombreEdificio"], DIAS_SEMANA.index(f["DiaSemana"]), f["HoraInicio"]),
    )


def _direccion_edificio(info: sqlite3.Row) -> str:
    partes = [p for p in (info["Domicilio"], info["DomicilioLocalidad"]) if p]
    return ", ".join(partes)


def _notas_direcciones_edificios(edificios: dict[int, sqlite3.Row]) -> list:
    """Aclaración con asterisco de a qué domicilio corresponde cada
    edificio mencionado en la tabla de bloques horarios, ej: "* Edificio
    Ramos 1: Corresponde a Av. Rivadavia 13876, Ramos Mejía."."""
    style = estilo_texto(8)
    story = []
    for info in edificios.values():
        direccion = _direccion_edificio(info)
        if direccion:
            story.append(Paragraph(f"* Edificio {info['NombreEdificio']}: Corresponde a {direccion}.", style))
    return story


def _edificios_para_valores(conn: sqlite3.Connection, edificios_reservados: dict[int, sqlite3.Row]) -> list[sqlite3.Row]:
    """La sección "Valores de los consultorios" lista todos los edificios
    de la(s) localidad(es) donde el profesional reserva, no solo los
    edificios donde reserva puntualmente — si algún día llega a reservar
    en otro edificio de esa misma localidad, ya tiene sus valores a mano.
    Los edificios sin localidad cargada no se pueden agrupar por
    localidad, así que solo entran si el profesional reserva ahí."""
    localidades = {info["DomicilioLocalidad"] for info in edificios_reservados.values() if info["DomicilioLocalidad"]}
    resultado = {id_ed: info for id_ed, info in edificios_reservados.items()}
    if localidades:
        placeholders = ", ".join("?" for _ in localidades)
        filas = conn.execute(
            f"SELECT IdEdificio, Nombre AS NombreEdificio, Domicilio, DomicilioLocalidad FROM Edificio "
            f"WHERE DomicilioLocalidad IN ({placeholders})",
            list(localidades),
        ).fetchall()
        for f in filas:
            resultado.setdefault(f["IdEdificio"], f)
    return sorted(resultado.values(), key=lambda info: info["NombreEdificio"])


def _tabla_bloques_horarios(bloques: list[sqlite3.Row], ancho: float) -> Table:
    filas = [["Edificio", "Día", "Hora inicio", "Hora liberación", "Unidad", "Consultorio", "Vigencia desde", "Vigencia hasta"]]
    for b in bloques:
        filas.append([
            b["NombreEdificio"], b["DiaSemana"], hora_fmt(b["HoraInicio"]), hora_fmt(b["HoraFin"]),
            b["Departamento"], str(b["NumeroConsultorio"]),
            fecha_larga(b["VigenciaInicio"]), fecha_larga(b["VigenciaFin"]),
        ])
    anchos = [ancho * p for p in (0.14, 0.11, 0.11, 0.13, 0.13, 0.11, 0.135, 0.135)]
    tabla = Table(filas, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA), ("FONTNAME", (0, 1), (-1, -1), FUENTE),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.6, "#000000"),
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_NIVEL_1), ("TEXTCOLOR", (0, 0), (-1, 0), "#FFFFFF"),
    ]))
    return tabla


# ---------------------------------------------------------------- ítems de la cuenta

def _texto_horas_agregadas(consultorios: dict, h) -> str:
    return (
        f"Horas regulares agregadas a partir del {h.dia_semana.lower()} {fecha_corta(h.vigencia_inicio)} "
        f"de {hora_fmt(h.hora_inicio)[:-2]} a {hora_fmt(h.hora_fin)} {_lugar(consultorios, h.id_consultorio)}"
    )


def _texto_feriado_trabajado_actual(consultorios: dict, item, tipo: str) -> str:
    concepto = "feriado" if tipo == "Feriado nacional" else "día no laborable"
    return (
        f"Importe con descuento incluido por {concepto} del {fecha_corta(item.fecha)} "
        f"de {hora_fmt(item.hora_inicio)[:-2]} a {hora_fmt(item.hora_fin)} {_lugar(consultorios, item.id_consultorio)}"
    )


def _texto_feriado_trabajado_anterior(consultorios: dict, item, mes_ant_texto: str) -> str:
    dia_semana = DIAS_SEMANA[date.fromisoformat(item.fecha).weekday()]
    return (
        f"Feriado trabajado en {mes_ant_texto}: {dia_semana.lower()} {fecha_corta(item.fecha)} "
        f"de {hora_fmt(item.hora_inicio)[:-2]} a {hora_fmt(item.hora_fin)} {_lugar(consultorios, item.id_consultorio)}"
    )


def _texto_aislada(consultorios: dict, item, verbo: str, mes_texto_opt: str | None) -> str:
    dia_semana = DIAS_SEMANA[date.fromisoformat(item.fecha).weekday()]
    prefijo = f"Hora aislada {verbo} en {mes_texto_opt}: " if mes_texto_opt else f"Hora aislada {verbo}: "
    return (
        f"{prefijo}{dia_semana.lower()} {fecha_corta(item.fecha)} "
        f"de {hora_fmt(item.hora_inicio)[:-2]} a {hora_fmt(item.hora_fin)} {_lugar(consultorios, item.id_consultorio)}"
    )


def _items_cuenta(
    liquidacion: Liquidacion, consultorios: dict, tipos_feriado_actual: dict[str, str],
    mes_actual_texto: str, mes_anterior_texto: str,
) -> list[tuple[str, float, bool]]:
    """(concepto, importe, es_subtotal) — DC-01 §1.10, con la redacción del
    modelo real: sin prefijos de categoría genéricos para cargos
    especiales (se muestra el Concepto tal cual se cargó). Los ítems de
    `descuento_licencias` deben traer ya colgado `.nombre_tipo` (ver
    `generar_pdf_liquidacion`, que lo resuelve una sola vez)."""
    items: list[tuple[str, float, bool]] = []
    items.append((f"Importe bruto correspondiente a la reserva regular de {mes_actual_texto}", liquidacion.bruto, False))
    concepto_desc = (
        f"Descuento ({liquidacion.descuento_horas_pct:g}%) por cantidad de horas semanales "
        f"reservadas ({liquidacion.horas_semanales:g}hs)"
    )
    items.append((concepto_desc, -(liquidacion.bruto - liquidacion.subtotal_reserva), False))
    items.append((f"Subtotal por reserva para el mes de {mes_actual_texto}", liquidacion.subtotal_reserva, True))
    if liquidacion.saldo_anterior > 0:
        concepto_saldo = "Saldo pendiente de la liquidación anterior"
    elif liquidacion.saldo_anterior < 0:
        concepto_saldo = "Saldo a favor del profesional de la liquidación anterior"
    else:
        concepto_saldo = "Saldo de la liquidación anterior"
    items.append((concepto_saldo, liquidacion.saldo_anterior, False))
    if liquidacion.reversion_descuento:
        items.append((
            "Reversión del descuento por arrastrar saldos del período anterior",
            liquidacion.reversion_descuento, False,
        ))

    for f in liquidacion.descuentos_feriados:
        dia_semana, fecha = _dia_y_fecha(f.fecha)
        items.append((f"Descuento por feriado - {dia_semana} {fecha}", -f.monto, False))
    for f in liquidacion.descuentos_no_laborables:
        dia_semana, fecha = _dia_y_fecha(f.fecha)
        items.append((f"Descuento por día no laborable - {dia_semana} {fecha}", -f.monto, False))
    for f in liquidacion.feriados_pendientes:
        dia_semana, fecha = _dia_y_fecha(f.fecha)
        items.append((f"Descuento feriado pendiente - {dia_semana} {fecha}", -f.monto, False))
    for v in liquidacion.descuento_vacaciones:
        d1, f1 = _dia_y_fecha(v.fecha_desde)
        d2, f2 = _dia_y_fecha(v.fecha_hasta)
        items.append((
            f"Descuento por vacaciones desde el {d1.lower()} {f1} hasta el {d2.lower()} {f2} inclusive",
            -v.monto, False,
        ))
    for lic in liquidacion.descuento_licencias:
        d1, f1 = _dia_y_fecha(lic.fecha_desde)
        d2, f2 = _dia_y_fecha(lic.fecha_hasta)
        items.append((
            f"Descuento por {lic.nombre_tipo.lower()} desde el {d1.lower()} {f1} hasta el {d2.lower()} {f2} inclusive",
            -lic.monto, False,
        ))

    for h in liquidacion.horas_regulares_agregadas:
        items.append((_texto_horas_agregadas(consultorios, h), h.monto, False))
    for item in liquidacion.feriados_trabajados_mes_anterior:
        items.append((_texto_feriado_trabajado_anterior(consultorios, item, mes_anterior_texto), item.monto, False))
    for item in liquidacion.feriados_trabajados_mes_en_curso:
        tipo = tipos_feriado_actual.get(item.fecha, "Feriado nacional")
        items.append((_texto_feriado_trabajado_actual(consultorios, item, tipo), item.monto, False))
    for item in liquidacion.aisladas_mes_anterior:
        items.append((_texto_aislada(consultorios, item, "trabajada", mes_anterior_texto), item.monto, False))
    for item in liquidacion.aisladas_mes_en_curso:
        items.append((_texto_aislada(consultorios, item, "a trabajar", mes_actual_texto), item.monto, False))
    if liquidacion.ajuste_saldo_atrasado:
        items.append(("Ajuste por saldo atrasado", liquidacion.ajuste_saldo_atrasado, False))
    for c in liquidacion.cargos_especiales:
        signo = 1 if c["Tipo"] == "Débito" else -1
        items.append((c["Concepto"], signo * c["Monto"], False))
    for c in liquidacion.cuotas_plan:
        items.append((f"Cuota {c['NumeroCuota']} del plan de pagos", c["Monto"], False))
    items.append((f"Liquidación a abonar por el profesional en el mes de {mes_actual_texto}", liquidacion.total, True))
    return items


def _tabla_items(items: list[tuple[str, float, bool]], ancho: float, decimales: int) -> list:
    """Filas simples (sin grilla, como el modelo real) para los ítems, y
    una caja con borde para cada fila marcada `es_subtotal` (el subtotal
    intermedio y el total final)."""
    story = []
    filas_simples: list[tuple[str, float]] = []
    for concepto, importe, es_subtotal in items[:-1]:
        if es_subtotal:
            if filas_simples:
                story.append(_tabla_plana(filas_simples, ancho, decimales))
                filas_simples = []
            story.append(_caja_subtotal(concepto, importe, ancho, decimales))
        else:
            filas_simples.append((concepto, importe))
    if filas_simples:
        story.append(_tabla_plana(filas_simples, ancho, decimales))

    concepto_total, importe_total, _ = items[-1]
    story.append(_caja_total(concepto_total, importe_total, ancho, decimales))
    return story


def _tabla_plana(filas: list[tuple[str, float]], ancho: float, decimales: int) -> Table:
    datos = [[concepto, formatear_moneda(importe, decimales)] for concepto, importe in filas]
    tabla = Table(datos, colWidths=[ancho * 0.78, ancho * 0.22])
    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), FUENTE), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i, (_, importe) in enumerate(filas):
        if importe < 0:
            estilo.append(("TEXTCOLOR", (1, i), (1, i), COLOR_ROJO))
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _caja_subtotal(concepto: str, importe: float, ancho: float, decimales: int) -> Table:
    tabla = Table([[concepto, formatear_moneda(importe, decimales)]], colWidths=[ancho * 0.78, ancho * 0.22])
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FUENTE_NEGRITA), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("BOX", (0, 0), (-1, -1), 1, "#000000"),
        ("BACKGROUND", (0, 0), (-1, -1), "#EEEEEE"), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tabla


def _caja_total(concepto: str, importe: float, ancho: float, decimales: int) -> Table:
    style_letras = estilo_texto(8, alignment=TA_RIGHT)
    letras = Paragraph(en_letras_pesos(importe), style_letras)
    tabla = Table(
        [[concepto, formatear_moneda(importe, decimales)], ["", letras]],
        colWidths=[ancho * 0.55, ancho * 0.45],
    )
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, 1), FUENTE_NEGRITA), ("FONTSIZE", (0, 0), (0, 1), 10),
        ("FONTNAME", (1, 0), (1, 0), FUENTE_NEGRITA_ITALICA), ("FONTSIZE", (1, 0), (1, 0), 12),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        # El concepto ancla arriba (fila del importe): si el texto en
        # letras se envuelve en más de una línea, la fila de abajo crece
        # sola sin arrastrar el concepto hacia el medio de las dos líneas.
        ("VALIGN", (0, 0), (0, 1), "TOP"), ("VALIGN", (1, 0), (1, 1), "TOP"),
        ("SPAN", (0, 0), (0, 1)), ("BOX", (0, 0), (-1, -1), 1.2, "#000000"),
        ("BACKGROUND", (0, 0), (-1, -1), "#EEEEEE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tabla


# --------------------------------------------------------- consultorios y horas

def _consultorios_y_horas(
    conn: sqlite3.Connection, ids: list[int], primer_dia: str, ultimo_dia: str,
    consultorios: dict, descuento_pct: float,
) -> list[dict]:
    placeholders = ", ".join("?" for _ in ids)
    acumulado: dict[int, float] = {}
    dia = date.fromisoformat(primer_dia)
    fin = date.fromisoformat(ultimo_dia)
    while dia <= fin:
        filas = conn.execute(
            f"""
            SELECT rr.IdConsultorio, rr.HoraInicio, rr.HoraFin
            FROM ReservaRegular rr
            WHERE rr.IdProfesional IN ({placeholders}) AND rr.DiaSemana = ?
              AND rr.VigenciaInicio <= ? AND (rr.VigenciaFin IS NULL OR rr.VigenciaFin >= ?)
            """,
            (*ids, DIAS_SEMANA[dia.weekday()], dia.isoformat(), dia.isoformat()),
        ).fetchall()
        for f in filas:
            acumulado[f["IdConsultorio"]] = acumulado.get(f["IdConsultorio"], 0.0) + (f["HoraFin"] - f["HoraInicio"])
        dia += timedelta(days=1)

    filas_resultado = []
    for id_consultorio, horas in acumulado.items():
        c = consultorios[id_consultorio]
        valor_regular = c["ValorHoraRegularActual"]
        valor_con_descuento = valor_regular * (1 - descuento_pct / 100)
        filas_resultado.append({
            "edificio": c["NombreEdificio"], "unidad": c["Departamento"], "consultorio": c["NumeroConsultorio"],
            "valor_regular": valor_regular, "desc_pct": descuento_pct, "valor_con_descuento": valor_con_descuento,
            "horas": horas,
        })
    filas_resultado.sort(key=lambda f: (f["edificio"], f["consultorio"]))
    return filas_resultado


def _tabla_consultorios_y_horas(filas_datos: list[dict], ancho: float, decimales: int) -> Table:
    filas = [["Edificio", "Unidad", "Consul.", "Valor regular", "Desc.", "Valor con descuento", "Horas mensuales"]]
    for f in filas_datos:
        filas.append([
            f["edificio"], f["unidad"], str(f["consultorio"]), formatear_moneda(f["valor_regular"], decimales),
            f"{f['desc_pct']:g}%", formatear_moneda(f["valor_con_descuento"], decimales), f"{f['horas']:g}",
        ])

    # "Valor regular" y "Valor con descuento" van al mismo ancho — el que
    # necesite el título más largo de los dos para no cortarse — sacando
    # la diferencia de "Horas mensuales" en vez de fracciones fijas, así
    # el ajuste sigue siendo válido si cambia cualquiera de los dos textos.
    padding = 12  # LEFT+RIGHTPADDING por defecto de reportlab (6pt c/u)
    ancho_valor_regular = ancho * 0.15
    ancho_valor_descuento = ancho * 0.17
    ancho_horas = ancho * 0.21
    minimo_valor = max(
        stringWidth("Valor regular", FUENTE_NEGRITA, 8),
        stringWidth("Valor con descuento", FUENTE_NEGRITA, 8),
    ) + padding
    ancho_columna_valor = max(ancho_valor_regular, ancho_valor_descuento, minimo_valor)
    delta = (ancho_columna_valor - ancho_valor_regular) + (ancho_columna_valor - ancho_valor_descuento)
    minimo_horas = stringWidth("Horas mensuales", FUENTE_NEGRITA, 8) + padding
    ancho_horas = max(ancho_horas - delta, minimo_horas)

    anchos = [ancho * 0.17, ancho * 0.14, ancho * 0.08, ancho_columna_valor, ancho * 0.08, ancho_columna_valor, ancho_horas]
    tabla = Table(filas, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA), ("FONTNAME", (0, 1), (-1, -1), FUENTE),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"), ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("ALIGN", (2, 1), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, "#000000"), ("BACKGROUND", (0, 0), (-1, 0), COLOR_NIVEL_1),
        ("TEXTCOLOR", (0, 0), (-1, 0), "#FFFFFF"),
    ]))
    return tabla


# ------------------------------------------------------------------- recordatorios

def _recordatorios(conn: sqlite3.Connection, ids: list[int], ajuste_pct: float) -> list:
    placeholders = ", ".join("?" for _ in ids)
    placas = conn.execute(
        f"""
        SELECT p.PosicionTablero, u.Departamento, e.Nombre AS NombreEdificio
        FROM Placa p JOIN Unidad u ON u.IdUnidad = p.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE p.IdProfesional IN ({placeholders}) AND p.Activo = 1
        """,
        ids,
    ).fetchall()
    style = estilo_texto(8)
    story = []
    for p in placas:
        story.append(Paragraph(
            f"* Placa para los timbres en la unidad del {p['Departamento']} del edificio "
            f"{p['NombreEdificio']} en la posición {p['PosicionTablero']} del tablero", style,
        ))
    story.append(Paragraph(
        "* Abonar el total liquidado dentro del mes en curso para mantener los descuentos "
        "en el próximo período.", style,
    ))
    story.append(Paragraph(
        f"* Los saldos pendientes que se trasladan de un mes a otro reciben un ajuste del "
        f"{ajuste_pct:g}% para mantener los mismos actualizados.", style,
    ))
    return story


# --------------------------------------------------------------------------- altura

def _altura_estimada(
    n_bloques: int, n_items: int, n_consultorios: int, n_edificios_valores: int,
    n_tramos_descuento: int, n_recordatorios: int, altura_disponibilidad: float,
    n_condiciones: int, n_notas_direccion: int = 0, n_fotos: int = 0,
) -> float:
    altura = 4 * cm  # logo/nombre + línea
    altura += 1.5 * cm + max(n_bloques, 1) * 0.55 * cm + n_notas_direccion * 0.4 * cm  # bloques horarios + notas
    altura += 1.5 * cm + n_items * 0.55 * cm + 3 * cm  # ítems + subtotal + total
    altura += 1.5 * cm + max(n_consultorios, 1) * 0.5 * cm + 1 * cm  # consultorios y horas
    altura += 1.5 * cm + n_edificios_valores * 3 * cm  # valores vigentes
    altura += 1.5 * cm + ceil(n_tramos_descuento / 9) * 1.4 * cm  # esquema descuentos
    altura += 1.5 * cm + max(n_recordatorios, 1) * 0.45 * cm  # recordatorios
    altura += altura_disponibilidad  # disponibilidad (grilla, o girada si supera el umbral)
    altura += 1.5 * cm + ceil(max(n_fotos, 1) / 2) * 6.8 * cm  # fotos
    altura += 1.5 * cm + n_condiciones * 1.3 * cm  # condiciones
    return altura * 1.15


# ------------------------------------------------------------------------------ main

def generar_pdf_liquidacion(conn: sqlite3.Connection, liquidacion: Liquidacion, directorio: str) -> str:
    """Genera el PDF de liquidación mensual y devuelve la ruta completa del
    archivo creado (`directorio` debe existir)."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(liquidacion.id_profesional)
    cfg = conn.execute("SELECT * FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    decimales = decimales_configurados(conn)

    ids = ids_consolidados(conn, liquidacion.id_profesional)
    anio, mes = parsear_periodo(liquidacion.periodo)
    anio_ant, mes_ant = parsear_periodo(f"{anio - 1:04d}-12" if mes == 1 else f"{anio:04d}-{mes - 1:02d}")
    primer_dia = primer_dia_mes(anio, mes).isoformat()
    ultimo_dia = ultimo_dia_mes(anio, mes).isoformat()
    consultorios = _mapa_consultorios(conn)

    # Resolver los nombres de TipoLicencia una sola vez, no en cada ítem.
    repo_tipo_lic = obtener_repositorio(conn, "TipoLicencia")
    for lic in liquidacion.descuento_licencias:
        tipo = repo_tipo_lic.obtener(lic.id_tipo_licencia)
        lic.nombre_tipo = tipo["Nombre"] if tipo else "licencia"

    tipos_feriado_actual = {f["Fecha"]: f["Tipo"] for f in feriados_relevantes_periodo(conn, anio, mes)}
    mes_actual_texto = mes_texto(mes)
    mes_anterior_texto = mes_texto(mes_ant)

    bloques = _bloques_horarios(conn, ids)
    edificios_bloques: dict[int, sqlite3.Row] = {}
    for b in bloques:
        edificios_bloques.setdefault(b["IdEdificio"], b)

    items = _items_cuenta(liquidacion, consultorios, tipos_feriado_actual, mes_actual_texto, mes_anterior_texto)
    # El "valor con descuento" de cada consultorio es un valor final "en
    # vivo" (igual que feriados trabajados u horas agregadas): si se pierde
    # el descuento por saldo atrasado, va sin descuento — a diferencia del
    # bruto, acá no hay una línea de reversión que lo compense.
    descuento_pct_valores = 0.0 if liquidacion.pierde_descuento_horas else liquidacion.descuento_horas_pct
    filas_consultorios = _consultorios_y_horas(
        conn, ids, primer_dia, ultimo_dia, consultorios, descuento_pct_valores
    )

    imagenes = imagenes_de_consultorios(conn, _ids_consultorio_reservados(conn, ids))

    n_tramos_descuento = conn.execute("SELECT COUNT(*) FROM EsquemaDescuentos WHERE Activo = 1").fetchone()[0]
    n_condiciones = conn.execute("SELECT COUNT(*) FROM CondicionNorma WHERE Activo = 1").fetchone()[0]
    altura_disponibilidad = altura_estimada_grilla(conn, list(edificios_bloques.keys()) or None)
    n_notas_direccion = sum(1 for info in edificios_bloques.values() if _direccion_edificio(info))
    edificios_valores = _edificios_para_valores(conn, edificios_bloques)

    altura = _altura_estimada(
        n_bloques=len(bloques), n_items=len(items), n_consultorios=len(filas_consultorios),
        n_edificios_valores=len(edificios_valores), n_tramos_descuento=n_tramos_descuento,
        n_recordatorios=3, altura_disponibilidad=altura_disponibilidad,
        n_condiciones=n_condiciones, n_notas_direccion=n_notas_direccion, n_fotos=len(imagenes),
    )

    fecha_titulo = fecha_larga(fecha_actual(conn).isoformat()).replace("/", "-")
    desde, hasta = rango_actualizacion(conn, liquidacion.periodo)

    def _construir_story(ancho: float) -> list:
        # Los flowables (Paragraph/Table) no se pueden reusar entre
        # distintos `doc.build()` — si `construir_sin_saltos` reintenta con
        # más alto, este closure se vuelve a llamar entero, así que todo
        # (incluidas las condiciones) se arma de cero acá adentro.
        condiciones_flowables = condiciones_normas(conn)
        story = []

        # Logo centrado (o el nombre del espacio si no hay uno configurado)
        # y línea separatoria — sin subtítulo ni localidad: un profesional
        # puede reservar en edificios de más de una localidad, no hay una
        # localidad única "de este documento" como sí la hay en
        # Disponibilidad/Propuesta.
        story.extend(encabezado_espacio(conn, ancho, mostrar_localidad=False))

        titulo_detalle = f"Liquidación período {periodo_mm_aaaa(liquidacion.periodo)} - {_nombre_completo(profesional)}"
        story.append(encabezado(1, titulo_detalle, ancho))
        story.append(Spacer(1, 6))

        story.append(Spacer(1, 6))
        story.append(encabezado(2, "Bloques de horarios regulares reservados", ancho))
        story.append(Spacer(1, 6))
        if bloques:
            story.append(_tabla_bloques_horarios(bloques, ancho))
        else:
            story.append(Paragraph("Sin bloques horarios regulares vigentes.", estilo_texto(9)))
        notas_direcciones = _notas_direcciones_edificios(edificios_bloques)
        if notas_direcciones:
            story.append(Spacer(1, 3))
            story.extend(notas_direcciones)
        story.append(Spacer(1, 8))

        story.append(Spacer(1, 6))
        story.append(encabezado(2, "Liquidación mensual mes en curso", ancho))
        story.append(Spacer(1, 6))
        story.extend(_tabla_items(items, ancho, decimales))
        story.append(Spacer(1, 8))

        story.append(Spacer(1, 6))
        story.append(encabezado(2, "Consultorios y cantidad de horas utilizadas por el profesional en el mes liquidado", ancho))
        story.append(Spacer(1, 6))
        if filas_consultorios:
            story.append(_tabla_consultorios_y_horas(filas_consultorios, ancho, decimales))
            total_horas = sum(f["horas"] for f in filas_consultorios)
            story.append(Spacer(1, 3))
            story.append(Paragraph(
                f"<para align=right><b>Total horas mensuales: {total_horas:g}hs - "
                f"Subtotal liquidación: {formatear_moneda(liquidacion.subtotal_reserva, decimales)}</b></para>",
                estilo_texto(9),
            ))
        story.append(Spacer(1, 10))

        titulo_valores = (
            f"Valores de los consultorios para el período comprendido entre "
            f"{periodo_mm_aaaa(desde)} y {periodo_mm_aaaa(hasta)}"
        )
        story.append(Spacer(1, 6))
        story.append(encabezado(2, titulo_valores, ancho))
        for info in edificios_valores:
            story.append(Spacer(1, 6))
            direccion = _direccion_edificio(info)
            texto_edificio = f"Edificio {info['NombreEdificio']} - {direccion}" if direccion else f"Edificio {info['NombreEdificio']}"
            story.append(encabezado(3, texto_edificio, ancho))
            story.append(Spacer(1, 6))
            story.extend(matriz_valores_edificio(conn, info["IdEdificio"], ancho))
            story.append(Spacer(1, 6))

        story.append(Spacer(1, 6))
        story.append(encabezado(2, "Esquema de descuentos", ancho))
        story.append(Spacer(1, 6))
        story.extend(bloques_esquema_descuentos(conn, ancho))

        story.append(Spacer(1, 6))
        story.append(encabezado(2, "Recordatorios varios para el profesional", ancho))
        story.append(Spacer(1, 6))
        story.extend(_recordatorios(conn, ids, cfg["PorcentajeAjusteSaldoAtrasado"] if cfg else 0))
        story.append(Spacer(1, 10))

        story.append(Spacer(1, 6))
        story.extend(secciones_disponibilidad(
            conn, anio, mes, ancho, fecha_titulo, ids_edificio=list(edificios_bloques.keys()) or None,
        ))

        story.append(Spacer(1, 6))
        story.append(encabezado(2, "Fotos de los consultorios reservados", ancho))
        story.append(Spacer(1, 6))
        story.extend(tabla_fotos(imagenes, ancho, mostrar_apto_camilla=False))

        if condiciones_flowables:
            titulo_condiciones = "Condiciones y normas generales de convivencia relacionadas con la reserva en el espacio"
            story.append(Spacer(1, 6))
            story.append(Spacer(1, 6))
            story.append(encabezado(2, titulo_condiciones, ancho))
            story.append(Spacer(1, 6))
            story.extend(condiciones_flowables)

        return story

    ruta = os.path.join(directorio, _nombre_archivo(liquidacion.periodo, profesional))
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta
