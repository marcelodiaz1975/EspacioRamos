"""Placas de nombre de los profesionales en el tablero magnético de cada
Unidad (sección 3.8/Etapa 9, redefinida en conversación con la clienta).

Cada Unidad tiene un tablero interno con una cantidad fija de posiciones
(Unidad.CantLimitePlacas, editable por unidad — es el tablero relevante
para el sistema). El tablerito más chico de la puerta de cada unidad,
con una posición exacta por consultorio, NO se modela: no hace falta
administrarlo.

Cada posición tiene como mucho UNA placa a la vez — no se lleva
historial de placas viejas. Cuando la clienta reutiliza una posición
para otro profesional, rompe la placa física vieja y arma la nueva:
`asignar_placa` pisa el mismo registro (mismo IdUnidad + PosicionTablero)
en vez de crear uno nuevo. Si el profesional se va y la posición NO se
reutiliza, el registro se deja tal cual — sigue mostrando a ese
profesional a modo de consulta, sin que el sistema avise nada; así, si
vuelve a trabajar en la unidad, la clienta sabe que ya tiene una placa
hecha ahí.

El vínculo es por IdProfesional (fijo): un cambio de categoría/código
(ej. R3 a X4) no requiere tocar nada acá, se refleja solo en cualquier
consulta en vivo (mismo mecanismo que ya usan pagos, llaves, etc. — ver
HistorialCodigo). El nombre grabado en la placa física es Tratamiento +
NombrePila + Apellido del profesional, salvo que la placa sea
personalizada (EsPersonalizada), en cuyo caso se usa el texto cargado a
mano — nunca lleva el código, así que un cambio de código no vuelve
obsoleta a la placa ya hecha.

`Placa.Activo` queda siempre en 1 en este esquema (ya no representa
"vigente" vs "histórico", porque no se guarda historial): se mantiene
sin migrar el esquema porque `app.pdf.placas_pdf.generar_pdf_placas`
(el PDF de referencia del tablero, automático en el avance de mes) ya
filtra por él.

La impresión puntual de placas nuevas (`app.pdf.placas_pdf.
generar_pdf_placas_seleccionadas`) es independiente de este modelo: se arma
buscando profesionales (con o sin placa asignada todavía) y no necesita
pasar por acá."""
from __future__ import annotations

import sqlite3
from datetime import date

from app.negocio.dias import fecha_actual
from app.repositorio.registro import obtener_repositorio


def nombre_estandar(profesional: sqlite3.Row) -> str:
    """"Tratamiento NombrePila Apellido" — el mismo texto que se graba en
    la placa física salvo que sea personalizada."""
    partes = [p for p in (profesional["Tratamiento"], profesional["NombrePila"], profesional["Apellido"]) if p]
    return " ".join(partes) if partes else profesional["Apellido"]


def texto_para_imprimir(profesional: sqlite3.Row, *, linea1: str | None = None, linea2: str | None = None) -> str:
    """Texto a grabar en una placa de la hoja de impresión puntual
    (independiente de si el profesional ya tiene o no una posición
    asignada en algún tablero, y del nombre grabado que tenga ahí si la
    tiene). Con `linea1` cargado se usa tal cual (más `linea2` si
    también se cargó) — para el caso personalizado, ej. "Equipo Sol
    terapias" en dos renglones definidos a mano. Sin `linea1`, se usa el
    nombre estándar del profesional en una sola línea de texto: el
    renderizador (Paragraph de reportlab en el PDF, QLabel con
    word-wrap en la vista previa) la parte solo si no entra completa en
    el ancho de la placa — nunca a mitad de palabra."""
    if linea1:
        lineas = [linea1] + ([linea2] if linea2 else [])
        return "\n".join(lineas)
    return nombre_estandar(profesional)


def nombre_grabado(placa: sqlite3.Row, profesional: sqlite3.Row) -> str:
    if placa["EsPersonalizada"] and placa["NombreGrabado"]:
        return placa["NombreGrabado"]
    return nombre_estandar(profesional)


def personalizacion_del_profesional(conn: sqlite3.Connection, id_profesional: int) -> str | None:
    """Pedido explícito de la clienta: el nombre personalizado se carga y
    guarda solo desde el diálogo de Asignar/Reasignar (primera solapa) —
    "Agregar a impresión" (segunda solapa) ya no pide nada, solo LEVANTA
    esa info. Si el profesional tiene alguna placa personalizada (en
    cualquier unidad, no hace falta que sea en la que se está imprimiendo
    puntualmente), devuelve su `NombreGrabado` tal cual está guardado —
    una sola línea, o dos separadas por "\\n" si se cargó una segunda
    línea (mismo formato que ya arma `texto_para_imprimir` al unir
    linea1/linea2). Si tiene más de una placa personalizada (un
    profesional con más de una unidad, caso raro) se usa la primera que
    aparezca — no hay forma de saber cuál "corresponde" a una impresión
    puntual, que no está atada a ninguna unidad en particular. `None` si
    no tiene ninguna placa personalizada."""
    for placa in listar_placas(conn, id_profesional=id_profesional):
        if placa["EsPersonalizada"] and placa["NombreGrabado"]:
            return placa["NombreGrabado"]
    return None


def listar_placas(
    conn: sqlite3.Connection, *, ids_localidad: list[int | None] | None = None,
    ids_edificio: list[int] | None = None, ids_unidad: list[int] | None = None,
    id_profesional: int | None = None,
) -> list[sqlite3.Row]:
    """Placas existentes (posiciones ocupadas) con los filtros combinados
    — localidad/edificio/unidad amplían o reducen el rango de búsqueda,
    profesional puntual responde "¿en qué unidades tiene placa?"."""
    sql = """
        SELECT p.*, u.Departamento, u.IdEdificio, e.Nombre AS NombreEdificio, loc.Localidad AS DomicilioLocalidad
        FROM Placa p
        JOIN Unidad u ON u.IdUnidad = p.IdUnidad
        JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad
        WHERE 1=1
    """
    parametros: list = []
    if ids_localidad:
        marcas = []
        for id_localidad in ids_localidad:
            if id_localidad is None:
                marcas.append("e.IdLocalidad IS NULL")
            else:
                marcas.append("e.IdLocalidad = ?")
                parametros.append(id_localidad)
        sql += " AND (" + " OR ".join(marcas) + ")"
    if ids_edificio:
        placeholders = ", ".join("?" for _ in ids_edificio)
        sql += f" AND u.IdEdificio IN ({placeholders})"
        parametros.extend(ids_edificio)
    if ids_unidad:
        placeholders = ", ".join("?" for _ in ids_unidad)
        sql += f" AND p.IdUnidad IN ({placeholders})"
        parametros.extend(ids_unidad)
    if id_profesional is not None:
        sql += " AND p.IdProfesional = ?"
        parametros.append(id_profesional)
    sql += " ORDER BY e.Nombre, u.Departamento, p.PosicionTablero"
    return conn.execute(sql, parametros).fetchall()


def posiciones_libres(conn: sqlite3.Connection, id_unidad: int) -> list[int]:
    """Posiciones del tablero de `id_unidad` que todavía no tienen placa
    — para ofrecerlas al armar una placa nueva (a diferencia de
    reasignar una posición ya ocupada)."""
    unidad = obtener_repositorio(conn, "Unidad").obtener(id_unidad)
    if unidad is None or not unidad["CantLimitePlacas"]:
        return []
    ocupadas = {
        f["PosicionTablero"] for f in obtener_repositorio(conn, "Placa").listar(IdUnidad=id_unidad)
        if f["PosicionTablero"] is not None
    }
    return [p for p in range(1, unidad["CantLimitePlacas"] + 1) if p not in ocupadas]


def unidades_en_alcance(
    conn: sqlite3.Connection, *, ids_localidad: list[int | None] | None = None,
    ids_edificio: list[int] | None = None, ids_unidad: list[int] | None = None,
) -> list[sqlite3.Row]:
    """Unidades (con su Edificio/Localidad) que entran en el mismo
    alcance de filtros que `listar_placas` — a diferencia de esa, no
    pasa por la tabla `Placa`, así que también alcanza unidades sin
    ninguna placa asignada todavía. Usada para ofrecer también las
    posiciones LIBRES del tablero (`posiciones_libres`) cuando el
    filtro "Posiciones que se podrían liberar" está activo — pedido
    explícito de la clienta: "que muestre también las posiciones
    libres, aparte de las ocupadas según la situación de cada
    profesional"."""
    sql = """
        SELECT u.IdUnidad, u.CantLimitePlacas, u.Departamento, u.IdEdificio,
               e.Nombre AS NombreEdificio, loc.Localidad AS DomicilioLocalidad
        FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        LEFT JOIN Localidad loc ON loc.IdLocalidad = e.IdLocalidad
        WHERE 1=1
    """
    parametros: list = []
    if ids_localidad:
        marcas = []
        for id_localidad in ids_localidad:
            if id_localidad is None:
                marcas.append("e.IdLocalidad IS NULL")
            else:
                marcas.append("e.IdLocalidad = ?")
                parametros.append(id_localidad)
        sql += " AND (" + " OR ".join(marcas) + ")"
    if ids_edificio:
        placeholders = ", ".join("?" for _ in ids_edificio)
        sql += f" AND u.IdEdificio IN ({placeholders})"
        parametros.extend(ids_edificio)
    if ids_unidad:
        placeholders = ", ".join("?" for _ in ids_unidad)
        sql += f" AND u.IdUnidad IN ({placeholders})"
        parametros.extend(ids_unidad)
    return conn.execute(sql, parametros).fetchall()


def _reserva_regular_activa_en_unidad(conn: sqlite3.Connection, id_profesional: int, id_unidad: int, hoy: str) -> bool:
    """Mismo criterio que `app.negocio.panel_control._reserva_regular_
    activa`/`app.negocio.mensajeria._reserva_regular_activa` (vigente
    HOY, no "alguna vez"), acá acotado a los consultorios de UNA unidad
    puntual — la de la placa que se está evaluando."""
    return conn.execute(
        """
        SELECT 1 FROM ReservaRegular rr JOIN Consultorio c ON c.IdConsultorio = rr.IdConsultorio
        WHERE rr.IdProfesional = ? AND c.IdUnidad = ?
              AND rr.VigenciaInicio <= ? AND (rr.VigenciaFin IS NULL OR rr.VigenciaFin >= ?)
        LIMIT 1
        """,
        (id_profesional, id_unidad, hoy, hoy),
    ).fetchone() is not None


def _hace_mas_de_un_anio_sin_reservar(conn: sqlite3.Connection, id_profesional: int, hoy: date) -> bool:
    """Categoría A: sin ninguna `ReservaAislada` Confirmada (en TODO el
    espacio, no acotado a una unidad — pedido explícito de la clienta,
    a diferencia de R/E más abajo) con fecha dentro del último año.
    Mismo cálculo del límite de un año que `app.negocio.avance_mes.
    _limite_retencion_activos` (29 de febrero sin año bisiesto
    equivalente: se recorta al 28)."""
    try:
        limite = hoy.replace(year=hoy.year - 1).isoformat()
    except ValueError:
        limite = hoy.replace(year=hoy.year - 1, day=28).isoformat()
    ultima = conn.execute(
        "SELECT MAX(Fecha) AS Ultima FROM ReservaAislada WHERE IdProfesional = ? AND Estado = 'Confirmada'",
        (id_profesional,),
    ).fetchone()["Ultima"]
    return ultima is None or ultima < limite


def placa_se_podria_liberar(conn: sqlite3.Connection, placa: sqlite3.Row, hoy: date | None = None) -> bool:
    """Pedido explícito de la clienta ("Búsqueda y asignación de
    placas"): candidatas a revisar porque el profesional que ocupa esa
    posición da señales de ya no estar usando el espacio — el criterio
    es distinto por categoría, cada uno definido explícitamente por
    ella:
    - R: no tiene una `ReservaRegular` vigente HOY en la unidad de la
      placa (puede seguir reservando en otra unidad del espacio, eso no
      cuenta).
    - X: siempre candidata (sin reservas regulares propias, no hay una
      condición más puntual que mirar).
    - E: su Cabeza de equipo (categoría R) es el que realmente ocupa el
      consultorio — se mira si ESE R tiene `ReservaRegular` vigente hoy
      en la unidad de la placa, no el E (que nunca tiene reservas
      regulares propias, ver `crear_reserva_regular`). Sin cabeza válido
      cargado, se toma como candidata (no hay nada que la sostenga).
    - A: hace más de un año sin ninguna `ReservaAislada` Confirmada en
      TODO el espacio (pedido explícito: "no en la unidad solamente").
    - B y cualquier otra categoría, o sin profesional asignado: nunca
      candidata (la clienta no dio un criterio para B)."""
    if placa["IdProfesional"] is None:
        return False
    profesional = obtener_repositorio(conn, "Profesional").obtener(placa["IdProfesional"])
    if profesional is None:
        return False
    hoy = hoy or fecha_actual(conn)
    categoria = profesional["CategoriaProfesional"]
    if categoria == "R":
        return not _reserva_regular_activa_en_unidad(conn, profesional["IdProfesional"], placa["IdUnidad"], hoy.isoformat())
    if categoria == "X":
        return True
    if categoria == "E":
        id_cabeza = profesional["ProfesionalCabezaEquipo"]
        if id_cabeza is None:
            return True
        return not _reserva_regular_activa_en_unidad(conn, id_cabeza, placa["IdUnidad"], hoy.isoformat())
    if categoria == "A":
        return _hace_mas_de_un_anio_sin_reservar(conn, profesional["IdProfesional"], hoy)
    return False


def asignar_placa(
    conn: sqlite3.Connection, *, id_unidad: int, posicion: int, id_profesional: int,
    es_personalizada: bool = False, nombre_grabado_personalizado: str | None = None,
) -> int:
    """Ocupa una posición del tablero para un profesional. Si la posición
    ya tenía una placa (de éste u otro profesional), la pisa: coincide
    con lo físico (la clienta rompe la placa vieja y arma la nueva antes
    de tocar acá), así que no hace falta conservar ningún historial."""
    unidad = obtener_repositorio(conn, "Unidad").obtener(id_unidad)
    if unidad is None:
        raise ValueError("La unidad seleccionada no existe.")
    limite = unidad["CantLimitePlacas"] or 0
    if not (1 <= posicion <= limite):
        raise ValueError(f"La posición tiene que estar entre 1 y {limite} (capacidad del tablero de esta unidad).")
    if obtener_repositorio(conn, "Profesional").obtener(id_profesional) is None:
        raise ValueError("El profesional seleccionado no existe.")

    repo = obtener_repositorio(conn, "Placa")
    existente = next(
        (f for f in repo.listar(IdUnidad=id_unidad) if f["PosicionTablero"] == posicion), None,
    )
    nombre_personalizado = nombre_grabado_personalizado if es_personalizada else None
    if existente:
        repo.actualizar(
            existente["IdPlaca"], IdProfesional=id_profesional, EsPersonalizada=int(es_personalizada),
            NombreGrabado=nombre_personalizado,
        )
        return existente["IdPlaca"]
    return repo.crear(
        IdUnidad=id_unidad, PosicionTablero=posicion, IdProfesional=id_profesional, Activo=1,
        EsPersonalizada=int(es_personalizada), NombreGrabado=nombre_personalizado,
    )


def placa_faltante_para_reserva(conn: sqlite3.Connection, *, id_profesional: int, id_consultorio: int) -> list[str]:
    """Pedido explícito de la clienta, mismo criterio y mismo cartel que
    `app.negocio.llaves.llaves_faltantes_para_reserva` (con el que se
    combina en un único aviso desde `reservas.py`): al cargar una
    reserva (regular o aislada), chequea si el profesional ya tiene
    alguna placa asignada (en cualquier posición del tablero, no importa
    cuál) en la Unidad del consultorio reservado. Devuelve una lista de
    un solo texto ("la placa de la unidad {Departamento}") si le falta,
    vacía si ya tiene alguna ahí o si el consultorio/unidad no existen —
    puramente informativo, nunca bloquea la carga."""
    consultorio = obtener_repositorio(conn, "Consultorio").obtener(id_consultorio)
    if consultorio is None:
        return []
    unidad = obtener_repositorio(conn, "Unidad").obtener(consultorio["IdUnidad"])
    if unidad is None:
        return []
    tiene_placa = any(
        p["IdProfesional"] == id_profesional
        for p in obtener_repositorio(conn, "Placa").listar(IdUnidad=unidad["IdUnidad"])
    )
    if tiene_placa:
        return []
    return [f"la placa de la unidad {unidad['Departamento']}"]


def liberar_posicion(conn: sqlite3.Connection, id_placa: int) -> None:
    """Deja la posición vacía otra vez (no queda ningún registro) — para
    cuando la clienta saca la placa física sin armarle una nueva a otro
    profesional en el momento."""
    obtener_repositorio(conn, "Placa").eliminar(id_placa)
