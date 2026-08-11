"""Punto de entrada de la interfaz gráfica (Etapa 8+: ensamblado de GUI)."""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.db.connection import DB_PATH_DEFAULT
from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.main_window import Seccion, VentanaPrincipal
from app.gui.pantallas import catalogos
from app.gui.pantallas.grilla import GrillaDisponibilidad
from app.gui.pantallas.panel_control import PanelControl


def construir_secciones() -> list[Seccion]:
    return [
        Seccion("Panel de control", lambda conn: PanelControl(conn), categoria="Principal"),
        Seccion("Disponibilidad operativa", lambda conn: GrillaDisponibilidad(conn), categoria="Principal"),
        Seccion("Edificios", catalogos.pantalla_edificios, categoria="Catálogos"),
        Seccion("Unidades", catalogos.pantalla_unidades, categoria="Catálogos"),
        Seccion("Consultorios", catalogos.pantalla_consultorios, categoria="Catálogos"),
        Seccion("Responsables", catalogos.pantalla_responsables, categoria="Catálogos"),
        Seccion("Tipos de licencia", catalogos.pantalla_tipos_licencia, categoria="Catálogos"),
        Seccion("Listas editables", catalogos.pantalla_listas_editables, categoria="Catálogos"),
        Seccion("Condiciones y normas", catalogos.pantalla_condiciones_normas, categoria="Catálogos"),
        Seccion("Mensajes predefinidos", catalogos.pantalla_mensajes_predefinidos, categoria="Catálogos"),
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
