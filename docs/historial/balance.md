# Historial archivado — Balance del negocio

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

## Balance del negocio: Ingresos/Resultado en tabla, "Ver historial"/
## "Ver período actual" en vez de "Actualizar"

Pedido de la clienta de pulir las solapas "Ingresos"/"Resultado" de
"Balance del negocio" (la solapa "Gastos" no se tocó):

- **De etiquetas sueltas a tabla.** Las dos solapas mostraban su
  resultado en un `QLabel` por dato (`fmt_dato`, con un título armado a
  mano, "Ingresos período MM-AAAA"). Pasan a una tabla a la derecha del
  panel de filtros (`_armar_tabla`, nueva, compartida por las dos —
  Stretch en todas las columnas, mismo criterio "pocas columnas,
  importancia pareja" que Placas/Importar planilla), con las columnas
  pedidas explícitamente: "Período"/"Ingreso por horas regulares"/
  "Ingreso por horas aisladas"/"Ingreso por feriados y días
  especiales"/"Total ingresos" en Ingresos; "Período"/"Total ingresos"/
  "Total gastos"/"Balance del período" en Resultado. Por defecto (al
  entrar a la solapa, o al cambiar cualquier filtro) la tabla muestra
  una ÚNICA fila, la del período elegido en el campo "Período" — mismo
  comportamiento de siempre, solo que ahora en una fila de tabla en vez
  de en etiquetas.
  - **Bug encontrado al armar esto (mismo que "Valores vigentes" de la
    ronda anterior, pero por una causa distinta)**: con las 5 columnas
    de Ingresos en Stretch parejo, "Ingreso por feriados y días
    especiales" (la más larga) quedaba con el título recortado a los
    dos lados — no alcanzaba el ancho que le tocaba en partes iguales.
    Se resuelve con el mismo recurso ya documentado en "Selectores y
    fecha"/Estadísticas para títulos de columna largos: un `"\n"`
    literal partiéndolo en dos líneas ("Ingreso por feriados\ny días
    especiales") — `QHeaderView` agranda el alto de encabezado solo,
    sin tocar el ancho de las demás columnas ni el texto pedido por la
    clienta (sigue diciendo exactamente "Ingreso por feriados y días
    especiales", solo partido visualmente).
- **"Actualizar" se saca, reemplazado por dos botones.** La clienta
  notó que "Actualizar" (`botonPrimario`) no cumplía ninguna función
  real — los filtros ya estaban conectados para recalcular solos
  (`editingFinished`/`currentIndexChanged` ya llamaban a `actualizar()`
  antes de este pedido). En su lugar, dos botones nuevos en
  `_PanelFiltrosMixin` (compartidos por las dos solapas, Gastos no los
  tiene):
  - **"Ver historial"** (`botonPrimario`): llena la tabla con una fila
    por cada período que tiene algún dato cargado en el sistema, del
    más nuevo al más viejo — reusa `app.negocio.estadisticas.
    _periodos_para_filtro(conn, desde=None, hasta=None)` (import
    cruzado de un símbolo privado, mismo criterio que
    `_ids_consultorio_del_alcance`, ya importado antes en este módulo),
    que ya devuelve esos períodos en ese orden sin necesitar invertir
    nada. Respeta el alcance de ubicación elegido (Localidad/Edificio/
    Unidad/Consultorio), igual que la fila única de `actualizar()`.
  - **"Ver período actual"** (`botonSecundario`): solo toca el campo
    Período (lo vuelve a `periodo_actual(conn)`) y llama a
    `actualizar()` — a propósito NO toca los combos de ubicación, a
    diferencia del viejo `_restablecer` (el handler de "Actualizar",
    que si reiniciaba toda la cascada) — pedido explícito de la
    clienta: "ahi setea de nuevo el período actual en el filtro de
    período", nada más. `_restablecer` se borra entero, sin otro
    consumidor.
  - Cambiar cualquier filtro de ubicación mientras se está viendo el
    historial (varias filas) vuelve a mostrar una sola fila — mismo
    mecanismo de siempre (`currentIndexChanged` sigue llamando a
    `actualizar()`, no a `_ver_historial()`), interpretación propia sin
    pedido explícito sobre este caso puntual: cambiar un filtro de
    ubicación es un pedido nuevo de "qué estoy mirando", no tiene
    sentido que seguir mostrando el historial viejo sin ese filtro
    aplicado.

Tests nuevos/reescritos en `tests/test_gui_balance.py`: los que
revisaban las etiquetas (`etiqueta_regulares`/etc.) pasan a revisar la
tabla (una fila, columnas en el orden pedido);
`test_botones_historial_y_periodo_actual_tienen_los_estilos_correctos`;
`test_ingresos_ver_historial_muestra_todos_los_periodos_mas_nuevo_arriba`/
`test_resultado_ver_historial_muestra_todos_los_periodos_mas_nuevo_arriba`
(con una `ReservaRegular` del período anterior al actual, para tener
más de un período con datos); `test_ingresos_ver_periodo_actual_
vuelve_a_una_sola_fila`/`test_resultado_ver_periodo_actual_vuelve_a_
una_sola_fila`.

## Gastos operativos: identificación por Consultorio, y prorrateo en cascada en Balance

Dos pedidos relacionados sobre "Balance del negocio" (repaso de la
rentabilidad por Unidad que ya ofrece el formulario): Gastos operativos
suma un cuarto nivel de Alcance, Consultorio, y la forma de atribuir un
gasto cargado a un nivel superior a un filtro más específico pasa de
"excluir los generales" a prorratearlos en cascada.

### Consultorio como cuarto nivel de Alcance (improbable que se use, "tenelo preparado por las dudas")

`ALCANCES_GASTO` (`app.negocio.gastos_operativos`) suma "Consultorio" a
los tres de siempre (Espacio general/Edificio/Unidad) — sigue siendo
excluyente, un gasto nunca queda asociado a más de un nivel a la vez:
`sanear_alcance` ahora limpia también `IdConsultorio` cuando el Alcance
no es ese, y limpia `IdEdificio`/`IdUnidad` cuando sí lo es.

`GastoOperativo` suma la columna `IdConsultorio` (referencia a
`Consultorio`) — pero a diferencia de cualquier columna nueva de
`_COLUMNAS_NUEVAS`, el CHECK de `Alcance` ya estaba fijo a los tres
valores originales desde que se creó la tabla, y SQLite no permite
ensanchar un CHECK con `ALTER TABLE`. `app.db.migraciones.
_ampliar_alcance_gasto_a_consultorio` recrea la tabla entera (patrón
estándar de SQLite: tabla nueva con el CHECK ya correcto, copiar los
datos, reemplazar la vieja) en vez de sumar una entrada más a
`_COLUMNAS_NUEVAS` — es idempotente (no hace nada si `GastoOperativo` ya
tiene `IdConsultorio`) y se llama al final de `aplicar_migraciones`,
después de que la columna `CampoLibre1/2/3` de esa misma tabla ya se
sumó por la vía genérica (así la tabla nueva tiene algo que copiar para
esas tres columnas también).

`catalogos.pantalla_gastos_operativos` suma `Campo("IdConsultorio",
"Consultorio", tipo="combo", opciones=_opciones_consultorio_o_ninguno_
gasto)` justo después de `IdUnidad` en la lista de `Campo` — como la
tabla del catálogo arma sus columnas en el mismo orden que esa lista
(criterio de siempre de `PantallaCRUD`), "Consultorio" queda como
columna de la tabla justo después de "Unidad", tal cual se pidió.
`_al_abrir_dialogo_gasto` suma el tercer combo a la cascada de
habilitar/limpiar: Alcance="Consultorio" habilita solo ese combo
(deshabilita y limpia Edificio/Unidad), cualquier otro Alcance
deshabilita y limpia Consultorio — mismo mecanismo exacto que ya regía
entre Edificio/Unidad, extendido a tres ramas en vez de dos.

Confirmado a la clienta de paso: Categoría sigue siendo un combo
abierto que sugiere los valores de Listas editables
(`TipoLista="CategoriaGasto"`) pero admite tipear uno nuevo ahí mismo
(`combo_editable=True`); Concepto sigue siendo texto libre sin ningún
validador (`Campo("Concepto", "Concepto")`, tipo="texto" por default)
— ninguno de los dos cambió con este pedido.

Tests nuevos: `tests/test_gastos_operativos.py` (`sanear_alcance` con
Consultorio limpia Edificio/Unidad, y Edificio/Unidad limpian también
Consultorio); `tests/test_migraciones.py` (una base vieja de
GastoOperativo gana `IdConsultorio` y el CHECK ensanchado sin perder
los datos ya cargados, idempotencia); `tests/test_catalogos.py` (el
combo de Consultorio habilita/deshabilita igual que los otros dos, la
columna "Consultorio" queda justo después de "Unidad" en `campos`, un
gasto con Alcance="Consultorio" se guarda y se lee con `IdEdificio`/
`IdUnidad` en `None`).

### Balance del negocio: prorrateo en cascada en vez de excluir los generales

Al confirmar con la clienta la nota sobre rentabilidad por Unidad (un
gasto de Edificio se contaba 100% contra CUALQUIER Unidad filtrada de
ese edificio, sin prorratear), propuso un criterio general y explícito
para todo "Balance del negocio", no solo para ese caso puntual: un gasto
cargado a un nivel superior se reparte en PARTES IGUALES, en cascada,
nivel por nivel, hacia los niveles inferiores de la jerarquía —
"Espacio general" se divide por igual entre todas las Localidades que
haya, lo que le toca a cada una se vuelve a dividir por igual entre sus
Edificios, de ahí entre sus Unidades, y de ahí entre sus Consultorios; un
gasto de Edificio arranca esa misma cascada un escalón más abajo, de
Unidad un escalón más abajo todavía (y uno de Consultorio, el nivel
nuevo de arriba, ya no reparte nada: cae entero en ese consultorio).
Ejemplo textual de la clienta, usado tal cual en los tests: "si pago
publicidad para todo el espacio, manejo dos localidades, una con un
edificio y una unidad, y la otra con 3 edificios y 8 unidades, la
incidencia en el negocio a nivel ingresos es mayor en la segunda
localidad, y el gasto lo estoy repartiendo en formas iguales entre las
dos" — aceptado explícitamente como desproporcionado frente a la
incidencia real de cada rama en los ingresos: "no importa, se entiende
que cuando se estima algo es muy difícil que todo sea exacto... no
termina siendo relevante" perseguir un reparto proporcional de verdad.

Esto REEMPLAZA por completo el criterio viejo documentado en el
docstring de `app.negocio.balance` ("cuando se elige cualquier filtro
puntual los gastos Espacio general quedan afuera del Resultado de ese
lugar, por no ser atribuibles a un lugar puntual") — ese criterio era
un parche para el mismo problema que el prorrateo en cascada resuelve
de raíz, así que deja de hacer falta excluir nada: ahora cualquier gasto
de un nivel superior SÍ entra en el Resultado de un filtro puntual, con
la porción que le corresponde en la cascada (que puede coincidir con el
100% si ese filtro es la única rama que existe en el sistema).

`_distribuir_gasto_por_consultorio` (`app.negocio.balance`, nueva)
calcula, para un gasto puntual, el monto que le llega a CADA Consultorio
alcanzado por su cascada — recorriendo Localidad→Edificio→Unidad→
Consultorio con tres helpers chicos (`_edificios_de_localidad`/
`_unidades_de_edificio`/`_consultorios_de_unidad`) y dividiendo por la
cantidad de hijos en cada escalón. `_localidades_con_algun_edificio`
resuelve qué "localidades que haya" entran en el primer reparto: cada
`IdLocalidad` con al menos un Edificio (vía `SELECT DISTINCT IdLocalidad
FROM Edificio`, que ya deja afuera sola a cualquier Localidad sin
ningún Edificio cargado) más el bucket "Sin localidad" (`None`) si hay
algún Edificio sin localidad asignada — dividir por una Localidad vacía
no tendría a ningún Consultorio al que llegarle la porción.

`total_gastos_periodo` reemplaza a `_alcance_gastos_del_filtro` (se
borra, sin otro consumidor): sin ningún filtro (alcance "Todos"/todo el
espacio) sigue sumando los montos directo, sin prorratear nada — evita
perder centavos por una rama incompleta y mantiene "Todos" como la
fuente de verdad del gasto total del período. Con cualquier filtro
puntual, resuelve `ids_consultorio` con el mismo `_ids_consultorio_del_
alcance` que ya usa Ingresos (mismo "el más específico manda") y suma,
para cada gasto, la porción de su reparto en cascada que cae dentro de
ese conjunto de consultorios.

**Una rama sin hijos en algún escalón no reparte nada de esa porción a
ningún Consultorio** (ej. un Edificio cargado sin ninguna Unidad
todavía) — se pierde, mismo criterio de imprecisión aceptada que el
resto del modelo, y consistente con que esa rama tampoco puede generar
ningún Ingreso (sin Unidad no hay Consultorio reservable). Esto solo
afecta al prorrateo bajo un filtro puntual: la suma sin filtro de
"Todos" nunca se ve afectada, porque no prorratea nada.

Tests nuevos/reescritos en `tests/test_balance.py`: alcance Consultorio
cuenta entero solo en ese consultorio; Unidad se reparte en partes
iguales entre sus consultorios; Edificio se reparte primero por Unidad y
de ahí por Consultorio (con un ejemplo de reparto desigual entre dos
Unidades con distinta cantidad de consultorios, para dejar claro que NO
es proporcional al total); Espacio general se reparte en cascada
completa por Localidad (reproduce el ejemplo textual de la clienta, dos
localidades con distinta cantidad de edificios terminan absorbiendo la
misma porción); una rama sin hijos no reparte nada; sin filtro se sigue
sumando todo. `tests/test_gui_balance.py`
(`test_resultado_prorratea_gastos_generales_al_filtrar_por_consultorio`,
reemplaza al viejo test de "excluye generales" con dos edificios para
que la porción prorateada sea visible y no un simple 0/100%).


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
  "Editar registro" de "Historial" de Control de pagos) — Eliminar NO
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

## Gastos: tabla ordenable por click en el encabezado + F5 + otro 25% de ancho

Dos pedidos puntuales más sobre "Gastos" (`_PanelGastos`, `app/gui/
pantallas/balance.py`), ronda siguiente a la de más arriba (que
compartió además un segundo bug real de Panel de control, ver
`docs/historial/sistema.md`):

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

Tests: `tests/test_gui_balance.py` (+2: `test_gastos_tabla_ordenable_
por_click_en_encabezado`, `test_gastos_f5_tambien_reinicia_el_orden`;
reescrito el test de ancho a la cascada ×1.3×1.25). Suite: 38 passed,
más 168 passed en la corrida conjunta con `test_balance.py`/`test_
gastos_operativos.py`/`test_gui_panel_control.py`. pyflakes limpio en
`app/gui/pantallas/balance.py` y el archivo de test tocado.

## Ingresos: columnas rediseñadas (parte del rediseño grande de Panel de control)

El rediseño completo de "Estadísticas principales mes en curso" de
Panel de control (ver `docs/historial/sistema.md` para la ronda
completa, con las cuatro preguntas de aclaración y la lógica de
negocio nueva en `panel_control.py`/`balance.py`) trajo, como
consecuencia directa en esta pantalla, un cambio de columnas en
"Ingresos" (`_PanelIngresos`, `app/gui/pantallas/balance.py`):
`_COLUMNAS_INGRESOS` pasa de 5 columnas a 4 (`"Período"`, `"Monto
total liquidado"`, `"Ingresos por fuera de las liquidaciones"`,
`"Total ingresos"` — se elimina la columna de feriados y días
especiales, ya absorbida dentro de "Monto total liquidado"); `_fila`/
`_llenar_filas` desempaquetan la tupla nueva de 2 valores de
`total_ingresos_periodo` (`app.negocio.balance`) en vez de la de 3 que
tenía antes. "Resultado" no cambia de columnas, solo hereda el "Total
ingresos" nuevo. "Monto total liquidado" pasó a NO filtrarse más por
ubicación (decisión de la clienta, Q1 de esa ronda: una liquidación es
por PROFESIONAL, no se puede partir prolijamente por Consultorio).

Test: `tests/test_gui_balance.py` (`test_ingresos_recalcula_al_
cambiar_periodo`, reescrito con `emitir_liquidacion` real en vez de
calcular en vivo desde reservas sueltas).
