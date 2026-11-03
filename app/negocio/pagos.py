"""Pagos, cargos especiales y planes de pago (secciones 3.6, 3.15 y 3.23,
planes afinados por DC-09 §3).

CargoEspecial es el mecanismo genérico para los ítems manuales que después
aparecen en la liquidación (sección 4.5): ajustes, depósito/reintegro de
llave (IdLlave), ítems libres y feriados trabajados avisados con horas ya
calculadas manualmente. No hace falta un modelo separado para cada uno,
alcanza con Tipo (Débito/Crédito), Concepto y el período que imputan.

PlanPago admite refinanciación con interés simple (todas las cuotas
tienen el mismo importe): MontoTotalAPagar = MontoRefinanciado × (1 +
PorcentajeInteresMensual/100 × CantidadCuotas). Solo puede haber un plan
Activo por profesional a la vez — para otro hay que cancelar o refinanciar
el existente.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from app.negocio.dias import fecha_actual, periodo_actual, sumar_meses
from app.repositorio.registro import obtener_repositorio

TIPOS_CARGO = ("Débito", "Crédito")

# #42: antes solo existía la distinción implícita "con llave" (IdLlave) /
# "sin llave" (todo lo demás, mostrado como un único "ítem libre" en el
# PDF). Ajuste y Bonificación se separan como subtipos propios dentro de
# ese "sin llave" — "Depósito de llave" sigue siendo exclusivo de
# `app.negocio.llaves` (nunca se elige a mano desde el formulario de
# Cargos especiales, se deriva solo de `id_llave`). Orden fijo: es el
# mismo que agrupa `app.pdf.liquidacion_pdf._items_cuenta`.
SUBTIPOS_CARGO = ("Depósito de llave", "Ajuste", "Bonificación", "Ítem libre")


def _capitalizar(texto: str) -> str:
    texto = texto.strip()
    return texto[:1].upper() + texto[1:] if texto else texto


def resolver_profesional_para_cargo(conn: sqlite3.Connection, id_profesional: int) -> int:
    """Devuelve el id de profesional al que REALMENTE corresponde
    imputar un cargo/pago — compartida por `registrar_pago` y
    `crear_cargo_especial` (y, de rebote, por los depósitos/reintegros
    de llave de `app.negocio.llaves`, que llaman a `crear_cargo_
    especial` internamente, así que no necesitan su propio chequeo).

    Confirmado por la clienta sobre las seis categorías de Profesional:
    - **R/A/X**: a sí mismo — son las únicas con cuenta propia.
    - **E**: a su cabeza de equipo (tiene que ser un R válido). Nada lee
      nunca el saldo propio de un E: `liquidaciones.
      CATEGORIAS_CON_LIQUIDACION_MENSUAL` es solo `("R",)`, y
      `calcular_liquidacion` filtra `CargoEspecial` por el IdProfesional
      exacto del R que se está liquidando, no por los ids consolidados
      del equipo — un cargo o pago dejado en el E quedaría huérfano
      para siempre, sin que nadie se entere ni lo cobre.
    - **B**: nunca — "todo lo que se les carga queda bonificado", no
      tiene cuenta propia.
    - **C**: nunca — "no se puede hacer ningún otro movimiento con
      ellos". Ya excluido de los combos de creación de las tres
      pantallas (Cargos especiales, Pagos, Llaves); esto es la defensa
      en profundidad a nivel de negocio, mismo criterio que
      `reservas._validar_categoria_reserva`."""
    repo = obtener_repositorio(conn, "Profesional")
    profesional = repo.obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    categoria = profesional["CategoriaProfesional"]
    if categoria == "C":
        raise ValueError("Un profesional categoría C no puede recibir ningún cargo ni pago.")
    if categoria == "B":
        raise ValueError(
            "Un profesional categoría B no puede recibir ningún cargo ni pago: todo queda bonificado."
        )
    if categoria == "E":
        id_cabeza = profesional["ProfesionalCabezaEquipo"]
        cabeza = repo.obtener(id_cabeza) if id_cabeza else None
        if cabeza is None or cabeza["CategoriaProfesional"] != "R":
            raise ValueError(
                "Este profesional categoría E no tiene un cabeza de equipo válido (categoría R) — "
                "corregilo desde Profesionales antes de imputarle algo."
            )
        return id_cabeza
    return id_profesional


def _campo_saldo(conn: sqlite3.Connection, periodo_imputado: str | None) -> str:
    es_mes_anterior = bool(periodo_imputado) and periodo_imputado < periodo_actual(conn)
    return "SaldoCuentaAnterior" if es_mes_anterior else "SaldoCuentaActual"


def _aplicar_pago_con_cascada(
    conn: sqlite3.Connection, id_profesional: int, monto: float, periodo_imputado: str | None,
) -> tuple[float, float]:
    """Aplica `monto` (con signo) al profesional, imputado según
    `periodo_imputado`, y devuelve `(impacto_anterior, impacto_actual)`:
    el delta que terminó afectando a CADA campo de Profesional.

    Bug real reportado por la clienta: "abonó el saldo del mes anterior,
    el actual, y un poco más" — un pago (`monto` negativo) tan grande que
    alcanzaba a cubrir POR COMPLETO tanto el período al que se imputaba
    como el OTRO período, con margen, quedaba como un crédito
    desconectado en el campo imputado, mientras el OTRO campo seguía
    mostrando una deuda que en los hechos ya estaba cubierta — nunca se
    repartía. Ahora, si el sobrante alcanza para cubrir el OTRO saldo por
    completo (no alcanza con dejarlo apenas más chico: tiene que llegar a
    cero), esa deuda se cancela y lo que queda de más pasa a ser el
    crédito final, en el campo imputado.

    Un sobrante que NO llega a cubrir el otro saldo por completo no
    reparte nada — sigue exactamente igual que antes del fix, como un
    crédito en el campo imputado nomás: ese caso es indistinguible de un
    pago por adelantado normal contra un período que todavía no tiene
    cargado el saldo real (ej. una reserva aislada recién creada, que
    todavía no pasó por `emitir_liquidacion`), y el sistema nunca podría
    saber si el operador quiso en verdad empezar a pagar el otro período
    o no — confirmado con un caso real de la suite (`test_mensajes.
    test_detalle_aislada_calcula_saldo_a_abonar`) antes de agregar esta
    condición. Un cargo (`monto` positivo) nunca cae en cascada: solo
    afecta el campo al que se imputa, igual que antes."""
    repo_prof = obtener_repositorio(conn, "Profesional")
    profesional = repo_prof.obtener(id_profesional)
    campo_objetivo = _campo_saldo(conn, periodo_imputado)
    campo_otro = "SaldoCuentaActual" if campo_objetivo == "SaldoCuentaAnterior" else "SaldoCuentaAnterior"
    saldo_objetivo_previo = profesional[campo_objetivo] or 0.0
    saldo_otro_previo = profesional[campo_otro] or 0.0

    nuevo_objetivo_simple = saldo_objetivo_previo + monto
    sobrante = -nuevo_objetivo_simple
    if monto < 0 and saldo_otro_previo > 0 and sobrante >= saldo_otro_previo:
        nuevo_otro = 0.0
        nuevo_objetivo = nuevo_objetivo_simple + saldo_otro_previo
    else:
        nuevo_otro = saldo_otro_previo
        nuevo_objetivo = nuevo_objetivo_simple

    repo_prof.actualizar(id_profesional, **{campo_objetivo: nuevo_objetivo, campo_otro: nuevo_otro})

    impacto_objetivo = nuevo_objetivo - saldo_objetivo_previo
    impacto_otro = nuevo_otro - saldo_otro_previo
    if campo_objetivo == "SaldoCuentaAnterior":
        return impacto_objetivo, impacto_otro
    return impacto_otro, impacto_objetivo


def registrar_pago(
    conn: sqlite3.Connection, *, id_profesional: int, monto: float, fecha: str | None = None,
    medio_pago: str | None = None, cuenta_receptora: str | None = None,
    periodo_imputado: str | None = None, es_ajuste: bool = False, observacion: str | None = None,
    fecha_transferencia: str | None = None, hora_transferencia: str | None = None,
    fecha_hora_recogida_sobres: str | None = None, fecha_hora_apertura_buzon: str | None = None,
) -> tuple[int, bool]:
    """Registra un movimiento de cuenta (pago o ajuste). `monto` es un
    valor con signo: negativo se resta de la cuenta del profesional (un
    pago recibido, que reduce lo que debe), positivo se suma (un cargo,
    que aumenta lo que debe). Si se imputa a un período anterior al mes
    en curso afecta SaldoCuentaAnterior (DC-09 §8); si no,
    SaldoCuentaActual. Si el pago alcanza a cubrir por completo ese
    saldo Y el del otro período, el sobrante cae en cascada reduciendo
    esa otra deuda (ver `_aplicar_pago_con_cascada`) — ya no queda nunca
    como un crédito desconectado mientras el otro período sigue
    mostrando una deuda ya cubierta.

    `fecha`, si no se pasa, toma la fecha de hoy (antes era un campo que
    cargaba el operador a mano; con el rediseño del formulario de Pagos
    ese dato pasó a ser siempre "ahora", igual que FechaHoraCarga).

    El segundo valor devuelto (`cruza_tolerancia`) es True cuando el pago
    imputado al mes anterior hace que ese saldo pase de estar por encima de
    ToleranciaDeudaDescuento a estar dentro — el caso en que corresponde
    preguntarle al operador si restablece el descuento por horas semanales
    para la liquidación remanente de ese período puntual (DC-06 §5.2)."""
    id_profesional = resolver_profesional_para_cargo(conn, id_profesional)
    if periodo_imputado and periodo_imputado < sumar_meses(periodo_actual(conn), -1):
        raise ValueError("Un pago no se puede imputar a más de un mes anterior al mes en curso")

    campo_objetivo = _campo_saldo(conn, periodo_imputado)
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    saldo_previo = profesional[campo_objetivo] or 0.0

    impacto_anterior, impacto_actual = _aplicar_pago_con_cascada(conn, id_profesional, monto, periodo_imputado)

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    nuevo_saldo = profesional[campo_objetivo] or 0.0
    es_mes_anterior = campo_objetivo == "SaldoCuentaAnterior"

    repo = obtener_repositorio(conn, "HistorialPagos")
    id_pago = repo.crear(
        IdProfesional=id_profesional, Fecha=fecha or fecha_actual(conn).isoformat(), Monto=monto,
        MedioPago=medio_pago, CuentaReceptora=cuenta_receptora,
        FechaHoraCarga=datetime.now().isoformat(timespec="seconds"),
        FechaTransferencia=fecha_transferencia, HoraTransferencia=hora_transferencia,
        PeriodoImputado=periodo_imputado, EsAjuste=int(es_ajuste), Observacion=observacion,
        FechaHoraRecogidaSobres=fecha_hora_recogida_sobres, FechaHoraAperturaBuzon=fecha_hora_apertura_buzon,
        SaldoAnterior=saldo_previo, SaldoNuevo=nuevo_saldo, RegistroModificado=0,
        ImpactoSaldoAnterior=impacto_anterior, ImpactoSaldoActual=impacto_actual,
    )

    cruza_tolerancia = False
    if es_mes_anterior:
        cfg = conn.execute(
            "SELECT ToleranciaDeudaDescuento FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        tolerancia = cfg["ToleranciaDeudaDescuento"] if cfg else 0.0
        cruza_tolerancia = saldo_previo > tolerancia >= nuevo_saldo
    return id_pago, cruza_tolerancia


def modificar_pago(
    conn: sqlite3.Connection, id_pago: int, *, monto: float | None = None, medio_pago: str | None = None,
    cuenta_receptora: str | None = None, periodo_imputado: str | None = None,
    fecha_hora_recogida_sobres: str | None = None,
) -> None:
    """Edita un pago ya cargado in-place (a diferencia de Vacaciones/
    Licencias/Ausencias, acá no se anula y se recrea): revierte el efecto
    que tenía sobre el saldo del profesional (usando los deltas exactos
    que guardó en `ImpactoSaldoAnterior`/`ImpactoSaldoActual` — puede
    haber estado repartido entre los dos campos por la cascada de
    `_aplicar_pago_con_cascada`) y aplica el nuevo, conserva
    FechaHoraCarga tal cual quedó la primera vez, y marca
    RegistroModificado. Los parámetros en None dejan ese campo como
    estaba — pasar explícitamente el valor actual si se quiere "no
    cambiarlo" pero de todos modos tocar otro campo."""
    repo = obtener_repositorio(conn, "HistorialPagos")
    pago = repo.obtener(id_pago)
    if pago is None:
        raise ValueError(f"No existe el pago #{id_pago}")
    repo_prof = obtener_repositorio(conn, "Profesional")
    profesional = repo_prof.obtener(pago["IdProfesional"])
    if profesional is None:
        raise ValueError(f"No existe el profesional #{pago['IdProfesional']}")
    if periodo_imputado and periodo_imputado < sumar_meses(periodo_actual(conn), -1):
        raise ValueError("Un pago no se puede imputar a más de un mes anterior al mes en curso")

    repo_prof.actualizar(
        pago["IdProfesional"],
        SaldoCuentaAnterior=(profesional["SaldoCuentaAnterior"] or 0.0) - (pago["ImpactoSaldoAnterior"] or 0.0),
        SaldoCuentaActual=(profesional["SaldoCuentaActual"] or 0.0) - (pago["ImpactoSaldoActual"] or 0.0),
    )

    nuevo_monto = monto if monto is not None else pago["Monto"]
    nuevo_periodo = periodo_imputado if periodo_imputado is not None else pago["PeriodoImputado"]
    campo_nuevo = _campo_saldo(conn, nuevo_periodo)
    profesional = repo_prof.obtener(pago["IdProfesional"])
    saldo_previo = profesional[campo_nuevo] or 0.0

    impacto_anterior, impacto_actual = _aplicar_pago_con_cascada(conn, pago["IdProfesional"], nuevo_monto, nuevo_periodo)

    profesional = repo_prof.obtener(pago["IdProfesional"])
    nuevo_saldo = profesional[campo_nuevo] or 0.0

    repo.actualizar(
        id_pago, Monto=nuevo_monto,
        MedioPago=medio_pago if medio_pago is not None else pago["MedioPago"],
        CuentaReceptora=cuenta_receptora if cuenta_receptora is not None else pago["CuentaReceptora"],
        PeriodoImputado=nuevo_periodo,
        FechaHoraRecogidaSobres=(
            fecha_hora_recogida_sobres if fecha_hora_recogida_sobres is not None else pago["FechaHoraRecogidaSobres"]
        ),
        SaldoAnterior=saldo_previo, SaldoNuevo=nuevo_saldo, RegistroModificado=1,
        ImpactoSaldoAnterior=impacto_anterior, ImpactoSaldoActual=impacto_actual,
    )


def eliminar_pago(conn: sqlite3.Connection, id_pago: int) -> sqlite3.Row:
    """Revierte por completo un movimiento de HistorialPagos: le devuelve
    al profesional el saldo que tenía antes de ese movimiento (en los dos
    campos, por los deltas exactos de `ImpactoSaldoAnterior`/
    `ImpactoSaldoActual` — ver `modificar_pago`) y borra el registro.
    Devuelve la fila borrada, para que quien la llame pueda avisar qué se
    eliminó (y, si corresponde, regenerar la liquidación del mes en curso
    — eso queda a cargo de quien llama, igual que ya hace `modificar_
    pago` vía la pantalla)."""
    repo = obtener_repositorio(conn, "HistorialPagos")
    pago = repo.obtener(id_pago)
    if pago is None:
        raise ValueError(f"No existe el pago #{id_pago}")

    repo_prof = obtener_repositorio(conn, "Profesional")
    profesional = repo_prof.obtener(pago["IdProfesional"])
    if profesional is not None:
        repo_prof.actualizar(
            pago["IdProfesional"],
            SaldoCuentaAnterior=(profesional["SaldoCuentaAnterior"] or 0.0) - (pago["ImpactoSaldoAnterior"] or 0.0),
            SaldoCuentaActual=(profesional["SaldoCuentaActual"] or 0.0) - (pago["ImpactoSaldoActual"] or 0.0),
        )

    repo.eliminar(id_pago)
    return pago


def deshacer_ultimo_pago(conn: sqlite3.Connection) -> sqlite3.Row:
    """Como `eliminar_pago`, pero sobre el último movimiento registrado en
    HistorialPagos (el de IdPago más alto), sin necesidad de elegirlo a
    mano."""
    todos = obtener_repositorio(conn, "HistorialPagos").listar()
    if not todos:
        raise ValueError("No hay ningún movimiento para deshacer")
    ultimo = max(todos, key=lambda p: p["IdPago"])
    return eliminar_pago(conn, ultimo["IdPago"])


def reconciliar_saldos_cruzados(conn: sqlite3.Connection) -> list[int]:
    """Corrección retroactiva del bug real reportado por la clienta (ver
    CLAUDE.md): antes de que `registrar_pago` repartiera en cascada un
    pago que alcanzaba a cubrir POR COMPLETO tanto el período al que se
    imputaba como el otro período, con margen (ver
    `_aplicar_pago_con_cascada`), ese sobrante quedaba como un crédito
    desconectado en un campo mientras el OTRO campo seguía mostrando una
    deuda que en los hechos ya estaba cubierta.

    La detección usa EXACTAMENTE el mismo umbral que el fix (no cualquier
    combinación de signos opuestos): un campo en deuda (positivo) y el
    OTRO en crédito (negativo) cuya magnitud alcanza para cubrir esa
    deuda por completo. Un crédito que NO llega a cubrir la otra deuda
    por completo no se toca — es indistinguible de un pago por
    adelantado normal contra un período que todavía no tiene cargado el
    saldo real (confirmado con un caso real de la suite, ver
    `_aplicar_pago_con_cascada`), y tocarlo sería corregir algo que nunca
    estuvo roto.

    Se llama una vez en cada arranque (`app.db.init_db.init_database`,
    después de `aplicar_migraciones`): neta un campo contra el otro — la
    SUMA de los dos no cambia, solo se redistribuye correctamente entre
    "anterior" y "actual" — y deja su propio movimiento en
    HistorialPagos (Monto=0, EsAjuste, con el detalle exacto en
    Observación) para que quede visible en Estado de cuenta y sea
    reversible como cualquier otro pago (Eliminar) si hiciera falta. Es
    así de por sí idempotente: una vez corregido un profesional, ya no
    vuelve a cumplir la condición (y el fix en `registrar_pago` ya no
    vuelve a generarla), así que no hace nada en los arranques
    siguientes. Devuelve la lista de IdProfesional corregidos."""
    repo_prof = obtener_repositorio(conn, "Profesional")
    repo_pago = obtener_repositorio(conn, "HistorialPagos")
    corregidos = []
    for prof in repo_prof.listar():
        anterior = prof["SaldoCuentaAnterior"] or 0.0
        actual = prof["SaldoCuentaActual"] or 0.0
        if anterior > 0 and actual < 0 and -actual >= anterior:
            nuevo_anterior, nuevo_actual = 0.0, actual + anterior
        elif actual > 0 and anterior < 0 and -anterior >= actual:
            nuevo_anterior, nuevo_actual = anterior + actual, 0.0
        else:
            continue

        repo_prof.actualizar(
            prof["IdProfesional"], SaldoCuentaAnterior=nuevo_anterior, SaldoCuentaActual=nuevo_actual,
        )
        repo_pago.crear(
            IdProfesional=prof["IdProfesional"], Fecha=fecha_actual(conn).isoformat(), Monto=0.0,
            FechaHoraCarga=datetime.now().isoformat(timespec="seconds"), EsAjuste=1,
            Observacion=(
                "Corrección automática de saldos cruzados entre período anterior y actual "
                f"(bug ya corregido): saldo período anterior {anterior:.2f} -> {nuevo_anterior:.2f}, "
                f"saldo período actual {actual:.2f} -> {nuevo_actual:.2f}."
            ),
            SaldoAnterior=anterior, SaldoNuevo=nuevo_anterior, RegistroModificado=0,
            ImpactoSaldoAnterior=nuevo_anterior - anterior, ImpactoSaldoActual=nuevo_actual - actual,
        )
        corregidos.append(prof["IdProfesional"])
    return corregidos


# --------------------------------------------------------------- tanda de sobres (DC-08 §5.3)
#
# Una "tanda" no tiene tabla propia: se identifica por su FechaHoraApertura
# (el momento en que se abrió), guardada en Configuracion mientras está
# abierta. Cada pago por sobre registrado durante esa tanda guarda el mismo
# valor en HistorialPagos.FechaHoraAperturaBuzon, que es lo que permite
# sumar el subtotal en vivo sin necesitar una tabla aparte ni un ID: dos
# pagos "pertenecen a la misma tanda" si comparten esa marca de tiempo.

def tanda_sobres_abierta(conn: sqlite3.Connection) -> str | None:
    """Fecha y hora de apertura de la tanda actual, o None si no hay
    ninguna abierta."""
    cfg = conn.execute(
        "SELECT TandaSobresAbierta, TandaSobresApertura FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    if cfg and cfg["TandaSobresAbierta"]:
        return cfg["TandaSobresApertura"]
    return None


def abrir_tanda_sobres(conn: sqlite3.Connection) -> str:
    """Abre una tanda nueva (o reemplaza la que estuviera abierta: el
    operador ya decidió no mantenerla, ver `tanda_sobres_es_de_otro_dia`).
    Devuelve la marca de tiempo de apertura."""
    apertura = datetime.now().isoformat(timespec="seconds")
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, TandaSobresAbierta=1, TandaSobresApertura=apertura,
    )
    return apertura


def cerrar_tanda_sobres(conn: sqlite3.Connection) -> None:
    obtener_repositorio(conn, "Configuracion").actualizar(1, TandaSobresAbierta=0)


def tanda_sobres_es_de_otro_dia(conn: sqlite3.Connection) -> bool:
    """True si hay una tanda abierta pero de un día calendario distinto al
    de hoy — el caso en que corresponde preguntarle al operador si la
    mantiene o arranca una nueva (DC-08 §5.3)."""
    apertura = tanda_sobres_abierta(conn)
    if apertura is None:
        return False
    return apertura[:10] != fecha_actual(conn).isoformat()


def subtotal_tanda_sobres(conn: sqlite3.Connection, apertura: str) -> float:
    """Suma de los pagos por sobre registrados durante la tanda que abrió
    en `apertura` — el subtotal en vivo para cuadrar contra el efectivo
    físico al ir abriendo los sobres."""
    fila = conn.execute(
        "SELECT COALESCE(SUM(Monto), 0) AS total FROM HistorialPagos "
        "WHERE MedioPago = 'Sobre en buzón' AND FechaHoraAperturaBuzon = ?",
        (apertura,),
    ).fetchone()
    return fila["total"]


def suspender_descuento_periodo(conn: sqlite3.Connection, *, id_profesional: int, periodo: str) -> None:
    """DC-06 §5.2, rama "No" (la recomendada por defecto): aunque el saldo
    anterior ya volvió a estar dentro de tolerancia, el descuento por horas
    semanales queda perdido igual para la liquidación remanente de ese
    período puntual — los meses siguientes se evalúan de forma
    independiente, sin arrastrar esta decisión."""
    obtener_repositorio(conn, "Profesional").actualizar(id_profesional, DescuentoSuspendidoPeriodo=periodo)


def crear_cargo_especial(
    conn: sqlite3.Connection, *, id_profesional: int, tipo: str, concepto: str, monto: float,
    periodo_imputado: str, subtipo: str | None = None, id_llave: int | None = None,
    id_unidad: int | None = None, observacion: str | None = None,
) -> int:
    """A diferencia de Pagos (que sí puede corregir hasta un mes atrás), un
    cargo especial nunca se imputa a un período ya cerrado — ajustes,
    bonificaciones y depósitos/reintegros de llave se cargan siempre al mes
    en curso o al que viene, nunca más adelante (pedido explícito de la
    clienta: "solo se puede agendar para el mes en curso o el que viene"),
    para no tener que reabrir una liquidación ya emitida. El monto lleva
    directo el signo que le corresponde al Tipo (Débito positivo, Crédito
    negativo) — Tipo queda como una validación cruzada de ese signo, no
    hace falta derivarlo aparte en ningún lado que sume estos montos.

    Esta función NO regenera ninguna liquidación — eso queda del lado de
    la GUI (`_PanelCargosEspeciales._crear`, mismo criterio que Vacaciones/
    Licencias/Reservas regulares): si el cargo se imputa al mes en curso,
    la liquidación de ESE período ya emitida tiene que regenerarse y
    quedar marcada como no enviada; si se imputa al mes que viene, no hay
    nada para regenerar todavía — `calcular_liquidacion` ya lo toma solo
    cuando le llegue el turno a ese período (filtra `CargoEspecial` por
    `PeriodoImputado` exacto).

    `subtipo` (#42) se deriva solo cuando viene `id_llave`: "Depósito de
    llave" siempre, sin importar lo que se pase — es estructural (ver
    `app.negocio.llaves`), no una elección del operador. Sin `id_llave`,
    tiene que ser uno de los otros tres (Ajuste/Bonificación/Ítem libre);
    sin indicar ninguno, cae a "Ítem libre" (mismo default que la columna
    en la base, para no romper a ningún llamador de antes de este
    pedido — el formulario de Cargos especiales sí lo pasa siempre).

    `id_profesional` pasa primero por `resolver_profesional_para_cargo`:
    un E se redirige solo a su cabeza de equipo (cubre también los
    depósitos/reintegros de llave, que llaman a esta función), B/C
    nunca pueden recibir un cargo."""
    id_profesional = resolver_profesional_para_cargo(conn, id_profesional)
    if tipo not in TIPOS_CARGO:
        raise ValueError(f"Tipo de cargo inválido: {tipo!r} (debe ser Débito o Crédito)")
    if not periodo_imputado:
        raise ValueError("El período imputado es obligatorio")
    periodo_siguiente = sumar_meses(periodo_actual(conn), 1)
    if periodo_imputado not in (periodo_actual(conn), periodo_siguiente):
        raise ValueError(
            "Un cargo especial solo se puede imputar al mes en curso o al que viene "
            f"({periodo_actual(conn)} o {periodo_siguiente})"
        )
    if tipo == "Débito" and monto <= 0:
        raise ValueError("Un cargo especial Débito debe cargarse con un monto positivo")
    if tipo == "Crédito" and monto >= 0:
        raise ValueError("Un cargo especial Crédito debe cargarse con un monto negativo")
    if id_llave is not None:
        subtipo = "Depósito de llave"
    elif subtipo is None:
        subtipo = "Ítem libre"
    elif subtipo not in SUBTIPOS_CARGO or subtipo == "Depósito de llave":
        raise ValueError(f"Subtipo de cargo inválido: {subtipo!r} (debe ser Ajuste, Bonificación o Ítem libre)")

    repo = obtener_repositorio(conn, "CargoEspecial")
    return repo.crear(
        IdProfesional=id_profesional, Tipo=tipo, Subtipo=subtipo, Concepto=_capitalizar(concepto), Monto=monto,
        Fecha=fecha_actual(conn).isoformat(), PeriodoImputado=periodo_imputado,
        IdLlave=id_llave, IdUnidad=id_unidad, Observacion=observacion,
    )


def _generar_cuotas(conn: sqlite3.Connection, id_plan: int, monto_total_a_pagar: float,
                     importe_por_cuota: float, cantidad_cuotas: int, mes_ano_inicio: str) -> None:
    repo_cuota = obtener_repositorio(conn, "CuotaPlan")
    # la última cuota absorbe el resto del redondeo para que la suma cierre exacto
    acumulado = 0.0
    for numero in range(1, cantidad_cuotas + 1):
        if numero < cantidad_cuotas:
            monto_cuota = importe_por_cuota
            acumulado += monto_cuota
        else:
            monto_cuota = round(monto_total_a_pagar - acumulado, 2)
        repo_cuota.crear(
            IdPlan=id_plan, NumeroCuota=numero,
            PeriodoImputado=sumar_meses(mes_ano_inicio, numero - 1),
            Monto=monto_cuota, Pagado=0, Estado="Pendiente",
        )


def _validar_sin_plan_activo(conn: sqlite3.Connection, id_profesional: int) -> None:
    plan_activo = obtener_repositorio(conn, "PlanPago").listar(IdProfesional=id_profesional, Estado="Activo")
    if plan_activo:
        raise ValueError(
            f"El profesional #{id_profesional} ya tiene un plan de pagos activo "
            f"(#{plan_activo[0]['IdPlan']}); hay que cancelarlo o refinanciarlo, no puede haber dos a la vez"
        )


def crear_plan_pago(
    conn: sqlite3.Connection, *, id_profesional: int, monto_refinanciado: float, cantidad_cuotas: int,
    porcentaje_interes_mensual: float = 0.0, observacion: str | None = None,
) -> int:
    """Formulario de "Guardar nuevo plan de pagos" (DC-09 §3.6, aclarado en
    conversación): se arma siempre a principio del mes en curso.
    `monto_refinanciado` sale del saldo atrasado (SaldoCuentaAnterior), que
    se descuenta acá — deja de ser deuda suelta y pasa a pagarse en cuotas.
    La primera cuota queda imputada al período actual y se cobra sola en
    la próxima liquidación de este mes, junto con lo demás
    (`calcular_liquidacion` ya suma las CuotaPlan pendientes del período)."""
    _validar_sin_plan_activo(conn, id_profesional)
    repo_prof = obtener_repositorio(conn, "Profesional")
    profesional = repo_prof.obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    repo_prof.actualizar(
        id_profesional, SaldoCuentaAnterior=(profesional["SaldoCuentaAnterior"] or 0.0) - monto_refinanciado
    )
    return _crear_plan_pago(
        conn, id_profesional=id_profesional, monto_refinanciado=monto_refinanciado,
        cantidad_cuotas=cantidad_cuotas, mes_ano_inicio=periodo_actual(conn),
        porcentaje_interes_mensual=porcentaje_interes_mensual, observacion=observacion,
    )


def crear_plan_pago_historico(
    conn: sqlite3.Connection, *, id_profesional: int, monto_refinanciado: float, cantidad_cuotas: int,
    mes_ano_inicio: str, porcentaje_interes_mensual: float = 0.0, observacion: str | None = None,
) -> int:
    """Para reconstruir un plan que ya venía en curso antes de empezar a
    usar el sistema (importación de Excel, `importar_excel.
    _crear_plan_pago_importado`): a diferencia de `crear_plan_pago`, no
    toca SaldoCuentaAnterior — ese estado ya viene reflejado aparte en el
    saldo importado del profesional — y admite cualquier MesAnoInicio,
    no solo el período actual."""
    _validar_sin_plan_activo(conn, id_profesional)
    return _crear_plan_pago(
        conn, id_profesional=id_profesional, monto_refinanciado=monto_refinanciado,
        cantidad_cuotas=cantidad_cuotas, mes_ano_inicio=mes_ano_inicio,
        porcentaje_interes_mensual=porcentaje_interes_mensual, observacion=observacion,
    )


def _crear_plan_pago(
    conn: sqlite3.Connection, *, id_profesional: int, monto_refinanciado: float, cantidad_cuotas: int,
    mes_ano_inicio: str, porcentaje_interes_mensual: float = 0.0, observacion: str | None = None,
    es_refinanciacion: bool = False, id_plan_anterior: int | None = None,
) -> int:
    """Crea el plan sin verificar el invariante de "un solo plan activo" —
    `refinanciar_plan` ya canceló el plan vigente (o decidió a propósito no
    hacerlo) antes de llamar acá, así que no corresponde repetir el chequeo."""
    if cantidad_cuotas <= 0:
        raise ValueError("La cantidad de cuotas debe ser mayor a cero")

    monto_total_a_pagar = monto_refinanciado * (1 + (porcentaje_interes_mensual / 100) * cantidad_cuotas)
    importe_por_cuota = round(monto_total_a_pagar / cantidad_cuotas, 2)

    repo_plan = obtener_repositorio(conn, "PlanPago")
    id_plan = repo_plan.crear(
        IdProfesional=id_profesional, MontoRefinanciado=monto_refinanciado,
        PorcentajeInteresMensual=porcentaje_interes_mensual, MontoTotalAPagar=monto_total_a_pagar,
        CantidadCuotas=cantidad_cuotas, ImportePorCuota=importe_por_cuota, MesAnoInicio=mes_ano_inicio,
        Estado="Activo", EsRefinanciacion=int(es_refinanciacion), IdPlanAnterior=id_plan_anterior,
        Observacion=observacion,
    )
    _generar_cuotas(conn, id_plan, monto_total_a_pagar, importe_por_cuota, cantidad_cuotas, mes_ano_inicio)
    return id_plan


def plan_activo_de(conn: sqlite3.Connection, id_profesional: int) -> sqlite3.Row | None:
    """El plan de pagos Activo del profesional, si tiene uno (nunca puede
    haber más de uno a la vez)."""
    activos = obtener_repositorio(conn, "PlanPago").listar(IdProfesional=id_profesional, Estado="Activo")
    return activos[0] if activos else None


def cuotas_restantes_plan(conn: sqlite3.Connection, id_plan: int) -> tuple[int, float]:
    """Cantidad y monto de las cuotas del plan que todavía no cerró el
    avance de mes (`avance_mes._cerrar_cuotas` las pasa a Estado="Cerrada"
    al cerrar el período al que estaban imputadas, cobradas o no vía la
    liquidación de ese mes) — son las que de verdad quedan sin abonar,
    incluida la del período en curso si todavía no se cerró."""
    fila = conn.execute(
        "SELECT COUNT(*) AS cantidad, COALESCE(SUM(Monto), 0) AS total FROM CuotaPlan "
        "WHERE IdPlan = ? AND Estado != 'Cerrada'",
        (id_plan,),
    ).fetchone()
    return fila["cantidad"], fila["total"]


def cuotas_pendientes_plan(conn: sqlite3.Connection, id_plan: int) -> float:
    """Ver `cuotas_restantes_plan` — esto es solo el monto."""
    return cuotas_restantes_plan(conn, id_plan)[1]


def cancelar_plan(conn: sqlite3.Connection, id_plan: int) -> None:
    """Cancela un plan activo. Las cuotas que todavía quedaban sin abonar
    (incluida la del mes en curso si no se cerró) se suman a
    SaldoCuentaAnterior: vuelven a ser saldo atrasado, tal como estaban
    antes de armar el plan (DC-09 §3.5, aclarado en conversación)."""
    repo_plan = obtener_repositorio(conn, "PlanPago")
    plan = repo_plan.obtener(id_plan)
    if plan is None:
        raise ValueError(f"No existe el plan #{id_plan}")
    if plan["Estado"] != "Activo":
        raise ValueError(f"El plan #{id_plan} no está activo (Estado={plan['Estado']!r})")

    pendientes = cuotas_pendientes_plan(conn, id_plan)
    repo_plan.actualizar(id_plan, Estado="Cancelado")
    if pendientes:
        repo_prof = obtener_repositorio(conn, "Profesional")
        profesional = repo_prof.obtener(plan["IdProfesional"])
        repo_prof.actualizar(
            plan["IdProfesional"], SaldoCuentaAnterior=(profesional["SaldoCuentaAnterior"] or 0.0) + pendientes
        )


def refinanciar_plan(
    conn: sqlite3.Connection, *, id_profesional: int, monto_a_refinanciar: float, cantidad_cuotas: int,
    porcentaje_interes_mensual: float = 0.0, observacion: str | None = None,
) -> int:
    """Formulario de refinanciación (DC-09 §3.6, aclarado en conversación):
    se arma siempre a principio del mes en curso. Cancela el plan vigente
    (las cuotas que le quedaban, incluida la de este mes, se suman a
    SaldoCuentaAnterior — ver `cancelar_plan`), descuenta de ahí
    `monto_a_refinanciar` (que en la pantalla ya viene sugerido como ese
    mismo saldo atrasado, con las cuotas del plan viejo incluidas) y arma
    el plan nuevo con eso."""
    plan_activo = obtener_repositorio(conn, "PlanPago").listar(IdProfesional=id_profesional, Estado="Activo")
    if not plan_activo:
        raise ValueError(f"El profesional #{id_profesional} no tiene un plan de pagos activo para refinanciar")
    id_plan_anterior = plan_activo[0]["IdPlan"]
    cancelar_plan(conn, id_plan_anterior)

    repo_prof = obtener_repositorio(conn, "Profesional")
    profesional = repo_prof.obtener(id_profesional)
    if profesional is None:
        raise ValueError(f"No existe el profesional #{id_profesional}")
    repo_prof.actualizar(
        id_profesional, SaldoCuentaAnterior=(profesional["SaldoCuentaAnterior"] or 0.0) - monto_a_refinanciar
    )

    return _crear_plan_pago(
        conn, id_profesional=id_profesional, monto_refinanciado=monto_a_refinanciar,
        cantidad_cuotas=cantidad_cuotas, mes_ano_inicio=periodo_actual(conn),
        porcentaje_interes_mensual=porcentaje_interes_mensual, observacion=observacion,
        es_refinanciacion=True, id_plan_anterior=id_plan_anterior,
    )


def marcar_cuota_pagada(conn: sqlite3.Connection, id_cuota: int) -> None:
    repo_cuota = obtener_repositorio(conn, "CuotaPlan")
    cuota = repo_cuota.obtener(id_cuota)
    if cuota is None:
        raise ValueError(f"No existe la cuota #{id_cuota}")

    repo_cuota.actualizar(id_cuota, Pagado=1, Estado="Pagada")

    pendientes = conn.execute(
        "SELECT COUNT(*) FROM CuotaPlan WHERE IdPlan = ? AND Pagado = 0", (cuota["IdPlan"],)
    ).fetchone()[0]
    if pendientes == 0:
        obtener_repositorio(conn, "PlanPago").actualizar(cuota["IdPlan"], Estado="Finalizado")
