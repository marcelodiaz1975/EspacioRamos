"""Cálculo de la grilla de disponibilidad (sección 4.2 del documento).

Un consultorio está "ocupado" en un día/hora si hay una ReservaRegular
vigente que lo cubre. Reglas particulares del documento:

- Una reserva confirmada que arranca en un mes posterior al mes activo
  también marca el slot como ocupado (ya está comprometido, aunque todavía
  no haya empezado).
- Una reserva cuya VigenciaFin cae en el mes siguiente al mes activo marca
  el slot como disponible (se va a liberar pronto, así que se puede ofrecer).
- Vacaciones y ausencias NO afectan esta grilla (así lo indica el documento).

Color de cada celda (por unidad/día/hora), según cuántos consultorios de
esa unidad quedan libres:
    2 o más libres -> verde
    1 libre con ventana -> amarillo
    1 libre sin ventana -> naranja
    ninguno libre -> rojo
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date

from app.negocio.ausencias import esta_ausente
from app.negocio.dias import DIAS_SEMANA, fecha_a_dia_semana
from app.negocio.dias import primer_dia_mes as _primer_dia_mes
from app.negocio.dias import ultimo_dia_mes as _ultimo_dia_mes

DIAS_GRILLA_DEFAULT = DIAS_SEMANA[:6]  # Lunes a Sábado


def dias_grilla(conn: sqlite3.Connection) -> list[str]:
    """Días configurables de la grilla (sección 3.28: Configuracion.
    DiasGrilla, JSON) — DIAS_GRILLA_DEFAULT si no está configurado o el
    valor guardado no es una lista de días válida."""
    cfg = conn.execute("SELECT DiasGrilla FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    if not cfg or not cfg["DiasGrilla"]:
        return DIAS_GRILLA_DEFAULT
    try:
        dias = json.loads(cfg["DiasGrilla"])
    except (TypeError, ValueError):
        return DIAS_GRILLA_DEFAULT
    if not isinstance(dias, list) or not dias:
        return DIAS_GRILLA_DEFAULT
    return dias

VERDE = "verde"
AMARILLO = "amarillo"
NARANJA = "naranja"
ROJO = "rojo"


def _mes_siguiente(anio: int, mes: int) -> tuple[int, int]:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def _reserva_relevante(reserva: sqlite3.Row, anio_activo: int, mes_activo: int) -> bool:
    """Descarta reservas ya terminadas antes del mes activo."""
    fin = reserva["VigenciaFin"]
    if fin is None:
        return True
    return date.fromisoformat(fin) >= _primer_dia_mes(anio_activo, mes_activo)


def _termina_mes_siguiente(vigencia_fin: str | None, anio_activo: int, mes_activo: int) -> bool:
    if not vigencia_fin:
        return False
    anio_sig, mes_sig = _mes_siguiente(anio_activo, mes_activo)
    fin = date.fromisoformat(vigencia_fin)
    return _primer_dia_mes(anio_sig, mes_sig) <= fin <= _ultimo_dia_mes(anio_sig, mes_sig)


def _ocupa_mes_activo(reserva: sqlite3.Row, anio_activo: int, mes_activo: int) -> bool:
    """Una reserva relevante ocupa el slot salvo que se esté por liberar el
    mes que viene (ver docstring del módulo)."""
    return not _termina_mes_siguiente(reserva["VigenciaFin"], anio_activo, mes_activo)


def _clasificar(consultorios_libres: list[sqlite3.Row]) -> str:
    n = len(consultorios_libres)
    if n >= 2:
        return VERDE
    if n == 0:
        return ROJO
    return AMARILLO if consultorios_libres[0]["Ventana"] else NARANJA


def calcular_ocupacion_regular(
    conn: sqlite3.Connection, anio_activo: int, mes_activo: int, dias: list[str] | None = None,
) -> dict[tuple[int, str, int], bool]:
    """Devuelve {(IdConsultorio, dia, hora): True} para cada hora ocupada."""
    dias = dias or dias_grilla(conn)
    ocupado: dict[tuple[int, str, int], bool] = {}
    reservas = conn.execute("SELECT * FROM ReservaRegular").fetchall()
    for r in reservas:
        if r["DiaSemana"] not in dias:
            continue
        if not _reserva_relevante(r, anio_activo, mes_activo):
            continue
        if not _ocupa_mes_activo(r, anio_activo, mes_activo):
            continue
        for h in range(int(r["HoraInicio"]), int(r["HoraFin"])):
            ocupado[(r["IdConsultorio"], r["DiaSemana"], h)] = True
    return ocupado


def calcular_ocupacion_fecha(conn: sqlite3.Connection, fecha: str) -> dict[tuple[int, int], bool]:
    """Ocupación real de una fecha puntual (DC-03 Mensaje 2 Variante B), a
    diferencia de `calcular_ocupacion_regular` que promedia todo un mes por
    día de semana genérico. Acá SÍ importan las excepciones de ese día
    concreto: una reserva regular no ocupa si el profesional está ausente
    ese día (mismo criterio que `verificar_conflictos_aislada`).

    Las reservas aisladas NO cuentan acá como ocupación (a diferencia de
    una primera versión de esta función): quien busca disponibilidad para
    horarios REGULARES tiene que seguir viendo el horario como alternativa
    aunque haya una aislada asignada — es un compromiso puntual de un solo
    día que se puede reubicar, no una ocupación real del consultorio. Ver
    `aisladas_confirmadas_fecha` para detectar esos casos y avisar en vez
    de bloquear. Devuelve {(IdConsultorio, hora): True}."""
    dia_semana = fecha_a_dia_semana(date.fromisoformat(fecha))
    ocupado: dict[tuple[int, int], bool] = {}

    for r in conn.execute("SELECT * FROM ReservaRegular WHERE DiaSemana = ?", (dia_semana,)).fetchall():
        vigencia_fin = r["VigenciaFin"] or "9999-12-31"
        if not (r["VigenciaInicio"] <= fecha <= vigencia_fin):
            continue
        if esta_ausente(conn, r["IdProfesional"], fecha, r["IdConsultorio"]):
            continue
        for h in range(int(r["HoraInicio"]), int(r["HoraFin"])):
            ocupado[(r["IdConsultorio"], h)] = True

    return ocupado


def aisladas_confirmadas_fecha(conn: sqlite3.Connection, fecha: str) -> list[sqlite3.Row]:
    """Reservas aisladas Confirmadas de una fecha puntual — para avisar,
    no para bloquear, cuando se ofrece esa fecha como alternativa de
    horario regular (ver `calcular_ocupacion_fecha`)."""
    return conn.execute(
        "SELECT * FROM ReservaAislada WHERE Fecha = ? AND Estado = 'Confirmada'", (fecha,)
    ).fetchall()


def calcular_grilla(
    conn: sqlite3.Connection, anio_activo: int, mes_activo: int,
    hora_ini: int | None = None, hora_fin: int | None = None, dias: list[str] | None = None,
) -> dict[tuple[int, str, int], str]:
    """Devuelve {(IdUnidad, dia, hora): color} para toda la grilla."""
    dias = dias or dias_grilla(conn)

    if hora_ini is None or hora_fin is None:
        cfg = conn.execute(
            "SELECT HoraInicioGrilla, HoraFinGrilla FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        hora_ini = hora_ini if hora_ini is not None else (cfg["HoraInicioGrilla"] if cfg else 8)
        hora_fin = hora_fin if hora_fin is not None else (cfg["HoraFinGrilla"] if cfg else 22)

    consultorios = conn.execute("SELECT IdConsultorio, IdUnidad, Ventana FROM Consultorio").fetchall()
    unidades: dict[int, list[sqlite3.Row]] = {}
    for c in consultorios:
        unidades.setdefault(c["IdUnidad"], []).append(c)

    ocupado = calcular_ocupacion_regular(conn, anio_activo, mes_activo, dias)

    resultado: dict[tuple[int, str, int], str] = {}
    for id_unidad, lista in unidades.items():
        for dia in dias:
            for h in range(int(hora_ini), int(hora_fin)):
                libres = [c for c in lista if not ocupado.get((c["IdConsultorio"], dia, h))]
                resultado[(id_unidad, dia, h)] = _clasificar(libres)
    return resultado
