"""Pantallas de catálogo (Localidades, Edificios, Unidades, Consultorios,
Responsables, Tipos de licencia, Listas editables, Condiciones y normas,
Profesiones, Gastos operativos, Placas, Fechas especiales) — todas
construidas sobre PantallaCRUD, sin código bespoke por tabla.
("Mensajes predefinidos" vive aparte, en mensajes_predefinidos.py — tiene
filtro y vista previa propios, sección 5.5. El esquema de descuentos NO
tiene pantalla de catálogo propia — se maneja y se visualiza únicamente
desde la solapa "Esquema de descuentos" de Aumentos y descuentos, ver
app/gui/pantallas/aumentos.py.)"""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QMessageBox

from app.gui.crud_generico import Campo, PantallaCRUD
from app.negocio.formato import formatear_moneda
from app.negocio.gastos_operativos import gasto_en_conflicto
from app.negocio.listas_editables import opciones_lista
from app.negocio.oferta_busqueda import TAMANOS_CONSULTORIO
from app.negocio.validaciones import (
    FORMATO_EMAIL,
    FORMATO_FECHA,
    FORMATO_PERIODO,
    es_email_valido,
    es_fecha_valida,
    es_periodo_valido,
)
from app.repositorio.registro import obtener_repositorio


def _opciones_tamano(conn: sqlite3.Connection) -> list[tuple[str | None, str]]:
    return [(None, "Sin clasificar")] + [(t, t) for t in TAMANOS_CONSULTORIO]


def _opciones_localidad(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    filas = conn.execute("SELECT IdLocalidad, Localidad FROM Localidad ORDER BY Localidad").fetchall()
    return [(None, "Sin localidad")] + [(f["IdLocalidad"], f["Localidad"]) for f in filas]


def _opciones_edificio(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdEdificio, Nombre FROM Edificio ORDER BY Nombre").fetchall()
    return [(f["IdEdificio"], f["Nombre"]) for f in filas]


def _opciones_unidad(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute(
        "SELECT u.IdUnidad, u.Departamento, e.Nombre AS Edificio FROM Unidad u "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio ORDER BY e.Nombre, u.Departamento"
    ).fetchall()
    return [(f["IdUnidad"], f"{f['Edificio']} — {f['Departamento']}") for f in filas]


def _opciones_consultorio(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute(
        "SELECT c.IdConsultorio, c.NumeroConsultorio, u.Departamento, e.Nombre AS Edificio "
        "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio ORDER BY e.Nombre, u.Departamento, c.NumeroConsultorio"
    ).fetchall()
    return [
        (f["IdConsultorio"], f"{f['Edificio']} — {f['Departamento']} — Consultorio {f['NumeroConsultorio']}")
        for f in filas
    ]


def pantalla_localidades(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("Localidad", "Localidad", requerido=True),
        Campo("Partido", "Partido"),
        Campo("Provincia", "Provincia"),
        Campo("Pais", "País"),
        Campo("CampoLibre1", "Campo libre 1"),
        Campo("CampoLibre2", "Campo libre 2"),
        Campo("CampoLibre3", "Campo libre 3"),
    ]
    return PantallaCRUD(conn, "Localidad", "Localidades", campos)


def pantalla_edificios(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("Domicilio", "Domicilio"),
        Campo("IdLocalidad", "Localidad", tipo="combo", opciones=_opciones_localidad),
        Campo("CampoLibre1", "Campo libre 1"),
        Campo("CampoLibre2", "Campo libre 2"),
        Campo("CampoLibre3", "Campo libre 3"),
    ]
    return PantallaCRUD(conn, "Edificio", "Edificios", campos)


def pantalla_unidades(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=_opciones_edificio, requerido=True),
        Campo("Departamento", "Departamento", requerido=True),
        Campo("Cocina", "Cocina", tipo="booleano"),
        Campo("SalaDeEspera", "Sala de espera", tipo="booleano"),
        # Cantidad, no Sí/No: una unidad puede tener más de un baño
        # (pedido puntual de la clienta al revisar este catálogo).
        Campo("Banos", "Cantidad de baños", tipo="numero"),
        Campo("AreaGuardado", "Área de guardado", tipo="booleano"),
        Campo("AreaDescanso", "Área de descanso", tipo="booleano"),
        Campo("AreaFumadores", "Área de fumadores", tipo="booleano"),
        Campo("Recepcionista", "Recepcionista", tipo="booleano"),
        Campo("BalconComun", "Balcón común", tipo="booleano"),
        Campo("EntradaProfesionalExclusiva", "Entrada exclusiva", tipo="booleano"),
        Campo("WiFi", "WiFi", tipo="booleano"),
        Campo("CantLimitePlacas", "Límite de placas", tipo="numero"),
        Campo("CampoLibre1", "Campo libre 1"),
        Campo("CampoLibre2", "Campo libre 2"),
        Campo("CampoLibre3", "Campo libre 3"),
    ]
    return PantallaCRUD(conn, "Unidad", "Unidades", campos)


def pantalla_consultorios(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad, requerido=True),
        Campo("NumeroConsultorio", "Número", tipo="numero", requerido=True),
        Campo("Largo", "Largo (m)", tipo="numero"),
        Campo("Ancho", "Ancho (m)", tipo="numero"),
        Campo("TamanoClasificacion", "Clasificación", tipo="combo", opciones=_opciones_tamano),
        Campo("Ventana", "Ventana", tipo="booleano"),
        Campo("Placard", "Placard", tipo="booleano"),
        Campo("AireAcondicionado", "Aire acondicionado", tipo="booleano"),
        Campo("VentiladorTecho", "Ventilador de techo", tipo="booleano"),
        Campo("Sillones", "Sillones", tipo="booleano"),
        Campo("AptoCamilla", "Apto camilla", tipo="booleano"),
        Campo("Balcon", "Balcón", tipo="booleano"),
        Campo("ValorHoraRegularActual", "Valor hora regular actual", tipo="numero"),
        Campo("ValorHoraRegularAnterior", "Valor hora regular anterior", tipo="numero"),
        Campo("ValorHoraAisladaActual", "Valor hora aislada actual", tipo="numero"),
        Campo("ValorHoraAisladaAnterior", "Valor hora aislada anterior", tipo="numero"),
        Campo("CampoLibre1", "Campo libre 1"),
        Campo("CampoLibre2", "Campo libre 2"),
        Campo("CampoLibre3", "Campo libre 3"),
    ]
    return PantallaCRUD(conn, "Consultorio", "Consultorios", campos)


def pantalla_responsables(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("Celular", "Celular"),
        Campo("Email", "Email", validador=es_email_valido, formato_esperado=FORMATO_EMAIL),
        Campo("Rol", "Rol", tipo="combo", opciones=opciones_lista("RolResponsable"), combo_editable=True),
        Campo("EsContactoPrincipal", "Contacto principal", tipo="booleano"),
        Campo("AptoPDF", "Apto para figurar en PDF", tipo="booleano"),
        Campo("Activo", "Activo", tipo="booleano"),
        Campo("CampoLibre1", "Campo libre 1"),
        Campo("CampoLibre2", "Campo libre 2"),
        Campo("CampoLibre3", "Campo libre 3"),
    ]
    return PantallaCRUD(conn, "Responsable", "Responsables", campos)


def pantalla_tipos_licencia(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("PorcentajeBonificacion", "% Bonificación", tipo="numero"),
        Campo("DuracionMaximaDias", "Duración máxima (días)", tipo="numero"),
        Campo("EsManual", "Carga manual", tipo="booleano"),
        Campo("Activo", "Activo", tipo="booleano"),
        Campo("CampoLibre1", "Campo libre 1"),
        Campo("CampoLibre2", "Campo libre 2"),
        Campo("CampoLibre3", "Campo libre 3"),
    ]
    return PantallaCRUD(conn, "TipoLicencia", "Tipos de licencia", campos)


def pantalla_listas_editables(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("TipoLista", "Tipo de lista", requerido=True),
        Campo("Valor", "Valor", requerido=True),
        Campo("Orden", "Orden", tipo="numero"),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    return PantallaCRUD(conn, "ListasEditables", "Listas editables", campos)


def pantalla_condiciones_normas(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("Numero", "N°", requerido=True),
        Campo("Titulo", "Título", requerido=True),
        Campo("Texto", "Texto", tipo="texto_largo", requerido=True),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    return PantallaCRUD(conn, "CondicionNorma", "Condiciones y normas", campos)


def pantalla_detalles_complementarios_propuesta(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("Orden", "Orden", tipo="numero", requerido=True),
        Campo("Titulo", "Título", requerido=True),
        Campo("Texto", "Texto", tipo="texto_largo", requerido=True),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    return PantallaCRUD(
        conn, "DetalleComplementarioPropuesta", "Detalles complementarios (Propuesta)", campos,
    )


def pantalla_profesiones(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("NombreMasculino", "Nombre (masculino)"),
        Campo("NombreFemenino", "Nombre (femenino)"),
        Campo("NombreNeutro", "Nombre (neutro)"),
        Campo("TratamientoDefaultMasculino", "Tratamiento por defecto (masculino)"),
        Campo("TratamientoDefaultFemenino", "Tratamiento por defecto (femenino)"),
        Campo("TieneMultiplesTratamientos", "Tiene múltiples tratamientos", tipo="booleano"),
        Campo("OpcionesTratamientoMasculino", "Opciones de tratamiento (masculino, separadas por coma)"),
        Campo("OpcionesTratamientoFemenino", "Opciones de tratamiento (femenino, separadas por coma)"),
    ]
    return PantallaCRUD(conn, "Profesion", "Profesiones", campos)


def pantalla_gastos_operativos(conn: sqlite3.Connection) -> PantallaCRUD:
    def opciones_alcance(c):
        return [("Espacio general", "Espacio general"), ("Edificio", "Edificio"), ("Unidad", "Unidad")]

    def opciones_origen(c):
        return [("Manual", "Manual"), ("Importado", "Importado")]

    campos = [
        Campo(
            "Periodo", "Período (AAAA-MM)", requerido=True,
            validador=es_periodo_valido, formato_esperado=FORMATO_PERIODO,
        ),
        Campo("Categoria", "Categoría"),
        Campo("Concepto", "Concepto"),
        Campo("Monto", "Monto", tipo="numero", requerido=True),
        Campo("Alcance", "Alcance", tipo="combo", opciones=opciones_alcance),
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=_opciones_edificio),
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad),
        Campo("Origen", "Origen", tipo="combo", opciones=opciones_origen),
        Campo("Observacion", "Observación", tipo="texto_largo"),
    ]
    pantalla = PantallaCRUD(conn, "GastoOperativo", "Gastos operativos", campos)
    pantalla.al_guardar = lambda valores, registro: _resolver_conflicto_gasto(pantalla, conn, valores, registro)
    return pantalla


def _resolver_conflicto_gasto(parent, conn: sqlite3.Connection, valores: dict, registro) -> dict | None:
    id_actual = registro["IdGasto"] if registro is not None else None
    conflicto = gasto_en_conflicto(
        conn, periodo=valores.get("Periodo"), concepto=valores.get("Concepto"),
        origen=valores.get("Origen"), id_gasto_actual=id_actual,
    )
    if conflicto is None:
        return valores
    respuesta = QMessageBox.question(
        parent, "Conflicto de origen",
        f"Ya existe un gasto operativo \"{conflicto['Concepto']}\" del período {conflicto['Periodo']} con "
        f"origen \"{conflicto['Origen']}\" ({formatear_moneda(conflicto['Monto'])}). No pueden convivir un origen Manual "
        f"y uno Importado para el mismo concepto y período.\n\n¿Reemplazarlo por este nuevo valor "
        f"(\"{valores.get('Origen')}\")?",
    )
    if respuesta != QMessageBox.StandardButton.Yes:
        return None
    obtener_repositorio(conn, "GastoOperativo").eliminar(conflicto["IdGasto"])
    return valores


def pantalla_placas(conn: sqlite3.Connection) -> PantallaCRUD:
    def opciones_profesional(c):
        filas = c.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido").fetchall()
        return [(f["IdProfesional"], f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", ")) for f in filas]

    campos = [
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad, requerido=True),
        Campo("PosicionTablero", "Posición en el tablero", tipo="numero"),
        Campo("IdProfesional", "Profesional", tipo="combo", opciones=opciones_profesional),
        Campo("NombreGrabado", "Nombre grabado"),
        Campo("EsPersonalizada", "Es personalizada", tipo="booleano"),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    return PantallaCRUD(conn, "Placa", "Placas", campos)


def pantalla_fechas_especiales(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo(
            "Fecha", "Fecha (AAAA-MM-DD)", requerido=True,
            validador=es_fecha_valida, formato_esperado=FORMATO_FECHA,
        ),
        Campo("Descripcion", "Descripción"),
        Campo("Tipo", "Tipo", tipo="combo", opciones=opciones_lista("TipoFechaEspecial")),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    return PantallaCRUD(conn, "FechasEspeciales", "Fechas especiales", campos)
