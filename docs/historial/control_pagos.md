# Historial archivado — Control de pagos (ME1)

## Módulo extendido ME1: "Control de pagos" — primera implementación

Primera implementación del primero de los seis módulos extendidos
identificados en la especificación v1.0 (ver `Configuracion.
ModulosExtendidos`, ya existía como parámetro preparado pero sin nada
conectado — ver `docs/historial/sistema.md` para ese antecedente).
Pedido explícito de la clienta: control mes a mes de todo lo que hay
que abonar, sea del espacio o personal/familiar, con un solo lugar de
carga del que las demás pantallas levantan la información (no al
revés). Arrancado con el grueso del concepto ya definido, a iterar con
correcciones según lo que la clienta vaya encontrando en el uso real
(pedido explícito: "lo voy probando y las correcciones las hacemos por
lo que vaya encontrando con el sistema en sí" — no se espera que esta
primera vuelta quede perfecta).

### Modelo de datos

Dos niveles (`app/negocio/control_pagos.py`, tablas 3.35-3.37 de
`schema.sql`):
- `ConceptoControlPago`: el "maestro" recurrente (ej. "Edenor") — Nombre,
  Categoría (lista editable `CategoriaControlPagos`, las 13 que pasó la
  clienta), Afectación y Medio de pago sugerido.
- `InstanciaControlPago`: una fila por Concepto y Período — se genera en
  blanco (`generar_instancias_periodo`, llamada desde el `showEvent` de
  "Carga y control", idempotente) para cada concepto Activo que todavía
  no tenga una ese mes.

**Afectación** (pedido explícito: "la opción robusta", con referencias
reales, no texto suelto): no es una tabla aparte — `TipoAfectacion` +
hasta 5 columnas FK nullable directo en `ConceptoControlPago` (mismo
criterio que `GastoOperativo.Alcance`, `sanear_afectacion` limpia las
que no corresponden). Siete tipos: "Espacio general"/"Edificio"/"Unidad"
(referencias reales a las tablas de siempre del espacio — llega hasta
Unidad, no baja a Consultorio, mismo criterio que Gastos operativos) y
"Inmueble personal"/"Rodado"/"Persona" (catálogos nuevos y livianos,
`InmueblePersonal`/`Rodado`/`PersonaFamilia` — NO se reutilizó
`Responsable`, que es para contactos administrativos del negocio, otro
dominio) / "Familia" (sin catálogo, un único valor fijo).

**Sincronización con Balance del negocio** (pedido explícito: "lo que
cargo en módulo extendido pase al balance del negocio y no al revés"):
cada vez que cambia el Importe de una instancia imputada al Espacio
(Espacio general/Edificio/Unidad), `sincronizar_gasto_operativo` crea o
actualiza el `GastoOperativo` correspondiente con Origen="Importado" —
exactamente el mecanismo que ya estaba preparado para esto desde que se
armó Gastos operativos (ver `docs/historial/catalogos.md`: "esta tabla
se puede cargar tanto a mano como, a futuro, importada desde un módulo
extendido"). Si ya existe un gasto Manual en conflicto para el mismo
Período+Concepto, no se pisa (`gasto_en_conflicto`, regla ya existente).
Los conceptos personales/familiares/de rodados nunca tocan
`GastoOperativo`. Vaciar el Importe borra el gasto sincronizado.

### Decisiones confirmadas con la clienta antes de implementar

- Afectación con referencias reales (no texto libre) — ver arriba.
- No hace falta Consultorio como nivel de Afectación por ahora (se puede
  sumar después, mismo criterio que ya se usó para Gastos operativos).
- Un concepto nuevo puede arrancar directo en el mes en curso, no hace
  falta esperar al período siguiente.
- Además de "Editar" (vencimiento/monto de UN mes) y "Archivar"
  (cierra solo ese mes, el concepto sigue generándose), dos acciones
  más pedidas explícitamente: "Editar concepto seleccionado" (Nombre/
  Categoría/Afectación/Medio de pago sugerido del concepto en sí) y
  "Dar de baja concepto seleccionado" (para siempre — deja de generar
  instancias nuevas, el historial ya generado no se toca). Las dos
  viven como botones en el panel izquierdo (debajo de "Crear
  concepto"), no como botón por fila — "Dar de baja..." no entraba en
  la tabla sin angostar demasiado el resto de las columnas.

### Pantalla

`PantallaControlPagos` (`app/gui/pantallas/control_pagos.py`), cinco
solapas: "Carga y control" (formulario de alta a la izquierda — Nombre/
Categoría/Afectación/Medio de pago/Vencimiento/Importe/3 campos libres,
crea el concepto y, si se cargó algo, su primera instancia de una —
mismo criterio que el "Crear licencia" combinado de Novedades; tabla a
la derecha con los tres botones por fila: Editar/Marcar abonado/
Archivar, habilitados según Estado/si hay datos cargados), "Historial"
(filtros por Categoría/Concepto/Afectación/Medio de pago, "todos los
que se puedan poner" como pidió la clienta — mismo criterio "filtro que
solo afecta la visualización"), y los tres catálogos de Afectación
anidados (Inmuebles personales/Rodados/Personas, `PantallaCRUD`
genérica, sin código propio).

Solo aparece en el menú (`gui_main.construir_secciones`) con
`Configuracion.ModulosExtendidos` prendido — apagado (el default), ni
la Sección ni nada se ve, confirmando lo que ya estaba previsto para
ese parámetro. Prendido, pedido explícito de la clienta: categoría
PROPIA, tercera del menú ("Módulos extendidos", no mezclada con
"Parámetros del sistema" ni con la del espacio) — ahí van también los
que se sumen más adelante (ME2-ME6), no solo este.

### Bug real encontrado y arreglado en el camino

La migración que precarga las categorías/medios de pago en
`ListasEditables` (`app.db.migraciones._precargar_listas_control_
pagos`, para que lleguen también a una base YA en uso, no solo a una
nueva) corría dentro de `init_database`, ANTES de que quien llama
decida sembrar los valores por defecto — en una base recién creada
insertaba igual, dejando `ListasEditables` de estar vacía y haciendo
que `sembrar_listas_editables` (que solo siembra con la tabla ENTERA
vacía) se salteara TODOS los demás tipos (`CondicionFiscal`,
`MedioPago`, etc.), no solo los de este módulo. Arreglado agregando un
guard explícito: si `ListasEditables` está totalmente vacía (base
nueva, sin sembrar todavía), la migración no toca nada — esos dos
tipos ya están en `LISTAS_EDITABLES` de `seed.py`, así que una base
nueva los recibe por ese camino. Tests de regresión en
`tests/test_migraciones.py` (`test_base_nueva_siembra_listas_control_
pagos_via_seed_no_via_migracion` y dos más).

### Verificación de esta ronda

pyflakes limpio en los 9 archivos tocados/nuevos. Suite completa de
`test_control_pagos.py` (12, negocio), `test_gui_control_pagos.py` (11,
GUI), más `test_migraciones.py`/`test_gui_main.py`/`test_catalogos.py`/
`test_seed.py`/`test_main_window.py`/`test_pagos.py`/`test_gui_pagos.py`/
`test_balance.py`/`test_gui_balance.py`/`test_mensajes.py`/
`test_gui_mensajeria.py`/`test_gui_novedades.py`/
`test_gastos_operativos.py`: 660 passed. Verificado visualmente con
capturas offscreen de "Carga y control" e "Historial" (alta de
concepto, columnas de botones a su ancho real, Importe en blanco
cuando no se cargó nada — no "$ 0,00").

### Categoría propia en el menú

Pedido explícito de la clienta, ronda siguiente a la de arriba:
"Control de pagos" pasa a tener su PROPIA categoría en el menú lateral
("Módulos extendidos", tercera categoría, no mezclada con "Parámetros
del sistema" ni con la del espacio) — ahí van también los módulos
extendidos que se sumen más adelante (ME2-ME6), no solo este.

### Planilla de importación: cuatro hojas nuevas

Pedido explícito de la clienta, misma ronda: carga inicial de los
conceptos reales que ya tenía, vía la planilla de importación del
sistema (`app/importacion/`) — mismo criterio que `PlanPago` (una
excepción al alcance de la Etapa 1, que en general no importa entidades
que se cargan desde la propia pantalla: acá tiene sentido porque es
"lo que ya existía antes de empezar a usar el sistema", no algo que se
repita por planilla mes a mes).

Cuatro hojas nuevas (`definiciones.COLUMNAS_PLANTILLA`, en orden:
`InmueblePersonal`/`Rodado`/`PersonaFamilia` ANTES que
`ConceptoControlPago`, que las referencia): solo se importan los
CONCEPTOS (el maestro) — las instancias de cada período las genera
sola la pantalla al entrar, nunca por planilla. `ConceptoControlPago`
tiene columnas "Edificio"/"Unidad"/"InmueblePersonal"/"Rodado"/
"Persona" (una sola completa según "TipoAfectacion", validado contra
los siete valores exactos — `app.importacion.importar_excel._resolver_
referencias`, mismo patrón que el resto de las entidades con
referencia a otra ya cargada en la planilla).

Se le armó y mandó por acá (no es parte del repositorio) una copia YA
PRECARGADA con los ~60 conceptos reales que pasó la clienta (categoría,
afectación y medio de pago actual de cada uno, como los describió) —
confirmado que importa limpio contra una base de prueba. Los conceptos
imputados a una Unidad del espacio (28 de los 60: Edenor/AYSA/
Municipal/ARBA/Expensas/etc. de las cuatro unidades) quedaron con
"COMPLETAR (tu edificio real)" en la columna Edificio — el sistema no
tiene forma de adivinar el nombre real del edificio de cada unidad, así
que esas filas fallan la importación a propósito (mensaje de error
claro, señalando exactamente cuál) hasta que la clienta lo reemplace a
mano por el Edificio real antes de importar. Las dos Localidades
usadas para los inmuebles personales (San Justo/CABA) se precargaron
con datos geográficos reales (no inventados) — si ya existen en el
sistema con otros valores, sacar esas dos filas de la hoja Localidad
antes de importar, para no generar una duplicada (el chequeo de
duplicados compara la fila entera, no solo el nombre).

Tests nuevos en `tests/test_importacion.py` (7): los siete
TipoAfectacion resolviendo correctamente, error con tipo inválido,
error con Edificio/Unidad inexistente, error con Inmueble personal
inexistente, error de Localidad inexistente (hoja InmueblePersonal), y
que un concepto duplicado no se vuelve a crear. Suite completa de
`test_importacion.py`: 42 passed.

### Pendiente

Nada más del resto de los módulos extendidos (ME2-ME6) — fuera de
alcance de esta ronda, se planifican recién al iniciar esa etapa.

## Control de pagos (ME1): rediseño completo de "Carga y control"

Pedido explícito de la clienta, 17 puntos en un mismo mensaje sobre
esta sola solapa. Dos ambigüedades consultadas antes de empezar
(`AskUserQuestion`): la idea de "tres columnas arriba" la retiró ella
misma ("me olvidé de borrarlo, era una idea y luego me arrepentí") —
queda solo "que el primer elemento arranque en el pixel 85, y de ahí
baje el resto", mismo mecanismo de siempre (ver "Jerarquía de
títulos" en CLAUDE.md), sin coordinar con una segunda columna porque
acá no la hay. Y "Duplicar para período próximo" confirmado en blanco
(solo Medio de pago, igual que un concepto nuevo) — nunca copia
Vencimiento/Importe de la fila de origen.

- **Avance de mes archiva lo no abonado.** `app.negocio.control_
  pagos.archivar_pendientes_del_periodo(conn, periodo)` (nueva):
  archiva TODA instancia Pendiente de `periodo`, tenga o no datos
  cargados — a diferencia de `archivar_instancia` (el botón manual
  de una fila, que sigue exigiendo vencimiento/importe vacíos, sin
  tocar). Se puede reabrir después desde "Historial" con "Editar
  registro". Llamada desde `avance_mes.avanzar_mes` (nuevo campo
  `ResumenAvanceMes.instancias_control_pagos_archivadas`), junto a
  la limpieza de fechas especiales del período cerrado.
- **Columna "Período" (yyyy-mm) después de "Medio de pago".** La
  tabla de "Carga y control" ahora muestra a la vez las instancias
  del período actual Y las del período próximo (si se duplicó
  alguna, ver abajo) — sin esta columna no se podrían distinguir.
- **Pixel 85 + achique del 15% del panel del formulario.**
  `_ALTO_TITULO_CARGA_CONTROL = 7` (mismo valor medido que Reservas
  regulares/aisladas y los paneles de Novedades — confirmado
  programáticamente offscreen: con ese valor, el primer elemento
  queda al mismo píxel relativo, ±1px, que la referencia aprobada).
  `_ANCHO_PANEL_CARGA_CONTROL`/`_ANCHO_CAMPO_CARGA_CONTROL` son
  `_ANCHO_PANEL_IZQUIERDA`/`_ANCHO_CAMPO` al 85% (238px/204px) —
  constantes propias de esta pantalla, no se tocó el panel de
  filtros de "Historial" (comparte las constantes genéricas, pero
  no estaba pedido achicarlo). Verificado con captura offscreen que
  ningún botón queda con el texto cortado al nuevo ancho.
- **Campos libres fuera de la UI.** Las tres `QLineEdit` y la
  lectura/escritura de `CampoLibre1/2/3` en `_crear` se sacaron del
  todo de este archivo — las columnas siguen en el schema, sin uso.
- **Botones reordenados y nuevos, todos habilitados solo con
  selección.** Orden final de la columna 1: Nombre/Categoría/
  Afectación/Medio de pago/Vencimiento/Importe, "Crear concepto"
  (subido al lugar que dejaron los campos libres, sin la línea
  divisoria que había antes), "Editar concepto seleccionado", "Dar
  de baja concepto seleccionado", "Duplicar para período próximo"
  (nuevo), "Eliminar registro duplicado" (nuevo), línea divisoria,
  "Editar registro"/"Marcar abonado"/"Archivar registro" (bajados
  acá desde el final de cada fila de la tabla — ya no hay
  `cellWidget` por fila). `_actualizar_botones_seleccion` centraliza
  el habilitado: todos requieren una fila seleccionada, y además
  "Duplicar..." solo sobre una fila del período ACTUAL, "Eliminar
  registro duplicado" solo sobre una del período PRÓXIMO (pedido
  explícito: "solo se pueden duplicar registros para el período
  próximo nada más"), "Marcar abonado"/"Archivar registro" con la
  misma condición de Estado/datos cargados que ya tenían como botón
  de fila. `app.negocio.control_pagos.duplicar_para_periodo_
  proximo`/`eliminar_instancia_duplicada` (nuevas) — la segunda
  también borra el `GastoOperativo` sincronizado si lo había, mismo
  criterio que vaciar un Importe.
- **Ancho de tabla repartido.** Al sacar las tres columnas de botón,
  el `Stretch` que ya tenían Nombre/Categoría/Afectación/Medio de
  pago absorbe todo el ancho liberado solo — no hizo falta ningún
  cálculo manual. Período/Vencimiento/Importe/Estado quedan en
  `ResizeToContents`.
- **Colores de fila por vencimiento + gris para lo resuelto.**
  `_PanelCargaControl._color_fila`: gris (`COLOR_GRIS`, nueva
  constante en `estilos.py`, mismo hex que `mensajeria._COLOR_
  FONDO["gris"]`) para Abonado/Archivado sin mirar el vencimiento;
  si Pendiente, violeta (`COLOR_VIOLETA`, nueva constante, mismo
  criterio) si ya venció, rojo si vence hoy, amarillo si vence
  mañana, verde si faltan 2 días o más, blanco si no tiene
  vencimiento cargado. Letra blanca salvo sobre amarillo (letra
  negra) — mismo criterio exacto que Centro de mensajería.
- **Orden de filas en tres grupos.** `_clave_orden_instancia`:
  arriba las Pendientes sin vencimiento O sin importe (por Nombre,
  Afectación); en el medio las Pendientes con ambos datos (por
  Período más próximo, Vencimiento, Nombre, Afectación); al fondo,
  en gris, las Abonadas/Archivadas — "parecido a lo que se hace con
  el centro de mensajería".
- **Alertas de éxito en cada acción** (crear/editar concepto, dar de
  baja, duplicar, eliminar duplicado, editar/marcar abonado/archivar
  registro) — antes varias de estas acciones no avisaban nada.
- **F5 reinicia la solapa.** `_PanelCargaControl.reiniciar()`
  (nuevo): resetea el formulario (a diferencia de `showEvent`, que
  no lo toca), limpia la selección de la tabla, refresca y devuelve
  el foco a "Nombre" — mismo criterio general documentado en
  CLAUDE.md ("F5... reinicia desde cero, distinto de showEvent").
- **"Editar registro" en "Historial".** Botón nuevo debajo de los
  cuatro filtros, habilitado solo con una fila seleccionada; abre
  `_DialogoEditarInstancia(..., incluir_estado=True)` — mismo diálogo
  que ya existía, con un combo de Estado sumado solo para este caso
  (la "Editar registro" de "Carga y control" no lo necesita, ahí
  "Marcar abonado"/"Archivar registro" están aparte). `app.negocio.
  control_pagos.actualizar_instancia` suma el parámetro `estado`
  (mismo patrón `_SIN_CAMBIOS` que ya tenía para vencimiento/importe/
  medio de pago), validado contra `ESTADOS_INSTANCIA`.

Verificado con captura offscreen (`Carga y control` con filas en cada
color/bucket, incluida una duplicada para el período próximo, y
`Historial` con "Editar registro" habilitado) y con el mismo script
de medición programática usado para confirmar el pixel 85 contra
Reservas regulares como referencia. Tests nuevos: 8 en
`tests/test_control_pagos.py` (archivar_pendientes_del_periodo,
duplicar_para_periodo_proximo ×2, eliminar_instancia_duplicada,
actualizar_instancia con estado ×2), 1 en `tests/test_avance_mes.py`,
8 en `tests/test_gui_control_pagos.py` (columna Período, botones sin
selección, duplicar/eliminar duplicado, gris al fondo, los cuatro
colores de vencimiento, reiniciar, Editar registro de Historial) —
más 3 tests existentes ajustados a la nueva API (los botones de fila
pasaron a vivir en la columna 1). pyflakes limpio en los 4 archivos
tocados. Suite completa sin regresiones nuevas (los mismos ~10
fallos conocidos del sandbox, ver CLAUDE.md).

**Ronda siguiente, tres ajustes de layout sobre esta misma solapa:**

- **"Período actual" en una sola línea, el valor en negrita.** Pasa
  de dos widgets (`_titulo_campo` + `QLabel`) a uno solo:
  `self.etiqueta_periodo.setText(f"Período actual: <b>{periodo}</b>")`
  — `QLabel` detecta el HTML solo (`Qt.AutoText`, sin `setTextFormat`
  explícito, mismo criterio que `_fmt_saldo_label` en `pagos.py`). Al
  sacar un renglón, todo lo de abajo sube solo (es la misma
  `QVBoxLayout`, no hace falta tocar nada más) y la columna deja de
  necesitar scroll vertical para llegar a "Archivar registro".
- **Ancho de columna 1 recalculado desde el texto real, no desde un
  85% arbitrario.** El 15% de achique de la ronda anterior dejaba el
  botón "Dar de baja concepto seleccionado" en 204px cuando su
  `sizeHint()` real (medido con `QFontMetrics` contra la hoja de
  estilos real) es 239px — se cortaba. `_ANCHO_CAMPO_CARGA_CONTROL`
  pasa a 240 (el que ya tenía el resto del sistema, antes de esta
  pantalla) y `_ANCHO_PANEL_CARGA_CONTROL` a 262. El ancho que gana
  el panel (262 contra los 238 que tenía) se le resta a la columna
  "Medio de pago" de la tabla (pedido explícito, no a Nombre/
  Categoría/Afectación): sale del `Stretch` a `Interactive` con un
  ancho fijo (`_ANCHO_MEDIO_PAGO_CARGA_CONTROL`, medido contra su
  ancho real bajo Stretch menos lo que gana la columna 1) — Nombre/
  Categoría/Afectación siguen en Stretch sin cambios, la cuenta
  cierra sola (lo que pierde una columna es exactamente lo que gana
  la otra, verificado con captura y medición programática).
- **10% de "Categoría" pasa a "Importe".** Mismo mecanismo que
  "Medio de pago": las dos salen de Stretch/`ResizeToContents` a un
  ancho fijo propio (`_ANCHO_CATEGORIA_CARGA_CONTROL`/`_ANCHO_
  IMPORTE_CARGA_CONTROL`), medidos contra sus anchos reales con datos
  cargados — Nombre/Afectación no se tocan.

Verificado con captura offscreen y medición programática de cada
columna antes/después (`tabla.columnWidth`) confirmando que Nombre/
Afectación quedan exactamente iguales. Tests nuevos en `tests/test_
gui_control_pagos.py`: `test_etiqueta_periodo_actual_en_una_sola_
linea_con_el_periodo_en_negrita`, `test_columna_1_entra_el_boton_
dar_de_baja_sin_cortar`, `test_anchos_de_columna_categoria_medio_
pago_e_importe_se_ajustan_sin_tocar_nombre_ni_afectacion`. pyflakes
limpio, resto de la suite de control de pagos sin regresiones (57
tests).

**Ronda siguiente, dos pedidos más sobre esta misma tabla:**

- **Ordenable por click en el encabezado.** `self._orden = OrdenTabla
  (self.tabla, self.actualizar)` (mismo mecanismo que ya usan las
  tablas de Pagos, `app/gui/widgets/orden_tabla.py`): un click ordena
  por esa columna, otro click invierte el sentido. El orden por
  defecto (los tres grupos de `_clave_orden_instancia`) se sigue
  aplicando siempre primero; si hay una columna elegida por click, se
  aplica ENCIMA (`_clave_orden_columna`, sort estable). `reiniciar()`
  (F5) llama a `self._orden.reiniciar()`, mismo criterio que el resto
  del sistema.
- **Fila de filtros por columna arriba de la tabla.** Un `QLineEdit`
  por columna de Nombre a Vencimiento incluido (texto libre, sin
  distinguir mayúsculas ni acentos — mismo criterio que "Buscar" de
  los catálogos genéricos) y, sobre Importe/Estado, un botón
  "Reiniciar filtros" en vez de más filtros. Es un widget PROPIO (una
  fila en su propio `QHBoxLayout`, arriba de la tabla dentro de un
  `QVBoxLayout` compartido) y no una fila de la `QTableWidget` en sí —
  así no hace falta pelear con la selección ni con el orden por click
  de la tabla. El ancho de cada campo se sincroniza con el de su
  columna real (`_sincronizar_ancho_filtros`, incluido un espaciador
  al ancho del encabezado vertical de filas para que el primer campo
  arranque justo donde arranca "Nombre") — se llama al armar la
  pantalla, en cada `actualizar()` (las columnas en `ResizeToContents`
  pueden cambiar de ancho con los datos) y cada vez que el usuario
  redimensiona una columna (`header.sectionResized`); verificado con
  captura y medición programática que la sincronización también
  sobrevive a un resize de ventana completo. El filtrado se aplica
  sobre la lista de Python ANTES de ordenar y poblar la tabla (mismo
  criterio que ya usa "Historial" con sus combos) — F5 y "Reiniciar
  filtros" limpian los seis campos por igual.

Tests nuevos en `tests/test_gui_control_pagos.py`:
`test_click_en_encabezado_ordena_por_esa_columna_y_el_segundo_click_
invierte`, `test_f5_reiniciar_vuelve_al_orden_por_defecto`,
`test_filtros_por_columna_acotan_la_tabla_sin_distinguir_acentos_ni_
mayusculas`, `test_filtros_por_columna_se_combinan_entre_si`,
`test_boton_reiniciar_filtros_los_vuelve_a_su_estado_natural`,
`test_f5_reiniciar_tambien_limpia_los_filtros_por_columna`,
`test_anchos_de_filtros_quedan_sincronizados_con_las_columnas_
reales`. pyflakes limpio, suite completa de Control de pagos/Pagos/
Avance de mes sin regresiones nuevas (238 passed, los mismos 3
fallos conocidos del reloj del sandbox).

## Control de pagos: rediseño completo de "Carga y control" en 4 columnas

Pedido explícito de la clienta sobre el layout de la ronda anterior
(un solo panel de formulario a la izquierda + tabla a la derecha):
pasa a 4 columnas de ancho IGUAL (`stretch=1` cada una en un
`QHBoxLayout` común, cada una un `QWidget` propio con
`objectName="panelSolapa"`) que abarcan todo el ancho de la pantalla,
con la tabla ahora DEBAJO de esas 4 columnas (no al costado — el
layout externo de `_PanelCargaControl` pasa de `QHBoxLayout` a
`QVBoxLayout`), escroleable (`QTableWidget` normal, sin
`QScrollArea` — ya no hace falta, al no competir por espacio con un
panel lateral).

- **Columna 1:** Nombre, Categoría, Afectación (sus dos combos) y
  Medio de pago.
- **Columna 2:** Vencimiento, Importe, y el botón principal "Crear
  concepto".
- **Columna 3:** los 4 botones secundarios sobre el CONCEPTO
  seleccionado — "Editar concepto seleccionado"/"Dar de baja concepto
  seleccionado"/"Duplicar para período próximo"/"Eliminar registro
  duplicado" (bajados de la columna 1 de la ronda anterior, sin
  cambiar su comportamiento).
- **Columna 4:** los filtros, en cascada MUTUA — Nombre/Categoría/
  Afectación/Medio de pago no tienen jerarquía entre sí (a diferencia
  de una cascada jerárquica real del sistema, ej. Localidad->
  Edificio->Unidad en Estadísticas), así que cada combo se acota por
  la selección VIGENTE de los otros tres, nunca la propia
  (`_repoblar_filtros_cascada`/`_coincide_filtros` con el parámetro
  `excepto`) — si se acotara también a sí mismo, elegir un valor
  haría desaparecer las demás opciones de ESE mismo combo,
  imposibilitando cambiar la selección. Sentinel `_TODOS` (mismo
  criterio que `_PanelHistorialControlPagos._TODAS`) para "sin
  filtro", nunca `None`. Buscador con el mismo mecanismo que el
  selector de profesional (`habilitar_busqueda_profesional`, `app/
  gui/widgets/selector_profesional.py` — confirmado genérico, no
  depende de que el combo tenga datos de un profesional, solo de que
  ya esté poblado con pares etiqueta/dato) — no cambia de ancho al
  seleccionar ni al tipear, mismo `setFixedWidth` que el resto de los
  campos. Reemplaza por completo la fila de filtros de texto libre
  por columna que había armado la ronda anterior (sacados
  `filtros_columna`, `_sincronizar_ancho_filtros`, `_coincide_
  filtros` de texto libre, `_normalizar_filtro` y las constantes de
  ancho que esa fila necesitaba).

**Pixel 85 en las 4 columnas:** cada columna usa el mismo margen
superior que ya tenían Reservas regulares/Novedades
(`_ALTO_TITULO_CARGA_CONTROL = 7`, sin cambios — confirmado que sigue
dando el mismo resultado relativo en esta estructura de 4 columnas
planas, sin el `QScrollArea` que envolvía el panel único de antes).
Verificado por medición programática (offscreen) que el primer
elemento de las 4 columnas — título o botón, lo que haya primero en
cada una — queda exactamente a la misma altura relativa al panel, y
que las 4 columnas quedan del mismo ancho entre sí (±1px por
redondeo del `stretch` al repartir el ancho total entre 4).

**Tabla:** vuelve a 8 columnas de datos (Nombre/Categoría/Afectación/
Medio de pago en `Stretch`, el resto en `ResizeToContents` — se
revierten los anchos fijos "robados" entre columnas de la ronda
anterior, que ya no hacen falta al no competir con un panel lateral
angosto) más 3 columnas de botón al final de cada fila — "Editar"
(antes "Editar registro"), "Abonar" (antes "Marcar abonado") y
"Archivar" (antes "Archivar registro"), mismas funciones y
comportamientos, vueltas a vivir por fila (`_armar_botones_fila`) en
vez de en la columna 1.

**Bug real encontrado y arreglado en el camino — abort del proceso al
cerrar, NO una falla de ningún test:** la primera versión de
`_armar_botones_fila` reusaba el botón YA EXISTENTE en esa posición
(fila_idx, columna) con `self.tabla.cellWidget(fila_idx, columna)`,
llamando `.clicked.disconnect()` + `.connect(...)` para apuntarlo a
la instancia nueva — el mismo patrón que tenía la primera
implementación de este módulo. Como `_clave_orden_instancia`/un
click de encabezado puede cambiar qué instancia cae en cada posición
entre un `actualizar()` y el siguiente, reconectar un botón visual
reciclado sobre una posición que antes tenía una instancia distinta
corrompía silenciosamente el estado de Qt/shiboken — los 26 tests de
este archivo pasaban igual (ninguna aserción fallaba), pero el
PROCESO terminaba con `Fatal Python error: bool_dealloc` (refcount
corrupto) al cerrarse, solo en determinadas combinaciones de archivos
de test ejecutados en el mismo proceso (confirmado: solo este
archivo solo = aborta; combinado con `test_gui_pagos.py` = aborta;
combinado con `test_gui_placas.py` = NO aborta — la combinación
exacta de asignaciones/liberaciones de memoria es lo que determina si
se manifiesta, no algo determinable por lógica de la app).
Confirmado con el código ANTERIOR a esta ronda (sin estos botones por
fila) que el abort no existía antes — es una regresión de esta
ronda, no algo preexistente del sandbox. Arreglado creando un botón
`QPushButton` NUEVO en cada `actualizar()` (igual que ya se hace con
el resto de las celdas de la fila, un `QTableWidgetItem` nuevo cada
vez) en vez de reusar por posición — de paso, `self.tabla.
setRowCount(0)` antes de volver a crecer con `setRowCount(len(
filas))`, para que Qt suelte los cell widgets viejos de una en vez
de arrastrar alguno huérfano a una fila con otro contenido
(confirmado con captura offscreen: sin este `setRowCount(0)`, un
botón "Archivar" de una fila vieja quedaba pintado encimado contra la
esquina superior izquierda de la tabla al agregar conceptos uno por
uno — mismo tipo de huérfano ya documentado en Aumentos, "`setCellWidget`
NO borra solo el widget que reemplaza").

Tests reescritos/nuevos en `tests/test_gui_control_pagos.py` para la
nueva API (botones por fila vía `tabla.cellWidget(fila, columna)` en
vez de `panel.boton_editar_registro`/etc.; filtros vía los 4 combos
`combo_filtro_*` en vez de `filtros_columna`):
`test_las_cuatro_columnas_arrancan_a_la_misma_altura_y_con_igual_
ancho`, `test_boton_dar_de_baja_entra_en_el_ancho_fijo_compartido_
sin_cortar`, `test_filtro_categoria_acota_la_tabla_por_la_seleccion`,
`test_filtros_cascada_se_acotan_mutuamente_sin_acotar_la_propia_
seleccion`, `test_boton_reiniciar_filtros_vuelve_todos_los_combos_a_
todos`, `test_f5_reiniciar_tambien_reinicia_los_filtros_cascada` —
más los tests existentes de botones/colores/orden adaptados a la
nueva ubicación de los tres botones por fila. pyflakes limpio. Suite
completa sin regresiones nuevas (mismos fallos conocidos del
sandbox/reloj, ver CLAUDE.md) y sin el abort al cerrar en ninguna
combinación de archivos probada.

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
  tarjeta nueva de Panel de control (ver `docs/historial/sistema.md`)
  para no duplicar el cálculo — en "Carga y control" se calculan además
  los cuatro filtros en cascada que ya tenía la pantalla, mientras que
  en Panel de control es el total sin filtrar.

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

## Control de pagos ("Carga y control"): "Total expensas sin abonar" + saldos por banco, campo "N° transacción", Cuenta/Id a la derecha

Cuatro pedidos puntuales de la clienta sobre `_PanelCargaControl` (`app/
gui/pantallas/control_pagos.py`):

- Etiqueta nueva "Total expensas sin abonar" debajo de "Eliminar
  registro duplicado" (columna 3): suma el `Importe` de toda instancia
  `Estado='Pendiente'` del período vigente cuyo concepto tiene
  `Categoria='Expensas'`. Debajo, cuatro etiquetas más — "Saldo a
  cubrir en CA Bco Patagonia"/"...Provincia"/"Saldo a cubrir Bco
  Hipotecario"/"...Macro" — mismo criterio pero agrupado por `MedioPago`
  (los cuatro medios de pago bancarios ya precargados en
  `MedioPagoControlPagos`, ver `seed.py`), sin filtrar por categoría.
  Nueva función `saldos_expensas_y_bancos` (`app/negocio/control_pagos.
  py`) — a diferencia de las siete etiquetas de conteo de la columna 2
  (que SÍ reflejan los cuatro filtros en cascada de la columna 4), estas
  cinco son totales absolutos del período actual, siempre sobre TODO lo
  cargado (mismo criterio que los totales "sin filtro" de Panel de
  control). Los cinco `QLabel` necesitan `setWordWrap(True)` +
  `setFixedWidth(_ANCHO_CAMPO_CARGA_CONTROL)` — sin esto, el texto largo
  ("Saldo a cubrir en CA Bco Patagonia: $...") ensanchaba esa columna
  más que las otras tres del `QHBoxLayout` con `stretch=1` parejo.
- Campo nuevo "N° transacción (opcional)" en `_DialogoEditarInstancia`,
  debajo de "Cuenta/Id (opcional)": texto libre, reusa `CampoLibre2` de
  `InstanciaControlPago` (`CampoLibre1` ya lo usa Cuenta/Id) — pedido
  explícito de la clienta: "por si el día de mañana tengo que
  consultar", sin mostrarse en ninguna columna de ninguna tabla (a
  diferencia de Cuenta/Id) ni heredarse de un período al siguiente (es
  el número de operación de ESE pago puntual, no un dato del concepto).
  `actualizar_instancia` suma el parámetro `numero_transaccion` →
  `CampoLibre2`.
- Columna "Cuenta/Id" de la tabla de "Carga y control" pasa a alineada
  a la derecha (`item_numero`, mismo helper que las columnas numéricas,
  aunque el contenido sea texto libre).

Tests: `tests/test_control_pagos.py` (+2: `saldos_expensas_y_bancos`
con pendiente/abonado/otro medio de pago mezclados; `numero_
transaccion` mapea a `CampoLibre2` sin tocar `CampoLibre1`).
`tests/test_gui_control_pagos.py` (+4: alineación de Cuenta/Id, las
cinco etiquetas muestran los valores de `saldos_expensas_y_bancos`,
el campo del diálogo precarga desde `CampoLibre2`, guardar vía
"Editar" persiste el número de transacción sin sumar ninguna columna
nueva a la tabla; 3 fakes `_DialogoFalso` de tests preexistentes
actualizados con el método `numero_transaccion()` nuevo). Suite:
27 + 50 passed, más 171 passed en la corrida conjunta con `test_
avance_mes.py`/`test_catalogos.py` (los 3 fallos de `test_avance_mes.py`
son los conocidos por el reloj real del sandbox, ajenos a esta ronda).
pyflakes limpio en los cuatro archivos tocados.
