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
class LiquidacionSimulada:
    id_profesional: int
    periodo: str
    bloques: list[BloqueSimulado]
    horas_semanales: float
    descuento_horas_pct: float
    bruto: float
    descuentos_feriados: list[ItemFeriadoSimulado] = field(default_factory=list)

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
    dia_actual, ultimo_dia = primer_dia_mes(anio, mes), ultimo_dia_mes(anio, mes)
    bruto = 0.0
    while dia_actual <= ultimo_dia:
        dia_semana = fecha_a_dia_semana(dia_actual)
        bruto += sum(
            (b.hora_fin - b.hora_inicio) * valores_hora[b.id_consultorio]
            for b in bloques if b.dia_semana == dia_semana
        )
        dia_actual += timedelta(days=1)

    porcentajes_tipo = _porcentajes_tipo_fecha(conn)
    descuentos_feriados = []
    for feriado in feriados_relevantes_periodo(conn, anio, mes):
        dia_semana = fecha_a_dia_semana(date.fromisoformat(feriado["Fecha"]))
        valor_dia = sum(
            (b.hora_fin - b.hora_inicio) * valores_hora[b.id_consultorio]
            for b in bloques if b.dia_semana == dia_semana
        )
        if valor_dia <= 0:
            continue
        monto = valor_dia * (1 - descuento_pct / 100) * (porcentajes_tipo[feriado["Tipo"]] / 100)
        if monto <= 0:
            continue
        descuentos_feriados.append(ItemFeriadoSimulado(fecha=feriado["Fecha"], tipo=feriado["Tipo"], monto=monto))

    return LiquidacionSimulada(
        id_profesional=id_profesional, periodo=periodo, bloques=list(bloques),
        horas_semanales=horas_semanales, descuento_horas_pct=descuento_pct, bruto=bruto,
        descuentos_feriados=descuentos_feriados,
    )
