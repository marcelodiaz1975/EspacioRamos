"""PDF de Oferta de consultorios armado a partir de una búsqueda ad-hoc
(`app.negocio.oferta_busqueda`) — distinto del PDF de Oferta atado a un
pedido de Lista de espera (`app.pdf.oferta_pdf`). Este es el que se arma
cuando un profesional pide opciones de consultorios (para reservar en
forma regular o por horas aisladas) y el resultado puede salir como este
PDF o como mensaje de WhatsApp (el mensaje se resuelve más adelante, con
el mismo motor de búsqueda).

Nombre de archivo fijo "Oferta consultorios.pdf": siempre se sobrescribe,
sin historial de versiones.

Anonimización: depende de la categoría del profesional al que va dirigida
la búsqueda — R/A/E/X/B muestran el departamento real (piso y letra), C
se anonimiza como "Unidad N". Distinto del resto de los PDFs del sistema
(que solo consideran activas a R/A/B/E): acá X también cuenta como activa
porque, a diferencia de Propuesta/Disponibilidad, esto lo arma el
operador para un profesional puntual, no es un documento que se entrega
sin más contexto.

Estructura: nivel 1 "Búsqueda solicitada por {profesional}" -> nivel 2
"Criterios de búsqueda generales" (los criterios comunes a todas las
búsquedas del documento: tipo, localidad, edificios/unidades/consultorios
alcanzados — "todos"/"todas" cuando no se restringió, o cuando el alcance
elegido igual cubre absolutamente todo lo que hay en la localidad) -> por
cada búsqueda, nivel 2 "Búsqueda {N}" con nivel 3 "Criterios de búsqueda
seleccionados" (los filtros particulares de esa búsqueda) y nivel 3
"Coincidencias de la búsqueda" (TODAS las opciones encontradas por día —
si más de un consultorio puede cubrir el bloque por sí solo, se listan
todas, no solo la primera — con una explicación en texto del tipo de
cobertura: completa o parcial según si se cubrió todo el bloque pedido o
solo una parte, y un aviso cuando hay una hora aislada asignada dentro
del bloque ofrecido) -> nivel 2 "Fotos de los consultorios que
intervienen en las búsquedas" (unión de todos los consultorios ofrecidos
en cualquiera de las búsquedas, agrupados por edificio cuando hay más de
uno administrado, ordenados por unidad real o posición anonimizada y
consultorio; el pie de cada foto es Edificio (si hay más de uno) - Unidad
- Consultorio: Valor, sin repetir el valor en ningún otro lado)."""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.negocio.formato import fecha_larga, hora_fmt
from app.negocio.oferta_busqueda import (
    AMARILLO,
    NARANJA,
    VERDE,
    Alternativa,
    Busqueda,
    CriteriosGlobales,
    Opcion,
    resolver_busqueda,
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

_ES_ACTIVO = ("R", "A", "E", "X", "B")

_DETALLE_COLOR = {
    VERDE: "un solo consultorio cubre {parte} bloque pedido.",
    AMARILLO: "requiere combinar más de un consultorio, todos dentro de la misma unidad, para cubrir {parte} bloque pedido.",
    NARANJA: "requiere combinar consultorios de distintas unidades, dentro del mismo edificio, para cubrir {parte} bloque pedido.",
}

_NOMBRES_CARACTERISTICA = {"apto_camilla": "apto camilla", "ventana": "con ventana", "sillones": "con sillones"}


def _categoria_es_activa(profesional: sqlite3.Row) -> bool:
    return profesional["CategoriaProfesional"] in _ES_ACTIVO


def _nombre_completo(profesional: sqlite3.Row) -> str:
    tratamiento = profesional["Tratamiento"] or ""
    nombre = profesional["NombrePila"] or ""
    apellido = profesional["Apellido"]
    return " ".join(p for p in (tratamiento, nombre, apellido) if p)


def _formatear_valor(monto: float, decimales: int) -> str:
    """Sin decimales cuando el valor es redondo (sin centavos), con los
    decimales configurados cuando no."""
    return formatear_moneda(monto, 0 if monto == int(monto) else decimales)


def _edificios_de_localidad(conn: sqlite3.Connection, localidad: str | None) -> set[int]:
    if localidad:
        filas = conn.execute("SELECT IdEdificio FROM Edificio WHERE DomicilioLocalidad = ?", (localidad,)).fetchall()
    else:
        filas = conn.execute("SELECT IdEdificio FROM Edificio").fetchall()
    return {f["IdEdificio"] for f in filas}


def _texto_edificios(conn: sqlite3.Connection, globales: CriteriosGlobales) -> str:
    """"todos" cuando no se restringió el alcance, o cuando el alcance
    elegido igual cubre TODOS los edificios de la localidad — si no,
    enumera con la dirección de cada uno ("Av. Rivadavia 13876 (Ramos
    1)"): la localidad ya se aclaró antes, no hace falta repetirla."""
    if not globales.ids_edificio or set(globales.ids_edificio) == _edificios_de_localidad(conn, globales.localidad):
        return "todos"
    placeholders = ", ".join("?" for _ in globales.ids_edificio)
    filas = conn.execute(
        f"SELECT Nombre, Domicilio FROM Edificio WHERE IdEdificio IN ({placeholders})", globales.ids_edificio,
    ).fetchall()
    return ", ".join(f"{f['Domicilio']} ({f['Nombre']})" if f["Domicilio"] else f["Nombre"] for f in filas)


def _nombres_unidad(conn: sqlite3.Connection, ids_unidad: list[int]) -> list[str]:
    if not ids_unidad:
        return []
    placeholders = ", ".join("?" for _ in ids_unidad)
    filas = conn.execute(f"SELECT Departamento FROM Unidad WHERE IdUnidad IN ({placeholders})", ids_unidad).fetchall()
    return [f["Departamento"] for f in filas]


def _texto_criterios_globales(conn: sqlite3.Connection, globales: CriteriosGlobales) -> list:
    style = estilo_texto(9)
    tipo_texto = "Horarios regulares" if globales.tipo_busqueda == "Regular" else "Horas aisladas"
    nombres_un = _nombres_unidad(conn, globales.ids_unidad) if globales.ids_unidad else []
    return [
        Paragraph(f"<b>Tipo de búsqueda:</b> {tipo_texto}", style),
        Paragraph(f"<b>Localidad:</b> {globales.localidad or '—'}", style),
        Paragraph(f"<b>Edificios:</b> {_texto_edificios(conn, globales)}", style),
        Paragraph(f"<b>Unidades:</b> {', '.join(nombres_un) or 'todas'}", style),
        Paragraph(
            f"<b>Consultorios:</b> {len(globales.ids_consultorio) if globales.ids_consultorio else 'todos'}"
            + (" seleccionados" if globales.ids_consultorio else ""),
            style,
        ),
    ]


def _texto_criterios_busqueda(busqueda: Busqueda) -> list:
    style = estilo_texto(9)
    story = [
        Paragraph(f"<b>Fecha inicial:</b> {fecha_larga(busqueda.fecha_desde)}", style),
        Paragraph(f"<b>Fecha final:</b> {fecha_larga(busqueda.fecha_hasta) if busqueda.fecha_hasta else 'indefinida'}", style),
        Paragraph(f"<b>Días solicitados:</b> {', '.join(busqueda.dias)}", style),
    ]
    desde, hasta = hora_fmt(busqueda.hora_desde)[:-2], hora_fmt(busqueda.hora_hasta)
    story.append(Paragraph(f"<b>Horario:</b> {desde} a {hasta}", style))
    texto_cantidad = f"{busqueda.cantidad_horas_minimas:g}hs dentro del rango horario (no hace falta que sea el rango completo)" if busqueda.cantidad_horas_minimas else "todo el rango horario"
    story.append(Paragraph(f"<b>Cantidad de horas mínimas dentro del rango solicitado:</b> {texto_cantidad}", style))
    texto_combinar = {
        "Ninguna": "un solo consultorio, sin combinar",
        "MismaUnidad": "admite combinar consultorios, sin salir de la misma unidad",
        "MismoEdificio": "admite combinar consultorios (siempre dentro del mismo edificio)",
    }.get(busqueda.combinacion, busqueda.combinacion)
    story.append(Paragraph(f"<b>Combinación de consultorios:</b> {texto_combinar}", style))

    caracteristicas = [
        etiqueta for clave, etiqueta in _NOMBRES_CARACTERISTICA.items() if getattr(busqueda, clave)
    ]
    if busqueda.tamano:
        caracteristicas.append(f"tamaño {busqueda.tamano.lower()}")
    story.append(Paragraph(f"<b>Características del consultorio:</b> {', '.join(caracteristicas) or '—'}", style))
    if busqueda.valor_maximo_hora is not None:
        story.append(Paragraph(f"<b>Valor máximo por hora regular:</b> {formatear_moneda(busqueda.valor_maximo_hora)}", style))
    if busqueda.combinacion_con_siguiente:
        texto = (
            "tienen que darse las dos búsquedas juntas" if busqueda.combinacion_con_siguiente == "Y"
            else "alcanza con que se dé alguna de las dos búsquedas"
        )
        story.append(Paragraph(f"<b>Combinación con la búsqueda siguiente:</b> {texto}", style))
    return story


def _etiqueta_dia(dia_semana: str, fecha: str | None) -> str:
    return f"{dia_semana} {fecha_larga(fecha)}" if fecha else dia_semana


def _es_cobertura_parcial(busqueda: Busqueda, tramos: list) -> bool:
    duracion_cubierta = sum(t.hora_fin - t.hora_inicio for t in tramos)
    return duracion_cubierta < (busqueda.hora_hasta - busqueda.hora_desde)


def _texto_tipo_cobertura(busqueda: Busqueda, opcion: Opcion) -> str:
    parcial = _es_cobertura_parcial(busqueda, opcion.tramos)
    prefijo = "Cobertura parcial" if parcial else "Cobertura completa"
    parte = "una parte del" if parcial else "todo el"
    detalle = _DETALLE_COLOR.get(opcion.color, "").format(parte=parte)
    return f"{prefijo}: {detalle}"


def _detalle_tramo(
    t, c: sqlite3.Row, mostrar_edificio: bool, mostrar_consultorio: bool, anonimizar: bool, decimales: int,
) -> str:
    """Con consultorio (modo normal): "De 9 a 15hs consultorio 2 del 7mo
    "L" del edificio Ramos 1 - Hora regular $X" (el tramo del edificio se
    omite si hay uno solo). Sin consultorio (detalle reducido): "De 9 a
    15hs en la unidad del 7mo "L" - Edificio Ramos 1" (mismo criterio de
    edificio, sin valor porque no hay un consultorio puntual del que
    salga)."""
    rango = f"De {hora_fmt(t.hora_inicio)[:-2]} a {hora_fmt(t.hora_fin)}"
    if mostrar_consultorio:
        unidad_txt = f"- Unidad {c['IdUnidad']}" if anonimizar else f"del {c['Departamento']}"
        texto = f"{rango} consultorio {c['NumeroConsultorio']} {unidad_txt}"
        if mostrar_edificio:
            texto += f" del edificio {c['NombreEdificio']}"
        texto += f" - Hora regular {_formatear_valor(c['ValorHoraRegularActual'], decimales)}"
    else:
        unidad_txt = f"en la Unidad {c['IdUnidad']}" if anonimizar else f"en la unidad del {c['Departamento']}"
        texto = f"{rango} {unidad_txt}"
        if mostrar_edificio:
            texto += f" - Edificio {c['NombreEdificio']}"
    return texto


def _texto_opcion(opcion: Opcion, consultorios: dict, mostrar_edificio: bool, mostrar_consultorio: bool, anonimizar: bool, decimales: int) -> list:
    style = estilo_texto(9)
    if len(opcion.tramos) == 1:
        t = opcion.tramos[0]
        c = consultorios.get(t.id_consultorio)
        if c is None:
            return []
        detalle = _detalle_tramo(t, c, mostrar_edificio, mostrar_consultorio, anonimizar, decimales)
        return [Paragraph(f"* {detalle}", style)]
    story = [Paragraph("* Combinación de consultorios:", style)]
    for t in opcion.tramos:
        c = consultorios.get(t.id_consultorio)
        if c is None:
            continue
        detalle = _detalle_tramo(t, c, mostrar_edificio, mostrar_consultorio, anonimizar, decimales)
        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;· {detalle}", style))
    return story


def _texto_coincidencias(
    busqueda: Busqueda, alternativas: list[Alternativa], consultorios: dict, anonimizar: bool, mostrar_edificio: bool,
    mostrar_consultorio: bool, decimales: int,
) -> list:
    style = estilo_texto(9)
    style_aviso = estilo_texto(8, italica=True)
    if not alternativas:
        return [Paragraph("Sin disponibilidad para esta búsqueda con los filtros solicitados.", style)]

    story = []
    for indice, alt in enumerate(alternativas):
        if indice > 0:
            story.append(Spacer(1, 6))
        # Cuando hay más de una opción para el mismo día, todas comparten
        # tipo de cobertura (todas son de un solo consultorio — si hiciera
        # falta combinar, solo se ofrece UNA opción de respaldo).
        story.append(Paragraph(f"<i>{_etiqueta_dia(alt.dia_semana, alt.fecha)}: {_texto_tipo_cobertura(busqueda, alt.opciones[0])}</i>", style))
        for opcion in alt.opciones:
            story.extend(_texto_opcion(opcion, consultorios, mostrar_edificio, mostrar_consultorio, anonimizar, decimales))
        for aviso in alt.avisos:
            story.append(Paragraph(aviso, style_aviso))
    return story


def _mapa_consultorios_basico(conn: sqlite3.Connection, ids_consultorio: list[int]) -> dict[int, sqlite3.Row]:
    if not ids_consultorio:
        return {}
    placeholders = ", ".join("?" for _ in ids_consultorio)
    filas = conn.execute(
        f"""
        SELECT c.IdConsultorio, c.NumeroConsultorio, c.ValorHoraRegularActual,
               u.IdUnidad, u.Departamento, e.IdEdificio, e.Nombre AS NombreEdificio
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE c.IdConsultorio IN ({placeholders})
        """,
        ids_consultorio,
    ).fetchall()
    return {f["IdConsultorio"]: f for f in filas}


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
    """Edificio (si hay más de uno) - Unidad - Consultorio: Valor/hora — ni
    apto camilla ni el valor se repiten en ningún otro lado, ese detalle
    ya se desprende de "Criterios de búsqueda seleccionados"."""
    unidad = f"Unidad {imagen['IdUnidadConsultorio']}" if anonimizar else imagen["Departamento"]
    partes = ([f"Edificio {imagen['NombreEdificio']}"] if mostrar_edificio else []) + [unidad, f"Consultorio {imagen['NumeroConsultorio']}"]
    return f"{' - '.join(partes)}: {_formatear_valor(imagen['ValorHoraRegularActual'], decimales)}/hora"


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


def _filtrar_excluidas(alternativas: list[Alternativa], indice_busqueda: int, excluir: set[tuple[int, int, int]]) -> list[Alternativa]:
    """Deja afuera opciones puntuales marcadas en `excluir` (índice de
    búsqueda, índice de alternativa/día, índice de opción dentro de ese
    día) — si un día se queda sin ninguna opción, el día entero desaparece
    del documento (equivale a no haber encontrado nada ese día)."""
    resultado = []
    for i_alt, alt in enumerate(alternativas):
        opciones = [op for i_op, op in enumerate(alt.opciones) if (indice_busqueda, i_alt, i_op) not in excluir]
        if opciones:
            resultado.append(Alternativa(dia_semana=alt.dia_semana, fecha=alt.fecha, opciones=opciones, avisos=alt.avisos))
    return resultado


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
    anonimizar = not _categoria_es_activa(profesional)
    decimales = decimales_configurados(conn)

    listas_alternativas = [
        _filtrar_excluidas(resolver_busqueda(conn, globales, b).alternativas, i, excluir)
        for i, b in enumerate(busquedas)
    ]
    ids_consultorio = sorted({
        t.id_consultorio for alts in listas_alternativas for alt in alts for op in alt.opciones for t in op.tramos
    })
    consultorios = _mapa_consultorios_basico(conn, ids_consultorio)
    imagenes = imagenes_de_consultorios(conn, ids_consultorio)
    mostrar_edificio = len({c["IdEdificio"] for c in consultorios.values()}) > 1
    mostrar_consultorio = not globales.detalle_reducido

    altura = (
        6 * cm + 3 * cm + len(busquedas) * 6 * cm + len(ids_consultorio) * 2 * 0.5 * cm
        + (len(imagenes) // 2 + 1) * 7 * cm + 3 * cm
    ) * 1.2

    def _construir_story(ancho: float) -> list:
        story = list(encabezado_espacio(conn, ancho))

        story.append(encabezado(1, f"Búsqueda solicitada por {_nombre_completo(profesional)}", ancho))
        story.append(Spacer(1, 8))
        story.append(encabezado(2, "Criterios de búsqueda generales", ancho))
        story.append(Spacer(1, 6))
        story.extend(_texto_criterios_globales(conn, globales))
        story.append(Spacer(1, 10))

        for i, (busqueda, alternativas) in enumerate(zip(busquedas, listas_alternativas)):
            story.append(encabezado(2, f"Búsqueda {i + 1}", ancho))
            story.append(Spacer(1, 6))
            story.append(encabezado(3, "Criterios de búsqueda seleccionados", ancho))
            story.append(Spacer(1, 4))
            story.extend(_texto_criterios_busqueda(busqueda))
            story.append(Spacer(1, 6))
            story.append(encabezado(3, "Coincidencias de la búsqueda", ancho))
            story.append(Spacer(1, 4))
            story.extend(_texto_coincidencias(busqueda, alternativas, consultorios, anonimizar, mostrar_edificio, mostrar_consultorio, decimales))
            story.append(Spacer(1, 10))

        # Con detalle reducido no se identifica qué consultorio puntual se
        # ofrece (ver `Busqueda`/`_detalle_tramo`) — una foto es, en los
        # hechos, el consultorio mostrado sin ambigüedad, así que esta
        # sección completa no tiene sentido en ese modo.
        if not globales.detalle_reducido:
            story.append(encabezado(2, "Fotos de los consultorios que intervienen en las búsquedas", ancho))
            story.append(Spacer(1, 8))
            story.extend(_bloque_consultorios_intervinientes(conn, consultorios, imagenes, anonimizar, mostrar_edificio, ancho, decimales))
        return story

    ruta = os.path.join(directorio, "Oferta consultorios.pdf")
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta
