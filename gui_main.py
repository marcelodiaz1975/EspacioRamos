"""Punto de entrada de la interfaz gráfica (Etapa 8+: ensamblado de GUI)."""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.db.connection import DB_PATH_DEFAULT
from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.main_window import Seccion, VentanaPrincipal
from app.gui.pantallas import catalogos
from app.gui.pantallas.archivos_varios import PantallaArchivosVarios
from app.gui.pantallas.aumentos import PantallaAumentos
from app.gui.pantallas.bloques_rigidos import PantallaBloquesRigidos
from app.gui.pantallas.configuracion import ConfiguracionGeneral
from app.gui.pantallas.estadisticas import PantallaEstadisticas
from app.gui.pantallas.estado_cuenta import PantallaEstadoCuenta
from app.gui.pantallas.grilla import GrillaDisponibilidad
from app.gui.pantallas.imagenes import PantallaImagenes
from app.gui.pantallas.importacion import PantallaImportacion
from app.gui.pantallas.liquidacion import ProcesoLiquidacion
from app.gui.pantallas.lista_espera import PantallaListaEspera
from app.gui.pantallas.llaves import PantallaLlaves
from app.gui.pantallas.mensajeria import CentroMensajeria
from app.gui.pantallas.novedades import PantallaNovedades
from app.gui.pantallas.oferta import PantallaOferta
from app.gui.pantallas.pagos import PantallaPagos
from app.gui.pantallas.panel_control import PanelControl
from app.gui.pantallas.profesionales import pantalla_profesionales
from app.gui.pantallas.reservas import PantallaReservas


def construir_secciones() -> list[Seccion]:
    return [
        Seccion("Panel de control", lambda conn: PanelControl(conn), categoria="Principal"),
        Seccion("Disponibilidad operativa", lambda conn: GrillaDisponibilidad(conn), categoria="Principal"),
        Seccion("Reservas", lambda conn: PantallaReservas(conn), categoria="Principal"),
        Seccion("Liquidación mensual", lambda conn: ProcesoLiquidacion(conn), categoria="Principal"),
        Seccion("Centro de mensajería", lambda conn: CentroMensajeria(conn), categoria="Principal"),
        Seccion("Llaves", lambda conn: PantallaLlaves(conn), categoria="Principal"),
        Seccion("Lista de espera", lambda conn: PantallaListaEspera(conn), categoria="Principal"),
        Seccion("Oferta de consultorios", lambda conn: PantallaOferta(conn), categoria="Principal"),
        Seccion("Archivos varios", lambda conn: PantallaArchivosVarios(conn), categoria="Principal"),
        Seccion("Novedades", lambda conn: PantallaNovedades(conn), categoria="Principal"),
        Seccion("Pagos", lambda conn: PantallaPagos(conn), categoria="Principal"),
        Seccion("Estado de cuenta", lambda conn: PantallaEstadoCuenta(conn), categoria="Principal"),
        Seccion("Estadísticas", lambda conn: PantallaEstadisticas(conn), categoria="Principal"),
        Seccion("Análisis de aumentos", lambda conn: PantallaAumentos(conn), categoria="Principal"),
        Seccion("Profesionales", pantalla_profesionales, categoria="Catálogos"),
        Seccion("Edificios", catalogos.pantalla_edificios, categoria="Catálogos"),
        Seccion("Unidades", catalogos.pantalla_unidades, categoria="Catálogos"),
        Seccion("Consultorios", catalogos.pantalla_consultorios, categoria="Catálogos"),
        Seccion("Imágenes", lambda conn: PantallaImagenes(conn), categoria="Catálogos"),
        Seccion("Responsables", catalogos.pantalla_responsables, categoria="Catálogos"),
        Seccion("Tipos de licencia", catalogos.pantalla_tipos_licencia, categoria="Catálogos"),
        Seccion("Listas editables", catalogos.pantalla_listas_editables, categoria="Catálogos"),
        Seccion("Condiciones y normas", catalogos.pantalla_condiciones_normas, categoria="Catálogos"),
        Seccion(
            "Detalles complementarios (Propuesta)",
            catalogos.pantalla_detalles_complementarios_propuesta,
            categoria="Catálogos",
        ),
        Seccion("Mensajes predefinidos", catalogos.pantalla_mensajes_predefinidos, categoria="Catálogos"),
        Seccion("Profesiones", catalogos.pantalla_profesiones, categoria="Catálogos"),
        Seccion("Gastos operativos", catalogos.pantalla_gastos_operativos, categoria="Catálogos"),
        Seccion("Placas", catalogos.pantalla_placas, categoria="Catálogos"),
        Seccion("Fechas especiales", catalogos.pantalla_fechas_especiales, categoria="Catálogos"),
        Seccion("Esquema de descuentos", catalogos.pantalla_esquema_descuentos, categoria="Catálogos"),
        Seccion("Bloques rígidos", lambda conn: PantallaBloquesRigidos(conn), categoria="Catálogos"),
        Seccion("Configuración general", lambda conn: ConfiguracionGeneral(conn), categoria="Configuración"),
        Seccion("Importar planilla", lambda conn: PantallaImportacion(conn), categoria="Configuración"),
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
