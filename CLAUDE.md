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
