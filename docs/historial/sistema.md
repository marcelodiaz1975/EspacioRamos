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

## Saldo actual inflado por una reserva aislada a futuro; Panel de control: resaltado de hoy, combo de Profesión y formato de Día de la profesión

Pedido de la clienta en Reinicio de prueba: notó una profesional con
"saldo actual" muy superior al del mes, sospechando que una reserva
aislada agendada para un mes futuro (diciembre, estando parada en
noviembre) se lo estaba sumando encima.

**Confirmado y corregido.** Causa: `emitir_liquidacion`
(`app/negocio/liquidaciones.py`) acreditaba el delta de CUALQUIER
emisión a `Profesional.SaldoCuentaActual` sin importar el período —
incluida la emisión-preview de un período FUTURO que dispara sola
`regenerar_si_corresponde` al cargar/editar una reserva aislada con
"Período a imputar" posterior al operativo actual. `SaldoCuentaActual`
representa solo el período operativo actual (se resetea a 0 en cada
avance de mes, ver `avance_mes.py`), así que una preview a futuro no le
tiene que sumar nada todavía — ese crédito llega solo, más adelante,
cuando el avance de mes alcance ese período y alguien la reemita contra
un `SaldoCuentaActual` recién puesto en 0. Mismo patrón que el guard ya
existente para "no rechazar reemitir el período actual por haber una
preview posterior" (`periodo <= periodo_operativo_actual(conn)`), ahora
aplicado también al crédito de saldo. Test de regresión:
`test_emitir_liquidacion_de_un_periodo_futuro_sin_cerrar_no_infla_el_saldo_actual`
(`tests/test_liquidaciones.py`) — confirmado que SIN el fix falla con el
síntoma exacto reportado (saldo duplicando dos períodos).

**Importante para la clienta:** el fix evita que el bug vuelva a pasar
de acá en adelante, pero NO corrige retroactivamente el valor ya
inflado de la profesional que detectó — ese quedó escrito por el código
viejo. Se ajustó a mano una vez desde "Ajustar saldo" en Reinicio de
prueba (`_DialogoAjustarSaldo`).

De paso, en Panel de control: cumpleaños, días de profesión y feriados/
fechas especiales que caen justo HOY (`fecha_real`, no la fecha de
período) se resaltan en rojo y negrita en sus respectivos cuadritos
(`_resaltar_si_es_hoy`, `panel_control.py`) — mismo criterio que el
"VENCIDO" de Estado de backup. "Aniversarios" confirmado por la
clienta: es el sinónimo coloquial que usa para "día de profesión", no
hay ningún concepto separado que agregar.

**Combo "Profesión" de Nuevo/Editar profesional — investigado, no era
un bug de código.** La clienta reportó ver "Día del psicólogo" como
alternativa en el desplegable "Profesión" al dar de alta un
profesional. Revisado `_opciones_profesion` (`app/gui/pantallas/
profesionales.py`): solo lee `Profesion.Nombre` — probado en una base
limpia con `DiaProfesion` cargado y el combo sale sin ninguna entrada de
ese tipo, solo nombres de profesión reales. **Confirmado por la
clienta**: era una fila de verdad en el catálogo "Profesiones y
tratamientos" cuyo campo "Nombre" era literalmente "Día del
Psicólogo" — se había creado una profesión nueva con ese texto como
nombre en vez de cargar el campo "Día de la profesión" sobre la
profesión real "Psicología". Corregido a mano borrando la fila
fantasma y cargando el día en la fila real.

**Formato de "Día de la profesión": DD-MM en vez de MM-DD.** Pedido de
la clienta al cerrar el punto anterior: el campo quedaba "al revés" de
cómo se lee una fecha en el resto del sistema. Cambiado en los tres
lugares que conocían el orden viejo: `FORMATO_DIA_MES`/
`es_dia_mes_valido` (`app/negocio/validaciones.py`), el parseo en
`cumpleanos_y_dias_profesion_proximos` (`app/negocio/panel_control.py`)
y la etiqueta del Campo en `catalogos.py`, que pasa de "Día de la
profesión" a "Día de la profesión (dd-mm)" (antes el formato solo se
veía en el mensaje de error de `formato_esperado`, nunca de entrada).
`Configuracion.FormatoDiaProfesionInvertido` (columna nueva, default 1
en `schema.sql` para que una base NUEVA nazca "ya migrada") es el
marcador de una sola vez: en 0 dispara `_invertir_formato_dia_profesion_
a_dd_mm` (`app/db/migraciones.py`), que invierte las dos mitades de
cada `Profesion.DiaProfesion` cargado y sube el flag a 1 para no volver
a invertirlas en el próximo arranque.

## Reinicio de prueba: selección automática del resultado único al filtrar

Pedido de la clienta: *"Si empiezo a filtrar y queda un resultado solo
en la lista, que quede seleccionado en la tabla para ya empezar a
editarlo directamente sin tener que pinchar en el registro"*.

`_PanelSaldosIniciales._aplicar_filtro_busqueda`
(`app/gui/pantallas/reinicio_prueba.py`) ya ocultaba filas por
substring (mismo criterio que "Filtros que solo afectan la
visualización"); ahora, si queda exactamente una fila visible, la
selecciona sola (`self.tabla.selectRow(...)`) para poder ir directo a
"Ajustar saldo" sin pinchar la fila a mano. Solo dispara mientras hay
texto buscado ("si EMPIEZO a filtrar", pedido textual) — con el campo
vacío (todas las filas visibles) no selecciona nada, aunque por
coincidencia haya un solo profesional cargado en la base entera. La
otra solapa de esta pantalla (Depurar historial) usa `QTableWidget.
SelectionMode.NoSelection` en su tabla, así que el pedido no le
aplica. Tests nuevos: `test_buscar_con_un_solo_resultado_lo_selecciona_
solo`, `test_buscar_con_mas_de_un_resultado_no_selecciona_nada`
(`tests/test_gui_reinicio_prueba.py`).


## Panel de control: se saca la sección "Alertas", se agrega el cuadro "Control de pagos"

Pedido explícito de la clienta: eliminar por completo la sección
"Alertas" de Panel de control, y sumar tres cuadritos más a la grilla
(ahora 9, en 3 filas de 3, en vez de 6 + Alertas aparte). El cuadrito
inferior izquierdo pasa a llamarse "Control de pagos" y replica las
siete etiquetas de conteo de "Carga y control" (ver `docs/historial/
control_pagos.md` — mismo `resumen_conteo_vencimientos`, sin los
cuatro filtros que ahí sí se aplican, porque Panel de control muestra
el total real) — "Con vencimiento hoy"/"Con vencimiento mañana" se
resaltan en rojo y negrita cuando el conteo es mayor a cero, el resto
de las líneas queda siempre en texto plano. Los otros dos cuadritos
nuevos (inferior centro e inferior derecha) quedan sin asignar por
ahora — consultado explícitamente con la clienta vía pregunta directa,
eligió dejarlos vacíos (solo el título "(Sin asignar):") en vez de
definir su contenido en esta ronda.

Se eliminó de `app/negocio/panel_control.py` el dataclass `Alertas`,
`calcular_alertas` y sus helpers exclusivos (`_reserva_regular_activa`,
`_deuda_regulares_alerta`, `_planes_con_cuotas_vencidas`, `_fechas_
especiales_proximas`, `_categoria_x_con_llaves_pendientes`) —
confirmado por grep que ningún otro módulo los importa (otras pantallas
con nombres parecidos, ej. `mensajeria.py`/`placas.py`, tienen sus
propias funciones independientes). `_deuda_regulares`/`_deuda_aisladas`
se mantuvieron: los sigue usando `calcular_estadisticas_profesionales`
(el cuadrito "Profesionales", que no cambió). La grilla de tarjetas de
`PanelAvanceMes._armar_ui` pasa de una estructura hardcodeada (2 filas +
Alertas aparte) a un loop genérico sobre listas de 3 en 3, mismo
`stretch=1` por fila para que todas midan igual de alto.

Tests: eliminados 13 tests de alertas en `tests/test_panel_control.py`
y 7 en `tests/test_gui_panel_control.py` (3 de alertas puntuales + 2 de
ancho + 2 de scroll/estilo), renombrado/reescrito el test de "seis
tarjetas parejas" a `test_nueve_tarjetas_parejas_en_tres_filas`, y
sumados 4 tests nuevos: `test_tarjeta_control_pagos_muestra_los_siete_
conteos`, `test_tarjeta_control_pagos_resalta_vencimiento_hoy_y_mañana_
en_rojo_y_negrita`, `test_tarjeta_control_pagos_sin_vencimientos_
proximos_no_resalta`, `test_tarjetas_vacias_no_tienen_contenido_
asignado`. pyflakes limpio en los cuatro archivos tocados
(`app/gui/pantallas/panel_control.py`, `app/negocio/panel_control.py`,
`tests/test_panel_control.py`, `tests/test_gui_panel_control.py`);
suite completa de los dos archivos de test: 94 passed.

## Panel de control: reordenar "Estadísticas principales" + corregir Total liquidado/Saldo pendiente

Dos pedidos sobre el cuadrito "Estadísticas principales mes en curso"
(`PanelAvanceMes`, `app/gui/pantallas/panel_control.py`):

- Reorden pedido explícitamente: "Gastos operativos"/"Balance de
  negocio" pasan a estar inmediatamente después de "Total ingresos";
  "Total liquidado"/"Saldo pendiente de cobro (de lo liquidado)" quedan
  al final (antes estaban en el medio, antes de Gastos/Balance).
- Auditoría pedida de "Total liquidado"/"Saldo pendiente": "Total
  liquidado" (`_total_liquidado_periodo`, `app/negocio/panel_control.
  py`) YA estaba correcto de una ronda anterior (dedup a la última
  emisión por profesional vía `MAX(IdLiquidacion) GROUP BY
  IdProfesional`, sobre `MontoGenerado` — que ya incluye todos los
  conceptos: especiales, descuentos de feriados/vacaciones/licencias,
  horas agregadas, aisladas, cuotas de plan — todo lo que la clienta
  describió), no hizo falta tocarlo.

  **Bug real encontrado y arreglado en "Saldo pendiente de cobro"**
  (`_saldo_pendiente_periodo`): el ejemplo que dio la clienta — "total
  liquidado $10.000, un profesional tiene que abonar $500, abona $600 y
  deja $100 a favor del próximo mes, el saldo pendiente tiene que decir
  $9500, no $9400" — exponía que el cálculo restaba lo cobrado de TODOS
  los profesionales de una sola vez contra el total liquidado global
  (`total_liquidado - SUM(HistorialPagos.Monto)` sin agrupar), sin
  ningún tope por profesional: el sobrepago de uno terminaba reduciendo
  el saldo pendiente de los demás en vez de quedar como crédito propio
  a favor del mes próximo. Se reescribe para calcular profesional por
  profesional (liquidado de su última emisión del período vs. cobrado
  imputado a ese mismo período) y sumar los pendientes individuales,
  cada uno acotado a no bajar de $0 (`max(Liquidado - Pagado, 0)`) — el
  que pagó de más aporta $0, nunca un valor negativo que termine
  compensando la deuda de otro.

Tests: `tests/test_panel_control.py` (+1: escenario exacto del ejemplo
de la clienta, dos profesionales, uno sobrepaga y el otro no paga nada,
saldo pendiente = $9500 no $9400 — el test preexistente de saldo
pendiente de un solo profesional sigue pasando tal cual, el cálculo por
profesional coincide con el global cuando hay uno solo);
`tests/test_gui_panel_control.py` (+1: orden de las cinco etiquetas en
el texto de la tarjeta). Suite: 32 + 64 passed, más 281 passed en la
corrida conjunta con `test_control_pagos.py`/`test_migraciones.py`/
`test_gui_balance.py`/`test_gui_control_pagos.py`/`test_balance.py`/
`test_gastos_operativos.py` (confirma que ningún cambio de esta ronda
pisó a los anteriores). pyflakes limpio en `app/negocio/panel_control.
py`, `app/gui/pantallas/panel_control.py` y los dos archivos de test.

## Panel de control: segundo bug real en "Saldo pendiente de cobro" — el signo de `HistorialPagos.Monto`

La clienta mandó capturas Y la base de datos real del espacio,
preguntando directamente qué incluye cada concepto porque "no
encuentro relación" entre los números — el cuadrito real mostraba
Saldo pendiente $21.242.875, MÁS GRANDE que Total liquidado
$14.220.133, matemáticamente imposible con el cálculo de la ronda
anterior si el signo fuera el asumido (la suma de pendientes por
profesional, cada uno acotado a no superar su propio liquidado, nunca
puede superar la suma total liquidada).

**Causa real**: la ronda anterior (ver arriba) corrigió el "sin tope
por profesional" pero siguió asumiendo que `HistorialPagos.Monto` es
positivo para un pago real ("debía $500, pagó $600"). Es al revés:
`app.negocio.pagos.registrar_pago` (su propio docstring) guarda
`Monto` CON SIGNO — **negativo** para un pago recibido (resta de la
cuenta, reduce lo que debe) y **positivo** para un cargo/ajuste (suma,
aumenta lo que debe); confirmado también en la GUI de "Registrar
pagos" (`nuevo_saldo = saldo_total + monto`, un monto negativo hace
bajar el saldo). La fórmula de la ronda anterior RESTABA `Pagado` (la
suma de `Monto`) de `Liquidado`, así que un pago real (negativo) en vez
de reducir el pendiente lo AUMENTABA — exactamente lo que mostraba la
base real: cuanto más pagó un profesional, más alto salía su
"pendiente". Verificado armando un script puntual contra la base real
adjunta (`get_connection` + `calcular_estadisticas_principales`):
reproducía el mismo $21.242.875 del cuadrito, y con la fórmula
corregida (sumar en vez de restar) baja a $7.631.152 — ya por debajo
del total liquidado, como corresponde.

**Arreglo**: `_saldo_pendiente_periodo` pasa de `max(Liquidado -
Pagado, 0)` a `max(Liquidado + Pagado, 0)` por profesional — sumar el
NETO de los movimientos del período (no restarlo) es lo que corresponde
al signo real: un pago real (negativo) sigue reduciendo el pendiente
(ahora sí, al sumarlo), y un ajuste positivo (un cargo que aumenta la
deuda del período) ahora SUMA al pendiente en vez de restarle, que es
el comportamiento correcto para ese caso.

Los dos tests de la ronda anterior que simulaban un pago con `Monto`
POSITIVO (irreal — un pago real nunca se guarda así) se corrigen a
`Monto` negativo, manteniendo el mismo resultado esperado en pesos
(la fórmula corregida da el mismo número que la fórmula vieja daba con
el signo vuelto al revés, así que los valores esperados de los tests
no cambiaron, solo el signo de la entrada). Se suma un test nuevo para
el caso de un ajuste positivo (debía cubrir el caso que la ronda
anterior no contemplaba: un cargo, no un pago, imputado al período).

Tests: `tests/test_panel_control.py` (signo corregido en los dos tests
de saldo pendiente existentes — `Monto=-4000`/`Monto=-600` en vez de
positivo —, +1 nuevo:
`test_estadisticas_principales_saldo_pendiente_un_ajuste_positivo_
suma_deuda_del_periodo`). Suite: 33 passed, más 168 passed en la
corrida conjunta con `test_balance.py`/`test_gastos_operativos.py`/
`test_gui_panel_control.py` (ver también `docs/historial/balance.md`
para la mitad "Gastos" de esta misma ronda de trabajo). pyflakes
limpio en `app/negocio/panel_control.py`. Verificado además contra la
base de datos real adjunta por la clienta (`espacio_ramos.db`) que el
número final del cuadrito queda por debajo del total liquidado, como
corresponde.

## Panel de control: desglose de "Total liquidado" (feriados/vacaciones/aisladas/cuotas)

La clienta preguntó, con capturas reales, por qué "Monto por reservas
regulares" sale más alto que "Total liquidado" y cómo se calcula cada
concepto — se le explicó (y se confirmó con su base real) que la
diferencia viene de que "Monto por reservas regulares"/"Monto por
reservas aisladas" miran la grilla/reservas VIGENTE tal cual, mientras
que "Total liquidado" resta lo que la liquidación de cada profesional
descuenta por ausencias reales del mes (feriados no trabajados,
vacaciones, licencias) y suma lo que no está en la grilla regular
(aisladas, cuotas de planes de pago). A pedido explícito, esas cuatro
líneas se agregan al cuadrito para que la diferencia se vea de un
vistazo, entre "Total liquidado" y "Saldo pendiente de cobro".

**Tres preguntas de la clienta, respondidas con el código real (no solo
de palabra, confirmado leyendo `app.negocio.liquidaciones`/`vacaciones`/
`licencias`):**

1. El subtotal de reservas regulares (`Tramo.subtotal`, usado tanto por
   `monto_neto_regular_periodo` como por `calcular_liquidacion`) YA está
   neto del descuento por volumen de horas semanales — nunca es el
   bruto.
2. Feriados (recalculado día a día, con el % vigente ESE día —
   `_monto_feriado_dia`) y vacaciones/licencias (`ValorBonificado`,
   congelado al cargar la vacación/licencia pero YA calculado con el %
   vigente en ese momento, ver `crear_vacacion`/`crear_licencia`) también
   están netos de ese mismo descuento — ninguno de los dos trabaja sobre
   el valor bruto.
3. **Hallazgo real, corrige una suposición equivocada de la clienta**:
   "Monto por reservas aisladas" (`monto_neto_aislada_periodo`, en
   `app.negocio.estadisticas`) NO filtra por categoría de profesional —
   suma TODAS las `ReservaAislada` confirmadas del período, incluidas
   las de categoría A (que nunca entran en ninguna liquidación mensual,
   se cobran aparte). Confirmado con la base real: de las aisladas de
   noviembre, 58 eran de profesionales A y solo 20 de R — la mayoría del
   monto que se ve en ese cuadrito corresponde a profesionales que
   jamás tienen una liquidación. Dato a tener en cuenta para la "vista
   previa de balance del negocio" que la clienta quiere armar en el
   octavo cuadrito (en espera de más definición de su parte).

### Implementación

`DesgloseLiquidaciones`/`_desglose_liquidaciones_periodo` (`app/
negocio/panel_control.py`, nuevo campo `EstadisticasPrincipales.
desglose_liquidaciones`): recorre los profesionales con una
`LiquidacionEmitida` este período (misma población que `_total_
liquidado_periodo`) y recalcula la liquidación de cada uno AHORA con
`calcular_liquidacion` — mismo criterio "en vivo" que ya usan `monto_
neto_regular_periodo`/`monto_neto_aislada_periodo` en este mismo
cuadrito (puede no coincidir centavo a centavo con el `MontoGenerado`
ya congelado si algo cambió después de emitida la liquidación, mismo
caso ya documentado para feriados/aisladas — sirve para explicar de un
vistazo, no para una reconciliación exacta). Categoría E (se consolida
en la liquidación de su R) y categoría B (nunca se liquida) hacen que
`calcular_liquidacion` tire `ValueError` — se ignoran en el loop, su
aporte ya está contado en la liquidación del R que las consolida.
`descuento_feriados`/`descuento_vacaciones_licencias` se guardan en
NEGATIVO (restan, mismo signo con el que ya trabaja `formatear_moneda`
para mostrar el "-" solo); `aisladas_en_liquidaciones`/`cuotas_planes_
pago` en positivo (suman). Tiempo medido contra la base real de la
clienta (109 profesionales): 0.175s — no hace falta ningún `Procesando`.

Tests: `tests/test_panel_control.py` (+2: escenario con los cuatro
conceptos a la vez —feriado, vacación, aislada, cuota de plan—, montos
verificados contra las mismas fórmulas de `calcular_liquidacion`; y
una `LiquidacionEmitida` de categoría E con `MontoGenerado=0` no rompe
el desglose); `tests/test_gui_panel_control.py` (+1: las cuatro líneas
quedan entre "Total liquidado" y "Saldo pendiente de cobro"). Suite:
35 + 65 passed, más 153 passed en la corrida conjunta con `test_
liquidaciones.py`. pyflakes limpio en `app/negocio/panel_control.py`,
`app/gui/pantallas/panel_control.py` y los dos archivos de test.

## Panel de control ("Avance de período, backup, y vista rápida"): rediseño completo de la grilla + "Estadísticas principales mes en curso" con tres cuentas en cascada; Balance del negocio ("Ingresos"): columnas rediseñadas

Pedido explícito de la clienta, mensaje textual (ver el hilo completo
para la redacción exacta de cada línea — se resume acá el resultado):
"Vamos a rediseñar la solapa... El tercer cuadro 'Ocupación y horas mes
en curso' ponelo en el segundo cuadro... El sexto cuadro 'Cumpleaños y
días de profesión' lo pones debajo del cuadro 'Feriados y fechas
especiales próximas'... Quedaron libres los tres cuadros de la derecha,
esos los vamos a unificar, queda un solo cuadro largo, ahi vamos a
poner todas las estadísticas mas detalladas". Avisó explícitamente:
"Avisame por cualquier duda, comentario o sugerencia" — se le hicieron
4 preguntas de aclaración antes de tocar código (ver abajo, cada una
cambió o confirmó una parte del diseño).

### Grilla: de 3x3 pareja a 2 columnas de 3 + 1 columna larga

La clienta corrigió por su cuenta una primera lectura equivocada del
pedido (yo había asumido que el séptimo cuadro quedaba "mezclado" con
Feriados en el mismo marco — nunca fue así, los corrigió antes de que
se tocara código): "Van a quedar dos columnas de tres cuadritos, y una
columna entera de un solo cuadro a la derecha, en total son 7, 6 chicos
y uno largo." Con el orden exacto que dio:

- Columna 1 (de arriba a abajo): "Período actual y último backup",
  "Profesionales", "Control de pagos".
- Columna 2 (de arriba a abajo): "Ocupación y horas mes en curso",
  "Feriados y fechas especiales próximas", "Cumpleaños y días de
  profesión".
- Columna 3: un solo cuadro LARGO, "Estadísticas principales mes en
  curso" (ver abajo).

Se eliminan los dos cuadritos "(Sin asignar)" que habían quedado libres
de la ronda anterior — ya no hace falta nada vacío en este diseño.
`_armar_ui` (`app/gui/pantallas/panel_control.py`) pasa del loop
genérico sobre una grilla 3x3 (`QHBoxLayout` por fila) a dos `QVBoxLayout`
("columna_1"/"columna_2", tres cuadritos cada una con `stretch=1`) más
un `QHBoxLayout` externo ("fila_columnas") que pone esas dos columnas
y la tarjeta larga como tres hermanos, los tres con `stretch=1` — así
las tres "columnas" quedan del mismo ancho, y la columna larga queda
del alto de las otras dos juntas (sus tres cuadritos chicos + el
espaciado entre ellos). Se elimina `_armar_tarjeta_vacia` (de baja, sin
otro uso) y la constante `_COLUMNAS_GRILLA` (ya no hace falta, el
armado deja de ser un loop genérico sobre N columnas).

### "Estadísticas principales mes en curso": rediseño completo, tres cuentas en cascada

Diseño pedido por la clienta, tres secciones con subtítulo en itálica,
línea divisoria antes del total, y el total en negrita:

1. **"Liquidaciones mes en curso"**: Monto neto reservas regulares +
   Descuentos por feriados no trabajados (resta) + Descuentos por
   vacaciones (resta) + Descuentos por licencias (resta) + Reservas
   aisladas + Feriados trabajados + Cargos especiales + Cuotas de
   planes de pago + Otros ajustes = **Total liquidado mes en curso**.
2. **"Resultado del negocio"**: Total liquidado mes en curso + Horas
   aisladas por fuera de la liquidación + Reservas extraordinarias por
   fuera de la liquidación + Otros conceptos por fuera de la
   liquidación − Gastos operativos = **Balance del negocio**.
3. **"Monto a cobrar en el mes en curso"**: Monto liquidado más horas
   aisladas − Monto cobrado hasta el momento = **Monto restante del
   mes a cobrar**.

Cuatro preguntas de aclaración, y las cuatro decisiones que fijaron:

- **Q1** (si "Monto total liquidado" en Ingresos/Resultado debía seguir
  filtrando por ubicación): la clienta eligió la opción recomendada,
  "Deja de filtrarse por ubicación" — una liquidación es por
  PROFESIONAL, no se puede partir prolijamente por Consultorio (los
  descuentos de feriados/vacaciones no son por ubicación).
- **Q2** (qué hacer con los conceptos más raros de una liquidación —
  reversión de descuento, feriados pendientes, horas agregadas, ajuste
  por saldo atrasado, ajuste de redondeo — que no tenían línea propia
  en el diseño original de 8 líneas): "Sumarlos en una línea extra
  'Otros ajustes'" — así "Total liquidado mes en curso" cierra SIEMPRE
  exacto con la suma de las liquidaciones recalculadas, nunca "si no
  coincide es porque falta algún concepto".
- **Q3** (cómo tratar lo que generan los profesionales categoría A por
  fuera de cualquier liquidación, más allá de las aisladas): la
  clienta agregó, con el mismo criterio que "Horas aisladas por fuera
  de la liquidación", dos líneas más — "Reservas extraordinarias por
  fuera de la liquidación" y "Otros conceptos por fuera de la
  liquidación" (llaves + cargos especiales sueltos) — y pidió que
  "Monto cobrado hasta el momento" considere los tres para que la
  cuenta cierre ("las horas aisladas, las reservas extraordinarias y
  los conceptos especiales"). En "Ingresos" (Balance del negocio, ver
  `docs/historial/balance.md`), la columna pasa a llamarse "Ingresos
  por fuera de las liquidaciones" y reflejar la suma de esos mismos
  tres conceptos.
- **Q4** (la disposición exacta de la grilla): corrigió una lectura
  equivocada mía (ver arriba) y dio el orden exacto de las dos
  columnas de 3 + la columna larga.

### Negocio: `DesgloseLiquidaciones` (10 campos) + `DesgloseFueraDeLiquidacion` (nueva, en `balance.py`)

`app/negocio/panel_control.py`, `DesgloseLiquidaciones` pasa de 4
campos a 8 líneas visibles + `otros_ajustes` (catch-all) + `cobrado_r`
(no se muestra como línea propia, solo alimenta la Sección 3) — los 8+1
campos suman EXACTO la misma fórmula que `Liquidacion.monto_generado`
(verificado término a término contra esa property), así que "Total
liquidado mes en curso" (`DesgloseLiquidaciones.total`, property nueva)
nunca puede "no coincidir" por faltar un concepto. `_desglose_
liquidaciones_periodo` sigue recalculando EN VIVO con `calcular_
liquidacion` para cada profesional con una liquidación emitida este
período (igual que antes) — `cobrado_r` se calcula reusando la fórmula
ya establecida de "pendiente acotado por profesional" (`pendiente =
max(monto_generado + pagado, 0)`, con `pagado` negativo para un pago
real) y derivando `cobrado = monto_generado - pendiente`.

`app/negocio/balance.py` suma `DesgloseFueraDeLiquidacion` (`aisladas_
normales`/`reservas_extraordinarias`/`otros_conceptos`/`cobrado`, +
property `bruto`) y `fuera_de_liquidacion_periodo`: recorre cada
profesional categoría A (nunca tiene liquidación mensual propia) y
arma, por `Fecha` real del movimiento (a diferencia del desglose de
arriba, que mira si algo "entra" en una liquidación, no la fecha real):
aisladas comunes (mismo criterio que `app.negocio.mensajes.
movimiento_periodo_aislada`, duplicado a propósito en vez de reusar esa
función para no tocar un camino compartido con Centro de mensajería —
mismo criterio de duplicación aceptada entre módulos sin relación que
ya usa el resto del sistema), reservas extraordinarias (`MontoExtraordinario`
a mano), y "otros conceptos" (depósitos/reintegros de `LlaveMovimiento`
+ `CargoEspecial` sin `IdLlave`, para no contar dos veces un cargo ya
atado a una llave). `cobrado` usa el mismo tope por profesional que
`cobrado_r`.

`monto_liquidado_periodo` (nueva, `balance.py`) reemplaza a la vieja
`_total_liquidado_periodo` de `panel_control.py` (de baja, junto con
`_saldo_pendiente_periodo`, también de baja) — es el valor FROZEN (el
`MontoGenerado` real tal como se facturó, con los valores vigentes al
emitir cada liquidación), a propósito DISTINTO del recálculo en vivo
de `DesgloseLiquidaciones` — Ingresos/Resultado pueden mostrar
cualquier período histórico, así que no tiene sentido reconstruirlo con
tarifas de HOY. Los dos valores coinciden en el caso normal (nada
cambió desde la emisión) pero pueden divergir si algo cambió después
— divergencia aceptada, documentada en el docstring de la función.
`ingresos_feriados_trabajados_periodo` queda eliminada (de baja, sin
otro consumidor) — ese concepto ya viene incluido dentro del
`MontoGenerado` congelado.

`total_ingresos_periodo` pasa a devolver `(monto_liquidado, fuera_de_
liquidacion_bruto)` en vez de la tupla de 3 vieja — `ids_consultorio`
queda como parámetro sin usar (compatibilidad de firma con
`resultado_periodo`, que SÍ sigue filtrando Gastos operativos por
ubicación). `resultado_periodo` no cambia de firma, solo de qué suma
para "ingresos".

### GUI: `app/gui/pantallas/panel_control.py` y `app/gui/pantallas/balance.py`

`_armar_tarjeta_estadisticas_principales` deja de ser un solo `QLabel`:
pasa a ser un `QWidget` con su propio `QVBoxLayout` (mismo patrón que
"Período actual y último backup") con, por cada una de las tres
secciones, un subtítulo en itálica (`_subtitulo_italica`, nuevo
helper), una etiqueta de detalle (`QLabel` con las líneas de esa
sección), una línea divisoria (`_linea_divisoria`, ya existía) y una
etiqueta de total en negrita (`setStyleSheet("font-weight: bold;")`) —
con una línea de espacio (`addSpacing(12)`) entre una sección y la
siguiente. `actualizar()` llena cada una de esas seis etiquetas por
separado en vez de un único `setText` con todo el bloque.

"Ingresos" (`_PanelIngresos`, `balance.py` — ver `docs/historial/
balance.md`): `_COLUMNAS_INGRESOS` pasa de 5 columnas a 4; `_fila`/
`_llenar_filas` desempaquetan la tupla nueva de 2 valores de `total_
ingresos_periodo` en vez de la de 3. "Resultado" no cambia de columnas,
solo hereda el "Total ingresos" nuevo.

### Tests

`tests/test_balance.py`: reescritos los tests de `total_ingresos_
periodo` (ahora usa `emitir_liquidacion` real en vez de calcular en
vivo desde reservas sueltas — el "monto liquidado" es FROZEN), eliminado
el test de `ingresos_feriados_trabajados_periodo` (función de baja),
+1 nuevo (`test_fuera_de_liquidacion_periodo_desglosa_tres_conceptos_y_
acota_el_cobrado`, con aislada+extraordinaria+llave+pago de más).
`tests/test_panel_control.py`: reescritos los tests de "saldo
pendiente" (ya no existe — ahora prueban `monto_cobrado`/`monto_
restante_a_cobrar`, con reservas reales + `emitir_liquidacion` en vez
de filas de `LiquidacionEmitida` a mano, porque el recálculo en vivo ya
no lee `MontoGenerado`), reescrito el test de "no duplica reemisiones"
(ahora prueba que el `GROUP BY` no recalcula dos veces al mismo
profesional), actualizados los nombres de campo en los tests de
desglose (`descuento_vacaciones_licencias` → `descuento_vacaciones`/
`descuento_licencias`). `tests/test_gui_panel_control.py`: eliminados
los tests de los cuadritos vacíos y de "siete tarjetas"/"tres filas"
(de baja), +4 nuevos sobre la tarjeta larga (`test_seis_tarjetas_
chicas_y_la_tarjeta_larga_quedan_del_mismo_ancho`, `test_tarjeta_larga_
queda_del_alto_de_sus_tres_hermanas_chicas`, `test_tarjeta_
estadisticas_principales_tres_subtitulos_en_itálica_y_en_orden`, `test_
tarjeta_estadisticas_principales_orden_de_las_tres_secciones`), 1
corregido (`test_hay_una_linea_divisoria_entre_los_dos_botones`, acotado
a las líneas hijas directas del panel, ya que la tarjeta larga suma sus
propias tres). `tests/test_gui_balance.py`: encabezados de "Ingresos"
actualizados, `test_ingresos_recalcula_al_cambiar_periodo` reescrito
con `emitir_liquidacion` real. Suite completa de los cuatro archivos de
negocio/GUI tocados: sin regresiones nuevas (ver CLAUDE.md, "Fallos
conocidos del sandbox/contenedor" para los ~10 fallos preexistentes
ajenos a esta ronda). pyflakes limpio en los ocho archivos tocados.

## Panel de control ("Estadísticas principales mes en curso"): subtítulos subrayados, totales en itálica, línea en blanco; bug real — aisladas cargadas en fecha de feriado

Cuatro pedidos puntuales de la clienta sobre el cuadro largo recién
armado en la ronda anterior:

- Los tres subtítulos de sección (`_subtitulo_italica`) suman
  subrayado además de la itálica que ya tenían
  (`"font-style: italic; text-decoration: underline;"`).
- Los tres totales ("Total liquidado mes en curso"/"Balance del
  negocio"/"Monto restante del mes a cobrar") pasan de negrita a
  itálica SIN subrayar (`"font-style: italic;"`) — corrección explícita
  de la ronda anterior, donde habían quedado en negrita.
- Una línea en blanco (`addSpacing(12)`, mismo valor ya usado entre
  las otras dos secciones) antes del primer subtítulo ("Liquidaciones
  mes en curso").

**Bug real encontrado, investigado antes de tocar nada**: la clienta
reportó que "Feriados trabajados" le daba 0 aunque una profesional (R60
Julieta Battaglia) le avisó que iba a trabajar un feriado descontado —
"en el PDF se incluyó como horas aisladas". Investigado con grep antes
de asumir nada: existe una tabla `FeriadoTrabajado` y todo el cálculo
en `calcular_liquidacion` para ese concepto (`_calcular_feriados_
trabajados`), pero NINGÚN formulario del sistema la usa — no hay
ninguna pantalla para cargar un "feriado trabajado" de verdad. Por eso
la clienta, sin otra alternativa, cargó esas horas como una
`ReservaAislada` en la fecha del feriado — correcta para que se le
pague, pero mal clasificada: el PDF la muestra como "hora aislada" y
este cuadrito la contaba en "Reservas aisladas" en vez de "Feriados
trabajados".

Pedido explícito de la clienta, acotado por ella misma a la sumatoria
de este cuadrito ("ese concepto es el que se tendría que tomar en
cuenta a la hora de la sumatoria en el cuadro este que te estoy
diciendo"): NO se tocó `calcular_liquidacion` ni el PDF ni los mensajes
(sigue viéndose "hora aislada" ahí, sin cambios en esta ronda — ver
`docs/historial/liquidaciones.md` para la ronda posterior que sí
diferenció el texto del PDF) — se acotó la reclasificación a
`_desglose_liquidaciones_periodo` (`app/negocio/panel_control.py`).
Cada ítem de `aisladas_mes_anterior`/`aisladas_mes_en_curso` cuya
`fecha` cae en un feriado nacional/día no laborable activo
(`es_feriado_relevante`, `app.negocio.feriados` — mismo criterio que ya
usa el descuento de feriados en la liquidación real) suma a
`feriados_trabajados` en vez de a `aisladas_en_liquidaciones`; el total
del cuadrito (`DesgloseLiquidaciones.total`) no cambia, solo a qué
línea va cada monto, así que sigue cerrando exacto contra `Liquidacion.
monto_generado`.

Tests: `tests/test_gui_panel_control.py` — reescritos `test_tarjeta_
estadisticas_principales_tres_subtitulos_en_itálica_subrayados_y_en_
orden` (antes sin el subrayado) y `test_tarjeta_estadisticas_
principales_los_tres_totales_van_en_italica_sin_subrayar` (antes
negrita), +1 nuevo (`test_tarjeta_estadisticas_principales_linea_en_
blanco_antes_del_primer_subtitulo`). `tests/test_panel_control.py`:
+1 nuevo (`test_desglose_liquidaciones_aislada_cargada_en_fecha_de_
feriado_cuenta_como_feriado_trabajado`, dos aisladas del mismo
profesional, una en fecha de feriado y otra no, verificando que cada
una cae en la línea correcta). pyflakes limpio en los dos archivos de
negocio/GUI y los dos de test tocados; suites `test_panel_control.py`
(35 passed) y `test_gui_panel_control.py` (66 passed) sin regresiones.

## Panel de control: subtítulos y subtotales en negrita, sin itálica ni subrayado

Pedido explícito de la clienta sobre el cuadro largo "Estadísticas
principales mes en curso": "sacá la itálica de los subtítulos y los
subtotales del cuadro largo, sacá los subrayados también, que tanto
los subtítulos estén en negrita y los subtotales con los importes
también" — tercera vuelta de estilo de este mismo elemento (itálica
+subrayado → itálica sin subrayar en los totales → esta ronda, negrita
a secas en los dos). `_subtitulo_italica` se renombra `_subtitulo_
negrita` (`app/gui/pantallas/panel_control.py`, `font-weight: bold;`
en vez de itálica+subrayado) y los tres `etiqueta_total_liquidado`/
`etiqueta_balance_negocio`/`etiqueta_monto_restante_a_cobrar` pasan de
`"font-style: italic;"` a `"font-weight: bold;"`. Tests reescritos:
`test_tarjeta_estadisticas_principales_tres_subtitulos_en_negrita_y_en_
orden`, `test_tarjeta_estadisticas_principales_los_tres_totales_van_en_
negrita`.

## Panel de control: separar visualmente las tres cuentas de "Estadísticas principales mes en curso"

Pedido explícito de la clienta: "El fondo del contenido de todo el
recuadro de 'Estadísticas principales mes en curso' es todo gris,
separame las tres cuentas con un espacio en blanco finito aunque sea,
como el fondo del título del cuadro, como para que visualmente las
tres secciones dentro del cuadro queden diferenciadas." Investigado
antes de tocar nada: el cuadrito (`QFrame#cuadritoInfo`, `_tarjeta` en
`app/gui/pantallas/panel_control.py`) nunca tuvo un `background-color`
propio — solo el borde — así que tanto el título como el contenido de
abajo caían al gris default de Qt por igual (confirmado armando la
pantalla real offscreen y muestreando píxeles: título y contenido daban
el mismo `#efefef`, ningún color "blanco" preexistente en ningún lado
de este cuadrito en particular).

Cada una de las tres cuentas ("Liquidaciones mes en curso"/"Resultado
del negocio"/"Monto a cobrar en el mes en curso") pasa a envolverse en
su propio widget con objectName nuevo `seccionEstadisticas`
(`_seccion_estadisticas()`, nueva en `panel_control.py`), con fondo
blanco (`t['superficie']`, misma regla QSS que ya usa `QWidget#
panelSolapa` — sumada en `app/gui/estilos.py`) y un margen propio
(`setContentsMargins(6, 6, 6, 6)`). El `addSpacing(12)` que ya separaba
una cuenta de la siguiente queda igual (sigue siendo del mismo gris que
el resto del contenido escrolable, sin pintar nada) — pero ahora, al
estar entre dos secciones blancas, se ve como el "espacio en blanco
finito" pedido: tres cuadros blancos recortados contra el gris de
fondo, en vez de un bloque gris liso sin ninguna separación. Nada de
esto toca los otros cinco cuadritos del panel (`cuadritoInfo` en sí no
cambió, el objectName nuevo es exclusivo de estas tres secciones).

Tests actualizados en `tests/test_gui_panel_control.py`: los dos que
asumían que las seis etiquetas vivían directo en un único `contenido`
compartido (`test_tarjeta_estadisticas_principales_linea_en_blanco_
antes_del_primer_subtitulo`/`test_tarjeta_estadisticas_principales_
orden_de_las_tres_secciones`) se reescriben para subir un nivel más
(`_contenido_estadisticas`, nuevo helper de test) y, en el segundo,
chequear el orden de las TRES secciones entre sí además del orden
detalle→total DENTRO de cada una. Test nuevo:
`test_tarjeta_estadisticas_principales_las_tres_secciones_tienen_
fondo_blanco`. Verificado armando la pantalla real offscreen y
comparando colores de píxeles antes/después (ver captura enviada:
las tres cuentas en blanco, separadas por el gris del cuadrito).
pyflakes limpio en `panel_control.py`/`estilos.py`/el archivo de test.

## Panel de control: sacar la línea en blanco inicial e invertir el esquema de color de "Estadísticas principales"

Pedido explícito de la clienta, ronda siguiente a la de "separar
visualmente las tres secciones": "eliminá esa línea en blanco inicial
arriba de 'Liquidaciones mes en curso', luego invertí los colores de
fondo, todo lo que son las cuentas tiene que estar en gris, y las
líneas intermedias en blanco, o sea al revés que ahora." Investigado
antes de tocar nada (armando la pantalla real offscreen y muestreando
píxeles): el cuadrito (`QFrame#cuadritoInfo`) nunca tuvo un
`background-color` propio — título y contenido caían los dos al mismo
gris default de Qt (`#efefef`), así que "el fondo del título" de la
ronda anterior no era, en rigor, un blanco ya existente — era solo la
referencia de diseño general del sistema.

`_seccion_estadisticas()` (envuelve cada una de las tres cuentas) pierde
su objectName/fondo blanco — vuelve a ser un `QWidget` liso, que
muestra el gris del cuadrito por detrás, igual que el resto del
contenido. El objectName blanco (`t['superficie']`) se muda al
separador INTERMEDIO: `_separador_estadisticas()`, nueva función,
`QWidget` de alto fijo (12px) con objectName `separadorEstadisticas`
(`estilos.py` sube la regla, reemplazando a la vieja `#seccionEstadisticas`)
— se agrega entre cuenta 1→2 y cuenta 2→3 (dos en total), nunca antes
de la primera ni después de la última. El `addSpacing(12)` que
separaba la primera cuenta del título del cuadrito se saca directo, sin
reemplazo — confirmado offscreen que, de paso, esto saca también el
scroll vertical de más que aparecía en el cuadrito (ya no hay contenido
de sobra para el alto disponible).

Tests en `tests/test_gui_panel_control.py`: los dos que asumían fondo
blanco en las cuentas se reescriben (`test_tarjeta_estadisticas_
principales_las_tres_cuentas_sin_fondo_propio` confirma objectName
vacío, `test_tarjeta_estadisticas_principales_los_separadores_
intermedios_tienen_fondo_blanco` confirma exactamente dos widgets
`separadorEstadisticas`); el de la línea en blanco inicial se invierte
(`test_tarjeta_estadisticas_principales_sin_linea_en_blanco_antes_del_
primer_subtitulo`, ahora exige que el primer ítem con widget sea el
índice 0). pyflakes limpio en `panel_control.py`/`estilos.py`/el
archivo de test. Suite conjunta de `test_gui_panel_control.py`/`test_
panel_control.py`: 105 passed.

## Panel de control: refrescar cumpleaños/fechas especiales contra la fecha real, no la del día que se abrió la app

Pedido explícito de la clienta: "Noto que si dejo el sistema abierto de
un día para otro la info que muestra en esa pantalla queda anclada al
día que se abrió, por ejemplo me sigue marcando en rojo cumpleaños de
personas de hace dos días, si se puede que con cada proceso que
refresque el contenido de esa pantalla de acuerdo al día real de la
fecha." Investigado antes de tocar nada: `fecha_real`/`cumpleanos_y_
dias_profesion_proximos` (`app/negocio/dias.py`/`app/negocio/panel_
control.py`) ya recalculan `date.today()` en vivo cada vez que se
llaman — no había ningún valor cacheado ahí. El problema real es que
nada volvía a llamar a `actualizar()` (el método que arma TODO el
contenido de la solapa, incluido el resaltado en rojo de "hoy" en
Cumpleaños/Fechas especiales) con solo el paso del tiempo: solo corría
al construir la pantalla, al volver a entrar a la solapa (`showEvent`)
o con F5 — dejando el sistema abierto en esa misma solapa de un día
para el otro, sin tocar nada, nunca lo volvía a llamar.

El timer del reloj en vivo (`self._timer_reloj`, ya corría cada
segundo para `_actualizar_reloj`, que solo tocaba `etiqueta_reloj`)
pasa a comparar la fecha real contra `self._fecha_ultima_
actualizacion` (nueva, guardada al construir la pantalla) y, si cambió
(cruzó la medianoche), dispara `self.actualizar()` completo una sola
vez — no hace falta recalcular todo cada segundo, solo el día en que
efectivamente cambia. Tests nuevos en `tests/test_gui_panel_control.py`
(mockean `datetime.now`, mismo criterio que el test ya existente del
reloj): `test_actualizar_reloj_dispara_actualizar_completo_al_cruzar_
la_medianoche`, `test_actualizar_reloj_no_dispara_actualizar_completo_
en_el_mismo_dia`; el test preexistente del reloj se actualiza para la
llamada extra a `datetime.now()` que suma `_fecha_ultima_
actualizacion` en el constructor.

## Panel de control: fusionar título e importe en "Estadísticas principales", sacar líneas divisorias

Pedido explícito de la clienta, tercera ronda de rediseño de este
cuadro: "En el cuadro de 'Estadísticas principales mes en curso' en las
tres secciones elimina la linea divisoria y el título de cada
subtotal. El importe quiero que aparezca dentro de cada título. Por
ejemplo, 'Liquidaciones mes en curso: $ 14.341.476,00'. El primer
título que quede 'Total liquidado mes en curso: $ 0.000.000,00'. El
segundo título que quede 'Balance del negocio: $ 0.000.000,00'. El
tercer título que quede 'Saldo a cobrar del mes en curso: $
0.000.000,00'. Los de abajo de los títulos no cambian, solo se
suprimen las lineas divisorias y los importes se reubican junto al
título."

`_armar_tarjeta_estadisticas_principales` (`app/gui/pantallas/
panel_control.py`): cada una de las tres secciones pasa a armar
PRIMERO su propia etiqueta en negrita (`self.etiqueta_total_liquidado`/
`etiqueta_balance_negocio`/`etiqueta_monto_restante_a_cobrar`, ya
existían) con el texto COMBINADO "Título: $ importe" — sin el
`_subtitulo_negrita(...)` suelto de antes ni el `_linea_divisoria()`
que separaba el subtítulo del detalle. Lo de abajo de cada título
(detalle por localidad/edificio, igual que siempre) no se tocó.
`actualizar()` arma ese texto combinado en cada refresco; la tercera
etiqueta cambia de nombre de cara al usuario ("Monto restante del mes
a cobrar" -> "Saldo a cobrar del mes en curso", pedido explícito de
este mismo mensaje) sin cambiar el atributo Python
(`etiqueta_monto_restante_a_cobrar`, para no tocar el resto del código
que ya lo usaba). `_subtitulo_negrita` (la función que armaba el
subtítulo suelto) se elimina del archivo — confirmado sin otro uso.

Tests en `tests/test_gui_panel_control.py`:
`test_tarjeta_estadisticas_principales_muestra_las_lineas_de_las_tres_
secciones` actualizado al nuevo texto "Saldo a cobrar del mes en
curso:". `test_tarjeta_estadisticas_principales_tres_subtitulos_en_
negrita_y_en_orden` renombrado a `...tres_titulos_combinados_en_
negrita_y_en_orden`, ahora chequea que las tres etiquetas (título+
importe) tengan `font-weight: bold;` y que el texto antes de ":" sea
"Total liquidado mes en curso"/"Balance del negocio"/"Saldo a cobrar
del mes en curso" en ese orden. `test_tarjeta_estadisticas_principales_
orden_de_las_tres_secciones` se invierte (ahora el título va ANTES del
detalle, no después). pyflakes limpio en `panel_control.py`. Suite
conjunta de `test_gui_panel_control.py`/`test_panel_control.py`: 105
passed.

## F2: planilla flotante en vez de la calculadora

Pedido explícito de la clienta, en un mismo mensaje junto con otros dos
pedidos sobre Registrar pagos y Mensajes predefinidos (ver
`docs/historial/pagos.md` y `docs/historial/grilla_mensajeria.md` para
esos dos): "F2 Calculadora * Quería saber si en vez de la calculadora
al presionar esa tecla me podría cargar una especie de planilla de
Excel flotante, para hacer anotaciones, cálculos, etc. * Si se puede,
esas anotaciones quiero que se guarde permanentemente, que las pueda
borrar cuando yo quiera, no cuando se cierra el sistema y se vuelve a
entrar se blanquea todo, quiero que se conserven * Es para anotaciones
simples y cálculos simples, temporales, como para tener a mano cada
tanto." Sobre el motor de fórmulas, la clienta aclaró: "fórmulas tipo
excel, funciones básicas de operaciones aritméticas... no fórmulas
complejas... negrita[,] el color de la fuente... algún color de
relleno en las celdas... formato de números de dos decimales y
separador de miles."

`PlanillaFlotante` (`app/gui/widgets/planilla_flotante.py`, motor en
`app/negocio/planilla_flotante.py`) reemplaza por completo a la vieja
`Calculadora` (eliminada, junto con su test). Grilla tipo Excel (12
columnas A-L × 40 filas) con barra de fórmula arriba (no se edita
directo en la celda, todo pasa por ahí, igual que Excel) — fórmulas
con "=" (ej. "=A1+B2*3": +-*/, paréntesis, referencias a otras celdas,
sin funciones — "no fórmulas complejas"), detección de referencia
circular, celdas sin "=" nunca se calculan aunque el texto parezca una
cuenta (para poder anotar texto/números sueltos libremente). Formato
por celda: negrita, color de texto, color de relleno (vía
`QColorDialog`), "Formato número" (dos decimales + separador de miles,
`formatear_miles`, mismo esquema punto-de-miles/coma-decimal que
`formatear_moneda` sin el "$"). Delete/Backspace borra el contenido de
la selección sin tocar el formato. Botón "Vaciar todo" (con
confirmación) borra contenido Y formato de toda la planilla de una.

Persistencia permanente a pedido explícito ("no quiero que se
blanquee al cerrar el sistema, quiero que se conserven"): tabla nueva
`CeldaPlanilla` (`IdCelda` tipo "A1" como PK, `Contenido`, `Negrita`,
`ColorTexto`, `ColorFondo`, `FormatoNumero`) — una fila por celda con
algo propio, sin fila = celda vacía sin estilo (mismo criterio sparse
que `PlantillaTexto`).

### Dos bugs reales de PySide6/shiboken (6.12.0, este sandbox) investigados a fondo para poder armar esta pantalla

**Primero** (resuelto de raíz): guardar un `QFont`/`QBrush`/`QColor`
como rol de un `QTableWidgetItem` (`setFont`/`setForeground`/
`setBackground`) a partir de unos cientos de celdas, y después tocar
su texto, abortaba el proceso al cerrar la ventana ("Fatal Python
error: none_dealloc... bug likely caused by a refcount error in a C
extension"). Se resolvió sacando todo el estilo del modelo/ítem: un
`QStyledItemDelegate` propio (`_DelegadoCelda`) calcula negrita/color
de texto/color de relleno al pintar, leyendo un dict Python común
(`self._celdas`) — nunca persiste un tipo complejo de Qt como rol.

**Segundo** (mitigado, no eliminable desde el código de la app):
investigando por qué el abort seguía apareciendo igual, con o sin
delegate, se confirmó con varios scripts offscreen aislados que el
bug de fondo es muchísimo más general — aparece con `QTableWidgetItem.
setText`, con `setData`, y hasta con un `QAbstractTableModel` propio
sin ningún `QTableWidgetItem` de por medio. El disparador real es un
conteo TOTAL de mutaciones de texto sobre ítems de tabla dentro del
mismo proceso — un número fijo y chico (entre ~700 y ~1000,
confirmado con scripts mínimos de una sola celda), no algo que escale
con la cantidad de celdas ni con crear/destruir ventanas. Por debajo
de ese umbral nunca pasa nada (confirmado hasta 500 mutaciones
sin ningún problema); por encima, el proceso aborta — pero SOLO en el
garbage collection final de Python al cerrar TODO el programa, nunca
durante el uso real (confirmado repetidas veces: el script de prueba
siempre termina su trabajo e imprime su resultado antes de que
aparezca el abort en el shutdown). Es decir: ningún dato se pierde
nunca (ya quedó guardado en SQLite en cada edición), lo que podría
fallar es el cierre prolijo del proceso tras una sesión muy larga de
uso intensivo de esta pantalla puntual.

Mitigado con dos cambios, que entre los dos dejan el conteo real muy
por debajo del umbral en el uso típico ("anotaciones simples... cada
tanto", no una grilla que se recalcula entera en cada tecla):

1. `_recalcular_textos()` solo llama a `item.setText(...)` cuando el
   texto cambió de verdad (antes re-seteaba las 480 celdas completas
   en CADA edición, la inmensa mayoría siempre vacías) — en el uso
   real esto reduce el conteo de mutaciones de cientos por edición a
   prácticamente una sola.
2. `PlanillaFlotante` nunca se destruye: `VentanaPrincipal` crea una
   única instancia la primera vez que se aprieta F2 y la reusa el
   resto de la sesión, alternando `show()`/`hide()` (`closeEvent`
   ignora el cierre real y solo esconde) — así nunca hace falta
   reconstruir la grilla de 480 `QTableWidgetItem` de cero, que por sí
   sola ya es una buena porción del presupuesto antes de llegar al
   umbral.

El resto de las pantallas del sistema no tropieza con este bug en el
uso diario porque ninguna mantiene un ítem de tabla vivo mutando su
texto cientos de veces en la misma sesión — todas rearman sus
`QTableWidgetItem` de cero en cada refresco (bastantes menos refrescos
por sesión que ediciones posibles en una planilla de notas). No se
encontró ninguna forma de eliminar el bug de fondo desde código de la
aplicación (se probó, sin éxito: `gc.disable()`, llamar
`QApplication.processEvents()` seguido, reemplazar `setText` por
`setData`, reemplazar `QTableWidgetItem` por un `QAbstractTableModel`
propio) — es un defecto del build de PySide6/shiboken instalado en
este sandbox (`pip show PySide6` → 6.12.0), no de cómo está armada
esta pantalla. Mismo criterio que el resto de los "Fallos conocidos
del sandbox/contenedor" (ver CLAUDE.md): no bloquea cerrar la ronda,
pero vale la pena confirmar en el entorno real de la clienta (Windows)
si esta versión puntual de PySide6 también lo tiene, antes de que haga
un uso muy intensivo y prolongado de esta pantalla en particular.

Tests: `tests/test_planilla_flotante.py` (27, motor de fórmulas y
persistencia: valores/fórmulas/referencias/ciclos/errores, formato de
miles, guardar/leer/vaciar). `tests/test_gui_widget_planilla_
flotante.py` (17, la ventana real: escribir y persistir, fórmulas con
referencias, notas sueltas no se calculan, confirmar con Enter baja
una fila, negrita/color de texto/color de relleno/formato número
sobre una celda y sobre una selección múltiple, Delete/Backspace,
Vaciar todo con y sin confirmar, recarga desde lo ya guardado al
construir una instancia nueva, cerrar con la cruz solo esconde). Este
archivo comparte una ÚNICA instancia de `PlanillaFlotante` entre todos
sus tests (fixture `_instancia_compartida`, reconectada a la base de
cada test sin reconstruir la ventana) — mismo criterio que la app
real, y necesario para no disparar el segundo bug de arriba dentro de
la propia suite (confirmado: construir una instancia nueva por test,
~13 veces, ya lo disparaba).

`tests/test_main_window.py`: `test_f2_abre_una_sola_calculadora_y_f2_
de_nuevo_la_cierra` se reemplaza por `test_f2_abre_la_planilla_y_f2_
de_nuevo_la_oculta` (misma instancia siempre, `show()`/`hide()` en vez
de crear/destruir) y se actualiza la leyenda de la barra de estado
("F2 – Planilla" en vez de "F2 – Calculadora"). `app/gui/widgets/
calculadora.py` y `tests/test_gui_widget_calculadora.py` se eliminan
(sin otro uso confirmado con `grep -rln "Calculadora\b" app/ tests/`).

pyflakes limpio en los ocho archivos de `app/` tocados (`app/db/
schema.sql`, `app/gui/crud_generico.py`, `app/gui/main_window.py`,
`app/gui/pantallas/pagos.py`, `app/gui/pantallas/textos_sistema.py`,
`app/gui/widgets/planilla_flotante.py` nuevo, `app/negocio/mensajes.py`,
`app/negocio/plantillas_texto.py`, `app/negocio/planilla_flotante.py`
nuevo) y los ocho de test tocados/nuevos.

Suite completa (`pytest tests/`, 3290 tests): 13 failed, 3277 passed —
los 13 son EXACTAMENTE los ya documentados (ver CLAUDE.md, "Fallos
conocidos del sandbox/contenedor": los 3 de `test_avance_mes.py`, los
3 de `test_gui_mensajeria.py` y los 7 de calibración de fuentes),
ninguno nuevo de esta ronda. Al final de esa corrida, después de
imprimirse el resumen completo, aparece un crash de memoria del
proceso ("malloc(): unaligned tcache chunk detected") — confirmado con
una segunda corrida completa EXCLUYENDO los dos archivos de test
nuevos de la planilla (`--ignore=tests/test_gui_widget_planilla_
flotante.py --ignore=tests/test_planilla_flotante.py`) que el mismo
crash, con los mismos 13 fallos, aparece IGUAL sin esos archivos — así
que no lo causa esta ronda: es un artefacto preexistente de correr la
suite entera (~3290 tests, muchas pantallas con `QTableWidget` pesado)
en un solo proceso, de la misma familia de bug de PySide6/shiboken
investigada arriba para la planilla, pero a una escala que ya se da
sin que esta ronda le agregue nada.

## F2 - Planilla: escribir directo en la celda al navegar + "+" como sinónimo de "="

Dos pedidos puntuales de la clienta sobre la planilla flotante:

> "F2 - Planilla * Que al navegar con el cursor se pueda empezar a
> escribir directamente en la celda * Que al poner '+C2+C3' por
> ejemplo sea lo mismo que '=C2+C3', que haga la suma de las dos
> celdas."

### "+" como sinónimo de "=" (motor de fórmulas)

`app/negocio/planilla_flotante.py` suma `_es_formula`/`_expresion_
formula`: una celda es fórmula si arranca con "=" O con "+" (mismo
criterio que Excel/Lotus 1-2-3 con el signo "+" — "no quiero que sea
fórmula" nunca se pidió para "-", así que a propósito NO se suma como
sinónimo: un número negativo suelto, ej. "-500", sigue siendo una
nota/número como hasta ahora, no una fórmula). Al evaluar, el "=" se
descarta (no es un operador válido) pero el "+" se deja tal cual (es
una suma unaria válida, `eval("+5+3")` da 8 sin tocar nada). `valor_
celda`/`texto_resultado_celda` usan estos dos helpers en vez de
chequear `startswith("=")` a mano. Tests nuevos en `tests/test_
planilla_flotante.py`: `test_valor_celda_mas_al_principio_es_sinonimo_
de_formula`, `test_valor_celda_mas_solo_tambien_es_formula`, `test_
valor_celda_menos_al_principio_no_es_formula` (confirma que "-" sigue
sin ser fórmula), `test_texto_resultado_celda_con_mas_calcula_igual_
que_con_igual`.

### Escribir directo en la celda al navegar (GUI)

Hasta esta ronda, las celdas de la grilla no tenían `ItemIsEditable` y
TODA edición pasaba por la barra de fórmula — tipear estando parado en
una celda (sin haber clickeado antes la barra) no hacía nada útil
(Qt lo tomaba como búsqueda incremental de ítems, el comportamiento
default de `QAbstractItemView`). `PlanillaFlotante.eventFilter`
(`app/gui/widgets/planilla_flotante.py`) suma: cualquier tecla con
texto imprimible (que no sea Delete/Backspace, ya manejadas) dispara
`_empezar_a_escribir(texto)` — pone ese texto en la barra de fórmula,
marca el pendiente (`_marcar_pendiente`) y le pasa el foco a la barra,
con el cursor al final (`QLineEdit.end(False)`). Mismo comportamiento
que Excel: tipear sobre una celda ya con contenido lo PISA entero, no
lo agrega. Solo hace falta interceptar la PRIMERA tecla — una vez que
el foco está en la barra de fórmula, el resto de lo que se tipee lo
recibe esa misma `QLineEdit` de forma nativa (`textEdited` ya estaba
conectado a `_marcar_pendiente` desde el armado original de la
pantalla). Las celdas en sí siguen sin `ItemIsEditable` — Qt nunca
abre un editor nativo sobre ellas, la edición de verdad sigue siendo
siempre la barra de fórmula, solo que ahora se puede arrancar sin
clickearla primero.

Tests nuevos en `tests/test_gui_widget_planilla_flotante.py`: `test_
tipear_en_la_tabla_sin_tocar_la_barra_arranca_edicion_en_la_celda`
(tecla real vía `qtbot.keyClick` sobre la tabla, confirma que el texto
llega a la barra y que Enter lo confirma en la celda — sin chequear
`hasFocus()`, frágil bajo Qt offscreen sin la ventana realmente activa;
alcanza con confirmar que el texto efectivamente llegó y se puede
confirmar), `test_tipear_en_la_celda_pisa_el_contenido_anterior`,
`test_tipear_varias_teclas_seguidas_se_siguen_acumulando_en_la_barra`
(confirma que solo la primera tecla necesita interceptarse).

pyflakes limpio en `app/negocio/planilla_flotante.py` y `app/gui/
widgets/planilla_flotante.py`. Suite conjunta de `tests/test_planilla_
flotante.py`/`tests/test_gui_widget_planilla_flotante.py`/`tests/test_
main_window.py`: 100 passed.

## F2 - Planilla auxiliar: alineación, selección al navegar, apertura maximizada, renombre

Siguiente tanda de pedidos sobre la planilla flotante, en un mismo
mensaje (dos de los puntos — "+" como fórmula y escribir directo al
navegar — ya estaban resueltos de la ronda anterior, se confirmaron sin
tocar nada más):

> "F2 - Planilla * Explicame como hacer una fórmula 'suma' o 'sumar',
> como para sumar un rango de celdas * Agregame botones para
> alineaciones, derecha, centro o izquierda * Que por defecto lo que es
> texto se justifique a la izquierda y los valores a la derecha * Al
> seleccionar una celda con el mouse ya me tiene que dejar el foco para
> empezar a escribir, que el texto que este cargado al pinchar se
> seleccione todo por si quiero volver a escribir arriba y borrar el
> contenido con ese acto. * Cambiale la etiqueta al menú, en lugar de
> 'F2 - Planilla' que 'F2 - Planilla auxiliar' * Que la planilla se
> abra maximizada, y con la planilla activa, si vuelvo a presionar F2
> que se cierre manteniendo los valores cargados."

### Cómo sumar un rango de celdas (respuesta, no requiere código)

El motor de fórmulas sigue sin funciones tipo `SUMA`/`SUM` — "funciones
básicas de operaciones aritméticas... no fórmulas complejas" es el
pedido original. Para sumar un rango hoy hay que escribir cada celda
sumada con "+", ej. para sumar C2 a C10: `=C2+C3+C4+C5+C6+C7+C8+C9+C10`
(o con el atajo "+" nuevo de la ronda anterior, arrancando directo con
"+": `+C2+C3+C4+C5+C6+C7+C8+C9+C10`, mismo resultado). No hay una
sintaxis de rango (`C2:C10`) — hay que nombrar cada celda.

### Botones de alineación + default automático (texto izquierda, número derecha)

Tres botones nuevos ("Izquierda"/"Centro"/"Derecha", en la misma fila
que Negrita/Color de texto/Color de relleno/Formato número) aplican un
override EXPLÍCITO de alineación a la celda/selección actual
(`_alinear`, `app/gui/widgets/planilla_flotante.py`) — mismo mecanismo
`_aplicar_a_seleccion` que ya usan negrita/color/formato número.

Sin ese override, `_alineacion_efectiva` decide un default automático:
mira si la celda resuelve a un número (`valor_celda` de `app.negocio.
planilla_flotante` — fórmula o número suelto, no `None`) y, si es así,
alinea a la derecha; si no (texto/nota suelta, vacía, o una fórmula con
error), a la izquierda. `_estilo_en` (la función que lee el delegate en
cada repintado) resuelve esto antes de devolver el estilo, así que
`_DelegadoCelda` nunca ve `None` en `estilo["alineacion"]` — solo
necesita mapear "izquierda"/"centro"/"derecha" a `Qt.AlignmentFlag` vía
`option.displayAlignment`.

Persistencia: columna nueva `CeldaPlanilla.Alineacion` (`TEXT`, 
`NULL` = sin override) — sumada tanto en `schema.sql` (bases nuevas)
como en `_COLUMNAS_NUEVAS` de `app/db/migraciones.py` (bases ya
creadas con la tabla vieja, mismo mecanismo que cualquier columna
nueva sobre una tabla existente). `guardar_celda`/`leer_celdas`
(`app/negocio/planilla_flotante.py`) suman el parámetro/campo; el
chequeo de "celda vacía, no hace falta la fila" ahora también exige
`alineacion is None`.

### Selección al navegar/pinchar una celda (foco + selección de contenido)

Investigado antes de tocar nada: "empezar a escribir al seleccionar
con el mouse" ya funcionaba sin cambios — el `eventFilter` que
intercepta la primera tecla imprimible (sumado la ronda anterior) está
en la TABLA, así que da lo mismo si el foco llegó ahí por teclado o por
un click del mouse en una celda (Qt le da foco al widget clickeado).
Lo que faltaba era la segunda parte del pedido: "que el texto que esté
cargado al pinchar se seleccione todo" — `_cargar_barra_formula`
(llamada en cada cambio de celda, click o navegación) suma `self.
barra_formula.selectAll()` después de cargar el contenido. A diferencia
de `instalar_seleccionar_todo_al_enfocar` (`app/gui/widgets/foco.py`,
usado en el resto del sistema), no hace falta el `QTimer.singleShot`
de ese mecanismo: ahí el click que dispara el foco es sobre el MISMO
widget que hay que seleccionar (Qt reposiciona el cursor después,
pisando un `selectAll()` inmediato) — acá el click que cambia de celda
es sobre la TABLA, un widget distinto de la barra de fórmula, así que
no hay nada que compita por pisar la selección.

### Renombre de la leyenda + apertura maximizada/activa

`self._etiqueta_funciones` (`app/gui/main_window.py`) cambia "F2 –
Planilla" por "F2 – Planilla auxiliar". `_abrir_calculadora` (el
método atrás de F2) pasa de `self._planilla.show()` a `self._planilla.
showMaximized()` + `self._planilla.activateWindow()` en la rama que
la muestra — "que se abra maximizada, y con la planilla activa". La
rama que la oculta (F2 con la ventana ya visible) no cambió, y
tampoco el resto del mecanismo de instancia única (`show()`/`hide()`,
nunca se destruye) — "si vuelvo a presionar F2 que se cierre
manteniendo los valores cargados" ya se cumplía sin tocar nada (los
datos viven en `self._celdas`/SQLite, ajenos a mostrar/ocultar la
ventana).

Tests nuevos en `tests/test_gui_widget_planilla_flotante.py`: `test_
cambiar_de_celda_selecciona_todo_el_contenido_de_la_barra`, `test_
alineacion_por_defecto_texto_izquierda_numero_derecha`, `test_boton_
de_alineacion_pisa_el_default_y_persiste`, `test_boton_de_alineacion_
centro_se_aplica_a_toda_la_seleccion`. En `tests/test_planilla_
flotante.py`: `test_guardar_celda_vacia_pero_con_alineacion_si_deja_
fila`, más el test de persistencia existente actualizado con
`alineacion="centro"`. En `tests/test_main_window.py`: `test_
etiqueta_de_funciones_f1_a_f12` actualizado al nuevo texto, test nuevo
`test_f2_abre_la_planilla_maximizada_y_activa` (mockea `showMaximized`/
`activateWindow` de la instancia y confirma que se llaman en ese
orden al volver a abrir, no en la apertura que la oculta).

pyflakes limpio en `app/db/migraciones.py`, `app/gui/main_window.py`,
`app/gui/widgets/planilla_flotante.py`, `app/negocio/planilla_
flotante.py` y los tres archivos de test tocados. Suite conjunta de
`tests/test_planilla_flotante.py`/`tests/test_gui_widget_planilla_
flotante.py`/`tests/test_main_window.py`/`tests/test_migraciones.py`:
150 passed.

## F2 - Planilla auxiliar: F2/ApplicationShortcut, modo señalar, grilla A-Z/1-100, combinar celdas — y un bug de PySide6 más serio que los anteriores

Ronda siguiente, cinco pedidos puntuales sobre la misma pantalla:

> "Con F2 de nuevo con la planilla activa no cierra la pantalla. Fijate
> si se puede hacer con esa tecla o si no con otra, como con ESC"
> "Si empiezo a generar una suma o una operación en una celda, quiero
> que al presionar el cursor me navegue con en excel para otras celdas
> como para ir generando las operaciones de esa manera, es decir,
> empiezo a escribir en '+45+' en C1, presiono cursor abajo, ahi
> quedaría '+45+C2', a medida de que sigo poniendo signos me sigue
> concatenendo celdas o números."
> "Columnas hasta la Z, filas hasta la 100"
> "Agregame un botón de combinar celdas, que es botón también
> descombine. Que los botones queden en una sola fila, reducí el ancho
> de los mismos"
> "La alineación vertical siempre centralizada"

### F2 no cerraba la planilla con ella activa

Investigado antes de tocar nada: `QShortcut` usa por default `Qt.
ShortcutContext.WindowShortcut` — solo dispara si la ventana DUEÑA del
atajo (`VentanaPrincipal`, acá `self`) tiene el foco. La planilla es
otra ventana de nivel superior (`Qt.WindowType.Window`) — en cuanto
ella pasa a tener el foco (justo lo que pasa al abrirla, "con la
planilla activa" de la ronda anterior), F2 registrado en
`VentanaPrincipal` deja de verse, aunque las dos ventanas sean de la
MISMA aplicación. `self._atajo_calculadora.setContext(Qt.
ShortcutContext.ApplicationShortcut)` (`app/gui/main_window.py`) lo
hace disparar sin importar cuál de las dos ventanas esté activa —
mismo atajo F2, no hizo falta pasar a ESC. Test nuevo en `tests/test_
main_window.py`: `test_atajo_f2_usa_contexto_de_aplicacion_no_de_
ventana` (confirma `context() == ApplicationShortcut` directo, en vez
de simular foco real entre dos ventanas top-level, frágil bajo Qt
offscreen).

### "Modo señalar" (navegación tipo Excel al armar una fórmula)

Mismo mecanismo que Excel: con el cursor dentro de una fórmula en
construcción en la barra de fórmula ("=" o "+" al principio), cada
flecha CONCATENA una referencia de celda en vez de mover el cursor de
texto. `_mover_puntero_formula`/`_al_tipear_en_formula`
(`app/gui/widgets/planilla_flotante.py`) distinguen, sin más estado que
dos pares de atributos nuevos (`_punto_fila`/`_punto_columna`,
`_puntero_activo`), dos casos sobre el ejemplo de la clienta ("+45+" en
C1, cursor abajo → "+45+C2", seguir poniendo signos sigue
concatenando"):

- Flecha tras OTRA flecha (sin tipear nada real en el medio): MUEVE la
  referencia ya insertada (la reemplaza) — "cursor abajo, cursor abajo"
  dos veces seguidas desde C1 da "+45+C3", no "+45+C2+C3".
- Flecha tras tipear algo real (`textEdited` real del usuario, no un
  `setText` programático de este mismo mecanismo — distinción clave:
  `textEdited` nunca se dispara con `setText()`): la referencia
  anterior queda "fijada" y la próxima flecha agrega una referencia
  NUEVA, partiendo de la última celda señalada (no de la celda que se
  está editando) — así se puede "caminar" la misma fila/columna de a
  una celda, sumando signos entre cada una, igual que en Excel.

El `eventFilter` ya existente (intercepta Delete/Backspace y la
primera tecla imprimible de la tabla) suma: una flecha en la barra de
fórmula, con el texto actual arrancando en "=" o "+", dispara este
modo en vez de mover el cursor de texto nativo — sin prefijo de
fórmula, la flecha se deja pasar sin tocar nada (una nota suelta no
entra en este modo). Tests nuevos en `tests/test_gui_widget_planilla_
flotante.py`: `test_flecha_abajo_en_formula_concatena_referencia_de_
celda` (el ejemplo exacto de la clienta), `test_flechas_consecutivas_
mueven_la_misma_referencia_en_vez_de_agregar`, `test_tipear_entre_
flechas_fija_la_referencia_y_agrega_una_nueva`, `test_flecha_sin_
prefijo_de_formula_no_dispara_el_modo_senalar`.

### Botón combinar/descombinar + una sola fila de botones más angosta

`_combinar_celdas` (nueva): un solo botón que combina o descombina
según el estado actual de la selección — "un botón de combinar
celdas, que es botón también descombine" — mira `rowSpan`/`columnSpan`
de la celda superior-izquierda de la selección con `QTableWidget.
setSpan(...)` (combinar) o `setSpan(fila, columna, 1, 1)`
(descombinar, API nativa de Qt para deshacer un span). Sin
persistencia propia (a diferencia del resto de la planilla, que
guarda todo en `CeldaPlanilla`) — no se pidió explícitamente guardarlo,
y la ventana de todos modos nunca se destruye durante la sesión, así
que sobrevive a mostrar/ocultar con F2 igual; si se cierra TODO el
sistema, se pierde (se documenta así, sin guardarlo, mismo criterio
que "a veces se prueba algo y no se lo guarda si no se pidió
explícitamente").

"Que los botones queden en una sola fila, reducí el ancho de los
mismos": `ancho_boton = max(QFontMetrics(self.font()).
horizontalAdvance(b.text()) for b in botones) + 16` (mismo criterio
de ancho fijo único del resto del sistema, calculado para que entre
el texto más largo) en vez del ancho automático de cada botón — de
paso, los textos se acortan ("Color de texto" → "Color texto", "Color
de relleno" → "Color fondo", "Formato número" → "Formato núm.") para
que la fila entera entre sin tener que agrandar la ventana. Tests
nuevos: `test_boton_combinar_combina_la_seleccion`, `test_boton_
combinar_es_el_mismo_boton_para_combinar_y_descombinar`, `test_sin_
seleccion_combinar_no_hace_nada`, `test_todos_los_botones_de_estilo_
tienen_el_mismo_ancho`.

### Alineación vertical siempre centralizada

Ya estaba resuelto sin tocar nada — `_ALINEACION_QT` (los tres valores
de alineación horizontal) ya incluía `Qt.AlignmentFlag.AlignVCenter`
en los tres desde que se armó este mecanismo (ronda anterior). Test
nuevo de todos modos para dejarlo cubierto explícitamente: `test_
alineacion_vertical_siempre_centralizada`.

### Grilla "columnas hasta la Z, filas hasta la 100" — y un CUARTO bug de PySide6/shiboken, más serio que los tres anteriores

`_COLUMNAS`/`_FILAS` pasan de 12×40 (480 celdas) a 26×100 (2600
celdas), tal como se pidió. Investigando esto a fondo aparecieron DOS
hallazgos nuevos de PySide6/shiboken (6.12.0, este sandbox — ver el
docstring completo de `PlanillaFlotante` para el detalle técnico de
los cuatro hallazgos, el primero y el segundo ya documentados en
rondas anteriores):

- **Tercero**: crear los `QTableWidgetItem` de las 2600 celdas de
  entrada (como hacía la vieja `_refrescar_grilla`, solo para poder
  apagarles `ItemIsEditable`) ya cruza, por sí solo, el mismo umbral
  de ~700-1000 ya documentado para mutaciones de texto — confirmado
  con un script offscreen que crea ítems vacíos sin tocar su texto
  nunca. **Mitigado**: `self.tabla.setEditTriggers(QAbstractItemView.
  EditTrigger.NoEditTriggers)` apaga la edición nativa a nivel TABLA
  en vez de por ítem (confirmado que alcanza igual, ningún editor se
  abre aunque la celda no tenga ítem propio) — así, `_recalcular_
  textos` puede crear cada `QTableWidgetItem` de forma PEREZOSA, recién
  la primera vez que una celda necesita mostrar texto no vacío, en vez
  de las 2600 de entrada. En el uso real ("anotaciones simples... cada
  tanto") la enorme mayoría de las celdas nunca llega a necesitar un
  ítem.

- **Cuarto, sin mitigación posible desde código de la app**: aun con
  ese fix — CERO ítems creados, instancia recién construida — el mismo
  abort ("Fatal Python error: none_dealloc") sigue apareciendo en algún
  punto posterior del mismo proceso, con la grilla en 100×26.
  Achicado con scripts offscreen que solo construyen un `QTableWidget`
  liso (sin ítems, sin delegate, sin esta pantalla): con 26 columnas
  fijas, 65 filas (1690 celdas) nunca rompe, 70 filas (1820 celdas) sí
  — un umbral FIJO, parecido al de los hallazgos anteriores, pero que
  depende de la estructura interna fila×columna del propio
  `QTableWidget`/`QHeaderView` (secciones de encabezado, índices de
  modelo), no de los ítems que contiene — con una sola columna, en
  cambio, 1100 filas no rompe, así que tampoco es un simple total
  filas×columnas. Mismo criterio que el resto de los "Fallos conocidos
  del sandbox/contenedor" (ver CLAUDE.md): es un bug de la librería, no
  de esta pantalla, nunca se pierde ningún dato (todo ya quedó en
  SQLite en cada edición) y no se encontró ninguna mitigación de
  código que lo elimine sin achicar la grilla por debajo de ese umbral
  — lo que iría en contra del pedido explícito. Se deja documentado,
  pendiente de confirmar si el build de PySide6 del entorno real de la
  clienta (Windows) también lo tiene.

**Impacto en la suite de tests** (no en la app real): corriendo la
grilla de PRODUCCIÓN (2600 celdas) dentro de una sesión de `pytest`
— que ya trae su propio "churn" de objetos Qt por los fixtures/qtbot
de otros tests — el umbral del cuarto hallazgo se cruza mucho antes
(confirmado: con un `QTableWidget` de 100×26 compartido entre los 24
tests de `tests/test_gui_widget_planilla_flotante.py`, el abort
aparecía DETERMINÍSTICAMENTE a mitad de la suite, no solo al cierre
final del proceso como en los hallazgos anteriores). `tests/
conftest.py` suma un fixture `autouse`/`scope="session"`
(`_planilla_flotante_grilla_chica_para_tests`) que achica `_FILAS`/
`_COLUMNAS` a 15×15 (225 celdas, de sobra para cualquier test — ninguno
usa más allá de la fila/columna 5) durante TODA la sesión de tests,
sin tocar los valores de producción (la app real sigue armando la
grilla completa pedida) — con esto, la suite vuelve a correr sin
abortar a mitad de camino; el único abort que puede seguir apareciendo
es el ya documentado "al final, después de imprimirse el resumen
completo" (ver CLAUDE.md, "Fallos conocidos del sandbox/contenedor"),
que no afecta el resultado reportado de ningún test.

Tests nuevos: ninguno específico de este hallazgo (es un bug de
infraestructura de test, no de comportamiento de la pantalla) — se
confirma indirectamente con el resto de la suite de esta pantalla
corriendo sin abortar.

### Resumen de verificación

pyflakes limpio en `app/gui/main_window.py`, `app/gui/widgets/
planilla_flotante.py`, `tests/conftest.py` y los dos archivos de test
tocados. Suite conjunta de `tests/test_gui_widget_planilla_flotante.
py`/`tests/test_planilla_flotante.py`/`tests/test_main_window.py`:
116 passed (más el artefacto ya documentado de fin de proceso, sin
afectar el resultado de ningún test).

## Base de datos: renombre a `sistemadf.db`

Pedido explícito de la clienta: en vez de esperar un "final" de la
revisión pantalla por pantalla (que en la práctica no tiene un punto
de cierre fijo — sigue apareciendo algo nuevo en cada ronda), hacer el
renombre ahora, con las precauciones correspondientes, en vez de
dejarlo indefinidamente pendiente.

`DB_PATH_DEFAULT` (`app/db/connection.py`) pasa de `data/espacio_
ramos.db` a `data/sistemadf.db` — único lugar real del código que fija
el nombre (`get_connection`/`init_database`/`main.py`/`gui_main.py`
todos lo toman de esta constante, nunca lo repiten). Se revisó todo el
repo (`grep` de "espacio_ramos" fuera de `docs/historial/`) antes de
tocar nada, para no dejar una referencia vieja suelta: aparte de esta
constante, solo quedaban un mención en `README.md` (actualizada al
nuevo nombre) y un `assert` en `tests/test_connection.py` que compara
contra el valor real de la constante (actualizado). El resto de las
apariciones (`tests/test_backup.py`/`tests/test_instancia_unica.py`)
son nombres de archivo ARBITRARIOS que esos tests usan para un
`tmp_path` de prueba — no dependen del nombre real y funcionan igual
con cualquier nombre, así que se dejan como estaban.

**Importante, de cara al entorno real de la clienta:** este cambio
es puramente de código — el archivo real `data/espacio_ramos.db` de
su máquina NO se renombra solo. Sin el paso manual correspondiente,
al levantar esta versión el programa va a buscar `data/sistemadf.db`,
no lo va a encontrar, y le va a crear uno nuevo VACÍO con ese nombre
(mismo mecanismo de `get_connection`/`init_database` que crea la base
si no existe) — sin perder el archivo viejo, pero sin verlo tampoco.
Paso a paso que tiene que hacer ella antes de levantar esta versión:
1. Backup de `data/espacio_ramos.db` (por las dudas, aparte del
   backup que ya hace el propio sistema).
2. Renombrar ese archivo a `data/sistemadf.db` (mismo directorio).
3. Levantar la versión nueva del código normalmente — va a encontrar
   la base ya renombrada y seguir con todos los datos tal cual estaban.

Tests actualizados: `tests/test_connection.py` (el `assert` contra
`DB_PATH_DEFAULT`). pyflakes limpio en `app/db/connection.py` y el
archivo de test. Suite conjunta de `tests/test_connection.py`/`tests/
test_instancia_unica.py`/`tests/test_backup.py`/`tests/test_
migraciones.py`: 93 passed.

Aparte, se le confirmó a la clienta que el archivo de bloqueo
(`espacio_ramos.db.lock`) NO hace falta renombrarlo a mano —
`BloqueoInstanciaUnica` (`app/negocio/instancia_unica.py`) lo deriva
siempre del nombre de la base (`db_path.name + ".lock"`), así que en
cuanto la base quede renombrada y se levante la versión nueva, el
`.lock` nuevo (`sistemadf.db.lock`) se crea solo. El viejo queda
huérfano pero inofensivo (es un archivo de control, no de datos) —
se puede borrar sin problema, no es obligatorio.

## F2 - Planilla auxiliar: botones Copiar/Pegar + fórmula SUMA(rango)

Dos pedidos puntuales de la clienta sobre la planilla flotante:

> "Agregame los botones de copiar y pegar, para copiar celdas o
> rangos de celdas"
> "Se puede crear una fórmula sola como para sumar un rango de
> celdas..?"

### Botones Copiar/Pegar

`_copiar`/`_pegar` (`app/gui/widgets/planilla_flotante.py`), nuevos,
primeros de la fila de botones (antes de "Negrita"). `_copiar` guarda
en un portapapeles interno (`self._portapapeles`, una lista nueva —
NO el portapapeles del sistema operativo, es copiar/pegar DENTRO de
la planilla) la posición RELATIVA de cada celda de la selección
actual (o la celda actual, sin selección) dentro del rectángulo
copiado, junto con su estilo completo (contenido, negrita, colores,
formato número, alineación — mismo criterio "todo junto" que ya usa
`_estilo`/`_aplicar_a_seleccion` para el resto de los botones).
`_pegar` reproduce esa misma forma relativa anclada en la celda
ACTUAL (la que tenga el foco al apretar "Pegar") — las celdas que
caerían afuera de la grilla al pegar cerca de un borde se descartan
sin romper nada.

No ajusta referencias de fórmula al pegar en otra posición (ej.
"=A1+1" se pega tal cual, no se corre a "=A2+1") — a propósito, mismo
criterio de "sin fórmulas complejas" del resto del motor; un
ajuste de referencias relativas al estilo Excel es una pieza bastante
más grande que lo que se pidió ("copiar celdas o rangos de celdas").

Tests nuevos en `tests/test_gui_widget_planilla_flotante.py`:
`test_copiar_y_pegar_una_sola_celda`, `test_copiar_y_pegar_copia_
tambien_el_formato`, `test_copiar_y_pegar_un_rango_mantiene_la_
forma`, `test_pegar_cerca_del_borde_descarta_las_celdas_que_quedan_
afuera`, `test_pegar_sin_copiar_antes_no_hace_nada` (portapapeles
vacío a propósito, en vez de confiar en que ningún test anterior
sobre la misma instancia compartida haya copiado algo — ver
`_instancia_compartida`). `test_todos_los_botones_de_estilo_tienen_
el_mismo_ancho` actualizado para incluir los dos botones nuevos en
el chequeo de ancho uniforme.

### `SUMA(rango)`: única excepción al motor "sin funciones"

Pedido explícito de la clienta, repitiendo la pregunta de una ronda
anterior (donde se le explicó que solo se podía sumar nombrando cada
celda con "+") — esta vez se agrega de verdad. `_PATRON_RANGO`
(`app/negocio/planilla_flotante.py`) reconoce `SUMA(C2:C10)` (también
bloques de varias columnas/filas, ej. `SUMA(A1:B10)`, igual que
Excel) y lo reemplaza por el número ya calculado ANTES de que
`_PATRON_CELDA` procese el resto de la fórmula — así que
"=SUMA(C2:C10)+D1" sigue funcionando (el "+D1" lo resuelve el
mecanismo de siempre). `_indice_columna`/`_letra_desde_indice`/
`_celdas_en_rango`, nuevas, hacen la conversión letra↔índice de
columna (base-26 estándar de cualquier planilla) y expanden las dos
esquinas del rango a la lista de direcciones del rectángulo entre
ellas (funciona con las esquinas en cualquier orden, ej. "SUMA(C4:C2)"
suma igual que "SUMA(C2:C4)"). Cada celda del rango pasa por
`valor_celda` con el mismo `_visitando` de la fórmula que la
contiene, así que una referencia circular adentro del rango (ej.
sumar un rango que se incluye a sí misma) se detecta igual que una
referencia circular suelta — sin código nuevo para eso, reutiliza el
mecanismo existente. Sigue siendo la ÚNICA función disponible —
"no fórmulas complejas" sigue siendo el criterio, esto es una
excepción puntual pedida explícitamente, no una apertura a sumar más
funciones sin que se pidan.

Tests nuevos en `tests/test_planilla_flotante.py`:
`test_valor_celda_suma_rango_de_una_columna`, `test_valor_celda_suma_
rango_rectangular` (bloque de varias filas Y columnas),
`test_valor_celda_suma_rango_con_mas_sigue_siendo_formula` (combinado
con el resto de la fórmula), `test_valor_celda_suma_rango_ignora_
celdas_sin_numero`, `test_valor_celda_suma_rango_con_esquinas_
invertidas`, `test_valor_celda_suma_rango_detecta_referencia_
circular`, `test_texto_resultado_celda_suma_rango`.

pyflakes limpio en `app/gui/widgets/planilla_flotante.py`,
`app/negocio/planilla_flotante.py` y los dos archivos de test
tocados. Suite conjunta de `tests/test_gui_widget_planilla_flotante.
py`/`tests/test_planilla_flotante.py`/`tests/test_main_window.py`:
128 passed (más el artefacto ya documentado de fin de proceso, sin
afectar el resultado de ningún test).
