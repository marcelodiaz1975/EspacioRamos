"""Carpetas y limpieza de los documentos que el sistema genera o administra
(Propuesta, Disponibilidad, Oferta de consultorios, Liquidación, fotos de
edificios/unidades/consultorios, documentación de profesionales): todos se
guardan bajo una única carpeta base configurada una sola vez (Configuracion.
CarpetaBaseArchivos), en subcarpetas fijas:

    {base}/Archivos varios/Propuesta/
    {base}/Archivos varios/Disponibilidad/
    {base}/Archivos varios/Oferta/
    {base}/Archivos varios/Placas/
    {base}/Profesionales/{IdCodigo}/
    {base}/Profesionales/{IdCodigo}/Documentación/
    {base}/Imagenes/{Alcance}_{Id}/

Los tres primeros son documentos únicos del espacio en general: cada
regeneración sobrescribe el anterior, no se acumula historial de archivos.
Profesionales/{IdCodigo} en cambio acumula las liquidaciones mensuales (y,
en su subcarpeta Documentación, cualquier archivo del profesional) de ese
profesional en particular — todo bajo el mismo código, así que se muda
entero cuando el código cambia (ver `renombrar_carpeta_profesional`).
Imagenes/{Alcance}_{Id} usa el ID interno (no un nombre editable) para no
depender de que el operador no le cambie el nombre al edificio/unidad más
adelante.
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import date
from pathlib import Path

SUBCARPETA_PROPUESTA = "Propuesta"
SUBCARPETA_DISPONIBILIDAD = "Disponibilidad"
SUBCARPETA_OFERTA = "Oferta"
SUBCARPETA_PLACAS = "Placas"
SUBCARPETA_MANUAL = "Manual"

_RETENCION_LIQUIDACIONES_ANIOS = 1


def carpeta_base(conn: sqlite3.Connection) -> Path | None:
    fila = conn.execute("SELECT CarpetaBaseArchivos FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    ruta = fila["CarpetaBaseArchivos"] if fila else None
    return Path(ruta) if ruta else None


def _requerir_carpeta_base(conn: sqlite3.Connection) -> Path:
    base = carpeta_base(conn)
    if base is None:
        raise ValueError(
            "Configurá primero la carpeta base de archivos en Configuración general."
        )
    return base


def carpeta_archivos_varios(conn: sqlite3.Connection, subcarpeta: str) -> Path:
    """"Archivos varios/{subcarpeta}" bajo la carpeta base. La crea si hace falta."""
    carpeta = _requerir_carpeta_base(conn) / "Archivos varios" / subcarpeta
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def carpeta_profesional(conn: sqlite3.Connection, codigo: str) -> Path:
    """"Profesionales/{codigo}" bajo la carpeta base. La crea si hace falta."""
    if not codigo:
        raise ValueError("El profesional no tiene código cargado: no se puede determinar su carpeta.")
    carpeta = _requerir_carpeta_base(conn) / "Profesionales" / codigo
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def carpeta_documentacion_profesional(conn: sqlite3.Connection, codigo: str) -> Path:
    """"Profesionales/{codigo}/Documentación" bajo la carpeta base. La crea si hace falta."""
    carpeta = carpeta_profesional(conn, codigo) / "Documentación"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def carpeta_imagenes(conn: sqlite3.Connection, alcance: str, id_valor: int) -> Path:
    """"Imagenes/{Alcance}_{Id}" bajo la carpeta base (alcance: "Edificio",
    "Unidad" o "Consultorio"). La crea si hace falta."""
    carpeta = _requerir_carpeta_base(conn) / "Imagenes" / f"{alcance}_{id_valor}"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def destino_sin_colision(carpeta: Path, nombre: str) -> Path:
    """Ruta de destino para copiar `nombre` a `carpeta` sin pisar un
    archivo existente: si ya hay uno con ese nombre, agrega " (2)", " (3)"
    etc. antes de la extensión."""
    destino = carpeta / nombre
    if not destino.exists():
        return destino
    base, ext = destino.stem, destino.suffix
    i = 2
    while (carpeta / f"{base} ({i}){ext}").exists():
        i += 1
    return carpeta / f"{base} ({i}){ext}"


def vaciar_carpeta(carpeta: Path) -> int:
    """Elimina todos los archivos sueltos de `carpeta` (no subcarpetas).
    Devuelve la cantidad borrada. No falla si la carpeta no existe."""
    if not carpeta.exists():
        return 0
    borrados = 0
    for archivo in carpeta.iterdir():
        if archivo.is_file():
            archivo.unlink()
            borrados += 1
    return borrados


def limpiar_liquidaciones_antiguas(carpeta: Path, hoy: date) -> int:
    """Borra, dentro de `carpeta` (Profesionales/{codigo}), los PDF de
    liquidación de períodos con más de un año de antigüedad respecto de
    `hoy`. El nombre de archivo empieza siempre con "AAAA-MM - Liquidación
    ..." (ver `app.pdf.liquidacion_pdf._nombre_archivo`), así que alcanza
    con comparar el prefijo de 7 caracteres."""
    if not carpeta.exists():
        return 0
    limite_anio = hoy.year - _RETENCION_LIQUIDACIONES_ANIOS
    periodo_limite = f"{limite_anio:04d}-{hoy.month:02d}"
    borrados = 0
    for archivo in carpeta.iterdir():
        if not archivo.is_file() or not archivo.name.endswith(".pdf"):
            continue
        periodo = archivo.name[:7]
        if len(periodo) == 7 and periodo[4] == "-" and periodo < periodo_limite:
            archivo.unlink()
            borrados += 1
    return borrados


def aplicar_cambio_codigo(conn: sqlite3.Connection, registro_anterior: sqlite3.Row, valores_nuevos: dict, hoy: date) -> None:
    """Hook llamado por la pantalla de Profesionales después de guardar una
    edición: si cambió la categoría y/o el código, registra el cambio en
    HistorialCodigo y, si cambió el código, renombra en disco la carpeta
    Profesionales/{código} conservando los archivos y aplica en el mismo
    proceso la limpieza de liquidaciones con más de un año."""
    categoria_anterior = registro_anterior["CategoriaProfesional"]
    codigo_anterior = registro_anterior["IdCodigo"]
    categoria_nueva = valores_nuevos.get("CategoriaProfesional", categoria_anterior)
    codigo_nuevo = valores_nuevos.get("IdCodigo", codigo_anterior)
    if categoria_nueva == categoria_anterior and codigo_nuevo == codigo_anterior:
        return

    conn.execute(
        "INSERT INTO HistorialCodigo "
        "(IdProfesional, CategoriaAnterior, CodigoAnterior, CategoriaNueva, CodigoNuevo, FechaCambio) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            registro_anterior["IdProfesional"], categoria_anterior, codigo_anterior,
            categoria_nueva, codigo_nuevo, hoy.isoformat(),
        ),
    )
    conn.commit()

    if codigo_nuevo != codigo_anterior:
        if carpeta_base(conn) is not None:
            renombrar_carpeta_profesional(conn, codigo_anterior, codigo_nuevo)
            if codigo_nuevo:
                limpiar_liquidaciones_antiguas(carpeta_profesional(conn, codigo_nuevo), hoy)


def renombrar_carpeta_profesional(conn: sqlite3.Connection, codigo_anterior: str | None, codigo_nuevo: str | None) -> None:
    """Al cambiar el código de un profesional, la carpeta con sus archivos
    se renombra (no se crea una nueva vacía): se conservan todas las
    liquidaciones ya generadas bajo el código anterior."""
    if not codigo_nuevo or codigo_anterior == codigo_nuevo:
        return
    base = carpeta_base(conn)
    if base is None:
        return
    carpeta_anterior = base / "Profesionales" / codigo_anterior if codigo_anterior else None
    carpeta_nueva = base / "Profesionales" / codigo_nuevo
    if carpeta_anterior and carpeta_anterior.exists():
        carpeta_nueva.parent.mkdir(parents=True, exist_ok=True)
        if carpeta_nueva.exists():
            for archivo in carpeta_anterior.iterdir():
                shutil.move(str(archivo), str(carpeta_nueva / archivo.name))
            carpeta_anterior.rmdir()
        else:
            shutil.move(str(carpeta_anterior), str(carpeta_nueva))
    else:
        carpeta_nueva.mkdir(parents=True, exist_ok=True)
