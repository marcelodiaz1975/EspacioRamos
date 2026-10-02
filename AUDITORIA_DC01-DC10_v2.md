# Auditoría línea por línea v2: DC-01 a DC-10 vs. código real

Fecha: 2026-10-02. Punto de partida: `AUDITORIA_DC01-DC10.md` (21-ago-2026), re-verificada hallazgo por hallazgo contra el código actual de `claude/etapa-4-obset4` — en el medio pasó toda la reorganización de formularios, la revisión "uno por uno" de pantallas y varias funcionalidades nuevas (Liquidaciones simuladas, Balance del negocio, Bordó, avisos de llaves/placas, etc.), así que varios hallazgos quedaron resueltos sin que estuvieran anotados como tales. **No se tocó código en este pase** — es relevamiento, igual que el documento anterior.

**Cómo leer esto**: mismo esquema de severidad (🔴 crítico / 🟠 importante / 🟡 moderado / ⚪ cosmético / ℹ️ ya conocido). Cada ítem conserva su número original y suma una marca de estado: **✅ RESUELTO** (confirmado en el código actual), **🔸 PARCIAL** (mejoró pero no cubre todo lo que pedía el documento), **❌ SIGUE** (confirmado que el hallazgo sigue vigente), **♻️ OBSOLETO** (el concepto que describía ya no existe, lo reemplazó otra cosa), o **❔ SIN RE-VERIFICAR** (no se revisó en este pase, se arrastra del documento anterior tal cual).

---

## 🔴 Hallazgos críticos (afectan el monto que se le cobra a un profesional)

1. **DC-01 §1.2** — ✅ **RESUELTO**. `liquidacion_pdf.py:_armar_items` (`multi_tramo`) desglosa explícitamente bruto y descuento de CADA tramo por separado cuando cambian las horas semanales a mitad de mes, con el rango de fechas de cada uno en el concepto. Confirmado leyendo el código real, no solo el docstring.
2. **DC-01 §1.6** — ✅ **RESUELTO**. `RecargoPorcentajeAisladas` se siembra en `0` (`app/db/seed.py`), no en 10% como decía la auditoría vieja.
3. **DC-01 §1.3** — ✅ **RESUELTO**. `liquidaciones.py` lee `PorcentajeDescuentoFeriado`/`PorcentajeDescuentoNoLaborable` de `Configuracion` (dos parámetros independientes, con fallback a 100 solo si faltara la fila) — y están expuestos en Configuración general → Valores y liquidación (captura ya enviada).
4. **DC-09 §6** — ✅ **RESUELTO**. `_aisladas_periodo` (`liquidaciones.py:723`) chequea `f["EsReubicacion"]` y la excluye del cobro. Salió a la luz y se corrigió de rebote al armar `monto_neto_aislada_periodo` para Estadísticas, que necesitaba replicar exactamente esta función.
5. **DC-05 §2.1/§2.2** — ✅ **RESUELTO**. `crear_licencia`/`_profesional_tiene_derecho` valida categoría R/B/E **y** reserva regular activa antes de aceptar la licencia. `porcentaje_bonificacion` es un parámetro editable caso por caso (`spin_porcentaje` en la GUI, precarga el default del tipo pero se puede pisar) — sí existe la "edición de porcentaje caso por caso" que la auditoría vieja daba por ausente. `EsManual` sigue controlando otra cosa (si hace falta tipear FechaHasta a mano), eso no cambió, pero no es el bug que se había anotado.

**Los 5 hallazgos críticos de la auditoría anterior están resueltos.** No encontré ningún 🔴 nuevo en lo que revisé.

## 🟠 Hallazgos importantes (funcionalidad documentada, ausente o desconectada)

6. **DC-06 §1** — ✅ **RESUELTO**. No quedó ninguna restricción de fecha sobre "Avanzar de mes": el botón está siempre habilitado, sin ningún `puede_avanzar_mes`/chequeo de día del mes en el código actual.
7. **DC-06 §3 completa** — ❌ **SIGUE**. Repetí la búsqueda (alerta permanente, pregunta "¿esta reserva es de mes anterior o nuevo?", ajuste retroactivo) y no encontré rastro de esto en `avance_mes.py` ni en las pantallas de reservas/pagos. Sigue sin implementar.
8. **DC-06 §5.2** — ✅ **RESUELTO**. `pagos.py:_preguntar_restablecer_descuento` existe, con la pregunta textual "¿Querés restablecerle el descuento por cantidad de horas semanales reservadas...", disparada cuando `registrar_pago` devuelve `cruza_tolerancia=True`.
9. **DC-08 §3.7/§4.6/§5.4** — ✅ **RESUELTO**. `regenerar_si_corresponde` ahora se llama desde `reservas.py`, `novedades.py` (vacaciones/ausencias) y `pagos.py` — los tres puntos que la auditoría vieja señalaba como huérfanos.
10. **DC-08 §5.3** — ✅ **RESUELTO**. La tanda de sobres está implementada en Pagos (`abrir_tanda_sobres`/`cerrar_tanda_sobres`/`tanda_sobres_abierta`, subtotal en vivo, campo de fecha/hora de recogida con selector — y encima ese mismo valor se reusa ahora en el mensaje de Bordó del Centro de mensajería).
11. **DC-09 §3.6** — ✅ **RESUELTO**. `pagos.py` importa y llama `refinanciar_plan` — ya no es solo una función de negocio sin consumidor.
12. **DC-10 §2.2 paso 5** — 🔸 **PARCIAL**. `reservas.py` importa `marcar_resuelto` y lo ofrece al confirmar una reserva regular que cubre un pedido de Lista de espera — pero con una pregunta de confirmación ("¿Lo marcás como resuelto?"), no en automático silencioso como describe el documento. Es una diferencia de criterio UX (no silenciar un cambio de estado), no una ausencia total como decía la auditoría vieja.
13. **DC-03 Mensaje 2, Variante B** — ❔ **SIN RE-VERIFICAR** (no encontré evidencia de que se haya sumado disponibilidad por fecha puntual para aisladas; lo dejo como estaba, no until profundizar más).
14. **DC-02/DC-03/DC-04** — ✅ **RESUELTO**. `reservas.py:_copiar_mensaje_detalle`, con el comentario explícito "confirmar, cancelar o modificar una reserva aislada carga sola el mensaje de detalle al portapapeles" — exactamente lo que pedían los tres documentos.
15. **DC-04 §2.2/§4.3** — ✅ **RESUELTO**. `crear_reserva_aislada` NO llama `verificar_bloques_rigidos` (docstring: "Las reservas aisladas no tienen ninguna restricción de bloques rígidos, confirmado por el usuario"), y `cancelar_reserva_aislada` nunca bloquea (docstring: "nunca bloquea, ni siquiera si el horario cae dentro de un bloque rígido").
16. **DC-04 §3.2/§3.3** — 🔸 **PARCIAL**. Vacaciones y Licencias ahora SÍ cruzan contra aisladas confirmadas, pero solo en el sentido "anular una vacación/licencia ya cargada" (`aisladas_bloqueadas_por_anulacion`, bloquea si eso haría chocar una aislada ya asignada). No encontré el cruce en el sentido "cargar una vacación nueva avisa/bloquea si ya hay una aislada de otro profesional en ese horario" — ese costado sigue sin validación explícita.
17. **DC-05 §1.1/§2.1** — 🔸 **PARCIAL** / posible decisión consciente, no bug. `grilla.py` dice explícitamente "Vacaciones y ausencias NO afectan esta grilla (así lo indica el documento)" — contradice en apariencia el hallazgo viejo, pero puede ser que se esté hablando de dos cosas distintas (la grilla de referencia visual vs. la disponibilidad real para reservar una aislada). Vale la pena confirmar con vos antes de tocar nada acá — no quiero asumir que está resuelto sin estar seguro.
18. **DC-07 §3.3** — ℹ️ Sin cambios, sigue siendo una decisión documentada en el propio código (declarado intencional), no un bug.

## 🟡 Hallazgos moderados (UI/UX incompleta)

19. **F16** — ✅ **RESUELTO**. Reservas regulares tiene checkboxes múltiples L-M-X-J-V-S (grilla de 2 columnas), vista previa de grilla embebida (`GrillaOperativaWidget`) y resumen de horas semanales/% de descuento en tiempo real (`_actualizar_resumen_profesional`) — toda la revisión "uno por uno" de Reservas giró en torno a esto.
20. **F19 (vacaciones)** — ❌ **SIGUE**. No encontré ningún filtro de profesional por categoría/reserva activa, ni campo Observación, ni cálculo en vivo al elegir fechas en el panel de Vacaciones. La revisión de esta pantalla se centró en sacar "Deshacer último movimiento" y sumar la solapa de Tipos de licencia, no en estos puntos.
21. **F24 (grilla operativa)** — 🔸 **PARCIAL, mejoró bastante**. SÍ hay interacción de clic en celdas (`_CeldaGrilla.mousePressEvent` → `_mostrar_detalle`, muestra el detalle de lo ocupado) y SÍ hay filtro de Unidad (`_filtro_unidad`) — los dos huecos más grandes del hallazgo viejo. Sigue sin "alta rápida de aislada en celda libre" (el clic solo muestra detalle, no abre un alta), y la solapa "Grilla semanal" en sí (dentro de "Grilla y mensajería") no tiene botón de generar PDF ni acceso directo a Lista de espera — esas dos acciones viven en Disponibilidad/Oferta, pantallas distintas.
22. **F12 (lista de espera)** — ❔ **SIN RE-VERIFICAR**.
23. **DC-09 §11** — ❌ **SIGUE**. Conté 17 `ayuda=` armadas a mano en `gui_main.py`, sin ninguna tabla ni pantalla de edición en la base.
24. **DC-09 §9** — 🔸 **PARCIAL**. `mensajes_predefinidos.py` ya tiene vínculo a Profesional ("Dirigido a", selector buscable) y fallback `{apodo}` — los dos huecos más importantes del hallazgo viejo. No confirmé si hay una lista explícita de variables disponibles al editar (hay al menos un texto de ayuda contextual mencionando `{apodo}`), habría que mirarlo con más detalle si te interesa.
25. **DC-09 §7** — ✅ **RESUELTO**. `app/negocio/balance.py` (`total_gastos_periodo`/`resultado_periodo`) calcula Resultado = Ingresos − Gastos en vivo — la solapa "Resultado" de Balance del negocio es exactamente el "resultado neto" que pedía el documento, aunque no viva dentro de Estadísticas como se imaginaba originalmente sino en su propio formulario.
26. **DC-06 §6** — ❔ **SIN RE-VERIFICAR**.
27. **DC-02 §2.5** — ♻️ **OBSOLETO**. Reemplazamos por completo la reactivación a rojo por el color Bordó, con su propio parámetro expuesto (default 5, el mismo valor del documento original aunque por otro mecanismo) — el hallazgo ya no aplica a nada que exista en el código.
28. **DC-06 §2 Paso 6** — ✅ **RESUELTO**. `panel_control._avanzar_mes` muestra la cantidad de pedidos vencidos y pregunta explícitamente "¿Confirmás eliminarlos ahora?", con "No" dejándolos un tiempo más — exactamente lo que pedía el documento.
29. **DC-06 §2 Paso 9** — ❌ **SIGUE**. `avanzar_mes` sigue generando el snapshot como segundo paso (justo después del backup), no al final.
30. **DC-10 §1.2** — ❌ **SIGUE**. No encontré resaltado de valores editados a mano, botón "Restablecer" por fila, ni cambio en el timing del aviso de liquidaciones a regenerar.
31. **DC-07 §2.5** — ❌ **SIGUE**. `grilla_pdf.py` no menciona `DiasVisualizacion`/`DiasLogica` en ningún lado — sigue clasificando bloques rígidos solo por horario.
32. **DC-07 §6** — ❌ **SIGUE** (al menos el punto de "Apto camilla"). `oferta_pdf.py` sigue llamando con `mostrar_apto_camilla=True`. No re-revisé la estructura completa de secciones ni la posición del valor bajo cada foto.

## ⚪ Hallazgos cosméticos (texto/formato)

33. ❌ **SIGUE**. Confirmé en el código: "Saldo de la liquidación anterior" se agrega siempre, sin importar si es $0 — no se omite.
34–46. ❔ **SIN RE-VERIFICAR** — no entré a este nivel de detalle en este pase; los arrastro tal cual del documento anterior. Si querés que los chequee antes de definir prioridades, lo hago, pero dado el tamaño de la lista preferí primero cerrar los 🔴/🟠 que son los que de verdad importan.

## ℹ️ Ya conocidos (sin cambios)

Las seis aclaraciones de la auditoría anterior siguen vigentes tal cual — no son bugs, son decisiones ya confirmadas en conversación.

---

## Resumen numérico

De los 32 hallazgos 🔴/🟠/🟡 que re-verifiqué (1 al 32): **15 resueltos**, **4 parciales**, **8 siguen vigentes**, **1 obsoleto**, **4 sin re-verificar**. De los 14 ⚪ cosméticos: 1 confirmado vigente, 13 sin re-verificar.

## Lo que de verdad queda pendiente (con evidencia fresca)

- 🟠 **#7** — DC-06 §3, la sección completa de "operaciones en el mes anterior tras avanzar" nunca se construyó.
- 🟠 **#16/#17** — el cruce aislada↔ausencia/vacaciones/licencia solo cubre un sentido (anular), no el otro (cargar una nueva). **#17 necesita tu confirmación** antes de tocar nada — puede que "la grilla no se ve afectada" y "la disponibilidad real sí" sean dos cosas distintas, no quiero asumir.
- 🟡 **#20** — Vacaciones (F19) sigue sin filtro de profesional/categoría, sin Observación, sin cálculo en vivo.
- 🟡 **#21** — Grilla operativa: falta alta rápida de aislada desde una celda libre, y accesos directos a PDF/Lista de espera desde "Grilla semanal".
- 🟡 **#23** — Ayuda F1 sigue sin ser editable desde la base.
- 🟡 **#29/#30/#31/#32** — snapshot como paso 2 en vez de último, aumentos sin resaltado/restablecer por fila, grilla PDF ignora días, Oferta PDF con "Apto camilla" de más.
- ⚪ **#33** — "Saldo de la liquidación anterior" no se omite en $0.
- ❔ Todo lo marcado "sin re-verificar" (#13, #22, #26, #34-46) — candidatos para un próximo pase si querés cerrar el documento del todo.

**No toqué código.** Decime por dónde arrancamos.
