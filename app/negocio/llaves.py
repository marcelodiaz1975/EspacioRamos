"""Llaves (sección 3.7 del documento).

Un titular por llave a la vez — no se puede entregar una llave que ya
tiene un titular sin devolución registrada (FechaDevolucion IS NULL). Alta
de la llave posible en el momento mismo de la entrega, sin stock previo
cargado.

El depósito cobrado y el reintegro se reflejan en la liquidación del
profesional como CargoEspecial (Débito/Crédito) ligado a IdLlave — es el
mismo mecanismo genérico de la sección 3.15 (ya usado en Etapa 4), no hace
falta un camino de facturación aparte para las llaves.
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


def _titular_actual(conn: sqlite3.Connection, id_llave: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM LlaveProfesional WHERE IdLlave = ? AND FechaDevolucion IS NULL", (id_llave,)
    ).fetchone()


def entregar_llave(
    conn: sqlite3.Connection, *, id_llave: int, id_profesional: int, fecha_entrega: str | None = None,
    cobrar_deposito: bool = False, monto_cobrado: float | None = None,
    periodo_imputado: str | None = None, observacion: str | None = None,
) -> int:
    titular = _titular_actual(conn, id_llave)
    if titular is not None:
        raise ValueError(
            f"La llave #{id_llave} ya tiene un titular (profesional #{titular['IdProfesional']}); "
            "hay que registrar la devolución antes de entregarla a otro profesional"
        )

    llave = obtener_repositorio(conn, "Llave").obtener(id_llave)
    if llave is None:
        raise ValueError(f"No existe la llave #{id_llave}")

    if cobrar_deposito and monto_cobrado is None:
        monto_cobrado = llave["ValorDepositoActual"]

    repo = obtener_repositorio(conn, "LlaveProfesional")
    id_llave_profesional = repo.crear(
        IdLlave=id_llave, IdProfesional=id_profesional,
        FechaEntrega=fecha_entrega or fecha_actual(conn).isoformat(),
        DepositoCobrado=int(cobrar_deposito), MontoCobrado=monto_cobrado, Observacion=observacion,
    )

    if cobrar_deposito and monto_cobrado:
        crear_cargo_especial(
            conn, id_profesional=id_profesional, tipo="Débito",
            concepto=f"depósito llave {llave['Descripcion'] or id_llave}", monto=monto_cobrado,
            periodo_imputado=periodo_imputado or periodo_actual(conn), id_llave=id_llave,
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
        llave = obtener_repositorio(conn, "Llave").obtener(tenencia["IdLlave"])
        crear_cargo_especial(
            conn, id_profesional=tenencia["IdProfesional"], tipo="Crédito",
            concepto=f"reintegro llave {llave['Descripcion'] or tenencia['IdLlave']}", monto=-monto_reintegrado,
            periodo_imputado=periodo_imputado or periodo_actual(conn), id_llave=tenencia["IdLlave"],
        )
