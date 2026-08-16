import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.documentacion_profesional import agregar_documento, eliminar_documento, listar_documentos
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _configurar_carpeta_base(conn, ruta) -> None:
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBaseArchivos=str(ruta))


def test_listar_documentos_carpeta_vacia(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    assert listar_documentos(conn, "R1") == []


def test_agregar_documento_pdf_lo_copia(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen = tmp_path / "origen" / "dni.pdf"
    origen.parent.mkdir()
    origen.write_bytes(b"contenido")

    destino = agregar_documento(conn, "R1", str(origen))

    assert destino.is_file()
    assert destino != origen
    assert destino.read_bytes() == b"contenido"
    assert listar_documentos(conn, "R1") == [destino]


def test_agregar_documento_imagen_tambien_se_acepta(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen = tmp_path / "origen" / "matricula.jpg"
    origen.parent.mkdir()
    origen.write_bytes(b"x")
    destino = agregar_documento(conn, "R1", str(origen))
    assert destino.is_file()


def test_agregar_documento_formato_no_soportado_falla(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    origen = tmp_path / "datos.xlsx"
    origen.write_bytes(b"x")
    with pytest.raises(ValueError):
        agregar_documento(conn, "R1", str(origen))


def test_agregar_documento_inexistente_falla(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    with pytest.raises(ValueError):
        agregar_documento(conn, "R1", str(tmp_path / "no-existe.pdf"))


def test_agregar_mismo_nombre_no_pisa_el_anterior(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen = tmp_path / "dni.pdf"
    origen.write_bytes(b"primero")
    d1 = agregar_documento(conn, "R1", str(origen))
    origen.write_bytes(b"segundo")
    d2 = agregar_documento(conn, "R1", str(origen))

    assert d1 != d2
    assert d1.read_bytes() == b"primero"
    assert d2.read_bytes() == b"segundo"
    assert set(listar_documentos(conn, "R1")) == {d1, d2}


def test_eliminar_documento(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen = tmp_path / "dni.pdf"
    origen.write_bytes(b"x")
    destino = agregar_documento(conn, "R1", str(origen))

    eliminar_documento(conn, "R1", destino.name)

    assert not destino.is_file()
    assert listar_documentos(conn, "R1") == []


def test_eliminar_documento_inexistente_no_falla(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    eliminar_documento(conn, "R1", "no-existe.pdf")


def test_documentos_de_distintos_profesionales_no_se_mezclan(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen = tmp_path / "dni.pdf"
    origen.write_bytes(b"x")
    agregar_documento(conn, "R1", str(origen))
    assert listar_documentos(conn, "R2") == []
