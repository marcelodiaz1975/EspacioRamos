"""Motor de cálculo de la "Grilla Operativa" (miscelánea, ago-2026,
segunda versión — reemplaza por completo el primer diseño basado en un
horizonte fijo de 2 meses).

Grilla semanal (consultorio x día de la semana x hora), evaluada contra
un RANGO DE FECHAS explícito que elige quien consulta (por defecto el
mes del período activo completo, pero se puede acotar). Se usa como
widget compartido en Reservas aisladas, Reservas regulares, Vacaciones,
Licencias, Ausencias y en una pantalla propia "Grilla operativa".

Dos modos de visualización con reglas de color propias:

MODO "regular" — pensado para responder "¿quién tiene este horario?":
  - Blanco completo: caso base — sin reserva regular relevante en el
    rango (sin código), o con una reserva regular activa que no dispara
    ninguna de las reglas siguientes (con código).
  - Verde completo: hay una reserva regular activa HOY que no se libera
    dentro del rango (VigenciaFin nulo o posterior al fin del rango).
  - Rojo completo: hay una reserva regular que todavía no arrancó hoy
    (arranque dentro o después del rango, da lo mismo) para un
    profesional distinto al que ocupa el horario ahora (o para
    cualquier profesional, si ahora no lo ocupa nadie).
  - Rojo con centro amarillo: igual que el anterior + ya hay una o más
    reservas aisladas asignadas dentro del rango.
  - Blanco con centro verde: reservado en forma regular dentro del
    rango, pero el profesional que lo tiene libera algún día suelto
    dentro de ese rango por vacaciones/licencia/ausencia (todavía sin
    tomar por una aislada).
  - Blanco con centro amarillo: igual que el anterior, pero ese hueco
    ya tiene una reserva aislada confirmada adentro.
  - Amarillo completo: libre de reserva regular en todo el rango, pero
    ya hay una aislada asignada en algún día del rango.

MODO "aislada" — pensado para responder "¿puedo poner una hora aislada
acá?": no le importan las reservas regulares que todavía no arrancaron
(un profesional "entrante" no bloquea nada hasta que efectivamente
empieza), solo lo que está activo HOY.
  - Rojo completo: bloqueado en todo el rango por una reserva regular
    activa sin ningún hueco.
  - Verde completo: libre de reserva regular en todo el rango.
  - Rojo con centro verde: reservado en forma regular dentro del rango,
    pero libera algún hueco dentro de ese rango por vacaciones/licencia
    /ausencia (todavía sin tomar).
  - Rojo con centro amarillo: igual que el anterior, pero el hueco ya
    tiene una aislada confirmada adentro.
  - Amarillo completo: libre de reserva regular en todo el rango + ya
    hay una aislada asignada dentro del rango.

Regla común a los dos modos: si el profesional del filtro de la grilla
es el que se está mostrando (el código que aparece en la celda), la
celda pasa a Azul oscuro con fuente blanca, pisando cualquier otro
color.

"Fecha de corte" (aclarado en conversación): todo se evalúa tomando HOY
como referencia — una vacación/licencia/ausencia que ya terminó ayer no
cuenta, una que termina hoy sí. Una reserva regular que todavía no
arrancó hoy nunca cuenta como "la reserva actual", sin importar si su
inicio cae dentro o después del rango seleccionado (en ambos casos se
trata igual: dispara la regla de "rojo").
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.negocio.dias import DIAS_SEMANA, fecha_a_dia_semana, fecha_actual

AZUL_OSCURO = "azul_oscuro"
BLANCO = "blanco"
VERDE = "verde"
AMARILLO = "amarillo"
ROJO = "rojo"
NEGRA = "negra"
BLANCA = "blanca"

ModoGrillaOperativa = Literal["regular", "aislada"]


@dataclass
class CeldaGrillaOperativa:
    color_aro: str
    color_centro: str
    color_fuente: str
    codigo: str | None
    detalle: str
    id_profesional_mostrado: int | None


def _nombre_con_codigo(profesional: sqlite3.Row) -> str:
    partes = [p for p in (profesional["Tratamiento"], profesional["NombrePila"], profesional["Apellido"]) if p]
    nombre = " ".join(partes) if partes else profesional["Apellido"]
    codigo = profesional["IdCodigo"]
    return f"{nombre} ({codigo})" if codigo else nombre


def _fecha_dia_texto(fecha_iso: str) -> str:
    f = date.fromisoformat(fecha_iso)
    return f"{fecha_a_dia_semana(f).lower()} {f.day}/{f.month}"


def _rango_intersecta_dia_semana(
    fecha_desde_reg: str, fecha_hasta_reg: str, dia_semana: str, hoy: date, fecha_desde_rango: date, fecha_hasta_rango: date,
) -> bool:
    """¿Algún día del registro (vacación/licencia/ausencia), recortado a
    lo que todavía no pasó (>= hoy) y al rango consultado, cae en ese
    día de la semana?"""
    desde = max(date.fromisoformat(fecha_desde_reg), hoy, fecha_desde_rango)
    hasta = min(date.fromisoformat(fecha_hasta_reg), fecha_hasta_rango)
    if desde > hasta:
        return False
    cursor = desde
    while cursor <= hasta:
        if fecha_a_dia_semana(cursor) == dia_semana:
            return True
        cursor += timedelta(days=1)
    return False


def _novedades_profesional(
    conn: sqlite3.Connection, id_profesional: int, dia_semana: str, id_consultorio: int,
    hoy: date, fecha_desde_rango: date, fecha_hasta_rango: date,
) -> list[tuple[str, str]]:
    """[(fecha_orden, texto)] de vacaciones, licencias y ausencias del
    profesional que caen en ese día de la semana dentro del rango."""
    clausulas: list[tuple[str, str]] = []

    for v in conn.execute("SELECT * FROM Vacacion WHERE IdProfesional = ?", (id_profesional,)).fetchall():
        if _rango_intersecta_dia_semana(v["FechaDesde"], v["FechaHasta"], dia_semana, hoy, fecha_desde_rango, fecha_hasta_rango):
            texto = f"De vacaciones desde el {_fecha_dia_texto(v['FechaDesde'])} hasta el {_fecha_dia_texto(v['FechaHasta'])}."
            clausulas.append((v["FechaDesde"], texto))

    for lic in conn.execute(
        "SELECT l.*, t.Nombre AS NombreTipo FROM Licencia l JOIN TipoLicencia t ON t.IdTipoLicencia = l.IdTipoLicencia "
        "WHERE l.IdProfesional = ?", (id_profesional,),
    ).fetchall():
        if _rango_intersecta_dia_semana(lic["FechaDesde"], lic["FechaHasta"], dia_semana, hoy, fecha_desde_rango, fecha_hasta_rango):
            texto = (
                f"De licencia por {lic['NombreTipo'].lower()} desde el {_fecha_dia_texto(lic['FechaDesde'])} "
                f"hasta el {_fecha_dia_texto(lic['FechaHasta'])}."
            )
            clausulas.append((lic["FechaDesde"], texto))

    for a in conn.execute("SELECT * FROM Ausencia WHERE IdProfesional = ?", (id_profesional,)).fetchall():
        if a["IdConsultorio"] is not None and a["IdConsultorio"] != id_consultorio:
            continue
        if not _rango_intersecta_dia_semana(a["FechaDesde"], a["FechaHasta"], dia_semana, hoy, fecha_desde_rango, fecha_hasta_rango):
            continue
        motivo = f" por {a['Motivo'].lower()}" if a["Motivo"] else ""
        if a["FechaDesde"] == a["FechaHasta"]:
            texto = f"Ausente{motivo} el {_fecha_dia_texto(a['FechaDesde'])}."
        else:
            texto = f"Ausente{motivo} desde el {_fecha_dia_texto(a['FechaDesde'])} hasta el {_fecha_dia_texto(a['FechaHasta'])}."
        clausulas.append((a["FechaDesde"], texto))

    return sorted(clausulas)


def _aisladas_en_rango(
    conn: sqlite3.Connection, id_consultorio: int, dia_semana: str, hora: float,
    hoy: date, fecha_desde_rango: date, fecha_hasta_rango: date,
    cache_profesionales: dict[int, sqlite3.Row],
) -> list[tuple[str, int, str]]:
    """[(Fecha, IdProfesional, texto)] de aisladas Confirmadas dentro del
    rango que caen en ese día de la semana, ordenadas por cercanía a hoy
    (incluye aisladas ya pasadas si el rango consultado las abarca)."""
    filas = conn.execute(
        "SELECT * FROM ReservaAislada WHERE IdConsultorio = ? AND Estado = 'Confirmada' "
        "AND Fecha BETWEEN ? AND ? AND HoraInicio <= ? AND HoraFin > ?",
        (id_consultorio, fecha_desde_rango.isoformat(), fecha_hasta_rango.isoformat(), hora, hora),
    ).fetchall()
    resultado = []
    for f in filas:
        fecha = date.fromisoformat(f["Fecha"])
        if fecha_a_dia_semana(fecha) != dia_semana:
            continue
        nombre = _nombre_con_codigo(cache_profesionales[f["IdProfesional"]])
        texto = f"Hora aislada reservada por {nombre} para el {_fecha_dia_texto(f['Fecha'])}."
        resultado.append((f["Fecha"], f["IdProfesional"], texto))
    resultado.sort(key=lambda t: abs((date.fromisoformat(t[0]) - hoy).days))
    return resultado


def claves_con_ausencia(
    conn: sqlite3.Connection, id_profesional: int, ids_consultorio: list[int], dias: list[str],
    hora_ini: int, hora_fin: int, fecha_desde: str, fecha_hasta: str,
) -> set[tuple[int, str, int]]:
    """{(IdConsultorio, dia, hora)} donde el profesional tiene una
    ausencia registrada dentro de [fecha_desde, fecha_hasta], recortado a
    lo que todavía no pasó (>= hoy) igual que el resto de la grilla.
    Respeta el horario puntual de la ausencia (HoraInicio/HoraFin) cuando
    está presente; si no, cubre todas las horas del rango consultado.
    Pensado para pasarse como `ausente_en` a `calcular_grilla_operativa`."""
    hoy = fecha_actual(conn)
    fecha_desde_rango = date.fromisoformat(fecha_desde)
    fecha_hasta_rango = date.fromisoformat(fecha_hasta)
    dias_validos = [d for d in DIAS_SEMANA if d in dias]

    claves: set[tuple[int, str, int]] = set()
    for a in conn.execute("SELECT * FROM Ausencia WHERE IdProfesional = ?", (id_profesional,)).fetchall():
        desde = max(date.fromisoformat(a["FechaDesde"]), hoy, fecha_desde_rango)
        hasta = min(date.fromisoformat(a["FechaHasta"]), fecha_hasta_rango)
        if desde > hasta:
            continue
        if a["HoraInicio"] is not None and a["HoraFin"] is not None:
            horas = [h for h in range(int(hora_ini), int(hora_fin)) if a["HoraInicio"] <= h < a["HoraFin"]]
        else:
            horas = list(range(int(hora_ini), int(hora_fin)))
        if not horas:
            continue
        consultorios = [a["IdConsultorio"]] if a["IdConsultorio"] is not None else ids_consultorio
        cursor = desde
        while cursor <= hasta:
            dia = fecha_a_dia_semana(cursor)
            if dia in dias_validos:
                for id_consultorio in consultorios:
                    for hora in horas:
                        claves.add((id_consultorio, dia, hora))
            cursor += timedelta(days=1)
    return claves


def calcular_grilla_operativa(
    conn: sqlite3.Connection, ids_consultorio: list[int], dias: list[str], hora_ini: int, hora_fin: int,
    fecha_desde: str, fecha_hasta: str, modo: ModoGrillaOperativa = "regular", id_profesional_filtro: int | None = None,
    ausente_en: set[tuple[int, str, int]] | None = None,
) -> dict[tuple[int, str, int], CeldaGrillaOperativa]:
    """Devuelve {(IdConsultorio, dia, hora): CeldaGrillaOperativa} para
    toda la grilla filtrada, evaluada contra [fecha_desde, fecha_hasta].

    `ausente_en`, si se pasa, es el conjunto de (IdConsultorio, dia, hora)
    donde el profesional del filtro tiene una ausencia registrada — usado
    por la pantalla de Ausencias para resaltar en verde con letra negra
    los horarios que de otro modo se mostrarían en azul oscuro (el
    horario propio del profesional filtrado)."""
    hoy = fecha_actual(conn)
    fecha_desde_rango = date.fromisoformat(fecha_desde)
    fecha_hasta_rango = date.fromisoformat(fecha_hasta)
    dias = [d for d in DIAS_SEMANA if d in dias]

    profesionales = {p["IdProfesional"]: p for p in conn.execute("SELECT * FROM Profesional").fetchall()}

    regulares_por_slot: dict[tuple[int, str], list[sqlite3.Row]] = {}
    if ids_consultorio:
        placeholders = ", ".join("?" for _ in ids_consultorio)
        filas = conn.execute(
            f"SELECT * FROM ReservaRegular WHERE IdConsultorio IN ({placeholders})", ids_consultorio,
        ).fetchall()
        for r in filas:
            regulares_por_slot.setdefault((r["IdConsultorio"], r["DiaSemana"]), []).append(r)

    resultado: dict[tuple[int, str, int], CeldaGrillaOperativa] = {}
    for id_consultorio in ids_consultorio:
        for dia in dias:
            candidatas = regulares_por_slot.get((id_consultorio, dia), [])
            for hora in range(int(hora_ini), int(hora_fin)):
                cubren = [r for r in candidatas if r["HoraInicio"] <= hora < r["HoraFin"]]
                actual, entrante = _clasificar_regulares(cubren, hoy)
                celda = _resolver_celda(
                    conn, id_consultorio, dia, hora, hoy, fecha_desde_rango, fecha_hasta_rango,
                    actual, entrante, profesionales, modo, id_profesional_filtro,
                )
                clave = (id_consultorio, dia, hora)
                if ausente_en and celda.color_aro == AZUL_OSCURO and clave in ausente_en:
                    celda = CeldaGrillaOperativa(
                        VERDE, VERDE, NEGRA, celda.codigo,
                        f"{celda.detalle} Ausente en este horario.".strip(), celda.id_profesional_mostrado,
                    )
                resultado[clave] = celda
    return resultado


def _clasificar_regulares(
    cubren: list[sqlite3.Row], hoy: date,
) -> tuple[sqlite3.Row | None, sqlite3.Row | None]:
    """(actual, entrante) — "actual" es la reserva activa hoy (si hay
    varias, la primera); "entrante" es la que todavía no arrancó hoy más
    próxima a arrancar."""
    actual = None
    entrante = None
    for r in cubren:
        vigencia_inicio = date.fromisoformat(r["VigenciaInicio"])
        vigencia_fin = date.fromisoformat(r["VigenciaFin"]) if r["VigenciaFin"] else None
        if vigencia_inicio <= hoy and (vigencia_fin is None or vigencia_fin >= hoy):
            if actual is None:
                actual = r
        elif vigencia_inicio > hoy:
            if entrante is None or vigencia_inicio < date.fromisoformat(entrante["VigenciaInicio"]):
                entrante = r
    return actual, entrante


def _resolver_celda(
    conn: sqlite3.Connection, id_consultorio: int, dia: str, hora: int, hoy: date,
    fecha_desde_rango: date, fecha_hasta_rango: date, actual: sqlite3.Row | None, entrante: sqlite3.Row | None,
    profesionales: dict[int, sqlite3.Row], modo: ModoGrillaOperativa, id_profesional_filtro: int | None,
) -> CeldaGrillaOperativa:
    aisladas = _aisladas_en_rango(conn, id_consultorio, dia, hora, hoy, fecha_desde_rango, fecha_hasta_rango, profesionales)
    hay_aisladas = bool(aisladas)

    novedades_actual: list[tuple[str, str]] = []
    if actual is not None:
        novedades_actual = _novedades_profesional(
            conn, actual["IdProfesional"], dia, id_consultorio, hoy, fecha_desde_rango, fecha_hasta_rango,
        )
    hay_novedad_actual = bool(novedades_actual)

    if modo == "regular":
        return _resolver_regular(
            actual, entrante, hay_aisladas, aisladas, hay_novedad_actual, novedades_actual,
            fecha_hasta_rango, profesionales, id_profesional_filtro,
        )
    return _resolver_aislada(
        actual, hay_aisladas, aisladas, hay_novedad_actual, novedades_actual, profesionales, id_profesional_filtro,
    )


def _resolver_regular(
    actual: sqlite3.Row | None, entrante: sqlite3.Row | None, hay_aisladas: bool, aisladas: list[tuple[str, int, str]],
    hay_novedad: bool, novedades: list[tuple[str, str]], fecha_hasta_rango: date,
    profesionales: dict[int, sqlite3.Row], id_profesional_filtro: int | None,
) -> CeldaGrillaOperativa:
    nombre_actual = _nombre_con_codigo(profesionales[actual["IdProfesional"]]) if actual else None
    codigo_actual = profesionales[actual["IdProfesional"]]["IdCodigo"] if actual else None
    base = f"Horario reservado por {nombre_actual}." if actual else None

    if actual is not None and id_profesional_filtro is not None and actual["IdProfesional"] == id_profesional_filtro:
        return CeldaGrillaOperativa(AZUL_OSCURO, AZUL_OSCURO, BLANCA, codigo_actual, base, actual["IdProfesional"])

    conflicto = entrante is not None and (actual is None or entrante["IdProfesional"] != actual["IdProfesional"])
    if conflicto:
        nombre_entrante = _nombre_con_codigo(profesionales[entrante["IdProfesional"]])
        clausula_entrante = f"Horario reservado por {nombre_entrante} a partir del {_fecha_dia_texto(entrante['VigenciaInicio'])}."
        texto = " ".join(([base] if base else []) + [clausula_entrante])
        if hay_aisladas:
            texto = " ".join([texto] + [t for _, _, t in aisladas])
            return CeldaGrillaOperativa(ROJO, AMARILLO, NEGRA, codigo_actual, texto, actual["IdProfesional"] if actual else None)
        return CeldaGrillaOperativa(ROJO, ROJO, NEGRA, codigo_actual, texto, actual["IdProfesional"] if actual else None)

    if actual is not None:
        if hay_novedad:
            texto = " ".join([base] + [t for _, t in novedades])
            if hay_aisladas:
                texto = " ".join([texto] + [t for _, _, t in aisladas])
                return CeldaGrillaOperativa(BLANCO, AMARILLO, NEGRA, codigo_actual, texto, actual["IdProfesional"])
            return CeldaGrillaOperativa(BLANCO, VERDE, NEGRA, codigo_actual, texto, actual["IdProfesional"])

        vigencia_fin = date.fromisoformat(actual["VigenciaFin"]) if actual["VigenciaFin"] else None
        if vigencia_fin is None or vigencia_fin > fecha_hasta_rango:
            return CeldaGrillaOperativa(VERDE, VERDE, NEGRA, codigo_actual, base, actual["IdProfesional"])
        return CeldaGrillaOperativa(BLANCO, BLANCO, NEGRA, codigo_actual, base, actual["IdProfesional"])

    if hay_aisladas:
        texto = " ".join(t for _, _, t in aisladas)
        codigo = profesionales[aisladas[0][1]]["IdCodigo"]
        id_prof = aisladas[0][1]
        if id_profesional_filtro is not None and id_prof == id_profesional_filtro:
            return CeldaGrillaOperativa(AZUL_OSCURO, AZUL_OSCURO, BLANCA, codigo, texto, id_prof)
        return CeldaGrillaOperativa(AMARILLO, AMARILLO, NEGRA, codigo, texto, id_prof)

    return CeldaGrillaOperativa(BLANCO, BLANCO, NEGRA, None, "Horario disponible.", None)


def _resolver_aislada(
    actual: sqlite3.Row | None, hay_aisladas: bool, aisladas: list[tuple[str, int, str]],
    hay_novedad: bool, novedades: list[tuple[str, str]],
    profesionales: dict[int, sqlite3.Row], id_profesional_filtro: int | None,
) -> CeldaGrillaOperativa:
    codigo = profesionales[aisladas[0][1]]["IdCodigo"] if hay_aisladas else None
    id_prof_mostrado = aisladas[0][1] if hay_aisladas else None
    texto_aisladas = " ".join(t for _, _, t in aisladas)

    if id_profesional_filtro is not None and id_prof_mostrado == id_profesional_filtro:
        return CeldaGrillaOperativa(AZUL_OSCURO, AZUL_OSCURO, BLANCA, codigo, texto_aisladas, id_prof_mostrado)

    if actual is not None:
        nombre_actual = _nombre_con_codigo(profesionales[actual["IdProfesional"]])
        base = f"Horario reservado en forma regular por {nombre_actual}."
        if hay_novedad:
            texto = " ".join([base] + [t for _, t in novedades])
            if hay_aisladas:
                texto = " ".join([texto] + [t for _, _, t in aisladas])
                return CeldaGrillaOperativa(ROJO, AMARILLO, NEGRA, codigo, texto, id_prof_mostrado)
            return CeldaGrillaOperativa(ROJO, VERDE, NEGRA, None, texto, None)
        return CeldaGrillaOperativa(ROJO, ROJO, NEGRA, None, base, None)

    if hay_aisladas:
        return CeldaGrillaOperativa(AMARILLO, AMARILLO, NEGRA, codigo, texto_aisladas, id_prof_mostrado)

    return CeldaGrillaOperativa(VERDE, VERDE, NEGRA, None, "Horario disponible para reservas aisladas.", None)
