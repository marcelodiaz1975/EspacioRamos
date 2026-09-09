"""Promedios de valor hora regular por localidad/edificio/unidad, para el
resumen que acompaña a "Valores de los consultorios" (Vista rápida). Es
un promedio simple (no ponderado por horas ni ocupación) de
`Consultorio.ValorHoraRegularActual`, acotado a los consultorios que
pasa quien llama — la pantalla es la que resuelve ese conjunto según sus
propios filtros de Localidad/Edificio/Unidad/Consultorio."""
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


@dataclass
class PromediosValorHora:
    general: float = 0.0
    por_localidad: list[PromedioGrupo] = field(default_factory=list)
    por_edificio: list[PromedioGrupo] = field(default_factory=list)
    por_unidad: list[PromedioGrupo] = field(default_factory=list)


def calcular_promedios_valor_hora_regular(conn: sqlite3.Connection, ids_consultorio: list[int]) -> PromediosValorHora:
    if not ids_consultorio:
        return PromediosValorHora()

    placeholders = ", ".join("?" for _ in ids_consultorio)
    filas = conn.execute(
        f"""
        SELECT c.ValorHoraRegularActual, u.IdUnidad, u.Departamento, e.IdEdificio, e.Nombre AS NombreEdificio,
               e.DomicilioLocalidad
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE c.IdConsultorio IN ({placeholders})
        """,
        ids_consultorio,
    ).fetchall()
    if not filas:
        return PromediosValorHora()

    valores_localidad: dict[str, list[float]] = {}
    valores_edificio: dict[int, list[float]] = {}
    valores_unidad: dict[int, list[float]] = {}
    nombre_edificio_de: dict[int, str] = {}
    localidad_de_edificio: dict[int, str] = {}
    departamento_de_unidad: dict[int, str] = {}
    edificio_de_unidad: dict[int, int] = {}
    total_valores: list[float] = []

    for f in filas:
        valor = f["ValorHoraRegularActual"] or 0.0
        localidad = f["DomicilioLocalidad"] or "(Sin localidad)"
        total_valores.append(valor)
        valores_localidad.setdefault(localidad, []).append(valor)
        valores_edificio.setdefault(f["IdEdificio"], []).append(valor)
        valores_unidad.setdefault(f["IdUnidad"], []).append(valor)
        nombre_edificio_de[f["IdEdificio"]] = f["NombreEdificio"]
        localidad_de_edificio[f["IdEdificio"]] = localidad
        departamento_de_unidad[f["IdUnidad"]] = f["Departamento"]
        edificio_de_unidad[f["IdUnidad"]] = f["IdEdificio"]

    def _promedio(valores: list[float]) -> float:
        return sum(valores) / len(valores) if valores else 0.0

    por_localidad = [
        PromedioGrupo(nombre=loc, localidad=loc, promedio_valor_hora_regular=_promedio(vals))
        for loc, vals in valores_localidad.items()
    ]
    por_edificio = [
        PromedioGrupo(
            nombre=nombre_edificio_de[id_ed], localidad=localidad_de_edificio[id_ed], edificio=nombre_edificio_de[id_ed],
            promedio_valor_hora_regular=_promedio(vals),
        )
        for id_ed, vals in valores_edificio.items()
    ]
    por_unidad = [
        PromedioGrupo(
            nombre=f"{nombre_edificio_de[edificio_de_unidad[id_u]]} - {departamento_de_unidad[id_u]}",
            localidad=localidad_de_edificio[edificio_de_unidad[id_u]],
            edificio=nombre_edificio_de[edificio_de_unidad[id_u]],
            unidad=departamento_de_unidad[id_u],
            promedio_valor_hora_regular=_promedio(vals),
        )
        for id_u, vals in valores_unidad.items()
    ]

    return PromediosValorHora(
        general=_promedio(total_valores),
        por_localidad=sorted(por_localidad, key=lambda g: g.localidad),
        por_edificio=sorted(por_edificio, key=lambda g: (g.localidad, g.edificio)),
        por_unidad=sorted(por_unidad, key=lambda g: (g.localidad, g.edificio, clave_orden_unidad(g.unidad))),
    )
