"""Liquidación mensual de profesionales regulares (Etapa 4, sección 4.5,
afinado por DC-01, DC-05, DC-06, DC-09, DC-11 y aclaraciones directas).

Solo los profesionales categoría R tienen liquidación mensual propia:
- Categoría E: sus horas (bruto, feriados, vacaciones, licencias, aisladas)
  se consolidan en la liquidación del R cabeza de equipo — económicamente
  es como si fueran del R. No se genera liquidación para el E.
- Categoría B: sin liquidación bajo ningún concepto — sus bloques ya están
  bonificados y nunca generan cargo.

Orden de ítems (DC-01 §1.10), con el detalle de cómo se calcula cada uno:

    Bruto (por tramo si cambian horas semanales o consultorio a mitad de
    mes) -> Descuento por horas semanales (por tramo) -> Subtotal reserva
    -> Saldo anterior -> Descuento feriados -> Descuento no laborables ->
    Descuento feriados pendientes del mes anterior -> Descuento vacaciones
    -> Descuento licencias -> Horas regulares agregadas (deferidas del mes
    anterior) -> Feriado trabajado mes anterior -> Feriado trabajado mes en
    curso -> Aisladas mes anterior -> Aisladas mes en curso -> Ajuste por
    saldo atrasado (solo si aplica) -> Cargos especiales -> Cuotas de plan
    de pago -> Total

Tramos (DC-01 §1.1/§1.2): si cambia la cantidad de horas semanales
reservadas (agrega/quita reservas) o el consultorio a mitad de mes, el %
de descuento no es uno solo para todo el bruto — cada día usa el % vigente
ESE día. En vez de "detectar" tramos por separado, se calcula día por día
(que es lo que da el monto exacto sin importar cuántos cambios haya) y
LUEGO se agrupan los días consecutivos con el mismo % y las mismas horas
semanales en tramos, solo para exponer el desglose.

Pérdida del descuento por horas (DC-02/DC-06 §5.1, aclarado en
conversación): si el profesional arrastra saldo por encima de
ToleranciaDeudaDescuento, el descuento por horas semanales es 0% en TODA
la liquidación de ese mes (bruto, feriados, vacaciones, licencias, horas
agregadas, feriado trabajado — todo lo que use "valor con descuento").

Ajuste por saldo atrasado y pérdida de descuento (DC-06 §5.2, corregido en
conversación): las dos cosas se evalúan EN VIVO en cada cálculo, no una
sola vez en el avance de mes. Si el profesional paga algo imputado al mes
anterior que regulariza la situación ANTES de que se le emita y envíe la
liquidación, ni el ajuste ni la pérdida de descuento se aplican — no hace
falta ninguna reversión porque nunca llegaron a calcularse: alcanza con
que `calcular_liquidacion` siempre lea el SaldoCuentaAnterior actual (ya
neto de cualquier pago tardío, ver `pagos.registrar_pago`). El avance de
mes (`avance_mes.py`) solo trasplanta el saldo — no aplica ningún ajuste
por su cuenta.

Feriados — tres situaciones distintas (aclaradas en conversación):
1. Feriado ya conocido dentro del mes en curso: descuento normal, uno por
   día (`descuentos_feriados` / `descuentos_no_laborables`).
2. Feriado agregado a la lista DESPUÉS de emitida la liquidación del mes
   en que cae (ej. feriado extraordinario de último momento): descuento
   pendiente en la liquidación siguiente (`feriados_pendientes`).
3. Profesional que TRABAJA un feriado (en vez de tomarse el descuento):
   cargo aparte (`feriados_trabajados_mes_en_curso` /
   `_mes_anterior`), calculado con el MISMO descuento por horas semanales
   que las horas regulares (corrige DC-01 §1.5, que decía "sin descuento").
   Si se avisa antes de emitir la liquidación del mes del feriado, entra
   ese mismo mes; si se avisa después, se traslada al mes siguiente — la
   señal es FeriadoTrabajado.FechaCarga contra LiquidacionEmitida.
   FechaEmision del mes correspondiente.

SaldoCuentaActual (DC-09 §8): no se pisa con el total de la liquidación.
Se lleva como ledger: cada emisión suma el "monto generado" (todo menos
saldo_anterior) y, si es una reemisión, se resta primero lo que había
aportado la emisión anterior de ese mismo período (delta), para no perder
pagos ya registrados contra el mes en curso (esos pagos NUNCA entran en el
cálculo de la liquidación en sí — se tienen en cuenta recién al cierre del
mes, en el avance de mes).
"""
from __future__ import annotations

import calendar
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.negocio.dias import fecha_a_dia_semana
from app.negocio.feriados import feriados_relevantes_periodo
from app.negocio.valores import obtener_porcentaje_descuento
from app.repositorio.registro import obtener_repositorio

CATEGORIAS_CON_LIQUIDACION_MENSUAL = ("R",)


@dataclass
class Tramo:
    fecha_desde: str
    fecha_hasta: str
    horas_semanales: float
    descuento_pct: float
    bruto: float

    @property
    def subtotal(self) -> float:
        return self.bruto * (1 - self.descuento_pct / 100)


@dataclass
class ItemFeriado:
    fecha: str
    tipo: str
    monto: float


@dataclass
class ItemHorasAgregadas:
    id_reserva_regular: int
    dia_semana: str
    vigencia_inicio: str
    monto: float


@dataclass
class ItemFeriadoTrabajado:
    id_feriado_trabajado: int
    id_consultorio: int
    fecha: str
    hora_inicio: float
    hora_fin: float
    monto: float


@dataclass
class Liquidacion:
    id_profesional: int
    periodo: str
    bruto: float
    horas_semanales: float
    descuento_horas_pct: float
    subtotal_reserva: float
    saldo_anterior: float
    tramos: list[Tramo] = field(default_factory=list)
    pierde_descuento_horas: bool = False
    descuentos_feriados: list[ItemFeriado] = field(default_factory=list)
    descuentos_no_laborables: list[ItemFeriado] = field(default_factory=list)
    feriados_pendientes: list[ItemFeriado] = field(default_factory=list)
    descuento_vacaciones: float = 0.0
    descuento_licencias: float = 0.0
    horas_regulares_agregadas: list[ItemHorasAgregadas] = field(default_factory=list)
    feriados_trabajados_mes_anterior: list[ItemFeriadoTrabajado] = field(default_factory=list)
    feriados_trabajados_mes_en_curso: list[ItemFeriadoTrabajado] = field(default_factory=list)
    aisladas_mes_anterior: float = 0.0
    aisladas_mes_en_curso: float = 0.0
    ajuste_saldo_atrasado: float = 0.0
    cargos_especiales: list[sqlite3.Row] = field(default_factory=list)
    cuotas_plan: list[sqlite3.Row] = field(default_factory=list)

    @property
    def total_descuento_feriados(self) -> float:
        return sum(i.monto for i in self.descuentos_feriados)

    @property
    def total_descuento_no_laborables(self) -> float:
        return sum(i.monto for i in self.descuentos_no_laborables)

    @property
    def total_feriados_pendientes(self) -> float:
        return sum(i.monto for i in self.feriados_pendientes)

    @property
    def total_horas_regulares_agregadas(self) -> float:
        return sum(i.monto for i in self.horas_regulares_agregadas)

    @property
    def total_feriados_trabajados_mes_anterior(self) -> float:
        return sum(i.monto for i in self.feriados_trabajados_mes_anterior)

    @property
    def total_feriados_trabajados_mes_en_curso(self) -> float:
        return sum(i.monto for i in self.feriados_trabajados_mes_en_curso)

    @property
    def total_cargos_especiales(self) -> float:
        return sum(c["Monto"] if c["Tipo"] == "Débito" else -c["Monto"] for c in self.cargos_especiales)

    @property
    def total_cuotas_plan(self) -> float:
        return sum(c["Monto"] for c in self.cuotas_plan)

    @property
    def monto_generado(self) -> float:
        """Todo lo que esta liquidación aporta, SIN el saldo anterior (es lo
        que se acredita a SaldoCuentaActual al emitir)."""
        return (
            self.subtotal_reserva
            - self.total_descuento_feriados
            - self.total_descuento_no_laborables
            - self.total_feriados_pendientes
            - self.descuento_vacaciones
            - self.descuento_licencias
            + self.total_horas_regulares_agregadas
            + self.total_feriados_trabajados_mes_anterior
            + self.total_feriados_trabajados_mes_en_curso
            + self.aisladas_mes_anterior
            + self.aisladas_mes_en_curso
            + self.ajuste_saldo_atrasado
            + self.total_cargos_especiales
            + self.total_cuotas_plan
        )

    @property
    def total(self) -> float:
        return self.saldo_anterior + self.monto_generado


# ------------------------------------------------------------------ utilidades de fecha

def _parsear_periodo(periodo: str) -> tuple[int, int]:
    anio, mes = (int(p) for p in periodo.split("-"))
    if not 1 <= mes <= 12:
        raise ValueError(f"Período inválido: {periodo!r}")
    return anio, mes


def _periodo_anterior(periodo: str) -> str:
    anio, mes = _parsear_periodo(periodo)
    return f"{anio}-{12:02d}" if mes == 1 else f"{anio}-{mes - 1:02d}"


def _primer_dia(anio: int, mes: int) -> date:
    return date(anio, mes, 1)


def _ultimo_dia(anio: int, mes: int) -> date:
    return date(anio, mes, calendar.monthrange(anio, mes)[1])


def _interseccion(desde_a: str, hasta_a: str, desde_b: str, hasta_b: str) -> tuple[str, str] | None:
    desde = max(desde_a, desde_b)
    hasta = min(hasta_a, hasta_b)
    return (desde, hasta) if desde <= hasta else None


# ------------------------------------------------------------- consolidación categoría E

def _ids_consolidados(conn: sqlite3.Connection, id_profesional: int) -> list[int]:
    """El profesional R más todos los E que lo tienen como cabeza de
    equipo (DC-01 §1.1: sus horas se consolidan económicamente en el R)."""
    filas = conn.execute(
        "SELECT IdProfesional FROM Profesional WHERE ProfesionalCabezaEquipo = ? AND CategoriaProfesional = 'E'",
        (id_profesional,),
    ).fetchall()
    return [id_profesional] + [f["IdProfesional"] for f in filas]


# ------------------------------------------------------------------- reservas regulares

def _reservas_regulares_del_dia(
    conn: sqlite3.Connection, ids: list[int], dia: date, ids_excluir: frozenset[int] = frozenset(),
):
    placeholders = ", ".join("?" for _ in ids)
    fecha_iso = dia.isoformat()
    filas = conn.execute(
        f"""
        SELECT rr.IdReservaRegular, rr.HoraInicio, rr.HoraFin, c.ValorHoraRegularActual
        FROM ReservaRegular rr
        JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio
        WHERE rr.IdProfesional IN ({placeholders}) AND rr.DiaSemana = ?
          AND rr.VigenciaInicio <= ? AND (rr.VigenciaFin IS NULL OR rr.VigenciaFin >= ?)
        """,
        (*ids, fecha_a_dia_semana(dia), fecha_iso, fecha_iso),
    ).fetchall()
    return [f for f in filas if f["IdReservaRegular"] not in ids_excluir]


def _horas_semanales_vigentes(
    conn: sqlite3.Connection, ids: list[int], fecha_referencia: str, ids_excluir: frozenset[int] = frozenset(),
) -> float:
    placeholders = ", ".join("?" for _ in ids)
    filas = conn.execute(
        f"SELECT IdReservaRegular, HoraInicio, HoraFin FROM ReservaRegular "
        f"WHERE IdProfesional IN ({placeholders}) "
        "AND VigenciaInicio <= ? AND (VigenciaFin IS NULL OR VigenciaFin >= ?)",
        (*ids, fecha_referencia, fecha_referencia),
    ).fetchall()
    return sum(f["HoraFin"] - f["HoraInicio"] for f in filas if f["IdReservaRegular"] not in ids_excluir)


def _descuento_pct_en_fecha(
    conn: sqlite3.Connection, ids: list[int], fecha: str, ids_excluir: frozenset[int], pierde_descuento: bool,
) -> float:
    if pierde_descuento:
        return 0.0
    horas = _horas_semanales_vigentes(conn, ids, fecha, ids_excluir)
    return obtener_porcentaje_descuento(conn, horas)


def _ids_reservas_tardias(
    conn: sqlite3.Connection, ids: list[int], anio: int, mes: int, fecha_corte: str | None,
) -> frozenset[int]:
    """Reservas que empezaron dentro de (anio, mes) después de `fecha_corte`
    (la emisión de la liquidación de ese mismo mes): sus ocurrencias de ese
    mes quedan afuera del bruto y pasan como "horas regulares agregadas"
    al mes siguiente. Vacío si el mes no fue emitido: no hay nada que
    trasladar."""
    if fecha_corte is None:
        return frozenset()
    placeholders = ", ".join("?" for _ in ids)
    primer = _primer_dia(anio, mes).isoformat()
    ultimo = _ultimo_dia(anio, mes).isoformat()
    filas = conn.execute(
        f"SELECT IdReservaRegular FROM ReservaRegular WHERE IdProfesional IN ({placeholders}) "
        "AND VigenciaInicio > ? AND VigenciaInicio BETWEEN ? AND ?",
        (*ids, fecha_corte, primer, ultimo),
    ).fetchall()
    return frozenset(f["IdReservaRegular"] for f in filas)


def _bruto_y_tramos(
    conn: sqlite3.Connection, ids: list[int], primer_dia: str, ultimo_dia: str,
    ids_excluir: frozenset[int], pierde_descuento: bool,
) -> list[Tramo]:
    """Recorre día por día el período y agrupa los días consecutivos con
    las mismas horas semanales y el mismo % de descuento en tramos. El
    monto siempre es exacto (se calcula por día); los tramos son solo para
    desglosar el PDF más adelante."""
    tramos: list[Tramo] = []
    dia = date.fromisoformat(primer_dia)
    fin = date.fromisoformat(ultimo_dia)
    while dia <= fin:
        fecha_iso = dia.isoformat()
        horas_sem = _horas_semanales_vigentes(conn, ids, fecha_iso, ids_excluir)
        pct = 0.0 if pierde_descuento else obtener_porcentaje_descuento(conn, horas_sem)
        bruto_dia = sum(
            (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"]
            for f in _reservas_regulares_del_dia(conn, ids, dia, ids_excluir)
        )
        if tramos and tramos[-1].horas_semanales == horas_sem and tramos[-1].descuento_pct == pct:
            tramos[-1].fecha_hasta = fecha_iso
            tramos[-1].bruto += bruto_dia
        else:
            tramos.append(Tramo(
                fecha_desde=fecha_iso, fecha_hasta=fecha_iso,
                horas_semanales=horas_sem, descuento_pct=pct, bruto=bruto_dia,
            ))
        dia += timedelta(days=1)
    return tramos


# --------------------------------------------------------------------------- feriados

def _fecha_emision_periodo(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> str | None:
    """Fecha de la última emisión (o reemisión) de la liquidación de ese
    período, o None si ese período todavía no fue emitido."""
    filas = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    fechas = [f["FechaEmision"] for f in filas if f["FechaEmision"]]
    return max(fechas) if fechas else None


def _calcular_descuentos_feriados(
    conn: sqlite3.Connection, ids: list[int], anio: int, mes: int,
    ids_excluir: frozenset[int], pierde_descuento: bool,
) -> tuple[list[ItemFeriado], list[ItemFeriado]]:
    feriados = feriados_relevantes_periodo(conn, anio, mes)
    nacionales, no_laborables = [], []
    for feriado in feriados:
        dia = date.fromisoformat(feriado["Fecha"])
        pct = _descuento_pct_en_fecha(conn, ids, feriado["Fecha"], ids_excluir, pierde_descuento)
        monto = sum(
            (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"] * (1 - pct / 100)
            for f in _reservas_regulares_del_dia(conn, ids, dia, ids_excluir)
        )
        if monto <= 0:
            continue
        item = ItemFeriado(fecha=feriado["Fecha"], tipo=feriado["Tipo"], monto=monto)
        (nacionales if feriado["Tipo"] == "Feriado nacional" else no_laborables).append(item)
    return nacionales, no_laborables


def _calcular_feriados_pendientes(
    conn: sqlite3.Connection, ids: list[int], id_profesional: int, periodo_anterior: str,
    ids_excluir: frozenset[int], pierde_descuento: bool,
) -> list[ItemFeriado]:
    """Feriados del mes anterior agregados a la lista DESPUÉS de que ya se
    había emitido la liquidación de ese mes (ej. feriado extraordinario de
    último momento): el descuento queda pendiente y se suma acá."""
    fecha_emision_ant = _fecha_emision_periodo(conn, id_profesional, periodo_anterior)
    if fecha_emision_ant is None:
        return []
    anio_ant, mes_ant = _parsear_periodo(periodo_anterior)
    pendientes = []
    for feriado in feriados_relevantes_periodo(conn, anio_ant, mes_ant):
        if feriado["Fecha"] <= fecha_emision_ant:
            continue  # ya estaba en la lista cuando se emitió esa liquidación
        dia = date.fromisoformat(feriado["Fecha"])
        pct = _descuento_pct_en_fecha(conn, ids, feriado["Fecha"], ids_excluir, pierde_descuento)
        monto = sum(
            (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"] * (1 - pct / 100)
            for f in _reservas_regulares_del_dia(conn, ids, dia, ids_excluir)
        )
        if monto > 0:
            pendientes.append(ItemFeriado(fecha=feriado["Fecha"], tipo=feriado["Tipo"], monto=monto))
    return pendientes


# ------------------------------------------------------------ horas regulares agregadas

def _calcular_horas_regulares_agregadas(
    conn: sqlite3.Connection, ids: list[int], id_profesional: int, periodo: str, pierde_descuento: bool,
) -> list[ItemHorasAgregadas]:
    """Reservas agregadas a mitad del mes anterior después de que su
    liquidación ya había sido emitida: se cobran ahora, con el mismo
    descuento por horas semanales que tendrían si se hubieran cobrado a
    tiempo, por las ocurrencias entre su VigenciaInicio y el fin de ese
    mes, sin contar los feriados de ese mes."""
    periodo_anterior = _periodo_anterior(periodo)
    fecha_corte = _fecha_emision_periodo(conn, id_profesional, periodo_anterior)
    if fecha_corte is None:
        return []

    anio_ant, mes_ant = _parsear_periodo(periodo_anterior)
    ultimo_dia_ant = _ultimo_dia(anio_ant, mes_ant)
    feriados_ant = {f["Fecha"] for f in feriados_relevantes_periodo(conn, anio_ant, mes_ant)}

    placeholders = ", ".join("?" for _ in ids)
    filas = conn.execute(
        f"""
        SELECT rr.IdReservaRegular, rr.DiaSemana, rr.HoraInicio, rr.HoraFin, rr.VigenciaInicio,
               c.ValorHoraRegularActual
        FROM ReservaRegular rr
        JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio
        WHERE rr.IdProfesional IN ({placeholders}) AND rr.VigenciaInicio > ?
          AND rr.VigenciaInicio BETWEEN ? AND ?
        """,
        (*ids, fecha_corte, _primer_dia(anio_ant, mes_ant).isoformat(), ultimo_dia_ant.isoformat()),
    ).fetchall()

    items = []
    for f in filas:
        dia = date.fromisoformat(f["VigenciaInicio"])
        monto = 0.0
        while dia <= ultimo_dia_ant:
            if fecha_a_dia_semana(dia) == f["DiaSemana"] and dia.isoformat() not in feriados_ant:
                pct = _descuento_pct_en_fecha(conn, ids, dia.isoformat(), frozenset(), pierde_descuento)
                monto += (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"] * (1 - pct / 100)
            dia += timedelta(days=1)
        if monto > 0:
            items.append(ItemHorasAgregadas(
                id_reserva_regular=f["IdReservaRegular"], dia_semana=f["DiaSemana"],
                vigencia_inicio=f["VigenciaInicio"], monto=monto,
            ))
    return items


# --------------------------------------------------------------------- feriado trabajado

def _valor_feriado_trabajado(
    conn: sqlite3.Connection, ids: list[int], fila: sqlite3.Row, pierde_descuento: bool, recargo_pct: float,
) -> float:
    horas = fila["HoraFin"] - fila["HoraInicio"]
    pct = _descuento_pct_en_fecha(conn, ids, fila["Fecha"], frozenset(), pierde_descuento)
    monto = horas * fila["ValorHoraRegularActual"] * (1 - pct / 100)
    if fila["AplicaRecargo"]:
        monto *= 1 + recargo_pct / 100
    return monto


def _calcular_feriados_trabajados(
    conn: sqlite3.Connection, ids: list[int], id_profesional: int, periodo: str, pierde_descuento: bool,
) -> tuple[list[ItemFeriadoTrabajado], list[ItemFeriadoTrabajado]]:
    """Horas trabajadas en un feriado en vez de tomarse el descuento (DC-01
    §1.5, DC-11 caso 2). Con el mismo descuento por horas semanales que las
    horas regulares. Si se cargó antes de emitir la liquidación del mes del
    feriado entra ese mes; si se cargó después, se traslada al siguiente."""
    placeholders = ", ".join("?" for _ in ids)
    cfg = conn.execute(
        "SELECT RecargoPorcentajeAisladas FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    recargo_pct = cfg["RecargoPorcentajeAisladas"] if cfg else 0.0

    def _filas_del_mes(anio: int, mes: int) -> list[sqlite3.Row]:
        prefijo = f"{anio:04d}-{mes:02d}-"
        return conn.execute(
            f"""
            SELECT ft.IdFeriadoTrabajado, ft.IdConsultorio, ft.Fecha, ft.HoraInicio, ft.HoraFin,
                   ft.AplicaRecargo, ft.FechaCarga, c.ValorHoraRegularActual
            FROM FeriadoTrabajado ft
            JOIN Consultorio c ON c.IdConsultorio = ft.IdConsultorio
            WHERE ft.IdProfesional IN ({placeholders}) AND ft.Fecha LIKE ?
            """,
            (*ids, prefijo + "%"),
        ).fetchall()

    anio, mes = _parsear_periodo(periodo)
    fecha_emision_este = _fecha_emision_periodo(conn, id_profesional, periodo)
    mes_en_curso = []
    for f in _filas_del_mes(anio, mes):
        if fecha_emision_este is not None and f["FechaCarga"] > fecha_emision_este:
            continue  # avisado después de emitida: se traslada al mes siguiente
        monto = _valor_feriado_trabajado(conn, ids, f, pierde_descuento, recargo_pct)
        mes_en_curso.append(ItemFeriadoTrabajado(
            id_feriado_trabajado=f["IdFeriadoTrabajado"], id_consultorio=f["IdConsultorio"],
            fecha=f["Fecha"], hora_inicio=f["HoraInicio"], hora_fin=f["HoraFin"], monto=monto,
        ))

    periodo_anterior = _periodo_anterior(periodo)
    anio_ant, mes_ant = _parsear_periodo(periodo_anterior)
    fecha_emision_ant = _fecha_emision_periodo(conn, id_profesional, periodo_anterior)
    mes_anterior = []
    if fecha_emision_ant is not None:
        for f in _filas_del_mes(anio_ant, mes_ant):
            if f["FechaCarga"] <= fecha_emision_ant:
                continue  # ya se había avisado a tiempo: entró en la liquidación de ese mes
            monto = _valor_feriado_trabajado(conn, ids, f, pierde_descuento, recargo_pct)
            mes_anterior.append(ItemFeriadoTrabajado(
                id_feriado_trabajado=f["IdFeriadoTrabajado"], id_consultorio=f["IdConsultorio"],
                fecha=f["Fecha"], hora_inicio=f["HoraInicio"], hora_fin=f["HoraFin"], monto=monto,
            ))

    return mes_anterior, mes_en_curso


# --------------------------------------------------------------- vacaciones y licencias

def _calcular_descuento_vacaciones(
    conn: sqlite3.Connection, ids: list[int], primer_dia: str, ultimo_dia: str,
    ids_excluir: frozenset[int], pierde_descuento: bool,
) -> float:
    """Recalcula el ValorBonificado de cada Vacacion (de R y de sus E)
    restringido a los días que caen en este período — evita descontar dos
    veces una vacación que cruza fin de mes (DC-01 §1.7, DC-05 §1.6)."""
    total = 0.0
    for id_prof in ids:
        for v in obtener_repositorio(conn, "Vacacion").listar(IdProfesional=id_prof):
            interseccion = _interseccion(v["FechaDesde"], v["FechaHasta"], primer_dia, ultimo_dia)
            if interseccion is None:
                continue
            dia = date.fromisoformat(interseccion[0])
            fin = date.fromisoformat(interseccion[1])
            while dia <= fin:
                for f in _reservas_regulares_del_dia(conn, [id_prof], dia, ids_excluir):
                    pct = _descuento_pct_en_fecha(conn, ids, dia.isoformat(), ids_excluir, pierde_descuento)
                    total += (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"] * (1 - pct / 100)
                dia += timedelta(days=1)
    return total


def _calcular_descuento_licencias(
    conn: sqlite3.Connection, ids: list[int], primer_dia: str, ultimo_dia: str,
    ids_excluir: frozenset[int], pierde_descuento: bool,
) -> float:
    """Igual criterio que vacaciones (DC-05 §2.4), multiplicado además por
    el % de bonificación del tipo de licencia."""
    total = 0.0
    for id_prof in ids:
        for l in obtener_repositorio(conn, "Licencia").listar(IdProfesional=id_prof):
            interseccion = _interseccion(l["FechaDesde"], l["FechaHasta"], primer_dia, ultimo_dia)
            if interseccion is None:
                continue
            porcentaje = (l["PorcentajeBonificacionAplicado"] or 0.0) / 100
            dia = date.fromisoformat(interseccion[0])
            fin = date.fromisoformat(interseccion[1])
            while dia <= fin:
                for f in _reservas_regulares_del_dia(conn, [id_prof], dia, ids_excluir):
                    pct = _descuento_pct_en_fecha(conn, ids, dia.isoformat(), ids_excluir, pierde_descuento)
                    total += (
                        (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"]
                        * (1 - pct / 100) * porcentaje
                    )
                dia += timedelta(days=1)
    return total


# --------------------------------------------------------------------------- aisladas

def _valor_aisladas_periodo(conn: sqlite3.Connection, ids: list[int], anio: int, mes: int) -> float:
    placeholders = ", ".join("?" for _ in ids)
    prefijo = f"{anio:04d}-{mes:02d}-"
    filas = conn.execute(
        f"""
        SELECT ra.HoraInicio, ra.HoraFin, ra.AplicaRecargo, c.ValorHoraAisladaActual
        FROM ReservaAislada ra
        JOIN Consultorio c ON c.IdConsultorio = ra.IdConsultorio
        WHERE ra.IdProfesional IN ({placeholders}) AND ra.Estado = 'Confirmada' AND ra.Fecha LIKE ?
        """,
        (*ids, prefijo + "%"),
    ).fetchall()
    cfg = conn.execute(
        "SELECT RecargoPorcentajeAisladas FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    recargo_pct = cfg["RecargoPorcentajeAisladas"] if cfg else 0.0

    total = 0.0
    for f in filas:
        monto = (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraAisladaActual"]
        if f["AplicaRecargo"]:
            monto *= 1 + recargo_pct / 100
        total += monto
    return total


# ------------------------------------------------------------------------------ cálculo

def calcular_liquidacion(conn: sqlite3.Connection, *, id_profesional: int, periodo: str) -> Liquidacion:
    """Calcula (sin persistir) la liquidación mensual de un profesional R
    para el período `periodo` (formato 'AAAA-MM'). Consolida automática-
    mente las horas de los profesionales E que lo tienen como cabeza de
    equipo."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    if profesional["CategoriaProfesional"] not in CATEGORIAS_CON_LIQUIDACION_MENSUAL:
        raise ValueError(
            "Solo los profesionales categoría R tienen liquidación mensual propia "
            "(categoría E se consolida en la de su R, categoría B nunca se liquida)"
        )

    ids = _ids_consolidados(conn, id_profesional)
    anio, mes = _parsear_periodo(periodo)
    anio_ant, mes_ant = _parsear_periodo(_periodo_anterior(periodo))
    primer_dia_periodo = _primer_dia(anio, mes).isoformat()
    ultimo_dia_periodo = _ultimo_dia(anio, mes).isoformat()

    saldo_anterior = profesional["SaldoCuentaAnterior"] or 0.0
    cfg = conn.execute(
        "SELECT ToleranciaDeudaDescuento, PorcentajeAjusteSaldoAtrasado FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    tolerancia = cfg["ToleranciaDeudaDescuento"] if cfg else 0.0
    ajuste_pct = cfg["PorcentajeAjusteSaldoAtrasado"] if cfg else 0.0
    pierde_descuento = saldo_anterior > tolerancia
    # Ajuste por saldo atrasado (DC-06 §5.2): se evalúa en vivo, igual que
    # pierde_descuento. Si un pago imputado al mes anterior ya regularizó
    # la situación antes de calcular esto, saldo_anterior bajó y no aplica
    # — no hace falta ninguna reversión posterior.
    ajuste_saldo_atrasado = saldo_anterior * ajuste_pct / 100 if pierde_descuento else 0.0

    fecha_emision_este_periodo = _fecha_emision_periodo(conn, id_profesional, periodo)
    ids_tardias = _ids_reservas_tardias(conn, ids, anio, mes, fecha_emision_este_periodo)

    tramos = _bruto_y_tramos(conn, ids, primer_dia_periodo, ultimo_dia_periodo, ids_tardias, pierde_descuento)
    bruto = sum(t.bruto for t in tramos)
    subtotal_reserva = sum(t.subtotal for t in tramos)

    descuentos_feriados, descuentos_no_laborables = _calcular_descuentos_feriados(
        conn, ids, anio, mes, ids_tardias, pierde_descuento
    )
    feriados_pendientes = _calcular_feriados_pendientes(
        conn, ids, id_profesional, _periodo_anterior(periodo), ids_tardias, pierde_descuento
    )
    horas_regulares_agregadas = _calcular_horas_regulares_agregadas(
        conn, ids, id_profesional, periodo, pierde_descuento
    )
    feriados_trab_anterior, feriados_trab_actual = _calcular_feriados_trabajados(
        conn, ids, id_profesional, periodo, pierde_descuento
    )
    descuento_vacaciones = _calcular_descuento_vacaciones(
        conn, ids, primer_dia_periodo, ultimo_dia_periodo, ids_tardias, pierde_descuento
    )
    descuento_licencias = _calcular_descuento_licencias(
        conn, ids, primer_dia_periodo, ultimo_dia_periodo, ids_tardias, pierde_descuento
    )

    aisladas_mes_anterior = _valor_aisladas_periodo(conn, ids, anio_ant, mes_ant)
    aisladas_mes_en_curso = _valor_aisladas_periodo(conn, ids, anio, mes)

    cargos_especiales = obtener_repositorio(conn, "CargoEspecial").listar(
        IdProfesional=id_profesional, PeriodoImputado=periodo
    )
    cuotas_plan = conn.execute(
        """
        SELECT cp.* FROM CuotaPlan cp
        JOIN PlanPago pp ON pp.IdPlan = cp.IdPlan
        WHERE pp.IdProfesional = ? AND cp.PeriodoImputado = ? AND cp.Pagado = 0
        """,
        (id_profesional, periodo),
    ).fetchall()

    return Liquidacion(
        id_profesional=id_profesional, periodo=periodo, bruto=bruto,
        horas_semanales=tramos[0].horas_semanales if tramos else 0.0,
        descuento_horas_pct=tramos[0].descuento_pct if tramos else 0.0,
        subtotal_reserva=subtotal_reserva, saldo_anterior=saldo_anterior, tramos=tramos,
        pierde_descuento_horas=pierde_descuento,
        descuentos_feriados=descuentos_feriados, descuentos_no_laborables=descuentos_no_laborables,
        feriados_pendientes=feriados_pendientes,
        descuento_vacaciones=descuento_vacaciones, descuento_licencias=descuento_licencias,
        horas_regulares_agregadas=horas_regulares_agregadas,
        feriados_trabajados_mes_anterior=feriados_trab_anterior,
        feriados_trabajados_mes_en_curso=feriados_trab_actual,
        aisladas_mes_anterior=aisladas_mes_anterior, aisladas_mes_en_curso=aisladas_mes_en_curso,
        ajuste_saldo_atrasado=ajuste_saldo_atrasado,
        cargos_especiales=cargos_especiales, cuotas_plan=cuotas_plan,
    )


def emitir_liquidacion(
    conn: sqlite3.Connection, *, id_profesional: int, periodo: str, fecha_emision: str | None = None,
    nombre_archivo: str | None = None, es_reemision: bool = False,
) -> tuple[int, Liquidacion]:
    """Calcula la liquidación, la persiste en LiquidacionEmitida y acredita
    lo generado a SaldoCuentaActual. No toca SaldoCuentaAnterior (eso es
    responsabilidad del avance de mes). Si ya había una emisión previa para
    el mismo período, se acredita solo el DELTA contra esa emisión, para no
    perder pagos ya registrados contra el mes en curso mientras tanto."""
    monto_generado_anterior = 0.0
    repo_liq = obtener_repositorio(conn, "LiquidacionEmitida")
    previas = repo_liq.listar(IdProfesional=id_profesional, Periodo=periodo)
    if previas:
        ultima = max(previas, key=lambda f: f["IdLiquidacion"])
        monto_generado_anterior = ultima["MontoGenerado"] or 0.0

    liquidacion = calcular_liquidacion(conn, id_profesional=id_profesional, periodo=periodo)

    id_liquidacion = repo_liq.crear(
        IdProfesional=id_profesional, Periodo=periodo, FechaEmision=fecha_emision,
        NombreArchivo=nombre_archivo, EsReemision=int(es_reemision), EstadoEnvio="No enviada",
        MontoGenerado=liquidacion.monto_generado,
    )

    delta = liquidacion.monto_generado - monto_generado_anterior
    repo_prof = obtener_repositorio(conn, "Profesional")
    profesional = repo_prof.obtener(id_profesional)
    repo_prof.actualizar(id_profesional, SaldoCuentaActual=(profesional["SaldoCuentaActual"] or 0.0) + delta)

    return id_liquidacion, liquidacion
