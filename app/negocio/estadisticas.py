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
snapshot.

`generar_snapshot` se llama automáticamente al final de
`avance_mes.avanzar_mes` (sección 6.1: "Proceso de avance: genera
snapshot, actualiza saldos..."), con el período que se está cerrando.

Revisión "uno por uno" de la pantalla (ver CLAUDE.md, sección
"Estadísticas"): además de la ocupación, el resto de las funciones de
este módulo arman las filas de las dos solapas de esa pantalla
("Historial general", que surge de lo guardado en SnapshotMensual más el
mes en curso calculado en vivo, y "Estadísticas varias", 100% en vivo y
filtrable por localidad/edificio/unidad/consultorio). Dos decisiones de
la clienta a tener siempre presentes:

- "Monto por horas regulares"/"Monto por horas aisladas" son el monto
  real facturado, pero a nivel BRUTO (antes de descuentos por volumen de
  horas semanales y demás ajustes de `app.negocio.liquidaciones`): esos
  ajustes se calculan por profesional sobre el total de SUS reservas en
  todos los consultorios del sistema, así que no hay forma de repartirlos
  de vuelta a un edificio/unidad/consultorio puntual sin inventar un
  criterio de prorrateo que nadie pidió. `LiquidacionEmitida.MontoGenerado`
  tampoco sirve como fuente: es un total ya combinado (bruto regular +
  aisladas + cargos especiales + ajustes, todo junto), no separable en
  categorías.
- "Horas regulares semanales" de un período NO es un promedio por
  profesional: es un promedio ponderado día a día dentro del período
  (ver `horas_regulares_semanales_promedio`), para que una liberación de
  horas a mitad de mes pese solo la mitad de los días — ejemplo de la
  clienta: 30hs reservadas la primera quincena de un mes de 30 días, se
  liberan 10 y quedan 20hs la segunda quincena, promedio del mes = 25hs.
- Las cantidades de Localidades/Edificios/Unidades/Consultorios de
  cualquier fila (pasada o presente) son siempre el conteo ACTUAL del
  sistema (o el del alcance elegido en "Estadísticas varias") — ninguna
  de esas tablas guarda de baja lógica ni fecha de alta, así que no hay
  forma de reconstruir cuántas había en un período anterior.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.negocio.dias import (
    DIAS_SEMANA,
    fecha_a_dia_semana,
    fecha_actual,
    parsear_periodo,
    periodo_actual,
    periodo_anterior,
    primer_dia_mes,
    ultimo_dia_mes,
)
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


def calcular_ocupacion(
    conn: sqlite3.Connection, anio: int, mes: int, ids_consultorio: list[int] | None = None,
) -> Ocupacion:
    """% de ocupación general y desglosado, contando solo las horas del
    rango "hábil" configurado por día de la semana. `ids_consultorio`
    (usado por "Estadísticas varias" para acotar a un alcance puntual)
    restringe el cálculo a esos consultorios; `None` es todo el sistema,
    `[]` no calcula nada (0% en vez de dividir por cero)."""
    rangos = rango_horas_por_dia(conn)
    dias = [d for d in DIAS_SEMANA if d in rangos]
    ocupado = calcular_ocupacion_regular(conn, anio, mes, dias=dias)

    sql = (
        "SELECT c.IdConsultorio, c.NumeroConsultorio, u.IdUnidad, u.Departamento, "
        "       e.IdEdificio, e.Nombre AS NombreEdificio "
        "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio"
    )
    if ids_consultorio is None:
        consultorios = conn.execute(sql).fetchall()
    elif not ids_consultorio:
        consultorios = []
    else:
        placeholders = ", ".join("?" for _ in ids_consultorio)
        consultorios = conn.execute(f"{sql} WHERE c.IdConsultorio IN ({placeholders})", ids_consultorio).fetchall()

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
    anio, mes = parsear_periodo(periodo)
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
        HorasRegularesSemanales=horas_regulares_semanales_promedio(conn, anio, mes),
        MontoHorasRegulares=monto_bruto_regular_periodo(conn, anio, mes),
        MontoHorasAisladas=monto_bruto_aislada_periodo(conn, anio, mes),
    )


# --------------------------------------------------------------------------
# Pantalla Estadísticas (revisión "uno por uno"): historial general y
# estadísticas varias — ver el docstring del módulo para las decisiones de
# la clienta sobre cómo se calcula cada columna.
# --------------------------------------------------------------------------


def _horas_regulares_semanales_en_fecha(
    conn: sqlite3.Connection, fecha_iso: str, ids_consultorio: list[int] | None = None,
) -> float:
    """Total de horas semanales reservadas (ReservaRegular vigente a esa
    fecha), sin distinguir profesional — la "foto" de un día puntual que
    `horas_regulares_semanales_promedio` promedia día a día."""
    if ids_consultorio is not None and not ids_consultorio:
        return 0.0
    sql = (
        "SELECT HoraInicio, HoraFin FROM ReservaRegular "
        "WHERE VigenciaInicio <= ? AND (VigenciaFin IS NULL OR VigenciaFin >= ?)"
    )
    parametros: list = [fecha_iso, fecha_iso]
    if ids_consultorio is not None:
        sql += f" AND IdConsultorio IN ({', '.join('?' for _ in ids_consultorio)})"
        parametros.extend(ids_consultorio)
    filas = conn.execute(sql, parametros).fetchall()
    return sum(f["HoraFin"] - f["HoraInicio"] for f in filas)


def horas_regulares_semanales_promedio(
    conn: sqlite3.Connection, anio: int, mes: int, ids_consultorio: list[int] | None = None,
) -> float:
    """Promedio ponderado día a día de las horas regulares semanales
    reservadas durante el período (no un promedio por profesional): si a
    mitad de mes se liberan horas, esos días pesan con el valor más bajo
    el resto del mes, en vez de promediarse por cantidad de profesionales
    o de reservas — ejemplo de la clienta en el docstring del módulo."""
    dia = primer_dia_mes(anio, mes)
    ultimo = ultimo_dia_mes(anio, mes)
    total = 0.0
    cantidad_dias = 0
    while dia <= ultimo:
        total += _horas_regulares_semanales_en_fecha(conn, dia.isoformat(), ids_consultorio)
        cantidad_dias += 1
        dia += timedelta(days=1)
    return total / cantidad_dias if cantidad_dias else 0.0


def monto_bruto_regular_periodo(
    conn: sqlite3.Connection, anio: int, mes: int, ids_consultorio: list[int] | None = None,
) -> float:
    """Monto real facturado por horas regulares en el período, a nivel
    BRUTO (antes de descuentos por volumen y demás ajustes de
    `app.negocio.liquidaciones`, que se calculan por profesional sobre
    todas sus reservas del sistema y no se pueden repartir de vuelta a un
    alcance puntual — ver el docstring del módulo). Día por día, a los
    valores vigentes de cada consultorio (mismo criterio que
    `app.negocio.valores.valor_regular_por_rango_dias`, acá sin acotar
    por profesional sino por consultorio)."""
    if ids_consultorio is not None and not ids_consultorio:
        return 0.0
    sql = (
        "SELECT rr.HoraInicio, rr.HoraFin, c.ValorHoraRegularActual "
        "FROM ReservaRegular rr JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio "
        "WHERE rr.DiaSemana = ? AND rr.VigenciaInicio <= ? AND (rr.VigenciaFin IS NULL OR rr.VigenciaFin >= ?)"
    )
    if ids_consultorio is not None:
        sql += f" AND rr.IdConsultorio IN ({', '.join('?' for _ in ids_consultorio)})"

    dia = primer_dia_mes(anio, mes)
    ultimo = ultimo_dia_mes(anio, mes)
    total = 0.0
    while dia <= ultimo:
        fecha_iso = dia.isoformat()
        parametros: list = [fecha_a_dia_semana(dia), fecha_iso, fecha_iso]
        if ids_consultorio is not None:
            parametros.extend(ids_consultorio)
        for f in conn.execute(sql, parametros).fetchall():
            total += (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"]
        dia += timedelta(days=1)
    return total


def monto_bruto_aislada_periodo(
    conn: sqlite3.Connection, anio: int, mes: int, ids_consultorio: list[int] | None = None,
) -> float:
    """Monto real facturado por horas aisladas confirmadas del período, a
    valores vigentes — mismo criterio "bruto" que `monto_bruto_regular_
    periodo` (acá no hay descuento por volumen para restar: las aisladas
    no entran en ese esquema, así que esto ya es el monto final de esa
    categoría, no una aproximación)."""
    if ids_consultorio is not None and not ids_consultorio:
        return 0.0
    parametros: list = [primer_dia_mes(anio, mes).isoformat(), ultimo_dia_mes(anio, mes).isoformat()]
    sql = (
        "SELECT ra.HoraInicio, ra.HoraFin, c.ValorHoraAisladaActual "
        "FROM ReservaAislada ra JOIN Consultorio c ON c.IdConsultorio = ra.IdConsultorio "
        "WHERE ra.Estado = 'Confirmada' AND ra.Fecha BETWEEN ? AND ?"
    )
    if ids_consultorio is not None:
        sql += f" AND ra.IdConsultorio IN ({', '.join('?' for _ in ids_consultorio)})"
        parametros.extend(ids_consultorio)
    filas = conn.execute(sql, parametros).fetchall()
    return sum((f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraAisladaActual"] for f in filas)


def _ids_consultorio_del_alcance(
    conn: sqlite3.Connection, *,
    id_localidad: int | None = None, id_edificio: int | None = None,
    id_unidad: int | None = None, id_consultorio: int | None = None,
) -> list[int] | None:
    """Consultorios del alcance más específico elegido ("el más específico
    manda", mismo criterio que la cascada de Gestor de archivos) — `None`
    si no se eligió ningún filtro de ubicación (todo el sistema)."""
    if id_consultorio is not None:
        return [id_consultorio]
    if id_unidad is not None:
        filas = conn.execute("SELECT IdConsultorio FROM Consultorio WHERE IdUnidad = ?", (id_unidad,)).fetchall()
        return [f["IdConsultorio"] for f in filas]
    if id_edificio is not None:
        filas = conn.execute(
            "SELECT c.IdConsultorio FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
            "WHERE u.IdEdificio = ?",
            (id_edificio,),
        ).fetchall()
        return [f["IdConsultorio"] for f in filas]
    if id_localidad is not None:
        filas = conn.execute(
            "SELECT c.IdConsultorio FROM Consultorio c "
            "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "WHERE e.IdLocalidad = ?",
            (id_localidad,),
        ).fetchall()
        return [f["IdConsultorio"] for f in filas]
    return None


def conteo_entidades(
    conn: sqlite3.Connection, *,
    id_localidad: int | None = None, id_edificio: int | None = None,
    id_unidad: int | None = None, id_consultorio: int | None = None,
) -> tuple[int, int, int, int]:
    """(Localidades, Edificios, Unidades, Consultorios) del alcance más
    específico elegido — sin alcance, el conteo actual de todo el
    sistema. Ninguna de estas tablas guarda de baja lógica ni fecha de
    alta, así que esto es siempre el conteo ACTUAL, nunca uno histórico
    (ver el docstring del módulo)."""
    if id_consultorio is not None:
        return 1, 1, 1, 1
    if id_unidad is not None:
        cant = conn.execute("SELECT COUNT(*) AS n FROM Consultorio WHERE IdUnidad = ?", (id_unidad,)).fetchone()["n"]
        return 1, 1, 1, cant
    if id_edificio is not None:
        cant_unidades = conn.execute(
            "SELECT COUNT(*) AS n FROM Unidad WHERE IdEdificio = ?", (id_edificio,)
        ).fetchone()["n"]
        cant_consultorios = conn.execute(
            "SELECT COUNT(*) AS n FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
            "WHERE u.IdEdificio = ?",
            (id_edificio,),
        ).fetchone()["n"]
        return 1, 1, cant_unidades, cant_consultorios
    if id_localidad is not None:
        cant_edificios = conn.execute(
            "SELECT COUNT(*) AS n FROM Edificio WHERE IdLocalidad = ?", (id_localidad,)
        ).fetchone()["n"]
        cant_unidades = conn.execute(
            "SELECT COUNT(*) AS n FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "WHERE e.IdLocalidad = ?",
            (id_localidad,),
        ).fetchone()["n"]
        cant_consultorios = conn.execute(
            "SELECT COUNT(*) AS n FROM Consultorio c "
            "JOIN Unidad u ON u.IdUnidad = c.IdUnidad JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
            "WHERE e.IdLocalidad = ?",
            (id_localidad,),
        ).fetchone()["n"]
        return 1, cant_edificios, cant_unidades, cant_consultorios
    return (
        conn.execute("SELECT COUNT(*) AS n FROM Localidad").fetchone()["n"],
        conn.execute("SELECT COUNT(*) AS n FROM Edificio").fetchone()["n"],
        conn.execute("SELECT COUNT(*) AS n FROM Unidad").fetchone()["n"],
        conn.execute("SELECT COUNT(*) AS n FROM Consultorio").fetchone()["n"],
    )


@dataclass
class FilaEstadistica:
    """Una fila de cualquiera de las dos solapas de la pantalla
    Estadísticas — mismas 11 columnas en las dos, con distinta fuente de
    datos y filtros (ver el docstring del módulo)."""
    periodo: str  # "AAAA" o "AAAA-MM" según el modo
    ocupacion_pct: float | None
    horas_regulares_semanales: float | None
    variacion_horas: float | None
    monto_regular: float | None
    monto_aislada: float | None
    cant_localidades: int
    cant_edificios: int
    cant_unidades: int
    cant_consultorios: int

    @property
    def monto_total(self) -> float | None:
        if self.monto_regular is None and self.monto_aislada is None:
            return None
        return (self.monto_regular or 0.0) + (self.monto_aislada or 0.0)


def _periodo_mas_antiguo_con_datos(conn: sqlite3.Connection) -> str:
    """Primer período con alguna reserva (regular o aislada) cargada —
    de ahí en más "Estadísticas varias" arma una fila por período sin
    filtro; si el sistema todavía no tiene ninguna reserva, el único
    período con sentido es el actual."""
    candidatos: list[str] = []
    fila = conn.execute("SELECT MIN(VigenciaInicio) AS f FROM ReservaRegular").fetchone()
    if fila and fila["f"]:
        candidatos.append(fila["f"])
    fila = conn.execute("SELECT MIN(Fecha) AS f FROM ReservaAislada").fetchone()
    if fila and fila["f"]:
        candidatos.append(fila["f"])
    if not candidatos:
        return periodo_actual(conn)
    fecha_min = min(date.fromisoformat(f) for f in candidatos)
    return f"{fecha_min.year:04d}-{fecha_min.month:02d}"


def _periodos_para_filtro(conn: sqlite3.Connection, *, desde: str | None, hasta: str | None) -> list[str]:
    """Períodos ("AAAA-MM") a listar en "Estadísticas varias" para el
    rango Desde/Hasta elegido, del más nuevo al más viejo. `hasta` nunca
    pasa del período actual (un mes que todavía no llegó no tiene nada
    que mostrar) y `desde` nunca antes del primer dato cargado; ambos en
    blanco es "todo el historial" (pedido de la clienta)."""
    actual = periodo_actual(conn)
    hasta_efectivo = hasta if hasta is not None and hasta <= actual else actual
    desde_efectivo = desde if desde is not None else _periodo_mas_antiguo_con_datos(conn)
    if desde_efectivo > hasta_efectivo:
        return []

    periodos = []
    cursor = hasta_efectivo
    while cursor >= desde_efectivo:
        periodos.append(cursor)
        cursor = periodo_anterior(cursor)
    return periodos


def historial_general(conn: sqlite3.Connection, *, por_anio: bool) -> list[FilaEstadistica]:
    """Solapa "Historial general": surge de los SnapshotMensual ya
    generados (uno por cada avance de mes) más el mes en curso, calculado
    en vivo porque todavía no se cerró. Los snapshots generados antes de
    esta revisión no tienen Horas/Montos guardados (esas columnas no
    existían) — esas celdas quedan en blanco, no se recalculan
    retroactivamente (ver el docstring del módulo: la info "surge de los
    snapshots", no se reconstruye por fuera de ellos)."""
    snapshots = obtener_repositorio(conn, "SnapshotMensual").listar()
    datos_por_mes: dict[str, dict] = {
        s["Periodo"]: {
            "ocupacion_pct": s["PorcentajeOcupacionGeneral"],
            "horas": s["HorasRegularesSemanales"],
            "monto_regular": s["MontoHorasRegulares"],
            "monto_aislada": s["MontoHorasAisladas"],
        }
        for s in snapshots
    }

    periodo_en_curso = periodo_actual(conn)
    if periodo_en_curso not in datos_por_mes:
        anio, mes = parsear_periodo(periodo_en_curso)
        datos_por_mes[periodo_en_curso] = {
            "ocupacion_pct": calcular_ocupacion(conn, anio, mes).general,
            "horas": horas_regulares_semanales_promedio(conn, anio, mes),
            "monto_regular": monto_bruto_regular_periodo(conn, anio, mes),
            "monto_aislada": monto_bruto_aislada_periodo(conn, anio, mes),
        }

    cant_localidades, cant_edificios, cant_unidades, cant_consultorios = conteo_entidades(conn)

    if not por_anio:
        filas = []
        for periodo in sorted(datos_por_mes, reverse=True):
            datos = datos_por_mes[periodo]
            anterior = datos_por_mes.get(periodo_anterior(periodo))
            variacion = None
            if anterior is not None and datos["horas"] is not None and anterior["horas"] is not None:
                variacion = datos["horas"] - anterior["horas"]
            filas.append(FilaEstadistica(
                periodo=periodo,
                ocupacion_pct=datos["ocupacion_pct"],
                horas_regulares_semanales=datos["horas"],
                variacion_horas=variacion,
                monto_regular=datos["monto_regular"],
                monto_aislada=datos["monto_aislada"],
                cant_localidades=cant_localidades, cant_edificios=cant_edificios,
                cant_unidades=cant_unidades, cant_consultorios=cant_consultorios,
            ))
        return filas

    # "Por año": ocupación/horas se promedian entre los meses del año con
    # datos, montos se suman — pedido explícito de la clienta ("mixto
    # según la columna"); las cantidades de entidades son siempre las
    # actuales, año pasado o vigente (ver el docstring del módulo).
    periodos_por_anio: dict[int, list[str]] = {}
    for periodo in datos_por_mes:
        anio, _mes = parsear_periodo(periodo)
        periodos_por_anio.setdefault(anio, []).append(periodo)

    def _promedio(campo: str, periodos: list[str]) -> float | None:
        valores = [datos_por_mes[p][campo] for p in periodos if datos_por_mes[p][campo] is not None]
        return sum(valores) / len(valores) if valores else None

    def _suma(campo: str, periodos: list[str]) -> float | None:
        valores = [datos_por_mes[p][campo] for p in periodos if datos_por_mes[p][campo] is not None]
        return sum(valores) if valores else None

    filas = []
    for anio in sorted(periodos_por_anio, reverse=True):
        periodos_del_anio = periodos_por_anio[anio]
        horas_prom = _promedio("horas", periodos_del_anio)
        horas_anterior = _promedio("horas", periodos_por_anio.get(anio - 1, []))
        variacion = horas_prom - horas_anterior if horas_prom is not None and horas_anterior is not None else None
        filas.append(FilaEstadistica(
            periodo=str(anio),
            ocupacion_pct=_promedio("ocupacion_pct", periodos_del_anio),
            horas_regulares_semanales=horas_prom,
            variacion_horas=variacion,
            monto_regular=_suma("monto_regular", periodos_del_anio),
            monto_aislada=_suma("monto_aislada", periodos_del_anio),
            cant_localidades=cant_localidades, cant_edificios=cant_edificios,
            cant_unidades=cant_unidades, cant_consultorios=cant_consultorios,
        ))
    return filas


def estadisticas_varias(
    conn: sqlite3.Connection, *,
    desde: str | None = None, hasta: str | None = None,
    id_localidad: int | None = None, id_edificio: int | None = None,
    id_unidad: int | None = None, id_consultorio: int | None = None,
) -> list[FilaEstadistica]:
    """Solapa "Estadísticas varias": 100% en vivo (no lee SnapshotMensual).
    `desde`/`hasta` ("AAAA-MM", ambos opcionales) acotan el rango de
    períodos a mostrar — los dos en blanco es todo el historial, desde el
    primer dato hasta el mes en curso. Sin filtro de ubicación es todo el
    sistema; "el más específico manda" entre Localidad/Edificio/Unidad/
    Consultorio, mismo criterio que el Alcance de Gestor de archivos."""
    ids_consultorio = _ids_consultorio_del_alcance(
        conn, id_localidad=id_localidad, id_edificio=id_edificio, id_unidad=id_unidad, id_consultorio=id_consultorio,
    )
    cant_localidades, cant_edificios, cant_unidades, cant_consultorios = conteo_entidades(
        conn, id_localidad=id_localidad, id_edificio=id_edificio, id_unidad=id_unidad, id_consultorio=id_consultorio,
    )

    filas = []
    for periodo in _periodos_para_filtro(conn, desde=desde, hasta=hasta):
        p_anio, p_mes = parsear_periodo(periodo)
        horas = horas_regulares_semanales_promedio(conn, p_anio, p_mes, ids_consultorio)
        a_anio, a_mes = parsear_periodo(periodo_anterior(periodo))
        horas_anterior = horas_regulares_semanales_promedio(conn, a_anio, a_mes, ids_consultorio)
        filas.append(FilaEstadistica(
            periodo=periodo,
            ocupacion_pct=calcular_ocupacion(conn, p_anio, p_mes, ids_consultorio).general,
            horas_regulares_semanales=horas,
            variacion_horas=horas - horas_anterior,
            monto_regular=monto_bruto_regular_periodo(conn, p_anio, p_mes, ids_consultorio),
            monto_aislada=monto_bruto_aislada_periodo(conn, p_anio, p_mes, ids_consultorio),
            cant_localidades=cant_localidades, cant_edificios=cant_edificios,
            cant_unidades=cant_unidades, cant_consultorios=cant_consultorios,
        ))
    return filas
