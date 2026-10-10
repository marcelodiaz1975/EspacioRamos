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

Se evaluó centralizar la documentación de Profesionales en el Gestor de
archivos (agregando una segunda solapa "Archivos de los profesionales")
pero la clienta pidió dejarla como estaba, solo mejorando el nombrado:
"Agregar archivo" ahora abre `_DialogoCategoriaDocumento` (lista cerrada
`app.negocio.documentacion_profesional.
CATEGORIAS_DOCUMENTACION_PROFESIONAL` — DNI completo/frente/dorso,
Título, Curso, Capacitación, Seguro mala praxis, Matrícula nacional/
provincial, más las dos categorías libres "Otras imágenes"/"Otros
documentos", compartidas por nombre con las de Gestor de archivos) y el
archivo se guarda con el nombre de esa categoría (o "{categoría} -
{detalle}" para las dos libres) en vez del nombre original — sigue
siendo pura gestión de archivos en carpeta, sin fila propia en la base,
sin concepto de "principal" ni de orden: es deliberadamente más simple
que Gestor de archivos.

El título del campo Buscar es "Buscar" por default, pero se puede
personalizar por catálogo con `etiqueta_buscar` (ej. Profesionales:
"Buscar profesional") sin cambiar el criterio de filtrado en sí (sigue
siendo substring por cualquier columna visible, no restringido a
campos puntuales). En Profesionales además el orden de columnas
arranca con Código/Tratamiento/Nombre/Apellido (el mismo orden que el
formato canónico "{código} - {tratamiento} {nombre} {apellido}" de los
selectores de profesional del resto del sistema) — pedido puntual de
esa pantalla, cada catálogo define el orden de sus propias columnas
según lo que tenga más sentido mostrar primero, no hay una regla única.

## Mensajes predefinidos (ya en formato estándar, con dos paneles propios)

Pasó de `compacto=True` (filtro de categoría en una fila propia arriba
de la tabla) al formato solapa estándar al revisar esta pantalla, con
todo lo propio agrupado en un solo `panel_extra_superior_izquierda`
(arriba de Nuevo/Editar/Eliminar, sin línea divisoria entre secciones —
se probó una entre Categoría y Dirigido a y la clienta la sacó), de
arriba abajo: "Categoría" (combo, filtro que solo afecta la
visualización, oculta filas igual que antes), "Dirigido a" + los cuatro
selectores de contexto Localidad/Edificio/Unidad/Consultorio (ver abajo)
y el botón "Copiar mensaje" — pedido explícito de la clienta sobre el
orden ("Copiar mensaje" arriba de "Nuevo", "Dirigido a" arriba de
"Copiar mensaje", y los cuatro selectores de contexto después de
"Dirigido a"). "Copiar mensaje" es `botonPrimario` acá (es la acción más
importante de esta pantalla), así que "Nuevo" pasa a `botonSecundario`
vía el parámetro nuevo `nuevo_secundario=True` de `PantallaCRUD` (pinta
"Nuevo" en secundario en vez de primario, para cuando otra acción del
panel es más importante que dar de alta un registro).

Categoría es un catálogo abierto (mismo criterio que Responsable.Rol):
sugiere los valores de Listas editables (`TipoLista="CategoriaMensaje"`)
pero admite tipear uno nuevo ahí mismo, sin tener que darlo de alta
primero en ese catálogo.

Localidad/Edificio/Unidad/Consultorio DEL MENSAJE (en el cuadro de
diálogo Nuevo/Editar; Localidad es campo nuevo, pedido de la clienta, va
antes que Edificio): cuatro campos independientes, sin cascada entre
ellos. Si los cuatro quedan sin seleccionar, el mensaje se entiende
general (pedido de la clienta) — "En general" es la etiqueta de ese
valor en blanco (antes "Sin edificio"/"Sin localidad"/etc., unificado a
pedido de la clienta para que coincida con la de los selectores de
contexto de abajo). Por eso Edificio/Unidad/Consultorio en esta pantalla
usan su propia versión de las opciones con ese valor en blanco al
principio (`_opciones_edificio_o_general` y análogas en
`mensajes_predefinidos.py`, no las de `catalogos.py`, que ahí son
`requerido=True` y no tienen ni necesitan esa opción).

Selectores de CONTEXTO (Dirigido a + Localidad/Edificio/Unidad/
Consultorio, debajo de "Categoría"): ninguno es parte del registro
guardado — son solo contexto para la Vista previa del mensaje
seleccionado en la tabla, todos arrancan en su valor "general" ("Nadie
en particular" / "En general") y cambiarlos nunca filtra la lista, solo
recalcula la vista previa.
- "Dirigido a": selector de profesional buscable (mismo criterio de
  siempre, `habilitar_busqueda_profesional`). Si el mensaje usa
  `{apodo}` (ej. "Hola {apodo}, mañana no hay agua"), sustituye por el
  Apodo del profesional elegido.
- Localidad/Edificio/Unidad/Consultorio de contexto: cuando alguno
  queda en "En general", la vista previa usa el valor de ESE campo tal
  cual está guardado en el mensaje; elegir algo puntual lo pisa campo
  por campo (`_actualizar_vista_previa` arma un id efectivo por campo:
  el de contexto si no es None, si no el del mensaje) antes de resolver
  `{edificio}`/`{unidad}`/`{consultorio}` con el mismo criterio de
  "el más específico gana" (`_variables_ubicacion`). Sirve para
  previsualizar, por ejemplo, un mensaje general como si fuera para un
  edificio puntual, sin tener que editar el mensaje. El de Localidad no
  tiene ninguna variable propia todavía (no existe `{localidad}`) — está
  ahí por paridad con el cuadro de diálogo.

`crud_generico.PantallaCRUD` tenía una línea tenue justo debajo de la
solapa "Listado" en TODOS los catálogos (detectado al revisar esta
pantalla, no es puntual de acá): el borde nativo del `QTabBar` más el
marco propio del `QScrollArea` de la solapa, ninguno de los dos
controlable solo con QSS. Se corrigió ahí (afecta a todos los
catálogos): `solapas.tabBar().setDrawBase(False)` +
`scroll.setFrameShape(QFrame.Shape.NoFrame)`. Las pantallas con su
propio `QTabWidget` armado a mano (Placas, Aumentos y descuentos,
Grilla operativa, Novedades, Reservas, Pagos, Gestor de archivos, Lista
de espera) no se tocaron todavía — si al revisarlas se ve el mismo
defecto, aplicarles el mismo combo ahí. Liquidación mensual ya lo tiene
(ver su sección más abajo).

Pedido explícito de la clienta (al revisar Consultorios): a partir de
ahora, TODO catálogo que se revise de acá en adelante suma tres campos
libres (`CampoLibre1/2/3`, texto opcional, sin validación) al final de
su lista de `Campo` — no solo cuando lo pide puntualmente. Ya aplicado a
Localidades, Edificios, Unidades, Consultorios, Responsables, Tipos de
licencia, Condiciones y normas, Detalles complementarios (Propuesta),
Profesiones, Gastos operativos y Fechas especiales; falta sumarlo al
resto a medida que se van revisando. Cada uno
necesita el campo en `schema.sql`, la entrada correspondiente en
`_COLUMNAS_NUEVAS` de `migraciones.py` (para las bases ya creadas) y, si
el catálogo tiene plantilla de importación Excel, las tres columnas al
final de su entrada en `COLUMNAS_PLANTILLA` (la plantilla siempre las
incluye, sin importar el parámetro de abajo — es para migrar datos, no
para uso día a día).

Cada catálogo arma esos tres campos con `app.gui.crud_generico.
campos_libres(conn)` en vez de escribir las tres líneas de `Campo(...)` a
mano — un solo lugar sirve para todos. Pedido de la clienta: agregó un
parámetro en Configuración general, "Visualizar campos libres"
(`Configuracion.VisualizarCamposLibres`, Sí por defecto), que apaga los
tres campos en TODOS los catálogos a la vez con un solo click —
`campos_libres` devuelve la lista vacía si está en "No". Como tabla y
diálogo Nuevo/Editar arman sus columnas/campos a partir de la misma
lista de `Campo` (`app/gui/crud_generico.py`), sacarlos de esa lista
alcanza para que desaparezcan de los dos lugares a la vez. Los valores
ya cargados no se borran: la columna sigue en la base, el parámetro solo
controla si se muestran y se piden. Como el alto del cuadro de diálogo
se calcula en función de `len(campos)` (`_DialogoRegistro.__init__`,
`60 + 40px por campo`), el diálogo también se achica o se agranda solo,
sin ningún ajuste extra. Se agregó también a `_campos_profesional`
(Profesionales) con el mismo mecanismo, aunque esa pantalla no forma
parte de la revisión "uno por uno" de catálogos.

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

## Gestor de archivos (administrador de archivos, no un catálogo)

`app/gui/pantallas/imagenes.py` (título "Gestor de archivos", solapa
"Archivos del espacio" — hoy es la única; una eventual "Archivos de los
profesionales" quedó descartada, ver más abajo el criterio que se siguió
para la documentación de Profesionales en su lugar) sigue el mismo
lenguaje visual que los catálogos (filtros a la izquierda, tabla
escroleable a la derecha, botones debajo de los filtros, con más ancho
que el `resizeColumnsToContents` justo — mismo criterio que `novedades.
_ajustar_columnas`, con la columna Descripción todavía más generosa)
pero NO usa `PantallaCRUD`: no hay un cuadro de diálogo con campos de un
registro, es un administrador de archivos por alcance. Por lo mismo no
lleva los tres campos libres — no es un registro de catálogo. La tabla
tiene el ancho justo de sus columnas (sin stretch); el panel de vista
previa a la derecha es el que se estira y come el resto del ancho
disponible, para que no quede un espacio en blanco entre el final de la
tabla y el panel — pedido puntual de la clienta al revisar esta pantalla.

Tipo de archivo: además de imágenes (JPG/PNG) se pueden cargar
documentos (PDF/Word/TXT) — combo "Tipo de archivo" justo debajo de
Alcance (Imagen/Documento), que filtra la tabla y decide con qué
extensiones se abre el selector de archivo y qué lista de categorías se
ofrece al agregar. La distinción es pura extensión (`app.negocio.
imagenes.es_imagen`/`es_documento`), no hay columna propia en la base.
Vista previa: imágenes con QPixmap directo, PDF renderizando la primera
página con PyMuPDF (dependencia opcional en tiempo de ejecución — si no
está instalado cae al mensaje de "sin vista", no rompe la pantalla), TXT
mostrando las primeras líneas como texto. Word no tiene vista previa
todavía — mismo cartel "No hay vista disponible" que cualquier archivo
que no se pudo leer.

El alcance (`app.negocio.imagenes.ALCANCES`) tiene 5 niveles: "Espacio"
(imágenes generales del sistema, sin atarse a ningún edificio — logos,
flyers, banners), "Localidad" (referencia el catálogo `Localidad` de
arriba — mismo criterio de ID estable que el resto), "Edificio",
"Unidad" y "Consultorio". El combo Alcance define hasta qué nivel de la
cadena Localidad → Edificio → Unidad → Consultorio hace falta elegir un
valor concreto: los combos de nivel superior al elegido quedan
deshabilitados (si Alcance = "Espacio" los cuatro quedan grises; si
Alcance = "Unidad" se puede setear Localidad/Edificio/Unidad pero no
Consultorio). El valor que efectivamente determina qué imágenes se
listan/agregan es el del combo en el nivel EXACTO del alcance elegido —
los de niveles inferiores solo acotan en cascada las opciones de ese
combo (mismo criterio de cascada que Aumentos y descuentos). El combo
Localidad lista el catálogo completo (no solo las localidades que ya
tienen algún Edificio cargado).

El combo Alcance tiene además, como primera opción, "Todos los
archivos": lista TODAS las imágenes del sistema sin filtrar (Espacio,
todas las Localidades, todos los Edificios/Unidades/Consultorios
juntos), ordenadas por nivel (Espacio, Localidad, Edificio, Unidad,
Consultorio, en ese orden) y después por Descripción —
`app.negocio.imagenes.imagenes_todas`, con columnas propias (Alcance,
Localidad, Edificio, Unidad, Consultorio, además de Descripción/
Categoría/Principal/Activo) para poder distinguir cada fila. En este
modo los filtros en cascada y los botones Agregar/Subir/Bajar/Marcar
como principal quedan deshabilitados — no tiene sentido agregar o
reordenar sin haber elegido un alcance puntual; Eliminar/Activar-
Desactivar/Descargar siguen funcionando sobre la fila seleccionada.

Categoría y principal (pedido de la clienta al revisar esta pantalla):
cada alcance tiene, para cada tipo (Imagen/Documento), su propia lista
cerrada de categorías (`app.negocio.imagenes.
CATEGORIAS_IMAGEN_POR_ALCANCE`/`CATEGORIAS_DOCUMENTO_POR_ALCANCE`, ej.
Edificio-Imagen: "Fachada", "Ascensor"...; Unidad-Documento: "Planos de
instalación", "Habilitación"...; Espacio-Documento: "Manual del
usuario"...) que se elige en el cuadro "Agregar archivo"
(`_DialogoAgregarArchivo`) junto con un check "Marcar como principal".
Las categorías "Otras imágenes"/"Otros documentos" (siempre las últimas
de su lista, una por tipo) no tienen nombre propio: piden además un
detalle libre (`Imagen.EtiquetaLibre`) que se suma a la Descripción y al
nombre de archivo para poder identificarlas — el resto de las
categorías arma la Descripción sola, sin pedir nada más.

Dentro de cada (alcance, entidad, categoría) puede haber varios archivos
cargados, pero solo uno es el "principal" (`NumeroOrden = 1`): los demás
quedan de respaldo. Para promover uno ya cargado sin volver a subirlo
está el botón "Marcar como principal" en la lista (intercambia el orden
con el que era principal, que no se borra, solo pasa a ser uno más —
`app.negocio.imagenes.marcar_principal`). La Descripción y el nombre del
archivo en disco se arman solos como "{Alcance} - {Categoría} [-
{detalle}] - {Orden}" (`_descripcion_automatica`) y se recalculan/
renombran solos cada vez que el orden cambia (Subir/Bajar, Marcar como
principal) — pasando los archivos por un nombre temporal primero para
que un intercambio 1↔2 no pise el nombre del otro antes de liberarlo
(`_intercambiar_orden`).

`app.negocio.imagenes.obtener_principal(conn, categoria, ...)`: para
cuando algún PDF necesite buscar, por ejemplo, el logo — devuelve la
imagen principal de esa categoría en el nivel más específico indicado;
si es alcance Localidad y esa localidad no tiene ninguna marcada ahí,
cae al alcance Espacio (el logo general pisa por defecto, pero una
localidad con su propio logo usa el suyo). Edificio/Unidad/Consultorio
no tienen ese respaldo: si no cargaste una Fachada para ese edificio
puntual, no hay ninguna.

Botón "Descargar": copia el archivo de la imagen seleccionada a donde
elija el operador (selector nativo "Guardar como") — las imágenes en sí
siguen viviendo solo dentro de la carpeta base configurada, esto es
para sacar una copia hacia afuera cuando hace falta.

En disco, cada alcance guarda sus archivos en una carpeta separada
(`app.negocio.archivos_generados.carpeta_imagenes`): `Imagenes/Espacio`
para el nivel general, `Imagenes/{Alcance}_{Id}` para el resto (Id =
el ID interno de la tabla correspondiente, Localidad incluida).

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

## Centro de mensajería (formato solapa, filtros a la izquierda)

Pasó del layout viejo (fila de filtros arriba + `QSplitter` tabla/panel de
texto) al formato solapa estándar (`panelSolapa` dentro de un
`QTabWidget` de una sola pestaña, "Listado", envuelto en `QScrollArea`
con `setDrawBase(False)`/`NoFrame` como el resto). Todo lo que antes
estaba repartido entre la fila de arriba y el panel derecho del splitter
pasó a una sola columna izquierda de ancho fijo (280px, campos y
botones — subido de 220 a pedido de la clienta, quedaba justo), con la
tabla ocupando el resto del ancho a la derecha — mismo criterio de
columna izquierda que Gastos operativos/catálogos genéricos.

Orden final de la columna izquierda (de arriba abajo, pedido explícito
de la clienta sobre dos rondas de ajuste): Filtro, Período, los dos
checks "Combinar" (debajo de Período, no de los botones), "Copiar
mensaje" (`botonPrimario` — es la acción más importante de esta
pantalla, arriba de "Actualizar"), "Actualizar", "Mensaje grupal" y
"Deshacer última acción" (los tres `botonSecundario` — "Mensaje grupal"
pasó de primario a secundario al dejar de ser la acción principal),
línea divisoria, "Vista previa" y su texto. "Copiar mensaje" quedó
lejos del texto que copia (armado antes que la Vista previa en la
columna) pero sigue operando sobre `self.texto_mensaje` igual que
siempre, así que el corrimiento es puramente visual. No se armó una
cadena de foco Enter/Tab propia (no la tenía y sigue sin tenerla), pero
sí se agregó `showEvent` con `self.combo_filtro.setFocus()` (mismo
motivo que Reservas/Liquidación: al construir el `QTabWidget` el foco
queda en la tab bar hasta que la solapa se muestra de verdad) para que
al entrar a la pantalla el foco arranque en Filtro y el Tab nativo baje
desde ahí en el orden en que están los widgets en la columna.

El check "Enviada" de la tabla (`_item_enviada`) ahora centra su
`QTableWidgetItem` con `setTextAlignment(Qt.AlignmentFlag.AlignCenter)`
— `liquidacion.py` ya tenía un comentario diciendo "mismo criterio que
el check Enviada de Centro de mensajería" para su propio check, pero
acá nunca se le había puesto ese alineado: quedó corregido para que la
frase sea cierta.

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

## Liquidación mensual (foco completo, línea de solapa)

Al revisar esta pantalla contra la regla general de foco (ver más
arriba) aparecieron dos huecos:
- "Emisión de archivos": la cadena de `instalar_enter_avanza_foco` se
  armaba con `[Período, Profesional, Estado, Calcular]` nada más —
  faltaban los tres botones "Emitir...", así que un Tab desde
  "Calcular" volvía directo a Período en vez de seguir bajando. Se
  sumaron los tres al final de la lista, en el mismo orden visual
  (Pendientes → Seleccionadas → Todas).
- "Estado de cuenta" no tenía ningún `showEvent`/foco inicial armado.
  Se agregó uno que enfoca "Profesional" al mostrarse la solapa — es el
  único control interactivo de ese panel (el campo de saldo es de solo
  lectura), así que no hace falta una cadena Enter/Tab completa, alcanza
  con el foco inicial.

De paso se sumó `self.pestanas.tabBar().setDrawBase(False)` en
`ProcesoLiquidacion` (la línea tenue debajo de la barra de solapas que
ya se había corregido en los catálogos genéricos — ver más arriba —
pero seguía pendiente acá).

"Calcular" pasa a `botonPrimario` (pedido explícito de la clienta,
distinto del candidato que se había barajado antes —
"Emitir liquidaciones pendientes"—); los tres `Emitir...` se mantienen
en `botonSecundario`. Se sacó también la línea divisoria que separaba
"Calcular" de los tres `Emitir...`: quedan los cuatro botones seguidos,
sin ningún corte visual entre ellos.

El selector de Profesional de las dos solapas ya era buscable por
código o nombre (`habilitar_busqueda_profesional`) antes de esta
revisión — ya estaba cubierto por la regla general de "Selectores y
fecha" más arriba, no hizo falta ningún cambio.

El panel de filtros de "Estado de cuenta" pasó de
`setMaximumWidth(_ANCHO_PANEL_FILTROS_ESTADO_CUENTA)` a
`setFixedWidth(...)`: con solo un máximo, el panel se achicaba al ancho
natural de sus widgets (Profesional + el campo de saldo, ninguno con
ancho propio) y quedaba angosto pese al límite de 340px — con
`setFixedWidth` ahora sí ocupa ese ancho completo.

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

## Estadísticas (dos solapas, historial guardado vs. todo en vivo)

Pasó de una sola pantalla con un formulario Año/Mes + tres tablas de
ocupación en vivo + un historial de snapshots en texto plano, a formato
solapa estándar con dos pestañas que comparten las mismas 11 columnas
pero difieren en fuente de datos y filtros — pedido explícito de la
clienta, en el mismo mensaje que definió toda la pantalla de punta a
punta. Toda la lógica de cálculo vive en `app.negocio.estadisticas`
(dataclass `FilaEstadistica` + `historial_general`/`estadisticas_varias`
+ los helpers que arman cada columna); la GUI (`app/gui/pantallas/
estadisticas.py`) solo arma filtros, llama a esas funciones y pinta la
tabla.

Columnas (las mismas en las dos solapas): Período, Porcentaje Ocupación,
Horas regulares semanales, Variación sobre período anterior, Monto por
horas regulares, Monto por horas aisladas, Monto total (no se guarda,
es `monto_regular + monto_aislada` calculado al leer), Localidades,
Edificios, Unidades, Consultorios.

Tres decisiones de la clienta a tener siempre presentes (ver también el
docstring de `app.negocio.estadisticas`):

- **Montos = "monto real facturado", NETO del descuento por volumen
  (regulares) y del recargo (aisladas) — sin ningún otro concepto de
  liquidación.** Primera vuelta: se había optado por un cálculo BRUTO
  (antes de descuentos/recargos) porque el descuento por volumen de
  horas semanales (`app.negocio.valores.obtener_porcentaje_descuento`)
  se calcula por profesional sobre TODAS sus reservas del sistema, y
  parecía no haber un criterio no inventado para repartirlo de vuelta a
  un edificio/unidad/consultorio puntual. Consultada la clienta ("me
  gustaría ver reflejado los montos reales, con descuentos aplicados"),
  se encontró que SÍ hay forma exacta, sin prorratear nada: ese
  descuento es un porcentaje PLANO (no escalonado por tramo de reserva)
  que se aplica tal cual al 100% del bruto de un profesional
  (`app.negocio.valores.calcular_valor_semanal_regular`) — como es
  plano, el mismo % rige para cualquier subconjunto de sus horas, así
  que se le puede aplicar sin inventar ningún criterio a la porción que
  cae dentro de un consultorio/edificio/unidad puntual.
  `monto_neto_regular_periodo` recorre el período día por día (mismo
  criterio que antes, a valores vigentes de cada consultorio — ver
  `app.negocio.valores.valor_regular_por_rango_dias`, acá acotado por
  consultorio en vez de por profesional) y, por cada profesional que
  reserva ese día, busca sus horas semanales totales en TODO el sistema
  (`app.negocio.valores.horas_semanales_vigentes`) para sacar el % de
  descuento una sola vez y aplicarlo a lo que le corresponde de ese día
  dentro del alcance pedido. `LiquidacionEmitida.MontoGenerado` sigue
  sin servir como fuente (total ya combinado con cargos/ajustes/etc.,
  sin desglose guardado), así que el cálculo sigue siendo en vivo, día
  por día, no una lectura directa de esa columna.

  De paso, armar `monto_neto_aislada_periodo` para que replique
  EXACTAMENTE `app.negocio.liquidaciones._aisladas_periodo` (la fuente
  real de lo que se liquida) destapó que la versión bruta anterior tenía
  un bug propio, no relacionado con el pedido de la clienta: no sumaba
  el recargo (`Configuracion.RecargoPorcentajeAisladas`, que solo aplica
  cuando la reserva lo tiene marcado con `AplicaRecargo`) ni excluía las
  reubicaciones (`EsReubicacion`, que no generan cargo — compensan una
  ausencia en vez de facturar). Quedó corregido de una junto con el
  pasaje a neto.

  Límite documentado: esto arregla el cálculo EN VIVO (`estadisticas_
  varias`, y los snapshots que se generen de acá en adelante vía
  `generar_snapshot`) pero NO recalcula los `SnapshotMensual` ya
  guardados de períodos pasados en "Historial general" — esas filas
  siguen mostrando el valor bruto con el que se generaron en su momento,
  a menos que se regeneren aparte.
- **"Horas regulares semanales" es un promedio ponderado día a día, NO
  un promedio por profesional.** Ejemplo textual de la clienta: un
  consultorio con 30hs reservadas la primera quincena de un mes de 30
  días, se liberan 10hs a mitad de mes y quedan 20hs la segunda
  quincena → el promedio del mes es 25hs (15 días a 30hs + 15 días a
  20hs, no una división por cantidad de profesionales ni de reservas).
  `horas_regulares_semanales_promedio` recorre el período día por día
  sumando el total de horas semanales vigentes ese día
  (`_horas_regulares_semanales_en_fecha`, mismo criterio que
  `app.negocio.valores.horas_semanales_vigentes` pero sin acotar por
  profesional) y divide por la cantidad de días del período.
- **Localidades/Edificios/Unidades/Consultorios son siempre el conteo
  ACTUAL**, para cualquier fila (pasada o presente): ninguna de esas
  cuatro tablas guarda de baja lógica ni fecha de alta, así que no hay
  forma de reconstruir cuántas había en un período anterior — pedido de
  la clienta sobre este punto puntual: "sería lo actual o lo último si
  se trata de un período anterior al vigente" (`conteo_entidades`).

### Solapa "Historial general"

Filtros a la izquierda: dos `QCheckBox` excluyentes "Por mes"/"Por año"
(agrupados en un `QButtonGroup` exclusivo — evita destildar el marcado
sin marcar el otro, sin necesitar lógica propia; arranca en "Por mes")
más el botón "Actualizar tabla" (`botonPrimario`, vuelve el check a "Por
mes" y reinicia el orden de la tabla — "como si se entrara al
formulario"). La info "surge de los snapshots mensuales": cada fila
sale de un `SnapshotMensual` ya generado (uno por avance de mes), más el
mes en curso, calculado en vivo porque todavía no se cerró
(`historial_general`). Los snapshots generados ANTES de esta revisión no
tienen `HorasRegularesSemanales`/`MontoHorasRegulares`/
`MontoHorasAisladas` cargados (esas columnas no existían) — esas celdas
quedan en blanco en vez de recalcularse por fuera de lo guardado, límite
aceptado y documentado, no un bug. `generar_snapshot` ya calcula y
persiste las tres columnas nuevas para los avances de mes de acá en
adelante.

"Por año" agrupa los meses de cada año con dato: Ocupación% y Horas
regulares semanales se PROMEDIAN entre esos meses, los tres montos se
SUMAN — pedido explícito de la clienta ("mixto según la columna"); los
conteos de entidades siguen siendo siempre el actual (ver arriba). La
"Variación sobre período anterior" en modo año compara contra el
promedio de horas del año anterior, mismo criterio.

### Solapa "Estadísticas varias"

Filtros a la izquierda: Desde, Hasta, Localidad, Edificio, Unidad,
Consultorio. Desde/Hasta reemplazaron a los combos separados de Año y
Mes de la primera vuelta (pedido de la clienta: "para que uno pueda
elegir un período más específico") — son dos combos de período
("AAAA-MM", poblados con `_periodo_mas_antiguo_con_datos` hasta el
período actual) que arrancan en "Todo el historial" (`None`) cada uno;
dejar los dos así trae todo el historial, elegir cualquier combinación
acota el rango (inclusive en las dos puntas). Los otros cuatro filtros
(Localidad/Edificio/Unidad/Consultorio) siguen en "Todos" por defecto,
combos independientes (no una selección tipo Alcance de Gestor de
archivos) que se acotan en cascada al elegir uno de nivel superior
(mismo criterio de cascada que Gestor de archivos: elegir una Localidad
limita las opciones de Edificio a los de esa localidad, y así en
cadena). El botón "Actualizar tabla" (`botonPrimario`) vuelve los seis
filtros a su default y reinicia el orden de la tabla.

100% en vivo (no lee `SnapshotMensual`): sin ningún filtro de ubicación
es todo el sistema, sin filtro de período muestra una fila por cada mes
desde el primer dato hasta el actual (`_periodos_para_filtro`). Entre
Localidad/Edificio/Unidad/Consultorio "el más específico manda" — elegir
un Consultorio puntual fija el alcance a ese consultorio solo, sin
importar qué haya elegido (o no) en los combos de nivel superior
(`_ids_consultorio_del_alcance`/`estadisticas_varias`). Cualquier
combinación de filtros dispara un recálculo real de la tabla (no un
`setRowHidden` como el patrón de "Filtros que solo afectan la
visualización" — acá cambiar el alcance realmente recalcula ocupación,
horas y montos para ESE alcance, no solo oculta filas de un cálculo ya
hecho para todo el sistema).

### Detalles compartidos por las dos solapas

Tabla ordenable por click en cualquier título (`OrdenTabla`, mismo
criterio que Llaves/Reservas/Placas/Pagos/Novedades — no el
`setSortingEnabled` nativo de Qt, que compararía las celdas ya
formateadas como texto y ordenaría mal los montos/porcentajes/horas);
por defecto, sin ningún click todavía, las dos quedan ordenadas por
Período de más nuevo a más viejo. Cada solapa es su propia clase
(`_PanelHistorialGeneral`/`_PanelEstadisticasVarias`, mismo patrón que
`ProcesoLiquidacion`/`_PanelEmisionArchivos` en Liquidación mensual y
`_PanelReservasRegulares`/`_PanelReservasAisladas` en Reservas) con
`objectName="panelSolapa"` y su propio `showEvent` — necesario porque
cada pestaña necesita enfocar su propio primer control al mostrarse (no
alcanza con uno solo en la pantalla contenedora), y ese patrón solo
funciona pasando el panel directamente a `addTab(...)` (no envuelto en
un `QScrollArea` externo, que rompería la propagación del evento).

Celdas: "Variación sobre período anterior" en rojo cuando es negativa
(mismo criterio que "Importes negativos en rojo" de la sección de
tablas, aplicado acá a un delta de horas en vez de a un monto). Un valor
faltante (snapshot viejo sin las columnas nuevas) se muestra en blanco,
nunca como 0 — un cero sería un dato real distinto de "no lo sabemos".

Títulos de columna largos ("Variación sobre período anterior", "Monto
por horas regulares/aisladas", etc.) van partidos en dos líneas con un
`"\n"` literal en el texto del encabezado (pedido de la clienta: más
alto, menos ancho) — `QHeaderView` ya soporta esto solo, agranda el alto
de la fila de encabezados y `resizeColumnsToContents()` angosta la
columna a la línea más larga de las dos, sin ningún código extra. Nada
puntual de Estadísticas: cualquier tabla nueva con un título largo puede
usar el mismo recurso.

## Configuración general (formulario plano -> 5 solapas temáticas)

Pasó de un `QFormLayout` con los 30 campos de `Configuracion` seguidos,
uno abajo del otro sin ningún agrupamiento, a formato solapa con 5
pestañas temáticas. El agrupamiento lo armé a criterio propio (pedido
explícito de la clienta: "separalo por solapas por temas a tu
criterio") y lo mostré armado antes de tocar código para que lo
aprobara — "en principio está bien así, cualquier cosa se reevalúa más
adelante" — así que el criterio de agrupamiento en sí queda abierto a
cambios puntuales más adelante, no es definitivo:

- **General**: Nombre del espacio, Ruta del logo, Modo oscuro, Mensajes
  en plural, Módulos extendidos, Visualizar campos libres, Cantidad de
  decimales.
- **Grilla y ocupación**: Días de grilla, Hora inicio/fin de grilla,
  Fracción de grilla, Umbral de giro de grilla, Rangos de estadísticas
  de ocupación.
- **Valores y liquidación**: Frecuencia/meses de actualización de
  valores, Recargo % aisladas (+ el check "activo por defecto"), %
  ajuste saldo atrasado, Tolerancia deuda para descuento, % descuento
  feriado/no laborable, Semanas de vacaciones máximas, Días de margen
  para envío de liquidaciones, Retención historial lista de espera.
- **Archivos y backup**: Frecuencia de backup a Drive, Carpeta base de
  archivos, Carpeta de backup, Tamaño máximo de imagen.
- **Modo QA**: Fecha ficticia, Modo fecha ficticia.

`_GRUPOS` (`app/gui/pantallas/configuracion.py`) es la única fuente de
este agrupamiento — mover un campo de solapa es cambiar una lista, no
tocar el resto de la pantalla. Un test (`test_todos_los_campos_estan_
agrupados_una_sola_vez`) verifica que `_GRUPOS` cubre exactamente los
mismos campos que `_CAMPOS_TEXTO`/`_CAMPOS_NUMERICOS`/`_CAMPOS_
BOOLEANOS` (ninguno se pierde ni queda duplicado) para que un futuro
cambio de agrupamiento no pueda dejar un campo afuera sin que un test
lo note.

El botón "Guardar" queda FUERA del `QTabWidget` (no es de ninguna
solapa en particular): sigue guardando los 30 campos juntos de una sola
vez, no solo los de la pestaña que se esté viendo — sigue siendo una
única fila de configuración, el agrupamiento es puramente visual. Por
ser compartido por las cinco solapas, la cadena de foco Enter/Tab
(`_actualizar_cadena_foco`) se reinstala cada vez que se cambia de
pestaña (`QTabWidget.currentChanged`) con los campos de ESA solapa +
"Guardar" al final — necesario porque instalar las cinco cadenas de una
sola vez dejaría a "Guardar" respondiendo siempre según la última
cadena instalada (la de la solapa construida al final), sin importar
cuál esté realmente visible en pantalla.

Cada solapa (`_PanelCampos`) sigue el mismo patrón que `_PanelReservas
Regulares` de Reservas: el propio widget con `objectName="panelSolapa"`
es el que se pasa a `addTab(...)` (no envuelto desde afuera en un
`QScrollArea`), con su `QScrollArea` interno para el formulario y su
propio `showEvent` que enfoca el primer campo de esa solapa al
mostrarse — mismo motivo que en Estadísticas/Liquidación/Reservas: un
`setFocus()` durante la construcción no alcanza a pegar antes de que el
`QTabWidget` contenedor esté realmente mostrado.

Segunda vuelta sobre esta misma pantalla ("arreglá todo lo que te
parezca de esos últimos comentarios"), los cuatro puntos que habían
quedado pendientes:

- **Campos numéricos**: pasaron de `QLineEdit` con parseo manual a
  `float` a `QSpinBox`/`QDoubleSpinBox` (`_crear_spin_numerico`) — ya no
  hay forma de dejarlos en un estado inválido, así que `_guardar` dejó
  de necesitar el try/except de conversión para estos catorce campos.
  Los de hora (`HoraInicioGrilla`/`HoraFinGrilla`) muestran "8:00hs" en
  vez del decimal (`_SpinHora`, mismo criterio que Oferta/Reservas/Lista
  de espera, duplicado acá); los de porcentaje suman sufijo "%"; el de
  tolerancia de deuda (`ToleranciaDeudaDescuento`) se muestra como
  moneda (`_SpinMoneda`, mismo criterio que `_SpinMonto` de Pagos);
  "Tamaño máximo de imagen" suma sufijo " MB"; el resto son enteros
  simples. Los rangos (`_RANGOS_NUMERICOS`) se eligieron generosos a
  propósito — nunca deben recortar un valor ya guardado en la base al
  cargar la pantalla (`setValue()` clampea en silencio sin avisar).
- **Fecha ficticia**: pasó al mismo `QDateEdit` con calendario que el
  resto del sistema ("Selectores y fecha" más arriba). Como un
  `QDateEdit` siempre tiene algún valor concreto (a diferencia del
  `QLineEdit` de antes, que podía quedar vacío), un valor NULL en la
  base (base nueva, todavía sin guardar nada acá) carga la fecha real de
  hoy como default de visualización nomás — `ModoFechaFicticia`
  (el check aparte) sigue siendo lo único que decide si esa fecha se usa
  de verdad en `app.negocio.dias.fecha_actual`, así que este cambio no
  altera ningún comportamiento existente.
- **Ruta del logo / Carpeta base de archivos / Carpeta de backup**:
  suman un botón "Elegir" (`_CampoRuta`, `QFileDialog` nativo — archivo
  para el logo, carpeta para las otras dos) al lado del campo de texto,
  en vez de tipear la ruta a mano. El campo de texto interno sigue
  siendo un `QLineEdit` común (`entradas[nombre]` apunta a ÉL, no al
  contenedor), así que `actualizar`/`_guardar` no necesitaron cambiar
  nada para estos tres campos — cancelar el selector deja el valor que
  ya había, no lo borra.
- **"Días de grilla" con caracteres escapados**: los tres `json.dumps`
  de `app/db/seed.py` que arman los valores por defecto de `DiasGrilla`
  ahora pasan `ensure_ascii=False` — el JSON seguía siendo válido antes
  (`é` decodifica a "é" igual), pero se mostraba crudo en esta
  pantalla en vez de "Miércoles"/"Sábado".

## Panel de control (formato solapa + grilla de cuadritos informativos)

Primera vuelta: pasó de dos botones sueltos en una fila (uno primario,
el otro sin estilo) a formato solapa con los dos como `botonSecundario`
y una leyenda de estado propia arriba de cada uno. Segunda vuelta
(pedido explícito de la clienta sobre esa primera versión): esas dos
leyendas y el subtítulo del encabezado (período en curso + hoy) se
sacaron — la información que daban ahora vive, más completa, en una
grilla de cuadritos informativos debajo de los botones. También se
invirtió el orden de los botones ("Generar backup ahora" arriba,
"Avanzar de mes" abajo) y "Avanzar de mes" volvió a ser `botonPrimario`
(el otro queda `botonSecundario`) — sigue siendo la acción más
"definitiva" de la pantalla. La solapa pasó a llamarse "Panel de
control" (antes "Resumen") y, a futuro, va a terminar viviendo dentro
de otro formulario todavía sin definir — no se tocó nada de la
estructura pensando en eso, es solo un aviso para cuando se defina.

Columna izquierda (ancho fijo): "Generar backup ahora" arriba,
"Avanzar de mes" abajo. A la derecha, el mismo cuadro de texto fijo de
la primera vuelta (borde negro) explicando qué hace cada botón — no se
tocó, la clienta solo pidió sacar las leyendas, no esta explicación.

Debajo, una `QGridLayout` de 3 columnas con siete cuadritos (`_tarjeta`,
borde negro + título en negrita arriba, `QSizePolicy.Expanding` en los
dos ejes + `setColumnStretch`/`setRowStretch` a 1 en toda la grilla
para que ocupen todo el espacio disponible, pedido explícito de la
clienta — "que quede todo ocupado de alguna manera"):

1. **Fecha y hora actual**: reloj en vivo (`QTimer` cada 1000ms,
   `_actualizar_reloj`) con segundos — a propósito la hora REAL del
   sistema (`datetime.now()`), no la fecha ficticia de QA: un reloj en
   vivo tiene que orientar al operador con la hora real aunque el resto
   de la pantalla esté calculando sobre una fecha simulada.
2. **Período actual**: mismo texto que mostraba antes el subtítulo del
   encabezado ("Septiembre de 2026 (09/2026)"), ahora en su propio
   cuadrito.
3. **Último backup**: fecha/hora del backup más reciente (`app.negocio.
   backup.ultimo_backup`, nueva función — arma el `datetime` completo a
   partir del nombre de la subcarpeta, mismo criterio que la ya
   existente `backup_vencido` pero sin descartar la hora), frecuencia
   configurada y estado (al día/vencido, reusando `backup_vencido`)
   — "información completa", pedido explícito de la clienta.
4. **Feriados y fechas especiales (este mes y el próximo)**: ventana
   CALENDARIO (primer día del mes en curso al último día del siguiente,
   `app.negocio.panel_control.fechas_especiales_mes_actual_y_siguiente`
   — nueva función, distinta de la que ya existía para la alerta de
   "próximos 15 días corridos", que sigue como estaba).
5. **Profesionales** (`calcular_estadisticas_profesionales`, nueva
   función): cantidad con plan de pago vigente (`PlanPago.Estado =
   'Activo'`), cantidad con saldo fuera de tolerancia (mismo criterio
   que las alertas de deuda, sumando regulares + aisladas en un solo
   número acá), cantidad con reservas regulares activas hoy.
6. **Ocupación y horas** (`calcular_estadisticas_ocupacion`, nueva
   función, reusa `calcular_ocupacion`/`monto_neto_aislada_periodo` de
   `app.negocio.estadisticas`): % de ocupación regular general, horas
   regulares reservadas por semana en este momento, horas aisladas
   confirmadas del mes en curso, monto que generaron esas horas
   aisladas (neto, mismo criterio que Estadísticas — ver esa sección
   para el detalle del pasaje de bruto a neto), y "saldo pendiente
   de cobro este mes" — lo facturado del período
   (`LiquidacionEmitida.MontoGenerado`) menos lo ya cobrado imputado a
   ese mismo período (`HistorialPagos.Monto`); confirmado con la
   clienta en el repaso de pendientes abiertos, es el cálculo que tenía
   en mente.
7. **Alertas**: el mecanismo de siempre (`Alertas`/`calcular_alertas`,
   `_tarjeta_alerta`/`_tarjeta_alerta_simple`, `self.contenedor_alertas`/
   `self.layout_alertas` con los mismos nombres de atributo que antes)
   sin cambios funcionales ("algo más que se te ocurra": en vez de
   inventar contenido nuevo para este último cuadrito, se reaprovechó lo
   que ya existía).

Sexta vuelta (repaso de pendientes abiertos, ya con todas las
pantallas revisadas): el título pasa a mostrar el nombre del espacio
con `.upper()` — pedido explícito de la clienta, mismo formato Nivel 1
que el resto de las pantallas del sistema. De paso surgió que el
nombre real del espacio es "Espacio Ramos Consultorios" (no "Espacio
Ramos", el fallback que usaba el código hasta ahora cuando
`Configuracion.NombreEspacio` está vacío) — se corrigió ese fallback
acá y en todos los demás lugares que lo repetían igual (`app.negocio.
oferta_busqueda_texto`, `app.pdf.estilos`, `app.pdf.oferta_pdf`,
`app.pdf.placas_pdf`), salvo `app.pdf.propuesta_pdf`/`disponibilidad_
pdf`, que ya arman su nombre de archivo como "{nombre_espacio}
Consultorios" — ahí cambiar el fallback hubiera duplicado la palabra
("...Consultorios Consultorios.pdf"), así que esos dos quedaron con el
fallback "Espacio Ramos" de siempre (la fórmula ya arma el nombre
completo por su cuenta).

**Revertido en el reordenamiento de formularios**: al pasar Panel de
control a ser un formulario más entre otros seis del menú de "Sistema"
(dejó de ser conceptualmente "la portada" del sistema), el título de
mostrar el nombre del espacio volvió a mostrar el nombre de la
pantalla ("PANEL DE CONTROL") — pedido explícito de la clienta, para
quedar coherente con el resto (todas las demás pantallas del sistema
muestran su propio nombre, nunca el del espacio). El resto de lo
corregido en esta vuelta (el fallback "Espacio Ramos Consultorios" en
los demás lugares del código) no se tocó, sigue vigente.

Tercera vuelta (ajustes sobre la grilla de cuadritos de la vuelta
anterior): "Alertas" deja de ser un cuadrito más de la grilla 3x2 —
pasa a su propio `QFrame` aparte, ABAJO de la grilla, ocupando todo el
ancho de la pantalla (`layout_solapa.addWidget(self.tarjeta_alertas,
stretch=1)`, fuera del `QGridLayout`) y quedándose con todo el
`QScrollArea` que ya tenía (puede ser una lista larga) — pedido
explícito de la clienta. Los seis cuadritos que quedan en la grilla
(reloj, período, backup, fechas especiales, profesionales, ocupación)
tienen que ser todos del mismo ancho Y del mismo alto: `_ALTO_MINIMO_
TARJETA` (140px) fuerza un piso de altura parejo en las seis, para que
el cuadrito con más líneas de contenido ("Ocupación y horas", 5 líneas)
no termine desparejando el resto — sin ese piso, cada fila de la
grilla toma la altura de su contenido más alto ANTES de repartir el
espacio sobrante por `setRowStretch`, así que dos filas con contenido
de distinto largo quedaban de distinto alto. El ancho ya salía parejo
solo (`setColumnStretch` a 1 en las tres columnas).

Dentro de cada cuadrito (`_tarjeta`, la función que arma el título y
devuelve el layout para que cada uno cargue su contenido): el título
pasa a itálica (`QLabel` con `font-style: italic;` en el stylesheet, en
vez de negrita) y termina en ":" — pedido explícito de la clienta.

Cuarta vuelta: la clienta señaló, con captura en mano, que SÍ había
"cuadritos dentro de los cuadros" — el título y el contenido de cada
cuadrito tenían su propio recuadro además del borde exterior. La causa:
`_tarjeta` pintaba el borde con un selector de clase sin acotar
(`"QFrame { border: 1px solid black; }"`), y en Qt `QLabel` HEREDA de
`QFrame` — ese selector de clase le pintaba el mismo borde a cualquier
`QLabel` hijo del cuadrito (el título y el contenido), no solo al
`QFrame` de afuera. Se corrigió acotando el estilo por objectName
(`tarjeta.setObjectName("cuadritoInfo")` +
`"QFrame#cuadritoInfo { border: ... }"`, selector por id en vez de por
clase) — mismo criterio que ya usaban `QFrame#tarjetaAlerta`/
`QLabel#tituloPantalla`/etc. en `estilos.py`, que por eso nunca habían
tenido este problema. Ojo para el futuro: cualquier regla QSS que
apunte a `QFrame` (o a cualquier clase de la que `QLabel` herede) sin
acotar por objectName corre el mismo riesgo de colarse a los `QLabel`
de adentro.

De paso, el título de cada cuadrito pasa también a NEGRITA (además de
la itálica que ya tenía), y se suma una línea divisoria
(`_linea_divisoria`, mismo `QFrame.Shape.HLine` que el resto del
sistema) entre los dos botones de la columna izquierda — se había
sacado sin querer en la segunda vuelta al eliminar las leyendas que
tenía al lado, y la clienta la pidió de vuelta.

Quinta vuelta: la clienta notó que la columna de "Fecha y hora actual"
quedaba más ancha que las otras dos. Causa real: `QGridLayout` calcula
el ancho mínimo de cada columna a partir del contenido más ancho que
tenga adentro, y RECIÉN DESPUÉS reparte el espacio sobrante según
`setColumnStretch` — con las tres columnas en 1 de stretch por igual,
la que tenía el título más largo ("Feriados y fechas especiales (este
mes y el próximo)") arrancaba con un mínimo más alto que las otras dos,
así que terminaba más ancha aunque el stretch fuera parejo. Se acortó
el título a "Feriados y fechas especiales próximas" (pedido explícito
de la clienta) y las tres columnas quedaron parejas (comprobado:
~381-382px las tres, contra una diferencia real de 4px antes del
cambio — ver `test_hay_seis_tarjetas_parejas_en_la_grilla_y_alertas_
aparte`).

De paso cambió la lógica de ese cuadrito (`app.negocio.panel_control.
fechas_especiales_proximas_dos_meses`, renombrada desde `fechas_
especiales_mes_actual_y_siguiente`): antes arrancaba en el día 1 del
mes en curso (mostraba fechas ya pasadas de ese mes) y llegaba hasta el
último día del mes siguiente; ahora arranca en HOY (lo que ya pasó del
mes no se muestra) y llega hasta el último día del SEGUNDO mes
siguiente — "lo que queda de este mes, más los dos próximos meses",
pedido explícito de la clienta.

Las explicaciones de los botones dejan de ser un único cuadro de texto
compartido y pasan a ser una por botón (`self.etiqueta_explicacion_
backup`/`self.etiqueta_explicacion_avanzar`, `_texto_explicacion`),
cada una en la misma fila que su botón correspondiente (`fila_backup`/
`fila_avanzar`, con el botón alineado arriba —
`Qt.AlignmentFlag.AlignTop` — para que no se estire ni quede centrado
raro contra un texto de varias líneas) — "que queden a la par del botón
correspondiente", pedido explícito de la clienta. El texto de "Avanzar
de mes" se reescribió con la redacción exacta que dio la clienta
("Avanzar de mes realiza el pase de un mes a otro en el sistema. Este
proceso ubica virtualmente al operador en el nuevo período cualquier
sea la fecha real del día."); el de "Generar backup ahora" es el mismo
texto de siempre, solo que ahora en su propio cuadro en vez de
compartido.

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

## Seguridad (login, bloqueo por inactividad, niveles de acceso)

Pantalla/funcionalidad nueva pedida por la clienta después de cerrar la
revisión "uno por uno" de las pantallas existentes — no es parte de esa
revisión, es una funcionalidad nueva del sistema. Toda la lógica vive en
`app.negocio.seguridad` (ver su docstring para el detalle técnico de
hashing/historial/niveles); acá va el resumen de las decisiones de
producto.

Pedido inicial: manejo de contraseñas para ingresar al sistema, bloqueo
automático por inactividad, historial de cambios de contraseña, y
niveles de acceso — pensado en un primer momento para la clienta y su
familia nomás, pero dejando la puerta abierta a que cada pantalla del
menú requiera un nivel puntual más adelante. Antes de implementar nada
se le consultaron tres decisiones abiertas (`AskUserQuestion`):

- **Recuperación de un acceso perdido** (no hay servidor/email para
  resetear nada, es una app de escritorio): "ambas" — un usuario
  Administrador puede resetear la contraseña de otro sin conocer la
  actual (pantalla de Usuarios), MÁS una contraseña maestra guardada
  aparte en `Configuracion` (hasheada, nunca se pide en el uso normal)
  como red de seguridad si se pierde el acceso de TODOS los
  administradores a la vez.
- **Qué pasa al vencer el tiempo de inactividad**: "bloquea sin cerrar
  sesión" — la pantalla queda tapada y pide la contraseña para
  desbloquear, pero lo que estaba cargado en cada formulario (sin
  guardar todavía) sigue ahí al volver a entrar.
- **Niveles de acceso**: sobre si se iba a poder ir modificando qué
  nivel requiere cada pantalla desde el sistema mismo (no fijo en
  código) — confirmado que sí, ese es justamente el diseño: la
  asignación pantalla→nivel se guarda en una tabla propia
  (`PermisoPantalla`) editable en cualquier momento desde la nueva
  pantalla "Usuarios y permisos", nunca hay que tocar código para
  cambiarla. Se arrancó con dos niveles (Administrador/Operador,
  catálogo abierto a sumar un tercero si hiciera falta más adelante) en
  vez de un número abierto 1-5: más simple de entender y de asignar por
  pantalla mientras el uso real siga siendo ella y su familia.

### Modelo de datos

`NivelAcceso` (catálogo con `Orden` — mayor Orden = más privilegios,
sembrado con Administrador=100/Operador=10), `Usuario` (login: nombre,
hash+salt de contraseña, nivel, activo, último ingreso),
`HistorialContrasenas` (una fila por cada cambio de contraseña: hash/
salt ANTERIOR al cambio — nunca la contraseña en texto plano, ni
siquiera la nueva —, fecha, motivo y quién lo hizo) y `PermisoPantalla`
(`NombrePantalla` → nivel mínimo requerido, una fila por cada pantalla
del menú). `Configuracion` suma `MinutosInactividadBloqueo` y la
contraseña maestra (hasheada, dos columnas: hash y salt).

Contraseñas hasheadas con PBKDF2-HMAC-SHA256 + salt aleatorio por
usuario (`hashlib`/`secrets` de la librería estándar — no se sumó
ninguna dependencia nueva al proyecto para esto).

`PermisoPantalla` no se siembra con una lista fija de nombres de
pantalla (eso duplicaría la lista de `gui_main.construir_secciones` en
la capa de datos): `app.negocio.seguridad.asegurar_permisos_pantalla`
se llama en `gui_main.main()`, después de armar la lista de secciones,
y le crea una fila (al nivel más bajo — visible para cualquiera, para
no restringir sin querer algo que ya se veía) a toda pantalla que
todavía no tenga una. Así una pantalla nueva del sistema siempre nace
visible hasta que alguien decida subirle el nivel desde "Usuarios y
permisos".

### Login y bloqueo (`app/gui/dialogos_seguridad.py`)

`DialogoLogin` se muestra al arrancar `gui_main.main()`, antes de
`VentanaPrincipal`. Si `Usuario` está vacío (primer arranque de esta
base), muestra un alta de Administrador en vez de un login que nadie
podría pasar. Cancelar el diálogo cierra la aplicación sin llegar a
mostrar la ventana principal.

`MonitorInactividad` se instala como event filter de la `QApplication`
entera (`app.installEventFilter(...)`): cualquier click/tecla/scroll en
cualquier pantalla reinicia un `QTimer` armado con
`Configuracion.MinutosInactividadBloqueo`; al vencer sin actividad
dispara `DialogoDesbloqueo` de forma modal — sin botón Cancelar ni X
(`reject()` no hace nada), la única salida es tipear la contraseña del
usuario logueado o la contraseña maestra. No cierra sesión ni destruye
ningún estado de las pantallas: es un overlay modal encima de
`VentanaPrincipal`, que sigue intacta debajo.

`VentanaPrincipal` suma un parámetro opcional `id_nivel_usuario` (`None`
por defecto, el que usan todos los tests de pantallas que no tienen
nada que ver con Seguridad — no filtra nada): cuando viene informado,
antes de armar la navegación descarta las `Seccion` cuyo
`nivel_alcanza(conn, id_nivel_usuario, seccion.nombre)` da `False`, sin
llegar a instanciar esas pantallas.

### Pantalla "Usuarios y permisos" (`app/gui/pantallas/usuarios.py`)

Nueva sección del menú, categoría "Configuración" (junto a
"Configuración general"/"Importar planilla"). No usa `PantallaCRUD`
(mismo criterio que Bloques rígidos/Gestor de archivos): el alta
necesita contraseña + confirmación, la edición no debería poder pisar
la contraseña sin querer, y la segunda tabla (permisos por pantalla) no
es un catálogo de registros propios.

Formato solapa con DOS pestañas (pedido explícito de la clienta al
revisar la primera versión, que apilaba las dos tablas en una sola
solapa): mismo patrón que `_PanelHistorialGeneral`/`_PanelEstadisticasVarias`
de Estadísticas — cada solapa (`_PanelUsuarios`/`_PanelPermisosPantalla`)
es su propia clase con `objectName="panelSolapa"` y su propio
`showEvent`, pasada directamente a `addTab(...)` (no envuelta en un
`QScrollArea` externo, que rompería la propagación del evento):

- **"Usuarios"**: columna de botones a la izquierda ("Nuevo usuario"
  `botonPrimario`; "Editar usuario"/"Resetear contraseña"/"Ver
  historial de contraseñas" `botonSecundario`), tabla a la derecha
  (nombre, nivel, activo, último ingreso). Editar cambia nombre/nivel/
  activo (nunca la contraseña, para eso está "Resetear contraseña"
  aparte, que no pide la actual). "Ver historial de contraseñas" abre
  un diálogo de solo lectura con fecha, motivo y quién hizo cada cambio
  del usuario seleccionado.
- **"Permisos por pantalla"**: sin botones, una tabla sola con una fila
  por cada `NombrePantalla` ya registrada y un combo de nivel por fila
  — cambiar el combo escribe directo a la base (`UPDATE
  PermisoPantalla`), sin un botón "Guardar" aparte, mismo criterio
  inmediato que "Marcar como principal" en Gestor de archivos.

Guardarraíl: no se puede desactivar ni degradar (bajarle el nivel) al
único usuario Administrador ACTIVO que quede
(`app.negocio.seguridad.hay_otro_usuario_activo_de_nivel`) — dejaría el
sistema sin nadie que pueda administrarlo. El diálogo de edición se
cierra igual, pero el cambio no se aplica y se avisa por qué.

### Solapa "Seguridad" en Configuración general

Sexta solapa (junto a General/Grilla y ocupación/Valores y liquidación/
Archivos y backup/Modo QA — pedido explícito de la clienta: "una solapa
más para poner dentro de configuración"), con los dos ajustes globales
simples: minutos de inactividad para el bloqueo automático (spin
numérico, mismo mecanismo que el resto de `_CAMPOS_NUMERICOS`) y la
contraseña maestra. Esta última NO es un campo de texto común — es un
"campo especial" (`_CAMPOS_ESPECIALES`, aparte de texto/numérico/
booleano/fecha): un botón "Establecer/cambiar contraseña maestra" que
abre su propio diálogo y escribe directo a la base apenas se confirma
(`cambiar_contrasena_maestra`, ver segunda vuelta más abajo), sin pasar
por el botón "Guardar" general de la pantalla — nunca queda una
contraseña pendiente de guardar en memoria más tiempo del necesario, y
nunca se muestra ni se lee el valor actual.

La gestión de Usuarios y de Permisos por pantalla quedó en su propia
sección del menú ("Usuarios y permisos", ver arriba) en vez de meterse
en esta solapa — es una tabla de registros propios con sus propios
diálogos, no un valor simple de `Configuracion` como el resto de las
solapas de esta pantalla; mismo criterio que "Importar planilla" (
también "de Configuración" pero fuera de `ConfiguracionGeneral`).

### Segunda vuelta: tres huecos que señaló la clienta al repasar el diseño

Antes de dar por cerrada esta primera implementación, la clienta hizo
tres preguntas puntuales sobre el comportamiento tal cual había quedado
armado, que expusieron huecos reales (no cambios de gusto, sino casos
sin cubrir):

- **"¿Para cambiar la contraseña maestra pide algo?"** No pedía nada:
  cualquiera que tuviera abierta "Configuración general" podía pisarla
  sin volver a autenticarse. Se resolvió con "la contraseña maestra
  anterior" (la opción que eligió, no "tu propia contraseña de
  usuario"): `app.negocio.seguridad.cambiar_contrasena_maestra(conn,
  contrasena_actual, contrasena_nueva)` exige la anterior correcta
  ANTES de reemplazarla — salvo la primera vez que se establece
  (`hay_contrasena_maestra` todavía `False`), que se puede fijar
  libremente porque no hay ninguna que pedir. `_DialogoContrasenaMaestra`
  ahora recibe `conn` y muestra el campo "Contraseña maestra actual"
  solo cuando corresponde (`self._pide_actual`), y es el diálogo mismo
  el que escribe a la base al confirmar (antes lo hacía
  `_CampoContrasenaMaestra` después de leer `.contrasena()` del
  diálogo).
- **"¿Con qué contraseña maestra viene el sistema al instalarse?"** Con
  ninguna — el campo nace `NULL` y así se queda hasta que alguien la
  establece a mano. Sumado a que las pantallas nacían visibles para
  cualquier nivel (ver el punto siguiente), esto significaba que si el
  único Administrador se olvidaba su contraseña ANTES de que a alguien
  se le ocurriera configurar la maestra, no había ninguna forma de
  recuperar el sistema. Se resolvió pidiéndola en la misma alta del
  primer Administrador: `DialogoLogin`, en su modo "alta inicial" (sin
  usuarios cargados todavía), ahora suma dos campos más ("Contraseña
  maestra (recuperación)"/"Confirmar contraseña maestra") y llama
  `establecer_contrasena_maestra` junto con `crear_usuario` — la red de
  seguridad queda puesta desde el minuto uno, no como paso opcional
  posterior.
- **"¿Cuántos niveles hay?"** Dos, fijos (Administrador/Operador) — la
  respuesta en sí no cambió nada, pero al mismo tiempo se marcó que,
  como toda pantalla nace en el nivel más bajo (Operador) hasta que se
  la sube a mano, un usuario Operador recién creado podía entrar
  directo a "Configuración general" (y desde ahí a la contraseña
  maestra) o a "Usuarios y permisos" sin que nadie se lo hubiera
  impedido. Se resolvió haciendo que esas dos pantallas puntuales nazcan
  directo en Administrador: `asegurar_permisos_pantalla` suma un
  parámetro `nombres_nivel_alto` (default vacío, no cambia el
  comportamiento de ninguna otra pantalla), y `gui_main.main()` lo llama
  con `{"Configuración general", "Usuarios y permisos"}` — el resto de
  las pantallas del sistema sigue naciendo visible para cualquiera,
  como antes.

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

## Reordenamiento de formularios y solapas (en curso)

Después de cerrar la revisión "uno por uno" de cada pantalla (incluida
Seguridad), la clienta pidió una reorganización completa de la
navegación: mandó un Excel con, por cada formulario nuevo del menú, sus
solapas (en orden — la primera es la que se ve por defecto al entrar) y
qué formulario/solapa vieja va a parar ahí, más una columna de
modificaciones puntuales. El criterio general: varias pantallas que hoy
son formularios propios del menú pasan a ser solapas de un formulario
más grande y afín (ej. "Importar planilla" deja de estar en el menú y
pasa a ser una solapa de "Panel de control"), y las categorías del menú
se renombran de "Principal"/"Catálogos"/"Configuración" a "Sistema"/
"Operativa diaria".

Se detectaron dos casos que el Excel de la clienta no contemplaba
(pantallas/catálogos existentes sin destino asignado), resueltos con
ella antes de tocar código:
- La solapa "Estadísticas" de Vista rápida (tabla de ocupación en vivo,
  filtrable, DISTINTA de la pantalla completa "Estadísticas") — decisión:
  sacarla del sistema, queda cubierta por la pantalla completa.
- El catálogo "Placas" (tablero de posiciones/nombre grabado, DISTINTO
  de la pantalla operativa "Placas") — decisión: pasa a ser la tercera
  solapa de "Placas para timbres" (el nuevo nombre de la pantalla
  operativa "Placas").

El trabajo se hace por etapas (un merge por vez, con capturas y
pyflakes/suite después de cada uno), empezando por los merges más
simples de la categoría "Sistema":

### Panel de control + Importación

Primer merge hecho. "Importar planilla" deja de ser una pantalla propia
del menú y pasa a ser la segunda solapa de "Panel de control"
("Importación datos desde Excel"), junto a la primera ("Avance de
período y backups", todo lo que antes era el contenido único de esa
pantalla). Mecánicamente:

- `app/gui/pantallas/importacion.py`: la clase pasa de `PantallaImportacion`
  (pantalla completa, con su propio título Nivel 1 y su propio
  `QTabWidget` de una sola pestaña) a `_PanelImportacion` (una solapa
  desnuda — `objectName="panelSolapa"` puesto sobre sí misma, sin título
  ni `QTabWidget` propio), lista para pasarse directo a `addTab(...)` de
  otro formulario — mismo criterio ya usado en toda la revisión (
  `_PanelReservasRegulares`, `_PanelHistorialGeneral`, etc.). El contenido
  interno (botones, tabla de resultados, informe de integridad) no
  cambió en nada.
- `app/gui/pantallas/panel_control.py`: el contenido que antes era la
  única solapa de `PanelControl` ("Panel de control", con los dos
  botones, la grilla de cuadritos y las alertas) se extrajo tal cual a
  una clase nueva, `_PanelAvancePeriodo` (mismo patrón `panelSolapa`/
  `showEvent` propio). `PanelControl` queda como el contenedor de
  afuera: solo el título Nivel 1 (nombre del espacio) y un `QTabWidget`
  con las dos solapas (`_PanelAvancePeriodo` como "Avance de período y
  backups", `_PanelImportacion` — importado cruzado, mismo criterio que
  `_pixmap_primera_pagina_pdf`/`_opciones_profesional` en otras
  pantallas — como "Importación datos desde Excel"). `PanelControl.
  actualizar()` sigue siendo el punto de entrada de afuera (nada externo
  lo llamaba salvo el propio `__init__`), y ahora hace dos cosas:
  actualiza el título y delega en `self.panel_avance.actualizar()` para
  todo el resto (períodos, tarjetas, alertas).
- `gui_main.py`: se sacó la `Seccion` propia "Importar planilla" y su
  import; la ayuda de "Panel de control" se actualizó para mencionar las
  dos solapas.
- Tests: `test_gui_importacion.py` pasa a instanciar `_PanelImportacion`
  directo (dejó de tener sentido el test de "una sola pestaña", ya no
  hay ningún `QTabWidget` propio — se reemplazó por un test más simple
  que confirma el `objectName="panelSolapa"`). `test_gui_panel_control.py`
  pasa todos sus accesos de `pantalla.boton_backup`/`etiqueta_*`/etc. a
  `pantalla.panel_avance.boton_backup`/etc. (el título sigue siendo
  `pantalla.titulo`, en el contenedor de afuera), y suma dos tests
  nuevos confirmando las dos solapas y que la de Importación es un
  `_PanelImportacion` funcional.

### Configuración general + Bloques rígidos

Segundo merge de "Sistema" hecho. "Bloques rígidos" deja de ser una
pantalla propia del menú y pasa a ser una solapa más de "Configuración
general", intercalada entre "Grilla y ocupación" y "Valores y
liquidación" (7 solapas en total).

- `app/gui/pantallas/bloques_rigidos.py`: `PantallaBloquesRigidos` pasa
  a `_PanelBloquesRigidos` (mismo criterio que `_PanelImportacion`): sin
  título Nivel 1 ni `QTabWidget`/`QScrollArea` propio, `objectName=
  "panelSolapa"` puesto sobre sí misma, lista para `addTab(...)`. El
  contenido (Buscar/Nuevo/Editar/Eliminar + tabla) no cambió.
- `app/gui/pantallas/configuracion.py`: a diferencia de las otras seis
  solapas (todas `_PanelCampos`, generadas en un loop sobre `_GRUPOS`
  con campos simples de `Configuracion`), "Bloques rígidos" es un
  catálogo completo con su propia lógica y su propia cadena de foco
  Enter/Tab (Buscar → Nuevo → Editar → Eliminar) — no tiene sentido que
  el botón "Guardar" compartido (que persiste los campos de
  `Configuracion`) se sume al final de esa cadena. Se resolvió
  intercalando la solapa en `_armar_ui` (después de agregar "Grilla y
  ocupación", antes de seguir con el resto de `_GRUPOS`) y anotando un
  `None` en la posición correspondiente de `self._paneles` — `
  _actualizar_cadena_foco` corta temprano cuando el panel de la solapa
  actual es `None`, dejando que `_PanelBloquesRigidos` siga manejando su
  propia cadena de foco de siempre, sin tocarla. Mismo criterio ya
  documentado para Gastos operativos (`instalar_foco=False`): una
  solapa que "arma la suya propia" en vez de sumarse a la genérica.
- `gui_main.py`: se sacó la `Seccion` propia "Bloques rígidos" y su
  import; la ayuda de "Configuración general" se actualizó para
  mencionar la solapa nueva.
- Tests: `test_gui_bloques_rigidos.py` pasa a instanciar
  `_PanelBloquesRigidos` directo, con el mismo reemplazo del test de
  "una sola pestaña" por uno de `objectName="panelSolapa"` que en
  Importación. `test_gui_configuracion.py` suma un helper
  `_indice_de_solapa`/`_panel_de_grupo` (busca la solapa por su TEXTO en
  vez de por posición fija en `_GRUPOS`, que ya no coincide 1 a 1 con el
  índice real de cada solapa desde que se intercaló una que no viene de
  `_GRUPOS`) y lo usa en los tests que antes indexaban `_paneles`/
  `_GRUPOS` a mano (búsqueda de la solapa "Seguridad", cambio de solapa
  para revisar la cadena de foco); suma un test nuevo confirmando que la
  cadena de foco NO se reinstala al entrar a "Bloques rígidos".

### Archivos y listas (formulario nuevo, 4 solapas)

Tercer merge de "Sistema" hecho, el primero que junta pantallas antes
completamente independientes (sin relación entre sí) en un formulario
nuevo. "Archivos y listas" agrupa "Gestor de archivos del espacio"
(antes "Gestor de archivos", pantalla propia) + tres catálogos genéricos
que antes también eran pantallas propias del menú: "Listas editables",
"Condiciones y normas" y "Detalles complementarios de la propuesta".

Esto destapó una limitación real de `PantallaCRUD` (`crud_generico.py`):
hasta ahora solo sabía ser una pantalla de catálogo independiente
(título Nivel 1 + su propio `QTabWidget` de una sola pestaña "Listado")
o, en modo `compacto=True`, un componente embebido DENTRO de otra
pantalla compuesta pero sin la fila de Buscar ni la tabla envuelta en
solapa (pensado para catálogos como Mensajes predefinidos, con sus
propios paneles alrededor). Ninguno de los dos servía para "este
catálogo completo, tal cual, como una solapa más de un formulario
ajeno" — que es exactamente lo que necesitan varios formularios del
reordenamiento (Archivos y listas, Base datos del espacio, Profesionales
+Profesiones, Registro de ausencias +Tipos de licencia, Liquidaciones
+Fechas especiales, Placas para timbres +Placas, Balance del negocio
+Gastos operativos). Se sumó un parámetro nuevo, `anidado: bool = False`:
cuando es `True`, `PantallaCRUD` se salta el título y el `QTabWidget`
propio, pone `objectName="panelSolapa"` en sí misma (el widget de más
afuera, listo para `addTab(...)`) y arma el resto (Buscar + Nuevo/
Editar/Eliminar + tabla, con su `QScrollArea` interno) exactamente igual
que siempre — se extrajo esa construcción a un método propio,
`_armar_panel_izquierda_y_tabla`, compartido entre el modo estándar y el
anidado, para no duplicar el layout. La cadena de foco Enter/Tab
(Buscar → Nuevo → Editar → Eliminar) y el `showEvent` que la reinicia y
enfoca el primer control siguen funcionando igual en modo anidado, sin
ningún cambio — es la misma `PantallaCRUD` de siempre, solo sin la
ceremonia de título/solapa propia. Los tres catálogos de este merge
(`pantalla_listas_editables`/`pantalla_condiciones_normas`/
`pantalla_detalles_complementarios_propuesta` en `catalogos.py`) suman
un parámetro `anidado` propio (default `False`, no cambia nada para
quien los siga llamando sin ese argumento) que solo reenvían a
`PantallaCRUD`.

- `app/gui/pantallas/imagenes.py`: `PantallaImagenes` pasa a
  `_PanelGestorArchivos`, mismo criterio que el resto de los merges
  (`objectName="panelSolapa"` en sí misma, sin título ni `QTabWidget`
  propio) — a diferencia de `_PanelImportacion`/`_PanelBloquesRigidos`,
  conserva un `QScrollArea` interno (mismo patrón que `_PanelCampos` de
  Configuración general: el `objectName` va en el widget de más afuera
  aunque el contenido scrollee adentro), porque la pantalla original ya
  scrolleaba así. Esta pantalla nunca tuvo cadena de foco propia (no
  formó parte de la revisión "uno por uno") y se dejó tal cual — no es
  parte del alcance de esta reorganización agregarle una.
- `app/gui/pantallas/archivos_y_listas.py` (nuevo): `PantallaArchivosYListas`,
  mismo patrón que Usuarios y permisos — título Nivel 1 fijo
  ("ARCHIVOS Y LISTAS") + `QTabWidget` con las cuatro solapas en el
  orden del Excel de la clienta.
- `gui_main.py`: se sacaron las cuatro `Seccion` independientes
  ("Imágenes", "Listas editables", "Condiciones y normas", "Detalles
  complementarios (Propuesta)") y se sumó una sola, "Archivos y listas".
- Tests: `test_gui_imagenes.py` renombra la clase en sus imports/usos y
  suma un test de `objectName="panelSolapa"` (mismo criterio que
  Importación/Bloques rígidos). `test_crud_generico.py` suma dos tests
  para el modo `anidado=True` (sin título/QTabWidget, Buscar y foco
  intactos). `test_gui_archivos_y_listas.py` (nuevo) cubre el título, las
  cuatro solapas en orden, que "Gestor de archivos del espacio" es un
  `_PanelGestorArchivos` funcional y que las tres solapas de catálogo son
  `PantallaCRUD` anidadas de verdad (sin título propio, con `anidado is
  True`).

### Base datos del espacio (formulario nuevo, 5 solapas)

Cuarto y último merge de "Sistema": agrupa los cinco catálogos de
estructura física/contacto del espacio — antes cinco pantallas propias
del menú sin relación de navegación entre sí — en el orden de la cadena
de referencias real entre las tablas (Localidad → Edificio → Unidad →
Consultorio), más Responsables al final: "Localidades", "Edificios",
"Unidades", "Consultorios", "Responsables".

Mecánicamente el mismo patrón que Archivos y listas, reusando el
`anidado=True` de `PantallaCRUD` sumado en ese merge:
`pantalla_localidades`/`pantalla_edificios`/`pantalla_unidades`/
`pantalla_consultorios`/`pantalla_responsables` (`catalogos.py`) suman
su propio parámetro `anidado` (default `False`, sin efecto para quien ya
los llamaba sin ese argumento) que reenvían a `PantallaCRUD`.
`app/gui/pantallas/base_datos_espacio.py` (nuevo) define
`PantallaBaseDatosEspacio`, título Nivel 1 fijo + `QTabWidget` con las
cinco solapas. `gui_main.py` saca las cinco `Seccion` independientes y
suma una sola, "Base datos del espacio". Tests nuevos en
`test_gui_base_datos_espacio.py`, mismo criterio que Archivos y listas
(título, orden de las cinco solapas, cada una `anidado is True` sin
título propio, una solapa con datos reales cargados).

Con este merge, las cuatro pantallas de "Sistema" del reordenamiento
(Panel de control, Configuración general, Archivos y listas, Base datos
del espacio) quedan completas — sigue pendiente Usuarios y permisos
(que no necesitó ningún cambio, ya estaba en el formato final) y el
renombre de categorías "Principal"/"Catálogos"/"Configuración" a
"Sistema"/"Operativa diaria" en todas las `Seccion` de `gui_main.py`, que
queda para el final de toda la reorganización (junto con las pantallas
de "Operativa diaria" que todavía faltan).

### Grilla y mensajería + Valores (primeras dos de "Operativa diaria", con baja de Estadísticas en vivo)

Primer merge de "Operativa diaria", y el más grande hasta ahora: la vieja
pantalla "Vista rápida" (tres solapas: "Grilla semanal", "Valores de los
consultorios", "Estadísticas") se retira por completo, sus solapas se
reparten entre DOS formularios nuevos distintos, y una de las tres se
saca del sistema — la única baja de funcionalidad completa de todo el
reordenamiento (fuera de la reubicación del botón "Manual del usuario",
todavía pendiente). Antes de tocar código se le preguntó a la clienta
por este caso puntual, no contemplado en su Excel de reubicación (la
solapa "Estadísticas" de Vista rápida — una tabla en vivo, filtrable —
es DISTINTA de la pantalla completa "Estadísticas"): confirmó sacarla
del sistema, queda cubierta por la pantalla completa.

- **"Grilla y mensajería"** (`grilla_y_mensajeria.py`, nuevo): "Grilla
  semanal" (de Vista rápida) + "Centro de mensajería" + "Mensajes
  predefinidos" (antes las dos últimas, pantallas propias del menú).
- **"Valores"** (`valores.py`, nuevo): "Valores vigentes" (antes "Valores
  de los consultorios" de Vista rápida) + "Aumentos"/"Esquema de
  descuentos" (antes las dos solapas de la pantalla propia "Aumentos y
  descuentos").

Mecánica de la baja de Estadísticas: en `grilla_operativa.py` se borró
todo el código exclusivo de esa solapa (`_refrescar_estadisticas`,
`_ordenar_estadisticas_por_columna`, `_reconstruir_filas_estadisticas`,
`_ensanchar_columnas_localidad_edificio`, `_llenar_fila_estadistica`,
`tabla_estadisticas`/`filtros_estadisticas`/`_estadisticas`/
`_columna_orden_estadisticas`, las constantes `_COLUMNAS_ESTADISTICAS`/
`_PADDING_COLUMNAS_ESTADISTICAS`/`_VALOR_ESTADISTICA_POR_COLUMNA`/
`_fmt_horas`), junto con el módulo `app.negocio.estadisticas_operativas`
completo (`estadisticas_operativas.py` + su test) — sin otro consumidor,
confirmado por búsqueda antes de borrar. Lo que SÍ sigue usando ese
módulo (`_PanelFiltrosJerarquico`/`_PanelPromedios`, exclusivos de
"Valores de los consultorios") se quedó intacto.

Las dos solapas que sobreviven pasan a clases bare (`_PanelGrillaSemanal`/
`_PanelValoresVigentes`, ambas en `grilla_operativa.py`, mismo criterio
`objectName="panelSolapa"` de siempre) — la vieja `PantallaGrillaOperativa`
(título "Vista rápida" + su `QTabWidget` de tres solapas) se borra por
completo, cada nueva solapa se importa cruzada (import cruzado de un
símbolo privado, mismo criterio del resto de la reorganización) en el
formulario que corresponde.

`CentroMensajeria` (`mensajeria.py`) pasa a `_PanelCentroMensajeria`
(mismo criterio `_PanelImportacion`/`_PanelBloquesRigidos`: sin título ni
`QTabWidget`/`QScrollArea` propios). `PantallaMensajesPredefinidos`
(`mensajes_predefinidos.py`) pasa a `_PanelMensajesPredefinidos`: el
`PantallaCRUD` que arma internamente (con `panel_extra_superior_
izquierda` para todo lo propio de esta pantalla) suma `anidado=True`
(reusa el parámetro sumado en Archivos y listas); la fábrica
`pantalla_mensajes_predefinidos` se borra (ya no tiene otro consumidor).

`PantallaAumentos` (contenedor de "Aumentos y descuentos", dos solapas)
se retira: sus dos paneles (`_PanelAumentos`/`_PanelEsquemaDescuentos`,
ya eran clases bare desde que se armó esa pantalla) quedan como las dos
últimas solapas de "Valores", importadas cruzadas — ya no hace falta un
contenedor propio para ellas.

`gui_main.py`: se sacan las `Seccion` "Vista rápida", "Centro de
mensajería", "Mensajes predefinidos" y "Aumentos y descuentos"; se suman
"Grilla y mensajería" y "Valores".

Tests: `test_estadisticas_operativas.py` se borra entero (feature
retirada). `test_gui_pantalla_grilla_operativa.py` se reescribe: se
sacan todos los tests exclusivos de la solapa Estadísticas (8 tests) y
uno que comparaba el filtro de Valores contra el de la Grilla (dejó de
tener sentido: ya ni siquiera son solapas de la misma pantalla), el
resto pasa a instanciar `_PanelGrillaSemanal`/`_PanelValoresVigentes`
directo. `test_gui_mensajeria.py`/`test_mensajes_predefinidos.py` renombran
la clase en sus tests y suman un test de `objectName="panelSolapa"` (el
segundo además confirma `anidado is True` en el CRUD interno).
`test_gui_aumentos.py` reescribe sus ~27 tests para instanciar
`_PanelAumentos`/`_PanelEsquemaDescuentos` directo (se saca el único
test que existía solo para el contenedor, `test_pestanas`). Dos archivos
nuevos, `test_gui_grilla_y_mensajeria.py`/`test_gui_valores.py`, cubren
cada formulario nuevo (título, orden de solapas, tipo e identidad de
cada panel).

### Disponibilidad (con reubicación del botón "Manual del usuario")

Segundo merge de "Operativa diaria": agrupa "Oferta de consultorios" +
"Lista de espera" + "Archivos varios" (renombrada "Archivos para
enviar"), las tres antes pantallas propias e independientes del menú,
en un formulario nuevo. De paso, cumple el pedido puntual de la clienta
sobre esta misma reorganización: el botón "Manual del usuario" se saca
de "Archivos para enviar" (donde era uno de los botones de "elegir/ver",
junto a Propuesta/Disponibilidad) y se reubica en Gestor de archivos del
espacio (`imagenes.py`, formulario "Archivos y listas"), como botón
`botonPrimario` propio, después de "Eliminar" y con una línea divisoria
propia arriba.

- `oferta.py`/`lista_espera.py`/`archivos_varios.py`: `PantallaOferta`/
  `PantallaListaEspera`/`PantallaArchivosVarios` pasan a `_PanelOferta`/
  `_PanelListaEspera`/`_PanelArchivosVarios` (sin título ni `QTabWidget`
  propios). Caso especial: `_PanelListaEspera` NO le pone
  `objectName="panelSolapa"` a `self` — esta pantalla, desde antes de la
  reorganización, ya tenía el fondo claro de "ficha" acotado solo al
  formulario "Nuevo pedido" (la tabla de pedidos y los botones de abajo
  quedaban deliberadamente fuera de ese panel, sobre el fondo liso) — se
  preservó esa distinción tal cual estaba en vez de extender el fondo
  claro a toda la solapa, que hubiera sido un cambio visual no pedido.
- `disponibilidad.py` (nuevo): `PantallaDisponibilidad`, mismo patrón que
  el resto — título Nivel 1 fijo + `QTabWidget` con las tres solapas en
  el orden del Excel.
- Botón "Manual del usuario": `_PanelGestorArchivos` (`imagenes.py`) suma
  un parámetro `secciones` opcional (mismo dato que ya recibía
  `PantallaArchivosVarios` — la lista de `Seccion` del menú, para armar
  la ayuda contextual del manual vía `app.pdf.manual_pdf.
  generar_pdf_manual`) y un botón nuevo que, a diferencia del resto de
  los botones de este panel (que actúan sobre la fila seleccionada en la
  tabla), no depende de ninguna selección — siempre regenera el PDF
  contra el estado actual del sistema. `PantallaArchivosYListas` reenvía
  `secciones` hacia ese panel; `gui_main.py` se la pasa igual que antes
  se la pasaba a "Archivos varios" (comentario actualizado en
  `construir_secciones`, que arma la lista como mutable justamente por
  esto). `_PanelArchivosVarios` pierde `_TIPOS_DOCUMENTO["manual"]`, el
  botón y el parámetro `secciones` — ya no le hace falta.
- `gui_main.py`: se sacan las `Seccion` "Oferta de consultorios", "Lista
  de espera" y "Archivos varios"; se suma "Disponibilidad".
- Tests: `test_gui_oferta.py`/`test_gui_lista_espera.py`/
  `test_gui_archivos_varios.py` renombran la clase y suman/ajustan los
  tests de formato (el de Lista de espera se reescribe para no asumir
  más un `QTabWidget` ni un título propio). Los dos tests de "Manual del
  usuario" que tenía `test_gui_archivos_varios.py` se mudan, adaptados,
  a `test_gui_imagenes.py` (`_regenerar_manual` sobre
  `_PanelGestorArchivos`), más un test nuevo de posición/estilo del
  botón. `test_gui_main.py` actualiza su test de "la fábrica recibe la
  lista completa de secciones" para apuntar a "Archivos y listas" en vez
  de la ya inexistente "Archivos varios". `test_gui_disponibilidad.py`
  (nuevo) cubre el formulario compuesto.

### Profesionales (+ Profesiones y tratamientos)

Tercer merge de "Operativa diaria": agrupa "Profesionales" (listado +
documentación adjunta) con el catálogo "Profesiones" (renombrado
"Profesiones y tratamientos" como solapa), antes ambos pantallas propias
del menú.

A diferencia de los merges anteriores, acá el nombre del formulario de
afuera coincide con el de la pantalla vieja ("Profesionales"), así que
`app/gui/pantallas/profesionales.py` termina con las dos versiones
conviviendo en el mismo archivo: `PantallaProfesionales` (renombrada
desde la vieja pantalla) pasa a `_PanelProfesionales` (solapa desnuda,
`objectName="panelSolapa"`, sin título propio; el `PantallaCRUD` interno
`self.crud_profesionales` suma `anidado=True`), y el nombre
`PantallaProfesionales` queda libre para el contenedor de afuera nuevo
— título Nivel 1 fijo + `QTabWidget` con `_PanelProfesionales` como
"Listado de profesionales" y `catalogos.pantalla_profesiones(conn,
anidado=True)` (que suma su propio parámetro `anidado`, mismo mecanismo
que el resto de los catálogos) como "Profesiones y tratamientos". La
fábrica `pantalla_profesionales` (que devolvía la vieja pantalla) se
borra — ya no tiene otro consumidor fuera de `gui_main.py`.

`gui_main.py`: se sacan las `Seccion` "Profesionales" (la vieja, sobre la
fábrica) y "Profesiones"; se suma una sola "Profesionales" sobre
`PantallaProfesionales(conn)`.

Tests: `test_profesionales.py` renombra sus llamadas a `_PanelProfesionales`
y reescribe el único test estructural que asumía un `QTabWidget`/
`QScrollArea` propios del `PantallaCRUD` interno (ahora anidado, sin
esos dos). `test_gui_profesionales_formulario.py` (nuevo) cubre el
formulario compuesto (título, orden de solapas, tipo/objectName de cada
panel, `anidado is True` en la solapa de Profesiones).

### Reservas y Pagos (solo renombre de solapas) + Liquidaciones (+ Fechas especiales)

Cuarto merge de "Operativa diaria" según el Excel de la clienta, con dos
renombres puntuales de paso (sin ningún otro cambio estructural en esas
dos pantallas) y un merge real en Liquidaciones:

- **Reservas** (`reservas.py`): las dos solapas pasan de "Regulares"/
  "Aisladas" a "Reservas regulares"/"Reservas aisladas" — la pantalla
  sigue siendo la misma `PantallaReservas`, sin ningún otro cambio.
- **Pagos** (`pagos.py`): la solapa "Registrar pago" pasa a "Registrar
  pagos" — mismo criterio, solo texto de la pestaña (el botón interno
  sigue diciendo "Registrar pago", eso no cambió).
- **Liquidaciones** (antes "Liquidación mensual", `liquidacion.py`): pasa
  a formulario de tres solapas, sumando el catálogo "Fechas especiales"
  (antes pantalla propia del menú, categoría "Catálogos") como tercera
  solapa "Feriados y fechas especiales" — están relacionados porque los
  feriados/no laborables afectan el cálculo de la liquidación. Mismo
  mecanismo `anidado=True` de siempre: `catalogos.pantalla_fechas_
  especiales` suma su propio parámetro `anidado` (default `False`,
  reenviado a `PantallaCRUD`). El título Nivel 1 de `ProcesoLiquidacion`
  pasa de "Proceso de liquidación mensual" a "Liquidaciones" — mismo
  criterio que el resto de los merges de esta reorganización (el título
  pasa a ser el nombre nuevo del formulario), salvo Panel de control,
  que es un caso especial documentado aparte. `gui_main.py`: se renombra
  la `Seccion` "Liquidación mensual" a "Liquidaciones" (con la ayuda
  actualizada mencionando las tres solapas) y se saca la `Seccion`
  propia "Fechas especiales" — el catálogo "Placas" de esa misma
  categoría no se tocó, es un merge aparte (pasa a ser la tercera solapa
  de "Placas para timbres", todavía pendiente).

Tests: `test_gui_reservas.py`/`test_gui_pagos.py` no tenían ningún
assert sobre el texto de esas solapas, así que no hizo falta tocarlos.
`test_gui_liquidacion.py` suma cuatro tests: el objectName
`panelSolapa` de la solapa nueva (junto a los dos que ya existían para
Emisión/Estado de cuenta), el título Nivel 1 ("LIQUIDACIONES"), el
orden de las tres solapas, y que la solapa de Fechas especiales es un
`PantallaCRUD` anidado de verdad (sin título propio, con `campo_buscar`
armado) — mismo criterio que los tests de Base datos del espacio.

### Registro de ausencias (+ Tipos de licencia)

Quinto merge de "Operativa diaria": suma el catálogo "Tipos de licencia"
(antes pantalla propia del menú, categoría "Catálogos") como cuarta
solapa de "Registro de ausencias", intercalada entre "Licencias" y
"Ausencias" — están relacionados porque Licencias lee ese catálogo para
el combo de tipo. De paso, la solapa "Ausencias" se renombra "Ausencias
por motivos varios" (pedido del Excel de la clienta, más descriptivo
para no confundirla con el nombre genérico de la pantalla).

Mecánicamente el mismo patrón `anidado=True` de siempre:
`catalogos.pantalla_tipos_licencia` suma su propio parámetro `anidado`
(default `False`, sin efecto para quien ya la llamaba sin ese
argumento) que reenvía a `PantallaCRUD`. `PantallaRegistroAusencias`
(`app/gui/pantallas/novedades.py`) no cambia de forma — sigue siendo el
mismo contenedor título+`QTabWidget` de siempre — solo suma
`self.panel_tipos_licencia = catalogos.pantalla_tipos_licencia(conn,
anidado=True)` como tercera pestaña, importando `catalogos` cruzado
(sin ciclo: `catalogos.py` no importa `novedades.py`).

`gui_main.py`: se saca la `Seccion` propia "Tipos de licencia" y se
actualiza la ayuda de "Registro de ausencias" para mencionar las cuatro
solapas. `PantallaCargosEspeciales` (misma pantalla vieja, en el mismo
archivo) no se tocó en este merge — su combinación con Llaves queda
para el próximo.

Tests: `test_gui_novedades.py` suma dos tests (orden de las cuatro
solapas; la de Tipos de licencia es un `PantallaCRUD` anidado de
verdad, sin título propio, con `campo_buscar` armado) — mismo criterio
que Liquidaciones/Base datos del espacio. No hizo falta tocar ningún
test existente: ninguno hacía `tabText`/`pestanas.count()` sobre
`PantallaRegistroAusencias` antes de este merge.

### Llaves y otros conceptos (formulario nuevo, 3 solapas)

Sexto merge de "Operativa diaria": agrupa "Llaves" (antes pantalla propia
del menú, un único formulario con tres tablas apiladas) con las dos
solapas que ya tenía "Cargos especiales" (también pantalla propia del
menú) — ambas relacionadas porque un movimiento de llave (asignación/
devolución con depósito) genera automáticamente un cargo especial. Tres
solapas: "Movimientos y tenencias de llaves" (la vieja Llaves), "Registro
de cargos especiales" y "Estado de cuenta" (sin cambios, mismo orden que
ya tenían dentro de Cargos especiales).

Mecánicamente el mismo criterio que el resto de la reorganización, con
una variante nueva: acá NO se sumó ningún parámetro `anidado` (esta
pantalla no usa `PantallaCRUD`) — en su lugar, cada pieza se convirtió a
mano:

- `app/gui/pantallas/llaves.py`: `PantallaLlaves` pasa a `_PanelLlaves`
  (solapa desnuda, `objectName="panelSolapa"` en el widget de más
  afuera, sin título ni `QTabWidget` propio) — conserva su `QScrollArea`
  interno, mismo criterio que `_PanelGestorArchivos`/`_PanelCampos` para
  pantallas que ya scrolleaban así (el contenido de las tres tablas
  apiladas no entra siempre en el alto disponible).
- `app/gui/pantallas/novedades.py`: se borra el contenedor
  `PantallaCargosEspeciales` (título + `QTabWidget` propio) — sus dos
  paneles internos, `_PanelCargosEspeciales`/`_PanelEstadoCuentaCargos`,
  ya eran clases bare desde que se armó esa pantalla (mismo caso que
  `_PanelAumentos`/`_PanelEsquemaDescuentos` en su momento), así que no
  necesitaron ningún cambio propio — se importan cruzadas tal cual.
- `app/gui/pantallas/llaves_y_otros_conceptos.py` (nuevo): 
  `PantallaLlavesYOtrosConceptos`, mismo patrón que el resto — título
  Nivel 1 fijo + `QTabWidget` con las tres solapas importadas cruzadas.

`gui_main.py`: se sacan las `Seccion` "Llaves" y "Cargos especiales"; se
suma una sola "Llaves y otros conceptos".

Tests: `test_gui_llaves.py` renombra la clase (`_PanelLlaves`) en sus ~38
usos y reemplaza el único test estructural que asumía un `QTabWidget`
propio de una sola pestaña "Llaves" por uno de `objectName="panelSolapa"`
(mismo criterio que Bloques rígidos/Importación). `test_gui_novedades.py`
(que ya cubría Cargos especiales, al vivir en el mismo archivo fuente)
reemplaza sus ~26 instanciaciones de `PantallaCargosEspeciales(conn)` por
`_PanelCargosEspeciales(conn)`/`_PanelEstadoCuentaCargos(conn)` directo,
sacando la indirección `pantalla.panel`/`pantalla.panel_estado_cuenta`; el
test que verificaba el orden de las dos solapas dentro del contenedor
viejo se saca de acá (perdió sentido, ya no hay contenedor) y su
verificación pasa al nuevo `test_gui_llaves_y_otros_conceptos.py`, que
cubre el formulario compuesto completo (título, orden de las tres
solapas, tipo/objectName de cada panel).

### Placas para timbres (formulario nuevo, 3 solapas, con Buscar/Imprimir compartiendo estado)

Séptimo merge de "Operativa diaria": renombra la pantalla operativa
"Placas" a "Placas para timbres", renombra sus dos solapas ("Buscar y
asignar placas" → "Búsqueda y asignación de placas", "Imprimir placas"
→ "Impresión de placas en papel") y suma el catálogo "Placas" (el
tablero de posiciones/nombre grabado, distinto de la pantalla operativa
aunque comparten nombre) como tercera solapa — caso no contemplado en
el Excel de la clienta, resuelto con ella: "como tercera solapa de
'Placas para timbres'".

Variante nueva sobre el patrón de conversión a solapa desnuda: acá las
dos solapas viejas (Buscar/Imprimir) SIGUEN viviendo en una sola clase
porque comparten estado real, no solo un archivo — "Agregar a
impresión" en Buscar carga `_cola_impresion`, que Imprimir lee y
consume. Separarlas en dos clases independientes hubiera significado
inventar un canal de comunicación entre ellas que no hacía falta.
Solución: `PantallaPlacas` pasa a `_PanelPlacasOperativas`
(`app/gui/pantallas/placas.py`) — deja de ser, ella misma, una pantalla
con título y `QTabWidget` propio, pasa a ser un contenedor de lógica
compartida que expone `panel_buscar`/`panel_imprimir` (dos `QWidget`
que YA se construían por separado, en `_armar_panel_buscar`/
`_armar_panel_imprimir`) para que el formulario contenedor los sume
como dos solapas propias, hermanas del catálogo. El reinicio de
filtros al reingresar a la solapa de Buscar (antes en el `showEvent`
de la pantalla completa) pasa a `_PanelBuscarPlacas`, una subclase
mínima de `QWidget` solo para poder engancharle ese `showEvent` — un
`QWidget()` liso no admite pisarle el método de instancia porque Qt
resuelve `showEvent` por la clase, no por atributo.

`app/gui/pantallas/placas_para_timbres.py` (nuevo): `PantallaPlacasParaTimbres`,
mismo patrón que el resto — título Nivel 1 fijo + `QTabWidget` con las
tres solapas (`panel_operativas.panel_buscar`/`panel_operativas.
panel_imprimir`/`catalogos.pantalla_placas(conn, anidado=True)`, que
suma su propio parámetro `anidado`).

`gui_main.py`: se renombra la `Seccion` "Placas" (pantalla operativa) a
"Placas para timbres" sobre `PantallaPlacasParaTimbres`, con la ayuda
actualizada; se saca la `Seccion` propia del catálogo "Placas".

Tests: `test_gui_placas.py` renombra la clase (`_PanelPlacasOperativas`)
en sus ~30 usos; el test de título y el de "tiene dos solapas" se sacan
de acá (pasan al nuevo `test_gui_placas_para_timbres.py`); el de fondo
claro pasa a comprobar `pantalla.panel_buscar`/`pantalla.panel_imprimir`
directo (ya no hay un `QTabWidget` interno del que sacarlos con
`findChild`); los ~8 tests que mostraban la pantalla completa
(`pantalla.show()`/`waitExposed`) para medir geometría real pasan a
mostrar el panel puntual que corresponde (`pantalla.panel_buscar.show()`
o `pantalla.panel_imprimir.show()`), sacando el `findChild(QTabWidget).
setCurrentIndex(1)` que antes hacía falta para exponer la solapa de
Imprimir (ya no existe ese `QTabWidget` intermedio). `test_gui_placas_
para_timbres.py` (nuevo) cubre el formulario compuesto completo (título,
orden de las tres solapas, fondo claro de las dos operativas, catálogo
anidado sin título propio).

### Balance del negocio (formulario nuevo, 3 solapas — dos de informe en vivo, nunca existieron antes)

Octavo merge de "Operativa diaria", el único de toda la reorganización
que suma funcionalidad nueva de verdad (no solo reordena pantallas
existentes): "Gastos" es el catálogo Gastos operativos de siempre
(anidado, mismo mecanismo que el resto), pero "Ingresos" y "Resultado"
son informes 100% en vivo que no existían en ningún lado del sistema —
pedido explícito de la clienta al definir este formulario. Antes de
programarlos se le consultaron tres decisiones abiertas
(`AskUserQuestion`, ver también el docstring de `app.negocio.balance`):

- **Ingresos por horas regulares/aisladas, ¿neto o bruto?** Neto —
  mismo criterio "monto real facturado" que ya usa Estadísticas
  (descuento por volumen y recargo de aisladas ya aplicados). Reusa
  `app.negocio.estadisticas.monto_neto_regular_periodo`/`monto_neto_
  aislada_periodo` tal cual, sin duplicar el cálculo.
- **"Ingresos por reubicaciones por feriados": ¿a qué se refiere?**
  Aclarado por la clienta: no son las reubicaciones (que no facturan,
  compensan una ausencia). Es el cargo por "feriado trabajado" — un
  feriado no se cobra (se descuenta de la liquidación, se asume que el
  profesional no usa el espacio) salvo que decida usarlo, avisando
  cerca del momento; ese cargo puede caer en la liquidación del mes del
  feriado (si avisa antes de emitirla) o en la del mes siguiente (si
  avisa después) — "quiero que se contemple dentro de los ingresos en
  el período en el cual se carga en la liquidación, no importa la
  fecha del feriado". Esa resolución de período YA existe, tal cual
  descripta, en `app.negocio.liquidaciones._calcular_feriados_
  trabajados` (tabla `FeriadoTrabajado`, ya usada por Liquidaciones) —
  `app.negocio.balance.ingresos_feriados_trabajados_periodo` la reusa
  para todos los profesionales R del sistema en vez de reimplementarla,
  sumando el monto de cada item que efectivamente cae en el período
  pedido.
- **Alcance de ubicación**: mismos 4 niveles en cascada (Localidad/
  Edificio/Unidad/Consultorio, "el más específico manda") que ya usa
  Estadísticas Varias — confirmado. Esto generó un cruce con Gastos
  operativos, que tiene su propio Alcance de 3 niveles (Espacio
  general/Edificio/Unidad, sin Consultorio): consultado aparte,
  confirmó que al elegir cualquier filtro puntual de los 4, los gastos
  "Espacio general" quedan afuera del Resultado de ese lugar (no son
  atribuibles a uno puntual) — solo entran cuando los cuatro filtros
  están en su valor por defecto ("Todas"/"Todos", todo el espacio).
  `app.negocio.balance._alcance_gastos_del_filtro` traduce un alcance
  al otro.

Simplificación deliberada, documentada, misma que ya tenía `monto_neto_
regular_periodo`: el descuento por volumen de horas semanales se aplica
siempre, sin replicar la suspensión por saldo atrasado (`pierde_
descuento`) de una liquidación puntual — es un informe agregado, no una
liquidación.

`app/negocio/balance.py` (nuevo): `total_ingresos_periodo` (regulares +
aisladas + feriados trabajados, cada uno por separado), `total_gastos_
periodo` (con el cruce de alcance de arriba) y `resultado_periodo`
(ingresos - gastos), todo parametrizado por período y por el alcance de
ubicación de 4 niveles.

`app/gui/pantallas/balance.py` (nuevo): `PantallaBalanceDelNegocio`
(título Nivel 1 + `QTabWidget` con las tres solapas, en el orden
Gastos/Ingresos/Resultado — el catálogo ya existente primero, las dos
nuevas después). `_PanelIngresos`/`_PanelResultado`: cada uno arma su
propio panel de filtros (Período — arranca en el actual, cambiable,
mismo criterio que Gastos operativos — más la cascada de ubicación,
mismo código que `_PanelEstadisticasVarias` de Estadísticas, duplicado
acá como el resto de las pantallas del sistema que arman su propia
cadena de filtros — `_PanelFiltrosMixin` solo evita duplicar ESE
cableado entre los dos paneles nuevos, no es una clase base de verdad)
y muestra el resultado en un cuadro de etiquetas (`app.gui.widgets.
resumen_saldo.fmt_dato`, el mismo helper compartido que ya usan las
solapas "Estado de cuenta" de Pagos/Liquidaciones/Cargos especiales
para "rojo si es negativo").

`catalogos.pantalla_gastos_operativos` suma su propio parámetro
`anidado` (default `False`, reenviado a `PantallaCRUD`, mismo mecanismo
que el resto de los catálogos). `gui_main.py`: se saca la `Seccion`
propia "Gastos operativos" y se suma "Balance del negocio".

Tests: `tests/test_balance.py` (nuevo) cubre la lógica de negocio (suma
de los tres componentes de ingresos, traslado del feriado trabajado al
período siguiente cuando se avisa tarde, filtro por consultorio,
inclusión/exclusión de gastos generales según haya o no un filtro
puntual, resultado = ingresos - gastos). `tests/test_gui_balance.py`
(nuevo) cubre el formulario compuesto (título, orden de las tres
solapas, catálogo anidado sin título propio, fondo claro de los tres
paneles, valores por defecto de los filtros, recálculo al cambiar
período, coloreado rojo de gastos/resultado).

### Renombre final de categorías: Sistema / Operativa diaria

Con Balance del negocio, las doce pantallas de "Operativa diaria" con
cambio de código quedaron completas. Último paso del reordenamiento de
formularios: las tres categorías viejas del menú ("Principal"/
"Catálogos"/"Configuración") pasan a solo dos, "Sistema"/"Operativa
diaria", en todas las `Seccion` de `gui_main.py`.

`VentanaPrincipal` arma un separador de categoría cada vez que cambia
respecto de la `Seccion` anterior en la lista (no agrupa por nombre
repetido en toda la lista) — así que hizo falta REORDENAR la lista, no
solo cambiar el string de `categoria`, para que las cinco de "Sistema"
queden todas juntas y las doce de "Operativa diaria" también, sin
intercalarse (si no, el menú mostraría el separador "SISTEMA" varias
veces salteado). Dentro de cada bloque se conservó el orden relativo
que ya tenían entre sí las Secciones (no hay un orden pedido por la
clienta para este paso final, es criterio propio):

- **Sistema** (5): Panel de control, Archivos y listas, Base datos del
  espacio, Configuración general, Usuarios y permisos.
- **Operativa diaria** (12): Grilla y mensajería, Reservas,
  Liquidaciones, Llaves y otros conceptos, Placas para timbres,
  Disponibilidad, Registro de ausencias, Pagos, Estadísticas, Valores,
  Profesionales, Balance del negocio.

Test nuevo en `test_gui_main.py`: confirma que las categorías de
`construir_secciones()` son exactamente esas dos y que hay un solo
cambio de categoría en toda la lista (es decir, que van contiguas).

### Panel de control: primer alerta solo profesionales que reservan regular

Pedido de la clienta (repaso de pendientes abiertos, Excel de la
reorganización): "que el primer alerta sea los que deben por fuera del
rango de tolerancia a ese momento ordenado de por código, solo los
profesionales que reservan regular." La primera alerta ("Deuda mes
anterior — profesionales regulares") ya se mostraba primera (el orden
lo define `_TITULOS_ALERTA` en `app/gui/pantallas/panel_control.py`,
dict con "deuda_regulares" como primera clave — sin cambios ahí), pero
antes de este pedido incluía a CUALQUIER profesional categoría R con
saldo fuera de tolerancia, sin importar si hoy tiene alguna reserva
regular vigente, y sin ningún orden particular.

`app.negocio.panel_control._deuda_regulares` (la que también alimenta
el cuadrito "Profesionales" — "con saldo fuera de tolerancia", que
suma regulares + aisladas) se dejó SIN CAMBIOS a propósito, para no
alterar sin que se pidiera un cálculo de otra parte del panel. En su
lugar se sumó `_deuda_regulares_alerta` (más `_reserva_regular_activa`,
helper chico compartido), exclusiva para esta alerta: parte de la
misma lista de `_deuda_regulares` pero además exige una `ReservaRegular`
vigente hoy, y ordena el resultado por `Profesional.IdCodigo`.
`calcular_alertas` pasa a usar `_deuda_regulares_alerta` en vez de
`_deuda_regulares` para el campo `Alertas.deuda_regulares`.

### Menú lateral: ítem seleccionado en blanco y negrita; fantasma en alertas de Panel de control

Dos ajustes puntuales pedidos por la clienta al revisar capturas del
menú ya reordenado (Sistema/Operativa diaria):

- **Ítem de menú seleccionado**: el fondo bordó (`COLOR_DIA_GRILLA`) del
  ítem activo en el menú ya estaba bien, pero el texto no tenía un
  `color` propio en `::item:selected` — Qt caía al `HighlightedText` de
  la paleta global (pensada para la selección de filas de tabla en todo
  el sistema, no para esto), que en modo claro es casi negro y quedaba
  de bajo contraste contra el bordó. `QListWidget#navegacion::item:
  selected` (`estilos.py`) suma `color: {COLOR_TEXTO_CLARO}; font-
  weight: bold;` — mismo fondo bordó de siempre, texto blanco y
  negrita.
- **Alerta "fantasma" en Panel de control**: al revisar una captura de
  la tarjeta de alertas, se veía una segunda copia parcial (naranja sin
  texto + una sola línea suelta) debajo de la tarjeta real. Causa real,
  no un artefacto de la captura: `_refrescar_alertas` sacaba la tarjeta
  vieja del layout con `takeAt(0)` y la mandaba a `deleteLater()`, pero
  `takeAt` por sí solo NO oculta el widget — sigue siendo hijo visible
  en su última posición hasta que el event loop procesa el borrado
  diferido de `deleteLater`. Cualquier refresco encadenado (`showEvent`
  + el de la construcción inicial, por ejemplo) podía dejar la tarjeta
  vieja pintada un instante de más, superpuesta o debajo de la nueva.
  Se corrigió sumando `item.widget().hide()` antes de `deleteLater()`
  en ese mismo lugar — oculta al toque, sin depender de cuándo el
  event loop procese el borrado real. Test de regresión: guarda una
  referencia a la tarjeta antes de un segundo `actualizar()` y confirma
  `tarjeta_vieja.isHidden()` después.

### Separadores de categoría del menú en negrita con fondo azul oscuro; alerta de deuda regular mira el mes en curso

Dos ajustes puntuales más, pedidos por la clienta al revisar el menú ya
reordenado:

- **Separadores "— SISTEMA —"/"— OPERATIVA DIARIA —"**: quedaban con el
  mismo fondo azul (`COLOR_NIVEL_1`) y peso normal que cualquier ítem
  del menú, sin distinguirse como encabezados de grupo. Como estos
  ítems ya se arman con `Qt.ItemFlag.NoItemFlags` (deshabilitados, no
  seleccionables — `app/gui/main_window.py`), alcanzó con sumar
  `QListWidget#navegacion::item:disabled` en `estilos.py` (negrita +
  `COLOR_NIVEL_1_OSCURO`, el mismo azul más oscuro que ya usan los
  encabezados de columna de tabla) — no hizo falta tocar el código que
  arma el menú.
- **Alerta "Deuda mes anterior — profesionales regulares" (ahora "Deuda
  mes en curso...")**: la clienta aclaró que esta alerta puntual tiene
  que mirar el saldo de lo liquidado en el mes EN CURSO, no el
  arrastrado de meses anteriores. `_deuda_regulares_alerta` (`app.
  negocio.panel_control`) pasa a filtrar por `Profesional.
  SaldoCuentaActual` (lo que `avance_mes.avanzar_mes` resetea a 0 al
  arrancar un mes, `liquidaciones.emitir_liquidacion` va sumando y
  `pagos.registrar_pago` va restando durante el mes) en vez de
  `SaldoCuentaAnterior` — sin tocar `_deuda_regulares` (la función base,
  sigue con `SaldoCuentaAnterior`, sigue alimentando sin cambios el
  cuadrito "Profesionales: con saldo fuera de tolerancia"), aclarado
  explícitamente por la clienta como algo puntual "en esta sección al
  menos". El título de la alerta pasa de "Deuda mes anterior" a "Deuda
  mes en curso" (quedaba engañoso mantener el nombre viejo mostrando el
  dato nuevo) y la etiqueta de cada fila pasa de "saldo anterior" a
  "saldo actual" (mismo nombre que usan las solapas "Estado de cuenta"
  de Pagos/Liquidaciones/Cargos especiales para `SaldoCuentaActual`,
  vía `app.gui.widgets.resumen_saldo.fmt_dato`). La alerta de deuda de
  profesionales de reserva aislada ("Deuda mes anterior — profesionales
  de reserva aislada") no se tocó — sigue siendo sobre
  `SaldoCuentaAnterior`, no fue parte de este pedido.

### Panel izquierdo gris en vez de blanco (bug real, no solo la captura)

La clienta notó, mirando capturas de "Archivos y listas", que el panel
izquierdo (Buscar/Nuevo/Editar/Eliminar y cualquier `panel_extra_*`)
quedaba con un relleno más OSCURO que la solapa activa y que la tabla —
al revés de la regla ("Solapa ACTIVA: fondo CLARO... el panel de
contenido usa el mismo tono claro", ver "Jerarquía de títulos" más
arriba). Causa real, confirmada midiendo píxeles antes y después:

- `QWidget#panelSolapa { background-color: white; }` solo pinta blanco
  al widget que TIENE ese objectName puesto explícitamente — no
  "hereda" hacia sus hijos aunque el widget de más afuera sí lo tenga.
- El widget "panel izquierda" (Buscar+botones, armado en
  `crud_generico._armar_panel_izquierda_y_tabla`, reusado por TODOS los
  catálogos que pasan por `PantallaCRUD`) nunca tuvo ese objectName —
  solo el widget de MÁS afuera (`self` en modo `anidado`, o
  `panel_solapa` en modo estándar) lo tenía. Qt le pinta a ese panel
  izquierdo el gris por defecto de un `QWidget` sin estilo (visible
  contra el blanco de alrededor), mientras que la tabla se ve blanca
  aparte porque `QTableWidget` usa otro rol de paleta (`Base`) que sí es
  blanco por defecto — de ahí que solo el panel izquierdo se viera "más
  oscuro", nunca la tabla.
- En modo `anidado` había además un segundo widget sin ese objectName:
  `contenido` (el que se pasa a `scroll.setWidget(...)`, sin él en
  medio entre `self` y `panel_izquierda`) — en modo estándar ese
  equivalente (`panel_solapa`) SÍ lo tenía puesto desde siempre, así
  que ese modo estaba cubierto a medias.

Arreglo: `crud_generico.py` suma `panel_izquierda.setObjectName(
"panelSolapa")` en `_armar_panel_izquierda_y_tabla` (afecta a TODOS los
catálogos que pasan por acá, `anidado` o no) y `contenido.setObjectName(
"panelSolapa")` en el modo `anidado`. Como cualquier `panel_extra_
superior_izquierda`/`panel_extra_izquierda` (widgets propios de cada
catálogo, ej. "Período actual" de Gastos operativos) cuelgan DENTRO del
panel izquierda ya arreglado, quedaron blancos de rebote sin tocarlos
aparte — confirmado con Balance del negocio → Gastos.

Mismo bug, misma causa, encontrado también en `_PanelGestorArchivos`
(`app/gui/pantallas/imagenes.py`, armado a mano, no pasa por
`crud_generico.py`) — mismo arreglo aplicado ahí (`contenido`/
`panel_izquierda` propios de ese archivo suman `panelSolapa`).

Tests de regresión (cuentan cuántos `QWidget` descendientes tienen
`objectName() == "panelSolapa"`, ya que ninguno de los dos guarda
`panel_izquierda`/`contenido` como atributo propio): en
`test_crud_generico.py`,
`test_pantalla_crud_panel_izquierdo_tiene_fondo_blanco_no_gris` (modo
estándar) y `test_pantalla_crud_anidado_panel_izquierdo_tiene_fondo_
blanco` (modo `anidado`); en `test_gui_imagenes.py`,
`test_panel_izquierdo_tiene_fondo_blanco_no_gris`.

**Precisión sobre cuándo aparece de verdad** (surgió al revisar la
captura de "Bloques rígidos" dentro de Configuración general, y se
terminó de confirmar revisando Reservas/Llaves/Novedades a pedido de la
clienta): el bug NO afecta a cualquier panel armado a mano — depende de
si el widget que se pasa a `scroll.setWidget(...)` (`contenido`, en las
pantallas que envuelven su solapa en un `QScrollArea` propio) tiene o no
`objectName="panelSolapa"`:

- **Bloques rígidos**: arma su panel directo sobre `self` con un
  `QHBoxLayout`, sin ningún `QScrollArea` de por medio — no aplica este
  patrón, y confirmado en blanco sin tocar nada.
- **Novedades** (`_PanelVacaciones`/`_PanelLicencias`/`_PanelAusencias`):
  usa `QScrollArea`, pero `contenido` YA tenía `panelSolapa` puesto desde
  antes de esta revisión — confirmado en blanco sin tocar nada.
- **Reservas** (`_PanelReservasRegulares`/`_PanelReservasAisladas`) y
  **Llaves** (`_PanelLlaves`): usan `QScrollArea` y `contenido` NO tenía
  `panelSolapa` — bug real, confirmado por muestreo de píxeles (`#efefef`
  antes del arreglo, `#ffffff` después, en el panel de filtros/botones de
  cada una). Corregido sumando `contenido.setObjectName("panelSolapa")`
  en las tres construcciones (`reservas.py` ×2, `llaves.py`) — mismo
  criterio que `crud_generico.py`/`imagenes.py`, y sin necesidad de
  tocar los widgets nested más adentro (`panel_form`, los grupos de
  botones de Llaves, etc.): alcanza con que `contenido` lo tenga para
  que todo lo de adentro se vea blanco, la cascada ya la resuelve Qt en
  este caso puntual (a diferencia de `panel_izquierda` en
  `crud_generico.py`, que si necesitó su propio objectName aparte del de
  `contenido`/`panel_solapa`). Tests de regresión: mismo criterio de
  contar `QWidget` descendientes con `objectName() == "panelSolapa"`
  (`test_contenido_dentro_del_scroll_tiene_fondo_claro` en
  `test_gui_reservas.py`/`test_gui_llaves.py`).

De la lista original de pantallas con panel armado a mano, quedan
**Placas, Valores, Grilla operativa y Pagos** sin verificar todavía —
no usan `QScrollArea` para su panel principal (Placas sí lo usa, pero
solo para un cuadro de vista previa aparte), así que es esperable que ya
estén bien (mismo caso que Bloques rígidos), pero no se confirmó pantalla
por pantalla. Pedido explícito de la clienta: no hace falta un barrido
completo ahora — se sigue resolviendo a medida que se revisan. Si al
repasar alguna aparece el gris de más, el diagnóstico rápido es mirar si
`contenido` (el widget del `scroll.setWidget(...)`) tiene `panelSolapa`
puesto, y sumárselo si falta.

## Gestor de archivos: tipo "Enlace" (videos de YouTube, etc.)

Pedido de la clienta, ya con la reorganización de formularios en curso
("¿se puede agregar tipo de archivo Enlace? Es para ir guardando los
enlaces de videos de YouTube que voy creando, como recorrido de las
unidades o consultorios en particular. Esos enlaces una vez
identificados se los pego por WhatsApp al interesado"). Antes de
implementar se consultaron tres decisiones abiertas (`AskUserQuestion`):

- **Alcance**: "todos los niveles" — Espacio/Localidad/Edificio/Unidad/
  Consultorio, los mismos 5 que Imagen/Documento (no solo Unidad/
  Consultorio, el ejemplo puntual de la clienta).
- **Acciones en la lista** (en vez de "Descargar" + vista previa de
  archivo, que no aplican a un enlace): "Copiar enlace" nomás — se
  descartó sumar además "Abrir enlace" (no lo pidió).
- **Varios enlaces por categoría**: "sí, como con las imágenes" — mismo
  mecanismo de orden/"principal" que Imagen/Documento, no "el nuevo
  reemplaza al anterior".

Mecánicamente (`app.negocio.imagenes`): "Enlace" se suma a
`TIPOS_ARCHIVO` como tercer tipo, con su propia
`CATEGORIAS_ENLACE_POR_ALCANCE` (una categoría con nombre propio por
nivel — "Recorrido de la unidad"/"...del consultorio"/"...del
edificio"/"...de la localidad", "Video institucional" para Espacio —
más "Otros enlaces" al final de cada lista, mismo patrón "Otras
imágenes"/"Otros documentos" con etiqueta libre obligatoria). Nombrado
de categorías a criterio propio, igual que el agrupamiento de solapas
de Configuración general en su momento — fácil de renombrar si la
clienta prefiere otra cosa, es solo texto en un dict.

Un enlace no se distingue por extensión (no tiene) sino por el prefijo
`http://`/`https://` (`es_enlace`) — mismo criterio "sin columna propia
en la base" que ya usaban Imagen/Documento entre sí.
`Imagen.RutaArchivo` guarda la URL tal cual en vez de una ruta de
archivo. `agregar_enlace` (paralela a `agregar_imagen`, sin copiar nada
a disco ni validar extensión/tamaño) escribe la fila con el mismo
mecanismo de orden/categoría/principal de siempre.

Ojo con `pathlib.Path` sobre una URL: `_sincronizar_descripcion_y_
archivo`/`_intercambiar_orden` (las dos únicas funciones que antes
convertían `RutaArchivo` a `Path` para renombrar el archivo en disco)
ahora cortan camino cuando `es_enlace(RutaArchivo)` da `True` — sin ese
corte, pasar "https://youtu.be/xyz" por `Path(...)` colapsa el "//"
después de "https:" a un solo "/", corrompiendo el enlace guardado
(confirmado con un test dedicado, `test_agregar_enlace_guarda_la_url_
sin_corromperla`). `eliminar_imagen` no necesitó ningún cambio: ya
comprobaba `Path(...).is_file()` antes de intentar borrar el archivo,
que para una URL da `False` sin más.

GUI (`_PanelGestorArchivos`): el combo "Tipo de archivo" no abre ningún
`QFileDialog` cuando está en "Enlace" — `_DialogoAgregarArchivo` suma un
parámetro `pedir_url` que agrega un campo de URL arriba de Categoría (se
pide ahí mismo, validada contra `es_enlace` antes de aceptar). El botón
"Descargar" pasa a "Copiar enlace" (copia la URL al portapapeles,
`QApplication.clipboard()`, mismo criterio de test que ya usaba Reservas
para su propio "copiar al portapapeles") mientras el Tipo de archivo
elegido sea Enlace, y vuelve a "Descargar" para Imagen/Documento — un
solo botón, cambia de texto y de acción según el combo
(`_al_cambiar_tipo`/`_descargar_o_copiar`). La Vista previa, para un
enlace, muestra la URL como texto ("Enlace:\n{url}") en vez de intentar
renderizar nada.

## Usuarios y permisos: tercer nivel "Supervisor general"

Pedido de la clienta, ya con la reorganización de formularios cerrada:
"¿Se puede agregar una categoría más de usuario? 'Supervisor general',
estaría por encima de las otras dos. No me imagino usarlo en lo
inmediato, pero prefiero preverlo por si acaso." Sin caso de uso
concreto todavía — puro future-proofing, a diferencia del resto de
`NivelAcceso` (Administrador/Operador), que sí tienen pantallas
puntuales atadas (`PermisoPantalla`).

Mecánicamente es "un catálogo más" (`app.negocio.seguridad` ya lo
documenta así: "se puede sumar otro nivel más adelante sin tocar nada
de la lógica de comparación, que solo mira `Orden`"): `app.db.seed.
sembrar_niveles_acceso` pasa a sembrar tres filas en vez de dos
(Supervisor general=1000, Administrador=100, Operador=10) para una base
NUEVA; `app.db.migraciones._agregar_nivel_supervisor_general` (llamada
al final de `aplicar_migraciones`) suma la fila que falta a una base YA
sembrada (Administrador/Operador cargados desde antes de este pedido) —
se saltea sin hacer nada si `NivelAcceso` todavía está completamente
vacía (base nueva, sin sembrar todavía): si insertara ahí, la tabla
dejaría de estar vacía y `sembrar_niveles_acceso` (que solo siembra si
está vacía) nunca llegaría a cargar Administrador/Operador en una base
nueva — el orden real de arranque (`app.db.init_db.init_database`) crea
las tablas y corre las migraciones ANTES de que nada llame a la siembra.

**El pedido en sí no tocó ninguna lógica de negocio** (no hay ninguna
pantalla ni comportamiento nuevo atado a "Supervisor general" más que
poder asignárselo a un usuario desde "Usuarios y permisos" y que las
pantallas que hoy nacen en Administrador — Configuración general,
Usuarios y permisos — sigan siendo accesibles para él, vía
`nivel_alcanza`'s `Orden >=`). Lo que sí generó trabajo real fue
revisar, uno por uno, todos los lugares del código que hasta ahora
resolvían "el nivel administrativo" como "el nivel más alto del
catálogo" (`ORDER BY Orden DESC LIMIT 1` / `max(niveles, key=Orden)`) en
vez de por el NOMBRE "Administrador" — con un tercer nivel por encima,
esa resolución deja de apuntar a Administrador y apunta a Supervisor
general, rompiendo en silencio la intención original de cada uno de
esos lugares. Antes de tocar nada se le planteó el riesgo del primero de
estos casos (el guardarraíl de "no dejar el sistema sin Administrador")
a la clienta vía `AskUserQuestion`, con dos opciones; eligió la
recomendada: "Sí, proteger siempre a Administrador o superior — nunca
se puede dejar el sistema sin al menos un usuario activo Administrador o
Supervisor general, exactamente el comportamiento actual, con Supervisor
general ya incluido a futuro." Los otros dos casos (encontrados después,
al revisar sistemáticamente todo el código que tocaba `NivelAcceso`) se
resolvieron con el mismo criterio, sin volver a consultar por ser
variaciones mecánicas de la misma decisión ya tomada:

- **`app.gui.pantallas.usuarios._editar`** (el guardarraíl en sí, el caso
  que motivó la pregunta): `nivel_admin = max(niveles, key=lambda n:
  n["Orden"])` pasa a `next(n for n in niveles if n["Nombre"] ==
  "Administrador")`, y la comparación de "¿deja de ser administrador
  activo?" pasa de comparar `IdNivelAcceso` exacto a comparar `Orden` vía
  un helper `_alcanza_admin(id_nivel)` (`Orden >= Orden de Administrador`)
  — así un Supervisor general activo también cuenta como "alguien que
  puede administrar" a los efectos de esta protección, sin que haga
  falta que sea "exactamente" Administrador.
- **`app.negocio.seguridad.hay_otro_usuario_activo_de_nivel`**: mismo
  cambio, del lado de la consulta SQL — pasa de `WHERE IdNivelAcceso = ?`
  a un `JOIN` que compara `Orden >= Orden de referencia` entre el nivel
  del usuario candidato y el nivel pedido. Sin este cambio, un Supervisor
  general activo NO "sería" Administrador (comparación exacta) y el
  guardarraíl bloquearía sin necesidad la baja del único Administrador
  aunque el sistema siguiera teniendo quien lo administre.
- **`app.negocio.seguridad.asegurar_permisos_pantalla`** (detectado
  después, revisando sistemáticamente el resto de los usos de
  `NivelAcceso` — no parte de la pregunta original a la clienta): el
  `nivel_alto` que reciben las pantallas sensibles (Configuración
  general, Usuarios y permisos) pasa de `ORDER BY Orden DESC LIMIT 1` a
  `WHERE Nombre = 'Administrador'` (con el `ORDER BY` viejo como
  respaldo si por algún motivo esa fila no existiera). Sin este cambio,
  una pantalla sensible NUEVA en una base recién creada (los tres
  niveles se siembran juntos) nacería exigiendo Supervisor general en
  vez de Administrador — dejando afuera a cualquier Administrador, al
  revés de la intención original ("Administrador" está en el docstring
  de la función desde antes de este pedido).
- **`app.gui.dialogos_seguridad.DialogoLogin._crear_administrador`**
  (mismo criterio, mismo motivo de detección): el primer usuario de una
  base nueva (alta inicial, sin usuarios cargados todavía) pasa de
  `ORDER BY Orden DESC LIMIT 1` a `WHERE Nombre = 'Administrador'` (con
  el mismo respaldo). El método se llama literalmente
  `_crear_administrador` — la intención siempre fue esa, nunca "dale el
  nivel más alto que exista"; un test ya existente
  (`test_alta_inicial_crea_administrador_y_autentica`) fijaba ese
  comportamiento desde antes de este pedido y hubiera empezado a fallar
  sin este cambio. Promover a alguien a Supervisor general sigue siendo
  posible, pero es una decisión aparte, tomada después, desde "Usuarios
  y permisos" — no algo que deba pasar en el alta inicial solo porque
  ese nivel ya existe en el catálogo.

Tests nuevos: `tests/test_seguridad.py` (siembra de tres niveles,
`hay_otro_usuario_activo_de_nivel` con un Supervisor general activo
alcanzando para Administrador y con un Operador activo sin alcanzar,
`asegurar_permisos_pantalla` con nivel_alto resolviendo a Administrador
habiendo Supervisor general en el catálogo — comentado explícitamente
como test de regresión); `tests/test_gui_usuarios.py` (no se puede
desactivar al único Administrador activo aun habiendo el nivel
Supervisor general en el catálogo si nadie lo ocupa; sí se puede si hay
un Supervisor general activo); `tests/test_gui_dialogos_seguridad.py`
(alta inicial sigue creando Administrador con Supervisor general ya
sembrado); `tests/test_migraciones.py` (una base nueva no recibe
Supervisor general vía migración, solo vía seed; una base ya sembrada
sí lo recibe vía migración; idempotencia; base sin la tabla NivelAcceso
no rompe).

## Centro de mensajería: Vista previa estirada hasta el borde de la tabla

Pedido puntual de la clienta al revisar la pantalla "Grilla y
mensajería": el cuadro de Vista previa (`self.texto_mensaje`) tenía un
alto fijo (220px) seguido de un `columna.addStretch()` que dejaba un
espacio en blanco sin usar entre el final del cuadro y el borde inferior
del panel izquierdo. Se saca el alto fijo y el `addStretch()` final, y
`self.texto_mensaje` se agrega con `stretch=1` — así ocupa todo el alto
que le sobra a la columna, quedando su borde inferior a la misma altura
que el de la tabla de la derecha (ambas dentro del mismo `QHBoxLayout`
de la solapa, que ya reparte el mismo alto a los dos).

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

## Liquidaciones: cuarta solapa "Liquidaciones simuladas"

Pedido de la clienta, ya con las cuatro solapas de "Liquidaciones"
armadas y la revisión "uno por uno" de Reservas cerrada: "quisiera al
margen agregar una cuarta solapa... el sentido es crear un archivo
simulando una liquidación para que un profesional vea cómo se manda el
archivo y cuánto le saldría un período determinado a modo de ejemplo".
El caso de uso es mostrarle a un profesional que todavía NO tiene
ninguna reserva real cargada cuánto le saldría reservar ciertos
bloques, antes de darlos de alta de verdad.

Tres decisiones explícitas de la clienta acotaron el alcance desde el
pedido original, sin necesidad de `AskUserQuestion` (ya venían resueltas
en su mensaje):

- **Ignora la ocupación real por completo**: "el sistema ignora si el
  consultorio está ocupado o reservado por otro profesional, no importa
  eso" — nunca lee `ReservaRegular` ni ninguna tabla de ocupación, es
  simulación pura sobre los bloques que el operador tipea a mano.
- **Sí contempla feriados y fechas especiales**: "si cae algo de eso lo
  descuenta" — mismos porcentajes que la liquidación real
  (`Configuracion.PorcentajeDescuentoFeriado`/`PorcentajeDescuentoNoLaborable`).
- **Nada de conceptos especiales**: "no se cargan conceptos especiales
  como llaves y cosas así, es solo para apreciar cuánto daría una
  reserva" — sin saldo anterior, vacaciones, licencias, ausencias,
  cargos especiales, feriados trabajados ni reubicaciones. Deliberamente
  mucho más simple que `app.negocio.liquidaciones` (907 líneas de
  cascada secuencial) — se armó una lógica nueva e independiente en vez
  de reusar/parametrizar esa, para no acoplar algo tan simple a los
  internos de un cálculo mucho más complejo.

### Cálculo (`app/negocio/liquidacion_simulada.py`)

`BloqueSimulado` (día/horario/consultorio, sin persistir en ninguna
tabla — vive solo en memoria mientras se arma la simulación) +
`calcular_liquidacion_simulada(conn, *, id_profesional, periodo,
bloques)`, que devuelve `LiquidacionSimulada` (bruto, horas semanales,
% de descuento por volumen, lista de `ItemFeriadoSimulado`, con
`neto`/`total_descuento_feriados` como propiedades calculadas). El
bruto se calcula recorriendo el período día por día y sumando, para
cada día, los bloques cuyo `dia_semana` coincide — no hay "vigencia"
que vaya cambiando dentro del período como en una reserva real, los
bloques simulados valen para el período entero. El descuento por
volumen (`obtener_porcentaje_descuento`) se calcula una sola vez sobre
el total de horas semanales de todos los bloques juntos. Los feriados
del período (`feriados_relevantes_periodo`, ya excluye domingos) se
descuentan solo si algún bloque cae ese día de la semana, con los
mismos porcentajes por tipo que la liquidación real — reimplementados
en una función privada propia (`_porcentajes_tipo_fecha`) en vez de
importar la versión privada de `liquidaciones.py`, por el mismo motivo
de desacople de arriba.

### PDF (`app/pdf/liquidacion_simulada_pdf.py`)

Mucho más corto que el PDF de liquidación real: encabezado del espacio,
un párrafo en itálica aclarando "Documento de ejemplo... No representa
una liquidación real ni una reserva confirmada", la tabla "Bloques
simulados" (Día/Horario/Consultorio) y la tabla "Liquidación simulada"
(Bruto, Descuento por volumen, un renglón por cada feriado descontado,
Total simulado en negrita con línea arriba) — mismo estilo visual
(colores, tipografía) que el resto de los PDF del sistema.

Nombre de archivo pedido explícitamente por la clienta: `"{AAAA-MM} -
Liquidación simulada {Tratamiento} {Nombre} {Apellido}.pdf"` (el
"{yyyy-aa}" de su mensaje se interpretó como el mismo formato de
período `AAAA-MM` que usa todo el resto del sistema, confirmado
comparando contra el prefijo que ya arma `liquidacion_pdf.
nombre_archivo_liquidacion` para las liquidaciones reales) — sin el
sufijo de código que sí lleva el nombre de archivo real, no hace falta
desambiguar contra otro archivo del mismo profesional porque viven en
carpetas separadas.

### Carpeta y retención (`app/negocio/archivos_generados.py`)

Pedido explícito: "que se vayan conservando las liquidaciones de los
últimos 3 meses y que luego se vayan eliminando a través de un proceso
con el avance de mes". A diferencia de las liquidaciones reales (una
carpeta `Profesionales/{código}` por profesional, retención de 1 año),
acá es una única carpeta compartida `Liquidaciones simuladas` bajo la
carpeta base (`carpeta_liquidaciones_simuladas`) — son ejemplos
descartables, no hace falta separarlos por profesional ni conservarlos
tanto tiempo. `limpiar_liquidaciones_simuladas_antiguas` compara el
mismo prefijo `AAAA-MM` del nombre de archivo (mismo mecanismo que
`limpiar_liquidaciones_antiguas`, pero con retención en MESES en vez de
años) y se llama desde `avance_mes.avanzar_mes` junto con la limpieza de
liquidaciones reales.

### GUI: cuarta solapa de "Liquidaciones" (`app/gui/pantallas/liquidacion.py`)

`_PanelLiquidacionesSimuladas`, mismo criterio de "controles y botones a
la izquierda" que el resto del sistema (pedido explícito de la clienta
para esta pantalla nueva, "fijate cómo se te ocurre armarlo, siempre con
los controles y los botones a la izquierda con los estilos que venimos
manejando"):

- **Columna izquierda** (ancho máximo `_ANCHO_PANEL_FILTROS`, mismo
  valor que "Emisión de archivos"): Profesional (combo buscable, solo
  categoría R, mismo criterio que las otras tres solapas), Período a
  simular (`QLineEdit` con el mismo formato libre `AAAA-MM` que "Emisión
  de archivos" — por defecto `sumar_meses(periodo_actual(conn), 1)`, "el
  mes siguiente al actual", pedido explícito de la clienta), línea
  divisoria, la cascada Localidad→Edificio→Unidad→Consultorio (importada
  cruzada de `reservas.py` — `_opciones_localidad`/`_opciones_edificio`/
  `_recargar_unidades`/`_recargar_consultorios`, mismo criterio de
  import cruzado de símbolos privados que ya usa esta pantalla para
  `_opciones_profesional`/`_texto_profesional`/`_numero_codigo`), Día
  (combo con `_DIAS_RESERVA`, Lunes a Sábado) y horario Desde/Hasta
  (`_SpinHorario`, también importado cruzado), "Agregar bloque"/"Quitar
  bloque" (`botonSecundario`, deshabilitado sin selección en la tabla de
  bloques), línea divisoria, "Generar liquidación simulada"
  (`botonPrimario` — la única acción que efectivamente escribe algo, un
  PDF). Los tres botones comparten un mismo ancho fijo
  (`_ANCHO_BOTON_SIMULADA`).
- **Columna derecha**: "Bloques cargados" (tabla Día/Horario/Consultorio,
  se arma en memoria con una lista de `BloqueSimulado`, sin persistir
  nada — "Consultorio" reusa `_lugar_bloque`, importado cruzado del
  propio módulo del PDF, para no duplicar esa consulta) y, debajo,
  "Resultado de la última simulación generada" (tabla Concepto/Monto,
  mismas filas que arma el PDF — Bruto, Descuento por volumen, un
  renglón por feriado descontado, Total simulado — con `item_monto`, el
  mismo helper compartido de "Estado de cuenta" que colorea en rojo los
  montos negativos).

"Agregar bloque" valida que haya un consultorio elegido y que el
horario "hasta" sea posterior al "desde" antes de sumar el bloque (con
un `QMessageBox.warning` si no); "Generar" valida profesional, período y
que haya al menos un bloque cargado, y atrapa el `ValueError` de
`calcular_liquidacion_simulada`/`generar_pdf_liquidacion_simulada`
mostrándolo en un cartel en vez de romper. No hay ningún guardado en la
base — cerrar y volver a entrar a la solapa pierde los bloques cargados,
comportamiento aceptado porque es una herramienta de "armar y generar en
el momento", no un registro que haya que conservar entre sesiones.

### Segunda vuelta: desglose por bloque y "Total general"

Pedido de la clienta al ver la primera captura de esta solapa nueva,
con tres cambios sobre las dos tablas de la derecha:

- **"Bloques cargados" con más columnas**: pasa de 3 columnas (Día/
  Horario/Consultorio, este último un texto armado con
  `_lugar_bloque` del módulo del PDF) a 8: N° Bloque, Día, Horario
  desde, Horario hasta (separado en dos columnas, cada una con
  `_fmt_hora` de `reservas.py`, mismo formato "9:00" que ya usan los
  `_SpinHorario` de esta misma pantalla) y Localidad/Edificio/Unidad/
  Consultorio por separado — `_ubicacion_bloque` (nueva, en
  `liquidacion.py`) hace el mismo JOIN Consultorio→Unidad→Edificio→
  Localidad que ya usa `_opciones_localidad` de `reservas.py`, con el
  mismo "(Sin localidad)" cuando el edificio no tiene una cargada. Deja
  de importarse `_lugar_bloque` acá (queda como uso interno del PDF
  nomás, no se borra de ese módulo).
- **La tabla de resultado se renombra "Subtotal por bloque"**: en vez de
  una fila por concepto (Bruto/Descuento por volumen/cada feriado/
  Total), ahora es una fila POR BLOQUE cargado — columnas N° Bloque,
  Cantidad horas semanales, Cantidad horas mensuales, Importe Bruto, %
  Descuento, Descuento, Importe Neto — más una fila de Total al final,
  resaltada con el mismo naranja suave que ya usa toda la aplicación
  para la fila seleccionada de cualquier tabla (`resalte_seleccion` de
  `paleta()` en `estilos.py`, `"#F2C4A0"` — reusado tal cual, no un
  naranja nuevo, como `_COLOR_FILA_TOTAL` en `liquidacion.py`).
- **Tabla nueva "Total general"**: debajo de "Subtotal por bloque", una
  tabla con las mismas 7 columnas y una única fila ("Total general" en
  vez de un número de bloque) — mismos valores que la fila de Total ya
  resaltada arriba, pedida como tabla aparte en vez de (o además de)
  esa fila. `QTableWidgetItem.clone()` duplica cada celda de la fila de
  total ya armada (un `QTableWidgetItem` no puede pertenecer a dos
  tablas a la vez) antes de renombrar la primera celda.

Esto obligó a que `app.negocio.liquidacion_simulada.
calcular_liquidacion_simulada` calculara el desglose por bloque, no
solo el agregado: `SubtotalBloque` (una instancia por bloque, en el
mismo orden y numerados 1-based) con horas semanales/mensuales, bruto,
% de descuento (el mismo para todos los bloques — se calcula una sola
vez sobre el total de horas de TODOS los bloques juntos, como ya hacía
`descuento_horas_pct`) y `descuento`/`neto` YA propios de ese bloque.
Punto importante, no pedido explícitamente pero necesario para que los
números cierren: `descuento` de un bloque no es solo su parte del
descuento por volumen — también incluye cualquier feriado que caiga en
el día de la semana de ESE bloque en particular (a diferencia de
`descuentos_feriados`, la lista existente pensada para el PDF, que
agrupa por fecha sin importar a qué bloque corresponde). Sin este
reparto, sumar el `neto` de todos los `SubtotalBloque` no hubiera dado
exactamente el `neto` total de la liquidación cuando hay un feriado de
por medio.

El cálculo del bruto total se aprovechó para simplificarse de paso: en
vez de recorrer el período día por día sumando lo que le toca a cada
bloque ese día (el `while` original), ahora se calcula directamente
bloque por bloque — cuántas veces cae su día de la semana en el período
(`_cantidad_dias_semana_en_periodo`, nueva, mismo criterio que el
helper de test que ya existía en `test_liquidacion_simulada.py` con
otro nombre) × sus horas × el valor hora de su consultorio — y se suma.
Los dos caminos dan matemáticamente el mismo total (cada día solo le
suma a los bloques cuyo día de semana coincide, sin importar el orden
de la suma), confirmado porque los 9 tests que ya existían para
`calcular_liquidacion_simulada` siguieron pasando sin tocarlos.

### Tercera vuelta: se saca "Total general", más alto y ancho en las tablas

Pedido de la clienta sobre la captura de la segunda vuelta:

- **Se saca la tabla "Total general"**: "me había arrepentido" de
  pedirla — la fila de Total ya resaltada en naranja al final de
  "Subtotal por bloque" alcanza. Se borra `self.tabla_total_general`
  entera (widget, `QLabel` "Total general:" y el bloque que la llenaba
  clonando la fila de Total en `_mostrar_resultado`).
- **"Subtotal por bloque" pasa a llamarse "Totales por bloques y
  general"**: mismo widget (`self.tabla_subtotales`), solo cambia el
  texto del `QLabel` de arriba — sigue teniendo una fila por bloque más
  la fila de Total al final, eso no cambió.
- **Las dos tablas que quedan suben de alto**: `setMinimumHeight(
  _alto_para_filas(tabla, _FILAS_VISIBLES_SIMULADAS))` (8 filas,
  constante nueva) en vez de dejarlas al alto mínimo que les daba el
  layout — `_alto_para_filas`, importado cruzado de `llaves.py` (mismo
  criterio de import cruzado de un símbolo privado que ya usa esta
  pantalla para los helpers de `reservas.py`), calcula el alto justo
  para N filas sin scroll; acá se usa como PISO (`setMinimumHeight`, no
  `setFixedHeight`) para que sigan siendo scrolleables si hay más
  bloques de los que entran, pedido explícito de la clienta ("igualmente
  que sean escroleables"). Las dos tablas suman además `stretch=1` en
  `layout_derecha` para repartirse el alto sobrante de la columna
  derecha en partes iguales.
- **"Bloques cargados": más ancho donde hace falta**. Tres ajustes:
  - "Día" suma 30px de padding sobre lo que deja
    `resizeColumnsToContents()` (mismo valor y criterio que
    `_PADDING_COLUMNA` de `novedades.py`/`llaves.py`, aplicado acá a una
    sola columna en vez de a todas).
  - "Horario desde"/"Horario hasta" pasan de texto a la izquierda
    ("9:00") a `item_numero` (alineado a la derecha, mismo helper que
    importes/porcentajes) con sufijo "hs" al final ("9:00hs") — pedido
    explícito de la clienta sobre el formato.
  - Localidad/Edificio/Unidad/Consultorio (las últimas cuatro columnas)
    pasan a `QHeaderView.ResizeMode.Stretch` — "para aprovechar el
    ancho de la pantalla visible" en vez de quedarse angostas al ancho
    justo de su contenido, mismo criterio que ya usan Placas/Importar
    planilla para columnas parejas. `resizeColumnsToContents()` sigue
    llamándose en cada refresco de la tabla para las primeras cuatro
    columnas (N° Bloque/Día/Horario desde/Horario hasta); no afecta a
    las cuatro en modo Stretch.

### Cuarta vuelta: títulos de horas más cortos, importes también en Stretch

Dos ajustes más de la clienta sobre "Totales por bloques y general":

- **Títulos más cortos**: "Cantidad horas semanales"/"Cantidad horas
  mensuales" pasan a "Horas semanales"/"Horas mensuales" — cambio de
  texto nomás, mismo criterio que la vuelta que acortó "Horas aisladas
  mensuales" a "Cant. horas aisladas mensuales" en Reservas (ver esa
  sección más arriba): cuando un título de columna queda largo, se
  acorta sin tocar el dato que muestra.
- **Importe Bruto/Descuento/Importe Neto en Stretch**: mismo mecanismo
  y mismo pedido ("aprovechar el ancho visible de la pantalla") que las
  columnas de ubicación de "Bloques cargados" en la vuelta anterior —
  `header_subtotales.setSectionResizeMode(columna, QHeaderView.
  ResizeMode.Stretch)` en las columnas 3/5/6 (los tres importes; "%
  Descuento", columna 4, se queda en su ancho justo — no es un importe).
  `resizeColumnsToContents()` en `_mostrar_resultado` sigue ajustando
  las columnas 0/1/2 (N° Bloque/Horas semanales/Horas mensuales) sin
  afectar a las tres en Stretch.

## Cargos especiales y Centro de mensajería: se sacan sus "Deshacer..."

Pedido explícito de la clienta al ver las capturas de "Llaves y otros
conceptos" (solapa "Registro de cargos especiales") y de "Grilla y
mensajería" (solapa "Centro de mensajería"): sacar el botón "Deshacer
último movimiento"/"Deshacer última acción" de las dos — mismo criterio
ya aplicado antes en Llaves y en Reservas ("cubría cualquier alta/
edición/baja de esta pantalla, se sacó por completo a pedido explícito
porque no estaba en la lista final de botones que dio la clienta —
pérdida de funcionalidad real, no solo estética"). Acá también se borra
todo el código que solo existía para alimentar ese botón, no solo el
widget.

- **Cargos especiales** (`_PanelCargosEspeciales`, `app/gui/pantallas/
  novedades.py`): se borra el botón, su conexión
  (`clicked.connect(self._deshacer_ultimo)`) y el método `_deshacer_
  ultimo` entero, además de sacarlo de la cadena de foco Enter/Tab
  (pasa de Buscar→Tipo→Concepto→Monto→Período→Crear→Modificar→
  Eliminar→Deshacer a la misma cadena sin el último paso).
  `_bloqueado_por_llave` (el guardarraíl que impide tocar un cargo
  ligado a una llave) se queda intacto — sigue haciendo falta para
  Modificar/Eliminar, que no se tocaron.
- **Centro de mensajería** (`_PanelCentroMensajeria`, `app/gui/
  pantallas/mensajeria.py`): a diferencia de Llaves/Cargos especiales,
  acá "Deshacer última acción" no borraba un solo tipo de registro —
  revertía CUALQUIERA de cuatro acciones distintas (marcar/desmarcar
  "Enviada", generar el texto marrón de "mensaje previo" o el celeste
  de "mensaje aislada"), guardadas en un diccionario `self._ultima_
  accion` que se iba pisando en cada acción mutante. Sacar el botón por
  sí solo hubiera dejado ese diccionario (y todo lo que lo alimentaba)
  como código muerto, así que se borró todo junto: el atributo
  `_ultima_accion`, los cuatro lugares donde se lo pisaba
  (`_al_cambiar_enviada`/`_desmarcar_enviada`/`_marcar_como_enviada`/
  `_generar_y_mostrar`/`_texto_para_boton`) y los tres métodos que solo
  existían para leerlo (`_deshacer_ultima_accion`/`_deshacer_marcar_
  enviada`/`_revertir_bandera_mensajeria`). De paso se sacó el respaldo
  de PDF previo que hacía `_marcar_como_enviada` antes de generar el
  nuevo (leer a memoria el archivo viejo con ese nombre, si existía,
  para poder restaurarlo al deshacer) — sin la opción de deshacer, ese
  respaldo no tenía ningún otro consumidor, así que quedaba leyendo un
  archivo a memoria en cada marcado sin que nada lo usara después.
  Tests borrados en bloque (mismo criterio: eran pruebas de la
  funcionalidad que se retira, no de otra cosa): los ocho de la sección
  "deshacer última acción" al final de `test_gui_mensajeria.py`
  (sin acciones, marcar enviada con/sin PDF previo, restaurar saldo
  actual, violeta restaura plazo extendido, desmarcar enviada, generar
  texto marrón/aislada, y el de "generar texto sin mutación no deja
  nada para deshacer" — este último ya no tiene sentido sin el
  concepto de "última acción" a probar).

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

## Registro de ausencias: se saca "Deshacer último movimiento" de las
## tres solapas con alta/edición (Vacaciones, Licencias, Ausencias)

Pedido explícito de la clienta, mismo criterio ya aplicado antes en
Llaves, Reservas y Cargos especiales/Centro de mensajería: el botón
"Deshacer último movimiento" cubría cualquier alta/anulación de la
solapa (anulaba la última Vacación/Licencia/Ausencia cargada en todo el
sistema, sin importar el profesional del filtro), y se saca por
completo — no estaba en la lista final de botones que dio la clienta.
"Tipos de licencia" (la cuarta solapa, un catálogo `PantallaCRUD`
anidado) nunca tuvo este botón, no fue parte del pedido.

Se borra, en `_PanelVacaciones`/`_PanelLicencias`/`_PanelAusencias`
(`app/gui/pantallas/novedades.py`) — cada una con su propia
implementación, ninguna compartía estado con otro método salvo
`_cancelar_registro` (que Anular ya usa, se queda intacto): el widget
del botón, su conexión (`clicked.connect(self._deshacer_ultimo)`) y el
método `_deshacer_ultimo` entero. Ninguna de las tres tenía este botón
sumado a su cadena de foco Enter/Tab (`instalar_enter_avanza_foco`
termina en el botón "Crear..." de cada una), así que no hizo falta
tocar ningún `_foco`.

Tests borrados en bloque en `test_gui_novedades.py` (mismo criterio:
eran pruebas de la funcionalidad que se retira, no de otra cosa): los 9
de "deshacer_ultimo_movimiento_{vacaciones,licencia,ausencia}_
{sin_registros_no_falla,anula_la_ultima_sin_importar_filtro,
cancelado_por_usuario_no_borra}". `test_botones_secundarios_de_las_
tres_solapas_son_celestes` (confirma que Modificar/Anular quedan en
`botonSecundario`) pierde su aserción sobre los tres "Deshacer..." y su
docstring, que los mencionaba.

## Valores: se saca "Deshacer último movimiento" de la solapa "Aumentos"

Pedido explícito de la clienta, mismo criterio ya aplicado en Llaves/
Reservas/Registro de ausencias/Cargos especiales/Centro de mensajería:
se borra el botón, su conexión (`clicked.connect(self._deshacer_ultimo)`)
y el método `_deshacer_ultimo` de `_PanelAumentos` (`app/gui/pantallas/
aumentos.py`), además de sacarlo de la cadena de foco Enter/Tab (pasa de
terminar en Simular→Confirmar→Editar porcentaje diferencial→Deshacer a
la misma cadena sin el último paso).

Distinto de los casos anteriores: acá `app.negocio.aumentos.
deshacer_ultimo_aumento` (la función que revierte valores de
consultorio/esquema de descuentos/liquidaciones regeneradas) NO se
borra — a diferencia de los helpers puramente de soporte de Llaves/
Reservas (que solo existían para alimentar el botón), esta es una
función de negocio completa, con su propia batería de tests dedicada
(`tests/test_aumentos.py`) independiente de la GUI; se deja intacta por
si hace falta usarla desde otro lado más adelante (soporte, un futuro
botón en otra pantalla, etc.), aunque hoy quede sin ningún consumidor
en la GUI. Solo se borran los dos tests GUI-side que ejercían el botón
en `test_gui_aumentos.py` (`test_deshacer_ultimo_movimiento_revierte`/
`test_deshacer_sin_movimientos_no_falla`) — los cuatro tests de negocio
de `deshacer_ultimo_aumento` en `test_aumentos.py` no se tocan.

## Reordenamiento del menú "Operativa diaria" (pedido explícito de la clienta)

Sexto ajuste sobre el orden final del menú (después del renombre de
categorías "Sistema"/"Operativa diaria"): la clienta pidió un orden
puntual, distinto del que se había armado a criterio propio en esa
ronda, para las doce secciones de "Operativa diaria":

Grilla y mensajería, Reservas, Valores, Liquidaciones, Pagos, Registro
de ausencias, Disponibilidad, Profesionales, Llaves y otros conceptos,
Placas para timbres, Estadísticas, Balance del negocio.

Mismo mecanismo que el renombre de categorías (`VentanaPrincipal` arma
un separador de categoría cada vez que cambia respecto de la `Seccion`
anterior en la lista, no agrupa por nombre repetido) — alcanzó con
reordenar los doce bloques `Seccion` ya existentes dentro de
`construir_secciones()` (`gui_main.py`), sin tocar contenido de ninguno
(nombre, fábrica, ayuda). "Sistema" (5 secciones) no se tocó, sigue en
el mismo orden de siempre. Comentario de `construir_secciones` corregido
para reflejar que el orden de "Operativa diaria" es ahora un pedido
explícito de la clienta, no criterio propio.

Sin tests que actualizar: `test_categorias_son_solo_sistema_y_
operativa_diaria_y_van_contiguas` (`tests/test_gui_main.py`) solo
verifica que las categorías sean esas dos y que vayan contiguas, no el
orden interno de cada una — sigue pasando sin cambios.

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

## Capturas: sin sufijo "(pantalla completa)", a pantalla completa para
## varias pantallas más

Dos pedidos de la clienta sobre el criterio de capturas:

- **Nombre de archivo**: el sufijo "(pantalla completa)" que habían
  sumado las dos capturas de Placas de la ronda anterior se saca —
  vuelven al formato estándar de todo este documento, "{Sección} -
  {Formulario} - {Solapa}.png", igual al nombre con el que ya se
  descargan. El contenido (pantalla completa, con el menú a la
  izquierda) no cambió, solo el nombre del archivo.
- **Más pantallas a pantalla completa**: pedido explícito de "mandame de
  nuevo todas las solapas con el menú de navegación a la izquierda"
  para Valores, Registro de ausencias, Profesionales, Pagos y
  Estadísticas — mismo mecanismo que Placas (armar `VentanaPrincipal`
  de verdad vía `gui_main.construir_secciones()`, seleccionar la
  `Seccion` por su nombre en el menú lateral, `.grab()` sobre la
  ventana completa) aplicado a estas cinco. Sigue sin ser un cambio de
  convención retroactivo para el resto de las capturas ya enviadas —
  se aplica pantalla por pantalla, a medida que la clienta las pide de
  nuevo.

## Valores vigentes: columnas sin scroll horizontal, Localidad/Edificio
## más anchas en Promedios

Tres pedidos de la clienta sobre la solapa "Valores vigentes" (de
"Valores"), revisada al mandarle la captura a pantalla completa:

- **Las dos tablas, sin scroll horizontal.** "Valores vigentes por
  horas regulares y aisladas" (`tabla_valores`, 6 columnas) quedaba con
  barra de scroll horizontal en un panel más angosto que el de otras
  pantallas — sus columnas usaban el `ResizeToContents` default de
  `_armar_tabla` (compartido con `_PanelPromedios`, ver abajo), que
  dimensiona cada columna a su contenido sin importar cuánto ancho haya
  disponible en el `GroupBox` que la contiene. Localidad/Edificio/
  Unidad/Consultorio se quedan en ese modo (contenido corto, no
  necesitan más); "Valor hora regular"/"Valor hora aislada" — las dos
  columnas que de ese modo quedaban más angostas que su propio título —
  pasan a `Stretch`, mismo criterio que "Totales por bloques" de
  Liquidaciones simuladas (columnas cortas a su ancho justo, las
  últimas en Stretch). Para que las dos en Stretch tuvieran lugar de
  sobra se acortó además su título ("Valor hora regular"/"...aislada" →
  "Valor regular"/"Valor aislada" — "hora" ya está en el título del
  `GroupBox` que las contiene, de sobra repetirlo en la columna, mismo
  criterio de acortar títulos largos que ya se usó en otras pantallas).
- **"Promedios de valor hora regular y aislada": Localidad/Edificio más
  anchas, sin espacio en blanco al final.** Esta tabla (`_PanelPromedios`,
  un `QGroupBox` con ancho fijo 720-780 sin relación con el contenido
  real) dejaba un hueco en blanco después de la última columna —
  `_ajustar_ancho` (nuevo) calcula el ancho de la TABLA (no ya del
  `GroupBox`, que se achica solo alrededor) como la suma real de sus 5
  columnas, sacando el rango fijo de siempre. Localidad/Edificio
  (columnas 0/1) pasan de `ResizeToContents` a `Interactive` para poder
  sumarles `_PADDING_COLUMNA_PROMEDIOS = 20` sobre su ancho justo (mismo
  mecanismo que "Día" en Liquidaciones simuladas: `resizeColumnToContents`
  + `setColumnWidth(... + padding)`, que solo pega en una columna que no
  siga en `ResizeToContents` continuo). Un colchón de 2px sobre la suma
  de columnas absorbe un residuo de redondeo de Qt entre el ancho
  "lógico" seteado por columna y el pixel real que termina pidiendo el
  viewport — sin él, quedaba un scroll horizontal de 1px.

**Bug real encontrado al revisar esto contra la pantalla completa, no
solo el panel suelto** (confirmado con captura — el panel aislado en un
test daba bien, la pantalla completa no): `_PanelPromedios` arma y
puebla su tabla durante `__init__` de `_PanelValoresVigentes` (el
`on_cambiar` que dispara `_PanelFiltrosJerarquico` al construirse, ver
el comentario ya existente sobre ese orden), momento en el que el
widget todavía es huérfano — no cuelga todavía del árbol de
`VentanaPrincipal`, que recién arma cada `Seccion` DESPUÉS de haberse
aplicado a SÍ MISMA (no a la `QApplication`) el `setStyleSheet` de
`hoja_estilos()`. Con la fuente default de Qt (sin el bold/14px real de
los encabezados de `estilos.py`), `_ajustar_ancho` calculaba anchos más
angostos que los que hacen falta una vez que el panel cuelga de verdad
de la ventana y hereda el estilo real — mismo motivo, ya documentado en
Reservas, por el que un `sizeHint` calculado durante la construcción no
siempre es el definitivo. Se corrige con un `showEvent` en
`_PanelPromedios` que vuelve a llamar `_ajustar_ancho()` al mostrarse de
verdad. Test de regresión
(`test_valores_vigentes_sin_scroll_horizontal_con_estilo_real_aplicado`)
replica el bug real aplicando `hoja_estilos()` al panel DESPUÉS de
construirlo (mismo mecanismo que ya usan varios tests de Reservas) en
vez de a toda la `QApplication` — necesario para que la medición
"antes de estilar" ocurra de verdad.

Tests nuevos en `tests/test_gui_valores.py`:
`test_promedios_localidad_y_edificio_mas_anchas_que_sin_padding`,
`test_promedios_sin_espacio_en_blanco_tras_la_ultima_columna`,
`test_valores_vigentes_sin_scroll_horizontal_con_estilo_real_aplicado`.

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

## Centro de mensajería: color Bordó (recordatorio de fin de mes), se descarta la reactivación a rojo

Pedido de la clienta, ya con el sistema completamente reordenado: "quiero
agregar una instancia más al centro de mensajería... al final de mes
tendría a todos los profesionales en gris, salvo alguno con plan de pago
impago" — repaso que destapó la vieja reactivación gris->rojo (DC-02
§2.5: a X días de fin de mes, un gris con plan activo y saldo del mes en
curso fuera de tolerancia volvía a subir a rojo). Sobre esa descripción,
la clienta decidió: "El rojo lo dejamos para el punto 1 nada más, el
punto 2 lo desestimamos" — rojo queda SOLO para el camino de siempre
(deuda fuera de tolerancia + plan activo, liquidación todavía NO
enviada); la reactivación se borra por completo (`_debe_reactivar_rojo`/
`_dias_reactivacion_rojo` en `app.negocio.mensajeria`, y `mensaje_
situacion_4` en `app.negocio.mensajes`) y se reemplaza por un color
nuevo, bordó, con un alcance deliberadamente MÁS AMPLIO que el que tenía
la reactivación: "aplica a TODOS los profesionales con reserva regular
cuando se llega a esa instancia de mes" — sin mirar deuda ni plan de
pago, a diferencia de lo que reemplaza.

**Parámetro**: "Cantidad de días antes de fin de mes para activar
recordatorios en mensajería" (ej. "si el mes tiene 31 días, el día 26
por defecto 5 me va a cambiar el color de los profesionales grises").
Investigado antes de sumar una columna nueva: `Configuracion.
DiasAntesFinMesRecordatorioGeneral` ya existía en el schema (sembrada
con default 3) desde antes de este pedido, sin ningún lector en todo el
código — quedó así reusada para esto (default subido a 5) en vez de
crear una columna nueva, y sumada por primera vez a la GUI (`app.gui.
pantallas.configuracion`, solapa "Valores y liquidación", junto a "Días
de margen para envío de liquidaciones"). `DiasAntesFinMesRecordatorioPlan`
(el parámetro que leía la reactivación descartada) se dejó tal cual en
el schema en su momento — sin ningún lector nuevo ni viejo, sin armar
una migración para sacarlo.

**Repaso posterior, pedido explícito de la clienta** ("no cumple
función alguna ahora, quitalo"): se sacó de punta a punta —
`schema.sql` (ya no se crea en una base nueva), `seed.py` (fuera del
`INSERT` de valores por defecto) y `_COLUMNAS_ELIMINADAS` en
`migraciones.py` (`ALTER TABLE ... DROP COLUMN` para una base ya
creada que todavía la tenga) — mismo mecanismo ya usado para
`Consultorio.PanelVidrioLuzNatural`/`Edificio.DomicilioLocalidad`/
`Imagen.Localidad`. `DiasAntesFinMesRecordatorioGeneral` (la que sí
lee el recordatorio Bordó) no se tocó.

**Disparador** (`app.negocio.mensajeria._debe_recordar_fin_de_mes`): un
profesional categoría R que ya está en gris (liquidación del período
enviada) + tiene una `ReservaRegular` vigente hoy (`_reserva_regular_
activa`, duplicado del homónimo privado de `app.negocio.panel_control`
— mismo criterio de "no importar símbolos privados entre módulos sin
relación real entre sí", aunque los dos sean de negocio) + faltan ≤ N
días para fin de mes (el parámetro de arriba) + todavía no generó su
recordatorio este período → bordó. Sin reserva regular activa, o ya
generado el recordatorio este período, se queda en gris.

**Transición bordó -> gris**: mismo mecanismo que marrón->amarillo/
celeste->azul (`EstadoMensajeriaPeriodo`, columna nueva
`RecordatorioMensajeriaGenerado`), pero a la inversa — de urgente a
calmo en vez de al revés. Al generar el texto del recordatorio (botón
"Generar texto", igual que cualquier otro color) se llama `marcar_
recordatorio_mensajeria_generado`, y el profesional vuelve a gris por el
resto del período aunque sigan dándose las mismas condiciones (sigue
dentro de la ventana de días, sigue reservando regular) — "una vez que
lo copio... me lo pasa a gris de nuevo y me lo baja", confirmado por la
clienta.

**Mensaje** (`app.negocio.mensajes.mensaje_recordatorio_fin_de_mes`):
modelo final acordado con la clienta en dos vueltas (un primer borrador
propio, que la clienta reescribió con la redacción exacta que quería).
Empieza igual que el resto de los mensajes automáticos ("MENSAJE
AUTOMATICO", el mismo preámbulo literal de `mensaje_situacion_1`/
`mensaje_envio_liquidacion`) más una aclaración de que es informativo y
no hace falta responder. Después, "ESTADO DE CUENTA ACTUAL" con el
`SaldoCuentaActual` del profesional (no el anterior — es un recordatorio
sobre el mes que se está cerrando): en cero ("Saldo en cero, sin
deuda"), a favor del profesional (saldo negativo) o pendiente de
cancelación (saldo positivo) — nunca ambigüo sobre a favor de quién
queda la diferencia. Si queda deudor, suma una línea con la fecha de la
última recogida de sobres (`Configuracion.FechaHoraRecogidaSobres`, el
mismo valor que ya precarga el campo de Pagos al registrar un pago por
sobre — no una fecha nueva, reusada tal cual) como corte de lo ya
contemplado en ese saldo; si nunca se registró un pago por sobre, se
omite la línea entera. Las tres secciones de abajo repiten, casi
textual, las de "Mensaje grupal" (`mensaje_grupal`): "CIERRE DE
RESERVAS" (último día del período, mismo cálculo que ya usa esa
función), "ENVIO DE LIQUIDACIONES" (primer día del mes siguiente) y
"PROXIMOS FERIADOS" (uno por uno, no agrupados en una sola línea como en
"Mensaje grupal" — pedido explícito: "hacer esto con cada feriado o
fecha especial que haya cargada" — se omite la sección entera si no hay
ninguno).

**GUI** (`app/gui/pantallas/mensajeria.py`): bordó se suma a `_ORDEN_
COLOR` (justo antes de gris, mismo criterio de "urgencia decreciente"
que el resto del orden), `_ESTADO_TEXTO`, `_COLOR_FONDO` (`#6D1B2A`,
bordó real) y `_COLORES_CON_CHECK` (mismo criterio que gris: el check
"Enviada" sigue disponible para desmarcarla a mano si hiciera falta
corregir algo) y `COLORES_ENVIADOS` (el filtro "Enviados" también lo
muestra — ya tiene la liquidación enviada, igual que gris/azul). El
botón "Generar texto" de un bordó llama a `mensaje_recordatorio_fin_de_
mes` y dispara la transición a gris en el mismo golpe de clic, mismo
patrón que marrón/celeste.

## Textos del sistema (mensajes automáticos y ayuda F1 editables)

Pedido de la clienta ("los mensajes que se generan en el centro de
mensajería y todo otro texto que se genere en el sistema quiero que sea
editable"), consultado antes de implementar (`AskUserQuestion`, tres
decisiones):

- **Alcance**: los 7 mensajes automáticos del Centro de mensajería
  (situación 1/2/3/5, envío de liquidación, mensaje grupal, recordatorio
  de fin de mes/Bordó) + la ayuda contextual F1 de cada pantalla —
  prosa simple, bajo riesgo. Quedan AFUERA de esta vuelta
  `mensaje_detalle_reserva_aislada` (arma listas de reservas/cargos/
  edificios con loops) y los textos de WhatsApp de Oferta/Disponibilidad
  (`generar_texto_oferta_busqueda`, loops de franjas) — misma
  complejidad estructural, candidatos a una vuelta aparte. Los PDFs
  (tablas de ReportLab, no texto libre) quedan fuera de cualquier vuelta
  de "texto editable" — es un proyecto de maquetación, no de redacción.
- **Condicionales**: el sistema sigue decidiendo CUÁNDO aparece una
  sección condicional (la línea de sobres solo si hay deuda, el bloque
  de feriados solo si hay alguno cargado) — a la plantilla le llega ya
  armada como una variable más (`{bloque_feriados}`, `{estado_cuenta}`),
  nunca como lógica editable dentro del texto. Evita que una plantilla
  mal escrita rompa quién recibe qué contenido, a costa de que la
  redacción de esos bloques en sí no sea editable en esta primera
  vuelta (ej. las 3 líneas de "FERIADOS MES DE..." del Mensaje grupal).
- **Ubicación**: quinta solapa de "Archivos y listas" (no una pantalla
  propia del menú, ni una solapa de Configuración general ni de Listas
  editables, pensada para valores cortos de catálogo, no párrafos).

### Mecanismo (`app/negocio/plantillas_texto.py`)

Reusa `sustituir_variables` (mudada acá desde `app.negocio.mensajes`,
reexportada ahí para no romper a quien ya la importaba de ese módulo) —
mismo patrón ya aprobado para `MensajePredefinido`, en vez de inventar
uno nuevo. Tabla nueva, `PlantillaTexto` (`Clave` única + `TextoPersonalizado`
opcional): sin alta/baja desde la GUI, los "slots" son un conjunto FIJO
que define el código. `resolver_plantilla(conn, clave, default)` — el
texto personalizado si existe, si no el de fábrica (hardcodeado como
`DEFAULT_*` en este módulo, extraído literal de las funciones viejas de
`mensajes.py`). `guardar_texto_personalizado(conn, clave, texto)` con
`texto` vacío/`None` BORRA la fila en vez de guardar una cadena vacía —
"nunca se personalizó" y "se personalizó a propósito como texto vacío"
son estados distintos.

Cada `mensaje_situacion_N`/`mensaje_grupal`/`mensaje_envio_liquidacion`/
`mensaje_recordatorio_fin_de_mes` (`app/negocio/mensajes.py`) pasa de
armar el string a mano a: calcular las mismas variables de siempre en
un `dict`, resolver la plantilla (personalizada o de fábrica) y
sustituir — mismo resultado exacto que antes cuando no hay
personalización (confirmado: los tests de redacción existentes
siguieron pasando sin tocarlos). `MENSAJES_EDITABLES` (lista de
`PlantillaMensaje`: clave, nombre legible, default, variables
disponibles) es el registro que lee la pantalla para armar su lista —
vive acá, no en `mensajes.py`, para que la GUI no tenga que importar ni
ejecutar ninguna función de armado solo para mostrar nombres/variables.

La ayuda F1 (`VentanaPrincipal._mostrar_ayuda`, `app/gui/main_window.py`)
pasa a resolver `resolver_plantilla(conn, f"ayuda:{seccion.nombre}",
seccion.ayuda or "...")` en vez de leer `seccion.ayuda` directo — la
clave usa el nombre de la `Seccion` del menú (mismo criterio que
`PermisoPantalla.NombrePantalla`, que ya identifica pantallas por su
nombre de menú en vez de un ID propio).

### GUI (`app/gui/pantallas/textos_sistema.py`, `_PanelTextosDelSistema`)

No usa `PantallaCRUD` (mismo criterio que Usuarios y permisos/Gestor de
archivos: no hay alta/baja, es edición de un conjunto fijo) — una lista
a la izquierda (`QListWidget`, ancho fijo 360px) agrupada en dos
secciones con separadores no seleccionables (mismo mecanismo
`Qt.ItemFlag.NoItemFlags` que ya usan los separadores de categoría del
menú lateral): "MENSAJES AUTOMÁTICOS" (los 7 de `MENSAJES_EDITABLES`) y
"AYUDA CONTEXTUAL (F1)" (una por cada `Seccion` recibida — mismo dato
`secciones` que ya le llegaba a "Archivos y listas" para el botón
"Manual del usuario" de Gestor de archivos, reenviado también acá).
Un ítem ya personalizado muestra "(personalizado)" al final de su
nombre en la lista.

A la derecha: nombre del texto elegido, una línea con las variables
disponibles (o "Este texto no tiene variables" para la ayuda F1, que no
tiene ninguna), el editor (`QPlainTextEdit`, precargado con el texto
EFECTIVO — personalizado o de fábrica) y dos botones del mismo ancho
(`botonPrimario`/`botonSecundario`): "Guardar" y "Restablecer al
original" (deshabilitado si no hay override para ese texto todavía).
"Restablecer" pide confirmación (se pierde la personalización) y borra
la fila en vez de guardarla vacía.

Guardarraíl liviano (no bloqueante): al guardar, si el texto tipeado
tiene algún `{token}` que no es ninguna de las variables disponibles
para ESE mensaje puntual, se avisa con un cartel Sí/No antes de guardar
igual — para avisar de un typo en el nombre de una variable (quedaría
visible tal cual en el mensaje real, sin reemplazar) sin impedir
guardar si la clienta de verdad quiere ese texto literal.

### Corrección de paso

El docstring de `mensajes_predefinidos.py` mencionaba una categoría
"Situaciones centro de mensajería" y una función `_DESCRIPCION_SITUACION`
que nunca llegaron a existir en el código (quedó de una etapa de diseño
anterior, nunca se corrigió) — se actualizó para apuntar a este
mecanismo nuevo (`PlantillaTexto`), que es el que realmente cubre ese
caso.

### Segunda vuelta: se suma `mensaje_detalle_reserva_aislada`

Pedido explícito de la clienta: sumar el octavo mensaje que había
quedado afuera de la primera vuelta por su complejidad estructural
(arma casi todo su cuerpo con loops — llaves, reservas, saldo, pagos,
ítems libres, reservas posteriores, edificios mencionados, nota de
sobres). Mismo criterio ya usado para `{bloque_feriados}` del Mensaje
grupal: en vez de dejar cada línea del cuerpo editable (lo que
rompería en cuanto cambiara algo que el código necesita seguir
calculando), todo ese cuerpo se le entrega a la plantilla como una
ÚNICA variable ya armada, `{detalle_items}` — no editable línea por
línea, solo reubicable dentro del texto. Lo que SÍ queda editable de
verdad es el encabezado: título ("DETALLE RESERVA {mes_mayus}") y
nombre del profesional (`{nombre_profesional}`).

`DEFAULT_DETALLE_RESERVA_AISLADA` (`app/negocio/plantillas_texto.py`):
`"DETALLE RESERVA {mes_mayus}\n{nombre_profesional}\n\n{detalle_items}"`
— reproduce exacto el formato de siempre (confirmado: los tests de
redacción existentes de `mensaje_detalle_reserva_aislada`, que no
personalizan nada, siguieron pasando sin tocarlos). `mensajes.py` pasa
de armar `lineas` con el encabezado adentro a arrancar esa lista vacía
(solo el cuerpo) y resolver la plantilla al final, igual que el resto
de los 7 mensajes ya editables.

Los textos de WhatsApp de Oferta/Disponibilidad (loops de franjas,
misma complejidad estructural) siguen sin ser parte de esta
funcionalidad — no fueron parte de este pedido.

Tests nuevos en `tests/test_plantillas_texto.py`:
`test_mensaje_detalle_reserva_aislada_solo_el_encabezado_es_editable`
(personaliza el encabezado, confirma que `{detalle_items}` sigue
armado por el código) y `test_mensaje_detalle_reserva_aislada_sin_
personalizar_sigue_igual_que_antes`. El conteo de `MENSAJES_EDITABLES`
en `test_claves_de_mensajes_editables_son_unicas` sube de 7 a 8.

### Tercera vuelta: se suma `oferta_busqueda_whatsapp` y auditoría de cierre

Pedido explícito de la clienta: sumar el texto de WhatsApp de "Oferta
de consultorios"/"Disponibilidad" (`generar_texto_oferta_busqueda`,
`app/negocio/oferta_busqueda_whatsapp.py`) — el otro candidato que había
quedado afuera de la primera vuelta, misma complejidad estructural que
`mensaje_detalle_reserva_aislada` — y de paso auditar el resto del
sistema por si quedaba algún otro texto generado que mereciera entrar a
"Textos del sistema", "así tenemos todo cubierto en este aspecto".

**Auditoría de cierre** (agente de exploración, sin escribir código):
barrido de todo `app/` fuera de `app/pdf/` buscando cualquier función
que arme y devuelva un texto de varias líneas pensado para ser leído/
copiado/enviado por la clienta a un profesional o a un tercero. Resultado:
ningún otro candidato real.
- `mensaje_conflicto_aislada` (`app.negocio.conflictos_aisladas`):
  cartel de error en un `QMessageBox.warning`, solo para la operadora,
  nunca se envía a nadie — mismo descarte que cualquiera de los demás
  carteles de advertencia/información sueltos por el sistema (no son
  "texto de fábrica" con una redacción fija que tenga sentido poder
  reescribir, son mensajes de validación puntual con datos en vivo).
- `texto_para_imprimir` de Placas (`app.negocio.placas`): no es prosa
  de fábrica — es el nombre estándar del profesional O un texto YA
  libre que la clienta tipea por placa (`NombreGrabado`); no hay nada
  fijo ahí que haga falta volver editable, el mecanismo de "texto
  libre por registro" ya cumple ese rol.
- PDFs (`app/pdf/`): quedan fuera de cualquier vuelta de esta
  funcionalidad — son tablas/Paragraphs de ReportLab, un proyecto de
  maquetación, no de redacción de texto corrido.
- Revisadas puntualmente y descartadas por ser resúmenes de datos para
  mostrar en una celda/tooltip, no mensajes: `app.gui.widgets.
  resumen_saldo` (etiquetas de saldo con color), `_texto_condiciones`
  de Lista de espera (resumen de filtros en una celda).

Con esto, "Textos del sistema" queda en 9 slots de mensaje (los 7 del
Centro de mensajería + `mensaje_detalle_reserva_aislada` +
`oferta_busqueda_whatsapp`) más la ayuda F1 de cada pantalla — no
queda pendiente ningún otro texto generado por el sistema con este
perfil.

**Mecánica de `oferta_busqueda_whatsapp`**: mismo criterio que
`mensaje_detalle_reserva_aislada` — el texto tiene tres secciones
armadas con loops (detalle de la búsqueda, listado de alternativas,
comentario de edificios/avisos) que se entregan a la plantilla como
tres variables de bloque ya resueltas (`{bloque_detalle_busqueda}`/
`{bloque_alternativas}`/`{bloque_comentario}`), nunca editables línea
por línea. Lo editable de verdad son los tres títulos en negrita de
WhatsApp ("*Búsqueda requerida por el profesional*", "*Detalle de la
búsqueda*", "*Listado de alternativas encontradas*"). El título propio
de la sección de comentario, "*Comentario*", queda DENTRO de
`{bloque_comentario}` (no como texto fijo aparte) — mismo truco que
`{bloque_feriados}` del Mensaje grupal: así toda la sección, título
incluido, desaparece junto cuando no hay ni edificios que aclarar ni
avisos. Los marcadores estructurales de WhatsApp (viñetas "- ", la
numeración "_Alternativa N_", la frase "Sin disponibilidad...") quedan
del lado del código, dentro de `{bloque_alternativas}` — el sistema
sigue decidiendo cuándo y cómo, nunca una plantilla mal escrita.

`DEFAULT_OFERTA_BUSQUEDA_WHATSAPP` reproduce exacto el formato de
siempre (confirmado: los 13 tests ya existentes de
`generar_texto_oferta_busqueda`, que no personalizan nada, siguieron
pasando sin tocarlos). `generar_texto_oferta_busqueda` pasa de armar
`lineas` a mano y unirlas con `"\n".join` a juntar cada sección en su
propia lista (`detalle_lineas`/`alternativas_lineas`/`comentario`),
resolver la plantilla y sustituir — mismo patrón que el resto de los
mensajes editables.

Tests nuevos en `tests/test_plantillas_texto.py`:
`test_oferta_busqueda_whatsapp_solo_los_titulos_son_editables`
(personaliza los tres títulos, confirma que los tres bloques siguen
armados por el código) y `test_oferta_busqueda_whatsapp_sin_
personalizar_sigue_igual_que_antes`. El conteo de `MENSAJES_EDITABLES`
sube de 8 a 9.

## DC-06 §3: alerta de deuda regular anterior, snapshot retroactivo y
## bloqueo de reservas regulares en períodos cerrados

Repaso de un punto de la auditoría DC-01/DC-10 que había quedado
señalado como "sigue sin implementar": el documento original DC-06 §3 no
está en el repositorio, solo un resumen de una línea en el audit ("alerta
permanente, pregunta '¿esta reserva es de mes anterior o nuevo?', ajuste
retroactivo"). Antes de tocar código se le preguntó a la clienta si tenía
el texto original para pasar o prefería que se propusiera un diseño a
partir de ese resumen — eligió lo segundo.

Investigando el código antes de proponer nada salió a la luz que buena
parte de "DC-06 §3" YA estaba implementada, bajo otros nombres, de
rondas anteriores de este mismo documento — la auditoría la había
pasado por alto porque buscó solo dentro de `app/negocio/`:
`app/gui/dialogos.py` (`confirmar_si_fecha_es_mes_anterior`/
`confirmar_si_periodo_imputado_es_anterior`, con "DC-06 §3" ya en su
propio docstring) es exactamente la "pregunta" del resumen — un cartel
Sí/No para atajar errores de tipeo en la fecha, ya conectado en Reservas
aisladas (campo Fecha) y en Pagos (período imputado). El "ajuste
retroactivo" también estaba cubierto en gran parte:
`liquidaciones._calcular_horas_regulares_agregadas`/`_calcular_feriados_
pendientes` ya reclasifican solas, sin preguntar nada, una reserva
regular o un feriado que llega justo después de que su mes ya se había
emitido — las corren al período siguiente con el mismo descuento que les
hubiera correspondido a tiempo.

Con eso ya mapeado, se le propusieron tres piezas puntuales a la clienta
(`AskUserQuestion`) para cubrir lo que realmente faltaba:

- **Alerta permanente de deuda regular anterior**: hoy solo existe para
  aisladas (`_deuda_aisladas`). Aprobado con la recomendación.
- **Snapshot retroactivo**: que un `SnapshotMensual` ya cerrado se
  recalcule solo cuando llega una aislada tardía a ese mes. Aprobado,
  condicionado a que no fuera costoso — el cálculo resultó ser el mismo
  que ya corre una vez por mes en cada avance de mes (unas pocas
  consultas SQL por día del período), así que recalcularlo ante un
  evento raro (una aislada cargada en un período cerrado) no agrega
  ningún costo de otro orden de magnitud.
- **La "pregunta" sobre reservas**: la clienta aclaró el punto más
  importante de esta vuelta, más allá de la pregunta en sí — "si se
  quiere cargar una reserva aislada a un período anterior cerrado...
  modifica el saldo anterior y lo traslada al actual. Si pasa lo mismo
  con una reserva regular, ahí es más complejo, porque aparte de los
  saldos habría que tocar las liquidaciones... en el caso de querer
  modificar reservas regulares en períodos cerrados bloqueaba con un
  alerta, y cualquier ajuste se hacía a través del manejo de cargos
  especiales". Esto fija una asimetría real entre los dos tipos de
  reserva que no estaba cubierta: una aislada en un período cerrado se
  puede cargar sin pedir nada más (ya se resuelve sola, ver abajo); una
  regular en un período cerrado tiene que BLOQUEARSE sin excepción,
  dirigiendo a Cargos especiales para cualquier corrección.

### Alerta "Deuda mes anterior — profesionales regulares"

`app.negocio.panel_control._deuda_regulares` (todos los R con
`SaldoCuentaAnterior` fuera de tolerancia) ya existía, pero solo
alimentaba el cuadrito "Profesionales" — nunca había tenido su propia
tarjeta en "Alertas". Se sumó el campo `Alertas.deuda_regulares_mes_
anterior`, wireado a esa misma función (sin filtro de reserva activa,
mismo criterio que `_deuda_aisladas`, a diferencia de `_deuda_regulares_
alerta` — la alerta de "Deuda mes en curso" ya existente, que sí exige
reserva activa y mira `SaldoCuentaActual` en vez de `SaldoCuentaAnterior`
— dos alertas distintas, sin relación entre sí más que el nombre de
función parecido). `_TITULOS_ALERTA`/`_ETIQUETA_FILA`
(`app/gui/pantallas/panel_control.py`) suman la entrada nueva con el
mismo formato de etiqueta que ya usa "Deuda mes anterior — profesionales
de reserva aislada".

### Snapshot retroactivo ante una aislada tardía

`app.negocio.estadisticas._campos_snapshot(conn, anio, mes)` (nueva)
extrae los campos recalculables de un snapshot (ocupación, valores
vigentes, horas regulares promedio, montos netos regular/aislada) a un
helper compartido — `generar_snapshot` (alta, al avanzar de mes) y
`regenerar_snapshot_si_corresponde(conn, periodo)` (nueva) lo llaman
igual, sin duplicar el cálculo. Esta última busca si YA existe un
`SnapshotMensual` para `periodo` (si no, no hace nada — el mes no cerró,
no hay nada desalineado) y, si existe, lo actualiza IN PLACE con los
valores recalculados — conservando `FechaGeneracion` (sigue siendo
cuándo se cerró el mes, no cuándo se corrigió después) y
`PorcentajeAumentoAplicado` (dato de contexto del cierre original, no
recalculable desde el estado actual).

Se llama desde `app/gui/pantallas/reservas.py`, en los tres puntos donde
una `ReservaAislada` cambia de estado (`_crear`/`_cancelar_registro` de
`_PanelReservasAisladas` — "Modificar reserva" reusa `_cancelar_
registro` + el alta de siempre, así que queda cubierta de rebote), con
el período de la `Fecha` de la reserva (no `periodo_actual`: es el
período al que esa fecha puntual pertenece, sea el actual o uno
cerrado). Una reserva regular NO dispara esto — queda bloqueada antes de
llegar a tocar nada (ver abajo), así que nunca hay un snapshot cerrado
que una regular pueda desalinear.

### Bloqueo de reservas regulares en períodos cerrados

"Período cerrado" se define con el mismo criterio EXACTO que ya usa el
guardarraíl de `liquidaciones.emitir_liquidacion` (DC-08 §6.2: "nunca se
puede generar una liquidación de un mes anterior ya cerrado") — ya
existe una `LiquidacionEmitida` de un período POSTERIOR, para el
profesional LIQUIDABLE (`liquidaciones.id_profesional_liquidable`: el R
mismo, o su cabeza de equipo si es categoría E). Sin eso, el período
sigue "abierto" aunque ya haya pasado en el calendario — no hay ninguna
liquidación posterior que una reclasificación pudiera desalinear, así
que no hace falta bloquear nada.

`app.negocio.reservas._periodo_regular_cerrado`/`_validar_vigencia_no_
cerrada` (nuevas) aplican este chequeo sobre `vigencia_inicio` Y
`vigencia_fin` en `crear_reserva_regular` — a diferencia de los
conflictos de superposición (avisos que `forzar=True` puede confirmar),
este bloqueo NUNCA se puede forzar: no es una advertencia, es un
guardarraíl real, mismo criterio sin excepción que `emitir_liquidacion`.
El mensaje de error dirige explícitamente a usar un Cargo especial para
corregir algo de un período ya cerrado, en vez de tocar la reserva.

Como "Finalizar reserva a fin de mes"/"Modificar reserva" (las dos
solapas de Reservas) ponían `VigenciaFin` escribiendo directo al
repositorio (`ReservaRegular.actualizar`), sin pasar por ninguna función
de negocio, esa vía quedaba sin el chequeo — se sumó `finalizar_reserva_
regular(conn, id_reserva_regular, vigencia_fin)` (nueva, con el mismo
guardarraíl) y `_finalizar_registro` (`app/gui/pantallas/reservas.py`)
pasa a llamarla, devolviendo `False` (con un cartel de aviso en vez de
romper) si el bloqueo se dispara. Bajo el uso normal de esos dos botones
(que siempre finalizan a fin de mes actual o a hoy, nunca a una fecha
pasada) esto nunca debería dispararse — la validación vive en la capa de
negocio para que ningún botón futuro, ni un uso directo de la función
fuera de la GUI, pueda sortearla.

Tests nuevos: `tests/test_panel_control.py` (dos tests de la alerta
nueva, respeta tolerancia y no exige reserva activa). `tests/test_
reservas.py` (ocho tests: bloquea con `vigencia_inicio`/`vigencia_fin`
en un período cerrado, `forzar=True` no lo sortea, el mismo período que
la última liquidación NO bloquea — `Periodo >`, no `>=`—, un E consolida
el chequeo en su R, un B nunca bloquea — no tiene profesional liquidable
—, `finalizar_reserva_regular` bloquea/funciona según corresponda).
`tests/test_estadisticas.py` (cuatro tests de `regenerar_snapshot_si_
corresponde`: sin snapshot previo no hace nada, recalcula montos con una
aislada tardía actualizando la fila existente sin duplicarla, conserva
`FechaGeneracion`/`PorcentajeAumentoAplicado`, no toca el snapshot de
otro período). `tests/test_gui_reservas.py` (dos tests confirmando que
crear y cancelar una aislada disparan la regeneración del snapshot de su
propio período).

## DC-06 §2 Paso 9: el snapshot se genera al final del avance de mes

Siguiente punto de la auditoría DC-01/DC-10 (hallazgo #29, v2): `avance_
mes.avanzar_mes` generaba el `SnapshotMensual` del período que se cierra
como SEGUNDO paso del proceso (justo después del backup), en vez de
como el último (DC-06 §2 Paso 9, el último del documento original).

`generar_snapshot` pasa a llamarse al final de `avanzar_mes`, después de
traspasar saldos, cerrar cuotas, limpiar la lista de espera, regenerar
Archivos varios y limpiar liquidaciones antiguas — en vez de justo
después del backup. Ningún valor calculado cambia con este reordenamiento
(confirmado revisando los otros pasos: ninguno toca `ReservaRegular`/
`ReservaAislada`/`Consultorio.ValorHora*`, que es todo lo que
`generar_snapshot` lee), pero el snapshot queda representando de verdad
el cierre del mes después de que el resto del proceso corrió, no una
"foto" tomada a mitad de camino — consistente con el orden documentado.

Test nuevo en `tests/test_avance_mes.py`
(`test_avanzar_mes_genera_snapshot_al_final`): envuelve `generar_
snapshot`/`_traspasar_saldos`/`_regenerar_archivos_varios` para
registrar el orden real de ejecución y confirma que el snapshot es el
último de los tres.

## DC-10 §1.2: valores a mano, resaltado, botón Restablecer y aviso de
## liquidaciones antes de confirmar (solapa "Aumentos")

Siguiente punto de la auditoría DC-01/DC-10 (hallazgo #30): "Al análisis
de aumentos le falta: resaltado visual de valores editados a mano vs.
calculados por %; botón 'Restablecer' por fila individual; y el aviso de
cuántas liquidaciones se van a regenerar aparece DESPUÉS de confirmar,
no antes." Los tres huecos eran reales — confirmado leyendo el código:
`app.negocio.aumentos.simular_aumento`/`confirmar_aumento` ya tenían
soporte completo para un override de valor final en $ por consultorio
(`valores_override`, "más específico todavía" que el % diferencial, ver
su propio docstring) desde que se armó esa pantalla, pero la GUI nunca
había expuesto ningún control para cargarlo — solo el % diferencial.

- **"Editar valores manuales"** (botón hermano de "Editar porcentaje
  diferencial", mismo criterio checkable): habilita a mano, en $, las
  columnas "Regular nuevo"/"Aislada nuevo" — hasta ahora siempre de solo
  lectura. Mismo criterio "un solo tipo de override por fila" que ya
  regía entre % general/diferencial ("nunca se muestran los dos
  juntos"): fijar un valor a mano en una fila limpia el % diferencial de
  esa fila y viceversa, en vez de dejar un estado ambiguo con los dos
  override activos a la vez.
- **Resaltado amarillo** (`COLOR_AMARILLO`, reusado de `estilos.py`, no
  un color nuevo) en la celda puntual ("Regular nuevo" o "Aislada
  nuevo") cuando ESE valor viene de un override a mano — nunca cuando
  sale de aplicar el % general o el diferencial, que siguen siendo
  "calculado por %" (un % puntual de esa fila sigue siendo un %, no una
  cifra tipeada a mano) — lectura literal del hallazgo, confirmada
  contra el ejemplo de la captura enviada.
- **Botón "Restablecer" por fila**: columna nueva sin título, un botón
  por fila (`setCellWidget`) deshabilitado si esa fila no tiene ningún
  override — clickearlo limpia el % diferencial Y el valor manual de
  esa fila de una sola vez, volviéndola a calcular por el % general.
- **Aviso de liquidaciones ANTES de confirmar**: `app.negocio.aumentos.
  cantidad_liquidaciones_a_regenerar(conn, periodo)` (nueva, extraída
  del mismo query que ya usaba `confirmar_aumento` para armar
  `ids_profesional`) se consulta antes de mostrar el cartel de
  confirmación, y la cantidad entra directo en el texto del cartel
  ("Hay N liquidación(es) ya emitida(s) para ese período: se van a
  regenerar con los valores nuevos" / "Todavía no hay ninguna
  liquidación emitida para ese período") — antes esa cantidad solo
  aparecía en el cartel de éxito, después de que ya se habían
  regenerado.

**Bug real encontrado al armar "Restablecer", no pedido** (destapado
comparando la geometría real contra lo esperado, no a ojo): `setCellWidget`
no borra solo el widget que reemplaza —a diferencia de `setItem`, que sí
limpia el item viejo— así que crear un botón "Restablecer" nuevo en
CADA render (`_simular`, tildar/destildar "Editar...") dejaba el botón
anterior huérfano, colgado del viewport sin ninguna posición asignada
por la tabla: Qt lo terminaba pintando en la esquina superior izquierda
del viewport, superpuesto contra "Localidad"/"Edificio" de la primera
fila en vez de desaparecer — `deleteLater()` tampoco alcanzaba, la
deleción queda pendiente del event loop, que entre un render y el
siguiente acá no llega a correr. Se resolvió reusando un solo botón por
consultorio (`self._botones_restablecer`, limpiado en `actualizar()`
junto con `_diferenciales`/`_valores_manuales`) en vez de crear uno
nuevo cada vez — solo se le actualiza el `setEnabled()` según corresponda.

Tests nuevos en `tests/test_aumentos.py` (tres: `cantidad_liquidaciones_
a_regenerar` sin emisiones es cero, cuenta profesionales distintos una
sola vez aunque tengan reemisión, coincide exactamente con lo que
`confirmar_aumento` termina regenerando) y en `tests/test_gui_aumentos.py`
(catorce: botón/columnas editables solo con el toggle prendido, fijar un
valor a mano actualiza la simulación sin que el % general/redondeo le
vuelvan a pegar, vaciar la celda saca solo ESE override, valor inválido
avisa sin romper, resaltado amarillo solo en la celda con override a
mano — nunca en la calculada por %—, valor manual y % diferencial se
excluyen mutuamente en una y otra dirección, "Restablecer" deshabilitado
sin override / limpia los dos tipos de override al clickear, el cartel
de confirmación menciona la cantidad real de liquidaciones — con y sin
liquidaciones emitidas—, confirmar aplica el valor manual al consultorio,
y el test de regresión del bug de los botones huérfanos).

## DC-06 §6: snapshot "de operación importante", retención y exportar a Excel

Hallazgo de la auditoría DC-01/DC-10 (v1, nunca re-verificado hasta este
pase): "no existe el tipo de snapshot 'de operación importante' (antes
de aumentos o desactivación de edificio/unidad), ni función para
eliminar snapshots antiguos con sus reglas de retención, ni exportación
a Excel desde Estadísticas". Confirmado contra el código actual: ninguna
de las tres piezas existía. Antes de implementar se consultaron tres
decisiones (`AskUserQuestion`), porque el hallazgo daba por sentada una
funcionalidad que no existe en el sistema (desactivar un edificio/
unidad — `Edificio`/`Unidad` no tienen ningún campo `Activo`):

- **Alcance del snapshot especial**: "solo antes de Aumentos" — se
  descarta inventar un sistema de activo/inactivo para edificio/unidad
  solo para cubrir la otra mitad del hallazgo original, que no tiene
  ningún otro punto de apoyo en el resto del sistema.
- **Retención**: 12 meses, solo para los snapshots de este tipo nuevo —
  los mensuales de siempre (uno por período, que "Historial general"
  necesita conservar para siempre) no se tocan.
- **Exportar a Excel**: sí, un botón por solapa que exporta exactamente
  lo que está filtrado/visible en ese momento en la tabla.

### Snapshot "de operación importante" (`app.negocio.estadisticas`)

`SnapshotMensual` suma dos columnas: `Tipo` (`'Mensual'` por default —
las filas ya cargadas antes de este cambio quedan así solas, vía
migración — o `'OperacionImportante'`) y `Observacion` (texto libre,
solo para el tipo nuevo). `generar_snapshot` (el de siempre, uno por
período al cerrar el mes) ahora pasa `Tipo="Mensual"` explícito.

`generar_snapshot_operacion_importante(conn, periodo, *, observacion=None)`
(nueva) arma un snapshot con el mismo contenido que el mensual
(`_campos_snapshot`, compartido entre los tres) pero `Tipo=
'OperacionImportante'` — a diferencia del mensual, PUEDE haber varios en
el mismo período (cada operación importante genera el suyo, no hay
restricción de "uno por período"). `app.negocio.aumentos.confirmar_aumento`
la llama al principio, ANTES de tocar ningún valor de consultorio — así
`ValoresConsultorios` del snapshot queda con el estado VIEJO, el punto
de comparación real que pedía el hallazgo ("antes de la operación"), no
el nuevo recién aplicado.

`historial_general` y `regenerar_snapshot_si_corresponde` (DC-06 §3, ver
más arriba) pasan a filtrar `Tipo='Mensual'` en su `SnapshotMensual.
listar(...)` — sin este filtro, un snapshot de operación importante del
mismo período podía colarse en `datos_por_mes` (que es un dict keyed por
`Periodo`, pensado para una sola fila por mes) y pisar o duplicar al
mensual real, según el orden de iteración. Son conceptos distintos: el
de operación importante no representa "el cierre de ese período", así
que nunca debe aparecer en "Historial general" ni ser el blanco de un
ajuste retroactivo de DC-06 §3.

No tiene pantalla propia para revisarlos a mano todavía — no fue parte
de lo que se consultó ni de lo que pide el hallazgo (que solo pedía que
el tipo existiera, la retención y la exportación); quedan en la base
como registro histórico, visibles solo indirectamente a través de la
retención.

### Retención: 12 meses (`limpiar_snapshots_operacion_importante_antiguos`)

Mismo criterio de retención en MESES que `app.negocio.archivos_
generados.limpiar_liquidaciones_simuladas_antiguas` (comparar contra
`sumar_meses`), pero sobre filas de la base en vez de archivos en disco:
borra los `SnapshotMensual` con `Tipo='OperacionImportante'` cuyo
`Periodo` quedó a más de 12 meses de `hoy`. Los mensuales de siempre no
se tocan, sin importar su antigüedad — siguen conservándose para
siempre, como ya documentaba la sección de Estadísticas más arriba.

Se llama desde `avance_mes.avanzar_mes` (nuevo campo `snapshots_
operacion_importante_eliminados` en `ResumenAvanceMes`), junto al resto
de limpiezas periódicas del proceso — mismo lugar que `_limpiar_
liquidaciones_simuladas_antiguas`, antes del snapshot del Paso 9.

### Exportar a Excel (`app/gui/pantallas/estadisticas.py`)

Un botón "Exportar a Excel" (`botonSecundario`, mismo ancho que
"Actualizar tabla" — debajo de ese botón en las dos solapas, sumado
también a la cadena de foco Enter/Tab de cada panel) abre un selector
nativo "Guardar como" (`QFileDialog.getSaveFileName`, mismo criterio que
"Descargar planilla importación") y genera ahí un libro Excel
(`openpyxl`, ya dependencia del proyecto) con las mismas 11 columnas que
la tabla en pantalla, mismos títulos (sin el `"\n"` que ahí sirve para
achicar el ancho del encabezado — no hace falta en una planilla) y el
MISMO formato de texto que ya se ve en cada celda (`_texto_pct`/
`_texto_horas`/`_texto_variacion`/`_texto_monto`, reusados tal cual) —
exporta exactamente las filas que están filtradas/ordenadas en ese
momento (`self._filas`, ya calculado por `actualizar()`), no un volcado
aparte de toda la base. `_exportar_filas_a_excel(filas, ruta)` es una
función compartida por las dos solapas (`_PanelHistorialGeneral`/
`_PanelEstadisticasVarias`), cada una con su propio nombre de archivo
sugerido ("Estadisticas - Historial general.xlsx"/"Estadisticas -
Estadisticas varias.xlsx").

Bug real encontrado al armar los tests de esta pantalla, no puntual de
Estadísticas: `QMessageBox.information`/`.critical` son modales de
verdad (`exec()` bloquea el hilo esperando una respuesta) — un test que
ejercite el camino de éxito o de error de "Exportar a Excel" se queda
esperando para siempre si no se los neutraliza. `test_gui_importacion.py`
ya tenía resuelto esto con una fixture `autouse` que los pisa por un
no-op (`monkeypatch.setattr(QMessageBox, "information"/"critical",
staticmethod(lambda *a, **k: None))`) — se sumó la misma fixture a
`test_gui_estadisticas.py`, que hasta ahora nunca había tocado ningún
`QMessageBox` modal y por eso no la necesitaba.

Tests nuevos: `tests/test_estadisticas.py` (siete: el snapshot nuevo
queda marcado `Tipo='OperacionImportante'` con su observación, el
mensual sigue en `Tipo='Mensual'`, pueden convivir varios del tipo
nuevo en el mismo período, `historial_general` los ignora por completo,
`regenerar_snapshot_si_corresponde` no los toca si es lo único que hay
en ese período, la retención borra solo los de más de 12 meses, nunca
toca un mensual). `tests/test_aumentos.py` (uno: `confirmar_aumento`
deja el snapshot con el estado VIEJO de `ValoresConsultorios`, no el
nuevo). `tests/test_avance_mes.py` (uno: `avanzar_mes` limpia los
vencidos sin tocar los mensuales). `tests/test_gui_estadisticas.py`
(cinco: el botón es `botonSecundario`, exportar genera el archivo con
los encabezados y filas esperados en las dos solapas, cancelar el
selector no genera nada, la cadena de foco de "Estadísticas varias"
suma el botón nuevo al final).

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

## DC-07 §2.5: Tipo Bloque de la grilla ignora DiasVisualizacion/DiasLogica — decisión consciente, sin tocar código

Hallazgo de la auditoría DC-01/DC-10 (#31, confirmado ❌ SIGUE en el v2):
"la grilla PDF ignora `DiasVisualizacion`/`DiasLogica`: clasifica
bloques rígidos solo por horario, sin distinguir por día". Investigado
antes de tocar nada: el bug es más profundo de lo que sugiere el texto
del hallazgo, y está duplicado en dos lugares, no solo en el PDF.

**Diagnóstico**: tanto `app/pdf/grilla_pdf.py` (`_tipo_bloque_por_hora`)
como `app/gui/widgets/grilla_operativa.py` (función homónima, misma
firma e idéntica lógica) clasifican cada hora como Rígido/Flexible
mirando únicamente si algún `BloqueRigido` activo cubre esa hora
(`HoraInicio <= h < HoraFin`), sin mirar `DiasLogica` ni
`DiasVisualizacion` en absoluto — la columna "Tipo Bloque" de la grilla
(PDF y GUI por igual) es una única columna por hora, COMPARTIDA por
todos los días que muestra la grilla, así que ni siquiera hay dónde
guardar un valor distinto por día con la estructura actual de la tabla.
El único arreglo de raíz sería convertir esa columna en una por cada
grupo de día (misma reestructuración necesaria en los dos archivos,
PDF y GUI) — alcance real mucho mayor que lo que sugiere el hallazgo
original.

Por qué nunca se notó con los datos de ejemplo: el bloque rígido default
de 18-21hs se siembra con `DiasLogica` = Lunes a Viernes pero
`DiasVisualizacion` = Lunes a Sábado (documentado a propósito desde que
se armó esta funcionalidad, ver `app/db/seed.py:
sembrar_bloques_rigidos` y el docstring de `bloques_rigidos.py` —
"puede ser más amplio que DiasLogica, como el default de 18-21hs") — y
`dias_grilla()` por defecto también es Lunes a Sábado, así que
`DiasVisualizacion` termina coincidiendo con TODOS los días que la
grilla muestra por defecto, ocultando el bug en cualquier captura o uso
con la configuración de fábrica. Solo se manifiesta con una
configuración real donde `DiasVisualizacion` no cubre todos los días
visibles de la grilla (ej. un bloque que se visualiza rígido L-V pero
no sábado).

**Decisión de la clienta, consultada antes de tocar nada** (dos
alcances posibles: arreglo completo en los dos archivos con columna por
día, o solo el PDF per el alcance literal del hallazgo): "No quiero
tocar nada de las grillas" — las dos opciones quedan descartadas, no se
toca ni `grilla_pdf.py` ni `grilla_operativa.py`. Como alternativa, dejó
abierta una simplificación de DATOS en vez de código (hacer que
`DiasLogica` del bloque de 18-21hs también incluya el sábado, para que
coincida con `DiasVisualizacion` y el desajuste deje de existir en la
práctica) — "si simplifica la lógica"/"eso si es necesario". Evaluado:
no hace falta — el desajuste entre `DiasLogica`/`DiasVisualizacion` del
dato semilla es intencional desde que se armó esta funcionalidad
(documentado en el propio docstring de `bloques_rigidos.py` como
ejemplo explícito de que los dos campos pueden diferir), así que
cambiarlo sería alterar sin necesidad un dato de ejemplo que hoy sirve
justamente para ilustrar esa distinción — se deja tal cual, con el
desajuste visual/lógico aceptado para el sábado 18-21hs (se ve rígido
en la grilla pero sigue siendo flexible a los efectos de
`verificar_bloques_rigidos`, sin el aviso que generaría si fuera rígido
de verdad ese día).

Mismo criterio que DC-07 §3.3 más arriba (decisión documentada, no un
bug): este hallazgo queda cerrado sin cambio de código.

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

## Liquidación: "Saldo de la liquidación anterior" siempre se muestra (hallazgo #33, decisión consciente)

Hallazgo cosmético de la auditoría DC-01/DC-10 (#33, confirmado ❌ SIGUE
en el v2: "'Saldo de la liquidación anterior' se agrega siempre, sin
importar si es $0 — no se omite"). Se implementó la omisión en $0 (ver
`_items_cuenta`, `app/pdf/liquidacion_pdf.py`) y se le mostraron a la
clienta tres PDF de ejemplo (antes/después del caso en $0, más un
tercero con saldo real para confirmar que no cambiaba) — mismo criterio
de "mostrar antes de confirmar" que el resto de esta lista.

**Revertido a pedido explícito de la clienta**: "Sin cambios, que esa
línea se muestre siempre, es decir el saldo de la liquidación anterior,
ya sea a favor del profesional, como pendiente a favor del espacio, o
en cero, que se muestre siempre." El hallazgo de la auditoría queda
cerrado SIN cambio de código — mismo criterio que DC-07 §2.5/§3.3 más
arriba (decisión consciente documentada, no un bug): la línea de saldo
anterior sigue apareciendo siempre en el PDF, en sus tres redacciones de
siempre ("Saldo pendiente..."/"Saldo a favor..."/"Saldo de la
liquidación anterior" a secas para el caso en $0), sin ninguna
condición que la omita.

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

## Novedades: vacaciones/licencias nunca chocan con una aislada ya cargada (auditoría #16, decisión consciente)

Hallazgo de la auditoría (#16): "al cargar una Vacación o Licencia, el
sistema no avisa ni bloquea si ya hay una Reserva Aislada de OTRO
profesional ocupando ese mismo consultorio/horario gracias al lugar que
dejó vacante el profesional ausente". Investigado antes de proponer
nada: `crear_vacacion`/`crear_licencia` en efecto no hacen ningún chequeo
contra `ReservaAislada` — solo `cancelar_vacacion`/`cancelar_licencia` lo
hacen (`aisladas_bloqueadas_por_anulacion`, para impedir anular una
vacación si eso dejaría "huérfana" una aislada que ya ocupó ese lugar).

Confirmado con la clienta que esto no es un hueco: una reserva aislada
SOLO se puede cargar en un consultorio/horario ya liberado por una
vacación/licencia/ausencia existente (`verificar_conflictos_aislada`
exige que el lugar esté libre o vacante) — es decir, el orden real
siempre es "primero se vacía el lugar, después se ocupa". Al CREAR una
vacación/licencia nueva no puede existir todavía ninguna aislada que
dependa de ella (no hay ninguna aislada previa que "choque" con un
vaciado que recién está ocurriendo) — el caso que sí importa (anular una
vacación que una aislada ya está usando) ya está cubierto por el
chequeo que SÍ existe en `cancelar_vacacion`/`cancelar_licencia`.

Hallazgo cerrado sin cambio de código — mismo criterio que otras
decisiones ya documentadas en este archivo (DC-07 §2.5/§3.3, hallazgo
#33): no es un bug, agregar el chequeo sería redundante.

## Registro de ausencias (Vacaciones): combo acotado a reserva activa, cálculo en vivo del período (auditoría #20)

Hallazgo de la auditoría (#20, DC-10 §1.1 F19): "el combo Profesional de
la solapa Vacaciones no se acota a quienes realmente pueden tomar
vacaciones, y no hay ningún cálculo en vivo mientras se eligen las
fechas Desde/Hasta — solo se sabe el impacto real al confirmar". Pedido
explícito de la clienta sobre los dos puntos: "acortá la lista de
alguna manera a que solo se pueda buscar profesionales con reservas
regulares activas. No se pueden cargar vacaciones a quién no tiene
reserva regular. Y sumá el cálculo en vivo, me parece interesante y
útil."

### Combo acotado a reserva regular activa

`_opciones_profesional_vacaciones(conn)` (nueva, `app/gui/pantallas/
novedades.py`) reemplaza, SOLO en `_PanelVacaciones`, el `_opciones_
profesional(self.conn, _CATEGORIAS_TODAS)` genérico que seguían usando
Licencias/Ausencias/Cargos especiales (esas tres pantallas no fueron
parte de este pedido, se quedan igual). Devuelve categoría R/B/E
(`CATEGORIAS_CON_DERECHO_A_VACACIONES`, ya existente) CON una
`ReservaRegular` vigente HOY (mismo criterio de "activa" que `app.
negocio.panel_control._reserva_regular_activa`: `VigenciaInicio <= hoy
AND (VigenciaFin IS NULL OR VigenciaFin >= hoy)`).

Este combo cumple doble función en esta pantalla (elegir a quién
crearle una vacación nueva, Y filtrar el historial de la tabla de
abajo) — acotarlo solo a los elegibles de HOY hubiera dejado sin forma
de filtrar el historial de alguien que ya tiene vacaciones cargadas
pero hoy dejó de reservar regular. Por eso la lista es la UNIÓN de "
elegible hoy" con "ya tiene al menos una `Vacacion` registrada" (un
`OR EXISTS` contra la tabla `Vacacion`, no solo el filtro de reserva
activa) — nadie con historial real desaparece de la lista, aunque ya
no se le pueda cargar una vacación nueva.

### Cálculo en vivo al elegir Desde/Hasta

`simular_vacacion(conn, *, id_profesional, fecha_desde, fecha_hasta)`
(nueva, `app/negocio/vacaciones.py`, devuelve el dataclass `Simulacion
Vacacion`) extrae el cálculo que ya hacía `crear_vacacion` de punta a
punta (valor bonificado, fracción de semana consumida, % de cupo
consumido/restante, la advertencia de "excede el cupo disponible" si
corresponde) SIN llegar a guardar nada — `crear_vacacion` pasa a
delegar en esta función (mismo resultado exacto, confirmado con la
suite completa de `tests/test_vacaciones.py` sin tocarla).

`_PanelVacaciones` suma `self.etiqueta_simulacion_periodo` (un `QLabel`
con `setWordWrap`, ubicado justo debajo de los campos Desde/Hasta, antes
de los tres botones de acción) y `_actualizar_simulacion_periodo`, que
llama a `simular_vacacion` con el profesional/fechas tal cual están
tipeados en ESE momento — conectado a `combo_profesional.
currentIndexChanged` (vía `_profesional_cambio`) y a `campo_desde.
dateChanged`/`campo_hasta.dateChanged` directo, así que se recalcula
sin necesitar ningún botón. Sin profesional elegido, o si `simular_
vacacion` tira `ValueError` (ej. un período que cruza de año), muestra
un guión en vez de romper. También se vuelve a llamar después de Crear/
Anular (el cupo ya consumido cambia, así que la vista previa del mismo
período tiene que reflejarlo).

Tests nuevos en `tests/test_gui_novedades.py`: `test_combo_vacaciones_
solo_incluye_profesionales_con_reserva_regular_activa` (categoría R sin
reserva y categoría sin derecho quedan afuera), `test_combo_vacaciones_
conserva_a_quien_ya_tiene_historial_aunque_hoy_no_califique` (alguien
con una vacación ya cargada sigue en el combo aunque se le cierre la
`ReservaRegular`), `test_simulacion_en_vivo_del_periodo_se_actualiza_al_
cambiar_las_fechas` (guión sin profesional, texto real al elegir
fechas), `test_simulacion_en_vivo_se_recalcula_despues_de_crear_una_
vacacion` (el mismo período muestra un texto distinto después de
confirmar). El test preexistente de "filtra por profesional" se ajustó:
el "otro profesional" que antes era categoría A sin ninguna reserva (ya
no entraría al combo acotado) pasa a ser categoría R con su propia
`ReservaRegular` vigente, preservando la intención original del test
(un profesional elegible sin ninguna vacación cargada muestra la tabla
vacía).

## Grilla y mensajería: se sacan los atajos rápidos desde celdas libres de la grilla semanal (auditoría #21, decisión consciente)

Hallazgo de la auditoría (#21): la "Grilla semanal" (solapa de "Grilla y
mensajería") no ofrece ningún atajo para cargar una vacación/licencia/
aislada/reserva regular haciendo click directo sobre una celda libre —
hay que ir a la pantalla correspondiente y elegir profesional/fecha/
consultorio a mano. Consultada la clienta sobre si esto era lo que
señalaba el hallazgo: confirmó que sí, y decidió explícitamente dejarlo
como está — "dejalo así". Hallazgo cerrado sin cambio de código, mismo
criterio que otras decisiones ya documentadas en este archivo.

## Mensajes predefinidos: variables disponibles en el campo Mensaje (auditoría #24)

Hallazgo de la auditoría (#24): el campo "Mensaje" del diálogo Nuevo/
Editar no muestra en ningún lado qué variables se pueden usar — la
única pista estaba en la leyenda de "Vista previa", DEBAJO de todo el
`PantallaCRUD`, lejos de donde se escribe el mensaje. Consultada la
clienta ("Mostrame o contame mejor esto, sería para hacer algo similar
a la solapa de Textos del sistema..?"): confirmó que sí, y pidió además
poder INSERTAR las variables con un clic ("como selecciono variables")
y, de paso, sumar variables nuevas a futuro aunque hoy no se usen
("por el día de mañana las necesito no está de más tampoco").

### Mecanismo genérico en `crud_generico.py`

`Campo` suma un parámetro nuevo, `variables: dict[str, str] | None =
None` (nombre de variable sin llaves → descripción), solo con efecto en
`tipo="texto_largo"`. Cuando está presente, `_DialogoRegistro` agrega
una fila debajo del campo con una grilla de 4 columnas de botones
(`_armar_fila_variables`, `_COLUMNAS_BOTONES_VARIABLES = 4` — mismo
criterio de grilla fija que la de días de Llaves/Oferta de
consultorios, para que una lista larga de variables no quede recortada
contra el borde del diálogo), uno por variable: clickearlo inserta
`{nombre}` en el cursor del `QPlainTextEdit` sin pisar lo ya tipeado
(`QPlainTextEdit.insertPlainText`), con la descripción como tooltip del
botón (sin alargar la fila con texto largo). El `QPlainTextEdit` real
sigue siendo lo único que guarda `_DialogoRegistro._entradas[campo.
nombre]` (no un widget contenedor) — así la cadena de foco Enter/Tab, la
validación de campo obligatorio y `valores()` no necesitaron ningún
cambio, siguen operando sobre el mismo widget de siempre.

Queda disponible para cualquier catálogo con un campo `texto_largo`, no
solo para Mensajes predefinidos — hoy es el único que lo usa.

### Variables de Mensajes predefinidos: de 4 a 8

`_VARIABLES_MENSAJE` (`app/gui/pantallas/mensajes_predefinidos.py`) es
el diccionario único que alimenta tanto la fila de botones del campo
Mensaje como la leyenda de "Vista previa" (una sola fuente, no dos
listas a mantener). Además de las 4 que ya existían
(`{apodo}`/`{edificio}`/`{unidad}`/`{consultorio}`), se suman cuatro
más, elegidas por ser datos que esta pantalla ya tiene resueltos en su
propio contexto (sin inventar ninguna fuente nueva):

- `{localidad}`: cierra un hueco ya documentado en este archivo ("Localidad
  no tiene ninguna variable propia todavía... queda ahí por paridad con
  el cuadro de diálogo, listo para el día que haga falta un
  {localidad}") — `_variables_ubicacion` suma un cuarto parámetro
  `id_localidad` (independiente de edificio/unidad/consultorio, mismo
  criterio de "sin cascada" que el resto de los campos de ubicación de
  esta pantalla) y resuelve el nombre de la `Localidad` vinculada al
  mensaje, en blanco si no hay ninguna — mismo criterio de "en blanco si
  no hay nada elegido" que edificio/unidad/consultorio. El selector de
  contexto Localidad (ya existía, sin usarlo para ninguna variable) pasa
  a poder pisar también esta.
- `{nombre}`/`{apellido}`/`{tratamiento}`: del profesional elegido en
  "Dirigido a", mismo origen que `{apodo}` — `_apodo_dirigido_a` se
  reemplaza por `_variables_profesional_dirigido_a` (devuelve las
  cuatro juntas, en blanco las cuatro sin ningún profesional elegido),
  para no repetir la misma consulta a `Profesional` cuatro veces.

Tests nuevos en `tests/test_mensajes_predefinidos.py`:
`test_campo_mensaje_suma_variables_al_diccionario_de_campo` (las 8
quedan en `Campo.variables`), `test_dialogo_suma_un_boton_por_variable_
que_inserta_en_el_cursor` (clic inserta en el cursor sin pisar lo
tipeado, tooltip con la descripción), `test_campos_sin_variables_no_
suman_ningun_boton_extra` (un campo `texto_largo` común, de cualquier
otro catálogo, no se ve afectado), `test_localidad_del_mensaje_
sustituye_en_la_vista_previa`, `test_contexto_localidad_pisa_al_
vinculo_del_mensaje_general`, `test_dirigido_a_sustituye_nombre_
apellido_y_tratamiento`.

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

## Auditoría DC-01/DC-10: hallazgos cosméticos #34, #35, #37, #38, #40, #45

Repaso de los hallazgos cosméticos que habían quedado "sin re-verificar"
en la auditoría (#34 a #46) — la clienta los revisó uno por uno,
eligiendo opción por ítem. Los que pedía "dejar así" (#36, #41, #43)
quedan documentados como decisión consciente, sin cambio de código,
mismo criterio que otras decisiones ya registradas en este archivo
(DC-07 §2.5/§3.3). Los de #39 (nombres de archivo), #42 (cargos
especiales en 4 posiciones) y #44 (checks "Combinar..." tildados por
defecto) quedaron pendientes de la clienta, que pidió ver ejemplos
antes de decidir — no implementados todavía.

- **#34 — "Saldo a favor... del profesional" de más**: en
  `liquidacion_pdf.py` (`_items_cuenta`), "Saldo a favor del profesional
  de la liquidación anterior" pasa a "Saldo a favor de la liquidación
  anterior" — mismo texto, sin la aclaración redundante, que ya usaba el
  Mensaje de texto equivalente (`mensajes.py`, "Saldo a favor mes
  anterior").
- **#35 — "Descuento feriado pendiente" vs "Descuento por feriado..."**:
  mismo prefijo que el feriado del mes en curso — pasa a "Descuento por
  feriado (mes anterior) - {día} {fecha}" en vez de una redacción
  distinta para el mismo concepto.
- **#36 — Ajuste saldo atrasado sin sufijo de período**: sin cambios
  (opción elegida por la clienta) — "Ajuste por saldo atrasado" se queda
  como está; el período ya queda implícito por la liquidación que lo
  contiene.
- **#37 — Cuota sin "/Total"**: "Cuota {N} del plan de pagos" pasa a
  "Cuota {N}/{Total} del plan de pagos". El total de cuotas
  (`PlanPago.CantidadCuotas`) no llegaba a esta consulta — se suma a la
  query de `CuotaPlan` en `liquidaciones.calcular_liquidacion` (join
  contra `PlanPago`, ya existente para resolver `IdProfesional`).
- **#38 — Edificio mencionado siempre, no solo si hay +1**: mismo
  criterio que ya usan Placas y el pie de foto de Oferta de
  consultorios, trasladado a `liquidacion_pdf.py`. `_lugar` suma un
  parámetro `mostrar_edificio` (default `True`, no rompe ningún llamador
  existente) que los cuatro `_texto_*` (horas agregadas, feriado
  trabajado actual/anterior, aislada) reenvían. `generar_pdf_
  liquidacion` lo calcula una sola vez por documento: la unión de los
  edificios de las reservas regulares (`edificios_bloques`, ya se
  calculaba ahí) con el edificio de cada ítem puntual de horas
  agregadas/feriados trabajados/aisladas — no alcanza con mirar solo las
  reservas regulares, una aislada en un edificio distinto del habitual
  también cuenta para la cuenta de "cuántos edificios distintos
  aparecen en este documento".
- **#40 — Período de valores nunca usa "al"**: el conector pasa de "y" a
  "al" en los dos PDFs que comparten `rango_actualizacion`
  (`liquidacion_pdf.py` y `propuesta_pdf.py`) — es un RANGO continuo
  (desde/hasta), no una lista de fechas sueltas, así que "al" describe
  mejor la relación que "y".
- **#41 — Localidad sin guiones**: sin cambios (opción elegida por la
  clienta) — sigue en su propia línea bajo el logo, sin "- Localidad -".
- **#42 — Cargos especiales en 2 posiciones**: pendiente, ver más abajo.
- **#43 — Punto final faltante**: sin cambios (opción elegida por la
  clienta) — "Corresponde a X, Y" se queda sin el punto final en
  `mensajes.py`.
- **#45 — Reserva aislada que cruza medianoche**: `crear_reserva_
  aislada` (`app/negocio/reservas.py`) suma una validación al principio
  (`hora_fin <= hora_inicio` → `ValueError`) — antes no se chequeaba en
  absoluto, y el formulario (dos `QDoubleSpinBox` independientes) de
  hecho dejaba cargar un horario cruzado (ej. 23 a 1), calculando un
  monto negativo en silencio. No se implementó el "partido en dos
  líneas" que pedía originalmente el documento (opción (a) elegida por
  la clienta: bloquear es más simple y evita el dato inconsistente; el
  caso de una reserva que de verdad cruza medianoche sigue sin estar
  soportado, pero ya no se puede cargar mal por error de tipeo). La GUI
  no necesitó ningún cambio: `_PanelReservasAisladas._crear` ya
  atrapaba `ValueError` y lo mostraba en un cartel, mismo mecanismo que
  cualquier otra validación de esta función.
- **#46 — Viñetas del Mensaje 2 Variante A**: cerrado sin acción —
  obsoleto, el mensaje se reescribió por completo en una ronda anterior
  (prosa plana, sin viñetas) y no queda estructura contra la cual
  comparar el hallazgo.

Tests nuevos: `tests/test_pdf_liquidacion.py` (`#34`: ajustada la
aserción existente de "a favor"; `#35`:
`test_feriado_pendiente_usa_el_mismo_prefijo_que_el_del_mes_en_curso`;
`#37`: `test_cuota_de_plan_muestra_numero_sobre_el_total`; `#38`:
`test_hora_aislada_omite_el_edificio_con_un_solo_edificio_en_el_
documento`/`test_hora_aislada_menciona_el_edificio_cuando_hay_mas_de_
uno`; `#40`: ajustada la aserción existente de frecuencia de
actualización). `tests/test_reservas.py` (`#45`:
`test_crear_reserva_aislada_que_cruza_medianoche_falla`/`test_crear_
reserva_aislada_hora_fin_igual_a_hora_inicio_falla`).

### #39, #42, #44: los tres resueltos (con ejemplos mostrados antes de implementar)

Los tres habían quedado pendientes de que la clienta viera ejemplos
concretos antes de elegir. Los tres ya se resolvieron sobre la
respuesta que dio viendo esos ejemplos.

- **#39 — Nombre de archivo de Liquidación, sin sufijo de código**:
  decisión final de la clienta, distinta de lo que sugería el hallazgo
  original ("le falta 'mensual'") — el nombre ideal que dio fue
  "2026-08 - Liquidación Lic. Marcela Lo Veci" (sin "mensual", sin el
  "R1" del código). `nombre_archivo_liquidacion` (`liquidacion_pdf.py`)
  saca el `sufijo_codigo` por completo — no hace falta para desambiguar:
  cada profesional ya tiene su propia carpeta
  (`Profesionales/{código}`), así que dos profesionales nunca comparten
  directorio aunque coincidiera su nombre. Propuesta/Disponibilidad
  quedan sin cambios, confirmado por la clienta ("ok así").

  Tests actualizados en `tests/test_pdf_liquidacion.py`:
  `test_nombre_archivo_sigue_el_formato_del_documento` (nuevo valor
  esperado, sin sufijo); `test_nombre_archivo_sin_codigo_no_agrega_
  sufijo` se renombra `test_nombre_archivo_nunca_agrega_sufijo_de_
  codigo` y suma `IdCodigo` al profesional de prueba para confirmar que
  el sufijo no aparece NI SIQUIERA cuando el profesional sí tiene
  código cargado (antes el test probaba el caso "sin código", que ya no
  es la distinción relevante).

- **#44 — Una línea por bloque continuo de horas (default sin
  combinar)**: la clienta confirmó el default destildado (ya era así)
  y agregó una precisión real sobre el contenido de esa línea, más allá
  de lo que mostraban mis ejemplos: no es "una línea por reserva aislada
  individual" sino "una línea por bloque CONTINUO de horas" — dos
  reservas del mismo consultorio sin ningún hueco entre medio (el
  `HoraFin` de una coincide con el `HoraInicio` de la siguiente, ej. 10
  a 12 y 12 a 14) tienen que verse como un único rango ("10 a 14hs"), no
  como dos líneas separadas. Esto es distinto de "Combinar misma
  unidad" (que fusiona TODAS las reservas de ese día/consultorio con
  "y de", continuas o no) — ese checkbox no se tocó, sigue con su
  comportamiento de siempre.

  `_agrupar_bloques_continuos` (nueva, `app/negocio/mensajes.py`)
  agrupa, por consultorio, las reservas de un día ordenadas por
  `HoraInicio` y las funde en un mismo bloque mientras no haya hueco;
  reemplaza al `[[f] for f in reservas_dia]` que usaba antes el camino
  SIN combinar (una fila por reserva, sin mirar continuidad).
  `_lineas_reservas_aisladas` arma el texto del horario de forma
  distinta según el camino: con "Combinar misma unidad" sigue uniendo
  con "y de" (sin cambios); sin combinar, arma un único rango de punta a
  punta del bloque (`HoraInicio` del primero a `HoraFin` del último) en
  vez de unir cada reserva por separado.

  Tests nuevos en `tests/test_mensajes.py`:
  `test_detalle_aislada_sin_combinar_une_bloque_continuo_en_una_sola_
  linea` (10-12 + 12-14 se muestran como "10 a 14hs", sin "y de");
  `test_detalle_aislada_sin_combinar_bloque_continuo_no_mezcla_
  consultorios` (la misma hora exacta en dos consultorios distintos NO
  se funde, cada consultorio agrupa sus propios bloques). El test
  preexistente de "sin combinar, cada reserva en su propia línea" usa
  horarios con hueco (10-12 y 14-16, no contiguos) — sigue pasando sin
  tocarlo, porque ese caso ya daba 2 líneas antes y sigue dando 2 líneas
  ahora (el cambio solo afecta a bloques genuinamente continuos).

- **#42 — Cargos especiales en 4 posiciones**: implementado, sí tocando
  lógica, base de datos y formulario (confirmado explícitamente en la
  pregunta de la clienta antes de avanzar — "Avanza con el proceso de
  las 4 posiciones en todo lo que necesites"). Antes solo existía la
  distinción implícita "con llave" (`IdLlave`, un solo concepto
  "Depósito de llave") / "sin llave" (todo lo demás, mostrado en el PDF
  como un único grupo "ítem libre"). Pasa a cuatro Subtipos reales:
  Depósito de llave / Ajuste / Bonificación / Ítem libre.

  `CargoEspecial` suma la columna `Subtipo` (`schema.sql` + migración en
  `app.db.migraciones`, mismo mecanismo `_COLUMNAS_NUEVAS` de siempre,
  default `'Ítem libre'`). Una base ya en uso no puede reclasificar
  retroactivamente Ajuste vs. Bonificación (son indistinguibles sin más
  dato que el `Concepto` de texto libre) — quedan todos en "Ítem libre",
  el default seguro. Lo que SÍ se puede reclasificar con certeza es
  "Depósito de llave": `_clasificar_subtipo_deposito_llave` (migración
  nueva, se llama al final de `aplicar_migraciones`) corre un `UPDATE`
  que pasa a ese Subtipo cualquier fila ya existente con `IdLlave` no
  nulo — sin este paso, una base vieja con depósitos de llave ya
  cargados los mostraría mezclados entre los "ítem libre" del PDF en
  vez de agrupados aparte, como siempre estuvieron.

  "Depósito de llave" sigue siendo exclusivo de `app.negocio.llaves`
  (`asignar_llave`/`devolver_llave`, los únicos dos puntos que crean un
  `CargoEspecial` con `id_llave`) — nunca una elección del operador.
  `crear_cargo_especial` (`app.negocio.pagos`) lo fuerza solo con que
  venga `id_llave`, sin importar qué `subtipo` se le pase (o ninguno);
  sin `id_llave`, exige uno de los otros tres, y si no se indica
  ninguno cae a "Ítem libre" (mismo default que la columna, para no
  romper a ningún llamador de antes de este pedido — ni `llaves.py`, que
  nunca pasó `subtipo`, ni los tests existentes). `registrar_perdida`
  (`app.negocio.llaves`) se revisó y confirmó que NO crea ningún
  `CargoEspecial` (da de baja stock o cierra una Asignación sin
  depósito involucrado) — no necesitó ningún cambio.

  GUI (`_PanelCargosEspeciales`, "Llaves y otros conceptos" → "Registro
  de cargos especiales"): combo nuevo "Subtipo", debajo de "Tipo",
  con los tres editables (Ajuste/Bonificación/Ítem libre — "Depósito de
  llave" nunca se ofrece ahí, es estructural) — sumado a la cadena de
  foco Enter/Tab en ese mismo lugar. La tabla gana una columna "Subtipo"
  (entre Tipo y Concepto, 7 columnas en total) y "Modificar cargo
  especial" precarga el combo con el Subtipo de la fila (un cargo
  "Depósito de llave" ya está bloqueado antes de llegar ahí por
  `_bloqueado_por_llave`, así que el combo nunca necesita ofrecer esa
  cuarta opción). `_PanelEstadoCuentaCargos` (misma pantalla, solapa
  "Estado de cuenta") suma la misma columna "Subtipo" a su tabla de
  solo lectura, mismo criterio de "mismos campos que Registro de cargos
  especiales" que ya documentaba esa clase.

  PDF (`liquidacion_pdf._items_cuenta`): los dos loops viejos
  (`IdLlave is None`/`is not None`) pasan a cuatro, uno por cada
  `Subtipo` en el orden fijo de `SUBTIPOS_CARGO` (Depósito de llave →
  Ajuste → Bonificación → Ítem libre) — mismo criterio de separación
  que ya usaba el Mensaje 1 de WhatsApp.

  Tests nuevos: `tests/test_pagos.py` (default a "Ítem libre" sin
  indicar subtipo, Ajuste/Bonificación se guardan tal cual, subtipo
  inválido se rechaza, "Depósito de llave" se rechaza sin `id_llave`,
  con `id_llave` se fuerza a "Depósito de llave" aunque se pase otro
  valor); `tests/test_migraciones.py` (una base vieja de `CargoEspecial`
  gana la columna con el default correcto, reclasificando solo la fila
  ligada a una llave); `tests/test_gui_novedades.py` (el combo ofrece
  los tres editables sin "Depósito de llave", crear con un subtipo
  elegido persiste y se ve en la tabla, modificar precarga el subtipo
  de la fila, más la actualización de índices de columna en los tests
  ya existentes de esa tabla); `tests/test_pdf_liquidacion.py`
  (los cuatro subtipos quedan en el orden fijo sin importar el orden de
  carga, además del test ya existente de "llave antes que libre", que
  sigue pasando sin tocarlo).

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

## Backup y sincronización: detección de base local desactualizada, "modo local sin sincronizar"

Pedido de la clienta, surgido de una pregunta puntual sobre un escenario
real: "estoy trabajando siempre en una notebook, voy backapeando la
información cuando quiero y aparte se va sincronizando con Google Drive
en forma automática. Por algún motivo necesito de urgencia usar el
sistema en otra máquina... ¿Puedo pedir que baje la info más actualizada
desde el último backup, o que se levante del Google Drive a mi
elección?"

Investigado antes de proponer nada: una parte de esto YA estaba
cubierta. `app.negocio.backup.restaurar_backup` (sección 2: "restauración
automática desde Google Drive") ya existía y `gui_main._ofrecer_
restaurar_backup` ya la ofrecía al arrancar, pero SOLO cuando no hay
ningún archivo de base en esa máquina todavía (instalación nunca usada
ahí). El hueco real: si la máquina de emergencia YA tiene una base
(vieja, de la última vez que se usó ahí hace tiempo), ese chequeo nunca
dispara — el programa abre esa base vieja tal cual está, sin preguntar
nada ni comparar contra lo que hay en Drive.

Pedido explícito de la clienta sobre cómo cerrar ese hueco: "que detecte
de alguna manera que la base de datos local no es la última que se
sincronizó... casi que me obligue a levantar y a usar lo sincronizado.
No quiero que por algún bug la info vieja pise a la nueva." Sobre la
vía de escape de ese bloqueo (consultada por `AskUserQuestion`, con un
agregado propio de la clienta sobre la respuesta): "sin ninguna vía de
escape, pero podría ser con alguna vía de escape que solo me permita
usar el programa localmente SIN QUE SINCRONICEN los cambios que a
partir de ahí se hagan" — así quedó: existe una vía de escape, pero
contiene el riesgo real en vez de solo destrabar el cartel.

### Detección (`app.negocio.backup`)

`Configuracion.UltimoBackupPropio` (TEXT, ISO) guarda el timestamp del
backup que la base viva "dice ser": `generar_backup` lo escribe con su
propio `momento` al terminar, y `restaurar_backup` lo pisa con el
timestamp DEL BACKUP RESTAURADO (no "ahora") — la base restaurada se
"convierte" en esa versión. Comparar fechas de ARCHIVO (mtime del `.db`)
se descartó a propósito: Drive no siempre preserva esa fecha al
sincronizar, y dos relojes de máquina distinta pueden tener un
desfasaje — un valor que vive adentro de los datos mismos, y que viaja
con cada restauración, es más confiable.

`hay_backup_mas_reciente_sin_sincronizar(conn)` es el chequeo en sí: si
en la carpeta de backup (la misma que ya sincroniza Drive) hay un
backup con un timestamp MÁS NUEVO que `UltimoBackupPropio`, lo devuelve
— es la señal de que otra instalación generó un backup más avanzado que
esta copia local. `None` sin carpeta configurada, sin ningún backup
todavía, o si esta base ya está al día (el caso normal de la máquina de
uso diario: tu propio backup más reciente nunca puede quedar "más nuevo
que vos misma", y un backup restaurado tampoco, porque hereda
exactamente ese timestamp).

Migración (`app.db.migraciones._inicializar_ultimo_backup_propio`): una
base ya en uso recibe la columna en NULL por el `ALTER TABLE` genérico
— se inicializa sola a "ahora" (no se deja en blanco) para que el día de
la actualización no dispare una alarma falsa contra backups que ya
estaban sincronizados de antes de que existiera este chequeo. Corre en
cada `aplicar_migraciones` pero solo toca filas en NULL, así que es
inocua después de la primera vez.

### El cartel bloqueante (`DialogoBaseDesactualizada`, `app/gui/
dialogos_seguridad.py`)

Se dispara en `gui_main.main()`, justo después de abrir la base y antes
del login — no tiene sentido dejar entrar a un mundo de datos que se
sabe desactualizado. Tres caminos, sin ningún botón de "seguir igual"
visible a simple vista (pedido explícito, "casi que me obligue"):

- **"Restaurar y continuar"**: pide la carpeta de Drive y llama a
  `restaurar_backup`. `gui_main.main()` (no el diálogo) es quien cierra
  la conexión vieja ANTES de que `restaurar_backup` reescriba el
  archivo — una conexión todavía abierta encima del mismo archivo puede
  fallar al reescribirlo, sobre todo en Windows (no se puede reescribir
  un archivo que otro proceso tiene abierto) — y abre una nueva después.
- **"Continuar sin sincronizar"**: pide la contraseña maestra (sin
  contraseña maestra configurada todavía, esta vía queda inhabilitada
  por completo — no hay nada contra qué verificarla) y, si es correcta,
  activa el "modo local, sin sincronizar" (ver abajo).
- **"Salir del programa"**: cierra la aplicación sin tocar nada.

El diálogo no actúa sobre la base directamente — devuelve la decisión
en `self.accion` para que `gui_main.main()` la ejecute con el orden de
conexión/archivo correcto.

### "Modo local, sin sincronizar"

Un archivo marcador al lado de la base (`{db}.sin_sincronizar`, mismo
patrón que el lock de `app.negocio.instancia_unica.
BloqueoInstanciaUnica` — un archivo chico junto al `.db` en vez de una
columna DENTRO de la base, para que siga siendo visible aunque la base
misma esté desactualizada o corrupta). Mientras esté presente:

- `generar_backup` se niega a correr (`ValueError`) — ni el botón manual
  "Generar backup ahora" de Panel de control ni el backup automático del
  avance de mes pueden escribir en la carpeta sincronizada a Drive. Esto
  es lo que de verdad contiene el riesgo: nada generado desde esta rama
  diverge puede llegarle a Drive y pisar la cadena de backups legítima
  que sigue avanzando en otro lado.
  - "Avanzar de mes" en sí NO se bloquea — ya estaba diseñado para que
    un backup fallido (sin carpeta configurada, error de disco, etc.)
    no frene el resto del proceso (`_generar_backup_previo` atrapa el
    error y sigue, dejando `backup_generado=False` en el resumen); con
    el modo activo, el backup simplemente no se genera y el resumen lo
    refleja igual, sin necesitar ningún cambio en `avance_mes.py`.
- Panel de control muestra un aviso permanente en rojo, arriba de todo
  (`_PanelAvancePeriodo.etiqueta_modo_sin_sincronizar`) — no un cartel
  que se cierra y se olvida, tiene que seguir ahí mientras el modo esté
  activo, recalculado en cada `actualizar()`.
- Al volver a abrir el programa en esa misma máquina mientras el modo
  sigue activo, NO se vuelve a mostrar el cartel bloqueante ni se pide
  la contraseña de nuevo — ya quedó registrado que se entró así a
  propósito. El aviso permanente de Panel de control sigue ahí como
  recordatorio constante.
- Se desactiva solo, automáticamente, en el momento en que se restaura
  un backup de verdad en esa máquina (`restaurar_backup` lo borra al
  final) — volver a la cadena de backups legítima es, justamente, lo
  que levanta la cuarentena.

**Lo que esto NO resuelve, documentado a propósito**: si en esa
emergencia se cargó algo importante que no está en la rama "buena", el
sistema no tiene forma de fusionar automáticamente esos dos mundos — la
reconciliación (volver a cargar eso en la instalación principal, o lo
que corresponda) queda en manos del operador. Esta función solo evita
que lo viejo pise a lo nuevo sin que nadie se entere; no resuelve el
merge.

Tests nuevos: `tests/test_backup.py` (`UltimoBackupPropio` se actualiza
al generar y al restaurar un backup — con el timestamp del backup
restaurado, no "ahora"; `generar_backup` falla y no crea nada en modo
sin sincronizar; `restaurar_backup` desactiva el modo; activar/
desactivar/consultar el marcador; `hay_backup_mas_reciente_sin_
sincronizar` en sus distintos casos — sin carpeta, sin backups, con el
propio último backup, detecta uno de otra instalación, no alerta si es
anterior o igual, sin ningún `UltimoBackupPropio` registrado todavía).
`tests/test_migraciones.py` (inicialización en una base vieja sin la
columna, no pisa un valor ya real, idempotencia, tabla `Configuracion`
inexistente no rompe). `tests/test_gui_dialogos_seguridad.py`
(`DialogoBaseDesactualizada` en sus tres caminos, más la contraseña
incorrecta/cancelada y sin contraseña maestra configurada).
`tests/test_gui_panel_control.py` (el aviso permanente oculto por
defecto, visible con el modo activo).

## Metodología de trabajo

Revisión "uno por uno", pantalla por pantalla, con la clienta. Un cambio
de estilo se prueba primero en la pantalla que se está revisando; si lo
aprueba y es de alcance general, se sube a `estilos.py` para que aplique
a todas las que ya usan ese objectName (no hace falta retocar cada
pantalla). A veces se prueba algo y se desestima (ej. gris en los
botones) — en ese caso se revierte al valor anterior, no queda a mitad
de camino. Después de cada ronda: pyflakes limpio, suite completa sin
regresiones nuevas (los ~15 fallos preexistentes de mensajería/pagos/
liquidaciones no están relacionados con la GUI y no se tocan acá),
captura de pantalla con Qt offscreen/xvfb para verificar visualmente
antes de dar la pantalla por cerrada.

Las capturas que se le envían a la clienta se nombran
"{Sección} - {Formulario} - {Solapa}.png" (pedido explícito de la
clienta, para no tener que renombrarlas ella a mano) — ej. "Sistema -
Panel de control - Avance de período y backups.png". Sección es
"Sistema"/"Operativa diaria" (las dos categorías del menú), Formulario
el nombre del `Seccion` del menú, Solapa el texto de la pestaña
mostrada (si la pantalla no tiene solapas, se omite esa tercera parte).

## Primera tanda de correcciones post-v1 (lógica ante todo, lo visual queda
## para otra ronda)

Ya con el sistema instalado y en uso real por primera vez, la clienta
empezó a anotar bugs/ajustes mientras seguía probando, con un pedido
explícito sobre el orden de trabajo: "me voy a tratar de concentrar más
en lo otro" (la lógica, no lo visual) y "no largues la nueva versión
hasta que yo te diga, solo hace las correcciones" — los diez puntos de
esta tanda se implementaron de punta a punta, pero sin dar por lanzada
ninguna versión nueva todavía.

### Ventana maximizada al iniciar

`gui_main.main()`: `ventana.show()` pasa a `ventana.showMaximized()`.
Pedido directo, sin alternativas que evaluar.

### Indicador visual de foco (acotado a botones, con el porqué documentado)

"Toco Tab, pasa de botón en botón, pero no veo dónde estoy parado."
Investigado antes de tocar nada: `hoja_estilos()` nunca había tenido
ninguna regla `:focus` — el estilo propio de `botonPrimario`/
`botonSecundario` (fondo + borde negro) le ganaba al rectángulo de foco
nativo que dibuja el estilo base de Qt, dejándolo invisible.

Se probó `outline` (en vez de `border`) a propósito: no ocupa espacio
de layout, así que un botón no "salta" un par de píxeles al ganar o
perder el foco (lo que sí pasaría agrandando el borde en `:focus`).
Color nuevo, `COLOR_FOCO = "#FFC107"` (ámbar) — ninguno de los colores
ya existentes (azul de marca, naranja de selección de fila, rojo de
alerta) servía sin generar confusión con otro significado ya asignado.

**Verificado con capturas reales antes de darlo por bueno** (mismo
criterio de todo este documento: medir, no asumir) — `outline` resultó
NO ser parejo entre tipos de widget en este Qt: se pinta bien en
`QPushButton` (confirmado con captura y con muestreo de píxeles), pero
no se pintó en absoluto en `QComboBox`/`QDateEdit`/`QSpinBox`/
`QCheckBox`/`QPlainTextEdit`/`QTextEdit`/`QTabBar::tab` (comprobado con
el mismo método de muestreo, ninguno mostró el color). `QLineEdit` no
necesitó nada: ya tenía su propio foco nativo visible (borde celeste)
desde antes.

Para esos otros tipos de widget SÍ hubiera funcionado `border`, pero a
costa de agregarles un borde (reservado, transparente cuando no hay
foco) que no tienen hoy — comprobado que eso les cambia el look en
reposo (pierden el marco nativo 3D/sundido que ya traían). Es un cambio
visual real, y la clienta pidió explícitamente concentrarse en lógica
por ahora — se dejó la regla acotada a `QPushButton:focus` nada más,
documentado en el propio comentario de `estilos.py` para que quede
registrado por qué no se generalizó, con el camino (border reservado)
ya investigado para cuando se retome en la ronda visual.

Tests: `test_boton_tiene_anillo_de_foco_en_la_hoja_de_estilos` (texto
del QSS) y `test_boton_primario_muestra_el_anillo_de_foco_al_recibir_
foco_real` (captura + muestreo de píxeles contra `COLOR_FOCO`, no solo
el texto — mismo motivo que el resto de esta sección: `outline` no se
garantiza parejo).

### Renombre del programa a "SistemaDF" (versión "v0.1")

Pedido explícito: el PROGRAMA pasa a llamarse "SistemaDF", sin importar
qué espacio lo use — distinto de `Configuracion.NombreEspacio` (el
nombre del NEGOCIO, editable desde la app, sigue siendo "Espacio Ramos
Consultorios" u otro que se cargue ahí). `app/version.py` (nuevo) es la
fuente única: `NOMBRE_PROGRAMA = "SistemaDF"`, `VERSION = "v0.1"`,
`NOMBRE_Y_VERSION` para el título de ventana.

Alcance del renombre — todo lo que es branding del PROGRAMA, nada que
sea branding del NEGOCIO:
- Título de la ventana principal (`VentanaPrincipal`, ahora "SistemaDF
  v0.1" — cumple de paso el pedido de mostrar la versión) y del diálogo
  de login ("SistemaDF — Ingresar"/"Crear administrador").
- Los dos `QMessageBox` de `gui_main.py` que usaban el nombre viejo como
  título (instancia ya abierta, ofrecer restaurar backup).
- El mensaje de `InstanciaYaAbierta` ("Ya hay otra sesión del sistema
  abierta...", sin el nombre viejo hardcodeado).
- El `ArgumentParser` de `main.py` (CLI).
- El nombre sugerido de la planilla de importación descargable
  (`Plantilla_Importacion_SistemaDF.xlsx`, en la GUI y como default del
  comando `generar-plantillas`).
- El spec de PyInstaller: `espacio_ramos.spec` se renombra
  `sistemadf.spec` (`git mv`, conserva el historial), y el nombre del
  `.exe`/la carpeta de salida pasan de `EspacioRamos`/`dist/EspacioRamos`
  a `SistemaDF`/`dist/SistemaDF`.
- Docstrings de `app/db/connection.py`/`app/repositorio/base.py` (solo
  texto, sin efecto en runtime).
- README.md y `docs/MANUAL_INSTALACION.md`: todas las rutas/comandos de
  ejemplo actualizados al nombre nuevo.

Lo que **no** se tocó, a propósito: `Configuracion.NombreEspacio` y su
fallback `"Espacio Ramos Consultorios"`/`"Espacio Ramos"` en
`oferta_busqueda_texto.py`/`pdf/estilos.py`/`pdf/placas_pdf.py`/
`pdf/oferta_pdf.py`/`pdf/propuesta_pdf.py`/`pdf/disponibilidad_pdf.py`
(el nombre del NEGOCIO, confirmado en cada uno que es eso y no
branding del programa) y el nombre del repositorio de GitHub (fuera del
alcance de este pedido, cambiarlo rompería la identidad de la sesión).

**Validado de nuevo tras el renombre** (mismo criterio que la primera
vez, ver sección de instalación): se volvió a correr `pyinstaller
sistemadf.spec` completo en este entorno Linux — build sin errores,
carpeta de salida y `.exe` ya con el nombre `SistemaDF`, arranque
offscreen limpio contra una base sin inicializar — confirma que el
renombre no rompió el empaquetado.

### Importación: no duplicar registros ya existentes

"Que no importe los registros que son iguales para evitar que se
dupliquen." Investigado: `importar_hoja` nunca había comparado contra
lo ya cargado — cada fila válida llamaba `repo.crear(**datos)` sin
condición, así que reimportar la misma planilla (o una que se
superpone) duplicaba todo sin avisar.

`_ya_existe_identico(conn, tabla, datos)` (nueva,
`app/importacion/importar_excel.py`): compara por igualdad EXACTA
(NULL incluido) contra la tabla, sobre todas las columnas presentes en
`datos` DESPUÉS de resolver referencias — "registros iguales", en el
sentido literal que pidió la clienta, no una coincidencia por clave
natural inventada. Una fila "parecida" pero con un solo campo distinto
(ej. un CampoLibre corregido) no cuenta como duplicado, se importa
igual. Se llama una sola vez, genérico para las ~12 entidades
importables (mismo nombre de entidad = nombre de tabla en todas), justo
antes del `try` que crea el registro — ANTES de cualquier columna que
la propia importación agregue sola (importa para Llave: el chequeo
corre sobre Tipo/ValorDepositoActual/Observacion, antes de que se le
asigne `Nombre` — autogenerado, siempre distinto, comparar con eso
nunca encontraría un duplicado real). Para PlanPago corre contra la
tabla `PlanPago` antes de `_crear_plan_pago_importado`, evitando
también duplicar sus `CuotaPlan`.

`ResultadoImportacion` suma `filas_duplicadas: int` (no se mezcla con
`errores` — un duplicado no es un error, es información). GUI
(`_PanelImportacion`): la tabla "Resultado por hoja" suma una columna
"Duplicados (no importados)", y el cartel final sincero sobre cuántas
filas se saltearon por ya existir. CLI (`main.py`): la línea de resumen
por hoja menciona el número de duplicados.

Tests: `tests/test_importacion.py` (reimportar la misma planilla no
duplica y lo reporta; una fila con un campo distinto SÍ se importa, no
cuenta como duplicado; Llave duplicada no se vuelve a crear pese a que
`Nombre` sería distinto en cada intento; PlanPago duplicado no genera
un segundo juego de `CuotaPlan`). `tests/test_gui_importacion.py` (la
columna nueva muestra el conteo correcto, antes y después de
reimportar).

### Tecla Delete = botón "Eliminar" (o su equivalente: Anular/Cancelar/
### Liberar/Descartar/Quitar), en todo el sistema

"Si presiono Delete en alguna fila de alguna tabla... que me ofrezca
eliminar como si tocara el botón 'Eliminar' de cada solapa." Mecanismo
nuevo y genérico, `app/gui/widgets/eliminar_tecla.py`
(`instalar_eliminar_con_tecla(widget, accion)`): instala un filtro de
eventos sobre la tabla (o lista) que, al recibir `Key_Delete`, llama
DIRECTO al mismo método que ya usa el botón correspondiente — no
duplica ninguna validación (selección vacía, confirmación, guardarraíl
de integridad referencial): es, literalmente, la misma llamada que ya
hacía el botón. Mismo criterio de referencia débil que `OrdenTabla`
(`app/gui/widgets/orden_tabla.py`) para `accion` — evita el mismo ciclo
panel → objeto → panel ya documentado ahí, con el mismo riesgo de
segfault al destruir muchos paneles seguidos (tests).

Sirve tanto para `QTableWidget` como para `QListWidget` (ej. la lista
de documentos de Profesionales, la lista de franjas de Oferta) — el
filtro de eventos no depende de ningún método propio de tabla.

**Cobertura, pantalla por pantalla** (la acción real detrás de Delete
varía: no todas las pantallas tienen un botón literal "Eliminar" — se
usó el botón equivalente más cercano de cada una):

- `crud_generico.PantallaCRUD` (un solo lugar, cubre de rebote TODOS
  los catálogos genéricos — Localidades/Edificios/Unidades/
  Consultorios/Responsables/Tipos de licencia/Condiciones y normas/
  Profesiones/Gastos operativos/Fechas especiales/Listas editables/
  Detalles complementarios/Mensajes predefinidos/Profesionales): Delete
  → `self._eliminar` (ya validaba selección y pedía confirmación, sin
  cambios ahí). En modo `solo_lectura` no se instala nada (no hay
  `_eliminar` que llamar).
- Reservas (`reservas.py`, las tres solapas): Regulares → `_finalizar_
  vigencia` (no hay "Eliminar" literal, es el equivalente real);
  Aisladas y Extraordinaria → `_cancelar`.
- Registro de ausencias (`novedades.py`, las cuatro tablas con alta):
  Vacaciones/Licencias/Ausencias → `_cancelar` (etiqueta de botón
  "Anular..."); Cargos especiales → `_eliminar`.
- Llaves (`llaves.py`): Tipos → `_eliminar_tipo`; Accesos → `_eliminar_
  acceso`. Movimientos no tiene ninguna acción de "sacar una fila" (es
  un historial), no se tocó.
- Pagos (`pagos.py`): Registrar pagos → `_eliminar`; Planes de pago →
  `_cancelar` ("Cancelar plan seleccionado"). Estado de cuenta es de
  solo lectura, sin acción, no se tocó.
- Placas para timbres (`placas.py`, solapa operativa): → `_liberar`
  ("Liberar posición de placa").
- Bloques rígidos (`bloques_rigidos.py`): → `_eliminar`.
- Gestor de archivos del espacio (`imagenes.py`): → `_eliminar`.
- Lista de espera (`lista_espera.py`): → `_descartar` ("Descartar
  pedido").
- Oferta de consultorios (`oferta.py`, lista "Franjas agregadas a esta
  búsqueda"): → `_quitar_franja_seleccionada`.
- Profesionales (`profesionales.py`, lista de documentación adjunta):
  → `_eliminar_documento`.

Pantallas revisadas y descartadas a propósito (sin ninguna acción de
"sacar una fila" que mapear): Estadísticas (solo lectura), Centro de
mensajería (solo marca "Enviada", no borra nada), Usuarios y permisos
(solo desactivar vía Editar, sin baja), Configuración general (no es
una tabla de registros). Los formularios compuestos que agrupan
pantallas ya cubiertas (Disponibilidad, Llaves y otros conceptos,
Grilla y mensajería, Base datos del espacio, Archivos y listas, Placas
para timbres, Balance del negocio, Valores) no necesitaron ningún
cambio propio — el cableado vive en el panel real que ya usan.

Tests: `tests/test_eliminar_tecla.py` (el mecanismo en sí: dispara con
Delete, no con otra tecla, no sostiene vivo al dueño del método atado
— mismo criterio de test que `OrdenTabla` —, y una tecla sin acción
viva no rompe nada). Un test de integración real (tecla de verdad vía
`qtbot.keyClick`, no llamar al método a mano) por cada pantalla recién
cableada: `test_crud_generico.py` (catálogo genérico, con y sin
selección, y confirmando que en modo `solo_lectura` no hace nada),
`test_gui_reservas.py` (las tres solapas), `test_gui_llaves.py`
(Tipos), `test_gui_pagos.py` (Registrar pagos).

### Botón "Restaurar backup" en Panel de control (elegir cuál, no
### siempre el más reciente)

Pedido explícito, siguiendo una sugerencia propia de una ronda
anterior: hasta ahora `restaurar_backup` solo se disparaba en dos vías
automáticas (instalación nueva, base desactualizada) y siempre tomaba
el backup MÁS RECIENTE, sin dejar elegir. Se refactorizó
`app/negocio/backup.py` sin romper ninguna de las dos vías existentes:

- `restaurar_backup_desde(origen, db_path)` (nueva): el mecanismo real
  de restauración sobre un backup YA ELEGIDO — extraído tal cual de lo
  que antes era el cuerpo de `restaurar_backup` después de encontrar
  `origen`, sin ningún cambio de comportamiento.
- `restaurar_backup(carpeta_backups, db_path)` (la de siempre, sin
  cambiar su firma ni su contrato): ahora es un wrapper de una línea
  — busca el más reciente y delega en `restaurar_backup_desde`.
- `listar_backups(carpeta)` (nueva): todas las subcarpetas "Backup
  AAAA-MM-DD HHhMM", de la más nueva a la más vieja — para ofrecer una
  lista real en vez de "siempre el último".

GUI (`_PanelAvancePeriodo.boton_restaurar`, debajo de "Generar backup
ahora", mismo ancho/criterio de fila con su propia explicación al
lado): elige carpeta (sugiere la ya configurada), lista los backups de
ahí (`listar_backups`), deja elegir uno (`QInputDialog.getItem`, el más
reciente como default), confirma con el nombre elegido y una
advertencia explícita de que el programa se va a cerrar.

**Por qué se cierra el programa después de restaurar** (no es una
limitación aceptada a medias, es la única forma segura con la
arquitectura actual): `self.conn` es la MISMA conexión SQLite
compartida por todos los paneles de la ventana ya construida — cerrarla
acá para poder sobreescribir el archivo (mismo motivo documentado para
las dos vías automáticas: una conexión abierta encima del archivo
puede fallar al reescribirlo, sobre todo en Windows) deja a cualquier
OTRO panel con una conexión muerta si se sigue usando el programa. No
hay forma de "pasarle" una conexión nueva a todos los paneles ya
armados, así que la única salida consistente es cerrar la aplicación
entera (`QApplication.instance().quit()`) después de restaurar — el
sistema operativo libera el lock de instancia única solo con que el
proceso termine, sin necesitar tocar `BloqueoInstanciaUnica` desde acá.

Tests: `tests/test_backup.py` (`listar_backups` — vacío sin carpeta/sin
backups, orden del más nuevo al más viejo; `restaurar_backup_desde`
elige puntualmente uno que NO es el más reciente, a diferencia de
`restaurar_backup`). `tests/test_gui_panel_control.py` (botón
secundario del mismo ancho que "Generar backup ahora"; cancelar en
cualquier paso no rompe ni toca la conexión; caso de punta a punta con
una conexión NUEVA después — ya que la vieja se cierra — confirmando
que el archivo en disco volvió al estado del backup elegido y que
`QApplication.quit` se llamó).

### Orden natural de códigos de profesional en tablas (letra + número
### completo, no dígito a dígito)

"X1, X10, X11, X2... no va. X1, X2, X3, X4, X10, X11... X234 sí va.
Primero por letra, después por la cadena de números completa." El
orden alfabético puro que usaban las tablas comparaba texto, así que
"R10" quedaba antes que "R2". Ya existía una versión correcta de esto,
pero aislada en un solo lugar (`mensajeria._clave_codigo`, para la
columna "Código" de Centro de mensajería) y con una limitación que
nunca se había notado porque ahí nunca hacía falta: solo funcionaba
con el código SOLO, se rompía si el texto traía algo más después (el
caso real en el resto del sistema: "R12 - Lic. Juan Pérez", la columna
"Profesional" con código + nombre juntos).

`clave_orden_codigo(texto)` (nueva, `app/gui/widgets/orden_tabla.py` —
mismo archivo que ya tenía `OrdenTabla`, concepto relacionado): separa
el prefijo alfabético del principio y la cadena de dígitos que sigue
(regex `^(\D*)(\d+)`, no "todo lo que sigue"), e ignora cualquier texto
después — por eso funciona igual de bien con un código solo ("R12") que
con código + nombre ("R12 - Lic. Juan Pérez"). Reemplaza a la versión
vieja de `mensajeria.py` (que se saca, sin otro usuario) y se aplica en
todos los lugares que ordenaban por código o por el texto combinado de
"Profesional":

- `crud_generico.py`: la columna `IdCodigo` del catálogo de
  Profesionales (por nombre de campo, no hizo falta un tipo de `Campo`
  nuevo — ningún otro catálogo tiene esta columna).
- `reservas.py` (las tres tablas, columna "Profesional"),
  `novedades.py` (las cuatro tablas, orden por click Y el orden por
  defecto al construir), `pagos.py` (las dos tablas), `placas.py`
  (columna "Profesional" armada aparte como texto), `llaves.py` (tabla
  de Movimientos, orden por click y por defecto).
- `liquidacion.py`: el orden por defecto de "Emisión de archivos" (no
  tiene click-to-sort) pasa de `_numero_codigo` (solo el número,
  ignorando la letra — podía mezclar categorías) a este.

Tests: `tests/test_orden_tabla.py` (la función en sí: número completo
no dígito a dígito, agrupa primero por letra, funciona con texto
después del código, sin número cae a orden de texto, vacío/`None` no
rompe). `tests/test_profesionales.py` (click en "Código" del catálogo
real ordena natural, no alfabético).
