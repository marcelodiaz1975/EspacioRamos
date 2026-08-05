"""Fechas especiales / feriados (sección 3.17 del documento).

Incluye la importación automática de feriados nacionales de Argentina que
menciona el documento ("Importación automática desde argentina.gob.ar/
feriados disponible"). La función que llama a la API real es inyectable
(parámetro `obtener_datos`) para poder testear sin red y para no atarse a
un único proveedor si el endpoint cambia.

NOTA: no fue posible verificar en vivo el formato exacto de la respuesta
de la API oficial desde este entorno (la red saliente lo bloquea). El
parseo de abajo está escrito de forma defensiva sobre el formato público
más citado (claves "dia", "mes", "tipo", "motivo") pero conviene
confirmarlo con una prueba real antes de usarlo en producción.
"""
from __future__ import annotations

import json
import sqlite3
import urllib.request
from datetime import date

from app.repositorio.registro import obtener_repositorio

URL_FERIADOS_ARGENTINA = "https://api.argentina.gob.ar/v2/feriados/{anio}"

MAPEO_TIPO_API = {
    "inamovible": "Feriado nacional",
    "trasladable": "Feriado nacional",
    "no_laborable": "Día no laborable",
    "puente": "Puente turístico",
}

TIPOS_QUE_DESCUENTAN_100 = ("Feriado nacional", "Día no laborable")


def _obtener_feriados_api(anio: int) -> list[dict]:
    url = URL_FERIADOS_ARGENTINA.format(anio=anio)
    with urllib.request.urlopen(url, timeout=10) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def importar_feriados_argentina(conn: sqlite3.Connection, anio: int, obtener_datos=None) -> int:
    """Importa los feriados nacionales de `anio` a FechasEspeciales. No
    duplica fechas ya cargadas. Devuelve la cantidad de filas nuevas."""
    obtener_datos = obtener_datos or _obtener_feriados_api
    datos = obtener_datos(anio)
    repo = obtener_repositorio(conn, "FechasEspeciales")
    existentes = {f["Fecha"] for f in repo.listar()}

    insertados = 0
    for item in datos:
        fecha = f"{anio:04d}-{int(item['mes']):02d}-{int(item['dia']):02d}"
        if fecha in existentes:
            continue
        tipo = MAPEO_TIPO_API.get(item.get("tipo"), "Feriado nacional")
        repo.crear(Fecha=fecha, Descripcion=item.get("motivo"), Tipo=tipo)
        existentes.add(fecha)
        insertados += 1
    return insertados


def feriados_relevantes_periodo(conn: sqlite3.Connection, anio: int, mes: int) -> list[sqlite3.Row]:
    """Feriados que se descuentan al 100% en la liquidación (sección 5.4):
    nacionales y no laborables, de lunes a sábado (domingos se omiten)."""
    prefijo = f"{anio:04d}-{mes:02d}-"
    filas = obtener_repositorio(conn, "FechasEspeciales").listar(Activo=1)
    resultado = []
    for f in filas:
        if not f["Fecha"].startswith(prefijo):
            continue
        if f["Tipo"] not in TIPOS_QUE_DESCUENTAN_100:
            continue
        if date.fromisoformat(f["Fecha"]).weekday() == 6:  # domingo
            continue
        resultado.append(f)
    return resultado
