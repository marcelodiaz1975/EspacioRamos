"""Pantalla de Profesionales (F06/F07, sección 3.4) sobre PantallaCRUD."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QMessageBox

from app.gui.crud_generico import Campo, PantallaCRUD
from app.negocio.archivos_generados import aplicar_cambio_codigo
from app.negocio.dias import fecha_actual

_CATEGORIAS = [
    ("R", "R - Regular"),
    ("A", "A - Reserva aislada"),
    ("B", "B - Bonificado"),
    ("E", "E - Equipo (consolida en su cabeza de equipo)"),
    ("X", "X - Inactivo"),
    ("C", "C - Contacto / prospecto"),
]
_SEXOS = [("Masculino", "Masculino"), ("Femenino", "Femenino"), ("No binario", "No binario")]


def _opciones_categoria(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return _CATEGORIAS


def _opciones_sexo(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return _SEXOS


def _opciones_profesion(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdProfesion, Nombre FROM Profesion ORDER BY Nombre").fetchall()
    return [(f["IdProfesion"], f["Nombre"]) for f in filas]


def _opciones_profesional(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido").fetchall()
    return [(f["IdProfesional"], f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", ")) for f in filas]


def _al_actualizar_profesional(conn: sqlite3.Connection, registro_anterior: sqlite3.Row, valores_nuevos: dict) -> None:
    try:
        aplicar_cambio_codigo(conn, registro_anterior, valores_nuevos, fecha_actual(conn))
    except OSError as error:
        QMessageBox.warning(
            None, "Cambio de código",
            f"Se registró el cambio de código, pero no se pudo renombrar la carpeta en disco: {error}",
        )


def pantalla_profesionales(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("CategoriaProfesional", "Categoría", tipo="combo", opciones=_opciones_categoria, requerido=True),
        Campo("Apellido", "Apellido", requerido=True),
        Campo("NombrePila", "Nombre"),
        Campo("Apodo", "Apodo"),
        Campo("Tratamiento", "Tratamiento"),
        Campo("Sexo", "Sexo", tipo="combo", opciones=_opciones_sexo),
        Campo("IdCodigo", "Código"),
        Campo("DNI", "DNI"),
        Campo("CUIT", "CUIT"),
        Campo("CondicionFiscal", "Condición fiscal"),
        Campo("FechaNacimiento", "Fecha de nacimiento (AAAA-MM-DD)"),
        Campo("Domicilio", "Domicilio"),
        Campo("DomicilioLocalidad", "Localidad"),
        Campo("TelefonoParticular", "Teléfono particular"),
        Campo("Celular", "Celular"),
        Campo("Email", "Email"),
        Campo("IdProfesion", "Profesión", tipo="combo", opciones=_opciones_profesion),
        Campo("MatriculaNacional", "Matrícula nacional"),
        Campo("MatriculaProvincial", "Matrícula provincial"),
        Campo("FechaContacto", "Fecha de contacto (AAAA-MM-DD)"),
        Campo("ProfesionalCabezaEquipo", "Cabeza de equipo", tipo="combo", opciones=_opciones_profesional),
        Campo("SaldoCuentaActual", "Saldo cuenta actual", tipo="numero"),
        Campo("SaldoCuentaAnterior", "Saldo cuenta anterior", tipo="numero"),
        Campo("PlazoPagoExtendido", "Plazo de pago extendido"),
        Campo("MotivoPlazoExtra", "Motivo del plazo extra"),
        Campo("CampoLibre1", "Campo libre 1"),
        Campo("CampoLibre2", "Campo libre 2"),
        Campo("CampoLibre3", "Campo libre 3"),
    ]
    return PantallaCRUD(
        conn, "Profesional", "Profesionales", campos,
        al_actualizar=lambda anterior, valores: _al_actualizar_profesional(conn, anterior, valores),
    )
