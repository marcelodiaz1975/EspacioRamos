"""Motor de cálculo de la "Grilla Operativa" (miscelánea, ago-2026,
tercera versión — reemplaza el esquema de rango de fechas explícito por
un único "Período" AAAA-MM, y rediseña por completo las reglas de color
del modo "regular").

Grilla semanal (consultorio x día de la semana x hora), evaluada contra
un ÚNICO PERÍODO que elige quien consulta (por defecto el mes en curso
al entrar a la pantalla). Se usa como widget compartido en Reservas
aisladas, Reservas regulares, Vacaciones, Licencias, Ausencias y en una
pantalla propia "Grilla operativa".

Dos modos de visualización con reglas de color propias:

MODO "regular" — pensado para responder "¿quién tiene este horario, y
qué va a cambiar?" (rediseño ago-2026, confirmado por la clienta con
mockup):
  - Blanco liso: sin circunstancias para destacar (vacaciones, ausencias,
    licencias, reservas entrantes, aisladas) dentro del mes en curso o
    los meses posteriores — con el código de quien lo tiene reservado
    hoy, si hay alguien.
  - Verde liso: hay una reserva activa hoy con fecha de liberación
    conocida (VigenciaFin cargada) — se va a liberar en algún momento.
  - Rojo liso: el horario tiene una reserva regular que todavía no
    arrancó (cargada a futuro), sin aisladas asignadas dentro del mes en
    curso. Si además hay alguien ocupándolo hoy, se lo menciona en el
    detalle, pero el color pasa a rojo igual (aviso de cambio próximo).
  - Amarillo liso: no hay ninguna reserva regular (ni activa ni
    entrante) pero ya hay una hora aislada confirmada, desde hoy en
    adelante (dentro del mes en curso o en meses posteriores).
  - Rojo con triángulo derecho amarillo: como "Rojo liso", pero además
    ya hay una o más aisladas confirmadas dentro del mes en curso.
  - Blanco con triángulo derecho verde: hay una reserva activa hoy, pero
    su titular libera un hueco puntual dentro del mes en curso (por
    vacaciones/licencia/ausencia), todavía sin tomar.
  - Blanco con triángulo derecho amarillo: igual que el anterior, pero
    ese hueco ya tiene una aislada confirmada adentro.

  Interpretación de "meses posteriores" para Verde/Rojo liso: no se exige
  que el corte de mes ya haya pasado — alcanza con que la reserva activa
  tenga una fecha de baja cargada (Verde) o con que exista una reserva
  entrante cargada a futuro (Rojo), sin importar si esa fecha cae más
  adelante este mismo mes o en uno posterior. Es la misma lógica de
  corte "todo lo de hoy en adelante" que ya se usaba en el diseño
  anterior de esta grilla — más simple y consistente con el resto de las
  reglas, que si distinguiera "este mes" de "meses futuros" para estos
  dos casos puntuales.

  Regla del código (independiente del color, confirmada por la clienta):
  el código del profesional aparece ÚNICAMENTE cuando el horario está
  ocupado por una reserva regular vigente HOY dentro del período
  consultado — nunca por una reserva entrante (todavía no vigente) ni
  por una aislada (no es una reserva regular). El color de fondo puede
  cambiar sin que esto se altere.

MODO "aislada" — sin cambios de reglas todavía (a definir por la
clienta) — pensado para responder "¿puedo poner una hora aislada acá?":
no le importan las reservas regulares que todavía no arrancaron (un
profesional "entrante" no bloquea nada hasta que efectivamente empieza),
solo lo que está activo HOY. El rango que antes elegía el usuario a mano
(Desde/Hasta) ahora es siempre el mes completo del período seleccionado.
  - Rojo completo: bloqueado en todo el mes por una reserva regular
    activa sin ningún hueco.
  - Verde completo: libre de reserva regular en todo el mes.
  - Rojo con centro verde: reservado en forma regular dentro del mes,
    pero libera algún hueco dentro de ese mes por vacaciones/licencia
    /ausencia (todavía sin tomar).
  - Rojo con centro amarillo: igual que el anterior, pero el hueco ya
    tiene una aislada confirmada adentro.
  - Amarillo completo: libre de reserva regular en todo el mes + ya hay
    una aislada asignada dentro del mes.

Regla común a los dos modos, y de prioridad máxima sobre cualquier otro
color (confirmado por la clienta): si el profesional del filtro de la
grilla es el que tiene el código mostrado en la celda, esa celda pasa a
Azul oscuro con fuente blanca, pisando cualquier otro color — incluida
la propia regla del código: en modo "regular" esto solo puede pasar en
una celda que YA muestra código (reserva vigente hoy), nunca en una
celda "Amarillo liso" (aislada sin reserva regular), porque ahí no hay
código para resaltar.

"Fecha de corte" (aclarado en conversación): todo se evalúa tomando HOY
como referencia — una vacación/licencia/ausencia que ya terminó ayer no
cuenta, una que termina hoy sí. Una reserva regular que todavía no
arrancó hoy nunca cuenta como "la reserva actual".
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.negocio.dias import DIAS_SEMANA, fecha_a_dia_semana, fecha_actual, parsear_periodo, primer_dia_mes, ultimo_dia_mes

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
    conn: sqlite3.Connection, id_profesional: int, dia_semana: str, id_consultorio: int, hora: float,
    hoy: date, fecha_desde_rango: date, fecha_hasta_rango: date,
) -> list[tuple[str, str]]:
    """[(fecha_orden, texto)] de vacaciones, licencias y ausencias del
    profesional que caen en ese día de la semana dentro del rango. Las
    ausencias con horario puntual (HoraInicio/HoraFin) solo cuentan para
    la `hora` consultada — sin horario puntual (ambos None) cubren todo
    el día, igual que vacaciones y licencias (que no tienen ese campo)."""
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
        if a["HoraInicio"] is not None and a["HoraFin"] is not None and not (a["HoraInicio"] <= hora < a["HoraFin"]):
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
    periodo: str, modo: ModoGrillaOperativa = "regular", id_profesional_filtro: int | None = None,
    ausente_en: set[tuple[int, str, int]] | None = None,
) -> dict[tuple[int, str, int], CeldaGrillaOperativa]:
    """Devuelve {(IdConsultorio, dia, hora): CeldaGrillaOperativa} para
    toda la grilla filtrada, evaluada contra el mes del `periodo`
    (AAAA-MM) consultado.

    `ausente_en`, si se pasa, es el conjunto de (IdConsultorio, dia, hora)
    donde el profesional del filtro tiene una ausencia registrada — usado
    por la pantalla de Ausencias para resaltar en verde con letra negra
    los horarios que de otro modo se mostrarían en azul oscuro (el
    horario propio del profesional filtrado)."""
    hoy = fecha_actual(conn)
    anio, mes = parsear_periodo(periodo)
    mes_actual_inicio = primer_dia_mes(anio, mes)
    mes_actual_fin = ultimo_dia_mes(anio, mes)
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
                if modo == "regular":
                    celda = _resolver_regular(
                        conn, id_consultorio, dia, hora, hoy, mes_actual_inicio, mes_actual_fin,
                        actual, entrante, profesionales, id_profesional_filtro,
                    )
                else:
                    celda = _resolver_aislada(
                        conn, id_consultorio, dia, hora, hoy, mes_actual_inicio, mes_actual_fin,
                        actual, profesionales, id_profesional_filtro,
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


# ------------------------------------------------------------ modo regular


def _resolver_regular(
    conn: sqlite3.Connection, id_consultorio: int, dia: str, hora: int, hoy: date,
    mes_actual_inicio: date, mes_actual_fin: date, actual: sqlite3.Row | None, entrante: sqlite3.Row | None,
    profesionales: dict[int, sqlite3.Row], id_profesional_filtro: int | None,
) -> CeldaGrillaOperativa:
    codigo = profesionales[actual["IdProfesional"]]["IdCodigo"] if actual is not None else None
    id_mostrado = actual["IdProfesional"] if actual is not None else None
    base = f"Horario reservado por {_nombre_con_codigo(profesionales[actual['IdProfesional']])}." if actual is not None else None

    # Regla de prioridad máxima: el filtro pinta azul cualquier celda
    # donde su código quede mostrado — que, por la regla del código, solo
    # puede pasar sobre una reserva vigente hoy.
    if actual is not None and id_profesional_filtro is not None and actual["IdProfesional"] == id_profesional_filtro:
        return CeldaGrillaOperativa(AZUL_OSCURO, AZUL_OSCURO, BLANCA, codigo, base, id_mostrado)

    if entrante is not None:
        nombre_entrante = _nombre_con_codigo(profesionales[entrante["IdProfesional"]])
        clausula_entrante = f"Horario reservado por {nombre_entrante} a partir del {_fecha_dia_texto(entrante['VigenciaInicio'])}."
        texto = " ".join(([base] if base else []) + [clausula_entrante])
        aisladas_mes = _aisladas_en_rango(conn, id_consultorio, dia, hora, hoy, mes_actual_inicio, mes_actual_fin, profesionales)
        if aisladas_mes:
            texto = " ".join([texto] + [t for _, _, t in aisladas_mes])
            return CeldaGrillaOperativa(ROJO, AMARILLO, NEGRA, codigo, texto, id_mostrado)
        return CeldaGrillaOperativa(ROJO, ROJO, NEGRA, codigo, texto, id_mostrado)

    if actual is not None:
        novedades = _novedades_profesional(conn, actual["IdProfesional"], dia, id_consultorio, hora, hoy, mes_actual_inicio, mes_actual_fin)
        if novedades:
            texto = " ".join([base] + [t for _, t in novedades])
            aisladas_mes = _aisladas_en_rango(conn, id_consultorio, dia, hora, hoy, mes_actual_inicio, mes_actual_fin, profesionales)
            if aisladas_mes:
                texto = " ".join([texto] + [t for _, _, t in aisladas_mes])
                return CeldaGrillaOperativa(BLANCO, AMARILLO, NEGRA, codigo, texto, id_mostrado)
            return CeldaGrillaOperativa(BLANCO, VERDE, NEGRA, codigo, texto, id_mostrado)

        if actual["VigenciaFin"]:
            texto = f"{base} Se libera el {_fecha_dia_texto(actual['VigenciaFin'])}."
            return CeldaGrillaOperativa(VERDE, VERDE, NEGRA, codigo, texto, id_mostrado)

        return CeldaGrillaOperativa(BLANCO, BLANCO, NEGRA, codigo, base, id_mostrado)

    aisladas_desde_hoy = _aisladas_en_rango(conn, id_consultorio, dia, hora, hoy, hoy, date.max, profesionales)
    if aisladas_desde_hoy:
        texto = " ".join(t for _, _, t in aisladas_desde_hoy)
        return CeldaGrillaOperativa(AMARILLO, AMARILLO, NEGRA, None, texto, None)

    return CeldaGrillaOperativa(BLANCO, BLANCO, NEGRA, None, "Horario disponible.", None)


# ------------------------------------------------------------ modo aislada


def _resolver_aislada(
    conn: sqlite3.Connection, id_consultorio: int, dia: str, hora: int, hoy: date,
    mes_actual_inicio: date, mes_actual_fin: date, actual: sqlite3.Row | None,
    profesionales: dict[int, sqlite3.Row], id_profesional_filtro: int | None,
) -> CeldaGrillaOperativa:
    aisladas = _aisladas_en_rango(conn, id_consultorio, dia, hora, hoy, mes_actual_inicio, mes_actual_fin, profesionales)
    hay_aisladas = bool(aisladas)
    codigo = profesionales[aisladas[0][1]]["IdCodigo"] if hay_aisladas else None
    id_prof_mostrado = aisladas[0][1] if hay_aisladas else None
    texto_aisladas = " ".join(t for _, _, t in aisladas)

    if id_profesional_filtro is not None and id_prof_mostrado == id_profesional_filtro:
        return CeldaGrillaOperativa(AZUL_OSCURO, AZUL_OSCURO, BLANCA, codigo, texto_aisladas, id_prof_mostrado)

    if actual is not None:
        nombre_actual = _nombre_con_codigo(profesionales[actual["IdProfesional"]])
        base = f"Horario reservado en forma regular por {nombre_actual}."
        novedades = _novedades_profesional(conn, actual["IdProfesional"], dia, id_consultorio, hora, hoy, mes_actual_inicio, mes_actual_fin)
        if novedades:
            texto = " ".join([base] + [t for _, t in novedades])
            if hay_aisladas:
                texto = " ".join([texto] + [t for _, _, t in aisladas])
                return CeldaGrillaOperativa(ROJO, AMARILLO, NEGRA, codigo, texto, id_prof_mostrado)
            return CeldaGrillaOperativa(ROJO, VERDE, NEGRA, None, texto, None)
        return CeldaGrillaOperativa(ROJO, ROJO, NEGRA, None, base, None)

    if hay_aisladas:
        return CeldaGrillaOperativa(AMARILLO, AMARILLO, NEGRA, codigo, texto_aisladas, id_prof_mostrado)

    return CeldaGrillaOperativa(VERDE, VERDE, NEGRA, None, "Horario disponible para reservas aisladas.", None)
