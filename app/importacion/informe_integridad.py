"""Informe de integridad post-importación (FA5): la carga masiva por
planilla no pasa por las mismas validaciones que la pantalla de Reservas
(sección 3.9) ni impone unicidad de código de profesional — por diseño,
para no frenar una importación grande por un dato puntual. Este módulo
corre después de importar y junta, sin bloquear nada, los casos que
convendría revisar a mano:

- Profesionales con el mismo IdCodigo: como el código se usa para resolver
  referencias en la planilla (reservas, placas, etc.), un duplicado hace
  que esas referencias siempre resuelvan al primero de los dos.
- Reservas regulares que se superponen en el mismo consultorio/día/horario
  entre profesionales sin relación de equipo — reusa
  app.negocio.reservas.verificar_conflictos_regular (la misma regla que
  aplica la pantalla de Reservas al cargar una reserva a mano) para que el
  criterio de "conflicto real" sea uno solo en todo el sistema."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from app.negocio.reservas import verificar_conflictos_regular


@dataclass
class CodigoDuplicado:
    codigo: str
    profesionales: list[tuple[int, str]]  # (IdProfesional, Apellido)


@dataclass
class ReservaSuperpuesta:
    id_consultorio: int
    dia_semana: str
    reserva_a: sqlite3.Row
    reserva_b: sqlite3.Row
    mensaje: str


@dataclass
class InformeIntegridad:
    codigos_duplicados: list[CodigoDuplicado] = field(default_factory=list)
    reservas_superpuestas: list[ReservaSuperpuesta] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.codigos_duplicados) + len(self.reservas_superpuestas)


def _codigos_duplicados(conn: sqlite3.Connection) -> list[CodigoDuplicado]:
    codigos = conn.execute(
        "SELECT IdCodigo FROM Profesional WHERE IdCodigo IS NOT NULL AND IdCodigo != '' "
        "GROUP BY IdCodigo HAVING COUNT(*) > 1"
    ).fetchall()
    resultado = []
    for fila in codigos:
        profesionales = conn.execute(
            "SELECT IdProfesional, Apellido FROM Profesional WHERE IdCodigo = ? ORDER BY IdProfesional",
            (fila["IdCodigo"],),
        ).fetchall()
        resultado.append(CodigoDuplicado(
            codigo=fila["IdCodigo"],
            profesionales=[(p["IdProfesional"], p["Apellido"]) for p in profesionales],
        ))
    return resultado


def _reservas_superpuestas(conn: sqlite3.Connection) -> list[ReservaSuperpuesta]:
    reservas = conn.execute("SELECT * FROM ReservaRegular").fetchall()
    vistos: set[tuple[int, int]] = set()
    resultado = []
    for r in reservas:
        conflictos = verificar_conflictos_regular(
            conn,
            id_consultorio=r["IdConsultorio"], dia_semana=r["DiaSemana"],
            hora_inicio=r["HoraInicio"], hora_fin=r["HoraFin"],
            vigencia_inicio=r["VigenciaInicio"], vigencia_fin=r["VigenciaFin"],
            id_profesional=r["IdProfesional"], excluir_id=r["IdReservaRegular"],
        )
        for c in conflictos:
            if not c.bloqueante:
                continue
            otro = c.reserva_existente
            par = tuple(sorted((r["IdReservaRegular"], otro["IdReservaRegular"])))
            if par in vistos:
                continue
            vistos.add(par)
            resultado.append(ReservaSuperpuesta(
                id_consultorio=r["IdConsultorio"], dia_semana=r["DiaSemana"],
                reserva_a=r, reserva_b=otro, mensaje=c.mensaje,
            ))
    return resultado


def generar_informe_integridad(conn: sqlite3.Connection) -> InformeIntegridad:
    return InformeIntegridad(
        codigos_duplicados=_codigos_duplicados(conn),
        reservas_superpuestas=_reservas_superpuestas(conn),
    )
