# Historial archivado — Reservas (regulares, aisladas, extraordinarias)

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

## Reservas regulares: checks de Días en grilla de 2 columnas

Pedido puntual de la clienta: el campo "Días" del formulario de alta
(`_PanelReservasRegulares`) pasa de una lista vertical de un check por
línea a una grilla de 2 columnas fijas — Lunes/Martes, Miércoles/Jueves,
Viernes/Sábado. Distinto del criterio de la grilla de días de Oferta de
consultorios (`math.ceil(len(dias) / 2)` columnas, mitad arriba/mitad
abajo): acá la clienta pidió específicamente 2 columnas siempre, así que
`grid_dias.addWidget(check, i // 2, i % 2)` no depende de `len(_DIAS_
RESERVA)` — si se suma Domingo a esa lista más adelante, cae solo en una
fila nueva debajo de Viernes/Sábado, sin acompañante en la segunda
columna, en vez de reacomodar todo el resto de la grilla como pasaría
con el criterio de Oferta.

Reservas aisladas no tiene ningún campo de días de la semana (usa una
fecha puntual, `campo_fecha`) — el pedido de la clienta mencionaba "los
dos formularios de reservas" pero solo Reservas regulares tiene este
campo; se aplicó únicamente ahí.

## Reservas: sin título de la grilla, tabla de abajo siempre visible

Dos pedidos puntuales de la clienta sobre las dos solapas (Reservas
regulares/aisladas), aplicados juntos porque el segundo depende del
espacio que libera el primero:

- **Sin título en el `QGroupBox` de la grilla**: "Vista previa: grilla
  operativa" se saca (`grupo_grilla = QGroupBox()`, sin texto) en las
  dos solapas — el `QGroupBox` sigue existiendo (borde propio), solo
  pierde el título.
- **La tabla de abajo ("Horarios reservados"/"Reservas aisladas") queda
  FUERA del `QScrollArea` de la grilla**, en vez de compartirlo: antes,
  `contenido` (form + grilla + tabla, todo junto) era el único widget
  del `QScrollArea` — si la grilla necesitaba mostrarse entera (su
  `QTableWidget` interno fuerza un alto mínimo igual a la suma exacta
  de sus filas, ver el hallazgo documentado en
  `test_grilla_preview_no_tiene_scroll_interno_al_elegir_profesional`:
  la grilla NUNCA debe recortarse con un scroll interno propio), esa
  altura mínima arrastraba a la tabla de abajo fuera de la vista, y
  había que scrollear TODO el panel para llegar a ella. Se resolvió
  sacando `panel_tabla` de `contenido` (que sigue siendo lo único
  adentro del `QScrollArea`, ahora con `splitter_superior` nomás) y
  agregándolo aparte, directo a `layout_externo`, con
  `setMinimumHeight(_ALTO_MINIMO_TABLA_INFERIOR)` (230px, alcanza para
  el título + encabezado + un par de filas) — la grilla arriba puede
  seguir necesitando SU PROPIO scroll para mostrarse entera sin
  recortarse (eso no cambió), pero la tabla de abajo ya no depende de
  eso: siempre tiene su franja fija visible, con su propio scroll
  interno si hay más filas de las que entran (mismo criterio que
  cualquier tabla del sistema, no distinto de antes).
- Como `panel_tabla` deja de estar dentro de `contenido` (que tiene
  `objectName="panelSolapa"`), suma su propio `panelSolapa` para no
  perder el fondo blanco de la solapa — mismo criterio ya documentado
  en "Panel izquierdo gris en vez de blanco" más arriba, aplicado acá a
  un `QGroupBox` en vez de a un panel de filtros/botones.

Test de regresión actualizado en `test_gui_reservas.py`
(`test_contenido_dentro_del_scroll_tiene_fondo_claro`, ahora espera 2
descendientes `panelSolapa` — `contenido` y `panel_tabla` — en vez de 1)
más uno nuevo que confirma el título ausente y que `panel_tabla` queda
fuera del `QScrollArea` de la grilla.

Confirmado con la clienta después de este cambio: "todos los botones y
todas las referencias de colores, luego de eso la tabla" — con
`panel_tabla` ya fuera del `QScrollArea` de arriba, scrollear ESE
`QScrollArea` (form + grilla) hasta el final muestra los tres botones
completos y las ocho referencias de colores completas, y justo después,
sin ningún scroll adicional, arranca "Horarios reservados"/"Reservas
aisladas" — verificado programáticamente llevando el scrollbar a su
`maximum()` y confirmando que todo el contenido queda visible antes de
la tabla.

## Reservas: se saca "Deshacer último movimiento"

Pedido explícito de la clienta, mismo criterio que en su momento con
Llaves ("Deshacer último movimiento" cubría cualquier alta/edición/baja
de esa pantalla, se sacó por completo a pedido explícito porque no
estaba en la lista final de botones que dio la clienta — pérdida de
funcionalidad real, no solo estética). Acá el pedido fue directo: se
borra el botón, su conexión (`clicked.connect(self._deshacer_ultimo)`)
y el método `_deshacer_ultimo` entero, en las DOS solapas (Reservas
regulares/aisladas — cada una tenía su propia implementación, ninguna
compartía estado con otro método salvo los helpers ya usados por
Modificar/Cancelar, así que no quedó código muerto de soporte). Sus 8
tests (4 por solapa: sin registros no falla, borra/cancela el alta
reciente, cancelado por el usuario no hace nada, con vigencia ya
cerrada/reserva ya cancelada avisa y no hace nada) se sacan con él.

De paso, sacar este botón fue lo que terminó de lograr el pedido
anterior ("todos los botones y las referencias de colores, luego la
tabla" — ver arriba): sin el botón de más, el contenido del panel
superior entra en el scroll disponible junto con la tabla de abajo sin
quedar nada a mitad de camino.

## Reservas: panel de Filtros de la grilla más compacto

Tres pedidos puntuales de la clienta sobre la misma zona (la "Vista
previa: grilla operativa" embebida en las dos solapas de Reservas),
todos apuntando a lo mismo: ganar espacio para que "Referencias de
colores" entre sin cortarse:

- **La columna del formulario se angosta, el panel de Filtros crece**:
  `_ANCHO_COMBO_PROFESIONAL` (ancho de `combo_profesional`, que de
  rebote define el ancho de toda esa columna al ser el único campo con
  ancho propio) pasa de 220 a 190; ese ancho liberado se lo lleva el
  panel de Filtros de `GrillaOperativaWidget` (`panel_filtros.
  setMaximumWidth`, de 260 a 290) — método nuevo `agrandar_panel_
  filtros(ancho)`.
- **"Día de la semana" de a pares**: mismo criterio que el campo "Días"
  del alta de Reservas regulares (ver más arriba) — método nuevo
  `agrupar_dias_en_pares()`, que reemplaza el `QVBoxLayout` de los
  checks ya construidos por un `QGridLayout` de 2 columnas fijas vía
  `layout.replaceWidget(viejo, nuevo)` (no hace falta re-crear los
  `QCheckBox`, solo reubicarlos).
- **"Referencias de colores" a 2 columnas, más chica**: `LeyendaColores`
  suma `hacer_compacta()` (pasa a `columnas=2`, la muestra de color de
  40×24 a 28×16, y `font-size: 10px` en sus etiquetas) y
  `GrillaOperativaWidget.mostrar_leyenda_colores` suma un parámetro
  `compacta: bool = False` que la invoca. En Reservas aisladas (6
  referencias) entra completa sin necesitar scroll; en Reservas
  regulares (8 referencias, lista más larga) sigue necesitando scroll
  para verse entera, pero bastante menos que antes.

De paso, pedido explícito de la clienta también: "subí el título
Filtros" — el título de ese panel quedaba visiblemente más abajo que
"Profesional" (la columna de al lado, sin `QGroupBox` de por medio).
Causa: `GrillaOperativaWidget._armar_ui` armaba su `QHBoxLayout`
principal SIN sacarle el margen por defecto, así que este widget sumaba
su propio margen encima del que ya le daba el contenedor de afuera
(`grupo_grilla`, el `QGroupBox` sin título que lo envuelve en Reservas).
`layout_principal.setContentsMargins(0, 0, 0, 0)` — cambio general, sin
riesgo (solo achica un margen vacío que nunca hacía falta), aplica a
los cuatro usos de esta grilla (Reservas ×2, Oferta de consultorios,
Novedades ×3, Grilla semanal). `layout_grupo_grilla.setContentsMargins(
0, 0, 0, 0)`, del lado de `reservas.py`, es la mitad Reservas-específica
del mismo ajuste.

**Los tres primeros cambios (ancho del panel, días de a pares, leyenda
compacta) son opt-in, no tocan el comportamiento por defecto**:
`GrillaOperativaWidget` es un widget compartido (Reservas ×2, Oferta de
consultorios, Novedades ×3, Grilla semanal) — cambiar `panel_filtros`/
`_leyenda_colores`/los checks de día directamente en `_armar_ui` hubiera
afectado a las seis pantallas sin que nadie lo pidiera ahí. Los tres
métodos nuevos (`agrandar_panel_filtros`/`agrupar_dias_en_pares`/
`mostrar_leyenda_colores(compacta=True)`) solo los llama Reservas; el
resto de las pantallas sigue exactamente igual que antes — confirmado
corriendo sus tests después del cambio (`test_gui_oferta.py`,
`test_gui_novedades.py`, `test_gui_pantalla_grilla_operativa.py`, sin
ninguna diferencia).

## Reservas: columna del formulario alineada, sin título Filtros, Detalle visible

Tres ajustes más de la clienta sobre la misma zona (formulario + grilla
embebida), en la misma ronda de revisión:

- **Reservas aisladas, columna del formulario del mismo ancho que la de
  Filtros**: el checkbox `casilla_reubicacion` ("Es reubicación
  (compensa una ausencia del profesional, no genera cargo)") tiene el
  texto más largo de todo el formulario, y `QCheckBox` NO ajusta su
  texto solo (a diferencia de un `QLabel` con `setWordWrap`) — sin
  wrapear, su `sizeHint` de una sola línea (468px) es lo que terminaba
  estirando toda la columna muy por encima del ancho del panel de
  Filtros de al lado (290px), aunque `_ANCHO_COMBO_PROFESIONAL` diga
  190. Se resuelve con un salto de línea a mano en el texto ("...una
  ausencia\ndel profesional..."), que Qt sí respeta para texto de
  botón/checkbox (solo no lo AGREGA solo) — bajó el `sizeHint` a 265px,
  quedando la columna pareja con la de Filtros. Reservas regulares no
  tiene este checkbox (es propio del flujo de reubicación de aisladas),
  así que no le hacía falta ningún cambio — su columna ya salía pareja
  con la de Filtros de antes.
- **Se saca el título "Filtros" y se renombran los filtros individuales**:
  `GrillaOperativaWidget` suma `renombrar_etiquetas_filtro()` ("Localidad"
  → "Filtro de localidad", "Edificio" → "Filtro de edificio", "Unidad" →
  "Filtro de unidad", "Día de la semana" → "Filtro de día de la semana";
  "Profesional" queda igual, no lo pidió) — las cuatro etiquetas pasan a
  guardarse como atributos (`_etiqueta_localidad`/etc., antes `QLabel`
  sueltos sin referencia) para poder renombrarlas después de construir
  el panel. El título del `QGroupBox` en sí se saca con
  `fijar_titulo_filtros("")` (el método ya existía, para ponerle OTRO
  nombre en Oferta — acá se lo llama con string vacío). Mismo criterio
  "opt-in" que el resto de esta sección: solo Reservas llama a estos dos
  métodos nuevos, el resto de las pantallas que usan esta grilla
  compartida siguen con "Filtros" tal cual.
- **La tabla de abajo muestra 3 filas fijas, no un mínimo aproximado**:
  `panel_tabla.setMinimumHeight(230)` (un número tanteado a ojo en la
  ronda anterior) se reemplaza por `self.tabla.setFixedHeight(
  _alto_para_filas(self.tabla, 3))` — mismo criterio EXACTO que
  `app.gui.pantallas.llaves._alto_para_filas` (duplicado acá, pantallas
  sin relación entre sí): calcula el alto justo para encabezado + 3
  filas de datos, la tabla sigue siendo scrolleable para ver el resto.
  Pedido explícito de la clienta ("que se vean 3 registros nada más").
  Al ocupar bastante menos alto que el mínimo aproximado de antes, el
  panel de arriba (formulario + grilla) queda con más alto disponible
  dentro de la ventana — lo suficiente para que "Detalle:" (el cuadro de
  texto al pie de la grilla, que antes quedaba fuera de la vista sin
  scrollear más de la cuenta) se vea junto con los botones y las
  referencias de colores, en las dos solapas, sin tener que scrollear
  nada en la mayoría de los tamaños de ventana probados.

Tests nuevos: `test_gui_grilla_operativa.py` (`fijar_titulo_filtros("")`
saca el título; `renombrar_etiquetas_filtro` deja Profesional intacto);
`test_gui_reservas.py` (título/etiquetas renombradas en las dos solapas;
`panel.tabla.height()` coincide con `_alto_para_filas(tabla, 3)`; el
checkbox de reubicación tiene un `"\n"` en su texto).

## Reservas: más filas en aisladas, sin "Horas aisladas mensuales" en
## regulares, "Detalle" parejo con la columna de al lado

Tercera vuelta sobre la misma zona (formulario + grilla embebida),
apuntando a terminar de usar el espacio que sobraba en cada solapa
después de la ronda anterior:

- **Aisladas: más filas visibles en la tabla de abajo.** La clienta
  notó, mirando la captura, que sobraba lugar debajo del cuadro
  "Detalle" y del título "% Descuento" incluso con las 3 filas fijas de
  la ronda anterior — acá la columna de la grilla (no la del
  formulario, más corta en esta solapa por no tener los campos "Días"
  ni "Vigencia" de Reservas regulares) es la que sobra en alto.
  `_FILAS_VISIBLES_TABLA_INFERIOR` se separa en dos constantes,
  `_FILAS_VISIBLES_TABLA_INFERIOR_REGULARES = 3` y
  `_FILAS_VISIBLES_TABLA_INFERIOR_AISLADAS = 5` (antes una sola,
  compartida por las dos solapas sin necesidad).
- **Regulares: se saca "Horas aisladas mensuales".** Pedido explícito de
  la clienta: en esta solapa solo importan "Horas regulares semanales"
  y "% Descuento" — la de horas aisladas se saca del todo (creación del
  `QLabel`, `form.addWidget` y las dos líneas de `.setText(...)` en
  `_actualizar_resumen_profesional`), sin tocar la versión de Reservas
  aisladas (que sigue mostrando las tres, es su propio método duplicado,
  no compartido). `hasattr(panel_regulares, "etiqueta_horas_aisladas")`
  pasa a dar `False`; en aisladas sigue dando `True`.
- **"Detalle" parejo con la columna de al lado.** Con las 3 labels
  originales, "% Descuento" quedaba fuera de la vista (había que
  scrollear ~40px para verlo) en Regulares, y la columna de la grilla
  (grid + Detalle) en Aisladas terminaba varios px más abajo que la del
  formulario — ninguna de las dos quedaba "pareja". Diagnóstico medido
  con un script de geometría (ancho/alto real, no a ojo): en Regulares
  la columna del formulario es la más alta de las dos (más campos,
  incluye "Días" y "Vigencia"); en Aisladas es al revés, la columna de
  la grilla es la más alta (por el `QTableWidget` de la grilla + el
  cuadro "Detalle"). Como `self.tabla` (la grilla, adentro de
  `GrillaOperativaWidget`) tiene `stretch=1` por defecto en su layout,
  cualquier alto de sobra que le toque a esa columna (forzada a la
  altura de la más alta de las dos, por venir de un `QSplitter`) lo
  absorbía la grilla — quedando con relleno en blanco debajo de la
  última hora en vez de dárselo a "Detalle", que se quedaba en su
  tamaño fijo de siempre (90px). Dos métodos nuevos en
  `GrillaOperativaWidget`, opt-in (no tocan el resto de los usos de esta
  grilla compartida — Oferta, Novedades, Grilla semanal):
  - `dar_stretch_a_detalle()`: le saca el `stretch` a la grilla
    (`setStretchFactor(self.tabla, 0)`) y se lo pasa a "Detalle"
    (`setStretchFactor(self.texto_detalle, 1)`, sin límite de alto
    máximo) — Reservas regulares lo llama, así el cuadro "Detalle" crece
    para terminar a la misma altura que la columna del formulario (que
    ahora es la más alta, tras sacarle la label de horas aisladas) en
    vez de dejar que la grilla se estire con relleno vacío.
  - `achicar_detalle(alto)`: baja el alto máximo de "Detalle" (90px por
    defecto) a lo que se le pase — Reservas aisladas lo llama con 40px:
    acá es la columna de la grilla la que sobra en alto, así que hay que
    achicarla a ELLA (no dársela, como en Regulares) para poder correr
    el límite de scroll hacia abajo y dejarle más filas a la tabla de
    "Reservas aisladas".
  - Ninguno de los dos alcanzó, solo, a eliminar del todo el scroll
    necesario: `contenido`/`form` (el `QVBoxLayout` que envuelve todo el
    contenido scrolleable, y el del formulario en sí) tenían el margen
    default de Qt (9px por lado) sin ninguna necesidad — se puso a cero
    arriba/abajo en las dos solapas (`layout.setContentsMargins(0, 0, 0,
    0)`/`form.setContentsMargins(9, 0, 9, 0)`, dejando el margen
    izquierdo/derecho para no pegar el contenido al borde). Entre eso y
    el ajuste de "Detalle", Regulares queda con "% Descuento" visible
    sin ningún scroll (confirmado píxel a píxel: por debajo del borde
    del viewport por menos de 1px, imperceptible) y Aisladas queda
    apenas por debajo (~5px, el texto se sigue leyendo completo,
    confirmado recortando y agrandando la captura) — la clienta pidió
    específicamente más filas en la tabla de abajo, así que se priorizó
    eso sobre perseguir el último resto de scroll en esta solapa.

Tests nuevos: `test_gui_grilla_operativa.py`
(`dar_stretch_a_detalle_pasa_el_estirado_de_la_grilla_al_cuadro_detalle`,
`achicar_detalle_baja_el_alto_maximo`); `test_gui_reservas.py`
(`test_tabla_de_abajo_tiene_alto_fijo_para_filas_visibles` — reemplaza
al de "3 filas" de la ronda anterior, ahora con un número por solapa;
`test_regulares_sin_horas_aisladas_mensuales`;
`test_cuadro_detalle_queda_parejo_con_la_columna_del_formulario`).

## Reservas: título Profesional alineado, fecha con día de semana, ajustes finos

Cuarta vuelta sobre la misma zona, con cinco pedidos puntuales de la
clienta al revisar la captura de la ronda anterior:

- **Aisladas: se saca "Horas regulares semanales".** Simétrico al pedido
  de la vuelta anterior sobre Regulares (que se había sacado "Horas
  aisladas mensuales" de ahí) — ahora Aisladas se queda solo con "Horas
  aisladas mensuales" y "% Descuento", sacando el `QLabel`, el
  `form.addWidget` y las dos líneas de `.setText(...)` en su propio
  `_actualizar_resumen_profesional` (método duplicado, no compartido con
  Regulares). Cada solapa termina con sus propios dos títulos
  informativos, DISTINTOS entre sí — ninguna comparte las tres de antes.
- **"Fecha" de Aisladas con día de la semana.** `self.campo_fecha` pasa
  de `_FORMATO_FECHA` ("dd-MM-yyyy") a `_FORMATO_FECHA_DIA` ("ddd
  dd-MM-yyyy") + `_LOCALE_ES`, mismo criterio que Registro de ausencias/
  Fechas especiales (ej. "vie 25-09-2026") — duplicado acá porque son
  pantallas sin relación entre sí. Puntual de ESTE campo nomás: "Fecha
  que falta" (`campo_fecha_ausencia`, del bloque de reubicación) y las
  dos fechas de Vigencia de Regulares no fueron parte del pedido, se
  quedan con el formato de siempre.
- **"Profesional" alineado con "Filtro de localidad".** La clienta pidió
  bajar el título "Profesional" (primero de la columna del formulario)
  para que arranque a la misma altura que "Filtro de localidad" (primero
  del panel de Filtros de al lado) — quedaban desalineados por 21px,
  medido programáticamente: `form` (la columna del formulario) tenía
  margen superior en 0 desde la ronda anterior, mientras que "Filtro de
  localidad" vive dentro de un `QGroupBox` (`panel_filtros`) que suma su
  propio margen superior nativo para dejarle lugar a su borde/título,
  aunque ese título esté vacío. `_ALTO_TITULO_FILTROS = 21` (constante
  nueva, valor medido, no a ojo) pasa a ser el margen superior de `form`
  en las dos solapas, en vez de 0.
- **Ese margen nuevo hay que recuperarlo de algún lado.** Sumarle 21px al
  margen superior de `form` en Regulares volvía a esconder "% Descuento"
  fuera de la vista sin scrollear (el problema que la ronda anterior
  había resuelto) — `_ESPACIADO_FORM = 4` (contra el spacing default de
  Qt, 6px) achica un poco el espacio entre cada campo de esa columna
  (son muchos: 5 combos, "Días", horario, dos vigencias, 3 botones,
  separador, 2 títulos informativos), alcanza de sobra para compensar
  los 21px nuevos y deja además unos px de margen extra. En Aisladas no
  hizo falta tocar el spacing: sacar "Horas regulares semanales" (~20px)
  ya compensaba casi exactamente los 21px nuevos del margen, dejando la
  visibilidad de "% Descuento"/"Detalle" prácticamente en el mismo punto
  que antes de esta vuelta.
- **Aisladas: la tabla de abajo baja un poco (de 5 a 4 filas) para que
  "Detalle" se vea completo.** Con los cambios de esta
  vuelta, el cuadro "Detalle" quedaba visible por apenas 1px de margen
  (demasiado justo, la clienta señaló que quería verlo "en forma
  completa") — `_FILAS_VISIBLES_TABLA_INFERIOR_AISLADAS` baja de 5 a 4:
  la tabla de abajo pierde una fila de alto, ese alto se lo lleva de
  vuelta el panel de arriba, y tanto "Detalle" como "% Descuento" quedan
  con más de 10px de margen cada uno (confirmado programáticamente, no
  a ojo). Sigue siendo una fila más que las 3 originales de dos rondas
  atrás.
- **Tablas de abajo escrolleables verticalmente.** Ya lo eran por
  default de Qt (mismo criterio que Llaves: nunca hizo falta
  `setVerticalScrollBarPolicy` explícito, `QTableWidget` ya scrollea
  sola en cuanto su contenido no entra en el alto fijo) — se sumaron dos
  tests de regresión (uno por tabla, forzando 6 filas contra las 3/4
  visibles) que lo dejan cubierto de acá en adelante, sin haber hecho
  falta ningún cambio de código.
- **¿Estos cambios afectan la grilla de "Grilla y mensajería"?** No —
  consultado por la clienta, confirmado revisando el diff: ninguno de
  los cambios de esta vuelta tocó `app/gui/widgets/grilla_operativa.py`
  (el archivo de `GrillaOperativaWidget`, compartido por Reservas ×2,
  Oferta, Novedades ×3 y Grilla semanal) — todo vive en `reservas.py`
  (constantes, márgenes/spacing de `panel_form`, formato de fecha,
  cantidad de filas de la tabla), específico de las dos solapas de
  Reservas. La solapa "Grilla semanal" de "Grilla y mensajería" usa la
  misma `GrillaOperativaWidget` pero sin llamar a ninguno de los métodos
  opt-in que usa Reservas (`dar_stretch_a_detalle`/`achicar_detalle`/
  etc., de la ronda anterior) — sigue exactamente igual que antes de
  las últimas dos vueltas de Reservas.

Tests nuevos: `test_gui_reservas.py`
(`test_titulo_profesional_alineado_con_filtro_de_localidad` — compara
`mapToGlobal` de los dos títulos en las dos solapas;
`test_campo_fecha_aisladas_muestra_dia_de_la_semana`;
`test_tabla_horarios_reservados_escrolea_con_mas_filas_de_las_que_entran`/
`test_tabla_reservas_aisladas_escrolea_con_mas_filas_de_las_que_entran`,
mismo criterio que las tres de Llaves). El de "sin horas aisladas
mensuales" de la ronda anterior se renombra
`test_regulares_sin_horas_aisladas_mensuales_y_aisladas_sin_horas_
regulares` y suma las dos aserciones simétricas nuevas. El de "alto fijo
para filas visibles" actualiza su valor esperado en Aisladas de 5 a 4.

## Reservas: botones compactos con color, sin "% Descuento" en aisladas, Detalle a lo ancho

Quinta vuelta sobre la misma zona, con cuatro pedidos más:

- **Botones de acción compactos, pero con su color.** La clienta pidió
  que los tres botones de acción de cada solapa (Crear/Modificar/
  Finalizar en Regulares; Crear/Modificar/Cancelar en Aisladas)
  mantengan los colores primario/secundario de siempre, pero bajen de
  alto para quedar como "los otros" controles de esa columna — los
  botones-resumen de los filtros colapsables (`_FiltroColapsable._boton`
  en `grilla_operativa.py`, sin objectName, ~22px de alto con el padding
  default de Qt). Con `padding: 8px 16px` (el de `botonPrimario`/
  `botonSecundario` en `estilos.py`) esos botones medían 32px. Se
  revisó el código de los seis botones antes de tocar nada y salió a la
  luz que "Modificar seleccionada"/"Finalizar reserva a fin de mes"
  (Regulares) y "Modificar reserva"/"Cancelar reserva" (Aisladas) NUNCA
  habían tenido `objectName("botonSecundario")` puesto — quedaban sin
  colorear (gris/blanco default de Qt) desde que se armó esta pantalla,
  algo que no se había detectado en ninguna ronda anterior. Se corrigió
  de una junto con el pedido de esta vuelta: los cuatro suman
  `botonSecundario`, y los seis (los cuatro más los dos "Crear reserva
  ..." que ya eran `botonPrimario`) suman además
  `setStyleSheet("padding: 3px 16px;")` — un override puntual por
  widget, solo para estos seis botones de esta pantalla (constante
  `_ESTILO_BOTON_COMPACTO`, "cambio solo para estas pantallas", pedido
  explícito de la clienta, no se tocó `estilos.py`) que baja el alto a
  22px sin perder el color/borde que ya les da el objectName — Qt
  aplica el estilo del propio widget por encima del de la app para las
  propiedades que define, dejando las demás (color, borde) como las
  definió `estilos.py`.
- **En aisladas se saca también "% Descuento".** Ya se le había sacado
  "Horas regulares semanales" en la vuelta anterior; ahora se le saca
  "% Descuento" también — Aisladas termina con un solo título
  informativo ("Horas aisladas mensuales"), Regulares sigue con dos
  ("Horas regulares semanales" y "% Descuento", sin tocar).
- **Detalle a lo ancho en aisladas, no en regulares.** "El cuadro de
  detalle en horas aisladas podés agrandarlo en horizontal, que ocupe
  la segunda y tercer columna. En regulares no porque no entra" — hasta
  ahora "Detalle" vivía DENTRO de la columna de la grilla (la mitad
  derecha de `self.grilla`, al lado de la columna de Filtros), con la
  mitad del ancho disponible nomás. Método nuevo en
  `GrillaOperativaWidget`, `extraer_detalle()`: saca la etiqueta
  "Detalle:" y el `QTextEdit` del layout de la columna de la grilla
  (`self._layout_grilla.removeWidget(...)` en los dos, sin destruirlos)
  y devuelve los mismos objetos para que el que la use los reubique en
  otro layout — `self.texto_detalle` sigue siendo el mismo widget
  válido, solo cambia de padre. Reservas aisladas los agrega después a
  `layout_grupo_grilla` (el `QVBoxLayout` que ya envuelve TODO el ancho
  de `self.grilla`, Filtros + grid juntos — la "segunda y tercer
  columna" que pidió la clienta), quedando como una franja debajo de
  toda la grilla en vez de a un costado. Reservas regulares no llama a
  este método nuevo — se queda con "Detalle" adentro de la columna de
  la grilla, como en la ronda anterior (`dar_stretch_a_detalle`, sin
  cambios), tal como pidió la clienta explícitamente ("no entra").
  `achicar_detalle` (el método de la ronda anterior) sigue existiendo
  y sigue cubierto por su propio test, aunque Reservas ya no lo llama
  para Aisladas — el alto máximo de "Detalle" ahí ahora se fija con un
  `setMaximumHeight` directo sobre el `QTextEdit` ya extraído.
- **Tablas y "Detalle" scrolleables, repetido.** La clienta insistió en
  que tanto las tablas de abajo COMO el cuadro "Detalle" tienen que ser
  scrolleables cuando el contenido no entra — las tablas ya estaban
  cubiertas desde la ronda anterior; se sumó un test nuevo confirmando
  que "Detalle" (un `QTextEdit`) también scrollea sola por default de
  Qt, en las dos solapas, sin haber hecho falta ningún cambio de
  código.

Tests nuevos: `test_gui_grilla_operativa.py`
(`test_extraer_detalle_saca_la_etiqueta_y_el_texto_de_la_grilla`);
`test_gui_reservas.py` (`test_detalle_de_aisladas_ocupa_todo_el_ancho_
de_la_grilla` — compara el ancho de `texto_detalle` contra el de
`self.grilla` en las dos solapas; `test_botones_de_accion_quedan_
compactos_con_su_color` — aplica `hoja_estilos()` a la pantalla de
prueba, ya que esta pantalla se instancia sin pasar por
`VentanaPrincipal` en los tests y las reglas de `estilos.py` no
aplicarían solas; `test_cuadro_detalle_escrolea_con_mas_texto_del_que_
entra`). El de "sin horas aisladas mensuales" se renombra otra vez,
`test_regulares_sin_horas_aisladas_mensuales_y_aisladas_solo_horas_
aisladas`, y suma la aserción de "% Descuento" ausente en Aisladas.

## Reservas: grilla de aisladas achicada, Detalle pegado, botones más
## altos y fecha con día de semana en regulares

Sexta vuelta sobre la misma zona (formulario + grilla embebida) de
Reservas, con cinco pedidos puntuales de la clienta:

- **Regulares: la tabla de abajo, si hay lugar, que arranque más
  arriba.** Medido con un script de geometría (mismo criterio de todo
  este apartado): a la ventana de referencia (1500×800, la misma que usa
  `shot_reservas.py`) el `QScrollArea` de arriba (form + grilla) ya
  ocupa, sin scrollear, prácticamente todo el alto disponible antes de
  la tabla fija de abajo (`vscrollbar.maximum() == 0`, ni un pixel de
  sobra) — subir la cantidad de filas visibles de esa tabla en uno solo
  ya dispara scroll interno (`vscrollbar.maximum() == 14` al pasar de 3
  a 4 filas). Sin margen real para ganar una fila completa sin violar
  "sin tocar nada de los de arriba" (el pedido explícito de la clienta),
  se dejó `_FILAS_VISIBLES_TABLA_INFERIOR_REGULARES` en 3, documentado
  acá en vez de forzar un cambio que hubiera exigido tocar el formulario
  o la grilla de arriba, o mostrar una fila cortada a la mitad.
- **Aisladas: la grilla termina alineada con "Profesional filtrado".**
  La grilla (Período/Visualización + la tabla) dejaba de tener sentido
  que impusiera su propio alto natural (más alto que el panel de
  Filtros de al lado) al resto de la columna — pedido explícito de la
  clienta: que termine alineada con la última referencia de colores del
  panel de Filtros ("Profesional filtrado"). De paso, tanto en Aisladas
  como en Regulares, la grilla queda scrolleable de acá en adelante
  (revirtiendo, opt-in y solo para Reservas, la regla general de
  `_construir_tabla` de que "la grilla nunca debe recortarse con un
  scroll interno propio") — por si el día de mañana hace falta mostrar
  más horarios sin agrandar el panel.

  Tres métodos nuevos en `GrillaOperativaWidget`, todos opt-in (no
  tocan el resto de los usos de esta grilla compartida — Oferta,
  Novedades, Grilla semanal):
  - `alto_natural_filtros()`: el `sizeHint()` (no `.height()`, que ese
    panel tiene un `addStretch()` final que infla su alto real más allá
    de su contenido visible) del panel de Filtros — para que quien la
    use se pueda alinear contra él sin acceder a `_panel_filtros` desde
    afuera.
  - `alto_natural_grilla()`: análogo, pero de esta misma columna
    (Período/Visualización + la tabla) — pensado para pasarle a
    `limitar_alto_grilla` un tope "igual a lo que ya mide hoy" cuando
    solo se quiere dejarla scrolleable sin cambiar nada visible (el caso
    de Regulares en esta misma vuelta).
  - `limitar_alto_grilla(alto)`: pone un tope de alto FIJO a la columna
    entera (`self`, el widget completo — no solo a `self.tabla`) en
    `alto`, descontando primero todo lo que en esa columna NO es la
    tabla en sí (la fila Período/Visualización, el espaciado antes de la
    grilla y los márgenes arriba/abajo de `layout_grilla`) antes de
    aplicárselo a `self.tabla`. A partir de acá la tabla scrollea sola
    si su contenido no entra en ese alto.

  Reservas aisladas llama `limitar_alto_grilla(alto_natural_filtros())`
  (tope ESTRICTO, igual al panel de Filtros); Reservas regulares llama
  `limitar_alto_grilla(alto_natural_grilla())` (tope IGUAL a lo que ya
  mide hoy — no recorta nada, solo habilita el scroll a futuro).

  Dos bugs de layout reales, no pedidos pero necesarios para que esto
  funcionara, encontrados al medir píxel a píxel contra lo esperado:
  - `limitar_alto_grilla` descontaba de menos al principio (le faltaban
    los márgenes de `layout_grilla`, solo restaba la fila de controles y
    el espaciado): el contenido real de la columna (margen + fila +
    tabla ya recortada + margen) terminaba siendo MÁS ALTO que el tope
    puesto al widget completo, y el exceso desbordaba en vez de quedar
    alineado. Se corrigió sumando esos márgenes a lo que se descuenta.
  - Poner un tope de alto a `self` (el widget entero) SIN un
    `addStretch()` final en el layout que lo contiene hace que Qt
    CENTRE el widget dentro del sobrante en vez de dejarlo pegado
    arriba (mismo mecanismo, un nivel más afuera, que el
    `addStretch()` que ya tenía `GrillaOperativaWidget._armar_ui` desde
    la ronda de "botones compactos" — ver esa sección más arriba).
    Esto rompió en silencio la alineación de "Profesional" contra
    "Filtro de localidad" en Reservas REGULARES (destapado por
    `test_titulo_profesional_alineado_con_filtro_de_localidad`, que ya
    existía de una ronda anterior) — `self.grilla` quedaba centrado en
    el sobrante que le daba el splitter en vez de pegado arriba. Se
    corrigió sumando el mismo `addStretch()` al `layout_grupo_grilla`
    de Reservas regulares (Aisladas ya lo tenía, por eso no se vio ahí).
- **Aisladas: "Detalle" sube para pegarse a la grilla ya achicada.**
  Con la grilla más baja, "Detalle" (extraído con `extraer_detalle` en
  una ronda anterior) queda pegado justo debajo, sin el hueco de más
  que tenía antes (heredado de cuando la grilla quedaba forzada a la
  altura del panel de al lado por el splitter, con un montón de espacio
  muerto invisible adentro). `_ALTO_DETALLE_AISLADAS` sube de 40 a 96
  (valor medido, no a ojo) para que el cuadro, ya con su tope de alto
  más alto, termine en la misma posición absoluta que tenía antes de
  esta vuelta — "que se vea todo parejo", ganando una columna angosta y
  perdiendo hueco muerto, sin cambiar el punto final.
- **Aisladas: los tres botones crecen para alinear "Horas aisladas
  mensuales" con el pie de "Detalle".** Nuevo estilo puntual,
  `_ESTILO_BOTON_AISLADAS_ALTO = "padding: 11px 16px;"` (≈38px de alto),
  que reemplaza a `_ESTILO_BOTON_COMPACTO` (22px) SOLO en los tres
  botones de Aisladas (Crear/Modificar/Cancelar) — los de Regulares
  siguen en 22px, no fueron parte de este pedido. Valor medido
  iterativamente (padding candidato → medir → ajustar), no calculado a
  ojo.
- **Regulares: "Vigencia desde"/"Vigencia hasta" con día de la semana.**
  Mismo formato `"ddd dd-MM-yyyy"` + `QLocale` español que ya tenía
  "Fecha" en Aisladas desde una ronda anterior — pedido explícito de la
  clienta ("que se comporte igual"). "Fecha que falta"
  (`campo_fecha_ausencia`, del bloque de reubicación en Aisladas) no fue
  parte de este pedido y sigue con el formato de siempre.

Tests nuevos: `test_gui_grilla_operativa.py`
(`test_alto_natural_filtros_devuelve_el_sizehint_del_panel_de_filtros`,
`test_alto_natural_grilla_devuelve_el_sizehint_de_la_columna_de_la_
grilla`, `test_limitar_alto_grilla_con_el_alto_natural_no_cambia_nada`,
`test_limitar_alto_grilla_con_un_tope_mas_chico_recorta_la_tabla_y_el_
widget`); `test_gui_reservas.py`
(`test_grilla_de_regulares_mantiene_el_tope_identidad_sin_achicarse`,
`test_grilla_de_aisladas_termina_alineada_con_las_referencias_de_
colores`, `test_detalle_de_aisladas_queda_pegado_debajo_de_la_grilla`,
`test_titulo_horas_aisladas_alineado_con_el_pie_de_detalle`,
`test_botones_de_aisladas_quedan_mas_altos_que_los_de_regulares`). El
de "botones compactos" (`test_botones_de_accion_quedan_compactos_con_
su_color`) pasa a verificar solo los de Regulares (22px), separando el
caso de Aisladas al test nuevo de arriba; el de "cuadro Detalle parejo"
actualiza su valor esperado de `maximumHeight()` de 40 a 96; el de
formato de fecha suma "ddd dd-MM-yyyy" para las dos "Vigencia" de
Regulares.

## Reservas: tablas de abajo sin título (con espaciador que compensa),
## grilla de aisladas completa y "Cant. horas..."

Séptima vuelta sobre la misma zona de Reservas, con cuatro pedidos:

- **Regulares/Aisladas: se sacan los títulos "Horarios reservados"/
  "Reservas aisladas" de la tabla de abajo, "para que la tabla pueda
  situarse un poco más arriba".** Sacar el título por sí solo NO mueve
  la tabla ni un pixel: `layout_externo` (el layout de cada solapa)
  reparte TODO el alto disponible entre el `QScrollArea` de arriba
  (`stretch=1`) y `panel_tabla` (sin stretch) — cualquier alto que
  `panel_tabla` deje de necesitar (al perder el título) se lo vuelve a
  llevar el scroll (el único ítem flexible), empujando `panel_tabla`
  hacia ABAJO exactamente la misma medida. Confirmado midiendo antes/
  después: la posición absoluta de la tabla no cambiaba un pixel al
  sacar el título solo. Se corrigió agregando un espaciador FIJO
  (`_ALTO_TITULO_PANEL_TABLA = 14`, valor medido — un `QGroupBox` con
  título vs. sin título, mismo contenido, siempre difieren en 14px,
  independiente del contenido) justo después de `panel_tabla` en
  `layout_externo`: compensa exactamente el alto que el título dejó de
  ocupar, así el reparto entre scroll/tabla no cambia (`scroll` termina
  exactamente en la misma posición que antes — cumple "sin tocar nada
  de lo que está antes de la tabla", pedido explícito de la clienta) y
  la tabla sí sube esos 14px, con el espaciador como hueco muerto al
  final de todo el panel, después de la tabla, donde no se nota.
- **"Horas aisladas mensuales"/"Horas regulares semanales" pasan a
  "Cant. horas aisladas mensuales"/"Cant. horas regulares semanales".**
  Cambio de texto nomás, en los dos métodos `_actualizar_resumen_
  profesional` (uno por solapa, no comparten código).
- **Aisladas: la grilla se ve completa, ya no recortada.** La ronda
  anterior la había capado a la altura del panel de Filtros de al lado
  (para que "termine alineada con Profesional filtrado"), pero eso la
  dejaba con una tabla scrolleable que en la práctica se veía "cortada"
  — pedido explícito de la clienta: "dale mas alta de manera que se
  visualice completa". Pasa al mismo criterio "identidad" que ya usaba
  Regulares (`limitar_alto_grilla(alto_natural_grilla())`, sin recortar
  nada, solo deja la infraestructura de scroll lista para el día de
  mañana). Importa el ORDEN: `extraer_detalle()` se llama ANTES de medir
  `alto_natural_grilla()` — si se sacara después, ese alto natural
  todavía arrastraría el de "Detalle" (que de todos modos se saca a
  continuación), dando un valor de referencia más alto de lo que
  corresponde.
- **Los "cuadraditos" de "Referencias de colores" crecen para llegar al
  borde inferior de la grilla, ya más alta.** Con la grilla mostrándose
  completa (más alta que antes), el panel de Filtros de al lado queda
  más bajo — pedido explícito de la clienta: la diferencia se reparte
  entre las muestras de color de la leyenda (no se deja como hueco en
  blanco al final, que es lo que haría solo el `addStretch()` de
  `layout_filtros`). Tres piezas nuevas, todas opt-in (no tocan el resto
  de los usos de esta grilla compartida): `LeyendaColores.
  fijar_tamano_muestra(ancho, alto)` (guarda el tamaño nuevo, no
  redibuja); `GrillaOperativaWidget.tamano_muestra_leyenda()` (lee el
  tamaño actual, para calcular cuánto agrandar a partir de ahí, sin
  acceder a `_leyenda_colores` desde afuera); `GrillaOperativaWidget.
  agrandar_muestras_leyenda(ancho, alto)` (fija el tamaño Y refresca la
  leyenda de una sola llamada). Reservas aisladas calcula la diferencia
  entre el alto natural de la grilla y el del panel de Filtros, la
  reparte en partes iguales entre las 3 filas de la leyenda compacta (6
  referencias / 2 columnas) y se lo suma al alto de muestra actual.
  Guardarraíl: si la diferencia da negativa o cero (ej. una base con muy
  pocos consultorios cargados, la grilla sin columnas queda más baja que
  Filtros) no se toca nada — agrandar con un valor negativo hubiera
  producido una muestra de tamaño inválido (confirmado con un
  `QWidget::setMinimumSize` de alto negativo al probarlo sin este
  guardarraíl, con una base de prueba vacía).
- **"Detalle" recalculado.** Sigue arrancando pegado justo debajo de la
  grilla (sin cambios en ESE mecanismo), pero como la grilla ahora
  termina más abajo (se ve completa, más alta que el criterio "alineada
  con Filtros" de la ronda anterior), "Detalle" arranca más tarde —
  `_ALTO_DETALLE_AISLADAS` baja de 96 a 54 (valor medido iterativamente,
  no calculado a ojo — el `QTextEdit` con `stretch=0` no crece
  exactamente hasta el `maximumHeight` que se le pone, así que hizo
  falta ajustar por aproximaciones sucesivas) para que el cuadro
  siga terminando exactamente a la par del borde inferior de "Cant.
  horas aisladas mensuales", como pedía la clienta ("termina a la par
  de 'Cant. horas aisladas mensuales' para que luego pegado esté la
  tabla").

Tests nuevos: `test_gui_grilla_operativa.py`
(`test_tamano_muestra_leyenda_devuelve_el_tamano_actual`,
`test_agrandar_muestras_leyenda_cambia_el_tamano_y_refresca`);
`test_gui_reservas.py`
(`test_tabla_de_abajo_sin_titulo_tiene_espaciador_que_compensa`). El de
"sin título de Vista previa..." se actualiza para no asumir más un
título en la tabla de abajo (usa `panel.tabla.parentWidget()` en vez de
buscar por texto de título). El de "cuadro Detalle parejo" actualiza su
valor esperado de `maximumHeight()` de 96 a 54. El de alineación
"Horas aisladas mensuales"/pie de Detalle pasa a usar `_preparar(conn)`
(al menos un consultorio cargado): con una base totalmente vacía la
grilla no tiene columnas y su alto natural se achica mucho, corriendo
todo el cálculo fuera de rango — mismo motivo por el que las capturas
que se le envían a la clienta siempre parten de datos de ejemplo, nunca
de una base vacía.

## Reservas: cuadraditos de referencias más grandes en regulares, tablas
## de abajo sin hueco arriba

Octava vuelta sobre la misma zona de Reservas, con dos pedidos:

- **Regulares: "Referencias de colores" un poco más grande a lo alto,
  "hay lugar para hacerlo".** Investigado con el mismo criterio de
  medición de siempre, salió a la luz un comportamiento no documentado
  hasta ahora de este panel: "Referencias de colores" (`_leyenda_
  colores`, dentro de `panel_filtros`) NO cambia de alto según su propio
  contenido — `layout_filtros` (el `QVBoxLayout` de todo el panel de
  Filtros) le da un lugar FIJO (determinado por lo que sobra después de
  ubicar el resto de los filtros de arriba, con un `addStretch()` final
  absorbiendo cualquier resto), así que agrandar o achicar la muestra de
  color NUNCA cambia el alto del `QGroupBox` en sí — solo cambia cuánto
  de ese lugar fijo usa el contenido real, versus cuánto queda como
  hueco en blanco debajo. Confirmado con un experimento: entre (28,16) y
  (28,40) el propio `_leyenda_colores.height()` medido da el MISMO valor
  exacto (262px) sin importar el tamaño de muestra pedido — el
  `sizeHint()`/`minimumSizeHint()` sí crecen con la muestra, pero el
  alto REAL asignado no se mueve mientras siga entrando en ese lugar
  fijo. Recién a partir de cierto punto (~(28,50) para las 8 referencias
  de Regulares, 4 filas) el contenido empieza a no entrar y las filas se
  superponen/recortan de verdad (confirmado visualmente con (28,80):
  filas literalmente pisándose unas a otras).
  `GrillaOperativaWidget.agrandar_muestras_leyenda(28, 26)` — 26px de
  alto por muestra, bastante por debajo del límite medido (~50px), "un
  poquito" más grande como pidió la clienta, no al límite de lo que
  entra. Dos piezas nuevas en `LeyendaColores`/`GrillaOperativaWidget`,
  ambas opt-in (no tocan el resto de los usos de esta grilla compartida
  — ya se habían sumado hermanas de estas en la ronda anterior para
  Aisladas, ver esa sección): `LeyendaColores.fijar_tamano_muestra`
  reusada tal cual (ya existía); esta vuelta solo suma la LLAMADA nueva
  desde Regulares, no funciones nuevas.
- **Las dos tablas de abajo tienen un hueco en blanco arriba, "podrán
  arrancar más arriba, más pegado al contenido que está arriba".**
  Medido: dentro de `panel_tabla` (el `QGroupBox` sin título de la ronda
  anterior), `layout_tabla` tenía el margen default de Qt (9px arriba)
  sin ninguna necesidad, dejando ese hueco entre el borde del cuadro y
  el encabezado de la tabla. `layout_tabla.setContentsMargins(9, 0, 9,
  9)` (arriba en 0, el resto igual) lo saca.

  Mismo mecanismo de la ronda anterior, y la misma trampa: achicar
  `panel_tabla` (acá, sacándole el margen) por sí solo NO sube la tabla
  — `layout_externo` le vuelve a dar ese alto liberado al `QScrollArea`
  de arriba (el único ítem con `stretch=1`), dejando la tabla en la
  misma posición absoluta que antes. `_ALTO_TITULO_PANEL_TABLA` (el
  espaciador fijo después de `panel_tabla` que compensa esto, sumado la
  ronda pasada para el título) sube de 14 a 23 (14 del título + 9 de
  este margen) para seguir compensando el total correcto — confirmado
  midiendo que el `QScrollArea` de arriba queda exactamente en la misma
  posición que antes de esta vuelta, y que la tabla en sí baja su
  encabezado de 15px de hueco interno a solo 6px (el mínimo que impone
  el propio borde del `QGroupBox`, no recortable más).

Tests nuevos: `test_gui_reservas.py`
(`test_leyenda_de_regulares_se_agranda_un_poco`,
`test_tabla_de_abajo_sin_margen_superior`). El de "panel de Filtros
compacto" deja de comparar `_tamano_muestra` exacto entre las dos
solapas (ahora difiere: Regulares agranda a un valor fijo, Aisladas
según cuánto le sobre a la grilla, puede quedar en el tamaño compacto de
base si no hay diferencia que repartir) y pasa a comprobar solo el ancho
(28, común a las dos).

## Reservas: tabla de Regulares más pegada a lo de arriba, grilla de
## Aisladas sin scrollbar interno

Novena vuelta sobre la misma zona de Reservas, con dos pedidos puntuales
más:

- **Regulares: "subí un poco más la tabla para pegarlo a lo de arriba
  sin tocar el resto".** Medido con el mismo criterio de todo este
  apartado: además del margen superior de `layout_tabla` (ya sacado en
  una ronda anterior) y del borde nativo del `QGroupBox` (~6px,
  irreductible, confirmado de nuevo), `layout_externo` todavía tenía el
  espaciado DEFAULT de Qt (6px) entre el `QScrollArea` de arriba y
  `panel_tabla` — un hueco de más antes de la tabla que no era ni el
  margen del cuadro ni el borde nativo. `layout_externo.setSpacing(0)`
  (solo en Regulares — la clienta no pidió tocar Aisladas en este
  pedido) lo saca; mismo mecanismo de siempre (`layout_externo` reparte
  TODO el alto disponible entre el scroll de arriba, único ítem con
  `stretch=1`, y el resto): sacar ese espaciado por sí solo NO sube la
  tabla, el scroll se lo vuelve a llevar. Comparando `panel.height() -
  scroll_area.height()` (el consumo fijo total, sin el scroll) antes y
  después con un script de geometría, el ajuste correcto resultó ser
  sumar 6px al espaciador final (no 12, como daría sumar ingenuamente
  los dos espaciados de 6px que rodeaban a `panel_tabla` antes de
  sacarlos — parte de ese espaciado ya quedaba "libre" del otro lado sin
  necesitar compensación doble): `_ALTO_TITULO_PANEL_TABLA_REGULARES =
  _ALTO_TITULO_PANEL_TABLA + 6 = 29`, constante nueva y propia de
  Regulares (Aisladas se queda con `_ALTO_TITULO_PANEL_TABLA = 23` de
  siempre, sin tocar). Confirmado con el mismo script que `scroll`
  termina en la MISMA posición absoluta que antes de este cambio ("sin
  tocar el resto") y que la tabla sube esos 6px.
- **Aisladas: "ajustá un pelín la grilla para que se vea el borde de
  abajo y que no aparezca el escrolleable".** El tope "identidad"
  (`alto_natural_grilla()`, de la ronda anterior) dejaba
  `tabla.verticalScrollBar().maximum()` en 1 con datos reales — un
  desfasaje mínimo entre el `sizeHint()` de la columna (de donde sale el
  tope) y lo que la tabla de la grilla realmente necesita para
  mostrarse sin scroll interno (`sum(rowHeight(i)) + 2 × frameWidth`,
  con el encabezado horizontal oculto): 2px de diferencia, medidos con
  un script de geometría, no algo que dependa de los datos cargados.
  `_AJUSTE_ALTO_GRILLA_AISLADAS = 2` se suma al tope antes de aplicarlo
  (`self.grilla.alto_natural_grilla() + _AJUSTE_ALTO_GRILLA_AISLADAS`),
  dejando `verticalScrollBar().maximum()` en 0 contra la pantalla
  completa (mismo armado que `shot_reservas.py`) — confirmado
  visualmente en la captura, el borde inferior de la grilla se ve
  entero.

  El valor exacto de `verticalScrollBar().maximum()` renderizado resultó
  ser sensible al ANCHO real de la ventana (no solo al contenido): contra
  una `PantallaReservas` armada sola con `qtbot` (sin la ventana
  completa, como hacen el resto de los tests de este archivo) el mismo
  ajuste no lograba bajarlo a 0 — reproducido aparte con un script de
  geometría: el offscreen platform de Qt tira un warning conocido
  ("This plugin does not support propagateSizeHints()") que ya viene
  apareciendo en toda esta ronda de trabajo, y hace que el `sizeHint()`
  de un layout no sea perfectamente estable entre una llamada y la
  siguiente una vez que se modificó algo aguas abajo (acá, agrandar la
  leyenda de colores DESPUÉS de aplicar el tope). Por eso el test de
  regresión nuevo no vuelve a comparar contra `verticalScrollBar().
  maximum()` ya renderizado (frágil, depende del ancho real de la
  ventana en la que se mida) ni contra un nuevo llamado a
  `alto_natural_grilla()` (tampoco estable una vez terminada la
  construcción) — compara contra `panel._alto_grilla_aplicado`, un
  atributo nuevo que guarda el valor efectivamente usado en el momento
  en que se llamó a `limitar_alto_grilla`, mismo criterio de
  determinismo que ya usaba `test_grilla_de_regulares_mantiene_el_tope_
  identidad_sin_achicarse` (tampoco depende del scrollbar ya
  renderizado). La verificación visual real (que el scrollbar no
  aparece y el borde se ve completo) queda cubierta por la captura de
  pantalla contra la ventana completa, no por este test.

Tests nuevos: `test_gui_reservas.py`
(`test_regulares_tabla_de_abajo_sube_sin_mover_el_scroll_de_arriba` —
compara el espaciado de `layout_externo` y el tamaño del espaciador
final de cada panel contra su propia constante, ya no comparten el
mismo valor; `test_aisladas_grilla_ajustada_sin_scrollbar` — compara
`panel_a.grilla.maximumHeight()` contra `panel_a._alto_grilla_aplicado`,
el valor real usado en la construcción). El de "espaciador que compensa"
(`test_tabla_de_abajo_sin_titulo_tiene_espaciador_que_compensa`) se
actualiza para comparar cada panel contra su propia constante en vez de
una sola compartida.

## Reservas: tablas de abajo agrandadas al máximo, separación mínima
## grilla-Detalle en Aisladas, cuadros scrolleables como regla general

Décima vuelta sobre la misma zona de Reservas, con tres pedidos:

- **Regulares: "ampliá el tamaño de la tabla, subiéndola arriba al
  límite de cuando termina el cuadro de Detalle... y que llegue lo más
  abajo posible dentro de la pantalla que se visualiza. Solo tocá la
  tabla, nada del resto".** Hasta la ronda anterior `layout_externo`
  (form+grilla scrolleable, seguido de la tabla de abajo) le daba TODO
  el alto sobrante de la ventana al `QScrollArea` de arriba
  (`stretch=1`), mientras la tabla se quedaba con un alto fijo de 3
  filas sin importar cuánta ventana sobrara debajo — medido con un
  script de geometría: 585px de scroll contra un mínimo real de 569px
  (`contenido.minimumSizeHint()`), y 73px de ventana sin usar debajo de
  la tabla. Se invirtió el reparto: `scroll` pasa a un alto FIJO igual a
  ese mínimo real (así el contenido de arriba no se mueve ni un pixel,
  "nada del resto") y es `panel_tabla` el que pasa a `stretch=1` en
  `layout_externo` — la tabla se lleva TODO el sobrante, tanto el que
  antes quedaba invisible dentro del scroll como el que sobraba al pie
  de la ventana. `self.tabla` pasa de `setFixedHeight` a
  `setMinimumHeight` (mismo cálculo de `_alto_para_filas`, ahora como
  piso en vez de techo) para poder crecer con `panel_tabla` sin dejar de
  garantizar esas filas mínimas. Ya no hace falta ningún espaciador de
  compensación (`_ALTO_TITULO_PANEL_TABLA`/`_ALTO_TITULO_PANEL_TABLA_
  REGULARES`, de las dos rondas anteriores, se sacan): no hay más hueco
  muerto que esconder, todo el sobrante pasa a ser tabla de verdad.
  Confirmado con captura: la tabla queda mucho más grande, pegada contra
  el borde inferior de Detalle arriba (el margen que queda, ~13px, es un
  límite propio de la grilla — ver el punto siguiente, no se tocó) y
  contra el borde de la pantalla abajo.
- **Aisladas: "el título Detalle y el comienzo de la tabla... subilo un
  poco para que haya una separación mínima con la grilla. Y la tabla de
  abajo bajala un poco más".** Mismo mecanismo que Regulares (`scroll`
  a alto fijo, `panel_tabla` a `stretch=1`) para la tabla de abajo. Para
  la separación grilla-Detalle: `layout_grupo_grilla.setSpacing(0)` saca
  el espaciado default de Qt (6px) entre el borde de `self.grilla` y
  "Detalle:", dejando solo el borde propio de la grilla como separación
  (de 7px a 1px, medido). Efecto secundario esperado: "Detalle" se corrió
  hacia arriba, rompiendo la alineación de su borde inferior contra el
  pie de "Cant. horas aisladas mensuales" que se había logrado en una
  ronda anterior ("que se vea todo parejo") — `_ALTO_DETALLE_AISLADAS`
  sube de 54 a 64 (medido, no a ojo) para recuperarla.

  Estas dos tablas dependen de que `scroll` tenga un alto FIJO calculado
  con `contenido.minimumSizeHint()` — ese `sizeHint()` no siempre está
  asentado la primera vez que se calcula (mismo tipo de imprecisión ya
  documentado para `alto_natural_grilla()` en Aisladas: el offscreen
  platform de Qt no soporta `propagateSizeHints`). Las dos solapas
  guardan `scroll`/`contenido` como `self._scroll_superior`/`self.
  _contenido_superior` y vuelven a fijar el alto en `showEvent` (que ya
  existía, para el foco inicial) con el valor ya asentado — mismo
  criterio que otros recálculos en `showEvent` de este archivo.
- **"Siempre todos los cuadros del sistema que sean escroleables en el
  caso de que no se vea la información completa en la pantalla".** Regla
  general, no puntual de esta ronda (mismo criterio que "Foco (Enter/
  Tab): orden general" o "Selectores y fecha" más arriba: una vez que la
  clienta la marca así, se aplica hacia adelante, no se sale a auditar
  todo el sistema de una sola vez). Ya era el comportamiento por defecto
  de `QTableWidget`/`QTextEdit` en todas las tablas y cuadros de texto de
  este sistema (nunca hizo falta `setVerticalScrollBarPolicy` a mano,
  confirmado con tests dedicados en Llaves, Reservas, etc.) — al pasar
  las tablas de esta pantalla de un alto fijo a un piso (`setMinimumHeight`)
  hacían falta bastantes más filas que antes para forzar el desborde en
  los tests que ya lo cubrían (`test_tabla_horarios_reservados_escrolea_
  con_mas_filas_de_las_que_entran`/`test_tabla_reservas_aisladas_
  escrolea_con_mas_filas_de_las_que_entran`, ahora con 36 y 30 filas en
  vez de 6) — confirmado que el mecanismo sigue intacto, la tabla más
  grande simplemente tarda más filas en necesitar su propio scroll.

Tests nuevos/actualizados en `test_gui_reservas.py`:
`test_tabla_de_abajo_se_expande_con_el_sobrante_de_la_ventana` (stretch
de `scroll`/`panel_tabla` en `layout_externo`, alto fijo de `scroll`
igual al `minimumSizeHint()` de su contenido, sin ningún ítem después de
`panel_tabla`, reemplaza al viejo test del espaciador que compensa);
`test_layout_externo_sin_espaciado_en_las_dos_solapas` (spacing 0 en las
dos, reemplaza al que comparaba contra la constante vieja de Regulares
nomás); `test_grilla_y_detalle_de_aisladas_separacion_minima` (gap
grilla→"Detalle:" ≤ 2px); `test_tabla_de_abajo_tiene_un_piso_de_filas_
visibles` (renombrado desde "...alto_fijo...", ahora compara con `>=` en
vez de `==`); `test_cuadro_detalle_queda_parejo_con_la_columna_del_
formulario` actualiza el valor esperado de Aisladas de 54 a 64.

## Reservas: aviso si al profesional le falta la llave de acceso al cargar una reserva

Pedido de la clienta, ya con la revisión "uno por uno" de pantallas
cerrada: "cuando se intente cargar una reserva, ya sea aislada o
regular, que el sistema chequee si el profesional tiene las llaves del
edificio y de la unidad necesarias para ingresar... En el caso de que le
falte alguna, que salga un alerta... con opción de confirmar/continuar y
cancelar. Un profesional sin acceso le puedo hacer abrir por medio de
otro profesional que esté en ese momento, por eso no es excluyente...
pero está bueno que el sistema me avise para que en ese momento vea cómo
manejo el tema del acceso." Explícitamente NO bloqueante — solo informa,
nunca impide cargar la reserva.

No se consultó ninguna decisión abierta antes de implementar (a
diferencia de otras funcionalidades nuevas de esta lista): el modelo de
datos de Llaves ya resuelve sin ambigüedad qué significa "tener acceso"
(una Asignación abierta de una Llave activa cuyo LlaveAcceso cubre el
lugar), y el pedido en sí ya describe el comportamiento de punta a
punta (avisa, no bloquea, Confirmar/Cancelar) sin dejar ninguna bifurcación
real de producto para decidir.

`app.negocio.llaves.llaves_faltantes_para_reserva(conn, id_profesional,
id_consultorio)` (nueva) resuelve Consultorio → Unidad → Edificio y
devuelve una lista de textos ("la llave del edificio {nombre}"/"la
llave de la unidad {departamento}") por cada nivel que le falta —
vacía si tiene todo lo necesario, o si ese lugar no tiene ninguna Llave
ACTIVA configurada (nada para chequear: un edificio que nunca cargó
llaves en el sistema no tiene por qué generar alertas). "Tener" un
acceso es: alguna Llave activa con `LlaveAcceso` a ese lugar tiene una
`LlaveMovimiento` Tipo="Asignación" SIN Devolución/Pérdida que la cierre
a nombre de este profesional — alcanza con cualquiera de las que abren
ese lugar, no hace falta tener todas. El acceso a nivel EDIFICIO se
distingue de uno a nivel UNIDAD por si el `LlaveAcceso` tiene o no
`IdUnidad`: uno con unidad puntual solo abre esa unidad, no el edificio
entero — `.listar(IdUnidad=None)` no sirve para este filtro (una
comparación SQL "= NULL" nunca es verdadera), así que se filtra en
Python sobre todos los accesos del edificio.

En `app/gui/pantallas/reservas.py`, `_confirmar_llaves_faltantes` (una
función a nivel de módulo, no un método — se comparte entre las dos
solapas, mismo criterio que `_alto_para_filas`) arma el cartel
`QMessageBox.question` con Sí/No ("¿Confirmás la reserva de todos
modos?"), mismo mecanismo (`QMessageBox.question`, no un diálogo
propio) que ya usa este archivo para `ConflictoBloqueanteError`. El
chequeo se llama UNA sola vez por click en "Crear reserva regular"/
"Crear reserva aislada" — en Regulares, antes del loop que crea una
fila por cada día tildado (no tiene sentido preguntar una vez por día,
la llave que hace falta es la misma para todos); en Aisladas, con la
misma guarda `if not forzar` que ya protege la pregunta de "¿fecha de
un mes anterior?" — evita volver a preguntar en el reintento automático
con `forzar=True` que dispara `ConflictoBloqueanteError` (ya se
confirmó, o no hacía falta, en el primer intento).

"Modificar seleccionada"/"Modificar reserva" en las dos solapas no
necesitó ningún cambio aparte: ya funcionaban finalizando/cancelando la
reserva vieja y precargando el formulario para dar de alta la versión
nueva por el mismo botón "Crear" (documentado desde que se armó esa
función) — el aviso de llaves, enganchado ahí, cubre alta y
modificación por igual sin duplicar nada.

Tests nuevos: `tests/test_llaves.py` (11 tests de
`llaves_faltantes_para_reserva` — sin ninguna llave configurada, falta
edificio, falta unidad, faltan las dos, con Asignación abierta no
reporta nada, una Devolución vuelve a reportarlo, alcanza con
cualquiera de varias llaves del mismo lugar, una Llave inactiva no
cuenta, una llave de unidad puntual no cuenta como acceso de edificio,
consultorio inexistente no rompe); `tests/test_gui_reservas.py` (6
tests, 3 por solapa: avisa y confirma con "Yes" — se crea igual; avisa
y cancela con "No" — no se crea nada; con la llave ya asignada no se
llama a `question` en absoluto — confirmado forzando la respuesta a
"No" y comprobando que la reserva se crea de todos modos).

## Reservas: aviso si al profesional le falta la placa de la unidad

Pedido explícito de la clienta, mismo mecanismo y mismo cartel que el
aviso de llaves faltantes (ver "Reservas: aviso si al profesional le
falta la llave..." más arriba): "cuando asigne una reserva, ya sea
aislada o regular, que el sistema chequee si el profesional tiene placa
en la unidad a la cual se le asigna... si no tiene placa no bloquea,
emite un alerta... con opciones de continuar o cancelar. Este alerta
funciona en conjunto con el alerta de las llaves, en el mismo cuadro
avisa si le falta llave y placa, solo placa o solo llave. Si no le
falta nada el alerta no se hace." Tampoco acá se consultó ninguna
decisión abierta: el pedido ya describe el comportamiento de punta a
punta y el modelo de `Placa` (una fila por posición del tablero de una
Unidad, con `IdProfesional`) ya resuelve sin ambigüedad qué significa
"tener placa" — cualquier posición asignada a ese profesional en esa
Unidad alcanza, no hace falta ninguna posición puntual.

`app.negocio.placas.placa_faltante_para_reserva(conn, *, id_profesional,
id_consultorio)` (nueva) resuelve Consultorio → Unidad y devuelve
`["la placa de la unidad {Departamento}"]` si el profesional no tiene
ninguna fila de `Placa` en esa Unidad, o `[]` si ya tiene alguna (en
cualquier posición) o si el consultorio/unidad no existen — mismo
contrato exacto que `llaves_faltantes_para_reserva` (misma firma de
parámetros por keyword, misma forma de lista de textos), a propósito,
para que las dos listas se puedan concatenar sin ninguna adaptación.

En `app/gui/pantallas/reservas.py`, `_confirmar_llaves_faltantes` se
renombra `_confirmar_llave_o_placa_faltante` y arma un único cartel
(`QMessageBox.question`, título "Falta llave o placa") con el mensaje
"Al profesional le falta " + " y ".join(faltantes) + — la lista que
recibe ya viene de concatenar las dos funciones
(`llaves_faltantes_para_reserva(...) + placa_faltante_para_reserva(...)`)
en los dos call sites (Regulares y Aisladas), así que el texto
menciona automáticamente cualquier combinación (solo llave, solo placa,
o ambas juntas) sin necesitar ninguna rama nueva — si la lista
concatenada queda vacía, no se llama a la función y no aparece ningún
cartel. Mismo lugar de la cadena que antes (una sola vez por click en
"Crear...", antes del loop de días en Regulares; con la misma guarda
`if not forzar` en Aisladas para no repreguntar en el reintento
automático de `ConflictoBloqueanteError`).

Tests nuevos: `tests/test_placas.py` (`placa_faltante_para_reserva` — 5
tests: sin placa la reporta, con placa asignada no reporta nada,
alcanza con cualquier posición del tablero, no cuenta la placa de otro
profesional, consultorio inexistente no rompe — mismo criterio que los
tests ya existentes de `llaves_faltantes_para_reserva`).
`tests/test_gui_reservas.py` suma, en las dos solapas, un test de
"avisa solo por placa si no hay llaves configuradas" y uno de "avisa
con llave y placa juntas en un mismo cartel" (capturando el texto real
del cartel vía monkeypatch de `QMessageBox.question`); los dos tests ya
existentes de "con llave asignada no avisa" se actualizan para además
asignarle una placa al profesional (si no, ahora avisarían igual, por
la placa faltante).

Regresión encontrada y corregida en un test PREEXISTENTE, sin relación
directa con este pedido:
`test_crear_reserva_regular_con_conflicto_en_un_dia_sigue_con_los_demas`
mockea `QMessageBox.question` globalmente a "No" para simular que el
operador cancela el cartel de conflicto de un día puntual (Martes),
esperando que Lunes se cree igual. Como el profesional de este test
nunca tenía una placa asignada, el aviso nuevo disparaba SU PROPIO
cartel antes de llegar siquiera al loop de días — y el mismo mock
global de "No" cancelaba ahí la carga completa (ni Lunes ni Martes),
en vez de solo cancelar Martes como pretendía el test. Se corrigió
asignándole una placa al profesional en el setup de ese test, con un
comentario explicando por qué hace falta — verificado además que
ningún otro test de este archivo con el mismo patrón de mock
(`test_crear_reserva_regular_no_resuelve_pedido_si_operador_dice_que_no`,
`test_crear_reserva_aislada_fecha_mes_anterior_pide_confirmacion`)
tiene el mismo problema, por motivos propios de cada uno (ver el código
para el detalle).

## Reservas: solapa nueva "Reserva extraordinaria" (categoría A)

Pedido de la clienta: una tercera solapa en "Reservas" para cargar un
cobro puntual, con un ítem a texto libre y un monto que se tipea a mano,
en vez de calcularse por hora×tarifa — "No es necesario armar PDF, si
estaría bueno un texto tipo reserva aislada con el mismo formato... Se
tiene en cuenta el saldo anterior y los conceptos especiales como
llaves y otros cargos. Afecta la grilla visual en la ocupación como
reserva aislada. Se asigna a un profesional cargado como categoría A."

Antes de implementar se consultaron dos decisiones (`AskUserQuestion`):

- **Modelo de datos**: extender `ReservaAislada` (con un flag + un monto
  manual opcional) en vez de armar una tabla nueva separada — elegida la
  opción recomendada: reusa gratis toda la lógica ya armada de
  conflictos, ocupación de grilla, cancelación y mensaje de detalle de
  aisladas, en vez de duplicarla.
- **Cálculo del monto**: manual (el operador tipea el monto final junto
  con el ítem de texto libre) en vez de seguir calculando por tarifa
  horaria del consultorio — "es justamente lo 'extraordinario': un cargo
  pactado aparte de la tarifa normal".

Investigado antes de diseñar nada: categoría A YA es, en todo el
sistema, la categoría de "reserva aislada" (`_CATEGORIAS_AISLADAS =
("R", "A")` en `reservas.py`, Centro de mensajería filtra "Solo
aisladas" para A) — no es un tipo de profesional nuevo, es la misma
categoría que ya arma `ReservaAislada` y el mensaje de detalle mensual.
Esto es lo que hace viable extender esa misma tabla en vez de inventar
un modelo paralelo.

### Modelo de datos (`ReservaAislada`)

Suma tres columnas: `EsExtraordinaria` (booleano), `ItemExtraordinario`
(texto libre, qué se está cobrando) y `MontoExtraordinario` (el monto
manual). Migración simple vía `_COLUMNAS_NUEVAS` — a diferencia de la
columna `Consultorio` de Gastos operativos (ver la sección de arriba),
acá no hay ningún CHECK que ensanchar, así que alcanza con el mecanismo
genérico de siempre.

### Negocio (`app.negocio.reservas.crear_reserva_aislada`)

Suma tres parámetros opcionales (`es_extraordinaria`/
`item_extraordinario`/`monto_extraordinario`, default `False`/`None`/
`None` — sin efecto para cualquier llamador existente). Con
`es_extraordinaria=True`:
- Valida que el profesional sea categoría A (`ValueError` si no) — único
  guardarraíl nuevo de categoría en toda la función.
- Valida que `item_extraordinario` tenga texto y `monto_extraordinario`
  no sea `None`.
- Ignora `aplica_recargo` (se fuerza a `False` — el monto ya es el final
  a cobrar, el recargo de aisladas no tiene sentido encima de un cargo
  ya manual).
- El resto de la función (validación de fracción de grilla, `verificar_
  conflictos_aislada`, `ConflictoBloqueanteError`/`forzar`) corre
  EXACTAMENTE igual que para cualquier aislada — es lo que le da, gratis,
  el pedido de "afecta la grilla visual... como reserva aislada": sigue
  siendo una fila más de `ReservaAislada` con `Estado='Confirmada'`, así
  que cualquier código que ya lee esa tabla para ocupación/conflictos
  (grilla operativa, Oferta, Novedades, otras reservas) la trata igual
  que cualquier otra, sin ningún cambio en esos módulos.

### Mensaje de detalle (`app.negocio.mensajes.mensaje_detalle_reserva_aislada`)

Mismo mensaje de siempre (DETALLE RESERVA {MES}, editable desde Textos
del sistema) — no se armó ninguna función nueva. La consulta que trae
las `ReservaAislada` del profesional/período ya traía CUALQUIER fila sin
filtrar por `EsExtraordinaria`, así que una extraordinaria ya llegaba
ahí sola; lo único que hacía falta era que no se formateara con la
lógica de `_lineas_reservas_aisladas` (que asume un monto calculado por
hora×tarifa y agrupa por bloques continuos/combinar, algo que no tiene
sentido para un cobro puntual con su propia descripción).

`_lineas_reservas_extraordinarias` (nueva, paralela a
`_lineas_reservas_aisladas` pero mucho más simple): una línea por cada
extraordinaria, SIN agrupar ni combinar nunca (cada una describe un
cobro distinto, fundir dos en una sola línea les haría perder sentido)
— `"+ {día} {fecha} - {ItemExtraordinario} {monto}"`. `del_mes`/
`posteriores` (las dos listas que ya arma la función) se separan en
"normales"/"extraordinarias" ANTES de pasarlas a cada formateador, pero
siguen enteras (sin filtrar) para la "Regla del edificio" de más abajo
— una extraordinaria también cuenta para decidir si hay que mencionar
el edificio. El total de las extraordinarias se suma al de las
reservas normales antes de calcular `SALDO A ABONAR` — así el saldo
anterior, las llaves y los ítems libres se siguen computando exactamente
igual, con la extraordinaria como un componente más, tal como pedía la
clienta ("se tiene en cuenta el saldo anterior y los conceptos
especiales").

### GUI (`app/gui/pantallas/reservas.py`, `_PanelReservaExtraordinaria`)

Tercera solapa de "Reservas" ("Reserva extraordinaria"), deliberadamente
simple — sin grilla de referencia embebida, a diferencia de Reservas
regulares/aisladas (con rondas y rondas de calibración pixel a pixel
documentadas más arriba): un primer armado que no arriesga esa geometría
ya afinada. Columna izquierda de ancho fijo: Profesional (combo buscable,
SOLO categoría A, `_opciones_profesional(conn, ("A",))` — distinto del
combo de Aisladas, que incluye R también), la cascada Localidad→
Edificio→Unidad→Consultorio de siempre, Fecha (mismo formato "día de
semana" que el resto del sistema), horario Desde/Hasta, "Ítem a cargar"
(`QLineEdit` libre) y "Monto a cobrar" (`QDoubleSpinBox`), con "Crear
reserva extraordinaria" (`botonPrimario`) y "Cancelar reserva"
(`botonSecundario`) debajo. Tabla a la derecha: Profesional/Localidad/
Edificio/Unidad/Consultorio/Día/Fecha/Horario/Ítem/Monto/Estado, con
orden por click en el encabezado (`OrdenTabla`) y filtrable por el mismo
combo de Profesional (patrón "Todos los profesionales" de siempre).

`_crear`/`_cancelar` reusan exactamente el mismo flujo que ya tiene
Reservas aisladas (confirmación de fecha de mes anterior, aviso de
llave/placa faltante, `ConflictoBloqueanteError` con reintento
`forzar=True`, `regenerar_snapshot_si_corresponde`) — mismos imports,
sin duplicar ninguna lógica de negocio, solo la UI. Al confirmar (alta o
cancelación), copia al portapapeles el mensaje de detalle actualizado
del profesional — mismo mecanismo (`_copiar_mensaje_detalle`) que ya
usa Aisladas, así que el pedido de "un texto tipo reserva aislada con el
mismo formato" queda cubierto sin necesitar ningún botón "Copiar
mensaje" aparte: ya se copia solo al cargarla.

`_PanelReservasAisladas._valor_reserva` (la tabla de "Reservas
aisladas" de siempre) se ajusta de paso: como una extraordinaria
también es una fila de esa tabla (sin filtrar en ningún lado), su
columna "Valor" mostraba un cálculo de hora×tarifa que no reflejaba lo
que de verdad se cobra — ahora, si `EsExtraordinaria`, muestra
`MontoExtraordinario` directo.

Tests nuevos: `tests/test_reservas.py` (`crear_reserva_aislada` con
`es_extraordinaria=True` — se guarda con el monto manual, rechaza
categoría distinta de A, rechaza sin ítem, rechaza sin monto, genera el
mismo conflicto bloqueante que cualquier aislada contra otro
profesional); `tests/test_mensajes.py` (el detalle usa el monto manual
y el ítem de texto libre, convive con una aislada normal en el mismo
mes, una posterior va a su propia sección sin sumarse al saldo del
período actual); `tests/test_migraciones.py` (una base vieja de
`ReservaAislada` gana las tres columnas sin perder las filas ya
cargadas); `tests/test_gui_reservas.py` (la solapa existe con el combo
acotado a categoría A, crear guarda y copia el mensaje al portapapeles,
sin ítem o sin monto no crea nada, cancelar funciona, y la fila también
se ve en la tabla de "Reservas aisladas" con el monto manual en su
columna "Valor").

### Segunda vuelta: botón "Modificar reserva" en la solapa nueva

Pedido de la clienta, con tres puntos sobre la ronda anterior:

- **Capturas de las tres solapas completas**: confirmado que el
  mensaje de detalle de una extraordinaria ya se copiaba solo al
  portapapeles al crearla (mismo mecanismo `_copiar_mensaje_detalle`
  que Aisladas, documentado arriba) — se le mandó un ejemplo del texto
  real para que lo viera: una línea con el ítem de texto libre,
  conviviendo con una aislada común y el saldo anterior, todo sumado en
  el mismo "SALDO A ABONAR" final.
- **"Que cada vez que se cree, modifique o cancele... genere o
  regenere ese texto"**: en "Reservas aisladas" ya pasaba así (Crear/
  Modificar/Cancelar llaman los tres a `_copiar_mensaje_detalle`,
  `test_modificar_reserva_aislada_al_confirmar_regenera_mensaje_al_
  portapapeles` ya lo cubría desde antes de esta vuelta) — sin cambios
  ahí. "Reserva extraordinaria" solo tenía Crear/Cancelar (ambos ya
  copiaban), le faltaba un "Modificar" propio: se sumó `boton_
  modificar`/`_modificar_seleccionada` (`_PanelReservaExtraordinaria`),
  mismo patrón exacto que `_PanelReservasAisladas` — cancela la
  seleccionada (que ya copia el mensaje sin ella, vía el `_cancelar_
  registro` compartido que ahora usan `_cancelar`/`_modificar_
  seleccionada` de este panel) y precarga el formulario con sus datos
  (profesional, ubicación, fecha, horario, ítem, monto) para que el
  operador ajuste y confirme con "Crear reserva extraordinaria" —ese
  clic vuelve a copiar, ya con la versión corregida.

Tests nuevos en `tests/test_gui_reservas.py`:
`test_modificar_reserva_extraordinaria_cancela_la_vieja_y_precarga_el_
formulario`, `test_modificar_reserva_extraordinaria_sin_seleccion_
avisa`, `test_modificar_reserva_extraordinaria_copia_mensaje_de_
detalle_al_portapapeles`.

### Tercera vuelta: bordes de los tres botones cortados contra el panel

Pedido explícito de la clienta sobre la captura de la ronda anterior:
"Crear reserva extraordinaria"/"Modificar reserva"/"Cancelar reserva"
se veían con el borde derecho cortado. Causa real, medida con un script
de geometría: `panel_form` (el contenedor de toda la columna izquierda)
tiene ancho fijo `_ANCHO_PANEL_FILTROS_GRILLA` (290), pero su
`QVBoxLayout` se queda con el margen default de Qt (9px por lado) —
el ancho de CONTENIDO real es 290 - 9 - 9 = 272 (confirmado contra
`combo_profesional`, que ya se dimensionaba bien a ese ancho). Los tres
botones, en cambio, se fijaban al ancho TOTAL del panel (290, el mismo
que `panel_form`) en vez de al de contenido — su borde derecho quedaba
9px más allá del borde del propio panel, cortado contra él.

`_ANCHO_BOTON_EXTRAORDINARIA = _ANCHO_PANEL_FILTROS_GRILLA - 18`
(constante nueva, puntual de esta pantalla) reemplaza a
`_ANCHO_PANEL_FILTROS_GRILLA` en los tres `setFixedWidth` de los
botones — confirmado con el mismo script que los tres terminan exacto
en el mismo borde derecho que `combo_profesional` (x=281), bien
adentro del ancho de `panel_form` (290).

## Cuarta tanda de correcciones post-v1: Reservas (las tres solapas) + reglas generales

Lista grande de pedidos sobre "Reservas" (Reservas regulares/Reservas
aisladas/Reserva extraordinaria), más dos pedidos "EN GENERAL" que
arrancan como reglas nuevas. Mismo criterio de toda esta serie de
tandas: se implementa, se investiga lo que hay que investigar (algunos
puntos eran "fijate si entendés a qué me refiero", no pedidos de
arreglo puntual), se corren pyflakes y la suite completa, y la nueva
versión no se larga hasta que la clienta lo pida.

### Orden de Unidad (PB/EP/piso ascendente) en los selectores del sistema

Mismo bug en dos lugares: tanto `reservas.py::_opciones_unidad` (un solo
edificio ya elegido) como `catalogos.py::_opciones_unidad`/
`_opciones_consultorio` (sin edificio fijo, listan todas) ordenaban
`Departamento` alfabéticamente por SQL — "EP" quedaba antes que "PB", y
un piso de dos dígitos (ej. "10mo") se intercalaba mal contra uno de un
dígito. La grilla embebida (`grilla_operativa.py`) ya resolvía esto
correctamente con `clave_orden_unidad` (de `app.pdf.estilos`, ya
existente) desde antes — las dos funciones de arriba pasan a ordenar en
Python con esa misma clave en vez de depender del `ORDER BY` de SQL.
En `catalogos.py`, que lista TODAS las unidades/consultorios del
sistema sin acotar a un edificio, la clave pasa a ser compuesta
(`(Edificio, clave_orden_unidad(Departamento))`) para no mezclar pisos
de edificios distintos entre sí — error que se corrigió en el diseño,
antes de escribirlo, no después de un test fallido.

Quedó pendiente (mismo patrón, no corregido en esta tanda por acotar el
alcance): `llaves.py`, `balance.py`, `imagenes.py`, `estadisticas.py`,
`aumentos.py` tienen el mismo `ORDER BY Departamento` sin pasar por
`clave_orden_unidad` — se arreglan la próxima vez que se revise alguna
de esas pantallas.

### Indicador de foco visible en checks y combos (estilos.py)

La regla general de foco (`QPushButton:focus { outline: ...}`, ver más
arriba en este documento) había quedado deliberadamente acotada a
`QPushButton` porque `outline` no se pinta en otros tipos de widget en
este Qt. Pedido explícito de la clienta sobre Reservas ("no veo en los
cheks... por ejemplo"): se suma `border` reservado (2px transparente en
reposo, color real en :focus, para no correr el contenido de
alrededor) a `QComboBox` y `QCheckBox`. Comprobado con captura real +
muestreo de píxeles (mismo criterio que el resto de este documento): el
combo mostraba un botón nativo (click normal, sin estilo propio) antes
de este cambio — agregar `border` no le cambió el look en reposo, solo
sumó el anillo al enfocar.

Investigado aparte: por qué solo mencionó "checks" y no "botones" (los
botones YA tenían el anillo desde la ronda de "Indicador visual de
foco" original) — comprobado con un script que los botones de Reservas
(incluidos los compactos, con `setStyleSheet("padding: 3px 16px;")`)
SÍ muestran el anillo correctamente; el override puntual de padding no
pisa la regla `:focus` global. No se encontró ningún bug ahí — el pedido
real era sobre checks/combos, cubierto arriba.

Suite de regresión corrida contra los ~15 archivos de tests de GUI más
sensibles a geometría (incluida toda la batería de Reservas/Oferta,
calibrada pixel a pixel en rondas anteriores): sin cambios, el border
reservado de 2px no corrió nada de lo ya afinado.

### Reservas regulares: wordWrap en las etiquetas de resumen, Tab no se salta "Día de la semana"

- **"Cantidad de horas regulares semanales" se veía cortado**:
  `etiqueta_horas_semanales`/`etiqueta_descuento` (Regulares) y
  `etiqueta_horas_aisladas` (Aisladas) suman `setWordWrap(True)` — sin
  esto, un texto más largo que la columna no se recortaba de forma
  visible en el layout pero podía quedar tapado por el panel de al lado
  o cortado contra el borde de la ventana; con wrap pasa a una segunda
  línea en vez de desbordar.
- **Tab salteaba "Filtro de día de la semana" entre Unidad y Profesional**:
  investigado a fondo, el bug es real y tiene una causa concreta. El
  panel de Filtros de la grilla embebida (Localidad/Edificio/Unidad/Día
  de la semana/Profesional) nunca tuvo una cadena explícita de
  `instalar_enter_avanza_foco` — dependía del orden nativo de Tab de
  Qt. `GrillaOperativaWidget.agrupar_dias_en_pares()` (pedido de una
  ronda anterior, pasa los checks de día a una grilla de 2 columnas)
  reparenta esos checks a un contenedor NUEVO después de construido el
  resto del panel — Qt los reinserta al FINAL de la cadena nativa en vez
  de mantenerlos en su lugar, así que Tab desde "Filtro de unidad" caía
  directo en "Profesional". Se corrige con un método nuevo,
  `GrillaOperativaWidget.widgets_filtro_para_foco()` (devuelve, en
  orden visual, los botones-resumen de los tres filtros colapsables —
  `_FiltroColapsable.foco_widget()`, no la lista interna que arranca
  oculta —, cada check de día y el combo de Profesional), que Reservas
  (las dos solapas con grilla embebida) usa para armar una cadena de
  foco PROPIA de ese panel, separada de `self._foco` (el formulario de
  alta, que vive en otra columna con otro propósito). Confirmado con
  `QTest.keyClick` real, no solo revisando el código.

### Referencias de colores: borde cortado — investigado, sin reproducir

Pedido de "fijate si entendés a qué me refiero" sobre el borde de los
cuadraditos de "Referencias de colores" (se veía con el borde exterior
cortado, según la clienta). Investigado con captura real + pixel a
pixel (`_CeldaGrilla.paintEvent`/`_dibujar_bordes_gruesos`, que dibuja
un borde gris fino de 1px en las 4 caras de cada swatch, sin relación
con `bordes` — siempre se dibuja): en este entorno, CUALQUIER swatch
probado (simple y con triángulo divisor) muestra un rectángulo cerrado,
sin corte en ningún lado. No se encontró ningún código que pudiera
producir el defecto descripto — puede ser específico del renderizado
real (Windows/DPI) o de la captura que la clienta estaba mirando; si
persiste en la instalación real, hace falta una captura de pantalla
puntual para poder reproducirlo acá.

### Líneas de la grilla que varían según la consulta — explicación, no pedido de arreglo

La clienta aclaró explícitamente que esto era una pregunta ("fijate y
comentame si te das cuenta de qué estoy hablando"), no un pedido de
arreglar un caso puntual (con datos propios que no se pueden ver desde
acá). Respuesta: sí, se entiende a qué se refiere, y es el
comportamiento ESPERADO, no un bug — `_dibujar_bordes_gruesos`
(`grilla_operativa.py`) pinta tres grosores/colores distintos según
qué tipo de límite cae en cada borde de celda:

- **Fina gris (`#999999`, 1px)**: la cuadrícula de siempre, en las 4
  caras de CUALQUIER celda — la línea "default" que separa cualquier
  par de celdas vecinas sin ningún límite especial entre medio.
- **Media (`_COLOR_LINEA_UNIDAD`, un gris más oscuro, 2px)**: separa dos
  UNIDADES distintas dentro del mismo día (ej. el consultorio 3 del
  "7mo" contra el consultorio 1 del "9no", si ambos aparecen uno al
  lado del otro en la grilla) — sumada en la tanda anterior
  ("Grilla semanal: scroll horizontal, colores de líneas..."). También
  separa la fila "Día de la semana" del resto de las filas de
  encabezado.
- **Gruesa negra (3px)**: separa DÍAS distintos (el límite entre, por
  ejemplo, martes y miércoles) y encierra el bloque de encabezado.

El ejemplo puntual que dio la clienta (línea vertical entre los
consultorios 3 y 4 del "7mo" los martes) sería, con ese criterio, una
línea MEDIA si consultorio 3 y 4 pertenecen a UNIDADES distintas (ej.
"7mo A" y "7mo B" cargadas como dos filas de `Unidad` separadas, aunque
compartan el mismo texto "7mo" en el nombre visible) — es información
real sobre la estructura de datos, no un error de dibujo. Lo que SÍ
puede variar "según la consulta" (lo que la clienta notó) es que, al
cambiar los filtros de Localidad/Edificio/Unidad de la grilla, cambia
QUÉ columnas quedan una al lado de la otra — un consultorio que hoy
tiene al lado uno de la MISMA unidad (línea fina) puede, con otro
filtro aplicado, terminar al lado de uno de OTRA unidad (línea media) o
de otro DÍA (línea gruesa), simplemente porque cambió su vecino
inmediato en la grilla resultante. No hay ningún código que decida el
grosor "al azar" ni que dependa de qué profesional está seleccionado —
depende únicamente de qué dato cae al lado de cuál en cada consulta
puntual.

### Reservas aisladas: "Cancelar reserva" cortado — investigado, sin reproducir

Capturado con datos mínimos en 1500×800 y 1366×768 (tamaños de ventana
reales, con `hoja_estilos()` aplicada): en los dos casos "Cancelar
reserva" se ve completo, dentro del panel, sin recorte. El mecanismo de
alto de esta solapa (`scroll.setFixedHeight(contenido.
minimumSizeHint().height())`, con la tabla de abajo llevándose el resto
vía `stretch=1`) ya está diseñado para que el formulario de arriba
nunca empuje a los botones fuera de la vista. No se pudo reproducir con
los tamaños de ventana probados — puede depender del tamaño real de la
ventana de la clienta o de datos cargados que alarguen el formulario de
otra forma; si persiste, hace falta su tamaño de ventana real (o una
captura) para reproducirlo con precisión.

### Scrollbars: solo la que hace falta, nunca una de más tapando contenido

Pedido explícito, "en todos los formularios del sistema": la grilla
embebida tiene que verse entera cuando entra sin necesitar scroll
vertical, y cuando sí necesita scroll horizontal (muchos consultorios),
esa barra no tiene que "tapar" la última fila ni disparar un scroll
vertical de más que no haría falta si la barra no estuviera ahí.

Investigado antes de tocar nada: el mecanismo que resuelve exactamente
este problema ya existía — `GrillaOperativaWidget.reservar_alto_scroll_
horizontal()` (sumado en la revisión de Oferta de consultorios, séptima
vuelta: "dale más largo para que el scroll horizontal no tape lo
último que se tendría que ver de la grilla") suma al alto mínimo de la
tabla el espacio real que el estilo activo le da a una barra de scroll
horizontal (`QStyle.PM_ScrollBarExtent`) — sin esto, el viewport mide
justo la suma de las filas, y la barra, al aparecer, le come ese mismo
alto, tapando la última fila (y con ella, en los casos más ajustados,
obligando a un scroll vertical que no haría falta si el espacio ya
estuviera reservado de entrada).

El mecanismo es opt-in (no afecta a ningún otro uso de esta grilla
compartida) y, confirmado por búsqueda antes de este pedido, solo lo
llamaban `_PanelGrillaSemanal` ("Grilla y mensajería") y `_PanelOferta`
("Disponibilidad") — las dos solapas de Reservas y las tres de
Registro de ausencias nunca lo habían sumado, pese a embeber la misma
grilla y poder necesitar scroll horizontal con una base de muchos
consultorios. Se suma la misma llamada, en el mismo lugar (justo
después de `activar_filas_y_columnas_fijas()`), en los cinco paneles
que todavía no la tenían: `_PanelReservasRegulares`/`_PanelReservasAisladas`
(`reservas.py`) y `_PanelVacaciones`/`_PanelLicencias`/`_PanelAusencias`
(`novedades.py`) — sin tocar nada del mecanismo en sí, que ya estaba
cubierto a fondo por sus propios tests en `test_gui_grilla_operativa.py`.

Tests nuevos: `test_grillas_de_reservas_reservan_alto_para_el_scroll_
horizontal` (`test_gui_reservas.py`) y `test_grillas_de_registro_de_
ausencias_reservan_alto_para_el_scroll_horizontal` (`test_gui_
novedades.py`) — mismo criterio que el test ya existente de
`activar_filas_y_columnas_fijas()` en cada archivo: confirman el flag
`_reservar_alto_scroll_horizontal is True` en las solapas que
corresponda, sin repetir la verificación del mecanismo en sí.

### Reserva extraordinaria: renombre a plural, categoría R además de A, Modificar reserva arreglado, orden por fecha

- **Solapa renombrada** "Reservas extraordinarias" (antes "Reserva
  extraordinaria", singular).
- **Categoría R además de A** (pedido explícito, segunda vuelta sobre
  esta funcionalidad — ver más arriba la sección original "Reservas:
  solapa nueva 'Reserva extraordinaria' (categoría A)"): "le puedo
  hacer abrir por medio de otro profesional"/cobros puntuales fuera de
  tarifa también les pasan a los R, y a diferencia de A (sin
  liquidación mensual propia) SÍ pueden afectar una `LiquidacionEmitida`
  ya generada. El guardarraíl de categoría que tenía
  `crear_reserva_aislada` (`"Una reserva extraordinaria solo se puede
  asignar a un profesional categoría A"`) pasa a aceptar A o R.
  - Label del combo pasa de "Profesional (categoría A)" a "Profesional"
    a secas.
  - Orden del combo: A primero (código natural ascendente — A2, A3,
    A21, A23...), R después (mismo criterio ascendente) — `_opciones_
    profesional_extraordinaria` (nueva, `reservas.py`), DISTINTA de la
    jerarquía global B/R/A/E/X/C que usa `_opciones_profesional` para
    el resto del sistema (ahí R va antes que A) — acá el pedido
    explícito de la clienta invierte ese orden para este combo
    puntual.
  - **"Período a imputar"** (combo nuevo, "Período actual (el de la
    fecha cargada)"/"Período siguiente"): oculto por default, visible
    SOLO cuando el profesional elegido es categoría R
    (`_al_cambiar_profesional`/`_es_profesional_r`). Respuesta de la
    clienta a la pregunta de qué hacer con una liquidación ya emitida:
    "si se imputa al mismo período de la liquidación, la rehace y la
    marca como no enviada. Si la imputa para el período siguiente, no
    toca la liquidación del mes, se contempla ese punto para la
    liquidación del mes siguiente." — "Período siguiente" no necesita
    ningún código: `calcular_liquidacion` ya suma, para cualquier
    período, tanto las aisladas del mes en curso como las del mes
    ANTERIOR (`aisladas_mes_anterior`/`aisladas_mes_en_curso`), así que
    una extraordinaria fechada este mes entra sola en el cálculo del
    mes siguiente sin tener que mover ni marcar nada ahora. "Período
    actual" reusa `regenerar_si_corresponde` (`app.negocio.
    liquidaciones`, la misma función que ya usan las reservas
    regulares, DC-08 §3.7) — resuelve el profesional liquidable,
    reemite la liquidación de ese período (si no se puede, ej. ya hay
    períodos posteriores emitidos, no rompe la carga de la reserva) y
    `emitir_liquidacion` ya deja sola la marca "Regenerada no enviada"
    si la última emisión de ese período ya estaba Enviada (DC-09
    §2.1/2.2) — no hace falta llamar a `marcar_estado_envio` aparte.
  - **Bug real encontrado al abrir esto a R, no pedido explícitamente
    pero necesario para que los números cierren**: `_aisladas_periodo`
    (`app.negocio.liquidaciones`, la función que arma el desglose de
    aisladas de una liquidación) calculaba el monto de CUALQUIER
    `ReservaAislada` con hora×tarifa, sin mirar `EsExtraordinaria` —
    hubiera ignorado el monto manual cargado a mano apenas un R
    tuviera una extraordinaria (bug latente desde que se armó la
    funcionalidad para A, nunca alcanzable en producción porque A no
    tiene liquidación mensual propia). Corregido: usa
    `MontoExtraordinario` cuando `EsExtraordinaria` es verdadero, sin
    aplicar el recargo de aisladas (mismo criterio que `crear_reserva_
    aislada`, que ya fuerza `AplicaRecargo=False` para estas). `ItemAislada`
    suma un campo `item_extraordinario` (opcional, default `None`) para
    que el PDF pueda describir el cargo — `_texto_aislada` (`liquidacion_
    pdf.py`) usa ese ítem en vez de "Hora aislada trabajada/a trabajar"
    cuando corresponde.
- **"Modificar reserva" arreglado** (bug reportado por la clienta: "no
  me permite editar... es mas la cancela"): investigado, el mecanismo
  en sí (cancelar la vieja + precargar el formulario con sus datos, el
  mismo criterio que usan las otras dos solapas desde que se armó esta
  funcionalidad) YA funcionaba correctamente — confirmado con un test
  que verifica la precarga campo por campo. El problema era de
  PERCEPCIÓN: el único efecto visible de clickear "Modificar reserva"
  era que la fila pasaba a "Cancelada" en la tabla, sin ningún aviso de
  que el formulario quedó precargado y hay que volver a tocar "Crear
  reserva extraordinaria" para guardar la versión corregida — desde la
  pantalla, parecía que el botón solo cancelaba. Se agrega un
  `QMessageBox.information` explícito después de la precarga,
  aclarando los dos pasos.
- **Orden por fecha ascendente** (pedido explícito: "las reservas
  tienen que aparecer por orden de fecha, lo mas próximo arriba"): el
  orden por defecto de la tabla pasa de descendente (la fecha más
  lejana primero) a ascendente.

### Campos de monto: separador de miles + select-all al enfocar (todo el sistema)

Pedido puntual sobre "Monto a cobrar" de Reserva extraordinaria,
extendido explícitamente a "todos los cuadros de texto similares del
sistema". El patrón `_SpinMonto`/`_SpinMoneda` (QDoubleSpinBox que se
muestra como moneda vía `formatear_moneda`, "$ 1.234,56") ya existía,
duplicado por pantalla (Pagos, Configuración general) — las dos
clases existentes suman `focusInEvent` con `QTimer.singleShot(0,
self.selectAll)` (mismo mecanismo ya usado por el selector de
profesional: un `selectAll()` inmediato durante el propio evento de
foco queda pisado por el reposicionamiento nativo del cursor que hace
Qt justo después de un click).

- `reservas.py` suma su propia `_SpinMonto` (mismo patrón, duplicado
  acá) y la usa para "Monto a cobrar" de Reserva extraordinaria — antes
  un `QDoubleSpinBox` liso, sin formato de moneda ni select-all.
- `llaves.py` NO duplica una tercera vez — importa `_SpinMonto` de
  `reservas.py` (mismo criterio de import cruzado que ya usa este
  archivo para `_opciones_profesional`/`_texto_profesional`) y la usa
  para "Depósito actual"/"Monto cobrado"/"Monto a reintegrar" (antes
  tres `QDoubleSpinBox` lisos, sin formato de moneda).

### Selectores de fecha: semana empieza en lunes (todo el sistema)

`QLocale(QLocale.Language.Spanish)` ya tiene `firstDayOfWeek() ==
Monday` por default (criterio ISO) — `gui_main.main()` suma `QLocale.
setDefault(QLocale(QLocale.Language.Spanish))` (junto a `app.setFont(...)`,
antes de mostrar cualquier pantalla) para que CUALQUIER `QDateEdit` del
sistema (su calendario emergente incluido) herede este comportamiento
sin tener que tocar cada instancia una por una — las pantallas que ya
llamaban `.setLocale(_LOCALE_ES)` a mano (Registro de ausencias,
Reservas) no cambian de comportamiento, es el mismo locale.

### Reserva extraordinaria: texto generado con horario y consultorio/unidad

`_lineas_reservas_extraordinarias` (`app.negocio.mensajes`) armaba la
línea del mensaje de detalle con día, fecha, ítem y monto nomás — sin
decir CUÁNDO (horario) ni DÓNDE (consultorio/unidad) pasó el cargo,
distinto de cualquier aislada común. Pedido explícito de la clienta:
"mismo formato". Suma los mismos tres parámetros y el mismo helper
(`_lugar_reserva`) que `_lineas_reservas_aisladas`, para que el
criterio de qué mostrar (incluir o no consultorio/unidad/edificio) sea
idéntico entre las dos — la línea pasa de `"+ {día} {fecha} - {ítem}
{monto}"` a `"+ {día} {fecha} de {horario} {lugar} - {ítem} {monto}"`.

### Mensajes generados: espacio antes de una línea que empieza con "-" (todo el sistema)

Pedido explícito, no un bug del sistema sino una corrección para cómo
WhatsApp Web interpreta el texto: un "-" al principio de línea lo toma
como una llamada/viñeta/formato propio en vez del carácter literal.
`sustituir_variables` (`app.negocio.plantillas_texto` — la ÚNICA
función que arma el texto final de TODO mensaje editable del sistema:
los 9 slots de "Textos del sistema" y `MensajePredefinido`) suma, como
último paso, después de reemplazar las `{variable}`: cualquier línea
del resultado que empiece con "-" (el texto de fábrica, el de una
variable sustituida, o el de una plantilla personalizada por la
clienta) suma un espacio adelante. Un único cambio, en el choke-point
compartido por todos los mensajes, cubre automáticamente cualquier
mensaje actual y futuro construido sobre este mecanismo, sin tener que
tocar cada función de armado (`mensaje_situacion_*`, `mensaje_grupal`,
`oferta_busqueda_whatsapp`, etc.) una por una.

### EN GENERAL: diálogo de confirmación antes de crear una reserva

Pedido explícito: "cuando se crea una reserva... un alerta previo con
los datos que se van a cargar para confirmar o cancelar, si uno cancela
siguen los datos cargados". Segunda parte del pedido ("mismo
comportamiento para todo, crear un edificio, agregar a profesional,
etc., para todo el sistema") — consultada la clienta sobre el alcance,
eligió la opción recomendada: "pantalla por pantalla, a medida que las
revisás", no un barrido de todo el sistema de una sola vez.

`confirmar_datos_antes_de_crear(parent, titulo, lineas)` (nueva,
`app/gui/dialogos.py`, al lado de `confirmar_si_fecha_es_mes_anterior`/
`confirmar_si_periodo_imputado_es_anterior` — mismo criterio de
"diálogos de confirmación reusados entre varias pantallas"): arma un
`QMessageBox.question` con la vista previa (una línea por dato) y
devuelve `True`/`False` según la respuesta — no toca el formulario, esa
responsabilidad queda del lado de quien llama (si cancela, el llamador
simplemente no limpia nada, a diferencia del camino de éxito que sí
resetea el formulario al final).

Conectado en las tres solapas de Reservas, al final de la cadena de
validaciones/avisos de cada `_crear()` (después de "fecha de mes
anterior" y "llave/placa faltante", justo antes de la creación real) —
mismo criterio que esos otros chequeos: una sola vez por submit, no
repetido en el reintento automático con `forzar=True` después de un
`ConflictoBloqueanteError`. Cada solapa arma su propia lista de líneas
(Profesional, ubicación, días/fecha, horario, y los campos propios de
cada una — vigencia para Regulares, recargo/reubicación para Aisladas,
ítem/monto/período a imputar para Extraordinaria).

Tests de regresión: varios tests ya existentes que monkeypatcheaban
`QMessageBox.question` para simular SOLO el cartel de llave/placa (o
SOLO el de conflicto bloqueante) con una respuesta única necesitaron
distinguir por TÍTULO del cartel (`"Falta llave o placa"` vs.
`"Crear reserva regular"`/etc.) en vez de asumir una sola llamada en
total — el nuevo cartel se suma a la cadena, no la reemplaza. Tests
nuevos por solapa confirman que cancelar no crea nada y deja el
formulario intacto (profesional/ítem/monto siguen cargados), y que
confirmar sigue creando como siempre.

## Reservas (las tres solapas): batch completo (#9.1.x del documento)

Décima tanda de `v0.11.2026.10`, cerrando la cuarta sección del
documento ("RESERVAS"). Las tres solapas (Reservas regulares/aisladas/
extraordinarias) comparten el mismo set de puntos — `reiniciar()`/
`showEvent` (1.4, ya cumplido desde una ronda anterior en las tres),
`excluir_tabla_del_tab` (1.5, ídem), foco visible en combos/checks
(1.7, ídem), líneas de grilla sin doble efecto (1.8, exclusivo de
Regulares/Aisladas, que embeben la grilla), `regenerar_si_corresponde`
tras cualquier recálculo del período actual (1.9, ya cumplido), fecha
con día de semana (1.10, ya cumplido), sábado en negro (1.13, ya
cumplido) — así que esta tanda se concentró en los puntos propios de
cada solapa que SÍ faltaban: diálogo de edición en vez de "cancela y
precarga" (#9.1.4), confirmación explícita antes de cancelar/eliminar
(#9.1.6), botones deshabilitados sin selección (1.11/EN GENERAL, ya
aplicado en el resto del sistema), y varios ajustes puntuales de cada
solapa.

### Reservas regulares

- **`eliminar_reserva_regular` (nueva, `app.negocio.reservas`)**: el
  botón pasa de "Finalizar reserva a fin de mes" (pone `VigenciaFin`,
  conserva la fila) a "Eliminar reserva" — BORRA la fila por completo.
  Mismo guardarraíl de período cerrado que el resto del módulo
  (`_validar_vigencia_no_cerrada` sobre `VigenciaInicio` de la fila):
  no se puede eliminar una reserva cuya vigencia ya haya sido usada por
  una liquidación posterior, porque eso desalinearía esa liquidación
  sin dejar ningún rastro al que una futura revisión pudiera recurrir.
- **`modificar_reserva_regular` (nueva) + `_DialogoModificarReservaRegular`
  (GUI)**: punto #9.1.4 — "Modificar reserva" deja de finalizar la fila
  vieja y precargar el formulario de alta (que daba la impresión de
  solo cancelarla, sin dejar en claro que quedaba algo pendiente de
  confirmar) y pasa a un diálogo propio que edita Horario/Vigencia de
  la fila EXISTENTE, dejándola corriendo con la modificación aplicada.
  Profesional/Consultorio/Día se muestran de solo lectura (cambiarlos
  es, en los hechos, dar de alta una reserva distinta). "Si quiero la
  termino desde el cuadro de diálogo" — alcanza con poner una Vigencia
  hasta real en vez de dejarla en "(sin fecha)", sin ningún control
  aparte. Mismos guardarraíles que `crear_reserva_regular`: ninguna
  vigencia (la vieja de la fila NI la nueva) puede caer en un período
  ya cerrado, y la superposición contra otra reserva se vuelve a
  chequear con `excluir_id` para no comparar la fila contra sí misma.
- Botones "Modificar reserva"/"Eliminar reserva" deshabilitados sin
  fila seleccionada (`self.boton_modificar`/`self.boton_eliminar`,
  antes variables locales).
- Alerta de éxito explícita ("Reserva cargada con éxito.") cuando
  "Crear reserva regular" termina sin ningún aviso — antes el único
  camino "silencioso" (sin avisos de conflicto) no mostraba ningún
  cartel, dejando la duda de si de verdad se había guardado.
- `wordWrap(True)` en las etiquetas de resumen ("Cantidad de horas
  regulares semanales"/"% Descuento") — un texto más largo que la
  columna quedaba tapado por el panel de al lado o cortado contra el
  borde de la ventana en vez de pasar a una segunda línea.
- Foco: "Filtro de día de la semana" (panel de Filtros de la grilla
  embebida) dejaba de estar en la cadena nativa de Tab entre "Filtro de
  unidad" y "Profesional" — causa real: `agrupar_dias_en_pares()`
  reparenta esos checks a un contenedor nuevo DESPUÉS de construido el
  resto del panel, y Qt los reinserta al final de la cadena nativa.
  `GrillaOperativaWidget.widgets_filtro_para_foco()` (nueva) devuelve,
  en orden visual, los botones-resumen de los filtros colapsables +
  cada check de día + el combo de Profesional, para que Reservas (las
  dos solapas con grilla embebida) arme su propia cadena explícita
  sobre ese panel en vez de depender del orden nativo.

### Reservas aisladas

- **`modificar_reserva_aislada` (nueva, `app.negocio.reservas`) +
  `_DialogoModificarReservaAislada` (GUI)**: homólogo de Regulares,
  pero armado desde el principio para servir TAMBIÉN a Extraordinarias
  (que son `ReservaAislada` con `EsExtraordinaria=True`) — el diálogo
  muestra "Aplica recargo" (checkbox) para una aislada común, o "Ítem a
  cargar"/"Monto a cobrar" para una extraordinaria, según
  `reserva["EsExtraordinaria"]`, sin duplicar ningún código entre las
  dos solapas. Mismos guardarraíles de conflicto que
  `crear_reserva_aislada` (con `excluir_id` para no chocar contra sí
  misma).
- **"Cancelar reserva" pide confirmación explícita** (#9.1.6, antes
  cancelaba directo sin preguntar nada): `QMessageBox.question` con el
  profesional, día de semana y horario de la reserva seleccionada.
- **Columna "Período imputado" (`ReservaAislada.PeriodoImputado`,
  columna nueva en el schema)**: se guarda ya resuelto a "AAAA-MM" (no
  "actual"/"siguiente" tal cual viene del combo) al crear la reserva —
  `_resolver_periodo_imputar` (compartida con Extraordinarias) sigue
  siendo la que decide el efecto real sobre la liquidación
  (`regenerar_si_corresponde` si es el período actual, nada si es el
  siguiente — ese caso se resuelve solo cuando `calcular_liquidacion`
  llegue a ese mes), la columna de la tabla es puramente informativa.
- **Foco: "Período a imputar" no se saltea para categoría R.** Faltaba
  por completo de la cadena de `self._foco` — pedido explícito de la
  clienta: "si elijo un profesional categoría R el foco desde el
  selector del profesional pasa al 'Período a imputar', no lo saltea".
  Al estar deshabilitado para A/B (`_al_cambiar_profesional`),
  `instalar_enter_avanza_foco` ya lo saltea sola sin necesitar ninguna
  condición extra.
- **"Aplica recargo"/"Es reubicación" en una sola fila**, con el texto
  del segundo acortado (sin el salto de línea manual que tenía antes)
  — entran los dos lado a lado sin necesitar wrap.
- **Botones de acción al mismo alto que Regulares** (22px,
  `_ESTILO_BOTON_COMPACTO`) — antes tenían su propio estilo más alto
  (`_ESTILO_BOTON_AISLADAS_ALTO`, pensado para alinear "Horas aisladas
  mensuales" con el pie del tercer botón en una ronda anterior); con el
  nuevo criterio de esta tanda (parejo con Regulares) ese estilo pasa a
  ser un alias del compacto.
- **Tabla ensanchada** (`_ajustar_columnas`, mismo padding que
  `novedades._ajustar_columnas`) en vez del ancho justo de
  `resizeColumnsToContents()`.
- **Botones "Modificar reserva"/"Cancelar reserva" deshabilitados sin
  selección** (`_actualizar_botones`, conectado a `tabla.
  itemSelectionChanged`).
- **Leyenda de colores con letra un poco más chica** (`fijar_tamano_
  fuente_leyenda(9)`, un punto por debajo del 10px default de
  `hacer_compacta()`) — pedido puntual de esta ronda para que las
  referencias no salgan apelmazadas.
- **"Detalle" retocado con mejor esfuerzo, documentado como límite
  aceptado**: `_ALTO_DETALLE_AISLADAS` se volvió a medir contra el
  nuevo criterio (alinear con el pie del tercer botón, ya no con
  "Horas aisladas mensuales") — medido SIN `hoja_estilos()` da un
  ajuste exacto, pero con el estilo real aplicado (lo que la clienta
  realmente ve) queda un resto de entre 16 y 34px que esta única
  constante no puede cerrar, porque el tamaño de fuente real se
  propaga de forma no lineal por el resto de la columna. Se dejó el
  valor medido (igual de válido que cualquier otro en ese rango) y se
  ensanchó la tolerancia del test de regresión en vez de perseguir un
  ajuste pixel-perfect inalcanzable bajo la plataforma `offscreen` de
  los tests — mismo criterio ya documentado para otros casos
  "investigado, sin reproducir del todo" de este archivo.

### Reservas extraordinarias

Mismo patrón que Aisladas, reusando directamente sus piezas genéricas
(`_DialogoModificarReservaAislada`/`modificar_reserva_aislada`, ya
armados para soportar `EsExtraordinaria` desde el principio) en vez de
duplicar nada:

- **"Modificar reserva" deja de cancelar y precargar el formulario.**
  Antes, al no poder editar in-place, cancelaba la fila seleccionada y
  precargaba el formulario con sus datos para dar de alta la versión
  corregida — pedido de la clienta sobre ese comportamiento ("no me
  permite editar... es mas la cancela") había llevado, en una ronda
  anterior, a sumar un cartel explicando el mecanismo; esta ronda lo
  reemplaza directamente por edición in-place, mismo criterio que
  Regulares/Aisladas. El método `_seleccionar_ubicacion` de este panel
  (que solo existía para precargar la cascada de ubicación en el
  mecanismo viejo) queda sin ningún uso y se borra.
- **"Cancelar reserva" pide confirmación explícita**, mismo mecanismo
  que Aisladas (profesional/día/horario/ítem en el texto del cartel).
- **Columna "Período imputado"** agregada a la tabla (al final, mismo
  criterio que Aisladas) — hueco real detectado al escribir el primer
  test: `_crear()` nunca pasaba `periodo_imputado=` a `crear_reserva_
  aislada` (a diferencia de Aisladas, que sí lo hacía desde la ronda
  anterior), así que la columna quedaba siempre en blanco. Corregido
  sumando el mismo cálculo (`fecha[:7]` si es "actual", `sumar_meses(
  fecha[:7], 1)` si es "siguiente") al llamado.
- **Botones "Modificar reserva"/"Cancelar reserva" deshabilitados sin
  selección**, mismo mecanismo que las otras dos solapas — pasan de
  variables locales a `self.boton_modificar`/`self.boton_cancelar` con
  `_actualizar_botones()`.
- La tabla de esta solapa suma `excluir_tabla_del_tab` (1.5, no estaba
  aplicado todavía acá).

### Bug real corregido de paso: Liquidaciones no se refrescaba en vivo

Reportado por la clienta mientras probaba esta tanda: crear una
reserva aislada de un profesional categoría R con "Período a imputar"
= actual regenera la liquidación de ese período (ver arriba), pero la
solapa "Emisión de archivos" de Liquidaciones no mostraba el cambio
hasta reabrir la pantalla. Causa real: `_PanelEmisionArchivos.
showEvent()` solo hacía `self.campo_periodo.setFocus()`, sin llamar
`self.actualizar()` — a diferencia del resto de las solapas de este
documento, que sí recalculan su contenido en cada `showEvent`. Se
corrige sumando esa llamada antes de poner el foco.

### Hallazgo de estabilidad real: `WA_StyledBackground` + `paintEvent` sin `super()` puede segfaultear

Al sumar un borde negro a las muestras de color de "Referencias de
colores" (petición de una ronda anterior, revisada de paso en esta
tanda), la primera versión le ponía `Qt.WidgetAttribute.WA_
StyledBackground` directo a `_CeldaGrilla` (el widget de pintado
manual, cuyo `paintEvent` NO llama a `super().paintEvent()`) para que
el borde QSS se pintara encima. Corriendo la suite completa aparecía
un `Fatal Python error: Segmentation fault` real, reproducible,
DENTRO de `paintEvent` de esa misma clase — pero solo cuando se
corrían ciertos archivos de test juntos (`test_reservas.py` +
`test_gui_liquidacion.py` + `test_gui_grilla_operativa.py`), nunca
archivo por archivo ni en combinaciones de dos. Diagnosticado con
`git stash` acotado a `grilla_operativa.py`/`estilos.py`: revertir
justo ese cambio hacía desaparecer el crash. Causa: `WA_
StyledBackground` sobre un widget con pintado 100% manual, combinado
con la hoja de estilos global reaplicándose en ciclos rápidos de
creación/destrucción de widgets (muchos tests seguidos), termina
corrompiendo memoria real — no es un flake del test runner.

Arreglo: en vez de poner el atributo sobre `_CeldaGrilla` directo, cada
muestra de la leyenda se envuelve en un `QFrame` propio
(`objectName="muestraLeyenda"`) — un `QFrame` soporta el borde de QSS
de forma nativa, sin necesitar `WA_StyledBackground` ni tocar el
`paintEvent` de nada. Verificado corriendo la combinación exacta que
crasheaba 3 veces seguidas sin problema. Ojo para el futuro: cualquier
widget con `paintEvent` propio que no llame a `super()` corre el mismo
riesgo si se le pone `WA_StyledBackground` — envolverlo en un `QFrame`
en vez de tocarle el atributo directo.

Tests nuevos/reescritos: `tests/test_reservas.py` (9 tests de
`modificar_reserva_aislada`, más los de `crear_reserva_aislada` con
`periodo_imputado`). `tests/test_gui_reservas.py` (batch completo de
las tres solapas: diálogos mockeados con `_DialogoRegularFalso`/
`_mockear_dialogo_modificar_regular`/`_mockear_dialogo_modificar_
aislada`, confirmaciones de cancelar con `QMessageBox.question`
mockeado a Sí/No, columna "Período imputado", botones deshabilitados
sin selección, foco). `tests/test_gui_grilla_operativa.py`
(`test_muestras_de_la_leyenda_quedan_recuadradas_en_negro` reescrito
contra el `QFrame` nuevo en vez de `WA_StyledBackground`).

## Reservas regulares: finalizar/eliminar una reserva cuya Vigencia desde es de un período ya cerrado

Caso real de la clienta: profesional R5 con una reserva regular vigente
desde octubre (9-12hs, consultorio 3), parada virtualmente en noviembre
(ya hay una liquidación de noviembre emitida, así que octubre quedó
"cerrado" — DC-08 §6.2). Pide una hora más (9-13hs) desde noviembre, en
OTRO consultorio (el 2) — hace falta reemplazar la reserva vieja por
una nueva, pero ni "Modificar reserva" ni "Eliminar reserva" lo
permitían: el guardarraíl de período cerrado (`_validar_vigencia_no_
cerrada`, sobre la `VigenciaInicio` de la fila) bloqueaba cualquier
edición, aunque el cambio real no tocara nada de octubre — "Modificar
reserva" ni siquiera permite cambiar de consultorio (solo Horario/
Vigencia), así que el camino real es finalizar la vieja desde noviembre
y crear la nueva (eso sí ya funcionaba sin bloqueo, noviembre está
abierto).

Dos ajustes puntuales, confirmados con la clienta antes de tocar código
(el guardarraíl protege plata real, no es un detalle cosmético):

### "Modificar reserva": finalizar sin reabrir el período cerrado

`_ultimo_dia_cerrado(conn, id_profesional)` (nueva): el último día real
del último período YA cerrado para este profesional (`None` si no hay
ninguno) — el borde seguro, porque una reserva que ya estuvo activa sin
cambios durante todo ese período no le cambia nada a lo que esa
liquidación ya calculó.

`modificar_reserva_regular` detecta el caso "solo finalizar" (Horario Y
Vigencia desde quedan EXACTAMENTE igual que la fila, Vigencia hasta se
fija por primera vez o se acorta — nunca se estira) y, solo en ese
caso, usa `_validar_finalizacion_no_retroactiva` en vez del guardarraíl
estricto: permite cualquier Vigencia hasta que caiga en el borde de
arriba o después (ej. 31/10, el último día del período cerrado), sigue
bloqueando una que se meta A MITAD de un período cerrado (ej. 15/10 —
eso sí le quitaría presencia que esa liquidación ya tuvo en cuenta).
Cualquier otro cambio (horario, Vigencia desde) sigue con el
guardarraíl de siempre, sin excepción.

### "Eliminar reserva": permitido si la reserva sigue activa

Pedido explícito de la clienta, aceptando el costo a sabiendas: a
diferencia de "finalizar" (conserva la fila), "Eliminar reserva" borra
la fila entera — perdería el rastro de que existió durante el período
cerrado. Consultada la clienta puntualmente sobre esta diferencia,
confirmó que igual prefiere que borre la fila de verdad en este caso.

`eliminar_reserva_regular` ahora permite el borrado si la reserva sigue
ACTIVA al borde del último período cerrado (`VigenciaFin` en blanco, o
posterior a ese borde — el caso real: "tengo una reserva vieja
corriendo y la quiero reemplazar ya"). Si la reserva YA estaba
finalizada ANTES de ese borde (una fila puramente histórica, sin
ningún motivo de negocio real para tocarla ahora), sigue bloqueado
igual que antes.

Tests nuevos: `tests/test_reservas.py`
(`test_modificar_reserva_regular_finaliza_en_el_borde_del_periodo_
cerrado_se_permite`, `test_modificar_reserva_regular_finaliza_dentro_
del_periodo_cerrado_sigue_bloqueada`, `test_modificar_reserva_regular_
cambia_horario_y_finaliza_en_periodo_cerrado_sigue_bloqueada`,
`test_eliminar_reserva_regular_activa_en_periodo_cerrado_se_permite`).
El test preexistente `test_eliminar_reserva_regular_en_periodo_
cerrado_bloquea` pasó a llamarse `..._ya_finalizada_..._sigue_
bloqueada`, agregándole un `vigencia_fin` histórico a la reserva de
prueba — su escenario original (reserva sin Vigencia hasta) ahora cae
del lado permitido a propósito.

## Reservas aisladas: rediseño a 4 columnas

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
trabajo" (CLAUDE.md).

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
largo (ver "Indicador 'Procesando...'", CLAUDE.md).

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

Ronda siguiente, pedido explícito de la clienta sobre la pantalla ya en
uso ("Muy conforme hasta ahora, ajustaría el ancho de la tabla en
algunas columnas ya para terminar esta solapa definitivamente"):

- **Horario**: sufijo "hs" al final ("9:00 a 10:00hs"), alineado a la
  derecha — agregado directo en el `setItem` de esta tabla, sin tocar
  `_fmt_horario` (compartida con Regulares/Extraordinaria, que no
  pidieron este cambio).
- **Fecha**: pasa de `_fmt_fecha` (compartida) a `_fmt_fecha_dia_abrev`
  (nueva, puntual de esta tabla) — mismo formato "ddd dd-MM-yyyy" que ya
  usa el campo "Fecha" del formulario de esta misma pantalla (`_FORMATO_
  FECHA_DIA`/`_LOCALE_ES`, ya existían). Alineada a la derecha. Ancho:
  pasa del grupo "recorte porcentual" (20%) al grupo "que entre justo"
  (ancho NATURAL de `resizeColumnsToContents()`, que ya mide el
  contenido real — "mar 15-10-2026" — cargado antes de llamar a
  `_ajustar_columnas_aisladas`).
- **Consul/Reubicación/Período imputado**: contenido centrado
  (`item_centrado`, nuevo en `app/gui/widgets/items_tabla.py`, hermano
  de `item_numero` — mismo criterio "excepción puntual" que documenta la
  convención general de "Contenido de celda" en CLAUDE.md).
- **Profesional se lleva el ancho sobrante**: pedido explícito ("dáselo
  a la columna 'Profesional'... sin espacios en blanco al final y sin
  que se vea la barra de desplazamiento horizontal... contemplá que vas
  a ver sí o sí la barra de desplazamiento vertical") —
  `_distribuir_ancho_sobrante_aisladas` (nueva, llamada al final de
  `_ajustar_columnas_aisladas`) calcula `tabla.width()` menos el
  encabezado vertical, el borde de `QTableView` (2px, `estilos.py`) y
  el ancho de la barra de desplazamiento vertical — este último
  SIEMPRE, la esté mostrando Qt en este momento o no (`QStyle.PM_
  ScrollBarExtent`, no `verticalScrollBar().isVisible()`): sin este
  descuento incondicional, el día que la tabla realmente necesite esa
  barra (el caso normal, con muchas reservas cargadas) le robaría ancho
  al viewport y de rebote aparecería la barra horizontal, que es
  justo lo que se quiere evitar. Lo que sobra de esa cuenta, menos la
  suma de las otras 11 columnas, se lo lleva "Profesional" (con el piso
  de siempre, `_ANCHO_COL_PROFESIONAL`).

  `tabla.width()` recién refleja el ancho real una vez que Qt terminó
  de resolver el layout de toda la ventana — en el momento en que
  `showEvent` llama a `actualizar()` (que dispara `_ajustar_columnas_
  aisladas`) ese ancho puede seguir desincronizado (mismo problema de
  fondo que `_alto_referencia_aisladas`, confirmado con un script de
  geometría: sin este reintento "Profesional" se quedaba en el piso de
  180px en vez de repartirse el sobrante real). `showEvent` programa un
  `QTimer.singleShot(0, ...)` para volver a correr `_distribuir_ancho_
  sobrante_aisladas` apenas el loop de eventos procese el layout
  pendiente.

  Bug real encontrado corriendo la suite completa (no al revisar la
  pantalla sola): si la ventana se cierra antes de que ese timer
  dispare, `self.tabla` ya no existe del lado de C++ cuando el callback
  corre — "libshiboken: Internal C++ object... already deleted",
  reventaba en medio de OTRO test sin relación, el que le tocara
  procesar el loop de eventos en ese momento. Mismo guard que ya usan
  `foco._EnterAvanzaFoco`/`selector_profesional._SeleccionarTodoAl
  Enfocar` para este mismo problema: `shiboken6.isValid(self.tabla)`
  antes de tocarla (`_distribuir_ancho_sobrante_si_sigue_vivo`, nuevo
  método del panel).

Pixel final del borde derecho de la tabla, medido con un script de
geometría offscreen a 1500x900 (mismo criterio que el pixel del botón
"Cancelar reserva" de la ronda anterior): **1475**. Reportado a la
clienta como referencia.

Tests nuevos en `tests/test_gui_reservas.py`:
`test_tabla_aisladas_formato_fecha_horario_y_columnas_centradas`,
`test_tabla_aisladas_profesional_se_lleva_el_ancho_sobrante`. Varios
tests preexistentes que comparaban el texto de la columna "Fecha" de
esta tabla contra el formato viejo ("18-08-2026") se actualizaron al
nuevo ("mar 18-08-2026").

Hilo cerrado: la clienta confirmó conformidad con todas las tareas de
esta etapa.

## Reservas aisladas — tabla (ancho fijo, Eliminar, sin Estado) y mensaje con placas

Pedido de la clienta, cuatro puntos sobre la tabla de abajo de "Reservas
aisladas" y uno sobre el mensaje "DETALLE RESERVA {MES}" (DC-03):

1. **Bug real reportado y su causa**: "cuando abro el sistema no aparece
   la barra de desplazamiento horizontal... filtro por un profesional,
   vuelvo a poner todos, ahí aparece la barra". Reproducido con un
   script de geometría offscreen (120 reservas de distintos
   profesionales, filtrar a 1 y volver a "Todos"): el encabezado
   vertical (número de fila) de `self.tabla` no tiene ancho fijo —Qt lo
   recalcula solo según la cantidad de dígitos que necesite mostrar
   (21px con 1 dígito, 29px con 2, 38px con 3, 46px con 4, medido con
   `QFontMetrics` sobre el estilo real de la app)— y
   `_distribuir_ancho_sobrante_aisladas` (que reparte el ancho sobrante
   a la columna "Profesional" leyendo `tabla.verticalHeader().width()`
   en cada `actualizar()`) corría ANTES de que Qt terminara de
   recalcular ese ancho para la cantidad de filas nueva: leía el valor
   VIEJO (más angosto), le daba a "Profesional" más ancho del que
   correspondía, y cuando Qt actualizaba el encabezado al valor
   correcto (más ancho) ya no quedaba margen — la suma total desbordaba
   el viewport por esa misma diferencia y aparecía la barra.

   Arreglado dándole un ancho FIJO al encabezado vertical
   (`_ANCHO_HEADER_VERTICAL_AISLADAS = 46`, alcanza para 4 caracteres
   numéricos — pedido explícito de la clienta) con `verticalHeader()
   .setFixedWidth(...)`, una sola vez en `_armar_ui`: al no cambiar
   nunca más de valor, el bug de lectura desactualizada queda eliminado
   de raíz (no hace falta ningún ajuste de timing). El ancho que esto le
   "saca" a Profesional lo absorbe automáticamente el mecanismo que ya
   existía (`_distribuir_ancho_sobrante_aisladas`), sin tocarlo.

2. **Columna "Estado" eliminada**: consecuencia directa del punto 3
   (ver abajo) — con "Eliminar reserva" borrando la fila de la base en
   vez de marcarla cancelada, toda fila que figure en esta tabla es,
   por definición, una reserva confirmada, así que la columna deja de
   aportar nada. El ancho que ocupaba (medido igual que siempre, "que
   entre justo la palabra 'Confirmada'") se reparte en partes iguales
   entre Profesional/Localidad/Edificio/Fecha (pedido explícito), DESPUÉS
   de los ajustes puntuales de cada una (ver `_ajustar_columnas_
   aisladas`) — no los reemplaza, se suma encima.

3. **"Cancelar reserva" pasa a "Eliminar reserva"**: borra la fila de
   la tabla/base directamente (`eliminar_reserva_aislada`, nueva en
   `app.negocio.reservas`) en vez de marcarla `Estado="Cancelada"`
   (`cancelar_reserva_aislada`, que sigue existiendo TAL CUAL — todavía
   la usa "Reserva extraordinaria", que no se tocó, pedido puntual de
   esta solapa). Mismo aviso de "mismo día" que antes (`requiere_
   aviso`); pierde el historial de canceladas por profesional que antes
   se podía revisar en esta tabla (filtrando por un profesional
   puntual) — aceptado explícitamente por la clienta, consecuencia
   directa de su propio pedido, no un efecto colateral oculto.

4. **Columna "Unidad" centrada** (antes alineada a la izquierda, como
   Localidad/Edificio — texto largo; Unidad es un código corto, mismo
   criterio que Consul/Reubicación/Período imputado).

5. **Mensaje "DETALLE RESERVA {MES}": sección "PLACAS PARA LOS
   TIMBRES"**: al final del mensaje (después de "RESERVAS POSTERIORES"
   y de la nota de sobres, si la hay), una línea "+ {Edificio} -
   {Unidad}: Posición {N}" (signo "+", mismo criterio que el resto de
   las líneas de detalle del mensaje — ver punto 7) por cada unidad
   involucrada en el mensaje (del mes + posteriores) donde el
   profesional YA tiene una placa asignada (mismo criterio que
   `placas.placa_faltante_para_reserva`: cualquier posición de esa
   unidad alcanza). Si no tiene placa en alguna de esas unidades, esa
   unidad se omite sin avisar nada — el aviso de placa faltante ya
   existe aparte, al cargar la reserva; si no tiene en NINGUNA, se omite
   la sección entera. Al pasar por `mensaje_detalle_reserva_aislada`,
   llega gratis tanto al mensaje que se copia al confirmar una reserva
   aislada como al que genera Centro de mensajería a mano (misma
   función, sin duplicar nada).

6. **Filtro de período (arriba de la grilla) se cortaba al desplegar**:
   pedido explícito de la clienta, reportado sobre Reservas aisladas
   pero el combo es COMPARTIDO (`GrillaOperativaWidget.combo_periodo`,
   `app/gui/widgets/grilla_operativa.py` — usado también por Oferta de
   consultorios, Novedades y Grilla semanal). Ancho natural muy ajustado
   (~72px para "2026-10" + flecha, con solo ~22px de margen real sobre
   el texto) — en la pantalla real de la clienta, con los 13 períodos
   sin entrar todos en la altura visible, el desplegable saca un
   scrollbar vertical que le come ese margen y corta el texto. Ancho
   mínimo subido a 100px (`setMinimumWidth`) para que sobre lugar de
   verdad, scrollbar incluido.

7. **Formato WhatsApp (negrita/itálica) en el mensaje**: pedido
   explícito de la clienta, con un mensaje modelo exacto. `*texto*` en
   negrita, `_texto_` en itálica (convención ya usada en otros mensajes
   del sistema, ej. `DEFAULT_OFERTA_BUSQUEDA_WHATSAPP`) — ahora también
   en `mensaje_detalle_reserva_aislada`:
   - `*DETALLE RESERVA {MES}*` y `_{NOMBRE PROFESIONAL}_`: en la
     plantilla editable (`plantillas_texto.DEFAULT_DETALLE_RESERVA_
     AISLADA`, clave "Textos del sistema" `mensaje_detalle_reserva_
     aislada`) — sigue siendo el único texto de plantilla de verdad.
   - `*SALDO A ABONAR: {monto}*`, `_RESERVAS POSTERIORES_` y
     `_PLACAS PARA LOS TIMBRES_`: hardcodeado en el código (como el
     resto del cuerpo del mensaje, armado algorítmicamente, no es texto
     de plantilla).
   - El resto del mensaje (línea de edificio, detalle de cada reserva,
     saldo pendiente, placas) sigue sin ningún marcador — solo esos
     cinco elementos puntuales, tal cual el mensaje modelo que dio la
     clienta.

Tests nuevos/actualizados: `tests/test_reservas.py`
(`test_eliminar_reserva_aislada_otro_dia_no_requiere_aviso_y_borra_la_
fila`, `test_eliminar_reserva_aislada_mismo_dia_requiere_aviso`,
`test_eliminar_reserva_aislada_inexistente_lanza_error`),
`tests/test_gui_reservas.py` (renombrados/actualizados los que
probaban "Cancelar reserva" sobre Aisladas —
`test_eliminar_reserva_aislada_borra_la_fila`, `test_eliminar_reserva_
aislada_pide_confirmacion_explicita`, `test_eliminar_reserva_aislada_
declinada_no_cambia_nada`, `test_tecla_delete_en_aisladas_elimina_la_
reserva` — más un test nuevo end-to-end de la sección de placas,
`test_crear_reserva_aislada_con_placa_asignada_copia_placas_para_los_
timbres`), `tests/test_mensajes.py` (`test_detalle_aislada_sin_placas_
no_agrega_la_seccion`, `test_detalle_aislada_con_placa_en_una_sola_
unidad_solo_esa_linea`, `test_detalle_aislada_con_placas_en_ambas_
unidades_las_dos_lineas`, más los ajustados por el formato WhatsApp
nuevo del encabezado/"RESERVAS POSTERIORES"), `tests/test_plantillas_
texto.py` (ídem, template por defecto).

Hilo cerrado: la clienta confirmó las correcciones finales (formato
WhatsApp del mensaje y ancho del combo de período) y pidió archivar.

## Reserva aislada de un mes pasado, imputada al siguiente, no regeneraba la liquidación en curso

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
sube reflejando la aislada, correctamente. No se encontró ningún bug
separado acá: lo más probable es que el síntoma (2) haya sido el MISMO
problema visto desde el lado manual (sin el fix de (1), quizás algún
otro paso intermedio tampoco se disparaba) o un detalle puntual de qué
estaba tildado/seleccionado en la pantalla en ese momento.

Hilo cerrado: pendiente de que la clienta reporte si, ya con el fix de
(1) andando, el síntoma (2) le sigue pasando al reemitir manualmente —
sin un caso puntual nuevo (pantalla exacta, pasos, período elegido) no
hay nada más para investigar de este lado; se archiva a pedido de la
clienta junto con el resto de los hilos cerrados de esta ronda.

## Reservas aisladas: check "Mostrar todas las reservas" (sin filtro de fecha por defecto)

Pedido de la clienta:

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

## Reservas aisladas: rename del check "Mostrar todas las reservas"; arranque de la revisión de Reservas regulares

Pedido explícito de la clienta, varios puntos en un mismo mensaje:

1. **Reservas aisladas: check "Mostrar todas las reservas" renombrado a
   "Mostrar reservas anteriores"** (`_PanelReservasAisladas.check_
   mostrar_todas`, `app/gui/pantallas/reservas.py`) — mismo
   comportamiento de siempre, solo cambia la etiqueta.

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

## Reservas regulares: ronda 4 — aclaración de la clienta sobre el borde, pedido nuevo de "Detalle", colchón de 5px para el scroll

La clienta aclaró cada uno de los tres puntos de la ronda anterior con
pedidos mucho más concretos (verbatim, un solo mensaje):

"* Referencia de colores: ponele de nuevo la linea fina del contorno a
cada referencia de colores. Lo que te había pedido que saques era
porque había un recuadro "doble" llamalo asi, uno que envolvía justo el
contorno de la referencia, que es lo que quiero conservar, y otro que
ocupaba un area mas grande, como si fuera la celda invisible en el cual
estaba adentro la referencia.
* Lo de la etiqueta detalle y el cuadro de detalle te lo explico de
manera distinta. Tomando como referencia que la linea de abajo del
cuadro de detalle esta en la posición correcta, a partir de ahi reducí
el alto del cuadro a la mitad, y arriba donde termina el cuadro y abajo
de la grilla poné la etiqueta que dice "Detalle"
* Para evitar la barra de scroll vertical del formulario, baja la tabla
5px a ver si asi la pegamos y resolvemos el tema"

1. **Borde de la leyenda — aclarado: el "recuadro doble" era el MISMO
   borde del `QFrame` (Punto #9.1.2), dibujado alrededor de una celda
   más grande que la muestra, no dos mecanismos de borde distintos.**
   `marco_muestra` (el `QFrame` que envuelve cada muestra, ver
   `LeyendaColores.actualizar`) no tenía `setFixedSize` — el grid layout
   lo estiraba a TODO el ancho/alto de su celda (columnas sin alinear a
   la izquierda estiran sus widgets a ocupar toda la celda), una "celda
   invisible" más grande que la muestra de color de adentro cuando algún
   vecino de esa columna pedía más ancho — el borde quedaba alrededor de
   esa celda estirada, no pegado al contorno real de la muestra: visto
   de cerca, dos rectángulos (el borde grande + el color chico adentro
   con espacio en blanco al rededor). Se repone `border: 1px solid
   #000000` en `estilos.py` (revertido el `border: none` de la ronda
   anterior) y se suma `marco_muestra.setFixedSize(*self._tamano_
   muestra)` — el `QFrame` nunca puede ser más grande que la muestra que
   envuelve, así el borde queda pegado justo a su contorno sea cual sea
   el ancho real de la columna. Confirmado con zoom x3 sobre una captura
   con datos densos: un solo rectángulo por muestra, pegado a su color.

2. **"Detalle": pedido nuevo y más concreto, reemplaza el intento de la
   ronda anterior.** El pie del cuadro (ya en la posición correcta,
   `min(pie_eliminar, pie_maximo_grilla)`, sin tocar) se toma como
   referencia fija; el cuadro pasa a medir la MITAD de lo que medía
   antes, y la etiqueta "Detalle:" (antes de alto fijo/chico, pegada
   arriba de todo) crece para ocupar la otra mitad, con su texto
   alineado abajo (pegado al cuadro al que describe, no a la grilla).

   Primer intento (revertido): un `QSpacerItem` nuevo insertado antes de
   la etiqueta, redimensionado en cada pasada de `_ajustar_alto_
   detalle`. Confirmado con un script de geometría que NO funcionaba:
   `sizeHint()` del espaciador reflejaba el alto pedido pero su
   `geometry()` real se quedaba en 0 — un espaciador sin contenido
   propio parece ser lo primero que Qt recorta cuando el layout no entra
   del todo en el tope de `self.grilla` (`limitar_alto_grilla`), a
   diferencia de un widget real con `setFixedHeight`, que si se respeta
   como restricción dura (confirmado: `texto_detalle.setFixedHeight(...)`
   sí se refleja siempre, en todas las rondas anteriores).

   Arreglo definitivo: en vez de un espaciador nuevo, se agranda la
   ETIQUETA misma (`etiqueta_detalle`, pasada de privada — `_etiqueta_
   detalle` — a pública, mismo criterio que `texto_detalle`, para que
   Reservas regulares pueda medirla y fijarle el alto desde afuera sin
   reinventar el acceso) con `setFixedHeight`, un widget real — mismo
   mecanismo ya confiable. `GrillaOperativaWidget` suma dos métodos
   nuevos: `alinear_etiqueta_detalle_al_pie()` (alinea el texto abajo a
   la izquierda, llamado una sola vez en el armado) y `fijar_alto_
   etiqueta_y_cuadro_detalle(alto_etiqueta, alto_cuadro)` (fija los dos
   altos juntos). `_ajustar_alto_detalle` mide ahora contra el TECHO de
   la etiqueta (no el del cuadro) — ese techo no depende de su propio
   alto (lo determina lo que hay ARRIBA: la grilla + el espacio fijo de
   14px), así que el cálculo es idempotente sin necesitar resetear nada
   antes de medir, ni siquiera llamándose dos veces por entrada a la
   solapa.

   Confirmado con el script de geometría de rondas anteriores (36
   consultorios/200+ reservas/1366×768): `etiqueta_detalle.height()` y
   `texto_detalle.height()` quedan parejos (57px cada uno, de un
   sobrante de 114), sin superposición con la grilla, scroll vertical de
   `_scroll_superior` en 0. Con el dataset simple de los tests (1
   reserva, sin forzar el tope de `self.grilla`), el pie del cuadro
   sigue cerca del pie de "Eliminar reserva" (mismo criterio de
   siempre), confirmando que el reparto nuevo no rompe el caso normal.

3. **Colchón de 5px en `_scroll_superior`, propuesto por la clienta
   como arreglo pragmático para el resto de la barra de scroll vertical
   ("por un pelín") que seguía apareciendo en rondas anteriores.**
   `_MARGEN_SCROLL_SUPERIOR_REGULARES = 5`, sumado al `setFixedHeight`
   de `_scroll_superior` (en `showEvent` y en el reajuste diferido) —
   unos pocos píxeles de margen absorben una pequeña diferencia de
   medición entre este sandbox y la PC real sin arriesgar que el
   contenido no entre, a costa de esos mismos píxeles de menos para la
   tabla de abajo (imperceptible frente al resto del alto disponible).

Tests: `tests/test_gui_grilla_operativa.py` (`test_muestras_de_la_
leyenda_quedan_recuadradas_pegadas_a_su_contorno`, reemplaza al test de
la ronda anterior — verifica que el `QFrame` queda EXACTAMENTE del
mismo tamaño que la muestra que envuelve, la causa real del "recuadro
doble"); `tests/test_gui_reservas.py` (`test_regulares_detalle_termina_
cerca_del_pie_de_eliminar_reserva_con_grilla_cargada`, reescrito:
verifica el reparto parejo entre etiqueta/cuadro, que quedan contiguos
sin hueco entre sí, y que ninguno de los dos se superpone con la
grilla) — el resto de los tests de ambos archivos, y el escenario denso
(`test_regulares_con_grilla_densa_no_muestra_scroll_vertical_de_la_
solapa`), siguen pasando sin cambios.

## Reservas regulares: ronda 5 — pedido más concreto de "Detalle" (vuelta al criterio simple), tabla contra "Eliminar reserva", barra horizontal nueva en el menú lateral

Pedido explícito de la clienta, tres puntos en un mismo mensaje (ya NO
sobre Reservas regulares el primero — un bug nuevo, distinto, en el menú
lateral de toda la app):

"* Aparece una barra de escroll horizontal en el menu lateral que antes
no aparecía, fijate si podes ajustar algo para que no se vea, si tenés
que reducir alguna fuente del menú hacelo.
* Subí la etiqueta "Detalle" para que quede abajo de la grilla, abajo de
la barra de escroll horizontal de la grilla concretamente. Luego que el
cuadro de detalle empiece abajo de esa etiqueta, y que se estire hasta
la altura donde termina el botón de eliminar reserva.
* La tabla subila un poco hasta abajo del botón "Eliminar reserva", sin
superponerse con esa altura, justo abajo. Y luego que la tabla termine
abajo de la solapa hasta donde llegue como para ver cuatro filas de
registros enteras"

1. **Barra de scroll horizontal nueva en el menú lateral — bug real,
   nada que ver con Reservas.** `QListWidget#navegacion` (`app/gui/
   main_window.py`) tiene ancho fijo (240px, 14px de padding a cada
   lado en `estilos.py` — 212px disponibles) y nunca había tenido
   política de scroll horizontal explícita. La categoría del segundo
   grupo de secciones es el NOMBRE DEL ESPACIO, personalizable en
   Configuración general — en mayúscula y negrita (pedido de siempre) —
   y el de la clienta ("Espacio Ramos consultorios") es bastante largo.
   Confirmado con `QFontMetrics`: "ESPACIO RAMOS CONSULTORIOS" a 13px
   negrita (el tamaño que tenían las categorías hasta ahora, igual al
   resto del menú) mide 214px, ya por encima de los 212px disponibles
   EN ESTE SANDBOX — la fuente real de Windows mide distinto (ver
   "Metodología de trabajo"), así que el sobrante real podía ser mayor
   todavía; de ahí la barra de scroll horizontal nativa de `QListWidget`
   que apareció sola, nunca pedida ni contemplada antes. Dos capas de
   arreglo: la fuente de la categoría baja a 11px (sigue en negrita —
   "ESPACIO RAMOS CONSULTORIOS" pasa a medir 181px, con margen de
   sobra) y, defensivo, `self._navegacion.setHorizontalScrollBarPolicy
   (Qt.ScrollBarPolicy.ScrollBarAlwaysOff)` — un nombre de espacio
   TODAVÍA más largo que el de la clienta no tiene por qué volver a
   mostrar una barra nueva: con la política apagada, se recorta contra
   el borde del menú en vez de eso. Test nuevo en `tests/test_main_
   window.py`: `test_categoria_de_nombre_largo_no_dispara_scroll_
   horizontal_del_menu` (categoría "ESPACIO RAMOS CONSULTORIOS",
   confirma `horizontalScrollBar().maximum() == 0`).

2. **"Detalle": pedido más concreto, vuelve al criterio simple
   (reemplaza el reparto a la mitad de la ronda anterior).** La ronda
   anterior probó partir el sobrante en dos mitades (etiqueta agrandada
   + cuadro a la mitad) — la clienta lo descartó con un pedido más
   directo: la etiqueta vuelve a su alto NATURAL, pegada abajo de la
   grilla (sin tocar nada — `agregar_espacio_antes_de_detalle(14)` ya
   mide desde el pie real de la grilla, barra de scroll horizontal
   incluida si está visible, de rondas bien anteriores) y el cuadro
   `texto_detalle` vuelve a ocupar TODO el sobrante hasta el pie de
   "Eliminar reserva" — el criterio de dos rondas atrás, con el tope
   anti-superposición de la ronda inmediatamente anterior (`min(pie_
   eliminar, pie_maximo_grilla)`) que SÍ se queda, sin tocar: ese tope
   es el que evita la superposición real que había reportado la clienta
   con foto/video, independiente de cómo se reparta el sobrante adentro.
   Se sacan los dos métodos que ya no hacían falta
   (`alinear_etiqueta_detalle_al_pie`/`fijar_alto_etiqueta_y_cuadro_
   detalle`, `GrillaOperativaWidget`) y se revierte el test asociado
   (`test_regulares_detalle_termina_cerca_del_pie_de_eliminar_reserva_
   con_grilla_cargada`) a su forma de dos rondas atrás.

3. **Tabla de abajo: pegada contra el pie de "Eliminar reserva", y 4
   filas en vez de 3.** `_scroll_superior` (el `QScrollArea` que
   envuelve formulario+grilla+Detalle) fijaba su alto SOLO contra
   `_contenido_superior.minimumSizeHint()` — ese mínimo puede incluir
   de más: `panel_form` termina con un `addStretch()` final que el
   splitter puede estirar más allá del pie de `boton_eliminar` cuando
   la columna de al lado (`self.grilla`) necesita más alto, dejando a
   la tabla de abajo (`panel_tabla`, que arranca justo donde termina
   `scroll`) empezando más abajo de lo necesario. `_fijar_alto_scroll_
   superior` (nueva, reemplaza el cálculo inline que estaba repetido en
   `showEvent`/`_reajustar_alto_y_columnas_si_sigue_vivo`) mide también
   la distancia real entre el techo de `scroll` y el pie de `boton_
   eliminar`, y usa el MAYOR entre esa distancia y el mínimo del
   contenido — nunca más chico que lo que el contenido necesita de
   verdad (evita reabrir la barra de scroll vertical de rondas
   anteriores), pero prefiere la referencia de `boton_eliminar` cuando
   alcanza, en vez de arrastrar el sobrante del `addStretch()`.
   `_FILAS_VISIBLES_TABLA_INFERIOR_REGULARES` sube de 3 a 4 (mismo
   valor que ya tenía Aisladas) para la segunda parte del pedido.

   Confirmado con el script de geometría de rondas anteriores (36
   consultorios/200+ reservas/1366×768): sin cambios en los números
   medidos acá (el mínimo de contenido sigue siendo el más grande de
   los dos en este dataset, así que el cambio es un no-op en este
   sandbox) — el mecanismo (preferir `boton_eliminar` cuando alcanza,
   nunca por debajo del mínimo real) es el que debería notarse en la PC
   real, donde aparentemente el mínimo de contenido deja más margen de
   sobra del necesario.

Tests: `tests/test_main_window.py` (nuevo, ver punto 1); `tests/test_
gui_reservas.py` (`test_regulares_detalle_termina_cerca_del_pie_de_
eliminar_reserva_con_grilla_cargada`, revertido a la versión de dos
rondas atrás) — el resto de los tests de Reservas regulares, incluido
el escenario denso, siguen pasando sin cambios.

## Reservas regulares: ronda 6 — tabla 5px más abajo, "Detalle" repartido un tercio/dos tercios

Pedido explícito de la clienta, tres puntos en un mismo mensaje:

"* La tabla entera, asi como está, bajala 5 pixeles
* Reducí un tercio el alto del cuadro de "Detalle".
* La etiqueta "Detalle" que baje ese tercio de tamaño que se redujo del
cuadro"

1. **Tabla de abajo 5px más abajo.** `panel_tabla` arranca justo donde
   termina `_scroll_superior` (`stretch=1` en `layout_externo`), así que
   bajar la tabla entera es lo mismo que agrandar el alto fijo de
   `_scroll_superior` en 5px más. `_MARGEN_SCROLL_SUPERIOR_REGULARES`
   (el colchón ya sumado en la ronda 4 para absorber diferencias de
   medición de fuente entre este sandbox y la PC real de la clienta)
   sube de `5` a `10` — mismo mecanismo de siempre
   (`_fijar_alto_scroll_superior`, sin tocar su lógica), el pedido es
   literalmente "5 píxeles más" sobre el colchón que ya había.

2. **"Detalle": reparto un tercio (etiqueta) / dos tercios (cuadro) del
   mismo sobrante de siempre.** Hasta la ronda anterior, "Detalle:" (la
   etiqueta) se quedaba en su alto natural y `texto_detalle` (el cuadro)
   se llevaba TODO el sobrante hasta el tope anti-superposición (`min
   (pie_eliminar, pie_maximo_grilla)`, sin cambios — sigue siendo la
   misma referencia que evita el recorte/superposición real reportado
   en rondas 2 y 3). Ahora ese mismo sobrante se reparte: 1/3 para la
   etiqueta (que CRECE, con su texto alineado abajo — pegado al cuadro
   al que describe, `Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.
   AlignBottom` — en vez de arriba de todo, para que visualmente "baje"
   ese tercio hacia el cuadro) y 2/3 para el cuadro.

   Mismo mecanismo PROBADO de la ronda 4 (no el de la ronda inmediata
   anterior, que había vuelto al reparto 100% simple): `setFixedHeight`
   sobre los dos widgets REALES (`self.grilla.etiqueta_detalle`,
   `self.grilla.texto_detalle`) — NO un `QSpacerItem` nuevo (ver el
   historial de la ronda 4 sobre por qué un espaciador no funciona en
   este layout: su `sizeHint()` refleja el alto pedido pero su
   `geometry()` real queda en 0 cuando el layout contenedor está
   acotado por `setMaximumHeight`, a diferencia de un widget real, que
   Qt sí respeta como restricción dura). A diferencia de la ronda 4
   (que agregaba métodos nuevos en `GrillaOperativaWidget`,
   `alinear_etiqueta_detalle_al_pie`/`fijar_alto_etiqueta_y_cuadro_
   detalle`, borrados en la ronda 5 por quedar sin uso), el reparto
   queda esta vez inline en `_ajustar_alto_detalle`
   (`app/gui/pantallas/reservas.py`), usando directamente los atributos
   ya públicos `etiqueta_detalle`/`texto_detalle` — no hace falta
   reponer esos métodos.

   La referencia de medición sigue siendo el TECHO de la etiqueta
   (`self.grilla.etiqueta_detalle`, no el del cuadro) — no depende de
   su PROPIO alto (lo determina solo lo que hay arriba: la grilla + el
   espacio fijo de 14px), así que el cálculo sigue siendo idempotente
   sin necesitar resetear nada antes de medir, aunque `_ajustar_alto_
   detalle` se llame dos veces por entrada a la solapa (la sincrónica
   de `showEvent` y la diferida del `QTimer`).

   Confirmado con el script de geometría de rondas anteriores (36
   consultorios/200+ reservas/1366×768): `etiqueta_detalle.height()`
   pasa de compartir el 100% del sobrante con el cuadro a quedarse con
   un tercio exacto (38px de 114px totales) y `texto_detalle.height()`
   con los dos tercios restantes (76px) — sin superposición con la
   grilla y sin scrollbar vertical interna en `_scroll_superior`
   (`verticalScrollBar().maximum() == 0`, sin cambios respecto de
   rondas anteriores).

Tests: `tests/test_gui_reservas.py`
(`test_regulares_detalle_termina_cerca_del_pie_de_eliminar_reserva_
con_grilla_cargada`, docstring actualizado al reparto 1/3-2/3 y se
suma una verificación explícita de que el cuadro mide el doble que la
etiqueta, con margen de 3px por el redondeo de la división entera) —
el resto de los tests de Reservas regulares, incluido el escenario
denso (`test_regulares_con_grilla_densa_no_muestra_scroll_vertical_
de_la_solapa`), siguen pasando sin cambios.

## Reservas regulares: ronda 7 — vuelta al criterio simple de "Detalle" más arriba, tabla pegada a "Eliminar reserva" (causa de fondo, no solo colchón)

La clienta mandó una captura real de la app (video/foto de rondas
anteriores habían llevado a la tabla 5px más abajo y al reparto 1/3-2/3
de la ronda 6) con tres preguntas de pixeles concretas antes de pedir
nada, para evitar seguir iterando a ciegas — respondidas con geometría
medida directamente sobre esa captura (no a ojo): la grilla completa
(con la barra de scroll horizontal) terminaba en y≈708; el cuadro de
"Detalle" en y≈809; la etiqueta "Detalle:" en y≈742-752; "Eliminar
reserva" en y≈802 y la tabla de abajo recién arrancaba en y≈869 — un
gap de 67px contra el botón, muy por encima de los 5px que se venían
pidiendo. La clienta confirmó además un "efecto raro": la pantalla se
ve distinta recién abierta que después de navegar a otra solapa y
volver (la segunda, más cercana a lo pedido) — consistente con el
`showEvent` disparándose de nuevo con geometría ya asentada por el
splitter, mismo mecanismo que describen rondas anteriores.

Con esos números como referencia, pedido confirmado en tres partes:

1. **Subir la etiqueta "Detalle" para que quede pegada (casi) al pie
   de la grilla+scrollbar.** `agregar_espacio_antes_de_detalle`
   (`_armar_ui`) baja de 14 a 2 — se probó primero en 0 (replicando el
   "hasta antes de la barra" de manera literal) pero un test con
   geometría real detectó que la etiqueta quedaba a -1px de la última
   fila de la grilla (superposición de 1px) — 2px de margen alcanzan
   para evitarlo sin volver a los 14px de antes, que ya no hacían falta
   (el riesgo real de superposición lo resuelve `fijar_alto_filas`, no
   este espacio).

2. **El cuadro mantiene su pie fijo, pero su techo sube con la
   etiqueta.** Se revierte el reparto 1/3 (etiqueta) / 2/3 (cuadro) de
   la ronda 6 al criterio simple de dos rondas atrás: la etiqueta a su
   alto NATURAL (sin `setFixedHeight` ni alineación especial) y
   `texto_detalle` ocupando TODO el sobrante hasta el mismo tope de
   siempre (`min(pie_eliminar, pie_maximo_grilla)`, sin tocar). Como el
   cuadro arranca justo debajo de la etiqueta, y la etiqueta subió por
   el punto 1, el cuadro automáticamente "arranca más arriba" sin
   perder su pie — exactamente lo pedido, sin necesitar ningún cálculo
   nuevo de reparto.

3. **La tabla de abajo, a 5px exactos de "Eliminar reserva" — causa de
   fondo, no un colchón más.** Las dos rondas anteriores (colchón
   `_MARGEN_SCROLL_SUPERIOR_REGULARES`, de 5 a 10) atacaban el SÍNTOMA
   (la tabla lejos del botón) sumando margen a ciegas, sin explicar por
   qué `_fijar_alto_scroll_superior` elegía el piso de `_contenido_
   superior.minimumSizeHint()` por encima del pie real de "Eliminar
   reserva" en vez de usar este último. Investigado con un script de
   geometría sobre el escenario denso (36 consultorios/200+ reservas):
   dos causas reales, encontradas recién esta ronda porque las
   anteriores solo se habían confirmado con datasets chicos de test,
   donde nunca llegaban a disparar:

   - **`self._alto_referencia_regulares` (el presupuesto de columna 1,
     usado para topear columna 2/3 vía `limitar_alto_grilla`) se
     retroalimentaba solo.** Se leía de `panel_form.height()` (el alto
     YA estirado por el splitter) — si `self.grilla` alguna vez pedía
     más alto del que columna 1 necesitaba de verdad (por ejemplo, el
     propio cálculo de "Detalle" de la ronda anterior), el splitter
     estiraba panel_form para dárselo, y la PRÓXIMA vuelta de
     `showEvent`/`QTimer` volvía a leer ESE alto ya estirado como si
     fuera el "natural" de columna 1 — un ciclo que no converge al pie
     real de "Eliminar reserva" (confirmado con el script: `panel_form.
     height()` terminaba en 547px, 23px por encima de su propio
     `minimumSizeHint()`, 524px — que sí coincide con el pie de
     "Eliminar reserva"). Las tres lecturas de `_alto_referencia_
     regulares` (en `showEvent`, en el reajuste diferido y en `_armar_
     ui`) pasan de `.height()`/`.sizeHint()` a `.minimumSizeHint()` de
     `panel_form` — el piso GENUINO de la columna, que no se mueve
     aunque el splitter la haya estirado de más en una pasada previa,
     rompiendo el ciclo.

   - **El presupuesto que recibía `self.grilla` nunca restaba el
     chroma propio de `grupo_grilla`.** `grupo_grilla` (el `QGroupBox`
     que envuelve a `self.grilla` en el splitter, ver `_armar_ui`) le
     suma 6px propios arriba (`_ALTO_BASE_GRUPO_GRILLA`, ya usado para
     alinear el PRIMER pixel de la columna con sus vecinas, ver rondas
     anteriores) que nunca se habían restado del presupuesto de ALTO
     TOTAL — solo del margen superior. Las tres llamadas a `limitar_
     alto_grilla` y el cálculo de `pie_maximo_grilla` (`_ajustar_alto_
     detalle`) pasan a usar `self._alto_referencia_regulares -
     _ALTO_BASE_GRUPO_GRILLA` en vez del valor entero.

   Con las dos causas corregidas juntas (una sola no alcanzaba: se
   probó restar el chroma sin romper el ciclo de `.height()` primero, y
   el piso seguía igual de inflado), el piso de `_fijar_alto_scroll_
   superior` (`alto_minimo_contenido`) bajó de 542 a 527 en el mismo
   escenario denso — contra un `alto_hasta_eliminar` de 523, una
   diferencia de apenas 4px (antes 19px) — y el `_MARGEN_SCROLL_
   SUPERIOR_REGULARES` baja de 10 a 5 (el valor que la clienta pidió
   literalmente: "una separación de 5 pixeles"), ya que ahora sí
   gobierna el cálculo real en vez de competir contra un piso inflado.
   Confirmado visualmente con una captura del escenario denso: la
   leyenda de colores (que en una ronda anterior se había cuidado de no
   dejar apretada al usar `.height()` en vez de `sizeHint()`) sigue sin
   superponerse ni comprimirse con este cambio — el piso corregido solo
   le resta presupuesto a lo que `self.grilla` pedía de más por el
   ciclo de Detalle, no al natural de la leyenda.

   **Investigado y descartado antes de aceptar el residuo de ~4-9px
   final** (en vez de 0 exacto): no se pudo bajar más sin arriesgar
   reabrir el bug de rondas anteriores (`_scroll_superior` mostrando su
   propia barra de scroll vertical) — un pequeño colchón estable sigue
   siendo necesario, mismo criterio que cualquier otro "residuo"
   aceptado en esta sección.

Tests: `tests/test_gui_reservas.py` —
`test_regulares_detalle_termina_cerca_del_pie_de_eliminar_reserva_
con_grilla_cargada` (docstring y tolerancia actualizados al criterio
simple, sube de 5 a 10px por el residuo de la corrección de fondo);
`test_grilla_de_regulares_usa_panel_form_como_referencia_de_alto`
(actualizado: `maximumHeight()` ya no es igual a `_alto_referencia_
regulares` sino `_ALTO_BASE_GRUPO_GRILLA` menos, y la referencia en sí
usa `minimumSizeHint()` en vez de `sizeHint()`); test nuevo
`test_regulares_tabla_de_abajo_arranca_cerca_del_pie_de_eliminar_
reserva` (gap real entre `boton_eliminar` y `self.tabla`, tolerancia de
15px) — el resto de los tests de Reservas regulares, incluido el
escenario denso (`test_regulares_con_grilla_densa_no_muestra_scroll_
vertical_de_la_solapa`), siguen pasando sin cambios.

## Reservas regulares: ronda 8 — "Detalle" superpuesto con la barra de scroll en la ronda anterior: la causa era el espaciado por defecto de Qt, no un número fijo

Reporte real de la clienta sobre la captura ya enviada de la ronda
anterior (2px de margen explícito antes de "Detalle:"): "en la captura
veo que la etiqueta 'Detalle' está superpuesta a la barra de scroll
horizontal... porque es el problema que venimos teniendo, cuando te
digo subir la altura del cuadro para que llegue abajo de la grilla no
tiene en cuenta lo que ocupa ese título, esa etiqueta, y termina
quedando arriba de la barra." Antes de pedir que probara el .exe,
investigado el mecanismo de fondo (sin reproducir todavía la
superposición exacta en este sandbox, pero identificando la causa real
con certeza): `agregar_espacio_antes_de_detalle(2)` sumaba 2px
EXPLÍCITOS, pensados para sumarse al espaciado PAREJO POR DEFECTO de
`layout_grilla` — pero ese default no es un número fijo del sistema,
es el que resuelve el ESTILO NATIVO de Qt para `QVBoxLayout.spacing()
== -1` ("usar el del estilo"). Confirmado programáticamente: en este
sandbox resuelve a 6px — pero no hay ninguna garantía de que el tema
nativo de Windows de la clienta resuelva ese mismo valor (mismo tipo de
diferencia de entorno que las fuentes, ya documentado en "Metodología
de trabajo", pero acá en espaciado de layout en vez de texto). Un
número fijo pensado para sumarse a un default ambiguo nunca puede
garantizar un gap mínimo real — exactamente el patrón que la clienta
describe ("no tiene en cuenta lo que ocupa...").

**Primer intento (revertido): un mecanismo dinámico que medía el gap
real y agrandaba un widget si no alcanzaba un mínimo.** Sonaba más
robusto que un número fijo (medir, no asumir — el mismo criterio que
ya usa `_ajustar_alto_detalle`), pero un test que forzaba `layout_
grilla.setSpacing(0)` (el peor caso posible, más adverso que cualquier
tema real) reveló que la corrección dinámica podía EMPEORAR el gap en
vez de mejorarlo: agrandar el espaciador en una pasada de `showEvent`/
`QTimer` no se refleja en la posición de los widgets de abajo dentro
del MISMO evento síncrono (necesita que Qt procese el layout pendiente
en otra vuelta del loop de eventos), así que la SIGUIENTE medición
(ya sea la pasada diferida, o la del test) termina viendo una posición
todavía no asentada — y como el sistema completo (splitter, `panel_
form`, `self.grilla`) sigue conviviendo con el ciclo de convergencia ya
documentado en la ronda 7, la corrección del espaciador interactuaba
con ESE ciclo de forma impredecible: en el escenario de prueba, el gap
terminó en -15px (peor que el -7px de partida) después de "corregirlo"
dos veces. Revertido por completo (`asegurar_espacio_minimo_antes_de_
detalle` y el guard dinámico, eliminados de `GrillaOperativaWidget` y
de los dos `showEvent`/reajuste diferido de Reservas regulares) — un
mecanismo que puede empeorar el problema bajo ciertas condiciones es
peor que uno simple que no lo resuelve del todo.

**Arreglo definitivo: un colchón ESTÁTICO más generoso, no una
corrección dinámica.** `agregar_espacio_antes_de_detalle` sigue
armando un widget REAL con `setFixedHeight` (eso sí se queda — más
confiable que un `insertSpacing`, mismo criterio que el resto de esta
sección), pero el valor que Reservas regulares le pasa sube de 2 a 8 —
lo bastante grande como para que, incluso si el tema nativo de Windows
resolviera un default sensiblemente más chico que los 6px de este
sandbox (o incluso 0), el gap total siga siendo cómodo, sin tener que
confiar en medir y corregir en tiempo real. Vuelta al criterio simple y
pragmático ya usado para el resto de los "colchones" de esta sección
(`_MARGEN_SCROLL_SUPERIOR_REGULARES`): un número con margen de sobra,
no calibrado al límite.

Tests: `tests/test_gui_reservas.py` —
`test_regulares_detalle_no_se_superpone_con_la_barra_de_scroll_con_
margen_de_sobra` (nuevo, reemplaza un primer intento que forzaba
`setSpacing(0)` — revertido junto con el mecanismo dinámico que
probaba — verifica un gap de al menos 4px, no solo "sin superposición")
— el resto de los tests de Reservas regulares, incluido el escenario
denso y el de la tabla de abajo, siguen pasando sin cambios.

## Reservas regulares: ronda 9 — nuevo intento, más simple: tabla 5px más abajo, cuadro a la mitad sin mover el pie, etiqueta "Detalle" eliminada

Pedido explícito de la clienta, abriendo con "es terrible pero no
termina de salir bien algo simple, vamos de nuevo con otro intento" —
tres puntos en un mismo mensaje:

"* Se superpone un poco la tabla con el botón de 'Eliminar reserva'.
Baja la posición de la tabla 5px
* Del cuadro de detalle respetá si o si la posición en pantalla de
donde termina. Con es referencia reduci a la mitad la altura del
cuadro para que baje posición en pantalla de donde comienza el
elemento
* Una vez reducido el cuadro, para no tener mas problemas, eliminá la
etiqueta que dice 'Detalle', que quede solo el cuadro"

1. **Tabla de abajo 5px más abajo.** Mismo mecanismo de siempre
   (`_fijar_alto_scroll_superior`, sin tocar su lógica) — `_MARGEN_
   SCROLL_SUPERIOR_REGULARES` sube de 5 a 10 (+5, el mismo pedido
   literal que ya se había hecho una vez en la ronda 6).

2. **El cuadro a la mitad, con el pie SIN TOCAR.** Hasta la ronda
   anterior, `texto_detalle` ocupaba TODO el sobrante entre la grilla y
   el tope de siempre (`min(pie_eliminar, pie_maximo_grilla)`, que
   sigue siendo exactamente el mismo tope, sin cambios). Ahora ese
   sobrante se reparte en dos mitades iguales: la de ABAJO para el
   cuadro (que sigue terminando en el mismo pie de siempre — "respetá
   sí o sí la posición de dónde termina" — pero mide la mitad de alto)
   y la de ARRIBA, que pasa a ser espacio en blanco (el mismo widget
   real de `agregar_espacio_antes_de_detalle`, agrandado) entre la
   grilla y el cuadro — "que baje la posición de dónde comienza el
   elemento" es automático: al quedarse con menos alto pero el mismo
   pie, el techo del cuadro baja exactamente esa mitad.

   La referencia de TECHO para medir el sobrante total pasa a ser el
   pie real de `self.grilla.tabla` (la grilla de horarios) en vez del
   techo de `texto_detalle` mismo (que usaban las rondas anteriores,
   cuando la etiqueta todavía estaba en medio) — sigue siendo estable/
   independiente de lo que mida el cuadro o el espacio en este momento,
   mismo criterio de idempotencia de siempre.

3. **Etiqueta "Detalle:" eliminada — "para no tener más problemas".**
   `GrillaOperativaWidget.ocultar_etiqueta_detalle()` (nueva) saca
   `self.etiqueta_detalle` de `layout_grilla` por completo (`removeWidget`
   + `.hide()`, no solo ocultarla — dejarla en el layout sin sacarla
   reservaría su lugar igual) — llamada una sola vez desde `_armar_ui`
   de Reservas regulares, DESPUÉS de `agregar_espacio_antes_de_detalle`
   (que todavía necesita el índice de la etiqueta para insertarse antes
   de ella, ver su propio código). No afecta a Reservas aisladas, que
   usa `extraer_detalle()` para un caso distinto (reubicar los dos
   widgets en otro lado, no eliminar ninguno) ni a ningún otro uso
   compartido de esta grilla (Oferta, Novedades, Grilla semanal).

   `agregar_espacio_antes_de_detalle` pasa a guardar el widget real que
   arma como atributo (`self._espacio_antes_detalle`, antes una
   variable local) para que un método nuevo, `fijar_espacio_y_alto_
   cuadro_detalle(espacio, alto_cuadro)`, pueda fijar los dos altos
   (el del espacio en blanco de arriba y el del cuadro) juntos, calculados
   los dos del mismo sobrante total por quien llama (`_ajustar_alto_
   detalle`, reservas.py) — fijar uno sin el otro dejaría el reparto a
   medio hacer.

Tests: `tests/test_gui_reservas.py` —
`test_regulares_detalle_termina_cerca_del_pie_de_eliminar_reserva_
con_grilla_cargada` (reescrito: ya no depende de la etiqueta, verifica
que el pie del cuadro sigue en el mismo tope de siempre Y que el gap
que quedó arriba del cuadro es comparable a su propio alto — reparto
mitad y mitad); se reemplaza `test_regulares_detalle_no_se_superpone_
con_la_barra_de_scroll_con_margen_de_sobra` (verificaba la posición de
una etiqueta que ya no existe) por `test_regulares_etiqueta_detalle_
queda_oculta_solo_el_cuadro` (confirma que la etiqueta está afuera del
layout Y oculta); `test_regulares_tabla_de_abajo_arranca_cerca_del_
pie_de_eliminar_reserva` (tolerancia subida de 15 a 25px, +5 por el
mismo colchón) — el resto de los tests de Reservas regulares, incluido
el escenario denso, siguen pasando sin cambios.



## Reservas regulares: ronda 10 — ampliar el cuadro de "Detalle" a 1.5x, respetando el pie

Pedido explícito de la clienta, después de probar la ronda anterior
("probado, casi todo bien"): "ampliá la altura del cuadro de detalle
respetando donde termina, o sea de abajo lo estirás para arriba 1/2 de
tamaño que tiene ahora. Es decir, no se cuantos pixeles tiene ese
cuadro, si mide 100 que mida 150. Que el cuadro se escroleable solo si
es necesario."

`_ajustar_alto_detalle` (`app/gui/pantallas/reservas.py`) seguía
repartiendo el sobrante total (entre el pie de la grilla y el mismo
tope de siempre, `min(pie_eliminar, pie_maximo_grilla)`, sin tocar) en
mitad para el cuadro y mitad como espacio en blanco arriba — ahora el
cuadro se queda con 1.5 veces esa mitad (3/4 del sobrante total), y el
espacio en blanco se achica a lo que queda (1/4). El PIE del cuadro
sigue sin moverse ni un pixel (la cuenta solo cambia CÓMO se reparte el
sobrante por encima de él, el tope en sí no se tocó).

Sobre "que se escrolee solo si es necesario": `texto_detalle` ya es un
`QTextEdit` con `setFixedHeight` y la política de scrollbar vertical
por default de Qt (`AsNeeded`, nunca pisada en este archivo) — un
detalle más largo que el cuadro (ya agrandado) escrolea solo, sin
recortarse, de fábrica. No hizo falta ningún cambio de código para esa
parte del pedido, solo confirmarlo.

Tests: `tests/test_gui_reservas.py` —
`test_regulares_detalle_termina_cerca_del_pie_de_eliminar_reserva_
con_grilla_cargada` (docstring y assert actualizados: el gap que queda
arriba del cuadro ahora tiene que ser comparable a UN TERCIO del alto
del cuadro, no a su alto completo — 3/4 cuadro, 1/4 espacio → espacio =
cuadro/3) — el resto de los tests de Reservas regulares, incluido el
escenario denso y el de la tabla de abajo, siguen pasando sin cambios.

## Archivado de contexto (CLAUDE.md → este archivo)

Pedido explícito de la clienta, cerrando por ahora la revisión de
Reservas regulares: "archivá en los md correspondiente, y limpiá
contexto innecesario en CLAUDE.md de todos los hilos que tratamos
ultimamente para arrancar de cero con otras tareas". Movido de
CLAUDE.md a este archivo (manteniendo el orden cronológico original):
el hilo "Reservas aisladas: check 'Mostrar todas las reservas'" (antes
mezclado con dos puntos de Pagos, que se quedaron en CLAUDE.md bajo su
propio hilo, "Hilo cerrado: Pagos"), la sección completa de "Mensaje
'DETALLE RESERVA {MES}'", el rename del check de Aisladas + el arranque
de la revisión de Reservas regulares (antes mezclados con tres puntos
sueltos de Profesionales/catálogos genéricos/badge de período, que se
quedaron en CLAUDE.md bajo "Batch de 3 pedidos sueltos"), la sección
completa de "Reservas aisladas imputadas al mes siguiente", y las
rondas 1 a 10 enteras de Reservas regulares (todo lo que vivía bajo
"## Reservas regulares: ..." en CLAUDE.md). Los docstrings/comentarios
de `app/gui/pantallas/reservas.py` que apuntaban a "CLAUDE.md" para
este contexto se actualizaron para apuntar acá.
