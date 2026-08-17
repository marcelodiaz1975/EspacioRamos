"""Manual de usuario (Etapa 11): un único PDF navegable que junta el
texto de ayuda contextual (el mismo que se ve al apretar F1 en cada
pantalla) agrupado por categoría, en el mismo orden que la navegación
lateral de la aplicación.

Este módulo no importa PySide6 — recibe las secciones ya como tuplas
planas (categoria, nombre, texto), no como el `Seccion` de la GUI, para
no romper la separación entre `app/pdf` (Qt-free) y `app/gui`."""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.pdf.estilos import construir_sin_saltos, encabezado, encabezado_espacio, estilo_texto

NOMBRE_ARCHIVO = "Manual de usuario.pdf"


def generar_pdf_manual(
    conn: sqlite3.Connection, directorio: str, secciones: list[tuple[str, str, str]],
) -> str:
    """Genera el manual y devuelve la ruta completa. `secciones` es una
    lista de (categoria, nombre, texto) — las que tengan texto vacío se
    omiten (todavía no tienen ayuda cargada)."""
    con_ayuda = [(c, n, t) for c, n, t in secciones if t.strip()]

    n_lineas_estimadas = sum(1 + max(1, len(t) // 80) for _, _, t in con_ayuda)
    altura = (6 * cm + 1.5 * cm + len(con_ayuda) * 0.8 * cm + n_lineas_estimadas * 0.5 * cm) * 1.2

    def _construir_story(ancho: float) -> list:
        story = list(encabezado_espacio(conn, ancho))
        story.append(encabezado(1, "Manual de usuario", ancho))
        story.append(Spacer(1, 10))

        if not con_ayuda:
            story.append(Paragraph("Todavía no hay ayuda contextual cargada.", estilo_texto(9)))
            return story

        categoria_actual = None
        for categoria, nombre, texto in con_ayuda:
            if categoria != categoria_actual:
                story.append(encabezado(2, categoria, ancho))
                story.append(Spacer(1, 6))
                categoria_actual = categoria
            story.append(Paragraph(nombre, estilo_texto(10, negrita=True)))
            story.append(Spacer(1, 2))
            story.append(Paragraph(texto.replace("\n", "<br/>"), estilo_texto(9)))
            story.append(Spacer(1, 10))
        return story

    ruta = os.path.join(directorio, NOMBRE_ARCHIVO)
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta
