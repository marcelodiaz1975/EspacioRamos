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

El título del campo Buscar es "Buscar" por default, pero se puede
personalizar por catálogo con `etiqueta_buscar` (ej. Profesionales:
"Buscar profesional") sin cambiar el criterio de filtrado en sí (sigue
siendo substring por cualquier columna visible, no restringido a
campos puntuales) — cada catálogo define el orden de sus propias
columnas según lo que tenga más sentido mostrar primero, no hay una
regla única (ver `docs/historial/profesionales.md` para el caso de
Profesionales, y la decisión sobre el nombrado de archivos de su
documentación).

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
regresiones nuevas (ver más abajo los fallos preexistentes conocidos,
del entorno y no de la app), captura de pantalla con Qt offscreen/xvfb
para verificar visualmente antes de dar la pantalla por cerrada.

Las capturas que se le envían a la clienta se nombran
"{Sección} - {Formulario} - {Solapa}.png" (pedido explícito de la
clienta, para no tener que renombrarlas ella a mano) — ej. "Sistema -
Panel de control - Avance de período, backup, y vista rápida.png". Sección es
"Sistema"/"Operativa diaria" (las dos categorías del menú), Formulario
el nombre del `Seccion` del menú, Solapa el texto de la pestaña
mostrada (si la pantalla no tiene solapas, se omite esa tercera parte).

**Fallos conocidos, del sandbox/contenedor y no de la app:** hasta 10
tests pueden aparecer en rojo en este entorno sin ser una regresión
real — 7 por una particularidad de fuentes de este contenedor
(fontconfig/Carlito, calibración pixel a pixel de Reservas/Lista de
espera/Profesionales/Oferta/Placas) y 3 de `test_avance_mes.py` por el
reloj real del sandbox (dependencia de en qué mes real se corre la
suite). Investigación completa, lista exacta de los 10 nombres y por
qué no se tocan en `docs/historial/general.md` ("Fallos del
sandbox/contenedor, ajenos a la app"). Si reaparecen, no bloquean
cerrar una ronda.

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
- `docs/historial/control_pagos.md` — Módulo extendido ME1 "Control de
  pagos".

Un pedido nuevo sobre una pantalla sigue documentándose en CLAUDE.md como
hasta ahora (sección propia con la ronda de trabajo); si esa sección queda
"cerrada" y deja de aportar algo que otra pantalla necesite tener siempre
a la vista, se puede migrar después al archivo que corresponda — no hace
falta hacerlo en el momento.

## Pagos (Registrar pagos): doble alto de encabezado + reordenar/achicar columnas

Cuatro pedidos puntuales de la clienta sobre la tabla de
`_PanelRegistrarPago` (`app/gui/pantallas/pagos.py`):

- Encabezados de "Período imputado", "Monto", "Saldo previo", "Nuevo
  saldo" y "Registro modificado" pasan a dos líneas (`"Período\n
  imputado"`, etc.) — mismo mecanismo ya usado en Estadísticas:
  `QHeaderView` agranda solo el alto de la fila de encabezados y angosta
  la columna a lo que mide la palabra más larga, sin código extra.
- "Monto", "Saldo previo" y "Nuevo saldo" se achican un 40% respecto al
  ancho natural (`resizeColumnsToContents()`), calculado sobre la tabla
  ya con filas cargadas (el ancho natural de una tabla vacía no sirve de
  referencia).
- Reorden de columnas: "Saldo previo" y "Nuevo saldo" pasan a estar
  pegados después de "Monto" (antes del Medio de pago); el resto sigue
  en el mismo orden relativo.
- "Registro modificado" también a dos líneas, ancho mínimo.

`_PanelEstadoCuentaPagos` (la otra solapa, "Estado de cuenta") no se
tocó — el pedido fue puntual de "Registrar pagos".

Tests en `tests/test_gui_pagos.py`: `test_tabla_registrar_pagos_monto_
saldos_se_achican_un_40_por_ciento` (achicado vs. natural post-carga,
±1px de tolerancia por redondeo de Qt) y `test_tabla_registrar_pagos_
encabezados_partidos_en_dos_lineas` (alto de encabezado crece, sin
asumir un múltiplo exacto). Suite completa de `test_gui_pagos.py` sin
regresiones (87 tests).

## Control de pagos (Carga y control): doce pedidos sobre vencimiento/importe/columna nueva/deshacer/etiquetas de conteo

Ronda grande de pedidos puntuales de la clienta sobre `_PanelCargaControl`
y `_DialogoEditarInstancia` (`app/gui/pantallas/control_pagos.py`):

- El campo Vencimiento, al editar, arranca en la fecha de hoy (no en
  "(sin fecha)") para que las flechas de teclado (`instalar_flechas_
  cambian_fecha_completa`) muevan la fecha real día por día desde un
  punto cercano, en vez de saltar desde la fecha mínima sentinel.
- El campo Importe acepta "." como separador decimal además de ",":
  `_SpinImporteControlPagos(_SpinMonto)` sobreescribe solo
  `valueFromText` — cambio acotado a Control de pagos, no al
  `_SpinMonto` compartido con Pagos.
- Editar un ítem Archivado lo reabre como Pendiente (disponible para
  abonar/archivar de nuevo).
- Enter en el campo Importe avanza el foco a los botones del diálogo
  (para poder confirmar con Espacio).
- Conceptos con medio de pago "tarjeta" (`es_medio_pago_tarjeta`,
  substring case-insensitive, mismo criterio que `_es_transferencia`/
  `_es_sobre` en el resto del sistema): Vencimiento queda deshabilitado,
  solo se carga Importe, y cargarlo marca la instancia Abonada
  directamente.
- Conceptos pagados a mano (caja de ahorro, no tarjeta): Vencimiento e
  Importe van siempre juntos — cargar uno sin el otro rechaza el
  diálogo con un aviso.
- Columna nueva "Cuenta/Id" después de "Afectación": texto libre,
  opcional, para el número de cuenta/servicio. Reusa `CampoLibre1` de
  `InstanciaControlPago` (confirmado por `schema.sql` que ese campo
  vive solo ahí, no en `ConceptoControlPago`) y se hereda de la
  instancia más reciente del mismo concepto que lo tenga cargado
  (`_cuenta_id_heredada`) al generar instancias nuevas o duplicar al
  período próximo — se comporta como si fuera un dato del concepto sin
  tocar el esquema. Ancho igual al de "Categoría", sacado mitad de
  "Nombre" y mitad de "Afectación".
- Los ítems Pendientes (sin vencimiento/importe) ya NO se archivan
  solos al avanzar de mes — quedan en pantalla indefinidamente hasta
  que se cargan o se archivan a mano. Se revierte `archivar_pendientes_
  del_periodo` (`app/negocio/control_pagos.py`), que una ronda anterior
  había sumado — se eliminó entera (función, llamada desde `avance_mes.
  py`, campo del resumen, test). El avance de mes sigue generando las
  instancias del período nuevo como siempre.
- Botón "↩" (Deshacer) al final de cada fila, habilitado solo si la
  fila tiene vencimiento o importe cargado: limpia los dos campos y
  vuelve el ítem a Pendiente. Ancho sacado mitad de "Nombre" y mitad de
  "Afectación".
- Ancho de "Importe" +20% (mismo reparto mitad "Nombre"/mitad
  "Afectación").
- Cargar o editar un concepto deja la selección de la tabla parada en
  esa fila (`_seleccionar_instancia`, llamado también después de crear,
  abonar, archivar y duplicar al período próximo).
- Cuatro etiquetas nuevas debajo de "Crear concepto": "Conceptos por
  cargar", "Con vencimiento hoy", "Con vencimiento mañana", "Con
  vencimiento en días" — y dos más debajo de "Eliminar registro
  duplicado": "Con vencimiento vencido", "Conceptos archivados", más
  "Total conceptos". Los siete conteos salen de `resumen_conteo_
  vencimientos` (`app/negocio/control_pagos.py`), compartida con la
  tarjeta nueva de Panel de control (ver más abajo) para no duplicar el
  cálculo — en "Carga y control" se calculan además los cuatro filtros
  en cascada que ya tenía la pantalla, mientras que en Panel de control
  es el total sin filtrar.

Tests: ~6 nuevos en `tests/test_control_pagos.py` (detección de tarjeta,
herencia de Cuenta/Id en generar/duplicar, `resumen_conteo_vencimientos`
de siete buckets), renombrado el test de avance de mes en `tests/
test_avance_mes.py` a `test_avanzar_mes_no_toca_las_instancias_de_
control_pagos_pendientes_del_periodo_cerrado`, y ~15 nuevos en `tests/
test_gui_control_pagos.py` (default de fecha, tarjeta deshabilita
vencimiento y auto-abona, pago manual exige los dos campos juntos,
columna Cuenta/Id, +20% de Importe, Deshacer habilitado/limpia, editar
archivado reabre a Pendiente, selección tras crear/editar, etiquetas de
conteo, foco a OK, parseo de "."). Suite completa: 23 + 40 tests,
verificados sin regresiones.

## Panel de control: se saca la sección "Alertas", se agrega el cuadro "Control de pagos"

Pedido explícito de la clienta: eliminar por completo la sección
"Alertas" de Panel de control, y sumar tres cuadritos más a la grilla
(ahora 9, en 3 filas de 3, en vez de 6 + Alertas aparte). El cuadrito
inferior izquierdo pasa a llamarse "Control de pagos" y replica las
siete etiquetas de conteo de "Carga y control" (mismo `resumen_conteo_
vencimientos`, sin los cuatro filtros que ahí sí se aplican, porque
Panel de control muestra el total real) — "Con vencimiento hoy"/"Con
vencimiento mañana" se resaltan en rojo y negrita cuando el conteo es
mayor a cero, el resto de las líneas queda siempre en texto plano. Los
otros dos cuadritos nuevos (inferior centro e inferior derecha) quedan
sin asignar por ahora — consultado explícitamente con la clienta vía
pregunta directa, eligió dejarlos vacíos (solo el título "(Sin
asignar):") en vez de definir su contenido en esta ronda.

Se eliminó de `app/negocio/panel_control.py` el dataclass `Alertas`,
`calcular_alertas` y sus helpers exclusivos (`_reserva_regular_activa`,
`_deuda_regulares_alerta`, `_planes_con_cuotas_vencidas`, `_fechas_
especiales_proximas`, `_categoria_x_con_llaves_pendientes`) —
confirmado por grep que ningún otro módulo los importa (otras pantallas
con nombres parecidos, ej. `mensajeria.py`/`placas.py`, tienen sus
propias funciones independientes). `_deuda_regulares`/`_deuda_aisladas`
se mantuvieron: los sigue usando `calcular_estadisticas_profesionales`
(el cuadrito "Profesionales", que no cambió). La grilla de tarjetas de
`PanelAvanceMes._armar_ui` pasa de una estructura hardcodeada (2 filas +
Alertas aparte) a un loop genérico sobre listas de 3 en 3, mismo
`stretch=1` por fila para que todas midan igual de alto.

Tests: eliminados 13 tests de alertas en `tests/test_panel_control.py`
y 7 en `tests/test_gui_panel_control.py` (3 de alertas puntuales + 2 de
ancho + 2 de scroll/estilo), renombrado/reescrito el test de "seis
tarjetas parejas" a `test_nueve_tarjetas_parejas_en_tres_filas`, y
sumados 4 tests nuevos: `test_tarjeta_control_pagos_muestra_los_siete_
conteos`, `test_tarjeta_control_pagos_resalta_vencimiento_hoy_y_mañana_
en_rojo_y_negrita`, `test_tarjeta_control_pagos_sin_vencimientos_
proximos_no_resalta`, `test_tarjetas_vacias_no_tienen_contenido_
asignado`. pyflakes limpio en los cuatro archivos tocados
(`app/gui/pantallas/panel_control.py`, `app/negocio/panel_control.py`,
`tests/test_panel_control.py`, `tests/test_gui_panel_control.py`);
suite completa de los dos archivos de test: 94 passed.

## Pagos (Registrar pagos): ancho de Monto/Saldo previo/Nuevo saldo para que entre "$ 0.000.000,00"

Pedido explícito de la clienta, ronda siguiente a la que las achicó un
40% del ancho natural (ver más arriba, "doble alto de encabezado..."):
en vez de un porcentaje relativo al contenido real (que varía según
los importes cargados), las tres columnas pasan a un ancho FIJO
calculado para que entre exactamente el texto "$ 0.000.000,00" —medido
con `QFontMetrics` sobre la fuente real de la tabla más un colchón
chico (`_TEXTO_MONTO_MAXIMO`/`_PADDING_COLUMNA_MONTO`, `app/gui/
pantallas/pagos.py`), mismo criterio ya usado en otras pantallas para
no depender de `resizeColumnsToContents()` cuando se necesita un ancho
exacto en vez de "lo que mida el contenido actual". Test reescrito:
`test_tabla_registrar_pagos_monto_saldos_anchas_para_el_formato_
maximo` (antes comparaba contra el 60% del ancho natural). Suite de
`test_gui_pagos.py`: 87 passed.

## Control de pagos ("Carga y control"): reordenar etiquetas, Vencimiento sin día de la semana, anchos Cuenta/Id -25%/Importe -20%, título "Filtros"

Cuatro pedidos puntuales de la clienta sobre `_PanelCargaControl` (`app/
gui/pantallas/control_pagos.py`):

- Las tres etiquetas de conteo que vivían debajo de "Eliminar registro
  duplicado" (columna 3) pasan a vivir debajo de las otras cuatro, en
  la misma columna 2 (debajo de "Crear concepto") — las siete quedan
  juntas, columna 3 se queda solo con los cuatro botones de acción
  sobre el concepto seleccionado.
- Vencimiento (tanto el `QDateEdit` de esta columna como el de
  `_DialogoEditarInstancia`, y el texto de la columna "Vencimiento" de
  la tabla) pasa a "dd-mm-yyyy", SIN el día de la semana abreviado que
  usa el resto del sistema (`_campo_fecha`/`_campo_fecha_opcional`,
  "ddd dd-MM-yyyy") — pedido puntual de esta pantalla, no una
  generalización. Nueva función `_campo_vencimiento_sin_dia` (envuelve
  `_campo_fecha_opcional` y le pisa el `displayFormat`) y `_fecha_dd_
  mm_yyyy` (texto de tabla) en vez de mostrar el AAAA-MM-DD crudo que
  se guarda en la base — el orden por click en el encabezado sigue
  ordenando por ese AAAA-MM-DD real (`_clave_orden_columna`), no se
  tocó.
- "Cuenta/Id" (que una ronda anterior fijó al ancho de "Categoría") se
  reduce un 25% más; "Importe" (que una ronda anterior fijó un 20% más
  ancho que su ancho natural) se reduce un 20% más. El ancho liberado
  lo siguen absorbiendo solas "Nombre"/"Afectación" (`Stretch`, sin
  cálculo manual).
- Título "Filtros" (`subtituloSeccion`, Nivel 2) arriba de "Nombre" en
  la columna 4, y una línea divisoria vertical nueva (`QFrame.Shape.
  VLine`, `_linea_divisoria_vertical`) entre las columnas 3 y 4.

Tests nuevos en `tests/test_gui_control_pagos.py`: `test_las_siete_
etiquetas_de_conteo_viven_todas_en_la_columna_2`, `test_columna_4_
tiene_titulo_filtros_y_linea_divisoria_con_columna_3`, `test_
vencimiento_formato_dd_mm_yyyy_en_campo_y_en_tabla`, `test_dialogo_
editar_instancia_campo_vencimiento_formato_dd_mm_yyyy`; reescritos
`test_tabla_carga_control_cuenta_id_despues_de_afectacion_y_ancho_25_
por_ciento_menos_que_categoria` y `test_tabla_carga_control_importe_
un_20_por_ciento_mas_ancho_menos_un_20_por_ciento` (antes contra el
75%/80% de más arriba). Suite: 50 passed.

## Control de pagos ("Historial"): columnas al mínimo/al formato, Vencimiento sin día, "Editar registro" restringido a períodos viejos, orden por click + F5

Cinco pedidos puntuales de la clienta sobre `_PanelHistorialControlPagos`
(`app/gui/pantallas/control_pagos.py`), que hasta esta ronda no tenía
ningún ajuste de ancho propio (las columnas 1-4 en `Stretch`, el resto
al tamaño default de Qt, nunca tocado):

- "Período"/"Vencimiento" al ancho mínimo que entra el título sin
  cortar (mismo criterio que `imagenes._ajustar_columnas`: `QFontMetrics`
  sobre la fuente real del encabezado + `_COLCHON_TITULO_COLUMNA`).
- Vencimiento a "dd-mm-yyyy" sin día de la semana, mismo criterio y
  mismas funciones (`_campo_vencimiento_sin_dia`/`_fecha_dd_mm_yyyy`)
  que la ronda de "Carga y control" de más arriba.
- "Importe" al ancho de "$ 0.000.000,00" (`_TEXTO_IMPORTE_MAXIMO`/
  `_PADDING_COLUMNA_IMPORTE`, mismo criterio que `pagos._TEXTO_MONTO_
  MAXIMO`).
- El ancho liberado por los tres puntos de arriba lo absorben solas
  "Nombre"/"Afectación": para que "Categoría"/"Medio de pago" dejen de
  competir por ese espacio, salen de `Stretch` y pasan a
  `ResizeToContents` (antes las cuatro —Nombre, Categoría, Afectación,
  Medio de pago— eran `Stretch` por igual).
- "Editar registro" pasa a estar restringido a un registro VIEJO (de
  un período anterior al actual, `instancia["Periodo"] < periodo_
  actual(conn)`): uno del período actual o de uno posterior (duplicado
  al próximo) se edita desde "Carga y control", que tiene el resto de
  la lógica de ese período (tarjeta, vencimiento+importe juntos,
  duplicar/eliminar duplicado) que el diálogo de "Historial" no
  replica. El botón sigue habilitándose con cualquier selección (igual
  que antes); es `_editar_registro` el que, al click, si el
  seleccionado no es viejo, muestra una alerta explicando el por qué en
  vez de abrir el diálogo.
- Tabla ordenable por click en el encabezado (`OrdenTabla`, mismo
  mecanismo que "Carga y control"/"Registrar pagos") y F5 (`reiniciar`,
  nuevo: limpia selección, orden y los cuatro filtros) — antes esta
  solapa no tenía ningún `reiniciar()`, F5 no hacía nada en ella.

Tests nuevos: `test_historial_editar_registro_bloqueado_para_periodo_
actual_con_alerta`, `test_historial_editar_registro_permite_un_periodo_
viejo`, `test_historial_columnas_periodo_y_vencimiento_al_minimo_e_
importe_para_formato_maximo`, `test_historial_vencimiento_formato_dd_
mm_yyyy_en_tabla`, `test_historial_tabla_ordenable_por_click_en_
encabezado`, `test_historial_f5_reinicia_filtros_orden_y_seleccion`.
Suite completa de `test_gui_control_pagos.py` (incluye esta solapa y
"Carga y control"): 50 passed. pyflakes limpio en `app/gui/pantallas/
control_pagos.py`, `app/gui/pantallas/pagos.py` y los dos archivos de
test tocados.

## Balance del negocio: "Gastos" rediseño completo + nivel Afectación "Localidad" + Ingresos/Resultado/Estadísticas varios ajustes chicos

Ronda grande, la solapa "Gastos" pasa de ser el catálogo genérico
`catalogos.pantalla_gastos_operativos` (`PantallaCRUD`) a un panel
bespoke (`_PanelGastos`, `app/gui/pantallas/balance.py`) — pedido
explícito de la clienta de tratarla igual que el resto de las
pantallas ya rediseñadas (Carga y control, Historial). El catálogo
genérico queda eliminado (sin otro consumidor) junto a sus helpers
privados (`_al_abrir_dialogo_gasto`, `_resolver_conflicto_gasto`,
`_titulo_subtotal_periodo`, los tres `_opciones_*_o_ninguno_gasto`) —
`_opciones_edificio`/`_opciones_unidad`/`_opciones_consultorio`/
`_opciones_localidad` (sin el sufijo, plain) siguen en `catalogos.py`
y ahora los importa `balance.py` (import cruzado de un símbolo
privado, mismo criterio ya usado en el resto del sistema).

### Nivel nuevo "Localidad" en Afectación/Alcance de un gasto

Pedido explícito de la clienta: un gasto extraordinario puede afectar
a una Localidad entera, no solo a Espacio general/Edificio/Unidad/
Consultorio. `ALCANCES_GASTO` (`app.negocio.gastos_operativos`) suma
"Localidad" (`sanear_alcance` actualizado para el quinto nivel).
`GastoOperativo` suma la columna `IdLocalidad` — mismo problema que
cuando se sumó Consultorio (el CHECK de `Alcance` no admite un `ALTER
TABLE` que lo ensanche): `_ampliar_alcance_gasto_a_localidad`
(`app.db.migraciones`) recrea la tabla entera, mismo patrón que
`_ampliar_alcance_gasto_a_consultorio`, corre justo después de esa en
`aplicar_migraciones`. `app.negocio.balance._distribuir_gasto_por_
consultorio` suma la rama "Localidad": mismo reparto en cascada que
"Espacio general" (Edificio→Unidad→Consultorio, partes iguales en
cada escalón), pero acotado a UNA localidad — arranca un escalón más
abajo en vez de repartir primero entre todas las que haya (se extrajo
`_por_localidad` como helper interno, reusado por los dos casos).
`texto_afectacion_gasto` (`gastos_operativos`, nueva) da el texto
legible de la Afectación de un gasto para la tabla/filtros, los 5
niveles — mismo criterio que `control_pagos.texto_afectacion`.

### `_PanelGastos`/`_DialogoGasto` (`app/gui/pantallas/balance.py`)

- Columnas de tabla, en este orden: Período, Nombre, Categoría,
  Afectación, Monto, Origen, Observación — "Período" al ancho mínimo
  que entra el título sin cortar (`QFontMetrics` + colchón, mismo
  criterio que `control_pagos._PanelHistorialControlPagos`) y
  centrado. Orden de filas: Período, Afectación, Categoría, Nombre.
- Período con `SelectorPeriodo` (mismo widget que Ingresos/Resultado),
  arranca en el período actual — reemplaza el `QLineEdit` de texto
  libre que tenía el catálogo genérico.
- Debajo de "Eliminar": línea divisoria, subtotal del período (en
  NEGRITA, etiqueta e importe — pedido explícito; nunca lo tocan los
  filtros de más abajo, solo el período elegido), otra línea
  divisoria, título "Filtros" y los mismos cuatro filtros en cascada
  mutua con sentinel "Todos/Todas" que ya usa la columna 4 de "Carga y
  control" (Nombre/Categoría/Afectación, más "Origen" nuevo) + botón
  "Reiniciar filtros" — estos filtros solo ocultan filas de la tabla,
  nunca cambian el período cargado ni el subtotal (CLAUDE.md, "Filtros
  que solo afectan la visualización").
- "Nuevo"/"Editar" abren `_DialogoGasto`: Categoría ofrece las
  categorías de Control de pagos (`CategoriaControlPagos`, antes
  `CategoriaGasto`) en vez de las propias de Gastos; "Alcance" se
  renombra "Afectación" y suma el selector de Localidad (cascada
  igual a antes, extendida a 5 ramas: solo el combo que corresponde al
  Alcance elegido queda habilitado); Origen siempre "Manual", sin
  ningún combo para cambiarlo (un `QLabel` nomás) — lo Importado se
  sincroniza solo desde "Carga y control" de Control de pagos
  (`sincronizar_gasto_operativo`) y se edita desde ahí, nunca desde
  "Gastos"; "Concepto" pasa a llamarse "Nombre" (dialogo y tabla).
  "Editar" sobre un gasto con Origen "Importado" queda bloqueado con
  una alerta explicando por qué (mismo patrón que la restricción de
  "Editar registro" de "Historial" en la ronda anterior) — Eliminar NO
  tiene esta restricción (no hay riesgo de pisar el Origen real).
- El conflicto Manual/Importado (mismo Periodo+Concepto, Orígenes
  distintos) se sigue resolviendo igual que el catálogo genérico
  (`gasto_en_conflicto`, pregunta si reemplazar) — sigue siendo
  relevante aunque "Nuevo" solo cree Manual, porque puede chocar
  contra uno Importado ya sincronizado.
- `reiniciar()` (F5): período al actual, filtros y selección a cero.
  "Nuevo"/"Editar"/"Eliminar" muestran alerta de éxito.

### Ingresos/Resultado

Columna "Período" de la tabla pasa a centrada (`item_centrado` en vez
de `QTableWidgetItem` simple) — pedido explícito, sin otro cambio
(ya tenían `reiniciar()` y no tienen ningún botón que modifique
datos, así que no les hacía falta ninguna alerta de éxito nueva).

### Tests

`tests/test_gastos_operativos.py` (+9: sanear_alcance con Localidad,
texto_afectacion_gasto); `tests/test_migraciones.py` (+1: migración
IdLocalidad); `tests/test_balance.py` (+1: prorrateo Localidad);
`tests/test_catalogos.py` (removidos ~24 tests del catálogo genérico
de baja); `tests/test_gui_balance.py` (+18: columnas/orden/ancho/
centrado de Gastos, Nuevo/Editar/Eliminar/conflicto, filtros/subtotal/
F5, diálogo, alertas de éxito, Período centrado en Ingresos/
Resultado). pyflakes limpio en los nueve archivos tocados (`app/db/
schema.sql`, `app/db/migraciones.py`, `app/negocio/gastos_operativos.
py`, `app/negocio/balance.py`, `app/gui/pantallas/balance.py`,
`app/gui/pantallas/catalogos.py`, y los cuatro de test).

## Estadísticas: conteo de Localidades corregido + columna Período centrada + anchos a todo el ancho de pantalla

Tres pedidos puntuales de la clienta sobre "Historial general"/
"Estadísticas varias" (`app/gui/pantallas/estadisticas.py`, `app.
negocio.estadisticas`):

- **Bug real encontrado**: "Localidades" contaba TODAS las filas de la
  tabla `Localidad` (`conteo_entidades`, sin alcance), incluyendo las
  que la clienta usa únicamente para un `InmueblePersonal` (inmueble
  propio fuera del negocio, sin relación con el espacio — ver su
  comentario en `schema.sql`) — con 3 Localidades cargadas (1 con el
  único Edificio del espacio, 2 solo de inmuebles personales) mostraba
  3 en vez de 1. Se corrige a `COUNT(DISTINCT IdLocalidad) FROM
  Edificio` (mismo criterio que `balance._localidades_con_algun_
  edificio`, sin el bucket "Sin localidad" porque acá no es una
  Localidad real para contar) — `COUNT(DISTINCT ...)` ya descarta los
  `NULL` solo. Los otros tres conteos (Edificios/Unidades/
  Consultorios) y las ramas CON alcance (Localidad/Edificio/Unidad/
  Consultorio puntual) no tenían este problema, no se tocaron.
- Columna "Período" de las dos tablas centrada (`item_centrado`).
- Anchos de columna repartidos para aprovechar todo el ancho de
  pantalla: las 11 columnas (todas de importancia pareja, mismo
  criterio que `balance._armar_tabla`) ya no quedan al ancho justo de
  `resizeColumnsToContents()` (que suele dejar un tramo sin usar a la
  derecha del panel) — se reparte el sobrante en partes iguales entre
  las 11 (`_ajustar_columnas`, nueva). Reusa `_TablaConAnchoDinamico`
  (`app.gui.pantallas.imagenes`, import cruzado) para recalcular cada
  vez que la tabla cambia de tamaño (al construirse y al redimensionar
  la ventana), no solo una vez al cargar datos.

Tests: `tests/test_estadisticas.py` (+1: `conteo_entidades` con el
caso real de la clienta, 3 Localidades → 1); `tests/test_gui_
estadisticas.py` (+2: columna Período centrada en las dos tablas,
anchos repartidos hasta el ancho del viewport). Suite: 18 + 26 passed,
más 125 passed en la corrida conjunta con `test_estadisticas_pantalla.
py`/`test_gui_imagenes.py` (confirma que el import cruzado de
`_TablaConAnchoDinamico` no rompe nada). pyflakes limpio en `app/
negocio/estadisticas.py`, `app/gui/pantallas/estadisticas.py` y los
dos archivos de test.

## Gastos: bug real de un concepto repetido para distintas unidades + anchos de columna

Tres pedidos puntuales de la clienta sobre "Gastos" (Balance del
negocio), el más importante un bug real: "tengo dos alquileres, uno
por la unidad del 9no 'C' y otro por la del 15 'H', solo me muestra y
computa la del 15 'H'... puede haber un mismo concepto repetido para
distintas unidades" — y explícito: "si en algún momento te pedí que
esta solapa reduzca a un item no lo hagas, quiero que detalle todo lo
que se imputa al período y luego compute todo para la suma" (nunca se
había pedido eso; se verificó que `_PanelGastos.actualizar()` ya
listaba todas las filas de `GastoOperativo` sin ningún `GROUP BY` ni
dedup — la pantalla nunca colapsó nada, así que la causa estaba en
otro lado).

**Causa real**: `sincronizar_gasto_operativo` (`app/negocio/
control_pagos.py`, el puente entre "Carga y control" y "Gastos" — ver
su docstring de módulo) encontraba "el `GastoOperativo` ya
sincronizado para este concepto" buscando por `Periodo` + `Concepto`
(el NOMBRE, texto libre) + `Origen='Importado'`. El nombre no es
único — dos `ConceptoControlPago` distintos pueden compartir nombre
(ej. "Alquiler" del 9no "C" y del 15 "H") — así que sincronizar el
segundo encontraba y pisaba la fila del primero en vez de crear una
propia, y uno de los dos quedaba "perdido" en Balance del negocio. El
mismo lookup por nombre existía también en `eliminar_instancia_
duplicada` (deshacer un "Duplicar para período próximo" hecho por
error) — mismo riesgo de borrar el gasto del concepto equivocado,
arreglado con el mismo criterio.

**Arreglo**: `GastoOperativo` suma `IdConceptoControlPago` (FK a
`ConceptoControlPago.IdConcepto`, nullable, solo se usa para
`Origen='Importado'` — ver el comentario en `schema.sql`, es una
referencia hacia adelante dentro del mismo script, válida porque
SQLite solo valida FKs en tiempo de DML, no de DDL). `sincronizar_
gasto_operativo`/`eliminar_instancia_duplicada` ahora buscan por esa
identidad estable, nunca por el nombre — dos conceptos con el mismo
nombre quedan en dos filas de `GastoOperativo` separadas, cada una
siempre al día con SU propia instancia.

La columna nueva se agrega con dos migraciones en `app/db/
migraciones.py`, en este orden específico (importa: `GastoOperativo`
ya pasó por DOS migraciones de "recrear la tabla entera" en rondas
anteriores — Consultorio y Localidad — para ensanchar el CHECK de
`Alcance`, y esas dos tienen su propia lista hardcodeada de columnas
que no sabe nada de columnas agregadas por el camino genérico; agregar
`IdConceptoControlPago` por ese camino se habría perdido silenciosamente
cuando esas dos migraciones corrieran después):
- `_agregar_id_concepto_control_pago_a_gasto`: corre DESPUÉS de las dos
  migraciones que recrean `GastoOperativo` — para este punto la tabla
  ya tiene su forma final, un simple `ALTER TABLE ... ADD COLUMN`
  alcanza (esta columna no tiene ningún CHECK que lo impida).
- `_corregir_gastos_importados_sin_identidad_de_concepto`: repara el
  daño que el bug ya hizo en bases existentes — borra los
  `GastoOperativo` Origen='Importado' que quedaron con
  `IdConceptoControlPago` NULL (todos los que existían antes del fix,
  por diseño ambiguos/pisados) y vuelve a sincronizar TODAS las
  `InstanciaControlPago` con Importe cargado, regenerando una fila
  correcta y separada por concepto con el monto ACTUAL de cada
  instancia (no hay forma de recuperar el monto exacto que un gasto ya
  perdido tenía antes de perderse). Idempotente: si no hay huérfanos no
  hace nada, segura de correr en cada arranque.

Los otros dos pedidos, de ancho de columna: "Nombre"/"Categoría"/
"Afectación" ganan un 30% de ancho (`Interactive` en vez de
`ResizeToContents`, ancho natural × 1.3 calculado después de cargar
las filas) sacado de "Observación" — sale solo, sin ningún cálculo
manual, porque es la única columna en `Stretch`.

Tests: `tests/test_control_pagos.py` (+2: dos conceptos con el mismo
nombre para unidades distintas sincronizan/editan/vacían gastos
separados sin pisarse, mismo escenario para `eliminar_instancia_
duplicada`); `tests/test_migraciones.py` (+1: simula el estado ya
dañado — una fila Importado sin la identidad nueva — y confirma que
`aplicar_migraciones` la repara, regenerando dos filas correctas,
idempotente en una segunda corrida); `tests/test_gui_balance.py` (+1:
las tres columnas miden 1.3× su ancho natural, ±1px). Suite: 25 + 41 +
37 passed. pyflakes limpio en `app/db/migraciones.py`, `app/negocio/
control_pagos.py`, `app/gui/pantallas/balance.py` y los tres archivos
de test.

## Carga y control: ancho de "Importe" para el formato máximo

Mismo pedido ya aplicado en "Registrar pagos" (Monto/Saldo previo/
Nuevo saldo) e "Historial" de este mismo módulo: "Importe" pasa de un
% relativo a su ancho natural (que varía según los importes cargados
en pantalla) a un ancho FIJO calculado con `QFontMetrics` para que
entre exactamente "$ 0.000.000,00" (`_TEXTO_IMPORTE_MAXIMO`/
`_PADDING_COLUMNA_IMPORTE`, ya existían, reusados tal cual — antes solo
los usaba "Historial"). El ancho que esto libera lo sigue absorbiendo
sola "Nombre"/"Afectación" (`Stretch`, sin cálculo manual). Test
reescrito: `test_tabla_carga_control_importe_ancho_para_el_formato_
maximo` (antes comparaba contra natural×1.2×0.8). Suite de `test_gui_
control_pagos.py`: 50 passed.

## Panel de control: reordenar "Estadísticas principales" + corregir Total liquidado/Saldo pendiente

Dos pedidos sobre el cuadrito "Estadísticas principales mes en curso"
(`PanelAvanceMes`, `app/gui/pantallas/panel_control.py`):

- Reorden pedido explícitamente: "Gastos operativos"/"Balance de
  negocio" pasan a estar inmediatamente después de "Total ingresos";
  "Total liquidado"/"Saldo pendiente de cobro (de lo liquidado)" quedan
  al final (antes estaban en el medio, antes de Gastos/Balance).
- Auditoría pedida de "Total liquidado"/"Saldo pendiente": "Total
  liquidado" (`_total_liquidado_periodo`, `app/negocio/panel_control.
  py`) YA estaba correcto de una ronda anterior (dedup a la última
  emisión por profesional vía `MAX(IdLiquidacion) GROUP BY
  IdProfesional`, sobre `MontoGenerado` — que ya incluye todos los
  conceptos: especiales, descuentos de feriados/vacaciones/licencias,
  horas agregadas, aisladas, cuotas de plan — todo lo que la clienta
  describió), no hizo falta tocarlo.

  **Bug real encontrado y arreglado en "Saldo pendiente de cobro"**
  (`_saldo_pendiente_periodo`): el ejemplo que dio la clienta — "total
  liquidado $10.000, un profesional tiene que abonar $500, abona $600 y
  deja $100 a favor del próximo mes, el saldo pendiente tiene que decir
  $9500, no $9400" — exponía que el cálculo restaba lo cobrado de TODOS
  los profesionales de una sola vez contra el total liquidado global
  (`total_liquidado - SUM(HistorialPagos.Monto)` sin agrupar), sin
  ningún tope por profesional: el sobrepago de uno terminaba reduciendo
  el saldo pendiente de los demás en vez de quedar como crédito propio
  a favor del mes próximo. Se reescribe para calcular profesional por
  profesional (liquidado de su última emisión del período vs. cobrado
  imputado a ese mismo período) y sumar los pendientes individuales,
  cada uno acotado a no bajar de $0 (`max(Liquidado - Pagado, 0)`) — el
  que pagó de más aporta $0, nunca un valor negativo que termine
  compensando la deuda de otro.

Tests: `tests/test_panel_control.py` (+1: escenario exacto del ejemplo
de la clienta, dos profesionales, uno sobrepaga y el otro no paga nada,
saldo pendiente = $9500 no $9400 — el test preexistente de saldo
pendiente de un solo profesional sigue pasando tal cual, el cálculo por
profesional coincide con el global cuando hay uno solo);
`tests/test_gui_panel_control.py` (+1: orden de las cinco etiquetas en
el texto de la tarjeta). Suite: 32 + 64 passed, más 281 passed en la
corrida conjunta con `test_control_pagos.py`/`test_migraciones.py`/
`test_gui_balance.py`/`test_gui_control_pagos.py`/`test_balance.py`/
`test_gastos_operativos.py` (confirma que ningún cambio de esta ronda
pisó a los anteriores). pyflakes limpio en `app/negocio/panel_control.
py`, `app/gui/pantallas/panel_control.py` y los dos archivos de test.

## Gastos: tabla ordenable + F5 + otro 25% de ancho; Panel de control: segundo bug real en Saldo pendiente (signo de HistorialPagos.Monto)

### Gastos: orden por click + F5, y otro 25% de ancho

Dos pedidos puntuales más sobre "Gastos" (`_PanelGastos`, `app/gui/
pantallas/balance.py`), ronda siguiente a la de más arriba:

- Tabla ordenable por click en el encabezado — mismo mecanismo
  (`OrdenTabla`, `app/gui/widgets/orden_tabla.py`) que "Carga y
  control"/"Historial"/"Registrar pagos": un click ordena por esa
  columna, otro click invierte, y el criterio es transitorio (se pierde
  al reconstruirse el panel). `reiniciar()` (F5) ahora también llama
  `self._orden.reiniciar()`, mismo criterio que el resto del sistema
  (CLAUDE.md, "F5... reinicia desde cero").
- "Nombre"/"Categoría"/"Afectación" ganan otro 25% de ancho SOBRE el
  30% ya aplicado la ronda anterior — cascada, mismo criterio que
  "Cuenta/Id"/"Importe" de "Carga y control" (natural×1.3×1.25, el
  ancho liberado lo sigue absorbiendo sola "Observación").

### Panel de control: segundo bug real en "Saldo pendiente de cobro" — el signo de `HistorialPagos.Monto`

La clienta mandó capturas Y la base de datos real del espacio,
preguntando directamente qué incluye cada concepto porque "no
encuentro relación" entre los números — el cuadrito real mostraba
Saldo pendiente $21.242.875, MÁS GRANDE que Total liquidado
$14.220.133, matemáticamente imposible con el cálculo de la ronda
anterior si el signo fuera el asumido (la suma de pendientes por
profesional, cada uno acotado a no superar su propio liquidado, nunca
puede superar la suma total liquidada).

**Causa real**: la ronda anterior (ver más arriba) corrigió el "sin
tope por profesional" pero siguió asumiendo que `HistorialPagos.Monto`
es positivo para un pago real ("debía $500, pagó $600"). Es al revés:
`app.negocio.pagos.registrar_pago` (su propio docstring) guarda
`Monto` CON SIGNO — **negativo** para un pago recibido (resta de la
cuenta, reduce lo que debe) y **positivo** para un cargo/ajuste (suma,
aumenta lo que debe); confirmado también en la GUI de "Registrar
pagos" (`nuevo_saldo = saldo_total + monto`, un monto negativo hace
bajar el saldo). La fórmula de la ronda anterior RESTABA `Pagado` (la
suma de `Monto`) de `Liquidado`, así que un pago real (negativo) en vez
de reducir el pendiente lo AUMENTABA — exactamente lo que mostraba la
base real: cuanto más pagó un profesional, más alto salía su
"pendiente". Verificado armando un script puntual contra la base real
adjunta (`get_connection` + `calcular_estadisticas_principales`):
reproducía el mismo $21.242.875 del cuadrito, y con la fórmula
corregida (sumar en vez de restar) baja a $7.631.152 — ya por debajo
del total liquidado, como corresponde.

**Arreglo**: `_saldo_pendiente_periodo` pasa de `max(Liquidado -
Pagado, 0)` a `max(Liquidado + Pagado, 0)` por profesional — sumar el
NETO de los movimientos del período (no restarlo) es lo que corresponde
al signo real: un pago real (negativo) sigue reduciendo el pendiente
(ahora sí, al sumarlo), y un ajuste positivo (un cargo que aumenta la
deuda del período) ahora SUMA al pendiente en vez de restarle, que es
el comportamiento correcto para ese caso.

Los dos tests de la ronda anterior que simulaban un pago con `Monto`
POSITIVO (irreal — un pago real nunca se guarda así) se corrigen a
`Monto` negativo, manteniendo el mismo resultado esperado en pesos
(la fórmula corregida da el mismo número que la fórmula vieja daba con
el signo vuelto al revés, así que los valores esperados de los tests
no cambiaron, solo el signo de la entrada). Se suma un test nuevo para
el caso de un ajuste positivo (debía cubrir el caso que la ronda
anterior no contemplaba: un cargo, no un pago, imputado al período).

Tests: `tests/test_panel_control.py` (signo corregido en los dos tests
de saldo pendiente existentes — `Monto=-4000`/`Monto=-600` en vez de
positivo —, +1 nuevo:
`test_estadisticas_principales_saldo_pendiente_un_ajuste_positivo_
suma_deuda_del_periodo`); `tests/test_gui_balance.py` (+2: `test_
gastos_tabla_ordenable_por_click_en_encabezado`, `test_gastos_f5_
tambien_reinicia_el_orden`; reescrito el test de ancho a la cascada
×1.3×1.25). Suite: 33 + 38 passed, más 168 passed en la corrida
conjunta con `test_balance.py`/`test_gastos_operativos.py`/`test_
gui_panel_control.py`. pyflakes limpio en `app/gui/pantallas/
balance.py`, `app/negocio/panel_control.py` y los tres archivos de
test tocados. Verificado además contra la base de datos real adjunta
por la clienta (`espacio_ramos.db`) que el número final del cuadrito
queda por debajo del total liquidado, como corresponde.

## Panel de control: desglose de "Total liquidado" (feriados/vacaciones/aisladas/cuotas)

La clienta preguntó, con capturas reales, por qué "Monto por reservas
regulares" sale más alto que "Total liquidado" y cómo se calcula cada
concepto — se le explicó (y se confirmó con su base real) que la
diferencia viene de que "Monto por reservas regulares"/"Monto por
reservas aisladas" miran la grilla/reservas VIGENTE tal cual, mientras
que "Total liquidado" resta lo que la liquidación de cada profesional
descuenta por ausencias reales del mes (feriados no trabajados,
vacaciones, licencias) y suma lo que no está en la grilla regular
(aisladas, cuotas de planes de pago). A pedido explícito, esas cuatro
líneas se agregan al cuadrito para que la diferencia se vea de un
vistazo, entre "Total liquidado" y "Saldo pendiente de cobro".

**Tres preguntas de la clienta, respondidas con el código real (no solo
de palabra, confirmado leyendo `app.negocio.liquidaciones`/`vacaciones`/
`licencias`):**

1. El subtotal de reservas regulares (`Tramo.subtotal`, usado tanto por
   `monto_neto_regular_periodo` como por `calcular_liquidacion`) YA está
   neto del descuento por volumen de horas semanales — nunca es el
   bruto.
2. Feriados (recalculado día a día, con el % vigente ESE día —
   `_monto_feriado_dia`) y vacaciones/licencias (`ValorBonificado`,
   congelado al cargar la vacación/licencia pero YA calculado con el %
   vigente en ese momento, ver `crear_vacacion`/`crear_licencia`) también
   están netos de ese mismo descuento — ninguno de los dos trabaja sobre
   el valor bruto.
3. **Hallazgo real, corrige una suposición equivocada de la clienta**:
   "Monto por reservas aisladas" (`monto_neto_aislada_periodo`, en
   `app.negocio.estadisticas`) NO filtra por categoría de profesional —
   suma TODAS las `ReservaAislada` confirmadas del período, incluidas
   las de categoría A (que nunca entran en ninguna liquidación mensual,
   se cobran aparte). Confirmado con la base real: de las aisladas de
   noviembre, 58 eran de profesionales A y solo 20 de R — la mayoría del
   monto que se ve en ese cuadrito corresponde a profesionales que
   jamás tienen una liquidación. Dato a tener en cuenta para la "vista
   previa de balance del negocio" que la clienta quiere armar en el
   octavo cuadrito (en espera de más definición de su parte).

### Implementación

`DesgloseLiquidaciones`/`_desglose_liquidaciones_periodo` (`app/
negocio/panel_control.py`, nuevo campo `EstadisticasPrincipales.
desglose_liquidaciones`): recorre los profesionales con una
`LiquidacionEmitida` este período (misma población que `_total_
liquidado_periodo`) y recalcula la liquidación de cada uno AHORA con
`calcular_liquidacion` — mismo criterio "en vivo" que ya usan `monto_
neto_regular_periodo`/`monto_neto_aislada_periodo` en este mismo
cuadrito (puede no coincidir centavo a centavo con el `MontoGenerado`
ya congelado si algo cambió después de emitida la liquidación, mismo
caso ya documentado para feriados/aisladas — sirve para explicar de un
vistazo, no para una reconciliación exacta). Categoría E (se consolida
en la liquidación de su R) y categoría B (nunca se liquida) hacen que
`calcular_liquidacion` tire `ValueError` — se ignoran en el loop, su
aporte ya está contado en la liquidación del R que las consolida.
`descuento_feriados`/`descuento_vacaciones_licencias` se guardan en
NEGATIVO (restan, mismo signo con el que ya trabaja `formatear_moneda`
para mostrar el "-" solo); `aisladas_en_liquidaciones`/`cuotas_planes_
pago` en positivo (suman). Tiempo medido contra la base real de la
clienta (109 profesionales): 0.175s — no hace falta ningún `Procesando`.

Tests: `tests/test_panel_control.py` (+2: escenario con los cuatro
conceptos a la vez —feriado, vacación, aislada, cuota de plan—, montos
verificados contra las mismas fórmulas de `calcular_liquidacion`; y
una `LiquidacionEmitida` de categoría E con `MontoGenerado=0` no rompe
el desglose); `tests/test_gui_panel_control.py` (+1: las cuatro líneas
quedan entre "Total liquidado" y "Saldo pendiente de cobro"). Suite:
35 + 65 passed, más 153 passed en la corrida conjunta con `test_
liquidaciones.py`. pyflakes limpio en `app/negocio/panel_control.py`,
`app/gui/pantallas/panel_control.py` y los dos archivos de test.

## Reservas aisladas/extraordinarias: cargar una a un profesional A marca su mensaje como enviado en Centro de mensajería

Dos pedidos puntuales de la clienta sobre "Centro de mensajería", a
partir del flujo de "Reservas aisladas"/"Reservas extraordinarias"
(`app/gui/pantallas/reservas.py`):

- Cargar (crear/confirmar/cancelar/modificar) una reserva aislada o
  extraordinaria a un profesional A ya copia el mensaje de detalle al
  portapapeles (`_copiar_mensaje_detalle`, sin cambios en eso) — ahora
  ADEMÁS llama a `marcar_mensaje_aislada_generado` (`app.negocio.
  mensajeria`, ya existía, hasta ahora solo la llamaba el botón
  "Generar texto" del Centro de mensajería) cuando el profesional es
  categoría A, así que ese profesional queda celeste->azul en el acto,
  sin tener que pasar por esa pantalla a mano. Mismo arreglo duplicado
  en las dos clases que tienen su propio `_copiar_mensaje_detalle`
  (`_PanelReservasAisladas`/`_PanelReservaExtraordinaria`), mismo
  criterio de "cada pantalla arma lo suyo" que ya usa el resto del
  archivo.
- El período que se marca como generado es `periodo_actual(conn)` (el
  de HOY, igual que `_copiar_mensaje_detalle` ya usaba para armar el
  mensaje) — NUNCA el período de la fecha de la reserva que se está
  cargando. Esto es justamente lo que deja conforme al segundo pedido
  de la clienta sin tocar nada más: "el celeste... que solo tenga
  sentido con el avance de mes" — una reserva cargada en noviembre para
  diciembre (`mensaje_detalle_reserva_aislada` ya arma un solo mensaje
  con "del mes" + "posteriores") deja azul a NOVIEMBRE nomás; la fila
  de `EstadoMensajeriaPeriodo` de diciembre para ese profesional nunca
  se toca, así que al llegar diciembre (avance de mes) sigue celeste —
  recordatorio de que ese mes puntual todavía no se le mandó nada,
  aunque la reserva ya estuviera cargada de antes.

Tests nuevos en `tests/test_gui_reservas.py`: `test_crear_reserva_
aislada_de_profesional_a_marca_mensaje_generado_queda_azul`, `test_
crear_reserva_aislada_de_profesional_a_para_el_mes_siguiente_no_lo_
marca_azul_ese_mes` (noviembre queda azul, diciembre sigue celeste —
`color_profesional` llamado con los dos períodos), `test_crear_reserva_
extraordinaria_de_profesional_a_marca_mensaje_generado_queda_azul`.
pyflakes limpio en `app/gui/pantallas/reservas.py`.

## Panel de control ("Avance de período, backup, y vista rápida"): rediseño completo de la grilla + "Estadísticas principales mes en curso" con tres cuentas en cascada; Balance del negocio ("Ingresos"): columnas rediseñadas

Pedido explícito de la clienta, mensaje textual (ver el hilo completo
para la redacción exacta de cada línea — se resume acá el resultado):
"Vamos a rediseñar la solapa... El tercer cuadro 'Ocupación y horas mes
en curso' ponelo en el segundo cuadro... El sexto cuadro 'Cumpleaños y
días de profesión' lo pones debajo del cuadro 'Feriados y fechas
especiales próximas'... Quedaron libres los tres cuadros de la derecha,
esos los vamos a unificar, queda un solo cuadro largo, ahi vamos a
poner todas las estadísticas mas detalladas". Avisó explícitamente:
"Avisame por cualquier duda, comentario o sugerencia" — se le hicieron
4 preguntas de aclaración antes de tocar código (ver abajo, cada una
cambió o confirmó una parte del diseño).

### Grilla: de 3x3 pareja a 2 columnas de 3 + 1 columna larga

La clienta corrigió por su cuenta una primera lectura equivocada del
pedido (yo había asumido que el séptimo cuadro quedaba "mezclado" con
Feriados en el mismo marco — nunca fue así, los corrigió antes de que
se tocara código): "Van a quedar dos columnas de tres cuadritos, y una
columna entera de un solo cuadro a la derecha, en total son 7, 6 chicos
y uno largo." Con el orden exacto que dio:

- Columna 1 (de arriba a abajo): "Período actual y último backup",
  "Profesionales", "Control de pagos".
- Columna 2 (de arriba a abajo): "Ocupación y horas mes en curso",
  "Feriados y fechas especiales próximas", "Cumpleaños y días de
  profesión".
- Columna 3: un solo cuadro LARGO, "Estadísticas principales mes en
  curso" (ver abajo).

Se eliminan los dos cuadritos "(Sin asignar)" que habían quedado libres
de la ronda anterior — ya no hace falta nada vacío en este diseño.
`_armar_ui` (`app/gui/pantallas/panel_control.py`) pasa del loop
genérico sobre una grilla 3x3 (`QHBoxLayout` por fila) a dos `QVBoxLayout`
("columna_1"/"columna_2", tres cuadritos cada una con `stretch=1`) más
un `QHBoxLayout` externo ("fila_columnas") que pone esas dos columnas
y la tarjeta larga como tres hermanos, los tres con `stretch=1` — así
las tres "columnas" quedan del mismo ancho, y la columna larga queda
del alto de las otras dos juntas (sus tres cuadritos chicos + el
espaciado entre ellos). Se elimina `_armar_tarjeta_vacia` (de baja, sin
otro uso) y la constante `_COLUMNAS_GRILLA` (ya no hace falta, el
armado deja de ser un loop genérico sobre N columnas).

### "Estadísticas principales mes en curso": rediseño completo, tres cuentas en cascada

Diseño pedido por la clienta, tres secciones con subtítulo en itálica,
línea divisoria antes del total, y el total en negrita:

1. **"Liquidaciones mes en curso"**: Monto neto reservas regulares +
   Descuentos por feriados no trabajados (resta) + Descuentos por
   vacaciones (resta) + Descuentos por licencias (resta) + Reservas
   aisladas + Feriados trabajados + Cargos especiales + Cuotas de
   planes de pago + Otros ajustes = **Total liquidado mes en curso**.
2. **"Resultado del negocio"**: Total liquidado mes en curso + Horas
   aisladas por fuera de la liquidación + Reservas extraordinarias por
   fuera de la liquidación + Otros conceptos por fuera de la
   liquidación − Gastos operativos = **Balance del negocio**.
3. **"Monto a cobrar en el mes en curso"**: Monto liquidado más horas
   aisladas − Monto cobrado hasta el momento = **Monto restante del
   mes a cobrar**.

Cuatro preguntas de aclaración, y las cuatro decisiones que fijaron:

- **Q1** (si "Monto total liquidado" en Ingresos/Resultado debía seguir
  filtrando por ubicación): la clienta eligió la opción recomendada,
  "Deja de filtrarse por ubicación" — una liquidación es por
  PROFESIONAL, no se puede partir prolijamente por Consultorio (los
  descuentos de feriados/vacaciones no son por ubicación).
- **Q2** (qué hacer con los conceptos más raros de una liquidación —
  reversión de descuento, feriados pendientes, horas agregadas, ajuste
  por saldo atrasado, ajuste de redondeo — que no tenían línea propia
  en el diseño original de 8 líneas): "Sumarlos en una línea extra
  'Otros ajustes'" — así "Total liquidado mes en curso" cierra SIEMPRE
  exacto con la suma de las liquidaciones recalculadas, nunca "si no
  coincide es porque falta algún concepto".
- **Q3** (cómo tratar lo que generan los profesionales categoría A por
  fuera de cualquier liquidación, más allá de las aisladas): la
  clienta agregó, con el mismo criterio que "Horas aisladas por fuera
  de la liquidación", dos líneas más — "Reservas extraordinarias por
  fuera de la liquidación" y "Otros conceptos por fuera de la
  liquidación" (llaves + cargos especiales sueltos) — y pidió que
  "Monto cobrado hasta el momento" considere los tres para que la
  cuenta cierre ("las horas aisladas, las reservas extraordinarias y
  los conceptos especiales"). En "Ingresos" (Balance del negocio), la
  columna pasa a llamarse "Ingresos por fuera de las liquidaciones" y
  reflejar la suma de esos mismos tres conceptos.
- **Q4** (la disposición exacta de la grilla): corrigió una lectura
  equivocada mía (ver arriba) y dio el orden exacto de las dos
  columnas de 3 + la columna larga.

### Negocio: `DesgloseLiquidaciones` (10 campos) + `DesgloseFueraDeLiquidacion` (nueva, en `balance.py`)

`app/negocio/panel_control.py`, `DesgloseLiquidaciones` pasa de 4
campos a 8 líneas visibles + `otros_ajustes` (catch-all) + `cobrado_r`
(no se muestra como línea propia, solo alimenta la Sección 3) — los 8+1
campos suman EXACTO la misma fórmula que `Liquidacion.monto_generado`
(verificado término a término contra esa property), así que "Total
liquidado mes en curso" (`DesgloseLiquidaciones.total`, property nueva)
nunca puede "no coincidir" por faltar un concepto. `_desglose_
liquidaciones_periodo` sigue recalculando EN VIVO con `calcular_
liquidacion` para cada profesional con una liquidación emitida este
período (igual que antes) — `cobrado_r` se calcula reusando la fórmula
ya establecida de "pendiente acotado por profesional" (`pendiente =
max(monto_generado + pagado, 0)`, con `pagado` negativo para un pago
real) y derivando `cobrado = monto_generado - pendiente`.

`app/negocio/balance.py` suma `DesgloseFueraDeLiquidacion` (`aisladas_
normales`/`reservas_extraordinarias`/`otros_conceptos`/`cobrado`, +
property `bruto`) y `fuera_de_liquidacion_periodo`: recorre cada
profesional categoría A (nunca tiene liquidación mensual propia) y
arma, por `Fecha` real del movimiento (a diferencia del desglose de
arriba, que mira si algo "entra" en una liquidación, no la fecha real):
aisladas comunes (mismo criterio que `app.negocio.mensajes.
movimiento_periodo_aislada`, duplicado a propósito en vez de reusar esa
función para no tocar un camino compartido con Centro de mensajería —
mismo criterio de duplicación aceptada entre módulos sin relación que
ya usa el resto del sistema), reservas extraordinarias (`MontoExtraordinario`
a mano), y "otros conceptos" (depósitos/reintegros de `LlaveMovimiento`
+ `CargoEspecial` sin `IdLlave`, para no contar dos veces un cargo ya
atado a una llave). `cobrado` usa el mismo tope por profesional que
`cobrado_r`.

`monto_liquidado_periodo` (nueva, `balance.py`) reemplaza a la vieja
`_total_liquidado_periodo` de `panel_control.py` (de baja, junto con
`_saldo_pendiente_periodo`, también de baja) — es el valor FROZEN (el
`MontoGenerado` real tal como se facturó, con los valores vigentes al
emitir cada liquidación), a propósito DISTINTO del recálculo en vivo
de `DesgloseLiquidaciones` — Ingresos/Resultado pueden mostrar
cualquier período histórico, así que no tiene sentido reconstruirlo con
tarifas de HOY. Los dos valores coinciden en el caso normal (nada
cambió desde la emisión) pero pueden divergir si algo cambió después
— divergencia aceptada, documentada en el docstring de la función.
`ingresos_feriados_trabajados_periodo` queda eliminada (de baja, sin
otro consumidor) — ese concepto ya viene incluido dentro del
`MontoGenerado` congelado.

`total_ingresos_periodo` pasa a devolver `(monto_liquidado, fuera_de_
liquidacion_bruto)` en vez de la tupla de 3 vieja — `ids_consultorio`
queda como parámetro sin usar (compatibilidad de firma con
`resultado_periodo`, que SÍ sigue filtrando Gastos operativos por
ubicación). `resultado_periodo` no cambia de firma, solo de qué suma
para "ingresos".

### GUI: `app/gui/pantallas/panel_control.py` y `app/gui/pantallas/balance.py`

`_armar_tarjeta_estadisticas_principales` deja de ser un solo `QLabel`:
pasa a ser un `QWidget` con su propio `QVBoxLayout` (mismo patrón que
"Período actual y último backup") con, por cada una de las tres
secciones, un subtítulo en itálica (`_subtitulo_italica`, nuevo
helper), una etiqueta de detalle (`QLabel` con las líneas de esa
sección), una línea divisoria (`_linea_divisoria`, ya existía) y una
etiqueta de total en negrita (`setStyleSheet("font-weight: bold;")`) —
con una línea de espacio (`addSpacing(12)`) entre una sección y la
siguiente. `actualizar()` llena cada una de esas seis etiquetas por
separado en vez de un único `setText` con todo el bloque.

"Ingresos" (`_PanelIngresos`, `balance.py`): `_COLUMNAS_INGRESOS` pasa
de 5 columnas a 4 (`"Período"`, `"Monto total liquidado"`, `"Ingresos
por fuera de las liquidaciones"`, `"Total ingresos"` — se elimina la
columna de feriados y días especiales, ya absorbida dentro de "Monto
total liquidado"); `_fila`/`_llenar_filas` desempaquetan la tupla nueva
de 2 valores de `total_ingresos_periodo` en vez de la de 3. "Resultado"
no cambia de columnas, solo hereda el "Total ingresos" nuevo.

### Tests

`tests/test_balance.py`: reescritos los tests de `total_ingresos_
periodo` (ahora usa `emitir_liquidacion` real en vez de calcular en
vivo desde reservas sueltas — el "monto liquidado" es FROZEN), eliminado
el test de `ingresos_feriados_trabajados_periodo` (función de baja),
+1 nuevo (`test_fuera_de_liquidacion_periodo_desglosa_tres_conceptos_y_
acota_el_cobrado`, con aislada+extraordinaria+llave+pago de más).
`tests/test_panel_control.py`: reescritos los tests de "saldo
pendiente" (ya no existe — ahora prueban `monto_cobrado`/`monto_
restante_a_cobrar`, con reservas reales + `emitir_liquidacion` en vez
de filas de `LiquidacionEmitida` a mano, porque el recálculo en vivo ya
no lee `MontoGenerado`), reescrito el test de "no duplica reemisiones"
(ahora prueba que el `GROUP BY` no recalcula dos veces al mismo
profesional), actualizados los nombres de campo en los tests de
desglose (`descuento_vacaciones_licencias` → `descuento_vacaciones`/
`descuento_licencias`). `tests/test_gui_panel_control.py`: eliminados
los tests de los cuadritos vacíos y de "siete tarjetas"/"tres filas"
(de baja), +4 nuevos sobre la tarjeta larga (`test_seis_tarjetas_
chicas_y_la_tarjeta_larga_quedan_del_mismo_ancho`, `test_tarjeta_larga_
queda_del_alto_de_sus_tres_hermanas_chicas`, `test_tarjeta_
estadisticas_principales_tres_subtitulos_en_itálica_y_en_orden`, `test_
tarjeta_estadisticas_principales_orden_de_las_tres_secciones`), 1
corregido (`test_hay_una_linea_divisoria_entre_los_dos_botones`, acotado
a las líneas hijas directas del panel, ya que la tarjeta larga suma sus
propias tres). `tests/test_gui_balance.py`: encabezados de "Ingresos"
actualizados, `test_ingresos_recalcula_al_cambiar_periodo` reescrito
con `emitir_liquidacion` real. Suite completa de los cuatro archivos de
negocio/GUI tocados: sin regresiones nuevas (ver CLAUDE.md, "Fallos
conocidos del sandbox/contenedor" para los ~10 fallos preexistentes
ajenos a esta ronda). pyflakes limpio en los ocho archivos tocados.

