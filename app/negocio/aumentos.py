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
"""
from __future__ import annotations

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


def _es_correccion_del_mes(conn: sqlite3.Connection, periodo: str) -> bool:
    return bool(obtener_repositorio(conn, "AumentoAplicado").listar(Periodo=periodo))


def simular_aumento(
    conn: sqlite3.Connection, *, porcentaje_general: float, valores_override: dict[int, dict] | None = None,
    periodo: str | None = None,
) -> list[FilaSimulacion]:
    """Tabla de vista previa (DC-10 §1.2 pasos 2-4): valor actual y valor
    nuevo de cada consultorio, calculado con el % general salvo que haya
    un override manual para ese consultorio puntual.

    Si ya se corrió un aumento este mismo mes (`periodo`, default el mes en
    curso), el % se aplica sobre ValorHoraXAnterior (el valor congelado
    ANTES del primer aumento del mes) en vez de sobre el Actual — así una
    corrección reemplaza el cálculo anterior en vez de apilarse arriba."""
    periodo = periodo or periodo_actual(conn)
    es_correccion = _es_correccion_del_mes(conn, periodo)
    valores_override = valores_override or {}
    filas = []
    for c in obtener_repositorio(conn, "Consultorio").listar():
        base_regular = c["ValorHoraRegularAnterior"] if es_correccion else c["ValorHoraRegularActual"]
        base_aislada = c["ValorHoraAisladaAnterior"] if es_correccion else c["ValorHoraAisladaActual"]
        override = valores_override.get(c["IdConsultorio"], {})
        valor_reg_nuevo = override.get("regular")
        if valor_reg_nuevo is None:
            valor_reg_nuevo = base_regular * (1 + porcentaje_general / 100)
        valor_ais_nuevo = override.get("aislada")
        if valor_ais_nuevo is None:
            valor_ais_nuevo = base_aislada * (1 + porcentaje_general / 100)
        filas.append(FilaSimulacion(
            id_consultorio=c["IdConsultorio"],
            valor_regular_actual=c["ValorHoraRegularActual"], valor_regular_nuevo=valor_reg_nuevo,
            valor_aislada_actual=c["ValorHoraAisladaActual"], valor_aislada_nuevo=valor_ais_nuevo,
        ))
    return filas


def actualizar_esquema_descuentos(conn: sqlite3.Connection, tramos: list[tuple[float, float, float]]) -> None:
    """Reemplaza el esquema de descuentos vigente. `tramos` es una lista de
    (HorasSemanalesDesde, HorasSemanalesHasta, PorcentajeDescuento). Los
    tramos viejos no se borran (quedan Activo=0 — es el historial de
    cambios que pide la sección 3.18); los nuevos quedan vigentes desde
    hoy."""
    conn.execute("UPDATE EsquemaDescuentos SET Activo = 0 WHERE Activo = 1")
    conn.commit()
    hoy = fecha_actual(conn).isoformat()
    repo = obtener_repositorio(conn, "EsquemaDescuentos")
    for desde, hasta, porcentaje in tramos:
        repo.crear(
            HorasSemanalesDesde=desde, HorasSemanalesHasta=hasta, PorcentajeDescuento=porcentaje,
            FechaVigenciaDesde=hoy, Activo=1,
        )


def confirmar_aumento(
    conn: sqlite3.Connection, *, porcentaje_general: float, valores_override: dict[int, dict] | None = None,
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
        conn, porcentaje_general=porcentaje_general, valores_override=valores_override, periodo=periodo,
    )
    repo_consultorio = obtener_repositorio(conn, "Consultorio")
    for fila in filas:
        campos = {
            "ValorHoraRegularActual": fila.valor_regular_nuevo,
            "ValorHoraAisladaActual": fila.valor_aislada_nuevo,
        }
        if not es_correccion:
            campos["ValorHoraRegularAnterior"] = fila.valor_regular_actual
            campos["ValorHoraAisladaAnterior"] = fila.valor_aislada_actual
        repo_consultorio.actualizar(fila.id_consultorio, **campos)

    if nuevo_esquema_descuentos is not None:
        actualizar_esquema_descuentos(conn, nuevo_esquema_descuentos)

    hoy = fecha_actual(conn).isoformat()
    obtener_repositorio(conn, "AumentoAplicado").crear(
        Periodo=periodo, PorcentajeGeneral=porcentaje_general, FechaAplicacion=hoy, Observacion=observacion,
    )

    ids_profesional = {
        f["IdProfesional"] for f in obtener_repositorio(conn, "LiquidacionEmitida").listar(Periodo=periodo)
    }
    liquidaciones_regeneradas = []
    for id_profesional in ids_profesional:
        emitir_liquidacion(conn, id_profesional=id_profesional, periodo=periodo, fecha_emision=hoy)
        liquidaciones_regeneradas.append(id_profesional)

    return ResumenAumento(
        periodo=periodo, porcentaje_general=porcentaje_general, es_correccion_del_mes=es_correccion,
        consultorios_actualizados=len(filas), liquidaciones_regeneradas=liquidaciones_regeneradas,
    )
