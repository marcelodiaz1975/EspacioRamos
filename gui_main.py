"""Punto de entrada de la interfaz gráfica (Etapa 8+: ensamblado de GUI)."""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

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
from app.gui.pantallas.grilla_operativa import PantallaGrillaOperativa
from app.gui.pantallas.imagenes import PantallaImagenes
from app.gui.pantallas.importacion import PantallaImportacion
from app.gui.pantallas.liquidacion import ProcesoLiquidacion
from app.gui.pantallas.lista_espera import PantallaListaEspera
from app.gui.pantallas.llaves import PantallaLlaves
from app.gui.pantallas.mensajeria import CentroMensajeria
from app.gui.pantallas.mensajes_predefinidos import pantalla_mensajes_predefinidos
from app.gui.pantallas.novedades import PantallaNovedades
from app.gui.pantallas.oferta import PantallaOferta
from app.gui.pantallas.pagos import PantallaPagos
from app.gui.pantallas.panel_control import PanelControl
from app.gui.pantallas.profesionales import pantalla_profesionales
from app.gui.pantallas.reservas import PantallaReservas
from app.negocio.backup import restaurar_backup
from app.negocio.instancia_unica import BloqueoInstanciaUnica, InstanciaYaAbierta


def construir_secciones() -> list[Seccion]:
    # Se arma como lista mutable (en vez de un literal) porque la sección
    # "Archivos varios" necesita la lista completa para poder armar el
    # manual de usuario (junta la ayuda de todas las demás) — su fábrica
    # captura `secciones` por referencia y para cuando de verdad se llama
    # (al construir VentanaPrincipal) la lista ya está completa.
    secciones: list[Seccion] = []

    secciones.extend([
        Seccion(
            "Panel de control", lambda conn: PanelControl(conn), categoria="Principal",
            ayuda="Resumen del estado actual del espacio: ocupación, próximos vencimientos y alertas.",
        ),
        Seccion(
            "Disponibilidad operativa", lambda conn: GrillaDisponibilidad(conn), categoria="Principal",
            ayuda="Grilla de disponibilidad de todos los consultorios, día por franja horaria. "
            "Desde acá también se cargan reservas haciendo clic en una celda libre.",
        ),
        Seccion(
            "Reservas", lambda conn: PantallaReservas(conn), categoria="Principal",
            ayuda="Alta, edición y baja de reservas (regulares y aisladas) por profesional, consultorio y franja.",
        ),
        Seccion(
            "Grilla operativa", lambda conn: PantallaGrillaOperativa(conn), categoria="Principal",
            ayuda="Grilla filtrable por localidad/edificio/unidad/día/profesional, con período y rango de "
            "fechas propios y dos modos de visualización (reservas regulares o aisladas). Al hacer clic en "
            "una celda se muestra el detalle de esa hora.",
        ),
        Seccion(
            "Liquidación mensual", lambda conn: ProcesoLiquidacion(conn), categoria="Principal",
            ayuda="Genera la liquidación PDF de cada profesional para el período seleccionado, con "
            "descuentos por feriados/licencias/vacaciones ya aplicados.",
        ),
        Seccion(
            "Centro de mensajería", lambda conn: CentroMensajeria(conn), categoria="Principal",
            ayuda="Arma los mensajes de WhatsApp predefinidos (individuales o grupales) para las "
            "distintas situaciones habituales de comunicación con los profesionales.",
        ),
        Seccion(
            "Llaves", lambda conn: PantallaLlaves(conn), categoria="Principal",
            ayuda="Entrega y devolución de llaves con depósito, y definición de a qué edificio/unidad "
            "da acceso cada llave (panel Accesos).",
        ),
        Seccion(
            "Lista de espera", lambda conn: PantallaListaEspera(conn), categoria="Principal",
            ayuda="Profesionales interesados en un horario que hoy está ocupado — el sistema avisa "
            "automáticamente cuando ese horario se libera.",
        ),
        Seccion(
            "Oferta de consultorios", lambda conn: PantallaOferta(conn), categoria="Principal",
            ayuda="Búsqueda de horarios libres que cumplen criterios combinados (franjas, días, "
            "consultorio) para armar una oferta en PDF a un profesional interesado.",
        ),
        Seccion(
            "Archivos varios", lambda conn: PantallaArchivosVarios(conn, secciones), categoria="Principal",
            ayuda="Regenerar a demanda los documentos que ya se generan solos en el avance de mes "
            "(Propuesta, Disponibilidad, Placas) y el manual de usuario.",
        ),
        Seccion(
            "Novedades", lambda conn: PantallaNovedades(conn), categoria="Principal",
            ayuda="Registro de novedades/incidentes cargados manualmente sobre profesionales o unidades.",
        ),
        Seccion(
            "Pagos", lambda conn: PantallaPagos(conn), categoria="Principal",
            ayuda="Registro de pagos recibidos y planes de pago con refinanciación e interés por saldos atrasados.",
        ),
        Seccion(
            "Estado de cuenta", lambda conn: PantallaEstadoCuenta(conn), categoria="Principal",
            ayuda="Historial de liquidaciones y pagos de un profesional, con el saldo acumulado a la fecha.",
        ),
        Seccion(
            "Estadísticas", lambda conn: PantallaEstadisticas(conn), categoria="Principal",
            ayuda="Indicadores generales del espacio: ocupación, ingresos y otras métricas agregadas.",
        ),
        Seccion(
            "Análisis de aumentos", lambda conn: PantallaAumentos(conn), categoria="Principal",
            ayuda="Simula el impacto de un aumento de valores antes de confirmarlo, y aplica el "
            "aumento confirmado a todos los valores correspondientes.",
        ),
        Seccion(
            "Profesionales", pantalla_profesionales, categoria="Catálogos",
            ayuda="Alta, baja y edición de profesionales, con su categoría, código y la "
            "documentación adjunta de cada uno.",
        ),
        Seccion(
            "Edificios", catalogos.pantalla_edificios, categoria="Catálogos",
            ayuda="Alta, baja y edición de los edificios que integran el espacio.",
        ),
        Seccion(
            "Unidades", catalogos.pantalla_unidades, categoria="Catálogos",
            ayuda="Alta, baja y edición de las unidades (departamentos) de cada edificio.",
        ),
        Seccion(
            "Consultorios", catalogos.pantalla_consultorios, categoria="Catálogos",
            ayuda="Alta, baja y edición de los consultorios dentro de cada unidad, con sus valores.",
        ),
        Seccion(
            "Imágenes", lambda conn: PantallaImagenes(conn), categoria="Catálogos",
            ayuda="Carga y ordena las fotos de edificios, unidades y consultorios usadas en Propuesta.",
        ),
        Seccion(
            "Responsables", catalogos.pantalla_responsables, categoria="Catálogos",
            ayuda="Personas de contacto/responsables asociadas a edificios o unidades.",
        ),
        Seccion(
            "Tipos de licencia", catalogos.pantalla_tipos_licencia, categoria="Catálogos",
            ayuda="Catálogo de tipos de licencia disponibles para cargarle a un profesional.",
        ),
        Seccion(
            "Listas editables", catalogos.pantalla_listas_editables, categoria="Catálogos",
            ayuda="Listas de valores editables usadas como opciones en otras pantallas del sistema.",
        ),
        Seccion(
            "Condiciones y normas", catalogos.pantalla_condiciones_normas, categoria="Catálogos",
            ayuda="Texto de condiciones y normas que se incluye en los documentos de Propuesta.",
        ),
        Seccion(
            "Detalles complementarios (Propuesta)",
            catalogos.pantalla_detalles_complementarios_propuesta,
            categoria="Catálogos",
            ayuda="Datos adicionales por consultorio que se muestran en el PDF de Propuesta.",
        ),
        Seccion(
            "Mensajes predefinidos", pantalla_mensajes_predefinidos, categoria="Catálogos",
            ayuda="Plantillas de mensaje usadas por el Centro de mensajería para cada situación.",
        ),
        Seccion(
            "Profesiones", catalogos.pantalla_profesiones, categoria="Catálogos",
            ayuda="Catálogo de profesiones disponibles para asignarle a un profesional.",
        ),
        Seccion(
            "Gastos operativos", catalogos.pantalla_gastos_operativos, categoria="Catálogos",
            ayuda="Gastos operativos del espacio, usados en los cálculos de estadísticas.",
        ),
        Seccion(
            "Placas", catalogos.pantalla_placas, categoria="Catálogos",
            ayuda="Placas del tablero de cada unidad: posición y nombre grabado, activas o no.",
        ),
        Seccion(
            "Fechas especiales", catalogos.pantalla_fechas_especiales, categoria="Catálogos",
            ayuda="Feriados y fechas especiales, cargados a mano — el sistema no los importa de "
            "ningún sitio externo, para poder darle a cada fecha el tratamiento que corresponda.",
        ),
        Seccion(
            "Esquema de descuentos", catalogos.pantalla_esquema_descuentos, categoria="Catálogos",
            ayuda="Porcentajes de descuento aplicados por cada tipo de licencia/feriado en la liquidación.",
        ),
        Seccion(
            "Bloques rígidos", lambda conn: PantallaBloquesRigidos(conn), categoria="Catálogos",
            ayuda="Franjas horarias que quedan bloqueadas de forma fija, sin poder reservarse.",
        ),
        Seccion(
            "Configuración general", lambda conn: ConfiguracionGeneral(conn), categoria="Configuración",
            ayuda="Datos generales del espacio (nombre, logo), carpeta base de archivos, carpeta de "
            "backup y modo de fecha ficticia para pruebas.",
        ),
        Seccion(
            "Importar planilla", lambda conn: PantallaImportacion(conn), categoria="Configuración",
            ayuda="Importación masiva inicial de datos desde una planilla Excel.",
        ),
    ])
    return secciones


def _ofrecer_restaurar_backup(db_path: Path) -> None:
    """Instalación en máquina nueva (sección 2): si no hay base de datos
    todavía, ofrece restaurar el último backup desde una carpeta de
    Google Drive que el operador ya tenga sincronizada en esta máquina
    (ver app.negocio.backup — el backup en sí ya asume esa carpeta, acá
    solo se recorre en sentido inverso)."""
    respuesta = QMessageBox.question(
        None, "Sistema Espacio Ramos",
        "No se encontró una base de datos en esta máquina.\n\n"
        "¿Querés restaurar el último backup desde una carpeta de Google Drive ya sincronizada acá?",
    )
    if respuesta != QMessageBox.StandardButton.Yes:
        return
    carpeta = QFileDialog.getExistingDirectory(None, "Elegir la carpeta de backups de Google Drive")
    if not carpeta:
        return
    try:
        origen = restaurar_backup(Path(carpeta), db_path)
    except ValueError as error:
        QMessageBox.warning(None, "Restaurar backup", str(error))
        return
    QMessageBox.information(None, "Restaurar backup", f"Se restauró: {origen.name}")


def main() -> None:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_PATH_DEFAULT

    app = QApplication(sys.argv)

    if not db_path.exists():
        _ofrecer_restaurar_backup(db_path)

    bloqueo = BloqueoInstanciaUnica(db_path)
    try:
        bloqueo.adquirir()
    except InstanciaYaAbierta as error:
        QMessageBox.critical(None, "Sistema Espacio Ramos", str(error))
        sys.exit(1)

    conn = init_database(db_path)
    sembrar_valores_por_defecto(conn)

    ventana = VentanaPrincipal(conn, construir_secciones())
    ventana.show()
    codigo_salida = app.exec()
    bloqueo.liberar()
    sys.exit(codigo_salida)


if __name__ == "__main__":
    main()
