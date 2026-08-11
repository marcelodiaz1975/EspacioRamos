"""Estadísticas y snapshots mensuales (Etapa 9).

El documento no detalla el contenido de la pantalla FA3 ("Estadísticas")
más allá del nombre — remite a versiones v2/v3 no incluidas, igual que
pasó con otras secciones esta etapa. Lo que sí especifica con precisión
es el modelo de `SnapshotMensual` (sección 3.24, ya en schema.sql) y el
criterio de horario "hábil" para medir ocupación:
`Configuracion.RangosEstadisticasOcupacion` (sección 2, JSON por día —
default L-V 9-21hs / S 9-15hs, domingo no cuenta, igual que la grilla de
disponibilidad). Este módulo calcula el % de ocupación sobre ese rango
horario (general y desglosado por edificio/unidad/consultorio) y arma el
snapshot; el resto del contenido de FA3 queda para cuando se pueda
revisar contra un ejemplo real.

`generar_snapshot` se llama automáticamente al final de
`avance_mes.avanzar_mes` (sección 6.1: "Proceso de avance: genera
snapshot, actualiza saldos..."), con el período que se está cerrando.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from app.negocio.dias import DIAS_SEMANA, fecha_actual
from app.negocio.grilla import calcular_ocupacion_regular
from app.repositorio.registro import obtener_repositorio

RANGO_DEFAULT: dict[str, tuple[float, float]] = {
    "Lunes": (9, 21), "Martes": (9, 21), "Miércoles": (9, 21), "Jueves": (9, 21),
    "Viernes": (9, 21), "Sábado": (9, 15),
}


@dataclass
class OcupacionConsultorio:
    numero: int
    edificio: str
    unidad: str
    porcentaje: float


@dataclass
class OcupacionAgregada:
    nombre: str
    porcentaje: float = 0.0
    _ocupados: int = field(default=0, repr=False)
    _slots: int = field(default=0, repr=False)


@dataclass
class Ocupacion:
    general: float
    por_edificio: dict[int, OcupacionAgregada]
    por_unidad: dict[int, OcupacionAgregada]
    por_consultorio: dict[int, OcupacionConsultorio]


def rango_horas_por_dia(conn: sqlite3.Connection) -> dict[str, tuple[float, float]]:
    cfg = conn.execute(
        "SELECT RangosEstadisticasOcupacion FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    if cfg and cfg["RangosEstadisticasOcupacion"]:
        crudo = json.loads(cfg["RangosEstadisticasOcupacion"])
        return {dia: (rango[0], rango[1]) for dia, rango in crudo.items()}
    return RANGO_DEFAULT


def calcular_ocupacion(conn: sqlite3.Connection, anio: int, mes: int) -> Ocupacion:
    """% de ocupación general y desglosado, contando solo las horas del
    rango "hábil" configurado por día de la semana."""
    rangos = rango_horas_por_dia(conn)
    dias = [d for d in DIAS_SEMANA if d in rangos]
    ocupado = calcular_ocupacion_regular(conn, anio, mes, dias=dias)

    consultorios = conn.execute(
        """
        SELECT c.IdConsultorio, c.NumeroConsultorio, u.IdUnidad, u.Departamento,
               e.IdEdificio, e.Nombre AS NombreEdificio
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        """
    ).fetchall()

    por_edificio: dict[int, OcupacionAgregada] = {}
    por_unidad: dict[int, OcupacionAgregada] = {}
    por_consultorio: dict[int, OcupacionConsultorio] = {}
    total_slots = 0
    total_ocupados = 0

    for c in consultorios:
        slots_c = 0
        ocupados_c = 0
        for dia in dias:
            hora_ini, hora_fin = rangos[dia]
            for h in range(int(hora_ini), int(hora_fin)):
                slots_c += 1
                if ocupado.get((c["IdConsultorio"], dia, h)):
                    ocupados_c += 1
        pct_c = (ocupados_c / slots_c * 100) if slots_c else 0.0
        por_consultorio[c["IdConsultorio"]] = OcupacionConsultorio(
            numero=c["NumeroConsultorio"], edificio=c["NombreEdificio"], unidad=c["Departamento"], porcentaje=pct_c,
        )

        u = por_unidad.setdefault(c["IdUnidad"], OcupacionAgregada(nombre=f"{c['NombreEdificio']} - {c['Departamento']}"))
        u._ocupados += ocupados_c
        u._slots += slots_c

        e = por_edificio.setdefault(c["IdEdificio"], OcupacionAgregada(nombre=c["NombreEdificio"]))
        e._ocupados += ocupados_c
        e._slots += slots_c

        total_slots += slots_c
        total_ocupados += ocupados_c

    for agregado in (*por_edificio.values(), *por_unidad.values()):
        agregado.porcentaje = (agregado._ocupados / agregado._slots * 100) if agregado._slots else 0.0

    general = (total_ocupados / total_slots * 100) if total_slots else 0.0
    return Ocupacion(general=general, por_edificio=por_edificio, por_unidad=por_unidad, por_consultorio=por_consultorio)


def generar_snapshot(
    conn: sqlite3.Connection, periodo: str, *, porcentaje_aumento_aplicado: float | None = None,
) -> int:
    """Persiste un SnapshotMensual con la ocupación y los valores vigentes
    de `periodo` (sección 3.24: "backup de estado" para poder comparar
    meses más adelante)."""
    anio, mes = (int(p) for p in periodo.split("-"))
    ocupacion = calcular_ocupacion(conn, anio, mes)

    valores_consultorios = {
        str(c["IdConsultorio"]): c["ValorHoraRegularActual"]
        for c in conn.execute("SELECT IdConsultorio, ValorHoraRegularActual FROM Consultorio").fetchall()
    }

    repo = obtener_repositorio(conn, "SnapshotMensual")
    return repo.crear(
        Periodo=periodo,
        FechaGeneracion=fecha_actual(conn).isoformat(),
        PorcentajeOcupacionGeneral=ocupacion.general,
        PorOcupEdificio=json.dumps({e.nombre: e.porcentaje for e in ocupacion.por_edificio.values()}),
        PorOcupUnidad=json.dumps({u.nombre: u.porcentaje for u in ocupacion.por_unidad.values()}),
        PorOcupConsultorio=json.dumps({
            f"{c.edificio} - {c.unidad} - {c.numero}": c.porcentaje for c in ocupacion.por_consultorio.values()
        }),
        ValoresConsultorios=json.dumps(valores_consultorios),
        PorcentajeAumentoAplicado=porcentaje_aumento_aplicado,
    )
