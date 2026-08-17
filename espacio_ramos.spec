# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec para empaquetar el Sistema Espacio Ramos como
ejecutable de escritorio (Etapa 10, sección 2: "Empaquetado: PyInstaller
(.exe)"). Generar con:

    pyinstaller espacio_ramos.spec

El resultado queda en dist/EspacioRamos/ (modo "onedir": una carpeta con
el .exe y sus dependencias — más confiable con PySide6 que --onefile, que
además tendría que descomprimirse en una carpeta temporal en cada
arranque). Esa carpeta es la instalación completa: la base de datos y las
carpetas de archivos/backup se crean al lado del ejecutable (ver
app.db.connection._raiz_proyecto), así que copiar dist/EspacioRamos/ a
otra máquina alcanza para "instalar" — no hace falta un instalador aparte.

Único dato que no se detecta solo por análisis estático de imports:
app/db/schema.sql, que app.db.init_db lee desde disco en vez de traerlo
embebido en el código."""
from pathlib import Path

RAIZ = Path(SPECPATH)

a = Analysis(
    [str(RAIZ / "gui_main.py")],
    pathex=[str(RAIZ)],
    binaries=[],
    datas=[(str(RAIZ / "app" / "db" / "schema.sql"), "app/db")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EspacioRamos",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="EspacioRamos",
)
