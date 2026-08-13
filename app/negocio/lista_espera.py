"""Lista de espera (sección 3.21) — cruce automático de pedidos contra
disponibilidad real (DC-08 §2, DC-10 §2).

El cruce evalúa, para cada día pedido y el horario completo solicitado,
qué consultorios están libres TODAS las horas de ese rango (reutilizando
la ocupación de `grilla.py`) y que además cumplen las condiciones
opcionales pedidas (ventana, camilla, tamaño, balcón, aire). Con eso arma
la jerarquía de color:

    Verde    — un solo consultorio cubre todo el horario pedido.
    Amarillo — hace falta combinar más de un consultorio, todos de la
               misma unidad.
    Naranja  — hace falta combinar consultorios de más de una unidad,
               todas del mismo edificio.
    Rojo     — hace falta combinar consultorios de más de un edificio.
    Sin color (None) — no hay forma de cubrir todo el horario pedido.

Tipo de combinación de días (TipoCombinacion):
    O — alcanza con que UN día de los pedidos tenga cobertura.
    Y — TODOS los días pedidos tienen que tener cobertura simultánea.

`CantidadHorasRequeridas` (opcional): en vez de exigir que TODO el rango
HorarioDesde-HorarioHasta esté libre, alcanza con encontrar un sub-rango
contiguo de esa duración en algún punto del rango pedido — "necesito 3hs
dentro del bloque de 9 a 13hs, sin importar cuáles exactamente". Se prueba
arrancar en cada hora posible del rango, de la más temprana a la más
tardía, y se toma la primera que se puede cubrir entera (con un solo
consultorio si se puede, si no combinando). Sin este campo (None), el
comportamiento es el de siempre: el sub-rango buscado es el rango
completo.

Cuando hace falta combinar consultorios se arma con un barrido simple hora
por hora: se mantiene el consultorio elegido mientras siga libre, y al
liberarse se elige uno nuevo priorizando quedarse en la misma unidad, luego
el mismo edificio, y si no cualquiera disponible. No es una búsqueda
exhaustiva de la combinación óptima (podría existir una combinación con
menos consultorios en algún caso raro), pero cubre bien los casos reales:
pocas horas por bloque y pocos consultorios candidatos.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from app.negocio.dias import fecha_actual
from app.negocio.grilla import calcular_ocupacion_regular
from app.repositorio.registro import obtener_repositorio

VERDE = "verde"
AMARILLO = "amarillo"
NARANJA = "naranja"
ROJO = "rojo"

TIPOS_COMBINACION = ("O", "Y")


@dataclass
class TramoCobertura:
    hora_inicio: float
    hora_fin: float
    id_consultorio: int


@dataclass
class Coincidencia:
    color: str
    dias_cubiertos: list[str]
    tramos_por_dia: dict[str, list[TramoCobertura]] = field(default_factory=dict)


def crear_pedido(
    conn: sqlite3.Connection, *, id_profesional: int, tipo_combinacion: str, dias: list[str],
    horario_desde: float, horario_hasta: float, cantidad_horas_requeridas: float | None = None,
    condiciones_consultorio: dict | None = None, detalle: str | None = None, fecha_pedido: str | None = None,
) -> int:
    if tipo_combinacion not in TIPOS_COMBINACION:
        raise ValueError(f"tipo_combinacion inválido: {tipo_combinacion!r} (debe ser 'O' o 'Y')")
    if horario_hasta <= horario_desde:
        raise ValueError("HorarioHasta debe ser posterior a HorarioDesde")
    if not dias:
        raise ValueError("El pedido necesita al menos un día")
    if cantidad_horas_requeridas is not None and not (0 < cantidad_horas_requeridas <= horario_hasta - horario_desde):
        raise ValueError("CantidadHorasRequeridas debe ser mayor a 0 y no superar el rango HorarioDesde-HorarioHasta")

    repo = obtener_repositorio(conn, "ListaEspera")
    return repo.crear(
        IdProfesional=id_profesional, FechaPedido=fecha_pedido or fecha_actual(conn).isoformat(),
        TipoCombinacion=tipo_combinacion, Dias=json.dumps(dias),
        HorarioDesde=horario_desde, HorarioHasta=horario_hasta, CantidadHorasRequeridas=cantidad_horas_requeridas,
        CondicionesConsultorio=json.dumps(condiciones_consultorio or {}), Detalle=detalle, Estado="Activo",
    )


def _cambiar_estado(conn: sqlite3.Connection, id_pedido: int, estado: str, observacion: str | None) -> None:
    repo = obtener_repositorio(conn, "ListaEspera")
    pedido = repo.obtener(id_pedido)
    if pedido is None:
        raise ValueError(f"No existe el pedido #{id_pedido}")
    if pedido["Estado"] != "Activo":
        raise ValueError(f"El pedido #{id_pedido} ya está {pedido['Estado']}, no está Activo")
    repo.actualizar(id_pedido, Estado=estado, ObservacionCierre=observacion)


def marcar_resuelto(conn: sqlite3.Connection, id_pedido: int, observacion: str | None = None) -> None:
    """DC-10 §2.2 paso 5: al confirmar la reserva en F16, el pedido pasa a
    Resuelto."""
    _cambiar_estado(conn, id_pedido, "Resuelto", observacion)


def marcar_descartado(conn: sqlite3.Connection, id_pedido: int, observacion: str | None = None) -> None:
    """DC-10 §2.2 paso 4b: el operador decide no proceder con el pedido."""
    _cambiar_estado(conn, id_pedido, "Descartado", observacion)


def _consultorios_candidatos(conn: sqlite3.Connection, condiciones: dict) -> list[sqlite3.Row]:
    """Consultorios que cumplen las condiciones opcionales pedidas. Si no
    se pidió ninguna condición, cualquier consultorio cuenta."""
    filas = conn.execute(
        "SELECT c.*, u.IdEdificio AS IdEdificioReal FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad"
    ).fetchall()
    resultado = []
    for c in filas:
        if condiciones.get("ventana") and not c["Ventana"]:
            continue
        if condiciones.get("aptoCamilla") and not c["AptoCamilla"]:
            continue
        if condiciones.get("balcon") and not c["Balcon"]:
            continue
        if condiciones.get("aire") and not c["AireAcondicionado"]:
            continue
        tamano = condiciones.get("tamano")
        if tamano and (c["TamanoClasificacion"] or "").strip().lower() != str(tamano).strip().lower():
            continue
        resultado.append(c)
    return resultado


def _elegir_consultorio(libres_ids: list[int], candidatos_por_id: dict, actual_id: int | None) -> int:
    if actual_id in libres_ids:
        return actual_id
    actual = candidatos_por_id.get(actual_id) if actual_id is not None else None
    if actual is not None:
        misma_unidad = [i for i in libres_ids if candidatos_por_id[i]["IdUnidad"] == actual["IdUnidad"]]
        if misma_unidad:
            return misma_unidad[0]
        mismo_edificio = [i for i in libres_ids if candidatos_por_id[i]["IdEdificioReal"] == actual["IdEdificioReal"]]
        if mismo_edificio:
            return mismo_edificio[0]
    return libres_ids[0]


def _cobertura_subrango(candidatos_por_id: dict, dia: str, horas: list[int], ocupado: dict) -> list[TramoCobertura] | None:
    """Cobertura de un sub-rango YA elegido (una hora de inicio concreta):
    None si alguna hora puntual no tiene ningún consultorio libre, si no un
    solo tramo (un consultorio cubre todo) o varios (combinación, barrido
    hora por hora)."""
    libres_por_hora = {}
    for h in horas:
        libres = [i for i, c in candidatos_por_id.items() if not ocupado.get((i, dia, h))]
        if not libres:
            return None
        libres_por_hora[h] = libres

    # un solo consultorio para todo el sub-rango
    for id_consultorio in candidatos_por_id:
        if all(id_consultorio in libres_por_hora[h] for h in horas):
            return [TramoCobertura(hora_inicio=horas[0], hora_fin=horas[-1] + 1, id_consultorio=id_consultorio)]

    # combinación: barrido hora por hora
    tramos = []
    actual_id = None
    inicio_tramo = horas[0]
    for h in horas:
        elegido = _elegir_consultorio(libres_por_hora[h], candidatos_por_id, actual_id)
        if actual_id is not None and elegido != actual_id:
            tramos.append(TramoCobertura(hora_inicio=inicio_tramo, hora_fin=h, id_consultorio=actual_id))
            inicio_tramo = h
        actual_id = elegido
    tramos.append(TramoCobertura(hora_inicio=inicio_tramo, hora_fin=horas[-1] + 1, id_consultorio=actual_id))
    return tramos


def _cobertura_dia(
    candidatos_por_id: dict, dia: str, hora_desde: float, hora_hasta: float, ocupado: dict,
    duracion_requerida: float | None = None,
) -> list[TramoCobertura] | None:
    """Sin `duracion_requerida` (o igual al rango completo): comportamiento
    de siempre, todo el rango hora_desde-hora_hasta tiene que estar libre.
    Con `duracion_requerida` menor al rango: alcanza con encontrar ESE
    tanto de horas contiguas en algún punto del rango — se prueba cada
    hora de inicio posible, de la más temprana a la más tardía, y se toma
    la primera que se puede cubrir entera."""
    hora_desde_i, hora_hasta_i = int(hora_desde), int(hora_hasta)
    duracion = int(duracion_requerida) if duracion_requerida else hora_hasta_i - hora_desde_i
    if duracion <= 0 or duracion > hora_hasta_i - hora_desde_i:
        return None

    for inicio in range(hora_desde_i, hora_hasta_i - duracion + 1):
        cobertura = _cobertura_subrango(candidatos_por_id, dia, list(range(inicio, inicio + duracion)), ocupado)
        if cobertura is not None:
            return cobertura
    return None


def _clasificar_color(candidatos_por_id: dict, ids_consultorios: set[int]) -> str:
    if len(ids_consultorios) == 1:
        return VERDE
    unidades = {candidatos_por_id[i]["IdUnidad"] for i in ids_consultorios}
    if len(unidades) == 1:
        return AMARILLO
    edificios = {candidatos_por_id[i]["IdEdificioReal"] for i in ids_consultorios}
    if len(edificios) == 1:
        return NARANJA
    return ROJO


def calcular_coincidencia(conn: sqlite3.Connection, pedido: sqlite3.Row, anio: int, mes: int) -> Coincidencia | None:
    """Cruza un pedido contra la disponibilidad de (anio, mes). None si no
    hay ninguna coincidencia ("sin color")."""
    dias = json.loads(pedido["Dias"] or "[]")
    condiciones = json.loads(pedido["CondicionesConsultorio"] or "{}")
    candidatos = _consultorios_candidatos(conn, condiciones)
    if not candidatos or not dias:
        return None
    candidatos_por_id = {c["IdConsultorio"]: c for c in candidatos}
    ocupado = calcular_ocupacion_regular(conn, anio, mes, dias=dias)

    # `pedido` puede ser una fila real de ListaEspera o un dict armado al
    # vuelo (mensajes.mensaje_disponibilidad_horarios, que no persiste el
    # pedido) — a diferencia de un dict, sqlite3.Row no tiene `.get()`, así
    # que el chequeo de la clave tiene que andar para los dos.
    duracion_requerida = pedido["CantidadHorasRequeridas"] if "CantidadHorasRequeridas" in pedido.keys() else None
    cobertura_por_dia: dict[str, list[TramoCobertura]] = {}
    for dia in dias:
        tramos = _cobertura_dia(
            candidatos_por_id, dia, pedido["HorarioDesde"], pedido["HorarioHasta"], ocupado,
            duracion_requerida=duracion_requerida,
        )
        if tramos is not None:
            cobertura_por_dia[dia] = tramos

    if pedido["TipoCombinacion"] == "Y":
        if len(cobertura_por_dia) != len(dias):
            return None
        dias_cubiertos = list(dias)
    else:
        if not cobertura_por_dia:
            return None
        dias_cubiertos = [d for d in dias if d in cobertura_por_dia]

    ids_consultorios = {t.id_consultorio for d in dias_cubiertos for t in cobertura_por_dia[d]}
    color = _clasificar_color(candidatos_por_id, ids_consultorios)
    if condiciones.get("sinCombinar") and color != VERDE:
        return None
    return Coincidencia(
        color=color, dias_cubiertos=dias_cubiertos,
        tramos_por_dia={d: cobertura_por_dia[d] for d in dias_cubiertos},
    )


def listar_pedidos_con_coincidencia(
    conn: sqlite3.Connection, anio: int, mes: int,
) -> list[tuple[sqlite3.Row, Coincidencia | None]]:
    """DC-08 §2.1: todos los pedidos Activos con su coincidencia calculada,
    para pintar la pantalla F12 de un saque."""
    pedidos = obtener_repositorio(conn, "ListaEspera").listar(Estado="Activo")
    return [(p, calcular_coincidencia(conn, p, anio, mes)) for p in pedidos]
