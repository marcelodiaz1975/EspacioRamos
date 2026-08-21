"""Lista de espera (sección 3.21) — cruce automático de pedidos contra
disponibilidad real (DC-08 §2, DC-10 §2).

Un pedido puede pedir varios bloques día(s)+horario a la vez — ejemplo
real: "martes o jueves 3hs entre 14 y 18hs" Y "sábado de 9 a 12hs" tienen
que darse los dos; con Y/O invertido en vez de Y alcanzaría con que se dé
uno de los dos. Cada bloque (ListaEsperaBloque) es exactamente lo que
antes era todo el pedido: una lista de días con su propia combinación
Y/O interna (`TipoCombinacionDias`) y un horario (+ opcionalmente
`CantidadHorasRequeridas`). El pedido (ListaEspera) agrega arriba de eso
un `TipoCombinacion` que ahora es la combinación ENTRE bloques, no entre
días — un pedido de un solo bloque (el caso más común) se comporta
exactamente igual que antes.

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
from datetime import date

from app.negocio.dias import fecha_actual, fecha_a_dia_semana
from app.negocio.formato import fecha_corta, hora_fmt
from app.negocio.grilla import aisladas_confirmadas_fecha, calcular_ocupacion_fecha, calcular_ocupacion_regular
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
    # Solo Variante B (fechas puntuales): avisos de reservas aisladas que
    # coinciden con alguna alternativa ofrecida, para que el operador
    # evalúe reubicarlas — NUNCA bloquean la alternativa (ver
    # `calcular_ocupacion_fecha`).
    alertas_aisladas: list[str] = field(default_factory=list)


def _validar_bloque(bloque: dict) -> None:
    tipo_dias = bloque.get("tipo_combinacion_dias", "O")
    if tipo_dias not in TIPOS_COMBINACION:
        raise ValueError(f"tipo_combinacion_dias inválido: {tipo_dias!r} (debe ser 'O' o 'Y')")
    if not bloque.get("dias"):
        raise ValueError("Cada bloque necesita al menos un día")
    horario_desde, horario_hasta = bloque["horario_desde"], bloque["horario_hasta"]
    if horario_hasta <= horario_desde:
        raise ValueError("HorarioHasta debe ser posterior a HorarioDesde")
    cantidad_horas = bloque.get("cantidad_horas_requeridas")
    if cantidad_horas is not None and not (0 < cantidad_horas <= horario_hasta - horario_desde):
        raise ValueError("CantidadHorasRequeridas debe ser mayor a 0 y no superar el rango HorarioDesde-HorarioHasta")


def crear_pedido(
    conn: sqlite3.Connection, *, id_profesional: int, bloques: list[dict], tipo_combinacion_bloques: str = "O",
    condiciones_consultorio: dict | None = None, detalle: str | None = None, fecha_pedido: str | None = None,
) -> int:
    """Cada bloque es un dict con `dias` (lista), `horario_desde`,
    `horario_hasta`, y opcionalmente `tipo_combinacion_dias` ('O' por
    defecto) y `cantidad_horas_requeridas`. `tipo_combinacion_bloques`
    combina los bloques ENTRE sí (irrelevante con un solo bloque, que es
    el caso más común)."""
    if tipo_combinacion_bloques not in TIPOS_COMBINACION:
        raise ValueError(f"tipo_combinacion_bloques inválido: {tipo_combinacion_bloques!r} (debe ser 'O' o 'Y')")
    if not bloques:
        raise ValueError("El pedido necesita al menos un bloque de día(s) + horario")
    for bloque in bloques:
        _validar_bloque(bloque)

    repo_pedido = obtener_repositorio(conn, "ListaEspera")
    id_pedido = repo_pedido.crear(
        IdProfesional=id_profesional, FechaPedido=fecha_pedido or fecha_actual(conn).isoformat(),
        TipoCombinacion=tipo_combinacion_bloques,
        CondicionesConsultorio=json.dumps(condiciones_consultorio or {}), Detalle=detalle, Estado="Activo",
    )
    repo_bloque = obtener_repositorio(conn, "ListaEsperaBloque")
    for bloque in bloques:
        repo_bloque.crear(
            IdPedido=id_pedido, TipoCombinacionDias=bloque.get("tipo_combinacion_dias", "O"),
            Dias=json.dumps(bloque["dias"]), HorarioDesde=bloque["horario_desde"],
            HorarioHasta=bloque["horario_hasta"], CantidadHorasRequeridas=bloque.get("cantidad_horas_requeridas"),
        )
    return id_pedido


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


def eliminar_pedido(conn: sqlite3.Connection, id_pedido: int) -> None:
    """Borra el pedido y sus bloques (ListaEsperaBloque) — hace falta
    borrar los bloques antes por la referencia (FK), no hay ON DELETE
    CASCADE en el schema. Lo usa la limpieza de avance de mes (DC-08
    §2.6)."""
    repo_bloque = obtener_repositorio(conn, "ListaEsperaBloque")
    for bloque in repo_bloque.listar(IdPedido=id_pedido):
        repo_bloque.eliminar(bloque["IdBloque"])
    obtener_repositorio(conn, "ListaEspera").eliminar(id_pedido)


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


def _bloques_de(conn: sqlite3.Connection, pedido) -> list:
    """`pedido` puede ser una fila real de ListaEspera (los bloques se
    buscan en ListaEsperaBloque) o un dict armado al vuelo
    (mensajes.mensaje_disponibilidad_horarios, que no persiste el pedido y
    trae la lista de bloques directo en la clave "Bloques")."""
    if "Bloques" in pedido.keys():
        return pedido["Bloques"]
    return obtener_repositorio(conn, "ListaEsperaBloque").listar(IdPedido=pedido["IdPedido"])


def _coincidencia_bloque(
    conn: sqlite3.Connection, candidatos_por_id: dict, bloque, anio: int, mes: int,
) -> tuple[list[str], dict[str, list[TramoCobertura]]] | None:
    dias = json.loads(bloque["Dias"] or "[]")
    if not dias:
        return None
    ocupado = calcular_ocupacion_regular(conn, anio, mes, dias=dias)
    duracion_requerida = bloque["CantidadHorasRequeridas"] if "CantidadHorasRequeridas" in bloque.keys() else None

    cobertura_por_dia: dict[str, list[TramoCobertura]] = {}
    for dia in dias:
        tramos = _cobertura_dia(
            candidatos_por_id, dia, bloque["HorarioDesde"], bloque["HorarioHasta"], ocupado,
            duracion_requerida=duracion_requerida,
        )
        if tramos is not None:
            cobertura_por_dia[dia] = tramos

    if bloque["TipoCombinacionDias"] == "Y":
        if len(cobertura_por_dia) != len(dias):
            return None
        dias_cubiertos = list(dias)
    else:
        if not cobertura_por_dia:
            return None
        dias_cubiertos = [d for d in dias if d in cobertura_por_dia]

    return dias_cubiertos, {d: cobertura_por_dia[d] for d in dias_cubiertos}


def calcular_coincidencia(conn: sqlite3.Connection, pedido, anio: int, mes: int) -> Coincidencia | None:
    """Cruza un pedido (posiblemente de varios bloques día(s)+horario)
    contra la disponibilidad de (anio, mes). None si no hay ninguna
    coincidencia ("sin color")."""
    condiciones = json.loads(pedido["CondicionesConsultorio"] or "{}")
    candidatos = _consultorios_candidatos(conn, condiciones)
    bloques = _bloques_de(conn, pedido)
    if not candidatos or not bloques:
        return None
    candidatos_por_id = {c["IdConsultorio"]: c for c in candidatos}

    resultados = [_coincidencia_bloque(conn, candidatos_por_id, bloque, anio, mes) for bloque in bloques]

    if pedido["TipoCombinacion"] == "Y":
        if any(r is None for r in resultados):
            return None
        cubiertos = resultados
    else:
        cubiertos = [r for r in resultados if r is not None]
        if not cubiertos:
            return None

    dias_cubiertos: list[str] = []
    tramos_por_dia: dict[str, list[TramoCobertura]] = {}
    for dias_bloque, tramos_bloque in cubiertos:
        for d in dias_bloque:
            if d not in dias_cubiertos:
                dias_cubiertos.append(d)
        tramos_por_dia.update(tramos_bloque)

    ids_consultorios = {t.id_consultorio for tramos in tramos_por_dia.values() for t in tramos}
    color = _clasificar_color(candidatos_por_id, ids_consultorios)
    if condiciones.get("sinCombinar") and color != VERDE:
        return None
    return Coincidencia(color=color, dias_cubiertos=dias_cubiertos, tramos_por_dia=tramos_por_dia)


def _alertas_aisladas(conn: sqlite3.Connection, fecha: str, tramos: list[TramoCobertura]) -> list[str]:
    """Reservas aisladas que se superponen con alguna alternativa ofrecida
    para `fecha` — para avisarle al operador, nunca para bloquear (ver
    `calcular_ocupacion_fecha`)."""
    aisladas = aisladas_confirmadas_fecha(conn, fecha)
    if not aisladas:
        return []
    etiqueta_fecha = f"{fecha_a_dia_semana(date.fromisoformat(fecha)).lower()} {fecha_corta(fecha)}"
    alertas = []
    for t in tramos:
        for a in aisladas:
            if a["IdConsultorio"] != t.id_consultorio:
                continue
            if not (t.hora_inicio < a["HoraFin"] and a["HoraInicio"] < t.hora_fin):
                continue
            profesional = conn.execute(
                "SELECT Apellido FROM Profesional WHERE IdProfesional = ?", (a["IdProfesional"],)
            ).fetchone()
            nombre = profesional["Apellido"] if profesional else "?"
            alertas.append(
                f"{etiqueta_fecha} de {hora_fmt(a['HoraInicio'])[:-2]} a {hora_fmt(a['HoraFin'])}: ya hay una "
                f"reserva aislada asignada de {nombre} en ese consultorio — revisá si conviene reubicarla."
            )
    return alertas


def _coincidencia_bloque_fechas(
    conn: sqlite3.Connection, candidatos_por_id: dict, bloque: dict,
) -> tuple[list[str], dict[str, list[TramoCobertura]], list[str]] | None:
    """Igual que `_coincidencia_bloque`, pero contra fechas puntuales
    (DC-03 Mensaje 2 Variante B) en vez de días de la semana genéricos
    promediados en un mes — cada fecha usa su ocupación real ese día
    concreto (`calcular_ocupacion_fecha`: respeta ausencias puntuales).
    Una reserva aislada que coincide con la alternativa NO la descarta,
    solo suma un aviso en el tercer elemento de la tupla (ver
    `_alertas_aisladas`)."""
    fechas = bloque.get("fechas") or []
    if not fechas:
        return None
    duracion_requerida = bloque.get("cantidad_horas_requeridas")

    cobertura_por_fecha: dict[str, list[TramoCobertura]] = {}
    for fecha in fechas:
        ocupado_fecha = calcular_ocupacion_fecha(conn, fecha)
        ocupado = {(idc, fecha, h): v for (idc, h), v in ocupado_fecha.items()}
        tramos = _cobertura_dia(
            candidatos_por_id, fecha, bloque["horario_desde"], bloque["horario_hasta"], ocupado,
            duracion_requerida=duracion_requerida,
        )
        if tramos is not None:
            cobertura_por_fecha[fecha] = tramos

    if bloque.get("tipo_combinacion_dias", "O") == "Y":
        if len(cobertura_por_fecha) != len(fechas):
            return None
        fechas_cubiertas = list(fechas)
    else:
        if not cobertura_por_fecha:
            return None
        fechas_cubiertas = [f for f in fechas if f in cobertura_por_fecha]

    alertas: list[str] = []
    for f in fechas_cubiertas:
        alertas.extend(_alertas_aisladas(conn, f, cobertura_por_fecha[f]))

    return fechas_cubiertas, {f: cobertura_por_fecha[f] for f in fechas_cubiertas}, alertas


def calcular_coincidencia_fechas(
    conn: sqlite3.Connection, *, bloques: list[dict], tipo_combinacion_bloques: str = "O",
    condiciones_consultorio: dict | None = None,
) -> Coincidencia | None:
    """Variante B de `calcular_coincidencia` (DC-03 Mensaje 2): cruza
    fechas puntuales en vez de días de la semana genéricos + (anio, mes).
    No persiste nada — igual que `mensaje_disponibilidad_horarios`, es
    solo para armar el mensaje. Cada bloque es un dict con `fechas`
    (lista de 'AAAA-MM-DD'), `horario_desde`, `horario_hasta`, y
    opcionalmente `tipo_combinacion_dias` ('O' por defecto) y
    `cantidad_horas_requeridas`."""
    condiciones = condiciones_consultorio or {}
    candidatos = _consultorios_candidatos(conn, condiciones)
    if not candidatos or not bloques:
        return None
    candidatos_por_id = {c["IdConsultorio"]: c for c in candidatos}

    resultados = [_coincidencia_bloque_fechas(conn, candidatos_por_id, bloque) for bloque in bloques]

    if tipo_combinacion_bloques == "Y":
        if any(r is None for r in resultados):
            return None
        cubiertos = resultados
    else:
        cubiertos = [r for r in resultados if r is not None]
        if not cubiertos:
            return None

    fechas_cubiertas: list[str] = []
    tramos_por_fecha: dict[str, list[TramoCobertura]] = {}
    alertas_aisladas: list[str] = []
    for fechas_bloque, tramos_bloque, alertas_bloque in cubiertos:
        for f in fechas_bloque:
            if f not in fechas_cubiertas:
                fechas_cubiertas.append(f)
        tramos_por_fecha.update(tramos_bloque)
        for alerta in alertas_bloque:
            if alerta not in alertas_aisladas:
                alertas_aisladas.append(alerta)

    ids_consultorios = {t.id_consultorio for tramos in tramos_por_fecha.values() for t in tramos}
    color = _clasificar_color(candidatos_por_id, ids_consultorios)
    if condiciones.get("sinCombinar") and color != VERDE:
        return None
    return Coincidencia(
        color=color, dias_cubiertos=fechas_cubiertas, tramos_por_dia=tramos_por_fecha,
        alertas_aisladas=alertas_aisladas,
    )


def listar_pedidos_con_coincidencia(
    conn: sqlite3.Connection, anio: int, mes: int,
) -> list[tuple[sqlite3.Row, Coincidencia | None]]:
    """DC-08 §2.1: todos los pedidos Activos con su coincidencia calculada,
    para pintar la pantalla F12 de un saque."""
    pedidos = obtener_repositorio(conn, "ListaEspera").listar(Estado="Activo")
    return [(p, calcular_coincidencia(conn, p, anio, mes)) for p in pedidos]
