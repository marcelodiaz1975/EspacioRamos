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
from datetime import date

from app.negocio.dias import fecha_actual, periodo_actual, sumar_meses
from app.negocio.gastos_operativos import gasto_en_conflicto
from app.repositorio.registro import obtener_repositorio

TIPOS_AFECTACION = ("Espacio general", "Edificio", "Unidad", "Inmueble personal", "Rodado", "Persona", "Familia")

# Afectaciones del espacio (único subconjunto que sincroniza GastoOperativo
# — ver `sincronizar_gasto_operativo`).
_TIPOS_AFECTACION_ESPACIO = ("Espacio general", "Edificio", "Unidad")

ESTADOS_INSTANCIA = ("Pendiente", "Abonado", "Archivado")


def es_medio_pago_tarjeta(medio_pago: str | None) -> bool:
    """Pedido explícito de la clienta: los conceptos a debitar por
    tarjeta ("Tarjeta Bco X" en `MedioPagoControlPagos`, ver `seed.py`)
    se tratan distinto de los que se abonan en forma manual/débito de
    una caja de ahorro ("CA Bco X") o "Pago manual" — no por nombre
    exacto (el combo de Medio de pago es editable, la clienta puede
    agregar valores nuevos), sino por contener "tarjeta", mismo
    criterio que `_es_transferencia`/`_es_sobre` en `app/gui/pantallas/
    pagos.py`."""
    return "tarjeta" in (medio_pago or "").lower()

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


def _cuenta_id_heredada(conn: sqlite3.Connection, id_concepto: int) -> str | None:
    """"Cuenta/Id" (`InstanciaControlPago.CampoLibre1`, reusado — pedido
    explícito de la clienta) es una referencia estable del concepto (el
    número de cuenta o servicio de "Edenor", por ejemplo no cambia mes a
    mes), pero vive en la tabla de instancias, no en `ConceptoControlPago`
    — se hereda de la instancia más reciente del mismo concepto que la
    tenga cargada, para no tener que volver a tipearla cada período."""
    filas = obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto)
    con_dato = [f for f in filas if f["CampoLibre1"]]
    if not con_dato:
        return None
    return max(con_dato, key=lambda f: f["IdInstancia"])["CampoLibre1"]


def generar_instancias_periodo(conn: sqlite3.Connection, periodo: str) -> int:
    """Genera una `InstanciaControlPago` en blanco (Vencimiento/Importe
    NULL, Estado "Pendiente", `MedioPago` precargado del sugerido por el
    concepto, "Cuenta/Id" heredada de la instancia más reciente del
    mismo concepto que la tenga — ver `_cuenta_id_heredada`) para cada
    concepto Activo que todavía no tenga una instancia de este período
    — pedido explícito de la clienta: "a principio de mes yo quiero que
    en la tabla me cargue todos los conceptos, con los vencimientos y
    los importes en blanco". Se puede llamar las veces que haga falta
    (ej. cada vez que se entra a la solapa): es naturalmente idempotente,
    no duplica nada. Devuelve la cantidad de instancias nuevas creadas."""
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
            MedioPago=concepto["MedioPagoSugerido"], CampoLibre1=_cuenta_id_heredada(conn, c["IdConcepto"]),
        )
        creadas += 1
    return creadas


def archivar_instancia(conn: sqlite3.Connection, id_instancia: int) -> None:
    """Cierra una instancia sin datos cargados ese mes ("no tengo
    vencimientos de ese concepto este mes") — habilitado solo cuando no
    hay Vencimiento ni Importe cargados, para no poder archivar algo que
    en realidad hay que pagar. Botón manual de una fila puntual — a
    diferencia de un concepto Pendiente sin tocar, que ya no se archiva
    solo al avanzar de mes (pedido explícito de la clienta: queda en
    pantalla hasta que ella decida qué hacer con él)."""
    instancia = obtener_repositorio(conn, "InstanciaControlPago").obtener(id_instancia)
    if instancia is None:
        raise ValueError(f"No existe la instancia #{id_instancia}")
    if instancia["Vencimiento"] or instancia["Importe"] is not None:
        raise ValueError("No se puede archivar una instancia con vencimiento o importe cargado.")
    obtener_repositorio(conn, "InstanciaControlPago").actualizar(id_instancia, Estado="Archivado")


def marcar_abonada(conn: sqlite3.Connection, id_instancia: int) -> None:
    obtener_repositorio(conn, "InstanciaControlPago").actualizar(id_instancia, Estado="Abonado")


def duplicar_para_periodo_proximo(conn: sqlite3.Connection, id_instancia: int) -> int:
    """Pedido explícito de la clienta: "por si ya tengo la información
    para adelantar" un concepto del período en curso — duplica la
    instancia elegida al período siguiente, EN BLANCO (solo con el
    Medio de pago sugerido del concepto, igual que `generar_instancias_
    periodo`) para que se cargue a mano el vencimiento/importe real ya
    conocido. Nunca copia Vencimiento/Importe de la instancia de
    origen — confirmado explícitamente con la clienta. "Cuenta/Id"
    (`CampoLibre1`) SÍ se copia: es una referencia estable del
    concepto, no un dato del período (mismo criterio que la herencia de
    `generar_instancias_periodo`, ver `_cuenta_id_heredada`). Devuelve
    el `IdInstancia` nuevo."""
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancia = repo.obtener(id_instancia)
    if instancia is None:
        raise ValueError(f"No existe la instancia #{id_instancia}")
    periodo_proximo = sumar_meses(instancia["Periodo"], 1)
    if repo.listar(IdConcepto=instancia["IdConcepto"], Periodo=periodo_proximo):
        raise ValueError("Ya existe un registro de este concepto para el período próximo.")
    concepto = obtener_repositorio(conn, "ConceptoControlPago").obtener(instancia["IdConcepto"])
    return repo.crear(
        IdConcepto=instancia["IdConcepto"], Periodo=periodo_proximo, Estado="Pendiente",
        MedioPago=concepto["MedioPagoSugerido"] if concepto else None, CampoLibre1=instancia["CampoLibre1"],
    )


def eliminar_instancia_duplicada(conn: sqlite3.Connection, id_instancia: int) -> None:
    """Deshace un "Duplicar para período próximo" hecho por error — a
    diferencia de `archivar_instancia` (que solo cambia el Estado), esto
    borra la fila entera: no es historial real, es un duplicado que
    nunca debió existir. Si ya había sincronizado un `GastoOperativo`
    (Importe cargado antes de borrarla), también se borra ese gasto —
    mismo criterio que `sincronizar_gasto_operativo` cuando el Importe
    se vacía."""
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancia = repo.obtener(id_instancia)
    if instancia is None:
        raise ValueError(f"No existe la instancia #{id_instancia}")
    concepto = obtener_repositorio(conn, "ConceptoControlPago").obtener(instancia["IdConcepto"])
    if concepto is not None and concepto["TipoAfectacion"] in _TIPOS_AFECTACION_ESPACIO:
        repo_gasto = obtener_repositorio(conn, "GastoOperativo")
        existente = next(
            (
                g for g in repo_gasto.listar(
                    Periodo=instancia["Periodo"], IdConceptoControlPago=concepto["IdConcepto"],
                )
                if g["Origen"] == "Importado"
            ),
            None,
        )
        if existente is not None:
            repo_gasto.eliminar(existente["IdGasto"])
    repo.eliminar(id_instancia)


def actualizar_instancia(
    conn: sqlite3.Connection, id_instancia: int, *,
    vencimiento=_SIN_CAMBIOS, importe=_SIN_CAMBIOS, medio_pago=_SIN_CAMBIOS, estado=_SIN_CAMBIOS,
    cuenta_id=_SIN_CAMBIOS, numero_transaccion=_SIN_CAMBIOS,
) -> None:
    """Edita vencimiento/monto (y opcionalmente el medio de pago, el
    Estado y/o "Cuenta/Id"/"N° transacción") de UNA instancia puntual —
    distinto de `editar_concepto`. Cada parámetro que se deja sin pasar
    queda sin tocar (`_SIN_CAMBIOS`); pasarlo en `None` explícitamente
    SÍ lo vacía (ej. borrar un vencimiento ya cargado). `estado` lo usa
    "Editar registro" de la solapa "Historial" (vencimiento+importe+
    estado juntos, para poder reabrir algo que el cierre de mes archivó
    de más). `cuenta_id` mapea a `CampoLibre1` (reusado — pedido
    explícito de la clienta, ver `_cuenta_id_heredada`). `numero_
    transaccion` mapea a `CampoLibre2` — pedido explícito de la
    clienta ("por si el día de mañana tengo que consultar"): texto
    libre guardado por instancia, SIN mostrarse en ninguna tabla ni
    heredarse de un período al siguiente (a diferencia de Cuenta/Id,
    el número de operación es propio de CADA pago puntual). Sincroniza
    `GastoOperativo` después, si corresponde (ver `sincronizar_gasto_
    operativo`)."""
    campos = {}
    if vencimiento is not _SIN_CAMBIOS:
        campos["Vencimiento"] = vencimiento
    if importe is not _SIN_CAMBIOS:
        campos["Importe"] = importe
    if medio_pago is not _SIN_CAMBIOS:
        campos["MedioPago"] = medio_pago
    if cuenta_id is not _SIN_CAMBIOS:
        campos["CampoLibre1"] = cuenta_id
    if numero_transaccion is not _SIN_CAMBIOS:
        campos["CampoLibre2"] = numero_transaccion
    if estado is not _SIN_CAMBIOS:
        if estado not in ESTADOS_INSTANCIA:
            raise ValueError(f"Estado inválido: {estado!r}")
        campos["Estado"] = estado
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
    `gasto_en_conflicto`, el gasto manual sigue mandando.

    Bug real encontrado y arreglado (pedido explícito de la clienta,
    "Gastos" de Balance del negocio): "el gasto ya sincronizado" se
    encontraba antes por Periodo+Concepto, el NOMBRE — que no es único,
    dos conceptos distintos pueden compartir nombre (ej. "Alquiler" del
    9no "C" y del 15 "H") — así que sincronizar el segundo pisaba el
    `GastoOperativo` del primero en vez de crear uno nuevo, y uno de
    los dos quedaba "perdido" en Balance del negocio. Ahora se busca
    por `IdConceptoControlPago` (identidad real y estable del concepto,
    ver `schema.sql`), nunca por el nombre — dos conceptos con el mismo
    nombre quedan en dos filas de `GastoOperativo` separadas, cada una
    siempre al día con SU propia instancia."""
    instancia = obtener_repositorio(conn, "InstanciaControlPago").obtener(id_instancia)
    if instancia is None:
        return
    concepto = obtener_repositorio(conn, "ConceptoControlPago").obtener(instancia["IdConcepto"])
    if concepto is None or concepto["TipoAfectacion"] not in _TIPOS_AFECTACION_ESPACIO:
        return

    repo_gasto = obtener_repositorio(conn, "GastoOperativo")
    existente = next(
        (
            g for g in repo_gasto.listar(
                Periodo=instancia["Periodo"], IdConceptoControlPago=concepto["IdConcepto"],
            )
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
        "IdConceptoControlPago": concepto["IdConcepto"],
    }
    if existente is not None:
        repo_gasto.actualizar(existente["IdGasto"], **valores)
    else:
        repo_gasto.crear(**valores)


def _bucket_vencimiento(instancia: sqlite3.Row, hoy: date) -> str | None:
    """Mismo criterio de color que `_PanelCargaControl._color_fila`
    (`app/gui/pantallas/control_pagos.py`), separado acá para que
    "Panel de control" pueda replicar el mismo conteo sin depender de
    la pantalla."""
    if instancia["Estado"] in ("Abonado", "Archivado"):
        return "gris"
    vencimiento = instancia["Vencimiento"]
    if not vencimiento:
        return None
    dias = (date.fromisoformat(vencimiento) - hoy).days
    if dias < 0:
        return "violeta"
    if dias == 0:
        return "rojo"
    if dias == 1:
        return "amarillo"
    return "verde"


def resumen_conteo_vencimientos(conn: sqlite3.Connection) -> dict:
    """Siete conteos pedidos explícitamente por la clienta — usados por
    "Carga y control" (sobre lo filtrado en pantalla, ver `_PanelCarga
    Control._actualizar_etiquetas_conteo`) y por "Panel de control"
    (sin filtro, sobre TODO lo que entra en el mismo alcance: toda
    instancia Pendiente más las del período actual/próximo en
    cualquier Estado — mismo criterio que `_PanelCargaControl.
    actualizar`)."""
    periodo = periodo_actual(conn)
    periodo_proximo = sumar_meses(periodo, 1)
    hoy = fecha_actual(conn)
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancias = [
        i for i in repo.listar()
        if i["Estado"] == "Pendiente" or i["Periodo"] in (periodo, periodo_proximo)
    ]
    colores = [_bucket_vencimiento(i, hoy) for i in instancias]
    return {
        "por_cargar": sum(
            1 for i in instancias
            if i["Estado"] == "Pendiente" and (not i["Vencimiento"] or i["Importe"] is None)
        ),
        "vencimiento_hoy": colores.count("rojo"),
        "vencimiento_mañana": colores.count("amarillo"),
        "vencimiento_en_dias": colores.count("verde"),
        "vencimiento_vencido": colores.count("violeta"),
        "archivados": sum(1 for i in instancias if i["Estado"] == "Archivado"),
        "total": len(instancias),
    }


MEDIOS_PAGO_SALDO_BANCOS = ("CA Bco Patagonia", "CA Bco Provincia", "CA Bco Hipotecario", "CA Bco Macro")
"""Pedido explícito de la clienta sobre "Carga y control" — los cuatro
medios de pago bancarios ya precargados en `MedioPagoControlPagos`
(ver `seed.py`) sobre los que quiere ver el saldo sin pagar, línea por
línea."""


def saldos_expensas_y_bancos(conn: sqlite3.Connection) -> dict:
    """Pedido explícito de la clienta sobre "Carga y control": "Total
    expensas sin abonar" (todo lo cargado en la categoría "Expensas"
    del período vigente que todavía no se pagó) más el saldo sin pagar
    en cada uno de los cuatro medios de pago bancarios (`MEDIOS_PAGO_
    SALDO_BANCOS`, sin importar la categoría). Las cinco cifras son
    sobre TODO lo cargado del período actual, sin filtrar por lo que
    esté elegido en los combos de "Filtros" (esos filtros solo ocultan
    filas de la tabla, ver CLAUDE.md "Filtros que solo afectan la
    visualización") — "sin abonar"/"sin pagar" es `Estado == 'Pendiente'`,
    nunca `Abonado` ni `Archivado`."""
    periodo = periodo_actual(conn)
    instancias = [
        i for i in obtener_repositorio(conn, "InstanciaControlPago").listar(Periodo=periodo)
        if i["Estado"] == "Pendiente"
    ]
    conceptos = {c["IdConcepto"]: c for c in obtener_repositorio(conn, "ConceptoControlPago").listar()}
    total_expensas = sum(
        i["Importe"] or 0.0 for i in instancias
        if conceptos.get(i["IdConcepto"]) is not None and conceptos[i["IdConcepto"]]["Categoria"] == "Expensas"
    )
    resultado = {"total_expensas_sin_abonar": total_expensas}
    for medio in MEDIOS_PAGO_SALDO_BANCOS:
        resultado[medio] = sum(i["Importe"] or 0.0 for i in instancias if i["MedioPago"] == medio)
    return resultado
