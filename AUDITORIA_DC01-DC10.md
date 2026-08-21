# Auditoría línea por línea: DC-01 a DC-10 vs. código real

Fecha: 2026-08-21. Alcance: comparación de los 10 documentos complementarios de diseño contra la implementación actual en `claude/etapa-4-obset4`. No se tocó código todavía — este documento es solo el relevamiento, para decidir juntos qué corregir y en qué orden.

**Cómo leer esto**: cada hallazgo está clasificado como 🔴 crítico (afecta montos que se cobran), 🟠 importante (funcionalidad documentada que falta o está desconectada), 🟡 moderado (UI/UX incompleta respecto del documento), o ⚪ cosmético (texto/formato). Los marcados **ℹ️ ya conocido** son casos donde el código sigue una corrección posterior confirmada en conversación — no son bugs, se listan solo para que quede constancia de por qué difieren del documento. Todo lo demás es candidato a corregir, pero **no se tocó nada todavía** a la espera de que definas prioridades.

---

## 🔴 Hallazgos críticos (afectan el monto que se le cobra a un profesional)

1. **DC-01 §1.2** — Cuando un profesional cambia de horas semanales a mitad de mes (dos tramos con % de descuento distinto), el PDF **nunca** desglosa en dos líneas de bruto/descuento como exige DC-01 §1.10 ítems 1-4. Muestra una sola línea con el % del *primer* tramo únicamente (`liquidaciones.py:754-756`, `liquidacion_pdf.py:244-249`). El total cobrado es correcto, pero el desglose que ve el profesional no.
2. **DC-01 §1.6** — El recargo de aisladas está sembrado en **10%** (`app/db/seed.py:294`), no en 0% como dice el documento ("hoy el recargo está en 0%"). Esto cobra de más desde el primer uso del sistema a cualquier profesional con `AplicaRecargo=1`.
3. **DC-01 §1.3** — El porcentaje de descuento por feriado/día no laborable está **hardcodeado al 100%** (`app/negocio/feriados.py:15`), sin los dos parámetros independientes que pide Configuracion. Hoy da lo mismo numéricamente, pero no es configurable como debería.
4. **DC-09 §6** — El campo `EsReubicacion` de `ReservaAislada` (aislada que compensa una ausencia, "no genera cargo") se puede guardar pero **nunca se lee** en ningún cálculo. `_aisladas_periodo` (`liquidaciones.py:645-672`) cobra la reubicación igual que cualquier aislada normal.
5. **DC-05 §2.1/§2.2** — `crear_licencia` no valida que el profesional tenga categoría R/B/E con reserva activa (cualquiera puede tener una licencia registrada), y el campo `EsManual` no controla el porcentaje editable como describe el documento — controla otra cosa (si la fecha de fin es manual). La "edición de porcentaje caso por caso" que promete DC-05 no existe en ningún lado.

## 🟠 Hallazgos importantes (funcionalidad documentada, ausente o desconectada)

6. **DC-06 §1** — El botón "Avanzar de mes" está **restringido al último o primer día del mes** (`puede_avanzar_mes`, `panel_control.py:40-45`, con test dedicado), cuando el documento pide explícitamente que esté disponible en cualquier momento. Esto bloquea de raíz el caso de uso "avanzar 3-4 días antes por vacaciones del administrador".
7. **DC-06 §3 completa** — Toda la sección "operaciones en el mes anterior después de avanzar" (alerta permanente, pregunta "¿esta reserva es de {mes anterior} o {mes nuevo}?", ajuste de saldo/snapshot retroactivo) **no está implementada en absoluto**. Confirmado por búsqueda exhaustiva sin resultados.
8. **DC-06 §5.2** — La pregunta interactiva "¿Querés reestablecerle los descuentos?" (con dos ramas Sí/No) **no existe en ningún lado**. No es solo que se movió el timing del ajuste (eso sí es una corrección conocida, ver más abajo) — la funcionalidad de decisión del operador se perdió por completo.
9. **DC-08 §3.7 / §4.6 / §5.4** (patrón repetido en 3 formularios distintos) — Ninguna de las siguientes acciones dispara regeneración automática de liquidación ni la marca "pendiente de envío": cargar/modificar/dar de baja una reserva regular (F16), registrar vacaciones (F19), registrar un pago imputado a mes anterior (F21). Todo el ciclo de regeneración quedó centralizado a mano en F22. Vale confirmar si esto fue una decisión de diseño consciente.
10. **DC-08 §5.3** — La "tanda de sobres" (botones Iniciar/Cerrar tanda, subtotal en vivo para cuadrar con el efectivo físico) **no está implementada**. Ni siquiera existe una UI para el campo simple de §5.2 (`FechaHoraRecogidaSobres`) — solo se puede setear escribiendo directo en la base.
11. **DC-09 §3.6** — El formulario de refinanciación de plan de pagos (`refinanciar_plan`) está implementado y testeado en el negocio, pero **la pantalla real no lo usa** — solo permite crear un plan nuevo, que falla si ya hay uno activo, sin ofrecer cancelar/refinanciar desde la UI. Es la brecha funcional más grande de DC-09.
12. **DC-10 §2.2 paso 5** — Confirmar una reserva regular en F16 **no marca automáticamente** el pedido de Lista de espera correspondiente como Resuelto. Son dos acciones manuales sin ninguna conexión en el código.
13. **DC-03 Mensaje 2, Variante B** — La disponibilidad para reservas aisladas por **fecha puntual** (en vez de día de la semana genérico) no está implementada; solo existe la Variante A.
14. **DC-02/DC-03/DC-04** (mismo hallazgo confirmado por 3 auditores distintos) — El mensaje de detalle de aisladas **no se genera ni se copia automáticamente al portapapeles** al confirmar una reserva aislada nueva desde el formulario. Solo se genera a mano desde el Centro de mensajería.
15. **DC-04 §2.2/§4.3** — Las reservas aisladas reciben advertencia de bloque rígido al crearse, y su **cancelación el mismo día se bloquea** si cae dentro de un bloque rígido — el documento exige que las aisladas no tengan ninguna restricción de bloques rígidos y que la cancelación nunca se bloquee.
16. **DC-04 §3.2/§3.3** — No hay ninguna validación cruzada de ausencia/vacaciones contra aisladas ya confirmadas (en ningún sentido): se puede registrar una ausencia o una vacación sin aviso ni bloqueo aunque exista una aislada confirmada de otro profesional en ese horario.
17. **DC-05 §1.1/§2.1** — Registrar vacaciones o licencias no libera el consultorio para aisladas de otro profesional (solo `Ausencia` está conectada a `verificar_conflictos_aislada`), pese a que el documento lo cita como el propósito operativo del registro para categoría B.
18. **DC-07 §3.3** — El PDF de Propuesta le faltan 2 de las 7 secciones documentadas: no tiene "Condiciones y normas generales" (los 21 puntos) ni "Esquema de descuentos" como sección independiente — está declarado intencional en el propio docstring del archivo, pero contradice el documento.

## 🟡 Hallazgos moderados (UI/UX incompleta)

19. F16 (reserva regular): carga un día a la vez (combo simple) en vez de checkboxes múltiples L-M-X-J-V-S-D; sin vista previa de grilla antes de confirmar; sin resumen de horas semanales/% de descuento en tiempo real.
20. F19 (vacaciones): el combo de profesional no filtra por categoría/reserva activa (solo valida al confirmar); sin campo Observación (ni en schema ni en UI); sin ningún cálculo en tiempo real mientras se eligen fechas — todo se ve recién después de guardar.
21. F24 (grilla operativa): sin interacción de clic en celdas (ni detalle de ocupado ni alta rápida de aislada en celda libre); sin botón de generar PDF ni acceso directo a Lista de espera desde la pantalla; sin filtro de Unidad ni de hora desde/hasta.
22. F12 (lista de espera): sin vista de detalle de qué consultorio(s) específicos cubren un pedido resaltado; sin atajo para iniciar F16 pre-completado desde ahí.
23. DC-09 §11 — La ayuda contextual F1 funciona y es contextual, pero **no es editable sin tocar código**: los ~28 textos están hardcodeados en `gui_main.py`, sin tabla en la base ni pantalla de edición, contradiciendo el requisito explícito del documento.
24. DC-09 §9 — `MensajePredefinido` solo soporta variables de edificio/unidad/consultorio; no tiene vínculo a Profesional, no hay fallback tipo `{Apodo}→NombrePila→...`, y no se ofrece ninguna lista de variables al editar.
25. DC-09 §7 — `GastoOperativo` es efectivamente una tabla de solo-escritura: nunca se usa para calcular ningún "resultado neto" en Estadísticas, y el texto "Resultado neto no disponible — faltan datos de gastos" no existe en ningún lado.
26. DC-06 §6 — No existe el tipo de snapshot "de operación importante" (antes de aumentos o desactivación de edificio/unidad), ni función para eliminar snapshots antiguos con sus reglas de retención, ni exportación a Excel desde Estadísticas.
27. DC-02 §2.5 — El default de "días antes de fin de mes" para reactivar rojo es **5**, no 7 como dice el documento, y el parámetro no está expuesto en la pantalla de Configuración pese a existir en la base.
28. DC-06 §2 Paso 6 — La limpieza de lista de espera en el avance de mes nunca muestra el resumen previo ni ofrece las opciones "conservar un mes más / confirmar eliminación" — el parámetro correspondiente nunca se pasa desde la GUI, así que los registros vencidos jamás se limpian en la práctica.
29. DC-06 §2 Paso 9 — El snapshot definitivo se genera como *segundo* paso del proceso (justo después del backup), no al final como exige el documento. Impacto práctico bajo, pero contradice el orden explícito.
30. DC-10 §1.2 — Al análisis de aumentos le falta: resaltado visual de valores editados a mano vs. calculados por %; botón "Restablecer" por fila individual; y el aviso de cuántas liquidaciones se van a regenerar aparece *después* de confirmar, no antes.
31. DC-07 §2.5 — La grilla PDF ignora `DiasVisualizacion`/`DiasLogica`: clasifica bloques rígidos solo por horario, sin distinguir por día, aunque el módulo de reservas sí tiene la función correcta (simplemente no la usa el generador de PDF).
32. DC-07 §6 (Oferta de consultorios) — Estructura de secciones distinta a la documentada; muestra "✔ Apto camilla" cuando el documento pide que no lo haga; el valor no queda debajo de cada foto sino aparte.

## ⚪ Hallazgos cosméticos (texto/formato, no cambian montos ni bloqueos)

33. "Saldo de la liquidación anterior" se muestra igual aunque sea $0 (debería omitirse) — y está congelado así en un test.
34. Texto "Saldo a favor..." trae "del profesional" de más.
35. Texto de feriado pendiente distinto ("Descuento feriado pendiente" vs "Descuento por feriado mes anterior").
36. Texto de ajuste por saldo atrasado sin el sufijo "— período {mes anterior}".
37. Texto de cuota sin "/Total" (dice "Cuota 3 del plan de pagos" en vez de "Cuota 3/12...").
38. El edificio se menciona siempre en varias líneas de detalle/placas, no solo cuando el profesional tiene más de un edificio (afecta horas agregadas, feriados trabajados, placas, y el pie de foto de Oferta).
39. Nombres de archivo de Propuesta, Disponibilidad y Liquidación no siguen el patrón textual exacto del documento (orden de palabras, falta de fecha en Disponibilidad, falta "mensual" en Liquidación) — sí son internamente consistentes y están testeados.
40. La etiqueta de período de valores nunca usa el conector "al" para 3+ meses — siempre usa "y", y el mecanismo de cálculo del rango es distinto al descrito (usa vigencia de aumentos, no lista literal de meses configurados).
41. Localidad en encabezado de PDF sin los guiones "- Localidad -" (aparece solo el nombre).
42. Cargos especiales manuales (bonificación/ajuste/depósito llave/ítem libre) quedan agrupados en 2 posiciones de la cuenta en vez de las 4 posiciones distintas que pide DC-01 §1.10 — mencionado ya por el usuario en el pedido original de la tarea #73/74, ya resuelto parcialmente esta sesión.
43. Punto final faltante en la aclaración de edificios del Mensaje 1 ("Corresponde a X, Y" sin el punto).
44. Defaults de "Combinar consultorios misma/distinta unidad" vienen destildados, el documento pide tildados por defecto.
45. Reserva aislada que cruza medianoche: no se parte en dos líneas como pide el documento, y el formulario ni siquiera permite cargar ese caso como registro único.
46. Varias diferencias de viñetas/formato en el Mensaje 2 Variante A (título sin viñetas, "·" y "-" invertidos respecto del documento, "combinación de consultorios" sin frase explícita).

## ℹ️ Ya conocidos — decisiones posteriores confirmadas, no son bugs

- El ajuste por saldo atrasado se evalúa en vivo en cada liquidación en vez de una sola vez en el avance de mes (DC-01 §1.9 / DC-06 §5.2) — corrección documentada en el propio código.
- El orden dentro de cada color del Centro de mensajería es por código **descendente**, no ascendente (DC-02 §2.1, DC-06 §4.3) — confirmado por vos en esta conversación.
- Regla del edificio: sin llaves + más de un edificio en el espacio → se incluye el edificio en el texto (DC-03) — corrección confirmada por vos esta sesión.
- Se sacaron los checkboxes "incluir consultorio/unidad/edificio" del Mensaje 1 en el Centro de mensajería (ahora se decide solo por las llaves) — pedido tuyo esta sesión.
- Feriado trabajado sí lleva descuento por horas semanales, contradiciendo la letra de DC-01 §1.5 — el propio código cita una corrección de conversación anterior a esta sesión.
- Lista de espera con múltiples bloques día+horario combinados Y/O — evolución de esta sesión, compatible con (y más rica que) lo que pedían DC-08/DC-10.

---

## Cómo seguimos

No toqué nada de código todavía. Si me confirmás prioridades puedo ir corrigiendo en tandas — sugiero empezar por los 5 hallazgos 🔴 críticos (afectan plata real) y después seguir por importancia, pero es tu decisión. Avisame también si alguno de los puntos marcados como discrepancia en realidad corresponde a otra decisión que tomamos en el camino y no quedó reflejada acá — antes de tocar nada te lo confirmo.
