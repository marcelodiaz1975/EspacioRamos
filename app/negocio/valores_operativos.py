"""Promedios de valor hora regular y hora aislada por localidad/edificio/
unidad, para el resumen que acompaña a "Valores de los consultorios"
(Vista rápida). Son promedios simples (no ponderados por horas ni
ocupación) de `Consultorio.ValorHoraRegularActual`/`ValorHoraAisladaActual`,
acotados a los consultorios que pasa quien llama — la pantalla es la que
resuelve ese conjunto según sus propios filtros de Localidad/Edificio/
Unidad/Consultorio."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from app.pdf.estilos import clave_orden_unidad


@dataclass
class PromedioGrupo:
    """Un renglón agregado (localidad, edificio, o unidad). `localidad`/
    `edificio`/`unidad` van poblados solo hasta el nivel que corresponde
    — mismo criterio que `EstadisticaGrupo`."""
    nombre: str
    localidad: str | None = None
    edificio: str | None = None
    unidad: str | None = None
    promedio_valor_hora_regular: float = 0.0
    promedio_valor_hora_aislada: float = 0.0


@dataclass
class PromediosValorHora:
    general_regular: float = 0.0
    general_aislada: float = 0.0
    por_localidad: list[PromedioGrupo] = field(default_factory=list)
    por_edificio: list[PromedioGrupo] = field(default_factory=list)
    por_unidad: list[PromedioGrupo] = field(default_factory=list)


def calcular_promedios_valor_hora(conn: sqlite3.Connection, ids_consultorio: list[int]) -> PromediosValorHora:
    if not ids_consultorio:
        return PromediosValorHora()

    placeholders = ", ".join("?" for _ in ids_consultorio)
    filas = conn.execute(
        f"""
        SELECT c.ValorHoraRegularActual, c.ValorHoraAisladaActual, u.IdUnidad, u.Departamento, e.IdEdificio,
               e.Nombre AS NombreEdificio, e.DomicilioLocalidad
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE c.IdConsultorio IN ({placeholders})
        """,
        ids_consultorio,
    ).fetchall()
    if not filas:
        return PromediosValorHora()

    regular_localidad: dict[str, list[float]] = {}
    regular_edificio: dict[int, list[float]] = {}
    regular_unidad: dict[int, list[float]] = {}
    aislada_localidad: dict[str, list[float]] = {}
    aislada_edificio: dict[int, list[float]] = {}
    aislada_unidad: dict[int, list[float]] = {}
    nombre_edificio_de: dict[int, str] = {}
    localidad_de_edificio: dict[int, str] = {}
    departamento_de_unidad: dict[int, str] = {}
    edificio_de_unidad: dict[int, int] = {}
    total_regular: list[float] = []
    total_aislada: list[float] = []

    for f in filas:
        valor_regular = f["ValorHoraRegularActual"] or 0.0
        valor_aislada = f["ValorHoraAisladaActual"] or 0.0
        localidad = f["DomicilioLocalidad"] or "(Sin localidad)"
        total_regular.append(valor_regular)
        total_aislada.append(valor_aislada)
        regular_localidad.setdefault(localidad, []).append(valor_regular)
        regular_edificio.setdefault(f["IdEdificio"], []).append(valor_regular)
        regular_unidad.setdefault(f["IdUnidad"], []).append(valor_regular)
        aislada_localidad.setdefault(localidad, []).append(valor_aislada)
        aislada_edificio.setdefault(f["IdEdificio"], []).append(valor_aislada)
        aislada_unidad.setdefault(f["IdUnidad"], []).append(valor_aislada)
        nombre_edificio_de[f["IdEdificio"]] = f["NombreEdificio"]
        localidad_de_edificio[f["IdEdificio"]] = localidad
        departamento_de_unidad[f["IdUnidad"]] = f["Departamento"]
        edificio_de_unidad[f["IdUnidad"]] = f["IdEdificio"]

    def _promedio(valores: list[float]) -> float:
        return sum(valores) / len(valores) if valores else 0.0

    por_localidad = [
        PromedioGrupo(
            nombre=loc, localidad=loc,
            promedio_valor_hora_regular=_promedio(regular_localidad[loc]),
            promedio_valor_hora_aislada=_promedio(aislada_localidad[loc]),
        )
        for loc in regular_localidad
    ]
    por_edificio = [
        PromedioGrupo(
            nombre=nombre_edificio_de[id_ed], localidad=localidad_de_edificio[id_ed], edificio=nombre_edificio_de[id_ed],
            promedio_valor_hora_regular=_promedio(regular_edificio[id_ed]),
            promedio_valor_hora_aislada=_promedio(aislada_edificio[id_ed]),
        )
        for id_ed in regular_edificio
    ]
    por_unidad = [
        PromedioGrupo(
            nombre=f"{nombre_edificio_de[edificio_de_unidad[id_u]]} - {departamento_de_unidad[id_u]}",
            localidad=localidad_de_edificio[edificio_de_unidad[id_u]],
            edificio=nombre_edificio_de[edificio_de_unidad[id_u]],
            unidad=departamento_de_unidad[id_u],
            promedio_valor_hora_regular=_promedio(regular_unidad[id_u]),
            promedio_valor_hora_aislada=_promedio(aislada_unidad[id_u]),
        )
        for id_u in regular_unidad
    ]

    return PromediosValorHora(
        general_regular=_promedio(total_regular),
        general_aislada=_promedio(total_aislada),
        por_localidad=sorted(por_localidad, key=lambda g: g.localidad),
        por_edificio=sorted(por_edificio, key=lambda g: (g.localidad, g.edificio)),
        por_unidad=sorted(por_unidad, key=lambda g: (g.localidad, g.edificio, clave_orden_unidad(g.unidad))),
    )
