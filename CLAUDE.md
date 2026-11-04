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

**Fallos de fuentes del contenedor de desarrollo (no de la app):**
investigado un lote de 7 fallos nuevos de tests de GUI calibrados
pixel a pixel (altura de botones en Reservas/Lista de espera/
Profesionales, ancho de grilla en Oferta, corte de línea en Placas)
que aparecieron después de un reinicio del contenedor en la nube donde
corre este trabajo — confirmado que NO son un bug de la app ni de
ningún cambio de código (se reproducen igual sobre el código ya
commiteado, sin ninguna modificación):
- 5 de los 7: el contenedor trae un archivo de fontconfig propio
  (`/etc/fonts/conf.d/56-prefer-inter.conf`, ajeno a este proyecto) que
  fuerza la fuente genérica `sans-serif` a "Inter" en vez del default
  clásico de Linux (DejaVu Sans/Liberation Sans, con el que están
  calibrados los tamaños fijos) — la app nunca fija su propia fuente a
  propósito (ver más arriba, "se revirtió a pedido explícito de la
  clienta" sobre Segoe UI), así que depende del default del sistema.
  Confirmado sacando ese archivo (fontconfig cae en DejaVu Sans): los 5
  tests pasan. No existe en la máquina real de la clienta (Windows).
- Los otros 2 (Placas, calibración Calibri→Carlito): causa distinta,
  no relacionada con lo de Inter — la versión de la fuente Carlito que
  trae este contenedor mide la frase de referencia ("Lic. Agustina
  Viavattenee") más angosta que la calibración original, así que ya no
  cruza el umbral de corte de línea calibrado.

No se tocó nada (ni la app, ni los tests, ni la config del contenedor
— el cambio de fontconfig fue solo diagnóstico y se revirtió) porque
aflojar la tolerancia de estos tests para tapar una particularidad de
fuentes de este sandbox puntual debilitaría la señal real de
regresiones futuras, y la calibración pixel a pixel está atada a
propósito al entorno real de la clienta, no a este contenedor. Si
estos 7 vuelven a aparecer en una corrida de la suite, son del entorno
y no bloquean cerrar una ronda.

## Hilo abierto: Reservas aisladas — check "Mostrar todas las reservas"; Pagos — "Saldo total"

Pedido de la clienta, dos pantallas:

1. **Resuelto — Reservas aisladas: la tabla acumulaba TODAS las aisladas
   alguna vez cargadas, sin filtro de fecha.** Investigado antes de
   tocar código (la clienta pidió confirmación explícita): ¿son seguras
   de borrar las aisladas de meses viejos? NO — `_aisladas_periodo`
   (liquidaciones) solo lee mes anterior + mes actual, así que una vieja
   nunca vuelve a afectar ningún cálculo de liquidación, PERO
   `monto_neto_aislada_periodo` (`app/negocio/estadisticas.py`) se usa
   en vivo por Estadísticas ("Historial general", con selector Desde/
   Hasta) y Balance del negocio (Ingresos) para CUALQUIER período
   histórico que se elija mirar — borrar una aislada vieja dejaría esos
   reportes en $0 para siempre en ese mes. Se resolvió con un filtro de
   VISUALIZACIÓN nomás (mismo criterio que "Filtros que solo afectan la
   visualización"): debajo del filtro de Profesional de la columna 2
   (la de `GrillaOperativaWidget.extraer_panel_filtros()`, no la del
   formulario de alta de la columna 1), una línea divisoria y un check
   "Mostrar todas las reservas" (`_PanelReservasAisladas.check_mostrar_
   todas`) — desactivado por defecto (solo se listan desde hoy en
   adelante), activado muestra el historial completo como antes. F5
   lo resetea a desactivado, igual que el resto de los filtros de esta
   solapa.

   Pedido de seguimiento: al activar el check, la tabla no tiene que
   arrancar escroleada arriba de todo (la más vieja) — se posiciona en
   la primera fila de hoy en adelante (`self.tabla.scrollToItem(...,
   PositionAtTop)`), dejando habilitado escrolear para atrás además de
   para adelante. Solo aplica con el orden por defecto (fecha/hora/
   código) — un click en un encabezado de columna cambia el criterio de
   orden, así que "hoy" deja de tener una posición fija.

   Tests nuevos/actualizados en `tests/test_gui_reservas.py`: se agregó
   `check_mostrar_todas.setChecked(True)` a los 14 tests existentes que
   cargaban aisladas con fechas fijas (ya en el pasado respecto de la
   fecha real del sistema) para que sigan viendo sus filas; un test de
   scroll (`test_tabla_reservas_aisladas_escrolea_con_mas_filas_de_las_
   que_entran`) necesitó además mover el `setChecked(True)` a ANTES de
   `show()` (si no, el layout se resuelve con la tabla vacía y el
   scrollbar queda sin rango aunque después se agreguen filas — mismo
   tipo de problema de timing que otros tests de geometría offscreen de
   este archivo).

2. **Resuelto — Pagos/Registrar pagos: "Nuevo saldo" solo restaba el
   pago del período ACTUAL.** Si el pago se imputa al período anterior,
   "Nuevo saldo" (que solo mira `SaldoCuentaActual`) daba un importe
   incompleto/mentiroso — no reflejaba el saldo real a cubrir. Se agrega
   "Saldo total" (`etiqueta_saldo_total`, debajo de "Saldo período
   actual"), que suma las dos etiquetas de arriba (`SaldoCuentaAnterior
   + SaldoCuentaActual`), y "Nuevo saldo" pasa a calcularse en vivo
   sobre ESE total en vez de sobre el saldo actual a secas
   (`_actualizar_saldos`, `app/gui/pantallas/pagos.py`). Puro cambio de
   PREVIEW en pantalla — no toca todavía `registrar_pago` (ver el hilo
   del bug real de `SaldoCuentaAnterior`/`SaldoCuentaActual` más abajo,
   reportado de inmediato después de este cambio, que sí ataca el
   cálculo real). Test nuevo: `test_saldo_total_suma_anterior_y_actual_
   y_nuevo_saldo_lo_usa_de_base` (`tests/test_gui_pagos.py`).

3. **Resuelto — Pagos/Registrar pagos: un pago que cubría el saldo
   anterior Y el actual, con margen, solo descontaba del actual y
   dejaba el resto como crédito desconectado.** Bug real reportado por
   la clienta: "al cargar un importe de pago de un profesional que
   abonó el saldo del mes anterior, el actual y un poco más, me
   tendría que dejar como saldo de cuenta actual la diferencia del
   pago hecho menos los dos saldos, solo resta del saldo actual y
   carga el resto como crédito al profesional" — pedido explícito de
   que el fix impacte también los registros ya cargados, no solo los
   pagos nuevos.

   `registrar_pago` (`app/negocio/pagos.py`) imputa siempre a un solo
   campo (`SaldoCuentaAnterior` o `SaldoCuentaActual`, según
   `periodo_imputado` — "Nunca toca ambos a la vez", documentado desde
   siempre) — eso seguía intencional. El bug era que, si el pago
   alcanzaba a cubrir ese campo por completo Y TAMBIÉN el otro con
   margen, el sobrante se quedaba en el campo imputado como crédito
   (muy negativo) mientras el OTRO campo seguía mostrando una deuda ya
   cobrada en los hechos. `_aplicar_pago_con_cascada` (helper nuevo)
   agrega la cascada: solo cuando el sobrante alcanza para cubrir el
   OTRO saldo POR COMPLETO (no con que lo achique nomás), lo cancela y
   el resto queda como crédito final en el campo imputado. Ese umbral
   de "cobertura completa" (no cualquier sobrante) es clave: un pago
   que deja el campo imputado en crédito sin llegar a cubrir el otro
   saldo entero no reparte nada — es indistinguible de un pago por
   adelantado normal contra un período que todavía no tiene cargado el
   saldo real (ej. una reserva aislada recién creada, antes de pasar
   por `emitir_liquidacion`) — confirmado con una regresión real de la
   suite (`test_mensajes.test_detalle_aislada_calcula_saldo_a_abonar`)
   al probar primero con "cualquier sobrante reparte", que hubo que
   descartar por este motivo antes de subir el umbral a cobertura
   completa.

   `modificar_pago`/`eliminar_pago` ahora revierten por los deltas
   exactos que quedaron guardados en dos columnas nuevas de
   `HistorialPagos`, `ImpactoSaldoAnterior`/`ImpactoSaldoActual` (una
   de las dos en 0 si el pago no cayó en cascada) — ya no asumen que
   el pago tocó un solo campo, así que revierten bien un pago
   repartido entre los dos. Migración (`app/db/migraciones.py`): las
   filas de `HistorialPagos` ya cargadas (de antes de este fix, que
   nunca repartían) se backfillean con el mismo campo único que ya
   usaba `_campo_saldo`, para que sigan revirtiéndose exactamente igual
   que antes.

   Corrección retroactiva (lo pedido explícitamente: "que me impacte
   en los registros que ya pude haber cargado hasta el momento"):
   `reconciliar_saldos_cruzados` (`app/negocio/pagos.py`) corre sola en
   cada arranque (`app.db.init_db.init_database`, después de
   `aplicar_migraciones`) y neta, para cada profesional, un campo en
   deuda contra el otro en crédito — pero SOLO cuando el crédito
   alcanza a cubrir esa deuda por completo (mismo umbral exacto que el
   fix, para no corregir un estado que nunca estuvo roto). Deja su
   propio movimiento en `HistorialPagos` (Monto=0, EsAjuste, con el
   detalle de antes/después en Observación) para que quede visible en
   Estado de cuenta y sea reversible (Eliminar) como cualquier pago; es
   de por sí idempotente (una vez corregido un profesional ya no
   vuelve a cumplir la condición, y el fix en `registrar_pago` ya no
   vuelve a generarla).

   El cartel de confirmación de "Eliminar pago" (`app/gui/pantallas/
   pagos.py`) ahora distingue si el pago a revertir cayó en cascada
   (avisa "repartiéndolo entre el saldo del período anterior y el
   saldo actual") de uno que tocó un solo campo, en vez de asumir
   siempre un solo campo.

   Tests: `tests/test_pagos.py` (cascada en los dos sentidos, umbral de
   cobertura completa, `modificar_pago`/`eliminar_pago` con un pago
   repartido, `reconciliar_saldos_cruzados` en los dos sentidos + no-op
   si no hay cobertura completa + idempotencia, y wiring completo vía
   `init_database`), `tests/test_migraciones.py` (backfill de
   `ImpactoSaldoAnterior`/`ImpactoSaldoActual` en filas viejas +
   idempotencia), `tests/test_gui_pagos.py` (wording del cartel de
   Eliminar con cascada).

## Mensaje "DETALLE RESERVA {MES}" (reservas aisladas): sección "ÚLTIMA LEVANTADA DE PAGOS EN SOBRES"

Pedido de la clienta, con el mensaje modelo real como referencia: la
frase suelta que ya existía al pie del mensaje ("* Nota: Se imputaron
los pagos de los sobres recogidos en las unidades hasta el {día}
{dd/mm} a las {hora}.", generada en `mensaje_detalle_reserva_aislada`,
`app/negocio/mensajes.py`) pasa a ser una sección propia, con el mismo
formato que "PLACAS PARA LOS TIMBRES" (título en itálica + línea de
detalle con "+"): "_ÚLTIMA LEVANTADA DE PAGOS EN SOBRES_" / "+ {Día}
{dd/mm} - {HH:MM}hs" — mayúscula inicial en el día (antes iba en
minúscula) y hora siempre con minutos (`dt.strftime("%H:%M")` en vez de
`hora_fmt`, que recorta los ":00"). Se ubica DESPUÉS de "PLACAS PARA
LOS TIMBRES" (antes la frase vieja iba antes, pegada a "RESERVAS
POSTERIORES"), mismo orden que el mensaje modelo. El dato sigue
saliendo de la misma fuente de siempre ("lo que se va cargando con los
pagos en ese campo", confirmado por la clienta): de los pagos de este
profesional imputados a este período con medio "Sobre en buzón"
(`HistorialPagos.FechaHoraRecogidaSobres`), el más reciente — se omite
la sección entera si no hubo ningún pago por sobre, igual que antes.

Tests renombrados/actualizados en `tests/test_mensajes.py`:
`test_detalle_aislada_ultima_levantada_de_sobres_solo_si_hubo_pago_por_
sobre` y `test_detalle_aislada_sin_ultima_levantada_de_sobres_si_no_
hubo_pago_por_sobre` (antes `..._nota_de_sobres_...`).

## Batch de 7 pedidos sueltos + arranque de revisión de Reservas regulares

1. **Reservas aisladas: check "Mostrar todas las reservas" renombrado a
   "Mostrar reservas anteriores"** (`_PanelReservasAisladas.check_
   mostrar_todas`, `app/gui/pantallas/reservas.py`) — mismo
   comportamiento de siempre, solo cambia la etiqueta.

2. **Resuelto — Profesionales: a veces no salía el cartel de "Registro
   editado con éxito" al completar una edición, y al volver a editar sí
   salía.** Bug real: `regenerar_si_corresponde` (`app/negocio/
   liquidaciones.py`), disparada desde `_al_actualizar_profesional`
   cuando cambia el plazo de pago extendido, escribe el PDF de la
   liquidación en disco sin atajar ningún error de escritura — si ese
   PDF estaba abierto en otro programa en ese momento (lector de PDF,
   escenario común), la escritura tiraba `PermissionError` (un
   `OSError`) que se propagaba sin capturar hasta `_editar`
   (`crud_generico.py`), abortando el flujo ANTES de su cartel de éxito
   final, sin ningún aviso visible (PySide6 solo imprime el traceback a
   la consola, invisible en el .exe empaquetado). Se agrega un
   `try/except OSError` alrededor de la escritura del PDF: si falla, se
   salta sin más (igual que las otras condiciones de esa función que
   tampoco regeneran el PDF — "no es motivo para interrumpir la
   operación principal", ya documentado ahí), dejando que el flujo
   llegue igual al cartel de éxito. Test nuevo:
   `test_regenerar_si_corresponde_no_rompe_si_el_pdf_esta_bloqueado`
   (`tests/test_liquidaciones.py`).

3. **Resuelto — Regla general nueva: filtrar una tabla hasta dejar un
   solo registro visible lo selecciona solo**, para poder ir directo a
   Editar/Eliminar sin pinchar en la fila. Implementado en
   `PantallaCRUD._aplicar_filtro_busqueda` (`app/gui/crud_generico.py`)
   — cubre de una los ~15 catálogos genéricos (incluida Profesionales,
   que arma su CRUD con esta misma clase). Solo dispara con un filtro
   de Buscar ACTIVO (texto no vacío): un catálogo que de entrada tenga
   una sola fila cargada no se autoselecciona al abrir la pantalla
   (confirmado con un test — rompía la vista previa de documentación de
   Profesionales, que tiene que arrancar sin selección). Pendiente
   (pedido explícito "y en todas en realidad", pero fuera de esta
   ronda, mismo criterio que toda convención general de este sistema —
   "se va resolviendo pantalla por pantalla"): extenderlo a las
   pantallas con filtro armado a mano, no genérico (Reservas aisladas,
   Llaves, Estado de cuenta, etc.), caso por caso a medida que se
   revise cada una. Tests nuevos en `tests/test_crud_generico.py`.

4. **Resuelto — Badge "PERÍODO {mes}/{año}" (barra de estado, abajo a
   la derecha): pasa de azul a color de texto normal (negro).**
   `QLabel#badgePeriodo` en `estilos.py` — probado primero en azul
   (`COLOR_NIVEL_1_OSCURO`, mismo tono que los encabezados de columna,
   pedido de una ronda anterior), la clienta pidió el cambio al
   revisarlo de nuevo: se ve mejor en negro.

5-7. **Arranca la revisión de Reservas regulares.** Primeros dos
   pedidos de esta pantalla:

   - **"Quitale el recuadro a las referencias de colores"**: mismo
     tratamiento ya aplicado antes en Reservas aisladas
     (`LeyendaColores.quitar_marco`) — el título se queda, se saca la
     caja nativa de `QGroupBox`. Como acá la leyenda sigue embebida
     dentro del panel de Filtros (no se extrae a su propia columna como
     en Aisladas), se agregó el método público `GrillaOperativaWidget.
     quitar_marco_leyenda_colores(margen_superior=None)`, que reenvía a
     `LeyendaColores.quitar_marco` sin que el llamador tenga que tocar
     el atributo privado `_leyenda_colores`.

   - **"Que el primer elemento de cada columna arranque en el pixel 85
     como en Reservas aisladas, subiendo todo lo más posible"**: las
     "tres columnas" son, de izquierda a derecha, el formulario de
     alta, el panel de Filtros de la grilla (Localidad/Edificio/.../
     Profesional) y la grilla en sí — las dos primeras comparten
     margen de arriba (tienen que arrancar a la misma altura entre sí,
     mismo criterio de siempre), la tercera ya estaba prácticamente
     alineada sin tocar nada (diferencia de 1px, dentro del margen de
     error de medición). Medido programáticamente (geometría real,
     no a ojo) contra Reservas aisladas como referencia:
     - Columna 1 (formulario): `_ALTO_TITULO_COLUMNAS_REGULARES = 7`
       (antes `_ALTO_TITULO_FILTROS = 21`, que solo alineaba las
       columnas 1 y 2 de Regulares ENTRE SÍ, sin relación con
       Aisladas) como margen de arriba de `form`.
     - Columna 2 (panel de Filtros embebido): a diferencia de la
       leyenda, este panel SÍ seguía con su marco nativo de
       `QGroupBox` (con título vacío, `fijar_titulo_filtros("")`, pero
       sin sacarle el borde) — se agregó
       `GrillaOperativaWidget.quitar_marco_panel_filtros(margen_
       superior=None)` (mismo mecanismo que la leyenda) y se llama con
       `_ALTO_TITULO_COLUMNAS_REGULARES - _ALTO_BASE_GRUPO_GRILLA`: el
       `QGroupBox` sin título que envuelve esta columna completa
       (`grupo_grilla`) reserva 6px propios arriba ANTES de que
       arranque el panel de Filtros, que la columna 1 no tiene (vive
       directo en el splitter) — hay que restarlos para que las dos
       columnas terminen en el mismo píxel final a pesar de partir de
       bases distintas.

   **Hilo cerrado en la ronda siguiente — bug preexistente encontrado al
   armar la captura de la ronda anterior:** la leyenda compacta (2
   columnas) de Reservas regulares tenía las descripciones de texto
   superpuestas entre sí — confirmado con `git stash` que el bug ya
   estaba así antes de esa ronda (desajuste distinto, misma causa).
   Causa identificada: `hacer_compacta()` nunca llamó a `fijar_ancho_
   etiqueta_leyenda` (el fix que sí tiene Oferta de consultorios, ver
   `LeyendaColores.fijar_ancho_etiqueta`). Un primer intento con
   `fijar_ancho_etiqueta_leyenda(98)` solo (sin tocar el tamaño de
   letra) empeoró el problema — se había revertido en su momento.

   Pedido explícito de la clienta sobre esta misma solapa, ronda
   siguiente: "En la solapa de reservas regulares hay una linea
   divisoria y dos etiquetas informativas abajo del botón 'Eliminar
   reserva'. Sacá los tres elementos, que la columna termine con
   'Eliminar reserva'. Ajustá lo necesario en tamaño del recuadro de
   referencia y tamaño de la fuente de referencia para que entre todo
   sin apelmazar y la columna termine a la misma altura que la primer
   columna."

   - **Línea divisoria + 2 etiquetas afuera.** `_PanelReservasRegulares.
     _armar_ui` (`app/gui/pantallas/reservas.py`): se saca el `QFrame`
     divisorio y las dos `QLabel` ("Cant. horas regulares semanales"/
     "% Descuento") que colgaban debajo de "Eliminar reserva" — la
     columna 1 pasa a terminar directo en `form.addStretch()`. Se borra
     también el método que las alimentaba (`_actualizar_resumen_
     profesional`, con su único call site) y el import ya sin uso de
     `calcular_resumen_profesional` (`app/negocio/resumen_profesional`).

   - **Columna 2 (Filtros + leyenda) a la misma altura que la columna 1
     — causa de fondo del "apelmazamiento".** `limitar_alto_grilla`
     (ver `app/gui/widgets/grilla_operativa.py`) tapa el alto de TODO
     `self.grilla` (Filtros + grilla embebida), no solo la tabla — y
     Reservas regulares lo venía llamando con `alto_natural_grilla()`
     (el alto natural de la GRILLA sola, pensado solo para dejarla
     scrolleable a futuro "sin cambiar nada visible"). Medido: ese tope
     (458px) quedaba por DEBAJO del alto natural del panel de Filtros
     (472px) — el panel de Filtros (con la leyenda adentro) se achicaba
     por este tope sin que nadie lo hubiera pedido, apretando la
     leyenda contra un límite más chico del que necesitaba. Se cambia
     la referencia de `limitar_alto_grilla` de `alto_natural_grilla()`
     a `panel_form.sizeHint().height()` (guardado en `self._alto_
     referencia_regulares`, mismo mecanismo que `_alto_referencia_
     aisladas` en Reservas aisladas) — ahora el panel de Filtros tiene
     el mismo alto de sobra que la columna 1, en vez de un tope más
     chico impuesto por la grilla sola. Recalculado también en
     `showEvent` (mismo motivo que `_scroll_superior` ahí mismo: el
     `sizeHint()` de acá, antes del primer show, no siempre coincide
     con el real).

   - **Bug de fondo de la leyenda, ahora sí resuelto.** Con más alto
     disponible, la leyenda compacta quedó visible SIN comprimirse —
     pero reveló que las descripciones SÍ disparan wrap en este ancho
     (al contrario de lo que se había asumido en una ronda anterior de
     Oferta de consultorios, "su texto es corto y nunca dispara wrap" —
     ya no es así). Mismo arreglo de fondo que ya usa Oferta de
     consultorios (ver `docs/historial/disponibilidad.md`):
     `hacer_compacta()` fija la letra con un `setStyleSheet` de CSS
     crudo (cambia lo que Qt PINTA pero no lo que devuelve `QLabel.
     font()`), así que el `QFontMetrics` que usa `fijar_ancho_etiqueta_
     leyenda` para
     calcular el alto de cada fila medía con la letra default de la
     app, no con la compacta real. Se suma `self.grilla.fijar_tamano_
     fuente_leyenda(10)` (usa `QLabel.setFont`, no CSS) ANTES de
     `fijar_ancho_etiqueta_leyenda(98)` (98px, el ancho real medido de
     cada columna de etiqueta) — con la letra medida correctamente, el
     alto de fila calculado ya alcanza para el texto wrapeado real, sin
     superponerse con la fila de abajo.

   - **"Apelmazada contra el título", mismo bug ya documentado en
     Aisladas.** Con el bug de wrap resuelto, quedó un segundo síntoma
     real: el título "Referencias de colores" pegado contra la primera
     fila (`quitar_marco_leyenda_colores()` sin argumento usa el margen
     mínimo nativo, que ya estaba documentado como insuficiente —
     "queda apelmazada con la primera referencia", mismo bug que
     Aisladas ya había resuelto pasándole un margen explícito). Se pasa
     `self.grilla.quitar_marco_leyenda_colores(20)` en vez de sin
     argumento.

   - **Resultado.** Las 8 referencias entran en 2 columnas × 4 filas sin
     ningún texto superpuesto, con respiro claro entre el título y la
     primera fila. La columna 2 (Filtros + leyenda) termina a ≤5px del
     pie de "Eliminar reserva" (columna 1) — el splitter iguala el alto
     de las dos columnas automáticamente (`QSplitter` horizontal: todos
     los hijos comparten el mismo alto), así que ambas crecieron juntas
     unos pocos píxeles más que el alto natural original de la columna
     1 (524→540px) para darle a la leyenda, ya correctamente medida, el
     lugar que necesita — aceptado, mismo criterio que el "residuo"
     documentado para Oferta de consultorios (`docs/historial/
     disponibilidad.md`): preferible a dejar la leyenda apretada.
     Captura enviada a la clienta.

   Tests en `tests/test_gui_reservas.py`: se reemplaza `test_datos_
   complementarios_del_profesional`/`test_etiquetas_horas_regulares_y_
   aisladas_tienen_wordwrap`/`test_regulares_con_horas_semanales_y_
   descuento_aisladas_sin_ninguno` (la línea divisoria/etiquetas que
   verificaban ya no existen) por `test_columna_del_formulario_termina_
   en_eliminar_reserva`; se reemplaza `test_grilla_de_regulares_
   mantiene_el_tope_identidad_sin_achicarse` (verificaba el tope viejo,
   `alto_natural_grilla()`) por `test_grilla_de_regulares_usa_panel_
   form_como_referencia_de_alto` y se suma `test_regulares_columna_de_
   filtros_termina_cerca_del_pie_de_eliminar_reserva` (tolerancia de
   20px, mismo criterio que el test análogo de Aisladas).

   **Ronda siguiente, sobre la captura ya enviada: pixel 85, grilla sin
   scroll (8 a 22hs) y "Detalle" alineado.** Pedido explícito de la
   clienta: "chequea que los elementos iniciales de las tres columnas
   arranquen en el pixel 85. La grilla que sea visible de la misma
   manera que la de reservas aisladas, escroleable en horizontal, si es
   necesario en vertical si se agregan horarios también, pero en
   principio de 8 a 22hs se tiene que ver todo entero sin escrolear como
   en la otra solapa. Ajustá el cuadro de detalle para que termine a la
   misma altura que los otros elementos de la primer y segunda columna."

   - **Columna 3 no arrancaba al mismo pixel que las columnas 1 y 2.**
     Medido programáticamente: columnas 1 y 2 arrancaban al mismo pixel
     (comparten `_ALTO_TITULO_COLUMNAS_REGULARES - _ALTO_BASE_GRUPO_
     GRILLA` como margen de arriba, ver la ronda anterior), pero la
     columna 3 (Período/Visualización + la grilla, `layout_grilla`
     dentro de `GrillaOperativaWidget`) se había quedado con el margen
     default de Qt (9px) — 8px más abajo que sus vecinas, aunque las
     tres viven dentro del mismo `self.grilla` sin margen propio.
     `GrillaOperativaWidget.fijar_margen_superior_grilla(margen)`
     (nueva, mismo mecanismo que `quitar_marco_panel_filtros`) expone
     el margen de `layout_grilla` para pisarlo desde afuera; Reservas
     regulares la llama con el mismo valor que la columna 2, por el
     mismo motivo (son hermanas dentro de `self.grilla`). Las tres
     columnas quedan al mismo pixel exacto (medido: 93 en los tres,
     antes 91/91/99 — el valor absoluto no es literalmente 85 en este
     contenedor por el mismo desvío de fuente ya documentado en
     "Metodología de trabajo", pero la alineación relativa entre las
     tres es la que importa y ya es exacta).

   - **La grilla (8 a 22hs) quedaba recortada/superpuesta con "Detalle",
     no por falta de alto sino por el alto de fila default.** Al cargar
     una reserva real y medir con las 14 horas pobladas: la tabla (alto
     de fila 26px encabezado/24px dato, el default de esta grilla
     compartida) necesitaba más alto del que le quedaba disponible
     dentro del tope de la columna (el de la columna 1, ver la ronda
     anterior) una vez descontado "Período/Visualización" — el sobrante
     no alcanzaba para "Detalle" también, y como `limitar_alto_grilla`
     le da a la tabla un tope de alto que no la obliga a achicarse por
     debajo de su contenido real, el resultado no era scroll sino
     superposición visual real entre la etiqueta "Detalle:" y la última
     fila de la grilla (confirmado con geometría: "Detalle:" arrancaba
     en medio del rango vertical de la tabla). Mismo arreglo que ya usa
     Reservas aisladas para el mismo problema (8 a 22hs sin scroll
     vertical): `self.grilla.fijar_alto_filas(_ALTO_FILA_ENCABEZADO_
     REGULARES, _ALTO_FILA_DATO_REGULARES)` (18px/16px, mismos valores
     que `_ALTO_FILA_ENCABEZADO_AISLADAS`/`_ALTO_FILA_DATO_AISLADAS`),
     llamado ANTES de la primera construcción real de la grilla (mismo
     requisito que en Aisladas). Con el alto de fila más chico, las 14
     horas entran sin scroll vertical (`tabla.verticalScrollBar().
     maximum() == 0`, confirmado) y "Detalle" (que ya absorbía el
     sobrante vía `dar_stretch_a_detalle`, ronda anterior) vuelve a
     tener lugar de sobra, sin superponerse con la última fila.

   - **"Detalle" a la misma altura que las columnas 1 y 2, ya sin
     recortarse.** Con el punto de arriba resuelto, "Detalle" vuelve a
     terminar cerca del pie de "Eliminar reserva" (columna 1) por el
     mismo mecanismo de siempre (`dar_stretch_a_detalle` + el tope de
     `limitar_alto_grilla` igualado a la columna 1) — no hizo falta
     ningún ajuste nuevo en el reparto de alto, solo liberar el espacio
     que el alto de fila default le sacaba.

   - **Scroll horizontal, sin cambios.** La grilla ya era scrolleable en
     horizontal de siempre (`reservar_alto_scroll_horizontal`/
     `activar_filas_y_columnas_fijas`, filas/columnas fijas al estilo
     Excel) — mismo criterio que Reservas aisladas, no hizo falta
     tocar nada ahí.

   Tests nuevos en `tests/test_gui_reservas.py`:
   `test_regulares_las_tres_columnas_arrancan_a_la_misma_altura`,
   `test_regulares_grilla_de_8_a_22_entra_sin_scroll_vertical`,
   `test_regulares_detalle_termina_cerca_del_pie_de_eliminar_reserva_
   con_grilla_cargada` (tolerancia de 20px, mismo criterio que el resto
   de los tests de este archivo sobre la plataforma offscreen, más una
   verificación explícita de que "Detalle:" no arranca antes de que
   termine la tabla).

   **Ronda siguiente: tabla inferior, ancho de columnas, "Detalle" y
   Visualización en las dos solapas.** Pedido explícito de la clienta
   (verbatim, varios puntos en un mismo mensaje):

   - "Sacale el recuadro que rodea a las referencias de colores, que
     quede como en reservas aisladas" — **ya resuelto en la ronda
     anterior** (`quitar_marco_leyenda_colores`/`quitar_marco_panel_
     filtros`): confirmado con una captura de zoom sobre la leyenda, sin
     ningún borde propio (solo el de cada "cuadrito" de color, que es
     el `#000000` fino pedido aparte y se queda). No hizo falta tocar
     nada de nuevo acá.

   - **Alineaciones de la tabla inferior**: Unidad y "Consul" (antes
     "Consultorio", mismo rename ya aplicado en Aisladas) centradas;
     Horario con sufijo "hs" alineado a la derecha (ej. "9:00 a
     17:00hs"); Vigencia desde/hasta en formato "ddd dd-MM-yyyy" (ej.
     "jue 01-01-2026"), alineadas a la derecha. Mismos helpers que ya
     usa Aisladas para su propia tabla (`item_centrado`/`item_numero`,
     `_fmt_fecha_dia_abrev`) — nueva función `_ajustar_columnas_
     regulares` (análoga a `_ajustar_columnas_aisladas`, reemplaza a la
     genérica `_ajustar_columnas`, que no se usaba en ningún otro lado
     de este archivo). El orden por click en el encabezado de Vigencia
     desde/hasta sigue ordenando por el AAAA-MM-DD real (`_clave_orden`,
     sin tocar), no por el texto mostrado.

   - **"Dale más ancho a Profesional/Localidad/Edificio para que la
     tabla llegue al pixel 1475... contemplando la barra de scroll
     vertical."** `_distribuir_ancho_sobrante_regulares` (nueva, mismo
     descuento de ancho de scrollbar/borde que `_distribuir_ancho_
     sobrante_aisladas`): a diferencia de Aisladas (que le da TODO el
     sobrante a "Profesional" sola), acá el sobrante se reparte en
     partes iguales entre las tres columnas pedidas, con el resto del
     reparto entero yendo a Edificio (la última) para que la suma
     coincida exacto, sin que ninguna de las tres baje de su propio
     ancho natural (piso, mismo criterio que `_ANCHO_COL_PROFESIONAL`
     en Aisladas). Medido: el borde derecho de la tabla llega a
     x≈1477 (ventana de referencia 1500px), con las 9 columnas usando
     todo ese ancho — nada de hueco en blanco al final. Al igual que en
     Aisladas (`_distribuir_ancho_sobrante_si_sigue_vivo`), el ancho
     real de `self.tabla` recién se conoce después de que Qt termina de
     resolver el layout de toda la ventana — `showEvent` suma un
     `QTimer.singleShot(0, self._reajustar_alto_y_columnas_si_sigue_
     vivo)` (mismo guard `shiboken6.isValid(...)`) que vuelve a correr
     `_ajustar_columnas_regulares` (vía `actualizar()`) una vez resuelto
     ese layout pendiente — sin esto, el reparto se quedaba con un
     `tabla.width()` todavía angosto (una de las corridas intermedias
     midió 546px en vez de los 1452px reales).

   - **"Bajá un poco la etiqueta 'Detalle'... para que no se superponga
     con la grilla, y a partir de ahí bajá el alto del cuadro de
     detalle para que termine justo antes de que empiece la tabla de
     abajo."** `GrillaOperativaWidget.agregar_espacio_antes_de_detalle
     (espacio)` (nueva): suma un `insertSpacing` puntual justo antes de
     la etiqueta "Detalle:" en `layout_grilla`, sin tocar el resto del
     espaciado de esa columna (la separación entre "Período/
     Visualización" y la grilla se queda igual) — Reservas regulares la
     llama con 14px. Como "Detalle" (`texto_detalle`) ya se estira con
     `dar_stretch_a_detalle` (ronda anterior) para llegar siempre al pie
     de la columna 1, el cuadro se achica solo por este espacio nuevo,
     sin tener que tocarle el alto a mano. De paso, `showEvent` pasa a
     usar `panel_form.height()` (el alto YA asentado por el splitter)
     en vez de `panel_form.sizeHint()` (el "preferido" de la columna
     sola, que subestimaba cuánto la estira el splitter cuando la
     columna de al lado — Filtros + leyenda — pide más alto del que
     `panel_form` mide por su cuenta) para recalcular `_alto_referencia_
     regulares`, mismo motivo que el `QTimer.singleShot` del punto de
     arriba. **No resuelto del todo**: queda un margen residual de
     ~19px entre el pie de "Detalle" y el techo de la tabla de abajo
     (bajó de ~26px a ~19px con estos dos cambios) — se investigó subir
     `self.grilla` a `QSizePolicy.Expanding` + `stretch=1` en
     `layout_grupo_grilla` (mismo mecanismo que `panel_filtros_
     aisladas` en Reservas aisladas) y hasta forzarle un `setMinimumHeight`
     igual al tope, pero ninguno de los dos hizo que `self.grilla`
     creciera más allá de su propio alto mínimo natural (531px, medido),
     y el segundo intento además desencadenaba un crecimiento en
     cascada de `panel_form` (vía el splitter) que dejaba a `_scroll_
     superior` con un alto ya desactualizado (riesgo real de recorte) —
     se revirtieron los dos, se dejó el resultado más chico (19px) por
     ser estable y no arriesgar un recorte visible. Pendiente para una
     próxima ronda si la clienta pide cerrar ese margen del todo.

   - **"Que el selector de Visualización esté habilitado en las dos
     solapas, con 'Reservas regulares'/'Reservas aisladas' como default
     de cada una, y que cambiar la visualización cambie también las
     referencias."** `fijar_modo(...)` sigue fijando el modo por
     default de cada solapa (sin tocarla), pero ya no se deja
     deshabilitado el combo después: `self.grilla.combo_modo.setEnabled
     (True)`, tanto en Reservas regulares como en Reservas aisladas. El
     cambio de referencias al cambiar de visualización YA estaba
     conectado de antes (`combo_modo.currentIndexChanged` ->
     `_actualizar_leyenda_colores`, sin uso real hasta ahora porque el
     combo estaba bloqueado) — confirmado con una captura en cada
     sentido: Reservas regulares mostrando "Reservas aisladas" (6
     referencias, propias de Aisladas, en el mismo panel de 2 columnas)
     y Reservas aisladas mostrando "Reservas regulares" (8 referencias,
     en su propia leyenda a 1 columna) — ninguna de las dos
     desborda ni se superpone, aunque el tamaño de muestra/letra sigue
     optimizado para la visualización POR DEFECTO de cada solapa (pedido
     explícito: "optimizando el espacio... para la visualización por
     defecto de cada una"), no para la alternativa.

   Tests nuevos/actualizados en `tests/test_gui_reservas.py`:
   `test_tabla_regulares_desglosa_localidad_edificio_unidad_consultorio`
   (header "Consul" en vez de "Consultorio"), `test_tablas_de_abajo_
   muestran_tratamiento_nombre_apellido_y_columna_ancha` (Horario con
   "hs"); se reemplazan `test_grilla_preview_regulares_bloquea_la_
   visualizacion_en_regular`/`test_grilla_preview_aisladas_bloquea_la_
   visualizacion_en_aislada` (verificaban el combo bloqueado, ya no
   aplica) por `test_grilla_preview_regulares_arranca_en_regular_con_
   el_combo_habilitado`/`test_grilla_preview_aisladas_arranca_en_
   aislada_con_el_combo_habilitado`, y se suma `test_grilla_preview_
   regulares_cambia_la_leyenda_al_cambiar_visualizacion`.

## Reservas aisladas imputadas al mes siguiente: generación prematura de liquidación y valor congelado

Pedido/reporte de la clienta (verbatim, un solo mensaje con cuatro
puntos):

"Cargué una reserva aislada a ser tomada dentro del mes de noviembre
para ser rendida en el mes de diciembre, estoy parado en noviembre
ahora, a un profesional categoría R con reservas activas. Mes a
imputar el próximo, por ende se tiene que incluír dentro de la futura
liquidación. Vi que el sistema en ese momento me generó una
liquidación para el mes próximo, esta mal, no lo tiene que hacer, solo
tiene que agendar la reserva, y cuando avancemos de mes y se generen
las liquidaciones de ese mes, es decir en este ejemplo diciembre, ahi
en ese momento contemplar esas reservas que se agendaron para rendir
en el mes próximo. Esto es asi porque la idea en lo posible es emitir
solo una vez la liquidación de cada profesional, se manda, y lo nuevo
que pueda ir apareciendo se carga para el otro mes. Aparte, pueden
cambiar los valores de un mes a otro, por eso. El valor de la reserva
es siempre el que tiene dentro del mes donde se toma... el valor que
se aplica es el valor que tiene la reserva en noviembre, no en
diciembre."

Dos bugs reales, investigados y confirmados con tests que reproducen
cada uno ANTES de tocar código (mismo criterio de siempre: nunca se
arregla a ciegas), ambos en el mismo flujo (reserva aislada con
"Período a imputar" = siguiente) y hay que resolverlos juntos: arreglar
solo el primero sin el segundo dejaría una regresión silenciosa más
difícil de notar (ver el final de esta sección).

1. **Generación prematura de la liquidación del mes siguiente.**
   `_resolver_periodo_imputar` (`app/gui/pantallas/reservas.py`,
   compartida por Reservas aisladas y Reservas extraordinarias) ya
   tenía un fix de una ronda anterior (reserva de un mes YA PASADO,
   imputada a "siguiente", que podía resolver al período OPERATIVO
   ACTUAL — ver el comentario completo que sigue ahí) que, al
   resolverlo, pasó a llamar a `regenerar_si_corresponde` SIEMPRE,
   incluido el caso NORMAL (reserva del mes en curso, imputada al
   próximo, un mes genuinamente futuro) — `emitir_liquidacion` trata
   ese caso sin romper nada (dejaba una `LiquidacionEmitida`/PDF
   "preview", sin acreditar `SaldoCuentaActual` todavía, pensado para
   que el profesional pudiera verla si la pedía), pero la clienta pidió
   ahora que directamente NO se genere nada para un mes que todavía no
   llegó — ni siquiera como preview. Se agrega un guard: `_resolver_
   periodo_imputar` solo llama a `regenerar_si_corresponde` si el
   período real resuelto ya está alcanzado por el período operativo
   (`periodo_real <= periodo_actual(conn)`) — para un período
   genuinamente futuro, no hace nada más que la reserva en sí (que ya
   quedó guardada ANTES de este helper, nunca se pierde). El caso de la
   ronda anterior (mes pasado -> "siguiente" resuelve al actual) sigue
   regenerando YA, sin cambios — ese período no es futuro.

   Confirmado con `periodo_actual(conn) == periodo_operativo_actual
   (conn)` (`app/negocio/dias.py`: el primero es solo el "AAAA-MM" del
   segundo, recortado por `fecha_actual`) — usar cualquiera de los dos
   da lo mismo acá, se usa `periodo_actual` por ser el que ya importaba
   este archivo.

2. **Valor de la reserva aislada no congelado — usaba la tarifa VIGENTE
   HOY del consultorio, no la del momento en que se tomó.** Reproducido
   con un test antes del fix: una aislada tomada en noviembre
   ($1000/hora), con un aumento después que sube el consultorio a
   $2000/hora, calculada recién en la liquidación de diciembre (donde
   entra por "aisladas_mes_anterior", ver `_aisladas_periodo`) daba
   $2000, no $1000. Causa: `_aisladas_periodo`/`monto_neto_aislada_
   periodo`/`mensaje_detalle_reserva_aislada`/`saldo_actual_aislada`
   leían `Consultorio.ValorHoraAisladaActual` en vivo, recién al armar
   cada cálculo — `ReservaAislada` no guardaba ningún valor propio.
   Antes de este reporte, el bug de arriba (generación inmediata, en
   noviembre, mientras el valor de noviembre todavía era el vigente)
   tapaba este segundo bug como efecto colateral — arreglar el primero
   SOLO habría expuesto este segundo de lleno (el valor recién se
   leería en diciembre, ya con el aumento aplicado), así que había que
   arreglar los dos juntos.

   `ReservaAislada.ValorHoraAlMomentoDeLaReserva` (columna nueva, mismo
   criterio que `Vacacion.ValorSemanalAlMomentoDelRegistro`, ya
   establecido en este sistema para el mismo problema en otra
   pantalla): `crear_reserva_aislada` (`app/negocio/reservas.py`) lo
   congela con el `ValorHoraAisladaActual` del consultorio al momento
   de crear la reserva. `_aisladas_periodo` (`app/negocio/
   liquidaciones.py`) pasa a leer `COALESCE(ra.ValorHoraAlMomentoDeLa
   Reserva, c.ValorHoraAisladaActual)` en vez del valor en vivo a
   secas — el `COALESCE` es solo por las filas ya cargadas antes del
   backfill (no debería pasar en la práctica, la migración las cubre).
   Mismo cambio en las dos funciones de `app/negocio/mensajes.py` que
   independientemente repetían el mismo cálculo (`saldo_actual_
   aislada`, el "saldo actual" en vivo de categoría A, y `mensaje_
   detalle_reserva_aislada`, el "SALDO A ABONAR") — tienen que coincidir
   con lo que realmente factura la liquidación. `app/negocio/
   estadisticas.py::monto_neto_aislada_periodo` (usada por "Historial
   general"/Balance) se deja SIN TOCAR a propósito: su propio docstring
   ya dice explícitamente "a valores vigentes" — parece una elección
   deliberada de esa pantalla (comparar contra la tarifa de HOY, no
   reconstruir el monto histórico real), no lo que se reportó acá; se
   toca aparte si la clienta lo pide.

   Migración (`app/db/migraciones.py`): las filas de `ReservaAislada`
   ya cargadas antes de este fix reciben la columna nueva en NULL con
   el `ALTER TABLE` — `_inicializar_valor_aislada_al_momento_de_la_
   reserva` las backfillea con el `ValorHoraAisladaActual` de HOY del
   consultorio (lo más parecido disponible; no hay forma de recuperar
   el valor histórico real de un aumento ya aplicado) — el mismo valor
   que ya venía usando el cálculo para esa fila hasta ahora, así que no
   le cambia el resultado a nada ya calculado de algo viejo, solo
   corrige el cálculo de acá en adelante.

   No se tocó `RecargoPorcentajeAisladas` (el % de recargo de
   `Configuracion`, también usado en el mismo cálculo): tiene el mismo
   problema en teoría (también podría cambiar de un mes a otro sin
   quedar congelado), pero no es lo que se reportó — queda anotado acá
   por si la clienta lo pide en una próxima ronda.

   Tests nuevos: `tests/test_reservas.py` (`test_crear_reserva_aislada_
   congela_el_valor_hora_del_consultorio`), `tests/test_liquidaciones.py`
   (`test_aislada_usa_el_valor_congelado_no_el_vigente_del_consultorio`),
   `tests/test_mensajes.py` (`test_detalle_aislada_usa_el_valor_
   congelado_no_el_vigente_del_consultorio`), `tests/test_migraciones.py`
   (`test_aplicar_migraciones_backfillea_valor_aislada_con_el_del_
   consultorio_hoy`, más la columna nueva sumada a `test_base_nueva_ya_
   tiene_las_columnas_migradas`), y en `tests/test_gui_reservas.py`
   (`test_crear_reserva_aislada_del_mes_actual_con_periodo_siguiente_no_
   genera_nada_todavia`, a nivel de pantalla completa, para el primer
   bug) — el test ya existente de la ronda anterior (`test_crear_
   reserva_aislada_de_mes_pasado_con_periodo_siguiente_regenera_
   liquidacion_del_periodo_operativo`) sigue pasando sin cambios,
   confirmando que el caso de "mes pasado" no se rompió con este fix.

## Reservas regulares: ancho de la tabla, "Detalle" pegado al pie de "Eliminar reserva" y F5 repone Visualización

Pedido explícito de la clienta, solapa Reservas regulares (varios
puntos en un mismo mensaje):

- **"Sacale el recuadro a las referencias de colores... que se vea
  como está en la solapa de reservas aisladas."** Ya resuelto en una
  ronda anterior — confirmado de nuevo con una captura de zoom sobre la
  leyenda: sin ningún borde propio, solo el `#000000` fino de cada
  "cuadrito" de color (Punto #9.1.2, pedido aparte y distinto de esto).
  No hizo falta ningún cambio de código.

- **"Ajustá la tabla sacándole ancho a la columna edificio de manera
  que el final de la columna 'Vigencia hasta' termine justo antes de
  donde se visualiza la barra de escroll vertical, así no se ve la
  barra de escroll horizontal."** `_distribuir_ancho_sobrante_
  regulares` (ronda anterior) repartía el sobrante en partes iguales
  entre Profesional/Localidad/Edificio, con un piso igual al ancho
  natural de cada una — `max(ancho_para_repartir, suma de los tres
  pisos)` dejaba que el total pedido superara el ancho disponible si
  esos tres pisos ya sumaban más (nombres reales más largos que los de
  prueba de la ronda anterior), apareciendo el scroll horizontal que
  se quiere evitar siempre. Reescrita: Profesional y Localidad se
  quedan con el reparto parejo + piso de siempre (nunca se recortan);
  Edificio pasa a ser la única columna que cede — se lleva lo que
  sobre después de esas dos, incluso por debajo de su propio ancho
  natural si hace falta, con un piso absoluto bajo (`_ANCHO_MINIMO_
  EDIFICIO = 60`) solo para no desaparecer del todo. Confirmado
  forzando un escenario de overflow real (localidad/edificio/
  profesional con nombres largos a propósito): sin la barra de scroll
  horizontal, Edificio efectivamente la columna que se angosta.

- **"Bajá la etiqueta 'Detalle'... se ve apelmazada arriba de la barra
  de escroll horizontal de la grilla. Bajala por abajo de esa barra, y
  ajustá el cuadro de detalle de manera que arranque justo abajo de la
  etiqueta 'Detalle' y el cuadro termine justo antes de que comience la
  tabla de abajo. Es decir a la altura de donde termina el botón
  'Eliminar reserva'."** El espaciado antes de "Detalle:" (`agregar_
  espacio_antes_de_detalle(14)`, ronda anterior) ya medía desde el pie
  REAL de la grilla (que incluye su barra de scroll horizontal cuando
  está visible, parte del `rect()` de la tabla) — confirmado con
  geometría que el gap ya es de ~21px, no apelmazado; no hizo falta
  tocar ese número.

  El segundo pedido — que "Detalle" termine exacto en el pie de
  "Eliminar reserva" — es el mismo hilo abierto de la ronda anterior
  (quedaba un margen residual de ~19px, con dos intentos revertidos por
  riesgo de recorte). Esta vez se resuelve con un mecanismo distinto,
  más directo: `_ajustar_alto_detalle` (nueva, llamada desde `showEvent`
  y desde el `QTimer.singleShot` de reajuste diferido) mide en
  coordenadas GLOBALES el pie real de `self.boton_eliminar` y el techo
  real de `self.grilla.texto_detalle`, y fija ese `QTextEdit` con
  `setFixedHeight` (no `setMaximumHeight`/`stretch`, que es lo que no
  había alcanzado la ronda anterior) al alto exacto que hace falta para
  que las dos líneas coincidan. La diferencia de fondo con los intentos
  de antes: ahí se intentaba hacer crecer a `self.grilla` (el widget
  compuesto completo, Filtros + grilla) con `QSizePolicy.Expanding` +
  `stretch=1` o `setMinimumHeight`, apoyándose en que Qt "adivinara"
  cuánto estirarlo — no funcionaba (se quedaba en su alto mínimo
  natural) y el segundo intento además desencadenaba un crecimiento en
  cascada de `panel_form` vía el splitter. Acá, en cambio, se fija un
  alto mínimo EXPLÍCITO en la hoja más profunda del árbol (`texto_
  detalle`), que Qt sí propaga hacia arriba de manera confiable
  (`texto_detalle` -> `panel_grilla` -> `self.grilla` -> `grupo_
  grilla`) sin depender de que ningún widget intermedio "decida"
  estirarse por su cuenta. Medido: la diferencia entre el pie de
  "Detalle" y el de "Eliminar reserva" bajó de hasta 19px a 1-3px
  (redondeo normal de geometría, no un margen real).

- **"Si toco el filtro de Visualización... y presiono F5, que devuelva
  el valor de ese filtro al estado original (visualización regulares
  en Reservas regulares, visualización aisladas en Reservas
  aisladas)."** El combo "Visualización" (`combo_modo`) se había
  habilitado la ronda anterior pero `reiniciar()` (F3/F5/`showEvent`)
  no lo tocaba — quedaba en lo último que el operador hubiera elegido.
  Las dos `reiniciar()` (Regulares y Aisladas) ahora reponen `combo_
  modo` a su propio default ("regular"/"aislada" respectivamente),
  mismo criterio que el resto de los filtros de cada solapa.

Tests nuevos/actualizados en `tests/test_gui_reservas.py`:
`test_tabla_regulares_edificio_cede_ancho_para_no_mostrar_scroll_
horizontal` (localidad/edificio/profesional con nombres largos a
propósito, confirma `horizontalScrollBar().maximum() == 0`);
`test_regulares_detalle_termina_cerca_del_pie_de_eliminar_reserva_con_
grilla_cargada` (tolerancia bajada de 20px a 5px, ahora que el alto se
fija exacto); `test_reiniciar_regulares_repone_la_visualizacion_a_
reservas_regulares`/`test_reiniciar_aisladas_repone_la_visualizacion_a_
reservas_aisladas` (nuevos).

## Reservas regulares: barra de scroll vertical de la solapa (bug real de la ronda anterior, visto con datos densos de la app real)

La ronda anterior se verificó solo con los datasets chicos de los tests
(1-2 consultorios, 1 reserva) — la clienta mandó después una captura de
la app real en Windows (muchos consultorios por edificio: "EP", "7mo",
"9no" con varias columnas cada uno; la grilla con su propio scroll
horizontal; la tabla de abajo con decenas de profesionales reales) con
tres síntomas nuevos en la misma solapa, los tres en un mismo mensaje:

1. "Baja la terminación de la tabla de abajo para que coincida con el
   final de la solapa, estira la tabla un pelín más para aprovechar ese
   espacio que quedó porque la barra de desplazamiento horizontal no se
   ve más por el momento" (confirma de paso que el fix de la ronda
   anterior para esa barra horizontal funcionó).
2. "Detalle sigue estando superpuesto a la grilla... que detalle quede
   ABAJO de la grilla, y luego ajustá el cuadro de detalle para que esté
   abajo de esa etiqueta que dice 'Detalle' y el final de la tabla."
3. "Se sigue viendo la barra de escrol vertical de la solapa en sí...
   la idea es que la barra de desplazamiento vertical de la solapa no
   se vea."

Investigado antes de tocar nada (mismo criterio de siempre: nunca a
ciegas) con un script de geometría que reproduce un escenario denso de
verdad — 36 consultorios en 4 edificios (fuerza el scroll horizontal de
la grilla, igual que la foto real) y más de 200 reservas regulares
repartidas entre 25 profesionales (pobla la tabla de abajo con muchas
filas) — contra una ventana de 1366×768 (una resolución real más chica
que los 1500×900 de los tests existentes). Confirmado con ese script:
`self._scroll_superior.verticalScrollBar().maximum()` daba 4, no 0 —
había efectivamente una barra de scroll vertical de más dentro de
`_scroll_superior` (el `QScrollArea` que envuelve formulario+grilla,
ver `_armar_ui`), con `self._contenido_superior.minimumSizeHint()` en
544 contra un `scroll` ya fijado (`setFixedHeight`) en 540.

Causa real, en el propio `showEvent` de `_PanelReservasRegulares`:
`self._scroll_superior.setFixedHeight(self._contenido_superior.
minimumSizeHint().height())` se llamaba ANTES de `self._ajustar_alto_
detalle()` — que puede agrandar `texto_detalle` con `setFixedHeight`
(ver la ronda anterior) para cerrar la distancia hasta el pie de
"Eliminar reserva", cambiando de paso el alto mínimo real de TODO
`_contenido_superior` (formulario + grilla + Detalle, todo adentro del
mismo `QScrollArea`). `_scroll_superior` quedaba fijado al valor de
ANTES de ese agrandamiento, así que su alto fijo terminaba por debajo
de lo que su propio contenido necesitaba de verdad — un `QScrollArea`
con `setWidgetResizable(True)` en esa situación muestra su propia barra
de scroll vertical en vez de dejar que el contenido se recorte sin
avisar, que es justo la barra que la clienta reportó (síntoma #3), y el
motivo de que le quedara menos lugar real a la tabla de abajo (síntoma
#1: `panel_tabla` se queda con lo que `_scroll_superior` NO usa, `stretch
=1`, así que cualquier pixel de más que `_scroll_superior` reclame de
manera errónea es un pixel menos para la tabla). El reajuste diferido
(`_reajustar_alto_y_columnas_si_sigue_vivo`, disparado por el `QTimer.
singleShot` de `showEvent`) tampoco ayudaba: vuelve a llamar a `_ajustar_
alto_detalle()` (una segunda vez, ya con el layout de toda la ventana
resuelto de verdad — mismo motivo que recalcula `_alto_referencia_
regulares`/`limitar_alto_grilla` ahí mismo) pero nunca volvía a fijar el
alto de `_scroll_superior`, así que quedaba pegado para siempre al
valor de la primera pasada de `showEvent`, sin importar cuánto cambiara
`texto_detalle` después.

Sobre el síntoma #2 ("Detalle superpuesto a la grilla"): no se reprodujo
una superposición visible dentro del script de geometría con este
dataset (la causa de fondo — `_scroll_superior` desincronizado — sí se
confirmó igual), pero es consistente con el mismo mecanismo: en la PC
real de la clienta, con métricas de fuente distintas a las de este
contenedor (ver "Metodología de trabajo" más arriba sobre Carlito/
Inter), la distancia real entre el pie de "Eliminar reserva" y el techo
de "Detalle" puede ser bastante mayor que en este sandbox — agrandando
`texto_detalle` mucho más de lo que agranda acá, y por lo tanto
agrandando mucho más la desincronización de `_scroll_superior` con
él, lo que alcanza para que el contenido de más abajo dentro de ese
`QScrollArea` (la grilla, "Detalle") se vea recortado/superpuesto en vez
de solo una barra de scroll de unos pocos píxeles como en este sandbox.

Arreglo: `_scroll_superior.setFixedHeight(...)` se mueve a DESPUÉS de
`_ajustar_alto_detalle()` en `showEvent`, y se suma el mismo llamado al
final de `_reajustar_alto_y_columnas_si_sigue_vivo` (que antes solo
recalculaba `_alto_referencia_regulares`/`limitar_alto_grilla`/
`_ajustar_alto_detalle` pero no volvía a sincronizar `_scroll_superior`
con el resultado) — así `_scroll_superior` queda siempre fijado DESPUÉS
de que todo lo demás que puede cambiar el alto mínimo real de su
contenido ya corrió, en las dos pasadas (la sincrónica de `showEvent` y
la diferida del `QTimer`). Confirmado con el mismo script de geometría:
`scroll.verticalScrollBar().maximum()` pasa a dar 0, tanto con la
ventana de 1366×768 como con la de 1500×900 de los tests existentes.

Test nuevo en `tests/test_gui_reservas.py`:
`test_regulares_con_grilla_densa_no_muestra_scroll_vertical_de_la_
solapa` (36 consultorios/200+ reservas/1366×768, mismo dataset que el
script de diagnóstico, verifica `_scroll_superior.verticalScrollBar().
maximum() == 0`) — los tests existentes de esta solapa (con datasets
chicos, donde el bug nunca llegaba a disparar una barra de scroll
visible) siguen pasando sin cambios.

## Reservas regulares: foto real con datos densos, ronda 2 — borde de la leyenda, "Detalle" todavía superpuesto, resto de la barra de scroll

La clienta confirmó que el .exe que probó para la ronda anterior (la del
`_scroll_superior` desincronizado) ya tenía ese fix — así que estos tres
puntos, con fotos nuevas más detalladas (incluido el .exe real,
"SistemaDF v.2026.11", con datos igual de densos que la ronda anterior:
muchos consultorios por edificio, decenas de profesionales), son
síntomas reales que ese fix no alcanzó a resolver del todo:

"* Recuadros alrededor de las referencias.
* Barra de escroll vertical de la solapa por un pelín que aún hay que
ajustar.
* Cuadro de detalle y etiqueta muy sobre la grilla, lo pisa."

1. **"Recuadros alrededor de las referencias" — no era el marco grande
   de la leyenda (ese seguía sacado), era el bordecito de cada "cuadrito"
   de color.** Confirmado con la clienta antes de tocar nada (ambigüedad
   real: el Punto #9.1.2 había pedido ESE borde a propósito, "para que
   se vean delimitados", y quedó documentado como una decisión
   deliberada) — cambio de criterio explícito: ahora se quiere sacar
   también. `QWidget#muestraLeyenda` pasa de `border: 1px solid #000000`
   a `border: none` en `estilos.py` — alcance general (no puntual de
   Reservas regulares), mismo criterio de siempre: ese objectName lo usan
   todas las pantallas con `LeyendaColores` (Vista rápida, Oferta de
   consultorios, Reservas regulares/aisladas). El `QFrame` que envuelve
   cada muestra se queda igual (ya no hace falta por el borde, pero sigue
   siendo necesario para evitar el segfault de pintar directo sobre
   `_CeldaGrilla` con `WA_StyledBackground`, documentado desde el
   Punto #9.1.2 original). Test renombrado en
   `tests/test_gui_grilla_operativa.py`:
   `test_muestras_de_la_leyenda_siguen_envueltas_en_su_propio_marco`
   (antes `test_muestras_de_la_leyenda_quedan_recuadradas_en_negro` —
   ya no verificaba un color de borde puntual, solo la estructura del
   `QFrame`, así que no hacía falta cambiar sus asserts, solo el nombre
   y el docstring).

2. **"Detalle" seguía superpuesto a la grilla — confirmado real con la
   foto, no solo una sospecha.** La ronda anterior ya había anotado este
   riesgo como posible ("en la PC real... la distancia real... puede ser
   bastante mayor que en este sandbox") sin poder reproducirlo con los
   datasets de prueba disponibles acá. Causa real, ahora sí identificada:
   `_ajustar_alto_detalle` fijaba el alto de `texto_detalle` para que
   llegara exacto al pie de `self.boton_eliminar` (columna 1) SIN
   comparar ese objetivo contra lo que la columna 2/3 (`self.grilla`,
   con su propio tope de `limitar_alto_grilla`) realmente tiene
   disponible — en este sandbox el pie de `boton_eliminar` siempre
   resultó ser el techo más chico de los dos (así que el fix de la
   ronda anterior funcionaba bien acá), pero con métricas de fuente
   reales de Windows la tabla/filtros de arriba de la columna 2/3 pueden
   necesitar más alto del medido en este contenedor, dejándole a
   `texto_detalle` menos lugar real del que `_ajustar_alto_detalle` le
   pedía — forzarlo de todos modos hace que Qt no pueda satisfacer a la
   vez el alto fijo pedido y el tope de `self.grilla`, y el resultado es
   contenido superpuesto en vez de un error visible.

   Arreglo: `_ajustar_alto_detalle` pasa a tomar el MENOR de dos techos
   — el pie de `boton_eliminar` (el objetivo ideal, sin cambios) Y el
   pie REAL de `self.grilla` (`self.grilla.mapToGlobal(...)`, nuevo) —
   nunca le pide a `texto_detalle` más alto del que la columna 2/3
   realmente tiene, a costa de un posible hueco en blanco (mejor que un
   recorte) cuando el pie de `self.grilla` termina siendo el más
   restrictivo. Confirmado con el mismo script de geometría de la ronda
   anterior (36 consultorios/200+ reservas/1366×768): sin cambios en los
   números medidos acá (el pie de `boton_eliminar` sigue siendo el techo
   más chico en este dataset, así que el cambio es un no-op en este
   sandbox) — no se pudo reproducir la superposición real con los datos
   disponibles acá, pero el mecanismo de fondo (nunca pedir más alto del
   que la columna realmente tiene) es el que corrige la causa, no un
   número calibrado a ciegas.

3. **Resto de la barra de scroll vertical ("por un pelín").** Mismo
   mecanismo que el punto 2: si `_ajustar_alto_detalle` forzaba a
   `texto_detalle` más alto del que `self.grilla` tenía disponible, eso
   inflaba de más el alto mínimo real de `self.grilla` (y con él, el de
   `_contenido_superior` completo) más allá de lo que hacía falta — el
   mismo tope nuevo del punto 2 evita ese sobre-pedido, así que debería
   achicar o cerrar del todo el resto de esta barra en la PC real
   también (no se pudo confirmar con un número exacto por no poder
   reproducir el escenario límite acá — pendiente de que la clienta
   pruebe la build nueva).

Tests: `tests/test_gui_grilla_operativa.py` (rename, ver punto 1);
`tests/test_gui_reservas.py` sin cambios de assert (el escenario denso ya
existente, `test_regulares_con_grilla_densa_no_muestra_scroll_vertical_
de_la_solapa`, sigue pasando — el cambio en `_ajustar_alto_detalle` es
un no-op con ese dataset, confirmado).

## Reservas regulares: ronda 3 — video real confirma que el fix anterior no alcanzaba, causa de fondo de los dos puntos

La clienta mandó un video de la app real (mismo build que el fix de la
ronda anterior, confirmado explícitamente: "el video es de lo último que
subiste") — así que los dos puntos de abajo son fallas reales del fix
anterior, no evidencia vieja. Revisado extrayendo frames del video
(`ffmpeg`): se ve "Detalle:" literalmente escrito letra sobre letra
encima de la fila de la grilla (caso extremo, mucho más claro que
cualquier captura propia hasta ahora), la barra de scroll vertical de la
solapa todavía visible bajando hasta la barra de tareas de Windows, y
cada muestra de la leyenda con un resto de línea visible a pesar del
`border: none` de la ronda anterior.

1. **Resto de borde en la leyenda — causa real distinta a la asumida.**
   `_CeldaGrilla.paintEvent` (la clase que pinta cada muestra de color,
   reutilizada tal cual de la grilla real) llama a `_dibujar_bordes_
   gruesos`, que dibuja una línea fina gris (`#999999`, abajo y derecha)
   de forma INCONDICIONAL, sin pasar por el parámetro `bordes` — es el
   separador entre una celda de la grilla y su vecina de al lado/abajo,
   documentado como necesario para la grilla real ("cada límite interno
   lo traza una única celda"). La leyenda reusa esta misma clase para
   cada muestra sin pasarle una vecina real, así que esa línea se
   dibujaba igual, sin sentido para una muestra suelta — quedaba
   TAPADA por el marco negro de 4 caras del `QFrame` (Punto #9.1.2)
   hasta que ese marco se sacó en la ronda anterior, momento en el que
   quedó expuesta como un resto en forma de "L" en la esquina
   inferior/derecha de cada muestra. `_CeldaGrilla.__init__` suma
   `dibujar_separador: bool = True` (guardado en `self._dibujar_
   separador`, pasado a `_dibujar_bordes_gruesos` en `paintEvent`);
   `LeyendaColores.actualizar` arma cada muestra con `dibujar_
   separador=False`. No afecta ningún otro uso de `_CeldaGrilla` (la
   grilla real sigue con el default `True`, sin tocar).

2. **"Detalle" seguía superpuesto — el tope de la ronda anterior no era
   un techo independiente.** `_ajustar_alto_detalle` topeaba contra el
   pie REAL MEDIDO de `self.grilla` (`self.grilla.mapToGlobal(self.
   grilla.rect().bottomLeft())`) — pero ese pie no es una referencia
   fija: depende en parte de cuánto el propio método ya estiró `texto_
   detalle` en la llamada anterior (`self.grilla` crece para darle
   lugar a sus hijos). Un techo que se mueve junto con lo que se está
   limitando no frena nada — dos pasadas seguidas (la de `showEvent` y
   la del reajuste diferido) podían seguir forzando a `texto_detalle`
   más alto de lo que la columna realmente tenía, exactamente el mismo
   síntoma que se había intentado resolver.

   Arreglo: el techo pasa a ser el TOPE que `limitar_alto_grilla` ya le
   fija a `self.grilla` (`self._alto_referencia_regulares`, el alto de
   la columna 1 — un valor que NO depende de `texto_detalle` en
   absoluto) sumado al TECHO de `self.grilla` (`self.grilla.mapToGlobal
   (self.grilla.rect().topLeft())` — tampoco se mueve con el alto de
   los hijos de la columna, solo con lo que hay arriba de ella en el
   splitter). Dos referencias genuinamente independientes de `texto_
   detalle`, a diferencia del pie medido de la ronda anterior.

   Confirmado con el mismo script de geometría de las rondas anteriores
   (36 consultorios/200+ reservas/1366×768): sin cambios en los números
   medidos acá (el pie de `boton_eliminar` sigue siendo el techo más
   chico en este dataset, así que el cambio es un no-op en este
   sandbox, igual que la ronda anterior) — la corrección de fondo
   (techo genuinamente independiente, no circular) es la que debería
   notarse en la PC real, donde el pie "real medido" de `self.grilla`
   SÍ resultaba más chico que su verdadero tope.

Tests: sin cambios de assert en ninguno de los dos archivos (`tests/
test_gui_grilla_operativa.py`, `tests/test_gui_reservas.py`) — los
escenarios de prueba disponibles en este sandbox no alcanzan a
reproducir ninguno de los dos síntomas reales (ni el resto de borde, que
necesita zoom sobre una captura real para notarse en píxeles tan chicos;
ni la circularidad del tope, que solo se manifiesta cuando el pie
"medido" de `self.grilla` es menor que su tope real — no ocurre con los
datasets disponibles acá), así que las dos correcciones son de mecanismo
(nunca pedirle a `texto_detalle` más de lo que la columna tiene
garantizado, nunca dejar dibujar un separador sin vecina), no de un
número recalibrado — pendiente de que la clienta confirme con la build
nueva.

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

