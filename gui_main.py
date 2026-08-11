"""Punto de entrada de la interfaz gráfica (Etapa 8+: ensamblado de GUI)."""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.db.connection import DB_PATH_DEFAULT
from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.main_window import Seccion, VentanaPrincipal
from app.gui.pantallas.panel_control import PanelControl


def construir_secciones() -> list[Seccion]:
    return [
        Seccion("Panel de control", lambda conn: PanelControl(conn), categoria="Principal"),
    ]


def main() -> None:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_PATH_DEFAULT
    conn = init_database(db_path)
    sembrar_valores_por_defecto(conn)

    app = QApplication(sys.argv)
    ventana = VentanaPrincipal(conn, construir_secciones())
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
