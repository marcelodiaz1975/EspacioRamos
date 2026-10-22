# Historial archivado — Valores: Valores vigentes, Aumentos, Esquema de descuentos

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

## Valores: se saca "Deshacer último movimiento" de la solapa "Aumentos"

Pedido explícito de la clienta, mismo criterio ya aplicado en Llaves/
Reservas/Registro de ausencias/Cargos especiales/Centro de mensajería:
se borra el botón, su conexión (`clicked.connect(self._deshacer_ultimo)`)
y el método `_deshacer_ultimo` de `_PanelAumentos` (`app/gui/pantallas/
aumentos.py`), además de sacarlo de la cadena de foco Enter/Tab (pasa de
terminar en Simular→Confirmar→Editar porcentaje diferencial→Deshacer a
la misma cadena sin el último paso).

Distinto de los casos anteriores: acá `app.negocio.aumentos.
deshacer_ultimo_aumento` (la función que revierte valores de
consultorio/esquema de descuentos/liquidaciones regeneradas) NO se
borra — a diferencia de los helpers puramente de soporte de Llaves/
Reservas (que solo existían para alimentar el botón), esta es una
función de negocio completa, con su propia batería de tests dedicada
(`tests/test_aumentos.py`) independiente de la GUI; se deja intacta por
si hace falta usarla desde otro lado más adelante (soporte, un futuro
botón en otra pantalla, etc.), aunque hoy quede sin ningún consumidor
en la GUI. Solo se borran los dos tests GUI-side que ejercían el botón
en `test_gui_aumentos.py` (`test_deshacer_ultimo_movimiento_revierte`/
`test_deshacer_sin_movimientos_no_falla`) — los cuatro tests de negocio
de `deshacer_ultimo_aumento` en `test_aumentos.py` no se tocan.

## Valores vigentes: columnas sin scroll horizontal, Localidad/Edificio
## más anchas en Promedios

Tres pedidos de la clienta sobre la solapa "Valores vigentes" (de
"Valores"), revisada al mandarle la captura a pantalla completa:

- **Las dos tablas, sin scroll horizontal.** "Valores vigentes por
  horas regulares y aisladas" (`tabla_valores`, 6 columnas) quedaba con
  barra de scroll horizontal en un panel más angosto que el de otras
  pantallas — sus columnas usaban el `ResizeToContents` default de
  `_armar_tabla` (compartido con `_PanelPromedios`, ver abajo), que
  dimensiona cada columna a su contenido sin importar cuánto ancho haya
  disponible en el `GroupBox` que la contiene. Localidad/Edificio/
  Unidad/Consultorio se quedan en ese modo (contenido corto, no
  necesitan más); "Valor hora regular"/"Valor hora aislada" — las dos
  columnas que de ese modo quedaban más angostas que su propio título —
  pasan a `Stretch`, mismo criterio que "Totales por bloques" de
  Liquidaciones simuladas (columnas cortas a su ancho justo, las
  últimas en Stretch). Para que las dos en Stretch tuvieran lugar de
  sobra se acortó además su título ("Valor hora regular"/"...aislada" →
  "Valor regular"/"Valor aislada" — "hora" ya está en el título del
  `GroupBox` que las contiene, de sobra repetirlo en la columna, mismo
  criterio de acortar títulos largos que ya se usó en otras pantallas).
- **"Promedios de valor hora regular y aislada": Localidad/Edificio más
  anchas, sin espacio en blanco al final.** Esta tabla (`_PanelPromedios`,
  un `QGroupBox` con ancho fijo 720-780 sin relación con el contenido
  real) dejaba un hueco en blanco después de la última columna —
  `_ajustar_ancho` (nuevo) calcula el ancho de la TABLA (no ya del
  `GroupBox`, que se achica solo alrededor) como la suma real de sus 5
  columnas, sacando el rango fijo de siempre. Localidad/Edificio
  (columnas 0/1) pasan de `ResizeToContents` a `Interactive` para poder
  sumarles `_PADDING_COLUMNA_PROMEDIOS = 20` sobre su ancho justo (mismo
  mecanismo que "Día" en Liquidaciones simuladas: `resizeColumnToContents`
  + `setColumnWidth(... + padding)`, que solo pega en una columna que no
  siga en `ResizeToContents` continuo). Un colchón de 2px sobre la suma
  de columnas absorbe un residuo de redondeo de Qt entre el ancho
  "lógico" seteado por columna y el pixel real que termina pidiendo el
  viewport — sin él, quedaba un scroll horizontal de 1px.

**Bug real encontrado al revisar esto contra la pantalla completa, no
solo el panel suelto** (confirmado con captura — el panel aislado en un
test daba bien, la pantalla completa no): `_PanelPromedios` arma y
puebla su tabla durante `__init__` de `_PanelValoresVigentes` (el
`on_cambiar` que dispara `_PanelFiltrosJerarquico` al construirse, ver
el comentario ya existente sobre ese orden), momento en el que el
widget todavía es huérfano — no cuelga todavía del árbol de
`VentanaPrincipal`, que recién arma cada `Seccion` DESPUÉS de haberse
aplicado a SÍ MISMA (no a la `QApplication`) el `setStyleSheet` de
`hoja_estilos()`. Con la fuente default de Qt (sin el bold/14px real de
los encabezados de `estilos.py`), `_ajustar_ancho` calculaba anchos más
angostos que los que hacen falta una vez que el panel cuelga de verdad
de la ventana y hereda el estilo real — mismo motivo, ya documentado en
Reservas, por el que un `sizeHint` calculado durante la construcción no
siempre es el definitivo. Se corrige con un `showEvent` en
`_PanelPromedios` que vuelve a llamar `_ajustar_ancho()` al mostrarse de
verdad. Test de regresión
(`test_valores_vigentes_sin_scroll_horizontal_con_estilo_real_aplicado`)
replica el bug real aplicando `hoja_estilos()` al panel DESPUÉS de
construirlo (mismo mecanismo que ya usan varios tests de Reservas) en
vez de a toda la `QApplication` — necesario para que la medición
"antes de estilar" ocurra de verdad.

Tests nuevos en `tests/test_gui_valores.py`:
`test_promedios_localidad_y_edificio_mas_anchas_que_sin_padding`,
`test_promedios_sin_espacio_en_blanco_tras_la_ultima_columna`,
`test_valores_vigentes_sin_scroll_horizontal_con_estilo_real_aplicado`.

## DC-10 §1.2: valores a mano, resaltado, botón Restablecer y aviso de
## liquidaciones antes de confirmar (solapa "Aumentos")

Siguiente punto de la auditoría DC-01/DC-10 (hallazgo #30): "Al análisis
de aumentos le falta: resaltado visual de valores editados a mano vs.
calculados por %; botón 'Restablecer' por fila individual; y el aviso de
cuántas liquidaciones se van a regenerar aparece DESPUÉS de confirmar,
no antes." Los tres huecos eran reales — confirmado leyendo el código:
`app.negocio.aumentos.simular_aumento`/`confirmar_aumento` ya tenían
soporte completo para un override de valor final en $ por consultorio
(`valores_override`, "más específico todavía" que el % diferencial, ver
su propio docstring) desde que se armó esa pantalla, pero la GUI nunca
había expuesto ningún control para cargarlo — solo el % diferencial.

- **"Editar valores manuales"** (botón hermano de "Editar porcentaje
  diferencial", mismo criterio checkable): habilita a mano, en $, las
  columnas "Regular nuevo"/"Aislada nuevo" — hasta ahora siempre de solo
  lectura. Mismo criterio "un solo tipo de override por fila" que ya
  regía entre % general/diferencial ("nunca se muestran los dos
  juntos"): fijar un valor a mano en una fila limpia el % diferencial de
  esa fila y viceversa, en vez de dejar un estado ambiguo con los dos
  override activos a la vez.
- **Resaltado amarillo** (`COLOR_AMARILLO`, reusado de `estilos.py`, no
  un color nuevo) en la celda puntual ("Regular nuevo" o "Aislada
  nuevo") cuando ESE valor viene de un override a mano — nunca cuando
  sale de aplicar el % general o el diferencial, que siguen siendo
  "calculado por %" (un % puntual de esa fila sigue siendo un %, no una
  cifra tipeada a mano) — lectura literal del hallazgo, confirmada
  contra el ejemplo de la captura enviada.
- **Botón "Restablecer" por fila**: columna nueva sin título, un botón
  por fila (`setCellWidget`) deshabilitado si esa fila no tiene ningún
  override — clickearlo limpia el % diferencial Y el valor manual de
  esa fila de una sola vez, volviéndola a calcular por el % general.
- **Aviso de liquidaciones ANTES de confirmar**: `app.negocio.aumentos.
  cantidad_liquidaciones_a_regenerar(conn, periodo)` (nueva, extraída
  del mismo query que ya usaba `confirmar_aumento` para armar
  `ids_profesional`) se consulta antes de mostrar el cartel de
  confirmación, y la cantidad entra directo en el texto del cartel
  ("Hay N liquidación(es) ya emitida(s) para ese período: se van a
  regenerar con los valores nuevos" / "Todavía no hay ninguna
  liquidación emitida para ese período") — antes esa cantidad solo
  aparecía en el cartel de éxito, después de que ya se habían
  regenerado.

**Bug real encontrado al armar "Restablecer", no pedido** (destapado
comparando la geometría real contra lo esperado, no a ojo): `setCellWidget`
no borra solo el widget que reemplaza —a diferencia de `setItem`, que sí
limpia el item viejo— así que crear un botón "Restablecer" nuevo en
CADA render (`_simular`, tildar/destildar "Editar...") dejaba el botón
anterior huérfano, colgado del viewport sin ninguna posición asignada
por la tabla: Qt lo terminaba pintando en la esquina superior izquierda
del viewport, superpuesto contra "Localidad"/"Edificio" de la primera
fila en vez de desaparecer — `deleteLater()` tampoco alcanzaba, la
deleción queda pendiente del event loop, que entre un render y el
siguiente acá no llega a correr. Se resolvió reusando un solo botón por
consultorio (`self._botones_restablecer`, limpiado en `actualizar()`
junto con `_diferenciales`/`_valores_manuales`) en vez de crear uno
nuevo cada vez — solo se le actualiza el `setEnabled()` según corresponda.

Tests nuevos en `tests/test_aumentos.py` (tres: `cantidad_liquidaciones_
a_regenerar` sin emisiones es cero, cuenta profesionales distintos una
sola vez aunque tengan reemisión, coincide exactamente con lo que
`confirmar_aumento` termina regenerando) y en `tests/test_gui_aumentos.py`
(catorce: botón/columnas editables solo con el toggle prendido, fijar un
valor a mano actualiza la simulación sin que el % general/redondeo le
vuelvan a pegar, vaciar la celda saca solo ESE override, valor inválido
avisa sin romper, resaltado amarillo solo en la celda con override a
mano — nunca en la calculada por %—, valor manual y % diferencial se
excluyen mutuamente en una y otra dirección, "Restablecer" deshabilitado
sin override / limpia los dos tipos de override al clickear, el cartel
de confirmación menciona la cantidad real de liquidaciones — con y sin
liquidaciones emitidas—, confirmar aplica el valor manual al consultorio,
y el test de regresión del bug de los botones huérfanos).

## Séptima tanda de correcciones post-v1: Esquema de descuentos y
## Aumentos (edición por celda, en vez de checkbox global)

### Esquema de descuentos: mismo aviso de regeneración que Aumentos

`_PanelEsquemaDescuentos._confirmar_cambios` suma el mismo aviso que ya
tenía "Aumentos" (reusa `cantidad_liquidaciones_a_regenerar`, sin
duplicarla): antes de confirmar, si hay liquidaciones ya emitidas del
período en curso, el cartel dice cuántas y que van a quedar marcadas
como no enviadas. A diferencia de "Aumentos" (que regenera vía
`confirmar_aumento`, atado a `AumentoAplicado`/snapshot de "operación
importante"), acá se regenera directo con `regenerar_si_corresponde`
por cada profesional con liquidación emitida en el período — un cambio
de esquema de descuentos es más simple que un aumento, no necesita
ninguno de los efectos colaterales que sí tiene `confirmar_aumento`
(deshacer, snapshot).

### Aumentos: edición por click en la celda puntual, no por checkbox global

Pedido explícito de la clienta: en vez de dos botones checkable
("Editar porcentaje diferencial"/"Editar valores manuales") que
habilitaban la edición IN-PLACE de toda la columna a la vez, clickear
la celda puntual ("% diferencial", "Regular nuevo" o "Aislada nuevo")
abre un diálogo chico (`_DialogoValorFila`, genérico, reusado por los
tres) para fijar/quitar el override de ESA fila nomás — las otras filas
quedan intactas sin que haga falta "entrar/salir" de un modo de edición
global primero.

Se sacan los dos botones (`boton_editar`/`boton_editar_valores`) y los
flags `_editando_diferencial`/`_editando_valores` — las tres celdas
(`_COL_PORCENTAJE_DIFERENCIAL`/`_COL_REGULAR_NUEVO`/`_COL_AISLADA_
NUEVO`) pasan a ser SIEMPRE no editables in-place (`_celda_porcentaje`/
`_celda_monto_nuevo` sin el parámetro `editable`), y `tabla.itemChanged`
se reemplaza por `tabla.cellClicked` → `_al_click_celda(fila, columna)`,
que deriva a `_editar_diferencial`/`_editar_valor_manual` según la
columna. Un `QLabel` nuevo (`etiqueta_ayuda_edicion`) explica el
mecanismo donde antes estaban los botones. El resto de la lógica de
negocio (override mutuamente excluyente entre % diferencial/valor
manual, resaltado amarillo del valor manual, botón "Restablecer" por
fila) no cambió — solo cambió CÓMO se dispara la edición.

De paso, pedido explícito de revisar el foco visible en esta pantalla:
los `QRadioButton` de "Múltiplos de..." (el único lugar de todo el
sistema con `QRadioButton` en una cadena de foco) nunca habían tenido
ninguna regla `:focus` en `estilos.py` — mismo hueco que en su momento
tuvieron QComboBox/QCheckBox, mismo arreglo (`border` reservado,
transparente en reposo, color real al enfocar).

Tests: `tests/test_gui_aumentos.py` reescribe los ~13 tests que
dependían de los botones/edición in-place (ahora mockeando
`_DialogoValorFila` con un `_DialogoValorFalso`, mismo criterio que
`_DialogoFalso` de Pagos) y suma los de cancelar el diálogo sin cambiar
nada, más dos nuevos para el aviso/regeneración de Esquema de
descuentos. `tests/test_gui_estilos.py` suma `QRadioButton` a los dos
tests existentes de borde de foco reservado (texto de la hoja + render
real con muestreo de píxeles).

## Valores (las tres solapas): batch completo (#10.x del documento)

Undécima tanda de `v0.11.2026.10`, cerrando la décima sección del
documento ("VALORES"). A diferencia de la mayoría de las secciones
anteriores, acá dos de las tres solapas ya estaban completamente
cubiertas por tandas previas — se investigó cada punto contra el
código real antes de tocar nada, para no duplicar trabajo ya hecho:

- **Aumentos** (1.3/1.5/1.7/1.9/1.11 + "checks de múltiplos en
  columna"): confirmado, sin ningún cambio de código necesario. 1.3
  (orden PB/EP/piso de Unidad) ya se resolvió explícitamente para
  `aumentos.py` en la tanda GENERAL ("Orden natural de códigos..."
  más arriba, que también cubrió el combo de Unidad del filtro visual
  y `_cargar_consultorios_info`); 1.5 (`excluir_tabla_del_tab`) ya
  estaba llamado sobre la tabla de esta solapa; 1.7 (foco visible) ya
  sumó `QRadioButton` a la regla de borde reservado en la séptima
  tanda ("edición por celda, en vez de checkbox global"); 1.9
  (regenerar + marcar no enviada tras cualquier recálculo del período
  actual) ya se logra de punta a punta dentro de `confirmar_aumento`
  (`app.negocio.aumentos`), que llama `emitir_liquidacion` directo por
  cada profesional con liquidación emitida del período — mismo
  resultado que `regenerar_si_corresponde`, por un camino ya existente
  desde antes de este documento; 1.11 (alerta con el número real antes
  de confirmar, más alerta de éxito) ya estaba resuelto por
  `cantidad_liquidaciones_a_regenerar` (DC-10 §1.2, tanda anterior) y
  el cartel final de "Aumento confirmado". "Checks de múltiplos en
  columna": la grilla de checkboxes de "Múltiplos de..." ya se armaba
  en 2 columnas fijas (`indice // 2, indice % 2`) desde que se armó esa
  sección — confirmado leyendo el código, no es un pedido nuevo.
- **Esquema de descuentos** (1.9 si corresponde): confirmado, sin
  ningún cambio de código necesario — `_PanelEsquemaDescuentos.
  _confirmar_cambios` ya llama `regenerar_si_corresponde` por cada
  profesional con liquidación emitida en el período, sumado en la
  séptima tanda ("mismo aviso de regeneración que Aumentos").
- **Valores vigentes** (1.4/1.5 + reubicar tablas/anchos + foco sin
  título de pestaña): 1.5 ya estaba resuelto (`setFocusPolicy(
  ClickFocus)` + `setTabKeyNavigation(True)` puestos a mano sobre
  `tabla_valores`/la tabla de `_PanelPromedios`, funcionalmente
  idéntico a `excluir_tabla_del_tab`). "Reubicar tablas + anchos" ya
  quedó resuelto en la ronda "Valores vigentes: columnas sin scroll
  horizontal, Localidad/Edificio más anchas en Promedios" (ver más
  arriba en este documento) — sin ningún pedido nuevo que apunte a otra
  cosa, se tomó como ya cumplido.

  **1.4/"foco sin título de pestaña" era un hueco real**: esta solapa
  pasa DESNUDA a `addTab(...)` de "Valores" (sin `QTabWidget`/título
  propio — mismo criterio `panelSolapa` que el resto de las solapas
  "bare" de este sistema), así que necesitaba su propio `showEvent`
  para que el foco no se quedara en la barra de solapas al entrar —
  ninguno de los paneles de esta pantalla (`_PanelValoresVigentes`) lo
  tenía. Se suma `_PanelFiltrosJerarquico.reiniciar()` (recarga la
  cascada completa de Localidad/Edificio/Unidad/Consultorio volviendo
  los cuatro niveles a "Todas/os" y enfoca el primer filtro,
  `self._filtro_localidad.foco_widget()` — el botón-resumen del
  `_FiltroColapsable`, no la lista interna que arranca oculta) y
  `_PanelValoresVigentes.showEvent()`/`reiniciar()` (delega en el
  `reiniciar()` del panel de Filtros) — mismo patrón `showEvent` →
  `reiniciar()` ya usado en todo el sistema para el punto 1.4, y mismo
  método que F3 (`VentanaPrincipal._reiniciar_solapa_activa`) puede
  disparar por duck-typing sin necesitar ningún cambio ahí.

Tests nuevos: `tests/test_gui_valores.py`
(`test_valores_vigentes_reiniciar_recarga_filtros_y_enfoca_el_primero`
— deselecciona Localidad a mano, muestra el panel, y confirma que
`reiniciar()` volvió a seleccionar todo y que el foco llegó al primer
filtro; usa `qtbot.waitUntil` para el `hasFocus()`, no un assert
inmediato — bajo la plataforma `offscreen`, el foco puesto dentro de
`showEvent` no siempre se refleja en `hasFocus()` sin un tick más del
event loop, mismo criterio ya usado en varios tests de
`test_gui_reservas.py`). Suite combinada (`test_gui_valores.py` +
`test_gui_pantalla_grilla_operativa.py` + `test_gui_aumentos.py` +
`test_gui_grilla_y_mensajeria.py`): 72 passed, sin regresiones.

