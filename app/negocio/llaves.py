"""Llaves (sección 3.7 del documento, modelo aclarado en conversación con la
clienta).

Llave es el TIPO de llave (el patrón/combinación): define Tipo
(Edificio/Unidad/No especificada), a qué edificio(s)/unidad(es) abre
(LlaveAcceso) y su propio valor de depósito. Nunca se entrega directamente.
Las de Tipo Edificio nunca se repiten (un tipo = un edificio, sin compartir
con otro). Las de Tipo Unidad sí pueden repetirse entre sí — el mismo tipo
puede dar acceso a más de una unidad (incluso de edificios distintos) si se
preparó una cerradura gemela.

De cada tipo se sacan copias físicas (LlaveCopia) y esas son las que
circulan de verdad: se entregan y se devuelven (LlaveProfesional cuelga de
la copia, no del tipo), porque puede haber varias copias del mismo tipo
repartidas a distintos profesionales a la vez — un titular por COPIA a la
vez, no por tipo.

El depósito cobrado y el reintegro se reflejan en la liquidación del
profesional como CargoEspecial (Débito/Crédito) ligado a IdLlave (el tipo,
no la copia puntual — el valor de depósito es una propiedad del tipo) — es
el mismo mecanismo genérico de la sección 3.15 (ya usado en Etapa 4), no
hace falta un camino de facturación aparte para las llaves.
"""
from __future__ import annotations

import sqlite3

from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.pagos import crear_cargo_especial
from app.repositorio.registro import obtener_repositorio


def crear_llave(
    conn: sqlite3.Connection, *, descripcion: str | None = None, tipo: str = "No especificada",
    valor_deposito_actual: float = 0.0,
) -> int:
    repo = obtener_repositorio(conn, "Llave")
    return repo.crear(Descripcion=descripcion, Tipo=tipo, ValorDepositoActual=valor_deposito_actual, Activo=1)


def agregar_acceso_llave(
    conn: sqlite3.Connection, *, id_llave: int, id_edificio: int, id_unidad: int | None = None,
    descripcion_acceso: str | None = None,
) -> int:
    """Sección 3.7: valida el alcance según el Tipo de la llave antes de
    agregar el acceso (LlaveAcceso). Una llave de Tipo Edificio abre un
    solo edificio — no puede tener accesos a más de uno distinto. Una de
    Tipo Unidad apunta a una unidad puntual — "todas las unidades del
    edificio" (IdUnidad NULL) no tiene sentido para ese tipo. Tipo No
    especificada no valida nada (alcance libre)."""
    llave = obtener_repositorio(conn, "Llave").obtener(id_llave)
    if llave is None:
        raise ValueError(f"No existe la llave #{id_llave}")

    if llave["Tipo"] == "Edificio":
        edificios_actuales = {a["IdEdificio"] for a in obtener_repositorio(conn, "LlaveAcceso").listar(IdLlave=id_llave)}
        if edificios_actuales and edificios_actuales != {id_edificio}:
            raise ValueError(
                "Una llave de Tipo Edificio solo puede dar acceso a un edificio; "
                "esta ya tiene un acceso configurado a otro distinto"
            )
    elif llave["Tipo"] == "Unidad" and id_unidad is None:
        raise ValueError('Una llave de Tipo Unidad necesita una unidad puntual, no "todas las unidades"')

    return obtener_repositorio(conn, "LlaveAcceso").crear(
        IdLlave=id_llave, IdEdificio=id_edificio, IdUnidad=id_unidad, DescripcionAcceso=descripcion_acceso,
    )


def crear_copia_llave(conn: sqlite3.Connection, *, id_llave: int, identificador: str | None = None) -> int:
    """Da de alta una copia física nueva de un tipo de llave ya existente.
    Si no se da un identificador, se sugiere uno correlativo ("Copia N")
    según cuántas copias tiene ya ese tipo — el operador lo puede
    reemplazar por el que use físicamente (número de llavero, etc.)."""
    llave = obtener_repositorio(conn, "Llave").obtener(id_llave)
    if llave is None:
        raise ValueError(f"No existe la llave #{id_llave}")
    if identificador is None:
        cantidad = len(obtener_repositorio(conn, "LlaveCopia").listar(IdLlave=id_llave))
        identificador = f"Copia {cantidad + 1}"
    return obtener_repositorio(conn, "LlaveCopia").crear(IdLlave=id_llave, Identificador=identificador, Activo=1)


def _titular_actual(conn: sqlite3.Connection, id_copia: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM LlaveProfesional WHERE IdLlaveCopia = ? AND FechaDevolucion IS NULL", (id_copia,)
    ).fetchone()


def entregar_llave(
    conn: sqlite3.Connection, *, id_copia: int, id_profesional: int, fecha_entrega: str | None = None,
    cobrar_deposito: bool = False, monto_cobrado: float | None = None,
    periodo_imputado: str | None = None, observacion: str | None = None,
) -> int:
    titular = _titular_actual(conn, id_copia)
    if titular is not None:
        raise ValueError(
            f"La copia #{id_copia} ya tiene un titular (profesional #{titular['IdProfesional']}); "
            "hay que registrar la devolución antes de entregarla a otro profesional"
        )

    copia = obtener_repositorio(conn, "LlaveCopia").obtener(id_copia)
    if copia is None:
        raise ValueError(f"No existe la copia #{id_copia}")
    llave = obtener_repositorio(conn, "Llave").obtener(copia["IdLlave"])
    if llave is None:
        raise ValueError(f"No existe la llave #{copia['IdLlave']}")

    if cobrar_deposito and monto_cobrado is None:
        monto_cobrado = llave["ValorDepositoActual"]

    repo = obtener_repositorio(conn, "LlaveProfesional")
    id_llave_profesional = repo.crear(
        IdLlaveCopia=id_copia, IdProfesional=id_profesional,
        FechaEntrega=fecha_entrega or fecha_actual(conn).isoformat(),
        DepositoCobrado=int(cobrar_deposito), MontoCobrado=monto_cobrado, Observacion=observacion,
    )

    if cobrar_deposito and monto_cobrado:
        crear_cargo_especial(
            conn, id_profesional=id_profesional, tipo="Débito",
            concepto=f"depósito llave {llave['Descripcion'] or llave['IdLlave']}", monto=monto_cobrado,
            periodo_imputado=periodo_imputado or periodo_actual(conn), id_llave=llave["IdLlave"],
        )
    return id_llave_profesional


def devolver_llave(
    conn: sqlite3.Connection, id_llave_profesional: int, *, fecha_devolucion: str | None = None,
    reintegrar_deposito: bool = False, monto_reintegrado: float | None = None,
    periodo_imputado: str | None = None,
) -> None:
    repo = obtener_repositorio(conn, "LlaveProfesional")
    tenencia = repo.obtener(id_llave_profesional)
    if tenencia is None:
        raise ValueError(f"No existe la entrega de llave #{id_llave_profesional}")
    if tenencia["FechaDevolucion"] is not None:
        raise ValueError(f"La entrega #{id_llave_profesional} ya tiene devolución registrada")

    if reintegrar_deposito and monto_reintegrado is None:
        monto_reintegrado = tenencia["MontoCobrado"] or 0.0

    repo.actualizar(
        id_llave_profesional, FechaDevolucion=fecha_devolucion or fecha_actual(conn).isoformat(),
        DepositoReintegrado=int(reintegrar_deposito), MontoReintegrado=monto_reintegrado,
    )

    if reintegrar_deposito and monto_reintegrado:
        copia = obtener_repositorio(conn, "LlaveCopia").obtener(tenencia["IdLlaveCopia"])
        llave = obtener_repositorio(conn, "Llave").obtener(copia["IdLlave"])
        crear_cargo_especial(
            conn, id_profesional=tenencia["IdProfesional"], tipo="Crédito",
            concepto=f"reintegro llave {llave['Descripcion'] or llave['IdLlave']}", monto=-monto_reintegrado,
            periodo_imputado=periodo_imputado or periodo_actual(conn), id_llave=llave["IdLlave"],
        )
