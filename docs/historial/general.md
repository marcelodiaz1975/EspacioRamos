# Historial archivado — General y multi-pantalla (reorganizaciones, auditorías, tandas de correcciones cross-cutting)

Rondas de trabajo ya cerradas, movidas aquí desde CLAUDE.md para aligerar lo que se carga en cada sesión nueva (ver CLAUDE.md, sección "Historial archivado"). Contenido tal cual se escribió en su momento — el texto no se reescribió, solo se reubicó.

## Reordenamiento de formularios y solapas (en curso)

Después de cerrar la revisión "uno por uno" de cada pantalla (incluida
Seguridad), la clienta pidió una reorganización completa de la
navegación: mandó un Excel con, por cada formulario nuevo del menú, sus
solapas (en orden — la primera es la que se ve por defecto al entrar) y
qué formulario/solapa vieja va a parar ahí, más una columna de
modificaciones puntuales. El criterio general: varias pantallas que hoy
son formularios propios del menú pasan a ser solapas de un formulario
más grande y afín (ej. "Importar planilla" deja de estar en el menú y
pasa a ser una solapa de "Panel de control"), y las categorías del menú
se renombran de "Principal"/"Catálogos"/"Configuración" a "Sistema"/
"Operativa diaria".

Se detectaron dos casos que el Excel de la clienta no contemplaba
(pantallas/catálogos existentes sin destino asignado), resueltos con
ella antes de tocar código:
- La solapa "Estadísticas" de Vista rápida (tabla de ocupación en vivo,
  filtrable, DISTINTA de la pantalla completa "Estadísticas") — decisión:
  sacarla del sistema, queda cubierta por la pantalla completa.
- El catálogo "Placas" (tablero de posiciones/nombre grabado, DISTINTO
  de la pantalla operativa "Placas") — decisión: pasa a ser la tercera
  solapa de "Placas para timbres" (el nuevo nombre de la pantalla
  operativa "Placas").

El trabajo se hace por etapas (un merge por vez, con capturas y
pyflakes/suite después de cada uno), empezando por los merges más
simples de la categoría "Sistema":

### Panel de control + Importación

Primer merge hecho. "Importar planilla" deja de ser una pantalla propia
del menú y pasa a ser la segunda solapa de "Panel de control"
("Importación datos desde Excel"), junto a la primera ("Avance de
período y backups", todo lo que antes era el contenido único de esa
pantalla). Mecánicamente:

- `app/gui/pantallas/importacion.py`: la clase pasa de `PantallaImportacion`
  (pantalla completa, con su propio título Nivel 1 y su propio
  `QTabWidget` de una sola pestaña) a `_PanelImportacion` (una solapa
  desnuda — `objectName="panelSolapa"` puesto sobre sí misma, sin título
  ni `QTabWidget` propio), lista para pasarse directo a `addTab(...)` de
  otro formulario — mismo criterio ya usado en toda la revisión (
  `_PanelReservasRegulares`, `_PanelHistorialGeneral`, etc.). El contenido
  interno (botones, tabla de resultados, informe de integridad) no
  cambió en nada.
- `app/gui/pantallas/panel_control.py`: el contenido que antes era la
  única solapa de `PanelControl` ("Panel de control", con los dos
  botones, la grilla de cuadritos y las alertas) se extrajo tal cual a
  una clase nueva, `_PanelAvancePeriodo` (mismo patrón `panelSolapa`/
  `showEvent` propio). `PanelControl` queda como el contenedor de
  afuera: solo el título Nivel 1 (nombre del espacio) y un `QTabWidget`
  con las dos solapas (`_PanelAvancePeriodo` como "Avance de período y
  backups", `_PanelImportacion` — importado cruzado, mismo criterio que
  `_pixmap_primera_pagina_pdf`/`_opciones_profesional` en otras
  pantallas — como "Importación datos desde Excel"). `PanelControl.
  actualizar()` sigue siendo el punto de entrada de afuera (nada externo
  lo llamaba salvo el propio `__init__`), y ahora hace dos cosas:
  actualiza el título y delega en `self.panel_avance.actualizar()` para
  todo el resto (períodos, tarjetas, alertas).
- `gui_main.py`: se sacó la `Seccion` propia "Importar planilla" y su
  import; la ayuda de "Panel de control" se actualizó para mencionar las
  dos solapas.
- Tests: `test_gui_importacion.py` pasa a instanciar `_PanelImportacion`
  directo (dejó de tener sentido el test de "una sola pestaña", ya no
  hay ningún `QTabWidget` propio — se reemplazó por un test más simple
  que confirma el `objectName="panelSolapa"`). `test_gui_panel_control.py`
  pasa todos sus accesos de `pantalla.boton_backup`/`etiqueta_*`/etc. a
  `pantalla.panel_avance.boton_backup`/etc. (el título sigue siendo
  `pantalla.titulo`, en el contenedor de afuera), y suma dos tests
  nuevos confirmando las dos solapas y que la de Importación es un
  `_PanelImportacion` funcional.

### Configuración general + Bloques rígidos

Segundo merge de "Sistema" hecho. "Bloques rígidos" deja de ser una
pantalla propia del menú y pasa a ser una solapa más de "Configuración
general", intercalada entre "Grilla y ocupación" y "Valores y
liquidación" (7 solapas en total).

- `app/gui/pantallas/bloques_rigidos.py`: `PantallaBloquesRigidos` pasa
  a `_PanelBloquesRigidos` (mismo criterio que `_PanelImportacion`): sin
  título Nivel 1 ni `QTabWidget`/`QScrollArea` propio, `objectName=
  "panelSolapa"` puesto sobre sí misma, lista para `addTab(...)`. El
  contenido (Buscar/Nuevo/Editar/Eliminar + tabla) no cambió.
- `app/gui/pantallas/configuracion.py`: a diferencia de las otras seis
  solapas (todas `_PanelCampos`, generadas en un loop sobre `_GRUPOS`
  con campos simples de `Configuracion`), "Bloques rígidos" es un
  catálogo completo con su propia lógica y su propia cadena de foco
  Enter/Tab (Buscar → Nuevo → Editar → Eliminar) — no tiene sentido que
  el botón "Guardar" compartido (que persiste los campos de
  `Configuracion`) se sume al final de esa cadena. Se resolvió
  intercalando la solapa en `_armar_ui` (después de agregar "Grilla y
  ocupación", antes de seguir con el resto de `_GRUPOS`) y anotando un
  `None` en la posición correspondiente de `self._paneles` — `
  _actualizar_cadena_foco` corta temprano cuando el panel de la solapa
  actual es `None`, dejando que `_PanelBloquesRigidos` siga manejando su
  propia cadena de foco de siempre, sin tocarla. Mismo criterio ya
  documentado para Gastos operativos (`instalar_foco=False`): una
  solapa que "arma la suya propia" en vez de sumarse a la genérica.
- `gui_main.py`: se sacó la `Seccion` propia "Bloques rígidos" y su
  import; la ayuda de "Configuración general" se actualizó para
  mencionar la solapa nueva.
- Tests: `test_gui_bloques_rigidos.py` pasa a instanciar
  `_PanelBloquesRigidos` directo, con el mismo reemplazo del test de
  "una sola pestaña" por uno de `objectName="panelSolapa"` que en
  Importación. `test_gui_configuracion.py` suma un helper
  `_indice_de_solapa`/`_panel_de_grupo` (busca la solapa por su TEXTO en
  vez de por posición fija en `_GRUPOS`, que ya no coincide 1 a 1 con el
  índice real de cada solapa desde que se intercaló una que no viene de
  `_GRUPOS`) y lo usa en los tests que antes indexaban `_paneles`/
  `_GRUPOS` a mano (búsqueda de la solapa "Seguridad", cambio de solapa
  para revisar la cadena de foco); suma un test nuevo confirmando que la
  cadena de foco NO se reinstala al entrar a "Bloques rígidos".

### Archivos y listas (formulario nuevo, 4 solapas)

Tercer merge de "Sistema" hecho, el primero que junta pantallas antes
completamente independientes (sin relación entre sí) en un formulario
nuevo. "Archivos y listas" agrupa "Gestor de archivos del espacio"
(antes "Gestor de archivos", pantalla propia) + tres catálogos genéricos
que antes también eran pantallas propias del menú: "Listas editables",
"Condiciones y normas" y "Detalles complementarios de la propuesta".

Esto destapó una limitación real de `PantallaCRUD` (`crud_generico.py`):
hasta ahora solo sabía ser una pantalla de catálogo independiente
(título Nivel 1 + su propio `QTabWidget` de una sola pestaña "Listado")
o, en modo `compacto=True`, un componente embebido DENTRO de otra
pantalla compuesta pero sin la fila de Buscar ni la tabla envuelta en
solapa (pensado para catálogos como Mensajes predefinidos, con sus
propios paneles alrededor). Ninguno de los dos servía para "este
catálogo completo, tal cual, como una solapa más de un formulario
ajeno" — que es exactamente lo que necesitan varios formularios del
reordenamiento (Archivos y listas, Base datos del espacio, Profesionales
+Profesiones, Registro de ausencias +Tipos de licencia, Liquidaciones
+Fechas especiales, Placas para timbres +Placas, Balance del negocio
+Gastos operativos). Se sumó un parámetro nuevo, `anidado: bool = False`:
cuando es `True`, `PantallaCRUD` se salta el título y el `QTabWidget`
propio, pone `objectName="panelSolapa"` en sí misma (el widget de más
afuera, listo para `addTab(...)`) y arma el resto (Buscar + Nuevo/
Editar/Eliminar + tabla, con su `QScrollArea` interno) exactamente igual
que siempre — se extrajo esa construcción a un método propio,
`_armar_panel_izquierda_y_tabla`, compartido entre el modo estándar y el
anidado, para no duplicar el layout. La cadena de foco Enter/Tab
(Buscar → Nuevo → Editar → Eliminar) y el `showEvent` que la reinicia y
enfoca el primer control siguen funcionando igual en modo anidado, sin
ningún cambio — es la misma `PantallaCRUD` de siempre, solo sin la
ceremonia de título/solapa propia. Los tres catálogos de este merge
(`pantalla_listas_editables`/`pantalla_condiciones_normas`/
`pantalla_detalles_complementarios_propuesta` en `catalogos.py`) suman
un parámetro `anidado` propio (default `False`, no cambia nada para
quien los siga llamando sin ese argumento) que solo reenvían a
`PantallaCRUD`.

- `app/gui/pantallas/imagenes.py`: `PantallaImagenes` pasa a
  `_PanelGestorArchivos`, mismo criterio que el resto de los merges
  (`objectName="panelSolapa"` en sí misma, sin título ni `QTabWidget`
  propio) — a diferencia de `_PanelImportacion`/`_PanelBloquesRigidos`,
  conserva un `QScrollArea` interno (mismo patrón que `_PanelCampos` de
  Configuración general: el `objectName` va en el widget de más afuera
  aunque el contenido scrollee adentro), porque la pantalla original ya
  scrolleaba así. Esta pantalla nunca tuvo cadena de foco propia (no
  formó parte de la revisión "uno por uno") y se dejó tal cual — no es
  parte del alcance de esta reorganización agregarle una.
- `app/gui/pantallas/archivos_y_listas.py` (nuevo): `PantallaArchivosYListas`,
  mismo patrón que Usuarios y permisos — título Nivel 1 fijo
  ("ARCHIVOS Y LISTAS") + `QTabWidget` con las cuatro solapas en el
  orden del Excel de la clienta.
- `gui_main.py`: se sacaron las cuatro `Seccion` independientes
  ("Imágenes", "Listas editables", "Condiciones y normas", "Detalles
  complementarios (Propuesta)") y se sumó una sola, "Archivos y listas".
- Tests: `test_gui_imagenes.py` renombra la clase en sus imports/usos y
  suma un test de `objectName="panelSolapa"` (mismo criterio que
  Importación/Bloques rígidos). `test_crud_generico.py` suma dos tests
  para el modo `anidado=True` (sin título/QTabWidget, Buscar y foco
  intactos). `test_gui_archivos_y_listas.py` (nuevo) cubre el título, las
  cuatro solapas en orden, que "Gestor de archivos del espacio" es un
  `_PanelGestorArchivos` funcional y que las tres solapas de catálogo son
  `PantallaCRUD` anidadas de verdad (sin título propio, con `anidado is
  True`).

### Base datos del espacio (formulario nuevo, 5 solapas)

Cuarto y último merge de "Sistema": agrupa los cinco catálogos de
estructura física/contacto del espacio — antes cinco pantallas propias
del menú sin relación de navegación entre sí — en el orden de la cadena
de referencias real entre las tablas (Localidad → Edificio → Unidad →
Consultorio), más Responsables al final: "Localidades", "Edificios",
"Unidades", "Consultorios", "Responsables".

Mecánicamente el mismo patrón que Archivos y listas, reusando el
`anidado=True` de `PantallaCRUD` sumado en ese merge:
`pantalla_localidades`/`pantalla_edificios`/`pantalla_unidades`/
`pantalla_consultorios`/`pantalla_responsables` (`catalogos.py`) suman
su propio parámetro `anidado` (default `False`, sin efecto para quien ya
los llamaba sin ese argumento) que reenvían a `PantallaCRUD`.
`app/gui/pantallas/base_datos_espacio.py` (nuevo) define
`PantallaBaseDatosEspacio`, título Nivel 1 fijo + `QTabWidget` con las
cinco solapas. `gui_main.py` saca las cinco `Seccion` independientes y
suma una sola, "Base datos del espacio". Tests nuevos en
`test_gui_base_datos_espacio.py`, mismo criterio que Archivos y listas
(título, orden de las cinco solapas, cada una `anidado is True` sin
título propio, una solapa con datos reales cargados).

Con este merge, las cuatro pantallas de "Sistema" del reordenamiento
(Panel de control, Configuración general, Archivos y listas, Base datos
del espacio) quedan completas — sigue pendiente Usuarios y permisos
(que no necesitó ningún cambio, ya estaba en el formato final) y el
renombre de categorías "Principal"/"Catálogos"/"Configuración" a
"Sistema"/"Operativa diaria" en todas las `Seccion` de `gui_main.py`, que
queda para el final de toda la reorganización (junto con las pantallas
de "Operativa diaria" que todavía faltan).

### Grilla y mensajería + Valores (primeras dos de "Operativa diaria", con baja de Estadísticas en vivo)

Primer merge de "Operativa diaria", y el más grande hasta ahora: la vieja
pantalla "Vista rápida" (tres solapas: "Grilla semanal", "Valores de los
consultorios", "Estadísticas") se retira por completo, sus solapas se
reparten entre DOS formularios nuevos distintos, y una de las tres se
saca del sistema — la única baja de funcionalidad completa de todo el
reordenamiento (fuera de la reubicación del botón "Manual del usuario",
todavía pendiente). Antes de tocar código se le preguntó a la clienta
por este caso puntual, no contemplado en su Excel de reubicación (la
solapa "Estadísticas" de Vista rápida — una tabla en vivo, filtrable —
es DISTINTA de la pantalla completa "Estadísticas"): confirmó sacarla
del sistema, queda cubierta por la pantalla completa.

- **"Grilla y mensajería"** (`grilla_y_mensajeria.py`, nuevo): "Grilla
  semanal" (de Vista rápida) + "Centro de mensajería" + "Mensajes
  predefinidos" (antes las dos últimas, pantallas propias del menú).
- **"Valores"** (`valores.py`, nuevo): "Valores vigentes" (antes "Valores
  de los consultorios" de Vista rápida) + "Aumentos"/"Esquema de
  descuentos" (antes las dos solapas de la pantalla propia "Aumentos y
  descuentos").

Mecánica de la baja de Estadísticas: en `grilla_operativa.py` se borró
todo el código exclusivo de esa solapa (`_refrescar_estadisticas`,
`_ordenar_estadisticas_por_columna`, `_reconstruir_filas_estadisticas`,
`_ensanchar_columnas_localidad_edificio`, `_llenar_fila_estadistica`,
`tabla_estadisticas`/`filtros_estadisticas`/`_estadisticas`/
`_columna_orden_estadisticas`, las constantes `_COLUMNAS_ESTADISTICAS`/
`_PADDING_COLUMNAS_ESTADISTICAS`/`_VALOR_ESTADISTICA_POR_COLUMNA`/
`_fmt_horas`), junto con el módulo `app.negocio.estadisticas_operativas`
completo (`estadisticas_operativas.py` + su test) — sin otro consumidor,
confirmado por búsqueda antes de borrar. Lo que SÍ sigue usando ese
módulo (`_PanelFiltrosJerarquico`/`_PanelPromedios`, exclusivos de
"Valores de los consultorios") se quedó intacto.

Las dos solapas que sobreviven pasan a clases bare (`_PanelGrillaSemanal`/
`_PanelValoresVigentes`, ambas en `grilla_operativa.py`, mismo criterio
`objectName="panelSolapa"` de siempre) — la vieja `PantallaGrillaOperativa`
(título "Vista rápida" + su `QTabWidget` de tres solapas) se borra por
completo, cada nueva solapa se importa cruzada (import cruzado de un
símbolo privado, mismo criterio del resto de la reorganización) en el
formulario que corresponde.

`CentroMensajeria` (`mensajeria.py`) pasa a `_PanelCentroMensajeria`
(mismo criterio `_PanelImportacion`/`_PanelBloquesRigidos`: sin título ni
`QTabWidget`/`QScrollArea` propios). `PantallaMensajesPredefinidos`
(`mensajes_predefinidos.py`) pasa a `_PanelMensajesPredefinidos`: el
`PantallaCRUD` que arma internamente (con `panel_extra_superior_
izquierda` para todo lo propio de esta pantalla) suma `anidado=True`
(reusa el parámetro sumado en Archivos y listas); la fábrica
`pantalla_mensajes_predefinidos` se borra (ya no tiene otro consumidor).

`PantallaAumentos` (contenedor de "Aumentos y descuentos", dos solapas)
se retira: sus dos paneles (`_PanelAumentos`/`_PanelEsquemaDescuentos`,
ya eran clases bare desde que se armó esa pantalla) quedan como las dos
últimas solapas de "Valores", importadas cruzadas — ya no hace falta un
contenedor propio para ellas.

`gui_main.py`: se sacan las `Seccion` "Vista rápida", "Centro de
mensajería", "Mensajes predefinidos" y "Aumentos y descuentos"; se suman
"Grilla y mensajería" y "Valores".

Tests: `test_estadisticas_operativas.py` se borra entero (feature
retirada). `test_gui_pantalla_grilla_operativa.py` se reescribe: se
sacan todos los tests exclusivos de la solapa Estadísticas (8 tests) y
uno que comparaba el filtro de Valores contra el de la Grilla (dejó de
tener sentido: ya ni siquiera son solapas de la misma pantalla), el
resto pasa a instanciar `_PanelGrillaSemanal`/`_PanelValoresVigentes`
directo. `test_gui_mensajeria.py`/`test_mensajes_predefinidos.py` renombran
la clase en sus tests y suman un test de `objectName="panelSolapa"` (el
segundo además confirma `anidado is True` en el CRUD interno).
`test_gui_aumentos.py` reescribe sus ~27 tests para instanciar
`_PanelAumentos`/`_PanelEsquemaDescuentos` directo (se saca el único
test que existía solo para el contenedor, `test_pestanas`). Dos archivos
nuevos, `test_gui_grilla_y_mensajeria.py`/`test_gui_valores.py`, cubren
cada formulario nuevo (título, orden de solapas, tipo e identidad de
cada panel).

### Disponibilidad (con reubicación del botón "Manual del usuario")

Segundo merge de "Operativa diaria": agrupa "Oferta de consultorios" +
"Lista de espera" + "Archivos varios" (renombrada "Archivos para
enviar"), las tres antes pantallas propias e independientes del menú,
en un formulario nuevo. De paso, cumple el pedido puntual de la clienta
sobre esta misma reorganización: el botón "Manual del usuario" se saca
de "Archivos para enviar" (donde era uno de los botones de "elegir/ver",
junto a Propuesta/Disponibilidad) y se reubica en Gestor de archivos del
espacio (`imagenes.py`, formulario "Archivos y listas"), como botón
`botonPrimario` propio, después de "Eliminar" y con una línea divisoria
propia arriba.

- `oferta.py`/`lista_espera.py`/`archivos_varios.py`: `PantallaOferta`/
  `PantallaListaEspera`/`PantallaArchivosVarios` pasan a `_PanelOferta`/
  `_PanelListaEspera`/`_PanelArchivosVarios` (sin título ni `QTabWidget`
  propios). Caso especial: `_PanelListaEspera` NO le pone
  `objectName="panelSolapa"` a `self` — esta pantalla, desde antes de la
  reorganización, ya tenía el fondo claro de "ficha" acotado solo al
  formulario "Nuevo pedido" (la tabla de pedidos y los botones de abajo
  quedaban deliberadamente fuera de ese panel, sobre el fondo liso) — se
  preservó esa distinción tal cual estaba en vez de extender el fondo
  claro a toda la solapa, que hubiera sido un cambio visual no pedido.
- `disponibilidad.py` (nuevo): `PantallaDisponibilidad`, mismo patrón que
  el resto — título Nivel 1 fijo + `QTabWidget` con las tres solapas en
  el orden del Excel.
- Botón "Manual del usuario": `_PanelGestorArchivos` (`imagenes.py`) suma
  un parámetro `secciones` opcional (mismo dato que ya recibía
  `PantallaArchivosVarios` — la lista de `Seccion` del menú, para armar
  la ayuda contextual del manual vía `app.pdf.manual_pdf.
  generar_pdf_manual`) y un botón nuevo que, a diferencia del resto de
  los botones de este panel (que actúan sobre la fila seleccionada en la
  tabla), no depende de ninguna selección — siempre regenera el PDF
  contra el estado actual del sistema. `PantallaArchivosYListas` reenvía
  `secciones` hacia ese panel; `gui_main.py` se la pasa igual que antes
  se la pasaba a "Archivos varios" (comentario actualizado en
  `construir_secciones`, que arma la lista como mutable justamente por
  esto). `_PanelArchivosVarios` pierde `_TIPOS_DOCUMENTO["manual"]`, el
  botón y el parámetro `secciones` — ya no le hace falta.
- `gui_main.py`: se sacan las `Seccion` "Oferta de consultorios", "Lista
  de espera" y "Archivos varios"; se suma "Disponibilidad".
- Tests: `test_gui_oferta.py`/`test_gui_lista_espera.py`/
  `test_gui_archivos_varios.py` renombran la clase y suman/ajustan los
  tests de formato (el de Lista de espera se reescribe para no asumir
  más un `QTabWidget` ni un título propio). Los dos tests de "Manual del
  usuario" que tenía `test_gui_archivos_varios.py` se mudan, adaptados,
  a `test_gui_imagenes.py` (`_regenerar_manual` sobre
  `_PanelGestorArchivos`), más un test nuevo de posición/estilo del
  botón. `test_gui_main.py` actualiza su test de "la fábrica recibe la
  lista completa de secciones" para apuntar a "Archivos y listas" en vez
  de la ya inexistente "Archivos varios". `test_gui_disponibilidad.py`
  (nuevo) cubre el formulario compuesto.

### Profesionales (+ Profesiones y tratamientos)

Tercer merge de "Operativa diaria": agrupa "Profesionales" (listado +
documentación adjunta) con el catálogo "Profesiones" (renombrado
"Profesiones y tratamientos" como solapa), antes ambos pantallas propias
del menú.

A diferencia de los merges anteriores, acá el nombre del formulario de
afuera coincide con el de la pantalla vieja ("Profesionales"), así que
`app/gui/pantallas/profesionales.py` termina con las dos versiones
conviviendo en el mismo archivo: `PantallaProfesionales` (renombrada
desde la vieja pantalla) pasa a `_PanelProfesionales` (solapa desnuda,
`objectName="panelSolapa"`, sin título propio; el `PantallaCRUD` interno
`self.crud_profesionales` suma `anidado=True`), y el nombre
`PantallaProfesionales` queda libre para el contenedor de afuera nuevo
— título Nivel 1 fijo + `QTabWidget` con `_PanelProfesionales` como
"Listado de profesionales" y `catalogos.pantalla_profesiones(conn,
anidado=True)` (que suma su propio parámetro `anidado`, mismo mecanismo
que el resto de los catálogos) como "Profesiones y tratamientos". La
fábrica `pantalla_profesionales` (que devolvía la vieja pantalla) se
borra — ya no tiene otro consumidor fuera de `gui_main.py`.

`gui_main.py`: se sacan las `Seccion` "Profesionales" (la vieja, sobre la
fábrica) y "Profesiones"; se suma una sola "Profesionales" sobre
`PantallaProfesionales(conn)`.

Tests: `test_profesionales.py` renombra sus llamadas a `_PanelProfesionales`
y reescribe el único test estructural que asumía un `QTabWidget`/
`QScrollArea` propios del `PantallaCRUD` interno (ahora anidado, sin
esos dos). `test_gui_profesionales_formulario.py` (nuevo) cubre el
formulario compuesto (título, orden de solapas, tipo/objectName de cada
panel, `anidado is True` en la solapa de Profesiones).

### Reservas y Pagos (solo renombre de solapas) + Liquidaciones (+ Fechas especiales)

Cuarto merge de "Operativa diaria" según el Excel de la clienta, con dos
renombres puntuales de paso (sin ningún otro cambio estructural en esas
dos pantallas) y un merge real en Liquidaciones:

- **Reservas** (`reservas.py`): las dos solapas pasan de "Regulares"/
  "Aisladas" a "Reservas regulares"/"Reservas aisladas" — la pantalla
  sigue siendo la misma `PantallaReservas`, sin ningún otro cambio.
- **Pagos** (`pagos.py`): la solapa "Registrar pago" pasa a "Registrar
  pagos" — mismo criterio, solo texto de la pestaña (el botón interno
  sigue diciendo "Registrar pago", eso no cambió).
- **Liquidaciones** (antes "Liquidación mensual", `liquidacion.py`): pasa
  a formulario de tres solapas, sumando el catálogo "Fechas especiales"
  (antes pantalla propia del menú, categoría "Catálogos") como tercera
  solapa "Feriados y fechas especiales" — están relacionados porque los
  feriados/no laborables afectan el cálculo de la liquidación. Mismo
  mecanismo `anidado=True` de siempre: `catalogos.pantalla_fechas_
  especiales` suma su propio parámetro `anidado` (default `False`,
  reenviado a `PantallaCRUD`). El título Nivel 1 de `ProcesoLiquidacion`
  pasa de "Proceso de liquidación mensual" a "Liquidaciones" — mismo
  criterio que el resto de los merges de esta reorganización (el título
  pasa a ser el nombre nuevo del formulario), salvo Panel de control,
  que es un caso especial documentado aparte. `gui_main.py`: se renombra
  la `Seccion` "Liquidación mensual" a "Liquidaciones" (con la ayuda
  actualizada mencionando las tres solapas) y se saca la `Seccion`
  propia "Fechas especiales" — el catálogo "Placas" de esa misma
  categoría no se tocó, es un merge aparte (pasa a ser la tercera solapa
  de "Placas para timbres", todavía pendiente).

Tests: `test_gui_reservas.py`/`test_gui_pagos.py` no tenían ningún
assert sobre el texto de esas solapas, así que no hizo falta tocarlos.
`test_gui_liquidacion.py` suma cuatro tests: el objectName
`panelSolapa` de la solapa nueva (junto a los dos que ya existían para
Emisión/Estado de cuenta), el título Nivel 1 ("LIQUIDACIONES"), el
orden de las tres solapas, y que la solapa de Fechas especiales es un
`PantallaCRUD` anidado de verdad (sin título propio, con `campo_buscar`
armado) — mismo criterio que los tests de Base datos del espacio.

### Registro de ausencias (+ Tipos de licencia)

Quinto merge de "Operativa diaria": suma el catálogo "Tipos de licencia"
(antes pantalla propia del menú, categoría "Catálogos") como cuarta
solapa de "Registro de ausencias", intercalada entre "Licencias" y
"Ausencias" — están relacionados porque Licencias lee ese catálogo para
el combo de tipo. De paso, la solapa "Ausencias" se renombra "Ausencias
por motivos varios" (pedido del Excel de la clienta, más descriptivo
para no confundirla con el nombre genérico de la pantalla).

Mecánicamente el mismo patrón `anidado=True` de siempre:
`catalogos.pantalla_tipos_licencia` suma su propio parámetro `anidado`
(default `False`, sin efecto para quien ya la llamaba sin ese
argumento) que reenvía a `PantallaCRUD`. `PantallaRegistroAusencias`
(`app/gui/pantallas/novedades.py`) no cambia de forma — sigue siendo el
mismo contenedor título+`QTabWidget` de siempre — solo suma
`self.panel_tipos_licencia = catalogos.pantalla_tipos_licencia(conn,
anidado=True)` como tercera pestaña, importando `catalogos` cruzado
(sin ciclo: `catalogos.py` no importa `novedades.py`).

`gui_main.py`: se saca la `Seccion` propia "Tipos de licencia" y se
actualiza la ayuda de "Registro de ausencias" para mencionar las cuatro
solapas. `PantallaCargosEspeciales` (misma pantalla vieja, en el mismo
archivo) no se tocó en este merge — su combinación con Llaves queda
para el próximo.

Tests: `test_gui_novedades.py` suma dos tests (orden de las cuatro
solapas; la de Tipos de licencia es un `PantallaCRUD` anidado de
verdad, sin título propio, con `campo_buscar` armado) — mismo criterio
que Liquidaciones/Base datos del espacio. No hizo falta tocar ningún
test existente: ninguno hacía `tabText`/`pestanas.count()` sobre
`PantallaRegistroAusencias` antes de este merge.

### Llaves y otros conceptos (formulario nuevo, 3 solapas)

Sexto merge de "Operativa diaria": agrupa "Llaves" (antes pantalla propia
del menú, un único formulario con tres tablas apiladas) con las dos
solapas que ya tenía "Cargos especiales" (también pantalla propia del
menú) — ambas relacionadas porque un movimiento de llave (asignación/
devolución con depósito) genera automáticamente un cargo especial. Tres
solapas: "Movimientos y tenencias de llaves" (la vieja Llaves), "Registro
de cargos especiales" y "Estado de cuenta" (sin cambios, mismo orden que
ya tenían dentro de Cargos especiales).

Mecánicamente el mismo criterio que el resto de la reorganización, con
una variante nueva: acá NO se sumó ningún parámetro `anidado` (esta
pantalla no usa `PantallaCRUD`) — en su lugar, cada pieza se convirtió a
mano:

- `app/gui/pantallas/llaves.py`: `PantallaLlaves` pasa a `_PanelLlaves`
  (solapa desnuda, `objectName="panelSolapa"` en el widget de más
  afuera, sin título ni `QTabWidget` propio) — conserva su `QScrollArea`
  interno, mismo criterio que `_PanelGestorArchivos`/`_PanelCampos` para
  pantallas que ya scrolleaban así (el contenido de las tres tablas
  apiladas no entra siempre en el alto disponible).
- `app/gui/pantallas/novedades.py`: se borra el contenedor
  `PantallaCargosEspeciales` (título + `QTabWidget` propio) — sus dos
  paneles internos, `_PanelCargosEspeciales`/`_PanelEstadoCuentaCargos`,
  ya eran clases bare desde que se armó esa pantalla (mismo caso que
  `_PanelAumentos`/`_PanelEsquemaDescuentos` en su momento), así que no
  necesitaron ningún cambio propio — se importan cruzadas tal cual.
- `app/gui/pantallas/llaves_y_otros_conceptos.py` (nuevo): 
  `PantallaLlavesYOtrosConceptos`, mismo patrón que el resto — título
  Nivel 1 fijo + `QTabWidget` con las tres solapas importadas cruzadas.

`gui_main.py`: se sacan las `Seccion` "Llaves" y "Cargos especiales"; se
suma una sola "Llaves y otros conceptos".

Tests: `test_gui_llaves.py` renombra la clase (`_PanelLlaves`) en sus ~38
usos y reemplaza el único test estructural que asumía un `QTabWidget`
propio de una sola pestaña "Llaves" por uno de `objectName="panelSolapa"`
(mismo criterio que Bloques rígidos/Importación). `test_gui_novedades.py`
(que ya cubría Cargos especiales, al vivir en el mismo archivo fuente)
reemplaza sus ~26 instanciaciones de `PantallaCargosEspeciales(conn)` por
`_PanelCargosEspeciales(conn)`/`_PanelEstadoCuentaCargos(conn)` directo,
sacando la indirección `pantalla.panel`/`pantalla.panel_estado_cuenta`; el
test que verificaba el orden de las dos solapas dentro del contenedor
viejo se saca de acá (perdió sentido, ya no hay contenedor) y su
verificación pasa al nuevo `test_gui_llaves_y_otros_conceptos.py`, que
cubre el formulario compuesto completo (título, orden de las tres
solapas, tipo/objectName de cada panel).

### Placas para timbres (formulario nuevo, 3 solapas, con Buscar/Imprimir compartiendo estado)

Séptimo merge de "Operativa diaria": renombra la pantalla operativa
"Placas" a "Placas para timbres", renombra sus dos solapas ("Buscar y
asignar placas" → "Búsqueda y asignación de placas", "Imprimir placas"
→ "Impresión de placas en papel") y suma el catálogo "Placas" (el
tablero de posiciones/nombre grabado, distinto de la pantalla operativa
aunque comparten nombre) como tercera solapa — caso no contemplado en
el Excel de la clienta, resuelto con ella: "como tercera solapa de
'Placas para timbres'".

Variante nueva sobre el patrón de conversión a solapa desnuda: acá las
dos solapas viejas (Buscar/Imprimir) SIGUEN viviendo en una sola clase
porque comparten estado real, no solo un archivo — "Agregar a
impresión" en Buscar carga `_cola_impresion`, que Imprimir lee y
consume. Separarlas en dos clases independientes hubiera significado
inventar un canal de comunicación entre ellas que no hacía falta.
Solución: `PantallaPlacas` pasa a `_PanelPlacasOperativas`
(`app/gui/pantallas/placas.py`) — deja de ser, ella misma, una pantalla
con título y `QTabWidget` propio, pasa a ser un contenedor de lógica
compartida que expone `panel_buscar`/`panel_imprimir` (dos `QWidget`
que YA se construían por separado, en `_armar_panel_buscar`/
`_armar_panel_imprimir`) para que el formulario contenedor los sume
como dos solapas propias, hermanas del catálogo. El reinicio de
filtros al reingresar a la solapa de Buscar (antes en el `showEvent`
de la pantalla completa) pasa a `_PanelBuscarPlacas`, una subclase
mínima de `QWidget` solo para poder engancharle ese `showEvent` — un
`QWidget()` liso no admite pisarle el método de instancia porque Qt
resuelve `showEvent` por la clase, no por atributo.

`app/gui/pantallas/placas_para_timbres.py` (nuevo): `PantallaPlacasParaTimbres`,
mismo patrón que el resto — título Nivel 1 fijo + `QTabWidget` con las
tres solapas (`panel_operativas.panel_buscar`/`panel_operativas.
panel_imprimir`/`catalogos.pantalla_placas(conn, anidado=True)`, que
suma su propio parámetro `anidado`).

`gui_main.py`: se renombra la `Seccion` "Placas" (pantalla operativa) a
"Placas para timbres" sobre `PantallaPlacasParaTimbres`, con la ayuda
actualizada; se saca la `Seccion` propia del catálogo "Placas".

Tests: `test_gui_placas.py` renombra la clase (`_PanelPlacasOperativas`)
en sus ~30 usos; el test de título y el de "tiene dos solapas" se sacan
de acá (pasan al nuevo `test_gui_placas_para_timbres.py`); el de fondo
claro pasa a comprobar `pantalla.panel_buscar`/`pantalla.panel_imprimir`
directo (ya no hay un `QTabWidget` interno del que sacarlos con
`findChild`); los ~8 tests que mostraban la pantalla completa
(`pantalla.show()`/`waitExposed`) para medir geometría real pasan a
mostrar el panel puntual que corresponde (`pantalla.panel_buscar.show()`
o `pantalla.panel_imprimir.show()`), sacando el `findChild(QTabWidget).
setCurrentIndex(1)` que antes hacía falta para exponer la solapa de
Imprimir (ya no existe ese `QTabWidget` intermedio). `test_gui_placas_
para_timbres.py` (nuevo) cubre el formulario compuesto completo (título,
orden de las tres solapas, fondo claro de las dos operativas, catálogo
anidado sin título propio).

### Balance del negocio (formulario nuevo, 3 solapas — dos de informe en vivo, nunca existieron antes)

Octavo merge de "Operativa diaria", el único de toda la reorganización
que suma funcionalidad nueva de verdad (no solo reordena pantallas
existentes): "Gastos" es el catálogo Gastos operativos de siempre
(anidado, mismo mecanismo que el resto), pero "Ingresos" y "Resultado"
son informes 100% en vivo que no existían en ningún lado del sistema —
pedido explícito de la clienta al definir este formulario. Antes de
programarlos se le consultaron tres decisiones abiertas
(`AskUserQuestion`, ver también el docstring de `app.negocio.balance`):

- **Ingresos por horas regulares/aisladas, ¿neto o bruto?** Neto —
  mismo criterio "monto real facturado" que ya usa Estadísticas
  (descuento por volumen y recargo de aisladas ya aplicados). Reusa
  `app.negocio.estadisticas.monto_neto_regular_periodo`/`monto_neto_
  aislada_periodo` tal cual, sin duplicar el cálculo.
- **"Ingresos por reubicaciones por feriados": ¿a qué se refiere?**
  Aclarado por la clienta: no son las reubicaciones (que no facturan,
  compensan una ausencia). Es el cargo por "feriado trabajado" — un
  feriado no se cobra (se descuenta de la liquidación, se asume que el
  profesional no usa el espacio) salvo que decida usarlo, avisando
  cerca del momento; ese cargo puede caer en la liquidación del mes del
  feriado (si avisa antes de emitirla) o en la del mes siguiente (si
  avisa después) — "quiero que se contemple dentro de los ingresos en
  el período en el cual se carga en la liquidación, no importa la
  fecha del feriado". Esa resolución de período YA existe, tal cual
  descripta, en `app.negocio.liquidaciones._calcular_feriados_
  trabajados` (tabla `FeriadoTrabajado`, ya usada por Liquidaciones) —
  `app.negocio.balance.ingresos_feriados_trabajados_periodo` la reusa
  para todos los profesionales R del sistema en vez de reimplementarla,
  sumando el monto de cada item que efectivamente cae en el período
  pedido.
- **Alcance de ubicación**: mismos 4 niveles en cascada (Localidad/
  Edificio/Unidad/Consultorio, "el más específico manda") que ya usa
  Estadísticas Varias — confirmado. Esto generó un cruce con Gastos
  operativos, que tiene su propio Alcance de 3 niveles (Espacio
  general/Edificio/Unidad, sin Consultorio): consultado aparte,
  confirmó que al elegir cualquier filtro puntual de los 4, los gastos
  "Espacio general" quedan afuera del Resultado de ese lugar (no son
  atribuibles a uno puntual) — solo entran cuando los cuatro filtros
  están en su valor por defecto ("Todas"/"Todos", todo el espacio).
  `app.negocio.balance._alcance_gastos_del_filtro` traduce un alcance
  al otro.

Simplificación deliberada, documentada, misma que ya tenía `monto_neto_
regular_periodo`: el descuento por volumen de horas semanales se aplica
siempre, sin replicar la suspensión por saldo atrasado (`pierde_
descuento`) de una liquidación puntual — es un informe agregado, no una
liquidación.

`app/negocio/balance.py` (nuevo): `total_ingresos_periodo` (regulares +
aisladas + feriados trabajados, cada uno por separado), `total_gastos_
periodo` (con el cruce de alcance de arriba) y `resultado_periodo`
(ingresos - gastos), todo parametrizado por período y por el alcance de
ubicación de 4 niveles.

`app/gui/pantallas/balance.py` (nuevo): `PantallaBalanceDelNegocio`
(título Nivel 1 + `QTabWidget` con las tres solapas, en el orden
Gastos/Ingresos/Resultado — el catálogo ya existente primero, las dos
nuevas después). `_PanelIngresos`/`_PanelResultado`: cada uno arma su
propio panel de filtros (Período — arranca en el actual, cambiable,
mismo criterio que Gastos operativos — más la cascada de ubicación,
mismo código que `_PanelEstadisticasVarias` de Estadísticas, duplicado
acá como el resto de las pantallas del sistema que arman su propia
cadena de filtros — `_PanelFiltrosMixin` solo evita duplicar ESE
cableado entre los dos paneles nuevos, no es una clase base de verdad)
y muestra el resultado en un cuadro de etiquetas (`app.gui.widgets.
resumen_saldo.fmt_dato`, el mismo helper compartido que ya usan las
solapas "Estado de cuenta" de Pagos/Liquidaciones/Cargos especiales
para "rojo si es negativo").

`catalogos.pantalla_gastos_operativos` suma su propio parámetro
`anidado` (default `False`, reenviado a `PantallaCRUD`, mismo mecanismo
que el resto de los catálogos). `gui_main.py`: se saca la `Seccion`
propia "Gastos operativos" y se suma "Balance del negocio".

Tests: `tests/test_balance.py` (nuevo) cubre la lógica de negocio (suma
de los tres componentes de ingresos, traslado del feriado trabajado al
período siguiente cuando se avisa tarde, filtro por consultorio,
inclusión/exclusión de gastos generales según haya o no un filtro
puntual, resultado = ingresos - gastos). `tests/test_gui_balance.py`
(nuevo) cubre el formulario compuesto (título, orden de las tres
solapas, catálogo anidado sin título propio, fondo claro de los tres
paneles, valores por defecto de los filtros, recálculo al cambiar
período, coloreado rojo de gastos/resultado).

### Renombre final de categorías: Sistema / Operativa diaria

Con Balance del negocio, las doce pantallas de "Operativa diaria" con
cambio de código quedaron completas. Último paso del reordenamiento de
formularios: las tres categorías viejas del menú ("Principal"/
"Catálogos"/"Configuración") pasan a solo dos, "Sistema"/"Operativa
diaria", en todas las `Seccion` de `gui_main.py`.

`VentanaPrincipal` arma un separador de categoría cada vez que cambia
respecto de la `Seccion` anterior en la lista (no agrupa por nombre
repetido en toda la lista) — así que hizo falta REORDENAR la lista, no
solo cambiar el string de `categoria`, para que las cinco de "Sistema"
queden todas juntas y las doce de "Operativa diaria" también, sin
intercalarse (si no, el menú mostraría el separador "SISTEMA" varias
veces salteado). Dentro de cada bloque se conservó el orden relativo
que ya tenían entre sí las Secciones (no hay un orden pedido por la
clienta para este paso final, es criterio propio):

- **Sistema** (5): Panel de control, Archivos y listas, Base datos del
  espacio, Configuración general, Usuarios y permisos.
- **Operativa diaria** (12): Grilla y mensajería, Reservas,
  Liquidaciones, Llaves y otros conceptos, Placas para timbres,
  Disponibilidad, Registro de ausencias, Pagos, Estadísticas, Valores,
  Profesionales, Balance del negocio.

Test nuevo en `test_gui_main.py`: confirma que las categorías de
`construir_secciones()` son exactamente esas dos y que hay un solo
cambio de categoría en toda la lista (es decir, que van contiguas).

### Panel de control: primer alerta solo profesionales que reservan regular

Pedido de la clienta (repaso de pendientes abiertos, Excel de la
reorganización): "que el primer alerta sea los que deben por fuera del
rango de tolerancia a ese momento ordenado de por código, solo los
profesionales que reservan regular." La primera alerta ("Deuda mes
anterior — profesionales regulares") ya se mostraba primera (el orden
lo define `_TITULOS_ALERTA` en `app/gui/pantallas/panel_control.py`,
dict con "deuda_regulares" como primera clave — sin cambios ahí), pero
antes de este pedido incluía a CUALQUIER profesional categoría R con
saldo fuera de tolerancia, sin importar si hoy tiene alguna reserva
regular vigente, y sin ningún orden particular.

`app.negocio.panel_control._deuda_regulares` (la que también alimenta
el cuadrito "Profesionales" — "con saldo fuera de tolerancia", que
suma regulares + aisladas) se dejó SIN CAMBIOS a propósito, para no
alterar sin que se pidiera un cálculo de otra parte del panel. En su
lugar se sumó `_deuda_regulares_alerta` (más `_reserva_regular_activa`,
helper chico compartido), exclusiva para esta alerta: parte de la
misma lista de `_deuda_regulares` pero además exige una `ReservaRegular`
vigente hoy, y ordena el resultado por `Profesional.IdCodigo`.
`calcular_alertas` pasa a usar `_deuda_regulares_alerta` en vez de
`_deuda_regulares` para el campo `Alertas.deuda_regulares`.

### Menú lateral: ítem seleccionado en blanco y negrita; fantasma en alertas de Panel de control

Dos ajustes puntuales pedidos por la clienta al revisar capturas del
menú ya reordenado (Sistema/Operativa diaria):

- **Ítem de menú seleccionado**: el fondo bordó (`COLOR_DIA_GRILLA`) del
  ítem activo en el menú ya estaba bien, pero el texto no tenía un
  `color` propio en `::item:selected` — Qt caía al `HighlightedText` de
  la paleta global (pensada para la selección de filas de tabla en todo
  el sistema, no para esto), que en modo claro es casi negro y quedaba
  de bajo contraste contra el bordó. `QListWidget#navegacion::item:
  selected` (`estilos.py`) suma `color: {COLOR_TEXTO_CLARO}; font-
  weight: bold;` — mismo fondo bordó de siempre, texto blanco y
  negrita.
- **Alerta "fantasma" en Panel de control**: al revisar una captura de
  la tarjeta de alertas, se veía una segunda copia parcial (naranja sin
  texto + una sola línea suelta) debajo de la tarjeta real. Causa real,
  no un artefacto de la captura: `_refrescar_alertas` sacaba la tarjeta
  vieja del layout con `takeAt(0)` y la mandaba a `deleteLater()`, pero
  `takeAt` por sí solo NO oculta el widget — sigue siendo hijo visible
  en su última posición hasta que el event loop procesa el borrado
  diferido de `deleteLater`. Cualquier refresco encadenado (`showEvent`
  + el de la construcción inicial, por ejemplo) podía dejar la tarjeta
  vieja pintada un instante de más, superpuesta o debajo de la nueva.
  Se corrigió sumando `item.widget().hide()` antes de `deleteLater()`
  en ese mismo lugar — oculta al toque, sin depender de cuándo el
  event loop procese el borrado real. Test de regresión: guarda una
  referencia a la tarjeta antes de un segundo `actualizar()` y confirma
  `tarjeta_vieja.isHidden()` después.

### Separadores de categoría del menú en negrita con fondo azul oscuro; alerta de deuda regular mira el mes en curso

Dos ajustes puntuales más, pedidos por la clienta al revisar el menú ya
reordenado:

- **Separadores "— SISTEMA —"/"— OPERATIVA DIARIA —"**: quedaban con el
  mismo fondo azul (`COLOR_NIVEL_1`) y peso normal que cualquier ítem
  del menú, sin distinguirse como encabezados de grupo. Como estos
  ítems ya se arman con `Qt.ItemFlag.NoItemFlags` (deshabilitados, no
  seleccionables — `app/gui/main_window.py`), alcanzó con sumar
  `QListWidget#navegacion::item:disabled` en `estilos.py` (negrita +
  `COLOR_NIVEL_1_OSCURO`, el mismo azul más oscuro que ya usan los
  encabezados de columna de tabla) — no hizo falta tocar el código que
  arma el menú.
- **Alerta "Deuda mes anterior — profesionales regulares" (ahora "Deuda
  mes en curso...")**: la clienta aclaró que esta alerta puntual tiene
  que mirar el saldo de lo liquidado en el mes EN CURSO, no el
  arrastrado de meses anteriores. `_deuda_regulares_alerta` (`app.
  negocio.panel_control`) pasa a filtrar por `Profesional.
  SaldoCuentaActual` (lo que `avance_mes.avanzar_mes` resetea a 0 al
  arrancar un mes, `liquidaciones.emitir_liquidacion` va sumando y
  `pagos.registrar_pago` va restando durante el mes) en vez de
  `SaldoCuentaAnterior` — sin tocar `_deuda_regulares` (la función base,
  sigue con `SaldoCuentaAnterior`, sigue alimentando sin cambios el
  cuadrito "Profesionales: con saldo fuera de tolerancia"), aclarado
  explícitamente por la clienta como algo puntual "en esta sección al
  menos". El título de la alerta pasa de "Deuda mes anterior" a "Deuda
  mes en curso" (quedaba engañoso mantener el nombre viejo mostrando el
  dato nuevo) y la etiqueta de cada fila pasa de "saldo anterior" a
  "saldo actual" (mismo nombre que usan las solapas "Estado de cuenta"
  de Pagos/Liquidaciones/Cargos especiales para `SaldoCuentaActual`,
  vía `app.gui.widgets.resumen_saldo.fmt_dato`). La alerta de deuda de
  profesionales de reserva aislada ("Deuda mes anterior — profesionales
  de reserva aislada") no se tocó — sigue siendo sobre
  `SaldoCuentaAnterior`, no fue parte de este pedido.

### Panel izquierdo gris en vez de blanco (bug real, no solo la captura)

La clienta notó, mirando capturas de "Archivos y listas", que el panel
izquierdo (Buscar/Nuevo/Editar/Eliminar y cualquier `panel_extra_*`)
quedaba con un relleno más OSCURO que la solapa activa y que la tabla —
al revés de la regla ("Solapa ACTIVA: fondo CLARO... el panel de
contenido usa el mismo tono claro", ver "Jerarquía de títulos" más
arriba). Causa real, confirmada midiendo píxeles antes y después:

- `QWidget#panelSolapa { background-color: white; }` solo pinta blanco
  al widget que TIENE ese objectName puesto explícitamente — no
  "hereda" hacia sus hijos aunque el widget de más afuera sí lo tenga.
- El widget "panel izquierda" (Buscar+botones, armado en
  `crud_generico._armar_panel_izquierda_y_tabla`, reusado por TODOS los
  catálogos que pasan por `PantallaCRUD`) nunca tuvo ese objectName —
  solo el widget de MÁS afuera (`self` en modo `anidado`, o
  `panel_solapa` en modo estándar) lo tenía. Qt le pinta a ese panel
  izquierdo el gris por defecto de un `QWidget` sin estilo (visible
  contra el blanco de alrededor), mientras que la tabla se ve blanca
  aparte porque `QTableWidget` usa otro rol de paleta (`Base`) que sí es
  blanco por defecto — de ahí que solo el panel izquierdo se viera "más
  oscuro", nunca la tabla.
- En modo `anidado` había además un segundo widget sin ese objectName:
  `contenido` (el que se pasa a `scroll.setWidget(...)`, sin él en
  medio entre `self` y `panel_izquierda`) — en modo estándar ese
  equivalente (`panel_solapa`) SÍ lo tenía puesto desde siempre, así
  que ese modo estaba cubierto a medias.

Arreglo: `crud_generico.py` suma `panel_izquierda.setObjectName(
"panelSolapa")` en `_armar_panel_izquierda_y_tabla` (afecta a TODOS los
catálogos que pasan por acá, `anidado` o no) y `contenido.setObjectName(
"panelSolapa")` en el modo `anidado`. Como cualquier `panel_extra_
superior_izquierda`/`panel_extra_izquierda` (widgets propios de cada
catálogo, ej. "Período actual" de Gastos operativos) cuelgan DENTRO del
panel izquierda ya arreglado, quedaron blancos de rebote sin tocarlos
aparte — confirmado con Balance del negocio → Gastos.

Mismo bug, misma causa, encontrado también en `_PanelGestorArchivos`
(`app/gui/pantallas/imagenes.py`, armado a mano, no pasa por
`crud_generico.py`) — mismo arreglo aplicado ahí (`contenido`/
`panel_izquierda` propios de ese archivo suman `panelSolapa`).

Tests de regresión (cuentan cuántos `QWidget` descendientes tienen
`objectName() == "panelSolapa"`, ya que ninguno de los dos guarda
`panel_izquierda`/`contenido` como atributo propio): en
`test_crud_generico.py`,
`test_pantalla_crud_panel_izquierdo_tiene_fondo_blanco_no_gris` (modo
estándar) y `test_pantalla_crud_anidado_panel_izquierdo_tiene_fondo_
blanco` (modo `anidado`); en `test_gui_imagenes.py`,
`test_panel_izquierdo_tiene_fondo_blanco_no_gris`.

**Precisión sobre cuándo aparece de verdad** (surgió al revisar la
captura de "Bloques rígidos" dentro de Configuración general, y se
terminó de confirmar revisando Reservas/Llaves/Novedades a pedido de la
clienta): el bug NO afecta a cualquier panel armado a mano — depende de
si el widget que se pasa a `scroll.setWidget(...)` (`contenido`, en las
pantallas que envuelven su solapa en un `QScrollArea` propio) tiene o no
`objectName="panelSolapa"`:

- **Bloques rígidos**: arma su panel directo sobre `self` con un
  `QHBoxLayout`, sin ningún `QScrollArea` de por medio — no aplica este
  patrón, y confirmado en blanco sin tocar nada.
- **Novedades** (`_PanelVacaciones`/`_PanelLicencias`/`_PanelAusencias`):
  usa `QScrollArea`, pero `contenido` YA tenía `panelSolapa` puesto desde
  antes de esta revisión — confirmado en blanco sin tocar nada.
- **Reservas** (`_PanelReservasRegulares`/`_PanelReservasAisladas`) y
  **Llaves** (`_PanelLlaves`): usan `QScrollArea` y `contenido` NO tenía
  `panelSolapa` — bug real, confirmado por muestreo de píxeles (`#efefef`
  antes del arreglo, `#ffffff` después, en el panel de filtros/botones de
  cada una). Corregido sumando `contenido.setObjectName("panelSolapa")`
  en las tres construcciones (`reservas.py` ×2, `llaves.py`) — mismo
  criterio que `crud_generico.py`/`imagenes.py`, y sin necesidad de
  tocar los widgets nested más adentro (`panel_form`, los grupos de
  botones de Llaves, etc.): alcanza con que `contenido` lo tenga para
  que todo lo de adentro se vea blanco, la cascada ya la resuelve Qt en
  este caso puntual (a diferencia de `panel_izquierda` en
  `crud_generico.py`, que si necesitó su propio objectName aparte del de
  `contenido`/`panel_solapa`). Tests de regresión: mismo criterio de
  contar `QWidget` descendientes con `objectName() == "panelSolapa"`
  (`test_contenido_dentro_del_scroll_tiene_fondo_claro` en
  `test_gui_reservas.py`/`test_gui_llaves.py`).

De la lista original de pantallas con panel armado a mano, quedan
**Placas, Valores, Grilla operativa y Pagos** sin verificar todavía —
no usan `QScrollArea` para su panel principal (Placas sí lo usa, pero
solo para un cuadro de vista previa aparte), así que es esperable que ya
estén bien (mismo caso que Bloques rígidos), pero no se confirmó pantalla
por pantalla. Pedido explícito de la clienta: no hace falta un barrido
completo ahora — se sigue resolviendo a medida que se revisan. Si al
repasar alguna aparece el gris de más, el diagnóstico rápido es mirar si
`contenido` (el widget del `scroll.setWidget(...)`) tiene `panelSolapa`
puesto, y sumárselo si falta.

## Reordenamiento del menú "Operativa diaria" (pedido explícito de la clienta)

Sexto ajuste sobre el orden final del menú (después del renombre de
categorías "Sistema"/"Operativa diaria"): la clienta pidió un orden
puntual, distinto del que se había armado a criterio propio en esa
ronda, para las doce secciones de "Operativa diaria":

Grilla y mensajería, Reservas, Valores, Liquidaciones, Pagos, Registro
de ausencias, Disponibilidad, Profesionales, Llaves y otros conceptos,
Placas para timbres, Estadísticas, Balance del negocio.

Mismo mecanismo que el renombre de categorías (`VentanaPrincipal` arma
un separador de categoría cada vez que cambia respecto de la `Seccion`
anterior en la lista, no agrupa por nombre repetido) — alcanzó con
reordenar los doce bloques `Seccion` ya existentes dentro de
`construir_secciones()` (`gui_main.py`), sin tocar contenido de ninguno
(nombre, fábrica, ayuda). "Sistema" (5 secciones) no se tocó, sigue en
el mismo orden de siempre. Comentario de `construir_secciones` corregido
para reflejar que el orden de "Operativa diaria" es ahora un pedido
explícito de la clienta, no criterio propio.

Sin tests que actualizar: `test_categorias_son_solo_sistema_y_
operativa_diaria_y_van_contiguas` (`tests/test_gui_main.py`) solo
verifica que las categorías sean esas dos y que vayan contiguas, no el
orden interno de cada una — sigue pasando sin cambios.

## Capturas: sin sufijo "(pantalla completa)", a pantalla completa para
## varias pantallas más

Dos pedidos de la clienta sobre el criterio de capturas:

- **Nombre de archivo**: el sufijo "(pantalla completa)" que habían
  sumado las dos capturas de Placas de la ronda anterior se saca —
  vuelven al formato estándar de todo este documento, "{Sección} -
  {Formulario} - {Solapa}.png", igual al nombre con el que ya se
  descargan. El contenido (pantalla completa, con el menú a la
  izquierda) no cambió, solo el nombre del archivo.
- **Más pantallas a pantalla completa**: pedido explícito de "mandame de
  nuevo todas las solapas con el menú de navegación a la izquierda"
  para Valores, Registro de ausencias, Profesionales, Pagos y
  Estadísticas — mismo mecanismo que Placas (armar `VentanaPrincipal`
  de verdad vía `gui_main.construir_secciones()`, seleccionar la
  `Seccion` por su nombre en el menú lateral, `.grab()` sobre la
  ventana completa) aplicado a estas cinco. Sigue sin ser un cambio de
  convención retroactivo para el resto de las capturas ya enviadas —
  se aplica pantalla por pantalla, a medida que la clienta las pide de
  nuevo.

## DC-07 §2.5: Tipo Bloque de la grilla ignora DiasVisualizacion/DiasLogica — decisión consciente, sin tocar código

Hallazgo de la auditoría DC-01/DC-10 (#31, confirmado ❌ SIGUE en el v2):
"la grilla PDF ignora `DiasVisualizacion`/`DiasLogica`: clasifica
bloques rígidos solo por horario, sin distinguir por día". Investigado
antes de tocar nada: el bug es más profundo de lo que sugiere el texto
del hallazgo, y está duplicado en dos lugares, no solo en el PDF.

**Diagnóstico**: tanto `app/pdf/grilla_pdf.py` (`_tipo_bloque_por_hora`)
como `app/gui/widgets/grilla_operativa.py` (función homónima, misma
firma e idéntica lógica) clasifican cada hora como Rígido/Flexible
mirando únicamente si algún `BloqueRigido` activo cubre esa hora
(`HoraInicio <= h < HoraFin`), sin mirar `DiasLogica` ni
`DiasVisualizacion` en absoluto — la columna "Tipo Bloque" de la grilla
(PDF y GUI por igual) es una única columna por hora, COMPARTIDA por
todos los días que muestra la grilla, así que ni siquiera hay dónde
guardar un valor distinto por día con la estructura actual de la tabla.
El único arreglo de raíz sería convertir esa columna en una por cada
grupo de día (misma reestructuración necesaria en los dos archivos,
PDF y GUI) — alcance real mucho mayor que lo que sugiere el hallazgo
original.

Por qué nunca se notó con los datos de ejemplo: el bloque rígido default
de 18-21hs se siembra con `DiasLogica` = Lunes a Viernes pero
`DiasVisualizacion` = Lunes a Sábado (documentado a propósito desde que
se armó esta funcionalidad, ver `app/db/seed.py:
sembrar_bloques_rigidos` y el docstring de `bloques_rigidos.py` —
"puede ser más amplio que DiasLogica, como el default de 18-21hs") — y
`dias_grilla()` por defecto también es Lunes a Sábado, así que
`DiasVisualizacion` termina coincidiendo con TODOS los días que la
grilla muestra por defecto, ocultando el bug en cualquier captura o uso
con la configuración de fábrica. Solo se manifiesta con una
configuración real donde `DiasVisualizacion` no cubre todos los días
visibles de la grilla (ej. un bloque que se visualiza rígido L-V pero
no sábado).

**Decisión de la clienta, consultada antes de tocar nada** (dos
alcances posibles: arreglo completo en los dos archivos con columna por
día, o solo el PDF per el alcance literal del hallazgo): "No quiero
tocar nada de las grillas" — las dos opciones quedan descartadas, no se
toca ni `grilla_pdf.py` ni `grilla_operativa.py`. Como alternativa, dejó
abierta una simplificación de DATOS en vez de código (hacer que
`DiasLogica` del bloque de 18-21hs también incluya el sábado, para que
coincida con `DiasVisualizacion` y el desajuste deje de existir en la
práctica) — "si simplifica la lógica"/"eso si es necesario". Evaluado:
no hace falta — el desajuste entre `DiasLogica`/`DiasVisualizacion` del
dato semilla es intencional desde que se armó esta funcionalidad
(documentado en el propio docstring de `bloques_rigidos.py` como
ejemplo explícito de que los dos campos pueden diferir), así que
cambiarlo sería alterar sin necesidad un dato de ejemplo que hoy sirve
justamente para ilustrar esa distinción — se deja tal cual, con el
desajuste visual/lógico aceptado para el sábado 18-21hs (se ve rígido
en la grilla pero sigue siendo flexible a los efectos de
`verificar_bloques_rigidos`, sin el aviso que generaría si fuera rígido
de verdad ese día).

Mismo criterio que DC-07 §3.3 más arriba (decisión documentada, no un
bug): este hallazgo queda cerrado sin cambio de código.

## Auditoría DC-01/DC-10: hallazgos cosméticos #34, #35, #37, #38, #40, #45

Repaso de los hallazgos cosméticos que habían quedado "sin re-verificar"
en la auditoría (#34 a #46) — la clienta los revisó uno por uno,
eligiendo opción por ítem. Los que pedía "dejar así" (#36, #41, #43)
quedan documentados como decisión consciente, sin cambio de código,
mismo criterio que otras decisiones ya registradas en este archivo
(DC-07 §2.5/§3.3). Los de #39 (nombres de archivo), #42 (cargos
especiales en 4 posiciones) y #44 (checks "Combinar..." tildados por
defecto) quedaron pendientes de la clienta, que pidió ver ejemplos
antes de decidir — no implementados todavía.

- **#34 — "Saldo a favor... del profesional" de más**: en
  `liquidacion_pdf.py` (`_items_cuenta`), "Saldo a favor del profesional
  de la liquidación anterior" pasa a "Saldo a favor de la liquidación
  anterior" — mismo texto, sin la aclaración redundante, que ya usaba el
  Mensaje de texto equivalente (`mensajes.py`, "Saldo a favor mes
  anterior").
- **#35 — "Descuento feriado pendiente" vs "Descuento por feriado..."**:
  mismo prefijo que el feriado del mes en curso — pasa a "Descuento por
  feriado (mes anterior) - {día} {fecha}" en vez de una redacción
  distinta para el mismo concepto.
- **#36 — Ajuste saldo atrasado sin sufijo de período**: sin cambios
  (opción elegida por la clienta) — "Ajuste por saldo atrasado" se queda
  como está; el período ya queda implícito por la liquidación que lo
  contiene.
- **#37 — Cuota sin "/Total"**: "Cuota {N} del plan de pagos" pasa a
  "Cuota {N}/{Total} del plan de pagos". El total de cuotas
  (`PlanPago.CantidadCuotas`) no llegaba a esta consulta — se suma a la
  query de `CuotaPlan` en `liquidaciones.calcular_liquidacion` (join
  contra `PlanPago`, ya existente para resolver `IdProfesional`).
- **#38 — Edificio mencionado siempre, no solo si hay +1**: mismo
  criterio que ya usan Placas y el pie de foto de Oferta de
  consultorios, trasladado a `liquidacion_pdf.py`. `_lugar` suma un
  parámetro `mostrar_edificio` (default `True`, no rompe ningún llamador
  existente) que los cuatro `_texto_*` (horas agregadas, feriado
  trabajado actual/anterior, aislada) reenvían. `generar_pdf_
  liquidacion` lo calcula una sola vez por documento: la unión de los
  edificios de las reservas regulares (`edificios_bloques`, ya se
  calculaba ahí) con el edificio de cada ítem puntual de horas
  agregadas/feriados trabajados/aisladas — no alcanza con mirar solo las
  reservas regulares, una aislada en un edificio distinto del habitual
  también cuenta para la cuenta de "cuántos edificios distintos
  aparecen en este documento".
- **#40 — Período de valores nunca usa "al"**: el conector pasa de "y" a
  "al" en los dos PDFs que comparten `rango_actualizacion`
  (`liquidacion_pdf.py` y `propuesta_pdf.py`) — es un RANGO continuo
  (desde/hasta), no una lista de fechas sueltas, así que "al" describe
  mejor la relación que "y".
- **#41 — Localidad sin guiones**: sin cambios (opción elegida por la
  clienta) — sigue en su propia línea bajo el logo, sin "- Localidad -".
- **#42 — Cargos especiales en 2 posiciones**: pendiente, ver más abajo.
- **#43 — Punto final faltante**: sin cambios (opción elegida por la
  clienta) — "Corresponde a X, Y" se queda sin el punto final en
  `mensajes.py`.
- **#45 — Reserva aislada que cruza medianoche**: `crear_reserva_
  aislada` (`app/negocio/reservas.py`) suma una validación al principio
  (`hora_fin <= hora_inicio` → `ValueError`) — antes no se chequeaba en
  absoluto, y el formulario (dos `QDoubleSpinBox` independientes) de
  hecho dejaba cargar un horario cruzado (ej. 23 a 1), calculando un
  monto negativo en silencio. No se implementó el "partido en dos
  líneas" que pedía originalmente el documento (opción (a) elegida por
  la clienta: bloquear es más simple y evita el dato inconsistente; el
  caso de una reserva que de verdad cruza medianoche sigue sin estar
  soportado, pero ya no se puede cargar mal por error de tipeo). La GUI
  no necesitó ningún cambio: `_PanelReservasAisladas._crear` ya
  atrapaba `ValueError` y lo mostraba en un cartel, mismo mecanismo que
  cualquier otra validación de esta función.
- **#46 — Viñetas del Mensaje 2 Variante A**: cerrado sin acción —
  obsoleto, el mensaje se reescribió por completo en una ronda anterior
  (prosa plana, sin viñetas) y no queda estructura contra la cual
  comparar el hallazgo.

Tests nuevos: `tests/test_pdf_liquidacion.py` (`#34`: ajustada la
aserción existente de "a favor"; `#35`:
`test_feriado_pendiente_usa_el_mismo_prefijo_que_el_del_mes_en_curso`;
`#37`: `test_cuota_de_plan_muestra_numero_sobre_el_total`; `#38`:
`test_hora_aislada_omite_el_edificio_con_un_solo_edificio_en_el_
documento`/`test_hora_aislada_menciona_el_edificio_cuando_hay_mas_de_
uno`; `#40`: ajustada la aserción existente de frecuencia de
actualización). `tests/test_reservas.py` (`#45`:
`test_crear_reserva_aislada_que_cruza_medianoche_falla`/`test_crear_
reserva_aislada_hora_fin_igual_a_hora_inicio_falla`).

### #39, #42, #44: los tres resueltos (con ejemplos mostrados antes de implementar)

Los tres habían quedado pendientes de que la clienta viera ejemplos
concretos antes de elegir. Los tres ya se resolvieron sobre la
respuesta que dio viendo esos ejemplos.

- **#39 — Nombre de archivo de Liquidación, sin sufijo de código**:
  decisión final de la clienta, distinta de lo que sugería el hallazgo
  original ("le falta 'mensual'") — el nombre ideal que dio fue
  "2026-08 - Liquidación Lic. Marcela Lo Veci" (sin "mensual", sin el
  "R1" del código). `nombre_archivo_liquidacion` (`liquidacion_pdf.py`)
  saca el `sufijo_codigo` por completo — no hace falta para desambiguar:
  cada profesional ya tiene su propia carpeta
  (`Profesionales/{código}`), así que dos profesionales nunca comparten
  directorio aunque coincidiera su nombre. Propuesta/Disponibilidad
  quedan sin cambios, confirmado por la clienta ("ok así").

  Tests actualizados en `tests/test_pdf_liquidacion.py`:
  `test_nombre_archivo_sigue_el_formato_del_documento` (nuevo valor
  esperado, sin sufijo); `test_nombre_archivo_sin_codigo_no_agrega_
  sufijo` se renombra `test_nombre_archivo_nunca_agrega_sufijo_de_
  codigo` y suma `IdCodigo` al profesional de prueba para confirmar que
  el sufijo no aparece NI SIQUIERA cuando el profesional sí tiene
  código cargado (antes el test probaba el caso "sin código", que ya no
  es la distinción relevante).

- **#44 — Una línea por bloque continuo de horas (default sin
  combinar)**: la clienta confirmó el default destildado (ya era así)
  y agregó una precisión real sobre el contenido de esa línea, más allá
  de lo que mostraban mis ejemplos: no es "una línea por reserva aislada
  individual" sino "una línea por bloque CONTINUO de horas" — dos
  reservas del mismo consultorio sin ningún hueco entre medio (el
  `HoraFin` de una coincide con el `HoraInicio` de la siguiente, ej. 10
  a 12 y 12 a 14) tienen que verse como un único rango ("10 a 14hs"), no
  como dos líneas separadas. Esto es distinto de "Combinar misma
  unidad" (que fusiona TODAS las reservas de ese día/consultorio con
  "y de", continuas o no) — ese checkbox no se tocó, sigue con su
  comportamiento de siempre.

  `_agrupar_bloques_continuos` (nueva, `app/negocio/mensajes.py`)
  agrupa, por consultorio, las reservas de un día ordenadas por
  `HoraInicio` y las funde en un mismo bloque mientras no haya hueco;
  reemplaza al `[[f] for f in reservas_dia]` que usaba antes el camino
  SIN combinar (una fila por reserva, sin mirar continuidad).
  `_lineas_reservas_aisladas` arma el texto del horario de forma
  distinta según el camino: con "Combinar misma unidad" sigue uniendo
  con "y de" (sin cambios); sin combinar, arma un único rango de punta a
  punta del bloque (`HoraInicio` del primero a `HoraFin` del último) en
  vez de unir cada reserva por separado.

  Tests nuevos en `tests/test_mensajes.py`:
  `test_detalle_aislada_sin_combinar_une_bloque_continuo_en_una_sola_
  linea` (10-12 + 12-14 se muestran como "10 a 14hs", sin "y de");
  `test_detalle_aislada_sin_combinar_bloque_continuo_no_mezcla_
  consultorios` (la misma hora exacta en dos consultorios distintos NO
  se funde, cada consultorio agrupa sus propios bloques). El test
  preexistente de "sin combinar, cada reserva en su propia línea" usa
  horarios con hueco (10-12 y 14-16, no contiguos) — sigue pasando sin
  tocarlo, porque ese caso ya daba 2 líneas antes y sigue dando 2 líneas
  ahora (el cambio solo afecta a bloques genuinamente continuos).

- **#42 — Cargos especiales en 4 posiciones**: implementado, sí tocando
  lógica, base de datos y formulario (confirmado explícitamente en la
  pregunta de la clienta antes de avanzar — "Avanza con el proceso de
  las 4 posiciones en todo lo que necesites"). Antes solo existía la
  distinción implícita "con llave" (`IdLlave`, un solo concepto
  "Depósito de llave") / "sin llave" (todo lo demás, mostrado en el PDF
  como un único grupo "ítem libre"). Pasa a cuatro Subtipos reales:
  Depósito de llave / Ajuste / Bonificación / Ítem libre.

  `CargoEspecial` suma la columna `Subtipo` (`schema.sql` + migración en
  `app.db.migraciones`, mismo mecanismo `_COLUMNAS_NUEVAS` de siempre,
  default `'Ítem libre'`). Una base ya en uso no puede reclasificar
  retroactivamente Ajuste vs. Bonificación (son indistinguibles sin más
  dato que el `Concepto` de texto libre) — quedan todos en "Ítem libre",
  el default seguro. Lo que SÍ se puede reclasificar con certeza es
  "Depósito de llave": `_clasificar_subtipo_deposito_llave` (migración
  nueva, se llama al final de `aplicar_migraciones`) corre un `UPDATE`
  que pasa a ese Subtipo cualquier fila ya existente con `IdLlave` no
  nulo — sin este paso, una base vieja con depósitos de llave ya
  cargados los mostraría mezclados entre los "ítem libre" del PDF en
  vez de agrupados aparte, como siempre estuvieron.

  "Depósito de llave" sigue siendo exclusivo de `app.negocio.llaves`
  (`asignar_llave`/`devolver_llave`, los únicos dos puntos que crean un
  `CargoEspecial` con `id_llave`) — nunca una elección del operador.
  `crear_cargo_especial` (`app.negocio.pagos`) lo fuerza solo con que
  venga `id_llave`, sin importar qué `subtipo` se le pase (o ninguno);
  sin `id_llave`, exige uno de los otros tres, y si no se indica
  ninguno cae a "Ítem libre" (mismo default que la columna, para no
  romper a ningún llamador de antes de este pedido — ni `llaves.py`, que
  nunca pasó `subtipo`, ni los tests existentes). `registrar_perdida`
  (`app.negocio.llaves`) se revisó y confirmó que NO crea ningún
  `CargoEspecial` (da de baja stock o cierra una Asignación sin
  depósito involucrado) — no necesitó ningún cambio.

  GUI (`_PanelCargosEspeciales`, "Llaves y otros conceptos" → "Registro
  de cargos especiales"): combo nuevo "Subtipo", debajo de "Tipo",
  con los tres editables (Ajuste/Bonificación/Ítem libre — "Depósito de
  llave" nunca se ofrece ahí, es estructural) — sumado a la cadena de
  foco Enter/Tab en ese mismo lugar. La tabla gana una columna "Subtipo"
  (entre Tipo y Concepto, 7 columnas en total) y "Modificar cargo
  especial" precarga el combo con el Subtipo de la fila (un cargo
  "Depósito de llave" ya está bloqueado antes de llegar ahí por
  `_bloqueado_por_llave`, así que el combo nunca necesita ofrecer esa
  cuarta opción). `_PanelEstadoCuentaCargos` (misma pantalla, solapa
  "Estado de cuenta") suma la misma columna "Subtipo" a su tabla de
  solo lectura, mismo criterio de "mismos campos que Registro de cargos
  especiales" que ya documentaba esa clase.

  PDF (`liquidacion_pdf._items_cuenta`): los dos loops viejos
  (`IdLlave is None`/`is not None`) pasan a cuatro, uno por cada
  `Subtipo` en el orden fijo de `SUBTIPOS_CARGO` (Depósito de llave →
  Ajuste → Bonificación → Ítem libre) — mismo criterio de separación
  que ya usaba el Mensaje 1 de WhatsApp.

  Tests nuevos: `tests/test_pagos.py` (default a "Ítem libre" sin
  indicar subtipo, Ajuste/Bonificación se guardan tal cual, subtipo
  inválido se rechaza, "Depósito de llave" se rechaza sin `id_llave`,
  con `id_llave` se fuerza a "Depósito de llave" aunque se pase otro
  valor); `tests/test_migraciones.py` (una base vieja de `CargoEspecial`
  gana la columna con el default correcto, reclasificando solo la fila
  ligada a una llave); `tests/test_gui_novedades.py` (el combo ofrece
  los tres editables sin "Depósito de llave", crear con un subtipo
  elegido persiste y se ve en la tabla, modificar precarga el subtipo
  de la fila, más la actualización de índices de columna en los tests
  ya existentes de esa tabla); `tests/test_pdf_liquidacion.py`
  (los cuatro subtipos quedan en el orden fijo sin importar el orden de
  carga, además del test ya existente de "llave antes que libre", que
  sigue pasando sin tocarlo).

## Primera tanda de correcciones post-v1 (lógica ante todo, lo visual queda
## para otra ronda)

Ya con el sistema instalado y en uso real por primera vez, la clienta
empezó a anotar bugs/ajustes mientras seguía probando, con un pedido
explícito sobre el orden de trabajo: "me voy a tratar de concentrar más
en lo otro" (la lógica, no lo visual) y "no largues la nueva versión
hasta que yo te diga, solo hace las correcciones" — los diez puntos de
esta tanda se implementaron de punta a punta, pero sin dar por lanzada
ninguna versión nueva todavía.

### Ventana maximizada al iniciar

`gui_main.main()`: `ventana.show()` pasa a `ventana.showMaximized()`.
Pedido directo, sin alternativas que evaluar.

### Indicador visual de foco (acotado a botones, con el porqué documentado)

"Toco Tab, pasa de botón en botón, pero no veo dónde estoy parado."
Investigado antes de tocar nada: `hoja_estilos()` nunca había tenido
ninguna regla `:focus` — el estilo propio de `botonPrimario`/
`botonSecundario` (fondo + borde negro) le ganaba al rectángulo de foco
nativo que dibuja el estilo base de Qt, dejándolo invisible.

Se probó `outline` (en vez de `border`) a propósito: no ocupa espacio
de layout, así que un botón no "salta" un par de píxeles al ganar o
perder el foco (lo que sí pasaría agrandando el borde en `:focus`).
Color nuevo, `COLOR_FOCO = "#FFC107"` (ámbar) — ninguno de los colores
ya existentes (azul de marca, naranja de selección de fila, rojo de
alerta) servía sin generar confusión con otro significado ya asignado.

**Verificado con capturas reales antes de darlo por bueno** (mismo
criterio de todo este documento: medir, no asumir) — `outline` resultó
NO ser parejo entre tipos de widget en este Qt: se pinta bien en
`QPushButton` (confirmado con captura y con muestreo de píxeles), pero
no se pintó en absoluto en `QComboBox`/`QDateEdit`/`QSpinBox`/
`QCheckBox`/`QPlainTextEdit`/`QTextEdit`/`QTabBar::tab` (comprobado con
el mismo método de muestreo, ninguno mostró el color). `QLineEdit` no
necesitó nada: ya tenía su propio foco nativo visible (borde celeste)
desde antes.

Para esos otros tipos de widget SÍ hubiera funcionado `border`, pero a
costa de agregarles un borde (reservado, transparente cuando no hay
foco) que no tienen hoy — comprobado que eso les cambia el look en
reposo (pierden el marco nativo 3D/sundido que ya traían). Es un cambio
visual real, y la clienta pidió explícitamente concentrarse en lógica
por ahora — se dejó la regla acotada a `QPushButton:focus` nada más,
documentado en el propio comentario de `estilos.py` para que quede
registrado por qué no se generalizó, con el camino (border reservado)
ya investigado para cuando se retome en la ronda visual.

Tests: `test_boton_tiene_anillo_de_foco_en_la_hoja_de_estilos` (texto
del QSS) y `test_boton_primario_muestra_el_anillo_de_foco_al_recibir_
foco_real` (captura + muestreo de píxeles contra `COLOR_FOCO`, no solo
el texto — mismo motivo que el resto de esta sección: `outline` no se
garantiza parejo).

### Renombre del programa a "SistemaDF" (versión "v0.1")

Pedido explícito: el PROGRAMA pasa a llamarse "SistemaDF", sin importar
qué espacio lo use — distinto de `Configuracion.NombreEspacio` (el
nombre del NEGOCIO, editable desde la app, sigue siendo "Espacio Ramos
Consultorios" u otro que se cargue ahí). `app/version.py` (nuevo) es la
fuente única: `NOMBRE_PROGRAMA = "SistemaDF"`, `VERSION = "v0.1"`,
`NOMBRE_Y_VERSION` para el título de ventana.

Alcance del renombre — todo lo que es branding del PROGRAMA, nada que
sea branding del NEGOCIO:
- Título de la ventana principal (`VentanaPrincipal`, ahora "SistemaDF
  v0.1" — cumple de paso el pedido de mostrar la versión) y del diálogo
  de login ("SistemaDF — Ingresar"/"Crear administrador").
- Los dos `QMessageBox` de `gui_main.py` que usaban el nombre viejo como
  título (instancia ya abierta, ofrecer restaurar backup).
- El mensaje de `InstanciaYaAbierta` ("Ya hay otra sesión del sistema
  abierta...", sin el nombre viejo hardcodeado).
- El `ArgumentParser` de `main.py` (CLI).
- El nombre sugerido de la planilla de importación descargable
  (`Plantilla_Importacion_SistemaDF.xlsx`, en la GUI y como default del
  comando `generar-plantillas`).
- El spec de PyInstaller: `espacio_ramos.spec` se renombra
  `sistemadf.spec` (`git mv`, conserva el historial), y el nombre del
  `.exe`/la carpeta de salida pasan de `EspacioRamos`/`dist/EspacioRamos`
  a `SistemaDF`/`dist/SistemaDF`.
- Docstrings de `app/db/connection.py`/`app/repositorio/base.py` (solo
  texto, sin efecto en runtime).
- README.md y `docs/MANUAL_INSTALACION.md`: todas las rutas/comandos de
  ejemplo actualizados al nombre nuevo.

Lo que **no** se tocó, a propósito: `Configuracion.NombreEspacio` y su
fallback `"Espacio Ramos Consultorios"`/`"Espacio Ramos"` en
`oferta_busqueda_texto.py`/`pdf/estilos.py`/`pdf/placas_pdf.py`/
`pdf/oferta_pdf.py`/`pdf/propuesta_pdf.py`/`pdf/disponibilidad_pdf.py`
(el nombre del NEGOCIO, confirmado en cada uno que es eso y no
branding del programa) y el nombre del repositorio de GitHub (fuera del
alcance de este pedido, cambiarlo rompería la identidad de la sesión).

**Validado de nuevo tras el renombre** (mismo criterio que la primera
vez, ver sección de instalación): se volvió a correr `pyinstaller
sistemadf.spec` completo en este entorno Linux — build sin errores,
carpeta de salida y `.exe` ya con el nombre `SistemaDF`, arranque
offscreen limpio contra una base sin inicializar — confirma que el
renombre no rompió el empaquetado.

### Importación: no duplicar registros ya existentes

"Que no importe los registros que son iguales para evitar que se
dupliquen." Investigado: `importar_hoja` nunca había comparado contra
lo ya cargado — cada fila válida llamaba `repo.crear(**datos)` sin
condición, así que reimportar la misma planilla (o una que se
superpone) duplicaba todo sin avisar.

`_ya_existe_identico(conn, tabla, datos)` (nueva,
`app/importacion/importar_excel.py`): compara por igualdad EXACTA
(NULL incluido) contra la tabla, sobre todas las columnas presentes en
`datos` DESPUÉS de resolver referencias — "registros iguales", en el
sentido literal que pidió la clienta, no una coincidencia por clave
natural inventada. Una fila "parecida" pero con un solo campo distinto
(ej. un CampoLibre corregido) no cuenta como duplicado, se importa
igual. Se llama una sola vez, genérico para las ~12 entidades
importables (mismo nombre de entidad = nombre de tabla en todas), justo
antes del `try` que crea el registro — ANTES de cualquier columna que
la propia importación agregue sola (importa para Llave: el chequeo
corre sobre Tipo/ValorDepositoActual/Observacion, antes de que se le
asigne `Nombre` — autogenerado, siempre distinto, comparar con eso
nunca encontraría un duplicado real). Para PlanPago corre contra la
tabla `PlanPago` antes de `_crear_plan_pago_importado`, evitando
también duplicar sus `CuotaPlan`.

`ResultadoImportacion` suma `filas_duplicadas: int` (no se mezcla con
`errores` — un duplicado no es un error, es información). GUI
(`_PanelImportacion`): la tabla "Resultado por hoja" suma una columna
"Duplicados (no importados)", y el cartel final sincero sobre cuántas
filas se saltearon por ya existir. CLI (`main.py`): la línea de resumen
por hoja menciona el número de duplicados.

Tests: `tests/test_importacion.py` (reimportar la misma planilla no
duplica y lo reporta; una fila con un campo distinto SÍ se importa, no
cuenta como duplicado; Llave duplicada no se vuelve a crear pese a que
`Nombre` sería distinto en cada intento; PlanPago duplicado no genera
un segundo juego de `CuotaPlan`). `tests/test_gui_importacion.py` (la
columna nueva muestra el conteo correcto, antes y después de
reimportar).

### Tecla Delete = botón "Eliminar" (o su equivalente: Anular/Cancelar/
### Liberar/Descartar/Quitar), en todo el sistema

"Si presiono Delete en alguna fila de alguna tabla... que me ofrezca
eliminar como si tocara el botón 'Eliminar' de cada solapa." Mecanismo
nuevo y genérico, `app/gui/widgets/eliminar_tecla.py`
(`instalar_eliminar_con_tecla(widget, accion)`): instala un filtro de
eventos sobre la tabla (o lista) que, al recibir `Key_Delete`, llama
DIRECTO al mismo método que ya usa el botón correspondiente — no
duplica ninguna validación (selección vacía, confirmación, guardarraíl
de integridad referencial): es, literalmente, la misma llamada que ya
hacía el botón. Mismo criterio de referencia débil que `OrdenTabla`
(`app/gui/widgets/orden_tabla.py`) para `accion` — evita el mismo ciclo
panel → objeto → panel ya documentado ahí, con el mismo riesgo de
segfault al destruir muchos paneles seguidos (tests).

Sirve tanto para `QTableWidget` como para `QListWidget` (ej. la lista
de documentos de Profesionales, la lista de franjas de Oferta) — el
filtro de eventos no depende de ningún método propio de tabla.

**Cobertura, pantalla por pantalla** (la acción real detrás de Delete
varía: no todas las pantallas tienen un botón literal "Eliminar" — se
usó el botón equivalente más cercano de cada una):

- `crud_generico.PantallaCRUD` (un solo lugar, cubre de rebote TODOS
  los catálogos genéricos — Localidades/Edificios/Unidades/
  Consultorios/Responsables/Tipos de licencia/Condiciones y normas/
  Profesiones/Gastos operativos/Fechas especiales/Listas editables/
  Detalles complementarios/Mensajes predefinidos/Profesionales): Delete
  → `self._eliminar` (ya validaba selección y pedía confirmación, sin
  cambios ahí). En modo `solo_lectura` no se instala nada (no hay
  `_eliminar` que llamar).
- Reservas (`reservas.py`, las tres solapas): Regulares → `_finalizar_
  vigencia` (no hay "Eliminar" literal, es el equivalente real);
  Aisladas y Extraordinaria → `_cancelar`.
- Registro de ausencias (`novedades.py`, las cuatro tablas con alta):
  Vacaciones/Licencias/Ausencias → `_cancelar` (etiqueta de botón
  "Anular..."); Cargos especiales → `_eliminar`.
- Llaves (`llaves.py`): Tipos → `_eliminar_tipo`; Accesos → `_eliminar_
  acceso`. Movimientos no tiene ninguna acción de "sacar una fila" (es
  un historial), no se tocó.
- Pagos (`pagos.py`): Registrar pagos → `_eliminar`; Planes de pago →
  `_cancelar` ("Cancelar plan seleccionado"). Estado de cuenta es de
  solo lectura, sin acción, no se tocó.
- Placas para timbres (`placas.py`, solapa operativa): → `_liberar`
  ("Liberar posición de placa").
- Bloques rígidos (`bloques_rigidos.py`): → `_eliminar`.
- Gestor de archivos del espacio (`imagenes.py`): → `_eliminar`.
- Lista de espera (`lista_espera.py`): → `_descartar` ("Descartar
  pedido").
- Oferta de consultorios (`oferta.py`, lista "Franjas agregadas a esta
  búsqueda"): → `_quitar_franja_seleccionada`.
- Profesionales (`profesionales.py`, lista de documentación adjunta):
  → `_eliminar_documento`.

Pantallas revisadas y descartadas a propósito (sin ninguna acción de
"sacar una fila" que mapear): Estadísticas (solo lectura), Centro de
mensajería (solo marca "Enviada", no borra nada), Usuarios y permisos
(solo desactivar vía Editar, sin baja), Configuración general (no es
una tabla de registros). Los formularios compuestos que agrupan
pantallas ya cubiertas (Disponibilidad, Llaves y otros conceptos,
Grilla y mensajería, Base datos del espacio, Archivos y listas, Placas
para timbres, Balance del negocio, Valores) no necesitaron ningún
cambio propio — el cableado vive en el panel real que ya usan.

Tests: `tests/test_eliminar_tecla.py` (el mecanismo en sí: dispara con
Delete, no con otra tecla, no sostiene vivo al dueño del método atado
— mismo criterio de test que `OrdenTabla` —, y una tecla sin acción
viva no rompe nada). Un test de integración real (tecla de verdad vía
`qtbot.keyClick`, no llamar al método a mano) por cada pantalla recién
cableada: `test_crud_generico.py` (catálogo genérico, con y sin
selección, y confirmando que en modo `solo_lectura` no hace nada),
`test_gui_reservas.py` (las tres solapas), `test_gui_llaves.py`
(Tipos), `test_gui_pagos.py` (Registrar pagos).

### Botón "Restaurar backup" en Panel de control (elegir cuál, no
### siempre el más reciente)

Pedido explícito, siguiendo una sugerencia propia de una ronda
anterior: hasta ahora `restaurar_backup` solo se disparaba en dos vías
automáticas (instalación nueva, base desactualizada) y siempre tomaba
el backup MÁS RECIENTE, sin dejar elegir. Se refactorizó
`app/negocio/backup.py` sin romper ninguna de las dos vías existentes:

- `restaurar_backup_desde(origen, db_path)` (nueva): el mecanismo real
  de restauración sobre un backup YA ELEGIDO — extraído tal cual de lo
  que antes era el cuerpo de `restaurar_backup` después de encontrar
  `origen`, sin ningún cambio de comportamiento.
- `restaurar_backup(carpeta_backups, db_path)` (la de siempre, sin
  cambiar su firma ni su contrato): ahora es un wrapper de una línea
  — busca el más reciente y delega en `restaurar_backup_desde`.
- `listar_backups(carpeta)` (nueva): todas las subcarpetas "Backup
  AAAA-MM-DD HHhMM", de la más nueva a la más vieja — para ofrecer una
  lista real en vez de "siempre el último".

GUI (`_PanelAvancePeriodo.boton_restaurar`, debajo de "Generar backup
ahora", mismo ancho/criterio de fila con su propia explicación al
lado): elige carpeta (sugiere la ya configurada), lista los backups de
ahí (`listar_backups`), deja elegir uno (`QInputDialog.getItem`, el más
reciente como default), confirma con el nombre elegido y una
advertencia explícita de que el programa se va a cerrar.

**Por qué se cierra el programa después de restaurar** (no es una
limitación aceptada a medias, es la única forma segura con la
arquitectura actual): `self.conn` es la MISMA conexión SQLite
compartida por todos los paneles de la ventana ya construida — cerrarla
acá para poder sobreescribir el archivo (mismo motivo documentado para
las dos vías automáticas: una conexión abierta encima del archivo
puede fallar al reescribirlo, sobre todo en Windows) deja a cualquier
OTRO panel con una conexión muerta si se sigue usando el programa. No
hay forma de "pasarle" una conexión nueva a todos los paneles ya
armados, así que la única salida consistente es cerrar la aplicación
entera (`QApplication.instance().quit()`) después de restaurar — el
sistema operativo libera el lock de instancia única solo con que el
proceso termine, sin necesitar tocar `BloqueoInstanciaUnica` desde acá.

Tests: `tests/test_backup.py` (`listar_backups` — vacío sin carpeta/sin
backups, orden del más nuevo al más viejo; `restaurar_backup_desde`
elige puntualmente uno que NO es el más reciente, a diferencia de
`restaurar_backup`). `tests/test_gui_panel_control.py` (botón
secundario del mismo ancho que "Generar backup ahora"; cancelar en
cualquier paso no rompe ni toca la conexión; caso de punta a punta con
una conexión NUEVA después — ya que la vieja se cierra — confirmando
que el archivo en disco volvió al estado del backup elegido y que
`QApplication.quit` se llamó).

### Orden natural de códigos de profesional en tablas (letra + número
### completo, no dígito a dígito)

"X1, X10, X11, X2... no va. X1, X2, X3, X4, X10, X11... X234 sí va.
Primero por letra, después por la cadena de números completa." El
orden alfabético puro que usaban las tablas comparaba texto, así que
"R10" quedaba antes que "R2". Ya existía una versión correcta de esto,
pero aislada en un solo lugar (`mensajeria._clave_codigo`, para la
columna "Código" de Centro de mensajería) y con una limitación que
nunca se había notado porque ahí nunca hacía falta: solo funcionaba
con el código SOLO, se rompía si el texto traía algo más después (el
caso real en el resto del sistema: "R12 - Lic. Juan Pérez", la columna
"Profesional" con código + nombre juntos).

`clave_orden_codigo(texto)` (nueva, `app/gui/widgets/orden_tabla.py` —
mismo archivo que ya tenía `OrdenTabla`, concepto relacionado): separa
el prefijo alfabético del principio y la cadena de dígitos que sigue
(regex `^(\D*)(\d+)`, no "todo lo que sigue"), e ignora cualquier texto
después — por eso funciona igual de bien con un código solo ("R12") que
con código + nombre ("R12 - Lic. Juan Pérez"). Reemplaza a la versión
vieja de `mensajeria.py` (que se saca, sin otro usuario) y se aplica en
todos los lugares que ordenaban por código o por el texto combinado de
"Profesional":

- `crud_generico.py`: la columna `IdCodigo` del catálogo de
  Profesionales (por nombre de campo, no hizo falta un tipo de `Campo`
  nuevo — ningún otro catálogo tiene esta columna).
- `reservas.py` (las tres tablas, columna "Profesional"),
  `novedades.py` (las cuatro tablas, orden por click Y el orden por
  defecto al construir), `pagos.py` (las dos tablas), `placas.py`
  (columna "Profesional" armada aparte como texto), `llaves.py` (tabla
  de Movimientos, orden por click y por defecto).
- `liquidacion.py`: el orden por defecto de "Emisión de archivos" (no
  tiene click-to-sort) pasa de `_numero_codigo` (solo el número,
  ignorando la letra — podía mezclar categorías) a este.

Tests: `tests/test_orden_tabla.py` (la función en sí: número completo
no dígito a dígito, agrupa primero por letra, funciona con texto
después del código, sin número cae a orden de texto, vacío/`None` no
rompe). `tests/test_profesionales.py` (click en "Código" del catálogo
real ordena natural, no alfabético).

## Segunda tanda de correcciones post-v1

Siguiendo el mismo criterio de la primera tanda ("no largues la nueva
versión hasta que yo te diga, solo hace las correcciones"): cinco
puntos más, con los dos primeros ("buscar por código, no por nombre" +
"desplegable en cascada con negrita") y el tercero (jerarquía de
categorías) aplicados todos sobre el ÚNICO selector de profesional
compartido de todo el sistema (`habilitar_busqueda_profesional`,
`app/gui/widgets/selector_profesional.py`) — el cuarto punto de la
clienta ("esto aplica a todos los campos de búsqueda de profesional")
ya queda cumplido por construcción, es el mismo mecanismo que usan los
18 selectores de profesional del sistema (Reservas ×3, Novedades ×5,
Pagos ×3, Liquidaciones ×3, Llaves, Placas ×3, Lista de espera, Oferta,
Mensajes predefinidos, la Grilla operativa compartida), sin que haya
hecho falta tocar ninguno de ellos.

### Selector de profesional: solo por código (prefijo), select-all al
### enfocar, negrita en el desplegable

Pedido explícito de la clienta, con un ejemplo puntual: "si empiezo a
escribir Leandro no [tiene que encontrarlo], solo busca desde el
comienzo de la cadena {código – tratamiento nombre apellido}" — y la
pregunta de si esto se podía hacer. Se puede, y de la forma más simple:
el filtro, que hasta ahora matcheaba por CUALQUIER PARTE del texto
(`patron in texto`, buscaba por código O por nombre/apellido sueltos en
cualquier posición), pasa a matchear solo por PREFIJO de la cadena
canónica completa ("{código} - {tratamiento} {nombre} {apellido}",
`_normalizar(texto).startswith(patron)` en vez de `in`). Como el código
va siempre primero en esa cadena, esto habilita en los hechos "buscar
por código" (sigue funcionando: "R11" encuentra a "R11 - Lic. Leandro
Cervellini") y deshabilita "buscar por nombre" (escribir "Leandro" ya
no encuentra nada, porque no es el principio de la cadena) — exactamente
lo que pedía el ejemplo. Sigue sin distinguir mayúsculas ni acentos,
aplicado ahora al prefijo en vez de a cualquier parte.

Dos piezas más sobre el mismo widget, pedidas en el mismo mensaje:

- **Select-all al enfocar** ("apenas se pinche se seleccione todo el
  contenido, para poder borrarlo con Delete y escribir en limpio"):
  `_SeleccionarTodoAlEnfocar`, un filtro de eventos sobre el
  `QLineEdit` del combo que dispara `selectAll()` en `QEvent.FocusIn` —
  diferido con `QTimer.singleShot(0, ...)` porque un `selectAll()`
  inmediato durante el propio evento de foco queda pisado por el manejo
  nativo del click de Qt, que reposiciona el cursor en el punto
  clickeado justo después (confirmado al tanteo: sin el diferido, el
  texto quedaba deseleccionado).
- **Desplegable en cascada con negrita** ("si pongo R11, me muestra en
  cascada R11, R110, R112, R118... poniendo en negrita los caracteres
  que van coincidiendo"): el "en cascada" (varias coincidencias a la
  vez, bajar con las flechas, confirmar con Enter) ya lo daba gratis el
  `QCompleter` nativo en modo popup desde antes de este pedido — lo
  único que faltaba era la negrita. Como el filtro ahora es por
  PREFIJO, negritar "lo que va coincidiendo" se simplifica a negritar
  los primeros `len(patrón)` caracteres de cada opción (no hace falta
  ningún resaltado de substring en posición arbitraria, que sí hubiera
  hecho falta con el filtro viejo). `_DelegadoNegritaPrefijo`
  (`QStyledItemDelegate` puesto en `completador.popup()`) pinta el
  fondo/selección nativo de la fila y arriba el texto con un
  `QTextDocument` en HTML (`<b>{prefijo}</b>{resto}`), en vez de dejar
  que Qt pinte el texto plano.

  Pieza técnica encontrada al armar esto, no pedida pero necesaria:
  `combo.completer()` (el completer que `QComboBox` arma solo al volverlo
  editable) tiene su `popup()` en `None` hasta que se muestra por
  primera vez de verdad — no se le puede poner un delegado antes de eso.
  Se resolvió armando un `QCompleter()` nuevo aparte (que SÍ trae su
  popup armado desde el constructor, confirmado a mano) y asignándolo al
  combo con `combo.setCompleter(...)`, en vez de seguir reusando el que
  ya traía `combo.completer()`.

Tests reescritos de punta a punta en
`tests/test_gui_widget_selector_profesional.py` (los viejos, que
probaban "busca por cualquier parte"/"por nombre", dejaron de ser
ciertos y se reemplazan por sus opuestos): filtra por prefijo de
código, NO filtra por nombre en el medio de la cadena (ni en el
completer ni en la confirmación al perder el foco), select-all real al
enfocar (simulando el evento de foco, con `qtbot.wait` para el
`singleShot`), el popup del completer tiene el delegado de negrita
puesto.

**Corrección inmediata, mismo día**: la clienta aclaró que se había
expresado mal — el pedido real era al revés de lo recién implementado:
"quiero buscar por nombre también... quiero que busque DENTRO de la
cadena también y no solo al principio". El filtro vuelve a matchear
por CUALQUIER PARTE del texto (`patron in texto`, no `startswith`) —
tanto en el `QSortFilterProxyModel` del completer como en el fallback
de `_confirmar_texto` — recuperando el comportamiento original
("Leandro" vuelve a encontrar a "R11 - Lic. Leandro Cervellini") sin
perder nada de lo demás pedido en la misma tanda (select-all al
enfocar, negrita en el desplegable).

La negrita sí tuvo que cambiar de mecánica: con el filtro por
substring (no por prefijo), "lo que va coincidiendo" puede estar en
CUALQUIER posición de la cadena, no solo al principio — alcanzar con
negritar los primeros N caracteres (como permitía el prefijo) ya no
sirve. `_DelegadoNegritaPrefijo` se renombra `_DelegadoNegritaCoincidencia`
y suma `_rango_resaltado(texto, patron)` (nueva, en el mismo módulo):
busca la posición real del `patron` dentro del texto normalizado (sin
acentos, sin mayúsculas) y devuelve `(inicio, fin)` para resaltar esa
porción exacta del texto ORIGINAL — funciona porque `_normalizar`
preserva la longitud carácter a carácter para el texto típico de este
sistema (sacar tildes + `casefold()` no colapsa ni expande posiciones
para texto en español ya compuesto en NFC, que es como llega cualquier
nombre tipeado normalmente). Sin coincidencia, no se resalta nada.

Tests actualizados otra vez en
`tests/test_gui_widget_selector_profesional.py`: los que habían pasado
a probar "NO busca por nombre" se revierten a probar que SÍ busca
(mismos nombres de test que la primera versión, antes de esta tanda),
más dos tests nuevos para `_rango_resaltado` (encuentra la posición
real del substring, sin distinguir acentos, `None` sin coincidencia o
sin patrón) — el de select-all y el del delegado puesto se mantienen
sin cambios de fondo, solo el nombre de la clase que verifica el
segundo.

### Jerarquía de categorías B, R, A, E, X, C en los combos de profesional

Pedido explícito, "para todos los formularios": el ORDEN en que
aparecen las opciones de cualquier combo/selector de profesional tiene
que respetar primero la jerarquía de categorías B, R, A, E, X, C y,
dentro de cada categoría, el mismo orden natural de código que ya usan
las columnas "Profesional" de las tablas (`clave_orden_codigo`, de la
tanda anterior) — sin tocar qué categorías ofrece cada pantalla (cada
una sigue restringida a su propio subconjunto, ej. Aisladas sigue en
R/A, Vacaciones en R/B/E; la jerarquía solo decide el orden DENTRO de
lo que cada pantalla ya elige mostrar).

`clave_orden_profesional(categoria, codigo)` (nueva, `app/gui/widgets/
orden_tabla.py`, al lado de `clave_orden_codigo`): combina un dict fijo
`ORDEN_CATEGORIA_PROFESIONAL = {"B":0,"R":1,"A":2,"E":3,"X":4,"C":5}`
con el orden natural de código ya existente. Reemplaza el `ORDER BY
Apellido` que tenían las tres funciones que arman listas de
profesionales para combos (`reservas._opciones_profesional` — la
compartida, reusada por cross-import en la mayoría de las pantallas;
`grilla_operativa._opciones_profesional_grilla` y `novedades.
_opciones_profesional_vacaciones`, duplicadas por los mismos motivos de
import circular/filtro propio ya documentados en el código) — las tres
pasan a traer `CategoriaProfesional` en el SELECT y ordenar en Python
con esta función en vez de alfabéticamente por apellido.

Tests: ningún test nuevo dedicado (no hay una función de negocio
aislada más allá de `clave_orden_profesional` en sí, cubierta
indirectamente por los tests ya existentes de cada pantalla que
siguieron pasando sin tocarlos — confirmado corriendo la suite
completa de Reservas/Novedades/Grilla operativa/Oferta/Lista de
espera/Pagos/Llaves/Placas/Liquidación/Mensajes predefinidos después
del cambio, sin ninguna regresión).

### Panel de control: séptimo cuadrito, "Cumpleaños y días de profesión"

Pedido explícito de la clienta: "un cuadrito similar a los que
están... que me vaya indicando por orden de cercanía los cumpleaños de
los profesionales activos en el espacio... y los días del psicólogo,
del fonoaudiólogo, etc." Dos fuentes de datos muy distintas en la misma
lista, ordenadas juntas por cercanía:

- **Cumpleaños**: de `Profesional.FechaNacimiento` (ya existía en el
  schema). "Profesionales activos en el espacio" se interpretó como
  "sin importar la categoría salvo las dos que no son un profesional
  usando el espacio de verdad": se excluyen categoría X (Inactivo) y C
  (Contacto/prospecto, todavía no se le dio de alta como alguien que
  reserva) — quedan R, A, B, E.
- **Días de profesión**: pedido sin resolver de antemano ("quedo atento
  a alguna sugerencia de cómo armar esto de la manera más simple"). Se
  sumó `Profesion.DiaProfesion` (TEXT, "MM-DD" SIN año — ej. "10-13"
  para el 13 de octubre, se repite igual todos los años, a diferencia
  de `FechasEspeciales` que guarda fechas puntuales de un año concreto)
  como campo nuevo y OPCIONAL del catálogo "Profesiones y tratamientos"
  (`catalogos.pantalla_profesiones`), en vez de hardcodear un diccionario
  en Python — mismo criterio de "dato editable desde el sistema, no en
  código" que el resto del proyecto (campos libres, Listas editables,
  etc.): para sumar o corregir un día de profesión no hace falta tocar
  nada de código, se carga desde la pantalla. Validado con un validador
  nuevo, `es_dia_mes_valido`/`FORMATO_DIA_MES` (`app.negocio.
  validaciones`, mismo mecanismo `Campo.validador`/`formato_esperado`
  que ya usan Email/CUIT/DNI en los catálogos) — valida contra un año
  bisiesto de referencia (2024) para no rechazar un 29 de febrero. Una
  profesión sin este dato cargado simplemente no aparece en el
  cuadrito.

**Redacción, corregida el mismo día a pedido de la clienta** ("prefiero
algo más coloquial si se puede, sino complica dejalo así como lo
planteaste"): la primera versión armaba el texto como "Día de la
profesión: {Nombre}" (reusando el nombre de la disciplina, ej. "Día de
la profesión: Psicología") para no tener que resolver el género del
título ("Día del"/"Día de la"). Resultó no complicar: `Profesion.
NombreMasculino` YA existe en el catálogo (sembrado para cada profesión,
ej. "Psicólogo" para Psicología) — "del" contrae correctamente con
cualquier nombre marcado como masculino sin importar con qué letra
empiece, así que `f"Día del {NombreMasculino}"` es gramaticalmente
válido sin tener que inventar ninguna regla de género ni sumar ningún
campo nuevo. Sin `NombreMasculino` cargado para esa profesión puntual,
cae al genérico "Día de la profesión: {Nombre}" de la primera versión,
en vez de romper o mostrar "Día del None".

`app.negocio.panel_control.cumpleanos_y_dias_profesion_proximos(conn,
meses_ventana=2)` (nueva): mismo criterio de ventana que `fechas_
especiales_proximas_dos_meses` (lo que queda del mes en curso + los
próximos dos meses) — `_proxima_ocurrencia(hoy, mes, dia)` calcula la
próxima fecha futura (hoy inclusive) en que cae ese mes/día sin
importar el año, probando hasta 8 años para adelante (cubre de sobra un
29 de febrero, que como mucho tarda 4 años en volver a existir). Las
dos listas (cumpleaños + días de profesión) se mezclan en una sola,
ordenada por `dias_restantes` ascendente.

GUI (`app/gui/pantallas/panel_control.py`): séptimo cuadrito,
`_armar_tarjeta_cumpleanos`/`etiqueta_cumpleanos`, mismo patrón
`_tarjeta`/`QLabel` con `setWordWrap` que el resto — el armado de la
grilla (`_COLUMNAS_GRILLA = 3`, cálculo de filas por redondeo hacia
arriba) ya era genérico sobre la cantidad de tarjetas, así que pasar de
6 a 7 no necesitó ningún cambio ahí; el séptimo cuadrito queda solo en
su propia fila, sin ningún otro al lado.

Tests: `tests/test_panel_control.py` (`_proxima_ocurrencia` — dentro
del mismo año, hoy cuenta como próxima, ya pasó este año salta al que
viene, 29 de febrero salta al próximo bisiesto; `cumpleanos_y_dias_
profesion_proximos` — cumpleaños de categoría activa aparece con los
datos correctos, X/C quedan afuera, fuera de la ventana de dos meses no
aparece, día de profesión cargado aparece/sin cargar no aparece,
cumpleaños y días de profesión se mezclan ordenados por cercanía).
`tests/test_gui_panel_control.py` (cuadrito sin datos muestra el
mensaje default, con datos lista ambos tipos de evento; el test
estructural de "seis tarjetas parejas" se renombra y actualiza a
siete). `tests/test_catalogos.py` (el campo nuevo existe en
"Profesiones y tratamientos" con su validador puesto). `tests/
test_validaciones.py` (`es_dia_mes_valido`, formatos válidos/
inválidos, incluyendo el caso del 29 de febrero). De paso se sumó
`DiaProfesion` a `COLUMNAS_PLANTILLA["Profesion"]`
(`app.importacion.definiciones`) para que la plantilla de importación
Excel también lo contemple, mismo criterio que los campos libres.

### Fuente fija de toda la app (independiza los tamaños de a qué máquina se mude la clienta)

Pregunta de la clienta, surgida al notar diferencias entre lo que se
había afinado pixel a pixel durante toda la revisión "uno por uno" (ver
las decenas de rondas de calibración documentadas más arriba, sobre
todo Reservas/Oferta) y lo que se ve en la versión instalada: "¿se
puede regular los tamaños dentro del sistema?" — seguido de una
precisión importante al confirmar que el problema real era de fuente/
DPI, no de un tamaño puntual: "puedo cambiar de máquina y monitor, por
ahí caigo en un Windows 11 al 100%, ¿cómo se puede manejar mejor este
tema?"

**Diagnóstico, antes de proponer nada**: `estilos.py` nunca fijó una
`font-family` en ningún lado — toda la app corre con la fuente DEFAULT
del sistema operativo donde se ejecuta. Cada ancho/alto fijo a mano que
se calibró durante toda la revisión ("ancho justo para que entre el
texto más largo sin cortarse") se midió en este entorno de desarrollo
(Linux, sin interfaz gráfica real, plataforma `offscreen` de Qt), que
usa una fuente genérica de Linux — DISTINTA a la que usa Windows por
default ("Segoe UI" desde Windows Vista). Esa diferencia de métricas de
fuente (ancho real de cada letra) es lo que corre los números, no el
125%/100% de escala de Windows en sí: Qt6 (la versión que usa PySide6
en este proyecto) escala automáticamente los tamaños en píxeles lógicos
por el factor de DPI del sistema — un ancho fijo de 220px y el texto
que tiene que entrar ahí escalan JUNTOS al mismo factor, así que pasar
de 100% a 125%, o de una máquina a otra con otra escala, no debería por
sí solo desalinear nada — lo que sí desalinea es que la fuente real
nunca fue la misma que se usó para medir.

**Dos cambios, los dos en `gui_main.main()`, antes de crear la
`QApplication`** (tienen que fijarse ahí, después no tienen efecto):

- `app.setFont(QFont(FUENTE_APP))` — `FUENTE_APP = "Segoe UI"`
  (`app.gui.estilos`, nueva constante, al lado de los demás colores):
  fija la fuente de toda la aplicación en vez de dejarla a la default
  de cada instalación. "Segoe UI" viene instalada de fábrica en
  Windows 7 en adelante — Windows 10 Y Windows 11 la tienen por igual,
  así que cambiar de máquina/monitor entre esas dos versiones deja de
  importar para este propósito: el ancho real del texto va a ser
  siempre el mismo. Elegido por `app.setFont(...)` (fuente default de
  la aplicación entera) en vez de threadearlo como `font-family` dentro
  de `hoja_estilos()`: esa hoja de estilos solo se aplica con
  `self.setStyleSheet(...)` sobre `VentanaPrincipal` (`app/gui/
  main_window.py`), así que cualquier diálogo construido sin colgar de
  ese árbol de widgets (bastante comunes en este sistema, ej. los
  `_Dialogo*` de Nuevo/Editar) podía quedar afuera de ese alcance —
  `app.setFont(...)` fija el default de TODA la aplicación, sin
  depender de qué widget sea ancestro de qué otro, y además es lo que
  usa por default cualquier `QFontMetrics()` construido sin argumentos
  en el código (los cálculos manuales de ancho que ya existen en varias
  pantallas).
- `QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.
  HighDpiScaleFactorRoundingPolicy.PassThrough)` — ya es el default de
  Qt6 (no hacía falta para que funcione), se fija de forma explícita
  para que quede documentada la intención en el propio código y no
  dependa de que una futura actualización de Qt cambie ese default sin
  que nadie se entere: con `PassThrough`, un factor de escala
  fraccionario (125%, 150%) no introduce un redondeo de más entre el
  tamaño lógico que ya se calibró y el tamaño físico en pantalla.

**Sin "Segoe UI" instalada** (ej. corriendo este mismo código en Linux,
como en este entorno de desarrollo): Qt sustituye sola la fuente más
parecida que encuentre, sin romper — solo deja de ser pixel-perfect en
ese caso puntual, que es exactamente la situación que ya existía antes
de este cambio y que va a seguir existiendo únicamente ahí (nunca en
una instalación real de Windows).

**Lo que este cambio NO resuelve, aclarado a la clienta de entrada**:
fijar la fuente hace que los tamaños queden ESTABLES de acá en
adelante (la misma fuente, siempre, en cualquier máquina Windows) —
pero no corrige retroactivamente ningún desajuste que ya exista entre
lo calibrado contra la fuente de Linux y lo que realmente necesita
"Segoe UI" (que es más ancha en promedio que la mayoría de las fuentes
default de Linux). Una vuelta de validación visual sobre la instalación
real (mismo criterio "uno por uno" de siempre: la clienta señala qué
pantalla/campo quedó corto o desalineado, se corrige puntualmente) va
a seguir haciendo falta — este cambio evita que ese trabajo haya que
repetirlo cada vez que se cambia de máquina, no lo saltea. Se descartó,
por ahora, un control de "escala de interfaz" general dentro de
Configuración (multiplicar todos los anchos fijos por un factor
elegible) — mucho más trabajo (revisar decenas de constantes en todas
las pantallas) para resolver un problema que la fuente fija ya ataca de
raíz.

Tests: `tests/test_gui_estilos.py`
(`test_fuente_app_fijada_a_segoe_ui`). Las dos líneas nuevas de
`gui_main.main()` en sí no tienen test dedicado — ese punto de entrada
nunca se probó de punta a punta en este proyecto (requiere boostrapear
una base, el diálogo de login, etc.), mismo criterio que otras llamadas
directas ya existentes ahí (`ventana.showMaximized()`); se verificó a
mano que `QGuiApplication.setHighDpiScaleFactorRoundingPolicy` +
`app.setFont(QFont("Segoe UI"))` no rompen la `QApplication` bajo la
plataforma `offscreen`.

## Quinta tanda de correcciones post-v1: Valores vigentes, Pagos, Registro de
## ausencias

Nueva ronda de feedback sobre el build instalado, con el mismo criterio de
siempre ("dale para adelante con todo... cuando terminemos de revisar la
primera tanda de solapas vamos con otra versión de prueba").

### Valores vigentes: filtro colapsable no corre más la tabla de la derecha

Hallazgo real (#54, ya venía pendiente de la tanda anterior): el panel
"Filtros" de esta solapa (`_PanelFiltrosJerarquico`, cuatro `_FiltroColapsable`
en cascada — Localidad/Edificio/Unidad/Consultorio) solo tenía un
`setMaximumWidth(260)` — colapsado se achicaba por debajo de ese tope
(ancho natural, más angosto que el botón-resumen más largo) y volvía a
ensancharse hasta 260px al desplegar una lista con nombres largos. En el
`QHBoxLayout` de `_PanelValoresVigentes` (Filtros | Promedios | tabla de
Valores, esta última con `stretch=1`), ese ensanche se lo quitaba a la
tabla — exactamente "correrse la tabla de la derecha". Mismo criterio ya
usado para este mismo problema en el panel de Filtros de Oferta de
consultorios: `setMaximumWidth` pasa a `setFixedWidth(260)`, siempre el
mismo ancho, colapsado o desplegado.

### Pagos: Registrar pagos (diálogo de modificar, botones deshabilitados,
### confirmaciones), Planes de pago (diálogos por fila seleccionada)

**Registrar pagos**: el selector de profesional y el foco visible en
botones ya estaban cubiertos por los mecanismos compartidos de rondas
anteriores — nada que tocar ahí. Lo nuevo:

- **"Modificar pago"/"Eliminar pago" deshabilitados sin selección,
  "Deshacer último movimiento" sin movimientos**: `boton_modificar`/
  `boton_eliminar`/`boton_deshacer` pasan a atributos `self.` (antes
  variables locales de `_armar_ui`) y suman `_actualizar_botones()`
  (conectado a `tabla.itemSelectionChanged` y llamado al final de
  `actualizar()`) — sin selección, los dos primeros quedan grises; sin
  ningún registro, el tercero también. Como `_EnterAvanzaFoco._mover`
  ya salteaba widgets deshabilitados desde que se armó ese mecanismo,
  "desseleccionables con el tabulador" sale gratis con solo
  `setEnabled(False)`, sin tocar `foco.py`.
- **"Modificar pago" pasa a un cuadro de diálogo propio**
  (`_DialogoModificarPago`): antes reusaba los campos del formulario de
  alta de la izquierda (que además precargaba sola `_precargar_seleccion`
  al elegir una fila) — ahora ese formulario queda exclusivo de
  "Registrar pago" nuevo, sin precargarse con nada al seleccionar una
  fila (`_actualizar_botones` reemplaza a `_precargar_seleccion`, que se
  borra). El diálogo trae Período imputado/Monto/Medio de pago/Cuenta
  receptora precargados del registro elegido (Profesional y fecha de
  carga se muestran de solo lectura, nunca se tocan — `modificar_pago`
  tampoco los cambia) y valida igual que antes de confirmar.
- **"Eliminar pago" con alerta explícita sobre el impacto en la cuenta**:
  confirmado que `eliminar_pago`/`modificar_pago` (`app.negocio.pagos`)
  YA revertían correctamente según `PeriodoImputado` del pago
  (`SaldoCuentaAnterior` si es anterior al mes en curso, `SaldoCuentaActual`
  si no, vía `_campo_saldo`) — el pedido de la clienta ("ojo con eso, hay
  que revertir de acuerdo al período en el cual se había imputado") ya
  estaba bien resuelto en la capa de negocio, solo faltaba que el cartel
  lo dijera: ahora menciona el profesional, el monto, el período imputado
  y a qué saldo específico se devuelve.
- **Confirmación antes de registrar un pago nuevo**
  (`confirmar_datos_antes_de_crear`, mismo mecanismo de Reservas): se
  suma también a "Guardar nuevo plan de pagos" de la otra solapa, por
  consistencia dentro del mismo formulario que se estaba revisando.

**Planes de pago**: "Refinanciar plan seleccionado"/"Cancelar plan
seleccionado" dejan de habilitarse según si el profesional del COMBO
tiene un plan activo (`plan_activo_de`) y pasan a habilitarse según la
FILA elegida en la TABLA (`_fila_seleccionada_plan`/`_actualizar_botones_fila`,
solo si `Estado == "Activo"`) — bug latente de rebote: antes, con la
tecla Delete (atada a `_cancelar`) o con el combo apuntando a otro
profesional distinto del resaltado en la tabla, se podía cancelar un
plan que no era el que se veía seleccionado. "Refinanciar" abre
`_DialogoRefinanciarPlan` (Monto a refinanciar/Cantidad de cuotas/%
Interés, con el mismo monto sugerido de siempre — saldo atrasado + cuotas
pendientes del plan a reemplazar, movido acá desde `_profesional_cambio`)
en vez de leer los campos sueltos de la columna izquierda, que ahora son
exclusivos de "Guardar nuevo plan de pagos". "Cancelar" suma un cartel de
confirmación explícito (antes cancelaba directo, sin preguntar nada)
explicando que las cuotas pendientes vuelven a sumarse como saldo
atrasado.

**Estado de cuenta**: investigado el pedido de "que no corra el ancho al
pinchar en el cuadro" — el combo de profesional ya tiene `setFixedWidth`
desde siempre, no se encontró ningún mecanismo real en el código que
pudiera correrlo. Sin poder reproducirlo en este entorno, queda
documentado por si vuelve a aparecer en la instalación real (si persiste,
hace falta una captura puntual).

Tests: `tests/test_gui_pagos.py` reescribe los tests que asumían el
viejo comportamiento (selección precarga el formulario, refinanciar/
cancelar por combo) y suma un helper `_DialogoFalso`/`_mockear_dialogo_
modificar`/`_mockear_dialogo_refinanciar` (reemplaza, en los tests, a los
`QDialog` reales — `exec()` devuelve el resultado ya decidido sin abrir
ninguna ventana) para poder probar los flujos de diálogo sin bloquear.
El fixture `_sin_dialogos_modales` de este archivo suma `QMessageBox.
question` por default a "Yes" (antes solo lo mockeaban los tests
puntuales que ya lo necesitaban) — con la confirmación nueva en el
camino feliz de "Registrar pago"/"Guardar nuevo plan de pagos", cualquier
test que llamara a esos métodos sin mockear `question` quedaba
bloqueado esperando una respuesta real.

### Registro de ausencias: Vacaciones, Licencias, Ausencias

- **Vacaciones**: "Crear vacaciones" suma la misma confirmación
  (`confirmar_datos_antes_de_crear`) que el resto del sistema.
  Investigado el reparto de una vacación que cruza fin de mes (ejemplo de
  la clienta: 20/10 al 5/11, 20-31/10 en octubre y 1-5/11 en noviembre) —
  confirmado que `app.negocio.liquidaciones._calcular_descuento_vacaciones`/
  `_prorratear_valor_bonificado` YA lo hacían bien desde antes (DC-05
  §1.6): prorratea el `ValorBonificado` ya congelado según qué proporción
  del BRUTO ponderado por día cae en cada período — con horas constantes
  durante toda la vacación esto coincide exactamente con un prorrateo por
  días corridos como el del ejemplo, y generaliza mejor si el profesional
  cambia de consultorio o de cantidad de días reservados a mitad de la
  vacación. No fue necesario ningún cambio de código para este punto —
  quedó confirmado, no corregido.
- **Vacaciones/Licencias, regenerar liquidación del período actual**: ya
  estaba resuelto para Vacaciones (`_crear`/`_cancelar_registro` ya
  llamaban `regenerar_si_corresponde`) pero faltaba en Licencias — hueco
  real, corregido con el mismo mecanismo exacto.
- **Licencias, "Hasta" llevaba al año 2000 al abrir el calendario**: bug
  real, mismo patrón en Reservas regulares ("Vigencia hasta") — los dos
  campos usan el sentinel `_FECHA_SIN_DATO` (`QDate(2000, 1, 1)`) para
  "(sin fecha)", y el popup de calendario arrancaba siempre en esa
  página mientras el campo no tuviera una fecha real cargada. Qt
  sincroniza la página visible del calendario con `date()` al armar el
  popup, antes de mostrarlo — `_FiltroCalendarioArrancaHoy`/
  `_instalar_calendario_arranca_hoy` (nuevos, `reservas.py`, importado
  cruzado en `novedades.py`) se instala como event filter sobre
  `campo.calendarWidget()` y, en su evento Show, si el campo sigue en el
  sentinel, llama `setCurrentPage(hoy.year, hoy.month)` — solo cambia qué
  página se VE, nunca el valor real del campo ni el sentinel.
- **Ausencias por motivos varios**: mismo patrón que Pagos/Vacaciones —
  "Crear ausencia" suma confirmación, "Modificar ausencia seleccionada"/
  "Anular ausencia seleccionada" quedan deshabilitados sin fila elegida
  en la tabla (`boton_modificar`/`boton_cancelar` pasan a `self.`,
  `_actualizar_botones` nueva).
- **Tipos de licencia**: catálogo genérico anidado, sin selector de
  profesional propio — nada que tocar ahí.

Tests: `tests/test_gui_reservas.py`/`tests/test_gui_novedades.py` suman
los del calendario (simulando el evento Show a mano con `QApplication.
sendEvent` — un `.show()` directo sobre el `QCalendarWidget` de un
`QDateTimeEdit`, pensado para mostrarse solo como popup nativo, no
siempre entrega el evento esperado) y los de confirmación/regeneración/
botones deshabilitados, mismo criterio que rondas anteriores.

## Sexta tanda de correcciones post-v1: Valores vigentes, Liquidaciones,
## Fechas especiales

### Valores vigentes: filtro colapsable corría la tabla (#54/#55)

`_PanelFiltrosJerarquico` solo tenía `setMaximumWidth(260)` en vez de
`setFixedWidth(260)` — en estado colapsado (el default) el panel se
achicaba a su ancho natural, más angosto que 260px, así que desplegar
cualquiera de los 4 `_FiltroColapsable` (Localidad/Edificio/Unidad/
Consultorio) con nombres largos lo empujaba de vuelta hacia 260px,
corriendo "Valores vigentes por horas regulares y aisladas" (el único
widget con `stretch=1` del `QHBoxLayout`) hacia la derecha — mismo bug
ya documentado y corregido en su momento para Oferta de consultorios.
Se corrige con `setFixedWidth`, igual que esa pantalla.

De paso, ninguna de las dos tablas de esta solapa (`tabla_valores` de
`_PanelValoresVigentes`, la de `_PanelPromedios`) tenía nunca excluida
del tab-chain nativo — Tab podía entrar a ellas y, una vez dentro,
navegar celda por celda en vez de saltar al siguiente control real de
la pantalla. `setFocusPolicy(Qt.FocusPolicy.ClickFocus)` +
`setTabKeyNavigation(True)` en las dos (mismo criterio ya usado en
otras tablas de solo lectura del sistema): Tab ya no entra, un click
sigue pudiendo seleccionar una fila.

### Liquidaciones: "Monto a generar" no coincidía con el PDF (#58)

`LiquidacionCalculada.monto_generado` ("lo que esta emisión aporta por
sí sola, SIN saldo anterior" — el valor que de verdad se persiste en
`LiquidacionEmitida.MontoGenerado`, crítico para el mecanismo de delta
de `emitir_liquidacion` en una reemisión) y `.total` (`saldo_anterior +
monto_generado`, lo que el PDF realmente pone en letras) son dos cosas
distintas a propósito — la columna "Monto a generar" de la vista previa
de "Emisión de archivos" mostraba la primera, pero la clienta esperaba
ver el mismo número que el PDF. Se corrige SOLO en la columna de la
vista previa (`_PanelEmisionArchivos.actualizar()` pasa a leer
`liquidacion.total`) — lo que se persiste y el mecanismo de reemisión
no se tocan.

### Liquidaciones: "Emitir liquidaciones seleccionadas" sin selección (#60)

El botón quedaba siempre habilitado, aunque ningún check de la tabla
estuviera tildado — `boton_emitir_seleccionadas` pasa a `self.`,
arranca deshabilitado, y una nueva `_actualizar_boton_seleccionadas`
(conectada a `tabla.itemChanged`, llamada también al final de
`actualizar()`) lo habilita solo si hay al menos un check tildado.
Cuidado al armar esto: `itemChanged` dispara en medio del propio loop
de `actualizar()` que puebla la tabla fila por fila (`setItem` en la
fila N dispara el evento antes de que la fila N+1 tenga su item en la
columna 0 todavía) — `any(...)` necesita filtrar `item is not None`
antes de preguntar `.checkState()`, si no tira `AttributeError` sobre
`None`.

### Selector de período Año + Mes, reemplaza el texto libre "AAAA-MM" (#59)

Pedido de la clienta: poder elegir el período con un desplegable de
año y uno de mes, en vez de tipear "AAAA-MM" a mano. `SelectorPeriodo`
(`app/gui/widgets/selector_periodo.py`, nuevo) es un `QWidget` chico y
reusable — `QSpinBox` (año, 2000-2100) + `QComboBox` (mes, "Enero" a
"Diciembre"), arranca en `periodo_actual(conn)` (respeta la fecha
ficticia de QA), expone `periodo()`/`set_periodo(...)` con el mismo
formato "AAAA-MM" que usa el resto del sistema, y una señal `cambiado`
que se emite al tocar cualquiera de los dos — pensado para reemplazar,
de a una, cualquier otro campo de período en texto libre del sistema;
por ahora solo se integra en "Emisión de archivos" (Liquidaciones), el
caso puntual que pidió la clienta primero.

`campo_periodo` (`_PanelEmisionArchivos`) pasa de `QLineEdit` a
`SelectorPeriodo`; `_periodo()` pasa de leer `.text()` a `.periodo()`;
la cadena de foco suma `campo_periodo.spin_anio`/`.combo_mes` como dos
entradas separadas en el lugar donde antes había una sola. "Período a
simular" (Liquidaciones simuladas, otra solapa del mismo formulario)
NO se tocó — sigue en texto libre, es un campo distinto, sin relación.

Bug de conexión encontrado al armarlo: `QSpinBox.valueChanged`/
`QComboBox.currentIndexChanged` pasan el valor nuevo como argumento al
slot conectado — conectarlos directo a `self.cambiado.emit` (una señal
de 0 argumentos) tira `TypeError: cambiado() only accepts 0 argument(s),
1 given!` en cuanto se toca el spin/combo. Se resuelve con
`_emitir_cambiado(self, *_args)` como intermediario.

### Fechas especiales: aviso de regeneración antes de confirmar (#61)

Mismo criterio ya usado en Aumentos: antes de guardar un alta/edición/
baja que afecte una fecha del PERÍODO ACTUAL, si ya hay liquidaciones
emitidas para ese período, se avisa con la cantidad exacta
(`cantidad_liquidaciones_a_regenerar`, reusada de `app.negocio.
aumentos`, no duplicada) y se puede cancelar. Al confirmar (alta/
edición) o directamente al eliminar (sin segunda confirmación — el
cartel genérico de "¿Confirmás eliminar?" ya cumplió ese rol), se
regeneran solas las liquidaciones de los profesionales R de ese
período (`regenerar_si_corresponde`, mismo mecanismo que Vacaciones/
Licencias/Reservas regulares) — una edición chequea tanto la fecha
VIEJA como la NUEVA (mover una fecha especial fuera del período actual
también tiene que disparar la regeneración de ese período).

Bug de referencia débil encontrado al conectar los hooks:
`PantallaCRUD` guarda `al_crear`/`al_actualizar`/`al_eliminar` como
`weakref` (a propósito, para no crear un ciclo de GC con métodos atados
a la propia pantalla) — pasar lambdas sueltas, sin ninguna otra
referencia fuerte, las deja elegibles para el recolector de basura casi
de inmediato, volviendo los hooks no-ops en silencio. Se resuelve
anclándolas como atributo del objeto devuelto
(`pantalla._hooks_regeneracion = (al_crear, al_actualizar, al_eliminar)`)
— mismo criterio que ya usa el resto del sistema para hooks de
`PantallaCRUD` que no son métodos de la propia pantalla.

Tests: `tests/test_gui_valores.py`/`tests/test_gui_pantalla_grilla_
operativa.py` (ancho fijo del panel de filtros, tablas fuera del
tab-chain); `tests/test_gui_liquidacion.py` (monto a generar = total,
botón de seleccionadas deshabilitado sin tildar nada, más la
actualización de los tests de foco/período por defecto al nuevo
`SelectorPeriodo`); `tests/test_catalogos.py` (aviso de regeneración al
crear/cancelar la confirmación/sin liquidaciones emitidas/al eliminar
sin preguntar de nuevo).

## Novena tanda de correcciones post-v1: Disponibilidad, Profesionales,
## Llaves, Placas, Estadísticas, Balance del negocio

Nueva ronda de feedback sobre el build instalado, pedida solapa por
solapa sobre seis formularios — mismo criterio de siempre ("no largues
la nueva versión hasta que yo te diga, solo hace las correcciones").

### Dos reglas generales nuevas, aplicadas en el mecanismo compartido

- **Tab TAMBIÉN selecciona el contenido prefijado del campo al llegar**
  (`app/gui/widgets/foco.py`): revierte la decisión anterior ("Tab no
  selecciona, solo Enter") — pedido explícito de la clienta sobre Llaves,
  extendido a "todos los formularios del sistema": "cuando tabulo hacia
  un cuadro de texto en el que hay una opción prefijada... que quede
  seleccionado al hacer foco ahí así uno tiene la opción de empezar a
  escribir borrando el contenido prefijado". `_EnterAvanzaFoco._mover`
  pasa `seleccionar_todo=True` también en la rama de Tab/Backtab (antes
  `False`) — un solo cambio en el mecanismo compartido por decenas de
  formularios, sin tocar ninguna pantalla puntual.
- **Importes negativos en rojo, "compete a todos los importes del
  sistema"**: hasta ahora `item_monto` (moneda + alineado a la derecha +
  rojo si negativo) solo vivía en las solapas "Estado de cuenta" de
  Pagos/Liquidaciones/Cargos especiales. `Campo` (`crud_generico.py`)
  suma `es_monto: bool = False` — con `tipo="numero"` y `es_monto=True`,
  la tabla de CUALQUIER catálogo genérico pinta esa columna con
  `item_monto` en vez del número crudo sin formato. Aplicado en esta
  ronda a Consultorios (los 4 `ValorHora*`), Gastos operativos
  (`Monto`) y Profesionales (`SaldoCuentaActual`/`SaldoCuentaAnterior`)
  — los campos numéricos que NO son un importe (Cantidad de baños, %
  Bonificación, Orden) se quedan sin este flag, sin cambiar su
  comportamiento.

### Disponibilidad: Oferta de consultorios / Lista de espera / Archivos para enviar

Las tres solapas ya tenían el selector de profesional compartido
(`habilitar_busqueda_profesional`) y la cadena de foco Enter/Tab general
desde rondas anteriores — "visualización de focos" (Archivos para
enviar) se revisó y se confirmó que ya cumplía la regla general, sin
necesitar ningún cambio propio.

- **Oferta: "Día de la semana" del filtro de la grilla embebida,
  siempre de a pares.** Hasta ahora `agrupar_dias_en_pares()` (la lista
  de 2 columnas, mismo criterio que Reservas) solo se aplicaba cuando el
  sistema tenía domingo sumado a `Configuracion.DiasGrilla` — pedido
  explícito de la clienta de aplicarlo siempre, sin esa condición.
  `_AJUSTE_EXTRA_MUESTRA_CON_DOMINGO` se renombra `_AJUSTE_EXTRA_
  MUESTRA_PARES` (mismo valor, 9px) y pasa a sumarse siempre al ajuste
  de alto de "Referencias de colores" (antes solo con domingo
  configurado) — con los días siempre a 2 columnas, la leyenda necesita
  el mismo empujón extra para seguir llegando al pie de la columna, sin
  importar si hay 6 o 7 días.
- **Lista de espera: cadena de foco Enter/Tab propia.** Esta solapa
  nunca había tenido una cadena explícita (dependía del orden nativo de
  Qt) — se suma una, de arriba a abajo por columnas (Profesional →
  Localidad/Edificio/Unidad → Días → Tipo/horario → Agregar/Quitar
  bloque → Características pedidas → Detalle → Crear/Confirmar
  reserva/Descartar/Editar), con `showEvent` enfocando el combo de
  Profesional al entrar a la pantalla.

### Profesionales (Listado de profesionales / Profesiones y tratamientos)

- **Diálogo Nuevo/Editar: ancho dinámico en vez de 480px fijo**
  (`crud_generico.py`, cambio genérico, no puntual de Profesionales):
  480 recortaba etiquetas/campos largos de este formulario (ej. "Día
  del mes para plazo extendido automático..."). `_DialogoRegistro.
  __init__` calcula el ancho contra el `sizeHint()` real del formulario
  ya armado, con un piso de 480 (no se achica para diálogos chicos) y
  un techo de 900 (un campo larguísimo sigue envolviendo en dos líneas
  en vez de estirar el diálogo sin límite).
- **Combo "Tratamiento" no desplegaba nada para la mayoría de las
  profesiones**: bug real — `opciones_tratamiento` solo devuelve algo
  para Fonoaudiología/Psicopedagogía (sección 8.1 del negocio); el resto
  de las profesiones dejaba el combo vacío. `_actualizar_tratamiento`
  suma, siempre, cualquier `Tratamiento` ya usado por algún profesional
  del sistema (`_opciones_tratamiento_usados`, nueva — mismo criterio
  "catálogo abierto, sugiere lo ya usado" que `Responsable.Rol`/
  `CondicionFiscal`) a las que ya sugiere `opciones_tratamiento` para la
  profesión/sexo elegidos — el combo nunca vuelve a quedar sin ninguna
  opción una vez que hay al menos un profesional cargado con tratamiento.
- **Categoría se adelanta al principio del diálogo, arriba de Código.**
  `PantallaCRUD` suma un parámetro nuevo, `campos_primero_dialogo:
  list[str] | None` — reordena esos campos al principio SOLO en el
  cuadro Nuevo/Editar, sin tocar el orden de columnas de la tabla/
  listado (que sigue siendo "Código - Tratamiento - Nombre -
  Apellido...", el formato canónico de los selectores de profesional).
  `pantalla_profesionales` lo pasa como `["CategoriaProfesional"]`.
- **"Fecha de nacimiento" pasa a `tipo="fecha"` con formato
  "dd-MM-yyyy"** (sin día de semana — pedido explícito: "el día de la
  semana de un nacimiento no aporta nada", a diferencia de una fecha
  operativa como Vigencia). `Campo` suma `formato_fecha: str | None`
  (solo para `tipo="fecha"`, patrón de visualización alternativo al
  default del sistema `_FORMATO_FECHA_DIA`) — `_fmt_fecha_dia` y el
  `QDateEdit.setDisplayFormat` del diálogo lo usan cuando está presente.

  Como "Fecha de nacimiento" es opcional (no toda persona cargada tiene
  que tener este dato), `crud_generico.py` suma un sentinel propio para
  "(sin fecha)" en `tipo="fecha"` NO obligatorio: `_FECHA_SIN_DATO =
  QDate(1900, 1, 1)` — DISTINTO del `QDate(2000, 1, 1)` que ya usan
  Reservas/Novedades para sus propias fechas operativas (duplicado acá,
  sin relación entre los tres módulos), porque 2000 hubiera recortado en
  silencio cualquier nacimiento real anterior a ese año
  (`QDateEdit.setDate` por debajo del mínimo configurado clampea sin
  avisar). `setMinimumDate(_FECHA_SIN_DATO)` + `setSpecialValueText(
  "(sin fecha)")` solo se aplican cuando `campo.requerido` es `False`;
  un campo de fecha obligatorio sigue arrancando en `QDate.currentDate()`
  como siempre, sin este sentinel.

  **Bug real, encontrado al revisar la cobertura de este sentinel
  genérico, no pedido por la clienta**: "Fechas especiales" (su campo
  `Fecha`, obligatorio — `NOT NULL` en el schema) usaba `Campo(tipo=
  "fecha")` SIN `requerido=True` — con el sentinel nuevo, "Nuevo" sin
  tocar el campo guardaba `None` y el `repositorio.crear(...)` reventaba
  con `sqlite3.IntegrityError`, que a su vez quedaba atrapado por un
  `QMessageBox.warning` real (no mockeado en varios tests) — en
  producción, un cartel modal; en la suite de tests, un hang
  indefinido, detectado con `faulthandler`+`SIGALRM` forzando un dump
  del stack en pleno bloqueo. Corregido sumando `requerido=True` al
  `Campo("Fecha", ...)` de Fechas especiales — el único otro uso de
  `tipo="fecha"` en catálogos genéricos (`Profesional.FechaNacimiento`,
  legítimamente nullable en el schema) se queda sin tocar.
- **Profesiones y tratamientos: botones secundarios deshabilitados sin
  selección.** Cubierto de rebote por el cambio genérico de
  `PantallaCRUD` (ver más abajo) — no hizo falta ningún código puntual
  de este catálogo. Foco revisado y confirmado sin problemas.

### Botones Editar/Eliminar deshabilitados sin selección — regla general

Pedido explícito de la clienta, "ESTO PARA TODO EL SISTEMA": los botones
secundarios de edición de un catálogo arrancan deshabilitados y solo se
habilitan con una fila elegida en la tabla. `PantallaCRUD` (`crud_
generico.py`) suma `_actualizar_botones_seleccion()` (conectada a
`tabla_widget.itemSelectionChanged`, llamada también al final de
`actualizar()`) — un solo cambio en la clase genérica cubre de una a los
~14 catálogos que pasan por acá (Localidades, Edificios, Unidades,
Consultorios, Responsables, Tipos de licencia, Listas editables,
Condiciones y normas, Detalles complementarios, Profesiones, Gastos
operativos, Fechas especiales, Mensajes predefinidos, Profesionales).
Mismo criterio ya usado puntualmente en rondas anteriores para Pagos/
Registrar pagos y Planes de pago, ahora generalizado a la clase base.
Pantallas armadas a mano que NO pasan por `PantallaCRUD` (Llaves, Placas,
Bloques rígidos) necesitan el mismo cableado por separado — ver sus
secciones correspondientes más abajo.

### Llaves (Movimientos y tenencias / Registro de cargos especiales / Estado de cuenta)

**Movimientos y tenencias:**

- Botones Editar/Eliminar de las tres secciones (Tipos/Accesos/
  Movimientos) deshabilitados sin selección en su tabla correspondiente
  — `_actualizar_botones_tipo`/`_actualizar_botones_acceso`/`_
  actualizar_botones_movimiento` (esta última ya existía parcialmente,
  se extiende para cubrir también "Ingresar copia"/"Asignar copia", que
  dependen de tener un Tipo elegido).
- **Columna "Observación" nueva en la tabla de Movimientos** (8va
  columna) — el dato (`LlaveMovimiento.Observacion`) ya existía y se
  podía cargar desde el campo de observación de abajo, pero nunca se
  veía en la tabla. `_clave_orden_movimientos` suma la entrada
  correspondiente para que también sea ordenable por click.
- **Nomenclatura automática de Tipo="Edificio": "Tipo llave E{N} -
  {NombreEdificio}"** (antes solo "Tipo llave E{N}", sin distinguir a
  qué edificio corresponde cuando hay más de uno). `siguiente_nombre_
  llave`/`crear_llave` (`app.negocio.llaves`) suman un parámetro
  `id_edificio: int | None = None` (sin efecto para cualquier llamador
  existente, Tipo="Unidad"/"No especificada" no lo usan) que agrega el
  sufijo solo cuando `tipo == "Edificio"` y se pasó un edificio.
  `_DialogoTipo` suma un combo "Edificio" (solo habilitado para
  Tipo="Edificio" en un alta nueva, nunca en una edición — el edificio
  de una llave ya creada no se puede cambiar después) con su propia
  validación antes de aceptar.
- **Orden de Unidad en "Agregar acceso de llave"**: el combo de Unidad
  de `_DialogoAcceso` ordenaba alfabético por `Departamento` — pasa a
  `clave_orden_unidad` (de `app.pdf.estilos`, ya usada en toda la
  grilla/reservas), mismo criterio PB/EP/piso ascendente que el resto
  del sistema.

**Registro de cargos especiales:**

- **"Subtipo" se adelanta arriba de "Tipo", con reglas que lo
  condicionan**: Bonificación → Tipo fijo en Débito (combo
  deshabilitado); Ajuste → Tipo editable, default Crédito; Ítem libre →
  Tipo editable, default Débito. `_actualizar_tipo_segun_subtipo` (nueva)
  conecta el cambio de Subtipo a esta lógica. "Modificar cargo
  especial" precarga Subtipo antes que Tipo, y si el Subtipo no es
  Bonificación, pisa el default con el Tipo REAL ya guardado en la fila
  (no el que acabaría de sugerir el Subtipo).
- **Un cargo especial solo se puede imputar al mes en curso o al
  siguiente** (`crear_cargo_especial`, `app.negocio.pagos`) — antes solo
  rechazaba imputar a un mes YA PASADO; ahora también rechaza imputar
  más de un mes para adelante, con el mensaje indicando ambos períodos
  válidos.
- **Imputado al mes en curso, regenera y marca no enviada la
  liquidación de ese profesional** (mismo mecanismo `regenerar_si_
  corresponde` ya usado en Vacaciones/Licencias/Reservas regulares) —
  al mes SIGUIENTE no hace falta ningún llamado extra: `calcular_
  liquidacion` ya suma los cargos especiales de ese período al calcular,
  así que un cargo agendado para el mes que viene entra solo cuando
  llegue ese momento.

**Estado de cuenta:**

- Panel de filtros pasa de `setMaximumWidth(260)` a `setFixedWidth(260)`
  — con solo el máximo, clickear el combo de profesional (que despliega
  una lista más ancha momentáneamente) corría el ancho real del panel y
  la tabla de al lado se reacomodaba; con el ancho fijo, el panel nunca
  cambia de tamaño.
- `self.tabla.horizontalHeader().setStretchLastSection(True)` — la
  última columna se estira para ocupar el ancho sobrante del panel en
  vez de dejar un área en blanco a la derecha.

### Placas para timbres (Búsqueda y asignación / Impresión en papel)

**Regla general nueva, "ESTO PARA TODO EL SISTEMA"**: los botones
secundarios de una tabla se habilitan/deshabilitan según la fila
seleccionada, y cualquier edición pasa por un cuadro de diálogo en vez
de por campos sueltos al costado — mismo criterio ya generalizado en
`PantallaCRUD` (ver arriba) y ya usado en varias rondas anteriores para
Pagos/Cargos especiales/Planes de pago. En Placas esto ya estaba
cumplido de antes ("Reasignar"/"Liberar" ya se habilitaban solo con
selección, y ya usan sus propios diálogos) — confirmado sin necesitar
ningún cambio de código en esta pantalla puntual.

- **Tabla ya ordenada por Localidad/Edificio/Unidad/Posición** —
  confirmado por revisión de código, sin cambios: el orden por defecto
  ya sigue esa jerarquía exacta desde que se armó la pantalla.
- **Bloquear "Asignar posición de placa nueva" sin posiciones libres**:
  el mensaje de aviso (`QMessageBox.warning`, ya existía para el caso de
  tablero lleno) se actualiza para sugerir explícitamente la
  alternativa — reasignar la posición de otro profesional en vez de
  dejar la operación simplemente rechazada sin salida.
- **"Placa a imprimir": selector colapsable nuevo en la solapa de
  Impresión**, debajo del combo de Profesional — lista todas las
  posiciones de placa ya asignadas a ese profesional (puede tener una
  placa estándar en una unidad y una personalizada en otra) y deja
  elegir CUÁL imprimir, en vez de asumir "la personalización de
  cualquier placa suya" como hacía antes `personalizacion_del_
  profesional` (ese helper se deja de usar en este punto de entrada).
  `_lista_seleccion_simple()` (helper nuevo, `QListWidget` de selección
  única) + `_cargar_placas_profesional_imprimir`/`_placa_seleccionada_
  imprimir`/`_actualizar_boton_agregar_impresion` resuelven la carga/
  selección/habilitación del botón "Agregar a impresión" según haya 0,
  1 o varias placas para ese profesional.
- **Selector de profesional + cadena de foco en las dos solapas**
  (Buscar y Asignar / Imprimir): cada una suma su propio
  `instalar_enter_avanza_foco` y una subclase mínima de `QWidget`
  (`_PanelImprimirPlacas`, mismo patrón que la ya existente
  `_PanelBuscarPlacas`) con `showEvent` propio para enfocar el combo de
  Profesional de esa solapa al mostrarse.
- **El PDF generado por "Agregar a impresión" va a una carpeta propia,
  "Placas para imprimir"**, distinta de la carpeta del tablero de
  referencia completo (`generar_pdf_placas`, el PDF automático del
  avance de mes, que sigue en su carpeta de siempre). `app.negocio.
  archivos_generados` suma `SUBCARPETA_PLACAS_PARA_IMPRIMIR` como
  constante separada de `SUBCARPETA_PLACAS`, con el docstring
  explicando la distinción.

### Estadísticas / Balance del negocio

Las dos pantallas se revisaron contra la regla general de foco — ya
cumplían el orden de siempre (botones "Ver historial"/"Ver período
actual"/"Exportar a Excel" y los catálogos anidados correspondientes),
sin encontrar ningún hueco. Sin cambios de código en ninguna de las dos.

Tests: `tests/test_gui_widget_foco.py` (Tab selecciona contenido
prefijado, reemplaza al test que probaba lo contrario);
`tests/test_catalogos.py` (es_monto en las tablas de Consultorios/
Gastos operativos, botones deshabilitados sin selección, Fecha
requerido=True en Fechas especiales); `tests/test_profesionales.py`
(ancho dinámico del diálogo, combo Tratamiento con valores usados,
Categoría primero, formato de fecha de nacimiento, es_monto en los dos
saldos); `tests/test_gui_oferta.py` (días siempre a pares, sin la
condición de domingo); `tests/test_llaves.py`/`tests/test_gui_llaves.py`
(nomenclatura Edificio, orden de unidad, columna Observación, botones
deshabilitados); `tests/test_pagos.py` (límite de imputación a mes
siguiente); `tests/test_gui_novedades.py` (reglas Subtipo→Tipo,
regeneración al imputar al mes en curso); `tests/test_gui_placas.py`
(selector "Placa a imprimir" con 0/1/varias opciones, aviso de tablero
lleno con la sugerencia, carpeta "Placas para imprimir", foco en las
dos solapas). Suite completa: 2384 passed, sin regresiones.

## Se revierte la fuente fija de toda la app ("Segoe UI")

Ya instalado y probado en una máquina real, la clienta reportó que las
fuentes quedaron "muy grandes, peor que antes" — tanto que se apelmazaba
el contenido y quedaban cosas fuera de la pantalla, en todo el sistema a
la vez. Diagnóstico confirmado antes de tocar nada: el cambio
responsable es `app.setFont(QFont(FUENTE_APP))` (`gui_main.main()`,
`FUENTE_APP = "Segoe UI"` en `estilos.py`, sumado en la "Segunda tanda")
— `QFont("Segoe UI")` sin un tamaño de punto explícito deja que Qt
resuelva el tamaño "default" de esa fuente, y ese tamaño resultó más
grande que el default que ya traía Windows en esa máquina. Contra los
anchos/altos fijos calibrados pixel a pixel en todo el sistema (toda la
revisión "uno por uno" documentada en este archivo), una fuente más
grande sobre esas medidas fijas es justo lo que produce el apelmazado
descripto.

Pedido explícito de la clienta: revertir SOLO esta parte y dejar el
tema visual de fuentes para una ronda aparte, después de pulir la
lógica — "ir probando la lógica, y cuando la lógica se pula y quede
bien volver a realizar los ajustes visuales pantalla por pantalla".

Revertido de punta a punta, aislado, sin tocar nada más: se saca la
línea `app.setFont(QFont(FUENTE_APP))` de `gui_main.main()` (la
aplicación vuelve a usar la fuente nativa de cada instalación, como
estaba antes de esa tanda) y la constante `FUENTE_APP`, ya sin ningún
consumidor, de `estilos.py` — con un comentario en su lugar explicando
por qué se probó y se descartó, para no repetir el mismo camino sin
revisar este historial. La política de escala de DPI
(`setHighDpiScaleFactorRoundingPolicy(PassThrough)`, sumada en el mismo
cambio original) NO se tocó — es inocua (ya es el default de Qt6) y no
tiene relación con el tamaño de fuente en sí.

Tests: se borra `test_fuente_app_fijada_a_segoe_ui`
(`tests/test_gui_estilos.py`), que solo verificaba la constante ya
retirada — ninguna otra prueba dependía de `FUENTE_APP`/del `setFont`.

## SistemaDF v0.11.2026.10: documento "Correcciones para próxima versión"

La clienta mandó un documento nuevo (Word) con ~220 puntos para la
próxima versión, organizado en dos partes: una sección "GENERAL PARA
TODO EL SISTEMA" (14 reglas numeradas 1.1 a 1.14, más tres pedidos
sueltos — nombre de la versión, carpeta de profesional, planilla de
Llaves) y, debajo, cada pantalla del sistema con sus propios puntos,
muchos de los cuales referencian una regla general por número ("Aplicar
corrección #1.4"). Mismo criterio de trabajo que toda la revisión
anterior: primero las reglas GENERALES (son la base que el resto
referencia), después pantalla por pantalla en el orden del documento,
con tandas intermedias de pyflakes + suite + commit. Esta sección cubre
la primera tanda — los puntos GENERALES que se pueden resolver de una
sola vez, centralizados — antes de arrancar el recorrido pantalla por
pantalla (que queda documentado en sus propias secciones, a medida que
se hace).

### 1.1 — Panel de control al abrir, pantalla maximizada

`VentanaPrincipal.__init__` elegía como pestaña inicial la PRIMERA
`Seccion` de la lista (posición 0) — hoy coincide con "Panel de
control" porque esa `Seccion` ya es la primera de "Sistema", pero el
punto 19/20 de este mismo documento (ver "Menú lateral" más abajo) va a
sacarla de esa categoría y ponerla primera en "{Nombre del espacio}" —
con eso, "la primera de la lista" dejaría de ser Panel de control.
Se resuelve buscándola por NOMBRE en vez de por posición: `VentanaPrincipal`
guarda `fila_panel_control` mientras arma el menú y, si la encuentra, la
usa como fila inicial en lugar de `primer_item_seleccionable` — robusto
a cualquier reordenamiento futuro del menú. Sin esa `Seccion` en la
lista (algún nivel de usuario sin acceso a ella), cae al primer ítem de
siempre. La ventana maximizada ya estaba resuelta de una tanda anterior
(`ventana.showMaximized()`), no se tocó.

### 1.2 — Selector de profesional: ya resuelto

Select-all al enfocar (click y Tab), sin distinguir mayúsculas/acentos,
substring en cualquier parte de la cadena — las tres cosas ya estaban
resueltas en `app/gui/widgets/selector_profesional.py` de rondas
anteriores (ver ese archivo y las tandas "Selector de profesional..."
más arriba en este documento). No hizo falta ningún cambio: se verificó
leyendo el código, no se repite la implementación acá. Queda pendiente,
sí, confirmar pantalla por pantalla que el selector usado en cada
formulario con búsqueda de profesional sea efectivamente este
(`habilitar_busqueda_profesional`) y no un combo suelto — eso se revisa
en el recorrido pantalla por pantalla, no es un punto GENERAL en sí.

### 1.3 — Orden de unidades (piso + letra): extendido a los 5 lugares que faltaban

`clave_orden_unidad` (`app.pdf.estilos`) ya existía y ya se usaba en la
mayoría del sistema — CLAUDE.md ya tenía anotado qué pantallas quedaban
pendientes de una revisión anterior ("Llaves, Balance, Imágenes,
Estadísticas, Aumentos"). Se completaron los cinco, cada uno
reemplazando su `ORDER BY Departamento` (alfabético puro, "EP" quedaba
antes de "PB") por un `sorted(..., key=lambda f: clave_orden_unidad(...))`
en Python después de traer las filas:

- `llaves.py`: el combo de Unidad del diálogo "Agregar acceso" ya estaba
  resuelto; lo que faltaba era `_accesos`/`_clave_orden_accesos` (la
  tabla de Accesos de la pantalla) — la columna 2 ("Unidad") del orden
  por click en el encabezado pasa a `clave_orden_unidad`, y el orden por
  defecto (sin click) se resuelve en Python en vez del `ORDER BY ...,
  u.Departamento` que tenía la consulta.
- `balance.py`/`imagenes.py`/`estadisticas.py`: mismo patrón en
  `_cargar_combo_unidad` (cascada Localidad→Edificio→Unidad→Consultorio
  de los filtros) — se trae `SELECT IdUnidad, Departamento FROM Unidad
  ...` sin el `ORDER BY Departamento` y se ordena en Python antes de
  poblar el combo.
- `aumentos.py`: dos lugares — el combo de Unidad del filtro visual
  (mismo patrón que los tres de arriba) y `_cargar_consultorios_info`
  (la lista ordenada de consultorios que alimenta la tabla de Aumentos/
  Esquema de descuentos), que ordenaba por SQL `loc.Localidad, e.Nombre,
  u.Departamento, c.NumeroConsultorio` — pasa a ordenar por SQL solo
  Localidad/Edificio/NumeroConsultorio (sin Departamento) y reordenar en
  Python con clave compuesta `(Localidad, Edificio, clave_orden_unidad(
  Departamento))`, confiando en que `sorted` es estable para no perder
  el orden por NumeroConsultorio dentro de una misma unidad.

### 1.4 y 1.5 — Dos cadenas de foco independientes + reset al reingresar: infraestructura

Dos pedidos relacionados, con una pieza de infraestructura compartida y
una pieza que se termina de aplicar pantalla por pantalla (no es
mecánicamente centralizable al 100%):

**1.5 (tablas nunca reciben el foco por Tab) — resuelto de una sola vez
para todo el sistema.** `excluir_tabla_del_tab(tabla)` (nueva, `app.gui.
widgets.foco`) factoriza el patrón puntual que ya existía para "Valores
vigentes" (`ClickFocus` + `setTabKeyNavigation(True)` — Tab no puede
aterrizar en la tabla desde ningún filtro/botón, solo un click la
selecciona; una vez que SÍ tiene el foco por click, Tab sigue
recorriendo celdas en vez de "escaparse" hacia otro widget, que ya es el
default de `QTableView`). Se aplicó con un script de un solo uso a las
32 tablas del sistema (`QTableWidget()` en 16 archivos de pantallas +
`crud_generico.py`, que cubre de rebote los ~14 catálogos genéricos) y,
a mano, a la grilla operativa compartida (`app.gui.widgets.
grilla_operativa.GrillaOperativaWidget.tabla` — el widget reutilizado
por Reservas/Oferta/Novedades/Grilla semanal/Valores vigentes, antes sin
excluir salvo en los dos usos puntuales que ya lo hacían a mano). Con
esto, "los focos no pasan nunca de los filtros a las tablas" queda
garantizado en todo el sistema de una sola vez — lo que falta pantalla
por pantalla es la otra mitad del pedido (que la cadena de controles/
filtros de CADA pantalla esté completa y cerrada, sin huecos que la
dejen "escaparse" por el orden nativo de Qt hacia algún widget sin la
cadena instalada), que se revisa caso por caso en el recorrido.

**1.4 (reset de filtros al salir de la solapa, foco siempre en el
primer control) — infraestructura de F3 lista, aplicación pantalla por
pantalla.** Ver el punto 1.6 de abajo: el mecanismo es el mismo que F3
("reiniciar la solapa... como recién se entrara en ella") — cada panel
que lo necesite expone un método `reiniciar()` que resetea sus propios
filtros a su valor por defecto y refoca el primer control, y ESE MISMO
método es lo que hay que llamar tanto desde `showEvent` (para que ya
esté así "al volver a ingresar", sin que el usuario note nada) como
desde F3 (para poder forzarlo a mano). La pieza central (cómo encontrar
"la solapa activa en este momento", bajando por cualquier cadena de
`QTabWidget` anidados, y el atajo F3 que la invoca) ya está lista — ver
`VentanaPrincipal._panel_mas_interno`/`_reiniciar_solapa_activa` en el
punto 1.6. Sumarle el método `reiniciar()` a cada panel en particular
(qué cuenta como "sus filtros", qué es "el primer control") se hace
pantalla por pantalla, a medida que se recorre el documento — no hay
una forma genérica de saber eso sin mirar cada pantalla.

### 1.6 — Línea F1/F2/F3 + calculadora flotante

`VentanaPrincipal` suma, en la barra de estado, una etiqueta "F1 –
Ayuda / F2 – Calculadora / F3 – Reiniciar solapa" — con `statusBar().
addWidget(...)` (no `addPermanentWidget`, usado ya para el badge de
período) queda del lado IZQUIERDO de esa misma línea, tal como pide el
documento ("en esa misma línea pero al borde de la izquierda").

`Calculadora` (nueva, `app/gui/widgets/calculadora.py`): una ventana de
verdad (`Qt.WindowType.Window`, no un diálogo modal — no tiene que
bloquear el resto del sistema mientras está abierta), con las cuatro
operaciones básicas (dígitos + `+ - * /` + `.` + `C` + borrar último
carácter + `=`). `_calcular` usa `eval` sobre la expresión acumulada,
pero sin ningún riesgo de ejecutar código arbitrario: los únicos
caracteres que pueden llegar a esa cadena son los de los propios
botones (dígitos, operadores, paréntesis — no hay ningún campo de texto
libre), validados explícitamente antes de evaluar. `WA_DeleteOnClose`
hace que cerrarla con la cruz la destruya de verdad (el default de
`QWidget.close()` es solo ESCONDERLA, no destruirla) — necesario para
que `VentanaPrincipal` se entere (señal `destroyed`) y pueda volver a
abrir una nueva la próxima vez que se presione F2, en vez de quedar
"colgada" de una instancia ya cerrada. F2 abre una sola instancia por
ventana (si ya está abierta, la trae al frente con `raise_()`/
`activateWindow()` en vez de abrir una segunda).

F3 (`_reiniciar_solapa_activa`) resuelve primero "cuál es la solapa
activa en este momento" con `_panel_mas_interno`: baja por la cadena de
`self._pila.currentWidget()` mientras sea un `QTabWidget`, hasta llegar
al panel de verdad que se está viendo (una pantalla compuesta como
"Archivos y listas" es un `QTabWidget` cuyo contenido de cada pestaña
puede a su vez ser OTRO formulario con sus propias solapas — hay que
bajar las veces que haga falta, no solo un nivel). Si ese panel tiene un
método `reiniciar` (duck-typing, no una interfaz formal — la mayoría de
los paneles todavía no lo tienen, se va sumando pantalla por pantalla
según 1.4), lo llama; si no lo tiene, no hace nada en vez de romper.

### 1.7 — Recuadro negro fino en filtros/cuadros de texto

`QComboBox` ya tenía un borde reservado de 2px para el anillo de foco
(ver la sección "Indicador visual de foco" más arriba), pero
TRANSPARENTE en reposo — por eso varios combos usados como filtro se
veían "sin delimitar" hasta que se los enfocaba. Pasa de `transparent`
a `#000000` en reposo (mismo ancho de 2px, así el foco no corre nada al
ganar/perder color). `QLineEdit` no tenía ninguna regla propia en
`estilos.py` — dependía por completo del estilo nativo de cada
instalación, que en algunos casos lo deja prácticamente invisible; se
suma `QLineEdit { border: 1px solid #000000; border-radius: 2px;
padding: 1px 2px; }`, mismo criterio "borde negro fino" que el resto de
la app (botones, solapas, tabla).

### 1.8 — Líneas internas de la grilla: ya no se ven dobles

Causa real del efecto "como que están más encimados unos cuadritos, como
si no compartieran la misma línea" (`_dibujar_bordes_gruesos`, `app.gui.
widgets.grilla_operativa`): cada celda pintaba su propio marco fino
COMPLETO (las 4 caras, vía `drawRect`) — el límite ENTRE dos celdas
vecinas quedaba pintado DOS VECES, una por cada lado (el borde derecho
de la celda de la izquierda Y el borde izquierdo de la celda de la
derecha), en dos columnas de píxeles distintas y contiguas en vez de una
sola línea compartida de 1px. Se corrige pintando solo abajo y a la
derecha (`drawLine` ×2 en vez de `drawRect`): cada límite interno queda
trazado por una única celda (la de arriba/la de la izquierda), sin
duplicarse. El borde exterior superior/izquierdo de la grilla sigue
cerrado igual que antes porque ahí ya cae la línea gruesa estructural
(día/encabezado), nunca la fina — no hace falta ningún caso especial
para el borde de afuera.

### 1.9 a 1.12 — Reglas cruzadas, se aplican pantalla por pantalla

Cuatro puntos que no son centralizables en un solo lugar (dependen del
flujo concreto de cada pantalla), así que quedan como criterio a aplicar
durante el recorrido, no como un cambio de una sola vez acá:

- **1.9** (regenerar liquidación + marcar no enviada tras cualquier
  recálculo del período actual; copiar WhatsApp si es categoría A): en
  gran parte YA es el comportamiento del sistema desde varias tandas
  anteriores (`regenerar_si_corresponde`, usado por Vacaciones/
  Licencias/Reservas regulares/Cargos especiales/Aumentos/Fechas
  especiales) — lo que queda es verificar que no falte en ningún lugar
  nuevo a medida que se revisa cada pantalla.
- **1.10** (alertas con el contenido completo, no solo el número de
  referencia + fecha con día de semana abreviado) y **1.11** (alerta
  final de éxito/cancelación): se revisan mensaje por mensaje, pantalla
  por pantalla — no hay un único lugar que arme "todos los carteles del
  sistema".
- **1.12** (solo se puede imputar al período actual o posterior, nunca
  a uno anterior): ya existe como criterio en varios flujos (Reservas,
  Cargos especiales, movimientos de Llaves) — se revisa que esté en
  todos los lugares con un campo de período a imputar.

### 1.13 — Sábado en negro en todos los selectores de fecha

`aplicar_color_sabado_negro` (nuevo, `app/gui/widgets/fecha.py`): toma
un `QDateEdit` ya con `setCalendarPopup(True)` y le pinta de negro el
`weekdayTextFormat` del sábado en su `calendarWidget()` (por default, Qt
lo pinta en un tono distinto al resto de la semana, igual que el
domingo — la clienta pidió corregir solo el sábado). Se aplicó en los
seis puntos de construcción de `QDateEdit` del sistema: tres fábricas
compartidas (`novedades._campo_fecha`, `llaves._fecha_edit`,
`configuracion._crear_campo_fecha`) que ya cubren varios usos cada una,
más los campos armados a mano en `oferta.py` (2), `reservas.py` (5, vía
un script de un solo uso sobre cada `setCalendarPopup(True)`) y
`crud_generico.py` (el `tipo="fecha"` de los catálogos genéricos).

### 1.14 — Nueva versión: "SistemaDF v0.11.2026.10"

`app/version.py`: `VERSION` pasa de `"v0.1"` a `"v0.11.2026.10"` — sin
ningún otro cambio, `NOMBRE_Y_VERSION` ya se arma solo a partir de esa
constante.

### Carpeta de profesional: nombre completo, se renombra sola ante cualquier cambio relevante

Pedido explícito de la clienta: la carpeta de un profesional
(`Profesionales/{...}`, liquidaciones + documentación) pasa de llamarse
solo con el código ("R1") a "{código} - {tratamiento} {nombre}
{apellido}" (ej. "R1 - Lic. Virginia Lo Veci"), el mismo formato
canónico que ya muestran los selectores de profesional de todo el
sistema — para poder identificar de quién es la carpeta sin tener que
abrir el sistema.

`nombre_carpeta_profesional(codigo, tratamiento, nombre_pila, apellido)`
(nuevo, `app.negocio.archivos_generados`) arma y sanea ese texto
(`_CARACTERES_INVALIDOS_CARPETA`, mismo criterio que `app.negocio.
imagenes._nombre_archivo_valido` — Windows no admite `\/:*?"<>|` en un
nombre de archivo/carpeta, duplicado acá porque son capas de negocio sin
relación entre sí) — sin tratamiento/nombre/apellido cargados, cae al
código solo, igual que antes de este cambio (compatibilidad con
cualquier Profesional de prueba sin esos campos). `carpeta_profesional`
pasa a resolver internamente el nombre completo consultando la tabla
`Profesional` por `IdCodigo` — los llamadores (`mensajeria.py`,
`liquidacion.py`, `avance_mes.py`) no cambiaron, siguen pasando solo el
código.

`aplicar_cambio_codigo` (el hook que ya corría al editar un profesional
desde la pantalla, antes solo para código/categoría) ahora dispara el
renombrado de carpeta ante un cambio en CUALQUIERA de los cuatro campos
que componen el nombre (código, tratamiento, nombre, apellido) — no solo
el código como antes. El nombre ANTERIOR se calcula a partir de
`registro_anterior` (la fila de antes de guardar, que el hook ya recibía)
en vez de volver a consultar la base por el código viejo, que para
cuando corre este hook ya no existe ahí (`repositorio.actualizar` ya
hizo commit antes de llamarlo). `renombrar_carpeta_profesional` pasa a
recibir el nombre de carpeta COMPLETO en sus dos parámetros (antes,
códigos sueltos) — mismo mecanismo de mover+limpiar de siempre, solo
cambia qué representan esos dos strings.

Tests nuevos en `tests/test_archivos_generados.py`
(`nombre_carpeta_profesional` con distintas combinaciones, `carpeta_
profesional` con y sin registro real) y ajustados en `tests/test_
profesionales.py`/`tests/test_gui_liquidacion.py` (las rutas de disco
esperadas pasan de "R3"/"R1" a "R3 - Ramos"/"R1 - Gómez", reflejando el
nombre real del profesional de cada test — incluido un caso donde el
diálogo de edición real termina completando "Tratamiento" con un valor
default del combo aunque el mock no lo haya tocado, destapando que
cualquier edición por ese diálogo ya rellenaba ese campo desde antes de
este cambio, simplemente sin que importara hasta ahora).

### Planilla de importación de Llaves: tipos, accesos y tenencias en una sola hoja

Pedido explícito de la clienta — contradice una decisión anterior de
"dejarlo como está" (ver la sección "Planilla de importación: revisión
de cobertura" más arriba), tomada antes de este pedido nuevo y explícito
de volver a resolverlo. La hoja "Llave" suma cuatro columnas opcionales
al final de las tres que ya tenía (`Tipo`, `ValorDepositoActual`,
`Observacion`): `Edificio`, `Unidad`, `Profesional`, `DepositoAbonado` —
al final de la lista, no en el medio, para no correr la posición de las
columnas que ya tenía alguien con una planilla vieja descargada (se
resuelve por nombre de encabezado, pero mantener el orden estable evita
sorpresas).

Alcance deliberadamente acotado al caso común — "una fila = un tipo de
llave, con como mucho UN acceso y UNA tenencia inicial" — en vez de
construir un mecanismo de referencias cruzadas entre hojas (`LlaveAcceso`/
`LlaveMovimiento` como hojas aparte, referenciando filas de "Llave" por
algún identificador inventado): la fila ya resuelve directamente el caso
real que describió la clienta ("qué llaves tiene cada profesional, y si
abonó depósito"). Si una llave necesitara más de un acceso o más de un
tenedor, se completa a mano desde la pantalla de Llaves después de
importar — igual que antes de este cambio.

Mecánica (`app/importacion/importar_excel.py`, rama `elif entidad ==
"Llave":`): `_resolver_referencias` resuelve Edificio (opcional) →
`IdEdificio`, Unidad (opcional, solo si hay Edificio) → `IdUnidad`, y
Profesional (opcional, por `IdCodigo`) → `IdProfesional` — las tres
quedan en `datos` aunque sean `None`, a diferencia del resto de las
entidades de esta función (que SIEMPRE son obligatorias). `importar_hoja`
saca esas tres referencias más `DepositoAbonado` de `datos` ANTES del
chequeo de duplicado (`_ya_existe_identico` reventaría contra la tabla
`Llave`, que no tiene esas columnas, si quedaran) y antes de crear la
`Llave` en sí:

- Si hay Edificio, `agregar_acceso_llave(conn, id_llave=..., id_edificio=...,
  id_unidad=...)` — misma función que ya usa la pantalla, con sus mismas
  validaciones (una llave Tipo Edificio no admite más de un edificio
  distinto, Tipo Unidad exige una unidad puntual).
- Si hay Profesional, `ingresar_copias` (una copia nueva al stock) +
  un `LlaveMovimiento` Tipo="Asignación" armado directo por repositorio
  (no vía `asignar_llave`, la función que usa la pantalla para una
  asignación NUEVA): a propósito NUNCA genera un `CargoEspecial`, sea
  que `DepositoAbonado` venga en "Sí" o en "No" — es una tenencia
  HISTÓRICA, de antes de empezar a usar el sistema; si ya lo pagó, fue
  por fuera del sistema (se registra `DepositoCobrado=1`/`MontoCobrado`
  para que quede history, sin cobrar nada de nuevo); si no lo pagó,
  tampoco corresponde cobrárselo recién ahora solo por estar
  importando el dato histórico — mismo criterio que ya usa `PlanPago`
  importado (las cuotas pasadas se marcan solas como pagadas, sin
  volver a generar nada).

Chequeo de duplicados (`_ya_existe_identico`) se saltea por completo
para "Llave" cuando la fila trae Edificio o Profesional: comparar solo
por las columnas reales de la tabla Llave (Tipo/ValorDepositoActual/
Observacion) hubiera hecho pasar como "duplicadas" a dos llaves del
mismo tipo/valor pero con acceso a edificios o profesionales DISTINTOS
— exactamente las dos columnas que quedarían afuera de esa comparación
son las que hacen que sean filas legítimamente distintas. Sin Edificio
ni Profesional (el caso simple, "solo cargo el tipo"), el chequeo sigue
funcionando exactamente igual que antes de este cambio.

Tests nuevos en `tests/test_importacion.py`: acceso creado con Edificio
válido, error con edificio inexistente, tenencia con depósito abonado
(sin `CargoEspecial` generado) y sin abonar, error con profesional
inexistente, dos llaves del mismo tipo/valor a edificios distintos NO
se consideran duplicadas entre sí.

### Menú lateral (puntos 19, 20 y 74): categorías renombradas, Panel de control reubicado, acordeón colapsable

Tres pedidos sobre `gui_main.construir_secciones`/`app.gui.main_window.
VentanaPrincipal`, resueltos juntos porque los tres tocan la misma
estructura (las dos categorías del menú y el orden de sus Secciones).

**Punto 19 — renombre de las dos categorías.** "Sistema" pasa a llamarse
"Parámetros del sistema" (string fijo). "Operativa diaria" deja de ser
un nombre fijo y pasa a mostrar el nombre del espacio configurado, en
MAYÚSCULA — mismo criterio Nivel 1 que el resto del sistema.
`construir_secciones` suma un parámetro `conn: sqlite3.Connection | None
= None` (antes solo recibía `usuario`): con `conn`, lee `Configuracion.
NombreEspacio` y arma `categoria_espacio = nombre_espacio.upper()`
(fallback "Espacio Ramos Consultorios" si está vacío, el mismo fallback
que ya usan `app.negocio.oferta_busqueda_texto`/`app.pdf.estilos`/etc.);
sin `conn` (la mayoría de los tests de pantallas sueltas, que no tienen
que ver con el menú en sí), cae directo a ese fallback sin tocar la
base. `gui_main.main()` pasa a llamar `construir_secciones(usuario,
conn)`. Dentro de la lista, cada `categoria="Sistema"`/`categoria=
"Operativa diaria"` literal se reemplazó por las variables
`categoria_sistema`/`categoria_espacio` correspondientes — ningún otro
cambio en qué Seccion cae en cuál categoría.

**Punto 74 — "Panel de control" pasa a ser la primera Seccion de la
categoría del espacio**, arriba de "Grilla y mensajería" (antes era la
primera de "Sistema"). Se sacó esa `Seccion` de su posición vieja y se
reinsertó al principio del bloque `categoria_espacio` — `VentanaPrincipal.
_abrir_calculadora`/arranque-por-nombre (punto 1.1, ver más arriba) ya
buscaba "Panel de control" por NOMBRE y no por posición, así que este
movimiento no necesitó ningún cambio ahí.

**Punto 20 — las dos categorías arrancan COLAPSADAS, acordeón por
clic, "Panel de control" siempre visible.** Hasta ahora el separador de
categoría (`"— {categoria.upper()} —"`) se armaba con `Qt.ItemFlag.
NoItemFlags` — ni seleccionable ni clickeable, puramente decorativo.
Pasa a `Qt.ItemFlag.ItemIsEnabled` (clickeable, pero nunca "seleccionado"
como la fila actual) y suma una flecha (▸ colapsado / ▾ expandido) al
texto. `VentanaPrincipal` suma tres diccionarios nuevos armados al
construir el menú: `_categorias_expandidas` (estado por categoría,
arranca en `False` para las dos), `_separadores_por_categoria` (para
poder reescribirle el texto/flecha al toggle) y `_items_por_categoria`
(la lista de ítems de pantalla de cada categoría que SÍ hay que ocultar/
mostrar — "Panel de control" queda deliberadamente afuera de esa lista
de su categoría, así nunca se oculta sin importar el estado del
acordeón). `_aplicar_colapso(categoria)` sincroniza texto del separador
+ `setHidden()` de cada ítem de esa categoría contra el estado guardado;
se llama una vez por categoría al terminar de armar el menú (deja todo
colapsado salvo Panel de control) y de nuevo cada vez que se clickea un
separador (`_al_click_item_navegacion`, conectada a `itemClicked` —
ítems normales, sin la marca de separador en `Qt.ItemDataRole.UserRole +
1`, no hacen nada al clickearlos ahí, la selección de pantalla la sigue
manejando `currentRowChanged` de siempre).

Un ítem oculto (`setHidden(True)`) sigue pudiendo recibir el foco de
selección por código (`QListWidget.setCurrentRow`/`currentItem()`)
aunque no se vea en pantalla — confirmado antes de tocar nada, así que
ningún mecanismo existente que ya hacía eso (arranque en "Panel de
control", `ir_a_seccion`, los tests que setean la fila a mano) se vio
afectado por el colapso. `ir_a_seccion` (#22, Lista de espera → Reservas)
suma un paso extra: si la Seccion destino está en una categoría todavía
colapsada, la expande antes de seleccionarla — saltar a una pantalla
"escondida" detrás de un acordeón sin desplegarlo dejaría la selección
sin ningún indicio visual en el menú.

Tests nuevos en `tests/test_gui_main.py` (reemplazando el viejo test de
categorías fijas): nombres/contigüidad de las dos categorías nuevas,
`categoria_espacio` refleja `Configuracion.NombreEspacio` cuando se pasa
`conn`, "Panel de control" es la primera Seccion de la categoría del
espacio y no de "Parámetros del sistema". Tests nuevos en
`tests/test_main_window.py`: las dos categorías arrancan colapsadas
salvo "Panel de control", clic en el separador despliega/vuelve a
colapsar (con la flecha cambiando), clic en un ítem normal no toca nada
del colapso, `ir_a_seccion` expande la categoría si estaba colapsada.

### Archivos y listas / Base de datos del espacio / Configuración general / Usuarios y permisos / Panel de control

Segunda tanda del documento, cubriendo el resto de "ARCHIVOS Y LISTAS",
"BASE DE DATOS DEL ESPACIO" completa (sin puntos propios, solo 1.4/1.11
— ya cubierta por el cambio central de `PantallaCRUD`), "CONFIGURACIÓN
GENERAL", "USUARIOS Y PERMISOS" y el reordenamiento de "PANEL DE
CONTROL" (puntos 76-80).

**1.4/1.11 centralizados en `PantallaCRUD` (`crud_generico.py`)**: de
una sola vez, para los ~14 catálogos genéricos (Localidades, Edificios,
Unidades, Consultorios, Responsables, Listas editables, Condiciones y
normas, Detalles complementarios, etc.) — `showEvent` pasa a llamar un
método nuevo, `reiniciar()` (mismo contrato que el resto del sistema
para F3): limpia el campo "Buscar" además de reiniciar el orden de la
tabla, y vuelve a enfocar el primer control. `_nuevo`/`_editar`/
`_eliminar` suman un `QMessageBox.information` de éxito al terminar, y
`_eliminar` suma uno de "Eliminación cancelada" cuando se declina la
confirmación — mismo criterio en los tres. Como Listas editables/
Condiciones y normas/Detalles complementarios/los 5 catálogos de Base
de datos del espacio no tienen ningún parámetro propio de foco (usan
`PantallaCRUD` tal cual, sin pisar nada), este único cambio ya cumple
"Aplicar correcciones 1.4, 1.11" para los tres primeros y para los
cinco de Base de datos del espacio sin necesitar ningún código
puntual.

**Gestor de archivos del espacio** (puntos 23 a 27, `imagenes.py`):
- Punto 23: `QTableView` (clase base de `QTableWidget`) suma un borde
  negro fino en `estilos.py` — se confundía contra el fondo, mismo
  criterio ya aplicado a filtros/cuadros de texto (1.7).
- Puntos 25/27: `_ajustar_columnas` suma un parámetro `columnas_
  minimas` — las columnas "Orden"/"Principal"/"Activo" (vista por
  alcance) o "Consultorio"/"Principal"/"Activo" (vista "Todos los
  archivos") se quedan en el ancho justo de `resizeColumnsToContents`
  en vez del padding generoso de las demás, para que el ancho que esas
  tres dejan de usar se lo lleve la Vista previa (la única con
  `stretch=1` del layout de la solapa).
- Punto 26: cadena de foco explícita (`instalar_enter_avanza_foco`),
  Alcance → Tipo de archivo → Localidad → Edificio → Unidad →
  Consultorio → los siete botones → Manual del usuario, con wrap-around
  de vuelta a Alcance (gratis).
- 1.4/1.11: `reiniciar()`/`showEvent` (reinicia Alcance/Tipo de archivo
  a su valor por defecto, limpia la selección, enfoca Alcance) y
  alertas de éxito/cancelación en `_agregar`/`_eliminar`.

**Textos del sistema** (punto 41, `textos_sistema.py`): los subtítulos
"MENSAJES AUTOMÁTICOS"/"AYUDA CONTEXTUAL (F1)" pasan a negrita y color
negro explícito (antes dependían del estilo nativo de un ítem
deshabilitado, sin ninguna regla QSS propia para esta lista en
particular — a diferencia del menú lateral, que sí la tiene por
`objectName="navegacion"`); "Textos editables" pasa de `subtituloCampo`
a `subtituloSeccion`, mismo tamaño/negrita que `etiqueta_nombre` (el
título que aparece arriba del cuadro de la derecha al seleccionar un
texto). `reiniciar()`/`showEvent` descartan cualquier edición sin
guardar y vuelven al estado "sin selección"; `_guardar`/`_restablecer`
suman alertas de éxito y de cancelación (al declinar el cartel de
variable desconocida / de confirmación de restablecer).

**Configuración general** (`configuracion.py`): `ConfiguracionGeneral`
(el contenedor con las 7 solapas) suma `showEvent`/`reiniciar()` — a
diferencia de los catálogos, acá "resetear filtros" se traduce en
recargar los valores reales de `Configuracion` (vía `actualizar()`, ya
existía) y descartar cualquier campo tocado sin guardar, sin importar
en qué solapa haya quedado el usuario — el botón "Guardar" sigue siendo
compartido por las 7, así que el reset vive en el contenedor de afuera,
no en cada `_PanelCampos` individual.

**Bloques rígidos** (`bloques_rigidos.py`, solapa de Configuración
general): mismo patrón que los catálogos genéricos pero a mano (no usa
`PantallaCRUD`) — `showEvent` pasa a `reiniciar()` (limpia "Buscar" +
reinicia orden + reenfoca) y `_nuevo`/`_editar`/`_eliminar` suman las
mismas alertas de éxito/cancelación.

**Usuarios y permisos** (`usuarios.py`): `_PanelUsuarios`/`_PanelPermisosPantalla`
suman `reiniciar()` (antes la lógica vivía solo en `showEvent`, sin
método propio para que F3 la dispare) y `_nuevo`/`_editar` suman
alertas de éxito ("Resetear contraseña" ya la tenía).

**Panel de control, "Avance de período y backups"** (puntos 76-80,
`panel_control.py`): "Fecha y hora actual" se funde dentro de "Período
actual" (período en la primera línea, fecha/hora real debajo, mismo
cuadrito) — la grilla vuelve a 6 cuadritos (de los 7 que tenía desde que
se sumó "Cumpleaños y días de profesión"), en el orden pedido
explícito: Período actual, Último backup, Ocupación y horas /
Profesionales, Feriados y fechas especiales, Cumpleaños y días de
profesión. Cada uno de los seis pasa a ser escroleable EN VERTICAL de
forma individual (`_agregar_contenido_escrolable`, nueva: envuelve el
`QLabel` — o el contenedor con las dos etiquetas del cuadrito de
Período — en un `QScrollArea` propio sin marco, en vez de agregarlo
directo al layout del cuadrito) para cuando el contenido no entre en el
alto parejo de la grilla (`_ALTO_MINIMO_TARJETA`); la tarjeta de
Alertas, debajo de los seis, ya tenía su propio scroll desde antes.
"Cumpleaños y días de profesión" pasa a mostrar el día de la semana
abreviado ("ddd dd-mm", ej. "mar 15-10"), mismo criterio que el resto
del sistema (1.10).

Tests actualizados en `tests/test_gui_panel_control.py`: el conteo de
la grilla pasa de 7 a 6; los tres tests que ubicaban el cuadrito de
"Período actual" vía `etiqueta_periodo.parentWidget()` (ya no es
directo, ahora hay un `QScrollArea` de por medio) pasan a un helper
nuevo, `_tarjeta_de(widget)`, que sube por `parentWidget()` hasta
encontrar el `QFrame#cuadritoInfo`; se suman dos tests (cada cuadrito
principal tiene su propio `QScrollArea`, "Período actual"/reloj caen en
el mismo cuadrito) y se actualiza el test de cumpleaños para el formato
con día de la semana.

Tests nuevos/actualizados en `tests/test_gui_imagenes.py`,
`tests/test_gui_textos_sistema.py`, `tests/test_gui_configuracion.py`,
`tests/test_gui_bloques_rigidos.py` y `tests/test_gui_usuarios.py` —
mismo criterio en los cinco: alertas de éxito/cancelación capturadas
monkeypatcheando `QMessageBox.information`/`question`, `reiniciar()`
llamado directo para confirmar que descarta el estado transitorio
correspondiente a cada pantalla.

### Grilla y mensajería (puntos 83-96)

**Grilla semanal** (`_PanelGrillaSemanal`, `grilla_operativa.py`):
- Punto 87: cadena de foco explícita sobre el panel de Filtros de la
  grilla embebida (`GrillaOperativaWidget.widgets_filtro_para_foco()`,
  ya existía para este mismo propósito en Reservas) — Localidad →
  Edificio → Unidad → checks de día → Profesional, wrap-around gratis.
  `reiniciar()`/`showEvent` enfocan el primero de la cadena.
- Punto 86: la solapa entera pasa a estar envuelta en un `QScrollArea`
  propio (antes agregaba todo directo a `self`) — si la grilla se
  configura con más horarios de los que entran en la pantalla
  maximizada, se puede escrolear en vertical sin perder de vista
  "Detalle" ni la leyenda de colores, mismo criterio "los cuadros
  escrolean, no la pantalla" del resto del sistema.
- Puntos 1.2/1.5/1.7/1.8/1.11 ya resueltos (selector de profesional,
  tabla excluida del Tab, bordes de filtro/grilla, líneas sin doble
  efecto — ver 1.7/1.8 más arriba); el punto 85 ("no se ve la línea de
  las 21hs") queda cubierto por el mismo `QScrollArea` nuevo.

**Centro de mensajería** (`_PanelCentroMensajeria`, `mensajeria.py`):
ya tenía una cadena de foco explícita de una ronda anterior
(Filtro→Período→los dos checks→Copiar mensaje→Actualizar→Mensaje
grupal→vuelve a Filtro) que YA coincidía exacto con el punto 92 — no
hizo falta tocarla. Lo que faltaba:
- Punto 91: la etiqueta "Filtro" pasa a "Filtro de visualización".
- Punto 90: `_al_cambiar_enviada` ya conservaba filtro/período/checks al
  refrescar (`actualizar()` los lee tal cual están, sin tocarlos) — lo
  que faltaba era volver el scroll de la tabla al principio
  (`self.tabla.scrollToTop()`) después de marcar/desmarcar "Enviada",
  para que el reordenamiento por color no deje la vista a mitad de la
  tabla.
- 1.4: `reiniciar()`/`showEvent` nuevos — resetean Filtro/Período/los
  dos checks a su default (distinto del refresco de punto 90, que a
  propósito CONSERVA esos valores).

**Mensajes predefinidos** (`_PanelMensajesPredefinidos`,
`mensajes_predefinidos.py`): punto 95, cadena de foco completa —
Buscar → Categoría → Dirigido a → Localidad → Edificio → Unidad →
Consultorio → Copiar mensaje → Nuevo → Editar → Eliminar. El
`PantallaCRUD` interno pasa a `instalar_foco=False` (mismo criterio que
Gastos operativos: "apagalo cuando la pantalla arma su propia cadena
que combina los botones del CRUD con los suyos") y la pantalla arma su
propia cadena con `instalar_enter_avanza_foco`, combinando
`self.crud.campo_buscar`/`boton_nuevo`/`boton_editar`/`boton_eliminar`
con los seis selectores de contexto y "Copiar mensaje". `reiniciar()`/
`showEvent` nuevos llaman a `self.crud.reiniciar()` (ya limpia Buscar y
refresca, ver la sección de `crud_generico.py` más arriba) y enfocan el
primero de la cadena completa.

### Bug real encontrado en esta tanda: `QMessageBox.question`/`information` reales cuelgan la suite sin mockear — default global en `conftest.py`

Al correr la suite completa después de sumar las alertas de éxito/
cancelación de la tanda anterior (1.11, en `PantallaCRUD` y varios
paneles armados a mano), se detectó un hang real: `QT_QPA_PLATFORM=
offscreen` no vuelve "no-op" a `QMessageBox.exec()` — sigue siendo un
diálogo MODAL de verdad (abre su propio loop de eventos y espera a que
lo cierren), así que cualquier test que disparara una acción de crear/
editar/eliminar sin mockear `information`/`warning`/`question` se
quedaba esperando para siempre un clic que nunca iba a llegar.
Reproducido puntualmente contra `test_catalogos.py::test_pantalla_
edificios_campo_libre_se_guarda_y_se_ve_en_la_tabla` (sin ningún mock de
estos tres métodos) con `pytest -v` + `timeout`, confirmando el hang
exacto.

Mismo motivo que ya tenían decenas de archivos de test, cada uno con su
propia fixture `autouse` local mockeando estos tres métodos — en vez de
seguir sumando una fixture local más por archivo nuevo (y arriesgarse a
olvidar alguno, como pasó acá), se sube un default a `tests/conftest.py`:
`_sin_dialogos_modales_por_defecto` (autouse, toda la suite)
mockea `information`/`warning` a no-op y `question` a "Sí" — cualquier
archivo que ya tenga su propia fixture local haciendo lo mismo sigue
funcionando igual (pytest instancia las fixtures `autouse` de un
conftest ancestro antes que las del módulo de test, así que la local
termina pisando/reafirmando el mismo valor), y los tests puntuales que
necesitan otra respuesta de `question` o capturar el texto de un
`information` siguen pudiendo pisarlo con su propio `monkeypatch.
setattr` dentro del test. Un default seguro así, aplicado una sola vez,
cubre también cualquier `QMessageBox` que se sume de acá en adelante en
el resto de este documento sin tener que acordarse de mockearlo archivo
por archivo.

## Placas para timbres / Estadísticas / Balance del negocio (batch #17.x del documento)

Decimoséptima tanda de `v0.11.2026.10`, cerrando "PLACAS PARA LOS
TIMBRES", "ESTADISTICAS" y "BALANCE DEL NEGOCIO".

### Placas para timbres

1.2 (selector de profesional)/1.3 (orden de unidad, ya resuelto en los
diálogos vía `reservas._opciones_unidad`)/1.5 (`excluir_tabla_del_tab`)
confirmados ya resueltos, sin cambios. 1.4 ya estaba completo en
"Búsqueda y asignación" (`_PanelBuscarPlacas.showEvent` ya reinicia
Profesional/cascada/orden desde una tanda anterior); en "Impresión" se
confirmó, investigando, que es un caso de preservación deliberada —
mismo criterio que Oferta/Estado de cuenta: la cola de impresión
(`self._cola_impresion`) está pensada explícitamente para sobrevivir
al cambiar de solapa ("Buscar y asignar" ↔ "Imprimir" comparten este
estado, según el propio docstring de la clase), así que resetear el
combo de profesional o la selección de placa en cada `showEvent`
rompería ese diseño sin que nadie lo pidiera — se deja como está, solo
con el foco inicial que ya tenía.

**1.11 — alertas de éxito**: "Asignar placa nueva"/"Reasignar"/
"Liberar posición" nunca avisaban nada al terminar con éxito (la
confirmación de "Liberar posición" ya existía, era solo la falta de
cierre lo que faltaba) — se suma un `QMessageBox.information` a cada
una. "Generar PDF" (solapa Imprimir) ya avisaba la ruta generada desde
que se armó esa funcionalidad; "Agregar a impresión"/"Quitar de la
lista" no suman nada, mismo criterio que el resto del sistema para
operaciones de lista en memoria sin persistencia (Oferta, Lista de
espera).

### Estadísticas

1.3 (orden de unidad)/1.7 (foco) confirmados ya resueltos desde la
tanda de "Orden natural de códigos..." y #102 — sin cambios de código.

### Balance del negocio (Ingresos/Resultado)

1.5 (`excluir_tabla_del_tab`)/1.7 (foco, #103) confirmados ya
resueltos. **"Selector año/mes en línea"**: `campo_periodo` pasa de
`QLineEdit` libre ("AAAA-MM") a `SelectorPeriodo` (el mismo widget
Año+Mes ya introducido en Liquidaciones > "Emisión de archivos") en
`_PanelFiltrosMixin._armar_panel_filtros` — un solo cambio en el mixin
compartido alcanza para las dos solapas (Ingresos y Resultado), sin
duplicar nada. `_ver_periodo_actual` pasa de `setText(periodo_actual(...))`
a `set_periodo(...)`; las dos `actualizar()` (una por panel) pasan de
`self.campo_periodo.text().strip() or periodo_actual(self.conn)` a
`self.campo_periodo.periodo()` directo — `SelectorPeriodo` siempre
devuelve un período válido, ya no hace falta el fallback. La cadena de
foco pasa a incluir `campo_periodo.spin_anio`/`.combo_mes` por
separado, mismo criterio que Liquidaciones.

Tests nuevos: `tests/test_gui_placas.py`
(`test_asignar_reasignar_y_liberar_muestran_alerta_de_exito`);
`tests/test_gui_balance.py`
(`test_periodo_es_selector_anio_y_mes_en_linea_en_las_dos_solapas`),
más el ajuste de los 5 tests ya existentes que usaban `campo_periodo.
text()`/`.setText()` (pasan a `.periodo()`/`.set_periodo()`). Suite
combinada `test_gui_placas.py`+`test_gui_placas_para_timbres.py`+
`test_gui_balance.py`+`test_estadisticas.py`+`test_gui_estadisticas.py`:
110 passed. Suite completa: 2492 passed, sin regresiones (mismo
segfault intermitente ya documentado reapareció en dos corridas
seguidas y no se reprodujo en una tercera — confirmado no relacionado
con esta tanda).

## Cierre de `v0.11.2026.10`

Con "Placas para timbres"/"Estadísticas"/"Balance del negocio" cerradas,
las once secciones del documento (GENERAL, MENU LATERAL, ARCHIVOS Y
LISTAS, BASE DE DATOS DEL ESPACIO, CONFIGURACION GENERAL, USUARIOS Y
PERMISOS, PANEL DE CONTROL, GRILLA Y MENSAJERIA, RESERVAS, VALORES,
LIQUIDACIONES, PAGOS, REGISTRO DE AUSENCIAS, DISPONIBILIDAD,
PROFESIONALES, LLAVES Y OTROS CONCEPTOS, PLACAS PARA LOS TIMBRES,
ESTADISTICAS, BALANCE DEL NEGOCIO) quedan recorridas de punta a punta.
`pyflakes app/ tests/` sin ningún warning; suite completa confirmada en
verde varias veces a lo largo de todo este trabajo (último conteo:
2492 passed) — el único ruido fue el segfault intermitente de
`grilla_operativa.py::paintEvent` ya documentado en este archivo
(hallazgo de estabilidad `WA_StyledBackground`/`paintEvent` manual bajo
la plataforma Qt `offscreen`, reproducido y descartado varias veces
contra código sin cambios, nunca contra un cambio puntual de esta
tanda — no es un bug de producción, es una fragilidad propia del
entorno de test offscreen bajo construcción/destrucción masiva de
widgets Qt).

Puntos del documento que quedaron **sin implementar, documentados como
pendientes de aclaración** por ser genuinamente ambiguos sin el texto
original a la vista (mismo criterio en los tres: no se inventa el
alcance exacto de un pedido vago, se pregunta antes de programar algo
que puede no ser lo que la clienta tenía en mente):

- **Pagos — "autocierre de tanda"**: sin ningún rastro de un mecanismo
  de cierre automático en el código (solo manual, "Iniciar tanda"/
  "Cerrar tanda"), sin saber qué condición debería dispararlo.
- **Oferta de consultorios — "reducir proporcional"**: sin ninguna base
  en el código ni en rondas anteriores de qué debería reducirse ni en
  qué proporción.
- **Profesionales (Listado) — "botones mitad alto, etiquetas, cuadro
  documentación 5 items, Vista previa"**: cuatro puntos sin ningún
  rastro en CLAUDE.md ni en el código actual, incluida una posible
  vista previa de documentos sin saber qué formato debería mostrar.
- **Llaves — "check Bonificar depósito"**: sin saber qué debería eximir
  exactamente (¿a qué profesional? ¿bajo qué condición?).
- **Llaves — nueva solapa "Stock de llaves por profesional"**: una
  pantalla/reporte nuevo completo, sin ninguna especificación de
  columnas o agrupamiento más allá del nombre.

Los cinco quedan anotados en el checklist de trabajo para retomarlos en
cuanto la clienta aclare el alcance — no se perdieron de vista, se
decidió no adivinarlos.

## Resolución de tres de los cinco puntos pendientes de arriba

De los cinco puntos que habían quedado abiertos, la clienta resolvió
tres en esta vuelta (Pagos sin cambios, Oferta y Profesionales — esta
última, corregida en una vuelta posterior tras una interpretación
equivocada de la primera, ver abajo). Los dos de Llaves ("check
Bonificar depósito" y la nueva solapa "Stock de llaves por
profesional") se resolvieron después, en la sección "Llaves: bonificado/
abonado..." más abajo — NO como una solapa nueva, sino como un
prototipo dentro de "Movimientos y tenencias de llaves".

### Pagos — "autocierre de tanda": dejado tal cual

Pedido explícito de la clienta: "Dejalo como está, no toque nada." Sin
ningún cambio de código — la pantalla sigue con el cierre manual de
siempre ("Iniciar tanda"/"Cerrar tanda").

### Oferta de consultorios: las cuatro columnas comprimidas hasta "Alcanza con esta franja sola (O)"

Pedido explícito de la clienta: todo el contenido de las cuatro
columnas de "Oferta de consultorios" tiene que entrar en el mismo alto
visible que ya alcanzaba hasta el check "Alcanza con esta franja sola
(O)" (el último control visible de la primera columna antes de esta
vuelta) — "de derecha a izquierda":

- **Columna 4 (la grilla)**: "la grilla come altura del cuadro de
  detalle" — se revierte `dar_stretch_a_detalle()` (sumado en una ronda
  anterior para que "Detalle" absorbiera el alto de sobra). Vuelve el
  comportamiento DEFAULT de `GrillaOperativaWidget` (la tabla con
  `stretch=1`, "Detalle" con su alto máximo fijo de siempre, sin
  stretch) — ahora es la tabla la que crece con cualquier alto de
  sobra, "Detalle" se queda en su tamaño chico.
- **Columna 3 (Filtros/Referencias de colores)**: "Referencias de
  colores" pasa de la versión grande (una sola columna, cuadraditos de
  40px) a `mostrar_leyenda_colores(compacta=True)` (2 columnas,
  cuadraditos de 28px) — mismo criterio `hacer_compacta()` que ya usa
  Reservas. Los `_AJUSTE_ALTO_MUESTRA_LEYENDA_REGULAR`/`_AISLADA` se
  tunearon con un script de geometría contra el modo compacto, bajo la
  plataforma offscreen (`self.grilla._panel_filtros.sizeHint()` no
  refleja un cambio de tamaño de la leyenda sin `updateGeometry()`
  antes, hallazgo ya documentado para este mecanismo).
- **Columna 2 ("Franjas agregadas a esta búsqueda")**: `lista_franjas`
  pasa de `stretch=1` sin tope (crecía hasta el pie de la columna,
  dejando mucho espacio en blanco) a un alto FIJO de ~3 líneas
  (`_ALTO_LISTA_FRANJAS`, mismo criterio de medición — alto de fila +
  marco — que `_ALTO_LISTA_DOCUMENTOS` en Profesionales, ver más abajo)
  — sigue scrolleando sola si hay más franjas de las que entran.
  `columna_franjas` suma un `addStretch()` al final (en vez del
  `stretch=1` que tenía la lista) para que el contenido (etiqueta +
  lista + 3 botones) quede pegado arriba en vez de centrarse en el alto
  que le dé el splitter — mismo mecanismo ya documentado para Reservas
  ("un tope de alto sin un `addStretch()` final en el layout que lo
  contiene centra el contenido en vez de pegarlo arriba").
- **Columna 1 (el formulario)**: "Combinación de consultorios" pierde
  su etiqueta propia y el combo pasa a vivir directo debajo del título
  "Requisitos de búsqueda" (antes "Características pedidas", renombrado
  a pedido explícito de la clienta en el mismo movimiento). Los checks
  "Con sillones"/"Con placard" se sacan por completo de `_grid_
  caracteristicas` (quedan Ventana/Camilla en la primera fila, Tamaño/
  Valor máximo en las dos que siguen) — `_armar_busqueda_actual` manda
  `sillones=False, placard=False` siempre, el campo sigue existiendo en
  `Busqueda` para cualquier otro llamador (ej. importación), solo deja
  de poder activarse desde esta pantalla.

**Corrección sobre una primera interpretación equivocada**: una primera
vuelta de esta misma tanda había sacado por completo "Agregar franja a
la búsqueda"/"Quitar franja seleccionada" de esta columna, leyendo mal
el pedido ("elimina los checks... y los botones que digan 'Agregar
franja' y 'Quitar franja' nada más, esto para que puedas reducir la
altura de los mismos") como "elimina también esos dos botones" — la
clienta corrigió de inmediato: **los dos botones se conservan**, lo que
pedía reducir era su ALTURA (no eliminarlos), para que terminen a la
altura donde hoy se ve "Alcanza con esta franja sola (O)". Se
restauraron `boton_agregar_franja`/`boton_quitar_franja` (misma `fila_
franja` horizontal, mismo texto a dos líneas de siempre) con un
override de estilo puntual, `_ESTILO_BOTON_COMPACTO_FRANJA = "padding:
3px 16px;"` (mismo criterio que `_ESTILO_BOTON_COMPACTO` de Reservas:
un override local, sin tocar `estilos.py`), y se sumaron de vuelta a
`self._foco`.

Captura enviada a la clienta (ventana completa 1500×850, mismo criterio
`VentanaPrincipal`/`ir_a_seccion` de siempre) para confirmar la
interpretación antes de seguir afinando el ajuste pixel a pixel —
pedido explícito: "mandame una captura de pantalla con lo que
interpretaste y vamos confirmando antes de tocar código". Con la
combinación de los cuatro puntos de arriba, las cuatro columnas ya
entran sin necesitar scroll en esa ventana de referencia (los dos
botones terminan dentro del alto visible) — pendiente de confirmación
visual de la clienta antes de dar el ajuste fino por cerrado.

Tests en `tests/test_gui_oferta.py`:
`test_agregar_y_quitar_franja_siguen_en_la_misma_fila_y_compactos`
(reemplaza al viejo "en la misma fila", ahora también confirma el
`_ESTILO_BOTON_COMPACTO_FRANJA`); `test_columna_del_formulario_mas_
angosta_que_antes` vuelve a confirmar que los dos botones EXISTEN (la
versión intermedia, ya corregida, llegó a afirmar lo contrario);
`test_lista_franjas_crece_hasta_el_pie_y_es_scroleable` se reemplaza
por `test_lista_franjas_alto_fijo_y_escrolea_con_mas_de_las_que_
entran` (alto fijo en vez de `stretch=1`, sigue escrolleando con 20
franjas cargadas directo vía `_agregar_franja`);
`test_caracteristicas_pedidas_en_grilla_de_pares_con_placard` se
reemplaza por `test_caracteristicas_pedidas_en_grilla_de_pares_sin_
sillones_ni_placard` (confirma que los dos checks no existen más, y la
posición de fila/columna de los que quedan); `test_placard_se_incluye_
en_la_busqueda_armada` se reemplaza por `test_busqueda_armada_nunca_
filtra_por_sillones_ni_placard` (sillones/placard siempre en `False`);
`test_detalle_pegado_debajo_de_la_grilla_sin_relleno` se reemplaza por
`test_la_grilla_come_la_altura_del_cuadro_detalle` (stretch invertido:
tabla=1, Detalle=0); `test_grilla_nunca_se_recorta_con_mas_horarios_
detalle_cede_espacio` se renombra `test_grilla_nunca_se_recorta_con_
mas_horarios` (la tabla se protege a sí misma con su propio `stretch=1`,
ya no depende de que "Detalle" ceda); se actualiza el docstring de
`test_columna_de_franjas_tiene_titulo_lista_y_tres_botones_al_pie`
(ya no menciona el `stretch=1` de la lista); se suma
`test_combinacion_de_consultorios_bajo_el_titulo_requisitos_de_busqueda`.

### Profesionales (Listado): botones a la mitad de alto, Vista previa de archivos

Pedido explícito de la clienta sobre "Listado de profesionales"
(`_PanelProfesionales`, `app/gui/pantallas/profesionales.py`):

- **Los cinco botones de la columna** (Nuevo/Editar/Eliminar del CRUD +
  Agregar archivo/Eliminar archivo) **bajan a la mitad del alto
  default** — `_ESTILO_BOTON_COMPACTO = "padding: 0px 16px;"` (constante
  LOCAL de este archivo, sin relación con la de mismo nombre en
  `reservas.py` — cada pantalla define la suya con el valor que le haga
  falta, mismo criterio ya documentado para "botones compactos" de
  Reservas), medido con un script de geometría contra el alto default
  real de `botonPrimario` (32px con `hoja_estilos()` aplicada): 0px de
  padding vertical da exactamente 16px, la mitad buscada.
- **"Documentación del profesional seleccionado" pasa a "Documentación
  del profesional"** — pedido explícito, así entra en una sola línea
  sin wrapear.
- **El cuadro de `lista_documentos` baja de alto**: pasa de `stretch=1`
  sin tope (crecía hasta el pie del panel) a un alto FIJO para ~5
  líneas (`_ALTO_LISTA_DOCUMENTOS = 76`, medido con un script de
  geometría — alto de fila de `QListWidget` + marco × 2 + 4px, mismo
  criterio que otras listas/tablas de ancho fijo del sistema) — sigue
  scrolleando sola (default de Qt) si hay más archivos de los que
  entran.
- **Cuadro nuevo "Vista previa"**, debajo de "Documentación del
  profesional" (los dos botones de Agregar/Eliminar archivo quedan
  entre la lista y la vista previa, sin cambiar de posición) — con
  `stretch=1`, es el único elemento del panel izquierdo que absorbe el
  alto de sobra (mismo mecanismo que antes usaba `lista_documentos`),
  así que llega hasta el pie del panel, a la par de la tabla de la
  derecha (`panel_extra_izquierda` de `PantallaCRUD` ya se agrega con
  `stretch=1` en el `form` del panel izquierdo — ver "Catálogos
  (PantallaCRUD genérica)" más arriba). Reusa el mismo mecanismo de
  Gestor de archivos/Archivos para enviar (imagen con `QPixmap` directo,
  PDF con la primera página vía `_pixmap_primera_pagina_pdf`, sin vista
  para cualquier otra extensión — acá solo hace falta cubrir PDF/JPG/
  PNG, las únicas que admite esta documentación) dentro de un
  `QScrollArea` propio (con `setMinimumSize(pixmap.size())` sobre la
  etiqueta, mismo motivo ya documentado en Archivos para enviar: sin
  esto el `QScrollArea` recorta la imagen al alto del viewport en vez de
  habilitar el scroll). Se actualiza sola al seleccionar un archivo de
  la lista (`itemSelectionChanged`), al elegir otro profesional (la
  lista se repuebla y la vista previa se resetea con ella) y al agregar/
  eliminar un documento.

  `_actualizar_documentacion` suma `item.setData(Qt.ItemDataRole.
  UserRole, str(ruta))` a cada fila de `lista_documentos` para poder
  resolver la ruta completa al armar la vista previa — `listar_
  documentos` ya devolvía objetos `Path` completos, solo que antes se
  usaba únicamente `.name` para el texto visible.

Tests nuevos en `tests/test_profesionales.py`: `test_pantalla_
profesionales_botones_quedan_a_la_mitad_del_alto_default` (compara
contra un botón de referencia con `hoja_estilos()` aplicada);
`test_pantalla_profesionales_titulo_documentacion_sin_seleccionado`;
`test_vista_previa_arranca_con_el_texto_de_ayuda_y_sin_seleccion_
vuelve_a_el` (incluye el caso de una extensión no soportada, ".txt",
que cae al mensaje de "sin vista"); `test_vista_previa_de_imagen_
muestra_el_pixmap`; `test_cambiar_de_profesional_actualiza_la_vista_
previa` (confirma que no queda la imagen del profesional anterior
pegada en pantalla al elegir uno sin documentos). El test ya existente
de `lista_documentos` se renombra `test_pantalla_profesionales_lista_
documentos_alto_fijo_y_vista_previa_se_estira` y se reescribe para el
nuevo comportamiento (alto fijo en la lista, `area_vista_previa` con
el alto de sobra).

## Selector de profesional: el filtro en vivo y el select-all por Tab nunca funcionaron de punta a punta

Segunda prueba del flujo de trabajo por temas separados: sesión nueva,
solo con `docs/historial/general.md` como contexto (donde vivían las
rondas anteriores de este mismo widget). La clienta reportó tres cosas
que ya se habían dado por resueltas en rondas anteriores ("Selector de
profesional: solo por código... select-all al enfocar", más arriba en
este archivo, y "1.2 — Selector de profesional: ya resuelto"):
mayúsculas/minúsculas, buscar en cualquier parte de la cadena (no solo
el principio) y select-all al llegar con Tab — con un ejemplo puntual
de cada una ("x1" no encuentra nada pero "X1" sí; "lo ve" no encuentra
"R1 - Lic. Virginia Lo Veci"; el combo Profesional de Reservas
regulares, con "Todos los profesionales" de default, no selecciona
nada al llegar por Tab).

Investigado ANTES de tocar código, con scripts que simulan tipeo/Tab
reales (no solo leer el código ni confiar en que los tests ya pasaban):
los tres reportes eran ciertos, con dos causas distintas — ninguna de
las dos estaba cubierta por los tests existentes, que probaban piezas
aisladas en vez del comportamiento real de punta a punta.

### Causa 1 (ítems 1 y 2): `QCompleter` tiene su propio filtro, aparte del nuestro

`_ProxyBusquedaSinAcentos` (el `QSortFilterProxyModel` que ya filtraba
bien, sin distinguir mayúsculas/acentos, por cualquier posición de la
cadena) sigue correcto — el problema es que `QCompleter` arma, ADEMÁS,
su PROPIO motor de filtrado interno sobre el modelo que se le pasa
(`completionPrefix`/`filterMode`/`caseSensitivity`), que nunca se había
tocado y se queda en el default de Qt: `MatchStartsWith` + `CaseSensitive`.
Ese filtro propio se aplica ENCIMA del nuestro, no en su lugar —
cualquier fila que `proxy` ya dejaba pasar podía desaparecer igual antes
de llegar al desplegable. Confirmado con un script que simula
`textEdited` real y lee `completador.completionModel()` (lo que de
verdad se ve en pantalla, a diferencia de llamar `proxy.
establecer_patron(...)` directo como hacían los tests viejos): "x1"
mostraba `[]` aunque hubiera un "X1 - ..." cargado, y "lo ve" también
`[]` aunque "R1 - Lic. Virginia Lo Veci" estuviera en la lista.

Ajustarle solo `filterMode`/`caseSensitivity` al completer no alcanza
por sí solo (confirmado aparte): sigue sin ignorar acentos, que es
justo lo que `proxy` ya resuelve — mezclar los dos filtros a medias
hubiera dejado un comportamiento inconsistente según el caso. Se
neutraliza por completo el filtro propio del completer reseteando su
`completionPrefix` a vacío cada vez que se actualiza el patrón de
`proxy` (`_al_tipear`, nueva, reemplaza la conexión directa de
`textEdited` a `proxy.establecer_patron`) — con prefijo vacío, el
filtro de Qt acepta cualquier fila trivialmente, dejando a `proxy` como
única fuente de verdad del filtrado, que es la intención original del
módulo desde que se armó.

### Causa 2 (ítem 3): `QComboBox` no tiene `.selectAll()` propio

Bug distinto, y más general — vive en `app/gui/widgets/foco.py`
(`_EnterAvanzaFoco._mover`), el mecanismo COMPARTIDO por Tab/Enter en
TODOS los formularios del sistema, no en `selector_profesional.py`.
`_mover` seleccionaba el contenido del widget destino con `if
seleccionar_todo and hasattr(candidato, "selectAll"): candidato.
selectAll()` — pero `candidato`, para un combo, es el `QComboBox`
completo, y `QComboBox` NO tiene `.selectAll()` propio (solo lo tiene
su `.lineEdit()` interno) — así que esa condición daba `False` para
CUALQUIER combo editable llegado por Tab, en cualquier pantalla del
sistema, no solo el selector de profesional. Confirmado con un script
que tabula de un campo a un combo real: el foco llegaba bien, pero
`lineEdit().selectedText()` quedaba vacío. El click directo del mouse
sí seleccionaba (ese es `_SeleccionarTodoAlEnfocar`, un mecanismo
aparte dentro de `selector_profesional.py`, sin relación con `foco.py`)
— por eso no se había notado en ninguna revisión anterior, todas las
pruebas manuales de "select-all" documentadas hasta ahora se hicieron
clickeando, no tabulando.

Arreglo: `_EnterAvanzaFoco._mover` suma un helper `_seleccionar_todo`
que, para un `QComboBox` editable, selecciona sobre `.lineEdit()` en
vez de sobre el combo — beneficia a cualquier combo editable del
sistema llegado por Tab, no solo a los selectores de profesional.

Tests nuevos: `tests/test_gui_widget_selector_profesional.py`
(`test_desplegable_real_no_distingue_mayusculas_de_minusculas`,
`test_desplegable_real_filtra_por_substring_en_el_medio` — las dos
simulan tipeo real y leen `completador.completionModel()`, el punto
exacto donde se coló el bug, no `proxy` en aislado como los tests
viejos); `tests/test_gui_widget_foco.py`
(`test_tab_selecciona_todo_el_texto_de_un_combo_editable_al_llegar`,
con un `QComboBox` editable real en la cadena, no solo `QLineEdit` como
el test ya existente de esta misma regla).

### Segunda vuelta: la primera corrección no alcanzaba con tipeo real, y el select-all no arrancaba sola la pantalla

La clienta probó el arreglo de arriba en la pantalla real y volvió con
tres conclusiones: mayúsculas/minúsculas seguía sin funcionar, buscar en
el medio de la cadena seguía sin funcionar, y el select-all funcionaba
al tabular y volver pero NO al entrar recién a la solapa/pantalla. Para
el select-all dio dos alternativas (mover el foco a la solapa en el
`QTabWidget` al clickearla, o chequear el caso en el primer foco del
campo) y pidió la segunda, dejando la implementación a criterio propio
por ser la de menor complejidad.

**Por qué la corrección anterior daba falso positivo.** El script de
diagnóstico de la primera vuelta simulaba el tipeo emitiendo la señal a
mano (`lineEdit().textEdited.emit(texto)`) y fijando `completionPrefix`
en el mismo slot — con eso, reseteaba el prefijo a vacío y el filtro
propio de `QCompleter` quedaba neutralizado, confirmado por ese mismo
script. Pero `QLineEdit` y `QCompleter` tienen, además, una conexión
interna de Qt a nivel C++ que TAMBIÉN fija `completionPrefix` al texto
tipeado — y lo hace en un punto del procesamiento de la tecla real que
el slot de Python conectado a `textEdited` no puede garantizar que
corra después. Repetir el diagnóstico con tipeo REAL (`QTest.
keyClicks`, que sintetiza eventos de teclado de verdad en vez de
emitir la señal a mano) lo confirmó: `completionPrefix()` terminaba
siendo el texto tipeado tal cual, no vacío, pese al reseteo — exactamente
lo que la clienta reportó. Cualquier arreglo que dependa del ORDEN en
que Qt dispara señales contra código Python es frágil por definición;
los dos tests nuevos de la primera vuelta (`test_desplegable_real_...`)
pasaban igual porque también usaban señal emitida a mano, no tipeo
real — dieron el mismo falso positivo que el script original. Lección
para cualquier test de este tipo de ahora en más: verificar con
`QTest.keyClicks`/`QTest.keyClick` (teclado real), nunca con la señal
emitida a mano, cuando lo que se prueba es la interacción entre un
widget nativo de Qt y su propia maquinaria interna.

**Arreglo robusto (sin pelear con el orden de señales).** En vez de
neutralizar el filtro propio de `QCompleter`, se lo hace filtrar
exactamente como hace falta, con sus propios puntos de extensión:

1. `_ProxyBusquedaSinAcentos` deja de filtrar filas — ahora solo expone
   un rol de dato nuevo, `_ROL_TEXTO_NORMALIZADO`, con el texto de cada
   fila ya sin acentos y en minúsculas.
2. El `QCompleter` (`_CompleterSinAcentos`, subclase nueva) usa ese rol
   como `completionRole`, con `setFilterMode(MatchContains)` +
   `setCaseSensitivity(CaseInsensitive)` — así su propio motor nativo ya
   filtra sin distinguir mayúsculas ni por posición, sin ningún filtro
   nuestro corriendo en paralelo ni ninguna carrera de señales.
3. Falta normalizar lo que el USUARIO tipeó (si no, escribir "díaz" con
   tilde no matchearía el rol normalizado "diaz"): `_CompleterSinAcentos`
   overridea `splitPath(path)` (método virtual público de `QCompleter`,
   el punto donde Qt arma la cadena que de verdad usa para comparar)
   para devolver `[_normalizar(path)]`.
4. Como el rol de matcheo es ahora el texto normalizado, Qt insertaría
   ESE texto (minúsculas, sin acentos) al elegir una opción del
   desplegable — se corrige overrideando también `pathFromIndex(index)`
   para devolver el texto original (`DisplayRole`), no el normalizado.

Verificado con tipeo real (`QTest.keyClicks`): "x1"/"X1" encuentran
"X1 - Carlos Pérez"; "lo ve" encuentra "R1 - Lic. Virginia Lo Veci";
"diaz" encuentra "R4 - Dr. Roberto Díaz"; elegir esa opción del
desplegable inserta el texto original con tilde, no el normalizado.

**Select-all al entrar a la pantalla (no solo al tabular/clickear).**
Instrumentando el evento real (no asumiendo), se confirmó que
`combo.setFocus()` llamado desde un `showEvent` (el patrón que usa casi
toda pantalla del sistema para arrancar la cadena de foco) entrega el
evento `FocusIn` al `QComboBox` de AFUERA, nunca a su `lineEdit()`
interno — a diferencia de un click directo del mouse en el campo de
texto, que sí se lo entrega al `lineEdit()`. `_SeleccionarTodoAlEnfocar`
escuchaba solo en el `lineEdit()`, así que el caso de "recién entro a la
pantalla" nunca disparaba el select-all. Arreglo elegido (la opción que
pidió la clienta, sin tocar el `showEvent` de ninguna pantalla en
particular): `_SeleccionarTodoAlEnfocar` ahora instala el mismo filtro
de eventos también en el `QComboBox` (no solo en su `lineEdit()`),
así que cualquiera de los dos widgets que reciba el `FocusIn` dispara el
mismo `selectAll()` sobre el `lineEdit()` — cubre de una sola vez el
click directo, la llegada por Tab (ver Causa 2 más arriba, sin cambios)
y ahora también el `showEvent`, en los ~18 selectores de profesional
del sistema sin tocar ninguna pantalla individual.

Tests: se reescribieron `test_desplegable_real_no_distingue_mayusculas_
de_minusculas` y `test_desplegable_real_filtra_por_substring_en_el_medio`
para tipear con `QTest.keyClicks` en vez de emitir la señal a mano
(corrigiendo el mismo problema de fondo que motivó esta segunda vuelta),
igual que `test_completer_filtra_por_codigo`/`..._por_nombre_en_el_medio_
de_la_cadena`/`..._sin_distinguir_acentos` (antes miraban `proxy`
aislado, que ya no filtra — ahora miran `completador.completionModel()`,
con tipeo real, igual que el resto). Nuevos:
`test_al_elegir_una_opcion_del_desplegable_inserta_el_texto_original`
(verifica `pathFromIndex` directo) y
`test_setfocus_directo_en_el_combo_selecciona_todo_el_contenido`
(simula el patrón `showEvent` llamando `combo.setFocus()` sin pasar por
el `lineEdit()`, el caso que faltaba cubrir).


## Categorías B/E/C: validación de cargos, pagos y depósitos de llave

Hilo abierto a partir de Reinicio de prueba (al decidir qué categorías
van en la tabla de saldos): la clienta repasó las seis categorías y
confirmó que el sistema tenía un hueco real, no solo cosmético —
"Cargos especiales", "Registrar pagos" y "Asignar llave" ya excluían a
C de sus combos de creación, pero SÍ dejaban elegir B o E sin ningún
aviso ni redirección.

Investigado antes de tocar código: `calcular_liquidacion` (`app.
negocio.liquidaciones`) filtra `CargoEspecial` por el `IdProfesional`
EXACTO del R que se está liquidando, no por los ids consolidados del
equipo (`ids_consolidados`, que sí usa para horas/reservas) — y nada
lee nunca el saldo propio de un E (`CATEGORIAS_CON_LIQUIDACION_MENSUAL`
es solo `("R",)`). Un cargo o un pago dejado en un E no era solo "falta
de aviso": quedaba huérfano en la base para siempre, sin que ninguna
liquidación ni pantalla lo mostrara jamás.

Reglas confirmadas por la clienta:

- **R/A/X**: a sí mismos — las únicas con cuenta propia.
- **C**: nunca ningún movimiento — "no se puede hacer ningún otro
  movimiento con ellos. Solo se pueden utilizar para listas de espera."
- **B**: "Sí pueden registrarse movimientos de llaves a nivel stock,
  pero no reciben ningún cargo ni tienen que abonar nada, todo lo que se
  les carge queda bonificado."
- **E**: "Se puede registrar lo mismo que los de categoría R y A... la
  diferencia es que los detalles y los cargos se trasladan al
  profesional cabeza de equipo."
- Para B, bloquear con un error claro (no forzar $0 en silencio) — mismo
  criterio que ya usa el sistema para categorías inválidas en Reservas
  (`_validar_categoria_reserva`).
- Los cargos/pagos/depósitos que ya existan cargados contra un B o un E
  de antes de este cambio se dejan como están — la validación nueva
  rige solo para lo que se cree de acá en adelante.

### Implementación

`resolver_profesional_para_cargo(conn, id_profesional)` (nueva,
`app.negocio.pagos`): a sí mismo para R/A/X; al cabeza de equipo (tiene
que ser un R válido) para E; `ValueError` para B y C. Compartida por
`registrar_pago` y `crear_cargo_especial` — y, de rebote, por los
depósitos/reintegros de llave de `app.negocio.llaves` (`asignar_llave`/
`devolver_llave`), que ya llamaban a `crear_cargo_especial`
internamente, así que no necesitaron su propio chequeo de B/E. El
movimiento de stock (`LlaveMovimiento`) sigue a nombre del E real (quien
físicamente tiene la llave) — solo el cargo monetario se redirige.

`asignar_llave` suma su propio guardarraíl de C (bloquea el stock
también, no solo el depósito) — mismo criterio que `reservas.
_validar_categoria_reserva`, defensa en profundidad sobre lo que ya
excluía el combo.

B se saca de los combos de creación de Cargos especiales
(`_CATEGORIAS_CON_CARGOS`) y Registrar pagos (`_CATEGORIAS_CON_PAGOS`) —
ya que `resolver_profesional_para_cargo` lo bloquea siempre, mejor que
el operador ni lo vea ofrecido a que choque con un error. Se queda en
el combo de "Asignar" llave (`_CATEGORIAS_CON_LLAVES`, sí puede recibir
el movimiento de stock); ahí, `_DialogoAsignar._al_cambiar_profesional`
fuerza el combo "Depósito" a "Bonificado" y lo deshabilita mientras el
profesional elegido sea un B, para que el operador no llegue a probar
"Abonado" y chocar con el error.

En `pagos.py` (GUI), `_preguntar_restablecer_descuento` (DC-06 §5.2)
tiene que operar sobre el mismo profesional al que `registrar_pago` ya
redirigió el saldo (el cabeza de equipo si era un E) — se resuelve de
nuevo ahí mismo con `resolver_profesional_para_cargo` antes de
llamarla, porque `suspender_descuento_periodo` escribe directo sobre el
`id_profesional` que recibe, sin resolver nada por su cuenta.
`regenerar_si_corresponde` (ya usada en los tres lugares) no necesitó
tocarse: ya resuelve E→cabeza de equipo por su cuenta vía
`liquidaciones.id_profesional_liquidable`.

Tests nuevos: `tests/test_pagos.py` (`resolver_profesional_para_cargo`
en sus seis casos — R/A/X a sí mismos, E al cabeza válido, E sin cabeza
o con cabeza no-R rechaza, B rechaza, C rechaza, inexistente rechaza —
más `registrar_pago`/`crear_cargo_especial` redirigiendo un E y
rechazando un B), `tests/test_llaves.py` (`asignar_llave` rechaza C,
rechaza depósito cobrado a un B, permite stock sin depósito a un B,
redirige el depósito de un E al cabeza de equipo manteniendo el
movimiento a nombre del E), `tests/test_gui_novedades.py`/`tests/
test_gui_pagos.py` (B ya no aparece en los combos de creación),
`tests/test_gui_llaves.py` (el combo Depósito se fuerza y deshabilita
para B, se reabilita para R). Un test preexistente de orden de tabla
(`test_tabla_cargos_especiales_orden_por_defecto...`) que creaba un
cargo contra un B vía `crear_cargo_especial` pasa a insertarlo directo
por el repositorio, simulando un registro histórico de antes de esta
validación.

## Selectores de fecha: Flecha arriba/abajo mueve la fecha completa (todo el sistema)

Pedido de la clienta, alcance general: "que con el cursor para arriba o
para abajo me permita subir y bajar de fecha en fecha de a un día a la
vez pero no solamente dentro de la semana, sino avanzar más allá de la
misma." Investigado antes de tocar código, con un script de prueba
armado contra un `QDateEdit` real: por default Qt mueve el VALOR DE LA
SECCIÓN donde está el cursor (día, mes, año, o -si el formato tiene
"ddd"- día de la semana), no la fecha completa. Confirmados dos bugs
reales por eso:
- Con el cursor sobre "dd" (día de mes, el caso de cualquier campo sin
  el día de semana): al llegar al último día del mes, Flecha arriba se
  queda clavado ahí, nunca pasa al mes siguiente.
- Con el cursor sobre "ddd" (día de semana — la sección que arranca
  enfocada en los campos con ese formato, ej. Registro de ausencias,
  Fechas especiales): al llegar al último día de la semana, Flecha
  arriba salta HACIA ATRÁS al mismo día de la semana anterior y se
  queda trabado repitiendo esa misma fecha — el síntoma exacto que
  reportó la clienta ("solo navega dentro de la misma semana").

`instalar_flechas_cambian_fecha_completa(campo)` (`app/gui/widgets/
fecha.py`, nueva, mismo módulo que `aplicar_color_sabado_negro`):
intercepta Flecha arriba/abajo con un event filter sobre el propio
campo y avanza/retrocede la FECHA completa (`QDate.addDays`) en vez de
dejar que Qt mueva la sección, sin importar dónde esté el cursor.
Aplicado en los 9 puntos donde se construye un `QDateEdit` en el
sistema (`oferta.py` ×2, `novedades.py` ×1 — cubre también el campo
opcional, que se arma sobre el mismo factory —, `reservas.py` ×7,
`llaves.py` ×1, `configuracion.py` ×1, `crud_generico.py` ×1) — mismo
criterio "mecanismo compartido, instalado explícitamente en cada
construcción" que `aplicar_color_sabado_negro` y `instalar_
seleccionar_todo_al_enfocar`, no una única instalación global. Un
`QDateEdit` nuevo que se agregue a futuro tiene que sumar este
llamado también, igual que esos otros dos mecanismos.

Sobre la validación que pidió la clienta de paso ("que no me permita
seleccionar una fecha muy para atrás... del período anterior"): no
hizo falta tocar nada ahí — ese tipo de guardarraíl (ej. período
cerrado en Reservas regulares) ya se valida al GUARDAR, no campo por
campo mientras se edita, así que sigue aplicando exactamente igual sin
importar si la fecha se tipeó, se eligió del calendario, o se llegó
con estas flechas nuevas.

Tests nuevos: `tests/test_gui_widget_fecha.py` (mecanismo compartido,
mismo criterio que `tests/test_gui_widget_foco.py` — la garantía es la
misma en todos los formularios porque es el mismo event filter): cruce
de fin de mes, cruce de fin de año, y el caso real con formato "ddd"
que antes se trababa retrocediendo.

## Cuadros de diálogo del sistema: botones "Sí"/"No" en vez de "Yes"/"No"

Pedido de la clienta, alcance general: "que se vea 'Si' y 'No' como
alternativas y no 'Yes' y 'No'" en los cuadros de diálogo del sistema
— calificado de "muy simple" al pedirlo. Investigado antes de
implementar: esos textos no son propios del sistema, son los botones
ESTÁNDAR de Qt (`QMessageBox.StandardButton.Yes`/`.No`, y también
Aceptar/Cancelar/Guardar en otros `QMessageBox` del sistema), que Qt
muestra en inglés por default salvo que se cargue su propia traducción
oficial al español — confirmado con un script de prueba contra un
`QMessageBox` real, cargando `qt_es.qm` (instalado junto con PySide6,
en `QLibraryInfo.path(TranslationsPath)`) sobre un `QTranslator`: los
botones Sí/No/Aceptar/Cancelar/Guardar pasan todos a español de una,
sin tocar ninguno de los más de cuarenta `QMessageBox.question`/
`.warning`/etc. del sistema uno por uno.

`instalar_traduccion_es(app)` (`gui_main.py`, nueva): instala ese
`QTranslator` sobre la `QApplication`, llamada una sola vez en
`main()` justo después de crearla — a diferencia de los mecanismos de
`app/gui/widgets/foco.py`/`fecha.py` (que necesitan un llamado
explícito por cada widget nuevo), esta es una instalación GLOBAL
única: ningún `QMessageBox` nuevo que se agregue a futuro necesita
sumar nada para heredar la traducción.

Test nuevo: `tests/test_gui_main.py`
(`test_instalar_traduccion_es_pone_si_no_en_los_botones_de_mensajebox`)
— mismo criterio que el test de "semana empieza en lunes" del mismo
archivo: no es testeable invocando `main()` en sí (abre una base real
y un diálogo de login), así que confirma la pieza real armando un
`QMessageBox` con botones Sí/No después de instalar la traducción.
