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


def liberar_posicion(conn: sqlite3.Connection, id_placa: int) -> None:
    """Deja la posición vacía otra vez (no queda ningún registro) — para
    cuando la clienta saca la placa física sin armarle una nueva a otro
    profesional en el momento."""
    obtener_repositorio(conn, "Placa").eliminar(id_placa)
