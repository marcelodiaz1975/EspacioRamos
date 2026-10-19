"""Importación de datos iniciales desde la planilla Excel (FA5).

Las columnas de referencia (Edificio, Unidad, Profesional, etc.) se cargan
en la planilla con nombres legibles en vez de IDs internos -- por ejemplo,
en la hoja "Consultorio" se indica el nombre del Edificio y el Departamento
de la Unidad, no sus IdEdificio/IdUnidad. Este módulo resuelve esas
referencias contra lo que ya se cargó en la base (por eso el orden de
ENTIDADES_IMPORTABLES importa: primero Edificio, después Unidad, etc.)

Fechas (DC-11 caso 7): el único formato aceptado en la planilla es
DD/MM/AAAA; se convierten a ISO (AAAA-MM-DD) antes de guardar, y un
formato inválido se reporta como error de esa fila/columna sin abortar el
resto de la importación. openpyxl también puede entregar la celda ya como
datetime si Excel la formateó como fecha -- se acepta igual.
"""
from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

from app.importacion.definiciones import (
    CAMPOS_BOOLEANOS,
    CAMPOS_FECHA,
    CAMPOS_PERIODO,
    COLUMNAS_REFERENCIA,
    ENTIDADES_IMPORTABLES,
)
from app.negocio.dias import fecha_actual, periodo_actual
from app.negocio.llaves import _LETRA_POR_TIPO, agregar_acceso_llave, ingresar_copias, siguiente_nombre_llave
from app.negocio.pagos import crear_plan_pago_historico, marcar_cuota_pagada
from app.repositorio.registro import obtener_repositorio


def _normalizar_encabezado(texto: str) -> str:
    """La base usa nombres de columna ASCII a propósito (sin tildes ni ñ,
    para evitar problemas de codificación al empaquetar con PyInstaller en
    Windows -- ver schema.sql), pero la planilla puede traer la versión con
    tilde/diéresis (p.ej. "Baños"). Se le sacan los diacríticos acá antes de
    matchear contra el nombre de columna real, en vez de mantener una lista
    de alias por cada palabra acentuada que pueda aparecer."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


@dataclass
class ResultadoImportacion:
    entidad: str
    filas_importadas: int = 0
    filas_duplicadas: int = 0
    errores: list[str] = field(default_factory=list)


def _convertir_booleano(valor) -> int:
    texto = str(valor).strip().upper()
    return 1 if texto in ("SI", "SÍ", "TRUE", "1", "X") else 0


def _convertir_fecha(valor) -> str:
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    partes = texto.split("/")
    if len(partes) != 3:
        raise ValueError(f"Fecha inválida (se espera DD/MM/AAAA): {valor!r}")
    dia, mes, anio = partes
    try:
        return date(int(anio), int(mes), int(dia)).isoformat()
    except ValueError as exc:
        raise ValueError(f"Fecha inválida (se espera DD/MM/AAAA): {valor!r}") from exc


def _convertir_periodo(valor) -> str:
    if isinstance(valor, (datetime, date)):
        return f"{valor.year:04d}-{valor.month:02d}"
    texto = str(valor).strip()
    partes = texto.split("/")
    if len(partes) != 2:
        raise ValueError(f"Período inválido (se espera MM/AAAA): {valor!r}")
    mes, anio = partes
    try:
        mes_i, anio_i = int(mes), int(anio)
        if not 1 <= mes_i <= 12:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"Período inválido (se espera MM/AAAA): {valor!r}") from exc
    return f"{anio_i:04d}-{mes_i:02d}"


def _convertir_valor(columna: str, valor):
    if valor is None or valor == "":
        return None
    if columna in CAMPOS_BOOLEANOS:
        return _convertir_booleano(valor)
    if columna in CAMPOS_FECHA:
        return _convertir_fecha(valor)
    if columna in CAMPOS_PERIODO:
        return _convertir_periodo(valor)
    return valor


def _buscar_id(conn: sqlite3.Connection, tabla: str, columna: str, valor) -> int | None:
    if valor is None:
        return None
    fila = conn.execute(f"SELECT * FROM {tabla} WHERE {columna} = ? LIMIT 1", (valor,)).fetchone()
    return fila[0] if fila else None


def _buscar_unidad(conn: sqlite3.Connection, nombre_edificio, departamento) -> int | None:
    id_edificio = _buscar_id(conn, "Edificio", "Nombre", nombre_edificio)
    if id_edificio is None:
        return None
    fila = conn.execute(
        "SELECT IdUnidad FROM Unidad WHERE IdEdificio = ? AND Departamento = ?",
        (id_edificio, departamento),
    ).fetchone()
    return fila["IdUnidad"] if fila else None


def _buscar_consultorio(conn: sqlite3.Connection, nombre_edificio, departamento, numero) -> int | None:
    id_unidad = _buscar_unidad(conn, nombre_edificio, departamento)
    if id_unidad is None:
        return None
    fila = conn.execute(
        "SELECT IdConsultorio FROM Consultorio WHERE IdUnidad = ? AND NumeroConsultorio = ?",
        (id_unidad, numero),
    ).fetchone()
    return fila["IdConsultorio"] if fila else None


def _resolver_referencias(
    conn: sqlite3.Connection, entidad: str, datos: dict, *, mapa_codigo_llave: dict[str, int] | None = None,
) -> tuple[dict, list[str]]:
    """Reemplaza las columnas de referencia (nombres legibles) por su IdX.
    Devuelve los datos resueltos y una lista de errores (referencias no
    encontradas).

    `mapa_codigo_llave` (solo para "LlaveAcceso"/"LlaveMovimiento"): el
    diccionario {Código de planilla -> IdLlave} que arma `importar_planilla`
    mientras procesa la hoja "Llave", ANTES de llegar a estas dos — ninguna
    de las dos resuelve su "CodigoLlave" contra ninguna columna de la base
    (ese Código no se guarda en ningún lado), lo resuelve contra este mapa
    en memoria."""
    errores: list[str] = []
    referencias = COLUMNAS_REFERENCIA.get(entidad, set())
    if not referencias:
        return datos, errores

    if entidad == "Edificio":
        nombre_loc = datos.pop("Localidad", None)
        if nombre_loc is not None:
            id_localidad = _buscar_id(conn, "Localidad", "Localidad", nombre_loc)
            if id_localidad is None:
                errores.append(f"No se encontró la localidad '{nombre_loc}'")
            datos["IdLocalidad"] = id_localidad

    elif entidad == "Unidad":
        nombre_ed = datos.pop("Edificio", None)
        id_edificio = _buscar_id(conn, "Edificio", "Nombre", nombre_ed)
        if id_edificio is None:
            errores.append(f"No se encontró el edificio '{nombre_ed}'")
        datos["IdEdificio"] = id_edificio

    elif entidad == "Consultorio":
        nombre_ed = datos.pop("Edificio", None)
        depto = datos.pop("Unidad", None)
        id_unidad = _buscar_unidad(conn, nombre_ed, depto)
        if id_unidad is None:
            errores.append(f"No se encontró la unidad '{depto}' del edificio '{nombre_ed}'")
        datos["IdUnidad"] = id_unidad

    elif entidad == "Profesional":
        nombre_prof = datos.pop("Profesion", None)
        if nombre_prof is not None:
            id_profesion = _buscar_id(conn, "Profesion", "Nombre", nombre_prof)
            if id_profesion is None:
                errores.append(f"No se encontró la profesión '{nombre_prof}'")
            datos["IdProfesion"] = id_profesion

        codigo_cabeza = datos.pop("ProfesionalCabezaEquipo", None)
        if codigo_cabeza is not None:
            id_cabeza = _buscar_id(conn, "Profesional", "IdCodigo", codigo_cabeza)
            if id_cabeza is None:
                errores.append(
                    f"No se encontró el profesional cabeza de equipo con código '{codigo_cabeza}' "
                    "(tiene que estar cargado antes en la planilla)"
                )
            datos["ProfesionalCabezaEquipo"] = id_cabeza

    elif entidad == "ReservaRegular":
        codigo = datos.pop("Profesional", None)
        id_profesional = _buscar_id(conn, "Profesional", "IdCodigo", codigo)
        if id_profesional is None:
            errores.append(f"No se encontró el profesional con código '{codigo}'")
        datos["IdProfesional"] = id_profesional

        nombre_ed = datos.pop("Edificio", None)
        depto = datos.pop("Unidad", None)
        numero = datos.pop("Consultorio", None)
        id_consultorio = _buscar_consultorio(conn, nombre_ed, depto, numero)
        if id_consultorio is None:
            errores.append(
                f"No se encontró el consultorio {numero} de la unidad '{depto}' del edificio '{nombre_ed}'"
            )
        datos["IdConsultorio"] = id_consultorio

    elif entidad == "Placa":
        nombre_ed = datos.pop("Edificio", None)
        depto = datos.pop("Unidad", None)
        id_unidad = _buscar_unidad(conn, nombre_ed, depto)
        if id_unidad is None:
            errores.append(f"No se encontró la unidad '{depto}' del edificio '{nombre_ed}'")
        else:
            posicion = datos.get("PosicionTablero")
            fila_unidad = conn.execute(
                "SELECT CantLimitePlacas FROM Unidad WHERE IdUnidad = ?", (id_unidad,),
            ).fetchone()
            limite = fila_unidad["CantLimitePlacas"] if fila_unidad else 0
            if posicion is not None and not (1 <= posicion <= limite):
                errores.append(
                    f"La posición {posicion} está fuera del rango 1-{limite} "
                    f"(capacidad del tablero) de la unidad '{depto}'"
                )
        datos["IdUnidad"] = id_unidad

        codigo = datos.pop("Profesional", None)
        if codigo is not None:
            id_profesional = _buscar_id(conn, "Profesional", "IdCodigo", codigo)
            if id_profesional is None:
                errores.append(f"No se encontró el profesional con código '{codigo}'")
            datos["IdProfesional"] = id_profesional

    elif entidad == "PlanPago":
        codigo = datos.pop("Profesional", None)
        id_profesional = _buscar_id(conn, "Profesional", "IdCodigo", codigo)
        if id_profesional is None:
            errores.append(f"No se encontró el profesional con código '{codigo}'")
        datos["IdProfesional"] = id_profesional

    elif entidad == "LlaveAcceso":
        codigo_llave = datos.pop("CodigoLlave", None)
        id_llave = _buscar_codigo_llave(codigo_llave, mapa_codigo_llave, errores)
        datos["IdLlave"] = id_llave

        # Edificio es obligatorio (LlaveAcceso.IdEdificio es NOT NULL -- un
        # acceso siempre abre al menos un edificio); Unidad es opcional,
        # solo para una llave de Tipo "Unidad" que apunta a una puntual.
        nombre_ed = datos.pop("Edificio", None)
        id_edificio = _buscar_id(conn, "Edificio", "Nombre", nombre_ed)
        if id_edificio is None:
            errores.append(f"No se encontró el edificio '{nombre_ed}'")
        datos["IdEdificio"] = id_edificio

        depto = datos.pop("Unidad", None)
        id_unidad = None
        if depto is not None:
            if id_edificio is None:
                errores.append("Para indicar una unidad primero hay que indicar el edificio de ese acceso")
            else:
                id_unidad = _buscar_unidad(conn, nombre_ed, depto)
                if id_unidad is None:
                    errores.append(f"No se encontró la unidad '{depto}' del edificio '{nombre_ed}'")
        datos["IdUnidad"] = id_unidad

    elif entidad == "LlaveMovimiento":
        codigo_llave = datos.pop("CodigoLlave", None)
        id_llave = _buscar_codigo_llave(codigo_llave, mapa_codigo_llave, errores)
        datos["IdLlave"] = id_llave

        codigo_prof = datos.pop("Profesional", None)
        id_profesional = _buscar_id(conn, "Profesional", "IdCodigo", codigo_prof)
        if id_profesional is None:
            errores.append(f"No se encontró el profesional con código '{codigo_prof}'")
        datos["IdProfesional"] = id_profesional

    return datos, errores


def _buscar_codigo_llave(
    codigo: str | None, mapa_codigo_llave: dict[str, int] | None, errores: list[str],
) -> int | None:
    """Resuelve el "CodigoLlave" de una fila de LlaveAcceso/LlaveMovimiento
    contra el mapa {Código -> IdLlave} armado al procesar la hoja "Llave"
    -- ese Código es puramente de planilla, nunca se guarda en la base, así
    que no hay ninguna columna contra la que buscarlo con `_buscar_id`."""
    if not codigo:
        errores.append('Falta el "CodigoLlave" -- a qué Tipo de llave (hoja "Llave") se refiere esta fila')
        return None
    id_llave = (mapa_codigo_llave or {}).get(codigo)
    if id_llave is None:
        errores.append(
            f"No se encontró ningún Tipo de llave con el código '{codigo}' "
            '(tiene que estar cargado antes, en la hoja "Llave")'
        )
    return id_llave


def _buscar_identico(conn: sqlite3.Connection, tabla: str, datos: dict) -> int | None:
    """Devuelve el Id (primera columna, convención de siempre en este
    módulo -- ver `_buscar_id`) de la fila ya existente en `tabla` con
    exactamente estos mismos valores en todas las columnas de `datos`
    (NULL incluido), o `None` si no hay ninguna — pedido explícito de la
    clienta: "que no importe los registros que son iguales para evitar
    que se dupliquen". Una fila "parecida" pero con algún campo distinto
    (ej. un CampoLibre corregido) no cuenta como duplicado y se importa
    igual. Se llama ANTES de cualquier columna que la propia importación
    agregue sola (ej. `Nombre` de Llave, autogenerado y por lo tanto
    siempre distinto) — comparar con esas ya puestas nunca encontraría un
    duplicado real.

    Devolver el Id (no solo un bool) sirve para "Llave": si la fila de la
    hoja "Llave" resulta duplicada de un Tipo ya cargado, igual hace falta
    saber SU Id para poder enlazar el "Codigo" de esta fila al Tipo ya
    existente (si la planilla entera se reimporta sin querer, las hojas
    "LlaveAcceso"/"LlaveMovimiento" tienen que poder seguir resolviendo
    ese mismo Código, no solo la primera vez)."""
    if not datos:
        return None
    condiciones = []
    valores = []
    for columna, valor in datos.items():
        if valor is None:
            condiciones.append(f"{columna} IS NULL")
        else:
            condiciones.append(f"{columna} = ?")
            valores.append(valor)
    consulta = f"SELECT * FROM {tabla} WHERE " + " AND ".join(condiciones) + " LIMIT 1"
    fila = conn.execute(consulta, valores).fetchone()
    return fila[0] if fila else None


def _crear_plan_pago_importado(conn: sqlite3.Connection, datos: dict) -> None:
    """A diferencia del resto de las entidades importables, un PlanPago no
    es un simple INSERT: hay que pasar por `crear_plan_pago` (calcula
    MontoTotalAPagar/ImportePorCuota y genera las CuotaPlan) y, como el
    plan puede venir de meses atrás (ya en curso antes de empezar a usar
    el sistema), las cuotas de períodos anteriores al actual se marcan
    solas como pagadas para que no queden colgadas como pendientes."""
    faltantes = [
        columna for columna in ("MesAnoInicio", "MontoRefinanciado", "CantidadCuotas")
        if datos.get(columna) is None
    ]
    if faltantes:
        raise ValueError(f"Faltan columnas obligatorias: {', '.join(faltantes)}")

    id_plan = crear_plan_pago_historico(
        conn, id_profesional=datos["IdProfesional"], monto_refinanciado=datos["MontoRefinanciado"],
        cantidad_cuotas=datos["CantidadCuotas"], mes_ano_inicio=datos["MesAnoInicio"],
        porcentaje_interes_mensual=datos.get("PorcentajeInteresMensual") or 0.0,
        observacion=datos.get("Observacion"),
    )
    periodo_hoy = periodo_actual(conn)
    for cuota in obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=id_plan):
        if cuota["PeriodoImputado"] < periodo_hoy:
            marcar_cuota_pagada(conn, cuota["IdCuota"])


# Copias de stock que la hoja "Llave" ingresa sola a cada Tipo que crea,
# para que la hoja "LlaveMovimiento" (asignaciones a profesionales) nunca
# falle por falta de stock disponible, sin importar cuántas tenencias
# traiga la planilla — pedido explícito de la clienta: después de
# importar, ajusta el stock real a mano (Ingreso/Pérdida, desde la
# pantalla de Llaves) para que vuelva a reflejar la cantidad real que
# tiene en circulación.
_STOCK_INICIAL_IMPORTACION = 1000


def importar_hoja(
    conn: sqlite3.Connection, entidad: str, ws, *, mapa_codigo_llave: dict[str, int] | None = None,
) -> ResultadoImportacion:
    """`mapa_codigo_llave`: el diccionario {Código de planilla -> IdLlave}
    compartido entre las tres hojas de Llaves (ver `_resolver_referencias`)
    -- `importar_planilla` arma uno solo y lo pasa a las tres llamadas, en
    orden, para que la hoja "Llave" lo vaya completando y "LlaveAcceso"/
    "LlaveMovimiento" lo lean después."""
    resultado = ResultadoImportacion(entidad=entidad)
    filas = list(ws.iter_rows(values_only=True))
    if not filas:
        return resultado

    encabezados = [_normalizar_encabezado(str(c).strip()) if c is not None else "" for c in filas[0]]
    repo = obtener_repositorio(conn, entidad)

    for numero_fila, fila in enumerate(filas[1:], start=2):
        if fila is None or all(v is None or str(v).strip() == "" for v in fila):
            continue

        datos: dict = {}
        error_conversion = None
        for columna, valor in zip(encabezados, fila):
            if not columna:
                continue
            try:
                datos[columna] = _convertir_valor(columna, valor)
            except ValueError as exc:
                error_conversion = f"Columna '{columna}': {exc}"
                break
        if error_conversion:
            resultado.errores.append(f"Fila {numero_fila}: {error_conversion}")
            continue

        datos, errores_referencia = _resolver_referencias(conn, entidad, datos, mapa_codigo_llave=mapa_codigo_llave)
        if errores_referencia:
            for err in errores_referencia:
                resultado.errores.append(f"Fila {numero_fila}: {err}")
            continue

        # "Codigo" (hoja "Llave") no es columna de la tabla Llave -- es un
        # identificador puramente de planilla, se saca de `datos` ACÁ,
        # antes del chequeo de duplicados, para que `_buscar_identico` no
        # reviente contra la tabla ("no such column"). Único dentro de
        # esta misma hoja: dos Tipos de llave con el mismo Código dejarían
        # a "LlaveAcceso"/"LlaveMovimiento" sin forma de saber a cuál de
        # los dos se referían.
        codigo_llave_nuevo = None
        if entidad == "Llave":
            codigo_llave_nuevo = datos.pop("Codigo", None)
            if not codigo_llave_nuevo:
                resultado.errores.append(
                    f'Fila {numero_fila}: falta el "Codigo" de este Tipo de llave -- hace falta para '
                    'poder referenciarlo después en las hojas "LlaveAcceso"/"LlaveMovimiento"'
                )
                continue
            if mapa_codigo_llave is not None and codigo_llave_nuevo in mapa_codigo_llave:
                resultado.errores.append(
                    f"Fila {numero_fila}: el código '{codigo_llave_nuevo}' ya se usó antes "
                    "en esta misma hoja -- tiene que ser único"
                )
                continue

        # "DepositoAbonado" (hoja "LlaveMovimiento") tampoco es columna de
        # LlaveMovimiento -- la columna real es DepositoCobrado, que se
        # arma más abajo recién al crear el movimiento.
        deposito_abonado = bool(datos.pop("DepositoAbonado", 0)) if entidad == "LlaveMovimiento" else False

        # "LlaveAcceso"/"LlaveMovimiento" nunca se tratan como duplicadas
        # de una fila ya existente (mismo criterio que tenía la hoja única
        # "Llave" para sus accesos/tenencias antes de este rediseño): un
        # acceso o una tenencia nueva siempre se agrega, no se compara.
        if entidad not in ("LlaveAcceso", "LlaveMovimiento"):
            id_identico = _buscar_identico(conn, entidad, datos)
            if id_identico is not None:
                resultado.filas_duplicadas += 1
                if entidad == "Llave" and mapa_codigo_llave is not None:
                    mapa_codigo_llave[codigo_llave_nuevo] = id_identico
                continue

        try:
            if entidad == "PlanPago":
                _crear_plan_pago_importado(conn, datos)
            elif entidad == "Llave":
                tipo = datos.get("Tipo")
                if tipo not in _LETRA_POR_TIPO:
                    raise ValueError(
                        f"Tipo de llave inválido o vacío: {tipo!r} "
                        f"(debe ser {', '.join(_LETRA_POR_TIPO)})"
                    )
                datos["Nombre"] = siguiente_nombre_llave(conn, tipo)
                id_llave = repo.crear(**datos)
                ingresar_copias(
                    conn, id_llave=id_llave, cantidad=_STOCK_INICIAL_IMPORTACION,
                    observacion="Stock inicial de importación (ajustar con Ingreso/Pérdida)",
                )
                if mapa_codigo_llave is not None:
                    mapa_codigo_llave[codigo_llave_nuevo] = id_llave
            elif entidad == "LlaveAcceso":
                agregar_acceso_llave(
                    conn, id_llave=datos.pop("IdLlave"), id_edificio=datos.pop("IdEdificio"),
                    id_unidad=datos.pop("IdUnidad"), nombre=datos.get("Nombre"),
                    observacion=datos.get("Observacion"),
                )
            elif entidad == "LlaveMovimiento":
                id_llave = datos["IdLlave"]
                llave = obtener_repositorio(conn, "Llave").obtener(id_llave)
                # Tenencia histórica, de antes de empezar a usar el
                # sistema: a diferencia de `asignar_llave` (la función que
                # usa la pantalla para una asignación NUEVA), acá nunca se
                # genera un CargoEspecial — si ya abonó el depósito, fue
                # en su momento, por fuera del sistema; si no lo abonó, no
                # hay por qué cobrárselo recién ahora solo por estar
                # importando el dato.
                obtener_repositorio(conn, "LlaveMovimiento").crear(
                    IdLlave=id_llave, Tipo="Asignación", Fecha=fecha_actual(conn).isoformat(),
                    IdProfesional=datos["IdProfesional"], Cantidad=1,
                    DepositoCobrado=int(deposito_abonado),
                    MontoCobrado=llave["ValorDepositoActual"] if deposito_abonado else None,
                    Observacion="Tenencia cargada por importación",
                )
            else:
                repo.crear(**datos)
            resultado.filas_importadas += 1
        except (sqlite3.Error, ValueError) as exc:
            resultado.errores.append(f"Fila {numero_fila}: {exc}")

    return resultado


def importar_planilla(conn: sqlite3.Connection, ruta_excel: Path | str) -> list[ResultadoImportacion]:
    wb = load_workbook(ruta_excel, data_only=True)
    resultados = []
    # Compartido entre las tres hojas de Llaves (ver `importar_hoja`) --
    # vive acá, no dentro de `importar_hoja`, porque tiene que persistir
    # ENTRE una llamada y la siguiente: la hoja "Llave" lo completa, las
    # hojas "LlaveAcceso"/"LlaveMovimiento" (que se procesan después, por
    # el orden de ENTIDADES_IMPORTABLES) lo leen.
    mapa_codigo_llave: dict[str, int] = {}
    for entidad in ENTIDADES_IMPORTABLES:
        if entidad not in wb.sheetnames:
            continue
        resultados.append(importar_hoja(conn, entidad, wb[entidad], mapa_codigo_llave=mapa_codigo_llave))
    return resultados
