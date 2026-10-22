# Historial archivado — Placas para timbres

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

## Placas para timbres: se saca la tercera solapa (catálogo "Placas"),
## botones debajo de los filtros

Tres pedidos de la clienta sobre "Placas para timbres":

- **Se elimina la tercera solapa** ("Placas", el catálogo genérico sobre
  la tabla `Placa` sumado en el merge de esta pantalla porque compartía
  nombre con la operativa) — "repite la función de la primer solapa":
  "Búsqueda y asignación de placas" ya cubre dar de alta/reasignar/
  liberar una posición del tablero, con validaciones y vista integrada
  que el catálogo genérico no tenía. `catalogos.pantalla_placas` se
  borra por completo de `catalogos.py` (queda sin ningún otro
  consumidor, mismo criterio de "borrar código muerto entero" del resto
  del proyecto) — `PantallaPlacasParaTimbres` pasa a tener solo las dos
  solapas operativas (`panel_operativas.panel_buscar`/`panel_imprimir`).
- **Los tres botones de acción bajan de una fila horizontal (debajo de
  la tabla) a la columna de Filtros, uno debajo del otro** — pedido
  explícito de la clienta, mismo criterio "botones debajo de los
  filtros" que ya usan Nuevo/Editar/Eliminar en los catálogos genéricos.
  Orden pedido explícitamente: "Asignar posición placa nueva"
  (`botonPrimario`) → "Reasignar posición placa existente"
  (`botonSecundario`) → "Liberar posición" (`botonSecundario`), los tres
  con el mismo ancho fijo que ya usaba la columna de Filtros
  (`_ANCHO_BOTON_BUSCAR`). Ningún cambio en la lógica de los tres
  métodos (`_asignar_nueva`/`_reasignar`/`_liberar`) ni en
  `_actualizar_botones_tabla` (Reasignar/Liberar siguen deshabilitados
  sin selección) — puramente reubicación de widgets dentro del mismo
  layout de columna.

`gui_main.py`: la ayuda de "Placas para timbres" se actualiza para no
mencionar más la tercera solapa.

Tests: `tests/test_catalogos.py` saca `pantalla_placas` de la
parametrización de fábricas y borra su test dedicado
(`test_pantalla_placas_muestra_unidad_y_profesional`).
`tests/test_gui_placas_para_timbres.py` pasa sus tests de "tres
pestañas" a "dos pestañas" y borra el que confirmaba la tercera solapa
como `PantallaCRUD` anidada.

## Placas: Localidad/Edificio/Unidad por separado en los diálogos (regla
## general nueva), botones más largos y respuesta sobre el nombre personalizado

Segunda vuelta sobre "Placas para timbres", con cinco pedidos de la
clienta sobre los dos diálogos de la primera solapa
(`_DialogoPlaca`, `app/gui/pantallas/placas.py`):

- **Diálogo "Asignar..." con Localidad/Edificio/Unidad por separado.**
  Reemplaza el combo único "Unidad" (que mostraba "Edificio - Unidad"
  combinado) por tres selectores en cascada real —
  `_opciones_localidad`/`_opciones_edificio`/`_opciones_unidad`,
  importados cruzados de `reservas.py` (mismo criterio de import
  cruzado que ya usa este archivo para `_opciones_profesional`/
  `_texto_profesional`, y que ya usan otras pantallas — Liquidaciones
  simuladas, etc. — para esta misma cascada). Elegir una Localidad
  acota las opciones de Edificio; elegir un Edificio acota las de
  Unidad — mismo mecanismo de recarga en cadena (`blockSignals` +
  recarga manual del siguiente nivel) que ya usan Liquidaciones
  simuladas/Reservas para esta misma cascada.
- **Si un nivel tiene una sola opción, se preselecciona y queda
  deshabilitado — el foco pasa solo al siguiente selector.** Pedido
  explícito de la clienta, aplicado a Localidad y a Edificio (no a
  Unidad, que no lo pidió). No hizo falta ningún manejo de foco
  explícito: un `QComboBox` deshabilitado (`setEnabled(False)`) ya
  queda afuera de la cadena de foco nativa de Qt, así que Tab/Enter lo
  saltea solo y cae directo en el siguiente selector habilitado.
- **Diálogo "Reasignar..." también con los tres por separado.** Antes
  mostraba un único `QLabel` "Edificio - Unidad"; ahora son tres
  `QLabel` de solo lectura (Localidad/Edificio/Unidad no se pueden
  cambiar al reasignar — la Unidad de una posición del tablero es fija,
  lo único que cambia es el profesional), resolviendo la Localidad vía
  `Edificio.IdLocalidad` con el mismo fallback "(Sin localidad)" que
  usa el resto del sistema.
- **Regla general nueva, para todo el sistema, no solo Placas**: "no me
  gusta la versión compacta, prefiero ver claramente los cuatro puntos
  por separado" — pedido explícito de la clienta sobre cualquier combo
  que combine Localidad/Edificio/Unidad/Consultorio en un solo texto
  ("Edificio - Unidad", etc.) de acá en adelante. Mismo criterio que
  otras reglas generales de este documento (Foco, Selectores y fecha,
  "cuadros scrolleables"): se aplica a las pantallas que se revisen de
  acá en adelante, no dispara un barrido retroactivo de todo el sistema
  ya armado con combos compactos. **Alcance confirmado con la clienta**
  (consultada por `AskUserQuestion` antes de tocar código, porque el
  pedido original mencionaba también "Consultorio" y el modelo de
  `Placa` no tiene ese nivel — el tablero es por Unidad, a propósito, no
  por consultorio, documentado desde el negocio de esta funcionalidad):
  la regla es Localidad/Edificio/Unidad — Consultorio no aplica a este
  diálogo puntual, la clienta confirmó el error ("me equivoqué con lo
  de consultorio... las placas se le asignan a la unidad").
- **Nombres de los tres botones, más largos, a dos líneas donde hace
  falta**: "Asignar posición placa nueva" → "Asignar posición de
  placa\na profesional"; "Reasignar posición placa existente" →
  "Reasignar posición de placa\na otro profesional" (los dos con salto
  de línea manual, mismo criterio que otros botones de dos líneas del
  sistema — ej. "Agregar franja\na la búsqueda" de Oferta — medido con
  el estilo real de la app antes de decidir el corte: las dos líneas
  resultantes son más cortas que el texto de una sola línea que ya
  entraba antes en el mismo ancho, así que `_ANCHO_BOTON_BUSCAR` no
  necesitó cambiar); "Liberar posición" → "Liberar posición de placa"
  (una sola línea, entra sin problema en el mismo ancho).

**Respuesta a la pregunta de la clienta** ("¿El nombre personalizado se
asigna con la primer solapa o con la segunda al imprimir y luego ese
dato pasa a la BD?", sin cambio de código, es aclaración de
comportamiento ya existente): son DOS mecanismos independientes, sin
relación entre sí.
- El "Nombre grabado personalizado" de los diálogos de la primera
  solapa (Asignar/Reasignar) SÍ se guarda en la base
  (`Placa.NombreGrabado`/`Placa.EsPersonalizada`, vía `asignar_placa`)
  — es el nombre que queda grabado en la placa física del tablero, y
  es lo que se ve después en la tabla ("Nombre grabado") y en
  `nombre_grabado()`.
- El "Personalizar texto de la placa" de la segunda solapa (Imprimir)
  NO se guarda en ningún lado — solo se usa para ESA tanda puntual de
  impresión (`generar_pdf_placas_seleccionadas`), independiente del
  modelo de `Placa` por completo (ver el docstring de
  `app.negocio.placas`: "La impresión puntual de placas nuevas es
  independiente de este modelo"). Cerrar la solapa sin generar el PDF
  pierde ese texto sin dejar rastro.

Tests nuevos en `tests/test_gui_placas.py`:
`test_dialogo_nueva_localidad_y_edificio_unicos_quedan_preseleccionados_y_deshabilitados`,
`test_dialogo_nueva_con_varias_localidades_el_combo_queda_habilitado`,
`test_dialogo_nueva_elegir_localidad_acota_edificio_y_unidad`,
`test_dialogo_reasignar_muestra_localidad_edificio_y_unidad_por_separado`.
`test_etiquetas_y_tamano_de_los_botones_de_buscar_y_asignar` actualiza
los tres textos esperados.

## Placas: nombre personalizado de dos líneas, se arma en la primera
## solapa y se levanta en la de impresión

Tercera vuelta sobre "Placas para timbres", con seis pedidos de la
clienta sobre el flujo de nombre personalizado:

- **El nombre personalizado se carga y guarda SOLO en la primera solapa
  (Asignar/Reasignar); la de Imprimir deja de pedirlo y solo lo
  levanta.** Hasta esta vuelta eran dos mecanismos totalmente
  independientes (ver la ronda anterior, "Respuesta a la pregunta de la
  clienta") — ahora pasan a ser uno solo. Se sacan de la solapa Imprimir
  el checkbox "Personalizar texto de la placa" y sus dos campos de línea
  (`casilla_personalizar_impresion`/`campo_linea1_impresion`/
  `campo_linea2_impresion`, con su validación de "cargá al menos la
  línea 1") — `_agregar_a_impresion` ahora llama a
  `app.negocio.placas.personalizacion_del_profesional(conn,
  id_profesional)` (nueva), que busca si el profesional elegido tiene
  alguna placa personalizada (en cualquier unidad — no hay forma de
  saber cuál "corresponde" a una impresión puntual, que no está atada a
  ninguna unidad en particular; con más de una, se usa la primera que
  aparezca, caso raro) y arma `linea1`/`linea2` a partir de ahí, en vez
  de pedirlos por teclado. Si no tiene ninguna, usa el nombre estándar
  (comportamiento sin cambios).
- **El diálogo de Asignar/Reasignar pasa a admitir DOS líneas**: el
  campo único "Nombre grabado" se reemplaza por "Línea 1"/"Línea 2
  (opcional)" (mismos placeholders que ya usaba la solapa de Imprimir
  antes de sacárselos) — "si pongo texto en las dos líneas las acomoda
  de acuerdo a lo que trabajamos por impresión". `Placa.NombreGrabado`
  sigue siendo una sola columna de texto (sin migración de schema): se
  guarda como `linea1` a secas si no hay segunda línea, o
  `"{linea1}\n{linea2}"` si la hay — el mismo formato que ya arma
  `texto_para_imprimir` al unir sus dos líneas, así que el valor
  guardado se puede pasar directo a esa función sin ninguna conversión
  extra (solo hace falta volver a separarlo con `.split("\n")` para
  precargar los dos campos al reabrir el diálogo de Reasignar, o para
  armar `linea1`/`linea2` en `_agregar_a_impresion`).
- **Límite de 24 caracteres por línea**: `_MAX_CARACTERES_LINEA_PLACA =
  24`, aplicado con `QLineEdit.setMaxLength(24)` en las dos líneas —
  Qt impide escribir de más, no hace falta validar al guardar. Pedido
  explícito de la clienta, mismo límite ya calibrado en
  `app.pdf.placas_pdf` contra su sistema físico: "Lic. Agustina
  Viavattene" (24 caracteres, contando puntos y espacios) es la
  referencia exacta que dio.
- **La columna "Nombre grabado" de la tabla muestra " / " en vez del
  salto de línea real**: "la barra solo es visual en el campo para que
  sepa a simple vista que se hizo en dos líneas" — el dato guardado
  sigue con el salto real (`\n`), la transformación es puramente de
  visualización en `_actualizar_tabla` (`e["nombre"].replace("\n", "
  / ")`), no toca el valor real ni lo que usa `_agregar_a_impresion`/el
  PDF. Ejemplo dado por la clienta: "Lic. Agustina Viavattene / Equipo
  Nutri Oeste".
- **Columnas de la tabla reacomodadas**: hasta esta vuelta las 7
  columnas se repartían el ancho por igual (`Stretch` en todas, pedido
  de una ronda anterior); ahora Localidad/Edificio/Unidad/Posición/
  Profesional/Personalizada pasan a `Interactive` + ajuste a contenido
  (`_ajustar_columnas`, mismo criterio `resizeColumnsToContents()` +
  padding que `novedades._ajustar_columnas`, acá con
  `_PADDING_COLUMNA_PLACAS = 20`) y "Nombre grabado" queda como la
  ÚNICA columna en `Stretch` — se lleva todo el ancho que las otras seis
  dejan libre. Pedido explícito de la clienta: "que entren 51
  caracteres, dos líneas completas más el ' / ' que iría en el medio"
  — verificado con un test que mide el ancho real necesario con
  `QFontMetrics` contra la fuente real de la tabla (no un pixel fijo
  hardcodeado, que sería frágil ante un cambio de fuente/DPI).
- **El PDF de referencia del tablero completo (`generar_pdf_placas`,
  automático en el avance de mes) también necesitaba un ajuste**: antes
  de esta vuelta `NombreGrabado` nunca tenía más de una línea, así que
  `_tabla_placas` nunca había necesitado manejar un salto de línea
  interno — con el nombre guardado ahora pudiendo traer un `\n` real,
  se corrigió para convertirlo a `<br/>` (la sintaxis que entiende
  `Paragraph` de reportlab) antes de armar la celda, para que el
  tablero de referencia muestre las dos líneas de verdad en vez del
  carácter crudo.

Tests nuevos: `tests/test_placas.py`
(`test_nombre_grabado_con_dos_lineas_guarda_el_salto_real`,
`personalizacion_del_profesional` — 5 tests: sin placa, con placa no
personalizada, con placa personalizada de una/dos líneas, no cuenta la
de otro profesional). `tests/test_gui_placas.py`
(`test_dialogo_reasignar_precarga_las_dos_lineas_por_separado`,
`test_dialogo_lineas_personalizadas_limitan_a_24_caracteres`,
`test_valores_arma_nombre_de_una_sola_linea`/`test_valores_arma_nombre_
de_dos_lineas_con_salto_real`, `test_nombre_grabado_es_la_unica_
columna_que_se_estira`, `test_nombre_grabado_entra_al_menos_51_
caracteres`, `test_columnas_cortas_quedan_mas_angostas_que_nombre_
grabado`, `test_nombre_grabado_en_la_tabla_muestra_barra_en_vez_de_
salto_de_linea`/`test_nombre_grabado_de_una_linea_en_la_tabla_queda_de_
corrido`, `test_panel_imprimir_no_tiene_controles_de_personalizar`,
`test_agregar_a_impresion_levanta_la_personalizacion_de_la_placa`/
`test_agregar_a_impresion_sin_placa_personalizada_usa_el_nombre_
estandar`). Los dos tests viejos de "Personalizar texto de la placa" en
la solapa de Imprimir (`test_personalizar_impresion_requiere_linea1`/
`test_personalizar_impresion_guarda_las_dos_lineas`) se sacan — eran
pruebas de la funcionalidad que se retira de esa solapa, no de otra
cosa. `test_columnas_de_la_tabla_se_reparten_el_ancho_por_igual` (de la
ronda que había igualado las 7 columnas) se saca, reemplazada por las
nuevas de arriba. `tests/test_pdf_placas.py` suma
`test_placa_personalizada_de_dos_lineas_muestra_las_dos`.

## Placas: "Liberar posición de placa" a la misma altura que los otros dos

Pedido puntual de la clienta al revisar la captura de la ronda anterior:
en la columna de Filtros de "Búsqueda y asignación de placas", los tres
botones (`boton_asignar_nueva`/`boton_reasignar`/`boton_liberar`) ya
compartían el mismo ancho fijo (`_ANCHO_BOTON_BUSCAR`), pero no el
alto — los dos primeros tienen texto de 2 líneas (desde una ronda
anterior, "Asignar posición de placa\na profesional"/"Reasignar
posición de placa\na otro profesional") mientras que "Liberar posición
de placa" es una sola línea, así que Qt le daba a cada uno el alto
natural de su propio `sizeHint()` — 46px a los de 2 líneas, 32px al de
una sola (medido con un script contra el estilo real de la app, no a
ojo). `_ALTO_BOTON_BUSCAR = 46` (nueva constante, en
`app/gui/pantallas/placas.py`) se aplica con `setFixedHeight` a los
tres — mismo criterio que ya usa `_ANCHO_BOTON_BUSCAR` para el ancho,
extendido acá al alto porque esta es la primera pantalla de la revisión
que mezcla botones de una y de dos líneas en un mismo grupo vertical
(el resto de los botones de dos líneas del sistema, ej. Oferta/
Reservas, no conviven con botones de una sola línea en la misma
columna, así que nunca había hecho falta igualar el alto a mano antes).
Test nuevo en `tests/test_gui_placas.py`: se suman dos aserciones al
test ya existente de etiquetas/ancho
(`test_etiquetas_y_tamano_de_los_botones_de_buscar_y_asignar`)
confirmando que los tres botones también comparten el mismo
`.height()`.

De paso, pedido de la clienta de cambiar el criterio de las capturas
que se le envían para esta pantalla puntual: en vez de la pantalla
`PantallaPlacasParaTimbres` sola (como el resto de las capturas de todo
este documento), pidió ver las dos solapas con la PANTALLA COMPLETA del
sistema, menú de navegación incluido — así que esta ronda sumó un
script de captura nuevo que arma `VentanaPrincipal` de verdad (con
`gui_main.construir_secciones()`), selecciona "Placas para timbres" en
el menú lateral y hace `.grab()` sobre la ventana completa en vez de
sobre el panel suelto. No es un cambio de convención general de
capturas para el resto del sistema — es puntual de este pedido sobre
esta pantalla.

