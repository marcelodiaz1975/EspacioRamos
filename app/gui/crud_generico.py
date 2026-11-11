"""Pantalla CRUD genérica: cubre las pantallas de catálogo simples (Edificios,
Unidades, Consultorios, Responsables, Tipos de licencia, Listas editables,
Condiciones y normas, Mensajes predefinidos) sin escribir una clase por tabla.
Se parametriza con una lista de Campo (columna, etiqueta, tipo de control) y
usa el Repositorio genérico (app/repositorio/base.py) para leer y escribir.

`anidado=True` (reordenamiento de formularios, Excel de la clienta): en vez
de pantalla de catálogo independiente (título Nivel 1 + su propio
`QTabWidget` de una sola pestaña "Listado"), el catálogo se arma como una
solapa desnuda lista para pasarse directo a `addTab(...)` de un formulario
compuesto (ej. "Archivos y listas", "Base datos del espacio") — mismo
criterio `objectName="panelSolapa"` en el widget de más afuera (`self`) que
`_PanelCampos`/`_PanelGestorArchivos`, con el mismo contenido de siempre
(Buscar + Nuevo/Editar/Eliminar + tabla) adentro de un `QScrollArea`
propio."""
from __future__ import annotations

import sqlite3
import unicodedata
import weakref
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtGui import QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.eliminar_tecla import instalar_eliminar_con_tecla
from app.gui.widgets.fecha import aplicar_color_sabado_negro, instalar_flechas_cambian_fecha_completa
from app.gui.widgets.foco import excluir_tabla_del_tab
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.items_tabla import item_centrado
from app.gui.widgets.orden_tabla import OrdenTabla, clave_orden_codigo
from app.gui.widgets.resumen_saldo import item_monto
from app.repositorio.registro import obtener_repositorio

_ID_REGISTRO = Qt.ItemDataRole.UserRole
_ANCHO_CAMPO = 240  # ancho compartido por el panel izquierdo (buscar + botones), mismo criterio que otras pantallas
_PADDING_COLUMNA = 30  # mismo criterio y mismo valor que novedades._ajustar_columnas/llaves._ajustar_columnas
_ANCHO_MINIMO_COLUMNA_FLEXIBLE = 80  # piso de `columna_flexible` — evita que quede en 0/negativo en una ventana angosta
_COLCHON_TITULO_COLUMNA = 12  # padding interno que Qt le suma a la celda del encabezado, ver Campo.ancho_minimo_etiqueta
_LOCALE_ES = QLocale(QLocale.Language.Spanish)
# "lun 07-09-2026" — mismo formato que los campos Desde/Hasta de Registro de
# ausencias (app/gui/pantallas/novedades.py), generalizado acá para
# tipo="fecha" en vez de duplicarlo pantalla por pantalla (pedido de la
# clienta al revisar Fechas especiales).
_FORMATO_FECHA_DIA = "ddd dd-MM-yyyy"
# Sentinel de QDateEdit.setSpecialValueText para "sin fecha" en un
# `Campo(tipo="fecha")` NO obligatorio (ej. Profesionales: Fecha de
# nacimiento) — mismo criterio que `reservas._FECHA_SIN_DATO`/
# `novedades._FECHA_SIN_DATO` (duplicado acá, este módulo no tiene
# relación con esos: sin esto, un `QDateEdit` siempre tiene algún valor
# concreto y un alta nueva sin tocar el campo guardaría "hoy" como si
# fuera un dato real), pero con un valor DISTINTO: año 1900 en vez de
# 2000. `setMinimumDate(_FECHA_SIN_DATO)` deja ese valor como el piso
# del campo — el 2000 que usan Reservas/Novedades (fechas operativas,
# nunca anteriores a la puesta en marcha del sistema) hubiera recortado
# en silencio cualquier fecha de nacimiento real anterior a ese año
# (bug real, encontrado al testear: `QDateEdit.setDate` con un valor
# por debajo del mínimo lo clampea al mínimo sin avisar).
_FECHA_SIN_DATO = QDate(1900, 1, 1)


def _titulo_campo(texto: str) -> QLabel:
    """Jerarquía 3 (subtituloCampo): mismo criterio que el resto de las
    pantallas para los títulos que van arriba de un selector."""
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _sin_acentos(texto: str) -> str:
    """Mismo criterio que `selector_profesional._sin_acentos` (duplicado
    acá, no importado: son dominios sin relación) — saca tildes
    descomponiendo cada letra en base + diacrítico y quedándose con la
    base."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _normalizar_busqueda(texto: str) -> str:
    return _sin_acentos(texto).casefold()


def _fmt_fecha_dia(fecha_iso: str | None, formato: str = _FORMATO_FECHA_DIA) -> str:
    """"lun 07-09-2026" a partir del AAAA-MM-DD guardado — ver
    `_FORMATO_FECHA_DIA`. `formato` deja usar otro patrón distinto del
    default (ej. Profesionales: "dd-MM-yyyy" sin día de semana para
    Fecha de nacimiento/contacto, ver `Campo.formato_fecha`). Si el
    valor no es una fecha válida (no debería pasar, viene siempre de un
    QDateEdit) se muestra tal cual en vez de romper."""
    if not fecha_iso:
        return ""
    fecha_qt = QDate.fromString(fecha_iso, "yyyy-MM-dd")
    return _LOCALE_ES.toString(fecha_qt, formato) if fecha_qt.isValid() else fecha_iso


def _referencia_debil(funcion):
    """Envuelve un callback en una referencia débil (mismo motivo que
    OrdenTabla, ver app/gui/widgets/orden_tabla.py): `al_crear`/
    `al_actualizar`/`al_eliminar` casi siempre son métodos atados de la
    pantalla compuesta dueña de este PantallaCRUD (ej. Llaves), y
    guardarlos fuertes crearía un ciclo pantalla -> PantallaCRUD ->
    pantalla que reventaba el proceso (segfault) si el recolector cíclico
    de Python corría en mal momento contra la destrucción de widgets de
    Qt. Devuelve un resolver de cero argumentos: llamarlo da el callback
    vivo o None si ya se recolectó."""
    if funcion is None:
        return lambda: None
    if hasattr(funcion, "__self__"):
        return weakref.WeakMethod(funcion)
    return weakref.ref(funcion)


@dataclass
class Campo:
    nombre: str
    etiqueta: str
    tipo: str = "texto"  # "texto" | "texto_largo" | "numero" | "booleano" | "combo" | "fecha"
    opciones: Callable[[sqlite3.Connection], list[tuple]] | None = None
    requerido: bool = False
    requerido_si: Callable[[Callable[[str], object]], bool] | None = None
    """Obligatoriedad dinámica, para cuando depende de otro campo del mismo
    diálogo (ej. Profesionales: Apellido deja de ser obligatorio para la
    categoría "C", donde en cambio pasan a serlo Nombre/Profesión/Fecha de
    contacto) — cuando está presente PISA a `requerido` (que para estos
    campos queda en False, el valor "sin condición" no se usa). Recibe
    `obtener_valor(nombre_campo)`, que da el valor ACTUAL de cualquier otro
    campo del mismo diálogo tal como lo daría `valores()` sin cerrarlo
    (ver `_DialogoRegistro._valor_actual`) — se evalúa tanto al validar
    (`_validar_y_aceptar`) como al redibujar el asterisco de la etiqueta
    (`actualizar_etiquetas_requeridas`, a conectar a mano contra lo que
    dispare el cambio, ej. el combo de Categoría)."""
    combo_editable: bool = False
    """Solo para tipo="combo": si el combo acepta texto libre además de las
    opciones sugeridas — para catálogos abiertos (p. ej. CondicionFiscal)
    a diferencia de los realmente cerrados (p. ej. TipoFechaEspecial, que
    feriados.py compara por string exacto: un valor fuera de catálogo ahí
    rompe en silencio el descuento del 100%)."""
    normalizar: Callable[[str], str] | None = None
    """Solo para tipo="texto": transforma el texto tipeado antes de
    guardarlo (p. ej. CUIT sin guiones — sección 3.4)."""
    validador: Callable[[str], bool] | None = None
    """Solo para tipo="texto": valida el texto ya normalizado (si hay
    `normalizar`) antes de guardar — si devuelve False, se avisa con
    `formato_esperado` y el diálogo no se cierra. Ver
    `app.negocio.validaciones` para los validadores ya armados (fecha,
    período, email, DNI, CUIT); campos vacíos y no obligatorios no se
    validan (ver `_validar_y_aceptar`)."""
    formato_esperado: str | None = None
    """Descripción corta del formato esperado, para el cartel de aviso
    cuando `validador` rechaza el valor (ej. "AAAA-MM-DD")."""
    formato_fecha: str | None = None
    """Solo para tipo="fecha": patrón de visualización a usar en vez del
    default del sistema (`_FORMATO_FECHA_DIA`, "lun 07-09-2026") — ej.
    Profesionales usa "dd-MM-yyyy" sin día de semana para Fecha de
    nacimiento/contacto, donde el día de la semana no aporta nada."""
    default_hoy: bool = False
    """Solo para tipo="fecha" NO `requerido` (estático): en vez de
    arrancar en "(sin fecha)" (`_FECHA_SIN_DATO`) en un alta nueva sin
    valor cargado, arranca en la fecha de hoy — pedido puntual de
    Profesionales para Fecha de contacto (no todas las categorías la
    exigen, pero cuando se da de alta un contacto es casi siempre
    "hoy"). Sigue siendo editable/vaciable como cualquier campo fecha
    opcional (el sentinel "(sin fecha)" se instala igual, ver
    `_crear_entrada`) — solo cambia el valor con el que arranca."""
    es_monto: bool = False
    """Solo para tipo="numero": se muestra en la tabla como moneda
    (`formatear_moneda`, con separador de miles), alineado a la derecha,
    y en rojo si es negativo (mismo criterio `item_monto` que ya usan
    las solapas "Estado de cuenta" de Pagos/Liquidaciones/Cargos
    especiales — pedido explícito de la clienta: "compete a todos los
    importes del sistema") — en vez del número crudo sin formato que
    usan los campos numéricos que NO son un importe (ej. "Cantidad de
    baños", "% Bonificación", "Orden")."""
    centrado: bool = False
    """Centra el contenido de esta columna en la tabla (no en el cuadro
    de diálogo Nuevo/Editar) — pedido puntual de un catálogo (ej.
    "Orden"/"Activo" en Listas editables), no un comportamiento default
    de `PantallaCRUD`."""
    ancho_fijo: bool = False
    """Esta columna no participa del reparto de ancho sobrante que hace
    `PantallaCRUD` cuando se pasa `columna_prioritaria` (ver más abajo):
    se queda siempre en el ancho justo de `resizeColumnsToContents()`
    más el padding general — mismo criterio que `columnas_minimas` en
    `app.gui.pantallas.imagenes._ajustar_columnas`."""
    ancho_minimo_etiqueta: bool = False
    """En vez del ancho natural de `resizeColumnsToContents()` + padding,
    esta columna queda exactamente en lo que mide su propio título de
    encabezado (`Campo.etiqueta`) más un colchón chico — pedido puntual
    (ej. "Consul"/"Activo" en Mensajes predefinidos): "reducí el ancho
    para que entre la etiqueta sin cortar", aunque el contenido real sea
    más largo (ahí se ve truncado con elipsis, comportamiento nativo de
    Qt). Nunca participa del reparto de `columna_prioritaria` (mismo
    criterio que `ancho_fijo`, que para esta columna no hace falta
    sumar aparte)."""
    tercio_extra: bool = False
    """Esta columna se lleva un tercio más de su propio ancho natural
    (`ancho + ancho // 3`) — pedido puntual (ej. "Categoría"/
    "Descripción" en Mensajes predefinidos), mismo criterio que ya usa
    `app.gui.pantallas.mensajeria._PanelCentroMensajeria._ajustar_
    columnas` para "Saldo anterior"/"Saldo actual". Tampoco participa
    del reparto de `columna_prioritaria`: ya tiene su propio ancho
    fijado, no uno a repartir de nuevo."""
    variables: dict[str, str] | None = None
    """Solo para tipo="texto_largo": variables `{nombre}` disponibles
    para sustituir en este campo, como `{"apodo": "Apodo del
    profesional elegido en..."}` — nombre de variable (sin llaves) a su
    descripción. Cuando está presente, el diálogo suma debajo del campo
    una fila con un botón por variable (hallazgo #24 de la auditoría,
    pedido explícito de la clienta: "cómo selecciono variables") que la
    inserta en el cursor del campo al hacer clic, con la descripción
    como tooltip del botón — ver `_DialogoRegistro._armar_fila_
    variables`. Puramente informativo/de conveniencia: no valida que lo
    tipeado a mano use solo variables de esta lista (`sustituir_
    variables` deja cualquier `{token}` desconocido tal cual, sin
    reemplazarlo ni romper)."""


class _TablaConAnchoDinamico(QTableWidget):
    """Notifica a `al_redimensionar` cada vez que cambia de tamaño —
    mismo motivo y mismo patrón que `app.gui.pantallas.imagenes.
    _TablaConAnchoDinamico`: el ancho real disponible (para repartir el
    sobrante, ver `PantallaCRUD._repartir_ancho_sobrante`) recién se
    conoce después de que el layout se resuelve, no al construirse."""

    def __init__(self, al_redimensionar, parent=None):
        super().__init__(parent)
        self._al_redimensionar = al_redimensionar

    def resizeEvent(self, evento) -> None:  # noqa: N802 (nombre impuesto por Qt)
        super().resizeEvent(evento)
        self._al_redimensionar()


def campos_libres(conn: sqlite3.Connection) -> list[Campo]:
    """Los tres campos libres (CampoLibre1/2/3) que se suman al final de
    todo catálogo revisado desde Consultorios en adelante (ver CLAUDE.md).
    La clienta los puede ocultar en todos los catálogos a la vez apagando
    "Visualizar campos libres" en Configuración general
    (Configuracion.VisualizarCamposLibres) — no borra los valores ya
    cargados, solo deja de mostrarlos y de pedirlos (tabla y diálogo Nuevo/
    Editar toman esta misma lista, así que alcanza con no incluirlos acá)."""
    fila = conn.execute("SELECT VisualizarCamposLibres FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    if fila is not None and not fila["VisualizarCamposLibres"]:
        return []
    return [
        Campo("CampoLibre1", "Campo libre 1"),
        Campo("CampoLibre2", "Campo libre 2"),
        Campo("CampoLibre3", "Campo libre 3"),
    ]


class PantallaCRUD(QWidget):
    def __init__(
        self, conn: sqlite3.Connection, tabla: str, titulo: str, campos: list[Campo], parent=None,
        al_actualizar: Callable[[sqlite3.Row, dict], None] | None = None,
        al_crear: Callable[[int, dict], None] | None = None,
        al_eliminar: Callable[[sqlite3.Row], None] | None = None,
        antes_de_eliminar: Callable[[sqlite3.Row], str | None] | None = None,
        al_abrir_dialogo: Callable[[QDialog], None] | None = None,
        al_guardar: Callable[[dict, sqlite3.Row | None], dict | None] | None = None,
        solo_lectura: bool = False,
        instalar_foco: bool = True,
        compacto: bool = False,
        panel_extra_izquierda: QWidget | None = None,
        panel_extra_superior_izquierda: QWidget | None = None,
        etiqueta_buscar: str = "Buscar",
        nuevo_secundario: bool = False,
        anidado: bool = False,
        campos_primero_dialogo: list[str] | None = None,
        columna_prioritaria: str | None = None,
        columna_flexible: str | None = None,
        multiplicador_tamano_dialogo: float = 1.0,
        multiplicador_alto_dialogo: float | None = None,
    ):
        super().__init__(parent)
        self.conn = conn
        self.tabla = tabla
        self.campos = campos
        self.repositorio = obtener_repositorio(conn, tabla)
        # al_actualizar/al_crear/al_eliminar: casi siempre son métodos
        # atados de una pantalla compuesta dueña de este PantallaCRUD (ej.
        # Llaves, que los usa para armar su propio "Deshacer último
        # movimiento" sin duplicar acá la lógica de guardado). Guardados
        # como referencia débil (ver `_referencia_debil`) para no crear un
        # ciclo pantalla -> PantallaCRUD -> pantalla.
        self._al_actualizar = _referencia_debil(al_actualizar)
        self._al_crear = _referencia_debil(al_crear)
        self._al_eliminar = _referencia_debil(al_eliminar)
        # antes_de_eliminar: a diferencia de al_eliminar (corre DESPUÉS del
        # borrado, solo para reaccionar — ver `_al_eliminar_fecha_especial`
        # en catalogos.py), este corre ANTES de pedir la confirmación
        # genérica y puede BLOQUEAR la eliminación devolviendo un mensaje
        # (None = sin objeción, seguir normal) — para catálogos donde
        # borrar el registro puede dejar algo inconsistente que el
        # sistema no puede resolver solo (ej. Fechas especiales: anular
        # un feriado con reservas aisladas ya confirmadas ese día).
        self._antes_de_eliminar = _referencia_debil(antes_de_eliminar)
        # solo_lectura: sin botones Nuevo/Editar/Eliminar ni doble clic para
        # editar — para catálogos que se modifican solo desde un proceso de
        # negocio específico (p. ej. Esquema de descuentos, que DC-10 §1.1
        # dice que solo debe tocarse durante el análisis de aumentos) y acá
        # se muestran únicamente como consulta/historial.
        self.solo_lectura = solo_lectura
        # instalar_foco: arma su propia cadena de Enter-avanza-foco (Nuevo /
        # Editar / Eliminar, con foco inicial en Nuevo) — apagalo cuando una
        # pantalla compuesta (p. ej. Llaves) va a armar una cadena propia que
        # combine estos tres botones con los suyos, para no instalar dos
        # filtros de evento distintos sobre los mismos widgets.
        self.instalar_foco = instalar_foco and not solo_lectura
        # al_abrir_dialogo: llamado con el diálogo recién construido, antes de
        # mostrarlo, tanto al crear un registro nuevo como al editar uno
        # existente — para pantallas que necesitan sugerir/reaccionar entre
        # campos del mismo formulario (p. ej. Profesionales: código sugerido
        # según categoría, desplegable de Tratamiento según profesión/sexo)
        # sin acoplar eso al CRUD genérico. Los hooks que solo deben sugerir
        # sobre un campo vacío (y no pisar un valor ya cargado) comparan
        # contra la última sugerencia propia, no contra "vacío".
        self.al_abrir_dialogo = al_abrir_dialogo
        # al_guardar: llamado con (valores, registro_existente_o_None) justo
        # antes de crear/actualizar — devuelve los valores a guardar (puede
        # modificarlos) o None para cancelar el guardado por completo. Para
        # validaciones entre registros que el diálogo por sí solo no puede
        # resolver (p. ej. Gastos operativos: no puede convivir un origen
        # Manual y uno Importado para el mismo concepto y período).
        self.al_guardar = al_guardar
        # campos_primero_dialogo: nombres de `Campo` que, SOLO en el
        # cuadro de diálogo Nuevo/Editar, se adelantan al principio del
        # formulario en ese orden (ej. Profesionales: Categoría antes de
        # Código) — la tabla/listado sigue mostrando las columnas en el
        # orden original de `campos`, que no se toca (pedido puntual
        # sobre el diálogo, no sobre el listado).
        self._campos_primero_dialogo = campos_primero_dialogo
        # columna_prioritaria: nombre de un `Campo` que se lleva la
        # mitad del ancho sobrante de la tabla (disponible menos lo que
        # ya ocupan sus columnas) una vez que ya mide su ancho real
        # disponible — la otra mitad se reparte entre el resto de las
        # columnas que no tengan `ancho_fijo=True` (si es una sola, se
        # la lleva entera: "dale más a X, lo que te quede a Y"). Mismo
        # criterio que `app.gui.pantallas.imagenes._repartir_sobrante`
        # (sin el ancho mínimo por etiqueta de encabezado, que ningún
        # catálogo genérico necesitó todavía). None (default) deja el
        # comportamiento de siempre: columnas al ancho justo de
        # `resizeColumnsToContents()` + padding, sin ocupar el resto de
        # la pantalla — se suma catálogo por catálogo a medida que se
        # revisa cada uno (mismo criterio que el resto del sistema), no
        # en los ~14 catálogos genéricos de una sola vez.
        self._columna_prioritaria = columna_prioritaria
        # columna_flexible: nombre de un `Campo` (típicamente tipo=
        # "texto_largo", cuyo contenido puede ser un párrafo entero y
        # haría que `resizeColumnsToContents()` la deje enorme) cuyo
        # ancho NO se calcula por contenido — se fuerza a lo que sobre
        # del ancho disponible una vez que el resto de las columnas ya
        # tiene el suyo, para que esas otras columnas (ej. "Activo")
        # entren siempre en pantalla sin escroleo horizontal (pedido
        # explícito de la clienta sobre Condiciones y normas/Detalles
        # complementarios: "reducila... entre la columna Activo en la
        # pantalla sin necesidad de escrolear"). Si el contenido de esa
        # columna queda cortado, se ve solo en parte — la clienta pidió
        # explícitamente esto ("aunque se vea el contenido en forma
        # parcial"), para eso suma el cuadro de vista previa aparte
        # (`panel_extra_izquierda`, ver `catalogos.py`). No both at
        # once con `columna_prioritaria` sobre la MISMA columna (una
        # agranda con el sobrante, la otra fuerza un ancho fijo
        # calculado distinto) — cada catálogo usa el que corresponda.
        self._columna_flexible = columna_flexible
        # multiplicador_tamano_dialogo: pedido puntual (Mensajes
        # predefinidos, "el doble de ancho y de alto") — se aplica al
        # tamaño ya calculado por `_DialogoRegistro` (no a un valor fijo
        # propio), así que un formulario con muchos campos sigue
        # creciendo en función de su contenido, solo que ahora al doble.
        # 1.0 (default) deja el tamaño de siempre en el resto de los
        # catálogos — no se toca de una sola vez.
        self._multiplicador_tamano_dialogo = multiplicador_tamano_dialogo
        # multiplicador_alto_dialogo: independiente del de ancho (pedido
        # posterior, misma pantalla: "reducí el alto... un 30%" sin tocar
        # el ancho ya aprobado) — `None` (default) reusa el multiplicador
        # de ancho para el alto también, mismo comportamiento de siempre
        # para cualquier otro catálogo que solo pase uno de los dos.
        self._multiplicador_alto_dialogo = (
            multiplicador_tamano_dialogo if multiplicador_alto_dialogo is None else multiplicador_alto_dialogo
        )
        # compacto: layout viejo (título + fila de botones arriba de la
        # tabla, sin solapa/filtro) — para cuando una pantalla compuesta
        # (ej. Mensajes predefinidos) inserta este CRUD como un componente
        # más dentro de su propia composición (con su propio título/
        # filtro/paneles alrededor), en vez de usarlo como pantalla de
        # catálogo independiente. Las pantallas de catálogo comunes usan
        # el layout nuevo (default): solapa "Listado" (ficha, como el resto
        # del sistema), panel de Buscar + botones a la izquierda, tabla a
        # la derecha, todo dentro de un QScrollArea.
        self.compacto = compacto
        # panel_extra_izquierda: widget ya armado (con sus propios botones/
        # conexiones) que se agrega debajo de Nuevo/Editar/Eliminar en el
        # panel izquierdo, antes del stretch final — para catálogos que
        # necesitan una sección extra ahí sin dejar de ser una pantalla de
        # catálogo "de verdad" (ej. Profesionales: panel de documentación
        # del profesional seleccionado). Solo aplica al layout nuevo (se
        # ignora en modo compacto, que no tiene panel izquierdo).
        self.panel_extra_izquierda = panel_extra_izquierda
        # panel_extra_superior_izquierda: widget ya armado que se agrega
        # ENTRE Buscar y Nuevo/Editar/Eliminar — para un filtro propio de
        # visualización que tiene que quedar arriba de los botones en vez
        # de debajo (ej. Mensajes predefinidos: combo de Categoría).
        # Distinto de panel_extra_izquierda (que va debajo de los
        # botones); un catálogo puede usar los dos a la vez. Solo aplica
        # al layout nuevo (se ignora en modo compacto).
        self.panel_extra_superior_izquierda = panel_extra_superior_izquierda
        # etiqueta_buscar: texto del título arriba del campo Buscar — default
        # genérico "Buscar", pero un catálogo puede pedir uno más específico
        # (ej. Profesionales: "Buscar profesional") sin cambiar el criterio
        # de filtrado en sí (sigue siendo substring por cualquier columna).
        self.etiqueta_buscar = etiqueta_buscar
        # nuevo_secundario: pinta "Nuevo" en botonSecundario en vez de
        # botonPrimario — para catálogos donde otra acción del panel es la
        # más importante (ej. Mensajes predefinidos: "Copiar mensaje").
        self.nuevo_secundario = nuevo_secundario
        # anidado: ver docstring del módulo — sin título ni QTabWidget
        # propio, para embeberse como solapa de un formulario compuesto.
        self.anidado = anidado
        self.campo_buscar: QLineEdit | None = None
        self.boton_nuevo = self.boton_editar = self.boton_eliminar = None
        self._armar_ui(titulo)
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar":
        el widget todavía no está mostrado en ese momento."""
        super().showEvent(event)
        self.reiniciar()

    def reiniciar(self) -> None:
        """Punto 1.4 (SistemaDF v0.11.2026.10, "resetear la solapa
        cuando se sale de ella" + F3/F5 "Reiniciar solapa"): además de
        reiniciar el orden de la tabla (`_orden.reiniciar()`, ya
        existía), limpia el campo "Buscar" — el único filtro propio de
        un catálogo genérico — para que re-entrar a la solapa (o F5)
        muestre la tabla completa, sin arrastrar lo que se haya tipeado
        la última vez. Mismo método para los dos disparadores: el
        `showEvent` de arriba (re-entrada real) y `VentanaPrincipal.
        _reiniciar_solapa_activa` (F5, por nombre de método, duck-typed).

        `tabla_widget.clearSelection()` (barrido F5 de #145): `actualizar()`
        reconstruye la tabla por índice de fila, nunca por identidad de
        registro, así que una fila seleccionada antes de F5 queda
        igual de seleccionada después, aunque ahora muestre otro
        registro — no es el estado de apertura real (sin nada
        seleccionado). El propio `clearSelection()` dispara
        `itemSelectionChanged`, que ya deshabilita Editar/Eliminar."""
        self._orden.reiniciar()
        if self.campo_buscar is not None:
            self.campo_buscar.clear()
        self.actualizar()
        self.tabla_widget.clearSelection()
        if self.instalar_foco:
            (self.campo_buscar or self.boton_nuevo).setFocus()

    def _armar_ui(self, titulo: str) -> None:
        if self.anidado:
            self.setObjectName("panelSolapa")
            layout_externo = QVBoxLayout(self)
            layout_externo.setContentsMargins(0, 0, 0, 0)
            scroll = QScrollArea()
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidgetResizable(True)
            contenido = QWidget()
            contenido.setObjectName("panelSolapa")
            layout_solapa = QHBoxLayout(contenido)
            self._armar_panel_izquierda_y_tabla(layout_solapa)
            scroll.setWidget(contenido)
            layout_externo.addWidget(scroll)

            orden_foco = [self.campo_buscar, self.boton_nuevo, self.boton_editar, self.boton_eliminar]
            if self.instalar_foco:
                self._foco = instalar_enter_avanza_foco([w for w in orden_foco if w is not None], parent=self)
        else:
            layout = QVBoxLayout(self)

            etiqueta_titulo = QLabel(titulo)
            etiqueta_titulo.setObjectName("tituloPantalla")
            layout.addWidget(etiqueta_titulo)

            if self.compacto:
                self._armar_botones_y_tabla(layout)
                if self.instalar_foco:
                    self._foco = instalar_enter_avanza_foco(
                        [self.boton_nuevo, self.boton_editar, self.boton_eliminar], parent=self,
                    )
            else:
                solapas = QTabWidget()
                panel_solapa = QWidget()
                panel_solapa.setObjectName("panelSolapa")
                layout_solapa = QHBoxLayout(panel_solapa)
                self._armar_panel_izquierda_y_tabla(layout_solapa)

                scroll = QScrollArea()
                scroll.setFrameShape(QFrame.Shape.NoFrame)
                scroll.setWidgetResizable(True)
                scroll.setWidget(panel_solapa)
                solapas.addTab(scroll, "Listado")
                solapas.tabBar().setDrawBase(False)
                layout.addWidget(solapas, stretch=1)

                orden_foco = [self.campo_buscar, self.boton_nuevo, self.boton_editar, self.boton_eliminar]
                if self.instalar_foco:
                    self._foco = instalar_enter_avanza_foco([w for w in orden_foco if w is not None], parent=self)

        self._orden = OrdenTabla(self.tabla_widget, self.actualizar)

    def _armar_panel_izquierda_y_tabla(self, layout_solapa) -> None:
        panel_izquierda = QWidget()
        panel_izquierda.setObjectName("panelSolapa")
        form = QVBoxLayout(panel_izquierda)
        form.addWidget(_titulo_campo(self.etiqueta_buscar))
        self.campo_buscar = QLineEdit()
        self.campo_buscar.setFixedWidth(_ANCHO_CAMPO)
        self.campo_buscar.textChanged.connect(self._aplicar_filtro_busqueda)
        form.addWidget(self.campo_buscar)
        if self.panel_extra_superior_izquierda is not None:
            form.addWidget(self.panel_extra_superior_izquierda)
        self._armar_botones_y_tabla(form, ancho_botones=_ANCHO_CAMPO)
        if self.panel_extra_izquierda is not None:
            # con stretch para que ocupe el resto del alto disponible (ej.
            # Profesionales: la lista de documentación se estira hasta el
            # pie del panel, a la par de la barra de desplazamiento
            # horizontal de la tabla) — sin esto quedaba pegado arriba,
            # del alto justo de su contenido, con todo el resto en blanco
            # abajo.
            form.addWidget(self.panel_extra_izquierda, stretch=1)
        else:
            form.addStretch()
        layout_solapa.addWidget(panel_izquierda)

        layout_solapa.addWidget(self.tabla_widget, stretch=1)

    def _armar_botones_y_tabla(self, layout, ancho_botones: int | None = None) -> None:
        """Arma los botones Nuevo/Editar/Eliminar (si no es de solo
        lectura) y la tabla, y los agrega a `layout` — compartido entre el
        layout compacto (fila de botones horizontal) y el nuevo (columna
        vertical en el panel izquierdo, con ancho fijo)."""
        if not self.solo_lectura:
            self.boton_nuevo = QPushButton("Nuevo")
            self.boton_nuevo.setObjectName("botonSecundario" if self.nuevo_secundario else "botonPrimario")
            self.boton_nuevo.clicked.connect(self._nuevo)
            self.boton_editar = QPushButton("Editar")
            self.boton_editar.setObjectName("botonSecundario")
            self.boton_editar.clicked.connect(self._editar)
            self.boton_eliminar = QPushButton("Eliminar")
            self.boton_eliminar.setObjectName("botonSecundario")
            self.boton_eliminar.clicked.connect(self._eliminar)
            # Editar/Eliminar arrancan deshabilitados y solo se habilitan con
            # una fila seleccionada en la tabla (pedido explícito de la
            # clienta, "ESTO PARA TODO EL SISTEMA") — mismo criterio ya usado
            # en Pagos/Registrar pagos y Planes de pago.
            self.boton_editar.setEnabled(False)
            self.boton_eliminar.setEnabled(False)
            if ancho_botones is not None:
                self.boton_nuevo.setFixedWidth(ancho_botones)
                self.boton_editar.setFixedWidth(ancho_botones)
                self.boton_eliminar.setFixedWidth(ancho_botones)
                layout.addWidget(self.boton_nuevo)
                layout.addWidget(self.boton_editar)
                layout.addWidget(self.boton_eliminar)
            else:
                fila_botones = QHBoxLayout()
                fila_botones.addWidget(self.boton_nuevo)
                fila_botones.addWidget(self.boton_editar)
                fila_botones.addWidget(self.boton_eliminar)
                fila_botones.addStretch()
                layout.addLayout(fila_botones)

        self.tabla_widget = _TablaConAnchoDinamico(self._reajustar_ancho_tabla)
        excluir_tabla_del_tab(self.tabla_widget)
        self.tabla_widget.setColumnCount(len(self.campos))
        self.tabla_widget.setHorizontalHeaderLabels([c.etiqueta for c in self.campos])
        # A propósito NO se fuerza `ScrollBarAlwaysOff` acá (a diferencia
        # de imagenes.py/mensajeria.py): `columna_flexible` tiene un piso
        # (`_ANCHO_MINIMO_COLUMNA_FLEXIBLE`) para no degenerar a 0 en una
        # ventana angosta o con muchas columnas fijas (ej. Campos libres
        # activados) — si ESE piso llega a dejar la tabla más ancha que
        # la pantalla, mejor que la barra horizontal aparezca sola (como
        # siempre) a que esas columnas queden inaccesibles sin aviso.
        self.tabla_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        if not self.solo_lectura:
            self.tabla_widget.doubleClicked.connect(self._editar)
            self.tabla_widget.itemSelectionChanged.connect(self._actualizar_botones_seleccion)
            instalar_eliminar_con_tecla(self.tabla_widget, self._eliminar)
        if ancho_botones is None:
            layout.addWidget(self.tabla_widget, stretch=1)

    def _aplicar_filtro_busqueda(self, *_args) -> None:
        """Solo cambia qué filas se ven — mismo criterio que los filtros
        de Vista rápida/Aumentos (ver CLAUDE.md, "Filtros que solo afectan
        la visualización"). Busca por cualquier parte del texto de
        cualquier columna visible, sin distinguir mayúsculas ni acentos
        (mismo criterio que el buscador de profesional)."""
        if self.campo_buscar is None:
            return
        buscado = _normalizar_busqueda(self.campo_buscar.text().strip())
        for fila in range(self.tabla_widget.rowCount()):
            if not buscado:
                self.tabla_widget.setRowHidden(fila, False)
                continue
            texto_fila = " ".join(
                self.tabla_widget.item(fila, col).text()
                for col in range(self.tabla_widget.columnCount())
                if self.tabla_widget.item(fila, col) is not None
            )
            self.tabla_widget.setRowHidden(fila, buscado not in _normalizar_busqueda(texto_fila))
        if buscado:
            self._seleccionar_si_queda_una_sola_fila_visible()

    def _seleccionar_si_queda_una_sola_fila_visible(self) -> None:
        """Pedido explícito de la clienta, regla general para toda
        pantalla que filtre una tabla (acá, "Buscar"): si escribir en el
        filtro deja UNA sola fila visible, se selecciona sola — para
        poder ir directo a Editar/Eliminar sin tener que pinchar primero
        en esa fila. Solo con un filtro activo (`buscado` no vacío): un
        catálogo que de entrada tenga una sola fila cargada no se
        selecciona sola al abrir la pantalla — nadie "filtró" nada
        todavía, y los paneles que dependen de la selección (ej. la
        documentación de Profesionales) tienen que arrancar vacíos."""
        visibles = [f for f in range(self.tabla_widget.rowCount()) if not self.tabla_widget.isRowHidden(f)]
        if len(visibles) == 1:
            self.tabla_widget.selectRow(visibles[0])

    def actualizar(self) -> None:
        registros = self.repositorio.listar()
        if self._orden.columna is not None:
            registros = sorted(
                registros, key=self._clave_orden(self._orden.columna), reverse=not self._orden.ascendente
            )
        self.tabla_widget.setRowCount(len(registros))
        for fila_idx, registro in enumerate(registros):
            for col_idx, campo in enumerate(self.campos):
                if campo.tipo == "numero" and campo.es_monto:
                    # Pedido explícito de la clienta ("compete a todos los
                    # importes del sistema"): mismo helper ya usado en
                    # Estado de cuenta de Pagos/Liquidaciones/Cargos
                    # especiales — moneda, a la derecha, rojo si negativo.
                    item = item_monto(registro[campo.nombre])
                elif campo.centrado:
                    item = item_centrado(self._texto_celda(registro, campo))
                else:
                    item = QTableWidgetItem(self._texto_celda(registro, campo))
                if col_idx == 0:
                    item.setData(_ID_REGISTRO, registro[self.repositorio.clave_primaria])
                self.tabla_widget.setItem(fila_idx, col_idx, item)
        # Hallazgo puntual en "Tipos de licencia" (columna "Nombre" muy
        # pegada al contenido): aplicado acá de una a los ~14 catálogos
        # genéricos, mismo criterio y mismo valor que
        # novedades._ajustar_columnas/llaves._ajustar_columnas — sobra
        # ancho en el panel, no tiene sentido dejar las columnas al
        # ancho justo de resizeColumnsToContents().
        self.tabla_widget.resizeColumnsToContents()
        metrica_encabezado = QFontMetrics(self.tabla_widget.horizontalHeader().font())
        for col, campo in enumerate(self.campos):
            if campo.ancho_minimo_etiqueta:
                ancho_titulo = metrica_encabezado.horizontalAdvance(campo.etiqueta)
                self.tabla_widget.setColumnWidth(col, ancho_titulo + _COLCHON_TITULO_COLUMNA)
            else:
                self.tabla_widget.setColumnWidth(col, self.tabla_widget.columnWidth(col) + _PADDING_COLUMNA)
            if campo.tercio_extra:
                ancho = self.tabla_widget.columnWidth(col)
                self.tabla_widget.setColumnWidth(col, ancho + ancho // 3)
        if self._columna_prioritaria is not None:
            self._repartir_ancho_sobrante()
        if self._columna_flexible is not None:
            self._ajustar_columna_flexible()
        self._aplicar_filtro_busqueda()
        self._actualizar_botones_seleccion()

    def _reajustar_ancho_tabla(self) -> None:
        """Se llama sola cada vez que `tabla_widget` cambia de tamaño
        (`_TablaConAnchoDinamico`) — mismo motivo que `imagenes.
        _PanelGestorArchivos._reajustar_ancho_tabla`: recién ahí se
        conoce el ancho real disponible para repartir el sobrante."""
        if self.tabla_widget.columnCount() == 0:
            return
        if self._columna_prioritaria is not None:
            self._repartir_ancho_sobrante()
        if self._columna_flexible is not None:
            self._ajustar_columna_flexible()

    def _ajustar_columna_flexible(self) -> None:
        """Ver `columna_flexible` más arriba: fuerza el ancho de esa
        columna a lo que sobre del ancho disponible de la tabla una vez
        que el resto de las columnas ya tiene el suyo (natural +
        padding) — nunca se calcula por su propio contenido."""
        indice = next((i for i, c in enumerate(self.campos) if c.nombre == self._columna_flexible), None)
        if indice is None:
            return
        disponible = self.tabla_widget.viewport().width()
        suma_otras = sum(
            self.tabla_widget.columnWidth(c) for c in range(self.tabla_widget.columnCount()) if c != indice
        )
        self.tabla_widget.setColumnWidth(indice, max(_ANCHO_MINIMO_COLUMNA_FLEXIBLE, disponible - suma_otras))

    def _repartir_ancho_sobrante(self) -> None:
        """La mitad del ancho sobrante (disponible menos lo que ya
        ocupan las columnas en su ancho natural + padding) va para
        `self._columna_prioritaria`; la otra mitad se reparte en partes
        iguales entre el resto de las columnas que no tengan `Campo.
        ancho_fijo=True` (si es una sola, se la lleva entera). Mismo
        criterio que `imagenes._repartir_sobrante`. Tampoco participan
        `Campo.ancho_minimo_etiqueta`/`tercio_extra`: ya tienen su
        propio ancho fijado por otro criterio, no uno a repartir de
        nuevo acá."""
        indice_prioritaria = next(
            (i for i, c in enumerate(self.campos) if c.nombre == self._columna_prioritaria), None,
        )
        if indice_prioritaria is None:
            return
        disponible = self.tabla_widget.viewport().width()
        suma_natural = sum(self.tabla_widget.columnWidth(c) for c in range(self.tabla_widget.columnCount()))
        sobrante = disponible - suma_natural
        if sobrante <= 0:
            return
        otras = [
            i for i, c in enumerate(self.campos)
            if i != indice_prioritaria and not c.ancho_fijo and not c.ancho_minimo_etiqueta and not c.tercio_extra
        ]
        para_prioritaria = sobrante // 2
        resto = sobrante - para_prioritaria
        self.tabla_widget.setColumnWidth(
            indice_prioritaria, self.tabla_widget.columnWidth(indice_prioritaria) + para_prioritaria,
        )
        if not otras:
            self.tabla_widget.setColumnWidth(
                indice_prioritaria, self.tabla_widget.columnWidth(indice_prioritaria) + resto,
            )
            return
        por_columna, residuo = divmod(resto, len(otras))
        for i, columna in enumerate(otras):
            extra = por_columna + (1 if i < residuo else 0)
            self.tabla_widget.setColumnWidth(columna, self.tabla_widget.columnWidth(columna) + extra)

    def _actualizar_botones_seleccion(self) -> None:
        if self.solo_lectura:
            return
        hay_seleccion = self.fila_seleccionada_id() is not None
        self.boton_editar.setEnabled(hay_seleccion)
        self.boton_eliminar.setEnabled(hay_seleccion)

    def _clave_orden(self, columna: int):
        campo = self.campos[columna]

        def clave(registro: sqlite3.Row):
            valor = registro[campo.nombre]
            if campo.tipo == "numero":
                return valor if valor is not None else float("-inf")
            if campo.tipo == "booleano":
                return bool(valor)
            if campo.tipo == "fecha":
                # Ordena por el AAAA-MM-DD guardado, no por el texto mostrado
                # ("lun 07-09-2026"): ese orden lexicográfico no coincide con
                # el cronológico (empieza por el día de la semana).
                return valor or ""
            if campo.nombre == "IdCodigo":
                # Orden natural (letra + número completo, ver CLAUDE.md
                # "Orden natural de códigos de profesional") — alcanza
                # con el nombre de columna, no hace falta un tipo nuevo
                # de Campo para esto, solo lo usa Profesionales hoy.
                return clave_orden_codigo(self._texto_celda(registro, campo))
            return self._texto_celda(registro, campo)

        return clave

    def _texto_celda(self, registro: sqlite3.Row, campo: Campo) -> str:
        valor = registro[campo.nombre]
        if campo.tipo == "booleano":
            return "Sí" if valor else "No"
        if campo.tipo == "fecha":
            return _fmt_fecha_dia(valor, campo.formato_fecha or _FORMATO_FECHA_DIA)
        if campo.tipo == "combo" and campo.opciones:
            opciones = dict(campo.opciones(self.conn))
            return opciones.get(valor, "" if valor is None else str(valor))
        return "" if valor is None else str(valor)

    def fila_seleccionada_id(self):
        """ID de la fila seleccionada, o None — pantallas compuestas (p. ej.
        Llaves) lo usan para saber sobre qué registro maestro operar."""
        filas = self.tabla_widget.selectionModel().selectedRows()
        if not filas:
            return None
        return self.tabla_widget.item(filas[0].row(), 0).data(_ID_REGISTRO)

    def _campos_dialogo(self) -> list[Campo]:
        if not self._campos_primero_dialogo:
            return self.campos
        por_nombre = {c.nombre: c for c in self.campos}
        primeros = [por_nombre[nombre] for nombre in self._campos_primero_dialogo]
        resto = [c for c in self.campos if c.nombre not in self._campos_primero_dialogo]
        return primeros + resto

    def _nuevo(self) -> None:
        dialogo = _DialogoRegistro(
            self.conn, self._campos_dialogo(), "Nuevo registro",
            multiplicador_ancho=self._multiplicador_tamano_dialogo,
            multiplicador_alto=self._multiplicador_alto_dialogo,
        )
        if self.al_abrir_dialogo:
            self.al_abrir_dialogo(dialogo)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            valores = dialogo.valores()
            if self.al_guardar:
                valores = self.al_guardar(valores, None)
                if valores is None:
                    return
            try:
                id_nuevo = self.repositorio.crear(**valores)
            except sqlite3.IntegrityError as error:
                QMessageBox.warning(self, "Nuevo registro", f"No se pudo guardar: {error}")
                return
            al_crear = self._al_crear()
            if al_crear:
                al_crear(id_nuevo, valores)
            self.actualizar()
            if self.instalar_foco:
                self.boton_nuevo.setFocus()
            QMessageBox.information(self, "Nuevo registro", "Registro creado con éxito.")

    def _editar(self) -> None:
        id_valor = self.fila_seleccionada_id()
        if id_valor is None:
            QMessageBox.information(self, "Editar", "Seleccioná un registro para editar.")
            return
        registro = self.repositorio.obtener(id_valor)
        dialogo = _DialogoRegistro(
            self.conn, self._campos_dialogo(), "Editar registro", registro=registro,
            multiplicador_ancho=self._multiplicador_tamano_dialogo,
            multiplicador_alto=self._multiplicador_alto_dialogo,
        )
        if self.al_abrir_dialogo:
            self.al_abrir_dialogo(dialogo)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            valores = dialogo.valores()
            if self.al_guardar:
                valores = self.al_guardar(valores, registro)
                if valores is None:
                    return
            try:
                self.repositorio.actualizar(id_valor, **valores)
            except sqlite3.IntegrityError as error:
                QMessageBox.warning(self, "Editar registro", f"No se pudo guardar: {error}")
                return
            al_actualizar = self._al_actualizar()
            if al_actualizar:
                al_actualizar(registro, valores)
            self.actualizar()
            if self.instalar_foco:
                self.boton_nuevo.setFocus()
            QMessageBox.information(self, "Editar registro", "Registro editado con éxito.")

    def _eliminar(self) -> None:
        id_valor = self.fila_seleccionada_id()
        if id_valor is None:
            QMessageBox.information(self, "Eliminar", "Seleccioná un registro para eliminar.")
            return
        registro = self.repositorio.obtener(id_valor)
        antes_de_eliminar = self._antes_de_eliminar()
        if antes_de_eliminar:
            motivo = antes_de_eliminar(registro)
            if motivo:
                QMessageBox.warning(self, "Eliminar", motivo)
                return
        confirmacion = QMessageBox.question(self, "Eliminar", "¿Confirmás eliminar el registro seleccionado?")
        if confirmacion != QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Eliminar", "Eliminación cancelada.")
            return
        try:
            self.repositorio.eliminar(id_valor)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Eliminar", "No se puede eliminar: hay otros registros que dependen de este.")
            return
        al_eliminar = self._al_eliminar()
        if al_eliminar:
            al_eliminar(registro)
        self.actualizar()
        if self.instalar_foco:
            self.boton_nuevo.setFocus()
        QMessageBox.information(self, "Eliminar", "Registro eliminado con éxito.")


class _DialogoRegistro(QDialog):
    def __init__(
        self, conn: sqlite3.Connection, campos: list[Campo], titulo: str, registro=None, parent=None,
        multiplicador_ancho: float = 1.0, multiplicador_alto: float = 1.0,
    ):
        super().__init__(parent)
        self.conn = conn
        self.campos = campos
        self.setWindowTitle(titulo)
        self._entradas: dict[str, QWidget] = {}
        self._etiquetas: dict[str, QLabel] = {}
        self._campo_por_nombre = {c.nombre: c for c in campos}

        layout_general = QVBoxLayout(self)

        formulario = QWidget()
        layout_formulario = QFormLayout(formulario)
        # Las entradas se arman todas antes de las etiquetas (abajo) para
        # que `requerido_si` pueda mirar el valor inicial de CUALQUIER otro
        # campo del mismo diálogo (ej. Categoría, más abajo en la lista que
        # algún campo cuya obligatoriedad depende de ella) al calcular el
        # asterisco inicial, sin importar el orden en que aparezcan.
        for campo in campos:
            self._entradas[campo.nombre] = self._crear_entrada(campo, registro)
        for campo in campos:
            entrada = self._entradas[campo.nombre]
            etiqueta = QLabel(self._texto_etiqueta(campo))
            self._etiquetas[campo.nombre] = etiqueta
            layout_formulario.addRow(etiqueta, entrada)
            if campo.variables:
                layout_formulario.addRow("", self._armar_fila_variables(entrada, campo.variables))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(formulario)
        layout_general.addWidget(scroll)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._validar_y_aceptar)
        botones.rejected.connect(self.reject)
        layout_general.addWidget(botones)

        # Ancho dinámico: 480 era un mínimo fijo que recortaba etiquetas/
        # campos largos (ej. "Día del mes para plazo extendido
        # automático..." en Profesionales) — se calcula contra el ancho
        # real que pide el formulario (`sizeHint`, ya con etiquetas y
        # campos armados) en vez de un número fijo, con un techo para no
        # terminar con un diálogo absurdamente ancho por un solo campo
        # larguísimo (ahí ya pasa a envolver en dos líneas, como antes).
        ancho = max(480, min(formulario.sizeHint().width() + 32, 900))
        alto = min(60 + 40 * len(campos), 640)
        # multiplicador_ancho/multiplicador_alto (pedido puntual, Mensajes
        # predefinidos: "el doble de ancho y de alto que el que se abre
        # ahora", y después "reducí el alto... un 30%" sin tocar el
        # ancho — de ahí que sean dos multiplicadores independientes, no
        # uno solo) se aplican sobre el tamaño ya calculado arriba, no
        # sobre un valor fijo propio — un formulario con más campos sigue
        # creciendo en función de su contenido, solo que ahora escalado.
        # 1.0 (default) en los dos no cambia nada.
        self.resize(int(ancho * multiplicador_ancho), int(alto * multiplicador_alto))
        if multiplicador_ancho != 1.0 or multiplicador_alto != 1.0:
            # "que arranque más arriba en pantalla, centralizado" — Qt no
            # centra sola una ventana sin padre (`parent=None` en todos
            # los llamadores de este diálogo); se calcula a mano contra
            # la pantalla principal, centrada en X y bien arriba en Y en
            # vez de centrada en Y (que la dejaría más abajo de lo que
            # pidió la clienta, "para que se vea completo al abrir").
            pantalla = QGuiApplication.primaryScreen()
            if pantalla is not None:
                geometria = pantalla.availableGeometry()
                x = geometria.x() + max(0, (geometria.width() - self.width()) // 2)
                y = geometria.y() + max(0, (geometria.height() - self.height()) // 10)
                self.move(x, y)

        boton_ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        boton_cancelar = botones.button(QDialogButtonBox.StandardButton.Cancel)
        self._foco = instalar_enter_avanza_foco([*self._entradas.values(), boton_ok, boton_cancelar], parent=self)

    def showEvent(self, event) -> None:  # noqa: N802
        """`setFocus()` durante la construcción no alcanza a "pegar": el
        diálogo todavía no está mostrado en ese momento."""
        super().showEvent(event)
        if self._entradas:
            next(iter(self._entradas.values())).setFocus()

    def _crear_entrada(self, campo: Campo, registro: sqlite3.Row | None) -> QWidget:
        valor = registro[campo.nombre] if registro is not None else None
        if campo.tipo == "booleano":
            entrada = QCheckBox()
            entrada.setChecked(bool(valor))
            return entrada
        if campo.tipo == "combo":
            entrada = QComboBox()
            entrada.setEditable(campo.combo_editable)
            for valor_opcion, etiqueta_opcion in campo.opciones(self.conn):
                entrada.addItem(etiqueta_opcion, valor_opcion)
            if valor is not None:
                indice = entrada.findData(valor)
                if indice >= 0:
                    entrada.setCurrentIndex(indice)
                elif campo.combo_editable:
                    entrada.setEditText(str(valor))
            return entrada
        if campo.tipo == "texto_largo":
            entrada = QPlainTextEdit()
            entrada.setPlainText("" if valor is None else str(valor))
            entrada.setFixedHeight(80)
            return entrada
        if campo.tipo == "fecha":
            entrada = QDateEdit()
            entrada.setDisplayFormat(campo.formato_fecha or _FORMATO_FECHA_DIA)
            entrada.setLocale(_LOCALE_ES)
            entrada.setCalendarPopup(True)
            aplicar_color_sabado_negro(entrada)
            instalar_flechas_cambian_fecha_completa(entrada)
            if not campo.requerido:
                # Sin esto, un campo opcional sin valor cargado quedaría
                # mostrando y guardando "hoy" como si fuera un dato real
                # (ver `_FECHA_SIN_DATO`) — solo para los obligatorios
                # (ej. Fechas especiales) tiene sentido forzar una fecha
                # concreta por default.
                entrada.setMinimumDate(_FECHA_SIN_DATO)
                entrada.setSpecialValueText("(sin fecha)")
            fecha_qt = QDate.fromString(valor, "yyyy-MM-dd") if valor else QDate()
            if fecha_qt.isValid():
                entrada.setDate(fecha_qt)
            elif campo.requerido or campo.default_hoy:
                entrada.setDate(QDate.currentDate())
            else:
                entrada.setDate(_FECHA_SIN_DATO)
            return entrada
        entrada = QLineEdit()
        if valor is not None:
            entrada.setText(str(valor))
        return entrada

    # 5 (antes 3, pedido explícito de la clienta al sumar la décima
    # variable en Mensajes predefinidos — "pone 2 filas de 5 botones"):
    # con 10 variables da exactamente 2x5. Solo Mensajes predefinidos
    # usa `variables=` hoy (ver `Campo.variables`), así que este cambio
    # no afecta a ningún otro catálogo todavía.
    _COLUMNAS_BOTONES_VARIABLES = 5

    def _armar_fila_variables(self, entrada: QPlainTextEdit, variables: dict[str, str]) -> QWidget:
        """Un botón por variable disponible (hallazgo #24 de la
        auditoría): clickearlo inserta "{nombre}" en el cursor de
        `entrada`, sin pisar nada de lo que ya estaba tipeado. La
        descripción de cada variable queda como tooltip del botón, para
        no alargar la fila con texto largo. En grilla (no una sola fila
        corrida) para que una lista más larga de variables no termine
        recortada contra el borde del diálogo, angosto por default —
        mismo criterio que la grilla de días de Llaves/Oferta de
        consultorios."""
        contenedor = QWidget()
        layout_variables = QVBoxLayout(contenedor)
        layout_variables.setContentsMargins(0, 0, 0, 0)
        layout_variables.addWidget(QLabel("Variables disponibles (clic para insertar en el cursor):"))
        grilla_botones = QGridLayout()
        for i, (nombre_variable, descripcion) in enumerate(variables.items()):
            boton = QPushButton(f"{{{nombre_variable}}}")
            boton.setToolTip(descripcion)
            boton.clicked.connect(lambda _checked=False, v=nombre_variable: self._insertar_variable(entrada, v))
            grilla_botones.addWidget(boton, i // self._COLUMNAS_BOTONES_VARIABLES, i % self._COLUMNAS_BOTONES_VARIABLES)
        layout_variables.addLayout(grilla_botones)
        return contenedor

    @staticmethod
    def _insertar_variable(entrada: QPlainTextEdit, nombre_variable: str) -> None:
        entrada.insertPlainText(f"{{{nombre_variable}}}")
        entrada.setFocus()

    def _es_requerido(self, campo: Campo) -> bool:
        if campo.requerido_si is not None:
            return campo.requerido_si(self._valor_actual)
        return campo.requerido

    def _texto_etiqueta(self, campo: Campo) -> str:
        """Asterisco en la etiqueta de todo campo obligatorio (estático o
        dinámico vía `requerido_si`), pedido explícito de la clienta."""
        return f"{campo.etiqueta} *" if self._es_requerido(campo) else campo.etiqueta

    def actualizar_etiquetas_requeridas(self) -> None:
        """A conectar a mano contra lo que dispare un cambio que pueda
        afectar algún `requerido_si` (ej. el combo de Categoría en
        Profesionales) — redibuja el asterisco de TODAS las etiquetas,
        no solo la del campo que depende de la que cambió."""
        for campo in self.campos:
            self._etiquetas[campo.nombre].setText(self._texto_etiqueta(campo))

    def _validar_y_aceptar(self) -> None:
        for campo in self.campos:
            entrada = self._entradas[campo.nombre]
            if campo.tipo == "numero":
                texto = entrada.text().strip()
                if texto:
                    try:
                        float(texto)
                    except ValueError:
                        QMessageBox.warning(self, "Dato inválido", f"El campo «{campo.etiqueta}» tiene que ser un número.")
                        entrada.setFocus()
                        return
            if campo.tipo == "texto" and campo.validador is not None:
                texto = entrada.text().strip()
                if texto:
                    valor = campo.normalizar(texto) if campo.normalizar else texto
                    if not campo.validador(valor):
                        QMessageBox.warning(
                            self, "Dato inválido",
                            f"El campo «{campo.etiqueta}» no tiene el formato esperado ({campo.formato_esperado}).",
                        )
                        entrada.setFocus()
                        return
            if not self._es_requerido(campo):
                continue
            vacio = (
                (campo.tipo in ("texto", "numero") and not entrada.text().strip())
                or (campo.tipo == "texto_largo" and not entrada.toPlainText().strip())
                or (campo.tipo == "fecha" and entrada.date() == _FECHA_SIN_DATO)
                or (campo.tipo == "combo" and not campo.combo_editable and entrada.currentData() is None)
            )
            if vacio:
                QMessageBox.warning(self, "Datos incompletos", f"El campo «{campo.etiqueta}» es obligatorio.")
                entrada.setFocus()
                return
        self.accept()

    def _valor_actual(self, nombre_campo: str):
        """El valor actual de un campo tal como lo daría `valores()`, sin
        cerrar el diálogo — usado tanto por `valores()` (ver abajo) como
        por `requerido_si` para mirar el valor de OTRO campo del mismo
        diálogo."""
        campo = self._campo_por_nombre[nombre_campo]
        entrada = self._entradas[nombre_campo]
        if campo.tipo == "booleano":
            return 1 if entrada.isChecked() else 0
        if campo.tipo == "combo":
            if campo.combo_editable:
                texto = entrada.currentText().strip()
                return texto or None
            return entrada.currentData()
        if campo.tipo == "texto_largo":
            texto = entrada.toPlainText().strip()
            return texto or None
        if campo.tipo == "numero":
            texto = entrada.text().strip()
            return float(texto) if texto else None
        if campo.tipo == "fecha":
            if not campo.requerido and entrada.date() == _FECHA_SIN_DATO:
                return None
            return entrada.date().toString("yyyy-MM-dd")
        texto = entrada.text().strip()
        if texto and campo.normalizar:
            texto = campo.normalizar(texto)
        return texto or None

    def valores(self) -> dict:
        return {campo.nombre: self._valor_actual(campo.nombre) for campo in self.campos}
