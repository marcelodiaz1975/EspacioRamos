import pytest
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph, Table

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.pdf.estilos import COLOR_NIVEL_1, FUENTE, FUENTE_NEGRITA
from app.pdf.grilla_pdf import (
    DIAS_GRILLA_DEFAULT,
    _partir_etiqueta_unidad,
    _tabla_grilla_edificio,
    _tabla_grilla_edificio_girada,
    _tamano_que_entra,
    altura_estimada_grilla,
    secciones_disponibilidad,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _unidades_ficticias(n):
    return [{"IdUnidad": i, "Departamento": f'{i}no "X"'} for i in range(1, n + 1)]


def test_etiquetas_de_unidad_no_se_truncan_con_muchas_unidades(conn):
    """Regresión: con muchas unidades por edificio (4+, como pasa con datos
    reales) la columna por consultorio se vuelve angosta — antes del fix la
    etiqueta iba como texto plano y se desbordaba sobre la celda vecina,
    mezclando el contenido de columnas adyacentes en la fila de encabezado
    (ver sesión de revisión con datos reales, edificio con 4 unidades)."""
    unidades = _unidades_ficticias(4)
    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=[9, 10], ancho=500)

    fila_piso = tabla._cellvalues[2][2:]  # las primeras 2 columnas son Tipo/Horario, vacías en esta fila
    fila_letra = tabla._cellvalues[3][2:]
    assert len(fila_piso) == 6 * len(unidades)  # 6 días x 4 unidades

    esperado = [_partir_etiqueta_unidad(u["Departamento"]) for _ in range(6) for u in unidades]
    obtenido = list(zip(
        [c.getPlainText() if isinstance(c, Paragraph) else c for c in fila_piso],
        [c.getPlainText() if isinstance(c, Paragraph) else c for c in fila_letra],
    ))
    assert obtenido == esperado


def test_etiquetas_de_unidad_son_paragraph_para_poder_ajustar(conn):
    """Un texto plano en una celda angosta de reportlab no ajusta ni
    envuelve — tiene que ser un Paragraph para poder partirse en líneas en
    vez de desbordar sobre la celda vecina."""
    unidades = _unidades_ficticias(5)
    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=[9], ancho=400)
    assert all(isinstance(c, Paragraph) for c in tabla._cellvalues[2][2:])
    assert all(isinstance(c, Paragraph) for c in tabla._cellvalues[3][2:])


def test_una_sola_unidad_no_rompe(conn):
    unidades = _unidades_ficticias(1)
    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=[9], ancho=500)
    assert [c.getPlainText() for c in tabla._cellvalues[2][2:]] == ["1"] * 6
    assert [c.getPlainText() for c in tabla._cellvalues[3][2:]] == ["X"] * 6


def test_grilla_edificio_real_conserva_columnas(conn):
    """Reproduce el caso real que disparó el bug: un edificio con 4
    unidades importado desde planilla — cada columna conserva su propia
    etiqueta (piso arriba, letra abajo, sin comillas, cada una en su
    propia fila) en vez de mezclarse con la de al lado."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    nombres = ['15 "H"', '7mo "L"', '9no "C"', 'EP "K"']
    esperado_piso = ["15", "7", "9", "EP"]
    esperado_letra = ["H", "L", "C", "K"]
    unidades = []
    for nombre in nombres:
        id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=nombre)
        unidades.append({"IdUnidad": id_unidad, "Departamento": nombre})

    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=list(range(9, 21)), ancho=550)
    obtenido_piso = [c.getPlainText() for c in tabla._cellvalues[2][2:2 + len(nombres)]]
    obtenido_letra = [c.getPlainText() for c in tabla._cellvalues[3][2:2 + len(nombres)]]
    assert obtenido_piso == esperado_piso
    assert obtenido_letra == esperado_letra


def test_partir_etiqueta_unidad_numero_de_piso_y_letra():
    assert _partir_etiqueta_unidad('7mo "L"') == ("7", "L")
    assert _partir_etiqueta_unidad('EP "K"') == ("EP", "K")
    assert _partir_etiqueta_unidad('15 "H"') == ("15", "H")
    assert _partir_etiqueta_unidad('9no "C"') == ("9", "C")
    assert _partir_etiqueta_unidad('3ero "B"') == ("3", "B")


def test_tamano_que_entra_no_parte_el_texto_a_mitad_de_palabra():
    """Regresión: con columnas angostas (7 unidades x 6 días es habitual en
    datos reales) y una fuente fija más grande, "15"/"EP" se envolvían en
    "1"/"5" y "E"/"P" a mitad de palabra — peor que un texto más chico
    pero legible en una sola línea."""
    ancho_columna_angosta = 11  # el caso real que disparó el bug
    tamano = _tamano_que_entra(["15", "EP", "7", "9"], ancho_columna_angosta)
    assert stringWidth("15", FUENTE_NEGRITA, tamano) <= ancho_columna_angosta * 0.85


def test_tamano_que_entra_usa_el_maximo_si_hay_lugar():
    assert _tamano_que_entra(["7"], ancho_disponible=200, tamano_max=10) == 10


def test_grilla_con_columnas_angostas_no_envuelve_el_piso(conn):
    """Con 7 unidades reales (varias de 2 dígitos/letras, ej. "15"/"EP")
    en un ancho chico, cada celda del piso tiene que quedar en una sola
    línea de texto — no partida en dos como "1"/"5"."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    nombres = ['15 "H"', '7mo "L"', '9no "C"', 'EP "K"', '3ero "B"', 'PB "D"', '1ro "A"']
    unidades = []
    for nombre in nombres:
        id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=nombre)
        unidades.append({"IdUnidad": id_unidad, "Departamento": nombre})

    ancho_total = 550
    n_unidades = len(unidades)
    ancho_col = (ancho_total - ancho_total * 0.14) / (6 * n_unidades)  # misma cuenta que _tabla_grilla_edificio

    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=[9], ancho=ancho_total)
    fila_piso = tabla._cellvalues[2][2:2 + n_unidades]
    for celda in fila_piso:
        celda.wrap(ancho_col - 2, 1000)  # -2: LEFTPADDING+RIGHTPADDING de la celda (1pt cada uno)
        assert len(celda.blPara.lines) == 1, f"'{celda.getPlainText()}' se partió en {len(celda.blPara.lines)} líneas"


def test_partir_etiqueta_unidad_formato_inesperado_no_rompe():
    assert _partir_etiqueta_unidad("Consultorio único") == ("Consultorio único", "")


def test_tamano_que_entra_mide_con_la_fuente_indicada():
    """Con una fuente angosta (no negrita) entra un tamaño más grande que
    con la negrita en el mismo ancho — la medición tiene que usar la
    fuente real de dibujo, no una fija."""
    ancho = stringWidth("EP", FUENTE_NEGRITA, 8) / 0.85 + 0.5
    tamano_negrita = _tamano_que_entra(["EP"], ancho, tamano_max=8, fuente=FUENTE_NEGRITA)
    tamano_regular = _tamano_que_entra(["EP"], ancho, tamano_max=8, fuente=FUENTE)
    assert tamano_regular >= tamano_negrita


def test_piso_y_letra_son_blancos_sin_negrita(conn):
    unidades = _unidades_ficticias(2)
    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=[9], ancho=400)
    celda_piso = tabla._cellvalues[2][2]
    assert celda_piso.style.fontName == FUENTE
    assert celda_piso.style.textColor == colors.white


def test_divisor_piso_letra_es_del_mismo_azul_que_el_fondo(conn):
    unidades = _unidades_ficticias(2)
    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=[9], ancho=400)
    lineas = [cmd for cmd in tabla._linecmds if cmd[0] == "LINEBELOW" and cmd[1][1] == 2]
    assert lineas, "no se encontró el LINEBELOW de la fila de piso"
    assert lineas[0][4] == COLOR_NIVEL_1


def test_dia_de_la_semana_usa_el_mismo_azul_y_fuente_mas_grande(conn):
    """El fondo del día de la semana va del mismo azul que el resto de la
    grilla (COLOR_NIVEL_1) — no un color aparte — pero mantiene la fuente
    más grande auto-ajustada."""
    unidades = _unidades_ficticias(2)
    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=[9], ancho=400)
    colores_fila_dia = {cmd[3] for cmd in tabla._bkgrndcmds if cmd[1] == (2, 0)}
    assert colores_fila_dia == {COLOR_NIVEL_1}

    tamano_dia = tabla._cellStyles[0][2].fontsize
    assert tamano_dia > 6  # más grande que el tamaño base de la grilla (6)


def test_fila_unidad_en_mayusculas(conn):
    unidades = _unidades_ficticias(2)
    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=[9], ancho=400)
    assert tabla._cellvalues[1][2] == "UNIDAD"


def test_sv_tiene_fuente_autoajustable(conn):
    """Con muchas unidades (columnas angostas) el tamaño de "S/V" tiene que
    reducirse para no desbordar la celda."""
    unidades_pocas = _unidades_ficticias(1)
    unidades_muchas = _unidades_ficticias(8)
    tabla_ancha = _tabla_grilla_edificio(conn, unidades_pocas, grilla={}, horas=[9], ancho=500)
    tabla_angosta = _tabla_grilla_edificio(conn, unidades_muchas, grilla={}, horas=[9], ancho=500)

    assert tabla_angosta._cellStyles[4][2].fontsize <= tabla_ancha._cellStyles[4][2].fontsize


# ---------------------------------------------------------------- grilla girada

def test_grilla_girada_tiene_las_dimensiones_esperadas(conn):
    n_unidades, horas = 10, [9, 10, 11]
    unidades = _unidades_ficticias(n_unidades)
    tabla = _tabla_grilla_edificio_girada(conn, unidades, grilla={}, horas=horas, ancho=550)

    n_dias = len(DIAS_GRILLA_DEFAULT)
    assert len(tabla._cellvalues) == 2 + n_dias * n_unidades  # 2 filas de encabezado + día x unidad
    assert len(tabla._cellvalues[0]) == 3 + len(horas)  # Día/Piso/Depto. + una columna por hora


def test_grilla_girada_conserva_piso_y_letra_por_fila(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    nombres = ['15 "H"', '7mo "L"', '9no "C"']
    unidades = []
    for nombre in nombres:
        id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=nombre)
        unidades.append({"IdUnidad": id_unidad, "Departamento": nombre})

    tabla = _tabla_grilla_edificio_girada(conn, unidades, grilla={}, horas=[9], ancho=550)
    primeras_filas = tabla._cellvalues[2:2 + len(unidades)]
    obtenido = [(f[1].getPlainText(), f[2].getPlainText()) for f in primeras_filas]
    assert obtenido == [("15", "H"), ("7", "L"), ("9", "C")]


def test_grilla_girada_el_dia_abarca_todas_las_filas_de_sus_unidades(conn):
    unidades = _unidades_ficticias(3)
    tabla = _tabla_grilla_edificio_girada(conn, unidades, grilla={}, horas=[9], ancho=550)
    spans_dia = [cmd for cmd in tabla._spanCmds if cmd[1][0] == 0 and cmd[1][1] >= 2]
    # un SPAN de columna 0 por cada día, cubriendo sus 3 filas de unidades
    assert len(spans_dia) == len(DIAS_GRILLA_DEFAULT)
    assert all(fin[1] - ini[1] == len(unidades) - 1 for _, ini, fin in spans_dia)


def test_secciones_disponibilidad_usa_grilla_girada_al_superar_el_umbral(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    for i in range(5):
        obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=f'{i + 1}ro "A"')
    obtener_repositorio(conn, "Configuracion").actualizar(1, UmbralGiroGrilla=3)

    story = secciones_disponibilidad(conn, 2026, 8, ancho=550, fecha_titulo="12-08-2026")
    tablas_grilla = [f for f in story[2]._content if isinstance(f, Table) and len(f._cellvalues) > 2]
    assert len(tablas_grilla) == 1
    # girada: repeatRows=2 (Día/Piso/Depto. arriba); sin girar sería 4.
    assert tablas_grilla[0].repeatRows == 2


def test_altura_estimada_grilla_crece_mas_con_grilla_girada(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    for i in range(3):
        obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=f'{i + 1}ro "A"')
    obtener_repositorio(conn, "Configuracion").actualizar(1, UmbralGiroGrilla=2)
    altura_girada = altura_estimada_grilla(conn, [id_edificio])

    obtener_repositorio(conn, "Configuracion").actualizar(1, UmbralGiroGrilla=10)
    altura_normal = altura_estimada_grilla(conn, [id_edificio])

    assert altura_girada > altura_normal
