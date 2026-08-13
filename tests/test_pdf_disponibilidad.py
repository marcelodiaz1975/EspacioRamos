import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.pdf.disponibilidad_pdf import generar_pdf_disponibilidad, generar_pdfs_disponibilidad_por_localidad
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_edificio(conn, nombre, localidad=None):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre=nombre, DomicilioLocalidad=localidad)
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento="1ro A")
    obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, Ventana=1, ValorHoraRegularActual=1000,
    )
    return id_edificio


def test_genera_pdf_valido_con_un_edificio(conn, tmp_path):
    _crear_edificio(conn, "Ramos 1", "CABA")
    ruta = generar_pdf_disponibilidad(conn, str(tmp_path))
    assert ruta.endswith(".pdf")
    with open(ruta, "rb") as f:
        contenido = f.read()
    assert contenido.startswith(b"%PDF")


def test_nombre_archivo_no_incluye_localidad_si_hay_una_sola(conn, tmp_path):
    _crear_edificio(conn, "Ramos 1", "CABA")
    ruta = generar_pdf_disponibilidad(conn, str(tmp_path))
    assert "CABA" not in ruta


def test_nombre_archivo_incluye_localidad_si_hay_varias(conn, tmp_path):
    _crear_edificio(conn, "Ramos 1", "CABA")
    id_ed2 = _crear_edificio(conn, "San Justo 1", "San Justo")
    ruta = generar_pdf_disponibilidad(conn, str(tmp_path), ids_edificio=[id_ed2])
    assert "San Justo" in ruta


def test_por_localidad_genera_un_archivo_separado_por_cada_una(conn, tmp_path):
    _crear_edificio(conn, "Ramos 1", "CABA")
    _crear_edificio(conn, "San Justo 1", "San Justo")

    rutas = generar_pdfs_disponibilidad_por_localidad(conn, str(tmp_path))

    assert len(rutas) == 2
    assert any("CABA" in r for r in rutas)
    assert any("San Justo" in r for r in rutas)
    for ruta in rutas:
        with open(ruta, "rb") as f:
            assert f.read().startswith(b"%PDF")
