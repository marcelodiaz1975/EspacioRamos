# Historial archivado — Liquidaciones

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

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

## Octava tanda de correcciones post-v1: Liquidaciones simuladas abierta a
## todas las categorías

Pedido explícito de la clienta sobre "Liquidaciones simuladas" (cuarta
solapa de "Liquidaciones"): el combo Profesional estaba acotado a
categoría R (`_opciones_profesional(self.conn, ("R",))`), pero el caso
de uso real de esta herramienta ("mostrarle a un profesional cuánto le
saldría reservar ciertos bloques antes de darlos de alta de verdad") no
tiene por qué limitarse a esa categoría — un B, A o E también puede
querer ver el ejemplo antes de confirmar nada. Combo pasa a `_opciones_
profesional(self.conn)` (todas las categorías, mismo criterio B/R/A/E/
X/C que el resto del sistema).

**Anonimización para categoría C** (todavía no activo): mismo criterio
ya usado en `oferta_pdf`/`fotos_pdf`/`oferta_busqueda_pdf` — "Unidad
{IdUnidad}" (el ID crudo, autoincremental) en vez del `Departamento`
real ("7mo L"). `_ubicacion_bloque` (`app/gui/pantallas/liquidacion.py`,
la tabla "Bloques cargados" de la GUI) y `_lugar_bloque`
(`app/pdf/liquidacion_simulada_pdf.py`, el PDF) suman un parámetro
`anonimizar: bool = False`, con el SELECT de las dos extendido para
traer `Unidad.IdUnidad`. `generar_pdf_liquidacion_simulada` calcula
`anonimizar = not categoria_es_activa(profesional)` (`app.negocio.
oferta_busqueda_texto`, el helper ya existente en todo el sistema para
esta misma distinción) una sola vez, justo después de validar que el
profesional existe. En la GUI, `_PanelLiquidacionesSimuladas` suma
`_anonimizar_actual()` (lee la categoría del profesional elegido en el
combo) y lo pasa a `_ubicacion_bloque` desde `_refrescar_tabla_bloques()`.

**Limpiar bloques al cambiar de profesional**: cargar bloques para un
profesional y después cambiar el combo a otro dejaba la lista vieja
colgada, mezclando bloques pensados para un profesional con la
simulación de otro. `combo_profesional.currentIndexChanged` se conecta
a `_al_cambiar_profesional` (nueva) — vacía `self._bloques`, refresca
"Bloques cargados" (ahora vacía) y limpia también "Totales por bloques
y general" (la simulación anterior ya no corresponde a lo que se ve
cargado). La conexión se instala al FINAL de `_armar_ui`, después de
construir `tabla_bloques`/`tabla_subtotales` — conectarla antes
dispara `currentIndexChanged` durante el propio `addItem` de poblado
inicial del combo, con esas tablas todavía sin existir.

Tests nuevos: `tests/test_gui_liquidacion.py`
(`test_liquidaciones_simuladas_lista_todas_las_categorias` — reemplaza
al viejo "solo categoría R";
`test_liquidaciones_simuladas_categoria_r_muestra_unidad_real`;
`test_liquidaciones_simuladas_categoria_c_anonimiza_la_unidad`;
`test_liquidaciones_simuladas_cambiar_profesional_limpia_bloques_y_
resultado`). `tests/test_pdf_liquidacion_simulada.py`
(`test_profesional_categoria_c_anonimiza_la_unidad` — mismo criterio,
contra el PDF generado).

## Liquidaciones (las cuatro solapas): batch completo (#11.x del documento)

Duodécima tanda de `v0.11.2026.10`, cerrando la undécima sección del
documento ("LIQUIDACIONES"). Mismo criterio de investigar primero: tres
de las cuatro solapas ya estaban prácticamente resueltas de tandas
anteriores (Selector de período, "Emitir seleccionadas" deshabilitado,
monto a generar = total, aviso de regeneración de Fechas especiales,
todas confirmadas leyendo el código actual), así que esta tanda se
concentró en los huecos reales que quedaban:

- **Emisión de archivos** (1.2/1.5/1.7/1.11): confirmado todo resuelto
  — combo de profesional con `habilitar_busqueda_profesional`,
  `excluir_tabla_del_tab` en la tabla, y `_emitir` ya pedía confirmación
  y mostraba un cartel de éxito con la cantidad emitida (de la tanda del
  Selector de período). Sin cambios de código.
- **Estado de cuenta**: 1.2/1.7 confirmados (combo con búsqueda,
  `excluir_tabla_del_tab`). 1.4 (reset de filtros al reingresar) NO se
  aplicó a propósito — `actualizar()` ya documenta una decisión
  consciente, anterior a este documento, de CONSERVAR el profesional
  elegido al salir y volver a entrar a esta solapa ("se busca de nuevo
  por su id después de repoblar el combo, en vez de resetear a
  'ninguno'") — aplicar 1.4 acá hubiera revertido esa decisión sin que
  nadie lo pidiera de nuevo.
- **Feriados y fechas especiales**: es el catálogo genérico
  `FechasEspeciales` anidado (`PantallaCRUD`) — 1.4/1.11 ya cubiertos de
  rebote por el cambio central en `crud_generico.py` de una tanda
  anterior, sin necesitar nada puntual acá.
- **Liquidaciones simuladas** — tres huecos reales:
  - **1.4**: esta solapa nunca tuvo `reiniciar()` — `showEvent` solo
    enfocaba Profesional. Se suma `reiniciar()` (Período al mes
    siguiente del actual — el default de siempre —, Localidad a
    "Todas", bloques cargados y resultado de la última simulación
    vaciados, foco en Profesional) y `showEvent` pasa a llamarla. El
    combo Profesional NO tiene una opción en blanco (siempre hace falta
    elegir uno para poder generar, a diferencia del resto de los
    combos de profesional del sistema) — `reiniciar()` no lo toca, se
    queda en el que ya estuviera elegido.
  - **"+ período + selector"**: "Período a simular" pasa de `QLineEdit`
    en texto libre a `SelectorPeriodo` (el widget de año+mes ya sumado
    para "Emisión de archivos" en una tanda anterior, que en su momento
    había quedado deliberadamente afuera de esta solapa) — mismo
    criterio que el resto del sistema, con el mismo default de siempre
    (mes siguiente al actual) fijado vía `set_periodo`. La validación
    de "Falta el período" se saca de `_generar`: `SelectorPeriodo`
    siempre tiene un valor válido, nunca puede quedar vacío.
  - **"PDF rojo" + "texto aclaratorio"**: el párrafo que avisa que es un
    documento de ejemplo (ya en itálica desde que se armó esta
    funcionalidad) pasa además a `COLOR_ROJO` — mismo criterio que
    "importes negativos en rojo" del resto del sistema, para que la
    aclaración de "esto no es una liquidación real" se destaque a
    simple vista.

Tests nuevos: `tests/test_gui_liquidacion.py`
(`test_liquidaciones_simuladas_reiniciar_vuelve_al_estado_inicial`,
ajuste de `test_liquidaciones_simuladas_periodo_por_defecto_es_el_mes_
siguiente_al_actual` al nuevo `.periodo()` en vez de `.text()`).
`tests/test_pdf_liquidacion_simulada.py`
(`test_disclaimer_de_documento_de_ejemplo_se_ve_en_rojo` — extrae los
spans de texto del PDF con PyMuPDF y compara el color del span que
contiene "Documento de ejemplo" contra el entero RGB de `COLOR_ROJO`).
Suite combinada (`test_gui_liquidacion.py` +
`test_pdf_liquidacion_simulada.py` + `test_catalogos.py` +
`test_pdf_liquidacion.py` + `test_gui_main.py`): 165 passed, sin
regresiones.

## Liquidaciones: redondeo del total a un peso entero (parámetro nuevo)

Pedido de la clienta, dado como ejemplo de "cambios de lógica, no de
tablas" al preguntar sobre el proceso de instalar una versión nueva
conservando la base: "agregar un parámetro en configuración para
indicar cómo redondear el importe total de la liquidación para que
luego de hacer toda la cuenta con centavos el último número quede
entero si yo lo llegara a setear así." Antes de implementar se
consultaron tres decisiones (`AskUserQuestion`):

- **Sobre qué monto**: confirmó "el importe en letras" — el `total`
  (saldo anterior + lo generado), no solo lo generado este mes.
- **Criterio**: al más cercano (redondeo estándar).
- **Impacto contable**: "ajuste contable real" — no es solo de
  presentación, tiene que modificar de verdad la cuenta.

Sobre el impacto contable, la clienta agregó una precisión clave que
termina de definir el diseño: "Si el parámetro nuevo está configurado
en 0 decimales, todos los valores de la cuenta deben mostrarse con
centavos y solo el resultado final, el del importe en letras, se debe
redondear. El importe del redondeo de ese valor se debe detallar como
último concepto justo antes del valor en letras, arriba del total
liquidado, con los centavos que hagan falta a favor o en contra para
que la suma luego de exacta. El detalle de decir únicamente
'Redondeo'."

### Parámetro nuevo, distinto del ya existente `CantidadDecimales`

Investigado antes de tocar nada: YA existe `Configuracion.
CantidadDecimales` (`app.negocio.formato.decimales_configurados`), pero
es un parámetro GLOBAL de puro DISPLAY — controla cuántos decimales se
VEN en Valores/Propuesta/Oferta/Disponibilidad/Oferta búsqueda (texto y
PDF), sin ningún efecto sobre ningún número real de la base. Reusarlo
para disparar un ajuste contable real en Liquidaciones hubiera sido un
riesgo real y silencioso: alguien que pusiera `CantidadDecimales=0`
solo para que otro PDF se vea más limpio empezaría, sin saberlo, a
generar ajustes de saldo en Liquidaciones. Se optó por un parámetro
NUEVO y totalmente independiente, `Configuracion.
DecimalesTotalLiquidacion` (INTEGER, default 2 — "sin redondear", mismo
comportamiento de siempre), para que activar uno nunca afecte al otro.

`decimales_total_liquidacion(conn)` (nueva, `app.negocio.formato`, al
lado de `decimales_configurados`): lee ese campo, default 2 si está en
NULL. GUI: mismo patrón que `CantidadDecimales` (`QSpinBox`, rango 0-4)
pero en la solapa "Valores y liquidación" de Configuración general (no
en "General", donde vive `CantidadDecimales`) — es un parámetro de
cálculo de liquidación, no de display general.

### `Liquidacion.ajuste_redondeo` (negocio)

`app.negocio.liquidaciones.Liquidacion` suma un campo nuevo,
`ajuste_redondeo: float = 0.0`, sumado dentro de la propiedad
`monto_generado` (mismo lugar que `ajuste_saldo_atrasado`) — así viaja
solo, sin ningún código nuevo, hasta `LiquidacionEmitida.MontoGenerado`
y el delta que `emitir_liquidacion` acredita a `SaldoCuentaActual`: es
un ítem más de la cuenta real, no un redondeo de pantalla.

`calcular_liquidacion` lo calcula al FINAL, después de armar el resto
de la liquidación (con `ajuste_redondeo` todavía en 0, así que
`liquidacion.total` da el valor exacto, con centavos): si
`decimales_total_liquidacion(conn) == 0`, `ajuste_redondeo = round(
total_exacto) - total_exacto` — los centavos exactos, a favor o en
contra, que hacen falta para que el total termine en un entero. En
cualquier otro valor del parámetro, `ajuste_redondeo` se queda en 0 y
nada cambia respecto de antes de este pedido.

### PDF (`app/pdf/liquidacion_pdf.py`)

`_items_cuenta` suma la línea "Redondeo" (con el valor de `ajuste_
redondeo`, positivo o negativo) justo antes del ítem final "Liquidación
a abonar..." — solo si `ajuste_redondeo` es distinto de 0 (no aparece
si el total ya caía justo en un peso entero, o si el parámetro está
apagado). `en_letras_pesos`/`_entero_y_centavos` ya manejaban bien un
monto exactamente entero (sin "con NN/100" de más) desde antes de este
pedido, así que no hizo falta tocar nada ahí — el PDF ya muestra el
total redondeado en letras, limpio.

`generar_pdf_liquidacion` fuerza `decimales = 2` cuando `decimales_
total_liquidacion(conn) == 0`, SIN importar lo que diga `CantidadDecimales`
— cumple al pie de la letra "todos los valores de la cuenta deben
mostrarse con centavos" cuando el redondeo está activo, sin que el otro
parámetro (pensado para otros documentos) pueda truncar de más los
ítems de esta liquidación puntual.

### Tests

`tests/test_formato.py` (`decimales_total_liquidacion` default 2,
independiente de `CantidadDecimales`). `tests/test_liquidaciones.py`
(sin el parámetro activo el total no se toca aunque el saldo anterior
tenga centavos; con el parámetro en 0 el total queda entero y `ajuste_
redondeo` es el valor exacto esperado; si el total ya caía en un
entero el ajuste da 0, no de más; el ajuste viaja de verdad hasta
`SaldoCuentaActual` vía `emitir_liquidacion`, no es solo de
presentación). `tests/test_pdf_liquidacion.py` (la línea "Redondeo"
aparece justo antes del total y no aparece sin ajuste; el PDF real
muestra la línea con los centavos exactos; los ítems siguen con
centavos aunque `CantidadDecimales` también esté en 0). `tests/
test_migraciones.py` (una base vieja gana la columna con el default 2,
sin afectar liquidaciones ya en uso). `tests/test_gui_configuracion.py`
(el campo es un `QSpinBox` en "Valores y liquidación", no en "General";
guardar lo persiste).

### Instalar una versión nueva conservando la base (pregunta de la clienta)

Sin relación con el cambio de arriba, pero preguntado en el mismo
mensaje: confirmado que copiar `data/espacio_ramos.db` (el único
archivo de la base, al lado del ejecutable — `app.db.connection.
_raiz_proyecto`) a la carpeta de la versión nueva alcanza, sin importar
si esa versión suma columnas/tablas — `init_database` corre `aplicar_
migraciones` en cada arranque, de forma idempotente, así que una base
vieja se pone al día sola la primera vez que la abre la versión nueva.
Las carpetas de archivos/backup (`CarpetaBaseArchivos`/`CarpetaBackup`)
solo hay que copiarlas si están configuradas DENTRO de la carpeta de
instalación vieja — si apuntan a una ruta fija del disco, la versión
nueva las sigue encontrando sola.

## Liquidaciones simuladas: sección "Fotos de los consultorios ofrecidos"

Primera prueba del flujo de trabajo nuevo (sesiones separadas por tema,
ver `CLAUDE.md` — "Historial archivado"): se le pidió a la IA cargar
solo `docs/historial/liquidaciones.md` como contexto antes de tocar
nada, en vez del proyecto entero.

Pedido de la clienta: debajo de la tabla "Liquidación simulada" (en el
PDF de esa cuarta solapa), una sección nueva "Fotos de los consultorios
ofrecidos" con una foto de cada consultorio involucrado en los bloques
cargados, junto a su nombre y su valor.

### Implementación (`app/pdf/liquidacion_simulada_pdf.py`)

Reusa tal cual el helper ya compartido por Propuesta/Disponibilidad
(`app.pdf.fotos_pdf.imagenes_de_consultorios`/`tabla_fotos`, con
`mostrar_valor=True`) en vez de armar un pie de foto propio — el pie
default de ese modo ("Consultorio {N} — Valor hora regular {$}") ya es
exactamente "nombre y valor", sin necesitar `pie_personalizado`.
`mostrar_apto_camilla=False` (como Disponibilidad): acá no es una
oferta real, no aporta nada.

`ids_consultorio = sorted({b.id_consultorio for b in liquidacion.
bloques})` (los consultorios de los bloques simulados, sin duplicar si
dos bloques comparten consultorio) alimenta `imagenes_de_consultorios`;
la estimación de `altura` (para que `construir_sin_saltos` no tenga que
reintentar con una página más alta) suma `(len(imagenes) // 2 + 1) * 7
* cm`, mismo criterio que ya usa `oferta_pdf.py` para su propia sección
de fotos. Sin ninguna `Imagen` cargada para esos consultorios, cae al
mismo aviso "Sin fotos cargadas." que el resto del sistema — no hace
falta ningún caso especial.

### Segunda vuelta: Tratamiento en el título, descuento en rojo

Dos pedidos de la clienta al revisar la primera captura:

- **"Con el nombre del profesional que salga el tratamiento también
  ('{Tratamiento} {Nombre} {Apellido}'), en la liquidación que yo
  simulé no salió el tratamiento de un profesional categoría X por
  ejemplo, pero sí lo vi en la captura que me mandaste."** Investigado
  antes de tocar nada: `_nombre_completo` (el título del PDF y el
  nombre de archivo) ya arma el nombre igual para cualquier categoría
  (`profesional["Tratamiento"] or ""`, sin ninguna rama que lo
  condicione a la categoría ni a `categoria_es_activa`/`anonimizar` —
  confirmado también contra `liquidacion_pdf.py`/`oferta_busqueda_
  texto.py`, que arman el nombre con el mismo criterio exacto en todo
  el sistema) y `Profesional.obtener(...)` hace `SELECT *`, así que el
  campo llega completo sin importar la categoría. Confirmado armando un
  profesional categoría X con `Tratamiento="Fgo."` de prueba: aparece
  correcto en el título y en el nombre de archivo. La conclusión, que
  se le devolvió a la clienta: el código ya es category-agnostic — si
  en su prueba no apareció, el profesional puntual que usó no tiene el
  campo Tratamiento cargado en el catálogo de Profesionales, no es un
  bug de esta pantalla. Se sumó un test de regresión igual, para que
  quede blindado ante un cambio futuro que sí rompiera esto.
- **"El importe que resta, en este caso los descuentos por volumen de
  horas, que se vea en fuente roja como todos los importes negativos
  del sistema."** Hueco real, confirmado contra el código: la tabla
  "Liquidación simulada" nunca había tenido ninguna regla de color por
  signo (a diferencia de `_tabla_plana` en `liquidacion_pdf.py`, que sí
  pinta de `COLOR_ROJO` cualquier importe negativo fila por fila). Se
  corrige con el mismo criterio: `filas_montos` pasa a construirse a
  partir de una lista intermedia `items_montos` (concepto, importe
  numérico sin formatear todavía), y después de armar la tabla se
  recorre esa lista sumando `("TEXTCOLOR", (1, i), (1, i), COLOR_ROJO)`
  por cada fila con importe negativo — cubre tanto el descuento por
  volumen de horas como cualquier descuento por feriado, y el total
  simulado si alguna vez diera negativo (no cambia nada del resto del
  estilo de esa fila, que sigue en negrita).

Tests nuevos en `tests/test_pdf_liquidacion_simulada.py`:
`test_sin_fotos_cargadas_muestra_el_aviso`, `test_con_foto_cargada_
muestra_el_pie_con_nombre_y_valor`, `test_tratamiento_se_muestra_sin_
importar_la_categoria` (categoría X con Tratamiento cargado, confirma
que aparece en el título y en el nombre de archivo), `test_descuento_
por_volumen_de_horas_se_ve_en_rojo` (con un bloque de 6hs semanales —
el esquema de descuentos por defecto da 0% hasta 2hs, hacía falta más
para tener un importe negativo real que pintar).

## Reemitir el período en curso se bloqueaba por una preview futura

Bug real reportado por la clienta: parada en noviembre (período
operativo actual), cargó reservas aisladas a una profesional R con
"Período a imputar" = actual para noviembre, y otras agendadas para
diciembre (mes siguiente, dentro del tope de 1 mes de anticipo). Al
apretar "Emitir todas las liquidaciones" (período noviembre), esa
profesional quedó afuera con el error "no se puede reemitir la
liquidación de un período anterior a la última que se hizo — resolvé
la diferencia con ajustes".

La clienta identificó la causa ella misma: cargar/editar una reserva
aislada de un mes FUTURO con "Período a imputar" = actual dispara
`regenerar_si_corresponde` (`app/negocio/liquidaciones.py`) para ESE mes
futuro (`_resolver_periodo_imputar`, `reservas.py`, con `periodo_reserva
= fecha[:7]` de la reserva) — crea una `LiquidacionEmitida` de diciembre
que es pura previsualización (mantiene el PDF/el estado del Centro de
mensajería al día si llegara a consultarse), sin que ningún avance de
mes la haya "cerrado" todavía. El guard de `emitir_liquidacion` ("no se
puede reemitir un período si ya hay liquidaciones de períodos
posteriores", DC-08 §6.2) comparaba contra CUALQUIER fila con `Periodo
> periodo`, sin distinguir una preview de un período realmente cerrado
— exactamente el caso que la clienta señaló: "sería un problema rehacer
octubre parado en noviembre, pero rehacer noviembre estando parado en
noviembre no tendría que tener ningún problema".

Reproducido con un script antes de tocar nada: se repite el escenario
exacto (operativo en noviembre, liquidación de noviembre emitida,
`regenerar_si_corresponde` para diciembre simulando la reserva aislada
futura, reintento de reemisión de noviembre) y el error aparece tal
cual lo describió la clienta.

Arreglado acotando la consulta del guard a `Periodo <= periodo_
operativo_actual(conn)` (`app/negocio/dias.py`, ya existía, sin usar
en este módulo): un período posterior solo bloquea si el período
operativo YA lo alcanzó — ahí sí pudo haber usado como base de cálculo
el período que se querría reabrir (el riesgo real que describe el
docstring de la función, "feriados/horas pendientes" duplicados). Una
preview de un mes que todavía no llegó no corre ese riesgo. Confirmado
con el mismo script que el caso que SÍ debe seguir bloqueado (un
período posterior realmente alcanzado) sigue bloqueando igual que
antes.

Test nuevo en `tests/test_liquidaciones.py`
(`test_emitir_liquidacion_no_rechaza_reemitir_si_el_periodo_posterior_
es_solo_una_preview_futura`) junto al test ya existente del caso que sí
bloquea (`test_emitir_liquidacion_rechaza_reemitir_periodo_anterior_a_
uno_ya_emitido`, al que se le sumó fijar `PeriodoOperativoActual`
explícitamente — antes dependía sin querer de que la fecha real del
sistema al correr el test ya hubiera pasado el período "posterior" del
escenario, algo que este mismo fix podía romper).

## Feriados y días no laborables en orden cronológico (PDF)

Pedido explícito de la clienta: en el PDF de liquidación mensual, los
descuentos por feriado y por día no laborable aparecían "mezclados" —
ejemplo dado: el feriado del 9 tiene que ir arriba del 23, no al revés.

Causa: `_calcular_descuentos_feriados` (`app/negocio/liquidaciones.py`)
devuelve DOS listas separadas (feriados nacionales / días no
laborables), cada una ordenada por su cuenta — pero antes con
`reverse=True` ("de más próximo a hoy arriba a más alejado abajo",
pedido de una ronda anterior de este mismo archivo, que en la práctica
daba el más RECIENTE primero). El PDF (`liquidacion_pdf.py::_items_
cuenta`) además las imprimía en dos bloques separados, uno por tipo —
así que aunque cada lista estuviera bien ordenada por su cuenta, el
resultado cruzado (feriados nacionales primero, días no laborables
después) no seguía una sola secuencia cronológica.

Arreglado en los dos lados: el criterio de orden pasa a ser ascendente
(el más viejo arriba) en `_calcular_descuentos_feriados` Y en
`_calcular_feriados_pendientes` ("mismo criterio", mismo comentario de
siempre) — pisando el pedido anterior de "más próximo a hoy arriba" a
pedido explícito de esta ronda, con un ejemplo concreto que lo deja sin
ambigüedad. Y en el PDF, las dos listas (feriados + no laborables) se
combinan con `sorted(...)` en un ÚNICO loop en vez de dos loops
separados por tipo, así quedan intercaladas por fecha real sin
importar el tipo de cada una.

De paso, mismo criterio aplicado en `liquidacion_simulada.py`
(`descuentos_feriados`, que no tenía NINGÚN orden — dependía del orden
de carga en la tabla de Fechas especiales) para no dejar la misma clase
de bug sin tocar en "Liquidaciones simuladas", aunque la clienta no la
mencionó puntualmente.

Tests actualizados/nuevos en `tests/test_pdf_liquidacion.py`: el test
viejo de orden (`test_descuentos_feriados_quedan_ordenados_de_mas_
reciente_a_mas_antiguo`) pasa a `..._cronologicamente` con la aserción
invertida, y un test nuevo
(`test_descuentos_feriados_y_no_laborables_se_intercalan_por_fecha`)
cubre el caso real de un feriado nacional y un día no laborable en el
mismo mes saliendo en un solo listado intercalado.

