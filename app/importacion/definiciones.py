"""Definición de qué entidades se cargan por planilla Excel (FA5) y con qué
columnas "legibles" (en vez de IDs internos) se le muestran al usuario.

Alcance de la Etapa 1: la carga inicial cubre la estructura física
(edificios, unidades, consultorios), los profesionales, sus reservas
regulares, las llaves, las placas de timbre y los responsables. El resto de
las entidades del modelo de datos (pagos, licencias, liquidaciones, etc.) se
cargan desde el sistema a medida que ocurren, no por importación masiva.

El orden de la lista importa: se importa en ese orden porque las entidades
más adelante en la lista referencian a las anteriores (ej. Unidad necesita
que su Edificio ya exista).
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
    ],
    "Profesional": [
        "CategoriaProfesional", "IdCodigo", "Apellido", "NombrePila", "Apodo",
        "Sexo", "DNI", "CUIT", "CondicionFiscal", "FechaNacimiento",
        "Domicilio", "DomicilioLocalidad", "TelefonoParticular", "Celular",
        "Email", "Profesion", "Tratamiento", "MatriculaNacional",
        "MatriculaProvincial",
    ],
    "ReservaRegular": [
        "Profesional", "Edificio", "Unidad", "Consultorio", "DiaSemana",
        "HoraInicio", "HoraFin", "VigenciaInicio", "VigenciaFin",
    ],
    "Llave": ["Descripcion", "Tipo", "ValorDepositoActual"],
    "Placa": ["Edificio", "Unidad", "PosicionTablero", "Profesional", "NombreGrabado"],
    "Responsable": ["Nombre", "Celular", "Email", "Rol", "EsContactoPrincipal", "AptoPDF"],
}

ENTIDADES_IMPORTABLES: list[str] = list(COLUMNAS_PLANTILLA.keys())

# Columnas booleanas: en la planilla se cargan como SI / NO.
CAMPOS_BOOLEANOS = {
    "Cocina", "SalaDeEspera", "AreaGuardado", "AreaDescanso", "AreaFumadores",
    "Recepcionista", "BalconComun", "EntradaProfesionalExclusiva", "WiFi",
    "Ventana", "PanelVidrioLuzNatural", "AireAcondicionado", "VentiladorTecho",
    "Sillones", "AptoCamilla", "Balcon", "EsContactoPrincipal", "AptoPDF",
}

# Columnas de referencia a otra entidad, agrupadas por entidad importada.
# Se usan en importar_excel.py para resolver el texto legible a un IdX.
COLUMNAS_REFERENCIA = {
    "Unidad": {"Edificio"},
    "Consultorio": {"Edificio", "Unidad"},
    "Profesional": {"Profesion"},
    "ReservaRegular": {"Profesional", "Edificio", "Unidad", "Consultorio"},
    "Placa": {"Edificio", "Unidad", "Profesional"},
}
