# Convenciones de diseño de pantallas (GUI)

Definidas en la revisión "uno por uno" de cada formulario con la clienta.
Viven implementadas en `app/gui/estilos.py` (`hoja_estilos`), que es la
fuente de verdad — acá va un resumen para no tener que releer todo ese
docstring cada vez. Un cambio de estilo probado y aprobado en una pantalla
se lleva siempre a `estilos.py` para que aplique a todas (no se duplica
por pantalla), salvo que se diga explícitamente que es solo para una.

## Jerarquía de títulos

- **Nivel 1** — título de la pantalla entera (objectName `tituloPantalla`):
  18px, negrita, MAYÚSCULA (`.upper()` en el texto, QSS no soporta
  text-transform), itálica, color de texto normal (NO azul — se probó en
  azul primero, la clienta pidió negro).
- **Nivel 2** — nombre de la solapa/sección (una solapa real de
  `QTabWidget`, no una etiqueta simulándola; se muestra la barra de
  solapas aunque haya una sola). Texto 14px, negrita, sin itálica, color
  de texto normal. Apariencia de "ficha de papel":
  - Solapa ACTIVA: fondo en tono CLARO (`t['superficie']`), sin borde
    abajo (se funde con el panel de contenido).
  - Solapa INACTIVA: fondo en tono OSCURO (`t['fondo']`, el mismo fondo
    que el resto de la ventana), con todo el borde, y baja 2px para
    quedar "detrás" de la activa.
  - El panel de contenido (`QTabWidget::pane`) usa el mismo tono claro
    que la solapa activa.
  - Borde (pane y las dos solapas): NEGRO (`#000000`) — se probó en un
    gris oscuro a tono con la solapa inactiva al revisar Registro de
    ausencias, pero la clienta pidió volver al negro para todas las
    pantallas al revisar Vista rápida/Estadísticas ("como está en Lista
    de espera", la referencia visual del estilo).
  - **Importante:** el fondo claro de la solapa activa NO llega solo al
    widget de cada pestaña — hay que darle objectName `"panelSolapa"` al
    widget de más afuera que se pasa a `addTab(...)` (o al widget
    interno de un `QScrollArea` si la pestaña scrollea) para que la
    regla `QWidget#panelSolapa` lo pinte. Ya aplicado a todas las
    pantallas con solapas del sistema (Registro de ausencias, Cargos
    especiales, Pagos, Lista de espera, Liquidación mensual, Reservas,
    Placas, Vista rápida, Aumentos y descuentos, Catálogos) — cualquier
    pantalla nueva con `QTabWidget` tiene que sumarlo también.
  - **Regla general, no solo del widget de más afuera** (subida a
    convención a pedido explícito de la clienta al detectar el caso de
    "Archivos y listas" — ver "Panel izquierdo gris" más abajo para el
    diagnóstico técnico completo): la pestaña ACTIVA entera, y CUALQUIER
    contenedor intermedio dentro de ella (panel izquierdo de
    Buscar/botones, `panel_extra_*`, cualquier `QWidget` genérico sin
    estilo propio que envuelva parte del contenido), tiene que quedar
    del mismo tono claro que el resto del contenido — nunca más oscuro.
    Un `QWidget` sin objectName cae al gris default de Qt aunque esté
    anidado dentro de un widget que sí tiene `panelSolapa`, porque esa
    regla QSS no cascada a los hijos — hay que sumarle el objectName a
    CADA widget intermedio, no solo al de más afuera. Esto se va
    resolviendo pantalla por pantalla a medida que se revisa cada una
    (no un barrido completo de una sola vez, pedido explícito de la
    clienta) — ver la lista de pantallas armadas a mano todavía
    pendientes de este chequeo en "Panel izquierdo gris" más abajo.
  - Como referencia suelta (sin ser una solapa real), objectName
    `subtituloSeccion` da el mismo formato en un QLabel.
- **Nivel 3** — título de un campo/selector puntual (objectName
  `subtituloCampo`, ej. "Profesional" arriba de su combo): mismo peso que
  el texto normal, SIN negrita — se probó en negrita en Registro de
  ausencias y se descartó.

## Botones

- `botonPrimario` — azul fuerte (`COLOR_NIVEL_1`), texto blanco, para la
  acción más importante/definitiva del formulario (ej. "Crear pedido").
  Se probó pasarlo a gris oscuro fijo y se desestimó: queda en azul.
- `botonSecundario` — celeste suave, para el resto de las acciones, no
  tan definitivas (ej. "Modificar", "Anular", "Deshacer último
  movimiento", "Agregar bloque"). Se probó pasarlo al gris de fuera del
  panel y se desestimó: queda en celeste. Mismo padding que
  `botonPrimario` (8px 16px), así que siempre quedan del mismo alto.
- Todos los botones de un mismo formulario van al mismo ancho fijo
  (`setFixedWidth`), calculado para que entre el texto más largo sin
  cortarse — nunca se dejan con el ancho automático de cada uno.
- Borde negro fino (`1px solid #000000`) en ambos.

## Foco (Enter/Tab): orden general

Regla general (no puntual de una pantalla, vale para toda revisión de
acá en adelante — se viene armando pantalla por pantalla, pero la
clienta la subió a regla general al revisar Oferta de consultorios): el
foco arranca en el control que esté más arriba de todo (selector, campo,
lo que sea) y de ahí baja. Cuando en algún punto de la cadena hay varios
controles a la misma altura (una fila con dos o más campos, una grilla
de checks tipo "Días" en Oferta), los recorre de izquierda a derecha
antes de seguir bajando a la fila siguiente. Al llegar al final de la
cadena, vuelve al primero — esto último ya lo da gratis
`instalar_enter_avanza_foco` (`app/gui/widgets/foco.py`), no hace falta
ningún código extra para el "wrap-around".

En la práctica, para que el foco realmente arranque en el primero de la
cadena al entrar a la pantalla (y no en la barra de una solapa, si la
pantalla tiene `QTabWidget`) hace falta un `showEvent` que llame
`.setFocus()` sobre ese primer control — patrón ya usado en Reservas,
Liquidación, Centro de mensajería y Oferta de consultorios (que ya lo
tenía de antes y sigue vigente con la solapa nueva).

- Números de fila (encabezado vertical) centrados globalmente
  (`QHeaderView:vertical { qproperty-defaultAlignment: AlignCenter }`).
- Encabezados de columna: azul más oscuro que `botonPrimario`
  (`COLOR_NIVEL_1_OSCURO`, para no confundirse con un botón), negrita.
- Contenido de celda: texto (nombre, código, fecha, estado) alineado a la
  izquierda; números/importes (`item_numero`) alineados a la derecha.
  Excepciones puntuales a pedido de la clienta (ej. un año suelto como
  "Año calendario", o columnas cortas como Unidad/Posición en Placas)
  van centradas — se define caso por caso, no es la regla general.
  Importes negativos en rojo (`COLOR_ROJO`), positivos en color normal.
- Ancho de columna: `resizeColumnsToContents()` más un padding extra por
  columna (ver `_ajustar_columnas` en `novedades.py`) en vez de dejarlas
  al ancho justo — suele sobrar ancho en el panel. En Placas en cambio
  se igualan todas con `QHeaderView.ResizeMode.Stretch` porque son pocas
  columnas y todas de importancia pareja — el criterio se elige por
  pantalla, no es una regla única.

## Filtros que solo afectan la visualización

Patrón usado en Vista rápida (Estadísticas/Valores) y en Aumentos y
descuentos: un panel de filtros (Localidad/Edificio/Unidad, en cascada)
oculta filas de la tabla (`setRowHidden`) pero nunca cambia el conjunto
de datos sobre el que opera un botón de acción (simular/confirmar) — ese
conjunto es siempre TODO, se esté viendo filtrado o no. Se resuelve
guardando el id real de cada fila (`Qt.ItemDataRole.UserRole` en la
primera celda) y comparando contra lo elegido en los combos, con un
sentinel propio (objeto único) para "Todas/Todos" en vez de `None` —
`None` puede ser un valor real (ej. una Localidad sin cargar) y no debe
confundirse con "sin filtro".

## Columna "un valor u otro, nunca los dos"

Patrón usado en Aumentos (columnas "% general"/"% diferencial"): cuando
dos columnas representan alternativas mutuamente excluyentes para la
misma fila (un % puntual pisa al % general), solo una de las dos muestra
el valor real por fila — la otra siempre muestra una rayita "-" — para
que nunca se pueda leer un valor de más y quede ambiguo cuál rige.

## Catálogos (PantallaCRUD genérica)

Los catálogos simples (Edificios, Unidades, Consultorios, Responsables,
Tipos de licencia, Listas editables, Condiciones y normas, Profesiones,
Gastos operativos, Placas, Fechas especiales, Esquema de descuentos,
Detalles complementarios, etc.) se arman todos con la misma clase
genérica (`app/gui/crud_generico.py::PantallaCRUD`), así que el layout
estándar se define UNA vez ahí y aplica a todos de una. Formato: solapa
única "Listado" (`panelSolapa`, mismo criterio "ficha" que el resto),
panel izquierdo con "Buscar" (filtro de texto libre — solo oculta filas,
mismo criterio que "Filtros que solo afectan la visualización" — sin
distinguir mayúsculas ni acentos) y, si no es de solo lectura, los
botones Nuevo (`botonPrimario`), Editar y Eliminar (`botonSecundario`)
debajo; tabla a la derecha; todo el panel dentro de un `QScrollArea`. La
selección de fila ya se pinta del naranja suave definido en `paleta()`
(es la paleta de selección de toda la aplicación, no algo puntual de acá).

Pedido explícito de la clienta: "todo catálogo que pida desde ahora" pasa
a este formato solapa (el mismo de Edificios), aunque tenga un panel
extra propio (ver Profesionales abajo) — `compacto=True` queda reservado
para las pantallas que todavía no se revisaron una por una, no para
catálogos nuevos.

Cuando un catálogo necesita una sección propia además de Nuevo/Editar/
Eliminar (ej. Profesionales: documentación del profesional seleccionado),
esa sección va DEBAJO de esos tres botones, en el mismo panel izquierdo
— no al costado en un splitter aparte, y con una línea divisoria propia
arriba (separándola de los tres botones del CRUD). Se arma pasándole a
`PantallaCRUD` un widget ya armado (con sus propios botones/conexiones)
por `panel_extra_izquierda`; sus botones (ej. "Agregar archivo"/
"Eliminar archivo" en Profesionales — sin puntos suspensivos, la clienta
los sacó al revisar esta pantalla) usan `botonPrimario`/`botonSecundario`
y el mismo ancho fijo que el resto del panel (`crud_generico._ANCHO_
CAMPO`, 240px), y sus propios métodos atados de la pantalla compuesta
(que a su vez usan `self.crud_profesionales`, construido después — el
binding funciona porque el click llega mucho después de que todo ya
está armado).

Cuando la sección propia tiene que quedar ARRIBA de los botones en vez
de debajo (ej. Mensajes predefinidos: el filtro de Categoría, pedido de
la clienta al revisar esa pantalla), se usa el hermano de ese parámetro,
`panel_extra_superior_izquierda` — va entre Buscar y Nuevo/Editar/
Eliminar. Un catálogo puede usar los dos a la vez (uno arriba, otro
abajo de los botones); ninguno de los dos existe en modo `compacto`.

Se evaluó centralizar la documentación de Profesionales en el Gestor de
archivos (agregando una segunda solapa "Archivos de los profesionales")
pero la clienta pidió dejarla como estaba, solo mejorando el nombrado:
"Agregar archivo" ahora abre `_DialogoCategoriaDocumento` (lista cerrada
`app.negocio.documentacion_profesional.
CATEGORIAS_DOCUMENTACION_PROFESIONAL` — DNI completo/frente/dorso,
Título, Curso, Capacitación, Seguro mala praxis, Matrícula nacional/
provincial, más las dos categorías libres "Otras imágenes"/"Otros
documentos", compartidas por nombre con las de Gestor de archivos) y el
archivo se guarda con el nombre de esa categoría (o "{categoría} -
{detalle}" para las dos libres) en vez del nombre original — sigue
siendo pura gestión de archivos en carpeta, sin fila propia en la base,
sin concepto de "principal" ni de orden: es deliberadamente más simple
que Gestor de archivos.

El título del campo Buscar es "Buscar" por default, pero se puede
personalizar por catálogo con `etiqueta_buscar` (ej. Profesionales:
"Buscar profesional") sin cambiar el criterio de filtrado en sí (sigue
siendo substring por cualquier columna visible, no restringido a
campos puntuales). En Profesionales además el orden de columnas
arranca con Código/Tratamiento/Nombre/Apellido (el mismo orden que el
formato canónico "{código} - {tratamiento} {nombre} {apellido}" de los
selectores de profesional del resto del sistema) — pedido puntual de
esa pantalla, cada catálogo define el orden de sus propias columnas
según lo que tenga más sentido mostrar primero, no hay una regla única.

## Selectores y fecha

- Selector de profesional: combo buscable por código o nombre
  (`habilitar_busqueda_profesional`), mismo criterio en todo el sistema.
- Fecha: `QDateEdit` con selector de calendario. Formato por defecto
  `dd-mm-aaaa`. Registro de ausencias (Vacaciones/Licencias/Ausencias)
  usa además el día de la semana abreviado (`ddd dd-MM-yyyy` con
  `QLocale(QLocale.Language.Spanish)`, ej. "lun 07-09-2026") en los
  campos Desde/Hasta y en las columnas Desde/Hasta de sus tablas — pedido
  puntual de esa pantalla en su momento, generalizado después (ver abajo).
- `app/gui/crud_generico.py` (`PantallaCRUD`/`Campo`) suma `tipo="fecha"`
  (pedido de la clienta al revisar Fechas especiales): en vez del texto
  libre validado contra AAAA-MM-DD que usaban antes los catálogos
  genéricos, el diálogo Nuevo/Editar arma un `QDateEdit` con el mismo
  `ddd dd-MM-yyyy` + `QLocale` español de Registro de ausencias, y la
  tabla del catálogo muestra ese mismo formato en la celda — coherente
  con el resto del sistema, ya no hace falta un `validador`/
  `formato_esperado` para este tipo de campo (`QDateEdit` no admite un
  valor mal formado). El AAAA-MM-DD sigue siendo lo que se guarda en la
  base (`entrada.date().toString("yyyy-MM-dd")` al guardar) — ningún PDF
  ni cálculo de negocio que ya leía esa columna como texto tuvo que
  tocarse. El orden por click en el encabezado (`OrdenTabla`) ordena por
  ese AAAA-MM-DD real, no por el texto mostrado: alfabéticamente "lun..."
  queda antes que "vie..." aunque la fecha "vie" sea cronológicamente
  anterior, así que había que evitar que la columna se ordenara como
  string. Primer catálogo genérico en usarlo: Fechas especiales
  (`Campo("Fecha", "Fecha", tipo="fecha")`, sin más parámetros) — el
  resto de los catálogos con un campo de fecha en texto libre sigue como
  estaba hasta que se revisen y se les aplique el mismo tipo.

## Foco: Shift+Enter inserta salto de línea en campos de texto largo (todos los formularios)

Pedido de la clienta al revisar el mecanismo de "variables disponibles"
de Mensajes predefinidos (#24): "¿se pueden hacer saltos de línea en
los textos de los mensajes predefinidos? ¿Con shift enter como acá
[en el chat]?" Investigado antes de responder: NO se podía — tanto
Enter solo como Shift+Enter quedaban interceptados por el mecanismo
compartido "Enter avanza foco" (`app/gui/widgets/foco.py`), que no
distinguía Shift ni hacía ninguna excepción para campos multilínea
(`_EnterAvanzaFoco.eventFilter` consumía el evento de Return/Enter
siempre, devolviendo `True` sin importar los modificadores, así que el
`QPlainTextEdit` nunca llegaba a ver la tecla). Confirmado armando un
script que simula las dos teclas contra el diálogo real de Mensajes
predefinidos: ninguna de las dos insertaba el salto.

Pedido explícito de la clienta sobre la respuesta: "con Shift enter en
los campos de texto largo de TODOS los formularios que genere un salto
de línea, incorporalo" — no puntual de una pantalla.

`_EnterAvanzaFoco.eventFilter` (`app/gui/widgets/foco.py`) suma una
excepción: si la tecla es Return/Enter CON Shift Y el widget que la
recibió es `QPlainTextEdit`/`QTextEdit`, devuelve `False` (no consume
el evento) en vez de avanzar el foco — el propio widget procesa la
tecla con su comportamiento nativo e inserta el salto de línea. Sin
Shift, Enter en un campo multilínea se sigue comportando exactamente
igual que en cualquier otro campo de la cadena (avanza al siguiente).

Arreglado en el mecanismo COMPARTIDO (no en `crud_generico.py` ni en
ninguna pantalla puntual): `instalar_enter_avanza_foco` lo usan
decenas de formularios de todo el sistema, así que cualquier campo
multilínea que alguno de ellos sume a su propia cadena queda cubierto
automáticamente, sin tener que tocar cada pantalla una por una ni
acordarse de repetir el arreglo en una pantalla nueva. Investigado cuáles
de los `QPlainTextEdit`/`QTextEdit` del sistema estaban realmente
afectados antes de tocar nada: la mayoría (Vista previa de Centro de
mensajería, Detalle de Lista de espera, el editor de Textos del
sistema, el Detalle de la grilla operativa) nunca pasaron por
`instalar_enter_avanza_foco` — ya aceptaban Enter nativo desde
siempre, sin este bug. Los únicos campos realmente afectados son los de
`tipo="texto_largo"` armados por `crud_generico.Campo` (el campo
"Mensaje" de Mensajes predefinidos y los tres `Campo texto_largo` de
`catalogos.py`), que sí pasan por el diálogo genérico con su cadena de
foco — quedan arreglados de rebote por este cambio central, sin tocar
`crud_generico.py`.

Tests nuevos en `tests/test_gui_widget_foco.py` (al nivel del
mecanismo compartido, mismo criterio que el resto del archivo — la
garantía es la misma en todos los formularios porque es la misma
clase): `test_shift_enter_en_campo_multilinea_inserta_salto_de_linea_
en_vez_de_avanzar` (Shift+Enter inserta el salto y el foco se queda en
el mismo campo) y `test_enter_solo_en_campo_multilinea_sigue_avanzando_
el_foco` (Enter sin Shift sigue avanzando sin agregar ningún salto).

## Foco: seleccionar todo el contenido al enfocar un campo prefijado (disponible para todo el sistema)

Pedido de la clienta al revisar `_DialogoAjustarSaldo` (Reinicio de
prueba): "que el importe esté seleccionado para empezar a escribir
encima y borrarlo a la vez, esto para todos los campos que requieran
texto a introducir por los usuarios... en todo el sistema". La regla de
Tab/Enter de más arriba (`instalar_enter_avanza_foco`) ya selecciona
todo al LLEGAR por Tab/Enter dentro de una cadena armada, pero no cubre
el foco automático que Qt le da al primer control enfocable de un
diálogo recién abierto (no es un evento de tecla, nunca dispara ese
filtro) — el caso real de `_DialogoAjustarSaldo`, que tiene un solo
campo editable.

`instalar_seleccionar_todo_al_enfocar(widget, parent=None)`
(`app/gui/widgets/foco.py`) es el mecanismo general: escucha
`FocusIn` en `widget` (por click, por Tab/Enter, o por `setFocus()`
llamado desde código) y selecciona todo su contenido con
`QTimer.singleShot(0, ...)` (un `selectAll()` inmediato queda pisado
por el reposicionamiento de cursor que hace Qt después de un click).
Sirve para cualquier widget con `.selectAll()` — `QLineEdit`,
`QDoubleSpinBox`/`QSpinBox`, `QDateEdit`, etc. Generalización del
mecanismo puntual que ya tenía `selector_profesional.py`
(`_SeleccionarTodoAlEnfocar`, sigue ahí sin tocar — cubre un caso propio
con dos widgets a escuchar) para que cualquier pantalla nueva lo use sin
duplicar la clase.

Aplicado por ahora solo en `_DialogoAjustarSaldo.spin_saldo` (Reinicio
de prueba) — queda disponible para sumarlo al resto de los formularios
del sistema caso por caso, mismo criterio que el resto de los cambios
de alcance general (no un barrido completo de una sola vez).

## F5 ("Refrescar"): reinicia desde cero, distinto de `showEvent`

Regla general confirmada en una auditoría completa de los ~24 métodos
`reiniciar()` del sistema (detalle pantalla por pantalla en
`docs/historial/general.md`): este atajo y `showEvent` son disparadores
DISTINTOS. Volver a entrar a una solapa (`showEvent`) no tiene por qué
perder un filtro que el operador ya eligió (ej. qué profesional estaba
mirando); el atajo sí es un pedido explícito de "empezar de cero" —
todos los filtros a su valor inicial y el foco al principio de la
cadena. Toda pantalla nueva con estado propio (filtros, selección) tiene
que mantener esta separación al armar su propio `reiniciar()`, no
mezclarlo con `showEvent`.

Pedido de la clienta (hilo "saldo actual"/atajos de teclado): la tecla
se corrió de F3 a F5 — "más asociado al refrescar que usan los
navegadores" — para dejar F3 libre como salto directo a una solapa (ver
abajo). El método (`VentanaPrincipal._reiniciar_solapa_activa`, que a su
vez llama a `reiniciar()` del panel más interno vía `_panel_mas_interno`)
no cambió, solo la tecla del `QShortcut`.

## F1-F12: leyenda completa de atajos, salto directo a una solapa

Pedido explícito de la clienta: además de F1 (Ayuda, `_mostrar_ayuda`),
F2 (Calculadora, `_abrir_calculadora`) y F5 (Refrescar, ver arriba), el
resto de las F quedan como atajo directo a una solapa puntual del
sistema — no la pantalla, la SOLAPA, en pantallas compuestas con varias:

- F3: Regulares (solapa "Reservas regulares" de la Seccion "Reservas")
- F4: Aisladas (solapa "Reservas aisladas" de "Reservas")
- F6: Grilla (solapa "Grilla semanal" de "Grilla y mensajería")
- F7: Mensajería (solapa "Centro de mensajería" de "Grilla y mensajería")
- F8: Predefinidos (solapa "Mensajes predefinidos" de "Grilla y mensajería")
- F9: Oferta (solapa "Oferta de consultorios" de "Disponibilidad")
- F10: Profesionales (solapa "Listado de profesionales" de "Profesionales")
- F11: Pagos (solapa "Registrar pagos" de la Seccion "Pagos")
- F12: Panel de control (Seccion "Panel de control" — sin solapa puntual,
  "Panel de control" no es el texto de ninguna de sus dos solapas reales
  ("Avance de período..."/"Importación datos desde Excel"), así que
  `ir_a_solapa` no encuentra coincidencia y se queda solo con el salto a
  la Seccion, que es lo que pidió la clienta)

Implementado con `VentanaPrincipal.ir_a_solapa(nombre_seccion,
texto_solapa)` (`app/gui/main_window.py`), que reusa `ir_a_seccion` (#22,
ya existía para el salto de botón "Confirmar reserva" de Lista de
espera) y después busca con `findChild(QTabWidget)` la solapa de ese
texto dentro de la Seccion — todas las pantallas compuestas de este
sistema arman su `QTabWidget` en el atributo `pestanas`, así que el
método es genérico y no hace falta tocarlo si se agrega una Seccion
nueva con el mismo patrón. `self._etiqueta_funciones` (barra de estado,
costado izquierdo) muestra la leyenda completa de las 12 teclas en el
orden pedido por la clienta.

## Indicador "Procesando..." para operaciones largas

Mecanismo compartido (`Procesando`, `app/gui/widgets/procesando.py` —
origen y caso real en `docs/historial/sistema.md`) para cualquier loop
sincrónico largo (ej. emitir todas las liquidaciones): `with
Procesando(self, "texto..."):` alrededor del loop, llamando a
`procesando.tick()` en cada vuelta — fuerza `QApplication.
processEvents()`, necesario porque Qt es de un solo hilo y si no el
cartel ni el resto de la ventana se repintarían hasta que el loop
termine. Se suma caso por caso a cualquier otro loop largo del sistema
que lo necesite (no es una instalación global).

## Metodología de trabajo

Revisión "uno por uno", pantalla por pantalla, con la clienta. Un cambio
de estilo se prueba primero en la pantalla que se está revisando; si lo
aprueba y es de alcance general, se sube a `estilos.py` para que aplique
a todas las que ya usan ese objectName (no hace falta retocar cada
pantalla). A veces se prueba algo y se desestima (ej. gris en los
botones) — en ese caso se revierte al valor anterior, no queda a mitad
de camino. Después de cada ronda: pyflakes limpio, suite completa sin
regresiones nuevas (los ~15 fallos preexistentes de mensajería/pagos/
liquidaciones no están relacionados con la GUI y no se tocan acá),
captura de pantalla con Qt offscreen/xvfb para verificar visualmente
antes de dar la pantalla por cerrada.

Las capturas que se le envían a la clienta se nombran
"{Sección} - {Formulario} - {Solapa}.png" (pedido explícito de la
clienta, para no tener que renombrarlas ella a mano) — ej. "Sistema -
Panel de control - Avance de período, backup, y vista rápida.png". Sección es
"Sistema"/"Operativa diaria" (las dos categorías del menú), Formulario
el nombre del `Seccion` del menú, Solapa el texto de la pestaña
mostrada (si la pantalla no tiene solapas, se omite esa tercera parte).

## Hilo abierto: reserva aislada de un mes pasado, imputada al siguiente, no regeneraba la liquidación en curso

Pedido de la clienta: carga una reserva aislada de un mes YA PASADO (ej.
14 de octubre, parada en noviembre) para corregir una omisión, con
"Período a imputar" en "Período siguiente" — que en SU caso resuelve a
noviembre, el período OPERATIVO ACTUAL (no un mes futuro todavía sin
calcular, el caso normal para el que se pensó esa opción). Reportó dos
síntomas del mismo problema: (1) al crear la reserva, no se regeneraba
sola la liquidación de noviembre; (2) yendo a Liquidaciones e intentando
reemitirla a mano, tampoco pasaba nada ni se veía ningún aviso.

**Confirmado y corregido el síntoma (1).** Causa: `_resolver_periodo_
imputar` (`app/gui/pantallas/reservas.py`, compartida por Reservas
aisladas y extraordinarias) solo llamaba a `regenerar_si_corresponde`
para "Período actual" — para "Período siguiente" no hacía nada en
absoluto, bajo el supuesto (cierto en el caso normal: reserva del mes en
curso imputada al próximo, todavía sin calcular) de que "el mes que
viene la recoge sola" al calcularlo por primera vez. Ese supuesto es
falso cuando la reserva es de un mes YA pasado: el "período siguiente"
puede ser el período operativo actual, cuya liquidación bien puede
estar ya emitida y necesitar regenerarse YA. Se resuelve calculando
siempre el período real (`periodo_reserva` para "actual",
`sumar_meses(periodo_reserva, 1)` para "siguiente") y llamando a
`regenerar_si_corresponde` sin distinguir casos — `emitir_liquidacion`
ya sabe tratar sin romper nada tanto un período genuinamente futuro
(preview, sin acreditar a `SaldoCuentaActual` todavía) como uno ya
alcanzado (lo reemite de verdad). Test de regresión: `test_crear_
reserva_aislada_de_mes_pasado_con_periodo_siguiente_regenera_
liquidacion_del_periodo_operativo` (`tests/test_gui_reservas.py`) —
confirmado que SIN el fix falla (solo 1 emisión en vez de 2).

**Investigado el síntoma (2): el cálculo en sí (`calcular_liquidacion`)
ya sumaba bien esa reserva.** `_aisladas_periodo` arma el bloque
"aisladas del mes anterior" por FECHA real de la reserva (no por
`PeriodoImputado`, que es puramente informativo para la columna de la
tabla) — una reserva aislada fechada en octubre SIEMPRE cae en el
bloque "mes anterior" de noviembre al calcular noviembre, sin importar
qué se elija en "Período a imputar". Probado directo contra el motor
(`emitir_liquidacion`, sin pasar por la GUI): emitir una vez, cargar la
aislada del mes anterior, volver a emitir el mismo período — el monto
sube reflejando la aislada, correctamente. No encontré ningún bug
separado acá: lo más probable es que el síntoma (2) haya sido el MISMO
problema visto desde el lado manual (sin el fix de (1), quizás algún
otro paso intermedio tampoco se disparaba) o un detalle puntual de qué
estaba tildado/seleccionado en la pantalla en ese momento. A confirmar
con la clienta si, ya con el fix de (1) andando, todavía le pasa al
reemitir manualmente — con el botón exacto que usa y el período
elegido en la pantalla.

## Hilo abierto: Liquidaciones — un solo listado cronológico para feriados, feriados trabajados y horas aisladas

Pedido explícito de la clienta: *"las horas aisladas, los feriados y lo
que tenga fecha que esté ordenado de menor a mayor por fecha ... no
importa si es aislada o feriado, todo lo que tenga fecha que se ordene
por fecha en el archivo"*.

Alcance acordado explícitamente con la clienta (sobre tres opciones
presentadas): se fusionan en un ÚNICO listado cronológico ascendente
los descuentos por feriado/día no laborable (actual + pendientes del
mes anterior, que ya estaban fusionados entre sí desde una ronda
anterior — ver "Feriados y días no laborables en orden cronológico
(PDF)" en `docs/historial/liquidaciones.md`), los feriados trabajados
(actual + mes anterior) y las horas aisladas (actual + mes anterior).
Vacaciones/licencias (un RANGO de fechas, no un día puntual) y horas
regulares agregadas (vigencia desde una fecha) quedan FUERA de este
listado, en sus bloques de siempre — alcance explícitamente acotado,
no "todo lo que tenga alguna fecha en el documento".

`_items_cuenta` (`app/pdf/liquidacion_pdf.py`) arma ahora una lista
intermedia `eventos_con_fecha` (fecha, texto, monto) con los seis
orígenes de arriba y la ordena una sola vez con `sorted(..., key=lambda
e: e[0])` antes de volcarla a `items` — en vez de los bloques separados
de antes (feriados+no laborables ya fusionados por un lado, feriados
trabajados y aisladas cada uno en su propio loop más abajo, después de
vacaciones/licencias/horas agregadas). Como consecuencia, feriados
trabajados y aisladas se mueven MÁS ARRIBA en el documento (antes de
vacaciones/licencias/horas agregadas) — es la posición natural del
único bloque fusionado, no algo pedido aparte. `sorted` es estable, así
que dos eventos de la misma fecha exacta mantienen el orden de carga de
siempre (feriado/no laborable primero, feriado trabajado después,
aislada al final).

Test nuevo: `test_feriados_y_aisladas_se_intercalan_por_fecha_sin_
importar_el_tipo` (`tests/test_pdf_liquidacion.py`) — un feriado
trabajado del 2/8, un descuento por feriado del 17/8 y una aislada del
28/8, cargados fuera de orden y de tipos distintos, confirmando que
salen en ese mismo orden cronológico en `_items_cuenta`. Confirmado por
reversión que el test falla sin el fix (el feriado del 17/8 salía
primero, antes del feriado trabajado del 2/8).

`liquidacion_simulada_pdf.py` no tiene este problema — no separa
feriados trabajados ni aisladas en bloques propios (es más simple,
sin esas dos categorías), así que no hizo falta tocarlo.

## Hilo abierto: batch de 6 pedidos (Horas aisladas, Liquidaciones, Llaves, Pagos)

Pedido de la clienta, seis puntos en un solo mensaje. Tres quedaron
desestimados/pendientes de que ella los verifique mejor antes de
seguir — dos porque, al investigar, el comportamiento pedido YA
estaba implementado (así que probablemente el síntoma real que vio es
otra cosa), uno porque se resolvió directo sin necesidad de más vueltas:

1. **Desestimado por la clienta** ("si ya tiene scroll ese cuadro de
   detalle desestimá mi pedido"): el cuadro "Detalle" de Reservas
   aisladas (`GrillaOperativaWidget.texto_detalle`, un `QTextEdit`) ya
   muestra su propia barra de scroll vertical en cuanto el texto no
   entra en el alto disponible — confirmado con un script de geometría
   offscreen (`verticalScrollBar().maximum() > 0` con el mismo alto
   acotado que usa esa pantalla). No se tocó código.
2. **Pendiente, a verificar por la clienta**: el concepto de "Depósito
   de llave" en la liquidación (`_lugar_llave_texto`, `app/negocio/
   llaves.py`) YA incluye la unidad cuando el Tipo de llave abre una
   sola unidad sin ambigüedad (ej. "Depósito llave unidad del 7mo "L"
   del edificio Ramos 1" — confirmado en `tests/test_llaves.py`). Si
   el caso real que motivó el pedido es otro (ej. una llave tipo
   Edificio, o sin acceso configurado todavía), falta que la clienta lo
   puntualice antes de tocar nada.
3. **Resuelto**: buscador de profesionales en Tenencias de llaves,
   arriba de "Ingresar copia al stock" — combo buscable ("Todos los
   profesionales" + código/nombre, mismo criterio que
   `combo_filtro_stock` de esta misma pantalla), filtrando la tabla de
   "Movimientos de llaves" (la última de la pantalla) SIN afectar a
   `combo_filtro_stock` ni a su tabla derivada (`self._movimientos_
   actuales` se mantiene completo, el filtro nuevo solo recorta lo que
   se vuelca a `self.tabla_movimientos`). `_PanelLlaves._grupo_botones`
   suma un parámetro opcional `combo_extra`: descuenta su alto (+ el
   espaciado que agrega como ítem nuevo del layout) del espaciador que
   alinea el primer botón con el primer registro de la tabla, así
   "Ingresar copia al stock" sigue exactamente a la misma altura que
   antes — confirmado con el test de geometría ya existente de esta
   pantalla (`test_cada_grupo_de_botones_arranca_a_la_altura_del_
   primer_registro`). Test nuevo: `test_movimientos_se_filtra_por_el_
   buscador_de_profesional` (`tests/test_gui_llaves.py`).
4. **Resuelto**: "Horas aisladas a trabajar/trabajada" en plural en vez
   de "Hora aislada" fijo cuando el bloque dura más de una hora
   (`_texto_aislada`, `app/pdf/liquidacion_pdf.py` — compara `item.
   hora_fin - item.hora_inicio`). Tests nuevos: `test_horas_aisladas_
   en_plural_cuando_el_bloque_dura_mas_de_una_hora`/`..._en_singular_
   cuando_el_bloque_dura_una_hora` (`tests/test_pdf_liquidacion.py`) —
   de paso, dos tests ya existentes que usaban un bloque de 2hs
   (`test_hora_aislada_omite_el_edificio_...`/`..._menciona_el_
   edificio_...`) se actualizaron a la redacción en plural que les
   corresponde ahora.
5. **Resuelto**: en Pagos/Registrar pagos, debajo de "Deshacer último
   movimiento", se agregó "Saldo período anterior:" (`SaldoCuenta
   Anterior` del profesional — cómo cerró el período anterior, antes
   sin mostrarse en esta solapa) arriba de "Saldo período actual:"
   (antes "Saldo actual" a secas, renombrada para distinguirlas). Test
   nuevo: `test_registrar_pago_muestra_etiqueta_de_saldo_periodo_
   anterior` (`tests/test_gui_pagos.py`).
6. **Resuelto**: eliminar una hora aislada del MES ANTERIOR que afecta
   el "saldo anterior" de la liquidación ACTUAL (`_aisladas_periodo` la
   toma por fecha real, no por Período imputado — mismo mecanismo que
   el hilo "reserva aislada de un mes pasado" más arriba) no rehacía
   esa liquidación ni la dejaba como no enviada —
   `eliminar_reserva_aislada` (negocio) nunca llamaba a `regenerar_si_
   corresponde`, a diferencia de crear/modificar una aislada. Se agregó
   el llamado en `_PanelReservasAisladas._eliminar_registro`
   (`app/gui/pantallas/reservas.py`), con `periodo=periodo_actual(self.
   conn)` — mismo criterio que el resto de los disparadores de
   `regenerar_si_corresponde` en pantallas de este sistema. Test nuevo:
   `test_eliminar_reserva_aislada_de_mes_anterior_regenera_liquidacion_
   actual` (`tests/test_gui_reservas.py`) — confirmado que SIN el fix
   falla (queda 1 emisión en vez de 2).

## Hilo abierto: Reservas aisladas en día feriado; anular un feriado con aisladas asignadas; bug de pagos en "Detalle reserva"

Pedido de la clienta, tres puntos:

1. **Resuelto — reserva aislada en un día feriado no choca con la
   reserva regular.** Pedido explícito: "si el día es feriado en
   principio todos los horarios se consideran libres" — no debería
   haber problema en asignar una aislada ese día, sea al mismo
   profesional de la regular o a otro distinto. `verificar_conflictos_
   aislada` (`app/negocio/reservas.py`) solo liberaba el consultorio de
   la reserva regular si el profesional tenía una Ausencia/Vacación/
   Licencia activa ese día — un feriado no estaba contemplado como otra
   razón válida. Se suma `es_feriado_relevante(conn, fecha)` (nueva,
   `app/negocio/feriados.py` — mismo criterio de "tipo relevante" que
   `feriados_relevantes_periodo`, pero para una fecha puntual, sin el
   filtro de domingo que es específico del descuento en la
   liquidación) como otra condición que libera el consultorio, igual
   que las tres anteriores. La otra validación (aislada contra otra
   aislada ya confirmada ese mismo día/horario/consultorio, más arriba
   en la misma función) NO cambia — sigue corriendo siempre, sea
   feriado o no, tal cual lo pidió la clienta ("lo que empiezo a
   anotar como reservas aisladas es lo que hay que controlar"). Test
   nuevo: `test_reserva_aislada_en_feriado_no_choca_con_regular`
   (`tests/test_reservas.py`).

2. **Resuelto — anular un feriado con aisladas confirmadas ese día
   queda bloqueado.** Caso hipotético planteado por la clienta ("en el
   improbable caso de que yo quiera anular un feriado... el sistema me
   tiene que avisar que antes tengo que cancelar todas las reservas
   aisladas de ese día"): como consecuencia del punto 1, eliminar el
   feriado sin revisar esas aisladas podría dejarlas pisando una
   reserva regular sin que nadie lo haya evaluado — no hay forma
   automática segura de resolverlo, así que el sistema bloquea y
   obliga a revisar caso por caso. `PantallaCRUD` (`app/gui/crud_
   generico.py`) suma un hook nuevo, `antes_de_eliminar` (a diferencia
   de `al_eliminar`, que ya existía pero corre DESPUÉS del borrado,
   este corre ANTES de pedir la confirmación genérica "¿Confirmás
   eliminar?" y puede bloquear devolviendo un mensaje). `pantalla_
   fechas_especiales` (`app/gui/pantallas/catalogos.py`) lo usa para
   chequear si hay alguna `ReservaAislada` con `Estado='Confirmada'`
   en la fecha del feriado que se intenta eliminar — de haber alguna,
   bloquea con `QMessageBox.warning` y ni siquiera llega a preguntar
   la confirmación genérica. Tests nuevos: `test_eliminar_fecha_
   especial_feriado_con_aisladas_confirmadas_bloquea`/`..._con_
   aisladas_canceladas_no_bloquea` (`tests/test_catalogos.py`).

3. **Resuelto — bug real de doble error en "Detalle reserva" (Mensaje 1
   de WhatsApp, categoría A).** La clienta imputó un pago de $40.000 al
   mes ANTERIOR (octubre) estando parada en noviembre, y el mensaje de
   noviembre lo mostraba de todas formas en "Pagos registrados en mes
   en curso" — Y ADEMÁS lo sumaba al saldo a abonar en vez de
   descontarlo. Dos bugs independientes en `mensaje_detalle_reserva_
   aislada` (`app/negocio/mensajes.py`):
   - La consulta de pagos filtraba por `Fecha` (fecha de CARGA del
     pago en el sistema) en vez de por `PeriodoImputado` (a qué
     período se imputó) — un pago cargado este mes pero imputado a
     otro no es "de este mes" para este mensaje. Cambiado a `WHERE
     IdProfesional = ? AND PeriodoImputado = ?`.
   - La fórmula de `saldo_a_abonar` hacía `- total_pagos`, pero
     `Monto` en `HistorialPagos` YA viene con signo (negativo = pago
     recibido, resta de la cuenta — ver `registrar_pago`): restar un
     valor ya negativo lo SUMABA en vez de descontarlo (doble
     negación). Cambiado a `+ total_pagos`, mismo criterio que
     `total_llaves`/`total_reservas`/`total_item_libre`, que ya se
     suman directo sin negación aparte.
   - Un test ya existente (`test_detalle_aislada_calcula_saldo_a_
     abonar`) tenía `monto=500` (positivo, semánticamente un CARGO, no
     un pago) para simular "un pago de 500" — los dos bugs se
     compensaban sin querer y el test pasaba por las razones
     equivocadas; corregido a `monto=-500` junto con el fix real (el
     resultado esperado no cambia). Test nuevo: `test_detalle_aislada_
     ignora_pago_imputado_a_otro_periodo` (`tests/test_mensajes.py`) —
     reproduce el caso real de la clienta (pago cargado en agosto,
     imputado a julio) y confirma que no aparece en el mensaje de
     agosto. Confirmado por reversión que ambos tests fallan sin el
     fix, con el síntoma exacto reportado.

## Hilo abierto: batch de 8 pedidos (F5, mensajería, plazo extendido, Procesando, conflictos de horarios, Configuración general)

Pedido de la clienta, ocho puntos en un solo mensaje:

1. **Resuelto — F5 ("Refrescar") "no funciona en ningún lado".**
   Investigado con un repro directo (`QTest.keyClick` sobre un
   `VentanaPrincipal` real con un panel sintético): el mecanismo del
   atajo en sí (`VentanaPrincipal._reiniciar_solapa_activa`/
   `_panel_mas_interno`, `app/gui/main_window.py`) andaba bien — el
   problema real era otro: la clienta pidió explícitamente el barrido
   completo de las ~24 pantallas ("los filtros y los distintos elementos
   tienen valores iniciales, al presionar esa tecla quiero que devuelva
   la solapa a esos estados iniciales a TODOS los elementos", más
   estricto que la auditoría previa de "F5 ('Refrescar')" más arriba,
   que solo confirmó el foco).

   Cruzando las 18 Secciones de nivel superior contra cada `addTab()`
   de cada pantalla compuesta, **13 solapas no tenían NINGÚN método
   `reiniciar()`** — F5 no hacía absolutamente nada en ellas (el
   duck-typing de `_panel_mas_interno` no rompe, simplemente no llama a
   nada). Esto explica el "no funciona en ningún lado": no era un bug
   puntual, era un barrido que nunca se había hecho sobre estas 13.
   Para cada una se reusó, con un `reiniciar()` nuevo, el reset que YA
   existía para otro disparador (un botón "Actualizar tabla"/"Nueva
   búsqueda", o `showEvent` en los dos casos donde ese método ya hacía
   un reset completo — ver más abajo) en vez de duplicar lógica:

   - `_PanelAvancePeriodo`/`_PanelImportacion` (`panel_control.py`):
     `actualizar()`/limpiar campo+resultados.
   - `_PanelAumentos`/`_PanelEsquemaDescuentos` (`aumentos.py`): cada
     uno con su propio `actualizar()`.
   - `_PanelHistorialGeneral`/`_PanelEstadisticasVarias`
     (`estadisticas.py`): cada uno con su propio `_restablecer()`
     (botón "Actualizar tabla").
   - `_PanelIngresos`/`_PanelResultado` (`balance.py`): nuevo
     `_restablecer_filtros()` compartido en `_PanelFiltrosMixin` (a
     diferencia de "Ver período actual", que a propósito NO toca la
     cascada de ubicación, F5 sí vuelve período Y ubicación a
     "Todas/Todos").
   - `_PanelLlaves` (`llaves.py`): mismo reset completo que ya hacía
     `showEvent` en esta pantalla (anti-patrón ya existente, no tocado
     — solo se le sumó `reiniciar()` con la misma lógica), más el
     filtro de profesional de "Movimientos de llaves" (#117, no
     existía cuando se escribió ese `showEvent`).
   - `_PanelBuscarPlacas`/`_PanelImprimirPlacas` (`placas.py`): mismo
     caso que Llaves para Buscar (se extrajo `_reiniciar_filtros()` del
     `showEvent` existente para compartirla); Imprimir no tenía ningún
     reset, se armó nuevo (profesional + cola de impresión + vista
     previa, todo a blanco).
   - `_PanelOferta` (`oferta.py`): reusa `_nueva_busqueda()` tal cual
     (a diferencia de entrar/salir de la solapa, que a propósito NO
     resetea nada en esta pantalla — confirmado en su momento con la
     clienta).
   - `_PanelProfesionales` (`profesionales.py`): no tenía NI SIQUIERA
     `showEvent` — reusa `crud_profesionales.reiniciar()` (ver bug de
     abajo) + `_actualizar_documentacion()` explícito.

   **Bug real encontrado de rebote, en el mecanismo COMPARTIDO de
   catálogos genéricos:** al escribir el test de `_PanelProfesionales`
   (seleccionar una fila, F5, verificar que la documentación de la
   derecha quedara vacía) se descubrió que `PantallaCRUD.reiniciar()`
   (`app/gui/crud_generico.py`) NUNCA deseleccionaba la fila — limpia
   "Buscar" y reconstruye la tabla (`actualizar()`), pero `actualizar()`
   reescribe los `QTableWidgetItem` por ÍNDICE de fila, no por
   identidad de registro, así que la selección vieja (por índice)
   seguía marcada después de F5, aunque esa fila pasara a mostrar otro
   registro. Esto afecta a TODOS los catálogos genéricos del sistema
   (Edificios, Unidades, Consultorios, Profesiones, etc.), no solo
   Profesionales — arreglado una sola vez en la base
   (`tabla_widget.clearSelection()`, que de rebote dispara
   `itemSelectionChanged` y deshabilita Editar/Eliminar, el estado
   correcto de apertura).

   Suite completa corrida sin regresiones nuevas tras el cambio en la
   base compartida (476 tests de las pantallas afectadas + la suite
   completa). Tests nuevos: uno por cada una de las 13 solapas
   (`test_gui_panel_control.py`, `test_gui_aumentos.py`,
   `test_gui_estadisticas.py` ×2, `test_gui_balance.py` ×2,
   `test_gui_llaves.py`, `test_gui_placas.py` ×2, `test_gui_oferta.py`,
   `test_profesionales.py` — este último confirmado que falla sin el
   fix de `clearSelection()`).

   **Fuera de alcance de este barrido** (deliberado, no un gap
   pendiente): las ~11 solapas que ya tenían `reiniciar()` desde la
   auditoría previa no se revisaron campo por campo de nuevo — esa
   auditoría ya había confirmado que cubrían el caso general (foco +
   filtros propios), y la excepción conocida de `_PanelEstadoCuenta*`
   (no resetea el profesional elegido, decisión explícita de la
   clienta) sigue vigente sin cambios.

2. **Resuelto — Centro de mensajería, "Saldo actual" mal calculado para
   categoría A.** La columna usaba la misma fórmula genérica para R y A
   (`saldo_anterior + SaldoCuentaActual`), pero `SaldoCuentaActual`
   nunca se acredita para un A (no hay liquidación propia de esa
   categoría — `emitir_liquidacion` es exclusiva de R). Se agrega
   `saldo_actual_aislada` (`app/negocio/mensajes.py`), con el mismo
   criterio EXACTO que el "SALDO A ABONAR" de `mensaje_detalle_reserva_
   aislada` (reservas aisladas del mes + llaves + ítems libres, menos
   pagos del período, más saldo anterior) — de hecho `mensaje_detalle_
   reserva_aislada` pasa a llamar a esta función nueva para su propio
   total, para que los dos lugares no puedan divergir nunca. `actualizar()`
   (`app/gui/pantallas/mensajeria.py`) usa esta función para A y sigue
   con la fórmula de siempre para R/X (que sí es correcta: `SaldoCuenta
   Actual` para un R refleja justo "lo liquidado menos los pagos del
   período", vía `emitir_liquidacion`/`registrar_pago`). Tests nuevos:
   `test_centro_mensajeria_saldo_actual_de_un_a_se_calcula_de_lo_
   agendado_menos_pagos` (`tests/test_gui_mensajeria.py`, confirmado que
   falla sin el fix, mostrando `SaldoCuentaActual` crudo en vez del
   cálculo real).

3. **Resuelto — modificar el plazo de pago extendido de un R no
   regeneraba la liquidación.** `_al_actualizar_profesional`
   (`app/gui/pantallas/profesionales.py`) suma el mismo disparador que
   ya usan Vacaciones/Cargos especiales/Pagos: si `PlazoPagoExtendido`,
   `MotivoPlazoExtra` o `DiaPlazoExtendidoAutomatico` cambiaron en la
   edición, llama a `regenerar_si_corresponde` con el período actual.
   Test nuevo: `test_editar_plazo_pago_extendido_regenera_liquidacion_
   enviada` (`tests/test_profesionales.py`).

4. **Resuelto — Fechas especiales no mostraba el indicador de
   Procesando al regenerar liquidaciones.** `_regenerar_liquidaciones_
   del_periodo_actual` (`app/gui/pantallas/catalogos.py`) envuelve su
   loop en `Procesando` (mismo mecanismo que Liquidaciones), con
   `procesando.tick()` por profesional.

5. **Resuelto — editar en Configuración general / "Valores y
   liquidación" un campo que afecta saldos no regeneraba nada.**
   `ConfiguracionGeneral._guardar` (`app/gui/pantallas/configuracion.py`)
   ahora compara el registro antes/después de guardar contra
   `_CAMPOS_VALORES_LIQUIDACION_AFECTAN_SALDO` (recargo de aisladas,
   ajuste por saldo atrasado, tolerancia de deuda, descuento feriados/
   no laborables, semanas de vacaciones máximas, decimales del total) —
   los únicos de ese grupo que de verdad entran en `calcular_
   liquidacion`/`vacaciones`/el redondeo del total (confirmado uno por
   uno contra el código, no a ojo). Si cambió alguno, regenera TODAS las
   liquidaciones ya emitidas del período actual (no acotado a un
   profesional puntual, a diferencia de Fechas especiales) con el mismo
   indicador de Procesando. El resto del grupo (frecuencia de
   actualización de valores, el default de "aplica recargo" de una
   aislada nueva, cadencias de recordatorios, retención de historial) no
   cambia ningún cálculo ya hecho, así que no dispara nada. Tests
   nuevos: `test_guardar_campo_que_afecta_saldo_regenera_liquidaciones_
   enviadas`/`..._que_no_afecta_saldo_no_regenera_...`
   (`tests/test_gui_configuracion.py`).

6. **Resuelto — "lo más sagrado de este sistema": una superposición de
   horarios bloqueante ya no se puede forzar de ninguna forma.** Antes,
   `crear_reserva_regular`/`modificar_reserva_regular`/`crear_reserva_
   aislada`/`modificar_reserva_aislada` (`app/negocio/reservas.py`)
   tenían un parámetro `forzar` que, si el operador confirmaba un
   cartel "¿Crear/Modificar la reserva de todos modos?" después de ver
   el conflicto, creaba/modificaba la reserva IGUAL. Se sacó el
   parámetro por completo de las cuatro funciones (y de los seis
   lugares de la GUI, `app/gui/pantallas/reservas.py`, que lo usaban
   para reintentar) — un `ConflictoBloqueanteError` ahora siempre
   interrumpe el proceso, sin ninguna vía para sortearlo, en Reservas
   regulares/aisladas/extraordinarias, tanto al crear como al modificar.
   El cartel pasa de `QMessageBox.question` (Sí/No) a `QMessageBox.
   warning` (solo Aceptar) con el detalle del conflicto. Ese detalle
   (`Conflicto.mensaje`, armado en `verificar_conflictos_regular`/
   `verificar_conflictos_aislada`) ya incluía el nombre del profesional,
   el día/fecha y el horario de la reserva con la que choca — se le
   suma el CONSULTORIO exacto (`_texto_consultorio_conflicto`, nueva),
   que antes no se mencionaba (se daba por obvio porque es el mismo que
   se está reservando), completando el pedido explícito de "nombres,
   días, horarios y consultorios exactos". Tests: `test_conflicto_
   bloqueante_no_se_puede_forzar_de_ninguna_forma` (reemplaza al viejo
   `test_forzar_ignora_conflicto_bloqueante`, que probaba justo el
   comportamiento contrario) y el ajuste de `test_crear_reserva_
   regular_en_periodo_cerrado_no_se_puede_forzar` (ambos en
   `tests/test_reservas.py`) — confirmada la suite completa de Reservas
   (GUI + negocio) sin romper nada de lo ya existente.

7. **Resuelto — Centro de mensajería mostraba profesionales categoría A
   sin reservas activas.** La depuración de A sin aisladas vigentes
   (DC-02 §2.2, `_tiene_aisladas_vigentes` en `app/gui/pantallas/
   mensajeria.py`) ya existía y tenía tests, pero comparaba contra el
   primer día del PERÍODO OPERATIVO (que puede estar atrasado si todavía
   no se apretó "Avanzar de mes") en vez de la fecha REAL del calendario
   — mismo bug de fondo que ya se había corregido para el cuadrito de
   cumpleaños del Panel de control (`fecha_real` vs `fecha_actual`, ver
   #148). Una aislada de un período ya pasado en la realidad, pero
   dentro del período operativo atrasado, seguía contando como
   "vigente" y el profesional no se depuraba. Cambiado a `fecha_real`
   (ya no depende de `periodo`, se sacó ese parámetro de `_tiene_
   aisladas_vigentes`). Test nuevo: `test_centro_mensajeria_aislada_
   depende_de_la_fecha_real_no_del_periodo_operativo_atrasado`
   (`tests/test_gui_mensajeria.py`, confirmado que falla sin el fix). El
   pedido de mostrar en marrón a los A sin reservas pero con deuda
   queda explícitamente SIN implementar — la clienta está evaluando un
   cambio de esquema de colores y pidió no tocarlo todavía.

8. **Resuelto — eliminar una reserva aislada (caso normal, no el mismo
   día) no mostraba la alerta final de éxito.** `_PanelReservasAisladas.
   _eliminar_registro` (`app/gui/pantallas/reservas.py`) tenía el aviso
   de "avisar al profesional" para el caso del mismo día, pero el resto
   de los casos no mostraba ningún cartel al terminar — mismo criterio
   que ya tenía Reserva extraordinaria para su "Cancelar reserva".
   Test nuevo: `test_eliminar_reserva_aislada_muestra_alerta_final_de_
   exito` (`tests/test_gui_reservas.py`).

## Hilo abierto: batch de 8 pedidos (PDF disponibilidad, mensajería R, Placas, Llaves, categoría en caliente, fecha de reservas, bug liquidación)

Pedido de la clienta, ocho puntos en un solo mensaje:

1. **Resuelto — PDF de Disponibilidad: cuadro de valores de todos los
   consultorios.** Abajo de la grilla y antes de las fotos, como en el
   archivo de la propuesta (`referencia/generar_propuesta.py`,
   `tabla_valores`) — la app real ya tenía el mismo cuadro implementado
   como `matriz_valores_edificio` (`app/pdf/valores_pdf.py`), usado por
   Propuesta (anonimizado, "Unidad N") y Liquidación. Se agrega una
   tercera sección de nivel 1 a `generar_pdf_disponibilidad`
   (`app/pdf/disponibilidad_pdf.py`), "Valores de los consultorios para
   el período comprendido entre...", entre "Disponibilidad de
   consultorios al..." y "Fotos de los consultorios" — SIN anonimizar
   (a diferencia de Propuesta, Disponibilidad es para profesionales ya
   ACTIVOS, muestra el departamento real). Test actualizado:
   `test_incluye_las_tres_secciones_de_nivel_1_con_departamento_real`
   (antes "las dos secciones", `tests/test_pdf_disponibilidad.py`) —
   confirma las tres secciones, el orden (grilla → valores → fotos) y
   que no aparece anonimizado.

2. **Resuelto — Centro de mensajería: los R sin reservas activas
   tampoco deben figurar.** Mismo criterio que ya tenía A
   (`_tiene_aisladas_vigentes`, DC-02 §2.2): se agrega
   `_tiene_regulares_vigentes` (`app/gui/pantallas/mensajeria.py`), que
   considera también las reservas de un E consolidado en el equipo del
   R (`ids_consolidados`). Impacto grande en los tests existentes: la
   enorme mayoría de `test_gui_mensajeria.py` crea un R "liso" (sin
   ninguna reserva) esperando que aparezca en la lista — se agregó
   `con_reserva_regular=True` por default a `_crear_profesional` (crea
   una reserva mínima siempre vigente para no tocar los ~55 tests que
   no están probando esta depuración en sí) y `con_reserva_regular=
   False` explícito en los tests nuevos que sí la prueban:
   `test_centro_mensajeria_regular_sin_reservas_vigentes_no_se_muestra`,
   `..._con_reserva_finalizada_no_se_muestra`,
   `..._con_reserva_consolidada_de_un_e_se_muestra`.

3. **Investigado, sin reproducir — "al modificar una reserva regular
   que salga el alerta de proceso completado".** Repro directo del
   botón "Modificar reserva" cambiando el horario
   (`_PanelReservasRegulares._modificar_seleccionada`): el cartel
   "Reserva modificada con éxito." YA aparece, confirmado capturando los
   `QMessageBox.information` reales en un test ad-hoc. Única vía de
   "Modificar" en esta solapa (un solo botón, sin doble-click ni atajo
   alternativo). La clienta confirmó dejarlo así por ahora — si vuelve
   a pasar, hace falta el caso puntual (pantalla exacta, pasos) para
   seguir investigando.

4. **Resuelto — Placas: Unidad no ordenaba natural (PB/EP/piso), sino
   alfabético por texto.** El orden por defecto (Localidad/Edificio/
   Unidad/Posición, #97) y el click en el encabezado de "Unidad"
   (`_PanelPlacasOperativas._clave_orden`/`_actualizar_tabla`,
   `app/gui/pantallas/placas.py`) comparaban `e["unidad"]` como string
   crudo — "10mo" quedaba antes que "2do" alfabéticamente. Se suma
   `clave_orden_unidad` (`app/pdf/estilos.py`, mismo helper que ya usan
   Reservas/Catálogos) en los dos lugares. Test nuevo:
   `test_orden_por_defecto_de_unidad_es_natural_no_alfabetico`
   (`tests/test_gui_placas.py`).

5. **Resuelto — Llaves: el depósito por defecto al asignar pasa a
   "abonado".** `_DialogoAsignar.combo_deposito`
   (`app/gui/pantallas/llaves.py`) arrancaba en "Bonificado" (pedido
   anterior, punto 4 del batch de 6) — pedido explícito posterior:
   "cuando asigno una llave por defecto que el depósito sea Depósito
   abonado". Se invierte el orden de los `addItem` (abonado primero) y
   `spin_monto` arranca habilitado; la fuerza a "Bonificado" para
   categoría B (`_al_cambiar_profesional`) pasa de `setCurrentIndex(0)`
   a `findData("bonificado")`, para no depender de qué índice quedó
   primero. Test actualizado (antes probaba "arranca en bonificado", lo
   contrario): `test_dialogo_asignar_arranca_en_abonado_con_monto_
   habilitado` + `..._elegir_bonificado_deshabilita_el_monto`
   (`tests/test_gui_llaves.py`).

6. **Resuelto — cambiar la categoría de un profesional en caliente no
   lo mostraba en Reservas regulares hasta reiniciar el sistema.** Bug
   real: `combo_profesional` de `_PanelReservasRegulares`
   (`app/gui/pantallas/reservas.py`) se poblaba una sola vez en
   `_armar_ui` y nunca se volvía a construir — ni `showEvent` ni F5
   (`reiniciar()`) lo refrescaban, solo reseteaban el índice
   seleccionado. Se extrae `_cargar_combo_profesional()` (reconstruye
   la lista desde cero) y se llama también desde `reiniciar()`, mismo
   patrón ya usado para combos de profesional en Liquidaciones/Lista de
   espera/Novedades/Oferta/Pagos. Test nuevo: `test_cambiar_categoria_
   de_profesional_en_caliente_lo_muestra_sin_reiniciar`
   (`tests/test_gui_reservas.py`).

7. **Resuelto — Reserva regular: "Vigencia desde" arranca en el primer
   día del mes, no en hoy.** `_PanelReservasRegulares` ponía la fecha de
   HOY como default en tres lugares (`_armar_ui`, `_resetear_
   formulario`, `_cargar_grupo_cobertura` de #22) — se cambia los dos
   primeros (el formulario manual de alta) a `QDate(hoy.year, hoy.month,
   1)`; `_cargar_grupo_cobertura` (precarga desde "Confirmar reserva"
   de Lista de espera, un flujo distinto con su propio criterio) queda
   sin tocar. Test nuevo: `test_vigencia_inicio_arranca_en_el_primer_
   dia_del_mes` (`tests/test_gui_reservas.py`).

8. **Pendiente de la clienta — bug real en liquidaciones con un
   profesional que cambia de consultorio/horario a mitad de mes.**
   Reproducido con un script directo contra `calcular_liquidacion`: si
   el mes YA fue emitido una vez (con `fecha_emision` real) y DESPUÉS,
   ese mismo mes, se finaliza una reserva regular y se crea una nueva
   (otro consultorio/horario, típico de "Modificar" cuando cambia el
   consultorio, que esta pantalla no soporta — hay que finalizar +
   crear de nuevo), el tramo nuevo queda en bruto $0 y descuento $0 — la
   plata aparece recién en la liquidación del MES SIGUIENTE, como "horas
   regulares agregadas". Causa: `_ids_reservas_tardias`
   (`app/negocio/liquidaciones.py`) trata cualquier reserva con
   `VigenciaInicio` posterior a la última emisión del período como
   "tardía" y la excluye del bruto de ese mes sin excepción — diseño
   explícito para no reabrir una liquidación YA EMITIDA (ver "Hilo
   abierto: reserva aislada de un mes pasado" y `docs/historial/
   general.md`, "ajuste retroactivo"). El choque: `regenerar_si_
   corresponde` (llamado automáticamente al crear/finalizar una reserva
   regular) SÍ está pensado para reflejar el cambio al instante ese
   mismo mes — pero la deferral de "tardía" lo pisa igual, sin importar
   que la liquidación de ese mes nunca se haya ENVIADO al profesional.
   Propuesta de fix presentada a la clienta (no aplicada todavía,
   pendiente de que confirme con el caso real si la liquidación de
   noviembre ya estaba emitida Y enviada antes del cambio de
   consultorio): que `_ids_reservas_tardias` solo difiera al mes
   siguiente si la última emisión de ese período ya quedó "Enviada" —
   si todavía está "No enviada"/"Regenerada no enviada", reflejar el
   cambio completo ese mismo mes es seguro (nadie la vio todavía).

## Historial archivado

El detalle ronda por ronda de cada pantalla/funcionalidad (pedidos de la
clienta, investigación, decisiones, nombres de tests) se movió a
`docs/historial/*.md` — esto (CLAUDE.md) se quedó solo con las
convenciones/reglas generales que siguen vigentes hoy y que se citan desde
cualquier pantalla. Antes de trabajar sobre un formulario puntual, leer el
archivo correspondiente de la lista — ahí está el contexto real de por qué
algo quedó como quedó:

- `docs/historial/general.md` — reorganizaciones de navegación, auditorías
  y tandas de correcciones que tocan varias pantallas a la vez.
- `docs/historial/sistema.md` — Configuración general, Panel de control,
  Seguridad, Usuarios y permisos, Backup, Reinicio de prueba, Pantalla de
  carga.
- `docs/historial/catalogos.md` — catálogos genéricos (`PantallaCRUD`):
  Mensajes predefinidos, Gastos operativos, Fechas especiales, Listas
  editables, Condiciones y normas, Detalles complementarios, Localidad,
  Consultorios, Importar planilla, Bloques rígidos.
- `docs/historial/archivos.md` — Gestor de archivos, tipo "Enlace", Textos
  del sistema.
- `docs/historial/grilla_mensajeria.md` — Grilla semanal, Centro de
  mensajería, Mensajes predefinidos.
- `docs/historial/reservas.md` — Reservas regulares, aisladas y
  extraordinarias.
- `docs/historial/disponibilidad.md` — Oferta de consultorios, Lista de
  espera, Archivos para enviar.
- `docs/historial/liquidaciones.md` — Liquidaciones (incluye Liquidaciones
  simuladas).
- `docs/historial/valores.md` — Valores vigentes, Aumentos, Esquema de
  descuentos.
- `docs/historial/estadisticas.md` — Estadísticas.
- `docs/historial/balance.md` — Balance del negocio.
- `docs/historial/pagos.md` — Pagos.
- `docs/historial/novedades.md` — Registro de ausencias (Vacaciones/
  Licencias/Ausencias) y Cargos especiales.
- `docs/historial/llaves.md` — Llaves y otros conceptos.
- `docs/historial/placas.md` — Placas para timbres.
- `docs/historial/profesionales.md` — Profesionales.

Un pedido nuevo sobre una pantalla sigue documentándose en CLAUDE.md como
hasta ahora (sección propia con la ronda de trabajo); si esa sección queda
"cerrada" y deja de aportar algo que otra pantalla necesite tener siempre
a la vista, se puede migrar después al archivo que corresponda — no hace
falta hacerlo en el momento.

