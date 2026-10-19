"""Definición de qué entidades se cargan por planilla Excel (FA5) y con qué
columnas "legibles" (en vez de IDs internos) se le muestran al usuario.

Alcance de la Etapa 1: la carga inicial cubre la estructura física
(edificios, unidades, consultorios), los profesionales, sus reservas
regulares, las llaves, las placas de timbre, los feriados/fechas especiales
y los responsables. El resto de las entidades del modelo de datos (pagos,
licencias, liquidaciones, etc.) se cargan desde el sistema a medida que
ocurren, no por importación masiva.

Excepción: PlanPago sí se puede importar, específicamente para dar de alta
de una sola vez los planes de pago que un profesional ya tenía acordados y
en curso antes de empezar a usar el sistema (no tendría sentido pedirle al
operador que los recree mes a mes a mano). Las cuotas de meses ya
transcurridos a la fecha de la importación se marcan solas como pagadas
(ver importar_excel._crear_plan_pago_importado) para que el estado de
cuenta no las muestre como pendientes.

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
    "Localidad": ["Localidad", "Partido", "Provincia", "Pais", "CampoLibre1", "CampoLibre2", "CampoLibre3"],
    "Edificio": ["Nombre", "Domicilio", "Localidad", "CampoLibre1", "CampoLibre2", "CampoLibre3"],
    "Unidad": [
        "Edificio", "Departamento", "Cocina", "SalaDeEspera", "Banos",
        "AreaGuardado", "AreaDescanso", "AreaFumadores", "Recepcionista",
        "BalconComun", "EntradaProfesionalExclusiva", "WiFi", "CantLimitePlacas",
        "CampoLibre1", "CampoLibre2", "CampoLibre3",
    ],
    "Consultorio": [
        "Edificio", "Unidad", "NumeroConsultorio", "Largo", "Ancho",
        "LargoEscritorio", "AnchoEscritorio",
        "TamanoClasificacion", "Ventana", "Placard",
        "AireAcondicionado", "VentiladorTecho", "Sillones", "AptoCamilla",
        "Balcon", "ValorHoraRegularActual", "ValorHoraAisladaActual",
        "CampoLibre1", "CampoLibre2", "CampoLibre3",
    ],
    "Profesion": [
        "Nombre", "NombreMasculino", "NombreFemenino", "NombreNeutro",
        "TratamientoDefaultMasculino", "TratamientoDefaultFemenino",
        "TieneMultiplesTratamientos", "OpcionesTratamientoMasculino", "OpcionesTratamientoFemenino",
        "DiaProfesion",
        "CampoLibre1", "CampoLibre2", "CampoLibre3",
    ],
    "Profesional": [
        "CategoriaProfesional", "IdCodigo", "Apellido", "NombreCompleto", "NombrePila", "Apodo",
        "Sexo", "DNI", "CUIT", "CondicionFiscal", "FechaNacimiento",
        "Domicilio", "DomicilioLocalidad", "TelefonoParticular", "Celular",
        "Email", "Profesion", "Tratamiento", "MatriculaNacional",
        "MatriculaProvincial", "FechaContacto", "SaldoCuentaAnterior", "ProfesionalCabezaEquipo",
        "CampoLibre1", "CampoLibre2", "CampoLibre3",
    ],
    "ReservaRegular": [
        "Profesional", "Edificio", "Unidad", "Consultorio", "DiaSemana",
        "HoraInicio", "HoraFin", "VigenciaInicio", "VigenciaFin", "EsExcepcion", "Observacion",
    ],
    # Llaves: tres hojas separadas (pedido explícito de la clienta, segunda
    # vuelta sobre esto — reemplaza el diseño de una sola hoja "Llave" con
    # columnas opcionales de acceso/tenencia, que mezclaba en una misma
    # fila tres conceptos de tablas distintas), una por cada tabla real del
    # modelo (Llave/LlaveAcceso/LlaveMovimiento), en el orden en que hay
    # que cargarlas: primero los TIPOS de llave que maneja, después a qué
    # ACCEDE cada uno, por último qué profesional tiene cuál en su poder.
    #
    # El Nombre de un Tipo de llave lo arma el sistema solo (correlativo,
    # "Tipo llave E1"...) — no hay forma de saberlo de antemano al escribir
    # la planilla, así que "Codigo" (hoja Llave) es un identificador
    # PURAMENTE DE PLANILLA, inventado por la clienta (cualquier texto
    # corto, ej. "LL-01"), que "CodigoLlave" (hojas LlaveAcceso/
    # LlaveMovimiento) repite para decir a qué Tipo de llave de la primera
    # hoja se refiere cada fila — nunca se guarda en la base, solo sirve
    # para que `importar_excel.py` una las tres hojas entre sí durante la
    # importación (ver `_resolver_referencias`/`mapa_codigo_llave`).
    #
    # La hoja "Llave" ingresa sola 1000 copias de stock a cada Tipo que
    # crea (ver `importar_excel._STOCK_INICIAL_IMPORTACION`) para que la
    # hoja "LlaveMovimiento" nunca falle por falta de stock disponible al
    # asignar — pedido explícito: "la clienta ajusta el stock real a mano
    # después, con Ingreso/Pérdida desde la pantalla de Llaves".
    # Sin los tres CampoLibre de siempre: a diferencia de los catálogos
    # genéricos (`PantallaCRUD`), Llave no pasa por ahí (armada a mano,
    # "Llaves (formato solapa a mano, no PantallaCRUD)") y la tabla nunca
    # llegó a sumarlos -- no hay columna a la que mapearlos.
    "Llave": ["Codigo", "Tipo", "ValorDepositoActual", "Observacion"],
    "LlaveAcceso": ["CodigoLlave", "Edificio", "Unidad", "Nombre", "Observacion"],
    "LlaveMovimiento": ["CodigoLlave", "Profesional", "DepositoAbonado"],
    "Placa": ["Edificio", "Unidad", "PosicionTablero", "Profesional", "NombreGrabado", "EsPersonalizada"],
    "FechasEspeciales": ["Fecha", "Descripcion", "Tipo", "CampoLibre1", "CampoLibre2", "CampoLibre3"],
    "Responsable": [
        "Nombre", "Celular", "Email", "Rol", "EsContactoPrincipal", "AptoPDF",
        "CampoLibre1", "CampoLibre2", "CampoLibre3",
    ],
    "PlanPago": [
        "Profesional", "MesAnoInicio", "MontoRefinanciado",
        "PorcentajeInteresMensual", "CantidadCuotas", "Observacion",
    ],
}

ENTIDADES_IMPORTABLES: list[str] = list(COLUMNAS_PLANTILLA.keys())

# Columnas booleanas: en la planilla se cargan como SI / NO.
CAMPOS_BOOLEANOS = {
    "Cocina", "SalaDeEspera", "AreaGuardado", "AreaDescanso", "AreaFumadores",
    "Recepcionista", "BalconComun", "EntradaProfesionalExclusiva", "WiFi",
    "Ventana", "Placard", "AireAcondicionado", "VentiladorTecho",
    "Sillones", "AptoCamilla", "Balcon", "EsContactoPrincipal", "AptoPDF",
    "TieneMultiplesTratamientos", "EsExcepcion", "EsPersonalizada", "DepositoAbonado",
}

# Columnas de fecha: en la planilla se cargan como DD/MM/AAAA (DC-11 caso 7),
# se convierten a ISO (AAAA-MM-DD) antes de guardar.
CAMPOS_FECHA = {
    "FechaNacimiento", "FechaContacto", "VigenciaInicio", "VigenciaFin", "Fecha",
}

# Columnas de período (mes+año, sin día): en la planilla se cargan como
# MM/AAAA, se convierten a AAAA-MM antes de guardar.
CAMPOS_PERIODO = {"MesAnoInicio"}

# Columnas de referencia a otra entidad, agrupadas por entidad importada.
# Se usan en importar_excel.py para resolver el texto legible a un IdX.
COLUMNAS_REFERENCIA = {
    "Edificio": {"Localidad"},
    "Unidad": {"Edificio"},
    "Consultorio": {"Edificio", "Unidad"},
    "Profesional": {"Profesion", "ProfesionalCabezaEquipo"},
    "ReservaRegular": {"Profesional", "Edificio", "Unidad", "Consultorio"},
    "Placa": {"Edificio", "Unidad", "Profesional"},
    "PlanPago": {"Profesional"},
    # "Llave" (tipos) ya no tiene ninguna referencia que resolver -- "Codigo"
    # es planilla-only, se extrae directo en importar_excel.importar_hoja,
    # no acá (no hace falta buscarlo contra la base, es un identificador
    # que la clienta inventa, no uno que ya exista en ningún lado).
    "LlaveAcceso": {"CodigoLlave", "Edificio", "Unidad"},
    "LlaveMovimiento": {"CodigoLlave", "Profesional"},
}
