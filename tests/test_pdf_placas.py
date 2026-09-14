import fitz
import pytest
from reportlab.lib.units import cm

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.pdf.placas_pdf import (
    ALTO_PLACA,
    ANCHO_PLACA,
    MARGEN_INTERNO_PLACA,
    TAMANO_FUENTE_PLACA,
    _altura_necesaria,
    _caja_placa,
    generar_pdf_placas,
    generar_pdf_placas_seleccionadas,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A", localidad=None):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre=nombre_edificio, DomicilioLocalidad=localidad)
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=departamento)
    return id_edificio, id_unidad


def test_sin_placas_avisa_y_genera_pdf_valido(conn, tmp_path):
    ruta = generar_pdf_placas(conn, str(tmp_path))
    assert ruta.endswith("Placas Espacio Ramos.pdf")
    texto = fitz.open(ruta)[0].get_text()
    assert "No hay placas activas cargadas." in texto


def test_lista_placas_activas_ordenadas_por_posicion(conn, tmp_path):
    _, id_unidad = _crear_unidad(conn)
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad, PosicionTablero=2, NombreGrabado="Lic. Pérez")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad, PosicionTablero=1, NombreGrabado="Dr. Gómez")

    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()

    assert texto.index("Dr. Gómez") < texto.index("Lic. Pérez")


def test_placa_inactiva_no_aparece(conn, tmp_path):
    _, id_unidad = _crear_unidad(conn)
    obtener_repositorio(conn, "Placa").crear(
        IdUnidad=id_unidad, PosicionTablero=1, NombreGrabado="Dado de baja", Activo=0,
    )
    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "Dado de baja" not in texto


def test_placa_sin_nombre_muestra_placeholder(conn, tmp_path):
    _, id_unidad = _crear_unidad(conn)
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad, PosicionTablero=1)
    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "(sin nombre cargado)" in texto


def test_placa_personalizada_se_marca(conn, tmp_path):
    _, id_unidad = _crear_unidad(conn)
    obtener_repositorio(conn, "Placa").crear(
        IdUnidad=id_unidad, PosicionTablero=1, NombreGrabado="Dr. Gómez", EsPersonalizada=1,
    )
    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "Dr. Gómez (personalizada)" in texto


def test_unidad_sin_placas_no_aparece(conn, tmp_path):
    id_edificio, id_unidad_con = _crear_unidad(conn, departamento="1ro A")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad_con, PosicionTablero=1, NombreGrabado="Con placa")
    obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="Vacía")  # sin placas

    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "Vacía" not in texto


def test_muestra_edificio_cuando_hay_mas_de_uno(conn, tmp_path):
    _, id_unidad1 = _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A")
    _, id_unidad2 = _crear_unidad(conn, nombre_edificio="Ramos 2", departamento="2do B")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad1, PosicionTablero=1, NombreGrabado="Uno")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad2, PosicionTablero=1, NombreGrabado="Dos")

    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "Ramos 1 - 1ro A" in texto
    assert "Ramos 2 - 2do B" in texto


def test_un_solo_edificio_no_repite_nombre(conn, tmp_path):
    _, id_unidad = _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad, PosicionTablero=1, NombreGrabado="Único")

    ruta = generar_pdf_placas(conn, str(tmp_path))
    texto = fitz.open(ruta)[0].get_text()
    assert "Ramos 1 - 1ro A" not in texto
    assert "1ro A" in texto


def test_filtra_por_ids_edificio(conn, tmp_path):
    id_edificio1, id_unidad1 = _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A")
    _, id_unidad2 = _crear_unidad(conn, nombre_edificio="Ramos 2", departamento="2do B")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad1, PosicionTablero=1, NombreGrabado="Uno")
    obtener_repositorio(conn, "Placa").crear(IdUnidad=id_unidad2, PosicionTablero=1, NombreGrabado="Dos")

    ruta = generar_pdf_placas(conn, str(tmp_path), ids_edificio=[id_edificio1])
    texto = fitz.open(ruta)[0].get_text()
    assert "Uno" in texto
    assert "Dos" not in texto


def _crear_profesional(conn, apellido="Lo Veci", nombre_pila="Virginia", tratamiento="Lic."):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido=apellido, NombrePila=nombre_pila, Tratamiento=tratamiento,
    )


def _entrada(id_profesional, linea1=None, linea2=None):
    return {"id_profesional": id_profesional, "linea1": linea1, "linea2": linea2}


def test_seleccionadas_sin_entradas_lanza_error(conn, tmp_path):
    with pytest.raises(ValueError):
        generar_pdf_placas_seleccionadas(conn, str(tmp_path), [])


def test_seleccionadas_genera_una_celda_por_profesional(conn, tmp_path):
    id_1 = _crear_profesional(conn, apellido="Lo Veci")
    id_2 = _crear_profesional(conn, apellido="Gómez", nombre_pila="Martín", tratamiento="Dr.")

    ruta = generar_pdf_placas_seleccionadas(conn, str(tmp_path), [_entrada(id_1), _entrada(id_2)])

    assert ruta.endswith(".pdf")
    assert "Placas para imprimir" in ruta
    texto = fitz.open(ruta)[0].get_text()
    assert "Lic. Virginia Lo Veci" in texto
    assert "Dr. Martín Gómez" in texto


def test_seleccionadas_ignora_entradas_de_profesionales_inexistentes(conn, tmp_path):
    id_1 = _crear_profesional(conn)
    ruta = generar_pdf_placas_seleccionadas(conn, str(tmp_path), [_entrada(id_1), _entrada(99999)])
    texto = fitz.open(ruta)[0].get_text()
    assert "Lic. Virginia Lo Veci" in texto


def test_seleccionadas_paginan_22_por_hoja(conn, tmp_path):
    entradas = [_entrada(_crear_profesional(conn, apellido=f"Apellido{i}")) for i in range(25)]

    ruta = generar_pdf_placas_seleccionadas(conn, str(tmp_path), entradas)

    documento = fitz.open(ruta)
    assert documento.page_count == 2
    assert documento[0].get_text().count("Apellido") == 22
    assert documento[1].get_text().count("Apellido") == 3


def test_seleccionadas_personalizada_usa_las_lineas_cargadas(conn, tmp_path):
    id_1 = _crear_profesional(conn, apellido="Pugliese", nombre_pila="Silvina")

    ruta = generar_pdf_placas_seleccionadas(
        conn, str(tmp_path), [_entrada(id_1, linea1="Lic. Silvina Pugliese", linea2='Equipo "Sol terapias"')],
    )

    texto = fitz.open(ruta)[0].get_text()
    assert "Lic. Silvina Pugliese" in texto
    # la fuente sustituta de Calibri es más ancha, así que "Equipo "Sol
    # terapias"" puede no entrar en una sola línea — igual tiene que
    # aparecer completo, sin cortar palabras.
    assert "Equipo" in texto and "Sol" in texto and "terapias" in texto
    assert "Lic. Silvina Pugliese Lo Veci" not in texto  # no mezcla con el nombre estándar del profesional


def test_seleccionadas_sin_personalizar_usa_el_nombre_estandar(conn, tmp_path):
    id_1 = _crear_profesional(conn, apellido="Difalco", nombre_pila="Sol")
    ruta = generar_pdf_placas_seleccionadas(conn, str(tmp_path), [_entrada(id_1)])
    texto = fitz.open(ruta)[0].get_text()
    assert "Lic. Sol Difalco" in texto


def test_medidas_de_la_placa_son_las_del_modelo_fisico():
    """Modelo pasado por la clienta: 7,6 cm x 2,2 cm, margen interno 0,3
    cm, fuente a 20pt (Calibri pedido, sustituida por Helvetica-
    BoldOblique — ver docstring del módulo)."""
    assert ANCHO_PLACA == pytest.approx(7.6 * cm)
    assert ALTO_PLACA == pytest.approx(2.2 * cm)
    assert MARGEN_INTERNO_PLACA == pytest.approx(0.3 * cm)
    assert TAMANO_FUENTE_PLACA == 20


def test_altura_crece_si_el_texto_no_entra_en_el_alto_de_placa():
    """Una placa personalizada larga (ej. "Equipo \"Sol terapias\"" en la
    fuente sustituta, más ancha que la Calibri pedida) no se recorta
    contra el borde: la fila crece en vez de solaparse."""
    corta = _caja_placa("Lic. Sol Difalco")
    larga = _caja_placa("Lic. Silvina Pugliese\nEquipo \"Sol terapias\" con un texto bien largo para forzar el ajuste")
    assert _altura_necesaria(corta) < ALTO_PLACA
    assert _altura_necesaria(larga) > ALTO_PLACA
