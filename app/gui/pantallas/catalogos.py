"""Pantallas de catálogo (Edificios, Unidades, Consultorios, Responsables,
Tipos de licencia, Listas editables, Condiciones y normas, Mensajes
predefinidos, Profesiones, Gastos operativos, Placas, Fechas especiales,
Esquema de descuentos) — todas construidas sobre PantallaCRUD, sin código
bespoke por tabla."""
from __future__ import annotations

import sqlite3

from app.gui.crud_generico import Campo, PantallaCRUD


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


def pantalla_edificios(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("Domicilio", "Domicilio"),
        Campo("DomicilioLocalidad", "Localidad"),
    ]
    return PantallaCRUD(conn, "Edificio", "Edificios", campos)


def pantalla_unidades(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=_opciones_edificio, requerido=True),
        Campo("Departamento", "Departamento", requerido=True),
        Campo("Cocina", "Cocina", tipo="booleano"),
        Campo("SalaDeEspera", "Sala de espera", tipo="booleano"),
        Campo("Banos", "Baños", tipo="booleano"),
        Campo("AreaGuardado", "Área de guardado", tipo="booleano"),
        Campo("AreaDescanso", "Área de descanso", tipo="booleano"),
        Campo("AreaFumadores", "Área de fumadores", tipo="booleano"),
        Campo("Recepcionista", "Recepcionista", tipo="booleano"),
        Campo("BalconComun", "Balcón común", tipo="booleano"),
        Campo("EntradaProfesionalExclusiva", "Entrada exclusiva", tipo="booleano"),
        Campo("WiFi", "WiFi", tipo="booleano"),
        Campo("CantLimitePlacas", "Límite de placas", tipo="numero"),
    ]
    return PantallaCRUD(conn, "Unidad", "Unidades", campos)


def pantalla_consultorios(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad, requerido=True),
        Campo("NumeroConsultorio", "Número", requerido=True),
        Campo("Largo", "Largo (m)", tipo="numero"),
        Campo("Ancho", "Ancho (m)", tipo="numero"),
        Campo("TamanoClasificacion", "Clasificación"),
        Campo("Ventana", "Ventana", tipo="booleano"),
        Campo("PanelVidrioLuzNatural", "Panel de vidrio / luz natural", tipo="booleano"),
        Campo("AireAcondicionado", "Aire acondicionado", tipo="booleano"),
        Campo("VentiladorTecho", "Ventilador de techo", tipo="booleano"),
        Campo("Sillones", "Sillones", tipo="booleano"),
        Campo("AptoCamilla", "Apto camilla", tipo="booleano"),
        Campo("Balcon", "Balcón", tipo="booleano"),
        Campo("ValorHoraRegularActual", "Valor hora regular actual", tipo="numero"),
        Campo("ValorHoraRegularAnterior", "Valor hora regular anterior", tipo="numero"),
        Campo("ValorHoraAisladaActual", "Valor hora aislada actual", tipo="numero"),
        Campo("ValorHoraAisladaAnterior", "Valor hora aislada anterior", tipo="numero"),
    ]
    return PantallaCRUD(conn, "Consultorio", "Consultorios", campos)


def pantalla_responsables(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("Celular", "Celular"),
        Campo("Email", "Email"),
        Campo("Rol", "Rol"),
        Campo("EsContactoPrincipal", "Contacto principal", tipo="booleano"),
        Campo("AptoPDF", "Apto para figurar en PDF", tipo="booleano"),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    return PantallaCRUD(conn, "Responsable", "Responsables", campos)


def pantalla_tipos_licencia(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("PorcentajeBonificacion", "% Bonificación", tipo="numero"),
        Campo("DuracionMaximaDias", "Duración máxima (días)", tipo="numero"),
        Campo("EsManual", "Carga manual", tipo="booleano"),
        Campo("Activo", "Activo", tipo="booleano"),
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


def pantalla_mensajes_predefinidos(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("Categoria", "Categoría"),
        Campo("Descripcion", "Descripción"),
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=_opciones_edificio),
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad),
        Campo("IdConsultorio", "Consultorio", tipo="combo", opciones=_opciones_consultorio),
        Campo("Mensaje", "Mensaje", tipo="texto_largo"),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    return PantallaCRUD(conn, "MensajePredefinido", "Mensajes predefinidos", campos)


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
        Campo("Periodo", "Período (AAAA-MM)", requerido=True),
        Campo("Categoria", "Categoría"),
        Campo("Concepto", "Concepto"),
        Campo("Monto", "Monto", tipo="numero", requerido=True),
        Campo("Alcance", "Alcance", tipo="combo", opciones=opciones_alcance),
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=_opciones_edificio),
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad),
        Campo("Origen", "Origen", tipo="combo", opciones=opciones_origen),
        Campo("Observacion", "Observación", tipo="texto_largo"),
    ]
    return PantallaCRUD(conn, "GastoOperativo", "Gastos operativos", campos)


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
        Campo("Fecha", "Fecha (AAAA-MM-DD)", requerido=True),
        Campo("Descripcion", "Descripción"),
        Campo("Tipo", "Tipo"),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    return PantallaCRUD(conn, "FechasEspeciales", "Fechas especiales", campos)


def pantalla_esquema_descuentos(conn: sqlite3.Connection) -> PantallaCRUD:
    campos = [
        Campo("HorasSemanalesDesde", "Horas semanales desde", tipo="numero", requerido=True),
        Campo("HorasSemanalesHasta", "Horas semanales hasta", tipo="numero", requerido=True),
        Campo("PorcentajeDescuento", "% Descuento", tipo="numero", requerido=True),
        Campo("FechaVigenciaDesde", "Vigencia desde (AAAA-MM-DD)"),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    return PantallaCRUD(conn, "EsquemaDescuentos", "Esquema de descuentos", campos)
