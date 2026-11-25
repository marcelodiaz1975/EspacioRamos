"""Pantalla principal / panel de control (Etapa 6.1, FA1).

Segunda vuelta de la revisión "uno por uno" (ver CLAUDE.md): las dos
leyendas de estado que iban arriba de cada botón ("Período actual"/
"Último backup") y el subtítulo del encabezado (período en curso + hoy)
se sacaron — esa información ahora vive, más completa, en los cuadritos
de abajo. La solapa pasa a llamarse "Panel de control" (va a terminar
viviendo dentro de otro formulario más adelante, todavía a definir).
Los botones se invierten ("Generar backup ahora" arriba, "Avanzar de
mes" abajo) y "Avanzar de mes" vuelve a ser `botonPrimario` (el otro
queda `botonSecundario`) — sigue siendo la acción más "definitiva" de
esta pantalla. Debajo de los botones, seis cuadritos informativos del
mismo ancho y alto (reloj en vivo, período actual, estado del backup,
fechas especiales de los próximos dos meses, estadísticas de
profesionales, estadísticas de ocupación/horas) en una grilla 3x2, y
las alertas de siempre debajo de esos seis, ocupando todo el ancho de
la pantalla y con su propio scroll (mismo mecanismo de antes, ahora
como un cuadrito aparte en vez de una lista suelta). Tercera vuelta:
los seis cuadritos principales quedan parejos (mismo ancho y alto,
`_ALTO_MINIMO_TARJETA`), el título de cada cuadrito pasa a itálica y
termina en ":" (`_tarjeta`), y ni el título ni el contenido de abajo
tienen caja propia — un solo borde por cuadrito, el de afuera. Cuarta
vuelta: el borde de `_tarjeta` en realidad SÍ se colaba al título y al
contenido de abajo — `QLabel` hereda de `QFrame` en Qt, así que el
selector de clase `QFrame { border: ... }` de la vuelta anterior
también les pintaba el borde a esos `QLabel` hijos ("cuadritos dentro
de los cuadros", como lo señaló la clienta); se corrigió acotando el
estilo por objectName (`QFrame#cuadritoInfo`). El título de cada
cuadrito pasa además a negrita (ya estaba en itálica), y se suma una
línea divisoria entre los dos botones de la columna izquierda.

Quinta vuelta: el título de la tarjeta de fechas especiales se acorta
("Feriados y fechas especiales próximas") porque era el más largo y
forzaba esa columna de la grilla más ancha que las otras dos; su lógica
cambia de "desde el día 1 del mes en curso" a "desde hoy" (lo que ya
pasó del mes no se muestra) hasta el último día del SEGUNDO mes
siguiente (antes solo llegaba al primero) —
`app.negocio.panel_control.fechas_especiales_proximas_dos_meses`,
renombrada para reflejar el nuevo alcance. Las explicaciones de los
botones dejan de ser un único cuadro de texto y pasan a ser una por
botón, alineada al lado de su botón correspondiente (`fila_backup`/
`fila_avanzar`) — el texto de "Avanzar de mes" además se reescribe con
la redacción exacta pedida por la clienta.

Reordenamiento de formularios (Excel de la clienta): "Panel de control"
pasa a tener dos solapas en vez de una. Todo lo de arriba (botones,
grilla de cuadritos, alertas) se movió tal cual a una clase propia,
`_PanelAvancePeriodo` (mismo patrón `panelSolapa`/`showEvent` que el
resto de las pantallas con solapas de esta revisión), y se le sumó una
segunda solapa, "Importación datos desde Excel", con `_PanelImportacion`
(antes la pantalla propia "Importar planilla" del menú — importado acá,
mismo criterio de import cruzado de un símbolo privado que
`_pixmap_primera_pagina_pdf`/`_opciones_profesional` en otras
pantallas). `PanelControl` queda como el contenedor de afuera: solo el
título Nivel 1 (nombre del espacio) y el `QTabWidget` con las dos
solapas — `actualizar()` sigue siendo el punto de entrada externo
(ej. después de avanzar de mes desde otro lado), y delega en
`self.panel_avance.actualizar()` para todo lo que no sea el título.

Séptimo cuadrito, pedido explícito de la clienta ("un cuadrito similar
a los que están... que me vaya indicando por orden de cercanía los
cumpleaños de los profesionales activos... y los días del psicólogo,
del fonoaudiólogo, etc."): "Cumpleaños y días de profesión"
(`app.negocio.panel_control.cumpleanos_y_dias_profesion_proximos`),
mismo criterio de ventana ("lo que queda de este mes + los próximos dos
meses") que "Feriados y fechas especiales próximas". Los cumpleaños
salen de `Profesional.FechaNacimiento` (excluyendo categoría X/C — ver
el docstring de la función); los días de profesión de
`Profesion.DiaProfesion`, un campo nuevo (DD-MM, SIN año — se repite
todos los años) editable desde el catálogo "Profesiones y tratamientos",
decisión tomada en vez de hardcodear un dict en Python para no tener que
tocar código cada vez que se suma o cambia una fecha. La grilla pasa a
7 cuadritos (sigue en 3 columnas; el séptimo queda solo en su propia
fila, sin ningún cuadrito más al lado) — el armado ya era genérico sobre
la cantidad de tarjetas, no hizo falta tocar `_COLUMNAS_GRILLA` ni el
cálculo de filas.

SistemaDF v0.11.2026.10, puntos 76-80 ("Avance de período y backups"):
"Fecha y hora actual" se funde dentro de "Período actual" (dos líneas
en el mismo cuadrito — período arriba, fecha/hora real debajo), así que
la grilla vuelve a 6 cuadritos, en el orden pedido explícito: Período
actual, Último backup, Ocupación y horas / Profesionales, Feriados y
fechas especiales, Cumpleaños y días de profesión. Cada cuadrito pasa a
ser escroleable EN VERTICAL de forma individual (`_agregar_contenido_
escrolable`, un `QScrollArea` propio por cuadrito en vez de agregar el
`QLabel` directo al layout) para cuando su contenido no entre en el
alto parejo de la grilla — la tarjeta de Alertas, debajo de los seis, ya
tenía su propio scroll desde antes. Cumpleaños y días de profesión pasa
a mostrar la fecha con el día de la semana abreviado ("ddd dd-mm", ej.
"mar 15-10"), mismo criterio que el resto del sistema.

Punto 81 (misma versión, segunda vuelta sobre esta solapa — ahora
"Avance de período, backup, y vista rápida"): "Último backup" se funde
DENTRO de "Período actual" (pasa a llamarse "Período actual y último
backup", con la info de período/reloj arriba y la de backup debajo, sin
cambios en ninguna de las dos) y el cuadrito que libera pasa a
"Estadísticas principales mes en curso" (montos del mes, reusando
`app.negocio.balance.resultado_periodo` — mismo criterio "neto" que
Estadísticas/Balance del negocio). "Ocupación y horas" (ahora "...mes en
curso") pierde el monto de aisladas y el saldo pendiente (ya están en el
cuadrito nuevo, sin duplicarse) y suma, debajo de los tres conceptos
generales, el mismo desglose por cada Unidad del sistema
(`calcular_estadisticas_ocupacion_por_unidad`). "Profesionales" suma
cuatro conceptos: con reservas aisladas activas, y tres sobre cambios de
`ReservaRegular` que todavía no entraron en vigencia (horarios
incorporados/liberados para el mes próximo, según caiga `VigenciaInicio`/
`VigenciaFin` dentro del mes próximo/en curso, más la diferencia entre
los dos). Los seis cuadritos (y Alertas) pasan a tener fondo transparente
en su `QScrollArea` (tanto el área como el viewport interno, que Qt arma
con su propio color default — "un cuadrito adentro del cuadrito", pedido
explícito de la clienta) y el contenido de un solo `QLabel` pasa a
alinearse arriba (`AlignTop`, en vez del centrado vertical default de
`QLabel` cuando `setWidgetResizable` lo estira al alto del viewport) —
ver `_agregar_contenido_escrolable`. `_ALTO_MINIMO_TARJETA` baja a 2/3
del valor anterior (pedido explícito, "lo que se libera dáselo al
cuadro de alertas") — no hace falta ningún cambio aparte para que
Alertas absorba ese espacio: ya tenía `stretch=1` en `layout_solapa`,
a diferencia de la grilla (sin stretch propio), así que cualquier
espacio vertical sobrante en la solapa ya iba entero a Alertas.

Rediseño completo (ronda siguiente): la grilla pareja de 3x3 se
reemplaza por dos columnas de tres cuadritos chicos (columna 1: Período
actual y último backup / Profesionales / Control de pagos; columna 2:
Ocupación y horas mes en curso / Feriados y fechas especiales próximas
/ Cumpleaños y días de profesión) y una tercer columna de un solo
cuadro LARGO, del mismo ancho que las otras dos pero con el alto de las
tres juntas — "Estadísticas principales mes en curso" rediseñada por
completo con ese espacio (ver `_armar_tarjeta_estadisticas_principales`
y `app.negocio.panel_control.EstadisticasPrincipales`). Se eliminan los
dos cuadritos "(Sin asignar)" (`_armar_tarjeta_vacia`, de baja) — ya no
quedan cuadritos libres en este diseño."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.estilos import COLOR_ROJO, COLOR_TEXTO_CLARO
from app.gui.pantallas.importacion import _PanelImportacion
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.negocio.avance_mes import (
    avanzar_mes, pedidos_activos_vencidos, porcentaje_aumento_del_periodo, puede_avanzarse_mes,
)
from app.negocio.backup import (
    _ruta_base_datos,
    backup_vencido,
    carpeta_backup,
    generar_backup,
    listar_backups,
    modo_sin_sincronizar_activo,
    restaurar_backup_desde,
    ultimo_backup,
)
from app.negocio.dias import fecha_a_dia_semana, fecha_actual, fecha_real, periodo_actual
from app.negocio.formato import formatear_moneda, mes_texto, periodo_mm_aaaa
from app.negocio.control_pagos import resumen_conteo_vencimientos
from app.negocio.panel_control import (
    calcular_estadisticas_ocupacion,
    calcular_estadisticas_ocupacion_por_unidad,
    calcular_estadisticas_principales,
    calcular_estadisticas_profesionales,
    cumpleanos_y_dias_profesion_proximos,
    fechas_especiales_proximas_dos_meses,
)

_ANCHO_BOTON = 220
# SistemaDF v0.11.2026.10 ("Avance de período, backup, y vista rápida"):
# un tercio menos que el alto original (140px) — pedido explícito de la
# clienta, el espacio que se libera lo absorbe solo el cuadro de Alertas
# (stretch=1 en `layout_solapa`, a diferencia de la grilla, que no
# compite por ese espacio extra — ver `_armar_ui`). Se probó además
# fijarles un alto FIJO (`setFixedHeight`) a los seis cuadritos y
# subirle el piso a Alertas a mano con el excedente — la clienta
# confirmó, tras revisar una captura, que este valor nomás (el mínimo,
# como estaba pedido desde el principio) ya daba el resultado que
# quería; se revirtió esa parte para no complicar el mecanismo sin
# necesidad.
_ALTO_MINIMO_TARJETA = round(140 * 2 / 3)

_TEXTO_EXPLICACION_BACKUP = (
    "Generar backup ahora copia la base de datos y toda la carpeta de archivos generados a la carpeta de "
    "backup configurada, sin esperar a que se cumpla la frecuencia automática."
)
_TEXTO_EXPLICACION_RESTAURAR = (
    "Restaurar backup reemplaza la base de datos actual por un backup elegido de una carpeta de Google "
    "Drive — lo que se haya cargado después de ese backup se pierde. El programa se cierra al terminar; "
    "hay que volver a abrirlo para seguir trabajando con los datos restaurados."
)
_TEXTO_EXPLICACION_AVANZAR = (
    "Avanzar de mes realiza el pase de un mes a otro en el sistema. Este proceso ubica virtualmente al "
    "operador en el nuevo período cualquier sea la fecha real del día."
)

def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _seccion_estadisticas() -> tuple[QWidget, QVBoxLayout]:
    """Cada una de las tres cuentas de "Estadísticas principales mes en
    curso" (Liquidaciones/Resultado del negocio/Monto a cobrar) queda
    envuelta en su propio widget — sin ningún estilo propio, así que
    muestra el mismo gris default del cuadrito (`cuadritoInfo`) por
    detrás. Ronda anterior: este widget tenía fondo blanco y el espacio
    ENTRE cuentas quedaba gris liso; pedido explícito de la clienta en
    la ronda siguiente para invertir ese esquema: "todo lo que son las
    cuentas tiene que estar en gris, y las líneas intermedias en
    blanco, o sea al revés que ahora" — ver `_separador_estadisticas`,
    que es ahora el que lleva el fondo blanco."""
    seccion = QWidget()
    layout = QVBoxLayout(seccion)
    layout.setContentsMargins(6, 6, 6, 6)
    return seccion, layout


def _separador_estadisticas() -> QWidget:
    """Espacio ENTRE una cuenta y la siguiente, dentro de "Estadísticas
    principales mes en curso" — fondo blanco (objectName
    `separadorEstadisticas`, mismo `t['superficie']` que el resto de
    los fondos claros del sistema) y alto fijo, en vez del
    `addSpacing(12)` invisible que separaba las cuentas en la ronda
    anterior (cuando las cuentas en sí eran las que llevaban el fondo
    blanco). Sin separador antes de la primera cuenta ni después de la
    última — pedido explícito de la clienta: "eliminá esa línea en
    blanco inicial arriba de 'Liquidaciones mes en curso'" (esa misma
    línea era, antes de esta ronda, la que generaba el scroll vertical
    de más en el cuadrito: sacarla también lo saca)."""
    separador = QWidget()
    separador.setObjectName("separadorEstadisticas")
    separador.setFixedHeight(12)
    return separador


def _texto_explicacion(texto: str) -> QLabel:
    """Cuadro de texto fijo (borde negro) que explica un botón puntual —
    antes había uno solo para los dos botones, ahora hay uno por botón,
    alineado a su lado ("a la par del botón correspondiente")."""
    etiqueta = QLabel(texto)
    etiqueta.setWordWrap(True)
    etiqueta.setStyleSheet("border: 1px solid black; padding: 8px;")
    return etiqueta


def _texto_fecha_hora(momento: datetime, *, con_segundos: bool = False) -> str:
    """"vie 25-08-2026 14:45hs" — mismo criterio que las fechas de
    Registro de ausencias/Pagos (día de la semana abreviado + dd-MM-yyyy
    + hora), armado a mano porque acá el dato es un `datetime` de Python,
    no un campo de formulario con su propio `QDateEdit`."""
    dia = fecha_a_dia_semana(momento.date())[:3].lower()
    hora = f"{momento.hour:02d}:{momento.minute:02d}"
    if con_segundos:
        hora += f":{momento.second:02d}"
    return f"{dia} {momento.day:02d}-{momento.month:02d}-{momento.year} {hora}hs"


def _texto_fecha(fecha_iso: str) -> str:
    """"vie 25-08-2026" — mismo criterio que `_texto_fecha_hora`, sin la
    hora (el dato es una fecha sola, AAAA-MM-DD, como la de `FechasEspeciales.
    Fecha`). Pedido explícito de la clienta para el cuadrito "Feriados y
    fechas especiales próximas" ("ddd dd-mm-yyyy")."""
    fecha = date.fromisoformat(fecha_iso)
    dia = fecha_a_dia_semana(fecha)[:3].lower()
    return f"{dia} {fecha.day:02d}-{fecha.month:02d}-{fecha.year}"


def _resaltar_si_es_hoy(linea_html: str, es_hoy: bool) -> str:
    """Pedido explícito de la clienta: el cumpleaños/día de profesión/
    feriado que cae justo HOY (fecha real, no la del período — ver
    `fecha_real`) se resalta en rojo y negrita en los cuadritos de Panel
    de control. `linea_html` ya viene con cualquier texto dinámico
    (Descripción, nombre del profesional) escapado (`html.escape`) por
    el llamador — acá solo se decide si hace falta envolverla."""
    if not es_hoy:
        return linea_html
    return f'<span style="color: {COLOR_ROJO}; font-weight: bold;">{linea_html}</span>'


def _agregar_contenido_escrolable(layout: QVBoxLayout, contenido: QWidget) -> None:
    """Punto 78 (SistemaDF v0.11.2026.10): cada cuadrito tiene que ser
    escroleable EN VERTICAL de forma individual si su contenido no
    entra en el alto parejo de la grilla (`_ALTO_MINIMO_TARJETA`), sin
    afectar el alto de los demás — un `QScrollArea` propio por cuadrito,
    envolviendo el `QLabel` (o el contenedor de varios) en vez de
    agregarlo directo al layout del cuadrito.

    Punto 81 (misma versión): dos retoques pedidos por la clienta sobre
    esa misma pieza, para que el contenido se vea igual que el resto del
    cuadrito, no como "una caja adentro de otra":
    - Fondo transparente del viewport interno del `QScrollArea` (el
      widget que Qt arma solo al llamar `setWidget`, no accesible por
      objectName — hay que tocarlo directo vía `.viewport()`): sin esto,
      el viewport pinta su fondo con el color de la paleta (`QPalette.
      ColorRole.Base`, que `QAbstractScrollArea` le fija por default con
      `autoFillBackground` activado) — en modo claro, `paleta()` no toca
      ese rol, así que cae al gris de sistema; en modo oscuro, el `Base`
      que sí fija `paleta()` no es necesariamente el mismo tono que el
      `superficie` de `QWidget#panelSolapa`/`QFrame#cuadritoInfo` — quedaba
      un recuadro de color distinto adentro del cuadrito. Se resuelve con
      `setAutoFillBackground(False)` (no con un stylesheet: un
      `setStyleSheet("background: transparent;")` en el cuadrito de
      Alertas, con sus propias tarjetas de alerta anidadas adentro,
      terminaba pisando el fondo naranja/letra blanca de los títulos de
      cada alerta — un stylesheet puesto en un ancestro le cambia el
      motor de pintado a TODOS los descendientes, aunque tengan su propio
      selector por objectName; `autoFillBackground` no toca ningún
      stylesheet, así que no corre ese riesgo).
    - Alineación arriba (`AlignLeft | AlignTop`) en el `QLabel` de
      contenido: con `setWidgetResizable(True)`, Qt estira ese `QLabel`
      al alto completo del viewport, y la alineación VERTICAL default de
      `QLabel` es centrada (`AlignVCenter`) — un cuadrito con poco texto
      lo mostraba centrado en vez de arriba. No aplica al contenedor de
      "Período actual y último backup" (un `QWidget` con su propio
      `QVBoxLayout` + `addStretch()` al final, que ya empuja todo arriba
      por su cuenta)."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.viewport().setAutoFillBackground(False)
    if isinstance(contenido, QLabel):
        contenido.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    scroll.setWidget(contenido)
    layout.addWidget(scroll, stretch=1)


def _tarjeta(titulo: str) -> tuple[QFrame, QVBoxLayout]:
    """Cuadrito informativo: UN solo borde negro alrededor de todo el
    cuadrito (mismo criterio que el cuadro de texto de los botones) — el
    título y el contenido de abajo son texto plano sin caja propia,
    nunca cuadritos anidados. El estilo se aplica con un selector por
    objectName (`QFrame#cuadritoInfo`), no por clase (`QFrame` a secas):
    `QLabel` hereda de `QFrame` en Qt, así que un selector de clase sin
    acotar terminaba pintándole el mismo borde a los QLabel de adentro
    (título y contenido) — el bug que la clienta señaló como "cuadritos
    dentro de los cuadros". Título en negrita e itálica y terminado en
    ":", pedido explícito de la clienta; altura mínima pareja para que
    los seis cuadritos principales queden del mismo alto sin importar
    cuánto contenido tenga cada uno."""
    tarjeta = QFrame()
    tarjeta.setObjectName("cuadritoInfo")
    tarjeta.setStyleSheet("QFrame#cuadritoInfo { border: 1px solid black; }")
    tarjeta.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    tarjeta.setMinimumHeight(_ALTO_MINIMO_TARJETA)
    layout = QVBoxLayout(tarjeta)
    encabezado = QLabel(f"{titulo}:")
    encabezado.setStyleSheet("font-style: italic; font-weight: bold;")
    layout.addWidget(encabezado)
    return tarjeta, layout


class PanelControl(QWidget):
    """Contenedor de afuera: título Nivel 1 fijo ("Panel de control") +
    las dos solapas (`_PanelAvancePeriodo`/`_PanelImportacion`, ver
    docstring del módulo).

    El título mostró el nombre del espacio en vez del nombre de la
    pantalla desde la revisión "uno por uno" (pedido explícito de la
    clienta, cuando esta pantalla funcionaba como portada del sistema)
    hasta el reordenamiento de formularios: al pasar a ser un formulario
    más entre otros en el menú, se volvió a "Panel de control" para
    quedar coherente con el resto (todas las demás pantallas muestran
    su propio nombre, no el del espacio)."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def _armar_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.titulo = QLabel("Panel de control".upper())
        self.titulo.setObjectName("tituloPantalla")
        layout.addWidget(self.titulo)

        solapas = QTabWidget()
        self.panel_avance = _PanelAvancePeriodo(self.conn)
        solapas.addTab(self.panel_avance, "Avance de período, backup, y vista rápida")
        self.panel_importacion = _PanelImportacion(self.conn)
        solapas.addTab(self.panel_importacion, "Importación datos desde Excel")
        solapas.tabBar().setDrawBase(False)
        layout.addWidget(solapas, stretch=1)

    def actualizar(self) -> None:
        self.panel_avance.actualizar()


class _PanelAvancePeriodo(QWidget):
    """Solapa "Avance de período y backups": todo lo que antes era el
    contenido único de Panel de control (botones, grilla de cuadritos,
    alertas) — ver docstring del módulo para el detalle de cada vuelta de
    revisión."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setObjectName("panelSolapa")
        self.conn = conn
        self._armar_ui()
        self.actualizar()

    def showEvent(self, event) -> None:  # noqa: N802
        """Mismo motivo que en Estadísticas/Liquidación/Reservas: el foco
        pedido durante la construcción no alcanza a "pegar" porque el
        QTabWidget contenedor todavía no está mostrado en ese momento."""
        super().showEvent(event)
        self.boton_backup.setFocus()

    def reiniciar(self) -> None:
        """F5: esta solapa no tiene ningún filtro propio que el operador
        pueda haber cambiado (los seis cuadritos y las alertas son puro
        estado calculado, siempre al día) — alcanza con refrescar esos
        datos y devolver el foco al primer botón, igual que `showEvent`."""
        self.actualizar()
        self.boton_backup.setFocus()

    def _armar_ui(self) -> None:
        layout_solapa = QVBoxLayout(self)

        # Aviso permanente mientras esta instalación esté en "modo local,
        # sin sincronizar" (ver app.negocio.backup, sección "Backup y
        # sincronización" de CLAUDE.md) — oculto en el caso normal,
        # self.actualizar() lo muestra/oculta según corresponda. No es un
        # cartel que se cierra y se olvida: tiene que seguir ahí mientras
        # el modo esté activo.
        self.etiqueta_modo_sin_sincronizar = QLabel(
            "MODO LOCAL, SIN SINCRONIZAR — los backups están deshabilitados en esta instalación. "
            "Restaurá la versión sincronizada desde Google Drive en cuanto puedas."
        )
        self.etiqueta_modo_sin_sincronizar.setWordWrap(True)
        self.etiqueta_modo_sin_sincronizar.setStyleSheet(
            f"background-color: {COLOR_ROJO}; color: {COLOR_TEXTO_CLARO}; font-weight: bold; padding: 8px;"
        )
        self.etiqueta_modo_sin_sincronizar.setVisible(False)
        layout_solapa.addWidget(self.etiqueta_modo_sin_sincronizar)

        # Orden invertido a pedido de la clienta: "Generar backup ahora"
        # arriba, "Avanzar de mes" abajo — y este último vuelve a ser el
        # botonPrimario de la pantalla (el otro queda botonSecundario).
        # Cada botón va en su propia fila junto con SU explicación (antes
        # era un único cuadro de texto para los dos) — pedido explícito
        # de la clienta: "que queden a la par del botón correspondiente".
        self.boton_backup = QPushButton("Generar backup ahora")
        self.boton_backup.setObjectName("botonSecundario")
        self.boton_backup.setFixedWidth(_ANCHO_BOTON)
        self.boton_backup.clicked.connect(self._generar_backup)
        self.etiqueta_explicacion_backup = _texto_explicacion(_TEXTO_EXPLICACION_BACKUP)
        fila_backup = QHBoxLayout()
        fila_backup.addWidget(self.boton_backup, alignment=Qt.AlignmentFlag.AlignTop)
        fila_backup.addWidget(self.etiqueta_explicacion_backup, stretch=1)

        # Par del botón de arriba — pedido explícito de la clienta, mismo
        # ancho/criterio de fila (botón + su propia explicación al lado).
        self.boton_restaurar = QPushButton("Restaurar backup")
        self.boton_restaurar.setObjectName("botonSecundario")
        self.boton_restaurar.setFixedWidth(_ANCHO_BOTON)
        self.boton_restaurar.clicked.connect(self._restaurar_backup)
        self.etiqueta_explicacion_restaurar = _texto_explicacion(_TEXTO_EXPLICACION_RESTAURAR)
        fila_restaurar = QHBoxLayout()
        fila_restaurar.addWidget(self.boton_restaurar, alignment=Qt.AlignmentFlag.AlignTop)
        fila_restaurar.addWidget(self.etiqueta_explicacion_restaurar, stretch=1)

        self.boton_avanzar = QPushButton("Avanzar de mes")
        self.boton_avanzar.setObjectName("botonPrimario")
        self.boton_avanzar.setFixedWidth(_ANCHO_BOTON)
        self.boton_avanzar.clicked.connect(self._avanzar_mes)
        self.etiqueta_explicacion_avanzar = _texto_explicacion(_TEXTO_EXPLICACION_AVANZAR)
        fila_avanzar = QHBoxLayout()
        fila_avanzar.addWidget(self.boton_avanzar, alignment=Qt.AlignmentFlag.AlignTop)
        fila_avanzar.addWidget(self.etiqueta_explicacion_avanzar, stretch=1)

        layout_solapa.addLayout(fila_backup)
        layout_solapa.addLayout(fila_restaurar)
        layout_solapa.addWidget(_linea_divisoria())
        layout_solapa.addLayout(fila_avanzar)

        # Seis cuadritos principales, todos del mismo ancho (dos filas de
        # tres) — sin la de Alertas, que va aparte ocupando todo el ancho
        # de la pantalla, ver abajo. Punto 81 (SistemaDF v0.11.2026.10):
        # "Último backup" se funde dentro de "Período actual" (un
        # cuadrito "Período actual y último backup", ver `_armar_tarjeta_
        # periodo_y_backup`) y el cuadrito que libera pasa a "Estadísticas
        # principales mes en curso" — sigue en 6 cuadritos, en el orden
        # pedido explícito: Período actual y último backup, Estadísticas
        # principales, Ocupación y horas / Profesionales, Feriados y
        # fechas especiales, Cumpleaños y días de profesión.
        #
        # Punto 82 (misma versión, segunda vuelta sobre esta solapa):
        # pedido explícito de la clienta — repartir TODO el alto que
        # queda debajo de "Avanzar de mes" en tres franjas iguales
        # (primera fila de tres cuadritos, segunda fila de tres, Alertas),
        # no que Alertas absorba "lo que sobra" después de que la grilla
        # tome lo que necesita. Antes las dos filas vivían en un único
        # `QGridLayout` agregado a `layout_solapa` SIN stretch propio,
        # compitiendo con Alertas (`stretch=1`) — un ítem sin stretch
        # explícito en un `QBoxLayout` no crece más allá de lo que pida
        # su contenido aunque tenga política `Expanding`, así que las dos
        # filas quedaban achicadas a su tamaño "natural" y Alertas se
        # llevaba todo el resto, en vez de quedar las tres parejas. Ahora
        # son tres ítems HERMANOS de `layout_solapa` (`fila_tarjetas_1`/
        # `fila_tarjetas_2`/la tarjeta de Alertas), cada uno con
        # `stretch=1` explícito — con el mismo stretch Y el mismo
        # `_ALTO_MINIMO_TARJETA` de piso en los tres, `QBoxLayout` reparte
        # cualquier espacio de sobra en partes iguales entre los tres,
        # así terminan siempre del mismo alto (verificado armando la
        # pantalla real y midiendo alto en píxeles, no solo leyendo el
        # código — ver docs/historial para el detalle de la ronda).
        # Rediseño (ver docstring del módulo): dos columnas de tres
        # cuadritos chicos cada una, más una tercer columna de un solo
        # cuadro LARGO — las tres columnas con el mismo stretch, así
        # quedan del mismo ancho, y la columna larga queda del alto de
        # las otras dos (3 cuadritos chicos + el espaciado entre ellos).
        columna_1 = QVBoxLayout()
        columna_1.addWidget(self._armar_tarjeta_periodo_y_backup(), stretch=1)
        columna_1.addWidget(self._armar_tarjeta_profesionales(), stretch=1)
        columna_1.addWidget(self._armar_tarjeta_control_pagos(), stretch=1)

        columna_2 = QVBoxLayout()
        columna_2.addWidget(self._armar_tarjeta_ocupacion(), stretch=1)
        columna_2.addWidget(self._armar_tarjeta_fechas_especiales(), stretch=1)
        columna_2.addWidget(self._armar_tarjeta_cumpleanos(), stretch=1)

        fila_columnas = QHBoxLayout()
        fila_columnas.addLayout(columna_1, stretch=1)
        fila_columnas.addLayout(columna_2, stretch=1)
        fila_columnas.addWidget(self._armar_tarjeta_estadisticas_principales(), stretch=1)
        layout_solapa.addLayout(fila_columnas, stretch=1)

        self._foco = instalar_enter_avanza_foco(
            [self.boton_backup, self.boton_restaurar, self.boton_avanzar], parent=self,
        )

        self._fecha_ultima_actualizacion = datetime.now().date()
        self._timer_reloj = QTimer(self)
        self._timer_reloj.timeout.connect(self._actualizar_reloj)
        self._timer_reloj.start(1000)
        self._actualizar_reloj()

    # ------------------------------------------------------------ tarjetas

    def _actualizar_reloj(self) -> None:
        """Hora real del sistema, no la fecha ficticia de QA — un reloj en
        vivo tiene que mostrar la hora real para orientar al operador,
        aunque el resto de la pantalla esté calculando sobre una fecha
        simulada.

        Pedido explícito de la clienta: si el sistema queda abierto de
        un día para el otro sin que nadie toque nada (sin F5, sin salir
        y volver a entrar a la solapa), el resto del contenido de esta
        pantalla — en particular el resaltado en rojo de "hoy" en
        Cumpleaños/Fechas especiales (`_resaltar_si_es_hoy`, que
        depende de `fecha_real`/`date.today()`) — quedaba "anclado" al
        día en que se había llamado `actualizar()` por última vez,
        porque nada volvía a llamarlo solo con el paso del tiempo. Este
        timer YA corre cada un segundo para el reloj en vivo; en vez de
        sumar un timer nuevo, alcanza con comparar la fecha real contra
        la última vez que se refrescó el contenido completo y, si
        cambió (cruzó la medianoche), disparar un `actualizar()`
        completo una sola vez — no hace falta recalcular todo cada
        segundo, solo el día en que efectivamente cambia."""
        ahora = datetime.now()
        self.etiqueta_reloj.setText(_texto_fecha_hora(ahora, con_segundos=True))
        if ahora.date() != self._fecha_ultima_actualizacion:
            self._fecha_ultima_actualizacion = ahora.date()
            self.actualizar()

    def _armar_tarjeta_periodo_y_backup(self) -> QFrame:
        """Punto 76 (vuelta anterior): unifica "Fecha y hora actual" dentro
        de "Período actual" (período arriba, fecha/hora real debajo).
        Punto 81 (esta vuelta, pedido explícito de la clienta): el
        cuadrito "Último backup" entero se funde ACÁ TAMBIÉN, debajo de lo
        anterior, para que quede todo junto en un solo cuadrito "Período
        actual y último backup" — se mantiene intacta la información del
        cuadrito de período (arriba) y se agrega debajo, sin cambios, la
        del cuadrito de backup (antes aparte)."""
        tarjeta, layout = _tarjeta("Período actual y último backup")
        contenido = QWidget()
        layout_contenido = QVBoxLayout(contenido)
        layout_contenido.setContentsMargins(0, 0, 0, 0)
        self.etiqueta_periodo = QLabel()
        layout_contenido.addWidget(self.etiqueta_periodo)
        self.etiqueta_reloj = QLabel()
        layout_contenido.addWidget(self.etiqueta_reloj)
        self.etiqueta_backup = QLabel()
        self.etiqueta_backup.setWordWrap(True)
        layout_contenido.addWidget(self.etiqueta_backup)
        # Separada de `etiqueta_backup` (pedido explícito de la clienta):
        # cuando el backup está vencido, SOLO esta línea pasa a mayúscula/
        # roja/negrita — las otras dos (Último backup/Frecuencia) siguen
        # con el estilo normal, así que no puede ser parte del mismo texto
        # plano de `etiqueta_backup`.
        self.etiqueta_estado_backup = QLabel()
        self.etiqueta_estado_backup.setWordWrap(True)
        layout_contenido.addWidget(self.etiqueta_estado_backup)
        layout_contenido.addStretch()
        _agregar_contenido_escrolable(layout, contenido)
        return tarjeta

    def _armar_tarjeta_estadisticas_principales(self) -> QFrame:
        """Rediseño completo (ronda siguiente a la del punto 81), pedido
        explícito de la clienta — tres cuentas en cascada (ver `app.
        negocio.panel_control.EstadisticasPrincipales` para las
        fórmulas, derivadas exactamente de `Liquidacion.monto_generado`
        para que "Total liquidado mes en curso" cierre siempre con la
        suma real de las liquidaciones emitidas del período). Cada una
        queda envuelta en su propia `_seccion_estadisticas`, separadas
        entre sí por `_separador_estadisticas` (fondo blanco) — pedido
        explícito de la clienta para diferenciarlas visualmente.

        Ronda siguiente, pedido explícito de la clienta: "en las tres
        secciones elimina la línea divisoria y el título de cada
        subtotal. El importe quiero que aparezca dentro de cada
        título" — el subtítulo plano de cada sección ("Liquidaciones
        mes en curso"/"Resultado del negocio"/"Monto a cobrar en el mes
        en curso") y la línea divisoria desaparecen; el título del
        subtotal (en negrita, ya con su importe) pasa a ser el título
        de la sección entera, ARRIBA de las líneas de detalle (que no
        cambian de contenido, solo de posición: ya no van después del
        subtotal, van después de este título combinado). Dos de los
        tres títulos conservan el texto que ya tenían como subtotal
        ("Total liquidado mes en curso"/"Balance del negocio"); el
        tercero se renombra a pedido explícito ("Saldo a cobrar del mes
        en curso", antes "Monto restante del mes a cobrar"):

        - "Total liquidado mes en curso": los ocho conceptos que
          componen una liquidación (más "Otros ajustes", la bolsa de
          conceptos raros sin línea propia).
        - "Balance del negocio": lo liquidado más lo que generan los
          profesionales A por fuera de cualquier liquidación (aisladas,
          extraordinarias, llaves/cargos), menos los gastos operativos
          del período.
        - "Saldo a cobrar del mes en curso": lo mismo de arriba menos lo
          efectivamente cobrado hasta el momento (acotado por
          profesional, sin contar excedentes)."""
        tarjeta, layout = _tarjeta("Estadísticas principales mes en curso")
        contenido = QWidget()
        layout_contenido = QVBoxLayout(contenido)
        layout_contenido.setContentsMargins(0, 0, 0, 0)

        seccion_liquidaciones, layout_liquidaciones = _seccion_estadisticas()
        self.etiqueta_total_liquidado = QLabel()
        self.etiqueta_total_liquidado.setStyleSheet("font-weight: bold;")
        layout_liquidaciones.addWidget(self.etiqueta_total_liquidado)
        self.etiqueta_detalle_liquidaciones = QLabel()
        self.etiqueta_detalle_liquidaciones.setWordWrap(True)
        layout_liquidaciones.addWidget(self.etiqueta_detalle_liquidaciones)
        layout_contenido.addWidget(seccion_liquidaciones)

        layout_contenido.addWidget(_separador_estadisticas())

        seccion_resultado, layout_resultado = _seccion_estadisticas()
        self.etiqueta_balance_negocio = QLabel()
        self.etiqueta_balance_negocio.setStyleSheet("font-weight: bold;")
        layout_resultado.addWidget(self.etiqueta_balance_negocio)
        self.etiqueta_detalle_resultado = QLabel()
        self.etiqueta_detalle_resultado.setWordWrap(True)
        layout_resultado.addWidget(self.etiqueta_detalle_resultado)
        layout_contenido.addWidget(seccion_resultado)

        layout_contenido.addWidget(_separador_estadisticas())

        seccion_cobro, layout_cobro = _seccion_estadisticas()
        self.etiqueta_monto_restante_a_cobrar = QLabel()
        self.etiqueta_monto_restante_a_cobrar.setStyleSheet("font-weight: bold;")
        layout_cobro.addWidget(self.etiqueta_monto_restante_a_cobrar)
        self.etiqueta_detalle_cobro = QLabel()
        self.etiqueta_detalle_cobro.setWordWrap(True)
        layout_cobro.addWidget(self.etiqueta_detalle_cobro)
        layout_contenido.addWidget(seccion_cobro)

        layout_contenido.addStretch()
        _agregar_contenido_escrolable(layout, contenido)
        return tarjeta

    def _armar_tarjeta_fechas_especiales(self) -> QFrame:
        tarjeta, layout = _tarjeta("Feriados y fechas especiales próximas")
        self.etiqueta_fechas_especiales = QLabel()
        self.etiqueta_fechas_especiales.setWordWrap(True)
        # Texto enriquecido: pedido explícito de la clienta, el feriado/
        # fecha especial que cae justo hoy (fecha real, no la del período)
        # se resalta en rojo y negrita — ver `actualizar()`.
        self.etiqueta_fechas_especiales.setTextFormat(Qt.TextFormat.RichText)
        _agregar_contenido_escrolable(layout, self.etiqueta_fechas_especiales)
        return tarjeta

    def _armar_tarjeta_profesionales(self) -> QFrame:
        tarjeta, layout = _tarjeta("Profesionales")
        self.etiqueta_profesionales = QLabel()
        self.etiqueta_profesionales.setWordWrap(True)
        _agregar_contenido_escrolable(layout, self.etiqueta_profesionales)
        return tarjeta

    def _armar_tarjeta_ocupacion(self) -> QFrame:
        """Punto 81: el monto generado por aisladas y el saldo pendiente
        se sacan de este cuadrito (ahora viven en "Estadísticas
        principales mes en curso", sin duplicarse) — quedan los tres
        conceptos de ocupación/horas generales, y debajo, repetidos para
        cada Unidad del sistema (`calcular_estadisticas_ocupacion_por_
        unidad`), pedido explícito de la clienta."""
        tarjeta, layout = _tarjeta("Ocupación y horas mes en curso")
        self.etiqueta_ocupacion = QLabel()
        self.etiqueta_ocupacion.setWordWrap(True)
        _agregar_contenido_escrolable(layout, self.etiqueta_ocupacion)
        return tarjeta

    def _armar_tarjeta_cumpleanos(self) -> QFrame:
        tarjeta, layout = _tarjeta("Cumpleaños y días de profesión")
        self.etiqueta_cumpleanos = QLabel()
        self.etiqueta_cumpleanos.setWordWrap(True)
        # Mismo motivo que etiqueta_fechas_especiales: el cumpleaños/día
        # de profesión que cae justo hoy se resalta en rojo y negrita.
        self.etiqueta_cumpleanos.setTextFormat(Qt.TextFormat.RichText)
        _agregar_contenido_escrolable(layout, self.etiqueta_cumpleanos)
        return tarjeta

    def _armar_tarjeta_control_pagos(self) -> QFrame:
        """Pedido explícito de la clienta: réplica de las siete etiquetas
        de conteo de "Carga y control" (`_PanelCargaControl`, `app/gui/
        pantallas/control_pagos.py`) — mismos siete números, calculados
        acá sin filtro (`resumen_conteo_vencimientos`, `app.negocio.
        control_pagos`, ver su docstring: mismo alcance que la tabla de
        esa solapa, pero sin los cuatro filtros que ahí sí se aplican).
        "Con vencimiento hoy"/"Con vencimiento mañana" van en rojo y
        negrita cuando hay al menos uno — pedido explícito, a diferencia
        del resto de las líneas, que quedan en texto plano siempre."""
        tarjeta, layout = _tarjeta("Control de pagos")
        self.etiqueta_control_pagos = QLabel()
        self.etiqueta_control_pagos.setWordWrap(True)
        self.etiqueta_control_pagos.setTextFormat(Qt.TextFormat.RichText)
        _agregar_contenido_escrolable(layout, self.etiqueta_control_pagos)
        return tarjeta

    def actualizar(self) -> None:
        ruta_db = _ruta_base_datos(self.conn)
        self.etiqueta_modo_sin_sincronizar.setVisible(
            ruta_db is not None and modo_sin_sincronizar_activo(ruta_db)
        )

        periodo = periodo_actual(self.conn)
        anio, mes = (int(p) for p in periodo.split("-"))
        self.etiqueta_periodo.setText(f"{mes_texto(mes).capitalize()} de {anio} ({periodo_mm_aaaa(periodo)})")

        momento_backup = ultimo_backup(self.conn)
        frecuencia = self.conn.execute(
            "SELECT FrecuenciaBackupDrive FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()["FrecuenciaBackupDrive"]
        lineas_backup = [
            f"Último backup: {_texto_fecha_hora(momento_backup)}" if momento_backup is not None
            else "Todavía no se generó ningún backup.",
            f"Frecuencia configurada: {frecuencia}" if frecuencia else "Frecuencia configurada: sin definir",
        ]
        self.etiqueta_backup.setText("\n".join(lineas_backup))

        if carpeta_backup(self.conn) is None:
            self.etiqueta_estado_backup.setText("")
            self.etiqueta_estado_backup.setStyleSheet("")
        elif backup_vencido(self.conn, fecha_actual(self.conn)):
            self.etiqueta_estado_backup.setText("ESTADO: VENCIDO")
            self.etiqueta_estado_backup.setStyleSheet(f"color: {COLOR_ROJO}; font-weight: bold;")
        else:
            self.etiqueta_estado_backup.setText("Estado: al día")
            self.etiqueta_estado_backup.setStyleSheet("")

        hoy_real = fecha_real(self.conn)
        fechas = fechas_especiales_proximas_dos_meses(self.conn)
        if fechas:
            texto_fechas = "<br>".join(
                _resaltar_si_es_hoy(
                    f"•  {_texto_fecha(f['Fecha'])} — {escape(f['Descripcion'] or f['Tipo'] or 'Sin descripción')}",
                    date.fromisoformat(f["Fecha"]) == hoy_real,
                )
                for f in fechas
            )
        else:
            texto_fechas = "Sin fechas especiales cargadas para lo que resta del período."
        self.etiqueta_fechas_especiales.setText(texto_fechas)

        prof = calcular_estadisticas_profesionales(self.conn)
        self.etiqueta_profesionales.setText(
            f"Con plan de pago vigente: {prof.con_plan_pago_vigente}\n"
            f"Con saldo fuera de tolerancia: {prof.con_saldo_fuera_de_tolerancia}\n"
            f"Con reservas regulares activas: {prof.con_reservas_regulares_activas}\n"
            f"Con reservas aisladas activas: {prof.con_reservas_aisladas_activas}\n"
            f"Horarios incorporados para el mes próximo: {prof.horarios_incorporados_proximo_periodo:.1f}hs\n"
            f"Horarios liberados para el mes próximo: {prof.horarios_liberados_proximo_periodo:.1f}hs\n"
            f"Diferencia: {prof.diferencia_horarios_proximo_periodo:+.1f}hs"
        )

        principales = calcular_estadisticas_principales(self.conn)
        desglose = principales.desglose_liquidaciones
        fuera = principales.desglose_fuera_liquidacion
        self.etiqueta_detalle_liquidaciones.setText(
            f"Monto neto reservas regulares: {formatear_moneda(desglose.monto_neto_reservas_regulares)}\n"
            f"Descuentos por feriados no trabajados: {formatear_moneda(desglose.descuento_feriados)}\n"
            f"Descuentos por vacaciones: {formatear_moneda(desglose.descuento_vacaciones)}\n"
            f"Descuentos por licencias: {formatear_moneda(desglose.descuento_licencias)}\n"
            f"Reservas aisladas: {formatear_moneda(desglose.aisladas_en_liquidaciones)}\n"
            f"Feriados trabajados: {formatear_moneda(desglose.feriados_trabajados)}\n"
            f"Cargos especiales: {formatear_moneda(desglose.cargos_especiales)}\n"
            f"Cuotas de planes de pago: {formatear_moneda(desglose.cuotas_planes_pago)}\n"
            f"Otros ajustes: {formatear_moneda(desglose.otros_ajustes)}"
        )
        self.etiqueta_total_liquidado.setText(
            f"Total liquidado mes en curso: {formatear_moneda(principales.total_liquidado)}"
        )

        self.etiqueta_detalle_resultado.setText(
            f"Total liquidado mes en curso: {formatear_moneda(principales.total_liquidado)}\n"
            f"Horas aisladas por fuera de la liquidación: {formatear_moneda(fuera.aisladas_normales)}\n"
            f"Reservas extraordinarias por fuera de la liquidación: {formatear_moneda(fuera.reservas_extraordinarias)}\n"
            f"Otros conceptos por fuera de la liquidación: {formatear_moneda(fuera.otros_conceptos)}\n"
            f"Gastos operativos: {formatear_moneda(-principales.gastos_operativos)}"
        )
        self.etiqueta_balance_negocio.setText(
            f"Balance del negocio: {formatear_moneda(principales.balance_negocio)}"
        )

        self.etiqueta_detalle_cobro.setText(
            f"Monto liquidado más horas aisladas: {formatear_moneda(principales.monto_a_cobrar_base)}\n"
            f"Monto cobrado hasta el momento: {formatear_moneda(-principales.monto_cobrado)}"
        )
        self.etiqueta_monto_restante_a_cobrar.setText(
            f"Saldo a cobrar del mes en curso: {formatear_moneda(principales.monto_restante_a_cobrar)}"
        )

        ocup = calcular_estadisticas_ocupacion(self.conn)
        lineas_ocupacion = [
            f"Ocupación regular general: {ocup.ocupacion_regular_pct:.1f}%",
            f"Cantidad horas regulares semanales mes en curso: {ocup.horas_regulares_semanales:.1f}hs",
            f"Cantidad horas aisladas mensuales: {ocup.horas_aisladas_mes:.1f}hs",
        ]
        for unidad in calcular_estadisticas_ocupacion_por_unidad(self.conn):
            lineas_ocupacion.append(f"\n{unidad.nombre}:")
            lineas_ocupacion.append(f"Ocupación regular general: {unidad.ocupacion_pct:.1f}%")
            lineas_ocupacion.append(
                f"Cantidad horas regulares semanales mes en curso: {unidad.horas_regulares_semanales:.1f}hs"
            )
            lineas_ocupacion.append(f"Cantidad horas aisladas mensuales: {unidad.horas_aisladas_mes:.1f}hs")
        self.etiqueta_ocupacion.setText("\n".join(lineas_ocupacion))

        eventos = cumpleanos_y_dias_profesion_proximos(self.conn)
        if eventos:
            # Punto 80: "ddd dd-mm" con el día de la semana abreviado,
            # mismo criterio que el resto del sistema (ver 1.10).
            texto_eventos = "<br>".join(
                _resaltar_si_es_hoy(
                    f"•  {fecha_a_dia_semana(e.fecha_proxima)[:3].lower()} "
                    f"{e.fecha_proxima.day:02d}-{e.fecha_proxima.month:02d} — {escape(e.descripcion)}",
                    e.fecha_proxima == hoy_real,
                )
                for e in eventos
            )
        else:
            texto_eventos = "Sin cumpleaños ni días de profesión para lo que resta del período."
        self.etiqueta_cumpleanos.setText(texto_eventos)

        self._actualizar_tarjeta_control_pagos()

    def _actualizar_tarjeta_control_pagos(self) -> None:
        resumen = resumen_conteo_vencimientos(self.conn)

        def _linea(etiqueta: str, clave: str, *, resaltar: bool = False) -> str:
            texto = f"{etiqueta}: {resumen[clave]}"
            if resaltar and resumen[clave] > 0:
                return f'<span style="color:{COLOR_ROJO}; font-weight:bold;">{texto}</span>'
            return texto

        self.etiqueta_control_pagos.setText("<br>".join([
            _linea("Conceptos por cargar", "por_cargar"),
            _linea("Con vencimiento hoy", "vencimiento_hoy", resaltar=True),
            _linea("Con vencimiento mañana", "vencimiento_mañana", resaltar=True),
            _linea("Con vencimiento en días", "vencimiento_en_dias"),
            _linea("Con vencimiento vencido", "vencimiento_vencido"),
            _linea("Conceptos archivados", "archivados"),
            _linea("Total conceptos", "total"),
        ]))

    def _avanzar_mes(self) -> None:
        periodo = periodo_actual(self.conn)

        if not puede_avanzarse_mes(self.conn):
            QMessageBox.information(
                self, "Avanzar de mes",
                f"Ya estás parado en el período {periodo}, un mes por delante de la fecha real de hoy. "
                "No se puede avanzar más de un período hasta que la fecha real alcance ese mes.",
            )
            return

        if porcentaje_aumento_del_periodo(self.conn, periodo) is None:
            respuesta_aumento = QMessageBox.question(
                self, "Avanzar de mes",
                f"¿Querés evaluar un aumento de valores para el período {periodo} antes de avanzar de mes?\n\n"
                "Elegí \"No\" para saltear este paso y avanzar directamente.",
            )
            if respuesta_aumento == QMessageBox.StandardButton.Yes:
                QMessageBox.information(
                    self, "Avanzar de mes",
                    "Se canceló el avance. Confirmá el aumento desde \"Aumentos y descuentos\" y volvé "
                    "a \"Avanzar de mes\" cuando termines.",
                )
                return

        confirmacion = QMessageBox.question(
            self, "Avanzar de mes",
            f"¿Confirmás el avance de mes para el período {periodo}? Esta acción traspasa saldos, "
            f"cierra cuotas y genera el snapshot mensual.",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return

        vencidos = pedidos_activos_vencidos(self.conn)
        eliminar_vencidos = False
        if vencidos:
            cantidad = len(vencidos)
            pedido_o_pedidos = "pedido" if cantidad == 1 else "pedidos"
            respuesta_vencidos = QMessageBox.question(
                self, "Lista de espera — pedidos vencidos",
                f"Hay {cantidad} {pedido_o_pedidos} Activo(s) en Lista de espera vencidos: superaron la "
                "retención configurada en Configuración. ¿Confirmás eliminarlos ahora?\n\n"
                "Si elegís \"No\" se conservan un tiempo más: podés eliminarlos a mano cuando quieras "
                "(descartando el pedido) o esperar a que se vuelva a avisar en un próximo avance de mes.",
            )
            eliminar_vencidos = respuesta_vencidos == QMessageBox.StandardButton.Yes

        resumen = avanzar_mes(
            self.conn, periodo_cerrado=periodo, eliminar_activos_vencidos_lista_espera=eliminar_vencidos,
        )
        self.conn.commit()
        mensaje_backup = (
            f"Backup previo generado en:\n{resumen.ruta_backup}\n\n" if resumen.backup_generado
            else "No se generó backup previo (falta configurar la carpeta de backup).\n\n"
        )
        mensaje_plazos = (
            f" Se aplicó el plazo extendido automático a {resumen.plazos_extendidos_automaticos_aplicados} "
            f"profesional(es)."
            if resumen.plazos_extendidos_automaticos_aplicados else ""
        )
        mensaje_fechas_especiales = (
            f" Se eliminaron {resumen.fechas_especiales_antiguas_eliminadas} feriado(s)/fecha(s) especial(es) "
            f"que ya no tienen efecto en liquidaciones nuevas."
            if resumen.fechas_especiales_antiguas_eliminadas else ""
        )
        QMessageBox.information(
            self, "Avance de mes completado",
            f"{mensaje_backup}Se traspasó el saldo de {resumen.profesionales_con_traspaso} profesional(es), se cerraron "
            f"{resumen.cuotas_cerradas} cuota(s) y se generó el snapshot #{resumen.id_snapshot}."
            f"{mensaje_plazos}{mensaje_fechas_especiales}",
        )
        self.actualizar()

    def _generar_backup(self) -> None:
        try:
            ruta = generar_backup(self.conn)
        except ValueError as error:
            QMessageBox.warning(self, "Generar backup", str(error))
            return
        QMessageBox.information(self, "Generar backup", f"Backup generado en:\n{ruta}")
        self.actualizar()

    def _restaurar_backup(self) -> None:
        """Restauración manual, a pedido — a diferencia de las dos vías
        automáticas de `gui_main.py` (instalación nueva / base
        desactualizada), acá el operador elige CUÁL backup restaurar, no
        siempre el más reciente (`listar_backups`, no `buscar_backup_
        mas_reciente`). Como la restauración reemplaza el archivo de la
        base en el lugar, hay que cerrar esta conexión (compartida por
        toda la ventana) antes de tocarlo — y como no hay forma segura de
        reabrir una conexión nueva y "pasarla" a todos los demás paneles
        ya construidos, la única salida consistente es cerrar el programa
        entero después: el sistema operativo libera el lock de instancia
        única solo con que el proceso termine (ver `BloqueoInstanciaUnica`),
        sin necesitar ningún código extra acá."""
        carpeta_sugerida = str(carpeta_backup(self.conn) or "")
        carpeta = QFileDialog.getExistingDirectory(
            self, "Elegir la carpeta de backups de Google Drive", carpeta_sugerida,
        )
        if not carpeta:
            return
        backups = listar_backups(Path(carpeta))
        if not backups:
            QMessageBox.warning(self, "Restaurar backup", f"No se encontró ningún backup en {carpeta}.")
            return
        nombres = [b.name for b in backups]
        nombre_elegido, confirmado = QInputDialog.getItem(
            self, "Restaurar backup", "Elegí qué backup restaurar (el más reciente aparece primero):",
            nombres, 0, False,
        )
        if not confirmado:
            return
        origen = backups[nombres.index(nombre_elegido)]
        if not list(origen.glob("*.db")):
            QMessageBox.warning(
                self, "Restaurar backup", f"El backup en {origen} no tiene ningún archivo de base de datos.",
            )
            return
        respuesta = QMessageBox.question(
            self, "Restaurar backup",
            f"Esto va a reemplazar la base de datos actual por el backup \"{origen.name}\" — lo que se "
            "haya cargado después de ese momento se va a perder.\n\n"
            "Después de restaurar, el programa se cierra — hay que volver a abrirlo para seguir trabajando "
            "con los datos restaurados.\n\n¿Confirmás?",
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        db_path = _ruta_base_datos(self.conn)
        if db_path is None:
            QMessageBox.warning(self, "Restaurar backup", "No se pudo determinar la ruta de la base de datos.")
            return
        self.conn.close()
        try:
            restaurar_backup_desde(origen, db_path)
        except ValueError as error:
            QMessageBox.warning(self, "Restaurar backup", str(error))
            return
        QMessageBox.information(
            self, "Restaurar backup", f"Se restauró: {origen.name}.\n\nEl programa se va a cerrar ahora.",
        )
        QApplication.instance().quit()
