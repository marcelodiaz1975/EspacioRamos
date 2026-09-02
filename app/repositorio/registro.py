"""Registro de las entidades del modelo de datos (sección 3 del documento)."""
from __future__ import annotations

import sqlite3

from app.repositorio.base import Repositorio

TABLAS = [
    "Edificio",
    "Unidad",
    "Consultorio",
    "Profesion",
    "Profesional",
    "HistorialCodigo",
    "HistorialPagos",
    "Llave",
    "LlaveAcceso",
    "LlaveMovimiento",
    "Placa",
    "ReservaRegular",
    "ReservaAislada",
    "BloqueRigido",
    "Vacacion",
    "TipoLicencia",
    "Licencia",
    "Ausencia",
    "CargoEspecial",
    "LiquidacionEmitida",
    "EstadoMensajeriaPeriodo",
    "FeriadoTrabajado",
    "AumentoAplicado",
    "FechasEspeciales",
    "EsquemaDescuentos",
    "ListasEditables",
    "ListaEspera",
    "ListaEsperaBloque",
    "Responsable",
    "PlanPago",
    "CuotaPlan",
    "RefinanciacionProgramada",
    "SnapshotMensual",
    "GastoOperativo",
    "Imagen",
    "MensajePredefinido",
    "Configuracion",
    "CondicionNorma",
    "DetalleComplementarioPropuesta",
    "HistorialOferta",
]


def obtener_repositorio(conn: sqlite3.Connection, entidad: str) -> Repositorio:
    if entidad not in TABLAS:
        raise ValueError(f"Entidad desconocida: {entidad}")
    return Repositorio(conn, entidad)
