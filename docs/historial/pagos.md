# Historial archivado — Pagos

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

## Pagos (las tres solapas): batch completo (#12.x del documento)

Decimotercera tanda de `v0.11.2026.10`, cerrando la duodécima sección
("PAGOS"). Las tres solapas ya tenían 1.2/1.5/1.7 resueltos de rondas
anteriores (selector de profesional con búsqueda, `excluir_tabla_del_
tab`, foco visible global) — el hueco real era 1.4 en las dos primeras:

- **Registrar pagos**: `showEvent` ya reiniciaba el orden de la tabla y
  refrescaba, pero nunca volvía el combo Profesional (que cumple doble
  función — filtro de la tabla Y "a quién registrarle el pago") a
  "Todos los profesionales" al reingresar a la solapa — quedaba en lo
  último elegido. Se suma `reiniciar()` (llamado desde `showEvent` y
  disponible para F3): mismo `_resetear_formulario()` que ya corría
  después de Registrar/Modificar/Eliminar/Deshacer, más el orden y el
  refresco de siempre.
- **Planes de pago**: mismo hueco — `showEvent` llamaba `_profesional_
  cambio()` directo sin resetear el combo primero, así que el
  profesional elegido sobrevivía al reingreso. `reiniciar()` nuevo
  vuelve Profesional a "Seleccionar profesional…" y Cuotas/Interés a su
  default (3 cuotas, 0%) antes de refrescar.
- **Estado de cuenta**: solo 1.2, ya resuelto (combo con búsqueda) —
  sin cambios. A diferencia de "Estado de cuenta" de Liquidaciones, acá
  no se consultó si correspondía sumarle 1.4 — no estaba en la lista de
  puntos para esta solapa en particular.
- **"Deshacer último movimiento" (Registrar pagos) y "monto a
  refinanciar" (Planes de pago)**: confirmados ya resueltos de tandas
  anteriores (deshabilitado sin movimientos; sugerido con el saldo
  atrasado + cuotas pendientes del plan a reemplazar) — sin cambios.
- **"Autocierre de tanda" (Registrar pagos)**: no implementado en esta
  tanda — no se encontró en el código ningún mecanismo de cierre
  automático de la tanda de sobres (solo manual, "Iniciar tanda"/
  "Cerrar tanda"), y sin el texto original del punto a la vista no hay
  forma confiable de inferir qué condición debería dispararlo (¿fin de
  día? ¿avance de mes? ¿cierta cantidad de sobres?) sin arriesgar
  inventar un comportamiento que la clienta no pidió. Queda pendiente
  de una aclaración puntual antes de implementarse.

Tests nuevos: `tests/test_gui_pagos.py`
(`test_registrar_pagos_reiniciar_vuelve_filtro_y_formulario_al_
default`, `test_planes_de_pago_reiniciar_vuelve_combo_y_spins_al_
default`). Suite: 62 passed.


## Pagos: `regenerar_si_corresponde` también regenera el PDF de la liquidación

Pedido de la clienta, hilo nuevo a partir de Pagos: imputar un pago al
mes anterior para un R ya actualizaba bien el estado en la grilla del
Centro de mensajería ("no enviada"), pero no regeneraba el ARCHIVO PDF
en disco — quedaba con los números de ANTES del pago. "No hace falta
preguntar, lo tiene que hacer sí o sí."

Investigado antes de tocar código: `regenerar_si_corresponde`
(`app.negocio.liquidaciones`) solo llamaba a `emitir_liquidacion`, que
ÚNICAMENTE persiste el registro en `LiquidacionEmitida` (lo que ya
alcanzaba para el estado correcto en mensajería) — el PDF en sí
(`generar_pdf_liquidacion` + `NombreArchivo`/`FechaHoraGeneracion`) solo
lo generaba la pantalla de Liquidaciones (`_emitir`), nunca esta función
compartida. El bug no era puntual de Pagos: `regenerar_si_corresponde`
tiene 18 puntos de llamada (Pagos, Cargos especiales, Vacaciones/
Licencias/Ausencias, Reservas regulares, Llaves, Aumentos, Fechas
especiales) — todos con el mismo hueco, su propio docstring ya prometía
"regenerar la liquidación" para los tres casos originales (DC-08 §3.7/
§4.6/§5.4). Arreglado en el mecanismo COMPARTIDO (mismo criterio que
Shift+Enter/seleccionar todo al enfocar): ahora, además del registro,
genera el PDF nuevo con `generar_pdf_liquidacion` y actualiza
`NombreArchivo`/`FechaHoraGeneracion` — igual que ya hacía
`PantallaLiquidacion._emitir`, sin pedir ninguna confirmación (la
función ya no pedía ninguna antes tampoco). Si todavía no hay carpeta
base configurada, o el profesional no tiene código asignado, sigue sin
romper nada — se salta el PDF, igual que ya hacía
`avance_mes._regenerar_archivos_varios` en ese mismo caso.

Import de `app.pdf.liquidacion_pdf.generar_pdf_liquidacion` hecho
TARDÍO (dentro de la función, no al principio del archivo): `liquidacion_
pdf.py` ya importa `Liquidacion`/`ids_consolidados` desde este mismo
módulo (`app.negocio.liquidaciones`), así que un import a nivel de
módulo en el otro sentido sería un ciclo — mismo patrón que `avance_mes.
_regenerar_archivos_varios` usa para sus imports de `app.pdf.*`.

Tests nuevos: `tests/test_liquidaciones.py` (`regenerar_si_corresponde`
genera el PDF y actualiza `NombreArchivo` cuando hay carpeta base
configurada; sin carpeta base, sigue sin romper ni generar nada),
`tests/test_gui_pagos.py` (el caso real de la clienta: pago imputado al
mes anterior para un R, el PDF de la liquidación del mes en curso queda
en disco con el nombre nuevo).

Consulta aislada de la clienta sobre el mismo hilo (los redondeos de
los montos finales de las liquidaciones no se estarían aplicando):
investigado — el mecanismo (`Liquidacion.ajuste_redondeo`,
`Configuracion.DecimalesTotalLiquidacion`, ver sección "Liquidaciones:
redondeo del total a un peso entero" en `docs/historial/
liquidaciones.md`) seguía intacto por código y por los tests
existentes. No era un bug: la clienta tenía el parámetro en 2 decimales
en vez de 0 en esta base de prueba — al ponerlo en 0 funcionó. Cerrado
sin cambios de código.

## Registrar pagos: "Período imputado" como alternador, alerta de restablecer descuento

Pedido de la clienta sobre la solapa "Registrar pagos":

1. **"Período imputado" deja de ser texto libre** — pasa a un
   `QComboBox` (`_PanelRegistrarPago.combo_periodo`, antes
   `campo_periodo`/`QLineEdit`) con exactamente dos opciones ("Período
   actual (MM/AAAA)" / "Período anterior (MM/AAAA)", recalculadas cada
   vez contra `periodo_actual(conn)` — `_armar_combo_periodo`), que se
   alternan con la flechita arriba/abajo (comportamiento nativo de
   `QComboBox` con el foco puesto, sin código extra) — arranca siempre
   en "Período actual". Reusa el mismo patrón ya probado en "Período a
   imputar" de Reservas aisladas/extraordinarias (`combo_periodo_
   imputar`, `reservas.py`). `es_periodo_valido`/`FORMATO_PERIODO` ya no
   hacen falta para este campo (el combo no puede tener un valor
   inválido) — sigue en uso en `_DialogoModificarPago`, que no se tocó
   (texto libre sin cambios, no pedido por la clienta).
2. **Alerta "Restablecer descuentos" (cruza de tolerancia) — default a
   "Sí"** (antes "No", perder el descuento — pedido explícito de
   invertirlo) **y botones "Sí"/"No" fijos, no en inglés.** La clienta
   reportó seguir viendo "Yes" en este cartel puntual pese a que la
   traducción oficial de Qt (`qt_es.qm`) ya estaba instalada para todo
   el sistema (ver "Cuadros de diálogo del sistema" en
   `docs/historial/general.md`) — esa traducción depende de que el
   `.qm` esté disponible y cargue bien en el entorno real, nada lo
   garantiza siempre. Se resuelve con `preguntar_si_no(parent, titulo,
   texto, default_si=True)` (`app/gui/dialogos.py`, nueva, reusable si
   aparece el mismo problema en otro cartel): arma los botones a mano
   con texto "Sí"/"No" fijo, nunca depende de ninguna traducción
   externa.
3. **Alerta final "Pago registrado con éxito."** al terminar
   `_registrar()` — mismo patrón ya establecido en otras pantallas
   (`crud_generico.py`, `reservas.py`: "{Entidad} {verbo} con éxito."),
   que a esta pantalla todavía no le había llegado.

## Planes de pago: alerta final de proceso exitoso

Pedido de la clienta: *"En pagos/Planes de pago — Alerta final de
proceso exitoso"*. A diferencia de Registrar pagos (ver más arriba, ya
con su alerta), `_PanelPlanesPago` (`app/gui/pantallas/pagos.py`) no
tenía ninguna en sus tres acciones. Se agregó al final de cada una,
mismo patrón "{Entidad} {verbo} con éxito.": `_guardar` → "Plan de
pagos creado con éxito.", `_refinanciar` → "Plan refinanciado con
éxito.", `_cancelar` → "Plan cancelado con éxito." No se tocó el
cartel de confirmación de `_cancelar` (`QMessageBox.question`, mismo
riesgo de traducción al inglés ya resuelto en Registrar pagos vía
`preguntar_si_no`) — no fue parte de este pedido puntual. Tests:
`test_guardar_plan_muestra_alerta_final_de_exito`,
`test_refinanciar_plan_muestra_alerta_final_de_exito`,
`test_cancelar_plan_muestra_alerta_final_de_exito`
(`tests/test_gui_pagos.py`).

## Pagos — "Saldo total" y cascada entre saldo anterior/actual

Pedido de la clienta:

1. **Resuelto — Pagos/Registrar pagos: "Nuevo saldo" solo restaba el
   pago del período ACTUAL.** Si el pago se imputa al período anterior,
   "Nuevo saldo" (que solo mira `SaldoCuentaActual`) daba un importe
   incompleto/mentiroso — no reflejaba el saldo real a cubrir. Se agrega
   "Saldo total" (`etiqueta_saldo_total`, debajo de "Saldo período
   actual"), que suma las dos etiquetas de arriba (`SaldoCuentaAnterior
   + SaldoCuentaActual`), y "Nuevo saldo" pasa a calcularse en vivo
   sobre ESE total en vez de sobre el saldo actual a secas
   (`_actualizar_saldos`, `app/gui/pantallas/pagos.py`). Puro cambio de
   PREVIEW en pantalla — no toca todavía `registrar_pago` (ver el hilo
   del bug real de `SaldoCuentaAnterior`/`SaldoCuentaActual` más abajo,
   reportado de inmediato después de este cambio, que sí ataca el
   cálculo real). Test nuevo: `test_saldo_total_suma_anterior_y_actual_
   y_nuevo_saldo_lo_usa_de_base` (`tests/test_gui_pagos.py`).

2. **Resuelto — Pagos/Registrar pagos: un pago que cubría el saldo
   anterior Y el actual, con margen, solo descontaba del actual y
   dejaba el resto como crédito desconectado.** Bug real reportado por
   la clienta: "al cargar un importe de pago de un profesional que
   abonó el saldo del mes anterior, el actual y un poco más, me
   tendría que dejar como saldo de cuenta actual la diferencia del
   pago hecho menos los dos saldos, solo resta del saldo actual y
   carga el resto como crédito al profesional" — pedido explícito de
   que el fix impacte también los registros ya cargados, no solo los
   pagos nuevos.

   `registrar_pago` (`app/negocio/pagos.py`) imputa siempre a un solo
   campo (`SaldoCuentaAnterior` o `SaldoCuentaActual`, según
   `periodo_imputado` — "Nunca toca ambos a la vez", documentado desde
   siempre) — eso seguía intencional. El bug era que, si el pago
   alcanzaba a cubrir ese campo por completo Y TAMBIÉN el otro con
   margen, el sobrante se quedaba en el campo imputado como crédito
   (muy negativo) mientras el OTRO campo seguía mostrando una deuda ya
   cobrada en los hechos. `_aplicar_pago_con_cascada` (helper nuevo)
   agrega la cascada: solo cuando el sobrante alcanza para cubrir el
   OTRO saldo POR COMPLETO (no con que lo achique nomás), lo cancela y
   el resto queda como crédito final en el campo imputado. Ese umbral
   de "cobertura completa" (no cualquier sobrante) es clave: un pago
   que deja el campo imputado en crédito sin llegar a cubrir el otro
   saldo entero no reparte nada — es indistinguible de un pago por
   adelantado normal contra un período que todavía no tiene cargado el
   saldo real (ej. una reserva aislada recién creada, antes de pasar
   por `emitir_liquidacion`) — confirmado con una regresión real de la
   suite (`test_mensajes.test_detalle_aislada_calcula_saldo_a_abonar`)
   al probar primero con "cualquier sobrante reparte", que hubo que
   descartar por este motivo antes de subir el umbral a cobertura
   completa.

   `modificar_pago`/`eliminar_pago` ahora revierten por los deltas
   exactos que quedaron guardados en dos columnas nuevas de
   `HistorialPagos`, `ImpactoSaldoAnterior`/`ImpactoSaldoActual` (una
   de las dos en 0 si el pago no cayó en cascada) — ya no asumen que
   el pago tocó un solo campo, así que revierten bien un pago
   repartido entre los dos. Migración (`app/db/migraciones.py`): las
   filas de `HistorialPagos` ya cargadas (de antes de este fix, que
   nunca repartían) se backfillean con el mismo campo único que ya
   usaba `_campo_saldo`, para que sigan revirtiéndose exactamente igual
   que antes.

   Corrección retroactiva (lo pedido explícitamente: "que me impacte
   en los registros que ya pude haber cargado hasta el momento"):
   `reconciliar_saldos_cruzados` (`app/negocio/pagos.py`) corre sola en
   cada arranque (`app.db.init_db.init_database`, después de
   `aplicar_migraciones`) y neta, para cada profesional, un campo en
   deuda contra el otro en crédito — pero SOLO cuando el crédito
   alcanza a cubrir esa deuda por completo (mismo umbral exacto que el
   fix, para no corregir un estado que nunca estuvo roto). Deja su
   propio movimiento en `HistorialPagos` (Monto=0, EsAjuste, con el
   detalle de antes/después en Observación) para que quede visible en
   Estado de cuenta y sea reversible (Eliminar) como cualquier pago; es
   de por sí idempotente (una vez corregido un profesional ya no
   vuelve a cumplir la condición, y el fix en `registrar_pago` ya no
   vuelve a generarla).

   El cartel de confirmación de "Eliminar pago" (`app/gui/pantallas/
   pagos.py`) ahora distingue si el pago a revertir cayó en cascada
   (avisa "repartiéndolo entre el saldo del período anterior y el
   saldo actual") de uno que tocó un solo campo, en vez de asumir
   siempre un solo campo.

   Tests: `tests/test_pagos.py` (cascada en los dos sentidos, umbral de
   cobertura completa, `modificar_pago`/`eliminar_pago` con un pago
   repartido, `reconciliar_saldos_cruzados` en los dos sentidos + no-op
   si no hay cobertura completa + idempotencia, y wiring completo vía
   `init_database`), `tests/test_migraciones.py` (backfill de
   `ImpactoSaldoAnterior`/`ImpactoSaldoActual` en filas viejas +
   idempotencia), `tests/test_gui_pagos.py` (wording del cartel de
   Eliminar con cascada).

## Registrar pagos: centrado y anchos de columna

Dos pedidos explícitos de la clienta sobre la tabla de
`_PanelRegistrarPago` (`app/gui/pantallas/pagos.py`):

1. **Centrado.** "Período imputado", "Registro modificado" y "Es
   ajuste" pasan de `QTableWidgetItem` liso (alineación default a la
   izquierda) a `item_centrado` (`app/gui/widgets/items_tabla.py`,
   mismo helper que ya usan otras pantallas para esta misma excepción
   puntual — ver "Contenido de celda" en CLAUDE.md).
2. **Anchos.** "Monto", "Saldo anterior" y "Nuevo saldo" al mismo
   ancho que "Registro modificado": tras el `resizeColumnsToContents()`
   de siempre, se toma `columnWidth()` de "Registro modificado" (ya
   calculado) y se aplica a esas tres columnas con `setColumnWidth`.

Alcance acotado a esta solapa puntual (no a la tabla de "Estado de
cuenta" de `_PanelEstadoCuentaPagos`, que comparte varias de estas
columnas pero no se tocó — no fue parte del pedido).

Tests nuevos en `tests/test_gui_pagos.py`:
`test_tabla_registrar_pagos_periodo_imputado_registro_modificado_y_es_
ajuste_centrados`,
`test_tabla_registrar_pagos_monto_saldos_al_mismo_ancho_que_registro_
modificado`. Verificado visualmente con captura offscreen. Suite
completa de `test_gui_pagos.py`: 78 passed.

## Planes de pago: ancho de Profesional

Pedido explícito de la clienta: "dale mas ancho a Profesional para
aprovechar el ancho de la pantalla" en `_PanelPlanesPago`. "Profesional"
pasa a `QHeaderView.ResizeMode.Stretch` (mismo criterio que "Profesional"
en Emisión de archivos/"Archivo" en Estado de cuenta de Liquidaciones)
— se saca el piso manual `setColumnWidth(0, max(..., _ANCHO_COL_
PROFESIONAL))` de `actualizar()`, que queda sin efecto (y sin sentido)
una vez que la columna está en modo Stretch.

Test nuevo en `tests/test_gui_pagos.py`:
`test_planes_de_pago_columna_profesional_se_estira_al_ancho_de_
pantalla`. Verificado visualmente con captura offscreen. Suite completa
de `test_gui_pagos.py`: 79 passed.

## Bug real: "Saldo período actual" en $0 para un A con una aislada pendiente de pagar

Pedido de la clienta: "Estoy intentando cargar un pago de un
profesional que me hizo una reserva aislada en noviembre, ya pasó la
reserva... en la etiqueta de saldo período actual o saldo total aparece
en cero." Caso real: profesional categoría A, aislada confirmada del
10/11 por $35.434, "hoy" del sistema 13/11, sin ningún pago imputado
todavía.

Investigado antes de tocar nada (la hipótesis original de la clienta —
que las aisladas con `Fecha` ya pasada se "sacan" del cálculo — no era
la causa): ni `calcular_liquidacion`/`_aisladas_periodo`
(`app/negocio/liquidaciones.py`) ni ningún otro lugar filtra una
aislada por "¿ya pasó respecto a hoy?" — solo filtran por período
(`Fecha LIKE 'AAAA-MM-%'`). Confirmado con un escenario sintético
(misma aislada, mismo monto): con categoría R el cálculo daba el monto
correcto; con categoría A, siempre $0.

**Causa real**: `_PanelRegistrarPago._actualizar_saldos` (pagos.py) y
`partes_resumen`/`texto_resumen` (`app/gui/widgets/resumen_saldo.py`,
compartidos también por "Estado de cuenta" de Cargos especiales)
mostraban "Saldo actual" leyendo DIRECTO el campo persistido
`Profesional.SaldoCuentaActual`. Ese campo solo se acredita al emitir
una liquidación mensual (`emitir_liquidacion`,
`app/negocio/liquidaciones.py`) — y la categoría A no tiene liquidación
mensual propia (`CATEGORIAS_CON_LIQUIDACION_MENSUAL = ("R",)`), así que
ese campo queda en $0 para siempre para un A, sin importar la fecha de
la aislada ni si está pagada o no. El sistema YA calculaba bien este
número en vivo para categoría A (`saldo_actual_aislada`,
`app/negocio/mensajes.py`) — pero esa cuenta solo la usaba Centro de
mensajería, nunca se conectó a Pagos ni a Cargos especiales.

**Arreglo** (opción elegida por la clienta de las dos propuestas:
reusar el cálculo en vivo en vez de hacer que una aislada acredite el
campo persistido, como si tuviera una "liquidación" simplificada —
menos invasivo, reutiliza una cuenta ya validada):

- `saldo_actual_aislada` se separó en dos funciones
  (`app/negocio/mensajes.py`): `movimiento_periodo_aislada` (el
  movimiento de UN período solo — reservas aisladas + llaves + ítems
  libres, menos pagos imputados — sin el saldo anterior) y
  `saldo_actual_aislada` (que ahora es `saldo_anterior +
  movimiento_periodo_aislada`, sin cambiar su comportamiento externo —
  Centro de mensajería sigue llamándola igual). La separación hacía
  falta porque Pagos/Cargos especiales muestran "Saldo actual" y
  "Saldo anterior" en DOS líneas separadas (nunca sumadas), a
  diferencia de la columna "Saldo actual" de Mensajería (que sí
  muestra el total).
- `saldo_actual_mostrado(conn, profesional)`, helper nuevo en
  `resumen_saldo.py`: para categoría A, usa `movimiento_periodo_
  aislada`; para el resto, el campo persistido de siempre. Lo usan
  `partes_resumen` (Pagos y Cargos especiales) y `_actualizar_saldos`
  (Pagos, que no pasa por `partes_resumen`).

Liquidación mensual no se tocó: ahí "Saldo actual" solo se muestra para
R (único combo que ofrece esa pantalla), que siempre tuvo el campo
persistido correcto.

Tests nuevos: `test_movimiento_periodo_aislada_no_incluye_el_saldo_
anterior` (`tests/test_mensajes.py`, a nivel de negocio — confirma que
la función extraída no suma el saldo anterior y que `saldo_actual_
aislada` sigue dando lo mismo de siempre), `test_saldo_periodo_actual_
de_un_a_se_calcula_de_la_aislada_pendiente` (`tests/test_gui_pagos.py`,
reproduce el caso real reportado) y `test_estado_cuenta_cargos_saldo_
actual_de_un_a_se_calcula_de_la_aislada_pendiente` (`tests/test_gui_
novedades.py`, misma solapa compartida). Suite de los módulos tocados
(`test_mensajes.py`, `test_gui_pagos.py`, `test_gui_novedades.py`,
`test_gui_mensajeria.py`, `test_mensajeria_negocio.py`,
`test_pagos.py`): 440 passed, sin regresiones.

## Registrar pagos: saldo período actual mal para una profesional categoría R con liquidación de noviembre pendiente y una aislada ya agendada para diciembre

Cerrado — no era un bug activo, era un resabio de un bug YA arreglado.
Con el PDF real de la liquidación de noviembre de Lic. Aldana Portillo
(R2) y el detalle exacto que la clienta pasó del pago, se reconstruyó
que su `SaldoCuentaActual` de antes del pago ($220.530) era exactamente
la suma de dos cosas: el total real de noviembre ($118.731, el de la
última emisión "Enviada") más el `MontoGenerado` de una
`LiquidacionEmitida` de **diciembre** ($101.799) que había quedado
acreditada de más. Esa fila de diciembre (confirmado con la base real
que mandó la clienta, vía `IdLiquidacion`/`FechaHoraGeneracion`) se
generó el **27/10/2026 a las 10:19hs** — TRES DÍAS ANTES del commit
que agregó el guard "no acreditar una liquidación-preview de un mes
que el período operativo todavía no alcanzó" (30/10/2026, ya
documentado en una ronda anterior). O sea: se acreditó por un bug que
en ese momento todavía existía en el código, antes de que arrancara
esta ronda — el fix posterior no revierte datos que ya habían quedado
mal, solo evita que vuelva a pasar de ahí en adelante. Confirmado
buscando en toda la base si había otro caso igual: solo una fila más
de un período futuro en todo el sistema (Lic. Valeria Sambucari, R100,
también diciembre) — pero esa se generó el 4/11, YA con el fix puesto,
y no acreditó nada (su saldo coincide exacto con su última liquidación
de noviembre) — confirma que el fix funciona bien hoy. Corrección
aplicada por la clienta a mano en Profesionales > Editar
(`SaldoCuentaActual`, el único lugar editable de ese campo — `Campo
tipo="numero"` en `app.gui.pantallas.profesionales`), sin tocar
código. No hace falta ningún barrido del resto de los profesionales:
los demás saldos altos que aparecían en la base real que mandó la
clienta son correctos (cada uno coincide con su última liquidación de
noviembre).

## Pagos: "Saldo anterior"/"Nuevo saldo" de la tabla de historial (Registrar pagos y Estado de cuenta) pasan a combinar los dos períodos

Pedido explícito de la clienta, con el PDF real de la liquidación de
noviembre de Lic. Gabriela Icutza (R16) como caso de prueba: notó que
esas dos columnas, POR FILA, no "se relacionaban" entre sí al pasar de
un pago a otro — porque cada una mostraba un solo campo
(`SaldoCuentaAnterior` o `SaldoCuentaActual`, según a qué período se
imputaba ESE pago puntual), mismo problema que ya se había corregido
una vez para las etiquetas de arriba del formulario ("Saldo total"/
"Nuevo saldo", ver el comentario en `_armar_ui` de `_PanelPagos`) pero
nunca se había llevado a las columnas de la tabla. Renombradas a
"Saldo antes del pago"/"Saldo después del pago", ahora muestran el
COMBINADO (`SaldoCuentaAnterior + SaldoCuentaActual`) antes/después de
cada movimiento — comprobado matemáticamente en
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

## Pagos: las columnas de saldo se renombran a "Saldo previo"/"Nuevo saldo"

Pedido explícito de la clienta, "para simplificar", sobre las dos
columnas de la tabla de "Registrar pagos"/"Estado de cuenta" que una
ronda anterior había renombrado a "Saldo antes del pago"/"Saldo
después del pago" (ver más abajo en el historial de esta misma
sección) — el CÁLCULO combinado (`SaldoCuentaAnterior +
SaldoCuentaActual` antes/después de cada pago) no cambia, es
exactamente el mismo, solo cambia la etiqueta en las dos tablas
(`_PanelPagos`/`_PanelEstadoCuentaPagos`, `app/gui/pantallas/
pagos.py`). La etiqueta "Nuevo saldo" que ya existía ARRIBA del
formulario (la vista previa en vivo de un pago todavía no registrado,
`etiqueta_nuevo_saldo`) es una cosa aparte, de una ronda bastante
anterior, y queda con el mismo texto — coincide de nombre con la
columna nueva de la tabla pero son dos widgets sin relación, no hubo
que tocar nada ahí.

Se usó este mismo caso (Lic. Gabriela Icutza, $81.236 de saldo
anterior + $277.292 de la liquidación de noviembre, pago de $70.000)
para confirmar los números esperados: "Saldo previo" $358.528, "Nuevo
saldo" $288.528 — coincide exacto con el cálculo COMBINADO ya
implementado, sin tocar `registrar_pago`/`modificar_pago`/
`reconciliar_saldos_cruzados` (`app/negocio/pagos.py`) ni el cálculo
de liquidaciones (`calcular_liquidacion` sigue leyendo
`SaldoCuentaAnterior` en vivo, confirmado correcto por lectura de
código) — el desajuste que la clienta reportó en el saldo real de
Gabriela Icutza ($207.292 en vez de $288.528) ya estaba identificado y
cerrado en la ronda anterior como un resabio de datos (una liquidación
de diciembre acreditada de más por un bug YA arreglado antes de esta
ronda, corregida a mano por la clienta en Profesionales — ver el
bloque correspondiente más abajo) — no un bug de cálculo vigente. No
se hizo un barrido exhaustivo de la base real completa más allá de ese
caso puntual y el chequeo ya documentado de que no hay otra fila con
el mismo patrón.

## Avance de mes: el traspaso de saldo perdía lo que quedaba sin pagar del período anterior

Bug real, grave, encontrado al investigar en profundidad el pedido de
la clienta de simplificar "Saldo anterior"/"Saldo actual".
`_traspasar_saldos` (`app/negocio/avance_mes.py`) hacía
`SaldoCuentaAnterior_nuevo = SaldoCuentaActual_viejo` — REEMPLAZABA en
vez de sumar. Si un profesional terminaba el mes sin haber pagado del
todo el saldo anterior (ej. $81.236 pendientes de antes + $277.292
generados este mes), ese saldo anterior sin pagar se perdía directo al
avanzar de mes (quedaba en $277.292 en vez de $358.528) — plata que
dejaba de figurar en ningún lado sin que nadie la hubiera pagado ni
perdonado.

Arreglo quirúrgico, no una redefinición: pasa a sumar
(`SaldoCuentaAnterior_nuevo = SaldoCuentaAnterior_viejo +
SaldoCuentaActual_viejo`) — el significado de los dos campos no
cambia en ningún otro lugar del sistema (planes de pago, mensajería
automática a categoría X, las dos alertas de panel de control,
Reinicio de prueba), así que no hubo que tocar nada más. Se evaluó y
se descartó adoptar la propuesta de la clienta de redefinir "Saldo
actual" para que ya incluya el anterior (`Saldo actual = Saldo
anterior + liquidación del mes - pagos al actual`): arreglaría este
mismo bug de rebote, pero pisa el significado que usan TEXTUALMENTE
esos otros cuatro lugares — se prefirió el cambio mínimo que ataca la
causa real sin ese riesgo. Test actualizado en
`tests/test_avance_mes.py`: `test_traspaso_de_saldo_suma_el_anterior_
sin_pagar_en_vez_de_perderlo` (antes `test_traspaso_de_saldo`,
verificaba el comportamiento VIEJO/roto).

**Pendiente, a pedido de la clienta:** no hay forma barata de saber
con certeza, mirando solo el estado actual, a qué otros profesionales
les pasó esto en el pasado — no se guarda ningún historial de qué
valía `SaldoCuentaAnterior` en cada traspaso viejo (`SnapshotMensual`
solo guarda ocupación/valores de consultorio, no saldos por
profesional). Si hace falta auditar la base real, el camino es
reconstruir por profesional "cuánto debería sumar hoy el combinado" a
partir de lo que SÍ queda registrado para siempre
(`LiquidacionEmitida.MontoGenerado` de la última emisión de cada
período + todo `HistorialPagos.Monto` + los movimientos de
`PlanPago`/refinanciación) y compararlo contra el combinado real —
cualquier diferencia hacia abajo es plata perdida por este bug. No se
armó ese script todavía (hace falta la base real para correrlo y
confirmar los números contra algo verificable, igual que se hizo a
mano con Gabriela Icutza y Aldana Portillo) — queda disponible para
cuando la clienta la vuelva a mandar.

## Corrección general de "Saldo previo"/"Nuevo saldo" en filas históricas de HistorialPagos

Hecho sobre la base real que mandó la clienta. Investigando el caso de
Gabriela Icutza se vio que el problema era mucho más general: como el
cálculo combinado es de esta sesión, TODA fila de `HistorialPagos`
anterior a hoy muestra el valor viejo de un solo campo en vez del
combinado, para cualquier profesional que tuviera algo en el OTRO
campo en ese momento — no es plata perdida, es una foto vieja de una
columna que antes no existía así.

Se armó un script de reconstrucción (no forma parte del repositorio,
vive en el historial de esta sesión) que reconstruye el combinado real
de cada pago CON CERTEZA MATEMÁTICA caminando hacia atrás desde el
saldo combinado vigente HOY de cada profesional, restando el `Monto`
de cada pago uno por uno — válido únicamente mientras no haya ningún
otro evento en el medio que también mueva el saldo (una liquidación
emitida, un cambio de mes que sugiere un avance de mes, o una
corrección manual ya conocida). Sobre la base real: 123 pagos en
total — 18 ya estaban bien, 64 se corrigieron con certeza, 39 no se
tocaron (tienen una liquidación emitida en el medio y no se puede
asegurar el número sin mirar el PDF real, caso por caso, si alguna vez
hace falta) y 2 profesionales quedaron afuera a propósito: uno con un
plan de pagos activo (la refinanciación mueve plata entre campos de
una forma que esta cuenta no contempla) y Aldana Portillo (R2, ya
tiene una corrección manual documentada en el saldo que rompe la
reconstrucción retroactiva para ella). Solo se tocaron las columnas
`SaldoAnterior`/`SaldoNuevo` de `HistorialPagos` — ningún otro dato de
la base, confirmado con `PRAGMA integrity_check` y comparando la
cantidad de filas de cada tabla antes/después.

**Revertido y vuelto a aplicar, SOLO categoría R.** La clienta reportó
que la corrección de categoría A dio error — investigado: los
profesionales categoría A nunca pasan por `LiquidacionEmitida` ("solo
los profesionales categoría R tienen liquidación mensual propia",
`app.negocio.liquidaciones`), así que su saldo de arranque (antes del
primer pago registrado) no sale de ningún evento rastreable en la base
— sale de una carga manual puntual (mismo punto ciego que ya tenía
Aldana Portillo, pero generalizado a toda la categoría) que el script
no tenía forma de detectar como "riesgo" en la cadena hacia atrás. Se
corrigió filtrando la reconstrucción a `CategoriaProfesional == "R"`
únicamente, corriendo de NUEVO contra el archivo ORIGINAL que había
mandado la clienta (no sobre el ya corregido, para no encadenar un
error sobre otro) — sin esto, A (y cualquier otra categoría salvo R)
queda exactamente en el valor que tenía antes de cualquier corrección.
Resultado sobre la base real: 32 profesionales / 52 pagos corregidos
(categoría R únicamente) — confirmado por bit a bit que las filas de
categoría A quedan idénticas al archivo original sin tocar.

**Aplicado de nuevo, sobre una base más nueva que mandó la clienta.**
Mismo resultado (filtrado a categoría R, partiendo siempre del archivo
que llega SIN corregir, nunca de uno ya corregido).

**Hallazgo real distinto, en el camino — sin arreglar todavía, hace
falta definir el diseño con la clienta antes de tocar código:**
reportó que al generar el texto de detalle de una reserva aislada
(categoría A) para A1, no aparece la línea de "saldo pendiente mes
anterior" pese a que ella lleva esa diferencia en su propia cuenta.
Confirmado que NO es por nada de esta ronda (nunca se tocó
`Profesional.SaldoCuentaAnterior`, solo las columnas de display de
`HistorialPagos`) — es un hueco real y bastante más de fondo:

- Para categoría A, lo que se debe por reservas aisladas/llaves/ítems
  libres de UN período se calcula siempre EN VIVO (`app.negocio.
  mensajes.movimiento_periodo_aislada`, filtrando `ReservaAislada.
  Fecha` por ese período puntual) — nunca se acredita a ningún campo
  de `Profesional`, a diferencia de un R (que sí acredita el neto del
  mes al emitir su liquidación, ver `emitir_liquidacion`).
- `avance_mes.avanzar_mes`/`_traspasar_saldos` NUNCA llama a
  `movimiento_periodo_aislada` — confirmado buscando en todo
  `avance_mes.py`. O sea: al cerrar un mes, lo que un A debe por
  aisladas de ESE mes que se cierra nunca se traslada a
  `SaldoCuentaAnterior` para el mes que viene. El mensaje de detalle
  del mes siguiente, al calcular en vivo, solo ve LAS RESERVAS DE ESE
  NUEVO MES — las del mes anterior ya no entran en el filtro de
  fecha, y como tampoco se acreditaron a ningún lado, el sistema deja
  de poder "verlas" en cualquier cálculo futuro. Coincide exacto con
  el síntoma: `SaldoCuentaAnterior` de A1 está en `0.0` en la base
  real (confirmado), mientras la clienta sí lleva una diferencia real
  aparte.
- Esto es DISTINTO del bug de traspaso ya arreglado más arriba (ese
  perdía lo que YA estaba en `SaldoCuentaAnterior`/`SaldoCuentaActual`
  al no sumarlos; esto es que para A nunca llega a cargarse ahí en
  primer lugar, por diseño, desde siempre).
- Pendiente: definir con la clienta qué tiene que pasar en el avance
  de mes para un A con aisladas sin cobrar al cerrar el período — ¿se
  acredita automático a `SaldoCuentaAnterior` (y de ahí en más A
  empieza a comportarse como R: paga en cualquier momento, se combina
  para mostrar "Saldo total")? ¿O el flujo real es otro (ella cobra en
  el momento, nunca debería quedar pendiente, y lo que reportó es un
  caso puntual a cargar a mano)? No se tocó código todavía — es un
  cambio de fondo real sobre cómo cierra el mes esta categoría, no un
  ajuste quirúrgico como el de arriba.

Cerrado por el momento a pedido de la clienta ("Tema pagos y saldos de
profesionales A y R por el momento conforme, si retomamos te aviso.")
— el hallazgo de categoría A queda documentado acá para cuando se
retome, sin código tocado todavía.

## Registrar pagos: alerta de éxito en Modificar/Eliminar/Deshacer

"Registrar pago" ya avisaba ("Pago registrado con éxito."); las otras
tres acciones de `_PanelRegistrarPago` (`app/gui/pantallas/pagos.py`)
no avisaban nada al completarse — se suma `QMessageBox.
information(...)` incondicional al final de cada una, mismo criterio
que el resto del sistema: "Pago modificado con éxito."
(`_modificar`), "Pago eliminado con éxito." (`_eliminar`, después de
la confirmación `QMessageBox.question` ya existente) y "Último
movimiento deshecho con éxito." (`_deshacer_ultimo`, idem). "Iniciar
tanda"/"Cerrar tanda" no se tocaron: esas dos ya tienen su propio
feedback inmediato en pantalla (la etiqueta "Con tanda abierta"/"Sin
tanda abierta" se actualiza en el acto), así que un cartel ahí sería
redundante. "Restablecer descuentos" tampoco: es una sub-pregunta
dentro del flujo de "Registrar pago", que ya tiene su propia alerta
final. Tests nuevos en `tests/test_gui_pagos.py`:
`test_modificar_pago_muestra_alerta_final_de_exito`,
`test_eliminar_pago_muestra_alerta_final_de_exito`,
`test_deshacer_ultimo_movimiento_muestra_alerta_final_de_exito`.
pyflakes limpio, suite completa de `test_gui_pagos.py` sin
regresiones (86 passed).

## Pagos (Registrar pagos): doble alto de encabezado + reordenar/achicar columnas

Cuatro pedidos puntuales de la clienta sobre la tabla de
`_PanelRegistrarPago` (`app/gui/pantallas/pagos.py`):

- Encabezados de "Período imputado", "Monto", "Saldo previo", "Nuevo
  saldo" y "Registro modificado" pasan a dos líneas (`"Período\n
  imputado"`, etc.) — mismo mecanismo ya usado en Estadísticas:
  `QHeaderView` agranda solo el alto de la fila de encabezados y angosta
  la columna a lo que mide la palabra más larga, sin código extra.
- "Monto", "Saldo previo" y "Nuevo saldo" se achican un 40% respecto al
  ancho natural (`resizeColumnsToContents()`), calculado sobre la tabla
  ya con filas cargadas (el ancho natural de una tabla vacía no sirve de
  referencia).
- Reorden de columnas: "Saldo previo" y "Nuevo saldo" pasan a estar
  pegados después de "Monto" (antes del Medio de pago); el resto sigue
  en el mismo orden relativo.
- "Registro modificado" también a dos líneas, ancho mínimo.

`_PanelEstadoCuentaPagos` (la otra solapa, "Estado de cuenta") no se
tocó — el pedido fue puntual de "Registrar pagos".

Tests en `tests/test_gui_pagos.py`: `test_tabla_registrar_pagos_monto_
saldos_se_achican_un_40_por_ciento` (achicado vs. natural post-carga,
±1px de tolerancia por redondeo de Qt) y `test_tabla_registrar_pagos_
encabezados_partidos_en_dos_lineas` (alto de encabezado crece, sin
asumir un múltiplo exacto). Suite completa de `test_gui_pagos.py` sin
regresiones (87 tests).

## Pagos (Registrar pagos): ancho de Monto/Saldo previo/Nuevo saldo para que entre "$ 0.000.000,00"

Pedido explícito de la clienta, ronda siguiente a la que las achicó un
40% del ancho natural (ver más arriba, "doble alto de encabezado..."):
en vez de un porcentaje relativo al contenido real (que varía según
los importes cargados), las tres columnas pasan a un ancho FIJO
calculado para que entre exactamente el texto "$ 0.000.000,00" —medido
con `QFontMetrics` sobre la fuente real de la tabla más un colchón
chico (`_TEXTO_MONTO_MAXIMO`/`_PADDING_COLUMNA_MONTO`, `app/gui/
pantallas/pagos.py`), mismo criterio ya usado en otras pantallas para
no depender de `resizeColumnsToContents()` cuando se necesita un ancho
exacto en vez de "lo que mida el contenido actual". Test reescrito:
`test_tabla_registrar_pagos_monto_saldos_anchas_para_el_formato_
maximo` (antes comparaba contra el 60% del ancho natural). Suite de
`test_gui_pagos.py`: 87 passed.
