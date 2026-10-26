# Historial archivado — Catálogos genéricos (PantallaCRUD): Mensajes predefinidos, Gastos operativos, Fechas especiales, Listas editables, Condiciones y normas, Detalles complementarios, Localidad, Consultorios, Importar planilla, Bloques rígidos

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

## Gastos operativos (Categoría abierta, Alcance excluyente)

Categoría pasa a combo abierto (mismo criterio que Responsable.Rol y la
Categoría de Mensajes predefinidos): sugiere los valores de Listas
editables (`TipoLista="CategoriaGasto"`) pero admite tipear uno nuevo
ahí mismo.

Alcance (Espacio general/Edificio/Unidad, sección 3.25) es excluyente:
un gasto está asociado a UNO solo de los tres niveles, nunca a más de
uno a la vez. `catalogos._al_abrir_dialogo_gasto` conecta el combo
Alcance para que, al cambiarlo, el campo del nivel que no corresponde
quede deshabilitado y se limpie (Edificio/Unidad usan acá su propia
versión de las opciones con un valor en blanco al principio,
`_opciones_edificio_o_ninguno_gasto`/análoga — las de `catalogos.py` no
la tienen porque en otros catálogos esos campos son obligatorios).
Pedido explícito de la clienta: no hace falta un nivel Localidad ni
Consultorio para gastos (a diferencia de Mensajes predefinidos) — dejó
la puerta abierta a sumarlo en el futuro si hiciera falta, pero no lo
ve necesario, así que no se agregó.

La limpieza de los campos que no corresponden también vive del lado de
los datos, no solo en la reactividad del diálogo:
`app.negocio.gastos_operativos.sanear_alcance(valores)` fuerza a None
IdEdificio/IdUnidad según el Alcance, y se llama desde
`_resolver_conflicto_gasto` antes de guardar. Motivo (pedido de la
clienta): esta tabla se puede cargar tanto a mano como, a futuro,
importada desde un módulo extendido — la limpieza no puede depender
únicamente de que la carga haya pasado por este diálogo en particular.
Por el mismo motivo, un gasto Manual puede pasar a Origen "Importado"
en cualquier momento con solo editarlo — `gasto_en_conflicto` excluye al
propio registro (`id_gasto_actual`), así que cambiarle el origen a uno
mismo nunca dispara el cartel de conflicto contra sí mismo.

Filtro "Período actual" (`panel_extra_superior_izquierda`, arriba de
Nuevo/Editar/Eliminar): arranca en `app.negocio.dias.periodo_actual(conn)`
(el mes en curso, respeta la fecha ficticia de QA) pero se puede
cambiar a mano — oculta filas de otros períodos, mismo criterio que
cualquier "filtro que solo afecta la visualización". Debajo de los
botones (`panel_extra_izquierda`, con su línea divisoria propia arriba,
pedido explícito de la clienta) va el título "Subtotal gastos período
{MM-AAAA}" (`_titulo_subtotal_periodo` — el período se guarda AAAA-MM
pero se muestra invertido acá, pedido de la clienta) seguido de la suma
de Monto de todos los gastos de ese período (no solo los visibles
después de "Buscar", que es un filtro aparte) — título y monto se
recalculan cada vez que cambia el período o se crea/edita/elimina un
gasto.

Edificio/Unidad de este catálogo: la opción en blanco (cuando el
Alcance no es ese nivel) dice "Sin relación a edificio específico"/"Sin
relación a unidad específica" (pedido de la clienta, más explícito que
"Sin edificio"/"Sin unidad").

Cadena de foco (Enter/Tab, ver `app.gui.widgets.foco`) propia de esta
pantalla: Buscar → Período actual → Nuevo → Editar → Eliminar → vuelve a
Buscar. Como "Período actual" no es uno de los widgets que
`PantallaCRUD` conoce, esta pantalla se construye con
`instalar_foco=False` (mismo criterio que Llaves: "apagalo cuando una
pantalla arma su propia cadena que combina estos tres botones con los
suyos") y arma la suya propia con `instalar_enter_avanza_foco` pisando
`pantalla._foco`, incluyendo el campo de período en el lugar que le
corresponde.

## Fechas especiales (Fecha con selector de calendario)

Al revisar este catálogo, el campo Fecha pasó de texto libre validado
contra AAAA-MM-DD a un selector de calendario real, con el mismo formato
"día de la semana abreviado" que Registro de ausencias (ej.
"lun 07-09-2026") — pedido de la clienta para que se vea igual en toda
la pantalla, listado incluido. Esto generalizó ese formato desde
`novedades.py` a `crud_generico.py` como `Campo(tipo="fecha")` (ver
"Selectores y fecha" más arriba): cualquier catálogo genérico puede
sumarlo de la misma forma, aunque por ahora solo lo usa esta pantalla —
el resto de los campos de fecha en texto libre de otros catálogos sigue
como estaba hasta que se revisen. La tabla sigue guardando AAAA-MM-DD
en la base (ningún PDF ni cálculo de negocio se tocó); el orden por
click en el encabezado ordena por ese valor real, no por el texto con
el día de la semana (ese orden alfabético no coincide con el
cronológico).

Suma también los tres campos libres, como el resto de los catálogos
revisados desde Consultorios en adelante.

## Listas editables (agregar valores, no tipos)

Pedido de la clienta al revisar este catálogo: "Tipo de lista" pasó de
texto libre a un combo cerrado (`catalogos._opciones_tipo_lista`, sin
`combo_editable`) con los tipos que ya existen en la tabla (`SELECT
DISTINCT TipoLista`) — esta pantalla es para sumar valores a una lista
que algún otro formulario ya lee por `opciones_lista(tipo_lista)`
(CondicionFiscal, MedioPago, CuentaReceptora, TipoFechaEspecial, etc.),
no para inventar un tipo nuevo que ningún combo del sistema vaya a leer.
Si hace falta un tipo realmente nuevo, hoy no hay forma de darlo de alta
desde la GUI (habría que cargar la primera fila por código/migración).

Orden es una posición, no un número suelto (pedido de la clienta:
"arrastrar y soltar", no que convivan huecos o dos filas con el mismo
número). `app.negocio.listas_editables.reordenar_al_guardar`, enganchado
como hook `al_guardar` de `PantallaCRUD`, corre a las demás filas del
mismo TipoLista para dejar libre el Orden elegido (clampeado a un rango
válido) cada vez que se guarda un alta o una edición — nunca hay que
tocarlas a mano. Dejar el campo Orden vacío en un alta manda el ítem al
final de su lista. Si una edición además cambia el TipoLista de una fila
existente, primero cierra el hueco que deja en la lista de la que sale
(`_renumerar`) antes de ubicarla en la nueva.

**Campos libres sumados después, como repaso aparte**: era el único de
los 14 catálogos sobre `PantallaCRUD` que todavía no sumaba los tres
(`*campos_libres(conn)`) — un hueco real, no una exclusión a propósito
(la clienta no le vio sentido práctico al pedirlo, pero prefirió
sumarlo igual para que la regla quede pareja en todos los catálogos).
Mismo mecanismo de siempre: `CampoLibre1/2/3` en `schema.sql` +
`_COLUMNAS_NUEVAS` (`migraciones.py`) para bases ya creadas. No tiene
plantilla de importación Excel (no está en `COLUMNAS_PLANTILLA`), así
que no hizo falta tocar nada de `app.importacion`.

## Condiciones y normas / Detalles complementarios (posición que se reacomoda sola)

Mismo criterio que el Orden de Listas editables (pedido de la clienta al
revisar Condiciones y normas, aplicado después también a Detalles
complementarios): el campo de posición (`CondicionNorma.Numero` — el
orden en que `app.pdf.valores_pdf` los imprime — y
`DetalleComplementarioPropuesta.Orden`, para el PDF de Propuesta) es un
lugar dentro de toda la lista, 1-based, no un número suelto. A
diferencia de Listas editables acá no hay un TipoLista que agrupe — el
reacomodo es sobre toda la tabla — así que ambos catálogos comparten un
mismo helper genérico, `app.negocio.posicion.reordenar_posicion_al_guardar`
(parametrizado por tabla/clave primaria/columna de posición), en vez de
duplicar el algoritmo: `app.negocio.condiciones_normas.reordenar_al_guardar`
y `app.negocio.detalles_complementarios.reordenar_al_guardar` son
wrappers de una línea sobre ese helper, enganchados como hook
`al_guardar` de `PantallaCRUD`. Corre a las demás filas para dejar libre
la posición elegida (clampeada entre 1 y "última posición + 1") cada vez
que se guarda un alta o una edición; dejar el campo vacío en un alta
manda el ítem al final de la lista.

## Localidad (catálogo propio, con ID estable)

Pedido de la clienta al revisar Imágenes: `Edificio.DomicilioLocalidad`
pasó de texto libre a una referencia (`Edificio.IdLocalidad`) a un
catálogo propio `Localidad` (campos Localidad, Partido, Provincia, País
+ los tres campos libres de siempre) — le da a cada localidad un ID
estable, necesario para las rutas de archivos por localidad (ver
Imágenes abajo) y para que un futuro armado de PDF por localidad pueda
buscar, por ejemplo, un logo propio de esa localidad ("LogoPDF_
{IdLocalidad}.jpg"). Partido/Provincia/País son datos de referencia
nomás — hoy el sistema no filtra ni agrupa por ellos, solo por Localidad.

El catálogo se edita desde `pantalla_localidades` (formato estándar,
igual al resto) y el Edificio lo referencia con un combo (`Campo(
"IdLocalidad", "Localidad", tipo="combo", opciones=_opciones_localidad)`)
en vez de un campo de texto — para cargar una localidad nueva hay que
darla de alta primero en su propio catálogo. La migración de bases
viejas (`app.db.migraciones._migrar_localidad_texto_a_tabla`) crea (o
reusa) una fila de Localidad por cada texto distinto que ya estaba
cargado en Edificio.DomicilioLocalidad (e Imagen.Localidad, ver abajo)
antes de sacar esas columnas de texto.

Todas las pantallas/PDFs que antes agrupaban o filtraban por el texto de
Edificio.DomicilioLocalidad (Aumentos, Lista de espera, Oferta de
consultorios, Placas, Reservas, Grilla operativa/Vista rápida, Llaves,
Mensajes, Propuesta/Disponibilidad/Liquidación) ahora lo hacen por
`Edificio.IdLocalidad`, resolviendo el texto a mostrar con un
`LEFT JOIN Localidad` aliased de vuelta a `DomicilioLocalidad` en la
consulta (así el código que ya leía esa clave de la fila no necesitó
tocarse) — solo cambiaron las consultas SQL, no los `dict`/`Row` que
consume cada pantalla.

## Bloques rígidos (formato solapa a mano, no PantallaCRUD)

Pasó del layout plano (título + fila de botones sin estilo arriba de la
tabla) al mismo lenguaje visual que los catálogos genéricos (solapa
única, `panelSolapa`/`QScrollArea` con `setDrawBase(False)`/`NoFrame`,
columna izquierda de ancho fijo con Buscar + Nuevo/Editar/Eliminar,
tabla ordenable a la derecha) — pero SIN construirse sobre
`PantallaCRUD`, a diferencia del resto de los catálogos: el diálogo
Nuevo/Editar necesita dos listas de días con checks (`_ListaDias`, una
para la restricción lógica y otra para la visualización en la grilla),
un tipo de control que `crud_generico.Campo` no contempla
(`tipo="texto"|"texto_largo"|"numero"|"booleano"|"combo"|"fecha"`).
Sumar un tipo nuevo ahí serviría a esta única pantalla, así que se
armó a mano en su lugar — mismo criterio ya documentado para Gestor de
archivos ("sigue el mismo lenguaje visual que los catálogos... pero NO
usa `PantallaCRUD`"). El diálogo en sí no cambió de contenido, solo de
formato de horario (ver abajo); Buscar filtra sin distinguir mayúsculas
ni acentos por cualquier columna visible, mismo criterio que "Filtros
que solo afectan la visualización" (reusa `_normalizar_busqueda` de
`crud_generico`, import cruzado de un símbolo privado — mismo criterio
que otros imports cruzados del sistema).

Editar/Eliminar pasan a `botonSecundario` (antes sin estilo), Nuevo
sigue en `botonPrimario`, los tres al mismo ancho fijo que Buscar. La
columna "Horario" de la tabla y los dos `QDoubleSpinBox` de Hora
inicio/fin del diálogo pasan de un decimal con coma ("18,5") a formato
horario con sufijo ("18:00hs a 21:00hs", `_SpinHora`/`_fmt_hora` —
mismo criterio que Configuración general/Oferta/Reservas/Lista de
espera, duplicado acá porque son pantallas sin relación entre sí). La
tabla también suma orden por click en el encabezado (`OrdenTabla`,
mismo criterio que el resto de las tablas del sistema) y una cadena de
foco Enter/Tab explícita (Buscar → Nuevo → Editar → Eliminar, con
`showEvent` enfocando Buscar al entrar a la pantalla) — ninguna de las
dos cosas existía antes de esta revisión. Se sacó de paso una quinta
columna sin usar en la tabla (`""`, encabezado vacío que `actualizar()`
nunca llenaba — resabio sin efecto visible, no un bug reportado).

Segunda vuelta: las columnas de la tabla suman `_PADDING_COLUMNA` (30px,
mismo criterio y mismo valor que `novedades._ajustar_columnas`) sobre lo
que deja `resizeColumnsToContents()` — quedaban apretadas, sobraba ancho
en el panel.

Tercera vuelta: el título de la solapa pasa de "Listado" (el genérico
que usan los catálogos) a "Bloques rígidos" — mismo criterio que Panel
de control: a futuro esta pantalla va a terminar viviendo dentro de
otro formulario todavía sin definir, así que necesita su propio nombre
en vez del genérico de catálogo. No se tocó nada de la estructura
pensando en eso, es solo un aviso para cuando se defina.

## Importar planilla (botones a la izquierda, planilla modelo descargable)

Mismo pasaje de layout que el resto de las pantallas de esta revisión:
de una fila horizontal de controles arriba de los cuadros de resultado,
a formato solapa (única pestaña "Importación") con una columna
izquierda de ancho fijo (`_ANCHO_BOTON = 260`, calculado para que entre
"Descargar planilla importación" sin cortarse) y los tres cuadros de
resultado (tabla por hoja, errores, informe de integridad) a la
derecha. "Importar" es `botonPrimario` (es la única de las tres
acciones que efectivamente escribe algo en la base); "Elegir archivo"
y "Descargar planilla importación" quedan en `botonSecundario`.

"Descargar planilla importación" es la primera vez que
`app.importacion.plantillas.generar_plantillas` se cuelga de la GUI:
antes solo estaba disponible por línea de comandos (`main.py
generar-plantillas`). Abre un selector nativo "Guardar como"
(`QFileDialog.getSaveFileName`, sugiere
"Plantilla_Importacion_EspacioRamos.xlsx") y genera ahí el mismo libro
Excel con la hoja de instrucciones y una hoja por entidad importable —
mismo criterio de "Descargar" que Gestor de archivos (copia hacia
afuera, no toca nada de lo que ya está cargado en el sistema).

Orden final de la columna izquierda (pedido explícito de la clienta en
una segunda vuelta, invirtiendo el orden de la primera): "Descargar
planilla importación" primero, después "Elegir archivo..." con el
archivo elegido mostrado debajo (`self.campo_ruta`, sigue siendo un
`QLineEdit` de solo lectura — no cambió de tipo, solo de posición, para
no romper los tests que lo cargan directo con `.setText()` salteando
el selector de archivo) y por último "Importar". La cadena de foco
Enter/Tab sigue ese mismo orden (Descargar planilla importación →
Elegir archivo → Importar, con `showEvent` enfocando el primero al
entrar a la pantalla) — la posición en la columna manda sobre cuál es
primario/secundario, son dos decisiones independientes.

Las columnas de "Resultado por hoja" (Hoja/Filas importadas/Errores)
pasaron del padding fijo (30px sobre `resizeColumnsToContents()`, que
en un cuadro angosto de tres columnas cortas dejaba espacio en blanco
sin usar a la derecha) a `QHeaderView.ResizeMode.Stretch` — mismo
criterio que Placas: pocas columnas, todas de importancia pareja, se
reparten todo el ancho disponible del cuadro en vez de ajustarse al
contenido.

## Consultorios: tamaño del escritorio (Largo/Ancho del mueble)

Pedido puntual de la clienta: poder cargar el tamaño del escritorio de
cada consultorio — distinto del `Largo`/`Ancho` que ya tenía el
consultorio, que son del AMBIENTE (la habitación), no del mueble.
Antes de implementar se consultaron dos decisiones (`AskUserQuestion`):

- **Tipo de dato**: medidas en metros (`LargoEscritorio`/
  `AnchoEscritorio`, dos `REAL`), mismo criterio que el `Largo`/`Ancho`
  del ambiente — no una clasificación cerrada tipo Grande/Chico ni texto
  libre.
- **Alcance**: puramente informativo por ahora — se carga y se ve en el
  catálogo de Consultorios (`Campo("LargoEscritorio", "Largo escritorio
  (m)", tipo="numero")`/análogo para Ancho, entre `Ancho` y
  `TamanoClasificacion` en `catalogos.pantalla_consultorios`), sin sumar
  ningún filtro nuevo a Oferta de consultorios (que si sigue filtrando
  solo por `TamanoClasificacion`, el tamaño del AMBIENTE) ni a ninguna
  otra pantalla — no se tocó ningún PDF (Propuesta/Disponibilidad) ni el
  detalle de Oferta. Si más adelante hace falta mostrarlo en algún otro
  lado, es un pedido aparte.

También se sumaron a `app.importacion.definiciones.COLUMNAS_PLANTILLA
["Consultorio"]` (entre `Ancho` y `TamanoClasificacion`, mismo orden que
en el catálogo) — la importación resuelve las columnas por el NOMBRE del
encabezado de la planilla real, no por posición fija, así que insertar
estas dos en el medio de la lista no rompe ninguna planilla ya
descargada antes de este cambio (sigue funcionando por el texto del
encabezado que traiga esa planilla puntual).


## Feriados y fechas especiales: limpieza automática, descripción y orden en el PDF, cartel de regeneración

Hilo nuevo, a partir de probar el arreglo de arriba (Pagos/PDF): la
clienta confirmó que, con ese cambio, eliminar/agregar un feriado del
mes en curso ya regenera de verdad TODAS las liquidaciones ya emitidas
de ese período (antes de ese cambio, `regenerar_si_corresponde` solo
tocaba el estado en la base, nunca el PDF — el mismo bug, visto desde
el lado de Fechas especiales en vez de Pagos). Cuatro pedidos nuevos
sobre esta misma pantalla:

### 1. Avance de mes: limpiar los feriados que ya no tienen efecto

"Cuando hizo el avance de mes de octubre a noviembre, me conservó en
la lista el feriado que tenía del 12-10, eso me lo tendría que haber
limpiado de la tabla ya que no tiene más efecto en las nuevas
liquidaciones." Confirmado por código antes de tocar nada: un feriado
del período que se cierra deja de poder afectar cualquier liquidación
nueva por DOS motivos, no uno — (a) DC-08 §6.2 ya bloquea reemitir un
período una vez que hay liquidaciones de períodos posteriores, así que
su propio cálculo nunca se vuelve a correr; (b) el único lugar donde
seguía pesando como "feriado pendiente" del período siguiente
(`liquidaciones._calcular_feriados_pendientes`) filtra contra la fecha
de emisión YA FIJADA del período que se cierra
(`feriado['Fecha'] <= fecha_emision_ant`, un valor que no cambia más),
así que si el feriado ya existía antes de esa emisión (el caso normal)
ya estaba excluido de "pendientes" para siempre, sin importar cuándo se
borre.

`avance_mes._limpiar_fechas_especiales_antiguas(conn, periodo_cerrado)`
(nueva, mismo patrón que `_limpiar_liquidaciones_antiguas_todos`/
`_limpiar_lista_espera`) borra toda fila de `FechasEspeciales` con
`Fecha` dentro del período que se cierra O anterior (por si quedó
alguna de una ronda vieja sin limpiar) — se llama en `avanzar_mes`
junto al resto de las limpiezas de fin de mes, nuevo campo
`ResumenAvanceMes.fechas_especiales_antiguas_eliminadas` sumado al
cartel final de "Avance de mes completado" (`panel_control.py`), mismo
criterio que los otros contadores de esa pantalla.

### 2. Descripción cargada, agregada al ítem del PDF

"En los items de feriados que aparecen en las liquidaciones agregame
la descripción que tiene cargada... en lugar de 'Descuento por feriado
- lunes 9/11' que diga 'Descuento por feriado - lunes 9/11 - Visita
Papal'." `ItemFeriado` (`app.negocio.liquidaciones`) suma un campo
`descripcion: str | None`, poblado con `feriado["Descripcion"]` en los
tres lugares donde se construye (`_calcular_descuentos_feriados` para
nacionales/no laborables, `_calcular_feriados_pendientes`).
`liquidacion_pdf._sufijo_descripcion` (" - {descripcion}", o "" si no
hay ninguna cargada) se agrega al final de los tres textos que ya
armaba `_items_cuenta` ("Descuento por feriado...", "...día no
laborable...", "...feriado (mes anterior)...") — sin tocar la
redacción existente cuando no hay descripción.

### 3. Orden en el PDF: más próximo arriba, más alejado abajo

"Que aparezcan en el PDF ordenados de más próximo arriba a más
alejados en el tiempo abajo, más allá de la posición en el que fueron
cargados en la tabla." Las tres listas (`descuentos_feriados`,
`descuentos_no_laborables`, `feriados_pendientes`) se ordenan por
`fecha` descendente al armarlas en `liquidaciones.py` (no en el PDF:
es la única parte del sistema que las consume, así que ordenar en el
origen alcanza) — el feriado más reciente del período queda arriba,
el más viejo abajo, sin importar el orden de carga en Fechas
especiales.

### 4. Cartel final de "proceso completado" al regenerar

"Asegurate que siempre salga un alerta que... va a regenerar todos los
archivos y marcarlos como no enviados, siempre con el ok final de
proceso completado cuando termine." Para crear/editar ya existía el
aviso ANTES de guardar (`_al_guardar_fecha_especial`, "Hay N
liquidación(es)... ¿Confirmás?"); lo que faltaba era un cartel
explícito DESPUÉS, sobre todo para Eliminar (no se puede avisar antes
de borrar — el genérico "¿Confirmás eliminar?" de `PantallaCRUD` ya
sirve de confirmación de la acción en sí). `_regenerar_liquidaciones_
del_periodo_actual` (`catalogos.py`) ahora, si de verdad regeneró algo,
muestra `QMessageBox.information` con la cantidad real y el período —
mismo criterio exacto que ya usan Aumentos/Esquema de descuentos para
su "cartel de éxito" (cuenta real, después de regenerar). Queda un
cartel de más en la secuencia (el genérico "Registro eliminado con
éxito" de `PantallaCRUD` sigue saliendo después) — aceptado como costo
menor frente a que SIEMPRE quede explícito que se regeneró algo. Este
patrón de "cartel final explícito cuando se regenera" queda disponible
para sumarse a otras pantallas con el mismo mecanismo (Aumentos y
Esquema de descuentos ya lo tenían de antes) caso por caso, no es un
barrido de una sola vez.

Tests nuevos: `tests/test_avance_mes.py` (limpia el período cerrado y
anteriores, conserva fechas futuras, cuenta 0 sin nada que limpiar),
`tests/test_pdf_liquidacion.py` (la descripción se agrega al ítem, sin
descripción no agrega guion de más, orden descendente por fecha tanto
en `Liquidacion.descuentos_feriados` como en los ítems del PDF),
`tests/test_catalogos.py` (el cartel de regeneración aparece con la
cantidad y el período correctos al eliminar, no aparece si no hay nada
que regenerar).
