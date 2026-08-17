import sqlite3
from datetime import datetime

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.backup import buscar_backup_mas_reciente, carpeta_backup, generar_backup, restaurar_backup
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
