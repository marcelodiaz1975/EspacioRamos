import sqlite3

from app.db.init_db import init_database
from app.db.migraciones import aplicar_migraciones


def test_base_nueva_ya_tiene_las_columnas_migradas(tmp_path):
    conn = init_database(tmp_path / "test.db")
    columnas = {f["name"] for f in conn.execute("PRAGMA table_info(Ausencia)").fetchall()}
    assert "IdReservaAislada" in columnas
    assert "HoraInicio" in columnas
    assert "HoraFin" in columnas
    conn.close()


def test_aplicar_migraciones_agrega_la_columna_a_una_base_vieja(tmp_path):
    """Simula una base creada antes de que existiera la columna: la crea
    a mano sin ella (como si viniera de un schema.sql viejo) y confirma
    que aplicar_migraciones la agrega sola."""
    db_path = tmp_path / "vieja.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE Ausencia (IdAusencia INTEGER PRIMARY KEY, IdProfesional INTEGER NOT NULL, "
        "IdConsultorio INTEGER, FechaDesde TEXT NOT NULL, FechaHasta TEXT NOT NULL, Motivo TEXT, Observacion TEXT)"
    )
    conn.commit()
    columnas_antes = {f["name"] for f in conn.execute("PRAGMA table_info(Ausencia)").fetchall()}
    assert "IdReservaAislada" not in columnas_antes

    aplicar_migraciones(conn)

    columnas_despues = {f["name"] for f in conn.execute("PRAGMA table_info(Ausencia)").fetchall()}
    assert "IdReservaAislada" in columnas_despues
    conn.close()


def test_aplicar_migraciones_es_idempotente(tmp_path):
    conn = init_database(tmp_path / "test.db")
    aplicar_migraciones(conn)  # segunda vez, no debería fallar ni duplicar la columna
    columnas = [f["name"] for f in conn.execute("PRAGMA table_info(Ausencia)").fetchall()]
    assert columnas.count("IdReservaAislada") == 1
    conn.close()
