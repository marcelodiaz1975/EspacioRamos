# Historial archivado — Archivos y listas: Gestor de archivos, tipo Enlace, Textos del sistema

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

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

