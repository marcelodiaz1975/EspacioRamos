"""Gestión de imágenes (FA4, sección 3.26): fotos de edificios, unidades y
consultorios que aparecen en Propuesta, Disponibilidad, Liquidación y
Oferta de consultorios (`app.pdf.fotos_pdf`) — hoy solo se muestran las de
consultorio (`app.pdf.fotos_pdf.imagenes_de_consultorios`), las de
edificio/unidad/localidad/espacio quedan guardadas para cuando algún
documento las use.

Alcance (`ALCANCES`): además de Edificio/Unidad/Consultorio hay dos
niveles más generales, pedidos por la clienta al revisar esta pantalla:
- "Espacio": imágenes generales del sistema, sin atarse a ningún
  edificio en particular (logos, flyers, banners). Es el alcance que
  resulta cuando no se pasa ninguno de los otros cuatro parámetros.
- "Localidad": referencia la tabla `Localidad` (catálogo propio, con
  Partido/Provincia/País como datos adicionales) en vez de Edificio/
  Unidad/Consultorio — mismo criterio de ID estable que el resto.

Categoría (`CATEGORIAS_POR_ALCANCE`): cada alcance tiene su propia lista
cerrada de categorías (ej. Edificio: "Fachada", "Ascensor"...; Unidad:
"Cocina", "Baño"...) elegida en el cuadro de diálogo al agregar una
imagen — se guarda en `Imagen.Tipo`. Dentro de cada (alcance, entidad,
categoría) las imágenes tienen un `NumeroOrden` propio: la de orden 1 es
la "principal" (puede haber varias de la misma categoría cargadas como
respaldo, pero solo una principal a la vez — `marcar_principal`
intercambia el orden con la que tenía el 1). La Descripción y el nombre
del archivo en disco se arman solos a partir de Alcance + Categoría +
Orden (`_descripcion_automatica`) — no se cargan a mano.

`obtener_principal`: para un (categoría, alcance) dado, si el alcance
es Localidad y no hay ninguna imagen principal ahí, cae al alcance
Espacio (ej. el logo general del sistema) — así una localidad sin su
propio logo cargado usa el del espacio, pero si tiene uno propio ese
pisa al general.

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
from uuid import uuid4

from app.negocio.archivos_generados import carpeta_imagenes, destino_sin_colision
from app.repositorio.registro import obtener_repositorio

EXTENSIONES_VALIDAS = (".jpg", ".jpeg", ".png")
ALCANCES = ("Espacio", "Localidad", "Edificio", "Unidad", "Consultorio")

CATEGORIAS_POR_ALCANCE: dict[str, list[str]] = {
    "Espacio": ["Logo PDF", "Logo WhatsApp", "Logo redes sociales", "Flyer", "Banner", "Otros archivos"],
    "Localidad": [
        "Mapa ubicación", "Logo PDF", "Logo WhatsApp", "Logo redes sociales", "Flyer", "Banner", "Otros archivos",
    ],
    "Edificio": ["Mapa ubicación", "Fachada", "Ascensor", "Pasillo", "Recepción", "Portero", "Otros archivos"],
    "Unidad": [
        "Plano", "Cocina", "Baño", "Sala de espera", "Office", "Área de guardado", "Pasillo",
        "Puerta de entrada", "Balcón", "Encendido luz común", "Caja para pagos", "Panel de luces testigo",
        "Otros archivos",
    ],
    "Consultorio": [
        "Foto general", "Sillón profesional", "Sillón paciente", "Escritorio", "Aire acondicionado",
        "Control de aire acondicionado", "Ventana", "Otros archivos",
    ],
}

_CARACTERES_INVALIDOS_ARCHIVO = re.compile(r'[\\/:*?"<>|]')


def _nombre_archivo_valido(texto: str) -> str:
    """Nombres de archivo en Windows (donde se empaqueta con
    PyInstaller) no admiten \\/:*?"<>|."""
    return _CARACTERES_INVALIDOS_ARCHIVO.sub("_", texto).strip() or "archivo"


def _alcance(
    id_localidad: int | None, id_edificio: int | None, id_unidad: int | None, id_consultorio: int | None,
) -> tuple[str, int | None]:
    """A qué nivel pertenece la imagen a partir de cuál de los cuatro
    parámetros vino cargado. Si ninguno vino cargado, el alcance es
    "Espacio"."""
    seleccionados = [
        (alcance, valor) for alcance, valor in (
            ("Localidad", id_localidad), ("Edificio", id_edificio), ("Unidad", id_unidad), ("Consultorio", id_consultorio),
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


def _condicion_alcance(alcance: str, valor: int | None) -> tuple[str, list]:
    if alcance == "Espacio":
        return "IdLocalidad IS NULL AND IdEdificio IS NULL AND IdUnidad IS NULL AND IdConsultorio IS NULL", []
    return f"Id{alcance} = ?", [valor]


def _condicion_alcance_categoria(alcance: str, valor: int | None, categoria: str) -> tuple[str, list]:
    condicion, parametros = _condicion_alcance(alcance, valor)
    return f"{condicion} AND Tipo = ?", [*parametros, categoria]


def _descripcion_automatica(alcance: str, categoria: str, numero_orden: int) -> str:
    return f"{alcance} - {categoria} - {numero_orden}"


def _tamano_maximo_mb(conn: sqlite3.Connection) -> float:
    fila = conn.execute("SELECT TamanoMaximoImagenMB FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    return (fila["TamanoMaximoImagenMB"] if fila else None) or 5


def imagenes_del_grupo(conn: sqlite3.Connection, imagen: sqlite3.Row) -> list[sqlite3.Row]:
    """Las imágenes que comparten alcance, entidad y categoría con
    `imagen` (incluida ella misma), ordenadas por NumeroOrden — el
    "grupo" dentro del cual el número 1 es la principal."""
    alcance, valor = _alcance(imagen["IdLocalidad"], imagen["IdEdificio"], imagen["IdUnidad"], imagen["IdConsultorio"])
    condicion, parametros = _condicion_alcance_categoria(alcance, valor, imagen["Tipo"])
    filas = conn.execute(f"SELECT * FROM Imagen WHERE {condicion}", parametros).fetchall()
    return sorted(filas, key=lambda i: i["NumeroOrden"])


def _mover_a_temporal(ruta: Path) -> Path:
    if not ruta.is_file():
        return ruta
    temporal = ruta.parent / f".tmp_{uuid4().hex}{ruta.suffix}"
    ruta.rename(temporal)
    return temporal


def _sincronizar_descripcion_y_archivo(conn: sqlite3.Connection, id_imagen: int) -> None:
    """Recalcula la Descripción (Alcance + Categoría + Orden) y, si
    cambió, renombra el archivo en disco para que coincida — se llama
    después de crear una imagen o de cualquier cambio de NumeroOrden."""
    repo = obtener_repositorio(conn, "Imagen")
    imagen = repo.obtener(id_imagen)
    if imagen is None:
        return
    alcance, _ = _alcance(imagen["IdLocalidad"], imagen["IdEdificio"], imagen["IdUnidad"], imagen["IdConsultorio"])
    descripcion = _descripcion_automatica(alcance, imagen["Tipo"], imagen["NumeroOrden"])
    ruta_actual = Path(imagen["RutaArchivo"])
    nombre_nuevo = f"{_nombre_archivo_valido(descripcion)}{ruta_actual.suffix.lower()}"
    if ruta_actual.name != nombre_nuevo and ruta_actual.is_file():
        destino = destino_sin_colision(ruta_actual.parent, nombre_nuevo)
        ruta_actual.rename(destino)
        ruta_actual = destino
    repo.actualizar(id_imagen, Descripcion=descripcion, RutaArchivo=str(ruta_actual))


def _intercambiar_orden(conn: sqlite3.Connection, id_imagen_1: int, id_imagen_2: int) -> None:
    """Intercambia NumeroOrden entre dos imágenes y actualiza su
    Descripción/nombre de archivo. Pasa los dos archivos por un nombre
    temporal antes de asignarles el nombre final: un intercambio directo
    (ej. "Fachada - 1.jpg" <-> "Fachada - 2.jpg") pisaría el nombre del
    otro antes de que se libere."""
    repo = obtener_repositorio(conn, "Imagen")
    img1 = repo.obtener(id_imagen_1)
    img2 = repo.obtener(id_imagen_2)
    ruta1_temp = _mover_a_temporal(Path(img1["RutaArchivo"]))
    ruta2_temp = _mover_a_temporal(Path(img2["RutaArchivo"]))
    repo.actualizar(id_imagen_1, NumeroOrden=img2["NumeroOrden"], RutaArchivo=str(ruta1_temp))
    repo.actualizar(id_imagen_2, NumeroOrden=img1["NumeroOrden"], RutaArchivo=str(ruta2_temp))
    _sincronizar_descripcion_y_archivo(conn, id_imagen_1)
    _sincronizar_descripcion_y_archivo(conn, id_imagen_2)


def agregar_imagen(
    conn: sqlite3.Connection, *, ruta_origen: str, categoria: str, principal: bool = False,
    id_localidad: int | None = None, id_edificio: int | None = None, id_unidad: int | None = None,
    id_consultorio: int | None = None,
) -> int:
    """Copia `ruta_origen` a la carpeta del alcance elegido y registra la
    fila en Imagen, al final del orden existente para esa categoría
    dentro de ese alcance — o como principal (orden 1, desplazando a la
    que tenía ese lugar) si `principal=True`. La Descripción y el nombre
    de archivo se arman solos. Devuelve el IdImagen creado."""
    alcance, valor = _alcance(id_localidad, id_edificio, id_unidad, id_consultorio)
    origen = Path(ruta_origen)
    if not origen.is_file():
        raise ValueError(f"No se encuentra el archivo: {ruta_origen}")
    if origen.suffix.lower() not in EXTENSIONES_VALIDAS:
        raise ValueError("Formato no soportado: usá JPG o PNG.")
    tamano_mb = origen.stat().st_size / (1024 * 1024)
    maximo = _tamano_maximo_mb(conn)
    if tamano_mb > maximo:
        raise ValueError(f"La imagen pesa {tamano_mb:.1f}MB, el máximo configurado es {maximo:g}MB.")

    destino = destino_sin_colision(carpeta_imagenes(conn, alcance, valor), origen.name)
    shutil.copy2(origen, destino)

    condicion, parametros = _condicion_alcance_categoria(alcance, valor, categoria)
    orden_actual = conn.execute(
        f"SELECT COALESCE(MAX(NumeroOrden), 0) FROM Imagen WHERE {condicion}", parametros
    ).fetchone()[0]
    repo = obtener_repositorio(conn, "Imagen")
    id_imagen = repo.crear(
        Tipo=categoria, IdLocalidad=id_localidad, IdEdificio=id_edificio, IdUnidad=id_unidad,
        IdConsultorio=id_consultorio, NumeroOrden=orden_actual + 1, RutaArchivo=str(destino), Activo=1,
    )
    _sincronizar_descripcion_y_archivo(conn, id_imagen)
    if principal:
        marcar_principal(conn, id_imagen)
    return id_imagen


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
    conn: sqlite3.Connection, id_localidad: int | None = None, id_edificio: int | None = None,
    id_unidad: int | None = None, id_consultorio: int | None = None,
) -> list[sqlite3.Row]:
    """Todas las imágenes (activas e inactivas) del alcance elegido,
    agrupadas por categoría (en el orden de `CATEGORIAS_POR_ALCANCE`) y,
    dentro de cada una, por NumeroOrden (la principal primero). Sin
    ningún parámetro, trae las de alcance "Espacio". Para la pantalla de
    gestión — a diferencia de `app.pdf.fotos_pdf.imagenes_de_
    consultorios`, que solo trae las activas para los documentos."""
    alcance, valor = _alcance(id_localidad, id_edificio, id_unidad, id_consultorio)
    condicion, parametros = _condicion_alcance(alcance, valor)
    filas = conn.execute(f"SELECT * FROM Imagen WHERE {condicion}", parametros).fetchall()
    orden_categorias = CATEGORIAS_POR_ALCANCE.get(alcance, [])

    def clave(fila: sqlite3.Row):
        tipo = fila["Tipo"] or ""
        indice = orden_categorias.index(tipo) if tipo in orden_categorias else len(orden_categorias)
        return (indice, fila["NumeroOrden"])

    return sorted(filas, key=clave)


def imagenes_todas(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Todas las imágenes del sistema, sea cual sea su alcance, con la
    ubicación textual resuelta (LocalidadTexto/EdificioTexto/
    UnidadTexto/ConsultorioNumero, según a qué nivel esté cada una) para
    la vista "Todos los archivos" de la pantalla. Orden: nivel (Espacio,
    Localidad, Edificio, Unidad, Consultorio, en ese orden) y después
    por Descripción."""
    filas = conn.execute(
        """
        SELECT i.*,
            CASE
                WHEN i.IdConsultorio IS NOT NULL THEN 'Consultorio'
                WHEN i.IdUnidad IS NOT NULL THEN 'Unidad'
                WHEN i.IdEdificio IS NOT NULL THEN 'Edificio'
                WHEN i.IdLocalidad IS NOT NULL THEN 'Localidad'
                ELSE 'Espacio'
            END AS Alcance,
            COALESCE(loc.Localidad, loc_ed.Localidad, loc_un.Localidad, loc_co.Localidad) AS LocalidadTexto,
            COALESCE(ed.Nombre, ed_un.Nombre, ed_co.Nombre) AS EdificioTexto,
            COALESCE(un.Departamento, un_co.Departamento) AS UnidadTexto,
            co.NumeroConsultorio AS ConsultorioNumero
        FROM Imagen i
        LEFT JOIN Localidad loc ON loc.IdLocalidad = i.IdLocalidad
        LEFT JOIN Edificio ed ON ed.IdEdificio = i.IdEdificio
        LEFT JOIN Localidad loc_ed ON loc_ed.IdLocalidad = ed.IdLocalidad
        LEFT JOIN Unidad un ON un.IdUnidad = i.IdUnidad
        LEFT JOIN Edificio ed_un ON ed_un.IdEdificio = un.IdEdificio
        LEFT JOIN Localidad loc_un ON loc_un.IdLocalidad = ed_un.IdLocalidad
        LEFT JOIN Consultorio co ON co.IdConsultorio = i.IdConsultorio
        LEFT JOIN Unidad un_co ON un_co.IdUnidad = co.IdUnidad
        LEFT JOIN Edificio ed_co ON ed_co.IdEdificio = un_co.IdEdificio
        LEFT JOIN Localidad loc_co ON loc_co.IdLocalidad = ed_co.IdLocalidad
        """
    ).fetchall()
    orden_nivel = {"Espacio": 0, "Localidad": 1, "Edificio": 2, "Unidad": 3, "Consultorio": 4}
    return sorted(filas, key=lambda f: (orden_nivel[f["Alcance"]], f["Descripcion"] or ""))


def reordenar(conn: sqlite3.Connection, id_imagen: int, delta: int) -> None:
    """Mueve una imagen un lugar dentro del orden de su mismo grupo
    (alcance + entidad + categoría) — delta -1 sube, +1 baja."""
    repo = obtener_repositorio(conn, "Imagen")
    imagen = repo.obtener(id_imagen)
    if imagen is None:
        return
    vecinas = imagenes_del_grupo(conn, imagen)
    indice = next(i for i, v in enumerate(vecinas) if v["IdImagen"] == id_imagen)
    nuevo_indice = indice + delta
    if not (0 <= nuevo_indice < len(vecinas)):
        return
    _intercambiar_orden(conn, id_imagen, vecinas[nuevo_indice]["IdImagen"])


def marcar_principal(conn: sqlite3.Connection, id_imagen: int) -> None:
    """Pone a esta imagen en el orden 1 de su grupo (alcance + entidad +
    categoría) — la que tenía ese lugar pasa a ocupar el suyo, sin
    borrarse: queda como una imagen más, de respaldo."""
    repo = obtener_repositorio(conn, "Imagen")
    imagen = repo.obtener(id_imagen)
    if imagen is None or imagen["NumeroOrden"] == 1:
        return
    vecinas = imagenes_del_grupo(conn, imagen)
    principal_actual = next((v for v in vecinas if v["NumeroOrden"] == 1), None)
    if principal_actual is None:
        repo.actualizar(id_imagen, NumeroOrden=1)
        _sincronizar_descripcion_y_archivo(conn, id_imagen)
        return
    _intercambiar_orden(conn, id_imagen, principal_actual["IdImagen"])


def obtener_principal(
    conn: sqlite3.Connection, categoria: str, *, id_localidad: int | None = None,
    id_edificio: int | None = None, id_unidad: int | None = None, id_consultorio: int | None = None,
) -> sqlite3.Row | None:
    """La imagen principal (NumeroOrden = 1) de esa categoría en el
    nivel más específico indicado. Para Localidad, si no hay ninguna
    marcada ahí, cae al alcance Espacio (ej. el logo general del
    sistema pisa por defecto, pero una localidad con su propio logo usa
    el suyo) — para el resto de los niveles no hay ese respaldo: si no
    cargaste una Fachada para ESE edificio puntual, no hay ninguna."""
    alcance, valor = _alcance(id_localidad, id_edificio, id_unidad, id_consultorio)
    condicion, parametros = _condicion_alcance_categoria(alcance, valor, categoria)
    fila = conn.execute(f"SELECT * FROM Imagen WHERE {condicion} AND NumeroOrden = 1", parametros).fetchone()
    if fila is not None:
        return fila
    if alcance == "Localidad":
        condicion_espacio, parametros_espacio = _condicion_alcance_categoria("Espacio", None, categoria)
        return conn.execute(
            f"SELECT * FROM Imagen WHERE {condicion_espacio} AND NumeroOrden = 1", parametros_espacio
        ).fetchone()
    return None


def alternar_activo(conn: sqlite3.Connection, id_imagen: int) -> None:
    repo = obtener_repositorio(conn, "Imagen")
    imagen = repo.obtener(id_imagen)
    if imagen is None:
        return
    repo.actualizar(id_imagen, Activo=0 if imagen["Activo"] else 1)
