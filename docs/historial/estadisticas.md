# Historial archivado — Estadísticas

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

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

