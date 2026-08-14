"""PDF de Oferta de consultorios armado a partir de una búsqueda ad-hoc
(`app.negocio.oferta_busqueda`) — distinto del PDF de Oferta atado a un
pedido de Lista de espera (`app.pdf.oferta_pdf`). Este es el que se arma
cuando un profesional pide opciones de consultorios (para reservar en
forma regular o por horas aisladas) y el resultado puede salir como este
PDF o como texto para portapapeles/WhatsApp (mismo motor de búsqueda y
mismo armado de texto — ver `app.negocio.oferta_busqueda_texto` — con
formato de WhatsApp en `app.negocio.oferta_busqueda_whatsapp`).

Nombre de archivo fijo "Oferta consultorios.pdf": siempre se sobrescribe,
sin historial de versiones.

Anonimización: depende de la categoría del profesional al que va dirigida
la búsqueda — R/A/E/X/B muestran el departamento real (piso y letra), C
se anonimiza como "Unidad N". Distinto del resto de los PDFs del sistema
(que solo consideran activas a R/A/B/E): acá X también cuenta como activa
porque, a diferencia de Propuesta/Disponibilidad, esto lo arma el
operador para un profesional puntual, no es un documento que se entrega
sin más contexto.

Estructura, deliberadamente breve (el profesional ya sabe lo que pidió,
no hace falta repetirle los criterios de la búsqueda): nivel 1 "Búsqueda
requerida por el profesional" -> nivel 2 "Detalle de la búsqueda" (una
línea por búsqueda del documento, solo días y horario — más el rango de
fechas si es Aislada) -> nivel 2 "Listado de alternativas encontradas"
(todas las opciones de todas las búsquedas, una tras otra; si hay más de
una se numeran "Alternativa N", si hay una sola se detalla directo) ->
nivel 2 "Comentario", solo si hace falta (a qué dirección corresponde
cada edificio mencionado, cuando hay más de uno; avisos de hora aislada
superpuesta) -> nivel 2 "Fotos de los consultorios ofrecidos" (unión de
todos los consultorios ofrecidos, agrupados por edificio cuando hay más
de uno, con el valor por hora debajo de cada foto — el único lugar donde
se muestra, no se repite en el listado de alternativas)."""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.negocio.oferta_busqueda import Alternativa, Busqueda, CriteriosGlobales, resolver_busqueda
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
from app.pdf.edificios_pdf import numero_unidad_en_edificio
from app.pdf.estilos import (
    clave_orden_unidad,
    construir_sin_saltos,
    decimales_configurados,
    encabezado,
    encabezado_espacio,
    estilo_texto,
    formatear_moneda,
)
from app.pdf.fotos_pdf import imagenes_de_consultorios, tabla_fotos
from app.repositorio.registro import obtener_repositorio


def _formatear_valor(monto: float, decimales: int) -> str:
    """Sin decimales cuando el valor es redondo (sin centavos), con los
    decimales configurados cuando no."""
    return formatear_moneda(monto, 0 if monto == int(monto) else decimales)


def _texto_detalle_busqueda(busquedas: list[Busqueda], tipo_busqueda: str) -> list:
    style = estilo_texto(9)
    return [Paragraph(f"* {resumen_busqueda(b, tipo_busqueda)}", style) for b in busquedas]


def _texto_alternativas(
    listas_alternativas: list[list[Alternativa]], consultorios: dict, mostrar_edificio: bool, mostrar_consultorio: bool,
    anonimizar: bool,
) -> list:
    style = estilo_texto(9)
    planas = alternativas_planas(listas_alternativas)
    if not planas:
        return [Paragraph("Sin disponibilidad para esta búsqueda con los filtros solicitados.", style)]

    numerar = len(planas) > 1
    story = []
    for indice, (etiqueta, opcion) in enumerate(planas):
        if indice > 0:
            story.append(Spacer(1, 8))
        if numerar:
            story.append(Paragraph(f"<b>Alternativa {indice + 1}</b>", style))
            story.append(Spacer(1, 2))
        for linea in lineas_opcion(etiqueta, opcion, consultorios, mostrar_edificio, mostrar_consultorio, anonimizar):
            story.append(Paragraph(f"* {linea}", style))
    return story


def _texto_comentario(conn: sqlite3.Connection, ids_edificio_resultado: set[int], mostrar_edificio: bool, avisos: list[str]) -> list:
    style = estilo_texto(9)
    style_aviso = estilo_texto(8, italica=True)
    lineas = [Paragraph(f"* {t}", style) for t in edificios_comentario(conn, ids_edificio_resultado)] if mostrar_edificio else []
    lineas += [Paragraph(f"* {aviso}", style_aviso) for aviso in avisos]
    return lineas


def _consultorios_ordenados(conn: sqlite3.Connection, consultorios: dict, anonimizar: bool) -> list[sqlite3.Row]:
    numeros_por_edificio: dict[int, dict[int, int]] = {}
    if anonimizar:
        for id_edificio in {c["IdEdificio"] for c in consultorios.values()}:
            numeros_por_edificio[id_edificio] = numero_unidad_en_edificio(conn, id_edificio)

    def clave(c: sqlite3.Row):
        if anonimizar:
            return (c["IdEdificio"], numeros_por_edificio[c["IdEdificio"]].get(c["IdUnidad"], 0), c["NumeroConsultorio"])
        return (c["IdEdificio"], clave_orden_unidad(c["Departamento"]), c["NumeroConsultorio"])

    return sorted(consultorios.values(), key=clave)


def _pie_foto(imagen: sqlite3.Row, mostrar_edificio: bool, anonimizar: bool, decimales: int) -> str:
    """Edificio (si hay más de uno) - Unidad - Consultorio - Hora regular
    $Valor — el único lugar del documento donde se muestra el valor."""
    unidad = f"Unidad {imagen['IdUnidadConsultorio']}" if anonimizar else f"Unidad {imagen['Departamento']}"
    partes = ([f"Edificio {imagen['NombreEdificio']}"] if mostrar_edificio else []) + [unidad, f"Consultorio {imagen['NumeroConsultorio']}"]
    return f"{' - '.join(partes)} - Hora regular {_formatear_valor(imagen['ValorHoraRegularActual'], decimales)}"


def _bloque_consultorios_intervinientes(
    conn: sqlite3.Connection, consultorios: dict, imagenes: list[sqlite3.Row], anonimizar: bool, mostrar_edificio: bool,
    ancho: float, decimales: int,
) -> list:
    if not consultorios:
        return [Paragraph("No hay consultorios involucrados en las alternativas encontradas.", estilo_texto(9))]

    consultorios_ordenados = _consultorios_ordenados(conn, consultorios, anonimizar)
    imagenes_por_consultorio: dict[int, list] = {}
    for img in imagenes:
        imagenes_por_consultorio.setdefault(img["IdConsultorio"], []).append(img)

    ids_edificio_orden = list(dict.fromkeys(c["IdEdificio"] for c in consultorios_ordenados))

    story = []
    for id_edificio in ids_edificio_orden:
        del_edificio = [c for c in consultorios_ordenados if c["IdEdificio"] == id_edificio]
        if mostrar_edificio:
            story.append(encabezado(3, f"Edificio {del_edificio[0]['NombreEdificio']}", ancho))
            story.append(Spacer(1, 6))
        imagenes_ed = [img for c in del_edificio for img in imagenes_por_consultorio.get(c["IdConsultorio"], [])]
        story.extend(tabla_fotos(
            imagenes_ed, ancho, pie_personalizado=lambda img: _pie_foto(img, mostrar_edificio, anonimizar, decimales),
        ))
        story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Los valores detallados corresponden a los vigentes a este mes en curso, y a los mismos luego se le "
        "aplican los descuentos en base a la cantidad de horas regulares que se tenga reservadas.",
        estilo_texto(8, italica=True),
    ))
    return story


def generar_pdf_oferta_busqueda(
    conn: sqlite3.Connection, directorio: str, id_profesional: int, globales: CriteriosGlobales,
    busquedas: list[Busqueda], excluir: set[tuple[int, int, int]] | None = None,
) -> str:
    """Genera "Oferta consultorios.pdf" a partir de una búsqueda ad-hoc (no
    se persiste nada — a diferencia de Lista de espera) y devuelve la ruta
    completa. `busquedas` es la lista de franjas de la búsqueda global,
    todas del mismo `globales.tipo_busqueda`.

    `excluir` — tripletas (índice de búsqueda, índice de alternativa/día,
    índice de opción dentro de ese día), 0-based, a dejar afuera del
    documento: pensado para la futura pantalla de previsualización, donde
    se puede destildar una opción puntual para no ofrecerla (p. ej.
    porque se prefiere guardar ese consultorio libre para otro
    profesional) sin descartar el resto de la búsqueda."""
    if not busquedas:
        raise ValueError("La búsqueda necesita al menos una franja")
    excluir = excluir or set()

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    anonimizar = not categoria_es_activa(profesional)
    decimales = decimales_configurados(conn)

    listas_alternativas = [
        filtrar_excluidas(resolver_busqueda(conn, globales, b).alternativas, i, excluir)
        for i, b in enumerate(busquedas)
    ]
    ids_consultorio = sorted({
        t.id_consultorio for alts in listas_alternativas for alt in alts for op in alt.opciones for t in op.tramos
    })
    consultorios = mapa_consultorios_basico(conn, ids_consultorio)
    imagenes = imagenes_de_consultorios(conn, ids_consultorio)
    ids_edificio_resultado = {c["IdEdificio"] for c in consultorios.values()}
    mostrar_edificio = len(ids_edificio_resultado) > 1
    mostrar_consultorio = not globales.detalle_reducido
    avisos = avisos_planos(listas_alternativas)

    altura = (
        6 * cm + 3 * cm + len(busquedas) * 1 * cm + len(ids_consultorio) * 2 * 1.2 * cm
        + (len(imagenes) // 2 + 1) * 7 * cm + 4 * cm
    ) * 1.2

    def _construir_story(ancho: float) -> list:
        story = list(encabezado_espacio(conn, ancho))

        story.append(encabezado(1, "Búsqueda requerida por el profesional", ancho))
        story.append(Spacer(1, 8))
        story.append(encabezado(2, "Detalle de la búsqueda", ancho))
        story.append(Spacer(1, 6))
        story.extend(_texto_detalle_busqueda(busquedas, globales.tipo_busqueda))
        story.append(Spacer(1, 10))

        story.append(encabezado(2, "Listado de alternativas encontradas", ancho))
        story.append(Spacer(1, 6))
        story.extend(_texto_alternativas(listas_alternativas, consultorios, mostrar_edificio, mostrar_consultorio, anonimizar))
        story.append(Spacer(1, 10))

        comentario = _texto_comentario(conn, ids_edificio_resultado, mostrar_edificio, avisos)
        if comentario:
            story.append(encabezado(2, "Comentario", ancho))
            story.append(Spacer(1, 6))
            story.extend(comentario)
            story.append(Spacer(1, 10))

        # Con detalle reducido no se identifica qué consultorio puntual se
        # ofrece (ver `Busqueda`/`detalle_tramo`) — una foto es, en los
        # hechos, el consultorio mostrado sin ambigüedad, así que esta
        # sección completa no tiene sentido en ese modo.
        if not globales.detalle_reducido:
            story.append(encabezado(2, "Fotos de los consultorios ofrecidos", ancho))
            story.append(Spacer(1, 8))
            story.extend(_bloque_consultorios_intervinientes(conn, consultorios, imagenes, anonimizar, mostrar_edificio, ancho, decimales))
        return story

    ruta = os.path.join(directorio, "Oferta consultorios.pdf")
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta
