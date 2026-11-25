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

Sumado en la ronda de redefinición de saldos: otros 3 tests de
`test_gui_mensajeria.py` (`test_marcar_enviada_emite_liquidacion_
genera_pdf_y_baja_a_gris`, `test_tildar_enviada_despues_de_ordenar_
afecta_al_profesional_correcto`, `test_categoria_x_gris_queda_al_final_
del_grupo_gris`) dependen del mismo reloj real del sandbox, por otra
vía: `_debe_recordar_fin_de_mes` (`app.negocio.mensajeria`) pasa un
profesional de gris a bordó cuando faltan pocos días reales para fin de
mes (`DiasAntesFinMesRecordatorioGeneral`), así que corriendo la suite
cerca de fin de mes estos tests (que asumen "gris") ven "bordo" en su
lugar. Confirmado con `git stash` que reproducen igual sin ningún
cambio de esta ronda — no es una regresión, mismo criterio que los
otros 10 ("si reaparecen, no bloquean cerrar una ronda").

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

## Cuatro pedidos puntuales: Carga y control (etiquetas), Panel de control (negrita sin itálica), Profesionales (calendario de nacimiento), Mensajes predefinidos (variables de llaves + orden + F5)

### Carga y control: etiquetas "Saldo a cubrir Bco {Nombre}"

Pedido explícito de la clienta: "Saldo a cubrir en CA Bco Patagonia"/
"...en CA Bco Provincia" pasan a "Saldo a cubrir Bco Patagonia"/"...Bco
Provincia" — mismo formato que ya tenían Hipotecario/Macro, sin el "en
CA" de más (`_actualizar_etiquetas_expensas_bancos`, `app/gui/
pantallas/control_pagos.py`). Test actualizado: `test_etiquetas_
expensas_y_saldos_bancarios_muestran_los_valores_de_saldos_expensas_y_
bancos`.

### Panel de control: subtítulos y subtotales en negrita, sin itálica ni subrayado

Pedido explícito de la clienta sobre el cuadro largo "Estadísticas
principales mes en curso": "sacá la itálica de los subtítulos y los
subtotales del cuadro largo, sacá los subrayados también, que tanto
los subtítulos estén en negrita y los subtotales con los importes
también" — tercera vuelta de estilo de este mismo elemento (itálica
+subrayado → itálica sin subrayar en los totales → esta ronda, negrita
a secas en los dos). `_subtitulo_italica` se renombra `_subtitulo_
negrita` (`app/gui/pantallas/panel_control.py`, `font-weight: bold;`
en vez de itálica+subrayado) y los tres `etiqueta_total_liquidado`/
`etiqueta_balance_negocio`/`etiqueta_monto_restante_a_cobrar` pasan de
`"font-style: italic;"` a `"font-weight: bold;"`. Tests reescritos:
`test_tarjeta_estadisticas_principales_tres_subtitulos_en_negrita_y_en_
orden`, `test_tarjeta_estadisticas_principales_los_tres_totales_van_en_
negrita`.

### Profesionales: calendario de Fecha de nacimiento arranca en el año 2000

Pedido explícito de la clienta: "que el año arranque en el 2000 para a
partir de ahí seleccionar la fecha de nacimiento del profesional" — sin
tocar nada más del campo (sigue mostrando "(sin fecha)" hasta elegir un
día, sigue vacío/opcional). `Campo` (`app/gui/crud_generico.py`) suma
`anio_calendario_inicial: int | None`: para un campo `tipo="fecha"` sin
valor cargado (ni `requerido` ni `default_hoy`), `_crear_entrada` llama
`entrada.calendarWidget().setCurrentPage(anio, 1)` justo después de
dejar la fecha en el sentinel "(sin fecha)" — reposiciona la página
visible del popup del calendario SIN tocar el valor real (confirmado
con un script puntual: `date()`/`text()` siguen en "(sin fecha)" después
del `setCurrentPage`). Antes, el popup arrancaba en 1900 (`_FECHA_SIN_
DATO` de `crud_generico.py`), bastante más lejos de una fecha de
nacimiento típica que el 2000 pedido. `_campos_profesional`
(`app/gui/pantallas/profesionales.py`) suma `anio_calendario_
inicial=2000` al `Campo("FechaNacimiento", ...)` ya existente. Tests
nuevos en `tests/test_profesionales.py`: `test_fecha_nacimiento_
calendario_arranca_en_el_anio_2000_en_un_alta_nueva`, `test_fecha_
nacimiento_ya_cargada_no_salta_al_anio_2000`.

### Mensajes predefinidos: variables de depósito/promedio de llaves + orden por Categoría/Descripción + F5 reinicia los 5 selectores de contexto

Tres pedidos puntuales de la clienta:

- Tres variables nuevas, con el mismo criterio de redondeo:
  `{promedio_valor_llave_edificio}`/`{promedio_valor_llave_unidad}`
  (promedio del `ValorDepositoActual` de las llaves ACTIVAS de ese
  Tipo, "redondeando para arriba en múltiplos de 100 sin centavos") y
  `{deposito_juego_llaves}` (suma de los dos anteriores — "es el valor
  de la única del edificio mas el promedio del valor de las llaves de
  las unidades"). `promedio_valor_llave`/`_promedio_redondeado_arriba`/
  `deposito_juego_llaves` nuevas en `app/negocio/llaves.py`; alcance
  GLOBAL de todo el espacio, sin distinguir localidad/edificio puntual
  (mismo criterio que `nombre_espacio`/`nombre_administrador_
  principal`, las otras variables fijas de esta pantalla). Formato de
  texto (`$14.000`, sin espacio ni decimales) vía `_moneda_mensaje`
  nueva en `app/gui/pantallas/mensajes_predefinidos.py` — duplica a
  propósito `app.negocio.mensajes._moneda` (privada, sin relación de
  dependencia entre los dos módulos, mismo criterio que `_nombre_
  espacio`/`_nombre_administrador_principal` ya duplicadas ahí), NO
  `app.negocio.formato.formatear_moneda` (que usa "$ " con espacio y
  decimales, formato de tabla/PDF, no de mensaje de texto). La grilla
  de botones de variables (`_armar_fila_variables`, `crud_generico.py`)
  ya era genérica en 5 columnas fijas — con las 13 variables totales
  pasa sola a 3 filas (2 de 5 + una de 3), sin tocar ese mecanismo.
- "Los mensajes predefinidos que estén ordenados por categoría primero,
  y luego por descripción": el orden de FILAS por defecto (sin ningún
  click en un encabezado) dejaba de ser el de inserción/rowid de
  `self.repositorio.listar()`. Se envuelve esa instancia en
  `_armar_ui` (mismo criterio ya usado ahí para envolver `self.crud.
  actualizar`): `self.crud.repositorio.listar` pasa a ordenar siempre
  por `(Categoria, Descripcion)` antes de que `PantallaCRUD.actualizar`
  haga lo suyo — `sorted` es estable, así que un click en otra columna
  (`OrdenTabla`) sigue funcionando normal, este orden de base solo
  cambia el desempate entre filas iguales en esa columna.
- "F5 refresca a valores iniciales": `reiniciar()` solo tocaba el
  filtro de Categoría y la tabla — ahora también resetea los cinco
  selectores de contexto (Dirigido a, Localidad/Edificio/Unidad/
  Consultorio) a su valor "En general"/"Nadie en particular" (índice 0).
  Alertas de éxito ("toda la solapa"): confirmado que Nuevo/Editar/
  Eliminar YA las mostraban (mecanismo genérico de `PantallaCRUD`, sin
  ninguna supresión en esta pantalla) — "Copiar mensaje" se deja sin
  alerta, mismo criterio que TODO el resto del sistema para una copia
  al portapapeles (Centro de mensajería, Reservas: ningún botón
  "Copiar"/"Generar texto" muestra cartel).

Tests: `tests/test_llaves.py` (+5: promedio de una sola llave, redondeo
con valores distintos, sin ninguna llave, ignora inactivas, suma de
los dos promedios). `tests/test_mensajes_predefinidos.py` (+7: las tres
variables nuevas sustituidas en la vista previa incluido el redondeo y
el filtro de inactivas, orden por defecto Categoría+Descripción, F5
resetea los cinco selectores; 2 tests preexistentes actualizados de
10 a 13 variables totales, y la grilla de 2x5 a 3 filas de 5 columnas).
Suite conjunta de `test_llaves.py`/`test_mensajes_predefinidos.py`/
`test_gui_control_pagos.py`/`test_gui_panel_control.py`/`test_panel_
control.py`/`test_profesionales.py`/`test_mensajes.py`/`test_
balance.py`: 399 passed, 1 failed — el fallo es el ya documentado de
calibración de fuentes del sandbox en Profesionales (ver "Fallos
conocidos del sandbox/contenedor" más arriba), ajeno a esta ronda.
pyflakes limpio en los seis archivos de app/ tocados (`app/gui/
pantallas/control_pagos.py`, `app/gui/pantallas/panel_control.py`,
`app/gui/crud_generico.py`, `app/gui/pantallas/profesionales.py`,
`app/negocio/llaves.py`, `app/gui/pantallas/mensajes_predefinidos.py`)
y los cuatro de test.

## Profesionales/PDF: checkbox "Ocultar condiciones de Vacaciones/Licencias en el PDF"

Pedido explícito de la clienta, mismo patrón que el checkbox "Ocultar
hora de liberación" de una ronda anterior:

> "Quisiera agregar un check mas en editar registro de los
> profesionales, como el que me hiciste antes en ese cuadro que dice
> 'Ocultar hora de liberación en el PDF', por defecto destildado. Esto
> es para que me saque de las condiciones que se imprimen en el PDF de
> las liquidaciones lo que aclara en los puntos referidos a
> 'Vacaciones' (3), Licencia por maternidad (11), Licencia por
> matrimonio (12). El resto igual, renumerado desde 1 en adelante sin
> saltear ningún número, lo único que omite son los puntos que te
> enumeré recién."

`Profesional` suma la columna `OcultarCondicionesVacacionesLicenciasPdf`
(booleana, default 0 — mismo mecanismo de `ALTER TABLE ... ADD COLUMN`
que `OcultarHoraLiberacionPdf`, en `schema.sql` y `_COLUMNAS_NUEVAS`).
`_campos_profesional` (`app/gui/pantallas/profesionales.py`) suma el
`Campo` booleano correspondiente, debajo del de "Hora de liberación".

`condiciones_normas` (`app/pdf/valores_pdf.py`) suma el parámetro
`excluir_vacaciones_licencias: bool = False`: sin marcar, comportamiento
de siempre (cada punto numerado con su `Numero` real de la base, que
puede tener huecos si algún punto está inactivo). Marcado, filtra los
puntos con `Numero` en `{3, 11, 12}` (`_NUMEROS_CONDICIONES_
VACACIONES_LICENCIAS`, los números reales de "Vacaciones"/"Licencia
por maternidad"/"Licencia por matrimonio") y renumera el resto de
manera SECUENCIAL desde 1 — a diferencia del caso sin marcar, que usa
el `Numero` real tal cual, el caso con exclusión nunca puede mostrar un
hueco porque ya no tiene sentido mostrar el `Numero` original (quedó
elegido a propósito para que cierre justo sin un profesional). `generar_
pdf_liquidacion` (`app/pdf/liquidacion_pdf.py`) le pasa el flag ya
resuelto desde `profesional["OcultarCondicionesVacacionesLicenciasPdf"]`.

Tests: `tests/test_valores_pdf.py` (+4: sin excluir sigue usando el
`Numero` real con huecos, excluyendo omite los tres puntos, renumera
1..18 sin saltear con los 21 sembrados por defecto, el texto de los
puntos que quedan no cambia). `tests/test_pdf_liquidacion.py` (+2:
integración end-to-end con/sin el profesional tildado).
`tests/test_profesionales.py` (+3: mismo trío de tests que "Hora de
liberación" — arranca destildado, se guarda tildado, precarga tildado
al editar). Suite conjunta de `test_valores_pdf.py`/`test_pdf_
liquidacion.py`/`test_profesionales.py`/`test_migraciones.py`: 186
passed, 1 failed — el fallo es el ya documentado de calibración de
fuentes del sandbox en Profesionales (ver "Fallos conocidos del
sandbox/contenedor" más arriba), ajeno a esta ronda. pyflakes limpio
en `app/pdf/valores_pdf.py`, `app/pdf/liquidacion_pdf.py`, `app/db/
migraciones.py`, `app/gui/pantallas/profesionales.py` y los tres
archivos de test tocados.

## Tres pedidos puntuales: Archivos para enviar (Procesando), Panel de control (separar las tres cuentas), Llaves (depósito abonado por defecto)

### Archivos para enviar: cartel "Procesando..." mientras se regeneran los archivos

Pedido explícito de la clienta: "Agregar relojito de arena y leyenda
procesando como en las liquidaciones durante el tiempo en el que se
regeneran los archivos." `_PanelArchivosVarios._regenerar_seleccionado`
(`app/gui/pantallas/archivos_varios.py`, solapa "Archivos para enviar"
de "Disponibilidad") llamaba directo a `generar_pdfs_propuesta_por_
localidad`/`generar_pdfs_disponibilidad_por_localidad` (un PDF por
localidad, `app/pdf/propuesta_pdf.py`/`app/pdf/disponibilidad_pdf.py`)
sin ningún indicador — a diferencia de Liquidaciones, el loop "uno por
localidad" vive DENTRO de esas funciones de negocio, no en la pantalla,
así que no alcanzaba con envolver la llamada en `with Procesando(...)`
a secas (el cartel se mostraría pero quedaría congelado, sin animar,
durante toda la regeneración).

Las dos funciones suman un parámetro opcional `on_avance: Callable[[],
None] | None = None`, llamado una vez por cada PDF de localidad ya
generado (mismo criterio en ambas, mínimo cambio: un `if on_avance is
not None: on_avance()` dentro del loop que ya armaba la lista de
rutas). `_regenerar_seleccionado` pasa `procesando.tick` como ese
callback:

```python
with Procesando(self, f"Regenerando {etiqueta}...") as procesando:
    rutas = self._generador(clave)(self.conn, directorio, on_avance=procesando.tick)
```

Mismo mecanismo compartido (`app/gui/widgets/procesando.py`) que ya
usan las liquidaciones — nada nuevo ahí.

Tests: `tests/test_pdf_disponibilidad.py`/`tests/test_pdf_propuesta.py`
(+1 cada uno: `on_avance` se llama una vez por localidad generada).
`tests/test_gui_archivos_varios.py` (+1: `Procesando` se instancia una
vez al regenerar; el test existente `test_regenerar_sin_archivos_
generados_no_rompe_la_vista_previa`, que monkeypatchea el generador con
un lambda de dos argumentos, se actualiza a tres con `on_avance=None`
para no romper con la nueva firma). pyflakes limpio en los tres
archivos de `app/` tocados y los tres de test.

### Panel de control: separar visualmente las tres cuentas de "Estadísticas principales mes en curso"

Pedido explícito de la clienta: "El fondo del contenido de todo el
recuadro de 'Estadísticas principales mes en curso' es todo gris,
separame las tres cuentas con un espacio en blanco finito aunque sea,
como el fondo del título del cuadro, como para que visualmente las
tres secciones dentro del cuadro queden diferenciadas." Investigado
antes de tocar nada: el cuadrito (`QFrame#cuadritoInfo`, `_tarjeta` en
`app/gui/pantallas/panel_control.py`) nunca tuvo un `background-color`
propio — solo el borde — así que tanto el título como el contenido de
abajo caían al gris default de Qt por igual (confirmado armando la
pantalla real offscreen y muestreando píxeles: título y contenido daban
el mismo `#efefef`, ningún color "blanco" preexistente en ningún lado
de este cuadrito en particular).

Cada una de las tres cuentas ("Liquidaciones mes en curso"/"Resultado
del negocio"/"Monto a cobrar en el mes en curso") pasa a envolverse en
su propio widget con objectName nuevo `seccionEstadisticas`
(`_seccion_estadisticas()`, nueva en `panel_control.py`), con fondo
blanco (`t['superficie']`, misma regla QSS que ya usa `QWidget#
panelSolapa` — sumada en `app/gui/estilos.py`) y un margen propio
(`setContentsMargins(6, 6, 6, 6)`). El `addSpacing(12)` que ya separaba
una cuenta de la siguiente queda igual (sigue siendo del mismo gris que
el resto del contenido escrolable, sin pintar nada) — pero ahora, al
estar entre dos secciones blancas, se ve como el "espacio en blanco
finito" pedido: tres cuadros blancos recortados contra el gris de
fondo, en vez de un bloque gris liso sin ninguna separación. Nada de
esto toca los otros cinco cuadritos del panel (`cuadritoInfo` en sí no
cambió, el objectName nuevo es exclusivo de estas tres secciones).

Tests actualizados en `tests/test_gui_panel_control.py`: los dos que
asumían que las seis etiquetas vivían directo en un único `contenido`
compartido (`test_tarjeta_estadisticas_principales_linea_en_blanco_
antes_del_primer_subtitulo`/`test_tarjeta_estadisticas_principales_
orden_de_las_tres_secciones`) se reescriben para subir un nivel más
(`_contenido_estadisticas`, nuevo helper de test) y, en el segundo,
chequear el orden de las TRES secciones entre sí además del orden
detalle→total DENTRO de cada una. Test nuevo:
`test_tarjeta_estadisticas_principales_las_tres_secciones_tienen_
fondo_blanco`. Verificado armando la pantalla real offscreen y
comparando colores de píxeles antes/después (ver captura enviada:
las tres cuentas en blanco, separadas por el gris del cuadrito).
pyflakes limpio en `panel_control.py`/`estilos.py`/el archivo de test.

### Llaves: diálogo de carga a profesional — ya estaba resuelto

Pedido: "Cuando se cargue una llave a un profesional que por defecto
en el cuadro de diálogo el depósito sea 'Depósito abonado (se cobra el
monto)'." Investigado antes de tocar nada: `_DialogoAsignar.combo_
deposito` (`app/gui/pantallas/llaves.py`) ya agrega "Depósito abonado
(se cobra el monto)" como PRIMER ítem (índice 0, el default de todo
`QComboBox` recién creado) desde una ronda anterior — ya documentado en
un comentario en el propio código ("pedido explícito posterior de la
clienta: cuando asigno una llave por defecto que el depósito sea
Depósito abonado") y cubierto por un test ya existente,
`test_dialogo_asignar_arranca_en_abonado_con_monto_habilitado`
(`tests/test_gui_llaves.py`), que sigue pasando tal cual. Lo único que
puede forzarlo a "Bonificado" es `_al_cambiar_profesional` cuando el
profesional elegido es categoría B (regla de negocio aparte, confirmada
por la clienta en su momento: "un profesional B nunca paga depósito").
No hacía falta ningún cambio de código — este pedido quedaba
satisfecho por trabajo de una ronda anterior; se cierra solo con la
verificación.

## Cuatro pedidos puntuales: Panel de control (colores invertidos + refresco diario), Vacaciones (orden), General (maximizado), Reservas aisladas (bug de superposición)

### Panel de control: sacar la línea en blanco inicial e invertir el esquema de color de "Estadísticas principales"

Pedido explícito de la clienta, ronda siguiente a la de "separar
visualmente las tres secciones": "eliminá esa línea en blanco inicial
arriba de 'Liquidaciones mes en curso', luego invertí los colores de
fondo, todo lo que son las cuentas tiene que estar en gris, y las
líneas intermedias en blanco, o sea al revés que ahora." Investigado
antes de tocar nada (armando la pantalla real offscreen y muestreando
píxeles): el cuadrito (`QFrame#cuadritoInfo`) nunca tuvo un
`background-color` propio — título y contenido caían los dos al mismo
gris default de Qt (`#efefef`), así que "el fondo del título" de la
ronda anterior no era, en rigor, un blanco ya existente — era solo la
referencia de diseño general del sistema.

`_seccion_estadisticas()` (envuelve cada una de las tres cuentas) pierde
su objectName/fondo blanco — vuelve a ser un `QWidget` liso, que
muestra el gris del cuadrito por detrás, igual que el resto del
contenido. El objectName blanco (`t['superficie']`) se muda al
separador INTERMEDIO: `_separador_estadisticas()`, nueva función,
`QWidget` de alto fijo (12px) con objectName `separadorEstadisticas`
(`estilos.py` sube la regla, reemplazando a la vieja `#seccionEstadisticas`)
— se agrega entre cuenta 1→2 y cuenta 2→3 (dos en total), nunca antes
de la primera ni después de la última. El `addSpacing(12)` que
separaba la primera cuenta del título del cuadrito se saca directo, sin
reemplazo — confirmado offscreen que, de paso, esto saca también el
scroll vertical de más que aparecía en el cuadrito (ya no hay contenido
de sobra para el alto disponible).

Tests en `tests/test_gui_panel_control.py`: los dos que asumían fondo
blanco en las cuentas se reescriben (`test_tarjeta_estadisticas_
principales_las_tres_cuentas_sin_fondo_propio` confirma objectName
vacío, `test_tarjeta_estadisticas_principales_los_separadores_
intermedios_tienen_fondo_blanco` confirma exactamente dos widgets
`separadorEstadisticas`); el de la línea en blanco inicial se invierte
(`test_tarjeta_estadisticas_principales_sin_linea_en_blanco_antes_del_
primer_subtitulo`, ahora exige que el primer ítem con widget sea el
índice 0). pyflakes limpio en `panel_control.py`/`estilos.py`/el
archivo de test. Suite conjunta de `test_gui_panel_control.py`/`test_
panel_control.py`: 105 passed.

### Panel de control: refrescar cumpleaños/fechas especiales contra la fecha real, no la del día que se abrió la app

Pedido explícito de la clienta: "Noto que si dejo el sistema abierto de
un día para otro la info que muestra en esa pantalla queda anclada al
día que se abrió, por ejemplo me sigue marcando en rojo cumpleaños de
personas de hace dos días, si se puede que con cada proceso que
refresque el contenido de esa pantalla de acuerdo al día real de la
fecha." Investigado antes de tocar nada: `fecha_real`/`cumpleanos_y_
dias_profesion_proximos` (`app/negocio/dias.py`/`app/negocio/panel_
control.py`) ya recalculan `date.today()` en vivo cada vez que se
llaman — no había ningún valor cacheado ahí. El problema real es que
nada volvía a llamar a `actualizar()` (el método que arma TODO el
contenido de la solapa, incluido el resaltado en rojo de "hoy" en
Cumpleaños/Fechas especiales) con solo el paso del tiempo: solo corría
al construir la pantalla, al volver a entrar a la solapa (`showEvent`)
o con F5 — dejando el sistema abierto en esa misma solapa de un día
para el otro, sin tocar nada, nunca lo volvía a llamar.

El timer del reloj en vivo (`self._timer_reloj`, ya corría cada
segundo para `_actualizar_reloj`, que solo tocaba `etiqueta_reloj`)
pasa a comparar la fecha real contra `self._fecha_ultima_
actualizacion` (nueva, guardada al construir la pantalla) y, si cambió
(cruzó la medianoche), dispara `self.actualizar()` completo una sola
vez — no hace falta recalcular todo cada segundo, solo el día en que
efectivamente cambia. Tests nuevos en `tests/test_gui_panel_control.py`
(mockean `datetime.now`, mismo criterio que el test ya existente del
reloj): `test_actualizar_reloj_dispara_actualizar_completo_al_cruzar_
la_medianoche`, `test_actualizar_reloj_no_dispara_actualizar_completo_
en_el_mismo_dia`; el test preexistente del reloj se actualiza para la
llamada extra a `datetime.now()` que suma `_fecha_ultima_
actualizacion` en el constructor.

### Vacaciones: orden por defecto Año calendario → Desde → Hasta → Código de profesional

Pedido explícito de la clienta: "que la tabla esté ordenada primero por
'Año calendario' de menor a mayor, luego por 'Desde', luego por
'Hasta', luego por Código de profesional." `_PanelVacaciones.actualizar`
(`app/gui/pantallas/novedades.py`) ordenaba antes por código de
profesional primero y Desde como único desempate — se invierte la
prioridad completa: la clave de orden pasa a ser `(FechaDesde[:4],
FechaDesde, FechaHasta, clave_orden_codigo(...))`. "Año calendario" es
literalmente el año de `FechaDesde` (mismo valor que ya muestra esa
columna en la tabla, `r["FechaDesde"][:4]`), así que ordenar por
`FechaDesde` completo ya alcanza para los dos primeros criterios a la
vez — se deja igual el año explícito como primer elemento de la tupla
para que la intención quede clara en el código, aunque sea redundante
hoy. El orden por click en un encabezado (`OrdenTabla`) no se toca —
sigue aplicándose DESPUÉS como un `sort` estable adicional, este orden
de base solo cambia el desempate entre filas iguales en esa columna.

Test nuevo en `tests/test_gui_novedades.py`:
`test_vacaciones_orden_por_defecto_anio_desde_hasta_codigo` — arma dos
profesionales (R1/R2, insertados a propósito en el orden inverso al que
tienen que terminar en la tabla) y vacaciones fuera de orden cubriendo
los cuatro niveles de desempate (años distintos, mismo Desde con Hasta
distinto, mismo Desde Y Hasta con código distinto). Suite completa de
`test_gui_novedades.py`: 144 passed.

### General: "cada tanto se distorsiona la pantalla" — sin patrón identificable, no se tocó código

Pedido/comentario de la clienta: "Cada tanto es como que se distorsiona
la pantalla y hay que tocar maximizar dos veces para que este efecto no
se dé, si se te ocurre algo... quedo atento a tu comentario." Este bug
(Windows, nunca reproducible en este sandbox Linux) ya tiene cinco
rondas de investigación documentadas en `docs/historial/general.md`
("Ventana principal: maximizado se destapa al entrar a la primera
solapa") — la última dejó el reafirmado doble (restaurar→maximizar,
dos veces, diferido con `QTimer.singleShot`) disparando SOLO en el
primer cambio de solapa real de la sesión (`self._recien_ingresado`),
con la clienta confirmando en su momento que, pasado ese primer cambio,
navegar entre distintas solapas ya andaba bien (al punto de sacar el
mismo reafirmado de F5 por pedido explícito, para no repetirlo sin
necesidad).

Antes de tocar código, se le preguntó a la clienta con qué parece
coincidir esta nueva aparición (¿al volver de minimizar/alt-tab?
¿después de dejarlo abierto mucho tiempo? ¿al cerrar un diálogo?) para
acotar el disparador real sin arriesgar una reintroducción del parpadeo
que se sacó a propósito de F5. Respuesta: "No tengo un patrón claro /
pasa sin más" — sin ningún disparador identificable, no hay forma de
armar una mitigación dirigida ni de verificar que una nueva no rompa el
caso ya confirmado como resuelto. Se deja sin tocar código esta ronda;
si vuelve a pasar, conviene que la clienta anote qué estaba haciendo
justo antes (qué solapa, si acababa de minimizar/restaurar, cuánto
tiempo llevaba el sistema abierto) para poder acotarlo en una próxima
vuelta.

### Reservas aisladas: bug real — dos aisladas superpuestas del MISMO profesional no bloqueaban

Bug real reportado por la clienta: "Tenía una reserva de una
profesional cargada para el 26-11 de 10 a 11hs. Quise agregar al mismo
profesional la reserva para ese mismo día en el mismo consultorio de 9
a 11hs sin recordar que tenía cargada una reserva para ese momento de
una hora. Me salió el cartel de aviso, pero me creó igual la reserva,
manteniendo la otra, es decir quedó una de una hora y otra de dos horas
superponiéndose una hora de ellas. Me tendría que haber bloqueado la
reserva sin procesar nada."

Investigado en `verificar_conflictos_aislada` (`app/negocio/
reservas.py`): el conflicto entre dos `ReservaAislada` del mismo
consultorio/día con horario superpuesto se clasifica `bloqueante` según
`_relacion_equipo(conn, id_profesional, fila["IdProfesional"])` — y esa
función devuelve `True` ("relación de equipo", conflicto NO bloqueante,
solo aviso) tanto para "mismo profesional" como para el par E/su propio
R. La excepción "mismo profesional" tiene sentido en el OTRO loop de
esta misma función (aislada contra una `ReservaRegular` — el caso real
de "reubicación": el profesional se saca a sí mismo de su propio
horario regular ese día para tomar la aislada en otro lado), pero entre
dos aisladas ya CONFIRMADAS nunca tiene sentido dejar a un profesional
doblemente reservado consigo mismo en el mismo horario — ahí es
exactamente el bug reportado.

Se acota el fix al loop aislada-vs-aislada únicamente (no se tocó
`verificar_conflictos_regular` ni el loop aislada-vs-regular de la
misma función, que siguen con su comportamiento de siempre): `mismo_
profesional = id_profesional == fila["IdProfesional"]`; si es el mismo
profesional, `bloqueante = True` siempre, sin pasar por `_relacion_
equipo` — para profesionales DISTINTOS, `_relacion_equipo` sigue
decidiendo igual que antes (la excepción E/su cabeza R no se toca).

Tests nuevos en `tests/test_reservas.py`:
`test_reserva_aislada_choca_con_otra_aislada_del_mismo_profesional`
(reproduce el bug reportado exacto — `ConflictoBloqueanteError`, la
segunda reserva nunca se crea), `test_reserva_aislada_no_choca_con_
otra_aislada_del_mismo_profesional_sin_superponerse` (dos aisladas del
mismo profesional sin superposición real siguen coexistiendo sin
aviso), `test_reserva_aislada_choca_con_otra_aislada_de_e_y_su_cabeza_
de_equipo_sigue_siendo_aviso` (confirma que la excepción de equipo
entre profesionales DISTINTOS no se tocó). pyflakes limpio en
`reservas.py`. Suite completa de `test_reservas.py`: 77 passed.

## Panel de control: fusionar título e importe en "Estadísticas principales", sacar líneas divisorias

Pedido explícito de la clienta, tercera ronda de rediseño de este
cuadro: "En el cuadro de 'Estadísticas principales mes en curso' en las
tres secciones elimina la linea divisoria y el título de cada
subtotal. El importe quiero que aparezca dentro de cada título. Por
ejemplo, 'Liquidaciones mes en curso: $ 14.341.476,00'. El primer
título que quede 'Total liquidado mes en curso: $ 0.000.000,00'. El
segundo título que quede 'Balance del negocio: $ 0.000.000,00'. El
tercer título que quede 'Saldo a cobrar del mes en curso: $
0.000.000,00'. Los de abajo de los títulos no cambian, solo se
suprimen las lineas divisorias y los importes se reubican junto al
título."

`_armar_tarjeta_estadisticas_principales` (`app/gui/pantallas/
panel_control.py`): cada una de las tres secciones pasa a armar
PRIMERO su propia etiqueta en negrita (`self.etiqueta_total_liquidado`/
`etiqueta_balance_negocio`/`etiqueta_monto_restante_a_cobrar`, ya
existían) con el texto COMBINADO "Título: $ importe" — sin el
`_subtitulo_negrita(...)` suelto de antes ni el `_linea_divisoria()`
que separaba el subtítulo del detalle. Lo de abajo de cada título
(detalle por localidad/edificio, igual que siempre) no se tocó.
`actualizar()` arma ese texto combinado en cada refresco; la tercera
etiqueta cambia de nombre de cara al usuario ("Monto restante del mes
a cobrar" -> "Saldo a cobrar del mes en curso", pedido explícito de
este mismo mensaje) sin cambiar el atributo Python
(`etiqueta_monto_restante_a_cobrar`, para no tocar el resto del código
que ya lo usaba). `_subtitulo_negrita` (la función que armaba el
subtítulo suelto) se elimina del archivo — confirmado sin otro uso.

Tests en `tests/test_gui_panel_control.py`:
`test_tarjeta_estadisticas_principales_muestra_las_lineas_de_las_tres_
secciones` actualizado al nuevo texto "Saldo a cobrar del mes en
curso:". `test_tarjeta_estadisticas_principales_tres_subtitulos_en_
negrita_y_en_orden` renombrado a `...tres_titulos_combinados_en_
negrita_y_en_orden`, ahora chequea que las tres etiquetas (título+
importe) tengan `font-weight: bold;` y que el texto antes de ":" sea
"Total liquidado mes en curso"/"Balance del negocio"/"Saldo a cobrar
del mes en curso" en ese orden. `test_tarjeta_estadisticas_principales_
orden_de_las_tres_secciones` se invierte (ahora el título va ANTES del
detalle, no después). pyflakes limpio en `panel_control.py`. Suite
conjunta de `test_gui_panel_control.py`/`test_panel_control.py`: 105
passed.

## Redefinición completa de "Saldo actual"/"Saldo anterior" (caso testigo Vanesa Moreno)

Pedido inicial de la clienta, con una base real adjunta para
investigar (`espacio_ramos.db`):

> "Tengo a la profesional R4 Vanesa Moreno, en noviembre tenía
> liquidados $130.811, y abono $131.000, por ende les sobran $189 para
> descontar en la próxima liquidación. Me meto en la ficha de ella y
> veo que dice 'Saldo de cuenta actual' $0 y 'Saldo cuenta anterior'
> -$189. Si bien el saldo total es correcto, -$189, no tendría que ser
> al reves lo de los saldos..?"

Investigado contra una copia de la base real (forense con SQL directo
sobre `HistorialPagos`/`Profesional`, IdProfesional=4): el -$189 de
"Saldo cuenta anterior" NO era el saldo anterior real — era el
resultado de `reconciliar_saldos_cruzados` (mecanismo de una ronda
previa, pensado para corregir un bug YA resuelto de la cascada de
pagos) fusionando, en un arranque anterior, un Anterior real de -$396
con un Actual real de $207 en un solo campo (`IdPago 87`, ajuste
sintético: "saldo período anterior -396.00 -> -189.00, saldo período
actual 207.00 -> 0.00"). El combinado de los dos campos (-$189) siempre
fue correcto — el problema era que la fusión destruía la separación
entre "lo que se arrastra de antes" y "lo que pasó este período",
dejando los dos campos leíbles por separado con un significado que ya
no correspondía a ninguna realidad.

Primera ronda de preguntas a la clienta (con `AskUserQuestion`,
alcance/opciones) no fue respondida con una opción — la clienta
redefinió el modelo completo por su cuenta, en dos mensajes:

> "La verdad esto de manejar o ver tres saldos me confunde mucho, me
> gustaría ver dos saldos nada mas.
>
> Saldo anterior = lo que quedó del mes anterior, se puede modificar
> desde el período actual si se hace un proceso que afecte al período
> anterior u horas aisladas
>
> Saldo actual = Saldo anterior + importe liquidado mes en curso (con
> todo lo que se vaya agregando a la imputación de este período
> actual) - pagos imputados al mes en curso
>
> El saldo actual es el resultado en vivo de como está la cuenta del
> profesional para mi."

Y, sobre el alcance de pantallas afectadas (segunda pregunta): el
campo "Saldo cuenta actual" de Profesionales edita el COMBINADO ya
armado (no el bucket crudo por separado), y los mensajes de WhatsApp
quedan "igual que ahora" (se profundiza más abajo qué significa eso
mensaje por mensaje). Mientras se estaba implementando llegó un
mensaje nuevo con seis puntos más, tratados como la especificación más
actual y autoritativa:

> "1) En solapa 'Registrar pagos' quiero que estas tres columnas se
> comporten asi: 'Monto': es el valor del pago o del movimiento que
> está haciendo. 'Saldo previo': es el saldo actual de la cuenta antes
> de ese pago. 'Nuevo saldo': Es el saldo actual de la cuenta con ese
> pago o movimiento contemplado.
>
> 2) Misma lógica que el punto 1). Reacomodame las columnas de paso,
> que 'Saldo previo' y 'Nuevo saldo' estén a continuación de 'Monto'
>
> 3) Eliminá la etiqueta informativa 'Saldo total', ese monto queda en
> lo que dice 'Saldo actual'. Dejá los campos hablitados para hacer
> ajustes manuales si es necesario, si lo quiero hacer que salga una
> alarta informando que eso puede afectar a la liquidación del
> profesional, y si le doy ok que cambie lo que tenga que cambiar.
>
> 4) En la grilla de mensajeria, por el caso testigo de Vanesa Moreno,
> Saldo anterior tendría que decir -$396 en lugar de -$189 como dice
> ahora; el saldo actual está bien, dice -$189
>
> 5) Si, tocá lo necesario en los mensajes para que reflejen los dos
> saldos que pienso manejar, el anterior y el actual.
>
> 6) Entiendo que es correcto"

El punto 4 confirma que `reconciliar_saldos_cruzados` quedó mal y hay
que REVERTIRLA, tanto hacia adelante como para los datos ya afectados:
Vanesa Moreno es el caso testigo aceptado — después del cambio, Saldo
anterior tiene que leer -$396 (no -$189) y Saldo actual combinado tiene
que seguir en -$189 (no cambia, era el único número ya correcto).

### Núcleo: `_aplicar_pago` sin cascada, migración que revierte la reconciliación, `saldo_actual_mostrado` combinado

`Profesional.SaldoCuentaAnterior` sigue siendo exactamente lo que era:
un campo propio, "lo que quedó del mes anterior", que solo cambia por
un pago/cargo imputado a un período anterior o por `avance_mes.py` al
rotar de mes. `Profesional.SaldoCuentaActual` sigue siendo el bucket
que acredita la liquidación del mes (R) o un pago/cargo imputado al
mes en curso — pero deja de ser lo que se MUESTRA como "Saldo actual"
en cualquier pantalla: ese nombre pasa a significar siempre el
COMBINADO (Anterior + ese bucket), "el resultado en vivo de cómo está
la cuenta del profesional", en toda pantalla/mensaje del sistema.

- `app/negocio/pagos.py`: `_aplicar_pago_con_cascada` se renombra
  `_aplicar_pago` y pierde toda la lógica de redistribución — aplica
  `monto` a UN SOLO campo (el que decide `_campo_saldo` según
  `periodo_imputado`, sin cambios) y devuelve `(impacto_anterior,
  impacto_actual)` con uno de los dos siempre en 0.0. Ya no hace falta
  la cascada: un crédito en el campo imputado que cubre de más ya se ve
  reflejado en el combinado sin tener que mezclar los dos campos
  guardados — mezclarlos, al revés, es justo el bug que motivó esta
  ronda. `registrar_pago`/`modificar_pago` pasan a llamar
  `_aplicar_pago`; el "Saldo antes/después del pago" (`SaldoAnterior`/
  `SaldoNuevo` de `HistorialPagos`) sigue siendo el combinado de los
  dos campos (eso no cambió, ya era así de una ronda anterior) y sigue
  cambiando en exactamente `monto` sin importar a qué campo se aplicó.
  La función `reconciliar_saldos_cruzados` se ELIMINA del archivo
  (ya no hace falta generar ningún ajuste sintético nuevo).
- `app/db/init_db.py`: se saca el `import`/llamada a
  `reconciliar_saldos_cruzados` (corría una vez por arranque).
- `app/db/migraciones.py`: `_revertir_correccion_saldos_cruzados`
  (nueva, llamada al final de `aplicar_migraciones`) busca en
  `HistorialPagos` cualquier fila `EsAjuste=1` con `Observacion` que
  arranque "Corrección automática de saldos cruzados" (la firma exacta
  que dejaba `reconciliar_saldos_cruzados`), le aplica a `Profesional`
  el delta OPUESTO al que guardó en `ImpactoSaldoAnterior`/
  `ImpactoSaldoActual` y borra la fila (era un movimiento sintético,
  `Monto=0`, sin plata real detrás). Corre en cada arranque — para una
  base ya revertida, no vuelve a encontrar ninguna fila y no hace nada
  (idempotente). Verificado contra una copia fresca de la base real
  adjuntada: antes de revertir, Vanesa Moreno (IdProfesional 4) tenía
  Anterior=-189/Actual=0 con el ajuste sintético en `HistorialPagos`;
  después de `init_database` (que aplica la migración), Anterior=-396/
  Actual=207, el ajuste sintético desaparece, y
  `saldo_actual_mostrado(conn, fila)` da -189 — EXACTAMENTE el caso
  testigo que pidió confirmar la clienta.
- `app/gui/widgets/resumen_saldo.py`: `saldo_actual_mostrado` pasa a
  devolver `SaldoCuentaAnterior + bucket` para TODAS las categorías
  (antes devolvía el bucket solo, con el caso especial de A ya
  resuelto en una ronda anterior). `partes_resumen`/`texto_resumen`
  (Cargos especiales, y cualquier otra pantalla que los use) ya
  llamaban a este helper para "Saldo actual" — quedan corregidos
  de rebote, sin tocarlos.

### Registrar pagos: "Saldo previo"/"Nuevo saldo" ya combinados, sin "Saldo total"

El formulario de carga (`_actualizar_saldos`, `app/gui/pantallas/
pagos.py`) pasa a mostrar solo DOS saldos (pedido explícito de la
clienta): "Saldo anterior" (campo crudo) y "Saldo actual" (combinado,
vía `saldo_actual_mostrado`) — se saca la etiqueta "Saldo total" de una
ronda anterior (quedaba redundante, ya lo muestra "Saldo actual") y
"Nuevo saldo" se calcula sumándole el monto cargado directamente a
"Saldo actual", sin ningún total intermedio. El orden/ancho de columnas
de la tabla de movimientos ("Saldo previo"/"Nuevo saldo" justo después
de "Monto") ya estaba resuelto de una ronda anterior (#79/#82) — nada
que tocar ahí, y esas dos columnas YA guardaban el combinado (ver
`registrar_pago`), así que ya cumplían el punto 1 del pedido sin
cambiar nada.

### Estado de cuenta (Liquidación mensual): agrega "Saldo anterior" al lado de "Saldo actual"

`_PanelEstadoCuentaLiquidaciones` (`app/gui/pantallas/liquidacion.py`)
mostraba solo "Saldo actual" (el bucket crudo, sin "Saldo anterior") —
se agrega un segundo campo de solo lectura "Saldo anterior" (campo
crudo) al lado, y "Saldo actual" pasa a leer el combinado vía
`saldo_actual_mostrado` en vez de `SaldoCuentaActual` directo.

### Profesionales: "Saldo cuenta actual" edita el combinado, alerta antes de un ajuste manual

Pedido explícito de la clienta: el campo "Saldo cuenta actual" del
diálogo Nuevo/Editar pasa a MOSTRAR/EDITAR el combinado (no el bucket
crudo) — se saca la fila de solo lectura "Saldo total" de una ronda
anterior (#75, ya redundante). `_al_abrir_dialogo` (`app/gui/pantallas/
profesionales.py`) reemplaza, apenas se abre el diálogo, el valor
precargado del campo (el bucket crudo, cargado por el mecanismo
genérico de `crud_generico.Campo`) por `bucket + anterior`.
`_al_guardar_profesional` hace la cuenta inversa antes de guardar
(`nuevo_bucket = combinado_ingresado - anterior_ingresado`) para volver
a persistir el bucket real en `SaldoCuentaActual` — "Saldo cuenta
anterior" nunca cambió de significado, sigue siendo el campo crudo.

Si el bucket resultante o el anterior cambiaron respecto a lo que el
profesional ya tenía guardado (un ajuste manual real, no solo abrir y
cerrar el diálogo sin tocar nada), se pregunta con un `QMessageBox.
question` si confirma el ajuste ("esto puede afectar su liquidación") —
al rechazar, no se guarda nada (`al_guardar` devuelve `None`, mismo
mecanismo que ya usan los dos guardarraíles de categoría de esta
misma función); al confirmar, se guarda el valor nuevo normalmente.
Solo se pregunta al EDITAR un profesional ya existente (`registro is
not None`) — un alta nueva no tiene ninguna liquidación que pueda verse
afectada.

### Centro de mensajería / Mensajes al profesional: mismo combinado en todos lados

`_PanelCentroMensajeria.actualizar()` (`app/gui/pantallas/
mensajeria.py`) ya calculaba "Saldo actual" a mano con la fórmula
correcta (`saldo_anterior + bucket` para R, `saldo_actual_aislada` para
A) — se simplifica para llamar al mismo `saldo_actual_mostrado`
compartido en vez de duplicar la cuenta (sin cambio de comportamiento,
solo DRY). `mensaje_recordatorio_fin_de_mes` (`app/negocio/
mensajes.py`, "ESTADO DE CUENTA ACTUAL") leía `SaldoCuentaActual` solo
— pasa a sumarle `SaldoCuentaAnterior` (esta función ya está acotada a
categoría R vía `_profesional_r`, así que no hace falta el caso
especial de A ni importar nada de `app.gui` desde la capa de negocio).
`mensaje_situacion_1`/`_3`/`_5` y `mensaje_recordatorio_deuda_
profesional_x` (que usan `SaldoCuentaAnterior` solo, para recordatorios
de deuda VIEJA) se confirman sin cambios — son, por diseño, el otro
saldo que la clienta pidió seguir viendo por separado.

### Tests y verificación

`tests/test_pagos.py`: la sección de cascada se reemplaza por una de
"un solo campo por pago (sin cascada)" — mismos escenarios reales
(pago que cubre de más el período imputado, que cae corto, cargo
positivo con el otro campo en crédito, eliminar/modificar) pero
confirmando que el OTRO campo nunca se toca. La sección completa de
`reconciliar_saldos_cruzados` (7 tests) se elimina. `tests/test_
migraciones.py` (+3): revierte un ajuste sintético ya generado
(reproduce el caso Vanesa Moreno con sus montos reales), idempotente
en la segunda vuelta, no toca un ajuste manual cualquiera que no tenga
la `Observacion` exacta de la reconciliación retirada. `tests/test_gui_
widget_resumen_saldo.py` (+2): `saldo_actual_mostrado` combina para R
y para A (con la aislada en vivo). `tests/test_gui_pagos.py`: los tres
tests de "Saldo período anterior/actual" pasan a "Saldo anterior/
actual" sin "Saldo total"; el test de Eliminar con impacto repartido
entre los dos campos se adapta a simular una fila VIEJA (anterior a
este cambio, con el impacto ya repartido a mano) en vez de reproducirla
con un pago nuevo (que ya no puede repartirse). `tests/test_gui_
novedades.py`/`tests/test_gui_liquidacion.py`: ajustados los valores
esperados de "Saldo actual" al combinado. `tests/test_profesionales.py`
(+6): el diálogo muestra el combinado sin "Saldo total", un alta nueva
arranca en $0, `_al_guardar_profesional` vuelve al bucket real sin
preguntar nada si no hay cambio real, pregunta y cancela si se
rechaza, pregunta y guarda bien si se confirma, también pregunta si
solo cambia el anterior. `tests/test_mensajes.py` (+1): el recordatorio
de fin de mes combina anterior y actual.

Suite completa tras esta ronda: pyflakes limpio en los nueve archivos
de `app/` tocados (`app/db/init_db.py`, `app/db/migraciones.py`,
`app/gui/pantallas/liquidacion.py`, `app/gui/pantallas/mensajeria.py`,
`app/gui/pantallas/pagos.py`, `app/gui/pantallas/profesionales.py`,
`app/gui/widgets/resumen_saldo.py`, `app/negocio/mensajes.py`,
`app/negocio/pagos.py`) y los nueve de test tocados.

## Saldo actual de categoría A: el diálogo de Profesionales y el historial de pagos no usaban el cálculo en vivo

Bug real reportado por la clienta, ronda siguiente a la redefinición de
saldos de más arriba (caso testigo A19 Marcela La Regina):

> "A19- Marcela La Regina : Figura en profesionales $147.686 como
> saldo actual; en la grilla de mensajería $163.540. De los dos
> valores el correcto es el último. En la tabla de pagos también
> tendría que actualizar la información, pero ante todo repasame la
> lógica por favor."

Investigado antes de tocar nada: para categoría A nada acredita nunca
el bucket crudo `Profesional.SaldoCuentaActual` (no hay liquidación
mensual propia) — por eso ese número se calcula EN VIVO
(`movimiento_periodo_aislada`: reservas aisladas + llaves + ítems
libres − pagos del período). `saldo_actual_mostrado` (la función
compartida que ya usan Centro de mensajería/Pagos/Estado de cuenta/
Cargos especiales) ya resolvía esto bien desde la ronda anterior. Pero
quedaron DOS lugares con la fórmula vieja (suma cruda de los dos
campos persistidos, sin el caso especial de A):

1. El diálogo Nuevo/Editar de Profesionales (`_al_abrir_dialogo`,
   sumado en la ronda anterior) calculaba el combinado a mostrar/editar
   leyendo los dos campos de texto ya precargados, en vez de llamar a
   `saldo_actual_mostrado` — para un R da lo mismo (el bucket crudo YA
   es el valor real), para un A da el bucket crudo obsoleto (normalmente
   $0 o un valor viejo) en vez del cálculo en vivo.
2. `registrar_pago`/`modificar_pago` (`app/negocio/pagos.py`) calculaban
   el snapshot "Saldo antes del pago"/"Saldo después del pago" que
   queda guardado en `HistorialPagos` con la misma suma cruda —
   cualquier pago histórico de un profesional A tiene esos dos valores
   mal, el pedido de "en la tabla de pagos también tendría que
   actualizar la información".

### `saldo_actual_mostrado` se muda a la capa de negocio

La función vivía en `app/gui/widgets/resumen_saldo.py` (un módulo de
GUI) a pesar de ser lógica de negocio pura, sin ningún uso de Qt —
quedó mal ubicada ahí desde que se creó. `app/negocio/pagos.py`
necesita poder llamarla (para el fix de `registrar_pago`/
`modificar_pago`) y esa capa de negocio no puede depender de la GUI, así
que se mudó la función a `app/negocio/pagos.py` (justo debajo de
`_aplicar_pago`, con el mismo docstring) — `app/gui/widgets/
resumen_saldo.py` la reexporta (`from app.negocio.pagos import
saldo_actual_mostrado`) para no tener que tocar ningún llamador de
pantallas (Centro de mensajería, Estado de cuenta de Liquidación
mensual, Registrar pagos, Cargos especiales ya la importaban desde ahí).

### `registrar_pago`/`modificar_pago`: `saldo_previo`/`nuevo_saldo` sin re-consultar el cálculo en vivo

Sustituir la suma cruda por `saldo_actual_mostrado(conn, profesional)`
en el punto donde ya se calculaba `saldo_previo` resuelve el caso de
`registrar_pago` directo — pero NO alcanza con volver a llamar a
`saldo_actual_mostrado` después de aplicar el pago para obtener
`nuevo_saldo`: para un A, `movimiento_periodo_aislada` suma los pagos
ya imputados a ese período consultando `HistorialPagos` directo, y el
pago que se está registrando/modificando todavía no está insertado (o
todavía tiene su Monto VIEJO) en ese momento — una segunda consulta
daría un valor viejo, no el real. Se usa en cambio la identidad
matemática ya confirmada por los tests existentes ("el combinado
cambia en exactamente el monto del pago, sin importar a qué campo se
aplique"): `nuevo_saldo = saldo_previo + monto` directo, sin volver a
calcular nada — funciona igual para todas las categorías y de paso
elimina una consulta redundante a `Profesional` que ya no hacía falta.

En `modificar_pago` hace falta un paso extra: revertir el impacto en
los campos crudos (ya existía) NO alcanza para que "Saldo antes de
este pago" excluya la versión VIEJA del pago que se está modificando,
porque para un A esa fila SIGUE en `HistorialPagos` con su Monto viejo
hasta el `repo.actualizar` final de la función — el cálculo en vivo la
sigue contando. Se la pone en `Monto=0` momentáneamente antes de
calcular `saldo_previo` (el `repo.actualizar` final la deja con el
Monto real de todas formas, así que no hace falta revertir este paso
aparte). Sin este paso, "Saldo antes de este pago" de un A quedaría
contando la versión vieja del propio pago que se está corrigiendo.

### Profesionales: mismo fix en el diálogo, con un cuidado extra al comparar para la alerta de ajuste manual

`_al_abrir_dialogo` pasa a llamar `saldo_actual_mostrado(conn, dialogo.
registro)` en vez de sumar a mano los dos campos de texto ya
precargados — `_DialogoRegistro` (`app/gui/crud_generico.py`) suma el
atributo `self.registro` (el registro con el que se abrió, `None` en
un alta nueva) para que `al_abrir_dialogo` pueda acceder al registro
completo, no solo a los campos propios del diálogo.

`_al_guardar_profesional` también necesitaba un ajuste, no solo
cambiar qué función llama: la comparación "¿hubo un ajuste manual
real?" (para decidir si preguntar y si hay que pisar el bucket crudo)
NO puede hacerse comparando el bucket DERIVADO (combinado ingresado
menos anterior) contra el bucket crudo ya guardado — para un A esos dos
números son casi siempre distintos aunque no se haya tocado nada
(el bucket crudo guardado no significa nada para un A, el real es el
cálculo en vivo), lo que disparaba la alerta en falso y pisaba el
bucket crudo con el valor en vivo con solo abrir y guardar el diálogo
sin cambiar nada. La comparación correcta es "combinado que se mostró
al abrir vs. combinado que quedó al guardar" (recalculando
`saldo_actual_mostrado(conn, registro)` fresco adentro de
`_al_guardar_profesional`, no reutilizando nada del diálogo) — si no
cambió, se conserva el bucket crudo tal cual estaba, sin pisarlo.

Tests nuevos: `tests/test_pagos.py` (+2:
`test_registrar_pago_de_un_a_usa_el_calculo_en_vivo_no_el_bucket_
crudo`, `test_modificar_pago_de_un_a_usa_el_calculo_en_vivo_no_el_
bucket_crudo` — reproducen el caso real con los montos de Marcela La
Regina). `tests/test_profesionales.py` (+2:
`test_dialogo_saldo_actual_de_un_a_muestra_el_calculo_en_vivo_no_el_
bucket_crudo`, `test_al_guardar_un_a_sin_tocar_nada_no_pregunta_ni_
pisa_el_bucket_crudo`). pyflakes limpio en `app/negocio/pagos.py`,
`app/gui/widgets/resumen_saldo.py`, `app/gui/pantallas/profesionales.py`,
`app/gui/crud_generico.py` y los dos archivos de test tocados.

## Centro de mensajería: bordó primero en el orden, sin condición de reserva regular activa, y reenvío manual sin perder el tipo de mensaje

Tres pedidos de la clienta sobre el mismo color, entregados en tres
mensajes consecutivos que hay que leer en conjunto (los últimos
corrigen/afinan a los primeros):

> 1. "Solapa 'Centro de mensajería' * Los profesionales que se ponen en
>    bordó, el recordatorio cercano a fin de mes, que se pongan arriba
>    de todo, luego al cliquear el check que se bajen a gris"
> 2. "Perdón, no al tocar el check, sino al generar el mensaje que se
>    bajen a gris, no a verde" (corrección al punto 1: el disparador no
>    es el check de "Enviada", es el botón "Generar texto")
> 3. "Y también veo profesionales categoría R que estaban en gris y no
>    en bordó, la idea es que se active el recordatorio en bordó para
>    todos los profesionales de esa categoría."
> 4. (misma ronda) "Y una vez que se genera el texto, cuando pasa de
>    bordó a gris, que sea el mensaje en bordó (actualizado con los
>    nuevos saldos si hace falta) que se vuelva a generar, no el
>    mensaje de gris. Si esto genera algún conflicto, el tipo de mensaje
>    digo, que siga en bordó, pero que el profesional que se pincha en
>    generar mensaje que baje en la tabla y quede luego de los azules
>    de las horas aisladas." (la clienta ofrece una alternativa de
>    respaldo — reordenar en vez de cambiar el mensaje — solo por si la
>    primera generaba algún problema; no hizo falta, ver abajo)

### Orden: bordó primero de todos (punto 1)

`_ORDEN_COLOR` (`app/gui/pantallas/mensajeria.py`) pasa "bordo" al
primer lugar de la tupla (antes estaba sobre el final, cerca de
marrón/gris) — el recordatorio de fin de mes es urgente y tiene que
verse antes que cualquier otro color.

### Investigado antes de tocar nada: el botón "Generar texto" ya bajaba a gris correctamente (punto 2)

El punto 2 corrige una primera implementación de este mismo pedido:
arranqué asumiendo que el disparador era el check "Enviada" (como
decía el mensaje original) y armé un caso especial ahí — la clienta
interrumpió para aclarar que el disparador real es el botón "Generar
texto", no el check. Se revirtió ese caso especial antes de que
llegara a tocar ningún test ni a comitearse.

Investigado con un script offscreen que clickea el botón real
"Generar texto" de un profesional bordó: ya bajaba a gris
correctamente, sin ningún cambio de código (`_texto_para_boton`, rama
`bordo`, ya llamaba a `marcar_recordatorio_mensajeria_generado` tras
armar el mensaje). Confirmado además por prueba estructural: en
`color_profesional`, una vez que `EstadoEnvio == "Enviada"` para R, la
función devuelve bordó o gris DENTRO de ese mismo bloque — nunca puede
caer al chequeo de "verde" más abajo, así que un salto a verde desde
bordó (lo que la clienta decía NO querer) era estructuralmente
imposible con este código. No hacía falta tocar nada acá — el bug real
que la clienta estaba viendo era el del punto 3.

### Bordó para CUALQUIER profesional R, sin mirar reserva regular (punto 3, el fix real)

`_debe_recordar_fin_de_mes` (`app/negocio/mensajeria.py`) tenía, desde
la ronda en que se armó por primera vez, una condición extra adentro:
solo pasaba a bordó un profesional con una `ReservaRegular` vigente a
la fecha de hoy (`_reserva_regular_activa`, duplicado del helper
mismo-nombre de `panel_control.py`, sin relación entre los dos
módulos). Esa condición nunca fue pedida para el caso general — era un
criterio razonable de la primera vuelta de este pedido, que la clienta
ahora pide sacar explícitamente: "la idea es que se active el
recordatorio en bordó para todos los profesionales de esa categoría".
Se elimina la condición y, de paso, la función `_reserva_regular_
activa` completa de este módulo (sin otro uso). El resto de las
condiciones de bordó no cambia: liquidación ya Enviada, dentro de
`DiasAntesFinMesRecordatorioGeneral` días de fin de mes, recordatorio
no generado todavía este período.

### Reenvío manual desde un gris que ya fue bordó: mismo mensaje, saldos vigentes (punto 4)

Al generar el texto de un bordó, el profesional pasa a gris para el
resto del período (mecanismo sin cambios, ver arriba) — pero un gris
que YA pasó por bordó sigue siendo distinto de un gris que nunca pasó
por bordó: antes de este pedido, un segundo click en "Generar texto"
sobre ESE MISMO profesional (ya en gris) generaba el mensaje de envío
de liquidación (el que usa el resto de los grises/verdes/amarillos/
violetas), perdiendo el mensaje de recordatorio. La clienta pidió que
un reenvío manual siga generando el mensaje de recordatorio de fin de
mes, actualizado con los saldos que tenga el profesional en ese
momento (no el que tenía la primera vez).

`recordatorio_mensajeria_ya_generado(conn, id_profesional, periodo)`,
nueva en `app/negocio/mensajeria.py`: lee `EstadoMensajeriaPeriodo.
RecordatorioMensajeriaGenerado` para ese profesional/período — `True`
si y solo si ya pasó por bordó alguna vez en este período (el caso
que importa acá, el que sigue en gris por eso). `_texto_para_boton`
(`app/gui/pantallas/mensajeria.py`) suma, antes de la rama genérica de
grises, un caso para `color == "gris" and recordatorio_mensajeria_ya_
generado(...)`: en ese caso devuelve `mensaje_recordatorio_fin_de_mes`
de nuevo (la misma función que usa bordó — ya lee los saldos en vivo,
no hace falta nada especial para que refleje el saldo vigente al
momento del reenvío) en vez de `mensaje_envio_liquidacion`. Un gris
que NUNCA pasó por bordó (lejos de fin de mes, o directamente nunca
tuvo el flag) sigue yendo por la rama de siempre, sin cambios.

No hizo falta la alternativa de respaldo que ofreció la clienta
(mantener el color en bordó y solo reordenar en la tabla) — distinguir
el tipo de mensaje por el flag ya existente
(`RecordatorioMensajeriaGenerado`) resuelve el pedido sin ningún
conflicto ni tener que tocar `color_profesional`/`_ORDEN_COLOR` de
nuevo.

Tests nuevos en `tests/test_mensajeria_negocio.py`
(`test_recordatorio_mensajeria_ya_generado_distingue_gris_que_fue_
bordo`, `test_recordatorio_mensajeria_ya_generado_falso_para_un_gris_
que_nunca_fue_bordo`, `test_recordatorio_mensajeria_ya_generado_falso_
sin_ningun_estado_del_periodo`) y renombrado/invertido
`test_gris_no_pasa_a_bordo_sin_reserva_regular_activa` ->
`test_gris_pasa_a_bordo_sin_reserva_regular_activa`. En
`tests/test_gui_mensajeria.py`:
`test_generar_texto_reenvio_desde_gris_que_fue_bordo_repite_el_
mensaje_de_recordatorio` (dos clicks reales en "Generar texto" sobre
el mismo profesional, cambiando el saldo entre uno y otro, confirma
que el segundo mensaje sigue siendo el de recordatorio y refleja el
saldo nuevo).

Suite completa tras esta ronda: pyflakes limpio en todo `app/`/`tests/`.
`tests/test_mensajeria_negocio.py`/`tests/test_gui_mensajeria.py`: solo
los 3 fallos ya documentados del reloj real del sandbox cerca de fin de
mes (ver "Fallos conocidos del sandbox/contenedor" más arriba) —
confirmado con `git stash` que reproducen igual sin los cambios de esta
ronda.
