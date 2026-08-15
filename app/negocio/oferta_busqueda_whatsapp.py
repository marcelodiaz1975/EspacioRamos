"""Texto para copiar al portapapeles (WhatsApp) de Oferta de consultorios
— misma información, mismo orden y misma redacción que
`app.pdf.oferta_busqueda_pdf` (ambos se arman sobre
`app.negocio.oferta_busqueda_texto`), pero con la sintaxis de WhatsApp en
vez de Paragraphs: *negrita* para los títulos, _itálica_ para los avisos,
"-" en vez de "*" para las viñetas (un "*" sin cerrar en un renglón
rompería la negrita del resto del mensaje, WhatsApp la extendería hasta
el próximo "*" que encuentre).

No incluye la sección de fotos: son archivos aparte, se adjuntan sueltos
en el chat — no hay forma de incrustarlas en el texto del mensaje. Por
eso, a diferencia del PDF, acá SÍ se muestra el valor por hora al final
de cada línea que identifica un consultorio puntual — no hay foto debajo
de la cual mostrarlo."""
from __future__ import annotations

import sqlite3

from app.negocio.formato import decimales_configurados
from app.negocio.oferta_busqueda import Alternativa, Busqueda, CriteriosGlobales, resolver_busquedas_documento
from app.negocio.oferta_busqueda_texto import (
    alternativas_planas,
    avisos_planos,
    categoria_es_activa,
    edificios_comentario,
    filtrar_excluidas,
    lineas_opcion,
    mapa_consultorios_basico,
    resumen_busqueda,
)
from app.repositorio.registro import obtener_repositorio


def generar_texto_oferta_busqueda(
    conn: sqlite3.Connection, id_profesional: int, globales: CriteriosGlobales, busquedas: list[Busqueda],
    excluir: set[tuple[int, int, int]] | None = None,
) -> str:
    """Devuelve el texto completo, listo para copiar y pegar en WhatsApp."""
    if not busquedas:
        raise ValueError("La búsqueda necesita al menos una franja")
    excluir = excluir or set()

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    anonimizar = not categoria_es_activa(profesional)
    decimales = decimales_configurados(conn)

    listas_alternativas: list[list[Alternativa]] = [
        filtrar_excluidas(alts, i, excluir)
        for i, alts in enumerate(resolver_busquedas_documento(conn, globales, busquedas))
    ]
    ids_consultorio = sorted({
        t.id_consultorio for alts in listas_alternativas for alt in alts for op in alt.opciones for t in op.tramos
    })
    consultorios = mapa_consultorios_basico(conn, ids_consultorio)
    ids_edificio_resultado = {c["IdEdificio"] for c in consultorios.values()}
    mostrar_edificio = len(ids_edificio_resultado) > 1
    mostrar_consultorio = not globales.detalle_reducido
    avisos = avisos_planos(listas_alternativas)

    lineas = ["*Búsqueda requerida por el profesional*", ""]

    lineas.append("*Detalle de la búsqueda*")
    for b in busquedas:
        lineas.append(f"- {resumen_busqueda(b, globales.tipo_busqueda)}")
    lineas.append("")

    lineas.append("*Listado de alternativas encontradas*")
    lineas.append("")
    planas = alternativas_planas(listas_alternativas)
    if not planas:
        lineas.append("Sin disponibilidad para esta búsqueda con los filtros solicitados.")
    else:
        numerar = len(planas) > 1
        for indice, (etiqueta, opcion) in enumerate(planas):
            if indice > 0:
                lineas.append("")
            if numerar:
                lineas.append(f"_Alternativa {indice + 1}_")
            for linea in lineas_opcion(
                etiqueta, opcion, consultorios, mostrar_edificio, mostrar_consultorio, anonimizar,
                mostrar_valor=True, decimales=decimales,
            ):
                lineas.append(f"- {linea}")

    comentario = [f"- {t}" for t in edificios_comentario(conn, ids_edificio_resultado)] if mostrar_edificio else []
    comentario += [f"- {aviso}" for aviso in avisos]
    if comentario:
        lineas += ["", "*Comentario*"] + comentario

    return "\n".join(lineas)
