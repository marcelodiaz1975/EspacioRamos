"""Texto compartido por el PDF y el texto para portapapeles (WhatsApp) de
Oferta de consultorios: arma, a partir de una búsqueda ya resuelta con
`app.negocio.oferta_busqueda.resolver_busqueda`, las mismas líneas de
texto plano (resumen de la búsqueda pedida, detalle de cada alternativa
encontrada, comentarios de edificio) para que ambos formatos de salida
digan lo mismo con distinta presentación — el PDF envuelve estas líneas
en Paragraphs con estilos y encabezados, el texto de WhatsApp las arma
con la sintaxis de WhatsApp (*negrita*).

`avisos_planos` (horas aisladas asignadas dentro de un horario regular
ofrecido) ya NO forma parte de ninguno de los dos documentos — pedido
explícito de la clienta: el profesional no tiene por qué verlo, es un
dato interno del espacio. Se usa en cambio para un aviso en pantalla al
operador, ver `app.gui.pantallas.oferta._PanelOferta._generar_y_mostrar`.

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

from app.negocio.formato import decimales_configurados, fecha_larga, formatear_valor, hora_fmt
from app.negocio.oferta_busqueda import (
    TIPO_AISLADA,
    Alternativa,
    Busqueda,
    CriteriosGlobales,
    Opcion,
    TramoCobertura,
    resolver_busquedas_documento,
)
from app.negocio.plantillas_texto import (
    DEFAULT_OFERTA_BUSQUEDA_COMENTARIO_ALTERNATIVAS_OFRECIDAS,
    DEFAULT_OFERTA_BUSQUEDA_COMENTARIO_RESERVAS_AISLADAS,
    DEFAULT_OFERTA_BUSQUEDA_COMENTARIO_RESERVAS_REGULARES,
    resolver_plantilla,
)
from app.repositorio.registro import obtener_repositorio

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
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos Consultorios"
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
    """IdLocalidad/NombreLocalidad (vía LEFT JOIN, un edificio puede no
    tener localidad cargada): solo los usa la previsualización interna
    de la operadora (`_lineas_opcion_previsualizacion`), para anteponer
    la localidad cuando hay más de una entre los resultados — el
    documento final para el profesional nunca la menciona."""
    if not ids_consultorio:
        return {}
    placeholders = ", ".join("?" for _ in ids_consultorio)
    filas = conn.execute(
        f"""
        SELECT c.IdConsultorio, c.NumeroConsultorio, c.ValorHoraRegularActual,
               u.IdUnidad, u.Departamento, e.IdEdificio, e.Nombre AS NombreEdificio,
               l.IdLocalidad, l.Localidad AS NombreLocalidad
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        LEFT JOIN Localidad l ON l.IdLocalidad = e.IdLocalidad
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
    (etiqueta de día, opción) — la combinación Y/O entre búsquedas
    (`app.negocio.oferta_busqueda.resolver_busquedas_documento`) ya se
    resolvió antes de llegar acá, así que alcanza con concatenar en
    orden lo que haya quedado."""
    planas = []
    for alternativas in listas_alternativas:
        for alt in alternativas:
            etiqueta = etiqueta_dia(alt.dia_semana, alt.fecha)
            for opcion in alt.opciones:
                planas.append((etiqueta, opcion))
    return planas


def avisos_planos(listas_alternativas: list[list[Alternativa]]) -> list[str]:
    """Avisos de todas las búsquedas, sin duplicados y en orden de
    aparición — ya no van al PDF/texto (ver `avisos_para_documento`), solo
    al aviso en pantalla."""
    avisos: list[str] = []
    for alternativas in listas_alternativas:
        for alt in alternativas:
            for aviso in alt.avisos:
                if aviso not in avisos:
                    avisos.append(aviso)
    return avisos


def avisos_para_documento(
    conn: sqlite3.Connection, globales: CriteriosGlobales, busquedas: list[Busqueda],
) -> list[str]:
    """Pedido explícito de la clienta: los avisos de hora aislada asignada
    dentro de un horario regular ofrecido ya no van impresos en el PDF/
    texto — se usan para un aviso en pantalla, al operador, nada más. Esta
    función resuelve la búsqueda igual que `previsualizar_documento` (sin
    aplicar `excluir` — el aviso tiene sentido apenas se arma la
    búsqueda, antes incluso de que el operador llegue a destildar
    opciones puntuales en la previsualización) y devuelve la misma lista
    sin duplicados que antes se embebía en el documento."""
    return avisos_planos(resolver_busquedas_documento(conn, globales, busquedas))


def identificacion_efectiva(globales: CriteriosGlobales) -> tuple[bool, bool]:
    """(mostrar_unidad, mostrar_consultorio) a partir de `globales.
    identificar_unidad`/`identificar_consultorio`, normalizado: no tiene
    sentido mostrar el consultorio sin la unidad que lo contiene, así
    que `identificar_consultorio` sin `identificar_unidad` no muestra
    ninguno de los dos — mismo criterio que ya impide esa combinación
    desde la pantalla (`_PanelOferta._al_desmarcar_identificar_unidad`),
    repetido acá por las dudas para quien arme un `CriteriosGlobales` a
    mano (ej. tests) sin pasar por la pantalla."""
    mostrar_unidad = globales.identificar_unidad
    mostrar_consultorio = globales.identificar_unidad and globales.identificar_consultorio
    return mostrar_unidad, mostrar_consultorio


def detalle_tramo(
    etiqueta: str, t: TramoCobertura, c: sqlite3.Row, mostrar_edificio: bool, mostrar_unidad: bool,
    mostrar_consultorio: bool, anonimizar: bool, mostrar_valor: bool = False, decimales: int = 2,
) -> str:
    """Con consultorio (detalle completo): "Viernes de 13 a 16hs
    consultorio 4 del EP "K" en Ramos 2" (el edificio se omite si hay uno
    solo). Sin consultorio pero con unidad (detalle reducido de siempre):
    "Viernes de 13 a 16hs en la unidad del EP "K" en Ramos 2". Sin
    unidad ni consultorio ("solo días y horarios", pedido explícito de
    la clienta): "Viernes de 13 a 16hs" a secas — tampoco se identifica
    el edificio en ese caso (`mostrar_edificio` solo aplica si `mostrar_
    unidad` también está activo: nombrar el edificio sin la unidad
    seguiría siendo identificar el lugar, lo que se quiere evitar del
    todo en este modo). `mostrar_valor` agrega el valor por hora al
    final ("- Hora regular $X") — solo tiene sentido junto con un
    consultorio identificado, si no no hay un valor puntual del que
    hablar."""
    rango = f"{etiqueta} de {hora_fmt(t.hora_inicio)[:-2]} a {hora_fmt(t.hora_fin)}"
    if mostrar_consultorio:
        unidad_txt = f"- Unidad {c['IdUnidad']}" if anonimizar else f"del {c['Departamento']}"
        texto = f"{rango} consultorio {c['NumeroConsultorio']} {unidad_txt}"
    elif mostrar_unidad:
        unidad_txt = f"en la Unidad {c['IdUnidad']}" if anonimizar else f"en la unidad del {c['Departamento']}"
        texto = f"{rango} {unidad_txt}"
    else:
        texto = rango
    if mostrar_edificio and mostrar_unidad:
        texto += f" en {c['NombreEdificio']}"
    if mostrar_valor and mostrar_consultorio:
        texto += f" - Hora regular {formatear_valor(c['ValorHoraRegularActual'], decimales)}"
    return texto


def lineas_opcion(
    etiqueta: str, opcion: Opcion, consultorios: dict, mostrar_edificio: bool, mostrar_unidad: bool,
    mostrar_consultorio: bool, anonimizar: bool, mostrar_valor: bool = False, decimales: int = 2,
) -> list[str]:
    """Una línea por tramo — una sola si es un consultorio solo, varias si
    es una combinación (una por cada consultorio que interviene)."""
    lineas = []
    for t in opcion.tramos:
        c = consultorios.get(t.id_consultorio)
        if c is None:
            continue
        lineas.append(
            detalle_tramo(etiqueta, t, c, mostrar_edificio, mostrar_unidad, mostrar_consultorio, anonimizar, mostrar_valor, decimales)
        )
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


# Claves de los tres comentarios fijos, independientes entre sí (pedido
# explícito de la clienta, reemplaza al bloque único de la vuelta
# anterior): cada uno se tilda por separado en la previsualización
# ("Comentarios a incluír", `app.gui.pantallas.oferta._DialogoPrevisualizacion`),
# TODOS destildados por defecto, y cada uno es a su vez editable como su
# propio texto en "Textos del sistema" (ver `app.negocio.plantillas_texto`).
COMENTARIO_RESERVAS_REGULARES = "reservas_regulares"
COMENTARIO_RESERVAS_AISLADAS = "reservas_aisladas"
COMENTARIO_ALTERNATIVAS_OFRECIDAS = "alternativas_ofrecidas"

_PLANTILLAS_COMENTARIOS_FIJOS = {
    COMENTARIO_RESERVAS_REGULARES: (
        "oferta_busqueda_comentario_reservas_regulares", DEFAULT_OFERTA_BUSQUEDA_COMENTARIO_RESERVAS_REGULARES,
    ),
    COMENTARIO_RESERVAS_AISLADAS: (
        "oferta_busqueda_comentario_reservas_aisladas", DEFAULT_OFERTA_BUSQUEDA_COMENTARIO_RESERVAS_AISLADAS,
    ),
    COMENTARIO_ALTERNATIVAS_OFRECIDAS: (
        "oferta_busqueda_comentario_alternativas_ofrecidas", DEFAULT_OFERTA_BUSQUEDA_COMENTARIO_ALTERNATIVAS_OFRECIDAS,
    ),
}


def comentarios_fijos(conn: sqlite3.Connection, incluidos: set[str]) -> list[str]:
    """Una línea por cada comentario fijo tildado en `incluidos` (alguna
    de las tres claves de arriba), en el orden fijo "Reservas regulares"/
    "Reservas aisladas"/"Alternativas ofrecidas" — sin importar el orden
    en que se hayan tildado los checks. Vacío si no se tildó ninguno (ya
    no van siempre, como en la vuelta anterior de este mecanismo)."""
    return [
        resolver_plantilla(conn, clave_plantilla, default)
        for clave, (clave_plantilla, default) in _PLANTILLAS_COMENTARIOS_FIJOS.items()
        if clave in incluidos
    ]


def edificios_comentario(conn: sqlite3.Connection, ids_edificio_resultado: set[int]) -> list[str]:
    """Una línea por edificio de `ids_edificio_resultado`, para el
    comentario que aclara direcciones cuando el documento menciona más de
    un edificio."""
    if not ids_edificio_resultado:
        return []
    placeholders = ", ".join("?" for _ in ids_edificio_resultado)
    filas = conn.execute(
        f"SELECT e.Nombre, e.Domicilio, loc.Localidad AS DomicilioLocalidad FROM Edificio e "
        f"LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad "
        f"WHERE e.IdEdificio IN ({placeholders}) ORDER BY e.IdEdificio",
        list(ids_edificio_resultado),
    ).fetchall()
    return [_texto_edificio_comentario(f) for f in filas]


def _lineas_opcion_previsualizacion(
    etiqueta: str, opcion: Opcion, consultorios: dict, mostrar_localidad: bool, mostrar_edificio: bool,
    decimales: int,
) -> list[str]:
    """Para la pantalla de previsualización (operadora, nunca el
    profesional): SIEMPRE con el detalle completo (unidad + consultorio)
    y sin anonimizar, sin importar los checks "Identificar unidad/
    consultorio" (que solo rigen lo que termina viendo el profesional en
    el documento final) ni la categoría del profesional — la operadora
    necesita identificar bien qué está tildando/destildando. Localidad se
    antepone si hay más de una entre los resultados de esta búsqueda
    (mismo criterio "solo si hace falta desambiguar" que ya usa
    `mostrar_edificio`)."""
    lineas = []
    for t in opcion.tramos:
        c = consultorios.get(t.id_consultorio)
        if c is None:
            continue
        texto = detalle_tramo(etiqueta, t, c, mostrar_edificio, True, True, False, mostrar_valor=True, decimales=decimales)
        if mostrar_localidad and c["NombreLocalidad"]:
            texto = f"{c['NombreLocalidad']} - {texto}"
        lineas.append(texto)
    return lineas


def previsualizar_documento(
    conn: sqlite3.Connection, id_profesional: int, globales: CriteriosGlobales, busquedas: list[Busqueda],
) -> list[tuple[int, int, int, str, float, float]]:
    """Para la pantalla de previsualización (`app.gui.pantallas.oferta`):
    una entrada por cada opción encontrada, ya con la combinación Y/O
    entre búsquedas aplicada (`resolver_busquedas_documento`), junto con
    la tripleta de índices (búsqueda, alternativa/día, opción) que la
    identifica para poder excluirla puntualmente sin descartar el resto
    de la búsqueda (ver `excluir` en `generar_pdf_oferta_busqueda` /
    `generar_texto_oferta_busqueda`), y el rango horario que cubre la
    opción completa (min/max de sus tramos — un solo tramo salvo
    combinación) para que el diálogo pueda calcular superposiciones
    ("Seleccionar solo una opción por bloque").

    El texto de cada fila SIEMPRE muestra el detalle completo (ver
    `_lineas_opcion_previsualizacion`) — independiente de "Identificar
    unidad/consultorio", que solo rige el documento final."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    decimales = decimales_configurados(conn)

    resultados = resolver_busquedas_documento(conn, globales, busquedas)
    ids_consultorio = sorted({
        t.id_consultorio for alts in resultados for alt in alts for op in alt.opciones for t in op.tramos
    })
    consultorios = mapa_consultorios_basico(conn, ids_consultorio)
    ids_edificio_resultado = {c["IdEdificio"] for c in consultorios.values()}
    ids_localidad_resultado = {c["IdLocalidad"] for c in consultorios.values()}
    mostrar_edificio = len(ids_edificio_resultado) > 1
    mostrar_localidad = len(ids_localidad_resultado) > 1

    filas: list[tuple[int, int, int, str, float, float]] = []
    for i_busqueda, alternativas in enumerate(resultados):
        for i_alt, alt in enumerate(alternativas):
            etiqueta = etiqueta_dia(alt.dia_semana, alt.fecha)
            for i_op, opcion in enumerate(alt.opciones):
                lineas = _lineas_opcion_previsualizacion(etiqueta, opcion, consultorios, mostrar_localidad, mostrar_edificio, decimales)
                hora_inicio = min(t.hora_inicio for t in opcion.tramos)
                hora_fin = max(t.hora_fin for t in opcion.tramos)
                filas.append((i_busqueda, i_alt, i_op, " / ".join(lineas), hora_inicio, hora_fin))
    return filas


def opciones_a_destildar_por_bloque(
    filas: list[tuple[int, int, int, str, float, float]],
) -> set[tuple[int, int, int]]:
    """"Seleccionar solo una opción por bloque" (pedido explícito de la
    clienta, ejemplo real: buscando lunes 9-18hs con 3hs mínimas, si
    aparecen las alternativas 9-13hs, 9-12hs y 14-18hs, tiene que quedar
    tildada 14-18hs por no superponerse con ninguna otra, y 9-13hs por
    ser la más extensa de las dos que SÍ se superponen entre sí).

    Agrupa, dentro de cada día (misma búsqueda + misma alternativa), las
    opciones que se superponen en horario con al menos otra — aunque sea
    de forma transitiva (A con B, B con C, sin que A y C se toquen entre
    sí) — y devuelve las tripletas a destildar: todas las de cada grupo
    salvo la(s) de mayor extensión (hora_fin - hora_inicio). Un grupo
    sin ningún superpuesto (tamaño 1) no aporta nada al resultado, sin
    importar cuántas opciones distintas haya ese día. Un empate exacto
    de extensión entre las más extensas de un grupo no destilda a
    ninguna de esas dos — decisión explícita de la clienta: "no tengo
    claro un criterio... deja las dos o más opciones tildadas y eso
    queda a mi criterio en el momento"."""
    por_dia: dict[tuple[int, int], list[tuple[int, int, int, float, float]]] = {}
    for i_busqueda, i_alt, i_op, _texto, hora_inicio, hora_fin in filas:
        por_dia.setdefault((i_busqueda, i_alt), []).append((i_busqueda, i_alt, i_op, hora_inicio, hora_fin))

    destildar: set[tuple[int, int, int]] = set()
    for opciones in por_dia.values():
        if len(opciones) < 2:
            continue
        # Unión por conjuntos disjuntos (pocas opciones por día, no hace
        # falta nada más sofisticado) para agrupar las conectadas por
        # superposición, directa o transitiva.
        padres = list(range(len(opciones)))

        def raiz(i: int) -> int:
            while padres[i] != i:
                i = padres[i]
            return i

        for i in range(len(opciones)):
            for j in range(i + 1, len(opciones)):
                inicio_i, fin_i = opciones[i][3], opciones[i][4]
                inicio_j, fin_j = opciones[j][3], opciones[j][4]
                if inicio_i < fin_j and inicio_j < fin_i:
                    ri, rj = raiz(i), raiz(j)
                    if ri != rj:
                        padres[ri] = rj

        grupos: dict[int, list[int]] = {}
        for i in range(len(opciones)):
            grupos.setdefault(raiz(i), []).append(i)

        for indices in grupos.values():
            if len(indices) < 2:
                continue
            duraciones = {i: opciones[i][4] - opciones[i][3] for i in indices}
            maxima = max(duraciones.values())
            for i in indices:
                if duraciones[i] < maxima:
                    destildar.add(opciones[i][:3])
    return destildar
