# Historial archivado — Grilla y mensajería: Grilla semanal, Centro de mensajería, Mensajes predefinidos

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

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

## Tercera tanda de correcciones post-v1: Grilla y mensajería

Lista de pedidos puntuales sobre las tres solapas de "Grilla y
mensajería", ya con la clienta usando el sistema instalado — mismo
criterio de la tanda anterior ("no largues la nueva versión hasta que
yo te diga").

### Grilla semanal

- **Scroll horizontal + "Detalle" tapado por la grilla**: investigado a
  fondo (medido con scripts de geometría, el mismo criterio de todo este
  documento) — el mecanismo de scroll horizontal de `self.tabla`
  (`ScrollBarAsNeeded`, correctamente dimensionado, sin que las tablas
  fijas de `activar_filas_y_columnas_fijas()` lo tapen) y la posición de
  "Detalle" respecto de la grilla (sin superposición, en ningún tamaño
  de ventana probado) resultaron correctos en todos los escenarios
  reproducidos. Lo que sí se confirmó, replicando `hoja_estilos()` sin
  ninguna regla propia de `QScrollBar`, es que el scrollbar quedaba a
  merced del estilo nativo de cada instalación — en la plataforma de
  desarrollo (Linux/offscreen) el thumb se pinta en un degradé gris muy
  pálido, casi indistinguible del fondo blanco, aunque funcionalmente
  esté ahí (`isVisible()`, `maximum()` correctos). Se suma una regla de
  `QScrollBar` propia a `estilos.py` (horizontal y vertical, parejo en
  toda la app) con un thumb gris más oscuro y borde negro fino —mismo
  criterio "borde negro fino" que el resto de los controles de esta
  app— para que el scroll se note a simple vista sin depender de qué
  tan buen contraste traiga el tema nativo de turno. De paso,
  `_PanelGrillaSemanal` suma `reservar_alto_scroll_horizontal()` (mismo
  mecanismo ya usado por Oferta de consultorios, la otra pantalla que
  necesita scroll horizontal de forma habitual) como refuerzo — reserva
  de más el alto que ocupa la barra, para que nunca tape la línea
  inferior de la última hora si en algún momento aparece.
- **Líneas de separación de unidad y de la fila "Día de la semana", en
  un color intermedio nuevo**: hasta ahora la grilla solo distinguía dos
  niveles de línea — la fina gris (`#999999`, 1px, la cuadrícula de
  siempre) y la gruesa negra (`#000000`, 3px, exclusiva de los límites
  de DÍA y del marco del bloque de encabezado). Se suma un tercer nivel,
  `_COLOR_LINEA_UNIDAD = "#666666"` a `_GROSOR_MEDIO = 2`px, en el punto
  intermedio pedido por la clienta: las separaciones de UNIDAD (ej. el
  consultorio 7 de un piso contra el consultorio 1 de otro, dentro del
  mismo día) y la línea horizontal que separa la fila "Día de la
  semana" del resto de las filas de encabezado. `_dibujar_bordes_
  gruesos` pasa a reconocer dos sufijos nuevos en el frozenset de
  bordes, `"right_medio"`/`"bottom_medio"` (al lado de los cuatro de
  siempre, sin sufijo = la línea gruesa negra), y `_limites_unidad`
  (nueva, mismo criterio que `_limites_dia` pero comparando `id_unidad`)
  se suma a `_agregar_encabezado_agrupado` (Localidad/Edificio/Unidad —
  cualquier transición de grupo en esas filas que NO sea un límite de
  día cae, por jerarquía, en un límite de unidad), `_agregar_
  encabezado_consultorio` y el loop de datos por hora: en los tres,
  `right_medio` se usa como alternativa a `right` (nunca los dos
  juntos). La fila "Día de la semana" suma `bottom_medio` en todas sus
  celdas (la etiqueta de la izquierda y cada grupo de día) al construir
  esa fila en particular (`fila == primera_fila`).
- **Filtros colapsables (Localidad/Edificio/Unidad), colapso automático
  al elegir un único valor**: pedido explícito, extendido a "todos los
  cuadros similares del sistema" — `_FiltroColapsable` (el widget
  compartido detrás de estos tres filtros en CUALQUIER pantalla que
  embeba `GrillaOperativaWidget`: Reservas, Oferta, Novedades, Grilla
  semanal) suma `_colapsar_si_una_sola_seleccion`, conectada a la misma
  señal `itemSelectionChanged` que ya actualiza el botón-resumen: si
  queda exactamente UN valor tildado (el caso común, un clic simple sin
  Ctrl), colapsa el menú solo. Si queda más de uno (selección múltiple
  con Ctrl+clic en curso), se deja desplegado — colapsarlo en cada clic
  hubiera roto la selección múltiple. Una sola corrección en el widget
  compartido cubre las cuatro pantallas de una.

### Centro de mensajería

- **Orden de código, antes al revés**: `actualizar()` ordenaba, dentro
  de cada color, por código DESCENDENTE (`reverse=True`, con un
  comentario que decía "confirmado por el usuario" de una ronda
  anterior) — la clienta pidió el criterio contrario ("los códigos
  numéricos tienen que estar ordenados en orden ascendente... los
  números están al revés nomás"). Se saca el `reverse=True`: ahora
  ordena ascendente, dentro de cada color.
- **Foco: Tab después de "Mensaje grupal" caía en "Vista previa"**: esta
  solapa nunca había tenido una cadena de foco Enter/Tab propia ("no la
  tenía y sigue sin tenerla", documentado desde que se armó) — Tab
  dependía del orden nativo de Qt, que terminaba cayendo en
  `self.texto_mensaje` (puramente visual, nunca se carga a mano) y,
  sosteniendo Tab ahí, insertaba tabulaciones dentro del mensaje en vez
  de seguir la cadena. Se suma una cadena explícita
  (`instalar_enter_avanza_foco`) con los siete controles reales de la
  columna izquierda (Filtro, Período, los dos checks "Combinar...",
  Copiar mensaje, Actualizar, Mensaje grupal) — a propósito SIN incluir
  `texto_mensaje`: al no tener el filtro instalado, Tab desde "Mensaje
  grupal" (el último de la cadena) se salta ese cuadro por completo y
  vuelve directo a "Filtro".

### Mensajes predefinidos

Investigados a fondo los dos puntos reportados (Tab no avanza desde
"Buscar", y tampoco de "Nuevo" a "Editar"/"Eliminar") con el mismo
criterio de "simular la tecla real, no solo revisar el código" de todo
este documento: reproducido con `QTest.keyClick` tanto contra el panel
aislado como contra el formulario compuesto completo
(`PantallaGrillaYMensajeria`, cambiando de solapa primero, tal como lo
haría la clienta), con y sin texto tipeado en Buscar — en los cuatro
escenarios, la cadena ya instalada por `PantallaCRUD` en modo
`anidado=True` (`[campo_buscar, boton_nuevo, boton_editar, boton_
eliminar]`, con wrap-around de "Eliminar" de vuelta a "Buscar") avanzó
correctamente en los cuatro pasos. No se encontró ningún defecto
reproducible en el código actual — queda documentado por si vuelve a
aparecer en la instalación real, con más detalle de cuándo pasa (recién
abierto el formulario vs. después de cambiar de solapa, por ejemplo)
para poder reproducirlo con precisión.

## Centro de mensajería — batch de pedidos (primera tanda)

Siete pedidos de la clienta sobre esta solapa (`app/gui/pantallas/
mensajeria.py`, negocio en `app/negocio/mensajeria.py`/`mensajes.py`).

### Filtro de visualización arranca en "Todos"

`_FILTRO_DEFAULT` pasa de `"pendientes"` a `"todos"` — reemplaza al
default anterior, mismo criterio simple que otros cambios de default.

### Selector de profesional (filtro visual, antes de Período)

Combo nuevo entre "Filtro de visualización" y "Período": "Todos los
profesionales" por defecto, buscable por código o nombre
(`habilitar_busqueda_profesional`, mismo mecanismo que el resto del
sistema), poblado con `_opciones_profesional(conn, ("R", "A", "X"))`
(reusa el helper de `reservas.py`, cross-import ya establecido —
`placas.py` hace lo mismo). Mismo criterio que "Filtros que solo afectan
la visualización": acota `self._profesionales` en `_listar_filtrados`,
nunca cambia lo que hace un botón. Sumado a la cadena de foco Enter/Tab
justo después del filtro de visualización, y al reset de `reiniciar()`.

### Marrón de R (deuda dentro de tolerancia) se unifica con amarillo

Pedido original: ese marrón pase a verde, "mismo mensaje, todo igual".
Al revisar el impacto (dejaba sin uso el color amarillo, el flag
`MensajePrevioGenerado` y las plantillas de Situación 2/3), la clienta
ajustó la decisión: **amarillo se mantiene como color propio** (pura
diferenciación visual, sin cambiar el tratamiento) en vez de fundirse
también en verde — "en la práctica, al menos por ahora, va a ser lo
mismo que el verde" (mismo mensaje a generar: `mensaje_envio_liquidacion`, ya sea por
botón o por check "Enviada"). `color_profesional` ya no consulta
`MensajePrevioGenerado` para decidir marrón/amarillo — cualquier
`SaldoCuentaAnterior` dentro de la tolerancia es amarillo directo, sin
sub-estado.

El flag `MensajePrevioGenerado` (schema), la función `marcar_mensaje_
previo_generado`, y los mensajes `mensaje_situacion_2`/`mensaje_
situacion_3` (negocio) se dejaron DEFINIDOS pero sin ningún llamador
desde la pantalla — la clienta avisó que "luego seguramente tocamos los
mensajes predefinidos" sobre este punto, así que no se borra nada
todavía (decisión explícita, no descuido: evita tener que re-crear estas
piezas si la retoma pronto).

### Marrón pasa a categoría X con deuda (nuevo, reemplaza el uso anterior)

Marrón, liberado por el punto anterior, se reutiliza para profesionales
categoría X (dejaron el espacio) con `SaldoCuentaAnterior > 0` — **sin
aplicar la tolerancia** (confirmado explícitamente: cualquier deuda
cuenta, por chica que sea, ya que no van a volver a reservar). Un X sin
deuda sigue sin participar del Centro de mensajería (`color_profesional`
devuelve `None`).

Posición en la grilla (`_ORDEN_COLOR`): marrón pasa de ser el PRIMER
color a ser el ÚLTIMO antes de gris — pedido explícito ("que sea el
último color antes de los grises"). Dentro del grupo gris en particular,
los grises de categoría X quedan DESPUÉS de los grises de siempre (R/A):
un tercer `.sort()` (además de código y color, mismo truco de sorts
estables encadenados) con la clave "es gris de categoría X" empuja esas
filas al final de la tabla entera — como gris ya es el último color, eso
coincide exactamente con "al final de ESE grupo" sin tocar el resto del
orden.

Mensaje nuevo (texto exacto pedido por la clienta, variables `{saldo}`/
`{nombre_espacio}`): `mensaje_recordatorio_deuda_profesional_x`
(`app/negocio/mensajes.py`, plantilla editable en "Textos del sistema",
clave `mensaje_recordatorio_deuda_profesional_x`). Usa `_moneda` del
mismo módulo (formato DC-03: "$1.234", sin espacio ni decimales) — SIN
agregar un "$" literal en la plantilla antes de `{saldo}`, mismo
criterio que todos los demás mensajes de este módulo (la plantilla que
pasó la clienta tenía "$ {saldo}" a mano, pero duplicaría el signo).

Botón "Generar texto" sobre un X (marrón o gris): copia el mensaje al
portapapeles y llama a `marcar_recordatorio_deuda_x_generado` (guarda
`Profesional.FechaUltimoRecordatorioDeudaX`, directo en `Profesional` y
no en `EstadoMensajeriaPeriodo` — un X ya no tiene período operativo
propio). Pasados `DiasRecordatorioProfesionalXDejoEspacio` días desde
esa fecha (parámetro nuevo en Configuración general / Valores y
liquidación, por defecto 30), `color_profesional` vuelve a marrón solo —
sin ningún refresco manual de por medio, se recalcula en cada
`actualizar()`. El check "Enviada" (columna propia) queda deshabilitado
para categoría X sin importar el color (marrón o gris): no hay
liquidación que marcar, a diferencia de R/A.

Tests nuevos: `tests/test_mensajeria_negocio.py` (color por deuda,
transición marrón->gris->marrón con `_fijar_fecha`), `tests/test_
mensajes.py` (mensaje nuevo, rechaza categoría distinta de X), `tests/
test_gui_mensajeria.py` (aparece/no aparece según deuda, botón, check
deshabilitado, orden dentro de gris, selector de profesional), `tests/
test_plantillas_texto.py` (conteo de claves +1).

## Mensajes de situaciones de profesionales (DC-03, Reservas aisladas)

Pedido de la clienta, tres partes sobre el mensaje "DETALLE RESERVA
{MES}" (DC-03, `app.negocio.mensajes.mensaje_detalle_reserva_aislada`)
y la solapa "Reservas aisladas":

1. **Bug real reportado**: parada en el período actual, con una hora
   aislada ya confirmada ese mes, agendarle otra al mismo profesional
   para el mes siguiente copiaba al portapapeles un mensaje que mostraba
   SOLO la reserva nueva — el detalle del mes en curso desaparecía por
   completo. A diferencia de generar el mismo mensaje a mano desde el
   Centro de mensajería (que sí mostraba las dos: la del mes en curso
   arriba, la del mes siguiente bajo "RESERVAS POSTERIORES"), porque
   `_PanelReservasAisladas._copiar_mensaje_detalle`/`_PanelReserva
   Extraordinaria._copiar_mensaje_detalle` (`app/gui/pantallas/
   reservas.py`) llamaban a `mensaje_detalle_reserva_aislada` con
   `periodo=fecha[:7]` (el mes DE LA RESERVA recién cargada) en vez de
   `periodo_actual(self.conn)` (el mes de HOY, mismo criterio que ya
   usaba el Centro de mensajería) — esa función solo arma "del mes" (el
   período consultado) y "posteriores" (estrictamente posterior), así
   que la reserva del mes en curso no encajaba en ninguna de las dos
   listas al consultar con el período de la reserva nueva, más adelante
   en el tiempo. Corregido en ambos métodos (ya no reciben el parámetro
   `fecha`, innecesario). Test de regresión: `tests/test_gui_reservas.py
   ::test_crear_reserva_aislada_de_un_mes_posterior_no_pierde_el_detalle_
   del_mes_en_curso`.

2. **Alerta de éxito**: al confirmar una reserva desde "Reservas
   aisladas" sin advertencias, ahora muestra "Reserva asignada con
   éxito." (antes no mostraba nada en ese caso) — mismo criterio "EN
   GENERAL" que el resto del sistema (alerta de éxito aunque no haya
   nada puntual que avisar). Puntual de esta solapa (la clienta la
   llama "proceso de asignación de horas aisladas"); "Reserva
   extraordinaria" no se tocó.

3. **Dirección del edificio arriba del mensaje**: pedido "que tengan
   siempre la dirección a mano" — se agrega, debajo del nombre del
   profesional, una línea "Edificio {nombre}: {Domicilio}, {Localidad}"
   por cada edificio distinto que aparezca en el mensaje (reservas del
   mes + posteriores). Regla propia de ESTE mensaje únicamente (acotada
   a pedido explícito de la clienta — "por ahora solo trabajamos textos
   para pegar al WhatsApp Web por detalle de horas aisladas", no es la
   "regla del edificio" general del resto del sistema, que sigue
   existiendo en `_incluir_edificio_efectivo` para los demás mensajes
   que puedan necesitarla más adelante):
   - La decisión mira solo cuántos edificios DISTINTOS aparecen EN ESTE
     MENSAJE (`edificios_mencionados`), no cuántos haya en todo el
     sistema ni las llaves del profesional.
   - Con más de un edificio en el mensaje: la línea de arriba aparece
     una vez por edificio Y además se sigue aclarando "- Edificio
     {nombre}" en la línea de cada reserva (para que el profesional no
     confunda a qué edificio corresponde cada unidad).
   - Con un solo edificio en el mensaje: la línea de arriba aparece una
     vez, pero se OMITE la aclaración en la línea de cada reserva — ya
     quedó dicho sin ambigüedad posible, repetirlo sería redundante.
   - El parámetro `incluir_edificio` (default `True`) sigue funcionando
     como apagado total si se pasa en `False` explícitamente (ningún
     llamador real lo hace hoy).
   - La línea de depósito/reintegro de llave NO sigue esta regla nueva
     — sigue con la "regla del edificio" general de siempre
     (`_incluir_edificio_efectivo`), porque el pedido de la clienta fue
     puntual sobre "el texto de la reserva" y esa línea puede aparecer
     sin ninguna reserva en el mensaje.

   Tests en `tests/test_mensajes.py` (reemplazan a los que probaban la
   vieja regla general para este mensaje puntual):
   `test_detalle_aislada_un_solo_edificio_en_el_mensaje_no_repite_la_
   mencion`, `test_detalle_aislada_un_edificio_en_el_mensaje_aunque_el_
   sistema_tenga_mas`, `test_detalle_aislada_sin_llaves_con_un_edificio_
   en_el_mensaje_lo_menciona`, `test_detalle_aislada_con_mas_de_un_
   edificio_en_el_mensaje_los_menciona_arriba_y_en_cada_linea`,
   `test_detalle_aislada_incluir_edificio_false_suprime_todo`,
   `test_detalle_aislada_un_edificio_en_dos_meses_distintos_no_repite_
   la_mencion` (este último reproduce el ejemplo exacto que dio la
   clienta: una reserva de noviembre y otra de diciembre, mismo único
   edificio, sin repetir la mención).

La clienta abrió el hilo mencionando también "archivos PDF varios, como
liquidaciones, disponibilidad y oferta" — no llegó a pedir nada concreto
sobre eso en este hilo.

