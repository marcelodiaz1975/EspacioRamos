import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.backup import (
    activar_modo_sin_sincronizar,
    backup_vencido,
    buscar_backup_mas_reciente,
    carpeta_backup,
    desactivar_modo_sin_sincronizar,
    generar_backup,
    hay_backup_mas_reciente_sin_sincronizar,
    modo_sin_sincronizar_activo,
    restaurar_backup,
    ultimo_backup,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _configurar_carpeta_backup(conn, ruta) -> None:
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBackup=str(ruta))


def test_carpeta_backup_none_sin_configurar(conn):
    assert carpeta_backup(conn) is None


def test_generar_backup_sin_carpeta_configurada_falla(conn):
    with pytest.raises(ValueError):
        generar_backup(conn)


def test_generar_backup_copia_la_base_de_datos(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")

    destino = generar_backup(conn, momento=datetime(2026, 8, 15, 10, 30))

    assert destino == tmp_path / "backups" / "Backup 2026-08-15 10h30"
    archivos_db = list(destino.glob("*.db"))
    assert len(archivos_db) == 1

    copia = sqlite3.connect(archivos_db[0])
    copia.row_factory = sqlite3.Row
    fila = copia.execute("SELECT Nombre FROM Edificio").fetchone()
    assert fila["Nombre"] == "Ramos 1"
    copia.close()


def test_generar_backup_copia_la_carpeta_base_de_archivos(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBaseArchivos=str(tmp_path / "archivos"))
    (tmp_path / "archivos" / "Profesionales" / "R1").mkdir(parents=True)
    (tmp_path / "archivos" / "Profesionales" / "R1" / "2026-08 - Liquidación Ramos.pdf").write_text("x")

    destino = generar_backup(conn, momento=datetime(2026, 8, 15, 10, 30))

    copia = destino / "Archivos" / "Profesionales" / "R1" / "2026-08 - Liquidación Ramos.pdf"
    assert copia.is_file()
    assert copia.read_text() == "x"


def test_generar_backup_sin_carpeta_base_de_archivos_no_falla(conn, tmp_path):
    """Todavía no se configuró CarpetaBaseArchivos: el backup de la base
    de datos igual tiene que funcionar."""
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    destino = generar_backup(conn, momento=datetime(2026, 8, 15, 10, 30))
    assert list(destino.glob("*.db"))
    assert not (destino / "Archivos").exists()


def test_generar_backup_dos_veces_en_el_mismo_minuto_no_pisa_datos(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    momento = datetime(2026, 8, 15, 10, 30)
    destino1 = generar_backup(conn, momento=momento)
    obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2")
    destino2 = generar_backup(conn, momento=momento)
    assert destino1 == destino2  # mismo minuto: se sobrescribe en la misma carpeta, no falla


def test_buscar_backup_mas_reciente_sin_carpeta_devuelve_none(tmp_path):
    assert buscar_backup_mas_reciente(tmp_path / "no-existe") is None


def test_buscar_backup_mas_reciente_sin_backups_devuelve_none(tmp_path):
    (tmp_path / "otra_cosa").mkdir()
    assert buscar_backup_mas_reciente(tmp_path) is None


def test_buscar_backup_mas_reciente_elige_el_ultimo_por_fecha(tmp_path):
    (tmp_path / "Backup 2026-08-01 09h00").mkdir()
    (tmp_path / "Backup 2026-08-15 10h30").mkdir()
    (tmp_path / "Backup 2026-08-10 08h00").mkdir()
    assert buscar_backup_mas_reciente(tmp_path).name == "Backup 2026-08-15 10h30"


def test_restaurar_backup_sin_ningun_backup_falla(tmp_path):
    with pytest.raises(ValueError):
        restaurar_backup(tmp_path / "backups", tmp_path / "destino" / "espacio_ramos.db")


def test_restaurar_backup_copia_base_de_datos_y_archivos(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBaseArchivos=str(tmp_path / "archivos"))
    obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    (tmp_path / "archivos" / "Profesionales" / "R1").mkdir(parents=True)
    (tmp_path / "archivos" / "Profesionales" / "R1" / "doc.pdf").write_text("x")
    generar_backup(conn, momento=datetime(2026, 8, 15, 10, 30))

    db_nueva = tmp_path / "maquina_nueva" / "espacio_ramos.db"
    origen_usado = restaurar_backup(tmp_path / "backups", db_nueva)

    assert origen_usado.name == "Backup 2026-08-15 10h30"
    assert db_nueva.is_file()
    restaurada = sqlite3.connect(db_nueva)
    restaurada.row_factory = sqlite3.Row
    fila = restaurada.execute("SELECT Nombre FROM Edificio").fetchone()
    assert fila["Nombre"] == "Ramos 1"
    restaurada.close()

    assert (tmp_path / "archivos" / "Profesionales" / "R1" / "doc.pdf").exists()


def test_restaurar_backup_elige_el_mas_reciente_entre_varios(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    generar_backup(conn, momento=datetime(2026, 7, 1, 9, 0))
    obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2")
    generar_backup(conn, momento=datetime(2026, 8, 15, 10, 30))

    db_nueva = tmp_path / "maquina_nueva" / "espacio_ramos.db"
    restaurar_backup(tmp_path / "backups", db_nueva)

    restaurada = sqlite3.connect(db_nueva)
    restaurada.row_factory = sqlite3.Row
    nombres = {f["Nombre"] for f in restaurada.execute("SELECT Nombre FROM Edificio")}
    restaurada.close()
    assert nombres == {"Ramos 2"}  # el backup de agosto ya tenía las dos, el de julio solo la primera


def test_restaurar_backup_sin_carpeta_archivos_en_el_backup_no_falla(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    generar_backup(conn, momento=datetime(2026, 8, 15, 10, 30))  # sin CarpetaBaseArchivos configurada

    db_nueva = tmp_path / "maquina_nueva" / "espacio_ramos.db"
    restaurar_backup(tmp_path / "backups", db_nueva)
    assert db_nueva.is_file()


# ------------------------------------------------------------------ backup_vencido (3.28)

def test_backup_vencido_sin_carpeta_configurada_es_false(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, FrecuenciaBackupDrive="Diario")
    assert backup_vencido(conn, date(2026, 8, 15)) is False


def test_backup_vencido_sin_frecuencia_configurada_es_false(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    assert backup_vencido(conn, date(2026, 8, 15)) is False


def test_backup_vencido_frecuencia_desconocida_es_false(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    obtener_repositorio(conn, "Configuracion").actualizar(1, FrecuenciaBackupDrive="Bimestral")
    assert backup_vencido(conn, date(2026, 8, 15)) is False


def test_backup_vencido_sin_ningun_backup_generado_es_true(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    obtener_repositorio(conn, "Configuracion").actualizar(1, FrecuenciaBackupDrive="Semanal")
    assert backup_vencido(conn, date(2026, 8, 15)) is True


def test_backup_vencido_dentro_de_la_frecuencia_es_false(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    obtener_repositorio(conn, "Configuracion").actualizar(1, FrecuenciaBackupDrive="Semanal")
    generar_backup(conn, momento=datetime(2026, 8, 10, 9, 0))
    assert backup_vencido(conn, date(2026, 8, 15)) is False  # 5 días, semanal = 7


def test_backup_vencido_fuera_de_la_frecuencia_es_true(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    obtener_repositorio(conn, "Configuracion").actualizar(1, FrecuenciaBackupDrive="Diario")
    generar_backup(conn, momento=datetime(2026, 8, 10, 9, 0))
    assert backup_vencido(conn, date(2026, 8, 15)) is True  # 5 días, diario = 1


def test_backup_vencido_usa_el_backup_mas_reciente(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    obtener_repositorio(conn, "Configuracion").actualizar(1, FrecuenciaBackupDrive="Semanal")
    generar_backup(conn, momento=datetime(2026, 7, 1, 9, 0))
    generar_backup(conn, momento=datetime(2026, 8, 14, 9, 0))
    assert backup_vencido(conn, date(2026, 8, 15)) is False  # 1 día desde el más reciente


# ------------------------------------------------------------- ultimo_backup (Panel de control)

def test_ultimo_backup_sin_carpeta_configurada_es_none(conn):
    assert ultimo_backup(conn) is None


def test_ultimo_backup_sin_ningun_backup_generado_es_none(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    assert ultimo_backup(conn) is None


def test_ultimo_backup_devuelve_fecha_y_hora_del_mas_reciente(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    generar_backup(conn, momento=datetime(2026, 7, 1, 9, 0))
    generar_backup(conn, momento=datetime(2026, 8, 14, 16, 45))
    assert ultimo_backup(conn) == datetime(2026, 8, 14, 16, 45)


def test_backup_vencido_frecuencia_no_distingue_mayusculas(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    obtener_repositorio(conn, "Configuracion").actualizar(1, FrecuenciaBackupDrive="  diario  ")
    generar_backup(conn, momento=datetime(2026, 8, 10, 9, 0))
    assert backup_vencido(conn, date(2026, 8, 15)) is True


# ------------------------------------------ detección de base desactualizada

def _ultimo_backup_propio(conn) -> str | None:
    return conn.execute(
        "SELECT UltimoBackupPropio FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()["UltimoBackupPropio"]


def test_generar_backup_actualiza_ultimo_backup_propio(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    generar_backup(conn, momento=datetime(2026, 8, 15, 10, 30))
    assert _ultimo_backup_propio(conn) == datetime(2026, 8, 15, 10, 30).isoformat()


def test_generar_backup_en_modo_sin_sincronizar_falla_y_no_crea_nada(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    db_path = Path(conn.execute("PRAGMA database_list").fetchone()["file"])
    activar_modo_sin_sincronizar(db_path)

    with pytest.raises(ValueError, match="modo local"):
        generar_backup(conn, momento=datetime(2026, 8, 15, 10, 30))

    assert not (tmp_path / "backups").exists()


def test_restaurar_backup_hereda_el_timestamp_del_backup_restaurado(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    generar_backup(conn, momento=datetime(2026, 7, 1, 9, 0))
    obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2")
    generar_backup(conn, momento=datetime(2026, 8, 15, 10, 30))

    db_nueva = tmp_path / "maquina_nueva" / "espacio_ramos.db"
    restaurar_backup(tmp_path / "backups", db_nueva)

    restaurada = sqlite3.connect(db_nueva)
    restaurada.row_factory = sqlite3.Row
    valor = restaurada.execute(
        "SELECT UltimoBackupPropio FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()["UltimoBackupPropio"]
    restaurada.close()
    assert valor == datetime(2026, 8, 15, 10, 30).isoformat()


def test_restaurar_backup_desactiva_el_modo_sin_sincronizar(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    generar_backup(conn, momento=datetime(2026, 8, 15, 10, 30))

    db_nueva = tmp_path / "maquina_vieja" / "espacio_ramos.db"
    db_nueva.parent.mkdir(parents=True)
    db_nueva.touch()
    activar_modo_sin_sincronizar(db_nueva)
    assert modo_sin_sincronizar_activo(db_nueva) is True

    restaurar_backup(tmp_path / "backups", db_nueva)
    assert modo_sin_sincronizar_activo(db_nueva) is False


def test_modo_sin_sincronizar_activar_y_desactivar(tmp_path):
    db_path = tmp_path / "espacio_ramos.db"
    assert modo_sin_sincronizar_activo(db_path) is False
    activar_modo_sin_sincronizar(db_path)
    assert modo_sin_sincronizar_activo(db_path) is True
    desactivar_modo_sin_sincronizar(db_path)
    assert modo_sin_sincronizar_activo(db_path) is False


def test_desactivar_modo_sin_sincronizar_sin_estar_activo_no_falla(tmp_path):
    desactivar_modo_sin_sincronizar(tmp_path / "espacio_ramos.db")  # no debe tirar ningún error


def test_hay_backup_mas_reciente_sin_sincronizar_sin_carpeta_configurada(conn):
    assert hay_backup_mas_reciente_sin_sincronizar(conn) is None


def test_hay_backup_mas_reciente_sin_sincronizar_sin_ningun_backup(conn, tmp_path):
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    assert hay_backup_mas_reciente_sin_sincronizar(conn) is None


def test_hay_backup_mas_reciente_sin_sincronizar_con_mi_propio_ultimo_backup_no_alerta(conn, tmp_path):
    """El caso normal de la máquina de uso diario: generar mi propio
    backup nunca puede quedar "más nuevo que yo misma"."""
    _configurar_carpeta_backup(conn, tmp_path / "backups")
    generar_backup(conn, momento=datetime(2026, 8, 15, 10, 30))
    assert hay_backup_mas_reciente_sin_sincronizar(conn) is None


def test_hay_backup_mas_reciente_sin_sincronizar_detecta_backup_de_otra_instalacion(conn, tmp_path):
    """Simula la máquina vieja: su propio UltimoBackupPropio quedó atrás
    de un backup que otra instalación generó y que Drive ya sincronizó
    a esta carpeta."""
    carpeta = tmp_path / "backups"
    _configurar_carpeta_backup(conn, carpeta)
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, UltimoBackupPropio=datetime(2026, 7, 1, 9, 0).isoformat(),
    )
    (carpeta / "Backup 2026-08-20 09h00").mkdir(parents=True)

    mas_nuevo = hay_backup_mas_reciente_sin_sincronizar(conn)
    assert mas_nuevo is not None
    assert mas_nuevo.name == "Backup 2026-08-20 09h00"


def test_hay_backup_mas_reciente_sin_sincronizar_no_alerta_si_es_anterior_o_igual(conn, tmp_path):
    carpeta = tmp_path / "backups"
    _configurar_carpeta_backup(conn, carpeta)
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, UltimoBackupPropio=datetime(2026, 8, 20, 9, 0).isoformat(),
    )
    (carpeta / "Backup 2026-07-01 09h00").mkdir(parents=True)
    assert hay_backup_mas_reciente_sin_sincronizar(conn) is None

    # Exactamente el mismo backup que ya genera/restauró esta base (caso
    # típico apenas después de restaurar): tampoco alerta.
    obtener_repositorio(conn, "Configuracion").actualizar(
        1, UltimoBackupPropio=datetime(2026, 8, 20, 9, 0).isoformat(),
    )
    (carpeta / "Backup 2026-08-20 09h00").mkdir(parents=True)
    assert hay_backup_mas_reciente_sin_sincronizar(conn) is None


def test_hay_backup_mas_reciente_sin_sincronizar_sin_ultimo_backup_propio_registrado(conn, tmp_path):
    """Una base sin ningún UltimoBackupPropio todavía (no debería pasar
    en la práctica, ver la migración que lo inicializa, pero el chequeo
    tiene que ser robusto igual) trata cualquier backup existente como
    más nuevo."""
    carpeta = tmp_path / "backups"
    _configurar_carpeta_backup(conn, carpeta)
    obtener_repositorio(conn, "Configuracion").actualizar(1, UltimoBackupPropio=None)
    (carpeta / "Backup 2026-08-20 09h00").mkdir(parents=True)
    assert hay_backup_mas_reciente_sin_sincronizar(conn) is not None
