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
    {base}/Imagenes/Localidad_{Localidad}/
    {base}/Imagenes/Edificio_{Localidad}_{Edificio}/
    {base}/Imagenes/Unidad_{Localidad}_{Edificio}_{Departamento}/
    {base}/Imagenes/Consultorio_{Localidad}_{Edificio}_{Departamento}_C{Número}/
    {base}/Liquidaciones simuladas/

Los tres primeros son documentos únicos del espacio en general: cada
regeneración sobrescribe el anterior, no se acumula historial de archivos.
Profesionales/{IdCodigo} en cambio acumula las liquidaciones mensuales (y,
en su subcarpeta Documentación, cualquier archivo del profesional) de ese
profesional en particular — todo bajo el mismo código, así que se muda
entero cuando el código cambia (ver `renombrar_carpeta_profesional`).
Imagenes/{Alcance}_... (Localidad, Edificio, Unidad, Consultorio) usa el
nombre descriptivo de cada nivel, encadenando los de arriba (pedido
explícito de la clienta: "la idea es que se replique el formato de ruta
para otros elementos" — antes solo Consultorio era descriptivo,
Localidad/Edificio/Unidad usaban el ID interno; ver `nombre_carpeta_
localidad`/`nombre_carpeta_edificio`/`nombre_carpeta_unidad`/`nombre_
carpeta_consultorio`). Cada nivel migra solo su carpeta vieja (la
basada en ID, de antes de este cambio — y, Consultorio además, la
intermedia "Consultorio - {Edificio} - {Unidad} - {Número}" de la
ronda anterior) la primera vez que se accede a sus imágenes
(`carpeta_imagenes`), y se renombra de nuevo si cambia alguno de los
campos que componen su propio nombre, desde SU PROPIA pantalla
(`renombrar_carpeta_imagenes_localidad`/`..._edificio`/`..._unidad`/
`..._consultorio`, hooks de `pantalla_localidades`/`pantalla_edificios`/
`pantalla_unidades`/`pantalla_consultorios`) — pero NO cuando el cambio
viene de un nivel SUPERIOR del que depende (ej. la carpeta de un
Edificio no se renombra sola si la Localidad a la que pertenece cambia
de nombre desde la pantalla de Localidades): cada nivel queda con el
nombre viejo hasta que se lo vuelva a guardar (editarlo sin cambiar
nada alcanza para que su propio hook lo reconcilie) — limitación
conocida, no resuelta en esta ronda, mismo criterio documentado desde
siempre para Consultorio.
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


def nombre_carpeta_localidad(localidad: str | None) -> str:
    """"Localidad_{Localidad}" — pedido explícito de la clienta: "la idea
    es que se replique el formato de ruta [descriptivo de Consultorio]
    para otros elementos" — antes esta carpeta se nombraba solo con el
    ID interno (`Localidad_{id}`), sin forma de identificar de cuál se
    trata sin abrir el sistema."""
    texto = f"Localidad_{localidad or '?'}"
    return _CARACTERES_INVALIDOS_CARPETA.sub("_", texto).strip()


def nombre_carpeta_edificio(localidad: str | None, edificio: str | None) -> str:
    """"Edificio_{Localidad}_{Edificio}" — mismo pedido que `nombre_
    carpeta_localidad`, encadenando el nombre de la Localidad a la que
    pertenece (puede no tener: "Sin localidad" es una opción válida del
    catálogo de Edificios, de ahí el `or '?'`)."""
    texto = f"Edificio_{localidad or '?'}_{edificio or '?'}"
    return _CARACTERES_INVALIDOS_CARPETA.sub("_", texto).strip()


def nombre_carpeta_unidad(localidad: str | None, edificio: str | None, departamento: str | None) -> str:
    """"Unidad_{Localidad}_{Edificio}_{Departamento}" — mismo pedido que
    `nombre_carpeta_localidad`, encadenando Localidad y Edificio."""
    texto = f"Unidad_{localidad or '?'}_{edificio or '?'}_{departamento or '?'}"
    return _CARACTERES_INVALIDOS_CARPETA.sub("_", texto).strip()


def nombre_carpeta_consultorio(
    localidad: str | None, edificio: str | None, unidad: str | None, numero_consultorio,
) -> str:
    """"Consultorio_{Localidad}_{Edificio}_{Unidad}_C{Consultorio}" —
    pedido explícito de la clienta, ronda "Ingreso de profesionales":
    antes se nombraba solo "Consultorio_{id}", sin forma de identificar
    de cuál se trata sin abrir el sistema. Formato cambiado de nuevo
    ("Consultorio - {Edificio} - {Unidad} - {Número}", con guiones y sin
    Localidad) a este, con guion bajo y Localidad incluida, pedido
    explícito de la clienta en la ronda siguiente, para que las cuatro
    carpetas descriptivas (Localidad/Edificio/Unidad/Consultorio) sigan
    el mismo patrón de armado."""
    texto = f"Consultorio_{localidad or '?'}_{edificio or '?'}_{unidad or '?'}_C{numero_consultorio}"
    return _CARACTERES_INVALIDOS_CARPETA.sub("_", texto).strip()


def _datos_localidad_para_carpeta(conn: sqlite3.Connection, id_localidad: int) -> sqlite3.Row | None:
    return conn.execute("SELECT Localidad FROM Localidad WHERE IdLocalidad = ?", (id_localidad,)).fetchone()


def _datos_edificio_para_carpeta(conn: sqlite3.Connection, id_edificio: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT e.Nombre AS Edificio, l.Localidad FROM Edificio e "
        "LEFT JOIN Localidad l ON l.IdLocalidad = e.IdLocalidad WHERE e.IdEdificio = ?",
        (id_edificio,),
    ).fetchone()


def _datos_unidad_para_carpeta(conn: sqlite3.Connection, id_unidad: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT u.Departamento, e.Nombre AS Edificio, l.Localidad FROM Unidad u "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
        "LEFT JOIN Localidad l ON l.IdLocalidad = e.IdLocalidad WHERE u.IdUnidad = ?",
        (id_unidad,),
    ).fetchone()


def _datos_consultorio_para_carpeta(conn: sqlite3.Connection, id_consultorio: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT c.NumeroConsultorio, u.Departamento, e.Nombre AS Edificio, l.Localidad "
        "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
        "LEFT JOIN Localidad l ON l.IdLocalidad = e.IdLocalidad WHERE c.IdConsultorio = ?",
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


def _renombrar_carpeta_imagenes_si_cambio(base: Path, nombre_anterior: str, nombre_nuevo: str) -> None:
    """Helper compartido por los cuatro `renombrar_carpeta_imagenes_*`
    de abajo: si el nombre no cambió, no toca nada; si cambió, mueve el
    contenido de la carpeta vieja a la nueva (`_mover_contenido_
    carpeta`, conserva los archivos ya cargados, no crea una carpeta
    nueva vacía)."""
    if nombre_nuevo == nombre_anterior:
        return
    carpeta_base_imagenes = base / "Archivos varios" / "Imagenes"
    _mover_contenido_carpeta(carpeta_base_imagenes / nombre_anterior, carpeta_base_imagenes / nombre_nuevo)


def renombrar_carpeta_imagenes_localidad(conn: sqlite3.Connection, id_localidad: int, nombre_anterior: str) -> None:
    """Al cambiar el nombre de una Localidad (`pantalla_localidades`,
    `al_actualizar`), la carpeta de sus imágenes se renombra para
    seguir el nombre descriptivo actual. `nombre_anterior` es el nombre
    de carpeta COMPLETO (`nombre_carpeta_localidad`) con los datos de
    ANTES de guardar.

    No cubre un cambio en cascada de los Edificios/Unidades/
    Consultorios que dependen de esta Localidad (sus carpetas incluyen
    el nombre de la Localidad, pero esas pantallas no saben que la
    Localidad de la que dependen cambió) — limitación conocida, mismo
    criterio documentado desde siempre para Consultorio, no resuelta en
    esta ronda."""
    base = carpeta_base(conn)
    if base is None:
        return
    fila = _datos_localidad_para_carpeta(conn, id_localidad)
    if fila is None:
        return
    _renombrar_carpeta_imagenes_si_cambio(base, nombre_anterior, nombre_carpeta_localidad(fila["Localidad"]))


def renombrar_carpeta_imagenes_edificio(conn: sqlite3.Connection, id_edificio: int, nombre_anterior: str) -> None:
    """Al cambiar el nombre o la Localidad de un Edificio
    (`pantalla_edificios`, `al_actualizar`), la carpeta de sus imágenes
    se renombra para seguir el nombre descriptivo actual. `nombre_
    anterior` es el nombre de carpeta COMPLETO (`nombre_carpeta_
    edificio`) con los datos de ANTES de guardar — mismas limitaciones
    que `renombrar_carpeta_imagenes_localidad` (no cascada hacia
    Unidad/Consultorio, ni hacia atrás si cambia el nombre de la
    Localidad desde SU pantalla)."""
    base = carpeta_base(conn)
    if base is None:
        return
    fila = _datos_edificio_para_carpeta(conn, id_edificio)
    if fila is None:
        return
    nombre_nuevo = nombre_carpeta_edificio(fila["Localidad"], fila["Edificio"])
    _renombrar_carpeta_imagenes_si_cambio(base, nombre_anterior, nombre_nuevo)


def renombrar_carpeta_imagenes_unidad(conn: sqlite3.Connection, id_unidad: int, nombre_anterior: str) -> None:
    """Al cambiar el Departamento o el Edificio de una Unidad
    (`pantalla_unidades`, `al_actualizar`), la carpeta de sus imágenes
    se renombra para seguir el nombre descriptivo actual. `nombre_
    anterior` es el nombre de carpeta COMPLETO (`nombre_carpeta_
    unidad`) con los datos de ANTES de guardar — mismas limitaciones
    que `renombrar_carpeta_imagenes_localidad` (no cascada hacia
    Consultorio, ni hacia atrás si cambia el nombre del Edificio o la
    Localidad desde SU pantalla)."""
    base = carpeta_base(conn)
    if base is None:
        return
    fila = _datos_unidad_para_carpeta(conn, id_unidad)
    if fila is None:
        return
    nombre_nuevo = nombre_carpeta_unidad(fila["Localidad"], fila["Edificio"], fila["Departamento"])
    _renombrar_carpeta_imagenes_si_cambio(base, nombre_anterior, nombre_nuevo)


def renombrar_carpeta_imagenes_consultorio(conn: sqlite3.Connection, id_consultorio: int, nombre_anterior: str) -> None:
    """Al cambiar la Unidad o el Número de un consultorio
    (`pantalla_consultorios`, `al_actualizar`), la carpeta de sus
    imágenes se renombra para seguir el nombre descriptivo actual.
    `nombre_anterior` es el nombre de carpeta COMPLETO (`nombre_carpeta_
    consultorio`) con los datos de ANTES de guardar — mismas
    limitaciones que `renombrar_carpeta_imagenes_localidad` (no cascada
    hacia atrás si cambia el nombre de la Unidad/Edificio/Localidad
    desde SU propia pantalla — editar el consultorio sin cambiar nada
    alcanza para que esta misma función lo reconcilie)."""
    base = carpeta_base(conn)
    if base is None:
        return
    fila = _datos_consultorio_para_carpeta(conn, id_consultorio)
    if fila is None:
        return
    nombre_nuevo = nombre_carpeta_consultorio(
        fila["Localidad"], fila["Edificio"], fila["Departamento"], fila["NumeroConsultorio"],
    )
    _renombrar_carpeta_imagenes_si_cambio(base, nombre_anterior, nombre_nuevo)


# (alcance, columna_de_id, dato_descriptivo). `dato_descriptivo` recibe la
# fila de `_datos_*_para_carpeta` y devuelve el nombre de carpeta —
# usado por `carpeta_imagenes` para no repetir cuatro veces el mismo
# "buscar datos, armar nombre, migrar lo viejo si hace falta".
_DATOS_PARA_CARPETA: dict = {
    "Localidad": (_datos_localidad_para_carpeta, lambda f: nombre_carpeta_localidad(f["Localidad"])),
    "Edificio": (_datos_edificio_para_carpeta, lambda f: nombre_carpeta_edificio(f["Localidad"], f["Edificio"])),
    "Unidad": (
        _datos_unidad_para_carpeta,
        lambda f: nombre_carpeta_unidad(f["Localidad"], f["Edificio"], f["Departamento"]),
    ),
    "Consultorio": (
        _datos_consultorio_para_carpeta,
        lambda f: nombre_carpeta_consultorio(f["Localidad"], f["Edificio"], f["Departamento"], f["NumeroConsultorio"]),
    ),
}
# Antes de este cambio, Consultorio ya tenía un nombre descriptivo
# propio, pero con guiones y sin Localidad ("Consultorio - {Edificio} -
# {Unidad} - {Número}") — una carpeta armada con esa fórmula vieja
# también se migra sola al nombre nuevo la primera vez que se accede a
# ese consultorio, además de la migración desde el esquema por ID que
# ya tenían los cuatro alcances (ver `carpeta_imagenes`).
_FORMATO_CONSULTORIO_ANTERIOR = (
    lambda f: _CARACTERES_INVALIDOS_CARPETA.sub(
        "_", f"Consultorio - {f['Edificio'] or '?'} - {f['Departamento'] or '?'} - {f['NumeroConsultorio']}"
    ).strip()
)


def carpeta_imagenes(conn: sqlite3.Connection, alcance: str, id_valor: int | None = None) -> Path:
    """"Archivos varios/Imagenes/{Alcance}" (alcance "Espacio", sin id:
    imágenes generales del sistema) bajo la carpeta base. La crea si
    hace falta.

    Pedido explícito de la clienta: "Imagenes" pasa a vivir DENTRO de
    "Archivos varios" (antes directo bajo la carpeta base, al mismo
    nivel que "Profesionales") — el resto de las carpetas generadas por
    el sistema ya vivía ahí (Propuesta/Disponibilidad/Oferta/Placas/
    Manual, ver `carpeta_archivos_varios`); "Profesionales" es la única
    que se deja a propósito FUERA, al mismo nivel que "Archivos varios".
    Si todavía existe la carpeta vieja "Imagenes" al nivel de arriba (de
    antes de este cambio), se migra sola la primera vez que se accede a
    CUALQUIER imagen (ver `_migrar_carpeta_imagenes_al_nivel_viejo`) —
    mismo criterio de "no hace falta mover nada a mano" que el resto de
    las migraciones de este módulo.

    Para "Localidad", "Edificio", "Unidad" y "Consultorio" usa en
    cambio el nombre descriptivo de cada nivel (`nombre_carpeta_
    localidad`/`..._edificio`/`..._unidad`/`..._consultorio`, pedido
    explícito de la clienta) — y, si todavía existe la carpeta vieja
    basada en ID ("{Alcance}_{id}", de antes de este cambio) sin la
    nueva, la migra sola la primera vez que se accede a las imágenes de
    ese registro, sin que haga falta renombrar nada a mano. Consultorio
    además migra, de la misma forma, desde su formato descriptivo
    anterior con guiones (ver `_FORMATO_CONSULTORIO_ANTERIOR`)."""
    base = _requerir_carpeta_base(conn)
    _migrar_carpeta_imagenes_al_nivel_viejo(base)
    carpeta_base_imagenes = base / "Archivos varios" / "Imagenes"
    datos = _DATOS_PARA_CARPETA.get(alcance)
    if datos is not None and id_valor is not None:
        buscar_fila, armar_nombre = datos
        fila = buscar_fila(conn, id_valor)
        nombre = armar_nombre(fila) if fila is not None else f"{alcance}_{id_valor}"
        carpeta = carpeta_base_imagenes / nombre
        carpeta_vieja_por_id = carpeta_base_imagenes / f"{alcance}_{id_valor}"
        if carpeta_vieja_por_id != carpeta:
            _mover_contenido_carpeta(carpeta_vieja_por_id, carpeta)
        if alcance == "Consultorio" and fila is not None:
            carpeta_vieja_con_guiones = carpeta_base_imagenes / _FORMATO_CONSULTORIO_ANTERIOR(fila)
            if carpeta_vieja_con_guiones != carpeta:
                _mover_contenido_carpeta(carpeta_vieja_con_guiones, carpeta)
    else:
        nombre = alcance if id_valor is None else f"{alcance}_{id_valor}"
        carpeta = carpeta_base_imagenes / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _migrar_carpeta_imagenes_al_nivel_viejo(base: Path) -> None:
    """Si todavía existe "Imagenes" al nivel viejo (bajo la carpeta
    base, al lado de "Archivos varios"/"Profesionales"), mueve TODO su
    contenido a "Archivos varios/Imagenes" de una sola vez — se llama al
    principio de `carpeta_imagenes`, así que corre sola la primera vez
    que se accede a cualquier imagen después de esta ronda, sin tocar
    nada a mano. No usa `_mover_contenido_carpeta` directo (que mueve
    TODO lo de `origen`, sin mirar si `destino` ya tiene algo con el
    mismo nombre) porque acá adentro hay subcarpetas por registro — si
    "Archivos varios/Imagenes" ya tuviera una subcarpeta con el mismo
    nombre (poco probable pero posible, ej. corriendo esta migración dos
    veces con algo creado en el medio), hay que fusionar el contenido de
    cada una en vez de que `shutil.move` falle.

    Bug real reportado por la clienta: en Windows, `rmdir()` de la
    carpeta vieja ya vacía puede tirar `PermissionError` (ej. un
    antivirus o el propio Explorer la tiene abierta/bloqueada en ese
    instante) — como esto corre en CADA arranque (`resincronizar_
    carpetas_imagenes`, llamada desde `init_database`), ese error
    tiraba abajo el arranque entero de la aplicación. El contenido ya
    se movió para entonces (lo único que falla es borrar la carpeta
    vieja, ya vacía), así que no borrarla todavía no es motivo para
    interrumpir el arranque — se reintenta sola en el próximo arranque."""
    carpeta_vieja = base / "Imagenes"
    if not carpeta_vieja.is_dir():
        return
    carpeta_nueva = base / "Archivos varios" / "Imagenes"
    carpeta_nueva.mkdir(parents=True, exist_ok=True)
    for entrada in list(carpeta_vieja.iterdir()):
        _mover_contenido_carpeta(entrada, carpeta_nueva / entrada.name)
    if not any(carpeta_vieja.iterdir()):
        try:
            carpeta_vieja.rmdir()
        except OSError:
            pass


def resincronizar_carpetas_imagenes(conn: sqlite3.Connection) -> int:
    """Pedido explícito de la clienta ("tengo las carpetas de imágenes de
    los consultorios con el formato viejo, ¿cómo hago para pasarlas al
    nuevo formato de una manera sencilla?"): `carpeta_imagenes` ya migra
    sola la carpeta de UN registro puntual cada vez que se accede a sus
    imágenes (ver su docstring), pero eso significaba, en la práctica,
    tener que entrar uno por uno a cada Localidad/Edificio/Unidad/
    Consultorio para que se renombrara. Esta función recorre TODOS los
    registros existentes de los cuatro alcances y dispara esa misma
    migración para cada uno que todavía tenga una carpeta vieja en
    disco — se llama sola en cada arranque (`app.db.init_db.
    init_database`, mismo criterio que `app.negocio.pagos.
    reconciliar_saldos_cruzados`), así que no hace falta ningún paso
    manual: la próxima vez que se abra el sistema, ya están todas al día.

    Solo toca un registro si encuentra, en disco, su carpeta vieja
    (basada en ID, o — para Consultorio — el formato descriptivo anterior
    con guiones): un registro que nunca tuvo imágenes cargadas no tiene
    ninguna carpeta vieja que migrar, así que no se le crea una carpeta
    nueva vacía de la nada (a diferencia de llamar a `carpeta_imagenes`
    directo, que SIEMPRE crea la carpeta si no existe). Sin efecto si la
    carpeta base de archivos todavía no está configurada. Devuelve la
    cantidad de carpetas migradas, para quien quiera loguearlo — el
    llamador de `init_database` no hace nada con el valor."""
    base = carpeta_base(conn)
    if base is None:
        return 0
    _migrar_carpeta_imagenes_al_nivel_viejo(base)
    carpeta_base_imagenes = base / "Archivos varios" / "Imagenes"
    if not carpeta_base_imagenes.is_dir():
        return 0

    migradas = 0
    for alcance, (buscar_fila, armar_nombre) in _DATOS_PARA_CARPETA.items():
        ids = [f[0] for f in conn.execute(f"SELECT Id{alcance} FROM {alcance}").fetchall()]
        for id_valor in ids:
            fila = buscar_fila(conn, id_valor)
            if fila is None:
                continue
            nombre_nuevo = armar_nombre(fila)
            carpeta_vieja_por_id = carpeta_base_imagenes / f"{alcance}_{id_valor}"
            necesita_migrar = carpeta_vieja_por_id.is_dir() and carpeta_vieja_por_id.name != nombre_nuevo
            if not necesita_migrar and alcance == "Consultorio":
                carpeta_vieja_guiones = carpeta_base_imagenes / _FORMATO_CONSULTORIO_ANTERIOR(fila)
                necesita_migrar = carpeta_vieja_guiones.is_dir() and carpeta_vieja_guiones.name != nombre_nuevo
            if necesita_migrar:
                carpeta_imagenes(conn, alcance, id_valor)
                migradas += 1
    return migradas


def carpeta_liquidaciones_simuladas(conn: sqlite3.Connection) -> Path:
    """"Archivos varios/Liquidaciones simuladas" bajo la carpeta base —
    carpeta ÚNICA compartida por todos los profesionales (a diferencia
    de `carpeta_profesional`, una por código): la retención acá es corta
    (`limpiar_liquidaciones_simuladas_antiguas`), no hace falta separar
    por profesional. La crea si hace falta.

    Pedido explícito de la clienta: pasa a vivir DENTRO de "Archivos
    varios" (antes directo bajo la carpeta base, al mismo nivel que
    "Profesionales") — mismo criterio que `carpeta_imagenes`. Si
    todavía existe la carpeta vieja al nivel de arriba, se migra sola
    (mueve TODO su contenido, sin pisar nada si la nueva ya tiene algo
    con el mismo nombre — mismas liquidaciones simuladas generadas en
    dos corridas distintas antes de reabrir el sistema, caso de borde
    poco probable pero cubierto)."""
    base = _requerir_carpeta_base(conn)
    carpeta = base / "Archivos varios" / SUBCARPETA_LIQUIDACIONES_SIMULADAS
    carpeta_vieja = base / SUBCARPETA_LIQUIDACIONES_SIMULADAS
    if carpeta_vieja.is_dir():
        carpeta.parent.mkdir(parents=True, exist_ok=True)  # _mover_contenido_carpeta necesita el padre ya creado
        _mover_contenido_carpeta(carpeta_vieja, carpeta)
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
