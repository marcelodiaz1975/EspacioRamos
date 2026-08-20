# Sistema Espacio Ramos

Aplicación de escritorio para administrar el alquiler por horas de consultorios a profesionales de salud (Espacio Ramos Consultorios). Reemplaza la gestión manual de reservas, liquidaciones, llaves, lista de espera y comunicación con los profesionales por un sistema único con base de datos local.

- **Lenguaje:** Python 3.11+
- **Base de datos:** SQLite (un único archivo, sin servidor)
- **Interfaz:** PySide6 (Qt), aplicación de escritorio nativa
- **Documentos:** ReportLab (PDF), openpyxl (Excel), Pillow (imágenes)
- **Empaquetado:** PyInstaller — se distribuye como carpeta con `.exe`, sin instalador
- **Destino de instalación:** Windows (ver notas al final)

## Estructura del repositorio

```
app/
  db/            Schema SQL, conexión, semillas de datos por defecto
  repositorio/   CRUD genérico por tabla (introspección de columnas vía PRAGMA)
  negocio/       Reglas de negocio: reservas, liquidaciones, pagos, llaves,
                 lista de espera, mensajería, avance de mes, importación, etc.
  pdf/           Generación de todos los documentos PDF (liquidación, propuesta,
                 disponibilidad, oferta, grilla, placas, manual de usuario)
  importacion/   Importación masiva desde planilla Excel
  gui/           Interfaz PySide6 (ventana principal + una pantalla por sección)
docs/            Especificación original del sistema (Sistema_Espacio_Ramos_v1.0.docx)
referencia/      Scripts de referencia previos a la reescritura (no se ejecutan)
tests/           ~795 tests (pytest + pytest-qt), uno por módulo de app/
gui_main.py      Punto de entrada de la aplicación (interfaz gráfica)
main.py          CLI de administración (init-db / generar-plantillas / importar)
espacio_ramos.spec   Spec de PyInstaller para armar el .exe
```

## Requisitos

- Python 3.11 o superior
- En Windows, la app se instala como carpeta autocontenida (`dist/EspacioRamos/`)
  generada con PyInstaller — la máquina de un operador **no necesita tener Python
  instalado**, solo copiar esa carpeta.
- Para desarrollo sí hace falta Python + las dependencias de `requirements-dev.txt`.

## Puesta en marcha (desarrollo)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

En Linux/Mac el único cambio es la forma de activar el entorno virtual (`source .venv/bin/activate`).

### Correr la aplicación

```powershell
python gui_main.py
```

Sin argumentos usa `data\espacio_ramos.db` (se crea sola, junto con sus tablas y
valores por defecto, si no existe). Se le puede pasar una ruta de base de datos
distinta como único argumento:

```powershell
python gui_main.py C:\ruta\a\otra_base.db
```

Si no encuentra base de datos en esa ruta, ofrece restaurar el último backup desde
una carpeta de Google Drive ya sincronizada en la máquina (pensado para instalar
en una máquina nueva sin perder el historial).

### CLI de administración

`main.py` es una herramienta de línea de comandos aparte, útil para tareas puntuales
sin abrir la interfaz gráfica:

```powershell
python main.py init-db                          # crea la base de datos y las tablas
python main.py generar-plantillas                # genera la planilla Excel de carga inicial
python main.py importar ruta\a\planilla.xlsx      # importa datos desde esa planilla
```

Todos los subcomandos aceptan `--db ruta` para apuntar a una base distinta de la default.

### Tests

```powershell
pytest
```

795 tests unitarios + de integración de GUI (`pytest-qt`), sin dependencias externas
(cada test arma su propia base SQLite temporal). Correr `pyflakes app tests` antes de
commitear — el proyecto se mantiene con cero warnings.

### Armar el ejecutable (Windows)

```powershell
pip install -r requirements-build.txt
pyinstaller espacio_ramos.spec
```

El resultado queda en `dist/EspacioRamos/` (modo "onedir": una carpeta con el `.exe`
y sus dependencias). Esa carpeta **es** la instalación completa — la base de datos y
las carpetas de archivos/backup se crean al lado del ejecutable la primera vez que se
abre, así que copiar `dist/EspacioRamos/` a otra máquina Windows alcanza para instalar,
sin necesidad de un instalador aparte.

## Conceptos clave

- **Sesión única:** el sistema no permite dos instancias abiertas contra la misma base
  de datos al mismo tiempo (lock de archivo nativo del SO — `msvcrt` en Windows,
  `fcntl` en Linux/Mac).
- **Modo de fecha ficticia:** desde Configuración se puede fijar una fecha "de mentira"
  para probar escenarios de fin/inicio de mes sin esperar al calendario real. Cuando
  está activo se ve una barra de aviso en toda la aplicación.
- **Avance de mes:** el cierre mensual (traspaso de saldos, cierre de cuotas, limpieza
  de lista de espera, backup previo, regeneración de PDFs) se dispara a mano desde
  Panel de control — no hay ningún proceso en segundo plano ni tarea programada.
- **Backup:** copia la base de datos y la carpeta de archivos generados a una carpeta
  local que el operador sincroniza con Google Drive por fuera de la aplicación (el
  sistema no habla con la API de Drive).
- **Idioma del dominio:** nombres de tablas, campos y funciones de negocio están en
  español (`Profesional`, `ReservaAislada`, `avanzar_mes`, etc.) porque reflejan
  vocabulario real del negocio, no una convención de traducción.

## Notas sobre Windows

El entorno de destino final es Windows (el de desarrollo en esta sesión fue Linux).
Puntos ya cubiertos en el código pensando en eso:

- El lock de sesión única (`app/negocio/instancia_unica.py`) usa `msvcrt.locking` en
  Windows y `fcntl.flock` en Linux/Mac según `sys.platform`, sin depender de ninguna
  librería externa.
- Todas las rutas de archivo se arman con `pathlib.Path`, nunca concatenando `/` a mano.
- No hay llamados a `locale.setlocale` (los nombres de meses/días en español están
  hardcodeados en tablas propias) — evita el problema clásico de nombres de locale
  distintos entre Windows y Unix.
- `app/db/connection.py` detecta si está corriendo empaquetado (`sys.frozen`) y ubica
  la base de datos junto al `.exe` en vez de en la carpeta temporal de extracción de
  PyInstaller.

Lo que **no** se pudo verificar en este entorno por tratarse de Linux: la compilación
real del `.exe` con PyInstaller y el comportamiento de la interfaz gráfica corriendo
en Windows de verdad. Antes de la entrega conviene un primer armado y prueba manual
en una máquina Windows real.
