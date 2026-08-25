"""Estadísticas por unidad/edificio para la sección "Estadísticas" de la
pantalla Grilla operativa (miscelánea, ago-2026, punto 21).

Siempre usa `periodo_actual(conn)` — no el período que se esté mirando
en la grilla, que puede ser uno futuro para ver disponibilidad (así lo
confirmó el usuario: las estadísticas van siempre por el mes real en
curso del sistema).

Los subtotales en pesos reutilizan `calcular_liquidacion` (el motor real
de la liquidación mensual, con sus descuentos por horas semanales/
ausencias/feriados) en vez de un cálculo simplificado de horas × valor,
para que coincidan con lo que de verdad se factura. `calcular_liquidacion`
da el total regular del profesional sin desglose por consultorio: cuando
reserva en más de uno a la vez, ese total se reparte proporcional a las
horas brutas de cada consultorio (sin descuentos) — en el caso normal de
un solo consultorio el reparto es exacto, no una aproximación. Las
aisladas sí vienen con su propio consultorio ya identificado en
`ItemAislada`, sin necesidad de repartir nada. Los pagos del período se
reparten con el mismo criterio de proporción.

Categoría B nunca se liquida (`id_profesional_liquidable` da None): sus
horas cuentan para ocupación y para "horas reservadas", pero el
subtotal en pesos les queda en $0, como corresponde.

No se persiste ningún subtotal acá: se recalcula cada vez que se abre o
refresca la sección — evita mantener sincronizado un caché contra los
muchos puntos que lo podrían desactualizar (reservas, pagos, ausencias,
vacaciones, cambios de valores, avance de mes...), y el volumen de datos
involucrado (profesionales con algo reservado en la unidad filtrada) es
chico."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.negocio.dias import fecha_a_dia_semana, parsear_periodo, periodo_actual, primer_dia_mes, ultimo_dia_mes
from app.negocio.estadisticas import calcular_ocupacion
from app.negocio.liquidaciones import calcular_liquidacion, id_profesional_liquidable


@dataclass
class EstadisticaGrupo:
    """Un renglón agregado (unidad, edificio, o el total general)."""
    id: int | None
    nombre: str
    porcentaje_ocupacion: float = 0.0
    horas_regulares: float = 0.0
    horas_aisladas: float = 0.0
    subtotal_regulares: float = 0.0
    subtotal_aisladas: float = 0.0
    pagos_atribuidos: float = 0.0

    @property
    def falta_cobrar(self) -> float:
        return self.subtotal_regulares + self.subtotal_aisladas - self.pagos_atribuidos


@dataclass
class EstadisticasOperativas:
    periodo: str
    por_unidad: list[EstadisticaGrupo] = field(default_factory=list)
    por_edificio: list[EstadisticaGrupo] = field(default_factory=list)
    total: EstadisticaGrupo = field(default_factory=lambda: EstadisticaGrupo(id=None, nombre="Total"))


def _dias_ocurrencia(desde: date, hasta: date, dia_semana: str) -> int:
    if desde > hasta:
        return 0
    dias = 0
    cursor = desde
    while cursor <= hasta:
        if fecha_a_dia_semana(cursor) == dia_semana:
            dias += 1
        cursor += timedelta(days=1)
    return dias


def _horas_regulares_por_consultorio(
    conn: sqlite3.Connection, primer_dia: date, ultimo_dia: date, ids_profesional: list[int] | None = None,
    ids_consultorio: list[int] | None = None,
) -> dict[int, float]:
    """{IdConsultorio: horas totales reservadas en forma regular dentro
    del período} — cuenta las horas programadas tal cual (sin descontar
    ausencias/feriados/vacaciones), es la base para repartir el
    subtotal en pesos proporcionalmente entre consultorios."""
    sql = "SELECT * FROM ReservaRegular WHERE VigenciaInicio <= ? AND (VigenciaFin IS NULL OR VigenciaFin >= ?)"
    parametros: list = [ultimo_dia.isoformat(), primer_dia.isoformat()]
    if ids_profesional:
        placeholders = ", ".join("?" for _ in ids_profesional)
        sql += f" AND IdProfesional IN ({placeholders})"
        parametros.extend(ids_profesional)
    if ids_consultorio:
        placeholders = ", ".join("?" for _ in ids_consultorio)
        sql += f" AND IdConsultorio IN ({placeholders})"
        parametros.extend(ids_consultorio)

    horas: dict[int, float] = {}
    for r in conn.execute(sql, parametros).fetchall():
        desde = max(primer_dia, date.fromisoformat(r["VigenciaInicio"]))
        hasta = min(ultimo_dia, date.fromisoformat(r["VigenciaFin"]) if r["VigenciaFin"] else ultimo_dia)
        ocurrencias = _dias_ocurrencia(desde, hasta, r["DiaSemana"])
        if ocurrencias:
            horas[r["IdConsultorio"]] = horas.get(r["IdConsultorio"], 0.0) + ocurrencias * (r["HoraFin"] - r["HoraInicio"])
    return horas


def _horas_aisladas_por_consultorio(
    conn: sqlite3.Connection, periodo: str, ids_consultorio: list[int] | None = None,
) -> dict[int, float]:
    sql = "SELECT * FROM ReservaAislada WHERE Estado = 'Confirmada' AND Fecha LIKE ?"
    parametros: list = [f"{periodo}-%"]
    if ids_consultorio:
        placeholders = ", ".join("?" for _ in ids_consultorio)
        sql += f" AND IdConsultorio IN ({placeholders})"
        parametros.extend(ids_consultorio)

    horas: dict[int, float] = {}
    for r in conn.execute(sql, parametros).fetchall():
        horas[r["IdConsultorio"]] = horas.get(r["IdConsultorio"], 0.0) + (r["HoraFin"] - r["HoraInicio"])
    return horas


def _profesionales_liquidables_en_alcance(conn: sqlite3.Connection, periodo: str, ids_consultorio: list[int]) -> set[int]:
    placeholders = ", ".join("?" for _ in ids_consultorio)
    ids_profesional = {
        f["IdProfesional"] for f in conn.execute(
            f"SELECT DISTINCT IdProfesional FROM ReservaRegular WHERE IdConsultorio IN ({placeholders})",
            ids_consultorio,
        ).fetchall()
    }
    ids_profesional |= {
        f["IdProfesional"] for f in conn.execute(
            f"SELECT DISTINCT IdProfesional FROM ReservaAislada WHERE IdConsultorio IN ({placeholders}) "
            f"AND Estado = 'Confirmada' AND Fecha LIKE ?",
            (*ids_consultorio, f"{periodo}-%"),
        ).fetchall()
    }
    liquidables = {id_profesional_liquidable(conn, p) for p in ids_profesional}
    liquidables.discard(None)
    return liquidables


def _pagos_del_periodo(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> float:
    fila = conn.execute(
        "SELECT COALESCE(SUM(Monto), 0) AS total FROM HistorialPagos WHERE IdProfesional = ? AND PeriodoImputado = ?",
        (id_profesional, periodo),
    ).fetchone()
    return fila["total"] or 0.0


def calcular_estadisticas_operativas(conn: sqlite3.Connection, ids_unidad: list[int]) -> EstadisticasOperativas:
    periodo = periodo_actual(conn)
    if not ids_unidad:
        return EstadisticasOperativas(periodo=periodo)

    anio, mes = parsear_periodo(periodo)
    primer_dia, ultimo_dia = primer_dia_mes(anio, mes), ultimo_dia_mes(anio, mes)

    placeholders = ", ".join("?" for _ in ids_unidad)
    consultorios = conn.execute(
        f"""
        SELECT c.IdConsultorio, u.IdUnidad, u.Departamento, e.IdEdificio, e.Nombre AS NombreEdificio
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        WHERE u.IdUnidad IN ({placeholders})
        """,
        ids_unidad,
    ).fetchall()
    id_unidad_de = {c["IdConsultorio"]: c["IdUnidad"] for c in consultorios}
    ids_consultorio = list(id_unidad_de)

    grupos_unidad: dict[int, EstadisticaGrupo] = {
        c["IdUnidad"]: EstadisticaGrupo(id=c["IdUnidad"], nombre=f"{c['NombreEdificio']} - {c['Departamento']}")
        for c in consultorios
    }
    id_edificio_de_unidad = {c["IdUnidad"]: c["IdEdificio"] for c in consultorios}
    nombre_edificio_de = {c["IdEdificio"]: c["NombreEdificio"] for c in consultorios}

    if ids_consultorio:
        horas_reg = _horas_regulares_por_consultorio(conn, primer_dia, ultimo_dia, ids_consultorio=ids_consultorio)
        horas_ais = _horas_aisladas_por_consultorio(conn, periodo, ids_consultorio=ids_consultorio)
        for id_consultorio, horas in horas_reg.items():
            grupos_unidad[id_unidad_de[id_consultorio]].horas_regulares += horas
        for id_consultorio, horas in horas_ais.items():
            grupos_unidad[id_unidad_de[id_consultorio]].horas_aisladas += horas

    ocupacion = calcular_ocupacion(conn, anio, mes)
    for id_unidad, grupo in grupos_unidad.items():
        agregado = ocupacion.por_unidad.get(id_unidad)
        grupo.porcentaje_ocupacion = agregado.porcentaje if agregado else 0.0

    for id_r in _profesionales_liquidables_en_alcance(conn, periodo, ids_consultorio):
        liq = calcular_liquidacion(conn, id_profesional=id_r, periodo=periodo)
        horas_reg_r = _horas_regulares_por_consultorio(conn, primer_dia, ultimo_dia, ids_profesional=[id_r])
        total_horas_r = sum(horas_reg_r.values())
        pagos_r = _pagos_del_periodo(conn, id_r, periodo)
        total_regular_aislada_r = liq.subtotal_reserva + liq.total_aisladas_mes_en_curso

        subtotal_regular_por_unidad: dict[int, float] = {}
        if total_horas_r:
            for id_consultorio, horas in horas_reg_r.items():
                id_unidad = id_unidad_de.get(id_consultorio)
                if id_unidad is None:
                    continue
                monto = liq.subtotal_reserva * (horas / total_horas_r)
                subtotal_regular_por_unidad[id_unidad] = subtotal_regular_por_unidad.get(id_unidad, 0.0) + monto
                grupos_unidad[id_unidad].subtotal_regulares += monto

        subtotal_aislada_por_unidad: dict[int, float] = {}
        for item in liq.aisladas_mes_en_curso:
            id_unidad = id_unidad_de.get(item.id_consultorio)
            if id_unidad is None:
                continue
            subtotal_aislada_por_unidad[id_unidad] = subtotal_aislada_por_unidad.get(id_unidad, 0.0) + item.monto
            grupos_unidad[id_unidad].subtotal_aisladas += item.monto

        if pagos_r and total_regular_aislada_r:
            ids_unidad_con_monto = set(subtotal_regular_por_unidad) | set(subtotal_aislada_por_unidad)
            for id_unidad in ids_unidad_con_monto:
                monto_unidad = subtotal_regular_por_unidad.get(id_unidad, 0.0) + subtotal_aislada_por_unidad.get(id_unidad, 0.0)
                grupos_unidad[id_unidad].pagos_atribuidos += pagos_r * (monto_unidad / total_regular_aislada_r)

    grupos_edificio: dict[int, EstadisticaGrupo] = {}
    for id_unidad, grupo in grupos_unidad.items():
        id_edificio = id_edificio_de_unidad[id_unidad]
        ge = grupos_edificio.setdefault(id_edificio, EstadisticaGrupo(id=id_edificio, nombre=nombre_edificio_de[id_edificio]))
        ge.horas_regulares += grupo.horas_regulares
        ge.horas_aisladas += grupo.horas_aisladas
        ge.subtotal_regulares += grupo.subtotal_regulares
        ge.subtotal_aisladas += grupo.subtotal_aisladas
        ge.pagos_atribuidos += grupo.pagos_atribuidos

    for id_edificio, ge in grupos_edificio.items():
        agregado = ocupacion.por_edificio.get(id_edificio)
        ge.porcentaje_ocupacion = agregado.porcentaje if agregado else 0.0

    total = EstadisticaGrupo(id=None, nombre="Total")
    for grupo in grupos_unidad.values():
        total.horas_regulares += grupo.horas_regulares
        total.horas_aisladas += grupo.horas_aisladas
        total.subtotal_regulares += grupo.subtotal_regulares
        total.subtotal_aisladas += grupo.subtotal_aisladas
        total.pagos_atribuidos += grupo.pagos_atribuidos

    # % general ponderado por slots disponibles (no por horas reservadas,
    # que sobrepesaría a las unidades ya más ocupadas) — los mismos
    # contadores que ya calculó `calcular_ocupacion` por unidad.
    slots_totales = sum(ocupacion.por_unidad[id_unidad]._slots for id_unidad in grupos_unidad)
    ocupados_totales = sum(ocupacion.por_unidad[id_unidad]._ocupados for id_unidad in grupos_unidad)
    total.porcentaje_ocupacion = (ocupados_totales / slots_totales * 100) if slots_totales else 0.0

    return EstadisticasOperativas(
        periodo=periodo,
        por_unidad=sorted(grupos_unidad.values(), key=lambda g: g.nombre),
        por_edificio=sorted(grupos_edificio.values(), key=lambda g: g.nombre),
        total=total,
    )
