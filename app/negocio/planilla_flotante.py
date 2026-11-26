"""Planilla flotante (F2, pedido de la clienta: "en vez de la calculadora,
una especie de planilla de Excel flotante, para hacer anotaciones, cálculos,
etc... para anotaciones simples y cálculos simples, temporales, como para
tener a mano cada tanto" — reemplaza por completo a la vieja `Calculadora`,
ver `app.gui.widgets.planilla_flotante`).

Persistencia permanente a pedido explícito ("no cuando se cierra el sistema
y se vuelve a entrar se blanquea todo, quiero que se conserven"): una fila
en `CeldaPlanilla` por celda con contenido o algún formato propio — sin fila
para una dirección ("A1", "B12", etc.) significa celda vacía, sin estilo.
"Que las pueda borrar cuando yo quiera" se resuelve de dos formas: una celda
vuelta a dejar sin contenido ni formato borra su fila sola (`guardar_celda`),
y `vaciar_todo` borra la planilla entera de una (botón aparte en la GUI).

Fórmulas: "funciones básicas de operaciones aritméticas... no fórmulas
complejas" (pedido explícito) — una celda que arranca con "=" es una fórmula
con +-*/, paréntesis y referencias a otras celdas (ej. "=A1+B2*3"), sin
funciones (no hay SUM/PROMEDIO/etc.). "+" es sinónimo de "=" (pedido
explícito: "que al poner '+C2+C3' sea lo mismo que '=C2+C3'", mismo
criterio que Excel/Lotus 1-2-3 con el signo "+") — "-" a propósito NO es
sinónimo, para no romper un número negativo suelto (ej. "-500") que se
sigue guardando como nota/número, no como fórmula. Se resuelve
recursivamente contra el contenido crudo de TODAS las celdas
(`valor_celda`), con detección de referencia circular. Una celda sin "="
ni "+" nunca es fórmula, aunque su texto parezca una cuenta — eso es
justo lo que permite "anotar" texto/números sueltos sin que el sistema
intente calcularlos.

Única excepción al "sin funciones" de arriba, agregada a pedido
explícito de la clienta ("¿se puede crear una fórmula sola como para
sumar un rango de celdas?", tras explicarle que sin esto hay que
nombrar cada celda sumada con "+"): `SUMA(C2:C10)` suma todas las
celdas del rectángulo entre las dos esquinas dadas (soporta rangos de
una sola columna/fila o un bloque de varias, igual que Excel) —
`_PATRON_RANGO` la reemplaza por el número ya calculado ANTES de que
`_PATRON_CELDA` procese el resto de la fórmula, así que "=SUMA(C2:C10)
+D1" sigue funcionando (el "+D1" lo resuelve el mecanismo de siempre).
Cada celda del rango pasa por `valor_celda` con el mismo `_visitando`
de la fórmula que contiene el `SUMA(...)` — una referencia circular
dentro del rango (ej. sumar un rango que se incluye a sí misma) se
detecta igual que una referencia circular suelta. Sigue siendo la
ÚNICA función disponible — "no fórmulas complejas" es el pedido
original, esto es una excepción puntual, no una apertura a más
funciones."""
from __future__ import annotations

import re
import sqlite3

_PATRON_CELDA = re.compile(r"[A-Z]+[0-9]+")
_PATRON_RANGO = re.compile(r"SUMA\(([A-Z]+[0-9]+):([A-Z]+[0-9]+)\)")
_PATRON_DIRECCION = re.compile(r"([A-Z]+)([0-9]+)")
_CARACTERES_FORMULA_VALIDOS = set("0123456789.+-*/() ")
_PREFIJOS_FORMULA = ("=", "+")


def _indice_columna(letras: str) -> int:
    """"A" -> 0, "B" -> 1... "Z" -> 25 (y, de yapa, "AA" -> 26... aunque
    la grilla de la GUI no llega a usar columnas de dos letras) — mismo
    algoritmo base-26 estándar de cualquier planilla de cálculo."""
    indice = 0
    for letra in letras:
        indice = indice * 26 + (ord(letra) - ord("A") + 1)
    return indice - 1


def _letra_desde_indice(indice: int) -> str:
    letras = ""
    indice += 1
    while indice > 0:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(ord("A") + resto) + letras
    return letras


def _celdas_en_rango(inicio: str, fin: str) -> list[str]:
    """Todas las direcciones del rectángulo entre `inicio` y `fin`
    (cualquiera de los dos puede ser la esquina "menor"), en orden de
    fila y luego columna — el orden no afecta la suma, solo importa
    que la lista sea siempre la misma para el mismo rango."""
    col_inicio, fila_inicio = _PATRON_DIRECCION.match(inicio).groups()
    col_fin, fila_fin = _PATRON_DIRECCION.match(fin).groups()
    col_min, col_max = sorted((_indice_columna(col_inicio), _indice_columna(col_fin)))
    fila_min, fila_max = sorted((int(fila_inicio), int(fila_fin)))
    return [
        f"{_letra_desde_indice(columna)}{fila}"
        for fila in range(fila_min, fila_max + 1)
        for columna in range(col_min, col_max + 1)
    ]


def _es_formula(contenido: str) -> bool:
    return contenido.startswith(_PREFIJOS_FORMULA)


def _expresion_formula(contenido: str) -> str:
    """El "=" no es un operador válido, así que se descarta antes de
    evaluar — el "+" sí lo es (suma unaria), se deja tal cual."""
    return contenido[1:] if contenido.startswith("=") else contenido


class ErrorFormula(Exception):
    """Fórmula inválida o con referencia circular — el llamador (GUI)
    muestra "#ERROR"/"#CICLO" en la celda en vez de romper el resto de
    la planilla."""


def valor_celda(
    celdas: dict[str, str], id_celda: str, _visitando: frozenset[str] = frozenset(),
) -> float | None:
    """Valor numérico de `id_celda` dado el contenido crudo de todas las
    celdas (`celdas`, dirección -> texto tal cual lo tipeó la clienta).
    `None` es una celda vacía o con texto no numérico — no es un error,
    una fórmula que la referencia la trata como 0 (pedido implícito de
    "simple": una celda de nota suelta no tiene que romper ninguna
    cuenta de otra celda)."""
    if id_celda in _visitando:
        raise ErrorFormula(f"Referencia circular en {id_celda}")
    contenido = (celdas.get(id_celda) or "").strip()
    if not contenido:
        return None
    if not _es_formula(contenido):
        try:
            return float(contenido.replace(",", "."))
        except ValueError:
            return None
    return _evaluar_formula(celdas, _expresion_formula(contenido), _visitando | {id_celda})


def _evaluar_formula(celdas: dict[str, str], formula: str, visitando: frozenset[str]) -> float:
    def _reemplazar_rango(coincidencia: re.Match) -> str:
        referencias = _celdas_en_rango(coincidencia.group(1), coincidencia.group(2))
        total = sum((valor_celda(celdas, ref, visitando) or 0.0) for ref in referencias)
        return repr(total)

    def _reemplazar(coincidencia: re.Match) -> str:
        valor = valor_celda(celdas, coincidencia.group().upper(), visitando)
        return repr(valor if valor is not None else 0.0)

    formula_mayus = _PATRON_RANGO.sub(_reemplazar_rango, formula.upper())
    expresion = _PATRON_CELDA.sub(_reemplazar, formula_mayus)
    if not expresion.strip() or any(c not in _CARACTERES_FORMULA_VALIDOS for c in expresion):
        raise ErrorFormula("Fórmula inválida")
    try:
        resultado = eval(expresion, {"__builtins__": {}}, {})  # noqa: S307 (whitelist de caracteres arriba)
    except (SyntaxError, ZeroDivisionError, ArithmeticError, TypeError):
        raise ErrorFormula("Fórmula inválida") from None
    if isinstance(resultado, bool) or not isinstance(resultado, (int, float)):
        raise ErrorFormula("Fórmula inválida")
    return float(resultado)


def texto_resultado_celda(celdas: dict[str, str], id_celda: str) -> str:
    """Lo que la grilla muestra para `id_celda`: el resultado de la
    fórmula (celdas con "="), o el contenido tal cual se tipeó (notas y
    números sueltos, sin fórmula) — el formato de miles/2 decimales lo
    aplica aparte la GUI, solo para celdas marcadas con ese estilo."""
    contenido = celdas.get(id_celda) or ""
    if not _es_formula(contenido.strip()):
        return contenido
    try:
        resultado = valor_celda(celdas, id_celda)
    except ErrorFormula:
        return "#ERROR"
    return _formato_general(resultado if resultado is not None else 0.0)


def _formato_general(valor: float) -> str:
    """Sin la coma/separador de miles de `formatear_miles` (eso es el
    estilo opcional "Formato número") — el resultado crudo de una
    fórmula, sin ceros de más (ej. "4" en vez de "4.0")."""
    return f"{valor:g}"


def formatear_miles(valor: float) -> str:
    """"Formato de números de dos decimales y separador de miles" (pedido
    explícito) — mismo esquema (punto de miles, coma decimal) que
    `app.negocio.formato.formatear_moneda`, sin el "$" (acá no es
    necesariamente un importe)."""
    return f"{valor:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def leer_celdas(conn: sqlite3.Connection) -> dict[str, dict]:
    filas = conn.execute(
        "SELECT IdCelda, Contenido, Negrita, ColorTexto, ColorFondo, FormatoNumero, Alineacion FROM CeldaPlanilla"
    ).fetchall()
    return {
        f["IdCelda"]: {
            "contenido": f["Contenido"] or "",
            "negrita": bool(f["Negrita"]),
            "color_texto": f["ColorTexto"],
            "color_fondo": f["ColorFondo"],
            "formato_numero": bool(f["FormatoNumero"]),
            "alineacion": f["Alineacion"],
        }
        for f in filas
    }


def guardar_celda(
    conn: sqlite3.Connection, id_celda: str, *, contenido: str = "", negrita: bool = False,
    color_texto: str | None = None, color_fondo: str | None = None, formato_numero: bool = False,
    alineacion: str | None = None,
) -> None:
    """Sin contenido ni ningún estilo propio, la celda no necesita fila
    (ver docstring del módulo) — se borra en vez de guardar una fila en
    blanco, mismo criterio que `plantillas_texto.guardar_texto_
    personalizado`. `alineacion` es "izquierda"/"centro"/"derecha" o
    `None` (sin override — la GUI decide un default según si la celda
    resuelve a un número o no, ver `app.gui.widgets.planilla_flotante`)."""
    vacia = (
        not contenido and not negrita and color_texto is None and color_fondo is None
        and not formato_numero and alineacion is None
    )
    if vacia:
        conn.execute("DELETE FROM CeldaPlanilla WHERE IdCelda = ?", (id_celda,))
    else:
        conn.execute(
            """
            INSERT INTO CeldaPlanilla
                (IdCelda, Contenido, Negrita, ColorTexto, ColorFondo, FormatoNumero, Alineacion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(IdCelda) DO UPDATE SET
                Contenido = excluded.Contenido, Negrita = excluded.Negrita, ColorTexto = excluded.ColorTexto,
                ColorFondo = excluded.ColorFondo, FormatoNumero = excluded.FormatoNumero,
                Alineacion = excluded.Alineacion
            """,
            (id_celda, contenido, int(negrita), color_texto, color_fondo, int(formato_numero), alineacion),
        )
    conn.commit()


def vaciar_todo(conn: sqlite3.Connection) -> None:
    """"Que las pueda borrar cuando yo quiera" — vacía la planilla
    entera de una, pedido explícito distinto de borrar una celda
    puntual (que ya resuelve sola `guardar_celda` con contenido vacío)."""
    conn.execute("DELETE FROM CeldaPlanilla")
    conn.commit()
