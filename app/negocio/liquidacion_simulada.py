"""Liquidaciones simuladas (pedido de la clienta, ya con la revisión "uno
por uno" y el reordenamiento de formularios cerrados): una cuarta solapa
de "Liquidaciones" para armar un PDF de ejemplo, "para que un profesional
vea cómo se manda el archivo y cuánto le saldría un período determinado
a modo de ejemplo" — antes de que ese profesional tenga ninguna reserva
real cargada.

Deliberadamente MUCHO más simple que `app.negocio.liquidaciones`
(confirmado explícitamente por la clienta, "no se cargan conceptos
especiales... es solo para apreciar cuánto daría una reserva"): el
operador carga a mano los bloques (día/horario/consultorio) que el
profesional querría reservar y el período a simular — nunca lee
`ReservaRegular` ni ninguna otra tabla de ocupación real, así que:

- Ignora por completo si el consultorio está ocupado o reservado por
  otro profesional a esa hora — "no importa eso", es una simulación
  pura, nunca toca la grilla ni la disponibilidad real.
- SÍ contempla los feriados y fechas especiales del período (si el
  bloque cae un feriado/no laborable, se descuenta) — mismo criterio y
  mismos porcentajes (`Configuracion.PorcentajeDescuentoFeriado`/
  `PorcentajeDescuentoNoLaborable`) que la liquidación real.
- SÍ aplica el descuento por volumen de horas semanales
  (`app.negocio.valores.obtener_porcentaje_descuento`), sobre el total
  de horas de los bloques cargados (no hay "vigencia" que vaya
  cambiando a lo largo del período — los bloques simulados valen para
  el período entero, así que las horas semanales son un número fijo).
- NO tiene saldo anterior, vacaciones, licencias, ausencias, cargos
  especiales (llaves y otros conceptos), feriados trabajados ni
  reubicaciones — ninguno de esos conceptos tiene sentido para "cuánto
  daría reservar este horario", que es la única pregunta que responde
  esta simulación.

Pedido de la clienta al revisar la primera versión de la solapa: además
del total general, quiere ver un desglose por cada bloque cargado
("Subtotal por bloque" en la GUI) — cuánto aporta cada uno por
separado, no solo la suma. `SubtotalBloque` (horas semanales/mensuales,
bruto, % y monto de descuento, neto, todos por ese bloque en
particular) se calcula sumando, para cada bloque, su propio aporte día
por día del período — el % de descuento por volumen es el mismo
(`descuento_horas_pct`, calculado una sola vez sobre el total de horas
de TODOS los bloques juntos) aplicado al bruto de ESE bloque nomás. El
descuento de un bloque incluye tanto su parte del descuento por volumen
como cualquier feriado que caiga en su día de la semana — a diferencia
de `descuentos_feriados` (un ítem por fecha, agregando todos los
bloques de ese día, pensado para el PDF), acá el monto de cada feriado
se reparte bloque por bloque para que la suma de `neto` de todos los
`SubtotalBloque` coincida exactamente con `LiquidacionSimulada.neto`.

El PDF resultante (`app.pdf.liquidacion_simulada_pdf`) se guarda en su
propia carpeta compartida (`app.negocio.archivos_generados.
carpeta_liquidaciones_simuladas`, NO en `Profesionales/{código}` como
las liquidaciones reales) con retención corta (3 meses, ver
`limpiar_liquidaciones_simuladas_antiguas`, llamada desde
`avance_mes.avanzar_mes` igual que la limpieza de liquidaciones reales) —
son ejemplos descartables, no un registro que haya que conservar."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.negocio.dias import fecha_a_dia_semana, parsear_periodo, primer_dia_mes, ultimo_dia_mes
from app.negocio.feriados import feriados_relevantes_periodo
from app.negocio.valores import obtener_porcentaje_descuento
from app.repositorio.registro import obtener_repositorio


@dataclass
class BloqueSimulado:
    dia_semana: str
    hora_inicio: float
    hora_fin: float
    id_consultorio: int


@dataclass
class ItemFeriadoSimulado:
    fecha: str
    tipo: str
    monto: float


@dataclass
class SubtotalBloque:
    """Desglose de lo que aporta UN bloque en particular (numerado
    1-based, en el mismo orden que `LiquidacionSimulada.bloques`) —
    `descuento` ya incluye tanto la parte de este bloque en el
    descuento por volumen como cualquier feriado que le corresponda,
    así que `neto` de todos los bloques suma exactamente el `neto`
    total de la liquidación."""
    numero: int
    horas_semanales: float
    horas_mensuales: float
    bruto: float
    descuento_pct: float
    descuento: float
    neto: float


@dataclass
class LiquidacionSimulada:
    id_profesional: int
    periodo: str
    bloques: list[BloqueSimulado]
    horas_semanales: float
    descuento_horas_pct: float
    bruto: float
    descuentos_feriados: list[ItemFeriadoSimulado] = field(default_factory=list)
    subtotales_bloques: list[SubtotalBloque] = field(default_factory=list)

    @property
    def total_descuento_feriados(self) -> float:
        return sum(i.monto for i in self.descuentos_feriados)

    @property
    def neto(self) -> float:
        return self.bruto * (1 - self.descuento_horas_pct / 100) - self.total_descuento_feriados


def _porcentajes_tipo_fecha(conn: sqlite3.Connection) -> dict[str, float]:
    """Mismos parámetros que usa la liquidación real para feriados
    nacionales/días no laborables (`Configuracion.PorcentajeDescuentoFeriado`/
    `PorcentajeDescuentoNoLaborable`) — reimplementado acá en vez de
    importar la versión privada de `app.negocio.liquidaciones` para no
    acoplar esta simulación (deliberadamente independiente) a los
    internos de esa lógica mucho más compleja."""
    cfg = conn.execute(
        "SELECT PorcentajeDescuentoFeriado, PorcentajeDescuentoNoLaborable FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    return {
        "Feriado nacional": cfg["PorcentajeDescuentoFeriado"] if cfg else 100.0,
        "Día no laborable": cfg["PorcentajeDescuentoNoLaborable"] if cfg else 100.0,
    }


def _cantidad_dias_semana_en_periodo(anio: int, mes: int, dia_semana: str) -> int:
    """Cuántas veces cae `dia_semana` (ej. "Lunes") dentro del período
    AAAA-MM indicado."""
    dia_actual, ultimo_dia = primer_dia_mes(anio, mes), ultimo_dia_mes(anio, mes)
    cantidad = 0
    while dia_actual <= ultimo_dia:
        if fecha_a_dia_semana(dia_actual) == dia_semana:
            cantidad += 1
        dia_actual += timedelta(days=1)
    return cantidad


def calcular_liquidacion_simulada(
    conn: sqlite3.Connection, *, id_profesional: int, periodo: str, bloques: list[BloqueSimulado],
) -> LiquidacionSimulada:
    if not bloques:
        raise ValueError("Agregá al menos un bloque para simular.")

    horas_semanales = sum(b.hora_fin - b.hora_inicio for b in bloques)
    descuento_pct = obtener_porcentaje_descuento(conn, horas_semanales)

    repo_consultorio = obtener_repositorio(conn, "Consultorio")
    valores_hora: dict[int, float] = {}
    for id_consultorio in {b.id_consultorio for b in bloques}:
        consultorio = repo_consultorio.obtener(id_consultorio)
        if consultorio is None:
            raise ValueError(f"No existe el consultorio #{id_consultorio}")
        valores_hora[id_consultorio] = consultorio["ValorHoraRegularActual"]

    anio, mes = parsear_periodo(periodo)

    # Bruto de cada bloque por separado (en vez de un recorrido día por
    # día del período): cuántas veces cae su día de la semana en el
    # período × sus horas × el valor hora de su consultorio. Sumar esto
    # bloque por bloque da exactamente el mismo total que recorrer el
    # período día por día (cada día solo le suma a los bloques cuyo
    # `dia_semana` coincide), pero de paso deja el aporte de cada bloque
    # calculado aparte para el desglose que pide la GUI.
    horas_mensuales_por_bloque = [
        (b.hora_fin - b.hora_inicio) * _cantidad_dias_semana_en_periodo(anio, mes, b.dia_semana) for b in bloques
    ]
    brutos_por_bloque = [
        horas_mensuales_por_bloque[i] * valores_hora[b.id_consultorio] for i, b in enumerate(bloques)
    ]
    bruto = sum(brutos_por_bloque)

    porcentajes_tipo = _porcentajes_tipo_fecha(conn)
    descuentos_feriados = []
    descuentos_feriados_por_bloque = [0.0] * len(bloques)
    for feriado in feriados_relevantes_periodo(conn, anio, mes):
        dia_semana_feriado = fecha_a_dia_semana(date.fromisoformat(feriado["Fecha"]))
        montos_por_bloque_este_feriado = [
            (b.hora_fin - b.hora_inicio) * valores_hora[b.id_consultorio] * (1 - descuento_pct / 100)
            * (porcentajes_tipo[feriado["Tipo"]] / 100)
            if b.dia_semana == dia_semana_feriado else 0.0
            for b in bloques
        ]
        monto_total_feriado = sum(montos_por_bloque_este_feriado)
        if monto_total_feriado <= 0:
            continue
        descuentos_feriados.append(
            ItemFeriadoSimulado(fecha=feriado["Fecha"], tipo=feriado["Tipo"], monto=monto_total_feriado)
        )
        for i, monto_bloque in enumerate(montos_por_bloque_este_feriado):
            descuentos_feriados_por_bloque[i] += monto_bloque

    subtotales_bloques = [
        SubtotalBloque(
            numero=i + 1,
            horas_semanales=b.hora_fin - b.hora_inicio,
            horas_mensuales=horas_mensuales_por_bloque[i],
            bruto=brutos_por_bloque[i],
            descuento_pct=descuento_pct,
            descuento=brutos_por_bloque[i] * descuento_pct / 100 + descuentos_feriados_por_bloque[i],
            neto=brutos_por_bloque[i] * (1 - descuento_pct / 100) - descuentos_feriados_por_bloque[i],
        )
        for i, b in enumerate(bloques)
    ]

    return LiquidacionSimulada(
        id_profesional=id_profesional, periodo=periodo, bloques=list(bloques),
        horas_semanales=horas_semanales, descuento_horas_pct=descuento_pct, bruto=bruto,
        descuentos_feriados=descuentos_feriados, subtotales_bloques=subtotales_bloques,
    )
