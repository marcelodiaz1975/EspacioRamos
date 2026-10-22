# Historial archivado — Profesionales

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

## Profesionales: sin cambios de código (batch #15.x del documento)

Decimoquinta tanda de `v0.11.2026.10`: "Listado de profesionales"
(`_PanelProfesionales`) ya cumple 1.4 de rebote — no tiene `showEvent`
propio, pero `self.crud_profesionales` (la `PantallaCRUD` anidada que
arma el catálogo) ya recibe su propio evento de visibilidad al mostrarse
y ya tiene `reiniciar()` desde el fix central de `crud_generico.py` —
confirmado leyendo el código, nada que agregar. "Profesiones y
tratamientos" (el otro tab de este formulario, también un catálogo
anidado) igual, cerrado desde las tandas #83/#84.

**"Listado: botones mitad alto, etiquetas, cuadro documentación 5
items, Vista previa"**: no implementado — ninguno de estos cuatro
puntos tiene ningún rastro en CLAUDE.md de tandas anteriores ni
ninguna base concreta en el código actual (botones "Agregar archivo"/
"Eliminar archivo" al alto default, sin ningún pedido de "mitad alto"
documentado; `lista_documentos` sin ningún criterio de "N items
visibles"; ninguna vista previa de documentos en esta pantalla, a
diferencia de Gestor de archivos). Sin el texto original del punto a
la vista, y sin saber qué formato de archivo debería previsualizar una
"Vista previa" acá, no hay una base segura para inventar el detalle —
mismo criterio que "autocierre de tanda" (Pagos) y "reducir
proporcional" (Oferta). Queda pendiente de una aclaración puntual.

## Profesionales: validaciones de categoría (R/E/A/B/X/C)

Pedido de la clienta, antes de implementar nada: un repaso explícito de
la lógica de las seis categorías de `Profesional` ("vamos a repasar la
lógica de las categorías... así controlamos que estamos en sintonía"),
con una descripción puntual de cada una y de qué validaciones debería
haber. Se investigó primero contra el código real (no contra memoria ni
contra lo documentado en otras rondas) qué de eso ya estaba cubierto y
qué no, y se le devolvió un repaso punto por punto antes de tocar nada
— varios huecos reales, no solo percepciones:

- **R**: el combo de "Reservas regulares" ya excluía A/X/C (solo R/B/E),
  pero de forma silenciosa — sin ningún alerta ni sugerencia de código,
  y SIN ninguna validación a nivel de negocio (`crear_reserva_regular`
  no chequeaba la categoría en absoluto).
- **E**: la consolidación económica en el cabeza de equipo (`id_
  profesional_liquidable`) ya funcionaba bien, pero nada impedía
  reservarle horas a un E sin `ProfesionalCabezaEquipo` cargado, o con
  un cabeza que no fuera categoría R — quedaba "huérfano" (nunca se
  liquida) sin que nadie se entere. Tampoco había ningún bloqueo al
  cambiar la categoría del R cabeza de equipo mientras todavía tuviera
  E vinculados.
- **A/X/C**: mismo patrón que R — exclusión silenciosa de los combos
  de Reservas, sin alerta ni sugerencia de código.
- **C**: hueco real — "no se puede hacer ningún otro movimiento con
  ellos" no se cumplía: el combo de profesional de Llaves (asignar),
  Cargos especiales (crear) y Pagos (Registrar pagos) incluía C sin
  ningún descarte.
- **Cambios de categoría**: el renombre de carpeta ya existía
  (`aplicar_cambio_codigo`), pero solo se disparaba si el CÓDIGO
  cambiaba — y el código nunca cambiaba solo por cambiar la categoría,
  el operador tenía que tipearlo a mano.

Sobre esos huecos, la clienta confirmó tres decisiones puntuales antes
de implementar:

- **E, "liberar sus horarios" es consecuencia de pasarlos a X**: el
  guardarraíl que bloquea cambiarle la categoría a un R con equipo solo
  chequea si tiene E vinculados (`ProfesionalCabezaEquipo` apuntando a
  él) — no hace falta ADEMÁS verificar que esos E no tengan reservas
  activas como condición aparte.
- **X, la sugerencia de código depende del tipo de horario intentado**:
  regular sugiere R, aislado sugiere A (no siempre R).
- **Código automático y de solo lectura**: cualquier cambio de
  categoría pasa a asignar, solo, el código más bajo disponible de la
  categoría nueva — el campo deja de ser editable a mano.
- **Alertas vs. validación silenciosa**: "en parte tenés razón, se
  cumple el objetivo con la validación silenciosa (no ofrecer la
  categoría donde no corresponde) — donde eso alcance, suprimí el
  alerta; donde consideres que suma, implementala." Esto definió qué
  de la lista se resolvió con un alerta activa (los dos guardarraíles
  de Profesionales, que SÍ necesitan un bloqueo real porque no hay
  ningún combo que los prevenga solos) y qué quedó cubierto de sobra
  con la exclusión silenciosa ya existente (A/X/C fuera de los combos
  de Reservas, sin sumar ningún cartel nuevo ahí).

### Código automático, de solo lectura, siempre el más bajo disponible

`sugerir_codigo` (`app.negocio.profesionales`) pasa de "sugerencia
editable antes de confirmar" a ser lo que determina el código real —
se extrae el cálculo a `_numeros_usados` y se suma
`sugerir_codigos_multiples(conn, categoria, cantidad)`: varios códigos
de la misma categoría EN UNA SOLA PASADA, simulando que cada uno ya se
ocupó antes de buscar el siguiente — necesario para el alerta de abajo
(un `sugerir_codigo` llamado una vez por cada profesional a
reclasificar devolvería el MISMO número a todos, porque ninguno está
guardado todavía).

`app.gui.pantallas.profesionales._al_abrir_dialogo`: `campo_codigo.
setReadOnly(True)` siempre. `categoria_original`/`codigo_original` (el
valor con el que se abrió el diálogo — vacío para un alta nueva, el
código real para una edición) son el ancla de `_actualizar_codigo`:
mientras la Categoría se quede en la que ya tenía, conserva el código
real tal cual estaba; en cuanto cambia a cualquier otra, sugiere el más
bajo libre de esa categoría nueva; si se vuelve a la categoría
original, restaura el código real de antes (no se pierde por haber
tanteado otra categoría en el camino). Esto simplificó de punta a punta
el seguimiento de "último sugerido" que tenía la versión anterior (ya
no hace falta: nadie puede tipear encima).

Como el código ahora SIEMPRE sigue a la categoría, `aplicar_cambio_
codigo` (ya existente, dispara el renombre de carpeta + registra
`HistorialCodigo`) pasa a disparar también de rebote en cualquier
cambio de categoría real, sin que el operador tenga que tocar el
código a mano — no hizo falta ningún cambio en esa función, el gatillo
(`IdCodigo` distinto en `valores_nuevos`) ya lo cubre solo.

### Dos guardarraíles nuevos en Profesionales (`al_guardar`, antes de guardar)

`PantallaCRUD` ya tenía un hook `al_guardar(valores, registro_o_None)`
(usado hasta ahora solo por Fechas especiales, para el aviso de
regeneración de liquidaciones) — corre ANTES de `repositorio.crear`/
`actualizar`, y devolver `None` cancela el guardado sin tocar la base.
`_al_guardar_profesional` (nuevo, `app.gui.pantallas.profesionales`)
suma los dos guardarraíles de esta ronda, los dos con un `QMessageBox.
warning` explicando por qué y devolviendo `None`:

- **E sin Cabeza de equipo válido**: si `CategoriaProfesional == "E"`,
  exige `ProfesionalCabezaEquipo` cargado Y que ese cabeza sea
  categoría R — sin esto, nunca se guarda un E "huérfano".
- **R con equipo E vinculado, cambio de categoría bloqueado**: si el
  `registro` que se está editando YA era categoría R y la categoría
  nueva es otra, busca profesionales con `ProfesionalCabezaEquipo`
  apuntando a él Y categoría E — si hay alguno, bloquea con un alerta
  que lista cada uno con el código X que le tocaría
  (`sugerir_codigos_multiples`, nunca el mismo número repetido). El
  mensaje dirige a desvincularlos (pasarlos a X, o asignarles otro
  cabeza) antes de poder cambiar este profesional.

Conectado vía `al_guardar=lambda valores, registro: _al_guardar_
profesional(valores, registro, conn)` en el `PantallaCRUD` de
`_PanelProfesionales` — cerrado sobre `conn` (variable local de
`_armar_ui`), NO sobre `self`, mismo criterio que otros cierres de este
proyecto para no armar un ciclo entre el panel y su propio `PantallaCRUD`
(a diferencia de `al_actualizar`/`al_crear`, que sí se envuelven en
referencia débil por este mismo motivo, `al_guardar` no lo hace — se
evita el ciclo desde el lado del cierre en vez de tocar el mecanismo
compartido).

### Guardarraíl de categoría en `crear_reserva_regular`/`crear_reserva_aislada` (defensa en profundidad)

Los combos de Reservas ya excluían las categorías que no corresponden,
pero eso es pura UI — nada a nivel de negocio impedía que otro camino
(una importación, un uso directo de la función, un bug de combo)
reservara horas a cualquier categoría. `_validar_categoria_reserva`
(nueva, `app.negocio.reservas`), compartida por las dos funciones:

- Si la categoría es E, exige Cabeza de equipo cargado y categoría R
  (mismo criterio exacto que `_al_guardar_profesional`) — nunca se
  acepta un E huérfano, ni siquiera por esta vía.
- Si no, exige que la categoría esté en `categorias_permitidas` (`("R",
  "B")` para regulares, `("A", "B", "R")` para la aislada COMÚN — la
  extraordinaria sigue con su propia validación de siempre, A/B/R/E,
  sin pasar por acá) — si no, levanta `ValueError` con el código
  sugerido de la categoría que correspondería (`sugerir_codigo`).

`crear_reserva_regular` la llama primero que nada (antes de la
validación de período cerrado); `crear_reserva_aislada` la llama solo
en la rama `else` de `es_extraordinaria` (la extraordinaria nunca pasa
por acá, tiene su propia lista cerrada A/B/R/E).

### Categoría C excluida de los combos de acción (Llaves, Cargos especiales, Pagos)

"No se puede hacer ningún otro movimiento con ellos" — se agrega una
constante nueva por pantalla (duplicada, mismo criterio que el resto
del proyecto: pantallas sin relación entre sí) que excluye C de
`_CATEGORIAS_TODAS`, usada SOLO en los combos que CREAN un movimiento
nuevo, no en los que solo filtran/visualizan uno ya existente:

- `pagos.py`: `_CATEGORIAS_CON_PAGOS` en "Registrar pagos" (`_CATEGORIAS_
  TODAS` queda sin otro uso en este archivo, se borra). "Estado de
  cuenta" sigue sin filtrar — mismo criterio ya documentado ahí, una
  vista, no una acción.
- `novedades.py`: `_CATEGORIAS_CON_CARGOS` en el combo de "Registro de
  cargos especiales" (crear uno nuevo) — Licencias/Ausencias, que
  comparten `_CATEGORIAS_TODAS` en este mismo archivo, no fueron parte
  de este pedido y se quedan igual.
- `llaves.py`: `_CATEGORIAS_CON_LLAVES` en `_DialogoAsignar` (asignar
  una llave nueva) — `combo_filtro_stock` ("Stock de llaves por
  profesional", puramente de visualización sobre tenencias YA
  existentes) se queda con `_CATEGORIAS_TODAS`, sin este descarte.

Tests nuevos: `tests/test_profesionales_negocio.py` (`sugerir_codigos_
multiples` — sin nadie cargado, no repite números, respeta huecos ya
usados, cantidad 0). `tests/test_profesionales.py` (código de solo
lectura; editar sin cambiar categoría conserva el código real; cambiar
categoría reasigna y volver a la original restaura; el viejo test de
"no pisa una edición manual" se reemplaza, ya no aplica; el de renombre
de carpeta se actualiza al código auto-asignado en vez del tipeado a
mano; los seis de `_al_guardar_profesional` — E sin cabeza, E con
cabeza que no es R, E válido, sin bloqueo fuera de estos dos casos,
bloqueo real con equipo vinculado, permite guardar el mismo R sin
cambiar categoría, sugiere códigos X distintos para cada E del
equipo). `tests/test_reservas.py` (seis en regulares — rechaza A/X/C
con código sugerido, rechaza E sin cabeza o con cabeza inválida, acepta
E válido — y cinco en aisladas — rechaza X/C, rechaza E sin cabeza,
acepta E válido, confirma que la extraordinaria no pasa por esta
validación). Suite completa corrida en 9 lotes en paralelo después de
este cambio (2576 tests, incluyendo cada pantalla que toca un combo de
profesional de cualquier categoría): sin ninguna falla.

