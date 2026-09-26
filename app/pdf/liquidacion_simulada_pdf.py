"""PDF de "Liquidación simulada" (pedido de la clienta, ver `app.negocio.
liquidacion_simulada` para el detalle completo de qué contempla y qué
no) — mucho más corto que el PDF de liquidación real
(`app.pdf.liquidacion_pdf`): solo los bloques que se cargaron para la
simulación, el bruto, el descuento por volumen de horas, los descuentos
por feriados/fechas especiales (si los hay) y el total neto. Sin
bloques de horarios reales, sin valores de consultorios, sin
disponibilidad, sin condiciones y normas — es un documento de ejemplo,
no el PDF que se le manda de verdad a un profesional."""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.negocio.formato import formatear_moneda, hora_fmt, periodo_mm_aaaa
from app.negocio.liquidacion_simulada import LiquidacionSimulada
from app.pdf.estilos import (
    COLOR_NIVEL_1,
    FUENTE,
    FUENTE_NEGRITA,
    construir_sin_saltos,
    encabezado,
    encabezado_espacio,
    estilo_texto,
)
from app.repositorio.registro import obtener_repositorio

_ALTO_FILA = 0.65 * cm


def _nombre_completo(profesional: sqlite3.Row) -> str:
    tratamiento = profesional["Tratamiento"] or ""
    nombre = profesional["NombrePila"] or ""
    apellido = profesional["Apellido"]
    return " ".join(p for p in (tratamiento, nombre, apellido) if p)


def nombre_archivo_liquidacion_simulada(periodo: str, profesional: sqlite3.Row) -> str:
    """"{AAAA-MM} - Liquidación simulada {Tratamiento} {Nombre}
    {Apellido}.pdf" — formato pedido explícitamente por la clienta, sin
    el sufijo de código que sí lleva `liquidacion_pdf.
    nombre_archivo_liquidacion` (acá no hace falta desambiguar contra
    ningún otro archivo real del mismo profesional: viven en carpetas
    separadas)."""
    return f"{periodo} - Liquidación simulada {_nombre_completo(profesional)}.pdf"


def _lugar_bloque(conn: sqlite3.Connection, id_consultorio: int) -> str:
    fila = conn.execute(
        """
        SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS NombreEdificio
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE c.IdConsultorio = ?
        """,
        (id_consultorio,),
    ).fetchone()
    if fila is None:
        return ""
    return f"consul {fila['NumeroConsultorio']} del {fila['Departamento']} - {fila['NombreEdificio']}"


def generar_pdf_liquidacion_simulada(conn: sqlite3.Connection, liquidacion: LiquidacionSimulada, directorio: str) -> str:
    profesional = obtener_repositorio(conn, "Profesional").obtener(liquidacion.id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{liquidacion.id_profesional}")
    decimales = 2

    n_filas = len(liquidacion.bloques) + len(liquidacion.descuentos_feriados)
    altura = (10 * cm + n_filas * _ALTO_FILA + 6 * cm) * 1.2

    def _construir_story(ancho: float) -> list:
        story = list(encabezado_espacio(conn, ancho))
        story.append(
            encabezado(
                1, f"Liquidación simulada {periodo_mm_aaaa(liquidacion.periodo)} - {_nombre_completo(profesional)}",
                ancho,
            )
        )
        story.append(Spacer(1, 8))
        story.append(
            Paragraph(
                "Documento de ejemplo: simula cuánto generarían los bloques cargados en este período, "
                "sin tener en cuenta si el consultorio está ocupado o reservado por otro profesional a esa "
                "hora. No representa una liquidación real ni una reserva confirmada.",
                estilo_texto(9, italica=True),
            )
        )
        story.append(Spacer(1, 12))

        story.append(Paragraph("Bloques simulados", estilo_texto(11, negrita=True)))
        story.append(Spacer(1, 4))
        filas_bloques = [["Día", "Horario", "Consultorio"]]
        for bloque in liquidacion.bloques:
            filas_bloques.append([
                bloque.dia_semana, f"{hora_fmt(bloque.hora_inicio)} a {hora_fmt(bloque.hora_fin)}",
                _lugar_bloque(conn, bloque.id_consultorio),
            ])
        tabla_bloques = Table(filas_bloques, colWidths=[ancho * 0.2, ancho * 0.3, ancho * 0.5])
        tabla_bloques.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_NIVEL_1),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA),
            ("FONTNAME", (0, 1), (-1, -1), FUENTE),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(tabla_bloques)
        story.append(Spacer(1, 14))

        story.append(Paragraph("Liquidación simulada", estilo_texto(11, negrita=True)))
        story.append(Spacer(1, 4))
        filas_montos = [
            ["Concepto", "Monto"],
            ["Bruto (horas semanales: " + f"{liquidacion.horas_semanales:g})", formatear_moneda(liquidacion.bruto, decimales)],
            [
                f"Descuento por volumen de horas ({liquidacion.descuento_horas_pct:g}%)",
                formatear_moneda(-liquidacion.bruto * liquidacion.descuento_horas_pct / 100, decimales),
            ],
        ]
        for item in liquidacion.descuentos_feriados:
            filas_montos.append([f"Descuento {item.tipo.lower()} ({item.fecha})", formatear_moneda(-item.monto, decimales)])
        filas_montos.append(["Total simulado", formatear_moneda(liquidacion.neto, decimales)])

        tabla_montos = Table(filas_montos, colWidths=[ancho * 0.7, ancho * 0.3])
        estilo_tabla_montos = [
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_NIVEL_1),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA),
            ("FONTNAME", (0, 1), (-1, -2), FUENTE),
            ("FONTNAME", (0, -1), (-1, -1), FUENTE_NEGRITA),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ]
        tabla_montos.setStyle(TableStyle(estilo_tabla_montos))
        story.append(tabla_montos)
        return story

    ruta = os.path.join(directorio, nombre_archivo_liquidacion_simulada(liquidacion.periodo, profesional))
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta
