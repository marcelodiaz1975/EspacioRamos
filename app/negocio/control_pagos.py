"""Módulo extendido ME1 — "Control de pagos" (sección 3.35-3.37): control
mes a mes de todo lo que hay que abonar, sea del espacio o personal/
familiar. Dos niveles: `ConceptoControlPago` (el maestro recurrente, ej.
"Edenor") e `InstanciaControlPago` (una fila por Concepto y Período,
generada en blanco al arrancar el período — ver `generar_instancias_
periodo` — y completada/archivada/marcada como abonada mes a mes).

Cuando la Afectación de un concepto es del espacio (Espacio general/
Edificio/Unidad), cada cambio de Importe de una instancia sincroniza un
`GastoOperativo` con Origen="Importado" (ver `sincronizar_gasto_
operativo`) — pedido explícito de la clienta: "me interesaría que lo que
cargo en módulo extendido pase al balance del negocio y no al revés".
Los conceptos personales/familiares/de rodados nunca tocan
`GastoOperativo`."""
from __future__ import annotations

import sqlite3

from app.negocio.gastos_operativos import gasto_en_conflicto
from app.repositorio.registro import obtener_repositorio

TIPOS_AFECTACION = ("Espacio general", "Edificio", "Unidad", "Inmueble personal", "Rodado", "Persona", "Familia")

# Afectaciones del espacio (único subconjunto que sincroniza GastoOperativo
# — ver `sincronizar_gasto_operativo`).
_TIPOS_AFECTACION_ESPACIO = ("Espacio general", "Edificio", "Unidad")

ESTADOS_INSTANCIA = ("Pendiente", "Abonado", "Archivado")

_SIN_CAMBIOS = object()
"""Sentinel para `actualizar_instancia`: distingue "no tocar este campo"
de "ponerlo en blanco" (`None` es un valor real y válido para Vencimiento/
Importe — vaciar un vencimiento ya cargado, por ejemplo)."""


def sanear_afectacion(valores: dict) -> dict:
    """Un concepto apunta a UN solo nivel de Afectación a la vez — fuerza
    a None las referencias que no corresponden al `TipoAfectacion`
    elegido, mismo criterio que `app.negocio.gastos_operativos.
    sanear_alcance`."""
    tipo = valores.get("TipoAfectacion")
    campos_referencia = ("IdEdificio", "IdUnidad", "IdInmueblePersonal", "IdRodado", "IdPersonaFamilia")
    conserva = {
        "Edificio": "IdEdificio", "Unidad": "IdUnidad", "Inmueble personal": "IdInmueblePersonal",
        "Rodado": "IdRodado", "Persona": "IdPersonaFamilia",
    }.get(tipo)
    for campo in campos_referencia:
        if campo != conserva:
            valores[campo] = None
    return valores


def texto_afectacion(conn: sqlite3.Connection, concepto: sqlite3.Row) -> str:
    """Texto legible de la Afectación de un concepto, para mostrar en la
    tabla/filtros de "Carga y control"/"Historial"."""
    tipo = concepto["TipoAfectacion"]
    if tipo == "Espacio general":
        return "Espacio general"
    if tipo == "Edificio":
        fila = obtener_repositorio(conn, "Edificio").obtener(concepto["IdEdificio"])
        return fila["Nombre"] if fila else "Edificio (eliminado)"
    if tipo == "Unidad":
        fila = conn.execute(
            "SELECT u.Departamento, e.Nombre AS NombreEdificio FROM Unidad u "
            "JOIN Edificio e ON e.IdEdificio = u.IdEdificio WHERE u.IdUnidad = ?",
            (concepto["IdUnidad"],),
        ).fetchone()
        return f"{fila['NombreEdificio']} - {fila['Departamento']}" if fila else "Unidad (eliminada)"
    if tipo == "Inmueble personal":
        fila = obtener_repositorio(conn, "InmueblePersonal").obtener(concepto["IdInmueblePersonal"])
        if fila is None:
            return "Inmueble personal (eliminado)"
        localidad = obtener_repositorio(conn, "Localidad").obtener(fila["IdLocalidad"]) if fila["IdLocalidad"] else None
        partes = [p for p in (fila["TipoInmueble"], fila["Direccion"]) if p]
        texto = " ".join(partes)
        return f"{texto}, {localidad['Localidad']}" if localidad else texto
    if tipo == "Rodado":
        fila = obtener_repositorio(conn, "Rodado").obtener(concepto["IdRodado"])
        if fila is None:
            return "Rodado (eliminado)"
        return " ".join(p for p in (fila["Marca"], fila["Modelo"], fila["Dominio"]) if p)
    if tipo == "Persona":
        fila = obtener_repositorio(conn, "PersonaFamilia").obtener(concepto["IdPersonaFamilia"])
        return fila["Nombre"] if fila else "Persona (eliminada)"
    return "Familia"


def crear_concepto(
    conn: sqlite3.Connection, *, nombre: str, categoria: str | None, tipo_afectacion: str,
    id_edificio: int | None = None, id_unidad: int | None = None, id_inmueble_personal: int | None = None,
    id_rodado: int | None = None, id_persona_familia: int | None = None, medio_pago_sugerido: str | None = None,
) -> int:
    if tipo_afectacion not in TIPOS_AFECTACION:
        raise ValueError(f"Tipo de afectación inválido: {tipo_afectacion!r}")
    valores = sanear_afectacion({
        "Nombre": nombre, "Categoria": categoria, "TipoAfectacion": tipo_afectacion,
        "IdEdificio": id_edificio, "IdUnidad": id_unidad, "IdInmueblePersonal": id_inmueble_personal,
        "IdRodado": id_rodado, "IdPersonaFamilia": id_persona_familia, "MedioPagoSugerido": medio_pago_sugerido,
        "Activo": 1,
    })
    return obtener_repositorio(conn, "ConceptoControlPago").crear(**valores)


def editar_concepto(conn: sqlite3.Connection, id_concepto: int, **campos) -> None:
    """Edita los datos del concepto en sí (Nombre/Categoría/Afectación/
    Medio de pago sugerido) — distinto de editar el vencimiento/monto de
    una instancia puntual (ver `actualizar_instancia`). Pedido explícito
    de la clienta: hace falta para cuando algo del concepto cambia (ej.
    se vende una unidad, o se corrige un error de carga)."""
    if "TipoAfectacion" in campos and campos["TipoAfectacion"] not in TIPOS_AFECTACION:
        raise ValueError(f"Tipo de afectación inválido: {campos['TipoAfectacion']!r}")
    if "TipoAfectacion" in campos:
        actual = obtener_repositorio(conn, "ConceptoControlPago").obtener(id_concepto)
        combinado = {**dict(actual), **campos}
        campos = sanear_afectacion(combinado)
    obtener_repositorio(conn, "ConceptoControlPago").actualizar(id_concepto, **campos)


def dar_de_baja_concepto(conn: sqlite3.Connection, id_concepto: int) -> None:
    """Deja de generar instancias nuevas para este concepto (ver
    `generar_instancias_periodo`) — el historial de instancias ya
    generadas no se toca. Distinto de "Archivar" una instancia puntual,
    que solo cierra el mes en curso y el concepto sigue generándose."""
    obtener_repositorio(conn, "ConceptoControlPago").actualizar(id_concepto, Activo=0)


def generar_instancias_periodo(conn: sqlite3.Connection, periodo: str) -> int:
    """Genera una `InstanciaControlPago` en blanco (Vencimiento/Importe
    NULL, Estado "Pendiente", `MedioPago` precargado del sugerido por el
    concepto) para cada concepto Activo que todavía no tenga una
    instancia de este período — pedido explícito de la clienta: "a
    principio de mes yo quiero que en la tabla me cargue todos los
    conceptos, con los vencimientos y los importes en blanco". Se puede
    llamar las veces que haga falta (ej. cada vez que se entra a la
    solapa): es naturalmente idempotente, no duplica nada. Devuelve la
    cantidad de instancias nuevas creadas."""
    conceptos_activos = conn.execute("SELECT IdConcepto FROM ConceptoControlPago WHERE Activo = 1").fetchall()
    ya_generados = {
        f["IdConcepto"] for f in conn.execute(
            "SELECT IdConcepto FROM InstanciaControlPago WHERE Periodo = ?", (periodo,)
        ).fetchall()
    }
    creadas = 0
    for c in conceptos_activos:
        if c["IdConcepto"] in ya_generados:
            continue
        concepto = obtener_repositorio(conn, "ConceptoControlPago").obtener(c["IdConcepto"])
        obtener_repositorio(conn, "InstanciaControlPago").crear(
            IdConcepto=c["IdConcepto"], Periodo=periodo, Estado="Pendiente",
            MedioPago=concepto["MedioPagoSugerido"],
        )
        creadas += 1
    return creadas


def archivar_instancia(conn: sqlite3.Connection, id_instancia: int) -> None:
    """Cierra una instancia sin datos cargados ese mes ("no tengo
    vencimientos de ese concepto este mes") — habilitado solo cuando no
    hay Vencimiento ni Importe cargados, para no poder archivar algo que
    en realidad hay que pagar."""
    instancia = obtener_repositorio(conn, "InstanciaControlPago").obtener(id_instancia)
    if instancia is None:
        raise ValueError(f"No existe la instancia #{id_instancia}")
    if instancia["Vencimiento"] or instancia["Importe"] is not None:
        raise ValueError("No se puede archivar una instancia con vencimiento o importe cargado.")
    obtener_repositorio(conn, "InstanciaControlPago").actualizar(id_instancia, Estado="Archivado")


def marcar_abonada(conn: sqlite3.Connection, id_instancia: int) -> None:
    obtener_repositorio(conn, "InstanciaControlPago").actualizar(id_instancia, Estado="Abonado")


def actualizar_instancia(
    conn: sqlite3.Connection, id_instancia: int, *,
    vencimiento=_SIN_CAMBIOS, importe=_SIN_CAMBIOS, medio_pago=_SIN_CAMBIOS,
) -> None:
    """Edita vencimiento/monto (y opcionalmente el medio de pago) de UNA
    instancia puntual — distinto de `editar_concepto`. Cada parámetro
    que se deja sin pasar queda sin tocar (`_SIN_CAMBIOS`); pasarlo en
    `None` explícitamente SÍ lo vacía (ej. borrar un vencimiento ya
    cargado). Sincroniza `GastoOperativo` después, si corresponde (ver
    `sincronizar_gasto_operativo`)."""
    campos = {}
    if vencimiento is not _SIN_CAMBIOS:
        campos["Vencimiento"] = vencimiento
    if importe is not _SIN_CAMBIOS:
        campos["Importe"] = importe
    if medio_pago is not _SIN_CAMBIOS:
        campos["MedioPago"] = medio_pago
    if campos:
        obtener_repositorio(conn, "InstanciaControlPago").actualizar(id_instancia, **campos)
    sincronizar_gasto_operativo(conn, id_instancia)


def sincronizar_gasto_operativo(conn: sqlite3.Connection, id_instancia: int) -> None:
    """Pedido explícito de la clienta: "me interesaría que lo que cargo
    en módulo extendido pase al balance del negocio y no al revés" — un
    concepto imputado al Espacio (Espacio general/Edificio/Unidad)
    mantiene su propio `GastoOperativo` (Origen="Importado") siempre al
    día con el último Importe cargado en la instancia, esté o no
    abonada todavía. Si el Importe queda en blanco, se borra el
    `GastoOperativo` ya sincronizado (si había uno) para no dejar un
    monto viejo en Balance del negocio. Si ya existe un gasto Manual en
    conflicto (mismo Período+Concepto, cargado aparte antes de que
    existiera este módulo) no se pisa — se respeta la regla de
    `gasto_en_conflicto`, el gasto manual sigue mandando."""
    instancia = obtener_repositorio(conn, "InstanciaControlPago").obtener(id_instancia)
    if instancia is None:
        return
    concepto = obtener_repositorio(conn, "ConceptoControlPago").obtener(instancia["IdConcepto"])
    if concepto is None or concepto["TipoAfectacion"] not in _TIPOS_AFECTACION_ESPACIO:
        return

    repo_gasto = obtener_repositorio(conn, "GastoOperativo")
    existente = next(
        (
            g for g in repo_gasto.listar(Periodo=instancia["Periodo"], Concepto=concepto["Nombre"])
            if g["Origen"] == "Importado"
        ),
        None,
    )
    if instancia["Importe"] is None:
        if existente is not None:
            repo_gasto.eliminar(existente["IdGasto"])
        return

    if gasto_en_conflicto(
        conn, periodo=instancia["Periodo"], concepto=concepto["Nombre"], origen="Importado",
        id_gasto_actual=existente["IdGasto"] if existente else None,
    ):
        return

    valores = {
        "Periodo": instancia["Periodo"], "Categoria": concepto["Categoria"], "Concepto": concepto["Nombre"],
        "Monto": instancia["Importe"], "Alcance": concepto["TipoAfectacion"],
        "IdEdificio": concepto["IdEdificio"], "IdUnidad": concepto["IdUnidad"], "Origen": "Importado",
    }
    if existente is not None:
        repo_gasto.actualizar(existente["IdGasto"], **valores)
    else:
        repo_gasto.crear(**valores)
