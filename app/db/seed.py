"""Carga de los valores por defecto del sistema (sección 8 del documento).

Cada función es idempotente: no duplica datos si ya se ejecutó antes (se
fija en si la tabla correspondiente ya tiene filas). Pensado para correrse
una vez, después de crear el esquema, en una base nueva.
"""
from __future__ import annotations

import json
import sqlite3

DIAS_LUNES_A_SABADO = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
DIAS_LUNES_A_VIERNES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

PROFESIONES = [
    # Nombre, NombreMasculino, NombreFemenino, TratamientoDefaultMasculino, TratamientoDefaultFemenino
    ("Psicología", "Psicólogo", "Psicóloga", "Lic.", "Lic."),
    ("Coaching", "Coach", "Coach", "Coach", "Coach"),
    ("Counseling", "Counselor", "Counselor", "Counselor", "Counselor"),
    ("Fonoaudiología", "Fonoaudiólogo", "Fonoaudióloga", "Fgo. o Lic.", "Fga. o Lic."),
    ("Medicina clínica", "Médico clínico", "Médica clínica", "Dr.", "Dra."),
    ("Nutrición", "Nutricionista", "Nutricionista", "Lic.", "Lic."),
    ("Profesorado", "Profesor", "Profesora", "Prof.", "Prof."),
    ("Psicopedagogía", "Psicopedagogo", "Psicopedagoga", "Psp. o Lic.", "Psp. o Lic."),
    ("Psiquiatría", "Psiquiatra", "Psiquiatra", "Dr.", "Dra."),
    ("Terapista hipnótico", "Terapista hipnótico", "Terapista hipnótica", "Tta.", "Tta."),
    ("Terapista holístico", "Terapista holístico", "Terapista holística", "Tta.", "Tta."),
    ("Terapista vibracional", "Terapista vibracional", "Terapista vibracional", "Tta.", "Tta."),
]

TIPOS_LICENCIA = [
    # Nombre, PorcentajeBonificacion, DuracionMaximaDias, EsManual
    ("Licencia médica", 100, None, 1),
    ("Licencia por duelo", 100, 5, 0),
    ("Licencia por matrimonio", 100, 14, 0),
    ("Licencia por maternidad", 50, 90, 0),
    ("Licencia por motivos personales", 100, None, 1),
]

LISTAS_EDITABLES = {
    "CondicionFiscal": ["Responsable Inscripto", "Monotributo", "Consumidor Final", "Exento"],
    "MedioPago": ["Sobre en buzón", "Dinero en mano", "Transferencia a cta Celeste", "Transferencia a cta Marcelo"],
    "CuentaReceptora": ["CA Banco Macro - Celeste", "CA Banco Hipotecario - Marcelo", "CA Banco Patagonia - Marcelo"],
    "TipoFechaEspecial": ["Feriado nacional", "Día no laborable", "Paro general", "Paro de transporte",
                          "Asueto extraordinario", "Puente turístico"],
    "RolResponsable": ["Administrador principal", "Administrador", "Administrativo", "Mantenimiento general",
                       "Mantenimiento limpieza", "Mantenimiento y administrativo"],
    "TipoLlave": ["Unidad", "Edificio", "No especificada"],
    "MotivoAusencia": ["Motivos personales", "Vacaciones fuera de cupo"],
}


def _tabla_vacia(conn: sqlite3.Connection, tabla: str) -> bool:
    return conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0] == 0


def sembrar_bloques_rigidos(conn: sqlite3.Connection) -> None:
    if not _tabla_vacia(conn, "BloqueRigido"):
        return
    conn.execute(
        "INSERT INTO BloqueRigido (HoraInicio, HoraFin, DiasLogica, DiasVisualizacion, Activo) "
        "VALUES (9, 11, ?, ?, 1)",
        (json.dumps(DIAS_LUNES_A_SABADO), json.dumps(DIAS_LUNES_A_SABADO)),
    )
    conn.execute(
        "INSERT INTO BloqueRigido (HoraInicio, HoraFin, DiasLogica, DiasVisualizacion, Activo) "
        "VALUES (18, 21, ?, ?, 1)",
        (json.dumps(DIAS_LUNES_A_VIERNES), json.dumps(DIAS_LUNES_A_SABADO)),
    )
    conn.commit()


def sembrar_configuracion(conn: sqlite3.Connection) -> None:
    if not _tabla_vacia(conn, "Configuracion"):
        return
    conn.execute(
        "INSERT INTO Configuracion (IdConfiguracion, HoraInicioGrilla, HoraFinGrilla, DiasGrilla, "
        "FraccionGrilla, UmbralGiroGrilla, RecargoPorcentajeAisladas, RecargoAisladasActivoPorDefecto, "
        "PorcentajeAjusteSaldoAtrasado, SemanasVacacionesMaximasPorAnio, DiasEnvioLiquidacionesRemanentes, "
        "DiasAntesFinMesRecordatorioPlan, DiasAntesFinMesRecordatorioGeneral, "
        "RetencionHistorialListaEsperaAnios, ModulosExtendidos, TamanoMaximoImagenMB, "
        "ModoFechaFicticia, MensajesPlural) "
        "VALUES (1, 8, 22, ?, 30, 8, 10, 0, 3, 2, 5, 5, 3, 5, 0, 5, 0, 1)",
        (json.dumps(DIAS_LUNES_A_SABADO),),
    )
    conn.commit()


def sembrar_profesiones(conn: sqlite3.Connection) -> None:
    if not _tabla_vacia(conn, "Profesion"):
        return
    conn.executemany(
        "INSERT INTO Profesion (Nombre, NombreMasculino, NombreFemenino, "
        "TratamientoDefaultMasculino, TratamientoDefaultFemenino) VALUES (?, ?, ?, ?, ?)",
        PROFESIONES,
    )
    conn.commit()


def sembrar_tipos_licencia(conn: sqlite3.Connection) -> None:
    if not _tabla_vacia(conn, "TipoLicencia"):
        return
    conn.executemany(
        "INSERT INTO TipoLicencia (Nombre, PorcentajeBonificacion, DuracionMaximaDias, EsManual, Activo) "
        "VALUES (?, ?, ?, ?, 1)",
        TIPOS_LICENCIA,
    )
    conn.commit()


def sembrar_esquema_descuentos(conn: sqlite3.Connection) -> None:
    """Default: 1% cada 2hs semanales, tope 25%."""
    if not _tabla_vacia(conn, "EsquemaDescuentos"):
        return
    tramos = []
    horas = 2
    while horas <= 52:
        porcentaje = min(horas // 2, 25)
        tramos.append((horas - 2, horas, porcentaje))
        horas += 2
    conn.executemany(
        "INSERT INTO EsquemaDescuentos (HorasSemanalesDesde, HorasSemanalesHasta, PorcentajeDescuento, Activo) "
        "VALUES (?, ?, ?, 1)",
        tramos,
    )
    conn.commit()


def sembrar_listas_editables(conn: sqlite3.Connection) -> None:
    if not _tabla_vacia(conn, "ListasEditables"):
        return
    filas = []
    for tipo_lista, valores in LISTAS_EDITABLES.items():
        for orden, valor in enumerate(valores):
            filas.append((tipo_lista, valor, orden))
    conn.executemany(
        "INSERT INTO ListasEditables (TipoLista, Valor, Activo, Orden) VALUES (?, ?, 1, ?)",
        filas,
    )
    conn.commit()


def sembrar_valores_por_defecto(conn: sqlite3.Connection) -> None:
    sembrar_bloques_rigidos(conn)
    sembrar_configuracion(conn)
    sembrar_profesiones(conn)
    sembrar_tipos_licencia(conn)
    sembrar_esquema_descuentos(conn)
    sembrar_listas_editables(conn)
