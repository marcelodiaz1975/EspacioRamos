# Historial archivado — Llaves y otros conceptos

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

## Llaves (solapa, botones a la izquierda, tablas apiladas a la derecha)

Última pantalla sin revisar del sistema. Pasó del `QSplitter` viejo de
dos paneles anchos (Tipos+Accesos a la izquierda, Movimientos a la
derecha, cada tabla con sus propios botones al lado) a formato solapa
única "Llaves" (`panelSolapa`/`QScrollArea`, `setDrawBase(False)`/
`NoFrame` como el resto) con una separación total entre botones y
tablas: columna izquierda de ancho fijo (`_ANCHO_BOTON = 280`,
calculado para "Devolución copia del profesional") con los diez
botones de las tres secciones, sin ninguna tabla; columna derecha con
las tres tablas apiladas una arriba de la otra (Tipos, Accesos,
Movimientos, en ese orden) — pedido explícito de la clienta sobre el
`QSplitter` viejo.

Los diez botones, de arriba a abajo (todos `botonSecundario` salvo el
último, pedido explícito de la clienta — antes "Nuevo" y "Asignar…"
eran los dos `botonPrimario` de la pantalla):
"Nuevo tipo de llave" / "Editar tipo de llave" / "Eliminar tipo de
llave", línea divisoria, "Agregar acceso de llave" / "Eliminar acceso
de llave", línea divisoria, "Ingresar copia al stock" / "Registrar
pérdida" / "Devolución copia del profesional" / "Asignar copia a
profesional" (`botonPrimario` — la única acción que la clienta marcó
como "más definitiva" de la pantalla). Los nombres también cambiaron
(ninguno lleva ya puntos suspensivos, mismo criterio que Profesionales
al sacárselos a "Agregar archivo") y el orden de los cuatro botones de
Movimientos se invirtió respecto de antes (Ingresar → Pérdida →
Devolución → Asignar, en vez de Ingresar → Asignar → Devolución →
Pérdida).

"Deshacer último movimiento" (cubría cualquier alta/edición/baja de
esta pantalla, con su propio mecanismo genérico `_marcar_ultimo`/
`_ultimo`) se sacó por completo a pedido explícito de la clienta al
darle la lista final de diez botones — confirmado aparte, porque no
estaba en la lista y es una pérdida de funcionalidad real, no solo
estética. Se borró también todo el código que solo existía para
alimentarlo: `_cargo_especial_creado` y el cómputo de `cargos_antes`/
`cargo_nuevo` en `_asignar`/`_registrar_devolucion` no tenían ningún
otro uso.

Alto de las tablas (pedido explícito de la clienta, distinto del
`stretch=1` parejo que tenían las tres antes): Tipos y Accesos quedan
con un alto FIJO calculado para mostrar 6 y 3 filas respectivamente sin
scroll (`_alto_para_filas`, a partir de `verticalHeader().
defaultSectionSize()` + el alto del encabezado — ambas tablas siguen
siendo scrolleables si hay más filas de las que entran, el alto fijo
solo define cuántas se ven sin tener que scrollear), y Movimientos se
queda con `stretch=1`, es decir todo el alto que sobra en la pantalla
después de las otras dos. Cada tabla conserva su campo de observación
(`campo_observacion_tipo`/`_acceso`/`_movimiento`) inmediatamente
debajo, en la misma columna derecha — no son botones, así que no
tenían lugar en la columna de botones y quedaron junto a su tabla, que
es de donde toman y a donde guardan el valor.

La cadena de foco Enter/Tab no sigue el orden puramente visual esta
vez (los botones y los campos de observación quedaron en columnas
separadas): se mantuvo el mismo orden lógico por sección que ya tenía
la pantalla antes de esta revisión (observación de Tipo → sus tres
botones → observación de Acceso → sus dos botones → observación de
Movimiento → sus cuatro botones, sin Deshacer), interpretación propia
ante la ambigüedad de qué es "más arriba" cuando dos columnas
independientes tienen contenido a la misma altura — confirmado con la
clienta: "de arriba a abajo el foco, intuitivo", el criterio actual
queda tal cual.

Con esto, Llaves — la última pantalla de la revisión "uno por uno" —
queda formalmente cerrada, y no quedan puntos abiertos pendientes de
confirmación en ninguna de las pantallas del sistema.

Segunda vuelta (tres pedidos sobre esta misma pantalla):

- **Títulos de sección sin negrita.** "Tipos de llaves"/"Accesos
  habilitados con la llave"/"Movimientos de llaves" pasan de
  `subtituloSeccion` (Nivel 2, negrita) a `subtituloCampo` (Nivel 3,
  mismo peso que el texto normal, sin nada que lo distinga) — pedido
  explícito de la clienta: no son solapas reales, van "como los de
  otros formularios". El título Nivel 1 ("LLAVES") y el nombre de la
  solapa ("Llaves") sí quedan como estaban — son los dos casos de esta
  pantalla que sí usan una fuente realmente distinta (mayúscula
  itálica el primero, la "ficha" de la solapa el segundo), la clienta
  los dejó afuera del pedido.
- **Cada grupo de botones alineado contra el título de su tabla.** Los
  diez botones dejaron de apilarse en una sola columna corrida (las
  tres secciones seguidas) para alinearse, grupo por grupo, contra el
  comienzo de la barra de título de su tabla correspondiente — pedido
  explícito de la clienta. Se resolvió con un único `QGridLayout` de 3
  filas × 2 columnas (antes eran dos `QWidget` con su propio
  `QVBoxLayout`, uno para todos los botones y otro para las tres
  tablas): columna 0 = grupo de botones de esa sección
  (`_grupo_botones`, un widget nuevo por sección con ancho fijo, sin
  builder repetido), columna 1 = título+tabla+observación de esa
  sección envueltos en su propio widget. Cada grupo de botones se
  agrega con `Qt.AlignmentFlag.AlignTop` (sin ese flag, `QGridLayout`
  estira el widget para llenar toda la fila en vez de dejarlo arriba
  del todo) — como la fila la termina definiendo el contenido más alto
  (la tabla, con su alto fijo o su `stretch`), el grupo de botones
  correspondiente queda "colgado" desde arriba exactamente a la altura
  de su título, sin necesitar ningún cálculo manual de espaciado.
  `setRowStretch(2, 1)` en la fila de Movimientos sigue logrando que
  esa fila (botones y tabla por igual) se quede con el resto del alto
  disponible, mismo criterio que la vuelta anterior.
- **Sin líneas divisorias.** Las dos que separaban los tres grupos de
  botones se sacaron — dejaron de hacer falta al quedar cada grupo ya
  separado visualmente por la distancia entre filas de la grilla.

Tercera vuelta (cuatro pedidos más sobre esta misma pantalla):

- **Botones alineados contra el primer registro, no contra el título.**
  Se corrigió el criterio de la vuelta anterior: el primer botón de
  cada grupo tiene que arrancar a la altura de la primera FILA de datos
  de su tabla (después del encabezado), no a la altura del título de la
  sección. `_alto_hasta_primera_fila(titulo, tabla)` calcula ese salto
  (alto del título + alto del encabezado de la tabla + su borde) y
  `_grupo_botones` lo antepone como un widget espaciador de alto fijo
  antes del primer botón del grupo — mismo mecanismo de `QGridLayout` +
  `AlignTop` que la vuelta anterior, solo que ahora el "colgado desde
  arriba" empieza más abajo. Para poder calcular el offset hizo falta
  invertir el orden de construcción: antes se armaban los diez botones
  y recién después las tres tablas; ahora cada sección arma primero su
  título+tabla (columna 1) y con esos dos widgets ya construidos arma
  después su grupo de botones (columna 0), sección por sección.
- **Títulos en negrita, mismo tamaño.** Vuelven a la negrita que tenían
  con `subtituloSeccion` en la revisión original, pero sin volver a ese
  tamaño (15px) — se quedan en el tamaño normal de `subtituloCampo` (la
  clienta pidió "ese tamaño pero en negrita"). Como ningún objectName
  existente combina tamaño normal con negrita, `_titulo_seccion` le
  suma un `setStyleSheet("font-weight: bold;")` puntual encima del
  `subtituloCampo` de la vuelta anterior, en vez de sumar un objectName
  nuevo a `estilos.py` para un caso que hoy solo usa esta pantalla.
- **Las tres tablas ya scrolleaban internamente** (columna que
  corresponde a esta revisión, no algo que haya hecho falta cambiar):
  se comprobó con un diagnóstico aparte que Tipos/Accesos (alto fijo,
  ver vuelta 1) y Movimientos (alto por `stretch`) ya mostraban su
  propia scrollbar vertical apenas su contenido no entraba en el alto
  asignado, sin que el `QScrollArea` externo de la solapa tuviera que
  scrollear la página entera. Se sumaron tres tests (uno por tabla) que
  fuerzan el desborde y confirman `verticalScrollBar().maximum() > 0`,
  para dejar esto cubierto de acá en adelante.
- **Más ancho en las columnas de Tipos y Accesos.** Tipos tenía anchos
  manuales fijos (no usa `resizeColumnsToContents`, porque "Nombre del
  tipo de llave" necesita espacio propio) — se subieron a mano
  (200→240, 70→100, 120→150, 90→120, 95→125, 65→95). Accesos pasa de
  `resizeColumnsToContents()` puro a sumarle `_PADDING_COLUMNA` (30px,
  mismo criterio y mismo valor que `bloques_rigidos._ajustar_columnas`/
  `novedades._ajustar_columnas`). Movimientos no se tocó — el pedido
  fue puntualmente sobre "las dos primeras tablas".

Cuarta vuelta: Accesos pide directamente el DOBLE de ancho en las
cuatro columnas (no un padding más generoso como Tipos) —
`_ajustar_columnas` suma un parámetro `factor` (default 1, sin cambiar
a nadie más que la llame) que multiplica el resultado de
`resizeColumnsToContents() + _PADDING_COLUMNA`; Accesos es la única
que lo llama con `factor=2`.

## Planilla de importación: revisión de cobertura (hueco real en Llaves, decisión consciente)

Pedido de la clienta: revisar la planilla de importación completa
("por las dudas"), con dudas puntuales sobre si la hoja "Llaves" cubre
todo lo necesario, si falta algún campo nuevo en alguna hoja existente,
o si habría que sumar alguna hoja más.

Repaso sistemático de `app.importacion.definiciones.COLUMNAS_PLANTILLA`
contra `schema.sql`, entidad por entidad: Localidad/Edificio/Unidad/
Consultorio/Profesion/Profesional/ReservaRegular/FechasEspeciales/
Responsable/PlanPago están completas (todo lo que corresponde cargar al
importar ya tiene su columna — lo que falta en cada una son campos que
el propio sistema calcula o gestiona en vivo, como `SaldoCuentaActual`
o `MontoTotalAPagar`, nunca algo que debiera venir de la planilla).

**Confirmada la duda sobre Llaves — hueco real, no una percepción
equivocada.** La hoja "Llave" solo da de alta el TIPO de llave (`Tipo`
+ `ValorDepositoActual`) — pero el modelo de Llaves tiene tres tablas
(sección 3.7 más arriba): `Llave` (el tipo), `LlaveAcceso` (a qué
Edificio/Unidad abre) y `LlaveMovimiento` (stock existente y
asignaciones ya vigentes a profesionales). Ninguna de las dos últimas
se puede cargar por planilla — un tipo de llave importado queda sin
ningún acceso configurado y sin ninguna copia en stock ni asignada,
hasta que alguien entra a mano a la pantalla de Llaves a completarlo.
Consecuencia práctica: el aviso "le falta la llave" de Reservas
(`llaves_faltantes_para_reserva`) nunca dispara para una llave
importada así, y si un profesional ya tenía una copia física antes de
usar el sistema, se lo va a mostrar como "sin llave" hasta que se
registre a mano el Ingreso + la Asignación correspondientes.

Dos alternativas de diseño se le plantearon a la clienta
(`AskUserQuestion`) antes de tocar nada: sumar columnas de acceso/stock
directo a la misma hoja "Llave" (cubre el caso común, un tipo con un
solo acceso), o una hoja nueva "LlaveMovimiento" referenciando el tipo
por una columna de referencia inventada para la importación (más
flexible, soporta accesos/asignaciones múltiples, pero más compleja de
llenar). **Decisión: dejarlo como está** — no se implementa ninguna de
las dos; el acceso y el stock/asignaciones de Llaves se siguen
configurando a mano desde la pantalla después de importar.

También se consultó sumar "Bloques rígidos" como hoja nueva (dato de
configuración inicial parecido a Fechas especiales, que sí se importa,
pero fuera del alcance original de la Etapa 1) — **decisión: no**, son
pocos bloques por sistema, más simple cargarlos a mano.

### Tres correcciones menores, sí implementadas

Encontradas de paso en la misma revisión, de alcance chico y acotado
— confirmadas con la clienta antes de tocarlas, implementadas sobre su
"sí, corregí los tres":

- **Hoja "Llave" sin `Observacion`**: la tabla `Llave` tiene esa
  columna (una nota libre sobre el tipo, ej. "está un poco gastada"),
  pero la planilla no la ofrecía. `COLUMNAS_PLANTILLA["Llave"]` suma
  `"Observacion"` al final de la lista.
- **Fila de Llave con `Tipo` vacío rompía TODA la importación**: `
  importar_hoja` armaba `datos["Nombre"] = siguiente_nombre_llave(conn,
  datos["Tipo"])`, y esa función hace `_LETRA_POR_TIPO[tipo]` — con
  `Tipo` en blanco (`None`) o mal tipeado, un `KeyError` sin capturar
  (el `try/except` de esa fila solo atrapaba `sqlite3.Error`/
  `ValueError`) interrumpía el loop completo en vez de reportarse como
  el error de esa única fila, como hace cualquier otra validación de
  este módulo. Se agrega una validación explícita antes de llamar a esa
  función (`tipo not in _LETRA_POR_TIPO`, importado cruzado de
  `app.negocio.llaves` — mismo criterio de import cruzado que ya usa
  este módulo) que levanta un `ValueError` con un mensaje claro,
  atrapado por el mecanismo normal: la fila se reporta como error y el
  resto de la hoja sigue importándose.
- **Hoja "Placa" no valida que la Posición esté dentro del tablero**:
  `asignar_placa` (la función de negocio que usa la pantalla al cargar
  a mano) valida que la posición esté entre 1 y
  `Unidad.CantLimitePlacas`, pero la importación hacía `repo.crear(
  **datos)` directo, sin pasar por esa validación — una planilla con
  una posición fuera de rango quedaba cargada igual, sin ningún aviso.
  `_resolver_referencias` (caso "Placa") suma el mismo chequeo
  (`1 <= PosicionTablero <= CantLimitePlacas`) antes de confirmar la
  unidad resuelta — si falla, se agrega a `errores` (mismo mecanismo
  que "no se encontró la unidad") y la fila se saltea sin romper el
  resto de la hoja.

Tests nuevos en `tests/test_importacion.py` (ninguna de las dos hojas
tenía cobertura de tests hasta ahora, otra señal de que este costado no
se había puesto a prueba): `test_importar_llave_guarda_observacion`,
`test_importar_llave_sin_tipo_reporta_error_y_no_rompe_las_demas_filas`
(confirma que el resto de la hoja sigue importándose después de la fila
con el error), `test_importar_placa_posicion_fuera_del_tablero_
reporta_error`, `test_importar_placa_posicion_dentro_del_tablero_
se_guarda`.

## Llaves y otros conceptos: Movimientos y tenencias (batch #16.x del documento)

Decimosexta tanda de `v0.11.2026.10`. 1.2 (selector de profesional,
`_DialogoAsignar`)/1.3 (orden de unidad, ya resuelto en una tanda
anterior en los tres lugares — `_accesos`, el combo de "Agregar
acceso" y la tabla de Accesos)/1.5 (`excluir_tabla_del_tab` en las tres
tablas)/1.7 (foco visible en combos/checks, regla general)/1.12
(período solo actual o siguiente, por construcción del combo nuevo —
ver abajo) confirmados ya resueltos, sin cambios. Lo que faltaba:

- **Período a imputar en los diálogos de Asignar/Devolución**:
  `asignar_llave`/`devolver_llave` (`app.negocio.llaves`) ya soportaban
  `periodo_imputado` desde que se armó el Subtipo "Depósito de llave" —
  nunca había ningún control en la GUI para elegir "el siguiente", el
  depósito/reintegro siempre caía en el período actual por el default
  del parámetro. Se suma el mismo combo "Período actual"/"Período
  siguiente" que ya usan Reservas aisladas/extraordinarias para esta
  misma decisión, a `_DialogoAsignar` y `_DialogoDevolucion` (que ahora
  recibe `conn` como parámetro nuevo, para poder resolver el período
  real en `valores()`).
- **1.9 — regenerar liquidación del período actual**: mismo criterio
  que Cargos especiales — `_asignar`/`_registrar_devolucion` llaman
  `regenerar_si_corresponde` cuando el depósito/reintegro cobrado cae
  en el período en curso (nunca cuando cae en el siguiente, ni cuando
  no se cobra/reintegra nada).
- **1.10 — fecha con día de la semana**: `_fecha_edit` (compartida por
  los diálogos de Asignar/Devolución/Ingreso/Pérdida) usaba
  "dd-MM-yyyy" sin el día — hueco real, pasa a "ddd dd-MM-yyyy" como el
  resto del sistema (el sábado en negro ya estaba, vía `aplicar_color_
  sabado_negro`, aplicado desde antes de esta tanda).
- **1.11 — alerta de éxito**: "Asignar"/"Registrar devolución"/
  "Registrar pérdida" nunca avisaban nada al terminar con éxito — se
  suma un `QMessageBox.information` a cada uno, mismo criterio que el
  resto del sistema.
- **"Check Bonificar depósito"**: no implementado — sin ningún rastro
  en el código ni en CLAUDE.md de qué debería hacer exactamente (¿exime
  de pagar el depósito a un profesional puntual? ¿a qué categoría?),
  queda pendiente de aclaración antes de implementarse.
- **"Nueva solapa 'Stock de llaves por profesional'"**: no
  implementado — es una pantalla/reporte nuevo completo, sin ninguna
  especificación de qué columnas o agrupamiento debería mostrar más
  allá del nombre. Mismo criterio que el resto de los puntos
  genuinamente ambiguos de este documento: no se inventa el alcance,
  queda pendiente de una definición puntual con la clienta antes de
  programarlo.
- **Estado de cuenta (Cargos especiales)**: confirmado sin ningún punto
  propio pendiente (ya cubierto por #93/#94) — 1.4 deliberadamente NO
  aplicado, mismo criterio ya documentado para "Estado de cuenta" de
  Liquidaciones: este panel conserva a propósito el profesional
  elegido entre una consulta y la siguiente, nunca tuvo `showEvent`
  propio y no se le agrega uno ahora.

Tests nuevos: `tests/test_gui_llaves.py`
(`test_dialogo_asignar_periodo_siguiente_imputa_al_mes_que_viene`,
`test_asignar_con_deposito_al_mes_actual_regenera_liquidacion_no_
enviada`, `test_dialogo_asignar_fecha_muestra_dia_de_la_semana`,
`test_asignar_con_exito_muestra_alerta`, `test_dialogo_devolucion_
periodo_siguiente_imputa_al_mes_que_viene`, `test_dialogo_devolucion_
fecha_muestra_dia_de_la_semana`), más la aserción nueva de `PeriodoImputado`
sumada a `test_asignar_crea_movimiento_y_cargo_especial`. Suite
combinada `test_gui_llaves.py`+`test_llaves.py`: 99 passed. Suite
completa: 2490 passed, sin regresiones (mismo segfault intermitente ya
documentado, no relacionado con esta tanda — confirmado con una
segunda corrida limpia).

## Llaves: bonificado/abonado (punto 4) y "Stock de llaves por profesional" dentro de la solapa existente (punto 5)

Cierra los dos puntos de Llaves que habían quedado pendientes de
definición en la lista de cinco ("check Bonificar depósito" y la
eventual nueva solapa "Stock de llaves por profesional") — la clienta
los resolvió explícitamente: punto 4 con una aclaración de para qué
sirve, punto 5 con un pedido puntual de prototipo DENTRO de la solapa
"Movimientos y tenencias de llaves" ("No hagas la solapa por ahora"),
con una lista de cambios concretos y pedido de captura antes de darlo
por cerrado.

### Punto 4 — "Depósito bonificado" vs "Depósito abonado"

Aclaración de la clienta sobre para qué sirve esta distinción: "que me
memorice también qué depósito les cobro y qué les bonifico... para que
a la hora de la devolución de la llave sepa yo si le tengo que
reintegrar el depósito o ya con el reintegro de la llave alcanza". El
dato de fondo YA existía (`LlaveMovimiento.DepositoCobrado`, que
`_DialogoDevolucion` ya usaba para pre-tildar "Reintegrar depósito") —
lo que faltaba era hacerlo EXPLÍCITO en los dos diálogos, en vez de
quedar escondido detrás de un checkbox genérico "Cobrar depósito".

`texto_estado_deposito(deposito_cobrado: bool) -> str` (nuevo,
`app.negocio.llaves`): "Abonado"/"Bonificado", único punto de verdad
para este texto — lo usan tanto la GUI (la columna "Depósito" de
"Stock de llaves por profesional", ver punto 5) como, en su momento,
la planilla de importación (que ya tenía su propia columna
`DepositoAbonado`, ver más abajo).

`_DialogoAsignar` (`app/gui/pantallas/llaves.py`): el checkbox "Cobrar
depósito" se reemplaza por un selector explícito, `combo_deposito`
("Depósito bonificado (no se cobra nada)"/"Depósito abonado (se cobra
el monto)"), arrancando en "Bonificado" (mismo default que tenía el
checkbox sin tildar) — "Monto cobrado" (`spin_monto`) pasa a
deshabilitado por default y solo se habilita al elegir "Abonado"
(`_al_cambiar_deposito`, conectado DESPUÉS de construir `spin_monto`
para no dispararse contra un atributo que todavía no existe en el
primer `addItem`). `valores()` sigue devolviendo exactamente el mismo
contrato de siempre (`cobrar_deposito`/`monto_cobrado`) para
`asignar_llave`, sin tocar la capa de negocio.

`_DialogoDevolucion`: suma una línea de texto, ANTES del checkbox
"Reintegrar depósito", mostrando el estado original tal cual quedó
registrado al asignar — "Depósito original: Abonado ($3.000)" o
"Depósito original: Bonificado (no se cobró nada — no corresponde
reintegrar)" — el checkbox sigue pre-tildándose solo según ese mismo
dato, esta etiqueta solo lo hace visible en vez de que la clienta tenga
que recordarlo o abrir el historial de movimientos para confirmarlo.

### Punto 5 — "Stock de llaves por profesional", dentro de "Movimientos y tenencias de llaves"

Pedido explícito y detallado de la clienta, implementado tal cual lo
describió, con el prototipo ya armado antes de pedir confirmación
("Si me entendiste prearmalo y mostrame una captura de pantalla"):

- **"Accesos habilitados con la llave" se achica hasta el ancho justo
  de sus columnas** (incluida "Nombre"). `panel_accesos` pasa de una
  columna sola a un `QHBoxLayout` con dos mitades — `panel_accesos_izq`
  (título + `tabla_accesos` + observación, SIN stretch) a la izquierda,
  `panel_stock` (la tabla nueva, CON `stretch=1`) a la derecha, para
  que se quede con el ancho que Accesos deja libre. `_actualizar_
  accesos` pasa a correr `_ajustar_columnas`/fijar el ancho de
  `tabla_accesos` SIEMPRE (antes solo con un Tipo seleccionado) y el
  ancho queda FIJO (`setFixedWidth`, suma de las 4 columnas + el marco)
  en vez de estirarse con el resto de la fila. De paso, el "doble de
  ancho" que esta misma tabla pedía en una ronda anterior
  ("Accesos pide directamente el DOBLE de ancho", `factor=2`) queda
  SUPERADO por este pedido nuevo y más específico ("acortar", no
  agrandar) — `factor` vuelve a 1.
- **Tabla nueva, "Stock de llaves por profesional"** (`self.tabla_
  stock`, 3 columnas: Profesional/Tipo de llave/Depósito): una fila por
  cada `LlaveMovimiento` Tipo="Asignación" todavía ABIERTA (sin
  Devolución/Pérdida que la cierre) — reusa `self._movimientos_
  actuales` (ya enriquecido por `_actualizar_movimientos`, que ahora
  también guarda `_categoria_profesional`) sin repetir la consulta;
  `_actualizar_stock()` se llama al final de `_actualizar_movimientos`,
  así que se refresca sola ante cualquier alta/baja de movimiento. La
  columna "Depósito" usa `texto_estado_deposito` (punto 4). Alto fijo a
  3 filas (`_FILAS_VISIBLES_ACCESOS`, mismo criterio que Accesos, para
  que las dos tablas de la fila quedaran parejas), con
  `setStretchLastSection(True)` (mismo criterio que "Estado de cuenta"
  de Cargos especiales) para que "Depósito" se lleve el ancho sobrante.
- **Orden fijo, NO por click de encabezado**: pedido explícito —
  categoría B,R,E,A,X (constante nueva, `_ORDEN_CATEGORIA_STOCK`,
  DISTINTA de la jerarquía global B,R,A,E,X,C que usa `clave_orden_
  profesional`/`_opciones_profesional` para el resto de los selectores
  del sistema — acá E va antes que A) y, dentro de cada categoría,
  código natural (`clave_orden_codigo`, reusado tal cual).
- **Los dos botones de Accesos suben, alineados contra el INICIO de la
  tabla** (su borde de arriba, sin saltear el encabezado) — DISTINTO
  del criterio `_alto_hasta_primera_fila` que usan Tipos/Movimientos
  (alineados contra la primera fila de DATOS, saltando el encabezado).
  Se suma `_alto_hasta_la_tabla(titulo)` (nueva, devuelve solo el alto
  del título) para este caso puntual.
- **Buscador de profesional, debajo de "Eliminar acceso de llave"**:
  `combo_filtro_stock`, mismo widget/criterio que "punto 1.2" del
  documento general (`habilitar_busqueda_profesional`), con "Todos los
  profesionales" como primera opción — filtra `tabla_stock` sin tocar
  `tabla_accesos`. Se agrega al mismo `QWidget` que devuelve `_grupo_
  botones` para Accesos (`grupo_accesos.layout().addWidget(...)`, en
  vez de pasarlo como un botón más — `_grupo_botones` solo fija ancho y
  apila, sirve igual para un combo) y se suma a la cadena de foco
  general de la pantalla, entre "Eliminar acceso de llave" y el campo
  de observación de Movimientos.

Captura enviada a la clienta (ventana completa, `VentanaPrincipal` +
`ir_a_seccion("Llaves y otros conceptos")`, con tres profesionales de
categorías B/R/E con tenencias abiertas de ejemplo) para confirmar el
prototipo antes de darlo por cerrado — pendiente de su revisión.

### Punto 6 — planilla de importación de ejemplo

La hoja "Llave" de la planilla de importación YA tenía, de una ronda
anterior ("Planilla de importación de Llaves: tipos, accesos y
tenencias en una sola hoja"), una columna `DepositoAbonado` (SI/NO)
que ya alimenta `LlaveMovimiento.DepositoCobrado` al importar una
tenencia histórica — sin generar ningún `CargoEspecial` (es un dato de
antes de empezar a usar el sistema, no un cobro nuevo) — así que no
hizo falta ningún cambio de código para este punto, solo generar y
enviar un archivo de ejemplo: `app.importacion.plantillas.
generar_plantillas` más 4 filas de muestra agregadas a mano a la hoja
"Llave" (una llave de Edificio con una tenencia abonada y otra
bonificada, una de Unidad sin tenencia todavía, una "No especificada"
abonada) — verificado que importa sin errores contra una base de
prueba antes de enviarlo.

## Llaves/Oferta: ronda de ajustes sobre la captura del prototipo de Stock

Tres pedidos puntuales de la clienta al revisar la captura del
prototipo "Stock de llaves por profesional" (punto 5) y la de Oferta de
la vuelta anterior:

### Llaves: investigación de los campos de observación (consultado, sin tocar nada)

Pregunta de la clienta: "¿Muestran algo los campos de texto que están
abajo de la tabla 'Accesos...' y de la tabla 'Movimientos...'? Si no
tienen función alguna los eliminaría para ganar espacio." Investigado
contra el código (`campo_observacion_acceso`/`campo_observacion_
movimiento`, `_actualizar_observacion_*`/`_guardar_observacion_*`): SÍ
tienen función real — muestran y permiten editar la `Observacion` de la
fila actualmente SELECCIONADA en su tabla correspondiente (`LlaveAcceso.
Observacion`/`LlaveMovimiento.Observacion`), guardando al perder el
foco (`editingFinished`). Quedan deshabilitados y vacíos cuando no hay
ninguna fila elegida — lo que probablemente los hace parecer "sin
función" a primera vista, si no se los ve justo después de clickear una
fila. No se tocó nada: la clienta condicionó la eliminación a que NO
tuvieran función ("si no tienen función alguna los eliminaría"), y
estos sí la tienen — queda pendiente de que confirme si, sabiendo esto,
los quiere eliminar igual (perdería la posibilidad de anotar una
observación por acceso/movimiento) o prefiere conservarlos.

### Llaves: buscador de Stock a la par del título, tablas alineadas de punta a punta

Dos pedidos sobre la misma zona: "Reubicá el selector de profesional,
ponelo a la par de la etiqueta 'Stock de llaves por profesional' apenas
termina la misma sin ninguna otra etiqueta adicional. La tabla ponela
bien a la par de la que está a la izquierda, que tengan el mismo alto
que empiecen y terminen en el mismo lugar de la pantalla."

- **Combo a la par del título**: `combo_filtro_stock` (antes debajo de
  "Eliminar acceso de llave", con su propia etiqueta "Buscar
  profesional\n(filtra Stock de llaves)") se saca de la columna de
  botones por completo — ni el combo ni esa etiqueta quedan ahí. El
  título "Stock de llaves por profesional" pasa a vivir en un `QWidget`
  propio con un `QHBoxLayout` (título + combo, sin ninguna etiqueta de
  más), reemplazando al `QLabel` suelto que tenía antes.
- **Bug real de geometría detrás del desalineado** (confirmado con un
  script, medición pixel a pixel, mismo criterio de todo este
  documento): las dos tablas NO arrancaban ni terminaban en el mismo
  lugar, aun con el mismo alto fijo (`_FILAS_VISIBLES_ACCESOS` en las
  dos). Causa en dos capas:
  1. Un `QHBoxLayout` con un `QLabel` (14px de alto natural) y un
     `QComboBox` editable (20px, por el borde reservado para el foco +
     el padding de `estilos.py`) agregado con `addLayout` a un
     `QVBoxLayout` reporta, bajo la plataforma `offscreen`, un
     `sizeHint()` de esa fila completamente fuera de rango (144px
     medidos contra un alto real de 20px) — mismo tipo de inestabilidad
     de `sizeHint()` ya documentado para la leyenda de colores de
     Reservas/Oferta. Se corrige envolviendo el título+combo en un
     `QWidget` con `setFixedHeight` explícito (el mismo alto, medido en
     vivo con `combo.sizeHint().height()`, que también se le aplica a
     `titulo_accesos` del otro lado) — ninguno de los dos títulos
     depende más de un `sizeHint()` de layout anidado.
  2. Con los dos títulos ya al mismo alto fijo, seguía quedando un
     desalineado de pie a pie: `panel_accesos_izq` (con el campo
     `campo_observacion_acceso` DEBAJO de su tabla) es más alto que
     `panel_stock` (que no tiene ningún campo equivalente) — dentro del
     `QHBoxLayout` que los contiene (`fila_accesos`), por default Qt
     estira `panel_stock` hasta igualar esa altura mayor, y como ningún
     hijo de `panel_stock` puede crecer de verdad (título y tabla con
     alto fijo), ese sobrante se reparte como relleno ANTES, ENTRE y
     DESPUÉS de los dos — título y tabla terminaban corridos hacia
     abajo en la misma medida, en vez de quedar arriba del todo.
     Corregido agregando `panel_stock` a `fila_accesos` con
     `alignment=Qt.AlignmentFlag.AlignTop` (en vez de dejarlo en el
     alineamiento default, que estira/rellena) — el sobrante cae entero
     DEBAJO de `panel_stock`, invisible, sin correr nada adentro.
     Confirmado con el mismo script: título y tabla de Stock terminan
     en el píxel EXACTO que los de "Accesos habilitados con la llave",
     en las dos puntas.

Tests nuevos en `tests/test_gui_llaves.py`:
`test_combo_filtro_stock_vive_a_la_par_del_titulo_sin_etiqueta_propia`
(el combo está en la misma fila que el título, sin ninguna etiqueta
extra, y ya no cuelga de la columna de botones de Accesos);
`test_tablas_de_accesos_y_stock_empiezan_y_terminan_a_la_misma_altura`
(compara `mapTo`/`rect()` de las dos tablas y de los dos títulos,
mostrando la pantalla de verdad — no alcanza con `sizeHint()` para este
caso, ver el bug de arriba).

### Oferta de consultorios: columna de franjas estirada hasta el pie

Pedido explícito de la clienta sobre la captura de la vuelta anterior
(la que restauró "Agregar franja"/"Quitar franja" en la columna 1,
compactados): "el cuadro de la segunda columna, el de las franjas,
quedó extremadamente chico. Estiralo para que el botón 'Nueva búsqueda'
termine a la misma altura que los botones de agregar y quitar franja."

Con `lista_franjas` fijada a un alto chico (`_ALTO_LISTA_FRANJAS = 48`,
de la vuelta anterior, pensada para un pedido de "achicar" que esta
vuelta revierte) y un `columna_franjas.addStretch()` al final, el hueco
sobrante quedaba TODO abajo de "Nueva búsqueda" en vez de repartirse —
exactamente lo opuesto de lo que se busca ahora. Se revierte al
criterio de antes de esa ronda: `lista_franjas` vuelve a `stretch=1` sin
tope de alto (sigue teniendo su propio scroll si hay más franjas de las
que entran) y se saca el `addStretch()` final — con la lista como único
elemento flexible de la columna, absorbe sola el alto de sobra que le
imponga el `QSplitter` (que iguala las cuatro columnas a la más alta —
la del formulario, con los botones de franja ya restaurados en su pie),
empujando los tres botones de acción hasta el borde inferior de la
columna. Constante `_ALTO_LISTA_FRANJAS` se elimina (sin otro uso).

Confirmado con un script de geometría: `boton_nueva.bottom()` (columna
2) y `boton_quitar_franja.bottom()` (columna 1) coinciden en el mismo
píxel exacto (diferencia de 0px, contra la ventana de referencia
1500×850).

Tests en `tests/test_gui_oferta.py`: el test de "alto fijo" de la ronda
anterior se reemplaza por
`test_lista_franjas_estirada_hasta_el_pie_y_escrolea_con_mas_de_las_que_
entran` (stretch=1, sin tope de alto, sigue escrolleando con 20 franjas
cargadas).

## Llaves/Oferta: segunda ronda — qué muestra el cuadro de Accesos, columnas de Stock/Movimientos achicadas, cierre de Oferta

Cuarto conjunto de pedidos sobre la captura del prototipo de Stock:

- **"¿El cuadro de abajo de Accesos qué tendría que mostrar?"** Mismo
  mecanismo exacto que los de Tipos/Movimientos (ya confirmados por la
  clienta como funcionales): muestra y permite editar la `Observacion`
  de la fila ACTUALMENTE SELECCIONADA en "Accesos habilitados con la
  llave" (`campo_observacion_acceso`/`_actualizar_observacion_acceso`/
  `_guardar_observacion_acceso`, sin cambios de código — ya estaba así
  desde antes de esta vuelta, confirmado leyendo el código y
  reproduciéndolo con un script en vivo). Punto importante para
  entender por qué puede parecer "que no muestra nada": como "Accesos"
  depende de qué Tipo de llave esté seleccionado en la tabla de arriba
  (`_actualizar_accesos` solo puebla `tabla_accesos` cuando hay un
  `_tipo_seleccionado()`), el cuadro de observación de Accesos se queda
  deshabilitado y vacío hasta que se elige PRIMERO una fila en "Tipos
  de llaves" Y DESPUÉS una fila en "Accesos" — sin ese primer paso, no
  hay ninguna fila de Acceso que seleccionar, así que el cuadro
  correctamente no muestra nada (no es un bug, es la cascada Tipo →
  Acceso que esta pantalla siempre tuvo).
- **"Achicá la columna de Depósito en la tabla Stock para que se vea
  horizontalmente de una sin escrolear."** `self.tabla_stock.
  horizontalHeader().setStretchLastSection(True)` se saca — medido con
  un script de geometría: esa llamada le daba a "Depósito"
  ("Abonado"/"Bonificado", el texto más corto de las tres columnas)
  TODO el ancho que "Profesional"/"Tipo de llave" dejaban libre dentro
  de `panel_stock` (hasta 233px en el escenario de prueba, contra
  ~103px que necesita de sobra con el mismo padding que las otras dos
  columnas — `_ajustar_columnas`, sin cambios). Sin el stretch, la
  columna queda al ancho justo como el resto de la tabla, y lo que
  sobra del panel se queda en blanco a la derecha en vez de hincharla.
- **"En movimientos de llaves también achicá columnas... si se
  puede."** Dos ajustes reversibles, sin pérdida de información:
  - Los encabezados "Depósito cobrado"/"Depósito reintegrado" pasan a
    "Dep. cobrado"/"Dep. reintegrado" — esas dos columnas se
    dimensionaban por el ANCHO DEL TÍTULO (más largo que el contenido
    real, "$5.000"/vacío), así que abreviarlo angosta la columna sin
    tocar nada del dato.
  - La columna "Fecha" pasaba el nombre completo del día de la semana
    ("Lunes 19-10-2026", vía `_fecha_larga`) — inconsistente con el
    resto del sistema, que abrevia a 3 letras (`"ddd dd-MM-yyyy"`, ej.
    "lun 19-10-2026", ya usado en Registro de ausencias/Reservas/
    Configuración general). `_fecha_larga` pasa a `dia[:3]` en vez del
    nombre completo — mismo dato (el día de la semana sigue mostrándose),
    columna más angosta.
  - **Límite real, documentado**: estos dos cambios ahorran espacio
    real (medido: ~75px sobre un total de ~1188px en el escenario de
    prueba) pero no alcanzan, por sí solos, para eliminar el scroll
    horizontal cuando "Tipo de llave" trae un nombre de llave largo
    (el nombre incluye el del edificio, sección 3.7/"nomenclatura
    automática") o cuando "Profesional" necesita su ancho mínimo ya
    establecido (`>= 180px`, cubierto por un test existente). Achicar
    esas dos columnas de verdad implicaría truncar contenido real
    (nombre del profesional o de la llave) — no pedido explícitamente
    esta vuelta, así que se deja como la limitación aceptada de este
    "si se puede": el ahorro logrado es neto y sin pérdida de
    información, pero no garantiza cero scroll con nombres largos.
- **"Conforme con oferta de consultorios, cerralo."** Confirmado por la
  clienta — la solapa "Franjas agregadas a esta búsqueda" con
  `stretch=1` (de la ronda anterior) queda cerrada, sin más cambios
  pendientes sobre Oferta de consultorios en esta vuelta.

Tests nuevos en `tests/test_gui_llaves.py`:
`test_columna_deposito_de_stock_no_se_estira_mas_alla_de_su_contenido`
(confirma `stretchLastSection() is False` y que la columna no supera el
doble de su ancho justo con padding) y
`test_fecha_de_movimientos_usa_el_dia_de_la_semana_abreviado` (el texto
de la celda arranca con una abreviatura de 3 letras, nunca con el
nombre completo del día). `test_columnas_de_deposito_cobrado_y_
reintegrado_tienen_el_mismo_ancho` se actualiza para medir contra "Dep.
reintegrado" (el título nuevo) en vez de "Depósito reintegrado".

## Planilla de importación de Llaves: rediseño en tres hojas (Llave / LlaveAcceso / LlaveMovimiento)

Pedido de la clienta, surgido al preguntar si la planilla de importación
"toma el tipo de llave, el nombre, el acceso y el stock" a partir de
cargar, por profesional, todas las llaves ya distribuidas. Investigado
antes de responder: SÍ tomaba todo eso, pero con un hueco real que la
clienta no había contemplado — la hoja única "Llave" de aquel momento
(ver "Planilla de importación de Llaves: tipos, accesos y tenencias en
una sola hoja", más arriba) creaba un Tipo de llave NUEVO por cada fila,
sin ningún mecanismo de fusión: si varios profesionales tenían copia de
la MISMA llave física (mismo Tipo + Edificio), cada fila terminaba en un
"Tipo de llave" propio con 1 copia/1 asignada/0 disponibles, en vez de un
único Tipo con varias copias — funcionaba igual para la alerta de "le
falta la llave" en Reservas, pero dejaba el catálogo "Tipos de llaves"
fragmentado en entradas que a simple vista parecen duplicadas.

Consultada la clienta con tres alternativas (`AskUserQuestion`), eligió
una cuarta, más clara, que ella misma propuso: tres hojas separadas, una
por cada tabla real del modelo (`Llave`/`LlaveAcceso`/`LlaveMovimiento`)
— "Tipos de llave" (con stock inicial de 1000 para que la importación
nunca falle por falta de stock, ajustado a mano después), "Accesos de
llave" y "Llaves distribuidas por profesional" (una fila por cada copia
ya repartida, con si abonó el depósito o fue bonificado). Confirmado con
ella que entendí bien antes de tocar código (preguntó "avisame si me
expliqué").

### El problema que su propio diseño no resolvía: cómo enlazar las tres hojas

El `Nombre` de un Tipo de llave lo arma el sistema solo (`siguiente_
nombre_llave`, "Tipo llave E1"...) — no hay forma de saberlo de antemano
al escribir la planilla, así que las hojas "Accesos" y "Llaves
distribuidas" necesitaban alguna forma de decir "esta fila es sobre ESE
Tipo de la hoja 1" sin depender de ese nombre. Consultado aparte
(`AskUserQuestion`, tres opciones), eligió la recomendada: un "Código"
propio, inventado por ella (cualquier texto corto, ej. "LL-01"), que la
hoja "Llave" suma como columna nueva y las hojas "LlaveAcceso"/
"LlaveMovimiento" repiten (columna "CodigoLlave") para decir a qué Tipo
se refiere cada una de sus filas — nunca se guarda en la base, es
puramente de planilla, solo sirve para que la importación una las tres
hojas entre sí durante esa corrida.

### Modelo nuevo (`app/importacion/definiciones.py`)

`COLUMNAS_PLANTILLA` reemplaza la vieja entrada única `"Llave"` por tres,
consecutivas (el orden del dict es el orden real de importación, vía
`ENTIDADES_IMPORTABLES = list(COLUMNAS_PLANTILLA.keys())` — "Llave"
tiene que procesarse antes que las otras dos, que la referencian):

- **"Llave"**: `Codigo, Tipo, ValorDepositoActual, Observacion` — sin los
  tres `CampoLibre` de siempre: a diferencia de los catálogos genéricos
  (`PantallaCRUD`), la tabla `Llave` nunca los sumó (esta pantalla está
  "armada a mano, no `PantallaCRUD`" — ver esa sección más arriba), no
  hay columna a la que mapearlos.
- **"LlaveAcceso"**: `CodigoLlave, Edificio, Unidad, Nombre, Observacion`
  — Edificio es obligatorio (`LlaveAcceso.IdEdificio` es `NOT NULL`),
  Unidad opcional (solo para una llave de Tipo "Unidad" que apunta a una
  puntual).
- **"LlaveMovimiento"**: `CodigoLlave, Profesional, DepositoAbonado` —
  una fila por cada copia ya repartida; `Profesional` por Código, mismo
  criterio que el resto de la planilla.

### Mecánica (`app/importacion/importar_excel.py`)

`importar_planilla` arma `mapa_codigo_llave: dict[str, int] = {}` una
sola vez, ANTES del loop sobre `ENTIDADES_IMPORTABLES`, y lo pasa a cada
llamada de `importar_hoja` (parámetro nuevo, `mapa_codigo_llave`) — tiene
que vivir ahí, no dentro de `importar_hoja`, porque necesita persistir
ENTRE una llamada y la siguiente: la hoja "Llave" lo completa, las otras
dos lo leen después. `_resolver_referencias` suma un parámetro homónimo
y un helper nuevo, `_buscar_codigo_llave(codigo, mapa_codigo_llave,
errores)`, compartido por las ramas `"LlaveAcceso"`/`"LlaveMovimiento"` —
resuelve "CodigoLlave" contra el mapa en memoria, nunca contra ninguna
columna de la base (ese Código no se guarda en ningún lado).

`_ya_existe_identico` se renombra `_buscar_identico` y pasa a devolver el
**Id** de la fila igual ya cargada (no solo un bool) — necesario para
"Llave": si la fila de la hoja 1 resulta duplicada de un Tipo ya
existente (ej. toda la planilla se reimporta sin querer), igual hace
falta ese Id para que `mapa_codigo_llave[codigo]` apunte al Tipo YA
existente, y así "LlaveAcceso"/"LlaveMovimiento" de esa misma corrida
sigan pudiendo resolver su "CodigoLlave" en vez de reportar "no
encontrado" — un reimport completo de la planilla entera queda prolijo
(Llave se marca duplicada, LlaveAcceso/LlaveMovimiento se procesan
igual, apuntando al Tipo correcto) en vez de romper en cascada.

"LlaveAcceso"/"LlaveMovimiento" nunca se tratan como duplicadas de una
fila ya existente — mismo criterio (sin cambios de fondo) que ya regía
para los accesos/tenencias de la vieja hoja única: un acceso o una
tenencia nueva siempre se agrega, no se compara.

`importar_hoja`, rama `"Llave"`: valida que "Codigo" venga completo
(error de fila si falta) y que sea único DENTRO de esta misma hoja
(error si se repite); si pasa, crea la `Llave` (mismo armado de
`Nombre`/validación de `Tipo` de siempre, ahora SIN pasarle `id_edificio`
a `siguiente_nombre_llave` — el edificio todavía no se sabe en este
punto, se carga recién en "LlaveAcceso") e ingresa sola
`_STOCK_INICIAL_IMPORTACION = 1000` copias de stock
(`ingresar_copias(..., observacion="Stock inicial de importación
(ajustar con Ingreso/Pérdida)")`) — la clienta ajusta el número real a
mano después, desde la pantalla de Llaves.

Rama `"LlaveAcceso"`: llama a `agregar_acceso_llave` directo (reusa sus
mismas validaciones de siempre — una llave Tipo Edificio no admite más
de un edificio, Tipo Unidad exige una unidad puntual). Rama
`"LlaveMovimiento"`: mismo armado de siempre para la tenencia histórica
("Asignación" sin `CargoEspecial`, el depósito cobrado/monto sale de
`DepositoAbonado` + `Llave.ValorDepositoActual` del Tipo resuelto) — ya
no necesita `ingresar_copias` propio (consume del stock inicial que la
hoja "Llave" ya precargó).

### Instrucciones (`app/importacion/plantillas.py`)

La hoja "Instrucciones" de la planilla descargable suma un bloque nuevo
explicando las tres hojas, el orden de carga, qué es "Codigo"/
"CodigoLlave" y por qué, y el ajuste manual de stock pendiente después
de importar — mismo criterio que el resto de esa hoja (texto plano,
una línea por `ws.append`).

### Tests

`tests/test_importacion.py`: se borran los 7 tests de la vieja hoja
única (duplicada con edificio/profesional mezclados, accesos y
tenencias armados desde la misma fila) y se arma una batería nueva —
por hoja (`Llave`: guarda Código, ingresa stock inicial, sin Código
reporta error sin romper el resto, sin Tipo ídem, Código duplicado en
la misma hoja reporta error, duplicado real no se vuelve a crear;
`LlaveAcceso`: crea el acceso, Código inexistente reporta error,
Edificio inexistente reporta error; `LlaveMovimiento`: con/sin depósito
abonado, profesional inexistente, Código inexistente) más dos de punta a
punta: las tres hojas juntas enlazan por Código al mismo `IdLlave`, y
reimportar toda la planilla deja "Llave" duplicada pero "LlaveAcceso"
sigue resolviendo el Código contra el Tipo ya existente.

