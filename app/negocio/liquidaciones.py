"""Liquidación mensual de profesionales regulares (Etapa 4, sección 4.5).

El documento define el orden de ítems del PDF de liquidación pero no dice
la fórmula exacta de cada uno (eso se resuelve recién con el armado visual
en la Etapa 7). Acá se calcula el valor de cada ítem que sí tiene datos
suficientes en el modelo, y se arma el total acumulado en el mismo orden
que la sección 4.5:

    Bruto -> Descuento horas -> Subtotal reserva -> Saldo anterior ->
    Descuento feriados -> Descuento no laborables -> Descuento vacaciones ->
    Descuento licencias -> Descuento bonificación (solo categoría B) ->
    Horas regulares agregadas -> Aisladas mes anterior -> Aisladas mes en
    curso -> Ajuste por saldo atrasado -> Cargos especiales -> Cuotas de
    plan de pago -> Total

La categoría B ("bonificado") tiene 100% de descuento sobre lo que le
correspondería pagar por sus reservas regulares del período: Bruto ya con
el descuento por volumen de horas y neto de los descuentos de feriados,
no laborables, vacaciones y licencias. Sigue pagando, si corresponde,
aisladas, cargos especiales, cuotas de plan de pago y el ajuste por saldo
atrasado (esas líneas no dependen de la categoría).

Horas regulares agregadas: cuando se suma una reserva regular nueva a
mitad de mes DESPUÉS de que la liquidación de ese mes ya fue emitida, sus
horas del resto del mes (excluyendo feriados) no se cobran en ese mes —
se trasladan como cargo aparte a la liquidación siguiente. Se detecta
comparando ReservaRegular.VigenciaInicio contra LiquidacionEmitida.
FechaEmision del mismo período: si la reserva empezó después de esa
fecha, sus ocurrencias de ese mes quedan afuera del Bruto de ese mes y
pasan a "horas_regulares_agregadas" del mes siguiente. Si el período
todavía no fue emitido, no hay nada que trasladar: se cobra completo como
siempre.

Feriados mes anterior: es el cargo (no descuento) por un profesional que
trabajó un día feriado, algo que en general se sabe/avisa tarde. No hace
falta una línea de cálculo propia para esto: se carga a mano con
`pagos.crear_cargo_especial` (Tipo="Débito", PeriodoImputado=mes que
corresponda cobrarlo), el mismo mecanismo genérico que ya cubre "Ítem
libre" y "Depósito/Reintegro llave" (sección 3.15).

Solo aplica a profesionales categoría R, B o E (los que tienen reservas
regulares y por lo tanto liquidación mensual). Los aislados (categoría A)
se liquidan con el mensaje de detalle de reservas (sección 5.1), no con
este proceso.
"""
from __future__ import annotations

import calendar
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.negocio.dias import fecha_a_dia_semana
from app.negocio.feriados import feriados_relevantes_periodo
from app.negocio.valores import obtener_porcentaje_descuento, valor_regular_por_rango_dias
from app.repositorio.registro import obtener_repositorio

CATEGORIAS_CON_LIQUIDACION_MENSUAL = ("R", "B", "E")


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
class Liquidacion:
    id_profesional: int
    periodo: str
    bruto: float
    horas_semanales: float
    descuento_horas_pct: float
    subtotal_reserva: float
    saldo_anterior: float
    descuentos_feriados: list[ItemFeriado] = field(default_factory=list)
    descuentos_no_laborables: list[ItemFeriado] = field(default_factory=list)
    descuento_vacaciones: float = 0.0
    descuento_licencias: float = 0.0
    descuento_bonificacion: float = 0.0
    horas_regulares_agregadas: list[ItemHorasAgregadas] = field(default_factory=list)
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
    def total_horas_regulares_agregadas(self) -> float:
        return sum(i.monto for i in self.horas_regulares_agregadas)

    @property
    def total_cargos_especiales(self) -> float:
        return sum(c["Monto"] if c["Tipo"] == "Débito" else -c["Monto"] for c in self.cargos_especiales)

    @property
    def total_cuotas_plan(self) -> float:
        return sum(c["Monto"] for c in self.cuotas_plan)

    @property
    def total(self) -> float:
        return (
            self.subtotal_reserva
            + self.saldo_anterior
            - self.total_descuento_feriados
            - self.total_descuento_no_laborables
            - self.descuento_vacaciones
            - self.descuento_licencias
            - self.descuento_bonificacion
            + self.total_horas_regulares_agregadas
            + self.aisladas_mes_anterior
            + self.aisladas_mes_en_curso
            + self.ajuste_saldo_atrasado
            + self.total_cargos_especiales
            + self.total_cuotas_plan
        )


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


def _reservas_regulares_del_dia(conn: sqlite3.Connection, id_profesional: int, dia: date):
    fecha_iso = dia.isoformat()
    return conn.execute(
        """
        SELECT rr.IdReservaRegular, rr.HoraInicio, rr.HoraFin, c.ValorHoraRegularActual
        FROM ReservaRegular rr
        JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio
        WHERE rr.IdProfesional = ? AND rr.DiaSemana = ?
          AND rr.VigenciaInicio <= ? AND (rr.VigenciaFin IS NULL OR rr.VigenciaFin >= ?)
        """,
        (id_profesional, fecha_a_dia_semana(dia), fecha_iso, fecha_iso),
    ).fetchall()


def _fecha_emision_periodo(conn: sqlite3.Connection, id_profesional: int, periodo: str) -> str | None:
    """Fecha de la última emisión (o reemisión) de la liquidación de ese
    período, o None si ese período todavía no fue emitido."""
    filas = obtener_repositorio(conn, "LiquidacionEmitida").listar(IdProfesional=id_profesional, Periodo=periodo)
    fechas = [f["FechaEmision"] for f in filas if f["FechaEmision"]]
    return max(fechas) if fechas else None


def _ids_reservas_tardias(
    conn: sqlite3.Connection, id_profesional: int, anio: int, mes: int, fecha_corte: str | None,
) -> set[int]:
    """IdReservaRegular de reservas que empezaron dentro de (anio, mes)
    después de `fecha_corte` (la emisión de la liquidación de ese mismo
    mes). Vacío si el mes no fue emitido: no hay nada que trasladar."""
    if fecha_corte is None:
        return set()
    primer = _primer_dia(anio, mes).isoformat()
    ultimo = _ultimo_dia(anio, mes).isoformat()
    filas = conn.execute(
        "SELECT IdReservaRegular FROM ReservaRegular WHERE IdProfesional = ? "
        "AND VigenciaInicio > ? AND VigenciaInicio BETWEEN ? AND ?",
        (id_profesional, fecha_corte, primer, ultimo),
    ).fetchall()
    return {f["IdReservaRegular"] for f in filas}


def _valor_regular_excluyendo(
    conn: sqlite3.Connection, id_profesional: int, fecha_desde: str, fecha_hasta: str, ids_excluir: set[int],
) -> float:
    """Igual que `valores.valor_regular_por_rango_dias`, pero sin contar las
    reservas de `ids_excluir` (las que se trasladan al mes siguiente)."""
    if not ids_excluir:
        return valor_regular_por_rango_dias(conn, id_profesional, fecha_desde, fecha_hasta)
    total = 0.0
    dia = date.fromisoformat(fecha_desde)
    fin = date.fromisoformat(fecha_hasta)
    while dia <= fin:
        for f in _reservas_regulares_del_dia(conn, id_profesional, dia):
            if f["IdReservaRegular"] in ids_excluir:
                continue
            total += (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"]
        dia += timedelta(days=1)
    return total


def _calcular_horas_regulares_agregadas(
    conn: sqlite3.Connection, id_profesional: int, periodo: str,
) -> list[ItemHorasAgregadas]:
    """Reservas regulares agregadas a mitad del mes anterior, después de que
    la liquidación de ese mes ya había sido emitida: se cobran ahora, por
    las ocurrencias entre su VigenciaInicio y el fin de ese mes, sin contar
    los feriados de ese mes."""
    periodo_anterior = _periodo_anterior(periodo)
    fecha_corte = _fecha_emision_periodo(conn, id_profesional, periodo_anterior)
    if fecha_corte is None:
        return []

    anio_ant, mes_ant = _parsear_periodo(periodo_anterior)
    ultimo_dia_ant = _ultimo_dia(anio_ant, mes_ant)
    feriados_ant = {f["Fecha"] for f in feriados_relevantes_periodo(conn, anio_ant, mes_ant)}

    filas = conn.execute(
        """
        SELECT rr.IdReservaRegular, rr.DiaSemana, rr.HoraInicio, rr.HoraFin, rr.VigenciaInicio,
               c.ValorHoraRegularActual
        FROM ReservaRegular rr
        JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio
        WHERE rr.IdProfesional = ? AND rr.VigenciaInicio > ?
          AND rr.VigenciaInicio BETWEEN ? AND ?
        """,
        (id_profesional, fecha_corte, _primer_dia(anio_ant, mes_ant).isoformat(), ultimo_dia_ant.isoformat()),
    ).fetchall()

    items = []
    for f in filas:
        dia = date.fromisoformat(f["VigenciaInicio"])
        valor_ocurrencia = (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"]
        monto = 0.0
        while dia <= ultimo_dia_ant:
            if fecha_a_dia_semana(dia) == f["DiaSemana"] and dia.isoformat() not in feriados_ant:
                monto += valor_ocurrencia
            dia += timedelta(days=1)
        if monto > 0:
            items.append(ItemHorasAgregadas(
                id_reserva_regular=f["IdReservaRegular"], dia_semana=f["DiaSemana"],
                vigencia_inicio=f["VigenciaInicio"], monto=monto,
            ))
    return items


def _horas_semanales_vigentes(conn: sqlite3.Connection, id_profesional: int, fecha_referencia: str) -> float:
    fila = conn.execute(
        "SELECT COALESCE(SUM(HoraFin - HoraInicio), 0) AS total FROM ReservaRegular "
        "WHERE IdProfesional = ? AND VigenciaInicio <= ? AND (VigenciaFin IS NULL OR VigenciaFin >= ?)",
        (id_profesional, fecha_referencia, fecha_referencia),
    ).fetchone()
    return fila["total"]


def _calcular_descuentos_feriados(
    conn: sqlite3.Connection, id_profesional: int, anio: int, mes: int, descuento_horas_pct: float,
    ids_excluir: set[int] = frozenset(),
) -> tuple[list[ItemFeriado], list[ItemFeriado]]:
    feriados = feriados_relevantes_periodo(conn, anio, mes)
    nacionales, no_laborables = [], []
    for feriado in feriados:
        dia = date.fromisoformat(feriado["Fecha"])
        monto = 0.0
        for f in _reservas_regulares_del_dia(conn, id_profesional, dia):
            if f["IdReservaRegular"] in ids_excluir:
                continue
            horas = f["HoraFin"] - f["HoraInicio"]
            monto += horas * f["ValorHoraRegularActual"] * (1 - descuento_horas_pct / 100)
        if monto <= 0:
            continue
        item = ItemFeriado(fecha=feriado["Fecha"], tipo=feriado["Tipo"], monto=monto)
        (nacionales if feriado["Tipo"] == "Feriado nacional" else no_laborables).append(item)
    return nacionales, no_laborables


def _interseccion(desde_a: str, hasta_a: str, desde_b: str, hasta_b: str) -> tuple[str, str] | None:
    desde = max(desde_a, desde_b)
    hasta = min(hasta_a, hasta_b)
    return (desde, hasta) if desde <= hasta else None


def _calcular_descuento_vacaciones(
    conn: sqlite3.Connection, id_profesional: int, primer_dia: str, ultimo_dia: str, descuento_horas_pct: float,
) -> float:
    """Igual que ValorBonificado de la Vacacion (sección 3.12), pero
    recalculado solo sobre los días que caen dentro de este período: una
    vacación que cruza fin de mes no debe descontarse dos veces."""
    total = 0.0
    for v in obtener_repositorio(conn, "Vacacion").listar(IdProfesional=id_profesional):
        interseccion = _interseccion(v["FechaDesde"], v["FechaHasta"], primer_dia, ultimo_dia)
        if interseccion is None:
            continue
        bruto = valor_regular_por_rango_dias(conn, id_profesional, *interseccion)
        total += bruto * (1 - descuento_horas_pct / 100)
    return total


def _calcular_descuento_licencias(
    conn: sqlite3.Connection, id_profesional: int, primer_dia: str, ultimo_dia: str,
) -> float:
    """Igual que ValorBonificado de la Licencia (sección 3.13), prorrateado
    por días de calendario dentro de este período (misma lógica de
    `licencias.crear_licencia`: valor_semanal/7 por día, congelados)."""
    total = 0.0
    for l in obtener_repositorio(conn, "Licencia").listar(IdProfesional=id_profesional):
        interseccion = _interseccion(l["FechaDesde"], l["FechaHasta"], primer_dia, ultimo_dia)
        if interseccion is None:
            continue
        dias = (date.fromisoformat(interseccion[1]) - date.fromisoformat(interseccion[0])).days + 1
        valor_semanal = l["ValorSemanalAlMomentoDelRegistro"] or 0.0
        porcentaje = l["PorcentajeBonificacionAplicado"] or 0.0
        total += (valor_semanal / 7) * dias * (porcentaje / 100)
    return total


def _valor_aisladas_periodo(conn: sqlite3.Connection, id_profesional: int, anio: int, mes: int) -> float:
    prefijo = f"{anio:04d}-{mes:02d}-"
    filas = conn.execute(
        """
        SELECT ra.HoraInicio, ra.HoraFin, ra.AplicaRecargo, c.ValorHoraAisladaActual
        FROM ReservaAislada ra
        JOIN Consultorio c ON c.IdConsultorio = ra.IdConsultorio
        WHERE ra.IdProfesional = ? AND ra.Estado = 'Confirmada' AND ra.Fecha LIKE ?
        """,
        (id_profesional, prefijo + "%"),
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


def calcular_liquidacion(conn: sqlite3.Connection, *, id_profesional: int, periodo: str) -> Liquidacion:
    """Calcula (sin persistir) la liquidación mensual de un profesional
    R/B/E para el período `periodo` (formato 'AAAA-MM')."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    if profesional["CategoriaProfesional"] not in CATEGORIAS_CON_LIQUIDACION_MENSUAL:
        raise ValueError(
            "Solo los profesionales categoría R, B o E tienen liquidación mensual"
        )

    anio, mes = _parsear_periodo(periodo)
    anio_ant, mes_ant = _parsear_periodo(_periodo_anterior(periodo))
    primer_dia_periodo = _primer_dia(anio, mes).isoformat()
    ultimo_dia_periodo = _ultimo_dia(anio, mes).isoformat()

    horas_semanales = _horas_semanales_vigentes(conn, id_profesional, primer_dia_periodo)
    descuento_horas_pct = obtener_porcentaje_descuento(conn, horas_semanales)

    fecha_emision_este_periodo = _fecha_emision_periodo(conn, id_profesional, periodo)
    ids_tardias = _ids_reservas_tardias(conn, id_profesional, anio, mes, fecha_emision_este_periodo)

    bruto = _valor_regular_excluyendo(conn, id_profesional, primer_dia_periodo, ultimo_dia_periodo, ids_tardias)
    subtotal_reserva = bruto * (1 - descuento_horas_pct / 100)

    descuentos_feriados, descuentos_no_laborables = _calcular_descuentos_feriados(
        conn, id_profesional, anio, mes, descuento_horas_pct, ids_excluir=ids_tardias,
    )
    horas_regulares_agregadas = _calcular_horas_regulares_agregadas(conn, id_profesional, periodo)
    descuento_vacaciones = _calcular_descuento_vacaciones(
        conn, id_profesional, primer_dia_periodo, ultimo_dia_periodo, descuento_horas_pct
    )
    descuento_licencias = _calcular_descuento_licencias(
        conn, id_profesional, primer_dia_periodo, ultimo_dia_periodo
    )

    descuento_bonificacion = 0.0
    if profesional["CategoriaProfesional"] == "B":
        neto_antes_de_bonificar = (
            subtotal_reserva
            - sum(i.monto for i in descuentos_feriados)
            - sum(i.monto for i in descuentos_no_laborables)
            - descuento_vacaciones
            - descuento_licencias
        )
        descuento_bonificacion = max(0.0, neto_antes_de_bonificar)

    aisladas_mes_anterior = _valor_aisladas_periodo(conn, id_profesional, anio_ant, mes_ant)
    aisladas_mes_en_curso = _valor_aisladas_periodo(conn, id_profesional, anio, mes)

    saldo_anterior = profesional["SaldoCuentaActual"]
    cfg = conn.execute(
        "SELECT PorcentajeAjusteSaldoAtrasado FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    ajuste_pct = cfg["PorcentajeAjusteSaldoAtrasado"] if cfg else 0.0
    ajuste_saldo_atrasado = saldo_anterior * ajuste_pct / 100 if saldo_anterior > 0 else 0.0

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
        id_profesional=id_profesional, periodo=periodo, bruto=bruto, horas_semanales=horas_semanales,
        descuento_horas_pct=descuento_horas_pct, subtotal_reserva=subtotal_reserva,
        saldo_anterior=saldo_anterior, descuentos_feriados=descuentos_feriados,
        descuentos_no_laborables=descuentos_no_laborables, descuento_vacaciones=descuento_vacaciones,
        descuento_licencias=descuento_licencias, descuento_bonificacion=descuento_bonificacion,
        horas_regulares_agregadas=horas_regulares_agregadas, aisladas_mes_anterior=aisladas_mes_anterior,
        aisladas_mes_en_curso=aisladas_mes_en_curso, ajuste_saldo_atrasado=ajuste_saldo_atrasado,
        cargos_especiales=cargos_especiales, cuotas_plan=cuotas_plan,
    )


def emitir_liquidacion(
    conn: sqlite3.Connection, *, id_profesional: int, periodo: str, fecha_emision: str | None = None,
    nombre_archivo: str | None = None, es_reemision: bool = False,
) -> tuple[int, Liquidacion]:
    """Calcula la liquidación, la persiste en LiquidacionEmitida y actualiza
    el saldo de cuenta del profesional (el total calculado pasa a ser la
    nueva deuda vigente; la deuda previa se congela en SaldoCuentaAnterior)."""
    liquidacion = calcular_liquidacion(conn, id_profesional=id_profesional, periodo=periodo)

    repo_liq = obtener_repositorio(conn, "LiquidacionEmitida")
    id_liquidacion = repo_liq.crear(
        IdProfesional=id_profesional, Periodo=periodo, FechaEmision=fecha_emision,
        NombreArchivo=nombre_archivo, EsReemision=int(es_reemision), EstadoEnvio="No enviada",
    )

    obtener_repositorio(conn, "Profesional").actualizar(
        id_profesional,
        SaldoCuentaAnterior=liquidacion.saldo_anterior,
        SaldoCuentaActual=liquidacion.total,
    )
    return id_liquidacion, liquidacion
