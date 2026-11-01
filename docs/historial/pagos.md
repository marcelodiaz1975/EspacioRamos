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
