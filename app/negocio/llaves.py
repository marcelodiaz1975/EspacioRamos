"""Llaves (sección 3.7 del documento, replanteado en conversación con la
clienta — segunda vuelta).

Llave es el TIPO de llave (el patrón/combinación): define Tipo
(Edificio/Unidad/No especificada), a qué edificio(s)/unidad(es) abre
(LlaveAcceso) y su propio valor de depósito. Su Nombre se arma solo
("Tipo llave E1"/"U3"/...) a partir de Tipo + un correlativo por letra —
no es editable a mano.

Las copias físicas no tienen identidad individual (para la clienta son
todas iguales, se entregan sueltas). LlaveMovimiento es un libro único de
movimientos por Tipo de llave:

- Ingreso: entra stock nuevo (Cantidad puede ser > 1, para cargar varias
  copias de una sola vez).
- Asignación: se le da una copia a un profesional (requiere que haya
  copias disponibles).
- Devolución: la copia vuelve al stock — cierra una Asignación abierta
  (referenciada en IdAsignacion), con reintegro de depósito opcional.
- Pérdida: la copia se da de baja para siempre. Si tenía un profesional a
  cargo (cierra esa Asignación abierta) nunca reintegra el depósito (es
  responsabilidad del profesional cuidar su juego; si se le da una copia
  nueva, es una Asignación nueva e independiente que vuelve a cobrar
  depósito); si todavía era stock sin asignar (ej. se traspapela en el
  cajón), se da de baja directo del stock disponible, sin profesional ni
  depósito de por medio.

Una Asignación sin ninguna Devolución/Pérdida que la referencie está
"abierta" (esa copia sigue en poder del profesional). El depósito cobrado
y el reintegro se reflejan en la liquidación del profesional como
CargoEspecial (Débito/Crédito) ligado a IdLlave (el tipo, no el
movimiento puntual) — es el mismo mecanismo genérico de la sección 3.15.
"""
from __future__ import annotations

import sqlite3

from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.pagos import crear_cargo_especial
from app.repositorio.registro import obtener_repositorio

_LETRA_POR_TIPO = {"Edificio": "E", "Unidad": "U", "No especificada": "N"}


def siguiente_nombre_llave(conn: sqlite3.Connection, tipo: str) -> str:
    """Arma el nombre correlativo por letra ("Tipo llave E1", "Tipo llave
    U3", ...) que le va a corresponder al próximo Tipo de llave que se cree
    con ese Tipo. Expuesto aparte de crear_llave para que la pantalla
    pueda mostrarlo como previsualización antes de confirmar el alta."""
    letra = _LETRA_POR_TIPO[tipo]
    cantidad = len(obtener_repositorio(conn, "Llave").listar(Tipo=tipo))
    return f"Tipo llave {letra}{cantidad + 1}"


def _lugar_llave_texto(conn: sqlite3.Connection, llave: sqlite3.Row) -> str:
    """Texto que describe a qué abre un Tipo de llave, para el profesional
    en el concepto de depósito/reintegro de la liquidación — distinto del
    Nombre interno ("Tipo llave U1"), que es solo para uso administrativo
    en pantalla. Si el tipo abre más de una unidad a la vez (cerradura
    gemela, sea del mismo edificio o de otro) no se puede nombrar una
    sola sin ambigüedad, así que queda genérico ("unidad", sin precisar
    cuál) — confirmado por la clienta."""
    accesos = obtener_repositorio(conn, "LlaveAcceso").listar(IdLlave=llave["IdLlave"])
    if llave["Tipo"] == "Edificio":
        if not accesos:
            return "edificio"
        edificio = obtener_repositorio(conn, "Edificio").obtener(accesos[0]["IdEdificio"])
        return f"edificio {edificio['Nombre']}" if edificio else "edificio"
    if llave["Tipo"] == "Unidad":
        if len(accesos) != 1 or accesos[0]["IdUnidad"] is None:
            return "unidad"
        acceso = accesos[0]
        edificio = obtener_repositorio(conn, "Edificio").obtener(acceso["IdEdificio"])
        unidad = obtener_repositorio(conn, "Unidad").obtener(acceso["IdUnidad"])
        if unidad is None or edificio is None:
            return "unidad"
        return f"unidad del {unidad['Departamento']} del edificio {edificio['Nombre']}"
    return ""


def crear_llave(
    conn: sqlite3.Connection, *, tipo: str = "No especificada", valor_deposito_actual: float = 0.0,
    observacion: str | None = None,
) -> int:
    nombre = siguiente_nombre_llave(conn, tipo)
    repo = obtener_repositorio(conn, "Llave")
    return repo.crear(
        Nombre=nombre, Tipo=tipo, ValorDepositoActual=valor_deposito_actual, Observacion=observacion, Activo=1,
    )


def agregar_acceso_llave(
    conn: sqlite3.Connection, *, id_llave: int, id_edificio: int, id_unidad: int | None = None,
    nombre: str | None = None, observacion: str | None = None,
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
        IdLlave=id_llave, IdEdificio=id_edificio, IdUnidad=id_unidad, Nombre=nombre, Observacion=observacion,
    )


def _asignaciones_cerradas(conn: sqlite3.Connection) -> set[int]:
    return {
        f["IdAsignacion"] for f in conn.execute(
            "SELECT IdAsignacion FROM LlaveMovimiento WHERE IdAsignacion IS NOT NULL"
        ).fetchall()
    }


def resumen_stock(conn: sqlite3.Connection, id_llave: int) -> dict:
    """Ingresadas/perdidas/existentes/asignadas/disponibles de un Tipo de
    llave, calculadas en vivo a partir del libro de movimientos (no se
    guardan como campos aparte, para que nunca puedan desincronizarse)."""
    movimientos = obtener_repositorio(conn, "LlaveMovimiento").listar(IdLlave=id_llave)
    ingresadas = sum(m["Cantidad"] for m in movimientos if m["Tipo"] == "Ingreso")
    perdidas = sum(m["Cantidad"] for m in movimientos if m["Tipo"] == "Pérdida")
    cerradas = _asignaciones_cerradas(conn)
    asignadas = sum(1 for m in movimientos if m["Tipo"] == "Asignación" and m["IdMovimiento"] not in cerradas)
    existentes = ingresadas - perdidas
    return {
        "ingresadas": ingresadas, "perdidas": perdidas, "existentes": existentes,
        "asignadas": asignadas, "disponibles": existentes - asignadas,
    }


def ingresar_copias(
    conn: sqlite3.Connection, *, id_llave: int, cantidad: int = 1, fecha: str | None = None,
    observacion: str | None = None,
) -> int:
    if cantidad < 1:
        raise ValueError("La cantidad a ingresar tiene que ser al menos 1")
    llave = obtener_repositorio(conn, "Llave").obtener(id_llave)
    if llave is None:
        raise ValueError(f"No existe la llave #{id_llave}")
    return obtener_repositorio(conn, "LlaveMovimiento").crear(
        IdLlave=id_llave, Tipo="Ingreso", Fecha=fecha or fecha_actual(conn).isoformat(),
        Cantidad=cantidad, Observacion=observacion,
    )


def asignar_llave(
    conn: sqlite3.Connection, *, id_llave: int, id_profesional: int, fecha: str | None = None,
    cobrar_deposito: bool = False, monto_cobrado: float | None = None,
    periodo_imputado: str | None = None, observacion: str | None = None,
) -> int:
    llave = obtener_repositorio(conn, "Llave").obtener(id_llave)
    if llave is None:
        raise ValueError(f"No existe la llave #{id_llave}")
    if resumen_stock(conn, id_llave)["disponibles"] <= 0:
        raise ValueError(f"No hay copias disponibles de {llave['Nombre']} para asignar")

    if cobrar_deposito and monto_cobrado is None:
        monto_cobrado = llave["ValorDepositoActual"]

    repo = obtener_repositorio(conn, "LlaveMovimiento")
    id_movimiento = repo.crear(
        IdLlave=id_llave, Tipo="Asignación", Fecha=fecha or fecha_actual(conn).isoformat(),
        IdProfesional=id_profesional, Cantidad=1,
        DepositoCobrado=int(cobrar_deposito), MontoCobrado=monto_cobrado, Observacion=observacion,
    )

    if cobrar_deposito and monto_cobrado:
        concepto = f"Depósito llave {_lugar_llave_texto(conn, llave)}".rstrip()
        crear_cargo_especial(
            conn, id_profesional=id_profesional, tipo="Débito",
            concepto=concepto, monto=monto_cobrado,
            periodo_imputado=periodo_imputado or periodo_actual(conn), id_llave=id_llave,
        )
    return id_movimiento


def _asignacion_abierta(conn: sqlite3.Connection, id_asignacion: int) -> sqlite3.Row:
    asignacion = obtener_repositorio(conn, "LlaveMovimiento").obtener(id_asignacion)
    if asignacion is None or asignacion["Tipo"] != "Asignación":
        raise ValueError(f"No existe la asignación #{id_asignacion}")
    if id_asignacion in _asignaciones_cerradas(conn):
        raise ValueError(f"La asignación #{id_asignacion} ya tiene una devolución o pérdida registrada")
    return asignacion


def devolver_llave(
    conn: sqlite3.Connection, id_asignacion: int, *, fecha: str | None = None,
    reintegrar_deposito: bool = False, monto_reintegrado: float | None = None,
    periodo_imputado: str | None = None, observacion: str | None = None,
) -> int:
    asignacion = _asignacion_abierta(conn, id_asignacion)
    llave = obtener_repositorio(conn, "Llave").obtener(asignacion["IdLlave"])

    if reintegrar_deposito and monto_reintegrado is None:
        monto_reintegrado = asignacion["MontoCobrado"] or 0.0

    id_movimiento = obtener_repositorio(conn, "LlaveMovimiento").crear(
        IdLlave=asignacion["IdLlave"], Tipo="Devolución", Fecha=fecha or fecha_actual(conn).isoformat(),
        IdProfesional=asignacion["IdProfesional"], Cantidad=1, IdAsignacion=id_asignacion,
        DepositoReintegrado=int(reintegrar_deposito), MontoReintegrado=monto_reintegrado, Observacion=observacion,
    )

    if reintegrar_deposito and monto_reintegrado:
        concepto = f"Reintegro depósito llave {_lugar_llave_texto(conn, llave)}".rstrip()
        crear_cargo_especial(
            conn, id_profesional=asignacion["IdProfesional"], tipo="Crédito",
            concepto=concepto, monto=-monto_reintegrado,
            periodo_imputado=periodo_imputado or periodo_actual(conn), id_llave=llave["IdLlave"],
        )
    return id_movimiento


def registrar_perdida(
    conn: sqlite3.Connection, *, id_asignacion: int | None = None, id_llave: int | None = None,
    cantidad: int = 1, fecha: str | None = None, observacion: str | None = None,
) -> int:
    """Dos formas de perder una copia:

    - `id_asignacion`: la tenía un profesional (cierra esa Asignación,
      igual que una Devolución). El depósito cobrado queda perdido, nunca
      se reintegra (responsabilidad del profesional cuidar su juego de
      llaves). Si más adelante se le da una copia nueva, es una
      asignación nueva e independiente que vuelve a cobrar depósito.
    - `id_llave` + `cantidad`: se pierde/extravía stock que todavía no se
      había asignado a nadie (ej. se traspapelan copias en el cajón) — no
      hay profesional ni depósito involucrado, solo se da de baja del
      stock disponible."""
    if id_asignacion is not None:
        asignacion = _asignacion_abierta(conn, id_asignacion)
        return obtener_repositorio(conn, "LlaveMovimiento").crear(
            IdLlave=asignacion["IdLlave"], Tipo="Pérdida", Fecha=fecha or fecha_actual(conn).isoformat(),
            IdProfesional=asignacion["IdProfesional"], Cantidad=1, IdAsignacion=id_asignacion,
            Observacion=observacion,
        )
    if id_llave is None:
        raise ValueError("Hay que indicar una asignación abierta o un Tipo de llave")
    if cantidad < 1:
        raise ValueError("La cantidad a dar de baja tiene que ser al menos 1")
    disponibles = resumen_stock(conn, id_llave)["disponibles"]
    if cantidad > disponibles:
        raise ValueError(f"Solo hay {disponibles} copias disponibles para dar de baja")
    return obtener_repositorio(conn, "LlaveMovimiento").crear(
        IdLlave=id_llave, Tipo="Pérdida", Fecha=fecha or fecha_actual(conn).isoformat(),
        Cantidad=cantidad, Observacion=observacion,
    )
