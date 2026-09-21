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

- **Montos = "monto real facturado", pero a nivel BRUTO.** No hay forma
  de leer un monto histórico neto por categoría: `LiquidacionEmitida.
  MontoGenerado` es un total ya combinado (regular + aisladas + cargos +
  ajustes, todo junto, sin desglose guardado), y los descuentos por
  volumen de horas semanales (`app.negocio.valores.
  obtener_porcentaje_descuento`) se calculan por profesional sobre TODAS
  sus reservas del sistema, así que no hay un criterio no inventado para
  repartirlos de vuelta a un edificio/unidad/consultorio puntual. Se
  optó por un cálculo bruto (antes de esos descuentos y ajustes), día
  por día del período, a los valores vigentes de cada consultorio —
  mismo criterio que `app.negocio.valores.valor_regular_por_rango_dias`,
  acá acotado por consultorio en vez de por profesional
  (`monto_bruto_regular_periodo`/`monto_bruto_aislada_periodo`). Queda
  pendiente de confirmar con la clienta si este nivel "bruto" le sirve
  o si prefiere que se acote el alcance de otra forma.
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
   función, reusa `calcular_ocupacion`/`monto_bruto_aislada_periodo` de
   `app.negocio.estadisticas`): % de ocupación regular general, horas
   regulares reservadas por semana en este momento, horas aisladas
   confirmadas del mes en curso, monto que generaron esas horas
   aisladas (bruto, mismo criterio que Estadísticas), y "saldo pendiente
   de cobro este mes" — interpretado como lo facturado del período
   (`LiquidacionEmitida.MontoGenerado`) menos lo ya cobrado imputado a
   ese mismo período (`HistorialPagos.Monto`); no hay una única forma
   de calcular esto último en el resto del sistema, así que quedó
   documentado como interpretación propia a confirmar con la clienta.
7. **Alertas**: el mecanismo de siempre (`Alertas`/`calcular_alertas`,
   `_tarjeta_alerta`/`_tarjeta_alerta_simple`, `self.contenedor_alertas`/
   `self.layout_alertas` con los mismos nombres de atributo que antes)
   sin cambios funcionales ("algo más que se te ocurra": en vez de
   inventar contenido nuevo para este último cuadrito, se reaprovechó lo
   que ya existía).

El título de la pantalla sigue mostrando el nombre del espacio tal cual
está cargado en Configuración general (sin `.upper()`) — sigue
pendiente de definir con la clienta si tiene sentido aplicarle el
formato Nivel 1 a un nombre propio; no se tocó en esta vuelta tampoco.

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
