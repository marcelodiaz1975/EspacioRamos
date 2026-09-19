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

## Tablas

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
propio `QTabWidget` armado a mano (Placas, Liquidación, Aumentos y
descuentos, Grilla operativa, Novedades, Reservas, Pagos, Gestor de
archivos, Lista de espera) no se tocaron todavía — si al revisarlas se
ve el mismo defecto, aplicarles el mismo combo ahí.

Pedido explícito de la clienta (al revisar Consultorios): a partir de
ahora, TODO catálogo que se revise de acá en adelante suma tres campos
libres (`CampoLibre1/2/3`, texto opcional, sin validación) al final de
su lista de `Campo` — no solo cuando lo pide puntualmente. Ya aplicado a
Localidades, Edificios, Unidades, Consultorios, Responsables, Tipos de
licencia, Condiciones y normas, Detalles complementarios (Propuesta),
Profesiones y Gastos operativos; falta sumarlo al resto a medida que se
van revisando. Cada uno
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
pedido explícito de la clienta) va "Subtotal del período": la suma de
Monto de todos los gastos de ese período (no solo los visibles después
de "Buscar", que es un filtro aparte) — se recalcula cada vez que
cambia el período o se crea/edita/elimina un gasto.

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
  puntual de esa pantalla, no aplicado (todavía) al resto.

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
