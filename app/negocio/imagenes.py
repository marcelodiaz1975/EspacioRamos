"""Gestión de imágenes (FA4, sección 3.26): fotos de edificios, unidades y
consultorios que aparecen en Propuesta, Disponibilidad, Liquidación y
Oferta de consultorios (`app.pdf.fotos_pdf`) — hoy solo se muestran las de
consultorio (`app.pdf.fotos_pdf.imagenes_de_consultorios`), las de
edificio/unidad/localidad/espacio quedan guardadas para cuando algún
documento las use.

Alcance (`ALCANCES`): además de Edificio/Unidad/Consultorio (usan el ID
interno de su tabla) hay dos niveles más generales, pedidos por la
clienta al revisar esta pantalla:
- "Espacio": imágenes generales del sistema, sin atarse a ningún
  edificio en particular (ej. el logo, si no termina necesitando su
  propia categoría aparte — a definir con la clienta). Es el alcance que
  resulta cuando no se pasa ninguno de los otros cuatro parámetros.
- "Localidad": agrupa por el texto libre de Edificio.DomicilioLocalidad
  — a diferencia de los demás, no tiene tabla propia con un ID estable,
  así que tanto el filtro (columna `Imagen.Localidad`) como la carpeta
  en disco usan directamente ese texto (ver `_nombre_carpeta_localidad`).

Los archivos se copian a Imagenes/{Alcance} o Imagenes/{Alcance}_{Id}
bajo la carpeta base en vez de referenciar la ubicación original en la
que el operador los tenía guardados: así el backup a Drive de "base de
datos e imágenes juntas" (sección 2 de la especificación) puede
respaldar todo desde un único lugar conocido."""
from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

from app.negocio.archivos_generados import carpeta_imagenes, destino_sin_colision
from app.repositorio.registro import obtener_repositorio

EXTENSIONES_VALIDAS = (".jpg", ".jpeg", ".png")
ALCANCES = ("Espacio", "Localidad", "Edificio", "Unidad", "Consultorio")

_CARACTERES_INVALIDOS_CARPETA = re.compile(r'[\\/:*?"<>|]')


def _nombre_carpeta_localidad(localidad: str) -> str:
    """Nombres de carpeta en Windows (donde se empaqueta con PyInstaller)
    no admiten \\/:*?"<>| — a diferencia de Edificio/Unidad/Consultorio,
    que usan su ID interno, Localidad es texto libre y puede traer
    cualquiera de esos caracteres."""
    return _CARACTERES_INVALIDOS_CARPETA.sub("_", localidad).strip() or "Sin nombre"


def _alcance(
    localidad: str | None, id_edificio: int | None, id_unidad: int | None, id_consultorio: int | None,
) -> tuple[str, str | int | None]:
    """A qué nivel pertenece la imagen a partir de cuál de los cuatro
    parámetros vino cargado. Si ninguno vino cargado, el alcance es
    "Espacio"."""
    seleccionados = [
        (alcance, valor) for alcance, valor in (
            ("Localidad", localidad), ("Edificio", id_edificio), ("Unidad", id_unidad), ("Consultorio", id_consultorio),
        )
        if valor is not None
    ]
    if len(seleccionados) > 1:
        raise ValueError(
            "Elegí un único alcance para la imagen: localidad, edificio, unidad o consultorio "
            "(o ninguno de los cuatro para Espacio)."
        )
    if not seleccionados:
        return ("Espacio", None)
    return seleccionados[0]


def _condicion_alcance(alcance: str, valor: str | int | None) -> tuple[str, list]:
    if alcance == "Espacio":
        return "Localidad IS NULL AND IdEdificio IS NULL AND IdUnidad IS NULL AND IdConsultorio IS NULL", []
    columna = "Localidad" if alcance == "Localidad" else f"Id{alcance}"
    return f"{columna} = ?", [valor]


def _tamano_maximo_mb(conn: sqlite3.Connection) -> float:
    fila = conn.execute("SELECT TamanoMaximoImagenMB FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    return (fila["TamanoMaximoImagenMB"] if fila else None) or 5


def agregar_imagen(
    conn: sqlite3.Connection, *, ruta_origen: str, descripcion: str | None = None, tipo: str | None = None,
    localidad: str | None = None, id_edificio: int | None = None, id_unidad: int | None = None,
    id_consultorio: int | None = None,
) -> int:
    """Copia `ruta_origen` a la carpeta del alcance elegido y registra la
    fila en Imagen, al final del orden existente para ese alcance.
    Devuelve el IdImagen creado."""
    alcance, valor = _alcance(localidad, id_edificio, id_unidad, id_consultorio)
    origen = Path(ruta_origen)
    if not origen.is_file():
        raise ValueError(f"No se encuentra el archivo: {ruta_origen}")
    if origen.suffix.lower() not in EXTENSIONES_VALIDAS:
        raise ValueError("Formato no soportado: usá JPG o PNG.")
    tamano_mb = origen.stat().st_size / (1024 * 1024)
    maximo = _tamano_maximo_mb(conn)
    if tamano_mb > maximo:
        raise ValueError(f"La imagen pesa {tamano_mb:.1f}MB, el máximo configurado es {maximo:g}MB.")

    nombre_carpeta = _nombre_carpeta_localidad(valor) if alcance == "Localidad" else valor
    destino = destino_sin_colision(carpeta_imagenes(conn, alcance, nombre_carpeta), origen.name)
    shutil.copy2(origen, destino)

    condicion, parametros = _condicion_alcance(alcance, valor)
    orden_actual = conn.execute(
        f"SELECT COALESCE(MAX(NumeroOrden), 0) FROM Imagen WHERE {condicion}", parametros
    ).fetchone()[0]
    repo = obtener_repositorio(conn, "Imagen")
    return repo.crear(
        Tipo=tipo, Localidad=localidad, IdEdificio=id_edificio, IdUnidad=id_unidad, IdConsultorio=id_consultorio,
        NumeroOrden=orden_actual + 1, Descripcion=descripcion, RutaArchivo=str(destino), Activo=1,
    )


def eliminar_imagen(conn: sqlite3.Connection, id_imagen: int) -> None:
    """Borra la fila de Imagen y, si existe, el archivo copiado en disco."""
    repo = obtener_repositorio(conn, "Imagen")
    imagen = repo.obtener(id_imagen)
    if imagen is None:
        return
    repo.eliminar(id_imagen)
    if imagen["RutaArchivo"]:
        ruta = Path(imagen["RutaArchivo"])
        if ruta.is_file():
            ruta.unlink()


def imagenes_del_alcance(
    conn: sqlite3.Connection, localidad: str | None = None, id_edificio: int | None = None,
    id_unidad: int | None = None, id_consultorio: int | None = None,
) -> list[sqlite3.Row]:
    """Todas las imágenes (activas e inactivas) del alcance elegido, en
    orden. Sin ningún parámetro, trae las de alcance "Espacio". Para la
    pantalla de gestión — a diferencia de
    `app.pdf.fotos_pdf.imagenes_de_consultorios`, que solo trae las
    activas para los documentos."""
    alcance, valor = _alcance(localidad, id_edificio, id_unidad, id_consultorio)
    condicion, parametros = _condicion_alcance(alcance, valor)
    filas = conn.execute(f"SELECT * FROM Imagen WHERE {condicion}", parametros).fetchall()
    return sorted(filas, key=lambda i: i["NumeroOrden"])


def reordenar(conn: sqlite3.Connection, id_imagen: int, delta: int) -> None:
    """Mueve una imagen un lugar dentro del orden de su mismo alcance
    (delta -1 sube, +1 baja) intercambiando NumeroOrden con la vecina."""
    repo = obtener_repositorio(conn, "Imagen")
    imagen = repo.obtener(id_imagen)
    if imagen is None:
        return
    vecinas = imagenes_del_alcance(
        conn, localidad=imagen["Localidad"], id_edificio=imagen["IdEdificio"],
        id_unidad=imagen["IdUnidad"], id_consultorio=imagen["IdConsultorio"],
    )
    indice = next(i for i, v in enumerate(vecinas) if v["IdImagen"] == id_imagen)
    nuevo_indice = indice + delta
    if not (0 <= nuevo_indice < len(vecinas)):
        return
    otra = vecinas[nuevo_indice]
    repo.actualizar(id_imagen, NumeroOrden=otra["NumeroOrden"])
    repo.actualizar(otra["IdImagen"], NumeroOrden=imagen["NumeroOrden"])


def alternar_activo(conn: sqlite3.Connection, id_imagen: int) -> None:
    repo = obtener_repositorio(conn, "Imagen")
    imagen = repo.obtener(id_imagen)
    if imagen is None:
        return
    repo.actualizar(id_imagen, Activo=0 if imagen["Activo"] else 1)
