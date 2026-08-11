import pytest
from reportlab.platypus import Paragraph

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.pdf.grilla_pdf import _tabla_grilla_edificio
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

    fila_etiquetas = tabla._cellvalues[2]
    celdas_unidad = fila_etiquetas[2:]  # las primeras 2 columnas son Tipo/Horario, vacías en esta fila
    assert len(celdas_unidad) == 6 * len(unidades)  # 6 días x 4 unidades

    esperado = [u["Departamento"] for _ in range(6) for u in unidades]
    obtenido = [c.getPlainText() if isinstance(c, Paragraph) else c for c in celdas_unidad]
    assert obtenido == esperado


def test_etiquetas_de_unidad_son_paragraph_para_poder_ajustar(conn):
    """Un texto plano en una celda angosta de reportlab no ajusta ni
    envuelve — tiene que ser un Paragraph para poder partirse en líneas en
    vez de desbordar sobre la celda vecina."""
    unidades = _unidades_ficticias(5)
    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=[9], ancho=400)
    fila_etiquetas = tabla._cellvalues[2]
    assert all(isinstance(c, Paragraph) for c in fila_etiquetas[2:])


def test_una_sola_unidad_no_rompe(conn):
    unidades = _unidades_ficticias(1)
    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=[9], ancho=500)
    fila_etiquetas = tabla._cellvalues[2]
    assert [c.getPlainText() for c in fila_etiquetas[2:]] == ['1no "X"'] * 6


def test_grilla_edificio_real_conserva_columnas(conn):
    """Reproduce el caso real que disparó el bug: un edificio con 4
    unidades importado desde planilla."""
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    nombres = ['15 "H"', '7mo "L"', '9no "C"', 'EP "K"']
    unidades = []
    for nombre in nombres:
        id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=nombre)
        unidades.append({"IdUnidad": id_unidad, "Departamento": nombre})

    tabla = _tabla_grilla_edificio(conn, unidades, grilla={}, horas=list(range(9, 21)), ancho=550)
    fila_etiquetas = tabla._cellvalues[2]
    obtenido = [c.getPlainText() for c in fila_etiquetas[2:2 + len(nombres)]]
    assert obtenido == nombres
