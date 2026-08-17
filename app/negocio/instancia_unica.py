"""Sesión única activa a la vez (sección 2, stack tecnológico): evita
abrir el sistema dos veces contra la misma base de datos al mismo tiempo,
para prevenir que una sesión pise cambios de la otra sin darse cuenta.

Usa un lock advisory sobre un archivo al lado de la base de datos, con la
API nativa del sistema operativo (`fcntl` en Linux/Mac, `msvcrt` en
Windows — no hace falta ninguna librería externa). El lock lo libera el
propio sistema operativo si el proceso se cierra o se cae, así que no
hace falta ninguna lógica de "detectar y limpiar un lock viejo" a mano."""
from __future__ import annotations

import sys
from pathlib import Path


class InstanciaYaAbierta(Exception):
    """Ya hay otra sesión abierta con esta misma base de datos."""


class BloqueoInstanciaUnica:
    def __init__(self, db_path: Path | str):
        db_path = Path(db_path)
        self.ruta_lock = db_path.with_name(db_path.name + ".lock")
        self._archivo = None

    def adquirir(self) -> None:
        self.ruta_lock.parent.mkdir(parents=True, exist_ok=True)
        archivo = open(self.ruta_lock, "a+")
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(archivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            archivo.close()
            raise InstanciaYaAbierta(
                f"Ya hay otra sesión de Espacio Ramos abierta con esta base de datos ({self.ruta_lock.stem})."
            )
        self._archivo = archivo

    def liberar(self) -> None:
        if self._archivo is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                self._archivo.seek(0)
                msvcrt.locking(self._archivo.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._archivo.fileno(), fcntl.LOCK_UN)
        finally:
            self._archivo.close()
            self._archivo = None

    def __enter__(self) -> "BloqueoInstanciaUnica":
        self.adquirir()
        return self

    def __exit__(self, *exc) -> None:
        self.liberar()
