"""Punto de entrada de la interfaz gráfica (Etapa 8+: ensamblado de GUI)."""
import sqlite3
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.db.connection import DB_PATH_DEFAULT
from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.gui.dialogos_seguridad import DialogoLogin, MonitorInactividad
from app.gui.main_window import Seccion, VentanaPrincipal
from app.gui.pantallas.archivos_y_listas import PantallaArchivosYListas
from app.gui.pantallas.balance import PantallaBalanceDelNegocio
from app.gui.pantallas.base_datos_espacio import PantallaBaseDatosEspacio
from app.gui.pantallas.configuracion import ConfiguracionGeneral
from app.gui.pantallas.disponibilidad import PantallaDisponibilidad
from app.gui.pantallas.estadisticas import PantallaEstadisticas
from app.gui.pantallas.grilla_y_mensajeria import PantallaGrillaYMensajeria
from app.gui.pantallas.liquidacion import ProcesoLiquidacion
from app.gui.pantallas.llaves_y_otros_conceptos import PantallaLlavesYOtrosConceptos
from app.gui.pantallas.novedades import PantallaRegistroAusencias
from app.gui.pantallas.pagos import PantallaPagos
from app.gui.pantallas.panel_control import PanelControl
from app.gui.pantallas.placas_para_timbres import PantallaPlacasParaTimbres
from app.gui.pantallas.profesionales import PantallaProfesionales
from app.gui.pantallas.reservas import PantallaReservas
from app.gui.pantallas.usuarios import PantallaUsuarios
from app.gui.pantallas.valores import PantallaValores
from app.negocio.backup import restaurar_backup
from app.negocio.instancia_unica import BloqueoInstanciaUnica, InstanciaYaAbierta
from app.negocio.seguridad import asegurar_permisos_pantalla


def construir_secciones(usuario: sqlite3.Row | None = None) -> list[Seccion]:
    # Se arma como lista mutable (en vez de un literal) porque la sección
    # "Archivos y listas" necesita la lista completa para poder armar el
    # manual de usuario (junta la ayuda de todas las demás, vía el botón
    # "Manual del usuario" de su solapa Gestor de archivos del espacio) —
    # su fábrica captura `secciones` por referencia y para cuando de
    # verdad se llama (al construir VentanaPrincipal) la lista ya está
    # completa.
    #
    # `usuario` (Seguridad): el usuario ya logueado (`gui_main.main` hace
    # el login antes de armar esta lista) — solo lo necesita "Usuarios y
    # permisos", para poder registrar quién resetea una contraseña ajena.
    # `None` (el default que usan los tests que llaman esta función sin
    # loguearse) deja esa pantalla sin ese dato, ver `PantallaUsuarios`.
    secciones: list[Seccion] = []

    # Categorías finales del reordenamiento de formularios (Excel de la
    # clienta): "Principal"/"Catálogos"/"Configuración" pasan a solo dos,
    # "Sistema"/"Operativa diaria" — como `VentanaPrincipal` arma un
    # separador cada vez que la categoría cambia respecto de la sección
    # anterior (no agrupa por nombre repetido en toda la lista), las
    # cinco de "Sistema" van todas juntas primero y las doce de
    # "Operativa diaria" después; dentro de cada bloque se conservó el
    # orden relativo que ya tenían entre sí (no hay un orden pedido por
    # la clienta para esto, es criterio propio).
    secciones.extend([
        Seccion(
            "Panel de control", lambda conn: PanelControl(conn), categoria="Sistema",
            ayuda="Solapa Avance de período y backups: resumen del estado actual del espacio (ocupación, "
            "próximos vencimientos y alertas), generación de backup manual y avance de mes. Solapa "
            "Importación datos desde Excel: importación masiva inicial de datos desde una planilla Excel.",
        ),
        Seccion(
            "Archivos y listas", lambda conn: PantallaArchivosYListas(conn, secciones), categoria="Sistema",
            ayuda="Solapa Gestor de archivos del espacio: fotos y documentos de edificios, unidades y "
            "consultorios usados en Propuesta/Disponibilidad/Liquidación/Oferta, más el botón "
            "\"Manual del usuario\" para regenerarlo contra el estado actual del sistema. Solapas "
            "Listas editables, Condiciones y normas y Detalles complementarios de la propuesta: "
            "listas y textos de referencia usados por otras pantallas y por el PDF de Propuesta.",
        ),
        Seccion(
            "Base datos del espacio", lambda conn: PantallaBaseDatosEspacio(conn), categoria="Sistema",
            ayuda="Localidades, Edificios, Unidades, Consultorios y Responsables — la estructura "
            "física y de contacto del espacio, en el orden de la cadena de referencias entre ellos.",
        ),
        Seccion(
            "Configuración general", lambda conn: ConfiguracionGeneral(conn), categoria="Sistema",
            ayuda="Datos generales del espacio (nombre, logo), carpeta base de archivos, carpeta de "
            "backup, modo de fecha ficticia para pruebas y las franjas horarias bloqueadas de forma "
            "fija (solapa Bloques rígidos).",
        ),
        Seccion(
            "Usuarios y permisos",
            lambda conn: PantallaUsuarios(conn, usuario["IdUsuario"] if usuario else None),
            categoria="Sistema",
            ayuda="Alta y baja de usuarios del sistema, nivel de acceso de cada uno, reseteo de "
            "contraseña, historial de cambios de contraseña, y qué nivel mínimo requiere cada "
            "pantalla del menú.",
        ),
        Seccion(
            "Grilla y mensajería", lambda conn: PantallaGrillaYMensajeria(conn), categoria="Operativa diaria",
            ayuda="Solapa Grilla semanal: grilla filtrable por localidad/edificio/unidad/día/profesional, "
            "con período propio y dos modos de visualización (reservas regulares o aisladas), más "
            "referencias de colores. Solapa Centro de mensajería: arma los mensajes de WhatsApp "
            "predefinidos (individuales o grupales) para las distintas situaciones habituales de "
            "comunicación con los profesionales. Solapa Mensajes predefinidos: plantillas de mensaje "
            "propias, editables.",
        ),
        Seccion(
            "Reservas", lambda conn: PantallaReservas(conn), categoria="Operativa diaria",
            ayuda="Alta, edición y baja de reservas (regulares y aisladas) por profesional, consultorio y franja.",
        ),
        Seccion(
            "Liquidaciones", lambda conn: ProcesoLiquidacion(conn), categoria="Operativa diaria",
            ayuda="Solapas Emisión de archivos/Estado de cuenta: genera la liquidación PDF de cada "
            "profesional para el período seleccionado, con descuentos por feriados/licencias/"
            "vacaciones ya aplicados, y el estado de cuenta con su historial de liquidaciones "
            "emitidas. Solapa Feriados y fechas especiales: catálogo de feriados y días no "
            "laborables, cargados a mano.",
        ),
        Seccion(
            "Llaves y otros conceptos", lambda conn: PantallaLlavesYOtrosConceptos(conn), categoria="Operativa diaria",
            ayuda="Solapa Movimientos y tenencias de llaves: entrega y devolución de llaves con depósito, "
            "y definición de a qué edificio/unidad da acceso cada llave. Solapas Registro de cargos "
            "especiales/Estado de cuenta: cargos extraordinarios (ajustes puntuales) que se suman a la "
            "liquidación de un profesional, y su historial.",
        ),
        Seccion(
            "Placas para timbres", lambda conn: PantallaPlacasParaTimbres(conn), categoria="Operativa diaria",
            ayuda="Solapa Búsqueda y asignación de placas: qué profesional tiene placa en qué posición "
            "del tablero de cada unidad, filtrable por localidad/edificio/unidad/profesional. Solapa "
            "Impresión de placas en papel: arma una selección puntual de profesionales y genera la hoja "
            "para cortar e imprimir. Solapa Placas: catálogo del tablero de posiciones/nombre grabado.",
        ),
        Seccion(
            "Disponibilidad", lambda conn: PantallaDisponibilidad(conn), categoria="Operativa diaria",
            ayuda="Solapa Oferta de consultorios: búsqueda de horarios libres que cumplen criterios "
            "combinados (franjas, días, consultorio) para armar una oferta en PDF a un profesional "
            "interesado. Solapa Lista de espera: profesionales interesados en un horario que hoy está "
            "ocupado — el sistema avisa automáticamente cuando ese horario se libera. Solapa Archivos "
            "para enviar: regenerar a demanda los documentos que ya se generan solos en el avance de "
            "mes (Propuesta, Disponibilidad).",
        ),
        Seccion(
            "Registro de ausencias", lambda conn: PantallaRegistroAusencias(conn), categoria="Operativa diaria",
            ayuda="Solapas Vacaciones/Licencias/Ausencias por motivos varios: plazos por inactividad de un "
            "profesional cargados manualmente, con su vista previa de la grilla operativa. Solapa Tipos "
            "de licencia: catálogo de tipos de licencia disponibles para cargarle a un profesional.",
        ),
        Seccion(
            "Pagos", lambda conn: PantallaPagos(conn), categoria="Operativa diaria",
            ayuda="Registro de pagos recibidos, planes de pago con refinanciación e interés por saldos "
            "atrasados, y estado de cuenta del profesional.",
        ),
        Seccion(
            "Estadísticas", lambda conn: PantallaEstadisticas(conn), categoria="Operativa diaria",
            ayuda="Indicadores generales del espacio: ocupación, ingresos y otras métricas agregadas.",
        ),
        Seccion(
            "Valores", lambda conn: PantallaValores(conn), categoria="Operativa diaria",
            ayuda="Solapa Valores vigentes: valor hora regular/aislada de cada consultorio, filtrable, "
            "con resumen de promedios. Solapas Aumentos/Esquema de descuentos: simula el impacto de un "
            "aumento de valores antes de confirmarlo (y lo aplica a todos los valores correspondientes), "
            "y define los tramos del esquema de descuentos por horas semanales.",
        ),
        Seccion(
            "Profesionales", lambda conn: PantallaProfesionales(conn), categoria="Operativa diaria",
            ayuda="Solapa Listado de profesionales: alta, baja y edición de profesionales, con su "
            "categoría, código y la documentación adjunta de cada uno. Solapa Profesiones y "
            "tratamientos: catálogo de profesiones disponibles para asignarle a un profesional.",
        ),
        Seccion(
            "Balance del negocio", lambda conn: PantallaBalanceDelNegocio(conn), categoria="Operativa diaria",
            ayuda="Solapa Gastos: gastos operativos del espacio, usados en los cálculos de estadísticas. "
            "Solapa Ingresos: ingresos por horas regulares/aisladas/feriados trabajados de un período. "
            "Solapa Resultado: ingresos menos gastos del período, para el mismo alcance de ubicación.",
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

    # Seguridad (ver CLAUDE.md): login obligatorio antes de mostrar la
    # ventana principal — con la base recién creada, sin ningún usuario
    # todavía, el diálogo pide de alta el primer Administrador en vez de
    # un login que nadie podría pasar (ver DialogoLogin.hay_usuarios).
    dialogo_login = DialogoLogin(conn)
    if dialogo_login.exec() != DialogoLogin.DialogCode.Accepted:
        bloqueo.liberar()
        sys.exit(0)
    usuario = dialogo_login.usuario

    secciones = construir_secciones(usuario)
    # "Configuración general" y "Usuarios y permisos" nacen directo en
    # Administrador (pedido explícito de la clienta) — no visibles para
    # cualquiera hasta que alguien las suba a mano, a diferencia del
    # resto de las pantallas nuevas del sistema.
    asegurar_permisos_pantalla(
        conn, [s.nombre for s in secciones],
        nombres_nivel_alto=frozenset({"Configuración general", "Usuarios y permisos"}),
    )

    ventana = VentanaPrincipal(conn, secciones, id_nivel_usuario=usuario["IdNivelAcceso"])
    ventana.show()

    # Bloqueo por inactividad: se instala sobre la QApplication entera
    # (cualquier click/tecla en cualquier pantalla la reinicia), así que
    # una referencia local alcanza — vive mientras dure `app.exec()`.
    monitor_inactividad = MonitorInactividad(conn, ventana, usuario)
    app.installEventFilter(monitor_inactividad)

    codigo_salida = app.exec()
    bloqueo.liberar()
    sys.exit(codigo_salida)


if __name__ == "__main__":
    main()
