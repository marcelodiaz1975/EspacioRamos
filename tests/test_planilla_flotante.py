import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.planilla_flotante import (
    ErrorFormula,
    formatear_miles,
    guardar_celda,
    leer_celdas,
    texto_resultado_celda,
    vaciar_todo,
    valor_celda,
)


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


# ------------------------------------------------------------------------------- valor_celda

def test_valor_celda_vacia_es_none():
    assert valor_celda({}, "A1") is None


def test_valor_celda_numero_sin_formula():
    assert valor_celda({"A1": "10"}, "A1") == 10.0


def test_valor_celda_acepta_coma_decimal():
    assert valor_celda({"A1": "10,5"}, "A1") == 10.5


def test_valor_celda_texto_sin_formula_es_none():
    """Una nota suelta (sin "=") nunca es fórmula, aunque el texto
    parezca una cuenta — es justo lo que permite anotar sin que el
    sistema intente calcular."""
    assert valor_celda({"A1": "10+5"}, "A1") is None


def test_valor_celda_formula_basica():
    assert valor_celda({"A1": "=2+3*4"}, "A1") == 14.0


def test_valor_celda_formula_referencia_otra_celda():
    assert valor_celda({"A1": "10", "A2": "=A1*2"}, "A2") == 20.0


def test_valor_celda_formula_referencia_en_cadena():
    celdas = {"A1": "10", "A2": "=A1+5", "A3": "=A2*2"}
    assert valor_celda(celdas, "A3") == 30.0


def test_valor_celda_referencia_a_celda_vacia_la_trata_como_cero():
    assert valor_celda({"A1": "=A2+5"}, "A1") == 5.0


def test_valor_celda_referencia_a_texto_lo_trata_como_cero():
    assert valor_celda({"A1": "Hola", "A2": "=A1+5"}, "A2") == 5.0


def test_valor_celda_formula_invalida_levanta_error_formula():
    with pytest.raises(ErrorFormula):
        valor_celda({"A1": "=2+"}, "A1")


def test_valor_celda_division_por_cero_levanta_error_formula():
    with pytest.raises(ErrorFormula):
        valor_celda({"A1": "=5/0"}, "A1")


def test_valor_celda_no_ejecuta_codigo_arbitrario():
    """Confirma que la fórmula no puede escapar a nada fuera de
    dígitos/operadores/paréntesis (mismo criterio que la vieja
    calculadora) — cualquier otro caracter la invalida."""
    with pytest.raises(ErrorFormula):
        valor_celda({"A1": "=__import__('os')"}, "A1")


def test_valor_celda_autoreferencia_es_ciclo():
    with pytest.raises(ErrorFormula):
        valor_celda({"A1": "=A1+1"}, "A1")


def test_valor_celda_ciclo_entre_dos_celdas():
    with pytest.raises(ErrorFormula):
        valor_celda({"A1": "=A2+1", "A2": "=A1+1"}, "A1")


# --------------------------------------------------------------- "+" sinónimo de "=" (#131)

def test_valor_celda_mas_al_principio_es_sinonimo_de_formula():
    """Pedido explícito: "poner '+C2+C3' sea lo mismo que '=C2+C3'"."""
    celdas = {"C2": "10", "C3": "20", "A1": "+C2+C3"}
    assert valor_celda(celdas, "A1") == 30.0


def test_valor_celda_mas_solo_tambien_es_formula():
    assert valor_celda({"A1": "+5"}, "A1") == 5.0


def test_valor_celda_menos_al_principio_no_es_formula():
    """"-" a propósito NO es sinónimo — un número negativo suelto
    (ej. "-500") sigue siendo una nota/número, no una fórmula."""
    assert valor_celda({"A1": "-500"}, "A1") == -500.0


# ------------------------------------------------------------------- texto_resultado_celda

def test_texto_resultado_celda_sin_formula_devuelve_tal_cual():
    assert texto_resultado_celda({"A1": "Nota suelta"}, "A1") == "Nota suelta"


def test_texto_resultado_celda_formula_sin_decimales_de_mas():
    assert texto_resultado_celda({"A1": "=4/2"}, "A1") == "2"


def test_texto_resultado_celda_formula_con_decimales():
    assert texto_resultado_celda({"A1": "=1/4"}, "A1") == "0.25"


def test_texto_resultado_celda_formula_invalida_muestra_error():
    assert texto_resultado_celda({"A1": "=5/0"}, "A1") == "#ERROR"


def test_texto_resultado_celda_ciclo_muestra_error():
    assert texto_resultado_celda({"A1": "=A1+1"}, "A1") == "#ERROR"


def test_texto_resultado_celda_con_mas_calcula_igual_que_con_igual():
    celdas = {"C2": "10", "C3": "20", "A1": "+C2+C3"}
    assert texto_resultado_celda(celdas, "A1") == "30"


# ------------------------------------------------------------------------- formatear_miles

def test_formatear_miles_separador_de_miles_y_dos_decimales():
    assert formatear_miles(1234.5) == "1.234,50"


def test_formatear_miles_numero_negativo():
    assert formatear_miles(-1234567.891) == "-1.234.567,89"


# -------------------------------------------------------------------------- persistencia

def test_leer_celdas_sin_nada_guardado_devuelve_vacio(conn):
    assert leer_celdas(conn) == {}


def test_guardar_y_leer_celda_con_contenido_y_estilo(conn):
    guardar_celda(
        conn, "A1", contenido="=1+1", negrita=True, color_texto="#ff0000", color_fondo="#ffff00",
        formato_numero=True, alineacion="centro",
    )
    celdas = leer_celdas(conn)
    assert celdas["A1"] == {
        "contenido": "=1+1", "negrita": True, "color_texto": "#ff0000", "color_fondo": "#ffff00",
        "formato_numero": True, "alineacion": "centro",
    }


def test_guardar_celda_vacia_pero_con_alineacion_si_deja_fila(conn):
    guardar_celda(conn, "A1", contenido="", alineacion="derecha")
    celdas = leer_celdas(conn)
    assert celdas["A1"]["alineacion"] == "derecha"


def test_guardar_celda_vacia_sin_estilo_no_deja_fila(conn):
    guardar_celda(conn, "A1", contenido="algo")
    guardar_celda(conn, "A1", contenido="")
    assert leer_celdas(conn) == {}


def test_guardar_celda_vacia_pero_con_estilo_si_deja_fila(conn):
    """Una celda sin contenido pero con, por ejemplo, color de relleno
    (resaltar una celda vacía a propósito) sigue necesitando su fila."""
    guardar_celda(conn, "A1", contenido="", color_fondo="#00ff00")
    celdas = leer_celdas(conn)
    assert celdas["A1"]["color_fondo"] == "#00ff00"


def test_guardar_celda_dos_veces_actualiza_la_misma_fila(conn):
    guardar_celda(conn, "A1", contenido="10")
    guardar_celda(conn, "A1", contenido="20")
    celdas = leer_celdas(conn)
    assert len(celdas) == 1
    assert celdas["A1"]["contenido"] == "20"


def test_vaciar_todo_borra_todas_las_celdas(conn):
    guardar_celda(conn, "A1", contenido="10")
    guardar_celda(conn, "B2", contenido="20", negrita=True)
    vaciar_todo(conn)
    assert leer_celdas(conn) == {}
