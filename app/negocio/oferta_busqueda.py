"""Motor de búsqueda de disponibilidad para armar una Oferta de
consultorios (PDF o mensaje de WhatsApp) a pedido de un profesional.

Distinto de Lista de espera (`app.negocio.lista_espera`): ahí un pedido se
persiste en `ListaEspera` y queda en seguimiento (Activo/Resuelto/
Descartado) hasta que se resuelve. Acá la búsqueda es ad-hoc — se arma y
se resuelve en el momento para un documento puntual, sin persistir nada.

Dos niveles de filtros:

  `CriteriosGlobales` — comunes a TODAS las búsquedas del mismo documento:
  tipo (Regular/Aislada, no se pueden mezclar en un mismo documento),
  localidad, edificios, unidades y consultorios sobre los que se busca.

  `Busqueda` — particulares de cada búsqueda dentro del documento: rango
  de fechas, días, horario, si se admite combinar consultorios y con qué
  alcance (nunca cruza de edificio — ver `combinacion`), características
  del consultorio, valor máximo por hora regular, cantidad de horas
  mínimas dentro del bloque (en vez de todo el bloque), y cómo se combina
  con la búsqueda siguiente ("Y"/"O") cuando hay más de una.

Regular vs Aislada:
  Regular — los días pedidos son de la semana, recurrentes: hace falta que
  TODOS tengan cobertura (si falta uno, la búsqueda no tiene alternativas).
  La cobertura de cada día se evalúa contra el mes de `fecha_desde"
  (reutiliza `grilla.calcular_ocupacion_regular`).

  Aislada — los días pedidos acotan qué días de la semana entran dentro
  del rango [fecha_desde, fecha_hasta]: se evalúa CADA fecha calendario
  del rango que caiga en esos días, y cada una que tenga cobertura es una
  alternativa aparte (no hace falta que todas la tengan).

`Busqueda.combinacion` — alcance de la combinación de consultorios:
  SIN_COMBINAR         — un solo consultorio, no se admite combinar.
  COMBINAR_MISMA_UNIDAD — se puede combinar, pero sin salir de la unidad
                          elegida para el primer tramo (si en algún
                          momento no queda ningún consultorio libre DE ESA
                          unidad, la cobertura de ese bloque falla en vez
                          de saltar a otra unidad).
  COMBINAR_MISMO_EDIFICIO — se puede combinar sin restricción de unidad,
                          pero nunca cruza de edificio (cada edificio del
                          alcance es un canal independiente).

Colores de coincidencia (igual jerarquía que Lista de espera, pero sin
rojo — la combinación nunca cruza edificios, así que ese caso no existe):
  verde    — un solo consultorio cubre todo el bloque.
  amarillo — hace falta combinar, todos los consultorios de la misma unidad.
  naranja  — hace falta combinar, consultorios de distintas unidades del
             mismo edificio (nunca ocurre con COMBINAR_MISMA_UNIDAD).

Varias coincidencias por día: cuando más de un consultorio (de cualquier
unidad/edificio del alcance) puede cubrir el bloque por sí solo, se
reportan TODAS esas opciones (todas "verde") en vez de quedarse con la
primera — el operador decide cuál ofrecer. Si ninguna cubre sola, se
ofrece como respaldo UNA combinación (la primera que se encuentra), no se
buscan todas las combinaciones posibles.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.negocio.dias import (
    fecha_a_dia_semana,
    fecha_actual,
    parsear_periodo,
    periodo_actual,
    primer_dia_mes,
    sumar_meses,
    ultimo_dia_mes,
)
from app.negocio.grilla import calcular_ocupacion_regular

TIPO_REGULAR = "Regular"
TIPO_AISLADA = "Aislada"

SALIDA_PDF = "PDF"
SALIDA_TEXTO = "Texto"

SIN_COMBINAR = "Ninguna"
COMBINAR_MISMA_UNIDAD = "MismaUnidad"
COMBINAR_MISMO_EDIFICIO = "MismoEdificio"

VERDE = "verde"
AMARILLO = "amarillo"
NARANJA = "naranja"


@dataclass
class CriteriosGlobales:
    tipo_busqueda: str  # TIPO_REGULAR | TIPO_AISLADA
    ids_edificio: list[int]
    localidad: str | None = None
    ids_unidad: list[int] | None = None  # None = todas las de los edificios seleccionados
    ids_consultorio: list[int] | None = None  # None = todos los de las unidades seleccionadas
    salida: str = SALIDA_PDF  # SALIDA_PDF | SALIDA_TEXTO — a dónde vuelca el resultado, no es un criterio de búsqueda
    detalle_reducido: bool = False  # el detalle de cada alternativa omite el consultorio (y su valor)


@dataclass
class Busqueda:
    fecha_desde: str
    fecha_hasta: str | None  # None solo válido en Regular (vigencia indefinida)
    dias: list[str]
    hora_desde: float
    hora_hasta: float
    combinacion: str = COMBINAR_MISMO_EDIFICIO  # SIN_COMBINAR | COMBINAR_MISMA_UNIDAD | COMBINAR_MISMO_EDIFICIO
    apto_camilla: bool = False
    ventana: bool = False
    sillones: bool = False
    tamano: str | None = None
    valor_maximo_hora: float | None = None
    cantidad_horas_minimas: float | None = None
    combinacion_con_siguiente: str | None = None  # "Y" | "O" | None (última búsqueda)


@dataclass
class TramoCobertura:
    id_consultorio: int
    hora_inicio: float
    hora_fin: float


@dataclass
class Opcion:
    """Una forma posible de cubrir el bloque pedido: un color (según haga
    falta combinar o no) y los tramos que la componen (uno solo si no hace
    falta combinar)."""
    color: str
    tramos: list[TramoCobertura]


@dataclass
class Alternativa:
    """Una alternativa encontrada, con todas las opciones de cobertura que
    se hayan podido armar para ese día. `fecha` es None en Regular (el día
    de la semana se cubre de forma recurrente); en Aislada es la fecha
    calendario puntual que tuvo cobertura.

    `avisos` — solo se completa en Regular: fechas puntuales del mes en
    las que, pese a que el horario da libre de forma recurrente, hay una
    ReservaAislada confirmada superpuesta con alguno de los tramos
    ofrecidos. La disponibilidad regular se calcula IGNORANDO las horas
    aisladas (no las bloquea — una reserva aislada no debería impedir
    ofrecer un horario regular a futuro), pero se avisa igual para poder
    evaluar más adelante si conviene reubicar esa hora aislada."""
    dia_semana: str
    fecha: str | None
    opciones: list[Opcion]
    avisos: list[str] = field(default_factory=list)


@dataclass
class ResultadoBusqueda:
    alternativas: list[Alternativa] = field(default_factory=list)


def fecha_inicio_default(conn: sqlite3.Connection, tipo_busqueda: str) -> str:
    """Regular: 1er día del mes siguiente al período en curso. Aislada:
    mañana."""
    if tipo_busqueda == TIPO_REGULAR:
        anio, mes = parsear_periodo(sumar_meses(periodo_actual(conn), 1))
        return primer_dia_mes(anio, mes).isoformat()
    return (fecha_actual(conn) + timedelta(days=1)).isoformat()


def fecha_fin_default(tipo_busqueda: str, fecha_desde: str) -> str | None:
    """Regular: indefinida (None). Aislada: una semana (7 días) a partir
    de `fecha_desde`."""
    if tipo_busqueda == TIPO_REGULAR:
        return None
    return (date.fromisoformat(fecha_desde) + timedelta(days=7)).isoformat()


def _consultorios_candidatos(
    conn: sqlite3.Connection, globales: CriteriosGlobales, busqueda: Busqueda,
) -> list[sqlite3.Row]:
    filas = conn.execute(
        "SELECT c.*, u.IdEdificio AS IdEdificioReal FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad"
    ).fetchall()
    resultado = []
    for c in filas:
        if globales.ids_edificio and c["IdEdificioReal"] not in globales.ids_edificio:
            continue
        if globales.ids_unidad and c["IdUnidad"] not in globales.ids_unidad:
            continue
        if globales.ids_consultorio and c["IdConsultorio"] not in globales.ids_consultorio:
            continue
        if busqueda.apto_camilla and not c["AptoCamilla"]:
            continue
        if busqueda.ventana and not c["Ventana"]:
            continue
        if busqueda.sillones and not c["Sillones"]:
            continue
        if busqueda.tamano and (c["TamanoClasificacion"] or "").strip().lower() != busqueda.tamano.strip().lower():
            continue
        if busqueda.valor_maximo_hora is not None and (c["ValorHoraRegularActual"] or 0) > busqueda.valor_maximo_hora:
            continue
        resultado.append(c)
    return resultado


def _candidatos_por_edificio(candidatos: list[sqlite3.Row]) -> dict[int, dict[int, sqlite3.Row]]:
    por_edificio: dict[int, dict[int, sqlite3.Row]] = {}
    for c in candidatos:
        por_edificio.setdefault(c["IdEdificioReal"], {})[c["IdConsultorio"]] = c
    return por_edificio


def _elegir_consultorio(libres_ids: list[int], candidatos_por_id: dict, actual_id: int | None) -> int:
    if actual_id in libres_ids:
        return actual_id
    actual = candidatos_por_id.get(actual_id) if actual_id is not None else None
    if actual is not None:
        misma_unidad = [i for i in libres_ids if candidatos_por_id[i]["IdUnidad"] == actual["IdUnidad"]]
        if misma_unidad:
            return misma_unidad[0]
    return libres_ids[0]


def _libres_por_hora(candidatos_por_id: dict, horas: list[int], ocupado_lookup) -> dict[int, list[int]] | None:
    libres_por_hora = {}
    for h in horas:
        libres = [i for i in candidatos_por_id if not ocupado_lookup(i, h)]
        if not libres:
            return None
        libres_por_hora[h] = libres
    return libres_por_hora


def _combinacion_subrango(candidatos_por_id: dict, horas: list[int], libres_por_hora: dict, combinacion: str) -> list[TramoCobertura] | None:
    """Barrido hora por hora armando la combinación — asume que ya se
    probó que ningún consultorio solo cubre todo el sub-rango. Con
    COMBINAR_MISMA_UNIDAD, la unidad queda fija desde el primer tramo: si
    en algún momento no hay ningún consultorio libre DE ESA unidad, la
    cobertura falla entera en vez de saltar a otra unidad."""
    if combinacion == SIN_COMBINAR:
        return None

    unidad_fija: int | None = None
    tramos: list[TramoCobertura] = []
    actual_id: int | None = None
    inicio_tramo = horas[0]
    for h in horas:
        libres = libres_por_hora[h]
        if combinacion == COMBINAR_MISMA_UNIDAD and unidad_fija is not None:
            libres = [i for i in libres if candidatos_por_id[i]["IdUnidad"] == unidad_fija]
            if not libres:
                return None
        elegido = _elegir_consultorio(libres, candidatos_por_id, actual_id)
        if combinacion == COMBINAR_MISMA_UNIDAD and unidad_fija is None:
            unidad_fija = candidatos_por_id[elegido]["IdUnidad"]
        if actual_id is not None and elegido != actual_id:
            tramos.append(TramoCobertura(actual_id, inicio_tramo, h))
            inicio_tramo = h
        actual_id = elegido
    tramos.append(TramoCobertura(actual_id, inicio_tramo, horas[-1] + 1))
    return tramos


def _clasificar_color(candidatos_por_id: dict, ids_consultorio: set[int]) -> str:
    if len(ids_consultorio) == 1:
        return VERDE
    unidades = {candidatos_por_id[i]["IdUnidad"] for i in ids_consultorio}
    return AMARILLO if len(unidades) == 1 else NARANJA


def _opciones_en_horas(
    candidatos_por_edificio: dict[int, dict[int, sqlite3.Row]], horas: list[int], ocupado_lookup, combinacion: str,
) -> list[Opcion] | None:
    """None si ningún edificio del alcance puede cubrir estas horas (ni
    solo ni combinando). Si no, TODAS las opciones de un solo consultorio
    encontradas en cualquier edificio; si no hay ninguna, una combinación
    de respaldo (la primera que se encuentra recorriendo los edificios en
    orden)."""
    libres_por_edificio: dict[int, dict[int, list[int]]] = {}
    for id_edificio, candidatos_por_id in candidatos_por_edificio.items():
        libres_por_hora = _libres_por_hora(candidatos_por_id, horas, ocupado_lookup)
        if libres_por_hora is not None:
            libres_por_edificio[id_edificio] = libres_por_hora
    if not libres_por_edificio:
        return None

    opciones: list[Opcion] = []
    for id_edificio, libres_por_hora in libres_por_edificio.items():
        candidatos_por_id = candidatos_por_edificio[id_edificio]
        for id_consultorio in candidatos_por_id:
            if all(id_consultorio in libres_por_hora[h] for h in horas):
                tramo = TramoCobertura(id_consultorio, horas[0], horas[-1] + 1)
                opciones.append(Opcion(color=VERDE, tramos=[tramo]))
    if opciones:
        return opciones

    for id_edificio, libres_por_hora in libres_por_edificio.items():
        candidatos_por_id = candidatos_por_edificio[id_edificio]
        tramos = _combinacion_subrango(candidatos_por_id, horas, libres_por_hora, combinacion)
        if tramos is not None:
            color = _clasificar_color(candidatos_por_id, {t.id_consultorio for t in tramos})
            return [Opcion(color=color, tramos=tramos)]
    return None


def _opciones_con_duracion(
    candidatos_por_edificio: dict[int, dict[int, sqlite3.Row]], busqueda: Busqueda, ocupado_lookup,
) -> list[Opcion] | None:
    hd, hh = int(busqueda.hora_desde), int(busqueda.hora_hasta)
    dur = int(busqueda.cantidad_horas_minimas) if busqueda.cantidad_horas_minimas else hh - hd
    if dur <= 0 or dur > hh - hd:
        return None
    for inicio in range(hd, hh - dur + 1):
        opciones = _opciones_en_horas(candidatos_por_edificio, list(range(inicio, inicio + dur)), ocupado_lookup, busqueda.combinacion)
        if opciones is not None:
            return opciones
    return None


def _ocupado_regular(conn: sqlite3.Connection, anio: int, mes: int, dia_semana: str):
    mapa = calcular_ocupacion_regular(conn, anio, mes, dias=[dia_semana])
    return lambda id_consultorio, hora: mapa.get((id_consultorio, dia_semana, hora), False)


def _avisos_aislada_regular(conn: sqlite3.Connection, anio: int, mes: int, dia_semana: str, opciones: list[Opcion]) -> list[str]:
    """Fechas puntuales del mes que caen en `dia_semana` donde alguno de
    los tramos ofrecidos (de cualquier opción) se superpone con una
    ReservaAislada confirmada en ese consultorio — la disponibilidad
    regular no las tiene en cuenta para bloquear (ver docstring de
    `Alternativa.avisos`), pero se reportan para decisión manual."""
    avisos = []
    fecha = primer_dia_mes(anio, mes)
    ultimo = ultimo_dia_mes(anio, mes)
    tramos = [t for op in opciones for t in op.tramos]
    while fecha <= ultimo:
        if fecha_a_dia_semana(fecha) == dia_semana:
            fecha_iso = fecha.isoformat()
            for t in tramos:
                filas = conn.execute(
                    "SELECT * FROM ReservaAislada WHERE IdConsultorio = ? AND Fecha = ? AND Estado = 'Confirmada'",
                    (t.id_consultorio, fecha_iso),
                ).fetchall()
                for r in filas:
                    if r["HoraInicio"] < t.hora_fin and t.hora_inicio < r["HoraFin"]:
                        avisos.append(
                            f"Atención: el {fecha_iso} hay una hora aislada asignada en el consultorio "
                            f"#{t.id_consultorio} de {r['HoraInicio']:g} a {r['HoraFin']:g}hs, dentro de este bloque."
                        )
        fecha += timedelta(days=1)
    return avisos


def _ocupado_fecha(conn: sqlite3.Connection, fecha: date):
    dia_semana = fecha_a_dia_semana(fecha)
    fecha_iso = fecha.isoformat()
    ocupado: dict[tuple[int, int], bool] = {}
    for r in conn.execute("SELECT * FROM ReservaRegular WHERE DiaSemana = ?", (dia_semana,)):
        if r["VigenciaInicio"] > fecha_iso:
            continue
        if r["VigenciaFin"] and r["VigenciaFin"] < fecha_iso:
            continue
        for h in range(int(r["HoraInicio"]), int(r["HoraFin"])):
            ocupado[(r["IdConsultorio"], h)] = True
    for r in conn.execute("SELECT * FROM ReservaAislada WHERE Fecha = ? AND Estado = 'Confirmada'", (fecha_iso,)):
        for h in range(int(r["HoraInicio"]), int(r["HoraFin"])):
            ocupado[(r["IdConsultorio"], h)] = True
    return lambda id_consultorio, hora: ocupado.get((id_consultorio, hora), False)


def resolver_busqueda(conn: sqlite3.Connection, globales: CriteriosGlobales, busqueda: Busqueda) -> ResultadoBusqueda:
    candidatos = _consultorios_candidatos(conn, globales, busqueda)
    candidatos_por_edificio = _candidatos_por_edificio(candidatos)
    if not candidatos_por_edificio or not busqueda.dias:
        return ResultadoBusqueda()

    alternativas: list[Alternativa] = []

    if globales.tipo_busqueda == TIPO_REGULAR:
        anio, mes = date.fromisoformat(busqueda.fecha_desde).year, date.fromisoformat(busqueda.fecha_desde).month
        opciones_por_dia: dict[str, list[Opcion]] = {}
        for dia in busqueda.dias:
            opciones = _opciones_con_duracion(candidatos_por_edificio, busqueda, _ocupado_regular(conn, anio, mes, dia))
            if opciones is not None:
                opciones_por_dia[dia] = opciones
        if len(opciones_por_dia) != len(busqueda.dias):
            return ResultadoBusqueda()  # Regular: todos los días pedidos tienen que coincidir
        for dia in busqueda.dias:
            opciones = opciones_por_dia[dia]
            avisos = _avisos_aislada_regular(conn, anio, mes, dia, opciones)
            alternativas.append(Alternativa(dia_semana=dia, fecha=None, opciones=opciones, avisos=avisos))
    else:
        fecha = date.fromisoformat(busqueda.fecha_desde)
        fecha_fin = date.fromisoformat(busqueda.fecha_hasta) if busqueda.fecha_hasta else fecha
        while fecha <= fecha_fin:
            dia_semana = fecha_a_dia_semana(fecha)
            if dia_semana in busqueda.dias:
                opciones = _opciones_con_duracion(candidatos_por_edificio, busqueda, _ocupado_fecha(conn, fecha))
                if opciones is not None:
                    alternativas.append(Alternativa(dia_semana=dia_semana, fecha=fecha.isoformat(), opciones=opciones))
            fecha += timedelta(days=1)

    return ResultadoBusqueda(alternativas=alternativas)
