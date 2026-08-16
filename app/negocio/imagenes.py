"""Gestión de imágenes (FA4, sección 3.26): fotos de edificios, unidades y
consultorios que aparecen en Propuesta, Disponibilidad, Liquidación y
Oferta de consultorios (`app.pdf.fotos_pdf`) — hoy solo se muestran las de
consultorio (`app.pdf.fotos_pdf.imagenes_de_consultorios`), las de
edificio/unidad quedan guardadas para cuando algún documento las use.

Los archivos se copian a Imagenes/{Alcance}_{Id} bajo la carpeta base en
vez de referenciar la ubicación original en la que el operador los tenía
guardados: así el backup a Drive de "base de datos e imágenes juntas"
(sección 2 de la especificación) puede respaldar todo desde un único
lugar conocido."""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app.negocio.archivos_generados import carpeta_imagenes, destino_sin_colision
from app.repositorio.registro import obtener_repositorio

EXTENSIONES_VALIDAS = (".jpg", ".jpeg", ".png")
ALCANCES = ("Edificio", "Unidad", "Consultorio")


def _alcance(id_edificio: int | None, id_unidad: int | None, id_consultorio: int | None) -> tuple[str, int]:
    seleccionados = [
        (alcance, valor) for alcance, valor in zip(ALCANCES, (id_edificio, id_unidad, id_consultorio))
        if valor is not None
    ]
    if len(seleccionados) != 1:
        raise ValueError("Elegí un único alcance para la imagen: edificio, unidad o consultorio.")
    return seleccionados[0]


def _tamano_maximo_mb(conn: sqlite3.Connection) -> float:
    fila = conn.execute("SELECT TamanoMaximoImagenMB FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    return (fila["TamanoMaximoImagenMB"] if fila else None) or 5


def agregar_imagen(
    conn: sqlite3.Connection, *, ruta_origen: str, descripcion: str | None = None, tipo: str | None = None,
    id_edificio: int | None = None, id_unidad: int | None = None, id_consultorio: int | None = None,
) -> int:
    """Copia `ruta_origen` a Imagenes/{Alcance}_{Id} y registra la fila en
    Imagen, al final del orden existente para ese alcance. Devuelve el
    IdImagen creado."""
    alcance, id_valor = _alcance(id_edificio, id_unidad, id_consultorio)
    origen = Path(ruta_origen)
    if not origen.is_file():
        raise ValueError(f"No se encuentra el archivo: {ruta_origen}")
    if origen.suffix.lower() not in EXTENSIONES_VALIDAS:
        raise ValueError("Formato no soportado: usá JPG o PNG.")
    tamano_mb = origen.stat().st_size / (1024 * 1024)
    maximo = _tamano_maximo_mb(conn)
    if tamano_mb > maximo:
        raise ValueError(f"La imagen pesa {tamano_mb:.1f}MB, el máximo configurado es {maximo:g}MB.")

    destino = destino_sin_colision(carpeta_imagenes(conn, alcance, id_valor), origen.name)
    shutil.copy2(origen, destino)

    repo = obtener_repositorio(conn, "Imagen")
    orden_actual = conn.execute(
        f"SELECT COALESCE(MAX(NumeroOrden), 0) FROM Imagen WHERE Id{alcance} = ?", (id_valor,)
    ).fetchone()[0]
    return repo.crear(
        Tipo=tipo, IdEdificio=id_edificio, IdUnidad=id_unidad, IdConsultorio=id_consultorio,
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


def imagenes_del_alcance(conn: sqlite3.Connection, id_edificio: int | None, id_unidad: int | None, id_consultorio: int | None) -> list[sqlite3.Row]:
    """Todas las imágenes (activas e inactivas) del alcance elegido, en
    orden. Para la pantalla de gestión — a diferencia de
    `app.pdf.fotos_pdf.imagenes_de_consultorios`, que solo trae las
    activas para los documentos."""
    alcance, id_valor = _alcance(id_edificio, id_unidad, id_consultorio)
    return sorted(
        obtener_repositorio(conn, "Imagen").listar(**{f"Id{alcance}": id_valor}),
        key=lambda i: i["NumeroOrden"],
    )


def reordenar(conn: sqlite3.Connection, id_imagen: int, delta: int) -> None:
    """Mueve una imagen un lugar dentro del orden de su mismo alcance
    (delta -1 sube, +1 baja) intercambiando NumeroOrden con la vecina."""
    repo = obtener_repositorio(conn, "Imagen")
    imagen = repo.obtener(id_imagen)
    if imagen is None:
        return
    vecinas = imagenes_del_alcance(conn, imagen["IdEdificio"], imagen["IdUnidad"], imagen["IdConsultorio"])
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
