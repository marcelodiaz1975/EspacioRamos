-- ═══════════════════════════════════════════════════════════════════════
-- SISTEMA ESPACIO RAMOS — Esquema de base de datos (Etapa 1)
-- Basado en la sección 3 (Modelo de datos) de Sistema_Espacio_Ramos_v1.0.docx
--
-- Convención: identificadores en ASCII (sin tildes/ñ) para evitar problemas
-- de codificación al empaquetar con PyInstaller en Windows. Los campos
-- booleanos se guardan como INTEGER (0/1). Las fechas se guardan como TEXT
-- en formato ISO (AAAA-MM-DD).
-- ═══════════════════════════════════════════════════════════════════════

PRAGMA foreign_keys = ON;

-- 3.1 Edificio ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Edificio (
    IdEdificio INTEGER PRIMARY KEY AUTOINCREMENT,
    Nombre TEXT NOT NULL,
    Domicilio TEXT,
    DomicilioLocalidad TEXT
);

-- 3.2 Unidad ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Unidad (
    IdUnidad INTEGER PRIMARY KEY AUTOINCREMENT,
    IdEdificio INTEGER NOT NULL REFERENCES Edificio(IdEdificio),
    Departamento TEXT NOT NULL,
    Cocina INTEGER NOT NULL DEFAULT 0,
    SalaDeEspera INTEGER NOT NULL DEFAULT 0,
    Banos INTEGER NOT NULL DEFAULT 0,
    AreaGuardado INTEGER NOT NULL DEFAULT 0,
    AreaDescanso INTEGER NOT NULL DEFAULT 0,
    AreaFumadores INTEGER NOT NULL DEFAULT 0,
    Recepcionista INTEGER NOT NULL DEFAULT 0,
    BalconComun INTEGER NOT NULL DEFAULT 0,
    EntradaProfesionalExclusiva INTEGER NOT NULL DEFAULT 0,
    WiFi INTEGER NOT NULL DEFAULT 0,
    CantLimitePlacas INTEGER NOT NULL DEFAULT 0
);

-- 3.3 Consultorio -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS Consultorio (
    IdConsultorio INTEGER PRIMARY KEY AUTOINCREMENT,
    IdUnidad INTEGER NOT NULL REFERENCES Unidad(IdUnidad),
    NumeroConsultorio INTEGER NOT NULL,
    Largo REAL,
    Ancho REAL,
    TamanoClasificacion TEXT,
    Ventana INTEGER NOT NULL DEFAULT 0,
    PanelVidrioLuzNatural INTEGER NOT NULL DEFAULT 0,
    AireAcondicionado INTEGER NOT NULL DEFAULT 0,
    VentiladorTecho INTEGER NOT NULL DEFAULT 0,
    Sillones INTEGER NOT NULL DEFAULT 0,
    AptoCamilla INTEGER NOT NULL DEFAULT 0,
    Balcon INTEGER NOT NULL DEFAULT 0,
    ValorHoraRegularActual REAL NOT NULL DEFAULT 0,
    ValorHoraRegularAnterior REAL NOT NULL DEFAULT 0,
    ValorHoraAisladaActual REAL NOT NULL DEFAULT 0,
    ValorHoraAisladaAnterior REAL NOT NULL DEFAULT 0
);

-- 3.20 Profesion (antes de Profesional porque este la referencia) ----------
CREATE TABLE IF NOT EXISTS Profesion (
    IdProfesion INTEGER PRIMARY KEY AUTOINCREMENT,
    Nombre TEXT NOT NULL,
    NombreMasculino TEXT,
    NombreFemenino TEXT,
    NombreNeutro TEXT,
    TratamientoDefaultMasculino TEXT,
    TratamientoDefaultFemenino TEXT,
    TieneMultiplesTratamientos INTEGER NOT NULL DEFAULT 0,
    OpcionesTratamientoMasculino TEXT,
    OpcionesTratamientoFemenino TEXT
);

-- 3.4 Profesional -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Profesional (
    IdProfesional INTEGER PRIMARY KEY AUTOINCREMENT,
    CategoriaProfesional TEXT NOT NULL CHECK (CategoriaProfesional IN ('R','A','B','E','X','C')),
    IdCodigo TEXT,
    Apellido TEXT NOT NULL,
    NombreCompleto TEXT,
    NombrePila TEXT,
    Apodo TEXT,
    Sexo TEXT CHECK (Sexo IN ('Masculino','Femenino','No binario')),
    DNI TEXT,
    CUIT TEXT,
    CondicionFiscal TEXT,
    FechaNacimiento TEXT,
    Domicilio TEXT,
    DomicilioLocalidad TEXT,
    TelefonoParticular TEXT,
    Celular TEXT,
    Email TEXT,
    IdProfesion INTEGER REFERENCES Profesion(IdProfesion),
    Tratamiento TEXT,
    MatriculaNacional TEXT,
    MatriculaProvincial TEXT,
    FechaContacto TEXT,
    ProfesionalCabezaEquipo INTEGER REFERENCES Profesional(IdProfesional),
    SaldoCuentaActual REAL NOT NULL DEFAULT 0,
    SaldoCuentaAnterior REAL NOT NULL DEFAULT 0,
    -- DC-06 §5.2: si un pago imputado al mes anterior hace que el saldo
    -- vuelva a estar dentro de la tolerancia, el operador decide si se le
    -- restablece el descuento por horas semanales para ESA liquidación
    -- puntual (AAAA-MM) o si queda perdido igual. No aplica a otros meses.
    DescuentoSuspendidoPeriodo TEXT,
    PlazoPagoExtendido TEXT,
    MotivoPlazoExtra TEXT,
    DiaPlazoExtendidoAutomatico INTEGER CHECK (
        DiaPlazoExtendidoAutomatico IS NULL OR DiaPlazoExtendidoAutomatico BETWEEN 1 AND 31
    ),
    CampoLibre1 TEXT,
    CampoLibre2 TEXT,
    CampoLibre3 TEXT
);

-- 3.5 HistorialCodigo ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS HistorialCodigo (
    IdHistorialCodigo INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    CategoriaAnterior TEXT,
    CodigoAnterior TEXT,
    CategoriaNueva TEXT,
    CodigoNuevo TEXT,
    FechaCambio TEXT,
    Observacion TEXT
);

-- 3.6 HistorialPagos ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HistorialPagos (
    IdPago INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    Fecha TEXT,
    Monto REAL NOT NULL,
    MedioPago TEXT,
    CuentaReceptora TEXT,
    FechaHoraCarga TEXT,
    FechaTransferencia TEXT,
    HoraTransferencia TEXT,
    PeriodoImputado TEXT,
    FechaHoraAperturaBuzon TEXT,
    FechaHoraRecogidaSobres TEXT,
    EsAjuste INTEGER NOT NULL DEFAULT 0,
    Observacion TEXT
);

-- 3.7 Llave / LlaveAcceso / LlaveProfesional -----------------------------------
CREATE TABLE IF NOT EXISTS Llave (
    IdLlave INTEGER PRIMARY KEY AUTOINCREMENT,
    Descripcion TEXT,
    Tipo TEXT CHECK (Tipo IN ('Edificio','Unidad','No especificada')),
    ValorDepositoActual REAL NOT NULL DEFAULT 0,
    ValorDepositoAnterior REAL NOT NULL DEFAULT 0,
    Activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS LlaveAcceso (
    IdLlaveAcceso INTEGER PRIMARY KEY AUTOINCREMENT,
    IdLlave INTEGER NOT NULL REFERENCES Llave(IdLlave),
    IdEdificio INTEGER NOT NULL REFERENCES Edificio(IdEdificio),
    IdUnidad INTEGER REFERENCES Unidad(IdUnidad),
    DescripcionAcceso TEXT
);

CREATE TABLE IF NOT EXISTS LlaveProfesional (
    IdLlaveProfesional INTEGER PRIMARY KEY AUTOINCREMENT,
    IdLlave INTEGER NOT NULL REFERENCES Llave(IdLlave),
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    FechaEntrega TEXT,
    FechaDevolucion TEXT,
    DepositoCobrado INTEGER NOT NULL DEFAULT 0,
    MontoCobrado REAL,
    DepositoReintegrado INTEGER NOT NULL DEFAULT 0,
    MontoReintegrado REAL,
    Observacion TEXT
);

-- 3.8 Placa ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Placa (
    IdPlaca INTEGER PRIMARY KEY AUTOINCREMENT,
    IdUnidad INTEGER NOT NULL REFERENCES Unidad(IdUnidad),
    PosicionTablero INTEGER,
    IdProfesional INTEGER REFERENCES Profesional(IdProfesional),
    NombreGrabado TEXT,
    EsPersonalizada INTEGER NOT NULL DEFAULT 0,
    Activo INTEGER NOT NULL DEFAULT 1
);

-- 3.9 ReservaRegular --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ReservaRegular (
    IdReservaRegular INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    IdConsultorio INTEGER NOT NULL REFERENCES Consultorio(IdConsultorio),
    DiaSemana TEXT NOT NULL CHECK (DiaSemana IN ('Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo')),
    HoraInicio REAL NOT NULL,
    HoraFin REAL NOT NULL,
    VigenciaInicio TEXT NOT NULL,
    VigenciaFin TEXT,
    EsExcepcion INTEGER NOT NULL DEFAULT 0,
    Observacion TEXT
);

-- 3.10 ReservaAislada ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ReservaAislada (
    IdReservaAislada INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    IdConsultorio INTEGER NOT NULL REFERENCES Consultorio(IdConsultorio),
    Fecha TEXT NOT NULL,
    HoraInicio REAL NOT NULL,
    HoraFin REAL NOT NULL,
    Estado TEXT NOT NULL CHECK (Estado IN ('Confirmada','Cancelada')) DEFAULT 'Confirmada',
    AplicaRecargo INTEGER NOT NULL DEFAULT 0,
    EsReubicacion INTEGER NOT NULL DEFAULT 0,
    Observacion TEXT
);

-- 3.11 BloqueRigido -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS BloqueRigido (
    IdBloqueRigido INTEGER PRIMARY KEY AUTOINCREMENT,
    HoraInicio REAL NOT NULL,
    HoraFin REAL NOT NULL,
    DiasLogica TEXT,
    DiasVisualizacion TEXT,
    Activo INTEGER NOT NULL DEFAULT 1
);

-- 3.12 Vacacion -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Vacacion (
    IdVacacion INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    FechaDesde TEXT NOT NULL,
    FechaHasta TEXT NOT NULL,
    ValorSemanalAlMomentoDelRegistro REAL,
    ValorBonificado REAL,
    FraccionSemanaConsumida REAL,
    CupoConsumidoPorcentaje REAL,
    CupoRestantePorcentaje REAL
);

-- 3.13 TipoLicencia / Licencia ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS TipoLicencia (
    IdTipoLicencia INTEGER PRIMARY KEY AUTOINCREMENT,
    Nombre TEXT NOT NULL,
    PorcentajeBonificacion REAL NOT NULL DEFAULT 100,
    DuracionMaximaDias INTEGER,
    EsManual INTEGER NOT NULL DEFAULT 1,
    Activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS Licencia (
    IdLicencia INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    IdTipoLicencia INTEGER NOT NULL REFERENCES TipoLicencia(IdTipoLicencia),
    FechaDesde TEXT NOT NULL,
    FechaHasta TEXT NOT NULL,
    PorcentajeBonificacionAplicado REAL,
    ValorSemanalAlMomentoDelRegistro REAL,
    ValorBonificado REAL
);

-- 3.14 Ausencia -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Ausencia (
    IdAusencia INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    IdConsultorio INTEGER REFERENCES Consultorio(IdConsultorio),
    FechaDesde TEXT NOT NULL,
    FechaHasta TEXT NOT NULL,
    Motivo TEXT,
    Observacion TEXT
);

-- 3.15 CargoEspecial ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CargoEspecial (
    IdCargo INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    Tipo TEXT NOT NULL CHECK (Tipo IN ('Débito','Crédito')),
    Concepto TEXT NOT NULL,
    Monto REAL NOT NULL,
    PeriodoImputado TEXT,
    IdLlave INTEGER REFERENCES Llave(IdLlave),
    IdUnidad INTEGER REFERENCES Unidad(IdUnidad),
    Observacion TEXT
);

-- 3.16 LiquidacionEmitida ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS LiquidacionEmitida (
    IdLiquidacion INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    Periodo TEXT NOT NULL,
    FechaEmision TEXT,
    NombreArchivo TEXT,
    EsReemision INTEGER NOT NULL DEFAULT 0,
    EstadoEnvio TEXT NOT NULL CHECK (EstadoEnvio IN ('Enviada','No enviada','Regenerada no enviada')) DEFAULT 'No enviada',
    -- Monto que ESTA emisión aportó a SaldoCuentaActual (total sin el saldo
    -- anterior). Al reemitir se usa para calcular el delta contra la emisión
    -- previa sin pisar pagos ya registrados contra el mes en curso.
    MontoGenerado REAL NOT NULL DEFAULT 0
);

-- EstadoMensajeriaPeriodo (DC-02 sec. 2) ------------------------------------------------------
-- Trackea, por profesional y período, las dos transiciones de color del
-- Centro de mensajería que no se pueden derivar de otra tabla: marrón (mensaje
-- previo pendiente) -> amarillo (mensaje previo ya generado) para categoría R,
-- y celeste (mensaje aisladas pendiente) -> azul (ya generado) para categoría
-- A. Sin fila para (profesional, período) = arranque de mes (marrón/celeste
-- según corresponda). No se resetea con un paso explícito de avance de mes:
-- un período nuevo simplemente no tiene fila todavía.
CREATE TABLE IF NOT EXISTS EstadoMensajeriaPeriodo (
    IdEstadoMensajeria INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    Periodo TEXT NOT NULL,
    MensajePrevioGenerado INTEGER NOT NULL DEFAULT 0,
    MensajeAisladaGenerado INTEGER NOT NULL DEFAULT 0,
    UNIQUE (IdProfesional, Periodo)
);

-- FeriadoTrabajado (DC-01 sec. 1.5, DC-11 caso 2, aclarado en conversación) -----------------
-- Horas que un profesional trabajó en un feriado en lugar de tomarse el
-- descuento habitual. El consultorio es independiente del que usa en su
-- reserva regular (el operador lo asigna al coordinar). Se calcula en vivo
-- al armar la liquidación: horas x ValorHoraRegularActual del consultorio
-- asignado x (1 - descuento por horas semanales, igual que las horas
-- regulares) x (1 + recargo aisladas si aplica). Igual que las aisladas,
-- no se congela ningún valor acá.
-- FechaCarga: cuándo se cargó el registro (no la fecha del feriado). Sirve
-- para decidir si entra en la liquidación del mes del feriado (avisado
-- antes de emitirla) o se traslada a la del mes siguiente (avisado después).
CREATE TABLE IF NOT EXISTS FeriadoTrabajado (
    IdFeriadoTrabajado INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    IdConsultorio INTEGER NOT NULL REFERENCES Consultorio(IdConsultorio),
    Fecha TEXT NOT NULL,
    HoraInicio REAL NOT NULL,
    HoraFin REAL NOT NULL,
    AplicaRecargo INTEGER NOT NULL DEFAULT 0,
    FechaCarga TEXT NOT NULL,
    Observacion TEXT
);

-- AumentoAplicado (Etapa 5, DC-10 sec. 1) -----------------------------------------------
-- Registro de cada corrida del análisis de aumentos. Sirve para saber si
-- ya se aplicó un aumento en este mes calendario: si es la primera corrida
-- se congela ValorHoraXAnterior; si es una corrección dentro del mismo mes
-- se deja el "anterior" como estaba (el del proceso original).
CREATE TABLE IF NOT EXISTS AumentoAplicado (
    IdAumento INTEGER PRIMARY KEY AUTOINCREMENT,
    Periodo TEXT NOT NULL,
    PorcentajeGeneral REAL NOT NULL,
    FechaAplicacion TEXT,
    Observacion TEXT
);

-- 3.17 FechasEspeciales --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS FechasEspeciales (
    IdFecha INTEGER PRIMARY KEY AUTOINCREMENT,
    Fecha TEXT NOT NULL,
    Descripcion TEXT,
    Tipo TEXT,
    Activo INTEGER NOT NULL DEFAULT 1
);

-- 3.18 EsquemaDescuentos -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS EsquemaDescuentos (
    IdEsquemaDescuento INTEGER PRIMARY KEY AUTOINCREMENT,
    HorasSemanalesDesde REAL NOT NULL,
    HorasSemanalesHasta REAL NOT NULL,
    PorcentajeDescuento REAL NOT NULL,
    FechaVigenciaDesde TEXT,
    Activo INTEGER NOT NULL DEFAULT 1
);

-- 3.19 ListasEditables ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ListasEditables (
    IdOpcion INTEGER PRIMARY KEY AUTOINCREMENT,
    TipoLista TEXT NOT NULL,
    Valor TEXT NOT NULL,
    Activo INTEGER NOT NULL DEFAULT 1,
    Orden INTEGER NOT NULL DEFAULT 0
);

-- 3.21 ListaEspera --------------------------------------------------------------------------
-- Un pedido puede pedir varios bloques día(s)+horario a la vez (p. ej.
-- "martes o jueves de 14 a 18hs" Y/O "sábado de 9 a 12hs"): TipoCombinacion
-- acá arriba es la combinación ENTRE bloques (ListaEsperaBloque.IdPedido);
-- la combinación entre los días DENTRO de cada bloque vive en
-- ListaEsperaBloque.TipoCombinacionDias.
CREATE TABLE IF NOT EXISTS ListaEspera (
    IdPedido INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    FechaPedido TEXT NOT NULL,
    TipoCombinacion TEXT CHECK (TipoCombinacion IN ('O','Y')),
    CondicionesConsultorio TEXT,
    Detalle TEXT,
    Estado TEXT NOT NULL CHECK (Estado IN ('Activo','Resuelto','Descartado')) DEFAULT 'Activo',
    ObservacionCierre TEXT
);

CREATE TABLE IF NOT EXISTS ListaEsperaBloque (
    IdBloque INTEGER PRIMARY KEY AUTOINCREMENT,
    IdPedido INTEGER NOT NULL REFERENCES ListaEspera(IdPedido),
    TipoCombinacionDias TEXT CHECK (TipoCombinacionDias IN ('O','Y')),
    Dias TEXT,
    HorarioDesde REAL,
    HorarioHasta REAL,
    CantidadHorasRequeridas REAL
);

-- 3.22 Responsable --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Responsable (
    IdResponsable INTEGER PRIMARY KEY AUTOINCREMENT,
    Nombre TEXT NOT NULL,
    Celular TEXT,
    Email TEXT,
    Rol TEXT,
    EsContactoPrincipal INTEGER NOT NULL DEFAULT 0,
    AptoPDF INTEGER NOT NULL DEFAULT 0,
    Activo INTEGER NOT NULL DEFAULT 1
);

-- 3.23 PlanPago / CuotaPlan -----------------------------------------------------------------
-- DC-09 sec. 3: refinanciación con interés simple. Todas las cuotas tienen
-- el mismo importe (interés simple, no compuesto).
CREATE TABLE IF NOT EXISTS PlanPago (
    IdPlan INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    MontoRefinanciado REAL NOT NULL,
    PorcentajeInteresMensual REAL NOT NULL DEFAULT 0,
    MontoTotalAPagar REAL NOT NULL,
    CantidadCuotas INTEGER NOT NULL,
    ImportePorCuota REAL NOT NULL,
    MesAnoInicio TEXT NOT NULL,
    Estado TEXT NOT NULL CHECK (Estado IN ('Activo','Finalizado','Cancelado')) DEFAULT 'Activo',
    EsRefinanciacion INTEGER NOT NULL DEFAULT 0,
    IdPlanAnterior INTEGER REFERENCES PlanPago(IdPlan),
    Observacion TEXT
);

CREATE TABLE IF NOT EXISTS CuotaPlan (
    IdCuota INTEGER PRIMARY KEY AUTOINCREMENT,
    IdPlan INTEGER NOT NULL REFERENCES PlanPago(IdPlan),
    NumeroCuota INTEGER NOT NULL,
    PeriodoImputado TEXT,
    Monto REAL NOT NULL,
    Pagado INTEGER NOT NULL DEFAULT 0,
    Estado TEXT NOT NULL CHECK (Estado IN ('Pendiente','Pagada','Cerrada')) DEFAULT 'Pendiente'
);

-- 3.24 SnapshotMensual ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS SnapshotMensual (
    IdSnapshot INTEGER PRIMARY KEY AUTOINCREMENT,
    Periodo TEXT NOT NULL,
    FechaGeneracion TEXT NOT NULL,
    PorcentajeOcupacionGeneral REAL,
    PorOcupEdificio TEXT,
    PorOcupUnidad TEXT,
    PorOcupConsultorio TEXT,
    ValoresConsultorios TEXT,
    PorcentajeAumentoAplicado REAL
);

-- 3.25 GastoOperativo -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS GastoOperativo (
    IdGasto INTEGER PRIMARY KEY AUTOINCREMENT,
    Periodo TEXT NOT NULL,
    Categoria TEXT,
    Concepto TEXT,
    Monto REAL NOT NULL,
    Alcance TEXT CHECK (Alcance IN ('Espacio general','Edificio','Unidad')),
    IdEdificio INTEGER REFERENCES Edificio(IdEdificio),
    IdUnidad INTEGER REFERENCES Unidad(IdUnidad),
    Origen TEXT CHECK (Origen IN ('Manual','Importado')),
    Observacion TEXT
);

-- 3.26 Imagen -------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Imagen (
    IdImagen INTEGER PRIMARY KEY AUTOINCREMENT,
    Tipo TEXT,
    IdEdificio INTEGER REFERENCES Edificio(IdEdificio),
    IdUnidad INTEGER REFERENCES Unidad(IdUnidad),
    IdConsultorio INTEGER REFERENCES Consultorio(IdConsultorio),
    NumeroOrden INTEGER,
    Descripcion TEXT,
    RutaArchivo TEXT,
    Activo INTEGER NOT NULL DEFAULT 1
);

-- 3.27 MensajePredefinido -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS MensajePredefinido (
    IdMensaje INTEGER PRIMARY KEY AUTOINCREMENT,
    Categoria TEXT,
    Descripcion TEXT,
    IdEdificio INTEGER REFERENCES Edificio(IdEdificio),
    IdUnidad INTEGER REFERENCES Unidad(IdUnidad),
    IdConsultorio INTEGER REFERENCES Consultorio(IdConsultorio),
    Mensaje TEXT,
    Activo INTEGER NOT NULL DEFAULT 1
);

-- 3.29 CondicionNorma (Etapa 7, sección 4.5: los 21 puntos editables de "Condiciones y
-- normas" que aparecen en el PDF de Liquidación) --------------------------------------------
CREATE TABLE IF NOT EXISTS CondicionNorma (
    IdCondicion INTEGER PRIMARY KEY AUTOINCREMENT,
    Numero INTEGER NOT NULL,
    Titulo TEXT NOT NULL,
    Texto TEXT NOT NULL,
    Activo INTEGER NOT NULL DEFAULT 1
);

-- 3.30 DetalleComplementarioPropuesta (Etapa 7, sección 4.3: los ítems editables y
-- ordenables de "Detalles complementarios de la propuesta" del PDF de Propuesta al
-- profesional) ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DetalleComplementarioPropuesta (
    IdDetalleComplementario INTEGER PRIMARY KEY AUTOINCREMENT,
    Orden INTEGER NOT NULL,
    Titulo TEXT NOT NULL,
    Texto TEXT NOT NULL,
    Activo INTEGER NOT NULL DEFAULT 1
);

-- 3.31 HistorialOferta (Etapa 9: historial de búsquedas de Oferta de consultorios) -----------
-- Guarda los criterios completos de cada búsqueda armada (no una foto congelada del
-- resultado): al regenerar el PDF o el texto se vuelve a resolver contra la
-- disponibilidad vigente en ese momento, igual que si se armara de nuevo.
CREATE TABLE IF NOT EXISTS HistorialOferta (
    IdHistorialOferta INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProfesional INTEGER NOT NULL REFERENCES Profesional(IdProfesional),
    FechaGeneracion TEXT NOT NULL,
    CriteriosJSON TEXT NOT NULL
);

-- 3.28 Configuracion (tabla de una sola fila, IdConfiguracion siempre = 1) -------------------
CREATE TABLE IF NOT EXISTS Configuracion (
    IdConfiguracion INTEGER PRIMARY KEY CHECK (IdConfiguracion = 1),
    NombreEspacio TEXT,
    HoraInicioGrilla REAL NOT NULL DEFAULT 8,
    HoraFinGrilla REAL NOT NULL DEFAULT 22,
    DiasGrilla TEXT,
    FraccionGrilla INTEGER NOT NULL DEFAULT 30,
    UmbralGiroGrilla INTEGER NOT NULL DEFAULT 8,
    RecargoPorcentajeAisladas REAL NOT NULL DEFAULT 0,
    RecargoAisladasActivoPorDefecto INTEGER NOT NULL DEFAULT 0,
    FrecuenciaActualizacionValores TEXT,
    MesesPeriodoActualizacion TEXT,
    PorcentajeAjusteSaldoAtrasado REAL NOT NULL DEFAULT 3,
    ToleranciaDeudaDescuento REAL NOT NULL DEFAULT 0,
    PorcentajeDescuentoFeriado REAL NOT NULL DEFAULT 100,
    PorcentajeDescuentoNoLaborable REAL NOT NULL DEFAULT 100,
    SemanasVacacionesMaximasPorAnio INTEGER NOT NULL DEFAULT 2,
    DiasEnvioLiquidacionesRemanentes INTEGER NOT NULL DEFAULT 5,
    DiasAntesFinMesRecordatorioPlan INTEGER NOT NULL DEFAULT 5,
    DiasAntesFinMesRecordatorioGeneral INTEGER NOT NULL DEFAULT 3,
    RetencionHistorialListaEsperaAnios INTEGER NOT NULL DEFAULT 5,
    RangosEstadisticasOcupacion TEXT,
    ModulosExtendidos INTEGER NOT NULL DEFAULT 0,
    TamanoMaximoImagenMB REAL NOT NULL DEFAULT 5,
    FrecuenciaBackupDrive TEXT,
    ModoFechaFicticia INTEGER NOT NULL DEFAULT 0,
    FechaFicticia TEXT,
    MensajesPlural INTEGER NOT NULL DEFAULT 1,
    CantidadDecimales INTEGER NOT NULL DEFAULT 2,
    RutaLogo TEXT,
    CarpetaBaseArchivos TEXT,
    CarpetaBackup TEXT,
    ModoOscuro INTEGER NOT NULL DEFAULT 0
);
