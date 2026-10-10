# Manual de instalación — SistemaDF (v0.1)

Esta guía cubre todo lo necesario para poner el sistema a funcionar por
primera vez: desde armar el ejecutable hasta dejarlo configurado y listo
para usar en la notebook de uso diario (y, opcionalmente, en una segunda
máquina de emergencia). Está pensada para seguirse paso a paso, en orden,
una sola vez por instalación.

No duplica el manual de uso del sistema — para eso, una vez adentro, está
la tecla **F1** en cualquier pantalla y el botón **"Manual del usuario"**
(dentro de "Archivos y listas" → "Gestor de archivos del espacio"), que
genera un PDF completo con la ayuda de todas las pantallas.

---

## 0. Qué vas a necesitar (resumen del entorno)

| Para qué | Qué hace falta |
|---|---|
| Armar el ejecutable (una sola vez) | Una máquina **Windows** con Python 3.11 o superior |
| Usar el sistema día a día | Solo la carpeta ya armada — **no hace falta instalar Python** ahí |
| Backup y recuperación ante emergencias | **Google Drive de escritorio** instalado y con una carpeta sincronizada |
| (Opcional) máquina de emergencia | Otra máquina Windows, con el mismo Google Drive sincronizado |

El sistema es una aplicación de escritorio para **Windows**, sin
servidor ni conexión a internet para funcionar (la única cosa que usa
internet es la sincronización de Google Drive, para el backup — y eso lo
hace el programa de Google, no el sistema).

---

## 1. Armar el ejecutable (una sola vez, por quien hace la entrega técnica)

Esto se hace **en una máquina Windows real** — el ejecutable que resulta
es específico de la plataforma en la que se compila, así que no sirve
armarlo en Linux o Mac y después copiarlo a Windows.

1. Instalar [Python 3.11 o superior](https://www.python.org/downloads/)
   en esa máquina (marcar la casilla "Add Python to PATH" durante la
   instalación).
2. Copiar la carpeta completa del proyecto a esa máquina (por ejemplo,
   descargando el repositorio como ZIP y descomprimiéndolo).
3. Abrir una terminal (PowerShell) parada en esa carpeta y ejecutar:

   ```powershell
   pip install -r requirements-build.txt
   pyinstaller sistemadf.spec
   ```

4. Esto genera la carpeta **`dist\SistemaDF\`** — esa carpeta **es**
   la instalación completa (el `.exe` más todo lo que necesita para
   funcionar). Es la que se copia a la máquina real de uso en el paso
   siguiente.

> Esta carpeta pesa varios cientos de MB (incluye Python, Qt y todas las
> librerías empaquetadas adentro) — es normal, no hace falta instalar
> nada más en la máquina de destino.

---

## 2. Preparar Google Drive **antes** del primer arranque

Esto es importante hacerlo antes del paso 4, porque en la configuración
inicial del sistema vas a necesitar la ruta de esta carpeta.

1. Instalar [Google Drive de escritorio](https://www.google.com/drive/download/)
   en la máquina donde va a vivir el sistema.
2. Iniciar sesión con la cuenta de Google de la clienta.
3. Elegir (o crear) una carpeta que quede sincronizada — por ejemplo
   "Espacio Ramos - Backups" dentro de "Mi unidad".
4. Anotar la ruta **local** de esa carpeta en esta máquina (algo como
   `C:\Users\<usuario>\Google Drive\Espacio Ramos - Backups`, o
   `G:\Mi unidad\Espacio Ramos - Backups` según cómo esté configurado
   Drive) — la vas a necesitar en el paso 5.
5. Confirmar que el ícono de Google Drive en la barra de tareas muestre
   "sincronizado" (nube o tilde verde), no "pendiente" (flechas
   girando) — recién ahí la carpeta está realmente lista para usarse.

---

## 3. Instalar en la máquina real

1. Copiar toda la carpeta `dist\SistemaDF\` (del paso 1) a un lugar
   fijo de esa máquina — por ejemplo `C:\SistemaDF`.
2. Adentro de esa carpeta está `SistemaDF.exe` — se puede crear un
   acceso directo a él en el Escritorio o anclarlo a la barra de tareas,
   para no tener que navegar hasta la carpeta cada vez.
3. No hace falta instalar Python, ni ninguna otra dependencia, en esta
   máquina — la carpeta ya trae todo adentro.

> **Primer arranque en Windows:** como el `.exe` no tiene firma digital,
> es posible que Windows muestre un aviso de SmartScreen ("Windows
> protegió su PC"). Hacer click en **"Más información"** y después en
> **"Ejecutar de todas formas"** — es un aviso normal para cualquier
> programa sin firmar, no significa que haya un problema real.

---

## 4. Primer arranque — alta del primer Administrador

1. Doble click en `SistemaDF.exe`.
2. Como todavía no hay ninguna base de datos en esta máquina, el
   sistema va a preguntar:

   > "No se encontró una base de datos en esta máquina. ¿Querés
   > restaurar el último backup desde una carpeta de Google Drive ya
   > sincronizada acá?"

   **La primera vez que se instala el sistema en general** (no hay
   ningún backup todavía en ningún lado) elegir **"No"** — se va a crear
   una base nueva, vacía.

   (Si en cambio estás instalando una **segunda máquina**, y ya generaste
   al menos un backup desde la primera — ver el paso 7 — ahí sí conviene
   elegir **"Sí"** y apuntar a la misma carpeta de Google Drive del paso
   2, para arrancar ya con todos los datos reales en vez de una base
   vacía.)

3. Se abre el alta del primer usuario **Administrador**. Pide:
   - **Usuario**: el nombre de quien va a ingresar (ej. el nombre de la
     clienta).
   - **Contraseña** y **Confirmar contraseña**: la contraseña de ese
     usuario.
   - **Contraseña maestra (recuperación)** y **Confirmar contraseña
     maestra**: una contraseña **distinta** de la anterior, que sirve
     como red de seguridad — es la única forma de recuperar el sistema
     si alguna vez se pierden los accesos de **todos** los
     Administradores a la vez. No se pide en el uso normal del
     sistema, solo en una emergencia de ese tipo.

   > ⚠️ **Guardar la contraseña maestra en un lugar seguro, fuera del
   > sistema** (un gestor de contraseñas, un papel guardado bajo llave,
   > etc.) — si se pierde junto con el resto de los accesos, no hay
   > ninguna forma de recuperarla desde adentro del programa.

4. Click en "Crear administrador" — con eso ya se puede ingresar al
   sistema.

---

## 5. Configuración inicial recomendada

Antes de empezar a cargar datos reales, conviene revisar estas pantallas
(todas dentro de la categoría **"Sistema"** del menú lateral):

### Configuración general

- **Solapa "General"**: nombre del espacio, logo (opcional), modo
  oscuro, etc.
- **Solapa "Archivos y backup"**:
  - **"Carpeta base de archivos generados"**: dónde el sistema guarda
    las fotos, documentos y PDFs que se van generando. Puede ser
    cualquier carpeta local — no necesita estar sincronizada con nada
    (a diferencia de la de backup).
  - **"Carpeta de backup (sincronizada con Google Drive)"**: pegar acá
    la ruta anotada en el paso 2.
  - **"Frecuencia de backup a Drive"**: cada cuánto se recuerda generar
    un backup (diario/semanal/quincenal/mensual) — es solo un
    recordatorio visual en Panel de control, no automático.
- **Solapa "Seguridad"**: minutos de inactividad para el bloqueo
  automático de pantalla.

### Usuarios y permisos

Si más de una persona va a usar el sistema (la clienta y su familia,
por ejemplo), dar de alta cada usuario acá, con el nivel que
corresponda (Administrador/Operador/Supervisor general).

### Base datos del espacio

Cargar la estructura real del negocio, en este orden (cada uno depende
del anterior): **Localidades → Edificios → Unidades → Consultorios →
Responsables**.

Esto se puede hacer a mano, pantalla por pantalla, o importando todo de
una desde una planilla Excel — ver el punto siguiente.

### Importar datos desde una planilla (opcional, más rápido para carga inicial)

Dentro de **Panel de control** → solapa **"Importación datos desde
Excel"**:

1. Botón **"Descargar planilla importación"** — genera un Excel con una
   hoja por cada tipo de dato (Localidades, Edificios, Unidades,
   Consultorios, Profesionales, Responsables, etc.) y una hoja de
   instrucciones.
2. Completar esa planilla con los datos reales del espacio.
3. Volver a esta pantalla, elegir el archivo con **"Elegir archivo"** y
   confirmar con **"Importar"**.

> Importante: el catálogo de **Llaves** (tipos de llave, a qué
> edificio/unidad abren, stock) y los **Bloques rígidos** no se cargan
> por esta vía — se configuran a mano desde sus propias pantallas
> ("Llaves y otros conceptos" y la solapa correspondiente de
> "Configuración general").

---

## 6. Primer backup

Una vez cargados los datos básicos (al menos un Edificio/Unidad/
Consultorio):

1. Ir a **Panel de control** → solapa **"Avance de período y backups"**.
2. Click en **"Generar backup ahora"**.
3. Confirmar que aparezca una carpeta nueva (con el formato
   `Backup AAAA-MM-DD HHhMM`) dentro de la carpeta de Google Drive del
   paso 2, y que Google Drive la termine de sincronizar (ícono
   "sincronizado").

---

## 7. (Opcional) Segunda máquina de emergencia

Si la idea es poder usar el sistema desde otra máquina en caso de
emergencia (ver más abajo cómo se comporta esto):

1. Repetir los pasos 1 a 3 en esa segunda máquina (mismo `.exe`
   armado, o una copia de la misma carpeta `dist\SistemaDF\`).
2. Instalar también ahí Google Drive de escritorio, con la **misma
   cuenta** y la **misma carpeta** sincronizada del paso 2.
3. Al abrir el sistema por primera vez en esa máquina, cuando pregunte
   si querés restaurar desde Google Drive, elegir **"Sí"** y apuntar a
   esa carpeta sincronizada — así arranca directo con los datos reales
   (el backup más reciente que haya generado la máquina principal),
   en vez de una base vacía.

**Cómo protege esto al sistema (ya implementado, no hace falta ninguna
acción extra de tu parte):** si alguna vez se usa esa segunda máquina
y, después, se vuelve a abrir la máquina principal sin haber
sincronizado los cambios, el sistema **detecta sola** que la base local
quedó desactualizada frente a un backup más nuevo y obliga a restaurarlo
antes de seguir — para que un error nunca termine con información vieja
pisando a la más nueva. Si en una emergencia hace falta seguir
trabajando sin poder sincronizar todavía, hay una vía de escape
protegida con la contraseña maestra ("Continuar sin sincronizar"), que
avisa en Panel de control con un cartel rojo permanente hasta que se
restaure la versión real.

---

## 8. Checklist final antes de dar por "en producción"

- [ ] Se armó el ejecutable en una máquina Windows real (no en Linux/Mac)
- [ ] Contraseña maestra guardada en un lugar seguro, **fuera** del
      sistema
- [ ] Google Drive de escritorio instalado, con sesión iniciada y la
      carpeta de backup realmente sincronizada (ícono en verde, no
      "pendiente")
- [ ] "Carpeta de backup" configurada en Configuración general, apuntando
      a esa carpeta
- [ ] Al menos un backup generado a mano y visible en la carpeta de
      Drive
- [ ] Estructura básica cargada: al menos una Localidad/Edificio/Unidad/
      Consultorio
- [ ] (Si corresponde) usuarios de la familia dados de alta en "Usuarios
      y permisos", con el nivel correcto
- [ ] (Si hay segunda máquina) probada con una restauración real desde
      la misma carpeta de Drive

---

## Problemas frecuentes

| Síntoma | Qué revisar |
|---|---|
| Windows muestra "Windows protegió su PC" al abrir el `.exe` | Normal para un programa sin firma digital — "Más información" → "Ejecutar de todas formas" |
| El sistema pide restaurar un backup apenas se abre, de la nada | Es correcto: detectó un backup más nuevo sincronizado desde otra máquina — conviene restaurarlo |
| No aparece la carpeta de backup nueva en Google Drive | Revisar que la ruta configurada en "Carpeta de backup" sea justo la carpeta sincronizada por Drive (no una copia local sin sincronizar) |
| "Esta instalación está en modo local, sin sincronizar" | Alguien eligió "Continuar sin sincronizar" en el cartel de base desactualizada — hay que restaurar un backup real para salir de ese modo (ver Panel de control) |
| Se olvidó la contraseña de un usuario | Un Administrador puede resetearla desde "Usuarios y permisos", sin necesitar la contraseña vieja |
| Se perdieron los accesos de **todos** los Administradores | Usar la contraseña maestra configurada en el alta inicial (paso 4) |
