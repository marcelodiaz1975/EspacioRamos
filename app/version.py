"""Nombre y versión del PROGRAMA en sí — fuente única para el título de
ventana, los mensajes de arranque y el nombre del ejecutable empaquetado.

Distinto de `Configuracion.NombreEspacio` (el nombre del NEGOCIO, editable
desde la app, ej. "Espacio Ramos Consultorios" — puede ser cualquier
espacio que use este software): pedido explícito de la clienta, el
programa pasa a llamarse "SistemaDF" independientemente de qué espacio
lo esté usando, para no atar el nombre del software al de un cliente en
particular."""
NOMBRE_PROGRAMA = "SistemaDF"
VERSION = "v0.1"
NOMBRE_Y_VERSION = f"{NOMBRE_PROGRAMA} {VERSION}"
