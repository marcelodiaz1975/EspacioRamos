"""Recursos estáticos de la GUI (íconos, imágenes).

`RUTA_ICONO` es el ícono del programa (ver CLAUDE.md, "Pantalla de
carga al iniciar sesión") — generado una sola vez (cuadrado redondeado
en degradé de `COLOR_NIVEL_1`/`COLOR_NIVEL_1_OSCURO`, monograma "DF"
en blanco) porque el proyecto nunca había tenido ninguno asignado
hasta ahora. Se usa como ícono de la ventana/aplicación
(`QApplication.setWindowIcon`), como ícono del ejecutable empaquetado
(`sistemadf.spec`) y en la pantalla de carga que se muestra al
terminar de loguearse. Reemplazar este archivo (mismo nombre, mismo
lugar) alcanza para cambiarlo en los tres puntos a la vez, sin tocar
código.
"""
from pathlib import Path

RUTA_ICONO = Path(__file__).parent / "icono.png"
RUTA_ICONO_ICO = Path(__file__).parent / "icono.ico"
