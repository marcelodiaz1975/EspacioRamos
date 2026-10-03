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
de la cual mostrarlo.

Editable desde "Textos del sistema" (clave `oferta_busqueda_whatsapp`)
— ver `app.negocio.plantillas_texto`: los tres títulos en negrita son
texto de plantilla de verdad; el contenido armado con loops (detalle de
la búsqueda, listado de alternativas, comentario de edificios/avisos)
llega ya resuelto como tres variables de bloque, nunca editable línea
por línea — mismo criterio que `{detalle_items}` en `mensaje_detalle_
reserva_aislada`."""
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
from app.negocio.plantillas_texto import DEFAULT_OFERTA_BUSQUEDA_WHATSAPP, resolver_plantilla, sustituir_variables
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

    detalle_lineas = [f"- {resumen_busqueda(b, globales.tipo_busqueda)}" for b in busquedas]

    alternativas_lineas: list[str] = []
    planas = alternativas_planas(listas_alternativas)
    if not planas:
        alternativas_lineas.append("Sin disponibilidad para esta búsqueda con los filtros solicitados.")
    else:
        numerar = len(planas) > 1
        for indice, (etiqueta, opcion) in enumerate(planas):
            if indice > 0:
                alternativas_lineas.append("")
            if numerar:
                alternativas_lineas.append(f"_Alternativa {indice + 1}_")
            for linea in lineas_opcion(
                etiqueta, opcion, consultorios, mostrar_edificio, mostrar_consultorio, anonimizar,
                mostrar_valor=True, decimales=decimales,
            ):
                alternativas_lineas.append(f"- {linea}")

    comentario = [f"- {t}" for t in edificios_comentario(conn, ids_edificio_resultado)] if mostrar_edificio else []
    comentario += [f"- {aviso}" for aviso in avisos]
    bloque_comentario = ("\n\n*Comentario*\n" + "\n".join(comentario)) if comentario else ""

    plantilla = resolver_plantilla(conn, "oferta_busqueda_whatsapp", DEFAULT_OFERTA_BUSQUEDA_WHATSAPP)
    return sustituir_variables(plantilla, {
        "bloque_detalle_busqueda": "\n".join(detalle_lineas),
        "bloque_alternativas": "\n".join(alternativas_lineas),
        "bloque_comentario": bloque_comentario,
    })
