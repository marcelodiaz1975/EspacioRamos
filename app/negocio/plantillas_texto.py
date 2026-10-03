"""Plantillas de texto editables: pedido de la clienta de poder editar sin
tocar código tanto los mensajes automáticos del Centro de mensajería como
la ayuda contextual F1 de cada pantalla (este último, además, es el
hallazgo #23 de la auditoría DC-01/DC-10: "la ayuda F1 funciona y es
contextual, pero no es editable sin tocar código").

Mecanismo (reusa `sustituir_variables`, ya aprobado para `MensajePredefinido`,
en vez de inventar uno nuevo): cada "slot" del sistema (un mensaje
puntual, la ayuda de una pantalla puntual) tiene una CLAVE fija y un texto
de fábrica hardcodeado en Python (`DEFAULT_*` acá, o el propio
`Seccion.ayuda` para la ayuda F1). `PlantillaTexto` guarda, por clave, un
override opcional — sin fila para esa clave, se usa el texto de fábrica.
No hay alta/baja desde la GUI (los slots son un conjunto fijo que define
el código), solo edición y "Restablecer al original" (que borra la fila,
no la deja en blanco: un texto vacío a propósito es distinto de "no
personalizado" — por eso `guardar_texto_personalizado` nunca persiste
una cadena vacía, la trata como "sin override").

Decisión explícita de la clienta: las partes condicionales de un mensaje
(si hay feriados cargados, si el profesional queda deudor, etc.) las
sigue resolviendo el código — a la plantilla le llegan ya armadas como
una variable más (ej. `{bloque_feriados}`), nunca como lógica editable
dentro del texto. Esto evita que una plantilla mal escrita rompa la
decisión de cuándo mostrar cada sección, a costa de que esos bloques en
sí (la redacción de las 3 líneas de feriados del Mensaje grupal, por
ejemplo) no sean editables en esta primera vuelta — si hace falta,
sumarlos como slots propios más adelante es un cambio acotado."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.repositorio.registro import obtener_repositorio


def sustituir_variables(texto: str, variables: dict[str, str]) -> str:
    """Reemplaza "{variable}" en el texto de una plantilla (de
    `MensajePredefinido`, o de las de acá) por su valor. Los saltos de
    línea del texto guardado se respetan tal cual."""
    resultado = texto
    for clave, valor in variables.items():
        resultado = resultado.replace(f"{{{clave}}}", str(valor))
    return resultado


def obtener_texto_personalizado(conn: sqlite3.Connection, clave: str) -> str | None:
    filas = obtener_repositorio(conn, "PlantillaTexto").listar(Clave=clave)
    return filas[0]["TextoPersonalizado"] if filas and filas[0]["TextoPersonalizado"] else None


def guardar_texto_personalizado(conn: sqlite3.Connection, clave: str, texto: str | None) -> None:
    """`texto` en blanco (o None) restablece al original: se borra la fila
    en vez de guardar una cadena vacía, para no confundir "nunca se
    personalizó" con "se personalizó a propósito como texto vacío"."""
    repo = obtener_repositorio(conn, "PlantillaTexto")
    filas = repo.listar(Clave=clave)
    valor = texto.strip() if texto and texto.strip() else None
    if filas:
        if valor is None:
            repo.eliminar(filas[0]["IdPlantilla"])
        else:
            repo.actualizar(filas[0]["IdPlantilla"], TextoPersonalizado=valor)
    elif valor is not None:
        repo.crear(Clave=clave, TextoPersonalizado=valor)


def resolver_plantilla(conn: sqlite3.Connection, clave: str, default: str) -> str:
    """El texto efectivo para esta clave: el personalizado si existe, si
    no el de fábrica. Separado de `sustituir_variables` porque la ayuda
    F1 no tiene variables que sustituir — solo necesita esta función."""
    personalizado = obtener_texto_personalizado(conn, clave)
    return personalizado if personalizado is not None else default


# --------------------------------------------------------------------------
# Registro de los 7 mensajes automáticos del Centro de mensajería (DC-02/
# DC-03) que pasan a ser editables. Separados acá (y no mezclados con la
# lógica de armado en `app.negocio.mensajes`) para que la pantalla de
# edición pueda listar nombre/variables sin tener que importar ni ejecutar
# ninguna función de armado de mensajes.
#
# `mensaje_detalle_reserva_aislada` queda FUERA de este alcance a
# propósito (pedido explícito de la clienta de arrancar acotado): arma
# listas de reservas/cargos/edificios con loops, misma complejidad
# estructural que los textos de WhatsApp de Oferta/Disponibilidad — un
# alcance más grande, para una vuelta aparte.

DEFAULT_SITUACION_1 = (
    "MENSAJE AUTOMATICO\n\n"
    "Al día de la fecha se registra un saldo de {saldo} correspondiente al período anterior, por ende se "
    "retiene la liquidación para ser enviada el {dia_semana} {fecha} contemplando las nuevas cancelaciones "
    "que se vayan a realizar desde ahora hasta ese momento con el fin de que en este plazo se regularice la "
    "situación.\n\n"
    "Se recuerda que los descuentos por cantidad de horas semanales reservadas se realizan únicamente cuando "
    "el saldo está al día al momento de comenzar el nuevo mes, y por otro lado los saldos atrasados que "
    "queden al momento de enviar la nueva liquidación se ajustarán para mantener los mismos actualizados.\n\n"
    "Por cualquier consulta o duda acerca de lo expresado en este texto responder este mensaje para con "
    "gusto conversar todas las inquietudes que pudieran existir.\n\n"
    "Saludos, {nombre_espacio}."
)

DEFAULT_SITUACION_2 = (
    "Hola {nombre}, cómo estás..? Te envío la liquidación del mes de {mes} en forma manual tal cual te había "
    "adelantado que iba a hacer luego del mensaje que se disparó anteriormente en forma automática. Por "
    "cualquier cosa me escribís, saludos..!"
)

DEFAULT_SITUACION_3 = (
    "Hola {nombre}, cómo estás? {cuando} se van a mandar los archivos con las liquidaciones de {mes} a los "
    "profesionales que están al día con sus saldos, en tu caso se va a llegar un mensaje automático en lugar "
    "del PDF, esto es porque quedó un saldo pendiente de {saldo} correspondiente al período anterior.\n\n"
    "Obviamente la diferencia no es significativa, yo luego de ese mensaje te mando el archivo en forma "
    "manual con los descuentos contemplados como siempre, solo te estoy anticipando esta secuencia para que "
    "no te sorprenda ya que todo se hace de manera automática.\n\n"
    "Luego del mensaje te escribo, saludos..!"
)

DEFAULT_SITUACION_5 = (
    "Hola {nombre}, cómo estás..? El mes de {mes} ya se encuentra cerrado en base a tu reserva actual, te va "
    "a llegar en breve un mensaje automático informándote que hay saldos para regularizar en lugar del "
    "archivo de la liquidación del mes.\n\n"
    "Como te informé hace unos días no se pueden trasladar saldos de un mes a otro cuando hay un plan de "
    "pagos acordado. El saldo a regularizar es de {saldo}. Quedo atento a tu comentario para estar al tanto "
    "de como tenés pensado manejar la situación, aguardo tu respuesta, gracias."
)

DEFAULT_ENVIO_LIQUIDACION = (
    "MENSAJE AUTOMATICO\n"
    "(no es necesario responder)\n\n"
    "* Se adjunta liquidación correspondiente al mes de {mes}\n"
    "* Abrir el archivo enseguida de recibirlo para que les quede en el teléfono\n"
    "* Revisar el contenido, por cualquier duda comunicarse con el administrador"
)

DEFAULT_GRUPAL = (
    "LIQUIDACIONES DE {mes_mayus} - AVISOS VARIOS\n\n"
    "CIERRE DE RESERVA 👇\n\n"
    "* El {dia_cierre} {fecha_cierre} cerramos las reservas de {mes}. Por informes de pago, avisos de "
    "vacaciones o por cualquier otra cosa relacionada con las reservas escribir por privado hasta ese día "
    "inclusive.\n\n"
    "ENVIO DE LIQUIDACIONES 👇\n\n"
    "* El {dia_envio} {fecha_envio} se enviarán a través de un programa en forma automática las liquidaciones "
    "sin otro mensaje complementario solo a los profesionales que estén sin saldos pendientes a la fecha.\n"
    "* No hace falta responder el mensaje, si se pide abrir en ese momento el archivo para que les quede en "
    "el teléfono.\n"
    "* Dichas liquidaciones contarán con los habituales descuentos por cantidad de horas semanales "
    "reservadas.\n"
    "* El profesional que tenga alguna duda por su saldo actual puede escribir{nos_o_me} por privado para "
    "consultar{nos_o_me} el estado de cuenta.{bloque_feriados}"
)

DEFAULT_RECORDATORIO_FIN_DE_MES = (
    "MENSAJE AUTOMATICO\n\n"
    "(Texto recordatorio de carácter informativo, no es necesario responder)\n\n"
    "ESTADO DE CUENTA ACTUAL 👇\n\n"
    "{estado_cuenta}\n\n"
    "CIERRE DE RESERVAS 👇\n\n"
    "* {fecha_cierre_reservas}\n\n"
    "ENVIO DE LIQUIDACIONES 👇\n\n"
    "* {fecha_envio_liquidaciones}{bloque_feriados}"
)


@dataclass
class PlantillaMensaje:
    clave: str
    nombre: str
    default: str
    variables: tuple[str, ...]


MENSAJES_EDITABLES: list[PlantillaMensaje] = [
    PlantillaMensaje(
        "mensaje_situacion_1", "Aviso de saldo pendiente (se retiene la liquidación)",
        DEFAULT_SITUACION_1, ("saldo", "dia_semana", "fecha", "nombre_espacio"),
    ),
    PlantillaMensaje(
        "mensaje_situacion_2", "Envío manual de liquidación (ya regularizado)",
        DEFAULT_SITUACION_2, ("nombre", "mes"),
    ),
    PlantillaMensaje(
        "mensaje_situacion_3", "Aviso previo de envío de liquidaciones (con saldo pendiente)",
        DEFAULT_SITUACION_3, ("nombre", "cuando", "mes", "saldo"),
    ),
    PlantillaMensaje(
        "mensaje_situacion_5", "Liquidación ya cerrada, saldo a regularizar (con plan de pagos)",
        DEFAULT_SITUACION_5, ("nombre", "mes", "saldo"),
    ),
    PlantillaMensaje(
        "mensaje_envio_liquidacion", "Mensaje que acompaña el PDF de liquidación",
        DEFAULT_ENVIO_LIQUIDACION, ("mes",),
    ),
    PlantillaMensaje(
        "mensaje_grupal", "Mensaje grupal de fin de mes (cierre de reservas y envío de liquidaciones)",
        DEFAULT_GRUPAL, ("mes_mayus", "dia_cierre", "fecha_cierre", "mes", "dia_envio", "fecha_envio",
                          "nos_o_me", "bloque_feriados"),
    ),
    PlantillaMensaje(
        "mensaje_recordatorio_fin_de_mes", "Recordatorio de fin de mes (color Bordó)",
        DEFAULT_RECORDATORIO_FIN_DE_MES, ("estado_cuenta", "fecha_cierre_reservas",
                                           "fecha_envio_liquidaciones", "bloque_feriados"),
    ),
]
