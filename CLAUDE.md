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

## F3 ("Reiniciar solapa"): reinicia desde cero, distinto de `showEvent`

Regla general confirmada en una auditoría completa de los ~24 métodos
`reiniciar()` del sistema (detalle pantalla por pantalla en
`docs/historial/general.md`): F3 y `showEvent` son disparadores
DISTINTOS. Volver a entrar a una solapa (`showEvent`) no tiene por qué
perder un filtro que el operador ya eligió (ej. qué profesional estaba
mirando); F3 sí es un pedido explícito de "empezar de cero" — todos los
filtros a su valor inicial y el foco al principio de la cadena. Toda
pantalla nueva con estado propio (filtros, selección) tiene que
mantener esta separación al armar su propio `reiniciar()`, no
mezclarlo con `showEvent`.

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

## Reservas aisladas — rediseño a 4 columnas (hilo abierto)

Pedido explícito de la clienta: la pantalla pasó de 2 "columnas"
(formulario + grilla con sus filtros embebidos, repartidas con un
`QSplitter`) a 4, todas armadas con `QHBoxLayout` (`fila_columnas` en
`_PanelReservasAisladas._armar_ui`):

1. Formulario de carga (`panel_form`), sin cambios de contenido hasta
   los checks "Aplica recargo"/"Es reubicación" — los tres botones
   (Crear/Modificar/Cancelar) siguen después, al final de la columna
   (ya estaban ahí). Se sacó el texto "Cant. horas aisladas mensuales"
   (`etiqueta_horas_aisladas`, con el método `_actualizar_resumen_
   profesional` que lo alimentaba) — pedido explícito, sin reemplazo.
2. Solo los filtros de la grilla (Localidad/Edificio/Unidad/Día de la
   semana/Profesional) — sacados de `self.grilla` con
   `GrillaOperativaWidget.extraer_panel_filtros()` (nuevo, mismo
   criterio que `extraer_detalle`: remueve el widget del layout interno
   y lo devuelve para reubicar, sin re-crearlo). Días de la semana de a
   uno (NO se llama `agrupar_dias_en_pares()`, a diferencia de
   Regulares) para que la columna gane alto y llegue simétrica con la 1
   sin hueco en blanco al final.
3. "Referencias de colores" (una por fila, sacada del panel de Filtros
   con `extraer_leyenda_colores()`, nuevo) + el cuadro "Detalle" (ya se
   sacaba con `extraer_detalle`) debajo, sin tope de alto (antes 25px)
   — se estira hasta el pie de la columna en vez de quedar chico con un
   hueco debajo. Ronda siguiente, sobre la pantalla ya en uso: sin el
   marco de `QGroupBox` que las envolvía (`LeyendaColores.quitar_
   marco()`, nuevo — el título "Referencias de colores" se queda, sin
   el borde), muestras al triple de alto (14 → 42, `fijar_tamano_
   muestra(24, 42)`), letra más grande (9 → 12, `fijar_tamano_fuente`),
   alineadas a la izquierda con el texto pegado a la muestra
   (`alinear_contenido_izquierda()`, nuevo, espaciado horizontal 6px →
   4px). Lo que gana de alto la leyenda se lo saca directo al cuadro
   "Detalle" sin código extra: ninguno de los dos tiene `addStretch()`
   propio después de la leyenda y "Detalle" sí tiene `stretch=1`, así
   que el margen que cede siempre es el de "Detalle".
4. La grilla sola (ya sin Filtros ni leyenda, que se sacaron arriba):
   `self.grilla` después de las extracciones queda reducida a esto
   (su propio `layout_principal` ya solo tiene `panel_grilla`). Celdas
   más bajas que el default (`fijar_alto_filas`, nuevo en
   `GrillaOperativaWidget` — 18px/16px en vez de 26px/24px) para que las
   14 horas (8 a 22hs) entren sin scroll vertical.

Las tres primeras columnas van al mismo ancho fijo
(`_ANCHO_COLUMNA_AISLADAS = 260`, subido de un primer intento en 230 al
ver el mockup real con `hoja_estilos()` — a 230 algunos textos cortos
("Aplica recargo", "Es reubicación", "Sin selección") quedaban
recortados). Debajo de las 4 columnas, la tabla de Reservas aisladas de
siempre, con más alto disponible gracias al espacio que se liberó
arriba.

`self.grilla._panel_filtros`/`_leyenda_colores` (QGroupBox) ya traían
su propio margen nativo para alinearse con "Profesional" — las columnas
2 y 3 van SIN margen superior propio (`layout_col_filtros`/`layout_col_
detalle` en 0,0,0,0): sumarle `_ALTO_TITULO_FILTROS` encima duplicaba
el corrimiento (bug real, detectado por
`test_titulo_profesional_alineado_con_filtro_de_localidad`, que
reventaba 81 contra 60 — la diferencia exacta de ese margen de más).

Ronda siguiente, sobre la pantalla ya en uso (pedido explícito de la
clienta con una foto real: "Referencias de colores" quedaba pegada
arriba, "Filtro de localidad" un poco más abajo y "Profesional" más
abajo todavía — un efecto escalera que además angostaba la tabla de
abajo): las tres columnas pasan al MISMO margen de arriba, explícito y
chico (`_ALTO_TITULO_COLUMNA_AISLADAS`, no `_ALTO_TITULO_FILTROS` de
Regulares) en vez de depender del margen nativo de cada `QGroupBox` —
ese margen nativo resultó no ser idéntico entre los tres (columna 2,
CON borde, reservaba 6px más que columna 1 o que columna 3, YA sin
borde desde el punto anterior), aunque el test de alineación (que mide
offscreen) no lo detectaba — diferencia real de medición entre el
entorno de test y una pantalla real, confirmada con captura de la
clienta. Columna 2 (`panel_filtros_aisladas`) suma el mismo tratamiento
"sin marco" que la columna 3 (`setStyleSheet("QGroupBox { border: none;
}")` + margen de arriba explícito, dejando los otros tres lados como
estaban) — pierde el borde de "Filtros" (ya sin título visible desde
antes) como efecto necesario para igualar el margen real, no solo el
nominal.

Arrancó en 9 (lo mínimo que la columna 3 necesitaba para no recortar el
título "Referencias de colores") — confirmado con un script de
geometría antes de aplicarlo (test a ciegas de `left`/`subcontrol-
origin` en el QSS del título dieron corrimientos horizontales raros —
la única combinación que no recortó nada fue heredar el margen nativo
que Qt ya calculaba para ESE título antes de sacarle el marco, no
inventar un valor a mano). Con 9 quedó "apelmazado" (la primera
referencia de color pegada al título) — pedido explícito de la
clienta, ronda siguiente sobre la pantalla ya en uso: subido a 18.
`LeyendaColores.quitar_marco()` suma un parámetro opcional
`margen_superior` para esto — sin pasarlo, sigue heredando el mínimo
nativo (comportamiento de siempre para cualquier otro uso futuro); acá
se le pasa `_ALTO_TITULO_COLUMNA_AISLADAS` explícito, igual que las
columnas 1 y 2, para que seguir las tres alineadas entre sí.

Todo el rediseño se armó y confirmó primero con un mockup aparte (script
descartable fuera de `app/`, reutilizando los widgets/estilos reales)
que se le mandó a la clienta como captura — recién con su "sí, así" se
tocó código de verdad, mismo criterio que el resto de "Metodología de
trabajo" mencionado más abajo.

`GrillaOperativaWidget` suma métodos opt-in para este rediseño (no
afectan a Oferta de consultorios/Novedades/Grilla semanal/Reservas
regulares, que no los llaman): `extraer_panel_filtros()`,
`extraer_leyenda_colores()`, `fijar_alto_filas(alto_encabezado,
alto_dato)` y, en `LeyendaColores`, `quitar_marco()`,
`fijar_columnas(n)` (reemplaza pisar `._columnas` a mano desde afuera)
y `alinear_contenido_izquierda(espaciado_horizontal)`.

Bug encontrado y arreglado en esta misma ronda (pantalla ya en uso):
"el formulario aparece con la barra de scroll vertical por unos pocos
pixeles" — `scroll.setFixedHeight(contenido.minimumSizeHint().height())`
(mismo mecanismo que Regulares) quedaba unos pixeles por debajo de lo
que el contenido necesitaba de verdad (confirmado con un script de
geometría: `minimumSizeHint()` daba 471, el alto real necesario —
`sizeHint()` — daba 512). Causa: la columna 2 tiene `QSizePolicy.
Expanding` (para estirarse hasta el pie de la columna 1), y un widget
`Expanding` puede encogerse bastante más que su alto real — el
`minimumSizeHint()` del contenedor entero hereda esa elasticidad y dejó
de ser un piso confiable. _PanelReservasAisladas_ (`_armar_ui` y
`showEvent`) pasa a medir con `sizeHint()` en vez de `minimumSizeHint()`
— Regulares no se tocó, sigue con `minimumSizeHint()` como siempre (no
tiene ningún `Expanding` en su columna).

Chequeo pedido por la clienta ("que salga una alerta de éxito como en
todo el sistema"): faltaba el cartel de éxito simple (sin advertencias)
al crear y al cancelar una reserva aislada — `_crear`/`_cancelar_
registro` solo avisaban cuando había advertencias o cuando la cancelación
era el mismo día, pero se quedaban mudos en el resto de los casos
(a diferencia de Regulares, que sí tiene el "Reserva cargada con
éxito."/"Reserva eliminada con éxito." de siempre, punto #9.1.9).
Mismo gap encontrado y corregido en Reserva extraordinaria (mismos dos
métodos, copiados de Aisladas). "Modificar reserva" ya tenía el cartel
en las tres pantallas, no hacía falta tocarlo. Revisado también si
hacía falta el indicador "Procesando..." (reloj de arena) acá: no — los
tres botones de acción son operaciones de un solo registro, no un loop
largo (ver "Indicador 'Procesando...'" más arriba, que es justamente
para eso).

Ronda siguiente, pedido explícito de la clienta con instrucciones
puntuales por columna (sobre la pantalla ya en uso):

- **Columna 1**: "Profesional" sube 16px, al mismo píxel donde arranca
  "Referencias de colores" (columna 3, que esta ronda NO cambia de
  posición) — todo lo que está debajo de esa etiqueta sube con ella (es
  un solo margen superior del formulario, `form.setContentsMargins(9,
  _ALTO_ETIQUETA_COLUMNAS_1_2_AISLADAS, 9, 0)`, antes en
  `_ALTO_TITULO_COLUMNA_AISLADAS` = 18, ahora en una constante propia,
  `_ALTO_ETIQUETA_COLUMNAS_1_2_AISLADAS` = 2 — 16px menos). Columna 1 deja
  de ser "una columna más": pasa a ser la REFERENCIA de alto para las
  columnas 2, 3 y 4 (`self._alto_referencia_aisladas = panel_form.
  sizeHint().height()`, guardado en `_armar_ui` y vuelto a calcular en
  `showEvent` por el mismo motivo que `_scroll_superior`/`_contenido_
  superior` — el `sizeHint()` puede quedar desincronizado hasta el primer
  show real).
- **Columna 2**: "Filtro de localidad" sube los mismos 16px que
  "Profesional" (mismo valor de margen, `_ALTO_ETIQUETA_COLUMNAS_1_2_
  AISLADAS`, para no perder la alineación entre las dos). Además se
  achica a dos tercios del ancho de las columnas 1/3 (`_ANCHO_COLUMNA_
  ANGOSTA_AISLADAS = _ANCHO_COLUMNA_AISLADAS * 2 // 3` = 173, pedido
  explícito: "Reduci en un tercio el ancho de la columna"). Alto topeado
  al de la columna 1 (`panel_filtros_aisladas.setMaximumHeight(self.
  _alto_referencia_aisladas)`).
- **Columna 3**: mismo achique de ancho que la columna 2 (misma
  constante), SIN mover su posición vertical (sigue con
  `_ALTO_TITULO_COLUMNA_AISLADAS` = 18, sin cambios — es la referencia
  contra la que subieron las columnas 1 y 2, no al revés). Con el ancho
  más angosto, dos de las ocho referencias ("Reservado, pero libera un
  hueco por ausencia/vacación/licencia."/"Igual, con aislada confirmada
  en ese hueco.") pasan de una línea a dos (`QLabel.setWordWrap(True)`,
  ya estaba puesto desde el rediseño original) — confirmado con captura
  real que no queda apelmazado ni cortado, así que no hizo falta tocar
  `fijar_tamano_fuente(12)` (la clienta había dado permiso explícito para
  achicarla "si lo necesitás", pero no hizo falta). Alto topeado al de la
  columna 1, igual que la columna 2 (`panel_col_detalle.setMaximumHeight
  (self._alto_referencia_aisladas)`) — "Detalle" (`stretch=1`, sin tope
  propio) sigue absorbiendo el sobrante entre el pie de la leyenda y el
  tope de la columna, mismo mecanismo que antes.
- **Columna 4** (la grilla): el ancho que liberan las columnas 2 y 3 lo
  gana automáticamente (ya tenía `stretch=1` en `fila_columnas`, sin
  código extra). Alto topeado al de la columna 1 con `self.grilla.
  limitar_alto_grilla(self._alto_referencia_aisladas)` (método
  preexistente, ya usado en Reservas regulares con su propio alto natural
  — acá se reinstala con la columna 1 como referencia en vez del alto
  natural de la propia grilla) — si las 14 horas no entran en ese tope,
  la grilla scrollea sola adentro en vez de desbordar la fila.
- La tabla de abajo queda pegada al pie de la columna 1 (que ahora
  termina antes, al haber subido 16px) — consecuencia automática de que
  las 4 columnas ya terminan a la misma altura, sin tocar el código de la
  tabla.

Pixel final del botón "Cancelar reserva" (y, por el tope de alto común,
también el pie de las columnas 2/3/4), medido con un script de geometría
offscreen a 1500x900: **535** (arrancaba en 83 el tope de las 4 columnas,
"Profesional"/"Filtro de localidad" en 85). Reportado a la clienta como
referencia, mismo criterio que las rondas anteriores de esta pantalla.

**Pendiente de investigar, declarado NO ser un bug tras revisión**: la
clienta pidió "si yo cambio el período en la grilla debería cambiar el
comportamiento de la grilla y mostrarme lo del período seleccionado,
tendría que ser el actual o posteriores, no anteriores, esto surgiría de
una validación". Investigado antes de tocar nada: `combo_periodo`
(`GrillaOperativaWidget._armar_ui`) ya se arma únicamente con el período
actual + 12 meses hacia adelante (`periodo_actual(self.conn)` +
`sumar_meses`, nunca un mes anterior) — no hay manera de seleccionar un
período pasado desde este combo, en ninguna pantalla que use esta grilla
compartida. Y cambiar el período SÍ cambia lo que muestra la grilla:
confirmado con un script que arma una aislada confirmada para el mes
siguiente y compara `calcular_grilla_operativa` con `periodo` = mes
actual (celda verde, "Horario disponible") contra `periodo` = mes
siguiente (celda amarilla, con el detalle de la aislada) — el motor ya
usa `periodo` para acotar `mes_actual_inicio`/`mes_actual_fin` en
`app/negocio/grilla_operativa.py`. Sin cambios de código: ambas partes
del pedido ya estaban cubiertas antes de esta ronda.

Ronda de cierre, pedido explícito de la clienta sobre la tabla de abajo
("Muy conforme hasta ahora, ajustaría el ancho de la tabla en algunas
columnas ya para terminar esta solapa definitivamente"): ancho por
columna puntual, no el `_ajustar_columnas` genérico que comparten
Regulares/Extraordinaria (`_ajustar_columnas_aisladas`, nueva función,
mismo arranque — `resizeColumnsToContents()` + `_PADDING_COLUMNA` — con
recortes después):

- Unidad/Día/Fecha: 20%/15%/20% de recorte sobre el ancho ya calculado
  (con relleno incluido).
- "Consultorio" pasa a llamarse "Consul" SOLO en esta tabla
  (`setHorizontalHeaderLabels`, no afecta a Regulares/Extraordinaria, que
  siguen con "Consultorio"). El recorte del 60% pedido sobre esa columna
  se probó primero literal y RECORTABA LA PROPIA ETIQUETA "Consul" a la
  mitad ("onsu" en pantalla, confirmado con una captura real) — se
  descartó ese porcentaje y se dejó al ancho natural que necesita el
  título "Consul" (58px contra 88px que hubiera tenido con el 60%
  literal), mismo criterio que Reubicación/Período imputado.
- Reubicación/Período imputado: "que la etiqueta del título entre
  justo"/"que el ancho coincida con el título" — ancho NATURAL que ya
  calcula `resizeColumnsToContents()` antes de sumarle `_PADDING_
  COLUMNA` (ese método ya mide el título en negrita tal cual lo pinta
  `QHeaderView::section`, no hace falta recalcularlo a mano).
- Estado: "que la palabra 'Confirmada' entre justo" — medida a mano con
  `QFontMetrics` sobre esa palabra puntual (no sobre lo que haya cargado
  en la tabla en ese momento, que podría no incluir ninguna fila
  "Confirmada" si está filtrada a un profesional con solo
  cancelaciones), tomando el máximo contra el ancho natural para no
  quedar más angosto que lo que la tabla ya necesita hoy.

Verificado con una captura real (1500px de ancho) que la tabla entera
entra sin scroll horizontal (1214px de columnas contra 1452px de ancho
disponible, de sobra) y que ninguna de las columnas "al mínimo" quedó
recortada. Tests nuevos en `tests/test_gui_reservas.py`
(`test_tabla_aisladas_columnas_angostadas_sin_scroll_horizontal`).

Pendiente: la clienta todavía no probó esta versión en vivo — puede
haber correcciones en la próxima ronda.

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

