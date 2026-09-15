"""Análisis de aumentos (Etapa 5, DC-10 §1).

Proceso separado de la generación de liquidaciones: solo actualiza los
valores de los consultorios (y, si se pide, el esquema de descuentos). Si
ya hay liquidaciones emitidas para el período afectado cuando se confirma
el aumento, se regeneran automáticamente con los valores nuevos (DC-10
§1.4) — para los profesionales que ya la tenían enviada, la reemisión la
marca sola "Regenerada no enviada" (ver `liquidaciones.emitir_liquidacion`).

Si se corre el proceso más de una vez dentro del mismo mes calendario, el
valor "Anterior" de cada consultorio se congela solo en la PRIMERA corrida
— las correcciones posteriores actualizan el "Actual" pero no vuelven a
pisar el "Anterior" (DC-10 §1.3). Se detecta consultando AumentoAplicado
por período.

El esquema de descuentos (EsquemaDescuentos) solo se toca desde acá — es
la única función de negocio que lo modifica, así que en la práctica
"editable solo durante el análisis de aumentos" (DC-10 §1.1) queda
garantizado por construcción, sin necesitar un flag de sesión aparte.

Cada corrida de `confirmar_aumento` deja en `AumentoAplicadoDetalle` una
foto de los valores previos de cada consultorio (y, en `AumentoAplicado`,
qué tramos de esquema reemplazó y qué liquidaciones regeneró) — es lo que
usa `deshacer_ultimo_aumento` para revertir la corrida más reciente sin
tener que recalcular nada a mano: los valores de consultorio se
restauran tal cual estaban, el esquema vuelve a activar los tramos
viejos y borra los nuevos, y las liquidaciones afectadas se vuelven a
emitir (ahora con los valores ya revertidos, así quedan como antes)."""
from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field

from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.liquidaciones import emitir_liquidacion
from app.repositorio.registro import obtener_repositorio


@dataclass
class FilaSimulacion:
    id_consultorio: int
    valor_regular_actual: float
    valor_regular_nuevo: float
    valor_aislada_actual: float
    valor_aislada_nuevo: float

    @property
    def diferencia_regular(self) -> float:
        return self.valor_regular_nuevo - self.valor_regular_actual

    @property
    def diferencia_aislada(self) -> float:
        return self.valor_aislada_nuevo - self.valor_aislada_actual


@dataclass
class ResumenAumento:
    periodo: str
    porcentaje_general: float
    es_correccion_del_mes: bool
    consultorios_actualizados: int = 0
    liquidaciones_regeneradas: list[int] = field(default_factory=list)
    id_aumento: int | None = None


@dataclass
class ResumenDeshacer:
    periodo: str
    consultorios_revertidos: int
    liquidaciones_regeneradas: list[int] = field(default_factory=list)


def _es_correccion_del_mes(conn: sqlite3.Connection, periodo: str) -> bool:
    return bool(obtener_repositorio(conn, "AumentoAplicado").listar(Periodo=periodo))


def _redondear_a_multiplo(valor: float, multiplo: float | None) -> float:
    """Siempre para arriba (pedido de la clienta) — nunca al más cercano
    ni para abajo, así el redondeo nunca deja un valor nuevo por debajo
    de lo que daría el cálculo exacto."""
    if not multiplo:
        return valor
    return math.ceil(valor / multiplo) * multiplo


def simular_aumento(
    conn: sqlite3.Connection, *, porcentaje_general: float, valores_override: dict[int, dict] | None = None,
    porcentajes_override: dict[int, float] | None = None, redondear_a: float | None = None,
    periodo: str | None = None,
) -> list[FilaSimulacion]:
    """Tabla de vista previa (DC-10 §1.2 pasos 2-4): valor actual y valor
    nuevo de cada consultorio, calculado con el % general salvo que el
    consultorio tenga su propio % puntual (`porcentajes_override`, la
    solapa "Aumentos" lo llama "porcentaje diferencial" — pisa al general
    para ese consultorio) o, más específico todavía, un valor final ya
    calculado a mano (`valores_override`, en $ directos, que se toma tal
    cual y no pasa por `redondear_a`).

    `redondear_a`, si se pasa (1/10/100/1000, checkbox "Redondear
    valores" de la solapa "Aumentos"), redondea el valor nuevo calculado
    al múltiplo de ese número — siempre PARA ARRIBA, nunca al más
    cercano (pedido de la clienta).

    Si ya se corrió un aumento este mismo mes (`periodo`, default el mes en
    curso), el % (general o diferencial) se aplica sobre ValorHoraXAnterior
    (el valor congelado ANTES del primer aumento del mes) en vez de sobre
    el Actual — así una corrección reemplaza el cálculo anterior en vez de
    apilarse arriba."""
    periodo = periodo or periodo_actual(conn)
    es_correccion = _es_correccion_del_mes(conn, periodo)
    valores_override = valores_override or {}
    porcentajes_override = porcentajes_override or {}
    filas = []
    for c in obtener_repositorio(conn, "Consultorio").listar():
        base_regular = c["ValorHoraRegularAnterior"] if es_correccion else c["ValorHoraRegularActual"]
        base_aislada = c["ValorHoraAisladaAnterior"] if es_correccion else c["ValorHoraAisladaActual"]
        porcentaje = porcentajes_override.get(c["IdConsultorio"], porcentaje_general)
        override = valores_override.get(c["IdConsultorio"], {})
        valor_reg_nuevo = override.get("regular")
        if valor_reg_nuevo is None:
            valor_reg_nuevo = _redondear_a_multiplo(base_regular * (1 + porcentaje / 100), redondear_a)
        valor_ais_nuevo = override.get("aislada")
        if valor_ais_nuevo is None:
            valor_ais_nuevo = _redondear_a_multiplo(base_aislada * (1 + porcentaje / 100), redondear_a)
        filas.append(FilaSimulacion(
            id_consultorio=c["IdConsultorio"],
            valor_regular_actual=c["ValorHoraRegularActual"], valor_regular_nuevo=valor_reg_nuevo,
            valor_aislada_actual=c["ValorHoraAisladaActual"], valor_aislada_nuevo=valor_ais_nuevo,
        ))
    return filas


def generar_tramos_esquema(
    cantidad_horas: float = 2, porcentaje_descuento: float = 1, porcentaje_tope: float = 25,
) -> list[tuple[float, float, float]]:
    """Genera los tramos (Desde, Hasta, %) del esquema de descuentos a
    partir de los 3 parámetros de la solapa "Esquema de descuentos"
    (DC-10 §1.1): cada `cantidad_horas` semanales regulares reservadas de
    más suma un punto de `porcentaje_descuento`, hasta topar en
    `porcentaje_tope`. Quien reserva hasta `cantidad_horas` (inclusive) no
    tiene descuento (0%) — aclarado por la clienta, que corrigió un
    ejemplo previo donde ese primer tramo daba 1% en vez de 0% — recién a
    partir de ahí entra al primer tramo con descuento. El corte de cada
    tramo es "Desde" EXCLUSIVE / "Hasta" INCLUSIVE, coherente con como lo
    lee `valores.obtener_porcentaje_descuento` ("más de 2 horas 1%, más
    de 4 horas 2%, ...")."""
    tramos: list[tuple[float, float, float]] = [(0, cantidad_horas, 0)]
    if porcentaje_descuento <= 0 or cantidad_horas <= 0:
        return tramos
    n = 1
    porcentaje = 0.0
    while porcentaje < porcentaje_tope and n < 100_000:
        porcentaje = min(n * porcentaje_descuento, porcentaje_tope)
        tramos.append((n * cantidad_horas, (n + 1) * cantidad_horas, porcentaje))
        n += 1
    return tramos


def detectar_parametros_esquema(tramos: list[tuple[float, float, float]]) -> tuple[float, float, float] | None:
    """Intenta reconstruir los 3 parámetros ("Cantidad de horas",
    "Porcentaje descuento", "Porcentaje tope descuento") que generarían
    exactamente estos `tramos` — para que la solapa "Esquema de
    descuentos" pueda mostrar en sus 3 campos el esquema vigente al
    entrar, en vez de arrancar siempre en los valores por defecto.

    No siempre es posible: el esquema vigente puede tener tramos que no
    salen de ningún juego de estos 3 parámetros (ej. un historial viejo
    cargado a mano, de cuando la pantalla todavía tenía el editor libre
    de tramos). En ese caso devuelve None y quien llame decide qué
    mostrar (los valores por defecto, con un aviso). Se verifica por
    "ida y vuelta": se extraen los 3 parámetros candidatos de los
    primeros tramos y se regeneran con `generar_tramos_esquema` — si el
    resultado no coincide exactamente con `tramos`, no hay forma
    confiable de que sean "los mismos" parámetros."""
    if not tramos:
        return None
    ordenados = sorted(tramos, key=lambda t: t[0])
    cantidad_horas = ordenados[0][1] - ordenados[0][0]
    if ordenados[0][0] != 0 or ordenados[0][2] != 0 or cantidad_horas <= 0:
        return None
    porcentaje_tope = ordenados[-1][2]
    porcentaje_descuento = ordenados[1][2] if len(ordenados) > 1 else 0
    candidato = generar_tramos_esquema(
        cantidad_horas=cantidad_horas, porcentaje_descuento=porcentaje_descuento, porcentaje_tope=porcentaje_tope,
    )
    if len(candidato) != len(ordenados) or any(
        not math.isclose(a, b, abs_tol=1e-9) for fc, fo in zip(candidato, ordenados) for a, b in zip(fc, fo)
    ):
        return None
    return (cantidad_horas, porcentaje_descuento, porcentaje_tope)


def actualizar_esquema_descuentos(conn: sqlite3.Connection, tramos: list[tuple[float, float, float]]) -> list[int]:
    """Reemplaza el esquema de descuentos vigente. `tramos` es una lista de
    (HorasSemanalesDesde, HorasSemanalesHasta, PorcentajeDescuento). Los
    tramos viejos no se borran (quedan Activo=0 — es el historial de
    cambios que pide la sección 3.18); los nuevos quedan vigentes desde
    hoy. Devuelve los IdEsquemaDescuento recién creados, para que quien
    llame (`confirmar_aumento`) los pueda guardar y así poder deshacer la
    corrida más adelante."""
    conn.execute("UPDATE EsquemaDescuentos SET Activo = 0 WHERE Activo = 1")
    conn.commit()
    hoy = fecha_actual(conn).isoformat()
    repo = obtener_repositorio(conn, "EsquemaDescuentos")
    nuevos_ids = []
    for desde, hasta, porcentaje in tramos:
        nuevos_ids.append(repo.crear(
            HorasSemanalesDesde=desde, HorasSemanalesHasta=hasta, PorcentajeDescuento=porcentaje,
            FechaVigenciaDesde=hoy, Activo=1,
        ))
    return nuevos_ids


def confirmar_aumento(
    conn: sqlite3.Connection, *, porcentaje_general: float, valores_override: dict[int, dict] | None = None,
    porcentajes_override: dict[int, float] | None = None, redondear_a: float | None = None,
    nuevo_esquema_descuentos: list[tuple[float, float, float]] | None = None,
    periodo: str | None = None, observacion: str | None = None,
) -> ResumenAumento:
    """Confirma el aumento (DC-10 §1.3/§1.4): actualiza valores de
    consultorios, opcionalmente el esquema de descuentos, y regenera las
    liquidaciones ya emitidas del período afectado (default: el mes en
    curso) para que reflejen los valores nuevos."""
    periodo = periodo or periodo_actual(conn)
    es_correccion = _es_correccion_del_mes(conn, periodo)

    filas = simular_aumento(
        conn, porcentaje_general=porcentaje_general, valores_override=valores_override,
        porcentajes_override=porcentajes_override, redondear_a=redondear_a, periodo=periodo,
    )
    hoy = fecha_actual(conn).isoformat()
    id_aumento = obtener_repositorio(conn, "AumentoAplicado").crear(
        Periodo=periodo, PorcentajeGeneral=porcentaje_general, FechaAplicacion=hoy, Observacion=observacion,
    )

    repo_consultorio = obtener_repositorio(conn, "Consultorio")
    repo_detalle = obtener_repositorio(conn, "AumentoAplicadoDetalle")
    for fila in filas:
        consultorio = repo_consultorio.obtener(fila.id_consultorio)
        repo_detalle.crear(
            IdAumento=id_aumento, IdConsultorio=fila.id_consultorio,
            ValorRegularActualPrevio=consultorio["ValorHoraRegularActual"],
            ValorRegularAnteriorPrevio=consultorio["ValorHoraRegularAnterior"],
            ValorAisladaActualPrevio=consultorio["ValorHoraAisladaActual"],
            ValorAisladaAnteriorPrevio=consultorio["ValorHoraAisladaAnterior"],
        )
        campos = {
            "ValorHoraRegularActual": fila.valor_regular_nuevo,
            "ValorHoraAisladaActual": fila.valor_aislada_nuevo,
        }
        if not es_correccion:
            campos["ValorHoraRegularAnterior"] = fila.valor_regular_actual
            campos["ValorHoraAisladaAnterior"] = fila.valor_aislada_actual
        repo_consultorio.actualizar(fila.id_consultorio, **campos)

    esquema_nuevos_ids = None
    esquema_anteriores_ids = None
    if nuevo_esquema_descuentos is not None:
        esquema_anteriores_ids = [
            f["IdEsquemaDescuento"] for f in obtener_repositorio(conn, "EsquemaDescuentos").listar(Activo=1)
        ]
        esquema_nuevos_ids = actualizar_esquema_descuentos(conn, nuevo_esquema_descuentos)

    ids_profesional = {
        f["IdProfesional"] for f in obtener_repositorio(conn, "LiquidacionEmitida").listar(Periodo=periodo)
    }
    liquidaciones_regeneradas = []
    for id_profesional in ids_profesional:
        emitir_liquidacion(conn, id_profesional=id_profesional, periodo=periodo, fecha_emision=hoy)
        liquidaciones_regeneradas.append(id_profesional)

    obtener_repositorio(conn, "AumentoAplicado").actualizar(
        id_aumento,
        EsquemaNuevosIds=json.dumps(esquema_nuevos_ids) if esquema_nuevos_ids else None,
        EsquemaAnterioresIds=json.dumps(esquema_anteriores_ids) if esquema_anteriores_ids else None,
        LiquidacionesRegeneradasJson=json.dumps(liquidaciones_regeneradas) if liquidaciones_regeneradas else None,
    )

    return ResumenAumento(
        periodo=periodo, porcentaje_general=porcentaje_general, es_correccion_del_mes=es_correccion,
        consultorios_actualizados=len(filas), liquidaciones_regeneradas=liquidaciones_regeneradas,
        id_aumento=id_aumento,
    )


def deshacer_ultimo_aumento(conn: sqlite3.Connection) -> ResumenDeshacer:
    """Revierte la corrida más reciente de `confirmar_aumento` (sin
    importar su período): restaura los valores previos de cada
    consultorio afectado desde `AumentoAplicadoDetalle`, si esa corrida
    había reemplazado el esquema de descuentos reactiva los tramos
    viejos y borra los que había creado, y vuelve a emitir las
    liquidaciones que había regenerado — ahora con los valores ya
    revertidos, así quedan como estaban antes de esa corrida."""
    ultimos = obtener_repositorio(conn, "AumentoAplicado").listar()
    if not ultimos:
        raise ValueError("No hay ningún aumento aplicado para deshacer.")
    ultimo = max(ultimos, key=lambda f: f["IdAumento"])
    id_aumento = ultimo["IdAumento"]

    repo_consultorio = obtener_repositorio(conn, "Consultorio")
    detalles = obtener_repositorio(conn, "AumentoAplicadoDetalle").listar(IdAumento=id_aumento)
    for detalle in detalles:
        repo_consultorio.actualizar(
            detalle["IdConsultorio"],
            ValorHoraRegularActual=detalle["ValorRegularActualPrevio"],
            ValorHoraRegularAnterior=detalle["ValorRegularAnteriorPrevio"],
            ValorHoraAisladaActual=detalle["ValorAisladaActualPrevio"],
            ValorHoraAisladaAnterior=detalle["ValorAisladaAnteriorPrevio"],
        )

    if ultimo["EsquemaNuevosIds"]:
        for id_esquema in json.loads(ultimo["EsquemaNuevosIds"]):
            conn.execute("DELETE FROM EsquemaDescuentos WHERE IdEsquemaDescuento = ?", (id_esquema,))
        for id_esquema in json.loads(ultimo["EsquemaAnterioresIds"] or "[]"):
            conn.execute("UPDATE EsquemaDescuentos SET Activo = 1 WHERE IdEsquemaDescuento = ?", (id_esquema,))
        conn.commit()

    hoy = fecha_actual(conn).isoformat()
    liquidaciones_regeneradas = json.loads(ultimo["LiquidacionesRegeneradasJson"] or "[]")
    for id_profesional in liquidaciones_regeneradas:
        emitir_liquidacion(conn, id_profesional=id_profesional, periodo=ultimo["Periodo"], fecha_emision=hoy)

    repo_aumento_detalle = obtener_repositorio(conn, "AumentoAplicadoDetalle")
    for detalle in detalles:
        repo_aumento_detalle.eliminar(detalle["IdAumentoDetalle"])
    obtener_repositorio(conn, "AumentoAplicado").eliminar(id_aumento)

    return ResumenDeshacer(
        periodo=ultimo["Periodo"], consultorios_revertidos=len(detalles),
        liquidaciones_regeneradas=liquidaciones_regeneradas,
    )
