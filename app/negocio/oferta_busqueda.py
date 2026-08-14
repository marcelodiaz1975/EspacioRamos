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
  de fechas, días, horario, si se admite combinar consultorios (nunca
  cruza de edificio — "combinar" es siempre DENTRO de un mismo edificio),
  características del consultorio, valor máximo por hora regular, cantidad
  de horas mínimas dentro del bloque (en vez de todo el bloque), y cómo se
  combina con la búsqueda siguiente ("Y"/"O") cuando hay más de una.

Regular vs Aislada:
  Regular — los días pedidos son de la semana, recurrentes: hace falta que
  TODOS tengan cobertura (si falta uno, la búsqueda no tiene alternativas).
  La cobertura de cada día se evalúa contra el mes de `fecha_desde"
  (reutiliza `grilla.calcular_ocupacion_regular`).

  Aislada — los días pedidos acotan qué días de la semana entran dentro
  del rango [fecha_desde, fecha_hasta]: se evalúa CADA fecha calendario
  del rango que caiga en esos días, y cada una que tenga cobertura es una
  alternativa aparte (no hace falta que todas la tengan).

Colores de coincidencia (igual jerarquía que Lista de espera, pero sin
rojo — la combinación nunca cruza edificios, así que ese caso no existe):
  verde    — un solo consultorio cubre todo el bloque.
  amarillo — hace falta combinar, todos los consultorios de la misma unidad.
  naranja  — hace falta combinar, consultorios de distintas unidades del
             mismo edificio.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.negocio.dias import fecha_a_dia_semana, fecha_actual, parsear_periodo, periodo_actual, primer_dia_mes, sumar_meses
from app.negocio.grilla import calcular_ocupacion_regular

TIPO_REGULAR = "Regular"
TIPO_AISLADA = "Aislada"

SALIDA_PDF = "PDF"
SALIDA_TEXTO = "Texto"

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


@dataclass
class Busqueda:
    fecha_desde: str
    fecha_hasta: str | None  # None solo válido en Regular (vigencia indefinida)
    dias: list[str]
    hora_desde: float
    hora_hasta: float
    combinar_consultorios: bool = True
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
class Alternativa:
    """Una alternativa encontrada. `fecha` es None en Regular (el día de
    la semana se cubre de forma recurrente); en Aislada es la fecha
    calendario puntual que tuvo cobertura."""
    dia_semana: str
    fecha: str | None
    color: str
    tramos: list[TramoCobertura]


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


def _cobertura_subrango(candidatos_por_id: dict, horas: list[int], ocupado_lookup, combinar: bool) -> list[TramoCobertura] | None:
    libres_por_hora = {}
    for h in horas:
        libres = [i for i in candidatos_por_id if not ocupado_lookup(i, h)]
        if not libres:
            return None
        libres_por_hora[h] = libres

    # un solo consultorio para todo el sub-rango
    for id_consultorio in candidatos_por_id:
        if all(id_consultorio in libres_por_hora[h] for h in horas):
            return [TramoCobertura(id_consultorio, horas[0], horas[-1] + 1)]

    if not combinar:
        return None

    # combinación dentro del edificio: barrido hora por hora
    tramos = []
    actual_id = None
    inicio_tramo = horas[0]
    for h in horas:
        elegido = _elegir_consultorio(libres_por_hora[h], candidatos_por_id, actual_id)
        if actual_id is not None and elegido != actual_id:
            tramos.append(TramoCobertura(actual_id, inicio_tramo, h))
            inicio_tramo = h
        actual_id = elegido
    tramos.append(TramoCobertura(actual_id, inicio_tramo, horas[-1] + 1))
    return tramos


def _cobertura_con_duracion(
    candidatos_por_id: dict, hora_desde: float, hora_hasta: float, duracion: float | None, ocupado_lookup, combinar: bool,
) -> list[TramoCobertura] | None:
    hd, hh = int(hora_desde), int(hora_hasta)
    dur = int(duracion) if duracion else hh - hd
    if dur <= 0 or dur > hh - hd:
        return None
    for inicio in range(hd, hh - dur + 1):
        cobertura = _cobertura_subrango(candidatos_por_id, list(range(inicio, inicio + dur)), ocupado_lookup, combinar)
        if cobertura is not None:
            return cobertura
    return None


def _clasificar_color(candidatos_por_id: dict, ids_consultorio: set[int]) -> str:
    if len(ids_consultorio) == 1:
        return VERDE
    unidades = {candidatos_por_id[i]["IdUnidad"] for i in ids_consultorio}
    return AMARILLO if len(unidades) == 1 else NARANJA


def _mejor_cobertura(
    candidatos_por_edificio: dict[int, dict[int, sqlite3.Row]], busqueda: Busqueda, ocupado_lookup,
) -> tuple[int, list[TramoCobertura]] | None:
    """Cada edificio del alcance es un canal independiente — la
    combinación de consultorios nunca cruza edificios. Devuelve la
    primera cobertura encontrada junto con el edificio al que
    pertenece."""
    for id_edificio, candidatos_por_id in candidatos_por_edificio.items():
        cobertura = _cobertura_con_duracion(
            candidatos_por_id, busqueda.hora_desde, busqueda.hora_hasta, busqueda.cantidad_horas_minimas,
            ocupado_lookup, busqueda.combinar_consultorios,
        )
        if cobertura is not None:
            return id_edificio, cobertura
    return None


def _ocupado_regular(conn: sqlite3.Connection, anio: int, mes: int, dia_semana: str):
    mapa = calcular_ocupacion_regular(conn, anio, mes, dias=[dia_semana])
    return lambda id_consultorio, hora: mapa.get((id_consultorio, dia_semana, hora), False)


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
        cobertura_por_dia: dict[str, tuple[int, list[TramoCobertura]]] = {}
        for dia in busqueda.dias:
            resultado = _mejor_cobertura(candidatos_por_edificio, busqueda, _ocupado_regular(conn, anio, mes, dia))
            if resultado is not None:
                cobertura_por_dia[dia] = resultado
        if len(cobertura_por_dia) != len(busqueda.dias):
            return ResultadoBusqueda()  # Regular: todos los días pedidos tienen que coincidir
        for dia in busqueda.dias:
            id_edificio, tramos = cobertura_por_dia[dia]
            color = _clasificar_color(candidatos_por_edificio[id_edificio], {t.id_consultorio for t in tramos})
            alternativas.append(Alternativa(dia_semana=dia, fecha=None, color=color, tramos=tramos))
    else:
        fecha = date.fromisoformat(busqueda.fecha_desde)
        fecha_fin = date.fromisoformat(busqueda.fecha_hasta) if busqueda.fecha_hasta else fecha
        while fecha <= fecha_fin:
            dia_semana = fecha_a_dia_semana(fecha)
            if dia_semana in busqueda.dias:
                resultado = _mejor_cobertura(candidatos_por_edificio, busqueda, _ocupado_fecha(conn, fecha))
                if resultado is not None:
                    id_edificio, tramos = resultado
                    color = _clasificar_color(candidatos_por_edificio[id_edificio], {t.id_consultorio for t in tramos})
                    alternativas.append(Alternativa(dia_semana=dia_semana, fecha=fecha.isoformat(), color=color, tramos=tramos))
            fecha += timedelta(days=1)

    return ResultadoBusqueda(alternativas=alternativas)
