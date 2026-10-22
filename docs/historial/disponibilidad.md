# Historial archivado — Disponibilidad: Oferta de consultorios, Lista de espera, Archivos para enviar

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

## Oferta de consultorios (formato solapa, botones unificados)

Pasó del `QSplitter` suelto (formulario / grilla operativa de referencia
/ detalle) a formato solapa: una sola pestaña "Nueva búsqueda"
(`panelSolapa` dentro de `QScrollArea`, `setDrawBase(False)`/`NoFrame`
como el resto) que envuelve ese mismo splitter tal cual estaba — no se
tocó la distribución interna (formulario a la izquierda, grilla de
referencia con sus propios filtros al medio, detalle a la derecha),
solo se le puso el marco de solapa por fuera. Se sacó el `QLabel`
"Nueva búsqueda" (`subtituloSeccion`) que quedaba adentro del
formulario: quedaba redundante contra el nombre de la solapa.

Los tres botones de abajo del formulario (`Generar PDF`, `Generar texto
WhatsApp`, `Nueva búsqueda`) usaban `botonAccion`/`botonDestacado` —
convención vieja, de antes de que se estandarizaran `botonPrimario`/
`botonSecundario`. Primero pasaron los tres a `botonSecundario` (ninguno
resaltado); en la siguiente ronda la clienta pidió puntualmente
`botonPrimario` para "Nueva búsqueda" (es la acción que arranca todo de
nuevo, la más "definitiva" de las tres), así que quedó: "Generar PDF" y
"Generar texto WhatsApp" en `botonSecundario`, "Nueva búsqueda" en
`botonPrimario` — mismo ancho fijo los tres (`_ANCHO_BOTON_ACCION =
220`), el estilo no cambia el ancho.

La cadena de foco de este formulario ya bajaba de arriba a abajo y
recorría de izquierda a derecha las filas con más de un control
(fechas Desde/Hasta, la grilla de checks de Días, horario, etc.) desde
antes de esta revisión — quedó confirmado que ya cumple la regla
general de foco (ver más arriba) sin tocar nada del armado de
`instalar_enter_avanza_foco`; el `showEvent` que ya tenía (enfoca
Profesional) sigue funcionando igual con la solapa nueva porque
`PantallaOferta` es la pantalla completa, no el contenido de una
pestaña individual (a diferencia de Reservas/Liquidación, donde cada
panel-solapa tiene su propio `showEvent`).

Mismo criterio aplicado de una en Liquidación mensual
(`_PanelEmisionArchivos`): "Calcular" (sin estilo antes) y los tres
"Emitir..." (`botonAccion`) pasan todos a `botonSecundario`, ancho fijo
`_ANCHO_BOTON_EMISION = 275` — hubo que subir `_ANCHO_PANEL_FILTROS` de
280 a 300 porque "Emitir liquidaciones seleccionadas" no entraba en el
ancho de botón que hacía falta dentro del panel viejo.

Como resultado de las dos migraciones no quedó ningún botón usando
`botonAccion`/`botonDestacado` en todo el sistema, esas dos reglas se
sacaron de `estilos.py` (muertas, no las usaba nadie más) — si en algún
momento hace falta un tercer nivel de énfasis de botón además de
`botonPrimario`/`botonSecundario`, se define de nuevo ahí mismo en vez
de reactivar las viejas.

## Archivos varios (formato solapa, elegir/ver separado de regenerar)

Pasó de tres botones sueltos en una fila (sin formato solapa, sin
`showEvent`) al formato estándar: solapa única "Documentos"
(`panelSolapa`/`QScrollArea`, `setDrawBase(False)`/`NoFrame` como el
resto), columna izquierda con el subtítulo explicativo y los botones,
columna derecha con un cuadro "Vista previa".

Los primeros tres botones ("Propuesta", "Disponibilidad", "Manual del
usuario" — antes "Regenerar Propuesta"/etc., `botonSecundario`)
cambiaron de comportamiento en una segunda vuelta de esta pantalla: ya
NO regeneran nada, solo eligen qué documento mirar
(`self._tipo_seleccionado`) y muestran en Vista previa el primer
archivo que YA existe en su subcarpeta (`_primer_archivo_existente`,
ordena por nombre y devuelve el primero — Propuesta/Disponibilidad
arman uno por localidad) sin generar nada nuevo. Un cuarto botón,
"Regenerar documento" (`botonPrimario` — pedido explícito de la
clienta: es la única de las cuatro acciones que efectivamente escribe
algo), llama al generador sobre el tipo elegido con los otros tres y
refresca la Vista previa con el resultado. Separar "elegir/ver" de
"regenerar" evita que simplemente mirar qué hay cargado dispare, de
paso, una regeneración no pedida. Los cuatro comparten un mismo ancho
fijo (`_ANCHO_BOTON = 200`, recalculado para las etiquetas más cortas
de esta vuelta — la más larga ahora es "Regenerar documento").
`showEvent` enfoca "Propuesta" al entrar a la pantalla, y una cadena
`instalar_enter_avanza_foco` explícita ([Propuesta → Disponibilidad →
Manual del usuario → Regenerar documento], con vuelta al principio)
cubre la regla general de foco de arriba a abajo — antes de esta vuelta
no había cadena armada, solo el orden nativo de Tab.

La Vista previa reusa `_pixmap_primera_pagina_pdf` de
`app/gui/pantallas/imagenes.py` (import directo del helper privado,
mismo criterio que otros imports cruzados del sistema, ej.
`_opciones_profesional`/`_texto_profesional` de `reservas.py`), que
ahora acepta un parámetro `escala` (default 0.6, sin tocar el
comportamiento de Gestor de archivos) — Archivos varios pide
`escala=1.3` para que se vea más grande y clara en su cuadro, más ancho
que el de esa otra pantalla. El pixmap además se escala con
`QPixmap.scaledToWidth` al ancho disponible del viewport (menos 24px de
margen, reservados para cuando aparece la barra de scroll vertical —
sin ese margen, la barra le come ancho al viewport recién DESPUÉS de
escalar y aparece una horizontal de sobra) y se fija con
`etiqueta_preview.setMinimumSize(pixmap.size())`: sin esto, el
`QScrollArea` (`widgetResizable=True`) achica la etiqueta al alto del
viewport y la imagen queda recortada en vez de poder bajarla con la
barra — forzar el mínimo al tamaño real de la imagen es lo que habilita
el scroll vertical. Si PyMuPDF no está instalado, o no hay ningún
archivo generado todavía, cae a un mensaje de texto en el mismo cuadro
en vez de romper — mismo criterio de "vista previa opcional" que Gestor
de archivos.

## Disponibilidad: Oferta de consultorios, columna angosta y grilla como en Reservas

Pedido de la clienta al revisar las capturas de "Disponibilidad": de las
tres solapas, solo "Oferta de consultorios" necesitaba ajustes ("las
otras dos están bien"). Cuatro pedidos sobre esa solapa:

- **Fondo del panel más claro (mismo tono que la solapa activa).** Mismo
  bug ya documentado en "Panel izquierdo gris en vez de blanco" (ver más
  arriba): `contenido` (el widget que se pasa a `scroll.setWidget(...)`)
  nunca tenía `objectName="panelSolapa"` puesto en esta pantalla — a
  diferencia de Reservas/Llaves, donde ya se había corregido. Se suma
  `contenido.setObjectName("panelSolapa")`, mismo criterio exacto que
  esas dos pantallas (alcanza con que lo tenga `contenido`, la cascada
  llega sola a `panel_form`/la grilla, sin tocar ningún widget nested).
- **Columna del formulario más angosta, ancho liberado a Filtros y a la
  grilla.** Medido con un script de geometría (mismo criterio de todo
  este apartado): antes de este cambio la columna medía 690px de
  sizeHint, dominada por la fila horizontal de los tres botones de
  acción ("Generar PDF"/"Generar texto WhatsApp"/"Nueva búsqueda", 220px
  cada uno, 660px sumados) — ninguno de los otros widgets del formulario
  se acercaba a esa medida. Se resolvió apilando verticalmente (mismo
  criterio que Reservas: `form.addWidget(boton)` uno debajo del otro, en
  vez de una fila con `QHBoxLayout`) las tres filas de botones/campos
  que hasta ahora iban horizontales sin necesitarlo: los tres botones de
  acción, "Agregar franja"/"Quitar franja" (189+172px lado a lado) y
  "Desde"/"Hasta (solo Aislada)" (432px de sizeHint entre los dos
  `QDateEdit`, sus etiquetas y los dos `addStretch()` — pasan a formato
  "etiqueta arriba, campo abajo", mismo criterio que "Vigencia desde"/
  "Vigencia hasta" en Reservas). De paso se envolvió con `setWordWrap`
  la etiqueta larga "Franjas agregadas a esta búsqueda..." (623px sin
  wrap) y se le sumó un salto de línea al checkbox "Cantidad de horas
  dentro del rango (en vez del rango completo)" (411px sin wrap, mismo
  mecanismo que el checkbox de reubicación de Reservas aisladas). La
  columna quedó en 370px de sizeHint (46% menos que los 690px
  originales) — el ancho liberado se lo lleva la grilla de al lado (de
  806px a 1112px), repartido entre `agrandar_panel_filtros(290)` (mismo
  valor que Reservas, antes 260px default) y el resto directo a
  `panel_grilla` (`stretch=1`, crece solo).
- **Filtros/días/referencias de la grilla como en Reservas.** La grilla
  embebida ("Grilla semanal", la referencia visual mientras se arma la
  búsqueda) llamaba `mostrar_leyenda_colores()` sin `compacta=True` y
  nunca llamaba `agrupar_dias_en_pares()` — quedaba con el criterio
  "grande" que usa Vista rápida en vez del compacto que ya usan las dos
  solapas de Reservas. Se suman las dos llamadas (`agrupar_dias_en_
  pares()`, `mostrar_leyenda_colores(compacta=True)`) junto con
  `agrandar_panel_filtros(290)` de arriba — las tres, opt-in, no afectan
  al resto de los usos de esta grilla compartida (Novedades, Grilla
  semanal de "Grilla y mensajería"). No se tocó `fijar_titulo_filtros`
  (sigue en "Grilla semanal", no en vacío) ni `renombrar_etiquetas_
  filtro()`: a diferencia de Reservas, acá el título describe la grilla
  entera como referencia visual, no un simple "Filtros" — la clienta no
  pidió sacarlo. El modo (Regular/Aislada) ya venía resuelto por
  `fijar_modo` según el "Tipo de búsqueda" elegido, y la leyenda ya
  cambiaba de referencias sola al cambiar de modo (la señal de `combo_
  modo` ya estaba conectada) — confirmado con un test nuevo, no hizo
  falta ningún cambio ahí.
- **Comentario sobre visualización**: apilar las tres filas horizontales
  (para angostar la columna) las volvió más ALTAS — el sizeHint vertical
  del formulario subió de 854px a 1031px. Contra una ventana de
  referencia (1500×850, la misma que usan las capturas), eso deja
  aproximadamente 270-310px de contenido por debajo del borde inferior
  visible sin scrollear (confirmado con un script de geometría: el botón
  "Nueva búsqueda", al final de la columna, termina en y=987 dentro del
  contenido scrolleable, contra un viewport de 720px) — hay que
  scrollear para llegar a "Detalle reducido", "Generar texto WhatsApp"/
  "Generar PDF" y "Nueva búsqueda". El panel ya tiene su `QScrollArea`
  propio de siempre (nada se corta ni queda inaccesible), pero conviene
  que la clienta lo sepa antes de dar esta vuelta por cerrada: angostar
  la columna trasladó parte de lo que antes se leía de un vistazo a
  scroll vertical.

Tests nuevos en `test_gui_oferta.py`: `test_contenido_dentro_del_scroll_
tiene_fondo_claro` (mismo criterio que Reservas/Llaves — cuenta
descendientes con `objectName() == "panelSolapa"`), `test_columna_del_
formulario_mas_angosta_que_antes`, `test_filtros_dias_y_referencias_
como_en_reservas`, `test_leyenda_cambia_de_referencias_segun_el_tipo_
de_busqueda`. El viejo `test_fecha_queda_pegada_a_su_etiqueta_sin_hueco`
(sobre la fila horizontal de fechas que ya no existe) se reescribe como
`test_fechas_desde_hasta_apiladas_en_vez_de_una_fila`, recorriendo el
layout en vez de buscar por texto (ambigüo: "Desde" se repite entre la
fila de fecha y la de horario).

### Segunda vuelta: reversiones, "Con placard" nuevo, botones al panel de Filtros

Pedido explícito de la clienta sobre la captura de la primera vuelta,
solo para "Oferta de consultorios" (Regular primero, "algo similar
sería para aislada... pero vamos con regular primero, luego vamos a
fondo con lo otro" — Aislada queda pendiente para una vuelta futura):

- **Regla general nueva: "prefiero siempre que los cuadros y tablas...
  sean escroleables y no la pantalla en sí".** Mismo tipo de regla
  general que "Foco (Enter/Tab): orden general" o "Selectores y fecha"
  más arriba — se aplica de acá en adelante, no dispara un barrido
  completo del sistema. Para esta pantalla puntual: "Franjas agregadas
  a esta búsqueda" (`lista_franjas`) pasa de un alto máximo fijo (90px)
  a `stretch=1` sin tope — crece hasta el pie de la columna en vez de
  quedar corta, y sigue teniendo su scroll propio de `QListWidget` para
  cuando hay más franjas de las que entran. Efecto medido con un script
  de geometría (ventana de referencia 1500×850, la misma de las
  capturas): el scroll de la pantalla completa (el `QScrollArea` externo
  de siempre) baja de ~270-310px de contenido oculto (medido en la
  primera vuelta) a solo 37px — no queda en cero (el piso real de
  `lista_franjas`, sumado a los márgenes de siempre, no da para más sin
  tocar otra cosa), pero la reducción es sustancial.
- **Se revierten dos apilados de la primera vuelta**: "Desde"/"Hasta
  (solo Aislada)" (la fecha) y "Agregar franja a la búsqueda"/"Quitar
  franja seleccionada" vuelven a su fila horizontal original, pedido
  explícito ("que estén en la misma fila", "a la par en la misma
  altura") — el ancho que esto le devuelve a la columna (`panel_form`
  pasa de 370px a 450px de sizeHint) se compensa de sobra con el punto
  siguiente.
- **Los tres botones de acción se mudan al panel de Filtros de la
  grilla**, debajo de "Referencias de colores" — pedido explícito
  ("Los tres botones ponelos uno arriba del otro al lado, abajo de las
  referencias de colores"), en el mismo orden de siempre (Generar PDF →
  Generar texto WhatsApp → Nueva búsqueda). Esto es lo que realmente
  angosta la columna del formulario (ya no cargan sus 660px de ancho
  ahí) y libera además todo el alto que ocupaban al pie de esa columna.
  Método nuevo en `GrillaOperativaWidget`, `agregar_widgets_debajo_de_
  leyenda(*widgets)` (opt-in, no afecta al resto de los usos de esta
  grilla compartida): inserta los widgets en `layout_filtros` justo
  antes del `addStretch()` final, así ese stretch sigue absorbiendo el
  resto del alto disponible después de ellos en vez de quedar
  "atrapado" entre la leyenda y los botones nuevos. Los botones se
  siguen construyendo en `_PanelOferta._armar_ui` (mismos métodos
  `self._generar_pdf`/etc., sin cambios) y quedan en la misma cadena de
  foco Enter/Tab de siempre — `instalar_enter_avanza_foco` instala el
  filtro por widget, no le importa de qué widget sean hijos, así que
  moverlos de padre no rompe el orden de Tab.
- **"Características pedidas" pasa a una grilla de 2 columnas por
  pares**, con un checkbox nuevo, "Con placard" — pedido explícito
  sobre el orden exacto: fila 1 "Con ventana"/"Apto camilla", fila 2
  "Con sillones"/"Con placard", fila 3 "Tamaño" + su combo, fila 4
  "Valor máximo por hora regular" + su spin. `Consultorio.Placard` ya
  existía en el schema (booleano, editable desde el catálogo de
  Consultorios) pero nunca se había conectado como criterio de
  búsqueda de Oferta — `Busqueda` (`app.negocio.oferta_busqueda`) suma
  el campo `placard: bool = False` y `_consultorios_candidatos` suma el
  filtro (`if busqueda.placard and not c["Placard"]: continue`), mismo
  patrón exacto que `apto_camilla`/`ventana`/`sillones`. Ninguna otra
  parte del sistema menciona estas características por su nombre (ni
  el resumen de franja, ni los PDF/texto generados), así que no hizo
  falta tocar nada más allá del filtro en sí.
- **"Detalle reducido" sube de posición**: pasa a vivir justo después
  de "Combinación con la próxima franja" y antes de "Agregar franja"/
  "Quitar franja" (antes estaba al final, justo arriba de los tres
  botones que ahora se mudaron) — interpretación propia ante la
  ambigüedad (la clienta no lo mencionó explícitamente en esta vuelta):
  como "Franjas agregadas a esta búsqueda" tiene que quedar como el
  último elemento de la columna (el que "llega al pie de la pantalla"),
  "Detalle reducido" no podía quedar después de esa lista.
- **"Franjas agregadas a esta búsqueda" pierde la aclaración entre
  paréntesis** ("si no agregás ninguna, se usa lo cargado arriba como
  franja única") — pedido explícito: "asi el título nomás". El
  comportamiento que describía esa aclaración no cambió, solo el texto.

Tests: `tests/test_oferta_busqueda.py` suma `test_placard_filtra_
candidatos` (mismo criterio que `test_sillones_y_tamano_filtran_
candidatos`). `test_gui_grilla_operativa.py` suma
`test_agregar_widgets_debajo_de_leyenda_quedan_despues_y_antes_del_
stretch`. `test_gui_oferta.py`: el de "apiladas" de la primera vuelta
se reemplaza por `test_fechas_desde_hasta_en_la_misma_fila` (compara
posición vertical); el de `lista_franjas` con alto fijo se reemplaza
por `test_lista_franjas_crece_hasta_el_pie_y_es_scroleable` (stretch=1,
sin tope de alto); el de ancho de columna actualiza su umbral (de <450
a <500, ahora por un motivo distinto: ya no son los tres botones los
que se sacaron, sino la fila de fechas que volvió); se suman
`test_agregar_y_quitar_franja_en_la_misma_fila`,
`test_etiqueta_franjas_agregadas_sin_texto_explicativo`,
`test_caracteristicas_pedidas_en_grilla_de_pares_con_placard` (compara
posiciones de fila/columna vía `grid.getItemPosition`, comparando
contra `pantalla._grid_caracteristicas` — nuevo atributo, necesario
porque el grid es un layout anidado dentro de `form`, no el layout
propio del widget padre de los checkboxes),
`test_placard_se_incluye_en_la_busqueda_armada`,
`test_botones_de_accion_viven_en_el_panel_de_filtros_de_la_grilla`.

### Tercera vuelta: sin título en la grilla, Profesional/Localidad alineados, Detalle pegado, "Hasta" más corto

Cuatro pedidos más de la clienta sobre "Oferta de consultorios" (siempre
Regular; Aislada sigue pendiente para más adelante):

- **Se saca el título "Grilla semanal"** del panel de Filtros de la
  grilla — `self.grilla.fijar_titulo_filtros("")`, mismo criterio que
  Reservas.
- **"Profesional" alineado con "Localidad".** Con el título sacado,
  "Localidad" (primer filtro del panel de Filtros, ya sin `renombrar_
  etiquetas_filtro()` en esta pantalla — sigue diciéndose "Localidad",
  no "Filtro de localidad") quedaba 6px más abajo que "Profesional"
  (primer campo de la columna del formulario) — medido con un script de
  geometría, no a ojo. A diferencia de Reservas (que parte de un margen
  superior en 0 para `form`), acá `form` nunca tuvo márgenes propios
  seteados — seguía con el default de Qt (9px) — así que alcanzó con
  subir el margen superior de `form` de 9 a 15px (`form.
  setContentsMargins(9, 15, 9, 9)`) para igualar las dos alturas exacto
  (confirmado: las dos etiquetas quedan al mismo `y` global).
- **"Detalle" pegado debajo de la grilla.** Mismo método opt-in que ya
  usa Reservas regulares, `self.grilla.dar_stretch_a_detalle()`: le
  saca el `stretch` a la tabla de la grilla (que se estiraba con
  relleno vacío hasta el pie de la columna) y se lo pasa al cuadro
  "Detalle", que ahora crece en su lugar — la tabla termina justo donde
  termina su contenido real, con "Detalle" inmediatamente debajo (el
  separador que queda es el spacing default de `layout_grilla`, 6px,
  mismo residual que ya acepta Reservas regulares para este mismo
  método, no se tocó).
- **"Hasta (solo Aislada)" pasa a "Hasta"** — pedido explícito, el
  comportamiento no cambia: sigue deshabilitado (gris) en modo Regular
  vía `_al_cambiar_tipo`, la aclaración entre paréntesis solo describía
  ese comportamiento en el texto, no lo cambiaba.
- **Ancho liberado a la segunda columna.** Acortar esa etiqueta bajó el
  sizeHint de `fila_fechas` (la fila que más pesaba en el ancho de la
  columna desde que "Agregar franja"/"Quitar franja" volvió a su fila
  horizontal) y con eso el de toda la columna, de 450px a 385px —
  `_ANCHO_PANEL_FILTROS_GRILLA` sube de 290 a 355 (mismo criterio que
  la primera vuelta: el ancho liberado en la columna del formulario se
  lo lleva el panel de Filtros de la grilla) para no dejarlo como
  espacio libre sin repartir.

Tests nuevos en `test_gui_oferta.py`: `test_etiqueta_hasta_sin_
aclaracion_de_aislada`, `test_profesional_alineado_con_localidad_de_la_
grilla`, `test_detalle_pegado_debajo_de_la_grilla_sin_relleno`,
`test_panel_filtros_de_la_grilla_mas_ancho`. El de "tiene título Grilla
semanal" se reescribe como `test_grilla_embebida_sin_titulo`.

### Cuarta vuelta: cuatro columnas (formulario / franjas+botones /
### filtros+referencias / grilla+Detalle)

Pedido explícito de la clienta, la reestructuración más grande de esta
solapa hasta ahora — sigue siendo Regular nomás, Aislada continúa
pendiente ("vamos con regular primero"):

- **"Agregar franja a la búsqueda"/"Quitar franja seleccionada" a dos
  líneas de texto.** `"Agregar franja\na la búsqueda"`/`"Quitar
  franja\nseleccionada"` (mismo mecanismo de salto de línea manual que
  `casilla_reubicacion` en Reservas aisladas) — más altos, y de paso más
  angostos (cada línea es más corta que el texto de una sola línea de
  antes), lo que termina de angostar la primera columna.
- **Segunda columna, nueva: "Franjas agregadas a esta búsqueda".** Lo
  que hasta la ronda anterior era el final de la primera columna
  (título + `lista_franjas`) pasa a vivir en un `panel_franjas` propio,
  agregado como segundo widget del `QSplitter` — junto con los tres
  botones de acción (`Generar PDF`/`Generar texto WhatsApp`/`Nueva
  búsqueda`), que la ronda anterior había mudado al panel de Filtros de
  la grilla y ahora se reubican acá, al pie de esta columna. Mismo
  mecanismo de siempre para "empujar algo al pie de una columna":
  `lista_franjas` es lo único con `stretch=1` en `columna_franjas` (el
  `QVBoxLayout` de este panel), así que absorbe todo el alto sobrante y
  cualquier widget agregado después de ella (los tres botones) queda
  pegado contra el borde inferior.
- **Tercera columna: Filtros + Referencias de colores, en una sola
  línea cada uno.** Se revierten los dos cambios "compactos" de la
  ronda anterior: `agrupar_dias_en_pares()` deja de llamarse (los días
  vuelven a una lista vertical, un check por línea) y `mostrar_leyenda_
  colores(compacta=True)` pasa a `mostrar_leyenda_colores()` (una sola
  columna de referencias, tamaño normal en vez del compactado a 2
  columnas). Como en esta ronda la columna de Filtros pasa a tener un
  ancho FIJO en vez de solo un tope (ver el bug de abajo), y la
  clienta pidió que las referencias "terminen al pie de la tercera
  columna", se agranda un poco la muestra de color (`agrandar_muestras_
  leyenda`, +6px de alto) y la letra (14px, un punto arriba del default
  de toda la app) — un residuo de ~3px entre el pie de esta columna y
  el de la primera quedó irreductible (confirmado probando varios
  valores de tamaño: agrandar la leyenda agranda por igual a la columna
  del formulario, que no tiene un alto "natural" fijo — ver el hallazgo
  de abajo — así que la brecha nunca se cierra del todo), aceptado como
  el mismo tipo de resto imperceptible que otras rondas de esta
  revisión.
- **Cuarta columna: la grilla escroleable + "Detalle" al pie del
  formulario.** Sin cambios de código nuevos acá — `dar_stretch_a_
  detalle()` (ya sumado en la ronda anterior) ya hacía exactamente esto:
  confirmado con un script de geometría que el borde inferior de
  "Detalle" coincide EXACTO (0px de diferencia) con el borde inferior
  de la primera columna, en cualquier tamaño probado.

**Dos bugs reales, no pedidos, encontrados al armar esta vuelta:**

- **"Referencias de colores" con texto recortado arriba y abajo, bug ya
  presente en `mostrar_leyenda_colores()` sin `compacta`** (nunca se
  había usado en producción sin `compacta=True` antes de esta ronda —
  confirmado reproduciéndolo también fuera de Oferta, con cualquier
  llamado a `mostrar_leyenda_colores()` a secas). Causa: `QLabel.
  sizeHint()` con `wordWrap=True` devuelve el alto de una sola línea SIN
  WRAPEAR (Qt no conoce el ancho final de la columna en ese momento), y
  `QGridLayout` arma la fila con ESE alto — con una descripción que
  necesita 2-3 líneas al ancho real de la columna, la fila queda más
  baja de lo que hace falta y, como `QLabel` alinea verticalmente al
  CENTRO por default (no arriba), el texto de más se recorta arriba Y
  abajo por igual, en vez de solo abajo (por eso se veía la mitad de
  cada descripción larga, con la primera y la última palabra cortadas).
  Arreglo: `LeyendaColores.fijar_ancho_etiqueta(ancho)` (nueva) calcula
  el alto real a mano con `QFontMetrics.boundingRect(...,
  TextWordWrap)` para ESE ancho puntual y lo fija con `setMinimumHeight`
  — no depende de que Qt vuelva a propagar el `sizeHint` después del
  wrap (que en la plataforma offscreen no siempre pasa, mismo
  `propagateSizeHints()` documentado en otras partes de esta grilla).
  `GrillaOperativaWidget.fijar_ancho_etiqueta_leyenda(ancho)` la expone
  — opt-in, sin afectar a Reservas (que sigue con `compacta=True`, texto
  corto, nunca disparó este bug).
- **El panel de Filtros de la grilla nunca llegaba a su ancho "máximo".**
  `agrandar_panel_filtros` solo pone un TOPE (`setMaximumWidth`): sin
  ningún `stretch` propio en el `QHBoxLayout` interno de la grilla
  (Filtros | grilla), este panel se quedaba en su ancho NATURAL
  (~190px, mucho menos que el tope) y toda la grilla (columna 4) se
  llevaba el resto — nadie lo había notado en rondas anteriores porque
  ahí el tope solo servía para no restringir de más un ancho que ya
  salía generoso solo. Acá sí hacía falta que el panel ocupara ese
  ancho de verdad, para que "Referencias de colores" tuviera sitio real.
  Arreglo puntual de esta pantalla (no tocado en `grilla_operativa.py`,
  que sigue sirviendo solo de tope para el resto de los usos):
  `self.grilla._panel_filtros.setMinimumWidth(_ANCHO_PANEL_FILTROS_
  GRILLA)`, dejándolo fijo (mínimo = máximo) en vez de solo topeado.
  `_ANCHO_PANEL_FILTROS_GRILLA` baja de 355 (ronda anterior, un tope que
  nunca se alcanzaba) a 250 (ahora sí un ancho real): con las cuatro
  columnas de esta vuelta, forzarlo a 355 de verdad le sacaba demasiado
  lugar a la grilla (columna 4) y disparaba scroll horizontal de toda la
  pantalla en vez de solo de la tabla.

**Hallazgo de geometría, documentado para no repetir el error:** la
primera columna (el formulario) NO tiene un alto "natural" fijo — sus
widgets (combos, checks, etc., con política de tamaño "Preferred") se
reparten cualquier alto de sobra que el `QSplitter` le imponga, en vez
de quedarse en su alto mínimo con hueco vacío al final. Esto significa
que agrandar CUALQUIER otra columna (ej. la leyenda de "Referencias de
colores") sube el alto de TODO el splitter, y la primera columna sube
con él en la misma medida — confirmado con un script de geometría
probando varios tamaños de muestra: el "pie" de la primera columna y el
de la leyenda suben exactamente lo mismo, así que la brecha entre
ambos nunca se cierra agrandando la leyenda. Para "hacer que algo
llegue al pie de una columna" hay que usar `stretch=1` en un widget de
ESA columna (como hace `dar_stretch_a_detalle`/`lista_franjas` en la
columna de franjas), no agrandar el contenido de otra columna esperando
que la brecha se achique.

Tests nuevos: `test_gui_grilla_operativa.py` suma
`test_fijar_ancho_etiqueta_leyenda_agranda_las_filas_que_wrappean`
(confirma que el bug de arriba queda cubierto) y `test_fijar_ancho_
etiqueta_leyenda_no_afecta_si_no_se_llama` (opt-in, Reservas no se ve
afectada). `test_gui_oferta.py` suma `test_pantalla_tiene_cuatro_
columnas`, `test_columna_de_franjas_tiene_titulo_lista_y_tres_botones_
al_pie`, `test_referencias_de_colores_sin_texto_recortado` y
`test_panel_filtros_de_la_grilla_ancho_fijo` (reemplaza a `test_panel_
filtros_de_la_grilla_mas_ancho`, que comparaba contra el tope viejo de
355). `test_botones_de_accion_viven_en_el_panel_de_filtros_de_la_grilla`
se reescribe como `test_botones_de_accion_viven_al_pie_de_la_columna_de_
franjas` (los botones ya no viven en Filtros). `test_filtros_dias_y_
referencias_como_en_reservas` se reescribe como `test_filtros_dias_y_
referencias_en_una_sola_linea` (justo lo contrario del criterio de la
ronda anterior). `test_columna_del_formulario_mas_angosta_que_antes` y
`test_lista_franjas_crece_hasta_el_pie_y_es_scroleable` se actualizan
para el nuevo lugar de `lista_franjas` (su propia columna, no ya el pie
del formulario).

### Quinta vuelta: Aislada tratada igual que Regular, y un bug de fondo
### en el tamaño de letra de la leyenda

Pedido explícito de la clienta: "vamos tipo de búsqueda aisladas de
manera similar a esta pantalla de regulares" — Oferta de consultorios no
tiene solapas separadas por tipo (a diferencia de Reservas): "Regular"/
"Aislada" es un solo combo (`combo_tipo`) sobre el mismo `_PanelOferta`,
así que "tratar Aislada igual" significa que el ajuste de tamaño de
"Referencias de colores" (columna 3) tiene que funcionar bien para las
dos, cambiando en caliente cada vez que se cambia el combo — no hay una
segunda pantalla que revisar aparte.

Diagnóstico: Aislada tiene 6 referencias contra las 8 de Regular — con
el mismo tamaño de muestra/letra que se había fijado para Regular (fijo,
una sola vez, en `_armar_ui`), Aislada dejaba un hueco en blanco grande
al pie de la columna de Filtros (menos filas, mismo alto total
disponible). `_ajustar_tamano_leyenda(tipo)` (nueva, en `_PanelOferta`)
resuelve esto aplicando un juego de valores de tamaño DISTINTO por tipo
— `_AJUSTE_ALTO_MUESTRA_LEYENDA_REGULAR`/`_TAMANO_FUENTE_LEYENDA_
REGULAR` y sus pares `..._AISLADA` (más grandes, para repartir el mismo
alto entre menos filas) — y se llama desde `_al_cambiar_tipo()`, justo
después de `self.grilla.fijar_modo(...)`, así que se re-aplica cada vez
que el combo "Tipo de búsqueda" cambia.

**Bug de fondo, no pedido, encontrado al armar esto** (y que en
retrospectiva ya afectaba un poco a la ronda anterior, sin llegar a
notarse): el tamaño de letra de la leyenda se venía fijando con
`self.grilla._leyenda_colores.setStyleSheet(f"QLabel {{ font-size:
Npx; }}")` — un `setStyleSheet` de CSS cambia lo que Qt PINTA pero NO lo
que devuelve `QLabel.font()`. Como `fijar_ancho_etiqueta_leyenda` mide
el alto necesario con `QFontMetrics(etiqueta.font())`, ese cálculo
seguía usando la letra VIEJA (la del tipo anterior, o el default de la
app si era la primera vez) mientras Qt terminaba pintando con la letra
NUEVA, más grande — el texto quedaba recortado arriba y abajo (`QLabel`
centra verticalmente por default), el mismo síntoma que el bug de ancho
resuelto en la ronda anterior, pero por una causa distinta. Se hizo
visible recién en esta vuelta porque antes Regular usaba un tamaño de
letra parecido al default (14px contra ~13px reales) — la diferencia
era chica y no llegaba a notarse — mientras que Aislada, con menos
filas, necesitaba un salto más grande (15px) que sí generó un recorte
visible.

Arreglo de fondo en `grilla_operativa.py` (no solo un parche de esta
pantalla): `LeyendaColores.fijar_tamano_fuente(puntos)` (nueva, mismo
criterio que `fijar_tamano_muestra`) guarda un tamaño de letra en píxeles
que `actualizar()` aplica con `QLabel.setFont` (no CSS) ANTES de medir
con `QFontMetrics` — así la letra que se mide es la misma que la que
Qt termina pintando, sin necesitar ningún orden particular de llamadas
para que coincidan. `GrillaOperativaWidget.fijar_tamano_fuente_leyenda`
la expone, opt-in — Reservas (que sigue con `hacer_compacta()` y su
`setStyleSheet` de toda la vida, sin haber tenido nunca este problema
porque su texto es corto y nunca dispara wrap) no se ve afectada.
`_PanelOferta._ajustar_tamano_leyenda` pasa a llamar `self.grilla.
fijar_tamano_fuente_leyenda(...)` en vez del `setStyleSheet` crudo.

**Efecto colateral real, no cosmético, de corregir la medición**: una
vez que el alto se calcula con la letra REAL (más alto del que se
pensaba, en los dos tipos), la pantalla completa necesitaba más alto
total del que entraba en la ventana de referencia (1500×850) sin
scrollear — confirmado con un script de geometría: la primera columna
(el formulario) no tiene un alto "natural" fijo, así que crecer
CUALQUIER otra columna sube el alto de todo el splitter parejo (mismo
hallazgo documentado en la ronda anterior). Se resolvió en tres pasos:
- `_ANCHO_PANEL_FILTROS_GRILLA` sube de 250 a 280 y el ancho de
  referencia para el wrap (`fijar_ancho_etiqueta_leyenda`) de 180 a 220
  — más ancho por línea, menos líneas de wrap, menos alto total pedido
  por columna (a costa de un poco más de scroll horizontal en la
  columna 4, de ~21px a ~51-65px según el tipo — aceptado, "la grilla
  escroleable" ya lo contemplaba).
- Con eso, Regular (a su tamaño de letra/muestra mínimo, sin ningún
  agrandado artificial) ya entra sin scroll vertical, con un residuo de
  9px entre el pie de la leyenda y el pie de la columna 1 — más grande
  que el 3px de la ronda anterior, pero imperceptible igual, y
  preferible a agrandar más y volver a necesitar scroll vertical.
- Aislada sube su propio juego de valores (`_AJUSTE_ALTO_MUESTRA_
  LEYENDA_AISLADA = 20`, `_TAMANO_FUENTE_LEYENDA_AISLADA = 15`, contra
  0/13 de Regular) hasta emparejar el mismo residuo de 9px que Regular
  — confirmado con el mismo script de geometría, iterando el valor
  hasta que los dos números de "gap" coincidieran.

Tests nuevos: `test_gui_grilla_operativa.py` suma `test_fijar_tamano_
fuente_leyenda_usa_setfont_no_solo_estilo` (confirma que el tamaño de
letra puesto ahí es el mismo que mide `QFontMetrics` después, en las dos
direcciones — letra más grande y más chica). `test_gui_oferta.py` suma
`test_leyenda_se_agranda_mas_en_aislada_que_en_regular` (compara el alto
de muestra entre los dos tipos) y `test_leyenda_de_aislada_sin_texto_
recortado` (mismo criterio que el test de Regular de la ronda anterior,
aplicado a Aislada).

### Sexta vuelta: sin scroll horizontal del formulario, domingo en el
### filtro de días de la grilla, confirmaciones sobre franjas/Detalle/grilla

Seis pedidos de la clienta sobre la captura de la ronda anterior, la
mayoría de verificación/afinado más que de diseño nuevo:

- **Se saca la etiqueta "Visualización:".** La clienta notó scroll
  horizontal en el formulario y preguntó si era por el combo "Reservas
  regulares"/"Reservas aisladas" (siempre deshabilitado acá, lo maneja
  "Tipo de búsqueda") quedando cortado. Confirmado con un script de
  geometría: la fila "Período: [combo] Visualización: [combo]" (dentro
  de `GrillaOperativaWidget`, compartida por Reservas/Novedades/Grilla
  semanal) fijaba el ancho MÍNIMO de toda la columna 4 en 391px — mucho
  más que lo que la tabla en sí necesita (70px, ya que scrollea sola) —
  y ese mínimo, sumado al de las otras tres columnas, superaba el ancho
  disponible y forzaba scroll horizontal de TODA la pantalla.
  `GrillaOperativaWidget.quitar_etiqueta_visualizacion()` (nueva, opt-in
  — el resto de los usos de esta grilla compartida se quedan con la
  etiqueta) oculta la etiqueta y le pone `setMaximumWidth(0)`, bajando
  ese mínimo a 303px.
- **Regla general nueva: "no quiero que sea escroleable en horizontal
  los formularios en general, solo la grilla".** Con la etiqueta
  sacada, medido de nuevo: el scroll horizontal de toda la pantalla
  bajó a 0 (antes ~51-65px según el tipo) — la tabla (columna 4) pasa a
  ser lo único que scrollea horizontal cuando hace falta (su propio
  `horizontalScrollBar`, ya tenía `ScrollBarAsNeeded` de siempre), con
  el resto del formulario siempre visible. Mismo criterio que la regla
  general de Reservas de "los cuadros scrollean, no la pantalla" —
  ahora extendida explícitamente al eje horizontal.
- **Franjas/Detalle escrolean solo si hace falta.** Verificado (sin
  ningún cambio de código): `lista_franjas` (`QListWidget`) y
  `texto_detalle` (`QTextEdit`) nunca tuvieron un
  `setVerticalScrollBarPolicy` explícito — ya scrollean con el
  comportamiento nativo de Qt (`ScrollBarAsNeeded`), mostrando su barra
  solo cuando el contenido no entra.
- **Confirmación: si se suma el domingo a `_DIAS_BUSQUEDA` (el campo
  "Días" del formulario, columna 1), queda Lunes/Martes/Miércoles/
  Jueves arriba y Viernes/Sábado/Domingo abajo.** Confirmado
  matemáticamente y con un test que monkeypatchea la lista a 7 días:
  `math.ceil(len(dias)/2)` da 4 columnas para 7 días, y
  `i // columnas, i % columnas` deja exactamente esa distribución (4+3)
  sin necesitar ningún cambio de código — el mismo algoritmo que ya
  arma la grilla de 6 días (3+3) hoy. `_DIAS_BUSQUEDA` sigue siendo una
  constante fija de 6 días (Lunes a Sábado, no depende de ningún
  parámetro de sistema pese a su comentario) — esto es una confirmación
  a futuro, no algo alcanzable hoy desde la GUI.
- **Si el domingo está configurado en el filtro "Día de la semana" de
  la grilla (columna 3), pasa a 2 columnas con el domingo solo al
  final.** A diferencia del caso de arriba, este filtro SÍ es
  alcanzable hoy: sale de `app.negocio.grilla.dias_grilla(conn)`, que
  lee `Configuracion.DiasGrilla` (editable desde "Configuración
  general" — sección "Grilla y ocupación" → "Días de grilla") y puede
  incluir domingo. `self._domingo_en_filtro_dia = "Domingo" in self.
  grilla._checks_dia` se calcula una vez al construir la pantalla, y si
  da `True` se llama `self.grilla.agrupar_dias_en_pares()` (mismo
  método que ya usa Reservas) — con 7 días este mismo método dado dos
  columnas fijas ya deja al séptimo (domingo, si el resto sigue en
  orden de semana) solo en su propia fila, sin necesitar ningún caso
  especial para "el último impar". Confirmado con un test que arma una
  base con el domingo en `DiasGrilla` y revisa la posición exacta.
  De paso, `_ajustar_tamano_leyenda` suma `_AJUSTE_EXTRA_MUESTRA_CON_
  DOMINGO` (una constante más, sumada a la de Regular/Aislada) cuando
  `_domingo_en_filtro_dia` es `True` — con los días a pares ocupando
  menos alto que la lista de 7 líneas de antes, la leyenda necesita un
  empujón extra para seguir llegando al pie de la columna; medido con
  una base de prueba con el domingo configurado (no a ojo, aunque sin
  captura de pantalla para la clienta — hoy ningún cliente real tiene
  el domingo activado, así que esta parte queda verificada por
  geometría y tests, no revisada visualmente).
- **Si se agregan más horarios a la grilla, que se vea completa y el
  espacio de más lo ceda "Detalle".** Confirmado (sin cambio de
  código): `dar_stretch_a_detalle()`, ya sumado en una ronda anterior,
  ya resuelve esto — deja la tabla con `stretch=0` (fija a su alto
  natural, nunca se recorta) y "Detalle" con `stretch=1` (absorbe
  cualquier diferencia, cediendo alto si la tabla necesita más).
  Probado con un script de geometría extendiendo el horario de la
  grilla a 0-24hs con fracciones de 30 minutos (27 filas, más del doble
  de lo habitual): la tabla se sigue viendo completa
  (`verticalScrollBar().maximum()` prácticamente 0) y "Detalle" se
  achica de forma proporcional, sin que la pantalla necesite scroll
  vertical.

**Ajuste fino de constantes, downstream de sacar la etiqueta
"Visualización:"**: al liberar esos 88px de ancho mínimo en la columna
4, el reparto de alto entre columnas cambió (mismo hallazgo de "la
primera columna no tiene un alto natural fijo" documentado en la ronda
anterior) — `_AJUSTE_ALTO_MUESTRA_LEYENDA_REGULAR`/`..._AISLADA` se
reajustan (de 10/30 a 3/23) para seguir sin scroll vertical con el
dataset real que usa `shot_oferta.py` (que difiere un poco del dataset
mínimo de los tests, por eso hizo falta afinar de nuevo mirando la
captura real y no solo el script de medición).

Tests nuevos en `test_gui_oferta.py`: `test_sin_etiqueta_visualizacion_
en_la_grilla`, `test_formulario_no_escrolea_horizontal_solo_la_grilla`,
`test_dias_con_domingo_agregado_quedan_4_y_3`, `test_filtro_dia_a_pares_
con_domingo_configurado`, `test_grilla_nunca_se_recorta_con_mas_
horarios_detalle_cede_espacio`.

### Séptima vuelta: bug real detrás de las "letras cortadas" (ancho mal
### asumido, no el tamaño de letra) y la grilla tapada por su propio scroll

Dos pedidos más de la clienta sobre la misma pantalla:

- **"Reducí un poco la fuente de las referencias de los colores para que
  aparezcan los textos completos sin letras cortadas" (las dos solapas).**
  Investigado con el mismo criterio de medición de siempre, el recorte
  NO era un problema de tamaño de letra en sí — era un bug real en
  `fijar_ancho_etiqueta_leyenda`: la llamada pasaba 220px como ancho de
  referencia para calcular cuántas líneas necesita cada descripción al
  wrapear, pero el ancho REAL renderizado de esa etiqueta (medido con
  `QLabel.width()` ya mostrada en pantalla, el mismo en Regular y en
  Aislada porque solo depende de `_ANCHO_PANEL_FILTROS_GRILLA`, no de la
  letra) es 186px. Con 220 de más, `QFontMetrics.boundingRect` calculaba
  menos líneas de wrap de las que el texto necesita a su ancho real —
  "Reservado a futuro + aislada confirmada este mes." wrapea a 2 líneas
  a 220px pero necesita 3 a los 186px reales, y esa tercera línea
  quedaba cortada contra la fila de abajo. Corregido el ancho a 186 en
  `fijar_ancho_etiqueta_leyenda(186)`, el recorte desaparece con
  CUALQUIER tamaño de letra — confirmado armando un test nuevo que mide
  contra el ancho REAL (`etiqueta.width()`, ya renderizada) en vez de
  contra `leyenda._ancho_etiqueta` (la asunción, que es exactamente lo
  que hacían los dos tests de la ronda anterior — por eso ninguno de los
  dos había detectado este bug: comparaban contra su propio valor
  equivocado, nunca contra la realidad).

  De todos modos se bajó la letra como pidió la clienta (13→12 en
  Regular, 15→11 en Aislada): con el ancho ya corregido no hace falta
  para evitar el recorte, pero la mayoría de las descripciones largas
  dejan de necesitar ese tercer renglón directamente, dando una leyenda
  más compacta y prolija. Bajar la letra achica el alto natural de cada
  descripción, así que `_AJUSTE_ALTO_MUESTRA_LEYENDA_REGULAR`/`..._
  AISLADA` (13/28) y `_AJUSTE_EXTRA_MUESTRA_CON_DOMINGO` (9) se
  volvieron a medir desde cero con el ancho y la letra ya corregidos —
  no alcanzaba con reusar los valores de la ronda anterior. Mismo
  hallazgo YA documentado de rondas previas: el dataset real de
  `shot_oferta.py` no coincide exactamente con el dataset mínimo de los
  tests (`_AJUSTE_ALTO_MUESTRA_LEYENDA_REGULAR` terminó en 9, no en el
  13 que alcanzaba en el dataset de test, para no pasarse del alto
  disponible con la captura real) — la tanda final de valores quedó
  verificada contra las dos capturas reales antes de darla por cerrada.

- **"La grilla está bien, solo dale más largo para que el scroll
  horizontal no tape lo último que se tendría que ver de la grilla, en
  este caso el horario de las 21hs con su línea inferior incluída."**
  Bug real, no puntual de esta pantalla en su causa pero sí en su
  efecto: `_construir_tabla` (`GrillaOperativaWidget`, compartida por
  Reservas, Novedades, Grilla semanal y Oferta) calcula el alto mínimo
  de `self.tabla` como la suma exacta de sus filas — correcto mientras
  la tabla no necesite scroll horizontal, pero en Oferta (la única
  pantalla donde esta grilla queda lo bastante angosta como para
  necesitarlo de forma habitual, con los seis días de la semana como
  columnas) la barra de scroll horizontal, al aparecer, le come al
  VIEWPORT el alto de su propia altura — con el widget dimensionado
  justo para la suma de filas, ese consumo tapaba la última fila
  (21:00) junto con su línea inferior, quedando a mitad de camino entre
  la última hora visible y la barra.

  Método nuevo, opt-in, `GrillaOperativaWidget.reservar_alto_scroll_
  horizontal()`: suma al alto mínimo de la tabla el valor de `QStyle.
  PM_ScrollBarExtent` (el alto real que el estilo activo le da a una
  barra de scroll horizontal) — sobra un poco de margen en blanco si la
  barra no llega a aparecer en algún caso puntual, pero nunca vuelve a
  faltar cuando sí aparece. Solo lo llama Oferta; no afecta al resto de
  los usos de esta grilla compartida. Con la grilla mostrando "modo
  regular" por default (el mismo `combo_modo` de siempre) y `fijar_modo(
  "regular")` sin disparar `currentIndexChanged` porque el índice no
  cambia, esta pantalla nunca vuelve a reconstruir la grilla de Regular
  después de armar la UI — el mismo motivo, ya documentado en rondas
  anteriores para otros métodos opt-in, por el que hacía falta que
  `reservar_alto_scroll_horizontal()` reaplique de una el alto extra
  (llamando a `_actualizar_grilla()`) si la tabla ya tiene filas armadas
  al momento de llamarlo, en vez de esperar a una reconstrucción real
  que en el modo por defecto nunca iba a llegar.

Tests nuevos: `test_gui_grilla_operativa.py`
(`test_reservar_alto_scroll_horizontal_suma_el_alto_de_la_barra`,
`test_reservar_alto_scroll_horizontal_es_opt_in`); `test_gui_oferta.py`
(`test_referencias_de_colores_sin_recorte_al_ancho_real_renderizado` —
el test de regresión real de este bug, ver el detalle de arriba;
`test_grilla_reserva_alto_para_que_el_scroll_horizontal_no_tape_la_
ultima_fila`, que confirma que el viewport de la tabla alcanza para
mostrar la suma completa de sus filas con la barra de scroll horizontal
ya presente).

### Octava vuelta: "inmovilizar paneles" en la grilla — columnas y filas
### de encabezado siempre visibles al escrolear

Pedido de la clienta sobre la grilla embebida de Oferta de consultorios:
"¿se puede dejar inmóvil la columna que dice día de la semana, unidad,
consultorio, tipo de bloques y horarios, y que lo que se escrolee sea
solo lo que está a la derecha?" — mismo concepto que "inmovilizar
paneles" de Excel. Antes de implementar se consultaron dos decisiones
(`AskUserQuestion`):

- **Alcance**: "solo Oferta de consultorios" por ahora — es la única
  pantalla donde esta grilla necesita scroll horizontal de forma
  habitual (ver rondas anteriores); la clienta pidió el cambio a las
  demás pantallas con esta grilla (Reservas, Novedades, Grilla semanal)
  solo si queda conforme con lo que ve acá.
- **Filas de encabezado al escrolear hacia abajo**: "fijar también el
  encabezado arriba" — no solo las columnas de la izquierda, también
  Día de la semana/Localidad/Edificio/Unidad/Consultorio quedan fijas
  arriba; solo se escrolea el bloque de datos, en las dos direcciones.

### Mecánica (`GrillaOperativaWidget.activar_filas_y_columnas_fijas`, opt-in)

`QTableWidget` no tiene un "inmovilizar paneles" nativo, y menos con
celdas armadas a mano vía `setCellWidget` (no hay un modelo compartido
que dos vistas puedan mirar en simultáneo, como en el ejemplo oficial
de Qt para una sola columna fija). Se arman tres tablas más chicas,
superpuestas ENCIMA de `self.tabla` con `setGeometry` (no dentro de
ningún layout — `self.tabla` sigue viviendo en el suyo, sin cambios):
`_tabla_esquina` (la intersección fija de arriba a la izquierda: filas
de encabezado × columnas Tipo de bloque/Horario), `_tabla_fila_fija`
(el resto de las filas de encabezado, con las mismas columnas de datos
que `self.tabla`) y `_tabla_columna_fija` (el resto de las columnas
fijas, con las mismas filas de datos que `self.tabla`) — entre las
tres cubren exactamente la porción que tiene que quedar fija, sin
superponerse entre sí.

Contenido: `_poner_texto_encabezado`/`_poner_texto_dato_fila` (los dos
únicos puntos por los que pasa CUALQUIER celda de encabezado/Tipo de
bloque/Horario, ver "Séptima vuelta" más arriba) duplican cada celda
hacia la tabla fija que corresponda además de escribirla en `self.tabla`
como siempre — un widget no puede tener dos padres, así que cada celda
se construye dos veces (instancias separadas de `_EtiquetaGrilla`, no
un problema: son widgets baratos y sin estado compartido). Ningún
llamador de estos dos métodos (`_agregar_encabezado_agrupado`,
`_agregar_encabezado_consultorio`, `_agregar_columna_tipo_bloque`, el
loop de horas de `_construir_tabla`) tuvo que tocarse — la duplicación
queda encapsulada ahí adentro, agnóstica de quién llama.

**Primer intento fallido, documentado para no repetirlo**: la primera
versión ocultaba las columnas/filas fijas en `self.tabla`
(`setColumnHidden`/`setRowHidden`) para que su propio scroll arrancara
directo en la primera fila/columna de DATOS, alineado 1 a 1 con las
tablas fijas sin necesitar ningún descuento de offset al sincronizar
los scrollbars. Se probó y resultó un error real, no solo cosmético:
Qt reacomoda el contenido VISIBLE de una tabla para no dejar hueco
donde antes había algo oculto — con las filas de encabezado ocultas,
las filas de DATOS se corrían hacia arriba para ocupar ese lugar, y
terminaban tapadas por `_tabla_fila_fija` (que se queda fija arriba)
en vez de aparecer debajo de ella. Confirmado con una captura de
prueba: la reserva "R1" cargada en la fila 9:00 desaparecía por
completo de la pantalla.

**Solución real**: `self.tabla` NO se toca — sigue con todas sus
filas/columnas visibles, escroleando en las dos direcciones exactamente
como antes de este pedido. Las tres tablas fijas, superpuestas encima,
simplemente TAPAN (con el contenido correcto, duplicado) la porción
que no tiene que scrollear; lo que hay debajo de ellas en `self.tabla`
en ese momento (sea la fila 0 sin scrollear, o cualquier fila de datos
después de scrollear) es irrelevante porque nunca se ve. Como ninguna
fila/columna se oculta, reenviar el VALOR del scrollbar de `self.tabla`
tal cual (sin ningún descuento) al de la tabla fija correspondiente ya
alinea perfectamente el contenido — confirmado con la matemática y con
una captura scrolleada al máximo en las dos direcciones (ver más
abajo). `setVerticalScrollMode`/`setHorizontalScrollMode` en
`ScrollPerPixel` (en las cuatro tablas) asegura que "el mismo valor" en
verdad signifique "el mismo desplazamiento en píxeles" en las dos.

Geometría (`_actualizar_geometria_tablas_fijas`): posiciona las tres
tablas fijas relativas a `self.tabla.viewport().pos()` (después del
borde/frame), midiendo el ancho/alto fijo sobre `_tabla_esquina` (no
sobre `self.tabla` directo — un cambio defensivo, no necesario hoy que
`self.tabla` no oculta nada, pero deja la cuenta blindada por si algún
día `self.tabla` llegara a ocultar alguna fila/columna por otro
motivo: Qt devuelve 0 de ancho/alto para una fila/columna oculta sin
importar lo que se le haya puesto con `setColumnWidth`/`setRowHeight`
— exactamente el bug que hizo fallar el primer intento, pero en la
MEDICIÓN en vez de en el contenido). Se recalcula con un
`eventFilter` en `self.tabla.viewport()` (dispara con cualquier
`QEvent.Type.Resize`) y, además, explícitamente al final de
`limitar_alto_grilla` — ese método achica `self.tabla` sin pasar por
`_construir_tabla`, así que sin este llamado extra las tablas fijas
podían quedar un instante con la geometría vieja (más alta) hasta que
el evento de resize llegara a disparar el filtro.

Verificación de punta a punta (scripts de geometría, no capturas para
la clienta — el comportamiento scrolleado no es algo que una captura
estática pueda mostrar bien): con más de un consultorio/día cargado, se
escroleó `self.tabla` al máximo horizontal y al máximo vertical (este
último forzando un tope con `limitar_alto_grilla`, ya que la grilla de
Oferta no lo usa y por eso normalmente nunca necesita scroll vertical
propio) y se confirmó en las dos capturas: las columnas Tipo de
bloque/Horario y las filas Día de la semana/Unidad/Consultorio quedan
fijas en su lugar, mostrando siempre el mismo contenido, mientras el
resto de la grilla (a la derecha/abajo) muestra los datos que
corresponden a la posición de scroll — sin ningún salto ni contenido
incorrecto.

Tests nuevos: `test_gui_grilla_operativa.py`
(`test_activar_filas_y_columnas_fijas_es_opt_in`,
`test_activar_filas_y_columnas_fijas_arma_las_tres_tablas_con_las_
dimensiones_correctas`, `test_activar_filas_y_columnas_fijas_duplica_
el_contenido`, `test_activar_filas_y_columnas_fijas_sincroniza_el_
scroll`, `test_activar_filas_y_columnas_fijas_geometria_cubre_la_
esquina_del_viewport`); `test_gui_oferta.py`
(`test_grilla_deja_fijas_las_columnas_y_las_filas_de_encabezado`, que
solo confirma que Oferta prende el mecanismo — el comportamiento del
mecanismo en sí queda cubierto en los tests de arriba).

### Novena vuelta: "inmovilizar paneles" en todas las pantallas con esta grilla

Después de ver la captura de Oferta con columnas/encabezado fijos, la
clienta pidió extender el mismo mecanismo a "todas las solapas del
sistema en el cual esté presente una grilla" — cumpliendo lo que había
quedado abierto en la ronda anterior ("solo Oferta por ahora... te pido
el cambio a todas las solapas si quedo conforme").

`GrillaOperativaWidget.activar_filas_y_columnas_fijas()` (el método
opt-in de la ronda anterior, sin cambios en su mecánica interna) pasa a
llamarse desde los seis usos restantes de esta grilla compartida,
sumado a Oferta:

- `reservas.py`: `_PanelReservasRegulares`/`_PanelReservasAisladas` (las
  dos solapas de "Reservas") — se llama al final del armado de
  `self.grilla`, después de `limitar_alto_grilla`/`agrandar_muestras_
  leyenda` (el resto de los métodos opt-in que ya usa esta pantalla),
  justo antes de agregar la grilla al layout. Sin ningún cambio de
  orden necesario: `limitar_alto_grilla` ya recalcula la geometría de
  las tablas fijas al final si el mecanismo está activo (ver el ajuste
  de robustez de la ronda anterior), así que da igual si se llama antes
  o después.
- `novedades.py`: `_PanelVacaciones`/`_PanelLicencias`/`_PanelAusencias`
  (las tres solapas con grilla de "Registro de ausencias") — estas tres
  pantallas nunca habían llamado ningún método opt-in de esta grilla
  compartida (ni `limitar_alto_grilla` ni `agrandar_panel_filtros`,
  nada); se suma solo esta llamada, sin tocar nada más de su armado.
- `grilla_operativa.py` (pantallas): `_PanelGrillaSemanal` (la solapa
  "Grilla semanal" de "Grilla y mensajería") — mismo criterio, una sola
  línea nueva antes de agregar la grilla al layout.

Verificación: sin ningún cambio de código en `GrillaOperativaWidget`
más allá de lo ya construido en la ronda anterior — solo se sumó el
llamado en seis lugares nuevos — la suite completa sigue dando los
mismos 15 fallos preexistentes de siempre (0 regresiones), confirmando
que el mecanismo es genuinamente agnóstico de quién lo usa. Capturas de
las cuatro pantallas (Reservas ×2, Registro de ausencias ×3 — con un
profesional elegido para que la vista previa muestre datos reales en
vez de quedar vacía, que es el comportamiento normal de esas tres
pantallas sin ningún profesional seleccionado, sin relación con este
cambio —, Grilla y mensajería) confirmaron visualmente que ninguna
quedó distinta a como se veía antes de prender el mecanismo: al no
necesitar scroll (todas menos Oferta caben enteras sin scrollear hoy),
las tres tablas fijas quedan invisiblemente superpuestas mostrando
exactamente el mismo contenido que ya se veía, listas para cuando algún
día haga falta scrollear (más consultorios, más días, una ventana más
chica).

Tests nuevos: `test_gui_reservas.py`
(`test_grillas_de_reservas_dejan_fijas_columnas_y_encabezado`, las dos
solapas); `test_gui_novedades.py`
(`test_grillas_de_registro_de_ausencias_dejan_fijas_columnas_y_
encabezado`, las tres solapas); `test_gui_grilla_y_mensajeria.py`
(`test_grilla_semanal_deja_fijas_columnas_y_encabezado`) — los tres
solo confirman `grilla._filas_columnas_fijas is True` en cada panel,
mismo criterio que el test equivalente de Oferta (el comportamiento del
mecanismo en sí ya está cubierto a fondo en `test_gui_grilla_
operativa.py`, no hace falta repetirlo por pantalla).

## DC-05 §1.1/§2.1: confirmado resuelto, más un hueco adyacente corregido en Lista de espera

Hallazgo de la auditoría DC-01/DC-10 (#17, v2: 🔸 PARCIAL / posible
decisión consciente — pedía confirmación antes de tocar nada porque el
v2 había encontrado un comentario en `grilla.py` ("Vacaciones y
ausencias NO afectan esta grilla") que parecía contradecir el hallazgo
viejo ("Registrar vacaciones o licencias no libera el consultorio para
aisladas de otro profesional"), sin estar seguro de si eran dos cosas
distintas.

**Confirmado: son dos cosas distintas, y el hallazgo original ya está
resuelto.** `verificar_conflictos_aislada` (`app.negocio.reservas`, el
gate real que corre al confirmar una reserva aislada) ya chequea
`esta_ausente` + `tiene_vacacion` + `tiene_licencia` — las tres liberan
el consultorio para asignárselo a otro profesional; los docstrings de
`tiene_vacacion`/`tiene_licencia` (`app.negocio.vacaciones`/`licencias`)
hasta citan "DC-05 §1.1"/"§2.1" explícitamente. El comentario de
`grilla.py` es sobre `calcular_ocupacion_regular` — la grilla semanal de
REFERENCIA visual (un patrón genérico por día de la semana, promediado
para todo un mes, usada en Oferta/Disponibilidad/Reservas/Novedades/
Grilla semanal) — que el documento pide explícitamente que ignore
excepciones puntuales. No hizo falta tocar nada de esa parte.

**Hueco real encontrado al investigar, corregido de paso** (consultado
con la clienta antes de tocarlo, no es parte del hallazgo #17 en sí):
`calcular_ocupacion_fecha` (`app.negocio.grilla` — ocupación de una
fecha PUNTUAL, no un día de semana genérico; DC-03 Mensaje 2 Variante B,
hallazgo #13, usada por Lista de espera para matchear pedidos contra
disponibilidad real día por día) solo chequeaba `esta_ausente`, dejando
afuera `tiene_vacacion`/`tiene_licencia` — mismo tipo de corrección que
ya tenía `verificar_conflictos_aislada`, aplicada acá con el mismo
criterio exacto: una reserva regular no ocupa esa fecha si el
profesional está ausente, de vacaciones O de licencia ese día.

Tests nuevos en `tests/test_grilla.py`: `test_ocupacion_fecha_libera_
por_vacacion_puntual`/`test_ocupacion_fecha_libera_por_licencia_
puntual` (mismo patrón que el ya existente `test_ocupacion_fecha_
libera_por_ausencia_puntual` — confirman que la fecha dentro del período
libera el consultorio y que OTRA fecha fuera de ese período sigue
ocupada).

## DC-07 §6: Oferta de consultorios — valor en el pie de cada foto,
## Apto camilla solo para no activos, Edificio/Localidad solo si hay más de uno

Hallazgo de la auditoría DC-01/DC-10 (#32, confirmado parcialmente ❌
SIGUE en el v2 solo para el punto de "Apto camilla"; los otros dos
puntos del v1 — "estructura de secciones distinta a la documentada" y
"el valor no queda debajo de cada foto sino aparte" — habían quedado
sin re-verificar). No se tiene el texto original de DC-07 §6 en el
repositorio (mismo caso que DC-06 §3 en su momento) — consultada la
clienta, eligió que se propusiera un diseño a partir del resumen del
hallazgo en vez de pasar el documento.

Investigando antes de proponer nada: el propio docstring de
`tabla_fotos` (`app/pdf/fotos_pdf.py`) ya anticipaba la solución para
"Oferta de consultorios por búsqueda" vía su parámetro
`pie_personalizado` — un pie de foto totalmente a medida, documentado
ahí desde que se armó esa función, nunca usado hasta ahora por ningún
llamador. Comparado contra los PDF hermanos: Propuesta siempre
anonimiza y muestra "✔ Apto camilla"; Disponibilidad nunca anonimiza y
nunca la muestra; Oferta (el único de los tres que depende del
profesional dueño del pedido puntual) no mostraba la aclaración en
ningún caso — bug real, confirmado contra el criterio de los otros dos.

Antes de implementar se le mostraron a la clienta, en varias rondas,
ejemplos concretos (primero texto, después PDF reales generados con
datos de prueba, antes/después) para cada decisión de diseño — mismo
criterio de "mostrar antes de implementar" ya usado para otras
funcionalidades de esta lista:

- **Estructura de secciones**: no se tocó — sin un documento DC-07 §6
  real contra el que comparar, no hay una fuente de verdad confiable
  de cuál sería "la estructura correcta"; se dejó la actual (3
  secciones: Criterios de búsqueda → Coincidencias → Consultorios que
  intervienen en las ofertas) tal cual.
- **"✔ Apto camilla"**: se corrige para que aparezca únicamente cuando
  el pedido es de un profesional NO activo (anonimizado) — mismo
  criterio que Propuesta (que siempre anonimiza y siempre la muestra);
  un profesional activo sigue el criterio de Disponibilidad (nunca la
  muestra).
- **El valor "aparte"**: se elimina la lista de texto plano que iba
  DESPUÉS de las fotos (una línea "Consultorio N - unidad - Edificio:
  $valor/hora" por cada consultorio, repitiendo lo que ya mostraba el
  pie de cada foto sin el valor) y se mergea todo en un único pie por
  foto, vía `pie_personalizado` — mismo pie, con el valor adentro, sin
  texto repetido aparte.

Sobre el contenido final del pie, la clienta pidió además sumar
Localidad (no estaba en el pedido original de "el valor no queda
debajo de cada foto"): "Que se vea todo en la línea al pie de la foto
y suprimí la línea posterior. Al pie de la foto: consultorio, unidad,
edificio, localidad, valor y apto camilla si aplica." Y, en la vuelta
final de revisión (ya con dos PDF de ejemplo mostrando Edificio y
Localidad siempre presentes): "Si, conforme. Lo único, aclarar solo
localidad y edificio cuando haya más de uno, repito por las dudas" —
Edificio y Localidad dejan de mostrarse SIEMPRE y pasan a aclararse
solo cuando hay ambigüedad real dentro de ese PDF puntual.

### Implementación

`_pie_foto_oferta(imagen, anonimizar, decimales, *, mostrar_edificio,
mostrar_localidad)` (`app/pdf/oferta_pdf.py`, nueva) arma el pie único:
Consultorio + Unidad siempre, Edificio y Localidad cada uno CONDICIONAL
a su propio flag, valor siempre, y "✔ Apto camilla" solo si
`anonimizar` (NO activo) y el consultorio lo tiene. Localidad usa el
mismo fallback "(Sin localidad)" que el resto del sistema.

`_bloque_consultorios_intervinientes` calcula los dos flags UNA sola
vez para todo el PDF (no por grupo de edificio dentro del loop), antes
de recorrer `ids_edificio_orden`:
- `mostrar_edificio` reusa tal cual `multi` (`len(ids_edificio_orden) >
  1`), que esa función ya calculaba desde antes de este pedido para
  decidir si imprime el encabezado "Edificio {Nombre}" por grupo —
  mismo criterio exacto, sin duplicar el cálculo: si solo hay un
  edificio interviniendo, ni el encabezado ni el pie lo mencionan; con
  más de uno, los dos lo hacen.
- `mostrar_localidad` es nuevo: `len({img["DomicilioLocalidad"] for img
  in imagenes}) > 1` — sobre las imágenes (no sobre `consultorios`, que
  no trae Localidad), porque es lo único con esa columna disponible
  (`imagenes_de_consultorios`, ver abajo). Un edificio sin localidad
  cargada cuenta como un valor (`None`) distinto de cualquier localidad
  real — si ese es el único caso distinto entre todas las fotos, sigue
  siendo "más de uno" y se aclara igual (ambigüedad real: alguna foto
  es de un edificio con localidad y otra no).

`app/pdf/fotos_pdf.py::imagenes_de_consultorios` suma `DomicilioLocalidad`
a su SELECT (`LEFT JOIN Localidad` vía `Edificio.IdLocalidad`, mismo
alias que el resto del sistema) — cambio en la consulta compartida por
los cuatro PDF que usan esta sección (Liquidación, Propuesta,
Disponibilidad, Oferta), inocuo para los otros tres porque ninguno lee
esa columna todavía.

### Tests

`tests/test_pdf_oferta.py` suma: `test_pie_de_foto_incluye_el_valor_sin_lista_aparte`
(el valor queda en el mismo pie, "Valor hora regular" — el texto de la
lista vieja — ya no aparece en ningún lado);
`test_apto_camilla_solo_para_profesional_no_activo` (aparece para "C",
no aparece para "R", mismo consultorio);
`test_pie_de_foto_sin_edificio_ni_localidad_con_uno_solo` (con un solo
edificio/localidad, el pie no los menciona);
`test_pie_de_foto_con_edificio_y_localidad_cuando_hay_mas_de_uno` (con
dos edificios en dos localidades distintas, el pie de cada foto
menciona ambos). El pre-existente `test_orden_consultorios_activo_por_
piso_y_departamento` (verifica el orden por piso vía el texto del pie)
necesitó sumar una `Imagen` por consultorio de prueba — antes se apoyaba
en la lista de texto aparte, que mostraba el Departamento de cada
consultorio sin necesitar ninguna foto cargada; al eliminarse esa lista,
el Departamento solo aparece a través del pie de una foto real.

Las aserciones sobre "✔ Apto camilla" se escriben sin el signo "✔"
(solo "Apto camilla", mismo criterio que los tests ya existentes de
Disponibilidad/Liquidación/Oferta por búsqueda): el extractor de texto
de PyMuPDF no siempre devuelve ese glifo tal cual con la fuente
embebida en el PDF (confirmado probando — el mismo PDF que se ve
correcto al abrirlo devuelve un carácter de control distinto al
extraer texto), así que el signo en sí no es un criterio de test
confiable en ningún PDF de este sistema.

## Reservas: resolución de Lista de espera 100% automática (auditoría #12)

Hallazgo de la auditoría DC-01/DC-10 (#12, DC-10 §2.2 paso 5): al
confirmar una reserva regular que coincide con un pedido Activo de Lista
de espera de ese profesional, el sistema preguntaba con un cartel Sí/No
("¿Marcar como resuelto el pedido de Lista de espera de este
profesional?") antes de marcarlo `Resuelto`. Pedido explícito de la
clienta sobre este hallazgo: "Pasalo a automático" — se saca el cartel
por completo, la resolución queda incondicional (siempre que haya
exactamente un pedido Activo de ese profesional; con más de uno sigue
quedando a criterio manual, no hay forma de saber cuál de todos se
acaba de cubrir, eso no cambió).

`app/gui/pantallas/reservas.py`: `_ofrecer_resolver_lista_espera`
(preguntaba, y solo si confirmaban llamaba `marcar_resuelto`) se
renombra `_resolver_lista_espera_si_corresponde` y llama `marcar_
resuelto` directo, sin ningún `QMessageBox.question` de por medio. Mismo
único call site de antes (al confirmar una reserva regular, después de
`crear_reserva_regular`).

Tests en `tests/test_gui_reservas.py`: el nombre del test que confirmaba
la resolución automática con un solo pedido se actualiza
(`test_crear_reserva_regular_resuelve_pedido_unico_de_lista_de_espera_
automaticamente`); se borra el que probaba la opción de decir "No" al
cartel (funcionalidad retirada); el de "no resuelve con más de un
pedido activo" se simplifica, sacando el monkeypatch de `QMessageBox.
question` que ya no hace falta.

## Lista de espera: botón "Confirmar reserva" (auditoría #22)

Pedido explícito de la clienta sobre el hallazgo #22 de la auditoría
("el detalle de cobertura está, pero no hay ningún atajo para iniciar
una reserva regular precargada desde un pedido seleccionado"): un botón
`botonPrimario`, "Confirmar reserva", a la izquierda de "Descartar
pedido", habilitado solo con una fila que tenga alguna cobertura real
(mismo criterio que ya decide `_mostrar_cobertura`). Al tocarlo, salta a
Reservas > Reservas regulares con la cobertura ya precargada (profesional,
consultorio, día(s), horario) — el operador la revisa y confirma con
"Crear reserva regular" de siempre, no se crea sola. El cierre del
pedido (pasar a "Resuelto") no necesitó ningún código nuevo:
`_resolver_lista_espera_si_corresponde` (DC-10 §2.2 paso 5) ya lo hacía
solo apenas se crea cualquier reserva regular del profesional.

Antes de tocar código se le planteó a la clienta, y confirmó
entendimiento, sobre tres puntos:

- **Ver la cobertura antes de accionar el botón**: ya existe — el
  cuadro "Cobertura de la coincidencia seleccionada" (`_mostrar_
  cobertura`) ya muestra día/horario/consultorio al seleccionar la fila,
  antes de tocar ningún botón.
- **Con más de una opción de consultorio, ¿cuál toma?** El primer grupo
  en orden de días de la semana (Lunes primero) — ver `grupos_cobertura`
  más abajo. Si la cobertura necesita más de un grupo para cubrir todo
  el pedido, un cartel previo lista TODAS las partes antes de saltar a
  Reservas (ver el tercer punto).
- **¿La opción (a) puede confundir al operador?** Sí, podía — se
  detectó un problema real al diseñarla: el cierre automático del
  pedido se dispara con la PRIMERA reserva regular creada del
  profesional, no con "cubrir todo lo pedido". Con una cobertura de
  varias partes, confirmar solo la primera ya marca el pedido
  "Resuelto" aunque falte cargar el resto — si el operador tuviera que
  volver a Lista de espera para la parte 2, el pedido ya no aparecería
  ahí (solo lista pedidos Activos). Se resolvió con una COLA interna en
  Reservas (ver `precargar_desde_pedido` más abajo): el operador nunca
  necesita volver a Lista de espera — cada "Crear reserva regular"
  exitoso precarga sola la parte siguiente, dentro de la misma pantalla,
  y el pedido recién se marca Resuelto cuando no queda ninguna parte
  pendiente.

### `grupos_cobertura` (`app/negocio/lista_espera.py`)

Agrupa los tramos de una `Coincidencia` por (consultorio, horario) —
cada grupo es lo que SÍ se puede cargar en una sola `ReservaRegular`
(`crear_reserva_regular` toma un solo horario por vez, ese es el límite
real, no uno inventado para esta funcionalidad). Un pedido Verde con un
solo bloque da un único grupo; pero Verde solo garantiza un ÚNICO
consultorio en todo el pedido, no un único horario — un pedido con dos
bloques de horario distinto (ej. "martes 9-12" + "jueves 14-17", mismo
consultorio los dos) sigue necesitando dos grupos. Lo mismo, por el
motivo contrario, si la cobertura combina más de un consultorio
(Amarillo/Naranja/Rojo). Los grupos quedan ordenados por el día de la
semana más temprano de cada uno.

### `precargar_desde_pedido` (`_PanelReservasRegulares`, `app/gui/
pantallas/reservas.py`)

Carga el primer grupo en el formulario (reusa `_seleccionar_ubicacion`,
ya existente para "Modificar reserva") y guarda el resto en
`self._cola_precarga_pedido`. `_crear()` suma, al final, un chequeo
nuevo: si queda algo en la cola, precarga la parte siguiente Y
`return`s ahí mismo — sin llamar a `_resolver_lista_espera_si_
corresponde` ni a `_resetear_formulario()` todavía. Recién cuando la
cola queda vacía (el caso de siempre, o la última parte de una
cobertura de varias) sigue el camino de siempre: resuelve el pedido
Activo del profesional si corresponde, y resetea el formulario. En el
uso manual de toda la vida la cola siempre está vacía, así que el
comportamiento no cambia en nada.

### `VentanaPrincipal.ir_a_seccion` (`app/gui/main_window.py`)

Primera vez que una pantalla necesita saltar a otra en todo el sistema
— no había ningún mecanismo para esto. Se sumó un método chico y
reusable en vez de algo hecho a medida para este botón puntual: busca
la `Seccion` por nombre, la selecciona en el menú lateral (como si el
operador hubiera clickeado ahí) y devuelve su widget. `_PanelListaEspera.
_confirmar_reserva` llega a la ventana con `self.window()` (hasta dónde
cuelga el panel en tiempo real) en vez de recibirla por parámetro — esta
pantalla también se instancia sola en los tests, sin ventana principal
de verdad detrás, así que el método chequea `hasattr(ventana, "ir_a_
seccion")` antes de usarlo y no hace nada si no está (en vez de romper).

### GUI (`app/gui/pantallas/lista_espera.py`)

`_texto_lugar` (nuevo, a nivel de módulo) factoriza el armado "{Edificio}
- {Unidad} - Consultorio {N}" que `_mostrar_cobertura` ya tenía inline,
para reusarlo también en el cartel de "Confirmar reserva". Con más de
un grupo, el cartel (`QMessageBox.question`) enumera "Parte 1/N",
"Parte 2/N"... con el detalle de cada uno, antes de preguntar si
continuar — si el operador dice que no, no pasa nada (ni navega ni
precarga).

Tests nuevos: `tests/test_lista_espera.py` (`grupos_cobertura` — Verde
de un solo grupo, Verde con horarios distintos en dos grupos, Amarillo
combinando dos consultorios en dos grupos, orden por día de la semana,
lista vacía sin tramos); `tests/test_main_window.py` (`ir_a_seccion`
selecciona y devuelve el widget, nombre inexistente devuelve `None` sin
romper); `tests/test_gui_reservas.py` (`precargar_desde_pedido` carga
el primer grupo y deja el resto en cola, avanza de parte en parte y
recién resuelve el pedido al final, con un solo grupo resuelve de una);
`tests/test_gui_lista_espera.py` (botón deshabilitado sin selección o
sin cobertura, habilitado con cobertura, un solo grupo navega sin
preguntar nada, más de un grupo avisa con el detalle de las partes
antes de navegar, cancelar el cartel no navega, el pedido se cierra
solo al confirmar en Reservas, instanciada sola sin ventana principal
no rompe).

## Disponibilidad (las tres solapas): batch completo (#14.x del documento)

Decimocuarta tanda de `v0.11.2026.10`, cerrando la sección
"DISPONIBILIDAD". 1.2 (selector de profesional)/1.5 (`excluir_tabla_
del_tab`)/1.7 (foco visible)/1.8 (líneas de grilla)/1.10 (fecha con día
de semana + sábado en negro, 1.13) ya estaban resueltos desde tandas
anteriores en las tres solapas (confirmado leyendo el código). Lo que
faltaba era 1.3 (orden de unidad) en dos de las tres, 1.4 en las tres
(con un hallazgo real sobre Oferta: no aplica, decisión previa ya
documentada) y los puntos propios de cada una.

### Oferta de consultorios

- **1.3 — orden de Unidad**: `_cargar_unidades` ordenaba por
  `(NombreEdificio, Departamento)` alfabético puro — mismo hueco ya
  corregido en otras pantallas en rondas anteriores (`clave_orden_
  unidad`, de `app.pdf.estilos`), nunca cerrado acá. Corregido con el
  mismo helper y mismo criterio PB/EP/piso ascendente.
- **1.4 — confirmado que NO aplica, decisión previa documentada**: la
  propia función `_nueva_busqueda` ya tenía, desde una ronda anterior,
  el comentario "Único punto que limpia el formulario a propósito —
  entrar y salir de la pantalla NO lo resetea (confirmado por la
  clienta: la última búsqueda queda cargada tal cual se la dejó)" —
  mismo criterio ya aplicado en Liquidaciones (Estado de cuenta):
  cuando hay una decisión previa de la clienta que contradice la regla
  general nueva, se respeta la decisión previa, documentada acá de
  nuevo para que quede claro que no es un olvido sino algo
  deliberadamente sin tocar.
- **1.11**: ya cubierto — "Generar PDF" avisa la ruta generada,
  "Generar texto WhatsApp" abre un diálogo con el resultado. "Agregar
  franja"/"Quitar franja" no suman ningún cartel (operaciones de lista
  en memoria, con feedback visual inmediato) — mismo criterio que el
  resto del sistema para acciones chicas de UI sin consecuencia
  persistente.
- **"Reducir proporcional"**: no implementado — ambigüedad sin el texto
  original del punto a la vista, queda pendiente de una aclaración
  puntual antes de implementarse (mismo criterio que "autocierre de
  tanda" de Pagos).

### Lista de espera

- **1.3 — orden de Unidad**: mismo hueco exacto que Oferta, en
  `_cargar_unidades` — corregido con el mismo helper.
- **1.4 — hueco real, `reiniciar()` nuevo**: a diferencia de Oferta,
  esta pantalla no tiene ninguna decisión previa documentada que
  contradiga la regla general — `showEvent` solo enfocaba Profesional,
  sin resetear nada del formulario "Nuevo pedido" (Profesional,
  cascada Localidad/Edificio/Unidad, días, tipo O/Y, horario, cantidad
  de horas, bloques pendientes, combinación de bloques/consultorios,
  características, comentarios, y el modo "editando" si había uno en
  curso). `reiniciar()` nuevo (llamado desde `showEvent`, descubrible
  por F3) vuelve todo a su default de recién construida.
- **Confirmar eliminar pedido**: `_descartar` borraba el pedido sin
  preguntar nada — el pedido no se vuelve a ver después (la tabla solo
  lista Activos), así que se suma un `QMessageBox.question` con el
  nombre del profesional antes de marcarlo Descartado, más un
  `QMessageBox.information` de éxito al terminar.
- **"Renombrar botones" / "Editar pedido"**: investigado, ya resuelto
  de una ronda anterior (#22) — "Editar pedido" ya existe como tercer
  botón, con su propio flujo de precarga del formulario
  (`_cargar_pedido_en_formulario`) — ningún cambio de código hizo
  falta. Mismo criterio documentado otras veces en este archivo: el
  checklist de trabajo es un resumen propio armado sin el texto
  original, así que a veces señala algo que investigar y resulta ya
  estar cubierto.

### Archivos para enviar

- **1.4 — hueco real, `reiniciar()` nuevo**: el único estado de esta
  pantalla es `_tipo_seleccionado` (qué documento se eligió ver) — sin
  resetear, volver a la solapa seguía mostrando la vista previa del
  último documento elegido. `reiniciar()` nuevo lo vuelve a `None` y la
  Vista previa al texto de ayuda default.

Tests nuevos: `tests/test_gui_oferta.py`
(`test_unidades_quedan_en_orden_pb_ep_piso_no_alfabetico`);
`tests/test_gui_lista_espera.py`
(`test_descartar_pide_confirmacion_y_no_descarta_si_se_cancela`,
`test_reiniciar_vuelve_el_formulario_de_nuevo_pedido_al_default`,
`test_unidades_quedan_en_orden_pb_ep_piso_no_alfabetico`);
`tests/test_gui_archivos_varios.py` (`test_reiniciar_vuelve_a_sin_
seleccion`). Suite combinada `test_gui_oferta.py`+`test_gui_lista_
espera.py`+`test_gui_archivos_varios.py`+`test_gui_disponibilidad.py`:
145 passed. Suite completa: 2484 passed, sin regresiones (un
segfault intermitente de `grilla_operativa.py::paintEvent` apareció en
una corrida y no se reprodujo en la siguiente — mismo hallazgo de
estabilidad ya documentado más arriba en este archivo, WA_
StyledBackground + paintEvent manual bajo la plataforma `offscreen`,
no relacionado con los cambios de esta tanda).

