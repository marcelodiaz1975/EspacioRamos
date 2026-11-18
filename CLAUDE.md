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

El título del campo Buscar es "Buscar" por default, pero se puede
personalizar por catálogo con `etiqueta_buscar` (ej. Profesionales:
"Buscar profesional") sin cambiar el criterio de filtrado en sí (sigue
siendo substring por cualquier columna visible, no restringido a
campos puntuales) — cada catálogo define el orden de sus propias
columnas según lo que tenga más sentido mostrar primero, no hay una
regla única (ver `docs/historial/profesionales.md` para el caso de
Profesionales, y la decisión sobre el nombrado de archivos de su
documentación).

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

## Foco: seleccionar todo el contenido al enfocar un campo prefijado (disponible para todo el sistema)

Pedido de la clienta al revisar `_DialogoAjustarSaldo` (Reinicio de
prueba): "que el importe esté seleccionado para empezar a escribir
encima y borrarlo a la vez, esto para todos los campos que requieran
texto a introducir por los usuarios... en todo el sistema". La regla de
Tab/Enter de más arriba (`instalar_enter_avanza_foco`) ya selecciona
todo al LLEGAR por Tab/Enter dentro de una cadena armada, pero no cubre
el foco automático que Qt le da al primer control enfocable de un
diálogo recién abierto (no es un evento de tecla, nunca dispara ese
filtro) — el caso real de `_DialogoAjustarSaldo`, que tiene un solo
campo editable.

`instalar_seleccionar_todo_al_enfocar(widget, parent=None)`
(`app/gui/widgets/foco.py`) es el mecanismo general: escucha
`FocusIn` en `widget` (por click, por Tab/Enter, o por `setFocus()`
llamado desde código) y selecciona todo su contenido con
`QTimer.singleShot(0, ...)` (un `selectAll()` inmediato queda pisado
por el reposicionamiento de cursor que hace Qt después de un click).
Sirve para cualquier widget con `.selectAll()` — `QLineEdit`,
`QDoubleSpinBox`/`QSpinBox`, `QDateEdit`, etc. Generalización del
mecanismo puntual que ya tenía `selector_profesional.py`
(`_SeleccionarTodoAlEnfocar`, sigue ahí sin tocar — cubre un caso propio
con dos widgets a escuchar) para que cualquier pantalla nueva lo use sin
duplicar la clase.

Aplicado por ahora solo en `_DialogoAjustarSaldo.spin_saldo` (Reinicio
de prueba) — queda disponible para sumarlo al resto de los formularios
del sistema caso por caso, mismo criterio que el resto de los cambios
de alcance general (no un barrido completo de una sola vez).

## F5 ("Refrescar"): reinicia desde cero, distinto de `showEvent`

Regla general confirmada en una auditoría completa de los ~24 métodos
`reiniciar()` del sistema (detalle pantalla por pantalla en
`docs/historial/general.md`): este atajo y `showEvent` son disparadores
DISTINTOS. Volver a entrar a una solapa (`showEvent`) no tiene por qué
perder un filtro que el operador ya eligió (ej. qué profesional estaba
mirando); el atajo sí es un pedido explícito de "empezar de cero" —
todos los filtros a su valor inicial y el foco al principio de la
cadena. Toda pantalla nueva con estado propio (filtros, selección) tiene
que mantener esta separación al armar su propio `reiniciar()`, no
mezclarlo con `showEvent`.

Pedido de la clienta (hilo "saldo actual"/atajos de teclado): la tecla
se corrió de F3 a F5 — "más asociado al refrescar que usan los
navegadores" — para dejar F3 libre como salto directo a una solapa (ver
abajo). El método (`VentanaPrincipal._reiniciar_solapa_activa`, que a su
vez llama a `reiniciar()` del panel más interno vía `_panel_mas_interno`)
no cambió, solo la tecla del `QShortcut`.

## F1-F12: leyenda completa de atajos, salto directo a una solapa

Pedido explícito de la clienta: además de F1 (Ayuda, `_mostrar_ayuda`),
F2 (Calculadora, `_abrir_calculadora`) y F5 (Refrescar, ver arriba), el
resto de las F quedan como atajo directo a una solapa puntual del
sistema — no la pantalla, la SOLAPA, en pantallas compuestas con varias:

- F3: Regulares (solapa "Reservas regulares" de la Seccion "Reservas")
- F4: Aisladas (solapa "Reservas aisladas" de "Reservas")
- F6: Grilla (solapa "Grilla semanal" de "Grilla y mensajería")
- F7: Mensajería (solapa "Centro de mensajería" de "Grilla y mensajería")
- F8: Predefinidos (solapa "Mensajes predefinidos" de "Grilla y mensajería")
- F9: Oferta (solapa "Oferta de consultorios" de "Disponibilidad")
- F10: Profesionales (solapa "Listado de profesionales" de "Profesionales")
- F11: Pagos (solapa "Registrar pagos" de la Seccion "Pagos")
- F12: Panel de control (Seccion "Panel de control" — sin solapa puntual,
  "Panel de control" no es el texto de ninguna de sus dos solapas reales
  ("Avance de período..."/"Importación datos desde Excel"), así que
  `ir_a_solapa` no encuentra coincidencia y se queda solo con el salto a
  la Seccion, que es lo que pidió la clienta)

Implementado con `VentanaPrincipal.ir_a_solapa(nombre_seccion,
texto_solapa)` (`app/gui/main_window.py`), que reusa `ir_a_seccion` (#22,
ya existía para el salto de botón "Confirmar reserva" de Lista de
espera) y después busca con `findChild(QTabWidget)` la solapa de ese
texto dentro de la Seccion — todas las pantallas compuestas de este
sistema arman su `QTabWidget` en el atributo `pestanas`, así que el
método es genérico y no hace falta tocarlo si se agrega una Seccion
nueva con el mismo patrón. `self._etiqueta_funciones` (barra de estado,
costado izquierdo) muestra la leyenda completa de las 12 teclas en el
orden pedido por la clienta.

## Módulo extendido ME1: "Control de pagos" (ronda en curso, no cerrada)

Primera implementación del primero de los seis módulos extendidos
identificados en la especificación v1.0 (ver `Configuracion.
ModulosExtendidos`, ya existía como parámetro preparado pero sin nada
conectado — ver `docs/historial/sistema.md` para ese antecedente).
Pedido explícito de la clienta: control mes a mes de todo lo que hay
que abonar, sea del espacio o personal/familiar, con un solo lugar de
carga del que las demás pantallas levantan la información (no al
revés). Arrancado con el grueso del concepto ya definido, a iterar con
correcciones según lo que la clienta vaya encontrando en el uso real
(pedido explícito: "lo voy probando y las correcciones las hacemos por
lo que vaya encontrando con el sistema en sí" — no se espera que esta
primera vuelta quede perfecta).

### Modelo de datos

Dos niveles (`app/negocio/control_pagos.py`, tablas 3.35-3.37 de
`schema.sql`):
- `ConceptoControlPago`: el "maestro" recurrente (ej. "Edenor") — Nombre,
  Categoría (lista editable `CategoriaControlPagos`, las 13 que pasó la
  clienta), Afectación y Medio de pago sugerido.
- `InstanciaControlPago`: una fila por Concepto y Período — se genera en
  blanco (`generar_instancias_periodo`, llamada desde el `showEvent` de
  "Carga y control", idempotente) para cada concepto Activo que todavía
  no tenga una ese mes.

**Afectación** (pedido explícito: "la opción robusta", con referencias
reales, no texto suelto): no es una tabla aparte — `TipoAfectacion` +
hasta 5 columnas FK nullable directo en `ConceptoControlPago` (mismo
criterio que `GastoOperativo.Alcance`, `sanear_afectacion` limpia las
que no corresponden). Siete tipos: "Espacio general"/"Edificio"/"Unidad"
(referencias reales a las tablas de siempre del espacio — llega hasta
Unidad, no baja a Consultorio, mismo criterio que Gastos operativos) y
"Inmueble personal"/"Rodado"/"Persona" (catálogos nuevos y livianos,
`InmueblePersonal`/`Rodado`/`PersonaFamilia` — NO se reutilizó
`Responsable`, que es para contactos administrativos del negocio, otro
dominio) / "Familia" (sin catálogo, un único valor fijo).

**Sincronización con Balance del negocio** (pedido explícito: "lo que
cargo en módulo extendido pase al balance del negocio y no al revés"):
cada vez que cambia el Importe de una instancia imputada al Espacio
(Espacio general/Edificio/Unidad), `sincronizar_gasto_operativo` crea o
actualiza el `GastoOperativo` correspondiente con Origen="Importado" —
exactamente el mecanismo que ya estaba preparado para esto desde que se
armó Gastos operativos (ver `docs/historial/catalogos.md`: "esta tabla
se puede cargar tanto a mano como, a futuro, importada desde un módulo
extendido"). Si ya existe un gasto Manual en conflicto para el mismo
Período+Concepto, no se pisa (`gasto_en_conflicto`, regla ya existente).
Los conceptos personales/familiares/de rodados nunca tocan
`GastoOperativo`. Vaciar el Importe borra el gasto sincronizado.

### Decisiones confirmadas con la clienta antes de implementar

- Afectación con referencias reales (no texto libre) — ver arriba.
- No hace falta Consultorio como nivel de Afectación por ahora (se puede
  sumar después, mismo criterio que ya se usó para Gastos operativos).
- Un concepto nuevo puede arrancar directo en el mes en curso, no hace
  falta esperar al período siguiente.
- Además de "Editar" (vencimiento/monto de UN mes) y "Archivar"
  (cierra solo ese mes, el concepto sigue generándose), dos acciones
  más pedidas explícitamente: "Editar concepto seleccionado" (Nombre/
  Categoría/Afectación/Medio de pago sugerido del concepto en sí) y
  "Dar de baja concepto seleccionado" (para siempre — deja de generar
  instancias nuevas, el historial ya generado no se toca). Las dos
  viven como botones en el panel izquierdo (debajo de "Crear
  concepto"), no como botón por fila — "Dar de baja..." no entraba en
  la tabla sin angostar demasiado el resto de las columnas.

### Pantalla

`PantallaControlPagos` (`app/gui/pantallas/control_pagos.py`), cinco
solapas: "Carga y control" (formulario de alta a la izquierda — Nombre/
Categoría/Afectación/Medio de pago/Vencimiento/Importe/3 campos libres,
crea el concepto y, si se cargó algo, su primera instancia de una —
mismo criterio que el "Crear licencia" combinado de Novedades; tabla a
la derecha con los tres botones por fila: Editar/Marcar abonado/
Archivar, habilitados según Estado/si hay datos cargados), "Historial"
(filtros por Categoría/Concepto/Afectación/Medio de pago, "todos los
que se puedan poner" como pidió la clienta — mismo criterio "filtro que
solo afecta la visualización"), y los tres catálogos de Afectación
anidados (Inmuebles personales/Rodados/Personas, `PantallaCRUD`
genérica, sin código propio).

Solo aparece en el menú (`gui_main.construir_secciones`) con
`Configuracion.ModulosExtendidos` prendido — apagado (el default), ni
la Sección ni nada se ve, confirmando lo que ya estaba previsto para
ese parámetro. Prendido, pedido explícito de la clienta: categoría
PROPIA, tercera del menú ("Módulos extendidos", no mezclada con
"Parámetros del sistema" ni con la del espacio) — ahí van también los
que se sumen más adelante (ME2-ME6), no solo este.

### Bug real encontrado y arreglado en el camino

La migración que precarga las categorías/medios de pago en
`ListasEditables` (`app.db.migraciones._precargar_listas_control_
pagos`, para que lleguen también a una base YA en uso, no solo a una
nueva) corría dentro de `init_database`, ANTES de que quien llama
decida sembrar los valores por defecto — en una base recién creada
insertaba igual, dejando `ListasEditables` de estar vacía y haciendo
que `sembrar_listas_editables` (que solo siembra con la tabla ENTERA
vacía) se salteara TODOS los demás tipos (`CondicionFiscal`,
`MedioPago`, etc.), no solo los de este módulo. Arreglado agregando un
guard explícito: si `ListasEditables` está totalmente vacía (base
nueva, sin sembrar todavía), la migración no toca nada — esos dos
tipos ya están en `LISTAS_EDITABLES` de `seed.py`, así que una base
nueva los recibe por ese camino. Tests de regresión en
`tests/test_migraciones.py` (`test_base_nueva_siembra_listas_control_
pagos_via_seed_no_via_migracion` y dos más).

### Verificación de esta ronda

pyflakes limpio en los 9 archivos tocados/nuevos. Suite completa de
`test_control_pagos.py` (12, negocio), `test_gui_control_pagos.py` (11,
GUI), más `test_migraciones.py`/`test_gui_main.py`/`test_catalogos.py`/
`test_seed.py`/`test_main_window.py`/`test_pagos.py`/`test_gui_pagos.py`/
`test_balance.py`/`test_gui_balance.py`/`test_mensajes.py`/
`test_gui_mensajeria.py`/`test_gui_novedades.py`/
`test_gastos_operativos.py`: 660 passed. Verificado visualmente con
capturas offscreen de "Carga y control" e "Historial" (alta de
concepto, columnas de botones a su ancho real, Importe en blanco
cuando no se cargó nada — no "$ 0,00").

### Categoría propia en el menú

Pedido explícito de la clienta, ronda siguiente a la de arriba:
"Control de pagos" pasa a tener su PROPIA categoría en el menú lateral
("Módulos extendidos", tercera categoría, no mezclada con "Parámetros
del sistema" ni con la del espacio) — ahí van también los módulos
extendidos que se sumen más adelante (ME2-ME6), no solo este.

### Planilla de importación: cuatro hojas nuevas

Pedido explícito de la clienta, misma ronda: carga inicial de los
conceptos reales que ya tenía, vía la planilla de importación del
sistema (`app/importacion/`) — mismo criterio que `PlanPago` (una
excepción al alcance de la Etapa 1, que en general no importa entidades
que se cargan desde la propia pantalla: acá tiene sentido porque es
"lo que ya existía antes de empezar a usar el sistema", no algo que se
repita por planilla mes a mes).

Cuatro hojas nuevas (`definiciones.COLUMNAS_PLANTILLA`, en orden:
`InmueblePersonal`/`Rodado`/`PersonaFamilia` ANTES que
`ConceptoControlPago`, que las referencia): solo se importan los
CONCEPTOS (el maestro) — las instancias de cada período las genera
sola la pantalla al entrar, nunca por planilla. `ConceptoControlPago`
tiene columnas "Edificio"/"Unidad"/"InmueblePersonal"/"Rodado"/
"Persona" (una sola completa según "TipoAfectacion", validado contra
los siete valores exactos — `app.importacion.importar_excel._resolver_
referencias`, mismo patrón que el resto de las entidades con
referencia a otra ya cargada en la planilla).

Se le armó y mandó por acá (no es parte del repositorio) una copia YA
PRECARGADA con los ~60 conceptos reales que pasó la clienta (categoría,
afectación y medio de pago actual de cada uno, como los describió) —
confirmado que importa limpio contra una base de prueba. Los conceptos
imputados a una Unidad del espacio (28 de los 60: Edenor/AYSA/
Municipal/ARBA/Expensas/etc. de las cuatro unidades) quedaron con
"COMPLETAR (tu edificio real)" en la columna Edificio — el sistema no
tiene forma de adivinar el nombre real del edificio de cada unidad, así
que esas filas fallan la importación a propósito (mensaje de error
claro, señalando exactamente cuál) hasta que la clienta lo reemplace a
mano por el Edificio real antes de importar. Las dos Localidades
usadas para los inmuebles personales (San Justo/CABA) se precargaron
con datos geográficos reales (no inventados) — si ya existen en el
sistema con otros valores, sacar esas dos filas de la hoja Localidad
antes de importar, para no generar una duplicada (el chequeo de
duplicados compara la fila entera, no solo el nombre).

Tests nuevos en `tests/test_importacion.py` (7): los siete
TipoAfectacion resolviendo correctamente, error con tipo inválido,
error con Edificio/Unidad inexistente, error con Inmueble personal
inexistente, error de Localidad inexistente (hoja InmueblePersonal), y
que un concepto duplicado no se vuelve a crear. Suite completa de
`test_importacion.py`: 42 passed.

### Pendiente (no bloquea cerrar esta ronda)

Nada más del resto de los módulos extendidos (ME2-ME6) — fuera de
alcance de esta ronda, se planifican recién al iniciar esa etapa.

## Indicador "Procesando..." para operaciones largas

Mecanismo compartido (`Procesando`, `app/gui/widgets/procesando.py` —
origen y caso real en `docs/historial/sistema.md`) para cualquier loop
sincrónico largo (ej. emitir todas las liquidaciones): `with
Procesando(self, "texto..."):` alrededor del loop, llamando a
`procesando.tick()` en cada vuelta — fuerza `QApplication.
processEvents()`, necesario porque Qt es de un solo hilo y si no el
cartel ni el resto de la ventana se repintarían hasta que el loop
termine. Se suma caso por caso a cualquier otro loop largo del sistema
que lo necesite (no es una instalación global).

## Metodología de trabajo

Revisión "uno por uno", pantalla por pantalla, con la clienta. Un cambio
de estilo se prueba primero en la pantalla que se está revisando; si lo
aprueba y es de alcance general, se sube a `estilos.py` para que aplique
a todas las que ya usan ese objectName (no hace falta retocar cada
pantalla). A veces se prueba algo y se desestima (ej. gris en los
botones) — en ese caso se revierte al valor anterior, no queda a mitad
de camino. Después de cada ronda: pyflakes limpio, suite completa sin
regresiones nuevas (ver más abajo los fallos preexistentes conocidos,
del entorno y no de la app), captura de pantalla con Qt offscreen/xvfb
para verificar visualmente antes de dar la pantalla por cerrada.

Las capturas que se le envían a la clienta se nombran
"{Sección} - {Formulario} - {Solapa}.png" (pedido explícito de la
clienta, para no tener que renombrarlas ella a mano) — ej. "Sistema -
Panel de control - Avance de período, backup, y vista rápida.png". Sección es
"Sistema"/"Operativa diaria" (las dos categorías del menú), Formulario
el nombre del `Seccion` del menú, Solapa el texto de la pestaña
mostrada (si la pantalla no tiene solapas, se omite esa tercera parte).

**Fallos conocidos, del sandbox/contenedor y no de la app:** hasta 10
tests pueden aparecer en rojo en este entorno sin ser una regresión
real — 7 por una particularidad de fuentes de este contenedor
(fontconfig/Carlito, calibración pixel a pixel de Reservas/Lista de
espera/Profesionales/Oferta/Placas) y 3 de `test_avance_mes.py` por el
reloj real del sandbox (dependencia de en qué mes real se corre la
suite). Investigación completa, lista exacta de los 10 nombres y por
qué no se tocan en `docs/historial/general.md` ("Fallos del
sandbox/contenedor, ajenos a la app"). Si reaparecen, no bloquean
cerrar una ronda.

## Ronda de pedidos sueltos (en curso)

Cuatro pedidos de la clienta en un mismo mensaje, sobre pantallas
distintas — se van resolviendo uno por uno, no todos juntos.

- **Reservas aisladas: foco vuelve al selector de Profesional tras un
  proceso exitoso.** Hecho. `_eliminar` ya lo hacía; se sumó el mismo
  `self.combo_profesional.setFocus()` al final de `_resetear_formulario`
  (cubre "Crear reserva aislada", su único llamador) y al final de
  `_modificar_seleccionada` (no pasa por `_resetear_formulario`, edita
  la fila existente sin tocar el resto del formulario). Tests nuevos en
  `tests/test_gui_reservas.py`:
  `test_crear_reserva_aislada_devuelve_el_foco_al_selector_de_profesional`,
  `test_modificar_reserva_aislada_devuelve_el_foco_al_selector_de_profesional`.
- **Placas: botón "Posiciones que se podrían liberar".** Hecho. Nuevo
  botón `checkable` (`boton_filtro_liberables`, mismo ancho/alto que
  Asignar/Reasignar/Liberar) en "Búsqueda y asignación de placas" —
  mismo criterio que "Filtros que solo afectan la visualización": se
  combina con Profesional/Localidad/Edificio/Unidad, nunca los
  reemplaza. El criterio de "candidata" es por categoría del
  profesional que ocupa la posición (`app.negocio.placas.
  placa_se_podria_liberar`, nueva función), tal cual lo pidió la
  clienta:
  - R: sin `ReservaRegular` vigente HOY en la unidad de la placa (otra
    unidad del espacio no cuenta).
  - X: siempre candidata.
  - E: no tiene reservas regulares propias (ver `crear_reserva_
    regular`, solo R/B) — se mira si su Cabeza de equipo (R) tiene
    `ReservaRegular` vigente hoy en esa unidad; sin cabeza cargado,
    candidata.
  - A: hace más de un año sin ninguna `ReservaAislada` Confirmada en
    TODO el espacio (pedido explícito: "no en la unidad solamente") —
    mismo cálculo de "un año atrás" que `app.negocio.avance_mes.
    _limite_retencion_activos` (29 de febrero sin bisiesto equivalente
    recorta al 28).
  - B y cualquier otra categoría, o posición sin profesional asignado:
    nunca candidata (la clienta no dio un criterio para B).
  Tests nuevos: 14 en `tests/test_placas.py` (uno por caso de
  categoría/borde) + 2 en `tests/test_gui_placas.py` (acota la tabla,
  se combina con el resto de los filtros) + 1 ampliado
  (`test_etiquetas_y_tamano_de_los_botones_de_buscar_y_asignar`, suma
  el nuevo botón a la comparación de ancho/alto).

  Ronda siguiente, pedido explícito de la clienta: el filtro también
  tiene que mostrar las posiciones LIBRES del tablero (sin profesional
  asignado), no solo las ocupadas que califican por categoría — una
  foto completa de qué lugar hay disponible. `unidades_en_alcance`
  (nueva, `app.negocio.placas`) replica el mismo alcance de filtros
  Localidad/Edificio/Unidad que `listar_placas`, pero consultando
  `Unidad` directo (no `Placa`), así que también alcanza unidades sin
  ninguna placa — de ahí, `posiciones_libres` por unidad. Las
  posiciones libres NUNCA se acotan por el filtro de Profesional (una
  posición libre no es de nadie) y se muestran como diccionarios
  "placa" livianos con `IdPlaca=None` — `_DialogoPlaca`/`_reasignar` ya
  saben leer un `placa_existente` sin profesional actual (mismo caso
  que una placa vieja sin dueño), así que seleccionar una fila libre y
  tocar "Reasignar..." la asigna de una, sin código extra. "Liberar" (y
  la tecla Delete, que llama a `_liberar` directo sin mirar si el botón
  está habilitado) queda deshabilitado/no hace nada para esas filas —
  nada que liberar. Tests nuevos en `tests/test_gui_placas.py`:
  `test_boton_filtro_liberables_muestra_tambien_las_posiciones_libres`,
  `test_posicion_libre_seleccionada_deshabilita_liberar_pero_no_
  reasignar`, `test_tecla_delete_sobre_posicion_libre_no_hace_nada`,
  `test_reasignar_una_posicion_libre_la_asigna` — más los dos tests
  existentes de esta misma ronda, ajustados a tableros de tamaño fijo
  (antes usaban el default de 10 posiciones, que ahora sí aparecen
  todas como libres y rompían el conteo esperado).
- **Reservas regulares: la grilla/vista previa no reflejaba una reserva
  nueva cargada a mitad de mes.** Hecho — bug real, confirmado y
  arreglado. La clienta aclaró que se refería a la grilla/vista previa
  DENTRO de la propia solapa de Reservas regulares (`self.grilla`,
  `GrillaOperativaWidget` en modo "regular"), no a "Grilla semanal".
  Reproducido: una `ReservaRegular` con `VigenciaInicio` posterior a
  hoy pero dentro del mismo mes visualizado (ej. parada el 16/11,
  reserva con vigencia desde el 20/11) queda clasificada como
  "entrante" (`_clasificar_regulares`, `app.negocio.grilla_
  operativa`) — nadie la ocupa "hoy" todavía (`actual is None`). El
  bug real: `_resolver_regular` armaba `id_mostrado` (campo interno,
  nunca se pinta — ver `CeldaGrillaOperativa`) a partir de `actual`
  en TODA la función, nunca a partir de `entrante`; en la rama
  "entrante", `id_mostrado` quedaba en `None` (o en el del titular
  actual si había conflicto, nunca el del entrante). El filtro
  exclusivo por profesional que usa justo esta vista previa
  (`GrillaOperativaWidget._actualizar_grilla`, `_filtro_exclusivo_
  profesional`) compara `celda.id_profesional_mostrado ==
  id_profesional_filtro` y pisa a `_CELDA_VACIA` lo que no coincide —
  así que la reserva recién cargada (filtrada por ESE mismo
  profesional, que es lo que hace siempre esta vista previa)
  desaparecía por completo de la grilla en vez de mostrarse en rojo
  como "entrante". Arreglado en `_resolver_regular` (rama `entrante`):
  `id_mostrado` pasa a tomarse siempre de `entrante`, no de `actual` —
  `codigo`/`base` (lo que se PINTA en la celda) no cambian, eso sigue
  siendo una decisión de diseño aparte ya probada (en blanco si nadie
  la ocupa hoy, el código del titular actual si hay conflicto). Tests
  nuevos: `tests/test_grilla_operativa.py`
  (`test_regular_entrante_sin_titular_actual_queda_identificado_para_
  el_filtro_exclusivo`, `test_regular_conflicto_el_entrante_tambien_
  queda_identificado_para_el_filtro_exclusivo`) y
  `tests/test_gui_reservas.py`
  (`test_grilla_preview_se_refresca_al_crear_una_reserva_que_arranca_
  a_mitad_de_mes`, reproduce el reporte textual de la clienta de punta
  a punta vía `_PanelReservasRegulares._crear`).
- **Registrar pagos: saldo período actual mal para una profesional
  categoría R con liquidación de noviembre pendiente y una aislada ya
  agendada para diciembre.** Cerrado — no era un bug activo, era un
  resabio de un bug YA arreglado. Con el PDF real de la liquidación de
  noviembre de Lic. Aldana Portillo (R2) y el detalle exacto que la
  clienta pasó del pago, se reconstruyó que su `SaldoCuentaActual` de
  antes del pago ($220.530) era exactamente la suma de dos cosas: el
  total real de noviembre ($118.731, el de la última emisión
  "Enviada") más el `MontoGenerado` de una `LiquidacionEmitida` de
  **diciembre** ($101.799) que había quedado acreditada de más. Esa
  fila de diciembre (confirmado con la base real que mandó la clienta,
  vía `IdLiquidacion`/`FechaHoraGeneracion`) se generó el **27/10/2026
  a las 10:19hs** — TRES DÍAS ANTES del commit que agregó el guard
  "no acreditar una liquidación-preview de un mes que el período
  operativo todavía no alcanzó" (30/10/2026, ya documentado arriba en
  este mismo archivo). O sea: se acreditó por un bug que en ese momento
  todavía existía en el código, antes de que arrancara esta ronda — el
  fix posterior no revierte datos que ya habían quedado mal, solo
  evita que vuelva a pasar de ahí en adelante. Confirmado buscando en
  toda la base si había otro caso igual: solo una fila más de un
  período futuro en todo el sistema (Lic. Valeria Sambucari, R100,
  también diciembre) — pero esa se generó el 4/11, YA con el fix
  puesto, y no acreditó nada (su saldo coincide exacto con su última
  liquidación de noviembre) — confirma que el fix funciona bien hoy.
  Corrección aplicada por la clienta a mano en Profesionales > Editar
  (`SaldoCuentaActual`, el único lugar editable de ese campo — `Campo
  tipo="numero"` en `app.gui.pantallas.profesionales`), sin tocar
  código. No hace falta ningún barrido del resto de los profesionales:
  los demás saldos altos que aparecían en la base real que mandó la
  clienta son correctos (cada uno coincide con su última liquidación
  de noviembre).

- **Pagos: "Saldo anterior"/"Nuevo saldo" de la tabla de historial
  (Registrar pagos y Estado de cuenta) pasan a combinar los dos
  períodos.** Hecho. Pedido explícito de la clienta, con el PDF real de
  la liquidación de noviembre de Lic. Gabriela Icutza (R16) como caso de
  prueba: notó que esas dos columnas, POR FILA, no "se relacionaban"
  entre sí al pasar de un pago a otro — porque cada una mostraba un solo
  campo (`SaldoCuentaAnterior` o `SaldoCuentaActual`, según a qué
  período se imputaba ESE pago puntual), mismo problema que ya se había
  corregido una vez para las etiquetas de arriba del formulario ("Saldo
  total"/"Nuevo saldo", ver el comentario en `_armar_ui` de
  `_PanelPagos`) pero nunca se había llevado a las columnas de la tabla.
  Renombradas a "Saldo antes del pago"/"Saldo después del pago", ahora
  muestran el COMBINADO (`SaldoCuentaAnterior + SaldoCuentaActual`)
  antes/después de cada movimiento — comprobado matemáticamente en
  `_aplicar_pago_con_cascada` que el combinado SIEMPRE cambia en
  exactamente `monto`, reparta como reparta la cascada entre los dos
  campos, así que no hace falta ningún caso especial. El encadenado que
  pidió la clienta ("si hay un nuevo pago en el mes, 'antes' muestra el
  último 'después' de ese mes") sale solo de leer los dos campos en vivo
  en cada registro — no hubo que programar ningún encadenamiento manual,
  y de paso queda más fiel a la realidad si en el medio se emite una
  liquidación nueva (la seguiría reflejando, cosa que un encadenado a
  ciegas no haría). Tocados los tres lugares que escriben esas columnas
  en `app/negocio/pagos.py` (`registrar_pago`, `modificar_pago`,
  `reconciliar_saldos_cruzados`) — el cruce de tolerancia de
  `registrar_pago` (DC-06 §5.2) sigue mirando el campo puntual, no el
  combinado, por ser una decisión de negocio distinta. Sin migración:
  las columnas de `HistorialPagos` se siguen llamando igual
  (`SaldoAnterior`/`SaldoNuevo`), solo cambia qué calculan y cómo se
  llaman en pantalla — confirmado que son los ÚNICOS dos lugares de la
  GUI que las leen (la tabla de "Registrar pagos" y la de "Estado de
  cuenta"; la etiqueta "Nuevo saldo" del panel de arriba es una cosa
  distinta, la vista previa en vivo de un pago que todavía no se
  registró, y no se tocó). Tests nuevos en `tests/test_pagos.py`:
  `test_registrar_pago_saldo_antes_y_despues_combina_los_dos_periodos`
  (reproduce el caso real de Gabriela Icutza), `test_registrar_pago_
  saldo_antes_del_pago_encadena_con_el_despues_del_pago_anterior`,
  `test_registrar_pago_con_cascada_tambien_combina_correctamente`,
  `test_modificar_pago_saldo_antes_y_despues_combina_los_dos_periodos`
  — más una aserción nueva en un test ya existente de
  `reconciliar_saldos_cruzados` (el combinado no cambia, es un reparto
  interno sin plata real de por medio). pyflakes limpio, suite completa
  de Pagos sin regresiones (162 tests) y sin regresiones en Mensajes/
  Balance/Avance de mes (los mismos 3 fallos conocidos del reloj del
  sandbox).

- **Ausencias por motivos varios: alerta de proceso exitoso al crear.**
  Hecho. Punto #9.1.9 — faltaba, `_PanelAusencias._crear`
  (`app/gui/pantallas/novedades.py`) no mostraba nada al completar el
  registro (a diferencia de Vacaciones/Licencias, que sí avisan pero
  solo cuando hay advertencias de por medio). Se sumó `QMessageBox.
  information(..., "Ausencia cargada con éxito.")`, incondicional, al
  final de `_crear`. Test nuevo:
  `test_crear_ausencia_muestra_alerta_final_de_exito`.
- **Cargos especiales: Ajuste/Bonificación con el signo al revés +
  alerta de éxito.** Hecho. Pedido explícito de la clienta: "el
  subtipo ajuste obliga a un débito (importe positivo) en contra del
  profesional, y el subtipo bonificación obliga a un crédito a favor
  del profesional (importe negativo)" — invierte el pedido original
  (`_actualizar_tipo_segun_subtipo`, que tenía Bonificación bloqueada
  en Débito y Ajuste editable por defecto en Crédito). Aclaración de
  la clienta sobre el motivo de la confusión: el resto del sistema
  mira Débito/Crédito desde la óptica del espacio, pero acá tiene más
  sentido mirarlo desde el impacto en la cuenta del PROFESIONAL.
  Arreglado invirtiendo literalmente los roles de los dos subtipos en
  `_actualizar_tipo_segun_subtipo` (ahora Ajuste es el bloqueado en
  Débito, Bonificación el editable por defecto en Crédito — Ítem libre
  no cambia) y en el único otro lugar que distinguía el subtipo
  bloqueado (`_modificar_seleccionada`, precarga del Tipo real
  guardado). `crear_cargo_especial` (`app/negocio/pagos.py`) no se
  tocó — nunca acopló Subtipo a Tipo, solo valida que el signo del
  monto sea consistente con el Tipo elegido, sin importar el Subtipo.
  De paso, mismo pedido que Ausencias: alerta final de éxito al cargar
  el registro (faltaba, igual que en esa otra solapa). Tests
  actualizados/nuevos en `tests/test_gui_novedades.py`:
  `test_subtipo_ajuste_fuerza_tipo_debito_y_lo_bloquea` (antes era
  sobre Bonificación), `test_subtipo_bonificacion_deja_tipo_editable_
  por_defecto_credito` (antes era sobre Ajuste),
  `test_modificar_cargo_especial_sin_llave_precarga_el_subtipo`
  (monto pasa a positivo, ya que ahora prueba Ajuste bloqueado en
  Débito), `test_crear_cargo_especial_muestra_alerta_final_de_exito`
  (nuevo).

- **Control de pagos (ME1): rediseño completo de "Carga y control".**
  Hecho. Pedido explícito de la clienta, 17 puntos en un mismo mensaje
  sobre esta sola solapa. Dos ambigüedades consultadas antes de
  empezar (`AskUserQuestion`): la idea de "tres columnas arriba" la
  retiró ella misma ("me olvidé de borrarlo, era una idea y luego me
  arrepentí") — queda solo "que el primer elemento arranque en el
  pixel 85, y de ahí baje el resto", mismo mecanismo de siempre (ver
  "Jerarquía de títulos" más arriba), sin coordinar con una segunda
  columna porque acá no la hay. Y "Duplicar para período próximo"
  confirmado en blanco (solo Medio de pago, igual que un concepto
  nuevo) — nunca copia Vencimiento/Importe de la fila de origen.

  - **Avance de mes archiva lo no abonado.** `app.negocio.control_
    pagos.archivar_pendientes_del_periodo(conn, periodo)` (nueva):
    archiva TODA instancia Pendiente de `periodo`, tenga o no datos
    cargados — a diferencia de `archivar_instancia` (el botón manual
    de una fila, que sigue exigiendo vencimiento/importe vacíos, sin
    tocar). Se puede reabrir después desde "Historial" con "Editar
    registro". Llamada desde `avance_mes.avanzar_mes` (nuevo campo
    `ResumenAvanceMes.instancias_control_pagos_archivadas`), junto a
    la limpieza de fechas especiales del período cerrado.
  - **Columna "Período" (yyyy-mm) después de "Medio de pago".** La
    tabla de "Carga y control" ahora muestra a la vez las instancias
    del período actual Y las del período próximo (si se duplicó
    alguna, ver abajo) — sin esta columna no se podrían distinguir.
  - **Pixel 85 + achique del 15% del panel del formulario.**
    `_ALTO_TITULO_CARGA_CONTROL = 7` (mismo valor medido que Reservas
    regulares/aisladas y los paneles de Novedades — confirmado
    programáticamente offscreen: con ese valor, el primer elemento
    queda al mismo píxel relativo, ±1px, que la referencia aprobada).
    `_ANCHO_PANEL_CARGA_CONTROL`/`_ANCHO_CAMPO_CARGA_CONTROL` son
    `_ANCHO_PANEL_IZQUIERDA`/`_ANCHO_CAMPO` al 85% (238px/204px) —
    constantes propias de esta pantalla, no se tocó el panel de
    filtros de "Historial" (comparte las constantes genéricas, pero
    no estaba pedido achicarlo). Verificado con captura offscreen que
    ningún botón queda con el texto cortado al nuevo ancho.
  - **Campos libres fuera de la UI.** Las tres `QLineEdit` y la
    lectura/escritura de `CampoLibre1/2/3` en `_crear` se sacaron del
    todo de este archivo — las columnas siguen en el schema, sin uso.
  - **Botones reordenados y nuevos, todos habilitados solo con
    selección.** Orden final de la columna 1: Nombre/Categoría/
    Afectación/Medio de pago/Vencimiento/Importe, "Crear concepto"
    (subido al lugar que dejaron los campos libres, sin la línea
    divisoria que había antes), "Editar concepto seleccionado", "Dar
    de baja concepto seleccionado", "Duplicar para período próximo"
    (nuevo), "Eliminar registro duplicado" (nuevo), línea divisoria,
    "Editar registro"/"Marcar abonado"/"Archivar registro" (bajados
    acá desde el final de cada fila de la tabla — ya no hay
    `cellWidget` por fila). `_actualizar_botones_seleccion` centraliza
    el habilitado: todos requieren una fila seleccionada, y además
    "Duplicar..." solo sobre una fila del período ACTUAL, "Eliminar
    registro duplicado" solo sobre una del período PRÓXIMO (pedido
    explícito: "solo se pueden duplicar registros para el período
    próximo nada más"), "Marcar abonado"/"Archivar registro" con la
    misma condición de Estado/datos cargados que ya tenían como botón
    de fila. `app.negocio.control_pagos.duplicar_para_periodo_
    proximo`/`eliminar_instancia_duplicada` (nuevas) — la segunda
    también borra el `GastoOperativo` sincronizado si lo había, mismo
    criterio que vaciar un Importe.
  - **Ancho de tabla repartido.** Al sacar las tres columnas de botón,
    el `Stretch` que ya tenían Nombre/Categoría/Afectación/Medio de
    pago absorbe todo el ancho liberado solo — no hizo falta ningún
    cálculo manual. Período/Vencimiento/Importe/Estado quedan en
    `ResizeToContents`.
  - **Colores de fila por vencimiento + gris para lo resuelto.**
    `_PanelCargaControl._color_fila`: gris (`COLOR_GRIS`, nueva
    constante en `estilos.py`, mismo hex que `mensajeria._COLOR_
    FONDO["gris"]`) para Abonado/Archivado sin mirar el vencimiento;
    si Pendiente, violeta (`COLOR_VIOLETA`, nueva constante, mismo
    criterio) si ya venció, rojo si vence hoy, amarillo si vence
    mañana, verde si faltan 2 días o más, blanco si no tiene
    vencimiento cargado. Letra blanca salvo sobre amarillo (letra
    negra) — mismo criterio exacto que Centro de mensajería.
  - **Orden de filas en tres grupos.** `_clave_orden_instancia`:
    arriba las Pendientes sin vencimiento O sin importe (por Nombre,
    Afectación); en el medio las Pendientes con ambos datos (por
    Período más próximo, Vencimiento, Nombre, Afectación); al fondo,
    en gris, las Abonadas/Archivadas — "parecido a lo que se hace con
    el centro de mensajería".
  - **Alertas de éxito en cada acción** (crear/editar concepto, dar de
    baja, duplicar, eliminar duplicado, editar/marcar abonado/archivar
    registro) — antes varias de estas acciones no avisaban nada.
  - **F5 reinicia la solapa.** `_PanelCargaControl.reiniciar()`
    (nuevo): resetea el formulario (a diferencia de `showEvent`, que
    no lo toca), limpia la selección de la tabla, refresca y devuelve
    el foco a "Nombre" — mismo criterio general documentado más arriba
    ("F5... reinicia desde cero, distinto de showEvent").
  - **"Editar registro" en "Historial".** Botón nuevo debajo de los
    cuatro filtros, habilitado solo con una fila seleccionada; abre
    `_DialogoEditarInstancia(..., incluir_estado=True)` — mismo diálogo
    que ya existía, con un combo de Estado sumado solo para este caso
    (la "Editar registro" de "Carga y control" no lo necesita, ahí
    "Marcar abonado"/"Archivar registro" están aparte). `app.negocio.
    control_pagos.actualizar_instancia` suma el parámetro `estado`
    (mismo patrón `_SIN_CAMBIOS` que ya tenía para vencimiento/importe/
    medio de pago), validado contra `ESTADOS_INSTANCIA`.

  Verificado con captura offscreen (`Carga y control` con filas en
  cada color/bucket, incluida una duplicada para el período próximo, y
  `Historial` con "Editar registro" habilitado) y con el mismo script
  de medición programática usado para confirmar el pixel 85 contra
  Reservas regulares como referencia. Tests nuevos: 8 en
  `tests/test_control_pagos.py` (archivar_pendientes_del_periodo,
  duplicar_para_periodo_proximo ×2, eliminar_instancia_duplicada,
  actualizar_instancia con estado ×2), 1 en `tests/test_avance_mes.py`,
  8 en `tests/test_gui_control_pagos.py` (columna Período, botones sin
  selección, duplicar/eliminar duplicado, gris al fondo, los cuatro
  colores de vencimiento, reiniciar, Editar registro de Historial) —
  más 3 tests existentes ajustados a la nueva API (los botones de fila
  pasaron a vivir en la columna 1). pyflakes limpio en los 4 archivos
  tocados. Suite completa sin regresiones nuevas (los mismos ~10
  fallos conocidos del sandbox, ver más abajo).

  **Ronda siguiente, tres ajustes de layout sobre esta misma solapa:**

  - **"Período actual" en una sola línea, el valor en negrita.** Pasa
    de dos widgets (`_titulo_campo` + `QLabel`) a uno solo:
    `self.etiqueta_periodo.setText(f"Período actual: <b>{periodo}</b>")`
    — `QLabel` detecta el HTML solo (`Qt.AutoText`, sin `setTextFormat`
    explícito, mismo criterio que `_fmt_saldo_label` en `pagos.py`). Al
    sacar un renglón, todo lo de abajo sube solo (es la misma
    `QVBoxLayout`, no hace falta tocar nada más) y la columna deja de
    necesitar scroll vertical para llegar a "Archivar registro".
  - **Ancho de columna 1 recalculado desde el texto real, no desde un
    85% arbitrario.** El 15% de achique de la ronda anterior dejaba el
    botón "Dar de baja concepto seleccionado" en 204px cuando su
    `sizeHint()` real (medido con `QFontMetrics` contra la hoja de
    estilos real) es 239px — se cortaba. `_ANCHO_CAMPO_CARGA_CONTROL`
    pasa a 240 (el que ya tenía el resto del sistema, antes de esta
    pantalla) y `_ANCHO_PANEL_CARGA_CONTROL` a 262. El ancho que gana
    el panel (262 contra los 238 que tenía) se le resta a la columna
    "Medio de pago" de la tabla (pedido explícito, no a Nombre/
    Categoría/Afectación): sale del `Stretch` a `Interactive` con un
    ancho fijo (`_ANCHO_MEDIO_PAGO_CARGA_CONTROL`, medido contra su
    ancho real bajo Stretch menos lo que gana la columna 1) — Nombre/
    Categoría/Afectación siguen en Stretch sin cambios, la cuenta
    cierra sola (lo que pierde una columna es exactamente lo que gana
    la otra, verificado con captura y medición programática).
  - **10% de "Categoría" pasa a "Importe".** Mismo mecanismo que
    "Medio de pago": las dos salen de Stretch/`ResizeToContents` a un
    ancho fijo propio (`_ANCHO_CATEGORIA_CARGA_CONTROL`/`_ANCHO_
    IMPORTE_CARGA_CONTROL`), medidos contra sus anchos reales con datos
    cargados — Nombre/Afectación no se tocan.

  Verificado con captura offscreen y medición programática de cada
  columna antes/después (`tabla.columnWidth`) confirmando que Nombre/
  Afectación quedan exactamente iguales. Tests nuevos en `tests/test_
  gui_control_pagos.py`: `test_etiqueta_periodo_actual_en_una_sola_
  linea_con_el_periodo_en_negrita`, `test_columna_1_entra_el_boton_
  dar_de_baja_sin_cortar`, `test_anchos_de_columna_categoria_medio_
  pago_e_importe_se_ajustan_sin_tocar_nombre_ni_afectacion`. pyflakes
  limpio, resto de la suite de control de pagos sin regresiones (57
  tests).

  **Ronda siguiente, dos pedidos más sobre esta misma tabla:**

  - **Ordenable por click en el encabezado.** `self._orden = OrdenTabla
    (self.tabla, self.actualizar)` (mismo mecanismo que ya usan las
    tablas de Pagos, `app/gui/widgets/orden_tabla.py`): un click ordena
    por esa columna, otro click invierte el sentido. El orden por
    defecto (los tres grupos de `_clave_orden_instancia`) se sigue
    aplicando siempre primero; si hay una columna elegida por click, se
    aplica ENCIMA (`_clave_orden_columna`, sort estable). `reiniciar()`
    (F5) llama a `self._orden.reiniciar()`, mismo criterio que el resto
    del sistema.
  - **Fila de filtros por columna arriba de la tabla.** Un `QLineEdit`
    por columna de Nombre a Vencimiento incluido (texto libre, sin
    distinguir mayúsculas ni acentos — mismo criterio que "Buscar" de
    los catálogos genéricos) y, sobre Importe/Estado, un botón
    "Reiniciar filtros" en vez de más filtros. Es un widget PROPIO (una
    fila en su propio `QHBoxLayout`, arriba de la tabla dentro de un
    `QVBoxLayout` compartido) y no una fila de la `QTableWidget` en sí —
    así no hace falta pelear con la selección ni con el orden por click
    de la tabla. El ancho de cada campo se sincroniza con el de su
    columna real (`_sincronizar_ancho_filtros`, incluido un espaciador
    al ancho del encabezado vertical de filas para que el primer campo
    arranque justo donde arranca "Nombre") — se llama al armar la
    pantalla, en cada `actualizar()` (las columnas en `ResizeToContents`
    pueden cambiar de ancho con los datos) y cada vez que el usuario
    redimensiona una columna (`header.sectionResized`); verificado con
    captura y medición programática que la sincronización también
    sobrevive a un resize de ventana completo. El filtrado se aplica
    sobre la lista de Python ANTES de ordenar y poblar la tabla (mismo
    criterio que ya usa "Historial" con sus combos) — F5 y "Reiniciar
    filtros" limpian los seis campos por igual.

  Tests nuevos en `tests/test_gui_control_pagos.py`:
  `test_click_en_encabezado_ordena_por_esa_columna_y_el_segundo_click_
  invierte`, `test_f5_reiniciar_vuelve_al_orden_por_defecto`,
  `test_filtros_por_columna_acotan_la_tabla_sin_distinguir_acentos_ni_
  mayusculas`, `test_filtros_por_columna_se_combinan_entre_si`,
  `test_boton_reiniciar_filtros_los_vuelve_a_su_estado_natural`,
  `test_f5_reiniciar_tambien_limpia_los_filtros_por_columna`,
  `test_anchos_de_filtros_quedan_sincronizados_con_las_columnas_
  reales`. pyflakes limpio, suite completa de Control de pagos/Pagos/
  Avance de mes sin regresiones nuevas (238 passed, los mismos 3
  fallos conocidos del reloj del sandbox).

- **General: confirmar salida con botones en español.** Hecho. La
  clienta notó que el cartel de "¿Seguro que querés salir?" (ya
  agregado en una ronda anterior, ver #31 en la lista de tareas) seguía
  mostrando "Yes"/"No" en inglés en vez de "Sí"/"No" — Qt no trae
  traducidas sus propias traducciones de botones estándar en este
  entorno. `VentanaPrincipal.closeEvent` pasa a usar `preguntar_si_no`
  (`app/gui/dialogos.py`, ya existía para "Restablecer descuentos" en
  Pagos — construye el `QMessageBox` a mano con botones "Sí"/"No"
  propios vía `addButton(..., ButtonRole.YesRole/NoRole)`, sin depender
  de ninguna traducción de Qt) en vez de `QMessageBox.question(...,
  StandardButton.Yes | StandardButton.No)`. Test nuevo en
  `tests/test_main_window.py`:
  `test_cerrar_con_la_cruz_usa_botones_en_espanol_no_yes_no`.

- **Profesionales: fila "Saldo total" combinado en Editar/Nuevo.**
  Hecho. Mismo criterio ya aplicado en Pagos (ver "Saldo previo"/
  "Nuevo saldo" más abajo): en el diálogo de alta/edición de un
  profesional, `SaldoCuentaAnterior` y `SaldoCuentaActual` siguen
  siendo dos campos EDITABLES por separado (no se tocó su mecánica:
  siguen siendo dos columnas reales de la base, cada una con su propio
  ciclo de pago/traspaso de mes — ver `avance_mes._traspasar_saldos`),
  pero se les agrega abajo una tercera fila de solo lectura, "Saldo
  total" (`_al_abrir_dialogo`, `app/gui/pantallas/profesionales.py`),
  que muestra la suma de los dos en vivo (se actualiza con cada
  `textChanged`/`valueChanged` de los dos campos editables) — para que
  se pueda ver de un vistazo "lo que me debe en total" sin tener que
  sumar a mano. Test nuevo en `tests/test_profesionales.py`:
  `test_dialogo_muestra_saldo_total_combinado_y_se_actualiza_en_vivo`.

- **Pagos: las columnas de saldo se renombran a "Saldo previo"/"Nuevo
  saldo".** Hecho. Pedido explícito de la clienta, "para simplificar",
  sobre las dos columnas de la tabla de "Registrar pagos"/"Estado de
  cuenta" que una ronda anterior había renombrado a "Saldo antes del
  pago"/"Saldo después del pago" (ver más abajo en el historial de esta
  misma sección) — el CÁLCULO combinado (`SaldoCuentaAnterior +
  SaldoCuentaActual` antes/después de cada pago) no cambia, es
  exactamente el mismo, solo cambia la etiqueta en las dos tablas
  (`_PanelPagos`/`_PanelEstadoCuentaPagos`, `app/gui/pantallas/
  pagos.py`). La etiqueta "Nuevo saldo" que ya existía ARRIBA del
  formulario (la vista previa en vivo de un pago todavía no
  registrado, `etiqueta_nuevo_saldo`) es una cosa aparte, de una ronda
  bastante anterior, y queda con el mismo texto — coincide de nombre
  con la columna nueva de la tabla pero son dos widgets sin relación,
  no hubo que tocar nada ahí.

  Se usó este mismo caso (Lic. Gabriela Icutza, $81.236 de saldo
  anterior + $277.292 de la liquidación de noviembre, pago de $70.000)
  para confirmar los números esperados: "Saldo previo" $358.528,
  "Nuevo saldo" $288.528 — coincide exacto con el cálculo COMBINADO ya
  implementado, sin tocar `registrar_pago`/`modificar_pago`/
  `reconciliar_saldos_cruzados` (`app/negocio/pagos.py`) ni el cálculo
  de liquidaciones (`calcular_liquidacion` sigue leyendo
  `SaldoCuentaAnterior` en vivo, confirmado correcto por lectura de
  código) — el desajuste que la clienta reportó en el saldo real de
  Gabriela Icutza ($207.292 en vez de $288.528) ya estaba identificado
  y cerrado en la ronda anterior como un resabio de datos (una
  liquidación de diciembre acreditada de más por un bug YA arreglado
  antes de esta ronda, corregida a mano por la clienta en Profesionales
  — ver el bloque correspondiente más abajo) — no un bug de cálculo
  vigente. No se hizo un barrido exhaustivo de la base real completa
  más allá de ese caso puntual y el chequeo ya documentado de que no
  hay otra fila con el mismo patrón.

- **Control de pagos: rediseño completo de "Carga y control" en 4
  columnas.** Hecho. Pedido explícito de la clienta sobre el layout de
  la ronda anterior (un solo panel de formulario a la izquierda + tabla
  a la derecha): pasa a 4 columnas de ancho IGUAL (`stretch=1` cada una
  en un `QHBoxLayout` común, cada una un `QWidget` propio con
  `objectName="panelSolapa"`) que abarcan todo el ancho de la pantalla,
  con la tabla ahora DEBAJO de esas 4 columnas (no al costado — el
  layout externo de `_PanelCargaControl` pasa de `QHBoxLayout` a
  `QVBoxLayout`), escroleable (`QTableWidget` normal, sin
  `QScrollArea` — ya no hace falta, al no competir por espacio con un
  panel lateral).

  - **Columna 1:** Nombre, Categoría, Afectación (sus dos combos) y
    Medio de pago.
  - **Columna 2:** Vencimiento, Importe, y el botón principal "Crear
    concepto".
  - **Columna 3:** los 4 botones secundarios sobre el CONCEPTO
    seleccionado — "Editar concepto seleccionado"/"Dar de baja concepto
    seleccionado"/"Duplicar para período próximo"/"Eliminar registro
    duplicado" (bajados de la columna 1 de la ronda anterior, sin
    cambiar su comportamiento).
  - **Columna 4:** los filtros, en cascada MUTUA — Nombre/Categoría/
    Afectación/Medio de pago no tienen jerarquía entre sí (a diferencia
    de una cascada jerárquica real del sistema, ej. Localidad->
    Edificio->Unidad en Estadísticas), así que cada combo se acota por
    la selección VIGENTE de los otros tres, nunca la propia
    (`_repoblar_filtros_cascada`/`_coincide_filtros` con el parámetro
    `excepto`) — si se acotara también a sí mismo, elegir un valor
    haría desaparecer las demás opciones de ESE mismo combo,
    imposibilitando cambiar la selección. Sentinel `_TODOS` (mismo
    criterio que `_PanelHistorialControlPagos._TODAS`) para "sin
    filtro", nunca `None`. Buscador con el mismo mecanismo que el
    selector de profesional (`habilitar_busqueda_profesional`, `app/
    gui/widgets/selector_profesional.py` — confirmado genérico, no
    depende de que el combo tenga datos de un profesional, solo de que
    ya esté poblado con pares etiqueta/dato) — no cambia de ancho al
    seleccionar ni al tipear, mismo `setFixedWidth` que el resto de los
    campos. Reemplaza por completo la fila de filtros de texto libre
    por columna que había armado la ronda anterior (sacados
    `filtros_columna`, `_sincronizar_ancho_filtros`, `_coincide_
    filtros` de texto libre, `_normalizar_filtro` y las constantes de
    ancho que esa fila necesitaba).

  **Pixel 85 en las 4 columnas:** cada columna usa el mismo margen
  superior que ya tenían Reservas regulares/Novedades
  (`_ALTO_TITULO_CARGA_CONTROL = 7`, sin cambios — confirmado que sigue
  dando el mismo resultado relativo en esta estructura de 4 columnas
  planas, sin el `QScrollArea` que envolvía el panel único de antes).
  Verificado por medición programática (offscreen) que el primer
  elemento de las 4 columnas — título o botón, lo que haya primero en
  cada una — queda exactamente a la misma altura relativa al panel, y
  que las 4 columnas quedan del mismo ancho entre sí (±1px por
  redondeo del `stretch` al repartir el ancho total entre 4).

  **Tabla:** vuelve a 8 columnas de datos (Nombre/Categoría/Afectación/
  Medio de pago en `Stretch`, el resto en `ResizeToContents` — se
  revierten los anchos fijos "robados" entre columnas de la ronda
  anterior, que ya no hacen falta al no competir con un panel lateral
  angosto) más 3 columnas de botón al final de cada fila — "Editar"
  (antes "Editar registro"), "Abonar" (antes "Marcar abonado") y
  "Archivar" (antes "Archivar registro"), mismas funciones y
  comportamientos, vueltas a vivir por fila (`_armar_botones_fila`) en
  vez de en la columna 1.

  **Bug real encontrado y arreglado en el camino — abort del proceso al
  cerrar, NO una falla de ningún test:** la primera versión de
  `_armar_botones_fila` reusaba el botón YA EXISTENTE en esa posición
  (fila_idx, columna) con `self.tabla.cellWidget(fila_idx, columna)`,
  llamando `.clicked.disconnect()` + `.connect(...)` para apuntarlo a
  la instancia nueva — el mismo patrón que tenía la primera
  implementación de este módulo. Como `_clave_orden_instancia`/un
  click de encabezado puede cambiar qué instancia cae en cada posición
  entre un `actualizar()` y el siguiente, reconectar un botón visual
  reciclado sobre una posición que before tenía una instancia distinta
  corrompía silenciosamente el estado de Qt/shiboken — los 26 tests de
  este archivo pasaban igual (ninguna aserción fallaba), pero el
  PROCESO terminaba con `Fatal Python error: bool_dealloc` (refcount
  corrupto) al cerrarse, solo en determinadas combinaciones de archivos
  de test ejecutados en el mismo proceso (confirmado: solo este
  archivo solo = aborta; combinado con `test_gui_pagos.py` = aborta;
  combinado con `test_gui_placas.py` = NO aborta — la combinación
  exacta de asignaciones/liberaciones de memoria es lo que determina si
  se manifiesta, no algo determinable por lógica de la app).
  Confirmado con el código ANTERIOR a esta ronda (sin estos botones por
  fila) que el abort no existía antes — es una regresión de esta
  ronda, no algo preexistente del sandbox. Arreglado creando un botón
  `QPushButton` NUEVO en cada `actualizar()` (igual que ya se hace con
  el resto de las celdas de la fila, un `QTableWidgetItem` nuevo cada
  vez) en vez de reusar por posición — de paso, `self.tabla.
  setRowCount(0)` antes de volver a crecer con `setRowCount(len(
  filas))`, para que Qt suelte los cell widgets viejos de una en vez
  de arrastrar alguno huérfano a una fila con otro contenido
  (confirmado con captura offscreen: sin este `setRowCount(0)`, un
  botón "Archivar" de una fila vieja quedaba pintado encimado contra la
  esquina superior izquierda de la tabla al agregar conceptos uno por
  uno — mismo tipo de huérfano ya documentado en Aumentos, "`setCellWidget`
  NO borra solo el widget que reemplaza").

  Tests reescritos/nuevos en `tests/test_gui_control_pagos.py` para la
  nueva API (botones por fila vía `tabla.cellWidget(fila, columna)` en
  vez de `panel.boton_editar_registro`/etc.; filtros vía los 4 combos
  `combo_filtro_*` en vez de `filtros_columna`):
  `test_las_cuatro_columnas_arrancan_a_la_misma_altura_y_con_igual_
  ancho`, `test_boton_dar_de_baja_entra_en_el_ancho_fijo_compartido_
  sin_cortar`, `test_filtro_categoria_acota_la_tabla_por_la_seleccion`,
  `test_filtros_cascada_se_acotan_mutuamente_sin_acotar_la_propia_
  seleccion`, `test_boton_reiniciar_filtros_vuelve_todos_los_combos_a_
  todos`, `test_f5_reiniciar_tambien_reinicia_los_filtros_cascada` —
  más los tests existentes de botones/colores/orden adaptados a la
  nueva ubicación de los tres botones por fila. pyflakes limpio. Suite
  completa sin regresiones nuevas (mismos fallos conocidos del
  sandbox/reloj, ver la lista de abajo) y sin el abort al cerrar en
  ninguna combinación de archivos probada.

- **Avance de mes: el traspaso de saldo perdía lo que quedaba sin pagar
  del período anterior.** Hecho — bug real, grave, encontrado al
  investigar en profundidad el pedido de la clienta de simplificar
  "Saldo anterior"/"Saldo actual". `_traspasar_saldos` (`app/negocio/
  avance_mes.py`) hacía `SaldoCuentaAnterior_nuevo = SaldoCuentaActual_
  viejo` — REEMPLAZABA en vez de sumar. Si un profesional terminaba el
  mes sin haber pagado del todo el saldo anterior (ej. $81.236
  pendientes de antes + $277.292 generados este mes), ese saldo
  anterior sin pagar se perdía directo al avanzar de mes (quedaba en
  $277.292 en vez de $358.528) — plata que dejaba de figurar en
  ningún lado sin que nadie la hubiera pagado ni perdonado.

  Arreglo quirúrgico, no una redefinición: pasa a sumar
  (`SaldoCuentaAnterior_nuevo = SaldoCuentaAnterior_viejo +
  SaldoCuentaActual_viejo`) — el significado de los dos campos no
  cambia en ningún otro lugar del sistema (planes de pago, mensajería
  automática a categoría X, las dos alertas de panel de control,
  Reinicio de prueba), así que no hubo que tocar nada más. Se evaluó y
  se descartó adoptar la propuesta de la clienta de redefinir
  "Saldo actual" para que ya incluya el anterior (`Saldo actual =
  Saldo anterior + liquidación del mes - pagos al actual`): arreglaría
  este mismo bug de rebote, pero pisa el significado que usan
  TEXTUALMENTE esos otros cuatro lugares — se prefirió el cambio
  mínimo que ataca la causa real sin ese riesgo. Test actualizado en
  `tests/test_avance_mes.py`: `test_traspaso_de_saldo_suma_el_anterior_
  sin_pagar_en_vez_de_perderlo` (antes `test_traspaso_de_saldo`,
  verificaba el comportamiento VIEJO/roto).

  **Pendiente, a pedido de la clienta:** no hay forma barata de saber
  con certeza, mirando solo el estado actual, a qué otros
  profesionales les pasó esto en el pasado — no se guarda ningún
  historial de qué valía `SaldoCuentaAnterior` en cada traspaso viejo
  (`SnapshotMensual` solo guarda ocupación/valores de consultorio, no
  saldos por profesional). Si hace falta auditar la base real, el
  camino es reconstruir por profesional "cuánto debería sumar hoy el
  combinado" a partir de lo que SÍ queda registrado para siempre
  (`LiquidacionEmitida.MontoGenerado` de la última emisión de cada
  período + todo `HistorialPagos.Monto` + los movimientos de
  `PlanPago`/refinanciación) y compararlo contra el combinado real —
  cualquier diferencia hacia abajo es plata perdida por este bug. No
  se armó ese script todavía (hace falta la base real para correrlo y
  confirmar los números contra algo verificable, igual que se hizo a
  mano con Gabriela Icutza y Aldana Portillo) — queda disponible para
  cuando la clienta la vuelva a mandar.

- **Placas: una posición recién asignada no aparecía para imprimir sin
  cambiar de solapa.** Hecho — bug real. `_PanelImprimirPlacas.
  showEvent` repoblaba el combo de profesional (`_cargar_combo_
  profesional_imprimir`) pero la lista "Placa a imprimir" (`_cargar_
  placas_profesional_imprimir`) solo estaba conectada al
  `currentIndexChanged` de ESE combo — si el profesional seleccionado
  no cambiaba de índice al volver a la solapa (el caso normal: sigue
  siendo el mismo de antes), la lista de placas se quedaba con los
  datos de la última vez que sí cambió de profesional, sin reflejar lo
  que se hubiera asignado/liberado mientras tanto en "Búsqueda y
  asignación de placas". Se suma el llamado directo a `_cargar_placas_
  profesional_imprimir()` en el `showEvent`, junto al del combo — ya
  consulta la base en vivo, así que entrar a la solapa siempre refleja
  lo recién asignado. Test nuevo en `tests/test_gui_placas.py`:
  `test_placa_asignada_en_buscar_aparece_en_imprimir_sin_cambiar_de_
  profesional`.

- **Registro de ausencias: alerta de éxito en las cuatro solapas.**
  Hecho. Pedido explícito de la clienta sobre Vacaciones/Licencias/
  Ausencias (Tipos de licencia ya la tenía: es el catálogo genérico
  `PantallaCRUD`, que ya avisa "Registro creado/editado/eliminado con
  éxito." sin tocar nada). Dos huecos reales en las otras tres:
  - "Crear..." en Vacaciones/Licencias solo avisaba cuando había
    advertencias de por medio (Ausencias ya avisaba siempre, de una
    ronda anterior) — pasa a avisar siempre ("Vacación cargada con
    éxito."/"Licencia cargada con éxito."), sumando las advertencias
    debajo del mensaje cuando las hay, en vez de reemplazarlo.
  - "Anular..." (botón `_cancelar`) no avisaba nada en ninguna de las
    tres — se agrega el aviso ("... anulada con éxito.") solo en el
    método del botón, no en `_cancelar_registro` (el helper
    compartido con "Modificar...", que primero anula y recién después
    deja el formulario precargado para dar de alta la versión
    corregida — avisar ahí sería prematuro, la alerta de éxito real
    de un "Modificar" llega sola al tocar "Crear..." después).
  Tests nuevos en `tests/test_gui_novedades.py`:
  `test_crear_vacacion_muestra_alerta_final_de_exito`,
  `test_anular_vacacion_muestra_alerta_final_de_exito`,
  `test_crear_licencia_muestra_alerta_final_de_exito`,
  `test_anular_licencia_muestra_alerta_final_de_exito`,
  `test_anular_ausencia_muestra_alerta_final_de_exito`.

- **Corrección general de "Saldo previo"/"Nuevo saldo" en filas
  históricas de `HistorialPagos`.** Hecho, sobre la base real que
  mandó la clienta. Investigando el caso de Gabriela Icutza se vio que
  el problema era mucho más general: como el cálculo combinado es de
  esta sesión, TODA fila de `HistorialPagos` anterior a hoy muestra el
  valor viejo de un solo campo en vez del combinado, para cualquier
  profesional que tuviera algo en el OTRO campo en ese momento — no es
  plata perdida, es una foto vieja de una columna que antes no existía
  así.

  Se armó un script de reconstrucción (no forma parte del repositorio,
  vive en el historial de esta sesión) que reconstruye el combinado
  real de cada pago CON CERTEZA MATEMÁTICA caminando hacia atrás desde
  el saldo combinado vigente HOY de cada profesional, restando el
  `Monto` de cada pago uno por uno — válido únicamente mientras no haya
  ningún otro evento en el medio que también mueva el saldo (una
  liquidación emitida, un cambio de mes que sugiere un avance de mes,
  o una corrección manual ya conocida). Sobre la base real: 123 pagos
  en total — 18 ya estaban bien, 64 se corrigieron con certeza, 39 no
  se tocaron (tienen una liquidación emitida en el medio y no se puede
  asegurar el número sin mirar el PDF real, caso por caso, si alguna
  vez hace falta) y 2 profesionales quedaron afuera a propósito: uno
  con un plan de pagos activo (la refinanciación mueve plata entre
  campos de una forma que esta cuenta no contempla) y Aldana Portillo
  (R2, ya tiene una corrección manual documentada en el saldo que
  rompe la reconstrucción retroactiva para ella). Solo se tocaron las
  columnas `SaldoAnterior`/`SaldoNuevo` de `HistorialPagos` — ningún
  otro dato de la base, confirmado con `PRAGMA integrity_check` y
  comparando la cantidad de filas de cada tabla antes/después.

  **Revertido y vuelto a aplicar, SOLO categoría R.** La clienta
  reportó que la corrección de categoría A dio error — investigado:
  los profesionales categoría A nunca pasan por `LiquidacionEmitida`
  ("solo los profesionales categoría R tienen liquidación mensual
  propia", `app.negocio.liquidaciones`), así que su saldo de arranque
  (antes del primer pago registrado) no sale de ningún evento
  rastreable en la base — sale de una carga manual puntual (mismo
  punto ciego que ya tenía Aldana Portillo, pero generalizado a toda
  la categoría) que el script no tenía forma de detectar como "riesgo"
  en la cadena hacia atrás. Se corrigió filtrando la reconstrucción a
  `CategoriaProfesional == "R"` únicamente, corriendo de NUEVO contra
  el archivo ORIGINAL que había mandado la clienta (no sobre el ya
  corregido, para no encadenar un error sobre otro) — sin esto, A
  (y cualquier otra categoría salvo R) queda exactamente en el valor
  que tenía antes de cualquier corrección. Resultado sobre la base
  real: 32 profesionales / 52 pagos corregidos (categoría R
  únicamente) — confirmado por bit a bit que las filas de categoría A
  quedan idénticas al archivo original sin tocar.

## Historial archivado

El detalle ronda por ronda de cada pantalla/funcionalidad (pedidos de la
clienta, investigación, decisiones, nombres de tests) se movió a
`docs/historial/*.md` — esto (CLAUDE.md) se quedó solo con las
convenciones/reglas generales que siguen vigentes hoy y que se citan desde
cualquier pantalla. Antes de trabajar sobre un formulario puntual, leer el
archivo correspondiente de la lista — ahí está el contexto real de por qué
algo quedó como quedó:

- `docs/historial/general.md` — reorganizaciones de navegación, auditorías
  y tandas de correcciones que tocan varias pantallas a la vez.
- `docs/historial/sistema.md` — Configuración general, Panel de control,
  Seguridad, Usuarios y permisos, Backup, Reinicio de prueba, Pantalla de
  carga.
- `docs/historial/catalogos.md` — catálogos genéricos (`PantallaCRUD`):
  Mensajes predefinidos, Gastos operativos, Fechas especiales, Listas
  editables, Condiciones y normas, Detalles complementarios, Localidad,
  Consultorios, Importar planilla, Bloques rígidos.
- `docs/historial/archivos.md` — Gestor de archivos, tipo "Enlace", Textos
  del sistema.
- `docs/historial/grilla_mensajeria.md` — Grilla semanal, Centro de
  mensajería, Mensajes predefinidos.
- `docs/historial/reservas.md` — Reservas regulares, aisladas y
  extraordinarias.
- `docs/historial/disponibilidad.md` — Oferta de consultorios, Lista de
  espera, Archivos para enviar.
- `docs/historial/liquidaciones.md` — Liquidaciones (incluye Liquidaciones
  simuladas).
- `docs/historial/valores.md` — Valores vigentes, Aumentos, Esquema de
  descuentos.
- `docs/historial/estadisticas.md` — Estadísticas.
- `docs/historial/balance.md` — Balance del negocio.
- `docs/historial/pagos.md` — Pagos.
- `docs/historial/novedades.md` — Registro de ausencias (Vacaciones/
  Licencias/Ausencias) y Cargos especiales.
- `docs/historial/llaves.md` — Llaves y otros conceptos.
- `docs/historial/placas.md` — Placas para timbres.
- `docs/historial/profesionales.md` — Profesionales.

Un pedido nuevo sobre una pantalla sigue documentándose en CLAUDE.md como
hasta ahora (sección propia con la ronda de trabajo); si esa sección queda
"cerrada" y deja de aportar algo que otra pantalla necesite tener siempre
a la vista, se puede migrar después al archivo que corresponda — no hace
falta hacerlo en el momento.

