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

