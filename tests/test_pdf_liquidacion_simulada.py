import fitz
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.liquidacion_simulada import BloqueSimulado, calcular_liquidacion_simulada
from app.pdf.liquidacion_simulada_pdf import generar_pdf_liquidacion_simulada, nombre_archivo_liquidacion_simulada
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def profesional(conn):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Tratamiento="Dra.", NombrePila="Virginia", Apellido="Lo Veci", IdCodigo="R9",
    )


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="7mo L")
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )


def test_nombre_archivo_sigue_el_formato_pedido(conn, profesional):
    fila = obtener_repositorio(conn, "Profesional").obtener(profesional)
    assert nombre_archivo_liquidacion_simulada("2026-11", fila) == "2026-11 - Liquidación simulada Dra. Virginia Lo Veci.pdf"


def test_genera_pdf_con_los_bloques_y_el_total(conn, profesional, consultorio, tmp_path):
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])

    ruta = generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))
    assert ruta.endswith("2026-11 - Liquidación simulada Dra. Virginia Lo Veci.pdf")

    texto = "".join(pagina.get_text() for pagina in fitz.open(ruta))
    assert "Liquidación simulada" in texto
    assert "Lunes" in texto
    assert "9hs a 11hs" in texto
    assert "consul 1 del 7mo L - Ramos 1" in texto
    from app.negocio.formato import formatear_moneda
    assert formatear_moneda(liquidacion.neto) in texto


def test_disclaimer_de_documento_de_ejemplo_se_ve_en_rojo(conn, profesional, consultorio, tmp_path):
    """Pedido explícito de la clienta ("PDF rojo"): el párrafo que avisa
    que es un documento de ejemplo, no una liquidación real, se destaca
    en rojo (`COLOR_ROJO`, no solo en itálica) — mismo criterio que
    importes negativos en el resto del sistema."""
    from app.pdf.estilos import COLOR_ROJO

    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])
    ruta = generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))

    color_esperado = int(COLOR_ROJO.hexval()[2:], 16)
    encontrado = False
    for pagina in fitz.open(ruta):
        for bloque_texto in pagina.get_text("dict")["blocks"]:
            for linea in bloque_texto.get("lines", []):
                for span in linea["spans"]:
                    if "Documento de ejemplo" in span["text"]:
                        assert span["color"] == color_esperado
                        encontrado = True
    assert encontrado, "no se encontró el párrafo del disclaimer en el PDF"


def test_pdf_incluye_descuento_de_feriado_cuando_hay(conn, profesional, consultorio, tmp_path):
    obtener_repositorio(conn, "FechasEspeciales").crear(
        Fecha="2026-11-02", Descripcion="Feriado de prueba", Tipo="Feriado nacional",
    )
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])
    assert liquidacion.descuentos_feriados

    ruta = generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))
    texto = "".join(pagina.get_text() for pagina in fitz.open(ruta))
    assert "Descuento feriado nacional (2026-11-02)" in texto


def test_tratamiento_se_muestra_sin_importar_la_categoria(conn, consultorio, tmp_path):
    """La clienta vio que un profesional categoría X no mostraba el
    Tratamiento en la liquidación simulada — `_nombre_completo` ya lo
    arma igual para cualquier categoría (`profesional["Tratamiento"] or
    ""`, mismo criterio que el resto del sistema), así que si el campo
    está cargado tiene que aparecer: queda cubierto para que no se
    rompa de rebote con algún cambio futuro."""
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="X", Tratamiento="Fgo.", NombrePila="Carlos", Apellido="Pérez",
    )
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=id_prof, periodo="2026-11", bloques=[bloque])

    ruta = generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))
    assert "Fgo. Carlos Pérez" in ruta

    texto = "".join(pagina.get_text() for pagina in fitz.open(ruta))
    assert "Fgo. Carlos Pérez" in texto


def test_descuento_por_volumen_de_horas_se_ve_en_rojo(conn, profesional, consultorio, tmp_path):
    """Pedido explícito de la clienta: los importes negativos de la
    tabla "Liquidación simulada" (acá, el descuento por volumen de
    horas) tienen que verse en rojo, mismo criterio que el resto del
    sistema ("Importes negativos en rojo, positivos en color normal")."""
    from app.pdf.estilos import COLOR_ROJO

    # 6hs semanales (no 2, el default de los otros tests): el esquema de
    # descuentos sembrado por defecto da 0% hasta 2hs — hace falta más
    # para que el descuento por volumen sea realmente negativo.
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=15, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])
    assert liquidacion.descuento_horas_pct > 0  # si no hay descuento, no hay nada que pintar de rojo
    ruta = generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))

    color_esperado = int(COLOR_ROJO.hexval()[2:], 16)
    encontrado = False
    for pagina in fitz.open(ruta):
        for bloque_texto in pagina.get_text("dict")["blocks"]:
            for linea in bloque_texto.get("lines", []):
                for span in linea["spans"]:
                    if span["text"].strip().startswith("-$"):
                        assert span["color"] == color_esperado
                        encontrado = True
    assert encontrado, "no se encontró ningún importe negativo pintado de rojo en el PDF"


def test_profesional_categoria_c_anonimiza_la_unidad(conn, consultorio, tmp_path):
    """Mismo criterio que `oferta_pdf`/`fotos_pdf`: categoría C (todavía
    no activo) muestra "Unidad {IdUnidad}" en vez del Departamento
    real — el resto de las categorías (R/A/B/E/X) muestran el dato
    real, confirmado por `test_genera_pdf_con_los_bloques_y_el_total`
    (categoría R)."""
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Suárez")
    id_unidad = obtener_repositorio(conn, "Consultorio").obtener(consultorio)["IdUnidad"]
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=id_prof, periodo="2026-11", bloques=[bloque])

    ruta = generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))
    texto = "".join(pagina.get_text() for pagina in fitz.open(ruta))
    assert f"consul 1 del Unidad {id_unidad} - Ramos 1" in texto
    assert "7mo L" not in texto


def test_sin_fotos_cargadas_muestra_el_aviso(conn, profesional, consultorio, tmp_path):
    """Pedido explícito de la clienta: una sección nueva "Fotos de los
    consultorios ofrecidos" al final del PDF — sin ninguna `Imagen`
    cargada para el consultorio del bloque, muestra el mismo aviso que
    el resto del sistema (`app.pdf.fotos_pdf.tabla_fotos`)."""
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])

    ruta = generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))
    texto = "".join(pagina.get_text() for pagina in fitz.open(ruta))
    assert "Fotos de los consultorios ofrecidos" in texto
    assert "Sin fotos cargadas." in texto


def test_con_foto_cargada_muestra_el_pie_con_nombre_y_valor(conn, profesional, consultorio, tmp_path):
    """Mismo pie que ya usan Propuesta/Disponibilidad con
    `mostrar_valor=True` ("Consultorio {N} — Valor hora regular
    {$}") — sin "Apto camilla", que acá no aporta nada (es una
    simulación de valores, no una oferta real)."""
    from app.negocio.formato import formatear_moneda

    obtener_repositorio(conn, "Imagen").crear(
        IdConsultorio=consultorio, RutaArchivo="/no/existe.jpg", NumeroOrden=1, Descripcion="Vista", Activo=1,
    )
    bloque = BloqueSimulado(dia_semana="Lunes", hora_inicio=9, hora_fin=11, id_consultorio=consultorio)
    liquidacion = calcular_liquidacion_simulada(conn, id_profesional=profesional, periodo="2026-11", bloques=[bloque])

    ruta = generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))
    texto = "".join(pagina.get_text() for pagina in fitz.open(ruta))
    valor = obtener_repositorio(conn, "Consultorio").obtener(consultorio)["ValorHoraRegularActual"]
    assert f"Consultorio 1 — Valor hora regular {formatear_moneda(valor, 2)}" in texto
    assert "Apto camilla" not in texto


def test_profesional_inexistente_rechaza(conn, tmp_path):
    from app.negocio.liquidacion_simulada import LiquidacionSimulada
    liquidacion = LiquidacionSimulada(
        id_profesional=999999, periodo="2026-11", bloques=[], horas_semanales=0, descuento_horas_pct=0, bruto=0,
    )
    with pytest.raises(ValueError):
        generar_pdf_liquidacion_simulada(conn, liquidacion, str(tmp_path))
