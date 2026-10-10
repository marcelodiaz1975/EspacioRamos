"""Backup previo (Paso 1 del avance de mes, DC-06): copia de la base de
datos y de toda la carpeta base de archivos (fotos, documentación de
profesionales, PDFs generados) antes de avanzar el mes, para poder volver
atrás si algo sale mal en el proceso.

No sube nada a Google Drive por API — no hay credenciales ni librería de
Drive en el proyecto (sección 2: "Backup automático a Google Drive").
Configuracion.CarpetaBackup se espera que sea una carpeta ya sincronizada
por el cliente de escritorio de Google Drive que el operador instala en
su máquina: el backup en sí es copiar los archivos ahí adentro, la
sincronización a la nube la hace ese cliente, no esta aplicación.

Detección de base local desactualizada (pedido de la clienta: "que
detecte de alguna manera que la base de datos local no es la última que
se sincronizó... casi que me obligue a levantar y a usar lo
sincronizado"): `Configuracion.UltimoBackupPropio` guarda el timestamp
del backup que la base viva "dice ser" — se actualiza al generar un
backup propio (`generar_backup`) o al restaurar uno (`restaurar_backup`,
que hereda el timestamp del backup restaurado). Comparar fechas de
ARCHIVO (mtime del .db) se descartó a propósito: Drive no siempre
preserva esa fecha al sincronizar, y dos relojes de máquina distinta
pueden tener un desfasaje — un valor que vive adentro de los datos
mismos, y que viaja con cada restauración, es más confiable.
`hay_backup_mas_reciente_sin_sincronizar` es el chequeo que corre al
arrancar el programa (ver `gui_main.py`): si en la carpeta sincronizada
hay un backup con un timestamp más nuevo que el que esta base dice ser,
es que otra instalación avanzó más que esta copia local.

"Modo local, sin sincronizar" (la vía de escape protegida por contraseña
maestra del cartel bloqueante que dispara ese chequeo): un archivo
marcador al lado de la base (mismo patrón que
`app.negocio.instancia_unica.BloqueoInstanciaUnica` para su lock, un
archivo chico junto al .db en vez de una columna dentro de la base —
así sigue siendo visible aunque la base misma esté desactualizada o
corrupta) que, mientras esté presente, hace que `generar_backup` se
niegue a correr: ningún backup generado desde esta rama diverge puede
llegarle a Drive y pisar la cadena de backups legítima que sigue
avanzando en otro lado. Se desactiva solo, automáticamente, la próxima
vez que se restaure un backup de verdad en esta misma máquina."""
from __future__ import annotations

import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path

from app.negocio.archivos_generados import carpeta_base
from app.repositorio.registro import obtener_repositorio

_DIAS_MAXIMOS_POR_FRECUENCIA = {
    "diario": 1, "diaria": 1,
    "semanal": 7,
    "quincenal": 15,
    "mensual": 30,
}


def carpeta_backup(conn: sqlite3.Connection) -> Path | None:
    fila = conn.execute("SELECT CarpetaBackup FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    ruta = fila["CarpetaBackup"] if fila else None
    return Path(ruta) if ruta else None


def _ruta_base_datos(conn: sqlite3.Connection) -> Path | None:
    """Ruta del archivo de la base "main" de esta conexión (vía PRAGMA
    database_list) — vacía para bases en memoria, que no hay qué copiar."""
    fila = conn.execute("PRAGMA database_list").fetchone()
    archivo = fila["file"] if fila else None
    return Path(archivo) if archivo else None


def _marcador_sin_sincronizar(db_path: Path) -> Path:
    db_path = Path(db_path)
    return db_path.with_name(db_path.name + ".sin_sincronizar")


def activar_modo_sin_sincronizar(db_path: Path) -> None:
    """Vía de escape del cartel bloqueante de arranque (ya verificada la
    contraseña maestra del lado de la GUI antes de llamar acá) — deja
    usar el sistema con la base local desactualizada, pero bloquea
    `generar_backup` hasta la próxima restauración real."""
    _marcador_sin_sincronizar(Path(db_path)).touch()


def modo_sin_sincronizar_activo(db_path: Path) -> bool:
    return _marcador_sin_sincronizar(Path(db_path)).is_file()


def desactivar_modo_sin_sincronizar(db_path: Path) -> None:
    marcador = _marcador_sin_sincronizar(Path(db_path))
    if marcador.is_file():
        marcador.unlink()


def generar_backup(conn: sqlite3.Connection, momento: datetime | None = None) -> Path:
    """Copia la base de datos (con `sqlite3.Connection.backup`, seguro
    aunque haya escrituras en curso — no es una copia cruda del archivo)
    y toda la carpeta base de archivos generados a una subcarpeta con
    fecha y hora dentro de la carpeta de backup configurada. Devuelve la
    carpeta creada.

    Se niega a correr en "modo local, sin sincronizar" (ver docstring
    del módulo) — ningún backup generado desde una rama que se sabe
    desactualizada puede llegarle a Drive."""
    ruta_db = _ruta_base_datos(conn)
    if ruta_db is not None and modo_sin_sincronizar_activo(ruta_db):
        raise ValueError(
            "Esta instalación está en modo local, sin sincronizar (ver Panel de control) — no se pueden "
            "generar backups hasta restaurar la versión sincronizada desde Google Drive."
        )

    destino_base = carpeta_backup(conn)
    if destino_base is None:
        raise ValueError("Configurá primero la carpeta de backup en Configuración general.")

    momento = momento or datetime.now()
    destino = destino_base / momento.strftime("Backup %Y-%m-%d %Hh%M")
    destino.mkdir(parents=True, exist_ok=True)

    if ruta_db is not None and ruta_db.is_file():
        destino_conn = sqlite3.connect(destino / ruta_db.name)
        try:
            conn.backup(destino_conn)
        finally:
            destino_conn.close()

    base_archivos = carpeta_base(conn)
    if base_archivos is not None and base_archivos.is_dir():
        shutil.copytree(base_archivos, destino / "Archivos", dirs_exist_ok=True)

    obtener_repositorio(conn, "Configuracion").actualizar(1, UltimoBackupPropio=momento.isoformat())

    return destino


def buscar_backup_mas_reciente(carpeta: Path) -> Path | None:
    """La más reciente de las subcarpetas "Backup AAAA-MM-DD HHhMM" de
    `carpeta` (orden alfabético == orden cronológico, por el formato de
    fecha usado). None si no hay ninguna."""
    if not carpeta.is_dir():
        return None
    candidatos = sorted(p for p in carpeta.iterdir() if p.is_dir() and p.name.startswith("Backup "))
    return candidatos[-1] if candidatos else None


def _fecha_hora_backup(carpeta: Path) -> datetime | None:
    """Fecha y hora codificadas en el nombre "Backup AAAA-MM-DD HHhMM" de
    una subcarpeta de backup generada por `generar_backup`."""
    try:
        return datetime.strptime(carpeta.name, "Backup %Y-%m-%d %Hh%M")
    except ValueError:
        return None


def _fecha_backup(carpeta: Path) -> date | None:
    momento = _fecha_hora_backup(carpeta)
    return momento.date() if momento is not None else None


def ultimo_backup(conn: sqlite3.Connection) -> datetime | None:
    """Fecha y hora del backup más reciente ya generado (Panel de
    control, leyenda arriba de "Generar backup ahora") — `None` sin
    carpeta de backup configurada o si todavía no se generó ninguno."""
    carpeta = carpeta_backup(conn)
    if carpeta is None:
        return None
    carpeta_mas_reciente = buscar_backup_mas_reciente(carpeta)
    if carpeta_mas_reciente is None:
        return None
    return _fecha_hora_backup(carpeta_mas_reciente)


def backup_vencido(conn: sqlite3.Connection, hoy: date) -> bool:
    """Sección 3.28 (Configuracion.FrecuenciaBackupDrive): True si pasó más
    tiempo que la frecuencia configurada desde el último backup generado.
    No hay nada que evaluar (False) sin carpeta de backup configurada,
    sin frecuencia configurada, o con un texto que no coincide con
    ninguna frecuencia conocida ("Diario"/"Semanal"/"Quincenal"/
    "Mensual") — nada de esto bloquea el uso del sistema, la alerta es
    solo un recordatorio."""
    cfg = conn.execute(
        "SELECT FrecuenciaBackupDrive, CarpetaBackup FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    if not cfg or not cfg["CarpetaBackup"] or not cfg["FrecuenciaBackupDrive"]:
        return False
    dias_maximos = _DIAS_MAXIMOS_POR_FRECUENCIA.get(cfg["FrecuenciaBackupDrive"].strip().lower())
    if dias_maximos is None:
        return False

    ultimo = buscar_backup_mas_reciente(Path(cfg["CarpetaBackup"]))
    if ultimo is None:
        return True
    fecha_ultimo = _fecha_backup(ultimo)
    if fecha_ultimo is None:
        return True
    return (hoy - fecha_ultimo).days > dias_maximos


def listar_backups(carpeta: Path) -> list[Path]:
    """Todas las subcarpetas "Backup AAAA-MM-DD HHhMM" de `carpeta`, de
    la más reciente a la más vieja — a diferencia de
    `buscar_backup_mas_reciente` (siempre una sola, la más nueva), esta
    es para ofrecer una ELECCIÓN puntual (botón "Restaurar backup" de
    Panel de control: no siempre se quiere volver justo al último)."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        return []
    return sorted(
        (p for p in carpeta.iterdir() if p.is_dir() and p.name.startswith("Backup ")),
        reverse=True,
    )


def restaurar_backup_desde(origen: Path, db_path: Path) -> None:
    """El mecanismo real de restauración, sobre un backup YA ELEGIDO
    (`origen`) — compartido por `restaurar_backup` (siempre el más
    reciente, instalación nueva o base desactualizada) y por el botón
    "Restaurar backup" de Panel de control (`app/gui/pantallas/
    panel_control.py`, elige cuál de la lista, no necesariamente el más
    reciente).

    Esta restauración hace que la base "se convierta" en esa versión: su
    propio `UltimoBackupPropio` pasa a ser el timestamp de `origen` (no
    "ahora" — el momento que ese backup representa), y se desactiva el
    "modo local, sin sincronizar" si esta máquina lo tenía activo (ver
    docstring del módulo) — restaurar de verdad es, justamente, volver a
    la cadena de backups legítima."""
    origen = Path(origen)
    archivos_db = list(origen.glob("*.db"))
    if not archivos_db:
        raise ValueError(f"El backup en {origen} no tiene ningún archivo de base de datos.")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archivos_db[0], db_path)

    # init_database (no get_connection) para que una base restaurada de
    # una versión vieja del programa — sin UltimoBackupPropio todavía —
    # llegue migrada antes de escribirle esa columna.
    from app.db.init_db import init_database

    conn_restaurada = init_database(db_path)
    try:
        origen_archivos = origen / "Archivos"
        if origen_archivos.is_dir():
            base_archivos = carpeta_base(conn_restaurada)
            if base_archivos is not None:
                shutil.copytree(origen_archivos, base_archivos, dirs_exist_ok=True)

        momento_origen = _fecha_hora_backup(origen)
        if momento_origen is not None:
            obtener_repositorio(conn_restaurada, "Configuracion").actualizar(
                1, UltimoBackupPropio=momento_origen.isoformat(),
            )
    finally:
        conn_restaurada.close()

    desactivar_modo_sin_sincronizar(db_path)


def restaurar_backup(carpeta_backups: Path, db_path: Path) -> Path:
    """Instalación en máquina nueva (sección 2: "restauración automática
    desde Google Drive") o base desactualizada: busca el backup más
    reciente dentro de `carpeta_backups` (la carpeta de Drive que el
    operador ya tiene sincronizada en esta máquina) y lo restaura con
    `restaurar_backup_desde`. Devuelve la carpeta de backup que se usó."""
    origen = buscar_backup_mas_reciente(Path(carpeta_backups))
    if origen is None:
        raise ValueError(f"No se encontró ningún backup en {carpeta_backups}.")
    restaurar_backup_desde(origen, db_path)
    return origen


def hay_backup_mas_reciente_sin_sincronizar(conn: sqlite3.Connection) -> Path | None:
    """El chequeo que corre al arrancar el programa (ver `gui_main.py`):
    si en la carpeta de backup (sincronizada por Drive) hay un backup con
    un timestamp más nuevo que el que esta base dice ser
    (`Configuracion.UltimoBackupPropio`), devuelve esa carpeta — es la
    señal de que otra instalación generó un backup más avanzado que esta
    copia local. `None` sin carpeta configurada, sin ningún backup
    todavía, o si esta base ya está al día (el caso normal: tu propio
    backup más reciente, o cualquiera posterior restaurado acá)."""
    carpeta = carpeta_backup(conn)
    if carpeta is None:
        return None
    mas_reciente = buscar_backup_mas_reciente(carpeta)
    if mas_reciente is None:
        return None
    momento_backup = _fecha_hora_backup(mas_reciente)
    if momento_backup is None:
        return None

    fila = conn.execute("SELECT UltimoBackupPropio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    valor_propio = fila["UltimoBackupPropio"] if fila else None
    propio = datetime.fromisoformat(valor_propio) if valor_propio else None

    if propio is not None and momento_backup <= propio:
        return None
    return mas_reciente
