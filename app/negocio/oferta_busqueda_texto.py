"""Texto compartido por el PDF y el texto para portapapeles (WhatsApp) de
Oferta de consultorios: arma, a partir de una búsqueda ya resuelta con
`app.negocio.oferta_busqueda.resolver_busqueda`, las mismas líneas de
texto plano (resumen de la búsqueda pedida, detalle de cada alternativa
encontrada, comentarios de edificio/avisos) para que ambos formatos de
salida digan lo mismo con distinta presentación — el PDF envuelve estas
líneas en Paragraphs con estilos y encabezados, el texto de WhatsApp las
arma con la sintaxis de WhatsApp (*negrita*, _itálica_).

El valor por hora es opcional (`mostrar_valor` en `detalle_tramo`/
`lineas_opcion`): el PDF lo omite en el listado de alternativas porque ya
se muestra debajo de cada foto (`app.pdf.oferta_busqueda_pdf._pie_foto`)
— repetirlo ahí sería redundante. El texto de WhatsApp no tiene fotos, así
que sí lo necesita cuando se identifica el consultorio puntual (si el
detalle es reducido y no se nombra ningún consultorio, tampoco hay valor
que mostrar). Tampoco se detallan los criterios de la búsqueda (fechas,
combinación, características, valor máximo, cantidad de horas mínimas):
son los que se usaron para ENCONTRAR las alternativas, no hacen falta
para elegir entre ellas — el profesional ya sabe lo que pidió."""
from __future__ import annotations

import sqlite3

from app.negocio.formato import fecha_larga, formatear_valor, hora_fmt
from app.negocio.oferta_busqueda import TIPO_AISLADA, Alternativa, Busqueda, Opcion, TramoCobertura

_ES_ACTIVO = ("R", "A", "E", "X", "B")


def categoria_es_activa(profesional: sqlite3.Row) -> bool:
    """R/A/E/X/B muestran el departamento real, C se anonimiza como
    "Unidad N" — distinto del resto del sistema (que solo considera
    activas a R/A/B/E) porque esto lo arma el operador para un
    profesional puntual, no es un documento suelto sin contexto."""
    return profesional["CategoriaProfesional"] in _ES_ACTIVO


def nombre_archivo_oferta(conn: sqlite3.Connection, profesional: sqlite3.Row) -> str:
    """"Oferta de consultorios - {Tratamiento} {Nombre} {Apellido}.pdf"
    para categorías activas; genérico con el nombre del espacio para
    categoría C, igual que la anonimización del contenido del documento."""
    if categoria_es_activa(profesional):
        tratamiento = profesional["Tratamiento"] or ""
        nombre = profesional["NombrePila"] or ""
        apellido = profesional["Apellido"]
        partes = " ".join(p for p in (tratamiento, nombre, apellido) if p)
        return f"Oferta de consultorios - {partes}.pdf"
    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"
    return f"Oferta de consultorios - {nombre_espacio}.pdf"


def filtrar_excluidas(alternativas: list[Alternativa], indice_busqueda: int, excluir: set[tuple[int, int, int]]) -> list[Alternativa]:
    """Deja afuera opciones puntuales marcadas en `excluir` (índice de
    búsqueda, índice de alternativa/día, índice de opción dentro de ese
    día) — si un día se queda sin ninguna opción, el día entero desaparece
    (equivale a no haber encontrado nada ese día)."""
    resultado = []
    for i_alt, alt in enumerate(alternativas):
        opciones = [op for i_op, op in enumerate(alt.opciones) if (indice_busqueda, i_alt, i_op) not in excluir]
        if opciones:
            resultado.append(Alternativa(dia_semana=alt.dia_semana, fecha=alt.fecha, opciones=opciones, avisos=alt.avisos))
    return resultado


def mapa_consultorios_basico(conn: sqlite3.Connection, ids_consultorio: list[int]) -> dict[int, sqlite3.Row]:
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


def resumen_busqueda(busqueda: Busqueda, tipo_busqueda: str) -> str:
    """"Viernes de 13 a 18hs" (Regular) o "Del 1 de septiembre de 2026 al 7
    de septiembre de 2026, Viernes de 13 a 18hs" (Aislada, donde el rango
    de fechas sí hace falta porque no es recurrente)."""
    dias = ", ".join(busqueda.dias)
    desde, hasta = hora_fmt(busqueda.hora_desde)[:-2], hora_fmt(busqueda.hora_hasta)
    resumen = f"{dias} de {desde} a {hasta}"
    if tipo_busqueda == TIPO_AISLADA:
        return f"Del {fecha_larga(busqueda.fecha_desde)} al {fecha_larga(busqueda.fecha_hasta)}, {resumen}"
    return resumen


def etiqueta_dia(dia_semana: str, fecha: str | None) -> str:
    return f"{dia_semana} {fecha_larga(fecha)}" if fecha else dia_semana


def alternativas_planas(listas_alternativas: list[list[Alternativa]]) -> list[tuple[str, Opcion]]:
    """Aplana todas las alternativas (una por día/fecha con cobertura) de
    todas las búsquedas del documento en una sola lista de a pares
    (etiqueta de día, opción) — cada búsqueda ya se resuelve de forma
    independiente (todavía no hay combinación Y/O real entre búsquedas
    distintas), así que alcanza con concatenar en orden."""
    planas = []
    for alternativas in listas_alternativas:
        for alt in alternativas:
            etiqueta = etiqueta_dia(alt.dia_semana, alt.fecha)
            for opcion in alt.opciones:
                planas.append((etiqueta, opcion))
    return planas


def avisos_planos(listas_alternativas: list[list[Alternativa]]) -> list[str]:
    """Avisos de todas las búsquedas, sin duplicados y en orden de
    aparición — van al comentario general, no repetidos por alternativa."""
    avisos: list[str] = []
    for alternativas in listas_alternativas:
        for alt in alternativas:
            for aviso in alt.avisos:
                if aviso not in avisos:
                    avisos.append(aviso)
    return avisos


def detalle_tramo(
    etiqueta: str, t: TramoCobertura, c: sqlite3.Row, mostrar_edificio: bool, mostrar_consultorio: bool, anonimizar: bool,
    mostrar_valor: bool = False, decimales: int = 2,
) -> str:
    """Con consultorio (modo normal): "Viernes de 13 a 16hs consultorio 4
    del EP "K" en Ramos 2" (el edificio se omite si hay uno solo). Sin
    consultorio (detalle reducido): "Viernes de 13 a 16hs en la unidad del
    EP "K" en Ramos 2". `mostrar_valor` agrega el valor por hora al final
    ("- Hora regular $X") — solo tiene sentido junto con un consultorio
    identificado, si no no hay un valor puntual del que hablar."""
    rango = f"{etiqueta} de {hora_fmt(t.hora_inicio)[:-2]} a {hora_fmt(t.hora_fin)}"
    if mostrar_consultorio:
        unidad_txt = f"- Unidad {c['IdUnidad']}" if anonimizar else f"del {c['Departamento']}"
        texto = f"{rango} consultorio {c['NumeroConsultorio']} {unidad_txt}"
    else:
        unidad_txt = f"en la Unidad {c['IdUnidad']}" if anonimizar else f"en la unidad del {c['Departamento']}"
        texto = f"{rango} {unidad_txt}"
    if mostrar_edificio:
        texto += f" en {c['NombreEdificio']}"
    if mostrar_valor and mostrar_consultorio:
        texto += f" - Hora regular {formatear_valor(c['ValorHoraRegularActual'], decimales)}"
    return texto


def lineas_opcion(
    etiqueta: str, opcion: Opcion, consultorios: dict, mostrar_edificio: bool, mostrar_consultorio: bool, anonimizar: bool,
    mostrar_valor: bool = False, decimales: int = 2,
) -> list[str]:
    """Una línea por tramo — una sola si es un consultorio solo, varias si
    es una combinación (una por cada consultorio que interviene)."""
    lineas = []
    for t in opcion.tramos:
        c = consultorios.get(t.id_consultorio)
        if c is None:
            continue
        lineas.append(detalle_tramo(etiqueta, t, c, mostrar_edificio, mostrar_consultorio, anonimizar, mostrar_valor, decimales))
    return lineas


def _texto_edificio_comentario(edificio: sqlite3.Row) -> str:
    """"Ramos 1 corresponde a Av. Rivadavia 13876, Ramos Mejía." — para el
    comentario que aclara a qué dirección corresponde cada edificio,
    cuando el documento menciona más de uno."""
    if edificio["Domicilio"] and edificio["DomicilioLocalidad"]:
        ubicacion = f"{edificio['Domicilio']}, {edificio['DomicilioLocalidad']}"
    else:
        ubicacion = edificio["Domicilio"] or edificio["DomicilioLocalidad"] or "—"
    return f"{edificio['Nombre']} corresponde a {ubicacion}."


def edificios_comentario(conn: sqlite3.Connection, ids_edificio_resultado: set[int]) -> list[str]:
    """Una línea por edificio de `ids_edificio_resultado`, para el
    comentario que aclara direcciones cuando el documento menciona más de
    un edificio."""
    if not ids_edificio_resultado:
        return []
    placeholders = ", ".join("?" for _ in ids_edificio_resultado)
    filas = conn.execute(
        f"SELECT Nombre, Domicilio, DomicilioLocalidad FROM Edificio WHERE IdEdificio IN ({placeholders}) ORDER BY IdEdificio",
        list(ids_edificio_resultado),
    ).fetchall()
    return [_texto_edificio_comentario(f) for f in filas]
