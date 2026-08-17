import sys
from pathlib import Path

from app.db.connection import get_connection


def test_get_connection_crea_directorio_padre(tmp_path):
    db_path = tmp_path / "subcarpeta" / "espacio_ramos.db"
    conn = get_connection(db_path)
    try:
        assert db_path.parent.is_dir()
    finally:
        conn.close()


def test_db_path_default_no_depende_de_meipass_cuando_esta_empaquetado(monkeypatch):
    """Empaquetado con PyInstaller, __file__ de los módulos bundleados
    apunta adentro de la carpeta temporal de extracción (_MEIPASS, se
    borra al cerrar) — la base de datos default tiene que calcularse a
    partir de sys.executable, no de __file__, para no vivir ahí."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/ruta/simulada/EspacioRamos.exe")

    import importlib

    import app.db.connection as connection
    importlib.reload(connection)
    try:
        assert connection.DB_PATH_DEFAULT == Path("/ruta/simulada") / "data" / "espacio_ramos.db"
    finally:
        monkeypatch.undo()
        importlib.reload(connection)
