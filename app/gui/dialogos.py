"""Diálogos de confirmación reusados entre varias pantallas."""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QMessageBox, QWidget

from app.negocio.dias import periodo_actual
from app.negocio.formato import mes_texto


def _confirmar_periodo_anterior(parent: QWidget, periodo: str, detalle: str) -> bool:
    anio, mes = (int(p) for p in periodo.split("-"))
    respuesta = QMessageBox.question(
        parent, "Fecha de un mes anterior",
        f"{detalle} corresponde a {mes_texto(mes)} de {anio}, un mes anterior al que está en curso.\n\n"
        "¿Confirmás que es correcta?",
    )
    return respuesta == QMessageBox.StandardButton.Yes


def confirmar_si_fecha_es_mes_anterior(parent: QWidget, conn: sqlite3.Connection, fecha_iso: str | None) -> bool:
    """DC-06 §3: cualquier movimiento cargado con una fecha de un mes
    anterior al mes en curso (algo que puede pasar mucho tiempo después de
    haber avanzado de mes, no solo en los primeros días) pide confirmación
    antes de guardarse, para atajar errores de tipeo en la fecha. Devuelve
    True si corresponde continuar: la fecha no es de un mes anterior, o el
    operador confirmó que es correcta."""
    if not fecha_iso:
        return True
    periodo_fecha = fecha_iso[:7]
    if periodo_fecha >= periodo_actual(conn):
        return True
    return _confirmar_periodo_anterior(parent, periodo_fecha, f"La fecha ingresada ({fecha_iso})")


def confirmar_si_periodo_imputado_es_anterior(parent: QWidget, conn: sqlite3.Connection, periodo: str | None) -> bool:
    """Misma confirmación que `confirmar_si_fecha_es_mes_anterior`, para
    formularios que imputan directo a un período ('AAAA-MM') en vez de a
    una fecha puntual (pagos, cargos especiales)."""
    if not periodo or periodo >= periodo_actual(conn):
        return True
    return _confirmar_periodo_anterior(parent, periodo, f"El período imputado ({periodo})")


def confirmar_datos_antes_de_crear(parent: QWidget, titulo: str, lineas: list[str]) -> bool:
    """Pedido explícito de la clienta ("antes de crear cualquier
    reserva, mostrar una alerta previa con los datos a guardar, con
    opción de confirmar o cancelar"): cartel de confirmación genérico,
    con una vista previa de los datos que se están por guardar —
    pensado para extenderse pantalla por pantalla a medida que se
    revisan (confirmado con la clienta, "pantalla por pantalla, a
    medida que las revisás", no un barrido de todo el sistema de una
    sola vez), arrancando por las tres solapas de Reservas.

    Esta función solo pregunta — nunca toca el formulario. Si el
    operador cancela (devuelve `False`), el llamador tiene que dejar los
    datos ya cargados tal cual estaban, sin limpiar nada, para que se
    puedan corregir y reintentar — es responsabilidad de quien llama
    (no de este diálogo) no resetear el formulario en ese caso, al
    revés de lo que sí hace después de una creación exitosa."""
    detalle = "\n".join(lineas)
    respuesta = QMessageBox.question(
        parent, titulo, f"Confirmá los datos antes de guardar:\n\n{detalle}",
    )
    return respuesta == QMessageBox.StandardButton.Yes


def preguntar_si_no(parent: QWidget, titulo: str, texto: str, *, default_si: bool = True) -> bool:
    """Pedido explícito de la clienta sobre la alerta de "Restablecer
    descuentos" de Pagos/Registrar pagos: "¿Yes/No" seguía viendo los
    botones en inglés, a pesar de que #140 ya instaló la traducción
    oficial de Qt (`qt_es.qm`, ver `instalar_traduccion_es` en
    `gui_main.py`) para todo el resto del sistema. Esa traducción
    depende de que el archivo `.qm` de Qt esté disponible y cargue bien
    en el entorno real donde corre la app — nada garantiza que un build
    empaquetado lo incluya siempre. En vez de confiar en eso para este
    cartel, se arman los botones a mano con texto "Sí"/"No" fijo (nunca
    depende de ninguna traducción externa) y con el default configurable
    (`default_si`, en vez del `QMessageBox.StandardButton.No` fijo que
    traía `QMessageBox.question`)."""
    cuadro = QMessageBox(QMessageBox.Icon.Question, titulo, texto, QMessageBox.StandardButton.NoButton, parent)
    boton_si = cuadro.addButton("Sí", QMessageBox.ButtonRole.YesRole)
    boton_no = cuadro.addButton("No", QMessageBox.ButtonRole.NoRole)
    cuadro.setDefaultButton(boton_si if default_si else boton_no)
    cuadro.exec()
    return cuadro.clickedButton() is boton_si
