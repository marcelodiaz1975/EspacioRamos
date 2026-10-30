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
conversación — ajustado a pedido para que el PDF sea transparente sobre
CUÁNTO descuento se pierde, no solo que se pierde): si el profesional
arrastra saldo por encima de ToleranciaDeudaDescuento, el descuento por
horas semanales se sigue calculando y APLICANDO al bruto normalmente
(`subtotal_reserva` refleja el % real, no 0%) y de inmediato se REVIERTE
con `reversion_descuento` (bruto - subtotal_reserva), que el PDF muestra
como una línea aparte junto al saldo anterior — el efecto neto sobre el
total es el mismo que forzar 0% directamente, pero mostrando el número
real en vez de esconderlo. Si las horas reservadas no alcanzan ningún
tramo con descuento, `reversion_descuento` da 0 sola (bruto ya es igual a
subtotal_reserva) y el PDF omite esa línea. El resto de los ítems que
usan "valor con descuento" calculado EN VIVO (feriados, horas agregadas,
feriado trabajado) SÍ se siguen forzando a 0% cuando se pierde el
descuento — a diferencia del bruto, no hay una línea de reversión para
cada uno de ellos, así que se calculan directamente "sin descuento".
Vacaciones y licencias quedan afuera de esta regla a propósito: su
ValorBonificado ya quedó congelado con el % vigente al momento de
registrarlas (DC-05 §1.3) y acá solo se prorratea ese valor entre los
meses que abarca — no se recalcula con el % de hoy.

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

import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.negocio.archivos_generados import carpeta_base, carpeta_profesional
from app.negocio.dias import (
    fecha_a_dia_semana,
    parsear_periodo,
    periodo_anterior as calcular_periodo_anterior,
    periodo_operativo_actual,
    primer_dia_mes,
    ultimo_dia_mes,
)
from app.negocio.feriados import feriados_relevantes_periodo
from app.negocio.formato import decimales_total_liquidacion
from app.negocio.valores import horas_semanales_vigentes, obtener_porcentaje_descuento, valor_regular_por_rango_dias
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
    descripcion: str | None = None


@dataclass
class ItemHorasAgregadas:
    id_reserva_regular: int
    id_consultorio: int
    dia_semana: str
    hora_inicio: float
    hora_fin: float
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
class ItemVacacion:
    id_vacacion: int
    fecha_desde: str
    fecha_hasta: str
    monto: float


@dataclass
class ItemLicencia:
    id_licencia: int
    id_tipo_licencia: int
    fecha_desde: str
    fecha_hasta: str
    monto: float


@dataclass
class ItemAislada:
    id_reserva_aislada: int
    id_consultorio: int
    fecha: str
    hora_inicio: float
    hora_fin: float
    monto: float
    # Solo para una Reserva extraordinaria (#38, segunda vuelta: los R
    # también pueden tenerlas) — el ítem de texto libre cargado a mano,
    # para que el PDF pueda describir el cargo en vez de mostrar "Hora
    # aislada trabajada" sobre algo que no se cobró por hora×tarifa.
    item_extraordinario: str | None = None


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
    reversion_descuento: float = 0.0
    descuentos_feriados: list[ItemFeriado] = field(default_factory=list)
    descuentos_no_laborables: list[ItemFeriado] = field(default_factory=list)
    feriados_pendientes: list[ItemFeriado] = field(default_factory=list)
    descuento_vacaciones: list[ItemVacacion] = field(default_factory=list)
    descuento_licencias: list[ItemLicencia] = field(default_factory=list)
    horas_regulares_agregadas: list[ItemHorasAgregadas] = field(default_factory=list)
    feriados_trabajados_mes_anterior: list[ItemFeriadoTrabajado] = field(default_factory=list)
    feriados_trabajados_mes_en_curso: list[ItemFeriadoTrabajado] = field(default_factory=list)
    aisladas_mes_anterior: list[ItemAislada] = field(default_factory=list)
    aisladas_mes_en_curso: list[ItemAislada] = field(default_factory=list)
    ajuste_saldo_atrasado: float = 0.0
    cargos_especiales: list[sqlite3.Row] = field(default_factory=list)
    cuotas_plan: list[sqlite3.Row] = field(default_factory=list)
    # Redondeo del total a un peso entero (Configuracion.
    # DecimalesTotalLiquidacion = 0, ver `app.negocio.formato.
    # decimales_total_liquidacion`): calculado DESPUÉS de armar el resto de
    # la liquidación, con los centavos exactos (a favor o en contra) que
    # hacen falta para que `total` termine en un número entero — un ítem
    # más de la cuenta real, no un redondeo de pantalla.
    ajuste_redondeo: float = 0.0

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
    def total_descuento_vacaciones(self) -> float:
        return sum(i.monto for i in self.descuento_vacaciones)

    @property
    def total_descuento_licencias(self) -> float:
        return sum(i.monto for i in self.descuento_licencias)

    @property
    def total_aisladas_mes_anterior(self) -> float:
        return sum(i.monto for i in self.aisladas_mes_anterior)

    @property
    def total_aisladas_mes_en_curso(self) -> float:
        return sum(i.monto for i in self.aisladas_mes_en_curso)

    @property
    def total_cargos_especiales(self) -> float:
        """`Monto` ya viene con el signo que le corresponde al Tipo (Débito
        positivo, Crédito negativo — validado al crear el cargo), así que
        alcanza con sumarlo tal cual."""
        return sum(c["Monto"] for c in self.cargos_especiales)

    @property
    def total_cuotas_plan(self) -> float:
        return sum(c["Monto"] for c in self.cuotas_plan)

    @property
    def monto_generado(self) -> float:
        """Todo lo que esta liquidación aporta, SIN el saldo anterior (es lo
        que se acredita a SaldoCuentaActual al emitir)."""
        return (
            self.subtotal_reserva
            + self.reversion_descuento
            - self.total_descuento_feriados
            - self.total_descuento_no_laborables
            - self.total_feriados_pendientes
            - self.total_descuento_vacaciones
            - self.total_descuento_licencias
            + self.total_horas_regulares_agregadas
            + self.total_feriados_trabajados_mes_anterior
            + self.total_feriados_trabajados_mes_en_curso
            + self.total_aisladas_mes_anterior
            + self.total_aisladas_mes_en_curso
            + self.ajuste_saldo_atrasado
            + self.total_cargos_especiales
            + self.total_cuotas_plan
            + self.ajuste_redondeo
        )

    @property
    def total(self) -> float:
        return self.saldo_anterior + self.monto_generado


# ------------------------------------------------------------------ utilidades de fecha

def _interseccion(desde_a: str, hasta_a: str, desde_b: str, hasta_b: str) -> tuple[str, str] | None:
    desde = max(desde_a, desde_b)
    hasta = min(hasta_a, hasta_b)
    return (desde, hasta) if desde <= hasta else None


# ------------------------------------------------------------- consolidación categoría E

def ids_consolidados(conn: sqlite3.Connection, id_profesional: int) -> list[int]:
    """El profesional R más todos los E que lo tienen como cabeza de
    equipo (DC-01 §1.1: sus horas se consolidan económicamente en el R)."""
    filas = conn.execute(
        "SELECT IdProfesional FROM Profesional WHERE ProfesionalCabezaEquipo = ? AND CategoriaProfesional = 'E'",
        (id_profesional,),
    ).fetchall()
    return [id_profesional] + [f["IdProfesional"] for f in filas]


def id_profesional_liquidable(conn: sqlite3.Connection, id_profesional: int) -> int | None:
    """El profesional R dueño de la liquidación que corresponde regenerar
    cuando algo de `id_profesional` cambia: él mismo si es R, su cabeza de
    equipo si es E (siempre que ESA sea R), o None si es B (nunca se
    liquida) o no tiene un R al que consolidarse."""
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    if profesional is None:
        return None
    if profesional["CategoriaProfesional"] == "R":
        return id_profesional
    if profesional["CategoriaProfesional"] == "E" and profesional["ProfesionalCabezaEquipo"]:
        cabeza = obtener_repositorio(conn, "Profesional").obtener(profesional["ProfesionalCabezaEquipo"])
        if cabeza is not None and cabeza["CategoriaProfesional"] == "R":
            return profesional["ProfesionalCabezaEquipo"]
    return None


def regenerar_si_corresponde(conn: sqlite3.Connection, *, id_profesional: int, periodo: str) -> None:
    """DC-08 §3.7/§4.6/§5.4: cargar/modificar/dar de baja una reserva
    regular, registrar vacaciones, o registrar un pago imputado al mes
    anterior tienen que regenerar sola la liquidación del R afectado y
    dejarla marcada como no enviada. Si no hay un R al que regenerarle
    nada, o el período no se puede reemitir (ya hay períodos posteriores
    emitidos), no hay nada que hacer — no es motivo para interrumpir la
    operación principal.

    `emitir_liquidacion` sola solo deja el registro en `LiquidacionEmitida`
    (lo que ya alcanza para que el Centro de mensajería muestre el estado
    correcto) — pero el PDF real en disco quedaba desactualizado, con los
    números de ANTES del cambio que disparó esta regeneración (bug real,
    no solo cosmético: confirmado por la clienta sobre un pago imputado al
    mes anterior). Acá también se genera el PDF nuevo y se actualiza
    `NombreArchivo`/`FechaHoraGeneracion`, mismo criterio exacto que
    `PantallaLiquidacion._emitir` — sin pedir confirmación, igual que el
    resto de esta función, y sin interrumpir nada si todavía no hay
    carpeta base configurada o el profesional no tiene código asignado."""
    id_r = id_profesional_liquidable(conn, id_profesional)
    if id_r is None:
        return
    try:
        id_liquidacion, liquidacion = emitir_liquidacion(conn, id_profesional=id_r, periodo=periodo)
    except ValueError:
        return
    if carpeta_base(conn) is None:
        return
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_r)
    if profesional is None or not profesional["IdCodigo"]:
        return
    from app.pdf.liquidacion_pdf import generar_pdf_liquidacion  # import tardío: evita el ciclo con este módulo

    ruta = generar_pdf_liquidacion(conn, liquidacion, str(carpeta_profesional(conn, profesional["IdCodigo"])))
    obtener_repositorio(conn, "LiquidacionEmitida").actualizar(
        id_liquidacion, NombreArchivo=os.path.basename(ruta),
        FechaHoraGeneracion=datetime.now().isoformat(timespec="seconds"),
    )


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


def _descuento_pct_en_fecha(
    conn: sqlite3.Connection, ids: list[int], fecha: str, ids_excluir: frozenset[int], pierde_descuento: bool,
) -> float:
    if pierde_descuento:
        return 0.0
    horas = horas_semanales_vigentes(conn, ids, fecha, ids_excluir)
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
    primer = primer_dia_mes(anio, mes).isoformat()
    ultimo = ultimo_dia_mes(anio, mes).isoformat()
    filas = conn.execute(
        f"SELECT IdReservaRegular FROM ReservaRegular WHERE IdProfesional IN ({placeholders}) "
        "AND VigenciaInicio > ? AND VigenciaInicio BETWEEN ? AND ?",
        (*ids, fecha_corte, primer, ultimo),
    ).fetchall()
    return frozenset(f["IdReservaRegular"] for f in filas)


def _bruto_y_tramos(
    conn: sqlite3.Connection, ids: list[int], primer_dia: str, ultimo_dia: str,
    ids_excluir: frozenset[int],
) -> list[Tramo]:
    """Recorre día por día el período y agrupa los días consecutivos con
    las mismas horas semanales y el mismo % de descuento en tramos. El
    monto siempre es exacto (se calcula por día); los tramos son solo para
    desglosar el PDF más adelante.

    Siempre usa el % real (no se fuerza a 0% acá aunque el profesional
    pierda el descuento por saldo atrasado) — `calcular_liquidacion` es
    quien revierte ese descuento después con `reversion_descuento`, para
    que el PDF pueda mostrar el número real aplicado y su reversión por
    separado en vez de esconderlo detrás de un "0%"."""
    tramos: list[Tramo] = []
    dia = date.fromisoformat(primer_dia)
    fin = date.fromisoformat(ultimo_dia)
    while dia <= fin:
        fecha_iso = dia.isoformat()
        horas_sem = horas_semanales_vigentes(conn, ids, fecha_iso, ids_excluir)
        pct = obtener_porcentaje_descuento(conn, horas_sem)
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


def _porcentajes_tipo_fecha(conn: sqlite3.Connection) -> dict[str, float]:
    """DC-01 §1.3: feriados nacionales y días no laborables tienen
    parámetros de porcentaje independientes en Configuracion — hoy ambos
    al 100% por defecto, pero modificables por separado."""
    cfg = conn.execute(
        "SELECT PorcentajeDescuentoFeriado, PorcentajeDescuentoNoLaborable FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    return {
        "Feriado nacional": cfg["PorcentajeDescuentoFeriado"] if cfg else 100.0,
        "Día no laborable": cfg["PorcentajeDescuentoNoLaborable"] if cfg else 100.0,
    }


def _monto_feriado_dia(
    conn: sqlite3.Connection, ids: list[int], fecha: str, ids_excluir: frozenset[int], pierde_descuento: bool,
    porcentaje_tipo: float = 100.0,
) -> float:
    """Valor descontado de las horas regulares reservadas para ese día de
    feriado, con el % de descuento por horas semanales vigente ese día,
    multiplicado por el % del tipo de fecha (feriado/no laborable)."""
    dia = date.fromisoformat(fecha)
    pct = _descuento_pct_en_fecha(conn, ids, fecha, ids_excluir, pierde_descuento)
    return sum(
        (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraRegularActual"] * (1 - pct / 100) * (porcentaje_tipo / 100)
        for f in _reservas_regulares_del_dia(conn, ids, dia, ids_excluir)
    )


def _calcular_descuentos_feriados(
    conn: sqlite3.Connection, ids: list[int], anio: int, mes: int,
    ids_excluir: frozenset[int], pierde_descuento: bool,
) -> tuple[list[ItemFeriado], list[ItemFeriado]]:
    feriados = feriados_relevantes_periodo(conn, anio, mes)
    porcentajes = _porcentajes_tipo_fecha(conn)
    nacionales, no_laborables = [], []
    for feriado in feriados:
        monto = _monto_feriado_dia(
            conn, ids, feriado["Fecha"], ids_excluir, pierde_descuento, porcentajes[feriado["Tipo"]],
        )
        if monto <= 0:
            continue
        item = ItemFeriado(
            fecha=feriado["Fecha"], tipo=feriado["Tipo"], monto=monto, descripcion=feriado["Descripcion"],
        )
        (nacionales if feriado["Tipo"] == "Feriado nacional" else no_laborables).append(item)
    # Pedido explícito de la clienta ("los veo mezclados", con un ejemplo
    # concreto: el feriado del 9 tiene que ir arriba del 23) — orden
    # cronológico ascendente, sin importar el orden de carga en la tabla
    # de Fechas especiales. Reemplaza el criterio anterior ("de más
    # próximo a hoy arriba a más alejado abajo", que en la práctica daba
    # el más RECIENTE primero — ver docs/historial/liquidaciones.md).
    nacionales.sort(key=lambda i: i.fecha)
    no_laborables.sort(key=lambda i: i.fecha)
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
    anio_ant, mes_ant = parsear_periodo(periodo_anterior)
    porcentajes = _porcentajes_tipo_fecha(conn)
    pendientes = []
    for feriado in feriados_relevantes_periodo(conn, anio_ant, mes_ant):
        if feriado["Fecha"] <= fecha_emision_ant:
            continue  # ya estaba en la lista cuando se emitió esa liquidación
        monto = _monto_feriado_dia(
            conn, ids, feriado["Fecha"], ids_excluir, pierde_descuento, porcentajes[feriado["Tipo"]],
        )
        if monto > 0:
            pendientes.append(ItemFeriado(
                fecha=feriado["Fecha"], tipo=feriado["Tipo"], monto=monto, descripcion=feriado["Descripcion"],
            ))
    pendientes.sort(key=lambda i: i.fecha)  # mismo criterio que _calcular_descuentos_feriados
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
    periodo_anterior = calcular_periodo_anterior(periodo)
    fecha_corte = _fecha_emision_periodo(conn, id_profesional, periodo_anterior)
    if fecha_corte is None:
        return []

    anio_ant, mes_ant = parsear_periodo(periodo_anterior)
    ultimo_dia_ant = ultimo_dia_mes(anio_ant, mes_ant)
    feriados_ant = {f["Fecha"] for f in feriados_relevantes_periodo(conn, anio_ant, mes_ant)}

    placeholders = ", ".join("?" for _ in ids)
    filas = conn.execute(
        f"""
        SELECT rr.IdReservaRegular, rr.IdConsultorio, rr.DiaSemana, rr.HoraInicio, rr.HoraFin, rr.VigenciaInicio,
               c.ValorHoraRegularActual
        FROM ReservaRegular rr
        JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio
        WHERE rr.IdProfesional IN ({placeholders}) AND rr.VigenciaInicio > ?
          AND rr.VigenciaInicio BETWEEN ? AND ?
        """,
        (*ids, fecha_corte, primer_dia_mes(anio_ant, mes_ant).isoformat(), ultimo_dia_ant.isoformat()),
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
                id_reserva_regular=f["IdReservaRegular"], id_consultorio=f["IdConsultorio"],
                dia_semana=f["DiaSemana"], hora_inicio=f["HoraInicio"], hora_fin=f["HoraFin"],
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
    recargo_pct: float,
) -> tuple[list[ItemFeriadoTrabajado], list[ItemFeriadoTrabajado]]:
    """Horas trabajadas en un feriado en vez de tomarse el descuento (DC-01
    §1.5, DC-11 caso 2). Con el mismo descuento por horas semanales que las
    horas regulares. Si se cargó antes de emitir la liquidación del mes del
    feriado entra ese mes; si se cargó después, se traslada al siguiente."""
    placeholders = ", ".join("?" for _ in ids)

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

    anio, mes = parsear_periodo(periodo)
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

    periodo_anterior = calcular_periodo_anterior(periodo)
    anio_ant, mes_ant = parsear_periodo(periodo_anterior)
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

def _fecha_hasta_bonificable_licencia(conn: sqlite3.Connection, licencia: sqlite3.Row) -> str:
    """La licencia puede pedirse por más días de los que su tipo permite
    bonificar (DC-05 §2.3: avisa pero no bloquea, el excedente se cobra
    normal) — `licencias.crear_licencia` ya recorta el cálculo de
    ValorBonificado a esta franja, pero guarda el FechaHasta completo tal
    como se pidió. Hay que rederivar el mismo recorte acá para no prorratear
    contra días que nunca se bonificaron."""
    tipo = obtener_repositorio(conn, "TipoLicencia").obtener(licencia["IdTipoLicencia"])
    dias_max = tipo["DuracionMaximaDias"] if tipo else None
    if not dias_max:
        return licencia["FechaHasta"]
    limite = (date.fromisoformat(licencia["FechaDesde"]) + timedelta(days=dias_max - 1)).isoformat()
    return min(limite, licencia["FechaHasta"])


def _prorratear_valor_bonificado(
    conn: sqlite3.Connection, id_profesional: int, valor_bonificado: float,
    fecha_desde_bonificable: str, fecha_hasta_bonificable: str, primer_dia: str, ultimo_dia: str,
) -> float:
    """Prorratea un ValorBonificado ya congelado (vacaciones o licencias)
    según qué proporción de sus días con reserva regular cae en este
    período. Se prorratea por bruto ponderado por día, no por días
    corridos, para que un período con más horas reservadas un mes que otro
    (ej. cambia de consultorio o de cantidad de días a mitad de la
    vacación) reparta el descuento de forma proporcional y no en partes
    iguales. Nunca recalcula con el % de descuento vigente HOY: usa el
    valor ya congelado al momento de registrar (DC-05 §1.3), que es
    justamente lo que evita perder de vista el tope de cupo o de duración
    máxima ya aplicado en el registro original."""
    if not valor_bonificado:
        return 0.0
    interseccion = _interseccion(fecha_desde_bonificable, fecha_hasta_bonificable, primer_dia, ultimo_dia)
    if interseccion is None:
        return 0.0
    bruto_total = valor_regular_por_rango_dias(conn, id_profesional, fecha_desde_bonificable, fecha_hasta_bonificable)
    if bruto_total <= 0:
        return 0.0
    bruto_interseccion = valor_regular_por_rango_dias(conn, id_profesional, *interseccion)
    return valor_bonificado * (bruto_interseccion / bruto_total)


def _calcular_descuento_vacaciones(
    conn: sqlite3.Connection, ids: list[int], primer_dia: str, ultimo_dia: str,
) -> list[ItemVacacion]:
    """Prorratea el ValorBonificado ya congelado de cada Vacacion (de R y
    de sus E) — evita descontar dos veces una vacación que cruza fin de mes
    (DC-01 §1.7, DC-05 §1.6) y respeta el recorte por cupo agotado, que
    `vacaciones.crear_vacacion` aplica como un escalado de todo el período,
    no como un corte de fecha. Un ítem por Vacacion (no un total): el PDF
    de liquidación detalla cada una con su rango de fechas."""
    items = []
    for id_prof in ids:
        for v in obtener_repositorio(conn, "Vacacion").listar(IdProfesional=id_prof):
            monto = _prorratear_valor_bonificado(
                conn, id_prof, v["ValorBonificado"], v["FechaDesde"], v["FechaHasta"], primer_dia, ultimo_dia,
            )
            if monto:
                items.append(ItemVacacion(
                    id_vacacion=v["IdVacacion"], fecha_desde=v["FechaDesde"], fecha_hasta=v["FechaHasta"],
                    monto=monto,
                ))
    return items


def _calcular_descuento_licencias(
    conn: sqlite3.Connection, ids: list[int], primer_dia: str, ultimo_dia: str,
) -> list[ItemLicencia]:
    """Igual criterio que vacaciones (DC-05 §2.4/§2.5), prorrateando contra
    la franja realmente bonificada (hasta el tope de duración máxima del
    tipo si el pedido lo excedió), no contra el FechaHasta completo."""
    items = []
    for id_prof in ids:
        for l in obtener_repositorio(conn, "Licencia").listar(IdProfesional=id_prof):
            fecha_hasta_bonificable = _fecha_hasta_bonificable_licencia(conn, l)
            monto = _prorratear_valor_bonificado(
                conn, id_prof, l["ValorBonificado"], l["FechaDesde"], fecha_hasta_bonificable, primer_dia, ultimo_dia,
            )
            if monto:
                items.append(ItemLicencia(
                    id_licencia=l["IdLicencia"], id_tipo_licencia=l["IdTipoLicencia"],
                    fecha_desde=l["FechaDesde"], fecha_hasta=fecha_hasta_bonificable, monto=monto,
                ))
    return items


# --------------------------------------------------------------------------- aisladas

def _aisladas_periodo(
    conn: sqlite3.Connection, ids: list[int], anio: int, mes: int, recargo_pct: float,
) -> list[ItemAislada]:
    """Un ítem por ReservaAislada confirmada del período (no un total): el
    PDF de liquidación detalla cada una con fecha, horario y consultorio."""
    placeholders = ", ".join("?" for _ in ids)
    prefijo = f"{anio:04d}-{mes:02d}-"
    filas = conn.execute(
        f"""
        SELECT ra.IdReservaAislada, ra.IdConsultorio, ra.Fecha, ra.HoraInicio, ra.HoraFin,
               ra.AplicaRecargo, ra.EsReubicacion, ra.EsExtraordinaria, ra.MontoExtraordinario,
               ra.ItemExtraordinario, c.ValorHoraAisladaActual
        FROM ReservaAislada ra
        JOIN Consultorio c ON c.IdConsultorio = ra.IdConsultorio
        WHERE ra.IdProfesional IN ({placeholders}) AND ra.Estado = 'Confirmada' AND ra.Fecha LIKE ?
        """,
        (*ids, prefijo + "%"),
    ).fetchall()

    items = []
    for f in filas:
        if f["EsExtraordinaria"]:
            # Monto manual, ya cargado tal cual al confirmarla — ni
            # hora×tarifa ni el recargo de aisladas corren acá (#38,
            # segunda vuelta: mismo criterio que `crear_reserva_aislada`,
            # que fuerza `AplicaRecargo=False` para estas).
            monto = f["MontoExtraordinario"] or 0.0
        elif f["EsReubicacion"]:
            # compensa una ausencia del mismo profesional en otro horario —
            # ocupa el consultorio pero no genera cargo (confirmado por el usuario).
            monto = 0.0
        else:
            monto = (f["HoraFin"] - f["HoraInicio"]) * f["ValorHoraAisladaActual"]
            if f["AplicaRecargo"]:
                monto *= 1 + recargo_pct / 100
        items.append(ItemAislada(
            id_reserva_aislada=f["IdReservaAislada"], id_consultorio=f["IdConsultorio"], fecha=f["Fecha"],
            hora_inicio=f["HoraInicio"], hora_fin=f["HoraFin"], monto=monto,
            item_extraordinario=f["ItemExtraordinario"] if f["EsExtraordinaria"] else None,
        ))
    return items


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

    ids = ids_consolidados(conn, id_profesional)
    anio, mes = parsear_periodo(periodo)
    anio_ant, mes_ant = parsear_periodo(calcular_periodo_anterior(periodo))
    primer_dia_periodo = primer_dia_mes(anio, mes).isoformat()
    ultimo_dia_periodo = ultimo_dia_mes(anio, mes).isoformat()

    saldo_anterior = profesional["SaldoCuentaAnterior"] or 0.0
    cfg = conn.execute(
        "SELECT ToleranciaDeudaDescuento, PorcentajeAjusteSaldoAtrasado, RecargoPorcentajeAisladas "
        "FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    tolerancia = cfg["ToleranciaDeudaDescuento"] if cfg else 0.0
    ajuste_pct = cfg["PorcentajeAjusteSaldoAtrasado"] if cfg else 0.0
    recargo_pct = cfg["RecargoPorcentajeAisladas"] if cfg else 0.0
    saldo_sigue_atrasado = saldo_anterior > tolerancia
    # DC-06 §5.2: si un pago imputado a este período puntual hizo que el
    # saldo volviera a estar dentro de tolerancia, pero el operador eligió
    # NO restablecer el descuento por horas semanales (`pagos.
    # suspender_descuento_periodo`), se seguía perdiendo igual para esta
    # liquidación remanente. La marca es por período: no arrastra a otros
    # meses. El ajuste por saldo atrasado (más abajo) NO se ve afectado por
    # esta decisión — depende solo del saldo real, nunca se "restablece".
    pierde_descuento = saldo_sigue_atrasado or profesional["DescuentoSuspendidoPeriodo"] == periodo
    # Ajuste por saldo atrasado (DC-06 §5.2): se evalúa en vivo sobre el
    # saldo real. Si un pago imputado al mes anterior ya regularizó la
    # situación antes de calcular esto, saldo_anterior bajó y no aplica —
    # no hace falta ninguna reversión posterior, y la suspensión manual del
    # descuento por horas no lo reactiva.
    ajuste_saldo_atrasado = saldo_anterior * ajuste_pct / 100 if saldo_sigue_atrasado else 0.0

    fecha_emision_este_periodo = _fecha_emision_periodo(conn, id_profesional, periodo)
    ids_tardias = _ids_reservas_tardias(conn, ids, anio, mes, fecha_emision_este_periodo)

    tramos = _bruto_y_tramos(conn, ids, primer_dia_periodo, ultimo_dia_periodo, ids_tardias)
    bruto = sum(t.bruto for t in tramos)
    subtotal_reserva = sum(t.subtotal for t in tramos)
    # El descuento por horas semanales se aplica siempre (ver _bruto_y_tramos)
    # y, si se pierde por saldo atrasado, se revierte acá — da 0 solo si las
    # horas reservadas no alcanzan ningún tramo con descuento real.
    reversion_descuento = (bruto - subtotal_reserva) if pierde_descuento else 0.0

    descuentos_feriados, descuentos_no_laborables = _calcular_descuentos_feriados(
        conn, ids, anio, mes, ids_tardias, pierde_descuento
    )
    feriados_pendientes = _calcular_feriados_pendientes(
        conn, ids, id_profesional, calcular_periodo_anterior(periodo), ids_tardias, pierde_descuento
    )
    horas_regulares_agregadas = _calcular_horas_regulares_agregadas(
        conn, ids, id_profesional, periodo, pierde_descuento
    )
    feriados_trab_anterior, feriados_trab_actual = _calcular_feriados_trabajados(
        conn, ids, id_profesional, periodo, pierde_descuento, recargo_pct
    )
    descuento_vacaciones = _calcular_descuento_vacaciones(conn, ids, primer_dia_periodo, ultimo_dia_periodo)
    descuento_licencias = _calcular_descuento_licencias(conn, ids, primer_dia_periodo, ultimo_dia_periodo)

    aisladas_mes_anterior = _aisladas_periodo(conn, ids, anio_ant, mes_ant, recargo_pct)
    aisladas_mes_en_curso = _aisladas_periodo(conn, ids, anio, mes, recargo_pct)

    cargos_especiales = obtener_repositorio(conn, "CargoEspecial").listar(
        IdProfesional=id_profesional, PeriodoImputado=periodo
    )
    # pp.CantidadCuotas sumada para #37 (PDF de liquidación: "Cuota N/Total
    # del plan de pagos" en vez de "Cuota N" a secas).
    cuotas_plan = conn.execute(
        """
        SELECT cp.*, pp.CantidadCuotas FROM CuotaPlan cp
        JOIN PlanPago pp ON pp.IdPlan = cp.IdPlan
        WHERE pp.IdProfesional = ? AND cp.PeriodoImputado = ? AND cp.Pagado = 0
        """,
        (id_profesional, periodo),
    ).fetchall()

    liquidacion = Liquidacion(
        id_profesional=id_profesional, periodo=periodo, bruto=bruto,
        horas_semanales=tramos[0].horas_semanales if tramos else 0.0,
        descuento_horas_pct=tramos[0].descuento_pct if tramos else 0.0,
        subtotal_reserva=subtotal_reserva, saldo_anterior=saldo_anterior, tramos=tramos,
        pierde_descuento_horas=pierde_descuento, reversion_descuento=reversion_descuento,
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
    # Redondeo del total a un peso entero (ver docstring de `Liquidacion.
    # ajuste_redondeo`): se calcula al final, con `ajuste_redondeo` todavía
    # en 0 (así `.total` da el valor exacto, con centavos) — la diferencia
    # contra el entero más cercano queda como un ítem más de la cuenta.
    if decimales_total_liquidacion(conn) == 0:
        total_exacto = liquidacion.total
        liquidacion.ajuste_redondeo = round(total_exacto) - total_exacto
    return liquidacion


def emitir_liquidacion(
    conn: sqlite3.Connection, *, id_profesional: int, periodo: str, fecha_emision: str | None = None,
    nombre_archivo: str | None = None,
) -> tuple[int, Liquidacion]:
    """Calcula la liquidación, la persiste en LiquidacionEmitida y acredita
    lo generado a SaldoCuentaActual. No toca SaldoCuentaAnterior (eso es
    responsabilidad del avance de mes). Si ya había una emisión previa para
    el mismo período, se acredita solo el DELTA contra esa emisión, para no
    perder pagos ya registrados contra el mes en curso mientras tanto.

    EsReemision y EstadoEnvio se derivan solos de si ya existía una emisión
    previa para este período (DC-09 §2.1/2.2): si la última ya estaba
    Enviada, la nueva entra como "Regenerada no enviada"; si no, entra como
    "No enviada" (primera vez o todavía pendiente).

    No se puede reemitir un período si ya hay liquidaciones de períodos
    posteriores YA ALCANZADOS por el período operativo (DC-08 §6.2:
    "nunca se puede generar una liquidación de un mes anterior ya
    cerrado"): reabrirlo pisaría con valores de hoy un período que un mes
    posterior ya pudo haber usado como base para sus propios "feriados/
    horas pendientes", duplicando ese descuento.

    Bug real reportado por la clienta: cargar/editar una reserva aislada
    de un mes futuro (ej. diciembre, parado en noviembre) con "Período a
    imputar" = actual dispara `regenerar_si_corresponde` para ESE mes
    futuro (`_resolver_periodo_imputar`, `reservas.py`) — crea una
    `LiquidacionEmitida` de diciembre que es pura previsualización,
    ningún avance de mes la "cerró" todavía. Esa fila bloqueaba reemitir
    noviembre (el período EN CURSO) con el mensaje de "ya hay períodos
    posteriores", pensado para un mes posterior realmente cerrado, no
    para una preview de un mes que ni siquiera llegó. Se acota la
    consulta a `Periodo <= periodo_operativo_actual`: solo cuenta un
    período posterior si el período operativo ya lo alcanzó (ahí sí pudo
    haber usado el período que se quiere reabrir como base de cálculo).

    Segunda vuelta del mismo bug, reportada por la clienta como "saldo
    actual" inflado en algunos profesionales: esa misma
    `LiquidacionEmitida` de diciembre — pura previsualización, sin
    cerrar — SÍ acreditaba su monto a `SaldoCuentaActual`, que en ese
    momento todavía representa SOLO noviembre (el período en curso
    real). El profesional terminaba con los dos meses sumados en el
    mismo campo hasta el próximo avance de mes. Por eso la acreditación
    de más abajo también se acota a `periodo <= periodo_operativo_
    actual`: una preview de un mes que todavía no llegó deja su
    `LiquidacionEmitida`/PDF al día (para que el profesional pueda verla
    si la pide) pero no toca el saldo real todavía — ese crédito llega
    solo, con el delta de siempre, cuando el avance de mes alcance ese
    período y alguien la vuelva a emitir (ya con `SaldoCuentaActual`
    recién puesto en 0 para ese mes)."""
    repo_liq = obtener_repositorio(conn, "LiquidacionEmitida")
    if conn.execute(
        "SELECT 1 FROM LiquidacionEmitida WHERE IdProfesional = ? AND Periodo > ? AND Periodo <= ? LIMIT 1",
        (id_profesional, periodo, periodo_operativo_actual(conn)),
    ).fetchone():
        raise ValueError(
            f"No se puede reemitir la liquidación de {periodo}: ya hay liquidaciones de períodos "
            "posteriores emitidas para este profesional"
        )
    previas = repo_liq.listar(IdProfesional=id_profesional, Periodo=periodo)
    monto_generado_anterior = 0.0
    estado_envio = "No enviada"
    if previas:
        ultima = max(previas, key=lambda f: f["IdLiquidacion"])
        monto_generado_anterior = ultima["MontoGenerado"] or 0.0
        if ultima["EstadoEnvio"] == "Enviada":
            estado_envio = "Regenerada no enviada"

    liquidacion = calcular_liquidacion(conn, id_profesional=id_profesional, periodo=periodo)

    id_liquidacion = repo_liq.crear(
        IdProfesional=id_profesional, Periodo=periodo, FechaEmision=fecha_emision,
        NombreArchivo=nombre_archivo, EsReemision=int(bool(previas)), EstadoEnvio=estado_envio,
        MontoGenerado=liquidacion.monto_generado,
    )

    if periodo <= periodo_operativo_actual(conn):
        delta = liquidacion.monto_generado - monto_generado_anterior
        repo_prof = obtener_repositorio(conn, "Profesional")
        profesional = repo_prof.obtener(id_profesional)
        repo_prof.actualizar(id_profesional, SaldoCuentaActual=(profesional["SaldoCuentaActual"] or 0.0) + delta)

    return id_liquidacion, liquidacion


def marcar_estado_envio(conn: sqlite3.Connection, *, id_profesional: int, periodo: str, enviada: bool) -> None:
    """Check "enviada" del centro de mensajería (sección 6.2): "marcable y
    reversible", habilita la situación 2/4 de esa liquidación. Actúa sobre
    la última emisión del período — no hay otra a la que pueda referirse
    un check que vive fuera de la pantalla de liquidación."""
    repo_liq = obtener_repositorio(conn, "LiquidacionEmitida")
    previas = repo_liq.listar(IdProfesional=id_profesional, Periodo=periodo)
    if not previas:
        raise ValueError(f"Todavía no se emitió ninguna liquidación de {periodo} para este profesional.")
    ultima = max(previas, key=lambda f: f["IdLiquidacion"])
    repo_liq.actualizar(ultima["IdLiquidacion"], EstadoEnvio="Enviada" if enviada else "No enviada")
