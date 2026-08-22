"""Motor de cálculo de la "Grilla Operativa" (miscelánea, ago-2026):
grilla semanal (consultorio x día de la semana x hora) que muestra el
código del profesional con reserva regular vigente este mes, coloreada
según qué más pasa en ese horario. Se usa como widget compartido en
Reservas aisladas, Reservas regulares, Vacaciones, Licencias, Ausencias
y en una pantalla propia "Grilla operativa".

Cada celda tiene dos colores — "aro" (contorno, alrededor del centro) y
"centro" (relleno del medio), igual que las referencias del PDF de
Disponibilidad ("solo un consultorio disponible con ventana" = aro
amarillo con punto naranja en el centro) — más el color de fuente.

Horizonte temporal: desde HOY hasta el último día del mes siguiente al
período activo (2 meses en total, el mismo horizonte que ya usa
`calcular_ocupacion_regular`/`_termina_mes_siguiente` para decidir qué
es "el mes en curso" y qué es "meses próximos"). Vacaciones, licencias,
ausencias y aisladas se buscan en TODO ese horizonte, no solo dentro
del mes en curso, porque pueden coincidir con una liberación que recién
se concreta el mes que viene.

Reglas de color (planilla "Criterios visuales grilla operativa",
aclaradas y corregidas en conversación) — todas al mismo nivel salvo la
primera, que pisa el resto:

1. El profesional del filtro de la grilla tiene la reserva regular ESTE
   MES en esa celda -> Azul oscuro / Azul oscuro / Blanca. Ningún otro
   caso en el que aparezca ese profesional (reserva futura, aislada)
   dispara esta regla — solo la reserva regular vigente este mes.
2. Nada reservado, sin ninguna otra novedad -> Blanco / Blanco / Negra,
   sin código ("Horario disponible").
3. Regular este mes, sin ninguna otra novedad -> Blanco / Blanco / Negra.
4. Regular este mes + el profesional actual se ausenta (vacaciones,
   licencia o ausencia) en algún tramo dentro del horizonte -> Blanco /
   Verde / Negra.
5. Regular este mes + el propio profesional ya tiene cargada su baja a
   futuro (VigenciaFin dentro del horizonte), sin nadie tomando el
   lugar todavía -> Verde / Verde / Negra.
6. Ídem anterior + ya hay una aislada asignada en ese hueco liberado ->
   Verde / Amarillo / Negra.
7. Regular este mes + YA hay otro profesional con reserva regular
   futura cargada en ese mismo horario (conflicto de titularidad) ->
   Rojo / Rojo / Negra.
8. Libre este mes, entra un profesional nuevo el mes próximo, sin
   ninguna otra novedad -> Rojo / Rojo / Negra.
9. Ídem + ese profesional entrante se ausenta (vacaciones, licencia o
   ausencia) dentro del horizonte -> Rojo / Verde / Negra.
10. Ídem (con o sin lo anterior) + hay una aislada en el medio, la
    aislada manda en el centro -> Rojo / Amarillo / Negra.
11. Regular este mes + hay una aislada asignada más adelante en ese
    mismo horario, sin baja propia cargada -> Amarillo / Amarillo /
    Negra.
12. Libre este mes, solo hay una aislada asignada más adelante ->
    Amarillo / Amarillo / Negra.

El código que se muestra en la celda es siempre el del profesional con
la reserva regular vigente ESTE MES (nunca el de una aislada ni el de
un profesional entrante todavía no vigente) — si no hay reserva regular
vigente este mes la celda no muestra código, aunque tenga color.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from app.negocio.dias import DIAS_SEMANA, fecha_a_dia_semana, fecha_actual, parsear_periodo, ultimo_dia_mes

AZUL_OSCURO = "azul_oscuro"
BLANCO = "blanco"
VERDE = "verde"
AMARILLO = "amarillo"
ROJO = "rojo"
NEGRA = "negra"
BLANCA = "blanca"


@dataclass
class CeldaGrillaOperativa:
    color_aro: str
    color_centro: str
    color_fuente: str
    codigo: str | None
    detalle: str
    id_profesional_actual: int | None


def _mes_siguiente(anio: int, mes: int) -> tuple[int, int]:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def _horizonte(conn: sqlite3.Connection, periodo_activo: str) -> tuple[date, date, date]:
    """(hoy, último día del mes activo, último día del mes próximo)."""
    anio, mes = parsear_periodo(periodo_activo)
    anio_sig, mes_sig = _mes_siguiente(anio, mes)
    return fecha_actual(conn), ultimo_dia_mes(anio, mes), ultimo_dia_mes(anio_sig, mes_sig)


def _nombre_con_codigo(profesional: sqlite3.Row) -> str:
    partes = [p for p in (profesional["Tratamiento"], profesional["NombrePila"], profesional["Apellido"]) if p]
    nombre = " ".join(partes) if partes else profesional["Apellido"]
    codigo = profesional["IdCodigo"]
    return f"{nombre} ({codigo})" if codigo else nombre


def _fecha_dia_texto(fecha_iso: str) -> str:
    f = date.fromisoformat(fecha_iso)
    return f"{fecha_a_dia_semana(f).lower()} {f.day}/{f.month}"


def _rango_intersecta_dia_semana(fecha_desde: str, fecha_hasta: str, dia_semana: str, hoy: date, fin_horizonte: date) -> bool:
    desde = max(date.fromisoformat(fecha_desde), hoy)
    hasta = min(date.fromisoformat(fecha_hasta), fin_horizonte)
    if desde > hasta:
        return False
    cursor = desde
    while cursor <= hasta:
        if fecha_a_dia_semana(cursor) == dia_semana:
            return True
        cursor += timedelta(days=1)
    return False


def _clasificar_ausencia_novedades(
    conn: sqlite3.Connection, id_profesional: int, dia_semana: str, hoy: date, fin_horizonte: date,
    id_consultorio: int,
) -> tuple[bool, list[tuple[str, str]]]:
    """(hay_novedad, [(fecha_orden, texto)]) para vacaciones, licencias y
    ausencias del profesional dentro del horizonte que caen en ese día de
    la semana."""
    clausulas: list[tuple[str, str]] = []

    for v in conn.execute("SELECT * FROM Vacacion WHERE IdProfesional = ?", (id_profesional,)).fetchall():
        if _rango_intersecta_dia_semana(v["FechaDesde"], v["FechaHasta"], dia_semana, hoy, fin_horizonte):
            texto = f"De vacaciones desde el {_fecha_dia_texto(v['FechaDesde'])} hasta el {_fecha_dia_texto(v['FechaHasta'])}."
            clausulas.append((v["FechaDesde"], texto))

    for lic in conn.execute(
        "SELECT l.*, t.Nombre AS NombreTipo FROM Licencia l JOIN TipoLicencia t ON t.IdTipoLicencia = l.IdTipoLicencia "
        "WHERE l.IdProfesional = ?", (id_profesional,),
    ).fetchall():
        if _rango_intersecta_dia_semana(lic["FechaDesde"], lic["FechaHasta"], dia_semana, hoy, fin_horizonte):
            texto = (
                f"De licencia por {lic['NombreTipo'].lower()} desde el {_fecha_dia_texto(lic['FechaDesde'])} "
                f"hasta el {_fecha_dia_texto(lic['FechaHasta'])}."
            )
            clausulas.append((lic["FechaDesde"], texto))

    for a in conn.execute("SELECT * FROM Ausencia WHERE IdProfesional = ?", (id_profesional,)).fetchall():
        if a["IdConsultorio"] is not None and a["IdConsultorio"] != id_consultorio:
            continue
        if not _rango_intersecta_dia_semana(a["FechaDesde"], a["FechaHasta"], dia_semana, hoy, fin_horizonte):
            continue
        motivo = f" por {a['Motivo'].lower()}" if a["Motivo"] else ""
        if a["FechaDesde"] == a["FechaHasta"]:
            texto = f"Ausente{motivo} el {_fecha_dia_texto(a['FechaDesde'])}."
        else:
            texto = f"Ausente{motivo} desde el {_fecha_dia_texto(a['FechaDesde'])} hasta el {_fecha_dia_texto(a['FechaHasta'])}."
        clausulas.append((a["FechaDesde"], texto))

    return bool(clausulas), clausulas


def _aisladas_novedades(
    conn: sqlite3.Connection, id_consultorio: int, dia_semana: str, hora: float, hoy: date, fin_horizonte: date,
    cache_profesionales: dict[int, sqlite3.Row],
) -> tuple[bool, list[tuple[str, str]]]:
    filas = conn.execute(
        "SELECT * FROM ReservaAislada WHERE IdConsultorio = ? AND Estado = 'Confirmada' "
        "AND Fecha BETWEEN ? AND ? AND HoraInicio <= ? AND HoraFin > ?",
        (id_consultorio, hoy.isoformat(), fin_horizonte.isoformat(), hora, hora),
    ).fetchall()
    clausulas: list[tuple[str, str]] = []
    for f in filas:
        if fecha_a_dia_semana(date.fromisoformat(f["Fecha"])) != dia_semana:
            continue
        nombre = _nombre_con_codigo(cache_profesionales[f["IdProfesional"]])
        texto = f"Hora aislada reservada por {nombre} para el {_fecha_dia_texto(f['Fecha'])}."
        clausulas.append((f["Fecha"], texto))
    return bool(clausulas), clausulas


def calcular_grilla_operativa(
    conn: sqlite3.Connection, ids_consultorio: list[int], dias: list[str], hora_ini: int, hora_fin: int,
    periodo_activo: str, id_profesional_filtro: int | None = None,
) -> dict[tuple[int, str, int], CeldaGrillaOperativa]:
    """Devuelve {(IdConsultorio, dia, hora): CeldaGrillaOperativa} para
    toda la grilla filtrada."""
    hoy, fin_mes_activo, fin_horizonte = _horizonte(conn, periodo_activo)
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
                actual = None
                entrante = None
                for r in cubren:
                    vigencia_fin = date.fromisoformat(r["VigenciaFin"]) if r["VigenciaFin"] else None
                    vigencia_inicio = date.fromisoformat(r["VigenciaInicio"])
                    vigente_activo = vigencia_inicio <= fin_mes_activo and (vigencia_fin is None or vigencia_fin >= hoy)
                    futuro = fin_mes_activo < vigencia_inicio <= fin_horizonte
                    if vigente_activo and actual is None:
                        actual = r
                    elif futuro and entrante is None:
                        entrante = r

                resultado[(id_consultorio, dia, hora)] = _resolver_celda(
                    conn, id_consultorio, dia, hora, hoy, fin_horizonte, actual, entrante,
                    profesionales, id_profesional_filtro,
                )
    return resultado


def _resolver_celda(
    conn: sqlite3.Connection, id_consultorio: int, dia: str, hora: int, hoy: date, fin_horizonte: date,
    actual: sqlite3.Row | None, entrante: sqlite3.Row | None,
    profesionales: dict[int, sqlite3.Row], id_profesional_filtro: int | None,
) -> CeldaGrillaOperativa:
    tiene_aislada, clausulas_aisladas = _aisladas_novedades(conn, id_consultorio, dia, hora, hoy, fin_horizonte, profesionales)

    if actual is not None:
        id_actual = actual["IdProfesional"]
        nombre_actual = _nombre_con_codigo(profesionales[id_actual])
        codigo = profesionales[id_actual]["IdCodigo"]

        if id_profesional_filtro is not None and id_actual == id_profesional_filtro:
            return CeldaGrillaOperativa(
                AZUL_OSCURO, AZUL_OSCURO, BLANCA, codigo, f"Horario reservado por {nombre_actual}.", id_actual,
            )

        base = f"Horario reservado por {nombre_actual}."

        if entrante is not None and entrante["IdProfesional"] != id_actual:
            nombre_entrante = _nombre_con_codigo(profesionales[entrante["IdProfesional"]])
            texto = f"{base} Horario reservado por {nombre_entrante} a partir del {_fecha_dia_texto(entrante['VigenciaInicio'])}."
            return CeldaGrillaOperativa(ROJO, ROJO, NEGRA, codigo, texto, id_actual)

        vigencia_fin = date.fromisoformat(actual["VigenciaFin"]) if actual["VigenciaFin"] else None
        libera_pronto = vigencia_fin is not None and hoy <= vigencia_fin <= fin_horizonte
        if libera_pronto:
            fecha_liberacion = _fecha_dia_texto((vigencia_fin + timedelta(days=1)).isoformat())
            texto = f"{base} Horario liberado a partir del {fecha_liberacion}."
            if tiene_aislada:
                texto = " ".join([texto] + [c[1] for c in sorted(clausulas_aisladas)])
                return CeldaGrillaOperativa(VERDE, AMARILLO, NEGRA, codigo, texto, id_actual)
            return CeldaGrillaOperativa(VERDE, VERDE, NEGRA, codigo, texto, id_actual)

        if tiene_aislada:
            texto = " ".join([base] + [c[1] for c in sorted(clausulas_aisladas)])
            return CeldaGrillaOperativa(AMARILLO, AMARILLO, NEGRA, codigo, texto, id_actual)

        tiene_novedad, clausulas_novedad = _clasificar_ausencia_novedades(conn, id_actual, dia, hoy, fin_horizonte, id_consultorio)
        if tiene_novedad:
            texto = " ".join([base] + [c[1] for c in sorted(clausulas_novedad)])
            return CeldaGrillaOperativa(BLANCO, VERDE, NEGRA, codigo, texto, id_actual)

        return CeldaGrillaOperativa(BLANCO, BLANCO, NEGRA, codigo, base, id_actual)

    if entrante is not None:
        id_entrante = entrante["IdProfesional"]
        nombre_entrante = _nombre_con_codigo(profesionales[id_entrante])
        base = f"Horario reservado por {nombre_entrante} a partir del {_fecha_dia_texto(entrante['VigenciaInicio'])}."

        if tiene_aislada:
            texto = " ".join([base] + [c[1] for c in sorted(clausulas_aisladas)])
            return CeldaGrillaOperativa(ROJO, AMARILLO, NEGRA, None, texto, None)

        tiene_novedad, clausulas_novedad = _clasificar_ausencia_novedades(conn, id_entrante, dia, hoy, fin_horizonte, id_consultorio)
        if tiene_novedad:
            texto = " ".join([base] + [c[1] for c in sorted(clausulas_novedad)])
            return CeldaGrillaOperativa(ROJO, VERDE, NEGRA, None, texto, None)

        return CeldaGrillaOperativa(ROJO, ROJO, NEGRA, None, base, None)

    if tiene_aislada:
        texto = " ".join(c[1] for c in sorted(clausulas_aisladas))
        return CeldaGrillaOperativa(AMARILLO, AMARILLO, NEGRA, None, texto, None)

    return CeldaGrillaOperativa(BLANCO, BLANCO, NEGRA, None, "Horario disponible.", None)
