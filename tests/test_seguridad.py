"""Login, historial de contraseñas y niveles de acceso por pantalla — ver
el docstring de app.negocio.seguridad para el detalle de cada decisión
de la clienta."""
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.seguridad import (
    asegurar_permisos_pantalla,
    autenticar,
    cambiar_contrasena,
    cambiar_contrasena_maestra,
    crear_usuario,
    establecer_contrasena_maestra,
    hay_contrasena_maestra,
    hay_otro_usuario_activo_de_nivel,
    hay_usuarios,
    nivel_alcanza,
    verificar_contrasena_maestra,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _id_nivel(conn, nombre):
    return conn.execute("SELECT IdNivelAcceso FROM NivelAcceso WHERE Nombre = ?", (nombre,)).fetchone()["IdNivelAcceso"]


# ------------------------------------------------------------- niveles


def test_sembrado_crea_supervisor_general_administrador_y_operador(conn):
    filas = obtener_repositorio(conn, "NivelAcceso").listar()
    nombres = {f["Nombre"] for f in filas}
    assert nombres == {"Supervisor general", "Administrador", "Operador"}
    supervisor = next(f for f in filas if f["Nombre"] == "Supervisor general")
    admin = next(f for f in filas if f["Nombre"] == "Administrador")
    operador = next(f for f in filas if f["Nombre"] == "Operador")
    assert supervisor["Orden"] > admin["Orden"] > operador["Orden"]


# ------------------------------------------------------------- usuarios


def test_hay_usuarios_falso_hasta_el_primer_alta(conn):
    assert hay_usuarios(conn) is False
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Administrador"))
    assert hay_usuarios(conn) is True


def test_crear_usuario_no_permite_nombre_duplicado(conn):
    id_nivel = _id_nivel(conn, "Operador")
    crear_usuario(conn, "ana", "clave123", id_nivel)
    with pytest.raises(ValueError):
        crear_usuario(conn, "ana", "otraclave", id_nivel)


def test_crear_usuario_no_permite_nombre_ni_contrasena_vacios(conn):
    id_nivel = _id_nivel(conn, "Operador")
    with pytest.raises(ValueError):
        crear_usuario(conn, "  ", "clave123", id_nivel)
    with pytest.raises(ValueError):
        crear_usuario(conn, "ana", "", id_nivel)


def test_contrasena_nunca_se_guarda_en_texto_plano(conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    fila = conn.execute("SELECT HashContrasena FROM Usuario WHERE NombreUsuario = 'ana'").fetchone()
    assert "clave123" not in fila["HashContrasena"]


# ------------------------------------------------------------ autenticar


def test_autenticar_con_credenciales_correctas(conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    usuario = autenticar(conn, "ana", "clave123")
    assert usuario is not None
    assert usuario["NombreUsuario"] == "ana"
    assert usuario["UltimoIngreso"] is not None


def test_autenticar_con_contrasena_incorrecta_devuelve_none(conn):
    crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    assert autenticar(conn, "ana", "otraclave") is None


def test_autenticar_usuario_inexistente_devuelve_none(conn):
    assert autenticar(conn, "no_existe", "clave123") is None


def test_autenticar_usuario_inactivo_devuelve_none(conn):
    id_usuario = crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    obtener_repositorio(conn, "Usuario").actualizar(id_usuario, Activo=0)
    conn.commit()
    assert autenticar(conn, "ana", "clave123") is None


# ------------------------------------------------------ cambiar contraseña


def test_cambiar_contrasena_permite_autenticar_con_la_nueva(conn):
    id_usuario = crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    cambiar_contrasena(conn, id_usuario, "clavenueva", realizado_por=id_usuario, motivo="Cambio propio")
    assert autenticar(conn, "ana", "clave123") is None
    assert autenticar(conn, "ana", "clavenueva") is not None


def test_cambiar_contrasena_guarda_historial_con_el_hash_anterior(conn):
    id_usuario = crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    hash_anterior = conn.execute("SELECT HashContrasena FROM Usuario WHERE IdUsuario = ?", (id_usuario,)).fetchone()[0]
    id_admin = crear_usuario(conn, "admin", "adminpass", _id_nivel(conn, "Administrador"))

    cambiar_contrasena(conn, id_usuario, "clavenueva", realizado_por=id_admin, motivo="Reseteo por administrador")

    historial = conn.execute(
        "SELECT * FROM HistorialContrasenas WHERE IdUsuario = ?", (id_usuario,)
    ).fetchall()
    assert len(historial) == 1
    fila = historial[0]
    assert fila["HashContrasenaAnterior"] == hash_anterior
    assert fila["Motivo"] == "Reseteo por administrador"
    assert fila["IdUsuarioQueRealizoElCambio"] == id_admin
    assert "clave123" not in fila["HashContrasenaAnterior"]


def test_cambiar_contrasena_no_permite_vacia(conn):
    id_usuario = crear_usuario(conn, "ana", "clave123", _id_nivel(conn, "Operador"))
    with pytest.raises(ValueError):
        cambiar_contrasena(conn, id_usuario, "", realizado_por=id_usuario, motivo="Cambio propio")


# ------------------------------------------------------ contraseña maestra


def test_contrasena_maestra_sin_configurar_nunca_autoriza(conn):
    assert verificar_contrasena_maestra(conn, "") is False
    assert verificar_contrasena_maestra(conn, "cualquiera") is False


def test_contrasena_maestra_configurada_se_puede_verificar(conn):
    establecer_contrasena_maestra(conn, "maestra123")
    assert verificar_contrasena_maestra(conn, "maestra123") is True
    assert verificar_contrasena_maestra(conn, "incorrecta") is False


def test_hay_contrasena_maestra_refleja_si_ya_se_establecio(conn):
    assert hay_contrasena_maestra(conn) is False
    establecer_contrasena_maestra(conn, "maestra123")
    assert hay_contrasena_maestra(conn) is True


def test_cambiar_contrasena_maestra_primera_vez_no_pide_la_anterior(conn):
    cambiar_contrasena_maestra(conn, "", "maestra123")
    assert verificar_contrasena_maestra(conn, "maestra123") is True


def test_cambiar_contrasena_maestra_exige_la_anterior_correcta(conn):
    establecer_contrasena_maestra(conn, "maestra123")
    with pytest.raises(ValueError):
        cambiar_contrasena_maestra(conn, "incorrecta", "nueva456")
    assert verificar_contrasena_maestra(conn, "maestra123") is True


def test_cambiar_contrasena_maestra_con_la_anterior_correcta(conn):
    establecer_contrasena_maestra(conn, "maestra123")
    cambiar_contrasena_maestra(conn, "maestra123", "nueva456")
    assert verificar_contrasena_maestra(conn, "maestra123") is False
    assert verificar_contrasena_maestra(conn, "nueva456") is True


# ------------------------------------------------------ permisos por pantalla


def test_asegurar_permisos_pantalla_crea_filas_al_nivel_mas_bajo(conn):
    asegurar_permisos_pantalla(conn, ["Reservas", "Pagos"])
    filas = {
        f["NombrePantalla"]: f["IdNivelAcceso"]
        for f in conn.execute("SELECT NombrePantalla, IdNivelAcceso FROM PermisoPantalla").fetchall()
    }
    assert filas["Reservas"] == _id_nivel(conn, "Operador")
    assert filas["Pagos"] == _id_nivel(conn, "Operador")


def test_asegurar_permisos_pantalla_nivel_alto_nace_en_administrador(conn):
    """Test de regresión: con "Supervisor general" ya sembrado por encima de
    Administrador (ver fixture `conn`), `nivel_alto` tiene que seguir
    resolviendo a Administrador por NOMBRE — si volviera a resolverse por
    `ORDER BY Orden DESC` (el nivel más alto del catálogo), esta pantalla
    sensible nacería exigiendo Supervisor general y este assert fallaría."""
    asegurar_permisos_pantalla(
        conn, ["Reservas", "Configuración general"], nombres_nivel_alto=frozenset({"Configuración general"}),
    )
    filas = {
        f["NombrePantalla"]: f["IdNivelAcceso"]
        for f in conn.execute("SELECT NombrePantalla, IdNivelAcceso FROM PermisoPantalla").fetchall()
    }
    assert filas["Reservas"] == _id_nivel(conn, "Operador")
    assert filas["Configuración general"] == _id_nivel(conn, "Administrador")


# ------------------------------------------ hay_otro_usuario_activo_de_nivel


def test_hay_otro_usuario_activo_de_nivel_administrador_no_cuenta_a_si_mismo(conn):
    id_admin = crear_usuario(conn, "admin", "clave123", _id_nivel(conn, "Administrador"))
    assert hay_otro_usuario_activo_de_nivel(conn, _id_nivel(conn, "Administrador"), excluir_id=id_admin) is False


def test_hay_otro_usuario_activo_de_nivel_supervisor_general_cuenta_como_administrador(conn):
    """Test de regresión de la razón de ser del cambio a `Orden >=`: un
    Supervisor general activo tiene que alcanzar para proteger al último
    Administrador — si se comparara por `IdNivelAcceso` exacto (como antes
    de sumar este tercer nivel), un Supervisor general no "sería"
    Administrador y esto daría `False`, bloqueando sin necesidad la baja
    del único Administrador aunque el sistema siga teniendo quien lo
    administre."""
    id_admin = crear_usuario(conn, "admin", "clave123", _id_nivel(conn, "Administrador"))
    crear_usuario(conn, "supervisor", "clave123", _id_nivel(conn, "Supervisor general"))
    assert hay_otro_usuario_activo_de_nivel(conn, _id_nivel(conn, "Administrador"), excluir_id=id_admin) is True


def test_hay_otro_usuario_activo_de_nivel_operador_no_alcanza_para_administrador(conn):
    id_admin = crear_usuario(conn, "admin", "clave123", _id_nivel(conn, "Administrador"))
    crear_usuario(conn, "operador", "clave123", _id_nivel(conn, "Operador"))
    assert hay_otro_usuario_activo_de_nivel(conn, _id_nivel(conn, "Administrador"), excluir_id=id_admin) is False


def test_asegurar_permisos_pantalla_no_pisa_una_ya_asignada(conn):
    asegurar_permisos_pantalla(conn, ["Reservas"])
    conn.execute(
        "UPDATE PermisoPantalla SET IdNivelAcceso = ? WHERE NombrePantalla = 'Reservas'",
        (_id_nivel(conn, "Administrador"),),
    )
    conn.commit()

    asegurar_permisos_pantalla(conn, ["Reservas", "Pagos"])

    fila = conn.execute("SELECT IdNivelAcceso FROM PermisoPantalla WHERE NombrePantalla = 'Reservas'").fetchone()
    assert fila["IdNivelAcceso"] == _id_nivel(conn, "Administrador")


def test_nivel_alcanza_administrador_alcanza_todo(conn):
    asegurar_permisos_pantalla(conn, ["Reservas"])
    conn.execute(
        "UPDATE PermisoPantalla SET IdNivelAcceso = ? WHERE NombrePantalla = 'Reservas'",
        (_id_nivel(conn, "Administrador"),),
    )
    conn.commit()
    assert nivel_alcanza(conn, _id_nivel(conn, "Administrador"), "Reservas") is True


def test_nivel_alcanza_operador_no_alcanza_pantalla_de_administrador(conn):
    asegurar_permisos_pantalla(conn, ["Reservas"])
    conn.execute(
        "UPDATE PermisoPantalla SET IdNivelAcceso = ? WHERE NombrePantalla = 'Reservas'",
        (_id_nivel(conn, "Administrador"),),
    )
    conn.commit()
    assert nivel_alcanza(conn, _id_nivel(conn, "Operador"), "Reservas") is False


def test_nivel_alcanza_pantalla_sin_fila_es_visible_por_cualquiera(conn):
    assert nivel_alcanza(conn, _id_nivel(conn, "Operador"), "Pantalla que todavía no se registró") is True
