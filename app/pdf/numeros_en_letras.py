"""Conversión de un monto a su expresión en letras (para el total del PDF
de liquidación, sección 4.5: "importe en letras der línea 2 dentro del
recuadro"). Formato moneda en español (Argentina), género masculino
("pesos")."""
from __future__ import annotations

_UNIDADES = [
    "", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
    "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete",
    "dieciocho", "diecinueve", "veinte",
]
_DECENAS = {
    30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta",
    70: "setenta", 80: "ochenta", 90: "noventa",
}
_CENTENAS = {
    100: "cien", 200: "doscientos", 300: "trescientos", 400: "cuatrocientos",
    500: "quinientos", 600: "seiscientos", 700: "setecientos",
    800: "ochocientos", 900: "novecientos",
}


_VEINTI_ACENTUADOS = {2: "veintidós", 3: "veintitrés", 6: "veintiséis"}


def _menor_a_cien(n: int) -> str:
    if n <= 20:
        return _UNIDADES[n]
    decena = (n // 10) * 10
    resto = n % 10
    if decena == 20:
        if resto == 0:
            return "veinte"
        return _VEINTI_ACENTUADOS.get(resto, "veinti" + _UNIDADES[resto])
    texto = _DECENAS[decena]
    return f"{texto} y {_UNIDADES[resto]}" if resto else texto


def _menor_a_mil(n: int) -> str:
    if n < 100:
        return _menor_a_cien(n)
    centena = (n // 100) * 100
    resto = n % 100
    if centena == 100:
        texto = "cien" if resto == 0 else "ciento"
    else:
        texto = _CENTENAS[centena]
    return f"{texto} {_menor_a_cien(resto)}" if resto else texto


def _apocope(texto: str) -> str:
    """"uno" pierde la 'o' final delante de "mil"/"millones": "veintiuno" ->
    "veintiún", "treinta y uno" -> "treinta y un" (pero como cifra final,
    sin nada detrás, se deja "uno"/"veintiuno" completo)."""
    if texto.endswith("iuno"):
        return texto[:-4] + "iún"
    if texto == "uno":
        return "un"
    if texto.endswith(" uno"):
        return texto[:-4] + " un"
    return texto


def _entero_en_letras(n: int) -> str:
    if n == 0:
        return "cero"
    partes = []
    millones, resto = divmod(n, 1_000_000)
    if millones:
        if millones == 1:
            partes.append("un millón")
        else:
            partes.append(f"{_apocope(_entero_en_letras(millones))} millones")
    miles, resto = divmod(resto, 1000)
    if miles:
        partes.append("mil" if miles == 1 else f"{_apocope(_menor_a_mil(miles))} mil")
    if resto:
        partes.append(_menor_a_mil(resto))
    return " ".join(partes)


def monto_en_letras(monto: float) -> str:
    """'Pesos cuarenta y cinco mil seiscientos setenta y ocho con 50/100'."""
    negativo = monto < 0
    entero = int(abs(monto) // 1)
    centavos = round((abs(monto) - entero) * 100)
    if centavos == 100:
        entero += 1
        centavos = 0
    texto = f"Pesos {_entero_en_letras(entero)} con {centavos:02d}/100"
    texto = texto[0].upper() + texto[1:]
    return f"Menos {texto[0].lower()}{texto[1:]}" if negativo else texto
