"""Definición de qué entidades se cargan por planilla Excel (FA5) y con qué
columnas "legibles" (en vez de IDs internos) se le muestran al usuario.

Alcance de la Etapa 1: la carga inicial cubre la estructura física
(edificios, unidades, consultorios), los profesionales, sus reservas
regulares, las llaves, las placas de timbre, los feriados/fechas especiales
y los responsables. El resto de las entidades del modelo de datos (pagos,
licencias, liquidaciones, etc.) se cargan desde el sistema a medida que
ocurren, no por importación masiva.

El orden de la lista importa: se importa en ese orden porque las entidades
más adelante en la lista referencian a las anteriores (ej. Unidad necesita
que su Edificio ya exista). Dentro de la hoja Profesional, además, los R
deben cargarse antes que sus E: ProfesionalCabezaEquipo se resuelve fila a
fila contra lo ya importado, así que un E no encuentra a su R si viene
antes en la misma planilla.
"""

# Entidad -> columnas tal como se muestran en la planilla (nombres legibles).
# Las columnas que refieren a otra entidad (ej. "Edificio", "Profesional")
# se resuelven a su IdX correspondiente en importar_excel.py.
COLUMNAS_PLANTILLA: dict[str, list[str]] = {
    "Edificio": ["Nombre", "Domicilio", "DomicilioLocalidad"],
    "Unidad": [
        "Edificio", "Departamento", "Cocina", "SalaDeEspera", "Banos",
        "AreaGuardado", "AreaDescanso", "AreaFumadores", "Recepcionista",
        "BalconComun", "EntradaProfesionalExclusiva", "WiFi", "CantLimitePlacas",
    ],
    "Consultorio": [
        "Edificio", "Unidad", "NumeroConsultorio", "Largo", "Ancho",
        "TamanoClasificacion", "Ventana", "PanelVidrioLuzNatural",
        "AireAcondicionado", "VentiladorTecho", "Sillones", "AptoCamilla",
        "Balcon", "ValorHoraRegularActual", "ValorHoraAisladaActual",
    ],
    "Profesion": [
        "Nombre", "NombreMasculino", "NombreFemenino", "NombreNeutro",
        "TratamientoDefaultMasculino", "TratamientoDefaultFemenino",
        "TieneMultiplesTratamientos", "OpcionesTratamientoMasculino", "OpcionesTratamientoFemenino",
    ],
    "Profesional": [
        "CategoriaProfesional", "IdCodigo", "Apellido", "NombreCompleto", "NombrePila", "Apodo",
        "Sexo", "DNI", "CUIT", "CondicionFiscal", "FechaNacimiento",
        "Domicilio", "DomicilioLocalidad", "TelefonoParticular", "Celular",
        "Email", "Profesion", "Tratamiento", "MatriculaNacional",
        "MatriculaProvincial", "FechaContacto", "ProfesionalCabezaEquipo",
        "CampoLibre1", "CampoLibre2", "CampoLibre3",
    ],
    "ReservaRegular": [
        "Profesional", "Edificio", "Unidad", "Consultorio", "DiaSemana",
        "HoraInicio", "HoraFin", "VigenciaInicio", "VigenciaFin", "EsExcepcion", "Observacion",
    ],
    "Llave": ["Descripcion", "Tipo", "ValorDepositoActual"],
    "Placa": ["Edificio", "Unidad", "PosicionTablero", "Profesional", "NombreGrabado", "EsPersonalizada"],
    "FechasEspeciales": ["Fecha", "Descripcion", "Tipo"],
    "Responsable": ["Nombre", "Celular", "Email", "Rol", "EsContactoPrincipal", "AptoPDF"],
}

ENTIDADES_IMPORTABLES: list[str] = list(COLUMNAS_PLANTILLA.keys())

# Columnas booleanas: en la planilla se cargan como SI / NO.
CAMPOS_BOOLEANOS = {
    "Cocina", "SalaDeEspera", "AreaGuardado", "AreaDescanso", "AreaFumadores",
    "Recepcionista", "BalconComun", "EntradaProfesionalExclusiva", "WiFi",
    "Ventana", "PanelVidrioLuzNatural", "AireAcondicionado", "VentiladorTecho",
    "Sillones", "AptoCamilla", "Balcon", "EsContactoPrincipal", "AptoPDF",
    "TieneMultiplesTratamientos", "EsExcepcion", "EsPersonalizada",
}

# Columnas de fecha: en la planilla se cargan como DD/MM/AAAA (DC-11 caso 7),
# se convierten a ISO (AAAA-MM-DD) antes de guardar.
CAMPOS_FECHA = {
    "FechaNacimiento", "FechaContacto", "VigenciaInicio", "VigenciaFin", "Fecha",
}

# Columnas de referencia a otra entidad, agrupadas por entidad importada.
# Se usan en importar_excel.py para resolver el texto legible a un IdX.
COLUMNAS_REFERENCIA = {
    "Unidad": {"Edificio"},
    "Consultorio": {"Edificio", "Unidad"},
    "Profesional": {"Profesion", "ProfesionalCabezaEquipo"},
    "ReservaRegular": {"Profesional", "Edificio", "Unidad", "Consultorio"},
    "Placa": {"Edificio", "Unidad", "Profesional"},
}
