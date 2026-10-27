# Historial archivado — Sistema: Configuración general, Panel de control, Seguridad, Usuarios y permisos, Backup, Reinicio de prueba, Pantalla de carga

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

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

## Menú lateral: "Sistema DF" como nombre de espacio default (en vez de "Espacio Ramos Consultorios")

Pedido explícito de la clienta: una base recién instalada, antes de
cargar "Nombre del espacio" en Configuración general, mostraba
"ESPACIO RAMOS CONSULTORIOS" como categoría del menú lateral (el
fallback de `Configuracion.NombreEspacio` vacío) — un nombre de negocio
de EJEMPLO que no tiene por qué ser el de quien instala el sistema.
Pasa a "Sistema DF" (el nombre del PROGRAMA, sin relación con ningún
negocio en particular — mismo criterio ya usado para `app.version.
NOMBRE_PROGRAMA`, aunque acá es un literal propio, con espacio, "Sistema
DF", en vez de reusar esa constante, que es "SistemaDF" sin espacio y
está pensada para branding del programa en sí — título de ventana, CLI,
nombre del ejecutable — no para esto).

Las dos ramas de `gui_main.construir_secciones` (con `conn`, cuando
`NombreEspacio` está vacío/NULL, y sin `conn`, los tests de pantallas
sueltas) cambian su literal de "Espacio Ramos Consultorios" a "Sistema
DF" — apenas se carga un nombre real en "Nombre del espacio", la
categoría pasa a mostrar ESE nombre en mayúsculas, como siempre.

Puntual de este fallback nomás: el resto de los fallbacks de
`NombreEspacio` del sistema (PDFs de Propuesta/Disponibilidad/Oferta/
Placas, `oferta_busqueda_texto`, etc., que siguen cayendo a "Espacio
Ramos Consultorios"/"Espacio Ramos" según el caso, documentado en la
sección de Panel de control más arriba) no se tocaron — son textos de
documentos reales del negocio, un caso distinto del nombre de categoría
de un menú de navegación.

Tests actualizados en `tests/test_gui_main.py`: los tres que
comparaban contra "ESPACIO RAMOS CONSULTORIOS" pasan a "SISTEMA DF".

## Reinicio de prueba: ajuste manual de saldos anteriores + depuración de historial

Pedido explícito de la clienta: quiere probar el sistema a fondo durante
un mes (octubre) antes de arrancar a usarlo de verdad en noviembre —
"con la base de datos cargada lo pruebo y reviento por todos lados sin
importar los saldos y cargos que voy generando". Al avanzar a
noviembre, `avance_mes.avanzar_mes` (`_traspasar_saldos`) ya pasa
`SaldoCuentaActual` a `SaldoCuentaAnterior` y resetea el actual a 0 —
pero el anterior queda con todo lo que se generó probando, no con el
valor real de arranque. Pidió, textualmente: poder "ajustar manualmente
los SALDOS ANTERIORES de los profesionales, no los actuales" uno por
uno, y de paso "borre los historiales... de movimientos varios del mes
anterior" — sin tocar los archivos subidos ni la base ya cargada
(estructura física, profesionales, reservas regulares — estas últimas
las revisa ella a mano, "controlar que todas las reservas estén
correctas", no un borrado automático).

Antes de tocar código se consultaron dos decisiones (`AskUserQuestion`,
sobre una propuesta de diseño propia — pantalla nueva en "Parámetros
del sistema", distinta de "Base de datos del espacio" porque esa es
pura estructura física sin relación con dinero):

- **Alcance de "historiales de movimientos varios" a depurar**: elegido
  "Pagos y liquidaciones" + "Reservas aisladas y extraordinarias" +
  "Snapshots y estado de mensajería" — descartado explícitamente
  "Movimientos de llaves y placas" (stock/asignaciones reales, riesgoso
  si durante el mes de prueba ya hubo movimientos de verdad que haya
  que conservar).
- **Seguridad de la depuración**: pide la contraseña maestra antes de
  ejecutar (mismo mecanismo ya usado para "Continuar sin sincronizar"
  en `DialogoBaseDesactualizada`) — es irreversible.

### Negocio (`app/negocio/reinicio_prueba.py`, nuevo)

`CATEGORIAS_CON_SALDO = ("R", "A")` — las dos únicas categorías con
saldo de cuenta propio (B/E/X/C no facturan directo; E consolida en su
cabeza de equipo R). `profesionales_con_saldo`/`ajustar_saldo_anterior`
(esta última pisa `SaldoCuentaAnterior` directo, SIN pasar por `pagos.
registrar_pago` — acá el valor nuevo ES el punto de partida, no un
movimiento más a sumar encima de lo que quedó de la prueba).

"Período de corte": cualquier fila con período (imputado o, a falta de
eso, el mes de su `Fecha`) MENOR O IGUAL al elegido se borra —
`contar_registros_a_depurar` (cuenta sin borrar, mismo criterio que
`aumentos.cantidad_liquidaciones_a_regenerar`: el número real antes de
confirmar, no una advertencia genérica) y `depurar_historial_hasta_
periodo` (ejecuta, una sola transacción con rollback si algo revienta)
tocan: `HistorialPagos`/`LiquidacionEmitida`/`CargoEspecial`/
`FeriadoTrabajado`/`PlanPago`+`CuotaPlan` (bucket "Pagos y
liquidaciones"), `ReservaAislada` (bucket "Reservas aisladas y
extraordinarias" — las dos conviven en la misma tabla, ver `app.
negocio.reservas`) y `SnapshotMensual`/`EstadoMensajeriaPeriodo`
(bucket "Snapshots y estado de mensajería"). Deliberadamente AFUERA:
`LlaveMovimiento`/`Placa` (descartados en la consulta) y `AumentoAplicado`/
`EsquemaDescuentos` (no son "historial de movimientos", son
configuración de valores vigentes).

Dos referencias que apuntan HACIA estas tablas (con `PRAGMA
foreign_keys = ON`, borrar sin tocarlas primero revienta con
`IntegrityError`) se limpian a NULL antes de borrar, sin tocar la fila
que las tiene: `Ausencia.IdReservaAislada` (el vínculo "esta ausencia
surgió de esta reubicación") y `PlanPago.IdPlanAnterior` (la cadena de
refinanciaciones, en cualquier plan que sobreviva y apunte a uno que se
va a borrar).

### GUI (`app/gui/pantallas/reinicio_prueba.py`, nuevo — `PantallaReinicioPrueba`)

Nueva `Seccion` en "Parámetros del sistema" (`gui_main.py`, después de
"Usuarios y permisos"), sumada al mismo guardarraíl de nivel alto que
esa pantalla y "Configuración general" (`nombres_nivel_alto`,
`asegurar_permisos_pantalla`) — nace directo en Administrador, mismo
criterio: ajusta saldos y borra historial financiero, no menos sensible
que esas dos.

Dos solapas, mismo patrón `panelSolapa`/`showEvent`→`reiniciar()` que
el resto del sistema:

- **"Saldos iniciales"**: tabla Profesional/Categoría/Saldo actual
  (solo lectura, referencia)/Saldo anterior (editable), ordenada por
  `clave_orden_profesional` — "Ajustar saldo anterior" (edición por
  selección + diálogo, `botonPrimario`, deshabilitado sin selección) y
  "Poner todos en $0" (`botonSecundario`, con confirmación) para el
  caso común de arrancar de cero.
- **"Depurar historial de prueba"**: `SelectorPeriodo` (arranca en el
  MES ANTERIOR al actual — el que recién se cerró de prueba, distinto
  del default de ese widget, que es el mes en curso), una tabla que
  muestra en vivo cuánto hay para borrar de cada concepto (`contar_
  registros_a_depurar`, recalculada al cambiar el período) y "Depurar
  historial de prueba" (`botonPrimario`, deshabilitado sin nada para
  borrar) — al confirmar, pide la contraseña maestra (`QInputDialog.
  getText` + `verificar_contrasena_maestra`, mismo patrón que
  `DialogoBaseDesactualizada._elegir_sin_sincronizar`); sin ninguna
  contraseña maestra configurada todavía, avisa que hay que configurar
  una primero en vez de dejar pasar la acción sin ninguna verificación.

Tests nuevos: `tests/test_reinicio_prueba.py` (negocio — filtrado por
categoría, no toca el saldo actual, cada bucket se cuenta y se borra
por su período correspondiente incluyendo el fallback a `Fecha` cuando
no hay período imputado, las dos referencias que apuntan hacia las
tablas borradas no rompen por FK, no toca Llaves/Placas/Reservas
regulares, `contar_registros_a_depurar` coincide exacto con lo que se
termina borrando); `tests/test_gui_reinicio_prueba.py` (orden natural
de la tabla de saldos, ajustar/poner todos en $0, botón deshabilitado
sin selección, el selector de período arranca en el mes anterior,
botón de depurar habilitado/deshabilitado según haya algo para borrar,
sin contraseña maestra configurada avisa y no borra, contraseña
incorrecta no borra, correcta borra y refresca, cancelar el pedido de
contraseña o el cartel de confirmación no borra nada, las dos tablas
quedan excluidas del tab-chain).

## Pantalla de carga al iniciar sesión

Pedido de la clienta: "Cuando esté cargando la base de datos luego de
poner el usuario y contraseña que se ponga una pantalla con el ícono
que me asignaste como miniatura del programa grande en el centro de la
pantalla o algo parecido, y abajo la leyenda 'SistemaDF {versión}'".

Investigado antes de implementar: el proyecto nunca tuvo, en ningún
lado, ningún ícono asignado — ni `QApplication.setWindowIcon`, ni
ningún `.ico`/`.png` referenciado desde `sistemadf.spec` ni desde
ningún módulo de la GUI (confirmado con una búsqueda completa del
repositorio). La frase de la clienta asumía que ya había uno; como no
lo había, se le consultó (`AskUserQuestion`) si prefería pasar un
archivo propio o que se generara uno simple ahora — eligió la opción
recomendada: generar uno.

### Ícono nuevo (`app/gui/recursos/`)

`icono.png` (512×512, con transparencia) e `icono.ico` (multi-
resolución, 16 a 256px, para el `.exe` empaquetado en Windows): un
cuadrado redondeado con degradé entre `COLOR_NIVEL_1`/`COLOR_NIVEL_1_
OSCURO` (el azul de marca que ya usa el resto del sistema, sin inventar
un color nuevo) y el monograma "DF" en blanco — generado una sola vez
con Pillow (ya dependencia del proyecto) y commiteado como archivo
estático, no código que se ejecute en cada arranque. `app/gui/recursos/
__init__.py` expone `RUTA_ICONO`/`RUTA_ICONO_ICO` como único punto de
referencia — reemplazar esos dos archivos (mismo nombre, mismo lugar)
alcanza para cambiar el ícono en los tres puntos donde se usa sin tocar
ningún código.

Se usa en tres lugares:
- `gui_main.main()`: `QApplication.setWindowIcon(QIcon(...))`, apenas
  se crea la `QApplication` — cualquier ventana/diálogo del sistema que
  no pise el suyo propio lo hereda (mismo criterio que ya se usaba para
  `app.setFont(...)` en su momento, antes de revertirse esa parte).
- La pantalla de carga nueva (ver abajo).
- `sistemadf.spec`: `icon=` del `EXE(...)` (`icono.ico`, Windows/macOS
  necesitan `.ico`/`.icns`, no `.png` — en Linux PyInstaller lo ignora
  con un warning, esperado, confirmado en la verificación de abajo) +
  los dos archivos sumados a `datas` (mismo mecanismo que ya usaba
  `schema.sql`) para que la versión empaquetada los encuentre en
  runtime por la misma ruta relativa (`Path(__file__).parent`) que usa
  el código fuente — confirmado corriendo el build completo
  (`pyinstaller sistemadf.spec`) y encontrando los dos archivos bajo
  `dist/SistemaDF/_internal/app/gui/recursos/`.

### Pantalla de carga (`app/gui/widgets/pantalla_carga.py`)

`crear_pantalla_carga() -> QSplashScreen`: arma un `QPixmap` de 420×340
a mano (no un archivo estático, porque la leyenda tiene que mostrar la
versión ACTUAL, que cambia con cada release) — fondo blanco, el ícono
escalado a 200px centrado arriba, y debajo "SistemaDF {versión}"
(`app.version.NOMBRE_Y_VERSION`, la misma fuente única que ya usa el
título de ventana y el login — nunca un string propio hardcodeado) en
negrita, `COLOR_NIVEL_1_OSCURO`. Se envuelve en un `QSplashScreen`
estándar de Qt en vez de un diálogo propio — no hace falta ningún
mecanismo de cierre manual, `QSplashScreen.finish(ventana)` ya lo
resuelve solo.

**Dónde se engancha, y por qué ahí**: investigado antes de tocar nada
—`VentanaPrincipal.__init__` arma las ~18 pantallas del sistema TODAS
DE UNA, dentro del loop que recorre `secciones` (`seccion.fabrica(conn)`
corre para cada una en la construcción, no al hacer clic — el docstring
de `Seccion`/`VentanaPrincipal` dice "una sola vez", que significa
"una vez en la vida de la sesión", no "perezoso"). Ese armado es lo que
puede tardar un momento perceptible — no la apertura de la conexión
SQLite en sí, que ya está resuelta mucho antes, en el login. Por eso
`gui_main.main()` muestra la pantalla de carga JUSTO DESPUÉS de un
login exitoso (`dialogo_login.exec() == Accepted`) y la cierra recién
cuando `VentanaPrincipal` ya está armada y maximizada — cubre
exactamente el tramo que puede demorar, ni antes (el login no tiene
ninguna carga pesada propia) ni después.

`app.processEvents()` justo después de `pantalla_carga.show()` es
necesario: sin eventos procesados, la pantalla de carga quedaría en
cola sin pintarse hasta que arrancara `app.exec()` — mucho más tarde,
con la ventana principal ya completamente armada encima, dejando la
pantalla de carga sin ningún efecto visible.

### Verificación

`tests/test_gui_pantalla_carga.py`: `crear_pantalla_carga()` devuelve
un `QSplashScreen` del tamaño esperado, con contenido real pintado
tanto en la zona del ícono como en la zona de la leyenda (barrido de
píxeles no-blancos, sin asumir una fila exacta de texto — depende de
la métrica real de la fuente, mismo criterio de "no asumir sizeHint
exacto" ya documentado en varias pantallas de este archivo) y que la
leyenda se arma a partir de `NOMBRE_Y_VERSION` (inspección del código
fuente, no hay forma de leer texto de un `QPixmap` sin OCR). `gui_main.
main()` en sí no tiene test de punta a punta (mismo criterio que el
resto de ese punto de entrada, nunca probado así en este proyecto) —
se verificó a mano corriendo el `.spec` empaquetado completo bajo
`QT_QPA_PLATFORM=offscreen` contra una base nueva: arranca limpio hasta
quedar esperando el diálogo de login (el único punto donde puede
seguir sin interacción humana), sin ningún traceback.

## Panel de control, solapa "Avance de período, backup, y vista rápida": rediseño de la grilla de cuadritos

Nuevo hilo de trabajo (tercera prueba del flujo por temas separados):
sesión nueva, con `docs/historial/sistema.md` como contexto (donde vive
el resto del historial de esta pantalla). Pedido de varios puntos juntos
sobre la grilla de cuadritos:

- **Título de la solapa**: "Avance de período y backups" pasa a "Avance
  de período, backup, y vista rápida" — pedido explícito, sin ningún
  otro cambio de fondo asociado.
- **Fusión de cuadritos**: "Último backup" se funde DENTRO de "Período
  actual" (ahora "Período actual y último backup") — la info del
  primero queda arriba, la del segundo debajo, sin tocar ninguna de las
  dos (`_armar_tarjeta_periodo_y_backup`, antes dos funciones separadas).
  El cuadrito que libera pasa a ser "Estadísticas principales mes en
  curso" (`calcular_estadisticas_principales`, `app.negocio.
  panel_control`): monto por reservas regulares/aisladas (`monto_neto_
  regular_periodo`/`monto_neto_aislada_periodo`, mismo criterio "neto"
  que Estadísticas), total ingresos/gastos operativos/balance de negocio
  (reusa `app.negocio.balance.resultado_periodo` tal cual, sin alcance de
  ubicación), total liquidado y saldo pendiente de cobro (`LiquidacionEmitida.
  MontoGenerado` del período, ya existía adentro de `_saldo_pendiente_
  periodo` — se extrajo a `_total_liquidado_periodo` para no duplicar la
  consulta).
- **"Ocupación y horas mes en curso"** (antes "Ocupación y horas"):
  pierde el monto de aisladas y el saldo pendiente (ya están en el
  cuadrito nuevo, sin duplicarse) y suma, debajo de los tres conceptos
  generales (ocupación %, horas regulares semanales, horas aisladas
  mensuales), el mismo desglose repetido por cada Unidad del sistema
  (`calcular_estadisticas_ocupacion_por_unidad`, nueva) — reusa
  `calcular_ocupacion(conn, anio, mes).por_unidad` para el % (ya lo
  calculaba agregado) y repite `_horas_regulares_semanales_en_fecha`/
  `_horas_aisladas_periodo` (esta última sumó un parámetro opcional
  `ids_consultorio`, que antes no tenía) acotados a los consultorios de
  cada Unidad. Orden: Edificio alfabético y, dentro de cada uno, la
  Unidad con el mismo criterio PB/EP/piso ascendente que el resto del
  sistema (`app.pdf.estilos.clave_orden_unidad`, importado cruzado de
  capa — mismo patrón que ya usa `app.negocio.valores_operativos`).
- **"Profesionales"** suma cuatro conceptos, todos en `calcular_
  estadisticas_profesionales`: "con reservas aisladas activas" (confirmadas
  desde HOY en adelante, inclusive — no cuenta una ya pasada) y tres
  sobre cambios de `ReservaRegular` que todavía no entraron en vigencia:
  "horarios incorporados para el mes próximo" (suma de horas semanales
  de reservas cuya `VigenciaInicio` cae dentro del mes PRÓXIMO),
  "horarios liberados para el mes próximo" (mismo criterio sobre
  `VigenciaFin` cayendo dentro del mes EN CURSO — dejan de estar
  vigentes a partir del 1° del próximo) y "Diferencia" (incorporados
  menos liberados, puede ser negativa). Estos tres últimos son una
  interpretación propia de "cambios de horas regulares para el próximo
  período" sobre el modelo de vigencias ya existente — no hay, todavía,
  confirmación explícita de la clienta sobre si es exactamente lo que
  tenía en mente.
- **Fondo "cuadrito adentro del cuadrito"**: el `QScrollArea` de cada
  tarjeta (y su viewport interno, que Qt arma solo al llamar `setWidget`
  y no es accesible por objectName) pintaba con el color default de Qt
  en vez del `superficie` del resto del cuadrito — en modo claro porque
  `paleta()` no toca `Base`/`Window` ahí (vuelve temprano), en modo
  oscuro porque el `Base` que sí fija no es necesariamente el mismo tono
  que `panelSolapa`/`cuadritoInfo`. Se resuelve seteando `background:
  transparent` directo en la instancia del `scroll` y de `scroll.
  viewport()` (`_agregar_contenido_escrolable`, y a mano en `_armar_
  tarjeta_alertas`, que no pasa por esa función) — sin tocar `estilos.py`
  global, es local a este módulo igual que el resto del estilo de
  `_tarjeta`.
- **Alineación arriba**: con `setWidgetResizable(True)`, Qt estira el
  `QLabel` de contenido al alto completo del viewport, y la alineación
  vertical default de `QLabel` es centrada — un cuadrito con poco texto
  quedaba centrado en vez de arriba. Se corrige con `setAlignment(AlignLeft
  | AlignTop)` sobre ese `QLabel`, adentro de `_agregar_contenido_
  escrolable` (no aplica al cuadrito de período/backup, que es un
  `QWidget` con su propio `QVBoxLayout` + `addStretch()`, ya alineado
  arriba por su cuenta).
- **Alto de los cuadritos, 2/3 del anterior**: `_ALTO_MINIMO_TARJETA`
  baja de 140 a 93px (`round(140 * 2 / 3)`). El espacio que se libera lo
  absorbe Alertas SOLO — no hizo falta ningún cambio de layout aparte:
  Alertas ya tenía `stretch=1` en `layout_solapa` desde que se separó de
  la grilla (tercera vuelta de una ronda anterior), mientras que la
  grilla en sí se agrega sin stretch propio, así que cualquier espacio
  vertical sobrante en la solapa ya iba entero a Alertas por cómo reparte
  `QVBoxLayout` el espacio entre sus hijos.

### Segunda vuelta: dos cosas que no andaban como se esperaba al probar en la pantalla real

La clienta probó esta primera versión y encontró dos problemas reales
(no de gusto, de comportamiento):

- **Los seis cuadritos no se veían más chicos** ("los veo igual o más
  grandes"). Hipótesis en el momento: `setMinimumHeight` es un PISO, no
  un TECHO — con `QSizePolicy.Expanding` en los dos ejes, los cuadritos
  podrían seguir creciendo hasta ocupar el espacio disponible sin
  importar el mínimo. Se probó un arreglo (`_tarjeta(..., alto_fijo=
  ...)`, `setFixedHeight` en vez de `setMinimumHeight`, con el piso de
  Alertas subido a mano con el excedente real) — ver tercera vuelta más
  abajo para el desenlace real de este punto.
- **El cambio de fondo le pisó el color a los títulos de las alertas**
  ("antes eran de fondo naranja y letras blancas... dejá como antes esa
  parte"). Causa: el arreglo de la primera vuelta usaba `setStyleSheet
  ("background: transparent;")` en el `QScrollArea`/viewport de cada
  cuadrito — para los seis cuadritos simples (un solo `QLabel` sin hijos
  con estilo propio) no se notaba, pero el de Alertas tiene adentro
  `QFrame#tarjetaAlerta` → `QLabel#encabezadoAlerta` (fondo naranja,
  letra blanca, con su PROPIO selector por objectName en `estilos.py`)
  — un stylesheet puesto en un ancestro le cambia el motor de pintado a
  TODOS los descendientes, y terminaba pisándole el color a esos
  `QLabel`, aunque tengan su propio selector. Arreglo: `setAutoFillBackground
  (False)` en el viewport en vez de cualquier `setStyleSheet` — no pasa
  por el motor de stylesheets, así que no puede competir con ningún
  selector de ningún descendiente. Se cambió en los SIETE lugares (los
  seis cuadritos, vía `_agregar_contenido_escrolable`, y Alertas,
  aparte, que no pasa por esa función). Confirmado por la clienta en la
  tercera vuelta: este arreglo queda tal cual, sin tocar.

### Tercera vuelta: la clienta avisó que había probado una versión sin comitear — el alto vuelve al mínimo simple

Después de ver una captura nueva (con `alto_fijo`/`setFixedHeight`), la
clienta aclaró que se había confundido probando algo sin comitear, y
adjuntó la captura que sí le había gustado: el alto de los seis
cuadritos con el mecanismo ORIGINAL (`setMinimumHeight(_ALTO_MINIMO_
TARJETA)`, sin `setFixedHeight` ni ningún piso calculado a mano para
Alertas) ya daba el resultado que pedía desde el principio. Se revirtió
esa parte completa — `_tarjeta` vuelve a tener un solo parámetro
(`titulo`), los seis `_armar_tarjeta_*` vuelven a llamarla sin
`alto_fijo`, `_armar_tarjeta_alertas` vuelve a no recibir ningún
parámetro de alto, y `_ALTO_MINIMO_TARJETA_ANTERIOR`/el cálculo de
`excedente_liberado` en `_armar_ui` se sacaron por completo — mientras
que el arreglo de color de la segunda vuelta (`setAutoFillBackground`
en vez de `setStyleSheet`) se mantiene intacto, confirmado explícitamente
por la clienta como la parte que sí había que aplicar y dejar.

### Cuarta vuelta: las tres franjas (fila 1, fila 2, Alertas) reparten el alto por igual

La clienta volvió a marcar que Alertas se veía "bajo" (corto) — pero
reformuló el pedido en términos más precisos, sin ambigüedad: todo el
alto que queda DEBAJO del botón "Avanzar de mes" tiene que repartirse en
TRES franjas iguales (la primera fila de tres cuadritos, la segunda fila
de tres, y Alertas), las tres del mismo tamaño visual — no que Alertas
absorba "lo que sobra" después de que la grilla tome lo que necesita (el
criterio con el que se había armado hasta acá, desde la primera
versión). Antes de tocar código se armó un script con la pantalla real
(no se adivinó a partir de leer el layout) para confirmar la causa: las
dos filas de cuadritos vivían en un único `QGridLayout`, agregado a
`layout_solapa` SIN ningún `stretch` propio (0 implícito), mientras
Alertas se agregaba con `stretch=1` — en un `QBoxLayout`, un ítem sin
stretch explícito NO crece más allá de lo que pide su contenido (aunque
sus hijos tengan política `Expanding`), así que la grilla quedaba
achicada a su tamaño "natural" (determinado en la práctica por el
tamaño por default de cada `QScrollArea`, ~192px, no por el piso de
`_ALTO_MINIMO_TARJETA`) y Alertas se llevaba TODO el resto — midiendo en
una ventana real de 950px de alto, la grilla terminaba en 138px por fila
y Alertas en 412px: ni iguales, ni en la proporción 2:1 que hubiera
tenido sentido para "dos filas + una franja".

Arreglo: las dos filas de tres cuadritos dejan de vivir en un único
`QGridLayout` — pasan a ser dos `QHBoxLayout` independientes
(`fila_tarjetas_1`/`fila_tarjetas_2`, cada cuadrito agregado con
`stretch=1` para mantener el mismo ancho parejo que ya daba
`setColumnStretch`), y las tres franjas (`fila_tarjetas_1`,
`fila_tarjetas_2`, la tarjeta de Alertas) se agregan a `layout_solapa`
como HERMANAS, con el mismo `stretch=1` cada una. Con el mismo stretch Y
el mismo piso (`_ALTO_MINIMO_TARJETA` en las tres, Alertas incluida, vía
`_tarjeta()`), `QBoxLayout` reparte cualquier espacio de sobra en partes
iguales entre las tres — confirmado armando la pantalla real y midiendo
alto en píxeles en dos tamaños de ventana distintos (950px y 800px de
alto): las tres franjas quedaron exactas o a 1px de diferencia en los
dos casos, no una aproximación. Ya no existe ningún `QGridLayout` en
esta solapa — `_COLUMNAS_GRILLA` se mantiene (ahora corta la lista de
seis tarjetas en dos mitades de tres para repartir entre las dos filas).

De paso, formato de fecha del cuadrito "Feriados y fechas especiales
próximas": pasa de mostrar `FechasEspeciales.Fecha` tal cual (AAAA-MM-DD)
a "ddd dd-mm-aaaa" (día de la semana abreviado, mismo criterio que el
resto del sistema) — `_texto_fecha`, nueva, mismo patrón que `_texto_
fecha_hora` pero sin la hora (acá el dato es una fecha sola). Puntual de
este cuadrito — la lista de alertas "Fechas especiales en los próximos
15 días" (`_ETIQUETA_FILA["fechas_especiales_proximas"]`, otro lugar
que también arma texto con `f['Fecha']`) no se tocó, no fue parte de
este pedido.

Pregunta aparte, sin cambio de código: cómo cargar "Día del psicólogo"
el 13 de octubre de cada año — se carga desde el catálogo "Profesiones y
tratamientos", campo "Día de profesión" (formato MM-DD, sin año, se
repite todos los años), en la fila de "Psicología"; el texto "Día del
Psicólogo" sale del campo "Nombre masculino" de esa misma fila. Ya
alimenta el cuadrito "Cumpleaños y días de profesión" sin tocar nada
más (`cumpleanos_y_dias_profesion_proximos`, sin cambios).

Segunda pregunta aparte, también sin cambio de código: qué es
`Configuracion.RangosEstadisticasOcupacion` ("Configuración general" →
solapa "Grilla y ocupación" → "Rangos de estadísticas de ocupación
(JSON)") — confirmado que sí, es exactamente eso: un JSON por día de la
semana (`{"Lunes": [9, 21], ...}`, default L-V 9-21hs / Sáb 9-15hs /
domingo no cuenta — `app.negocio.estadisticas.RANGO_DEFAULT`) que define
el rango horario "hábil" que se tiene en cuenta al calcular los % de
ocupación (general y desglosado por edificio/unidad/consultorio) —
`rango_horas_por_dia`/`calcular_ocupacion` en `app/negocio/estadisticas.py`
lo usan tal cual. Puntual: NO es lo mismo que "Hora inicio/fin de
grilla" (otro campo de esa misma solapa) — ese es el rango que se
MUESTRA en la grilla semanal visual, un concepto distinto que puede no
coincidir con el rango que efectivamente cuenta para las estadísticas.

Tests nuevos/reescritos: `tests/test_panel_control.py` (`calcular_
estadisticas_profesionales` con los tres casos de aisladas activas/
incorporados/liberados; `calcular_estadisticas_principales` contra
`resultado_periodo` directo, para no duplicar la fórmula en el test;
`calcular_estadisticas_ocupacion_por_unidad` con dos Unidades, cada una
con su propia reserva, más el orden PB antes que piso numérico; los
viejos `monto_aisladas_mes`/`saldo_pendiente_mes` de `EstadisticasOcupacion`
se sacaron, ya no existen ahí). `tests/test_gui_panel_control.py` (título
de solapa nuevo; título del cuadrito fusionado; los tres conceptos
generales de ocupación sin el monto/saldo viejo, más el desglose por
Unidad; los siete conceptos del cuadrito nuevo; los cuatro conceptos
nuevos de Profesionales; fondo transparente (`autoFillBackground`, no
`styleSheet`) del scroll en los seis cuadritos y en Alertas; alineación
`AlignTop` del contenido; `_ALTO_MINIMO_TARJETA` en el valor nuevo
(2/3 del anterior, con `setMinimumHeight` nomás — el intento de
`setFixedHeight`/piso calculado a mano para Alertas se probó y se
revirtió, ver tercera vuelta; los tests de esa variante se sacaron con
el revert); que ningún `QScrollArea`/viewport de Alertas tenga un
`styleSheet` propio, y que el título de cada alerta
(`QLabel#encabezadoAlerta`) no tenga ningún estilo local que pueda
competir con `estilos.py` — regresión del bug real que encontró la
clienta). Cuarta vuelta: los tres tests que usaban `pantalla.
findChild(QGridLayout)` (ya no existe ningún `QGridLayout` en esta
solapa) se reescriben ubicando cada cuadrito por su `QLabel` de
contenido (`_tarjeta_de`, ya usado en otros tests del archivo) en vez de
por posición dentro de la grilla vieja; nuevo `test_fila1_fila2_y_
alertas_quedan_del_mismo_alto` (reemplaza al que afirmaba que Alertas
quedaba "mucho más alto" — ya no es cierto, ahora es igual a propósito)
y el test de fecha de "Feriados y fechas especiales próximas" pasa a
verificar "ddd dd-mm-yyyy" en vez del AAAA-MM-DD crudo de antes.

## Avance de mes: período operativo real, independiente del modo QA

Bug reportado por la clienta probando el sistema EN SERIO (sin el modo
"fecha ficticia" de QA): parada en 10/2026, "Avanzar de mes" mostraba las
dos alertas de siempre (evaluar aumento, confirmar el pase) pero después
de confirmarlas no pasaba nada — seguía viendo 10/2026 en todos lados.

Investigado antes de tocar código (pedido explícito): `periodo_actual()`/
`fecha_actual()` (`app/negocio/dias.py`) devolvían siempre `date.today()`
tal cual (salvo con el modo ficticia activo) — no había NINGÚN campo que
"Avanzar de mes" (`app.negocio.avance_mes.avanzar_mes`) tocara para mover
ese "hoy" hacia adelante. El texto explicativo del botón ("Este proceso
ubica virtualmente al operador en el nuevo período cualquiera sea la
fecha real del día", redactado por la clienta en una ronda anterior)
describía un comportamiento que nunca se llegó a programar — ningún test
de `avance_mes.py` verificaba que `periodo_actual()` cambiara como efecto
de la función, todos fijaban el período a mano antes de probar.

Regla final, aclarada por la clienta tras una primera propuesta mía que
reusaba el campo de QA (descartada: mezclaba un concepto de testing con
uno de producción real, y hubiese dejado la franja naranja "MODO FECHA
FICTICIA (QA)" prendida todo el tiempo en uso normal):

- "Avanzar de mes" tiene que pasar sí o sí al período siguiente,
  ubicando al operador en el DÍA 1 de ese mes.
- Mientras la fecha real no llega a ese mes, el sistema se mantiene fijo
  en ese día 1 ("virtual"). Cuando la realidad lo alcanza, se rompe lo
  virtual y se sigue con la fecha real tal cual.
- Caso simétrico: si la fecha real ya cruzó a un mes nuevo pero no se
  apretó "Avanzar de mes", el sistema se queda en el ÚLTIMO día del mes
  que todavía no se cerró, no salta solo con el calendario.
- Tope de un período de anticipo: si ya se avanzó un mes por delante de
  la fecha real, no se puede volver a avanzar hasta que la realidad
  alcance ese período — confirmado explícitamente ("si estoy realmente
  en octubre, que me permita avanzar a noviembre y no más de eso").
- Aplica a TODO el sistema (cumpleaños próximos, fechas especiales,
  vencimientos, etc. — todo lo que usa `fecha_actual`), no solo al
  período de liquidaciones/cuotas.

Implementación: columna nueva `Configuracion.PeriodoOperativoActual`
('AAAA-MM', independiente de `ModoFechaFicticia`/`FechaFicticia` — ese
sigue siendo un override puro para QA, sin relación con esto). Nueva
`dias.periodo_operativo_actual()` la lee (con fallback al período real
si viene NULL). `dias.fecha_actual()`, fuera del modo QA, devuelve
`date.today()` recortada (clamp) para que nunca caiga afuera del mes de
`periodo_operativo_actual`: por abajo al día 1 (fecha real todavía no
llegó), por arriba al último día (fecha real ya pasó de mes sin avance)
— la fórmula de recorte da gratis los dos casos (el "virtual adelantado"
y el simétrico) sin lógica aparte. `periodo_actual()` no se tocó, hereda
el comportamiento nuevo por ser "año-mes de `fecha_actual()`".

`avance_mes.puede_avanzarse_mes(conn)` (mismo criterio que
`pedidos_activos_vencidos`: expuesta aparte para que la pantalla avise
ANTES de ofrecer el resto de los pasos) compara el primer día de
`periodo_operativo_actual` contra la fecha real — si ya quedó por
delante, devuelve False. `panel_control._avanzar_mes()` la chequea de
primero, antes de la pregunta de aumentos: si está bloqueado, un solo
`QMessageBox.information` explicando por qué y corta, sin tocar nada.
`avanzar_mes()` en sí no valida este tope (igual que no valida
`eliminar_activos_vencidos_lista_espera`, confía en que lo decidió la
pantalla) — como último paso, DESPUÉS de todo lo que todavía lee
`fecha_actual` dentro de la misma función (retención de liquidaciones,
snapshots de operación importante), mueve el ancla a
`sumar_meses(periodo_cerrado, 1)` — importa el orden: si se moviera
antes, esos pasos intermedios verían un "hoy" ya adelantado a mitad de
la propia operación de cierre.

Migración (`_inicializar_periodo_operativo_actual`, mismo patrón que
`_inicializar_ultimo_backup_propio`): una base ya en uso recibe la
columna en NULL y se backfillea al período real de hoy — "sin avance
pendiente", el mismo estado en que ya venía funcionando de hecho (sin
este campo, el sistema siempre mostraba el período real). Para una base
NUEVA, `sembrar_configuracion` ya la inicializa explícita en el INSERT
(no alcanza con la migración sola: corre ANTES de que `sembrar_*` cree la
fila, así que en una base recién creada el backfill no tendría ninguna
fila todavía sobre la que escribir).

Indicador visual (pedido de la clienta, "no lo necesitaría, pero tampoco
me molesta, agregalo por si acaso"): se reusa la misma barra naranja de
`_barra_fecha_ficticia` (mutuamente excluyente con el modo QA — mientras
ese modo está activo, el recorte ni corre) con un texto distinto
("AVANCE DE MES ADELANTADO", sin la palabra "QA") cuando
`puede_avanzarse_mes` es False.

Tests nuevos: `tests/test_dias.py` (clamp de `fecha_actual` en sus
distintos casos, prioridad del modo ficticia), `tests/test_avance_mes.py`
(`puede_avanzarse_mes`, tope de un período, `PeriodoOperativoActual` se
actualiza al avanzar), `tests/test_gui_panel_control.py` (bloqueo con
aviso y sin ejecutar nada en el intento de un segundo avance),
`tests/test_main_window.py` (franja nueva sin modo QA). Todos usan
`monkeypatch` sobre `date` en `app.negocio.dias`/`app.negocio.avance_mes`
para simular la fecha REAL del sistema operativo — distinto de
`ModoFechaFicticia`, que esta regla ignora a propósito.

## Reinicio de prueba: búsqueda de profesional, categoría X en saldos iniciales

Pedido de la clienta, hilo separado del de Avance de mes:

- **"Buscar profesional"** arriba de "Ajustar saldo anterior"
  (`_PanelSaldosIniciales`): filtro de texto libre, mismo criterio que
  "Filtros que solo afectan la visualización" (sustring por cualquier
  columna visible, sin distinguir mayúsculas ni acentos, reusa
  `_normalizar_busqueda` de `crud_generico.py` — mismo patrón ya usado
  en `bloques_rigidos.py`). Se limpia y recupera el foco en
  `reiniciar()`, como cualquier "Buscar" del sistema.
- **Categoría X sumada a la tabla de saldos** (`app.negocio.
  reinicio_prueba.CATEGORIAS_CON_SALDO`, ahora `("R", "A", "X")`):
  confirmado por la clienta — un X puede venir de haber sido R/A antes
  de liberar sus horarios, y conservar un saldo arrastrado de esa
  época. El orden ya salía solo correcto (R, luego A, luego X, cada uno
  por código) con el `clave_orden_profesional` que la tabla ya usaba —
  no hizo falta tocar la lógica de orden, solo sumar la categoría al
  filtro de la consulta.

Consulta aislada de la clienta sobre una validación más amplia (B/E/C
nunca deberían poder recibir cargos/pagos/depósitos de llave, E se
redirige al cabeza de equipo): investigado contra el código real,
confirmado un hueco real en Cargos especiales/Pagos/Llaves (hoy
excluyen C de esos combos, pero SÍ dejan crear un cargo/pago/depósito
contra un B o un E sin ningún aviso ni redirección) — queda **afuera**
de esta ronda, es tema de otro hilo (toca tres pantallas y sus negocios,
no tiene nada que ver con Reinicio de prueba).

Tests nuevos: `tests/test_gui_widget_foco.py` (`instalar_seleccionar_
todo_al_enfocar`, con `setFocus()` directo y con click), `tests/
test_reinicio_prueba.py` (`profesionales_con_saldo` trae R/A/X),
`tests/test_gui_reinicio_prueba.py` (orden R→A→X, el diálogo selecciona
el importe al abrir, el buscador filtra y se limpia en `reiniciar()`).

## Panel de control: fix de doble conteo, estado de backup, recordatorios por fecha real e indicador "Procesando..."

Tres pedidos puntuales de la clienta sobre la solapa "Avance de
período, backup, y vista rápida", más un mecanismo nuevo de alcance
general que surgió de paso en el mismo hilo.

### Total liquidado/saldo pendiente duplicaban reemisiones de prueba

Bug real reportado por la clienta: "estuve haciendo un par de pruebas
con las emisiones de liquidaciones y evidentemente va acumulando
valores". `_total_liquidado_periodo` (`app/negocio/panel_control.py`)
sumaba `MontoGenerado` de TODAS las filas de `LiquidacionEmitida` del
período — pero `emitir_liquidacion` crea una fila NUEVA en cada
reemisión, cada una con el monto TOTAL de esa emisión (no un delta: el
delta solo se usa para `SaldoCuentaActual`, ver su propio docstring),
así que sumar todas las filas cuenta de más cada reemisión de prueba
que haya hecho el operador para el mismo profesional/período.
Reproducido con un script: 3 emisiones de $100.000 para el mismo
profesional daban $300.000 en vez de $100.000.

Arreglado sumando solo la ÚLTIMA emisión de cada profesional
(subconsulta `MAX(IdLiquidacion) ... GROUP BY IdProfesional`). Afecta
tanto a "Total liquidado" como a "Saldo pendiente de cobro" (que se
calcula a partir de él). Test nuevo: `tests/test_panel_control.py`
(`test_estadisticas_principales_total_liquidado_no_duplica_
reemisiones`).

### Estado del backup "VENCIDO" en rojo, negrita y mayúscula

Pedido de la clienta, cuadrito "Período actual y último backup". Se
separó la línea "Estado: ..." de `etiqueta_backup` (que sigue
mostrando solo Último backup/Frecuencia, sin estilo especial) a una
etiqueta propia, `etiqueta_estado_backup`: si `backup_vencido()` es
`True`, el texto pasa a "ESTADO: VENCIDO" con `color: {COLOR_ROJO};
font-weight: bold;`; si está al día, "Estado: al día" sin estilo.
Tests nuevos en `tests/test_gui_panel_control.py`.

### Cuadros de Feriados/Cumpleaños basados en fecha real, no en la del período

Caso real de la clienta: hizo "Avanzar de mes" con todavía unos días
de octubre por delante (fecha real 27/10, parado virtualmente en
noviembre) y el cuadrito de cumpleaños dejó de mostrarle uno que caía
el 29/10. Causa: `fechas_especiales_proximas_dos_meses`/`cumpleanos_y_
dias_profesion_proximos` usaban `fecha_actual(conn)`, que recorta
`date.today()` al rango del período operativo — una vez avanzado el
mes, esa función ya devolvía el 01/11 (el primer día del período
nuevo), "perdiendo" todo lo que quedaba entre la fecha real y esa.

`fecha_real(conn)` (nueva, `app/negocio/dias.py`): igual que `fecha_
actual` pero SIN el recorte al período operativo — respeta el modo
fecha ficticia de QA (es la fecha "real" simulada mientras se prueba),
pero fuera de ese modo devuelve `date.today()` sin tocar. Los dos
cuadritos de recordatorios pasan a usarla; el resto de los usos de
`fecha_actual` en este módulo (ocupación, backup vencido, alertas,
cálculos atados al período) no se tocó — siguen necesitando el
recorte real para que el negocio calcule sobre el período correcto.
Tests nuevos en `tests/test_panel_control.py` reproduciendo el caso
exacto (fecha real 27/10, período operativo adelantado a noviembre,
el evento del 29/10 sigue apareciendo).

### Indicador "Procesando..." para operaciones largas (mecanismo nuevo, aplicado en Liquidaciones)

Pedido de la clienta, de paso ("para el comportamiento general del
sistema"): que un proceso largo (ejemplo que dio: emitir todas las
liquidaciones) muestre algo chico y centrado — relojito de arena +
"Procesando..." — para que no parezca que el sistema se colgó.

`Procesando` (`app/gui/widgets/procesando.py`, nuevo): se usa como
`with Procesando(self, "texto..."):` alrededor del loop largo, y el
propio loop llama a `procesando.tick()` en cada vuelta — Qt es de un
solo hilo, así que sin este empujón manual (`QApplication.
processEvents()` adentro de `tick()`) el cartel ni el resto de la
ventana se repintarían hasta que el loop termine. Se evaluó mover el
trabajo a otro hilo y se descartó: la conexión sqlite no está pensada
para compartirse entre hilos, mucho más riesgo que beneficio para este
caso (loops de unos pocos segundos, no minutos).

Aplicado en `_PanelEmisionArchivos._emitir` (`liquidacion.py`, el
`for profesional in seleccionados` que genera un PDF por cada uno) —
mecanismo compartido disponible para sumar a cualquier otro loop largo
del sistema caso por caso (ej. avance de mes, importación de Excel),
no un barrido completo de una sola vez. Tests nuevos en `tests/
test_gui_widget_procesando.py`.

