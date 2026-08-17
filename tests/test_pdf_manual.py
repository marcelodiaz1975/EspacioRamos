import fitz
import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.pdf.manual_pdf import generar_pdf_manual


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_sin_secciones_con_ayuda_avisa_y_genera_pdf_valido(conn, tmp_path):
    ruta = generar_pdf_manual(conn, str(tmp_path), [])
    assert ruta.endswith("Manual de usuario.pdf")
    texto = fitz.open(ruta)[0].get_text()
    assert "Todavía no hay ayuda contextual cargada." in texto


def test_omite_secciones_sin_texto_de_ayuda(conn, tmp_path):
    secciones = [("Principal", "Con ayuda", "Texto de ayuda."), ("Principal", "Sin ayuda", "")]
    ruta = generar_pdf_manual(conn, str(tmp_path), secciones)
    texto = "".join(pagina.get_text() for pagina in fitz.open(ruta))
    assert "Con ayuda" in texto
    assert "Sin ayuda" not in texto


def test_agrupa_por_categoria_en_orden(conn, tmp_path):
    secciones = [
        ("Principal", "Uno", "Ayuda uno."),
        ("Principal", "Dos", "Ayuda dos."),
        ("Catálogos", "Tres", "Ayuda tres."),
    ]
    ruta = generar_pdf_manual(conn, str(tmp_path), secciones)
    texto = "".join(pagina.get_text() for pagina in fitz.open(ruta))
    assert texto.index("Principal") < texto.index("Uno") < texto.index("Dos") < texto.index("Catálogos") < texto.index("Tres")
    # Solo un encabezado de categoría "Principal" aunque haya dos secciones dentro
    assert texto.count("Principal") == 1


def test_texto_de_ayuda_aparece_completo(conn, tmp_path):
    secciones = [("Principal", "Alguna pantalla", "Este es el texto de ayuda de la pantalla.")]
    ruta = generar_pdf_manual(conn, str(tmp_path), secciones)
    texto = "".join(pagina.get_text() for pagina in fitz.open(ruta))
    assert "Este es el texto de ayuda de la pantalla." in texto
