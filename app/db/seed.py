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
    # Nombre, NombreMasculino, NombreFemenino, TratDefaultM, TratDefaultF,
    # TieneMultiplesTratamientos, OpcionesTratamientoMasculino, OpcionesTratamientoFemenino
    ("Psicología", "Psicólogo", "Psicóloga", "Lic.", "Lic.", 0, None, None),
    ("Coaching", "Coach", "Coach", "Coach", "Coach", 0, None, None),
    ("Counseling", "Counselor", "Counselor", "Counselor", "Counselor", 0, None, None),
    ("Fonoaudiología", "Fonoaudiólogo", "Fonoaudióloga", "Fgo. o Lic.", "Fga. o Lic.", 1, "Fgo.,Lic.", "Fga.,Lic."),
    ("Medicina clínica", "Médico clínico", "Médica clínica", "Dr.", "Dra.", 0, None, None),
    ("Nutrición", "Nutricionista", "Nutricionista", "Lic.", "Lic.", 0, None, None),
    ("Profesorado", "Profesor", "Profesora", "Prof.", "Prof.", 0, None, None),
    ("Psicopedagogía", "Psicopedagogo", "Psicopedagoga", "Psp. o Lic.", "Psp. o Lic.", 1, "Psp.,Lic.", "Psp.,Lic."),
    ("Psiquiatría", "Psiquiatra", "Psiquiatra", "Dr.", "Dra.", 0, None, None),
    ("Terapista hipnótico", "Terapista hipnótico", "Terapista hipnótica", "Tta.", "Tta.", 0, None, None),
    ("Terapista holístico", "Terapista holístico", "Terapista holística", "Tta.", "Tta.", 0, None, None),
    ("Terapista vibracional", "Terapista vibracional", "Terapista vibracional", "Tta.", "Tta.", 0, None, None),
]

TIPOS_LICENCIA = [
    # Nombre, PorcentajeBonificacion, DuracionMaximaDias, EsManual
    ("Licencia médica", 100, None, 1),
    ("Licencia por duelo", 100, 5, 0),
    ("Licencia por matrimonio", 100, 14, 0),
    ("Licencia por maternidad", 50, 90, 0),
    ("Licencia por motivos personales", 100, None, 1),
]

CONDICIONES_NORMAS = [
    # Numero, Titulo, Texto
    (1, "Forma de pago", (
        "Se enviará a cada profesional una liquidación mensual a principios de mes por sus horarios reservados, "
        "la cual será abonada por el mismo dentro del mes en curso. El profesional podrá hacer un pago total o "
        "realizar también pagos parciales, lo importante es cancelar el total liquidado antes del comienzo del "
        "nuevo mes."
    )),
    (2, "Dias feriados", (
        "Los días declarados como feriados nacionales o días no laborables por el ministerio del interior no se "
        "contemplan dentro de la liquidación, dando por descontado, en principio, que el profesional no hará uso "
        "del espacio reservado en esas fechas. En caso de querer hacerlo, deberá comunicarse previamente con el "
        "administrador del espacio para coordinarlo, y abonará únicamente las horas utilizadas en la liquidación "
        "del mes siguiente. Aclaraciones y excepciones: el Jueves Santo no es considerado feriado por dicho "
        "organismo; por tal motivo, se liquidará normalmente. Las únicas excepciones serán el 24 y el 31 de "
        "diciembre, fechas a las que se les dará el mismo tratamiento que a los feriados, aunque legalmente no lo "
        "sean. Por cualquier duda consultar la fuente oficial: https://www.argentina.gob.ar/feriados"
    )),
    (3, "Vacaciones", (
        "Se reconocerá al profesional un máximo de dos semanas por año calendario en concepto de vacaciones. "
        "Dicho período no será abonado y el profesional conservará la reserva del espacio."
    )),
    (4, "Esquema de descuentos", (
        "Queda a criterio del espacio conservar, ampliar, modificar o eliminar el actual esquema de descuentos a "
        "futuro."
    )),
    (5, "Actualizacion de los valores", (
        "Los valores de las horas se revisarán y, de ser necesario, se ajustarán en forma bimestral durante los "
        "meses pares (febrero, abril, junio, agosto, octubre y diciembre) para mantener los mismos actualizados."
    )),
    (6, "Compromiso de reserva", (
        "El compromiso de reserva se renueva mensualmente. Antes de que comience el nuevo mes el profesional "
        "puede cancelar su reserva o bien ajustarla de acuerdo a su necesidad y a la disponibilidad del lugar. "
        "Las reducciones de los módulos fijos reservados se pueden hacer únicamente para el mes siguiente, en "
        "cambio las extensiones de dichos módulos se pueden coordinar entre el administrador y el profesional en "
        "cualquier momento del mes. Las nuevas horas incorporadas a la reserva durante el mes en curso se "
        "liquidarán al mes siguiente. Si el profesional no se contacta con el administrador se dará por entendido "
        "que continúa con la misma reserva del mes anterior."
    )),
    (7, "Reservas aisladas", (
        "Las horas aisladas para alguna fecha en particular deberán ser coordinadas previamente con el espacio. "
        "Las mismas no tienen recargo sobre el valor de la hora regular, pero no se les aplican los descuentos "
        "que sí poseen las reservas regulares. Dichas horas pueden cancelarse hasta con 24hs de anticipación sin "
        "costo alguno, no se pueden cancelar el mismo día de la reserva. Solo se reservan horarios con este "
        "formato de un mes a otro como máximo."
    )),
    (8, "Ausentes", (
        "Las ausencias tanto de los pacientes como de los profesionales no intervienen en el cálculo de la "
        "liquidación, por tal motivo son responsabilidad de estos últimos la administración y uso de sus bloques "
        "reservados."
    )),
    (9, "Juego de llaves", (
        "Se entregará al profesional un juego de llaves para que este se maneje con independencia durante su "
        "tiempo en el lugar haciéndose desde ese momento responsable de las mismas. Por dicho juego se pedirá un "
        "valor en concepto de depósito equivalente al costo de realizar esas llaves. En caso de extraviarlas el "
        "profesional deberá abonar la reposición de dichas llaves. Si el profesional en algún momento deja de "
        "atender en el lugar, en caso de que haya pagado ese depósito el espacio le reintegrará el valor "
        "actualizado de dichas llaves al momento de la devolución. Si es necesario realizar un cambio de "
        "combinación en las unidades el espacio reemplazará las llaves de los profesionales sin cargo alguno, "
        "pero en el caso de que sea la llave del edificio la que se cambia el profesional abonará el depósito de "
        "la nueva llave ya que es una responsabilidad ajena al espacio."
    )),
    (10, "Optimizacion de la grilla horaria", (
        "En el caso de haber modificaciones en cuanto a la disponibilidad por bajas de horas de algún "
        "profesional, primero se procurará realizar los cambios necesarios para ubicar a algún profesional "
        "activo que se encuentre tomando horas no consecutivas o en distintos consultorios, llegado el caso el "
        "espacio puede reubicar a otros profesionales en otros consultorios para poder optimizar las estructuras "
        "respetándoles los horarios que tenía acordados."
    )),
    (11, "Licencia por maternidad", (
        "Se reconocerá un máximo de 90 días corridos como licencia de maternidad para las profesionales mujeres "
        "que no vayan a utilizar los consultorios por ese motivo, período durante el cual abonará el 50% del "
        "valor de la reserva y conservará la misma hasta su reincorporación, siempre que desee mantenerla."
    )),
    (12, "Licencia por matrimonio", (
        "En el caso de que el profesional contraiga matrimonio y no utilizara los consultorios por algún viaje a "
        "modo de luna de miel, se le reconocerá un plazo adicional máximo de dos semanas con el mismo tratamiento "
        "que el período de vacaciones."
    )),
    (13, "Otras eventualidades", (
        "El espacio no contempla otras eventualidades además de las descriptas anteriormente. En caso de que el "
        "profesional no pueda utilizar el espacio reservado, ya sea por motivos personales o por causas de fuerza "
        "mayor, el espacio podrá ofrecer, sujeto a disponibilidad, alternativas para recuperar las horas no "
        "utilizadas sin costo adicional."
    )),
    (14, "Entrega de los consultorios", (
        "El profesional debe dejar puntualmente libre el consultorio en los horarios acordados, y a la hora de "
        "hacerlo se le solicita al mismo que tenga la seguridad de chequear que el aire acondicionado quede "
        "apagado, dejar la puerta del consultorio entreabierta y que la persiana quede baja en caso de que ese "
        "consultorio cuente con ella. Los atrasos de los pacientes no son motivo válido para extender el bloque "
        "reservado para no perjudicar a los profesionales que toman horas a posterior en ese consultorio."
    )),
    (15, "Convivencia", (
        "El profesional deberá cumplir con las normas de convivencia lógicas de cualquier lugar de este tipo, "
        "como ser el cuidado general del espacio, su limpieza, su orden, el hecho de trabajar en silencio y "
        "armonía, el respeto a sus colegas, etc., haciéndose responsable por dichas cuestiones tanto de sus actos "
        "como también los de sus pacientes, indicándoles a estos las conductas inapropiadas que puedan llegar a "
        "tener dentro de su permanencia en el lugar."
    )),
    (16, "Area de guardado de materiales", (
        "El espacio ofrece un lugar para que el profesional pueda dejar elementos personales y laborales, "
        "pidiéndole a este únicamente que identifique claramente con nombre dichos elementos. El espacio no se "
        "hace responsable de cualquier pérdida o daño que estos puedan sufrir."
    )),
    (17, "Acceso de terceros", (
        "No está permitido el ingreso de terceros relacionados con el profesional a los consultorios para que "
        "estos permanezcan ahí esperando a que dicho profesional termine su jornada, esto es para no incomodar "
        "al resto de los colegas y conservar la armonía del lugar de trabajo. Se entiende que el uso del espacio "
        "y de sus comodidades son exclusivamente para el profesional que contrata el lugar."
    )),
    (18, "Cesion de la reserva", (
        "Queda expresamente prohibido al profesional ceder su espacio reservado a otro profesional, sea o no "
        "miembro actual del equipo del consultorio, sin haberlo consultado previamente con el administrador del "
        "lugar."
    )),
    (19, "Area de cocina", (
        "El espacio cuenta con un sector de cocina del cual se ponen a disposición de los profesionales todos "
        "sus elementos conjuntamente con una variedad de infusiones para su uso sin cargo alguno. La única "
        "condición es que cada cual lave y ordene los elementos que haya utilizado dejando así el área en "
        "condiciones para el uso por parte de otro profesional."
    )),
    (20, "Vigencia de condiciones", (
        "Las condiciones anteriormente detalladas rigen desde el momento en que son enviadas al profesional "
        "conjuntamente con la liquidación mensual, tomando siempre el último envío como modelo de las "
        "condiciones vigentes para la reserva del espacio."
    )),
    (21, "Conformidad y cumplimiento", (
        "La reserva de un espacio por parte del profesional implica el conocimiento y la aceptación de todas las "
        "condiciones anteriormente detalladas."
    )),
]

DETALLES_COMPLEMENTARIOS_PROPUESTA = [
    # Orden, Titulo, Texto
    (1, "Apertura a los pacientes", (
        "El ingreso del paciente al edificio es a cargo nuestro, totalmente desatendido por parte del "
        "profesional, el mismo no tiene que hacer nada al respecto. Una vez que el paciente llega a la puerta de "
        "la unidad se le abre a través de un pulsador desde el mismo consultorio para que ingrese directamente a "
        "la sala de espera y aguarde allí para ser llamado por el profesional. Es decir, en ningún momento hay "
        "que bajar del piso, salir del consultorio, ni interrumpir la sesión en curso para abrirle al próximo "
        "paciente."
    )),
    (2, "Modalidad de reserva aislada", (
        "Aparte de las reservas regulares, que son las reservas fijas para todas las semanas del mes, se puede "
        "reservar en forma aislada para fechas y horarios puntuales por única vez nada mas."
    )),
    (3, "Descuentos por cantidad de horas semanales reservadas", (
        "Se realizan descuentos en base a la cantidad de horas semanales reservadas sobre el valor total de la "
        "reserva, siempre y cuando los pagos se vayan realizando dentro del mes en curso."
    )),
    (4, "Vacaciones", (
        "Se contemplan en favor del profesional hasta dos semanas por año calendario en concepto de vacaciones, "
        "dicho lapso no será abonado por el profesional y este conservará la reserva del espacio sin costo "
        "alguno."
    )),
    (5, "Feriados", (
        "Las horas reservadas en los días feriados no se abonan, salvo que el profesional quiera hacer uso igual "
        "del espacio ese día, en ese caso solo abonaría las horas utilizadas en esa jornada."
    )),
    (6, "Compromiso de reserva", (
        "El profesional puede ir modificando y adaptando su bloque reservado mes a mes de acuerdo a su necesidad "
        "y a la disponibilidad del espacio."
    )),
    (7, "Ajuste de valores", (
        "Se realizan en forma {frecuencia} los ajustes mínimos en los valores con el fin de mantener los mismos "
        "actualizados."
    )),
    (8, "Forma de pago", (
        "Los bloques reservados se liquidan a principio de mes y luego el profesional abona dicha liquidación "
        "preferentemente en cualquier momento dentro del mes en curso."
    )),
    (9, "Lista de espera", (
        "En el caso de no contar con la disponibilidad buscada manejamos una lista de espera en la que agendamos "
        "las preferencias de los profesionales, si en algún momento a futuro se produce una liberación que "
        "coincide con el interés del profesional nosotros nos comunicamos con el mismo para que sin compromiso "
        "alguno vuelva a evaluar la propuesta en ese momento."
    )),
    (10, "Grupo de WhatsApp", (
        "Contamos con un grupo de WhatsApp en el que están los profesionales que son miembros del espacio. "
        "Nosotros avisamos en el mismo cosas relacionadas con el lugar, y por otro lado queda como fuente de "
        "intercambio profesional para los profesionales miembros como consultas, derivaciones, avisos de cursos, "
        "etc."
    )),
    (11, "Juego de llaves", (
        "Se entrega al profesional un juego de llaves para que el mismo se maneje con independencia durante su "
        "permanencia en el espacio. Dicho juego tiene un costo a modo de depósito, eso significa que si el "
        "profesional prescinde de los servicios del espacio por cualquier motivo contraentrega de las llaves se "
        "le reintegrará el dinero del depósito actualizado a lo que valga en ese momento."
    )),
    (12, "Documentación necesaria", (
        "De confirmar la incorporación al espacio como documentación se pide únicamente DNI frente y dorso, "
        "título, y matrícula nacional y/o provincial más una ficha para completar con los datos personales."
    )),
    (13, "Visita para conocer el espacio", (
        "Los profesionales interesados en conocer el lugar en persona están invitados a hacerlo sin compromiso "
        "alguno solo con un mensaje previo para coordinar el día y el momento. Para poder apreciar el lugar sin "
        "gente y ver la totalidad de los consultorios se sugiere hacerlo temprano, alrededor de las 8:30hs, ya "
        "que la mayoría de los profesionales activos empiezan a llegar a partir de las 9hs. Los sábados luego de "
        "las 14hs es otra buena opción."
    )),
    (14, "Atención personalizada", (
        "Quedamos a disposición del profesional interesado en todo momento por cualquier consulta que nos "
        "quieran realizar o bien para volver a recibir la información actualizada del lugar. Las consultas no "
        "molestan, al contrario, es un placer para nosotros responderlas, así que no duden en escribir por "
        "cualquier cosa en que los podamos ayudar."
    )),
    (15, "Contacto", "{contacto}"),
]

LISTAS_EDITABLES = {
    "CondicionFiscal": ["Consumidor Final", "Responsable Inscripto", "Monotributo", "Exento"],
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
        "FrecuenciaActualizacionValores, MesesPeriodoActualizacion, "
        "PorcentajeAjusteSaldoAtrasado, SemanasVacacionesMaximasPorAnio, DiasEnvioLiquidacionesRemanentes, "
        "DiasAntesFinMesRecordatorioPlan, DiasAntesFinMesRecordatorioGeneral, "
        "RetencionHistorialListaEsperaAnios, ModulosExtendidos, TamanoMaximoImagenMB, "
        "ModoFechaFicticia, MensajesPlural) "
        "VALUES (1, 8, 22, ?, 30, 8, 10, 0, ?, ?, 3, 2, 5, 5, 3, 5, 0, 5, 0, 1)",
        (json.dumps(DIAS_LUNES_A_SABADO), "Bimestral", json.dumps([2, 4, 6, 8, 10, 12])),
    )
    conn.commit()


def sembrar_profesiones(conn: sqlite3.Connection) -> None:
    if not _tabla_vacia(conn, "Profesion"):
        return
    conn.executemany(
        "INSERT INTO Profesion (Nombre, NombreMasculino, NombreFemenino, "
        "TratamientoDefaultMasculino, TratamientoDefaultFemenino, TieneMultiplesTratamientos, "
        "OpcionesTratamientoMasculino, OpcionesTratamientoFemenino) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
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


def sembrar_condiciones_normas(conn: sqlite3.Connection) -> None:
    if not _tabla_vacia(conn, "CondicionNorma"):
        return
    conn.executemany(
        "INSERT INTO CondicionNorma (Numero, Titulo, Texto, Activo) VALUES (?, ?, ?, 1)",
        CONDICIONES_NORMAS,
    )
    conn.commit()


def sembrar_detalles_complementarios_propuesta(conn: sqlite3.Connection) -> None:
    if not _tabla_vacia(conn, "DetalleComplementarioPropuesta"):
        return
    conn.executemany(
        "INSERT INTO DetalleComplementarioPropuesta (Orden, Titulo, Texto, Activo) VALUES (?, ?, ?, 1)",
        DETALLES_COMPLEMENTARIOS_PROPUESTA,
    )
    conn.commit()


def sembrar_valores_por_defecto(conn: sqlite3.Connection) -> None:
    sembrar_bloques_rigidos(conn)
    sembrar_configuracion(conn)
    sembrar_profesiones(conn)
    sembrar_tipos_licencia(conn)
    sembrar_esquema_descuentos(conn)
    sembrar_listas_editables(conn)
    sembrar_condiciones_normas(conn)
    sembrar_detalles_complementarios_propuesta(conn)
