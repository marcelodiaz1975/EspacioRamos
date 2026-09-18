"""Migraciones incrementales: columnas nuevas que se agregan a tablas ya
existentes, columnas viejas que se sacan, y tablas viejas que se dan de
baja. `schema.sql` solo crea tablas con `CREATE TABLE IF NOT EXISTS` —
eso no hace nada en una base que ya existe, así que un cambio de columnas
hecho ahí nunca se refleja solo en una base ya en uso. Cada entrada de
`_COLUMNAS_NUEVAS` se aplica con `ALTER TABLE ... ADD COLUMN` si la
columna todavía no existe, cada entrada de `_COLUMNAS_ELIMINADAS` con
`ALTER TABLE ... DROP COLUMN` si todavía está, y cada entrada de
`_TABLAS_ELIMINADAS` se borra con `DROP TABLE` si la tabla todavía está
— así una base vieja se pone al día la próxima vez que esta app la abre.
Al agregar una columna nueva a una tabla existente, sumarla tanto en
`schema.sql` (para que una base nueva ya nazca con ella) como en
`_COLUMNAS_NUEVAS` acá (para que una base vieja la reciba); al sacar una
columna de `schema.sql`, sumarla en `_COLUMNAS_ELIMINADAS`; al sacar una
tabla entera, sumarla en `_TABLAS_ELIMINADAS`."""
from __future__ import annotations

import sqlite3

# (tabla, columna, definición SQL de la columna — tipo + constraints)
_COLUMNAS_NUEVAS: list[tuple[str, str, str]] = [
    ("Ausencia", "IdReservaAislada", "INTEGER REFERENCES ReservaAislada(IdReservaAislada)"),
    ("Ausencia", "HoraInicio", "REAL"),
    ("Ausencia", "HoraFin", "REAL"),
    ("HistorialPagos", "SaldoAnterior", "REAL"),
    ("HistorialPagos", "SaldoNuevo", "REAL"),
    ("HistorialPagos", "RegistroModificado", "INTEGER NOT NULL DEFAULT 0"),
    ("CargoEspecial", "Fecha", "TEXT"),
    ("LiquidacionEmitida", "FechaHoraGeneracion", "TEXT"),
    ("Consultorio", "Placard", "INTEGER NOT NULL DEFAULT 0"),
    ("AumentoAplicado", "EsquemaNuevosIds", "TEXT"),
    ("AumentoAplicado", "EsquemaAnterioresIds", "TEXT"),
    ("AumentoAplicado", "LiquidacionesRegeneradasJson", "TEXT"),
    ("Unidad", "CampoLibre1", "TEXT"),
    ("Unidad", "CampoLibre2", "TEXT"),
    ("Unidad", "CampoLibre3", "TEXT"),
    ("Edificio", "CampoLibre1", "TEXT"),
    ("Edificio", "CampoLibre2", "TEXT"),
    ("Edificio", "CampoLibre3", "TEXT"),
    ("Consultorio", "CampoLibre1", "TEXT"),
    ("Consultorio", "CampoLibre2", "TEXT"),
    ("Consultorio", "CampoLibre3", "TEXT"),
    ("Imagen", "Localidad", "TEXT"),
    ("Edificio", "IdLocalidad", "INTEGER REFERENCES Localidad(IdLocalidad)"),
    ("Imagen", "IdLocalidad", "INTEGER REFERENCES Localidad(IdLocalidad)"),
    ("Imagen", "EtiquetaLibre", "TEXT"),
    ("Responsable", "CampoLibre1", "TEXT"),
    ("Responsable", "CampoLibre2", "TEXT"),
    ("Responsable", "CampoLibre3", "TEXT"),
    ("TipoLicencia", "CampoLibre1", "TEXT"),
    ("TipoLicencia", "CampoLibre2", "TEXT"),
    ("TipoLicencia", "CampoLibre3", "TEXT"),
    ("Configuracion", "VisualizarCamposLibres", "INTEGER NOT NULL DEFAULT 1"),
    ("CondicionNorma", "CampoLibre1", "TEXT"),
    ("CondicionNorma", "CampoLibre2", "TEXT"),
    ("CondicionNorma", "CampoLibre3", "TEXT"),
]

# (tabla, columna) que existían en versiones anteriores y se dieron de baja
# — Panel de vidrio/luz natural se reemplaza por Placard como
# característica a cargar del consultorio (decisión de la clienta):
# no es un simple cambio de nombre, así que el valor viejo no se traslada.
_COLUMNAS_ELIMINADAS: list[tuple[str, str]] = [
    ("Consultorio", "PanelVidrioLuzNatural"),
    ("Edificio", "DomicilioLocalidad"),
    ("Imagen", "Localidad"),
]

# Tablas que existían en versiones anteriores y se dieron de baja del todo
# (decisión de la clienta sobre HistorialOferta: "búsqueda realizada es
# búsqueda terminada", no se guarda ningún historial de Oferta de
# consultorios).
_TABLAS_ELIMINADAS: list[str] = [
    "HistorialOferta",
]

# Consultorio.TamanoClasificacion pasó de texto libre a catálogo cerrado
# (mismos 3 valores que app.negocio.oferta_busqueda.TAMANOS_CONSULTORIO,
# duplicados acá en vez de importados para no hacer que la capa de base
# de datos dependa de la de negocio). Normaliza mayúsculas/espacios de lo
# que ya coincide y vacía cualquier otro valor viejo (ej. "Pequeño") que
# haya quedado cargado de cuando el campo era libre — así el filtro de
# tamaño de Oferta de consultorios, que compara por igualdad exacta,
# encuentra coincidencia con cualquier consultorio ya cargado.
_TAMANOS_CONSULTORIO = ["Grande", "Intermedio", "Chico"]

# Edificio.DomicilioLocalidad e Imagen.Localidad pasaron de texto libre a
# una referencia a la tabla Localidad (id propio — la clienta lo pidió
# para poder armar rutas de archivos estables, ver app.negocio.imagenes),
# que además suma Partido/Provincia/País como datos de referencia.
_TABLAS_LOCALIDAD_TEXTO = (
    ("Edificio", "DomicilioLocalidad", "IdLocalidad"),
    ("Imagen", "Localidad", "IdLocalidad"),
)


def _obtener_o_crear_localidad(conn: sqlite3.Connection, texto: str, cache: dict[str, int]) -> int:
    if texto in cache:
        return cache[texto]
    fila = conn.execute("SELECT IdLocalidad FROM Localidad WHERE Localidad = ?", (texto,)).fetchone()
    if fila:
        id_localidad = fila["IdLocalidad"]
    else:
        cur = conn.execute("INSERT INTO Localidad (Localidad) VALUES (?)", (texto,))
        id_localidad = cur.lastrowid
    cache[texto] = id_localidad
    return id_localidad


def _migrar_localidad_texto_a_tabla(conn: sqlite3.Connection) -> None:
    """Antes de sacar las columnas de texto viejas (ver
    `_COLUMNAS_ELIMINADAS`), crea (o reusa) una fila de Localidad por cada
    texto distinto ya cargado en Edificio.DomicilioLocalidad o
    Imagen.Localidad y apunta cada fila vieja a esa fila — mismo texto,
    misma fila de Localidad, para las dos tablas."""
    existe_localidad = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'Localidad'"
    ).fetchone()
    if not existe_localidad:
        return
    cache: dict[str, int] = {}
    for tabla, columna_texto, columna_id in _TABLAS_LOCALIDAD_TEXTO:
        existe_tabla = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabla,)
        ).fetchone()
        if not existe_tabla:
            continue
        columnas = {f["name"] for f in conn.execute(f"PRAGMA table_info({tabla})").fetchall()}
        if columna_texto not in columnas or columna_id not in columnas:
            continue
        filas = conn.execute(
            f"SELECT DISTINCT {columna_texto} AS texto FROM {tabla} "
            f"WHERE {columna_texto} IS NOT NULL AND TRIM({columna_texto}) != '' AND {columna_id} IS NULL"
        ).fetchall()
        for f in filas:
            id_localidad = _obtener_o_crear_localidad(conn, f["texto"], cache)
            conn.execute(
                f"UPDATE {tabla} SET {columna_id} = ? WHERE {columna_texto} = ? AND {columna_id} IS NULL",
                (id_localidad, f["texto"]),
            )


def _normalizar_tamanos_consultorio(conn: sqlite3.Connection) -> None:
    existe_tabla = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'Consultorio'"
    ).fetchone()
    if not existe_tabla:
        return
    for valor in _TAMANOS_CONSULTORIO:
        conn.execute(
            "UPDATE Consultorio SET TamanoClasificacion = ? "
            "WHERE TamanoClasificacion IS NOT NULL AND LOWER(TRIM(TamanoClasificacion)) = ?",
            (valor, valor.lower()),
        )
    placeholders = ", ".join("?" for _ in _TAMANOS_CONSULTORIO)
    conn.execute(
        "UPDATE Consultorio SET TamanoClasificacion = NULL "
        f"WHERE TamanoClasificacion IS NOT NULL AND TamanoClasificacion NOT IN ({placeholders})",
        _TAMANOS_CONSULTORIO,
    )


def aplicar_migraciones(conn: sqlite3.Connection) -> None:
    for tabla, columna, definicion in _COLUMNAS_NUEVAS:
        existe_tabla = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabla,)
        ).fetchone()
        if not existe_tabla:
            continue  # tabla nueva que todavía no existe en esta base — nada que migrarle
        columnas_existentes = {f["name"] for f in conn.execute(f"PRAGMA table_info({tabla})").fetchall()}
        if columna not in columnas_existentes:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
    _migrar_localidad_texto_a_tabla(conn)
    for tabla, columna in _COLUMNAS_ELIMINADAS:
        existe_tabla = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabla,)
        ).fetchone()
        if not existe_tabla:
            continue
        columnas_existentes = {f["name"] for f in conn.execute(f"PRAGMA table_info({tabla})").fetchall()}
        if columna in columnas_existentes:
            conn.execute(f"ALTER TABLE {tabla} DROP COLUMN {columna}")
    for tabla in _TABLAS_ELIMINADAS:
        conn.execute(f"DROP TABLE IF EXISTS {tabla}")
    _normalizar_tamanos_consultorio(conn)
    conn.commit()
