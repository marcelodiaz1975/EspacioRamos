"""Validaciones y alta/baja de reservas (Etapa 2).

Reglas tomadas de las secciones 3.9 a 3.11 del documento de planificación:

- Dos reservas del mismo consultorio no pueden superponerse en día/horario,
  excepto que sean de un profesional categoría E y su propio R (cat.
  "ProfesionalCabezaEquipo"): en ese caso se avisa pero no se bloquea.
- Un bloque rígido no se puede reservar parcialmente: si una reserva toca
  un bloque rígido activo ese día, tiene que cubrirlo completo.
- Cancelar una reserva aislada el mismo día está permitida (con aviso),
  salvo que el horario caiga dentro de un bloque rígido.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date

from app.negocio.dias import fecha_a_dia_semana
from app.repositorio.registro import obtener_repositorio

FIN_INDEFINIDO = "9999-12-31"


@dataclass
class Conflicto:
    bloqueante: bool
    mensaje: str
    reserva_existente: sqlite3.Row


class ConflictoBloqueanteError(Exception):
    def __init__(self, conflictos: list[Conflicto] | None = None, mensajes: list[str] | None = None):
        self.conflictos = conflictos or []
        self.mensajes_adicionales = mensajes or []
        textos = [c.mensaje for c in self.conflictos] + self.mensajes_adicionales
        super().__init__("; ".join(textos))


# ---------------------------------------------------------------- utilidades

def _solapan(inicio_a, fin_a, inicio_b, fin_b) -> bool:
    return inicio_a < fin_b and inicio_b < fin_a


def _vigencias_solapan(inicio_a, fin_a, inicio_b, fin_b) -> bool:
    fin_a = fin_a or FIN_INDEFINIDO
    fin_b = fin_b or FIN_INDEFINIDO
    return inicio_a <= fin_b and inicio_b <= fin_a


def _relacion_equipo(conn: sqlite3.Connection, id_profesional_a: int, id_profesional_b: int) -> bool:
    """True si a y b son la misma persona, o un par E / su propio R (superposición
    permitida con aviso en vez de bloqueo, según sección 3.9)."""
    if id_profesional_a == id_profesional_b:
        return True
    prof_a = conn.execute(
        "SELECT CategoriaProfesional, ProfesionalCabezaEquipo FROM Profesional WHERE IdProfesional = ?",
        (id_profesional_a,),
    ).fetchone()
    prof_b = conn.execute(
        "SELECT CategoriaProfesional, ProfesionalCabezaEquipo FROM Profesional WHERE IdProfesional = ?",
        (id_profesional_b,),
    ).fetchone()
    if prof_a is None or prof_b is None:
        return False
    if prof_a["CategoriaProfesional"] == "E" and prof_a["ProfesionalCabezaEquipo"] == id_profesional_b:
        return True
    if prof_b["CategoriaProfesional"] == "E" and prof_b["ProfesionalCabezaEquipo"] == id_profesional_a:
        return True
    return False


def verificar_bloques_rigidos(conn: sqlite3.Connection, dia_semana: str, hora_inicio: float, hora_fin: float) -> list[str]:
    problemas = []
    for fila in conn.execute("SELECT * FROM BloqueRigido WHERE Activo = 1").fetchall():
        dias = json.loads(fila["DiasLogica"] or "[]")
        if dia_semana not in dias:
            continue
        b_ini, b_fin = fila["HoraInicio"], fila["HoraFin"]
        if not _solapan(hora_inicio, hora_fin, b_ini, b_fin):
            continue
        if hora_inicio > b_ini or hora_fin < b_fin:
            problemas.append(
                f"El bloque rígido de {b_ini}–{b_fin}hs de los {dia_semana} no se puede "
                f"reservar parcialmente: la reserva debe cubrirlo completo"
            )
    return problemas


def _horario_en_bloque_rigido(conn: sqlite3.Connection, dia_semana: str, hora_inicio: float, hora_fin: float) -> bool:
    for fila in conn.execute("SELECT * FROM BloqueRigido WHERE Activo = 1").fetchall():
        dias = json.loads(fila["DiasVisualizacion"] or fila["DiasLogica"] or "[]")
        if dia_semana not in dias:
            continue
        if _solapan(hora_inicio, hora_fin, fila["HoraInicio"], fila["HoraFin"]):
            return True
    return False


# -------------------------------------------------------- verificación de conflictos

def verificar_conflictos_regular(
    conn: sqlite3.Connection, *, id_consultorio: int, dia_semana: str,
    hora_inicio: float, hora_fin: float, vigencia_inicio: str,
    vigencia_fin: str | None, id_profesional: int, excluir_id: int | None = None,
) -> list[Conflicto]:
    conflictos = []
    filas = conn.execute(
        "SELECT * FROM ReservaRegular WHERE IdConsultorio = ? AND DiaSemana = ?",
        (id_consultorio, dia_semana),
    ).fetchall()
    for fila in filas:
        if excluir_id is not None and fila["IdReservaRegular"] == excluir_id:
            continue
        if not _solapan(hora_inicio, hora_fin, fila["HoraInicio"], fila["HoraFin"]):
            continue
        if not _vigencias_solapan(vigencia_inicio, vigencia_fin, fila["VigenciaInicio"], fila["VigenciaFin"]):
            continue
        bloqueante = not _relacion_equipo(conn, id_profesional, fila["IdProfesional"])
        conflictos.append(Conflicto(
            bloqueante=bloqueante,
            mensaje=(
                f"Se superpone con la reserva regular #{fila['IdReservaRegular']} del "
                f"profesional #{fila['IdProfesional']} ({dia_semana} {fila['HoraInicio']}–{fila['HoraFin']}hs)"
            ),
            reserva_existente=fila,
        ))
    return conflictos


def verificar_conflictos_aislada(
    conn: sqlite3.Connection, *, id_consultorio: int, fecha: str,
    hora_inicio: float, hora_fin: float, id_profesional: int, excluir_id: int | None = None,
) -> list[Conflicto]:
    conflictos = []
    dia_semana = fecha_a_dia_semana(date.fromisoformat(fecha))

    filas = conn.execute(
        "SELECT * FROM ReservaAislada WHERE IdConsultorio = ? AND Fecha = ? AND Estado = 'Confirmada'",
        (id_consultorio, fecha),
    ).fetchall()
    for fila in filas:
        if excluir_id is not None and fila["IdReservaAislada"] == excluir_id:
            continue
        if not _solapan(hora_inicio, hora_fin, fila["HoraInicio"], fila["HoraFin"]):
            continue
        bloqueante = not _relacion_equipo(conn, id_profesional, fila["IdProfesional"])
        conflictos.append(Conflicto(
            bloqueante=bloqueante,
            mensaje=(
                f"Se superpone con la reserva aislada #{fila['IdReservaAislada']} del "
                f"profesional #{fila['IdProfesional']} ({fecha} {fila['HoraInicio']}–{fila['HoraFin']}hs)"
            ),
            reserva_existente=fila,
        ))

    filas = conn.execute(
        "SELECT * FROM ReservaRegular WHERE IdConsultorio = ? AND DiaSemana = ?",
        (id_consultorio, dia_semana),
    ).fetchall()
    for fila in filas:
        if not _solapan(hora_inicio, hora_fin, fila["HoraInicio"], fila["HoraFin"]):
            continue
        if not _vigencias_solapan(fecha, fecha, fila["VigenciaInicio"], fila["VigenciaFin"]):
            continue
        bloqueante = not _relacion_equipo(conn, id_profesional, fila["IdProfesional"])
        conflictos.append(Conflicto(
            bloqueante=bloqueante,
            mensaje=(
                f"Se superpone con la reserva regular #{fila['IdReservaRegular']} del "
                f"profesional #{fila['IdProfesional']} ({dia_semana} {fila['HoraInicio']}–{fila['HoraFin']}hs)"
            ),
            reserva_existente=fila,
        ))
    return conflictos


# ------------------------------------------------------------------------ servicio

def crear_reserva_regular(
    conn: sqlite3.Connection, *, id_profesional: int, id_consultorio: int, dia_semana: str,
    hora_inicio: float, hora_fin: float, vigencia_inicio: str, vigencia_fin: str | None = None,
    es_excepcion: bool = False, observacion: str | None = None, forzar: bool = False,
) -> tuple[int, list[str]]:
    conflictos = verificar_conflictos_regular(
        conn, id_consultorio=id_consultorio, dia_semana=dia_semana,
        hora_inicio=hora_inicio, hora_fin=hora_fin,
        vigencia_inicio=vigencia_inicio, vigencia_fin=vigencia_fin,
        id_profesional=id_profesional,
    )
    problemas_rigidos = verificar_bloques_rigidos(conn, dia_semana, hora_inicio, hora_fin)
    bloqueantes = [c for c in conflictos if c.bloqueante]
    if (bloqueantes or problemas_rigidos) and not forzar:
        raise ConflictoBloqueanteError(bloqueantes, problemas_rigidos)

    repo = obtener_repositorio(conn, "ReservaRegular")
    id_reserva = repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, DiaSemana=dia_semana,
        HoraInicio=hora_inicio, HoraFin=hora_fin, VigenciaInicio=vigencia_inicio,
        VigenciaFin=vigencia_fin, EsExcepcion=int(es_excepcion), Observacion=observacion,
    )
    advertencias = [c.mensaje for c in conflictos if not c.bloqueante]
    if forzar:
        advertencias += [c.mensaje for c in bloqueantes] + problemas_rigidos
    return id_reserva, advertencias


def crear_reserva_aislada(
    conn: sqlite3.Connection, *, id_profesional: int, id_consultorio: int, fecha: str,
    hora_inicio: float, hora_fin: float, aplica_recargo: bool | None = None,
    es_reubicacion: bool = False, observacion: str | None = None, forzar: bool = False,
) -> tuple[int, list[str]]:
    conflictos = verificar_conflictos_aislada(
        conn, id_consultorio=id_consultorio, fecha=fecha,
        hora_inicio=hora_inicio, hora_fin=hora_fin, id_profesional=id_profesional,
    )
    dia_semana = fecha_a_dia_semana(date.fromisoformat(fecha))
    problemas_rigidos = verificar_bloques_rigidos(conn, dia_semana, hora_inicio, hora_fin)
    bloqueantes = [c for c in conflictos if c.bloqueante]
    if (bloqueantes or problemas_rigidos) and not forzar:
        raise ConflictoBloqueanteError(bloqueantes, problemas_rigidos)

    if aplica_recargo is None:
        fila_cfg = conn.execute(
            "SELECT RecargoAisladasActivoPorDefecto FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        aplica_recargo = bool(fila_cfg["RecargoAisladasActivoPorDefecto"]) if fila_cfg else False

    repo = obtener_repositorio(conn, "ReservaAislada")
    id_reserva = repo.crear(
        IdProfesional=id_profesional, IdConsultorio=id_consultorio, Fecha=fecha,
        HoraInicio=hora_inicio, HoraFin=hora_fin, Estado="Confirmada",
        AplicaRecargo=int(aplica_recargo), EsReubicacion=int(es_reubicacion), Observacion=observacion,
    )
    advertencias = [c.mensaje for c in conflictos if not c.bloqueante]
    if forzar:
        advertencias += [c.mensaje for c in bloqueantes] + problemas_rigidos
    return id_reserva, advertencias


def cancelar_reserva_aislada(
    conn: sqlite3.Connection, id_reserva_aislada: int, fecha_actual: str | None = None,
) -> bool:
    """Cancela una reserva aislada. Devuelve True si la cancelación requiere
    aviso (porque fue el mismo día). Lanza ValueError si el horario cae
    dentro de un bloque rígido y se está cancelando el mismo día."""
    repo = obtener_repositorio(conn, "ReservaAislada")
    reserva = repo.obtener(id_reserva_aislada)
    if reserva is None:
        raise ValueError(f"No existe la reserva aislada #{id_reserva_aislada}")

    fecha_actual = fecha_actual or date.today().isoformat()
    mismo_dia = fecha_actual == reserva["Fecha"]
    requiere_aviso = False

    if mismo_dia:
        dia_semana = fecha_a_dia_semana(date.fromisoformat(reserva["Fecha"]))
        if _horario_en_bloque_rigido(conn, dia_semana, reserva["HoraInicio"], reserva["HoraFin"]):
            raise ValueError(
                f"No se puede cancelar la reserva #{id_reserva_aislada} el mismo día: "
                "el horario cae dentro de un bloque rígido"
            )
        requiere_aviso = True

    repo.actualizar(id_reserva_aislada, Estado="Cancelada")
    return requiere_aviso
