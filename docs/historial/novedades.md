# Historial archivado — Registro de ausencias (Vacaciones, Licencias, Ausencias) y Cargos especiales

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

## Cargos especiales y Centro de mensajería: se sacan sus "Deshacer..."

Pedido explícito de la clienta al ver las capturas de "Llaves y otros
conceptos" (solapa "Registro de cargos especiales") y de "Grilla y
mensajería" (solapa "Centro de mensajería"): sacar el botón "Deshacer
último movimiento"/"Deshacer última acción" de las dos — mismo criterio
ya aplicado antes en Llaves y en Reservas ("cubría cualquier alta/
edición/baja de esta pantalla, se sacó por completo a pedido explícito
porque no estaba en la lista final de botones que dio la clienta —
pérdida de funcionalidad real, no solo estética"). Acá también se borra
todo el código que solo existía para alimentar ese botón, no solo el
widget.

- **Cargos especiales** (`_PanelCargosEspeciales`, `app/gui/pantallas/
  novedades.py`): se borra el botón, su conexión
  (`clicked.connect(self._deshacer_ultimo)`) y el método `_deshacer_
  ultimo` entero, además de sacarlo de la cadena de foco Enter/Tab
  (pasa de Buscar→Tipo→Concepto→Monto→Período→Crear→Modificar→
  Eliminar→Deshacer a la misma cadena sin el último paso).
  `_bloqueado_por_llave` (el guardarraíl que impide tocar un cargo
  ligado a una llave) se queda intacto — sigue haciendo falta para
  Modificar/Eliminar, que no se tocaron.
- **Centro de mensajería** (`_PanelCentroMensajeria`, `app/gui/
  pantallas/mensajeria.py`): a diferencia de Llaves/Cargos especiales,
  acá "Deshacer última acción" no borraba un solo tipo de registro —
  revertía CUALQUIERA de cuatro acciones distintas (marcar/desmarcar
  "Enviada", generar el texto marrón de "mensaje previo" o el celeste
  de "mensaje aislada"), guardadas en un diccionario `self._ultima_
  accion` que se iba pisando en cada acción mutante. Sacar el botón por
  sí solo hubiera dejado ese diccionario (y todo lo que lo alimentaba)
  como código muerto, así que se borró todo junto: el atributo
  `_ultima_accion`, los cuatro lugares donde se lo pisaba
  (`_al_cambiar_enviada`/`_desmarcar_enviada`/`_marcar_como_enviada`/
  `_generar_y_mostrar`/`_texto_para_boton`) y los tres métodos que solo
  existían para leerlo (`_deshacer_ultima_accion`/`_deshacer_marcar_
  enviada`/`_revertir_bandera_mensajeria`). De paso se sacó el respaldo
  de PDF previo que hacía `_marcar_como_enviada` antes de generar el
  nuevo (leer a memoria el archivo viejo con ese nombre, si existía,
  para poder restaurarlo al deshacer) — sin la opción de deshacer, ese
  respaldo no tenía ningún otro consumidor, así que quedaba leyendo un
  archivo a memoria en cada marcado sin que nada lo usara después.
  Tests borrados en bloque (mismo criterio: eran pruebas de la
  funcionalidad que se retira, no de otra cosa): los ocho de la sección
  "deshacer última acción" al final de `test_gui_mensajeria.py`
  (sin acciones, marcar enviada con/sin PDF previo, restaurar saldo
  actual, violeta restaura plazo extendido, desmarcar enviada, generar
  texto marrón/aislada, y el de "generar texto sin mutación no deja
  nada para deshacer" — este último ya no tiene sentido sin el
  concepto de "última acción" a probar).

## Registro de ausencias: se saca "Deshacer último movimiento" de las
## tres solapas con alta/edición (Vacaciones, Licencias, Ausencias)

Pedido explícito de la clienta, mismo criterio ya aplicado antes en
Llaves, Reservas y Cargos especiales/Centro de mensajería: el botón
"Deshacer último movimiento" cubría cualquier alta/anulación de la
solapa (anulaba la última Vacación/Licencia/Ausencia cargada en todo el
sistema, sin importar el profesional del filtro), y se saca por
completo — no estaba en la lista final de botones que dio la clienta.
"Tipos de licencia" (la cuarta solapa, un catálogo `PantallaCRUD`
anidado) nunca tuvo este botón, no fue parte del pedido.

Se borra, en `_PanelVacaciones`/`_PanelLicencias`/`_PanelAusencias`
(`app/gui/pantallas/novedades.py`) — cada una con su propia
implementación, ninguna compartía estado con otro método salvo
`_cancelar_registro` (que Anular ya usa, se queda intacto): el widget
del botón, su conexión (`clicked.connect(self._deshacer_ultimo)`) y el
método `_deshacer_ultimo` entero. Ninguna de las tres tenía este botón
sumado a su cadena de foco Enter/Tab (`instalar_enter_avanza_foco`
termina en el botón "Crear..." de cada una), así que no hizo falta
tocar ningún `_foco`.

Tests borrados en bloque en `test_gui_novedades.py` (mismo criterio:
eran pruebas de la funcionalidad que se retira, no de otra cosa): los 9
de "deshacer_ultimo_movimiento_{vacaciones,licencia,ausencia}_
{sin_registros_no_falla,anula_la_ultima_sin_importar_filtro,
cancelado_por_usuario_no_borra}". `test_botones_secundarios_de_las_
tres_solapas_son_celestes` (confirma que Modificar/Anular quedan en
`botonSecundario`) pierde su aserción sobre los tres "Deshacer..." y su
docstring, que los mencionaba.

## Novedades: vacaciones/licencias nunca chocan con una aislada ya cargada (auditoría #16, decisión consciente)

Hallazgo de la auditoría (#16): "al cargar una Vacación o Licencia, el
sistema no avisa ni bloquea si ya hay una Reserva Aislada de OTRO
profesional ocupando ese mismo consultorio/horario gracias al lugar que
dejó vacante el profesional ausente". Investigado antes de proponer
nada: `crear_vacacion`/`crear_licencia` en efecto no hacen ningún chequeo
contra `ReservaAislada` — solo `cancelar_vacacion`/`cancelar_licencia` lo
hacen (`aisladas_bloqueadas_por_anulacion`, para impedir anular una
vacación si eso dejaría "huérfana" una aislada que ya ocupó ese lugar).

Confirmado con la clienta que esto no es un hueco: una reserva aislada
SOLO se puede cargar en un consultorio/horario ya liberado por una
vacación/licencia/ausencia existente (`verificar_conflictos_aislada`
exige que el lugar esté libre o vacante) — es decir, el orden real
siempre es "primero se vacía el lugar, después se ocupa". Al CREAR una
vacación/licencia nueva no puede existir todavía ninguna aislada que
dependa de ella (no hay ninguna aislada previa que "choque" con un
vaciado que recién está ocurriendo) — el caso que sí importa (anular una
vacación que una aislada ya está usando) ya está cubierto por el
chequeo que SÍ existe en `cancelar_vacacion`/`cancelar_licencia`.

Hallazgo cerrado sin cambio de código — mismo criterio que otras
decisiones ya documentadas en este archivo (DC-07 §2.5/§3.3, hallazgo
#33): no es un bug, agregar el chequeo sería redundante.

## Registro de ausencias (Vacaciones): combo acotado a reserva activa, cálculo en vivo del período (auditoría #20)

Hallazgo de la auditoría (#20, DC-10 §1.1 F19): "el combo Profesional de
la solapa Vacaciones no se acota a quienes realmente pueden tomar
vacaciones, y no hay ningún cálculo en vivo mientras se eligen las
fechas Desde/Hasta — solo se sabe el impacto real al confirmar". Pedido
explícito de la clienta sobre los dos puntos: "acortá la lista de
alguna manera a que solo se pueda buscar profesionales con reservas
regulares activas. No se pueden cargar vacaciones a quién no tiene
reserva regular. Y sumá el cálculo en vivo, me parece interesante y
útil."

### Combo acotado a reserva regular activa

`_opciones_profesional_vacaciones(conn)` (nueva, `app/gui/pantallas/
novedades.py`) reemplaza, SOLO en `_PanelVacaciones`, el `_opciones_
profesional(self.conn, _CATEGORIAS_TODAS)` genérico que seguían usando
Licencias/Ausencias/Cargos especiales (esas tres pantallas no fueron
parte de este pedido, se quedan igual). Devuelve categoría R/B/E
(`CATEGORIAS_CON_DERECHO_A_VACACIONES`, ya existente) CON una
`ReservaRegular` vigente HOY (mismo criterio de "activa" que `app.
negocio.panel_control._reserva_regular_activa`: `VigenciaInicio <= hoy
AND (VigenciaFin IS NULL OR VigenciaFin >= hoy)`).

Este combo cumple doble función en esta pantalla (elegir a quién
crearle una vacación nueva, Y filtrar el historial de la tabla de
abajo) — acotarlo solo a los elegibles de HOY hubiera dejado sin forma
de filtrar el historial de alguien que ya tiene vacaciones cargadas
pero hoy dejó de reservar regular. Por eso la lista es la UNIÓN de "
elegible hoy" con "ya tiene al menos una `Vacacion` registrada" (un
`OR EXISTS` contra la tabla `Vacacion`, no solo el filtro de reserva
activa) — nadie con historial real desaparece de la lista, aunque ya
no se le pueda cargar una vacación nueva.

### Cálculo en vivo al elegir Desde/Hasta

`simular_vacacion(conn, *, id_profesional, fecha_desde, fecha_hasta)`
(nueva, `app/negocio/vacaciones.py`, devuelve el dataclass `Simulacion
Vacacion`) extrae el cálculo que ya hacía `crear_vacacion` de punta a
punta (valor bonificado, fracción de semana consumida, % de cupo
consumido/restante, la advertencia de "excede el cupo disponible" si
corresponde) SIN llegar a guardar nada — `crear_vacacion` pasa a
delegar en esta función (mismo resultado exacto, confirmado con la
suite completa de `tests/test_vacaciones.py` sin tocarla).

`_PanelVacaciones` suma `self.etiqueta_simulacion_periodo` (un `QLabel`
con `setWordWrap`, ubicado justo debajo de los campos Desde/Hasta, antes
de los tres botones de acción) y `_actualizar_simulacion_periodo`, que
llama a `simular_vacacion` con el profesional/fechas tal cual están
tipeados en ESE momento — conectado a `combo_profesional.
currentIndexChanged` (vía `_profesional_cambio`) y a `campo_desde.
dateChanged`/`campo_hasta.dateChanged` directo, así que se recalcula
sin necesitar ningún botón. Sin profesional elegido, o si `simular_
vacacion` tira `ValueError` (ej. un período que cruza de año), muestra
un guión en vez de romper. También se vuelve a llamar después de Crear/
Anular (el cupo ya consumido cambia, así que la vista previa del mismo
período tiene que reflejarlo).

Tests nuevos en `tests/test_gui_novedades.py`: `test_combo_vacaciones_
solo_incluye_profesionales_con_reserva_regular_activa` (categoría R sin
reserva y categoría sin derecho quedan afuera), `test_combo_vacaciones_
conserva_a_quien_ya_tiene_historial_aunque_hoy_no_califique` (alguien
con una vacación ya cargada sigue en el combo aunque se le cierre la
`ReservaRegular`), `test_simulacion_en_vivo_del_periodo_se_actualiza_al_
cambiar_las_fechas` (guión sin profesional, texto real al elegir
fechas), `test_simulacion_en_vivo_se_recalcula_despues_de_crear_una_
vacacion` (el mismo período muestra un texto distinto después de
confirmar). El test preexistente de "filtra por profesional" se ajustó:
el "otro profesional" que antes era categoría A sin ninguna reserva (ya
no entraría al combo acotado) pasa a ser categoría R con su propia
`ReservaRegular` vigente, preservando la intención original del test
(un profesional elegible sin ninguna vacación cargada muestra la tabla
vacía).

## Registro de ausencias (las cuatro solapas): batch completo (#13.x del documento)

Decimotercera tanda de `v0.11.2026.10`, cerrando la sección "REGISTRO DE
AUSENCIAS". 1.2/1.5/1.7/1.8/1.9/1.10/1.11/1.12/1.13 ya estaban resueltos
desde tandas anteriores en las tres solapas con alta (confirmado leyendo
el código, sin ningún cambio): selector de profesional buscable
(`habilitar_busqueda_profesional`), `excluir_tabla_del_tab` en las tres
tablas, foco visible en combos/checks (regla general de `estilos.py`),
`activar_filas_y_columnas_fijas()`/`reservar_alto_scroll_horizontal()`
en la grilla embebida de las tres, `regenerar_si_corresponde` ya
llamado al crear/cancelar en Vacaciones y Licencias (tanda anterior,
"Vacaciones/Licencias: regenerar..."), `confirmar_datos_antes_de_crear`
ya conectado en Vacaciones/Ausencias, botones secundarios ya
deshabilitados sin selección en Ausencias, día de semana abreviado ya
en `_campo_fecha`, sábado en negro ya aplicado vía
`aplicar_color_sabado_negro` en esa misma fábrica. Lo que faltaba era
puntualmente **1.4** (reset de filtros al volver a la solapa) en las
tres, y un hallazgo de ancho de columna en el catálogo anidado "Tipos
de licencia".

### 1.4 — `reiniciar()` en Vacaciones/Licencias/Ausencias

Mismo hueco exacto ya corregido en Liquidaciones/Pagos: el `showEvent`
de las tres solo reiniciaba el orden de la tabla y refocaba
Profesional, sin devolver ningún campo a su valor de recién construida
— `combo_profesional` quedaba en el profesional que se hubiera elegido
la última vez, `spin_anio`/`campo_desde`/`campo_hasta` en lo que se
hubiera tipeado, etc. Las tres suman `reiniciar()` (llamado desde
`showEvent`, descubrible por F3 vía duck-typing, sin ningún cambio en
`main_window.py`):

- **Vacaciones**: Profesional a "Todos los profesionales", Año
  calendario al actual (`fecha_actual(conn).year`), Desde/Hasta a hoy.
- **Licencias**: Profesional a "Todos los profesionales", Tipo de
  licencia al primero (con su % de bonificación recargado vía
  `_precargar_porcentaje`, ya que `combo_tipo.setCurrentIndex(0)`
  puede no disparar `currentIndexChanged` si ya estaba en esa
  posición), Desde a hoy, Hasta al sentinel "(sin fecha)"
  (`_FECHA_SIN_DATO`, importado de `reservas.py`).
- **Ausencias**: Profesional a "Todos los profesionales", Motivo al
  primero, Desde/Hasta a hoy, "Horario puntual" destildado con su
  horario default (9 a 10).

### Tipos de licencia — columna "Nombre" muy pegada al contenido

Hallazgo real, no puntual de este catálogo: `PantallaCRUD.actualizar()`
(`crud_generico.py`) solo llamaba `resizeColumnsToContents()`, sin
ningún padding extra — a diferencia de `novedades._ajustar_columnas`/
`llaves._ajustar_columnas` (+30px sobre el ancho justo), que sí lo
tienen desde hace tiempo. Con un texto largo en "Nombre" (ej. una
licencia con nombre descriptivo largo), la columna quedaba exactamente
al ancho del texto, sin ningún margen de respiro — se notaba más en
este catálogo anidado (dentro de "Registro de ausencias") que en el
resto, pero el hueco real es compartido por los ~14 catálogos genéricos
que pasan por `PantallaCRUD`.

Corregido de una sola vez en el lugar común: `crud_generico.py` suma
`_PADDING_COLUMNA = 30` y, después de `resizeColumnsToContents()`, le
suma ese padding a cada columna (`setColumnWidth(col, columnWidth(col)
+ _PADDING_COLUMNA)`) — mismo criterio y mismo valor que las otras dos
pantallas armadas a mano, ahora centralizado para que cualquier
catálogo genérico (presente o futuro) quede parejo sin tener que
acordarse de aplicarlo pantalla por pantalla.

Tests nuevos: `tests/test_gui_novedades.py`
(`test_vacaciones_reiniciar_vuelve_filtros_al_default`,
`test_licencias_reiniciar_vuelve_filtros_al_default`,
`test_ausencias_reiniciar_vuelve_filtros_al_default` — las tres
muestran la pantalla de verdad, `pantalla.pestanas.setCurrentWidget(
panel)` para Licencias/Ausencias antes de llamar `reiniciar()`
directo, ya que `setFocus()` sobre un widget oculto no deja
`hasFocus()` en verdadero bajo la plataforma `offscreen`);
`tests/test_catalogos.py`
(`test_tabla_de_catalogo_generico_suma_padding_sobre_el_ancho_justo` —
mide el ancho real del texto más largo con `QFontMetrics` y confirma
que la columna queda por encima de ese ancho justo, no solo igual).
Suite combinada `test_gui_novedades.py`+`test_catalogos.py`+
`test_crud_generico.py`: 190 passed. Suite completa: 2479 passed, sin
regresiones.

