"""Seguridad: login del sistema, bloqueo por inactividad y niveles de
acceso por pantalla (nueva solapa "Seguridad" dentro de Configuración
general, revisión "uno por uno" ya cerrada — ver CLAUDE.md, sección
"Seguridad"). Pedido de la clienta, pensado en un primer momento para
ella y su familia, pero dejando la puerta abierta a que cada pantalla
del menú requiera un nivel de acceso puntual más adelante.

Contraseñas: nunca se guarda texto plano, ni siquiera en el historial de
cambios. Se hashean con PBKDF2-HMAC-SHA256 (`hashlib`, sin sumar una
dependencia nueva al proyecto) con un salt aleatorio por usuario
(`secrets.token_hex`). `HistorialContrasenas` guarda el hash/salt
ANTERIOR al cambio (para poder auditar cuándo y por quién cambió, no
para poder leer ninguna contraseña vieja ni la nueva).

Recuperación de acceso (pedido explícito de la clienta: "ambas" al
consultarle cómo se recupera un acceso perdido, dado que es una app de
escritorio sin server/email para resetear nada): (1) cualquier usuario
Administrador puede resetear la contraseña de otro usuario desde la
pantalla de Usuarios sin conocer la actual (`cambiar_contrasena` con
`realizado_por` distinto de `id_usuario`), y (2) una contraseña maestra
guardada aparte en `Configuracion` (`establecer_contrasena_maestra`/
`verificar_contrasena_maestra`) como red de seguridad si se pierde el
acceso de TODOS los administradores a la vez — no se pide nunca en el
uso normal del sistema, solo en esa pantalla de emergencia.

Niveles de acceso (`NivelAcceso`, catálogo con un campo `Orden` —
mayor Orden = más privilegios): pedido de la clienta, quedó confirmado
que la asignación de qué nivel mínimo requiere cada pantalla tiene que
poder cambiarse DESDE el sistema en cualquier momento, no fija en
código. `PermisoPantalla` guarda esa asignación por nombre de pantalla
(el mismo `nombre` de `Seccion` en `gui_main.construir_secciones`).
`asegurar_permisos_pantalla` se llama al arrancar la GUI y le crea una
fila (al nivel más bajo — "Operador", visible para cualquiera, para no
restringir nada que hoy ya se ve) a toda pantalla que todavía no tenga
una fila propia — así una pantalla nueva del sistema siempre aparece
visible por defecto hasta que alguien decida subirle el nivel."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime

_ITERACIONES_HASH = 200_000


def _generar_salt() -> str:
    return secrets.token_hex(16)


def _hashear(contrasena: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", contrasena.encode("utf-8"), bytes.fromhex(salt), _ITERACIONES_HASH,
    ).hex()


def hay_usuarios(conn: sqlite3.Connection) -> bool:
    """False en el primer arranque (todavía no se cargó ningún usuario) —
    la GUI usa esto para mostrar un alta inicial de Administrador en vez
    de un login que nadie podría pasar."""
    return conn.execute("SELECT COUNT(*) FROM Usuario").fetchone()[0] > 0


def crear_usuario(
    conn: sqlite3.Connection, nombre_usuario: str, contrasena: str, id_nivel_acceso: int,
) -> int:
    if not nombre_usuario.strip():
        raise ValueError("El nombre de usuario no puede estar vacío")
    if not contrasena:
        raise ValueError("La contraseña no puede estar vacía")
    if conn.execute("SELECT 1 FROM Usuario WHERE NombreUsuario = ?", (nombre_usuario,)).fetchone():
        raise ValueError(f"Ya existe un usuario '{nombre_usuario}'")
    salt = _generar_salt()
    cur = conn.execute(
        "INSERT INTO Usuario (NombreUsuario, HashContrasena, Salt, IdNivelAcceso, Activo, FechaCreacion) "
        "VALUES (?, ?, ?, ?, 1, ?)",
        (nombre_usuario, _hashear(contrasena, salt), salt, id_nivel_acceso, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return cur.lastrowid


def autenticar(conn: sqlite3.Connection, nombre_usuario: str, contrasena: str) -> sqlite3.Row | None:
    """Devuelve la fila de `Usuario` si el nombre/contraseña son correctos
    y el usuario está activo, `None` en cualquier otro caso (usuario
    inexistente, inactivo o contraseña incorrecta) — sin distinguir el
    motivo en la respuesta, para no darle pistas a quien intenta entrar
    sobre si el problema fue el usuario o la contraseña."""
    usuario = conn.execute(
        "SELECT * FROM Usuario WHERE NombreUsuario = ? AND Activo = 1", (nombre_usuario,)
    ).fetchone()
    if usuario is None:
        return None
    if _hashear(contrasena, usuario["Salt"]) != usuario["HashContrasena"]:
        return None
    conn.execute(
        "UPDATE Usuario SET UltimoIngreso = ? WHERE IdUsuario = ?",
        (datetime.now().isoformat(timespec="seconds"), usuario["IdUsuario"]),
    )
    conn.commit()
    return conn.execute("SELECT * FROM Usuario WHERE IdUsuario = ?", (usuario["IdUsuario"],)).fetchone()


def cambiar_contrasena(
    conn: sqlite3.Connection, id_usuario: int, contrasena_nueva: str, *, realizado_por: int, motivo: str,
) -> None:
    """Cambia la contraseña de `id_usuario`, guardando la anterior en
    `HistorialContrasenas` antes de pisarla. `realizado_por` es el
    usuario que hizo el cambio — el mismo `id_usuario` si cambió su
    propia contraseña, otro (un Administrador) si fue un reseteo."""
    if not contrasena_nueva:
        raise ValueError("La contraseña no puede estar vacía")
    usuario = conn.execute("SELECT * FROM Usuario WHERE IdUsuario = ?", (id_usuario,)).fetchone()
    if usuario is None:
        raise ValueError(f"No existe el usuario #{id_usuario}")
    conn.execute(
        "INSERT INTO HistorialContrasenas "
        "(IdUsuario, FechaHora, HashContrasenaAnterior, SaltAnterior, Motivo, IdUsuarioQueRealizoElCambio) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            id_usuario, datetime.now().isoformat(timespec="seconds"),
            usuario["HashContrasena"], usuario["Salt"], motivo, realizado_por,
        ),
    )
    salt = _generar_salt()
    conn.execute(
        "UPDATE Usuario SET HashContrasena = ?, Salt = ? WHERE IdUsuario = ?",
        (_hashear(contrasena_nueva, salt), salt, id_usuario),
    )
    conn.commit()


def establecer_contrasena_maestra(conn: sqlite3.Connection, contrasena: str) -> None:
    if not contrasena:
        raise ValueError("La contraseña no puede estar vacía")
    salt = _generar_salt()
    conn.execute(
        "UPDATE Configuracion SET ContrasenaMaestraHash = ?, ContrasenaMaestraSalt = ? WHERE IdConfiguracion = 1",
        (_hashear(contrasena, salt), salt),
    )
    conn.commit()


def verificar_contrasena_maestra(conn: sqlite3.Connection, contrasena: str) -> bool:
    """`False` si todavía no se configuró ninguna contraseña maestra — el
    campo NULL nunca autoriza, cualquiera sea el valor tipeado."""
    cfg = conn.execute(
        "SELECT ContrasenaMaestraHash, ContrasenaMaestraSalt FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    if cfg is None or not cfg["ContrasenaMaestraHash"]:
        return False
    return _hashear(contrasena, cfg["ContrasenaMaestraSalt"]) == cfg["ContrasenaMaestraHash"]


def asegurar_permisos_pantalla(conn: sqlite3.Connection, nombres_pantalla: list[str]) -> None:
    """Le crea una fila en `PermisoPantalla` (al nivel más bajo activo) a
    toda pantalla de `nombres_pantalla` que todavía no tenga una — se
    llama al arrancar la GUI con los nombres reales de
    `gui_main.construir_secciones()`, así que una pantalla nueva del
    sistema siempre nace visible para cualquier nivel hasta que alguien
    decida restringirla desde la pantalla de Seguridad."""
    nivel_defecto = conn.execute(
        "SELECT IdNivelAcceso FROM NivelAcceso WHERE Activo = 1 ORDER BY Orden ASC LIMIT 1"
    ).fetchone()
    if nivel_defecto is None:
        return
    conn.executemany(
        "INSERT OR IGNORE INTO PermisoPantalla (NombrePantalla, IdNivelAcceso) VALUES (?, ?)",
        [(nombre, nivel_defecto["IdNivelAcceso"]) for nombre in set(nombres_pantalla)],
    )
    conn.commit()


def hay_otro_usuario_activo_de_nivel(conn: sqlite3.Connection, id_nivel_acceso: int, excluir_id: int) -> bool:
    """True si existe al menos otro usuario ACTIVO con `id_nivel_acceso`,
    aparte de `excluir_id` — usado por la pantalla de Usuarios para
    evitar desactivar o degradar al último Administrador activo y dejar
    el sistema sin nadie que pueda administrarlo."""
    fila = conn.execute(
        "SELECT 1 FROM Usuario WHERE IdNivelAcceso = ? AND Activo = 1 AND IdUsuario != ? LIMIT 1",
        (id_nivel_acceso, excluir_id),
    ).fetchone()
    return fila is not None


def nivel_alcanza(conn: sqlite3.Connection, id_nivel_usuario: int, nombre_pantalla: str) -> bool:
    """True si el nivel del usuario logueado alcanza el nivel mínimo
    requerido por `nombre_pantalla` en `PermisoPantalla`. Una pantalla
    sin fila propia (no debería pasar si se llamó `asegurar_permisos_
    pantalla` al arrancar) se entiende visible por cualquiera — fail-open,
    para no esconder por error una pantalla nueva que todavía no se
    registró."""
    fila = conn.execute(
        "SELECT n.Orden FROM PermisoPantalla p JOIN NivelAcceso n ON n.IdNivelAcceso = p.IdNivelAcceso "
        "WHERE p.NombrePantalla = ?",
        (nombre_pantalla,),
    ).fetchone()
    if fila is None:
        return True
    orden_usuario = conn.execute("SELECT Orden FROM NivelAcceso WHERE IdNivelAcceso = ?", (id_nivel_usuario,)).fetchone()
    if orden_usuario is None:
        return False
    return orden_usuario["Orden"] >= fila["Orden"]
