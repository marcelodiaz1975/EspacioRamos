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
    {base}/Imagenes/Espacio/
    {base}/Imagenes/{Alcance}_{Id}/  (Localidad, Edificio, Unidad)
    {base}/Imagenes/Consultorio - {Edificio} - {Unidad} - {Número}/
    {base}/Liquidaciones simuladas/

Los tres primeros son documentos únicos del espacio en general: cada
regeneración sobrescribe el anterior, no se acumula historial de archivos.
Profesionales/{IdCodigo} en cambio acumula las liquidaciones mensuales (y,
en su subcarpeta Documentación, cualquier archivo del profesional) de ese
profesional en particular — todo bajo el mismo código, así que se muda
entero cuando el código cambia (ver `renombrar_carpeta_profesional`).
Imagenes/{Alcance}_{Id} (Localidad/Edificio/Unidad) usa el ID interno (no
un nombre editable) para no depender de que el operador no le cambie el
nombre al edificio/unidad más adelante — Consultorio es la EXCEPCIÓN
(pedido explícito de la clienta, ronda "Ingreso de profesionales"): usa
el nombre descriptivo armado en `nombre_carpeta_consultorio`, migrando
sola la carpeta vieja basada en ID la primera vez que se accede a ese
consultorio (`carpeta_imagenes`) y renombrándose de nuevo si cambia el
Número del consultorio (`renombrar_carpeta_imagenes_consultorio`, hook
de `pantalla_consultorios`) — pero no si cambia el nombre del Edificio o
la Unidad desde SUS propias pantallas (ver el docstring de esa función).
Liquidaciones simuladas (pedido de la clienta, ver `app.negocio.
liquidacion_simulada`) es una carpeta ÚNICA compartida por todos los
profesionales (a diferencia de Profesionales/{IdCodigo}) porque su
retención es corta (3 meses, ver `limpiar_liquidaciones_simuladas_
antiguas`) — son ejemplos descartables, no un historial por profesional
que haya que conservar ni mudar si cambia el código.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import date
from pathlib import Path

from app.negocio.dias import sumar_meses

# Windows (donde se empaqueta con PyInstaller) no admite \/:*?"<>| en un
# nombre de archivo/carpeta — mismo criterio que `app.negocio.imagenes.
# _nombre_archivo_valido`, duplicado acá (capa de negocio distinta, sin
# importar entre sí).
_CARACTERES_INVALIDOS_CARPETA = re.compile(r'[\\/:*?"<>|]')

SUBCARPETA_PROPUESTA = "Propuesta"
SUBCARPETA_DISPONIBILIDAD = "Disponibilidad"
SUBCARPETA_OFERTA = "Oferta"
SUBCARPETA_PLACAS = "Placas"
# Distinta de SUBCARPETA_PLACAS (el tablero completo de referencia, que
# regenera solo `avance_mes` con `generar_pdf_placas`) — esta es para el
# PDF puntual de "Agregar a impresión" / "Generar PDF" de la solapa
# "Impresión de placas en papel" (pedido explícito de la clienta sobre
# ESE botón nomás, no sobre el tablero de referencia).
SUBCARPETA_PLACAS_PARA_IMPRIMIR = "Placas para imprimir"
SUBCARPETA_MANUAL = "Manual"
SUBCARPETA_LIQUIDACIONES_SIMULADAS = "Liquidaciones simuladas"

_RETENCION_LIQUIDACIONES_ANIOS = 1
_RETENCION_LIQUIDACIONES_SIMULADAS_MESES = 3


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


def nombre_carpeta_profesional(
    codigo: str | None, tratamiento: str | None, nombre_pila: str | None, apellido: str | None,
) -> str:
    """"{código} - {tratamiento} {nombre} {apellido}" — mismo formato
    canónico que ya muestran los selectores de profesional de todo el
    sistema (ej. "R1 - Lic. Virginia Lo Veci"), saneado para nombre de
    carpeta. Pedido explícito de la clienta: antes la carpeta se nombraba
    solo con el código ("R1"), sin forma de identificar de quién es sin
    abrir el sistema."""
    partes = [p for p in (tratamiento, nombre_pila, apellido) if p]
    nombre = " ".join(partes) if partes else (apellido or "")
    if codigo and nombre:
        texto = f"{codigo} - {nombre}"
    else:
        texto = codigo or nombre or "Profesional"
    return _CARACTERES_INVALIDOS_CARPETA.sub("_", texto).strip()


def carpeta_profesional(conn: sqlite3.Connection, codigo: str) -> Path:
    """"Profesionales/{código} - {tratamiento nombre apellido}" bajo la
    carpeta base. La crea si hace falta. El nombre completo es puramente
    descriptivo (para que el operador identifique la carpeta a simple
    vista en el explorador de archivos) — toda la lógica de negocio
    sigue resolviendo siempre por código, nunca por este nombre."""
    if not codigo:
        raise ValueError("El profesional no tiene código cargado: no se puede determinar su carpeta.")
    fila = conn.execute(
        "SELECT Tratamiento, NombrePila, Apellido FROM Profesional WHERE IdCodigo = ?", (codigo,)
    ).fetchone()
    nombre_carpeta = nombre_carpeta_profesional(
        codigo, fila["Tratamiento"] if fila else None, fila["NombrePila"] if fila else None,
        fila["Apellido"] if fila else None,
    )
    carpeta = _requerir_carpeta_base(conn) / "Profesionales" / nombre_carpeta
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def carpeta_documentacion_profesional(conn: sqlite3.Connection, codigo: str) -> Path:
    """"Profesionales/{codigo}/Documentación" bajo la carpeta base. La crea si hace falta."""
    carpeta = carpeta_profesional(conn, codigo) / "Documentación"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def nombre_carpeta_consultorio(edificio: str | None, unidad: str | None, numero_consultorio) -> str:
    """"Consultorio - {Edificio} - {Unidad} - {Consultorio}" — pedido
    explícito de la clienta sobre esta carpeta puntual (no las de
    Localidad/Edificio/Unidad, que siguen por ID, ver `carpeta_
    imagenes`): antes se nombraba solo "Consultorio_{id}", sin forma de
    identificar de cuál se trata sin abrir el sistema — mismo criterio
    ya usado en `nombre_carpeta_profesional`."""
    texto = f"Consultorio - {edificio or '?'} - {unidad or '?'} - {numero_consultorio}"
    return _CARACTERES_INVALIDOS_CARPETA.sub("_", texto).strip()


def _datos_consultorio_para_carpeta(conn: sqlite3.Connection, id_consultorio: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS Edificio "
        "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio WHERE c.IdConsultorio = ?",
        (id_consultorio,),
    ).fetchone()


def _mover_contenido_carpeta(origen: Path, destino: Path) -> None:
    """Mueve TODO el contenido de `origen` a `destino` (creándola si hace
    falta) y borra `origen` — a diferencia de un simple `rename`, sirve
    tanto si `destino` todavía no existe como si ya existe (ej. ya se
    había migrado antes a mano, o dos consultorios distintos terminan
    apuntando al mismo nombre por datos repetidos)."""
    if not origen.exists():
        return
    if not destino.exists():
        origen.rename(destino)
        return
    for archivo in origen.iterdir():
        shutil.move(str(archivo), str(destino / archivo.name))
    origen.rmdir()


def renombrar_carpeta_imagenes_consultorio(conn: sqlite3.Connection, id_consultorio: int, nombre_anterior: str) -> None:
    """Al cambiar el Número de un consultorio (`pantalla_consultorios`,
    `al_actualizar`), la carpeta de sus imágenes se renombra para seguir
    el nombre descriptivo actual — se conservan los archivos ya
    cargados, no se crea una carpeta nueva vacía. `nombre_anterior` es
    el nombre de carpeta COMPLETO (`nombre_carpeta_consultorio`) con los
    datos de ANTES de guardar.

    No cubre un cambio de nombre de Edificio/Unidad hecho desde SUS
    propias pantallas (`pantalla_edificios`/`pantalla_unidades`): esas
    pantallas no saben qué consultorios dependen de ellas, así que la
    carpeta de un consultorio cuyo edificio o unidad se renombra DESPUÉS
    queda con el nombre viejo hasta que ese consultorio se vuelva a
    guardar (editarlo sin cambiar nada alcanza para que esta misma
    función lo reconcilie) — limitación conocida, no resuelta en esta
    ronda."""
    base = carpeta_base(conn)
    if base is None:
        return
    fila = _datos_consultorio_para_carpeta(conn, id_consultorio)
    if fila is None:
        return
    nombre_nuevo = nombre_carpeta_consultorio(fila["Edificio"], fila["Departamento"], fila["NumeroConsultorio"])
    if nombre_nuevo == nombre_anterior:
        return
    _mover_contenido_carpeta(base / "Imagenes" / nombre_anterior, base / "Imagenes" / nombre_nuevo)


def carpeta_imagenes(conn: sqlite3.Connection, alcance: str, id_valor: int | None = None) -> Path:
    """"Imagenes/{Alcance}" (alcance "Espacio", sin id: imágenes generales
    del sistema) o "Imagenes/{Alcance}_{Id}" (alcance "Localidad",
    "Edificio" o "Unidad", con el ID interno de su tabla) bajo la
    carpeta base. La crea si hace falta.

    Para alcance "Consultorio" usa en cambio el nombre descriptivo de
    `nombre_carpeta_consultorio` (pedido explícito de la clienta) — y,
    si todavía existe la carpeta vieja "Consultorio_{id}" (de antes de
    este cambio) sin la nueva, la migra sola la primera vez que se
    accede a las imágenes de ese consultorio, sin que haga falta
    renombrar nada a mano."""
    if alcance == "Consultorio" and id_valor is not None:
        base = _requerir_carpeta_base(conn)
        carpeta_vieja = base / "Imagenes" / f"Consultorio_{id_valor}"
        fila = _datos_consultorio_para_carpeta(conn, id_valor)
        nombre = (
            nombre_carpeta_consultorio(fila["Edificio"], fila["Departamento"], fila["NumeroConsultorio"])
            if fila is not None else f"Consultorio_{id_valor}"
        )
        carpeta = base / "Imagenes" / nombre
        if carpeta_vieja != carpeta:
            _mover_contenido_carpeta(carpeta_vieja, carpeta)
    else:
        nombre = alcance if id_valor is None else f"{alcance}_{id_valor}"
        carpeta = _requerir_carpeta_base(conn) / "Imagenes" / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def carpeta_liquidaciones_simuladas(conn: sqlite3.Connection) -> Path:
    """"Liquidaciones simuladas" bajo la carpeta base — carpeta ÚNICA
    compartida por todos los profesionales (a diferencia de
    `carpeta_profesional`, una por código): la retención acá es corta
    (`limpiar_liquidaciones_simuladas_antiguas`), no hace falta separar
    por profesional. La crea si hace falta."""
    carpeta = _requerir_carpeta_base(conn) / SUBCARPETA_LIQUIDACIONES_SIMULADAS
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


def limpiar_liquidaciones_simuladas_antiguas(carpeta: Path, hoy: date) -> int:
    """Pedido explícito de la clienta: "que se vayan conservando las
    liquidaciones [simuladas] de los últimos 3 meses y que luego se
    vayan eliminando a través de un proceso con el avance de mes" — mismo
    mecanismo que `limpiar_liquidaciones_antiguas` (compara el prefijo
    "AAAA-MM" del nombre de archivo, ver `app.pdf.liquidacion_simulada_
    pdf.nombre_archivo_liquidacion_simulada`), pero con una retención en
    MESES en vez de años, sobre la carpeta única `carpeta_liquidaciones_
    simuladas` (no una por profesional)."""
    if not carpeta.exists():
        return 0
    periodo_limite = sumar_meses(f"{hoy.year:04d}-{hoy.month:02d}", -_RETENCION_LIQUIDACIONES_SIMULADAS_MESES)
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
    HistorialCodigo. Si cambió el código, el tratamiento, el nombre o el
    apellido (cualquiera de los cuatro que componen el nombre de la
    carpeta, ver `nombre_carpeta_profesional`), renombra en disco la
    carpeta Profesionales/{...} conservando los archivos y aplica en el
    mismo proceso la limpieza de liquidaciones con más de un año.

    `valores_nuevos` llega con el valor YA actualizado en la base (este
    hook corre después de `repositorio.actualizar`, que ya hizo commit)
    — por eso el nombre de carpeta ANTERIOR se calcula a partir de
    `registro_anterior` (la fila de antes de guardar) en vez de volver a
    consultar la base por el código viejo, que ya no existe ahí."""
    categoria_anterior = registro_anterior["CategoriaProfesional"]
    codigo_anterior = registro_anterior["IdCodigo"]
    categoria_nueva = valores_nuevos.get("CategoriaProfesional", categoria_anterior)
    codigo_nuevo = valores_nuevos.get("IdCodigo", codigo_anterior)

    if categoria_nueva != categoria_anterior or codigo_nuevo != codigo_anterior:
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

    nombre_carpeta_anterior = nombre_carpeta_profesional(
        codigo_anterior, registro_anterior["Tratamiento"], registro_anterior["NombrePila"], registro_anterior["Apellido"],
    )
    nombre_carpeta_nuevo = nombre_carpeta_profesional(
        codigo_nuevo,
        valores_nuevos.get("Tratamiento", registro_anterior["Tratamiento"]),
        valores_nuevos.get("NombrePila", registro_anterior["NombrePila"]),
        valores_nuevos.get("Apellido", registro_anterior["Apellido"]),
    )
    if nombre_carpeta_nuevo != nombre_carpeta_anterior and carpeta_base(conn) is not None:
        renombrar_carpeta_profesional(conn, nombre_carpeta_anterior, nombre_carpeta_nuevo)
        if codigo_nuevo:
            limpiar_liquidaciones_antiguas(carpeta_profesional(conn, codigo_nuevo), hoy)


def renombrar_carpeta_profesional(conn: sqlite3.Connection, nombre_carpeta_anterior: str | None, nombre_carpeta_nuevo: str | None) -> None:
    """Al cambiar el código, tratamiento, nombre o apellido de un
    profesional, la carpeta con sus archivos se renombra (no se crea una
    nueva vacía): se conservan todas las liquidaciones ya generadas bajo
    el nombre anterior. Los parámetros son el nombre de carpeta COMPLETO
    (`nombre_carpeta_profesional`), no solo el código."""
    if not nombre_carpeta_nuevo or nombre_carpeta_anterior == nombre_carpeta_nuevo:
        return
    base = carpeta_base(conn)
    if base is None:
        return
    carpeta_anterior = base / "Profesionales" / nombre_carpeta_anterior if nombre_carpeta_anterior else None
    carpeta_nueva = base / "Profesionales" / nombre_carpeta_nuevo
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
