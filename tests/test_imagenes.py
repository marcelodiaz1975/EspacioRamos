from pathlib import Path

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.imagenes import agregar_imagen, alternar_activo, eliminar_imagen, imagenes_del_alcance, reordenar
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)


def _archivo_jpg(tmp_path, nombre="foto.jpg", contenido=b"x" * 100) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    ruta = tmp_path / nombre
    ruta.write_bytes(contenido)
    return str(ruta)


def _configurar_carpeta_base(conn, ruta) -> None:
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBaseArchivos=str(ruta))


def test_agregar_imagen_sin_alcance_falla(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    with pytest.raises(ValueError):
        agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path))


def test_agregar_imagen_con_dos_alcances_falla(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    with pytest.raises(ValueError):
        agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path), id_consultorio=consultorio, id_edificio=1)


def test_agregar_imagen_copia_el_archivo_y_registra_la_fila(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen = _archivo_jpg(tmp_path / "origen")

    id_imagen = agregar_imagen(conn, ruta_origen=origen, descripcion="Vista general", id_consultorio=consultorio)

    fila = obtener_repositorio(conn, "Imagen").obtener(id_imagen)
    assert fila["Descripcion"] == "Vista general"
    assert fila["NumeroOrden"] == 1
    assert fila["Activo"] == 1
    ruta_copia = Path(fila["RutaArchivo"])
    assert ruta_copia.is_file()
    assert ruta_copia != Path(origen)  # se copió, no referenció el original


def test_agregar_imagen_formato_no_soportado_falla(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    ruta = tmp_path / "documento.pdf"
    ruta.write_bytes(b"x")
    with pytest.raises(ValueError):
        agregar_imagen(conn, ruta_origen=str(ruta), id_consultorio=consultorio)


def test_agregar_imagen_supera_tamano_maximo_falla(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    obtener_repositorio(conn, "Configuracion").actualizar(1, TamanoMaximoImagenMB=0.00001)
    with pytest.raises(ValueError):
        agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path), id_consultorio=consultorio)


def test_agregar_dos_imagenes_incrementa_el_orden(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen_dir = tmp_path / "origen"
    origen_dir.mkdir()
    id1 = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "a.jpg"), id_consultorio=consultorio)
    id2 = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "b.jpg"), id_consultorio=consultorio)

    repo = obtener_repositorio(conn, "Imagen")
    assert repo.obtener(id1)["NumeroOrden"] == 1
    assert repo.obtener(id2)["NumeroOrden"] == 2


def test_agregar_mismo_nombre_no_pisa_el_archivo_anterior(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen1 = tmp_path / "a.jpg"
    origen1.write_bytes(b"primero")
    id1 = agregar_imagen(conn, ruta_origen=str(origen1), id_consultorio=consultorio)
    origen1.write_bytes(b"segundo")  # mismo nombre, otro contenido
    id2 = agregar_imagen(conn, ruta_origen=str(origen1), id_consultorio=consultorio)

    repo = obtener_repositorio(conn, "Imagen")
    ruta1 = Path(repo.obtener(id1)["RutaArchivo"])
    ruta2 = Path(repo.obtener(id2)["RutaArchivo"])
    assert ruta1 != ruta2
    assert ruta1.read_bytes() == b"primero"
    assert ruta2.read_bytes() == b"segundo"


def test_eliminar_imagen_borra_fila_y_archivo(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    id_imagen = agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen"), id_consultorio=consultorio)
    ruta = Path(obtener_repositorio(conn, "Imagen").obtener(id_imagen)["RutaArchivo"])

    eliminar_imagen(conn, id_imagen)

    assert obtener_repositorio(conn, "Imagen").obtener(id_imagen) is None
    assert not ruta.is_file()


def test_reordenar_intercambia_numero_orden(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen_dir = tmp_path / "origen"
    origen_dir.mkdir()
    id1 = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "a.jpg"), id_consultorio=consultorio)
    id2 = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "b.jpg"), id_consultorio=consultorio)

    reordenar(conn, id2, -1)  # sube la segunda al primer lugar

    repo = obtener_repositorio(conn, "Imagen")
    assert repo.obtener(id1)["NumeroOrden"] == 2
    assert repo.obtener(id2)["NumeroOrden"] == 1


def test_reordenar_en_el_extremo_no_hace_nada(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id1 = agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen"), id_consultorio=consultorio)
    reordenar(conn, id1, -1)  # ya es la primera, no hay a dónde subir
    assert obtener_repositorio(conn, "Imagen").obtener(id1)["NumeroOrden"] == 1


def test_alternar_activo(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_imagen = agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen"), id_consultorio=consultorio)
    alternar_activo(conn, id_imagen)
    assert obtener_repositorio(conn, "Imagen").obtener(id_imagen)["Activo"] == 0
    alternar_activo(conn, id_imagen)
    assert obtener_repositorio(conn, "Imagen").obtener(id_imagen)["Activo"] == 1


def test_imagenes_del_alcance_trae_activas_e_inactivas(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_imagen = agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen"), id_consultorio=consultorio)
    alternar_activo(conn, id_imagen)
    filas = imagenes_del_alcance(conn, None, None, consultorio)
    assert len(filas) == 1
